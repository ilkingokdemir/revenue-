"""K12 Esneklik Güç Analizi — log-log OLS ile tesis bazlı fiyat esnekliği ve agresiflik faktörü."""
import math
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends


def create_elasticity_router(db, require_roles):
    router = APIRouter(prefix="/elasticity", tags=["elasticity"])
    ROLES = ("admin", "manager")

    @router.get("/{pid}")
    async def measure(pid: str, window_days: int = 120, _u: dict = Depends(require_roles(*ROLES))):
        today = datetime.now(timezone.utc).date()
        window_days = max(30, min(365, window_days))
        start = (today - timedelta(days=window_days)).isoformat()
        bks = await db.bookings.find(
            {"property_id": pid, "status": {"$nin": ["cancelled", "no_show"]},
             "check_in": {"$gte": start, "$lte": today.isoformat()}},
            {"_id": 0, "check_in": 1, "check_out": 1, "total_price": 1}).to_list(5000)
        night_price, night_qty = {}, {}
        for b in bks:
            try:
                ci = datetime.strptime(b["check_in"], "%Y-%m-%d").date()
                co = datetime.strptime(b["check_out"], "%Y-%m-%d").date()
            except Exception:
                continue
            n = max((co - ci).days, 1)
            ppn = (b.get("total_price") or 0) / n
            if ppn <= 0:
                continue
            for i in range(n):
                d = ci + timedelta(days=i)
                if d > today:
                    break
                ds = d.isoformat()
                night_price.setdefault(ds, []).append(ppn)
                night_qty[ds] = night_qty.get(ds, 0) + 1
        points = [(sum(v) / len(v), night_qty[d]) for d, v in night_price.items() if night_qty.get(d)]
        sample = len(points)
        elasticity, r2 = None, 0.0
        if sample >= 10:
            xs = [math.log(p) for p, _q in points]
            ys = [math.log(q) for _p, q in points]
            xm, ym = sum(xs) / sample, sum(ys) / sample
            sxx = sum((x - xm) ** 2 for x in xs)
            sxy = sum((x - xm) * (y - ym) for x, y in zip(xs, ys))
            syy = sum((y - ym) ** 2 for y in ys)
            if sxx > 1e-9 and syy > 1e-9:
                b_ = sxy / sxx
                elasticity = round(b_, 3)
                r2 = round((sxy ** 2) / (sxx * syy), 3)
        e_abs = abs(elasticity) if (elasticity is not None and elasticity < 0) else 0.0
        if sample < 30 or r2 < 0.05 or elasticity is None:
            agg, verdict = 1.0, "Yetersiz/zayıf sinyal — nötr agresiflik (×1.0), varsayılan adım limitleri geçerli"
        elif e_abs >= 1.5:
            agg, verdict = 0.75, "Talep ÇOK esnek — fiyat artışları temkinli (×0.75): küçük zam bile talebi kaçırır"
        elif e_abs >= 1.0:
            agg, verdict = 0.9, "Talep esnek — öneri adımları hafif kısılır (×0.9)"
        elif e_abs >= 0.5:
            agg, verdict = 1.0, "Orta esneklik — standart agresiflik (×1.0)"
        else:
            agg, verdict = 1.2, "Talep esnek DEĞİL — fiyat gücü var, artışlar daha agresif (×1.2)"
        doc = {"property_id": pid, "elasticity": elasticity, "r2": r2, "sample_days": sample,
               "window_days": window_days, "aggressiveness": agg, "verdict": verdict,
               "computed_at": datetime.now(timezone.utc).isoformat()}
        await db.property_elasticity.update_one({"property_id": pid}, {"$set": doc}, upsert=True)
        month = today.isoformat()[:7]
        await db.elasticity_history.update_one(
            {"property_id": pid, "month": month},
            {"$set": {**doc, "month": month}}, upsert=True)
        return {**doc,
                "note": "log-log OLS: ln(satış) = a + e·ln(fiyat). e<0 normaldir; |e| büyüdükçe talep fiyata duyarlı. "
                        "Agresiflik faktörü AI fiyat önerilerinin adım büyüklüğünü otele göre ölçekler (7 gün geçerli)."}

    @router.get("/{pid}/history")
    async def history(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        rows = await db.elasticity_history.find(
            {"property_id": pid}, {"_id": 0}).sort("month", 1).to_list(36)
        return {"history": rows,
                "note": "Aylık esneklik trendi — |e| düşüyorsa fiyat gücü artıyor demektir."}

    return router
