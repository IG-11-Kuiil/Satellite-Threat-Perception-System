"""YOLO inference and confidence-ordered suppression in image coordinates."""
from pathlib import Path
from dataclasses import replace
from threading import Lock
import cv2
import numpy as np
import logging
from config import AnalysisSettings, MODELS_DIR, MODEL_PROFILES
logger = logging.getLogger(__name__)


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


def detection_polygon(detection):
    if detection.get("polygon"):
        return cv2.convexHull(np.asarray(detection["polygon"],dtype=np.float32)).reshape(-1,2)
    x1,y1,x2,y2 = detection["bbox"]
    return np.asarray([[x1,y1],[x2,y1],[x2,y2],[x1,y2]],dtype=np.float32)


def visible_tile_match(fragment, complete, iou_threshold):
    """Compare predictions in the fragment's observed field of view, not unseen pixels."""
    bounds = fragment.get("tile_bounds")
    if not fragment.get("edge_truncated") or not bounds or complete.get("edge_truncated"):
        return False
    x1,y1,x2,y2 = bounds
    roi = np.asarray([[x1,y1],[x2,y1],[x2,y2],[x1,y2]],dtype=np.float32)
    complete_polygon = detection_polygon(complete)
    full_area = cv2.contourArea(complete_polygon)
    visible_area, visible_complete = cv2.intersectConvexConvex(complete_polygon,roi)
    # The complete prediction must actually cross this crop boundary.
    if full_area <= 0 or visible_area <= 0 or visible_area >= full_area*0.98:
        return False
    fragment_area, visible_fragment = cv2.intersectConvexConvex(detection_polygon(fragment),roi)
    if fragment_area <= 0:
        return False
    intersection,_ = cv2.intersectConvexConvex(visible_complete,visible_fragment)
    union = visible_area+fragment_area-intersection
    return union > 0 and intersection/union > iou_threshold


def same_aircraft(first, second, iou_threshold):
    if first["class"] != second["class"]:
        return False
    iou, coverage = overlap_metrics(first, second)
    if iou > iou_threshold:
        return True
    if visible_tile_match(first,second,iou_threshold) or visible_tile_match(second,first,iou_threshold):
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


def corroborate_candidates(primary, supporting, settings, supporting_label):
    """Retain subthreshold aircraft only with a second model's overlapping evidence."""
    accepted = remove_duplicate_detections([
        d for d in primary if d["class"] != "aircraft" or d["confidence"] >= settings.aircraft_confidence
    ],settings.iou_threshold)
    weak = remove_duplicate_detections([
        d for d in primary if d["class"] == "aircraft" and d["confidence"] < settings.aircraft_confidence
    ],settings.iou_threshold)
    rescued = []
    for candidate in weak:
        if any(same_aircraft(candidate,d,settings.iou_threshold) for d in accepted):
            continue
        matches = [d for d in supporting if d["class"] == candidate["class"] and
                   d["confidence"] >= settings.aircraft_confidence and
                   overlap_metrics(candidate,d)[0] > settings.iou_threshold]
        if matches:
            best = max(matches,key=lambda d:d["confidence"])
            rescued.append({**candidate,"accepted_by":"cross_model_review","review_required":True,
                            "supporting_model":supporting_label,"supporting_confidence":best["confidence"]})
    return remove_duplicate_detections(accepted+rescued,settings.iou_threshold)


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
        self._verification_model = None
        if model is None:
            from ultralytics import YOLO
            MODELS_DIR.mkdir(parents=True, exist_ok=True)
            model = YOLO(str(MODELS_DIR / self.model_info["weights"]))
        self.model = model

    def _verify_candidates(self,image,windows,settings,progress):
        if progress:
            progress(.6,"Loading secondary aerial model to check weak candidates")
        if self._verification_model is None:
            from ultralytics import YOLO
            self._verification_model = YOLO(str(MODELS_DIR/MODEL_PROFILES["aerial_large"]["weights"]))
        verifier = self._verification_model
        verifier_ids = [i for i,name in verifier.names.items() if name in ("plane","airplane")]
        detections = []
        # Use the same inference plan: agreement is spatial evidence, not a count target.
        for index,(x,y) in enumerate(windows+[(0,0)]):
            full_pass = index == len(windows)
            source = image if full_pass else image[y:y+settings.tile_size,x:x+settings.tile_size]
            if progress:
                progress(.6+.4*index/(len(windows)+1),f"Verifying candidates: pass {index+1} of {len(windows)+1}")
            results = verifier.predict(source,conf=settings.aircraft_confidence,imgsz=settings.inference_size,
                                       classes=verifier_ids,verbose=self.verbose)
            detections.extend(self._process_yolo_results(results,settings,x,y,
                              None if full_pass else source.shape[:2],image.shape[:2],verifier))
        return detections,len(windows)+1

    def _process_yolo_results(self, results, settings, x_offset=0, y_offset=0,
                              tile_shape=None, image_shape=None, model=None):
        detections = []
        for result in results:
            oriented = getattr(result, "obb", None)
            boxes = oriented if oriented is not None else result.boxes
            for box in boxes:
                name = (model or self.model).names[int(box.cls[0])]
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
                                 "source": "tile" if tile_shape else "full", "edge_truncated": False,
                                 "accepted_by":"primary"}
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
        verification_enabled = settings.verify_weak_detections and self.model_profile == "aerial"
        candidate_settings = replace(settings,aircraft_confidence=min(0.10,settings.aircraft_confidence)) if verification_enabled else settings
        class_ids = [i for i, name in self.model.names.items()
                     if name in ("airplane", "plane") or (settings.enable_vehicle_detection and
                        name in ("car", "truck", "bus", "small-vehicle", "large-vehicle"))]
        if not class_ids:
            raise ValueError("The selected model has no supported aircraft or vehicle classes.")
        confidence = min(candidate_settings.aircraft_confidence, settings.vehicle_confidence) if settings.enable_vehicle_detection else candidate_settings.aircraft_confidence
        supporting_label = None
        supporting_detections = []
        verification_passes = 0
        verification_warning = None
        # Ultralytics predictors are mutable; serialize shared model access.
        with self._lock:
            for index, (x, y) in enumerate(windows):
                if progress:
                    progress(0.6*index/total if verification_enabled else index/total, f"Scanning tile {index+1} of {len(windows)}")
                tile = image[y:y+settings.tile_size, x:x+settings.tile_size]
                results = self.model.predict(tile,
                                             conf=confidence, imgsz=settings.inference_size,
                                             classes=class_ids, verbose=self.verbose)
                all_detections.extend(self._process_yolo_results(results, candidate_settings, x, y,
                                                               tile.shape[:2], image.shape[:2]))
            if progress:
                progress(0.6*len(windows)/total if verification_enabled else len(windows)/total, "Scanning full image")
            results = self.model.predict(image, conf=confidence, imgsz=settings.inference_size,
                                         classes=class_ids, verbose=self.verbose)
            all_detections.extend(self._process_yolo_results(results, candidate_settings))
            strong = remove_duplicate_detections([d for d in all_detections if d["class"] != "aircraft" or
                                                  d["confidence"] >= settings.aircraft_confidence],settings.iou_threshold)
            weak = [d for d in remove_duplicate_detections(all_detections,settings.iou_threshold)
                    if d["class"] == "aircraft" and d["confidence"] < settings.aircraft_confidence and
                    not any(same_aircraft(d,kept,settings.iou_threshold) for kept in strong)]
            if verification_enabled and weak:
                try:
                    supporting_detections,verification_passes = self._verify_candidates(image,windows,settings,progress)
                    supporting_label = MODEL_PROFILES["aerial_large"]["label"]
                except Exception:
                    logger.warning("Secondary verification unavailable; preserving primary detections",exc_info=True)
                    verification_warning = "Secondary model verification was unavailable. Primary detections are shown; weak candidates were not added."
        detections = corroborate_candidates(all_detections,supporting_detections,settings,supporting_label)
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
            d["review_required"] = bool(d.get("review_required") or d.get("edge_truncated") or d["confidence"] < 0.4)
        if progress:
            progress(1.0, "Detection complete")
        return {"image_path": str(image_path), "width": width, "height": height,
                "model": self.model_info["label"], "dataset": self.model_info["dataset"],
                "detections": detections, "inference_passes": total+verification_passes,
                "verification_model":supporting_label,
                "verification_warning":verification_warning,
                "raw_detection_count": len(all_detections),
                "duplicates_removed": len(all_detections)-len(remove_duplicate_detections(all_detections,settings.iou_threshold)),
                "candidates_filtered":len(all_detections)-len(detections)}
