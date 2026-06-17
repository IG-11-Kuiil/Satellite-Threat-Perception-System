from pathlib import Path
import cv2
import textwrap
from src.reasoning.spatial import analyze_clustering
from config import SAMPLE_IMAGES_DIR, OUTPUTS_DIR
from src.detection.detector import SatelliteDetector
from src.reasoning.activity import compute_activity_level, generate_summary


def count_classes(detections):
    aircraft_count = sum(1 for d in detections if d["class"] == "aircraft")
    vehicle_count = sum(1 for d in detections if d["class"] == "vehicle")
    return aircraft_count, vehicle_count


def draw_final_detections(image_path, detections):
    image = cv2.imread(str(image_path))

    for det in detections:
        x1, y1, x2, y2 = map(int, det["bbox"])
        label = f'{det["class"]} {det["confidence"]:.2f}'

        cv2.rectangle(image, (x1, y1), (x2, y2), (255, 0, 0), 3)
        cv2.putText(
            image,
            label,
            (x1, max(y1 - 10, 20)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (255, 0, 0),
            2,
            cv2.LINE_AA
        )

    return image


def main():
    detector = SatelliteDetector()

    image_path = SAMPLE_IMAGES_DIR / "example.png"
    result = detector.predict(str(image_path))

    detections = result["detections"]
    clusters = analyze_clustering(detections)

    has_low_confidence_detection = any(
        d["class"] == "aircraft" and d["confidence"] < 0.4
        for d in detections
    )
    aircraft_count, vehicle_count = count_classes(detections)

    activity_level = compute_activity_level(aircraft_count, vehicle_count)
    summary = generate_summary(
        aircraft_count,
        vehicle_count,
        activity_level,
        clusters,
        has_low_confidence_detection
    )

    print("Detections:")
    for d in detections:
        print(d)
    print("\nClusters:", clusters)
    print("\nCounts:")
    print("Aircraft:", aircraft_count)
    print("Vehicles:", vehicle_count)

    print("\nActivity Level:", activity_level)
    print("\nSummary:")
    print(textwrap.fill(summary, width=80))

    final_image = draw_final_detections(image_path, detections)

    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUTS_DIR / "prediction_example_final.jpg"

    cv2.imwrite(str(output_path), final_image)
    print("\nSaved final filtered prediction image to:", output_path)


if __name__ == "__main__":
    main()