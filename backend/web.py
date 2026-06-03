"""
Shared Pics — frontend 100% Python (NiceGUI) montado sobre o FastAPI.

Reaproveita a camada de serviços do backend (db, image_processor, qr_generator)
chamando diretamente como funções Python — sem JavaScript escrito à mão.

Telas:
  /                  Dashboard de eventos (fotógrafo)
  /evento/{id}       Tela do evento: upload, QR da última foto, álbum
  /foto/{id}         Página pública da foto (preview + download) — destino do QR
  /e/{id}            Álbum público do evento (ver, baixar individual / em lote)

Rodar local:
  uvicorn backend.web:app --host 0.0.0.0 --port 8000

As imagens são guardadas com caminho RELATIVO (/uploads/...) e os QR Codes /
links de compartilhamento usam a URL pública detectada na própria requisição,
então o app funciona igual em localhost ou em https://www.hostfoto.com.br sem
precisar configurar variável de ambiente.
"""
from __future__ import annotations

import os
import io
import uuid
import shutil
import zipfile

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

load_dotenv()

from .services.database import db
from .utils.image_processor import process_image
from .utils.qr_generator import generate_qr_base64
from .routers import auth, events, leads, photos

from nicegui import ui

# ---------------------------------------------------------------------------
# Configuração / caminhos
# ---------------------------------------------------------------------------

BRAND = "#f97316"
DARK = "#1c1c1e"
ALLOWED = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif", ".tiff", ".tif"}

UPLOAD_ROOT = os.path.abspath(
    os.getenv("UPLOAD_ROOT", os.path.join(os.path.dirname(__file__), "../uploads"))
)
os.makedirs(UPLOAD_ROOT, exist_ok=True)


def base_from_request(request: Request) -> str:
    """URL pública real, respeitando o proxy do Railway (https)."""
    proto = request.headers.get("x-forwarded-proto") or request.url.scheme
    host = (
        request.headers.get("x-forwarded-host")
        or request.headers.get("host")
        or request.url.netloc
    )
    return f"{proto}://{host}"


def _rel_url(path: str) -> str:
    """Caminho relativo servido pelo mount /uploads — funciona em qualquer host."""
    rel = os.path.relpath(path, UPLOAD_ROOT).replace(os.sep, "/")
    return f"/uploads/{rel}"


def get_default_user() -> dict:
    """Usuário fotógrafo padrão para o MVP (sem tela de login)."""
    user = db.get_user_by_email("demo@sharedpics.app")
    if not user:
        user = db.create_user(
            name="Fotógrafo", email="demo@sharedpics.app",
            hashed_pw="x", role="photographer",
        )
    return user


def get_photo(photo_id: str) -> dict | None:
    return db._data["photos"].get(photo_id)


def ingest_photo(event_id: str, filename: str, file_obj) -> dict:
    """Salva o arquivo original, gera preview + thumb e registra no banco."""
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
    return db.create_photo(
        filename=filename or f"{stem}{ext}",
        original_url=_rel_url(orig_path),
        preview_url=_rel_url(paths["preview_path"]),
        thumbnail_url=_rel_url(paths["thumb_path"]),
        event_id=event_id,
    )


# ---------------------------------------------------------------------------
# FastAPI base + API existente + rotas de download
# ---------------------------------------------------------------------------

app = FastAPI(title="Shared Pics")

app.include_router(auth.router, prefix="/api")
app.include_router(events.router, prefix="/api")
app.include_router(leads.router, prefix="/api")
app.include_router(photos.router, prefix="/api")

app.mount("/uploads", StaticFiles(directory=UPLOAD_ROOT), name="uploads")


@app.get("/health")
def health():
    return {"status": "ok", "service": "Shared Pics (Python UI)"}


def _orig_path_of(photo: dict) -> str:
    rel = photo["original_url"].split("/uploads/", 1)[-1]
    return os.path.join(UPLOAD_ROOT, rel.replace("/", os.sep))


@app.get("/download/foto/{photo_id}")
def download_single(photo_id: str):
    photo = get_photo(photo_id)
    if not photo:
        raise HTTPException(404, "Foto não encontrada")
    full = _orig_path_of(photo)
    if not os.path.exists(full):
        raise HTTPException(404, "Arquivo não encontrado")
    return FileResponse(full, filename=photo["filename"], media_type="application/octet-stream")


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
            full = _orig_path_of(p)
            if os.path.exists(full):
                zf.write(full, p["filename"])
    buffer.seek(0)
    slug = event["name"].lower().replace(" ", "-") or "album"
    return StreamingResponse(
        buffer, media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{slug}.zip"'},
    )


# ---------------------------------------------------------------------------
# Componentes de UI reutilizáveis
# ---------------------------------------------------------------------------

def page_header(subtitle: str = "") -> None:
    with ui.header().classes("items-center justify-between px-6 py-3").style(
        f"background:{DARK}"
    ):
        with ui.row().classes("items-center gap-2 cursor-pointer").on(
            "click", lambda: ui.navigate.to("/")
        ):
            ui.icon("photo_camera").style(f"color:{BRAND}").classes("text-3xl")
            ui.label("Shared Pics").classes("text-2xl font-bold text-white")
        if subtitle:
            ui.label(subtitle).classes("text-sm text-gray-400")


def apply_theme() -> None:
    ui.colors(primary=BRAND, dark=DARK)
    ui.dark_mode().enable()


# ---------------------------------------------------------------------------
# Dashboard de eventos
# ---------------------------------------------------------------------------

@ui.page("/")
def dashboard():
    apply_theme()
    user = get_default_user()
    page_header("Meus eventos")

    def open_new_event_dialog():
        with ui.dialog() as dialog, ui.card().classes("w-96 gap-3"):
            ui.label("Novo evento").classes("text-xl font-bold")
            nome = ui.input("Nome do evento").classes("w-full").props("autofocus")
            cliente = ui.input("Cliente").classes("w-full")
            data = ui.input("Data").classes("w-full").props("type=date")
            with ui.row().classes("w-full justify-end gap-2"):
                ui.button("Cancelar", on_click=dialog.close).props("flat")

                def create():
                    if not nome.value:
                        ui.notify("Informe o nome do evento", type="warning")
                        return
                    ev = db.create_event(
                        name=nome.value, description="",
                        date=data.value or "", location=cliente.value or "",
                        organizer_id=user["id"],
                    )
                    dialog.close()
                    ui.navigate.to(f"/evento/{ev['id']}")

                ui.button("Criar", on_click=create).props("unelevated")
        dialog.open()

    with ui.column().classes("w-full max-w-5xl mx-auto p-6 gap-4"):
        with ui.row().classes("w-full justify-between items-center"):
            ui.label("Eventos").classes("text-2xl font-bold")
            ui.button("Novo evento", icon="add", on_click=open_new_event_dialog).props(
                "unelevated"
            )

        eventos = db.list_events(organizer_id=user["id"])
        if not eventos:
            with ui.card().classes("w-full items-center p-10 gap-2"):
                ui.icon("event").classes("text-5xl text-gray-500")
                ui.label("Nenhum evento ainda").classes("text-lg text-gray-400")
                ui.label('Clique em "Novo evento" para começar.').classes(
                    "text-sm text-gray-500"
                )
            return

        with ui.element("div").classes(
            "w-full grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4"
        ):
            for ev in eventos:
                photos_ = db.list_photos(ev["id"])
                last = photos_[-1] if photos_ else None
                with ui.card().classes(
                    "cursor-pointer hover:shadow-lg transition-shadow p-0 overflow-hidden"
                ).on("click", lambda e=ev: ui.navigate.to(f"/evento/{e['id']}")):
                    if last:
                        ui.image(last["thumbnail_url"]).classes("w-full h-40 object-cover")
                    else:
                        with ui.element("div").classes(
                            "w-full h-40 flex items-center justify-center"
                        ).style(f"background:{DARK}"):
                            ui.icon("image").classes("text-5xl text-gray-600")
                    with ui.column().classes("p-3 gap-1"):
                        ui.label(ev["name"]).classes("font-bold text-lg")
                        if ev["location"]:
                            ui.label(ev["location"]).classes("text-sm text-gray-400")
                        with ui.row().classes("items-center gap-1 text-gray-400"):
                            ui.icon("photo_library").classes("text-sm")
                            ui.label(f"{len(photos_)} fotos").classes("text-sm")


# ---------------------------------------------------------------------------
# Tela do evento (fotógrafo)
# ---------------------------------------------------------------------------

@ui.page("/evento/{event_id}")
def event_page(event_id: str, request: Request):
    apply_theme()
    event = db.get_event(event_id)
    if not event:
        page_header()
        ui.label("Evento não encontrado").classes("text-xl m-6")
        return

    base = base_from_request(request)
    page_header(event["name"])
    album_link = f"{base}/e/{event_id}"

    with ui.column().classes("w-full max-w-5xl mx-auto p-6 gap-4"):
        with ui.row().classes("w-full justify-between items-start"):
            with ui.column().classes("gap-0"):
                ui.label(event["name"]).classes("text-3xl font-bold")
                meta = " · ".join(filter(None, [event.get("location"), event.get("date")]))
                if meta:
                    ui.label(meta).classes("text-gray-400")
            with ui.row().classes("gap-2"):
                ui.button(
                    "Compartilhar álbum", icon="share",
                    on_click=lambda: (
                        ui.clipboard.write(album_link),
                        ui.notify("Link do álbum copiado!", type="positive"),
                    ),
                ).props("outline")
                ui.button(
                    "Abrir álbum", icon="open_in_new",
                    on_click=lambda: ui.navigate.to(f"/e/{event_id}", new_tab=True),
                ).props("flat")

        ui.separator()

        with ui.row().classes("w-full gap-6 items-start flex-col md:flex-row"):
            with ui.column().classes("w-full md:flex-1 gap-3"):
                ui.label("Receber fotos").classes("text-lg font-bold")
                with ui.element("div").classes(
                    "w-full rounded-lg p-3 text-sm text-gray-300"
                ).style("background:#2a2a2e"):
                    ui.html(
                        "📱 <b>No iPhone:</b> ligue a câmera no cabo USB-C, "
                        "deixe o app <b>Fotos</b> importar as imagens, depois toque em "
                        "<b>Enviar fotos</b> abaixo e escolha as fotos da câmera. "
                        "O QR aparece na hora."
                    )

                def handle_upload(e):
                    try:
                        ingest_photo(event_id, e.name, e.content)
                        ui.notify(f"Foto recebida: {e.name}", type="positive")
                        gallery.refresh()
                        last_photo_panel.refresh()
                    except Exception as exc:  # noqa: BLE001
                        ui.notify(f"Erro: {exc}", type="negative")

                ui.upload(
                    multiple=True, auto_upload=True, on_upload=handle_upload,
                    label="Enviar fotos",
                ).props('accept=image/*').classes("w-full")

            @ui.refreshable
            def last_photo_panel():
                photos_ = db.list_photos(event_id)
                with ui.card().classes("w-full md:w-80 items-center gap-2 p-4"):
                    if not photos_:
                        ui.icon("hourglass_empty").classes("text-4xl text-gray-500")
                        ui.label("Aguardando a primeira foto").classes(
                            "text-sm text-gray-400 text-center"
                        )
                        return
                    last = photos_[-1]
                    ui.label("Última foto").classes("text-sm text-gray-400")
                    ui.image(last["thumbnail_url"]).classes(
                        "w-32 h-32 object-cover rounded"
                    )
                    qr = generate_qr_base64(f"{base}/foto/{last['id']}")
                    ui.image(qr).classes("w-40 h-40")
                    ui.label("Escaneie para baixar").classes("text-xs text-gray-500")
                    ui.button(
                        "Abrir foto", icon="qr_code",
                        on_click=lambda l=last: ui.navigate.to(f"/foto/{l['id']}"),
                    ).props("flat dense")

            last_photo_panel()

        ui.separator()

        @ui.refreshable
        def gallery():
            photos_ = db.list_photos(event_id)
            ui.label(f"Fotos do evento ({len(photos_)})").classes("text-lg font-bold")
            if not photos_:
                ui.label("Nenhuma foto ainda.").classes("text-sm text-gray-500")
                return
            with ui.grid(columns=5).classes("w-full gap-2"):
                for p in reversed(photos_):
                    ui.image(p["thumbnail_url"]).classes(
                        "w-full aspect-square object-cover rounded cursor-pointer "
                        "hover:opacity-80 transition-opacity"
                    ).on("click", lambda x=p: ui.navigate.to(f"/foto/{x['id']}"))

        gallery()


# ---------------------------------------------------------------------------
# Página pública da foto (destino do QR)
# ---------------------------------------------------------------------------

@ui.page("/foto/{photo_id}")
def photo_page(photo_id: str, request: Request):
    apply_theme()
    photo = get_photo(photo_id)
    page_header()
    if not photo:
        ui.label("Foto não encontrada").classes("text-xl m-6")
        return

    base = base_from_request(request)
    share_url = f"{base}/foto/{photo_id}"

    with ui.column().classes("w-full max-w-3xl mx-auto p-6 gap-4 items-center"):
        ui.image(photo["preview_url"]).classes("w-full rounded-lg shadow-lg")
        with ui.row().classes("gap-3"):
            ui.button(
                "Baixar foto", icon="download",
                on_click=lambda: ui.download(f"/download/foto/{photo_id}"),
            ).props("unelevated size=lg")
            ui.button(
                "Compartilhar", icon="share",
                on_click=lambda: (
                    ui.clipboard.write(share_url),
                    ui.notify("Link copiado!", type="positive"),
                ),
            ).props("outline size=lg")
        with ui.expansion("Mostrar QR Code", icon="qr_code").classes("w-64"):
            ui.image(generate_qr_base64(share_url)).classes("w-48 h-48 mx-auto")


# ---------------------------------------------------------------------------
# Álbum público do evento
# ---------------------------------------------------------------------------

@ui.page("/e/{event_id}")
def public_album(event_id: str, request: Request):
    apply_theme()
    event = db.get_event(event_id)
    page_header()
    if not event:
        ui.label("Álbum não encontrado").classes("text-xl m-6")
        return

    base = base_from_request(request)
    photos_ = db.list_photos(event_id)
    share_url = f"{base}/e/{event_id}"

    with ui.column().classes("w-full max-w-5xl mx-auto p-6 gap-4"):
        with ui.row().classes("w-full justify-between items-center"):
            with ui.column().classes("gap-0"):
                ui.label(event["name"]).classes("text-3xl font-bold")
                ui.label(f"{len(photos_)} fotos").classes("text-gray-400")
            with ui.row().classes("gap-2"):
                if photos_:
                    ui.button(
                        "Baixar tudo", icon="download",
                        on_click=lambda: ui.download(f"/download/evento/{event_id}"),
                    ).props("unelevated")
                ui.button(
                    "Compartilhar", icon="share",
                    on_click=lambda: (
                        ui.clipboard.write(share_url),
                        ui.notify("Link copiado!", type="positive"),
                    ),
                ).props("outline")

        ui.separator()

        if not photos_:
            ui.label("As fotos aparecem aqui assim que o fotógrafo enviar.").classes(
                "text-gray-500"
            )
            return

        with ui.grid(columns=4).classes("w-full gap-3"):
            for p in photos_:
                with ui.card().classes("p-0 overflow-hidden"):
                    ui.image(p["thumbnail_url"]).classes(
                        "w-full aspect-square object-cover cursor-pointer"
                    ).on("click", lambda x=p: ui.navigate.to(f"/foto/{x['id']}"))
                    ui.button(
                        "Baixar", icon="download",
                        on_click=lambda x=p: ui.download(f"/download/foto/{x['id']}"),
                    ).props("flat dense").classes("w-full")


# ---------------------------------------------------------------------------
# Monta o NiceGUI sobre o FastAPI
# ---------------------------------------------------------------------------

ui.run_with(app, title="Shared Pics", favicon="📸", dark=True, storage_secret="shared-pics")
