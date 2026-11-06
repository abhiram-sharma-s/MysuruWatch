from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime

class DetectionBox(BaseModel):
    box: List[float] = Field(..., description="[x1, y1, x2, y2] coordinates")
    label: str
    confidence: float
    severity: str

class DetectionResponse(BaseModel):
    success: bool = True
    is_road: Optional[bool] = True
    is_fake: Optional[bool] = False
    is_screen_device: Optional[bool] = False
    screen_warning: Optional[str] = ""
    detections: List[DetectionBox] = []
    condition: str = "Pothole"
    confidence: float = 0.85
    confidence_display: str = "85%"
    severity: str = "High"
    annotated_image: str = ""
    original_image: str = ""
    summary: str = ""

class ReportCreate(BaseModel):
    road_condition: Optional[str] = "Pothole"
    severity: Optional[str] = "High"
    confidence: Optional[float] = 0.90
    image: Optional[str] = ""
    annotated_image: Optional[str] = ""
    location: str
    google_maps_link: Optional[str] = ""
    description: Optional[str] = ""
    reporter_name: Optional[str] = "Mysuru Citizen"
    road_type: Optional[str] = "City road"

class ReportStatusUpdate(BaseModel):
    status: str
    notes: Optional[str] = None

class ReportResponse(BaseModel):
    report_id: str
    road_condition: str
    severity: str
    confidence: float
    confidence_display: Optional[str] = ""
    image: str
    annotated_image: Optional[str] = ""
    location: str
    google_maps_link: Optional[str] = ""
    description: Optional[str] = ""
    reporter_name: Optional[str] = "Citizen"
    road_type: Optional[str] = "City road"
    date: str
    time: str
    status: str
    authority_notes: Optional[str] = ""
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

class ReportListResponse(BaseModel):
    total: int
    reports: List[ReportResponse]
    stats: Dict[str, Any]

