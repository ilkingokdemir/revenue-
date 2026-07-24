"""
Competitor Price Radar (iter 430) — daily engine that scans compset rates
(deterministic mock scanner until real scraper credentials arrive), compares
against our own rate per date and produces pricing opportunity findings.
"""
from fastapi import APIRouter, Depends
from datetime import datetime, timezone, timedelta, date
from typing import Dict
import hashlib
import logging
import statistics

from routes.platform_ext.automation_settings import get_params
from routes.distribution.push_history import resolve_rate

logger = logging.getLogger(__name__)


def _mock_comp_rate(comp_id: str, d: str, base: float) -> float:
    """Deterministic pseudo-rate per competitor+date (stable across runs)."""
    h = int(hashlib.md5(f"{comp_id}:{d}".encode()).hexdigest()[:8], 16)
    factor = 0.75 + (h % 1000) / 1000 * 0.6  # 0.75x - 1.35x
    return round(base * factor, 2)


def create_comp_radar_router(db, require_roles):
    router = APIRouter()

    async def _radar_core(property_id: str = "") -> dict:
        cfg = await get_params(db, "comp_radar",
                               {"days_ahead": 14, "threshold_pct": 10})
        days_ahead = int(cfg["days_ahead"])
        threshold = float(cfg["threshold_pct"]) / 100
        now = datetime.now(timezone.utc).isoformat()

        pids = [property_id] if property_id and property_id not in ("all", "") else \
            await db.compset.distinct("property_id")
        total_scans, findings_count = 0, 0
        for pid in pids:
            comps = await db.compset.find({"property_id": pid}, {"_id": 0}).to_list(50)
            if not comps:
                continue
            base, _ = await resolve_rate(db, pid, date.today().isoformat())
            await db.comp_radar_findings.delete_many({"property_id": pid})
            for i in range(days_ahead):
                d = (date.today() + timedelta(days=i)).isoformat()
                comp_rates = []
                for c in comps:
                    r = _mock_comp_rate(c["id"], d, base)
                    comp_rates.append(r)
                    await db.comp_rate_snapshots.update_one(
                        {"property_id": pid, "comp_id": c["id"], "date": d},
                        {"$set": {"property_id": pid, "comp_id": c["id"],
                                  "comp_name": c.get("name"), "date": d,
                                  "rate": r, "scanned_at": now, "source": "mock-scanner"}},
                        upsert=True)
                    total_scans += 1
                own, own_src = await resolve_rate(db, pid, d)
                median = round(statistics.median(comp_rates), 2)
                gap_pct = round((own - median) / median * 100, 1) if median else 0
                finding = None
                if own < median * (1 - threshold):
                    finding = {"type": "underpriced",
                               "message": f"{d}: fiyatınız (£{own:.0f}) rakip medyanının (£{median:.0f}) %{abs(gap_pct)} altında — £{median * (1 - threshold):.0f} seviyesine artış fırsatı"}
                elif own > median * (1 + threshold):
                    finding = {"type": "overpriced",
                               "message": f"{d}: fiyatınız (£{own:.0f}) rakip medyanının (£{median:.0f}) %{gap_pct} üstünde — doluluk riski, gözden geçirin"}
                if finding:
                    findings_count += 1
                    await db.comp_radar_findings.insert_one({
                        "property_id": pid, "date": d, "own_rate": own,
                        "own_rate_source": own_src, "comp_median": median,
                        "comp_count": len(comp_rates), "gap_pct": gap_pct,
                        **finding, "created_at": now})
        return {"ok": True, "properties": len(pids), "scans": total_scans,
                "findings": findings_count}

    @router.get("/comp-radar/{property_id}")
    async def radar(property_id: str, days: int = 14,
                    current_user: dict = Depends(require_roles("admin", "manager"))):
        pq: Dict = {} if property_id == "all" else {"property_id": property_id}
        findings = await db.comp_radar_findings.find(
            pq, {"_id": 0}).sort("date", 1).to_list(200)
        # chart series: own vs median per date
        dates = [(date.today() + timedelta(days=i)).isoformat() for i in range(int(days))]
        pid = property_id
        if pid == "all":
            pids = await db.compset.distinct("property_id")
            pid = pids[0] if pids else "default"
        series = []
        for d in dates:
            snaps = await db.comp_rate_snapshots.find(
                {"property_id": pid, "date": d}, {"_id": 0, "rate": 1}).to_list(50)
            median = round(statistics.median([s["rate"] for s in snaps]), 2) if snaps else None
            own, _ = await resolve_rate(db, pid, d)
            series.append({"date": d, "own": own, "comp_median": median})
        last_snap = await db.comp_rate_snapshots.find_one(
            {"property_id": pid}, {"_id": 0, "scanned_at": 1}, sort=[("scanned_at", -1)])
        under = sum(1 for f in findings if f["type"] == "underpriced")
        over = sum(1 for f in findings if f["type"] == "overpriced")
        return {"property_id": property_id, "chart_property": pid,
                "findings": findings, "series": series,
                "summary": {"underpriced": under, "overpriced": over,
                            "total": len(findings)},
                "last_scanned_at": (last_snap or {}).get("scanned_at")}

    @router.post("/comp-radar/scan")
    async def scan_now(data: Dict = None,
                       current_user: dict = Depends(require_roles("admin", "manager"))):
        return await _radar_core((data or {}).get("property_id", ""))

    router.run_comp_radar_internal = _radar_core
    return router
