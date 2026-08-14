"""Pazarlama Fırsat Radarı — IDeaS 'Marketing Optimization' paritesi.
Düşük talepli tarih pencerelerini bulur, kampanya önerisi + beklenen ROI üretir."""
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from typing import Dict


def create_marketing_radar_router(db, require_roles):
    router = APIRouter(prefix="/marketing-radar", tags=["marketing-radar"])
    ROLES = ("admin", "manager")

    @router.get("/{pid}")
    async def radar(pid: str, days: int = 60, _u: dict = Depends(require_roles(*ROLES))):
        from routes.revenue_ext.ml_pickup import _stay_counts
        from routes.distribution.push_history import resolve_rate
        cap = await db.rooms.count_documents({"property_id": pid}) or 20
        today = datetime.now(timezone.utc).date()
        occ_map = {}
        for i in range(1, min(days, 90) + 1):
            ds = (today + timedelta(days=i)).isoformat()
            otb = (await _stay_counts(db, pid, ds))["otb"]
            occ_map[ds] = {"otb": otb, "occ": round(otb / cap * 100, 1)}
        dow_avg = {}
        for ds, v in occ_map.items():
            d = datetime.strptime(ds, "%Y-%m-%d").weekday()
            dow_avg.setdefault(d, []).append(v["occ"])
        dow_avg = {k: sum(v) / len(v) for k, v in dow_avg.items()}
        low = []
        for ds, v in sorted(occ_map.items()):
            d = datetime.strptime(ds, "%Y-%m-%d").weekday()
            if v["occ"] < 40 and v["occ"] <= dow_avg.get(d, 50):
                low.append(ds)
        windows, cur = [], []
        for ds in low:
            if cur and (datetime.strptime(ds, "%Y-%m-%d").date() -
                        datetime.strptime(cur[-1], "%Y-%m-%d").date()).days == 1:
                cur.append(ds)
            else:
                if cur:
                    windows.append(cur)
                cur = [ds]
        if cur:
            windows.append(cur)
        measured = await db.promo_campaigns.find(
            {"property_id": pid, "measured": True}, {"_id": 0, "pickup_gain": 1}).to_list(200)
        avg_pickup = (sum(float(m.get("pickup_gain") or 0) for m in measured) / len(measured)) if measured else 2.5
        avg_pickup = max(avg_pickup, 1.0)
        out = []
        for w in windows:
            base, _src = await resolve_rate(db, pid, w[0])
            base = base or 100.0
            weekend = any(datetime.strptime(ds, "%Y-%m-%d").weekday() >= 5 for ds in w)
            avg_occ = round(sum(occ_map[ds]["occ"] for ds in w) / len(w), 1)
            est_roi = round(avg_pickup * base * 0.92 * len(w), 2)
            camp = ("Hafta sonu kaçamağı paketi: min 2 gece + geç çıkış — sosyal medya + e-posta"
                    if weekend else
                    "Üye fiyatı (CUG) %8 + kurumsal hedefli e-posta — ADR tabanı korunur")
            out.append({
                "start": w[0], "end": w[-1], "nights": len(w), "avg_occ": avg_occ,
                "dates": w, "suggested_campaign": camp, "weekend": weekend,
                "base_rate": round(base, 2), "expected_pickup_per_night": round(avg_pickup, 1),
                "est_revenue_roi": est_roi,
            })
        out.sort(key=lambda x: x["est_revenue_roi"], reverse=True)
        return {"property_id": pid, "scanned_days": len(occ_map), "capacity": cap,
                "windows": out[:10], "low_dates": len(low),
                "note": "ROI = beklenen pickup × baz fiyat × %92 (indirim sonrası) × gece sayısı. Pickup tahmini geçmiş kampanya ölçümlerinden."}

    @router.post("/{pid}/activate")
    async def activate(pid: str, body: Dict, current_user: dict = Depends(require_roles(*ROLES))):
        from routes.revenue_ext.ml_pickup import _stay_counts
        dates = body.get("dates") or []
        now = datetime.now(timezone.utc).isoformat()
        created = []
        for ds in dates[:14]:
            otb = (await _stay_counts(db, pid, ds))["otb"]
            await db.promo_campaigns.update_one(
                {"property_id": pid, "date": ds, "type": "uye_fence"},
                {"$set": {"property_id": pid, "date": ds, "type": "uye_fence",
                          "discount_pct": 8, "min_los": 2, "channel": "direct",
                          "status": "aktif", "applied_at": now, "otb_at_apply": otb,
                          "applied_by": current_user.get("email", ""),
                          "aciklama": "Pazarlama Fırsat Radarı — düşük talep penceresi kampanyası"}},
                upsert=True)
            created.append(ds)
        await db.notifications.insert_one({
            "id": str(uuid.uuid4()), "type": "info",
            "title": "Pazarlama kampanyası aktifleşti",
            "message": f"Fırsat Radarı: {len(created)} gece için fence'li kampanya açıldı ({created[0] if created else ''}…). Etki otomatik ölçülecek.",
            "category": "revenue", "target_user": "", "target_role": "manager",
            "link_to": "marketing-radar", "priority": "normal",
            "read": False, "created_by": "Fırsat Radarı", "created_at": now})
        return {"ok": True, "campaign_dates": created}

    return router
