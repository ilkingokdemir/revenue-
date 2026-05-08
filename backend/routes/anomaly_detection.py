"""
AI Anomaly Detection — statistical spike/drop detection on daily revenue/occupancy/bookings/ADR
with optional GPT-5.2 natural-language explanation via EMERGENT_LLM_KEY.

Approach:
  Build a daily time-series for last 120 days.
  For each day, rolling window (prev 30 days): compute mean + std.
  z = (value - mean) / std. Flag |z| > 2.0 as anomaly.
  Tier: |z| > 3 = severe, >2 = moderate.

Endpoints:
  GET /anomaly/scan/{property_id}?days=60  — aggregated anomaly feed across metrics
  GET /anomaly/timeseries/{property_id}?metric=revenue&days=90 — chart-ready series
  POST /anomaly/explain {date, metric, property_id} — LLM root-cause hypothesis
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from datetime import datetime, timezone, timedelta, date
from typing import Optional, List
import statistics
import os
import logging

logger = logging.getLogger(__name__)


class ExplainReq(BaseModel):
    property_id: str
    date: str       # YYYY-MM-DD
    metric: str     # revenue | bookings | occupancy | adr
    value: float
    z: float


def _severity(z: float) -> str:
    az = abs(z)
    if az >= 3.0:
        return "severe"
    if az >= 2.0:
        return "moderate"
    return "normal"


async def _daily_series(db, property_id: str, days: int = 120):
    """Build a daily metrics series for the last `days` days."""
    today = date.today()
    start = today - timedelta(days=days)
    # All bookings with overlap window [start-30, today]
    bks = await db.bookings.find({
        "property_id": property_id,
        "check_in": {"$lte": today.isoformat()},
        "check_out": {"$gte": (start - timedelta(days=30)).isoformat()},
        "status": {"$ne": "cancelled"},
    }, {"_id": 0, "check_in": 1, "check_out": 1, "total_price": 1, "nights": 1,
        "status": 1, "booking_date": 1, "created_at": 1}).to_list(5000)

    # Count cancelled for ratio
    cancelled = await db.bookings.find({
        "property_id": property_id,
        "created_at": {"$gte": (start - timedelta(days=30)).isoformat()},
        "status": "cancelled",
    }, {"_id": 0, "created_at": 1}).to_list(5000)

    rooms_count = max(await db.rooms.count_documents({"property_id": property_id}), 1)

    out = []
    for i in range(days + 1):
        d = start + timedelta(days=i)
        dstr = d.isoformat()
        # OTB occupants for d
        otb = 0
        day_revenue = 0.0
        for b in bks:
            ci = (b.get("check_in") or "")[:10]
            co = (b.get("check_out") or "")[:10]
            if ci and co and ci <= dstr < co:
                otb += 1
                nights = max(1, b.get("nights") or 1)
                day_revenue += float(b.get("total_price") or 0) / nights

        # New bookings created today
        new_bk = 0
        for b in bks:
            cd = (b.get("booking_date") or b.get("created_at") or "")[:10]
            if cd == dstr:
                new_bk += 1
        new_cancel = sum(1 for c in cancelled if (c.get("created_at") or "")[:10] == dstr)

        occ = min(100, round(otb / rooms_count * 100, 1))
        adr = round(day_revenue / otb, 2) if otb else 0

        out.append({
            "date": dstr,
            "revenue": round(day_revenue, 2),
            "bookings": new_bk,
            "occupancy": occ,
            "adr": adr,
            "cancellations": new_cancel,
            "dow": d.weekday(),
        })
    return out


def _detect_anomalies(series: list, metric: str, window: int = 30, z_threshold: float = 2.0):
    """Return list of anomaly dicts for the metric."""
    anomalies = []
    for i in range(len(series)):
        if i < window:
            continue
        window_vals = [series[j][metric] for j in range(i - window, i)]
        # Filter zeros for metrics that naturally have zero days (optional)
        if not any(window_vals):
            continue
        try:
            mu = statistics.mean(window_vals)
            sigma = statistics.stdev(window_vals) if len(window_vals) > 1 else 0
        except statistics.StatisticsError:
            continue
        if sigma == 0:
            continue
        val = series[i][metric]
        z = (val - mu) / sigma
        if abs(z) >= z_threshold:
            anomalies.append({
                "date": series[i]["date"],
                "metric": metric,
                "value": val,
                "mean": round(mu, 2),
                "std": round(sigma, 2),
                "z": round(z, 2),
                "direction": "spike" if z > 0 else "drop",
                "severity": _severity(z),
            })
    return anomalies


def create_anomaly_router(db, require_roles, LlmChat=None, UserMessage=None):
    router = APIRouter()

    @router.get("/anomaly/scan/{property_id}")
    async def scan(property_id: str, days: int = 60,
                   current_user: dict = Depends(require_roles("admin", "manager"))):
        if days < 14 or days > 365:
            raise HTTPException(400, "days must be 14..365")
        series = await _daily_series(db, property_id, days + 30)
        # slice out last `days` for flagging
        all_anoms = []
        for metric in ("revenue", "bookings", "occupancy", "adr", "cancellations"):
            all_anoms.extend(_detect_anomalies(series, metric))
        # Only keep anomalies in the last `days` window
        cutoff = (date.today() - timedelta(days=days)).isoformat()
        filtered = [a for a in all_anoms if a["date"] >= cutoff]
        # Sort by date desc, severity weight
        sev_order = {"severe": 0, "moderate": 1}
        filtered.sort(key=lambda a: (a["date"], sev_order.get(a["severity"], 2)), reverse=True)

        by_metric = {}
        by_severity = {"severe": 0, "moderate": 0}
        for a in filtered:
            by_metric[a["metric"]] = by_metric.get(a["metric"], 0) + 1
            by_severity[a["severity"]] = by_severity.get(a["severity"], 0) + 1

        return {
            "property_id": property_id,
            "days": days,
            "total": len(filtered),
            "by_metric": by_metric,
            "by_severity": by_severity,
            "anomalies": filtered[:200],
        }

    @router.get("/anomaly/timeseries/{property_id}")
    async def timeseries(property_id: str, metric: str = "revenue", days: int = 90,
                         current_user: dict = Depends(require_roles("admin", "manager"))):
        if metric not in ("revenue", "bookings", "occupancy", "adr", "cancellations"):
            raise HTTPException(400, f"Unsupported metric: {metric}")
        if days < 14 or days > 365:
            raise HTTPException(400, "days must be 14..365")
        series = await _daily_series(db, property_id, days + 30)
        anoms = _detect_anomalies(series, metric)
        anom_dates = {a["date"]: a for a in anoms}

        cutoff = (date.today() - timedelta(days=days)).isoformat()
        points = []
        for pt in series:
            if pt["date"] < cutoff:
                continue
            a = anom_dates.get(pt["date"])
            points.append({
                "date": pt["date"],
                "value": pt[metric],
                "is_anomaly": bool(a),
                "severity": a["severity"] if a else None,
                "z": a["z"] if a else None,
                "direction": a["direction"] if a else None,
            })

        # Compute mean/std of the window for ref bands
        vals = [p["value"] for p in points if p["value"] > 0]
        mu = round(statistics.mean(vals), 2) if vals else 0
        sigma = round(statistics.stdev(vals), 2) if len(vals) > 1 else 0

        return {
            "property_id": property_id,
            "metric": metric,
            "days": days,
            "points": points,
            "mean": mu,
            "std": sigma,
            "anomaly_count": sum(1 for p in points if p["is_anomaly"]),
        }

    @router.post("/anomaly/explain")
    async def explain(req: ExplainReq,
                      current_user: dict = Depends(require_roles("admin", "manager"))):
        """
        Use GPT-5.2 to generate a natural-language root-cause hypothesis.
        Falls back to a heuristic string if EMERGENT_LLM_KEY missing.
        """
        heuristic = _heuristic_explain(req)
        llm_key = os.environ.get("EMERGENT_LLM_KEY", "")
        if not llm_key or LlmChat is None or UserMessage is None:
            return {"source": "heuristic", "hypothesis": heuristic, "actions": _suggest_actions(req)}

        try:
            import uuid as _uuid
            d = datetime.strptime(req.date, "%Y-%m-%d").date()
            dow = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][d.weekday()]
            system = (
                "You are a hotel revenue analyst. Provide a SHORT (2-3 sentence) natural-language "
                "root-cause hypothesis for a metric anomaly. Be specific and actionable. Respond in Turkish."
            )
            prompt = (
                f"Property {req.property_id} had a {req.metric} anomaly on {req.date} ({dow}).\n"
                f"Observed value: {req.value}\n"
                f"Z-score: {req.z}\n"
                f"Direction: {'spike' if req.z > 0 else 'drop'}\n\n"
                "In 2-3 sentences: what likely caused this and what should we do?"
            )
            chat = LlmChat(
                api_key=llm_key,
                session_id=f"anomaly-{_uuid.uuid4()}",
                system_message=system,
            ).with_model("openai", "gpt-5.2")
            resp = await chat.send_message(UserMessage(text=prompt))
            text = str(resp).strip() if resp else heuristic
            return {"source": "llm", "hypothesis": text, "actions": _suggest_actions(req)}
        except Exception as e:
            logger.warning(f"LLM explain failed, falling back to heuristic: {e}")
            return {"source": "heuristic_fallback", "hypothesis": heuristic, "actions": _suggest_actions(req)}

    return router


def _heuristic_explain(req: ExplainReq) -> str:
    direction = "yukarı" if req.z > 0 else "aşağı"
    sev = _severity(req.z)
    sev_tr = {"severe": "ciddi", "moderate": "orta"}[sev]
    metric_tr = {
        "revenue": "gelir",
        "bookings": "yeni rezervasyon",
        "occupancy": "doluluk",
        "adr": "ortalama gecelik fiyat",
        "cancellations": "iptal sayısı",
    }.get(req.metric, req.metric)

    if req.metric == "cancellations" and req.z > 0:
        return (
            f"{req.date} tarihinde iptaller {sev_tr} şekilde arttı (z={req.z}). "
            "Olası sebepler: Bir OTA kampanyası çıkışı, yüksek no-show, kredi kartı doğrulama hataları, "
            "veya politika değişikliği. Kanal ve no-show kayıtlarını inceleyin."
        )
    if req.z > 0:
        return (
            f"{req.date} tarihinde {metric_tr} {sev_tr} şekilde {direction} yönde saptı (z={req.z}). "
            "Olası sebepler: Yerel etkinlik, tatil, başarılı pazarlama kampanyası veya OTA öne çıkarması. "
            "Fırsatı yakalamak için kapasiteyi ve fiyatı optimize edin."
        )
    return (
        f"{req.date} tarihinde {metric_tr} {sev_tr} şekilde {direction} yönde saptı (z={req.z}). "
        "Olası sebepler: Hafta sonu düşüşü, kötü hava, rakip kampanyası, OTA parity ihlali veya review krizi. "
        "Parity kontrolü + review sentiment + local event takvimini inceleyin."
    )


def _suggest_actions(req: ExplainReq) -> list:
    if req.metric == "revenue" and req.z < 0:
        return ["Rate parity kontrolü", "Son 7 gün yorumları incele", "Pickup eğrisi sapması ara"]
    if req.metric == "bookings" and req.z > 0:
        return ["Stop-sell ihtimali kontrol et", "Ek staff planla", "Dinamik fiyatlamayı hızlandır"]
    if req.metric == "cancellations" and req.z > 0:
        return ["İptal edilen rezervasyonları grupla", "OTA kanal bazlı segment", "Ödeme hatalarını kontrol et"]
    if req.metric == "occupancy" and req.z < 0:
        return ["Flash sale kampanyası başlat", "OTA lead-time fiyat indirimi", "Walk-in oran artır"]
    return ["Veriyi segmentle", "Karşılaştırma için benzer güne bak", "Operasyon ekibiyle paylaş"]
