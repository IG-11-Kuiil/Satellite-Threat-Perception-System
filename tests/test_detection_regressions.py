"""Geometry regressions; no customer imagery or model weights committed."""
import numpy as np
from types import SimpleNamespace
from config import AnalysisSettings
from detector import SatelliteDetector, compute_iou, overlap_metrics, remove_duplicate_detections


def box(bbox, score=.8, truncated=False, kind="aircraft", polygon=None):
    d = {"class":kind,"confidence":score,"bbox":bbox,"edge_truncated":truncated}
    if polygon:
        d["polygon"] = polygon
    return d


def test_contained_seam_fragment_removed_even_with_low_iou_and_higher_confidence():
    complete = box([170,55,500,343],.68)
    fragment = box([320,100,499,246],.70,True)
    assert compute_iou(complete["bbox"],fragment["bbox"]) < .35
    assert remove_duplicate_detections([fragment,complete]) == [complete]


def test_nearby_independent_aircraft_are_retained():
    left,right = box([0,0,100,100]),box([95,0,195,100],.9)
    assert len(remove_duplicate_detections([left,right])) == 2


def test_unmatched_edge_aircraft_is_not_discarded():
    fragment = box([0,0,30,50],.6,True)
    assert remove_duplicate_detections([fragment]) == [fragment]


def test_nested_boxes_are_not_merged_by_containment_without_seam_evidence():
    assert len(remove_duplicate_detections([box([0,0,100,100]),box([30,30,50,50])])) == 2


def test_rotated_nearby_aircraft_use_polygon_overlap_not_enclosing_rectangle():
    first = box([0,0,100,100],polygon=[[0,0],[100,90],[100,100],[0,10]])
    second = box([0,0,100,100],polygon=[[0,90],[90,0],[100,0],[10,90]])
    assert compute_iou(first["bbox"],second["bbox"]) == 1
    assert overlap_metrics(first,second)[0] < .35
    assert len(remove_duplicate_detections([first,second])) == 2


def test_obb_class_mapping_polygon_offset_and_internal_seam_flag():
    model = SimpleNamespace(names={0:"plane",1:"small-vehicle",2:"ship"})
    detector = SatelliteDetector(model=model)
    plane = SimpleNamespace(cls=np.array([0]),conf=np.array([.7]),xyxy=np.array([[0,20,100,120]]),
                            xyxyxyxy=np.array([[[0,20],[100,20],[100,120],[0,120]]]))
    results = [SimpleNamespace(obb=[plane],boxes=None)]
    ds = detector._process_yolo_results(results,AnalysisSettings(),320,0,(640,640),(1080,1920))
    assert ds[0]["class"] == "aircraft"
    assert ds[0]["bbox"] == [320,20,420,120]
    assert ds[0]["polygon"][0] == [320,20]
    assert ds[0]["edge_truncated"]
    outer = detector._process_yolo_results(results,AnalysisSettings(),0,0,(640,640),(1080,1920))
    assert not outer[0]["edge_truncated"]
