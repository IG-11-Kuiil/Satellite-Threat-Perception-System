import pytest
from activity import compute_activity_level, generate_summary
from change_detection import compare_activity_levels, compare_scenes
from config import AnalysisSettings
from detector import compute_iou, remove_duplicate_detections, tile_origins
from spatial import analyze_spatial


def detection(x, y=0, confidence=.8, kind="aircraft"):
    return {"class": kind, "confidence": confidence, "bbox": [x, y, x+10, y+10]}


def scene(count, pairs, low=0, width=1000, height=1000):
    return {"aircraft_count": count, "vehicle_count": 0, "clusters": [(0, 1)]*pairs,
            "activity_level": compute_activity_level(count, 0), "low_confidence_count": low,
            "width": width, "height": height}


@pytest.mark.parametrize("count,expected", [(0,"LOW"),(2,"LOW"),(3,"MEDIUM"),(6,"MEDIUM"),(7,"HIGH")])
def test_activity_boundaries(count, expected):
    assert compute_activity_level(count, 0) == expected


def test_invalid_activity_rejected():
    with pytest.raises(ValueError):
        compute_activity_level(-1, 0)
    with pytest.raises(ValueError):
        compare_activity_levels("UNKNOWN", "HIGH")


@pytest.mark.parametrize("kwargs", [{"aircraft_confidence":0}, {"tile_stride":641}, {"cluster_distance_fraction":0}, {"inference_size":800}])
def test_invalid_settings_rejected(kwargs):
    with pytest.raises(ValueError):
        AnalysisSettings(**kwargs)


def test_proximity_components_and_actual_isolation():
    detections = [detection(0), detection(20), detection(40), detection(900), detection(800,kind="vehicle")]
    spatial = analyze_spatial(detections, 1000, 1000)
    assert spatial["groups"] == [[0,1,2]]
    assert spatial["isolated_indices"] == [3]
    assert spatial["pair_density"] == .5


def test_all_clustered_summary_has_no_isolation_claim():
    spatial = analyze_spatial([detection(x) for x in [0,20,40]],1000,1000)
    summary = generate_summary(3,0,"MEDIUM",spatial["pairs"],spatial=spatial)
    assert "no nearby" not in summary
    assert "isolated" not in summary
    assert spatial["isolated_count"] == 0


def test_proximity_invariant_to_image_resize():
    detections = [detection(0),detection(80),detection(800)]
    scaled = [{**d,"bbox":[x*2 for x in d["bbox"]]} for d in detections]
    assert analyze_spatial(detections,1000,1000)["pairs"] == analyze_spatial(scaled,2000,2000)["pairs"]


def test_no_detection_does_not_claim_absence():
    assert "does not establish" in generate_summary(0,0,"LOW",[])


def test_symmetric_priority_and_trend():
    before, after = scene(5,10), scene(13,69)
    forward, reverse = compare_scenes(before,after), compare_scenes(after,before)
    assert forward["priority"] == reverse["priority"] == "High"
    assert forward["activity_trend"] == "Increased"
    assert reverse["activity_trend"] == "Decreased"
    assert forward["trend_score"] == -reverse["trend_score"]


def test_raw_pairs_do_not_dominate_count_decline():
    result = compare_scenes(scene(15,0),scene(13,78))
    assert result["activity_trend"] == "Decreased"
    assert result["trend_score"] == -2


def test_confidence_and_extent_caveats_propagate():
    result = compare_scenes(scene(3,1,low=1),scene(3,1,width=2000))
    assert any("Low-confidence" in w for w in result["warnings"])
    assert any("aspect ratios" in w for w in result["warnings"])


def test_unchanged_scene_is_low_priority():
    result = compare_scenes(scene(3,1),scene(3,1))
    assert result["activity_trend"] == "Stable"
    assert result["priority"] == "Low"


def test_iou_and_class_aware_suppression():
    assert compute_iou([0,0,0,0],[0,0,0,0]) == 0
    assert compute_iou([0,0,10,10],[0,0,10,10]) == 1
    assert compute_iou([0,0,10,10],[20,0,30,10]) == 0
    kept = remove_duplicate_detections([detection(0,confidence=.2),detection(0,confidence=.9),detection(0,kind="vehicle")])
    assert len(kept) == 2
    assert kept[0]["confidence"] == .9


@pytest.mark.parametrize("length", [100,640,641,1000,4096])
def test_tiles_cover_edges_without_tiny_crops(length):
    origins = tile_origins(length,640,320)
    assert origins[0] == 0
    assert origins[-1]+640 >= length
    assert len(set(origins)) == len(origins)
    assert all(b-a <= 320 for a,b in zip(origins,origins[1:]))
