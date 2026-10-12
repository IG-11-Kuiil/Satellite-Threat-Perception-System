"""Shared paths and validated analysis settings."""
from dataclasses import asdict, dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SAMPLE_IMAGES_DIR = ROOT / "data" / "sample_images"
MODELS_DIR = ROOT / "models"
OUTPUTS_DIR = ROOT / "outputs"
RUNS_DIR = OUTPUTS_DIR / "runs"
STATIC_DIR = ROOT / "web"
TARGET_CLASSES = ("aircraft", "vehicle")
LOW_ACTIVITY_MAX = 2
MEDIUM_ACTIVITY_MAX = 6
MAX_UPLOAD_BYTES = 20 * 1024 * 1024
MAX_IMAGE_PIXELS = 16_000_000
MAX_IMAGE_SIDE = 4096
LOW_CONFIDENCE_THRESHOLD = 0.40
MODEL_PROFILES = {
    "aerial": {"weights": "yolo11s-obb.pt", "label": "YOLO11s-OBB / DOTA v1", "dataset": "DOTA v1"},
    "aerial_large": {"weights": "yolo26m-obb.pt", "label": "YOLO26m-OBB / DOTA v1", "dataset": "DOTA v1"},
    "general": {"weights": "yolov8s.pt", "label": "YOLOv8s / COCO", "dataset": "COCO"},
}


@dataclass(frozen=True)
class AnalysisSettings:
    model_profile: str = "aerial"
    aircraft_confidence: float = 0.40
    vehicle_confidence: float = 0.30
    iou_threshold: float = 0.35
    tile_size: int = 640
    tile_stride: int = 320
    inference_size: int = 1024
    tiled: bool = True
    enable_vehicle_detection: bool = False
    cluster_distance_fraction: float = 0.08

    def __post_init__(self):
        if self.model_profile not in MODEL_PROFILES:
            raise ValueError("Unknown detector profile.")
        for name in ("aircraft_confidence", "vehicle_confidence", "iou_threshold"):
            if not 0.05 <= getattr(self, name) <= 0.95:
                raise ValueError(f"{name} must be between 0.05 and 0.95.")
        if not 0.01 <= self.cluster_distance_fraction <= 0.5:
            raise ValueError("Proximity distance must be between 1% and 50% of the image diagonal.")
        if not 128 <= self.tile_size <= 1280 or not 1 <= self.tile_stride <= self.tile_size:
            raise ValueError("Tile size must be 128-1280 and stride must not exceed tile size.")
        if self.inference_size not in (640, 1024, 1280):
            raise ValueError("Inference size must be 640, 1024, or 1280.")

    def to_dict(self):
        return asdict(self)
