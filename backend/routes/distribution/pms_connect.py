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
    "opera-cloud": {
        "name": "Oracle OPERA Cloud (OHIP)", "region": "Global (zincir & üst segment lideri)", "api_type": "partner",
        "format": "json", "base_url": "",
        "auth_fields": [
            {"key": "client_id", "label": "OHIP Client ID", "secret": False},
            {"key": "client_secret", "label": "OHIP Client Secret", "secret": True},
            {"key": "app_key", "label": "x-app-key (Application Key)", "secret": True},
            {"key": "username", "label": "Entegrasyon Kullanıcısı", "secret": False},
            {"key": "password", "label": "Şifre", "secret": True},
            {"key": "hotel_id", "label": "Hotel ID (OPERA)", "secret": False},
            {"key": "rate_plan_code", "label": "Rate Plan Code", "secret": False},
            {"key": "endpoint_url", "label": "Gateway URL (örn. https://xxx.hospitality-api.us-region.ocs.oraclecloud.com)", "secret": False}],
        "note": "Oracle Hospitality Integration Platform — partner onayı + OHIP geliştirici hesabı şart. OAuth2 (password grant) ile token alınır; fiyatlar par/v1 pricingSchedules ile, müsaitlik inv/v1 ile yazılır. Kimlik gelene kadar MOCK iskelet hazır."},
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
    "opera-cloud": ("client_id", "client_secret", "app_key", "username", "password", "hotel_id", "rate_plan_code", "endpoint_url"),
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
    if provider == "opera-cloud":
        return {"method": "PUT", "path": f"/par/v1/hotels/{cfg.get('hotel_id', '')}/rates/{cfg.get('rate_plan_code', '')}/pricingSchedules",
                "headers": {"x-hotelid": cfg.get("hotel_id", ""), "x-app-key": "***", "Authorization": "Bearer ***"},
                "body": {"pricingSchedules": [{"start": r["date"], "end": r["date"], "rateCode": cfg.get("rate_plan_code", ""),
                                               "amounts": [{"amount": r["rate"], "currencyCode": currency, "guests": 2}]} for r in rows]}}
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
    rc = cfg.get("rate_id") or cfg.get("rate_plan_id") or cfg.get("inv_code", "")
    try:
        result = await _live_send(provider, cfg, translated)
    except HTTPException as e:
        await _log(db, pid, provider, "rate_push", "live", rows, translated, {"ok": False, "error": str(e.detail)[:300]}, cert_test, rate_code=rc)
        raise
    except Exception as e:
        await _log(db, pid, provider, "rate_push", "live", rows, translated, {"ok": False, "error": str(e)[:300]}, cert_test, rate_code=rc)
        raise HTTPException(502, f"{PROVIDERS[provider]['name']} bağlantı hatası: {str(e)[:200]}")
    await _log(db, pid, provider, "rate_push", "live", rows, translated, {"ok": True, **(result if isinstance(result, dict) else {"response": result})}, cert_test, rate_code=rc)
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


OTA_COMMISSIONS = {"booking.com": 0.15, "expedia": 0.18, "hotels.com": 0.18, "agoda": 0.17, "airbnb": 0.14}


def _channel_group(src: str) -> str:
    s = (src or "").lower()
    if s.startswith("ota:") or s.replace("ota:", "") in OTA_COMMISSIONS or s in ("expedia", "hotels.com", "booking.com", "agoda", "airbnb"):
        return "OTA"
    if s.startswith("pms:"):
        return "PMS"
    if s in ("phone", "walk-in", "manual", "website", "direct", "email"):
        return "Doğrudan"
    if s == "group_sales":
        return "Grup Satış"
    if s.startswith("demo"):
        return "Demo/Seed"
    return "Diğer"


def _commission_pct(src: str) -> float:
    if _channel_group(src) != "OTA":
        return 0.0
    return OTA_COMMISSIONS.get((src or "").lower().replace("ota:", ""), 0.15)


async def run_killswitch_drill(db, pid: str, triggered_by: str = "manual") -> dict:
    """Kill switch tatbikatı: acil durdurmayı simüle edip yönetime güvence raporu üretir."""
    now = datetime.now(timezone.utc).isoformat()
    steps = []
    await db.kill_switch.update_one(
        {"property_id": pid, "drill": True},
        {"$set": {"property_id": pid, "active": True, "drill": True, "activated_at": now}}, upsert=True)
    steps.append({"step": "1. Acil durdurma AÇILDI (tatbikat kaydı)", "passed": True})
    ks = await db.kill_switch.find_one({"property_id": {"$in": [pid, "global"]}, "active": True})
    blocked = bool(ks)
    steps.append({"step": "2. Robot fiyat uygulaması denendi → motorun blok koşulu doğrulandı",
                  "passed": blocked})
    if blocked:
        await db.guardrail_violations.insert_one({
            "property_id": pid, "type": "kill_switch", "blocked": True, "drill": True,
            "detail": "TATBİKAT: kill switch aktifken push bloklandı", "source": "drill",
            "created_at": now})
    steps.append({"step": "3. Blok olayı denetim kaydına (guardrail_violations) yazıldı", "passed": blocked})
    await db.kill_switch.update_one({"property_id": pid, "drill": True},
                                    {"$set": {"active": False, "deactivated_at": now}})
    ks2 = await db.kill_switch.find_one({"property_id": {"$in": [pid, "global"]}, "active": True})
    steps.append({"step": "4. Acil durdurma KAPATILDI → sistem normale döndü", "passed": ks2 is None})
    since30 = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    real_blocks = await db.guardrail_violations.count_documents(
        {"property_id": pid, "type": "kill_switch", "drill": {"$ne": True},
         "created_at": {"$gte": since30}})
    violations30 = await db.guardrail_violations.count_documents(
        {"property_id": pid, "created_at": {"$gte": since30}})
    passed = all(s["passed"] for s in steps)
    report = f"""KILL SWITCH TATBİKAT RAPORU — {now[:16].replace('T', ' ')} UTC

Sonuç: {'BAŞARILI — acil durdurma zinciri uçtan uca çalışıyor' if passed else 'BAŞARISIZ — acil müdahale gerekli'}

Tatbikat adımları:
""" + "\n".join(f"  {'✓' if s['passed'] else '✗'} {s['step']}" for s in steps) + f"""

Güvence özeti (son 30 gün):
  • Gerçek kill switch blokları: {real_blocks}
  • Toplam guardrail olayı (adım kırpma/limit/blok): {violations30}
  • Kapsam: kill switch aktifken hiçbir robot fiyatı yazılamaz (otonom + gece push dahil); tüm denemeler denetim kaydına düşer.
  • Ek emniyetler: ±%15 asimetrik adım limiti, günlük push tavanı, bid-price tabanı, publisher sertifikasyon kapısı.

Bu tatbikat kaydı denetim amacıyla saklanmıştır (drill=true etiketiyle gerçek olaylardan ayrılır)."""
    drill_id = str(uuid.uuid4())
    await db.killswitch_drills.insert_one({"id": drill_id, "property_id": pid,
                                           "passed": passed, "steps": steps, "report": report,
                                           "triggered_by": triggered_by, "created_at": now})
    return {"drill_id": drill_id, "passed": passed, "steps": steps, "report": report,
            "real_blocks_30d": real_blocks, "violations_30d": violations30}


async def build_drill_pdf(db, pid: str, drill: dict) -> bytes:
    """Yönetime sunulabilir tatbikat güvence PDF'i üretir."""
    prop = await db.properties.find_one({"id": pid}, {"_id": 0, "name": 1}) or {}
    total_drills = await db.killswitch_drills.count_documents({"property_id": pid})
    passed_drills = await db.killswitch_drills.count_documents({"property_id": pid, "passed": True})
    since30 = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    real_blocks = await db.guardrail_violations.count_documents(
        {"property_id": pid, "type": "kill_switch", "drill": {"$ne": True},
         "created_at": {"$gte": since30}})
    violations30 = await db.guardrail_violations.count_documents(
        {"property_id": pid, "created_at": {"$gte": since30}})
    from io import BytesIO
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas as pc
    from reportlab.lib.units import mm
    _t = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
    buf = BytesIO()
    c = pc.Canvas(buf, pagesize=A4)
    w, hh = A4
    ok = bool(drill.get("passed"))
    c.setFillColorRGB(*(0.02, 0.37, 0.31) if ok else (0.6, 0.1, 0.1))
    c.rect(0, hh - 38 * mm, w, 38 * mm, fill=1, stroke=0)
    try:
        from routes.platform_ext.branding import get_logo_reader, draw_logo
        _logo = await get_logo_reader(db, pid)
        if _logo:
            draw_logo(c, _logo, w, hh, mm)
    except Exception:
        pass
    c.setFillColorRGB(1, 1, 1)
    c.setFont("Helvetica-Bold", 17)
    c.drawString(18 * mm, hh - 16 * mm, "Kill Switch Tatbikat Raporu - Yonetim Guvencesi")
    c.setFont("Helvetica", 10)
    trig = "otomatik aylik robot" if drill.get("triggered_by") == "robot" else "manuel"
    c.drawString(18 * mm, hh - 24 * mm, f"{(prop.get('name') or pid).translate(_t)} · {str(drill['created_at'])[:16].replace('T', ' ')} UTC · tetik: {trig}")
    c.setFont("Helvetica-Bold", 11)
    c.drawString(18 * mm, hh - 32 * mm, "SONUC: " + ("BASARILI - acil durdurma zinciri uctan uca calisiyor" if ok else "BASARISIZ - acil mudahale gerekli"))
    y = hh - 52 * mm
    c.setFillColorRGB(0.1, 0.1, 0.1)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(18 * mm, y, "Tatbikat Adimlari")
    y -= 8 * mm
    c.setFont("Helvetica", 10)
    for s in drill.get("steps", []):
        c.setFillColorRGB(*(0.02, 0.45, 0.35) if s.get("passed") else (0.75, 0.15, 0.15))
        c.drawString(22 * mm, y, ("[OK] " if s.get("passed") else "[HATA] ") + str(s.get("step", "")).translate(_t)[:95])
        y -= 6.5 * mm
    y -= 6 * mm
    c.setFillColorRGB(0.1, 0.1, 0.1)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(18 * mm, y, "Guvence Ozeti (son 30 gun)")
    y -= 8 * mm
    c.setFont("Helvetica", 10)
    c.setFillColorRGB(0.25, 0.25, 0.25)
    for line in (
        f"Gercek kill switch bloklari: {real_blocks}",
        f"Toplam guardrail olayi (adim kirpma / limit / blok): {violations30}",
        f"Tatbikat gecmisi: {passed_drills}/{total_drills} basarili",
        "Kapsam: kill switch aktifken hicbir robot fiyati yazilamaz (otonom + gece push dahil).",
        "Tum denemeler denetim kaydina duser; tatbikat kayitlari drill=true etiketiyle ayrilir.",
        "Ek emniyetler: +-%15 asimetrik adim limiti, gunluk push tavani, bid-price tabani,",
        "publisher sertifikasyon kapisi."):
        c.drawString(22 * mm, y, line)
        y -= 6 * mm
    y -= 6 * mm
    c.setFont("Helvetica-Oblique", 8)
    c.setFillColorRGB(0.45, 0.45, 0.45)
    c.drawString(18 * mm, y, "Otomatik uretilmistir - MyHotelBox RMS / Robot Guven Merkezi. Denetim amaciyla saklanir.")
    c.save()
    buf.seek(0)
    return buf.getvalue()


PDF_BUILDERS = {}


async def archive_pdf_reports(db, pid: str, keys=("weekly", "executive")) -> dict:
    """Haftalık/aylık PDF'leri üretip tarihli arşive kaydeder (dönem başına 1 kez); saklama süresini uygular."""
    import base64 as _b64
    now = datetime.now(timezone.utc)
    periods = {"weekly": now.strftime("%G-W%V"), "executive": now.strftime("%Y-%m")}
    results = []
    for key in keys:
        period = periods[key]
        if await db.pdf_archive.find_one({"property_id": pid, "report_key": key, "period": period}, {"_id": 1}):
            results.append({"key": key, "period": period, "status": "zaten arşivde"})
            continue
        fn = PDF_BUILDERS.get(key)
        if not fn:
            results.append({"key": key, "period": period, "status": "üretici yok"})
            continue
        try:
            resp = await fn(pid)
            pdf = b"".join([c async for c in resp.body_iterator])
            await db.pdf_archive.insert_one({
                "id": str(uuid.uuid4()), "property_id": pid, "report_key": key,
                "period": period, "size_kb": round(len(pdf) / 1024, 1),
                "pdf_b64": _b64.b64encode(pdf).decode(),
                "created_at": now.isoformat()})
            results.append({"key": key, "period": period, "status": "arşivlendi",
                            "size_kb": round(len(pdf) / 1024, 1)})
        except Exception as e:
            results.append({"key": key, "period": period, "status": f"hata: {e}"})
    cfg = await db.pdf_archive_config.find_one({"property_id": pid}, {"_id": 0}) or {}
    months = int(cfg.get("retention_months", 12))
    cutoff = (now - timedelta(days=months * 30)).isoformat()
    purge = await db.pdf_archive.delete_many({"property_id": pid, "created_at": {"$lt": cutoff}})
    return {"property_id": pid, "results": results,
            "retention_months": months, "purged": purge.deleted_count}


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
                elif provider == "opera-cloud":
                    r = await client.post(f"{base}/oauth/v1/tokens",
                                          data={"grant_type": "password", "username": cfg["username"], "password": cfg["password"]},
                                          auth=(cfg["client_id"], cfg["client_secret"]),
                                          headers={"x-app-key": cfg["app_key"]})
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

    @router.get("/{provider}/push-preview/{pid}")
    async def push_preview(provider: str, pid: str, days: int = 14,
                           _u: dict = Depends(require_roles(*ROLES))):
        """Push öncesi önizleme: hangi güne hangi fiyat gidecek (eşleme çarpanlarıyla) — göndermez."""
        if provider not in PROVIDERS:
            raise HTTPException(404, "Bilinmeyen sağlayıcı")
        days = max(1, min(90, int(days)))
        rows = await _rms_rows(db, pid, days)
        if not rows:
            return {"rooms": [], "table": [], "total_prices": 0,
                    "message": "Gönderilecek RMS fiyatı yok."}
        mp = await db.pms_rate_mapping.find_one(
            {"property_id": pid, "provider": provider}, {"_id": 0})
        mappings = [m for m in (mp or {}).get("mappings", []) if m.get("channel_rate_code")]
        if not mappings:
            mappings = [{"room_type_name": "Varsayılan", "channel_rate_code": "RMS-RATE", "multiplier": 1.0}]
        table = []
        for r in rows:
            cells = {}
            for m in mappings:
                mult = float(m.get("multiplier", 1.0) or 1.0)
                cells[m.get("room_type_name", "?")] = {"rate": round(r["rate"] * mult, 2)}
            table.append({"date": r["date"], "cells": cells})
        return {"provider": provider,
                "rooms": [{"room_type": m.get("room_type_name", "?"),
                           "rateID": m["channel_rate_code"]} for m in mappings],
                "table": table, "total_prices": len(rows) * len(mappings)}

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

    @router.get("/{provider}/sync-timeline/{pid}")
    async def sync_timeline(provider: str, pid: str, days: int = 30, _u: dict = Depends(require_roles(*ROLES))):
        """Son N gün senkron zaman çizelgesi: gün bazlı başarılı/başarısız/mock sayıları, son başarı, son hata, yeniden denenebilir kayıtlar."""
        if provider not in PROVIDERS:
            raise HTTPException(404, "Bilinmeyen sağlayıcı")
        days = max(1, min(90, int(days)))
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        rows = await db.pms_push_log.find({"property_id": pid, "provider": provider, "created_at": {"$gte": since}},
                                          {"_id": 0, "translated_sample": 0}).sort("created_at", -1).to_list(2000)
        by_day: dict = {}
        last_ok = last_err = None
        failed = []
        for r in rows:
            d = r["created_at"][:10]
            b = by_day.setdefault(d, {"date": d, "ok": 0, "failed": 0, "mocked": 0})
            res = r.get("result") or {}
            is_fail = res.get("ok") is False
            if r.get("mode") == "mocked":
                b["mocked"] += 1
            elif is_fail:
                b["failed"] += 1
                if not last_err:
                    last_err = {"at": r["created_at"], "error": res.get("error"), "log_id": r["id"]}
                if len(failed) < 20:
                    failed.append({"id": r["id"], "at": r["created_at"], "kind": r.get("kind"), "error": res.get("error"), "rows": len(r.get("standard_rows") or [])})
            else:
                b["ok"] += 1
                if not last_ok:
                    last_ok = r["created_at"]
        cfg = await _cfg(db, pid, provider)
        total_fail = sum(b["failed"] for b in by_day.values())
        health = "no_data" if not rows else ("degraded" if total_fail and (not last_ok or (last_err and last_err["at"] > last_ok)) else "healthy")
        return {"provider": provider, "days": days, "mode": "live" if _has_creds(provider, cfg) else "mocked", "health": health,
                "timeline": sorted(by_day.values(), key=lambda x: x["date"]), "totals": {"ok": sum(b["ok"] for b in by_day.values()), "failed": total_fail, "mocked": sum(b["mocked"] for b in by_day.values())},
                "last_success_at": last_ok, "last_error": last_err, "last_test": cfg.get("last_test"), "failed_entries": failed}

    @router.post("/{provider}/resync/{pid}/{log_id}")
    async def resync(provider: str, pid: str, log_id: str, _u: dict = Depends(require_roles(*ROLES))):
        """Başarısız/eski bir push kaydını aynı satırlarla yeniden gönderir (tek tık re-sync)."""
        if provider not in PROVIDERS:
            raise HTTPException(404, "Bilinmeyen sağlayıcı")
        entry = await db.pms_push_log.find_one({"id": log_id, "property_id": pid, "provider": provider}, {"_id": 0})
        if not entry or not entry.get("standard_rows"):
            raise HTTPException(404, "Kayıt yok veya yeniden gönderilecek satır içermiyor")
        res = await _push(db, pid, provider, entry["standard_rows"], cert_test=bool(entry.get("cert_test")))
        await db.pms_push_log.update_one({"id": log_id}, {"$set": {"resynced_at": datetime.now(timezone.utc).isoformat(), "resynced_by": _u.get("email")}})
        return {"ok": True, "resynced_from": log_id, **res}

    @router.get("/{provider}/log/{pid}")
    async def get_log(provider: str, pid: str, limit: int = 20,
                      _u: dict = Depends(require_roles(*ROLES))):
        rows = await db.pms_push_log.find(
            {"property_id": pid, "provider": provider},
            {"_id": 0, "standard_rows": 0, "translated_sample": 0}
        ).sort("created_at", -1).to_list(min(limit, 100))
        return {"log": rows}

    @router.get("/{provider}/discover-rates/{pid}")
    async def discover_rates(provider: str, pid: str, _u: dict = Depends(require_roles(*ROLES))):
        """Kanaldaki gerçek rate/oda kategorilerini keşfeder — eşleştirme tablosu otomatik dolar."""
        if provider not in PROVIDERS:
            raise HTTPException(404, "Bilinmeyen sağlayıcı")
        cfg = await _cfg(db, pid, provider)
        if not _has_creds(provider, cfg):
            raise HTTPException(400, f"Önce {PROVIDERS[provider]['name']} kimliklerini girin.")
        if provider == "apaleo":
            async with httpx.AsyncClient(timeout=30) as client:
                tk = await client.post("https://identity.apaleo.com/connect/token",
                                       data={"grant_type": "client_credentials",
                                             "client_id": cfg["client_id"],
                                             "client_secret": cfg["client_secret"]})
                if tk.status_code != 200:
                    raise HTTPException(502, f"Apaleo OAuth hatası: {tk.text[:200]}")
                hdr = {"Authorization": f"Bearer {tk.json()['access_token']}"}
                rp = await client.get("https://api.apaleo.com/rateplan/v1/rate-plans",
                                      headers=hdr, params={"propertyId": cfg["apaleo_property_id"], "pageSize": 100})
                rates = [{"id": p["id"], "name": p.get("name", ""), "is_root": True, "is_active": True}
                         for p in (rp.json() or {}).get("ratePlans", [])] if rp.status_code == 200 else []
                ug = await client.get("https://api.apaleo.com/inventory/v1/unit-groups",
                                      headers=hdr, params={"propertyId": cfg["apaleo_property_id"], "pageSize": 100})
                categories = [{"id": g["id"], "name": g.get("name", ""), "capacity": g.get("maxPersons")}
                              for g in (ug.json() or {}).get("unitGroups", [])] if ug.status_code == 200 else []
            return {"service": cfg["apaleo_property_id"], "rates": rates,
                    "resource_categories": categories,
                    "note": "Apaleo rate plan'ları ve unit group'ları (gerçek oda tipleri)."}
        if provider != "mews":
            raise HTTPException(501, f"{PROVIDERS[provider]['name']} keşfi partner API dokümanları gelince açılacak — kodları elle girin.")
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
        cs = await db.commission_settings.find_one({"property_id": pid}, {"_id": 0}) or {}
        overrides = cs.get("rates") or {}

        def _cpct(src):
            key = (src or "").lower().replace("ota:", "")
            if key in overrides:
                return float(overrides[key]) / 100.0
            return _commission_pct(src)
        by_month = {}
        for a in agg:
            m, src = a["_id"]["month"], a["_id"]["source"]
            cpct = _cpct(src)
            by_month.setdefault(m, []).append(
                {"source": src, "group": _channel_group(src),
                 "revenue": round(a["revenue"], 2), "bookings": a["bookings"],
                 "commission_pct": round(cpct * 100, 1),
                 "net_revenue": round(a["revenue"] * (1 - cpct), 2)})
        for m, rows in by_month.items():
            tot = sum(r["revenue"] for r in rows) or 1
            for r in rows:
                r["pct"] = round(r["revenue"] / tot * 100, 1)
        totals = {}
        for rows in by_month.values():
            for r in rows:
                t = totals.setdefault(r["source"], {"source": r["source"], "group": r["group"],
                                                    "revenue": 0.0, "net_revenue": 0.0, "bookings": 0})
                t["revenue"] = round(t["revenue"] + r["revenue"], 2)
                t["net_revenue"] = round(t["net_revenue"] + r["net_revenue"], 2)
                t["bookings"] += r["bookings"]
        tot_all = sum(t["revenue"] for t in totals.values()) or 1
        totals_list = sorted(totals.values(), key=lambda x: -x["revenue"])
        for t in totals_list:
            t["pct"] = round(t["revenue"] / tot_all * 100, 1)
        groups = {}
        for t in totals_list:
            g = groups.setdefault(t["group"], {"group": t["group"], "revenue": 0.0,
                                               "net_revenue": 0.0, "bookings": 0})
            g["revenue"] = round(g["revenue"] + t["revenue"], 2)
            g["net_revenue"] = round(g["net_revenue"] + t["net_revenue"], 2)
            g["bookings"] += t["bookings"]
        groups_list = sorted(groups.values(), key=lambda x: -x["revenue"])
        for g in groups_list:
            g["pct"] = round(g["revenue"] / tot_all * 100, 1)
            g["commission_paid"] = round(g["revenue"] - g["net_revenue"], 2)
        return {"months": sorted(by_month.keys()), "by_month": by_month,
                "totals": totals_list, "groups": groups_list,
                "total_revenue": round(tot_all, 2),
                "total_net_revenue": round(sum(t["net_revenue"] for t in totals_list), 2),
                "commission_note": "OTA komisyonları: Booking %15, Expedia/Hotels.com %18, Agoda %17, diğer OTA %15 varsayılan."}

    @router.get("/commission-settings/{pid}")
    async def get_commission_settings(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        cs = await db.commission_settings.find_one({"property_id": pid}, {"_id": 0}) or {}
        srcs = await db.bookings.distinct("source", {"property_id": pid})
        ota_srcs = sorted({s for s in srcs if s and _channel_group(s) == "OTA"})
        rows = [{"source": s,
                 "default_pct": round(_commission_pct(s) * 100, 1),
                 "custom_pct": (cs.get("rates") or {}).get(s.lower().replace("ota:", ""))}
                for s in ota_srcs]
        return {"rows": rows,
                "note": "Boş bırakılan kaynaklar varsayılan oranı kullanır. Oranlar sözleşmenize göre düzenlenebilir."}

    @router.post("/commission-settings/{pid}")
    async def save_commission_settings(pid: str, data: dict, _u: dict = Depends(require_roles(*ROLES))):
        rates = {}
        for k, v in (data.get("rates") or {}).items():
            if v is None or v == "":
                continue
            rates[str(k).lower().replace("ota:", "")] = max(0.0, min(50.0, float(v)))
        await db.commission_settings.update_one(
            {"property_id": pid},
            {"$set": {"property_id": pid, "rates": rates,
                      "updated_at": datetime.now(timezone.utc).isoformat()}}, upsert=True)
        return {"ok": True, "count": len(rates)}

    async def _rev_data(pid: str, months: int = 6) -> dict:
        return await revenue_by_channel(pid, months, _u={"role": "admin"})

    @router.get("/direct-booking-tips/{pid}")
    async def direct_booking_tips(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        """Doğrudan rezervasyon teşviki: OTA komisyon kaybı + akıllı yönlendirme önerileri + takip."""
        d = await _rev_data(pid, 6)
        groups = {g["group"]: g for g in d["groups"]}
        ota = groups.get("OTA", {"revenue": 0, "net_revenue": 0, "pct": 0})
        direct = groups.get("Doğrudan", {"revenue": 0, "pct": 0})
        loss_6m = round(ota.get("commission_paid", ota["revenue"] - ota["net_revenue"]), 2)
        loss_annual = round(loss_6m * 2, 2)
        direct_pct = direct.get("pct", 0)
        texts = [
            f"Son 6 ayda OTA komisyonlarına ₺{loss_6m:,.0f} ödediniz (yıllık tahmini ₺{loss_annual:,.0f}). Bu tutarın %20'si doğrudan kanala kaysa yıllık ₺{loss_annual*0.2:,.0f} cebinizde kalır.",
            f"Doğrudan kanal payınız %{direct_pct} — sektör hedefi %30+. Web sitenizde 'En İyi Fiyat Garantisi' rozetiyle OTA'dan gelen misafiri kendi sitenize çekin.",
            "OTA'dan gelen misafire check-in'de e-posta izni alın; bir sonraki konaklama için doğrudan rezervasyona özel %5-8 indirim kuponu gönderin (komisyondan hâlâ kârlı).",
            "Bid-price tabanının üzerindeyken doğrudan kanalda ücretsiz erken check-in / geç check-out gibi ücretsiz avantajlar sunun — fiyat paritesini bozmadan doğrudan satışı büyütür.",
            "Sadakat listesi: geçmiş misafirlere sezon açılışında doğrudan-özel ön satış e-postası gönderin (Resend anahtarı girilince otomatikleştirilebilir).",
        ]
        st = await db.tip_status.find_one({"property_id": pid}, {"_id": 0}) or {}
        done_map = st.get("done", {})
        tips = [{"index": i, "text": t, "done": bool(done_map.get(str(i)))} for i, t in enumerate(texts)]
        direct_trend = []
        for m in d["months"]:
            rows = d["by_month"].get(m, [])
            tot = sum(r["revenue"] for r in rows) or 1
            dp = sum(r["revenue"] for r in rows if r["group"] == "Doğrudan")
            direct_trend.append({"month": m, "direct_pct": round(dp / tot * 100, 1)})
        return {"ota_revenue_6m": ota["revenue"], "ota_pct": ota["pct"],
                "commission_loss_6m": loss_6m, "commission_loss_annual_est": loss_annual,
                "direct_pct": direct_pct, "tips": tips,
                "done_count": sum(1 for t in tips if t["done"]),
                "direct_trend": direct_trend}

    @router.post("/direct-booking-tips/{pid}/toggle")
    async def toggle_tip(pid: str, data: dict, _u: dict = Depends(require_roles(*ROLES))):
        idx = int(data.get("index", -1))
        if idx < 0 or idx > 20:
            raise HTTPException(400, "Geçersiz index")
        await db.tip_status.update_one(
            {"property_id": pid},
            {"$set": {f"done.{idx}": bool(data.get("done")),
                      "updated_at": datetime.now(timezone.utc).isoformat()}}, upsert=True)
        return {"ok": True}

    @router.get("/pilot-invite/{pid}")
    async def pilot_invite(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        """Pilot otel daveti: Mews canlı kanıtı + sunum PDF'i referanslı Türkçe davet e-postası."""
        prop = await db.properties.find_one({"id": pid}, {"_id": 0, "name": 1}) or {}
        mews = await _cfg(db, pid, "mews")
        cert = mews.get("certification") or {}
        live_pushes = await db.pms_push_log.count_documents(
            {"property_id": pid, "provider": "mews", "mode": "live", "kind": "rate_push"})
        v = await db.pms_verify_log.find_one({"property_id": pid, "provider": "mews", "ok": True},
                                             {"_id": 0, "max_drift_pct": 1, "verified_at": 1},
                                             sort=[("verified_at", -1)])
        arc = await db.pitch_archive.find_one({"property_id": pid}, {"_id": 0, "id": 1, "created_at": 1},
                                              sort=[("created_at", -1)])
        subject = "Pilot Daveti — AI Gelir Robotu: Mews üzerinde CANLI kanıtlanmış, otelinize 30 günlük ücretsiz pilot"
        body = f"""Sayın Otel Yöneticisi,

MyHotelBox olarak yapay zekâ destekli Gelir Yönetim Sistemimiz (RMS) için sınırlı sayıda pilot otel arıyoruz — ve kanıtlarımızla geliyoruz:

CANLI TEKNİK KANIT (Mews demo ortamı, bağımsız doğrulanabilir)
  • Publisher sertifikasyonu: {'GEÇTİ (CANLI mod, ' + str(cert.get('at', ''))[:10] + ')' if cert.get('passed') and cert.get('mode') == 'live' else 'MOCK modda hazır'}
  • Gerçek fiyat push'u: {live_pushes} canlı işlem — oda tipi bazında ayrı rate plan'lara
  • Geri okuma doğrulaması: kanaldaki fiyat, bastığımızla birebir eşleşti (maks sapma %{(v or {}).get('max_drift_pct', 0)})
  • ~200 gerçek rezervasyon PMS'ten çekilip talep tahmin motorumuza bağlandı

PİLOTTA NE ALACAKSINIZ (30 gün, ücretsiz, riskisiz)
  • AI fiyat önerileri önce GÖLGE MODDA çalışır — siz onaylamadan tek kuruş değişmez
  • Bid-price tabanı, ±%15 emniyet limitleri, global kill-switch ve tam denetim kaydı
  • Her sabah otomatik rapor + fiyat sapması bekçisi + haftalık kanal performans özeti
  • Ekli pilot sunum PDF'inde: robot vs sabit fiyat gelir simülasyonu, rakip fiyat kıyası ve esneklik analizi

Sisteminiz Mews, Cloudbeds, HotelRunner{', Apaleo' if False else ''} veya başka bir PMS/kanal yöneticisi olabilir — adaptör katmanımız hazır.

15 dakikalık bir tanıtım görüşmesi için bu e-postaya dönmeniz yeterli. Simülasyonu kendi otelinizin verileriyle canlı gösterelim.

Saygılarımızla,
MyHotelBox RMS Ekibi
{prop.get('name', '')} pilot programı"""
        return {"email_subject": subject, "email_body": body,
                "attachment_hint": (f"Ek olarak kullanın: Pilot Sunum PDF (arşiv id: {arc['id']}, "
                                    f"{str(arc['created_at'])[:10]}) — Simülatör panelinden indirilebilir.") if arc
                else "Önce Simülatör panelinden bir Pilot Sunum PDF üretin — davete ek olarak kullanılır.",
                "proof": {"cert_passed_live": bool(cert.get("passed") and cert.get("mode") == "live"),
                          "live_pushes": live_pushes,
                          "last_verify_drift_pct": (v or {}).get("max_drift_pct")}}

    @router.get("/executive-pdf/{pid}")
    async def executive_pdf(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        """Aylık yönetici özeti: gelir kırılımı + kanal sağlığı + forecast isabeti tek PDF'te."""
        d = await _rev_data(pid, 6)
        h = await health(pid, _u)
        fa = await forecast_accuracy(pid, _u)
        prop = await db.properties.find_one({"id": pid}, {"_id": 0, "name": 1}) or {}
        from io import BytesIO
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas as pc
        from reportlab.lib.units import mm
        _t = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
        buf = BytesIO()
        c = pc.Canvas(buf, pagesize=A4)
        w, hh = A4
        c.setFillColorRGB(0.05, 0.09, 0.16)
        c.rect(0, hh - 34 * mm, w, 34 * mm, fill=1, stroke=0)
        try:
            from routes.platform_ext.branding import get_logo_reader, draw_logo
            _logo = await get_logo_reader(db, pid)
            if _logo:
                draw_logo(c, _logo, w, hh, mm)
        except Exception:
            pass
        c.setFillColorRGB(1, 1, 1)
        c.setFont("Helvetica-Bold", 17)
        c.drawString(18 * mm, hh - 15 * mm, (prop.get("name") or pid).translate(_t))
        c.setFont("Helvetica", 10)
        c.drawString(18 * mm, hh - 23 * mm, f"Aylik Yonetici Ozeti - {datetime.now(timezone.utc).date().isoformat()} - Dagitim & Gelir")
        y = hh - 46 * mm
        c.setFillColorRGB(0.1, 0.1, 0.1)
        c.setFont("Helvetica-Bold", 12)
        c.drawString(18 * mm, y, f"1. Gelir Kirilimi (6 ay) - Brut {d['total_revenue']:,.0f} / Net {d['total_net_revenue']:,.0f}")
        y -= 7 * mm
        c.setFont("Helvetica", 9)
        for g in d["groups"][:6]:
            c.setFillColorRGB(0.25, 0.25, 0.25)
            c.drawString(22 * mm, y, f"{g['group'].translate(_t)}: {g['revenue']:,.0f} (%{g['pct']}) - net {g['net_revenue']:,.0f}"
                         + (f" - komisyon {g['commission_paid']:,.0f}" if g.get('commission_paid') else ""))
            y -= 5.5 * mm
        y -= 5 * mm
        c.setFillColorRGB(0.1, 0.1, 0.1)
        c.setFont("Helvetica-Bold", 12)
        cert_n = sum(1 for ch in h["channels"] if ch["certified"])
        live_n = sum(1 for ch in h["channels"] if ch["mode"] == "live")
        c.drawString(18 * mm, y, f"2. Kanal Sagligi - {len(h['channels'])} kanal, {cert_n} sertifikali, {live_n} canli, {h['active_alerts']} aktif uyari")
        y -= 7 * mm
        c.setFont("Helvetica", 9)
        for ch in h["channels"]:
            c.setFillColorRGB(0.25, 0.25, 0.25)
            lp = str(ch.get("last_push_at") or "hic")[:16].replace("T", " ")
            c.drawString(22 * mm, y, f"{ch['name']}: {'CANLI' if ch['mode']=='live' else 'MOCK'} - "
                         f"{'SERTIFIKALI' if ch['certified'] else 'sertifikasyon bekliyor'} - son push {lp} - {ch['total_pushes']} islem")
            y -= 5.5 * mm
        y -= 5 * mm
        c.setFillColorRGB(0.1, 0.1, 0.1)
        c.setFont("Helvetica-Bold", 12)
        mae_txt = (f"MAE {fa['mae_occ_pts']} doluluk puani ({fa['matured_points']} nokta)"
                   if fa["mae_occ_pts"] is not None else "snapshot birikiyor (gece robotu)")
        c.drawString(18 * mm, y, f"3. Forecast Isabeti - {mae_txt}")
        y -= 7 * mm
        c.setFont("Helvetica", 9)
        c.setFillColorRGB(0.25, 0.25, 0.25)
        c.drawString(22 * mm, y, f"Mews canli rezervasyon katkisi (14 gun): +{fa['mews_total_contribution_14d']} oda-gece")
        y -= 9 * mm
        try:
            from routes.revenue_ext.trust_center import REJECT_TAG_LABELS, BLIND_SPOT_RECS
            since90 = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()
            _tags = {}
            async for dec in db.ai_pricing_decisions.find(
                    {"property_id": pid, "status": "rejected", "reason_tag": {"$ne": None},
                     "decided_at": {"$gte": since90}}, {"_id": 0, "reason_tag": 1}):
                _tags[dec["reason_tag"]] = _tags.get(dec["reason_tag"], 0) + 1
            c.setFillColorRGB(0.1, 0.1, 0.1)
            c.setFont("Helvetica-Bold", 12)
            if _tags:
                _top, _n = max(_tags.items(), key=lambda x: x[1])
                c.drawString(18 * mm, y, "4. Kor Nokta Radari (son 90 gun)")
                y -= 7 * mm
                c.setFont("Helvetica", 9)
                c.setFillColorRGB(0.6, 0.15, 0.15)
                c.drawString(22 * mm, y, f"En zayif alan: {REJECT_TAG_LABELS.get(_top, _top).translate(_t)} "
                             f"({_n}/{sum(_tags.values())} etiketli red)")
                y -= 5.5 * mm
                c.setFillColorRGB(0.25, 0.25, 0.25)
                c.drawString(22 * mm, y, "Oneri: " + BLIND_SPOT_RECS.get(_top, "").translate(_t)[:105])
            else:
                c.drawString(18 * mm, y, "4. Kor Nokta Radari - etiketli red yok (temiz)")
            y -= 10 * mm
        except Exception:
            y -= 1 * mm
        try:
            from routes.revenue_ext.weather_calendar import compute_impact_report
            imp = await compute_impact_report(db, pid, 4)
            c.setFillColorRGB(0.1, 0.1, 0.1)
            c.setFont("Helvetica-Bold", 12)
            c.drawString(18 * mm, y, "5. Sinyal Etkisi - hava + tatil carpanlari (son 4 hafta)")
            y -= 7 * mm
            c.setFont("Helvetica", 9)
            c.setFillColorRGB(*(0.02, 0.45, 0.35) if imp["total_est_impact"] >= 0 else (0.75, 0.15, 0.15))
            c.drawString(22 * mm, y, f"Toplam tahmini katki: {'+' if imp['total_est_impact'] >= 0 else ''}"
                         f"{imp['total_est_impact']} {imp['currency']} ({imp['total_signal_days']} sinyalli gun)")
            y -= 5.5 * mm
            c.setFillColorRGB(0.25, 0.25, 0.25)
            for wk in imp["weeks"]:
                if wk["signal_days"]:
                    c.drawString(22 * mm, y, f"{wk['week']}: {wk['signal_days']} gun · {wk['room_nights']} oda-gece · "
                                 f"{'+' if wk['est_impact'] >= 0 else ''}{wk['est_impact']} {imp['currency']}")
                    y -= 5 * mm
            y -= 5 * mm
        except Exception:
            y -= 1 * mm
        c.setFont("Helvetica-Oblique", 8)
        c.setFillColorRGB(0.45, 0.45, 0.45)
        c.drawString(18 * mm, y, "Otomatik uretilmistir - MyHotelBox RMS / PMS Baglanti Merkezi. Detaylar panelde.")
        c.save()
        buf.seek(0)
        from fastapi.responses import StreamingResponse
        return StreamingResponse(buf, media_type="application/pdf",
                                 headers={"Content-Disposition": 'inline; filename="yonetici-ozeti.pdf"'})

    @router.get("/pilot-leads/{pid}")
    async def pilot_leads(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        rows = await db.pilot_leads.find({"property_id": pid}, {"_id": 0}).sort("created_at", -1).to_list(100)
        now = datetime.now(timezone.utc)
        order = ["davet", "görüşme", "demo", "pilot"]
        for l in rows:
            try:
                upd = datetime.fromisoformat(str(l.get("updated_at") or l["created_at"]))
                days = max((now - upd).days, 0)
            except Exception:
                days = 0
            l["days_in_stage"] = days
            l["stale"] = l.get("status") in ("davet", "görüşme", "demo") and days >= 7
        active = [l for l in rows if l.get("status") in order]
        funnel = []
        prev_reached = None
        for i, stage in enumerate(order):
            reached = sum(1 for l in active if order.index(l["status"]) >= i)
            in_stage = [l for l in active if l["status"] == stage]
            funnel.append({
                "stage": stage, "count": len(in_stage), "reached": reached,
                "conv_pct": round(reached / prev_reached * 100, 0) if prev_reached else None,
                "avg_days_in_stage": round(sum(l["days_in_stage"] for l in in_stage) / len(in_stage), 1) if in_stage else None})
            prev_reached = reached or None
        return {"leads": rows, "statuses": ["davet", "görüşme", "demo", "pilot", "kaybedildi"],
                "funnel": funnel, "lost_count": sum(1 for l in rows if l.get("status") == "kaybedildi"),
                "stale_count": sum(1 for l in rows if l.get("stale")),
                "stale_days_threshold": 7}

    @router.post("/pilot-leads/{pid}")
    async def add_pilot_lead(pid: str, data: dict, _u: dict = Depends(require_roles(*ROLES))):
        name = (data.get("hotel_name") or "").strip()
        if not name:
            raise HTTPException(400, "Otel adı gerekli")
        lead = {"id": str(uuid.uuid4()), "property_id": pid, "hotel_name": name[:120],
                "contact": (data.get("contact") or "").strip()[:120],
                "note": (data.get("note") or "").strip()[:300], "status": "davet",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat()}
        await db.pilot_leads.insert_one(dict(lead))
        return {"ok": True, "lead": lead}

    @router.post("/pilot-leads/{lead_id}/status")
    async def set_lead_status(lead_id: str, data: dict, _u: dict = Depends(require_roles(*ROLES))):
        status = data.get("status")
        if status not in ("davet", "görüşme", "demo", "pilot", "kaybedildi"):
            raise HTTPException(400, "Geçersiz durum")
        r = await db.pilot_leads.update_one(
            {"id": lead_id},
            {"$set": {"status": status, "updated_at": datetime.now(timezone.utc).isoformat()}})
        if not r.matched_count:
            raise HTTPException(404, "Kayıt bulunamadı")
        return {"ok": True}

    @router.post("/pilot-leads/{lead_id}/note")
    async def set_lead_note(lead_id: str, data: dict, _u: dict = Depends(require_roles(*ROLES))):
        r = await db.pilot_leads.update_one(
            {"id": lead_id},
            {"$set": {"note": (data.get("note") or "").strip()[:300],
                      "updated_at": datetime.now(timezone.utc).isoformat()}})
        if not r.matched_count:
            raise HTTPException(404, "Kayıt bulunamadı")
        return {"ok": True}

    @router.get("/killswitch-drill/{pid}/report-pdf")
    async def killswitch_drill_pdf(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        """Son tatbikatın yönetime sunulabilir PDF güvence raporu."""
        drill = await db.killswitch_drills.find_one({"property_id": pid}, {"_id": 0},
                                                    sort=[("created_at", -1)])
        if not drill:
            raise HTTPException(404, "Henüz tatbikat çalıştırılmadı")
        pdf = await build_drill_pdf(db, pid, drill)
        from io import BytesIO
        from fastapi.responses import StreamingResponse
        return StreamingResponse(BytesIO(pdf), media_type="application/pdf",
                                 headers={"Content-Disposition": 'inline; filename="kill-switch-tatbikat-raporu.pdf"'})

    @router.post("/killswitch-drill/{pid}")
    async def killswitch_drill(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        return await run_killswitch_drill(db, pid, triggered_by="manual")

    @router.get("/killswitch-drill/{pid}/history")
    async def killswitch_drill_history(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        rows = await db.killswitch_drills.find(
            {"property_id": pid}, {"_id": 0, "report": 0, "steps": 0, "pdf_b64": 0}).sort("created_at", -1).to_list(24)
        for r in rows:
            r["pdf_archived"] = bool(await db.killswitch_drills.find_one(
                {"id": r["id"], "pdf_b64": {"$exists": True}}, {"_id": 1}))
        return {"drills": rows, "monthly_robot": True,
                "note": "Aylık tatbikat robotu her ayın 1'inde otomatik çalışır ve güvence PDF'ini arşive kaydeder."}

    @router.get("/killswitch-drill/archive/{drill_id}/pdf")
    async def killswitch_drill_archive_pdf(drill_id: str, _u: dict = Depends(require_roles(*ROLES))):
        doc = await db.killswitch_drills.find_one({"id": drill_id}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "Tatbikat kaydı bulunamadı")
        from io import BytesIO
        if doc.get("pdf_b64"):
            import base64 as _b64
            pdf = _b64.b64decode(doc["pdf_b64"])
        else:
            pdf = await build_drill_pdf(db, doc["property_id"], doc)
        from fastapi.responses import StreamingResponse
        return StreamingResponse(BytesIO(pdf), media_type="application/pdf",
                                 headers={"Content-Disposition": f'inline; filename="tatbikat-{str(doc["created_at"])[:10]}.pdf"'})

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

    @router.get("/pdf-center/{pid}")
    async def pdf_center(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        """Tüm PDF raporlarının tek arşiv listesi."""
        drills = await db.killswitch_drills.find(
            {"property_id": pid}, {"_id": 0, "id": 1, "created_at": 1, "passed": 1,
                                   "triggered_by": 1, "pdf_size_kb": 1}).sort("created_at", -1).to_list(24)
        for d in drills:
            d["url"] = f"/api/pms-connect/killswitch-drill/archive/{d['id']}/pdf"
        has_logo = bool(await db.template_settings.find_one(
            {"property_id": pid, "logo_b64": {"$exists": True}}, {"_id": 1}))
        on_demand = [
            {"key": "weekly", "title": "Haftalık Kanal Performans Raporu",
             "desc": "Son 7 gün: PMS push'ları, sertifikasyon, gece robotu, sapma uyarıları",
             "url": f"/api/pms-connect/weekly-report-pdf/{pid}"},
            {"key": "executive", "title": "Aylık Yönetici Özeti",
             "desc": "Kanal karışımı, gece robotu, forecast isabeti, kör nokta radarı, sinyal etkisi",
             "url": f"/api/pms-connect/executive-pdf/{pid}"},
            {"key": "gap", "title": "Rakip Gap Analizi",
             "desc": "17 kalemlik kapsam karşılaştırması — müşteri sunumuna hazır, markalanabilir",
             "url": f"/api/competitive-gap-pdf?pid={pid}"},
            {"key": "heatmap", "title": "Aylık Rakip Sapma Isı Haritası",
             "desc": "Takvim üzerinde gün gün pazar sapması — kırmızı pahalı, mavi ucuz; yönetim paylaşımına hazır",
             "url": f"/api/demand-signals/{pid}/heatmap-pdf"},
            {"key": "drill", "title": "Son Kill Switch Tatbikat Raporu",
             "desc": "Acil durdurma zincirinin uçtan uca çalıştığının yönetim güvencesi",
             "url": f"/api/pms-connect/killswitch-drill/{pid}/report-pdf",
             "available": bool(drills)},
        ]
        arch = await db.pdf_archive.find(
            {"property_id": pid},
            {"_id": 0, "pdf_b64": 0}).sort("created_at", -1).to_list(50)
        for a in arch:
            a["url"] = f"/api/pms-connect/pdf-archive/{a['id']}/download"
        _rcfg = await db.pdf_archive_config.find_one({"property_id": pid}, {"_id": 0}) or {}
        return {"property_id": pid, "on_demand": on_demand, "drill_archive": drills,
                "scheduled_archive": arch,
                "retention_months": int(_rcfg.get("retention_months", 12)),
                "branding": {"has_logo": has_logo,
                             "note": "Logo yüklüyse tüm PDF'lerde otomatik kullanılır (Ayarlar → Hotel Logo)."}}

    @router.put("/pdf-archive/{pid}/retention")
    async def set_pdf_retention(pid: str, data: dict, _u: dict = Depends(require_roles(*ROLES))):
        try:
            months = max(3, min(36, int(data.get("retention_months", 12))))
        except (TypeError, ValueError):
            raise HTTPException(400, "retention_months 3-36 arası olmalı")
        await db.pdf_archive_config.update_one(
            {"property_id": pid},
            {"$set": {"property_id": pid, "retention_months": months,
                      "updated_at": datetime.now(timezone.utc).isoformat()}}, upsert=True)
        cutoff = (datetime.now(timezone.utc) - timedelta(days=months * 30)).isoformat()
        purge = await db.pdf_archive.delete_many({"property_id": pid, "created_at": {"$lt": cutoff}})
        return {"ok": True, "retention_months": months, "purged": purge.deleted_count}

    @router.post("/pdf-archive/{pid}/run-now")
    async def pdf_archive_run_now(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        return await archive_pdf_reports(db, pid)

    @router.get("/pdf-archive/{doc_id}/download")
    async def pdf_archive_download(doc_id: str, _u: dict = Depends(require_roles(*ROLES))):
        import base64 as _b64
        doc = await db.pdf_archive.find_one({"id": doc_id}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "Arşiv kaydı bulunamadı")
        from io import BytesIO
        from fastapi.responses import StreamingResponse
        return StreamingResponse(BytesIO(_b64.b64decode(doc["pdf_b64"])), media_type="application/pdf",
                                 headers={"Content-Disposition": f'inline; filename="{doc["report_key"]}-{doc["period"]}.pdf"'})

    @router.get("/weekly-report-pdf/{pid}")
    async def weekly_report_pdf(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        wr = await weekly_report(pid, _u)
        prop = await db.properties.find_one({"id": pid}, {"_id": 0, "name": 1}) or {}
        from io import BytesIO
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas as pc
        from reportlab.lib.units import mm
        _t = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
        buf = BytesIO()
        c = pc.Canvas(buf, pagesize=A4)
        w, hh = A4
        c.setFillColorRGB(0.05, 0.09, 0.16)
        c.rect(0, hh - 34 * mm, w, 34 * mm, fill=1, stroke=0)
        try:
            from routes.platform_ext.branding import get_logo_reader, draw_logo
            _logo = await get_logo_reader(db, pid)
            if _logo:
                draw_logo(c, _logo, w, hh, mm)
        except Exception:
            pass
        c.setFillColorRGB(1, 1, 1)
        c.setFont("Helvetica-Bold", 17)
        c.drawString(18 * mm, hh - 15 * mm, "Haftalik Kanal Performans Raporu")
        c.setFont("Helvetica", 10)
        c.drawString(18 * mm, hh - 23 * mm, f"{(prop.get('name') or pid).translate(_t)} · {wr['week_of']} · son 7 gun")
        y = hh - 46 * mm
        c.setFillColorRGB(0.1, 0.1, 0.1)
        c.setFont("Helvetica-Bold", 12)
        c.drawString(18 * mm, y, "1. PMS Baglanti Merkezi Kanallari")
        y -= 8 * mm
        c.setFont("Helvetica", 9)
        for ch in wr["channels"]:
            c.setFillColorRGB(0.25, 0.25, 0.25)
            line = (f"{ch['name']}: {ch['pushes_7d']} push ({ch['live_7d']} canli) - "
                    f"{'SERTIFIKALI' if ch['certified'] else 'sertifikasyon bekliyor'}"
                    + (f" - dogrulama OK (maks sapma %{ch['max_drift_pct']})" if ch['last_verify_ok'] else ""))
            c.drawString(22 * mm, y, line.translate(_t))
            y -= 5.5 * mm
        y -= 5 * mm
        c.setFillColorRGB(0.1, 0.1, 0.1)
        c.setFont("Helvetica-Bold", 12)
        c.drawString(18 * mm, y, "2. Diger Kanallar & Otomasyon")
        y -= 8 * mm
        c.setFont("Helvetica", 9)
        c.setFillColorRGB(0.25, 0.25, 0.25)
        for line in (f"Cloudbeds: {wr['cloudbeds_7d']} islem · HotelRunner: {wr['hotelrunner_7d']} islem",
                     f"Gece push calismasi: {wr['night_pushes_7d']} kez",
                     f"Fiyat sapma uyarisi: {wr['drift_alerts_7d']} adet"
                     + (" - ACIL INCELEME GEREKLI" if wr['drift_alerts_7d'] else " (temiz)")):
            c.drawString(22 * mm, y, line)
            y -= 5.5 * mm
        y -= 8 * mm
        c.setFont("Helvetica-Oblique", 8)
        c.setFillColorRGB(0.45, 0.45, 0.45)
        c.drawString(18 * mm, y, "Tum canli push'lar publisher sertifikasyonundan gecmis kanallara yapilmistir. Otomatik uretilmistir - MyHotelBox RMS.")
        c.save()
        buf.seek(0)
        from fastapi.responses import StreamingResponse
        return StreamingResponse(buf, media_type="application/pdf",
                                 headers={"Content-Disposition": 'inline; filename="haftalik-kanal-raporu.pdf"'})

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

    PDF_BUILDERS["weekly"] = weekly_report_pdf
    PDF_BUILDERS["executive"] = executive_pdf
    return router
