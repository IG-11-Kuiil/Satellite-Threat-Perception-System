from pathlib import Path
import cv2
from ultralytics import YOLO


def compute_iou(box1, box2):
    x1 = max(box1[0], box2[0])
    y1 = max(box1[1], box2[1])
    x2 = min(box1[2], box2[2])
    y2 = min(box1[3], box2[3])

    inter_width = max(0, x2 - x1)
    inter_height = max(0, y2 - y1)
    intersection = inter_width * inter_height

    area1 = max(0, box1[2] - box1[0]) * max(0, box1[3] - box1[1])
    area2 = max(0, box2[2] - box2[0]) * max(0, box2[3] - box2[1])

    union = area1 + area2 - intersection
    if union == 0:
        return 0.0

    return intersection / union


def remove_duplicate_detections(detections, iou_threshold=0.4):
    detections = sorted(detections, key=lambda d: d["confidence"], reverse=True)
    filtered = []

    for det in detections:
        keep = True
        for kept in filtered:
            if det["class"] == kept["class"]:
                iou = compute_iou(det["bbox"], kept["bbox"])
                if iou > iou_threshold:
                    keep = False
                    break

        if keep:
            filtered.append(det)

    return filtered


class SatelliteDetector:
    def __init__(self, enable_vehicle_detection=False, verbose=False):
        self.model = YOLO("yolov8s.pt")

        self.aircraft_conf_threshold = 0.18
        self.vehicle_conf_threshold = 0.30

        self.enable_vehicle_detection = enable_vehicle_detection
        self.verbose = verbose

    def _process_yolo_results(self, results, x_offset=0, y_offset=0):
        detections = []

        for box in results[0].boxes:
            cls_id = int(box.cls[0])
            conf = float(box.conf[0])
            bbox = box.xyxy[0].tolist()

            class_name = self.model.names[cls_id]
            if self.verbose:
                print("Raw YOLO class:", class_name, "| confidence:", round(conf, 3))

            # shift box back into full-image coordinates
            bbox = [
                bbox[0] + x_offset,
                bbox[1] + y_offset,
                bbox[2] + x_offset,
                bbox[3] + y_offset,
            ]

            if class_name == "airplane" and conf >= self.aircraft_conf_threshold:
                detections.append({
                    "class": "aircraft",
                    "confidence": conf,
                    "bbox": bbox
                })


            elif (
                    self.enable_vehicle_detection
                    and class_name in ["car", "truck", "bus"]
                    and conf >= self.vehicle_conf_threshold
            ):
                detections.append({
                    "class": "vehicle",
                    "confidence": conf,
                    "bbox": bbox
                })
            # Vehicle detection is intentionally disabled for now because the COCO model
            # is unreliable for small overhead vehicles in satellite imagery.
            # This will be replaced later with a satellite/aerial vehicle model.

        return detections

    def predict(self, image_path: str):
        image_path = Path(image_path)
        image = cv2.imread(str(image_path))

        if image is None:
            raise FileNotFoundError(f"Could not read image: {image_path}")

        height, width = image.shape[:2]

        tile_size = 640
        stride = 320

        all_detections = []

        print("\nRunning sliding-window tiled detection")

        for y in range(0, height, stride):
            for x in range(0, width, stride):
                x2 = min(x + tile_size, width)
                y2 = min(y + tile_size, height)

                tile_img = image[y:y2, x:x2]

                if tile_img.shape[0] < 100 or tile_img.shape[1] < 100:
                    continue

                print(f"Running detection on tile x={x}, y={y}, w={x2 - x}, h={y2 - y}")

                results = self.model(tile_img, conf=0.10, imgsz=1280)
                tile_detections = self._process_yolo_results(
                    results,
                    x_offset=x,
                    y_offset=y,
                )
                all_detections.extend(tile_detections)

        print("\nRunning detection on full image")
        full_results = self.model(str(image_path), conf=0.10, imgsz=1280)
        full_detections = self._process_yolo_results(
            full_results,
            x_offset=0,
            y_offset=0,
        )
        all_detections.extend(full_detections)

        final_detections = remove_duplicate_detections(
            all_detections,
            iou_threshold=0.35,
        )

        return {
            "image_path": str(image_path),
            "detections": final_detections,
        }
