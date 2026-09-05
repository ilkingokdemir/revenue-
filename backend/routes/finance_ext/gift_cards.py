"""
Gift Cards / Vouchers (P1)
Hotel-branded prepaid vouchers. Typical revenue use cases:
- Christmas/holiday gift purchases (spike in Q4)
- Apology / compensation issuance
- Referral programme rewards
Each card has: code, initial_amount, balance, expires_at, status (active/redeemed/expired/cancelled)
Redemption creates a folio payment line with method='gift_card'. Outstanding balance is a liability.
"""
from fastapi.responses import Response
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta
from typing import Dict
import uuid
import secrets
import string
import logging

logger = logging.getLogger(__name__)


GIFT_DESIGNS = {
    "classic": {"name": "Klasik", "desc": "Otel vurgu rengi, zamansız", "season": "all", "bg": None, "text": "#ffffff", "eyebrow": "HEDİYE ÇEKİ · GIFT CARD", "emoji": "", "font": "Georgia,serif", "outer": "#f4f4f5", "deco": ""},
    "festive": {"name": "Yılbaşı & Kış", "desc": "Koyu yeşil, altın, kar taneleri", "season": "winter", "bg": "linear-gradient(135deg,#0b3d2e,#14532d 60%,#365314)", "solid": "#0b3d2e", "text": "#fde68a", "eyebrow": "MUTLU YILLAR · SEASON'S GREETINGS", "emoji": "❄️ ✨ ❄️", "font": "Georgia,serif", "outer": "#f1f5f4", "deco": "<div style='font-size:22px;letter-spacing:8px;opacity:.9'>❄ ✦ ❄ ✦ ❄</div>"},
    "summer": {"name": "Yaz & Sahil", "desc": "Mercan, turkuaz, güneş", "season": "summer", "bg": "linear-gradient(135deg,#f97316,#fb7185 50%,#0ea5e9)", "solid": "#f97316", "text": "#ffffff", "eyebrow": "YAZ HEDİYESİ · SUMMER GIFT", "emoji": "☀️ 🌊", "font": "'Trebuchet MS',Helvetica,sans-serif", "outer": "#fff7ed", "deco": "<div style='font-size:22px;letter-spacing:8px;opacity:.95'>☀ ≈ ☀ ≈ ☀</div>"},
    "spring": {"name": "İlkbahar & Sevgililer", "desc": "Pudra pembe, adaçayı yeşili, çiçek", "season": "spring", "bg": "linear-gradient(135deg,#fbcfe8,#f9a8d4 45%,#a7f3d0)", "solid": "#f9a8d4", "text": "#4a044e", "eyebrow": "SEVGİYLE · WITH LOVE", "emoji": "🌸 🌿", "font": "Georgia,serif", "outer": "#fdf2f8", "deco": "<div style='font-size:22px;letter-spacing:8px;opacity:.9'>✿ ❀ ✿ ❀ ✿</div>"},
}


def gift_card_html(card: dict, hotel_name: str, accent: str = "#0f4c5c", book_url: str = "", design: str = "classic") -> str:
    d = GIFT_DESIGNS.get(design or "classic") or GIFT_DESIGNS["classic"]
    sym = {"TRY": "₺", "EUR": "€", "USD": "$"}.get(card.get("currency", "GBP"), "£")
    amt = f"{sym}{float(card.get('initial_amount', 0)):,.0f}"
    exp = (card.get("expires_at") or "")[:10]
    msg = (card.get("message") or "").replace("<", "&lt;")
    rec = (card.get("recipient_name") or "Sevgili Misafir").replace("<", "&lt;")
    frm = (card.get("purchaser_name") or hotel_name).replace("<", "&lt;")
    head_bg = d["bg"] or accent
    head_solid = d.get("solid") or accent
    btn = accent if design in (None, "", "classic") else head_solid
    return f"""<!doctype html><html><body style="margin:0;background:{d['outer']};font-family:{d['font']};color:#1c1917">
<table width="100%" cellpadding="0" cellspacing="0" style="padding:32px 12px"><tr><td align="center">
<table width="560" cellpadding="0" cellspacing="0" style="max-width:560px;background:#fff;border-radius:20px;overflow:hidden;box-shadow:0 10px 40px rgba(0,0,0,.08)">
<tr><td bgcolor="{head_solid}" style="background:{head_bg};padding:36px 32px;color:{d['text']};text-align:center">
{d['deco']}
<div style="font-size:11px;letter-spacing:.3em;text-transform:uppercase;opacity:.85;margin-top:6px">{d['eyebrow']}</div>
<div style="font-size:52px;font-weight:700;margin:12px 0 4px">{amt}</div>
<div style="font-size:16px;opacity:.9">{hotel_name} {d['emoji']}</div></td></tr>
<tr><td style="padding:28px 32px">
<p style="font-size:16px;margin:0 0 12px">Merhaba {rec},</p>
<p style="font-size:14px;line-height:1.6;margin:0 0 16px;color:#44403c">{frm} size <b>{hotel_name}</b>'da unutulmaz bir konaklama hediye etti.{(' <br><br><i>“' + msg + '”</i>') if msg else ''}</p>
<div style="border:2px dashed {btn};border-radius:14px;padding:18px;text-align:center;margin:20px 0">
<div style="font-size:11px;letter-spacing:.2em;color:#78716c;text-transform:uppercase">Çek kodunuz</div>
<div style="font-family:Menlo,Consolas,monospace;font-size:24px;font-weight:700;color:{btn};margin-top:6px">{card.get('code', '')}</div></div>
<p style="font-size:13px;color:#57534e;line-height:1.6;margin:0 0 20px">Rezervasyon sırasında ödeme adımında “Hediye çekiniz var mı?” alanına kodu girin; tutar toplamdan düşülür. Kalan bakiye sonraki rezervasyonlarınızda kullanılabilir.{(' Son kullanma: <b>' + exp + '</b>.') if exp else ''}</p>
{('<p style="text-align:center;margin:0 0 8px"><a href="' + book_url + '" style="display:inline-block;background:' + btn + ';color:#fff;text-decoration:none;padding:14px 28px;border-radius:999px;font-weight:700;font-size:14px">Rezervasyon Yap</a></p>') if book_url else ''}
</td></tr>
<tr><td style="padding:16px 32px;background:#fafaf9;font-size:11px;color:#a8a29e;text-align:center">{hotel_name} · Powered by MyHotelBox</td></tr>
</table></td></tr></table></body></html>"""


async def send_gift_card_emails(db, card: dict, base_url: str = "") -> dict:
    """Alıcıya (ve satın alana kopya) markalı hediye çeki e-postası. Idempotent: gift_cards.email_sent_at."""
    if card.get("email_sent_at"):
        return {"skipped": "already_sent"}
    from routes.platform_ext.mailer import send_email
    prop = await db.properties.find_one({"id": card.get("property_id")}, {"_id": 0, "name": 1}) or {}
    ts = await db.template_settings.find_one({"property_id": card.get("property_id")}, {"_id": 0, "accent_color": 1, "primary_color": 1}) or {}
    hotel = prop.get("name") or "Hotel"
    accent = ts.get("accent_color") or ts.get("primary_color") or "#0f4c5c"
    book_url = f"{base_url}/book?property={card.get('property_id')}" if base_url else ""
    gcfg = await db.gift_card_config.find_one({"property_id": card.get("property_id")}, {"_id": 0, "design": 1}) or {}
    design = card.get("design") or gcfg.get("design") or "classic"
    html = gift_card_html(card, hotel, accent, book_url, design)
    sym = {"TRY": "₺", "EUR": "€", "USD": "$"}.get(card.get("currency", "GBP"), "£")
    subject = f"🎁 {hotel} hediye çekiniz — {sym}{float(card.get('initial_amount', 0)):,.0f}"
    out = {}
    if card.get("recipient_email"):
        out["recipient"] = await send_email(db, card["recipient_email"], subject, html, kind="gift_card", meta={"card_id": card.get("id"), "property_id": card.get("property_id")})
    if card.get("purchaser_email") and card.get("purchaser_email") != card.get("recipient_email"):
        out["purchaser"] = await send_email(db, card["purchaser_email"], f"Satın alma onayı — {subject}", html, kind="gift_card_receipt", meta={"card_id": card.get("id"), "property_id": card.get("property_id")})
    if out:
        await db.gift_cards.update_one({"id": card["id"]}, {"$set": {"email_sent_at": datetime.now(timezone.utc).isoformat(), "email_result": out}})
    return out


def _gen_code(prefix: str = "MHB") -> str:
    """Readable code like MHB-XJ4F-R9K2-8N7P."""
    alphabet = string.ascii_uppercase + string.digits
    alphabet = alphabet.replace("O", "").replace("0", "").replace("I", "").replace("1", "").replace("L", "")
    return f"{prefix}-{''.join(secrets.choice(alphabet) for _ in range(4))}-{''.join(secrets.choice(alphabet) for _ in range(4))}-{''.join(secrets.choice(alphabet) for _ in range(4))}"


def create_gift_cards_router(db, require_roles):
    router = APIRouter()

    @router.get("/gift-cards")
    async def list_cards(property_id: str = "", status: str = "",
                         current_user: dict = Depends(require_roles("admin", "manager"))):
        q = {}
        if property_id:
            q["property_id"] = property_id
        if status:
            q["status"] = status
        rows = await db.gift_cards.find(q, {"_id": 0}).sort("created_at", -1).to_list(500)
        return rows

    @router.get("/gift-cards/summary/{property_id}")
    async def summary(property_id: str,
                      current_user: dict = Depends(require_roles("admin", "manager"))):
        """Totals for the Gift Card panel header: sold, outstanding, redeemed."""
        pq = {} if property_id == "all" else {"property_id": property_id}
        cards = await db.gift_cards.find(pq, {"_id": 0}).to_list(5000)
        total_sold = sum(float(c.get("initial_amount", 0)) for c in cards)
        total_outstanding = sum(float(c.get("balance", 0)) for c in cards if c.get("status") == "active")
        total_redeemed = total_sold - total_outstanding - sum(
            float(c.get("initial_amount", 0)) for c in cards if c.get("status") in ("expired", "cancelled")
        )
        counts = {
            "active": sum(1 for c in cards if c.get("status") == "active"),
            "redeemed": sum(1 for c in cards if c.get("status") == "redeemed"),
            "expired": sum(1 for c in cards if c.get("status") == "expired"),
            "cancelled": sum(1 for c in cards if c.get("status") == "cancelled"),
        }
        return {
            "total_sold": round(total_sold, 2),
            "total_outstanding": round(total_outstanding, 2),
            "total_redeemed": round(max(0.0, total_redeemed), 2),
            "counts": counts,
            "count": len(cards),
        }

    @router.post("/gift-cards")
    async def issue_card(data: Dict,
                         current_user: dict = Depends(require_roles("admin", "manager"))):
        """Issue a new gift card. Body: {property_id, amount, recipient_name, recipient_email, message, expires_days}"""
        amount = float(data.get("amount") or 0)
        if amount <= 0:
            raise HTTPException(status_code=400, detail="amount must be > 0")
        prop_id = data.get("property_id") or ""
        expires_days = int(data.get("expires_days") or 365)
        now = datetime.now(timezone.utc)
        card = {
            "id": str(uuid.uuid4()),
            "code": _gen_code(),
            "property_id": prop_id,
            "initial_amount": round(amount, 2),
            "balance": round(amount, 2),
            "currency": data.get("currency", "GBP"),
            "recipient_name": (data.get("recipient_name") or "").strip(),
            "recipient_email": (data.get("recipient_email") or "").strip(),
            "purchaser_name": (data.get("purchaser_name") or "").strip(),
            "message": (data.get("message") or "").strip(),
            "status": "active",
            "expires_at": (now + timedelta(days=expires_days)).isoformat(),
            "created_at": now.isoformat(),
            "created_by": current_user.get("name", ""),
            "redemption_log": [],
            "design": data.get("design") if data.get("design") in GIFT_DESIGNS else None,
        }
        await db.gift_cards.insert_one(card)
        card.pop("_id", None)
        if data.get("send_email", True) and (card["recipient_email"] or data.get("purchaser_email")):
            card["purchaser_email"] = (data.get("purchaser_email") or "").strip()
            card["email_result"] = await send_gift_card_emails(db, card, (data.get("origin_url") or "").rstrip("/"))
        return card

    @router.get("/gift-cards/designs")
    async def list_designs(_u: dict = Depends(require_roles("admin", "manager"))):
        return [{"id": k, **{kk: vv for kk, vv in v.items() if kk in ("name", "desc", "season")}} for k, v in GIFT_DESIGNS.items()]

    @router.get("/gift-cards/preview")
    async def preview_design(property_id: str, design: str = "classic", amount: float = 100, recipient_name: str = "Ayşe Yılmaz",
                             purchaser_name: str = "", message: str = "İyi ki varsın!", _u: dict = Depends(require_roles("admin", "manager"))):
        prop = await db.properties.find_one({"id": property_id}, {"_id": 0, "name": 1, "currency": 1}) or {}
        ts = await db.template_settings.find_one({"property_id": property_id}, {"_id": 0, "accent_color": 1, "primary_color": 1}) or {}
        card = {"code": "MHB-XXXX-XXXX-XXXX", "initial_amount": amount, "currency": prop.get("currency", "GBP"), "recipient_name": recipient_name,
                "purchaser_name": purchaser_name, "message": message, "expires_at": (datetime.now(timezone.utc) + timedelta(days=365)).isoformat()}
        html = gift_card_html(card, prop.get("name") or "Hotel", ts.get("accent_color") or ts.get("primary_color") or "#0f4c5c", "#", design)
        return Response(html, media_type="text/html")

    @router.post("/gift-cards/{card_id}/resend-email")
    async def resend_email(card_id: str, data: Dict = None,
                           current_user: dict = Depends(require_roles("admin", "manager"))):
        card = await db.gift_cards.find_one({"id": card_id}, {"_id": 0})
        if not card:
            raise HTTPException(status_code=404, detail="Card not found")
        if (data or {}).get("recipient_email"):
            card["recipient_email"] = data["recipient_email"].strip()
            await db.gift_cards.update_one({"id": card_id}, {"$set": {"recipient_email": card["recipient_email"]}})
        if (data or {}).get("design") in GIFT_DESIGNS:
            card["design"] = data["design"]
            await db.gift_cards.update_one({"id": card_id}, {"$set": {"design": card["design"]}})
        card.pop("email_sent_at", None)
        res = await send_gift_card_emails(db, card, ((data or {}).get("origin_url") or "").rstrip("/"))
        return {"ok": True, "result": res}

    @router.post("/gift-cards/{card_id}/redeem")
    async def redeem(card_id: str, data: Dict,
                     current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        """Redeem part/all of a card against a booking's folio.
        Body: {booking_id, amount, note}
        Creates a folio payment line with method='gift_card' and deducts from card balance.
        """
        card = await db.gift_cards.find_one({"id": card_id}, {"_id": 0})
        if not card:
            raise HTTPException(status_code=404, detail="Card not found")
        if card.get("status") != "active":
            raise HTTPException(status_code=409, detail=f"Card is {card.get('status')}")
        amount = float(data.get("amount") or 0)
        if amount <= 0 or amount > float(card.get("balance", 0)):
            raise HTTPException(status_code=400, detail=f"Invalid amount (balance {card.get('balance')})")

        booking_id = data.get("booking_id")
        if not booking_id:
            raise HTTPException(status_code=400, detail="booking_id required")
        booking = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found")

        # Create folio payment line
        now = datetime.now(timezone.utc).isoformat()
        item = {
            "id": str(uuid.uuid4()),
            "booking_id": booking_id,
            "type": "payment",
            "category": "gift_card",
            "payment_method": "gift_card",
            "description": f"Gift card {card.get('code')}",
            "quantity": 1,
            "unit_price": amount,
            "amount": amount,
            "currency": card.get("currency", "GBP"),
            "reference": card.get("code"),
            "created_at": now,
            "created_by": current_user.get("name", ""),
        }
        await db.folio_items.insert_one(item)

        new_balance = round(float(card.get("balance", 0)) - amount, 2)
        new_status = "redeemed" if new_balance <= 0.009 else "active"
        log_entry = {
            "at": now, "by": current_user.get("name", ""),
            "amount": amount, "booking_id": booking_id,
            "note": (data.get("note") or "").strip(),
        }
        await db.gift_cards.update_one(
            {"id": card_id},
            {"$set": {"balance": new_balance, "status": new_status},
             "$push": {"redemption_log": log_entry}}
        )
        return {"status": "ok", "redeemed": amount, "new_balance": new_balance, "card_status": new_status}

    @router.post("/gift-cards/{card_id}/cancel")
    async def cancel_card(card_id: str, data: Dict,
                          current_user: dict = Depends(require_roles("admin", "manager"))):
        await db.gift_cards.update_one({"id": card_id},
            {"$set": {"status": "cancelled", "cancelled_at": datetime.now(timezone.utc).isoformat(),
                      "cancel_reason": (data.get("reason") or "").strip(),
                      "cancelled_by": current_user.get("name", "")}})
        return {"status": "cancelled"}

    @router.get("/gift-cards/lookup/{code}")
    async def lookup(code: str,
                     current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        """Look up a card by its code (for the reception check-lookup flow)."""
        card = await db.gift_cards.find_one({"code": code.upper().strip()}, {"_id": 0})
        if not card:
            raise HTTPException(status_code=404, detail="Card not found")
        return card

    return router
