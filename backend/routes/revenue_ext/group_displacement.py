"""
Group Displacement Analyzer — Duetto BlockBuster / Lybra paritesi.
Bir grup teklifi (tarih aralığı, oda sayısı, teklif fiyatı) için transient talebi
ne kadar yerinden edeceğini hesaplar ve kabul / pazarlık / red önerisi üretir.

Model (gece bazında):
- capacity = room_types.total_rooms toplamı
- booked   = o gece kesişen iptal-dışı rezervasyon odaları
- expected_pickup = geçmiş 8 aynı haftagünü ortalama doluluğa göre beklenen ek transient
- available_for_group = capacity - booked - expected_pickup
- displaced = max(0, istenen_oda - max(0, available_for_group))
- displacement_cost = displaced × transient ADR (o gecenin gerçek ADR'i, yoksa baz fiyat ort.)

Endpoints (/api/group-displacement/*):
- POST /analyze  → tam analiz + öneri (kaydeder)
- GET  /history/{property_id} → son analizler
"""
import uuid
from datetime import datetime, timedelta, timezone, date as ddate
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from auth import require_perm


def _build_proposal_pdf(a: dict, hotel_name: str, prepared_by: str) -> bytes:
    """Tek sayfalık şık grup teklif PDF'i (Türkçe karakter destekli)."""
    import io
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.colors import HexColor
    from reportlab.pdfgen import canvas
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    import os
    candidates = {
        "DVS": ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "/usr/share/fonts/truetype/freefont/FreeSans.ttf"],
        "DVSB": ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                 "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf"],
    }
    for fname, paths in candidates.items():
        if fname not in pdfmetrics.getRegisteredFontNames():
            for path in paths:
                if os.path.exists(path):
                    pdfmetrics.registerFont(TTFont(fname, path))
                    break

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    W, H = A4
    navy, gold, grey = HexColor("#1a3c5e"), HexColor("#b8860b"), HexColor("#6b7280")

    c.setFillColor(navy)
    c.rect(0, H - 110, W, 110, stroke=0, fill=1)
    c.setFillColor(HexColor("#ffffff"))
    c.setFont("DVSB", 20)
    c.drawString(40, H - 55, hotel_name)
    c.setFont("DVS", 12)
    c.drawString(40, H - 80, "GRUP KONAKLAMA TEKLİFİ")
    c.setFont("DVS", 9)
    c.drawRightString(W - 40, H - 80, datetime.now(timezone.utc).strftime("%d.%m.%Y"))

    y = H - 150
    c.setFillColor(navy)
    c.setFont("DVSB", 14)
    c.drawString(40, y, a.get("group_name") or "Grup Rezervasyonu")
    y -= 30
    c.setFont("DVS", 11)
    c.setFillColor(HexColor("#111827"))
    nights = a.get("nights", 0)
    rows = [
        ("Konaklama tarihleri", f"{a['check_in']}  →  {a['check_out']}  ({nights} gece)"),
        ("Oda sayısı", f"{a['rooms_requested']} oda / gece"),
        ("Gecelik oda fiyatı", f"{a['offered_rate']:.2f}"),
        ("Toplam konaklama bedeli", f"{a.get('total_group_revenue', 0):,.2f}"),
    ]
    for label, val in rows:
        c.setFillColor(grey)
        c.drawString(40, y, label)
        c.setFillColor(HexColor("#111827"))
        c.setFont("DVSB", 11)
        c.drawString(240, y, str(val))
        c.setFont("DVS", 11)
        y -= 22

    y -= 12
    c.setFillColor(HexColor("#f3f4f6"))
    c.roundRect(40, y - 96, W - 80, 96, 8, stroke=0, fill=1)
    c.setFillColor(navy)
    c.setFont("DVSB", 11)
    c.drawString(52, y - 22, "Gelir Yönetimi Değerlendirmesi")
    c.setFont("DVS", 9.5)
    c.setFillColor(HexColor("#374151"))
    verdict_tr = {"accept": "UYGUN — teklif kabul edilebilir",
                  "negotiate": "PAZARLIK — fiyat iyileştirmesi önerilir",
                  "reject": "UYGUN DEĞİL — mevcut fiyatla önerilmez"}.get(a.get("recommendation"), "-")
    lines = [
        f"Karar: {verdict_tr}",
        f"Yerinden edilen bireysel talep: {a.get('total_displaced_rooms', 0)} oda-gece "
        f"(maliyet {a.get('total_displacement_cost', 0):,.2f}, shoulder kaybı {a.get('shoulder_loss', 0):,.2f})",
        f"Komisyon sonrası net katkı: {a.get('net_value_after_commission', a.get('net_value', 0)):,.2f}",
        f"Başabaş gecelik fiyat (net): {a.get('breakeven_rate_net', a.get('breakeven_rate', 0)):,.2f}",
    ]
    ly = y - 40
    for ln in lines:
        c.drawString(52, ly, ln)
        ly -= 15

    y -= 130
    c.setFillColor(gold)
    c.roundRect(40, y - 60, W - 80, 60, 8, stroke=0, fill=1)
    c.setFillColor(HexColor("#ffffff"))
    c.setFont("DVSB", 12)
    c.drawString(52, y - 25, "Önerilen minimum gecelik fiyat")
    c.setFont("DVSB", 20)
    c.drawRightString(W - 52, y - 32, f"{a.get('suggested_min_rate_net', a.get('suggested_min_rate', 0)):,.2f}")
    c.setFont("DVS", 8)
    c.drawString(52, y - 45, "Fiyata vergiler dahildir. Kahvaltı ve toplantı salonu ihtiyaçları ayrıca fiyatlandırılır.")

    c.setFillColor(grey)
    c.setFont("DVS", 8)
    c.drawString(40, 60, f"Bu teklif {(datetime.now(timezone.utc) + timedelta(days=14)).strftime('%d.%m.%Y')} tarihine kadar geçerlidir ve müsaitlik teyidine tabidir.")
    c.drawString(40, 46, f"Hazırlayan: {prepared_by or 'Revenue Ekibi'} · {hotel_name} Grup Satış")
    c.setFillColor(navy)
    c.rect(0, 0, W, 24, stroke=0, fill=1)
    c.showPage()
    c.save()
    return buf.getvalue()


class AnalyzeIn(BaseModel):
    property_id: str
    check_in: str          # YYYY-MM-DD
    check_out: str
    rooms_requested: int
    offered_rate: float    # gecelik oda fiyatı
    group_name: Optional[str] = ""


def _d(s):
    return datetime.strptime(s[:10], "%Y-%m-%d").date()


async def _capacity(db, pid: str) -> int:
    total = 0
    async for rt in db.room_types.find({"property_id": pid}, {"_id": 0, "total_rooms": 1}):
        total += int(rt.get("total_rooms", 0) or 0)
    return max(total, 1)


async def _bookings(db, pid: str, start: ddate, end: ddate):
    return await db.bookings.find(
        {"property_id": pid, "status": {"$ne": "cancelled"},
         "check_in": {"$lt": (end + timedelta(days=1)).isoformat()},
         "check_out": {"$gt": (start - timedelta(days=60)).isoformat()}},
        {"_id": 0, "check_in": 1, "check_out": 1, "rooms": 1, "total_price": 1, "source": 1}
    ).to_list(20000)


def _commission_for(src: str) -> float:
    s = (src or "").lower()
    if "booking" in s:
        return 0.15
    if "expedia" in s:
        return 0.18
    if "airbnb" in s:
        return 0.03
    if "agoda" in s:
        return 0.17
    if "trip" in s:
        return 0.15
    return 0.0


def _rooms_on(bookings, night: ddate) -> int:
    n = 0
    iso = night.isoformat()
    for b in bookings:
        if (b.get("check_in") or "9999") <= iso < (b.get("check_out") or "0000"):
            n += int(b.get("rooms", 1) or 1)
    return n


def _adr_on(bookings, night: ddate, fallback: float) -> float:
    iso = night.isoformat()
    rates = []
    for b in bookings:
        ci, co = b.get("check_in"), b.get("check_out")
        if not ci or not co or not (ci <= iso < co):
            continue
        try:
            nights = max((_d(co) - _d(ci)).days, 1)
            rooms = int(b.get("rooms", 1) or 1)
            rates.append(float(b.get("total_price", 0) or 0) / nights / rooms)
        except (ValueError, ZeroDivisionError):
            continue
    rates = [r for r in rates if r > 0]
    return round(sum(rates) / len(rates), 2) if rates else fallback


async def compute_displacement(db, pid: str, start: ddate, end: ddate, rooms_requested: int, offered_rate: float):
    """Modül seviyesi: AI Auto-Quote gibi diğer modüller de kullanır."""
    capacity = await _capacity(db, pid)
    bookings = await _bookings(db, pid, start, end)
    base_prices = [float(rt.get("base_price", 0) or 0)
                   async for rt in db.room_types.find({"property_id": pid},
                                                      {"_id": 0, "base_price": 1})]
    base_prices = [p for p in base_prices if p > 0]
    fallback_adr = round(sum(base_prices) / len(base_prices), 2) if base_prices else 100.0

    nights = []
    total_displaced, total_disp_cost, total_group_rev = 0, 0.0, 0.0
    night = start
    while night < end:
        booked = _rooms_on(bookings, night)
        hist_occs = []
        for k in range(1, 9):
            past = night - timedelta(weeks=k)
            if past >= ddate.today():
                continue
            hist_occs.append(min(_rooms_on(bookings, past) / capacity, 1.0))
        hist_occ = sum(hist_occs) / len(hist_occs) if hist_occs else 0.5
        expected_final = max(booked, int(round(hist_occ * capacity)))
        expected_pickup = max(0, expected_final - booked)
        available = capacity - booked - expected_pickup
        displaced = max(0, rooms_requested - max(0, available))
        adr = _adr_on(bookings, night, fallback_adr)
        disp_cost = round(displaced * adr, 2)
        group_rev = round(rooms_requested * offered_rate, 2)
        nights.append({
            "date": night.isoformat(), "capacity": capacity, "booked": booked,
            "expected_pickup": expected_pickup, "available_for_group": max(0, available),
            "displaced_rooms": displaced, "transient_adr": adr,
            "displacement_cost": disp_cost, "group_revenue": group_rev,
            "net_value": round(group_rev - disp_cost, 2),
        })
        total_displaced += displaced
        total_disp_cost += disp_cost
        total_group_rev += group_rev
        night += timedelta(days=1)

    n_nights = len(nights)
    net_total = round(total_group_rev - total_disp_cost, 2)
    breakeven_rate = round(total_disp_cost / (rooms_requested * n_nights), 2) if n_nights else 0
    suggested_rate = round(max(breakeven_rate * 1.1, offered_rate), 2)

    # --- İkincil (shoulder-night) displacement + komisyon-sonrası net katkı ---
    los_list, src_counts = [], {}
    for b in bookings:
        try:
            los_list.append(max((_d(b["check_out"]) - _d(b["check_in"])).days, 1))
        except (ValueError, KeyError, TypeError):
            pass
        s = (b.get("source") or "direct").lower()
        src_counts[s] = src_counts.get(s, 0) + 1
    avg_los = round(sum(los_list) / len(los_list), 1) if los_list else 1.5
    tot_src = sum(src_counts.values()) or 1
    avg_comm = round(sum(_commission_for(s) * c for s, c in src_counts.items()) / tot_src, 4)

    disp_first = nights[0]["displaced_rooms"] if nights else 0
    disp_last = nights[-1]["displaced_rooms"] if nights else 0
    # Yerinden edilen kenar misafirleri ort. LOS kadar kalırdı → grup penceresi
    # dışına taşan geceler shoulder kaybı (misafir başına max 2 ek gece).
    edge_extra_nights = max(0.0, min((avg_los - 1) / 2.0, 2.0))
    shoulder_loss = round((disp_first + disp_last) * edge_extra_nights * fallback_adr, 2)

    gross_loss = total_disp_cost + shoulder_loss
    net_displacement_cost = round(gross_loss * (1 - avg_comm), 2)
    net_value_after_commission = round(total_group_rev - net_displacement_cost, 2)
    breakeven_rate_net = round(net_displacement_cost / (rooms_requested * n_nights), 2) if n_nights else 0
    suggested_min_rate_net = round(max(breakeven_rate_net * 1.1, offered_rate), 2)

    if total_displaced == 0 and shoulder_loss == 0:
        recommendation, reason = "accept", "Hiç transient talep yerinden edilmiyor — grup net katkı sağlıyor."
    elif net_value_after_commission > 0 and net_displacement_cost / max(total_group_rev, 1) < 0.35:
        recommendation, reason = "accept", (
            f"Komisyon sonrası net displacement maliyeti (shoulder dahil) grup gelirinin %35'inin altında — kabul edilebilir.")
    elif net_value_after_commission > 0:
        recommendation, reason = "negotiate", (
            f"Net pozitif ama displacement + shoulder kaybı yüksek. Önerilen min fiyat (net): {suggested_min_rate_net}.")
    else:
        recommendation, reason = "reject", (
            f"Grup geliri komisyon-sonrası displacement maliyetini karşılamıyor. En az {suggested_min_rate_net} istenmeli.")

    return {
        "nights": n_nights, "fallback_adr": fallback_adr,
        "total_group_revenue": round(total_group_rev, 2),
        "total_displaced_rooms": total_displaced,
        "total_displacement_cost": round(total_disp_cost, 2),
        "net_value": net_total, "breakeven_rate": breakeven_rate,
        "suggested_min_rate": suggested_rate,
        "avg_transient_los": avg_los,
        "avg_commission_pct": avg_comm,
        "shoulder_loss": shoulder_loss,
        "shoulder_edge_nights": edge_extra_nights,
        "net_displacement_cost": net_displacement_cost,
        "net_value_after_commission": net_value_after_commission,
        "breakeven_rate_net": breakeven_rate_net,
        "suggested_min_rate_net": suggested_min_rate_net,
        "recommendation": recommendation, "reason": reason,
        "per_night": nights,
    }


def create_group_displacement_router(db):
    router = APIRouter(prefix="/group-displacement")

    @router.post("/analyze")
    async def analyze(body: AnalyzeIn,
                      current_user: dict = Depends(require_perm("view_bookings", "edit_bookings", mode="any"))):
        try:
            start, end = _d(body.check_in), _d(body.check_out)
        except ValueError:
            raise HTTPException(400, "Dates must be YYYY-MM-DD")
        if end <= start:
            raise HTTPException(400, "check_out must be after check_in")
        if (end - start).days > 30:
            raise HTTPException(400, "Max 30 nights")
        if body.rooms_requested < 1:
            raise HTTPException(400, "rooms_requested must be >= 1")

        computed = await compute_displacement(db, body.property_id, start, end, body.rooms_requested, body.offered_rate)
        result = {
            "id": str(uuid.uuid4()), "property_id": body.property_id,
            "group_name": body.group_name or "", "check_in": body.check_in,
            "check_out": body.check_out,
            "rooms_requested": body.rooms_requested, "offered_rate": body.offered_rate,
            **computed,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": current_user.get("email", ""),
        }
        await db.group_displacement_analyses.insert_one(dict(result))
        result.pop("_id", None)
        return result

    @router.post("/proposal-pdf/{analysis_id}")
    async def proposal_pdf(analysis_id: str,
                           current_user: dict = Depends(require_perm("view_bookings", "edit_bookings", mode="any"))):
        """Displacement analizinden tek sayfalık grup teklif PDF'i üretir."""
        a = await db.group_displacement_analyses.find_one({"id": analysis_id}, {"_id": 0})
        if not a:
            raise HTTPException(404, "Analiz bulunamadı")
        prop = await db.properties.find_one({"id": a["property_id"]}, {"_id": 0, "name": 1}) or {}
        hotel_name = prop.get("name") or "Otel"
        pdf = _build_proposal_pdf(a, hotel_name, current_user.get("email", ""))
        fname = f"grup-teklif-{(a.get('group_name') or 'grup').replace(' ', '-')[:30]}.pdf"
        return Response(content=pdf, media_type="application/pdf",
                        headers={"Content-Disposition": f'attachment; filename="{fname}"'})

    @router.get("/verdicts/{property_id}")
    async def verdicts(property_id: str,
                       current_user: dict = Depends(require_perm("view_bookings", "edit_bookings", mode="any"))):
        """Bekleyen grup talepleri için hızlı displacement kararları (liste rozetleri)."""
        requests = await db.group_bookings.find(
            {"property_id": property_id, "status": {"$in": ["pending", "quoted", None]}},
            {"_id": 0, "id": 1, "check_in": 1, "check_out": 1, "total_rooms": 1, "quoted_price": 1}
        ).to_list(100)
        out = {}
        for r in requests:
            try:
                start, end = _d(r["check_in"]), _d(r["check_out"])
                n_nights = (end - start).days
                rooms = int(r.get("total_rooms", 1) or 1)
                if n_nights < 1 or n_nights > 30 or rooms < 1:
                    continue
                quoted = float(r.get("quoted_price", 0) or 0)
                if quoted > 0:
                    rate, estimated = round(quoted / (rooms * n_nights), 2), False
                else:
                    rate, estimated = None, True
                computed = await compute_displacement(db, property_id, start, end, rooms, rate if rate else 0)
                if estimated:
                    rate = round(computed["fallback_adr"] * 0.8, 2)
                    computed = await compute_displacement(db, property_id, start, end, rooms, rate)
                out[r["id"]] = {
                    "recommendation": computed["recommendation"],
                    "net_value": computed["net_value"],
                    "displaced_rooms": computed["total_displaced_rooms"],
                    "suggested_min_rate": computed["suggested_min_rate"],
                    "assumed_rate": rate, "rate_estimated": estimated,
                    "reason": computed["reason"],
                }
            except (ValueError, KeyError, TypeError):
                continue
        return out

    @router.get("/history/{property_id}")
    async def history(property_id: str, limit: int = 10,
                      current_user: dict = Depends(require_perm("view_bookings", "edit_bookings", mode="any"))):
        return await db.group_displacement_analyses.find(
            {"property_id": property_id}, {"_id": 0, "per_night": 0}
        ).sort("created_at", -1).to_list(min(limit, 50))

    return router
