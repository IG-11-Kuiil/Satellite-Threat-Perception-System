"""Local FastAPI UI with a serialized background inference queue."""
import json
import logging
import threading
import time
import uuid
import warnings
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from PIL import Image, ImageOps, UnidentifiedImageError
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from config import (AnalysisSettings, MAX_IMAGE_PIXELS, MAX_IMAGE_SIDE, MAX_UPLOAD_BYTES,
                    MODELS_DIR, RUNS_DIR, STATIC_DIR, MODEL_PROFILES)
from pipeline import execute_analysis

logger = logging.getLogger(__name__)
app = FastAPI(title="Athena Imagery Operations", version="2.0.0")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="imagery")
jobs = {}
jobs_lock = threading.Lock()
detector = None


def get_detector(model_profile="aerial"):
    global detector
    if detector is None or detector.model_profile != model_profile:
        from detector import SatelliteDetector
        detector = SatelliteDetector(model_profile=model_profile)
    return detector


def checked_run_dir(job_id):
    try:
        parsed = uuid.UUID(job_id)
        if str(parsed) != job_id:
            raise ValueError()
    except ValueError:
        raise HTTPException(404, "Analysis not found.")
    return RUNS_DIR / job_id


def persist_job(job):
    folder = checked_run_dir(job["id"])
    temp = folder / "job.tmp"
    content = json.dumps(job, allow_nan=False)
    # Windows sync/antivirus tools can briefly hold either file after a write.
    for attempt in range(7):
        try:
            temp.write_text(content, encoding="utf-8")
            temp.replace(folder / "job.json")
            return
        except PermissionError:
            if attempt == 6:
                raise
            time.sleep(0.05 * 2**attempt)


def update_job(job_id, **changes):
    with jobs_lock:
        jobs[job_id].update(changes)
        # Live tile progress stays in memory. Persist lifecycle transitions only.
        if "status" in changes:
            try:
                persist_job(jobs[job_id])
            except OSError:
                logger.warning("Could not persist job status; result artifacts are saved separately", exc_info=True)


def work(job_id, inputs, settings):
    try:
        update_job(job_id, status="running", progress=0.02,
                   message="Loading aircraft detector; first use may download model weights")
        model = get_detector(settings.model_profile)
        result = execute_analysis(model, inputs, checked_run_dir(job_id), job_id, settings,
                                  lambda fraction, message: update_job(job_id, progress=round(fraction, 3), message=message),
                                  created_at=jobs[job_id]["created_at"])
        update_job(job_id, status="completed", progress=1.0, message="Analysis complete", result=result)
    except Exception as exc:
        logger.exception("Analysis %s failed", job_id)
        update_job(job_id, status="failed", message="Analysis failed", error=str(exc) or type(exc).__name__)


async def validate_upload(upload):
    content = await upload.read(MAX_UPLOAD_BYTES+1)
    await upload.close()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "Each image must be 20 MB or smaller.")
    if not content:
        raise HTTPException(400, "The uploaded image is empty.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(content)) as source:
                if source.format not in {"PNG", "JPEG", "WEBP", "TIFF"}:
                    raise HTTPException(415, "Use PNG, JPEG, WebP, or TIFF imagery.")
                width, height = source.size
                if width < 32 or height < 32:
                    raise HTTPException(400, "Images must be at least 32 pixels on each side.")
                if width*height > MAX_IMAGE_PIXELS or max(width, height) > MAX_IMAGE_SIDE:
                    raise HTTPException(413, "Use an image no larger than 4096 pixels per side and 16 megapixels.")
                if getattr(source, "n_frames", 1) > 1:
                    raise HTTPException(415, "Upload a single-frame image, not animated or multi-page imagery.")
                image = ImageOps.exif_transpose(source).convert("RGB")
                normalized = BytesIO()
                image.save(normalized, "PNG")
                # Strip uploaded paths and control characters from report labels.
                name = (upload.filename or "image").replace("\\", "/").split("/")[-1]
                name = "".join(c for c in name if c.isprintable())[:160] or "image"
                return normalized.getvalue(), name
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise HTTPException(415, "The file could not be decoded as a supported image.")


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def health():
    return {"status": "ok", "model": MODEL_PROFILES["aerial"]["label"], "model_loaded": detector is not None,
            "weights_cached": (MODELS_DIR / MODEL_PROFILES["aerial"]["weights"]).exists(),
            "model_profiles": {key:{**info,"cached":(MODELS_DIR/info["weights"]).exists(),
                                       "loaded":detector is not None and detector.model_profile == key}
                               for key,info in MODEL_PROFILES.items()}, "max_upload_mb": 20}


@app.post("/api/analyze", status_code=202)
async def submit(mode: str = Form(...), image: UploadFile = File(...),
                 after: UploadFile | None = File(None), confidence: float = Form(0.40),
                 tiled: bool = Form(True), vehicles: bool = Form(False),
                 proximity: float = Form(0.08), resolution: int = Form(1024),
                 model_profile: str = Form("aerial"), verify_weak: bool = Form(True)):
    if mode not in ("single", "comparison"):
        raise HTTPException(400, "Choose single or comparison mode.")
    if mode == "comparison" and after is None:
        raise HTTPException(400, "Both before and after images are required.")
    if mode == "single" and after is not None:
        raise HTTPException(400, "Single-image analysis accepts one image.")
    try:
        settings = AnalysisSettings(model_profile=model_profile, aircraft_confidence=confidence, tiled=tiled,
                                    enable_vehicle_detection=vehicles,
                                    verify_weak_detections=verify_weak,
                                    cluster_distance_fraction=proximity, inference_size=resolution)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    with jobs_lock:
        if sum(job["status"] in ("queued", "running") for job in jobs.values()) >= 4:
            raise HTTPException(429, "The analysis queue is full. Wait for an existing run to finish.")
    original, filename = await validate_upload(image)
    normalized = {"before" if mode == "comparison" else "scene": (original, filename)}
    if after is not None:
        normalized["after"] = await validate_upload(after)
    job_id = str(uuid.uuid4())
    folder = checked_run_dir(job_id)
    job = {"id": job_id, "created_at": datetime.now(timezone.utc).isoformat(), "mode": mode,
           "status": "queued", "progress": 0, "message": "Queued for analysis",
           "filenames": [item[1] for item in normalized.values()]}
    with jobs_lock:
        # Recheck after awaited uploads; simultaneous submissions can fill the queue.
        if sum(item["status"] in ("queued", "running") for item in jobs.values()) >= 4:
            raise HTTPException(429, "The analysis queue is full. Wait for an existing run to finish.")
        folder.mkdir(parents=True)
        inputs = {}
        for label, (content, name) in normalized.items():
            path = folder / f"{label}.png"
            path.write_bytes(content)
            inputs[label] = {"path": path, "filename": name}
        jobs[job_id] = job
        persist_job(job)
    executor.submit(work, job_id, inputs, settings)
    return {"id": job_id, "status": "queued"}


@app.get("/api/jobs")
def recent_jobs():
    paths = sorted(RUNS_DIR.glob("*/job.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:12]
    result = []
    for path in paths:
        try:
            job = get_job(path.parent.name)
            result.append({k: job[k] for k in ("id", "mode", "status", "created_at", "filenames")})
        except (OSError, ValueError, KeyError, HTTPException):
            continue
    return result


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    folder = checked_run_dir(job_id)
    with jobs_lock:
        if job_id in jobs:
            # Serialize while holding the lock so inference updates cannot race a response.
            return json.loads(json.dumps(jobs[job_id]))
        try:
            job = json.loads((folder / "job.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raise HTTPException(404, "Analysis not found.")
        if job["status"] in ("queued", "running"):
            job.update(status="failed", error="The server restarted before this run finished. Submit the images again.")
            persist_job(job)
        return job


@app.get("/api/jobs/{job_id}/files/{filename}")
def artifact(job_id: str, filename: str):
    allowed = {"scene.png", "before.png", "after.png", "scene_annotated.jpg",
               "before_annotated.jpg", "after_annotated.jpg", "report.txt", "result.json"}
    if filename not in allowed:
        raise HTTPException(404, "Artifact not found.")
    path = checked_run_dir(job_id) / filename
    if not path.is_file():
        raise HTTPException(404, "Artifact not found.")
    download = filename in ("report.txt", "result.json")
    return FileResponse(path, filename=f"athena_{job_id[:8]}_{filename}" if download else None)
