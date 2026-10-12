"""Aggregate comparison with bounded spatial contribution and symmetric priority."""
from assessment_policy import DEFAULT_POLICY
ACTIVITY_RANK = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}


def trend_score(aircraft_delta,vehicle_delta,rank_delta,density_delta):
    p = DEFAULT_POLICY
    return (p.aircraft_weight*aircraft_delta+p.vehicle_weight*vehicle_delta+
            p.activity_rank_weight*rank_delta+p.proximity_density_weight*density_delta)


def compare_counts(previous_count, current_count, asset_name="asset"):
    difference = current_count-previous_count
    return {"asset_name": asset_name, "previous_count": previous_count, "current_count": current_count,
            "difference": difference,
            "trend": "increase" if difference > 0 else "decrease" if difference < 0 else "no_change"}


def compare_activity_levels(previous_level, current_level):
    if previous_level not in ACTIVITY_RANK or current_level not in ACTIVITY_RANK:
        raise ValueError("Activity levels must be LOW, MEDIUM, or HIGH.")
    difference = ACTIVITY_RANK[current_level]-ACTIVITY_RANK[previous_level]
    return {"previous_level": previous_level, "current_level": current_level,
            "rank_difference": difference,
            "trend": "increase" if difference > 0 else "decrease" if difference < 0 else "no_change"}


def pair_density(analysis):
    if "spatial" in analysis:
        return analysis["spatial"]["pair_density"]
    n = analysis["aircraft_count"]
    return len(analysis["clusters"])/(n*(n-1)/2) if n > 1 else 0.0


def assess_activity_trend(aircraft_change, vehicle_change, cluster_change, activity_change, density_difference=0.0):
    score = trend_score(aircraft_change["difference"],vehicle_change["difference"],activity_change["rank_difference"],density_difference)
    cutoff = DEFAULT_POLICY.trend_threshold
    return "Increased" if score >= cutoff else "Decreased" if score <= -cutoff else "Stable"


def assess_priority(aircraft_change, vehicle_change, cluster_change, activity_trend,
                    current_activity_level, previous_activity_level="LOW", density_difference=0.0):
    magnitude = abs(aircraft_change["difference"])
    if magnitude >= DEFAULT_POLICY.high_review_aircraft_delta or abs(vehicle_change["difference"]) >= DEFAULT_POLICY.high_review_vehicle_delta:
        return "High"
    if magnitude > 0 or abs(vehicle_change["difference"]) > 0 or abs(density_difference) >= DEFAULT_POLICY.medium_review_density_delta:
        return "Medium"
    return "Low"


def compare_scenes(previous_analysis, current_analysis):
    aircraft = compare_counts(previous_analysis["aircraft_count"], current_analysis["aircraft_count"], "aircraft")
    vehicles = compare_counts(previous_analysis["vehicle_count"], current_analysis["vehicle_count"], "vehicle")
    pairs = compare_counts(len(previous_analysis["clusters"]), len(current_analysis["clusters"]), "aircraft_cluster_pairs")
    activity = compare_activity_levels(previous_analysis["activity_level"], current_analysis["activity_level"])
    density_delta = pair_density(current_analysis)-pair_density(previous_analysis)
    score = trend_score(aircraft["difference"],vehicles["difference"],activity["rank_difference"],density_delta)
    trend = assess_activity_trend(aircraft, vehicles, pairs, activity, density_delta)
    priority = assess_priority(aircraft, vehicles, pairs, trend, current_analysis["activity_level"],
                               previous_analysis["activity_level"], density_delta)
    reasons = []
    if aircraft["difference"]:
        reasons.append(f"Aircraft count changed by {format_signed(aircraft['difference'])}.")
    if vehicles["difference"]:
        reasons.append(f"Vehicle count changed by {format_signed(vehicles['difference'])}.")
    if abs(density_delta) >= DEFAULT_POLICY.medium_review_density_delta:
        reasons.append(f"Aircraft proximity density changed by at least {DEFAULT_POLICY.medium_review_density_delta*100:g} percentage points.")
    if not reasons:
        reasons.append("No substantial change under the configured count and proximity rules.")
    warnings = ["Compare the same ground area, crop, and scale. Image alignment and asset matching are not performed.",
                "Detection differences may reflect visibility or model errors rather than physical changes."]
    if previous_analysis.get("low_confidence_count", 0) or current_analysis.get("low_confidence_count", 0):
        warnings.append("Low-confidence aircraft detections contribute to this comparison; verify those boxes before accepting count changes.")
    before_primary = previous_analysis.get("primary_aircraft_count",previous_analysis["aircraft_count"])
    after_primary = current_analysis.get("primary_aircraft_count",current_analysis["aircraft_count"])
    review_candidates = previous_analysis.get("review_candidate_count",0)+current_analysis.get("review_candidate_count",0)
    delta_min = after_primary-previous_analysis["aircraft_count"]
    delta_max = current_analysis["aircraft_count"]-before_primary
    if review_candidates:
        warnings.append("Reported totals include cross-model review candidates. The exact count change is provisional until those candidates are confirmed.")
    warnings.append("Clouds, shadows, and unequal visible coverage may conceal aircraft; aggregate totals alone cannot establish arrivals or departures.")
    if min(previous_analysis["aircraft_count"], current_analysis["aircraft_count"]) < 2:
        warnings.append("Proximity density is weak evidence with fewer than two aircraft in either scene.")
    if "width" in previous_analysis and "width" in current_analysis:
        ratio1 = previous_analysis["width"]/previous_analysis["height"]
        ratio2 = current_analysis["width"]/current_analysis["height"]
        if abs(ratio2/ratio1-1) > 0.05:
            warnings.append("Image aspect ratios differ by more than 5%; scenes may cover different ground areas.")
    return {"aircraft_change": aircraft, "vehicle_change": vehicles, "cluster_change": pairs,
            "activity_change": activity, "density_difference": round(density_delta, 4),
            "trend_score": round(score, 4), "activity_trend": trend, "priority": priority,
            "primary_aircraft_change":compare_counts(before_primary,after_primary,"primary_aircraft"),
            "review_candidate_count":review_candidates,"requires_confirmation":bool(review_candidates),
            "assessment_policy_id":DEFAULT_POLICY.id,
            "candidate_sensitivity":{"minimum_delta":delta_min,"maximum_delta":delta_max,
                                     "direction_depends_on_candidates":bool(review_candidates and delta_min <= 0 <= delta_max),
                                     "meaning":"Range from including/excluding known review candidates only; not a confidence interval or bound on missed aircraft."},
            "priority_reasons": reasons, "warnings": warnings}


def format_signed(value):
    return f"+{value}" if value > 0 else str(value)


def generate_change_summary(result):
    aircraft, vehicles = result["aircraft_change"], result["vehicle_change"]
    parts = [f"Aircraft detections changed from {aircraft['previous_count']} to {aircraft['current_count']} ({format_signed(aircraft['difference'])})."]
    if result.get("review_candidate_count"):
        primary = result["primary_aircraft_change"]
        parts.append(f"Totals include {result['review_candidate_count']} candidate(s) requiring manual confirmation. Primary detections changed from {primary['previous_count']} to {primary['current_count']} ({format_signed(primary['difference'])}); the exact total change is provisional.")
        sensitivity = result.get("candidate_sensitivity")
        if sensitivity:
            parts.append(f"Known-candidate sensitivity: {format_signed(sensitivity['minimum_delta'])} to {format_signed(sensitivity['maximum_delta'])} aircraft. This is not a statistical confidence interval.")
    if vehicles["previous_count"] or vehicles["current_count"]:
        parts.append(f"Vehicle detections changed from {vehicles['previous_count']} to {vehicles['current_count']} ({format_signed(vehicles['difference'])}).")
    activity = result["activity_change"]
    parts.append(f"Observed asset presence: {activity['previous_level']} → {activity['current_level']}.")
    parts.append(f"Activity trend: {result['activity_trend']}. Review priority: {result['priority']}.")
    parts.extend(result["priority_reasons"])
    parts.append("This is an aggregate detection comparison; individual aircraft are not tracked between images.")
    return " ".join(parts)
