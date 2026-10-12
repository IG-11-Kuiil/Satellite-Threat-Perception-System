import asyncio
import json
import uuid
from io import BytesIO
from PIL import Image
import pytest
from fastapi import HTTPException, UploadFile
import app as server


def upload(content, name="image.png"):
    return UploadFile(filename=name,file=BytesIO(content))


def test_exif_orientation_is_applied_and_metadata_removed():
    buffer = BytesIO()
    image = Image.new("RGB",(80,40))
    exif = image.getexif()
    exif[274] = 6
    image.save(buffer,"JPEG",exif=exif)
    normalized,name = asyncio.run(server.validate_upload(upload(buffer.getvalue(),"../folder/test\n.jpg")))
    assert name == "test.jpg"
    with Image.open(BytesIO(normalized)) as output:
        assert output.size == (40,80)
        assert not output.getexif()


def test_multipage_tiff_rejected():
    buffer = BytesIO()
    image = Image.new("RGB",(100,100))
    image.save(buffer,"TIFF",save_all=True,append_images=[image])
    with pytest.raises(HTTPException) as exc:
        asyncio.run(server.validate_upload(upload(buffer.getvalue(),"image.tiff")))
    assert exc.value.status_code == 415


def test_interrupted_run_recovered_as_failed(tmp_path,monkeypatch):
    monkeypatch.setattr(server,"RUNS_DIR",tmp_path)
    job_id = str(uuid.uuid4())
    folder = tmp_path/job_id
    folder.mkdir()
    job = {"id":job_id,"status":"running","progress":.5,"created_at":"2026-10-11T00:00:00Z","mode":"single","filenames":["test.png"]}
    (folder/"job.json").write_text(json.dumps(job))
    recovered = server.get_job(job_id)
    assert recovered["status"] == "failed"
    assert "restarted" in recovered["error"]
    assert server.recent_jobs()[0]["status"] == "failed"


def test_queue_rechecked_after_upload(tmp_path,monkeypatch):
    monkeypatch.setattr(server,"RUNS_DIR",tmp_path)
    server.jobs.clear()
    async def simulated_upload(upload):
        for i in range(4):
            server.jobs[str(i)] = {"status":"queued"}
        return b"test", "test.png"
    monkeypatch.setattr(server,"validate_upload",simulated_upload)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(server.submit(mode="single",image=upload(b"test"),after=None,
                                  confidence=.18,tiled=True,vehicles=False,proximity=.08,resolution=640,model_profile="aerial",verify_weak=True))
    assert exc.value.status_code == 429
    assert not list(tmp_path.iterdir())
    server.jobs.clear()


def test_status_save_retries_windows_file_locks(tmp_path,monkeypatch):
    from pathlib import Path
    monkeypatch.setattr(server,"RUNS_DIR",tmp_path)
    monkeypatch.setattr(server.time,"sleep",lambda seconds:None)
    original = Path.replace
    attempts = []
    def intermittently_locked(path,target):
        attempts.append(1)
        if len(attempts) < 3:
            raise PermissionError("Simulated OneDrive lock")
        return original(path,target)
    monkeypatch.setattr(Path,"replace",intermittently_locked)
    job_id = str(uuid.uuid4())
    (tmp_path/job_id).mkdir()
    server.persist_job({"id":job_id,"status":"completed"})
    assert len(attempts) == 3
    assert json.loads((tmp_path/job_id/"job.json").read_text())["status"] == "completed"


def test_progress_does_not_write_status_and_save_failure_does_not_abort(tmp_path,monkeypatch):
    job_id = str(uuid.uuid4())
    server.jobs[job_id] = {"id":job_id,"status":"running","progress":0}
    writes = []
    def fail_persistence(job):
        writes.append(job["status"])
        raise PermissionError("Locked by sync")
    monkeypatch.setattr(server,"persist_job",fail_persistence)
    server.update_job(job_id,progress=.5,message="Scanning")
    assert writes == []
    server.update_job(job_id,status="completed",progress=1)
    assert writes == ["completed"]
    assert server.jobs[job_id]["status"] == "completed"
    server.jobs.pop(job_id)
