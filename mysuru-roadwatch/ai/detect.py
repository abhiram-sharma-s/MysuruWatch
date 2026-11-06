"""
Mysuru RoadWatch — Standalone YOLO Road Damage Detection Script
Run inference on images or video files from the command line.

Usage:
  python ai/detect.py --source data/images/sample_pothole_road.jpg
  python ai/detect.py --source 0 (for live webcam)
"""

import sys
import argparse
from pathlib import Path

# Add project root to path
ai_dir = Path(__file__).resolve().parent
project_root = ai_dir.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from backend.services.yolo_service import yolo_detector

def run_detection(source_path: str, save_output: bool = True):
    path = Path(source_path)
    if not path.exists():
        print(f"[Error] Source file '{source_path}' does not exist.")
        sys.exit(1)

    print(f"\nAnalyzing road condition for: {source_path}")
    result = yolo_detector.detect_road_damage(path)

    print("=" * 50)
    print("  MYSURU ROADWATCH DETECTION REPORT")
    print("=" * 50)
    print(f" Detected Condition:  {result['condition']}")
    print(f" Severity Level:      {result['severity']}")
    print(f" AI Confidence:       {result['confidence_display']}")
    print(f" Total Defects:       {len(result['detections'])}")
    print(f" Annotated Result:    {result['annotated_image']}")
    print("=" * 50)

    for idx, d in enumerate(result['detections'], 1):
        print(f"  [{idx}] {d['label']} — Confidence: {int(d['confidence']*100)}% | Severity: {d['severity']} | Box: {d['box']}")

    return result

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Mysuru RoadWatch YOLO Road Damage Detection")
    parser.add_argument("--source", type=str, default="data/images/sample_pothole_road.jpg", help="Path to image or video")
    parser.add_argument("--save", action="store_true", default=True, help="Save annotated image output")
    args = parser.parse_args()

    run_detection(args.source, args.save)

