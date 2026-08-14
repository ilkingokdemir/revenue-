"""
ML Pickup Tahmin Motoru — kullanıcının yüklediği eğitilmiş LightGBM modeli
(Antonio 2019 gerçek otel verisiyle eğitilmiş, 500 ağaç, 9 özellik).
T gün kala nihai satılan oda sayısını tahmin eder; robot bunu boş gece riski
ve fiyat penceresi kararlarında kullanır.
Özellikler: otb_now, pickup_last7, pickup_last14, T, dow, month, week, is_weekend, hotel_c
"""
from datetime import datetime, timezone, timedelta
import os

_BOOSTER = None
MODEL_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "models", "pickup_model.txt")


def _get_booster():
    global _BOOSTER
    if _BOOSTER is None:
        import lightgbm as lgb
        _BOOSTER = lgb.Booster(model_file=MODEL_PATH)
    return _BOOSTER


async def _stay_counts(db, pid: str, ds: str) -> dict:
    otb = 0
    d7 = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    d14 = (datetime.now(timezone.utc) - timedelta(days=14)).isoformat()
    p7 = p14 = 0
    async for b in db.bookings.find(
            {"property_id": pid, "status": {"$nin": ["cancelled"]},
             "check_in": {"$lte": ds}, "check_out": {"$gt": ds}},
            {"_id": 0, "rooms": 1, "created_at": 1}):
        r = int(b.get("rooms", 1) or 1)
        otb += r
        ca = b.get("created_at") or ""
        if ca >= d7:
            p7 += r
        if ca >= d14:
            p14 += r
    return {"otb": otb, "p7": p7, "p14": p14}


async def ml_pickup_forecast(db, pid: str, days: int = 30) -> dict:
    import numpy as np
    booster = _get_booster()
    days = max(4, min(days, 60))
    cap = await db.rooms.count_documents({"property_id": pid}) or 20
    # Ölçek transferi: model büyük otellerle eğitildi (OTB 2-317). Küçük oteli
    # ~100 odalı model uzayına ölçekleyip tahmini geri ölçeklendiriyoruz.
    k = 100.0 / cap if cap < 40 else 1.0
    today = datetime.now(timezone.utc).date()
    rows, feats, metas = [], [], []
    for i in range(3, days):
        d = today + timedelta(days=i)
        ds = d.isoformat()
        c = await _stay_counts(db, pid, ds)
        wd = d.weekday()
        feats.append([c["otb"] * k, c["p7"] * k, (c["p7"] + c["p14"]) * k, i, wd, d.month,
                      d.isocalendar()[1], 1 if wd >= 5 else 0, 0])
        metas.append((ds, i, c))
    if feats:
        preds = booster.predict(np.array(feats, dtype=float))
        for (ds, t, c), pred in zip(metas, preds):
            final_rooms = max(0.0, min(float(pred) / k, cap * 1.1))
            # Sağduyu tabanı: nihai, mevcut OTB'nin %85'inin altına düşemez (maks ~%15 wash)
            final_rooms = max(final_rooms, c["otb"] * 0.85)
            occ = round(final_rooms / cap * 100, 1)
            naive = min(c["otb"] + c["p7"], cap)
            rows.append({"date": ds, "days_out": t, "otb": c["otb"],
                         "pickup_last7": c["p7"],
                         "ml_final_rooms": round(final_rooms, 1),
                         "ml_final_occ_pct": occ,
                         "naive_final_rooms": naive,
                         "risk": "bos_gece" if occ < 50 else ("sicak" if occ >= 90 else "normal")})
    risky = [r["date"] for r in rows if r["risk"] == "bos_gece"]
    hot = [r["date"] for r in rows if r["risk"] == "sicak"]
    return {"property_id": pid, "capacity": cap, "days": rows,
            "empty_risk_dates": risky[:10], "hot_dates": hot[:10],
            "model": "LightGBM 500 ağaç (kullanıcı yüklemesi, Antonio 2019 verisiyle eğitilmiş)",
            "note": "Zekâ uzak ufukta kazandırır: uzak tarihlerdeki (T>14) tahminlere göre fiyat penceresi aç; "
                    "yakın ufukta guardrail istikrarı korur."}


async def log_ml_forecasts(db, pid: str) -> int:
    """Tahmin karnesi 1/2: bugünkü ML tahminlerini kaydet (sonradan gerçekleşenle kıyaslanır)."""
    try:
        f = await ml_pickup_forecast(db, pid, days=45)
    except Exception:
        return 0
    log_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    n = 0
    for r in f["days"]:
        await db.ml_forecast_log.update_one(
            {"property_id": pid, "stay_date": r["date"], "log_date": log_date},
            {"$set": {"property_id": pid, "stay_date": r["date"], "log_date": log_date,
                      "days_out": r["days_out"], "otb": r["otb"],
                      "predicted_final": r["ml_final_rooms"],
                      "logged_at": datetime.now(timezone.utc).isoformat()}},
            upsert=True)
        n += 1
    return n


async def score_forecasts(db, pid: str) -> dict:
    """Tahmin karnesi 2/2: geçmiş tahminleri gerçekleşenle kıyasla, ufuk bazlı MAPE karnesi tut."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    actual_cache = {}
    async for log in db.ml_forecast_log.find(
            {"property_id": pid, "stay_date": {"$lt": today}, "ape": {"$exists": False}},
            {"_id": 0, "stay_date": 1, "log_date": 1, "predicted_final": 1}).limit(500):
        sd = log["stay_date"]
        if sd not in actual_cache:
            actual = 0
            async for b in db.bookings.find(
                    {"property_id": pid, "status": {"$nin": ["cancelled", "no_show"]},
                     "check_in": {"$lte": sd}, "check_out": {"$gt": sd}}, {"_id": 0, "rooms": 1}):
                actual += int(b.get("rooms", 1) or 1)
            actual_cache[sd] = actual
        actual = actual_cache[sd]
        ape = round(abs(log["predicted_final"] - actual) / max(actual, 1) * 100, 1)
        await db.ml_forecast_log.update_one(
            {"property_id": pid, "stay_date": sd, "log_date": log["log_date"]},
            {"$set": {"actual_final": actual, "ape": ape}})
    bands = {"yakin_3_7": [], "orta_8_14": [], "uzak_15plus": []}
    cutoff = (datetime.now(timezone.utc) - timedelta(days=35)).strftime("%Y-%m-%d")
    async for log in db.ml_forecast_log.find(
            {"property_id": pid, "ape": {"$exists": True}, "stay_date": {"$gte": cutoff}},
            {"_id": 0, "days_out": 1, "ape": 1}):
        t = log["days_out"]
        key = "yakin_3_7" if t <= 7 else ("orta_8_14" if t <= 14 else "uzak_15plus")
        bands[key].append(log["ape"])
    band_stats = {k: {"mape": round(sum(v) / len(v), 1) if v else None, "n": len(v)}
                  for k, v in bands.items()}
    all_apes = [a for v in bands.values() for a in v]
    overall = round(sum(all_apes) / len(all_apes), 1) if all_apes else None
    card = {"property_id": pid, "overall_mape": overall, "bands": band_stats,
            "scored": len(all_apes), "updated_at": datetime.now(timezone.utc).isoformat(),
            "alert": bool(overall is not None and overall > 25 and len(all_apes) >= 10),
            "note": "APE = |tahmin - gerçekleşen| / gerçekleşen. Son 35 günün skorları; ufuk bandına göre kırılım."}
    await db.ml_forecast_scorecard.update_one({"property_id": pid}, {"$set": card}, upsert=True)
    return card


async def ml_pickup_summary_for_llm(db, pid: str) -> str:
    try:
        f = await ml_pickup_forecast(db, pid, days=16)
    except Exception:
        return ""
    if not f["days"]:
        return ""
    parts = ["\nML PICKUP TAHMİNİN (kendi eğitilmiş LightGBM organınla üretildi — bunlara dayan):"]
    if f["empty_risk_dates"]:
        parts.append(f"- BOŞ GECE RİSKİ (<%50 nihai doluluk tahmini): {', '.join(f['empty_risk_dates'][:5])}")
    if f["hot_dates"]:
        parts.append(f"- SICAK GÜNLER (≥%90 tahmini): {', '.join(f['hot_dates'][:5])} — fiyat artış penceresi")
    avg = round(sum(r["ml_final_occ_pct"] for r in f["days"]) / len(f["days"]), 1)
    parts.append(f"- 14 gün ortalama nihai doluluk tahmini: %{avg} (kapasite {f['capacity']} oda)")
    return "\n".join(parts)
