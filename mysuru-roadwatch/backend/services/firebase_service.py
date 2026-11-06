import os
import json
import threading
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from backend.config import settings

class FirebaseReportService:
    def __init__(self):
        self.firebase_initialized = False
        self.db = None
        self.lock = threading.Lock()
        self._init_firebase()
        if not self.firebase_initialized:
            self._init_local_db()

    def _init_firebase(self):
        """Attempts to initialize Firebase Firestore using serviceAccountKey.json."""
        cred_path = Path(settings.FIREBASE_CRED_PATH)
        if cred_path.exists():
            try:
                import firebase_admin
                from firebase_admin import credentials, firestore

                if not firebase_admin._apps:
                    cred = credentials.Certificate(str(cred_path))
                    firebase_admin.initialize_app(cred)
                self.db = firestore.client()
                self.firebase_initialized = True
                print(f"[Firebase Service] Connected to Firebase Firestore using credentials at {cred_path}")
            except Exception as e:
                print(f"[Firebase Service] Warning: Firebase init failed ({e}). Falling back to local storage.")
                self.firebase_initialized = False
        else:
            print(f"[Firebase Service] Info: Firebase credentials not found at {cred_path}. Using resilient local JSON database.")

    def _init_local_db(self):
        """Pre-seeds the local database with realistic Mysuru city road reports if empty."""
        with self.lock:
            if not settings.LOCAL_DB_PATH.exists():
                initial_reports = self._get_initial_seed_data()
                with open(settings.LOCAL_DB_PATH, "w", encoding="utf-8") as f:
                    json.dump(initial_reports, f, indent=2)

    def _get_initial_seed_data(self) -> List[Dict[str, Any]]:
        now = datetime.now()
        date_str = now.strftime("%d-%b-%Y")
        time_str = now.strftime("%I:%M %p")

        return [
            {
                "report_id": "RW-001",
                "road_condition": "Pothole",
                "severity": "High",
                "confidence": 0.94,
                "confidence_display": "94%",
                "image": "/uploads/sample_pothole_road.jpg",
                "annotated_image": "/uploads/annotated/annotated_sample_pothole_road.jpg",
                "location": "Sayyaji Rao Road, Near Mysore Palace Gate, Mysuru",
                "google_maps_link": "https://maps.google.com/?q=12.3051,76.6551",
                "description": "Deep depression in asphalt along the primary traffic corridor, hazardous for two-wheelers.",
                "reporter_name": "Mysuru Commuter",
                "road_type": "City road",
                "date": date_str,
                "time": "10:15 AM",
                "status": "New",
                "authority_notes": "Awaiting initial assessment by Ward 14 inspector.",
                "created_at": now.isoformat(),
                "updated_at": now.isoformat()
            },
            {
                "report_id": "RW-002",
                "road_condition": "Severe Pothole Cluster",
                "severity": "Critical",
                "confidence": 0.96,
                "confidence_display": "96%",
                "image": "/uploads/sample_pothole_road.jpg",
                "annotated_image": "/uploads/annotated/annotated_sample_pothole_road.jpg",
                "location": "KRS Road, Near Vijayanagar 2nd Stage, Mysuru",
                "google_maps_link": "https://maps.google.com/?q=12.3385,76.6110",
                "description": "Cluster of deep potholes on the main KRS route leading to hospital area.",
                "reporter_name": "Traffic Warden",
                "road_type": "Highway",
                "date": date_str,
                "time": "11:45 AM",
                "status": "In Progress",
                "authority_notes": "Patchwork crew and road roller dispatched on 12-Oct.",
                "created_at": now.isoformat(),
                "updated_at": now.isoformat()
            },
            {
                "report_id": "RW-003",
                "road_condition": "Road Crack",
                "severity": "Moderate",
                "confidence": 0.89,
                "confidence_display": "89%",
                "image": "/uploads/sample_crack_road.jpg",
                "annotated_image": "/uploads/annotated/annotated_sample_crack_road.jpg",
                "location": "Devaraja Urs Road, Mysuru Commercial Zone",
                "google_maps_link": "https://maps.google.com/?q=12.3082,76.6450",
                "description": "Longitudinal fissure extending over 8 meters along the lane divider.",
                "reporter_name": "Resident Merchant",
                "road_type": "City road",
                "date": date_str,
                "time": "02:30 PM",
                "status": "Verified",
                "authority_notes": "Scheduled for bitumen crack sealing during night shift.",
                "created_at": now.isoformat(),
                "updated_at": now.isoformat()
            },
            {
                "report_id": "RW-004",
                "road_condition": "Alligator Crack",
                "severity": "High",
                "confidence": 0.91,
                "confidence_display": "91%",
                "image": "/uploads/sample_crack_road.jpg",
                "annotated_image": "/uploads/annotated/annotated_sample_crack_road.jpg",
                "location": "Hunsur Main Road, Near Jaladarshini, Mysuru",
                "google_maps_link": "https://maps.google.com/?q=12.3160,76.6340",
                "description": "Extensive crocodile cracking indicating base course fatigue.",
                "reporter_name": "College Bus Driver",
                "road_type": "Highway",
                "date": date_str,
                "time": "04:10 PM",
                "status": "New",
                "authority_notes": "Flagged for priority resurfacing review.",
                "created_at": now.isoformat(),
                "updated_at": now.isoformat()
            },
            {
                "report_id": "RW-005",
                "road_condition": "Pothole",
                "severity": "Low",
                "confidence": 0.88,
                "confidence_display": "88%",
                "image": "/uploads/sample_moderate_road.jpg",
                "annotated_image": "/uploads/annotated/annotated_sample_moderate_road.jpg",
                "location": "Chamundi Hill Road, Near View Point, Mysuru",
                "google_maps_link": "https://maps.google.com/?q=12.2750,76.6710",
                "description": "Shallow surface wear near curve apex.",
                "reporter_name": "Tourist Taxi Operator",
                "road_type": "Hill road",
                "date": date_str,
                "time": "05:00 PM",
                "status": "Resolved",
                "authority_notes": "Cold mix asphalt applied and leveled. Resolved.",
                "created_at": now.isoformat(),
                "updated_at": now.isoformat()
            }
        ]

    def _read_local_reports(self) -> List[Dict[str, Any]]:
        with self.lock:
            if not settings.LOCAL_DB_PATH.exists():
                return []
            try:
                with open(settings.LOCAL_DB_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return []

    def _write_local_reports(self, reports: List[Dict[str, Any]]):
        with self.lock:
            with open(settings.LOCAL_DB_PATH, "w", encoding="utf-8") as f:
                json.dump(reports, f, indent=2)

    def get_next_report_id(self) -> str:
        """Generates a sequential human-readable report ID like RW-006."""
        all_reports = self.get_all_reports()
        if not all_reports:
            return "RW-001"

        highest_num = 0
        for r in all_reports:
            rid = str(r.get("report_id", ""))
            if rid.startswith("RW-"):
                try:
                    num = int(rid.replace("RW-", ""))
                    if num > highest_num:
                        highest_num = num
                except ValueError:
                    continue
        return f"RW-{highest_num + 1:03d}"

    def create_report(self, report_data: Dict[str, Any]) -> Dict[str, Any]:
        """Creates a new road condition report."""
        if not report_data.get("report_id"):
            report_data["report_id"] = self.get_next_report_id()

        now = datetime.now()
        report_data.setdefault("date", now.strftime("%d-%b-%Y"))
        report_data.setdefault("time", now.strftime("%I:%M %p"))
        report_data.setdefault("status", "New")
        report_data.setdefault("created_at", now.isoformat())
        report_data.setdefault("updated_at", now.isoformat())

        if self.firebase_initialized and self.db is not None:
            try:
                doc_ref = self.db.collection("road_reports").document(report_data["report_id"])
                doc_ref.set(report_data)
                return report_data
            except Exception as e:
                print(f"[Firebase Service] Error saving to Firestore ({e}), fallback to local DB.")

        # Local fallback
        reports = self._read_local_reports()
        reports.insert(0, report_data)  # newest first
        self._write_local_reports(reports)
        return report_data

    @staticmethod
    def _extract_report_date_ymd(r: Dict[str, Any]) -> str:
        """Extracts normalized YYYY-MM-DD submission date from a report."""
        created = str(r.get("created_at") or "")
        if len(created) >= 10 and created[4] == '-' and created[7] == '-':
            return created[:10]
        d_str = str(r.get("date") or "").strip()
        if not d_str:
            return ""
        for fmt in ("%d-%b-%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
            try:
                return datetime.strptime(d_str[:11].strip(), fmt).strftime("%Y-%m-%d")
            except Exception:
                pass
        return ""

    def get_all_reports(
        self, 
        status: Optional[str] = None, 
        severity: Optional[str] = None, 
        search: Optional[str] = None, 
        since: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Retrieves reports with optional status, severity, search, since, and submission date range filtering."""
        reports = []
        if self.firebase_initialized and self.db is not None:
            try:
                col = self.db.collection("road_reports")
                query = col.order_by("created_at", direction="DESCENDING")
                docs = query.stream()
                reports = [doc.to_dict() for doc in docs]
            except Exception as e:
                print(f"[Firebase Service] Error reading from Firestore ({e}), fallback to local DB.")
                reports = self._read_local_reports()
        else:
            reports = self._read_local_reports()

        # Apply in-memory filters
        filtered = reports
        if status and isinstance(status, str) and status.lower() != "all":
            filtered = [r for r in filtered if str(r.get("status", "")).lower() == status.lower()]

        if severity and isinstance(severity, str) and severity.lower() != "all":
            filtered = [r for r in filtered if str(r.get("severity", "")).lower() == severity.lower()]

        if since and isinstance(since, str):
            filtered = [
                r for r in filtered
                if r.get("created_at") and str(r.get("created_at")) > since
            ]

        # Submission date range filters (YYYY-MM-DD inclusive bounds)
        if start_date and isinstance(start_date, str) and start_date.strip():
            s_val = start_date.strip()
            filtered = [
                r for r in filtered
                if (self._extract_report_date_ymd(r) or "9999-99-99") >= s_val
            ]

        if end_date and isinstance(end_date, str) and end_date.strip():
            e_val = end_date.strip()
            filtered = [
                r for r in filtered
                if (self._extract_report_date_ymd(r) or "0000-00-00") <= e_val
            ]

        if search and isinstance(search, str):
            q = search.lower()
            filtered = [
                r for r in filtered
                if q in str(r.get("report_id", "")).lower()
                or q in str(r.get("location", "")).lower()
                or q in str(r.get("road_condition", "")).lower()
                or q in str(r.get("description", "")).lower()
            ]

        return filtered

    def get_reports_since(self, since: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieves all reports created strictly after the given ISO timestamp."""
        all_reps = self.get_all_reports()
        if not since or not isinstance(since, str):
            return [r for r in all_reps if r.get("status") == "New"]
        return [r for r in all_reps if r.get("created_at") and str(r.get("created_at")) > since]

    def get_report_by_id(self, report_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a single report by ID."""
        if self.firebase_initialized and self.db is not None:
            try:
                doc = self.db.collection("road_reports").document(report_id).get()
                if doc.exists:
                    return doc.to_dict()
            except Exception as e:
                print(f"[Firebase Service] Error getting doc ({e}), fallback to local DB.")

        reports = self._read_local_reports()
        for r in reports:
            if r.get("report_id", "").upper() == report_id.upper():
                return r
        return None

    def update_report_status(self, report_id: str, new_status: str, notes: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Updates the status and optional notes of a report."""
        valid_statuses = ["New", "Verified", "In Progress", "Resolved"]
        matched_status = next((s for s in valid_statuses if s.lower() == new_status.lower()), None)
        if not matched_status:
            matched_status = new_status

        now_iso = datetime.now().isoformat()

        if self.firebase_initialized and self.db is not None:
            try:
                doc_ref = self.db.collection("road_reports").document(report_id)
                update_payload = {"status": matched_status, "updated_at": now_iso}
                if notes is not None:
                    update_payload["authority_notes"] = notes
                doc_ref.update(update_payload)
                return self.get_report_by_id(report_id)
            except Exception as e:
                print(f"[Firebase Service] Error updating in Firestore ({e}), fallback to local DB.")

        reports = self._read_local_reports()
        for r in reports:
            if r.get("report_id", "").upper() == report_id.upper():
                r["status"] = matched_status
                r["updated_at"] = now_iso
                if notes is not None:
                    r["authority_notes"] = notes
                self._write_local_reports(reports)
                return r
        return None

    def get_stats(self) -> Dict[str, Any]:
        """Calculates system summary statistics."""
        reports = self.get_all_reports()
        total = len(reports)
        new_cnt = sum(1 for r in reports if r.get("status") == "New")
        verified_cnt = sum(1 for r in reports if r.get("status") == "Verified")
        in_progress_cnt = sum(1 for r in reports if r.get("status") == "In Progress")
        resolved_cnt = sum(1 for r in reports if r.get("status") == "Resolved")
        critical_cnt = sum(1 for r in reports if r.get("severity") in ["Critical", "High"])

        pothole_cnt = sum(1 for r in reports if "pothole" in str(r.get("road_condition", "")).lower())
        crack_cnt = sum(1 for r in reports if "crack" in str(r.get("road_condition", "")).lower())

        return {
            "total_reports": total,
            "new_reports": new_cnt,
            "verified_reports": verified_cnt,
            "in_progress_reports": in_progress_cnt,
            "resolved_reports": resolved_cnt,
            "critical_high_reports": critical_cnt,
            "pothole_reports": pothole_cnt,
            "crack_reports": crack_cnt,
            "firebase_connected": self.firebase_initialized
        }

# Global singleton
report_service = FirebaseReportService()

