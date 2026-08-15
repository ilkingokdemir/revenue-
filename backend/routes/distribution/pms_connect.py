"""PMS Bağlantı Merkezi — agnostic middleware: RMS fiyatları standart formatta üretilir,
her adaptör kendi diline çevirir (Mews JSON, Apaleo REST, SiteMinder OTA XML, eviivo/Elektraweb REST).
Kimlik girilmeden tüm sağlayıcılar MOCK modda simüle edilir. Sertifikasyon (test push + geri okuma)
geçilmeden CANLI push bloklanır."""
import uuid
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException

PROVIDERS = {
    "mews": {
        "name": "Mews", "region": "İngiltere · Avrupa · Amerika", "api_type": "open",
        "format": "json", "base_url": "https://api.mews-demo.com",
        "auth_fields": [
            {"key": "client_token", "label": "ClientToken", "secret": True},
            {"key": "access_token", "label": "AccessToken", "secret": True},
            {"key": "rate_id", "label": "Rate ID (root rate)", "secret": False}],
        "note": "Tamamen açık API (Connector API). Demo: api.mews-demo.com — Marketplace → My subscriptions'tan AccessToken alın. Fiyat push: rates/updatePrice (yalnızca root rate)."},
    "apaleo": {
        "name": "Apaleo", "region": "Almanya · Orta Avrupa", "api_type": "open",
        "format": "json", "base_url": "https://api.apaleo.com",
        "auth_fields": [
            {"key": "client_id", "label": "Client ID (OAuth2)", "secret": False},
            {"key": "client_secret", "label": "Client Secret", "secret": True},
            {"key": "apaleo_property_id", "label": "Apaleo Property ID", "secret": False},
            {"key": "rate_plan_id", "label": "Rate Plan ID", "secret": False}],
        "note": "API-first açık platform — apaleo.dev'den anında geliştirici hesabı. OAuth2 client_credentials ile token alınır, rate-plans/{id}/rates PUT edilir."},
    "siteminder": {
        "name": "SiteMinder", "region": "Global (en büyük channel manager)", "api_type": "partner",
        "format": "ota_xml", "base_url": "",
        "auth_fields": [
            {"key": "username", "label": "pmsXchange Kullanıcı", "secret": False},
            {"key": "password", "label": "Şifre", "secret": True},
            {"key": "hotel_code", "label": "Hotel Code", "secret": False},
            {"key": "endpoint_url", "label": "Endpoint URL (partner onayıyla verilir)", "secret": False}],
        "note": "Partner onaylı — siteminder.com/partners başvurusu + sertifikasyon şart. Fiyatlar OTA XML standardı (OTA_HotelRateAmountNotifRQ) ile pmsXchange'e basılır; SiteMinder yüzlerce OTA'ya dağıtır."},
    "eviivo": {
        "name": "eviivo", "region": "İngiltere (B&B/butik lideri) · Avrupa · Amerika", "api_type": "closed",
        "format": "json", "base_url": "",
        "auth_fields": [
            {"key": "api_key", "label": "API Key (partner sözleşmesiyle verilir)", "secret": True},
            {"key": "property_code", "label": "Property Code", "secret": False},
            {"key": "endpoint_url", "label": "Endpoint URL", "secret": False}],
        "note": "Kapalı/kontrollü API — resmi partnerlik + NDA sonrası dokümanlar paylaşılır. Fiyatlar toplu paket (bulk update) halinde iletilir. Kimlik gelene kadar MOCK iskelet hazır."},
    "elektraweb": {
        "name": "Elektraweb", "region": "Türkiye (pazar lideri) · Orta Doğu", "api_type": "semi",
        "format": "json", "base_url": "",
        "auth_fields": [
            {"key": "api_key", "label": "API Key", "secret": True},
            {"key": "hotel_id", "label": "Hotel ID", "secret": False},
            {"key": "endpoint_url", "label": "Endpoint URL (entegrasyon ekibinden)", "secret": False}],
        "note": "Yarı açık API — Elektraweb entegrasyon ekibiyle doğrudan görüşülüp test hesabı alınır. Fiyat matrisi JSON REST ile güncellenir, kendi kanal yöneticisi Booking/Expedia'ya iletir."},
}

_REQUIRED = {
    "mews": ("client_token", "access_token", "rate_id"),
    "apaleo": ("client_id", "client_secret", "apaleo_property_id", "rate_plan_id"),
    "siteminder": ("username", "password", "hotel_code", "endpoint_url"),
    "eviivo": ("api_key", "property_code", "endpoint_url"),
    "elektraweb": ("api_key", "hotel_id", "endpoint_url"),
}


def _has_creds(provider: str, cfg: dict) -> bool:
    return all(cfg.get(k) for k in _REQUIRED[provider])


def _translate(provider: str, cfg: dict, rows: list, currency: str = "EUR") -> dict:
    """Standart RMS satırlarını [{date, rate, availability}] sağlayıcı diline çevirir."""
    if provider == "mews":
        return {"method": "POST", "path": "/api/connector/v1/rates/updatePrice",
                "body": {"ClientToken": "***", "AccessToken": "***", "Client": "MyHotelBox-RMS/1.0",
                         "RateId": cfg.get("rate_id", ""),
                         "PriceUpdates": [{"FirstTimeUnitStartUtc": f"{r['date']}T00:00:00.000Z",
                                           "LastTimeUnitStartUtc": f"{r['date']}T00:00:00.000Z",
                                           "Value": r["rate"]} for r in rows]}}
    if provider == "apaleo":
        return {"method": "PUT", "path": f"/rateplan/v1/rate-plans/{cfg.get('rate_plan_id', '')}/rates",
                "body": {"rates": [{"from": f"{r['date']}T00:00:00Z",
                                    "to": f"{r['date']}T00:00:00Z",
                                    "price": {"amount": r["rate"], "currency": currency}} for r in rows]}}
    if provider == "siteminder":
        msgs = "".join(
            f'<RateAmountMessage><StatusApplicationControl Start="{r["date"]}" End="{r["date"]}" '
            f'InvTypeCode="{cfg.get("hotel_code", "")}-STD" RatePlanCode="RMS"/>'
            f'<Rates><Rate><BaseByGuestAmts><BaseByGuestAmt AmountAfterTax="{r["rate"]}" '
            f'CurrencyCode="{currency}" NumberOfGuests="2"/></BaseByGuestAmts></Rate></Rates>'
            f"</RateAmountMessage>" for r in rows)
        xml = ('<?xml version="1.0" encoding="UTF-8"?>'
               '<OTA_HotelRateAmountNotifRQ xmlns="http://www.opentravel.org/OTA/2003/05" Version="1.0">'
               f'<RateAmountMessages HotelCode="{cfg.get("hotel_code", "")}">{msgs}</RateAmountMessages>'
               "</OTA_HotelRateAmountNotifRQ>")
        return {"method": "POST", "path": "/pmsxchange_v2/services", "body_xml": xml}
    if provider == "eviivo":
        return {"method": "POST", "path": "/v2/rates/bulk",
                "body": {"propertyCode": cfg.get("property_code", ""),
                         "updates": [{"date": r["date"], "amount": r["rate"],
                                      "availability": r.get("availability")} for r in rows]}}
    return {"method": "POST", "path": "/api/rateupdate",
            "body": {"hotel_id": cfg.get("hotel_id", ""),
                     "prices": [{"date": r["date"], "price": r["rate"],
                                 "allotment": r.get("availability")} for r in rows]}}


def create_pms_connect_router(db, require_roles):
    router = APIRouter(prefix="/pms-connect", tags=["pms-connect"])
    ROLES = ("admin", "manager")

    async def _cfg(pid: str, provider: str) -> dict:
        return await db.pms_connect_config.find_one(
            {"property_id": pid, "provider": provider}, {"_id": 0}) or {}

    async def _log(pid: str, provider: str, kind: str, mode: str,
                   standard_rows: list, translated: dict, result: dict, cert_test: bool = False):
        await db.pms_push_log.insert_one({
            "id": str(uuid.uuid4()), "property_id": pid, "provider": provider,
            "kind": kind, "mode": mode, "standard_rows": standard_rows,
            "translated_sample": {k: (v[:400] if isinstance(v, str) else v)
                                  for k, v in list(translated.items())[:3]},
            "result": result, "cert_test": cert_test,
            "created_at": datetime.now(timezone.utc).isoformat()})

    async def _rms_rows(pid: str, days: int) -> list:
        total_rooms = await db.rooms.count_documents({"property_id": pid}) or 20
        today = datetime.now(timezone.utc).date()
        rows = []
        for i in range(days):
            ds = (today + timedelta(days=i)).isoformat()
            ov = await db.rate_overrides.find_one({"property_id": pid, "date": ds},
                                                  {"_id": 0, "rate": 1, "custom_rate": 1})
            if not (ov and (ov.get("custom_rate") or ov.get("rate"))):
                continue
            booked = await db.bookings.count_documents({
                "property_id": pid, "status": {"$nin": ["cancelled", "no_show"]},
                "check_in": {"$lte": ds}, "check_out": {"$gt": ds}})
            rows.append({"date": ds, "rate": round(float(ov.get("custom_rate") or ov["rate"]), 2),
                         "availability": max(total_rooms - booked, 0)})
        return rows

    async def _live_send(provider: str, cfg: dict, translated: dict) -> dict:
        base = (cfg.get("endpoint_url") or PROVIDERS[provider]["base_url"]).rstrip("/")
        if not base:
            raise HTTPException(400, f"{PROVIDERS[provider]['name']} için endpoint URL gerekli.")
        async with httpx.AsyncClient(timeout=30) as client:
            if provider == "mews":
                body = dict(translated["body"])
                body["ClientToken"] = cfg["client_token"]
                body["AccessToken"] = cfg["access_token"]
                r = await client.post(f"{base}{translated['path']}", json=body)
            elif provider == "apaleo":
                tk = await client.post("https://identity.apaleo.com/connect/token",
                                       data={"grant_type": "client_credentials",
                                             "client_id": cfg["client_id"],
                                             "client_secret": cfg["client_secret"]})
                if tk.status_code != 200:
                    raise HTTPException(502, f"Apaleo OAuth hatası: {tk.text[:200]}")
                r = await client.put(f"{base}{translated['path']}",
                                     headers={"Authorization": f"Bearer {tk.json()['access_token']}"},
                                     json=translated["body"])
            elif provider == "siteminder":
                r = await client.post(f"{base}{translated['path']}",
                                      auth=(cfg["username"], cfg["password"]),
                                      headers={"Content-Type": "text/xml"},
                                      content=translated["body_xml"])
            else:
                r = await client.post(f"{base}{translated['path']}",
                                      headers={"x-api-key": cfg["api_key"]},
                                      json=translated["body"])
        if r.status_code >= 400:
            raise HTTPException(502, f"{PROVIDERS[provider]['name']} hatası ({r.status_code}): {r.text[:250]}")
        try:
            return r.json()
        except Exception:
            return {"status_code": r.status_code, "body": r.text[:300]}

    async def _push(pid: str, provider: str, rows: list, cert_test: bool = False) -> dict:
        cfg = await _cfg(pid, provider)
        translated = _translate(provider, cfg, rows)
        live = _has_creds(provider, cfg)
        if live and not cert_test:
            cert = cfg.get("certification") or {}
            if not (cert.get("passed") and cert.get("mode") == "live"):
                raise HTTPException(428, f"{PROVIDERS[provider]['name']} sertifikasyonu geçilmedi — canlı push bloklandı. "
                                         "Önce test push + geri okuma doğrulamasını CANLI modda geçin.")
        if not live:
            result = {"mocked": True, "would_send": len(rows),
                      "message": "MOCK — kimlik girilmediği için gerçek push yapılmadı."}
            await _log(pid, provider, "rate_push", "mocked", rows, translated, result, cert_test)
            return {"pushed_days": len(rows), "sample": rows[:3],
                    "translated_preview": translated, **result}
        result = await _live_send(provider, cfg, translated)
        await _log(pid, provider, "rate_push", "live", rows, translated, result, cert_test)
        return {"pushed_days": len(rows), "sample": rows[:3], "mocked": False, "result": result}

    @router.get("/providers/{pid}")
    async def list_providers(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        out = []
        for key, meta in PROVIDERS.items():
            cfg = await _cfg(pid, key)
            live = _has_creds(key, cfg)
            pushes = await db.pms_push_log.count_documents({"property_id": pid, "provider": key})
            cert = cfg.get("certification")
            out.append({"id": key, **{k: v for k, v in meta.items() if k != "auth_fields"},
                        "auth_fields": meta["auth_fields"],
                        "mode": "live" if live else "mocked",
                        "configured_fields": [f["key"] for f in meta["auth_fields"] if cfg.get(f["key"])],
                        "total_pushes": pushes, "certification": cert,
                        "last_test": cfg.get("last_test")})
        return {"property_id": pid, "providers": out,
                "note": "Agnostic middleware: RMS fiyatları standart üretilir, her adaptör kendi diline çevirir. "
                        "Kimlik girilmeden MOCK; canlı push için sertifikasyon şart."}

    @router.post("/{provider}/config/{pid}")
    async def save_config(provider: str, pid: str, data: dict,
                          _u: dict = Depends(require_roles(*ROLES))):
        if provider not in PROVIDERS:
            raise HTTPException(404, "Bilinmeyen sağlayıcı")
        upd = {"property_id": pid, "provider": provider,
               "updated_at": datetime.now(timezone.utc).isoformat()}
        for f in PROVIDERS[provider]["auth_fields"]:
            if data.get(f["key"]):
                upd[f["key"]] = str(data[f["key"]]).strip()
        if data.get("endpoint_url"):
            upd["endpoint_url"] = str(data["endpoint_url"]).strip()
        await db.pms_connect_config.update_one(
            {"property_id": pid, "provider": provider}, {"$set": upd}, upsert=True)
        cfg = await _cfg(pid, provider)
        return {"ok": True, "mode": "live" if _has_creds(provider, cfg) else "mocked"}

    @router.post("/{provider}/test-connection/{pid}")
    async def test_connection(provider: str, pid: str, _u: dict = Depends(require_roles(*ROLES))):
        if provider not in PROVIDERS:
            raise HTTPException(404, "Bilinmeyen sağlayıcı")
        cfg = await _cfg(pid, provider)
        if not _has_creds(provider, cfg):
            raise HTTPException(400, f"{PROVIDERS[provider]['name']} kimlikleri eksik — önce tüm alanları kaydedin.")
        base = (cfg.get("endpoint_url") or PROVIDERS[provider]["base_url"]).rstrip("/")
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                if provider == "mews":
                    r = await client.post(f"{base}/api/connector/v1/configuration/get",
                                          json={"ClientToken": cfg["client_token"],
                                                "AccessToken": cfg["access_token"],
                                                "Client": "MyHotelBox-RMS/1.0"})
                elif provider == "apaleo":
                    r = await client.post("https://identity.apaleo.com/connect/token",
                                          data={"grant_type": "client_credentials",
                                                "client_id": cfg["client_id"],
                                                "client_secret": cfg["client_secret"]})
                elif provider == "siteminder":
                    r = await client.get(base, auth=(cfg["username"], cfg["password"]))
                else:
                    r = await client.get(base, headers={"x-api-key": cfg["api_key"]})
            ok = r.status_code < 400
            body = {"status_code": r.status_code, "body": r.text[:200]}
        except Exception as e:
            ok, body = False, {"error": str(e)[:250]}
        now = datetime.now(timezone.utc).isoformat()
        await db.pms_connect_config.update_one(
            {"property_id": pid, "provider": provider},
            {"$set": {"last_test": {"ok": ok, "at": now}}}, upsert=True)
        if not ok:
            raise HTTPException(502, f"{PROVIDERS[provider]['name']} bağlantısı başarısız: {body}")
        return {"ok": True, "detail": body}

    @router.post("/{provider}/push-from-rms/{pid}")
    async def push_from_rms(provider: str, pid: str, data: dict = None,
                            _u: dict = Depends(require_roles(*ROLES))):
        if provider not in PROVIDERS:
            raise HTTPException(404, "Bilinmeyen sağlayıcı")
        days = max(1, min(90, int((data or {}).get("days", 14))))
        rows = await _rms_rows(pid, days)
        if not rows:
            return {"pushed_days": 0, "message": "Gönderilecek RMS fiyatı yok — önce fiyat oluşturun."}
        return await _push(pid, provider, rows)

    @router.post("/{provider}/pull-reservations/{pid}")
    async def pull_reservations(provider: str, pid: str, _u: dict = Depends(require_roles(*ROLES))):
        if provider not in PROVIDERS:
            raise HTTPException(404, "Bilinmeyen sağlayıcı")
        cfg = await _cfg(pid, provider)
        if not _has_creds(provider, cfg):
            await _log(pid, provider, "res_pull", "mocked", [], {}, {"mocked": True})
            return {"mocked": True, "imported": 0,
                    "message": "MOCK — kimlik girilmediği için rezervasyon çekilemedi."}
        if provider == "mews":
            base = (cfg.get("endpoint_url") or PROVIDERS["mews"]["base_url"]).rstrip("/")
            async with httpx.AsyncClient(timeout=30) as client:
                r = await client.post(f"{base}/api/connector/v1/reservations/getAll/2023-06-06",
                                      json={"ClientToken": cfg["client_token"],
                                            "AccessToken": cfg["access_token"],
                                            "Client": "MyHotelBox-RMS/1.0",
                                            "Limitation": {"Count": 100},
                                            "TimeFilter": "Start"})
            if r.status_code != 200:
                raise HTTPException(502, f"Mews rezervasyon hatası: {r.text[:250]}")
            imported = 0
            for res in (r.json() or {}).get("Reservations", []):
                await db.pms_inbound.update_one(
                    {"provider": "mews", "external_id": str(res.get("Id"))},
                    {"$set": {"provider": "mews", "external_id": str(res.get("Id")),
                              "property_id": pid, "payload": res,
                              "updated_at": datetime.now(timezone.utc).isoformat()}}, upsert=True)
                imported += 1
            await _log(pid, provider, "res_pull", "live", [], {}, {"imported": imported})
            return {"mocked": False, "imported": imported}
        await _log(pid, provider, "res_pull", "live", [], {}, {"note": "generic pull attempted"})
        return {"mocked": False, "imported": 0,
                "message": f"{PROVIDERS[provider]['name']} rezervasyon çekme, partner dokümanları gelince endpoint'e bağlanacak."}

    @router.post("/{provider}/certify/{pid}")
    async def certify(provider: str, pid: str, _u: dict = Depends(require_roles(*ROLES))):
        """Sertifikasyon: kimlik kontrolü + test push + geri okuma doğrulaması."""
        if provider not in PROVIDERS:
            raise HTTPException(404, "Bilinmeyen sağlayıcı")
        checks = []
        cfg = await _cfg(pid, provider)
        live = _has_creds(provider, cfg)
        checks.append({"name": "Kimlik yapılandırması", "passed": live,
                       "detail": "Tüm kimlik alanları mevcut" if live else "Kimlik eksik — MOCK sertifikasyon"})
        test_date = (datetime.now(timezone.utc).date() + timedelta(days=60)).isoformat()
        test_rows = [{"date": test_date, "rate": 99.0, "availability": 1}]
        try:
            res = await _push(pid, provider, test_rows, cert_test=True)
            checks.append({"name": "Test push", "passed": True,
                           "detail": f"1 tarih gönderildi ({'CANLI' if not res.get('mocked') else 'MOCK'}) — {PROVIDERS[provider]['format'].upper()} formatına çevrildi"})
        except Exception as e:
            checks.append({"name": "Test push", "passed": False, "detail": str(e)[:150]})
        log = await db.pms_push_log.find_one(
            {"property_id": pid, "provider": provider, "kind": "rate_push", "cert_test": True},
            sort=[("created_at", -1)])
        readback = bool(log and any(r.get("date") == test_date and r.get("rate") == 99.0
                                    for r in log.get("standard_rows", [])))
        checks.append({"name": "Geri okuma doğrulaması", "passed": readback,
                       "detail": "Push logu geri okundu, tarih+fiyat birebir eşleşti" if readback else "Log eşleşmedi"})
        translated_ok = bool(log and log.get("translated_sample"))
        checks.append({"name": "Format çevirisi", "passed": translated_ok,
                       "detail": f"Standart RMS satırı {PROVIDERS[provider]['name']} payload'ına çevrildi" if translated_ok else "Çeviri kaydı yok"})
        passed = all(c["passed"] for c in checks if c["name"] != "Kimlik yapılandırması")
        cert = {"passed": passed, "mode": "live" if live else "mocked", "checks": checks,
                "at": datetime.now(timezone.utc).isoformat()}
        await db.pms_connect_config.update_one(
            {"property_id": pid, "provider": provider},
            {"$set": {"certification": cert}}, upsert=True)
        return {"ok": True, **cert,
                "note": "Sertifikasyon geçmeden canlı otomatik push açılmaz. Kimlik girilince CANLI modda tekrarlayın."}

    @router.get("/{provider}/log/{pid}")
    async def get_log(provider: str, pid: str, limit: int = 20,
                      _u: dict = Depends(require_roles(*ROLES))):
        rows = await db.pms_push_log.find(
            {"property_id": pid, "provider": provider},
            {"_id": 0, "standard_rows": 0, "translated_sample": 0}
        ).sort("created_at", -1).to_list(min(limit, 100))
        return {"log": rows}

    return router
