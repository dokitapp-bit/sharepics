"""
HostFoto — frontend 100% Python (NiceGUI) sobre o FastAPI.

Visual reconstruído a partir do Figma (tema claro, header escuro, cards
brancos, laranja vivo e bottom navigation). Telas:

  /                          Dashboard (resumo, métricas, atalhos)
  /criar-evento              Formulário de novo evento
  /evento/{id}/equipamento   "Como vai capturar as fotos?" (Câmera/iPad/iPhone/Upload)
  /evento/{id}/capturar      Capturar foto + stats do evento
  /evento/{id}               Galeria do evento (adicionar + compartilhar + grid)
  /foto/{id}                 Resultado com QR Code ("Pronto! 🎉")
  /meus-eventos              Lista de eventos + busca
  /galeria                   Galeria geral (escolher evento)
  /upload                    Upload: escolhe evento -> equipamento
  /perfil                    Perfil do organizador (menu de ajustes)
  /e/{id}                    Álbum público do evento (cliente)

Backend reusa db / image_processor / qr_generator. Imagens em caminho
relativo (/uploads/...) e QR/links com a URL pública detectada na requisição.
"""
from __future__ import annotations

import os
import io
import uuid
import shutil
import zipfile
import unicodedata
import urllib.parse
from datetime import datetime

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

load_dotenv()

from .services.database import db
from .services import storage
from .utils.image_processor import process_image
from .utils.qr_generator import generate_qr_base64
from .routers import auth, events, leads, photos

from nicegui import ui, app as ng_app

# ---------------------------------------------------------------------------
# Paleta (extraída do Figma) e caminhos
# ---------------------------------------------------------------------------

ORANGE = "#FF6A00"        # laranja primário (botões, destaques)
ORANGE_DK = "#E85F00"
ORANGE_SOFT = "#FFE7D6"   # fundo suave dos círculos de ícone
HEADER = "#2B2B2B"        # barra superior escura
BG = "#ECECEC"            # fundo cinza claro
CARD = "#FFFFFF"          # cartões brancos
INK = "#1A1A1A"           # texto principal
GRAY = "#8A8A8A"          # texto secundário
BORDER = "#ECECEC"        # bordas/linhas
FIELD = "#F5F5F5"         # fundo dos campos de formulário
GREEN = "#2E7D32"         # badge PRO
LIVE = "#16A34A"          # verde "evento ao vivo"
LIVE_SOFT = "#DCFCE7"     # fundo suave do ícone ao vivo
WHATSAPP = "#25D366"
RED = "#E53935"

BRAND = "SnapShare"          # nome oficial da plataforma

ALLOWED = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif", ".tiff", ".tif"}

UPLOAD_ROOT = os.path.abspath(
    os.getenv("UPLOAD_ROOT", os.path.join(os.path.dirname(__file__), "../uploads"))
)
PWA_DIR = os.path.join(UPLOAD_ROOT, "pwa")
os.makedirs(PWA_DIR, exist_ok=True)

_MESES = ["JAN", "FEV", "MAR", "ABR", "MAI", "JUN",
          "JUL", "AGO", "SET", "OUT", "NOV", "DEZ"]
_MESES_LONGO = ["janeiro", "fevereiro", "março", "abril", "maio", "junho",
                "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]


def base_from_request(request: Request) -> str:
    proto = request.headers.get("x-forwarded-proto") or request.url.scheme
    host = (
        request.headers.get("x-forwarded-host")
        or request.headers.get("host")
        or request.url.netloc
    )
    return f"{proto}://{host}"


def _rel_url(path: str) -> str:
    rel = os.path.relpath(path, UPLOAD_ROOT).replace(os.sep, "/")
    return f"/uploads/{rel}"


def get_default_user() -> dict:
    user = db.get_user_by_email("demo@sharedpics.app")
    if not user:
        user = db.create_user(
            name="Organizador", email="demo@sharedpics.app",
            hashed_pw="x", role="photographer",
        )
    return user


def get_photo(photo_id: str) -> dict | None:
    return db._data["photos"].get(photo_id)


# --- sessão / autenticação simples (MVP) -----------------------------------

def current_user() -> dict | None:
    try:
        uid = ng_app.storage.user.get("uid")
    except Exception:  # noqa: BLE001 — fora de contexto de request
        uid = None
    if uid and uid in db._data["users"]:
        return db._data["users"][uid]
    return None


def login_user(user: dict) -> None:
    ng_app.storage.user["uid"] = user["id"]


def logout_user() -> None:
    try:
        ng_app.storage.user.pop("uid", None)
    except Exception:  # noqa: BLE001
        pass


# Equipamentos coletados no cadastro
TIPOS_EQUIP = ["Câmera DSLR / Mirrorless", "Celular / Tablet", "Action Cam"]
MARCAS_EQUIP = {
    "Câmera DSLR / Mirrorless": ["Canon", "Nikon", "Sony", "Fujifilm",
                                 "Panasonic", "Leica", "Outra"],
    "Celular / Tablet": ["Apple", "Samsung", "Xiaomi", "Motorola", "Outra"],
    "Action Cam": ["GoPro", "DJI", "Insta360", "Outra"],
}


def fmt_date(value: str) -> str:
    """ISO (yyyy-mm-dd) -> '12 OUT 2023'. Devolve o original se não parsear."""
    if not value:
        return ""
    try:
        d = datetime.strptime(value[:10], "%Y-%m-%d")
        return f"{d.day:02d} {_MESES[d.month - 1]} {d.year}"
    except ValueError:
        return value


def fmt_date_br(value: str) -> str:
    """ISO (yyyy-mm-dd) -> '22/06/2026' (padrão Brasil)."""
    if not value:
        return ""
    try:
        d = datetime.strptime(value[:10], "%Y-%m-%d")
        return d.strftime("%d/%m/%Y")
    except ValueError:
        return value


RESERVED_SLUGS = {
    "foto", "evento", "e", "f", "download", "brand", "uploads", "pwa", "api",
    "health", "manifest.webmanifest", "login", "cadastro", "perfil", "upload",
    "galeria", "meus-eventos", "criar-evento", "static", "favicon.ico",
}


def slugify(text: str) -> str:
    """'Casamento da Ana!' -> 'casamento-da-ana' (sem acento, minúsculo)."""
    t = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    out = []
    for ch in t.lower():
        if ch.isalnum():
            out.append(ch)
        elif ch in " -_":
            out.append("-")
    s = "".join(out)
    while "--" in s:
        s = s.replace("--", "-")
    return s.strip("-")


def ensure_user_slug(user: dict) -> str:
    if user.get("slug"):
        return user["slug"]
    base = slugify(user.get("name") or "") or "fotografo"
    taken = {u.get("slug") for u in db._data["users"].values() if u.get("slug")}
    slug, n = base, 2
    while slug in taken or slug in RESERVED_SLUGS:
        slug = f"{base}-{n}"
        n += 1
    db._data["users"][user["id"]]["slug"] = slug
    db._save()
    return slug


def ensure_event_slug(event: dict) -> str:
    if event.get("slug"):
        return event["slug"]
    base = slugify(event.get("name") or "") or "evento"
    taken = {e.get("slug") for e in db._data["events"].values()
             if e.get("organizer_id") == event.get("organizer_id") and e.get("slug")}
    slug, n = base, 2
    while slug in taken:
        slug = f"{base}-{n}"
        n += 1
    db._data["events"][event["id"]]["slug"] = slug
    db._save()
    return slug


def pretty_album_url(base: str, event: dict) -> str:
    """URL amigável do álbum: {base}/{fotografo}/{evento}; fallback /e/{id}."""
    org = db._data["users"].get(event.get("organizer_id"))
    if not org:
        return f"{base}/e/{event['id']}"
    return f"{base}/{ensure_user_slug(org)}/{ensure_event_slug(event)}"


def event_meta(event: dict) -> str:
    loc = (event.get("location") or "").upper()
    date = fmt_date(event.get("date") or "")
    return " • ".join(filter(None, [loc, date]))


def human_size(num_bytes: int) -> str:
    val = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if val < 1024 or unit == "TB":
            if unit in ("B", "KB"):
                return f"{val:.0f} {unit}"
            return f"{val:.1f} {unit}"
        val /= 1024
    return f"{val:.1f} TB"


def event_storage(event_id: str) -> str:
    total = 0
    orig_dir = os.path.join(UPLOAD_ROOT, "originals", event_id)
    if os.path.isdir(orig_dir):
        for root, _dirs, files in os.walk(orig_dir):
            for f in files:
                try:
                    total += os.path.getsize(os.path.join(root, f))
                except OSError:
                    pass
    return human_size(total)


def ingest_photo(event_id: str, filename: str, file_obj) -> dict:
    event = db.get_event(event_id)
    if not event:
        raise ValueError("Evento não encontrado")
    ext = os.path.splitext(filename or "")[1].lower()
    if ext not in ALLOWED:
        raise ValueError(f"Formato não suportado: {ext}")
    stem = str(uuid.uuid4())
    orig_dir = os.path.join(UPLOAD_ROOT, "originals", event_id)
    os.makedirs(orig_dir, exist_ok=True)
    orig_path = os.path.join(orig_dir, f"{stem}{ext}")
    with open(orig_path, "wb") as out:
        shutil.copyfileobj(file_obj, out)
    paths = process_image(orig_path, event_id, f"{stem}{ext}", UPLOAD_ROOT)

    if storage.enabled():
        # sobe os 3 arquivos pro Supabase e usa as URLs públicas (persistem entre deploys)
        orig_url = storage.upload_file(
            orig_path, f"originals/{event_id}/{stem}{ext}")
        preview_url = storage.upload_file(
            paths["preview_path"], f"previews/{event_id}/{stem}.jpg", "image/jpeg")
        thumb_url = storage.upload_file(
            paths["thumb_path"], f"thumbs/{event_id}/{stem}.jpg", "image/jpeg")
        # libera o disco efêmero local
        for p in (orig_path, paths["preview_path"], paths["thumb_path"]):
            try:
                os.remove(p)
            except OSError:
                pass
    else:
        orig_url = _rel_url(orig_path)
        preview_url = _rel_url(paths["preview_path"])
        thumb_url = _rel_url(paths["thumb_path"])

    return db.create_photo(
        filename=filename or f"{stem}{ext}",
        original_url=orig_url,
        preview_url=preview_url,
        thumbnail_url=thumb_url,
        event_id=event_id,
    )


def _generate_pwa_icons() -> None:
    """Ícones do PWA (quadrado laranja com câmera) gerados uma vez."""
    from PIL import Image, ImageDraw
    for size in (180, 512):
        path = os.path.join(PWA_DIR, f"icon-{size}.png")
        if os.path.exists(path):
            continue
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        r = int(size * 0.22)
        d.rounded_rectangle([0, 0, size - 1, size - 1], radius=r, fill=ORANGE)
        bw, bh = int(size * 0.52), int(size * 0.34)
        bx, by = (size - bw) // 2, int(size * 0.36)
        d.rounded_rectangle([bx, by, bx + bw, by + bh], radius=int(size * 0.05), fill="white")
        vw = int(size * 0.16)
        d.rounded_rectangle(
            [bx + int(bw * 0.18), by - int(size * 0.06), bx + int(bw * 0.18) + vw, by + 2],
            radius=int(size * 0.02), fill="white",
        )
        lr = int(size * 0.10)
        cx, cy = size // 2, by + bh // 2
        d.ellipse([cx - lr, cy - lr, cx + lr, cy + lr], fill=ORANGE)
        img.save(path, "PNG")


_generate_pwa_icons()

# ---------------------------------------------------------------------------
# FastAPI base
# ---------------------------------------------------------------------------

app = FastAPI(title=BRAND)

app.include_router(auth.router, prefix="/api")
app.include_router(events.router, prefix="/api")
app.include_router(leads.router, prefix="/api")
app.include_router(photos.router, prefix="/api")

app.mount("/uploads", StaticFiles(directory=UPLOAD_ROOT), name="uploads")
app.mount("/pwa", StaticFiles(directory=PWA_DIR), name="pwa")

BRAND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../design/logo"))
os.makedirs(BRAND_DIR, exist_ok=True)
app.mount("/brand", StaticFiles(directory=BRAND_DIR), name="brand")


def has_logo(name: str) -> bool:
    return os.path.exists(os.path.join(BRAND_DIR, name))


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": f"{BRAND} (Python UI)",
        "storage": "supabase" if storage.enabled() else "local",
        "env_seen": {
            "SUPABASE_URL": bool(os.getenv("SUPABASE_URL")),
            "SUPABASE_SERVICE_KEY": bool(os.getenv("SUPABASE_SERVICE_KEY")),
            "SUPABASE_BUCKET": bool(os.getenv("SUPABASE_BUCKET")),
        },
    }


@app.get("/manifest.webmanifest")
def manifest():
    return JSONResponse({
        "name": BRAND,
        "short_name": BRAND,
        "start_url": "/",
        "display": "standalone",
        "background_color": BG,
        "theme_color": HEADER,
        "icons": [
            {"src": "/pwa/icon-180.png", "sizes": "180x180", "type": "image/png"},
            {"src": "/pwa/icon-512.png", "sizes": "512x512", "type": "image/png"},
        ],
    })


def _orig_path_of(photo: dict) -> str:
    rel = photo["original_url"].split("/uploads/", 1)[-1]
    return os.path.join(UPLOAD_ROOT, rel.replace("/", os.sep))


def photo_original_bytes(photo: dict) -> bytes | None:
    """Bytes do original: disco local se existir, senão busca no Supabase."""
    url = photo.get("original_url", "")
    if "/uploads/" in url:
        full = _orig_path_of(photo)
        if os.path.exists(full):
            with open(full, "rb") as f:
                return f.read()
        return None
    # URL remota (Supabase público)
    return storage.fetch_url_bytes(url)


@app.get("/download/foto/{photo_id}")
def download_single(photo_id: str):
    photo = get_photo(photo_id)
    if not photo:
        raise HTTPException(404, "Foto não encontrada")
    # caminho local rápido quando disponível
    if "/uploads/" in photo.get("original_url", ""):
        full = _orig_path_of(photo)
        if os.path.exists(full):
            return FileResponse(full, filename=photo["filename"],
                                media_type="application/octet-stream")
    data = photo_original_bytes(photo)
    if data is None:
        raise HTTPException(404, "Arquivo não encontrado")
    return StreamingResponse(
        io.BytesIO(data), media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{photo["filename"]}"'},
    )


@app.get("/download/evento/{event_id}")
def download_event_zip(event_id: str):
    event = db.get_event(event_id)
    if not event:
        raise HTTPException(404, "Evento não encontrado")
    photos_ = db.list_photos(event_id)
    if not photos_:
        raise HTTPException(404, "Nenhuma foto neste evento")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in photos_:
            data = photo_original_bytes(p)
            if data is not None:
                zf.writestr(p["filename"], data)
    buffer.seek(0)
    slug = (event["name"].lower().replace(" ", "-") or "album")
    return StreamingResponse(
        buffer, media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{slug}.zip"'},
    )


# ---------------------------------------------------------------------------
# Tema / setup
# ---------------------------------------------------------------------------

def setup() -> None:
    ui.colors(primary=ORANGE)
    ui.dark_mode().disable()
    ui.add_head_html(f"""
      <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
      <meta name="apple-mobile-web-app-capable" content="yes">
      <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
      <meta name="apple-mobile-web-app-title" content="{BRAND}">
      <meta name="theme-color" content="{HEADER}">
      <link rel="manifest" href="/manifest.webmanifest">
      <link rel="apple-touch-icon" href="/pwa/icon-180.png">
      <link rel="preconnect" href="https://fonts.googleapis.com">
      <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
      <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
      <style>
        body {{ background:{BG} !important; font-family:'Poppins',sans-serif; color:{INK}; }}
        .q-page, .nicegui-content {{ background:{BG} !important; }}
        .hf-card {{ background:{CARD}; border-radius:18px;
          box-shadow:0 1px 4px rgba(0,0,0,0.06); }}
        /* campos de formulário (label acima, fundo cinza claro) */
        .hf-field .q-field__control {{ background:{FIELD} !important; border-radius:12px;
          box-shadow:none; height:52px; }}
        .hf-field .q-field__control:before {{ border:1px solid #E3E3E3 !important; }}
        .hf-field .q-field__control:after {{ border-color:{ORANGE} !important; }}
        .hf-field input, .hf-field .q-field__native, .hf-field textarea {{ color:{INK} !important; }}
        .hf-field input::placeholder {{ color:#B0B0B0 !important; }}
        .hf-field .q-icon {{ color:{ORANGE} !important; }}
        /* zona de upload pontilhada (tela 01 / 04) */
        .hf-upload {{ background:transparent !important; box-shadow:none !important;
          border:2px dashed #CFCFCF !important; border-radius:16px !important;
          min-height:200px; }}
        .hf-upload .q-uploader__header {{ background:transparent !important; color:{GRAY} !important; }}
        .hf-upload .q-uploader__subtitle {{ display:none !important; }}
        .hf-upload .q-uploader__list {{ background:transparent !important; min-height:0; }}
        .hf-upload .q-uploader__header-content {{ justify-content:center; color:{INK}; }}
        /* nav inferior */
        .hf-nav-item {{ display:flex; flex-direction:column; align-items:center;
          gap:2px; cursor:pointer; padding:6px 14px; border-radius:9999px; }}
        /* campo de busca na barra superior (pílula clara em qualquer header) */
        .hf-search .q-field__control {{ background:#F0F0F0 !important; border-radius:9999px;
          height:40px; min-height:40px; padding:0 14px; box-shadow:none; }}
        .hf-search .q-field__control:before, .hf-search .q-field__control:after {{
          display:none !important; }}
        .hf-search .q-field__marginal {{ height:40px; }}
        .hf-search input {{ color:{INK} !important; }}
        .hf-search input::placeholder {{ color:#9A9A9A !important; }}
        .hf-search .q-icon {{ color:#9A9A9A !important; }}
      </style>
    """)


# ---------------------------------------------------------------------------
# Componentes reutilizáveis
# ---------------------------------------------------------------------------

def page_container():
    # pb grande p/ não ficar atrás da bottom nav
    return ui.column().classes("w-full max-w-md mx-auto px-4 pt-4 pb-28 gap-4")


def logo(on_dark: bool = True) -> None:
    host = "#FFFFFF" if on_dark else INK
    with ui.row().classes("items-center gap-2 cursor-pointer no-wrap").on(
        "click", lambda: ui.navigate.to("/")
    ):
        if has_logo("icon.png"):
            ui.image("/brand/icon.png").style("height:32px;width:32px").props("no-spinner")
            ui.html('<span style="font-weight:800;font-size:19px;letter-spacing:-.3px">'
                    f'<span style="color:{host}">Snap</span>'
                    f'<span style="color:{ORANGE}">Share</span></span>')
        else:
            with ui.element("div").classes("flex items-center justify-center").style(
                f"width:34px;height:34px;border-radius:9px;background:{ORANGE}"
            ):
                ui.icon("photo_camera").classes("text-white").style("font-size:20px")
            ui.html('<span style="font-weight:800;font-size:19px;letter-spacing:-.3px">'
                    f'<span style="color:{host}">Snap</span>'
                    f'<span style="color:{ORANGE}">Share</span></span>')


def brand_big() -> None:
    """Logo grande para telas de login/cadastro."""
    if has_logo("logo.png"):
        ui.image("/brand/logo.png").style("height:64px").props("no-spinner")
    elif has_logo("icon.png"):
        ui.image("/brand/icon.png").style("height:72px;width:72px").props("no-spinner")
        ui.html('<span style="font-weight:800;font-size:26px">'
                f'<span style="color:{INK}">Snap</span>'
                f'<span style="color:{ORANGE}">Share</span></span>')
    else:
        with ui.element("div").classes("flex items-center justify-center").style(
            f"width:64px;height:64px;border-radius:16px;background:{ORANGE}"):
            ui.icon("photo_camera").classes("text-white").style("font-size:36px")
        ui.html('<span style="font-weight:800;font-size:26px">'
                f'<span style="color:{INK}">Snap</span>'
                f'<span style="color:{ORANGE}">Share</span></span>')


def logo_mark(on_dark: bool = True) -> None:
    """Só a marca (ícone) clicável que volta pra home — usada quando há busca."""
    el = ui.element("div").classes("cursor-pointer shrink-0").on(
        "click", lambda: ui.navigate.to("/"))
    with el:
        if has_logo("icon.png"):
            ui.image("/brand/icon.png").style("height:32px;width:32px").props("no-spinner")
        else:
            with ui.element("div").classes("flex items-center justify-center").style(
                f"width:32px;height:32px;border-radius:9px;background:{ORANGE}"):
                ui.icon("photo_camera").classes("text-white").style("font-size:18px")


def search_field() -> None:
    """Campo de busca de evento (nome, data ou local) — vai pra /meus-eventos."""
    inp = ui.input(placeholder="Buscar evento por nome, data ou local…").props(
        "dense borderless").classes("hf-search flex-1")
    with inp.add_slot("prepend"):
        ui.icon("search")

    def go():
        term = (inp.value or "").strip()
        ui.navigate.to(f"/meus-eventos?q={urllib.parse.quote(term)}"
                       if term else "/meus-eventos")

    inp.on("keydown.enter", lambda: go())


def top_bar(show_back: bool = False, search: bool = False) -> None:
    """Barra superior escura. Com busca: marca + campo de busca."""
    with ui.header().classes("items-center px-4 gap-3 no-wrap").style(
        f"background:{HEADER};height:60px;box-shadow:0 1px 0 rgba(0,0,0,0.2)"
    ):
        if show_back:
            ui.icon("arrow_back").classes("cursor-pointer shrink-0").style(
                f"color:{ORANGE};font-size:24px").on("click", lambda: ui.navigate.back())
        if search:
            logo_mark(on_dark=True)
            search_field()
        else:
            logo(on_dark=True)


def page_title(text: str) -> None:
    ui.label(text).style(
        f"color:{INK};font-weight:800;font-size:24px;line-height:1.2")


def light_bar() -> None:
    """Barra clara da Home (logo + busca)."""
    with ui.header().classes("items-center px-4 gap-3 no-wrap").style(
        f"background:{CARD};height:60px;border-bottom:1px solid {BORDER}"
    ):
        logo_mark(on_dark=False)
        search_field()


NAV = [
    ("Home", "home", "/"),
    ("Eventos", "calendar_month", "/meus-eventos"),
    ("Upload", "cloud_upload", "/upload"),
    ("Perfil", "person", "/perfil"),
]


def bottom_nav(active: str = "") -> None:
    with ui.footer(fixed=True).classes("justify-around items-center px-2").style(
        f"background:{CARD};height:64px;border-top:1px solid {BORDER};"
        "position:fixed;left:0;right:0;bottom:0;z-index:1000"
    ):
        for label, icon, route in NAV:
            is_active = label == active
            color = "#FFFFFF" if is_active else GRAY
            bg = ORANGE if is_active else "transparent"
            with ui.element("div").classes("hf-nav-item").style(
                f"background:{bg}").on("click", lambda r=route: ui.navigate.to(r)):
                ui.icon(icon).style(f"color:{color};font-size:22px")
                ui.label(label).style(f"color:{color};font-size:11px;font-weight:600")


def icon_circle(name: str, size: int = 56, bg: str = ORANGE_SOFT,
                fg: str = ORANGE) -> None:
    with ui.element("div").classes("flex items-center justify-center shrink-0").style(
        f"width:{size}px;height:{size}px;border-radius:14px;background:{bg}"
    ):
        ui.icon(name).style(f"color:{fg};font-size:{int(size*0.48)}px")


def primary_button(text: str, on_click, icon: str | None = None,
                   full: bool = True) -> None:
    btn = ui.button(text, icon=icon, on_click=on_click).props("unelevated").style(
        f"background:{ORANGE};color:#fff;border-radius:14px;height:54px;"
        "font-weight:700;font-size:15px;letter-spacing:.3px")
    btn.classes("w-full" if full else "")


def outline_button(text: str, on_click, icon: str | None = None) -> None:
    ui.button(text, icon=icon, on_click=on_click).props("outline").style(
        f"color:{ORANGE};border:2px solid {ORANGE};border-radius:14px;height:54px;"
        "font-weight:700;font-size:14px").classes("w-full")


def open_share(title: str, url: str, download_url: str | None = None,
               subtitle: str = "") -> None:
    """Menu de compartilhamento: WhatsApp, SMS, E-mail, (Baixar) e Copiar."""
    msg = f"{title}: {url}"
    wa = "https://wa.me/?text=" + urllib.parse.quote(msg)
    sms = "sms:?&body=" + urllib.parse.quote(msg)
    mail = ("mailto:?subject=" + urllib.parse.quote(title)
            + "&body=" + urllib.parse.quote(msg))

    with ui.dialog() as d, ui.card().classes("w-80 gap-3 p-5 items-stretch").style(
        f"background:{CARD};border-radius:20px"):
        ui.label("Compartilhar").style(
            f"color:{INK};font-weight:800;font-size:18px")
        ui.label(subtitle or "Envie por onde preferir.").style(
            f"color:{GRAY};font-size:13px")

        def opt(icon, label, color, action):
            el = ui.element("div").classes(
                "w-full flex items-center gap-3 p-3 cursor-pointer").style(
                f"background:{FIELD};border-radius:12px")
            with el.on("click", action):
                icon_circle(icon, 40, "#fff", color)
                ui.label(label).style(f"color:{INK};font-weight:600;flex:1")
                ui.icon("chevron_right").style(f"color:{GRAY}")

        opt("chat", "WhatsApp", WHATSAPP, lambda: ui.navigate.to(wa, new_tab=True))
        opt("sms", "SMS", "#2196F3", lambda: ui.navigate.to(sms))
        opt("mail", "E-mail", ORANGE, lambda: ui.navigate.to(mail))
        if download_url:
            opt("download", "Baixar", "#2E7D32",
                lambda u=download_url: ui.download(u))
        opt("content_copy", "Copiar link", INK,
            lambda: (ui.clipboard.write(url), ui.notify("Link copiado!", type="positive")))
        ui.button("Fechar", on_click=d.close).props("flat").style(f"color:{GRAY}")
    d.open()


def open_album_qr(event_name: str, url: str) -> None:
    """QR Code do álbum inteiro — baixa/abre todas as fotos do evento."""
    with ui.dialog() as d, ui.card().classes("w-80 gap-3 p-6 items-center").style(
        f"background:{CARD};border-radius:20px"):
        ui.label("QR do álbum").style(f"color:{INK};font-weight:800;font-size:20px")
        ui.label(f"Escaneie para ver e baixar todas as fotos do {event_name}.").style(
            f"color:{GRAY};font-size:13px;text-align:center")
        ui.image(generate_qr_base64(url)).classes("w-56 h-56").style(
            f"border-radius:16px;background:#fff;padding:10px;"
            f"box-shadow:0 0 0 4px {ORANGE}, 0 0 28px rgba(255,106,0,0.45)")
        ui.label(url).style(
            f"color:{GRAY};font-size:11px;text-align:center;word-break:break-all")
        primary_button("Abrir álbum", lambda: ui.navigate.to(url, new_tab=True),
                       icon="open_in_new")
        ui.button("Copiar link", icon="content_copy",
                  on_click=lambda: (ui.clipboard.write(url),
                                    ui.notify("Link copiado!", type="positive"))).props(
            "flat").style(f"color:{ORANGE}")
    d.open()


# ---------------------------------------------------------------------------
# Zona de upload / captura
# ---------------------------------------------------------------------------

def capture_card(event_id: str, on_done=None) -> None:
    """Card branco com zona pontilhada estilo tela 01."""
    def handle_upload(e):
        try:
            photo = ingest_photo(event_id, e.name, e.content)
            if on_done:
                on_done(photo)
            else:
                ui.navigate.to(f"/foto/{photo['id']}")
        except Exception as exc:  # noqa: BLE001
            ui.notify(f"Erro ao processar a foto: {exc}", type="negative")

    with ui.element("div").classes("hf-card w-full p-3"):
        with ui.column().classes("w-full items-center gap-1 py-4 hf-upload"):
            icon_circle("add_a_photo", 72, ORANGE_SOFT, ORANGE)
            ui.label("Toque para tirar foto").style(
                f"color:{INK};font-weight:700;font-size:18px;margin-top:8px")
            ui.label("ou escolher da galeria do seu dispositivo").style(
                f"color:{GRAY};font-size:13px;text-align:center")
        ui.upload(multiple=True, auto_upload=True, on_upload=handle_upload,
                  label="Selecionar fotos").props(
            'flat accept="image/*" color=orange').classes("w-full")


# ---------------------------------------------------------------------------
# LOGIN / CADASTRO
# ---------------------------------------------------------------------------

def auth_container():
    return ui.column().classes(
        "w-full max-w-md mx-auto px-6 pt-10 pb-16 gap-3 items-stretch")


def labeled_input(label: str, placeholder: str = "", value: str = "",
                  icon: str | None = None, date: bool = False):
    ui.label(label).style(f"color:{INK};font-weight:700;font-size:14px;margin-top:6px")
    inp = ui.input(placeholder=placeholder, value=value).props("outlined dense").classes(
        "w-full hf-field")
    if date:
        inp.props("type=date")
    if icon:
        with inp.add_slot("prepend"):
            ui.icon(icon)
    return inp


@ui.page("/login")
def login_page():
    setup()
    if current_user():
        ui.navigate.to("/")
        return
    with auth_container():
        with ui.column().classes("w-full items-center gap-2 py-4"):
            brand_big()
        ui.label("Entrar").style(
            f"color:{INK};font-weight:800;font-size:24px;text-align:center;width:100%")
        ui.label("Acesse sua conta para gerenciar seus eventos.").style(
            f"color:{GRAY};font-size:14px;text-align:center;width:100%")
        email = labeled_input("E-mail", "voce@email.com", icon="mail")

        def do_login():
            u = db.get_user_by_email((email.value or "").strip())
            if not u:
                ui.notify("Conta não encontrada. Crie a sua conta.", type="warning")
                return
            login_user(u)
            ui.navigate.to("/")

        primary_button("Entrar", do_login, icon="login")
        with ui.row().classes("w-full justify-center gap-1").style("margin-top:6px"):
            ui.label("Não tem conta?").style(f"color:{GRAY}")
            ui.label("Criar conta").classes("cursor-pointer").style(
                f"color:{ORANGE};font-weight:700").on(
                "click", lambda: ui.navigate.to("/cadastro"))


@ui.page("/cadastro")
def cadastro_page():
    setup()
    with auth_container():
        with ui.column().classes("w-full items-center gap-2 py-2"):
            brand_big()
        ui.label("Criar conta").style(
            f"color:{INK};font-weight:800;font-size:24px;text-align:center;width:100%")
        ui.label("Conte um pouco sobre você e seu equipamento.").style(
            f"color:{GRAY};font-size:14px;text-align:center;width:100%")

        with ui.element("div").classes("hf-card w-full p-5 flex flex-col gap-1"):
            nome = labeled_input("Nome Completo", "Seu nome", icon="person")
            estado = labeled_input("Estado", "Ex: SP", icon="map")
            cidade = labeled_input("Cidade", "Ex: Santos", icon="location_city")
            email = labeled_input("E-mail", "voce@email.com", icon="mail")
            whats = labeled_input("WhatsApp", "(00) 00000-0000", icon="chat")

            ui.label("Tipo de equipamento").style(
                f"color:{INK};font-weight:700;font-size:14px;margin-top:6px")
            tipo = ui.select(TIPOS_EQUIP, value=TIPOS_EQUIP[0]).props(
                "outlined dense").classes("w-full hf-field")

            ui.label("Marca do equipamento").style(
                f"color:{INK};font-weight:700;font-size:14px;margin-top:6px")
            marca = ui.select(MARCAS_EQUIP[TIPOS_EQUIP[0]],
                              value=MARCAS_EQUIP[TIPOS_EQUIP[0]][0]).props(
                "outlined dense").classes("w-full hf-field")

            def on_tipo():
                opts = MARCAS_EQUIP.get(tipo.value, ["Outra"])
                marca.options = opts
                marca.value = opts[0]
                marca.update()

            tipo.on("update:model-value", lambda e: on_tipo())

        def criar_conta():
            if not (nome.value or "").strip() or not (email.value or "").strip():
                ui.notify("Preencha nome e e-mail.", type="warning")
                return
            if db.get_user_by_email(email.value.strip()):
                ui.notify("Já existe conta com esse e-mail. Faça login.", type="warning")
                return
            u = db.create_user(name=nome.value.strip(), email=email.value.strip(),
                               hashed_pw="x", role="photographer")
            db._data["users"][u["id"]].update({
                "state": estado.value or "",
                "city": cidade.value or "",
                "phone": whats.value or "",
                "equipment_type": tipo.value,
                "equipment_brand": marca.value,
            })
            db._save()
            login_user(u)
            ui.notify("Conta criada! Bem-vindo 🎉", type="positive")
            ui.navigate.to("/")

        primary_button("Criar conta", criar_conta, icon="check")
        with ui.row().classes("w-full justify-center gap-1").style("margin-top:6px"):
            ui.label("Já tem conta?").style(f"color:{GRAY}")
            ui.label("Entrar").classes("cursor-pointer").style(
                f"color:{ORANGE};font-weight:700").on(
                "click", lambda: ui.navigate.to("/login"))


# ---------------------------------------------------------------------------
# DASHBOARD (tela 03)
# ---------------------------------------------------------------------------

@ui.page("/")
def dashboard():
    setup()
    user = current_user()
    if not user:
        ui.navigate.to("/login")
        return
    light_bar()
    events_ = db.list_events(organizer_id=user["id"])
    n_eventos = len(events_)
    total_fotos = sum(len(db.list_photos(e["id"])) for e in events_)
    n_leads = sum(len(db.list_leads(e["id"])) for e in events_)
    mes = _MESES_LONGO[datetime.now().month - 1].capitalize()

    def metric(label, value, extra="", extra_color=GREEN, icon=None):
        with ui.element("div").classes("hf-card p-4 flex flex-col gap-1").style("min-height:120px"):
            ui.label(label.upper()).style(
                f"color:{GRAY};font-size:11px;font-weight:700;letter-spacing:.5px")
            ui.label(str(value)).style(f"color:{INK};font-weight:800;font-size:26px")
            if extra:
                ui.label(extra).style(f"color:{extra_color};font-size:12px;font-weight:600")

    live = None
    if events_:
        live = sorted(events_, key=lambda e: e.get("created_at", ""), reverse=True)[0]

    with page_container():
        ui.label(f"Olá, fotógrafo! {mes} está rendendo.").style(
            f"color:{INK};font-weight:700;font-size:20px;line-height:1.25")
        ui.label("Aqui está o resumo da sua atividade.").style(
            f"color:{GRAY};font-size:14px")

        # evento ao vivo — acesso rápido ao voltar pro app
        if live:
            n_fotos_live = len(db.list_photos(live["id"]))
            card = ui.element("div").classes(
                "w-full p-4 flex items-center gap-3 cursor-pointer").style(
                f"background:{CARD};border:2px solid {LIVE};border-radius:18px;"
                f"box-shadow:0 2px 10px rgba(22,163,74,0.18)")
            with card.on("click", lambda e=live: ui.navigate.to(f"/evento/{e['id']}/capturar")):
                with ui.element("div").classes("flex items-center justify-center shrink-0").style(
                    f"width:48px;height:48px;border-radius:14px;background:{LIVE_SOFT}"):
                    ui.icon("radio_button_checked").style(f"color:{LIVE};font-size:26px")
                with ui.column().classes("gap-0").style("flex:1"):
                    with ui.row().classes("items-center gap-2 no-wrap"):
                        ui.element("div").style(
                            f"width:8px;height:8px;border-radius:9999px;background:{LIVE}")
                        ui.label("EVENTO AO VIVO").style(
                            f"color:{LIVE};font-weight:800;font-size:11px;letter-spacing:.5px")
                    ui.label(live["name"]).style(f"color:{INK};font-weight:700;font-size:17px")
                    ui.label(f"{n_fotos_live} fotos • toque para enviar agora").style(
                        f"color:{GRAY};font-size:12px")
                ui.icon("chevron_right").style(f"color:{GRAY}")

        with ui.element("div").classes("w-full grid grid-cols-2 gap-3"):
            metric("Fotos entregues", f"{total_fotos:,}".replace(",", "."),
                   "▲ entregues no mês")
            metric("Eventos", n_eventos, "ativos e arquivados")
            metric("Leads gerados", n_leads, "convidados capturados")
            metric("Download rate", "91%", "Excelente retenção")

        # card laranja: criar evento
        with ui.element("div").classes(
            "w-full p-5 flex items-center gap-4 cursor-pointer").style(
            f"background:{ORANGE};border-radius:18px").on(
            "click", lambda: ui.navigate.to("/criar-evento")):
            with ui.element("div").classes("flex items-center justify-center shrink-0").style(
                "width:48px;height:48px;border-radius:12px;background:rgba(0,0,0,0.18)"):
                ui.icon("add").style("color:#fff;font-size:28px")
            with ui.column().classes("gap-0"):
                ui.label("Criar Evento").style("color:#fff;font-weight:800;font-size:18px")
                ui.label("Novo álbum com QR e WhatsApp").style(
                    "color:rgba(255,255,255,0.9);font-size:13px")

        # últimos eventos
        if events_:
            with ui.row().classes("w-full items-center justify-between").style("margin-top:4px"):
                ui.label("Últimos Eventos").style(
                    f"color:{INK};font-weight:700;font-size:16px")
                ui.label("Ver tudo").style(
                    f"color:{ORANGE};font-weight:600;font-size:13px").classes(
                    "cursor-pointer").on("click", lambda: ui.navigate.to("/meus-eventos"))
            with ui.element("div").classes("hf-card w-full p-0 overflow-hidden"):
                for i, ev in enumerate(events_[:3]):
                    fotos = db.list_photos(ev["id"])
                    n_lead = len(db.list_leads(ev["id"]))
                    row = ui.element("div").classes(
                        "w-full flex items-center gap-3 p-3 cursor-pointer").style(
                        "" if i == 0 else f"border-top:1px solid {BORDER}")
                    with row.on("click", lambda e=ev: ui.navigate.to(f"/evento/{e['id']}")):
                        if fotos:
                            ui.image(fotos[-1]["thumbnail_url"]).classes(
                                "w-12 h-12 object-cover").style("border-radius:10px")
                        else:
                            icon_circle("image", 48, "#F0F0F0", GRAY)
                        with ui.column().classes("gap-0").style("flex:1"):
                            ui.label(ev["name"]).style(
                                f"color:{INK};font-weight:700;font-size:15px")
                            ui.label(f"{len(fotos)} fotos • {n_lead} leads").style(
                                f"color:{GRAY};font-size:12px")
                        ui.icon("chevron_right").style(f"color:{GRAY}")

    bottom_nav("Home")


# ---------------------------------------------------------------------------
# CRIAR EVENTO (tela 02)
# ---------------------------------------------------------------------------

@ui.page("/criar-evento")
def criar_evento():
    setup()
    user = current_user()
    if not user:
        ui.navigate.to("/login")
        return
    top_bar(show_back=True)

    def field(label: str, placeholder: str, icon: str | None = None,
              date: bool = False):
        ui.label(label).style(
            f"color:{INK};font-weight:700;font-size:14px;margin-top:6px")
        inp = ui.input(placeholder=placeholder).props("outlined dense").classes(
            "w-full hf-field")
        if date:
            inp.props("type=date")
        if icon:
            with inp.add_slot("prepend"):
                ui.icon(icon)
        return inp

    with page_container():
        page_title("Criar Novo Evento")
        with ui.element("div").classes("hf-card w-full p-5 flex flex-col gap-1"):
            nome = field("Nome do Evento", "Ex: Casamento Silva")
            data = field("Data", "", date=True)
            local = field("Localização", "Cidade, Estado ou Local", "location_on")
            email = field("E-mail de Contato", "contato@evento.com", "mail")
            fone = field("Telefone", "(00) 00000-0000", "phone")

        def criar():
            if not nome.value:
                ui.notify("Informe o nome do evento", type="warning")
                return
            ev = db.create_event(
                name=nome.value, description="", date=data.value or "",
                location=local.value or "", organizer_id=user["id"],
            )
            db.update_event(ev["id"], organizer_email=email.value or "",
                            organizer_phone=fone.value or "")
            ui.navigate.to(f"/evento/{ev['id']}/capturar")

        primary_button("CRIAR EVENTO", criar, icon="event")

    bottom_nav()


# ---------------------------------------------------------------------------
# EQUIPAMENTO / "Como vai capturar?" (tela 05)
# ---------------------------------------------------------------------------

@ui.page("/evento/{event_id}/equipamento")
def equipamento(event_id: str):
    setup()
    event = db.get_event(event_id)
    top_bar(show_back=True)
    if not event:
        with page_container():
            ui.label("Evento não encontrado").style(f"color:{INK}")
        bottom_nav("Upload")
        return

    metodos = [
        ("Câmera", "DSLR / Mirrorless", "photo_camera"),
        ("iPad", "Câmera do iPad", "tablet_mac"),
        ("iPhone", "Câmera do iPhone", "phone_iphone"),
        ("Upload", "Rolo da câmera / pastas", "cloud_upload"),
    ]
    selecionado = {"idx": None}  # nenhum método marcado por padrão

    with page_container():
        ui.label("Como vai capturar as fotos?").style(
            f"color:{INK};font-weight:800;font-size:26px;line-height:1.2")
        ui.label("Selecione o dispositivo ou método de entrada para iniciar o evento.").style(
            f"color:{GRAY};font-size:14px")

        @ui.refreshable
        def opcoes():
            for i, (titulo, sub, icon) in enumerate(metodos):
                ativo = selecionado["idx"] == i
                card = ui.element("div").classes(
                    "hf-card w-full flex items-center gap-4 p-4 cursor-pointer").style(
                    f"border:2px solid {ORANGE}" if ativo else "border:2px solid transparent")
                with card.on("click", lambda x=i: (selecionado.update(idx=x), opcoes.refresh())):
                    icon_circle(icon, 56, ORANGE if ativo else "#F0F0F0",
                                "#fff" if ativo else INK)
                    with ui.column().classes("gap-0"):
                        ui.label(titulo).style(f"color:{INK};font-weight:700;font-size:18px")
                        ui.label(sub).style(f"color:{GRAY};font-size:13px")

        opcoes()
        primary_button("CONTINUAR",
                       lambda: ui.navigate.to(f"/evento/{event_id}/capturar"))

    bottom_nav("Upload")


# ---------------------------------------------------------------------------
# CAPTURAR + STATS (tela 01)
# ---------------------------------------------------------------------------

@ui.page("/evento/{event_id}/capturar")
def capturar_page(event_id: str):
    setup()
    event = db.get_event(event_id)
    top_bar(show_back=True)
    if not event:
        with page_container():
            ui.label("Evento não encontrado").style(f"color:{INK}")
        bottom_nav("Upload")
        return
    fotos = db.list_photos(event_id)
    with page_container():
        ui.label(event["name"]).style(
            f"color:{INK};font-weight:800;font-size:24px;line-height:1.2")
        meta = event_meta(event)
        if meta:
            ui.label(meta).style(f"color:{GRAY};font-size:13px;font-weight:600")

        capture_card(event_id)

        with ui.element("div").classes("w-full grid grid-cols-2 gap-3"):
            with ui.element("div").classes("hf-card p-4 flex flex-col gap-1"):
                ui.label("Fotos enviadas").style(f"color:{GRAY};font-size:12px;font-weight:600")
                ui.label(str(len(fotos))).style(f"color:{INK};font-weight:800;font-size:24px")
            with ui.element("div").classes("hf-card p-4 flex flex-col gap-1"):
                ui.label("Armazenamento").style(f"color:{GRAY};font-size:12px;font-weight:600")
                ui.label(event_storage(event_id)).style(
                    f"color:{INK};font-weight:800;font-size:24px")

        with ui.element("div").classes("hf-card w-full p-4 flex items-start gap-3").style(
            f"background:{FIELD}"):
            icon_circle("info", 40, "#E6E6E6", GRAY)
            with ui.column().classes("gap-0").style("flex:1"):
                ui.label("Dica de fotógrafo").style(f"color:{INK};font-weight:700;font-size:14px")
                ui.label("Mantenha o foco manual em ambientes com pouca luz para "
                         "melhores resultados.").style(f"color:{GRAY};font-size:13px")

        outline_button("Ver galeria do evento",
                       lambda: ui.navigate.to(f"/evento/{event_id}"), icon="photo_library")

    bottom_nav("Upload")


# ---------------------------------------------------------------------------
# GALERIA DO EVENTO (tela 04)
# ---------------------------------------------------------------------------

@ui.page("/evento/{event_id}")
def evento_detalhe(event_id: str, request: Request):
    setup()
    event = db.get_event(event_id)
    top_bar(show_back=True)
    if not event:
        with page_container():
            ui.label("Evento não encontrado").style(f"color:{INK}")
        bottom_nav("Eventos")
        return
    base = base_from_request(request)
    album = pretty_album_url(base, event)
    photos_ = db.list_photos(event_id)
    with page_container():
        ui.label("GALERIA DO EVENTO").style(
            f"color:{ORANGE};font-weight:700;font-size:12px;letter-spacing:.5px")
        ui.label(event["name"]).style(
            f"color:{INK};font-weight:800;font-size:24px;line-height:1.2")
        with ui.row().classes("items-center gap-4 no-wrap"):
            if event.get("date"):
                with ui.row().classes("items-center gap-1 no-wrap"):
                    ui.icon("calendar_today").style(f"color:{GRAY};font-size:15px")
                    ui.label(fmt_date(event["date"])).style(f"color:{GRAY};font-size:13px")
            if event.get("location"):
                with ui.row().classes("items-center gap-1 no-wrap"):
                    ui.icon("location_on").style(f"color:{GRAY};font-size:15px")
                    ui.label(event["location"]).style(f"color:{GRAY};font-size:13px")

        with ui.row().classes("w-full gap-3 no-wrap").style("margin-top:4px"):
            ui.button("ADICIONAR FOTOS", icon="add_a_photo",
                      on_click=lambda: ui.navigate.to(f"/evento/{event_id}/capturar")).props(
                "unelevated").style(
                f"background:{ORANGE};color:#fff;border-radius:12px;height:48px;"
                "font-weight:700;font-size:12px").classes("flex-1")
            ui.button("COMPARTILHAR", icon="share",
                      on_click=lambda: open_share(
                          f"Álbum {event['name']}", album,
                          subtitle="Link com todas as fotos do evento.")).props(
                "outline").style(
                f"color:{ORANGE};border:2px solid {ORANGE};border-radius:12px;height:48px;"
                "font-weight:700;font-size:12px").classes("flex-1")

        with ui.row().classes("w-full items-center justify-between").style("margin-top:6px"):
            ui.label(f"Fotos ({len(photos_)})").style(
                f"color:{INK};font-weight:800;font-size:20px")
            with ui.row().classes("items-center gap-1 cursor-pointer"):
                ui.icon("filter_list").style(f"color:{GRAY};font-size:18px")
                ui.label("Filtrar").style(f"color:{GRAY};font-size:13px")

        if not photos_:
            with ui.element("div").classes(
                "hf-card w-full p-6 flex flex-col items-center gap-3").style(f"background:{FIELD}"):
                icon_circle("hide_image", 72, "#E6E6E6", GRAY)
                ui.label("Nenhuma foto ainda").style(
                    f"color:{INK};font-weight:700;font-size:17px")
                ui.label("As fotos enviadas aparecerão automaticamente nesta galeria "
                         "em tempo real.").style(
                    f"color:{GRAY};font-size:13px;text-align:center")
                ui.button("Começar upload agora", icon="cloud_upload",
                          on_click=lambda: ui.navigate.to(f"/evento/{event_id}/capturar")).props(
                    "unelevated").style(
                    f"background:{ORANGE_SOFT};color:{ORANGE};border-radius:9999px;"
                    "font-weight:700;height:44px;padding:0 18px")
        else:
            with ui.element("div").classes("w-full grid grid-cols-2 gap-3"):
                for p in reversed(photos_):
                    with ui.element("div").classes("hf-card overflow-hidden p-0 cursor-pointer").on(
                        "click", lambda x=p: ui.navigate.to(f"/foto/{x['id']}")):
                        ui.image(p["thumbnail_url"]).classes(
                            "w-full aspect-square object-cover")

        # card QR — abre o QR do álbum inteiro (baixa todas as fotos)
        qr_card = ui.element("div").classes(
            "hf-card w-full p-4 flex items-center gap-3 cursor-pointer")
        with qr_card.on("click", lambda: open_album_qr(event["name"], album)):
            icon_circle("qr_code_2", 48, ORANGE_SOFT, ORANGE)
            with ui.column().classes("gap-0").style("flex:1"):
                ui.label("QR Code do álbum").style(
                    f"color:{INK};font-weight:700;font-size:15px")
                ui.label("Escaneie e baixe todas as fotos do evento.").style(
                    f"color:{GRAY};font-size:12px")
            ui.icon("qr_code_scanner").style(f"color:{ORANGE};font-size:22px")

    bottom_nav("Eventos")


# ---------------------------------------------------------------------------
# FOTO + QR ("Pronto! 🎉" — tela 06)
# ---------------------------------------------------------------------------

@ui.page("/foto/{photo_id}")
def foto_page(photo_id: str, request: Request):
    setup()
    photo = get_photo(photo_id)
    top_bar(show_back=True)
    if not photo:
        with page_container():
            ui.label("Foto não encontrada").style(f"color:{INK}")
        return
    base = base_from_request(request)
    # link PÚBLICO (o que o QR aponta e o que é compartilhado): só foto + baixar
    share_url = f"{base}/f/{photo['id']}"
    dl_url = f"/download/foto/{photo['id']}"
    with page_container():
        # 1) FOTO em cima
        ui.image(photo["preview_url"]).classes("w-full").style("border-radius:16px")

        # 2) QR Code embaixo
        with ui.element("div").classes(
            "hf-card w-full p-6 flex flex-col items-center gap-3"):
            ui.label("Pronto! 🎉").style(f"color:{INK};font-weight:800;font-size:28px")
            ui.label("Escaneie o QR Code para baixar a foto").style(
                f"color:{GRAY};text-align:center;font-size:14px")
            qr = generate_qr_base64(share_url)
            ui.image(qr).classes("w-56 h-56").style(
                f"border-radius:16px;background:#fff;padding:10px;"
                f"box-shadow:0 0 0 4px {ORANGE}, 0 0 28px rgba(255,106,0,0.45)")
            with ui.row().classes("items-center gap-1").style("margin-top:6px"):
                ui.icon("info").style(f"color:{ORANGE};font-size:18px")
                ui.label("O link expira em 24 horas").style(
                    f"color:{ORANGE};font-size:13px;font-weight:600")

        # 3) só o botão Compartilhar (WhatsApp / SMS / E-mail / Baixar)
        primary_button(
            "COMPARTILHAR",
            lambda: open_share("Sua foto", share_url, download_url=dl_url,
                               subtitle="Envie a foto por onde preferir."),
            icon="share")

        with ui.column().classes("w-full items-center gap-1").style("margin-top:8px"):
            ui.label(BRAND).style(f"color:{INK};font-weight:700;font-size:15px")
            ui.label(f"© 2026 {BRAND}").style(f"color:{GRAY};font-size:12px")


# ---------------------------------------------------------------------------
# FOTO PÚBLICA (quem escaneou o QR) — só a imagem + baixar
# ---------------------------------------------------------------------------

def public_header() -> None:
    with ui.header().classes("items-center px-4").style(
        f"background:{HEADER};height:56px"):
        with ui.row().classes("items-center gap-2 no-wrap"):
            if has_logo("icon.png"):
                ui.image("/brand/icon.png").style("height:28px;width:28px").props("no-spinner")
            ui.html('<span style="font-weight:800;font-size:18px">'
                    f'<span style="color:#fff">Snap</span>'
                    f'<span style="color:{ORANGE}">Share</span></span>')


@ui.page("/f/{photo_id}")
def foto_publica(photo_id: str):
    setup()
    photo = get_photo(photo_id)
    public_header()
    if not photo:
        with page_container():
            ui.label("Foto não encontrada").style(f"color:{INK}")
        return
    img = photo.get("original_url") or photo.get("preview_url")
    with ui.column().classes("w-full max-w-md mx-auto px-4 pt-4 pb-8 gap-4"):
        ui.image(photo["preview_url"]).classes("w-full").style("border-radius:16px")
        primary_button("Baixar foto",
                       lambda u=img: ui.navigate.to(u, new_tab=True), icon="download")
        with ui.row().classes("w-full items-center justify-center gap-2").style(
            f"background:{FIELD};border-radius:12px;padding:10px"):
            ui.icon("touch_app").style(f"color:{ORANGE};font-size:20px")
            ui.label("Toque e segure na imagem para salvar na galeria").style(
                f"color:{GRAY};font-size:12px;text-align:center")
        with ui.column().classes("w-full items-center gap-0").style("margin-top:6px"):
            ui.label(BRAND).style(f"color:{INK};font-weight:700;font-size:14px")


# ---------------------------------------------------------------------------
# MEUS EVENTOS (lista + busca)
# ---------------------------------------------------------------------------

@ui.page("/meus-eventos")
def meus_eventos(request: Request):
    setup()
    user = current_user()
    if not user:
        ui.navigate.to("/login")
        return
    top_bar(show_back=True, search=True)
    q0 = request.query_params.get("q", "")
    with page_container():
        with ui.row().classes("w-full items-center justify-between no-wrap"):
            page_title("Meus Eventos")
            ui.button("Criar Evento", icon="add",
                      on_click=lambda: ui.navigate.to("/criar-evento")).props(
                "unelevated").style(
                f"background:{ORANGE};color:#fff;border-radius:12px;height:42px;"
                "font-weight:700;font-size:13px")
        busca = ui.input(placeholder="Buscar por nome, data ou local…", value=q0).props(
            'outlined dense clearable').classes("w-full hf-field")
        with busca.add_slot("prepend"):
            ui.icon("search")

        @ui.refreshable
        def lista():
            termo = (busca.value or "").lower().strip()
            eventos = db.list_events(organizer_id=user["id"])
            if termo:
                def match(e):
                    alvo = " ".join([
                        e.get("name", ""), e.get("location", ""),
                        e.get("date", ""), fmt_date_br(e.get("date", "")),
                        fmt_date(e.get("date", "")),
                    ]).lower()
                    return termo in alvo
                eventos = [e for e in eventos if match(e)]
            if not eventos:
                with ui.element("div").classes(
                    "hf-card w-full p-6 flex flex-col items-center gap-2"):
                    icon_circle("event", 56, "#F0F0F0", GRAY)
                    ui.label("Nenhum evento ainda").style(f"color:{INK};font-weight:700")
                    ui.button("Criar evento",
                              on_click=lambda: ui.navigate.to("/criar-evento")).props(
                        "flat").style(f"color:{ORANGE};font-weight:700")
                return
            for ev in eventos:
                fotos = db.list_photos(ev["id"])
                el = ui.element("div").classes(
                    "hf-card w-full flex items-center gap-3 p-3 cursor-pointer")
                with el.on("click", lambda e=ev: ui.navigate.to(f"/evento/{e['id']}")):
                    if fotos:
                        ui.image(fotos[-1]["thumbnail_url"]).classes(
                            "w-16 h-16 object-cover").style("border-radius:12px")
                    else:
                        icon_circle("image", 64, "#F0F0F0", GRAY)
                    with ui.column().classes("gap-0").style("flex:1"):
                        ui.label(ev["name"]).style(f"color:{INK};font-weight:700;font-size:16px")
                        sub = event_meta(ev)
                        if sub:
                            ui.label(sub).style(f"color:{GRAY};font-size:12px")
                        ui.label(f"{len(fotos)} fotos").style(
                            f"color:{ORANGE};font-size:12px;font-weight:600")
                    ui.icon("chevron_right").style(f"color:{GRAY}")

        busca.on("update:model-value", lambda: lista.refresh())
        lista()

    bottom_nav("Eventos")


# ---------------------------------------------------------------------------
# GALERIA (escolher evento)
# ---------------------------------------------------------------------------

@ui.page("/galeria")
def galeria():
    setup()
    user = current_user()
    if not user:
        ui.navigate.to("/login")
        return
    top_bar(show_back=True, search=True)
    eventos = db.list_events(organizer_id=user["id"])
    with page_container():
        with ui.row().classes("w-full items-center justify-between no-wrap"):
            page_title("Galeria")
            ui.button("Criar Evento", icon="add",
                      on_click=lambda: ui.navigate.to("/criar-evento")).props(
                "unelevated").style(
                f"background:{ORANGE};color:#fff;border-radius:12px;height:42px;"
                "font-weight:700;font-size:13px")
        if not eventos:
            with ui.element("div").classes(
                "hf-card w-full p-6 flex flex-col items-center gap-2"):
                icon_circle("photo_library", 56, "#F0F0F0", GRAY)
                ui.label("Nenhuma galeria ainda").style(f"color:{INK};font-weight:700")
                ui.button("Criar Evento",
                          on_click=lambda: ui.navigate.to("/criar-evento")).props(
                    "flat").style(f"color:{ORANGE};font-weight:700")
        else:
            with ui.element("div").classes("w-full grid grid-cols-2 gap-3"):
                for ev in eventos:
                    fotos = db.list_photos(ev["id"])
                    with ui.element("div").classes(
                        "hf-card overflow-hidden p-0 cursor-pointer").on(
                        "click", lambda e=ev: ui.navigate.to(f"/evento/{e['id']}")):
                        if fotos:
                            ui.image(fotos[-1]["thumbnail_url"]).classes(
                                "w-full aspect-square object-cover")
                        else:
                            with ui.element("div").classes(
                                "w-full aspect-square flex items-center justify-center").style(
                                f"background:{FIELD}"):
                                ui.icon("hide_image").style(f"color:{GRAY};font-size:32px")
                        with ui.column().classes("gap-0 p-3"):
                            ui.label(ev["name"]).style(
                                f"color:{INK};font-weight:700;font-size:14px")
                            data_br = fmt_date_br(ev.get("date") or "")
                            ui.label(" • ".join(filter(None, [
                                f"{len(fotos)} fotos", data_br]))).style(
                                f"color:{GRAY};font-size:12px")

    bottom_nav("Eventos")


# ---------------------------------------------------------------------------
# UPLOAD (escolhe evento -> equipamento)
# ---------------------------------------------------------------------------

@ui.page("/upload")
def upload_page():
    setup()
    user = current_user()
    if not user:
        ui.navigate.to("/login")
        return
    top_bar(show_back=True, search=True)
    eventos = db.list_events(organizer_id=user["id"])
    with page_container():
        page_title("Para qual evento?")
        ui.label("Escolha o evento e o método de captura das fotos.").style(
            f"color:{GRAY};font-size:14px")
        primary_button("Criar Álbum", lambda: ui.navigate.to("/criar-evento"),
                       icon="add")
        if not eventos:
            with ui.element("div").classes(
                "hf-card w-full p-6 flex flex-col items-center gap-2"):
                icon_circle("event", 56, "#F0F0F0", GRAY)
                ui.label("Nenhum evento ainda").style(f"color:{INK};font-weight:700")
        else:
            for ev in eventos:
                fotos = db.list_photos(ev["id"])
                el = ui.element("div").classes(
                    "hf-card w-full flex items-center gap-3 p-4 cursor-pointer")
                with el.on("click",
                           lambda e=ev: ui.navigate.to(f"/evento/{e['id']}/capturar")):
                    icon_circle("cloud_upload", 48, ORANGE_SOFT, ORANGE)
                    with ui.column().classes("gap-0").style("flex:1"):
                        ui.label(ev["name"]).style(f"color:{INK};font-weight:700;font-size:16px")
                        ui.label(f"{len(fotos)} fotos enviadas").style(
                            f"color:{GRAY};font-size:12px")
                    ui.icon("chevron_right").style(f"color:{GRAY}")

    bottom_nav("Upload")


# ---------------------------------------------------------------------------
# PERFIL / AJUSTES (tela 07)
# ---------------------------------------------------------------------------

@ui.page("/perfil")
def perfil():
    setup()
    user = current_user()
    if not user:
        ui.navigate.to("/login")
        return
    n_eventos = len(db.list_events(organizer_id=user["id"]))
    top_bar(show_back=True)

    def info_dialog(titulo: str, conteudo: str):
        with ui.dialog() as d, ui.card().classes("w-80 gap-2").style(
            f"background:{CARD};border-radius:18px"):
            ui.label(titulo).style(f"color:{INK};font-weight:700;font-size:18px")
            ui.label(conteudo).style(f"color:{GRAY}")
            ui.button("Fechar", on_click=d.close).props("flat").style(f"color:{ORANGE}")
        d.open()

    def dados_dialog():
        with ui.dialog() as d, ui.card().classes("w-96 gap-3 p-4").style(
            f"background:{CARD};border-radius:18px"):
            ui.label("Dados Cadastrais").style(f"color:{INK};font-weight:700;font-size:18px")

            def f(icon, placeholder, value):
                inp = ui.input(placeholder=placeholder, value=value or "").props(
                    "outlined dense").classes("w-full hf-field")
                with inp.add_slot("prepend"):
                    ui.icon(icon)
                return inp

            nome = f("person", "Nome", user.get("name"))
            email = f("mail", "E-mail", user.get("email"))
            fone = f("phone", "Telefone", user.get("phone"))

            def salvar():
                db._data["users"][user["id"]].update({
                    "name": nome.value or "Organizador",
                    "email": email.value or user.get("email"),
                    "phone": fone.value or "",
                })
                db._save()
                ui.notify("Dados salvos!", type="positive")
                d.close()
                ui.navigate.to("/perfil")

            with ui.row().classes("w-full justify-end gap-2"):
                ui.button("Cancelar", on_click=d.close).props("flat").style(f"color:{GRAY}")
                ui.button("Salvar", on_click=salvar).props("unelevated").style(
                    f"background:{ORANGE};color:#fff")
        d.open()

    def menu_row(icon: str, label: str, trailing=None, on_click=None, danger=False):
        txt = RED if danger else INK
        ico = RED if danger else ORANGE
        el = ui.element("div").classes(
            "hf-card w-full flex items-center gap-4 px-4 py-4 cursor-pointer")
        with el.on("click", on_click or (lambda: None)):
            icon_circle(icon, 44, "#FBE9E7" if danger else ORANGE_SOFT, ico)
            ui.label(label).style(f"color:{txt};font-weight:700;font-size:16px;flex:1")
            if trailing is not None:
                trailing()
            ui.icon("chevron_right").style(f"color:{GRAY}")

    with page_container():
        with ui.column().classes("w-full items-center gap-2 py-2"):
            with ui.element("div").classes("flex items-center justify-center").style(
                f"width:100px;height:100px;border-radius:9999px;background:{ORANGE_SOFT}"):
                ui.icon("person").style(f"color:{ORANGE};font-size:54px")
            ui.label(user.get("name") or "Organizador").style(
                f"color:{INK};font-weight:800;font-size:24px")
            ui.label(user.get("email") or "demo@sharedpics.app").style(f"color:{GRAY}")

        def badge_count():
            ui.label(str(n_eventos)).style(
                f"background:{ORANGE};color:#fff;font-weight:700;border-radius:9999px;"
                "min-width:28px;height:28px;display:flex;align-items:center;"
                "justify-content:center;padding:0 8px")

        def badge_pro():
            ui.label("PRO").style(
                f"background:{GREEN};color:#fff;font-weight:700;border-radius:9999px;"
                "padding:3px 12px;font-size:12px")

        menu_row("badge", "Dados Cadastrais", None, dados_dialog)
        menu_row("calendar_month", "Meus Eventos", badge_count,
                 lambda: ui.navigate.to("/meus-eventos"))
        menu_row("credit_card", "Plano e Pagamento", badge_pro,
                 lambda: info_dialog("Plano PRO",
                                     "Você está no plano PRO — eventos e fotos ilimitados."))
        menu_row("shield", "Segurança", None,
                 lambda: info_dialog("Segurança", "Sua conta e seus álbuns estão protegidos."))
        menu_row("support_agent", "Suporte", None,
                 lambda: info_dialog("Suporte", "Fale com a gente: suporte@snapshare.app"))
        menu_row("logout", "Sair", None,
                 lambda: (logout_user(), ui.notify("Sessão encerrada", type="info"),
                          ui.navigate.to("/login")),
                 danger=True)

        ui.label(f"{BRAND} v2.4.0").style(
            f"color:{GRAY};font-size:12px;text-align:center;width:100%;margin-top:8px")

    bottom_nav("Perfil")


# ---------------------------------------------------------------------------
# ÁLBUM PÚBLICO (cliente)
# ---------------------------------------------------------------------------

def render_album(event: dict | None) -> None:
    """Conteúdo do álbum público — usado por /e/{id} e /{fotografo}/{evento}."""
    public_header()
    if not event:
        with page_container():
            ui.label("Álbum não encontrado").style(f"color:{INK}")
        return
    event_id = event["id"]
    photos_ = db.list_photos(event_id)
    with ui.column().classes("w-full max-w-md mx-auto px-4 pt-4 pb-10 gap-4"):
        ui.label(event["name"]).style(
            f"color:{INK};font-weight:800;font-size:26px;line-height:1.2")
        meta = event_meta(event)
        if meta:
            ui.label(meta).style(f"color:{GRAY};font-size:13px;font-weight:600")
        ui.label(f"{len(photos_)} fotos").style(f"color:{GRAY};font-size:14px")
        if photos_:
            with ui.row().classes("w-full items-center gap-2").style(
                f"background:{FIELD};border-radius:12px;padding:10px"):
                ui.icon("touch_app").style(f"color:{ORANGE};font-size:20px")
                ui.label("No celular, toque na foto e segure para salvar na galeria.").style(
                    f"color:{GRAY};font-size:12px")
            primary_button("Baixar tudo (.zip)",
                           lambda: ui.download(f"/download/evento/{event_id}"), icon="download")
            with ui.element("div").classes("w-full grid grid-cols-2 gap-3"):
                for p in photos_:
                    img = p.get("original_url") or p.get("preview_url")
                    with ui.element("div").classes("hf-card overflow-hidden p-0"):
                        ui.image(p["thumbnail_url"]).classes(
                            "w-full aspect-square object-cover cursor-pointer").on(
                            "click", lambda x=p: ui.navigate.to(f"/f/{x['id']}"))
                        ui.button("Baixar", icon="download",
                                  on_click=lambda u=img: ui.navigate.to(u, new_tab=True)).props(
                            "flat dense").style(
                            f"color:{ORANGE};font-weight:600").classes("w-full")
        else:
            with ui.element("div").classes(
                "hf-card w-full p-6 flex flex-col items-center gap-2").style(f"background:{FIELD}"):
                icon_circle("hide_image", 64, "#E6E6E6", GRAY)
                ui.label("As fotos aparecem aqui assim que o fotógrafo enviar.").style(
                    f"color:{GRAY};text-align:center")


@ui.page("/e/{event_id}")
def album_publico(event_id: str, request: Request):
    setup()
    render_album(db.get_event(event_id))


# Rota amigável: /{fotografo}/{evento} — DEVE ficar por último (catch-all 2 níveis).
@ui.page("/{pslug}/{eslug}")
def album_pretty(pslug: str, eslug: str, request: Request):
    setup()
    if pslug in RESERVED_SLUGS or pslug.startswith("_") or pslug.startswith("."):
        render_album(None)
        return
    user = next((u for u in db._data["users"].values()
                 if u.get("slug") == pslug), None)
    event = None
    if user:
        event = next((e for e in db._data["events"].values()
                      if e.get("organizer_id") == user["id"]
                      and e.get("slug") == eslug), None)
    render_album(event)


ui.run_with(app, title=BRAND, favicon="📸", dark=False, storage_secret="snapshare")
