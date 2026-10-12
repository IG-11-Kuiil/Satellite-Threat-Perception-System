# Aerial detector validation

## What failed

In the supplied 1920 × 1080 overhead image, four aircraft are visibly present: two on the left, a smaller central aircraft, and a larger aircraft at lower right. The original YOLOv8s/COCO run reported four detections but missed the central aircraft and duplicated the upper-left aircraft. Equal totals therefore hid two errors.

The duplicate was a tile-edge fragment. The complete upper-left rectangle had confidence 0.687; the fragment had confidence 0.698 and IoU below the 0.35 cutoff. The fragment was largely contained by the complete rectangle, so standard IoU suppression alone did not remove it. The aircraft type supplied by the user is not independently identified by this system.

## Measured comparisons

All models ran locally using actual public pretrained Ultralytics weights. Aerial models were evaluated at 1024 px inference resolution. DOTA models predict rotated geometry.

| Model | Observed full-image result at confidence ≥0.10 |
| --- | --- |
| YOLO26s-OBB / DOTA v1 | Three aircraft; central aircraft missed |
| YOLO26m-OBB / DOTA v1 | All four aircraft plus a false positive on the MAXAR watermark |
| YOLO11s-OBB / DOTA v1 | All four aircraft, no additional candidates |

Tiling introduced partial duplicate boxes in both larger tested aerial models. With YOLO11s-OBB at the production defaults (40% confidence, 1024 px, tiled), the improved suppression returned these four detections:

| Detection | Visible object | Score |
| --- | --- | --- |
| A01 | Upper-left aircraft | 90.1% |
| A02 | Lower-left aircraft | 89.1% |
| A03 | Central aircraft missed previously | 60.9% |
| A04 | Lower-right aircraft | 93.4% |

22 raw candidates became four retained aircraft: 18 duplicate/invalid candidates removed. Visual inspection confirmed one box per visible aircraft and no watermark detection in this result. The detector still classifies these as generic aircraft. Scores are not calibrated probabilities.

The live HTTP workflow and browser upload workflow reproduced the four detections. A 960 × 540 resized copy also returned the same four visible aircraft; the central aircraft score was 64.6%. This is a resizing regression on the same scene, not independent dataset evidence.

## General changes

- Default model changed to YOLO11s-OBB/DOTA v1 based on observed performance, rather than release date alone.
- Default confidence is 40%, with lower values still available for candidate review.
- Rotated box polygons are preserved, drawn, and used for overlap comparisons.
- Internal tile-edge candidates are identified. Complete candidates take precedence over fragments, with smaller-box coverage supplementing IoU for known fragments.
- Unmatched truncated detections remain visible and receive a review caveat. Neighboring aircraft are not merged merely because their enclosing rectangles overlap.
- Reports, UI, CLI, and health status use actual model metadata instead of a hard-coded YOLOv8s label.

No coordinates, watermark mask, or image-specific detections are hard-coded into the production detector. The original uploaded image and baseline run remain intact. Benchmark evidence and annotated outputs are local ignored files under `outputs/verification/`; customer imagery and downloaded weights are not committed to Git.

## Reproduce

```powershell
.\.venv\Scripts\python.exe tools/benchmark_models.py "path\to\scene.png"
.\.venv\Scripts\python.exe tools/benchmark_models.py "path\to\scene.png" --models yolo11s-obb.pt yolo26m-obb.pt --tiles
.\.venv\Scripts\python.exe run_mvp.py --image "path\to\scene.png" --model aerial
```

The benchmark writes raw model predictions, not postprocessed final counts. To reproduce the production result, use the UI or single-image CLI. Unit regressions cover suppression geometry using synthetic boxes; they do not download weights or embed the user's imagery.

This is a qualitative, scene-specific validation, not a held-out dataset evaluation. Precision/recall across other satellite scenes, aircraft types, scales, or sensors has not been established. Primary model documentation: [Ultralytics OBB](https://docs.ultralytics.com/tasks/obb), [YOLO11 OBB and DOTA training](https://www.ultralytics.com/blog/how-to-use-ultralytics-yolo11-for-obb-object-detection).
