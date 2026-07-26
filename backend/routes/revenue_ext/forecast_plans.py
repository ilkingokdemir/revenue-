"""
Forecast Planlama Çalışma Alanı (FLYR Planning paritesi) — AI forecast'ı
sürümler, ekip düzeltmesine açar, kilitler (locked/published), yorum + onay
akışıyla izler ve sürümleri yan yana karşılaştırır.
Collection: forecast_versions {id, property_id, name, status: draft|locked,
  months, rows[{period,label,bookings,revenue,adr,confidence}], baseline_rows,
  adjustments[], comments[], approvals[], created_by, created_at, locked_*}
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone
from typing import Dict, Optional
import uuid
import logging

logger = logging.getLogger(__name__)

STAFF = ("admin", "manager")


def _iso():
    return datetime.now(timezone.utc).isoformat()


def _totals(rows):
    return {"bookings": sum(int(r.get("bookings", 0)) for r in rows),
            "revenue": round(sum(float(r.get("revenue", 0)) for r in rows), 2)}


def create_forecast_plans_router(db, require_roles):
    router = APIRouter(prefix="/forecast-plans")

    @router.post("/{property_id}/versions")
    async def create_version(property_id: str, data: Dict,
                             current_user: dict = Depends(require_roles(*STAFF))):
        from routes.revenue_ext.forecast_v2 import compute_horizon
        months = max(3, min(int(data.get("months", 12) or 12), 24))
        name = (data.get("name") or "").strip() or f"Forecast {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}"
        h = await compute_horizon(db, property_id, months)
        rows = [{"period": f["period"], "label": f["label"], "bookings": f["bookings"],
                 "revenue": f["revenue"], "adr": f["adr"], "confidence": f["confidence"]}
                for f in h.get("forecast", [])]
        doc = {"id": str(uuid.uuid4()), "property_id": property_id, "name": name,
               "status": "draft", "months": months, "rows": rows,
               "baseline_rows": [dict(r) for r in rows],
               "adjustments": [], "comments": [], "approvals": [],
               "created_by": current_user.get("name") or current_user.get("email", ""),
               "created_at": _iso()}
        await db.forecast_versions.insert_one(dict(doc))
        return {"ok": True, "version": doc}

    @router.get("/{property_id}/versions")
    async def list_versions(property_id: str,
                            current_user: dict = Depends(require_roles(*STAFF))):
        q = {} if property_id == "all" else {"property_id": property_id}
        rows = await db.forecast_versions.find(q, {"_id": 0}).sort("created_at", -1).to_list(100)
        out = []
        for v in rows:
            t = _totals(v["rows"])
            out.append({"id": v["id"], "property_id": v["property_id"], "name": v["name"],
                        "status": v["status"], "months": v["months"],
                        "total_bookings": t["bookings"], "total_revenue": t["revenue"],
                        "adjustment_count": len(v.get("adjustments", [])),
                        "comment_count": len(v.get("comments", [])),
                        "approval_count": len(v.get("approvals", [])),
                        "created_by": v.get("created_by", ""), "created_at": v["created_at"],
                        "locked_at": v.get("locked_at"), "locked_by": v.get("locked_by")})
        return {"versions": out,
                "summary": {"draft": sum(1 for v in rows if v["status"] == "draft"),
                            "locked": sum(1 for v in rows if v["status"] == "locked")}}

    @router.get("/versions/{version_id}")
    async def get_version(version_id: str,
                          current_user: dict = Depends(require_roles(*STAFF))):
        v = await db.forecast_versions.find_one({"id": version_id}, {"_id": 0})
        if not v:
            raise HTTPException(404, "Sürüm bulunamadı")
        v["totals"] = _totals(v["rows"])
        v["baseline_totals"] = _totals(v.get("baseline_rows", []))
        return v

    @router.put("/versions/{version_id}/rows")
    async def adjust_rows(version_id: str, data: Dict,
                          current_user: dict = Depends(require_roles(*STAFF))):
        """Body: {period, bookings?, revenue?, note?} — sadece taslak sürümde."""
        v = await db.forecast_versions.find_one({"id": version_id}, {"_id": 0})
        if not v:
            raise HTTPException(404, "Sürüm bulunamadı")
        if v["status"] != "draft":
            raise HTTPException(400, "Kilitli sürüm düzenlenemez — yeni taslak oluşturun")
        period = data.get("period", "")
        row = next((r for r in v["rows"] if r["period"] == period), None)
        if not row:
            raise HTTPException(404, "Dönem bulunamadı")
        user = current_user.get("name") or current_user.get("email", "")
        changes = {}
        for field in ("bookings", "revenue"):
            if field in data and data[field] is not None:
                old = row[field]
                new = round(float(data[field]), 2) if field == "revenue" else int(data[field])
                if new < 0:
                    raise HTTPException(400, f"{field} negatif olamaz")
                if new != old:
                    row[field] = new
                    changes[field] = {"from": old, "to": new}
        if not changes:
            return {"ok": True, "unchanged": True}
        v["adjustments"].append({"period": period, "changes": changes, "by": user,
                                 "note": (data.get("note") or "")[:200], "at": _iso()})
        await db.forecast_versions.update_one({"id": version_id}, {"$set": {
            "rows": v["rows"], "adjustments": v["adjustments"]}})
        return {"ok": True, "row": row, "totals": _totals(v["rows"])}

    @router.post("/versions/{version_id}/lock")
    async def lock_version(version_id: str,
                           current_user: dict = Depends(require_roles(*STAFF))):
        v = await db.forecast_versions.find_one({"id": version_id}, {"_id": 0})
        if not v:
            raise HTTPException(404, "Sürüm bulunamadı")
        if v["status"] == "locked":
            return {"ok": True, "already": True}
        user = current_user.get("name") or current_user.get("email", "")
        await db.forecast_versions.update_one({"id": version_id}, {"$set": {
            "status": "locked", "locked_at": _iso(), "locked_by": user}})
        return {"ok": True, "status": "locked"}

    @router.post("/versions/{version_id}/comment")
    async def add_comment(version_id: str, data: Dict,
                          current_user: dict = Depends(require_roles(*STAFF))):
        text = (data.get("text") or "").strip()
        if not text:
            raise HTTPException(400, "Yorum metni gerekli")
        user = current_user.get("name") or current_user.get("email", "")
        comment = {"id": str(uuid.uuid4()), "by": user, "text": text[:500],
                   "period": data.get("period") or None, "at": _iso()}
        r = await db.forecast_versions.update_one({"id": version_id},
                                                  {"$push": {"comments": comment}})
        if not r.matched_count:
            raise HTTPException(404, "Sürüm bulunamadı")
        return {"ok": True, "comment": comment}

    @router.post("/versions/{version_id}/approve")
    async def approve(version_id: str,
                      current_user: dict = Depends(require_roles(*STAFF))):
        v = await db.forecast_versions.find_one({"id": version_id}, {"_id": 0})
        if not v:
            raise HTTPException(404, "Sürüm bulunamadı")
        user = current_user.get("name") or current_user.get("email", "")
        if any(a["by"] == user for a in v.get("approvals", [])):
            return {"ok": True, "already": True}
        await db.forecast_versions.update_one({"id": version_id}, {"$push": {
            "approvals": {"by": user, "role": current_user.get("role", ""), "at": _iso()}}})
        return {"ok": True}

    @router.delete("/versions/{version_id}")
    async def delete_version(version_id: str,
                             current_user: dict = Depends(require_roles(*STAFF))):
        v = await db.forecast_versions.find_one({"id": version_id}, {"_id": 0})
        if not v:
            raise HTTPException(404, "Sürüm bulunamadı")
        if v["status"] == "locked":
            raise HTTPException(400, "Kilitli sürüm silinemez")
        await db.forecast_versions.delete_one({"id": version_id})
        return {"ok": True}

    @router.get("/{property_id}/compare")
    async def compare(property_id: str, a: str, b: str,
                      current_user: dict = Depends(require_roles(*STAFF))):
        va = await db.forecast_versions.find_one({"id": a}, {"_id": 0})
        vb = await db.forecast_versions.find_one({"id": b}, {"_id": 0})
        if not va or not vb:
            raise HTTPException(404, "Sürüm bulunamadı")
        map_b = {r["period"]: r for r in vb["rows"]}
        rows = []
        for ra in va["rows"]:
            rb = map_b.get(ra["period"])
            if not rb:
                continue
            rows.append({"period": ra["period"], "label": ra["label"],
                         "a_revenue": ra["revenue"], "b_revenue": rb["revenue"],
                         "delta_revenue": round(rb["revenue"] - ra["revenue"], 2),
                         "a_bookings": ra["bookings"], "b_bookings": rb["bookings"],
                         "delta_bookings": rb["bookings"] - ra["bookings"]})
        ta, tb = _totals(va["rows"]), _totals(vb["rows"])
        return {"a": {"id": va["id"], "name": va["name"], "status": va["status"], "totals": ta},
                "b": {"id": vb["id"], "name": vb["name"], "status": vb["status"], "totals": tb},
                "delta": {"revenue": round(tb["revenue"] - ta["revenue"], 2),
                          "bookings": tb["bookings"] - ta["bookings"]},
                "rows": rows}

    return router
