# Mysuru RoadWatch 🛣️
### Real-Time Road Condition Monitoring System for Mysuru City
*AI-Powered Pothole & Road Damage Detection using YOLO, OpenCV, FastAPI, and Firebase*

---

## 🌟 Overview

**Mysuru RoadWatch** is a modern, responsive web application designed for Mysuru City, Karnataka. It enables citizens to capture road images/videos directly using their smartphone cameras, automatically detect road problems such as **potholes** and **cracks** using **YOLO AI**, tag locations with **Google Maps**, and submit reports to a **Firebase Firestore** backend.

A dedicated **Authority Dashboard** empowers municipal engineers to monitor live reports, review annotated AI images, filter critical issues, and update maintenance statuses.

---

## 🚀 Key Features

* **Mobile Phone Camera Capture**: Citizens can capture live roadway photos using their smartphone's back camera (`facingMode: 'environment'`) or upload media.
* **YOLO & OpenCV Road Damage Detection**: Automatically generates bounding boxes, calculates confidence scores (e.g., 94%), and classifies severity (`Critical`, `High`, `Moderate`, `Low`).
* **Interactive AI Preview**: Instant visual feedback of original vs. annotated road images before submitting.
* **Smart Mysuru Geolocation**: Auto-detects GPS coordinates or provides one-click chips for popular Mysuru roads (Sayyaji Rao Road, KRS Road, Devaraja Urs Road, Hunsur Road, Outer Ring Road) and generates clickable Google Maps links.
* **Firebase Firestore Storage**: Cloud persistence of reports with thread-safe local JSON fallback for offline or zero-configuration demonstrations.
* **Authority Dashboard**: Complete administrative panel featuring real-time KPI metrics, search, severity filters, direct status changers (`New`, `Verified`, `In Progress`, `Resolved`), and inspection modals.
* **Citizen Report Tracking**: Real-time status timeline and tracking by Report ID (`RW-001`, `RW-002`, etc.).
* **Pure Custom CSS**: Modern road/infrastructure theme. **No Bootstrap, React, Angular, Vue, Leaflet, or OpenStreetMap.**

---

## 📁 Project Structure

```text
mysuru-roadwatch/
│
├── frontend/
│   ├── index.html              # Landing portal & live summary
│   ├── user.html               # Citizen camera capture & report submission
│   ├── authority.html          # Authority management dashboard
│   ├── report.html             # Public report tracking by ID
│   │
│   ├── css/
│   │   ├── style.css           # Global infrastructure design system & variables
│   │   ├── user.css            # Citizen camera, dropzone & AI preview styles
│   │   └── authority.css       # Authority table, KPI cards & modal styles
│   │
│   ├── js/
│   │   ├── main.js             # Common utilities, modals, toasts, badges
│   │   ├── user.js             # Camera capture, AI trigger & form handler
│   │   ├── authority.js        # Dashboard metrics, search, filter, CSV export
│   │   └── api.js              # Fetch client communicating with FastAPI
│   │
│   └── assets/
│       └── images/             # Sample road images for demonstration
│
├── backend/
│   ├── main.py                 # FastAPI application & static router
│   ├── requirements.txt        # Backend dependencies
│   │
│   ├── api/
│   │   ├── reports.py          # /api/reports CRUD & status endpoints
│   │   ├── detection.py        # /api/detect YOLO endpoint
│   │   └── health.py           # /api/health endpoint
│   │
│   ├── services/
│   │   ├── firebase_service.py # Firebase Firestore & fallback storage
│   │   ├── yolo_service.py     # YOLO & OpenCV detection engine
│   │   └── image_service.py    # Media storage service
│   │
│   ├── models/
│   │   └── report_model.py     # Pydantic data schemas
│   │
│   └── config/
│       └── settings.py         # Application configuration & Mysuru coords
│
├── ai/
│   ├── detect.py               # Standalone CLI detection script
│   ├── train.py                # Google Colab YOLOv8 training script
│   ├── requirements.txt        # AI requirements
│   └── model/
│       └── best.pt             # Trained YOLO weights
│
├── data/
│   ├── images/                 # Uploads and annotated detection results
│   ├── dataset/                # Dataset placeholder
│   └── reports_db.json         # Local persistent reports store
│
├── docs/
│   ├── architecture.md         # Detailed system architecture
│   └── api.md                  # REST API specification
│
├── .gitignore
├── README.md
└── requirements.txt
```

---

## ⚡ Quick Start & Running the Project

### 1. Install Dependencies

Open a terminal in the project directory:

```bash
pip install -r requirements.txt
```

### 2. Start the FastAPI Server

```bash
python backend/main.py
```

Or using Uvicorn:

```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

The server will start at **`http://localhost:8000`**.

### 3. Open the Interfaces

Open your web browser and navigate to:
* **Landing Portal**: [http://localhost:8000/](http://localhost:8000/)
* **Citizen Reporting**: [http://localhost:8000/user.html](http://localhost:8000/user.html)
* **Authority Dashboard**: [http://localhost:8000/authority.html](http://localhost:8000/authority.html)
* **Report Tracker**: [http://localhost:8000/report.html](http://localhost:8000/report.html)
* **Interactive API Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 🔐 Authority Dashboard Security Password

The Authority Dashboard is protected with a municipal security access clearance.

* **Primary Security Password**: `admin123`
* **Official Municipal Passcode**: `MCC@Mysuru2026` (or `mysuru2026`)
* **Session Management**: Session is maintained during your browser visit. Click **"🔒 Lock Panel"** in the topbar to lock the dashboard anytime.

---

## 🧪 Testing the AI Detection

1. Go to `http://localhost:8000/user.html`.
2. Under **Quick Demo Samples**, click:
   * **`🕳️ Sample: Severe Pothole`**
   * **`⚡ Sample: Road Crack`**
   * **`🛣️ Sample: Surface Wear`**
3. Watch the YOLO engine detect the defects in real time, draw bounding boxes with confidence scores (e.g., **94%**), and rate severity (**High** / **Critical**).
4. Click **Auto-Detect My GPS Coordinates** or select a Mysuru road chip (e.g. *Sayyaji Rao Road*).
5. Click **Submit Road Report**. A unique Report ID (e.g., `RW-006`) is generated.
6. Open the **Authority Dashboard** (`authority.html`) to view the newly submitted report, click **Open in Google Maps**, or change its status to `In Progress` or `Resolved`.

---

## ☁️ Firebase Firestore Setup (Optional)

1. Create a Firebase project in the [Firebase Console](https://console.firebase.google.com/).
2. Enable **Firestore Database**.
3. Generate a private key: **Project Settings -> Service Accounts -> Generate new private key**.
4. Save the downloaded JSON file as `backend/config/serviceAccountKey.json`.
5. Restart the server. The backend will automatically connect to Firebase Firestore!
*(Note: If no key is provided, the system automatically uses a thread-safe local JSON database so the project functions 100% out-of-the-box.)*

---

## 🤖 Google Colab Model Training (`ai/train.py`)

To train your own custom YOLOv8 road damage model:
1. Open [Google Colab](https://colab.research.google.com/) with a GPU runtime.
2. Run `!pip install ultralytics roboflow opencv-python`.
3. Upload your dataset or download the RDD2020 road dataset.
4. Execute `ai/train.py`.
5. Download the trained weights `runs/detect/mysuru_roadwatch/weights/best.pt`.
6. Copy `best.pt` to `ai/model/best.pt`.

---

## 📄 License & Credits

Developed for **Mysuru City Road Quality & Infrastructure Monitoring**. Suitable for college project demonstrations and municipal civic governance presentations.

