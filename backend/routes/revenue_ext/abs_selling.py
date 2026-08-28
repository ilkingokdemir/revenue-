"""
Attribute-Based Selling (ABS) — oda özelliklerini (manzara, kat, balkon...)
ayrı fiyatlanabilir ürün olarak satar. Booking widget'ta misafir seçer,
gecelik ek ücret rezervasyon toplamına eklenir.

Endpoints (/api/abs/*):
- GET    /public/{property_id}        → aktif özellikler (auth yok, widget kullanır)
- GET    /{property_id}               → admin liste + 90 günlük gelir istatistiği
- POST   /{property_id}               → özellik ekle/güncelle
- DELETE /{property_id}/{attr_id}     → pasifleştir
- POST   /{property_id}/seed          → başlangıç seti
"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict

from fastapi import APIRouter, Depends, HTTPException

STARTER = [
    {"name": "Deniz manzarası", "price": 15.0, "icon": "waves", "description": "Deniz cepheli oda garantisi",
     "image_url": "https://static.prod-images.emergentagent.com/jobs/f284f94c-059d-4721-a5db-def78e330cac/images/d218cf083e5a28710c6a523f82bfd32e4f5cf2dc578ba1ce926ee009d841cf54.jpeg"},
    {"name": "Yüksek kat", "price": 8.0, "icon": "building", "description": "5. kat ve üzeri",
     "image_url": "https://static.prod-images.emergentagent.com/jobs/f284f94c-059d-4721-a5db-def78e330cac/images/5d6ffb3194a7aa43856ff4dfb26c308b97019f0e8f4d8361247c0fa06ce54bec.jpeg"},
    {"name": "Balkonlu oda", "price": 12.0, "icon": "sun", "description": "Özel balkon",
     "image_url": "https://static.prod-images.emergentagent.com/jobs/f284f94c-059d-4721-a5db-def78e330cac/images/67975259827081d4b366a05ac5f5701654d708dc6e2e9c98d0fe4685d4d74177.jpeg"},
    {"name": "Sessiz oda", "price": 6.0, "icon": "moon", "description": "Asansör ve sokaktan uzak",
     "image_url": "https://static.prod-images.emergentagent.com/jobs/f284f94c-059d-4721-a5db-def78e330cac/images/bd39a8fb258af81f5951e530f211750980c644fec74676f464116a18cba16cf6.jpeg"},
    {"name": "Erken check-in garantisi", "price": 10.0, "icon": "clock", "description": "12:00'de odanız hazır",
     "image_url": "https://static.prod-images.emergentagent.com/jobs/f284f94c-059d-4721-a5db-def78e330cac/images/dfb0dd03dc13301730d1d8688cd7c184129e16d66daa0259896b0eee46d39667.jpeg"},
]


async def compute_price_suggestions(db, property_id: str) -> Dict:
    """Son 90 gün satış verisine göre her özellik için ideal ek ücret önerisi."""
    attrs = await db.abs_attributes.find({"property_id": property_id, "active": {"$ne": False}},
                                         {"_id": 0, "id": 1, "name": 1, "price": 1}).to_list(50)
    cutoff = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()
    total, sold, adr_sum, adr_n = 0, {}, 0.0, 0
    async for b in db.bookings.find(
            {"property_id": property_id, "created_at": {"$gte": cutoff},
             "status": {"$nin": ["cancelled", "no_show"]}},
            {"_id": 0, "abs_attributes.id": 1, "total_price": 1, "nights": 1}):
        total += 1
        n = int(b.get("nights") or 0)
        if n > 0 and float(b.get("total_price") or 0) > 0:
            adr_sum += float(b["total_price"]) / n
            adr_n += 1
        for a in (b.get("abs_attributes") or []):
            if a.get("id"):
                sold[a["id"]] = sold.get(a["id"], 0) + 1
    adr = round(adr_sum / adr_n, 2) if adr_n else 100.0
    cap = round(adr * 0.15, 2)
    out = []
    for a in attrs:
        s = sold.get(a["id"], 0)
        attach = round(s / total, 3) if total else 0
        price = float(a.get("price") or 0)
        if total < 20:
            suggested, reason = price, f"Yetersiz veri ({total} rezervasyon) — mevcut fiyat korunmalı."
        elif attach >= 0.30:
            suggested = min(round(price * 1.15, 2), cap)
            reason = f"Güçlü talep: rezervasyonların %{round(attach*100)}'i bu özelliği alıyor — %15 zam kaldırır (tavan: ADR'nin %15'i = £{cap})."
        elif attach <= 0.05:
            suggested = max(round(price * 0.85, 2), 2.0)
            reason = f"Düşük dönüşüm: sadece %{round(attach*100)} — %15 indirim denemesi dönüşümü artırabilir."
        else:
            suggested, reason = price, f"Dönüşüm dengeli (%{round(attach*100)}) — fiyat doğru bantta."
        out.append({"id": a["id"], "name": a["name"], "current_price": price,
                    "suggested_price": suggested, "attach_rate_pct": round(attach * 100, 1),
                    "sold_90d": s, "reason_tr": reason,
                    "action": "raise" if suggested > price else ("lower" if suggested < price else "keep")})
    return {"suggestions": out, "blended_adr_90d": adr, "price_cap": cap, "total_bookings_90d": total}


async def abs_auto_pricing_run(db, property_id: str) -> Dict:
    """Otomatik mod: önerileri güvenlik korkuluklarıyla uygular ve loglar."""
    result = await compute_price_suggestions(db, property_id)
    applied = []
    for s in result["suggestions"]:
        if s["action"] == "keep":
            continue
        await db.abs_attributes.update_one(
            {"id": s["id"], "property_id": property_id},
            {"$set": {"price": s["suggested_price"], "updated_at": datetime.now(timezone.utc).isoformat()}})
        await db.abs_price_log.insert_one({
            "id": str(uuid.uuid4()), "property_id": property_id, "attr_id": s["id"],
            "attr_name": s["name"], "old_price": s["current_price"], "new_price": s["suggested_price"],
            "reason": s["reason_tr"], "mode": "auto", "at": datetime.now(timezone.utc).isoformat()})
        applied.append(f"{s['name']}: £{s['current_price']} → £{s['suggested_price']}")
    await db.abs_settings.update_one(
        {"property_id": property_id},
        {"$set": {"last_auto_run": datetime.now(timezone.utc).isoformat(), "last_applied_count": len(applied)}},
        upsert=True)
    if applied:
        await db.notifications.insert_one({
            "id": str(uuid.uuid4()), "title": "🤖 ABS otomatik fiyat güncellendi",
            "message": f"{property_id}: " + " · ".join(applied[:5]),
            "category": "revenue", "priority": "medium", "read": False,
            "created_at": datetime.now(timezone.utc).isoformat()})
    return {"ok": True, "applied": applied, "applied_count": len(applied)}


async def check_abs_target_alerts(db, force_pid: str = None) -> int:
    """Ay sonuna ≤5 gün kala ABS hedefi geride kalan mülklere uyarı bildirimi (ayda bir kez)."""
    import calendar
    now = datetime.now(timezone.utc)
    days_in_month = calendar.monthrange(now.year, now.month)[1]
    in_window = (days_in_month - now.day) <= 5
    if not in_window and not force_pid:
        return 0
    month_key = now.strftime("%Y-%m")
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()
    q = {"abs_monthly_target": {"$gt": 0}}
    if force_pid:
        q["property_id"] = force_pid
    sent = 0
    async for st in db.abs_settings.find(q, {"_id": 0}):
        pid = st["property_id"]
        if st.get("abs_target_warned") == month_key and not force_pid:
            continue
        rev = 0.0
        async for b in db.bookings.find(
                {"property_id": pid, "created_at": {"$gte": month_start},
                 "status": {"$nin": ["cancelled", "no_show"]}, "abs_total": {"$gt": 0}},
                {"_id": 0, "abs_total": 1}):
            rev += float(b.get("abs_total") or 0)
        target = float(st["abs_monthly_target"])
        projected = round(rev / max(1, now.day) * days_in_month, 2)
        if projected >= target:
            continue
        pct = round(100 * rev / target, 1)
        await db.notifications.insert_one({
            "id": str(uuid.uuid4()), "title": "🎯 ABS hedefi geride kalıyor",
            "message": (f"{pid}: Ay sonuna {max(0, days_in_month - now.day)} gün kala ABS geliri "
                        f"£{round(rev, 2):,} / £{target:,} (%{pct}). Mevcut hızla ay sonu tahmini £{projected:,} — "
                        f"hedefin altında. Özellik fiyatlarını veya görünürlüğü gözden geçirin."),
            "category": "revenue", "priority": "high", "read": False,
            "created_at": now.isoformat()})
        await db.abs_settings.update_one({"property_id": pid}, {"$set": {"abs_target_warned": month_key}})
        sent += 1
    return sent


async def abs_auto_pricing_loop(db):
    """Saatlik kontrol: otomatik mod açık mülklerde 24 saatte bir fiyatları uygular + hedef uyarısı."""
    import asyncio
    while True:
        try:
            cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
            async for st in db.abs_settings.find({"auto_pricing": True}, {"_id": 0}):
                if not st.get("last_auto_run") or st["last_auto_run"] < cutoff:
                    await abs_auto_pricing_run(db, st["property_id"])
            await check_abs_target_alerts(db)
        except Exception:
            pass
        await asyncio.sleep(3600)


def create_abs_router(db, require_roles):
    router = APIRouter(prefix="/abs", tags=["abs-selling"])

    @router.get("/public/{property_id}")
    async def public_attrs(property_id: str):
        rows = await db.abs_attributes.find(
            {"property_id": property_id, "active": {"$ne": False}},
            {"_id": 0, "id": 1, "name": 1, "price": 1, "icon": 1, "description": 1, "image_url": 1}
        ).sort("sort", 1).to_list(20)
        # Akıllı sıralama: son 90 günde en çok satan özellik üstte (dönüşüm bazlı)
        cutoff = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()
        counts: Dict[str, int] = {}
        async for b in db.bookings.find(
                {"property_id": property_id, "abs_total": {"$gt": 0},
                 "created_at": {"$gte": cutoff}, "status": {"$ne": "cancelled"}},
                {"_id": 0, "abs_attributes.id": 1}):
            for a in (b.get("abs_attributes") or []):
                if a.get("id"):
                    counts[a["id"]] = counts.get(a["id"], 0) + 1
        rows.sort(key=lambda r: (-counts.get(r["id"], 0), r.get("name", "")))
        for r in rows:
            if counts.get(r["id"], 0) >= 3:
                r["popular"] = True
        return {"attributes": rows}

    @router.get("/{property_id}")
    async def admin_list(property_id: str,
                         _: dict = Depends(require_roles("admin", "manager"))):
        attrs = await db.abs_attributes.find(
            {"property_id": property_id}, {"_id": 0}).sort("sort", 1).to_list(50)
        cutoff = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()
        bookings = await db.bookings.find(
            {"property_id": property_id, "abs_total": {"$gt": 0},
             "created_at": {"$gte": cutoff}, "status": {"$ne": "cancelled"}},
            {"_id": 0, "abs_total": 1, "abs_attributes": 1}).to_list(2000)
        total_rev = round(sum(float(b.get("abs_total", 0) or 0) for b in bookings), 2)
        counts: Dict[str, int] = {}
        for b in bookings:
            for a in (b.get("abs_attributes") or []):
                counts[a.get("name", "?")] = counts.get(a.get("name", "?"), 0) + 1
        top = max(counts, key=counts.get) if counts else None
        return {"attributes": attrs,
                "stats": {"revenue_90d": total_rev, "bookings_with_abs": len(bookings),
                          "top_attribute": top, "attribute_counts": counts}}

    @router.post("/{property_id}")
    async def upsert(property_id: str, body: Dict,
                     _: dict = Depends(require_roles("admin", "manager"))):
        name = (body.get("name") or "").strip()
        if not name:
            raise HTTPException(400, "name gerekli")
        try:
            price = round(max(0.0, float(body.get("price", 0) or 0)), 2)
        except (TypeError, ValueError):
            raise HTTPException(400, "price sayısal olmalı")
        aid = body.get("id") or str(uuid.uuid4())
        doc = {"id": aid, "property_id": property_id, "name": name, "price": price,
               "icon": body.get("icon", "star"), "description": body.get("description", ""),
               "image_url": (body.get("image_url") or "").strip(),
               "active": bool(body.get("active", True)), "sort": int(body.get("sort", 99) or 99),
               "updated_at": datetime.now(timezone.utc).isoformat()}
        await db.abs_attributes.update_one({"id": aid}, {"$set": doc}, upsert=True)
        return {"ok": True, "attribute": doc}

    @router.delete("/{property_id}/{attr_id}")
    async def deactivate(property_id: str, attr_id: str,
                         _: dict = Depends(require_roles("admin", "manager"))):
        await db.abs_attributes.update_one(
            {"id": attr_id, "property_id": property_id}, {"$set": {"active": False}})
        return {"ok": True}

    @router.post("/{property_id}/seed")
    async def seed(property_id: str,
                   _: dict = Depends(require_roles("admin", "manager"))):
        existing = await db.abs_attributes.count_documents({"property_id": property_id})
        if existing > 0:
            raise HTTPException(400, f"Zaten {existing} özellik tanımlı")
        now = datetime.now(timezone.utc).isoformat()
        docs = [{"id": str(uuid.uuid4()), "property_id": property_id, "active": True,
                 "sort": i, "updated_at": now, **s} for i, s in enumerate(STARTER)]
        await db.abs_attributes.insert_many([dict(d) for d in docs])
        for d in docs:
            d.pop("_id", None)
        return {"ok": True, "seeded": len(docs), "attributes": docs}

    # ---------- ABS Çekirdek: Oda–Özellik eşlemesi + müsaitlik garantisi ----------

    @router.get("/{property_id}/room-matrix")
    async def room_matrix(property_id: str,
                          _: dict = Depends(require_roles("admin", "manager"))):
        rooms = await db.rooms.find({"property_id": property_id},
                                    {"_id": 0, "id": 1, "name": 1, "room_type_id": 1, "abs_attrs": 1}).to_list(200)
        attrs = await db.abs_attributes.find({"property_id": property_id, "active": {"$ne": False}},
                                             {"_id": 0, "id": 1, "name": 1, "price": 1}).sort("sort", 1).to_list(50)
        return {"rooms": rooms, "attributes": attrs}

    @router.put("/{property_id}/room-attrs/{room_id}")
    async def set_room_attrs(property_id: str, room_id: str, body: Dict,
                             _: dict = Depends(require_roles("admin", "manager"))):
        attr_ids = [str(a) for a in (body.get("attr_ids") or [])][:20]
        res = await db.rooms.update_one({"id": room_id, "property_id": property_id},
                                        {"$set": {"abs_attrs": attr_ids}})
        if res.matched_count == 0:
            raise HTTPException(404, "Oda bulunamadı")
        return {"ok": True, "room_id": room_id, "attr_ids": attr_ids}

    @router.post("/{property_id}/room-attrs/auto-seed")
    async def auto_seed_room_attrs(property_id: str,
                                   _: dict = Depends(require_roles("admin", "manager"))):
        """Demo/hızlı kurulum: özellikleri odalara dönüşümlü dağıtır."""
        rooms = await db.rooms.find({"property_id": property_id}, {"_id": 0, "id": 1}).to_list(200)
        attrs = await db.abs_attributes.find({"property_id": property_id, "active": {"$ne": False}},
                                             {"_id": 0, "id": 1}).to_list(50)
        if not rooms or not attrs:
            raise HTTPException(400, "Oda veya özellik yok")
        mapped = 0
        for i, r in enumerate(rooms):
            assigned = [a["id"] for j, a in enumerate(attrs) if (i + j) % 2 == 0]
            await db.rooms.update_one({"id": r["id"]}, {"$set": {"abs_attrs": assigned}})
            mapped += 1
        return {"ok": True, "rooms_mapped": mapped}

    @router.post("/public/{property_id}/availability")
    async def abs_availability(property_id: str, body: Dict):
        """Widget: seçili tarihlerde her özellik için müsait oda sayısı (auth yok)."""
        ci, co = str(body.get("check_in", "")), str(body.get("check_out", ""))
        if not ci or not co:
            raise HTTPException(422, "check_in ve check_out zorunlu")
        rooms = await db.rooms.find({"property_id": property_id},
                                    {"_id": 0, "id": 1, "abs_attrs": 1}).to_list(200)
        busy = set()
        async for b in db.bookings.find(
                {"property_id": property_id, "room_id": {"$ne": None},
                 "status": {"$nin": ["cancelled", "no_show", "checked_out"]},
                 "check_in": {"$lt": co}, "check_out": {"$gt": ci}},
                {"_id": 0, "room_id": 1}):
            busy.add(b.get("room_id"))
        free_rooms = [r for r in rooms if r["id"] not in busy]
        attrs = await db.abs_attributes.find({"property_id": property_id, "active": {"$ne": False}},
                                             {"_id": 0, "id": 1}).to_list(50)
        per_attr = {a["id"]: sum(1 for r in free_rooms if a["id"] in (r.get("abs_attrs") or [])) for a in attrs}
        sel = [str(a) for a in (body.get("attr_ids") or [])]
        combined = sum(1 for r in free_rooms if all(x in (r.get("abs_attrs") or []) for x in sel)) if sel else len(free_rooms)
        return {"per_attribute": per_attr, "combined_free_rooms": combined, "total_free_rooms": len(free_rooms)}

    @router.get("/{property_id}/price-suggestions")
    async def price_suggestions(property_id: str,
                                _: dict = Depends(require_roles("admin", "manager"))):
        """Robot: son 90 gün satış verisine göre her özellik için ideal ek ücret önerisi."""
        result = await compute_price_suggestions(db, property_id)
        settings = await db.abs_settings.find_one({"property_id": property_id}, {"_id": 0}) or {}
        result["auto_pricing"] = bool(settings.get("auto_pricing"))
        result["last_auto_run"] = settings.get("last_auto_run")
        return result

    @router.put("/{property_id}/auto-pricing")
    async def set_auto_pricing(property_id: str, body: Dict,
                               _: dict = Depends(require_roles("admin", "manager"))):
        enabled = bool(body.get("enabled"))
        await db.abs_settings.update_one({"property_id": property_id},
                                         {"$set": {"auto_pricing": enabled,
                                                   "updated_at": datetime.now(timezone.utc).isoformat()}},
                                         upsert=True)
        return {"ok": True, "auto_pricing": enabled}

    @router.post("/{property_id}/auto-pricing/run")
    async def run_auto_pricing(property_id: str,
                               _: dict = Depends(require_roles("admin", "manager"))):
        return await abs_auto_pricing_run(db, property_id)

    @router.get("/{property_id}/price-log")
    async def price_log(property_id: str,
                        _: dict = Depends(require_roles("admin", "manager"))):
        rows = await db.abs_price_log.find({"property_id": property_id}, {"_id": 0}).sort("at", -1).to_list(30)
        return {"log": rows}

    @router.get("/{property_id}/revenue-dashboard")
    async def abs_revenue_dashboard(property_id: str,
                                    _: dict = Depends(require_roles("admin", "manager"))):
        """ABS Gelir Panosu — son 6 ayın özellik geliri (satış/oluşturulma ayına göre)."""
        now = datetime.now(timezone.utc)
        start = (now - timedelta(days=183)).isoformat()
        months, attr_rev = {}, {}
        total_b, abs_b = 0, 0
        async for b in db.bookings.find(
                {"property_id": property_id, "created_at": {"$gte": start},
                 "status": {"$nin": ["cancelled", "no_show"]}},
                {"_id": 0, "created_at": 1, "abs_total": 1, "abs_attributes": 1, "nights": 1}):
            month = str(b.get("created_at", ""))[:7]
            if not month:
                continue
            m = months.setdefault(month, {"month": month, "abs_revenue": 0.0, "bookings_with_abs": 0, "total_bookings": 0})
            m["total_bookings"] += 1
            total_b += 1
            at = float(b.get("abs_total") or 0)
            if at > 0:
                m["abs_revenue"] = round(m["abs_revenue"] + at, 2)
                m["bookings_with_abs"] += 1
                abs_b += 1
                n = max(1, int(b.get("nights") or 1))
                for a in (b.get("abs_attributes") or []):
                    key = a.get("name", a.get("id", "?"))
                    attr_rev[key] = round(attr_rev.get(key, 0) + float(a.get("price") or 0) * n, 2)
        cur_month = now.strftime("%Y-%m")
        start_month = start[:7]
        monthly = [m for m in sorted(months.values(), key=lambda x: x["month"])
                   if start_month <= m["month"] <= cur_month]
        settings = await db.abs_settings.find_one({"property_id": property_id}, {"_id": 0}) or {}
        target = float(settings.get("abs_monthly_target") or 0)
        cur_rev = next((m["abs_revenue"] for m in monthly if m["month"] == cur_month), 0.0)
        by_attr = sorted([{"name": k, "revenue": v} for k, v in attr_rev.items()],
                         key=lambda x: -x["revenue"])
        total_abs = round(sum(m["abs_revenue"] for m in monthly), 2)
        return {"monthly": monthly, "by_attribute": by_attr, "total_abs_revenue": total_abs,
                "attach_rate_pct": round(100 * abs_b / total_b, 1) if total_b else 0,
                "total_bookings": total_b,
                "monthly_target": target, "current_month": cur_month,
                "current_month_revenue": round(cur_rev, 2),
                "target_progress_pct": round(100 * cur_rev / target, 1) if target > 0 else None}

    @router.put("/{property_id}/revenue-target")
    async def set_revenue_target(property_id: str, body: Dict,
                                 _: dict = Depends(require_roles("admin", "manager"))):
        try:
            target = float(body.get("monthly_target") or 0)
        except (TypeError, ValueError):
            raise HTTPException(422, "monthly_target sayı olmalı")
        if target < 0:
            raise HTTPException(422, "Hedef negatif olamaz")
        await db.abs_settings.update_one({"property_id": property_id},
                                         {"$set": {"abs_monthly_target": target,
                                                   "updated_at": datetime.now(timezone.utc).isoformat()}},
                                         upsert=True)
        return {"ok": True, "monthly_target": target}

    @router.post("/{property_id}/target-alert/check")
    async def target_alert_check(property_id: str,
                                 _: dict = Depends(require_roles("admin", "manager"))):
        """Hedef uyarısı kontrolünü elle tetikle (5 gün penceresini beklemeden)."""
        sent = await check_abs_target_alerts(db, force_pid=property_id)
        return {"ok": True, "notifications_sent": sent}

    return router
