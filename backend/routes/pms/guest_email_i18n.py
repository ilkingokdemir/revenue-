"""Guest-facing booking confirmation e-mail in the guest's language (TR/EN/DE)."""
import uuid
from datetime import datetime, timezone

from routes.platform_ext.mailer import send_email

T = {
    "en": {"subject": "Booking confirmed · {ref} — {hotel}", "title": "Booking Confirmed", "thanks": "Thank you for your reservation, {name}",
           "ref": "Booking reference", "guest": "Guest", "room": "Room", "ci": "Check-in", "co": "Check-out", "nights": "Nights",
           "guests": "Guests", "adults": "adult(s)", "children": "child(ren)", "total": "Total", "paid": "Paid online", "pay_at": "Pay at the property",
           "requests": "Special requests", "cancel": "Free cancellation up to 48 hours before arrival.", "questions": "Questions? Simply reply to this e-mail.",
           "footer": "We look forward to welcoming you."},
    "tr": {"subject": "Rezervasyonunuz onaylandı · {ref} — {hotel}", "title": "Rezervasyon Onaylandı", "thanks": "Rezervasyonunuz için teşekkürler, {name}",
           "ref": "Rezervasyon numarası", "guest": "Misafir", "room": "Oda", "ci": "Giriş", "co": "Çıkış", "nights": "Gece",
           "guests": "Misafir sayısı", "adults": "yetişkin", "children": "çocuk", "total": "Toplam", "paid": "Online ödendi", "pay_at": "Otelde ödenecek",
           "requests": "Özel istekler", "cancel": "Girişten 48 saat öncesine kadar ücretsiz iptal.", "questions": "Sorunuz mu var? Bu e-postayı yanıtlamanız yeterli.",
           "footer": "Sizi ağırlamak için sabırsızlanıyoruz."},
    "de": {"subject": "Buchung bestätigt · {ref} — {hotel}", "title": "Buchung bestätigt", "thanks": "Vielen Dank für Ihre Reservierung, {name}",
           "ref": "Buchungsnummer", "guest": "Gast", "room": "Zimmer", "ci": "Anreise", "co": "Abreise", "nights": "Nächte",
           "guests": "Gäste", "adults": "Erwachsene", "children": "Kind(er)", "total": "Gesamt", "paid": "Online bezahlt", "pay_at": "Zahlung vor Ort",
           "requests": "Besondere Wünsche", "cancel": "Kostenlose Stornierung bis 48 Stunden vor Anreise.", "questions": "Fragen? Antworten Sie einfach auf diese E-Mail.",
           "footer": "Wir freuen uns, Sie begrüssen zu dürfen."},
}
LOCALE = {"en": "en_GB", "tr": "tr_TR", "de": "de_DE"}
MONTHS = {
    "en": ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"],
    "tr": ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"],
    "de": ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"],
}


def _fmt_date(iso: str, lang: str) -> str:
    try:
        d = datetime.strptime(iso[:10], "%Y-%m-%d")
        return f"{d.day} {MONTHS[lang][d.month - 1]} {d.year}"
    except Exception:
        return iso or ""


def build_confirmation(booking: dict, hotel_name: str, lang: str) -> tuple:
    lang = lang if lang in T else "en"
    t = T[lang]
    cur = booking.get("currency", "GBP")
    sym = {"GBP": "£", "EUR": "€", "USD": "$", "CHF": "CHF ", "TRY": "₺"}.get(cur, cur + " ")
    total = float(booking.get("total") or booking.get("total_price") or 0)
    paid = booking.get("payment_status") == "paid" or booking.get("pay_now")
    row = lambda k, v: f"<tr><td style='padding:8px 0;color:#666;font-size:14px'>{k}</td><td style='padding:8px 0;font-weight:600;font-size:14px;text-align:right'>{v}</td></tr>"
    guests = f"{booking.get('adults') or booking.get('guests') or 1} {t['adults']}"
    if int(booking.get("children") or 0) > 0:
        guests += f", {booking.get('children')} {t['children']}"
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;background:#fff">
      <div style="background:#1a3c5e;color:#fff;padding:24px;text-align:center">
        <h1 style="margin:0;font-size:24px">{t['title']}</h1>
        <p style="margin:8px 0 0;opacity:.85">{t['thanks'].format(name=booking.get('guest_name', ''))}</p>
      </div>
      <div style="padding:24px">
        <div style="background:#F5F7FA;border-radius:8px;padding:20px;text-align:center;margin-bottom:20px">
          <p style="margin:0;font-size:12px;color:#666;text-transform:uppercase;letter-spacing:1px">{t['ref']}</p>
          <p style="margin:8px 0 0;font-size:28px;font-weight:bold;color:#1a3c5e;letter-spacing:2px">{booking.get('booking_ref', '')}</p>
        </div>
        <table style="width:100%;border-collapse:collapse">
          {row(t['guest'], booking.get('guest_name', ''))}
          {row(t['room'], booking.get('room_type', ''))}
          {row(t['ci'], _fmt_date(booking.get('check_in', ''), lang))}
          {row(t['co'], _fmt_date(booking.get('check_out', ''), lang))}
          {row(t['nights'], booking.get('nights', ''))}
          {row(t['guests'], guests)}
          <tr style="border-top:2px solid #e5e7eb"><td style="padding:12px 0;font-weight:700;font-size:16px">{t['total']}</td>
          <td style="padding:12px 0;font-weight:700;font-size:20px;text-align:right">{sym}{total:,.2f}<div style="font-size:11px;font-weight:400;color:#666">{t['paid'] if paid else t['pay_at']}</div></td></tr>
        </table>
        {f"<div style='background:#F0FFF4;border:1px solid #C6F6D5;border-radius:8px;padding:12px;margin-top:16px;font-size:13px;color:#2F855A'>{t['requests']}: {booking.get('special_requests')}</div>" if booking.get('special_requests') else ''}
        <p style="margin-top:20px;font-size:13px;color:#444">{t['cancel']}</p>
        <div style="margin-top:24px;padding:16px;background:#F5F7FA;border-radius:8px;text-align:center;font-size:12px;color:#666">
          <p style="margin:0"><strong>{hotel_name}</strong> — {t['footer']}</p>
          <p style="margin:4px 0 0">{t['questions']}</p>
        </div>
      </div>
    </div>"""
    return t["subject"].format(ref=booking.get("booking_ref", ""), hotel=hotel_name), html


async def send_guest_confirmation(db, booking: dict) -> dict:
    """Sends (or MOCKs) the confirmation e-mail in booking.guest_lang; logs to booking_email_log."""
    lang = (booking.get("guest_lang") or "en")[:2].lower()
    prop = await db.properties.find_one({"id": booking.get("property_id")}, {"_id": 0, "name": 1}) or {}
    ts = await db.tenant_settings.find_one({"property_id": booking.get("property_id")}, {"_id": 0, "hotel_name": 1}) or {}
    hotel_name = ts.get("hotel_name") or prop.get("name") or "Hotel"
    subject, html = build_confirmation(booking, hotel_name, lang)
    status = await send_email(db, booking.get("guest_email", ""), subject, html, kind="booking_confirmation",
                              meta={"booking_id": booking.get("id"), "booking_ref": booking.get("booking_ref"), "lang": lang})
    await db.booking_email_log.insert_one({
        "id": str(uuid.uuid4()), "booking_id": booking.get("id"), "booking_ref": booking.get("booking_ref", ""),
        "to": booking.get("guest_email", ""), "subject": subject, "lang": lang, "type": "booking_confirmation",
        "status": status.upper(), "sent_at": datetime.now(timezone.utc).isoformat()})
    return {"status": status, "lang": lang, "subject": subject}
