"""
Review Management Routes: Widget API, Approval Workflow, Reviews CRUD,
Notification Settings, Response Templates, Sentiment/Analytics, Competitors
Extracted from server.py for maintainability
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional
import os
import uuid
import asyncio
import logging

from routes.helpers import serialize_review, deserialize_review, log_sync, fire_webhooks

logger = logging.getLogger(__name__)

# ==================== REVIEW INTELLIGENCE (pure helpers, shared with autopilot/agent) ====================
import re
import difflib

_URL_RE = re.compile(r"(https?://|www\.|\.com\b|\.net\b|\.io\b|whatsapp\s*\+?\d)", re.I)
_KW = {
    "refund_requested": r"\b(refund|money back|para(mı|yı)? (geri|iade)|iade|rückerstattung|geld zurück|chargeback|reimburse)",
    "compensation_requested": r"\b(compensat|discount|voucher|telafi|indirim|tazminat|entschädigung|gutschein|free night)",
    "safety_issue": r"\b(unsafe|safety|fire|smoke alarm|injur|hurt|assault|bed ?bug|food poison|mold|mould|güvensiz|yaraland|zehirlen|böcek|tahtakurusu|brand|verletz|gefährlich)",
    "legal_issue": r"\b(lawyer|legal|sue|lawsuit|police|court|trading standards|avukat|dava|mahkeme|polis|anwalt|klage|gericht|polizei)",
    "discrimination": r"\b(racis|discriminat|sexis|homophob|ayrımcı|ırkçı|rassis|diskriminier)",
    "harassment": r"\b(harass|threaten|abus|taciz|tehdit|belästig|bedroh)",
    "fraud_allegation": r"\b(scam|fraud|stole|theft|stolen|overcharg|dolandır|hırsız|çalındı|betrug|gestohlen|abgezockt)",
    "medical_issue": r"\b(hospital|ambulance|doctor|allerg|sick|ill\b|hastane|ambulans|doktor|alerji|hasta|krankenhaus|arzt)",
}
RISK_LEVELS = ((20, "low"), (40, "medium"), (70, "high"), (100, "critical"))
DEFAULT_AUTO_RULES = {"min_rating": 4, "max_spam_pct": 5, "max_risk": 20, "min_quality": 80,
                      "max_similarity": 70, "block_refund": True, "block_legal": True, "block_safety": True}
PUBLISHING_MODES = ("manual", "smart_auto", "full_auto")


def heuristic_flags(text: str, rating: int) -> dict:
    """Deterministic keyword/pattern flags — used as fallback and merged under LLM output."""
    t = (text or "").lower()
    flags = {k: bool(re.search(p, t)) for k, p in _KW.items()}
    words = t.split()
    caps_ratio = sum(1 for w in (text or "").split() if len(w) > 3 and w.isupper()) / max(1, len(words))
    excl = t.count("!")
    spam = 0.02
    if _URL_RE.search(t): spam += 0.55
    if caps_ratio > 0.3: spam += 0.2
    if excl >= 4: spam += 0.15
    if len(words) < 4 and rating in (1, 5): spam += 0.1
    if re.search(r"\b(buy now|click here|promo code|best price|visit our|earn money)\b", t): spam += 0.3
    fake = 0.03
    if len(words) < 5 and not flags["refund_requested"]: fake += 0.12
    if rating == 5 and re.search(r"\b(best|perfect|amazing)\b.*\b(best|perfect|amazing)\b", t): fake += 0.1
    if spam > 0.5: fake += 0.3
    flags["spam_probability"] = round(min(spam, 0.99), 2)
    flags["fake_probability"] = round(min(fake, 0.99), 2)
    return flags


def compute_risk(analysis: dict, rating: int) -> dict:
    """0-100 risk score → LOW / MEDIUM / HIGH / CRITICAL + escalation level."""
    s = {1: 35, 2: 25, 3: 12, 4: 3, 5: 0}.get(int(rating or 3), 12)
    a = analysis or {}
    s += 30 if a.get("safety_issue") else 0
    s += 30 if a.get("legal_issue") else 0
    s += 25 if a.get("discrimination") or a.get("harassment") else 0
    s += 20 if a.get("fraud_allegation") else 0
    s += 20 if a.get("medical_issue") else 0
    s += 15 if a.get("refund_requested") else 0
    s += 8 if a.get("compensation_requested") else 0
    s += 8 if a.get("staff_mentioned") and a.get("sentiment") == "negative" else 0
    s += {"critical": 15, "high": 8}.get(a.get("urgency"), 0)
    s += {"critical": 10, "high": 5}.get(a.get("severity"), 0)
    s += int(float(a.get("spam_probability") or 0) * 15)
    score = max(0, min(100, s))
    level = next(l for cap, l in RISK_LEVELS if score <= cap)
    esc = "management" if level == "critical" else "manager" if level == "high" else "none"
    return {"risk_score": score, "risk_level": level, "escalation_level": esc}


_SIGN_RE = re.compile(r"^(—|–|-|kind regards|best regards|warm regards|sincerely|saygılar|sevgiler|mit freundlichen|herzliche|the management|yönetim|management team)", re.I)


def _norm(t: str) -> str:
    return re.sub(r"[^a-z0-9çğıöşüäöß ]+", " ", (t or "").lower()).strip()


def similarity_score(text: str, previous: List[str]) -> dict:
    """Exact + opening/closing + structure similarity vs previous responses (0-100)."""
    if not text or not previous:
        return {"max_pct": 0, "opening_pct": 0, "closing_pct": 0, "compared": 0, "action": "ok"}
    def _body(t: str) -> str:
        # imza / kapanış satırlarını (— Yönetim, Kind regards, The Management Team…) çıkar
        lines = [l for l in (t or "").splitlines() if l.strip() and not _SIGN_RE.match(l.strip())]
        return " ".join(lines)
    text_b = _body(text)
    n = _norm(text_b)
    sents = [x.strip() for x in re.split(r"[.!?]\s", text_b) if x.strip()]
    opening, closing = _norm(sents[0] if sents else text_b[:80]), _norm(sents[-1] if sents else text_b[-80:])
    best = op = cl = 0.0
    for p in previous[:100]:
        pb = _body(p)
        pn = _norm(pb)
        if not pn:
            continue
        best = max(best, difflib.SequenceMatcher(None, n, pn).ratio())
        ps = [x.strip() for x in re.split(r"[.!?]\s", pb) if x.strip()]
        if ps:
            op = max(op, difflib.SequenceMatcher(None, opening, _norm(ps[0])).ratio())
            cl = max(cl, difflib.SequenceMatcher(None, closing, _norm(ps[-1])).ratio())
    mx = round(max(best, op * 0.7, cl * 0.5) * 100)
    return {"max_pct": mx, "opening_pct": round(op * 100), "closing_pct": round(cl * 100),
            "compared": min(len(previous), 100), "action": "regenerate" if mx >= 85 else "ok"}


_BANNED = re.compile(r"\b(idiot|stupid|liar|shut up|fake review|you are wrong|aptal|yalancı|dumm|lügner)\b", re.I)
_GENERIC_OPEN = re.compile(r"^(thank you for your feedback|dear valued guest|değerli misafirimiz|vielen dank für ihr feedback)", re.I)


def quality_score(response: str, review: dict, analysis: dict, similarity_pct: int) -> dict:
    """7-dimension heuristic quality score (0-100 each) + total."""
    r, a = response or "", analysis or {}
    rl, words = r.lower(), r.split()
    name = (review.get("guest_name") or review.get("author") or "").split(" ")[0].lower()
    topics = [t.lower() for t in (a.get("topics") or [])] + [str(x).lower() for x in (a.get("key_issues") or []) + (a.get("key_praises") or [])]
    hits = sum(1 for t in topics if t and any(w in rl for w in t.split()[:2]))
    review_words = set(_norm(review.get("review_text") or review.get("comment") or "").split()) - {"the", "and", "was", "very", "bir", "ve", "çok"}
    overlap = len(review_words & set(_norm(r).split()))
    personal = min(100, (30 if name and name in rl else 0) + min(40, hits * 20) + min(40, overlap * 5))
    relevance = min(100, 55 + min(45, overlap * 6)) if words else 0
    neg = a.get("sentiment") == "negative" or int(review.get("rating") or 3) <= 2
    apology = bool(re.search(r"\b(sorry|apolog|özür|üzgün|entschuldig|bedauern)\b", rl))
    thanks = bool(re.search(r"\b(thank|teşekkür|dank)\b", rl))
    brand = 60 + (20 if (apology if neg else thanks) else 0) + (20 if 40 <= len(words) <= 220 else 5)
    fact = 100 - (30 if re.search(r"\b(always|never|100%|guarantee|garanti|her zaman|asla)\b", rl) else 0) - (20 if re.search(r"\b(refund(ed)?|iade edildi|we will refund)\b", rl) and not a.get("refund_requested") else 0)
    originality = max(0, 100 - int(similarity_pct or 0)) - (15 if _GENERIC_OPEN.search(r.strip()) else 0)
    prof = 100 - (40 if _BANNED.search(r) else 0) - (10 if r.count("!") > 3 else 0) - (10 if len(words) < 25 else 0)
    policy = 100 - (60 if _BANNED.search(r) else 0) - (40 if re.search(r"\b(five stars?|5 stars?|change your (review|rating)|remove (the|your) review|5 yıldız|puanı(nı)? değiştir|yorumu(nu)? sil)\b", rl) else 0) \
        - (30 if re.search(r"\b(room \d{3,4}|booking (ref|no)\.? ?[A-Z0-9]{5,}|card ending)\b", r, re.I) else 0)
    dims = {"personalisation": max(0, personal), "relevance": relevance, "brand_voice": min(100, brand), "factuality": max(0, fact),
            "originality": max(0, originality), "professionalism": max(0, prof), "policy_safety": max(0, policy)}
    total = round(sum(dims.values()) / len(dims))
    if dims["policy_safety"] < 60:
        total = min(total, 49)
    return {**dims, "total": total}


def decide_action(analysis: dict, rating: int, quality_total: int, similarity_pct: int, cfg: dict) -> dict:
    """Decision engine → do_not_reply | escalate | auto_approve | human_approval (+ reasons)."""
    a, reasons = analysis or {}, []
    rules = {**DEFAULT_AUTO_RULES, **(cfg.get("auto_rules") or {})}
    mode = cfg.get("publishing_mode") or "manual"
    spam = float(a.get("spam_probability") or 0) * 100
    risk = a.get("risk_level") or compute_risk(a, rating)["risk_level"]
    if spam >= 80:
        return {"action": "do_not_reply", "reasons": [f"spam {spam:.0f}%"], "mode": mode}
    if risk == "critical":
        return {"action": "escalate", "reasons": ["risk critical"], "mode": mode, "escalation_level": "management"}
    if mode == "manual":
        return {"action": "human_approval", "reasons": ["manual mode"], "mode": mode}
    if a.get("legal_issue"): reasons.append("legal")
    if a.get("safety_issue"): reasons.append("safety")
    if a.get("discrimination") or a.get("harassment"): reasons.append("sensitive")
    if mode == "full_auto":
        return {"action": "human_approval" if reasons else "auto_approve", "reasons": reasons or ["full_auto"], "mode": mode}
    if int(rating or 0) < int(rules["min_rating"]): reasons.append(f"rating < {rules['min_rating']}")
    if spam > float(rules["max_spam_pct"]): reasons.append(f"spam {spam:.0f}% > {rules['max_spam_pct']}%")
    if int(a.get("risk_score") or 0) > int(rules["max_risk"]): reasons.append(f"risk {a.get('risk_score')} > {rules['max_risk']}")
    if rules.get("block_refund") and (a.get("refund_requested") or a.get("compensation_requested")): reasons.append("refund/compensation")
    if a.get("staff_mentioned") and a.get("sentiment") == "negative": reasons.append("staff complaint")
    if quality_total is not None and int(quality_total) < int(rules["min_quality"]): reasons.append(f"quality {quality_total} < {rules['min_quality']}")
    if int(similarity_pct or 0) >= int(rules["max_similarity"]): reasons.append(f"similarity {similarity_pct}% ≥ {rules['max_similarity']}%")
    if risk == "high": reasons.append("risk high")
    return {"action": "human_approval" if reasons else "auto_approve", "reasons": reasons or ["rules passed"], "mode": mode}


_PRIV = {
    "email": re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"),
    "phone": re.compile(r"(?<![\d/.\-])(\+?\d[\d\s().-]{8,}\d)(?![\d/.\-])"),
    "card_or_iban": re.compile(r"\b(?:\d[ -]?){13,19}\b|\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b"),
    "payment": re.compile(r"\b(card ending|last 4 digits|cvv|expiry date|kart(ın)? son|kartın|iban|sort code|hesap no)\b", re.I),
    "booking_ref": re.compile(r"\b(booking|reservation|rezervasyon|confirmation|onay|ref(erence)?|buchung)\b\s*(no\.?|number|numarası|nr\.?|id|#|code|kodu)?\s*[:#]?\s*(?=[A-Z0-9-]*\d)[A-Z0-9][A-Z0-9-]{4,}\b", re.I),
    "room_number": re.compile(r"\b(room|oda|zimmer|suite)\s*(no\.?|number|numarası|nr\.?)?\s*#?\s*\d{2,4}\b", re.I),
    "internal_notes": re.compile(r"\b(internal note|internal only|do not publish|yayınlamayın|iç not|yönetici notu|manager note|staff note|crm|pms|folio|blacklist|kara liste|vip flag|housekeeping log|ticket #|incident report)\b", re.I),
}


def privacy_check(text: str, staff_surnames: Optional[List[str]] = None) -> dict:
    """Yayın öncesi sert gizlilik denetimi → {ok, violations[]}. Gerçek verileri asla döndürmez, sadece tür + maskeli örnek."""
    t = text or ""
    found = []
    for kind, rx in _PRIV.items():
        m = rx.search(t)
        if not m:
            continue
        if kind == "phone" and len(re.sub(r"\D", "", m.group(0))) < 9:
            continue
        snip = m.group(0)
        found.append({"type": kind, "sample": snip[:3] + "…" + snip[-2:] if len(snip) > 6 else "•••"})
    for sn in (staff_surnames or []):
        if sn and len(sn) >= 3 and re.search(r"\b" + re.escape(sn) + r"\b", t, re.I):
            found.append({"type": "staff_private", "sample": sn[:1] + "•••"})
            break
    return {"ok": not found, "violations": found}


_ROLE_WORDS = {"manager", "housekeeper", "receptionist", "admin", "staff", "team", "management", "director", "concierge",
               "host", "owner", "test", "user", "demo", "auditor", "chef", "waiter", "reception", "front", "desk", "night",
               "revenue", "finance", "sales", "marketing", "general", "assistant", "supervisor", "guest", "hotel", "yönetici",
               "müdür", "resepsiyon", "personel", "kat", "görevlisi", "leiter", "rezeption"}


async def staff_surnames_db(db) -> List[str]:
    """Personel soyadları (users/staff). Rol/unvan kelimeleri ve tek kelimelik isimler hariç."""
    surnames: List[str] = []
    for coll in (db.users, db.staff):
        try:
            async for u in coll.find({}, {"_id": 0, "name": 1, "full_name": 1, "last_name": 1}).limit(300):
                if u.get("last_name"):
                    nm = str(u["last_name"]).strip()
                else:
                    parts = (u.get("full_name") or u.get("name") or "").strip().split()
                    nm = parts[-1] if len(parts) >= 2 else ""
                if nm and len(nm) >= 3 and nm.lower() not in _ROLE_WORDS and nm.isalpha():
                    surnames.append(nm)
        except Exception:
            pass
    return surnames


async def privacy_check_db(db, text: str, property_id: str = "") -> dict:
    """privacy_check + personel soyadları (users/staff) ile."""
    return privacy_check(text, await staff_surnames_db(db))


TOPIC_ACTIONS = {
    "check-in": "15:00–18:00 arası resepsiyon kadrosunu artırın; online/self check-in'i ön varış e-postasında öne çıkarın.",
    "checkin": "15:00–18:00 arası resepsiyon kadrosunu artırın; online/self check-in'i ön varış e-postasında öne çıkarın.",
    "check-out": "Express check-out (folio e-posta) açın; sabah 10:00–12:00 kasada ikinci kişi bulundurun.",
    "cleanliness": "HK kontrol listesine banyo/yatak denetimi ekleyin; süpervizör örnekleme oranını %20'ye çıkarın.",
    "noise": "Sessiz kat/oda ataması kuralı; koridor ve klima gürültüsü için bakım turu; misafire kulak tıkacı seti.",
    "breakfast": "Kahvaltı çeşitliliğini gözden geçirin (sıcak seçenek, yerel ürün); yoğun saatte ikinci büfe hattı.",
    "food": "Menü mühendisliği: en çok şikâyet alan kalemleri değiştirin; mutfak porsiyon/sıcaklık standardı.",
    "staff": "Şikâyet alan personel için birebir koçluk; misafir iletişim eğitimi; övgü alanları ödüllendirin.",
    "wifi": "Erişim noktası kapsama testi; bant genişliği yükseltme; oda kartında Wi-Fi bilgisi.",
    "bathroom": "Duş basıncı/sıcak su bakım turu; tesisat önleyici bakım planı.",
    "bed": "Yatak/yastık değişim planı; yastık menüsü sunun.",
    "value": "Fiyat-değer algısı: dahil hizmetleri netleştirin; direkt rezervasyona küçük avantaj ekleyin.",
    "parking": "Otopark rezervasyon/ücret bilgisini ön varış e-postasına ekleyin; alternatif otopark anlaşması.",
    "location": "Ulaşım rehberi ve transfer seçeneğini ön varış e-postasında paylaşın.",
    "amenities": "Eksik/arızalı olanakları listeleyin; öncelikli bakım planı.",
    "maintenance": "Önleyici bakım turlarını haftalık yapın; arıza SLA'sı 2 saat.",
    "temperature": "Klima/ısıtma bakım turu; oda içi kontrol talimatı.",
}


async def root_cause(db, property_id: str, days: int = 30) -> dict:
    """Olumsuz yorumlardaki (≤3★) tekrarlayan konular: frekans %, önceki döneme göre trend, önerilen aksiyon."""
    now = datetime.now(timezone.utc)
    cur_from = (now - timedelta(days=days)).isoformat()
    prev_from = (now - timedelta(days=days * 2)).isoformat()
    pq = {"property_id": property_id} if property_id and property_id != "all" else {}
    base = {**pq, "rating": {"$lte": 3}, "sentiment_analysis.topics": {"$exists": True, "$ne": []}}

    async def _count(frm, to=None):
        q = {**base, "created_at": {"$gte": frm, **({"$lt": to} if to else {})}}
        docs = await db.reviews.find(q, {"_id": 0, "sentiment_analysis.topics": 1, "rating": 1}).to_list(2000)
        cnt: Dict[str, int] = {}
        for d in docs:
            for t in set((d.get("sentiment_analysis") or {}).get("topics") or []):
                t = str(t).lower().strip()
                cnt[t] = cnt.get(t, 0) + 1
        return len(docs), cnt

    n_cur, cur = await _count(cur_from)
    n_prev, prev = await _count(prev_from, cur_from)
    items = []
    for topic, c in sorted(cur.items(), key=lambda x: -x[1]):
        freq = round(c / n_cur * 100) if n_cur else 0
        pfreq = round(prev.get(topic, 0) / n_prev * 100) if n_prev else 0
        trend = freq - pfreq
        severity = "high" if freq >= 30 or trend >= 15 else "medium" if freq >= 15 or trend >= 5 else "low"
        items.append({"topic": topic, "count": c, "frequency_pct": freq, "prev_pct": pfreq, "trend_pts": trend,
                      "severity": severity, "recurring": c >= 3,
                      "action": TOPIC_ACTIONS.get(topic) or TOPIC_ACTIONS.get(topic.replace(" ", "-")) or "Konuyu haftalık operasyon toplantısında ele alın; sorumlu departman atayın."})
    return {"days": days, "negative_reviews": n_cur, "previous_negative_reviews": n_prev, "items": items[:8],
            "top": items[0] if items else None}


async def staff_intelligence(db, property_id: str, days: int = 90) -> dict:
    """Yorumlarda adı geçen personel: mention / övgü / şikâyet sayıları."""
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    pq = {"property_id": property_id} if property_id and property_id != "all" else {}
    docs = await db.reviews.find({**pq, "created_at": {"$gte": since}, "sentiment_analysis.staff_mentioned.0": {"$exists": True}},
                                 {"_id": 0, "id": 1, "rating": 1, "guest_name": 1, "created_at": 1, "sentiment_analysis.staff_mentioned": 1,
                                  "sentiment_analysis.sentiment": 1}).to_list(2000)
    people: Dict[str, dict] = {}
    for d in docs:
        a = d.get("sentiment_analysis") or {}
        positive = int(d.get("rating") or 3) >= 4 or a.get("sentiment") == "positive"
        for raw in a.get("staff_mentioned") or []:
            name = str(raw).strip().split(" ")[0].title()
            if not name or name.lower() in _ROLE_WORDS:
                continue
            p = people.setdefault(name, {"name": name, "mentions": 0, "positive": 0, "negative": 0, "ratings": [], "last_review_id": None, "last_at": ""})
            p["mentions"] += 1
            p["positive" if positive else "negative"] += 1
            p["ratings"].append(int(d.get("rating") or 3))
            if (d.get("created_at") or "") > p["last_at"]:
                p["last_at"], p["last_review_id"] = d.get("created_at", ""), d.get("id")
    out = []
    for p in people.values():
        p["avg_rating"] = round(sum(p["ratings"]) / len(p["ratings"]), 1)
        p.pop("ratings")
        out.append(p)
    out.sort(key=lambda x: -x["mentions"])
    return {"days": days, "staff": out[:20],
            "top_praised": sorted([x for x in out if x["positive"]], key=lambda x: -x["positive"])[:5],
            "recurring_complaints": sorted([x for x in out if x["negative"] >= 2], key=lambda x: -x["negative"])[:5]}


async def get_review_agent_cfg(db, property_id: str) -> dict:
    """Per-property publishing config (review_agent_config koleksiyonu — review_agent.py ile ortak)."""
    cfg = await db.review_agent_config.find_one({"property_id": property_id or "default"}, {"_id": 0}) or {}
    cfg.setdefault("publishing_mode", "smart_auto")
    cfg["auto_rules"] = {**DEFAULT_AUTO_RULES, **(cfg.get("auto_rules") or {})}
    return cfg


async def log_review_event(db, review_id: str, event: str, by: str = "system", **meta):
    """Audit zinciri: reviews.events[] (son 60 olay)."""
    await db.reviews.update_one({"id": review_id, "events": None}, {"$set": {"events": []}})
    await db.reviews.update_one({"id": review_id}, {"$push": {"events": {"$each": [{
        "type": event, "by": by, "at": datetime.now(timezone.utc).isoformat(), **({"meta": meta} if meta else {})}], "$slice": -60}}})


def create_reviews_router(db, require_roles, get_current_user, verify_api_key, LlmChat, UserMessage, resend):
    """Factory function that creates review routes with injected dependencies"""
    from models import (
        Review, ReviewCreate, ReviewResponse, AIGenerateRequest, AIGenerateResponse,
        NotificationSettings, NotificationSettingsUpdate,
        ResponseTemplate, ResponseTemplateCreate, ResponseTemplateUpdate,
        SentimentAnalysis, CompetitorData, CompetitorCreate, CompetitorUpdate,
        ApprovalAction, StatusCheck, StatusCheckCreate,
    )
    router = APIRouter()
    SENDER_EMAIL = os.environ.get('SENDER_EMAIL', 'onboarding@resend.dev')
    NOTIFICATION_EMAIL = os.environ.get('NOTIFICATION_EMAIL', '')

    # ==================== WIDGET API (API Key Auth) ====================

    @router.get("/widget/reviews")
    async def widget_get_reviews(request: Request, key_doc: dict = Depends(verify_api_key)):
        """Get reviews for widget display (authenticated via API key)"""
        property_id = request.query_params.get("property_id", "default")
        platform = request.query_params.get("platform")
        status = request.query_params.get("status")
        limit = min(int(request.query_params.get("limit", "20")), 50)

        query = {"property_id": property_id}
        if platform:
            query["platform"] = platform
        if status:
            query["response_status"] = status

        reviews = await db.reviews.find(query, {"_id": 0}).sort("created_at", -1).to_list(limit)
        return reviews

    @router.get("/widget/reviews/new")
    async def widget_new_reviews(request: Request, key_doc: dict = Depends(verify_api_key)):
        """Get reviews created after a given timestamp (for polling)"""
        property_id = request.query_params.get("property_id", "default")
        since = request.query_params.get("since")
        if not since:
            return []
        query = {"property_id": property_id, "created_at": {"$gt": since}}
        reviews = await db.reviews.find(query, {"_id": 0}).sort("created_at", -1).to_list(10)
        return reviews

    @router.get("/widget/stats")
    async def widget_get_stats(request: Request, key_doc: dict = Depends(verify_api_key)):
        """Get review stats for widget display"""
        property_id = request.query_params.get("property_id", "default")
        query = {"property_id": property_id}

        total = await db.reviews.count_documents(query)
        responded = await db.reviews.count_documents({**query, "response_status": "responded"})
        pending = await db.reviews.count_documents({**query, "response_status": {"$in": ["pending", "draft"]}})

        pipeline = [{"$match": query}, {"$group": {"_id": None, "avg": {"$avg": "$rating"}}}]
        avg_result = await db.reviews.aggregate(pipeline).to_list(1)
        avg_rating = round(avg_result[0]["avg"], 1) if avg_result else 0

        return {
            "total_reviews": total,
            "average_rating": avg_rating,
            "response_rate": round((responded / total) * 100, 1) if total > 0 else 0,
            "responded": responded,
            "pending": pending
        }

    @router.get("/widget/unread-count")
    async def widget_unread_count(request: Request, key_doc: dict = Depends(verify_api_key)):
        """Get count of unread reviews"""
        property_id = request.query_params.get("property_id", "default")
        count = await db.reviews.count_documents({"property_id": property_id, "is_read": {"$ne": True}})
        return {"unread": count}

    @router.put("/widget/reviews/{review_id}/read")
    async def widget_mark_read(review_id: str, key_doc: dict = Depends(verify_api_key)):
        """Mark a review as read"""
        result = await db.reviews.update_one({"id": review_id}, {"$set": {"is_read": True}})
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Review not found")
        return {"ok": True}

    @router.put("/widget/reviews/mark-all-read")
    async def widget_mark_all_read(request: Request, key_doc: dict = Depends(verify_api_key)):
        """Mark all reviews as read for a property"""
        property_id = request.query_params.get("property_id", "default")
        result = await db.reviews.update_many(
            {"property_id": property_id, "is_read": {"$ne": True}},
            {"$set": {"is_read": True}}
        )
        return {"marked": result.modified_count}

    @router.post("/widget/generate-response")
    async def widget_generate_response(request: Request, key_doc: dict = Depends(verify_api_key)):
        """Generate AI response from widget"""
        body = await request.json()
        review_id = body.get("review_id")
        language = body.get("language", "en")
        tone = body.get("tone", "professional")

        if not review_id:
            raise HTTPException(status_code=400, detail="review_id required")

        review = await db.reviews.find_one({"id": review_id}, {"_id": 0})
        if not review:
            raise HTTPException(status_code=404, detail="Review not found")

        api_key = os.environ.get("EMERGENT_LLM_KEY")
        if not api_key:
            raise HTTPException(status_code=500, detail="AI service not configured")

        prompt = f"""Generate a {tone} hotel review response in {language}.
    Guest: {review.get('guest_name', 'Guest')}
    Rating: {review.get('rating', 'N/A')}/5
    Platform: {review.get('platform', 'unknown')}
    Review: {review.get('review_text', '')}
    Keep it unique, warm, and under 150 words."""

        try:
            chat = LlmChat(api_key=api_key, session_id=f"widget-{uuid.uuid4()}", system_message="You are a hotel review response assistant.").with_model("openai", "gpt-5.2")
            response = await chat.send_message(UserMessage(text=prompt))
            response_text = response.strip()

            await db.reviews.update_one({"id": review_id}, {"$set": {
                "response_text": response_text,
                "response_status": "draft",
                "response_language": language,
                "response_generated_at": datetime.now(timezone.utc).isoformat()
            }})

            return {"response_text": response_text, "review_id": review_id, "status": "draft"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"AI generation failed: {str(e)[:100]}")

    # ==================== APPROVAL WORKFLOW ROUTES ====================

    @router.post("/reviews/{review_id}/submit-for-approval")
    async def submit_for_approval(review_id: str, request: Request):
        current_user = await get_current_user(request)
        review = await db.reviews.find_one({"id": review_id}, {"_id": 0})
        if not review:
            raise HTTPException(status_code=404, detail="Review not found")
        body = {}
        try:
            body = await request.json()
        except Exception:
            pass
        text = (body.get("response_text") or review.get("response_text") or review.get("ai_draft") or "").strip()
        if not text:
            raise HTTPException(status_code=400, detail="No response text to submit")
        await db.reviews.update_one({"id": review_id}, {"$set": {
            "response_text": text,
            "response_status": "pending_approval",
            "drafted_by": current_user.get("name", current_user.get("email")),
        }})
        await log_review_event(db, review_id, "submitted_for_approval", current_user.get("name", current_user.get("email")))
        return {"message": "Submitted for approval", "status": "pending_approval"}

    @router.post("/reviews/{review_id}/approve")
    async def approve_response(review_id: str, action: ApprovalAction, request: Request):
        current_user = await get_current_user(request)
        from routes.platform_ext.admin import has_permission
        if not has_permission(current_user, "reviews", "approve"):
            raise HTTPException(status_code=403, detail="CAN_APPROVE_RESPONSE izniniz yok")
        review = await db.reviews.find_one({"id": review_id}, {"_id": 0})
        if not review:
            raise HTTPException(status_code=404, detail="Review not found")
        who = current_user.get("name", current_user.get("email"))
        now = datetime.now(timezone.utc).isoformat()
        analysis = review.get("sentiment_analysis") or {}
        risk_level = analysis.get("risk_level", "low")

        if action.action == "approve":
            if not has_permission(current_user, "reviews", "publish"):
                raise HTTPException(status_code=403, detail="CAN_PUBLISH_RESPONSE izniniz yok")
            if analysis.get("spam_suspected") and not (action.notes or "").strip():
                raise HTTPException(status_code=400, detail="Spam şüpheli yorum: yayımlamak için gerekçe (notes) zorunlu")
            if not (review.get("response_text") or "").strip():
                raise HTTPException(status_code=400, detail="Yayımlanacak yanıt metni yok")
            pv = await privacy_check_db(db, review.get("response_text", ""), review.get("property_id", ""))
            if not pv["ok"]:
                await log_review_event(db, review_id, "publish_blocked_privacy", who, violations=[v["type"] for v in pv["violations"]])
                raise HTTPException(status_code=400, detail="Gizlilik ihlali — yayın engellendi: " + ", ".join(v["type"] for v in pv["violations"]))
            override = None
            if risk_level in ("high", "critical") or review.get("escalated"):
                if not (action.notes or "").strip():
                    raise HTTPException(status_code=400, detail=f"Risk {risk_level.upper()}: override gerekçesi (notes) zorunlu")
                override = {"by": who, "at": now, "reason": action.notes, "risk_level": risk_level,
                            "risk_score": analysis.get("risk_score"), "draft_version": review.get("regeneration_count", 1)}
            upd = {"response_status": "responded", "responded": True, "approved_by": who, "approval_notes": action.notes,
                   "response_date": now, "escalated": False}
            if override:
                upd["approval_override"] = override
            await db.reviews.update_one({"id": review_id}, {"$set": upd})
            await log_review_event(db, review_id, "override_approved" if override else "approved", who, reason=action.notes or "")
            await log_review_event(db, review_id, "published", who, channel=review.get("platform"))
            if review.get("platform") and review.get("external_review_id"):
                asyncio.create_task(_attempt_outbound_sync(review["platform"], review_id, review["external_review_id"], review.get("response_text", "")))
            return {"message": "Response approved and published", "status": "responded", "override": bool(override)}
        elif action.action == "reject":
            await db.reviews.update_one({"id": review_id}, {"$set": {
                "response_status": "rejected", "approved_by": who, "approval_notes": action.notes}})
            await log_review_event(db, review_id, "rejected", who, reason=action.notes or "")
            return {"message": "Response rejected", "status": "rejected"}
        elif action.action == "escalate":
            level = "management" if risk_level == "critical" else "manager"
            await db.reviews.update_one({"id": review_id}, {"$set": {
                "response_status": "pending_approval", "escalated": True, "escalation_level": level,
                "escalated_by": who, "escalated_at": now, "escalation_notes": action.notes or ""}})
            await log_review_event(db, review_id, "escalated", who, level=level, reason=action.notes or "")
            await db.notifications.insert_one({
                "id": str(uuid.uuid4()), "category": "review_escalation", "priority": "high",
                "title": f"🔺 Yorum eskalasyonu ({risk_level.upper()}): {review.get('guest_name', '')} {review.get('rating', '?')}★",
                "message": f"{who} yorumu {level} seviyesine yükseltti. {action.notes or ''} — \"{(review.get('review_text') or '')[:140]}\"",
                "property_id": review.get("property_id", ""), "review_id": review_id, "read": False, "created_at": now})
            return {"message": f"Escalated to {level}", "status": "pending_approval", "escalation_level": level}
        else:
            raise HTTPException(status_code=400, detail="Invalid action")

    @router.get("/reviews/pending-approval")
    async def get_pending_approvals(request: Request, property_id: Optional[str] = None):
        current_user = await get_current_user(request)
        if current_user["role"] not in ["admin", "manager"]:
            raise HTTPException(status_code=403, detail="Only managers and admins can view approval queue")
        q: Dict = {"response_status": "pending_approval"}
        if property_id and property_id != "all":
            q["property_id"] = property_id
        reviews = await db.reviews.find(q, {"_id": 0}).to_list(200)
        surnames = await staff_surnames_db(db)
        for r in reviews:
            if r.get("response_text"):
                r["response_privacy"] = privacy_check(r["response_text"], surnames)
        order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        reviews.sort(key=lambda r: (0 if r.get("escalated") else 1,
                                    order.get((r.get("sentiment_analysis") or {}).get("risk_level", "low"), 3),
                                    -int((r.get("sentiment_analysis") or {}).get("risk_score") or 0)))
        return [serialize_review(r) for r in reviews]

    @router.post("/reviews/approve-bulk")
    async def approve_bulk(request: Request):
        """Kontrollü toplu onay: sadece 4-5★ + risk low + kalite ≥ eşik + spam değil (1-3★ asla)."""
        current_user = await get_current_user(request)
        from routes.platform_ext.admin import has_permission
        if not (has_permission(current_user, "reviews", "approve") and has_permission(current_user, "reviews", "publish")):
            raise HTTPException(status_code=403, detail="Toplu onay için approve + publish izni gerekir")
        body = await request.json()
        ids = body.get("review_ids") or []
        q: Dict = {"response_status": "pending_approval"}
        if ids:
            q["id"] = {"$in": ids}
        elif body.get("property_id") and body["property_id"] != "all":
            q["property_id"] = body["property_id"]
        who = current_user.get("name", current_user.get("email"))
        approved, skipped = [], []
        for r in await db.reviews.find(q, {"_id": 0}).to_list(200):
            cfg = await get_review_agent_cfg(db, r.get("property_id", "default"))
            a = r.get("sentiment_analysis") or {}
            qt = (r.get("response_quality") or {}).get("total")
            why = []
            if int(r.get("rating") or 0) < 4: why.append("rating < 4")
            if a.get("risk_level", "low") != "low": why.append(f"risk {a.get('risk_level')}")
            if a.get("spam_suspected"): why.append("spam")
            if r.get("escalated"): why.append("escalated")
            if qt is not None and qt < cfg["auto_rules"]["min_quality"]: why.append(f"quality {qt}")
            if not (r.get("response_text") or "").strip(): why.append("no draft")
            elif not (await privacy_check_db(db, r["response_text"], r.get("property_id", "")))["ok"]: why.append("privacy")
            if why:
                skipped.append({"review_id": r["id"], "guest_name": r.get("guest_name"), "reasons": why}); continue
            now = datetime.now(timezone.utc).isoformat()
            await db.reviews.update_one({"id": r["id"]}, {"$set": {"response_status": "responded", "responded": True, "approved_by": who,
                                                                  "approval_notes": "bulk", "response_date": now}})
            await log_review_event(db, r["id"], "bulk_approved", who)
            await log_review_event(db, r["id"], "published", who, channel=r.get("platform"))
            approved.append(r["id"])
        return {"approved": len(approved), "approved_ids": approved, "skipped": skipped}

    def _basic_analysis(review_text: str, rating: int) -> dict:
        sentiment = "positive" if rating >= 4 else "negative" if rating <= 2 else "neutral"
        return {
            "sentiment": sentiment,
            "score": (rating - 3) / 2,
            "urgency": "critical" if rating == 1 else "high" if rating == 2 else "low",
            "topics": [],
            "suggested_tone": "apologetic" if rating <= 2 else "friendly" if rating >= 4 else "professional",
            "suggested_category": "negative" if rating <= 2 else "positive" if rating >= 4 else "neutral",
            "key_issues": [], "key_praises": [], "emotion": [], "staff_mentioned": [],
            "severity": "high" if rating <= 2 else "medium" if rating == 3 else "low",
            "customer_intent": "complaint" if rating <= 2 else "praise" if rating >= 4 else "feedback",
            "source": "heuristic",
        }

    def _enrich_analysis(analysis: dict, review_text: str, rating: int) -> dict:
        """Merge deterministic flags under LLM output, then compute risk + recommended action."""
        flags = heuristic_flags(review_text, rating)
        for k, v in flags.items():
            if k in ("spam_probability", "fake_probability"):
                analysis[k] = round(max(float(analysis.get(k) or 0), v), 2)
            else:
                analysis[k] = bool(analysis.get(k)) or v
        analysis.setdefault("emotion", []); analysis.setdefault("staff_mentioned", [])
        analysis.setdefault("severity", "high" if rating <= 2 else "medium" if rating == 3 else "low")
        analysis.update(compute_risk(analysis, rating))
        analysis["spam_suspected"] = analysis["spam_probability"] >= 0.8
        analysis["fake_suspected"] = analysis["fake_probability"] >= 0.7
        analysis["recommended_action"] = ("do_not_reply" if analysis["spam_suspected"] else
                                          "escalate" if analysis["risk_level"] == "critical" else
                                          "human_review" if analysis["risk_level"] in ("high", "medium") or analysis["fake_suspected"] else "auto_ok")
        analysis["analyzed_at"] = datetime.now(timezone.utc).isoformat()
        return analysis

    async def analyze_sentiment(review_text: str, rating: int) -> dict:
        """Review Intelligence: sentiment + emotion + topics + staff + risk flags + spam/fake (GPT-5.2, heuristik yedek)"""
        api_key = os.environ.get("EMERGENT_LLM_KEY")
        if not api_key:
            return _enrich_analysis(_basic_analysis(review_text, rating), review_text, rating)

        system_message = """You are a hotel review intelligence analyzer. Analyze the given review and return a JSON object with:
    - sentiment: "positive", "negative", "neutral", or "mixed"
    - score: float from -1 (very negative) to 1 (very positive)
    - emotion: array of emotions (e.g. "frustration","disappointment","anger","joy","gratitude","surprise")
    - severity: "low", "medium", "high", or "critical"
    - urgency: "low", "medium", "high", or "critical" (critical for reviews mentioning health/safety/legal issues)
    - topics: array of topics mentioned (cleanliness, staff, amenities, location, value, food, noise, parking, wifi, bathroom, bed, check-in, check-out, etc.)
    - subtopics: array of more specific sub-topics (e.g. "breakfast variety", "shower pressure")
    - staff_mentioned: array of staff first names mentioned (empty if none)
    - refund_requested: boolean (guest explicitly asks for money back)
    - compensation_requested: boolean (asks for discount/voucher/compensation)
    - safety_issue: boolean (physical safety, fire, injury, bed bugs, food poisoning)
    - legal_issue: boolean (lawyer, lawsuit, police, court, legal threats)
    - discrimination: boolean, harassment: boolean, fraud_allegation: boolean (theft/scam/overcharge), medical_issue: boolean
    - spam_probability: float 0-1 (ads, links, off-topic promotion)
    - fake_probability: float 0-1 (generic, implausible, pattern-like review)
    - customer_intent: "complaint", "praise", "feedback", "warning_others", "seeking_refund"
    - suggested_tone: "professional", "friendly", or "apologetic" based on what response tone would work best
    - suggested_category: "positive", "negative", "neutral", "complaint", or "praise" for template matching
    - key_issues: array of specific problems mentioned
    - key_praises: array of specific compliments mentioned

    Return ONLY valid JSON, no other text."""

        prompt = f"""Analyze this hotel review (rated {rating}/5 stars):

    "{review_text}"

    Return the sentiment analysis as JSON."""

        try:
            chat = LlmChat(
                api_key=api_key,
                session_id=f"sentiment-{uuid.uuid4()}",
                system_message=system_message
            ).with_model("openai", "gpt-5.2")

            user_message = UserMessage(text=prompt)
            response = await chat.send_message(user_message)

            # Parse JSON from response
            import json
            # Clean response - remove markdown code blocks if present
            cleaned = response.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("```")[1]
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:]
            cleaned = cleaned.strip()

            result = json.loads(cleaned)
            result["source"] = "llm"
            return _enrich_analysis(result, review_text, rating)
        except Exception as e:
            logger.error(f"Sentiment analysis error: {str(e)}")
            return _enrich_analysis(_basic_analysis(review_text, rating), review_text, rating)

    async def send_negative_review_notification(review: dict):
        """Send email notification for negative reviews (1-2 stars)"""
        settings = await db.notification_settings.find_one({}, {"_id": 0})

        if not settings or not settings.get('enabled', False):
            logger.info("Notifications disabled or not configured")
            return False

        if review.get('rating', 5) > settings.get('negative_threshold', 2):
            logger.info(f"Review rating {review.get('rating')} above threshold, skipping notification")
            return False

        notification_email = settings.get('email', NOTIFICATION_EMAIL)
        if not notification_email:
            logger.warning("No notification email configured")
            return False

        if not resend.api_key or resend.api_key == 're_123456789':
            logger.warning("Resend API key not configured - notification logged but not sent")
            # Log the notification for demo purposes
            await db.notification_log.insert_one({
                "id": str(uuid.uuid4()),
                "review_id": review.get('id'),
                "email": notification_email,
                "status": "demo_logged",
                "created_at": datetime.now(timezone.utc).isoformat()
            })
            return True

        platform_names = {
            "booking.com": "Booking.com",
            "airbnb": "Airbnb",
            "expedia": "Expedia",
            "tripadvisor": "TripAdvisor",
            "google": "Google",
            "trip.com": "Trip.com"
        }

        platform = platform_names.get(review.get('platform', ''), review.get('platform', 'Unknown'))
        rating_stars = '★' * review.get('rating', 1) + '☆' * (5 - review.get('rating', 1))

        html_content = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background-color: #C05A44; color: white; padding: 20px; border-radius: 8px 8px 0 0;">
                <h1 style="margin: 0; font-size: 24px;">⚠️ Negative Review Alert</h1>
            </div>
            <div style="background-color: #FAF9F6; padding: 20px; border: 1px solid #E7E5E4; border-top: none; border-radius: 0 0 8px 8px;">
                <p style="color: #57534E; margin-bottom: 20px;">A new negative review requires your attention:</p>

                <div style="background-color: white; border: 1px solid #E7E5E4; border-radius: 8px; padding: 20px; margin-bottom: 20px;">
                    <div style="display: flex; justify-content: space-between; margin-bottom: 15px;">
                        <span style="background-color: #3E5245; color: white; padding: 4px 12px; border-radius: 4px; font-size: 12px;">{platform}</span>
                        <span style="color: #D4A373; font-size: 18px;">{rating_stars}</span>
                    </div>
                    <p style="font-weight: bold; color: #1C1917; margin-bottom: 5px;">{review.get('guest_name', 'Guest')}</p>
                    <p style="color: #57534E; font-size: 14px; margin-bottom: 15px;">
                        {review.get('room_type', '')} • {review.get('stay_date', '')}
                    </p>
                    <p style="color: #1C1917; line-height: 1.6; background-color: #FAF9F6; padding: 15px; border-radius: 4px;">
                        "{review.get('review_text', '')}"
                    </p>
                </div>

                <p style="color: #57534E; font-size: 14px;">
                    Quick response to negative reviews can help protect your hotel's reputation. 
                    Log in to Review Hub to craft a thoughtful response.
                </p>

                <div style="margin-top: 20px; padding-top: 20px; border-top: 1px solid #E7E5E4; color: #57534E; font-size: 12px;">
                    This is an automated notification from Review Hub.
                </div>
            </div>
        </div>
        """

        try:
            params = {
                "from": SENDER_EMAIL,
                "to": [notification_email],
                "subject": f"⚠️ Negative Review Alert: {review.get('rating')}/5 on {platform}",
                "html": html_content
            }

            email_result = await asyncio.to_thread(resend.Emails.send, params)

            # Log successful notification
            await db.notification_log.insert_one({
                "id": str(uuid.uuid4()),
                "review_id": review.get('id'),
                "email": notification_email,
                "email_id": email_result.get('id'),
                "status": "sent",
                "created_at": datetime.now(timezone.utc).isoformat()
            })

            logger.info(f"Negative review notification sent to {notification_email}")
            return True

        except Exception as e:
            logger.error(f"Failed to send notification: {str(e)}")
            await db.notification_log.insert_one({
                "id": str(uuid.uuid4()),
                "review_id": review.get('id'),
                "email": notification_email,
                "status": "failed",
                "error": str(e),
                "created_at": datetime.now(timezone.utc).isoformat()
            })
            return False

    # ==================== ROUTES ====================

    # ==================== REVIEW ROUTES ====================

    @router.get("/reviews", response_model=List[Review])
    async def get_reviews(
        property_id: Optional[str] = None,
        platform: Optional[str] = None,
        status: Optional[str] = None,
        rating: Optional[int] = None
    ):
        """Get all reviews with optional filters"""
        query = {}
        if property_id:
            query["property_id"] = property_id
        if platform and platform != "all":
            query["platform"] = platform
        if status and status != "all":
            query["response_status"] = status
        if rating:
            query["rating"] = rating

        reviews = await db.reviews.find(query, {"_id": 0}).sort("review_date", -1).to_list(1000)
        for review in reviews:
            deserialize_review(review)
        return reviews

    @router.get("/reviews/staff-intelligence")
    async def get_staff_intelligence(property_id: Optional[str] = None, days: int = 90,
                                     _: dict = Depends(require_roles("admin", "manager"))):
        return await staff_intelligence(db, property_id or "all", days)

    @router.get("/reviews/root-cause")
    async def get_root_cause(property_id: Optional[str] = None, days: int = 30,
                             _: dict = Depends(require_roles("admin", "manager"))):
        return await root_cause(db, property_id or "all", days)

    @router.get("/reviews/{review_id}", response_model=Review)
    async def get_review(review_id: str):
        """Get a single review by ID"""
        review = await db.reviews.find_one({"id": review_id}, {"_id": 0})
        if not review:
            raise HTTPException(status_code=404, detail="Review not found")
        deserialize_review(review)
        return review

    @router.post("/reviews", response_model=Review)
    async def create_review(input: ReviewCreate):
        """Create a new review"""
        review = Review(**input.model_dump())
        doc = review.model_dump()
        doc = serialize_review(doc)
        for k in ("events", "rating_history", "ai_candidates", "regeneration_count"):
            if doc.get(k) is None:
                doc.pop(k, None)
        await db.reviews.insert_one(doc)

        # Trigger notification for negative reviews (1-2 stars)
        if input.rating <= 2:
            await send_negative_review_notification(doc)

        return review

    @router.put("/reviews/{review_id}/respond", response_model=Review)
    async def respond_to_review(review_id: str, response: ReviewResponse):
        """Submit a response to a review"""
        review = await db.reviews.find_one({"id": review_id}, {"_id": 0})
        if not review:
            raise HTTPException(status_code=404, detail="Review not found")

        pv = await privacy_check_db(db, response.response_text, review.get("property_id", ""))
        if not pv["ok"]:
            await log_review_event(db, review_id, "publish_blocked_privacy", "user", violations=[v["type"] for v in pv["violations"]])
            raise HTTPException(status_code=400, detail="Gizlilik ihlali — yayın engellendi: " + ", ".join(v["type"] for v in pv["violations"]))
        update_data = {
            "response_text": response.response_text,
            "response_status": "responded",
            "response_date": datetime.now(timezone.utc).isoformat()
        }

        await db.reviews.update_one(
            {"id": review_id},
            {"$set": update_data}
        )
        await log_review_event(db, review_id, "published", "user", channel=review.get("platform"),
                               edited=bool(review.get("ai_candidates")) and response.response_text not in [c.get("text") for c in (review.get("ai_candidates") or [])])

        # Attempt outbound platform sync in the background
        platform = review.get("platform")
        if platform and review.get("external_review_id"):
            asyncio.create_task(_attempt_outbound_sync(platform, review_id, review.get("external_review_id"), response.response_text))

        updated_review = await db.reviews.find_one({"id": review_id}, {"_id": 0})
        deserialize_review(updated_review)
        return updated_review

    async def _attempt_outbound_sync(platform: str, review_id: str, external_review_id: str, reply_text: str):
        """Attempt to post a reply back to the originating platform"""
        try:
            integration = await db.platform_integrations.find_one({"platform": platform}, {"_id": 0})
            if not integration or not integration.get("credentials_configured"):
                await log_sync(db, platform, "outbound", "skipped", f"No credentials configured for {platform}. Configure in Connections > Setup Wizard.", review_id)
                return

            success = False
            error_msg = ""

            if platform == "google":
                # Google Business Profile API - Reply to review
                access_token = integration.get("access_token", "")
                account_id = integration.get("account_id", "")
                location_id = integration.get("location_id", "")
                if access_token and account_id and location_id:
                    try:
                        import httpx
                        url = f"https://mybusiness.googleapis.com/v4/accounts/{account_id}/locations/{location_id}/reviews/{external_review_id}/reply"
                        async with httpx.AsyncClient() as client:
                            resp = await client.put(url,
                                json={"comment": reply_text},
                                headers={"Authorization": f"Bearer {access_token}"},
                                timeout=15)
                            if resp.status_code in (200, 201):
                                success = True
                            else:
                                error_msg = f"Google API {resp.status_code}: {resp.text[:150]}"
                    except Exception as e:
                        error_msg = str(e)[:200]
                else:
                    error_msg = "Missing Google credentials (access_token, account_id, location_id)"

            elif platform == "booking.com":
                # Booking.com Connectivity API
                api_key = integration.get("api_key", "")
                hotel_id = integration.get("hotel_id", "")
                if api_key and hotel_id:
                    try:
                        import httpx
                        url = f"https://supply-xml.booking.com/hotels/xml/reviews"
                        async with httpx.AsyncClient() as client:
                            resp = await client.post(url,
                                json={"hotel_id": hotel_id, "review_id": external_review_id, "response": reply_text},
                                headers={"Authorization": f"Basic {api_key}"},
                                timeout=15)
                            if resp.status_code in (200, 201):
                                success = True
                            else:
                                error_msg = f"Booking.com API {resp.status_code}: {resp.text[:150]}"
                    except Exception as e:
                        error_msg = str(e)[:200]
                else:
                    error_msg = "Missing Booking.com credentials (api_key, hotel_id)"

            elif platform == "tripadvisor":
                # TripAdvisor Management Center API
                api_key = integration.get("api_key", "")
                location_id = integration.get("location_id", "")
                if api_key and location_id:
                    try:
                        import httpx
                        url = f"https://api.tripadvisor.com/api/partner/3.0/location/{location_id}/reviews/{external_review_id}/response"
                        async with httpx.AsyncClient() as client:
                            resp = await client.post(url,
                                json={"response_text": reply_text},
                                headers={"x-tripadvisor-api-key": api_key},
                                timeout=15)
                            if resp.status_code in (200, 201):
                                success = True
                            else:
                                error_msg = f"TripAdvisor API {resp.status_code}: {resp.text[:150]}"
                    except Exception as e:
                        error_msg = str(e)[:200]
                else:
                    error_msg = "Missing TripAdvisor credentials (api_key, location_id)"

            else:
                error_msg = f"Outbound reply not yet supported for {platform}"

            if success:
                await db.reviews.update_one({"id": review_id}, {"$set": {
                    "synced_to_platform": True,
                    "sync_date": datetime.now(timezone.utc).isoformat(),
                    "sync_status": "synced",
                }})
                await log_sync(db, platform, "outbound", "success", f"Reply posted to {platform} for review {external_review_id}", review_id)
            else:
                await db.reviews.update_one({"id": review_id}, {"$set": {
                    "synced_to_platform": False,
                    "sync_status": "failed",
                    "sync_error": error_msg,
                }})
                await log_sync(db, platform, "outbound", "warning", f"Reply sync to {platform} failed: {error_msg}", review_id)
        except Exception as e:
            logger.error(f"Outbound sync error for {platform}: {e}")
            await log_sync(db, platform, "outbound", "error", str(e)[:200], review_id)

    SUPPORTED_LANGUAGES = {
        "auto": "Auto-detect",
        "en": "English",
        "fr": "French",
        "de": "German",
        "es": "Spanish",
        "it": "Italian",
        "pt": "Portuguese",
        "zh": "Chinese",
        "ja": "Japanese",
        "ko": "Korean",
        "ar": "Arabic",
        "ru": "Russian",
        "nl": "Dutch",
        "th": "Thai",
        "hi": "Hindi",
        "tr": "Turkish"
    }

    @router.post("/reviews/generate-ai-response", response_model=AIGenerateResponse)
    async def generate_ai_response(request: AIGenerateRequest):
        """Generate AI response for a review using GPT-5.2 with multi-language support and uniqueness"""
        review = await db.reviews.find_one({"id": request.review_id}, {"_id": 0})
        if not review:
            raise HTTPException(status_code=404, detail="Review not found")

        api_key = os.environ.get("EMERGENT_LLM_KEY")
        if not api_key:
            raise HTTPException(status_code=500, detail="AI service not configured")

        tone_instructions = {
            "professional": "professional, courteous, and business-like",
            "friendly": "warm, friendly, and personable",
            "apologetic": "sincere, apologetic, and solution-focused"
        }

        tone = tone_instructions.get(request.tone, tone_instructions["professional"])

        # Language handling
        lang = request.language
        language_instruction = ""
        if lang == "auto":
            language_instruction = """First, detect the language of the guest's review.
    Then write your entire response in that SAME language the guest used.
    If the review is in English, respond in English. If in French, respond in French. Etc."""
        elif lang == "en":
            language_instruction = "Write your response entirely in English."
        else:
            lang_name = SUPPORTED_LANGUAGES.get(lang, lang)
            language_instruction = f"Write your entire response in {lang_name}."

        # Fetch recent responses for uniqueness context (same property, last 100)
        recent_responses = await db.reviews.find(
            {"response_text": {"$nin": [None, ""]}, "id": {"$ne": request.review_id}, "property_id": review.get("property_id", "default")},
            {"response_text": 1, "_id": 0}
        ).sort("response_date", -1).limit(100).to_list(100)
        recent_texts = [r["response_text"] for r in recent_responses if r.get("response_text")]

        avoid_phrases = ""
        if recent_texts:
            avoid_phrases = "\n\nIMPORTANT: Make this response COMPLETELY UNIQUE. Do NOT reuse any of these opening lines or phrases from recent responses:\n"
            for i, text in enumerate(recent_texts[:3]):
                first_line = text.split('.')[0] if '.' in text else text[:80]
                avoid_phrases += f"- Avoid: \"{first_line}...\"\n"
            avoid_phrases += "Use a fresh, creative opening. Vary your sentence structure. Reference specific details from the guest's review."

        # Review Intelligence (analyze once, reuse)
        analysis = review.get("sentiment_analysis")
        if not analysis or "risk_score" not in analysis:
            analysis = await analyze_sentiment(review.get("review_text", ""), int(review.get("rating") or 3))
            await db.reviews.update_one({"id": request.review_id}, {"$set": {"sentiment_analysis": analysis}})
        cfg = await get_review_agent_cfg(db, review.get("property_id", "default"))
        identity = (cfg.get("sign_off") or "").strip()
        sign_line = f"Sign off exactly as '{identity}' (an authorised real person/team — never invent a name)." if identity and identity != "Yönetim" \
            else "Sign off as 'The Management Team' or similar — never invent a personal name."
        policy_line = ("POLICY: never ask the guest to change/remove the review or rating, never mention room numbers, booking references "
                       "or payment details, never promise a refund unless the hotel explicitly decided so; if the guest raised safety/legal "
                       "issues, invite them to contact management privately.")
        if analysis.get("staff_mentioned"):
            policy_line += f" You may thank staff by first name only if praised: {', '.join(analysis['staff_mentioned'][:3])}."

        def _system(tone_desc: str) -> str:
            return f"""You are a professional hotel manager responding to guest reviews. 
    Your responses should be {tone_desc}.
    Keep responses concise (2-3 paragraphs max).
    Always thank the guest for their feedback.
    If the review is negative, acknowledge their concerns and offer to make things right.
    If positive, express gratitude and invite them back.
    {language_instruction}
    {policy_line}

    CRITICAL: Every response must be UNIQUE and PERSONALIZED. 
    - Reference SPECIFIC details from the review (room type, dates, specific experiences mentioned).
    - Vary your opening line, sentence structure, and sign-off every time.
    - Never use generic phrases like "Thank you for your feedback" as an opener.
    - Be creative and genuine — guests can tell when responses are automated.
    {sign_line}{avoid_phrases}"""

        prompt = f"""Please write a response to this hotel review:

    Platform: {review['platform']}
    Rating: {review['rating']}/5 stars
    Guest: {review['guest_name']}
    Review: {review['review_text']}
    {f"Room: {review.get('room_type', '')}" if review.get('room_type') else ""}
    {f"Stay Date: {review.get('stay_date', '')}" if review.get('stay_date') else ""}

    Write a {tone}, UNIQUE and personalized response. {language_instruction}"""

        async def _one(style: str, tone_desc: str) -> dict:
            chat = LlmChat(api_key=api_key, session_id=f"review-{request.review_id}-{lang}-{style}-{uuid.uuid4().hex[:8]}",
                           system_message=_system(tone_desc)).with_model("openai", "gpt-5.2")
            text = (await chat.send_message(UserMessage(text=prompt))).strip()
            sim = similarity_score(text, recent_texts)
            q = quality_score(text, review, analysis, sim["max_pct"])
            pv = privacy_check(text, staff_surnames)
            if not pv["ok"]:
                q["policy_safety"] = min(q["policy_safety"], 20); q["total"] = min(q["total"], 40)
            return {"style": style, "text": text, "quality": q, "similarity": sim, "privacy": pv}

        staff_surnames = await staff_surnames_db(db)
        variants = [("selected", tone)]
        if request.candidates:
            variants = [("warm", "warm, empathetic and personable"), ("professional", "professional, courteous, and business-like"),
                        ("concise", "concise, direct and sincere (max 4 sentences)")]
        try:
            results = await asyncio.gather(*[_one(s, d) for s, d in variants])
            # regenerate once if best is too similar to history
            best = max(results, key=lambda c: (c["quality"]["total"], -c["similarity"]["max_pct"]))
            if best["similarity"]["action"] == "regenerate":
                retry = await _one(best["style"] + "_regen", tone)
                results.append(retry)
                best = max(results, key=lambda c: (c["quality"]["total"], -c["similarity"]["max_pct"]))
            decision = decide_action(analysis, int(review.get("rating") or 3), best["quality"]["total"], best["similarity"]["max_pct"], cfg)
            if not best["privacy"]["ok"]:
                decision = {**decision, "action": "human_approval" if decision["action"] == "auto_approve" else decision["action"],
                            "reasons": decision["reasons"] + ["privacy"]}
            await db.reviews.update_one({"id": request.review_id, "regeneration_count": None}, {"$set": {"regeneration_count": 0}})
            await db.reviews.update_one({"id": request.review_id}, {
                "$set": {"response_quality": best["quality"], "response_similarity": best["similarity"], "ai_decision": decision,
                         "response_privacy": best["privacy"], "ai_draft": best["text"], "ai_draft_at": datetime.now(timezone.utc).isoformat(),
                         "ai_candidates": [{k: c[k] for k in ("style", "text")} | {"quality": c["quality"]["total"], "similarity": c["similarity"]["max_pct"]} for c in results],
                         "response_uniqueness_hash": __import__("hashlib").md5(best["text"].encode()).hexdigest()[:12]},
                "$inc": {"regeneration_count": 1}})
            await log_review_event(db, request.review_id, "draft_generated", "ai", style=best["style"], quality=best["quality"]["total"],
                                   similarity=best["similarity"]["max_pct"], decision=decision["action"], candidates=len(results))
            return AIGenerateResponse(generated_text=best["text"], detected_language=lang if lang != "auto" else None,
                                      quality=best["quality"], similarity=best["similarity"], decision=decision, analysis=analysis, privacy=best["privacy"],
                                      candidates=[{"style": c["style"], "text": c["text"], "quality": c["quality"]["total"],
                                                   "similarity": c["similarity"]["max_pct"]} for c in results] if request.candidates else None)
        except Exception as e:
            logger.error(f"AI generation error: {str(e)}")
            raise HTTPException(status_code=500, detail=f"AI generation failed: {str(e)}")

    @router.post("/reviews/{review_id}/detect-language")
    async def detect_language(review_id: str):
        """Detect the language of a review using AI"""
        review = await db.reviews.find_one({"id": review_id}, {"_id": 0})
        if not review:
            raise HTTPException(status_code=404, detail="Review not found")

        api_key = os.environ.get("EMERGENT_LLM_KEY")
        if not api_key:
            raise HTTPException(status_code=500, detail="AI service not configured")

        try:
            chat = LlmChat(
                api_key=api_key,
                session_id=f"lang-detect-{review_id}",
                system_message="You are a language detection assistant. Respond ONLY with a JSON object."
            ).with_model("openai", "gpt-5.2")

            prompt = f"""Detect the language of this text and respond ONLY with a JSON object in this exact format:
    {{"code": "en", "name": "English", "confidence": 0.95}}

    Use ISO 639-1 codes. Text:
    "{review['review_text']}" """

            user_message = UserMessage(text=prompt)
            response = await chat.send_message(user_message)

            import json as json_module
            # Parse the response - handle potential markdown wrapping
            clean = response.strip()
            if clean.startswith("```"):
                clean = clean.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

            result = json_module.loads(clean)
            return {
                "code": result.get("code", "en"),
                "name": result.get("name", "English"),
                "confidence": result.get("confidence", 0.9)
            }
        except Exception as e:
            logger.error(f"Language detection error: {str(e)}")
            return {"code": "en", "name": "English", "confidence": 0.5}

    class TranslateRequest(BaseModel):
        text: str
        target_language: str = "en"

    @router.post("/reviews/translate")
    async def translate_text(request: TranslateRequest):
        """Translate text to a target language"""
        api_key = os.environ.get("EMERGENT_LLM_KEY")
        if not api_key:
            raise HTTPException(status_code=500, detail="AI service not configured")

        target_name = SUPPORTED_LANGUAGES.get(request.target_language, "English")

        try:
            chat = LlmChat(
                api_key=api_key,
                session_id=f"translate-{request.target_language}",
                system_message=f"You are a professional translator. Translate the given text to {target_name}. Return ONLY the translated text, nothing else."
            ).with_model("openai", "gpt-5.2")

            user_message = UserMessage(text=f"Translate this to {target_name}:\n\n{request.text}")
            response = await chat.send_message(user_message)

            return {"translated_text": response, "target_language": request.target_language, "target_name": target_name}
        except Exception as e:
            logger.error(f"Translation error: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Translation failed: {str(e)}")

    @router.post("/reviews/batch-auto-respond")
    async def batch_auto_respond(data: Dict = {},
                                 current_user: dict = Depends(require_roles("admin", "manager"))):
        """Batch auto-respond to all unresponded reviews using AI."""
        api_key = os.environ.get("EMERGENT_LLM_KEY")
        if not api_key:
            raise HTTPException(status_code=500, detail="AI service not configured")

        tone = data.get("tone", "professional")
        limit = min(int(data.get("limit", 10)), 20)
        property_id = data.get("property_id")

        query = {"response_status": "pending"}
        if property_id:
            query["property_id"] = property_id

        unresponded = await db.reviews.find(query, {"_id": 0}).sort("created_at", -1).to_list(limit)
        if not unresponded:
            return {"processed": 0, "message": "No unresponded reviews found"}

        tone_map = {
            "professional": "professional, courteous, and business-like",
            "friendly": "warm, friendly, and personable",
            "apologetic": "sincere, apologetic, and solution-focused",
        }
        tone_desc = tone_map.get(tone, tone_map["professional"])

        results = []
        processed = 0
        errors = []

        for review in unresponded:
            try:
                unique_session = f"batch-{review['id']}-{uuid.uuid4().hex[:8]}"
                system_msg = f"""You are a professional hotel manager responding to guest reviews.
Your responses should be {tone_desc}. Keep responses concise (2-3 paragraphs max).
Always thank the guest. If negative, acknowledge concerns and offer to make things right.
If positive, express gratitude and invite them back.
Detect the language of the review and respond in the SAME language.
Every response MUST be UNIQUE and PERSONALIZED — reference specific details from the review.
Never use generic openings. Sign off as 'The Management Team'."""

                prompt = f"""Write a response to this hotel review:
Platform: {review.get('platform', 'Unknown')}
Rating: {review.get('rating', 3)}/5 stars
Guest: {review.get('guest_name', 'Guest')}
Review: {review.get('review_text', '')}
{f"Room: {review.get('room_type', '')}" if review.get('room_type') else ""}
{f"Stay: {review.get('stay_date', '')}" if review.get('stay_date') else ""}"""

                chat = LlmChat(api_key=api_key, session_id=unique_session, system_message=system_msg).with_model("openai", "gpt-5.2")
                response_text = await chat.send_message(UserMessage(text=prompt))

                now_iso = datetime.now(timezone.utc).isoformat()
                await db.reviews.update_one({"id": review["id"]}, {"$set": {
                    "response_text": response_text,
                    "response_status": "responded",
                    "response_date": now_iso,
                    "response_by": current_user.get("name", "AI Auto-Respond"),
                    "response_method": "ai_batch",
                    "response_tone": tone,
                }})

                results.append({
                    "review_id": review["id"],
                    "guest_name": review.get("guest_name", ""),
                    "platform": review.get("platform", ""),
                    "rating": review.get("rating", 0),
                    "response_preview": response_text[:120] + "...",
                    "status": "responded",
                })
                processed += 1
            except Exception as e:
                logger.error(f"Batch respond error for {review.get('id')}: {e}")
                errors.append({"review_id": review.get("id"), "error": str(e)[:80]})

        return {
            "processed": processed,
            "errors": len(errors),
            "error_details": errors,
            "results": results,
            "tone": tone,
        }

    @router.get("/languages")
    async def get_languages():
        """Get supported languages"""
        return [{"code": k, "name": v} for k, v in SUPPORTED_LANGUAGES.items()]

    @router.get("/reviews/stats/summary")
    async def get_review_stats(property_id: Optional[str] = None):
        """Get review statistics summary"""
        query = {}
        if property_id:
            query["property_id"] = property_id

        total = await db.reviews.count_documents(query)
        responded = await db.reviews.count_documents({**query, "response_status": "responded"})
        pending = await db.reviews.count_documents({**query, "response_status": "pending"})
        pending_approval = await db.reviews.count_documents({**query, "response_status": "pending_approval"})

        # Calculate average rating
        match_stage = {"$match": query} if query else {"$match": {}}
        pipeline = [
            match_stage,
            {"$group": {"_id": None, "avg_rating": {"$avg": "$rating"}}}
        ]
        result = await db.reviews.aggregate(pipeline).to_list(1)
        avg_rating = result[0]["avg_rating"] if result else 0

        # Platform breakdown
        platform_pipeline = [
            match_stage,
            {"$group": {"_id": "$platform", "count": {"$sum": 1}}}
        ]
        platform_result = await db.reviews.aggregate(platform_pipeline).to_list(100)
        platforms = {item["_id"]: item["count"] for item in platform_result}

        # Approval Center + AI performance (Review Ops)
        pend = await db.reviews.find({**query, "response_status": "pending_approval"},
                                     {"_id": 0, "sentiment_analysis.risk_level": 1, "sentiment_analysis.spam_suspected": 1, "escalated": 1}).to_list(500)
        risk_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for r in pend:
            risk_counts[(r.get("sentiment_analysis") or {}).get("risk_level", "low")] += 1
        spam_suspected = await db.reviews.count_documents({**query, "sentiment_analysis.spam_suspected": True, "response_status": {"$ne": "responded"}})
        high_risk_open = await db.reviews.count_documents({**query, "sentiment_analysis.risk_level": {"$in": ["high", "critical"]}, "response_status": {"$ne": "responded"}})
        since30 = (datetime.now(timezone.utc) - __import__("datetime").timedelta(days=30)).isoformat()
        qa = await db.reviews.aggregate([{"$match": {**query, "response_quality.total": {"$exists": True}}},
                                         {"$group": {"_id": None, "avg": {"$avg": "$response_quality.total"}, "n": {"$sum": 1},
                                                     "regen": {"$sum": {"$cond": [{"$gt": ["$regeneration_count", 1]}, 1, 0]}},
                                                     "policy_risk": {"$sum": {"$cond": [{"$lt": ["$response_quality.policy_safety", 60]}, 1, 0]}}}}]).to_list(1)
        qa = qa[0] if qa else {"avg": 0, "n": 0, "regen": 0, "policy_risk": 0}
        auto_pub = await db.reviews.count_documents({**query, "response_method": {"$in": ["ai_autopilot", "ai_agent_auto"]}, "response_date": {"$gte": since30}})
        human_pub = await db.reviews.count_documents({**query, "approved_by": {"$exists": True, "$ne": None}, "response_status": "responded", "response_date": {"$gte": since30}})
        tot_pub = auto_pub + human_pub
        approval_center = {
            "risk_counts": risk_counts, "escalated": sum(1 for r in pend if r.get("escalated")),
            "spam_suspected": spam_suspected, "high_risk_open": high_risk_open,
            "ai_performance": {"avg_response_score": round(qa["avg"] or 0), "scored": qa["n"],
                               "auto_approval_rate": round(auto_pub / tot_pub * 100) if tot_pub else 0,
                               "human_approval_rate": round(human_pub / tot_pub * 100) if tot_pub else 0,
                               "regeneration_rate": round(qa["regen"] / qa["n"] * 100) if qa["n"] else 0,
                               "policy_risk_pct": round(qa["policy_risk"] / qa["n"] * 100, 1) if qa["n"] else 0},
        }

        return {
            "total_reviews": total,
            "responded": responded,
            "pending": pending,
            "pending_approval": pending_approval,
            "response_rate": round((responded / total * 100) if total > 0 else 0, 1),
            "average_rating": round(avg_rating, 1) if avg_rating else 0,
            "by_platform": platforms,
            "approval_center": approval_center,
        }

    @router.post("/reviews/seed")
    async def seed_reviews():
        """Seed database with mock reviews for demo purposes"""
        existing = await db.reviews.count_documents({})
        if existing > 0:
            return {"message": f"Database already has {existing} reviews", "seeded": False}

        # Seed default property if not exists
        prop_exists = await db.properties.find_one({"id": "default"})
        if not prop_exists:
            await db.properties.insert_one({
                "id": "default",
                "name": "My Hotel",
                "address": "",
                "city": "",
                "country": "",
                "property_type": "hotel",
                "is_active": True,
                "created_at": datetime.now(timezone.utc).isoformat()
            })

        avatars = [
            "https://images.unsplash.com/photo-1624300862338-94028d2603a5?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjAzOTB8MHwxfHNlYXJjaHwyfHxwZXJzb24lMjBwb3J0cmFpdCUyMG5ldXRyYWwlMjBiYWNrZ3JvdW5kfGVufDB8fHx8MTc3NTgyNjkzN3ww&ixlib=rb-4.1.0&q=85",
            "https://images.unsplash.com/photo-1576997355598-a5a9def46291?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjAzOTB8MHwxfHNlYXJjaHwxfHxwZXJzb24lMjBwb3J0cmFpdCUyMG5ldXRyYWwlMjBiYWNrZ3JvdW5kfGVufDB8fHx8MTc3NTgyNjkzN3ww&ixlib=rb-4.1.0&q=85",
            "https://images.unsplash.com/photo-1770058443069-e384cd001e9b?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjAzOTB8MHwxfHNlYXJjaHw0fHxwZXJzb24lMjBwb3J0cmFpdCUyMG5ldXRyYWwlMjBiYWNrZ3JvdW5kfGVufDB8fHx8MTc3NTgyNjkzN3ww&ixlib=rb-4.1.0&q=85",
            "https://images.pexels.com/photos/6627006/pexels-photo-6627006.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940",
            "https://images.pexels.com/photos/7719379/pexels-photo-7719379.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940"
        ]

        mock_reviews = [
            {
                "platform": "booking.com",
                "guest_name": "Sarah Johnson",
                "guest_avatar": avatars[0],
                "rating": 5,
                "review_text": "Absolutely wonderful stay! The room was immaculate, staff incredibly friendly, and the breakfast buffet exceeded all expectations. The location is perfect for exploring the city. Will definitely be back!",
                "stay_date": "December 2025",
                "room_type": "Deluxe Suite",
                "response_status": "pending"
            },
            {
                "platform": "airbnb",
                "guest_name": "Michael Chen",
                "guest_avatar": avatars[1],
                "rating": 4,
                "review_text": "Great location and comfortable beds. The check-in process was smooth. Only minor issue was the WiFi being a bit slow during peak hours. Otherwise, a pleasant experience overall.",
                "stay_date": "January 2026",
                "room_type": "Standard Room",
                "response_status": "pending"
            },
            {
                "platform": "expedia",
                "guest_name": "Emma Rodriguez",
                "guest_avatar": avatars[2],
                "rating": 3,
                "review_text": "The hotel is decent but room service was quite slow and the air conditioning wasn't working properly. Front desk staff were helpful in trying to resolve issues. Pool area was nice.",
                "stay_date": "January 2026",
                "room_type": "Premium Room",
                "response_status": "pending"
            },
            {
                "platform": "tripadvisor",
                "guest_name": "James Wilson",
                "guest_avatar": avatars[3],
                "rating": 5,
                "review_text": "Outstanding hotel! From the moment we arrived, we were treated like royalty. The spa facilities are world-class and the rooftop restaurant has amazing views. Highly recommend the seafood platter!",
                "stay_date": "December 2025",
                "room_type": "Executive Suite",
                "response_status": "responded",
                "response_text": "Dear James, thank you so much for your wonderful review! We're thrilled to hear you enjoyed your stay with us. Our team works hard to create memorable experiences, and it's always rewarding to receive such positive feedback. We look forward to welcoming you back soon! - The Management Team"
            },
            {
                "platform": "google",
                "guest_name": "Lisa Anderson",
                "guest_avatar": avatars[4],
                "rating": 2,
                "review_text": "Disappointed with my stay. The room wasn't ready at check-in time despite confirming in advance. Noise from the street made it hard to sleep. Expected more for the price paid.",
                "stay_date": "January 2026",
                "room_type": "City View Room",
                "response_status": "pending"
            },
            {
                "platform": "trip.com",
                "guest_name": "David Kim",
                "guest_avatar": avatars[0],
                "rating": 4,
                "review_text": "Solid choice for business travelers. Clean rooms, fast WiFi, and convenient location near the business district. The gym is well-equipped. Would appreciate more power outlets near the desk.",
                "stay_date": "January 2026",
                "room_type": "Business Suite",
                "response_status": "pending"
            },
            {
                "platform": "booking.com",
                "guest_name": "Anna Martinez",
                "guest_avatar": avatars[1],
                "rating": 5,
                "review_text": "Perfect family vacation! The kids loved the pool and the staff arranged wonderful activities. Rooms were spacious enough for our family of four. Breakfast had great variety for picky eaters.",
                "stay_date": "December 2025",
                "room_type": "Family Suite",
                "response_status": "responded",
                "response_text": "Dear Anna, what a pleasure it was to host your family! We're so glad the children had a wonderful time at the pool. Family happiness is our priority, and we're delighted we could contribute to your vacation memories. Can't wait to see you all again! - The Management Team"
            },
            {
                "platform": "airbnb",
                "guest_name": "Robert Brown",
                "guest_avatar": avatars[2],
                "rating": 1,
                "review_text": "Very disappointing experience. Found hair in the bathroom, the minibar was missing items that were charged to my bill, and housekeeping never came despite multiple requests. Will not return.",
                "stay_date": "January 2026",
                "room_type": "Standard Room",
                "response_status": "pending"
            },
            {
                "platform": "tripadvisor",
                "guest_name": "Jennifer Lee",
                "guest_avatar": avatars[3],
                "rating": 4,
                "review_text": "Lovely boutique hotel with character. The room decor was charming and unique. Breakfast could use more healthy options. Staff remembered our names which was a nice personal touch.",
                "stay_date": "December 2025",
                "room_type": "Boutique Room",
                "response_status": "pending"
            },
            {
                "platform": "google",
                "guest_name": "Thomas Wright",
                "guest_avatar": avatars[4],
                "rating": 5,
                "review_text": "Celebrated our anniversary here and the team made it unforgettable! Champagne in the room, special dinner arrangement, and the most beautiful room decoration. True five-star service!",
                "stay_date": "December 2025",
                "room_type": "Honeymoon Suite",
                "response_status": "pending"
            }
        ]

        for review_data in mock_reviews:
            review = Review(**review_data)
            doc = review.model_dump()
            doc = serialize_review(doc)
            await db.reviews.insert_one(doc)

        return {"message": f"Seeded {len(mock_reviews)} mock reviews", "seeded": True}

    @router.delete("/reviews/clear")
    async def clear_reviews():
        """Clear all reviews (for testing)"""
        result = await db.reviews.delete_many({})
        return {"message": f"Deleted {result.deleted_count} reviews"}

    # ==================== NOTIFICATION SETTINGS ROUTES ====================

    @router.get("/notifications/settings")
    async def get_notification_settings():
        """Get current notification settings"""
        settings = await db.notification_settings.find_one({}, {"_id": 0})
        if not settings:
            # Return default settings
            return {
                "id": None,
                "email": NOTIFICATION_EMAIL or "",
                "notify_negative_reviews": True,
                "negative_threshold": 2,
                "enabled": False,
                "message": "Notification settings not configured. Update to enable."
            }
        return settings

    @router.put("/notifications/settings")
    async def update_notification_settings(settings: NotificationSettingsUpdate):
        """Update notification settings"""
        existing = await db.notification_settings.find_one({}, {"_id": 0})

        if existing:
            update_data = {k: v for k, v in settings.model_dump().items() if v is not None}
            if update_data:
                await db.notification_settings.update_one(
                    {"id": existing["id"]},
                    {"$set": update_data}
                )
            updated = await db.notification_settings.find_one({}, {"_id": 0})
            return updated
        else:
            # Create new settings
            new_settings = NotificationSettings(
                email=settings.email or NOTIFICATION_EMAIL or "",
                notify_negative_reviews=settings.notify_negative_reviews if settings.notify_negative_reviews is not None else True,
                negative_threshold=settings.negative_threshold if settings.negative_threshold is not None else 2,
                enabled=settings.enabled if settings.enabled is not None else True
            )
            doc = new_settings.model_dump()
            doc['created_at'] = doc['created_at'].isoformat()
            await db.notification_settings.insert_one(doc)
            return new_settings

    @router.get("/notifications/log")
    async def get_notification_log():
        """Get notification history"""
        logs = await db.notification_log.find({}, {"_id": 0}).sort("created_at", -1).to_list(100)
        return logs

    @router.post("/notifications/test")
    async def test_notification():
        """Send a test notification email"""
        settings = await db.notification_settings.find_one({}, {"_id": 0})

        if not settings or not settings.get('enabled'):
            raise HTTPException(status_code=400, detail="Notifications not enabled. Configure settings first.")

        test_review = {
            "id": "test-notification",
            "platform": "google",
            "guest_name": "Test Guest",
            "rating": 1,
            "review_text": "This is a test notification to verify your email alerts are working correctly.",
            "room_type": "Test Room",
            "stay_date": "Test Date"
        }

        success = await send_negative_review_notification(test_review)

        if success:
            return {"status": "success", "message": f"Test notification sent to {settings.get('email')}"}
        else:
            raise HTTPException(status_code=500, detail="Failed to send test notification")

    # ==================== RESPONSE TEMPLATES ROUTES ====================

    @router.get("/templates", response_model=List[ResponseTemplate])
    async def get_templates(category: Optional[str] = None):
        """Get all response templates with optional category filter"""
        query = {}
        if category and category != "all":
            query["category"] = category

        templates = await db.response_templates.find(query, {"_id": 0}).sort("usage_count", -1).to_list(100)
        for template in templates:
            if isinstance(template.get('created_at'), str):
                template['created_at'] = datetime.fromisoformat(template['created_at'])
        return templates

    @router.get("/templates/{template_id}", response_model=ResponseTemplate)
    async def get_template(template_id: str):
        """Get a single template by ID"""
        template = await db.response_templates.find_one({"id": template_id}, {"_id": 0})
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
        if isinstance(template.get('created_at'), str):
            template['created_at'] = datetime.fromisoformat(template['created_at'])
        return template

    @router.post("/templates", response_model=ResponseTemplate)
    async def create_template(input: ResponseTemplateCreate):
        """Create a new response template"""
        template = ResponseTemplate(**input.model_dump())
        doc = template.model_dump()
        doc['created_at'] = doc['created_at'].isoformat()
        await db.response_templates.insert_one(doc)
        return template

    @router.put("/templates/{template_id}", response_model=ResponseTemplate)
    async def update_template(template_id: str, input: ResponseTemplateUpdate):
        """Update an existing template"""
        template = await db.response_templates.find_one({"id": template_id}, {"_id": 0})
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")

        update_data = {k: v for k, v in input.model_dump().items() if v is not None}
        if update_data:
            await db.response_templates.update_one(
                {"id": template_id},
                {"$set": update_data}
            )

        updated = await db.response_templates.find_one({"id": template_id}, {"_id": 0})
        if isinstance(updated.get('created_at'), str):
            updated['created_at'] = datetime.fromisoformat(updated['created_at'])
        return updated

    @router.delete("/templates/{template_id}")
    async def delete_template(template_id: str):
        """Delete a template"""
        result = await db.response_templates.delete_one({"id": template_id})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Template not found")
        return {"message": "Template deleted"}

    @router.post("/templates/{template_id}/use")
    async def use_template(template_id: str):
        """Increment usage count when a template is used"""
        template = await db.response_templates.find_one({"id": template_id}, {"_id": 0})
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")

        await db.response_templates.update_one(
            {"id": template_id},
            {"$inc": {"usage_count": 1}}
        )

        updated = await db.response_templates.find_one({"id": template_id}, {"_id": 0})
        return {"message": "Template usage recorded", "usage_count": updated.get("usage_count", 0)}

    @router.post("/templates/seed")
    async def seed_templates():
        """Seed database with default response templates"""
        existing = await db.response_templates.count_documents({})
        if existing > 0:
            return {"message": f"Database already has {existing} templates", "seeded": False}

        default_templates = [
            {
                "name": "Thank You - Excellent Stay",
                "category": "positive",
                "tone": "friendly",
                "content": "Dear {guest_name},\n\nThank you so much for your wonderful review and for choosing to stay with us! We're absolutely delighted to hear that you had an excellent experience.\n\nYour kind words mean the world to our team, and we're thrilled that we could make your stay memorable. We truly appreciate you taking the time to share your feedback.\n\nWe look forward to welcoming you back soon!\n\nWarm regards,\nThe Management Team"
            },
            {
                "name": "Appreciation - Great Service",
                "category": "praise",
                "tone": "professional",
                "content": "Dear {guest_name},\n\nThank you for your generous review and for recognizing our team's dedication to providing exceptional service.\n\nWe're committed to ensuring every guest feels valued and comfortable during their stay. Your feedback encourages us to continue striving for excellence.\n\nWe hope to have the pleasure of hosting you again in the future.\n\nBest regards,\nThe Management Team"
            },
            {
                "name": "Apology - Service Issue",
                "category": "complaint",
                "tone": "apologetic",
                "content": "Dear {guest_name},\n\nThank you for taking the time to share your feedback. We sincerely apologize that your experience did not meet your expectations.\n\nYour concerns have been brought to the attention of our management team, and we are taking immediate steps to address the issues you've raised. We take all feedback seriously as it helps us improve.\n\nWe would appreciate the opportunity to make things right. Please contact us directly at your convenience so we can discuss how we can better serve you in the future.\n\nWith sincere apologies,\nThe Management Team"
            },
            {
                "name": "Apology - Cleanliness Concern",
                "category": "negative",
                "tone": "apologetic",
                "content": "Dear {guest_name},\n\nThank you for bringing this matter to our attention. We sincerely apologize for the cleanliness issues you experienced during your stay.\n\nMaintaining high standards of cleanliness is a top priority for us, and we are deeply sorry that we fell short on this occasion. We have addressed this with our housekeeping team and implemented additional quality checks.\n\nWe value your feedback and would be grateful for another opportunity to provide you with the exceptional experience you deserve.\n\nWith our sincere apologies,\nThe Management Team"
            },
            {
                "name": "Response - Room Issues",
                "category": "complaint",
                "tone": "apologetic",
                "content": "Dear {guest_name},\n\nThank you for your feedback regarding your recent stay. We apologize for any inconvenience caused by the room issues you mentioned.\n\nWe have immediately notified our maintenance team to inspect and resolve the problems you described. Guest comfort is our priority, and we regret that we did not meet your expectations.\n\nWe would love to welcome you back and show you the true quality of our accommodation. Please reach out to us directly if you'd like to discuss this further.\n\nSincerely,\nThe Management Team"
            },
            {
                "name": "Neutral - Mixed Review",
                "category": "neutral",
                "tone": "professional",
                "content": "Dear {guest_name},\n\nThank you for sharing your balanced feedback about your stay with us. We appreciate you highlighting both the positives and areas where we can improve.\n\nWe're pleased that some aspects of your stay met your expectations, and we take your constructive feedback seriously. Our team is always working to enhance the guest experience.\n\nWe hope to welcome you back and exceed your expectations on your next visit.\n\nBest regards,\nThe Management Team"
            }
        ]

        for template_data in default_templates:
            template = ResponseTemplate(**template_data)
            doc = template.model_dump()
            doc['created_at'] = doc['created_at'].isoformat()
            await db.response_templates.insert_one(doc)

        return {"message": f"Seeded {len(default_templates)} default templates", "seeded": True}

    # ==================== SENTIMENT & ANALYTICS ROUTES ====================

    router.analyze_sentiment = analyze_sentiment

    @router.post("/reviews/{review_id}/analyze")
    async def analyze_review_sentiment(review_id: str):
        """Analyze sentiment of a specific review"""
        review = await db.reviews.find_one({"id": review_id}, {"_id": 0})
        if not review:
            raise HTTPException(status_code=404, detail="Review not found")

        analysis = await analyze_sentiment(review['review_text'], review['rating'])

        # Store analysis with review
        await db.reviews.update_one(
            {"id": review_id},
            {"$set": {"sentiment_analysis": analysis}}
        )

        # Find matching templates based on suggested category
        matching_templates = await db.response_templates.find(
            {"category": analysis.get("suggested_category", "neutral")},
            {"_id": 0}
        ).sort("usage_count", -1).to_list(3)

        return {
            "analysis": analysis,
            "suggested_templates": matching_templates
        }

    @router.post("/reviews/analyze-batch")
    async def analyze_reviews_batch():
        """Analyze sentiment for all reviews without analysis"""
        reviews = await db.reviews.find(
            {"sentiment_analysis": {"$exists": False}},
            {"_id": 0}
        ).to_list(100)

        analyzed_count = 0
        for review in reviews:
            try:
                analysis = await analyze_sentiment(review['review_text'], review['rating'])
                await db.reviews.update_one(
                    {"id": review['id']},
                    {"$set": {"sentiment_analysis": analysis}}
                )
                analyzed_count += 1
            except Exception as e:
                logger.error(f"Error analyzing review {review['id']}: {str(e)}")

        return {"message": f"Analyzed {analyzed_count} reviews", "total": len(reviews)}

    @router.get("/analytics/dashboard")
    async def get_analytics_dashboard():
        """Get comprehensive analytics dashboard data"""
        # Basic stats
        total_reviews = await db.reviews.count_documents({})
        responded = await db.reviews.count_documents({"response_status": "responded"})
        pending = await db.reviews.count_documents({"response_status": "pending"})

        # Average rating
        rating_pipeline = [
            {"$group": {"_id": None, "avg_rating": {"$avg": "$rating"}}}
        ]
        rating_result = await db.reviews.aggregate(rating_pipeline).to_list(1)
        avg_rating = round(rating_result[0]["avg_rating"], 2) if rating_result else 0

        # Rating distribution
        rating_dist_pipeline = [
            {"$group": {"_id": "$rating", "count": {"$sum": 1}}},
            {"$sort": {"_id": 1}}
        ]
        rating_dist = await db.reviews.aggregate(rating_dist_pipeline).to_list(10)
        rating_distribution = {item["_id"]: item["count"] for item in rating_dist}

        # Sentiment distribution (from analyzed reviews)
        sentiment_pipeline = [
            {"$match": {"sentiment_analysis": {"$exists": True}}},
            {"$group": {"_id": "$sentiment_analysis.sentiment", "count": {"$sum": 1}}}
        ]
        sentiment_result = await db.reviews.aggregate(sentiment_pipeline).to_list(10)
        sentiment_distribution = {item["_id"]: item["count"] for item in sentiment_result if item["_id"]}

        # Platform distribution
        platform_pipeline = [
            {"$group": {"_id": "$platform", "count": {"$sum": 1}, "avg_rating": {"$avg": "$rating"}}}
        ]
        platform_result = await db.reviews.aggregate(platform_pipeline).to_list(10)
        platform_stats = [
            {"platform": item["_id"], "count": item["count"], "avg_rating": round(item["avg_rating"], 2)}
            for item in platform_result
        ]

        # Urgency breakdown (from analyzed reviews)
        urgency_pipeline = [
            {"$match": {"sentiment_analysis.urgency": {"$exists": True}}},
            {"$group": {"_id": "$sentiment_analysis.urgency", "count": {"$sum": 1}}}
        ]
        urgency_result = await db.reviews.aggregate(urgency_pipeline).to_list(10)
        urgency_distribution = {item["_id"]: item["count"] for item in urgency_result if item["_id"]}

        # Top mentioned topics
        topic_pipeline = [
            {"$match": {"sentiment_analysis.topics": {"$exists": True}}},
            {"$unwind": "$sentiment_analysis.topics"},
            {"$group": {"_id": "$sentiment_analysis.topics", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 10}
        ]
        topic_result = await db.reviews.aggregate(topic_pipeline).to_list(10)
        top_topics = [{"topic": item["_id"], "count": item["count"]} for item in topic_result]

        # Common issues and praises
        issues_pipeline = [
            {"$match": {"sentiment_analysis.key_issues": {"$exists": True}}},
            {"$unwind": "$sentiment_analysis.key_issues"},
            {"$group": {"_id": "$sentiment_analysis.key_issues", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 5}
        ]
        issues_result = await db.reviews.aggregate(issues_pipeline).to_list(5)
        common_issues = [{"issue": item["_id"], "count": item["count"]} for item in issues_result]

        praises_pipeline = [
            {"$match": {"sentiment_analysis.key_praises": {"$exists": True}}},
            {"$unwind": "$sentiment_analysis.key_praises"},
            {"$group": {"_id": "$sentiment_analysis.key_praises", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 5}
        ]
        praises_result = await db.reviews.aggregate(praises_pipeline).to_list(5)
        common_praises = [{"praise": item["_id"], "count": item["count"]} for item in praises_result]

        # Response rate calculation
        response_rate = round((responded / total_reviews * 100) if total_reviews > 0 else 0, 1)

        # Priority queue - urgent reviews needing attention
        priority_reviews = await db.reviews.find(
            {
                "response_status": "pending",
                "$or": [
                    {"rating": {"$lte": 2}},
                    {"sentiment_analysis.urgency": {"$in": ["high", "critical"]}}
                ]
            },
            {"_id": 0}
        ).sort("rating", 1).to_list(10)

        for review in priority_reviews:
            deserialize_review(review)

        return {
            "overview": {
                "total_reviews": total_reviews,
                "responded": responded,
                "pending": pending,
                "response_rate": response_rate,
                "avg_rating": avg_rating
            },
            "rating_distribution": rating_distribution,
            "sentiment_distribution": sentiment_distribution,
            "urgency_distribution": urgency_distribution,
            "platform_stats": platform_stats,
            "top_topics": top_topics,
            "common_issues": common_issues,
            "common_praises": common_praises,
            "priority_queue": priority_reviews,
            "staff_intelligence": await staff_intelligence(db, "all", 90),
            "root_cause": await root_cause(db, "all", 30),
        }

    # ==================== COMPETITOR ROUTES ====================

    @router.get("/competitors")
    async def get_competitors():
        """Get all competitor data"""
        competitors = await db.competitors.find({}, {"_id": 0}).to_list(100)
        for comp in competitors:
            if isinstance(comp.get('last_updated'), str):
                comp['last_updated'] = datetime.fromisoformat(comp['last_updated'])
        return competitors

    @router.post("/competitors")
    async def add_competitor(input: CompetitorCreate):
        """Add a competitor for benchmarking"""
        competitor = CompetitorData(**input.model_dump())
        doc = competitor.model_dump()
        doc['last_updated'] = doc['last_updated'].isoformat()
        await db.competitors.insert_one(doc)
        return competitor

    @router.put("/competitors/{competitor_id}")
    async def update_competitor(competitor_id: str, input: CompetitorUpdate):
        """Update competitor data"""
        existing = await db.competitors.find_one({"id": competitor_id}, {"_id": 0})
        if not existing:
            raise HTTPException(status_code=404, detail="Competitor not found")

        update_data = {k: v for k, v in input.model_dump().items() if v is not None}
        update_data['last_updated'] = datetime.now(timezone.utc).isoformat()

        await db.competitors.update_one(
            {"id": competitor_id},
            {"$set": update_data}
        )

        updated = await db.competitors.find_one({"id": competitor_id}, {"_id": 0})
        return updated

    @router.delete("/competitors/{competitor_id}")
    async def delete_competitor(competitor_id: str):
        """Delete a competitor"""
        result = await db.competitors.delete_one({"id": competitor_id})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Competitor not found")
        return {"message": "Competitor deleted"}

    @router.get("/competitors/benchmark")
    async def get_competitor_benchmark():
        """Get benchmark comparison with competitors"""
        # Get our stats
        our_stats = await get_review_stats_internal()

        # Get competitors
        competitors = await db.competitors.find({}, {"_id": 0}).to_list(100)

        benchmark = {
            "your_hotel": {
                "avg_rating": our_stats.get("average_rating", 0),
                "total_reviews": our_stats.get("total_reviews", 0),
                "response_rate": our_stats.get("response_rate", 0)
            },
            "competitors": competitors,
            "ranking": {
                "rating_rank": 1,
                "response_rate_rank": 1
            }
        }

        # Calculate rankings
        all_ratings = [our_stats.get("average_rating", 0)] + [c.get("avg_rating", 0) for c in competitors]
        all_response_rates = [our_stats.get("response_rate", 0)] + [c.get("response_rate", 0) for c in competitors]

        all_ratings.sort(reverse=True)
        all_response_rates.sort(reverse=True)

        benchmark["ranking"]["rating_rank"] = all_ratings.index(our_stats.get("average_rating", 0)) + 1
        benchmark["ranking"]["response_rate_rank"] = all_response_rates.index(our_stats.get("response_rate", 0)) + 1
        benchmark["ranking"]["total_competitors"] = len(competitors) + 1

        return benchmark

    @router.post("/competitors/seed")
    async def seed_competitors():
        """Seed demo competitor data"""
        existing = await db.competitors.count_documents({})
        if existing > 0:
            return {"message": f"Database already has {existing} competitors", "seeded": False}

        demo_competitors = [
            {"name": "Grand Hotel Plaza", "platform": "all", "avg_rating": 4.2, "total_reviews": 1250, "response_rate": 78.5},
            {"name": "Seaside Resort & Spa", "platform": "all", "avg_rating": 4.5, "total_reviews": 890, "response_rate": 92.0},
            {"name": "City Center Inn", "platform": "all", "avg_rating": 3.8, "total_reviews": 2100, "response_rate": 45.0},
            {"name": "Mountain View Lodge", "platform": "all", "avg_rating": 4.0, "total_reviews": 560, "response_rate": 85.0},
            {"name": "Airport Express Hotel", "platform": "all", "avg_rating": 3.5, "total_reviews": 3200, "response_rate": 30.0}
        ]

        for comp_data in demo_competitors:
            competitor = CompetitorData(**comp_data)
            doc = competitor.model_dump()
            doc['last_updated'] = doc['last_updated'].isoformat()
            await db.competitors.insert_one(doc)

        return {"message": f"Seeded {len(demo_competitors)} competitors", "seeded": True}

    # Helper function used by benchmark (renamed to avoid conflict with API endpoint)
    async def get_review_stats_internal():
        """Get review statistics"""
        total = await db.reviews.count_documents({})
        responded = await db.reviews.count_documents({"response_status": "responded"})

        pipeline = [
            {"$group": {"_id": None, "avg_rating": {"$avg": "$rating"}}}
        ]
        result = await db.reviews.aggregate(pipeline).to_list(1)
        avg_rating = result[0]["avg_rating"] if result else 0

        return {
            "total_reviews": total,
            "responded": responded,
            "response_rate": round((responded / total * 100) if total > 0 else 0, 1),
            "average_rating": round(avg_rating, 1) if avg_rating else 0
        }


    return router
