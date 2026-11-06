import os
from pathlib import Path

# Paths
CONFIG_DIR = Path(__file__).resolve().parent
BACKEND_DIR = CONFIG_DIR.parent
PROJECT_ROOT = BACKEND_DIR.parent

DATA_DIR = PROJECT_ROOT / "data"
IMAGES_DIR = DATA_DIR / "images"
UPLOADS_DIR = IMAGES_DIR / "uploads"
ANNOTATED_DIR = IMAGES_DIR / "annotated"
FRONTEND_DIR = PROJECT_ROOT / "frontend"
AI_DIR = PROJECT_ROOT / "ai"
MODEL_PATH = AI_DIR / "model" / "best.pt"
LOCAL_DB_PATH = DATA_DIR / "reports_db.json"

# Ensure directories exist
for directory in [DATA_DIR, IMAGES_DIR, UPLOADS_DIR, ANNOTATED_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# Firebase configuration
FIREBASE_CRED_PATH = os.getenv(
    "FIREBASE_CREDENTIALS",
    str(CONFIG_DIR / "serviceAccountKey.json")
)
FIREBASE_STORAGE_BUCKET = os.getenv("FIREBASE_STORAGE_BUCKET", "")

# Server configuration
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", 8000))
DEBUG = os.getenv("DEBUG", "True").lower() == "true"

# Mysuru default geolocation metadata
MYSURU_CITY = "Mysuru, Karnataka"
MYSURU_DEFAULT_LAT = 12.2958
MYSURU_DEFAULT_LNG = 76.6394

# Severity and Status standards
SEVERITY_LEVELS = ["Low", "Moderate", "High", "Critical"]
STATUS_LEVELS = ["New", "Verified", "In Progress", "Resolved"]

