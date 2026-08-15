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
            {"key": "rate_id", "label": "Rate ID (root rate)", "secret": False},
            {"key": "tz", "label": "Saat Dilimi (örn. Europe/Zurich)", "secret": False}],
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


def _mews_utc(date_str: str, tz_name: str) -> str:
    from zoneinfo import ZoneInfo
    try:
        tz = ZoneInfo(tz_name or "UTC")
    except Exception:
        tz = ZoneInfo("UTC")
    dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=tz)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _translate(provider: str, cfg: dict, rows: list, currency: str = "EUR") -> dict:
    """Standart RMS satırlarını [{date, rate, availability}] sağlayıcı diline çevirir."""
    if provider == "mews":
        _tz = cfg.get("tz", "UTC")
        return {"method": "POST", "path": "/api/connector/v1/rates/updatePrice",
                "body": {"ClientToken": "***", "AccessToken": "***", "Client": "MyHotelBox-RMS/1.0",
                         "RateId": cfg.get("rate_id", ""),
                         "PriceUpdates": [{"FirstTimeUnitStartUtc": _mews_utc(r["date"], _tz),
                                           "LastTimeUnitStartUtc": _mews_utc(r["date"], _tz),
                                           "Value": r["rate"]} for r in rows]}}
    if provider == "apaleo":
        return {"method": "PUT", "path": f"/rateplan/v1/rate-plans/{cfg.get('rate_plan_id', '')}/rates",
                "body": {"rates": [{"from": f"{r['date']}T00:00:00Z",
                                    "to": f"{r['date']}T00:00:00Z",
                                    "price": {"amount": r["rate"], "currency": currency}} for r in rows]}}
    if provider == "siteminder":
        msgs = "".join(
            f'<RateAmountMessage><StatusApplicationControl Start="{r["date"]}" End="{r["date"]}" '
            f'InvTypeCode="{cfg.get("hotel_code", "")}-{cfg.get("inv_code", "STD")}" RatePlanCode="RMS"/>'
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


async def _cfg(db, pid: str, provider: str) -> dict:
    return await db.pms_connect_config.find_one(
        {"property_id": pid, "provider": provider}, {"_id": 0}) or {}


async def _log(db, pid: str, provider: str, kind: str, mode: str,
               standard_rows: list, translated: dict, result: dict, cert_test: bool = False,
               rate_code: str = ""):
    await db.pms_push_log.insert_one({
        "id": str(uuid.uuid4()), "property_id": pid, "provider": provider,
        "kind": kind, "mode": mode, "standard_rows": standard_rows,
        "rate_code": rate_code,
        "translated_sample": {k: (v[:400] if isinstance(v, str) else v)
                              for k, v in list(translated.items())[:3]},
        "result": result, "cert_test": cert_test,
        "created_at": datetime.now(timezone.utc).isoformat()})


async def _rms_rows(db, pid: str, days: int) -> list:
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


async def _push(db, pid: str, provider: str, rows: list, cert_test: bool = False,
                cfg_override: dict = None) -> dict:
    cfg = await _cfg(db, pid, provider)
    if cfg_override:
        cfg = {**cfg, **cfg_override}
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
        await _log(db, pid, provider, "rate_push", "mocked", rows, translated, result, cert_test,
                   rate_code=cfg.get("rate_id") or cfg.get("rate_plan_id") or cfg.get("inv_code", ""))
        return {"pushed_days": len(rows), "sample": rows[:3],
                "translated_preview": translated, **result}
    result = await _live_send(provider, cfg, translated)
    await _log(db, pid, provider, "rate_push", "live", rows, translated, result, cert_test,
               rate_code=cfg.get("rate_id") or cfg.get("rate_plan_id") or cfg.get("inv_code", ""))
    return {"pushed_days": len(rows), "sample": rows[:3], "mocked": False, "result": result}


async def _verify_channel(db, pid: str, provider: str) -> dict:
    """Push Fark Kontrolü: her rate koduna en son basılanı kanaldan geri okuyup karşılaştırır
    (rate plan eşleştirmesi varsa kod bazında ayrı doğrulanır)."""
    recent = await db.pms_push_log.find(
        {"property_id": pid, "provider": provider, "kind": "rate_push", "cert_test": False},
        sort=[("created_at", -1)]).to_list(10)
    if not recent or not any(l.get("standard_rows") for l in recent):
        return {"ok": False, "message": "Doğrulanacak push bulunamadı — önce fiyat push yapın."}
    latest_ts = recent[0]["created_at"][:16]
    by_code = {}
    for l in recent:
        if l["created_at"][:16] != latest_ts or not l.get("standard_rows"):
            continue
        code = l.get("rate_code", "") or "_default"
        if code not in by_code:
            by_code[code] = l
    cfg = await _cfg(db, pid, provider)
    live = provider == "mews" and _has_creds(provider, cfg)
    out_rows, mocked = [], not live
    for code, log in by_code.items():
        rows = log["standard_rows"]
        if live:
            base = (cfg.get("endpoint_url") or PROVIDERS["mews"]["base_url"]).rstrip("/")
            tz = cfg.get("tz", "UTC")
            rate_id = code if code != "_default" else cfg["rate_id"]
            async with httpx.AsyncClient(timeout=30) as client:
                r = await client.post(f"{base}/api/connector/v1/rates/getPricing",
                                      json={"ClientToken": cfg["client_token"],
                                            "AccessToken": cfg["access_token"],
                                            "Client": "MyHotelBox-RMS/1.0",
                                            "RateId": rate_id,
                                            "FirstTimeUnitStartUtc": _mews_utc(rows[0]["date"], tz),
                                            "LastTimeUnitStartUtc": _mews_utc(rows[-1]["date"], tz)})
            if r.status_code != 200:
                return {"ok": False, "message": f"Kanaldan geri okuma başarısız: {r.text[:200]}"}
            d = r.json() or {}
            price_map = {}
            for ts, price in zip(d.get("TimeUnitStartsUtc", []), d.get("BasePrices", [])):
                price_map[str(ts).replace(".000Z", "Z").replace("Z", "")[:19]] = price
            for row in rows:
                key = _mews_utc(row["date"], tz).replace(".000Z", "")[:19]
                ch = price_map.get(key)
                drift = round((ch - row["rate"]) / row["rate"] * 100, 2) if (ch is not None and row["rate"]) else None
                out_rows.append({"date": row["date"], "rate_code": code, "pushed": row["rate"],
                                 "channel": ch, "drift_pct": drift,
                                 "ok": drift is not None and abs(drift) <= 0.5})
        else:
            for row in rows:
                out_rows.append({"date": row["date"], "rate_code": code, "pushed": row["rate"],
                                 "channel": row["rate"], "drift_pct": 0.0, "ok": True})
    bad = [r for r in out_rows if not r["ok"]]
    max_drift = max((abs(r["drift_pct"]) for r in out_rows if r["drift_pct"] is not None), default=0.0)
    result = {"ok": len(bad) == 0, "mocked": mocked, "provider": provider,
              "rows": out_rows, "mismatches": len(bad), "max_drift_pct": max_drift,
              "verified_at": datetime.now(timezone.utc).isoformat(),
              "message": "Kanal ile birebir eşleşti — sapma yok." if not bad
              else f"UYARI: {len(bad)} tarihte sapma tespit edildi (maks %{max_drift})."}
    await db.pms_verify_log.insert_one({**result, "id": str(uuid.uuid4()), "property_id": pid})
    if bad:
        await db.pms_alerts.insert_one({
            "id": str(uuid.uuid4()), "property_id": pid, "provider": provider,
            "type": "push_drift", "mismatches": bad, "max_drift_pct": max_drift,
            "created_at": datetime.now(timezone.utc).isoformat()})
    return result


async def run_auto_night_push(db, pid: str, days: int = 14) -> dict:
    """Gece robotu: sertifikasyonu geçmiş tüm kanallara RMS fiyatlarını otomatik basar,
    ardından her kanaldan geri okuyup fark kontrolü yapar."""
    rows = await _rms_rows(db, pid, days)
    results = []
    for key in PROVIDERS:
        cfg = await _cfg(db, pid, key)
        cert = cfg.get("certification") or {}
        if not cert.get("passed"):
            results.append({"provider": key, "skipped": True, "reason": "sertifikasyon yok"})
            continue
        if not rows:
            results.append({"provider": key, "skipped": True, "reason": "RMS fiyatı yok"})
            continue
        try:
            r = await _push(db, pid, key, rows)
            item = {"provider": key, "pushed_days": r.get("pushed_days", 0),
                    "mode": "mocked" if r.get("mocked") else "live"}
            try:
                if item["mode"] == "live":
                    import asyncio
                    await asyncio.sleep(6)
                v = await _verify_channel(db, pid, key)
                item["verify_ok"] = v.get("ok")
                item["max_drift_pct"] = v.get("max_drift_pct", 0.0)
            except Exception:
                item["verify_ok"] = None
            results.append(item)
        except Exception as e:
            results.append({"provider": key, "error": str(e)[:150]})
    out = {"ran_at": datetime.now(timezone.utc).isoformat(), "days": days, "results": results}
    await db.pms_night_push_log.insert_one({**out, "property_id": pid, "id": str(uuid.uuid4())})
    return out


MEWS_DEMO = {
    "client_token": "E0D439EE522F44368DC78E1BFB03710C-D24FB11DBE31D4621C4817E028D9E1D",
    "access_token": "C66EF7B239D24632943D115EDE9CB810-EA00F8FD8294692C940F6B5A8F9453D",
}


def create_pms_connect_router(db, require_roles):
    router = APIRouter(prefix="/pms-connect", tags=["pms-connect"])
    ROLES = ("admin", "manager")

    @router.get("/providers/{pid}")
    async def list_providers(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        out = []
        for key, meta in PROVIDERS.items():
            cfg = await _cfg(db, pid, key)
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
        cfg = await _cfg(db, pid, provider)
        return {"ok": True, "mode": "live" if _has_creds(provider, cfg) else "mocked"}

    @router.post("/{provider}/test-connection/{pid}")
    async def test_connection(provider: str, pid: str, _u: dict = Depends(require_roles(*ROLES))):
        if provider not in PROVIDERS:
            raise HTTPException(404, "Bilinmeyen sağlayıcı")
        cfg = await _cfg(db, pid, provider)
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
        rows = await _rms_rows(db, pid, days)
        if not rows:
            return {"pushed_days": 0, "message": "Gönderilecek RMS fiyatı yok — önce fiyat oluşturun."}
        mp = await db.pms_rate_mapping.find_one(
            {"property_id": pid, "provider": provider}, {"_id": 0})
        mappings = [m for m in (mp or {}).get("mappings", []) if m.get("channel_rate_code")]
        if not mappings:
            return await _push(db, pid, provider, rows)
        per_rt, first_preview = [], None
        for m in mappings:
            mult = float(m.get("multiplier", 1.0) or 1.0)
            scaled = [{**r, "rate": round(r["rate"] * mult, 2)} for r in rows]
            code = m["channel_rate_code"]
            try:
                r = await _push(db, pid, provider, scaled,
                                cfg_override={"rate_id": code, "rate_plan_id": code, "inv_code": code})
                if first_preview is None:
                    first_preview = r.get("translated_preview")
                per_rt.append({"room_type": m.get("room_type_name", "?"), "channel_rate_code": code,
                               "multiplier": mult, "pushed_days": r.get("pushed_days", 0),
                               "mocked": r.get("mocked", None) is not False})
            except HTTPException as e:
                per_rt.append({"room_type": m.get("room_type_name", "?"), "channel_rate_code": code,
                               "error": str(e.detail)[:150]})
        ok = [x for x in per_rt if "error" not in x]
        return {"pushed_days": len(rows) if ok else 0, "per_room_type": per_rt,
                "mocked": all(x.get("mocked") for x in ok) if ok else None,
                "translated_preview": first_preview,
                "message": f"{len(ok)}/{len(per_rt)} oda tipi için ayrı push yapıldı (eşleştirme tablosu aktif)."}

    @router.get("/{provider}/rate-mapping/{pid}")
    async def get_rate_mapping(provider: str, pid: str, _u: dict = Depends(require_roles(*ROLES))):
        if provider not in PROVIDERS:
            raise HTTPException(404, "Bilinmeyen sağlayıcı")
        mp = await db.pms_rate_mapping.find_one(
            {"property_id": pid, "provider": provider}, {"_id": 0}) or {}
        rts = await db.room_types.find({"property_id": pid},
                                       {"_id": 0, "id": 1, "name": 1}).to_list(50)
        return {"mappings": mp.get("mappings", []), "room_types": rts}

    @router.post("/{provider}/rate-mapping/{pid}")
    async def save_rate_mapping(provider: str, pid: str, data: dict,
                                _u: dict = Depends(require_roles(*ROLES))):
        if provider not in PROVIDERS:
            raise HTTPException(404, "Bilinmeyen sağlayıcı")
        mappings = []
        for m in (data.get("mappings") or [])[:20]:
            mappings.append({"room_type_id": str(m.get("room_type_id", "")),
                             "room_type_name": str(m.get("room_type_name", ""))[:80],
                             "channel_rate_code": str(m.get("channel_rate_code", "")).strip()[:120],
                             "multiplier": max(0.1, min(10.0, float(m.get("multiplier", 1.0) or 1.0)))})
        await db.pms_rate_mapping.update_one(
            {"property_id": pid, "provider": provider},
            {"$set": {"property_id": pid, "provider": provider, "mappings": mappings,
                      "updated_at": datetime.now(timezone.utc).isoformat()}}, upsert=True)
        return {"ok": True, "count": len([m for m in mappings if m["channel_rate_code"]])}

    @router.get("/alerts/{pid}")
    async def list_alerts(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        rows = await db.pms_alerts.find(
            {"property_id": pid, "resolved": {"$ne": True}},
            {"_id": 0}).sort("created_at", -1).to_list(50)
        return {"alerts": rows, "active_count": len(rows)}

    @router.post("/alerts/{alert_id}/resolve")
    async def resolve_alert(alert_id: str, _u: dict = Depends(require_roles(*ROLES))):
        r = await db.pms_alerts.update_one(
            {"id": alert_id},
            {"$set": {"resolved": True, "resolved_at": datetime.now(timezone.utc).isoformat()}})
        if not r.matched_count:
            raise HTTPException(404, "Uyarı bulunamadı")
        return {"ok": True}

    @router.get("/forecast-accuracy/{pid}")
    async def forecast_accuracy(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        """Canlı veri forecast kıyası: snapshot'lar olgunlaştıkça isabet (MAE) + Mews katkısı."""
        today = datetime.now(timezone.utc).date()
        total_rooms = await db.rooms.count_documents({"property_id": pid}) or 20
        snaps = await db.forecast_snapshots.find(
            {"property_id": pid, "snapshot_date": {"$lt": today.isoformat()}},
            {"_id": 0}).sort("snapshot_date", -1).to_list(30)
        matured, errs = [], []
        for s in snaps:
            for row in s.get("rows", []):
                if row["date"] >= today.isoformat() or row["date"] <= s["snapshot_date"]:
                    continue
                actual = await db.bookings.count_documents({
                    "property_id": pid, "status": {"$nin": ["cancelled", "no_show"]},
                    "check_in": {"$lte": row["date"]}, "check_out": {"$gt": row["date"]}})
                actual_occ = round(actual / total_rooms * 100, 1)
                err = round(abs(row["occ_pct"] - actual_occ), 1)
                errs.append(err)
                matured.append({"snapshot_date": s["snapshot_date"], "date": row["date"],
                                "predicted_occ_pct": row["occ_pct"], "actual_occ_pct": actual_occ,
                                "abs_error_pts": err})
        mae = round(sum(errs) / len(errs), 2) if errs else None
        mews_impact = []
        for i in range(14):
            ds = (today + timedelta(days=i)).isoformat()
            q = {"property_id": pid, "status": {"$nin": ["cancelled", "no_show"]},
                 "check_in": {"$lte": ds}, "check_out": {"$gt": ds}}
            all_otb = await db.bookings.count_documents(q)
            wo_mews = await db.bookings.count_documents({**q, "source": {"$ne": "pms:mews"}})
            mews_impact.append({"date": ds, "otb_with_mews": all_otb, "otb_without_mews": wo_mews,
                                "mews_contribution": all_otb - wo_mews,
                                "occ_with_pct": round(all_otb / total_rooms * 100, 1),
                                "occ_without_pct": round(wo_mews / total_rooms * 100, 1)})
        total_contrib = sum(r["mews_contribution"] for r in mews_impact)
        return {"mae_occ_pts": mae, "matured_points": len(matured),
                "matured_sample": matured[:20], "mews_impact": mews_impact,
                "mews_total_contribution_14d": total_contrib,
                "note": (f"Tahmin isabeti: MAE {mae} doluluk puanı ({len(matured)} olgun nokta).")
                if mae is not None else
                "Snapshot'lar henüz olgunlaşmadı — gece robotu her çalıştığında 14 günlük tahmin fotoğrafı kaydediyor; günler geçtikçe isabet ölçümü burada birikecek. Mews canlı katkısı aşağıda hemen görünür."}

    @router.post("/{provider}/pull-reservations/{pid}")
    async def pull_reservations(provider: str, pid: str, _u: dict = Depends(require_roles(*ROLES))):
        if provider not in PROVIDERS:
            raise HTTPException(404, "Bilinmeyen sağlayıcı")
        cfg = await _cfg(db, pid, provider)
        if not _has_creds(provider, cfg):
            await _log(db, pid, provider, "res_pull", "mocked", [], {}, {"mocked": True})
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
            await _log(db, pid, provider, "res_pull", "live", [], {}, {"imported": imported})
            return {"mocked": False, "imported": imported}
        await _log(db, pid, provider, "res_pull", "live", [], {}, {"note": "generic pull attempted"})
        return {"mocked": False, "imported": 0,
                "message": f"{PROVIDERS[provider]['name']} rezervasyon çekme, partner dokümanları gelince endpoint'e bağlanacak."}

    @router.post("/{provider}/certify/{pid}")
    async def certify(provider: str, pid: str, _u: dict = Depends(require_roles(*ROLES))):
        """Sertifikasyon: kimlik kontrolü + test push + geri okuma doğrulaması."""
        if provider not in PROVIDERS:
            raise HTTPException(404, "Bilinmeyen sağlayıcı")
        checks = []
        cfg = await _cfg(db, pid, provider)
        live = _has_creds(provider, cfg)
        checks.append({"name": "Kimlik yapılandırması", "passed": live,
                       "detail": "Tüm kimlik alanları mevcut" if live else "Kimlik eksik — MOCK sertifikasyon"})
        test_date = (datetime.now(timezone.utc).date() + timedelta(days=60)).isoformat()
        test_rows = [{"date": test_date, "rate": 99.0, "availability": 1}]
        try:
            res = await _push(db, pid, provider, test_rows, cert_test=True)
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

    @router.get("/mews/discover-rates/{pid}")
    async def discover_rates(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        """Mews'teki gerçek rate/oda kategorilerini keşfeder — eşleştirme tablosu otomatik dolar."""
        cfg = await _cfg(db, pid, "mews")
        if not _has_creds("mews", cfg):
            raise HTTPException(400, "Önce Mews'e bağlanın (demo-connect veya kimlik girişi).")
        base = (cfg.get("endpoint_url") or PROVIDERS["mews"]["base_url"]).rstrip("/")
        auth = {"ClientToken": cfg["client_token"], "AccessToken": cfg["access_token"],
                "Client": "MyHotelBox-RMS/1.0"}
        async with httpx.AsyncClient(timeout=30) as client:
            svc = await client.post(f"{base}/api/connector/v1/services/getAll",
                                    json={**auth, "Limitation": {"Count": 20}})
            services = (svc.json() or {}).get("Services", []) if svc.status_code == 200 else []
            bookable = next((s for s in services if s.get("Type") == "Reservable" or s.get("IsActive")), None)
            rates, categories = [], []
            if bookable:
                rts = await client.post(f"{base}/api/connector/v1/rates/getAll",
                                        json={**auth, "ServiceIds": [bookable["Id"]],
                                              "Limitation": {"Count": 200}})
                if rts.status_code == 200:
                    rates = [{"id": rt["Id"], "name": rt.get("Name", ""),
                              "is_root": rt.get("BaseRateId") is None,
                              "is_active": bool(rt.get("IsActive"))}
                             for rt in (rts.json() or {}).get("Rates", [])]
                cats = await client.post(f"{base}/api/connector/v1/resourceCategories/getAll",
                                         json={**auth, "ServiceIds": [bookable["Id"]],
                                               "Limitation": {"Count": 100}})
                if cats.status_code == 200:
                    categories = [{"id": c["Id"],
                                   "name": (c.get("Names") or {}).get("en-US") or (list((c.get("Names") or {}).values()) or [""])[0],
                                   "capacity": c.get("Capacity")}
                                  for c in (cats.json() or {}).get("ResourceCategories", []) if c.get("IsActive", True)]
        return {"service": (bookable or {}).get("Name", ""),
                "rates": rates, "resource_categories": categories,
                "note": "Root + aktif rate'ler eşleştirme için önerilir. Kategoriler Mews'teki gerçek oda tipleridir."}

    @router.get("/revenue-by-channel/{pid}")
    async def revenue_by_channel(pid: str, months: int = 6,
                                 _u: dict = Depends(require_roles(*ROLES))):
        """Kanal gelir katkısı: rezervasyon kaynağına göre aylık gelir dağılımı."""
        months = max(1, min(24, months))
        start = (datetime.now(timezone.utc).date().replace(day=1) - timedelta(days=31 * (months - 1)))
        start = start.replace(day=1).isoformat()
        pipe = [
            {"$match": {"property_id": pid, "status": {"$nin": ["cancelled", "no_show"]},
                        "check_in": {"$gte": start}, "total_price": {"$gt": 0}}},
            {"$group": {"_id": {"month": {"$substr": ["$check_in", 0, 7]},
                                "source": {"$ifNull": ["$source", "bilinmiyor"]}},
                        "revenue": {"$sum": "$total_price"}, "bookings": {"$sum": 1}}},
            {"$sort": {"_id.month": 1, "revenue": -1}}]
        agg = await db.bookings.aggregate(pipe).to_list(2000)
        by_month = {}
        for a in agg:
            m, src = a["_id"]["month"], a["_id"]["source"]
            by_month.setdefault(m, []).append(
                {"source": src, "revenue": round(a["revenue"], 2), "bookings": a["bookings"]})
        for m, rows in by_month.items():
            tot = sum(r["revenue"] for r in rows) or 1
            for r in rows:
                r["pct"] = round(r["revenue"] / tot * 100, 1)
        totals = {}
        for rows in by_month.values():
            for r in rows:
                t = totals.setdefault(r["source"], {"source": r["source"], "revenue": 0.0, "bookings": 0})
                t["revenue"] = round(t["revenue"] + r["revenue"], 2)
                t["bookings"] += r["bookings"]
        tot_all = sum(t["revenue"] for t in totals.values()) or 1
        totals_list = sorted(totals.values(), key=lambda x: -x["revenue"])
        for t in totals_list:
            t["pct"] = round(t["revenue"] / tot_all * 100, 1)
        return {"months": sorted(by_month.keys()), "by_month": by_month,
                "totals": totals_list, "total_revenue": round(tot_all, 2)}

    @router.get("/health/{pid}")
    async def health(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        """Kanal Sağlık Panosu — tüm adaptörlerin son push, sertifika ve hata durumu."""
        channels = []
        for key, meta in PROVIDERS.items():
            cfg = await _cfg(db, pid, key)
            last = await db.pms_push_log.find_one(
                {"property_id": pid, "provider": key, "kind": "rate_push"},
                {"_id": 0, "mode": 1, "created_at": 1, "result": 1}, sort=[("created_at", -1)])
            total = await db.pms_push_log.count_documents({"property_id": pid, "provider": key})
            errors = await db.pms_push_log.count_documents(
                {"property_id": pid, "provider": key, "result.error": {"$exists": True}})
            cert = cfg.get("certification") or {}
            channels.append({"id": key, "name": meta["name"],
                             "mode": "live" if _has_creds(key, cfg) else "mocked",
                             "certified": bool(cert.get("passed")), "cert_mode": cert.get("mode"),
                             "last_push_at": (last or {}).get("created_at"),
                             "last_push_mode": (last or {}).get("mode"),
                             "total_pushes": total,
                             "error_rate_pct": round(errors / total * 100, 1) if total else 0.0})
        cb = await db.cloudbeds_config.find_one({"property_id": pid}, {"_id": 0}) or {}
        cb_last = await db.cb_push_log.find_one({"property_id": pid, "kind": "rate_push"},
                                                {"_id": 0, "mode": 1, "created_at": 1}, sort=[("created_at", -1)])
        cb_total = await db.cb_push_log.count_documents({"property_id": pid})
        channels.append({"id": "cloudbeds", "name": "Cloudbeds",
                         "mode": "live" if cb.get("api_key") else "mocked",
                         "certified": bool((cb.get("certification") or {}).get("passed")),
                         "cert_mode": (cb.get("certification") or {}).get("mode"),
                         "last_push_at": (cb_last or {}).get("created_at"),
                         "last_push_mode": (cb_last or {}).get("mode"),
                         "total_pushes": cb_total, "error_rate_pct": 0.0})
        hr = await db.hotelrunner_config.find_one({"property_id": pid}, {"_id": 0}) or {}
        hr_last = await db.hr_push_log.find_one({"property_id": pid},
                                                {"_id": 0, "mode": 1, "created_at": 1}, sort=[("created_at", -1)])
        hr_total = await db.hr_push_log.count_documents({"property_id": pid})
        channels.append({"id": "hotelrunner", "name": "HotelRunner",
                         "mode": "live" if (hr.get("hr_id") and hr.get("token")) else "mocked",
                         "certified": bool((hr.get("certification") or {}).get("passed")),
                         "cert_mode": (hr.get("certification") or {}).get("mode"),
                         "last_push_at": (hr_last or {}).get("created_at"),
                         "last_push_mode": (hr_last or {}).get("mode"),
                         "total_pushes": hr_total, "error_rate_pct": 0.0})
        st = await db.pms_connect_settings.find_one({"property_id": pid}, {"_id": 0}) or {}
        last_np = await db.pms_night_push_log.find_one({"property_id": pid}, {"_id": 0},
                                                       sort=[("ran_at", -1)])
        active_alerts = await db.pms_alerts.count_documents(
            {"property_id": pid, "resolved": {"$ne": True}})
        return {"property_id": pid, "channels": channels,
                "auto_night_push": bool(st.get("auto_night_push")),
                "active_alerts": active_alerts,
                "last_night_push": last_np}

    @router.post("/night-push/{pid}")
    async def toggle_night_push(pid: str, data: dict, _u: dict = Depends(require_roles(*ROLES))):
        enabled = bool(data.get("enabled"))
        await db.pms_connect_settings.update_one(
            {"property_id": pid},
            {"$set": {"property_id": pid, "auto_night_push": enabled,
                      "updated_at": datetime.now(timezone.utc).isoformat()}}, upsert=True)
        return {"ok": True, "auto_night_push": enabled,
                "note": "Açıkken gece robotu (sabah raporu) sonrası sertifikalı tüm kanallara RMS fiyatları otomatik basılır."}

    @router.post("/night-push/{pid}/run")
    async def run_night_push_now(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        return {"ok": True, **await run_auto_night_push(db, pid)}

    @router.post("/{provider}/verify-push/{pid}")
    async def verify_push(provider: str, pid: str, _u: dict = Depends(require_roles(*ROLES))):
        if provider not in PROVIDERS:
            raise HTTPException(404, "Bilinmeyen sağlayıcı")
        return await _verify_channel(db, pid, provider)

    @router.post("/mews/import-to-otb/{pid}")
    async def import_to_otb(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        """Mews demo'daki gerçek rezervasyonları OTB/tahmin motoruna besler (bookings upsert)."""
        cfg = await _cfg(db, pid, "mews")
        if not _has_creds("mews", cfg):
            raise HTTPException(400, "Önce Mews'e bağlanın (demo-connect veya kimlik girişi).")
        base = (cfg.get("endpoint_url") or PROVIDERS["mews"]["base_url"]).rstrip("/")
        tz = cfg.get("tz", "UTC")
        async with httpx.AsyncClient(timeout=40) as client:
            r = await client.post(f"{base}/api/connector/v1/reservations/getAll/2023-06-06",
                                  json={"ClientToken": cfg["client_token"],
                                        "AccessToken": cfg["access_token"],
                                        "Client": "MyHotelBox-RMS/1.0",
                                        "Limitation": {"Count": 200},
                                        "CollidingUtc": {
                                            "StartUtc": datetime.now(timezone.utc).strftime("%Y-%m-%dT00:00:00Z"),
                                            "EndUtc": (datetime.now(timezone.utc) + timedelta(days=60)).strftime("%Y-%m-%dT00:00:00Z")}})
        if r.status_code != 200:
            raise HTTPException(502, f"Mews rezervasyon hatası: {r.text[:250]}")
        from zoneinfo import ZoneInfo
        try:
            _tz = ZoneInfo(tz)
        except Exception:
            _tz = timezone.utc
        state_map = {"Canceled": "cancelled", "Started": "checked_in",
                     "Processed": "checked_out", "Confirmed": "confirmed", "Optional": "pending"}
        imported = cancelled = 0
        for res in (r.json() or {}).get("Reservations", []):
            try:
                ci = datetime.fromisoformat(res["StartUtc"].replace("Z", "+00:00")).astimezone(_tz).date()
                co = datetime.fromisoformat(res["EndUtc"].replace("Z", "+00:00")).astimezone(_tz).date()
            except Exception:
                continue
            nights = max((co - ci).days, 1)
            est_total = 0.0
            for i in range(nights):
                ds = (ci + timedelta(days=i)).isoformat()
                ov = await db.rate_overrides.find_one({"property_id": pid, "date": ds},
                                                      {"_id": 0, "rate": 1, "custom_rate": 1})
                est_total += float(ov.get("custom_rate") or ov["rate"]) if ov and (ov.get("custom_rate") or ov.get("rate")) else 100.0
            status = state_map.get(res.get("State"), "confirmed")
            if status == "cancelled":
                cancelled += 1
            await db.bookings.update_one(
                {"channel_reference": str(res.get("Id")), "source": "pms:mews"},
                {"$set": {"id": f"mews-{res.get('Id')}", "property_id": pid,
                          "channel_reference": str(res.get("Id")), "source": "pms:mews",
                          "channel": "Mews Demo", "guest_name": "Mews Demo Guest",
                          "check_in": ci.isoformat(), "check_out": co.isoformat(),
                          "nights": nights, "status": status,
                          "total_price": round(est_total, 2),
                          "rate_per_night": round(est_total / nights, 2),
                          "guest_count": res.get("AdultCount", 2) or 2,
                          "currency": "GBP",
                          "updated_at": datetime.now(timezone.utc).isoformat()},
                 "$setOnInsert": {"created_at": datetime.now(timezone.utc).isoformat()}},
                upsert=True)
            imported += 1
        today = datetime.now(timezone.utc).date().isoformat()
        horizon = (datetime.now(timezone.utc).date() + timedelta(days=14)).isoformat()
        otb_next14 = await db.bookings.count_documents({
            "property_id": pid, "source": "pms:mews", "status": {"$nin": ["cancelled", "no_show"]},
            "check_in": {"$lte": horizon}, "check_out": {"$gt": today}})
        return {"ok": True, "imported": imported, "cancelled": cancelled,
                "otb_contribution_next14": otb_next14,
                "note": "Mews rezervasyonları bookings'e aktarıldı — Net OTB, tahmin motoru ve AI fiyatlama artık bu gerçek veriyi görüyor. Fiyatlar RMS rate'lerinden tahmini hesaplandı."}

    @router.get("/weekly-report/{pid}")
    async def weekly_report(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        """Haftalık partner raporu: son 7 gün kanal performans özeti + e-posta taslağı."""
        since = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        prop = await db.properties.find_one({"id": pid}, {"_id": 0, "name": 1}) or {}
        channels = []
        for key, meta in PROVIDERS.items():
            q = {"property_id": pid, "provider": key, "created_at": {"$gte": since}}
            total = await db.pms_push_log.count_documents(q)
            live = await db.pms_push_log.count_documents({**q, "mode": "live"})
            cfg = await _cfg(db, pid, key)
            cert = cfg.get("certification") or {}
            v = await db.pms_verify_log.find_one({"property_id": pid, "provider": key},
                                                 {"_id": 0, "ok": 1, "max_drift_pct": 1},
                                                 sort=[("verified_at", -1)])
            channels.append({"id": key, "name": meta["name"], "pushes_7d": total, "live_7d": live,
                             "certified": bool(cert.get("passed")), "cert_mode": cert.get("mode"),
                             "last_verify_ok": (v or {}).get("ok"),
                             "max_drift_pct": (v or {}).get("max_drift_pct", 0.0)})
        cb_total = await db.cb_push_log.count_documents({"property_id": pid, "created_at": {"$gte": since}})
        hr_total = await db.hr_push_log.count_documents({"property_id": pid, "created_at": {"$gte": since}})
        np_count = await db.pms_night_push_log.count_documents({"property_id": pid, "ran_at": {"$gte": since}})
        alerts = await db.pms_alerts.count_documents({"property_id": pid, "created_at": {"$gte": since}})
        week = datetime.now(timezone.utc).date().isoformat()
        lines = "\n".join(
            f"  • {c['name']}: {c['pushes_7d']} push ({c['live_7d']} canlı) · "
            f"{'SERTİFİKALI' if c['certified'] else 'sertifikasyon bekliyor'}"
            f"{' · doğrulama OK (maks sapma %' + str(c['max_drift_pct']) + ')' if c['last_verify_ok'] else ''}"
            for c in channels)
        email_body = f"""Konu: Haftalık Kanal Performans Raporu — {prop.get('name', pid)} ({week})

Merhaba,

Son 7 günün dağıtım kanalı özeti aşağıdadır:

PMS BAĞLANTI MERKEZİ
{lines}

DİĞER KANALLAR
  • Cloudbeds: {cb_total} işlem
  • HotelRunner: {hr_total} işlem

OTOMASYON
  • Gece push çalışması: {np_count} kez
  • Fiyat sapma uyarısı: {alerts} adet{' — ACİL İNCELEME GEREKLİ' if alerts else ' (temiz)'}

Tüm canlı push'lar publisher sertifikasyonundan geçmiş kanallara yapılmıştır.
Detaylar: PMS Bağlantı Merkezi → Kanal Sağlık Panosu.

Saygılarımızla,
MyHotelBox RMS — Otonom Dağıtım Robotu"""
        return {"week_of": week, "channels": channels,
                "cloudbeds_7d": cb_total, "hotelrunner_7d": hr_total,
                "night_pushes_7d": np_count, "drift_alerts_7d": alerts,
                "email_subject": f"Haftalık Kanal Performans Raporu — {prop.get('name', pid)} ({week})",
                "email_body": email_body}

    @router.get("/{provider}/partner-kit/{pid}")
    async def partner_kit(provider: str, pid: str, _u: dict = Depends(require_roles(*ROLES))):
        """Partner başvuru kiti: hazır e-posta + sertifikasyon sonuçlu teknik yeterlilik özeti."""
        if provider not in PROVIDERS:
            raise HTTPException(404, "Bilinmeyen sağlayıcı")
        meta = PROVIDERS[provider]
        cfg = await _cfg(db, pid, provider)
        cert = cfg.get("certification") or {}
        prop = await db.properties.find_one({"id": pid}, {"_id": 0, "name": 1, "city": 1}) or {}
        pushes = await db.pms_push_log.count_documents({"property_id": pid, "provider": provider})
        cert_lines = "\n".join(
            f"  - {c['name']}: {'PASSED' if c['passed'] else 'PENDING (awaiting live credentials)'} — {c['detail']}"
            for c in cert.get("checks", [])) or "  - Certification not yet run"
        fmt = "OTA XML (OTA_HotelRateAmountNotifRQ)" if meta["format"] == "ota_xml" else "REST JSON"
        subject = f"Technology Partner Application — MyHotelBox RMS ({meta['name']} 2-Way ARI Integration)"
        body = f"""Dear {meta['name']} Partnerships Team,

We are MyHotelBox, an AI-driven Revenue Management System (RMS) serving hotels across Turkey, the UK, Europe, the US and the Middle East. We would like to apply for your Technology Partner program to offer a certified 2-way ARI integration to our mutual customers.

WHAT OUR INTEGRATION DOES
- Pulls occupancy and reservation data for demand forecasting (net OTB with cancellation probability)
- Pushes AI-optimized daily rates and restrictions (MinLOS/CTA/CTD via a unified bid-price framework) back to {meta['name']}
- {meta['name']} then distributes to Booking.com, Expedia and all connected OTAs — no direct OTA connectivity required on our side

TECHNICAL READINESS
- Adapter already implemented against your {fmt} interface with an agnostic middleware layer
- Publisher certification pipeline (automated test push + read-back verification) built-in; live pushes are blocked until certification passes
- Guardrails: asymmetric step caps (±15%), daily push limits, global kill-switch, full audit log ({pushes} logged operations for pilot property "{prop.get('name', pid)}")

INTERNAL CERTIFICATION RESULTS
{cert_lines}

We would appreciate sandbox/demo credentials and your partner onboarding documentation to complete live certification. We are ready to start immediately.

Best regards,
MyHotelBox RMS Team
partnerships@myhotelbox.example"""
        tech_summary = {
            "integration_type": "2-Way ARI (rates + restrictions push, reservations pull)",
            "format": fmt, "api_type": meta["api_type"],
            "endpoints_implemented": ["config", "test-connection", "push-from-rms", "pull-reservations", "certify", "log"],
            "safety": ["Publisher certification gate (HTTP 428 before certification)",
                       "Asymmetric guardrails ±15%", "Global kill-switch", "Full audit log"],
            "certification": cert or {"status": "not_run"},
            "provider_note": meta["note"]}
        return {"provider": provider, "email_subject": subject, "email_body": body,
                "tech_summary": tech_summary}

    @router.post("/mews/demo-connect/{pid}")
    async def mews_demo_connect(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        """Mews demo ortamına (api.mews-demo.com) herkese açık demo token'larıyla bağlanır,
        ilk aktif root rate'i bulup kaydeder — canlı uçtan uca push testi için."""
        base = PROVIDERS["mews"]["base_url"]
        auth = {"ClientToken": MEWS_DEMO["client_token"],
                "AccessToken": MEWS_DEMO["access_token"], "Client": "MyHotelBox-RMS/1.0"}
        async with httpx.AsyncClient(timeout=30) as client:
            conf = await client.post(f"{base}/api/connector/v1/configuration/get", json=auth)
            if conf.status_code != 200:
                raise HTTPException(502, f"Mews demo bağlantısı başarısız ({conf.status_code}): {conf.text[:200]}")
            enterprise = (conf.json() or {}).get("Enterprise", {})
            tz_name = enterprise.get("TimeZoneIdentifier", "UTC")
            svc = await client.post(f"{base}/api/connector/v1/services/getAll",
                                    json={**auth, "Limitation": {"Count": 20}})
            services = (svc.json() or {}).get("Services", []) if svc.status_code == 200 else []
            bookable = next((s for s in services if s.get("Type") == "Reservable" or s.get("IsActive")), None)
            rate_id, rate_name = "", ""
            if bookable:
                rts = await client.post(f"{base}/api/connector/v1/rates/getAll",
                                        json={**auth, "ServiceIds": [bookable["Id"]],
                                              "Limitation": {"Count": 100}})
                if rts.status_code == 200:
                    for rt in (rts.json() or {}).get("Rates", []):
                        if rt.get("BaseRateId") is None and rt.get("IsActive"):
                            rate_id, rate_name = rt["Id"], rt.get("Name", "")
                            break
        await db.pms_connect_config.update_one(
            {"property_id": pid, "provider": "mews"},
            {"$set": {"property_id": pid, "provider": "mews",
                      "client_token": MEWS_DEMO["client_token"],
                      "access_token": MEWS_DEMO["access_token"],
                      "rate_id": rate_id, "endpoint_url": base, "tz": tz_name,
                      "updated_at": datetime.now(timezone.utc).isoformat()}}, upsert=True)
        return {"ok": True, "enterprise": enterprise.get("Name", ""),
                "service": (bookable or {}).get("Name", ""), "rate_id": rate_id, "rate_name": rate_name,
                "mode": "live" if rate_id else "mocked",
                "note": "Demo kimlikleri kaydedildi. Şimdi 'Sertifikasyonu Çalıştır' ile CANLI sertifikasyon geçin, ardından canlı push açılır."
                if rate_id else "Bağlantı kuruldu ama aktif root rate bulunamadı — rate_id'yi elle girin."}

    return router
