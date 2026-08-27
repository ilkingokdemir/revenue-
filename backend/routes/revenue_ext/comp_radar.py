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
                comp_entries = []
                for c in comps:
                    r = _mock_comp_rate(c["id"], d, base)
                    comp_entries.append({"comp_name": c.get("name"), "rate": r})
                    await db.comp_rate_snapshots.update_one(
                        {"property_id": pid, "comp_id": c["id"], "date": d},
                        {"$set": {"property_id": pid, "comp_id": c["id"],
                                  "comp_name": c.get("name"), "date": d,
                                  "rate": r, "scanned_at": now, "source": "mock-scanner"}},
                        upsert=True)
                    total_scans += 1
                own, own_src = await resolve_rate(db, pid, d)
                from routes.revenue_ext.comp_anomaly import clean_comp_entries
                comp_rates, excluded = await clean_comp_entries(db, pid, d, comp_entries)
                if not comp_rates:
                    continue
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
                        "comp_count": len(comp_rates), "anomalies_excluded": excluded,
                        **finding, "gap_pct": gap_pct, "created_at": now})
        return {"ok": True, "properties": len(pids), "scans": total_scans,
                "findings": findings_count}

    @router.get("/comp-radar/{property_id}")
    async def radar(property_id: str, days: int = 14,
                    current_user: dict = Depends(require_roles("admin", "manager"))):
        pq: Dict = {} if property_id == "all" else {"property_id": property_id}
        findings = await db.comp_radar_findings.find(
            pq, {"_id": 0}).sort("date", 1).to_list(200)
        cfg = await get_params(db, "comp_radar", {"days_ahead": 14, "threshold_pct": 10})
        thr = float(cfg["threshold_pct"]) / 100
        for f in findings:
            m = float(f["comp_median"])
            f["suggested_rate"] = round(m * (1 - thr) if f["type"] == "underpriced" else m * (1 + thr), 2)
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

    @router.post("/comp-radar/apply")
    async def apply_price(data: Dict,
                          current_user: dict = Depends(require_roles("admin", "manager"))):
        """1-Click Price Push: apply the radar-suggested rate for a date and
        push it to every connected OTA via the sync queue."""
        from fastapi import HTTPException
        from routes.integrations_pkg.sync_queue import process_due_tasks
        import uuid

        pid = (data or {}).get("property_id") or ""
        target_date = (data or {}).get("date") or ""
        if not target_date:
            raise HTTPException(400, "date zorunlu")
        fq = {"date": target_date}
        if pid and pid != "all":
            fq["property_id"] = pid
        finding = await db.comp_radar_findings.find_one(fq, {"_id": 0})
        if not finding:
            raise HTTPException(404, "Bulgu bulunamadı")
        if finding.get("applied"):
            raise HTTPException(409, "Bu bulgu için fiyat zaten uygulandı")

        cfg = await get_params(db, "comp_radar", {"days_ahead": 14, "threshold_pct": 10})
        threshold = float(cfg["threshold_pct"]) / 100
        median = float(finding["comp_median"])
        if finding["type"] == "underpriced":
            new_rate = round(median * (1 - threshold), 2)
        else:
            new_rate = round(median * (1 + threshold), 2)
        override = (data or {}).get("rate")
        if override:
            new_rate = round(float(override), 2)

        conns = await db.channel_connections.find(
            {"channel_id": {"$ne": "direct"}, "connected": True},
            {"_id": 0, "channel_id": 1, "name": 1}).to_list(50)
        conns = list({c["channel_id"]: c for c in conns}.values())
        if not conns:
            raise HTTPException(400, "Bağlı OTA kanalı yok")

        fpid = finding["property_id"]
        now = datetime.now(timezone.utc).isoformat()
        task_ids = []
        for c in conns:
            task = {"id": str(uuid.uuid4()), "property_id": fpid,
                    "channel_id": c["channel_id"], "kind": "rate",
                    "payload": {"date": target_date, "rate": new_rate,
                                "source": "comp_radar_apply"},
                    "status": "pending", "attempts": 0, "max_attempts": 6,
                    "next_retry_at": now, "error": None, "result": None,
                    "created_at": now,
                    "created_by": f"radar-apply:{current_user.get('name', '')}"}
            await db.sync_queue.insert_one(task)
            task_ids.append(task["id"])

        await process_due_tasks(db, max_tasks=len(task_ids) + 5)

        results = []
        succeeded = 0
        for tid in task_ids:
            t = await db.sync_queue.find_one(
                {"id": tid}, {"_id": 0, "channel_id": 1, "status": 1, "error": 1})
            if t.get("status") == "succeeded":
                succeeded += 1
            results.append(t)

        await db.comp_radar_findings.update_one(
            {"property_id": fpid, "date": target_date},
            {"$set": {"applied": True, "applied_rate": new_rate,
                      "applied_at": now,
                      "applied_by": current_user.get("name", ""),
                      "push_results": results}})

        return {"ok": succeeded > 0, "date": target_date,
                "old_rate": finding["own_rate"], "new_rate": new_rate,
                "channels_total": len(task_ids), "channels_succeeded": succeeded,
                "results": results}

    router.run_comp_radar_internal = _radar_core
    return router
