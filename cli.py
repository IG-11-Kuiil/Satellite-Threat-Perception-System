"""Command-line entrypoints using the same pipeline as the web UI."""
import argparse
import json
import uuid
from pathlib import Path
from PIL import Image, ImageOps
from config import AnalysisSettings, MAX_IMAGE_PIXELS, MAX_IMAGE_SIDE, MAX_UPLOAD_BYTES, OUTPUTS_DIR, SAMPLE_IMAGES_DIR
from detector import SatelliteDetector
from pipeline import execute_analysis


def run(comparison=False):
    parser = argparse.ArgumentParser(description="Analyze overhead imagery with YOLOv8s and transparent activity rules.")
    if comparison:
        parser.add_argument("--before", type=Path, default=SAMPLE_IMAGES_DIR / "before.png")
        parser.add_argument("--after", type=Path, default=SAMPLE_IMAGES_DIR / "after.png")
    else:
        parser.add_argument("--image", type=Path, default=SAMPLE_IMAGES_DIR / "example.png")
    parser.add_argument("--confidence", type=float, default=0.18)
    parser.add_argument("--proximity", type=float, default=0.08, help="Fraction of image diagonal")
    parser.add_argument("--no-tiles", action="store_true", help="Run full-image inference only")
    parser.add_argument("--vehicles", action="store_true", help="Enable experimental vehicle detection")
    parser.add_argument("--resolution", type=int, choices=(640, 1280), default=640)
    parser.add_argument("--output-dir", type=Path, default=OUTPUTS_DIR / "runs")
    args = parser.parse_args()
    try:
        settings = AnalysisSettings(aircraft_confidence=args.confidence, cluster_distance_fraction=args.proximity,
                                    tiled=not args.no_tiles, enable_vehicle_detection=args.vehicles,
                                    inference_size=args.resolution)
        paths = {"before": args.before, "after": args.after} if comparison else {"scene": args.image}
        normalized = {}
        for label, path in paths.items():
            if not path.is_file():
                parser.error(f"Image not found: {path}. Supply an image path with --{label if comparison else 'image'}.")
            if path.stat().st_size > MAX_UPLOAD_BYTES:
                parser.error("Each image must be 20 MB or smaller.")
            with Image.open(path) as source:
                if source.format not in {"PNG", "JPEG", "WEBP", "TIFF"} or getattr(source, "n_frames", 1) > 1:
                    parser.error("Use a single-frame PNG, JPEG, WebP, or TIFF image.")
                width, height = source.size
                if min(width, height) < 32 or max(width, height) > MAX_IMAGE_SIDE or width*height > MAX_IMAGE_PIXELS:
                    parser.error("Images must be at least 32 px per side, at most 4096 px per side and 16 megapixels.")
                normalized[label] = ImageOps.exif_transpose(source).convert("RGB")
        run_id = str(uuid.uuid4())
        folder = args.output_dir / run_id
        folder.mkdir(parents=True)
        inputs = {}
        for label, image in normalized.items():
            path = folder / f"{label}.png"
            image.save(path)
            inputs[label] = {"path": path, "filename": paths[label].name}
        print("Loading YOLOv8s; pretrained weights download on first use.", flush=True)
        result = execute_analysis(SatelliteDetector(), inputs, folder, run_id, settings,
                                  lambda fraction, message: print(f"{fraction:.0%} {message}", flush=True))
        job = {"id": run_id, "mode": result["mode"], "created_at": result["created_at"],
               "status": "completed", "progress": 1, "message": "Analysis complete", "result": result,
               "filenames": [path.name for path in paths.values()]}
        (folder / "job.json").write_text(json.dumps(job, indent=2), encoding="utf-8")
        print(result.get("change_summary") or result["scenes"]["scene"]["summary"])
        print(f"\nReport and images saved to: {folder.resolve()}")
    except (ValueError, OSError, RuntimeError) as exc:
        parser.error(str(exc))
