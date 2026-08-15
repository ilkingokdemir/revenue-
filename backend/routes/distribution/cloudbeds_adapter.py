"""K14 Cloudbeds PMS Adaptörü — getHotels/getReservations/putRate (PMS REST API v1.3).
API key yoksa MOCK modda simüle eder."""
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException

CB_URL = "https://api.cloudbeds.com/api/v1.3"


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
        """RMS fiyatlarını önümüzdeki N gün için Cloudbeds'e gönderir (putRate, maks 30 aralık)."""
        d = data or {}
        days = max(1, min(30, int(d.get("days", 14))))
        cfg = await _cfg(pid)
        rate_id = (d.get("rate_id") or cfg.get("rate_id") or "RMS-RATE").strip()
        today = datetime.now(timezone.utc).date()
        intervals = []
        for i in range(days):
            ds = (today + timedelta(days=i)).isoformat()
            ov = await db.rate_overrides.find_one({"property_id": pid, "date": ds},
                                                  {"_id": 0, "rate": 1, "custom_rate": 1})
            if ov and (ov.get("custom_rate") or ov.get("rate")):
                intervals.append({"startDate": ds, "endDate": ds,
                                  "rate": round(float(ov.get("custom_rate") or ov["rate"]), 2)})
        if not intervals:
            return {"pushed_days": 0, "mocked": None, "message": "Gönderilecek RMS fiyatı yok — önce fiyat oluşturun."}
        payload = {"rates": [{"rateID": rate_id, "interval": intervals}]}
        if not cfg.get("api_key"):
            result = {"mocked": True, "would_send": len(intervals),
                      "message": "MOCK — API key girilmediği için gerçek push yapılmadı."}
            await _log(pid, "rate_push", "mocked", payload, result)
            return {"pushed_days": len(intervals), "sample": intervals[:3], **result}
        cert = cfg.get("certification") or {}
        if not (cert.get("passed") and cert.get("mode") == "live"):
            raise HTTPException(428, "Cloudbeds sertifikasyonu geçilmedi — canlı push bloklandı. "
                                     "Önce 'Sertifikasyonu Çalıştır' ile test push + geri okuma doğrulamasını CANLI modda geçin.")
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(f"{CB_URL}/putRate",
                                  headers={"x-api-key": cfg["api_key"],
                                           "content-type": "application/x-www-form-urlencoded"},
                                  content=urlencode(_flatten(payload)))
        result = r.json() if r.status_code == 200 else {"status_code": r.status_code, "body": r.text[:300]}
        await _log(pid, "rate_push", "live", payload, result)
        if r.status_code != 200:
            raise HTTPException(502, f"Cloudbeds push hatası: {result}")
        return {"pushed_days": len(intervals), "sample": intervals[:3], "mocked": False,
                "job_reference_id": (result or {}).get("jobReferenceID"),
                "note": "putRate asenkrondur — jobReferenceID ile Cloudbeds tarafında tamamlanma doğrulanmalı."}

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
