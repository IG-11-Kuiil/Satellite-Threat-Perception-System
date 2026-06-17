import cv2
import textwrap

from config import SAMPLE_IMAGES_DIR, OUTPUTS_DIR
from src.detection.detector import SatelliteDetector
from src.reasoning.activity import compute_activity_level, generate_summary
from src.reasoning.spatial import analyze_clustering
from src.reasoning.change_detection import compare_scenes, generate_change_summary


def count_classes(detections):
    aircraft_count = sum(1 for d in detections if d["class"] == "aircraft")
    vehicle_count = sum(1 for d in detections if d["class"] == "vehicle")
    return aircraft_count, vehicle_count


def draw_final_detections(image_path, detections, title):
    image = cv2.imread(str(image_path))

    if image is None:
        raise FileNotFoundError(f"Could not read image: {image_path}")

    detections = sorted(
        detections,
        key=lambda det: (det["bbox"][0], det["bbox"][1])
    )

    colors = {
        "aircraft": (255, 0, 0),
        "vehicle": (0, 255, 0),
    }

    cv2.putText(
        image,
        title,
        (20, image.shape[0] - 25),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.0,
        (0, 0, 255),
        3,
        cv2.LINE_AA,
    )

    for index, det in enumerate(detections):
        x1, y1, x2, y2 = map(int, det["bbox"])
        label = f'{det["class"][0].upper()}{index + 1}'
        color = colors.get(det["class"], (255, 255, 255))

        cv2.rectangle(image, (x1, y1), (x2, y2), color, 3)

        cv2.putText(
            image,
            label,
            (x1, max(y1 - 6, 18)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            color,
            2,
            cv2.LINE_AA,
        )

    return image


def analyze_image(detector, image_path):
    result = detector.predict(str(image_path))
    detections = result["detections"]

    aircraft_detections = [
        d for d in detections
        if d["class"] == "aircraft"
    ]

    clusters = analyze_clustering(aircraft_detections)

    aircraft_count, vehicle_count = count_classes(detections)

    has_low_confidence_detection = any(
        d["class"] == "aircraft" and d["confidence"] < 0.4
        for d in detections
    )

    activity_level = compute_activity_level(aircraft_count, vehicle_count)

    summary = generate_summary(
        aircraft_count,
        vehicle_count,
        activity_level,
        clusters,
        has_low_confidence_detection,
    )

    return {
        "image_path": str(image_path),
        "detections": detections,
        "aircraft_count": aircraft_count,
        "vehicle_count": vehicle_count,
        "clusters": clusters,
        "activity_level": activity_level,
        "summary": summary,
    }


def print_image_report(label, analysis):
    print(f"\n===== {label.upper()} IMAGE ANALYSIS =====")

    print("\nDetections:")
    for detection in analysis["detections"]:
        print(detection)

    print("\nCounts:")
    print("Aircraft:", analysis["aircraft_count"])
    print("Vehicles:", analysis["vehicle_count"])

    print("\nClusters:", analysis["clusters"])
    print("Activity Level:", analysis["activity_level"])

    print("\nSummary:")
    print(textwrap.fill(analysis["summary"], width=80))


def save_visualization(label, analysis):
    final_image = draw_final_detections(
        analysis["image_path"],
        analysis["detections"],
        title=f"{label.upper()} IMAGE",
    )

    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

    output_path = OUTPUTS_DIR / f"prediction_{label.lower()}_final.jpg"
    cv2.imwrite(str(output_path), final_image)

    print(f"\nSaved {label.lower()} visualization to:", output_path)

def format_signed(value):
    if value > 0:
        return f"+{value}"
    return str(value)


def save_change_report(previous_analysis, current_analysis, change_result, change_summary):
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

    report_path = OUTPUTS_DIR / "change_report.txt"

    aircraft_change = change_result["aircraft_change"]
    vehicle_change = change_result["vehicle_change"]
    cluster_change = change_result["cluster_change"]
    activity_change = change_result["activity_change"]

    report = f"""
SATELLITE CHANGE DETECTION REPORT

Before image: {previous_analysis["image_path"]}
After image: {current_analysis["image_path"]}

BEFORE IMAGE ANALYSIS
Aircraft detected: {previous_analysis["aircraft_count"]}
Vehicles detected: {previous_analysis["vehicle_count"]}
Aircraft cluster pairs: {len(previous_analysis["clusters"])}
Activity level: {previous_analysis["activity_level"]}

Before summary:
{previous_analysis["summary"]}

AFTER IMAGE ANALYSIS
Aircraft detected: {current_analysis["aircraft_count"]}
Vehicles detected: {current_analysis["vehicle_count"]}
Aircraft cluster pairs: {len(current_analysis["clusters"])}
Activity level: {current_analysis["activity_level"]}

After summary:
{current_analysis["summary"]}

CHANGE ASSESSMENT
Aircraft change: {format_signed(aircraft_change["difference"])}
Vehicle change: {format_signed(vehicle_change["difference"])}
Cluster change: {format_signed(cluster_change["difference"])}
Activity level change: {activity_change["previous_level"]} -> {activity_change["current_level"]}
Activity trend: {change_result["activity_trend"]}
Review priority: {change_result["priority"]}

Analyst-style change summary:
{change_summary}

LIMITATIONS
This assessment is based on model detections only. The detector may miss small,
low-contrast, partially obscured, or unusual aircraft due to domain mismatch
between general YOLO/COCO training data and overhead military satellite imagery.

Vehicle detection is currently disabled because the base model is unreliable for
small overhead vehicles. A future version should use a satellite or aerial
imagery-specific vehicle detection model.

Human analyst review is required before drawing operational conclusions.
""".strip()

    with open(report_path, "w", encoding="utf-8") as file:
        file.write(report)

    print("\nSaved change detection report to:", report_path)

def main():
    detector = SatelliteDetector()

    previous_image_path = SAMPLE_IMAGES_DIR / "before.png"
    current_image_path = SAMPLE_IMAGES_DIR / "after.png"

    if not previous_image_path.exists():
        raise FileNotFoundError(
            f"Missing previous image: {previous_image_path}. "
            "Add before.png to data/sample_images."
        )

    if not current_image_path.exists():
        raise FileNotFoundError(
            f"Missing current image: {current_image_path}. "
            "Add after.png to data/sample_images."
        )

    previous_analysis = analyze_image(detector, previous_image_path)
    current_analysis = analyze_image(detector, current_image_path)

    print_image_report("Before", previous_analysis)
    print_image_report("After", current_analysis)

    change_result = compare_scenes(previous_analysis, current_analysis)
    change_summary = generate_change_summary(change_result)

    print("\n===== CHANGE DETECTION RESULT =====")
    print("\nAircraft Change:", change_result["aircraft_change"]["difference"])
    print("Vehicle Change:", change_result["vehicle_change"]["difference"])
    print("Cluster Change:", change_result["cluster_change"]["difference"])
    print("Activity Change:", change_result["activity_change"]["trend"])
    print("Activity Trend:", change_result["activity_trend"])
    print("Priority:", change_result["priority"])

    print("\nChange Summary:")
    print(textwrap.fill(change_summary, width=80))
    save_change_report(
        previous_analysis,
        current_analysis,
        change_result,
        change_summary,
    )

    save_visualization("before", previous_analysis)
    save_visualization("after", current_analysis)


if __name__ == "__main__":
    main()