"""Auditable prototype policy. These cutoffs are not military or intelligence standards."""
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class AssessmentPolicy:
    id: str = "prototype-presence-v1"
    low_presence_max: int = 2
    medium_presence_max: int = 6
    aircraft_weight: float = 2
    vehicle_weight: float = 1
    activity_rank_weight: float = 2
    proximity_density_weight: float = 2
    trend_threshold: float = 2
    high_review_aircraft_delta: int = 2
    high_review_vehicle_delta: int = 4
    medium_review_density_delta: float = 0.25

    def snapshot(self):
        return {**asdict(self),"basis":"Local demonstration heuristics; not a military standard",
                "validated_operationally":False,"analytic_confidence":"Not assessed",
                "threat_level":"Not assessed"}


DEFAULT_POLICY = AssessmentPolicy()


def describe_policy(policy):
    return [f"Policy: {policy['id']} (prototype heuristic, not a military standard).",
            f"Asset presence: LOW 0-{policy['low_presence_max']}, MEDIUM {policy['low_presence_max']+1}-{policy['medium_presence_max']}, HIGH {policy['medium_presence_max']+1}+.",
            f"Trend weights: aircraft={policy['aircraft_weight']}, vehicles={policy['vehicle_weight']}, activity rank={policy['activity_rank_weight']}, proximity density={policy['proximity_density_weight']}.",
            f"Trend threshold: +/-{policy['trend_threshold']}; this score is not a probability.",
            f"High review priority: absolute aircraft change >= {policy['high_review_aircraft_delta']} or vehicles >= {policy['high_review_vehicle_delta']}.",
            f"Medium review priority: nonzero asset change or proximity density change >= {policy['medium_review_density_delta']:.0%}; otherwise Low.",
            "Formal analytic confidence and military threat level: Not assessed."]
