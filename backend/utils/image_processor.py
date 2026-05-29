from __future__ import annotations
from PIL import Image
import os
from pathlib import Path


PREVIEW_SIZE = (1920, 1080)
THUMBNAIL_SIZE = (400, 400)
JPEG_QUALITY = 88


def process_image(original_path: str, event_id: str, filename: str, upload_root: str) -> dict:
    stem = Path(filename).stem
    ext = ".jpg"

    preview_dir = os.path.join(upload_root, "previews", event_id)
    thumb_dir = os.path.join(upload_root, "thumbnails", event_id)
    os.makedirs(preview_dir, exist_ok=True)
    os.makedirs(thumb_dir, exist_ok=True)

    preview_path = os.path.join(preview_dir, f"{stem}{ext}")
    thumb_path = os.path.join(thumb_dir, f"{stem}{ext}")

    with Image.open(original_path) as img:
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        preview = img.copy()
        preview.thumbnail(PREVIEW_SIZE, Image.LANCZOS)
        preview.save(preview_path, "JPEG", quality=JPEG_QUALITY, optimize=True)

        thumb = img.copy()
        thumb.thumbnail(THUMBNAIL_SIZE, Image.LANCZOS)

        w, h = thumb.size
        side = min(w, h)
        left = (w - side) // 2
        top = (h - side) // 2
        thumb = thumb.crop((left, top, left + side, top + side))
        thumb = thumb.resize((300, 300), Image.LANCZOS)
        thumb.save(thumb_path, "JPEG", quality=80, optimize=True)

    return {
        "preview_path": preview_path,
        "thumb_path": thumb_path,
    }


def detect_qr_in_image(image_path: str) -> str | None:
    try:
        from pyzbar.pyzbar import decode
        with Image.open(image_path) as img:
            decoded = decode(img)
            for d in decoded:
                data = d.data.decode("utf-8")
                if data.startswith("LEAD:"):
                    return data
        return None
    except ImportError:
        return None
    except Exception:
        return None
