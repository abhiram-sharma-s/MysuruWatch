from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Request
from typing import Optional
from pathlib import Path
from pydantic import BaseModel
from backend.services.image_service import save_upload_file, save_base64_image, get_absolute_path_from_url
from backend.services.yolo_service import yolo_detector
from backend.config import settings

router = APIRouter()

class DetectBase64Request(BaseModel):
    image_base64: Optional[str] = None
    image_url: Optional[str] = None

@router.post("/detect")
async def detect_road_condition(
    file: Optional[UploadFile] = File(None),
    image_base64: Optional[str] = Form(None),
    image_url: Optional[str] = Form(None),
    request: Request = None
):
    """
    Detects road condition (potholes, cracks, severity) using YOLO and OpenCV.
    Accepts multipart file, form-data base64, or JSON payload.
    """
    target_abs_path: Optional[Path] = None
    original_rel_url = ""

    # Check if request has JSON body instead of form
    if file is None and image_base64 is None and image_url is None:
        try:
            body = await request.json()
            if isinstance(body, dict):
                image_base64 = body.get("image_base64")
                image_url = body.get("image_url")
        except Exception:
            pass

    # 1. Process uploaded file
    if file and file.filename:
        original_rel_url = save_upload_file(file)
        target_abs_path = get_absolute_path_from_url(original_rel_url)

    # 2. Process base64 camera capture
    elif image_base64:
        original_rel_url = save_base64_image(image_base64)
        target_abs_path = get_absolute_path_from_url(original_rel_url)

    # 3. Process existing sample or image URL
    elif image_url:
        target_abs_path = get_absolute_path_from_url(image_url)
        original_rel_url = image_url

    else:
        raise HTTPException(
            status_code=400,
            detail="No image provided. Please upload an image file or provide a base64 camera image."
        )

    if not target_abs_path or not target_abs_path.exists():
        raise HTTPException(status_code=404, detail="Target image file not found on server.")

    try:
        orig_filename = file.filename if (file and file.filename) else ""
        is_video = target_abs_path.suffix.lower() in [".mp4", ".mov", ".avi", ".webm", ".mkv"]
        if is_video:
            detection_result = yolo_detector.detect_video_road_damage(target_abs_path, original_filename=orig_filename)
        else:
            detection_result = yolo_detector.detect_road_damage(target_abs_path, original_filename=orig_filename)
        detection_result["original_image"] = original_rel_url
        return detection_result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI Detection failed: {str(e)}")

