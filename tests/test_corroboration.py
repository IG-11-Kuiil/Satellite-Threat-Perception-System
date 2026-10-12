import pytest
from config import AnalysisSettings
from detector import corroborate_candidates, remove_duplicate_detections, visible_tile_match


def detection(bbox, confidence=.8, **extra):
    return {"class":"aircraft","confidence":confidence,"bbox":bbox,**extra}


@pytest.mark.parametrize("scale,shift",[(.25,0),(1,0),(2,1000),(5,-300)])
def test_shifted_crop_fragment_compared_in_its_visible_window(scale,shift):
    def transformed(values):
        return [v*scale+shift for v in values]
    complete = detection(transformed([80,40,140,100]))
    fragment = detection(transformed([70,40,101,100]),.7,edge_truncated=True,
                         tile_bounds=transformed([0,0,100,200]))
    assert visible_tile_match(fragment,complete,.35)
    assert remove_duplicate_detections([fragment,complete]) == [complete]


def test_crop_projection_does_not_merge_an_adjacent_aircraft():
    complete = detection([80,40,140,100])
    other = detection([70,110,101,170],edge_truncated=True,tile_bounds=[0,0,100,200])
    assert not visible_tile_match(other,complete,.35)
    assert len(remove_duplicate_detections([complete,other])) == 2


def test_crop_projection_needs_complete_box_to_cross_same_boundary():
    complete = detection([40,40,90,100])
    fragment = detection([70,40,101,100],edge_truncated=True,tile_bounds=[0,0,100,200])
    assert not visible_tile_match(fragment,complete,.35)


def test_weak_candidate_requires_both_models_and_keeps_original_score():
    primary = [detection([0,0,100,100],.16)]
    supporter = [detection([0,0,100,100],.60)]
    ds = corroborate_candidates(primary,supporter,AnalysisSettings(),"supporter")
    assert len(ds) == 1
    assert ds[0]["confidence"] == .16
    assert ds[0]["supporting_confidence"] == .60
    assert ds[0]["review_required"]
    assert ds[0]["accepted_by"] == "cross_model_review"
    assert corroborate_candidates(primary,[],AnalysisSettings(),"supporter") == []
    assert corroborate_candidates([],supporter,AnalysisSettings(),"supporter") == []


def test_nonmatching_or_below_threshold_support_does_not_rescue():
    primary = [detection([0,0,100,100],.16)]
    assert not corroborate_candidates(primary,[detection([200,200,300,300],.8)],AnalysisSettings(),"supporter")
    assert not corroborate_candidates(primary,[detection([0,0,100,100],.3)],AnalysisSettings(),"supporter")


def test_support_does_not_duplicate_a_primary_detection():
    primary = [detection([0,0,100,100],.8),detection([0,0,100,100],.2)]
    ds = corroborate_candidates(primary,[detection([0,0,100,100],.9)],AnalysisSettings(),"supporter")
    assert len(ds) == 1 and ds[0]["confidence"] == .8


def test_missing_verifier_preserves_primary_result(tmp_path,monkeypatch):
    from PIL import Image
    import numpy as np
    from types import SimpleNamespace
    from detector import SatelliteDetector
    class Model:
        names = {0:"plane"}
        def predict(self,image,**kwargs):
            return [SimpleNamespace(boxes=[SimpleNamespace(cls=np.array([0]),conf=np.array([score]),
                                       xyxy=np.array([bbox])) for score,bbox in
                                       [(.8,[10,10,40,40]),(.2,[60,60,90,90])]])]
    path=tmp_path/"test.png";Image.new("RGB",(100,100)).save(path)
    detector = SatelliteDetector(model=Model())
    def unavailable(*args):
        raise RuntimeError("Offline")
    monkeypatch.setattr(detector,"_verify_candidates",unavailable)
    result = detector.predict(path)
    assert len(result["detections"]) == 1
    assert result["verification_warning"]
