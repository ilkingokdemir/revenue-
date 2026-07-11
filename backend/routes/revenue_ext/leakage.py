"""
Revenue Leakage Auditor (iter 403) — scans for money silently leaking:
unpaid folio balances, accepted upsells never posted to folio,
uncharged no-shows and zero-rate bookings.
"""
from fastapi import APIRouter, Depends
from datetime import datetime, timezone, timedelta
import logging
import os
import uuid

from routes.finance_ext.deposit_automation import _stripe_post

logger = logging.getLogger(__name__)


def create_leakage_router(db, require_roles):
    router = APIRouter()

    @router.get("/revenue/leakage/{property_id}")
    async def leakage(property_id: str, days: int = 30,
                      current_user: dict = Depends(require_roles("admin", "manager"))):
        return await _scan_core(property_id, days)

    async def _scan_core(property_id: str, days: int = 30) -> dict:
        days = min(max(days, 7), 180)
        now = datetime.now(timezone.utc)
        today = now.date().isoformat()
        since = (now.date() - timedelta(days=days)).isoformat()
        pq = {} if property_id == "all" else {"property_id": property_id}

        # 1. Unpaid folio balances on checked-out stays
        outs = await db.bookings.find(
            {**pq, "status": "checked_out", "check_out": {"$gte": since, "$lte": today}},
            {"_id": 0, "id": 1, "booking_ref": 1, "guest_name": 1}).to_list(3000)
        out_map = {b["id"]: b for b in outs}
        unpaid_items = []
        if out_map:
            pipeline = [
                {"$match": {"booking_id": {"$in": list(out_map.keys())}}},
                {"$group": {"_id": "$booking_id",
                            "charges": {"$sum": {"$cond": [{"$eq": ["$type", "payment"]}, 0, "$amount"]}},
                            "payments": {"$sum": {"$cond": [{"$eq": ["$type", "payment"]}, "$amount", 0]}}}},
            ]
            async for g in db.folio_items.aggregate(pipeline):
                bal = round(float(g.get("charges") or 0) - float(g.get("payments") or 0), 2)
                if bal > 0.5:
                    b = out_map.get(g["_id"], {})
                    unpaid_items.append({"booking_id": g["_id"], "ref": b.get("booking_ref", ""),
                                         "guest_name": b.get("guest_name", ""), "amount": bal,
                                         "detail": "Folyo bakiyesi ödenmemiş"})
        unpaid_items.sort(key=lambda x: -x["amount"])

        # 2. Accepted upsells never posted to folio
        since_iso = (now - timedelta(days=days)).isoformat()
        accepted = await db.upsell_offers.find(
            {**pq, "status": "accepted", "accepted_at": {"$gte": since_iso}},
            {"_id": 0, "booking_id": 1, "category": 1, "price": 1, "charged_amount": 1}).to_list(2000)
        missing_upsell = []
        if accepted:
            bids = list({a["booking_id"] for a in accepted})
            posted = await db.folio_items.find(
                {"booking_id": {"$in": bids}, "category": "upsell"},
                {"_id": 0, "booking_id": 1}).to_list(5000)
            posted_ids = {p["booking_id"] for p in posted}
            for a in accepted:
                if a["booking_id"] not in posted_ids:
                    amt = float(a.get("charged_amount") or a.get("price") or 0)
                    missing_upsell.append({"booking_id": a["booking_id"], "ref": "",
                                           "guest_name": "", "amount": round(amt, 2),
                                           "detail": f"Upsell ({a.get('category', '?')}) folyoya işlenmemiş"})

        # 3. No-shows never charged
        noshows = await db.bookings.find(
            {**pq, "status": "no_show", "check_in": {"$gte": since, "$lte": today},
             "total_price": {"$gt": 0}, "no_show_charged": {"$ne": True}},
            {"_id": 0, "id": 1, "booking_ref": 1, "guest_name": 1, "total_price": 1}).to_list(2000)
        noshow_items = []
        if noshows:
            ids = [b["id"] for b in noshows]
            pays = await db.folio_items.find(
                {"booking_id": {"$in": ids}, "type": "payment"},
                {"_id": 0, "booking_id": 1}).to_list(5000)
            paid_ids = {p["booking_id"] for p in pays}
            for b in noshows:
                if b["id"] not in paid_ids:
                    noshow_items.append({"booking_id": b["id"], "ref": b.get("booking_ref", ""),
                                         "guest_name": b.get("guest_name", ""),
                                         "amount": round(float(b["total_price"]), 2),
                                         "detail": "No-show ücreti tahsil edilmemiş"})
        noshow_items.sort(key=lambda x: -x["amount"])

        # 4. Zero-rate active bookings (data errors)
        zero = await db.bookings.find(
            {**pq, "status": {"$in": ["confirmed", "checked_in", "checked_out"]},
             "check_in": {"$gte": since},
             "$or": [{"total_price": {"$in": [0, None]}}, {"total_price": {"$exists": False}}]},
            {"_id": 0, "id": 1, "booking_ref": 1, "guest_name": 1, "room_type_name": 1}).to_list(2000)
        zero_items = [{"booking_id": b["id"], "ref": b.get("booking_ref", ""),
                       "guest_name": b.get("guest_name", ""), "amount": 0,
                       "detail": f"Sıfır fiyatlı rezervasyon ({b.get('room_type_name') or 'oda'})"}
                      for b in zero]

        def row(key, name, desc, items):
            return {"key": key, "name": name, "desc": desc, "count": len(items),
                    "leaked": round(sum(i["amount"] for i in items), 2), "items": items[:10]}

        rows = [
            row("unpaid_folio", "Ödenmemiş Folyolar",
                "Check-out olmuş ama folyo bakiyesi kapanmamış konaklamalar", unpaid_items),
            row("missing_upsell", "Folyoya İşlenmemiş Upsell'ler",
                "Misafir kabul etti ama ücret folyoya hiç yansımadı", missing_upsell),
            row("noshow_uncharged", "Tahsil Edilmemiş No-Show'lar",
                "Gelmeyen misafirlerden hiç ödeme alınmamış", noshow_items),
            row("zero_rate", "Sıfır Fiyatlı Rezervasyonlar",
                "Fiyatı 0 veya boş görünen aktif rezervasyonlar (veri hatası)", zero_items),
        ]
        return {"property_id": property_id, "days": days, "rows": rows,
                "total_leaked": round(sum(r["leaked"] for r in rows), 2),
                "total_items": sum(r["count"] for r in rows)}

    @router.post("/revenue/leakage/{property_id}/charge-noshows")
    async def charge_noshows(property_id: str, data: dict = None,
                             current_user: dict = Depends(require_roles("admin", "manager"))):
        """Bulk-post no-show fees to folio; attempt Stripe charge when a vault card exists."""
        body = data or {}
        return await _charge_core(
            property_id,
            body.get("policy") if body.get("policy") in ("first_night", "full") else "first_night",
            min(max(int(body.get("days") or 30), 7), 180),
            current_user.get("email", "system"))

    async def _charge_core(property_id: str, policy: str, days: int, actor: str) -> dict:
        now = datetime.now(timezone.utc)
        today = now.date().isoformat()
        since = (now.date() - timedelta(days=days)).isoformat()
        pq = {} if property_id == "all" else {"property_id": property_id}
        stripe_key = os.environ.get("STRIPE_API_KEY")

        noshows = await db.bookings.find(
            {**pq, "status": "no_show", "check_in": {"$gte": since, "$lte": today},
             "total_price": {"$gt": 0}, "no_show_charged": {"$ne": True}},
            {"_id": 0}).to_list(2000)
        if noshows:
            ids = [b["id"] for b in noshows]
            pays = await db.folio_items.find(
                {"booking_id": {"$in": ids}, "type": "payment"},
                {"_id": 0, "booking_id": 1}).to_list(5000)
            paid = {p["booking_id"] for p in pays}
            noshows = [b for b in noshows if b["id"] not in paid]

        posted, collected, no_card = 0, 0, 0
        total_posted = 0.0
        now_iso = now.isoformat()
        for b in noshows:
            total = float(b.get("total_price") or 0)
            nights = max(int(b.get("nights") or 1), 1)
            fee = round(total if policy == "full" else total / nights, 2)
            desc = f"No-show ücreti ({'tam tutar' if policy == 'full' else 'ilk gece'})"
            await db.folio_items.insert_one({
                "id": str(uuid.uuid4()), "booking_id": b["id"],
                "property_id": b.get("property_id"),
                "type": "charge", "category": "no_show", "description": desc,
                "quantity": 1, "unit_price": fee, "amount": fee, "currency": "GBP",
                "created_at": now_iso, "created_by": actor})
            charged_ok = False
            card = await db.vault_cards.find_one(
                {"booking_id": b["id"], "status": "active"}, {"_id": 0}) if stripe_key else None
            if card:
                code, pi = await _stripe_post("/payment_intents", {
                    "amount": int(round(fee * 100)), "currency": "gbp",
                    "customer": card["stripe_customer_id"],
                    "payment_method": card["payment_method_id"],
                    "off_session": "true", "confirm": "true",
                    "description": f"No-show fee · booking {b.get('booking_ref', '')}",
                    "metadata[booking_id]": b["id"],
                }, stripe_key)
                if code < 400 and pi.get("status") == "succeeded":
                    charged_ok = True
                    await db.folio_items.insert_one({
                        "id": str(uuid.uuid4()), "booking_id": b["id"],
                        "property_id": b.get("property_id"),
                        "type": "payment", "category": "card",
                        "description": f"No-show tahsilatı · {card.get('brand', '').title()} •••• {card.get('last4', '')}",
                        "quantity": 1, "unit_price": fee, "amount": fee, "currency": "GBP",
                        "reference": pi.get("id", ""), "created_at": now_iso,
                        "created_by": "noshow-auto"})
                    collected += 1
            else:
                no_card += 1
            await db.bookings.update_one(
                {"id": b["id"]},
                {"$set": {"no_show_charged": True, "no_show_fee": fee,
                          "no_show_collected": charged_ok, "no_show_charged_at": now_iso}})
            posted += 1
            total_posted += fee

        return {"ok": True, "policy": policy, "posted": posted,
                "total_posted": round(total_posted, 2),
                "collected_via_card": collected, "no_card_on_file": no_card}

    async def _sweep_core(property_id: str = "") -> dict:
        """Weekly autonomous sweep: scan → auto-charge no-shows (first night) → log."""
        pid = property_id or "default"
        before = await _scan_core(pid, 30)
        charge = await _charge_core(pid, "first_night", 30, "leakage-sweep")
        after = await _scan_core(pid, 30)
        entry = {
            "id": str(uuid.uuid4()), "property_id": pid,
            "ran_at": datetime.now(timezone.utc).isoformat(),
            "found_total": before["total_leaked"], "found_items": before["total_items"],
            "closed_total": charge["total_posted"], "closed_items": charge["posted"],
            "collected_via_card": charge["collected_via_card"],
            "remaining_total": after["total_leaked"], "remaining_items": after["total_items"],
        }
        await db.leakage_sweep_log.insert_one(dict(entry))
        return {"ok": True, **{k: v for k, v in entry.items() if k != "id"}}

    @router.get("/revenue/leakage/{property_id}/sweep-log")
    async def sweep_log(property_id: str, limit: int = 10,
                        current_user: dict = Depends(require_roles("admin", "manager"))):
        q = {} if property_id == "all" else {"property_id": property_id}
        rows = await db.leakage_sweep_log.find(q, {"_id": 0}).sort("ran_at", -1).to_list(int(limit))
        return {"rows": rows}

    router.run_leakage_sweep_internal = _sweep_core
    return router
