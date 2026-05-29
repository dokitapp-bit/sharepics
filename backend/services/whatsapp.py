import httpx
import os
from typing import Optional


EVOLUTION_API_URL = os.getenv("EVOLUTION_API_URL", "http://localhost:8080")
EVOLUTION_API_KEY = os.getenv("EVOLUTION_API_KEY", "")
EVOLUTION_INSTANCE = os.getenv("EVOLUTION_INSTANCE", "sharedpics")


async def send_gallery_link(phone: str, name: str, gallery_url: str, event_name: str) -> bool:
    if not EVOLUTION_API_KEY:
        print(f"[WhatsApp MOCK] Para {phone}: Suas fotos do evento '{event_name}' estão prontas! {gallery_url}")
        return True

    phone_clean = "".join(filter(str.isdigit, phone))
    if not phone_clean.startswith("55"):
        phone_clean = "55" + phone_clean

    message = (
        f"📸 *Olá, {name}!*\n\n"
        f"Suas fotos do evento *{event_name}* estão prontas! 🎉\n\n"
        f"🔗 Acesse sua galeria exclusiva:\n{gallery_url}\n\n"
        f"_Shared Pics — Compartilhe momentos automaticamente._"
    )

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{EVOLUTION_API_URL}/message/sendText/{EVOLUTION_INSTANCE}",
                headers={"apikey": EVOLUTION_API_KEY, "Content-Type": "application/json"},
                json={"number": phone_clean, "text": message}
            )
            return resp.status_code == 200
    except Exception as e:
        print(f"[WhatsApp] Erro ao enviar para {phone}: {e}")
        return False


async def send_event_confirmation(phone: str, name: str, lead_number: int,
                                   event_name: str, qr_url: str) -> bool:
    if not EVOLUTION_API_KEY:
        print(f"[WhatsApp MOCK] Confirmação para Lead #{lead_number} - {phone}")
        return True

    phone_clean = "".join(filter(str.isdigit, phone))
    if not phone_clean.startswith("55"):
        phone_clean = "55" + phone_clean

    message = (
        f"✅ *{name}, cadastro confirmado!*\n\n"
        f"Evento: *{event_name}*\n"
        f"Seu número: *Lead #{lead_number}*\n\n"
        f"📸 O fotógrafo irá escanear seu QR Code antes de tirar sua foto.\n\n"
        f"_Em breve você receberá suas fotos aqui mesmo!_"
    )

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{EVOLUTION_API_URL}/message/sendText/{EVOLUTION_INSTANCE}",
                headers={"apikey": EVOLUTION_API_KEY, "Content-Type": "application/json"},
                json={"number": phone_clean, "text": message}
            )
            return resp.status_code == 200
    except Exception as e:
        print(f"[WhatsApp] Erro: {e}")
        return False
