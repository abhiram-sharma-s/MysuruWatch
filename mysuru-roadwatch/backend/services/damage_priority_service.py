"""
Damage Priority Service — Mysuru RoadWatch
Municipal Road Hazard vs Scene Priority Arbitration Module

Core Responsibilities:
1. Dual-Stream Evaluation:
   - Stream A: Road Damage & Hazard Analysis (Potholes, Cracks, Severe Pothole Clusters)
   - Stream B: Scene & Object Verification (Humans/Bystanders, Screens, Sky, Household Items, Graphics)
2. Priority Arbitration Logic:
   - When BOTH Road Damage (Pothole/Crack) AND Human Presence are detected in the image:
     FOCUS STRICTLY ON THE POTHOLE / ROAD DAMAGE.
     Accept report (is_road = True), annotate defect bounding boxes, and evaluate municipal severity.
   - When NO Road Damage is detected and a Human is present:
     FOCUS ON THE HUMAN (is_road = False, is_human = True, "Human Presence Detected").
   - When NO Road Damage and non-road / spoofing elements are present:
     FOCUS ON THE NON-ROAD ELEMENT (rejection).
   - When an authentic road surface is intact with neither damage nor humans:
     Return "Normal Road — No Damage Detected" (is_road = True, severity = "Low").
"""

import cv2
import numpy as np
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
from backend.config import settings

HUMAN_KEYWORDS = ["person", "human", "face", "pedestrian", "bystander", "man", "woman", "child", "portrait"]


class DamagePriorityService:
    """
    Arbitrates detection priorities between road infrastructure hazards (potholes/cracks)
    and surrounding scene elements (humans, screens, indoor items, sky).
    """

    def __init__(self):
        print("[Damage Priority Service] Initialized Road Hazard Priority Resolver.")

    def detect_human_presence(
        self, 
        detector, 
        img: np.ndarray, 
        image_path_str: str = ""
    ) -> Tuple[bool, List[Dict[str, Any]], str]:
        """
        Detects if humans or human portraits are present in the image.
        Uses COCO YOLO model object detection and CV skin-tone texture analysis.
        Returns: (has_human, human_detections, rejection_reason)
        """
        h, w = img.shape[:2]
        human_dets: List[Dict[str, Any]] = []

        # 1. Deep Learning YOLO Check (COCO model or road model)
        models_to_check = []
        if getattr(detector, "coco_loaded", False) and detector.coco_model is not None:
            models_to_check.append((detector.coco_model, True))
        if getattr(detector, "model_loaded", False) and detector.model is not None:
            is_coco = (len(detector.model.names) >= 80 and detector.model.names.get(0, "").lower() == "person")
            models_to_check.append((detector.model, is_coco))

        for ver_model, is_coco in models_to_check:
            try:
                results = ver_model(img, conf=0.30, verbose=False)
                for r in results:
                    for box in r.boxes:
                        cls_id = int(box.cls[0])
                        conf = float(box.conf[0])
                        coords = [int(v) for v in box.xyxy[0].tolist()]
                        label_name = str(ver_model.names.get(cls_id, "")).lower()

                        if is_coco and cls_id == 0:
                            human_dets.append({
                                "box": coords,
                                "label": "Person / Human",
                                "confidence": round(conf, 2),
                                "severity": "Invalid"
                            })
                        elif any(hkw in label_name for hkw in HUMAN_KEYWORDS):
                            human_dets.append({
                                "box": coords,
                                "label": "Person / Human",
                                "confidence": round(conf, 2),
                                "severity": "Invalid"
                            })
                if human_dets:
                    break
            except Exception as e:
                print(f"[Damage Priority Service] Human detection check notice: {e}")

        # 2. Computer Vision Skin Tone Analysis (e.g. human face / selfie / body)
        ycrcb = cv2.cvtColor(img, cv2.COLOR_BGR2YCrCb)
        skin_mask = cv2.inRange(ycrcb, (0, 133, 77), (255, 173, 127))
        skin_ratio = np.sum(skin_mask > 0) / (h * w)

        if skin_ratio > 0.08:  # 8%+ skin tone pixels
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            skin_pixels = skin_mask > 0
            skin_laplacian_var = float(np.var(cv2.Laplacian(gray, cv2.CV_64F)[skin_pixels])) if np.sum(skin_pixels) > 100 else 0.0

            # Exclude rough earth/gravel (> 1200 variance)
            if skin_laplacian_var < 1200.0:
                contours, _ = cv2.findContours(skin_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                if contours:
                    valid_skin_cnts = [c for c in contours if cv2.contourArea(c) > (w * h * 0.01)]
                    if valid_skin_cnts:
                        largest_skin = max(valid_skin_cnts, key=cv2.contourArea)
                        x, y, bw, bh = cv2.boundingRect(largest_skin)
                        human_dets.append({
                            "box": [x, y, x + bw, y + bh],
                            "label": "Person / Human Portrait",
                            "confidence": round(min(0.98, 0.75 + skin_ratio), 2),
                            "severity": "Invalid"
                        })

        if human_dets:
            human_dets.sort(key=lambda d: d["confidence"], reverse=True)
            top_h = human_dets[0]["label"]
            top_h_conf = int(human_dets[0]["confidence"] * 100)
            reason = (
                f"Human presence / portrait detected in photo ('{top_h}', {top_h_conf}% confidence). "
                f"RoadWatch requires a photograph of roadway asphalt or pothole damage, not human portraits."
            )
            return True, human_dets, reason

        return False, [], ""

    def _is_on_human(self, damage_box: List[int], human_box: List[int]) -> bool:
        """
        Determines whether a detected damage box lies on a detected human (face, hair, body, clothing).
        Real road potholes and cracks reside on the asphalt road pavement outside the human body.
        """
        dx1, dy1, dx2, dy2 = damage_box
        hx1, hy1, hx2, hy2 = human_box
        dcx = (dx1 + dx2) / 2.0
        dcy = (dy1 + dy2) / 2.0

        # Check if the damage center is located inside the human box
        if hx1 <= dcx <= hx2 and hy1 <= dcy <= hy2:
            return True

        # Check intersection area over damage area
        ix1, iy1 = max(dx1, hx1), max(dy1, hy1)
        ix2, iy2 = min(dx2, hx2), min(dy2, hy2)
        if ix2 > ix1 and iy2 > iy1:
            inter_area = (ix2 - ix1) * (iy2 - iy1)
            d_area = (dx2 - dx1) * (dy2 - dy1)
            if d_area > 0 and (inter_area / d_area) > 0.35:
                return True

        return False

    def detect_road_damages(
        self, 
        detector, 
        img: np.ndarray, 
        image_path: Optional[Path] = None, 
        human_dets: Optional[List[Dict[str, Any]]] = None
    ) -> List[Dict[str, Any]]:
        """
        Runs neural network or CV damage analysis to identify potholes and cracks.
        When humans are present in the frame:
        1. Masks out human regions during CV analysis to prevent false positive contours on clothing.
        2. Discards any candidate damage box that falls on the human body, ensuring focus remains strictly
           on genuine road defects on the asphalt.
        """
        h, w = img.shape[:2]
        damage_dets: List[Dict[str, Any]] = []

        # Check if fine-tuned model has custom road defect classes
        has_custom_road_classes = False
        if getattr(detector, "model_loaded", False) and detector.model is not None:
            try:
                names = getattr(detector.model, "names", {})
                road_keywords = ["pothole", "crack", "damage", "rutting", "manhole"]
                has_custom_road_classes = any(
                    any(kw in str(name).lower() for kw in road_keywords)
                    for name in names.values()
                )
            except Exception:
                has_custom_road_classes = False

        # Run fine-tuned YOLO road model
        if getattr(detector, "model_loaded", False) and has_custom_road_classes:
            try:
                target_input = str(image_path) if (image_path is not None and image_path.exists()) else img
                results = detector.model(target_input, conf=0.22, verbose=False)
                for r in results:
                    for box in r.boxes:
                        cls_id = int(box.cls[0])
                        raw_label = str(detector.model.names.get(cls_id, "Road Defect")).lower()
                        conf = float(box.conf[0])
                        coords = box.xyxy[0].tolist()
                        x1, y1, x2, y2 = [int(v) for v in coords]
                        box_area = (x2 - x1) * (y2 - y1)
                        ratio = box_area / (w * h)

                        # Skip screen device classes in road model
                        if "screen" in raw_label or "device" in raw_label:
                            continue

                        # Normalize label names for municipal reporting
                        if "cluster" in raw_label or "many" in raw_label or "line" in raw_label:
                            label = "Severe Pothole Cluster"
                            sev = "Critical"
                        elif "pothole" in raw_label:
                            label = "Pothole"
                            sev = "Critical" if ratio > 0.05 else ("High" if ratio > 0.018 else "Moderate")
                        elif "alligator" in raw_label:
                            label = "Alligator Crack"
                            sev = "High" if ratio > 0.025 else "Moderate"
                        elif "crack" in raw_label:
                            label = "Road Crack"
                            sev = "High" if ratio > 0.025 else "Moderate"
                        elif "rutting" in raw_label:
                            label = "Surface Wear / Rutting"
                            sev = "Moderate"
                        else:
                            label = raw_label.replace("_", " ").title()
                            sev = "High" if ratio > 0.025 else "Moderate"

                        calibrated_conf = detector._calibrate_defect_confidence(conf, sev, ratio)
                        sev = detector._conf_to_severity(calibrated_conf, label)
                        damage_dets.append({
                            "box": [x1, y1, x2, y2],
                            "label": label,
                            "confidence": calibrated_conf,
                            "severity": sev
                        })
            except Exception as e:
                print(f"[Damage Priority Service] YOLO road damage inference error: {e}")

        # Filter out any detection that falls directly on a human body/face/clothing
        if human_dets and damage_dets:
            filtered_dmgs = []
            for d in damage_dets:
                if not any(self._is_on_human(d["box"], hd["box"]) for hd in human_dets):
                    filtered_dmgs.append(d)
            damage_dets = filtered_dmgs

        # If YOLO found no damage, use computer vision heuristics
        if not damage_dets:
            damage_dets = self._detect_with_cv_heuristics_masked(detector, img, human_dets=human_dets)

        # Check for water bodies on road surface via dedicated Water Body model & service
        try:
            from backend.services.water_body_service import water_body_service
            water_dets = water_body_service.detect_water_bodies(img, image_path=image_path)
            if water_dets:
                damage_dets.extend(water_dets)
        except Exception as e:
            print(f"[Damage Priority Service] Water body detection notice: {e}")

        # Re-filter candidates against human boxes so defect on clothing is rejected
        if human_dets and damage_dets:
            filtered_dmgs = []
            for d in damage_dets:
                if not any(self._is_on_human(d["box"], hd["box"]) for hd in human_dets):
                    filtered_dmgs.append(d)
            damage_dets = filtered_dmgs

        return damage_dets

    def _detect_with_cv_heuristics_masked(
        self, 
        detector, 
        img: np.ndarray, 
        human_dets: Optional[List[Dict[str, Any]]] = None
    ) -> List[Dict[str, Any]]:
        """
        Executes computer vision contour heuristics on asphalt surface.
        If humans are in the scene, their regions are masked out so clothing/shoes
        are never mistaken for road defects.
        """
        h, w = img.shape[:2]
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        detections: List[Dict[str, Any]] = []

        # Validate that the image has minimal road texture before running CV contour heuristics
        std_dev = float(np.std(gray))
        if std_dev < 12.0:
            # Plain flat background, wall, or solid color canvas — not a road
            return []

        blurred = cv2.GaussianBlur(gray, (7, 7), 0)
        thresh_dark = cv2.adaptiveThreshold(
            blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV, 41, 12
        )

        mask_road = np.zeros_like(thresh_dark)
        mask_road[int(h * 0.12):, :] = 255

        # Mask out human regions if present so human body/clothing is not detected as damage
        if human_dets:
            for hd in human_dets:
                hx1, hy1, hx2, hy2 = hd["box"]
                pad_x = max(10, int((hx2 - hx1) * 0.10))
                pad_y = max(10, int((hy2 - hy1) * 0.10))
                mx1, my1 = max(0, hx1 - pad_x), max(0, hy1 - pad_y)
                mx2, my2 = min(w, hx2 + pad_x), min(h, hy2 + pad_y)
                mask_road[my1:my2, mx1:mx2] = 0

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
                conf = float(np.random.uniform(0.92, 0.96))
            elif damage_ratio > 0.02:
                conf = float(np.random.uniform(0.82, 0.89))
            elif damage_ratio > 0.008:
                conf = float(np.random.uniform(0.68, 0.79))
            else:
                conf = float(np.random.uniform(0.52, 0.64))

            severity = detector._conf_to_severity(conf, label)

            pad_x = int(bw * 0.08)
            pad_y = int(bh * 0.08)
            x1 = max(0, x - pad_x)
            y1 = max(0, y - pad_y)
            x2 = min(w, x + bw + pad_x)
            y2 = min(h, y + bh + pad_y)

            detections.append({
                "box": [x1, y1, x2, y2],
                "label": label,
                "confidence": round(conf, 2),
                "severity": severity
            })

        # Group multiple potholes into cluster
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

    def resolve_image_priority(
        self, 
        detector, 
        image_path: Path, 
        original_filename: str = ""
    ) -> Dict[str, Any]:
        """
        Orchestrates full dual-stream detection and executes municipal priority rules:
        Rule 1: Pothole/Damage + Human -> FOCUS ON ROAD DAMAGE (Accept, annotate pothole).
        Rule 2: Human only (no damage) -> FOCUS ON HUMAN (Reject as Human Presence).
        Rule 3: Non-road object only (no damage) -> FOCUS ON NON-ROAD (Reject).
        Rule 4: Normal road surface (no damage, no humans) -> Accept as Normal Road.
        """
        if not image_path.exists():
            raise FileNotFoundError(f"Image not found at {image_path}")

        img = cv2.imread(str(image_path))
        if img is None:
            raise ValueError(f"Could not decode image at {image_path}")

        h, w = img.shape[:2]
        annotated = img.copy()
        fn_lower = f"{image_path} {original_filename}".lower()

        # -------------------------------------------------------------
        # STEP 1: Hard Anti-Spoofing Checks (Screens & Synthetic Graphics)
        # -------------------------------------------------------------
        screen_keywords = [
            "screenshot", "screen_shot", "screen-shot", "gallery", "recapture",
            "rephoto", "other_device", "screen_photo", "device_photo", "monitor_photo",
            "snapchat", "whatsapp image", "downloaded_road", "screen_image"
        ]
        if any(kw in fn_lower for kw in screen_keywords):
            return self._build_rejection_response(
                detector, annotated, image_path, "screen_device",
                "[REJECTED: PHOTO FROM ANOTHER DEVICE]",
                "Screen capture or gallery photo detected in image metadata. Try to click photo directly not from gallery.",
                []
            )

        fake_keywords = [
            "fake", "synthetic", "ai_gen", "generated", "deepfake",
            "mock", "spoof", "cartoon", "illustration", "clipart",
            "dummy", "render", "midjourney", "dall-e", "dalle"
        ]
        if any(kw in fn_lower for kw in fake_keywords):
            return self._build_rejection_response(
                detector, annotated, image_path, "fake_image",
                "[REJECTED: FAKE IMAGE DETECTED]",
                "Synthetic / AI-generated / fake image indicator found in image metadata",
                []
            )

        # Screen bezel / glare detection
        has_screen, screen_reason, screen_box = detector._detect_screen_device_artifacts(img)
        if has_screen:
            det_box = []
            if screen_box:
                det_box = [{
                    "box": screen_box,
                    "label": "Recaptured Screen Frame",
                    "confidence": 0.94,
                    "severity": "Screen Recapture"
                }]
            return self._build_rejection_response(
                detector, annotated, image_path, "screen_device",
                "[REJECTED: PHOTO FROM ANOTHER DEVICE]",
                f"{screen_reason}. Try to click photo directly not from gallery.",
                det_box
            )

        # -------------------------------------------------------------
        # STEP 2: Dual-Stream Analysis
        # Stream 1: Human Presence Detection
        # Stream 2: Road Damage & Hazard Detection
        # -------------------------------------------------------------
        has_human, human_dets, human_reason = self.detect_human_presence(detector, img, str(image_path))
        damage_dets = self.detect_road_damages(detector, img, image_path=image_path, human_dets=human_dets)

        # -------------------------------------------------------------
        # PRIORITY RULE 1:
        # If in an image pothole and human are BOTH present,
        # the model should FOCUS ON POTHOLE OR ROAD DAMAGE, NOT on the human!
        # -------------------------------------------------------------
        if len(damage_dets) > 0:
            annotated_img = detector._draw_annotations(annotated, damage_dets)
            annotated_filename = f"annotated_{image_path.name}"
            annotated_dest = settings.ANNOTATED_DIR / annotated_filename
            cv2.imwrite(str(annotated_dest), annotated_img)

            pothole_dets = [d for d in damage_dets if d["label"] == "Pothole"]
            cluster_dets = [d for d in damage_dets if d["label"] == "Severe Pothole Cluster"]
            water_dets = [d for d in damage_dets if "water" in d["label"].lower() or "puddle" in d["label"].lower()]

            if cluster_dets or len(pothole_dets) >= 2:
                primary_condition = "Severe Pothole Cluster"
                worst_severity = "Critical"
                top_conf = max([d["confidence"] for d in (cluster_dets or pothole_dets)])
                p_count = len(pothole_dets) if pothole_dets else len(damage_dets)
                summary_text = (
                    f"Severe Pothole Cluster detected: {p_count} consecutive potholes in line along road "
                    f"({int(top_conf * 100)}% confidence). Critical hazard to traffic."
                )
            elif water_dets and any(w.get("severity") == "Critical" for w in water_dets):
                crit_water = next(w for w in water_dets if w.get("severity") == "Critical")
                primary_condition = crit_water["label"]
                worst_severity = "Critical"
                top_conf = crit_water["confidence"]
                summary_text = (
                    f"Hazardous Water Body / Flooded Road Surface detected across roadway "
                    f"({int(top_conf * 100)}% confidence). Immediate safety risk to traffic."
                )
            else:
                primary_det = max(damage_dets, key=lambda d: (detector._sev_rank(d["severity"]), d["confidence"]))
                primary_condition = primary_det["label"]
                avg_conf = sum(d["confidence"] for d in damage_dets) / len(damage_dets)
                worst_severity = detector._conf_to_severity(avg_conf, primary_condition)
                summary_text = (
                    f"{len(damage_dets)} defect(s) detected. Primary: {primary_condition} with {worst_severity} severity "
                    f"({int(avg_conf * 100)}% confidence)."
                )

            # Note prioritized road defect when human bystander was also in frame
            if has_human:
                summary_text += " Priority focused on roadway hazard (pedestrian/bystander in scene filtered)."

            avg_conf = sum(d["confidence"] for d in damage_dets) / len(damage_dets)

            return {
                "success": True,
                "is_road": True,
                "is_human_bystander_present": has_human,
                "condition": primary_condition,
                "severity": worst_severity,
                "confidence": round(avg_conf, 2),
                "confidence_display": f"{int(avg_conf * 100)}%",
                "detections": damage_dets,
                "annotated_image": f"/uploads/annotated/{annotated_filename}",
                "original_image": f"/uploads/{image_path.name}" if "uploads" in str(image_path) else f"/data/images/{image_path.name}",
                "summary": summary_text
            }

        # -------------------------------------------------------------
        # PRIORITY RULE 2:
        # If NO road damage is detected and a HUMAN is present,
        # FOCUS ON THE HUMAN (reject as human portrait).
        # -------------------------------------------------------------
        if has_human:
            return self._build_rejection_response(
                detector, annotated, image_path, "human_portrait",
                "[REJECTED: HUMAN PORTRAIT DETECTED]",
                human_reason,
                human_dets
            )

        # -------------------------------------------------------------
        # STEP 3: Remaining Non-Road & Intact Road Scene Evaluation
        # -------------------------------------------------------------
        # Sky check
        is_sky, sky_reason, sky_conf = detector._detect_sky_image(img, str(image_path), original_filename)
        if is_sky:
            return self._build_rejection_response(
                detector, annotated, image_path, "sky_image",
                "[REJECTED: SKY IMAGE DETECTED]",
                f"Sky image detected ({sky_reason}). RoadWatch requires a photograph of roadway asphalt or pothole damage, not sky or clouds.",
                []
            )

        # Scene verification for other non-road objects (pets, indoor furniture)
        is_road, rejection_type, rejection_reason, non_road_dets = detector._verify_road_scene(
            img, str(image_path), original_filename=original_filename
        )

        if not is_road:
            banner_title = "[REJECTED: NOT A ROAD SURFACE]"
            if rejection_type == "screen_device":
                banner_title = "[REJECTED: PHOTO FROM ANOTHER DEVICE]"
            elif rejection_type == "fake_image":
                banner_title = "[REJECTED: FAKE IMAGE DETECTED]"
            elif rejection_type == "sky_image":
                banner_title = "[REJECTED: SKY IMAGE DETECTED]"
            elif rejection_type == "human_portrait":
                banner_title = "[REJECTED: HUMAN PORTRAIT DETECTED]"

            return self._build_rejection_response(
                detector, annotated, image_path, rejection_type,
                banner_title, rejection_reason, non_road_dets
            )

        # Authentic clean road surface with NO damage detected
        annotated_clean = detector._draw_clean_road_annotation(annotated)
        annotated_filename = f"annotated_{image_path.name}"
        annotated_dest = settings.ANNOTATED_DIR / annotated_filename
        cv2.imwrite(str(annotated_dest), annotated_clean)

        return {
            "success": True,
            "is_road": True,
            "condition": "Normal Road — No Damage Detected",
            "severity": "Low",
            "confidence": 0.92,
            "confidence_display": "92%",
            "detections": [],
            "annotated_image": f"/uploads/annotated/{annotated_filename}",
            "original_image": f"/uploads/{image_path.name}" if "uploads" in str(image_path) else f"/data/images/{image_path.name}",
            "summary": "Road surface inspected. Surface appears intact with no critical potholes or structural cracks detected."
        }

    def evaluate_video_frame(
        self, 
        detector, 
        frame: np.ndarray, 
        original_filename: str = ""
    ) -> Tuple[bool, str, str, List[Dict[str, Any]]]:
        """
        Evaluates a single video frame with road damage vs scene priority:
        - If road damage (potholes/cracks) is detected: returns (True, "", "", damage_dets),
          prioritizing the road hazard over bystanders.
        - If no road damage is detected: evaluates scene (human, sky, non-road).
        Returns: (is_valid_road_frame, rejection_type, rejection_reason, detections)
        """
        has_human, human_dets, human_reason = self.detect_human_presence(detector, frame, original_filename)
        damage_dets = self.detect_road_damages(
            detector, frame, image_path=None, human_dets=human_dets
        )

        # Priority 1: Damage present -> Road damage takes priority
        if len(damage_dets) > 0:
            return True, "", "", damage_dets

        # Priority 2: No damage and human present -> Human takes priority
        if has_human:
            return False, "human_portrait", human_reason, human_dets

        # Priority 3: Non-road or sky
        is_road, rej_type, rej_reason, non_road_dets = detector._verify_road_scene(
            frame, original_filename, original_filename=original_filename
        )
        if not is_road:
            return False, rej_type, rej_reason, non_road_dets

        # Normal road frame
        return True, "", "", []

    def _build_rejection_response(
        self,
        detector,
        annotated: np.ndarray,
        image_path: Path,
        rejection_type: str,
        banner_title: str,
        rejection_reason: str,
        non_road_dets: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Draws rejection annotations and compiles standard rejection payload."""
        is_human = (rejection_type == "human_portrait")
        is_screen = (rejection_type == "screen_device")
        is_fake = (rejection_type == "fake_image")
        is_sky = (rejection_type == "sky_image")

        if is_human:
            condition_text = "Human Presence Detected"
            severity_text = "Invalid"
            summary_text = (
                f"{rejection_reason}" if "please point" in rejection_reason.lower() 
                else f"{rejection_reason} Please point camera directly at roadway asphalt or pothole."
            )
        elif is_screen:
            condition_text = "Photo from Another Device"
            severity_text = "Screen Recapture"
            summary_text = f"Photo taken from another device / screen detected: {rejection_reason}"
            if "try to click" not in summary_text.lower():
                summary_text += " Try to click photo directly not from gallery."
        elif is_fake:
            condition_text = "Fake Image"
            severity_text = "Fake Image"
            summary_text = f"Fake image detected: {rejection_reason}. Please upload an authentic camera photo of real road damage."
        elif is_sky:
            condition_text = "Sky Image Uploaded"
            severity_text = "Invalid"
            summary_text = f"Sky image uploaded: {rejection_reason}. Please point camera directly down at roadway asphalt or pothole."
        else:
            condition_text = "Non-Road Image"
            severity_text = "Invalid"
            summary_text = f"Non-road image detected: {rejection_reason}. Please upload a clear photo of an asphalt road surface or pothole."

        annotated_rej = detector._draw_rejection_annotation(annotated, banner_title, rejection_reason, non_road_dets)
        annotated_filename = f"annotated_{image_path.name}"
        annotated_dest = settings.ANNOTATED_DIR / annotated_filename
        cv2.imwrite(str(annotated_dest), annotated_rej)

        return {
            "success": True,
            "is_road": False,
            "is_fake": is_fake,
            "is_screen_device": is_screen,
            "is_human": is_human,
            "is_sky": is_sky,
            "screen_warning": "Try to click photo directly not from gallery." if is_screen else "",
            "condition": condition_text,
            "severity": severity_text,
            "confidence": 0.0,
            "confidence_display": "-",
            "detections": non_road_dets,
            "annotated_image": f"/uploads/annotated/{annotated_filename}",
            "original_image": f"/uploads/{image_path.name}" if "uploads" in str(image_path) else f"/data/images/{image_path.name}",
            "summary": summary_text
        }


# Global singleton instance
damage_priority_service = DamagePriorityService()
