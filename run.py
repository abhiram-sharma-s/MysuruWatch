"""
Mysuru RoadWatch — Quick Launcher Script
Run this script from the project root to start the FastAPI server and launch the app in your browser.

Usage:
    python run.py
"""

import sys
import os
import webbrowser
import time
from pathlib import Path

# Set working directory to mysuru-roadwatch
root_dir = Path(__file__).resolve().parent
app_dir = root_dir / "mysuru-roadwatch"

if app_dir.exists():
    os.chdir(app_dir)
    sys.path.insert(0, str(app_dir))
else:
    sys.path.insert(0, str(root_dir))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    host = "0.0.0.0"

    print("=" * 68)
    print("   MYSURU ROADWATCH — REAL-TIME ROAD CONDITION MONITORING")
    print("=" * 68)
    print(f" Starting FastAPI Server on http://{host}:{port}...")
    print("=" * 68)

    # Optional auto-open browser only on local desktop (PORT not in env)
    if "PORT" not in os.environ:
        def open_browser():
            time.sleep(1.5)
            try:
                webbrowser.open(f"http://localhost:{port}/")
            except Exception:
                pass

        import threading
        threading.Thread(target=open_browser, daemon=True).start()

    import uvicorn
    is_dev = "PORT" not in os.environ
    uvicorn.run("backend.main:app", host=host, port=port, reload=is_dev)

