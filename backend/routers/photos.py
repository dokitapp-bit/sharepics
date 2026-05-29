import os
import shutil
import uuid
import zipfile
import io
from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends, BackgroundTasks
from fastapi.responses import StreamingResponse
from ..models.schemas import PhotoResponse
from ..services.database import db
from ..services.auth import get_current_user
from ..utils.image_processor import process_image, detect_qr_in_image

router = APIRouter(prefix="/photos", tags=["photos"])

def _base_url():
    return os.getenv("BASE_URL", "http://localhost:8000")

BASE_URL = _base_url()  # kept for compatibility
UPLOAD_ROOT = os.path.abspath(
    os.getenv("UPLOAD_ROOT", os.path.join(os.path.dirname(__file__), "../../uploads"))
)

ALLOWED = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif", ".tiff", ".tif"}

# Per-session QR state: {session_key: (lead_id, lead_number, timestamp)}
_qr_session: dict = {}


@router.post("/upload", response_model=PhotoResponse)
async def upload_photo(
    file: UploadFile = File(...),
    event_id: str = Form(...),
    lead_id: Optional[str] = Form(None),
    session_key: Optional[str] = Form(None),
    user=Depends(get_current_user),
):
    event = db.get_event(event_id)
    if not event:
        raise HTTPException(404, "Evento não encontrado")

    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED:
        raise HTTPException(400, f"Formato não suportado: {ext}")

    stem = str(uuid.uuid4())
    orig_dir = os.path.join(UPLOAD_ROOT, "originals", event_id)
    os.makedirs(orig_dir, exist_ok=True)
    orig_path = os.path.join(orig_dir, f"{stem}{ext}")

    with open(orig_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # Auto-detect QR Code
    qr_data = detect_qr_in_image(orig_path)
    resolved_lead_id = lead_id
    resolved_lead_number = None

    if qr_data and qr_data.startswith("LEAD:"):
        parts = qr_data.split(":")
        if len(parts) >= 3:
            qr_lead_id = parts[1]
            qr_lead_number = int(parts[2])
            session_key = session_key or f"{user['id']}_{event_id}"
            _qr_session[session_key] = (qr_lead_id, qr_lead_number)
            resolved_lead_id = qr_lead_id
            resolved_lead_number = qr_lead_number
    elif session_key and session_key in _qr_session:
        resolved_lead_id, resolved_lead_number = _qr_session[session_key]

    if resolved_lead_id and not resolved_lead_number:
        lead = db.get_lead(resolved_lead_id)
        if lead:
            resolved_lead_number = lead["lead_number"]

    paths = process_image(orig_path, event_id, f"{stem}{ext}", UPLOAD_ROOT)

    base = _base_url()

    def to_url(path: str) -> str:
        rel = os.path.relpath(path, UPLOAD_ROOT)
        return f"{base}/uploads/{rel.replace(os.sep, '/')}"

    photo = db.create_photo(
        filename=file.filename or f"{stem}{ext}",
        original_url=f"{base}/uploads/originals/{event_id}/{stem}{ext}",
        preview_url=to_url(paths["preview_path"]),
        thumbnail_url=to_url(paths["thumb_path"]),
        event_id=event_id,
        lead_id=resolved_lead_id,
        lead_number=resolved_lead_number,
    )
    return PhotoResponse(**photo)


@router.post("/upload-batch")
async def upload_batch(
    files: list[UploadFile] = File(...),
    event_id: str = Form(...),
    session_key: Optional[str] = Form(None),
    user=Depends(get_current_user),
):
    results = []
    for file in files:
        try:
            result = await upload_photo(file, event_id, None, session_key, user)
            results.append({"filename": file.filename, "id": result.id, "status": "ok"})
        except Exception as e:
            results.append({"filename": file.filename, "error": str(e), "status": "error"})
    return {"uploaded": len([r for r in results if r["status"] == "ok"]),
            "errors": len([r for r in results if r["status"] == "error"]),
            "results": results}


@router.get("/event/{event_id}", response_model=list[PhotoResponse])
def list_event_photos(event_id: str, lead_id: Optional[str] = None):
    photos = db.list_photos(event_id, lead_id)
    return [PhotoResponse(**p) for p in photos]


@router.get("/lead/{lead_id}", response_model=list[PhotoResponse])
def list_lead_photos(lead_id: str):
    lead = db.get_lead(lead_id)
    if not lead:
        raise HTTPException(404, "Lead não encontrado")
    photos = db.list_photos(lead["event_id"], lead_id)
    return [PhotoResponse(**p) for p in photos]


@router.post("/assign")
def assign_photos(photo_ids: list[str], lead_id: str, user=Depends(get_current_user)):
    lead = db.get_lead(lead_id)
    if not lead:
        raise HTTPException(404, "Lead não encontrado")
    db.assign_photos_to_lead(photo_ids, lead_id, lead["lead_number"])
    return {"assigned": len(photo_ids)}


@router.get("/event/{event_id}/download")
def download_event_zip(event_id: str):
    event = db.get_event(event_id)
    if not event:
        raise HTTPException(404, "Evento não encontrado")
    photos = db.list_photos(event_id)
    if not photos:
        raise HTTPException(404, "Nenhuma foto encontrada")

    def generate():
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for photo in photos:
                orig_path = photo["original_url"].replace(f"{BASE_URL}/uploads/", "")
                full_path = os.path.join(UPLOAD_ROOT, orig_path.replace("/", os.sep))
                if os.path.exists(full_path):
                    arcname = f"{photo.get('lead_number') or 'sem-lead'}/{photo['filename']}"
                    zf.write(full_path, arcname)
        buffer.seek(0)
        yield from iter(lambda: buffer.read(65536), b"")

    event_slug = event["name"].lower().replace(" ", "-")
    return StreamingResponse(
        generate(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{event_slug}.zip"'}
    )
