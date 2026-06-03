"""
HostFoto — frontend 100% Python (NiceGUI) sobre o FastAPI.

Fluxo (PWA iPhone/iPad):
  /                       Home — barra superior (logo + perfil) + 4 botões
  /perfil                 Dados, plano, histórico de eventos
  /criar-evento           Formulário de novo evento  (print 03)
  /evento/{id}/equipamento  Escolha do equipamento (Câmera/iPad/iPhone/Upload)
  /evento/{id}/capturar   Capturar ou carregar foto  (print 04)
  /evento/{id}            Detalhe do evento (galeria + adicionar + compartilhar)
  /foto/{id}              Resultado com QR Code        (print 05)
  /meus-eventos           Lista de eventos + busca
  /upload                 Upload: escolhe evento e envia
  /compartilhar           Links das pastas dos eventos
  /e/{id}                 Álbum público do evento

Backend reusa db / image_processor / qr_generator. Imagens em caminho
relativo (/uploads/...) e QR/links com a URL pública detectada na requisição.
"""
from __future__ import annotations

import os
import io
import uuid
import shutil
import zipfile
import urllib.parse

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

load_dotenv()

from .services.database import db
from .utils.image_processor import process_image
from .utils.qr_generator import generate_qr_base64
from .routers import auth, events, leads, photos

from nicegui import ui

# ---------------------------------------------------------------------------
# Paleta (extraída do protótipo) e caminhos
# ---------------------------------------------------------------------------

ORANGE = "#f97316"
ORANGE_DK = "#ea6a0a"
BG = "#1c1c1e"
CARD = "#2c2c2e"
BORDER = "#3a3a3c"
GRAY = "#8e8e93"
GREEN = "#25d366"
ICON_BG = "rgba(249,115,22,0.22)"

ALLOWED = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif", ".tiff", ".tif"}

UPLOAD_ROOT = os.path.abspath(
    os.getenv("UPLOAD_ROOT", os.path.join(os.path.dirname(__file__), "../uploads"))
)
PWA_DIR = os.path.join(UPLOAD_ROOT, "pwa")
os.makedirs(PWA_DIR, exist_ok=True)


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
    return db.create_photo(
        filename=filename or f"{stem}{ext}",
        original_url=_rel_url(orig_path),
        preview_url=_rel_url(paths["preview_path"]),
        thumbnail_url=_rel_url(paths["thumb_path"]),
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
        # corpo da câmera
        bw, bh = int(size * 0.52), int(size * 0.34)
        bx, by = (size - bw) // 2, int(size * 0.36)
        d.rounded_rectangle([bx, by, bx + bw, by + bh], radius=int(size * 0.05), fill="white")
        # visor
        vw = int(size * 0.16)
        d.rounded_rectangle(
            [bx + int(bw * 0.18), by - int(size * 0.06), bx + int(bw * 0.18) + vw, by + 2],
            radius=int(size * 0.02), fill="white",
        )
        # lente
        lr = int(size * 0.10)
        cx, cy = size // 2, by + bh // 2
        d.ellipse([cx - lr, cy - lr, cx + lr, cy + lr], fill=ORANGE)
        img.save(path, "PNG")


_generate_pwa_icons()

# ---------------------------------------------------------------------------
# FastAPI base
# ---------------------------------------------------------------------------

app = FastAPI(title="HostFoto")

app.include_router(auth.router, prefix="/api")
app.include_router(events.router, prefix="/api")
app.include_router(leads.router, prefix="/api")
app.include_router(photos.router, prefix="/api")

app.mount("/uploads", StaticFiles(directory=UPLOAD_ROOT), name="uploads")
app.mount("/pwa", StaticFiles(directory=PWA_DIR), name="pwa")


@app.get("/health")
def health():
    return {"status": "ok", "service": "HostFoto (Python UI)"}


@app.get("/manifest.webmanifest")
def manifest():
    return JSONResponse({
        "name": "HostFoto",
        "short_name": "HostFoto",
        "start_url": "/",
        "display": "standalone",
        "background_color": BG,
        "theme_color": BG,
        "icons": [
            {"src": "/pwa/icon-180.png", "sizes": "180x180", "type": "image/png"},
            {"src": "/pwa/icon-512.png", "sizes": "512x512", "type": "image/png"},
        ],
    })


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
    slug = (event["name"].lower().replace(" ", "-") or "album")
    return StreamingResponse(
        buffer, media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{slug}.zip"'},
    )


# ---------------------------------------------------------------------------
# Componentes de UI
# ---------------------------------------------------------------------------

def setup() -> None:
    ui.colors(primary=ORANGE, dark=BG)
    ui.dark_mode().enable()
    ui.add_head_html(f"""
      <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
      <meta name="apple-mobile-web-app-capable" content="yes">
      <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
      <meta name="apple-mobile-web-app-title" content="HostFoto">
      <meta name="theme-color" content="{BG}">
      <link rel="manifest" href="/manifest.webmanifest">
      <link rel="apple-touch-icon" href="/pwa/icon-180.png">
      <link rel="preconnect" href="https://fonts.googleapis.com">
      <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
      <style>
        body {{ background:{BG} !important; font-family:'Inter',sans-serif; }}
        .hf-card {{ background:{CARD}; border:1px solid {BORDER}; border-radius:18px; }}
        /* zona de upload estilo print 01 */
        .hf-upload {{ background:transparent !important; box-shadow:none !important;
          border:2px dashed {BORDER} !important; border-radius:16px !important;
          min-height:170px; }}
        .hf-upload .q-uploader__header {{ background:transparent !important; color:{GRAY} !important; }}
        .hf-upload .q-uploader__subtitle {{ display:none !important; }}
        .hf-upload .q-uploader__list {{ background:transparent !important; min-height:0; }}
        .hf-upload .q-uploader__header-content {{ justify-content:center; }}
        /* campos de formulário */
        .hf-field .q-field__control {{ background:{CARD} !important; border-radius:12px; }}
        .hf-field .q-field__control:before {{ border-color:{BORDER} !important; }}
        .hf-field .q-icon, .hf-field input {{ color:#fff; }}
      </style>
    """)


def logo() -> None:
    with ui.row().classes("items-center gap-2 cursor-pointer no-wrap").on(
        "click", lambda: ui.navigate.to("/")
    ):
        with ui.element("div").classes("flex items-center justify-center").style(
            f"width:38px;height:38px;border-radius:10px;background:{ORANGE}"
        ):
            ui.icon("photo_camera").classes("text-xl text-white")
        ui.html('<span style="font-weight:800;font-size:20px">'
                f'<span style="color:#fff">Host</span>'
                f'<span style="color:{ORANGE}">Foto</span></span>')


def top_bar(show_back: bool = False, show_profile: bool = True) -> None:
    with ui.header().classes("items-center justify-between px-4 py-3").style(
        f"background:{BG};border-bottom:1px solid {BORDER}"
    ):
        logo()
        with ui.row().classes("items-center gap-2"):
            if show_back:
                ui.button("Voltar", icon="arrow_back",
                          on_click=lambda: ui.navigate.back()).props("flat dense").classes(
                    "hf-card text-white px-3"
                )
            if show_profile:
                ui.button(icon="person", on_click=lambda: ui.navigate.to("/perfil")).props(
                    "flat round"
                ).style(f"color:{ORANGE}")


def icon_circle(name: str, size: int = 64) -> None:
    with ui.element("div").classes("flex items-center justify-center").style(
        f"width:{size}px;height:{size}px;border-radius:9999px;background:{ICON_BG}"
    ):
        ui.icon(name).style(f"color:{ORANGE};font-size:{int(size*0.5)}px")


def nav_card(icon: str, title: str, subtitle: str, on_click) -> None:
    with ui.element("div").classes(
        "hf-card flex flex-col items-center justify-center gap-3 p-5 cursor-pointer "
        "transition-transform active:scale-95"
    ).style("min-height:160px").on("click", on_click):
        icon_circle(icon)
        ui.label(title).classes("text-white font-bold text-center").style("font-size:17px")
        if subtitle:
            ui.label(subtitle).style(f"color:{GRAY};font-size:13px")


def section_title(emoji: str, text: str) -> None:
    ui.html(f'<div style="color:{GRAY};font-weight:600;font-size:15px;margin:4px 0">'
            f'{emoji} {text}</div>')


def page_container():
    return ui.column().classes("w-full max-w-md mx-auto p-4 gap-4")


# ---------------------------------------------------------------------------
# QR / resultado (print 05) — reutilizável
# ---------------------------------------------------------------------------

def qr_result_card(photo: dict, base: str) -> None:
    share_url = f"{base}/foto/{photo['id']}"
    with ui.element("div").classes("hf-card w-full p-6 flex flex-col items-center gap-3"):
        ui.label("Pronto! 🎉").classes("text-white font-extrabold").style("font-size:26px")
        ui.label("Escaneie o QR Code para baixar sua foto").style(
            f"color:{GRAY};text-align:center"
        )
        qr = generate_qr_base64(share_url)
        ui.image(qr).classes("w-56 h-56").style(
            f"border:4px solid {ORANGE};border-radius:14px;background:#fff;padding:6px"
        )
        with ui.row().classes("w-full gap-3 no-wrap"):
            ui.button("⬇️ Baixar", on_click=lambda: ui.download(
                f"/download/foto/{photo['id']}")).classes("flex-1 text-white font-bold").style(
                f"background:{ORANGE};border-radius:12px;height:50px"
            ).props("unelevated")
            wa = "https://wa.me/?text=" + urllib.parse.quote(
                f"Sua foto: {share_url}")
            ui.button("WhatsApp", icon="chat", on_click=lambda u=wa: ui.navigate.to(
                u, new_tab=True)).classes("flex-1 text-white font-bold").style(
                f"background:{GREEN};border-radius:12px;height:50px"
            ).props("unelevated")


# ---------------------------------------------------------------------------
# Ferramenta de captura / upload (print 04) — reutilizável
# ---------------------------------------------------------------------------

def upload_zone(on_upload, multiple: bool = True,
                label: str = "Arraste fotos aqui ou toque para selecionar") -> None:
    """Zona de upload no estilo do print 01 (pontilhada, sem barra laranja).

    Sem o atributo `capture`, o iPhone oferece tanto 'Tirar Foto' quanto
    'Biblioteca' — cobre câmera e galeria no mesmo lugar.
    """
    ui.upload(multiple=multiple, auto_upload=True, on_upload=on_upload,
              label=label).props('flat bordered accept="image/*" color=grey-9').classes(
        "hf-upload w-full")
    ui.label("JPG, PNG, WEBP, HEIC").style(
        f"color:{GRAY};font-size:12px;text-align:center").classes("w-full")


def capture_tool(event_id: str) -> None:
    """Capturar (câmera do iPhone) ou carregar da galeria — uma zona só."""
    section_title("📸", "Capturar ou Carregar Foto")

    def handle_upload(e):
        try:
            photo = ingest_photo(event_id, e.name, e.content)
            ui.navigate.to(f"/foto/{photo['id']}")
        except Exception as exc:  # noqa: BLE001
            ui.notify(f"Erro ao processar a foto: {exc}", type="negative")

    upload_zone(handle_upload, multiple=True,
                label="📸 Toque para tirar foto ou escolher da galeria")


# ---------------------------------------------------------------------------
# HOME
# ---------------------------------------------------------------------------

@ui.page("/")
def home():
    setup()
    get_default_user()
    top_bar(show_profile=True)
    with page_container():
        section_title("⚙️", "Painel Principal")
        with ui.element("div").classes("w-full grid grid-cols-2 gap-4"):
            nav_card("event", "Criar Evento", "Novo álbum",
                     lambda: ui.navigate.to("/criar-evento"))
            nav_card("photo_library", "Meus Eventos", "Ver e gerenciar",
                     lambda: ui.navigate.to("/meus-eventos"))
            nav_card("cloud_upload", "Upload de Fotos", "Enviar para um evento",
                     lambda: ui.navigate.to("/upload"))
            nav_card("share", "Compartilhar", "Links dos álbuns",
                     lambda: ui.navigate.to("/compartilhar"))


# ---------------------------------------------------------------------------
# PERFIL  (print 02)
# ---------------------------------------------------------------------------

@ui.page("/perfil")
def perfil():
    setup()
    user = get_default_user()
    n_eventos = len(db.list_events(organizer_id=user["id"]))
    top_bar(show_back=True, show_profile=False)

    def info_dialog(titulo: str, conteudo: str):
        with ui.dialog() as d, ui.card().classes("hf-card w-80 gap-2"):
            ui.label(titulo).classes("text-white text-lg font-bold")
            ui.label(conteudo).style(f"color:{GRAY}")
            ui.button("Fechar", on_click=d.close).props("flat").style(f"color:{ORANGE}")
        d.open()

    def dados_dialog():
        with ui.dialog() as d, ui.card().classes("hf-card w-96 gap-3 p-4"):
            ui.label("Dados Cadastrais").classes("text-white text-lg font-bold")

            def f(icon, placeholder, value):
                inp = ui.input(placeholder=placeholder, value=value or "").props(
                    "outlined dense").classes("w-full hf-field")
                with inp.add_slot("prepend"):
                    ui.icon(icon).style(f"color:{ORANGE}")
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

    def row(icon: str, label: str, trailing=None, on_click=None, danger=False):
        color = "#ff453a" if danger else "#fff"
        el = ui.element("div").classes(
            "hf-card w-full flex items-center gap-3 px-4 py-4 cursor-pointer"
        )
        with el.on("click", on_click or (lambda: None)):
            ui.icon(icon).style(f"color:{'#ff453a' if danger else ORANGE};font-size:22px")
            ui.label(label).classes("font-semibold").style(f"color:{color};flex:1")
            if trailing is not None:
                trailing()
            if not danger:
                ui.icon("chevron_right").style(f"color:{GRAY}")

    with page_container():
        with ui.column().classes("w-full items-center gap-1 py-2"):
            icon_circle("person", 96)
            ui.label(user.get("name") or "Organizador").classes(
                "text-white font-extrabold").style("font-size:24px")
            ui.label(user.get("email") or "hostfoto.com.br").style(f"color:{GRAY}")

        def badge_count():
            ui.label(str(n_eventos)).classes("text-white font-bold").style(
                f"background:{ORANGE};border-radius:9999px;min-width:28px;height:28px;"
                "display:flex;align-items:center;justify-content:center;padding:0 8px"
            )

        def badge_pro():
            ui.label("PRO").classes("font-bold").style(
                f"background:{GREEN};color:#03361a;border-radius:9999px;padding:3px 12px;font-size:13px"
            )

        row("badge", "Dados Cadastrais", None, dados_dialog)
        row("calendar_month", "Meus Eventos", badge_count,
            lambda: ui.navigate.to("/meus-eventos"))
        row("credit_card", "Plano e Pagamento", badge_pro,
            lambda: info_dialog("Plano PRO",
                                "Você está no plano PRO — eventos e fotos ilimitados."))
        row("shield", "Segurança", None,
            lambda: info_dialog("Segurança", "Sua conta e seus álbuns estão protegidos."))
        row("error", "Suporte", None,
            lambda: info_dialog("Suporte", "Fale com a gente: suporte@hostfoto.com.br"))
        row("logout", "Sair", None,
            lambda: (ui.notify("Sessão encerrada", type="info"), ui.navigate.to("/")),
            danger=True)


# ---------------------------------------------------------------------------
# CRIAR EVENTO  (print 03)
# ---------------------------------------------------------------------------

@ui.page("/criar-evento")
def criar_evento():
    setup()
    user = get_default_user()
    top_bar(show_back=True)

    def field(icon: str, placeholder: str, date: bool = False):
        inp = ui.input(placeholder=placeholder).props("outlined dense").classes(
            "w-full hf-field")
        if date:
            inp.props("type=date")
        with inp.add_slot("prepend"):
            ui.icon(icon).style(f"color:{ORANGE}")
        return inp

    with page_container():
        section_title("📅", "Criar Novo Evento")
        with ui.element("div").classes("hf-card w-full p-4 gap-3 flex flex-col"):
            nome = field("person", "Nome do Evento")
            data = field("calendar_month", "Data", date=True)
            local = field("location_on", "Local do Evento")
            email = field("mail", "E-mail do organizador")
            fone = field("phone", "Telefone do organizador")

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
                ui.navigate.to(f"/evento/{ev['id']}/equipamento")

            ui.button("📅 Criar Evento", on_click=criar).classes(
                "w-full text-white font-bold"
            ).style(f"background:{ORANGE};border-radius:14px;height:54px").props("unelevated")


# ---------------------------------------------------------------------------
# ESCOLHER EQUIPAMENTO (após criar evento)
# ---------------------------------------------------------------------------

@ui.page("/evento/{event_id}/equipamento")
def equipamento(event_id: str):
    setup()
    event = db.get_event(event_id)
    top_bar(show_back=True)
    if not event:
        with page_container():
            ui.label("Evento não encontrado").classes("text-white")
        return
    with page_container():
        ui.label(event["name"]).classes("text-white font-extrabold").style("font-size:22px")
        section_title("🎥", "Como vai capturar as fotos?")
        cap = f"/evento/{event_id}/capturar"
        with ui.element("div").classes("w-full grid grid-cols-2 gap-4"):
            nav_card("photo_camera", "Câmera", "DSLR / Mirrorless",
                     lambda: ui.navigate.to(cap))
            nav_card("tablet_mac", "iPad", "Câmera do iPad",
                     lambda: ui.navigate.to(cap))
            nav_card("phone_iphone", "iPhone", "Câmera do iPhone",
                     lambda: ui.navigate.to(cap))
            nav_card("cloud_upload", "Upload", "Rolo da câmera / pastas",
                     lambda: ui.navigate.to(cap))
        ui.button("Ver evento e fotos", icon="photo_library",
                  on_click=lambda: ui.navigate.to(f"/evento/{event_id}")).props(
            "flat").style(f"color:{ORANGE}").classes("w-full")


# ---------------------------------------------------------------------------
# CAPTURAR / UPLOAD por evento (print 04)
# ---------------------------------------------------------------------------

@ui.page("/evento/{event_id}/capturar")
def capturar_page(event_id: str):
    setup()
    event = db.get_event(event_id)
    top_bar(show_back=True)
    if not event:
        with page_container():
            ui.label("Evento não encontrado").classes("text-white")
        return
    with page_container():
        ui.label(event["name"]).classes("text-white font-extrabold").style("font-size:20px")
        capture_tool(event_id)


# ---------------------------------------------------------------------------
# DETALHE DO EVENTO (galeria + adicionar + compartilhar)
# ---------------------------------------------------------------------------

@ui.page("/evento/{event_id}")
def evento_detalhe(event_id: str, request: Request):
    setup()
    event = db.get_event(event_id)
    top_bar(show_back=True)
    if not event:
        with page_container():
            ui.label("Evento não encontrado").classes("text-white")
        return
    base = base_from_request(request)
    album = f"{base}/e/{event_id}"
    photos_ = db.list_photos(event_id)
    with page_container():
        ui.label(event["name"]).classes("text-white font-extrabold").style("font-size:22px")
        meta = " · ".join(filter(None, [event.get("location"), event.get("date")]))
        if meta:
            ui.label(meta).style(f"color:{GRAY}")
        with ui.row().classes("w-full gap-3 no-wrap"):
            ui.button("Adicionar fotos", icon="add_a_photo",
                      on_click=lambda: ui.navigate.to(f"/evento/{event_id}/capturar")).classes(
                "flex-1 text-white font-bold").style(
                f"background:{ORANGE};border-radius:12px;height:48px").props("unelevated")
            ui.button("Compartilhar", icon="share",
                      on_click=lambda: (ui.clipboard.write(album),
                                        ui.notify("Link copiado!", type="positive"))).classes(
                "flex-1").props("outline").style(f"color:{ORANGE}")
        section_title("🖼️", f"Fotos ({len(photos_)})")
        if not photos_:
            ui.label("Nenhuma foto ainda.").style(f"color:{GRAY}")
        else:
            with ui.element("div").classes("w-full grid grid-cols-3 gap-2"):
                for p in reversed(photos_):
                    ui.image(p["thumbnail_url"]).classes(
                        "w-full aspect-square object-cover cursor-pointer"
                    ).style("border-radius:10px").on(
                        "click", lambda x=p: ui.navigate.to(f"/foto/{x['id']}"))


# ---------------------------------------------------------------------------
# FOTO + QR (print 05)
# ---------------------------------------------------------------------------

@ui.page("/foto/{photo_id}")
def foto_page(photo_id: str, request: Request):
    setup()
    photo = get_photo(photo_id)
    top_bar(show_back=True)
    if not photo:
        with page_container():
            ui.label("Foto não encontrada").classes("text-white")
        return
    base = base_from_request(request)
    with page_container():
        ui.image(photo["preview_url"]).classes("w-full").style("border-radius:14px")
        qr_result_card(photo, base)


# ---------------------------------------------------------------------------
# MEUS EVENTOS (lista + busca)
# ---------------------------------------------------------------------------

@ui.page("/meus-eventos")
def meus_eventos():
    setup()
    user = get_default_user()
    top_bar(show_back=True)
    with page_container():
        section_title("📅", "Meus Eventos")
        busca = ui.input(placeholder="Buscar por nome…").props(
            'clearable borderless').classes("hf-card w-full px-4")

        @ui.refreshable
        def lista():
            termo = (busca.value or "").lower()
            eventos = db.list_events(organizer_id=user["id"])
            eventos = [e for e in eventos if termo in e["name"].lower()]
            if not eventos:
                ui.label("Nenhum evento.").style(f"color:{GRAY}")
                return
            for ev in eventos:
                fotos = db.list_photos(ev["id"])
                el = ui.element("div").classes(
                    "hf-card w-full flex items-center gap-3 p-3 cursor-pointer")
                with el.on("click", lambda e=ev: ui.navigate.to(f"/evento/{e['id']}")):
                    if fotos:
                        ui.image(fotos[-1]["thumbnail_url"]).classes(
                            "w-16 h-16 object-cover").style("border-radius:10px")
                    else:
                        with ui.element("div").classes(
                            "flex items-center justify-center").style(
                            f"width:64px;height:64px;border-radius:10px;background:{BG}"):
                            ui.icon("image").style(f"color:{GRAY}")
                    with ui.column().classes("gap-0").style("flex:1"):
                        ui.label(ev["name"]).classes("text-white font-bold")
                        sub = " · ".join(filter(None, [ev.get("location"), ev.get("date")]))
                        if sub:
                            ui.label(sub).style(f"color:{GRAY};font-size:13px")
                        ui.label(f"{len(fotos)} fotos").style(
                            f"color:{ORANGE};font-size:12px")
                    ui.icon("chevron_right").style(f"color:{GRAY}")

        busca.on("update:model-value", lambda: lista.refresh())
        lista()


# ---------------------------------------------------------------------------
# UPLOAD (escolhe evento -> capturar) — Home box 3
# ---------------------------------------------------------------------------

@ui.page("/upload")
def upload_page():
    setup()
    user = get_default_user()
    top_bar(show_back=True)
    eventos = db.list_events(organizer_id=user["id"])
    with page_container():
        section_title("☁️", "Upload de Fotos")
        ui.label("Escolha o evento para enviar as fotos:").style(f"color:{GRAY}")
        if not eventos:
            with ui.element("div").classes("hf-card w-full p-6 flex flex-col items-center gap-2"):
                ui.icon("event").style(f"color:{GRAY};font-size:40px")
                ui.label("Nenhum evento ainda").style(f"color:{GRAY}")
                ui.button("Criar evento", on_click=lambda: ui.navigate.to("/criar-evento")).props(
                    "flat").style(f"color:{ORANGE}")
            return
        for ev in eventos:
            fotos = db.list_photos(ev["id"])
            el = ui.element("div").classes(
                "hf-card w-full flex items-center gap-3 p-3 cursor-pointer")
            with el.on("click", lambda e=ev: ui.navigate.to(f"/evento/{e['id']}/capturar")):
                ui.icon("cloud_upload").style(f"color:{ORANGE};font-size:24px")
                with ui.column().classes("gap-0").style("flex:1"):
                    ui.label(ev["name"]).classes("text-white font-bold")
                    ui.label(f"{len(fotos)} fotos").style(f"color:{GRAY};font-size:12px")
                ui.icon("chevron_right").style(f"color:{GRAY}")


# ---------------------------------------------------------------------------
# COMPARTILHAR (links das pastas dos eventos) — Home box 4
# ---------------------------------------------------------------------------

@ui.page("/compartilhar")
def compartilhar_page(request: Request):
    setup()
    user = get_default_user()
    top_bar(show_back=True)
    base = base_from_request(request)
    eventos = db.list_events(organizer_id=user["id"])
    with page_container():
        section_title("🔗", "Compartilhar álbuns")
        if not eventos:
            ui.label("Nenhum evento ainda.").style(f"color:{GRAY}")
            return
        for ev in eventos:
            link = f"{base}/e/{ev['id']}"
            with ui.element("div").classes("hf-card w-full p-3 flex flex-col gap-2"):
                ui.label(ev["name"]).classes("text-white font-bold")
                ui.label(link).style(f"color:{GRAY};font-size:12px;word-break:break-all")
                with ui.row().classes("w-full gap-2 no-wrap"):
                    ui.button("Copiar", icon="content_copy",
                              on_click=lambda l=link: (ui.clipboard.write(l),
                                                       ui.notify("Copiado!", type="positive"))
                              ).classes("flex-1").props("outline").style(f"color:{ORANGE}")
                    ui.button("Abrir", icon="open_in_new",
                              on_click=lambda e=ev: ui.navigate.to(f"/e/{e['id']}", new_tab=True)
                              ).classes("flex-1 text-white").style(
                        f"background:{ORANGE};border-radius:10px").props("unelevated")
                    wa = "https://wa.me/?text=" + urllib.parse.quote(
                        f"Álbum {ev['name']}: {link}")
                    ui.button("WhatsApp", icon="chat",
                              on_click=lambda u=wa: ui.navigate.to(u, new_tab=True)
                              ).classes("flex-1 text-white").style(
                        f"background:{GREEN};border-radius:10px").props("unelevated")


# ---------------------------------------------------------------------------
# ÁLBUM PÚBLICO (cliente)
# ---------------------------------------------------------------------------

@ui.page("/e/{event_id}")
def album_publico(event_id: str, request: Request):
    setup()
    event = db.get_event(event_id)
    top_bar(show_profile=False)
    if not event:
        with page_container():
            ui.label("Álbum não encontrado").classes("text-white")
        return
    photos_ = db.list_photos(event_id)
    with page_container():
        ui.label(event["name"]).classes("text-white font-extrabold").style("font-size:24px")
        ui.label(f"{len(photos_)} fotos").style(f"color:{GRAY}")
        if photos_:
            ui.button("⬇️ Baixar tudo", on_click=lambda: ui.download(
                f"/download/evento/{event_id}")).classes("w-full text-white font-bold").style(
                f"background:{ORANGE};border-radius:12px;height:48px").props("unelevated")
            with ui.element("div").classes("w-full grid grid-cols-2 gap-3"):
                for p in photos_:
                    with ui.element("div").classes("hf-card overflow-hidden p-0"):
                        ui.image(p["thumbnail_url"]).classes(
                            "w-full aspect-square object-cover cursor-pointer").on(
                            "click", lambda x=p: ui.navigate.to(f"/foto/{x['id']}"))
                        ui.button("Baixar", icon="download",
                                  on_click=lambda x=p: ui.download(
                                      f"/download/foto/{x['id']}")).classes(
                            "w-full").props("flat dense").style(f"color:{ORANGE}")
        else:
            ui.label("As fotos aparecem aqui assim que o fotógrafo enviar.").style(
                f"color:{GRAY}")


ui.run_with(app, title="HostFoto", favicon="📸", dark=True, storage_secret="hostfoto")
