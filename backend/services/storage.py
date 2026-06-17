"""
Supabase Storage (API REST) para persistir fotos e o banco (db.json).

Ativa-se sozinho quando SUPABASE_URL + SUPABASE_SERVICE_KEY estão no ambiente;
caso contrário, `enabled()` é False e o app continua usando o disco local.

Vars de ambiente:
  SUPABASE_URL          ex: https://xxxx.supabase.co
  SUPABASE_SERVICE_KEY  service_role (secreta)
  SUPABASE_BUCKET       nome do bucket público (default: snapshare)
"""
from __future__ import annotations

import os
import mimetypes

import httpx

SUPABASE_URL = (os.getenv("SUPABASE_URL") or "").rstrip("/")
SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY") or ""
BUCKET = os.getenv("SUPABASE_BUCKET") or "snapshare"
TIMEOUT = float(os.getenv("SUPABASE_TIMEOUT", "30"))

DB_KEY = "_db/db.json"


def enabled() -> bool:
    return bool(SUPABASE_URL and SERVICE_KEY)


def _obj_url(key: str) -> str:
    return f"{SUPABASE_URL}/storage/v1/object/{BUCKET}/{key}"


def public_url(key: str) -> str:
    return f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET}/{key}"


def _headers(content_type: str | None = None, upsert: bool = True) -> dict:
    h = {"Authorization": f"Bearer {SERVICE_KEY}", "apikey": SERVICE_KEY}
    if content_type:
        h["Content-Type"] = content_type
    if upsert:
        h["x-upsert"] = "true"
    return h


def upload_bytes(key: str, data: bytes,
                 content_type: str = "application/octet-stream") -> str:
    r = httpx.post(_obj_url(key), content=data,
                   headers=_headers(content_type), timeout=TIMEOUT)
    r.raise_for_status()
    return public_url(key)


def upload_file(local_path: str, key: str, content_type: str | None = None) -> str:
    if not content_type:
        content_type = mimetypes.guess_type(local_path)[0] or "application/octet-stream"
    with open(local_path, "rb") as f:
        return upload_bytes(key, f.read(), content_type)


def fetch_url_bytes(url: str) -> bytes | None:
    """GET genérico (serve para URLs públicas do bucket)."""
    try:
        r = httpx.get(url, timeout=TIMEOUT)
        if r.status_code == 200:
            return r.content
    except Exception:
        return None
    return None


def download_key_bytes(key: str) -> bytes | None:
    """Download autorizado (funciona mesmo se o bucket for privado)."""
    try:
        r = httpx.get(_obj_url(key), headers=_headers(), timeout=TIMEOUT)
        if r.status_code == 200:
            return r.content
    except Exception:
        return None
    return None


# --- persistência do banco (db.json) ---------------------------------------

def push_db(local_path: str) -> bool:
    try:
        with open(local_path, "rb") as f:
            upload_bytes(DB_KEY, f.read(), "application/json")
        return True
    except Exception:
        return False


def pull_db(local_path: str) -> bool:
    data = download_key_bytes(DB_KEY)
    if data is None:
        return False
    try:
        with open(local_path, "wb") as f:
            f.write(data)
        return True
    except Exception:
        return False
