"""Robot Güven Merkezi — guardrail config/ihlal logu, öneri kabul oranı raporu, shadow mode."""
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException


async def run_shadow_snapshot(db, pid: str) -> dict:
    """Robot önerilerini push ETMEDEN kaydeder — otelin gerçek fiyatıyla kıyas için."""
    import routes.revenue_ext.ai_pricing_engine as eng
    builder = getattr(eng, "BUILD_SUGGESTIONS", None)
    if builder is None:
        raise HTTPException(500, "Fiyat motoru henüz başlatılmadı")
    payload = await builder(pid, 30, use_llm=False)
    today = datetime.now(timezone.utc).date().isoformat()
    n = 0
    for s in payload.get("suggestions", []):
        human = float(s.get("current_rate") or 0)
        robot = float(s.get("suggested_rate") or 0)
        diff_pct = round((robot - human) / human * 100, 1) if human else None
        await db.shadow_log.update_one(
            {"property_id": pid, "snapshot_date": today, "date": s["date"],
             "room_type_id": s.get("room_type_id", "")},
            {"$set": {"property_id": pid, "snapshot_date": today, "date": s["date"],
                      "room_type_id": s.get("room_type_id", ""),
                      "robot_rate": robot, "human_rate": human, "diff_pct": diff_pct,
                      "occupancy_pct": s.get("occupancy_pct"),
                      "rationale": s.get("rationale"),
                      "created_at": datetime.now(timezone.utc).isoformat()}},
            upsert=True)
        n += 1
    return {"snapshot_date": today, "recorded": n}


def create_trust_center_router(db, require_roles):
    router = APIRouter(tags=["trust-center"])
    ROLES = ("admin", "manager")

    # ---------- G1: Guardrail config + ihlal logu ----------
    @router.get("/guardrails/{pid}/config")
    async def get_gr_config(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        g = await db.guardrail_config.find_one({"property_id": pid}, {"_id": 0}) or {}
        return {"property_id": pid,
                "max_step_pct": float(g.get("max_step_pct", 15)),
                "daily_push_limit": int(g.get("daily_push_limit", 50))}

    @router.put("/guardrails/{pid}/config")
    async def put_gr_config(pid: str, data: dict, _u: dict = Depends(require_roles(*ROLES))):
        upd = {"property_id": pid,
               "max_step_pct": max(1.0, min(50.0, float(data.get("max_step_pct", 15)))),
               "daily_push_limit": max(1, min(500, int(data.get("daily_push_limit", 50)))),
               "updated_at": datetime.now(timezone.utc).isoformat()}
        await db.guardrail_config.update_one({"property_id": pid}, {"$set": upd}, upsert=True)
        return {"ok": True, **{k: upd[k] for k in ("max_step_pct", "daily_push_limit")}}

    @router.get("/guardrails/{pid}/violations")
    async def violations(pid: str, limit: int = 50, _u: dict = Depends(require_roles(*ROLES))):
        rows = await db.guardrail_violations.find(
            {"property_id": pid}, {"_id": 0}).sort("created_at", -1).to_list(min(limit, 200))
        today_start = datetime.now(timezone.utc).strftime("%Y-%m-%dT00:00:00")
        pushed_today = await db.ai_pricing_decisions.count_documents({
            "property_id": pid, "decided_at": {"$gte": today_start},
            "status": {"$in": ["accepted", "auto-applied"]}})
        return {"violations": rows, "pushed_today": pushed_today}

    # ---------- G2: Öneri kabul oranı raporu ----------
    @router.get("/rms-acceptance/{pid}/report")
    async def acceptance_report(pid: str, weeks: int = 8, _u: dict = Depends(require_roles(*ROLES))):
        weeks = max(2, min(26, weeks))
        since = (datetime.now(timezone.utc) - timedelta(weeks=weeks)).isoformat()
        decs = await db.ai_pricing_decisions.find(
            {"property_id": pid, "decided_at": {"$gte": since}},
            {"_id": 0, "status": 1, "decided_at": 1, "reason": 1}).to_list(10000)
        weekly, reasons = {}, {}
        acc_total, rej_total, auto_total = 0, 0, 0
        for d in decs:
            try:
                wk = datetime.fromisoformat(d["decided_at"].replace("Z", "")).strftime("%G-W%V")
            except Exception:
                continue
            w = weekly.setdefault(wk, {"week": wk, "accepted": 0, "rejected": 0, "auto_applied": 0})
            st = d.get("status")
            if st == "accepted":
                w["accepted"] += 1
                acc_total += 1
            elif st == "auto-applied":
                w["auto_applied"] += 1
                auto_total += 1
            elif st == "rejected":
                w["rejected"] += 1
                rej_total += 1
                reason = (d.get("reason") or "belirtilmedi").strip()[:60]
                reasons[reason] = reasons.get(reason, 0) + 1
        out = sorted(weekly.values(), key=lambda x: x["week"])
        for w in out:
            decided = w["accepted"] + w["auto_applied"] + w["rejected"]
            w["acceptance_rate_pct"] = round((w["accepted"] + w["auto_applied"]) / decided * 100, 1) if decided else None
        decided_all = acc_total + auto_total + rej_total
        return {"property_id": pid, "weeks": out,
                "reasons": sorted([{"reason": k, "count": v} for k, v in reasons.items()],
                                  key=lambda x: -x["count"])[:10],
                "total_accepted": acc_total, "total_auto_applied": auto_total,
                "total_rejected": rej_total,
                "overall_acceptance_pct": round((acc_total + auto_total) / decided_all * 100, 1) if decided_all else None,
                "target_pct": 70,
                "note": "Hedef kabul oranı ≥%70. Red nedenleri modelin kör nokta haritasıdır — etiketli veri olarak saklanır."}

    # ---------- G6: Shadow Mode ----------
    @router.get("/shadow-mode/{pid}/status")
    async def shadow_status(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        s = await db.shadow_mode.find_one({"property_id": pid}, {"_id": 0}) or {}
        snaps = await db.shadow_log.distinct("snapshot_date", {"property_id": pid})
        return {"property_id": pid, "active": bool(s.get("active")),
                "started_at": s.get("started_at"), "snapshot_days": len(snaps)}

    @router.post("/shadow-mode/{pid}/start")
    async def shadow_start(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        await db.shadow_mode.update_one(
            {"property_id": pid},
            {"$set": {"property_id": pid, "active": True,
                      "started_at": datetime.now(timezone.utc).isoformat(),
                      "started_by": _u.get("name", "")}}, upsert=True)
        return {"ok": True, "active": True,
                "note": "Shadow mode AÇIK: robot her gün önerir ama HİÇBİR fiyat push edilmez. 4 hafta sonunda kıyas raporunu inceleyin."}

    @router.post("/shadow-mode/{pid}/stop")
    async def shadow_stop(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        await db.shadow_mode.update_one({"property_id": pid}, {"$set": {"active": False}})
        return {"ok": True, "active": False}

    @router.post("/shadow-mode/{pid}/snapshot")
    async def shadow_snapshot(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        return {"ok": True, **(await run_shadow_snapshot(db, pid))}

    @router.get("/shadow-mode/{pid}/report")
    async def shadow_report(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        rows = await db.shadow_log.find(
            {"property_id": pid, "diff_pct": {"$ne": None}}, {"_id": 0}).to_list(20000)
        if not rows:
            return {"property_id": pid, "samples": 0, "weeks": [],
                    "note": "Henüz shadow verisi yok — shadow mode'u başlatın veya manuel snapshot alın."}
        diffs = [r["diff_pct"] for r in rows]
        agree = sum(1 for d in diffs if abs(d) <= 5)
        higher = sum(1 for d in diffs if d > 5)
        lower = sum(1 for d in diffs if d < -5)
        weekly = {}
        for r in rows:
            wk = datetime.strptime(r["snapshot_date"], "%Y-%m-%d").strftime("%G-W%V")
            w = weekly.setdefault(wk, {"week": wk, "n": 0, "sum_diff": 0.0, "agree": 0})
            w["n"] += 1
            w["sum_diff"] += r["diff_pct"]
            w["agree"] += 1 if abs(r["diff_pct"]) <= 5 else 0
        out = []
        for w in sorted(weekly.values(), key=lambda x: x["week"]):
            out.append({"week": w["week"], "samples": w["n"],
                        "avg_diff_pct": round(w["sum_diff"] / w["n"], 1),
                        "agreement_pct": round(w["agree"] / w["n"] * 100, 1)})
        snaps = sorted({r["snapshot_date"] for r in rows})
        return {"property_id": pid, "samples": len(rows),
                "snapshot_days": len(snaps), "first_snapshot": snaps[0], "last_snapshot": snaps[-1],
                "avg_diff_pct": round(sum(diffs) / len(diffs), 1),
                "agreement_pct": round(agree / len(diffs) * 100, 1),
                "robot_higher_pct": round(higher / len(diffs) * 100, 1),
                "robot_lower_pct": round(lower / len(diffs) * 100, 1),
                "weeks": out,
                "note": "Uyum = |fark| ≤ %5. Robot önerisi vs otelin gerçek fiyatı — 4 haftalık pilot güven inşası."}

    return router
