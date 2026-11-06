import os
import sys
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# Ensure project root is in python path
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from backend.config import settings
from backend.api.health import router as health_router
from backend.api.detection import router as detection_router
from backend.api.reports import router as reports_router

app = FastAPI(
    title="Mysuru RoadWatch API",
    description="Real-Time Road Condition Monitoring System for Mysuru City with YOLO & Firebase",
    version="1.0.0"
)

# Enable CORS for all local origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Routers
app.include_router(health_router, prefix="/api", tags=["Health"])
app.include_router(detection_router, prefix="/api", tags=["Detection"])
app.include_router(reports_router, prefix="/api", tags=["Reports"])

# Static file mounts
# 1. Image uploads and annotated detection results
app.mount("/uploads", StaticFiles(directory=str(settings.IMAGES_DIR)), name="uploads")
# 2. Frontend assets and styles
app.mount("/static", StaticFiles(directory=str(settings.FRONTEND_DIR)), name="static")

# Direct HTML page routes for convenient browsing
def no_cache_response(path):
    response = FileResponse(path)
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

@app.get("/")
def serve_index():
    return no_cache_response(settings.FRONTEND_DIR / "index.html")

@app.get("/index.html")
def serve_index_html():
    return no_cache_response(settings.FRONTEND_DIR / "index.html")

@app.get("/user")
@app.get("/user.html")
def serve_user():
    return no_cache_response(settings.FRONTEND_DIR / "user.html")

@app.get("/authority")
@app.get("/authority.html")
def serve_authority():
    return no_cache_response(settings.FRONTEND_DIR / "authority.html")

@app.get("/report")
@app.get("/report.html")
def serve_report():
    return no_cache_response(settings.FRONTEND_DIR / "report.html")

@app.get("/export")
@app.get("/export.html")
def serve_export():
    return no_cache_response(settings.FRONTEND_DIR / "export.html")

@app.get("/favicon.ico")
def serve_favicon():
    fav_path = settings.FRONTEND_DIR / "favicon.ico"
    if fav_path.exists():
        return FileResponse(fav_path)
    return FileResponse(settings.PROJECT_ROOT.parent / "favicon.ico")

# Serve any frontend static files directly from root path (css/, js/, assets/)
app.mount("/", StaticFiles(directory=str(settings.FRONTEND_DIR), html=True), name="frontend_root")

if __name__ == "__main__":
    import uvicorn
    print("=" * 65)
    print("   MYSURU ROADWATCH — REAL-TIME ROAD CONDITION MONITORING")
    print("=" * 65)
    print(" Server running at: http://localhost:8000")
    print(" User Interface:   http://localhost:8000/user.html")
    print(" Authority Panel:  http://localhost:8000/authority.html")
    print(" Report Tracker:   http://localhost:8000/report.html")
    print(" API Documentation:http://localhost:8000/docs")
    print("=" * 65)
    uvicorn.run("backend.main:app", host=settings.HOST, port=settings.PORT, reload=True)

