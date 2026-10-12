"""Transparent count-based scene heuristics."""
from config import LOW_ACTIVITY_MAX, MEDIUM_ACTIVITY_MAX


def compute_activity_level(aircraft_count, vehicle_count):
    if aircraft_count < 0 or vehicle_count < 0:
        raise ValueError("Asset counts cannot be negative.")
    total = aircraft_count+vehicle_count
    if total <= LOW_ACTIVITY_MAX:
        return "LOW"
    return "MEDIUM" if total <= MEDIUM_ACTIVITY_MAX else "HIGH"


def generate_summary(aircraft_count, vehicle_count, activity_level, clusters,
                     has_low_confidence_detection=False, spatial=None, vehicles_enabled=False):
    parts = [f"Detected {aircraft_count} aircraft."]
    if vehicles_enabled:
        parts.append(f"Detected {vehicle_count} vehicles (experimental detection).")
    if spatial is not None:
        if spatial["group_count"]:
            parts.append(f"Aircraft form {spatial['group_count']} proximity group(s), with {len(clusters)} nearby pair(s).")
        if aircraft_count and spatial["isolated_count"]:
            parts.append(f"{spatial['isolated_count']} aircraft have no nearby detected aircraft.")
    elif clusters:
        parts.append(f"There are {len(clusters)} nearby aircraft pair(s).")
    elif aircraft_count:
        parts.append("No nearby aircraft pairs were found.")
    if aircraft_count == 0:
        parts.append("No aircraft detections does not establish that aircraft are absent.")
    if has_low_confidence_detection:
        parts.append("Some aircraft detections have confidence below 40%; verify those boxes manually.")
    parts.append(f"Observed asset presence is {activity_level}, based on detected counts.")
    parts.append("Counts do not establish movement, military intent, or threat. Human review is required.")
    return " ".join(parts)
