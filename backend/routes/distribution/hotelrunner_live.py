"""HotelRunner Canlı Kanal Bağlantısı — ARI push (fiyat + müsaitlik), rezervasyon çekme,
fiyat sapma analizi ve otomatik yeniden push. Kimlik yoksa MOCK modda simüle eder."""
import os
import uuid
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException

HR_URL = "https://app.hotelrunner.com/api/v2/apps"


async def get_creds(db, pid: str):
    cfg = await db.hotelrunner_config.find_one({"property_id": pid}, {"_id": 0}) or {}
    hr_id = cfg.get("hr_id") or os.environ.get("HR_ID", "")
    token = cfg.get("token") or os.environ.get("HR_TOKEN", "")
    return hr_id, token, cfg


async def log_push(db, pid: str, kind: str, mode: str, payload: dict, result: dict):
    await db.hr_push_log.insert_one({
        "id": str(uuid.uuid4()), "property_id": pid, "kind": kind, "mode": mode,
        "payload": payload, "result": result,
        "created_at": datetime.now(timezone.utc).isoformat()})


async def push_daily(db, pid: str, inv_code: str, channel_codes: list, dates: list) -> dict:
    if len(dates) > 90:
        raise HTTPException(400, "HotelRunner en fazla 90 tarih kabul eder — parçalara bölün.")
    hr_id, token, cfg = await get_creds(db, pid)
    body = {"rooms": [{"inv_code": inv_code, "channel_codes": channel_codes, "dates": dates}]}
    if hr_id and token and inv_code != "CERT-TEST":
        cert = cfg.get("certification") or {}
        if not (cert.get("passed") and cert.get("mode") == "live"):
            raise HTTPException(428, "Publisher sertifikasyonu geçilmedi — canlı push bloklandı. "
                                     "Önce 'Sertifikasyonu Çalıştır' ile test push + geri okuma doğrulamasını CANLI modda geçin.")
    if not (hr_id and token):
        result = {"mocked": True, "would_send": len(dates),
                  "message": "MOCK — kimlik girilmediği için gerçek push yapılmadı."}
        await log_push(db, pid, "ari_push", "mocked", body, result)
        return result
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.put(f"{HR_URL}/rooms/daily",
                             params={"hr_id": hr_id, "token": token}, json=body)
    result = r.json() if r.status_code == 200 else {"status_code": r.status_code, "body": r.text[:300]}
    await log_push(db, pid, "ari_push", "live", body, result)
    if r.status_code != 200:
        raise HTTPException(502, f"HotelRunner push hatası: {result}")
    return {"mocked": False, **(result if isinstance(result, dict) else {"result": result})}


async def compute_drift(db, pid: str, days: int = 14, threshold: float = 5.0) -> dict:
    days = max(1, min(90, days))
    last_push = await db.hr_push_log.find_one(
        {"property_id": pid, "kind": "ari_push"}, {"_id": 0}, sort=[("created_at", -1)])
    pushed, inv_code = {}, "RMS-DEFAULT"
    if last_push:
        for room in (last_push.get("payload") or {}).get("rooms", []):
            inv_code = room.get("inv_code") or inv_code
            for d in room.get("dates", []):
                if d.get("price") is not None:
                    pushed[d["date"]] = float(d["price"])
    today = datetime.now(timezone.utc).date()
    rows = []
    for i in range(days):
        ds = (today + timedelta(days=i)).isoformat()
        ov = await db.rate_overrides.find_one({"property_id": pid, "date": ds}, {"_id": 0, "rate": 1, "custom_rate": 1})
        rms = round(float(ov.get("custom_rate") or ov["rate"]), 2) if ov and (ov.get("custom_rate") or ov.get("rate")) else None
        ch = pushed.get(ds)
        drift = None
        if rms is not None and ch:
            drift = round((rms - ch) / ch * 100, 1)
        rows.append({"date": ds, "channel_price": ch, "rms_price": rms,
                     "drift_pct": drift,
                     "status": ("drift" if drift is not None and abs(drift) > threshold
                                else "ok" if drift is not None else "no_data")})
    drift_count = sum(1 for r in rows if r["status"] == "drift")
    return {"property_id": pid, "threshold_pct": threshold, "inv_code": inv_code,
            "last_push_at": last_push.get("created_at") if last_push else None,
            "last_push_mode": last_push.get("mode") if last_push else None,
            "rows": rows, "drift_count": drift_count,
            "note": ("Sapma yok — kanal fiyatları RMS ile uyumlu." if drift_count == 0
                     else f"{drift_count} tarihte %{threshold:g}'i aşan sapma var — yeniden push önerilir.")}


async def repush_drifted(db, pid: str, days: int = 14, threshold: float = 5.0,
                         triggered_by: str = "manual") -> dict:
    drift = await compute_drift(db, pid, days, threshold)
    drifted = [r for r in drift["rows"] if r["status"] == "drift"]
    if not drifted:
        return {"repushed": 0, "mocked": None, "message": "Sapma yok — push gerekmedi."}
    dates = [{"date": r["date"], "price": r["rms_price"]} for r in drifted]
    res = await push_daily(db, pid, drift["inv_code"], [], dates)
    now = datetime.now(timezone.utc).isoformat()
    await db.notifications.insert_one({
        "id": str(uuid.uuid4()), "type": "success",
        "title": "Kanal fiyatları düzeltildi",
        "message": (f"{len(drifted)} tarihteki fiyat sapması kanala yeniden gönderildi "
                    f"({', '.join(r['date'] for r in drifted[:5])}{'...' if len(drifted) > 5 else ''}) — "
                    f"{'MOCK' if res.get('mocked') else 'CANLI'} · tetik: {'otomatik' if triggered_by == 'auto' else 'manuel'}."),
        "category": "revenue", "target_user": "", "target_role": "manager",
        "link_to": "hotelrunner-live", "priority": "normal", "read": False,
        "created_by": "Kanal Sapma Robotu", "created_at": now})
    return {"repushed": len(drifted), "mocked": res.get("mocked"),
            "dates": [r["date"] for r in drifted]}


def create_hotelrunner_router(db, require_roles):
    router = APIRouter(prefix="/hotelrunner", tags=["hotelrunner"])
    ROLES = ("admin", "manager")

    @router.get("/status/{pid}")
    async def status(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        hr_id, token, cfg = await get_creds(db, pid)
        live = bool(hr_id and token)
        pushes = await db.hr_push_log.count_documents({"property_id": pid})
        return {"property_id": pid, "mode": "live" if live else "mocked",
                "hr_id_masked": (hr_id[:4] + "***") if hr_id else "",
                "token_set": bool(token), "total_pushes": pushes,
                "auto_repush": bool(cfg.get("auto_repush")),
                "last_test": cfg.get("last_test"),
                "certification": cfg.get("certification"),
                "note": "Canlı mod için HotelRunner partner panelinden HR_ID ve API TOKEN alın (My Property → HotelRunner Apps). Kimlik girilmeden tüm push'lar MOCK olarak simüle edilir."}

    @router.post("/config/{pid}")
    async def save_config(pid: str, data: dict, _u: dict = Depends(require_roles(*ROLES))):
        upd = {"property_id": pid, "updated_at": datetime.now(timezone.utc).isoformat()}
        if data.get("hr_id"):
            upd["hr_id"] = str(data["hr_id"]).strip()
        if data.get("token"):
            upd["token"] = str(data["token"]).strip()
        if "auto_repush" in data:
            upd["auto_repush"] = bool(data["auto_repush"])
        await db.hotelrunner_config.update_one({"property_id": pid}, {"$set": upd}, upsert=True)
        hr_id, token, cfg = await get_creds(db, pid)
        return {"ok": True, "mode": "live" if (hr_id and token) else "mocked",
                "auto_repush": bool(cfg.get("auto_repush"))}

    @router.post("/test-connection/{pid}")
    async def test_connection(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        hr_id, token, _ = await get_creds(db, pid)
        if not (hr_id and token):
            raise HTTPException(400, "HR_ID ve TOKEN gerekli — önce kimlikleri kaydedin.")
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                r = await client.get(f"{HR_URL}/rooms", params={"hr_id": hr_id, "token": token})
            ok = r.status_code == 200
            body = r.json() if ok else {"status_code": r.status_code, "body": r.text[:300]}
        except Exception as e:
            ok, body = False, {"error": str(e)[:300]}
        now = datetime.now(timezone.utc).isoformat()
        await db.hotelrunner_config.update_one(
            {"property_id": pid},
            {"$set": {"last_test": {"ok": ok, "at": now}}}, upsert=True)
        if not ok:
            raise HTTPException(502, f"HotelRunner bağlantısı başarısız: {body}")
        rooms = body.get("rooms", [])
        return {"ok": True, "rooms_found": len(rooms),
                "rooms": [{"inv_code": r0.get("inv_code"), "name": r0.get("name")} for r0 in rooms[:20]]}

    @router.post("/push-ari/{pid}")
    async def push_ari(pid: str, data: dict, _u: dict = Depends(require_roles(*ROLES))):
        inv_code = (data.get("inv_code") or "").strip()
        dates = data.get("dates") or []
        if not inv_code or not dates:
            raise HTTPException(400, "inv_code ve dates gerekli")
        return await push_daily(db, pid, inv_code, data.get("channel_codes") or [], dates)

    @router.post("/push-from-rms/{pid}")
    async def push_from_rms(pid: str, data: dict = None, _u: dict = Depends(require_roles(*ROLES))):
        """RMS'in güncel fiyat ve müsaitliğini önümüzdeki N gün için HotelRunner'a gönderir."""
        days = max(1, min(90, int((data or {}).get("days", 14))))
        inv_code = ((data or {}).get("inv_code") or "").strip() or "RMS-DEFAULT"
        total_rooms = await db.rooms.count_documents({"property_id": pid}) or 20
        today = datetime.now(timezone.utc).date()
        dates = []
        for i in range(days):
            d = (today + timedelta(days=i)).isoformat()
            ov = await db.rate_overrides.find_one({"property_id": pid, "date": d}, {"_id": 0, "rate": 1, "custom_rate": 1})
            booked = await db.bookings.count_documents({
                "property_id": pid, "status": {"$nin": ["cancelled", "no_show"]},
                "check_in": {"$lte": d}, "check_out": {"$gt": d}})
            entry = {"date": d, "availability": max(total_rooms - booked, 0)}
            if ov and (ov.get("custom_rate") or ov.get("rate")):
                entry["price"] = round(float(ov.get("custom_rate") or ov["rate"]), 2)
            dates.append(entry)
        res = await push_daily(db, pid, inv_code, (data or {}).get("channel_codes") or [], dates)
        return {"pushed_days": len(dates), "sample": dates[:3], **res}

    @router.post("/pull-reservations/{pid}")
    async def pull_reservations(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        hr_id, token, _ = await get_creds(db, pid)
        if not (hr_id and token):
            await log_push(db, pid, "res_pull", "mocked", {}, {"mocked": True})
            return {"mocked": True, "imported": 0,
                    "message": "MOCK — kimlik girilmediği için rezervasyon çekilemedi."}
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(f"{HR_URL}/reservations",
                                 params={"hr_id": hr_id, "token": token,
                                         "undelivered": "true", "per_page": 100})
        if r.status_code != 200:
            raise HTTPException(502, f"HotelRunner rezervasyon hatası: {r.text[:300]}")
        payload = r.json()
        imported = 0
        for res in payload.get("reservations", []):
            await db.hr_inbound.update_one(
                {"external_id": str(res.get("reservation_id"))},
                {"$set": {"external_id": str(res.get("reservation_id")), "property_id": pid,
                          "payload": res, "updated_at": datetime.now(timezone.utc).isoformat()}},
                upsert=True)
            imported += 1
        await log_push(db, pid, "res_pull", "live", {}, {"imported": imported})
        return {"mocked": False, "imported": imported}

    @router.get("/price-drift/{pid}")
    async def price_drift(pid: str, days: int = 14, threshold: float = 5.0,
                          _u: dict = Depends(require_roles(*ROLES))):
        return await compute_drift(db, pid, days, threshold)

    @router.post("/re-push-drift/{pid}")
    async def re_push_drift(pid: str, data: dict = None, _u: dict = Depends(require_roles(*ROLES))):
        return await repush_drifted(db, pid,
                                    days=int((data or {}).get("days", 14)),
                                    threshold=float((data or {}).get("threshold", 5.0)))

    @router.post("/certify/{pid}")
    async def certify(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        """K13: kanala yazma öncesi otomatik sertifikasyon — test push + geri okuma doğrulaması."""
        checks = []
        hr_id, token, _ = await get_creds(db, pid)
        live = bool(hr_id and token)
        checks.append({"name": "Kimlik yapılandırması", "passed": live,
                       "detail": "HR_ID + TOKEN mevcut" if live else "Kimlik yok — MOCK sertifikasyon"})
        test_date = (datetime.now(timezone.utc).date() + timedelta(days=60)).isoformat()
        try:
            res = await push_daily(db, pid, "CERT-TEST", [],
                                   [{"date": test_date, "availability": 1, "price": 99.0}])
            checks.append({"name": "Test push", "passed": True,
                           "detail": f"1 tarih gönderildi ({'CANLI' if not res.get('mocked') else 'MOCK'})"})
        except Exception as e:
            checks.append({"name": "Test push", "passed": False, "detail": str(e)[:150]})
        log = await db.hr_push_log.find_one(
            {"property_id": pid, "kind": "ari_push", "payload.rooms.inv_code": "CERT-TEST"},
            sort=[("created_at", -1)])
        readback = bool(log and any(d.get("date") == test_date and d.get("price") == 99.0
                                    for r in log["payload"]["rooms"] for d in r.get("dates", [])))
        checks.append({"name": "Geri okuma doğrulaması", "passed": readback,
                       "detail": "Push logu geri okundu, tarih+fiyat birebir eşleşti" if readback else "Log eşleşmedi"})
        if live:
            try:
                async with httpx.AsyncClient(timeout=20) as client:
                    r = await client.get(f"{HR_URL}/rooms", params={"hr_id": hr_id, "token": token})
                checks.append({"name": "Canlı API erişimi", "passed": r.status_code == 200,
                               "detail": f"HTTP {r.status_code}"})
            except Exception as e:
                checks.append({"name": "Canlı API erişimi", "passed": False, "detail": str(e)[:120]})
        passed = all(c["passed"] for c in checks if c["name"] != "Kimlik yapılandırması")
        now = datetime.now(timezone.utc).isoformat()
        cert = {"passed": passed, "mode": "live" if live else "mocked", "checks": checks, "at": now}
        await db.hotelrunner_config.update_one(
            {"property_id": pid}, {"$set": {"certification": cert}}, upsert=True)
        return {"ok": True, **cert,
                "note": "Sertifikasyon geçmeden canlı otomatik push açılmamalı. Kimlik girilince CANLI modda tekrarlayın."}

    @router.get("/log/{pid}")
    async def get_push_log(pid: str, limit: int = 20, _u: dict = Depends(require_roles(*ROLES))):
        rows = await db.hr_push_log.find(
            {"property_id": pid}, {"_id": 0, "payload": 0}).sort("created_at", -1).to_list(min(limit, 100))
        return {"log": rows}

    return router
