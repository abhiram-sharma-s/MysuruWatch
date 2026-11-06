# Mysuru RoadWatch — System Architecture

**Mysuru RoadWatch** is a Real-Time Road Condition Monitoring System tailored for Mysuru City, Karnataka. It integrates mobile browser computer vision, YOLO object detection, and a FastAPI backend with Firebase Firestore to bridge the gap between citizens and municipal authorities.

---

## 1. High-Level Architecture Diagram

```
+-----------------------------------------------------------------------------------+
|                                  CLIENT LAYER                                     |
|                                                                                   |
|  [Citizen Mobile / Desktop Browser]                [Authority Admin Dashboard]    |
|   - Live Camera Capture (WebRTC)                    - Metric KPI Cards (Total/New)|
|   - Image & Video Upload (Dropzone)                 - Filter & Search Engine      |
|   - GPS Geolocation & Google Maps Auto-Link         - Interactive Data Table      |
|   - AI Detection Result Preview (Boxes/Conf/Sev)    - Status Transition Updater   |
|   - HTML5 / Vanilla CSS / Vanilla JS Fetch Client   - Detailed Inspection Modal   |
+------------------------------------------+----------------------------------------+
                                           | HTTP / REST (JSON & Multipart)
                                           v
+-----------------------------------------------------------------------------------+
|                                FASTAPI BACKEND                                    |
|                                                                                   |
|  +---------------------+   +----------------------+   +-----------------------+   |
|  | /api/detect         |   | /api/reports         |   | /api/health           |   |
|  | - Image Ingestion   |   | - Create Report      |   | - System Status       |   |
|  | - Preprocessing     |   | - List Reports       |   | - Model Health        |   |
|  | - Base64 Decoding   |   | - Status Updates     |   | - DB Connectivity     |   |
|  +----------+----------+   +----------+-----------+   +-----------------------+   |
+-------------|-------------------------|-------------------------------------------+
              |                         |
              v                         v
+-------------------------------+ +-------------------------------------------------+
|   AI / COMPUTER VISION        | |              DATABASE LAYER                     |
|                               | |                                                 |
|  - Ultralytics YOLOv8 Model   | |  - Google Firebase Firestore (Primary)          |
|    (ai/model/best.pt)         | |    * Collection: 'road_reports'                 |
|  - OpenCV Image Processing    | |  - Resilient Local JSON Store (Fallback)        |
|  - Severity Calculation       | |    * Path: 'data/reports_db.json'               |
|  - Annotated Box Generation   | |                                                 |
+-------------------------------+ +-------------------------------------------------+
```

---

## 2. Component Breakdown

### 2.1 Frontend (Presentation Layer)
* **Technology**: Pure HTML5, Modern CSS (Custom Design System, zero third-party frameworks like Bootstrap or React), Vanilla JavaScript ES6+.
* **Mobile-First Capture**: Uses `navigator.mediaDevices.getUserMedia` for instant camera capture with camera-flip (`facingMode: 'environment'`), ensuring citizens can take photos directly from their vehicle or roadside in Mysuru.
* **Location Mapping**: Eliminates dependency on heavy mapping libraries (Leaflet/OSM) by generating direct, lightweight **Google Maps Universal Links** (`https://maps.google.com/?q=lat,lng` or search query) and integrating HTML5 Geolocation API.

### 2.2 Backend (Application Layer)
* **Framework**: Python 3.12 with **FastAPI** and **Uvicorn** for asynchronous performance.
* **Services**:
  * `yolo_service.py`: Orchestrates model loading, OpenCV preprocessing, bounding box annotation, and severity classification.
  * `firebase_service.py`: Connects to Firebase Firestore with thread-safe operations. When credentials (`serviceAccountKey.json`) are absent, smoothly falls back to local persistent storage without crashing.
  * `image_service.py`: Securely saves uploaded files and base64 payloads to timestamped storage.

### 2.3 AI & Computer Vision Layer
* **YOLOv8**: Detects potholes, cracks (transverse, longitudinal, alligator), and surface damages.
* **Severity Matrix**:
  * **Critical**: Damage area > 8% of road surface or multiple clustered deep potholes. Immediate hazard for two-wheelers and buses.
  * **High**: Damage area between 3% and 8%. High risk of vehicle damage and traffic slowdown.
  * **Moderate**: Damage area between 1% and 3%. Surface cracking and shallow indentations.
  * **Low**: Surface abrasion or minor hairline cracks.
* **Training Pipeline**: `ai/train.py` formatted for Google Colab GPU training, exporting to `ai/model/best.pt`.

### 2.4 Database Layer
* **Firebase Firestore**: Cloud document database storing report metadata, image URLs, severity rating, confidence scores, and lifecycle status (`New` -> `Verified` -> `In Progress` -> `Resolved`).

