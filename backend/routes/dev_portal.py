"""
Public Developer Portal (Mews Marketplace parity v2).

Provides external developers with:
  - OAuth-app registration (client_id + client_secret)
  - Scoped API keys (read:bookings, write:bookings, etc.)
  - Sandbox environment toggle
  - API usage / rate-limit stats per app
  - Revenue share program enrollment (10% of subscription revenue)

This is DIFFERENT from the internal `partner_webhooks` module (which is for
hotels to set up their own webhooks). This is for THIRD-PARTY DEVELOPERS who
want to build apps that integrate with HotelBox.

Endpoints
---------
Public (dev portal landing — no auth):
  GET  /api/dev-portal/info                  — Portal metadata, available scopes
  POST /api/dev-portal/register              — Self-register developer account (no email verify yet)
  POST /api/dev-portal/login                 — Returns dev token

Authenticated developer (Bearer dev token):
  GET  /api/dev-portal/me
  POST /api/dev-portal/apps                  — Create OAuth app
  GET  /api/dev-portal/apps
  GET  /api/dev-portal/apps/{app_id}
  POST /api/dev-portal/apps/{app_id}/keys    — Generate API key (returns secret ONCE)
  GET  /api/dev-portal/apps/{app_id}/keys
  DELETE /api/dev-portal/apps/{app_id}/keys/{key_id}
  GET  /api/dev-portal/apps/{app_id}/stats   — Usage statistics
  POST /api/dev-portal/apps/{app_id}/revenue-share/opt-in
  GET  /api/dev-portal/apps/{app_id}/revenue-share/earnings

Admin:
  GET  /api/dev-portal/admin/apps            — List all apps (admin oversight)
  POST /api/dev-portal/admin/apps/{id}/approve
  POST /api/dev-portal/admin/apps/{id}/suspend
"""
from datetime import datetime, timezone, timedelta
import os
import secrets
import uuid
import bcrypt
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request

JWT_ALGORITHM = "HS256"

AVAILABLE_SCOPES = [
    {"id": "read:bookings", "label": "Rezervasyonları oku"},
    {"id": "write:bookings", "label": "Rezervasyon oluştur/güncelle"},
    {"id": "read:guests", "label": "Misafir profillerini oku"},
    {"id": "read:rates", "label": "Tarifeleri oku"},
    {"id": "write:rates", "label": "Tarifeleri güncelle"},
    {"id": "read:availability", "label": "Müsaitlik oku"},
    {"id": "read:reviews", "label": "Yorumları oku"},
    {"id": "write:reviews", "label": "Yorum yanıtla"},
    {"id": "read:reports", "label": "Raporları oku"},
    {"id": "webhooks:subscribe", "label": "Webhook'lara abone ol"},
]


def _jwt_secret() -> str:
    return os.environ["JWT_SECRET"]


def _hash(p: str) -> str:
    return bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()


def _verify(p: str, h: str) -> bool:
    try:
        return bcrypt.checkpw(p.encode(), h.encode())
    except Exception:
        return False


def _create_dev_token(dev_id: str) -> str:
    payload = {
        "sub": dev_id,
        "type": "developer_access",
        "exp": datetime.now(timezone.utc) + timedelta(days=7),
    }
    return jwt.encode(payload, _jwt_secret(), algorithm=JWT_ALGORITHM)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_dev_portal_router(db, require_roles):
    router = APIRouter()

    async def get_current_dev(request: Request) -> dict:
        auth = request.headers.get("Authorization", "")
        token = auth[7:] if auth.startswith("Bearer ") else ""
        if not token:
            raise HTTPException(401, "Not authenticated")
        try:
            payload = jwt.decode(token, _jwt_secret(), algorithms=[JWT_ALGORITHM])
            if payload.get("type") != "developer_access":
                raise HTTPException(401, "Invalid token type")
            dev = await db.developers.find_one({"id": payload["sub"]},
                                                {"_id": 0, "password_hash": 0})
            if not dev:
                raise HTTPException(401, "Developer not found")
            return dev
        except jwt.ExpiredSignatureError:
            raise HTTPException(401, "Token expired")
        except jwt.InvalidTokenError:
            raise HTTPException(401, "Invalid token")

    # =========== Public ===========
    @router.get("/dev-portal/info")
    async def info():
        return {
            "platform": "HotelBox Developer Portal",
            "version": "1.0",
            "base_url": os.environ.get("PUBLIC_API_BASE", "/api"),
            "auth_method": "Bearer token via OAuth2 client_credentials grant (or API key)",
            "rate_limits": {
                "default": "10 req/sec per app",
                "burst": "100 req/min",
            },
            "scopes": AVAILABLE_SCOPES,
            "revenue_share_program": {
                "default_share_percent": 10,
                "min_subscription_revenue": 100,
                "payout_currency": "USD",
                "payout_method": "wire/bank transfer",
            },
            "sandbox": {
                "base_url": os.environ.get("PUBLIC_API_BASE", "/api") + "/sandbox",
                "free": True,
                "note": "Sandbox uses isolated test data, never affects production.",
            },
        }

    @router.post("/dev-portal/register")
    async def register(body: dict):
        email = (body.get("email") or "").strip().lower()
        password = body.get("password") or ""
        name = (body.get("name") or "").strip()
        company = (body.get("company") or "").strip()
        if not email or not password or len(password) < 8:
            raise HTTPException(400, "email + password (8+ chars) required")
        ex = await db.developers.find_one({"email": email}, {"_id": 0, "id": 1})
        if ex:
            raise HTTPException(409, "Email already registered")
        dev = {
            "id": str(uuid.uuid4()),
            "email": email,
            "password_hash": _hash(password),
            "name": name,
            "company": company,
            "is_active": True,
            "is_verified": False,
            "created_at": _now_iso(),
        }
        await db.developers.insert_one(dev)
        token = _create_dev_token(dev["id"])
        return {
            "access_token": token,
            "token_type": "bearer",
            "developer": {"id": dev["id"], "email": email, "name": name},
        }

    @router.post("/dev-portal/login")
    async def login(body: dict):
        email = (body.get("email") or "").strip().lower()
        password = body.get("password") or ""
        dev = await db.developers.find_one({"email": email}, {"_id": 0})
        if not dev or not _verify(password, dev.get("password_hash", "")):
            raise HTTPException(401, "Invalid credentials")
        if not dev.get("is_active", True):
            raise HTTPException(403, "Account disabled")
        token = _create_dev_token(dev["id"])
        await db.developers.update_one(
            {"id": dev["id"]},
            {"$set": {"last_login_at": _now_iso()}},
        )
        return {
            "access_token": token,
            "token_type": "bearer",
            "developer": {"id": dev["id"], "email": email,
                          "name": dev.get("name"), "company": dev.get("company")},
        }

    @router.get("/dev-portal/me")
    async def me(dev: dict = Depends(get_current_dev)):
        return dev

    # =========== Apps ===========
    @router.post("/dev-portal/apps")
    async def create_app(body: dict, dev: dict = Depends(get_current_dev)):
        name = (body.get("name") or "").strip()
        if not name:
            raise HTTPException(400, "name required")
        client_id = "hb_" + secrets.token_urlsafe(16)
        client_secret_plain = secrets.token_urlsafe(32)
        app = {
            "id": str(uuid.uuid4()),
            "developer_id": dev["id"],
            "name": name,
            "description": body.get("description", ""),
            "category": body.get("category", "general"),
            "redirect_uris": body.get("redirect_uris", []),
            "scopes": body.get("scopes", []),
            "client_id": client_id,
            "client_secret_hash": _hash(client_secret_plain),
            "is_sandbox": body.get("is_sandbox", True),
            "status": "pending_review",
            "created_at": _now_iso(),
            "revenue_share_enrolled": False,
        }
        await db.developer_apps.insert_one(app)
        out = {**app}
        out.pop("_id", None)
        out.pop("client_secret_hash", None)
        out["client_secret"] = client_secret_plain  # one-time-only return
        out["note"] = ("Bu client_secret bir daha gösterilmeyecek. "
                       "Hemen güvenli bir yerde saklayın.")
        return out

    @router.get("/dev-portal/apps")
    async def list_apps(dev: dict = Depends(get_current_dev)):
        items = await db.developer_apps.find(
            {"developer_id": dev["id"]},
            {"_id": 0, "client_secret_hash": 0}
        ).sort("created_at", -1).to_list(100)
        return {"items": items, "count": len(items)}

    @router.get("/dev-portal/apps/{app_id}")
    async def get_app(app_id: str, dev: dict = Depends(get_current_dev)):
        app = await db.developer_apps.find_one(
            {"id": app_id, "developer_id": dev["id"]},
            {"_id": 0, "client_secret_hash": 0}
        )
        if not app:
            raise HTTPException(404, "App not found")
        return app

    # =========== API Keys ===========
    @router.post("/dev-portal/apps/{app_id}/keys")
    async def create_key(app_id: str, body: dict = None,
                         dev: dict = Depends(get_current_dev)):
        body = body or {}
        app = await db.developer_apps.find_one(
            {"id": app_id, "developer_id": dev["id"]}, {"_id": 0, "id": 1}
        )
        if not app:
            raise HTTPException(404, "App not found")
        key_plain = "hbk_" + secrets.token_urlsafe(28)
        prefix = key_plain[:10]
        rec = {
            "id": str(uuid.uuid4()),
            "app_id": app_id,
            "developer_id": dev["id"],
            "label": body.get("label", "Default key"),
            "prefix": prefix,
            "key_hash": _hash(key_plain),
            "scopes": body.get("scopes", []),
            "is_active": True,
            "created_at": _now_iso(),
            "last_used_at": None,
            "call_count": 0,
        }
        await db.developer_api_keys.insert_one(rec)
        return {
            "id": rec["id"],
            "label": rec["label"],
            "prefix": prefix,
            "key": key_plain,
            "scopes": rec["scopes"],
            "created_at": rec["created_at"],
            "note": "Bu anahtar bir daha gösterilmeyecek. Hemen güvenli yere kopyalayın.",
        }

    @router.get("/dev-portal/apps/{app_id}/keys")
    async def list_keys(app_id: str, dev: dict = Depends(get_current_dev)):
        items = await db.developer_api_keys.find(
            {"app_id": app_id, "developer_id": dev["id"]},
            {"_id": 0, "key_hash": 0}
        ).sort("created_at", -1).to_list(50)
        return {"items": items, "count": len(items)}

    @router.delete("/dev-portal/apps/{app_id}/keys/{key_id}")
    async def revoke_key(app_id: str, key_id: str,
                         dev: dict = Depends(get_current_dev)):
        r = await db.developer_api_keys.update_one(
            {"id": key_id, "app_id": app_id, "developer_id": dev["id"]},
            {"$set": {"is_active": False, "revoked_at": _now_iso()}}
        )
        if not r.matched_count:
            raise HTTPException(404, "Key not found")
        return {"ok": True}

    @router.get("/dev-portal/apps/{app_id}/stats")
    async def app_stats(app_id: str, dev: dict = Depends(get_current_dev)):
        keys = await db.developer_api_keys.find(
            {"app_id": app_id, "developer_id": dev["id"]},
            {"_id": 0, "id": 1, "label": 1, "call_count": 1, "last_used_at": 1}
        ).to_list(50)
        total = sum(int(k.get("call_count") or 0) for k in keys)
        return {
            "app_id": app_id,
            "total_calls": total,
            "keys": keys,
            "rate_limit": "10 req/sec",
        }

    # =========== Revenue share ===========
    @router.post("/dev-portal/apps/{app_id}/revenue-share/opt-in")
    async def opt_in_rev_share(app_id: str, body: dict = None,
                                dev: dict = Depends(get_current_dev)):
        body = body or {}
        r = await db.developer_apps.update_one(
            {"id": app_id, "developer_id": dev["id"]},
            {"$set": {
                "revenue_share_enrolled": True,
                "revenue_share_enrolled_at": _now_iso(),
                "revenue_share_percent": float(body.get("share_percent", 10)),
                "payout_email": body.get("payout_email", dev["email"]),
            }}
        )
        if not r.matched_count:
            raise HTTPException(404, "App not found")
        return {"ok": True, "share_percent": float(body.get("share_percent", 10))}

    @router.get("/dev-portal/apps/{app_id}/revenue-share/earnings")
    async def rev_share_earnings(app_id: str, dev: dict = Depends(get_current_dev)):
        # Aggregate from `developer_revenue_ledger` (mock — empty initially)
        items = await db.developer_revenue_ledger.find(
            {"app_id": app_id, "developer_id": dev["id"]},
            {"_id": 0}
        ).sort("month", -1).to_list(24)
        total = round(sum(float(i.get("payout") or 0) for i in items), 2)
        return {"app_id": app_id, "total_lifetime_payout": total,
                "monthly": items, "count": len(items)}

    # =========== Admin oversight ===========
    @router.get("/dev-portal/admin/apps")
    async def admin_list_apps(_: dict = Depends(require_roles("admin"))):
        items = await db.developer_apps.find(
            {}, {"_id": 0, "client_secret_hash": 0}
        ).sort("created_at", -1).to_list(500)
        # Enrich with developer email
        dev_ids = list({a["developer_id"] for a in items})
        devs = await db.developers.find(
            {"id": {"$in": dev_ids}}, {"_id": 0, "id": 1, "email": 1, "company": 1}
        ).to_list(500) if dev_ids else []
        dm = {d["id"]: d for d in devs}
        for a in items:
            d = dm.get(a["developer_id"], {})
            a["developer_email"] = d.get("email")
            a["developer_company"] = d.get("company")
        return {"items": items, "count": len(items)}

    @router.post("/dev-portal/admin/apps/{app_id}/approve")
    async def admin_approve(app_id: str,
                            current_user: dict = Depends(require_roles("admin"))):
        r = await db.developer_apps.update_one(
            {"id": app_id},
            {"$set": {"status": "approved",
                      "approved_at": _now_iso(),
                      "approved_by": current_user.get("name", "")}}
        )
        if not r.matched_count:
            raise HTTPException(404, "App not found")
        return {"ok": True}

    @router.post("/dev-portal/admin/apps/{app_id}/suspend")
    async def admin_suspend(app_id: str, body: dict = None,
                            current_user: dict = Depends(require_roles("admin"))):
        body = body or {}
        r = await db.developer_apps.update_one(
            {"id": app_id},
            {"$set": {"status": "suspended",
                      "suspended_at": _now_iso(),
                      "suspended_by": current_user.get("name", ""),
                      "suspend_reason": body.get("reason", "")}}
        )
        if not r.matched_count:
            raise HTTPException(404, "App not found")
        return {"ok": True}

    return router
