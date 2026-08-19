"""K14 Cloudbeds PMS Adaptörü — getHotels/getReservations/putRate (PMS REST API v1.3).
API key yoksa MOCK modda simüle eder."""
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException

CB_URL = "https://api.cloudbeds.com/api/v1.3"


async def _build_rate_blocks(db, pid: str, days: int, cfg: dict, rate_id_override: str = "") -> list:
    """Oda tipi bazlı fiyat blokları: override → base_rate fallback; rate_map ile CB rateID eşleme."""
    from datetime import date as _date
    today = datetime.now(timezone.utc).date()
    rate_map = cfg.get("rate_map") or {}
    rts = await db.room_types.find({"property_id": pid}, {"_id": 0}).to_list(20)
    if not rts:
        rts = [{"id": "", "name": "Default", "base_rate": 0}]
    default_rate_id = (rate_id_override or cfg.get("rate_id") or "RMS-RATE").strip()
    blocks = []
    for idx, rt in enumerate(rts):
        cb_rate_id = rate_map.get(rt.get("id", ""))
        if not cb_rate_id:
            if idx == 0 and not rate_map:
                cb_rate_id = default_rate_id
            else:
                continue
        base = float(rt.get("base_rate") or 0)
        intervals = []
        for i in range(days):
            ds = (today + timedelta(days=i)).isoformat()
            ov = await db.rate_overrides.find_one(
                {"property_id": pid, "date": ds, "room_type_id": rt.get("id", "")},
                {"_id": 0, "rate": 1, "custom_rate": 1})
            if not ov:
                ov = await db.rate_overrides.find_one(
                    {"property_id": pid, "date": ds, "room_type_id": {"$in": ["", None]}},
                    {"_id": 0, "rate": 1, "custom_rate": 1})
            rate = None
            if ov and (ov.get("custom_rate") or ov.get("rate")):
                rate = float(ov.get("custom_rate") or ov["rate"])
            elif base > 0:
                rate = base
            if rate:
                intervals.append({"startDate": ds, "endDate": ds, "rate": round(rate, 2)})
        if intervals:
            blocks.append({"room_type": rt.get("name", ""), "room_type_id": rt.get("id", ""),
                           "rateID": str(cb_rate_id), "interval": intervals})
    return blocks


async def do_push_rates(db, pid: str, days: int = 14, rate_id_override: str = "",
                        source: str = "manual") -> dict:
    """RMS fiyatlarını Cloudbeds'e basar (oda tipi bazlı). Loop ve route ortak kullanır."""
    days = max(1, min(30, int(days)))
    cfg = await db.cloudbeds_config.find_one({"property_id": pid}, {"_id": 0}) or {}
    blocks = await _build_rate_blocks(db, pid, days, cfg, rate_id_override)
    if not blocks:
        return {"pushed_days": 0, "rooms": 0, "mocked": None,
                "message": "Gönderilecek RMS fiyatı yok — takvimde fiyat veya oda taban fiyatı tanımlayın."}
    payload = {"rates": [{"rateID": b["rateID"], "interval": b["interval"]} for b in blocks]}
    total_days = sum(len(b["interval"]) for b in blocks)
    summary = [{"room_type": b["room_type"], "rateID": b["rateID"], "days": len(b["interval"]),
                "sample": b["interval"][:2]} for b in blocks]
    log_entry = {"id": str(uuid.uuid4()), "property_id": pid, "kind": "rate_push",
                 "source": source, "payload": payload,
                 "created_at": datetime.now(timezone.utc).isoformat()}
    if not cfg.get("api_key"):
        result = {"mocked": True, "would_send": total_days,
                  "message": "MOCK — API key girilmediği için gerçek push yapılmadı."}
        await db.cb_push_log.insert_one({**log_entry, "mode": "mocked", "result": result})
        return {"pushed_days": total_days, "rooms": len(blocks), "per_room": summary, **result}
    cert = cfg.get("certification") or {}
    if not (cert.get("passed") and cert.get("mode") == "live"):
        return {"error": 428, "detail": "Cloudbeds sertifikasyonu geçilmedi — canlı push bloklandı. "
                                        "Önce 'Sertifikasyonu Çalıştır' ile CANLI modda geçin."}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{CB_URL}/putRate",
                              headers={"x-api-key": cfg["api_key"],
                                       "content-type": "application/x-www-form-urlencoded"},
                              content=urlencode(_flatten(payload)))
    result = r.json() if r.status_code == 200 else {"status_code": r.status_code, "body": r.text[:300]}
    await db.cb_push_log.insert_one({**log_entry, "mode": "live", "result": result})
    if r.status_code != 200:
        return {"error": 502, "detail": f"Cloudbeds push hatası: {result}"}
    return {"pushed_days": total_days, "rooms": len(blocks), "per_room": summary, "mocked": False,
            "job_reference_id": (result or {}).get("jobReferenceID"),
            "note": "putRate asenkrondur — Cloudbeds aldığı fiyatı Booking.com ve bağlı kanallara kendi dağıtır."}


async def cloudbeds_autopush_loop(db, interval_seconds: int = 24 * 3600):
    """Her gece auto_push açık property'lerin RMS fiyatlarını Cloudbeds'e basar."""
    import asyncio
    await asyncio.sleep(300)
    while True:
        try:
            cfgs = await db.cloudbeds_config.find({"auto_push": True}, {"_id": 0}).to_list(50)
            for cfg in cfgs:
                pid = cfg.get("property_id")
                try:
                    r = await do_push_rates(db, pid, days=int(cfg.get("auto_push_days", 14)), source="auto")
                    failed = bool(r.get("error"))
                    day = datetime.now(timezone.utc).date().isoformat()
                    dup = await db.notifications.find_one(
                        {"created_by": "Cloudbeds Robotu", "property_id": pid, "day": day}, {"_id": 1})
                    if not dup:
                        await db.notifications.insert_one({
                            "id": str(uuid.uuid4()),
                            "type": "error" if failed else "success",
                            "title": ("⚠️ Cloudbeds otomatik push başarısız"
                                      if failed else "☁️ Cloudbeds otomatik push tamam"),
                            "message": (str(r.get("detail", ""))[:300] if failed else
                                        f"{r.get('rooms', 0)} oda tipi × {r.get('pushed_days', 0)} gün fiyat Cloudbeds'e gönderildi"
                                        + (" (MOCK)" if r.get("mocked") else " — Cloudbeds kanallara dağıtacak")),
                            "category": "distribution", "target_role": "manager",
                            "link_to": "cloudbeds-live", "priority": "high" if failed else "normal",
                            "read": False, "day": day, "property_id": pid,
                            "created_by": "Cloudbeds Robotu",
                            "created_at": datetime.now(timezone.utc).isoformat()})
                except Exception:
                    pass
        except Exception:
            pass
        await asyncio.sleep(interval_seconds)


def _flatten(value, prefix=""):
    out = []
    if isinstance(value, dict):
        for k, v in value.items():
            out += _flatten(v, f"{prefix}[{k}]" if prefix else k)
    elif isinstance(value, list):
        for i, v in enumerate(value):
            out += _flatten(v, f"{prefix}[{i}]")
    elif value is not None:
        out.append((prefix, str(value).lower() if isinstance(value, bool) else str(value)))
    return out


def create_cloudbeds_router(db, require_roles):
    router = APIRouter(prefix="/cloudbeds", tags=["cloudbeds"])
    ROLES = ("admin", "manager")

    async def _cfg(pid: str) -> dict:
        return await db.cloudbeds_config.find_one({"property_id": pid}, {"_id": 0}) or {}

    async def _log(pid: str, kind: str, mode: str, payload: dict, result: dict):
        await db.cb_push_log.insert_one({
            "id": str(uuid.uuid4()), "property_id": pid, "kind": kind, "mode": mode,
            "payload": payload, "result": result,
            "created_at": datetime.now(timezone.utc).isoformat()})

    @router.get("/status/{pid}")
    async def status(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        cfg = await _cfg(pid)
        live = bool(cfg.get("api_key"))
        pushes = await db.cb_push_log.count_documents({"property_id": pid})
        return {"property_id": pid, "mode": "live" if live else "mocked",
                "api_key_set": live, "cb_property_id": cfg.get("cb_property_id", ""),
                "rate_id": cfg.get("rate_id", ""), "total_pushes": pushes,
                "last_test": cfg.get("last_test"),
                "note": "Canlı mod için Cloudbeds panelinden API key alın (Account → Apps & Marketplace → API Credentials; "
                        "scope: read:hotel, read:reservation, read:rate, write:rate). Anahtar girilmeden tüm işlemler MOCK simüle edilir."}

    @router.post("/config/{pid}")
    async def save_config(pid: str, data: dict, _u: dict = Depends(require_roles(*ROLES))):
        upd = {"property_id": pid, "updated_at": datetime.now(timezone.utc).isoformat()}
        for k in ("api_key", "cb_property_id", "rate_id"):
            if data.get(k):
                upd[k] = str(data[k]).strip()
        await db.cloudbeds_config.update_one({"property_id": pid}, {"$set": upd}, upsert=True)
        cfg = await _cfg(pid)
        return {"ok": True, "mode": "live" if cfg.get("api_key") else "mocked"}

    @router.post("/test-connection/{pid}")
    async def test_connection(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        cfg = await _cfg(pid)
        if not cfg.get("api_key"):
            raise HTTPException(400, "API key gerekli — önce Cloudbeds API anahtarını kaydedin.")
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                r = await client.get(f"{CB_URL}/getHotels",
                                     headers={"x-api-key": cfg["api_key"], "accept": "application/json"},
                                     params={"pageNumber": 1, "pageSize": 100})
            ok = r.status_code == 200 and (r.json() or {}).get("success", True)
            body = r.json() if r.status_code == 200 else {"status_code": r.status_code, "body": r.text[:300]}
        except Exception as e:
            ok, body = False, {"error": str(e)[:300]}
        now = datetime.now(timezone.utc).isoformat()
        await db.cloudbeds_config.update_one(
            {"property_id": pid}, {"$set": {"last_test": {"ok": ok, "at": now}}}, upsert=True)
        if not ok:
            raise HTTPException(502, f"Cloudbeds bağlantısı başarısız: {body}")
        hotels = body.get("data", [])
        return {"ok": True, "hotels_found": len(hotels),
                "hotels": [{"propertyID": h.get("propertyID"), "name": h.get("propertyName")} for h in hotels[:20]]}

    @router.post("/push-from-rms/{pid}")
    async def push_from_rms(pid: str, data: dict = None, _u: dict = Depends(require_roles(*ROLES))):
        """RMS fiyatlarını oda tipi bazlı Cloudbeds'e gönderir — Cloudbeds kanallara dağıtır."""
        d = data or {}
        r = await do_push_rates(db, pid, days=int(d.get("days", 14)),
                                rate_id_override=(d.get("rate_id") or ""), source="manual")
        if r.get("error"):
            raise HTTPException(int(r["error"]), r["detail"])
        return r

    @router.get("/rate-map/{pid}")
    async def get_rate_map(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        cfg = await _cfg(pid)
        rts = await db.room_types.find({"property_id": pid},
                                       {"_id": 0, "id": 1, "name": 1, "base_rate": 1}).to_list(20)
        return {"property_id": pid, "room_types": rts, "rate_map": cfg.get("rate_map") or {},
                "auto_push": bool(cfg.get("auto_push")), "auto_push_days": int(cfg.get("auto_push_days", 14)),
                "note": "Her RMS oda tipini Cloudbeds rateID'sine eşleyin — eşlenmeyen odalar gönderilmez "
                        "(hiç eşleme yoksa ilk oda tipi varsayılan rateID ile gider)."}

    @router.post("/rate-map/{pid}")
    async def save_rate_map(pid: str, data: dict, _u: dict = Depends(require_roles(*ROLES))):
        rm = {str(k): str(v).strip() for k, v in (data.get("rate_map") or {}).items() if str(v).strip()}
        await db.cloudbeds_config.update_one(
            {"property_id": pid},
            {"$set": {"property_id": pid, "rate_map": rm,
                      "updated_at": datetime.now(timezone.utc).isoformat()}}, upsert=True)
        return {"ok": True, "mapped": len(rm)}

    @router.post("/auto-push/{pid}")
    async def set_auto_push(pid: str, data: dict, _u: dict = Depends(require_roles(*ROLES))):
        upd = {"property_id": pid, "auto_push": bool(data.get("enabled")),
               "auto_push_days": max(1, min(30, int(data.get("days", 14)))),
               "updated_at": datetime.now(timezone.utc).isoformat()}
        await db.cloudbeds_config.update_one({"property_id": pid}, {"$set": upd}, upsert=True)
        return {"ok": True, "auto_push": upd["auto_push"], "auto_push_days": upd["auto_push_days"],
                "note": "Robot her gece RMS fiyatlarını Cloudbeds'e basar; Cloudbeds kanallara dağıtır."}

    @router.post("/pull-reservations/{pid}")
    async def pull_reservations(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        cfg = await _cfg(pid)
        if not cfg.get("api_key"):
            await _log(pid, "res_pull", "mocked", {}, {"mocked": True})
            return {"mocked": True, "imported": 0,
                    "message": "MOCK — API key girilmediği için rezervasyon çekilemedi."}
        params = {"pageNumber": 1, "pageSize": 100,
                  "modifiedFrom": (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")}
        if cfg.get("cb_property_id"):
            params["propertyID"] = cfg["cb_property_id"]
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(f"{CB_URL}/getReservations",
                                 headers={"x-api-key": cfg["api_key"], "accept": "application/json"},
                                 params=params)
        if r.status_code != 200:
            raise HTTPException(502, f"Cloudbeds rezervasyon hatası: {r.text[:300]}")
        payload = r.json()
        imported = 0
        for res in payload.get("data", []):
            await db.cb_inbound.update_one(
                {"external_id": str(res.get("reservationID"))},
                {"$set": {"external_id": str(res.get("reservationID")), "property_id": pid,
                          "payload": res, "updated_at": datetime.now(timezone.utc).isoformat()}},
                upsert=True)
            imported += 1
        await _log(pid, "res_pull", "live", {}, {"imported": imported})
        return {"mocked": False, "imported": imported}

    @router.post("/certify/{pid}")
    async def certify(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        """Sertifikasyon: test push + geri okuma doğrulaması — HotelRunner ile aynı güvence."""
        checks = []
        cfg = await _cfg(pid)
        live = bool(cfg.get("api_key"))
        checks.append({"name": "Kimlik yapılandırması", "passed": live,
                       "detail": "API key mevcut" if live else "API key yok — MOCK sertifikasyon"})
        test_date = (datetime.now(timezone.utc).date() + timedelta(days=60)).isoformat()
        test_payload = {"rates": [{"rateID": "CERT-TEST",
                                   "interval": [{"startDate": test_date, "endDate": test_date, "rate": 99.0}]}]}
        try:
            if live:
                async with httpx.AsyncClient(timeout=30) as client:
                    r = await client.post(f"{CB_URL}/putRate",
                                          headers={"x-api-key": cfg["api_key"],
                                                   "content-type": "application/x-www-form-urlencoded"},
                                          content=urlencode(_flatten(test_payload)))
                push_ok = r.status_code == 200
                res = r.json() if push_ok else {"status_code": r.status_code}
                await _log(pid, "rate_push", "live", test_payload, res)
            else:
                push_ok = True
                await _log(pid, "rate_push", "mocked", test_payload, {"mocked": True, "cert": True})
            checks.append({"name": "Test push", "passed": push_ok,
                           "detail": f"1 tarih gönderildi ({'CANLI' if live else 'MOCK'})"})
        except Exception as e:
            checks.append({"name": "Test push", "passed": False, "detail": str(e)[:150]})
        log = await db.cb_push_log.find_one(
            {"property_id": pid, "kind": "rate_push", "payload.rates.rateID": "CERT-TEST"},
            sort=[("created_at", -1)])
        readback = bool(log and any(i.get("startDate") == test_date and i.get("rate") == 99.0
                                    for rt in log["payload"]["rates"] for i in rt.get("interval", [])))
        checks.append({"name": "Geri okuma doğrulaması", "passed": readback,
                       "detail": "Push logu geri okundu, tarih+fiyat birebir eşleşti" if readback else "Log eşleşmedi"})
        if live:
            try:
                async with httpx.AsyncClient(timeout=20) as client:
                    r = await client.get(f"{CB_URL}/getHotels",
                                         headers={"x-api-key": cfg["api_key"], "accept": "application/json"},
                                         params={"pageNumber": 1, "pageSize": 1})
                checks.append({"name": "Canlı API erişimi", "passed": r.status_code == 200,
                               "detail": f"HTTP {r.status_code}"})
            except Exception as e:
                checks.append({"name": "Canlı API erişimi", "passed": False, "detail": str(e)[:120]})
        passed = all(c["passed"] for c in checks if c["name"] != "Kimlik yapılandırması")
        cert = {"passed": passed, "mode": "live" if live else "mocked", "checks": checks,
                "at": datetime.now(timezone.utc).isoformat()}
        await db.cloudbeds_config.update_one(
            {"property_id": pid}, {"$set": {"certification": cert}}, upsert=True)
        return {"ok": True, **cert,
                "note": "Sertifikasyon geçmeden canlı otomatik push açılmamalı. API key girilince CANLI modda tekrarlayın."}

    @router.get("/log/{pid}")
    async def get_log(pid: str, limit: int = 20, _u: dict = Depends(require_roles(*ROLES))):
        rows = await db.cb_push_log.find(
            {"property_id": pid}, {"_id": 0, "payload": 0}).sort("created_at", -1).to_list(min(limit, 100))
        return {"log": rows}

    return router
