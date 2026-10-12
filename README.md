# Satellite Threat Perception System

A local imagery analysis workspace for single-scene aircraft detection and before/after comparison. The interface combines a defence-style operations console with aerial-model inference, transparent spatial reasoning, rotated annotations, and downloadable reports.

## Start the interface

Requires Python 3.10 or later. From the project directory:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe run_ui.py
```

The app opens at **http://127.0.0.1:8000**. The included `start.ps1` also creates an environment and installs dependencies if needed:

```powershell
.\start.ps1
```

If your PowerShell policy prevents script execution, use the Python commands above. No policy change is necessary. On macOS/Linux, use `.venv/bin/python` in place of `.venv\Scripts\python.exe`.

To use another port or skip automatic browser opening:

```powershell
.\.venv\Scripts\python.exe run_ui.py --port 8001 --no-browser
```

Stop the server with Ctrl+C in its terminal. It binds only to the local computer. There is no public deployment or remote inference service.

The default detector is **YOLO11s-OBB pretrained on DOTA v1 aerial imagery**, replacing the general COCO detector. First use downloads `yolo11s-obb.pt` (about 19 MB) into `models/`. Later runs reuse weights and can work offline. CPU inference is supported; tiled scanning and 1280-pixel inference take longer for large images. The model loads only when an analysis starts. The interface also offers experimental YOLO26m-OBB and the legacy YOLOv8s/COCO model. Larger/newer models are not automatically more accurate on a given scene.

## Use the workspace

1. Select **Change detection** to upload baseline and later-observation images, or **Single image analysis** to upload one scene.
2. Drop an image into each required slot or browse for files. PNG, JPEG, WebP, and single-frame TIFF are supported. Each file must be at most 20 MB, at least 32 px per side, no more than 4096 px per side, and no more than 16 megapixels. TIFF previews may be unavailable in the browser; the server can still decode them. Uploads are validated from their contents and EXIF orientation is applied.
3. Choose a detector profile and aircraft confidence threshold (default 40%). Tiled scanning is enabled by default. Advanced parameters expose inference resolution (default 1024 px), proximity distance, and experimental vehicle detection. Low confidence thresholds increase false detections, including on text and watermarks.
4. Run analysis and follow the actual inference progress. A single worker serializes model access; up to four active/queued runs are accepted.
5. Review annotated images, switch to originals, expand imagery, inspect the asset table, and download the text report or structured JSON.
6. Reopen completed analyses from Recent analyses. Runs persist across server restarts; interrupted runs are marked failed and can be submitted again. Recent runs and method information are available on mobile as well.

Each run has a unique directory under `outputs/runs/<uuid>/`. It contains normalized source PNGs, annotated JPEGs, `report.txt`, `result.json`, and lifecycle metadata in `job.json`. New analyses do not overwrite earlier runs. Uploads and generated outputs are excluded from Git. Files remain in this workspace; a workspace located in a cloud-synced folder follows that folder's normal sync behavior.

## How analysis works

**Detection.** YOLO11s-OBB uses DOTA v1 weights restricted to aircraft by default. For larger images, inference runs on 640 px overlapping tiles with a 320 px stride and on the full scene. Edge tiles cover the boundary without tiny trailing crops. Inference resolution is configurable at 640, 1024, or 1280 px. DOTA `plane` and COCO `airplane` map to `aircraft`. Optional DOTA `small-vehicle`/`large-vehicle` and COCO `car`/`truck`/`bus` map to `vehicle`. DOTA models return rotated polygons; COCO returns rectangular boxes. All geometry uses original-image pixel coordinates with labels such as A01 or V01. The model used is recorded in each result and report, including historical runs.

**Duplicate removal.** Same-class boxes use polygon IoU when both have rotated geometry, otherwise rectangular IoU. IoU >0.35 removes duplicates. Tile-edge fragments can have low IoU even when they describe a small part of a complete aircraft, so candidates near an internal crop boundary also use overlap over the smaller box (at least 80%). Complete boxes take precedence over truncated boxes, then confidence determines priority. Containment alone does not merge ordinary nested detections. Unmatched edge candidates are retained and flagged for review. Reports record how many duplicate/invalid candidates were removed.

**Spatial reasoning.** Aircraft centers are linked when separated by less than a configurable fraction of the image diagonal (default 8%). Connected components of two or more aircraft are proximity groups. An isolated aircraft has no neighbors. Nearby pairs and distinct groups are reported separately. Proximity density is nearby pairs divided by all possible aircraft pairs; this avoids a raw pair count that grows quadratically dominating comparisons. Relative-image distances remain consistent when the same image is resized; they do not compensate for different ground coverage, crops, or geographic resolution.

**Activity.** Detected aircraft plus enabled vehicle detections determine observed asset presence: LOW for 0–2, MEDIUM for 3–6, HIGH for 7+. Activity does not establish movement or intent. Aircraft scores below 40% produce visible review flags and caveats. Disabled vehicles are reported as **not analyzed**, rather than interpreted as absent.

**Change.** The app compares aggregate scene counts, nearby-pair density, and activity rank (LOW=0, MEDIUM=1, HIGH=2):

```text
trend score = 2 × aircraft change + vehicle change
            + 2 × activity rank change + 2 × proximity density change

score >= 2   Increased
score <= -2  Decreased
otherwise    Stable
```

Review priority uses absolute change, so departures receive review priority too:

| Priority | Rule |
| --- | --- |
| High | At least 2 aircraft or 4 vehicles changed |
| Medium | 1 aircraft, any vehicles, or at least 25 percentage points of proximity density changed |
| Low | Otherwise |

Reports explain the rules and priority reasons. Both scene caveats and comparison caveats are visible. Low-confidence detections still contribute to counts; their caveats are propagated rather than silently discarded. Differing aspect ratios trigger a comparison warning. Even equal-size images require a human to verify comparable ground coverage and scale.

## Command-line workflows

Both CLI runners use the same pipeline and settings as the interface:

```powershell
.\.venv\Scripts\python.exe run_mvp.py --image "C:\imagery\scene.png"
.\.venv\Scripts\python.exe run_change_detection.py --before "C:\imagery\before.png" --after "C:\imagery\after.png"
```

Use `--help` for `--model aerial|aerial_large|general`, confidence, proximity, resolution, tiling, vehicles, and output-directory options. The original default paths still work if you supply `data/sample_images/example.png`, `before.png`, and `after.png`. No sample imagery is bundled. CLI runs in the default output directory also appear in UI history.

## Project structure

```text
app.py                  Local API, uploads, queue, status, history, artifacts
run_ui.py / start.ps1    Launchers
web/                    HTML, CSS, JavaScript, and SVG brand mark
config.py               Shared validated settings and paths
detector.py             YOLO inference, tiling, coordinate mapping, suppression
spatial.py              Proximity pairs, groups, isolation, density
activity.py             Activity classification and scene prose
change_detection.py     Temporal comparison, priorities, caveats
pipeline.py             Shared orchestration, annotations, JSON, reports
cli.py                  Argument parsing and normalized CLI inputs
run_mvp.py              Single-scene CLI entrypoint
run_change_detection.py Two-scene CLI entrypoint
tests/                  Reasoning, inference adapters, uploads, API, persistence
models/                 Downloaded weights (ignored)
outputs/                Local run artifacts (ignored)
```

The original broken `src.*` imports have been replaced with the actual flat module layout. Shared configuration and analysis functions replace duplicated runner logic. `PROJECT_UNDERSTANDING.md` preserves the historical review of the original version.

## Validation

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest
node --check web/app.js
```

Tests cover activity boundaries, group/isolation correctness, resizing behavior, duplicate suppression, tile coverage, class mapping and offsets, symmetric priorities, bounded spatial scoring, uncertainty propagation, upload validation, EXIF orientation, multi-page rejection, artifacts, background failures, queue limits, restart recovery, and transient Windows file locks. Geometry regressions also cover contained high-confidence tile fragments, nearby rotated aircraft, unmatched edge detections, and OBB class/polygon mapping. API tests use a deterministic fake detector and require no model download. See [the scene validation record](docs/DETECTION_VALIDATION.md) for actual model comparisons and the image that motivated the aerial-model upgrade.

Framework APIs follow the [FastAPI upload documentation](https://fastapi.tiangolo.com/tutorial/request-files/) and [Ultralytics prediction documentation](https://docs.ultralytics.com/modes/predict). Shared predictor access is serialized in accordance with [Ultralytics thread-safety guidance](https://docs.ultralytics.com/guides/yolo-thread-safe-inference).

## Limitations and next improvements

This remains a prototype. Aerial weights can still miss small or atypical aircraft and produce false positives. Watermarks, text, shadows, and visibility can affect results; experimental YOLO26m-OBB produced a watermark false positive in the scene comparison. Vehicle detection is experimental. The system detects generic aircraft, not aircraft types such as Su-57, ownership, military intent, or an actual threat. No detections does not prove no assets are present. Confidence scores are not calibrated probabilities.

The comparison is an aggregate detection comparison, not pixel-level change segmentation or cross-image asset tracking. There is no image registration, ground-distance normalization, geospatial metadata interpretation, or verification that two images show the same area. Priority is a transparent heuristic, not a validated operational score. Labeled aerial/satellite imagery is required to measure precision and recall and fine-tune a domain-specific model. No improved detection-accuracy claim is made without those measurements.

Human review of the original imagery and annotated boxes is required before conclusions are drawn.
