from pathlib import Path

ROOT = Path(__file__).resolve().parent

DATA_DIR = ROOT / "data"
SAMPLE_IMAGES_DIR = DATA_DIR / "sample_images"

MODELS_DIR = ROOT / "models"
OUTPUTS_DIR = ROOT / "outputs"

TARGET_CLASSES = ["aircraft", "vehicle"]

LOW_ACTIVITY_MAX = 2
MEDIUM_ACTIVITY_MAX = 6