from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from dotenv import load_dotenv
import os

load_dotenv()

from .routers import auth, events, leads, photos

app = FastAPI(
    title="Shared Pics API",
    description="Plataforma inteligente de compartilhamento de fotos de eventos",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(events.router, prefix="/api")
app.include_router(leads.router, prefix="/api")
app.include_router(photos.router, prefix="/api")

UPLOAD_ROOT = os.path.abspath(
    os.getenv("UPLOAD_ROOT", os.path.join(os.path.dirname(__file__), "../uploads"))
)
os.makedirs(UPLOAD_ROOT, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_ROOT), name="uploads")

FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../frontend"))
app.mount("/static", StaticFiles(directory=os.path.join(FRONTEND_DIR, "static")), name="static")


@app.get("/", include_in_schema=False)
def root():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


@app.get("/register/{event_id}", include_in_schema=False)
def register_page(event_id: str):
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


@app.get("/gallery/{lead_id}", include_in_schema=False)
def gallery_page(lead_id: str):
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


@app.get("/admin/{path:path}", include_in_schema=False)
def admin_page(path: str):
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


@app.get("/health")
def health():
    return {"status": "ok", "service": "Shared Pics API"}
