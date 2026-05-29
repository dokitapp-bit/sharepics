from fastapi import APIRouter, HTTPException, Depends
from ..models.schemas import EventCreate, EventResponse
from ..services.database import db
from ..services.auth import get_current_user
from ..utils.qr_generator import generate_event_qr
import os

router = APIRouter(prefix="/events", tags=["events"])

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
UPLOAD_ROOT = os.getenv("UPLOAD_ROOT", os.path.join(os.path.dirname(__file__), "../../uploads"))


@router.post("", response_model=EventResponse)
def create_event(data: EventCreate, user=Depends(get_current_user)):
    event = db.create_event(
        name=data.name,
        description=data.description or "",
        date=data.date,
        location=data.location or "",
        organizer_id=user["id"]
    )
    qr_path = os.path.join(UPLOAD_ROOT, "qrcodes", "events", f"{event['id']}.png")
    generate_event_qr(event["id"], BASE_URL, qr_path)
    qr_url = f"{BASE_URL}/uploads/qrcodes/events/{event['id']}.png"
    db.update_event(event["id"], qr_code_url=qr_url)
    event["qr_code_url"] = qr_url
    return EventResponse(**event)


@router.get("", response_model=list[EventResponse])
def list_events(user=Depends(get_current_user)):
    events = db.list_events(organizer_id=user["id"])
    return [EventResponse(**e) for e in events]


@router.get("/{event_id}", response_model=EventResponse)
def get_event(event_id: str):
    event = db.get_event(event_id)
    if not event:
        raise HTTPException(404, "Evento não encontrado")
    return EventResponse(**event)


@router.get("/{event_id}/stats")
def event_stats(event_id: str, user=Depends(get_current_user)):
    event = db.get_event(event_id)
    if not event:
        raise HTTPException(404, "Evento não encontrado")
    leads = db.list_leads(event_id)
    photos = db.list_photos(event_id)
    tagged = [p for p in photos if p.get("lead_id")]
    return {
        "event": EventResponse(**event),
        "total_leads": len(leads),
        "total_photos": len(photos),
        "tagged_photos": len(tagged),
        "untagged_photos": len(photos) - len(tagged),
        "leads_with_photos": len([l for l in leads if l["photo_count"] > 0]),
    }
