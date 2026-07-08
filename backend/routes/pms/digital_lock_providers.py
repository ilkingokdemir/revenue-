"""
Digital Lock Provider Adapters (iter 373) — Assa Abloy Visionline, Salto SVN
============================================================================
Provider adapters for major hospitality electronic lock systems.

Currently MOCKED (no real vendor SDK). Ready to swap:
  - Assa Abloy VingCard → Visionline SDK / Mobile Access API
  - Salto Systems       → SVN Data-on-Card / Salto KS Mobile Guest Key API
  - dormakaba TouchLock (future)
  - Onity DirectKey     (future)

Endpoints
---------
  GET    /api/lock-providers                     — list supported providers
  POST   /api/lock-providers/provision/{key_id}   — push mobile key to lock system
  POST   /api/lock-providers/revoke/{key_id}      — revoke on lock system
  GET    /api/lock-providers/status/{key_id}      — provisioning status log

Env vars (production):
  ASSA_ABLOY_API_URL, ASSA_ABLOY_API_KEY, ASSA_ABLOY_CLIENT_ID
  SALTO_KS_API_URL,   SALTO_KS_API_KEY,   SALTO_KS_SITE_ID
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional, Dict, Any
import logging
import os
import random
import uuid

try:
    import httpx
except Exception:
    httpx = None

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)


# ═══════════ SUPPORTED PROVIDERS ═══════════
PROVIDERS: Dict[str, Dict[str, Any]] = {
    "assa_abloy": {
        "label":        "Assa Abloy VingCard (Visionline)",
        "brand_color":  "#e30613",
        "protocol":     "BLE + RFID (Mobile Access)",
        "prod_api_url": "https://api.assaabloyhospitality.com/v2",
        "api_key_env":  "ASSA_ABLOY_API_KEY",
        "url_env":      "ASSA_ABLOY_API_URL",
        "client_env":   "ASSA_ABLOY_CLIENT_ID",
    },
    "salto_ks": {
        "label":        "Salto KS (Cloud-connected)",
        "brand_color":  "#000000",
        "protocol":     "BLE (Mobile Guest Key)",
        "prod_api_url": "https://api.saltoks.com/v1.1",
        "api_key_env":  "SALTO_KS_API_KEY",
        "url_env":      "SALTO_KS_API_URL",
        "client_env":   "SALTO_KS_SITE_ID",
    },
    "dormakaba": {
        "label":        "dormakaba Ambiance / TouchLock",
        "brand_color":  "#0068b3",
        "protocol":     "BLE + NFC",
        "prod_api_url": "https://api.dormakaba.com/hospitality/v1",
        "api_key_env":  "DORMAKABA_API_KEY",
        "url_env":      "DORMAKABA_API_URL",
        "client_env":   "DORMAKABA_PROP_ID",
    },
    "onity": {
        "label":        "Onity DirectKey",
        "brand_color":  "#0d3d68",
        "protocol":     "BLE",
        "prod_api_url": "https://api.onity.com/directkey/v1",
        "api_key_env":  "ONITY_API_KEY",
        "url_env":      "ONITY_API_URL",
        "client_env":   "ONITY_SITE_ID",
    },
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _provider_live(pkey: str) -> bool:
    cfg = PROVIDERS.get(pkey, {})
    return bool(os.environ.get(cfg.get("api_key_env", "")) and
                 os.environ.get(cfg.get("url_env", "")))


async def _provision(pkey: str, key_doc: dict) -> Dict[str, Any]:
    """Push a mobile key to the lock system. Falls back to mock if creds missing."""
    if pkey not in PROVIDERS:
        return {"status": "error", "note": f"Bilinmeyen provider: {pkey}"}
    cfg = PROVIDERS[pkey]
    live = _provider_live(pkey)
    if not live or not httpx:
        # MOCK: return a deterministic vendor_key_id
        vendor_id = f"{pkey.upper()[:3]}-{random.randint(10_000_000, 99_999_999)}"
        return {
            "status":       "mocked_provisioned",
            "vendor_key_id": vendor_id,
            "at":            _now(),
            "note":          f"{cfg['label']} SDK entegre değil — env: {cfg['api_key_env']}",
        }
    # PROD path — placeholder, must be validated per vendor
    url = os.environ.get(cfg["url_env"])
    key = os.environ.get(cfg["api_key_env"])
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            r = await client.post(
                f"{url}/mobile-keys",
                headers={"Authorization": f"Bearer {key}",
                          "X-Client-Id": os.environ.get(cfg["client_env"], "")},
                json={
                    "guest_name":  key_doc.get("guest_name"),
                    "room":        key_doc.get("room_number"),
                    "expires_at":  key_doc.get("expires_at"),
                    "booking_id":  key_doc.get("booking_id"),
                    "hb_key_id":   key_doc.get("id"),
                },
            )
        if r.status_code < 300:
            data = r.json() if r.text else {}
            return {"status": "provisioned",
                     "vendor_key_id": data.get("id") or data.get("key_id"),
                     "at": _now()}
        return {"status": "error",
                 "note": f"HTTP {r.status_code}: {r.text[:200]}"}
    except Exception as e:
        return {"status": "error", "note": str(e)[:200]}


async def _revoke(pkey: str, vendor_key_id: str) -> Dict[str, Any]:
    if pkey not in PROVIDERS:
        return {"status": "error", "note": f"Bilinmeyen provider: {pkey}"}
    cfg = PROVIDERS[pkey]
    if not _provider_live(pkey) or not httpx:
        return {"status": "mocked_revoked", "at": _now(),
                 "note": f"{cfg['label']} MOCK revoke"}
    url = os.environ.get(cfg["url_env"])
    key = os.environ.get(cfg["api_key_env"])
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            r = await client.delete(
                f"{url}/mobile-keys/{vendor_key_id}",
                headers={"Authorization": f"Bearer {key}"},
            )
        if r.status_code < 300:
            return {"status": "revoked", "at": _now()}
        return {"status": "error",
                 "note": f"HTTP {r.status_code}: {r.text[:200]}"}
    except Exception as e:
        return {"status": "error", "note": str(e)[:200]}


# ═══════════ MODELS ═══════════
class ProvisionBody(BaseModel):
    provider:    str


# ═══════════ ROUTER ═══════════
def create_lock_providers_router(db, require_roles):
    router = APIRouter(prefix="/lock-providers", tags=["digital-lock-providers"])

    @router.get("")
    async def list_providers():
        return [
            {
                "key":         k,
                "label":       v["label"],
                "brand_color": v["brand_color"],
                "protocol":    v["protocol"],
                "live":        _provider_live(k),
                "required_env": [v["api_key_env"], v["url_env"], v["client_env"]],
            } for k, v in PROVIDERS.items()
        ]

    @router.post("/provision/{key_id}")
    async def provision_key(key_id: str, body: ProvisionBody,
                              current_user: dict = Depends(require_roles(
                                  "admin", "manager", "receptionist"))):
        key = await db.digital_keys.find_one({"id": key_id}, {"_id": 0})
        if not key:
            raise HTTPException(404, "Anahtar bulunamadı")
        if body.provider not in PROVIDERS:
            raise HTTPException(400, f"Bilinmeyen provider: {body.provider}")

        result = await _provision(body.provider, key)
        provision_log = {
            "id":         str(uuid.uuid4()),
            "key_id":     key_id,
            "provider":   body.provider,
            "action":     "provision",
            "result":     result,
            "actor":      current_user.get("email"),
            "at":         _now(),
        }
        await db.lock_provider_events.insert_one(provision_log)

        # Attach vendor_key_id to the key doc if success
        if result.get("vendor_key_id"):
            await db.digital_keys.update_one(
                {"id": key_id},
                {"$set": {"vendor_provider":   body.provider,
                           "vendor_key_id":     result["vendor_key_id"],
                           "vendor_provisioned_at": _now()}},
            )
        return {"ok": True, "result": result,
                 "key_id": key_id, "provider": body.provider}

    @router.post("/revoke/{key_id}")
    async def revoke_key(key_id: str,
                           current_user: dict = Depends(require_roles(
                               "admin", "manager", "receptionist"))):
        key = await db.digital_keys.find_one({"id": key_id}, {"_id": 0})
        if not key:
            raise HTTPException(404, "Anahtar bulunamadı")
        pkey = key.get("vendor_provider")
        vid = key.get("vendor_key_id")
        if not pkey or not vid:
            return {"ok": False, "reason": "not_provisioned"}

        result = await _revoke(pkey, vid)
        await db.lock_provider_events.insert_one({
            "id":         str(uuid.uuid4()),
            "key_id":     key_id,
            "provider":   pkey,
            "action":     "revoke",
            "result":     result,
            "actor":      current_user.get("email"),
            "at":         _now(),
        })
        if result.get("status") in ("revoked", "mocked_revoked"):
            await db.digital_keys.update_one(
                {"id": key_id},
                {"$set": {"vendor_revoked_at": _now()}},
            )
        return {"ok": True, "result": result}

    @router.get("/status/{key_id}")
    async def key_status(key_id: str,
                           _: dict = Depends(require_roles(
                               "admin", "manager", "receptionist"))):
        key = await db.digital_keys.find_one({"id": key_id}, {"_id": 0, "token": 0})
        if not key:
            raise HTTPException(404, "Anahtar bulunamadı")
        events = await db.lock_provider_events.find(
            {"key_id": key_id}, {"_id": 0}
        ).sort("at", -1).to_list(30)
        return {"key": key, "events": events}

    return router
