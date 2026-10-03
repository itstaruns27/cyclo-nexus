"""
Retrain the YOLO-OBB cyclone detector on REAL INSAT imagery (master plan v4, Task 3.4).

Run on a GPU (local RTX 4060 8 GB, or Kaggle / Colab) after exporting the dataset:
  pip install ultralytics
  python vision/train_real_obb.py --data data/training/yolo/data.yaml --epochs 120
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
    ap.add_argument("--model", default="yolo11s-obb.pt", help="pretrained OBB checkpoint to fine-tune")
    ap.add_argument("--epochs", type=int, default=120)
    ap.add_argument("--imgsz", type=int, default=512, help="store frames are 512²; serve.py feeds YOLO 512²")
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--workers", type=int, default=2, help="data-loader processes; each loads CUDA on Windows (page-file heavy)")
    args = ap.parse_args()

    model = YOLO(args.model)
    results = model.train(
        data=args.data, epochs=args.epochs, imgsz=args.imgsz, batch=args.batch, workers=args.workers,
        # Satellite imagery: no colour jitter (channels are physical brightness temperatures / rain);
        # no flips (a mirrored storm spins the wrong way for its hemisphere). Rotation keeps the
        # spin direction, so it is a physically valid augmentation; mosaic adds scene variety.
        hsv_h=0.0, hsv_s=0.0, hsv_v=0.0, fliplr=0.0, flipud=0.0, degrees=45.0, mosaic=0.5,
        close_mosaic=15, translate=0.1, scale=0.25, cos_lr=True, patience=30, seed=0, deterministic=True,
        project=str(Path(__file__).resolve().parents[1] / "runs" / "cyclone_obb"), name="real", exist_ok=True,
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
