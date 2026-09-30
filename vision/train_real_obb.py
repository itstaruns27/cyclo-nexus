"""
Retrain the YOLO-OBB cyclone detector on REAL INSAT imagery (master plan v4, Task 3.4).

Run on a GPU (Kaggle / Colab) after exporting the dataset:
  pip install ultralytics
  python vision/train_real_obb.py --data data/training/yolo/data.yaml --epochs 80
The best checkpoint is copied to vision/weights/vision_best.pt, which inference/serve.py loads.
Before enabling it in production, re-run the validation suite:
  python -m data_pipeline.validation.evaluate_detector
and a replay such as:
  python -m data_pipeline.ingestion.live_pipeline_runner --at 2024-05-26T12:00Z --dry-run
"""

import argparse
import shutil
from pathlib import Path

from ultralytics import YOLO


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/training/yolo/data.yaml")
    ap.add_argument("--model", default="yolov8n-obb.pt", help="pretrained OBB checkpoint to fine-tune")
    ap.add_argument("--epochs", type=int, default=80)
    ap.add_argument("--imgsz", type=int, default=1024)
    ap.add_argument("--batch", type=int, default=8)
    args = ap.parse_args()

    model = YOLO(args.model)
    results = model.train(
        data=args.data, epochs=args.epochs, imgsz=args.imgsz, batch=args.batch,
        # Satellite imagery: no colour jitter (channels are physical), flips are physically invalid
        # for rotating storms in a hemisphere, so keep only scale/translate augmentation.
        hsv_h=0.0, hsv_s=0.0, hsv_v=0.0, fliplr=0.0, flipud=0.0, mosaic=0.0, degrees=0.0,
        translate=0.1, scale=0.2, patience=20, project="runs/cyclone_obb", name="real",
    )
    best = Path(results.save_dir) / "weights" / "best.pt"
    dest = Path(__file__).resolve().parent / "weights" / "vision_best.pt"
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        shutil.copy(dest, dest.with_name("vision_best.synthetic_backup.pt"))
    shutil.copy(best, dest)
    print(f"Copied {best} → {dest}")


if __name__ == "__main__":
    main()
