"""YOLO inference and confidence-ordered suppression in image coordinates."""
from pathlib import Path
from threading import Lock
import cv2
import numpy as np
from config import AnalysisSettings, MODELS_DIR


def compute_iou(box1, box2):
    x1, y1 = max(box1[0], box2[0]), max(box1[1], box2[1])
    x2, y2 = min(box1[2], box2[2]), min(box1[3], box2[3])
    intersection = max(0, x2-x1) * max(0, y2-y1)
    area1 = max(0, box1[2]-box1[0]) * max(0, box1[3]-box1[1])
    area2 = max(0, box2[2]-box2[0]) * max(0, box2[3]-box2[1])
    union = area1+area2-intersection
    return intersection/union if union > 0 else 0.0


def remove_duplicate_detections(detections, iou_threshold=0.35):
    filtered = []
    for detection in sorted(detections, key=lambda d: d["confidence"], reverse=True):
        if not any(detection["class"] == kept["class"] and
                   compute_iou(detection["bbox"], kept["bbox"]) > iou_threshold
                   for kept in filtered):
            filtered.append(detection)
    return filtered


def tile_origins(length, tile_size, stride):
    """Cover edges without tiny trailing crops or duplicate small-image passes."""
    if length <= tile_size:
        return [0]
    origins = list(range(0, length-tile_size+1, stride))
    if origins[-1] != length-tile_size:
        origins.append(length-tile_size)
    return origins


def read_image(image_path):
    try:
        image = cv2.imdecode(np.fromfile(str(image_path), dtype=np.uint8), cv2.IMREAD_COLOR)
    except (OSError, ValueError):
        image = None
    if image is None:
        raise ValueError(f"Could not read image: {Path(image_path).name}")
    return image


class SatelliteDetector:
    def __init__(self, enable_vehicle_detection=False, verbose=False, model=None):
        self.verbose = verbose
        self.enable_vehicle_detection = enable_vehicle_detection
        self._lock = Lock()
        if model is None:
            from ultralytics import YOLO
            MODELS_DIR.mkdir(parents=True, exist_ok=True)
            model = YOLO(str(MODELS_DIR / "yolov8s.pt"))
        self.model = model

    def _process_yolo_results(self, results, settings, x_offset=0, y_offset=0):
        detections = []
        for result in results:
            for box in result.boxes:
                name = self.model.names[int(box.cls[0])]
                confidence = float(box.conf[0])
                target = None
                if name == "airplane" and confidence >= settings.aircraft_confidence:
                    target = "aircraft"
                elif (settings.enable_vehicle_detection and name in ("car", "truck", "bus")
                      and confidence >= settings.vehicle_confidence):
                    target = "vehicle"
                if target:
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    detections.append({"class": target, "confidence": confidence,
                                       "bbox": [x1+x_offset, y1+y_offset, x2+x_offset, y2+y_offset]})
        return detections

    def predict(self, image_path, settings=None, progress=None):
        settings = settings or AnalysisSettings(enable_vehicle_detection=self.enable_vehicle_detection)
        image = read_image(image_path)
        height, width = image.shape[:2]
        windows = []
        if settings.tiled and (width > settings.tile_size or height > settings.tile_size):
            windows = [(x, y) for y in tile_origins(height, settings.tile_size, settings.tile_stride)
                       for x in tile_origins(width, settings.tile_size, settings.tile_stride)]
        total, all_detections = len(windows)+1, []
        class_ids = [i for i, name in self.model.names.items()
                     if name == "airplane" or (settings.enable_vehicle_detection and name in ("car", "truck", "bus"))]
        confidence = min(settings.aircraft_confidence, settings.vehicle_confidence) if settings.enable_vehicle_detection else settings.aircraft_confidence
        # Ultralytics predictors are mutable; serialize shared model access.
        with self._lock:
            for index, (x, y) in enumerate(windows):
                if progress:
                    progress(index/total, f"Scanning tile {index+1} of {len(windows)}")
                results = self.model.predict(image[y:y+settings.tile_size, x:x+settings.tile_size],
                                             conf=confidence, imgsz=settings.inference_size,
                                             classes=class_ids, verbose=self.verbose)
                all_detections.extend(self._process_yolo_results(results, settings, x, y))
            if progress:
                progress(len(windows)/total, "Scanning full image")
            results = self.model.predict(image, conf=confidence, imgsz=settings.inference_size,
                                         classes=class_ids, verbose=self.verbose)
            all_detections.extend(self._process_yolo_results(results, settings))
        detections = remove_duplicate_detections(all_detections, settings.iou_threshold)
        for d in detections:
            x1, y1, x2, y2 = d["bbox"]
            d["bbox"] = [max(0, min(width, x1)), max(0, min(height, y1)),
                         max(0, min(width, x2)), max(0, min(height, y2))]
        detections = [d for d in detections if d["bbox"][2] > d["bbox"][0] and d["bbox"][3] > d["bbox"][1]]
        detections.sort(key=lambda d: (d["class"], d["bbox"][0], d["bbox"][1]))
        counters = {}
        for d in detections:
            key = d["class"]
            counters[key] = counters.get(key, 0)+1
            d["id"] = f"{'A' if key == 'aircraft' else 'V'}{counters[key]:02d}"
        if progress:
            progress(1.0, "Detection complete")
        return {"image_path": str(image_path), "width": width, "height": height,
                "detections": detections, "inference_passes": total}
