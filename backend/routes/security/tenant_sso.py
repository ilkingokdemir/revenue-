"""
Tenant (organizasyon) katmanı + tesise özel roller + OIDC SSO (Google Workspace / Microsoft Entra).
ENV: GOOGLE_SSO_CLIENT_ID/SECRET, MS_SSO_CLIENT_ID/SECRET, MS_SSO_TENANT_ID, PUBLIC_BASE_URL.
Kimlik: (provider, sub/oid) → users.sso_identities; org eşleşmesi doğrulanmış hd/tid veya allowed_domains ile.
"""
import base64
import hashlib
import logging
import os
import secrets
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional
from urllib.parse import urlencode

import httpx
import jwt
from jwt import PyJWKClient
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse

logger = logging.getLogger(__name__)
ROLE_RANK = {"admin": 5, "manager": 4, "receptionist": 3, "housekeeper": 2, "staff": 1, "viewer": 0}


def _now(): return datetime.now(timezone.utc)


def _providers():
    ms_t = os.environ.get("MS_SSO_TENANT_ID", "")
    return {
        "google": {"client_id": os.environ.get("GOOGLE_SSO_CLIENT_ID", ""), "secret": os.environ.get("GOOGLE_SSO_CLIENT_SECRET", ""),
                   "authorize": "https://accounts.google.com/o/oauth2/v2/auth", "token": "https://oauth2.googleapis.com/token",
                   "issuer": "https://accounts.google.com", "jwks": "https://www.googleapis.com/oauth2/v3/certs", "scope": "openid email profile"},
        "microsoft": {"client_id": os.environ.get("MS_SSO_CLIENT_ID", ""), "secret": os.environ.get("MS_SSO_CLIENT_SECRET", ""),
                      "authorize": f"https://login.microsoftonline.com/{ms_t or 'common'}/oauth2/v2.0/authorize",
                      "token": f"https://login.microsoftonline.com/{ms_t or 'common'}/oauth2/v2.0/token",
                      "issuer": f"https://login.microsoftonline.com/{ms_t}/v2.0", "jwks": f"https://login.microsoftonline.com/{ms_t or 'common'}/discovery/v2.0/keys",
                      "scope": "openid profile email"},
    }


def _cb(provider): return f"{os.environ.get('PUBLIC_BASE_URL', '').rstrip('/')}/api/auth/sso/{provider}/callback"


def effective_role(user: dict, property_id: Optional[str]) -> str:
    """Tesise özel rol varsa onu, yoksa genel rolü döndürür."""
    pr = (user or {}).get("property_roles") or {}
    if property_id and property_id in pr:
        return pr[property_id]
    return (user or {}).get("role", "viewer")


def create_tenant_sso_router(db, require_roles, create_access_token, create_refresh_token):
    router = APIRouter()

    # ---------------- Organizations ----------------
    @router.get("/orgs")
    async def list_orgs(_: dict = Depends(require_roles("admin"))):
        orgs = await db.organizations.find({}, {"_id": 0}).to_list(200)
        for o in orgs:
            o["user_count"] = await db.users.count_documents({"org_id": o["id"]})
            o["property_count"] = await db.properties.count_documents({"org_id": o["id"]})
        return {"items": orgs}

    @router.post("/orgs")
    async def create_org(body: dict, current_user: dict = Depends(require_roles("admin"))):
        name = str(body.get("name") or "").strip()
        if not name:
            raise HTTPException(400, "name gerekli")
        org = {"id": str(uuid.uuid4()), "name": name, "slug": body.get("slug") or name.lower().replace(" ", "-"),
               "allowed_domains": [d.lower().strip() for d in (body.get("allowed_domains") or []) if d],
               "sso": {"provider": body.get("sso_provider") or "", "google_hd": body.get("google_hd") or "", "ms_tid": body.get("ms_tid") or "",
                       "default_role": body.get("default_role") or "receptionist", "auto_provision": bool(body.get("auto_provision", True))},
               "created_by": current_user.get("email", ""), "created_at": _now().isoformat()}
        await db.organizations.insert_one(dict(org))
        return org

    @router.put("/orgs/{org_id}")
    async def update_org(org_id: str, body: dict, _: dict = Depends(require_roles("admin"))):
        upd = {}
        for k in ("name", "allowed_domains"):
            if k in body: upd[k] = body[k]
        for k in ("provider", "google_hd", "ms_tid", "default_role", "auto_provision"):
            if k in body: upd[f"sso.{k}"] = body[k]
        r = await db.organizations.update_one({"id": org_id}, {"$set": upd})
        if not r.matched_count: raise HTTPException(404)
        return await db.organizations.find_one({"id": org_id}, {"_id": 0})

    @router.post("/orgs/{org_id}/assign")
    async def assign(org_id: str, body: dict, _: dict = Depends(require_roles("admin"))):
        """Tesis ve/veya kullanıcıları organizasyona bağla."""
        if not await db.organizations.find_one({"id": org_id}, {"_id": 1}): raise HTTPException(404)
        p = await db.properties.update_many({"id": {"$in": body.get("property_ids") or []}}, {"$set": {"org_id": org_id}})
        from bson import ObjectId
        ids = body.get("user_ids") or []
        u = await db.users.update_many({"$or": [{"id": {"$in": ids}}, {"_id": {"$in": [ObjectId(x) for x in ids if ObjectId.is_valid(x)]}}]}, {"$set": {"org_id": org_id}})
        return {"ok": True, "properties": p.modified_count, "users": u.modified_count}

    @router.put("/orgs/users/{user_id}/property-roles")
    async def set_property_roles(user_id: str, body: dict, actor: dict = Depends(require_roles("admin"))):
        roles = {str(k): v for k, v in (body.get("property_roles") or {}).items() if v in ROLE_RANK}
        from bson import ObjectId
        q = {"$or": [{"id": user_id}] + ([{"_id": ObjectId(user_id)}] if ObjectId.is_valid(user_id) else [])}
        before = await db.users.find_one(q, {"_id": 1, "id": 1, "name": 1, "email": 1, "property_roles": 1})
        r = await db.users.update_one(q, {"$set": {"property_roles": roles}})
        if not r.matched_count: raise HTTPException(404, "User not found")
        from routes.security.permission_matrix import log_perm_change
        await log_perm_change(db, actor, before or {}, "property_roles", (before or {}).get("property_roles") or {}, roles)
        return {"ok": True, "property_roles": roles}

    # ---------------- SSO ----------------
    @router.get("/auth/sso/providers")
    async def sso_providers():
        p = _providers()
        return {k: {"configured": bool(v["client_id"] and v["secret"]), "redirect_uri": _cb(k)} for k, v in p.items()}

    @router.get("/auth/sso/{provider}/start")
    async def sso_start(provider: str, org: str = ""):
        p = _providers().get(provider)
        if not p: raise HTTPException(404, "Unknown provider")
        if not (p["client_id"] and p["secret"]):
            env = "GOOGLE_SSO_CLIENT_ID/SECRET" if provider == "google" else "MS_SSO_CLIENT_ID/SECRET/TENANT_ID"
            raise HTTPException(400, f"{env} .env'de yok. Redirect URI: {_cb(provider)}")
        state, nonce = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode()
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        await db.oauth_states.insert_one({"id": state, "provider": f"sso:{provider}", "nonce": nonce, "verifier": verifier, "org": org, "created_at": _now().isoformat()})
        params = {"client_id": p["client_id"], "response_type": "code", "redirect_uri": _cb(provider), "scope": p["scope"], "state": state,
                  "nonce": nonce, "code_challenge": challenge, "code_challenge_method": "S256", "response_mode": "query"}
        if provider == "google" and org:
            o = await db.organizations.find_one({"slug": org}, {"_id": 0, "sso.google_hd": 1})
            if o and (o.get("sso") or {}).get("google_hd"): params["hd"] = o["sso"]["google_hd"]
        return RedirectResponse(p["authorize"] + "?" + urlencode(params))

    async def _match_org(provider: str, claims: dict) -> Optional[dict]:
        email = (claims.get("email") or claims.get("preferred_username") or "").lower()
        domain = email.split("@")[-1] if "@" in email else ""
        q = {"$or": [{"allowed_domains": domain}] if domain else []}
        if provider == "google" and claims.get("hd"): q["$or"].append({"sso.google_hd": claims["hd"]})
        if provider == "microsoft" and claims.get("tid"): q["$or"].append({"sso.ms_tid": claims["tid"]})
        return await db.organizations.find_one(q, {"_id": 0}) if q["$or"] else None

    @router.get("/auth/sso/{provider}/callback")
    async def sso_callback(provider: str, code: str = "", state: str = "", error: str = ""):
        front = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")
        p = _providers().get(provider)
        if not p or error or not code or not state:
            return RedirectResponse(f"{front}/login?sso=error&reason={error or 'missing_code'}")
        st = await db.oauth_states.find_one_and_delete({"id": state, "provider": f"sso:{provider}"})
        if not st:
            return RedirectResponse(f"{front}/login?sso=error&reason=invalid_state")
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.post(p["token"], data={"grant_type": "authorization_code", "code": code, "redirect_uri": _cb(provider),
                                                "client_id": p["client_id"], "client_secret": p["secret"], "code_verifier": st["verifier"]})
        if r.status_code != 200:
            return RedirectResponse(f"{front}/login?sso=error&reason=token_exchange")
        id_token = r.json().get("id_token", "")
        try:
            key = PyJWKClient(p["jwks"]).get_signing_key_from_jwt(id_token).key
            claims = jwt.decode(id_token, key, algorithms=["RS256"], audience=p["client_id"],
                                issuer=p["issuer"] if (provider == "google" or os.environ.get("MS_SSO_TENANT_ID")) else None,
                                options={"require": ["exp", "iat", "iss", "aud", "sub"], "verify_iss": bool(provider == "google" or os.environ.get("MS_SSO_TENANT_ID"))})
            if claims.get("nonce") != st["nonce"]:
                raise ValueError("nonce")
        except Exception as e:
            logger.warning(f"sso id_token invalid: {e}")
            return RedirectResponse(f"{front}/login?sso=error&reason=invalid_token")
        subject = claims["sub"] if provider == "google" else claims.get("oid", claims["sub"])
        email = (claims.get("email") or claims.get("preferred_username") or "").lower()
        user = await db.users.find_one({"sso_identities": {"$elemMatch": {"provider": provider, "subject": subject}}}, {"_id": 0}) \
            or (await db.users.find_one({"email": email}, {"_id": 0}) if email else None)
        org = await _match_org(provider, claims)
        if not user:
            if not (org and (org.get("sso") or {}).get("auto_provision", True)):
                return RedirectResponse(f"{front}/login?sso=error&reason=no_org_for_domain")
            user = {"id": str(uuid.uuid4()), "email": email, "name": claims.get("name") or email, "role": (org.get("sso") or {}).get("default_role", "receptionist"),
                    "org_id": org["id"], "is_active": True, "is_activated": True, "auth_provider": provider, "created_at": _now().isoformat(),
                    "sso_identities": [{"provider": provider, "subject": subject, "tid": claims.get("tid"), "hd": claims.get("hd")}]}
            await db.users.insert_one(dict(user))
        else:
            if user.get("is_active") is False:
                return RedirectResponse(f"{front}/login?sso=error&reason=inactive")
            upd = {"last_login": _now().isoformat()}
            if org and not user.get("org_id"): upd["org_id"] = org["id"]
            await db.users.update_one({"id": user["id"]}, {"$set": upd, "$addToSet": {"sso_identities": {"provider": provider, "subject": subject}}})
        await db.sso_logins.insert_one({"id": str(uuid.uuid4()), "user_id": user["id"], "email": email, "provider": provider, "org_id": user.get("org_id"), "at": _now().isoformat()})
        access, refresh = create_access_token(user["id"], email), create_refresh_token(user["id"])
        resp = RedirectResponse(f"{front}/?sso=ok")
        resp.set_cookie("access_token", access, httponly=True, secure=False, samesite="lax", max_age=86400, path="/")
        resp.set_cookie("refresh_token", refresh, httponly=True, secure=False, samesite="lax", max_age=604800, path="/")
        return resp

    return router
