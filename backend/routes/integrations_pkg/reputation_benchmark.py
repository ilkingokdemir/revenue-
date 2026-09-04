"""
Reputation Benchmark — rakip otellerin Google puanlarını takip et, kıyasla.

GOOGLE_PLACES_API_KEY varsa gerçek rating/userRatingCount; yoksa deterministik
SIMULATED değerler. Günlük snapshot → trend. GuestRevu paritesi (5 rakip).
"""
from datetime import datetime, timedelta, timezone
import asyncio
import hashlib
import re
import logging
import os
import uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request

logger = logging.getLogger(__name__)

_BENCH = {}


async def run_reputation_scan(property_id: str = "all") -> dict:
    fn = _BENCH.get("fn")
    if not fn:
        return {"error": "reputation router not initialized"}
    return await fn(property_id)


def create_reputation_router(db, require_roles):
    router = APIRouter()

    def _now():
        return datetime.now(timezone.utc).isoformat()

    def _sim_rating(name: str):
        h = int(hashlib.sha1(f"{name}{datetime.now().strftime('%Y-%W')}".encode()).hexdigest(), 16)
        return round(3.4 + (h % 140) / 100, 1), 150 + (h % 900)

    async def _fetch_rating(place_id: str, name: str):
        api_key = os.environ.get("GOOGLE_PLACES_API_KEY", "")
        if api_key and place_id:
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    r = await client.get(
                        f"https://places.googleapis.com/v1/places/{place_id}",
                        headers={"X-Goog-Api-Key": api_key,
                                 "X-Goog-FieldMask": "rating,userRatingCount"})
                if r.status_code == 200:
                    d = r.json()
                    return d.get("rating"), d.get("userRatingCount"), "live"
            except Exception as e:
                logger.warning(f"places rating fetch failed: {e}")
        rating, count = _sim_rating(name)
        return rating, count, "simulated"

    async def _self_rating(pid: str):
        agg = await db.reviews.aggregate([
            {"$match": {"property_id": pid, "rating": {"$type": ["int", "double", "long"]}}},
            {"$group": {"_id": None, "avg": {"$avg": "$rating"}, "n": {"$sum": 1}}},
        ]).to_list(1)
        return (round(agg[0]["avg"], 1), agg[0]["n"]) if agg else (None, 0)

    TOPIC_KW = {
        "cleanliness": r"clean|dirty|temiz|kirli|sauber|schmutz|hygien",
        "staff": r"staff|receptionist|personel|çalışan|friendly|rude|mitarbeiter|freundlich",
        "breakfast": r"breakfast|kahvaltı|frühstück",
        "check-in": r"check[- ]?in|giriş|anreise|reception|wait",
        "location": r"location|konum|lage|central|metro",
        "value": r"value|price|expensive|cheap|fiyat|pahalı|preis|teuer",
        "noise": r"noise|noisy|loud|gürültü|laut|quiet",
        "wifi": r"wifi|wi-fi|internet",
    }

    def _topic_scores_from_texts(items):
        """items: [(rating, text)] → topic → avg rating (keyword eşleşmesi)."""
        acc = {t: [] for t in TOPIC_KW}
        for rating, text in items:
            tl = (text or "").lower()
            for t, kw in TOPIC_KW.items():
                if re.search(kw, tl):
                    acc[t].append(float(rating or 0))
        return {t: (round(sum(v) / len(v), 1) if v else None, len(v)) for t, v in acc.items()}

    async def _fetch_competitor_texts(place_id: str):
        api_key = os.environ.get("GOOGLE_PLACES_API_KEY", "")
        if not (api_key and place_id):
            return None
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(f"https://places.googleapis.com/v1/places/{place_id}",
                            headers={"X-Goog-Api-Key": api_key, "X-Goog-FieldMask": "reviews"})
            r.raise_for_status()
        return [(rv.get("rating"), (rv.get("text") or {}).get("text", "")) for rv in r.json().get("reviews", [])]

    AMENITY_KW = {
        "pool": r"\bpool|havuz|schwimmbad", "spa": r"\bspa\b|sauna|hamam|massage|masaj", "gym": r"\bgym|fitness|spor salonu",
        "rooftop bar": r"rooftop|çatı|dachterrasse|bar\b", "free parking": r"free parking|ücretsiz otopark|kostenlos.*park",
        "airport shuttle": r"shuttle|transfer|airport pick", "late checkout": r"late check[- ]?out|geç çıkış",
        "pet friendly": r"pet|dog|köpek|hund", "kids club": r"kids|children|çocuk|kinder", "ev charging": r"\bev\b|charging|şarj",
        "restaurant": r"restaurant|dinner|akşam yemeği", "room service": r"room service|oda servisi", "balcony": r"balcony|balkon|terrace|teras",
        "sea view": r"sea view|deniz manzara|meerblick|view\b", "free breakfast": r"free breakfast|breakfast included|kahvaltı dahil",
        "bathtub": r"bathtub|jacuzzi|küvet", "nespresso": r"nespresso|coffee machine|kahve makinesi", "welcome drink": r"welcome drink|hoş ?geldin",
    }
    POS_KW, NEG_KW = r"great|amazing|excellent|love|perfect|wonderful|harika|mükemmel|süper|toll|super|fantastic|best|nice|good", \
                     r"bad|poor|terrible|dirty|rude|slow|noisy|kötü|berbat|kirli|yavaş|schlecht|dreckig|worst|disappoint"

    def _sim_competitor_reviews(name: str):
        """Places API yoksa deterministik örnek yorum seti (SIMULATED)."""
        seeds = [("Great rooftop bar and free parking, staff were amazing.", 5), ("Pool was lovely, breakfast included and excellent.", 5),
                 ("Room was dirty and check-in slow.", 2), ("Nice spa and sauna, but noisy at night.", 3),
                 ("Late checkout allowed, very friendly reception.", 4), ("Airport shuttle was convenient; wifi poor.", 4),
                 ("Pet friendly and good location, restaurant disappointing.", 3), ("Balcony with sea view, perfect stay.", 5)]
        h = int(hashlib.sha1(name.encode()).hexdigest(), 16)
        return [(r, t) for i, (t, r) in enumerate(seeds) if (h >> i) & 1 or i < 3]

    def _extract(texts):
        strengths, weaknesses, amen = {}, {}, {}
        for rating, text in texts:
            tl = (text or "").lower()
            pos = float(rating or 0) >= 4 or re.search(POS_KW, tl)
            neg = float(rating or 0) <= 2 or re.search(NEG_KW, tl)
            for t, kw in TOPIC_KW.items():
                if re.search(kw, tl):
                    (strengths if pos and not neg else weaknesses if neg else strengths)[t] = (strengths if pos and not neg else weaknesses if neg else strengths).get(t, 0) + 1
            for a, kw in AMENITY_KW.items():
                if re.search(kw, tl) and not neg:
                    amen[a] = amen.get(a, 0) + 1
        return strengths, weaknesses, amen

    @router.get("/reputation/competitor-intel/{property_id}")
    async def competitor_intel(property_id: str, days: int = 180, _: dict = Depends(require_roles("admin", "manager"))):
        """Rakip yorumlarından güçlü/zayıf yanlar + 'onlarda var bizde yok' (olanak/konu) listesi."""
        cfg = await db.reputation_config.find_one({"property_id": property_id}, {"_id": 0}) or {}
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        pq = {"property_id": property_id} if property_id != "all" else {}
        ours = [(r.get("rating"), r.get("review_text", "")) for r in await db.reviews.find({**pq, "created_at": {"$gte": since}}, {"_id": 0, "rating": 1, "review_text": 1}).to_list(3000)]
        our_str, our_weak, our_amen = _extract(ours)
        prop = await db.properties.find_one({"id": property_id}, {"_id": 0, "amenities": 1}) or {}
        our_amenities = {str(a).lower() for a in (prop.get("amenities") or [])} | set(our_amen)
        comps, gap_count = [], {}
        for comp in (cfg.get("competitors") or [])[:5]:
            texts, mode = None, "simulated"
            try:
                texts = await _fetch_competitor_texts(comp.get("place_id", ""))
                if texts: mode = "live"
            except Exception as e:
                logger.warning(f"competitor-intel places fail: {e}")
            texts = texts or _sim_competitor_reviews(comp.get("name", "x"))
            st, wk, am = _extract(texts)
            they_have = [a for a in am if not any(a in o or o in a for o in our_amenities)]
            for a in they_have: gap_count[a] = gap_count.get(a, 0) + 1
            comps.append({"name": comp.get("name", ""), "mode": mode, "reviews_analyzed": len(texts),
                          "strengths": sorted(st, key=lambda k: -st[k])[:5], "weaknesses": sorted(wk, key=lambda k: -wk[k])[:5],
                          "amenities_praised": sorted(am, key=lambda k: -am[k])[:8], "they_have_we_dont": they_have})
        they_have_we_dont = [{"item": a, "competitors": n, "action": f"'{a}' rakiplerin {n} tanesinde övülüyor; sunuyorsanız web sitesi/OTA listesine ve ön varış e-postasına ekleyin, sunmuyorsanız fizibilite değerlendirin."}
                             for a, n in sorted(gap_count.items(), key=lambda x: -x[1])]
        our_topics_weak = [t for t in our_weak if our_weak[t] > our_str.get(t, 0)]
        their_strong_our_weak = sorted({t for c in comps for t in c["strengths"]} & set(our_topics_weak))
        return {"property_id": property_id, "days": days, "mode": "live" if any(c["mode"] == "live" for c in comps) else "simulated",
                "competitors": comps, "they_have_we_dont": they_have_we_dont, "their_strength_our_weakness": their_strong_our_weak,
                "our_weak_topics": our_topics_weak, "our_strong_topics": sorted(our_str, key=lambda k: -our_str[k])[:5],
                "insight": (f"Rakipler {', '.join(their_strong_our_weak)} konularında güçlü, biz zayıfız." if their_strong_our_weak else "Rakiplerin güçlü olduğu konularda zayıf noktamız yok.")
                           + (f" Onlarda var bizde yok: {', '.join(x['item'] for x in they_have_we_dont[:4])}." if they_have_we_dont else "")}

    @router.post("/reputation/competitor-intel/{property_id}/act")
    async def competitor_intel_act(property_id: str, body: dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        """'Onlarda var bizde yok' → add_amenity (properties.amenities + widget/OTA listesi) | feasibility_task (staff_tasks source competitor_gap)."""
        item = str(body.get("item") or "").strip().lower()
        action = body.get("action")
        if not item or action not in ("add_amenity", "feasibility_task"):
            raise HTTPException(400, "item ve action (add_amenity | feasibility_task) gerekli")
        now = datetime.now(timezone.utc).isoformat()
        who = current_user.get("name", current_user.get("email", ""))
        if action == "add_amenity":
            r = await db.properties.update_one({"id": property_id}, {"$addToSet": {"amenities": item}, "$set": {"updated_at": now}})
            await db.amenity_changes.insert_one({"id": str(uuid.uuid4()), "property_id": property_id, "amenity": item, "source": "competitor_gap",
                                                 "by": who, "created_at": now, "channels": ["website_widget", "ota_listing"]})
            return {"ok": True, "action": "add_amenity", "item": item, "matched": r.matched_count,
                    "note": "Olanak web sitesi/OTA olanak listesine eklendi (properties.amenities). OTA senkronu bir sonraki listing push'unda gider."}
        exists = await db.staff_tasks.find_one({"property_id": property_id, "source": "competitor_gap", "topic": item,
                                                "status": {"$nin": ["done", "resolved", "completed", "closed"]}}, {"_id": 0, "id": 1})
        if exists:
            return {"ok": True, "action": "feasibility_task", "item": item, "task_id": exists["id"], "duplicate": True}
        task = {"id": str(uuid.uuid4()), "property_id": property_id, "title": f"Fizibilite: {item}",
                "description": f"Rakip yorumlarında övülen '{item}' bizde yok. Maliyet / talep / uygulama süresi değerlendirin; sonucu görev notuna yazın.",
                "status": "open", "priority": "high", "department": "management", "source": "competitor_gap", "topic": item,
                "created_by": who, "created_at": now}
        await db.staff_tasks.insert_one(dict(task))
        return {"ok": True, "action": "feasibility_task", "item": item, "task_id": task["id"], "duplicate": False}

    @router.get("/reputation/topic-compare/{property_id}")
    async def topic_compare(property_id: str, days: int = 90,
                            _: dict = Depends(require_roles("admin", "manager"))):
        """Konu bazlı kıyas: bizim yorumlar (sentiment_analysis.topics veya anahtar kelime) vs rakipler (Places API varsa gerçek, yoksa SIMULATED)."""
        cfg = await db.reputation_config.find_one({"property_id": property_id}, {"_id": 0}) or {}
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        pq = {"property_id": property_id} if property_id != "all" else {}
        ours = await db.reviews.find({**pq, "created_at": {"$gte": since}}, {"_id": 0, "rating": 1, "review_text": 1, "sentiment_analysis.topics": 1}).to_list(3000)
        acc = {t: [] for t in TOPIC_KW}
        for r in ours:
            topics = [str(t).lower() for t in ((r.get("sentiment_analysis") or {}).get("topics") or [])]
            tl = (r.get("review_text") or "").lower()
            for t, kw in TOPIC_KW.items():
                if t in topics or any(t in x for x in topics) or re.search(kw, tl):
                    acc[t].append(float(r.get("rating") or 0))
        self_scores = {t: (round(sum(v) / len(v), 1) if v else None, len(v)) for t, v in acc.items()}
        comps = []
        for comp in (cfg.get("competitors") or [])[:5]:
            texts = None
            try:
                texts = await _fetch_competitor_texts(comp.get("place_id", ""))
            except Exception as e:
                logger.warning(f"topic-compare places fail {comp.get('name')}: {e}")
            if texts:
                sc, mode = _topic_scores_from_texts(texts), "live"
            else:
                base, _n = _sim_rating(comp.get("name", "x"))
                sc, mode = {}, "simulated"
                for t in TOPIC_KW:
                    h = int(hashlib.sha1(f"{comp.get('name')}|{t}".encode()).hexdigest(), 16)
                    sc[t] = (round(max(2.5, min(5.0, base + ((h % 90) - 45) / 100)), 1), 20 + h % 60)
            comps.append({"name": comp.get("name", ""), "mode": mode, "scores": {t: v[0] for t, v in sc.items()}})
        rows, weak, strong = [], [], []
        for t in TOPIC_KW:
            ours_v = self_scores[t][0]
            cvals = [c["scores"].get(t) for c in comps if c["scores"].get(t) is not None]
            cavg = round(sum(cvals) / len(cvals), 1) if cvals else None
            gap = round(ours_v - cavg, 1) if ours_v is not None and cavg is not None else None
            rows.append({"topic": t, "ours": ours_v, "ours_n": self_scores[t][1], "competitor_avg": cavg, "gap": gap,
                         "competitors": {c["name"]: c["scores"].get(t) for c in comps}})
            if gap is not None and gap <= -0.3: weak.append(t)
            if gap is not None and gap >= 0.3: strong.append(t)
        insight = (f"{', '.join(weak)} rakiplere göre zayıf (gap ≤ -0.3) — öncelikli aksiyon." if weak else "Rakiplere göre belirgin zayıf konu yok.")
        return {"property_id": property_id, "days": days, "competitors": [{"name": c["name"], "mode": c["mode"]} for c in comps],
                "rows": rows, "weak_topics": weak, "strong_topics": strong, "insight": insight,
                "mode": "live" if any(c["mode"] == "live" for c in comps) else "simulated"}

    async def _scan_property(pid: str) -> dict:
        cfg = await db.reputation_config.find_one({"property_id": pid}, {"_id": 0}) or {}
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        rows = []
        self_rating, self_n = await _self_rating(pid)
        rows.append({"entity": "self", "name": "Bizim Otel", "rating": self_rating,
                     "review_count": self_n, "mode": "internal"})
        for comp in (cfg.get("competitors") or [])[:5]:
            rating, count, mode = await _fetch_rating(comp.get("place_id", ""), comp.get("name", ""))
            rows.append({"entity": "competitor", "name": comp.get("name", "?"),
                         "rating": rating, "review_count": count, "mode": mode})
        for row in rows:
            await db.reputation_snapshots.update_one(
                {"property_id": pid, "name": row["name"], "date": today},
                {"$set": {**row, "property_id": pid, "date": today, "created_at": _now()}},
                upsert=True)
        return {"property_id": pid, "date": today, "rows": rows}

    async def _scan_all(property_id: str) -> dict:
        if property_id and property_id != "all":
            pids = [property_id]
        else:
            pids = [c["property_id"] for c in await db.reputation_config.find(
                {}, {"_id": 0, "property_id": 1}).to_list(100)]
        out = []
        for pid in pids:
            try:
                out.append(await _scan_property(pid))
            except Exception as e:
                logger.warning(f"reputation scan failed {pid}: {e}")
        return {"scanned": len(out)}

    _BENCH["fn"] = _scan_all

    @router.get("/reputation/benchmark/{property_id}")
    async def benchmark(property_id: str, days: int = 30,
                        _: dict = Depends(require_roles("admin", "manager"))):
        from datetime import timedelta
        cfg = await db.reputation_config.find_one({"property_id": property_id}, {"_id": 0}) or {}
        cutoff = (datetime.now(timezone.utc) - timedelta(days=min(days, 90))).strftime("%Y-%m-%d")
        snaps = await db.reputation_snapshots.find(
            {"property_id": property_id, "date": {"$gte": cutoff}},
            {"_id": 0}).sort("date", 1).to_list(1000)
        latest_by_name, series = {}, {}
        for s in snaps:
            latest_by_name[s["name"]] = s
            series.setdefault(s["name"], []).append({"date": s["date"], "rating": s.get("rating")})
        table = sorted(latest_by_name.values(),
                       key=lambda x: (x.get("rating") or 0), reverse=True)
        for i, row in enumerate(table):
            row["rank"] = i + 1
            pts = series.get(row["name"], [])
            row["trend"] = (round((pts[-1]["rating"] or 0) - (pts[0]["rating"] or 0), 1)
                            if len(pts) >= 2 and pts[0]["rating"] and pts[-1]["rating"] else 0)
        return {"property_id": property_id,
                "competitors": cfg.get("competitors", []),
                "table": table, "series": series,
                "google_live": bool(os.environ.get("GOOGLE_PLACES_API_KEY"))}

    @router.put("/reputation/config/{property_id}")
    async def set_config(property_id: str, body: dict,
                         current_user: dict = Depends(require_roles("admin", "manager"))):
        comps = []
        for c in (body.get("competitors") or [])[:5]:
            name = str(c.get("name", "")).strip()[:80]
            if name:
                comps.append({"name": name, "place_id": str(c.get("place_id", "")).strip()[:120]})
        await db.reputation_config.update_one(
            {"property_id": property_id},
            {"$set": {"property_id": property_id, "competitors": comps,
                      "updated_at": _now(), "updated_by": current_user.get("email", "")}},
            upsert=True)
        return {"property_id": property_id, "competitors": comps}

    @router.post("/reputation/scan/{property_id}")
    async def scan_now(property_id: str,
                       _: dict = Depends(require_roles("admin", "manager"))):
        return await _scan_property(property_id)

    SIM_COMP_REVIEWS = {
        0: [("kahvaltı", "Kahvaltı çeşitliliği zayıf, geç saatte açık büfe tükeniyor"),
            ("personel", "Resepsiyon yoğun saatlerde ilgisiz")],
        1: [("temizlik", "Odalarda toz ve eski mobilya şikayetleri"),
            ("wifi", "İnternet bağlantısı üst katlarda kopuyor")],
        2: [("ses yalıtımı", "Sokak gürültüsü ve ince duvarlar sık şikayet ediliyor"),
            ("fiyat", "Fiyat/performans dengesizliği eleştiriliyor")],
        3: [("klima", "Klima eski, yaz aylarında yetersiz"),
            ("otopark", "Otopark ücretli ve yetersiz")],
        4: [("check-in", "Check-in kuyrukları uzun"),
            ("yemek", "Restoran menüsü sınırlı")],
    }

    SPY_TOPIC_TO_CATEGORY = {
        "kahvaltı": "yemek", "yemek": "yemek", "personel": "personel",
        "check-in": "personel", "temizlik": "temizlik", "wifi": "oda_konforu",
        "ses yalıtımı": "oda_konforu", "klima": "oda_konforu",
        "otopark": "konum", "fiyat": "fiyat_performans",
    }

    @router.post("/reputation/competitor-spy/{property_id}")
    async def competitor_spy(property_id: str,
                             _: dict = Depends(require_roles("admin", "manager"))):
        """Rakiplerin son yorumlarındaki zayıf yönleri raporla (SIMULATED / Places API)."""
        cfg = await db.reputation_config.find_one({"property_id": property_id}, {"_id": 0}) or {}
        comps = (cfg.get("competitors") or [])[:5]
        if not comps:
            raise HTTPException(400, "Önce Benchmark sekmesinden rakip ekleyin")
        cat_reviews = await db.reviews.find(
            {"property_id": property_id, "category_scores": {"$exists": True}},
            {"_id": 0, "category_scores": 1}).to_list(1000)
        cat_scores = {}
        for r in cat_reviews:
            for c, v in (r.get("category_scores") or {}).items():
                if isinstance(v, (int, float)):
                    cat_scores.setdefault(c, []).append(v)
        our = {c: round(sum(v) / len(v), 2) for c, v in cat_scores.items()}
        rows = []
        for i, comp in enumerate(comps):
            weaknesses = []
            for k, b in SIM_COMP_REVIEWS.get(i % 5, []):
                cat = SPY_TOPIC_TO_CATEGORY.get(k)
                weaknesses.append({"konu": k, "bulgu": b,
                                   "bizim_kategori": cat, "bizim_puan": our.get(cat)})
            w0 = weaknesses[0]
            if w0.get("bizim_puan") is not None and w0["bizim_puan"] >= 3.5:
                firsat = (f"KANITLI FIRSAT: {w0['konu']} alanında bizim puanımız {w0['bizim_puan']}/5 — "
                          f"rakip burada zayıf, pazarlamada öne çıkarın")
            elif w0.get("bizim_puan") is not None:
                firsat = (f"{w0['konu']} alanında bizim puanımız da düşük ({w0['bizim_puan']}/5) — "
                          f"önce kendi puanımızı yükseltelim")
            else:
                firsat = f"{w0['konu']} alanında rakipten iyiysek pazarlamada vurgulayın"
            rows.append({"name": comp.get("name", "?"), "mode": "simulated",
                         "weaknesses": weaknesses, "firsat": firsat})
        doc = {"id": str(uuid.uuid4()), "property_id": property_id,
               "rows": rows, "created_at": datetime.now(timezone.utc).isoformat()}
        await db.competitor_spy_reports.insert_one(dict(doc))
        doc.pop("_id", None)
        return doc

    @router.get("/reputation/competitor-spy/{property_id}/latest")
    async def competitor_spy_latest(property_id: str,
                                    _: dict = Depends(require_roles("admin", "manager"))):
        doc = await db.competitor_spy_reports.find_one(
            {"property_id": property_id}, {"_id": 0}, sort=[("created_at", -1)])
        return doc or {}

    @router.post("/reputation/spy-opportunity/{property_id}")
    async def spy_opportunity(property_id: str, body: dict,
                              current_user: dict = Depends(require_roles("admin", "manager"))):
        """KANITLI FIRSAT → pazarlama görevi + sosyal medya taslağı."""
        konu = (body.get("konu") or "").strip()
        firsat = (body.get("firsat") or "").strip()
        comp_name = (body.get("competitor") or "").strip()
        puan = body.get("bizim_puan")
        if not konu:
            raise HTTPException(400, "konu gerekli")
        prop = await db.properties.find_one({"id": property_id}, {"_id": 0, "name": 1}) or {}
        try:
            from emergentintegrations.llm.chat import LlmChat, UserMessage
            client = LlmChat(
                api_key=os.environ.get("EMERGENT_LLM_KEY"),
                session_id=f"spy-social-{uuid.uuid4()}",
                system_message=("Otel pazarlama uzmanısın. Türkçe, 2-3 cümlelik Instagram/Facebook "
                                "gönderi taslağı yaz; rakip adı VERME, kendi güçlü yönümüzü öv. "
                                "1-2 emoji ve 3 hashtag ekle. Sadece gönderi metnini döndür."),
            ).with_model("openai", "gpt-5.2")
            draft = await client.send_message(UserMessage(text=(
                f"Otel: {prop.get('name', '')}. Güçlü alanımız: {konu} (misafir puanı {puan}/5). "
                f"Rakipler bu alanda zayıf. Fırsat notu: {firsat}")))
        except Exception as e:
            logger.warning(f"spy social draft failed: {e}")
            draft = (f"✨ {prop.get('name', 'Otelimiz')}'de {konu} misafirlerimizden {puan}/5 puan alıyor! "
                     f"Farkı yaşamak için sizi bekliyoruz. #otel #misafirmemnuniyeti #tatil")
        existing = await db.staff_tasks.find_one(
            {"property_id": property_id, "source": "spy_opportunity",
             "weak_topic": konu, "status": {"$in": ["open", "in_progress"]}},
            {"_id": 0, "id": 1})
        task_id = None
        if not existing:
            task_id = str(uuid.uuid4())
            await db.staff_tasks.insert_one({
                "id": task_id, "property_id": property_id,
                "title": f"Pazarlama fırsatı: {konu}"[:120],
                "description": (f"{firsat}\n"
                                + (f"Rakip ({comp_name}) bu alanda zayıf.\n" if comp_name else "")
                                + f"\nSosyal medya taslağı:\n{draft}"),
                "status": "open", "priority": "normal", "department": "marketing",
                "source": "spy_opportunity", "weak_topic": konu,
                "created_by": current_user.get("email", ""),
                "created_at": datetime.now(timezone.utc).isoformat()})
        await db.social_drafts.insert_one({
            "id": str(uuid.uuid4()), "property_id": property_id, "topic": konu,
            "draft": draft, "source": "spy_opportunity",
            "created_at": datetime.now(timezone.utc).isoformat()})
        return {"task_created": task_id is not None,
                "task_id": task_id or existing["id"], "social_draft": draft}

    @router.get("/reputation/social-drafts/{property_id}")
    async def social_drafts_list(property_id: str,
                                 _: dict = Depends(require_roles("admin", "manager"))):
        items = await db.social_drafts.find(
            {"property_id": property_id}, {"_id": 0}).sort("created_at", -1).to_list(50)
        return {"items": items}

    @router.put("/reputation/social-drafts/{draft_id}")
    async def social_draft_update(draft_id: str, body: dict,
                                  current_user: dict = Depends(require_roles("admin", "manager"))):
        text = (body.get("draft") or "").strip()
        if not text:
            raise HTTPException(400, "draft boş olamaz")
        res = await db.social_drafts.update_one(
            {"id": draft_id},
            {"$set": {"draft": text[:2000], "edited": True,
                      "updated_by": current_user.get("email", ""),
                      "updated_at": datetime.now(timezone.utc).isoformat()}})
        if not res.matched_count:
            raise HTTPException(404, "Taslak bulunamadı")
        return {"ok": True}

    IMG_STYLES = {
        "sicak": "Sıcak, davetkar, altın saat ışığı, samimi ve içten bir atmosfer.",
        "minimal": "Minimalist, temiz kompozisyon, bol negatif alan, sade pastel tonlar.",
        "luks": "Lüks, sofistike, zengin dokular, dramatik ışık, premium beş yıldızlı his.",
    }

    async def _gen_one_image(doc: dict, prop_name: str, style_prompt: str, out_path: str,
                             extra_note: str = ""):
        import base64
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        chat = LlmChat(api_key=os.environ.get("EMERGENT_LLM_KEY"),
                       session_id=f"social-img-{uuid.uuid4()}",
                       system_message="You are a hotel marketing visual designer.")
        chat.with_model("gemini", "gemini-3.1-flash-image-preview").with_params(
            modalities=["image", "text"])
        prompt = (f"Instagram için fotogerçekçi bir otel pazarlama görseli üret. "
                  f"Stil: {style_prompt} "
                  f"Konu: {doc.get('topic', '')}. Otel: {prop_name}. "
                  f"Gönderi metni bağlamı: {(doc.get('draft') or '')[:300]}. "
                  f"Görselde hiçbir yazı/metin/logo OLMASIN; sadece atmosferik, profesyonel fotoğraf.")
        if extra_note:
            prompt += f" ÖNEMLİ kullanıcı düzeltme notu (mutlaka uygula): {extra_note[:200]}."
        _text, images = await chat.send_message_multimodal_response(UserMessage(text=prompt))
        if not images:
            raise RuntimeError("no image returned")
        with open(out_path, "wb") as f:
            f.write(base64.b64decode(images[0]["data"]))

    @router.post("/reputation/social-drafts/{draft_id}/image")
    async def social_draft_image(draft_id: str, body: dict = None,
                                 _: dict = Depends(require_roles("admin", "manager"))):
        """Taslak için Gemini Nano Banana ile sosyal medya görseli üret (1 veya çok varyasyon)."""
        style = ((body or {}).get("style") or "sicak").lower()
        variants = min(max(int((body or {}).get("variants") or 1), 1), 3)
        style_prompt = IMG_STYLES.get(style, IMG_STYLES["sicak"])
        doc = await db.social_drafts.find_one({"id": draft_id}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "Taslak bulunamadı")
        prop = await db.properties.find_one(
            {"id": doc["property_id"]}, {"_id": 0, "name": 1}) or {}
        os.makedirs("/app/backend/uploads/social_images", exist_ok=True)
        now_iso = datetime.now(timezone.utc).isoformat()
        if variants == 1:
            path = f"/app/backend/uploads/social_images/{draft_id}.png"
            try:
                await _gen_one_image(doc, prop.get("name", ""), style_prompt, path)
            except Exception as e:
                logger.warning(f"social image generation failed: {e}")
                raise HTTPException(502, "Görsel üretilemedi, tekrar deneyin")
            image_url = f"/api/uploads/social_images/{draft_id}.png"
            await db.social_drafts.update_one(
                {"id": draft_id},
                {"$set": {"image_url": image_url, "image_style": style,
                          "image_generated_at": now_iso}})
            return {"image_url": image_url, "style": style}
        tasks = []
        for i in range(variants):
            path = f"/app/backend/uploads/social_images/{draft_id}_v{i}.png"
            tasks.append(_gen_one_image(doc, prop.get("name", ""), style_prompt, path))
        results = await asyncio.gather(*tasks, return_exceptions=True)
        urls = [f"/api/uploads/social_images/{draft_id}_v{i}.png"
                for i, r in enumerate(results) if not isinstance(r, Exception)]
        if not urls:
            raise HTTPException(502, "Görsel üretilemedi, tekrar deneyin")
        await db.social_drafts.update_one(
            {"id": draft_id},
            {"$set": {"image_variants": urls, "image_style": style,
                      "image_generated_at": now_iso}})
        return {"variants": urls, "style": style}

    @router.post("/reputation/social-drafts/{draft_id}/select-image")
    async def social_draft_select_image(draft_id: str, body: dict,
                                        _: dict = Depends(require_roles("admin", "manager"))):
        url = (body.get("image_url") or "").split("?")[0]
        doc = await db.social_drafts.find_one({"id": draft_id}, {"_id": 0, "image_variants": 1})
        if not doc:
            raise HTTPException(404, "Taslak bulunamadı")
        if url not in (doc.get("image_variants") or []):
            raise HTTPException(400, "Geçersiz görsel seçimi")
        await db.social_drafts.update_one(
            {"id": draft_id}, {"$set": {"image_url": url}})
        return {"ok": True, "image_url": url}

    @router.post("/reputation/social-drafts/{draft_id}/send-package")
    async def social_draft_send_package(draft_id: str, body: dict = None,
                                        current_user: dict = Depends(require_roles("admin", "manager"))):
        """Metin + görseli hazır paket olarak pazarlama görevine iliştir."""
        publish_date = ((body or {}).get("publish_date") or "").strip()
        publish_time = ((body or {}).get("publish_time") or "").strip()
        doc = await db.social_drafts.find_one({"id": draft_id}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "Taslak bulunamadı")
        existing = await db.staff_tasks.find_one(
            {"property_id": doc["property_id"], "source": "social_package",
             "draft_id": draft_id, "status": {"$in": ["open", "in_progress"]}},
            {"_id": 0, "id": 1})
        if existing:
            if publish_date:
                await db.staff_tasks.update_one(
                    {"id": existing["id"]},
                    {"$set": {"publish_date": publish_date, "publish_time": publish_time}})
                await db.social_drafts.update_one(
                    {"id": draft_id},
                    {"$set": {"publish_date": publish_date, "publish_time": publish_time,
                              "publish_alert_sent": False}})
            return {"task_created": False, "task_id": existing["id"],
                    "date_updated": bool(publish_date)}
        desc = f"Yayına hazır sosyal medya paketi.\n\nGönderi metni:\n{doc.get('draft', '')}"
        if doc.get("image_url"):
            desc += f"\n\nGörsel: {doc['image_url']} (stil: {doc.get('image_style', 'sicak')})"
        if publish_date:
            desc += f"\n\nPlanlanan yayın: {publish_date}{' ' + publish_time if publish_time else ''}"
        task_id = str(uuid.uuid4())
        await db.staff_tasks.insert_one({
            "id": task_id, "property_id": doc["property_id"],
            "title": f"📦 Sosyal medya paketi: {doc.get('topic', '')}"[:120],
            "description": desc, "attachment_url": doc.get("image_url"),
            "publish_date": publish_date or None,
            "publish_time": publish_time or None,
            "status": "open", "priority": "normal", "department": "marketing",
            "source": "social_package", "draft_id": draft_id,
            "created_by": current_user.get("email", ""),
            "created_at": datetime.now(timezone.utc).isoformat()})
        await db.social_drafts.update_one(
            {"id": draft_id},
            {"$set": {"packaged_task_id": task_id,
                      **({"publish_date": publish_date, "publish_time": publish_time}
                         if publish_date else {})}})
        return {"task_created": True, "task_id": task_id}

    @router.get("/reputation/social-calendar/{property_id}")
    async def social_calendar(property_id: str,
                              _: dict = Depends(require_roles("admin", "manager"))):
        """Paketlenmiş gönderilerin yayın planı — tarihe göre sıralı."""
        drafts = await db.social_drafts.find(
            {"property_id": property_id, "packaged_task_id": {"$exists": True}},
            {"_id": 0}).to_list(100)
        items = []
        for d in drafts:
            task = await db.staff_tasks.find_one(
                {"id": d.get("packaged_task_id")}, {"_id": 0, "status": 1})
            items.append({"draft_id": d["id"], "topic": d.get("topic"),
                          "draft": (d.get("draft") or "")[:120],
                          "image_url": d.get("image_url"),
                          "publish_date": d.get("publish_date"),
                          "publish_time": d.get("publish_time"),
                          "task_status": (task or {}).get("status", "open")})
        items.sort(key=lambda x: (x["publish_date"] is None, x["publish_date"] or "", ))
        return {"items": items}

    @router.post("/reputation/survey-to-draft/{property_id}")
    async def survey_to_draft(property_id: str,
                              _: dict = Depends(require_roles("admin", "manager"))):
        """Övgü dolu QR anket yorumunu sosyal medya taslağına çevir."""
        resp = await db.survey_responses.find_one(
            {"property_id": property_id, "nps_score": {"$gte": 9},
             "comment": {"$nin": ["", None]},
             "social_draft_created": {"$ne": True}},
            {"_id": 0}, sort=[("created_at", -1)])
        if not resp:
            raise HTTPException(404, "Sosyal medyaya çevrilecek yeni övgü dolu anket yorumu yok")
        prop = await db.properties.find_one({"id": property_id}, {"_id": 0, "name": 1}) or {}
        first_name = (resp.get("guest_name") or "Misafirimiz").split()[0]
        try:
            from emergentintegrations.llm.chat import LlmChat, UserMessage
            chat = LlmChat(api_key=os.environ.get("EMERGENT_LLM_KEY"),
                           session_id=f"survey-social-{uuid.uuid4()}",
                           system_message=("Otel pazarlama uzmanısın. Misafir övgüsünü alıntılayan, "
                                           "Türkçe, 2-3 cümlelik Instagram gönderi taslağı yaz. "
                                           "Misafirin sadece adını kullan (soyadı YOK). "
                                           "1-2 emoji + 3 hashtag ekle. Sadece gönderi metnini döndür."))
            chat.with_model("openai", "gpt-5.2")
            draft = await chat.send_message(UserMessage(text=(
                f"Otel: {prop.get('name', '')}. Misafir adı: {first_name}. "
                f"NPS puanı: {resp.get('nps_score')}/10. "
                f"Misafir yorumu: \"{resp.get('comment', '')[:400]}\"")))
        except Exception as e:
            logger.warning(f"survey social draft failed: {e}")
            draft = (f"💬 {first_name} adlı misafirimiz deneyimini şöyle anlattı: "
                     f"\"{resp.get('comment', '')[:180]}\" Teşekkürler! "
                     f"#misafirmemnuniyeti #otel #tesekkurler")
        draft_id = str(uuid.uuid4())
        await db.social_drafts.insert_one({
            "id": draft_id, "property_id": property_id,
            "topic": "anket övgüsü", "draft": draft, "source": "survey_praise",
            "survey_response_id": resp.get("id"),
            "created_at": datetime.now(timezone.utc).isoformat()})
        await db.survey_responses.update_one(
            {"id": resp.get("id")}, {"$set": {"social_draft_created": True}})
        return {"draft_id": draft_id, "draft": draft, "guest": first_name}

    @router.post("/reputation/trend-alerts/run")
    async def trend_alerts_run(_: dict = Depends(require_roles("admin", "manager"))):
        """Puan düşüş trendi kontrolünü manuel tetikle."""
        from workers import run_rating_trend_check
        return await run_rating_trend_check(db)

    @router.post("/reputation/publish-alerts/run")
    async def publish_alerts_run(_: dict = Depends(require_roles("admin", "manager"))):
        """Yayın günü bildirimlerini manuel tetikle."""
        from workers import run_publish_day_check
        return await run_publish_day_check(db)

    @router.post("/reputation/praise-hunter/run")
    async def praise_hunter_run(_: dict = Depends(require_roles("admin", "manager"))):
        """Övgü avcısını manuel tetikle."""
        from workers import run_praise_hunter
        return await run_praise_hunter(db)

    @router.post("/reputation/social-drafts/{draft_id}/refine-image")
    async def social_draft_refine_image(draft_id: str, body: dict,
                                        _: dict = Depends(require_roles("admin", "manager"))):
        """Kullanıcı notuna göre mevcut görseli yenile."""
        note = (body.get("note") or "").strip()
        if not note:
            raise HTTPException(400, "İyileştirme notu gerekli")
        doc = await db.social_drafts.find_one({"id": draft_id}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "Taslak bulunamadı")
        if not doc.get("image_url"):
            raise HTTPException(400, "Önce bir görsel üretin")
        prop = await db.properties.find_one(
            {"id": doc["property_id"]}, {"_id": 0, "name": 1}) or {}
        style_prompt = IMG_STYLES.get(doc.get("image_style") or "sicak", IMG_STYLES["sicak"])
        fname = doc["image_url"].split("?")[0].split("/")[-1]
        try:
            await _gen_one_image(doc, prop.get("name", ""), style_prompt,
                                 f"/app/backend/uploads/social_images/{fname}",
                                 extra_note=note)
        except Exception as e:
            logger.warning(f"image refine failed: {e}")
            raise HTTPException(502, "Görsel yenilenemedi, tekrar deneyin")
        await db.social_drafts.update_one(
            {"id": draft_id},
            {"$set": {"image_refine_note": note,
                      "image_generated_at": datetime.now(timezone.utc).isoformat()}})
        return {"image_url": doc["image_url"].split("?")[0], "note": note}

    @router.get("/reputation/social-drafts-pending")
    async def social_drafts_pending(_: dict = Depends(require_roles("admin", "manager"))):
        """Tüm şubelerin onay bekleyen otomatik taslakları."""
        items = await db.social_drafts.find(
            {"auto": True, "approved": {"$ne": True}},
            {"_id": 0}).sort("created_at", -1).to_list(100)
        props = {}
        async for p in db.properties.find({}, {"_id": 0, "id": 1, "name": 1}):
            props[p["id"]] = p.get("name", p["id"])
        for i in items:
            i["property_name"] = props.get(i["property_id"], i["property_id"])
        return {"items": items}

    @router.post("/reputation/social-drafts/approve-bulk")
    async def social_drafts_approve_bulk(body: dict,
                                         current_user: dict = Depends(require_roles("admin", "manager"))):
        ids = body.get("draft_ids") or []
        if not ids:
            raise HTTPException(400, "draft_ids gerekli")
        res = await db.social_drafts.update_many(
            {"id": {"$in": ids}, "auto": True},
            {"$set": {"approved": True, "approved_by": current_user.get("email", ""),
                      "approved_at": datetime.now(timezone.utc).isoformat()}})
        return {"approved": res.modified_count}

    @router.get("/reputation/social-connection/{property_id}")
    async def social_connection_get(property_id: str,
                                    _: dict = Depends(require_roles("admin", "manager"))):
        doc = await db.social_connections.find_one({"property_id": property_id}, {"_id": 0}) or {}
        tok = doc.get("meta_access_token", "")
        return {"connected": bool(tok),
                "meta_access_token_masked": (tok[:6] + "…" + tok[-4:]) if len(tok) > 12 else ("***" if tok else ""),
                "ig_business_id": doc.get("ig_business_id", ""),
                "fb_page_id": doc.get("fb_page_id", "")}

    @router.post("/reputation/social-connection/{property_id}")
    async def social_connection_save(property_id: str, body: dict,
                                     current_user: dict = Depends(require_roles("admin", "manager"))):
        upd = {"property_id": property_id,
               "updated_by": current_user.get("email", ""),
               "updated_at": datetime.now(timezone.utc).isoformat()}
        for k in ("meta_access_token", "ig_business_id", "fb_page_id"):
            v = (body.get(k) or "").strip()
            if v:
                upd[k] = v
        await db.social_connections.update_one(
            {"property_id": property_id}, {"$set": upd}, upsert=True)
        return {"ok": True}

    @router.post("/reputation/social-drafts/{draft_id}/publish")
    async def social_draft_publish(draft_id: str,
                                   _: dict = Depends(require_roles("admin", "manager"))):
        """Onaylı paketi Instagram/Facebook'a gönder (anahtar yoksa SİMÜLASYON)."""
        doc = await db.social_drafts.find_one({"id": draft_id}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "Taslak bulunamadı")
        if not doc.get("image_url"):
            raise HTTPException(400, "Önce bir görsel üretin")
        conn = await db.social_connections.find_one(
            {"property_id": doc["property_id"]}, {"_id": 0}) or {}
        now_iso = datetime.now(timezone.utc).isoformat()
        token = conn.get("meta_access_token")
        ig_id = conn.get("ig_business_id")
        if not (token and ig_id):
            await db.social_drafts.update_one(
                {"id": draft_id},
                {"$set": {"published": True, "published_at": now_iso,
                          "publish_mode": "simulated"}})
            return {"published": True, "mode": "simulated",
                    "message": "SİMÜLASYON: Meta anahtarları eklenince gerçek gönderime geçer"}
        # PNG → JPEG (Meta JPEG ister) ve public URL hazırla
        from PIL import Image
        fname = doc["image_url"].split("?")[0].split("/")[-1]
        png_path = f"/app/backend/uploads/social_images/{fname}"
        jpg_name = fname.rsplit(".", 1)[0] + ".jpg"
        Image.open(png_path).convert("RGB").save(
            f"/app/backend/uploads/social_images/{jpg_name}", "JPEG", quality=90)
        base_url = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")
        image_public = f"{base_url}/api/uploads/social_images/{jpg_name}"
        graph = "https://graph.facebook.com/v25.0"
        caption = (doc.get("draft") or "")[:2200]
        async with httpx.AsyncClient(timeout=30) as client:
            r1 = await client.post(f"{graph}/{ig_id}/media", params={
                "image_url": image_public, "caption": caption, "access_token": token})
            b1 = r1.json()
            if r1.is_error or "error" in b1:
                raise HTTPException(502, f"Instagram container hatası: {b1.get('error', {}).get('message', r1.text[:150])}")
            r2 = await client.post(f"{graph}/{ig_id}/media_publish", params={
                "creation_id": b1["id"], "access_token": token})
            b2 = r2.json()
            if r2.is_error or "error" in b2:
                raise HTTPException(502, f"Instagram yayın hatası: {b2.get('error', {}).get('message', r2.text[:150])}")
            fb_result = None
            if conn.get("fb_page_id"):
                r3 = await client.post(f"{graph}/{conn['fb_page_id']}/photos", params={
                    "url": image_public, "caption": caption, "access_token": token})
                fb_result = r3.json()
        await db.social_drafts.update_one(
            {"id": draft_id},
            {"$set": {"published": True, "published_at": now_iso, "publish_mode": "live",
                      "instagram_media_id": b2.get("id"), "facebook_result": fb_result}})
        return {"published": True, "mode": "live", "instagram_media_id": b2.get("id")}

    @router.post("/reputation/social-drafts/{draft_id}/performance")
    async def social_draft_performance(draft_id: str, body: dict,
                                       _: dict = Depends(require_roles("admin", "manager"))):
        perf = {}
        for k in ("likes", "reach", "comments"):
            try:
                perf[k] = max(0, int(body.get(k) or 0))
            except (TypeError, ValueError):
                perf[k] = 0
        res = await db.social_drafts.update_one(
            {"id": draft_id},
            {"$set": {"performance": perf,
                      "performance_at": datetime.now(timezone.utc).isoformat()}})
        if not res.matched_count:
            raise HTTPException(404, "Taslak bulunamadı")
        return {"ok": True, "performance": perf}

    @router.get("/reputation/social-performance/{property_id}")
    async def social_performance(property_id: str,
                                 _: dict = Depends(require_roles("admin", "manager"))):
        """Konu bazlı gönderi performansı — robot hangi konuların tuttuğunu öğrenir."""
        drafts = await db.social_drafts.find(
            {"property_id": property_id, "performance": {"$exists": True}},
            {"_id": 0, "topic": 1, "performance": 1}).to_list(200)
        topics = {}
        for d in drafts:
            t = d.get("topic") or "diğer"
            p = d.get("performance") or {}
            agg = topics.setdefault(t, {"posts": 0, "likes": 0, "reach": 0, "comments": 0})
            agg["posts"] += 1
            for k in ("likes", "reach", "comments"):
                agg[k] += p.get(k, 0)
        rows = []
        for t, a in topics.items():
            rows.append({"topic": t, "posts": a["posts"],
                         "avg_likes": round(a["likes"] / a["posts"], 1),
                         "avg_reach": round(a["reach"] / a["posts"], 1),
                         "avg_comments": round(a["comments"] / a["posts"], 1)})
        rows.sort(key=lambda x: -x["avg_likes"])
        insight = ""
        if len(rows) >= 2 and rows[0]["avg_likes"] > 0:
            diff = round((rows[0]["avg_likes"] - rows[-1]["avg_likes"])
                         / max(rows[-1]["avg_likes"], 1) * 100)
            insight = (f"'{rows[0]['topic']}' konulu gönderiler ortalama {rows[0]['avg_likes']} beğeni ile "
                       f"en iyi performansı gösteriyor (%{diff} fark). Bu konuya ağırlık verin.")
        elif len(rows) == 1:
            insight = f"Şu ana kadar tek konu ölçüldü: '{rows[0]['topic']}' ({rows[0]['avg_likes']} ort. beğeni)."
        return {"rows": rows, "insight": insight}

    @router.get("/reputation/best-time/{property_id}")
    async def best_publish_time(property_id: str,
                                _: dict = Depends(require_roles("admin", "manager"))):
        """Performans verisinden en iyi yayın gün/saatini öğren."""
        drafts = await db.social_drafts.find(
            {"property_id": property_id, "published": True,
             "performance.likes": {"$gt": 0}},
            {"_id": 0, "published_at": 1, "performance": 1}).to_list(200)
        days_tr = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
        buckets = {}
        for d in drafts:
            try:
                dt = datetime.fromisoformat(d["published_at"])
            except (KeyError, ValueError, TypeError):
                continue
            b = buckets.setdefault((dt.weekday(), dt.hour), {"likes": 0, "n": 0})
            b["likes"] += d["performance"].get("likes", 0)
            b["n"] += 1
        if not buckets:
            return {"has_data": False,
                    "message": "Yayınlanan gönderilere beğeni girdikçe en iyi yayın zamanı önerisi burada oluşacak."}
        (wd, hr), stats = max(buckets.items(), key=lambda kv: kv[1]["likes"] / kv[1]["n"])
        avg = round(stats["likes"] / stats["n"], 1)
        return {"has_data": True, "best_day": days_tr[wd], "best_hour": hr, "avg_likes": avg,
                "message": f"En iyi yayın zamanı: {days_tr[wd]} {hr:02d}:00 civarı (ort. {avg} beğeni). Yayın tarihinizi buna göre seçin."}

    @router.post("/reputation/winning-topic/run")
    async def winning_topic_run(_: dict = Depends(require_roles("admin", "manager"))):
        from workers import run_winning_topic_check
        return await run_winning_topic_check(db)

    @router.post("/reputation/social-report/run")
    async def social_report_run(_: dict = Depends(require_roles("admin", "manager"))):
        from workers import run_social_weekly_report
        return await run_social_weekly_report(db, force=True)

    @router.post("/reputation/social-report/pdf")
    async def social_report_pdf(_: dict = Depends(require_roles("admin", "manager"))):
        from workers import generate_social_report_pdf
        pdf_url = await generate_social_report_pdf(db)
        return {"pdf_url": pdf_url}

    @router.get("/reputation/guest-photos/{property_id}")
    async def guest_photos(property_id: str,
                           _: dict = Depends(require_roles("admin", "manager"))):
        """İzinli misafir anket fotoğrafları."""
        items = await db.survey_responses.find(
            {"property_id": property_id, "photo_consent": True,
             "photo_url": {"$nin": ["", None]}},
            {"_id": 0, "id": 1, "guest_name": 1, "photo_url": 1, "comment": 1,
             "nps_score": 1, "photo_draft_created": 1, "created_at": 1}
        ).sort("created_at", -1).to_list(30)
        return {"items": items}

    @router.post("/reputation/guest-photo-to-draft/{response_id}")
    async def guest_photo_to_draft(response_id: str,
                                   _: dict = Depends(require_roles("admin", "manager"))):
        """İzinli misafir fotoğrafını sosyal medya taslağına çevir."""
        resp = await db.survey_responses.find_one({"id": response_id}, {"_id": 0})
        if not resp or not resp.get("photo_url") or not resp.get("photo_consent"):
            raise HTTPException(404, "İzinli fotoğraf bulunamadı")
        if resp.get("photo_draft_created"):
            raise HTTPException(400, "Bu fotoğraf zaten taslağa çevrildi")
        prop = await db.properties.find_one(
            {"id": resp["property_id"]}, {"_id": 0, "name": 1}) or {}
        first_name = (resp.get("guest_name") or "Misafirimiz").split()[0]
        draft_id = str(uuid.uuid4())
        from PIL import Image
        src = "/app/backend/uploads/survey_photos/" + resp["photo_url"].split("/")[-1]
        if not os.path.exists(src):
            raise HTTPException(404, "Fotoğraf dosyası bulunamadı")
        os.makedirs("/app/backend/uploads/social_images", exist_ok=True)
        Image.open(src).save(f"/app/backend/uploads/social_images/{draft_id}.png", "PNG")
        quote = f" \"{(resp.get('comment') or '')[:120]}\"" if resp.get("comment") else ""
        draft = (f"📸 Bu kare misafirimiz {first_name}'den geldi!{quote} "
                 f"{prop.get('name', '')} deneyiminizi bizimle paylaştığınız için teşekkürler 🧡 "
                 f"#misafirkaresi #otel #tesekkurler")
        await db.social_drafts.insert_one({
            "id": draft_id, "property_id": resp["property_id"],
            "topic": "misafir karesi", "draft": draft, "source": "guest_photo",
            "image_url": f"/api/uploads/social_images/{draft_id}.png",
            "survey_response_id": response_id,
            "created_at": datetime.now(timezone.utc).isoformat()})
        await db.survey_responses.update_one(
            {"id": response_id}, {"$set": {"photo_draft_created": True}})
        return {"draft_id": draft_id, "draft": draft}

    @router.get("/reputation/public/photo-contest/{property_id}")
    async def public_photo_contest(property_id: str):
        """Herkese açık: Ayın Karesi kazananları galerisi (auth yok)."""
        import re as _re
        prop = await db.properties.find_one(
            {"id": property_id}, {"_id": 0, "name": 1})
        if not prop:
            raise HTTPException(404, "Otel bulunamadı")
        drafts = await db.social_drafts.find(
            {"property_id": property_id, "source": "photo_contest",
             "image_url": {"$nin": ["", None]}},
            {"_id": 0, "contest_month": 1, "winner_name": 1, "draft": 1,
             "image_url": 1, "created_at": 1}).sort("contest_month", -1).to_list(24)
        items = []
        for d in drafts:
            name = d.get("winner_name")
            if not name:
                m = _re.search(r"Kazanan (\S+)!", d.get("draft") or "")
                name = m.group(1) if m else "Misafirimiz"
            items.append({"month": d.get("contest_month"),
                          "winner": name,
                          "image_url": d.get("image_url")})
        candidates = await db.survey_responses.find(
            {"property_id": property_id, "photo_consent": True,
             "photo_url": {"$nin": ["", None]}, "photo_draft_created": {"$ne": True}},
            {"_id": 0, "id": 1, "guest_name": 1, "photo_url": 1, "gallery_votes": 1}
        ).sort("created_at", -1).to_list(12)
        cands = [{"id": c["id"],
                  "guest": (c.get("guest_name") or "Misafirimiz").split()[0],
                  "photo_url": c["photo_url"],
                  "votes": c.get("gallery_votes", 0)} for c in candidates]
        return {"hotel": prop.get("name", property_id), "items": items,
                "candidates": cands}

    @router.post("/reputation/public/photo-contest/{property_id}/vote")
    async def public_photo_vote(property_id: str, body: dict, request: Request):
        """Herkese açık: aday fotoğrafa oy ver (IP başına aday başına 1 oy)."""
        cid = (body.get("candidate_id") or "").strip()
        if not cid:
            raise HTTPException(400, "candidate_id gerekli")
        ip = (request.headers.get("x-forwarded-for") or
              (request.client.host if request.client else "")).split(",")[0].strip()
        client_token = re.sub(r"[^A-Za-z0-9-]", "", (body.get("client_token") or ""))[:64]
        ip_hash = hashlib.sha256(f"{ip}|{client_token}|{cid}".encode()).hexdigest()
        existing = await db.photo_votes.find_one({"vote_hash": ip_hash}, {"_id": 0, "id": 1})
        if existing:
            raise HTTPException(429, "Bu adaya zaten oy verdiniz")
        day_count = await db.photo_votes.count_documents(
            {"ip_hash": hashlib.sha256(ip.encode()).hexdigest(),
             "created_at": {"$gte": (datetime.now(timezone.utc)
                                     - timedelta(days=1)).isoformat()}})
        if day_count >= 20:
            raise HTTPException(429, "Günlük oy sınırına ulaşıldı")
        res = await db.survey_responses.find_one_and_update(
            {"id": cid, "property_id": property_id, "photo_consent": True},
            {"$inc": {"gallery_votes": 1}},
            projection={"_id": 0, "gallery_votes": 1})
        if res is None:
            raise HTTPException(404, "Aday bulunamadı")
        await db.photo_votes.insert_one({
            "id": str(uuid.uuid4()), "candidate_id": cid,
            "vote_hash": ip_hash,
            "ip_hash": hashlib.sha256(ip.encode()).hexdigest(),
            "created_at": datetime.now(timezone.utc).isoformat()})
        return {"ok": True, "votes": (res.get("gallery_votes") or 0) + 1}

    @router.get("/reputation/room-qr-cards/{property_id}")
    async def room_qr_cards(property_id: str,
                            _: dict = Depends(require_roles("admin", "manager"))):
        """Oda başına anket + galeri QR'lı masa kartları (toplu A4 PDF, 4 kart/sayfa)."""
        import qrcode
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas as pdfcanvas
        from reportlab.lib.units import mm
        from reportlab.lib.utils import ImageReader
        prop = await db.properties.find_one({"id": property_id}, {"_id": 0, "name": 1})
        if not prop:
            raise HTTPException(404, "Otel bulunamadı")
        rooms = await db.rooms.find(
            {"property_id": property_id},
            {"_id": 0, "name": 1, "room_number": 1, "number": 1}).to_list(200)
        if not rooms:
            raise HTTPException(400, "Bu şubede oda tanımlı değil")
        base = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")
        os.makedirs("/app/backend/uploads/reports", exist_ok=True)
        survey_qr = f"/app/backend/uploads/reports/_sq_{property_id}.png"
        gallery_qr = f"/app/backend/uploads/reports/_gq_{property_id}.png"
        qrcode.make(f"{base}/survey/qr-{property_id}").save(survey_qr)
        qrcode.make(f"{base}/kareler/{property_id}").save(gallery_qr)
        _tr = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
        hotel = prop.get("name", "").translate(_tr)[:30]
        fname = f"oda-qr-kartlari-{property_id}.pdf"
        pdf_path = f"/app/backend/uploads/reports/{fname}"
        c = pdfcanvas.Canvas(pdf_path, pagesize=A4)
        w, h = A4
        cw, ch = w / 2, h / 2
        sq = ImageReader(survey_qr)
        gq = ImageReader(gallery_qr)
        for i, room in enumerate(rooms):
            pos = i % 4
            if pos == 0 and i > 0:
                c.showPage()
            x0 = (pos % 2) * cw
            y0 = h - ((pos // 2) + 1) * ch
            room_label = (room.get("room_number") or room.get("number")
                          or room.get("name") or f"Oda {i + 1}")
            room_label = str(room_label).translate(_tr)[:20]
            c.setFillColorRGB(0.07, 0.06, 0.05)
            c.roundRect(x0 + 6 * mm, y0 + 6 * mm, cw - 12 * mm, ch - 12 * mm,
                        4 * mm, fill=1, stroke=0)
            c.setFillColorRGB(0.96, 0.62, 0.04)
            c.setFont("Helvetica-Bold", 10)
            c.drawCentredString(x0 + cw / 2, y0 + ch - 16 * mm, hotel)
            c.setFillColorRGB(1, 1, 1)
            c.setFont("Helvetica-Bold", 14)
            c.drawCentredString(x0 + cw / 2, y0 + ch - 24 * mm, room_label)
            qs = 34 * mm
            gap = (cw - 12 * mm - 2 * qs) / 3
            for j, (img, cap1, cap2) in enumerate(
                    [(sq, "Deneyiminizi", "paylasin"),
                     (gq, "Ayin Karesi", "kazananlari")]):
                qx = x0 + 6 * mm + gap + j * (qs + gap)
                qy = y0 + 24 * mm
                c.setFillColorRGB(1, 1, 1)
                c.roundRect(qx - 2 * mm, qy - 2 * mm, qs + 4 * mm, qs + 4 * mm,
                            2 * mm, fill=1, stroke=0)
                c.drawImage(img, qx, qy, width=qs, height=qs)
                c.setFillColorRGB(0.8, 0.78, 0.75)
                c.setFont("Helvetica", 8)
                c.drawCentredString(qx + qs / 2, qy - 6 * mm, cap1)
                c.drawCentredString(qx + qs / 2, qy - 9.5 * mm, cap2)
            c.setFillColorRGB(0.5, 0.48, 0.46)
            c.setFont("Helvetica", 7)
            c.drawCentredString(x0 + cw / 2, y0 + 10 * mm,
                                "QR kodu telefonunuzla okutmaniz yeterli")
        c.showPage()
        c.save()
        os.remove(survey_qr)
        os.remove(gallery_qr)
        return {"pdf_url": f"/api/uploads/reports/{fname}", "rooms": len(rooms)}

    @router.get("/reputation/photo-contest-poster/{property_id}")
    async def photo_contest_poster(property_id: str,
                                   _: dict = Depends(require_roles("admin", "manager"))):
        """Resepsiyon için QR'lı Ayın Karesi posteri (A4 PDF)."""
        import qrcode
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas as pdfcanvas
        from reportlab.lib.units import mm
        from reportlab.lib.utils import ImageReader
        prop = await db.properties.find_one(
            {"id": property_id}, {"_id": 0, "name": 1})
        if not prop:
            raise HTTPException(404, "Otel bulunamadı")
        base = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")
        gallery_url = f"{base}/kareler/{property_id}"
        qr_img = qrcode.make(gallery_url)
        os.makedirs("/app/backend/uploads/reports", exist_ok=True)
        qr_path = f"/app/backend/uploads/reports/_qr_{property_id}.png"
        qr_img.save(qr_path)
        _tr = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
        fname = f"kareler-poster-{property_id}.pdf"
        pdf_path = f"/app/backend/uploads/reports/{fname}"
        c = pdfcanvas.Canvas(pdf_path, pagesize=A4)
        w, h = A4
        c.setFillColorRGB(0.07, 0.06, 0.05)
        c.rect(0, 0, w, h, fill=1, stroke=0)
        c.setFillColorRGB(0.96, 0.62, 0.04)
        c.setFont("Helvetica-Bold", 15)
        c.drawCentredString(w / 2, h - 40 * mm, "A  Y  I  N     K  A  R  E  S  I")
        c.setFillColorRGB(1, 1, 1)
        c.setFont("Helvetica-Bold", 30)
        c.drawCentredString(w / 2, h - 58 * mm, prop.get("name", "").translate(_tr)[:32])
        c.setFillColorRGB(0.8, 0.78, 0.75)
        c.setFont("Helvetica", 13)
        c.drawCentredString(w / 2, h - 72 * mm,
                            "Konaklamanizdan bir kareyi anketimizle paylasin,")
        c.drawCentredString(w / 2, h - 79 * mm,
                            "ayin kazanani olun ve galerimizde yerinizi alin!")
        qs = 90 * mm
        c.setFillColorRGB(1, 1, 1)
        c.roundRect((w - qs - 10 * mm) / 2, h - 190 * mm, qs + 10 * mm, qs + 10 * mm,
                    6 * mm, fill=1, stroke=0)
        c.drawImage(ImageReader(qr_path), (w - qs) / 2, h - 185 * mm, width=qs, height=qs)
        c.setFillColorRGB(0.96, 0.62, 0.04)
        c.setFont("Helvetica-Bold", 14)
        c.drawCentredString(w / 2, h - 202 * mm, "Kazananlari gormek icin QR kodu okutun")
        c.setFillColorRGB(0.55, 0.52, 0.5)
        c.setFont("Helvetica", 9)
        c.drawCentredString(w / 2, h - 212 * mm, gallery_url)
        c.setFont("Helvetica", 8)
        c.drawCentredString(w / 2, 15 * mm,
                            "Fotograflar misafirlerimizin acik izniyle paylasilmaktadir.")
        c.showPage()
        c.save()
        os.remove(qr_path)
        return {"poster_url": f"/api/uploads/reports/{fname}", "gallery_url": gallery_url}

    @router.post("/reputation/photo-contest/run")
    async def photo_contest_run(_: dict = Depends(require_roles("admin", "manager"))):
        from workers import run_photo_contest
        return await run_photo_contest(db)

    @router.post("/reputation/vote-announce/run")
    async def vote_announce_run(_: dict = Depends(require_roles("admin", "manager"))):
        from workers import run_vote_announcement
        return await run_vote_announcement(db)

    @router.put("/reputation/social-drafts/{draft_id}/approve")
    async def social_draft_approve(draft_id: str,
                                   current_user: dict = Depends(require_roles("admin", "manager"))):
        res = await db.social_drafts.update_one(
            {"id": draft_id},
            {"$set": {"approved": True, "approved_by": current_user.get("email", ""),
                      "approved_at": datetime.now(timezone.utc).isoformat()}})
        if not res.matched_count:
            raise HTTPException(404, "Taslak bulunamadı")
        return {"ok": True}

    return router
