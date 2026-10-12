"""Evaluate supplied YOLO-OBB reference labels without changing detector parameters."""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from config import AnalysisSettings
from detector import SatelliteDetector, read_image, overlap_metrics


def evaluate(dataset, detector, settings):
    evidence = []
    for image_path in sorted((dataset/"images").rglob("*")):
        if image_path.suffix.lower() not in (".jpg",".png",".jpeg"):
            continue
        label_path = dataset/"labels"/image_path.relative_to(dataset/"images").with_suffix(".txt")
        if not label_path.exists():
            continue
        image = read_image(image_path)
        h,w = image.shape[:2]
        truth = []
        for line in label_path.read_text().splitlines():
            values = line.split()
            if len(values) == 9 and values[0] == "0":
                coords = list(map(float,values[1:]))
                polygon = [[coords[i]*w,coords[i+1]*h] for i in range(0,8,2)]
                truth.append({"polygon":polygon,"bbox":[min(p[0] for p in polygon),min(p[1] for p in polygon),max(p[0] for p in polygon),max(p[1] for p in polygon)]})
        result = detector.predict(image_path,settings)
        predicted = [d for d in result["detections"] if d["class"] == "aircraft"]
        matched = set()
        tp = 0
        for d in sorted(predicted,key=lambda d:d["confidence"],reverse=True):
            options = [(overlap_metrics(d,t)[0],index) for index,t in enumerate(truth) if index not in matched]
            if options:
                iou,index = max(options)
                if iou >= settings.iou_threshold:
                    matched.add(index);tp += 1
        record = {"image":image_path.name,"labeled_aircraft":len(truth),"predicted_aircraft":len(predicted),
                  "true_positives":tp,"false_positives":len(predicted)-tp,"false_negatives":len(truth)-tp,
                  "review_candidates":sum(d.get("accepted_by")=="cross_model_review" for d in predicted)}
        evidence.append(record)
        print(json.dumps(record),flush=True)
    return evidence


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset",type=Path,help="Directory containing images/ and labels/ in YOLO OBB format")
    parser.add_argument("--output",type=Path,default=Path("outputs/verification/reference-evaluation.json"))
    args = parser.parse_args()
    evidence = evaluate(args.dataset,SatelliteDetector(),AnalysisSettings())
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(evidence,indent=2))
