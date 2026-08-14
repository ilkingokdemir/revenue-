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
