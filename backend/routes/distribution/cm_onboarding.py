"""CM-only müşteri hızlı kurulum (eviivo tek-tık onboarding paritesi) + Go-Live skoru."""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

CHANNEL_CATALOG = [
    {"channel_id": "booking_com", "name": "Booking.com", "color": "#003580", "commission_pct": 15},
    {"channel_id": "expedia", "name": "Expedia", "color": "#fbc108", "commission_pct": 18},
    {"channel_id": "airbnb", "name": "Airbnb", "color": "#ff5a5f", "commission_pct": 14},
    {"channel_id": "agoda", "name": "Agoda", "color": "#5c2d91", "commission_pct": 17},
    {"channel_id": "google_hotel_ads", "name": "Google Hotel Ads", "color": "#4285f4", "commission_pct": 10},
    {"channel_id": "tripadvisor", "name": "Tripadvisor", "color": "#34e0a1", "commission_pct": 12},
    {"channel_id": "vrbo", "name": "Vrbo", "color": "#1d4ed8", "commission_pct": 8},
    {"channel_id": "hrs", "name": "HRS", "color": "#e30613", "commission_pct": 13},
]


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def create_cm_onboarding_router(db, require_roles):
    router = APIRouter(prefix="/cm", tags=["cm-onboarding"])
    ROLES = ("admin", "manager")

    async def _setup(pid: str) -> dict:
        return await db.cm_setup.find_one({"property_id": pid}, {"_id": 0}) or {"property_id": pid}

    def _check_scope(u: dict, pid: str):
        scoped = u.get("property_ids")
        if scoped and u.get("role") != "admin" and pid not in scoped:
            raise HTTPException(403, "Bu tesise erişim yetkiniz yok")

    @router.get("/setup/{pid}")
    async def get_setup(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        _check_scope(_u, pid)
        q = {"property_id": pid} if pid != "default" else {"property_id": {"$in": [pid, "all"]}}
        conns = await db.channel_connections.find(q, {"_id": 0}).to_list(30)
        rts = await db.room_types.find({"property_id": pid}, {"_id": 0, "id": 1, "name": 1}).to_list(50)
        rps = await db.rate_plans.find({"property_id": pid}, {"_id": 0, "id": 1, "name": 1}).to_list(50)
        maps = await db.channel_mappings.find({"property_id": pid}, {"_id": 0}).to_list(2000)
        return {"setup": await _setup(pid), "catalog": CHANNEL_CATALOG, "connections": conns,
                "room_types": rts, "rate_plans": rps, "mappings": maps}

    @router.post("/setup/{pid}/channels")
    async def save_channels(pid: str, data: dict, _u: dict = Depends(require_roles(*ROLES))):
        _check_scope(_u, pid)
        ids = data.get("channel_ids") or []
        if not ids:
            raise HTTPException(400, "channel_ids zorunlu")
        cat = {c["channel_id"]: c for c in CHANNEL_CATALOG}
        added = []
        for cid in ids:
            c = cat.get(cid)
            if not c:
                continue
            await db.channel_connections.update_one(
                {"property_id": pid, "channel_id": cid},
                {"$set": {"property_id": pid, "channel_id": cid, "name": c["name"], "type": "ota",
                          "color": c["color"], "commission_pct": c["commission_pct"], "logo": c["name"][0],
                          "connected": True, "status": "active", "rate_rule": "markup",
                          "rate_markup_pct": 0, "auto_sync": True, "updated_at": now_iso()},
                 "$setOnInsert": {"id": str(uuid.uuid4())[:8], "created_at": now_iso()}}, upsert=True)
            added.append(cid)
        await db.cm_setup.update_one({"property_id": pid},
                                     {"$set": {"channels_selected": added, "updated_at": now_iso()}}, upsert=True)
        return {"ok": True, "connected": added}

    @router.post("/setup/{pid}/mapping")
    async def save_mapping(pid: str, data: dict, _u: dict = Depends(require_roles(*ROLES))):
        _check_scope(_u, pid)
        rows = data.get("mappings") or []
        saved = 0
        for m in rows:
            if not (m.get("internal_id") and m.get("channel_id") and (m.get("external_id") or "").strip()):
                continue
            await db.channel_mappings.update_one(
                {"property_id": pid, "kind": m.get("kind", "room"),
                 "internal_id": m["internal_id"], "channel_id": m["channel_id"]},
                {"$set": {"external_id": m["external_id"].strip(), "updated_at": now_iso(),
                          "updated_by": _u.get("name", "")},
                 "$setOnInsert": {"id": str(uuid.uuid4()), "property_id": pid,
                                  "kind": m.get("kind", "room"), "internal_id": m["internal_id"],
                                  "channel_id": m["channel_id"], "created_at": now_iso()}}, upsert=True)
            saved += 1
        return {"ok": True, "saved": saved}

    @router.post("/setup/{pid}/sync-settings")
    async def save_sync(pid: str, data: dict, _u: dict = Depends(require_roles(*ROLES))):
        _check_scope(_u, pid)
        scope = data.get("ari_scope", "full")
        if scope not in ("full", "custom"):
            raise HTTPException(422, "ari_scope: full|custom")
        upd = {"ari_scope": scope,
               "push_frequency_min": max(5, min(1440, int(data.get("push_frequency_min") or 30))),
               "stop_sell_on_zero": bool(data.get("stop_sell_on_zero", True)),
               "updated_at": now_iso()}
        await db.cm_setup.update_one({"property_id": pid}, {"$set": upd}, upsert=True)
        return {"ok": True, **upd}

    @router.post("/test-push/{pid}")
    async def test_push(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        """Bağlı tüm kanallara mock ARI test push'u (gerçek OTA anahtarları gelince canlı)."""
        _check_scope(_u, pid)
        conns = await db.channel_connections.find(
            {"property_id": pid, "connected": True}, {"_id": 0, "channel_id": 1, "name": 1}).to_list(30)
        if not conns:
            raise HTTPException(400, "Önce en az bir kanal bağlayın")
        results = []
        for c in conns:
            await db.push_history.insert_one({
                "id": str(uuid.uuid4()), "property_id": pid, "channel_id": c["channel_id"],
                "kind": "test_push", "scope": "ARI", "status": "success", "mocked": True,
                "message": f"{c['name']} test push OK (mock — canlı API anahtarı bekleniyor)",
                "created_at": now_iso()})
            await db.channel_connections.update_one(
                {"property_id": pid, "channel_id": c["channel_id"]},
                {"$set": {"last_sync": now_iso(), "last_avail_sync": now_iso()}})
            results.append({"channel_id": c["channel_id"], "name": c["name"], "status": "success", "mocked": True})
        await db.cm_setup.update_one({"property_id": pid},
                                     {"$set": {"test_push_at": now_iso(), "updated_at": now_iso()}}, upsert=True)
        return {"ok": True, "results": results}

    @router.get("/golive/{pid}")
    async def golive(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        _check_scope(_u, pid)
        setup = await _setup(pid)
        rts = await db.room_types.count_documents({"property_id": pid})
        conns = await db.channel_connections.count_documents({"property_id": pid, "connected": True})
        maps = await db.channel_mappings.count_documents({"property_id": pid, "external_id": {"$nin": ["", None]}})
        expected = max(rts, 1) * max(conns, 1)
        coverage = round(maps / expected * 100) if conns and rts else 0
        checks = [
            {"key": "room_types", "label": "Oda tipleri tanımlı", "ok": rts > 0},
            {"key": "channels", "label": "En az 1 kanal bağlı", "ok": conns > 0},
            {"key": "mapping", "label": f"Oda eşleme kapsamı ≥%80 (şu an %{coverage})", "ok": coverage >= 80},
            {"key": "sync", "label": "Senkron ayarları (ARI kapsamı) seçildi", "ok": bool(setup.get("ari_scope"))},
            {"key": "stop_sell", "label": "0 müsaitlikte stop-sell aktif", "ok": bool(setup.get("stop_sell_on_zero"))},
            {"key": "test_push", "label": "Test push başarıyla yapıldı", "ok": bool(setup.get("test_push_at"))},
        ]
        score = round(sum(1 for c in checks if c["ok"]) / len(checks) * 100)
        return {"score": score, "ready": score >= 80, "checks": checks,
                "channels_connected": conns, "mapping_coverage_pct": coverage}

    # ---------------- EXPRESS CONNECT: KANAL LISTING AÇMA ----------------
    @router.get("/listings/{pid}")
    async def get_listings(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        _check_scope(_u, pid)
        rows = await db.channel_listings.find({"property_id": pid}, {"_id": 0}).sort("created_at", -1).to_list(50)
        # Mock ilerleme: incelemedeki başvurular 60 sn sonra canlıya geçer
        now = datetime.now(timezone.utc)
        for r in rows:
            if r.get("status") == "in_review" and r.get("submitted_at"):
                try:
                    sub = datetime.fromisoformat(r["submitted_at"])
                    if (now - sub).total_seconds() > 60:
                        tl = r.get("timeline", []) + [{"step": "live", "at": now_iso(),
                                                       "note": "Listing yayında (MOCK — canlı OTA anahtarı gelince gerçek)"}]
                        await db.channel_listings.update_one({"id": r["id"]},
                                                             {"$set": {"status": "live", "timeline": tl}})
                        r["status"], r["timeline"] = "live", tl
                except Exception:
                    pass
        return {"listings": rows, "catalog": CHANNEL_CATALOG}

    @router.post("/listings/{pid}")
    async def create_listing(pid: str, data: dict, _u: dict = Depends(require_roles(*ROLES))):
        _check_scope(_u, pid)
        cid = data.get("channel_id")
        cat = {c["channel_id"]: c for c in CHANNEL_CATALOG}
        if cid not in cat:
            raise HTTPException(422, "Geçersiz kanal")
        content = data.get("content") or {}
        if not (content.get("description") or "").strip():
            raise HTTPException(400, "Tesis açıklaması zorunlu")
        doc = {"id": str(uuid.uuid4()), "property_id": pid, "channel_id": cid,
               "channel_name": cat[cid]["name"], "content": content, "status": "draft",
               "timeline": [{"step": "draft", "at": now_iso(), "note": "Taslak oluşturuldu"}],
               "created_by": _u.get("name", ""), "created_at": now_iso()}
        await db.channel_listings.insert_one({**doc})
        doc.pop("_id", None)
        return {"ok": True, "listing": doc}

    @router.post("/listings/{pid}/{lid}/submit")
    async def submit_listing(pid: str, lid: str, _u: dict = Depends(require_roles(*ROLES))):
        _check_scope(_u, pid)
        r = await db.channel_listings.find_one({"id": lid, "property_id": pid}, {"_id": 0})
        if not r:
            raise HTTPException(404, "Listing bulunamadı")
        if r.get("status") not in ("draft", "rejected"):
            raise HTTPException(400, "Sadece taslak başvurular gönderilebilir")
        tl = r.get("timeline", []) + [
            {"step": "submitted", "at": now_iso(), "note": f"{r['channel_name']} başvurusu gönderildi (MOCK)"},
            {"step": "in_review", "at": now_iso(), "note": "Kanal tarafında incelemede — ~1 dk sürer (MOCK)"}]
        await db.channel_listings.update_one({"id": lid},
                                             {"$set": {"status": "in_review", "submitted_at": now_iso(), "timeline": tl}})
        return {"ok": True, "status": "in_review", "mocked": True}

    return router
