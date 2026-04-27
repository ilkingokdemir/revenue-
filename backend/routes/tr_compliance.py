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
import uuid
import logging

logger = logging.getLogger(__name__)


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
        booking = await db.bookings.find_one({"id": req.booking_id}, {"_id": 0})
        if not booking:
            raise HTTPException(404, "Booking not found")

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
        sender_name = req.sender_name or property_doc.get("legal_name") or property_doc.get("name") or "Hotel"
        sender_vkn = req.sender_vkn or property_doc.get("vkn") or property_doc.get("tax_id") or "0000000000"
        sender_addr = req.sender_address or property_doc.get("address") or ""
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
                tax_rate = float(c.get("tax_rate", 8.0))  # konaklama %8 default
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
            tax_rate = 8.0
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
            <cac:TaxScheme><cbc:Name>KDV</cbc:Name><cbc:TaxTypeCode>0015</cbc:TaxTypeCode></cac:TaxScheme>
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
            "status": "built",  # built → submitted → accepted | rejected
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
            {"_id": 0}
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

    return router
