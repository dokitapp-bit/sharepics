from fastapi import APIRouter, HTTPException, BackgroundTasks
from ..models.schemas import LeadCreate, LeadResponse
from ..services.database import db
from ..services import whatsapp
from ..utils.qr_generator import generate_lead_qr
import os

router = APIRouter(prefix="/leads", tags=["leads"])

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
UPLOAD_ROOT = os.getenv("UPLOAD_ROOT", os.path.join(os.path.dirname(__file__), "../../uploads"))


@router.post("", response_model=LeadResponse)
async def create_lead(data: LeadCreate, background_tasks: BackgroundTasks):
    event = db.get_event(data.event_id)
    if not event:
        raise HTTPException(404, "Evento não encontrado")

    existing = [l for l in db.list_leads(data.event_id) if l["phone"] == data.phone]
    if existing:
        return LeadResponse(**existing[0])

    lead = db.create_lead(
        name=data.name,
        phone=data.phone,
        email=data.email or "",
        event_id=data.event_id
    )

    qr_path = os.path.join(UPLOAD_ROOT, "qrcodes", "leads", f"{lead['id']}.png")
    os.makedirs(os.path.dirname(qr_path), exist_ok=True)
    generate_lead_qr(lead["id"], lead["lead_number"], event["name"], BASE_URL, qr_path)
    qr_url = f"{BASE_URL}/uploads/qrcodes/leads/{lead['id']}.png"

    gallery_url = f"{BASE_URL}/gallery/{lead['id']}"
    db.update_lead(lead["id"], qr_code_url=qr_url, gallery_url=gallery_url)
    lead["qr_code_url"] = qr_url
    lead["gallery_url"] = gallery_url

    background_tasks.add_task(
        whatsapp.send_event_confirmation,
        data.phone, data.name, lead["lead_number"], event["name"], qr_url
    )

    return LeadResponse(**lead)


@router.get("/event/{event_id}", response_model=list[LeadResponse])
def list_leads(event_id: str):
    leads = db.list_leads(event_id)
    return [LeadResponse(**l) for l in leads]


@router.get("/{lead_id}", response_model=LeadResponse)
def get_lead(lead_id: str):
    lead = db.get_lead(lead_id)
    if not lead:
        raise HTTPException(404, "Lead não encontrado")
    return LeadResponse(**lead)


@router.post("/{lead_id}/notify")
async def notify_lead(lead_id: str):
    lead = db.get_lead(lead_id)
    if not lead:
        raise HTTPException(404, "Lead não encontrado")
    event = db.get_event(lead["event_id"])
    gallery_url = lead.get("gallery_url") or f"{BASE_URL}/gallery/{lead_id}"
    ok = await whatsapp.send_gallery_link(
        lead["phone"], lead["name"], gallery_url, event["name"]
    )
    return {"success": ok, "phone": lead["phone"]}


@router.post("/direct-send")
async def direct_send(
    phone: str,
    name: str,
    event_id: str,
    photo_ids: list[str] = [],
    background_tasks: BackgroundTasks = None,
):
    """Cria ou encontra lead pelo telefone, associa fotos e envia link da galeria via WhatsApp."""
    event = db.get_event(event_id)
    if not event:
        raise HTTPException(404, "Evento não encontrado")

    phone_clean = "".join(filter(str.isdigit, phone))

    existing = [l for l in db.list_leads(event_id) if "".join(filter(str.isdigit, l["phone"])) == phone_clean]
    if existing:
        lead = existing[0]
    else:
        lead = db.create_lead(name=name, phone=phone_clean, email="", event_id=event_id)
        qr_path = os.path.join(UPLOAD_ROOT, "qrcodes", "leads", f"{lead['id']}.png")
        os.makedirs(os.path.dirname(qr_path), exist_ok=True)
        generate_lead_qr(lead["id"], lead["lead_number"], event["name"], BASE_URL, qr_path)
        qr_url = f"{BASE_URL}/uploads/qrcodes/leads/{lead['id']}.png"
        gallery_url = f"{BASE_URL}/gallery/{lead['id']}"
        db.update_lead(lead["id"], qr_code_url=qr_url, gallery_url=gallery_url)
        lead["gallery_url"] = gallery_url

    if photo_ids:
        db.assign_photos_to_lead(photo_ids, lead["id"], lead["lead_number"])

    gallery_url = lead.get("gallery_url") or f"{BASE_URL}/gallery/{lead['id']}"
    if background_tasks:
        background_tasks.add_task(
            whatsapp.send_gallery_link, phone_clean, name, gallery_url, event["name"]
        )

    return {"success": True, "lead_id": lead["id"], "gallery_url": gallery_url}


@router.post("/event/{event_id}/notify-all")
async def notify_all(event_id: str, background_tasks: BackgroundTasks):
    event = db.get_event(event_id)
    if not event:
        raise HTTPException(404, "Evento não encontrado")
    leads = [l for l in db.list_leads(event_id) if l["photo_count"] > 0]
    for lead in leads:
        gallery_url = lead.get("gallery_url") or f"{BASE_URL}/gallery/{lead['id']}"
        background_tasks.add_task(
            whatsapp.send_gallery_link,
            lead["phone"], lead["name"], gallery_url, event["name"]
        )
    return {"queued": len(leads)}
