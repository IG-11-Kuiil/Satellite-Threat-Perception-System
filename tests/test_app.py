import json
import time
from io import BytesIO
from types import SimpleNamespace
import numpy as np
import pytest
from PIL import Image
from fastapi.testclient import TestClient
import app as server
from config import AnalysisSettings
from detector import SatelliteDetector


class FakeDetector:
    def predict(self, path, settings=None, progress=None):
        if progress:
            progress(.5, "Test inference")
        with Image.open(path) as image:
            width,height = image.size
        return {"image_path":str(path),"width":width,"height":height,"inference_passes":1,
                "detections":[{"id":"A01","class":"aircraft","confidence":.3,"bbox":[10,10,30,30]}]}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(server,"RUNS_DIR",tmp_path)
    monkeypatch.setattr(server,"get_detector",lambda:FakeDetector())
    server.jobs.clear()
    with TestClient(server.app) as client:
        yield client


def image_bytes(size=(100,100),fmt="PNG"):
    buffer = BytesIO()
    Image.new("RGB",size,"#4a5146").save(buffer,fmt)
    return buffer.getvalue()


def wait_result(client, job_id):
    for _ in range(100):
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] in ("completed","failed"):
            return job
        time.sleep(.02)
    pytest.fail("Background analysis did not finish.")


@pytest.mark.parametrize("mode", ["single","comparison"])
def test_complete_upload_report_and_annotation(client,mode):
    files = {"image":("<script>.png",image_bytes(),"image/png")}
    if mode == "comparison":
        files["after"] = ("after.png",image_bytes(),"image/png")
    response = client.post("/api/analyze",data={"mode":mode},files=files)
    assert response.status_code == 202
    job = wait_result(client,response.json()["id"])
    assert job["status"] == "completed",job
    result = job["result"]
    assert result["mode"] == mode
    assert len(result["scenes"]) == (1 if mode == "single" else 2)
    for scene in result["scenes"].values():
        assert scene["low_confidence_count"] == 1
        assert "image_path" not in scene
        annotation = client.get(scene["annotated_url"])
        assert annotation.status_code == 200
        with Image.open(BytesIO(annotation.content)) as image:
            assert image.size == (100,100)
    report = client.get(result["report_url"])
    assert report.status_code == 200
    assert "Human verification" in report.text
    assert "not analyzed" in report.text
    assert client.get(result["json_url"]).json()["id"] == result["id"]
    assert client.get("/api/jobs").json()[0]["status"] == "completed"
    # Completed runs survive a new in-memory session.
    server.jobs.clear()
    assert client.get(f"/api/jobs/{job['id']}").json()["status"] == "completed"


def test_bad_mode_missing_pair_and_settings(client):
    files = {"image":("image.png",image_bytes(),"image/png")}
    assert client.post("/api/analyze",data={"mode":"unknown"},files=files).status_code == 400
    assert client.post("/api/analyze",data={"mode":"comparison"},files=files).status_code == 400
    assert client.post("/api/analyze",data={"mode":"single","confidence":2},files=files).status_code == 400


@pytest.mark.parametrize("content,expected", [(b"",400),(b"not an image",415),(image_bytes((10,10)),400),(image_bytes((4097,32)),413)])
def test_bad_images_rejected(client,content,expected):
    response = client.post("/api/analyze",data={"mode":"single"},files={"image":("bad.png",content,"image/png")})
    assert response.status_code == expected
    assert not list(server.RUNS_DIR.iterdir())


def test_size_limit_and_multi_frame(client,monkeypatch):
    monkeypatch.setattr(server,"MAX_UPLOAD_BYTES",10)
    assert client.post("/api/analyze",data={"mode":"single"},files={"image":("big.png",b"x"*11)}).status_code == 413


def test_failed_job_is_visible(client,monkeypatch):
    def fail():
        raise RuntimeError("Test model loading failed")
    monkeypatch.setattr(server,"get_detector",fail)
    response = client.post("/api/analyze",data={"mode":"single"},files={"image":("image.png",image_bytes())})
    job = wait_result(client,response.json()["id"])
    assert job["status"] == "failed"
    assert job["error"] == "Test model loading failed"


def test_artifacts_cannot_escape_run_directory(client):
    assert client.get("/api/jobs/not-a-uuid").status_code == 404
    assert client.get("/api/jobs/00000000-0000-0000-0000-000000000000/files/job.json").status_code == 404
    assert client.get("/").status_code == 200
    assert client.get("/api/health").json()["status"] == "ok"


def test_yolo_class_filtering_and_tile_offsets(tmp_path):
    calls = []
    class FakeModel:
        names = {0:"airplane",1:"car",2:"person"}
        def predict(self,image,**kwargs):
            calls.append(kwargs)
            boxes = [SimpleNamespace(cls=np.array([0]),conf=np.array([.7]),xyxy=np.array([[5,5,20,20]])),
                     SimpleNamespace(cls=np.array([1]),conf=np.array([.8]),xyxy=np.array([[25,25,40,40]]))]
            return [SimpleNamespace(boxes=boxes)]
    path = tmp_path / "image.png"
    Image.new("RGB",(1000,100)).save(path)
    detector = SatelliteDetector(model=FakeModel())
    result = detector.predict(path,AnalysisSettings())
    assert result["inference_passes"] == 4
    assert all(d["class"] == "aircraft" for d in result["detections"])
    assert any(d["bbox"][0] == 365 for d in result["detections"])
    assert all(call["classes"] == [0] for call in calls)
    vehicles = detector.predict(path,AnalysisSettings(tiled=False,enable_vehicle_detection=True))
    assert {d["class"] for d in vehicles["detections"]} == {"aircraft","vehicle"}
