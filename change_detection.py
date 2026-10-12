"""Aggregate comparison with bounded spatial contribution and symmetric priority."""
ACTIVITY_RANK = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}


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
    score = 2*aircraft_change["difference"]+vehicle_change["difference"]
    score += 2*activity_change["rank_difference"]+2*density_difference
    return "Increased" if score >= 2 else "Decreased" if score <= -2 else "Stable"


def assess_priority(aircraft_change, vehicle_change, cluster_change, activity_trend,
                    current_activity_level, previous_activity_level="LOW", density_difference=0.0):
    magnitude = abs(aircraft_change["difference"])
    if magnitude >= 2 or abs(vehicle_change["difference"]) >= 4:
        return "High"
    if magnitude == 1 or abs(vehicle_change["difference"]) > 0 or abs(density_difference) >= 0.25:
        return "Medium"
    return "Low"


def compare_scenes(previous_analysis, current_analysis):
    aircraft = compare_counts(previous_analysis["aircraft_count"], current_analysis["aircraft_count"], "aircraft")
    vehicles = compare_counts(previous_analysis["vehicle_count"], current_analysis["vehicle_count"], "vehicle")
    pairs = compare_counts(len(previous_analysis["clusters"]), len(current_analysis["clusters"]), "aircraft_cluster_pairs")
    activity = compare_activity_levels(previous_analysis["activity_level"], current_analysis["activity_level"])
    density_delta = pair_density(current_analysis)-pair_density(previous_analysis)
    score = 2*aircraft["difference"]+vehicles["difference"]+2*activity["rank_difference"]+2*density_delta
    trend = assess_activity_trend(aircraft, vehicles, pairs, activity, density_delta)
    priority = assess_priority(aircraft, vehicles, pairs, trend, current_analysis["activity_level"],
                               previous_analysis["activity_level"], density_delta)
    reasons = []
    if aircraft["difference"]:
        reasons.append(f"Aircraft count changed by {format_signed(aircraft['difference'])}.")
    if vehicles["difference"]:
        reasons.append(f"Vehicle count changed by {format_signed(vehicles['difference'])}.")
    if abs(density_delta) >= 0.25:
        reasons.append("Aircraft proximity density changed by at least 25 percentage points.")
    if not reasons:
        reasons.append("No substantial change under the configured count and proximity rules.")
    warnings = ["Compare the same ground area, crop, and scale. Image alignment and asset matching are not performed.",
                "Detection differences may reflect visibility or model errors rather than physical changes."]
    if previous_analysis.get("low_confidence_count", 0) or current_analysis.get("low_confidence_count", 0):
        warnings.append("Low-confidence aircraft detections contribute to this comparison; verify those boxes before accepting count changes.")
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
            "priority_reasons": reasons, "warnings": warnings}


def format_signed(value):
    return f"+{value}" if value > 0 else str(value)


def generate_change_summary(result):
    aircraft, vehicles = result["aircraft_change"], result["vehicle_change"]
    parts = [f"Aircraft detections changed from {aircraft['previous_count']} to {aircraft['current_count']} ({format_signed(aircraft['difference'])})."]
    if vehicles["previous_count"] or vehicles["current_count"]:
        parts.append(f"Vehicle detections changed from {vehicles['previous_count']} to {vehicles['current_count']} ({format_signed(vehicles['difference'])}).")
    activity = result["activity_change"]
    parts.append(f"Observed asset presence: {activity['previous_level']} → {activity['current_level']}.")
    parts.append(f"Activity trend: {result['activity_trend']}. Review priority: {result['priority']}.")
    parts.extend(result["priority_reasons"])
    parts.append("This is an aggregate detection comparison; individual aircraft are not tracked between images.")
    return " ".join(parts)
