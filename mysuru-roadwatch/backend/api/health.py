import os
import time
from datetime import datetime
from fastapi import APIRouter
from backend.services.firebase_service import report_service
from backend.services.yolo_service import yolo_detector
from backend.config import settings

router = APIRouter()
START_TIME = time.time()

@router.get("/health")
def health_check():
    """System health check endpoint."""
    uptime_seconds = int(time.time() - START_TIME)
    stats = report_service.get_stats()

    return {
        "status": "healthy",
        "system": "Mysuru RoadWatch API",
        "version": "1.0.0",
        "city": settings.MYSURU_CITY,
        "uptime_seconds": uptime_seconds,
        "database": {
            "mode": "Firebase Firestore" if report_service.firebase_initialized else "Local Resilient JSON Database",
            "connected": report_service.firebase_initialized,
            "total_records": stats["total_reports"]
        },
        "ai_engine": {
            "model_type": "YOLOv8 Road Damage Detection",
            "model_loaded": yolo_detector.model_loaded,
            "weights_path": str(settings.MODEL_PATH)
        },
        "timestamp": datetime.now().isoformat()
    }

