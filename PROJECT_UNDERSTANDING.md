# Satellite Threat Perception System: code understanding

> Historical baseline review, written before the v2 improvements. The execution blockers and reasoning issues below describe commit `650ecc7`. See README.md for the current implementation, setup, and limitations.

Reviewed on October 11, 2026. Repository: `IG-11-Kuiil/Satellite-Threat-Perception-System`. Branch: `main`. Reviewed commit: `650ecc75d2891face63a4d7958b5c88962b7f7e5`.

## Purpose and current scope

This is a Python command-line prototype that detects aircraft in overhead imagery and uses deterministic rules to describe scene activity and compare two observations. YOLO supplies object detections; ordinary Python functions supply the interpretation and prose. There is no language model, chatbot, web application, database, geospatial processing, object tracking, or training pipeline in this checkout. It counts generic aircraft and cannot identify aircraft types, ownership, intent, or an actual threat.

The repository contains seven Python modules, README, MIT license, and a generic Python gitignore. The complete fetched history contains five commits and the remote advertises only `main`; no tags were advertised.

## File responsibilities

| File | Responsibility |
| --- | --- |
| `config.py` | Defines repository-relative data, sample image, model, and output paths; also declares target classes and activity thresholds. |
| `detector.py` | Loads YOLOv8s, runs tiled and full-image inference, maps classes, filters confidence, translates tile coordinates, and removes duplicate boxes. |
| `spatial.py` | Calculates bounding-box centers and returns pairs of detections separated by less than a pixel-distance threshold. |
| `activity.py` | Assigns count-based activity levels and builds a templated scene summary. |
| `change_detection.py` | Compares counts and activity ranks, assigns trend and review priority, and generates a templated change summary. |
| `run_mvp.py` | Orchestrates one-image analysis, prints results, and writes an annotated image. |
| `run_change_detection.py` | Orchestrates two-image analysis, prints results, and writes a text report and two annotated images. |

## Pipeline and contracts

```text
Image path
  -> OpenCV image loading
  -> YOLO inference on overlapping tiles and the full image
  -> confidence and class filtering
  -> tile boxes translated into full-image coordinates
  -> same-class IoU suppression
  -> detections, counts, nearby aircraft pairs
  -> count-based activity classification and scene summary
  -> before/after differences, weighted trend, review priority
  -> console text, report, annotated JPEGs
```

Each detection is a dictionary with `class` (`aircraft` or `vehicle`), `confidence` (floating-point score), and `bbox` (four full-image pixel coordinates: x1, y1, x2, y2). `predict()` returns `image_path` and `detections`.

`analyze_image()` in the two-image runner adds `aircraft_count`, `vehicle_count`, `clusters`, `activity_level`, and `summary`. The comparison functions consume those dictionaries. Cluster entries are index pairs into the supplied detection list, not object identifiers or cluster components.

## Detection details

- Model: `YOLO("yolov8s.pt")`. The configured `MODELS_DIR` is unused; no model weights are committed.
- Tiles are up to 640 by 640 pixels, stepped by 320 pixels in both directions. Edge tiles with either dimension below 100 pixels are skipped. Full-image inference still follows.
- Both inference paths use `conf=0.10` and `imgsz=1280`.
- COCO `airplane` becomes `aircraft` when confidence is at least 0.18.
- Optional COCO `car`, `truck`, and `bus` become `vehicle` when confidence is at least 0.30. Vehicle detection defaults to disabled in both runners.
- Detections are sorted by confidence. A box is removed when an already retained box of the same class has IoU strictly greater than 0.35. The helper's standalone default is 0.40, overridden by `predict()`.
- Unreadable input images cause a `FileNotFoundError` in the detector. Prediction prints tile progress even with `verbose=False`; that flag controls only raw class logging.

## Reasoning rules

Nearby relationships use Euclidean distance between bounding-box centers, with a strict cutoff below 450 pixels. Every qualifying pair is returned. A group of n mutually nearby aircraft produces n(n-1)/2 pairs. This is pair counting, not a count of distinct groups, and it depends on image scale.

Activity level uses aircraft count plus vehicle count only: 0-2 is LOW, 3-6 is MEDIUM, and 7 or more is HIGH. Clustering changes prose and the temporal score, but does not affect the activity level. The corresponding constants in `config.py` are not consumed by this function.

Scene summaries mention nearby assets when there is at least one pair and mention limited confidence when a retained aircraft has confidence below 0.40. The isolation sentence is emitted whenever there are more than two aircraft and any nearby pair; it does not check whether an isolated aircraft actually exists.

For temporal comparison, let A be aircraft-count change, V vehicle-count change, C nearby-pair-count change, and R activity-rank change, where LOW/MEDIUM/HIGH map to 0/1/2. The trend score is:

```text
score = 2*A + V + C + 2*R
score >= 2: Increased
score <= -2: Decreased
otherwise: Stable
```

Review priority returns the first applicable result:

1. High if A >= 2.
2. High if current activity is HIGH and either A > 0 or C > 0.
3. High if trend is Increased and C > 0.
4. Medium if A == 1, V >= 2, or C > 0.
5. Low otherwise.

There is no calibrated probability or numerical threat score. Large decreases usually receive Low priority. Pair counts grow quadratically and can dominate trend even when aircraft numbers barely change. Invalid activity strings silently map to LOW rank in comparisons.

## Inputs and outputs

The one-image runner expects `data/sample_images/example.png` and writes `outputs/prediction_example_final.jpg`. It prints detections, counts, nearby pairs, activity, and summary; it does not save a text scene report.

The two-image runner expects `data/sample_images/before.png` and `after.png`. It writes `outputs/change_report.txt`, `prediction_before_final.jpg`, and `prediction_after_final.jpg`. Filenames are fixed and repeat runs overwrite existing outputs. Both runners use OpenCV to annotate boxes. The two-image runner sorts boxes by image position and labels them sequentially; labels do not match objects between observations. Neither runner checks the success return value of `cv2.imwrite`.

There are no command-line arguments, timestamps, location metadata, image registration, ground sampling distance normalization, or same-area validation. The comparison operates on aggregate scene statistics, not matched objects or pixel changes.

## Execution blockers and implementation discrepancies

1. **Package layout:** both runners import `src.detection.detector` and `src.reasoning.*`, but all modules are committed at the root and `src/` is absent. The README describes the intended package layout rather than the actual checkout.
2. **Dependencies:** there is no requirements file, package manifest, lockfile, or installation procedure. In the current default Python environment, OpenCV and Ultralytics were unavailable; NumPy and Torch were discoverable. End-to-end inference was not run.
3. **Assets:** no sample images, datasets, weights, or generated example outputs are committed. The README's numerical example cannot establish detector accuracy.
4. **Unsupported isolation statement:** a synthetic case with all three aircraft mutually nearby still produced the sentence asserting an isolated aircraft.
5. **Configuration drift:** target classes, model directory, and activity limits are declared but unused by their corresponding implementation paths.
6. **Clustering inconsistency:** the one-image runner clusters every detection; the two-image runner filters to aircraft first. Enabling vehicle detection would change the meaning of the one-image cluster summary.
7. **Confidence propagation:** low-confidence flags affect scene prose but do not reduce trend or priority and are not inputs to the comparison function.

The README correctly identifies the general COCO model's overhead-imagery limitations and explains that some experimentation used synthetic imagery. No measured precision, recall, comparison ground truth, tests, or continuous integration configuration are included.

## Verification performed

All seven Python modules passed AST syntax parsing. Dependency availability and the missing package/assets were checked without downloading weights or installing libraries. Direct smoke checks confirmed activity boundaries, pair enumeration, count comparison, the README's example change summary, IoU for identical/disjoint boxes, and highest-confidence duplicate retention. Detector helper checks extracted the pure functions through AST so optional ML dependencies were not required. These checks validate the inspected rules, not real-image performance.

Source code remains as pulled. This document is a local, uncommitted analysis artifact.

## Natural next steps

First reconcile the package layout, declare dependencies, and supply sample imagery so both runners can execute. Next correct the isolation predicate and consolidate shared configuration and analysis logic. Meaningful validation would measure aircraft detections on labeled overhead imagery and compare consistent image scales and scene extents before tuning activity and priority rules. Satellite-specific training, geospatial normalization, temporal matching, and an interface are future extensions, not existing features.
