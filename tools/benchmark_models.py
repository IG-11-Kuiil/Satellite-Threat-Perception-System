"""Run actual aerial-model predictions on a supplied image; write local evidence."""
import argparse
import json
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import MODELS_DIR
from detector import read_image, tile_origins
from ultralytics import YOLO

parser = argparse.ArgumentParser()
parser.add_argument("image", type=Path)
parser.add_argument("--models", nargs="+", default=["yolo26s-obb.pt", "yolo26m-obb.pt", "yolo11s-obb.pt"])
parser.add_argument("--resolution", type=int, default=1024)
parser.add_argument("--tiles", action="store_true")
args = parser.parse_args()
image = read_image(args.image)
height, width = image.shape[:2]
output = Path("outputs/verification/models")
output.mkdir(parents=True, exist_ok=True)
MODELS_DIR.mkdir(parents=True, exist_ok=True)
for filename in args.models:
    start = time.perf_counter()
    model = YOLO(str(MODELS_DIR/filename))
    ids = [i for i,n in model.names.items() if n in ("plane","airplane")]
    windows = [(0,0,width,height,"full")]
    if args.tiles:
        windows += [(x,y,min(x+640,width),min(y+640,height),"tile")
                    for y in tile_origins(height,640,320) for x in tile_origins(width,640,320)]
    detections = []
    for x,y,x2,y2,source in windows:
        result = model.predict(image[y:y2,x:x2], conf=.10, imgsz=args.resolution, classes=ids, verbose=False)[0]
        boxes = result.obb if result.obb is not None else result.boxes
        for box in boxes:
            bbox = box.xyxy[0].tolist()
            bbox = [bbox[0]+x,bbox[1]+y,bbox[2]+x,bbox[3]+y]
            d = {"confidence":float(box.conf[0]),"bbox":bbox,"source":source,"tile_origin":[x,y]}
            if result.obb is not None:
                d["polygon"] = [[float(px)+x,float(py)+y] for px,py in box.xyxyxyxy[0].tolist()]
            detections.append(d)
    evidence = {"model":filename,"elapsed_seconds":round(time.perf_counter()-start,2),
                "image":str(args.image),"resolution":args.resolution,"detections":detections}
    path = output / f"{Path(filename).stem}_{'tiled' if args.tiles else 'full'}.json"
    path.write_text(json.dumps(evidence,indent=2))
    print(json.dumps(evidence),flush=True)
