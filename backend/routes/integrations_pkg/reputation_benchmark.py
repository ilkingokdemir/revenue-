"""
Reputation Benchmark — rakip otellerin Google puanlarını takip et, kıyasla.

GOOGLE_PLACES_API_KEY varsa gerçek rating/userRatingCount; yoksa deterministik
SIMULATED değerler. Günlük snapshot → trend. GuestRevu paritesi (5 rakip).
"""
from datetime import datetime, timezone
import hashlib
import logging
import os
import uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException

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

    @router.post("/reputation/social-drafts/{draft_id}/image")
    async def social_draft_image(draft_id: str, body: dict = None,
                                 _: dict = Depends(require_roles("admin", "manager"))):
        """Taslak için Gemini Nano Banana ile sosyal medya görseli üret."""
        style = ((body or {}).get("style") or "sicak").lower()
        style_prompt = IMG_STYLES.get(style, IMG_STYLES["sicak"])
        doc = await db.social_drafts.find_one({"id": draft_id}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "Taslak bulunamadı")
        prop = await db.properties.find_one(
            {"id": doc["property_id"]}, {"_id": 0, "name": 1}) or {}
        import base64
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        chat = LlmChat(api_key=os.environ.get("EMERGENT_LLM_KEY"),
                       session_id=f"social-img-{uuid.uuid4()}",
                       system_message="You are a hotel marketing visual designer.")
        chat.with_model("gemini", "gemini-3.1-flash-image-preview").with_params(
            modalities=["image", "text"])
        prompt = (f"Instagram için fotogerçekçi bir otel pazarlama görseli üret. "
                  f"Stil: {style_prompt} "
                  f"Konu: {doc.get('topic', '')}. Otel: {prop.get('name', '')}. "
                  f"Gönderi metni bağlamı: {(doc.get('draft') or '')[:300]}. "
                  f"Görselde hiçbir yazı/metin/logo OLMASIN; sadece atmosferik, profesyonel fotoğraf.")
        try:
            _text, images = await chat.send_message_multimodal_response(UserMessage(text=prompt))
        except Exception as e:
            logger.warning(f"social image generation failed: {e}")
            raise HTTPException(502, "Görsel üretilemedi, tekrar deneyin")
        if not images:
            raise HTTPException(502, "Görsel üretilemedi, tekrar deneyin")
        os.makedirs("/app/backend/uploads/social_images", exist_ok=True)
        with open(f"/app/backend/uploads/social_images/{draft_id}.png", "wb") as f:
            f.write(base64.b64decode(images[0]["data"]))
        image_url = f"/api/uploads/social_images/{draft_id}.png"
        await db.social_drafts.update_one(
            {"id": draft_id},
            {"$set": {"image_url": image_url, "image_style": style,
                      "image_generated_at": datetime.now(timezone.utc).isoformat()}})
        return {"image_url": image_url, "style": style}

    @router.post("/reputation/social-drafts/{draft_id}/send-package")
    async def social_draft_send_package(draft_id: str, body: dict = None,
                                        current_user: dict = Depends(require_roles("admin", "manager"))):
        """Metin + görseli hazır paket olarak pazarlama görevine iliştir."""
        publish_date = ((body or {}).get("publish_date") or "").strip()
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
                    {"id": existing["id"]}, {"$set": {"publish_date": publish_date}})
                await db.social_drafts.update_one(
                    {"id": draft_id},
                    {"$set": {"publish_date": publish_date, "publish_alert_sent": False}})
            return {"task_created": False, "task_id": existing["id"],
                    "date_updated": bool(publish_date)}
        desc = f"Yayına hazır sosyal medya paketi.\n\nGönderi metni:\n{doc.get('draft', '')}"
        if doc.get("image_url"):
            desc += f"\n\nGörsel: {doc['image_url']} (stil: {doc.get('image_style', 'sicak')})"
        if publish_date:
            desc += f"\n\nPlanlanan yayın tarihi: {publish_date}"
        task_id = str(uuid.uuid4())
        await db.staff_tasks.insert_one({
            "id": task_id, "property_id": doc["property_id"],
            "title": f"📦 Sosyal medya paketi: {doc.get('topic', '')}"[:120],
            "description": desc, "attachment_url": doc.get("image_url"),
            "publish_date": publish_date or None,
            "status": "open", "priority": "normal", "department": "marketing",
            "source": "social_package", "draft_id": draft_id,
            "created_by": current_user.get("email", ""),
            "created_at": datetime.now(timezone.utc).isoformat()})
        await db.social_drafts.update_one(
            {"id": draft_id},
            {"$set": {"packaged_task_id": task_id,
                      **({"publish_date": publish_date} if publish_date else {})}})
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
            {"_id": 0}, sort=[("submitted_at", -1)])
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
