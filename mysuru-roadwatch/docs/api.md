# Mysuru RoadWatch — API Specification

The Mysuru RoadWatch backend exposes a RESTful API built with **FastAPI**.

Base URL: `http://localhost:8000/api`

Interactive OpenAPI Docs: `http://localhost:8000/docs`

---

## 1. Health Check

### `GET /api/health`
Returns system status, database mode, and AI engine status.

**Response (200 OK):**
```json
{
  "status": "healthy",
  "system": "Mysuru RoadWatch API",
  "version": "1.0.0",
  "city": "Mysuru, Karnataka",
  "uptime_seconds": 128,
  "database": {
    "mode": "Firebase Firestore",
    "connected": true,
    "total_records": 5
  },
  "ai_engine": {
    "model_type": "YOLOv8 Road Damage Detection",
    "model_loaded": true,
    "weights_path": "ai/model/best.pt"
  },
  "timestamp": "2026-10-12T21:15:00.000000"
}
```

---

## 2. AI Road Damage Detection

### `POST /api/detect`
Ingests an image, runs YOLO detection, computes severity & confidence, and outputs annotated bounding boxes.

**Request Formats:**
1. **Multipart Form**: `file` (Image file)
2. **Form / JSON Data**: `image_base64` (Base64 JPEG data URL from webcam)
3. **JSON**: `{"image_url": "/uploads/sample_pothole_road.jpg"}`

**Response (200 OK):**
```json
{
  "success": true,
  "condition": "Pothole",
  "severity": "High",
  "confidence": 0.94,
  "confidence_display": "94%",
  "detections": [
    {
      "box": [320, 240, 580, 410],
      "label": "Pothole",
      "confidence": 0.94,
      "severity": "High"
    }
  ],
  "annotated_image": "/uploads/annotated/annotated_upload_1760284200.jpg",
  "original_image": "/uploads/upload_1760284200.jpg",
  "summary": "1 defect(s) detected. Primary: Pothole with High severity (94% confidence)."
}
```

---

## 3. Road Condition Reports

### `POST /api/reports`
Submits a citizen road damage report to Firebase Firestore.

**Request Parameters (Multipart or JSON):**
| Field | Type | Required | Description |
|---|---|---|---|
| `location` | string | **Yes** | Mysuru road name (e.g. "Sayyaji Rao Road") |
| `road_condition` | string | Optional | Defect type (e.g. "Pothole", "Road Crack") |
| `severity` | string | Optional | `Low`, `Moderate`, `High`, `Critical` |
| `confidence` | float | Optional | AI confidence score (0.0 to 1.0) |
| `image` | string / file | Optional | Image URL or uploaded file |
| `annotated_image` | string | Optional | Path to annotated YOLO image |
| `google_maps_link`| string | Optional | Google Maps location URL |
| `description` | string | Optional | Citizen notes |
| `reporter_name` | string | Optional | Citizen name |
| `road_type` | string | Optional | "City road", "Highway", etc. |

**Response (200 OK):**
```json
{
  "success": true,
  "message": "Road condition report submitted successfully.",
  "report": {
    "report_id": "RW-006",
    "road_condition": "Pothole",
    "severity": "High",
    "confidence": 0.94,
    "confidence_display": "94%",
    "image": "/uploads/cam_1760284200.jpg",
    "annotated_image": "/uploads/annotated/annotated_cam_1760284200.jpg",
    "location": "Sayyaji Rao Road, Near Mysore Palace, Mysuru",
    "google_maps_link": "https://maps.google.com/?q=12.3051,76.6551",
    "description": "Large pothole causing vehicle swerving.",
    "reporter_name": "Mysuru Citizen",
    "road_type": "City road",
    "date": "12-Oct-2026",
    "time": "09:30 PM",
    "status": "New",
    "authority_notes": "",
    "created_at": "2026-10-12T21:30:00.000000"
  }
}
```

---

### `GET /api/reports`
Lists road condition reports with optional query filters.

**Query Parameters:**
* `status`: Filter by status (`New`, `Verified`, `In Progress`, `Resolved`)
* `severity`: Filter by severity (`Low`, `Moderate`, `High`, `Critical`)
* `search`: Filter by keyword (location, ID, or condition)

**Response (200 OK):**
```json
{
  "total": 5,
  "reports": [...],
  "stats": {
    "total_reports": 5,
    "new_reports": 2,
    "verified_reports": 1,
    "in_progress_reports": 1,
    "resolved_reports": 1,
    "critical_high_reports": 3,
    "pothole_reports": 3,
    "crack_reports": 2,
    "firebase_connected": true
  }
}
```

---

### `GET /api/reports/{report_id}`
Retrieves a specific report by ID (e.g. `RW-001`).

---

### `PUT /api/reports/{report_id}/status`
Updates report status and records municipal action notes.

**Request Body (JSON):**
```json
{
  "status": "In Progress",
  "notes": "Patchwork crew and road roller dispatched by Ward 14 engineer."
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "message": "Report 'RW-001' status updated to 'In Progress'.",
  "report": { ... }
}
```

