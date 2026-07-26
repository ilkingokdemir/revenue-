"""
Dijital Ödeme Yetkilendirme (Canary "Digital Authorizations" paritesi)
Faks/PDF kart formları yerine güvenli link: otel talep oluşturur → ödeyen
(kurumsal/3. şahıs) formu doldurur → otel tahsil eder veya iptal eder.
PCI: tam kart numarası ASLA saklanmaz — sadece son 4 hane + marka + imzalı onay.
Durum akışı: pending → authorized → charged | voided | expired
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional
import os
import uuid
import secrets
import logging

logger = logging.getLogger(__name__)

try:
    import resend
except Exception:
    resend = None

PURPOSES = {
    "room_charge": "Konaklama ücreti",
    "deposit": "Depozito",
    "no_show_guarantee": "No-show garantisi",
    "incidentals": "Ekstra harcamalar",
    "third_party": "3. şahıs ödemesi",
}


def _now():
    return datetime.now(timezone.utc)


async def _send_email(to_email: str, subject: str, html: str) -> str:
    api_key = os.environ.get("RESEND_API_KEY", "")
    if not resend or not api_key or api_key.startswith("re_1234"):
        logger.info(f"[MOCK EMAIL] DigitalAuth to {to_email}: {subject}")
        return "mock"
    try:
        resend.api_key = api_key
        resend.Emails.send({"from": os.environ.get("RESEND_FROM", "MyHotelBox <onboarding@resend.dev>"),
                            "to": [to_email], "subject": subject, "html": html})
        return "sent"
    except Exception as e:
        logger.warning(f"DigitalAuth email failed: {e}")
        return "failed"


def create_digital_auth_router(db, require_roles):
    router = APIRouter(prefix="/digital-auth")
    STAFF = require_roles("admin", "manager", "receptionist")

    @router.post("/requests")
    async def create_request(data: Dict, current_user: dict = Depends(STAFF)):
        email = (data.get("payer_email") or "").lower().strip()
        amount = float(data.get("amount") or 0)
        if not email or "@" not in email:
            raise HTTPException(400, "Geçerli payer_email gerekli")
        if amount <= 0:
            raise HTTPException(400, "amount > 0 olmalı")
        purpose = data.get("purpose", "room_charge")
        if purpose not in PURPOSES:
            purpose = "room_charge"
        expires_days = min(max(int(data.get("expires_days") or 7), 1), 30)
        doc = {
            "id": str(uuid.uuid4()), "token": secrets.token_urlsafe(16),
            "property_id": data.get("property_id", "all"),
            "payer_name": (data.get("payer_name") or "").strip(),
            "payer_email": email, "booking_id": data.get("booking_id", ""),
            "amount": round(amount, 2), "currency": data.get("currency", "GBP"),
            "purpose": purpose, "purpose_label": PURPOSES[purpose],
            "note": (data.get("note") or "")[:400],
            "status": "pending",
            "expires_at": (_now() + timedelta(days=expires_days)).isoformat(),
            "created_by": current_user.get("email", ""), "created_at": _now().isoformat(),
        }
        await db.digital_auth_requests.insert_one(dict(doc))
        doc.pop("_id", None)
        base = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")
        link = f"{base}/authorize/{doc['token']}"
        prop = await db.properties.find_one({"id": doc["property_id"]}, {"_id": 0, "name": 1}) or {}
        html = f"""
        <div style="font-family:Arial,sans-serif;max-width:560px;margin:auto;background:#fafaf9;padding:24px;border-radius:12px">
          <h2 style="color:#1c1917">🔐 Ödeme Yetkilendirme Talebi</h2>
          <p style="color:#44403c">{prop.get('name','Otelimiz')}, aşağıdaki işlem için kart yetkilendirmenizi talep ediyor:</p>
          <p style="background:#fff;border:1px solid #e7e5e4;border-radius:8px;padding:12px;color:#292524">
            <strong>{doc['purpose_label']}</strong> — {doc['currency']} {doc['amount']:,.2f}<br/>
            <span style="font-size:12px;color:#78716c">{doc['note']}</span></p>
          <p style="text-align:center;margin:24px 0">
            <a href="{link}" style="background:#1c1917;color:#fff;padding:14px 28px;border-radius:8px;text-decoration:none;font-weight:bold">Güvenli Formu Doldur →</a></p>
          <p style="color:#a8a29e;font-size:11px">Bağlantı {expires_days} gün geçerlidir. Kart bilgileriniz PCI-DSS uyumlu olarak işlenir; tam kart numarası saklanmaz.</p>
        </div>"""
        email_status = await _send_email(email, f"Ödeme yetkilendirme talebi — {prop.get('name','')}", html)
        await db.digital_auth_requests.update_one({"id": doc["id"]}, {"$set": {"email_status": email_status}})
        return {**doc, "link": link, "email_status": email_status}

    # ── PUBLIC ──
    @router.get("/public/{token}")
    async def public_get(token: str):
        d = await db.digital_auth_requests.find_one({"token": token}, {"_id": 0})
        if not d:
            raise HTTPException(404, "Geçersiz bağlantı")
        if d["status"] == "pending" and d["expires_at"] < _now().isoformat():
            await db.digital_auth_requests.update_one({"id": d["id"]}, {"$set": {"status": "expired"}})
            d["status"] = "expired"
        prop = await db.properties.find_one({"id": d.get("property_id")}, {"_id": 0, "name": 1}) or {}
        return {"status": d["status"], "property_name": prop.get("name", ""),
                "payer_name": d["payer_name"], "amount": d["amount"], "currency": d["currency"],
                "purpose_label": d["purpose_label"], "note": d["note"], "expires_at": d["expires_at"]}

    @router.post("/public/{token}/submit")
    async def public_submit(token: str, data: Dict):
        d = await db.digital_auth_requests.find_one({"token": token}, {"_id": 0})
        if not d:
            raise HTTPException(404, "Geçersiz bağlantı")
        if d["status"] != "pending":
            raise HTTPException(400, f"Bu talep artık doldurulamaz (durum: {d['status']})")
        if d["expires_at"] < _now().isoformat():
            await db.digital_auth_requests.update_one({"id": d["id"]}, {"$set": {"status": "expired"}})
            raise HTTPException(400, "Bağlantının süresi dolmuş")
        holder = (data.get("cardholder_name") or "").strip()
        last4 = str(data.get("card_last4") or "").strip()[-4:]
        signature = (data.get("signature") or "").strip()
        if len(holder) < 3 or not last4.isdigit() or len(last4) != 4:
            raise HTTPException(400, "Kart sahibi adı ve son 4 hane gerekli")
        if not data.get("consent") or len(signature) < 3:
            raise HTTPException(400, "Onay kutusu ve imza (ad soyad) zorunludur")
        await db.digital_auth_requests.update_one({"id": d["id"]}, {"$set": {
            "status": "authorized",
            "cardholder_name": holder[:80], "card_last4": last4,
            "card_brand": (data.get("card_brand") or "card")[:20],
            "billing_address": (data.get("billing_address") or "")[:200],
            "signature": signature[:80], "consent": True,
            "authorized_at": _now().isoformat(),
            "stripe_status": "mock_authorized",
        }})
        return {"ok": True, "status": "authorized"}

    # ── STAFF ──
    @router.get("/{property_id}")
    async def list_requests(property_id: str, status: Optional[str] = None,
                            current_user: dict = Depends(STAFF)):
        q: Dict = {} if property_id == "all" else {"property_id": property_id}
        if status:
            q["status"] = status
        now_iso = _now().isoformat()
        await db.digital_auth_requests.update_many(
            {**q, "status": "pending", "expires_at": {"$lt": now_iso}}, {"$set": {"status": "expired"}})
        rows = await db.digital_auth_requests.find(q, {"_id": 0}).sort("created_at", -1).to_list(200)
        base = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")
        for r in rows:
            r["link"] = f"{base}/authorize/{r['token']}"
        stats = {}
        for r in rows:
            stats[r["status"]] = stats.get(r["status"], 0) + 1
        return {"requests": rows, "stats": stats,
                "authorized_total": round(sum(r["amount"] for r in rows if r["status"] == "authorized"), 2),
                "charged_total": round(sum(r["amount"] for r in rows if r["status"] == "charged"), 2)}

    @router.post("/{request_id}/charge")
    async def charge(request_id: str, current_user: dict = Depends(STAFF)):
        d = await db.digital_auth_requests.find_one({"id": request_id, "status": "authorized"}, {"_id": 0})
        if not d:
            raise HTTPException(404, "Yetkilendirilmiş talep bulunamadı")
        await db.digital_auth_requests.update_one({"id": request_id}, {"$set": {
            "status": "charged", "charged_at": _now().isoformat(),
            "charged_by": current_user.get("email", ""), "stripe_status": "mock_charged"}})
        return {"ok": True, "status": "charged", "amount": d["amount"]}

    @router.post("/{request_id}/void")
    async def void(request_id: str, current_user: dict = Depends(STAFF)):
        r = await db.digital_auth_requests.update_one(
            {"id": request_id, "status": {"$in": ["pending", "authorized"]}},
            {"$set": {"status": "voided", "voided_at": _now().isoformat(),
                      "voided_by": current_user.get("email", "")}})
        if not r.modified_count:
            raise HTTPException(404, "İptal edilebilir talep bulunamadı")
        return {"ok": True, "status": "voided"}

    return router
