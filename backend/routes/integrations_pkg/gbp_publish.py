"""
Google Business Profile publish queue (PENDING-APPROVAL / MOCK mode).

Live GBP API access requires Google project approval (60+ day verified
Business Profile, quota grant). Until GBP_LIVE=true and OAuth credentials
are configured, approved review replies are queued with status
PENDING_APPROVAL instead of being pushed to Google.
"""
from datetime import datetime, timezone
import logging
import os

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
import secrets
import uuid
from urllib.parse import urlencode
import httpx

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
ACCOUNTS = "https://mybusinessaccountmanagement.googleapis.com/v1"
LOCATIONS = "https://mybusinessbusinessinformation.googleapis.com/v1"
REVIEWS = "https://mybusiness.googleapis.com/v4"
SCOPE = "https://www.googleapis.com/auth/business.manage"


def _cipher():
    key = os.environ.get("TOKEN_ENCRYPTION_KEY", "")
    if not key:
        return None
    from cryptography.fernet import Fernet
    return Fernet(key.encode())


def _enc(v: str) -> str:
    c = _cipher()
    return c.encrypt(v.encode()).decode() if c else v


def _dec(v: str) -> str:
    c = _cipher()
    return c.decrypt(v.encode()).decode() if c else v


def _creds():
    return os.environ.get("GOOGLE_CLIENT_ID", ""), os.environ.get("GOOGLE_CLIENT_SECRET", "")


def _redirect_uri():
    return f"{os.environ.get('PUBLIC_BASE_URL', '').rstrip('/')}/api/gbp/oauth/callback"


async def gbp_access_token(db, property_id: str) -> str:
    cid, sec = _creds()
    tok = await db.google_tokens.find_one({"property_id": property_id}, {"_id": 0}) or await db.google_tokens.find_one({}, {"_id": 0})
    if not tok:
        raise HTTPException(401, "Google Business Profile bağlı değil")
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.post(TOKEN_URL, data={"client_id": cid, "client_secret": sec,
                                          "refresh_token": _dec(tok["refresh_token"]), "grant_type": "refresh_token"})
    if r.status_code in (400, 401):
        await db.google_tokens.update_one({"id": tok["id"]}, {"$set": {"status": "revoked"}})
        raise HTTPException(401, "Google yetkisi süresi dolmuş/iptal; yeniden bağlanın")
    r.raise_for_status()
    return r.json()["access_token"]


async def gbp_publish_reply(db, review: dict, comment: str) -> dict:
    """Canlı yayın: accounts/{a}/locations/{l}/reviews/{r}/reply (PUT). Gerekli: google_tokens + mapping (account_id, location_id) + external_review_id."""
    if len(comment.encode("utf-8")) > 4096:
        raise HTTPException(422, "Yanıt 4096 baytı aşıyor")
    pid = review.get("property_id", "")
    tok = await db.google_tokens.find_one({"property_id": pid}, {"_id": 0}) or await db.google_tokens.find_one({}, {"_id": 0})
    if not tok or not tok.get("account_id") or not tok.get("location_id"):
        raise HTTPException(400, "Google konumu seçilmedi (Bağlantı Sihirbazı → Konum seç)")
    rid = review.get("external_review_id") or (review.get("external_id") or "").replace("gp-", "")
    if not rid:
        raise HTTPException(400, "Bu yorumun Google review ID'si yok (Places API yorumu yanıtlanamaz; GBP senkronu gerekir)")
    token = await gbp_access_token(db, pid)
    name = f"accounts/{tok['account_id']}/locations/{tok['location_id']}/reviews/{rid}"
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.put(f"{REVIEWS}/{name}/reply", headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                        json={"comment": comment})
    if r.is_error:
        raise HTTPException(r.status_code, f"Google: {r.text[:200]}")
    data = r.json() if r.content else {}
    await db.gbp_publish_queue.insert_one({"id": str(uuid.uuid4()), "property_id": pid, "review_id": review.get("id"), "status": "PUBLISHED",
                                          "google_name": name, "reply": data, "created_at": datetime.now(timezone.utc).isoformat()})
    return {"ok": True, "google_name": name, "update_time": data.get("updateTime")}

logger = logging.getLogger(__name__)


def create_gbp_router(db, require_roles):
    router = APIRouter()

    def _live() -> bool:
        return os.environ.get("GBP_LIVE", "false").lower() == "true"

    # ---------- Bağlantı Sihirbazı (OAuth 2.0, business.manage) ----------
    @router.get("/gbp/oauth/config")
    async def oauth_config(_: dict = Depends(require_roles("admin", "manager"))):
        cid, sec = _creds()
        return {"client_configured": bool(cid and sec), "redirect_uri": _redirect_uri(), "scope": SCOPE,
                "encrypted_storage": bool(os.environ.get("TOKEN_ENCRYPTION_KEY")),
                "missing": [k for k, v in (("GOOGLE_CLIENT_ID", cid), ("GOOGLE_CLIENT_SECRET", sec)) if not v]}

    @router.get("/gbp/oauth/start")
    async def oauth_start(property_id: str = "default", current_user: dict = Depends(require_roles("admin", "manager"))):
        cid, sec = _creds()
        if not (cid and sec):
            raise HTTPException(400, "GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET backend .env'de yok. Google Cloud → Credentials → OAuth client (Web) oluşturup redirect URI'yi ekleyin: " + _redirect_uri())
        state = secrets.token_urlsafe(32)
        await db.oauth_states.insert_one({"id": state, "property_id": property_id, "user": current_user.get("email", ""),
                                          "created_at": datetime.now(timezone.utc).isoformat()})
        params = {"client_id": cid, "redirect_uri": _redirect_uri(), "response_type": "code", "scope": SCOPE,
                  "access_type": "offline", "prompt": "consent", "include_granted_scopes": "true", "state": state}
        return {"url": AUTH_URL + "?" + urlencode(params)}

    @router.get("/gbp/oauth/callback")
    async def oauth_callback(code: str = "", state: str = "", error: str = ""):
        front = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")
        if error or not code or not state:
            return RedirectResponse(f"{front}/?gbp=error&reason={error or 'missing_code'}")
        st = await db.oauth_states.find_one_and_delete({"id": state})
        if not st:
            return RedirectResponse(f"{front}/?gbp=error&reason=invalid_state")
        cid, sec = _creds()
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.post(TOKEN_URL, data={"client_id": cid, "client_secret": sec, "code": code,
                                              "grant_type": "authorization_code", "redirect_uri": _redirect_uri()})
        if r.is_error:
            return RedirectResponse(f"{front}/?gbp=error&reason=token_exchange")
        tok = r.json()
        if not tok.get("refresh_token"):
            return RedirectResponse(f"{front}/?gbp=error&reason=no_refresh_token")
        await db.google_tokens.update_one({"property_id": st["property_id"]}, {"$set": {
            "id": str(uuid.uuid4()), "property_id": st["property_id"], "refresh_token": _enc(tok["refresh_token"]),
            "scope": tok.get("scope"), "status": "connected", "connected_by": st.get("user", ""),
            "connected_at": datetime.now(timezone.utc).isoformat()}}, upsert=True)
        return RedirectResponse(f"{front}/?gbp=connected")

    @router.get("/gbp/oauth/locations")
    async def oauth_locations(property_id: str = "default", _: dict = Depends(require_roles("admin", "manager"))):
        token = await gbp_access_token(db, property_id)
        hdr = {"Authorization": f"Bearer {token}"}
        out = []
        async with httpx.AsyncClient(timeout=25) as c:
            ra = await c.get(f"{ACCOUNTS}/accounts", headers=hdr, params={"pageSize": 20})
            if ra.is_error:
                raise HTTPException(ra.status_code, f"Google accounts: {ra.text[:200]}")
            for acc in ra.json().get("accounts", []):
                aid = acc["name"].split("/")[-1]
                rl = await c.get(f"{LOCATIONS}/accounts/{aid}/locations", headers=hdr,
                                 params={"pageSize": 100, "readMask": "name,title,storeCode"})
                for loc in (rl.json().get("locations", []) if not rl.is_error else []):
                    out.append({"account_id": aid, "account_name": acc.get("accountName", ""),
                                "location_id": loc["name"].split("/")[-1], "title": loc.get("title", ""), "store_code": loc.get("storeCode", "")})
        return {"locations": out}

    @router.post("/gbp/oauth/select-location")
    async def select_location(body: dict, _: dict = Depends(require_roles("admin", "manager"))):
        pid = body.get("property_id", "default")
        res = await db.google_tokens.update_one({"property_id": pid}, {"$set": {
            "account_id": str(body.get("account_id", "")), "location_id": str(body.get("location_id", "")),
            "location_title": body.get("title", "")}})
        if not res.matched_count:
            raise HTTPException(404, "Önce Google ile bağlanın")
        return {"ok": True}

    @router.delete("/gbp/oauth/disconnect")
    async def disconnect(property_id: str = "default", _: dict = Depends(require_roles("admin", "manager"))):
        await db.google_tokens.delete_many({"property_id": property_id})
        return {"ok": True}

    @router.get("/gbp/status")
    async def status(property_id: str = "",
                     _: dict = Depends(require_roles("admin", "manager"))):
        q = {"property_id": property_id} if property_id else {}
        pending = await db.gbp_publish_queue.count_documents({**q, "status": "PENDING_APPROVAL"})
        published = await db.gbp_publish_queue.count_documents({**q, "status": "PUBLISHED"})
        tok = await db.google_tokens.find_one({"property_id": property_id or "default"}, {"_id": 0, "refresh_token": 0}) or \
              await db.google_tokens.find_one({}, {"_id": 0, "refresh_token": 0})
        cid, sec = _creds()
        return {"live": _live() or bool(tok), "mode": "live" if (_live() or tok) else "mock_pending_approval",
                "connected": bool(tok), "connection": tok, "client_configured": bool(cid and sec),
                "redirect_uri": _redirect_uri(), "queue_pending": pending, "published": published}

    @router.get("/gbp/queue")
    async def queue(property_id: str = "", limit: int = 50,
                    _: dict = Depends(require_roles("admin", "manager"))):
        q = {"property_id": property_id} if property_id else {}
        items = await db.gbp_publish_queue.find(q, {"_id": 0}).sort(
            "created_at", -1).to_list(min(limit, 200))
        return {"items": items, "count": len(items)}

    @router.post("/gbp/publish/{queue_id}")
    async def publish(queue_id: str,
                      current_user: dict = Depends(require_roles("admin", "manager"))):
        item = await db.gbp_publish_queue.find_one({"id": queue_id}, {"_id": 0})
        if not item:
            raise HTTPException(404, "Kuyruk kaydı bulunamadı")
        if not _live():
            return {"mode": "mock", "status": "PENDING_APPROVAL",
                    "message": ("Google Business Profile API erişimi henüz onaylanmadı. "
                                "Yanıt kuyruğa kaydedildi; canlı mod (GBP_LIVE=true) "
                                "aktifleşince otomatik yayınlanacak.")}
        review = await db.reviews.find_one({"id": item.get("review_id")}, {"_id": 0}) or item
        res = await gbp_publish_reply(db, review, item.get("response_text") or item.get("reply_text") or "")
        await db.gbp_publish_queue.update_one({"id": queue_id}, {"$set": {"status": "PUBLISHED", "published_at": datetime.now(timezone.utc).isoformat(),
                                                                          "google_name": res["google_name"]}})
        return {"mode": "live", "status": "PUBLISHED", **res}

    @router.delete("/gbp/queue/{queue_id}")
    async def remove(queue_id: str,
                     _: dict = Depends(require_roles("admin", "manager"))):
        res = await db.gbp_publish_queue.update_one(
            {"id": queue_id},
            {"$set": {"status": "CANCELLED",
                      "cancelled_at": datetime.now(timezone.utc).isoformat()}})
        if not res.matched_count:
            raise HTTPException(404, "Kayıt bulunamadı")
        return {"ok": True}

    return router
