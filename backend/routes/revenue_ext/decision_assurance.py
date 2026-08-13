"""
Decision Assurance / Kanıtlı Autopilot — "Üç bağımsız rapor" 1 numaralı önceliği.
Her fiyat kararı için:
  - P10/P50/P90 beklenen gelir bandı (aynı haftagünü son 8 haftanın satış dağılımından)
  - Readback: karar gerçekten uygulandı mı? (rate_overrides / karar statüsü kanıtı)
  - Gerçekleşen etki: konaklama tarihi geçtiyse fiili gelir vs P50 (etiket: GÖZLEMSEL —
    nedensellik iddia edilmez)

Endpoint (/api/decision-assurance/*):
- GET /{property_id}?days=45 → decisions[] + summary
"""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends


def _pct(sorted_vals, p):
    if not sorted_vals:
        return 0
    k = max(0, min(len(sorted_vals) - 1, int(round(p * (len(sorted_vals) - 1)))))
    return sorted_vals[k]


async def _dow_sold_distribution(db, pid: str, target_date: str):
    """Aynı haftagünü son 8 haftada satılan oda-gece dağılımı."""
    try:
        td = datetime.fromisoformat(target_date).date()
    except ValueError:
        return []
    samples = []
    for w in range(1, 9):
        d = td - timedelta(days=7 * w)
        iso = d.isoformat()
        cnt = 0
        async for b in db.bookings.find(
                {"property_id": pid, "status": {"$nin": ["cancelled"]},
                 "check_in": {"$lte": iso}, "check_out": {"$gt": iso}},
                {"_id": 0, "rooms": 1}):
            cnt += int(b.get("rooms", 1) or 1)
        samples.append(cnt)
    return sorted(samples)


def create_decision_assurance_router(db, require_roles):
    router = APIRouter(prefix="/decision-assurance", tags=["decision-assurance"])

    @router.get("/{property_id}")
    async def assurance(property_id: str, days: int = 45,
                        _: dict = Depends(require_roles("admin", "manager"))):
        days = max(7, min(days, 120))
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        today = datetime.now(timezone.utc).date().isoformat()

        raw = []
        async for d in db.ai_pricing_decisions.find(
                {"property_id": property_id, "decided_at": {"$gte": cutoff}}, {"_id": 0}):
            raw.append({
                "source": "ai_pricing", "decided_at": d.get("decided_at"),
                "target_date": d.get("date"), "room_type": d.get("room_type_name", ""),
                "prev_rate": d.get("prev_rate"), "new_rate": d.get("new_rate"),
                "delta_pct": d.get("delta_pct"), "status": d.get("status", ""),
            })
        async for e in db.pricing_explanations.find(
                {"property_id": property_id, "created_at": {"$gte": cutoff},
                 "decision": {"$in": ["accept", "override"]}}, {"_id": 0}):
            raw.append({
                "source": "pricing_explain", "decided_at": e.get("decision_at") or e.get("created_at"),
                "target_date": e.get("target_date"), "room_type": e.get("room_type", ""),
                "prev_rate": e.get("current_rate"),
                "new_rate": e.get("decision_rate") or e.get("proposed_rate"),
                "delta_pct": e.get("delta_pct"), "status": e.get("decision", ""),
            })
        raw.sort(key=lambda x: x.get("decided_at") or "", reverse=True)
        raw = raw[:40]

        dist_cache = {}
        decisions, applied_n, observed = [], 0, []
        for d in raw:
            td = d.get("target_date") or ""
            if td not in dist_cache:
                dist_cache[td] = await _dow_sold_distribution(db, property_id, td)
            dist = dist_cache[td]
            rate = float(d.get("new_rate") or 0)
            band = {"p10": round(_pct(dist, 0.1) * rate, 2),
                    "p50": round(_pct(dist, 0.5) * rate, 2),
                    "p90": round(_pct(dist, 0.9) * rate, 2)}

            applied = d.get("status") in ("accepted", "auto_applied", "accept", "override")
            evidence = f"karar statüsü: {d.get('status')}"
            if not applied and td:
                ovr = await db.rate_overrides.find_one(
                    {"property_id": property_id, "date": td,
                     "custom_rate": {"$gte": rate - 0.51, "$lte": rate + 0.51}},
                    {"_id": 0, "set_by": 1})
                if ovr:
                    applied, evidence = True, f"rate_override bulundu (set_by: {ovr.get('set_by')})"
            if applied:
                applied_n += 1

            impact = {"status": "pending", "label": "gözlemsel"}
            if td and td < today:
                actual = 0.0
                async for b in db.bookings.find(
                        {"property_id": property_id, "status": {"$nin": ["cancelled"]},
                         "check_in": {"$lte": td}, "check_out": {"$gt": td}},
                        {"_id": 0, "total_price": 1, "total": 1, "check_in": 1, "check_out": 1, "rooms": 1}):
                    try:
                        n = max((datetime.fromisoformat(b["check_out"]).date()
                                 - datetime.fromisoformat(b["check_in"]).date()).days, 1)
                        actual += float(b.get("total_price") or b.get("total") or 0) / n
                    except (ValueError, KeyError, TypeError):
                        continue
                delta = round(actual - band["p50"], 2)
                impact = {"status": "observed", "actual_revenue": round(actual, 2),
                          "expected_p50": band["p50"], "delta_vs_p50": delta, "label": "gözlemsel"}
                observed.append(delta)

            decisions.append({**d, "band": band,
                              "readback": {"applied": applied, "evidence": evidence},
                              "impact": impact})

        return {
            "property_id": property_id, "days": days,
            "summary": {
                "decisions": len(decisions),
                "applied_pct": round(applied_n / len(decisions) * 100, 1) if decisions else 0,
                "observed_count": len(observed),
                "observed_delta_total": round(sum(observed), 2),
                "impact_disclaimer": "Etki değerleri GÖZLEMSELDİR — kontrollü deney (A/B) yapılmadan nedensellik iddia edilmez.",
            },
            "decisions": decisions,
        }

    return router
