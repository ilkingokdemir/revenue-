"""Beklenen Net OTB katmanı — rezervasyon başına iptal olasılığı (p_cancel) ve net doluluk.
Grup wash'ın münferit (transient) karşılığı. Fiyat motoru net doluluğu kullanır."""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends

LEAD_BUCKETS = [(0, 3, "0-3"), (4, 7, "4-7"), (8, 14, "8-14"), (15, 30, "15-30"), (31, 9999, "31+")]


def _lead_bucket(days: int) -> str:
    for lo, hi, name in LEAD_BUCKETS:
        if lo <= days <= hi:
            return name
    return "31+"


def _lead_days(b: dict) -> int:
    try:
        ci = datetime.strptime(b["check_in"], "%Y-%m-%d").date()
        cr = datetime.fromisoformat(str(b.get("created_at", "")).replace("Z", "")).date()
        return max((ci - cr).days, 0)
    except Exception:
        return 15


def _chan(b: dict) -> str:
    src = str(b.get("source") or b.get("channel") or "direct").lower()
    return "ota" if any(k in src for k in ("booking", "expedia", "airbnb", "ota", "agoda")) else "direct"


def _ref(b: dict) -> str:
    if b.get("refundable") is False or "nonref" in str(b.get("rate_plan", "")).lower():
        return "nonref"
    return "ref"


async def get_cancel_stats(db, pid: str) -> dict:
    """v2: lead-time × kanal × iade-edilebilirlik kırılımlı iptal oranları + kalibrasyon haritası."""
    since = (datetime.now(timezone.utc) - timedelta(days=365)).strftime("%Y-%m-%d")
    bks = await db.bookings.find(
        {"property_id": pid, "check_in": {"$gte": since}},
        {"_id": 0, "check_in": 1, "created_at": 1, "status": 1,
         "source": 1, "channel": 1, "refundable": 1, "rate_plan": 1}).to_list(10000)
    total = len(bks)
    cancelled = sum(1 for b in bks if b.get("status") in ("cancelled", "no_show"))
    global_rate = (cancelled + 1) / (total + 4) if total else 0.12
    buckets, combos = {}, {}
    for b in bks:
        k = _lead_bucket(_lead_days(b))
        st = buckets.setdefault(k, {"n": 0, "c": 0})
        st["n"] += 1
        st["c"] += 1 if b.get("status") in ("cancelled", "no_show") else 0
        ck = f"{k}|{_chan(b)}|{_ref(b)}"
        cs = combos.setdefault(ck, {"n": 0, "c": 0})
        cs["n"] += 1
        cs["c"] += 1 if b.get("status") in ("cancelled", "no_show") else 0
    rates = {k: round((st["c"] + global_rate * 10) / (st["n"] + 10), 4) for k, st in buckets.items()}
    combo_rates = {}
    for ck, cs in combos.items():
        base = rates.get(ck.split("|")[0], global_rate)
        combo_rates[ck] = round((cs["c"] + base * 8) / (cs["n"] + 8), 4)
    calib = await db.cancel_calibration.find_one({"property_id": pid}, {"_id": 0})
    return {"global_rate": round(global_rate, 4), "bucket_rates": rates,
            "combo_rates": combo_rates, "calibration": (calib or {}).get("mapping"),
            "sample": total, "cancelled": cancelled}


def _apply_calibration(mapping, p: float) -> float:
    if not mapping:
        return p
    for m in mapping:
        if m["lo"] <= p < m["hi"]:
            return round(m["actual"], 4)
    return p


def p_cancel_for(stats: dict, days_to_checkin: int, channel: str = None, refundable: str = None) -> float:
    """Kalan lead time + kanal + iade tipine göre iptal olasılığı; kalibrasyon haritası uygulanır."""
    bucket = _lead_bucket(max(days_to_checkin, 0))
    base = stats["bucket_rates"].get(bucket, stats["global_rate"])
    if channel and refundable:
        base = stats.get("combo_rates", {}).get(f"{bucket}|{channel}|{refundable}", base)
    if days_to_checkin <= 1:
        base = base * 0.35
    elif days_to_checkin <= 3:
        base = base * 0.6
    return _apply_calibration(stats.get("calibration"), round(base, 4))


async def compute_calibration(db, pid: str) -> dict:
    """K4: temporal validation (ilk %70 eğitim / son %30 test) + Brier skoru + binned kalibrasyon."""
    since = (datetime.now(timezone.utc) - timedelta(days=365)).strftime("%Y-%m-%d")
    bks = await db.bookings.find(
        {"property_id": pid, "check_in": {"$gte": since}},
        {"_id": 0, "check_in": 1, "created_at": 1, "status": 1,
         "source": 1, "channel": 1, "refundable": 1, "rate_plan": 1}).to_list(10000)
    bks.sort(key=lambda b: b.get("check_in", ""))
    if len(bks) < 50:
        return {"ok": False, "reason": f"Örneklem yetersiz ({len(bks)} < 50)"}
    split = int(len(bks) * 0.7)
    train, test = bks[:split], bks[split:]
    g = (sum(1 for b in train if b.get("status") in ("cancelled", "no_show")) + 1) / (len(train) + 4)
    tb = {}
    for b in train:
        k = _lead_bucket(_lead_days(b))
        st = tb.setdefault(k, {"n": 0, "c": 0})
        st["n"] += 1
        st["c"] += 1 if b.get("status") in ("cancelled", "no_show") else 0
    trates = {k: (st["c"] + g * 10) / (st["n"] + 10) for k, st in tb.items()}
    preds = []
    for b in test:
        p = trates.get(_lead_bucket(_lead_days(b)), g)
        y = 1 if b.get("status") in ("cancelled", "no_show") else 0
        preds.append((p, y))
    brier = round(sum((p - y) ** 2 for p, y in preds) / len(preds), 4)
    bins = [(0, 0.1), (0.1, 0.2), (0.2, 0.3), (0.3, 0.5), (0.5, 1.01)]
    mapping, table = [], []
    for lo, hi in bins:
        grp = [(p, y) for p, y in preds if lo <= p < hi]
        if len(grp) >= 5:
            pred_avg = round(sum(p for p, _ in grp) / len(grp), 4)
            actual = round(sum(y for _, y in grp) / len(grp), 4)
            mapping.append({"lo": lo, "hi": hi, "actual": actual})
            table.append({"bin": f"{lo:.1f}-{hi:.1f}", "n": len(grp),
                          "predicted_avg": pred_avg, "actual_rate": actual})
    now = datetime.now(timezone.utc).isoformat()
    await db.cancel_calibration.update_one(
        {"property_id": pid},
        {"$set": {"property_id": pid, "brier_score": brier, "mapping": mapping,
                  "table": table, "train_n": len(train), "test_n": len(test),
                  "calibrated_at": now}}, upsert=True)
    return {"ok": True, "brier_score": brier, "calibration_table": table,
            "train_n": len(train), "test_n": len(test), "calibrated_at": now,
            "note": "Brier: 0=mükemmel, 0.25=bilgisiz. Binned isotonic haritası p_cancel'e otomatik uygulanır. Temporal split: ilk %70 eğitim, son %30 test."}


async def expected_net_for_date(db, pid: str, date: str, stats: dict, total_rooms: int) -> dict:
    """Bir tarih için brüt OTB, beklenen iptal ve net doluluk."""
    bks = await db.bookings.find(
        {"property_id": pid, "check_in": {"$lte": date}, "check_out": {"$gt": date},
         "status": {"$nin": ["cancelled", "no_show"]}},
        {"_id": 0, "check_in": 1, "source": 1, "channel": 1,
         "refundable": 1, "rate_plan": 1}).to_list(3000)
    today = datetime.now(timezone.utc).date()
    exp_cancel = 0.0
    for b in bks:
        try:
            dtc = (datetime.strptime(b["check_in"], "%Y-%m-%d").date() - today).days
        except Exception:
            dtc = 15
        exp_cancel += p_cancel_for(stats, dtc, _chan(b), _ref(b))
    gross = len(bks)
    net = max(gross - exp_cancel, 0)
    return {"date": date, "gross_otb": gross, "expected_cancels": round(exp_cancel, 2),
            "net_otb": round(net, 2), "total_rooms": total_rooms,
            "gross_occupancy_pct": round(min(100, gross / total_rooms * 100), 1) if total_rooms else 0,
            "net_occupancy_pct": round(min(100, net / total_rooms * 100), 1) if total_rooms else 0}


def create_net_otb_router(db, require_roles):
    router = APIRouter(prefix="/net-otb", tags=["net-otb"])
    ROLES = ("admin", "manager")

    @router.get("/{pid}")
    async def net_otb(pid: str, days: int = 30, _u: dict = Depends(require_roles(*ROLES))):
        days = max(1, min(90, days))
        stats = await get_cancel_stats(db, pid)
        total_rooms = await db.rooms.count_documents({"property_id": pid}) or 20
        today = datetime.now(timezone.utc).date()
        rows = []
        for i in range(days):
            d = (today + timedelta(days=i)).isoformat()
            rows.append(await expected_net_for_date(db, pid, d, stats, total_rooms))
        return {"property_id": pid, "cancel_stats": stats, "rows": rows,
                "note": ("p_cancel: son 365 günün lead-time kovalı iptal oranları (Laplace düzeltmeli). "
                         "Check-in yaklaştıkça iptal olasılığı düşürülür. Fiyat motoru NET doluluğu kullanır — "
                         "brüt OTB yanıltıcıdır, beklenen iptal düşülür.")}

    @router.get("/{pid}/calibration")
    async def calibration_status(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        c = await db.cancel_calibration.find_one({"property_id": pid}, {"_id": 0})
        return c or {"property_id": pid, "calibrated_at": None,
                     "note": "Henüz kalibrasyon yok — 'Kalibre Et' ile başlatın. Robot her ay otomatik yeniler."}

    @router.post("/{pid}/calibrate")
    async def calibrate_now(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        return await compute_calibration(db, pid)

    return router
