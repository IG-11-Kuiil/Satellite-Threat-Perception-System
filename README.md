# Athena - Satellite Threat Perception System

Athena is a **Satellite Threat Perception System**: a local imagery analysis workspace for single-scene aircraft detection and before/after comparison. The interface combines a defence-style operations console with aerial-model inference, transparent spatial reasoning, rotated annotations, and downloadable reports.

**Assessment scope:** LOW/MEDIUM/HIGH are demonstration asset-presence bands. Review priority is a prototype triage rule. Neither is a military threat rating, and formal analytic confidence is **not assessed**. See [assessment policy and published guidance](docs/ASSESSMENT_POLICY.md).

## Project at a glance

Project by **Shaurya Singh**. Athena explores how overhead imagery can become a reviewable record of detected assets and scene-to-scene differences, rather than only a set of boxes. Its current focus is aircraft counting and human review in a local workspace.

| Capability | What works today |
| --- | --- |
| Single-scene analysis | Aircraft detections, rotated overlays, nearby groups, and asset-presence summaries |
| Before/after comparison | Aggregate count changes, grouping changes, and review priority |
| Candidate review | A second model checks weak primary candidates; provisional detections remain visible |
| Saved evidence | Original and annotated views, per-object scores, run history, text reports, and JSON exports |
| Local operation | Inference runs on this computer after model downloads; no hosted inference service |

**Built around pretrained models:** Ultralytics supplies the detection models. Athena's application layer provides validated uploads, overlapping image scans, duplicate suppression, candidate review, spatial reasoning, auditable assessments, and the operations interface. No custom aircraft model training is claimed.

## Screenshots

### Full desktop workspace

[![Athena workspace with two analysis workflows, upload slots, detector controls, and run history](docs/images/athena-overview.png)](docs/images/athena-overview.png)

Choose single-image analysis or before/after comparison. Click any screenshot to view it at full resolution.

### Single-image aircraft detection

[![Athena single-image result showing four rotated aircraft detections in a fresh capture without the horizontal green artifact](docs/images/athena-single-analysis-clean.jpg)](docs/images/athena-single-analysis-clean.jpg)

This run shows **four aircraft detections**, rotated boxes, model scores, and a count-based MEDIUM presence band. Athena detects generic aircraft; it does not identify aircraft types or establish military intent.

### Before/after change detection

[![Athena comparison result showing nine aircraft before and twelve candidate-inclusive detections after, with one review candidate](docs/images/athena-change-detection.png)](docs/images/athena-change-detection.png)

This tested pair shows **9 aircraft before and 12 candidate-inclusive detections after**, including **one candidate requiring confirmation**. Primary-only counts are **9 to 11**; the known-candidate change range is **+2 to +3**. This is one debugging example, not a measured accuracy rate or proof of aircraft arrivals or departures.

The workspace and comparison screenshots were supplied by the project author; the single-image screenshot is a fresh capture of the same completed four-aircraft run. All show actual app output. Standalone input imagery is not bundled. Third-party imagery remains subject to its own terms; see [imagery source notes](THIRD_PARTY_NOTICES.md#imagery-inside-documentation-screenshots).

## Try the workflow

After starting the local interface:

1. Analyze one overhead image and inspect the boxes against the original. Review flags and model scores are shown alongside counts.
2. Upload comparable before/after scenes and run change detection. Inspect primary counts separately from review candidates.
3. Expand the imagery, inspect the asset table, and read the comparison caveats before interpreting the change.
4. Download the report or JSON, then reopen the saved analysis from Recent runs.

Use imagery you are permitted to process. No input images are bundled. For a short narrated product walkthrough, see the [demo recording outline](docs/DEMO_WALKTHROUGH.md).

## Design choices and evidence

- **Aerial models instead of a general detector:** rotated detections suit overhead aircraft at different angles.
- **Tile-aware duplicate removal:** overlapping scans help small objects, but edge fragments must not inflate counts.
- **Visible provisional candidates:** agreement between two models can support review without turning a weak score into certainty.
- **Versioned assessment rules:** presence and review priority are explainable prototype rules, not military threat judgments.

The recorded single-scene check found four aircraft with the default aerial profile. The supplied comparison produced the counts shown above; a reduced-size version still missed an aircraft. A small public reference check also exposed a false positive. These are debugging and validation examples, not a representative benchmark. See [single-scene validation](docs/DETECTION_VALIDATION.md), [comparison validation](docs/COMPARISON_VALIDATION.md), and the [assessment policy](docs/ASSESSMENT_POLICY.md) for details.

The automated suite currently has **64 tests** covering geometry, reasoning, uploads, API behavior, and persistence. The tests verify application behavior; they do not establish model accuracy. [GitHub Actions](https://github.com/IG-11-Kuiil/Satellite-Threat-Perception-System/actions/workflows/tests.yml) runs the checks on pushes and pull requests.

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

The default detector is **YOLO11s-OBB pretrained on DOTA v1 aerial imagery**, replacing the general COCO detector. First use downloads `yolo11s-obb.pt` (about 19 MB) into `models/`. Cross-model candidate review, enabled by default for this profile, lazily downloads YOLO26m-OBB (about 46 MB) if unmatched weak candidates need checking. Later runs reuse both weights and can work offline. If verification fails, primary detections are preserved with a warning. CPU inference is supported; verification, tiled scanning, and 1280-pixel inference take longer for large images. Models load only when needed. The interface also offers standalone experimental YOLO26m-OBB and the legacy YOLOv8s/COCO model. Larger/newer models are not automatically more accurate on a given scene.

## Use the workspace

1. Select **Change detection** to upload baseline and later-observation images, or **Single image analysis** to upload one scene.
2. Drop an image into each required slot or browse for files. PNG, JPEG, WebP, and single-frame TIFF are supported. Each file must be at most 20 MB, at least 32 px per side, no more than 4096 px per side, and no more than 16 megapixels. TIFF previews may be unavailable in the browser; the server can still decode them. Uploads are validated from their contents and EXIF orientation is applied.
3. Choose a detector profile and aircraft confidence threshold (default 40%). Tiled scanning is enabled by default. Advanced parameters expose inference resolution (default 1024 px), proximity distance, and experimental vehicle detection. Low confidence thresholds increase false detections, including on text and watermarks.
4. Run analysis and follow the actual inference progress. A single worker serializes model access; up to four active/queued runs are accepted.
5. Review annotated images, switch to originals, expand imagery, inspect the asset table, and download the text report or structured JSON.
6. Reopen completed analyses from the **Recent runs** sidebar list (or the Recent runs dropdown on mobile). Runs persist across server restarts; interrupted runs are marked failed and can be submitted again.

Each run has a unique directory under `outputs/runs/<uuid>/`. It contains normalized source PNGs, annotated JPEGs, `report.txt`, `result.json`, and lifecycle metadata in `job.json`. New analyses do not overwrite earlier runs. Uploads and generated outputs are excluded from Git. Files remain in this workspace; a workspace located in a cloud-synced folder follows that folder's normal sync behavior.

## How analysis works

**Detection.** YOLO11s-OBB uses DOTA v1 weights restricted to aircraft by default. For larger images, inference runs on 640 px overlapping tiles with a 320 px stride and on the full scene. Edge tiles cover the boundary without tiny trailing crops. Inference resolution is configurable at 640, 1024, or 1280 px. DOTA `plane` and COCO `airplane` map to `aircraft`. Optional DOTA `small-vehicle`/`large-vehicle` and COCO `car`/`truck`/`bus` map to `vehicle`. DOTA models return rotated polygons; COCO returns rectangular boxes. All geometry uses original-image pixel coordinates with labels such as A01 or V01. The model used is recorded in each result and report, including historical runs.

**Duplicate removal.** Same-class boxes use polygon IoU when both have rotated geometry, otherwise rectangular IoU. IoU >0.35 removes duplicates. Tile-edge fragments can have low IoU even when they describe a small part of a complete aircraft, so candidates near an internal crop boundary also use overlap over the smaller box (at least 80%). Complete boxes take precedence over truncated boxes, then confidence determines priority. Containment alone does not merge ordinary nested detections. Unmatched edge candidates are retained and flagged for review. Reports record how many duplicate/invalid candidates were removed.

For shifted edge fragments, the detector clips both predictions to the fragment's actual tile field of view and compares the visible geometry at the same IoU threshold. This rule applies only if the matching complete prediction crosses that tile boundary. It does not alter tile grids or thresholds to match an image's expected aircraft count.

**Cross-model review.** The default aerial profile collects primary candidates down to a fixed 10% search floor while keeping the selected confidence threshold for automatic acceptance. An unmatched weak candidate is retained only if a second aerial model scores an overlapping aircraft above the selected threshold and polygon IoU exceeds the same configured overlap threshold. A secondary-only detection is not added. Retained weak candidates keep their primary score, show the supporting model score, and remain flagged for human confirmation. They are included in the candidate-inclusive total; the report separately states primary counts and marks the exact change provisional. Disable this mode with the UI checkbox or `--no-verification` for strict primary-only thresholding. This is model agreement, not a calibrated likelihood or proof of an aircraft behind cloud.

**Spatial reasoning.** Aircraft centers are linked when separated by less than a configurable fraction of the image diagonal (default 8%). Connected components of two or more aircraft are proximity groups. An isolated aircraft has no neighbors. Nearby pairs and distinct groups are reported separately. Proximity density is nearby pairs divided by all possible aircraft pairs; this avoids a raw pair count that grows quadratically dominating comparisons. Relative-image distances remain consistent when the same image is resized; they do not compensate for different ground coverage, crops, or geographic resolution.

**Asset presence.** Detected aircraft plus enabled vehicle detections determine a prototype count band: LOW for 0–2, MEDIUM for 3–6, HIGH for 7+. These are local demonstration cutoffs, not military standards. Presence does not establish movement or intent. Aircraft scores below 40% produce visible review flags and caveats. Disabled vehicles are reported as **not analyzed**, rather than interpreted as absent.

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

Every new report includes the `prototype-presence-v1` policy snapshot: cutoffs, weights, non-operational status, and unassessed threat/analytic confidence. Candidate sensitivity shows how the count delta changes when known review candidates are included or excluded. For the validated 9-before/12-after pair, that range is +2 to +3. It is not a statistical confidence interval and does not account for aircraft missed by both models. Published [ODNI](https://www.dni.gov/files/documents/ICD/ICD-203.pdf) and [PHIA](https://www.gov.uk/government/publications/explaining-uncertainty-in-uk-intelligence-assessment/explaining-uncertainty-in-uk-intelligence-assessment) guidance informs these transparency choices; no compliance or military calibration is claimed.

## Command-line workflows

Both CLI runners use the same pipeline and settings as the interface:

```powershell
.\.venv\Scripts\python.exe run_mvp.py --image "C:\imagery\scene.png"
.\.venv\Scripts\python.exe run_change_detection.py --before "C:\imagery\before.png" --after "C:\imagery\after.png"
```

Use `--help` for `--model aerial|aerial_large|general`, confidence, proximity, resolution, tiling, `--no-verification`, vehicles, and output-directory options. The original default paths still work if you supply `data/sample_images/example.png`, `before.png`, and `after.png`. No sample imagery is bundled. CLI runs in the default output directory also appear in UI history.

## Project structure

```text
app.py                  Local API, uploads, queue, status, history, artifacts
run_ui.py / start.ps1    Launchers
web/                    HTML, CSS, JavaScript, and SVG brand mark
config.py               Shared validated settings and paths
assessment_policy.py    Versioned presence, trend, and review policy
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

GitHub Actions runs the unit/API suite and JavaScript syntax check on pushes and pull requests, using CPU-only PyTorch. Unit tests do not download model weights or upload imagery.

Tests cover activity boundaries, group/isolation correctness, resizing behavior, duplicate suppression, tile coverage, class mapping and offsets, symmetric priorities, bounded spatial scoring, uncertainty propagation, upload validation, EXIF orientation, multi-page rejection, artifacts, background failures, queue limits, restart recovery, and transient Windows file locks. Geometry regressions also cover contained high-confidence tile fragments, nearby rotated aircraft, unmatched edge detections, and OBB class/polygon mapping. API tests use a deterministic fake detector and require no model download. See [the scene validation record](docs/DETECTION_VALIDATION.md) for actual model comparisons and the image that motivated the aerial-model upgrade.

Crop-projection and corroboration regressions additionally cover translations, multiple scales, adjacent-aircraft rejection, uncorroborated candidates, unchanged confidence scores, unavailable verifier fallback, and provisional count changes. `tools/validate_references.py` can check an external YOLO-OBB dataset without changing detector settings. Public reference results and the before/after debugging record are documented in [comparison validation](docs/COMPARISON_VALIDATION.md).

Framework APIs follow the [FastAPI upload documentation](https://fastapi.tiangolo.com/tutorial/request-files/) and [Ultralytics prediction documentation](https://docs.ultralytics.com/modes/predict). Shared predictor access is serialized in accordance with [Ultralytics thread-safety guidance](https://docs.ultralytics.com/guides/yolo-thread-safe-inference).

## Limitations and next improvements

This remains a prototype. Aerial weights can still miss small or atypical aircraft and produce false positives. Watermarks, text, shadows, and visibility can affect results; experimental YOLO26m-OBB produced a watermark false positive in the scene comparison. Vehicle detection is experimental. The system detects generic aircraft, not aircraft types such as Su-57, ownership, military intent, or an actual threat. No detections does not prove no assets are present. Confidence scores are not calibrated probabilities.

The comparison is an aggregate detection comparison, not pixel-level change segmentation or cross-image asset tracking. There is no image registration, ground-distance normalization, geospatial metadata interpretation, or verification that two images show the same area. Priority is a transparent heuristic, not a validated operational score. Labeled aerial/satellite imagery is required to measure precision and recall and fine-tune a domain-specific model. No improved detection-accuracy claim is made without those measurements.

Human review of the original imagery and annotated boxes is required before conclusions are drawn.

## Copyright and licensing

Copyright (c) 2026 Shaurya Singh. The current integrated Athena application is released under **GNU Affero General Public License version 3 only (AGPL-3.0-only)**. See the complete [license](LICENSE), [copyright and license-history notice](NOTICE), and [third-party licensing notes](THIRD_PARTY_NOTICES.md).

You may use, modify, and redistribute the covered application, including commercially, under the AGPL terms. Preserve required notices and provide corresponding source when required. For a modified covered version used over a network, section 13 requires offering its corresponding source to remote users. The software is provided without warranty. This source release replaces the prospective rights-reserved notice; it is not a proprietary-use license.

**Earlier MIT permissions remain.** Original code published through commit `a792e613fa24bae22dea69469bcff280d8752e03` retains its separately granted MIT permissions. The unmodified [previous MIT text](docs/licenses/MIT-previous.txt) is preserved; the AGPL license for the integrated application does not retract those earlier grants.

Athena directly uses Ultralytics software and downloaded YOLO weights. Their upstream terms still apply. This release follows the open-source licensing route described by [Ultralytics](https://www.ultralytics.com/license); no Enterprise license has been purchased or included. A future proprietary integration requires suitable commercial permission or replacement of affected components, with a review of all dependency and asset terms.

The interface links to the license and public source repository. If you distribute binaries, containers, model bundles, or deploy a modified service, provide the corresponding source, notices, and any required installation materials for that exact version; a link to an unrelated or newer source revision is insufficient. Downloaded weights and third-party artifacts require their own applicable notices and source/distribution review. This documentation is not a complete release-compliance audit.
