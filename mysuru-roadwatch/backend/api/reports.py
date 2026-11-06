from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Query, Request, Response
from typing import Optional, List, Dict, Any
from pathlib import Path
import csv
import io
from backend.services.firebase_service import report_service
from backend.services.image_service import save_upload_file, save_base64_image, get_absolute_path_from_url
from backend.services.yolo_service import yolo_detector
from backend.models.report_model import ReportCreate, ReportStatusUpdate

router = APIRouter()

@router.get("/reports")
def get_reports(
    status: Optional[str] = Query(None, description="Filter by status: New, Verified, In Progress, Resolved"),
    severity: Optional[str] = Query(None, description="Filter by severity: Low, Moderate, High, Critical"),
    search: Optional[str] = Query(None, description="Search term for location, ID, or condition"),
    since: Optional[str] = Query(None, description="ISO timestamp to filter reports created after this time"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD) for report submission date range"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD) for report submission date range")
):
    """Retrieves all road reports with optional filtering, since timestamp, submission date range, and summary statistics."""
    status_str = status if isinstance(status, str) else None
    severity_str = severity if isinstance(severity, str) else None
    search_str = search if isinstance(search, str) else None
    since_str = since if isinstance(since, str) else None
    start_date_str = start_date if isinstance(start_date, str) else None
    end_date_str = end_date if isinstance(end_date, str) else None

    reports = report_service.get_all_reports(
        status=status_str, 
        severity=severity_str, 
        search=search_str, 
        since=since_str,
        start_date=start_date_str,
        end_date=end_date_str
    )
    stats = report_service.get_stats()
    return {
        "total": len(reports),
        "reports": reports,
        "stats": stats
    }

@router.get("/reports/export/csv")
def export_reports_to_csv(
    start_date: Optional[str] = Query(None, description="Start submission date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End submission date (YYYY-MM-DD)"),
    status: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    search: Optional[str] = Query(None)
):
    """
    Exports road reports filtered by submission date range to a CSV spreadsheet file.
    """
    reports = report_service.get_all_reports(
        status=status,
        severity=severity,
        search=search,
        start_date=start_date,
        end_date=end_date
    )

    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_ALL)
    
    headers = [
        "Report ID", "Road Condition", "Severity", "AI Confidence", 
        "Location", "Google Maps Link", "Status", "Submission Date", 
        "Submission Time", "ISO Timestamp", "Reporter Name", "Road Type", 
        "Description", "Authority Notes"
    ]
    writer.writerow(headers)

    for r in reports:
        conf_disp = r.get("confidence_display")
        if not conf_disp and r.get("confidence") is not None:
            try:
                conf_disp = f"{int(float(r.get('confidence')) * 100)}%"
            except Exception:
                conf_disp = "-"
        writer.writerow([
            r.get("report_id", ""),
            r.get("road_condition", ""),
            r.get("severity", ""),
            conf_disp or "-",
            r.get("location", ""),
            r.get("google_maps_link", ""),
            r.get("status", "New"),
            r.get("date", ""),
            r.get("time", ""),
            r.get("created_at", ""),
            r.get("reporter_name", "Mysuru Citizen"),
            r.get("road_type", "City road"),
            r.get("description", ""),
            r.get("authority_notes", "")
        ])

    csv_data = "\ufeff" + output.getvalue()
    
    slug = "All_Dates"
    if start_date and end_date:
        slug = f"{start_date}_to_{end_date}"
    elif start_date:
        slug = f"from_{start_date}"
    elif end_date:
        slug = f"until_{end_date}"
        
    filename = f"Mysuru_RoadWatch_Reports_{slug}.csv"
    
    return Response(
        content=csv_data.encode("utf-8"),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )

@router.get("/reports/new-since-login")
def get_new_reports_since_login(
    since: Optional[str] = Query(None, description="ISO timestamp of previous authority login")
):
    """
    Returns the count and details of reports submitted between the last authority login and now.
    If 'since' is omitted, returns all reports currently with 'New' status.
    """
    since_str = since if isinstance(since, str) else None
    new_reports = report_service.get_reports_since(since=since_str)
    return {
        "count": len(new_reports),
        "since": since_str,
        "reports": new_reports
    }

@router.get("/reports/{report_id}")
def get_single_report(report_id: str):
    """Retrieve details for a single road condition report by ID."""
    report = report_service.get_report_by_id(report_id)
    if not report:
        raise HTTPException(status_code=404, detail=f"Report with ID '{report_id}' not found.")
    return report

@router.post("/reports")
async def create_new_report(
    file: Optional[UploadFile] = File(None),
    image_base64: Optional[str] = Form(None),
    image: Optional[str] = Form(None),
    annotated_image: Optional[str] = Form(None),
    road_condition: Optional[str] = Form("Pothole"),
    severity: Optional[str] = Form("High"),
    confidence: Optional[float] = Form(0.92),
    location: Optional[str] = Form(None),
    google_maps_link: Optional[str] = Form(""),
    description: Optional[str] = Form(""),
    reporter_name: Optional[str] = Form("Mysuru Citizen"),
    road_type: Optional[str] = Form("City road"),
    request: Request = None
):
    """
    Submits a new road condition report.
    Accepts both multipart form (with file) or application/json body.
    If image has not yet been processed by AI, triggers YOLO detection automatically.
    """
    report_dict: Dict[str, Any] = {}

    # Handle JSON body if submitted as JSON
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        try:
            body = await request.json()
            if isinstance(body, dict):
                report_dict = body
        except Exception:
            pass

    if not report_dict:
        # Build from Form / Multipart
        report_dict = {
            "image": image or "",
            "annotated_image": annotated_image or "",
            "road_condition": road_condition or "Pothole",
            "severity": severity or "High",
            "confidence": confidence or 0.90,
            "location": location or "",
            "google_maps_link": google_maps_link or "",
            "description": description or "",
            "reporter_name": reporter_name or "Mysuru Citizen",
            "road_type": road_type or "City road",
        }

    # If an image file or base64 was sent directly in this request
    if file and file.filename:
        saved_img_url = save_upload_file(file)
        report_dict["image"] = saved_img_url
    elif image_base64:
        saved_img_url = save_base64_image(image_base64)
        report_dict["image"] = saved_img_url

    # Validate location
    loc_val = report_dict.get("location", "").strip()
    if not loc_val:
        raise HTTPException(status_code=400, detail="Road or location name is required.")

    # Run AI detection if annotated_image is missing but an image is present
    img_val = report_dict.get("image", "").strip()
    if img_val and not report_dict.get("annotated_image"):
        try:
            abs_img_path = get_absolute_path_from_url(img_val)
            if abs_img_path.exists():
                ai_result = yolo_detector.detect_road_damage(abs_img_path)
                report_dict["road_condition"] = ai_result["condition"]
                report_dict["severity"] = ai_result["severity"]
                report_dict["confidence"] = ai_result["confidence"]
                report_dict["confidence_display"] = ai_result["confidence_display"]
                report_dict["annotated_image"] = ai_result["annotated_image"]
        except Exception as e:
            print(f"[Reports API] AI auto-detection notice: {e}")

    # Reject non-road images
    cond = str(report_dict.get("road_condition", "")).lower()
    sev = str(report_dict.get("severity", "")).lower()
    if "human" in cond:
        raise HTTPException(
            status_code=400,
            detail="Cannot submit report: Human presence detected in photo. RoadWatch requires a valid photo of asphalt roadway or pothole damage, not human portraits."
        )
    if "screen" in sev or "device" in cond:
        raise HTTPException(
            status_code=400,
            detail="Cannot submit report: Photo taken from another device / screen detected. Try to click photo directly not from gallery."
        )
    if "sky" in cond or "cloud" in cond:
        raise HTTPException(
            status_code=400,
            detail="Cannot submit report: Sky image detected. RoadWatch requires a valid photo of asphalt roadway or pothole damage, not sky or clouds."
        )
    if "invalid" in cond or "invalid" in sev or "fake" in sev or report_dict.get("is_road") is False:
        raise HTTPException(
            status_code=400,
            detail="Cannot submit report: The uploaded image was identified as a non-road surface. RoadWatch requires a valid photo of asphalt roadway or pothole."
        )

    # Ensure severity aligns with standardized confidence percentage range
    if "confidence" in report_dict:
        try:
            conf_val = float(report_dict["confidence"])
            conf_pct = conf_val * 100 if conf_val <= 1.0 else conf_val
            current_sev = str(report_dict.get("severity", "")).strip()
            if current_sev.lower() not in ["invalid", "screen recapture", "fake image", "sky image", "sky image uploaded"]:
                if conf_pct >= 90.0:
                    report_dict["severity"] = "Critical"
                elif conf_pct >= 80.0:
                    report_dict["severity"] = "High"
                elif conf_pct >= 65.0 and current_sev.lower() in ["low", ""]:
                    report_dict["severity"] = "Moderate"
        except (ValueError, TypeError):
            pass

    # Set confidence display string if not already set
    if "confidence" in report_dict and "confidence_display" not in report_dict:
        conf_val = float(report_dict["confidence"])
        report_dict["confidence_display"] = f"{int(conf_val * 100 if conf_val <= 1.0 else conf_val)}%"

    # Create report in Firebase / DB
    created = report_service.create_report(report_dict)
    return {
        "success": True,
        "message": "Road condition report submitted successfully.",
        "report": created
    }

@router.put("/reports/{report_id}/status")
async def update_report_status(report_id: str, payload: ReportStatusUpdate):
    """Updates the status of a road condition report (New, Verified, In Progress, Resolved)."""
    updated = report_service.update_report_status(
        report_id=report_id,
        new_status=payload.status,
        notes=payload.notes
    )
    if not updated:
        raise HTTPException(status_code=404, detail=f"Report with ID '{report_id}' not found.")

    return {
        "success": True,
        "message": f"Report '{report_id}' status updated to '{updated['status']}'.",
        "report": updated
    }

