"""
EU Country Compliance — Italy (SDI + Alloggiati), Spain (TicketBai/SES.HOSPEDAJES),
France (Police hôtels), Greece (MyDATA), Hungary (KSZF), Poland (KSeF), Mexico (CFDI).

Each country has 2 kinds of obligations typically:
  A) e-Invoice for financial authorities (XML, country-specific schema)
  B) Police / tourist-guest reporting (TXT/XML/CSV upload to portal)

This module produces export bundles per country — admin downloads and uploads
to the respective portal. Real-time API bridge is a P2 item (per-country SaaS
integrator keys needed).

Design: ONE endpoint per country × obligation, all returning `{xml|txt, filename,
validation, lineCount/totalAmount}`. UI exposes them as collapsed cards per country.
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, date
from typing import Optional, List
from pydantic import BaseModel
import uuid
import csv
import io
import logging

logger = logging.getLogger(__name__)


class CountryExportRequest(BaseModel):
    property_id: str
    country: str  # it / es / fr / gr / hu / pl / mx
    kind: str     # 'invoice' | 'police'
    from_date: str
    to_date: str


# Country catalogue - metadata for UI
COUNTRY_CATALOG = {
    "it": {
        "name": "Italia",
        "flag": "🇮🇹",
        "invoice": {
            "scheme": "FatturaPA 1.2 XML (Sistema di Interscambio / SDI)",
            "format": "xml",
        },
        "police": {
            "scheme": "Alloggiati Web (Polizia di Stato)",
            "format": "txt",
        },
    },
    "es": {
        "name": "España",
        "flag": "🇪🇸",
        "invoice": {
            "scheme": "TicketBai / Verifactu XML (AEAT)",
            "format": "xml",
        },
        "police": {
            "scheme": "SES.HOSPEDAJES (Ministerio del Interior)",
            "format": "csv",
        },
    },
    "fr": {
        "name": "France",
        "flag": "🇫🇷",
        "invoice": {
            "scheme": "Chorus Pro / Factur-X",
            "format": "xml",
        },
        "police": {
            "scheme": "Fiche de police (DGSI / Préfecture)",
            "format": "csv",
        },
    },
    "gr": {
        "name": "Ελλάδα",
        "flag": "🇬🇷",
        "invoice": {
            "scheme": "myDATA (AADE)",
            "format": "xml",
        },
        "police": {
            "scheme": "Tourism Police registry",
            "format": "csv",
        },
    },
    "hu": {
        "name": "Magyarország",
        "flag": "🇭🇺",
        "invoice": {
            "scheme": "KSZF Online Számla",
            "format": "xml",
        },
        "police": None,
    },
    "pl": {
        "name": "Polska",
        "flag": "🇵🇱",
        "invoice": {
            "scheme": "KSeF (Krajowy System e-Faktur)",
            "format": "xml",
        },
        "police": None,
    },
    "mx": {
        "name": "México",
        "flag": "🇲🇽",
        "invoice": {
            "scheme": "CFDI 4.0 (SAT)",
            "format": "xml",
        },
        "police": None,
    },
}


def _fmt_date(d: str) -> str:
    try:
        return datetime.strptime(d, "%Y-%m-%d").strftime("%Y-%m-%d")
    except Exception:
        raise HTTPException(400, "Invalid date — use YYYY-MM-DD")


# ---- Italy SDI / FatturaPA ----
def _build_italy_invoice(booking: dict, property_doc: dict, guest: dict) -> str:
    iva_rate = 10.0  # Italy hotels VAT 10%
    gross = float(booking.get("total_price", 0))
    imponibile = round(gross / (1 + iva_rate / 100), 2)
    imposta = round(gross - imponibile, 2)
    numero = f"H{datetime.now().strftime('%Y%m%d')}{booking.get('id', '')[:6].upper()}"
    piva = property_doc.get("piva") or property_doc.get("vat_id") or "IT00000000000"
    cliente_cf = guest.get("codice_fiscale") or guest.get("tc_kimlik_no") or "XXXXXXXXXXXXXXXX"
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<p:FatturaElettronica xmlns:p="http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2" versione="FPR12">
  <FatturaElettronicaHeader>
    <DatiTrasmissione>
      <IdTrasmittente><IdPaese>IT</IdPaese><IdCodice>{piva.replace("IT","")}</IdCodice></IdTrasmittente>
      <ProgressivoInvio>{booking.get('id','')[:8]}</ProgressivoInvio>
      <FormatoTrasmissione>FPR12</FormatoTrasmissione>
      <CodiceDestinatario>0000000</CodiceDestinatario>
    </DatiTrasmissione>
    <CedentePrestatore>
      <DatiAnagrafici>
        <IdFiscaleIVA><IdPaese>IT</IdPaese><IdCodice>{piva.replace("IT","")}</IdCodice></IdFiscaleIVA>
        <Anagrafica><Denominazione>{property_doc.get("legal_name", property_doc.get("name","Hotel"))}</Denominazione></Anagrafica>
        <RegimeFiscale>RF01</RegimeFiscale>
      </DatiAnagrafici>
    </CedentePrestatore>
    <CessionarioCommittente>
      <DatiAnagrafici>
        <CodiceFiscale>{cliente_cf}</CodiceFiscale>
        <Anagrafica><Denominazione>{booking.get("guest_name","Cliente")}</Denominazione></Anagrafica>
      </DatiAnagrafici>
    </CessionarioCommittente>
  </FatturaElettronicaHeader>
  <FatturaElettronicaBody>
    <DatiGenerali>
      <DatiGeneraliDocumento>
        <TipoDocumento>TD01</TipoDocumento>
        <Divisa>EUR</Divisa>
        <Data>{datetime.now().strftime('%Y-%m-%d')}</Data>
        <Numero>{numero}</Numero>
        <ImportoTotaleDocumento>{gross:.2f}</ImportoTotaleDocumento>
      </DatiGeneraliDocumento>
    </DatiGenerali>
    <DatiBeniServizi>
      <DettaglioLinee>
        <NumeroLinea>1</NumeroLinea>
        <Descrizione>Pernottamento {booking.get('check_in','')} / {booking.get('check_out','')}</Descrizione>
        <Quantita>1.00</Quantita>
        <PrezzoUnitario>{imponibile:.2f}</PrezzoUnitario>
        <PrezzoTotale>{imponibile:.2f}</PrezzoTotale>
        <AliquotaIVA>{iva_rate:.2f}</AliquotaIVA>
      </DettaglioLinee>
      <DatiRiepilogo>
        <AliquotaIVA>{iva_rate:.2f}</AliquotaIVA>
        <ImponibileImporto>{imponibile:.2f}</ImponibileImporto>
        <Imposta>{imposta:.2f}</Imposta>
      </DatiRiepilogo>
    </DatiBeniServizi>
  </FatturaElettronicaBody>
</p:FatturaElettronica>"""
    return xml, numero, gross


# ---- Italy Alloggiati Web (fixed-width, 170 chars per line) ----
def _build_italy_police(booking: dict, guest: dict) -> str:
    """Alloggiati line format (Ministero dell'Interno spec, abbreviated)."""
    # Type 16=check-in normal. Cognome(50) Nome(30) Sesso(1) DataNascita(8) LuogoNascita(9)
    # Nazionalita(9) TipoDocumento(5) NumeroDocumento(20) LuogoRilascio(9) + filler
    t = "16"
    cognome = (guest.get("last_name", "") or "").ljust(50)[:50]
    nome = (guest.get("first_name", "") or "").ljust(30)[:30]
    sesso = (guest.get("gender", "M") or "M")[:1].upper()
    dob = (guest.get("date_of_birth", "") or "").replace("-", "")[:8].ljust(8)
    luogo = (guest.get("birth_place", "") or "")[:9].ljust(9)
    naz = (guest.get("nationality", "IT") or "IT")[:9].ljust(9)
    tipo_doc = (guest.get("id_doc_type", "IDENT") or "IDENT")[:5].ljust(5)
    num_doc = (guest.get("id_doc_no", "") or "")[:20].ljust(20)
    rilascio = (guest.get("id_issuer_place", "") or "")[:9].ljust(9)
    arrivo = (booking.get("check_in", "") or "").replace("-", "")[:8]
    permanenza = "01"  # days
    filler = " " * 19  # total line length 170 chars
    return f"{t}{cognome}{nome}{sesso}{dob}{luogo}{naz}{tipo_doc}{num_doc}{rilascio}{arrivo}{permanenza}{filler}"


# ---- Spain SES.HOSPEDAJES CSV (Real Decreto 933/2021) ----
def _build_spain_police_csv(bookings: list) -> str:
    """Spanish Ministerio del Interior format - 17 fields CSV."""
    out = io.StringIO()
    writer = csv.writer(out, delimiter=";")
    writer.writerow([
        "establecimiento_id", "referencia_reserva", "fecha_entrada", "fecha_salida",
        "num_personas", "num_habitacion", "pais_residencia", "tipo_documento",
        "numero_documento", "apellido1", "apellido2", "nombre", "sexo",
        "fecha_nacimiento", "pais_nacionalidad", "direccion", "forma_pago",
    ])
    for b in bookings:
        g = b.get("_guest", {}) or {}
        writer.writerow([
            b.get("property_id", ""),
            b.get("id", "")[:20],
            b.get("check_in", ""),
            b.get("check_out", ""),
            b.get("guests", 1),
            b.get("room_name", ""),
            g.get("country", "ES"),
            g.get("id_doc_type", "DNI"),
            g.get("id_doc_no", ""),
            g.get("last_name", ""),
            g.get("second_last_name", ""),
            g.get("first_name", ""),
            g.get("gender", "M"),
            g.get("date_of_birth", ""),
            g.get("nationality", "ES"),
            g.get("address", ""),
            b.get("payment_method", "card"),
        ])
    return out.getvalue()


# ---- France fiche de police CSV (stripped) ----
def _build_france_police_csv(bookings: list) -> str:
    out = io.StringIO()
    writer = csv.writer(out, delimiter=";")
    writer.writerow([
        "nom", "prenom", "date_naissance", "lieu_naissance", "nationalite",
        "domicile", "date_arrivee", "date_depart", "numero_chambre", "piece_identite",
    ])
    for b in bookings:
        g = b.get("_guest", {}) or {}
        writer.writerow([
            g.get("last_name", ""), g.get("first_name", ""),
            g.get("date_of_birth", ""), g.get("birth_place", ""),
            g.get("nationality", ""), g.get("address", ""),
            b.get("check_in", ""), b.get("check_out", ""),
            b.get("room_name", ""), g.get("id_doc_no", ""),
        ])
    return out.getvalue()


# ---- Greek tourism police CSV ----
def _build_greece_police_csv(bookings: list) -> str:
    out = io.StringIO()
    writer = csv.writer(out, delimiter=";")
    writer.writerow([
        "hotel_id", "booking_ref", "guest_surname", "guest_name", "passport_no",
        "nationality", "arrival_date", "departure_date", "room_no",
    ])
    for b in bookings:
        g = b.get("_guest", {}) or {}
        writer.writerow([
            b.get("property_id", ""), b.get("id", "")[:12],
            g.get("last_name", ""), g.get("first_name", ""),
            g.get("id_doc_no", ""), g.get("nationality", "GR"),
            b.get("check_in", ""), b.get("check_out", ""),
            b.get("room_name", ""),
        ])
    return out.getvalue()


# ---- Generic UBL-style EU invoice (Hungary/Poland/Mexico/Greece/France/Spain short-form) ----
def _build_generic_eu_invoice(booking: dict, property_doc: dict, guest: dict, country: str) -> tuple:
    rate_map = {"es": 10.0, "fr": 10.0, "gr": 13.0, "hu": 18.0, "pl": 8.0, "mx": 16.0}
    vat_rate = rate_map.get(country, 10.0)
    gross = float(booking.get("total_price", 0))
    net = round(gross / (1 + vat_rate / 100), 2)
    vat = round(gross - net, 2)
    currency_map = {"es": "EUR", "fr": "EUR", "gr": "EUR", "hu": "HUF", "pl": "PLN", "mx": "MXN"}
    currency = currency_map.get(country, "EUR")
    numero = f"H-{country.upper()}-{datetime.now().strftime('%Y%m%d')}-{booking.get('id','')[:6].upper()}"
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
         xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
         xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
  <cbc:UBLVersionID>2.1</cbc:UBLVersionID>
  <cbc:ProfileID>urn:fdc:peppol.eu:2017:poacc:billing:01:1.0</cbc:ProfileID>
  <cbc:ID>{numero}</cbc:ID>
  <cbc:IssueDate>{datetime.now().strftime('%Y-%m-%d')}</cbc:IssueDate>
  <cbc:InvoiceTypeCode>380</cbc:InvoiceTypeCode>
  <cbc:DocumentCurrencyCode>{currency}</cbc:DocumentCurrencyCode>
  <cac:AccountingSupplierParty><cac:Party>
    <cac:PartyName><cbc:Name>{property_doc.get("name","Hotel")}</cbc:Name></cac:PartyName>
    <cac:PartyTaxScheme>
      <cbc:CompanyID>{property_doc.get("vat_id", property_doc.get("piva","000000000"))}</cbc:CompanyID>
      <cac:TaxScheme><cbc:ID>VAT</cbc:ID></cac:TaxScheme>
    </cac:PartyTaxScheme>
  </cac:Party></cac:AccountingSupplierParty>
  <cac:AccountingCustomerParty><cac:Party>
    <cac:PartyName><cbc:Name>{booking.get("guest_name","Customer")}</cbc:Name></cac:PartyName>
  </cac:Party></cac:AccountingCustomerParty>
  <cac:TaxTotal>
    <cbc:TaxAmount currencyID="{currency}">{vat:.2f}</cbc:TaxAmount>
  </cac:TaxTotal>
  <cac:LegalMonetaryTotal>
    <cbc:LineExtensionAmount currencyID="{currency}">{net:.2f}</cbc:LineExtensionAmount>
    <cbc:TaxExclusiveAmount currencyID="{currency}">{net:.2f}</cbc:TaxExclusiveAmount>
    <cbc:TaxInclusiveAmount currencyID="{currency}">{gross:.2f}</cbc:TaxInclusiveAmount>
    <cbc:PayableAmount currencyID="{currency}">{gross:.2f}</cbc:PayableAmount>
  </cac:LegalMonetaryTotal>
  <cac:InvoiceLine>
    <cbc:ID>1</cbc:ID>
    <cbc:InvoicedQuantity unitCode="C62">1</cbc:InvoicedQuantity>
    <cbc:LineExtensionAmount currencyID="{currency}">{net:.2f}</cbc:LineExtensionAmount>
    <cac:Item><cbc:Name>Accommodation {booking.get('check_in','')} - {booking.get('check_out','')}</cbc:Name></cac:Item>
    <cac:Price><cbc:PriceAmount currencyID="{currency}">{net:.2f}</cbc:PriceAmount></cac:Price>
  </cac:InvoiceLine>
</Invoice>"""
    return xml, numero, gross


def create_eu_compliance_router(db, require_roles):
    router = APIRouter()

    @router.get("/eu-compliance/catalog")
    async def get_catalog(current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        return {"countries": COUNTRY_CATALOG}

    @router.post("/eu-compliance/export")
    async def eu_export(req: CountryExportRequest,
                        current_user: dict = Depends(require_roles("admin", "manager"))):
        if req.country not in COUNTRY_CATALOG:
            raise HTTPException(400, f"Unsupported country: {req.country}")
        if req.kind not in ("invoice", "police"):
            raise HTTPException(400, "kind must be 'invoice' or 'police'")

        f, t = _fmt_date(req.from_date), _fmt_date(req.to_date)

        country_meta = COUNTRY_CATALOG[req.country]
        if req.kind == "police" and country_meta.get("police") is None:
            raise HTTPException(400, f"{req.country.upper()} does not require police reporting")

        bookings = await db.bookings.find({
            "property_id": req.property_id,
            "check_in": {"$gte": f, "$lte": t},
            "status": {"$in": ["confirmed", "checked_in", "checked_out"]},
        }, {"_id": 0}).to_list(2000)

        # Hydrate with guest
        for b in bookings:
            g = await db.guest_profiles.find_one({"id": b.get("guest_id")}, {"_id": 0}) or {}
            if not g.get("first_name"):
                gn = (b.get("guest_name") or "").split(" ", 1)
                g["first_name"] = gn[0] if gn else ""
                g["last_name"] = gn[1] if len(gn) > 1 else ""
            b["_guest"] = g

        property_doc = await db.properties.find_one(
            {"id": req.property_id}, {"_id": 0}
        ) or {}

        if req.kind == "invoice":
            # One file per booking bundled as a single tar-like text concat
            # with separator, or build one "batch" per booking. For simplicity,
            # return list of files.
            files = []
            total = 0.0
            for b in bookings:
                try:
                    if req.country == "it":
                        xml, num, gross = _build_italy_invoice(b, property_doc, b["_guest"])
                    else:
                        xml, num, gross = _build_generic_eu_invoice(b, property_doc, b["_guest"], req.country)
                    files.append({"filename": f"{num}.xml", "content": xml, "total": gross})
                    total += gross
                except Exception as ex:
                    logger.warning(f"Failed invoice for {b.get('id')}: {ex}")
            export_id = str(uuid.uuid4())
            await db.eu_exports.insert_one({
                "id": export_id, "property_id": req.property_id,
                "country": req.country, "kind": "invoice",
                "from_date": f, "to_date": t,
                "file_count": len(files), "total_amount": round(total, 2),
                "created_at": datetime.now(timezone.utc).isoformat(),
                "created_by": current_user.get("email"),
            })
            return {
                "export_id": export_id,
                "country": req.country,
                "country_name": country_meta["name"],
                "scheme": country_meta["invoice"]["scheme"],
                "file_count": len(files),
                "total_amount": round(total, 2),
                "files": files,
            }
        else:  # police
            if req.country == "it":
                lines = [_build_italy_police(b, b["_guest"]) for b in bookings if b["_guest"].get("id_doc_no")]
                content = "\n".join(lines)
                filename = f"alloggiati_{req.property_id}_{f}_{t}.txt"
            elif req.country == "es":
                content = _build_spain_police_csv(bookings)
                filename = f"ses_hospedajes_{req.property_id}_{f}_{t}.csv"
            elif req.country == "fr":
                content = _build_france_police_csv(bookings)
                filename = f"fiche_police_{req.property_id}_{f}_{t}.csv"
            elif req.country == "gr":
                content = _build_greece_police_csv(bookings)
                filename = f"tourism_police_{req.property_id}_{f}_{t}.csv"
            else:
                raise HTTPException(400, f"{req.country} police format not implemented")

            row_count = len(content.splitlines()) - (0 if req.country == "it" else 1)
            export_id = str(uuid.uuid4())
            await db.eu_exports.insert_one({
                "id": export_id, "property_id": req.property_id,
                "country": req.country, "kind": "police",
                "from_date": f, "to_date": t,
                "row_count": row_count,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "created_by": current_user.get("email"),
            })
            return {
                "export_id": export_id,
                "country": req.country,
                "country_name": country_meta["name"],
                "scheme": country_meta["police"]["scheme"],
                "format": country_meta["police"]["format"],
                "row_count": row_count,
                "content": content,
                "filename": filename,
            }

    @router.get("/eu-compliance/{property_id}/history")
    async def eu_history(property_id: str, country: Optional[str] = None,
                         current_user: dict = Depends(require_roles("admin", "manager"))):
        q = {"property_id": property_id}
        if country:
            q["country"] = country
        rows = await db.eu_exports.find(q, {"_id": 0}).sort("created_at", -1).limit(100).to_list(100)
        return {"history": rows}

    return router
