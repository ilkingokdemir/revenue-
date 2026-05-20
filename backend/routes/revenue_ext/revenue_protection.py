"""
Booking Insurance Upsell + OTA Parity Defender + Outbound Webhooks
------------------------------------------------------------------
Three small but impactful endpoints bundled together to save a router file.

1. INSURANCE — at-checkout offer of cancellation insurance. Pure rule-based
   pricing (% of total) until a real Booking Protect partnership is set up.
2. PARITY DEFENDER — auto-undercut OTA price by configurable % on direct widget.
   Reads existing parity_analysis collection.
3. WEBHOOKS — admin can subscribe an external URL to events
   (booking.created, booking.cancelled, folio.charged, no_show.marked).
   Outbound calls are best-effort fire-and-forget HTTPS POSTs.

Endpoints:
  GET  /api/insurance/{property_id}/config
  POST /api/insurance/{property_id}/config
  POST /api/insurance/quote                    (PUBLIC — for widget)

  GET  /api/parity-defender/{property_id}/config
  POST /api/parity-defender/{property_id}/config
  GET  /api/parity-defender/{property_id}/recommendation

  GET  /api/webhooks/{property_id}
  POST /api/webhooks/{property_id}             — subscribe
  DELETE /api/webhooks/{property_id}/{webhook_id}
  POST /api/webhooks/{property_id}/test/{webhook_id}
  GET  /api/webhooks/{property_id}/log         — recent fires
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
import uuid
import asyncio
import logging

logger = logging.getLogger(__name__)


def create_revenue_protection_router(db, require_roles):
    router = APIRouter()

    # --------------------------- Insurance ---------------------------

    DEFAULT_INSURANCE = {
        "enabled": True,
        "rate_pct": 5.0,            # 5 % of total
        "min_premium": 3.0,
        "max_premium": 75.0,
        "currency": "GBP",
        "label": "Cancel-anytime protection",
        "terms_url": "",
    }

    @router.get("/insurance/{property_id}/config")
    async def get_ins_cfg(property_id: str,
                            current_user: dict = Depends(require_roles("admin", "manager"))):
        doc = await db.insurance_config.find_one({"property_id": property_id}, {"_id": 0}) or {}
        return {**DEFAULT_INSURANCE, **doc}

    @router.post("/insurance/{property_id}/config")
    async def set_ins_cfg(property_id: str, data: Dict,
                            current_user: dict = Depends(require_roles("admin", "manager"))):
        update = {**DEFAULT_INSURANCE, **{k: v for k, v in data.items() if k in DEFAULT_INSURANCE}}
        update["property_id"] = property_id
        update["updated_at"] = datetime.now(timezone.utc).isoformat()
        await db.insurance_config.update_one({"property_id": property_id}, {"$set": update}, upsert=True)
        return {"ok": True, "config": update}

    @router.post("/insurance/quote")
    async def insurance_quote(data: Dict):
        """PUBLIC — booking widget calls this at checkout."""
        property_id = data.get("property_id", "")
        total = float(data.get("total") or 0)
        if not property_id or total <= 0:
            return {"available": False, "reason": "missing property_id or total"}
        cfg = {**DEFAULT_INSURANCE, **(await db.insurance_config.find_one(
            {"property_id": property_id}, {"_id": 0}) or {})}
        if not cfg.get("enabled"):
            return {"available": False, "reason": "disabled"}
        premium = max(cfg["min_premium"], min(cfg["max_premium"], round(total * cfg["rate_pct"] / 100, 2)))
        return {
            "available": True,
            "label": cfg["label"],
            "premium": premium,
            "currency": cfg["currency"],
            "rate_pct": cfg["rate_pct"],
            "terms_url": cfg["terms_url"],
        }

    # --------------------------- Parity Defender ---------------------------

    DEFAULT_PARITY = {
        "enabled": True,
        "undercut_pct": 5.0,  # show direct as 5 % cheaper than lowest OTA
        "floor_pct_of_base": 80.0,
        "min_undercut_amount": 1.0,
        "show_savings_badge": True,
    }

    @router.get("/parity-defender/{property_id}/config")
    async def get_par_cfg(property_id: str,
                            current_user: dict = Depends(require_roles("admin", "manager"))):
        doc = await db.parity_defender_config.find_one({"property_id": property_id}, {"_id": 0}) or {}
        return {**DEFAULT_PARITY, **doc}

    @router.post("/parity-defender/{property_id}/config")
    async def set_par_cfg(property_id: str, data: Dict,
                            current_user: dict = Depends(require_roles("admin", "manager"))):
        update = {**DEFAULT_PARITY, **{k: v for k, v in data.items() if k in DEFAULT_PARITY}}
        update["property_id"] = property_id
        update["updated_at"] = datetime.now(timezone.utc).isoformat()
        await db.parity_defender_config.update_one({"property_id": property_id}, {"$set": update}, upsert=True)
        return {"ok": True, "config": update}

    @router.get("/parity-defender/{property_id}/recommendation")
    async def parity_recommendation(property_id: str,
                                       current_user: dict = Depends(require_roles("admin", "manager"))):
        cfg = {**DEFAULT_PARITY, **(await db.parity_defender_config.find_one(
            {"property_id": property_id}, {"_id": 0}) or {})}
        # Pull most recent parity_analysis snapshot (ratescraper output)
        snap = await db.parity_analysis.find_one(
            {"property_id": property_id}, {"_id": 0},
            sort=[("captured_at", -1)],
        ) or {}
        ota_rates = snap.get("ota_rates") or snap.get("competitor_rates") or []
        # ota_rates expected list of {channel, rate, date}
        per_date: Dict[str, Dict] = {}
        for r in ota_rates:
            d = r.get("date") or ""
            row = per_date.setdefault(d, {"date": d, "min_ota": None, "min_channel": "", "rates": []})
            row["rates"].append({"channel": r.get("channel"), "rate": float(r.get("rate") or 0)})
            rate = float(r.get("rate") or 0)
            if row["min_ota"] is None or rate < row["min_ota"]:
                row["min_ota"] = rate
                row["min_channel"] = r.get("channel", "")
        # Compute recommended direct rate per date
        recs = []
        for d, row in per_date.items():
            if not row["min_ota"]:
                continue
            undercut = max(cfg["min_undercut_amount"], row["min_ota"] * cfg["undercut_pct"] / 100)
            recommended = round(max(0.0, row["min_ota"] - undercut), 2)
            recs.append({
                "date": d,
                "lowest_ota": row["min_ota"],
                "lowest_ota_channel": row["min_channel"],
                "rates": row["rates"],
                "recommended_direct": recommended,
                "savings": round(row["min_ota"] - recommended, 2),
                "savings_pct": round((row["min_ota"] - recommended) / row["min_ota"] * 100, 1) if row["min_ota"] else 0,
            })
        recs.sort(key=lambda x: x["date"])
        return {
            "config": cfg,
            "snapshot_at": snap.get("captured_at", ""),
            "recommendations": recs,
            "show_savings_badge": cfg["show_savings_badge"],
        }

    # --------------------------- Webhooks ---------------------------

    SUPPORTED_EVENTS = [
        "booking.created", "booking.cancelled", "booking.checked_in", "booking.checked_out",
        "folio.charged", "no_show.marked", "review.received", "complaint.created",
    ]

    @router.get("/webhooks/{property_id}")
    async def list_webhooks(property_id: str,
                              current_user: dict = Depends(require_roles("admin", "manager"))):
        rows = await db.webhook_subscriptions.find(
            {"property_id": property_id}, {"_id": 0}
        ).to_list(50)
        return {"items": rows, "supported_events": SUPPORTED_EVENTS}

    @router.post("/webhooks/{property_id}")
    async def subscribe(property_id: str, data: Dict,
                          current_user: dict = Depends(require_roles("admin", "manager"))):
        url = (data.get("url") or "").strip()
        events = data.get("events") or []
        if not url.startswith("https://"):
            raise HTTPException(400, "url must start with https://")
        unsupported = [e for e in events if e not in SUPPORTED_EVENTS]
        if unsupported:
            raise HTTPException(400, f"unsupported events: {unsupported}")
        record = {
            "id": str(uuid.uuid4()),
            "property_id": property_id,
            "url": url,
            "events": events,
            "secret": data.get("secret", str(uuid.uuid4())),
            "active": bool(data.get("active", True)),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": current_user.get("name", "Staff"),
            "fire_count": 0,
            "fail_count": 0,
        }
        await db.webhook_subscriptions.insert_one(dict(record))
        record.pop("_id", None)
        return {"ok": True, "webhook": record}

    @router.delete("/webhooks/{property_id}/{webhook_id}")
    async def unsubscribe(property_id: str, webhook_id: str,
                            current_user: dict = Depends(require_roles("admin", "manager"))):
        await db.webhook_subscriptions.delete_one({"id": webhook_id, "property_id": property_id})
        return {"ok": True}

    @router.post("/webhooks/{property_id}/test/{webhook_id}")
    async def test_webhook(property_id: str, webhook_id: str,
                             current_user: dict = Depends(require_roles("admin", "manager"))):
        wh = await db.webhook_subscriptions.find_one({"id": webhook_id, "property_id": property_id}, {"_id": 0})
        if not wh:
            raise HTTPException(404, "Webhook not found")
        payload = {
            "event": "test.ping",
            "property_id": property_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": {"hello": "world"},
        }
        result = await _fire(db, wh, payload)
        return {"ok": True, **result}

    @router.get("/webhooks/{property_id}/log")
    async def webhook_log(property_id: str, days: int = 7,
                            current_user: dict = Depends(require_roles("admin", "manager"))):
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        rows = await db.webhook_log.find(
            {"property_id": property_id, "fired_at": {"$gte": since}}, {"_id": 0}
        ).sort("fired_at", -1).to_list(200)
        return rows

    return router


async def _fire(db, wh: dict, payload: dict) -> Dict:
    """Best-effort POST. Returns a small status dict."""
    import httpx
    started = datetime.now(timezone.utc)
    status_code = 0
    error = ""
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.post(
                wh["url"],
                json=payload,
                headers={
                    "X-Webhook-Secret": wh.get("secret", ""),
                    "X-Webhook-Event": payload.get("event", ""),
                },
            )
            status_code = resp.status_code
    except Exception as e:
        error = str(e)
    duration_ms = round((datetime.now(timezone.utc) - started).total_seconds() * 1000, 1)
    success = 200 <= status_code < 300
    log = {
        "id": str(uuid.uuid4()),
        "property_id": wh.get("property_id", ""),
        "webhook_id": wh.get("id", ""),
        "event": payload.get("event", ""),
        "url": wh.get("url", ""),
        "status_code": status_code,
        "success": success,
        "error": error,
        "duration_ms": duration_ms,
        "fired_at": started.isoformat(),
    }
    await db.webhook_log.insert_one(dict(log))
    log.pop("_id", None)
    await db.webhook_subscriptions.update_one(
        {"id": wh.get("id", "")},
        {"$inc": {"fire_count": 1, **({"fail_count": 1} if not success else {})}},
    )
    return log
