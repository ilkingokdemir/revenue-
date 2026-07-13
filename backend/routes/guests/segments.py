"""
Guest Segmentation Engine (iter 416) — auto-classifies guests into segments
(VIP, loyal, family, business, risky, new, standard) and lets each autopilot
motor target segments differently via a strategy matrix.
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone
from typing import Dict
import logging

logger = logging.getLogger(__name__)

SEGMENTS = {
    "vip": {"label": "VIP", "description": "Yüksek harcama veya VIP işaretli misafirler", "color": "amber"},
    "riskli": {"label": "Riskli", "description": "No-show / iptal / chargeback geçmişi yüksek", "color": "rose"},
    "sadik": {"label": "Sadık", "description": "3+ tamamlanmış konaklama", "color": "emerald"},
    "aile": {"label": "Aile", "description": "Ortalama 3+ kişilik rezervasyonlar", "color": "sky"},
    "is": {"label": "İş", "description": "Hafta içi kısa konaklama ağırlıklı", "color": "violet"},
    "yeni": {"label": "Yeni", "description": "İlk konaklamasında veya henüz konaklamamış", "color": "cyan"},
    "standart": {"label": "Standart", "description": "Diğer tüm misafirler", "color": "stone"},
}

MOTORS = ["cancel_save", "upsell_autopilot", "deposit_autopilot", "email_nudge"]

SEGMENT_OFFER_PROFILES = {
    "vip": {
        "greeting": "Değerli VIP misafirimiz",
        "intro": "Sizin gibi seçkin bir misafiri yeniden ağırlamak bizim için ayrıcalık. Konaklamanız için özel olarak ayırdığımız teklif:",
        "closing": "VIP misafirimiz olarak bu teklifte önceliğiniz garanti altındadır.",
        "category_boost": {"room_upgrade": 15, "spa": 10},
    },
    "sadik": {
        "greeting": "Sevgili sadık misafirimiz",
        "intro": "Bizi yeniden tercih ettiğiniz için teşekkürler! Sadakatinize küçük bir jest olarak bu teklifi hazırladık:",
        "closing": "Tekrar aramızda olmanız bizim için çok değerli.",
        "category_boost": {"late_checkout": 10, "breakfast": 5},
    },
    "aile": {
        "greeting": "Merhaba",
        "intro": "Aileniz için konforlu bir konaklama olsun istedik. Çocuklarınızla birlikte keyif alacağınız teklif:",
        "closing": "Ailecek harika bir konaklama dileriz!",
        "category_boost": {"breakfast": 15, "transport": 10},
    },
    "is": {
        "greeting": "Merhaba",
        "intro": "Yoğun programınıza uyum sağlayacak, iş seyahatinizi kolaylaştıran bir teklif hazırladık:",
        "closing": "Verimli ve konforlu bir konaklama dileriz.",
        "category_boost": {"late_checkout": 15, "breakfast": 10},
    },
    "yeni": {
        "greeting": "Hoş geldiniz",
        "intro": "İlk konaklamanızı unutulmaz kılmak istiyoruz. Size özel karşılama teklifi:",
        "closing": "Umarız ilk konaklamanız uzun bir dostluğun başlangıcı olur.",
        "category_boost": {"breakfast": 5},
    },
}


def apply_segment_boost(scores: Dict, segment: str):
    """Returns (boosted_scores, top_cat, top_score) with segment category boosts."""
    profile = SEGMENT_OFFER_PROFILES.get(segment or "")
    boosted = dict(scores)
    if profile:
        for cat, boost in profile["category_boost"].items():
            if cat in boosted and boosted[cat] > 0:
                boosted[cat] = min(100, boosted[cat] + boost)
    top = max(boosted, key=boosted.get)
    return boosted, top, boosted[top]

DEFAULT_STRATEGY = {
    "vip":      {"cancel_save": False, "upsell_autopilot": True,  "deposit_autopilot": False, "email_nudge": True},
    "riskli":   {"cancel_save": True,  "upsell_autopilot": False, "deposit_autopilot": True,  "email_nudge": False},
    "sadik":    {"cancel_save": True,  "upsell_autopilot": True,  "deposit_autopilot": False, "email_nudge": True},
    "aile":     {"cancel_save": True,  "upsell_autopilot": True,  "deposit_autopilot": True,  "email_nudge": True},
    "is":       {"cancel_save": True,  "upsell_autopilot": True,  "deposit_autopilot": True,  "email_nudge": True},
    "yeni":     {"cancel_save": True,  "upsell_autopilot": True,  "deposit_autopilot": True,  "email_nudge": True},
    "standart": {"cancel_save": True,  "upsell_autopilot": True,  "deposit_autopilot": True,  "email_nudge": True},
}


async def segment_allows(db, guest_email: str, motor: str) -> bool:
    """Motors call this to check if the guest's segment permits this autopilot."""
    email = (guest_email or "").lower()
    if not email:
        return True
    g = await db.guest_profiles.find_one({"email": email}, {"_id": 0, "segment": 1})
    seg = (g or {}).get("segment") or "standart"
    saved = await db.segment_strategies.find_one({"segment": seg}, {"_id": 0}) or {}
    strat = {**DEFAULT_STRATEGY.get(seg, {}), **{k: v for k, v in saved.items() if k in MOTORS}}
    return bool(strat.get(motor, True))


def create_segments_router(db, require_roles, risk_for):
    router = APIRouter()

    def _classify(guest: dict, risk_level: str, avg_party: float, weekday_short_ratio: float) -> str:
        spend = float(guest.get("total_spend") or 0)
        stays = int(guest.get("total_stays") or 0)
        if guest.get("vip") or spend >= 3000:
            return "vip"
        if risk_level == "high":
            return "riskli"
        if stays >= 3:
            return "sadik"
        if avg_party >= 3:
            return "aile"
        if weekday_short_ratio >= 0.6 and stays >= 1:
            return "is"
        if stays <= 1:
            return "yeni"
        return "standart"

    async def _refresh_core(property_id: str = "") -> dict:
        guests = await db.guest_profiles.find({}, {"_id": 0}).to_list(5000)
        counts: Dict[str, int] = {k: 0 for k in SEGMENTS}
        now = datetime.now(timezone.utc).isoformat()
        for g in guests:
            email = (g.get("email") or "").lower()
            avg_party, weekday_short = 0.0, 0.0
            if email:
                bks = await db.bookings.find(
                    {"guest_email": email},
                    {"_id": 0, "guest_count": 1, "check_in": 1, "check_out": 1}).to_list(200)
                if bks:
                    avg_party = sum(int(b.get("guest_count") or 1) for b in bks) / len(bks)
                    ws = 0
                    for b in bks:
                        try:
                            ci = datetime.fromisoformat(b.get("check_in", "")[:10])
                            co = datetime.fromisoformat(b.get("check_out", "")[:10])
                            nights = max((co - ci).days, 1)
                            if ci.weekday() <= 3 and nights <= 2:
                                ws += 1
                        except (ValueError, TypeError):
                            continue
                    weekday_short = ws / len(bks)
            risk = await risk_for(email) if email else {"level": "low"}
            seg = _classify(g, risk["level"], avg_party, weekday_short)
            counts[seg] += 1
            key = {"id": g["id"]} if g.get("id") else {"email": email}
            if not key.get("id") and not email:
                continue
            await db.guest_profiles.update_one(
                key,
                {"$set": {"segment": seg, "segment_updated_at": now}})
        await db.guest_segments_summary.update_one(
            {"scope": "global"},
            {"$set": {"scope": "global", "counts": counts, "refreshed_at": now,
                      "total_guests": len(guests)}},
            upsert=True)
        return {"ok": True, "classified": len(guests), "counts": counts}

    @router.get("/guests/segments/summary")
    async def summary(current_user: dict = Depends(require_roles("admin", "manager"))):
        meta = await db.guest_segments_summary.find_one({"scope": "global"}, {"_id": 0}) or {}
        pipeline = [
            {"$group": {"_id": {"$ifNull": ["$segment", "standart"]},
                        "count": {"$sum": 1},
                        "revenue": {"$sum": {"$ifNull": ["$total_spend", 0]}},
                        "stays": {"$sum": {"$ifNull": ["$total_stays", 0]}}}},
        ]
        rows = await db.guest_profiles.aggregate(pipeline).to_list(20)
        by_seg = {r["_id"]: r for r in rows}
        out = []
        for key, m in SEGMENTS.items():
            r = by_seg.get(key, {})
            cnt = int(r.get("count") or 0)
            rev = float(r.get("revenue") or 0)
            out.append({"segment": key, **m, "count": cnt,
                        "revenue": round(rev, 2),
                        "avg_spend": round(rev / cnt, 2) if cnt else 0})
        return {"segments": out, "refreshed_at": meta.get("refreshed_at"),
                "total_guests": sum(s["count"] for s in out)}

    @router.get("/guests/segments/list")
    async def list_guests(segment: str, limit: int = 50,
                          current_user: dict = Depends(require_roles("admin", "manager"))):
        if segment not in SEGMENTS:
            raise HTTPException(status_code=400, detail="Geçersiz segment")
        q = {"segment": segment} if segment != "standart" else \
            {"$or": [{"segment": "standart"}, {"segment": {"$exists": False}}]}
        rows = await db.guest_profiles.find(
            q, {"_id": 0, "name": 1, "email": 1, "total_spend": 1,
                "total_stays": 1, "loyalty_tier": 1, "vip": 1, "last_stay": 1}
        ).sort("total_spend", -1).to_list(int(limit))
        return {"segment": segment, "guests": rows}

    @router.get("/guests/segments/strategy")
    async def get_strategy(current_user: dict = Depends(require_roles("admin", "manager"))):
        saved = {s["segment"]: s for s in
                 await db.segment_strategies.find({}, {"_id": 0}).to_list(20)}
        out = []
        for key, m in SEGMENTS.items():
            saved_s = saved.get(key) or {}
            strat = {**DEFAULT_STRATEGY[key], **{k: v for k, v in saved_s.items() if k in MOTORS}}
            out.append({"segment": key, "label": m["label"],
                        **{mo: bool(strat.get(mo, True)) for mo in MOTORS}})
        return {"strategies": out, "motors": MOTORS}

    @router.put("/guests/segments/strategy/{segment}")
    async def update_strategy(segment: str, data: Dict,
                              current_user: dict = Depends(require_roles("admin", "manager"))):
        if segment not in SEGMENTS:
            raise HTTPException(status_code=400, detail="Geçersiz segment")
        upd = {m: bool(data[m]) for m in MOTORS if m in data}
        if not upd:
            raise HTTPException(status_code=400, detail="Güncellenecek motor yok")
        await db.segment_strategies.update_one(
            {"segment": segment},
            {"$set": {"segment": segment, **upd,
                      "updated_at": datetime.now(timezone.utc).isoformat(),
                      "updated_by": current_user.get("name", "")}},
            upsert=True)
        return {"ok": True, "segment": segment}

    @router.post("/guests/segments/refresh")
    async def refresh(data: Dict = None,
                      current_user: dict = Depends(require_roles("admin", "manager"))):
        return await _refresh_core((data or {}).get("property_id", ""))

    router.run_segment_refresh_internal = _refresh_core
    return router
