"""YOLO inference and confidence-ordered suppression in image coordinates."""
from pathlib import Path
from threading import Lock
import cv2
import numpy as np
from config import AnalysisSettings, MODELS_DIR, MODEL_PROFILES


def compute_iou(box1, box2):
    x1, y1 = max(box1[0], box2[0]), max(box1[1], box2[1])
    x2, y2 = min(box1[2], box2[2]), min(box1[3], box2[3])
    intersection = max(0, x2-x1) * max(0, y2-y1)
    area1 = max(0, box1[2]-box1[0]) * max(0, box1[3]-box1[1])
    area2 = max(0, box2[2]-box2[0]) * max(0, box2[3]-box2[1])
    union = area1+area2-intersection
    return intersection/union if union > 0 else 0.0


def overlap_metrics(first, second):
    """Use oriented geometry when available; return IoU and smaller-box coverage."""
    if first.get("polygon") and second.get("polygon"):
        a = cv2.convexHull(np.asarray(first["polygon"], dtype=np.float32))
        b = cv2.convexHull(np.asarray(second["polygon"], dtype=np.float32))
        area_a, area_b = cv2.contourArea(a), cv2.contourArea(b)
        intersection, _ = cv2.intersectConvexConvex(a, b)
    else:
        a, b = first["bbox"], second["bbox"]
        area_a = max(0,a[2]-a[0])*max(0,a[3]-a[1])
        area_b = max(0,b[2]-b[0])*max(0,b[3]-b[1])
        intersection = max(0,min(a[2],b[2])-max(a[0],b[0]))*max(0,min(a[3],b[3])-max(a[1],b[1]))
    intersection = max(0, min(intersection, area_a, area_b))
    union, smaller = area_a+area_b-intersection, min(area_a,area_b)
    return intersection/union if union else 0.0, intersection/smaller if smaller else 0.0


def same_aircraft(first, second, iou_threshold):
    if first["class"] != second["class"]:
        return False
    iou, coverage = overlap_metrics(first, second)
    if iou > iou_threshold:
        return True
    # A crop may contain only a wing/tail. IoU stays low despite almost complete
    # containment. Apply containment only to a known internal tile-edge fragment.
    if coverage >= 0.80 and (first.get("edge_truncated") or second.get("edge_truncated")):
        return True
    return False


def remove_duplicate_detections(detections, iou_threshold=0.35):
    filtered = []
    # Complete boxes take precedence over confidently detected crop fragments.
    ordered = sorted(detections, key=lambda d: (bool(d.get("edge_truncated")), -d["confidence"]))
    for detection in ordered:
        if not any(same_aircraft(detection, kept, iou_threshold) for kept in filtered):
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
    def __init__(self, enable_vehicle_detection=False, verbose=False, model=None, model_profile="aerial"):
        self.verbose = verbose
        self.enable_vehicle_detection = enable_vehicle_detection
        self._lock = Lock()
        if model_profile not in MODEL_PROFILES:
            raise ValueError("Unknown detector profile.")
        self.model_profile = model_profile
        self.model_info = MODEL_PROFILES[model_profile]
        if model is None:
            from ultralytics import YOLO
            MODELS_DIR.mkdir(parents=True, exist_ok=True)
            model = YOLO(str(MODELS_DIR / self.model_info["weights"]))
        self.model = model

    def _process_yolo_results(self, results, settings, x_offset=0, y_offset=0,
                              tile_shape=None, image_shape=None):
        detections = []
        for result in results:
            oriented = getattr(result, "obb", None)
            boxes = oriented if oriented is not None else result.boxes
            for box in boxes:
                name = self.model.names[int(box.cls[0])]
                confidence = float(box.conf[0])
                target = None
                if name in ("airplane", "plane") and confidence >= settings.aircraft_confidence:
                    target = "aircraft"
                elif (settings.enable_vehicle_detection and name in ("car", "truck", "bus", "small-vehicle", "large-vehicle")
                      and confidence >= settings.vehicle_confidence):
                    target = "vehicle"
                if target:
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    detection = {"class": target, "confidence": confidence,
                                 "bbox": [x1+x_offset, y1+y_offset, x2+x_offset, y2+y_offset],
                                 "source": "tile" if tile_shape else "full", "edge_truncated": False}
                    if oriented is not None:
                        detection["polygon"] = [[float(x)+x_offset,float(y)+y_offset]
                                                for x,y in box.xyxyxyxy[0].tolist()]
                    if tile_shape and image_shape:
                        th, tw = tile_shape
                        ih, iw = image_shape
                        margin = 8
                        detection["edge_truncated"] = bool(
                            (x_offset > 0 and x1 < margin) or (y_offset > 0 and y1 < margin) or
                            (x_offset+tw < iw and x2 > tw-margin) or
                            (y_offset+th < ih and y2 > th-margin))
                        detection["tile_bounds"] = [x_offset,y_offset,x_offset+tw,y_offset+th]
                    detections.append(detection)
        return detections

    def predict(self, image_path, settings=None, progress=None):
        settings = settings or AnalysisSettings(model_profile=self.model_profile,
                                                enable_vehicle_detection=self.enable_vehicle_detection)
        if settings.model_profile != self.model_profile:
            raise ValueError("Settings and loaded detector profiles differ. Load the requested model first.")
        image = read_image(image_path)
        height, width = image.shape[:2]
        windows = []
        if settings.tiled and (width > settings.tile_size or height > settings.tile_size):
            windows = [(x, y) for y in tile_origins(height, settings.tile_size, settings.tile_stride)
                       for x in tile_origins(width, settings.tile_size, settings.tile_stride)]
        total, all_detections = len(windows)+1, []
        class_ids = [i for i, name in self.model.names.items()
                     if name in ("airplane", "plane") or (settings.enable_vehicle_detection and
                        name in ("car", "truck", "bus", "small-vehicle", "large-vehicle"))]
        if not class_ids:
            raise ValueError("The selected model has no supported aircraft or vehicle classes.")
        confidence = min(settings.aircraft_confidence, settings.vehicle_confidence) if settings.enable_vehicle_detection else settings.aircraft_confidence
        # Ultralytics predictors are mutable; serialize shared model access.
        with self._lock:
            for index, (x, y) in enumerate(windows):
                if progress:
                    progress(index/total, f"Scanning tile {index+1} of {len(windows)}")
                tile = image[y:y+settings.tile_size, x:x+settings.tile_size]
                results = self.model.predict(tile,
                                             conf=confidence, imgsz=settings.inference_size,
                                             classes=class_ids, verbose=self.verbose)
                all_detections.extend(self._process_yolo_results(results, settings, x, y,
                                                               tile.shape[:2], image.shape[:2]))
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
                "model": self.model_info["label"], "dataset": self.model_info["dataset"],
                "detections": detections, "inference_passes": total,
                "raw_detection_count": len(all_detections),
                "duplicates_removed": len(all_detections)-len(detections)}
