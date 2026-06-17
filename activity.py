def compute_activity_level(aircraft_count: int, vehicle_count: int) -> str:
    total = aircraft_count + vehicle_count

    if total <= 2:
        return "LOW"
    elif total <= 6:
        return "MEDIUM"
    return "HIGH"


def generate_summary(
    aircraft_count: int,
    vehicle_count: int,
    activity_level: str,
    clusters,
    has_low_confidence_detection=False
) -> str:
    summary_parts = []

    summary_parts.append(
        f"The image contains {aircraft_count} aircraft and {vehicle_count} vehicles."
    )

    if len(clusters) > 0:
        summary_parts.append(
            "Some detected aircraft appear clustered together, suggesting localized staging or parking activity."
        )
    else:
        summary_parts.append(
            "Detected assets appear relatively dispersed."
        )

    if aircraft_count > 0 and len(clusters) > 0 and aircraft_count > 2:
        summary_parts.append(
            "At least one additional aircraft appears more isolated from the clustered group."
        )

    if has_low_confidence_detection:
        summary_parts.append(
            "Model confidence remains limited in some regions, so smaller or atypical aircraft may not be fully captured."
        )

    summary_parts.append(
        f"Overall activity is assessed as {activity_level}."
    )

    summary_parts.append(
        "This scene should be reviewed by a human analyst."
    )

    return " ".join(summary_parts)