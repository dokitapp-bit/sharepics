import qrcode
import qrcode.image.svg
from io import BytesIO
import base64
import os
from PIL import Image, ImageDraw, ImageFont


def generate_qr_base64(data: str, size: int = 300) -> str:
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=2,
    )
    qr.add_data(data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="#f97316", back_color="#1c1c1e")
    img = img.resize((size, size), Image.LANCZOS)

    buffer = BytesIO()
    img.save(buffer, format="PNG")
    b64 = base64.b64encode(buffer.getvalue()).decode()
    return f"data:image/png;base64,{b64}"


def generate_lead_qr(lead_id: str, lead_number: int, event_name: str, base_url: str, save_path: str) -> str:
    data = f"LEAD:{lead_id}:{lead_number}"

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=12,
        border=3,
    )
    qr.add_data(data)
    qr.make(fit=True)

    qr_img = qr.make_image(fill_color="#1c1c1e", back_color="white")
    qr_img = qr_img.convert("RGB")
    qr_size = qr_img.size[0]

    card_w, card_h = qr_size + 60, qr_size + 120
    card = Image.new("RGB", (card_w, card_h), "#1c1c1e")

    draw = ImageDraw.Draw(card)

    header_h = 50
    draw.rectangle([0, 0, card_w, header_h], fill="#f97316")

    try:
        font_title = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 18)
        font_sub = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 14)
        font_num = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 22)
    except Exception:
        font_title = ImageFont.load_default()
        font_sub = font_title
        font_num = font_title

    title = "Shared Pics"
    bbox = draw.textbbox((0, 0), title, font=font_title)
    tw = bbox[2] - bbox[0]
    draw.text(((card_w - tw) // 2, 14), title, fill="white", font=font_title)

    qr_x, qr_y = 30, header_h + 10
    card.paste(qr_img, (qr_x, qr_y))

    lead_text = f"Lead #{lead_number}"
    bbox2 = draw.textbbox((0, 0), lead_text, font=font_num)
    tw2 = bbox2[2] - bbox2[0]
    draw.text(((card_w - tw2) // 2, qr_y + qr_size + 10), lead_text, fill="#f97316", font=font_num)

    event_short = event_name[:28] + "..." if len(event_name) > 28 else event_name
    bbox3 = draw.textbbox((0, 0), event_short, font=font_sub)
    tw3 = bbox3[2] - bbox3[0]
    draw.text(((card_w - tw3) // 2, qr_y + qr_size + 38), event_short, fill="#888888", font=font_sub)

    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    card.save(save_path, "PNG", quality=95)

    buffer = BytesIO()
    card.save(buffer, "PNG")
    b64 = base64.b64encode(buffer.getvalue()).decode()
    return f"data:image/png;base64,{b64}"


def generate_event_qr(event_id: str, base_url: str, save_path: str) -> str:
    url = f"{base_url}/register/{event_id}"

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=12,
        border=3,
    )
    qr.add_data(url)
    qr.make(fit=True)

    qr_img = qr.make_image(fill_color="#1c1c1e", back_color="white")
    qr_img = qr_img.convert("RGB")
    qr_size = qr_img.size[0]

    card_w, card_h = qr_size + 60, qr_size + 80
    card = Image.new("RGB", (card_w, card_h), "#1c1c1e")
    draw = ImageDraw.Draw(card)
    draw.rectangle([0, 0, card_w, 40], fill="#f97316")

    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 16)
        font_small = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 12)
    except Exception:
        font = ImageFont.load_default()
        font_small = font

    draw.text((10, 11), "Shared Pics — Escanear para participar", fill="white", font=font_small)
    card.paste(qr_img, (30, 50))

    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    card.save(save_path, "PNG", quality=95)

    buffer = BytesIO()
    card.save(buffer, "PNG")
    b64 = base64.b64encode(buffer.getvalue()).decode()
    return f"data:image/png;base64,{b64}"
