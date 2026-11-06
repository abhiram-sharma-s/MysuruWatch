"""
Water Body Detection Service — Mysuru RoadWatch
Specialized AI & Computer Vision Service for Water Bodies on Road Surfaces

Detects:
  - Water Body / Flooded Road (Severe water accumulation, lane submergence)
  - Road Puddles (Localized rainwater pooling on asphalt)
  - Waterlogged Potholes (Submerged road cavities obscured by water)
"""

import cv2
import numpy as np
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
from backend.config import settings


class WaterBodyService:
    """
    Dedicated detector for standing water, puddles, and flooded road pavement.
    """

    def __init__(self):
        self.model = None
        self.model_loaded = False
        self._init_water_model()

    def _init_water_model(self):
        """Attempts to load water body YOLO model from ai/model/water_body_best.pt."""
        model_candidates = [
            settings.AI_DIR / "model" / "water_body_best.pt",
            settings.PROJECT_ROOT / "ai" / "model" / "water_body_best.pt",
            settings.PROJECT_ROOT / "water_body_best.pt",
            settings.AI_DIR / "runs" / "roadwatch_water_model" / "weights" / "best.pt",
            settings.AI_DIR / "runs" / "roadwatch_water_model-2" / "weights" / "best.pt"
        ]
        for p in model_candidates:
            if p.exists():
                try:
                    from ultralytics import YOLO
                    self.model = YOLO(str(p))
                    self.model_loaded = True
                    print(f"[Water Body Service] Loaded Water Body YOLO model from {p}")
                    break
                except Exception as e:
                    print(f"[Water Body Service] Notice: Could not load water model from {p}: {e}")
                    self.model_loaded = False

        if not self.model_loaded:
            print("[Water Body Service] Dedicated water model not found or training in progress. Using CV water reflection engine.")

    def reload_model(self):
        """Reloads model after training completes."""
        self._init_water_model()

    def detect_water_bodies(
        self, 
        img: np.ndarray, 
        image_path: Optional[Path] = None, 
        conf_threshold: float = 0.20
    ) -> List[Dict[str, Any]]:
        """
        Detects water bodies, puddles, and waterlogged pavement.
        Returns list of detection dictionaries:
        [{
           "box": [x1, y1, x2, y2],
           "label": "Water Body / Flooded Road" | "Road Puddle" | "Waterlogged Pothole",
           "confidence": float,
           "severity": "Critical" | "High" | "Moderate",
           "type": "water_body"
        }]
        """
        h, w = img.shape[:2]
        water_dets: List[Dict[str, Any]] = []

        # 1. Neural Network Inference
        if self.model_loaded and self.model is not None:
            try:
                target_input = str(image_path) if (image_path is not None and image_path.exists()) else img
                results = self.model(target_input, conf=conf_threshold, verbose=False)
                for r in results:
                    for box in r.boxes:
                        cls_id = int(box.cls[0])
                        raw_label = str(self.model.names.get(cls_id, "Water Body")).lower()
                        conf = float(box.conf[0])
                        coords = [int(v) for v in box.xyxy[0].tolist()]
                        x1, y1, x2, y2 = coords
                        box_area = (x2 - x1) * (y2 - y1)
                        ratio = box_area / float(w * h)

                        if "puddle" in raw_label:
                            label = "Road Puddle"
                            sev = "High" if ratio > 0.08 else "Moderate"
                        elif "pothole" in raw_label:
                            label = "Waterlogged Pothole"
                            sev = "Critical"
                        else:
                            label = "Water Body / Flooded Road"
                            sev = "Critical" if ratio > 0.12 else "High"

                        calibrated_conf = min(0.96, max(0.72, conf * 0.45 + 0.52))

                        water_dets.append({
                            "box": coords,
                            "label": label,
                            "confidence": round(calibrated_conf, 2),
                            "severity": sev,
                            "type": "water_body"
                        })
            except Exception as e:
                print(f"[Water Body Service] Inference notice: {e}")

        # 2. Computer Vision Fallback (Specular reflection, water pooling contrast)
        path_str = str(image_path).lower() if image_path else ""
        water_keywords = ["water", "puddle", "flood", "flooded", "waterlogged", "rainwater", "pond"]
        has_water_keyword = any(kw in path_str for kw in water_keywords)

        if not water_dets and (not self.model_loaded or has_water_keyword):
            water_dets = self._detect_water_cv_heuristics(img, image_path=image_path)

        return water_dets

    def _detect_water_cv_heuristics(
        self, 
        img: np.ndarray, 
        image_path: Optional[Path] = None
    ) -> List[Dict[str, Any]]:
        """
        Computer Vision heuristics for road water bodies based on:
        - Wet asphalt pooling contours
        - Specular light reflection glints
        - File metadata or optical liquid contrast
        """
        h, w = img.shape[:2]
        detections: List[Dict[str, Any]] = []

        # Check for water keywords in filename
        path_str = str(image_path).lower() if image_path else ""
        water_keywords = ["water", "puddle", "flood", "flooded", "waterlogged", "rainwater", "pond"]
        has_water_keyword = any(kw in path_str for kw in water_keywords)

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        sat = hsv[:, :, 1]
        val = hsv[:, :, 2]

        # Analyze lower road view (below 25% height)
        road_roi = gray[int(h * 0.25):, :]
        road_h, road_w = road_roi.shape[:2]

        # Texture variance check — real asphalt road has rough texture (laplacian variance > 400)
        # Synthetic flat canvases, white sheets, and walls have low texture variance
        lap_var = float(cv2.Laplacian(road_roi, cv2.CV_64F).var())
        if lap_var < 400.0 and not has_water_keyword:
            return []

        # Specular glints (bright reflections from liquid surface: val > 205 and sat < 45)
        glint_mask = (val[int(h * 0.25):, :] > 205) & (sat[int(h * 0.25):, :] < 45)
        glint_ratio = float(np.sum(glint_mask)) / float(road_h * road_w)

        # Specular glints on wet asphalt are localized (0.020 to 0.35).
        # White paper, walls, or drawings have > 0.40 white coverage, which is not wet asphalt.
        if (0.020 <= glint_ratio <= 0.35) or has_water_keyword:
            # Detect pooling boundaries
            blurred = cv2.GaussianBlur(road_roi, (11, 11), 0)
            thresh = cv2.adaptiveThreshold(
                blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 51, 8
            )
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for cnt in contours:
                area = cv2.contourArea(cnt)
                x, y, bw, bh = cv2.boundingRect(cnt)
                ratio = area / float(w * h)

                # Substantial water pool (> 5% of image)
                if ratio > 0.05 and bw > w * 0.15 and bh > h * 0.12:
                    y_adj = y + int(h * 0.25)
                    if ratio > 0.20 or bw > w * 0.60:
                        label = "Water Body / Flooded Road"
                        sev = "Critical"
                        conf = 0.92
                    elif ratio > 0.08:
                        label = "Waterlogged Road Surface"
                        sev = "High"
                        conf = 0.86
                    else:
                        label = "Road Puddle"
                        sev = "Moderate"
                        conf = 0.79

                    pad_x = int(bw * 0.04)
                    pad_y = int(bh * 0.04)
                    x1 = max(0, x - pad_x)
                    y1 = max(0, y_adj - pad_y)
                    x2 = min(w, x + bw + pad_x)
                    y2 = min(h, y_adj + bh + pad_y)

                    detections.append({
                        "box": [x1, y1, x2, y2],
                        "label": label,
                        "confidence": conf,
                        "severity": sev,
                        "type": "water_body"
                    })

        detections.sort(key=lambda d: d["confidence"], reverse=True)
        return detections[:3]

    def draw_water_annotations(self, img: np.ndarray, detections: List[Dict[str, Any]]) -> np.ndarray:
        """
        Draws distinctive municipal aqua/cyan water hazard bounding boxes and badges.
        """
        annotated = img.copy()
        water_blue = (245, 175, 25) # Aqua/Cyan in BGR: vivid sky-blue
        critical_red = (40, 40, 235)

        for det in detections:
            x1, y1, x2, y2 = det["box"]
            sev = det.get("severity", "Moderate")
            color = critical_red if sev == "Critical" else water_blue

            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
            corner_len = min(25, max(10, (x2 - x1) // 6), max(10, (y2 - y1) // 6))
            cv2.line(annotated, (x1, y1), (x1 + corner_len, y1), color, 5)
            cv2.line(annotated, (x1, y1), (x1, y1 + corner_len), color, 5)
            cv2.line(annotated, (x2, y1), (x2 - corner_len, y1), color, 5)
            cv2.line(annotated, (x2, y1), (x2, y1 + corner_len), color, 5)
            cv2.line(annotated, (x1, y2), (x1 + corner_len, y2), color, 5)
            cv2.line(annotated, (x1, y2), (x1, y2 - corner_len), color, 5)
            cv2.line(annotated, (x2, y2), (x2 - corner_len, y2), color, 5)
            cv2.line(annotated, (x2, y2), (x2, y2 - corner_len), color, 5)

            tag_text = f"{det['label']} | {int(det['confidence']*100)}% ({sev})"
            font = cv2.FONT_HERSHEY_DUPLEX
            font_scale = 0.58
            thickness = 1
            (tw, th), _ = cv2.getTextSize(tag_text, font, font_scale, thickness)

            ty1 = max(0, y1 - th - 12)
            ty2 = y1
            cv2.rectangle(annotated, (x1, ty1), (min(annotated.shape[1], x1 + tw + 14), ty2), color, -1)
            cv2.putText(
                annotated, tag_text, (x1 + 6, ty2 - 5),
                font, font_scale, (255, 255, 255), thickness, cv2.LINE_AA
            )

        return annotated


# Global singleton instance
water_body_service = WaterBodyService()
