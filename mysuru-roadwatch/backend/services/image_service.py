import os
import uuid
import base64
import time
from pathlib import Path
from fastapi import UploadFile, HTTPException
from backend.config import settings

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".mp4", ".mov", ".avi", ".webm", ".mkv"}

def save_upload_file(file: UploadFile) -> str:
    """Save an uploaded file and return relative server path."""
    orig_name = Path(file.filename).stem if file.filename else "upload"
    clean_stem = "".join(c for c in orig_name if c.isalnum() or c in ("-", "_"))[:30]
    if not clean_stem:
        clean_stem = "upload"

    ext = Path(file.filename).suffix.lower() if file.filename else ".jpg"
    if ext not in ALLOWED_EXTENSIONS:
        ext = ".jpg"

    filename = f"upload_{clean_stem}_{int(time.time())}_{uuid.uuid4().hex[:6]}{ext}"
    dest_path = settings.UPLOADS_DIR / filename

    with open(dest_path, "wb") as buffer:
        content = file.file.read()
        buffer.write(content)

    return f"/uploads/{filename}"

def save_base64_image(base64_data: str) -> str:
    """Decode and save a base64 image (from live camera) and return relative server path."""
    try:
        if "," in base64_data:
            header, encoded = base64_data.split(",", 1)
        else:
            encoded = base64_data

        decoded = base64.b64decode(encoded)
        filename = f"cam_{int(time.time())}_{uuid.uuid4().hex[:8]}.jpg"
        dest_path = settings.UPLOADS_DIR / filename

        with open(dest_path, "wb") as f:
            f.write(decoded)

        return f"/uploads/{filename}"
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid base64 image data: {str(e)}")

def get_absolute_path_from_url(url: str) -> Path:
    """Convert a /uploads/... or /uploads/annotated/... or asset URL to system Path."""
    clean_url = url.lstrip("/")
    filename = clean_url
    if filename.startswith("uploads/"):
        filename = filename.replace("uploads/", "", 1)
    if filename.startswith("annotated/"):
        filename = filename.replace("annotated/", "", 1)
    if filename.startswith("static/"):
        filename = filename.replace("static/", "", 1)
    if filename.startswith("assets/images/"):
        filename = filename.replace("assets/images/", "", 1)

    # Check candidates
    candidates = [
        settings.IMAGES_DIR / filename,
        settings.UPLOADS_DIR / filename,
        settings.ANNOTATED_DIR / filename,
        settings.FRONTEND_DIR / "assets" / "images" / filename,
        settings.PROJECT_ROOT / clean_url,
        settings.PROJECT_ROOT / filename
    ]

    for p in candidates:
        if p.exists():
            return p

    # Return default upload path if none exist yet
    return settings.UPLOADS_DIR / filename

