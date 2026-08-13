"""
Group Sales OS (lite) — "Üç bağımsız rapor" orta vade önceliği.
RFP yaşam döngüsü + wash/attrition + comp oda + teklif versiyonlama;
her teklif versiyonu shoulder-night'lı displacement analiziyle fiyatlanır
ve mevcut tek sayfalık teklif PDF'i (proposal-pdf) ile paylaşılabilir.

Collections: group_rfps {id, property_id, group_name, contact_name, contact_email,
  check_in, check_out, rooms, offered_rate, wash_pct, comp_rooms, notes,
  status: new|quoted|negotiating|won|lost, versions[], created_at}

Endpoints (/api/group-sales/*):
- GET  /{property_id}                 → RFP listesi + pipeline özeti
- POST /{property_id}/rfp             → RFP oluştur
- PUT  /rfp/{rfp_id}                  → alan/statü güncelle
- POST /rfp/{rfp_id}/quote            → yeni teklif versiyonu (displacement + PDF analiz id'si)
"""
import math
import uuid
from datetime import datetime, timezone
from typing import Dict

from fastapi import APIRouter, Depends, HTTPException

from routes.revenue_ext.group_displacement import compute_displacement, _d

STATUSES = ("new", "quoted", "negotiating", "won", "lost")


def create_group_sales_router(db, require_roles):
    router = APIRouter(prefix="/group-sales", tags=["group-sales"])

    @router.get("/{property_id}")
    async def list_rfps(property_id: str,
                        _: dict = Depends(require_roles("admin", "manager"))):
        rfps = await db.group_rfps.find(
            {"property_id": property_id}, {"_id": 0}).sort("created_at", -1).to_list(100)
        by_status = {s: 0 for s in STATUSES}
        potential, won_rev = 0.0, 0.0
        for r in rfps:
            by_status[r.get("status", "new")] = by_status.get(r.get("status", "new"), 0) + 1
            v = (r.get("versions") or [{}])[-1]
            rev = float(v.get("adj_group_revenue", 0) or 0)
            if r.get("status") == "won":
                won_rev += rev
            elif r.get("status") not in ("lost",):
                potential += rev
        closed = by_status["won"] + by_status["lost"]
        return {"rfps": rfps, "pipeline": {
            "by_status": by_status, "potential_revenue": round(potential, 2),
            "won_revenue": round(won_rev, 2),
            "conversion_pct": round(by_status["won"] / closed * 100, 1) if closed else 0}}

    @router.post("/{property_id}/rfp")
    async def create_rfp(property_id: str, body: Dict,
                         user: dict = Depends(require_roles("admin", "manager"))):
        try:
            start, end = _d(body["check_in"]), _d(body["check_out"])
            rooms = int(body["rooms"])
            rate = float(body["offered_rate"])
        except (KeyError, ValueError, TypeError):
            raise HTTPException(400, "check_in, check_out, rooms, offered_rate gerekli")
        if end <= start or rooms < 1 or rate < 0:
            raise HTTPException(400, "Geçersiz tarih/oda/fiyat")
        doc = {
            "id": str(uuid.uuid4()), "property_id": property_id,
            "group_name": (body.get("group_name") or "İsimsiz Grup").strip(),
            "contact_name": body.get("contact_name", ""), "contact_email": body.get("contact_email", ""),
            "check_in": body["check_in"], "check_out": body["check_out"],
            "rooms": rooms, "offered_rate": rate,
            "wash_pct": max(0.0, min(float(body.get("wash_pct", 10) or 0), 60)),
            "comp_rooms": max(0, int(body.get("comp_rooms", 0) or 0)),
            "notes": body.get("notes", ""), "status": "new", "versions": [],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": user.get("email", ""),
        }
        await db.group_rfps.insert_one(dict(doc))
        return {"ok": True, "rfp": doc}

    @router.put("/rfp/{rfp_id}")
    async def update_rfp(rfp_id: str, body: Dict,
                         _: dict = Depends(require_roles("admin", "manager"))):
        upd = {}
        for f in ("group_name", "contact_name", "contact_email", "notes"):
            if f in body:
                upd[f] = body[f]
        if "status" in body:
            if body["status"] not in STATUSES:
                raise HTTPException(400, f"status şunlardan biri olmalı: {STATUSES}")
            upd["status"] = body["status"]
        for f in ("rooms", "comp_rooms"):
            if f in body:
                upd[f] = max(0, int(body[f] or 0))
        for f in ("offered_rate", "wash_pct"):
            if f in body:
                upd[f] = max(0.0, float(body[f] or 0))
        if not upd:
            raise HTTPException(400, "Güncellenecek alan yok")
        upd["updated_at"] = datetime.now(timezone.utc).isoformat()
        r = await db.group_rfps.update_one({"id": rfp_id}, {"$set": upd})
        if not r.matched_count:
            raise HTTPException(404, "RFP bulunamadı")
        return {"ok": True}

    @router.post("/rfp/{rfp_id}/quote")
    async def quote(rfp_id: str, body: Dict,
                    user: dict = Depends(require_roles("admin", "manager"))):
        rfp = await db.group_rfps.find_one({"id": rfp_id}, {"_id": 0})
        if not rfp:
            raise HTTPException(404, "RFP bulunamadı")
        rate = float(body.get("offered_rate", rfp["offered_rate"]) or rfp["offered_rate"])
        wash = max(0.0, min(float(body.get("wash_pct", rfp.get("wash_pct", 10)) or 0), 60))
        comp = max(0, int(body.get("comp_rooms", rfp.get("comp_rooms", 0)) or 0))
        rooms = int(rfp["rooms"])
        start, end = _d(rfp["check_in"]), _d(rfp["check_out"])
        nights = (end - start).days

        expected_rooms = max(1, math.ceil(rooms * (1 - wash / 100)))
        paying_rooms = max(0, expected_rooms - comp)
        adj_revenue = round(paying_rooms * rate * nights, 2)

        computed = await compute_displacement(db, rfp["property_id"], start, end, expected_rooms, rate)
        # comp odalar ve wash sonrası GERÇEK grup geliri üzerinden net değer
        real_net = round(adj_revenue - computed["net_displacement_cost"], 2)

        analysis = {
            "id": str(uuid.uuid4()), "property_id": rfp["property_id"],
            "group_name": rfp["group_name"], "check_in": rfp["check_in"], "check_out": rfp["check_out"],
            "rooms_requested": expected_rooms, "offered_rate": rate,
            **computed, "total_group_revenue": adj_revenue,
            "net_value_after_commission": real_net,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": user.get("email", ""),
        }
        await db.group_displacement_analyses.insert_one(dict(analysis))

        version = {
            "v": len(rfp.get("versions") or []) + 1,
            "offered_rate": rate, "rooms": rooms, "expected_rooms": expected_rooms,
            "wash_pct": wash, "comp_rooms": comp, "nights": nights,
            "adj_group_revenue": adj_revenue,
            "recommendation": computed["recommendation"],
            "net_value_after_commission": real_net,
            "breakeven_rate_net": computed["breakeven_rate_net"],
            "suggested_min_rate_net": computed["suggested_min_rate_net"],
            "shoulder_loss": computed["shoulder_loss"],
            "analysis_id": analysis["id"],
            "note": body.get("note", ""),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": user.get("email", ""),
        }
        await db.group_rfps.update_one(
            {"id": rfp_id},
            {"$push": {"versions": version},
             "$set": {"status": "quoted" if rfp.get("status") == "new" else rfp.get("status"),
                      "offered_rate": rate, "wash_pct": wash, "comp_rooms": comp,
                      "updated_at": datetime.now(timezone.utc).isoformat()}})
        return {"ok": True, "version": version}

    return router
