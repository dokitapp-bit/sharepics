"""
In-memory database for MVP — replace with Firebase Firestore in production.
Provides the same async interface so swap is a one-file change.
"""
import json
import os
import uuid
import time
from datetime import datetime
from typing import Optional, List, Dict, Any


DATA_FILE = os.path.join(os.path.dirname(__file__), "../data/db.json")


def _now() -> str:
    return datetime.utcnow().isoformat() + "Z"


class Database:
    def __init__(self):
        self._path = os.path.abspath(DATA_FILE)
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        self._data: Dict[str, Any] = self._load()

    def _load(self) -> Dict:
        if os.path.exists(self._path):
            try:
                with open(self._path) as f:
                    return json.load(f)
            except Exception:
                pass
        return {"users": {}, "events": {}, "leads": {}, "photos": {}, "counters": {}}

    def _save(self):
        with open(self._path, "w") as f:
            json.dump(self._data, f, indent=2, default=str)

    # --- Users ---

    def create_user(self, name: str, email: str, hashed_pw: str, role: str) -> Dict:
        uid = str(uuid.uuid4())
        user = {"id": uid, "name": name, "email": email, "password": hashed_pw,
                "role": role, "created_at": _now()}
        self._data["users"][uid] = user
        self._save()
        return user

    def get_user_by_email(self, email: str) -> Optional[Dict]:
        for u in self._data["users"].values():
            if u["email"] == email:
                return u
        return None

    def get_user(self, uid: str) -> Optional[Dict]:
        return self._data["users"].get(uid)

    # --- Events ---

    def create_event(self, name: str, description: str, date: str,
                     location: str, organizer_id: str) -> Dict:
        eid = str(uuid.uuid4())
        event = {"id": eid, "name": name, "description": description,
                 "date": date, "location": location, "organizer_id": organizer_id,
                 "qr_code_url": None, "lead_count": 0, "photo_count": 0,
                 "created_at": _now()}
        self._data["events"][eid] = event
        self._save()
        return event

    def get_event(self, event_id: str) -> Optional[Dict]:
        return self._data["events"].get(event_id)

    def list_events(self, organizer_id: Optional[str] = None) -> List[Dict]:
        events = list(self._data["events"].values())
        if organizer_id:
            events = [e for e in events if e["organizer_id"] == organizer_id]
        return sorted(events, key=lambda e: e["created_at"], reverse=True)

    def update_event(self, event_id: str, **kwargs) -> Optional[Dict]:
        if event_id not in self._data["events"]:
            return None
        self._data["events"][event_id].update(kwargs)
        self._save()
        return self._data["events"][event_id]

    # --- Leads ---

    def _next_lead_number(self, event_id: str) -> int:
        key = f"lead_{event_id}"
        n = self._data["counters"].get(key, 1000)
        self._data["counters"][key] = n + 1
        return n

    def create_lead(self, name: str, phone: str, email: str, event_id: str) -> Dict:
        lid = str(uuid.uuid4())
        number = self._next_lead_number(event_id)
        lead = {"id": lid, "lead_number": number, "name": name, "phone": phone,
                "email": email, "event_id": event_id, "qr_code_url": None,
                "photo_count": 0, "gallery_url": None, "created_at": _now()}
        self._data["leads"][lid] = lead
        ev = self._data["events"].get(event_id)
        if ev:
            ev["lead_count"] = ev.get("lead_count", 0) + 1
        self._save()
        return lead

    def get_lead(self, lead_id: str) -> Optional[Dict]:
        return self._data["leads"].get(lead_id)

    def get_lead_by_number(self, event_id: str, number: int) -> Optional[Dict]:
        for l in self._data["leads"].values():
            if l["event_id"] == event_id and l["lead_number"] == number:
                return l
        return None

    def list_leads(self, event_id: str) -> List[Dict]:
        leads = [l for l in self._data["leads"].values() if l["event_id"] == event_id]
        return sorted(leads, key=lambda l: l["lead_number"])

    def update_lead(self, lead_id: str, **kwargs) -> Optional[Dict]:
        if lead_id not in self._data["leads"]:
            return None
        self._data["leads"][lead_id].update(kwargs)
        self._save()
        return self._data["leads"][lead_id]

    # --- Photos ---

    def create_photo(self, filename: str, original_url: str, preview_url: str,
                     thumbnail_url: str, event_id: str,
                     lead_id: Optional[str] = None,
                     lead_number: Optional[int] = None) -> Dict:
        pid = str(uuid.uuid4())
        photo = {"id": pid, "filename": filename, "original_url": original_url,
                 "preview_url": preview_url, "thumbnail_url": thumbnail_url,
                 "event_id": event_id, "lead_id": lead_id,
                 "lead_number": lead_number, "uploaded_at": _now()}
        self._data["photos"][pid] = photo

        ev = self._data["events"].get(event_id)
        if ev:
            ev["photo_count"] = ev.get("photo_count", 0) + 1

        if lead_id and lead_id in self._data["leads"]:
            self._data["leads"][lead_id]["photo_count"] = \
                self._data["leads"][lead_id].get("photo_count", 0) + 1

        self._save()
        return photo

    def list_photos(self, event_id: str, lead_id: Optional[str] = None) -> List[Dict]:
        photos = [p for p in self._data["photos"].values() if p["event_id"] == event_id]
        if lead_id:
            photos = [p for p in photos if p["lead_id"] == lead_id]
        return sorted(photos, key=lambda p: p["uploaded_at"])

    def assign_photos_to_lead(self, photo_ids: List[str], lead_id: str, lead_number: int):
        for pid in photo_ids:
            if pid in self._data["photos"]:
                p = self._data["photos"][pid]
                if not p.get("lead_id"):
                    p["lead_id"] = lead_id
                    p["lead_number"] = lead_number
                    if lead_id in self._data["leads"]:
                        self._data["leads"][lead_id]["photo_count"] = \
                            self._data["leads"][lead_id].get("photo_count", 0) + 1
        self._save()


db = Database()
