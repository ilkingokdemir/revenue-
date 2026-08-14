"""
Group Sales OS (lite) — "Üç bağımsız rapor" orta vade önceliği.
RFP yaşam döngüsü + wash/attrition + comp oda + teklif versiyonlama;
her teklif versiyonu shoulder-night'lı displacement analiziyle fiyatlanır
ve mevcut tek sayfalık teklif PDF'i (proposal-pdf) ile paylaşılabilir.

Collections: group_rfps {id, property_id, group_name, contact_name, contact_email,
  check_in, check_out, rooms, offered_rate, wash_pct, comp_rooms, notes,
  status: new|quoted|negotiating|won|lost, versions[], created_at}

Endpoints (/api/group-sales/*):
- GET  /{property_id}                 → RFP listesi + pipeline özeti
- POST /{property_id}/rfp             → RFP oluştur
- PUT  /rfp/{rfp_id}                  → alan/statü güncelle
- POST /rfp/{rfp_id}/quote            → yeni teklif versiyonu (displacement + PDF analiz id'si)
"""
import base64
import logging
import math
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict

from fastapi import APIRouter, Depends, HTTPException

from routes.revenue_ext.group_displacement import compute_displacement, _d, _build_proposal_pdf

try:
    import resend
except ImportError:
    resend = None

logger = logging.getLogger(__name__)
STATUSES = ("new", "quoted", "negotiating", "won", "lost")
ALT_OFFSETS = (-14, -10, -7, -5, -3, 3, 5, 7, 10, 14, 17, 21)


async def _send_email_pdf(to_email: str, subject: str, html: str,
                          pdf_bytes: bytes, filename: str) -> str:
    api_key = os.environ.get("RESEND_API_KEY", "")
    if not resend or not api_key or api_key.startswith("re_1234"):
        logger.info(f"[MOCK EMAIL] Group proposal to {to_email}: {subject} (+{filename}, {len(pdf_bytes)}b)")
        return "mock"
    try:
        resend.api_key = api_key
        resend.Emails.send({
            "from": os.environ.get("RESEND_FROM", "MyHotelBox <onboarding@resend.dev>"),
            "to": [to_email], "subject": subject, "html": html,
            "attachments": [{"filename": filename,
                             "content": base64.b64encode(pdf_bytes).decode()}],
        })
        return "sent"
    except Exception as e:
        logger.warning(f"Group proposal email failed: {e}")
        return "failed"


async def _find_alternative_dates(db, pid: str, check_in: str, check_out: str,
                                  rooms: int, rate: float, current_net: float):
    """Aynı uzunlukta kaydırılmış pencereleri tarar, en yüksek net katkılı 3 tarihi döner."""
    start, end = _d(check_in), _d(check_out)
    nights = (end - start).days
    min_start = datetime.now(timezone.utc).date() + timedelta(days=3)
    results = []
    for off in ALT_OFFSETS:
        s = start + timedelta(days=off)
        if s < min_start:
            continue
        e = s + timedelta(days=nights)
        try:
            c = await compute_displacement(db, pid, s, e, rooms, rate)
        except Exception:
            continue
        results.append({
            "check_in": s.isoformat(), "check_out": e.isoformat(), "offset_days": off,
            "net_value_after_commission": c["net_value_after_commission"],
            "total_displaced_rooms": c["total_displaced_rooms"],
            "recommendation": c["recommendation"],
            "gain_vs_current": round(c["net_value_after_commission"] - current_net, 2),
        })
    results.sort(key=lambda x: -x["net_value_after_commission"])
    return [r for r in results if r["gain_vs_current"] > 0][:3]


def create_group_sales_router(db, require_roles):
    router = APIRouter(prefix="/group-sales", tags=["group-sales"])

    @router.get("/{property_id}")
    async def list_rfps(property_id: str,
                        _: dict = Depends(require_roles("admin", "manager"))):
        rfps = await db.group_rfps.find(
            {"property_id": property_id}, {"_id": 0}).sort("created_at", -1).to_list(100)
        by_status = {s: 0 for s in STATUSES}
        potential, won_rev = 0.0, 0.0
        for r in rfps:
            by_status[r.get("status", "new")] = by_status.get(r.get("status", "new"), 0) + 1
            v = (r.get("versions") or [{}])[-1]
            rev = float(v.get("adj_group_revenue", 0) or 0)
            if r.get("status") == "won":
                won_rev += rev
            elif r.get("status") not in ("lost",):
                potential += rev
        closed = by_status["won"] + by_status["lost"]
        return {"rfps": rfps, "pipeline": {
            "by_status": by_status, "potential_revenue": round(potential, 2),
            "won_revenue": round(won_rev, 2),
            "conversion_pct": round(by_status["won"] / closed * 100, 1) if closed else 0}}

    @router.post("/{property_id}/rfp")
    async def create_rfp(property_id: str, body: Dict,
                         user: dict = Depends(require_roles("admin", "manager"))):
        try:
            start, end = _d(body["check_in"]), _d(body["check_out"])
            rooms = int(body["rooms"])
            rate = float(body["offered_rate"])
        except (KeyError, ValueError, TypeError):
            raise HTTPException(400, "check_in, check_out, rooms, offered_rate gerekli")
        if end <= start or rooms < 1 or rate < 0:
            raise HTTPException(400, "Geçersiz tarih/oda/fiyat")
        doc = {
            "id": str(uuid.uuid4()), "property_id": property_id,
            "group_name": (body.get("group_name") or "İsimsiz Grup").strip(),
            "contact_name": body.get("contact_name", ""), "contact_email": body.get("contact_email", ""),
            "check_in": body["check_in"], "check_out": body["check_out"],
            "rooms": rooms, "offered_rate": rate,
            "wash_pct": max(0.0, min(float(body.get("wash_pct", 10) or 0), 60)),
            "comp_rooms": max(0, int(body.get("comp_rooms", 0) or 0)),
            "rebate_pct": max(0.0, min(float(body.get("rebate_pct", 0) or 0), 20)),
            "fb_contribution": max(0.0, float(body.get("fb_contribution", 0) or 0)),
            "pattern": [int(p) for p in (body.get("pattern") or []) if str(p).isdigit()][:31],
            "notes": body.get("notes", ""), "status": "new", "versions": [],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": user.get("email", ""),
        }
        await db.group_rfps.insert_one(dict(doc))
        return {"ok": True, "rfp": doc}

    @router.put("/rfp/{rfp_id}")
    async def update_rfp(rfp_id: str, body: Dict,
                         _: dict = Depends(require_roles("admin", "manager"))):
        upd = {}
        for f in ("group_name", "contact_name", "contact_email", "notes"):
            if f in body:
                upd[f] = body[f]
        if "status" in body:
            if body["status"] not in STATUSES:
                raise HTTPException(400, f"status şunlardan biri olmalı: {STATUSES}")
            upd["status"] = body["status"]
        for f in ("rooms", "comp_rooms"):
            if f in body:
                upd[f] = max(0, int(body[f] or 0))
        for f in ("offered_rate", "wash_pct"):
            if f in body:
                upd[f] = max(0.0, float(body[f] or 0))
        if not upd:
            raise HTTPException(400, "Güncellenecek alan yok")
        upd["updated_at"] = datetime.now(timezone.utc).isoformat()
        rfp = await db.group_rfps.find_one({"id": rfp_id}, {"_id": 0})
        if not rfp:
            raise HTTPException(404, "RFP bulunamadı")
        await db.group_rfps.update_one({"id": rfp_id}, {"$set": upd})

        # KAZANILAN RFP → takvime grup bloğu düşür / kaybedilirse bloğu iptal et
        block_info = None
        new_status = upd.get("status")
        if new_status == "won" and not rfp.get("block_booking_id"):
            last = (rfp.get("versions") or [{}])[-1]
            rooms_block = int(last.get("expected_rooms") or rfp.get("rooms", 1))
            nights = max((_d(rfp["check_out"]) - _d(rfp["check_in"])).days, 1)
            rate = float(last.get("offered_rate", rfp.get("offered_rate", 0)) or 0)
            booking = {
                "id": str(uuid.uuid4()),
                "booking_ref": f"GRP-{uuid.uuid4().hex[:8].upper()}",
                "property_id": rfp["property_id"],
                "guest_name": f"GRUP BLOĞU: {rfp['group_name']}",
                "guest_email": rfp.get("contact_email", ""),
                "room_type": "Group Block",
                "check_in": rfp["check_in"], "check_out": rfp["check_out"],
                "rooms": rooms_block, "guests": rooms_block,
                "rate": rate,
                "total_price": float(last.get("adj_group_revenue") or rooms_block * rate * nights),
                "status": "confirmed", "source": "group_sales",
                "group_rfp_id": rfp_id,
                "special_requests": f"Group Sales OS — RFP kazanıldı (v{last.get('v', '?')})",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            await db.bookings.insert_one(dict(booking))
            await db.group_rfps.update_one(
                {"id": rfp_id}, {"$set": {"block_booking_id": booking["id"],
                                          "block_booking_ref": booking["booking_ref"]}})
            block_info = {"action": "created", "booking_ref": booking["booking_ref"],
                          "rooms": rooms_block}
        elif new_status in ("lost", "new", "quoted", "negotiating") and rfp.get("block_booking_id") \
                and rfp.get("status") == "won":
            await db.bookings.update_one(
                {"id": rfp["block_booking_id"]},
                {"$set": {"status": "cancelled",
                          "cancelled_at": datetime.now(timezone.utc).isoformat()}})
            await db.group_rfps.update_one(
                {"id": rfp_id}, {"$unset": {"block_booking_id": "", "block_booking_ref": ""}})
            block_info = {"action": "released"}
        return {"ok": True, "block": block_info}

    @router.post("/rfp/{rfp_id}/quote")
    async def quote(rfp_id: str, body: Dict,
                    user: dict = Depends(require_roles("admin", "manager"))):
        rfp = await db.group_rfps.find_one({"id": rfp_id}, {"_id": 0})
        if not rfp:
            raise HTTPException(404, "RFP bulunamadı")
        rate = float(body.get("offered_rate", rfp["offered_rate"]) or rfp["offered_rate"])
        wash = max(0.0, min(float(body.get("wash_pct", rfp.get("wash_pct", 10)) or 0), 60))
        comp = max(0, int(body.get("comp_rooms", rfp.get("comp_rooms", 0)) or 0))
        rebate = max(0.0, min(float(body.get("rebate_pct", rfp.get("rebate_pct", 0)) or 0), 20))
        fb = max(0.0, float(body.get("fb_contribution", rfp.get("fb_contribution", 0)) or 0))
        pattern = body.get("pattern") or rfp.get("pattern") or []
        rooms = int(rfp["rooms"])
        start, end = _d(rfp["check_in"]), _d(rfp["check_out"])
        nights = (end - start).days

        if isinstance(pattern, list) and len(pattern) == nights and all(
                isinstance(p, (int, float)) and p >= 0 for p in pattern):
            # patterned block: gün gün değişen oda adedi
            room_nights = sum(int(p) for p in pattern)
            expected_rooms = max(1, math.ceil(max(int(p) for p in pattern) * (1 - wash / 100)))
            paying_room_nights = max(0, math.ceil(room_nights * (1 - wash / 100)) - comp * nights)
            adj_revenue = round(paying_room_nights * rate * (1 - rebate / 100) + fb, 2)
        else:
            pattern = []
            expected_rooms = max(1, math.ceil(rooms * (1 - wash / 100)))
            paying_rooms = max(0, expected_rooms - comp)
            adj_revenue = round(paying_rooms * rate * nights * (1 - rebate / 100) + fb, 2)

        computed = await compute_displacement(db, rfp["property_id"], start, end, expected_rooms, rate)
        # comp odalar ve wash sonrası GERÇEK grup geliri üzerinden net değer
        real_net = round(adj_revenue - computed["net_displacement_cost"], 2)

        analysis = {
            "id": str(uuid.uuid4()), "property_id": rfp["property_id"],
            "group_name": rfp["group_name"], "check_in": rfp["check_in"], "check_out": rfp["check_out"],
            "rooms_requested": expected_rooms, "offered_rate": rate,
            **computed, "total_group_revenue": adj_revenue,
            "net_value_after_commission": real_net,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": user.get("email", ""),
        }
        await db.group_displacement_analyses.insert_one(dict(analysis))

        version = {
            "v": len(rfp.get("versions") or []) + 1,
            "offered_rate": rate, "rooms": rooms, "expected_rooms": expected_rooms,
            "wash_pct": wash, "comp_rooms": comp, "nights": nights,
            "rebate_pct": rebate, "fb_contribution": fb,
            "pattern": pattern,
            "adj_group_revenue": adj_revenue,
            "recommendation": computed["recommendation"],
            "net_value_after_commission": real_net,
            "breakeven_rate_net": computed["breakeven_rate_net"],
            "suggested_min_rate_net": computed["suggested_min_rate_net"],
            "shoulder_loss": computed["shoulder_loss"],
            "analysis_id": analysis["id"],
            "note": body.get("note", ""),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": user.get("email", ""),
        }
        await db.group_rfps.update_one(
            {"id": rfp_id},
            {"$push": {"versions": version},
             "$set": {"status": "quoted" if rfp.get("status") == "new" else rfp.get("status"),
                      "offered_rate": rate, "wash_pct": wash, "comp_rooms": comp,
                      "rebate_pct": rebate, "fb_contribution": fb, "pattern": pattern,
                      "updated_at": datetime.now(timezone.utc).isoformat()}})

        # RED çıkarsa satış ekibine otomatik alternatif tarih önerisi
        alternatives = []
        if computed["recommendation"] == "reject":
            alternatives = await _find_alternative_dates(
                db, rfp["property_id"], rfp["check_in"], rfp["check_out"],
                expected_rooms, rate, real_net)
        return {"ok": True, "version": version, "alternatives": alternatives}

    @router.post("/rfp/{rfp_id}/reschedule")
    async def reschedule(rfp_id: str, body: Dict,
                         user: dict = Depends(require_roles("admin", "manager"))):
        """Alternatif tarih önerisini tek tıkla uygular: tarihleri taşır + otomatik yeniden fiyatlar."""
        rfp = await db.group_rfps.find_one({"id": rfp_id}, {"_id": 0})
        if not rfp:
            raise HTTPException(404, "RFP bulunamadı")
        try:
            s, e = _d(body["check_in"]), _d(body["check_out"])
        except (KeyError, ValueError, TypeError):
            raise HTTPException(400, "check_in ve check_out gerekli")
        if e <= s:
            raise HTTPException(400, "Geçersiz tarih aralığı")
        old = f"{rfp['check_in']} → {rfp['check_out']}"
        await db.group_rfps.update_one(
            {"id": rfp_id},
            {"$set": {"check_in": s.isoformat(), "check_out": e.isoformat(),
                      "updated_at": datetime.now(timezone.utc).isoformat()},
             "$push": {"reschedule_log": {"from": old, "to": f"{s.isoformat()} → {e.isoformat()}",
                                          "at": datetime.now(timezone.utc).isoformat(),
                                          "by": user.get("email", "")}}})
        result = await quote(rfp_id, {"note": f"Tarih kaydırma: {old} yerine"}, user)
        return {**result, "rescheduled": {"from": old, "to": f"{s.isoformat()} → {e.isoformat()}"}}

    @router.post("/rfp/{rfp_id}/alternatives")
    async def alternatives(rfp_id: str,
                           _: dict = Depends(require_roles("admin", "manager"))):
        rfp = await db.group_rfps.find_one({"id": rfp_id}, {"_id": 0})
        if not rfp:
            raise HTTPException(404, "RFP bulunamadı")
        last = (rfp.get("versions") or [{}])[-1]
        rate = float(last.get("offered_rate", rfp["offered_rate"]) or rfp["offered_rate"])
        expected = int(last.get("expected_rooms") or rfp["rooms"])
        current_net = float(last.get("net_value_after_commission", 0) or 0)
        alts = await _find_alternative_dates(
            db, rfp["property_id"], rfp["check_in"], rfp["check_out"], expected, rate, current_net)
        return {"ok": True, "current_net": current_net, "alternatives": alts}

    @router.post("/rfp/{rfp_id}/email")
    async def email_proposal(rfp_id: str, body: Dict,
                             user: dict = Depends(require_roles("admin", "manager"))):
        rfp = await db.group_rfps.find_one({"id": rfp_id}, {"_id": 0})
        if not rfp:
            raise HTTPException(404, "RFP bulunamadı")
        versions = rfp.get("versions") or []
        if not versions:
            raise HTTPException(400, "Önce teklif oluşturun (Fiyatla)")
        to = (body.get("to") or rfp.get("contact_email") or "").strip()
        if not to or "@" not in to:
            raise HTTPException(400, "Geçerli bir alıcı e-postası yok — RFP'ye iletişim e-postası ekleyin")
        last = versions[-1]
        a = await db.group_displacement_analyses.find_one({"id": last.get("analysis_id")}, {"_id": 0})
        if not a:
            raise HTTPException(404, "Teklif analizi bulunamadı")
        prop = await db.properties.find_one({"id": rfp["property_id"]}, {"_id": 0, "name": 1}) or {}
        hotel = prop.get("name") or "Otel"
        pdf = _build_proposal_pdf(a, hotel, user.get("email", ""))
        html = f"""
        <div style="font-family:Arial,sans-serif;max-width:560px;margin:auto;padding:24px;">
          <h2 style="color:#1a3c5e;">{hotel} — Grup Konaklama Teklifi</h2>
          <p>Sayın {rfp.get('contact_name') or 'Yetkili'},</p>
          <p><b>{rfp['group_name']}</b> için {rfp['check_in']} – {rfp['check_out']} tarihlerinde
          {rfp['rooms']} odalık grup konaklama teklifimiz ekte yer almaktadır.</p>
          <p>Gecelik oda fiyatı: <b>{last['offered_rate']:.2f}</b> (teklif v{last['v']})</p>
          <p style="font-size:12px;color:#78716c;">Teklif 14 gün geçerlidir ve müsaitlik teyidine tabidir.</p>
          <p>Saygılarımızla,<br/>{hotel} Grup Satış Ekibi</p>
        </div>"""
        fname = f"grup-teklif-{rfp['group_name'].replace(' ', '-')[:30]}.pdf"
        status = await _send_email_pdf(to, f"{hotel} — Grup Teklifi: {rfp['group_name']}", html, pdf, fname)
        log = {"to": to, "version": last["v"], "status": status,
               "sent_at": datetime.now(timezone.utc).isoformat(), "by": user.get("email", "")}
        await db.group_rfps.update_one({"id": rfp_id}, {"$push": {"emails_sent": log}})
        return {"ok": True, "status": status, "to": to,
                "note": "Resend anahtarı mock olduğu için e-posta simüle edildi" if status == "mock" else ""}

    @router.post("/rfp/{rfp_id}/rooming")
    async def add_rooming(rfp_id: str, body: Dict,
                          user: dict = Depends(require_roles("admin", "manager"))):
        """Grup bloğuna isimli misafir (rooming list) ekler."""
        rfp = await db.group_rfps.find_one({"id": rfp_id}, {"_id": 0, "status": 1})
        if not rfp:
            raise HTTPException(404, "RFP bulunamadı")
        if rfp.get("status") != "won":
            raise HTTPException(400, "Rooming list sadece kazanılmış RFP'lere eklenir")
        name = (body.get("guest_name") or "").strip()
        if not name:
            raise HTTPException(400, "guest_name gerekli")
        entry = {"id": str(uuid.uuid4()), "guest_name": name,
                 "guest_email": (body.get("guest_email") or "").strip(),
                 "rooms": max(1, int(body.get("rooms", 1) or 1)),
                 "added_at": datetime.now(timezone.utc).isoformat(),
                 "added_by": user.get("email", "")}
        await db.group_rfps.update_one({"id": rfp_id}, {"$push": {"rooming_list": entry}})
        return {"ok": True, "entry": entry}

    @router.delete("/rfp/{rfp_id}/rooming/{entry_id}")
    async def remove_rooming(rfp_id: str, entry_id: str,
                             _: dict = Depends(require_roles("admin", "manager"))):
        await db.group_rfps.update_one(
            {"id": rfp_id}, {"$pull": {"rooming_list": {"id": entry_id}}})
        return {"ok": True}

    @router.post("/rfp/{rfp_id}/rooming/bulk")
    async def bulk_rooming(rfp_id: str, body: Dict,
                           user: dict = Depends(require_roles("admin", "manager"))):
        """Excel'den yapıştırılan listeyi toplu ekler. Satır formatı esnek:
        'Ad Soyad', 'Ad Soyad<TAB>email', 'Ad Soyad;email;2' vb."""
        rfp = await db.group_rfps.find_one({"id": rfp_id}, {"_id": 0, "status": 1})
        if not rfp:
            raise HTTPException(404, "RFP bulunamadı")
        if rfp.get("status") != "won":
            raise HTTPException(400, "Rooming list sadece kazanılmış RFP'lere eklenir")
        text = (body.get("text") or "").strip()
        if not text:
            raise HTTPException(400, "text gerekli")
        now = datetime.now(timezone.utc).isoformat()
        entries, skipped = [], 0
        for line in text.splitlines()[:200]:
            parts = [p.strip() for p in
                     line.replace("\t", ";").replace(",", ";").split(";") if p.strip()]
            if not parts:
                continue
            name, email, rooms = "", "", 1
            for p in parts:
                if "@" in p and not email:
                    email = p
                elif p.isdigit():
                    rooms = max(1, min(int(p), 20))
                elif not name:
                    name = p
            if len(name) < 2:
                skipped += 1
                continue
            entries.append({"id": str(uuid.uuid4()), "guest_name": name,
                            "guest_email": email, "rooms": rooms,
                            "added_at": now, "added_by": user.get("email", "")})
        if not entries:
            raise HTTPException(400, "Geçerli satır bulunamadı")
        await db.group_rfps.update_one(
            {"id": rfp_id}, {"$push": {"rooming_list": {"$each": entries}}})
        return {"ok": True, "added": len(entries), "skipped": skipped,
                "total_rooms": sum(e["rooms"] for e in entries)}

    @router.get("/rfp/{rfp_id}/pickup")
    async def pickup(rfp_id: str,
                     _: dict = Depends(require_roles("admin", "manager"))):
        """Blok pickup takibi: kaç oda isimli listeye döndü, wash sapması var mı?"""
        rfp = await db.group_rfps.find_one({"id": rfp_id}, {"_id": 0})
        if not rfp:
            raise HTTPException(404, "RFP bulunamadı")
        if rfp.get("status") != "won" or not rfp.get("block_booking_id"):
            raise HTTPException(400, "Pickup takibi sadece bloğu oluşmuş kazanılmış RFP'lerde")
        block = await db.bookings.find_one(
            {"id": rfp["block_booking_id"]}, {"_id": 0, "rooms": 1, "created_at": 1})
        block_rooms = int((block or {}).get("rooms", 0) or 0)
        picked = sum(int(e.get("rooms", 1) or 1) for e in (rfp.get("rooming_list") or []))
        pickup_pct = round(picked / block_rooms * 100, 1) if block_rooms else 0

        today = datetime.now(timezone.utc).date()
        arrival = _d(rfp["check_in"])
        won_at = _d(((block or {}).get("created_at") or rfp["created_at"])[:10])
        cutoff = arrival - timedelta(days=7)  # rooming list son teslim: girişten 7 gün önce
        total_days = max((cutoff - won_at).days, 1)
        elapsed = max(min((today - won_at).days, total_days), 0)
        expected_pct = round(elapsed / total_days * 100, 1)
        deviation = round(pickup_pct - expected_pct, 1)
        days_to_arrival = (arrival - today).days

        if pickup_pct >= expected_pct - 5:
            status, suggestion = "on_track", "Pickup beklenen tempoda — aksiyon gerekmez."
        elif deviation > -20:
            status = "behind"
            suggestion = "Pickup temponun gerisinde — grup yetkilisine rooming list hatırlatması gönderin."
        else:
            status = "critical"
            at_risk = max(block_rooms - picked - round(block_rooms * expected_pct / 100 * 0.3), 0)
            suggestion = (f"Ciddi wash riski: tempoya göre ~{at_risk} oda dolmayabilir. "
                          f"Attrition maddesini işletin veya odaların bir kısmını satışa geri açın.")
        return {
            "rfp_id": rfp_id, "block_rooms": block_rooms, "picked_rooms": picked,
            "pickup_pct": pickup_pct, "expected_pct_now": expected_pct,
            "deviation_pts": deviation, "days_to_arrival": days_to_arrival,
            "rooming_deadline": cutoff.isoformat(), "status": status,
            "suggestion": suggestion, "rooming_list": rfp.get("rooming_list") or [],
        }

    @router.post("/rfp/{rfp_id}/pickup/release")
    async def release_rooms(rfp_id: str, body: Dict,
                            user: dict = Depends(require_roles("admin", "manager"))):
        """Dolmayan blok odalarını satışa geri açar (blok rezervasyonunu küçültür)."""
        rfp = await db.group_rfps.find_one({"id": rfp_id}, {"_id": 0})
        if not rfp or not rfp.get("block_booking_id"):
            raise HTTPException(404, "Blok bulunamadı")
        n = max(1, int(body.get("rooms", 1) or 1))
        block = await db.bookings.find_one({"id": rfp["block_booking_id"]}, {"_id": 0, "rooms": 1})
        cur = int((block or {}).get("rooms", 0) or 0)
        picked = sum(int(e.get("rooms", 1) or 1) for e in (rfp.get("rooming_list") or []))
        new_rooms = max(cur - n, picked, 1)
        released = cur - new_rooms
        if released <= 0:
            raise HTTPException(400, "Serbest bırakılabilir oda yok (isimli liste kadar oda korunur)")
        await db.bookings.update_one(
            {"id": rfp["block_booking_id"]}, {"$set": {"rooms": new_rooms, "guests": new_rooms}})
        await db.group_rfps.update_one(
            {"id": rfp_id},
            {"$push": {"release_log": {"released": released, "remaining": new_rooms,
                                       "at": datetime.now(timezone.utc).isoformat(),
                                       "by": user.get("email", "")}}})
        return {"ok": True, "released": released, "block_rooms": new_rooms}

    return router
