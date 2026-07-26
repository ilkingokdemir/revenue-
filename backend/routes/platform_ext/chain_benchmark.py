"""
Zincir Benchmark (Chain Benchmark) — tesisleri yan yana kıyaslar:
doluluk, ADR, RevPAR, misafir puanı, rezervasyon kalite skoru ve otomasyon
aktivitesinden 0-100 kompozit "Tesis Skoru" üretir; en iyi/en zayıf metrikleri
rozetler. Key Figures motorunu yeniden kullanır.
"""
from fastapi import APIRouter, Depends
from datetime import datetime, timezone, timedelta, date
from typing import Dict, List
import logging

from routes.pms.res_quality import scan_internal as rq_scan

logger = logging.getLogger(__name__)

METRICS = ["occupancy", "revpar", "review", "quality", "automation"]
WEIGHTS = {"occupancy": 0.30, "revpar": 0.30, "review": 0.20, "quality": 0.10, "automation": 0.10}
METRIC_LABELS = {"occupancy": "Doluluk", "revpar": "RevPAR", "review": "Misafir puanı",
                 "quality": "Rezervasyon kalitesi", "automation": "Otomasyon aktivitesi"}


def _norm(values: List[float]) -> List[float]:
    lo, hi = min(values), max(values)
    if hi - lo < 1e-9:
        return [50.0] * len(values)
    return [round((v - lo) / (hi - lo) * 100, 1) for v in values]


def create_chain_benchmark_router(db, require_roles, compute_kf):
    router = APIRouter(prefix="/chain")

    @router.get("/benchmark")
    async def benchmark(days: int = 30, active_only: bool = True,
                        current_user: dict = Depends(require_roles("admin", "manager"))):
        days = min(max(days, 7), 180)
        end = date.today() - timedelta(days=1)
        start = end - timedelta(days=days - 1)
        since_iso = datetime.now(timezone.utc) - timedelta(days=days)
        since = since_iso.isoformat()

        properties = await db.properties.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(100)
        rows = []
        for p in properties:
            pid = p["id"]
            kf = await compute_kf({"property_id": pid}, start, end, "staying")
            tiles = kf.get("tiles", {})
            occ = float(tiles.get("avg_occupancy_pct", 0) or 0)
            adr = float(tiles.get("avg_price_per_night", 0) or 0)
            revpar = round(adr * occ / 100, 2)

            reviews = await db.reviews.find(
                {"property_id": pid, "created_at": {"$gte": since}},
                {"_id": 0, "rating": 1}).to_list(500)
            ratings = [float(r.get("rating") or 0) for r in reviews if r.get("rating")]
            review_avg = round(sum(ratings) / len(ratings), 2) if ratings else 0

            try:
                rq = await rq_scan(db, pid, 14)
                quality = float(rq.get("quality_score", 100))
            except Exception:
                quality = 100.0

            auto_actions = 0
            auto_actions += await db.housekeeping_tasks.count_documents(
                {"property_id": pid, "auto_generated": True, "created_at": {"$gte": since}})
            auto_actions += await db.vcc_cards.count_documents(
                {"property_id": pid, "status": "charged", "charged_at": {"$gte": since}})
            auto_actions += await db.waitlist_entries.count_documents(
                {"property_id": pid, "offered_at": {"$gte": since}})
            auto_actions += await db.direct_conversion_offers.count_documents(
                {"property_id": pid, "created_at": {"$gte": since}})

            rows.append({
                "property_id": pid, "name": p.get("name", pid),
                "occupancy": occ, "adr": adr, "revpar": revpar,
                "total_revenue": float(tiles.get("total_revenue", 0) or 0),
                "nights_sold": tiles.get("nights_sold", 0),
                "review": review_avg, "review_count": len(ratings),
                "quality": quality, "automation": auto_actions,
                "cancellation_pct": float(tiles.get("cancellation_pct", 0) or 0),
            })

        if not rows:
            return {"days": days, "start": start.isoformat(), "end": end.isoformat(),
                    "properties": [], "chain": {}}

        if active_only:
            active = [r for r in rows if r["nights_sold"] or r["total_revenue"] or r["automation"]]
            if active:
                rows = active

        # normalize metrics → composite score
        norm_vals = {
            "occupancy": _norm([r["occupancy"] for r in rows]),
            "revpar": _norm([r["revpar"] for r in rows]),
            "review": _norm([r["review"] for r in rows]),
            "quality": _norm([r["quality"] for r in rows]),
            "automation": _norm([r["automation"] for r in rows]),
        }
        for i, r in enumerate(rows):
            r["score"] = round(sum(norm_vals[m][i] * WEIGHTS[m] for m in METRICS), 1)
            r["norm"] = {m: norm_vals[m][i] for m in METRICS}

        # badges: best / worst per metric (only meaningful when >1 property)
        for r in rows:
            r["badges"] = {"best": [], "worst": []}
        if len(rows) > 1:
            for m in METRICS:
                vals = [r[m] for r in rows]
                if max(vals) - min(vals) < 1e-9:
                    continue
                best_i = vals.index(max(vals))
                worst_i = vals.index(min(vals))
                rows[best_i]["badges"]["best"].append(m)
                rows[worst_i]["badges"]["worst"].append(m)

        rows.sort(key=lambda r: -r["score"])
        for i, r in enumerate(rows):
            r["rank"] = i + 1

        n = len(rows)
        chain = {
            "occupancy": round(sum(r["occupancy"] for r in rows) / n, 1),
            "adr": round(sum(r["adr"] for r in rows) / n, 2),
            "revpar": round(sum(r["revpar"] for r in rows) / n, 2),
            "total_revenue": round(sum(r["total_revenue"] for r in rows), 2),
            "review": round(sum(r["review"] for r in rows if r["review"]) / max(sum(1 for r in rows if r["review"]), 1), 2),
            "properties": n,
        }
        return {"days": days, "start": start.isoformat(), "end": end.isoformat(),
                "metric_labels": METRIC_LABELS, "properties": rows, "chain": chain}

    return router
