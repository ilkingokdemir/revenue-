"""
VCC Gelir Kurtarma (RobosizeME "VCC Reconciliation" paritesi) — OTA sanal kart
tutarsızlıklarını tespit eder ve kurtarılabilir geliri raporlar:
  - missed_charge : aktivasyonu geçmiş, hâlâ çekilmemiş kartlar → "Şimdi çek"
  - expired       : süresi dolmuş, tahsil edilememiş kartlar → OTA'ya itiraz
  - underfunded   : rezervasyon tutarı sonradan arttı, kart eski tutarda → fark itirazı
  - cancel_fee    : iptal edilmiş ama iptal ücreti çekilmemiş rezervasyonlar
Collections: ota_disputes. Motor: vcc_recovery.
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, date, timedelta
from typing import Dict, List
import uuid
import logging

logger = logging.getLogger(__name__)

TYPE_LABELS = {
    "missed_charge": "Unutulmuş çekim",
    "expired": "Süresi dolmuş kart",
    "underfunded": "Eksik yüklenmiş kart",
    "cancel_fee": "İptal ücreti çekilmemiş",
}
TYPE_ACTIONS = {
    "missed_charge": "charge_now",
    "expired": "open_dispute",
    "underfunded": "open_dispute",
    "cancel_fee": "open_dispute",
}


def _now():
    return datetime.now(timezone.utc).isoformat()


async def scan_recovery_internal(db, property_id: str = "all") -> Dict:
    today = date.today().isoformat()
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    pq: Dict = {} if property_id == "all" else {"property_id": property_id}
    cards = await db.vcc_cards.find(pq, {"_id": 0}).to_list(2000)
    disputed_ids = {d["vcc_id"] for d in await db.ota_disputes.find(
        {"status": {"$in": ["open", "recovered"]}}, {"_id": 0, "vcc_id": 1}).to_list(2000)}

    items: List[Dict] = []
    for c in cards:
        if c["id"] in disputed_ids:
            continue
        bk = await db.bookings.find_one({"id": c.get("booking_id", "")},
                                        {"_id": 0, "status": 1, "total_price": 1,
                                         "check_in": 1, "check_out": 1, "cancelled_at": 1})
        base = {"vcc_id": c["id"], "booking_id": c.get("booking_id", ""),
                "guest_name": c.get("guest_name", ""), "channel": c.get("channel", ""),
                "property_id": c.get("property_id", ""), "currency": c.get("currency", "GBP"),
                "card_amount": float(c.get("amount", 0)), "card_status": c.get("status", "")}

        # 1) Cancelled booking with uncharged card → cancellation fee (1 night)
        if bk and bk.get("status") == "cancelled" and c.get("status") in ("pending", "failed"):
            try:
                ci = datetime.fromisoformat(bk.get("check_in", today)).date()
                co = datetime.fromisoformat(bk.get("check_out", today)).date()
                nights = max((co - ci).days, 1)
            except Exception:
                nights = 1
            fee = round(float(bk.get("total_price") or c.get("amount", 0)) / nights, 2)
            if fee > 0:
                items.append({**base, "type": "cancel_fee", "recoverable": fee,
                              "detail": f"İptal edilmiş rezervasyon — 1 gece iptal ücreti ({fee}) tahsil edilmedi"})
            continue

        # 2) Expired uncharged
        if c.get("status") == "expired":
            items.append({**base, "type": "expired", "recoverable": float(c.get("amount", 0)),
                          "detail": "Kart tahsil edilemeden süresi doldu — OTA'ya itiraz açılmalı"})
            continue

        # 3) Missed charge (activation passed ≥1 day, still uncharged, booking active)
        if c.get("status") in ("pending", "failed") and c.get("activation_date", "9999") <= yesterday:
            items.append({**base, "type": "missed_charge", "recoverable": float(c.get("amount", 0)),
                          "detail": f"Aktivasyon {c.get('activation_date')} tarihinde geçti, hâlâ çekilmedi"
                                    + (f" ({c.get('attempts', 0)} deneme)" if c.get("attempts") else "")})
            continue

        # 4) Underfunded: booking total increased after card issued
        if bk and bk.get("status") not in ("cancelled", "no_show"):
            total = float(bk.get("total_price") or 0)
            card_amt = float(c.get("amount", 0))
            if total > card_amt + 0.01:
                items.append({**base, "type": "underfunded", "recoverable": round(total - card_amt, 2),
                              "detail": f"Rezervasyon tutarı {total} oldu, kart {card_amt} tutarında — fark OTA'dan talep edilmeli"})

    by_type: Dict[str, Dict] = {}
    for i in items:
        t = by_type.setdefault(i["type"], {"type": i["type"], "label": TYPE_LABELS[i["type"]],
                                           "count": 0, "recoverable": 0.0})
        t["count"] += 1
        t["recoverable"] = round(t["recoverable"] + i["recoverable"], 2)
    items.sort(key=lambda x: -x["recoverable"])
    for i in items:
        i["type_label"] = TYPE_LABELS[i["type"]]
        i["action"] = TYPE_ACTIONS[i["type"]]

    open_disputes = await db.ota_disputes.count_documents({"status": "open"})
    recovered_agg = await db.ota_disputes.aggregate([
        {"$match": {"status": "recovered"}},
        {"$group": {"_id": None, "total": {"$sum": "$recovered_amount"}}}]).to_list(1)
    return {"scanned_cards": len(cards), "items": items[:100],
            "total_recoverable": round(sum(i["recoverable"] for i in items), 2),
            "by_type": sorted(by_type.values(), key=lambda x: -x["recoverable"]),
            "open_disputes": open_disputes,
            "recovered_to_date": round((recovered_agg[0]["total"] if recovered_agg else 0) or 0, 2)}


async def recovery_job(db) -> Dict:
    scan = await scan_recovery_internal(db, "all")
    if scan["total_recoverable"] > 0:
        await db.notifications.insert_one({
            "id": str(uuid.uuid4()), "type": "warning", "category": "vcc_recovery",
            "title": "💸 VCC Gelir Kurtarma Fırsatı",
            "message": f"{len(scan['items'])} tutarsızlık tespit edildi — kurtarılabilir gelir: £{scan['total_recoverable']:,}",
            "target_user": "", "target_role": "manager", "link_to": "vcc-automation",
            "priority": "high", "read": False, "created_by": "VCC Recovery",
            "created_at": _now()})
    return {"ok": True, "found": len(scan["items"]), "recoverable": scan["total_recoverable"]}


def create_vcc_recovery_router(db, require_roles):
    router = APIRouter(prefix="/vcc-recovery")
    router.run_internal = lambda: recovery_job(db)

    @router.get("/{property_id}/scan")
    async def scan(property_id: str,
                   current_user: dict = Depends(require_roles("admin", "manager"))):
        return await scan_recovery_internal(db, property_id)

    @router.post("/dispute/{vcc_id}")
    async def open_dispute(vcc_id: str, data: Dict,
                           current_user: dict = Depends(require_roles("admin", "manager"))):
        card = await db.vcc_cards.find_one({"id": vcc_id}, {"_id": 0})
        if not card:
            raise HTTPException(404, "VCC bulunamadı")
        existing = await db.ota_disputes.find_one({"vcc_id": vcc_id, "status": "open"}, {"_id": 0, "id": 1})
        if existing:
            raise HTTPException(400, "Bu kart için zaten açık itiraz var")
        doc = {
            "id": str(uuid.uuid4()), "vcc_id": vcc_id,
            "booking_id": card.get("booking_id", ""), "guest_name": card.get("guest_name", ""),
            "channel": card.get("channel", ""), "property_id": card.get("property_id", ""),
            "type": data.get("type", "expired"), "claim_amount": float(data.get("amount") or card.get("amount", 0)),
            "currency": card.get("currency", "GBP"),
            "reason": (data.get("reason") or TYPE_LABELS.get(data.get("type", "expired"), ""))[:300],
            "status": "open", "opened_by": current_user.get("email", ""),
            "created_at": _now(),
        }
        await db.ota_disputes.insert_one(dict(doc))
        doc.pop("_id", None)
        return doc

    @router.post("/dispute/{dispute_id}/resolve")
    async def resolve_dispute(dispute_id: str, data: Dict,
                              current_user: dict = Depends(require_roles("admin", "manager"))):
        outcome = data.get("outcome", "recovered")
        if outcome not in ("recovered", "written_off"):
            raise HTTPException(400, "outcome recovered|written_off olmalı")
        d = await db.ota_disputes.find_one({"id": dispute_id, "status": "open"}, {"_id": 0})
        if not d:
            raise HTTPException(404, "Açık itiraz bulunamadı")
        upd = {"status": outcome, "resolved_at": _now(), "resolved_by": current_user.get("email", "")}
        if outcome == "recovered":
            upd["recovered_amount"] = float(data.get("amount") or d.get("claim_amount", 0))
        await db.ota_disputes.update_one({"id": dispute_id}, {"$set": upd})
        return {"ok": True, "status": outcome, "recovered_amount": upd.get("recovered_amount", 0)}

    @router.get("/{property_id}/disputes")
    async def list_disputes(property_id: str, status: str = "",
                            current_user: dict = Depends(require_roles("admin", "manager"))):
        q: Dict = {} if property_id == "all" else {"property_id": property_id}
        if status:
            q["status"] = status
        rows = await db.ota_disputes.find(q, {"_id": 0}).sort("created_at", -1).to_list(100)
        return {"disputes": rows,
                "open_total": round(sum(r.get("claim_amount", 0) for r in rows if r["status"] == "open"), 2),
                "recovered_total": round(sum(r.get("recovered_amount", 0) for r in rows if r["status"] == "recovered"), 2)}

    return router
