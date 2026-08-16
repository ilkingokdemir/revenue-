"""Otel logosu yönetimi — tüm PDF raporlarında otomatik markalama."""
import base64
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

MAX_LOGO_BYTES = 700 * 1024


async def get_logo_reader(db, pid: str):
    """PDF'ler için ImageReader döner (önce yüklenen b64, yoksa logo_url)."""
    if not pid:
        return None
    ts = await db.template_settings.find_one({"property_id": pid}, {"_id": 0, "logo_b64": 1, "logo_url": 1})
    if not ts:
        return None
    from io import BytesIO
    from reportlab.lib.utils import ImageReader
    if ts.get("logo_b64"):
        try:
            return ImageReader(BytesIO(base64.b64decode(ts["logo_b64"])))
        except Exception:
            return None
    url = (ts.get("logo_url") or "").strip()
    if url:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10, follow_redirects=True) as cl:
                r = await cl.get(url)
            if r.status_code == 200:
                return ImageReader(BytesIO(r.content))
        except Exception:
            return None
    return None


def draw_logo(c, img, page_w, page_h, mm):
    """Sayfa sağ üst köşesine logoyu çizer."""
    try:
        iw, ih = img.getSize()
        lw = 22 * mm
        lh = lw * ih / iw
        if lh > 24 * mm:
            lh = 24 * mm
            lw = lh * iw / ih
        c.drawImage(img, page_w - lw - 8 * mm, page_h - lh - 4 * mm,
                    width=lw, height=lh, mask="auto", preserveAspectRatio=True)
    except Exception:
        pass


def create_branding_router(db, require_roles):
    router = APIRouter(prefix="/branding", tags=["branding"])
    ROLES = ("admin", "manager")

    @router.post("/logo/{pid}")
    async def upload_logo(pid: str, data: dict, _u: dict = Depends(require_roles(*ROLES))):
        raw = (data.get("logo_b64") or "").strip()
        if not raw:
            raise HTTPException(400, "logo_b64 gerekli")
        mime = "image/png"
        if raw.startswith("data:"):
            head, _, raw = raw.partition(",")
            mime = head.split(";")[0].replace("data:", "") or mime
        try:
            blob = base64.b64decode(raw)
        except Exception:
            raise HTTPException(400, "Geçersiz base64")
        if len(blob) > MAX_LOGO_BYTES:
            raise HTTPException(400, f"Logo çok büyük (max {MAX_LOGO_BYTES // 1024}KB)")
        if mime not in ("image/png", "image/jpeg", "image/webp"):
            raise HTTPException(400, "Sadece PNG/JPEG/WebP desteklenir")
        await db.template_settings.update_one(
            {"property_id": pid},
            {"$set": {"property_id": pid, "logo_b64": base64.b64encode(blob).decode(),
                      "logo_mime": mime,
                      "logo_updated_at": datetime.now(timezone.utc).isoformat()}}, upsert=True)
        return {"ok": True, "size_kb": round(len(blob) / 1024, 1), "mime": mime}

    @router.get("/logo/{pid}")
    async def get_logo(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        ts = await db.template_settings.find_one(
            {"property_id": pid}, {"_id": 0, "logo_b64": 1, "logo_mime": 1})
        if not ts or not ts.get("logo_b64"):
            raise HTTPException(404, "Logo yüklenmemiş")
        return Response(content=base64.b64decode(ts["logo_b64"]),
                        media_type=ts.get("logo_mime", "image/png"))

    @router.delete("/logo/{pid}")
    async def delete_logo(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        await db.template_settings.update_one(
            {"property_id": pid},
            {"$unset": {"logo_b64": "", "logo_mime": "", "logo_updated_at": ""}})
        return {"ok": True}

    return router
