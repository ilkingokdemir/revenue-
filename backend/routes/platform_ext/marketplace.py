"""
Marketplace v1 — Integration Hub (Mews-parity Batch 3, iter 358).

Provides a curated catalog of 3rd-party integrations that the operator can
"install" (link a config record for a property). This is the FE-facing hub
that gives the app the same "1000+ integration ecosystem" feel Mews sells
as one of its biggest USPs.

Endpoints (all admin/manager):
  GET  /api/marketplace/catalog                   — list all catalog apps
  GET  /api/marketplace/catalog/{app_id}          — detail
  GET  /api/marketplace/installed/{property_id}   — installed apps for a property
  POST /api/marketplace/install                   — {app_id, property_id, config}
  POST /api/marketplace/uninstall                 — {app_id, property_id}
  POST /api/marketplace/toggle                    — {app_id, property_id, enabled}

The catalog is a static in-code list for v1 (no DB dependency) so we can
iterate on wording/logos quickly. Installations persist in `marketplace_installed`.
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Curated catalog — 20 integrations grouped by category. Kept flat so FE can
# tab / filter easily. `status` maps to badge colour on the FE.
# ---------------------------------------------------------------------------
CATALOG = [
    # ── Distribution / OTAs ──────────────────────────────────────────────
    {"id": "booking-com",  "name": "Booking.com",  "category": "distribution",
     "logo": "🅱️", "provider": "Booking Holdings",
     "summary": "2-way channel: rates, inventory, reservations. XML push + ARI pull.",
     "status": "available", "requires_config": True,
     "config_hint": "Hotel ID + Extranet API key (Booking.com'dan alın).", "featured": True},
    {"id": "airbnb",       "name": "Airbnb",       "category": "distribution",
     "logo": "🅰️", "provider": "Airbnb Inc.",
     "summary": "iCal + Enhanced API. Rezervasyon, mesajlaşma, fiyat senkronizasyonu.",
     "status": "available", "requires_config": True,
     "config_hint": "iCal URL veya OAuth ile bağlanın.", "featured": True},
    {"id": "expedia",      "name": "Expedia · Hotels.com", "category": "distribution",
     "logo": "🅴", "provider": "Expedia Group",
     "summary": "PMS ↔ Expedia connect. ARI + Booking retrieval.",
     "status": "available", "requires_config": True, "config_hint": "EQC credentials."},
    {"id": "tripadvisor",  "name": "TripAdvisor",  "category": "distribution",
     "logo": "🦉", "provider": "Tripadvisor LLC",
     "summary": "Review sync + Instant Booking (metaviews).",
     "status": "coming_soon"},
    {"id": "google-hotels","name": "Google Hotels","category": "distribution",
     "logo": "🔎", "provider": "Google",
     "summary": "Free booking links + metasearch rate parity feed.",
     "status": "available", "requires_config": True, "config_hint": "Google Hotel Center hesabınızın Merchant ID'si."},

    # ── Payments ─────────────────────────────────────────────────────────
    {"id": "stripe",       "name": "Stripe",       "category": "payments",
     "logo": "💳", "provider": "Stripe Inc.",
     "summary": "Kredi kartı çekimi, iade, deposit + tokenized cards on file.",
     "status": "installed", "requires_config": True, "config_hint": "Emergent Test Key otomatik yüklü.", "featured": True},
    {"id": "paypal",       "name": "PayPal",       "category": "payments",
     "logo": "🅿️", "provider": "PayPal Holdings",
     "summary": "PayPal + Pay in 4 / BNPL akışları.",
     "status": "available", "requires_config": True, "config_hint": "Client ID + Secret."},
    {"id": "razorpay",     "name": "Razorpay (IN)","category": "payments",
     "logo": "₹", "provider": "Razorpay",
     "summary": "UPI, cards, netbanking (Hindistan pazarı).",
     "status": "available", "requires_config": True, "config_hint": "Key ID + Secret."},

    # ── Messaging ────────────────────────────────────────────────────────
    {"id": "whatsapp",     "name": "WhatsApp Business", "category": "messaging",
     "logo": "🟢", "provider": "Meta",
     "summary": "Otomatik guest mesajları + rezervasyon onayları.",
     "status": "available", "requires_config": True,
     "config_hint": "Phone number ID + Meta System User token.", "featured": True},
    {"id": "twilio-sms",   "name": "Twilio SMS",   "category": "messaging",
     "logo": "📱", "provider": "Twilio",
     "summary": "SMS ile OTP, check-in reminder, review request.",
     "status": "available", "requires_config": True, "config_hint": "Account SID + Auth token + sender number."},
    {"id": "telegram",     "name": "Telegram Bot", "category": "messaging",
     "logo": "✈️", "provider": "Telegram",
     "summary": "Staff internal alerts + guest support bot.",
     "status": "available", "requires_config": True, "config_hint": "Bot token (BotFather'dan alın)."},
    {"id": "resend",       "name": "Resend",       "category": "messaging",
     "logo": "📧", "provider": "Resend",
     "summary": "Modern email API — pre-arrival, post-stay, win-back kampanyaları.",
     "status": "available", "requires_config": True, "config_hint": "API key + verified domain."},
    {"id": "sendgrid",     "name": "SendGrid",     "category": "messaging",
     "logo": "✉️", "provider": "Twilio",
     "summary": "Twilio email — high-volume transactional + newsletters.",
     "status": "available", "requires_config": True, "config_hint": "API key."},

    # ── Analytics / Marketing ────────────────────────────────────────────
    {"id": "google-ads",   "name": "Google Ads",   "category": "marketing",
     "logo": "📊", "provider": "Google",
     "summary": "Booking outcome tracking, ROAS raporu, conversion feed.",
     "status": "coming_soon", "featured": True},
    {"id": "meta-ads",     "name": "Meta Ads",     "category": "marketing",
     "logo": "🅼", "provider": "Meta",
     "summary": "Facebook + Instagram conversion API + retargeting audiences.",
     "status": "coming_soon"},
    {"id": "mailchimp",    "name": "Mailchimp",    "category": "marketing",
     "logo": "🐵", "provider": "Intuit",
     "summary": "Guest segmentation + email marketing kampanyaları.",
     "status": "available", "requires_config": True, "config_hint": "API key."},

    # ── Accounting ────────────────────────────────────────────────────────
    {"id": "quickbooks",   "name": "QuickBooks",   "category": "accounting",
     "logo": "📘", "provider": "Intuit",
     "summary": "Günlük gelir/gider senkronizasyonu.",
     "status": "coming_soon"},
    {"id": "xero",         "name": "Xero",         "category": "accounting",
     "logo": "📗", "provider": "Xero Ltd.",
     "summary": "Multi-currency invoicing + reconciliation.",
     "status": "coming_soon"},

    # ── Voice / Kiosk ─────────────────────────────────────────────────────
    {"id": "elevenlabs",   "name": "ElevenLabs Voice", "category": "ai",
     "logo": "🎙️", "provider": "ElevenLabs",
     "summary": "Marka sesli otel AI (rezervasyon, concierge çağrı).",
     "status": "available", "requires_config": True, "config_hint": "API key + selected voice ID."},

    # ── Automation ────────────────────────────────────────────────────────
    {"id": "zapier",       "name": "Zapier",       "category": "automation",
     "logo": "⚡", "provider": "Zapier Inc.",
     "summary": "5000+ app'e bağlan (webhook trigger + custom actions).",
     "status": "coming_soon", "featured": True},
]

CATEGORIES = [
    {"id": "distribution", "label": "Kanal Yönetimi", "icon": "🌐"},
    {"id": "payments",     "label": "Ödeme",           "icon": "💳"},
    {"id": "messaging",    "label": "Mesajlaşma",      "icon": "💬"},
    {"id": "marketing",    "label": "Pazarlama",       "icon": "📈"},
    {"id": "accounting",   "label": "Muhasebe",        "icon": "📚"},
    {"id": "ai",           "label": "AI · Ses",        "icon": "🤖"},
    {"id": "automation",   "label": "Otomasyon",       "icon": "⚙️"},
]


def create_marketplace_router(db, require_roles):
    router = APIRouter(prefix="/marketplace", tags=["marketplace"])

    async def _installed_map(property_id: str) -> dict:
        rows = await db.marketplace_installed.find(
            {"property_id": property_id}, {"_id": 0}
        ).to_list(200)
        return {r["app_id"]: r for r in rows}

    @router.get("/catalog")
    async def catalog(category: Optional[str] = None, featured: Optional[bool] = None,
                       property_id: Optional[str] = None,
                       _: dict = Depends(require_roles("admin", "manager"))):
        items = list(CATALOG)
        if category:
            items = [x for x in items if x["category"] == category]
        if featured:
            items = [x for x in items if x.get("featured")]
        # Merge installation status if property_id given
        if property_id:
            inst = await _installed_map(property_id)
            for it in items:
                if it["id"] in inst:
                    it["status"] = "installed" if inst[it["id"]].get("enabled", True) else "disabled"
                    it["installed_at"] = inst[it["id"]].get("installed_at")
        return {
            "categories": CATEGORIES,
            "total": len(items),
            "featured_count": sum(1 for x in items if x.get("featured")),
            "installed_count": sum(1 for x in items if x.get("status") in ("installed", "disabled")),
            "items": items,
        }

    @router.get("/catalog/{app_id}")
    async def get_app(app_id: str,
                       property_id: Optional[str] = None,
                       _: dict = Depends(require_roles("admin", "manager"))):
        app = next((x for x in CATALOG if x["id"] == app_id), None)
        if not app:
            raise HTTPException(404, "App not found")
        app = dict(app)
        if property_id:
            inst = await db.marketplace_installed.find_one(
                {"app_id": app_id, "property_id": property_id}, {"_id": 0}
            )
            if inst:
                app["status"] = "installed" if inst.get("enabled", True) else "disabled"
                app["installed_at"] = inst.get("installed_at")
                app["config"] = inst.get("config") or {}
        return app

    @router.get("/installed/{property_id}")
    async def list_installed(property_id: str,
                              _: dict = Depends(require_roles("admin", "manager"))):
        rows = await db.marketplace_installed.find(
            {"property_id": property_id}, {"_id": 0}
        ).sort("installed_at", -1).to_list(200)
        # Enrich with catalog metadata
        by_id = {c["id"]: c for c in CATALOG}
        for r in rows:
            meta = by_id.get(r.get("app_id")) or {}
            r["name"] = meta.get("name", r.get("app_id"))
            r["category"] = meta.get("category")
            r["logo"] = meta.get("logo")
            r["provider"] = meta.get("provider")
        return {"total": len(rows), "items": rows}

    @router.post("/install")
    async def install_app(body: dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        app_id = body.get("app_id")
        property_id = body.get("property_id")
        if not app_id or not property_id:
            raise HTTPException(400, "app_id and property_id required")
        app = next((x for x in CATALOG if x["id"] == app_id), None)
        if not app:
            raise HTTPException(404, "App not found in catalog")
        if app.get("status") == "coming_soon":
            raise HTTPException(400, f"{app['name']} yakında — henüz kurulamıyor")
        existing = await db.marketplace_installed.find_one(
            {"app_id": app_id, "property_id": property_id}, {"_id": 0}
        )
        if existing:
            # Idempotent — refresh config
            await db.marketplace_installed.update_one(
                {"app_id": app_id, "property_id": property_id},
                {"$set": {
                    "config": body.get("config") or existing.get("config") or {},
                    "enabled": True,
                    "updated_at": _now(),
                    "updated_by": (current_user or {}).get("email"),
                }},
            )
            return {"ok": True, "action": "refreshed", "app_id": app_id, "property_id": property_id}
        doc = {
            "id": str(uuid.uuid4()),
            "app_id": app_id,
            "property_id": property_id,
            "config": body.get("config") or {},
            "enabled": True,
            "installed_at": _now(),
            "installed_by": (current_user or {}).get("email"),
        }
        await db.marketplace_installed.insert_one(dict(doc))
        doc.pop("_id", None)
        return {"ok": True, "action": "installed", "app_id": app_id, "property_id": property_id, "record": doc}

    @router.post("/uninstall")
    async def uninstall_app(body: dict,
                              current_user: dict = Depends(require_roles("admin", "manager"))):
        app_id = body.get("app_id")
        property_id = body.get("property_id")
        if not app_id or not property_id:
            raise HTTPException(400, "app_id and property_id required")
        res = await db.marketplace_installed.delete_one(
            {"app_id": app_id, "property_id": property_id}
        )
        return {"ok": True, "removed": res.deleted_count}

    @router.post("/toggle")
    async def toggle_app(body: dict,
                          current_user: dict = Depends(require_roles("admin", "manager"))):
        app_id = body.get("app_id")
        property_id = body.get("property_id")
        enabled = bool(body.get("enabled", True))
        if not app_id or not property_id:
            raise HTTPException(400, "app_id and property_id required")
        await db.marketplace_installed.update_one(
            {"app_id": app_id, "property_id": property_id},
            {"$set": {"enabled": enabled, "updated_at": _now(),
                       "updated_by": (current_user or {}).get("email")}},
        )
        return {"ok": True, "enabled": enabled}

    return router
