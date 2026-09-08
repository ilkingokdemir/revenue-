"""
TR Country Compliance — Türkiye Kimlik Bildirim Sistemi (KBS) + e-Arşiv/e-Fatura.

KBS: Required by 1774 sayılı Kimlik Bildirme Kanunu — every guest must be
reported to the local police/jandarma within 24 hours of check-in.
The Ministry of Interior runs the official KBS portal at kbs.icisleri.gov.tr;
its bulk import format is a fixed-width pipe-delimited TXT file.

e-Arşiv Fatura: For B2C invoices, the GİB (Gelir İdaresi Başkanlığı) requires
UBL-TR 2.1 XML invoices submitted to e-Arşiv portal. Tax registered businesses
above the e-Fatura threshold (currently 5M TL/year) must use e-Fatura instead.

This module produces export bundles that an integrator can hand off
to KBS portal + GİB e-Arşiv. Real-time submission to GİB requires user's
GİB integrator key — that's a P2 (key-dependent) follow-up.
"""
from fastapi import APIRouter, Depends, HTTPException, Response
from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel
import os
import re
import uuid
import logging

logger = logging.getLogger(__name__)
_ROUTER_REF: dict = {}


VAT_PRESETS = [
    {"id": "tr_accommodation", "region": "tr", "label": "Türkiye — Konaklama KDV %10", "rate": 10, "tax_label": "KDV"},
    {"id": "tr_general", "region": "tr", "label": "Türkiye — Genel KDV %20", "rate": 20, "tax_label": "KDV"},
    {"id": "uk_standard", "region": "uk", "label": "UK — Standard VAT 20%", "rate": 20, "tax_label": "VAT"},
    {"id": "uk_zero", "region": "uk", "label": "UK — Zero-rated 0%", "rate": 0, "tax_label": "VAT"},
    {"id": "eu_de", "region": "eu", "label": "EU — Almanya konaklama %7 (USt)", "rate": 7, "tax_label": "USt"},
    {"id": "eu_at", "region": "eu", "label": "EU — Avusturya %10 (USt)", "rate": 10, "tax_label": "USt"},
    {"id": "eu_fr", "region": "eu", "label": "EU — Fransa hébergement %10 (TVA)", "rate": 10, "tax_label": "TVA"},
    {"id": "eu_es", "region": "eu", "label": "EU — İspanya %10 (IVA)", "rate": 10, "tax_label": "IVA"},
    {"id": "eu_it", "region": "eu", "label": "EU — İtalya %10 (IVA)", "rate": 10, "tax_label": "IVA"},
    {"id": "eu_nl", "region": "eu", "label": "EU — Hollanda %9 (BTW)", "rate": 9, "tax_label": "BTW"},
    {"id": "eu_gr", "region": "eu", "label": "EU — Yunanistan %13 (ΦΠΑ)", "rate": 13, "tax_label": "VAT"},
    {"id": "us_none", "region": "us", "label": "US — KDV yok (%0, eyalet vergisi ayrı)", "rate": 0, "tax_label": "Tax"},
    {"id": "us_occupancy", "region": "us", "label": "US — Occupancy tax %14 (örnek)", "rate": 14, "tax_label": "Occupancy Tax"},
    {"id": "custom", "region": "custom", "label": "Özel oran", "rate": None, "tax_label": "KDV"},
]
INTEGRATORS = [
    {"id": "none", "label": "Entegratör yok (GİB portal / manuel)"},
    {"id": "foriba", "label": "Foriba (Sovos)"},
    {"id": "uyumsoft", "label": "Uyumsoft"},
    {"id": "parasut", "label": "Paraşüt"},
    {"id": "birfatura", "label": "BirFatura"},
    {"id": "logo", "label": "Logo e-Fatura"},
    {"id": "edm", "label": "EDM Bilişim"},
    {"id": "izibiz", "label": "İzibiz"},
]


def _validate_tr_id(value: str) -> dict:
    v = "".join(ch for ch in str(value) if ch.isdigit())
    if len(v) == 10:
        d = [int(x) for x in v]
        total = 0
        for i in range(9):
            tmp = (d[i] + 9 - i) % 10
            s = (tmp * (2 ** (9 - i))) % 9
            if tmp != 0 and s == 0:
                s = 9
            total += s
        ok = (10 - total % 10) % 10 == d[9]
        return {"valid": ok, "type": "vkn", "value": v}
    if len(v) == 11:
        d = [int(x) for x in v]
        if d[0] == 0:
            return {"valid": False, "type": "tckn", "value": v}
        odd = d[0] + d[2] + d[4] + d[6] + d[8]
        even = d[1] + d[3] + d[5] + d[7]
        ok = (odd * 7 - even) % 10 == d[9] and sum(d[:10]) % 10 == d[10]
        return {"valid": ok, "type": "tckn", "value": v}
    return {"valid": False, "type": "unknown", "value": v}


class KbsExportRequest(BaseModel):
    property_id: str
    from_date: str  # YYYY-MM-DD
    to_date: str
    only_unsent: bool = True


class EArsivBuildRequest(BaseModel):
    booking_id: str
    invoice_type: str = "earsiv"  # "earsiv" (B2C) | "efatura" (B2B with VKN)
    sender_vkn: Optional[str] = None
    sender_name: Optional[str] = None
    sender_address: Optional[str] = None
    notes: Optional[str] = None


def _fmt_date(d: str) -> str:
    """Validate YYYY-MM-DD."""
    try:
        return datetime.strptime(d, "%Y-%m-%d").strftime("%Y-%m-%d")
    except Exception:
        raise HTTPException(400, "Invalid date — use YYYY-MM-DD")


def _kbs_line(g: dict, b: dict) -> str:
    """Build one fixed-width KBS line in pipe format.

    Fields (order required by KBS bulk uploader):
      tcKimlikNo | uyruk | adi | soyadi | dogumTarihi | cinsiyet |
      babaAdi | anneAdi | dogumYeri | belgeTuru | belgeNo |
      checkInTarihi | checkOutTarihi | odaNo | adresIl | adresIlce | telefon
    """
    # nationality short → KBS expects ISO-2 country code (TR / DE / GB ...)
    nat = (g.get("nationality") or g.get("country") or "TR").upper()[:2]
    fields = [
        (g.get("tc_kimlik_no") or "")[:11],          # TCKN (11 digits)
        nat,
        (g.get("first_name") or "").strip()[:50],
        (g.get("last_name") or "").strip()[:50],
        (g.get("date_of_birth") or "").replace("-", "."),
        (g.get("gender") or "")[:1].upper(),         # E / K
        (g.get("father_name") or "")[:50],
        (g.get("mother_name") or "")[:50],
        (g.get("birth_place") or "")[:50],
        (g.get("id_doc_type") or "PASAPORT")[:20],
        (g.get("id_doc_no") or "")[:30],
        (b.get("check_in") or "").replace("-", ".")[:10],
        (b.get("check_out") or "").replace("-", ".")[:10],
        (b.get("room_name") or b.get("room_number") or "")[:10],
        (g.get("address_city") or "")[:30],
        (g.get("address_district") or "")[:30],
        (g.get("phone") or "")[:20],
    ]
    return "|".join(fields)


def create_tr_compliance_router(db, require_roles):
    router = APIRouter()

    # -------- KBS — Kimlik Bildirim Sistemi --------

    @router.post("/tr-compliance/kbs/export")
    async def kbs_export(req: KbsExportRequest,
                         current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        """Build a KBS bulk-upload TXT for arrivals between dates."""
        f, t = _fmt_date(req.from_date), _fmt_date(req.to_date)

        q = {
            "property_id": req.property_id,
            "check_in": {"$gte": f, "$lte": t},
            "status": {"$in": ["confirmed", "checked_in", "checked_out"]},
        }
        if req.only_unsent:
            q["kbs_sent_at"] = {"$exists": False}

        bookings = await db.bookings.find(q, {"_id": 0}).to_list(2000)

        lines, included, skipped = [], [], []
        for b in bookings:
            guest = await db.guest_profiles.find_one(
                {"id": b.get("guest_id")}, {"_id": 0}
            ) or {}
            # Fall back to booking embedded guest
            if not guest.get("first_name"):
                gn = (b.get("guest_name") or "").split(" ", 1)
                guest["first_name"] = gn[0] if gn else ""
                guest["last_name"] = gn[1] if len(gn) > 1 else ""
            if not (guest.get("id_doc_no") or guest.get("tc_kimlik_no")):
                skipped.append({
                    "booking_id": b.get("id"),
                    "reason": "Missing TCKN or document number",
                })
                continue
            lines.append(_kbs_line(guest, b))
            included.append(b.get("id"))

        body = "\n".join(lines)

        # Persist export record
        export_id = str(uuid.uuid4())
        await db.kbs_exports.insert_one({
            "id": export_id,
            "property_id": req.property_id,
            "from_date": f,
            "to_date": t,
            "row_count": len(lines),
            "skipped_count": len(skipped),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": current_user.get("email"),
            "booking_ids": included,
        })
        # Mark bookings as exported (optimistic — final state when admin uploads)
        if included:
            await db.bookings.update_many(
                {"id": {"$in": included}},
                {"$set": {"kbs_exported_at": datetime.now(timezone.utc).isoformat(),
                          "kbs_export_id": export_id}}
            )

        return {
            "export_id": export_id,
            "row_count": len(lines),
            "skipped": skipped,
            "included_bookings": included,
            "txt": body,
            "filename": f"kbs_{req.property_id}_{f}_{t}.txt",
        }

    @router.get("/tr-compliance/kbs/export/{export_id}/download")
    async def kbs_download(export_id: str,
                           current_user: dict = Depends(require_roles("admin", "manager"))):
        rec = await db.kbs_exports.find_one({"id": export_id}, {"_id": 0})
        if not rec:
            raise HTTPException(404, "Export not found")
        # Re-build TXT (idempotent); could also persist body, but prefer to regenerate
        ids = rec.get("booking_ids", [])
        bookings = await db.bookings.find({"id": {"$in": ids}}, {"_id": 0}).to_list(2000)
        lines = []
        for b in bookings:
            g = await db.guest_profiles.find_one({"id": b.get("guest_id")}, {"_id": 0}) or {}
            if not g.get("first_name"):
                gn = (b.get("guest_name") or "").split(" ", 1)
                g["first_name"] = gn[0] if gn else ""
                g["last_name"] = gn[1] if len(gn) > 1 else ""
            lines.append(_kbs_line(g, b))
        body = "\n".join(lines)
        return Response(
            content=body,
            media_type="text/plain; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename=kbs_{export_id[:8]}.txt"},
        )

    @router.get("/tr-compliance/kbs/{property_id}/history")
    async def kbs_history(property_id: str, days: int = 90,
                          current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        rows = await db.kbs_exports.find(
            {"property_id": property_id},
            {"_id": 0}
        ).sort("created_at", -1).limit(50).to_list(50)
        # Pending (not yet exported) count
        pending = await db.bookings.count_documents({
            "property_id": property_id,
            "status": "checked_in",
            "kbs_exported_at": {"$exists": False},
        })
        return {"history": rows, "pending_count": pending}

    @router.post("/tr-compliance/kbs/export/{export_id}/mark-sent")
    async def kbs_mark_sent(export_id: str,
                            current_user: dict = Depends(require_roles("admin", "manager"))):
        rec = await db.kbs_exports.find_one({"id": export_id}, {"_id": 0})
        if not rec:
            raise HTTPException(404, "Export not found")
        now = datetime.now(timezone.utc).isoformat()
        await db.kbs_exports.update_one(
            {"id": export_id},
            {"$set": {"sent_to_kbs_at": now, "sent_by": current_user.get("email")}}
        )
        await db.bookings.update_many(
            {"id": {"$in": rec.get("booking_ids", [])}},
            {"$set": {"kbs_sent_at": now}}
        )
        return {"export_id": export_id, "sent_at": now}

    # -------- e-Arşiv / e-Fatura — UBL-TR 2.1 XML --------

    @router.post("/tr-compliance/efatura/build")
    async def efatura_build(req: EArsivBuildRequest,
                            current_user: dict = Depends(require_roles("admin", "manager"))):
        """Build a UBL-TR 2.1 InvoiceXML for one booking."""
        return await _build_one(req, current_user)

    async def _build_one(req: EArsivBuildRequest, current_user: dict, force: bool = True):
        booking = await db.bookings.find_one({"id": req.booking_id}, {"_id": 0})
        if not booking:
            raise HTTPException(404, "Booking not found")
        if booking.get("tr_invoice_uuid"):
            prev = await db.tr_invoices.find_one({"id": booking["tr_invoice_uuid"], "status": {"$ne": "cancelled"}}, {"_id": 0, "invoice_no": 1})
            if prev and not force:
                raise HTTPException(409, f"Bu rezervasyon için fatura zaten var: {prev['invoice_no']}")
        settings = await _get_settings(booking.get("property_id") or "")
        default_rate = float(settings.get("vat_rate") if settings.get("vat_rate") is not None else 10.0)
        tax_label = settings.get("tax_label") or "KDV"

        property_doc = await db.properties.find_one(
            {"id": booking.get("property_id")}, {"_id": 0}
        ) or {}
        guest = await db.guest_profiles.find_one(
            {"id": booking.get("guest_id")}, {"_id": 0}
        ) or {}
        charges = await db.folio_charges.find(
            {"booking_id": req.booking_id}, {"_id": 0}
        ).to_list(500)

        # Defaults
        sender_name = req.sender_name or settings.get("sender_name") or property_doc.get("legal_name") or property_doc.get("name") or "Hotel"
        sender_vkn = req.sender_vkn or settings.get("sender_vkn") or property_doc.get("vkn") or property_doc.get("tax_id") or "0000000000"
        sender_addr = req.sender_address or settings.get("sender_address") or property_doc.get("address") or ""
        recipient_vkn = guest.get("vkn") or guest.get("tc_kimlik_no") or "11111111111"
        recipient_name = f"{guest.get('first_name','')} {guest.get('last_name','')}".strip() or booking.get("guest_name", "Müşteri")

        invoice_no = f"HTL{datetime.now().strftime('%Y%m%d')}{booking.get('id', '')[:6].upper()}"
        issue_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        currency = booking.get("currency", "TRY")

        # Lines: prefer folio_charges; fall back to single room-rate line
        if charges:
            lines = []
            subtotal = 0.0
            tax_total = 0.0
            for i, c in enumerate(charges, start=1):
                gross = float(c.get("amount", 0))
                tax_rate = float(c.get("tax_rate", default_rate))
                net = round(gross / (1 + tax_rate / 100), 2)
                tax = round(gross - net, 2)
                lines.append({
                    "id": i,
                    "name": (c.get("description") or c.get("category") or "Konaklama")[:200],
                    "qty": 1,
                    "unit": "C62",  # piece
                    "price": net,
                    "tax_rate": tax_rate,
                    "tax_amount": tax,
                    "gross": gross,
                })
                subtotal += net
                tax_total += tax
            total = subtotal + tax_total
        else:
            total = float(booking.get("total_price", 0))
            tax_rate = default_rate
            net = round(total / (1 + tax_rate / 100), 2)
            tax = round(total - net, 2)
            lines = [{
                "id": 1,
                "name": f"Konaklama {booking.get('check_in')} - {booking.get('check_out')}",
                "qty": 1, "unit": "C62", "price": net,
                "tax_rate": tax_rate, "tax_amount": tax, "gross": total,
            }]
            subtotal = net
            tax_total = tax

        # Build a minimal UBL-TR 2.1 envelope
        inv_lines_xml = "\n".join([
            f"""    <cac:InvoiceLine>
      <cbc:ID>{ln["id"]}</cbc:ID>
      <cbc:InvoicedQuantity unitCode="{ln["unit"]}">{ln["qty"]}</cbc:InvoicedQuantity>
      <cbc:LineExtensionAmount currencyID="{currency}">{ln["price"]:.2f}</cbc:LineExtensionAmount>
      <cac:TaxTotal>
        <cbc:TaxAmount currencyID="{currency}">{ln["tax_amount"]:.2f}</cbc:TaxAmount>
        <cac:TaxSubtotal>
          <cbc:TaxableAmount currencyID="{currency}">{ln["price"]:.2f}</cbc:TaxableAmount>
          <cbc:TaxAmount currencyID="{currency}">{ln["tax_amount"]:.2f}</cbc:TaxAmount>
          <cac:TaxCategory>
            <cbc:Percent>{ln["tax_rate"]:.1f}</cbc:Percent>
            <cac:TaxScheme><cbc:Name>{tax_label}</cbc:Name><cbc:TaxTypeCode>0015</cbc:TaxTypeCode></cac:TaxScheme>
          </cac:TaxCategory>
        </cac:TaxSubtotal>
      </cac:TaxTotal>
      <cac:Item><cbc:Name>{ln["name"]}</cbc:Name></cac:Item>
      <cac:Price><cbc:PriceAmount currencyID="{currency}">{ln["price"]:.2f}</cbc:PriceAmount></cac:Price>
    </cac:InvoiceLine>"""
            for ln in lines
        ])

        profile = "EARSIVFATURA" if req.invoice_type == "earsiv" else "TICARIFATURA"
        invoice_uuid = str(uuid.uuid4())

        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
         xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
         xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
  <cbc:UBLVersionID>2.1</cbc:UBLVersionID>
  <cbc:CustomizationID>TR1.2</cbc:CustomizationID>
  <cbc:ProfileID>{profile}</cbc:ProfileID>
  <cbc:ID>{invoice_no}</cbc:ID>
  <cbc:CopyIndicator>false</cbc:CopyIndicator>
  <cbc:UUID>{invoice_uuid}</cbc:UUID>
  <cbc:IssueDate>{issue_date}</cbc:IssueDate>
  <cbc:InvoiceTypeCode>SATIS</cbc:InvoiceTypeCode>
  <cbc:DocumentCurrencyCode>{currency}</cbc:DocumentCurrencyCode>
  <cac:AccountingSupplierParty>
    <cac:Party>
      <cbc:WebsiteURI>{property_doc.get("website", "")}</cbc:WebsiteURI>
      <cac:PartyIdentification><cbc:ID schemeID="VKN">{sender_vkn}</cbc:ID></cac:PartyIdentification>
      <cac:PartyName><cbc:Name>{sender_name}</cbc:Name></cac:PartyName>
      <cac:PostalAddress><cbc:StreetName>{sender_addr}</cbc:StreetName><cac:Country><cbc:Name>Türkiye</cbc:Name></cac:Country></cac:PostalAddress>
    </cac:Party>
  </cac:AccountingSupplierParty>
  <cac:AccountingCustomerParty>
    <cac:Party>
      <cac:PartyIdentification><cbc:ID schemeID="TCKN">{recipient_vkn}</cbc:ID></cac:PartyIdentification>
      <cac:PartyName><cbc:Name>{recipient_name}</cbc:Name></cac:PartyName>
    </cac:Party>
  </cac:AccountingCustomerParty>
  <cac:TaxTotal>
    <cbc:TaxAmount currencyID="{currency}">{tax_total:.2f}</cbc:TaxAmount>
  </cac:TaxTotal>
  <cac:LegalMonetaryTotal>
    <cbc:LineExtensionAmount currencyID="{currency}">{subtotal:.2f}</cbc:LineExtensionAmount>
    <cbc:TaxExclusiveAmount currencyID="{currency}">{subtotal:.2f}</cbc:TaxExclusiveAmount>
    <cbc:TaxInclusiveAmount currencyID="{currency}">{(subtotal + tax_total):.2f}</cbc:TaxInclusiveAmount>
    <cbc:PayableAmount currencyID="{currency}">{(subtotal + tax_total):.2f}</cbc:PayableAmount>
  </cac:LegalMonetaryTotal>
{inv_lines_xml}
</Invoice>"""

        # Persist invoice meta
        await db.tr_invoices.insert_one({
            "id": invoice_uuid,
            "invoice_no": invoice_no,
            "booking_id": req.booking_id,
            "property_id": booking.get("property_id"),
            "type": req.invoice_type,
            "issue_date": issue_date,
            "subtotal": round(subtotal, 2),
            "tax_total": round(tax_total, 2),
            "total": round(subtotal + tax_total, 2),
            "currency": currency,
            "recipient_name": recipient_name,
            "recipient_vkn": recipient_vkn,
            "status": "built",  # built → submitted/sent → accepted | rejected | cancelled
            "tax_rate": default_rate, "tax_label": tax_label, "tax_region": settings.get("tax_region") or "tr",
            "sender_name": sender_name, "sender_vkn": sender_vkn, "sender_address": sender_addr,
            "guest_email": booking.get("guest_email", ""), "booking_ref": booking.get("booking_ref", ""),
            "check_in": booking.get("check_in"), "check_out": booking.get("check_out"),
            "lines": lines, "xml": xml, "notes": req.notes or "",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": current_user.get("email"),
        })
        await db.bookings.update_one(
            {"id": req.booking_id},
            {"$set": {"tr_invoice_uuid": invoice_uuid, "tr_invoice_no": invoice_no}}
        )

        return {
            "uuid": invoice_uuid,
            "invoice_no": invoice_no,
            "type": req.invoice_type,
            "subtotal": round(subtotal, 2),
            "tax_total": round(tax_total, 2),
            "total": round(subtotal + tax_total, 2),
            "currency": currency,
            "xml": xml,
            "filename": f"{invoice_no}.xml",
        }

    @router.get("/tr-compliance/efatura/{property_id}/list")
    async def efatura_list(property_id: str, days: int = 90,
                           current_user: dict = Depends(require_roles("admin", "manager"))):
        rows = await db.tr_invoices.find(
            {"property_id": property_id},
            {"_id": 0, "xml": 0, "lines": 0}
        ).sort("created_at", -1).limit(200).to_list(200)
        # Aggregate
        total_count = len(rows)
        total_amount = sum(r.get("total", 0) for r in rows)
        by_status = {}
        for r in rows:
            s = r.get("status", "built")
            by_status[s] = by_status.get(s, 0) + 1
        return {
            "invoices": rows,
            "total_count": total_count,
            "total_amount": round(total_amount, 2),
            "by_status": by_status,
        }

    @router.post("/tr-compliance/efatura/{invoice_id}/mark-submitted")
    async def efatura_mark_submitted(invoice_id: str,
                                     current_user: dict = Depends(require_roles("admin", "manager"))):
        rec = await db.tr_invoices.find_one({"id": invoice_id}, {"_id": 0})
        if not rec:
            raise HTTPException(404, "Invoice not found")
        now = datetime.now(timezone.utc).isoformat()
        await db.tr_invoices.update_one(
            {"id": invoice_id},
            {"$set": {"status": "submitted", "submitted_at": now,
                      "submitted_by": current_user.get("email")}}
        )
        return {"id": invoice_id, "status": "submitted", "submitted_at": now}

        # -------- e-Fatura ayarları / entegratör / KDV --------
    async def _get_settings(property_id: str) -> dict:
        doc = await db.tr_einvoice_settings.find_one({"property_id": property_id}, {"_id": 0}) or {}
        return {"property_id": property_id, "integrator": "none", "mode": "test", "api_key": "", "tax_region": "tr",
                "vat_preset": "tr_accommodation", "vat_rate": 10.0, "tax_label": "KDV", "sender_vkn": "", "sender_name": "",
                "sender_address": "", "auto_issue_on_checkout": False, "auto_submit": True, "email_guest_copy": True, "auto_invoice_type": "earsiv", "accountant_email": "", "accountant_name": "", **doc}

    def _mask(k: str) -> str:
        return f"••••{k[-4:]}" if k and len(k) > 4 else ("••••" if k else "")

    @router.get("/tr-compliance/efatura/{property_id}/settings")
    async def efatura_settings_get(property_id: str, _u: dict = Depends(require_roles("admin", "manager"))):
        st = await _get_settings(property_id)
        st["api_key_masked"] = _mask(st.pop("api_key", ""))
        return {"settings": st, "vat_presets": VAT_PRESETS, "integrators": INTEGRATORS}

    @router.put("/tr-compliance/efatura/{property_id}/settings")
    async def efatura_settings_put(property_id: str, data: dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        cur = await _get_settings(property_id)
        integ = data.get("integrator") if data.get("integrator") in {i["id"] for i in INTEGRATORS} else cur["integrator"]
        preset_id = data.get("vat_preset") or cur.get("vat_preset")
        preset = next((p for p in VAT_PRESETS if p["id"] == preset_id), None)
        if preset and preset["rate"] is not None:
            rate = float(preset["rate"]); label = preset["tax_label"]; region = preset["region"]
        else:
            try:
                rate = float(data.get("vat_rate", cur["vat_rate"]))
            except (TypeError, ValueError):
                raise HTTPException(422, "vat_rate sayı olmalı")
            label = str(data.get("tax_label") or cur.get("tax_label") or "KDV")[:20]
            region = data.get("tax_region") if data.get("tax_region") in ("tr", "uk", "eu", "us", "custom") else cur.get("tax_region", "tr")
        if not 0 <= rate <= 60:
            raise HTTPException(422, "KDV oranı 0-60 arasında olmalı")
        vkn = str(data.get("sender_vkn") or cur.get("sender_vkn") or "").strip()
        if vkn and not _validate_tr_id(vkn)["valid"]:
            raise HTTPException(422, "Geçersiz VKN/TCKN")
        upd = {"property_id": property_id, "integrator": integ, "mode": data.get("mode") if data.get("mode") in ("test", "live") else cur["mode"],
               "tax_region": region, "vat_preset": preset_id if preset else "custom", "vat_rate": rate, "tax_label": label,
               "sender_vkn": vkn, "sender_name": str(data.get("sender_name", cur.get("sender_name")) or "")[:160],
               "sender_address": str(data.get("sender_address", cur.get("sender_address")) or "")[:400],
               "auto_issue_on_checkout": bool(data.get("auto_issue_on_checkout", cur.get("auto_issue_on_checkout"))),
               "auto_submit": bool(data.get("auto_submit", cur.get("auto_submit", True))),
               "email_guest_copy": bool(data.get("email_guest_copy", cur.get("email_guest_copy", True))),
               "auto_invoice_type": data.get("auto_invoice_type") if data.get("auto_invoice_type") in ("earsiv", "efatura") else cur.get("auto_invoice_type", "earsiv"),
               "accountant_email": str(data.get("accountant_email", cur.get("accountant_email")) or "").strip()[:120],
               "accountant_name": str(data.get("accountant_name", cur.get("accountant_name")) or "").strip()[:120],
               "updated_at": datetime.now(timezone.utc).isoformat(), "updated_by": current_user.get("email")}
        if data.get("api_key") and "•" not in str(data["api_key"]):
            upd["api_key"] = str(data["api_key"])[:200]
        await db.tr_einvoice_settings.update_one({"property_id": property_id}, {"$set": upd}, upsert=True)
        st = await _get_settings(property_id)
        st["api_key_masked"] = _mask(st.pop("api_key", ""))
        return {"ok": True, "settings": st}

    @router.post("/tr-compliance/validate-id")
    async def validate_id(data: dict):
        return _validate_tr_id(str(data.get("value") or ""))

    @router.post("/tr-compliance/efatura/{invoice_id}/submit")
    async def efatura_submit(invoice_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        """Entegratör üzerinden GİB'e gönder. Gerçek API anahtarı yoksa SİMÜLE edilir (outbox)."""
        return await _submit_one(invoice_id, current_user)

    async def _submit_one(invoice_id: str, current_user: dict):
        rec = await db.tr_invoices.find_one({"id": invoice_id}, {"_id": 0, "xml": 0})
        if not rec:
            raise HTTPException(404, "Invoice not found")
        if rec.get("status") in ("sent", "accepted"):
            raise HTTPException(409, "Fatura zaten gönderilmiş")
        if rec.get("status") == "cancelled":
            raise HTTPException(409, "İptal edilmiş fatura gönderilemez")
        st = await _get_settings(rec.get("property_id") or "")
        now = datetime.now(timezone.utc).isoformat()
        ettn = str(uuid.uuid4())
        simulated = True  # gerçek entegratör SDK'sı anahtarla bağlanınca False olur
        provider = st.get("integrator") if st.get("integrator") != "none" else "gib_portal"
        upd = {"status": "sent", "ettn": ettn, "provider": provider, "provider_mode": st.get("mode", "test"), "simulated": simulated,
               "sent_at": now, "sent_by": current_user.get("email"), "gib_status": "accepted", "gib_status_at": now}
        await db.tr_invoices.update_one({"id": invoice_id}, {"$set": upd})
        await db.tr_einvoice_outbox.insert_one({"id": str(uuid.uuid4()), "invoice_id": invoice_id, "invoice_no": rec.get("invoice_no"),
                                                 "property_id": rec.get("property_id"), "provider": provider, "mode": st.get("mode", "test"),
                                                 "has_api_key": bool(st.get("api_key")), "simulated": simulated, "ettn": ettn, "created_at": now})
        return {"id": invoice_id, **upd}

    @router.post("/tr-compliance/efatura/{invoice_id}/cancel")
    async def efatura_cancel(invoice_id: str, data: dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        rec = await db.tr_invoices.find_one({"id": invoice_id}, {"_id": 0, "xml": 0})
        if not rec:
            raise HTTPException(404, "Invoice not found")
        if rec.get("status") == "cancelled":
            raise HTTPException(409, "Zaten iptal")
        reason = str(data.get("reason") or "").strip()
        if not reason:
            raise HTTPException(422, "İptal nedeni zorunlu")
        now = datetime.now(timezone.utc).isoformat()
        await db.tr_invoices.update_one({"id": invoice_id}, {"$set": {"status": "cancelled", "cancel_reason": reason[:300], "cancelled_at": now, "cancelled_by": current_user.get("email")}})
        await db.bookings.update_one({"id": rec.get("booking_id")}, {"$unset": {"tr_invoice_uuid": "", "tr_invoice_no": ""}})
        return {"id": invoice_id, "status": "cancelled", "cancelled_at": now}

    @router.post("/tr-compliance/efatura/bulk")
    async def efatura_bulk(data: dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        """Ay içinde çıkış yapan, faturası olmayan tüm rezervasyonlar için toplu fatura üret."""
        pid = data.get("property_id") or ""
        month = str(data.get("month") or "")
        if not pid or len(month) != 7:
            raise HTTPException(422, "property_id ve month (YYYY-MM) zorunlu")
        inv_type = data.get("invoice_type") if data.get("invoice_type") in ("earsiv", "efatura") else "earsiv"
        q = {"property_id": pid, "check_out": {"$gte": f"{month}-01", "$lte": f"{month}-31"}, "status": {"$nin": ["cancelled", "no_show"]},
             "tr_invoice_uuid": {"$exists": False}}
        if data.get("only_paid"):
            q["payment_status"] = "paid"
        bookings = await db.bookings.find(q, {"_id": 0, "id": 1}).limit(300).to_list(300)
        created, failed = [], 0
        for b in bookings:
            try:
                r = await _build_one(EArsivBuildRequest(booking_id=b["id"], invoice_type=inv_type), current_user)
                created.append({"invoice_no": r["invoice_no"], "total": r["total"], "uuid": r["uuid"]})
            except HTTPException:
                failed += 1
        return {"month": month, "created": len(created), "failed": failed, "invoices": created[:50]}

    @router.get("/tr-compliance/efatura/{invoice_id}/html")
    async def efatura_html(invoice_id: str, _u: dict = Depends(require_roles("admin", "manager"))):
        rec = await db.tr_invoices.find_one({"id": invoice_id}, {"_id": 0, "xml": 0})
        if not rec:
            raise HTTPException(404, "Invoice not found")
        return Response(_render_html(rec), media_type="text/html; charset=utf-8")

    def _render_html(rec: dict) -> str:
        cur = rec.get("currency", "TRY")
        rows = "".join(f"<tr><td>{ln['id']}</td><td>{ln['name']}</td><td class=r>{ln['qty']}</td><td class=r>{ln['price']:.2f}</td><td class=r>%{ln['tax_rate']:.0f}</td><td class=r>{ln['tax_amount']:.2f}</td><td class=r>{ln['gross']:.2f}</td></tr>" for ln in rec.get("lines") or [])
        status_tr = {"built": "Oluşturuldu", "sent": "GİB'e gönderildi", "submitted": "Gönderildi", "accepted": "Kabul", "rejected": "Red", "cancelled": "İPTAL"}.get(rec.get("status"), rec.get("status"))
        html = f"""<!doctype html><html lang=tr><head><meta charset=utf-8><title>{rec.get('invoice_no')}</title>
<style>body{{font-family:system-ui,Arial;margin:32px;color:#1c1917;font-size:13px}} h1{{font-size:20px;margin:0}} .grid{{display:grid;grid-template-columns:1fr 1fr;gap:24px;margin:20px 0}}
.box{{border:1px solid #e7e5e4;border-radius:8px;padding:12px}} .lbl{{font-size:10px;text-transform:uppercase;letter-spacing:.08em;color:#78716c}} table{{width:100%;border-collapse:collapse;margin-top:16px}}
th{{text-align:left;font-size:10px;text-transform:uppercase;color:#78716c;border-bottom:2px solid #e7e5e4;padding:6px}} td{{padding:7px 6px;border-bottom:1px solid #f5f5f4}} .r{{text-align:right}}
.tot{{margin-top:12px;margin-left:auto;width:280px}} .tot div{{display:flex;justify-content:space-between;padding:4px 0}} .tot .g{{font-weight:700;font-size:16px;border-top:2px solid #1c1917;padding-top:8px}}
.badge{{display:inline-block;padding:2px 8px;border-radius:999px;background:#f5f5f4;font-size:11px}} .cancel{{color:#b91c1c;font-weight:700}} @media print{{button{{display:none}}}}</style></head><body>
<div style="display:flex;justify-content:space-between;align-items:flex-start"><div><h1>{'e-Arşiv Fatura' if rec.get('type')=='earsiv' else 'e-Fatura'}</h1><div class=lbl>UBL-TR 2.1 · {rec.get('tax_region','tr').upper()}</div></div>
<div style="text-align:right"><div style="font-family:monospace;font-size:15px;font-weight:700">{rec.get('invoice_no')}</div><div class=lbl>Tarih {rec.get('issue_date')}</div><span class="badge {'cancel' if rec.get('status')=='cancelled' else ''}">{status_tr}</span></div></div>
<div class=grid><div class=box><div class=lbl>Satıcı</div><b>{rec.get('sender_name','')}</b><div>VKN: {rec.get('sender_vkn','')}</div><div>{rec.get('sender_address','')}</div></div>
<div class=box><div class=lbl>Alıcı</div><b>{rec.get('recipient_name','')}</b><div>VKN/TCKN: {rec.get('recipient_vkn','')}</div><div>{rec.get('guest_email','')}</div><div>Rez. {rec.get('booking_ref','')} · {rec.get('check_in','')} → {rec.get('check_out','')}</div></div></div>
{('<div class=box><div class=lbl>ETTN</div><code>'+rec['ettn']+'</code> · '+str(rec.get('provider',''))+' ('+str(rec.get('provider_mode',''))+('' if not rec.get('simulated') else ' · simülasyon')+')</div>') if rec.get('ettn') else ''}
<table><thead><tr><th>#</th><th>Açıklama</th><th class=r>Miktar</th><th class=r>Birim ({cur})</th><th class=r>{rec.get('tax_label','KDV')}</th><th class=r>Vergi</th><th class=r>Toplam</th></tr></thead><tbody>{rows}</tbody></table>
<div class=tot><div><span>Ara toplam</span><span>{rec.get('subtotal',0):.2f} {cur}</span></div><div><span>{rec.get('tax_label','KDV')} (%{rec.get('tax_rate',0):.0f})</span><span>{rec.get('tax_total',0):.2f} {cur}</span></div><div class=g><span>Genel toplam</span><span>{rec.get('total',0):.2f} {cur}</span></div></div>
{('<p class=cancel>İptal nedeni: '+rec.get('cancel_reason','')+'</p>') if rec.get('status')=='cancelled' else ''}
<p style="margin-top:28px;color:#78716c;font-size:11px">{rec.get('notes','')}</p><button onclick="window.print()" style="margin-top:12px;padding:8px 14px;border-radius:8px;border:1px solid #d6d3d1;background:#fff;cursor:pointer">Yazdır / PDF</button></body></html>"""
        return html

    @router.get("/tr-compliance/efatura/{property_id}/archive.zip")
    async def efatura_archive(property_id: str, month: str, _u: dict = Depends(require_roles("admin", "manager"))):
        """Aylık arşiv: her fatura için UBL XML + PDF + özet CSV tek ZIP."""
        import csv
        import io
        import zipfile
        if len(month) != 7:
            raise HTTPException(422, "month YYYY-MM")
        data, rows = await _build_archive(property_id, month)
        return Response(data, media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="efatura_{property_id}_{month}.zip"'})

    async def _build_archive(property_id: str, month: str):
        import csv
        import io
        import zipfile
        rows = await db.tr_invoices.find({"property_id": property_id, "issue_date": {"$gte": f"{month}-01", "$lte": f"{month}-31"}}, {"_id": 0}).sort("issue_date", 1).to_list(2000)
        if not rows:
            raise HTTPException(404, "Bu ay için fatura yok")
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            csv_io = io.StringIO(); w = csv.writer(csv_io)
            w.writerow(["invoice_no", "issue_date", "type", "status", "ettn", "recipient", "recipient_vkn", "subtotal", "tax_rate", "tax_total", "total", "currency", "booking_ref"])
            for r in rows:
                w.writerow([r.get("invoice_no"), r.get("issue_date"), r.get("type"), r.get("status"), r.get("ettn", ""), r.get("recipient_name"), r.get("recipient_vkn"),
                            r.get("subtotal"), r.get("tax_rate"), r.get("tax_total"), r.get("total"), r.get("currency"), r.get("booking_ref", "")])
                if r.get("xml"):
                    z.writestr(f"xml/{r['invoice_no']}.xml", r["xml"])
                z.writestr(f"pdf/{r['invoice_no']}.pdf", _render_pdf(r))
            z.writestr(f"ozet_{month}.csv", "\ufeff" + csv_io.getvalue())
        return buf.getvalue(), rows

    async def _send_archive(property_id: str, month: str, auto: bool = False, by: str = "system") -> dict:
        st = await _get_settings(property_id)
        to = st.get("accountant_email")
        if not to:
            raise HTTPException(422, "Muhasebeci e-postası tanımlı değil")
        data, rows = await _build_archive(property_id, month)
        token = uuid.uuid4().hex
        from object_storage import save_upload
        await save_upload(f"efatura_archives/{token}.zip", data)
        base = (os.environ.get("PUBLIC_BASE_URL") or "").rstrip("/")
        link = f"{base}/api/tr-compliance/efatura/archive-download/{token}"
        total = round(sum(float(r.get("total") or 0) for r in rows), 2)
        cur = rows[0].get("currency", "TRY") if rows else "TRY"
        prop = await db.properties.find_one({"id": property_id}, {"_id": 0, "name": 1}) or {}
        html = f"""<div style="font-family:system-ui,Arial;max-width:560px;margin:auto;color:#1c1917"><h2 style="margin:0 0 6px">{prop.get('name', property_id)} — {month} e-Fatura arşivi</h2>
<p style="color:#57534e;font-size:14px">Sayın {st.get('accountant_name') or 'Muhasebeci'}, {month} dönemine ait <b>{len(rows)}</b> fatura (toplam <b>{total:,.2f} {cur}</b>) UBL XML + PDF + özet CSV olarak ekte/bağlantıda.</p>
<p><a href="{link}" style="display:inline-block;background:#111;color:#fff;text-decoration:none;padding:10px 18px;border-radius:999px;font-weight:700">ZIP arşivini indir</a></p>
<p style="font-size:11px;color:#a8a29e">Bağlantı 90 gün geçerlidir. {'Otomatik aylık gönderim.' if auto else 'Manuel gönderim.'}</p></div>"""
        from routes.platform_ext.mailer import send_email
        status = await send_email(db, to, f"{prop.get('name', property_id)} · {month} e-Fatura arşivi ({len(rows)} fatura)", html, kind="efatura_archive", meta={"property_id": property_id, "month": month})
        rec = {"id": str(uuid.uuid4()), "token": token, "property_id": property_id, "month": month, "to": to, "count": len(rows), "total": total, "currency": cur,
               "auto": auto, "email_status": status, "sent_by": by, "size": len(data), "created_at": datetime.now(timezone.utc).isoformat()}
        await db.tr_einvoice_archives.insert_one(dict(rec))
        rec.pop("_id", None)
        return rec

    @router.post("/tr-compliance/efatura/{property_id}/archive/send")
    async def efatura_archive_send(property_id: str, data: dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        month = str(data.get("month") or "")
        if len(month) != 7:
            raise HTTPException(422, "month YYYY-MM")
        return await _send_archive(property_id, month, auto=False, by=current_user.get("email", ""))

    @router.get("/tr-compliance/efatura/{property_id}/archive/history")
    async def efatura_archive_history(property_id: str, _u: dict = Depends(require_roles("admin", "manager"))):
        rows = await db.tr_einvoice_archives.find({"property_id": property_id}, {"_id": 0, "token": 0}).sort("created_at", -1).limit(24).to_list(24)
        return {"history": rows}

    @router.get("/tr-compliance/efatura/archive-download/{token}")
    async def efatura_archive_download(token: str):
        rec = await db.tr_einvoice_archives.find_one({"token": re.sub(r"[^a-f0-9]", "", token)}, {"_id": 0})
        if not rec:
            raise HTTPException(404, "Arşiv bulunamadı")
        from object_storage import fetch_upload
        got = await fetch_upload(f"efatura_archives/{rec['token']}.zip")
        data = got[0] if isinstance(got, tuple) else got
        if not data:
            local = f"/app/backend/uploads/efatura_archives/{rec['token']}.zip"
            if os.path.exists(local):
                data = open(local, "rb").read()
        if not data:
            raise HTTPException(404, "Dosya bulunamadı")
        return Response(data, media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="efatura_{rec["property_id"]}_{rec["month"]}.zip"'})

    router.send_archive = _send_archive

    def _render_pdf(rec: dict) -> bytes:
        import io
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        font = "Helvetica"
        for path in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf"):
            if os.path.exists(path):
                try:
                    pdfmetrics.registerFont(TTFont("DejaVu", path)); font = "DejaVu"
                except Exception:
                    pass
                break
        out = io.BytesIO(); c = canvas.Canvas(out, pagesize=A4); W, H = A4; y = H - 50
        c.setFont(font, 16); c.drawString(40, y, "e-Arşiv Fatura" if rec.get("type") == "earsiv" else "e-Fatura"); c.setFont(font, 10)
        c.drawRightString(W - 40, y, f"{rec.get('invoice_no', '')}  ·  {rec.get('issue_date', '')}"); y -= 18
        c.drawRightString(W - 40, y, f"Durum: {rec.get('status', '')}" + (f"  ·  ETTN {rec.get('ettn')}" if rec.get("ettn") else "")); y -= 28
        c.drawString(40, y, f"Satıcı: {rec.get('sender_name', '')}  VKN {rec.get('sender_vkn', '')}"); y -= 14
        c.drawString(40, y, f"{rec.get('sender_address', '')}"); y -= 20
        c.drawString(40, y, f"Alıcı: {rec.get('recipient_name', '')}  VKN/TCKN {rec.get('recipient_vkn', '')}  ·  Rez. {rec.get('booking_ref', '')} {rec.get('check_in', '')} → {rec.get('check_out', '')}"); y -= 26
        cur = rec.get("currency", "TRY")
        c.line(40, y, W - 40, y); y -= 14
        c.drawString(40, y, "#"); c.drawString(60, y, "Açıklama"); c.drawRightString(W - 220, y, "Birim"); c.drawRightString(W - 150, y, rec.get("tax_label", "KDV")); c.drawRightString(W - 90, y, "Vergi"); c.drawRightString(W - 40, y, "Toplam"); y -= 6
        c.line(40, y, W - 40, y); y -= 14
        for ln in rec.get("lines") or []:
            c.drawString(40, y, str(ln["id"])); c.drawString(60, y, str(ln["name"])[:70]); c.drawRightString(W - 220, y, f"{ln['price']:.2f}"); c.drawRightString(W - 150, y, f"%{ln['tax_rate']:.0f}")
            c.drawRightString(W - 90, y, f"{ln['tax_amount']:.2f}"); c.drawRightString(W - 40, y, f"{ln['gross']:.2f}"); y -= 14
            if y < 120:
                c.showPage(); c.setFont(font, 10); y = H - 50
        y -= 10; c.line(W - 260, y, W - 40, y); y -= 16
        c.drawRightString(W - 120, y, "Ara toplam"); c.drawRightString(W - 40, y, f"{rec.get('subtotal', 0):.2f} {cur}"); y -= 14
        c.drawRightString(W - 120, y, f"{rec.get('tax_label', 'KDV')} %{rec.get('tax_rate', 0):.0f}"); c.drawRightString(W - 40, y, f"{rec.get('tax_total', 0):.2f} {cur}"); y -= 16
        c.setFont(font, 12); c.drawRightString(W - 120, y, "Genel toplam"); c.drawRightString(W - 40, y, f"{rec.get('total', 0):.2f} {cur}")
        if rec.get("status") == "cancelled":
            c.setFont(font, 14); c.drawString(40, 60, f"İPTAL — {rec.get('cancel_reason', '')}")
        c.showPage(); c.save()
        return out.getvalue()

    @router.get("/tr-compliance/efatura/{property_id}/auto-log")
    async def efatura_auto_log(property_id: str, _u: dict = Depends(require_roles("admin", "manager"))):
        rows = await db.tr_einvoice_auto_log.find({"property_id": property_id}, {"_id": 0}).sort("created_at", -1).limit(30).to_list(30)
        return {"log": rows}

    router.build_invoice = _build_one
    router.submit_invoice = _submit_one
    router.get_settings = _get_settings
    router.render_html = _render_html
    _ROUTER_REF["router"] = router
    _ROUTER_REF["db"] = db
    return router


async def send_archive_to_accountant(property_id: str, month: str, auto: bool = True) -> dict:
    r = _ROUTER_REF.get("router")
    if not r:
        return {"skipped": "no_router"}
    return await r.send_archive(property_id, month, auto=auto)


async def auto_issue_on_checkout(booking: dict) -> dict:
    """Check-out anında otomatik e-Arşiv: üret → (simüle) gönder → misafire HTML kopya e-postası."""
    r = _ROUTER_REF.get("router"); db = _ROUTER_REF.get("db")
    if not r or not booking or not booking.get("id"):
        return {"skipped": "no_router"}
    pid = booking.get("property_id") or ""
    st = await r.get_settings(pid)
    if not st.get("auto_issue_on_checkout"):
        return {"skipped": "disabled"}
    if booking.get("tr_invoice_uuid") and await db.tr_invoices.find_one({"id": booking["tr_invoice_uuid"], "status": {"$ne": "cancelled"}}, {"_id": 0, "id": 1}):
        return {"skipped": "exists"}
    now = datetime.now(timezone.utc).isoformat()
    log = {"id": str(uuid.uuid4()), "property_id": pid, "booking_id": booking["id"], "booking_ref": booking.get("booking_ref", ""),
           "guest_email": booking.get("guest_email", ""), "created_at": now}
    try:
        res = await r.build_invoice(EArsivBuildRequest(booking_id=booking["id"], invoice_type=st.get("auto_invoice_type") or "earsiv"), {"email": "auto@checkout"})
        await db.tr_invoices.update_one({"id": res["uuid"]}, {"$set": {"auto_issued": True}})
        log.update({"invoice_id": res["uuid"], "invoice_no": res["invoice_no"], "total": res["total"], "currency": res["currency"]})
        if st.get("auto_submit", True):
            sub = await r.submit_invoice(res["uuid"], {"email": "auto@checkout"})
            log.update({"ettn": sub.get("ettn"), "submitted": True, "simulated": sub.get("simulated", True)})
        email_status = "skipped"
        if st.get("email_guest_copy", True) and booking.get("guest_email"):
            from routes.platform_ext.mailer import send_email
            rec = await db.tr_invoices.find_one({"id": res["uuid"]}, {"_id": 0, "xml": 0})
            html = r.render_html(rec)
            email_status = await send_email(db, booking["guest_email"], f"Faturanız / Your invoice — {res['invoice_no']}", html,
                                            kind="e_invoice", meta={"booking_id": booking["id"], "invoice_id": res["uuid"], "property_id": pid})
        log.update({"email_status": email_status, "status": "ok"})
    except Exception as e:  # noqa: BLE001
        logger.warning(f"auto e-invoice failed for {booking.get('booking_ref')}: {e}")
        log.update({"status": "failed", "error": str(e)[:300]})
    await db.tr_einvoice_auto_log.insert_one(dict(log))
    log.pop("_id", None)
    return log
