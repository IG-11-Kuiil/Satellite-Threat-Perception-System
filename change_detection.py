ACTIVITY_RANK = {
    "LOW": 0,
    "MEDIUM": 1,
    "HIGH": 2,
}


def compare_counts(previous_count: int, current_count: int, asset_name: str = "asset"):
    difference = current_count - previous_count

    if difference > 0:
        trend = "increase"
    elif difference < 0:
        trend = "decrease"
    else:
        trend = "no_change"

    return {
        "asset_name": asset_name,
        "previous_count": previous_count,
        "current_count": current_count,
        "difference": difference,
        "trend": trend,
    }


def compare_activity_levels(previous_level: str, current_level: str):
    previous_rank = ACTIVITY_RANK.get(previous_level, 0)
    current_rank = ACTIVITY_RANK.get(current_level, 0)
    difference = current_rank - previous_rank

    if difference > 0:
        trend = "increase"
    elif difference < 0:
        trend = "decrease"
    else:
        trend = "no_change"

    return {
        "previous_level": previous_level,
        "current_level": current_level,
        "rank_difference": difference,
        "trend": trend,
    }


def assess_activity_trend(aircraft_change, vehicle_change, cluster_change, activity_change):
    score = 0

    score += aircraft_change["difference"] * 2
    score += vehicle_change["difference"]
    score += cluster_change["difference"]
    score += activity_change["rank_difference"] * 2

    if score >= 2:
        return "Increased"
    elif score <= -2:
        return "Decreased"
    return "Stable"


def assess_priority(aircraft_change, vehicle_change, cluster_change, activity_trend, current_activity_level):
    aircraft_delta = aircraft_change["difference"]
    vehicle_delta = vehicle_change["difference"]
    cluster_delta = cluster_change["difference"]

    if aircraft_delta >= 2:
        return "High"

    if current_activity_level == "HIGH" and (aircraft_delta > 0 or cluster_delta > 0):
        return "High"

    if activity_trend == "Increased" and cluster_delta > 0:
        return "High"

    if aircraft_delta == 1 or vehicle_delta >= 2 or cluster_delta > 0:
        return "Medium"

    return "Low"


def compare_scenes(previous_analysis, current_analysis):
    aircraft_change = compare_counts(
        previous_analysis["aircraft_count"],
        current_analysis["aircraft_count"],
        asset_name="aircraft",
    )

    vehicle_change = compare_counts(
        previous_analysis["vehicle_count"],
        current_analysis["vehicle_count"],
        asset_name="vehicle",
    )

    cluster_change = compare_counts(
        len(previous_analysis["clusters"]),
        len(current_analysis["clusters"]),
        asset_name="aircraft_cluster_pairs",
    )

    activity_change = compare_activity_levels(
        previous_analysis["activity_level"],
        current_analysis["activity_level"],
    )

    activity_trend = assess_activity_trend(
        aircraft_change,
        vehicle_change,
        cluster_change,
        activity_change,
    )

    priority = assess_priority(
        aircraft_change,
        vehicle_change,
        cluster_change,
        activity_trend,
        current_analysis["activity_level"],
    )

    return {
        "aircraft_change": aircraft_change,
        "vehicle_change": vehicle_change,
        "cluster_change": cluster_change,
        "activity_change": activity_change,
        "activity_trend": activity_trend,
        "priority": priority,
    }


def format_signed(value: int) -> str:
    if value > 0:
        return f"+{value}"
    return str(value)


def generate_change_summary(change_result):
    aircraft_change = change_result["aircraft_change"]
    vehicle_change = change_result["vehicle_change"]
    cluster_change = change_result["cluster_change"]
    activity_change = change_result["activity_change"]

    summary_parts = []

    summary_parts.append(
        "Aircraft count changed from "
        f"{aircraft_change['previous_count']} to {aircraft_change['current_count']} "
        f"({format_signed(aircraft_change['difference'])})."
    )

    summary_parts.append(
        "Vehicle count changed from "
        f"{vehicle_change['previous_count']} to {vehicle_change['current_count']} "
        f"({format_signed(vehicle_change['difference'])})."
    )

    summary_parts.append(
        "Aircraft cluster relationships changed from "
        f"{cluster_change['previous_count']} to {cluster_change['current_count']} "
        f"({format_signed(cluster_change['difference'])})."
    )

    if activity_change["trend"] == "increase":
        summary_parts.append(
            f"Overall activity increased from {activity_change['previous_level']} to {activity_change['current_level']}."
        )
    elif activity_change["trend"] == "decrease":
        summary_parts.append(
            f"Overall activity decreased from {activity_change['previous_level']} to {activity_change['current_level']}."
        )
    else:
        summary_parts.append(
            f"Overall activity remained {activity_change['current_level']}."
        )

    summary_parts.append(
        f"Activity trend is assessed as {change_result['activity_trend']}."
    )

    summary_parts.append(
        f"Review priority is assessed as {change_result['priority']}."
    )

    summary_parts.append(
        "This assessment is based on model detections and should be reviewed by a human analyst."
    )

    return " ".join(summary_parts)