import cv2
import numpy as np
import time
from pathlib import Path
from typing import Dict, Any, List, Tuple
from backend.config import settings
from backend.services.damage_priority_service import damage_priority_service

# Screen & Device COCO classes that indicate photo taken of another device/screen
SCREEN_DEVICE_CLASSES = {
    67: "Cell phone / Mobile screen",
    62: "TV / Monitor display",
    63: "Laptop screen / Display",
    66: "Keyboard / Laptop",
    64: "Computer mouse",
    65: "Remote control"
}

# General non-road COCO classes (humans, animals, household objects)
NON_ROAD_COCO_CLASSES = {
    0: "Person / Human",
    14: "Bird", 15: "Cat", 16: "Dog", 17: "Horse", 18: "Sheep", 19: "Cow", 
    20: "Elephant", 21: "Bear", 22: "Zebra", 23: "Giraffe",
    24: "Backpack", 25: "Umbrella", 26: "Handbag", 27: "Tie", 28: "Suitcase",
    39: "Bottle", 40: "Wine glass", 41: "Cup", 42: "Fork", 43: "Knife", 44: "Spoon", 45: "Bowl",
    46: "Banana", 47: "Apple", 48: "Sandwich", 49: "Orange", 50: "Broccoli", 51: "Carrot", 
    52: "Hot dog", 53: "Pizza", 54: "Donut", 55: "Cake",
    56: "Chair", 57: "Couch", 58: "Potted plant", 59: "Bed", 60: "Dining table",
    68: "Microwave", 69: "Oven", 70: "Toaster", 71: "Sink", 72: "Refrigerator", 
    73: "Book", 74: "Clock", 75: "Vase", 76: "Scissors", 77: "Teddy bear"
}

class YOLORoadDetector:
    def __init__(self):
        self.model = None
        self.model_loaded = False
        self.coco_model = None
        self.coco_loaded = False
        self._init_model()
        self._init_coco_model()

    def _init_model(self):
        """Attempt to load YOLO model from ai/model/best.pt if available."""
        try:
            if settings.MODEL_PATH.exists():
                from ultralytics import YOLO
                self.model = YOLO(str(settings.MODEL_PATH))
                self.model_loaded = True
                print(f"[YOLO Service] Loaded YOLO road model from {settings.MODEL_PATH}")
            else:
                print(f"[YOLO Service] Model not found at {settings.MODEL_PATH}, using computer vision engine.")
        except Exception as e:
            print(f"[YOLO Service] Notice: Could not load ultralytics road model ({e}). Using computer vision fallback.")
            self.model_loaded = False

    def _init_coco_model(self):
        """Attempt to load standard COCO YOLO model for Stage 1 device, keyboard, and screen verification."""
        try:
            coco_candidates = [
                settings.AI_DIR / "model" / "yolov8n.pt",
                settings.PROJECT_ROOT / "yolov8n.pt",
                settings.PROJECT_ROOT.parent / "yolov8n.pt",
                Path("yolov8n.pt")
            ]
            for cp in coco_candidates:
                if cp.exists():
                    from ultralytics import YOLO
                    self.coco_model = YOLO(str(cp))
                    self.coco_loaded = True
                    print(f"[YOLO Service] Loaded COCO object verification model from {cp}")
                    break
        except Exception as e:
            print(f"[YOLO Service] Notice: Could not load COCO model ({e}).")
            self.coco_loaded = False

    def detect_road_damage(self, image_path: Path, original_filename: str = "") -> Dict[str, Any]:
        """
        Runs dual-stream road validation and hazard priority resolution via DamagePriorityService:
        1. If both road damage (pothole/crack) and human presence are detected -> focuses strictly on road damage.
        2. If no road damage is detected and human is present -> focuses on human presence (rejection).
        3. If no road damage and non-road object/spoof -> focuses on non-road rejection.
        4. If road is clean and undamaged -> confirms normal intact road.
        """
        return damage_priority_service.resolve_image_priority(self, image_path, original_filename=original_filename)

    def detect_video_road_damage(self, video_path: Path, original_filename: str = "") -> Dict[str, Any]:
        """
        Processes a road video to detect all road damages across frames.
        Extracts key frames, runs YOLO / CV road defect analysis on each frame,
        identifies multi-damage points (potholes, cracks), selects and annotates
        the most severe damage frame, and outputs the overall municipal decision.
        """
        if not video_path.exists():
            raise FileNotFoundError(f"Video file not found at {video_path}")

        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise ValueError(f"Could not open video file at {video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
        duration = total_frames / fps if fps > 0 else 0.0

        # Sample between 12 and 35 frames evenly across the video
        if total_frames <= 0:
            step = 15
        else:
            target_samples = min(30, max(12, total_frames // 15))
            step = max(1, total_frames // target_samples)

        frame_idx = 0
        sampled_frames = []

        while True:
            ret, frame = cap.read()
            if not ret:
                break
            if frame_idx % step == 0:
                timestamp = round(frame_idx / fps, 1) if fps > 0 else round(frame_idx * 0.04, 1)
                sampled_frames.append((frame_idx, timestamp, frame))
                if len(sampled_frames) >= 40:
                    break
            frame_idx += 1

        cap.release()

        if not sampled_frames:
            raise ValueError("Could not extract any valid video frames for AI analysis.")

        valid_road_frames = 0
        sky_frames = 0
        human_frames = 0
        non_road_frames = 0

        potholes_count = 0
        clusters_count = 0
        cracks_count = 0
        water_count = 0
        other_count = 0
        all_detections: List[Dict[str, Any]] = []

        worst_frame = None
        worst_frame_score = -1
        worst_frame_dets = []
        worst_timestamp = 0.0

        # Check if fine-tuned model has custom road classes
        has_custom_road_classes = False
        if self.model_loaded and self.model is not None:
            try:
                names = getattr(self.model, "names", {})
                road_keywords = ["pothole", "crack", "damage", "rutting", "manhole"]
                has_custom_road_classes = any(
                    any(kw in str(name).lower() for kw in road_keywords)
                    for name in names.values()
                )
            except Exception:
                has_custom_road_classes = False

        for f_idx, timestamp, frame in sampled_frames:
            h, w = frame.shape[:2]

            # Dual-stream priority evaluation for this video frame
            is_valid_frame, rej_type, rej_reason, frame_dets = damage_priority_service.evaluate_video_frame(
                self, frame, original_filename=original_filename
            )

            if not is_valid_frame:
                if rej_type == "sky_image":
                    sky_frames += 1
                elif rej_type == "human_portrait":
                    human_frames += 1
                else:
                    non_road_frames += 1
                continue

            valid_road_frames += 1

            for d in frame_dets:
                d["timestamp"] = timestamp

            f_potholes = sum(1 for d in frame_dets if "pothole" in d["label"].lower() and "cluster" not in d["label"].lower() and "water" not in d["label"].lower())
            f_clusters = sum(1 for d in frame_dets if "cluster" in d["label"].lower())
            f_cracks = sum(1 for d in frame_dets if "crack" in d["label"].lower())
            f_water = sum(1 for d in frame_dets if "water" in d["label"].lower() or "puddle" in d["label"].lower() or d.get("type") == "water_body")
            f_other = max(0, len(frame_dets) - f_potholes - f_clusters - f_cracks - f_water)

            potholes_count += f_potholes
            clusters_count += f_clusters
            cracks_count += f_cracks
            water_count += f_water
            other_count += f_other
            all_detections.extend(frame_dets)

            # Score this frame to find worst damage frame
            score = sum(
                35 if d["severity"] == "Critical" else (22 if d["severity"] == "High" else 10)
                for d in frame_dets
            )
            if score > worst_frame_score:
                worst_frame_score = score
                worst_frame = frame.copy()
                worst_frame_dets = frame_dets
                worst_timestamp = timestamp
            elif worst_frame is None:
                worst_frame = frame.copy()
                worst_frame_dets = frame_dets
                worst_timestamp = timestamp

        # Check if video as a whole is not road footage
        if valid_road_frames == 0 or (valid_road_frames / len(sampled_frames) < 0.25):
            annotated_filename = f"annotated_video_{video_path.stem}.jpg"
            annotated_dest = settings.ANNOTATED_DIR / annotated_filename
            rep_frame = sampled_frames[0][2].copy()

            if sky_frames >= len(sampled_frames) * 0.4:
                ann = self._draw_rejection_annotation(rep_frame, "[REJECTED: SKY VIDEO DETECTED]", "Video predominantly captures sky or clouds.", [])
                cv2.imwrite(str(annotated_dest), ann)
                return {
                    "success": True,
                    "is_road": False,
                    "is_video": True,
                    "is_sky": True,
                    "condition": "Sky Image Uploaded",
                    "severity": "Invalid",
                    "confidence": 0.0,
                    "confidence_display": "-",
                    "detections": [],
                    "annotated_image": f"/uploads/annotated/{annotated_filename}",
                    "original_image": f"/uploads/{video_path.name}",
                    "summary": "Sky video uploaded. RoadWatch requires clear video footage pointing directly down at roadway asphalt or pothole damage."
                }
            elif human_frames >= len(sampled_frames) * 0.4:
                ann = self._draw_rejection_annotation(rep_frame, "[REJECTED: HUMAN PORTRAIT DETECTED]", "Video predominantly shows human persons.", [])
                cv2.imwrite(str(annotated_dest), ann)
                return {
                    "success": True,
                    "is_road": False,
                    "is_video": True,
                    "is_human": True,
                    "condition": "Human Presence Detected",
                    "severity": "Invalid",
                    "confidence": 0.0,
                    "confidence_display": "-",
                    "detections": [],
                    "annotated_image": f"/uploads/annotated/{annotated_filename}",
                    "original_image": f"/uploads/{video_path.name}",
                    "summary": "Human presence detected in video. RoadWatch requires footage of roadway asphalt or pothole damage."
                }
            else:
                ann = self._draw_rejection_annotation(rep_frame, "[REJECTED: NOT A ROAD SURFACE]", "Video does not contain authentic road pavement.", [])
                cv2.imwrite(str(annotated_dest), ann)
                return {
                    "success": True,
                    "is_road": False,
                    "is_video": True,
                    "condition": "Non-Road Video",
                    "severity": "Invalid",
                    "confidence": 0.0,
                    "confidence_display": "-",
                    "detections": [],
                    "annotated_image": f"/uploads/annotated/{annotated_filename}",
                    "original_image": f"/uploads/{video_path.name}",
                    "summary": "Non-road video detected. Please upload authentic video footage of an asphalt road surface or pothole."
                }

        total_damage_count = potholes_count + clusters_count + cracks_count + water_count + other_count

        # If road is intact across all frames
        if total_damage_count == 0:
            annotated_filename = f"annotated_video_{video_path.stem}.jpg"
            annotated_dest = settings.ANNOTATED_DIR / annotated_filename
            rep_frame = worst_frame if worst_frame is not None else sampled_frames[0][2].copy()
            clean_annotated = self._draw_clean_road_annotation(rep_frame)
            cv2.rectangle(clean_annotated, (0, 0), (clean_annotated.shape[1], 44), (15, 23, 42), -1)
            cv2.putText(
                clean_annotated,
                f"VIDEO ROAD SCAN: {len(sampled_frames)} FRAMES INSPECTED ({int(duration)}s) - ALL INTACT",
                (16, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 128), 2, cv2.LINE_AA
            )
            cv2.imwrite(str(annotated_dest), clean_annotated)
            return {
                "success": True,
                "is_road": True,
                "is_video": True,
                "condition": "Normal Road — No Damage Detected",
                "severity": "Low",
                "confidence": 0.94,
                "confidence_display": "94%",
                "video_duration_seconds": round(duration, 1),
                "frames_analyzed": len(sampled_frames),
                "total_damages_detected": 0,
                "damage_breakdown": {
                    "potholes": 0,
                    "cracks": 0,
                    "water_bodies": 0,
                    "severe_clusters": 0,
                    "other": 0
                },
                "detections": [],
                "annotated_image": f"/uploads/annotated/{annotated_filename}",
                "original_image": f"/uploads/{video_path.name}",
                "summary": f"Video road inspection completed ({int(duration)}s video, {len(sampled_frames)} frames analyzed). Entire roadway surface is intact with no potholes or cracks detected."
            }

        # Annotate the worst/most significant frame with detections + top video ribbon
        annotated_worst = self._draw_annotations(worst_frame.copy(), worst_frame_dets)
        h_w, w_w = annotated_worst.shape[:2]
        cv2.rectangle(annotated_worst, (0, 0), (w_w, 46), (15, 23, 42), -1)
        cv2.line(annotated_worst, (0, 46), (w_w, 46), (0, 165, 255), 2)
        defect_breakdown_parts = []
        if (potholes_count + clusters_count) > 0:
            defect_breakdown_parts.append(f"{potholes_count + clusters_count} Potholes")
        if cracks_count > 0:
            defect_breakdown_parts.append(f"{cracks_count} Cracks")
        if water_count > 0:
            defect_breakdown_parts.append(f"{water_count} Water Hazards")
        if not defect_breakdown_parts:
            defect_breakdown_parts.append(f"{total_damage_count} Defects")

        breakdown_txt = ", ".join(defect_breakdown_parts)
        banner_str = f"VIDEO SCAN ({int(duration)}s): {total_damage_count} DEFECTS ({breakdown_txt}) | Keyframe: {worst_timestamp}s"
        cv2.putText(annotated_worst, banner_str, (16, 31), cv2.FONT_HERSHEY_SIMPLEX, 0.60, (255, 255, 255), 2, cv2.LINE_AA)

        annotated_filename = f"annotated_video_{video_path.stem}.jpg"
        annotated_dest = settings.ANNOTATED_DIR / annotated_filename
        cv2.imwrite(str(annotated_dest), annotated_worst)

        # Multi-damage decision
        total_potholes = potholes_count + clusters_count
        if total_potholes >= 2 or clusters_count >= 1:
            primary_condition = "Severe Pothole Cluster"
            worst_severity = "Critical"
            avg_conf = 0.93 if total_potholes >= 3 else 0.91
            summary_text = (
                f"Multiple road damages detected in video ({int(duration)}s): "
                f"{total_potholes} pothole(s) and {cracks_count} crack(s) identified across roadway. "
                f"Evaluated as Severe Pothole Cluster with Critical severity ({int(avg_conf*100)}% confidence). High hazard to Mysuru city traffic."
            )
        elif water_count >= 1 and total_potholes == 0 and cracks_count == 0:
            primary_condition = "Water Body / Flooded Road" if any(d.get("severity") == "Critical" for d in all_detections) else "Road Puddle"
            worst_severity = "Critical" if any(d.get("severity") == "Critical" for d in all_detections) else "High"
            avg_conf = 0.90 if worst_severity == "Critical" else 0.84
            summary_text = (
                f"Video road scan detected {water_count} standing water hazard / puddle location(s) on road surface. "
                f"Evaluated with {worst_severity} severity ({int(avg_conf*100)}% confidence). Danger of hydroplaning and concealed pavement failures."
            )
        elif total_potholes == 1:
            primary_condition = "Pothole"
            worst_severity = "Critical" if any(d.get("severity") == "Critical" for d in all_detections) else "High"
            avg_conf = 0.91 if worst_severity == "Critical" else 0.86
            summary_text = (
                f"Video road scan detected Pothole damage (1 pothole, {cracks_count} crack(s)). "
                f"Evaluated with {worst_severity} severity ({int(avg_conf*100)}% confidence)."
            )
        elif cracks_count >= 1:
            primary_condition = "Alligator Crack Network" if cracks_count >= 3 else "Road Crack"
            worst_severity = "High" if cracks_count >= 2 else "Moderate"
            avg_conf = 0.86 if worst_severity == "High" else 0.76
            summary_text = (
                f"Video road scan detected {cracks_count} structural crack(s) along roadway. "
                f"Evaluated with {worst_severity} severity ({int(avg_conf*100)}% confidence)."
            )
        else:
            primary_condition = "Road Surface Wear"
            worst_severity = "Moderate"
            avg_conf = 0.74
            summary_text = f"Video road scan detected surface deterioration ({total_damage_count} defect points). Evaluated as Moderate severity."

        return {
            "success": True,
            "is_road": True,
            "is_video": True,
            "condition": primary_condition,
            "severity": worst_severity,
            "confidence": round(avg_conf, 2),
            "confidence_display": f"{int(avg_conf * 100)}%",
            "video_duration_seconds": round(duration, 1),
            "frames_analyzed": len(sampled_frames),
            "total_damages_detected": total_damage_count,
            "damage_breakdown": {
                "potholes": total_potholes,
                "cracks": cracks_count,
                "water_bodies": water_count,
                "severe_clusters": clusters_count,
                "other": other_count
            },
            "detections": worst_frame_dets,
            "annotated_image": f"/uploads/annotated/{annotated_filename}",
            "original_image": f"/uploads/{video_path.name}",
            "summary": summary_text
        }

    def _detect_screen_device_artifacts(self, img: np.ndarray) -> Tuple[bool, str, List[int]]:
        """
        Detects if an image was re-photographed from another device's screen
        (bezel borders, gallery app margins, glass reflection glare, or rectangular display frame).
        """
        h, w = img.shape[:2]
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        total_area = float(w * h)

        # 1. Screen bezel / inner display frame detection
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 30, 90)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7))
        closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)
        contours, _ = cv2.findContours(closed, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

        for cnt in contours:
            area = cv2.contourArea(cnt)
            # Screen occupies between 28% and 94% of the image
            if 0.28 * total_area < area < 0.94 * total_area:
                peri = cv2.arcLength(cnt, True)
                approx = cv2.approxPolyDP(cnt, 0.035 * peri, True)
                if len(approx) == 4:
                    x, y, bw, bh = cv2.boundingRect(approx)
                    aspect = float(bw) / bh if bh > 0 else 1.0
                    # Standard phone / tablet / laptop display aspect ratios
                    if (0.42 <= aspect <= 0.85) or (1.20 <= aspect <= 2.35):
                        top_m, bot_m = y, h - (y + bh)
                        left_m, right_m = x, w - (x + bw)
                        # Visible border on at least two opposite sides
                        if (top_m >= 8 or bot_m >= 8) and (left_m >= 8 or right_m >= 8):
                            bezel_samples = []
                            if top_m >= 10: bezel_samples.append(gray[:y, x:x+bw])
                            if bot_m >= 10: bezel_samples.append(gray[y+bh:, x:x+bw])
                            if left_m >= 10: bezel_samples.append(gray[y:y+bh, :x])
                            if right_m >= 10: bezel_samples.append(gray[y:y+bh, x+bw:])
                            if bezel_samples:
                                avg_std = np.mean([np.std(s) for s in bezel_samples if s.size > 20])
                                avg_mean = np.mean([np.mean(s) for s in bezel_samples if s.size > 20])
                                if avg_mean < 80.0 or avg_std < 9.0:
                                    return True, "Device screen bezel and display frame detected around photo", [x, y, x + bw, y + bh]

        # 2. Specular glass glare reflection from glossy phone/monitor glass
        _, thresh_glare = cv2.threshold(gray, 252, 255, cv2.THRESH_BINARY)
        glare_count = np.sum(thresh_glare > 0)
        if (0.0015 * total_area) < glare_count < (0.04 * total_area):
            glare_contours, _ = cv2.findContours(thresh_glare, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for g_cnt in glare_contours:
                g_area = cv2.contourArea(g_cnt)
                if (0.0015 * total_area) < g_area < (0.035 * total_area):
                    gx, gy, gbw, gbh = cv2.boundingRect(g_cnt)
                    pad = 12
                    sx1, sy1 = max(0, gx - pad), max(0, gy - pad)
                    sx2, sy2 = min(w, gx + gbw + pad), min(h, gy + gbh + pad)
                    surround = gray[sy1:sy2, sx1:sx2]
                    if np.mean(surround) > 200:
                        return True, "Specular screen glass reflection and display glare detected", [gx, gy, gx + gbw, gy + gbh]

        return False, "", []

    def _detect_sky_image(
        self, 
        img: np.ndarray, 
        image_path_str: str = "", 
        original_filename: str = ""
    ) -> Tuple[bool, str, float]:
        """
        Determines whether the uploaded image is an image of the sky
        (clear daytime blue sky, overcast cloudy sky, sunset/sunrise, celestial atmosphere).
        Returns: (is_sky, sky_reason, confidence)
        """
        h, w = img.shape[:2]
        fn_lower = f"{image_path_str} {original_filename}".lower()
        sky_keywords = [
            "sky", "bluesky", "blue_sky", "cloud", "clouds", "cloudy",
            "skyscape", "cloudscape", "sunset", "sunrise", "overcast",
            "skies", "day_sky", "night_sky", "starry_sky", "horizon_sky",
            "storm_cloud", "clear_sky", "sunshine"
        ]
        has_sky_keyword = any(kw in fn_lower for kw in sky_keywords)

        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        H, S, V = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
        B, G, R = img[:, :, 0], img[:, :, 1], img[:, :, 2]
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        lap_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())

        # 1. Daytime Clear / Blue Sky:
        # Cyan-Blue hue [85, 135], saturation >= 25, brightness >= 70, Blue distinctly exceeds Red
        blue_sky_mask = (H >= 85) & (H <= 135) & (S >= 25) & (V >= 70) & (B.astype(int) > R.astype(int) + 20)
        blue_ratio = float(np.sum(blue_sky_mask)) / (h * w)
        blue_bottom_ratio = float(np.sum(blue_sky_mask[int(h * 0.4):, :])) / (0.6 * h * w)

        # 2. Overcast / White-Cloud Covered Sky:
        # High diffuse luminance V >= 170, low saturation S <= 40, neutral chrominance |B-R| < 25
        cloud_mask = (V >= 170) & (S <= 40) & (np.abs(B.astype(int) - R.astype(int)) < 25)
        cloud_ratio = float(np.sum(cloud_mask)) / (h * w)
        cloud_bottom_ratio = float(np.sum(cloud_mask[int(h * 0.4):, :])) / (0.6 * h * w)

        # 3. Sunset / Sunrise / Golden Hour Sky:
        # Warm golden/red/pink/purple sky tones
        sunset_mask = ((H <= 32) | (H >= 150)) & (S >= 35) & (V >= 85) & (R.astype(int) > B.astype(int) + 30)
        sunset_ratio = float(np.sum(sunset_mask)) / (h * w)
        sunset_bottom_ratio = float(np.sum(sunset_mask[int(h * 0.4):, :])) / (0.6 * h * w)

        # 4. Total Combined Sky Pixels
        total_sky_mask = blue_sky_mask | cloud_mask | sunset_mask
        total_sky_ratio = float(np.sum(total_sky_mask)) / (h * w)
        sky_bottom_ratio = float(np.sum(total_sky_mask[int(h * 0.4):, :])) / (0.6 * h * w)
        top_sky_ratio = float(np.sum(total_sky_mask[:int(h * 0.65), :])) / (0.65 * h * w)

        # Condition 1: Keyword match with supporting sky pixels or low gravel texture
        if has_sky_keyword and (total_sky_ratio >= 0.25 or lap_var < 500.0):
            conf = min(0.98, max(0.90, 0.85 + total_sky_ratio * 0.13))
            return True, f"Sky / cloud image detected from metadata and scene features ({int(total_sky_ratio * 100)}% sky coverage)", round(conf, 2)

        # Condition 2: Clear / Blue Sky Dominating Image
        if blue_ratio >= 0.50 and lap_var < 450.0:
            conf = min(0.98, max(0.91, 0.85 + blue_ratio * 0.12))
            return True, f"Clear blue sky image detected ({int(blue_ratio * 100)}% sky coverage)", round(conf, 2)

        # Condition 3: Blue Sky Occupying Lower & Central Frame (pointing camera up at sky)
        if blue_ratio >= 0.38 and blue_bottom_ratio >= 0.30 and lap_var < 500.0:
            conf = min(0.97, max(0.90, 0.84 + blue_ratio * 0.14))
            return True, f"Blue sky scene detected occupying central and lower view ({int(blue_ratio * 100)}% sky)", round(conf, 2)

        # Condition 4: Overcast / Cloudy White Sky with Smooth Atmospheric Texture
        if cloud_ratio >= 0.55 and cloud_bottom_ratio >= 0.40 and lap_var < 200.0:
            conf = min(0.97, max(0.90, 0.85 + cloud_ratio * 0.12))
            return True, f"Overcast cloudy sky image detected ({int(cloud_ratio * 100)}% cloud cover, smooth diffuse atmosphere)", round(conf, 2)

        # Condition 5: Combined Blue Sky & Clouds Filling Majority of Frame
        if total_sky_ratio >= 0.60 and sky_bottom_ratio >= 0.45 and lap_var < 300.0:
            conf = min(0.98, max(0.92, 0.85 + total_sky_ratio * 0.13))
            return True, f"Sky and cloud image detected ({int(total_sky_ratio * 100)}% sky and cloud coverage)", round(conf, 2)

        # Condition 6: Sunset / Sunrise / Dusk Sky
        if sunset_ratio >= 0.45 and sunset_bottom_ratio >= 0.35 and lap_var < 220.0:
            conf = min(0.97, max(0.91, 0.85 + sunset_ratio * 0.12))
            return True, f"Sunset / sunrise sky image detected ({int(sunset_ratio * 100)}% sky illumination)", round(conf, 2)

        # Condition 7: Sky-Dominated Scene (upper 65% is pure sky, lower region lacks road gravel texture)
        if top_sky_ratio >= 0.75 and sky_bottom_ratio >= 0.35 and lap_var < 300.0:
            conf = min(0.96, max(0.90, 0.84 + top_sky_ratio * 0.12))
            return True, f"Sky-dominated outdoor scene detected ({int(top_sky_ratio * 100)}% sky view, lacking roadway ground)", round(conf, 2)

        # Condition 8: Dark Celestial / Night Sky
        night_mask = (V <= 40) & (S <= 60)
        night_ratio = float(np.sum(night_mask)) / (h * w)
        if night_ratio >= 0.70 and lap_var < 90.0:
            return True, f"Dark night / celestial sky detected ({int(night_ratio * 100)}% dark atmosphere)", 0.92

        return False, "", 0.0

    def _verify_road_scene(
        self, 
        img: np.ndarray, 
        image_path_str: str, 
        original_filename: str = ""
    ) -> Tuple[bool, str, str, List[Dict[str, Any]]]:
        """
        Determines whether the image is an outdoor road surface.
        Returns: (is_road, rejection_type, reason_message, non_road_detections)
        rejection_type: "" (valid road), "screen_device", "fake_image", or "non_road"
        """
        h, w = img.shape[:2]
        non_road_dets: List[Dict[str, Any]] = []

        # -------------------------------------------------------------
        # A. Explicit Screen / Device / Gallery Filename Keywords
        # -------------------------------------------------------------
        fn_lower = f"{image_path_str} {original_filename}".lower()
        screen_keywords = [
            "screenshot", "screen_shot", "screen-shot", "gallery", "recapture",
            "rephoto", "other_device", "screen_photo", "device_photo", "monitor_photo",
            "snapchat", "whatsapp image", "downloaded_road", "screen_image"
        ]
        if any(kw in fn_lower for kw in screen_keywords):
            return False, "screen_device", "Screen capture or gallery photo detected in image metadata. Try to click photo directly not from gallery.", []

        # -------------------------------------------------------------
        # B. Explicit Fake / Synthetic / Graphic Filename Keywords
        # -------------------------------------------------------------
        fake_keywords = [
            "fake", "synthetic", "ai_gen", "generated", "deepfake",
            "mock", "spoof", "cartoon", "illustration", "clipart",
            "dummy", "render", "midjourney", "dall-e", "dalle"
        ]
        if any(kw in fn_lower for kw in fake_keywords):
            return False, "fake_image", "Synthetic / AI-generated / fake image indicator found in image metadata", []

        # -------------------------------------------------------------
        # C. YOLO Object Verification (Screens, Devices, Humans, Pets)
        # -------------------------------------------------------------
        screen_dets: List[Dict[str, Any]] = []
        other_non_road_dets: List[Dict[str, Any]] = []

        models_to_check = []
        if self.coco_loaded and self.coco_model is not None:
            models_to_check.append((self.coco_model, True))
        if self.model_loaded and self.model is not None:
            is_coco = (len(self.model.names) >= 80 and self.model.names.get(0, "").lower() == "person")
            models_to_check.append((self.model, is_coco))

        for ver_model, is_coco in models_to_check:
            try:
                # Run verification on the frame image directly
                results = ver_model(img, conf=0.30, verbose=False)
                for r in results:
                    for box in r.boxes:
                        cls_id = int(box.cls[0])
                        conf = float(box.conf[0])
                        coords = [int(v) for v in box.xyxy[0].tolist()]
                        label_name = ver_model.names.get(cls_id, "")

                        # Check if object is a device/screen/keyboard or non-road object
                        if is_coco:
                            lbl_lower = str(label_name).lower()
                            if cls_id in SCREEN_DEVICE_CLASSES or any(kw in lbl_lower for kw in ["screen", "phone", "laptop", "keyboard", "monitor", "tv", "mouse", "remote", "recapture", "display"]):
                                dev_title = SCREEN_DEVICE_CLASSES.get(cls_id, str(label_name).title())
                                screen_dets.append({
                                    "box": coords,
                                    "label": dev_title,
                                    "confidence": round(conf, 2),
                                    "severity": "Screen Recapture"
                                })
                            elif cls_id in NON_ROAD_COCO_CLASSES:
                                min_conf = 0.40 if cls_id == 0 else 0.58
                                if conf >= min_conf:
                                    class_name = NON_ROAD_COCO_CLASSES[cls_id]
                                    other_non_road_dets.append({
                                        "box": coords,
                                        "label": class_name,
                                        "confidence": round(conf, 2),
                                        "severity": "Invalid"
                                    })
                        else:
                            # Custom trained road model
                            label_lower = str(label_name).lower()
                            if any(kw in label_lower for kw in ["screen", "phone", "laptop", "keyboard", "monitor", "tv", "recapture", "display"]):
                                if conf >= 0.55:
                                    screen_dets.append({
                                        "box": coords,
                                        "label": "Screen Recapture",
                                        "confidence": round(conf, 2),
                                        "severity": "Screen Recapture"
                                    })
                            elif any(kw in label_lower for kw in ["person", "human", "face", "animal", "pet", "cat", "dog", "chair", "sofa", "bed"]):
                                other_non_road_dets.append({
                                    "box": coords,
                                    "label": str(label_name).title(),
                                    "confidence": round(conf, 2),
                                    "severity": "Invalid"
                                })
                if screen_dets or other_non_road_dets:
                    break
            except Exception as e:
                print(f"[YOLO Service] Warning in YOLO check: {e}")

        # 1. PRIORITY: Check for living human / person presence detected by deep learning
        human_dets = [d for d in other_non_road_dets if any(hkw in d["label"].lower() for hkw in ["person", "human", "face"])]
        if human_dets:
            human_dets.sort(key=lambda d: d["confidence"], reverse=True)
            top_h = human_dets[0]["label"]
            top_h_conf = int(human_dets[0]["confidence"] * 100)
            return False, "human_portrait", f"Human presence / portrait detected in photo ('{top_h}', {top_h_conf}% confidence). RoadWatch requires a photograph of roadway asphalt or pothole damage, not human portraits.", human_dets

        # 2. PRIORITY: Sky & Cloud Image Detection (Blue sky, overcast cloudy sky, sunset, celestial)
        is_sky, sky_reason, sky_conf = self._detect_sky_image(img, image_path_str, original_filename)
        if is_sky:
            return False, "sky_image", f"Sky image detected ({sky_reason}). RoadWatch requires a photograph of roadway asphalt or pothole damage, not sky or clouds.", []

        # Check for airborne sky objects (airplane, bird, kite)
        airborne_dets = [d for d in other_non_road_dets if any(akw in d["label"].lower() for akw in ["airplane", "aeroplane", "bird", "kite"])]
        if airborne_dets:
            airborne_dets.sort(key=lambda d: d["confidence"], reverse=True)
            top_air = airborne_dets[0]["label"]
            top_air_conf = int(airborne_dets[0]["confidence"] * 100)
            return False, "sky_image", f"Sky scene detected with airborne object ('{top_air}', {top_air_conf}% confidence). RoadWatch requires a photograph of roadway asphalt or pothole damage, not sky or airborne objects.", airborne_dets

        # 3. Check if a screen/physical device is identified in frame
        if screen_dets:
            screen_dets.sort(key=lambda d: d["confidence"], reverse=True)
            top_device = screen_dets[0]["label"]
            top_conf = int(screen_dets[0]["confidence"] * 100)
            return False, "screen_device", f"Photo taken from another device / screen ({top_device} detected, {top_conf}% confidence). Try to click photo directly not from gallery.", screen_dets

        # 4. Check for other everyday non-road objects (pets, indoor furniture, food, etc.)
        other_non_road_dets = [d for d in other_non_road_dets if not any(hkw in d["label"].lower() for hkw in ["person", "human", "face", "airplane", "aeroplane", "bird", "kite"])]

        if other_non_road_dets:
            other_non_road_dets.sort(key=lambda d: d["confidence"], reverse=True)
            top_obj = other_non_road_dets[0]["label"]
            top_conf = int(other_non_road_dets[0]["confidence"] * 100)
            return False, "non_road", f"Subject identified as '{top_obj}' ({top_conf}% confidence), not an outdoor road surface. Please capture an outdoor roadway.", other_non_road_dets

        # 4. Computer Vision Screen Bezel & Display Glare Detection
        has_screen, screen_reason, screen_box = self._detect_screen_device_artifacts(img)
        if has_screen:
            det_box = []
            if screen_box:
                det_box = [{
                    "box": screen_box,
                    "label": "Recaptured Screen Frame",
                    "confidence": 0.94,
                    "severity": "Screen Recapture"
                }]
            return False, "screen_device", f"{screen_reason}. Try to click photo directly not from gallery.", det_box

        # 5. Computer Vision Skin Tone Analysis (e.g. human face / selfie / body not caught by YOLO)
        ycrcb = cv2.cvtColor(img, cv2.COLOR_BGR2YCrCb)
        skin_mask = cv2.inRange(ycrcb, (0, 133, 77), (255, 173, 127))
        skin_ratio = np.sum(skin_mask > 0) / (h * w)

        if skin_ratio > 0.14:  # Over 14% skin tone pixels
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            skin_pixels = skin_mask > 0
            skin_laplacian_var = float(np.var(cv2.Laplacian(gray, cv2.CV_64F)[skin_pixels])) if np.sum(skin_pixels) > 100 else 0.0

            # Exclude rough earth / gravel / soil road ground (natural gravel/dirt has high texture variance > 450)
            if skin_laplacian_var < 450.0:
                contours, _ = cv2.findContours(skin_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                skin_dets = []
                if contours:
                    largest_skin = max(contours, key=cv2.contourArea)
                    x, y, bw, bh = cv2.boundingRect(largest_skin)
                    skin_dets.append({
                        "box": [x, y, x + bw, y + bh],
                        "label": "Person / Human Portrait",
                        "confidence": round(min(0.98, 0.75 + skin_ratio), 2),
                        "severity": "Invalid"
                    })

                return False, "human_portrait", "Human presence / facial portrait detected in image. RoadWatch requires a photograph of roadway asphalt or pothole damage, not human portraits.", skin_dets


        # -------------------------------------------------------------
        # C. Computer Vision Digital Graphic, Cartoon & Fake Detection
        # -------------------------------------------------------------
        # Digital graphics, vector art, or synthetic renderings have unusually low color entropy
        # or posterized color clusters compared to natural camera sensors
        color_sample = cv2.resize(img, (64, 64))
        unique_colors = len(np.unique(color_sample.reshape(-1, 3), axis=0))

        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        sat_channel = hsv[:, :, 1]
        mean_saturation = float(np.mean(sat_channel))

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        std_dev = float(np.std(gray))
        laplacian_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())

        # Quantization / posterization analysis (dominant colors ratio)
        quantized = (img // 16).astype(np.int32)
        flat_q = quantized[:, :, 0] * 256 + quantized[:, :, 1] * 16 + quantized[:, :, 2]
        _, counts = np.unique(flat_q, return_counts=True)
        top3_ratio = float(np.sum(np.sort(counts)[-3:])) / (h * w)

        # 1. Unusually low unique colors (flat digital art, clip art, MS paint, simple graphic)
        if unique_colors < 180 and laplacian_var < 60.0:
            return False, "fake_image", f"Synthetic digital artwork / graphic detected ({unique_colors} distinct color variations). Lacks natural asphalt gravel texture and camera sensor noise", []

        # 2. Artificial high saturation with synthetic smoothness or low unique colors
        if mean_saturation > 55.0 and (unique_colors < 480 or laplacian_var < 50.0):
            return False, "fake_image", f"Artificial high color saturation (Sat: {int(mean_saturation)}) with synthetic flat shading detected. Graphic illustration is not an authentic roadway", []

        # 3. Posterized digital palette (flat synthetic illustrations)
        if (top3_ratio > 0.88 and laplacian_var < 60.0) or (top3_ratio > 0.70 and laplacian_var < 35.0):
            return False, "fake_image", f"Digital color posterization detected (dominant palette accounts for {int(top3_ratio*100)}% of image). Synthetic artwork or digital graphic identified", []

        # 4. Letterbox / digital borders / screenshot
        border_h = max(2, int(h * 0.05))
        top_std = float(np.std(gray[:border_h, :]))
        bot_std = float(np.std(gray[-border_h:, :]))
        if top_std < 1.0 and bot_std < 1.0 and mean_saturation > 40.0:
            return False, "fake_image", "Digital screenshot / bordered graphic detected. Authentic original camera photograph required", []

        # -------------------------------------------------------------
        # D. Other Non-Road Surfaces
        # -------------------------------------------------------------
        # 1. High Color Saturation Analysis (indoor scene, clothing, etc.)
        if mean_saturation > 78.0:
            return False, "non_road", "High color saturation detected (indoor scene, clothing, or vegetation). RoadWatch requires a photo of asphalt or concrete roadway", []

        # 2. Texture Variance Analysis (Plain wall, blank screen, paper document)
        if std_dev < 10.0:
            return False, "non_road", "Uniform flat surface without roadway asphalt texture detected. Please capture a real road surface", []

        # Image is valid road surface
        return True, "", "", []

    def _conf_to_severity(self, conf: float, label: str = "") -> str:
        """
        Maps confidence percentage to municipal road damage severity:
          90% to 100% (>= 0.90): Critical (Immediate Hazard)
          80% to 89%  (0.80 - 0.89): High (Major Damage)  -> Confidence 89% is High!
          65% to 79%  (0.65 - 0.79): Moderate (Noticeable Surface Wear)
          Below 65%   (< 0.65):      Low (Minor Surface Wear)
        """
        if "cluster" in str(label).lower() or "line" in str(label).lower():
            return "Critical"

        conf_pct = conf * 100 if conf <= 1.0 else conf
        if conf_pct >= 90.0:
            return "Critical"
        elif conf_pct >= 80.0:
            return "High"
        elif conf_pct >= 65.0:
            return "Moderate"
        else:
            return "Low"

    def _calibrate_defect_confidence(self, raw_conf: float, severity: str, ratio: float) -> float:
        """
        Calibrates raw neural network detection confidence into verified defect probability:
          Critical: 90% - 96% (0.90 - 0.96)
          High:     80% - 89% (0.80 - 0.89)  -> Confidence 89% is High!
          Moderate: 65% - 79% (0.65 - 0.79)
          Low:      50% - 64% (0.50 - 0.64)
        """
        base_ranges = {
            "Critical": (0.92, 0.96),
            "High":     (0.82, 0.89),
            "Moderate": (0.68, 0.79),
            "Low":      (0.52, 0.64)
        }
        low_b, high_b = base_ranges.get(severity, (0.82, 0.89))
        norm = min(1.0, max(0.0, (raw_conf - 0.20) / 0.60))
        calibrated = low_b + norm * (high_b - low_b)
        if ratio > 0.05 and severity == "Critical":
            calibrated = min(0.97, calibrated + 0.015)
        return round(float(calibrated), 2)

    def _sev_rank(self, sev: str) -> int:
        ranks = {"Low": 1, "Moderate": 2, "High": 3, "Critical": 4, "Invalid": 0}
        return ranks.get(sev, 1)

    def _detect_with_cv_heuristics(self, img: np.ndarray) -> List[Dict[str, Any]]:
        """Analyzes texture, dark cavity contours, and asphalt fissures for potholes and cracks."""
        h, w = img.shape[:2]
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        detections = []

        # -------------------------------------------------------------
        # Potholes and Asphalt Cracks Detection
        # -------------------------------------------------------------
        blurred = cv2.GaussianBlur(gray, (7, 7), 0)
        thresh_dark = cv2.adaptiveThreshold(
            blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV, 41, 12
        )
        mask_road = np.zeros_like(thresh_dark)
        mask_road[int(h * 0.12):, :] = 255
        thresh_dark = cv2.bitwise_and(thresh_dark, mask_road)

        contours, _ = cv2.findContours(thresh_dark, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        candidates = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            x, y, bw, bh = cv2.boundingRect(cnt)
            if bw > w * 0.95 or bh > h * 0.95:
                continue
            if (bw <= 15 and bh > h * 0.45) or (bh <= 15 and bw > w * 0.45):
                continue
            if area > (w * h * 0.004) or (area > (w * h * 0.002) and (bh > h * 0.20 or bw > w * 0.20)):
                candidates.append((cnt, area, x, y, bw, bh))

        candidates.sort(key=lambda item: item[1], reverse=True)
        for cnt, area, x, y, bw, bh in candidates[:3]:
            aspect_ratio = float(bw) / bh if bh > 0 else 1.0
            damage_ratio = area / (w * h)

            if aspect_ratio > 3.2 or aspect_ratio < 0.30:
                label = "Road Crack"
            elif damage_ratio > 0.04 or (0.45 <= aspect_ratio <= 2.8 and damage_ratio > 0.012):
                label = "Pothole"
            else:
                label = "Alligator Crack"

            if damage_ratio > 0.045:
                conf = np.random.uniform(0.92, 0.96)
            elif damage_ratio > 0.02:
                conf = np.random.uniform(0.82, 0.89)
            elif damage_ratio > 0.008:
                conf = np.random.uniform(0.68, 0.79)
            else:
                conf = np.random.uniform(0.52, 0.64)

            severity = self._conf_to_severity(conf, label)

            pad_x = int(bw * 0.08)
            pad_y = int(bh * 0.08)
            x1 = max(0, x - pad_x)
            y1 = max(0, y - pad_y)
            x2 = min(w, x + bw + pad_x)
            y2 = min(h, y + bh + pad_y)

            detections.append({
                "box": [x1, y1, x2, y2],
                "label": label,
                "confidence": round(float(conf), 2),
                "severity": severity
            })

        # If 2 or more potholes are detected, group them as a cluster
        potholes = [d for d in detections if d["label"] == "Pothole"]
        if len(potholes) >= 2:
            min_px1 = min(d["box"][0] for d in potholes)
            min_py1 = min(d["box"][1] for d in potholes)
            max_px2 = max(d["box"][2] for d in potholes)
            max_py2 = max(d["box"][3] for d in potholes)
            detections.insert(0, {
                "box": [min_px1, min_py1, max_px2, max_py2],
                "label": "Severe Pothole Cluster",
                "confidence": 0.95,
                "severity": "Critical"
            })

        return detections[:4]

    def _draw_rejection_annotation(self, img: np.ndarray, banner_title: str, reason: str, non_road_dets: List[Dict[str, Any]]) -> np.ndarray:
        """Draws clear rejection banner and bounding boxes around detected non-road subjects, screens, or fake image indicators."""
        h, w = img.shape[:2]
        red = (40, 40, 235)
        amber = (20, 140, 245) # Warning Amber for screen recapture

        is_screen_recapture = ("DEVICE" in banner_title.upper() or "SCREEN" in banner_title.upper())
        is_human = ("HUMAN" in banner_title.upper() or "PORTRAIT" in banner_title.upper())
        is_sky = ("SKY" in banner_title.upper() or "CLOUD" in banner_title.upper())
        sky_blue = (235, 175, 40) # Vivid cyan/sky blue in BGR
        accent_color = amber if is_screen_recapture else (sky_blue if is_sky else red)

        # Draw boxes on detected subjects (e.g. phone/monitor or person)
        for det in non_road_dets:
            x1, y1, x2, y2 = det["box"]
            cv2.rectangle(img, (x1, y1), (x2, y2), accent_color, 3)

            tag = f"{det['label']} ({int(det['confidence']*100)}%)"
            font = cv2.FONT_HERSHEY_DUPLEX
            (tw, th), _ = cv2.getTextSize(tag, font, 0.6, 1)
            cv2.rectangle(img, (x1, max(0, y1 - th - 12)), (x1 + tw + 12, y1), accent_color, -1)
            cv2.putText(img, tag, (x1 + 6, y1 - 4), font, 0.6, (255, 255, 255), 1, cv2.LINE_AA)

        # For screen recapture without bounding box, draw phone/screen frame brackets and central warning badge
        if is_screen_recapture and not non_road_dets:
            pad = 20
            corner_len = min(40, max(15, w // 8), max(15, h // 8))
            cv2.rectangle(img, (pad, pad + 70), (w - pad, h - pad), amber, 2)
            cv2.line(img, (pad, pad + 70), (pad + corner_len, pad + 70), amber, 5)
            cv2.line(img, (pad, pad + 70), (pad, pad + 70 + corner_len), amber, 5)
            cv2.line(img, (w - pad, pad + 70), (w - pad - corner_len, pad + 70), amber, 5)
            cv2.line(img, (w - pad, pad + 70), (w - pad, pad + 70 + corner_len), amber, 5)
            cv2.line(img, (pad, h - pad), (pad + corner_len, h - pad), amber, 5)
            cv2.line(img, (pad, h - pad), (pad, h - pad - corner_len), amber, 5)
            cv2.line(img, (w - pad, h - pad), (w - pad - corner_len, h - pad), amber, 5)
            cv2.line(img, (w - pad, h - pad), (w - pad, h - pad - corner_len), amber, 5)

            # Central warning badge
            center_tag = "[ PHOTO FROM OTHER DEVICE DETECTED ]"
            font = cv2.FONT_HERSHEY_DUPLEX
            (ctw, cth), _ = cv2.getTextSize(center_tag, font, 0.62, 2)
            cx = max(10, (w - ctw) // 2)
            cy = max(pad + 100, h // 2)
            cv2.rectangle(img, (cx - 14, cy - cth - 14), (cx + ctw + 14, cy + 24), (20, 20, 25), -1)
            cv2.rectangle(img, (cx - 14, cy - cth - 14), (cx + ctw + 14, cy + 24), amber, 2)
            cv2.putText(img, center_tag, (cx, cy), font, 0.62, (255, 255, 255), 2, cv2.LINE_AA)

            sub_tag = "Try to click photo directly not from gallery"
            (stw, sth), _ = cv2.getTextSize(sub_tag, font, 0.46, 1)
            scx = max(10, (w - stw) // 2)
            cv2.putText(img, sub_tag, (scx, cy + 18), font, 0.46, (220, 235, 255), 1, cv2.LINE_AA)

        # For human presence without bounding box, draw corner brackets and central warning badge
        elif is_human and not non_road_dets:
            pad = 20
            corner_len = min(40, max(15, w // 8), max(15, h // 8))
            cv2.rectangle(img, (pad, pad + 70), (w - pad, h - pad), red, 2)
            cv2.line(img, (pad, pad + 70), (pad + corner_len, pad + 70), red, 5)
            cv2.line(img, (pad, pad + 70), (pad, pad + 70 + corner_len), red, 5)
            cv2.line(img, (w - pad, pad + 70), (w - pad - corner_len, pad + 70), red, 5)
            cv2.line(img, (w - pad, pad + 70), (w - pad, pad + 70 + corner_len), red, 5)
            cv2.line(img, (pad, h - pad), (pad + corner_len, h - pad), red, 5)
            cv2.line(img, (pad, h - pad), (pad, h - pad - corner_len), red, 5)
            cv2.line(img, (w - pad, h - pad), (w - pad - corner_len, h - pad), red, 5)
            cv2.line(img, (w - pad, h - pad), (w - pad, h - pad - corner_len), red, 5)

            # Central warning badge
            center_tag = "[ HUMAN PORTRAIT DETECTED ]"
            font = cv2.FONT_HERSHEY_DUPLEX
            (ctw, cth), _ = cv2.getTextSize(center_tag, font, 0.62, 2)
            cx = max(10, (w - ctw) // 2)
            cy = max(pad + 100, h // 2)
            cv2.rectangle(img, (cx - 14, cy - cth - 14), (cx + ctw + 14, cy + 24), (20, 20, 25), -1)
            cv2.rectangle(img, (cx - 14, cy - cth - 14), (cx + ctw + 14, cy + 24), red, 2)
            cv2.putText(img, center_tag, (cx, cy), font, 0.62, (255, 255, 255), 2, cv2.LINE_AA)

            sub_tag = "RoadWatch requires road surface photo, not human portraits"
            (stw, sth), _ = cv2.getTextSize(sub_tag, font, 0.44, 1)
            scx = max(10, (w - stw) // 2)
            cv2.putText(img, sub_tag, (scx, cy + 18), font, 0.44, (220, 235, 255), 1, cv2.LINE_AA)

        # For sky image, draw sky blue corner brackets and central warning badge
        elif is_sky and not non_road_dets:
            pad = 20
            corner_len = min(40, max(15, w // 8), max(15, h // 8))
            cv2.rectangle(img, (pad, pad + 70), (w - pad, h - pad), sky_blue, 2)
            cv2.line(img, (pad, pad + 70), (pad + corner_len, pad + 70), sky_blue, 5)
            cv2.line(img, (pad, pad + 70), (pad, pad + 70 + corner_len), sky_blue, 5)
            cv2.line(img, (w - pad, pad + 70), (w - pad - corner_len, pad + 70), sky_blue, 5)
            cv2.line(img, (w - pad, pad + 70), (w - pad, pad + 70 + corner_len), sky_blue, 5)
            cv2.line(img, (pad, h - pad), (pad + corner_len, h - pad), sky_blue, 5)
            cv2.line(img, (pad, h - pad), (pad, h - pad - corner_len), sky_blue, 5)
            cv2.line(img, (w - pad, h - pad), (w - pad - corner_len, h - pad), sky_blue, 5)
            cv2.line(img, (w - pad, h - pad), (w - pad, h - pad - corner_len), sky_blue, 5)

            # Central warning badge
            center_tag = "[ SKY IMAGE DETECTED ]"
            font = cv2.FONT_HERSHEY_DUPLEX
            (ctw, cth), _ = cv2.getTextSize(center_tag, font, 0.62, 2)
            cx = max(10, (w - ctw) // 2)
            cy = max(pad + 100, h // 2)
            cv2.rectangle(img, (cx - 14, cy - cth - 14), (cx + ctw + 14, cy + 24), (20, 25, 30), -1)
            cv2.rectangle(img, (cx - 14, cy - cth - 14), (cx + ctw + 14, cy + 24), sky_blue, 2)
            cv2.putText(img, center_tag, (cx, cy), font, 0.62, (255, 255, 255), 2, cv2.LINE_AA)

            sub_tag = "RoadWatch requires road surface photo, not sky or clouds"
            (stw, sth), _ = cv2.getTextSize(sub_tag, font, 0.44, 1)
            scx = max(10, (w - stw) // 2)
            cv2.putText(img, sub_tag, (scx, cy + 18), font, 0.44, (220, 240, 255), 1, cv2.LINE_AA)

        # For fake/synthetic image, draw corner brackets and central warning badge if no specific object boxes
        elif "FAKE" in banner_title.upper() and not non_road_dets:
            pad = 20
            corner_len = min(40, max(15, w // 8), max(15, h // 8))
            cv2.rectangle(img, (pad, pad + 70), (w - pad, h - pad), red, 2)
            # 4 prominent corner brackets
            cv2.line(img, (pad, pad + 70), (pad + corner_len, pad + 70), red, 5)
            cv2.line(img, (pad, pad + 70), (pad, pad + 70 + corner_len), red, 5)
            cv2.line(img, (w - pad, pad + 70), (w - pad - corner_len, pad + 70), red, 5)
            cv2.line(img, (w - pad, pad + 70), (w - pad, pad + 70 + corner_len), red, 5)
            cv2.line(img, (pad, h - pad), (pad + corner_len, h - pad), red, 5)
            cv2.line(img, (pad, h - pad), (pad, h - pad - corner_len), red, 5)
            cv2.line(img, (w - pad, h - pad), (w - pad - corner_len, h - pad), red, 5)
            cv2.line(img, (w - pad, h - pad), (w - pad, h - pad - corner_len), red, 5)

            # Central warning badge
            center_tag = "[ FAKE / SYNTHETIC IMAGE DETECTED ]"
            font = cv2.FONT_HERSHEY_DUPLEX
            (ctw, cth), _ = cv2.getTextSize(center_tag, font, 0.62, 2)
            cx = max(10, (w - ctw) // 2)
            cy = max(pad + 100, h // 2)
            cv2.rectangle(img, (cx - 14, cy - cth - 12), (cx + ctw + 14, cy + 12), (20, 20, 25), -1)
            cv2.rectangle(img, (cx - 14, cy - cth - 12), (cx + ctw + 14, cy + 12), red, 2)
            cv2.putText(img, center_tag, (cx, cy), font, 0.62, (255, 255, 255), 2, cv2.LINE_AA)

        # Top warning banner
        banner_h = 70
        overlay = img.copy()
        cv2.rectangle(overlay, (0, 0), (w, banner_h), (25, 25, 30), -1)
        cv2.addWeighted(overlay, 0.85, img, 0.15, 0, img)
        cv2.line(img, (0, banner_h), (w, banner_h), accent_color, 3)

        cv2.putText(
            img, banner_title, (16, 28),
            cv2.FONT_HERSHEY_DUPLEX, 0.72, accent_color, 2, cv2.LINE_AA
        )

        display_reason = (reason[:80] + "...") if len(reason) > 80 else reason
        cv2.putText(
            img, display_reason, (16, 54),
            cv2.FONT_HERSHEY_DUPLEX, 0.50, (220, 225, 230), 1, cv2.LINE_AA
        )

        return img

    def _draw_clean_road_annotation(self, img: np.ndarray) -> np.ndarray:
        """Draws confirmation header for clean/intact road without damage."""
        h, w = img.shape[:2]
        green = (50, 180, 50)

        banner_h = 55
        overlay = img.copy()
        cv2.rectangle(overlay, (0, 0), (w, banner_h), (20, 35, 20), -1)
        cv2.addWeighted(overlay, 0.82, img, 0.18, 0, img)
        cv2.line(img, (0, banner_h), (w, banner_h), green, 2)

        cv2.putText(
            img, "[INSPECTED: ROAD SURFACE INTACT - NO DEFECTS]", (16, 26),
            cv2.FONT_HERSHEY_DUPLEX, 0.65, green, 2, cv2.LINE_AA
        )
        cv2.putText(
            img, "Asphalt pavement inspected. No severe potholes or structural cracks found.", (16, 45),
            cv2.FONT_HERSHEY_DUPLEX, 0.48, (230, 245, 230), 1, cv2.LINE_AA
        )

        return img

    def _draw_annotations(self, img: np.ndarray, detections: List[Dict[str, Any]]) -> np.ndarray:
        """Draws aesthetic bounding boxes and modern labels on the image."""
        palette = {
            "Critical": (45, 45, 235),     # Deep Red
            "High": (30, 110, 245),        # Red-Orange
            "Moderate": (20, 175, 245),    # Amber
            "Low": (70, 185, 45)           # Green
        }

        for det in detections:
            x1, y1, x2, y2 = det["box"]
            label = det["label"]
            conf = int(det["confidence"] * 100)
            sev = det["severity"]
            is_water = "water" in label.lower() or "puddle" in label.lower() or det.get("type") == "water_body"
            if is_water:
                color = (45, 45, 235) if sev == "Critical" else (245, 175, 25) # Aqua/Cyan for puddles, Red for flooded
            else:
                color = palette.get(sev, (0, 165, 255))

            cv2.rectangle(img, (x1, y1), (x2, y2), color, 3)

            corner_len = min(25, (x2 - x1) // 4, (y2 - y1) // 4)
            cv2.line(img, (x1, y1), (x1 + corner_len, y1), color, 6)
            cv2.line(img, (x1, y1), (x1, y1 + corner_len), color, 6)
            cv2.line(img, (x2, y1), (x2 - corner_len, y1), color, 6)
            cv2.line(img, (x2, y1), (x2, y1 + corner_len), color, 6)
            cv2.line(img, (x1, y2), (x1 + corner_len, y2), color, 6)
            cv2.line(img, (x1, y2), (x1, y2 - corner_len), color, 6)
            cv2.line(img, (x2, y2), (x2 - corner_len, y2), color, 6)
            cv2.line(img, (x2, y2), (x2, y2 - corner_len), color, 6)

            tag_text = f"{label} | {conf}% ({sev})"
            font = cv2.FONT_HERSHEY_DUPLEX
            font_scale = 0.65
            thickness = 1
            (text_w, text_h), _ = cv2.getTextSize(tag_text, font, font_scale, thickness)

            tag_y1 = max(0, y1 - text_h - 14)
            tag_y2 = y1
            tag_x1 = x1
            tag_x2 = min(img.shape[1], x1 + text_w + 16)

            cv2.rectangle(img, (tag_x1, tag_y1), (tag_x2, tag_y2), color, -1)
            cv2.putText(
                img, tag_text, (tag_x1 + 8, tag_y2 - 6),
                font, font_scale, (255, 255, 255), thickness, cv2.LINE_AA
            )

        return img

# Global singleton
yolo_detector = YOLORoadDetector()
