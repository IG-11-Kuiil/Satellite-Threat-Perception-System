"""Shared analysis, visualization, and report generation for CLI and UI."""
import json
from datetime import datetime, timezone
from pathlib import Path
import cv2
from activity import compute_activity_level, generate_summary
from change_detection import compare_scenes, generate_change_summary
from config import AnalysisSettings, LOW_CONFIDENCE_THRESHOLD
from detector import read_image
from spatial import analyze_spatial


def analyze_image(detector, image_path, settings=None, progress=None, filename=None):
    settings = settings or AnalysisSettings()
    result = detector.predict(image_path, settings=settings, progress=progress)
    detections = result["detections"]
    aircraft_count = sum(d["class"] == "aircraft" for d in detections)
    vehicle_count = sum(d["class"] == "vehicle" for d in detections)
    spatial = analyze_spatial(detections, result["width"], result["height"], settings.cluster_distance_fraction)
    low_count = sum(d["class"] == "aircraft" and d["confidence"] < LOW_CONFIDENCE_THRESHOLD for d in detections)
    activity = compute_activity_level(aircraft_count, vehicle_count)
    warnings = ["General-purpose COCO model; overhead aircraft may be missed or misclassified."]
    if low_count:
        warnings.append(f"{low_count} aircraft detection(s) have confidence below 40%.")
    if not aircraft_count:
        warnings.append("No aircraft detected. This does not confirm aircraft are absent.")
    if settings.enable_vehicle_detection:
        warnings.append("Vehicle detection is experimental and unreliable for small overhead vehicles.")
    else:
        warnings.append("Vehicle detection is disabled; vehicle count is not an observation of absence.")
    return {**result, "filename": filename or Path(image_path).name,
            "aircraft_count": aircraft_count, "vehicle_count": vehicle_count,
            "vehicles_enabled": settings.enable_vehicle_detection,
            "clusters": spatial["pairs"], "spatial": spatial, "activity_level": activity,
            "low_confidence_count": low_count,
            "mean_confidence": round(sum(d["confidence"] for d in detections)/len(detections), 4) if detections else None,
            "warnings": warnings,
            "summary": generate_summary(aircraft_count, vehicle_count, activity, spatial["pairs"],
                                        bool(low_count), spatial, settings.enable_vehicle_detection)}


def save_annotation(analysis, output_path):
    image = read_image(analysis["image_path"])
    thickness = max(1, round(max(analysis["width"], analysis["height"])/700))
    font_scale = max(0.4, min(1.1, max(analysis["width"], analysis["height"])/1500))
    for detection in analysis["detections"]:
        x1, y1, x2, y2 = map(round, detection["bbox"])
        color = (190, 225, 90) if detection["class"] == "aircraft" else (90, 185, 255)
        if detection["confidence"] < LOW_CONFIDENCE_THRESHOLD:
            color = (65, 175, 255)
        label = f"{detection['id']} {detection['confidence']:.0%}"
        cv2.rectangle(image, (x1, y1), (x2, y2), color, thickness)
        (tw, th), baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, font_scale, 1)
        tx = max(0, min(x1, analysis["width"]-tw-8))
        ty = max(th+7, y1-5)
        cv2.rectangle(image, (tx, ty-th-5), (tx+tw+7, ty+baseline+2), (20, 27, 24), -1)
        cv2.putText(image, label, (tx+3, ty), cv2.FONT_HERSHEY_SIMPLEX, font_scale, color, 1, cv2.LINE_AA)
    ok, buffer = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 94])
    if not ok:
        raise OSError("Could not encode the annotated image.")
    Path(output_path).write_bytes(buffer.tobytes())


def build_report(result):
    lines = ["SATELLITE THREAT PERCEPTION SYSTEM", "IMAGERY ANALYSIS REPORT", "",
             f"Run: {result['id']}", f"Created: {result['created_at']}",
             f"Mode: {result['mode']}", "Model: YOLOv8s / COCO", ""]
    for label, scene in result["scenes"].items():
        lines += [f"{label.upper()} SCENE", f"File: {scene['filename']}",
                  f"Dimensions: {scene['width']} x {scene['height']} px",
                  f"Aircraft: {scene['aircraft_count']}",
                  f"Vehicles: {scene['vehicle_count'] if scene['vehicles_enabled'] else 'not analyzed'}",
                  f"Aircraft proximity groups: {scene['spatial']['group_count']}",
                  f"Isolated aircraft: {scene['spatial']['isolated_count']}",
                  f"Nearby pairs: {len(scene['clusters'])}", f"Activity: {scene['activity_level']}",
                  f"Low-confidence aircraft: {scene['low_confidence_count']}", scene["summary"], ""]
        for detection in scene["detections"]:
            lines.append(f"  {detection['id']} | {detection['class']} | {detection['confidence']:.1%} | bbox {detection['bbox']}")
        lines += ["", "Scene caveats:"]+[f"- {warning}" for warning in scene["warnings"]]+[""]
    if result.get("change"):
        lines += ["CHANGE ASSESSMENT", result["change_summary"],
                  f"Trend score: {result['change']['trend_score']}",
                  f"Proximity density change: {result['change']['density_difference']:+.1%}", ""]
        lines += [f"- {warning}" for warning in result["change"]["warnings"]]+[""]
    lines += ["SETTINGS", json.dumps(result["settings"], indent=2), "", "RULES",
              "Activity: detected aircraft + enabled vehicles; LOW 0-2, MEDIUM 3-6, HIGH 7+.",
              "Trend: 2*aircraft_delta + vehicle_delta + 2*activity_rank_delta + 2*proximity_density_delta.",
              "Trend thresholds: >=2 Increased, <=-2 Decreased, otherwise Stable.",
              "Review priority: High for >=2 aircraft or >=4 vehicles changed (absolute).",
              "Medium for 1 aircraft, any vehicles, or >=25 percentage points of density change; otherwise Low.",
              "Proximity: connected aircraft groups using a fraction of image diagonal, not geographic distance.",
              "", "LIMITATIONS", "Counts do not establish military intent, movement, or threat.",
              "No image registration, geospatial normalization, or cross-image identity matching.",
              "Human verification is required; confidence scores are not calibrated probabilities."]
    return "\n".join(lines)


def execute_analysis(detector, inputs, run_dir, run_id, settings=None, progress=None, created_at=None):
    settings = settings or AnalysisSettings()
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    scenes = {}
    for index, (label, item) in enumerate(inputs.items()):
        def scene_progress(fraction, message):
            if progress:
                progress(0.1+0.8*(index+fraction)/len(inputs), f"{label.title()}: {message}")
        scene = analyze_image(detector, item["path"], settings, scene_progress, item.get("filename"))
        save_annotation(scene, run_dir / f"{label}_annotated.jpg")
        scene["original_url"] = f"/api/jobs/{run_id}/files/{label}.png"
        scene["annotated_url"] = f"/api/jobs/{run_id}/files/{label}_annotated.jpg"
        # Internal filesystem paths are not needed in the downloadable result.
        scene.pop("image_path")
        scenes[label] = scene
    result = {"id": run_id, "created_at": created_at or datetime.now(timezone.utc).isoformat(),
              "mode": "comparison" if len(inputs) == 2 else "single", "model": "YOLOv8s / COCO",
              "settings": settings.to_dict(), "scenes": scenes, "change": None}
    if len(inputs) == 2:
        result["change"] = compare_scenes(scenes["before"], scenes["after"])
        result["change_summary"] = generate_change_summary(result["change"])
    result["report_url"] = f"/api/jobs/{run_id}/files/report.txt"
    result["json_url"] = f"/api/jobs/{run_id}/files/result.json"
    if progress:
        progress(0.95, "Writing report and annotations")
    (run_dir / "report.txt").write_text(build_report(result), encoding="utf-8")
    (run_dir / "result.json").write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
    return result
