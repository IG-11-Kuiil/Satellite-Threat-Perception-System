import pytest
from assessment_policy import DEFAULT_POLICY
from change_detection import compare_scenes


def scene(primary,candidates):
    total = primary+candidates
    return {"aircraft_count":total,"primary_aircraft_count":primary,"review_candidate_count":candidates,
            "vehicle_count":0,"clusters":[],"activity_level":"HIGH"}


@pytest.mark.parametrize("before,after,minimum,maximum,dependent",[
    ((9,0),(11,1),2,3,False),
    ((11,1),(9,0),-3,-2,False),
    ((9,0),(9,2),0,2,True),
    ((9,1),(9,1),-1,1,True),
    ((9,0),(9,0),0,0,False),
])
def test_candidate_sensitivity_is_not_just_primary_delta(before,after,minimum,maximum,dependent):
    result = compare_scenes(scene(*before),scene(*after))
    sensitivity = result["candidate_sensitivity"]
    assert sensitivity["minimum_delta"] == minimum
    assert sensitivity["maximum_delta"] == maximum
    assert sensitivity["direction_depends_on_candidates"] == dependent
    assert "not a confidence interval" in sensitivity["meaning"]


def test_policy_does_not_claim_operational_or_analytic_confidence():
    policy = DEFAULT_POLICY.snapshot()
    assert not policy["validated_operationally"]
    assert policy["analytic_confidence"] == policy["threat_level"] == "Not assessed"
