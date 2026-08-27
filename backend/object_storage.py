"""Emergent Object Storage — yüklenen dosyaların kalıcı bulut deposu."""
import asyncio
import logging
import os

import requests

logger = logging.getLogger(__name__)

STORAGE_BASE = (os.environ.get("INTEGRATION_PROXY_URL") or "").strip() or "https://integrations.emergentagent.com"
STORAGE_URL = STORAGE_BASE.rstrip("/") + "/objstore/api/v1/storage"
EMERGENT_KEY = os.environ.get("EMERGENT_LLM_KEY")
APP_NAME = "hotelbox"
storage_key = None


def init_storage(force: bool = False):
    global storage_key
    if storage_key and not force:
        return storage_key
    resp = requests.post(f"{STORAGE_URL}/init", json={"emergent_key": EMERGENT_KEY}, timeout=30)
    resp.raise_for_status()
    storage_key = resp.json()["storage_key"]
    return storage_key


def put_object(path: str, data: bytes, content_type: str) -> dict:
    key = init_storage()
    resp = requests.put(f"{STORAGE_URL}/objects/{path}",
                        headers={"X-Storage-Key": key, "Content-Type": content_type},
                        data=data, timeout=120)
    if resp.status_code == 404:
        key = init_storage(force=True)
        resp = requests.put(f"{STORAGE_URL}/objects/{path}",
                            headers={"X-Storage-Key": key, "Content-Type": content_type},
                            data=data, timeout=120)
    resp.raise_for_status()
    return resp.json()


def get_object(path: str):
    key = init_storage()
    resp = requests.get(f"{STORAGE_URL}/objects/{path}",
                        headers={"X-Storage-Key": key}, timeout=60)
    resp.raise_for_status()
    return resp.content, resp.headers.get("Content-Type", "application/octet-stream")


async def save_upload(subpath: str, data: bytes, content_type: str = ""):
    """Yüklemeyi kalıcı bulut depoya yazar. subpath örn: 'rooms/abc.jpg'. Hata yükseltir."""
    import mimetypes
    ct = content_type or mimetypes.guess_type(subpath)[0] or "application/octet-stream"
    path = f"{APP_NAME}/uploads/{subpath}"
    try:
        await asyncio.to_thread(put_object, path, data, ct)
    except Exception as e:
        logger.error("Object storage yazımı başarısız (%s): %s", subpath, e)
        raise


async def fetch_upload(subpath: str):
    """Bulut depodan dosyayı döner → (bytes, content_type) veya None."""
    try:
        return await asyncio.to_thread(get_object, f"{APP_NAME}/uploads/{subpath}")
    except Exception:
        return None
