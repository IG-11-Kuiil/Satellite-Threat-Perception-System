# Satellite Threat Perception System

A computer vision and reasoning pipeline for analyzing overhead satellite imagery and identifying changes in military asset activity over time. The system detects aircraft, filters duplicate detections, analyzes spatial clustering, estimates activity level, and compares before/after images to generate an analyst-style change detection report.

## Why I Built This

I built this project to explore how AI can support satellite-based situational awareness and defense-oriented imagery analysis. Rather than only running object detection, I wanted to build a fuller pipeline that interprets detections, handles uncertainty, and explains why a scene may require human review.

## Features

* Aircraft detection in satellite imagery using YOLOv8
* Sliding-window tiled inference for improved small-object detection
* Confidence filtering and IoU-based duplicate detection removal
* Spatial clustering analysis to identify grouped vs. isolated assets
* Activity level estimation: LOW, MEDIUM, HIGH
* Analyst-style natural language summaries
* Before/after change detection between two satellite images
* Priority scoring for activity changes
* Final annotated output images and text-based change reports

## Tech Stack

* Python
* OpenCV
* YOLOv8 / Ultralytics
* NumPy
* Basic spatial analysis and rule-based reasoning
* Rule-based explainable reasoning

## Project Structure

```text
Satellite-Threat-Perception-System/
├── config.py
├── run_mvp.py
├── run_change_detection.py
├── src/
│   ├── detection/
│   │   └── detector.py
│   └── reasoning/
│       ├── activity.py
│       ├── spatial.py
│       └── change_detection.py
├── data/
│   └── sample_images/
└── outputs/
```

## How It Works

### 1. Detection

The detector uses a pretrained YOLOv8s model trained on COCO classes to identify aircraft in satellite imagery. Because aircraft can appear small in overhead images, the system runs both full-image inference and sliding-window tiled inference.

### 2. Filtering

Raw detections are filtered using class-specific confidence thresholds. Duplicate boxes are removed using Intersection over Union (IoU), keeping the highest-confidence detection when boxes overlap.

### 3. Spatial Reasoning

Detected aircraft are converted into center points. The system computes pairwise distances and identifies aircraft cluster relationships based on a distance threshold. This helps distinguish localized staging activity from dispersed assets.

### 4. Activity Assessment

The system estimates activity level using aircraft counts and spatial clustering patterns. It also flags low-confidence detections so the summary can communicate uncertainty instead of overstating model reliability.

### 5. Change Detection

For before/after images, the pipeline compares:

* Aircraft count
* Vehicle count
* Aircraft cluster relationships
* Activity level

It then assigns an activity trend and review priority.

## Example Output

Example change summary:

```text
SATELLITE CHANGE DETECTION REPORT

BEFORE IMAGE ANALYSIS
Aircraft detected: 5
Vehicles detected: 0
Aircraft cluster pairs: 10
Activity level: MEDIUM

AFTER IMAGE ANALYSIS
Aircraft detected: 13
Vehicles detected: 0
Aircraft cluster pairs: 69
Activity level: HIGH

CHANGE ASSESSMENT
Aircraft change: +8
Vehicle change: 0
Cluster change: +59
Activity level change: MEDIUM -> HIGH
Activity trend: Increased
Review priority: High

Analyst-style change summary:
Aircraft count changed from 5 to 13 (+8). Vehicle count changed from 0 to 0 (0).
Aircraft cluster relationships changed from 10 to 69 (+59). Overall activity increased from MEDIUM to HIGH.
Activity trend is assessed as Increased. Review priority is assessed as High.
This assessment is based on model detections and should be reviewed by a human analyst.
```

## Important Limitations

This is a prototype and should not be treated as an operational intelligence system.

* The detector uses a general COCO-trained YOLO model, not a satellite-specific model.
* Small, low-contrast, partially obscured, or unusual aircraft may be missed.
* Vehicle detection is currently disabled because the base model is unreliable for small overhead vehicles.
* Some test imagery was synthetically generated for experimentation because suitable public before/after satellite images were difficult to find.
* Human analyst review is required before drawing any real-world conclusions.

## Future Improvements

* Fine-tune on satellite/aerial datasets such as DOTA or xView
* Reintroduce vehicle detection using an aerial imagery-specific model
* Add a chatbot-style interface for querying detections and reports
* Improve geospatial reasoning using coordinates and location-aware analysis
* Extend from two-image comparison to multi-temporal tracking across longer observation windows

## Main Scripts

Run single-image MVP analysis:

```bash
python run_mvp.py
```

Run before/after change detection:

```bash
python run_change_detection.py
```

## Notes

This project was built as a personal AI and computer vision project focused on defense technology, satellite imagery interpretation, and reasoning around imperfect model outputs.
