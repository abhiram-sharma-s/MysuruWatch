"""
Mysuru RoadWatch — YOLO Model Training Script for Road Damage & Anti-Spoofing Detection
Detects:
  - Road Potholes (single pothole)
  - Severe Pothole Clusters / Many Potholes in Line (consecutive potholes along road lane)
  - Road Cracks (longitudinal & transverse fissures)
  - Alligator Cracks (fatigue web mesh cracks)
  - Screen recaptures & physical device displays (anti-spoofing)

Classes:
  0: pothole
  1: pothole_cluster
  2: crack
  3: alligator_crack
  4: screen_recapture
  5: other_device_screen

Usage:
  python ai/train.py --generate-dataset --epochs 20
  python ai/train.py --data data/dataset/dataset.yaml --epochs 25 --batch 8
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

def synthesize_single_pothole(src_img: np.ndarray):
    """
    Synthesizes a realistic single road pothole on asphalt.
    Returns (augmented_img, [(0, cx, cy, bw, bh)])
    """
    h, w = src_img.shape[:2]
    canvas = src_img.copy()

    px = random.randint(int(w * 0.25), int(w * 0.75))
    py = random.randint(int(h * 0.35), int(h * 0.80))
    p_rx = random.randint(int(w * 0.08), int(w * 0.18))
    p_ry = random.randint(int(h * 0.06), int(h * 0.14))
    angle = random.randint(-25, 25)

    overlay = canvas.copy()
    cv2.ellipse(overlay, (px, py), (p_rx + 8, p_ry + 6), angle, 0, 360, (28, 30, 32), -1)
    inner_col = (16, 18, 20) if random.random() > 0.5 else (50, 55, 60)
    cv2.ellipse(overlay, (px, py), (p_rx, p_ry), angle, 0, 360, inner_col, -1)
    cv2.addWeighted(overlay, 0.88, canvas, 0.12, 0, canvas)
    cv2.ellipse(canvas, (px, py), (p_rx + 3, p_ry + 3), angle, 0, 360, (48, 50, 52), 3)

    bx1 = max(0, px - p_rx - 8)
    by1 = max(0, py - p_ry - 6)
    bx2 = min(w, px + p_rx + 8)
    by2 = min(h, py + p_ry + 6)
    cx = float((bx1 + bx2) / 2.0) / w
    cy = float((by1 + by2) / 2.0) / h
    bw = float(bx2 - bx1) / w
    bh = float(by2 - by1) / h

    return canvas, [(0, cx, cy, bw, bh)]

def synthesize_many_potholes_in_line(src_img: np.ndarray):
    """
    Synthesizes multiple consecutive potholes aligned along the road lane (many potholes in line).
    Returns (augmented_img, [(class_id, cx, cy, bw, bh), ...])
    """
    h, w = src_img.shape[:2]
    canvas = src_img.copy()

    num_potholes = random.randint(3, 5)
    start_x = random.randint(int(w * 0.35), int(w * 0.65))
    start_y = random.randint(int(h * 0.65), int(h * 0.85))
    end_x = start_x + random.randint(-int(w * 0.15), int(w * 0.15))
    end_y = random.randint(int(h * 0.22), int(h * 0.38))

    pothole_boxes = []
    min_x, min_y, max_x, max_y = w, h, 0, 0

    for idx in range(num_potholes):
        t = idx / float(num_potholes - 1)
        px = int(start_x + t * (end_x - start_x) + random.randint(-12, 12))
        py = int(start_y + t * (end_y - start_y) + random.randint(-8, 8))

        scale = 1.0 - t * 0.55
        p_rx = int(random.randint(18, 36) * scale)
        p_ry = int(random.randint(10, 20) * scale)
        angle = random.randint(-20, 20)

        overlay = canvas.copy()
        cv2.ellipse(overlay, (px, py), (p_rx + 4, p_ry + 4), angle, 0, 360, (25, 28, 30), -1)
        inner_col = (15, 15, 18) if random.random() > 0.4 else (45, 50, 55)
        cv2.ellipse(overlay, (px, py), (p_rx, p_ry), angle, 0, 360, inner_col, -1)
        cv2.addWeighted(overlay, 0.85, canvas, 0.15, 0, canvas)
        cv2.ellipse(canvas, (px, py), (p_rx + 2, p_ry + 2), angle, 0, 360, (50, 52, 55), 2)

        bx1, by1 = max(0, px - p_rx - 4), max(0, py - p_ry - 4)
        bx2, by2 = min(w, px + p_rx + 4), min(h, py + p_ry + 4)
        min_x, min_y = min(min_x, bx1), min(min_y, by1)
        max_x, max_y = max(max_x, bx2), max(max_y, by2)

        bcx = float((bx1 + bx2) / 2.0) / w
        bcy = float((by1 + by2) / 2.0) / h
        bbw = float(bx2 - bx1) / w
        bbh = float(by2 - by1) / h
        pothole_boxes.append((0, bcx, bcy, bbw, bbh)) # Class 0: pothole

    cluster_cx = float((min_x + max_x) / 2.0) / w
    cluster_cy = float((min_y + max_y) / 2.0) / h
    cluster_w = float(max_x - min_x) / w
    cluster_h = float(max_y - min_y) / h
    all_boxes = [(1, cluster_cx, cluster_cy, cluster_w, cluster_h)] + pothole_boxes

    return canvas, all_boxes

def synthesize_road_crack(src_img: np.ndarray):
    """
    Synthesizes longitudinal/transverse asphalt cracks.
    Returns (augmented_img, [(2, cx, cy, bw, bh)])
    """
    h, w = src_img.shape[:2]
    canvas = src_img.copy()

    num_pts = random.randint(5, 9)
    cx_start = random.randint(int(w * 0.25), int(w * 0.75))
    cy_start = random.randint(int(h * 0.25), int(h * 0.45))
    pts = [(cx_start, cy_start)]

    cur_x, cur_y = cx_start, cy_start
    step_y = int((h * 0.50) / num_pts)
    for _ in range(num_pts):
        cur_x += random.randint(-18, 18)
        cur_y += step_y + random.randint(-4, 4)
        cur_x = max(10, min(w - 10, cur_x))
        cur_y = max(10, min(h - 10, cur_y))
        pts.append((cur_x, cur_y))

    for j in range(len(pts) - 1):
        cv2.line(canvas, pts[j], pts[j+1], (15, 18, 20), random.randint(2, 4))
        if random.random() > 0.6:
            bx_end = pts[j][0] + random.randint(-25, 25)
            by_end = pts[j][1] + random.randint(10, 30)
            cv2.line(canvas, pts[j], (bx_end, by_end), (20, 22, 25), 2)

    all_x = [p[0] for p in pts]
    all_y = [p[1] for p in pts]
    x1, y1 = max(0, min(all_x) - 10), max(0, min(all_y) - 10)
    x2, y2 = min(w, max(all_x) + 10), min(h, max(all_y) + 10)
    cx = float((x1 + x2) / 2.0) / w
    cy = float((y1 + y2) / 2.0) / h
    bw = float(x2 - x1) / w
    bh = float(y2 - y1) / h

    return canvas, [(2, cx, cy, bw, bh)]

def synthesize_alligator_crack(src_img: np.ndarray):
    """
    Synthesizes interconnected fatigue web cracks (alligator cracking).
    Returns (augmented_img, [(3, cx, cy, bw, bh)])
    """
    h, w = src_img.shape[:2]
    canvas = src_img.copy()

    center_x = random.randint(int(w * 0.3), int(w * 0.7))
    center_y = random.randint(int(h * 0.4), int(h * 0.75))
    rx = random.randint(int(w * 0.12), int(w * 0.22))
    ry = random.randint(int(h * 0.08), int(h * 0.16))

    for _ in range(random.randint(12, 22)):
        cell_x = center_x + random.randint(-rx, rx)
        cell_y = center_y + random.randint(-ry, ry)
        cell_w = random.randint(15, 35)
        cell_h = random.randint(12, 28)
        poly_pts = np.array([
            [cell_x - cell_w // 2, cell_y],
            [cell_x - cell_w // 4, cell_y - cell_h // 2],
            [cell_x + cell_w // 4, cell_y - cell_h // 2],
            [cell_x + cell_w // 2, cell_y],
            [cell_x + cell_w // 4, cell_y + cell_h // 2],
            [cell_x - cell_w // 4, cell_y + cell_h // 2]
        ], dtype=np.int32)
        cv2.polylines(canvas, [poly_pts], isClosed=True, color=(18, 20, 22), thickness=2)

    bx1, by1 = max(0, center_x - rx - 10), max(0, center_y - ry - 10)
    bx2, by2 = min(w, center_x + rx + 10), min(h, center_y + ry + 10)
    cx = float((bx1 + bx2) / 2.0) / w
    cy = float((by1 + by2) / 2.0) / h
    bw = float(bx2 - bx1) / w
    bh = float(by2 - by1) / h

    return canvas, [(3, cx, cy, bw, bh)]

def synthesize_laptop_keyboard(w: int = 800, h: int = 600):
    """
    Synthesizes a realistic laptop keyboard layout, keycap matrix, spacebar and trackpad.
    Returns (canvas, [(cls_id, cx, cy, bw, bh)])
    """
    canvas = np.zeros((h, w, 3), dtype=np.uint8)
    base_color = random.choice([(45, 45, 48), (35, 35, 38), (65, 68, 70), (190, 195, 200)])
    canvas[:] = base_color

    kb_x1, kb_y1 = int(w * 0.08), int(h * 0.12)
    kb_x2, kb_y2 = int(w * 0.92), int(h * 0.68)
    kb_bg = (20, 20, 22) if np.mean(base_color) > 100 else (18, 18, 20)
    cv2.rectangle(canvas, (kb_x1, kb_y1), (kb_x2, kb_y2), kb_bg, -1)

    num_rows = 5
    num_cols = 12
    key_h = max(8, int((kb_y2 - kb_y1 - (num_rows + 1) * 6) / num_rows))
    key_w = max(10, int((kb_x2 - kb_x1 - (num_cols + 1) * 6) / num_cols))
    key_color = (30, 30, 32) if np.mean(base_color) > 100 else (28, 28, 30)

    for r in range(num_rows):
        ky = kb_y1 + 6 + r * (key_h + 6)
        if r == num_rows - 1:
            sp_x1 = kb_x1 + 6 + int(num_cols * 0.28) * (key_w + 6)
            sp_x2 = sp_x1 + int(num_cols * 0.44) * (key_w + 6)
            cv2.rectangle(canvas, (sp_x1, ky), (sp_x2, ky + key_h), (40, 40, 44), -1)
            cv2.rectangle(canvas, (sp_x1, ky), (sp_x2, ky + key_h), (55, 55, 60), 1)
        else:
            for c in range(num_cols):
                kx = kb_x1 + 6 + c * (key_w + 6)
                cv2.rectangle(canvas, (kx, ky), (kx + key_w, ky + key_h), key_color, -1)
                cv2.rectangle(canvas, (kx, ky), (kx + key_w, ky + key_h), (45, 45, 50), 1)

    tp_x1, tp_y1 = int(w * 0.32), int(h * 0.72)
    tp_x2, tp_y2 = int(w * 0.68), int(h * 0.94)
    tp_color = tuple(int(max(0, min(255, c + 8))) for c in base_color)
    cv2.rectangle(canvas, (tp_x1, tp_y1), (tp_x2, tp_y2), tp_color, -1)
    cv2.rectangle(canvas, (tp_x1, tp_y1), (tp_x2, tp_y2), (40, 40, 45), 1)

    noise = np.random.normal(0, 4, canvas.shape).astype(np.int16)
    canvas = np.clip(canvas.astype(np.int16) + noise, 0, 255).astype(np.uint8)

    return canvas, [(5, 0.5, 0.5, 0.94, 0.92)]

def generate_training_dataset(dataset_root: Path, num_samples: int = 50) -> Path:
    """
    Synthesizes training samples of:
    - Real camera pothole images (including many potholes in line)
    - Single potholes & pothole clusters
    - Road cracks & alligator cracks
    - Screen recaptures & physical devices (for anti-spoofing)
    """
    print(f"[Dataset Generator] Generating {num_samples} training samples with accurate real road defects...")
    images_train_dir = dataset_root / "images" / "train"
    images_val_dir = dataset_root / "images" / "val"
    labels_train_dir = dataset_root / "labels" / "train"
    labels_val_dir = dataset_root / "labels" / "val"

    for d in [images_train_dir, images_val_dir, labels_train_dir, labels_val_dir]:
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True, exist_ok=True)

    # 1. Real user uploaded road defect images with precise ground truth
    uploads_dir = project_root / "data" / "images" / "uploads"
    real_user_samples = [
        # Image 1: Many potholes in line along road lane
        {
            "filename": "upload_roadpathole1_1792424050_8186bf.jpeg",
            "boxes": [
                (1, 0.539, 0.524, 0.608, 0.845), # Class 1: pothole_cluster (line of potholes)
                (0, 0.537, 0.824, 0.180, 0.176), # Class 0: pothole (lower)
                (0, 0.557, 0.500, 0.188, 0.176), # Class 0: pothole (mid)
                (0, 0.627, 0.378, 0.149, 0.122), # Class 0: pothole (upper mid)
                (0, 0.675, 0.297, 0.125, 0.108), # Class 0: pothole (upper)
            ]
        },
        # Image 2: Pothole surrounded by cracks & alligator cracks
        {
            "filename": "upload_roadpathole2_1792424066_44b3ba.jpeg",
            "boxes": [
                (0, 0.502, 0.473, 0.549, 0.405), # Class 0: pothole (center)
                (3, 0.502, 0.500, 0.953, 0.946), # Class 3: alligator_crack
                (2, 0.400, 0.350, 0.700, 0.450)  # Class 2: crack
            ]
        },
        # Image 3: Many potholes in line along driving lane
        {
            "filename": "upload_roadpathole3_1792940572_ce17bf.jpeg",
            "boxes": [
                (1, 0.689, 0.514, 0.542, 0.439), # Class 1: pothole_cluster
                (0, 0.517, 0.378, 0.172, 0.162), # Class 0: pothole 1
                (0, 0.631, 0.514, 0.271, 0.203), # Class 0: pothole 2
                (0, 0.862, 0.662, 0.222, 0.189), # Class 0: pothole 3
            ]
        },
        # Image 4: Single deep road pothole
        {
            "filename": "upload_roadpathole_1792423705_19c480.jpeg",
            "boxes": [
                (0, 0.490, 0.574, 0.423, 0.351)  # Class 0: pothole
            ]
        }
    ]

    sample_counter = 0

    # Add real images and augmentations into dataset
    for item in real_user_samples:
        src_path = uploads_dir / item["filename"]
        if src_path.exists():
            base_img = cv2.imread(str(src_path))
            if base_img is not None:
                # Add original
                for is_val in [False, True]:
                    out_img_dir = images_val_dir if is_val else images_train_dir
                    out_lbl_dir = labels_val_dir if is_val else labels_train_dir
                    fname = f"real_pothole_{sample_counter:03d}.jpg"
                    cv2.imwrite(str(out_img_dir / fname), base_img)
                    with open(out_lbl_dir / f"real_pothole_{sample_counter:03d}.txt", "w") as lf:
                        for cid, cx, cy, bw, bh in item["boxes"]:
                            lf.write(f"{cid} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}\n")
                    sample_counter += 1

                # Horizontal flip augmentation
                flipped = cv2.flip(base_img, 1)
                fname = f"real_pothole_flip_{sample_counter:03d}.jpg"
                cv2.imwrite(str(images_train_dir / fname), flipped)
                with open(labels_train_dir / f"real_pothole_flip_{sample_counter:03d}.txt", "w") as lf:
                    for cid, cx, cy, bw, bh in item["boxes"]:
                        lf.write(f"{cid} {1.0 - cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}\n")
                sample_counter += 1

                # Brightness augmentation
                bright = cv2.convertScaleAbs(base_img, alpha=1.18, beta=12)
                fname = f"real_pothole_bright_{sample_counter:03d}.jpg"
                cv2.imwrite(str(images_train_dir / fname), bright)
                with open(labels_train_dir / f"real_pothole_bright_{sample_counter:03d}.txt", "w") as lf:
                    for cid, cx, cy, bw, bh in item["boxes"]:
                        lf.write(f"{cid} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}\n")
                sample_counter += 1

    # Base reference road images
    source_images_dir = project_root / "data" / "images"
    sample_files = list(source_images_dir.glob("sample_*.jpg"))
    if not sample_files:
        base_asphalt = np.zeros((480, 640, 3), dtype=np.uint8)
        base_asphalt[:] = (65, 68, 70)
        cv2.imwrite(str(source_images_dir / "sample_synthetic_road.jpg"), base_asphalt)
        sample_files = [source_images_dir / "sample_synthetic_road.jpg"]

    # Synthesize diverse defect distribution
    for i in range(num_samples):
        src_path = random.choice(sample_files)
        src_img = cv2.imread(str(src_path))
        if src_img is None:
            continue

        sh, sw = src_img.shape[:2]
        is_val = (i % 5 == 0)
        img_out_dir = images_val_dir if is_val else images_train_dir
        lbl_out_dir = labels_val_dir if is_val else labels_train_dir

        sample_type = random.choice([
            "many_potholes_in_line", "many_potholes_in_line",
            "single_pothole", "single_pothole",
            "road_crack", "alligator_crack",
            "phone_screen", "glare_recapture", "laptop_keyboard"
        ])

        if sample_type == "many_potholes_in_line":
            img, boxes = synthesize_many_potholes_in_line(src_img)
            filename = f"pothole_line_{sample_counter:03d}.jpg"
            cv2.imwrite(str(img_out_dir / filename), img)
            with open(lbl_out_dir / f"pothole_line_{sample_counter:03d}.txt", "w") as lf:
                for cls_id, cx, cy, bw, bh in boxes:
                    lf.write(f"{cls_id} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}\n")

        elif sample_type == "single_pothole":
            img, boxes = synthesize_single_pothole(src_img)
            filename = f"single_pothole_{sample_counter:03d}.jpg"
            cv2.imwrite(str(img_out_dir / filename), img)
            with open(lbl_out_dir / f"single_pothole_{sample_counter:03d}.txt", "w") as lf:
                for cls_id, cx, cy, bw, bh in boxes:
                    lf.write(f"{cls_id} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}\n")

        elif sample_type == "road_crack":
            img, boxes = synthesize_road_crack(src_img)
            filename = f"crack_{sample_counter:03d}.jpg"
            cv2.imwrite(str(img_out_dir / filename), img)
            with open(lbl_out_dir / f"crack_{sample_counter:03d}.txt", "w") as lf:
                for cls_id, cx, cy, bw, bh in boxes:
                    lf.write(f"{cls_id} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}\n")

        elif sample_type == "alligator_crack":
            img, boxes = synthesize_alligator_crack(src_img)
            filename = f"alligator_{sample_counter:03d}.jpg"
            cv2.imwrite(str(img_out_dir / filename), img)
            with open(lbl_out_dir / f"alligator_{sample_counter:03d}.txt", "w") as lf:
                for cls_id, cx, cy, bw, bh in boxes:
                    lf.write(f"{cls_id} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}\n")

        elif sample_type == "laptop_keyboard":
            img, boxes = synthesize_laptop_keyboard(sw, sh)
            filename = f"laptop_keyboard_{sample_counter:03d}.jpg"
            cv2.imwrite(str(img_out_dir / filename), img)
            with open(lbl_out_dir / f"laptop_keyboard_{sample_counter:03d}.txt", "w") as lf:
                for cls_id, cx, cy, bw, bh in boxes:
                    lf.write(f"{cls_id} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}\n")

        else: # Screen recapture
            margin_tb = random.randint(45, 95)
            margin_lr = random.randint(35, 75)
            canvas_h = sh + margin_tb * 2
            canvas_w = sw + margin_lr * 2
            canvas = np.zeros((canvas_h, canvas_w, 3), dtype=np.uint8)
            canvas[:] = (30, 32, 35)
            bezel_col = (15, 15, 18)
            cv2.rectangle(canvas, (margin_lr - 10, margin_tb - 15), (canvas_w - margin_lr + 10, canvas_h - margin_tb + 15), bezel_col, -1)
            canvas[margin_tb:margin_tb + sh, margin_lr:margin_lr + sw] = src_img

            if sample_type == "glare_recapture" or random.random() > 0.4:
                glare_center = (random.randint(margin_lr + 50, margin_lr + sw - 50), random.randint(margin_tb + 40, margin_tb + sh - 40))
                glare_radius = random.randint(25, 60)
                overlay = canvas.copy()
                cv2.circle(overlay, glare_center, glare_radius, (255, 255, 255), -1)
                cv2.addWeighted(overlay, 0.45, canvas, 0.55, 0, canvas)

            filename = f"recaptured_screen_{sample_counter:03d}.jpg"
            cv2.imwrite(str(img_out_dir / filename), canvas)
            bx_center = (margin_lr + sw / 2.0) / canvas_w
            by_center = (margin_tb + sh / 2.0) / canvas_h
            b_width = float(sw) / canvas_w
            b_height = float(sh) / canvas_h

            with open(lbl_out_dir / f"recaptured_screen_{sample_counter:03d}.txt", "w") as lf:
                lf.write(f"4 {bx_center:.6f} {by_center:.6f} {b_width:.6f} {b_height:.6f}\n")
                dev_x = 0.5
                dev_y = 0.5
                dev_w = float(sw + margin_lr * 1.5) / canvas_w
                dev_h = float(sh + margin_tb * 1.5) / canvas_h
                lf.write(f"5 {dev_x:.6f} {dev_y:.6f} {dev_w:.6f} {dev_h:.6f}\n")

        sample_counter += 1

    # Generate dataset.yaml with all 6 classes
    yaml_path = dataset_root / "dataset.yaml"
    yaml_content = f"""# Mysuru RoadWatch Dataset Configuration
path: {dataset_root.resolve().as_posix()}
train: images/train
val: images/val

names:
  0: pothole
  1: pothole_cluster
  2: crack
  3: alligator_crack
  4: screen_recapture
  5: other_device_screen
"""
    with open(yaml_path, "w") as f:
        f.write(yaml_content)

    print(f"[Dataset Generator] Successfully configured dataset with 6 classes ({sample_counter} samples) at: {yaml_path}")
    return yaml_path

def train_yolo_roadwatch(
    epochs: int = 15,
    batch: int = 8,
    imgsz: int = 480,
    device: str = "cpu",
    dataset_yaml: str = None,
    generate_data: bool = True
):
    print("=" * 68)
    print("  MYSURU ROADWATCH — YOLO ROAD DAMAGE & POTHOLE CLUSTERS TRAINING")
    print("=" * 68)

    dataset_root = project_root / "data" / "dataset"
    if generate_data or not (dataset_root / "dataset.yaml").exists():
        dataset_yaml = str(generate_training_dataset(dataset_root, num_samples=50))
    elif not dataset_yaml:
        dataset_yaml = str(dataset_root / "dataset.yaml")

    print(f"Using Dataset YAML: {dataset_yaml}")

    # Load base weights
    base_model_path = project_root / "ai" / "model" / "yolov8n.pt"
    if not base_model_path.exists():
        base_model_path = project_root / "yolov8n.pt"
    if not base_model_path.exists():
        base_model_path = Path("yolov8n.pt")

    print(f"Loading pretrained backbone from: {base_model_path}...")
    model = YOLO(str(base_model_path))

    print(f"\nStarting training with parameters:")
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
        name="roadwatch_pothole_model",
        save=True,
        plots=False,
        optimizer="auto",
        device=device
    )

    print("\nTraining completed successfully!")
    save_dir = Path(getattr(results, "save_dir", runs_dir / "roadwatch_pothole_model"))
    weights_path = save_dir / "weights" / "best.pt"
    if not weights_path.exists():
        weights_path = runs_dir / "roadwatch_pothole_model" / "weights" / "best.pt"
    dest_model = project_root / "ai" / "model" / "best.pt"

    if weights_path.exists():
        dest_model.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(str(weights_path), str(dest_model))
        print(f"Updated production model weights at: {dest_model.resolve()}")

    return results

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train Mysuru RoadWatch YOLO model for road defects, potholes, cracks, and pothole clusters")
    parser.add_argument("--epochs", type=int, default=15, help="Number of training epochs")
    parser.add_argument("--batch", type=int, default=8, help="Batch size")
    parser.add_argument("--imgsz", type=int, default=480, help="Input image size")
    parser.add_argument("--device", type=str, default="cpu", help="Compute device ('cpu' or '0')")
    parser.add_argument("--data", type=str, default=None, help="Path to dataset.yaml")
    parser.add_argument("--generate-dataset", action="store_true", help="Generate synthetic training dataset before training")
    args = parser.parse_args()

    train_yolo_roadwatch(
        epochs=args.epochs,
        batch=args.batch,
        imgsz=args.imgsz,
        device=args.device,
        dataset_yaml=args.data,
        generate_data=args.generate_dataset
    )
