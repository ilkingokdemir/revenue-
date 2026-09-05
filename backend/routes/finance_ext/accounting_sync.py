"""
Muhasebe Konektörleri — Xero (ManualJournals) + QuickBooks Online (JournalEntry) + TR e-Fatura (UBL-TR 1.2 taslak).
Günlük iş: accounting_daily_sync (03:30) → dünün gelir/ödeme yevmiyesi → bağlı sağlayıcıya gönder (token yoksa MOCK/outbox).
ENV: XERO_CLIENT_ID/SECRET, QBO_CLIENT_ID/SECRET, PUBLIC_BASE_URL, TOKEN_ENCRYPTION_KEY (ops.), EFATURA_INTEGRATOR_KEY (ops.)
"""
import base64
import logging
import os
import secrets
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional
from urllib.parse import urlencode
from xml.sax.saxutils import escape

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse

logger = logging.getLogger(__name__)

PROV = {
    "xero": {"auth": "https://login.xero.com/identity/connect/authorize", "token": "https://identity.xero.com/connect/token",
             "scope": "openid profile email offline_access accounting.manualjournals accounting.settings", "env": "XERO"},
    "qbo": {"auth": "https://appcenter.intuit.com/connect/oauth2", "token": "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer",
            "scope": "com.intuit.quickbooks.accounting", "env": "QBO"},
}
DEFAULT_MAPPING = {"xero": {"payments": "090", "revenue": "200", "tax": "820", "ar": "610"},
                   "qbo": {"payments": "35", "revenue": "80", "tax": "89", "ar": "84"}}


def _cipher():
    key = os.environ.get("TOKEN_ENCRYPTION_KEY", "")
    if not key:
        return None
    from cryptography.fernet import Fernet
    return Fernet(key.encode())


def _enc(v): c = _cipher(); return c.encrypt(v.encode()).decode() if c else v
def _dec(v): c = _cipher(); return c.decrypt(v.encode()).decode() if c else v
def _now(): return datetime.now(timezone.utc)


def _creds(p):
    e = PROV[p]["env"]
    return os.environ.get(f"{e}_CLIENT_ID", ""), os.environ.get(f"{e}_CLIENT_SECRET", "")


def _redirect(p):
    return f"{os.environ.get('PUBLIC_BASE_URL', '').rstrip('/')}/api/accounting/oauth/{p}/callback"


async def build_daily_journal(db, property_id: str, business_date: str) -> dict:
    """Günlük yevmiye: DR ödemeler (tahsilat), CR oda geliri, CR vergi; fark → AR/clearing."""
    pays = await db.payments.find({"property_id": property_id, "date": business_date, "payment_type": {"$ne": "refund"}},
                                  {"_id": 0, "amount": 1, "method": 1}).to_list(5000)
    refunds = await db.payments.find({"property_id": property_id, "date": business_date, "payment_type": "refund"}, {"_id": 0, "amount": 1}).to_list(1000)
    outs = await db.bookings.find({"property_id": property_id, "check_out": business_date, "status": {"$in": ["checked_out", "completed"]}},
                                  {"_id": 0, "total_price": 1, "total_amount": 1, "tax_amount": 1, "currency": 1}).to_list(5000)
    payments = round(sum(float(p.get("amount") or 0) for p in pays) - sum(float(r.get("amount") or 0) for r in refunds), 2)
    gross = round(sum(float(b.get("total_price") or b.get("total_amount") or 0) for b in outs), 2)
    tax = round(sum(float(b.get("tax_amount") or 0) for b in outs), 2)
    if not tax and gross:
        rate = float((await db.properties.find_one({"id": property_id}, {"_id": 0, "vat_rate": 1}) or {}).get("vat_rate") or 20) / 100
        tax = round(gross - gross / (1 + rate), 2)
    revenue = round(gross - tax, 2)
    ar = round(gross - payments, 2)  # + → AR artışı (tahsil edilmemiş), − → peşin/depozito
    currency = (outs[0].get("currency") if outs else None) or "GBP"
    by_method: Dict[str, float] = {}
    for p in pays:
        by_method[p.get("method", "other")] = round(by_method.get(p.get("method", "other"), 0) + float(p.get("amount") or 0), 2)
    lines = [{"account": "payments", "side": "debit", "amount": payments, "desc": f"Tahsilat {business_date}"},
             {"account": "revenue", "side": "credit", "amount": revenue, "desc": "Oda geliri (net)"},
             {"account": "tax", "side": "credit", "amount": tax, "desc": "KDV/VAT"}]
    if ar:
        lines.append({"account": "ar", "side": "debit" if ar > 0 else "credit", "amount": abs(ar), "desc": "Misafir alacağı / clearing"})
    lines = [l for l in lines if l["amount"]]
    return {"property_id": property_id, "business_date": business_date, "currency": currency, "payments": payments, "gross": gross,
            "revenue": revenue, "tax": tax, "ar_delta": ar, "by_method": by_method, "checkouts": len(outs), "lines": lines,
            "balanced": round(sum(l["amount"] for l in lines if l["side"] == "debit") - sum(l["amount"] for l in lines if l["side"] == "credit"), 2) == 0}



# ==================== YEVMİYE UYARILARI ====================
async def run_journal_alert_check(db, property_id: Optional[str] = None, force: bool = False) -> dict:
    """Son 2 gün için: başarısız yevmiye → anında; eksik yevmiye 2 gün üst üste → uyarı. E-posta + WhatsApp + bildirim."""
    from routes.platform_ext.mailer import send_email
    today = _now().date()
    d1, d2 = (today - timedelta(days=1)).isoformat(), (today - timedelta(days=2)).isoformat()
    q = {"property_id": property_id} if property_id else {}
    cfgs = {c["property_id"]: c async for c in db.journal_alert_config.find(q, {"_id": 0})}
    pids = [property_id] if property_id else sorted({*cfgs.keys(), *[c["property_id"] async for c in db.accounting_connections.find({}, {"_id": 0, "property_id": 1})]})
    out = {"checked": 0, "alerts": []}
    for pid in pids:
        cfg = cfgs.get(pid) or {"enabled": True, "emails": [], "whatsapp": [], "missing_days": 2}
        if not cfg.get("enabled", True):
            continue
        out["checked"] += 1
        recs = await db.accounting_journal.find({"property_id": pid, "business_date": {"$in": [d1, d2]}}, {"_id": 0, "business_date": 1, "provider": 1, "status": 1, "response": 1}).to_list(50)
        failed = [r for r in recs if r.get("status") == "failed"]
        have = {r["business_date"] for r in recs if r.get("status") in ("pushed", "mock")}
        missing_both = d1 not in have and d2 not in have and int(cfg.get("missing_days") or 2) <= 2
        issues = []
        if failed:
            issues.append(("failed", d1 if any(r["business_date"] == d1 for r in failed) else d2, f"{len(failed)} yevmiye kaydı başarısız: " + "; ".join(f"{r['provider'].upper()} {r['business_date']}: {str(r.get('response'))[:80]}" for r in failed[:3])))
        if missing_both:
            issues.append(("missing", d1, f"{d2} ve {d1} günlerine ait yevmiye Xero/QuickBooks'a gönderilmedi (2 gün eksik)."))
        prop = await db.properties.find_one({"id": pid}, {"_id": 0, "name": 1}) or {}
        for kind, bd, text in issues:
            key = {"property_id": pid, "kind": kind, "business_date": bd}
            if not force and await db.journal_alerts.find_one(key):
                continue
            recipients = list(cfg.get("emails") or [])
            if not recipients:
                async for u in db.users.find({"role": {"$in": ["admin", "manager"]}, "is_active": {"$ne": False}}, {"_id": 0, "email": 1, "property_access": 1}):
                    if u.get("email") and (not u.get("property_access") or pid in u["property_access"]):
                        recipients.append(u["email"])
            title = f"⚠️ Yevmiye uyarısı — {prop.get('name', pid)}"
            html = (f"<div style='font-family:system-ui;max-width:560px'><h2 style='color:#b91c1c'>Yevmiye {('başarısız' if kind == 'failed' else 'eksik')}</h2>"
                    f"<p><b>{prop.get('name', pid)}</b></p><p>{text}</p>"
                    f"<p style='color:#57534e;font-size:13px'>Muhasebe → Yevmiye Takvimi'nden tek tıkla yeniden gönderebilirsiniz.</p></div>")
            sent = {"email": [], "whatsapp": []}
            for em in recipients[:10]:
                try:
                    sent["email"].append({em: await send_email(db, em, title, html, kind="journal_alert", meta={"property_id": pid, "business_date": bd})})
                except Exception as e:
                    sent["email"].append({em: f"error:{str(e)[:60]}"})
            for num in (cfg.get("whatsapp") or [])[:5]:
                try:
                    from routes.marketing.whatsapp_voice import _send_whatsapp_reply
                    to = num if num.startswith("whatsapp:") else f"whatsapp:{num}"
                    sent["whatsapp"].append({num: (await _send_whatsapp_reply(to, f"{title}\n{text}\nMuhasebe → Yevmiye Takvimi'nden yeniden gönderin.")).get("status")})
                except Exception as e:
                    sent["whatsapp"].append({num: f"error:{str(e)[:60]}"})
            await db.notifications.insert_one({"id": str(uuid.uuid4()), "property_id": pid, "type": "journal_alert", "title": title, "body": text, "read": False, "created_at": _now().isoformat()})
            await db.journal_alerts.insert_one({**key, "id": str(uuid.uuid4()), "text": text, "recipients": recipients, "sent": sent, "created_at": _now().isoformat()})
            out["alerts"].append({"property_id": pid, "kind": kind, "business_date": bd, "recipients": len(recipients), "whatsapp": len(cfg.get("whatsapp") or [])})
    return out


def _xero_body(j, m):
    return {"ManualJournals": [{"Date": j["business_date"], "Narration": f"Hotel daily journal {j['business_date']}", "LineAmountTypes": "NoTax",
                                "JournalLines": [{"Description": l["desc"], "AccountCode": m[l["account"]], "TaxType": "NONE",
                                                  "LineAmount": l["amount"] if l["side"] == "debit" else -l["amount"]} for l in j["lines"]]}]}


def _qbo_body(j, m):
    return {"TxnDate": j["business_date"], "PrivateNote": f"Hotel daily journal {j['business_date']}", "CurrencyRef": {"value": j["currency"]},
            "Line": [{"Amount": l["amount"], "Description": l["desc"], "DetailType": "JournalEntryLineDetail",
                      "JournalEntryLineDetail": {"PostingType": "Debit" if l["side"] == "debit" else "Credit", "AccountRef": {"value": m[l["account"]]}}}
                     for l in j["lines"]]}


def build_ubl_tr(booking: dict, prop: dict, inv_no: str) -> str:
    """UBL-TR 1.2 e-Fatura (TEMELFATURA) taslağı — GİB entegratörüne gönderilecek XML."""
    gross = float(booking.get("total_price") or booking.get("total_amount") or 0)
    rate = float(prop.get("vat_rate") or 10)
    net = round(gross / (1 + rate / 100), 2); vat = round(gross - net, 2)
    d = (booking.get("check_out") or _now().date().isoformat())[:10]
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2" xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2" xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
  <cbc:UBLVersionID>2.1</cbc:UBLVersionID><cbc:CustomizationID>TR1.2</cbc:CustomizationID>
  <cbc:ProfileID>TEMELFATURA</cbc:ProfileID><cbc:ID>{escape(inv_no)}</cbc:ID><cbc:CopyIndicator>false</cbc:CopyIndicator>
  <cbc:UUID>{uuid.uuid4()}</cbc:UUID><cbc:IssueDate>{d}</cbc:IssueDate><cbc:InvoiceTypeCode>SATIS</cbc:InvoiceTypeCode>
  <cbc:DocumentCurrencyCode>{escape(booking.get('currency') or 'TRY')}</cbc:DocumentCurrencyCode><cbc:LineCountNumeric>1</cbc:LineCountNumeric>
  <cac:AccountingSupplierParty><cac:Party><cac:PartyIdentification><cbc:ID schemeID="VKN">{escape(str(prop.get('tax_number') or '0000000000'))}</cbc:ID></cac:PartyIdentification>
    <cac:PartyName><cbc:Name>{escape(prop.get('legal_name') or prop.get('name') or 'Hotel')}</cbc:Name></cac:PartyName></cac:Party></cac:AccountingSupplierParty>
  <cac:AccountingCustomerParty><cac:Party><cac:PartyIdentification><cbc:ID schemeID="TCKN">{escape(str(booking.get('guest_tax_id') or '11111111111'))}</cbc:ID></cac:PartyIdentification>
    <cac:Person><cbc:FirstName>{escape((booking.get('guest_name') or 'Misafir').split(' ')[0])}</cbc:FirstName><cbc:FamilyName>{escape(' '.join((booking.get('guest_name') or '').split(' ')[1:]) or '-')}</cbc:FamilyName></cac:Person></cac:Party></cac:AccountingCustomerParty>
  <cac:TaxTotal><cbc:TaxAmount currencyID="TRY">{vat:.2f}</cbc:TaxAmount><cac:TaxSubtotal><cbc:TaxableAmount currencyID="TRY">{net:.2f}</cbc:TaxableAmount><cbc:TaxAmount currencyID="TRY">{vat:.2f}</cbc:TaxAmount><cbc:Percent>{rate:.0f}</cbc:Percent><cac:TaxCategory><cac:TaxScheme><cbc:Name>KDV</cbc:Name><cbc:TaxTypeCode>0015</cbc:TaxTypeCode></cac:TaxScheme></cac:TaxCategory></cac:TaxSubtotal></cac:TaxTotal>
  <cac:LegalMonetaryTotal><cbc:LineExtensionAmount currencyID="TRY">{net:.2f}</cbc:LineExtensionAmount><cbc:TaxExclusiveAmount currencyID="TRY">{net:.2f}</cbc:TaxExclusiveAmount><cbc:TaxInclusiveAmount currencyID="TRY">{gross:.2f}</cbc:TaxInclusiveAmount><cbc:PayableAmount currencyID="TRY">{gross:.2f}</cbc:PayableAmount></cac:LegalMonetaryTotal>
  <cac:InvoiceLine><cbc:ID>1</cbc:ID><cbc:InvoicedQuantity unitCode="C62">1</cbc:InvoicedQuantity><cbc:LineExtensionAmount currencyID="TRY">{net:.2f}</cbc:LineExtensionAmount>
    <cac:Item><cbc:Name>Konaklama {escape(booking.get('check_in') or '')} - {escape(booking.get('check_out') or '')}</cbc:Name></cac:Item><cac:Price><cbc:PriceAmount currencyID="TRY">{net:.2f}</cbc:PriceAmount></cac:Price></cac:InvoiceLine>
</Invoice>"""


def create_accounting_sync_router(db, require_roles):
    router = APIRouter()

    async def _token(provider: str, property_id: str) -> dict:
        con = await db.accounting_connections.find_one({"provider": provider, "property_id": property_id}, {"_id": 0})
        if not con:
            raise HTTPException(400, f"{provider} bağlı değil")
        exp = datetime.fromisoformat(con["expires"]) if isinstance(con["expires"], str) else con["expires"]
        if exp > _now() + timedelta(seconds=60):
            return con
        cid, sec = _creds(provider)
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.post(PROV[provider]["token"], data={"grant_type": "refresh_token", "refresh_token": _dec(con["refresh"])},
                             auth=(cid, sec), headers={"Accept": "application/json"})
        if r.status_code in (400, 401):
            await db.accounting_connections.update_one({"id": con["id"]}, {"$set": {"status": "reauth_required"}})
            raise HTTPException(401, f"{provider} yetkisi yenilenemedi; yeniden bağlanın")
        r.raise_for_status(); t = r.json()
        upd = {"access": _enc(t["access_token"]), "expires": (_now() + timedelta(seconds=int(t["expires_in"]))).isoformat()}
        if t.get("refresh_token"): upd["refresh"] = _enc(t["refresh_token"])
        await db.accounting_connections.update_one({"id": con["id"]}, {"$set": upd})
        return {**con, **upd}

    async def push_journal(provider: str, property_id: str, j: dict) -> dict:
        con = await db.accounting_connections.find_one({"provider": provider, "property_id": property_id}, {"_id": 0})
        m = {**DEFAULT_MAPPING[provider], **((con or {}).get("mapping") or {})}
        key = f"{property_id}|{provider}|{j['business_date']}|daily"
        if await db.accounting_journal.find_one({"idem_key": key, "status": {"$in": ["pushed", "mock"]}}, {"_id": 1}):
            return {"status": "duplicate_skipped", "idem_key": key}
        body = _xero_body(j, m) if provider == "xero" else _qbo_body(j, m)
        rec = {"id": str(uuid.uuid4()), "idem_key": key, "provider": provider, "property_id": property_id, "business_date": j["business_date"],
               "journal": j, "request_body": body, "created_at": _now().isoformat()}
        if not con or not _creds(provider)[0]:
            rec.update({"status": "mock", "note": "Sağlayıcı bağlı değil — outbox'ta bekliyor (MOCK)"})
            await db.accounting_journal.insert_one(dict(rec)); rec.pop("_id", None)
            return rec
        tok = await _token(provider, property_id)
        async with httpx.AsyncClient(timeout=30) as c:
            if provider == "xero":
                r = await c.post("https://api.xero.com/api.xro/2.0/ManualJournals", json=body,
                                 headers={"Authorization": f"Bearer {_dec(tok['access'])}", "xero-tenant-id": tok["tenant_id"],
                                          "Accept": "application/json", "Idempotency-Key": key})
            else:
                base = "https://sandbox-quickbooks.api.intuit.com" if os.environ.get("QBO_SANDBOX", "true") == "true" else "https://quickbooks.api.intuit.com"
                r = await c.post(f"{base}/v3/company/{tok['realm_id']}/journalentry", json=body,
                                 headers={"Authorization": f"Bearer {_dec(tok['access'])}", "Accept": "application/json", "Content-Type": "application/json"})
        rec.update({"status": "pushed" if not r.is_error else "failed", "http_status": r.status_code,
                    "response": (r.json() if r.content and not r.is_error else r.text[:500])})
        await db.accounting_journal.insert_one(dict(rec)); rec.pop("_id", None)
        return rec

    async def run_daily_sync_internal(property_id: str = "all", business_date: Optional[str] = None) -> dict:
        bd = business_date or (_now() - timedelta(days=1)).date().isoformat()
        pids = [property_id] if property_id and property_id != "all" else [p["id"] async for p in db.properties.find({}, {"_id": 0, "id": 1})]
        out = []
        for pid in pids:
            j = await build_daily_journal(db, pid, bd)
            cons = await db.accounting_connections.find({"property_id": pid}, {"_id": 0, "provider": 1}).to_list(5)
            providers = [c["provider"] for c in cons] or [(await db.accounting_settings.find_one({"property_id": pid}, {"_id": 0}) or {}).get("default_provider", "xero")]
            res = {p: await push_journal(p, pid, j) for p in providers}
            ef = None
            if (await db.accounting_settings.find_one({"property_id": pid}, {"_id": 0}) or {}).get("efatura_enabled"):
                ef = await issue_efatura_internal(pid, bd)
            out.append({"property_id": pid, "business_date": bd, "journal": {k: j[k] for k in ("payments", "revenue", "tax", "ar_delta", "checkouts", "balanced")},
                        "results": {p: r["status"] for p, r in res.items()}, "efatura": ef})
        return {"ok": True, "results": out}

    async def issue_efatura_internal(property_id: str, business_date: str) -> dict:
        prop = await db.properties.find_one({"id": property_id}, {"_id": 0}) or {}
        outs = await db.bookings.find({"property_id": property_id, "check_out": business_date, "status": {"$in": ["checked_out", "completed"]},
                                       "efatura_id": {"$exists": False}}, {"_id": 0}).to_list(500)
        issued = []
        seq = await db.efatura.count_documents({"property_id": property_id}) + 1
        for b in outs:
            inv_no = f"{(prop.get('efatura_prefix') or 'HTL')}{_now().year}{seq:09d}"; seq += 1
            xml = build_ubl_tr(b, prop, inv_no)
            live = bool(os.environ.get("EFATURA_INTEGRATOR_KEY"))
            rec = {"id": str(uuid.uuid4()), "property_id": property_id, "booking_id": b.get("id"), "invoice_no": inv_no, "guest_name": b.get("guest_name"),
                   "amount": float(b.get("total_price") or b.get("total_amount") or 0), "xml": xml,
                   "status": "sent" if live else "draft", "gib_status": "queued" if live else "not_sent_mock", "created_at": _now().isoformat()}
            await db.efatura.insert_one(dict(rec))
            await db.bookings.update_one({"id": b.get("id")}, {"$set": {"efatura_id": rec["id"], "efatura_no": inv_no}})
            issued.append({"invoice_no": inv_no, "amount": rec["amount"], "status": rec["status"]})
        return {"issued": len(issued), "items": issued[:20], "mode": "live" if os.environ.get("EFATURA_INTEGRATOR_KEY") else "MOCK_DRAFT"}

    router.run_daily_sync_internal = run_daily_sync_internal

    # ---------- endpoints ----------
    @router.get("/accounting/connectors/{property_id}")
    async def connectors(property_id: str, _: dict = Depends(require_roles("admin", "manager"))):
        cons = await db.accounting_connections.find({"property_id": property_id}, {"_id": 0, "access": 0, "refresh": 0}).to_list(5)
        st = await db.accounting_settings.find_one({"property_id": property_id}, {"_id": 0}) or {}
        last = await db.accounting_journal.find({"property_id": property_id}, {"_id": 0, "request_body": 0}).sort("created_at", -1).to_list(10)
        ef = await db.efatura.count_documents({"property_id": property_id})
        return {"providers": {p: {"client_configured": bool(_creds(p)[0] and _creds(p)[1]), "redirect_uri": _redirect(p),
                                  "connected": any(c["provider"] == p for c in cons),
                                  "connection": next((c for c in cons if c["provider"] == p), None), "mapping": {**DEFAULT_MAPPING[p], **(next((c.get("mapping") or {} for c in cons if c["provider"] == p), {}))}}
                              for p in PROV},
                "efatura": {"enabled": bool(st.get("efatura_enabled")), "live": bool(os.environ.get("EFATURA_INTEGRATOR_KEY")), "issued": ef},
                "settings": st, "recent_journals": last}

    @router.post("/accounting/settings/{property_id}")
    async def save_settings(property_id: str, body: dict, _: dict = Depends(require_roles("admin", "manager"))):
        upd = {k: body[k] for k in ("efatura_enabled", "default_provider", "efatura_prefix") if k in body}
        await db.accounting_settings.update_one({"property_id": property_id}, {"$set": {"property_id": property_id, **upd}}, upsert=True)
        return await db.accounting_settings.find_one({"property_id": property_id}, {"_id": 0})

    @router.post("/accounting/mapping/{provider}/{property_id}")
    async def save_mapping(provider: str, property_id: str, body: dict, _: dict = Depends(require_roles("admin", "manager"))):
        if provider not in PROV: raise HTTPException(404)
        m = {k: str(v) for k, v in body.items() if k in DEFAULT_MAPPING[provider]}
        r = await db.accounting_connections.update_one({"provider": provider, "property_id": property_id}, {"$set": {"mapping": m}})
        if not r.matched_count:
            await db.accounting_connections.insert_one({"id": str(uuid.uuid4()), "provider": provider, "property_id": property_id, "status": "mapping_only",
                                                        "mapping": m, "expires": _now().isoformat(), "created_at": _now().isoformat()})
        return {"ok": True, "mapping": {**DEFAULT_MAPPING[provider], **m}}

    @router.get("/accounting/oauth/{provider}/start")
    async def oauth_start(provider: str, property_id: str = "default", current_user: dict = Depends(require_roles("admin", "manager"))):
        if provider not in PROV: raise HTTPException(404)
        cid, sec = _creds(provider)
        if not (cid and sec):
            raise HTTPException(400, f"{PROV[provider]['env']}_CLIENT_ID / _CLIENT_SECRET .env'de yok. Redirect URI: {_redirect(provider)}")
        state = secrets.token_urlsafe(32)
        await db.oauth_states.insert_one({"id": state, "provider": provider, "property_id": property_id, "user": current_user.get("email", ""), "created_at": _now().isoformat()})
        params = {"response_type": "code", "client_id": cid, "redirect_uri": _redirect(provider), "scope": PROV[provider]["scope"], "state": state}
        return {"url": PROV[provider]["auth"] + "?" + urlencode(params)}

    @router.get("/accounting/oauth/{provider}/callback")
    async def oauth_callback(provider: str, code: str = "", state: str = "", realmId: str = "", error: str = ""):
        front = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")
        if provider not in PROV or error or not code or not state:
            return RedirectResponse(f"{front}/?acct=error&reason={error or 'missing_code'}")
        st = await db.oauth_states.find_one_and_delete({"id": state, "provider": provider})
        if not st:
            return RedirectResponse(f"{front}/?acct=error&reason=invalid_state")
        cid, sec = _creds(provider)
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.post(PROV[provider]["token"], data={"grant_type": "authorization_code", "code": code, "redirect_uri": _redirect(provider)},
                             auth=(cid, sec), headers={"Accept": "application/json"})
            if r.is_error:
                return RedirectResponse(f"{front}/?acct=error&reason=token_exchange")
            tok = r.json()
            doc = {"id": str(uuid.uuid4()), "provider": provider, "property_id": st["property_id"], "access": _enc(tok["access_token"]),
                   "refresh": _enc(tok.get("refresh_token", "")), "expires": (_now() + timedelta(seconds=int(tok["expires_in"]))).isoformat(),
                   "status": "connected", "connected_by": st.get("user", ""), "connected_at": _now().isoformat()}
            if provider == "xero":
                con = await c.get("https://api.xero.com/connections", headers={"Authorization": f"Bearer {tok['access_token']}"})
                if con.is_error or not con.json():
                    return RedirectResponse(f"{front}/?acct=error&reason=no_tenant")
                doc["tenant_id"] = con.json()[0]["tenantId"]; doc["tenant_name"] = con.json()[0].get("tenantName", "")
            else:
                if not realmId:
                    return RedirectResponse(f"{front}/?acct=error&reason=missing_realm")
                doc["realm_id"] = realmId
        await db.accounting_connections.update_one({"provider": provider, "property_id": st["property_id"]}, {"$set": doc}, upsert=True)
        return RedirectResponse(f"{front}/?acct=connected&provider={provider}")

    @router.delete("/accounting/oauth/{provider}/disconnect")
    async def disconnect(provider: str, property_id: str = "default", _: dict = Depends(require_roles("admin", "manager"))):
        await db.accounting_connections.delete_many({"provider": provider, "property_id": property_id})
        return {"ok": True}

    @router.get("/accounting/journal/preview/{property_id}")
    async def journal_preview(property_id: str, business_date: Optional[str] = None, _: dict = Depends(require_roles("admin", "manager"))):
        return await build_daily_journal(db, property_id, business_date or (_now() - timedelta(days=1)).date().isoformat())

    @router.post("/accounting/sync/run/{property_id}")
    async def sync_run(property_id: str, business_date: Optional[str] = None, _: dict = Depends(require_roles("admin", "manager"))):
        return await run_daily_sync_internal(property_id, business_date)

    @router.get("/accounting/journal/{property_id}")
    async def journal_list(property_id: str, limit: int = 30, _: dict = Depends(require_roles("admin", "manager"))):
        return {"items": await db.accounting_journal.find({"property_id": property_id}, {"_id": 0, "request_body": 0, "journal.lines": 0}).sort("created_at", -1).to_list(limit)}

    @router.get("/accounting/journal/calendar/{property_id}")
    async def journal_calendar(property_id: str, month: Optional[str] = None, _: dict = Depends(require_roles("admin", "manager"))):
        """Ay bazında gün gün yevmiye durumu: pushed / mock / failed / missing (bugünden önceki günler)."""
        from datetime import date as _date
        try:
            y, m = (int(x) for x in (month or _now().strftime("%Y-%m")).split("-"))
            first = _date(y, m, 1)
        except Exception:
            raise HTTPException(422, "month=YYYY-MM")
        last = _date(y + (m == 12), (m % 12) + 1, 1) - timedelta(days=1)
        yesterday = (_now() - timedelta(days=1)).date()
        providers = [c["provider"] for c in await db.accounting_connections.find({"property_id": property_id}, {"_id": 0, "provider": 1}).to_list(5)] or ["xero", "qbo"]
        recs = await db.accounting_journal.find({"property_id": property_id, "business_date": {"$gte": first.isoformat(), "$lte": last.isoformat()}},
                                                {"_id": 0, "request_body": 0, "journal.lines": 0}).sort("created_at", 1).to_list(2000)
        by = {}
        for r in recs:
            by.setdefault(r["business_date"], {})[r["provider"]] = r
        days, counts = [], {"pushed": 0, "mock": 0, "failed": 0, "missing": 0, "future": 0}
        d = first
        while d <= last:
            iso = d.isoformat()
            per = {}
            for p in providers:
                r = by.get(iso, {}).get(p)
                if d > yesterday:
                    st = "future"
                elif not r:
                    st = "missing"
                else:
                    st = r.get("status") if r.get("status") in ("pushed", "mock", "failed") else "failed"
                per[p] = {"status": st, "id": (r or {}).get("id"), "total": ((r or {}).get("journal") or {}).get("gross"),
                          "error": (str((r or {}).get("response"))[:160] if st == "failed" else None), "at": (r or {}).get("created_at")}
            worst = "future" if d > yesterday else ("failed" if any(x["status"] == "failed" for x in per.values()) else "missing" if any(x["status"] == "missing" for x in per.values()) else "mock" if any(x["status"] == "mock" for x in per.values()) else "pushed")
            counts[worst] += 1
            days.append({"date": iso, "status": worst, "providers": per, "weekend": d.weekday() >= 5})
            d += timedelta(days=1)
        return {"month": f"{y:04d}-{m:02d}", "providers": providers, "days": days, "counts": counts,
                "resend_candidates": [x["date"] for x in days if x["status"] in ("failed", "missing")]}

    @router.post("/accounting/journal/resend/{property_id}")
    async def journal_resend(property_id: str, body: dict, _: dict = Depends(require_roles("admin", "manager"))):
        """Eksik/başarısız günleri tek tıkla yeniden gönder. body: {dates: [..]} veya {business_date}"""
        dates = body.get("dates") or ([body["business_date"]] if body.get("business_date") else [])
        if not dates or len(dates) > 31:
            raise HTTPException(422, "1-31 tarih verin")
        out = []
        for bd in dates:
            await db.accounting_journal.update_many({"property_id": property_id, "business_date": bd, "status": "failed"}, {"$set": {"status": "superseded"}})
            out.append({"business_date": bd, "result": await run_daily_sync_internal(property_id, bd)})
        return {"ok": True, "items": out}

    @router.get("/accounting/journal/alerts/config/{property_id}")
    async def journal_alert_cfg(property_id: str, _: dict = Depends(require_roles("admin", "manager"))):
        cfg = await db.journal_alert_config.find_one({"property_id": property_id}, {"_id": 0}) or {"property_id": property_id, "enabled": True, "emails": [], "whatsapp": [], "missing_days": 2}
        log = await db.journal_alerts.find({"property_id": property_id}, {"_id": 0}).sort("created_at", -1).to_list(20)
        return {**cfg, "log": log}

    @router.put("/accounting/journal/alerts/config/{property_id}")
    async def journal_alert_cfg_save(property_id: str, body: dict, _: dict = Depends(require_roles("admin", "manager"))):
        emails = [e.strip() for e in (body.get("emails") or []) if isinstance(e, str) and "@" in e][:10]
        wa = [w.strip() for w in (body.get("whatsapp") or []) if isinstance(w, str) and w.strip().lstrip("whatsapp:+").isdigit()][:5]
        upd = {"property_id": property_id, "enabled": bool(body.get("enabled", True)), "emails": emails, "whatsapp": wa, "missing_days": 2, "updated_at": _now().isoformat()}
        await db.journal_alert_config.update_one({"property_id": property_id}, {"$set": upd}, upsert=True)
        return {"ok": True, **upd}

    @router.post("/accounting/journal/alerts/run/{property_id}")
    async def journal_alert_run(property_id: str, force: bool = False, _: dict = Depends(require_roles("admin", "manager"))):
        return await run_journal_alert_check(db, property_id, force=force)

    @router.post("/accounting/efatura/issue/{property_id}")
    async def efatura_issue(property_id: str, business_date: Optional[str] = None, _: dict = Depends(require_roles("admin", "manager"))):
        return await issue_efatura_internal(property_id, business_date or (_now() - timedelta(days=1)).date().isoformat())

    @router.get("/accounting/efatura/{property_id}")
    async def efatura_list(property_id: str, limit: int = 30, _: dict = Depends(require_roles("admin", "manager"))):
        return {"items": await db.efatura.find({"property_id": property_id}, {"_id": 0, "xml": 0}).sort("created_at", -1).to_list(limit)}

    @router.get("/accounting/efatura/{property_id}/{invoice_id}/xml")
    async def efatura_xml(property_id: str, invoice_id: str, _: dict = Depends(require_roles("admin", "manager"))):
        from fastapi.responses import Response
        rec = await db.efatura.find_one({"property_id": property_id, "id": invoice_id}, {"_id": 0, "xml": 1, "invoice_no": 1})
        if not rec: raise HTTPException(404)
        return Response(rec["xml"], media_type="application/xml", headers={"Content-Disposition": f"attachment; filename={rec['invoice_no']}.xml"})

    return router
