"""
Mysuru RoadWatch — YOLO Model Training Script for Water Body on Road Surface Detection

Detects:
  - Water Body / Flooded Road (large standing water on roadway pavement)
  - Road Puddle (localized rainwater puddles on asphalt)
  - Waterlogged Pothole (water-filled road cavities)

Classes:
  0: water_body
  1: puddle
  2: waterlogged_pothole

Usage:
  python ai/train_water_body.py --epochs 16 --batch 8
"""

import os
import sys
import argparse
import random
import shutil
from pathlib import Path
import cv2
import numpy as np

# Ensure project root in sys.path
ai_dir = Path(__file__).resolve().parent
project_root = ai_dir.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from ultralytics import YOLO


def synthesize_road_puddle(src_img: np.ndarray):
    """
    Synthesizes a realistic rainwater puddle on asphalt road with
    specular reflection, darker wet rim, and fluid organic contour.
    Returns: (augmented_img, [(1, cx, cy, bw, bh)])
    """
    h, w = src_img.shape[:2]
    canvas = src_img.copy()

    px = random.randint(int(w * 0.20), int(w * 0.80))
    py = random.randint(int(h * 0.35), int(h * 0.85))
    rx = random.randint(int(w * 0.08), int(w * 0.20))
    ry = random.randint(int(h * 0.05), int(h * 0.12))
    angle = random.randint(-25, 25)

    # 1. Darker wet road boundary rim
    overlay = canvas.copy()
    cv2.ellipse(overlay, (px, py), (rx + 10, ry + 8), angle, 0, 360, (20, 22, 25), -1)
    cv2.addWeighted(overlay, 0.40, canvas, 0.60, 0, canvas)

    # 2. Reflective puddle water body
    puddle_overlay = canvas.copy()
    water_color = (random.randint(65, 95), random.randint(65, 90), random.randint(55, 75))
    cv2.ellipse(puddle_overlay, (px, py), (rx, ry), angle, 0, 360, water_color, -1)

    # 3. Specular sky highlight inside puddle (gloss reflection)
    highlight_rx = max(5, int(rx * 0.60))
    highlight_ry = max(3, int(ry * 0.45))
    hx = px + random.randint(-int(rx * 0.2), int(rx * 0.2))
    hy = py - random.randint(2, int(ry * 0.25))
    specular_color = (random.randint(125, 175), random.randint(130, 180), random.randint(120, 160))
    cv2.ellipse(puddle_overlay, (hx, hy), (highlight_rx, highlight_ry), angle, 0, 360, specular_color, -1)

    cv2.addWeighted(puddle_overlay, 0.70, canvas, 0.30, 0, canvas)

    # 4. Faint water ripple rings
    cv2.ellipse(canvas, (px, py), (int(rx * 0.85), int(ry * 0.85)), angle, 0, 360, (110, 120, 130), 1)

    bx1 = max(0, px - rx - 10)
    by1 = max(0, py - ry - 8)
    bx2 = min(w, px + rx + 10)
    by2 = min(h, py + ry + 8)

    cx = float((bx1 + bx2) / 2.0) / w
    cy = float((by1 + by2) / 2.0) / h
    bw = float(bx2 - bx1) / w
    bh = float(by2 - by1) / h

    return canvas, [(1, cx, cy, bw, bh)]


def synthesize_large_water_body(src_img: np.ndarray):
    """
    Synthesizes an extended water body / flooded section across road surface.
    Returns: (augmented_img, [(0, cx, cy, bw, bh)])
    """
    h, w = src_img.shape[:2]
    canvas = src_img.copy()

    # Spans a large portion of the road lane
    cx_center = random.randint(int(w * 0.35), int(w * 0.65))
    cy_center = random.randint(int(h * 0.48), int(h * 0.80))
    rx = random.randint(int(w * 0.22), int(w * 0.42))
    ry = random.randint(int(h * 0.12), int(h * 0.25))
    angle = random.randint(-15, 15)

    # Darker wet surrounding asphalt
    overlay = canvas.copy()
    cv2.ellipse(overlay, (cx_center, cy_center), (rx + 16, ry + 12), angle, 0, 360, (22, 25, 28), -1)
    cv2.addWeighted(overlay, 0.45, canvas, 0.55, 0, canvas)

    # Deep water body fill
    water_overlay = canvas.copy()
    water_tone = (random.randint(60, 85), random.randint(65, 90), random.randint(55, 75))
    cv2.ellipse(water_overlay, (cx_center, cy_center), (rx, ry), angle, 0, 360, water_tone, -1)

    # Broad specular light reflection from sky/sun
    glint_x = cx_center + random.randint(-int(rx * 0.15), int(rx * 0.15))
    glint_y = cy_center - int(ry * 0.20)
    cv2.ellipse(water_overlay, (glint_x, glint_y), (int(rx * 0.75), int(ry * 0.50)), angle, 0, 360, (135, 145, 150), -1)

    # Ripples across the flooded surface
    for rip_scale in [0.4, 0.65, 0.85]:
        cv2.ellipse(water_overlay, (cx_center, cy_center), (int(rx * rip_scale), int(ry * rip_scale)), angle, 0, 360, (115, 125, 130), 1)

    cv2.addWeighted(water_overlay, 0.72, canvas, 0.28, 0, canvas)

    bx1 = max(0, cx_center - rx - 16)
    by1 = max(0, cy_center - ry - 12)
    bx2 = min(w, cx_center + rx + 16)
    by2 = min(h, cy_center + ry + 12)

    cx = float((bx1 + bx2) / 2.0) / w
    cy = float((by1 + by2) / 2.0) / h
    bw = float(bx2 - bx1) / w
    bh = float(by2 - by1) / h

    return canvas, [(0, cx, cy, bw, bh)]


def synthesize_waterlogged_pothole(src_img: np.ndarray):
    """
    Synthesizes a submerged, water-filled road pothole.
    Returns: (augmented_img, [(2, cx, cy, bw, bh)])
    """
    h, w = src_img.shape[:2]
    canvas = src_img.copy()

    px = random.randint(int(w * 0.25), int(w * 0.75))
    py = random.randint(int(h * 0.35), int(h * 0.80))
    p_rx = random.randint(int(w * 0.07), int(w * 0.16))
    p_ry = random.randint(int(h * 0.05), int(h * 0.12))
    angle = random.randint(-20, 20)

    # Pothole cavity rim
    overlay = canvas.copy()
    cv2.ellipse(overlay, (px, py), (p_rx + 8, p_ry + 6), angle, 0, 360, (20, 22, 24), -1)

    # Muddy/waterlogged inner pool
    inner_water = (random.randint(45, 70), random.randint(55, 75), random.randint(50, 68))
    cv2.ellipse(overlay, (px, py), (p_rx, p_ry), angle, 0, 360, inner_water, -1)

    # Water reflection glint
    cv2.ellipse(overlay, (px, py - 3), (max(3, int(p_rx * 0.5)), max(2, int(p_ry * 0.4))), angle, 0, 360, (115, 125, 130), -1)

    cv2.addWeighted(overlay, 0.85, canvas, 0.15, 0, canvas)

    bx1 = max(0, px - p_rx - 8)
    by1 = max(0, py - p_ry - 6)
    bx2 = min(w, px + p_rx + 8)
    by2 = min(h, py + p_ry + 6)

    cx = float((bx1 + bx2) / 2.0) / w
    cy = float((by1 + by2) / 2.0) / h
    bw = float(bx2 - bx1) / w
    bh = float(by2 - by1) / h

    return canvas, [(2, cx, cy, bw, bh)]


def generate_water_body_dataset(dataset_root: Path, num_samples: int = 45) -> Path:
    """
    Creates dataset with ground truth water bodies on road surfaces:
    - Real waterlogged road image with precise annotations
    - Synthesized water bodies (large standing water / floods)
    - Synthesized road puddles
    - Synthesized waterlogged potholes
    - Negative background samples (dry clean roads) to suppress false positives
    """
    print(f"[Water Body Dataset] Generating {num_samples} road water surface samples...")
    images_train_dir = dataset_root / "images" / "train"
    images_val_dir = dataset_root / "images" / "val"
    labels_train_dir = dataset_root / "labels" / "train"
    labels_val_dir = dataset_root / "labels" / "val"

    for d in [images_train_dir, images_val_dir, labels_train_dir, labels_val_dir]:
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True, exist_ok=True)

    sample_counter = 0

    # 1. Real waterlogged road sample
    real_sample_path = project_root / "data" / "images" / "sample_waterlogged_road.jpg"
    if real_sample_path.exists():
        real_img = cv2.imread(str(real_sample_path))
        if real_img is not None:
            # Water body spanning road center and puddle on lower-mid road
            real_boxes = [
                (0, 0.500, 0.620, 0.780, 0.540), # Class 0: water_body
                (1, 0.450, 0.750, 0.420, 0.320)  # Class 1: puddle
            ]
            for is_val in [False, True]:
                out_img_dir = images_val_dir if is_val else images_train_dir
                out_lbl_dir = labels_val_dir if is_val else labels_train_dir
                fname = f"real_waterlogged_{sample_counter:03d}.jpg"
                cv2.imwrite(str(out_img_dir / fname), real_img)
                with open(out_lbl_dir / f"real_waterlogged_{sample_counter:03d}.txt", "w") as f:
                    for cid, cx, cy, bw, bh in real_boxes:
                        f.write(f"{cid} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}\n")
                sample_counter += 1

            # Flip augmentation
            flipped = cv2.flip(real_img, 1)
            fname = f"real_waterlogged_flip_{sample_counter:03d}.jpg"
            cv2.imwrite(str(images_train_dir / fname), flipped)
            with open(labels_train_dir / f"real_waterlogged_flip_{sample_counter:03d}.txt", "w") as f:
                for cid, cx, cy, bw, bh in real_boxes:
                    f.write(f"{cid} {1.0 - cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}\n")
            sample_counter += 1

    # Base reference road images for background
    source_images_dir = project_root / "data" / "images"
    sample_files = list(source_images_dir.glob("sample_*.jpg"))
    if not sample_files:
        sample_files = [real_sample_path]

    # Generate synthetic diverse water bodies
    for i in range(num_samples):
        src_path = random.choice(sample_files)
        src_img = cv2.imread(str(src_path))
        if src_img is None:
            continue

        is_val = (i % 5 == 0)
        img_out_dir = images_val_dir if is_val else images_train_dir
        lbl_out_dir = labels_val_dir if is_val else labels_train_dir

        water_type = random.choice(["water_body", "puddle", "waterlogged_pothole", "multi_puddle"])

        if water_type == "water_body":
            img, boxes = synthesize_large_water_body(src_img)
        elif water_type == "waterlogged_pothole":
            img, boxes = synthesize_waterlogged_pothole(src_img)
        elif water_type == "multi_puddle":
            img, boxes1 = synthesize_road_puddle(src_img)
            img, boxes2 = synthesize_road_puddle(img)
            boxes = boxes1 + boxes2
        else: # single puddle
            img, boxes = synthesize_road_puddle(src_img)

        fname = f"water_sample_{sample_counter:03d}.jpg"
        cv2.imwrite(str(img_out_dir / fname), img)
        with open(lbl_out_dir / f"water_sample_{sample_counter:03d}.txt", "w") as lf:
            for cls_id, cx, cy, bw, bh in boxes:
                lf.write(f"{cls_id} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}\n")

        sample_counter += 1

    # Add negative background samples (clean dry roads without water)
    for dry_name in ["sample_moderate_road.jpg", "sample_muddy_road.jpg", "sample_crack_road.jpg"]:
        dp = source_images_dir / dry_name
        if dp.exists():
            dimg = cv2.imread(str(dp))
            if dimg is not None:
                fname = f"dry_road_{sample_counter:03d}.jpg"
                cv2.imwrite(str(images_train_dir / fname), dimg)
                # Empty label file for background image
                with open(labels_train_dir / f"dry_road_{sample_counter:03d}.txt", "w") as lf:
                    pass
                sample_counter += 1

    # Write dataset.yaml
    yaml_path = dataset_root / "dataset.yaml"
    yaml_content = f"""# Mysuru RoadWatch — Water Body on Road Surface Dataset
path: {dataset_root.resolve().as_posix()}
train: images/train
val: images/val

names:
  0: water_body
  1: puddle
  2: waterlogged_pothole
"""
    with open(yaml_path, "w") as f:
        f.write(yaml_content)

    print(f"[Water Body Dataset] Dataset configured with {sample_counter} samples at: {yaml_path}")
    return yaml_path


def train_water_body_model(
    epochs: int = 15,
    batch: int = 8,
    imgsz: int = 384,
    device: str = "cpu",
    dataset_yaml: str = None,
    generate_data: bool = True
):
    print("=" * 68)
    print("  MYSURU ROADWATCH — TRAINING WATER BODY ON ROAD SURFACE MODEL")
    print("=" * 68)

    dataset_root = project_root / "data" / "water_dataset"
    if generate_data or not (dataset_root / "dataset.yaml").exists():
        dataset_yaml = str(generate_water_body_dataset(dataset_root, num_samples=45))
    elif not dataset_yaml:
        dataset_yaml = str(dataset_root / "dataset.yaml")

    print(f"Dataset configuration: {dataset_yaml}")

    # Load base pretrained model
    base_model_candidates = [
        project_root / "ai" / "model" / "yolov8n.pt",
        project_root / "yolov8n.pt",
        Path("yolov8n.pt")
    ]
    base_model_path = next((p for p in base_model_candidates if p.exists()), Path("yolov8n.pt"))
    print(f"Loading pretrained YOLOv8 backbone from: {base_model_path}...")
    model = YOLO(str(base_model_path))

    print(f"\nTraining configuration:")
    print(f" - Model:      YOLOv8n (Custom Water Body Detector)")
    print(f" - Epochs:     {epochs}")
    print(f" - Image Size: {imgsz}")
    print(f" - Batch Size: {batch}")
    print(f" - Device:     {device}")

    runs_dir = project_root / "ai" / "runs"
    results = model.train(
        data=dataset_yaml,
        epochs=epochs,
        imgsz=imgsz,
        batch=batch,
        project=str(runs_dir),
        name="roadwatch_water_model",
        save=True,
        plots=False,
        optimizer="auto",
        device=device
    )

    print("\nTraining completed successfully!")
    save_dir = Path(getattr(results, "save_dir", runs_dir / "roadwatch_water_model"))
    weights_path = save_dir / "weights" / "best.pt"
    if not weights_path.exists():
        weights_path = runs_dir / "roadwatch_water_model" / "weights" / "best.pt"

    dest_model = project_root / "ai" / "model" / "water_body_best.pt"
    if weights_path.exists():
        dest_model.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(str(weights_path), str(dest_model))
        print(f"\n[OK] Model saved to production path: {dest_model.resolve()}")

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train YOLO model for water body on road surface")
    parser.add_argument("--epochs", type=int, default=15, help="Training epochs")
    parser.add_argument("--batch", type=int, default=8, help="Batch size")
    parser.add_argument("--imgsz", type=int, default=384, help="Image size")
    parser.add_argument("--device", type=str, default="cpu", help="Compute device ('cpu' or '0')")
    parser.add_argument("--data", type=str, default=None, help="Dataset yaml path")
    parser.add_argument("--generate-dataset", action="store_true", help="Generate water body dataset")
    args = parser.parse_args()

    train_water_body_model(
        epochs=args.epochs,
        batch=args.batch,
        imgsz=args.imgsz,
        device=args.device,
        dataset_yaml=args.data,
        generate_data=True
    )
