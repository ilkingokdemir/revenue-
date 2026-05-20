"""
Workforce extras — Bordro (Payroll) CSV export + PDF Bordro + Tip Pool distribution.
"""
import csv
import io
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)


# Standard 2026 Turkish payroll deduction rates (employee side, "İşçi Payı")
# Source: Turkish Labour Law (4857 Sayılı İş Kanunu) + 5510 Sayılı SGK Kanunu.
# Numbers reflect default brackets; admins can override via query params.
TR_SGK_RATE = 0.14         # SGK İşçi Payı
TR_UNEMP_RATE = 0.01       # İşsizlik Sigortası İşçi Payı
TR_INCOME_TAX_RATE = 0.15  # Gelir Vergisi (1. dilim)
TR_STAMP_RATE = 0.00759    # Damga Vergisi


def _tr_payroll_breakdown(gross: float, sgk: float = TR_SGK_RATE,
                          unemp: float = TR_UNEMP_RATE,
                          income_tax: float = TR_INCOME_TAX_RATE,
                          stamp: float = TR_STAMP_RATE) -> dict:
    """Return TR Labor Law required pay-stub breakdown.

    Brüt → SGK İşçi Payı → İşsizlik İşçi Payı → Gelir Vergisi Matrahı
         → Gelir Vergisi → Damga Vergisi → Net Ücret
    """
    g = max(0.0, float(gross or 0))
    sgk_amt = round(g * sgk, 2)
    unemp_amt = round(g * unemp, 2)
    tax_base = round(g - sgk_amt - unemp_amt, 2)
    income_tax_amt = round(max(0, tax_base) * income_tax, 2)
    stamp_amt = round(g * stamp, 2)
    net = round(g - sgk_amt - unemp_amt - income_tax_amt - stamp_amt, 2)
    return {
        "brut": g,
        "sgk": sgk_amt, "issizlik": unemp_amt,
        "gelir_matrah": tax_base, "gelir_vergisi": income_tax_amt,
        "damga_vergisi": stamp_amt,
        "net": net,
    }


async def _aggregate_for_payroll(db, property_id: str, month: str = "",
                                 week_start: str = "",
                                 sgk: float = TR_SGK_RATE,
                                 unemp: float = TR_UNEMP_RATE,
                                 income_tax: float = TR_INCOME_TAX_RATE,
                                 stamp: float = TR_STAMP_RATE):
    """Aggregate shift entries → per-staff TR-payroll-ready rows."""
    prop_filter = {} if property_id == "all" else {"property_id": property_id}
    query = {**prop_filter, "status": {"$in": ["completed", "approved"]}}
    if week_start:
        query["week_start"] = week_start
    if month:
        query["date"] = {"$regex": f"^{month}"}
    shifts = await db.shift_entries.find(query, {"_id": 0}).sort("date", 1).to_list(5000)

    per_staff: dict = {}
    for s in shifts:
        sid = s.get("staff_id")
        if not sid:
            continue
        entry = per_staff.setdefault(sid, {
            "staff_id": sid,
            "staff_name": s.get("staff_name", ""),
            "role": s.get("role", ""),
            "shift_count": 0,
            "total_hours": 0.0,
            "total_earned": 0.0,
        })
        entry["shift_count"] += 1
        entry["total_hours"] += float(s.get("hours_worked", 0) or 0)
        entry["total_earned"] += float(s.get("earned_amount", 0) or 0)

    rows = []
    for entry in per_staff.values():
        bd = _tr_payroll_breakdown(entry["total_earned"], sgk, unemp, income_tax, stamp)
        rows.append({**entry, **bd})
    rows.sort(key=lambda r: (r["staff_name"] or "").lower())

    totals = {
        "shift_count": sum(r["shift_count"] for r in rows),
        "total_hours": round(sum(r["total_hours"] for r in rows), 2),
        "brut": round(sum(r["brut"] for r in rows), 2),
        "sgk": round(sum(r["sgk"] for r in rows), 2),
        "issizlik": round(sum(r["issizlik"] for r in rows), 2),
        "gelir_vergisi": round(sum(r["gelir_vergisi"] for r in rows), 2),
        "damga_vergisi": round(sum(r["damga_vergisi"] for r in rows), 2),
        "net": round(sum(r["net"] for r in rows), 2),
    }
    period_label = month or (f"Hafta {week_start}" if week_start else "Tüm dönem")
    prop_doc = None
    if property_id != "all":
        prop_doc = await db.properties.find_one({"id": property_id},
                                                {"_id": 0, "name": 1, "currency": 1})
    return rows, totals, period_label, prop_doc


def create_workforce_extras_router(db, require_roles):
    router = APIRouter()
    # ============== BORDRO CSV EXPORT ==============
    @router.get("/payroll/export/{property_id}")
    async def export_payroll(property_id: str, week_start: str = "", month: str = "",
                             current_user: dict = Depends(require_roles("admin", "manager"))):
        """Generate CSV download for shifts within a week or month."""
        prop_filter = {} if property_id == "all" else {"property_id": property_id}
        query = {**prop_filter, "status": {"$in": ["completed", "approved"]}}
        if week_start:
            query["week_start"] = week_start
        if month:
            query["date"] = {"$regex": f"^{month}"}
        shifts = await db.shift_entries.find(query, {"_id": 0}).sort("date", 1).to_list(5000)

        # Aggregate per staff
        per_staff: dict = {}
        for s in shifts:
            sid = s.get("staff_id")
            if not sid:
                continue
            entry = per_staff.setdefault(sid, {
                "staff_name": s.get("staff_name", ""),
                "role": s.get("role", ""),
                "pay_type": s.get("pay_type", "daily"),
                "pay_rate": float(s.get("pay_rate", 0) or 0),
                "currency": s.get("currency", "GBP"),
                "shift_count": 0,
                "total_hours": 0.0,
                "total_earned": 0.0,
                "shifts": [],
            })
            entry["shift_count"] += 1
            entry["total_hours"] += float(s.get("hours_worked", 0) or 0)
            entry["total_earned"] += float(s.get("earned_amount", 0) or 0)
            entry["shifts"].append(s.get("date", ""))

        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow([
            "Personel", "Rol", "Ödeme Tipi", "Birim Ücret", "Para Birimi",
            "Vardiya Sayısı", "Toplam Saat", "Toplam Kazanç",
        ])
        for entry in per_staff.values():
            writer.writerow([
                entry["staff_name"], entry["role"], entry["pay_type"],
                f"{entry['pay_rate']:.2f}", entry["currency"],
                entry["shift_count"], f"{entry['total_hours']:.2f}",
                f"{entry['total_earned']:.2f}",
            ])
        # Totals row
        writer.writerow([])
        writer.writerow([
            "TOPLAM", "", "", "", "",
            sum(e["shift_count"] for e in per_staff.values()),
            f"{sum(e['total_hours'] for e in per_staff.values()):.2f}",
            f"{sum(e['total_earned'] for e in per_staff.values()):.2f}",
        ])

        buf.seek(0)
        filename = f"bordro_{property_id}_{week_start or month or 'all'}.csv"
        return StreamingResponse(
            iter([buf.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    # ============== BORDRO PREVIEW (JSON) ==============
    @router.get("/payroll/preview/{property_id}")
    async def preview_payroll(property_id: str, month: str = "", week_start: str = "",
                              sgk: float = TR_SGK_RATE, unemp: float = TR_UNEMP_RATE,
                              income_tax: float = TR_INCOME_TAX_RATE,
                              stamp: float = TR_STAMP_RATE,
                              current_user: dict = Depends(require_roles("admin", "manager"))):
        """JSON preview of the monthly bordro with TR labor law deductions.
        Used by frontend before triggering PDF download."""
        rows, totals, period_label, prop_doc = await _aggregate_for_payroll(
            db, property_id, month, week_start,
            sgk=sgk, unemp=unemp, income_tax=income_tax, stamp=stamp
        )
        return {
            "property_id": property_id,
            "property_name": (prop_doc or {}).get("name") or property_id,
            "period": period_label,
            "month": month, "week_start": week_start,
            "currency": (prop_doc or {}).get("currency") or "GBP",
            "deduction_rates": {
                "sgk": sgk, "issizlik": unemp,
                "gelir_vergisi": income_tax, "damga_vergisi": stamp,
            },
            "rows": rows,
            "totals": totals,
        }

    # ============== BORDRO PDF EXPORT ==============
    @router.get("/payroll/export-pdf/{property_id}")
    async def export_payroll_pdf(property_id: str, month: str = "", week_start: str = "",
                                 sgk: float = TR_SGK_RATE, unemp: float = TR_UNEMP_RATE,
                                 income_tax: float = TR_INCOME_TAX_RATE,
                                 stamp: float = TR_STAMP_RATE,
                                 current_user: dict = Depends(require_roles("admin", "manager"))):
        """Generate a TR Labor Law compliant monthly Bordro PDF.

        - Header: Property + period
        - Per-employee breakdown row: Brüt / SGK / İşsizlik / Gelir Vergisi / Damga / Net
        - Footer: Signature areas (İşveren / Personel)
        """
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle,
                                        Paragraph, Spacer, PageBreak)

        rows, totals, period_label, prop_doc = await _aggregate_for_payroll(
            db, property_id, month, week_start,
            sgk=sgk, unemp=unemp, income_tax=income_tax, stamp=stamp
        )
        if not rows:
            raise HTTPException(404, f"Bu dönemde ({period_label}) tamamlanmış vardiya bulunamadı.")

        currency = (prop_doc or {}).get("currency") or "GBP"
        cur_sym = {"GBP": "£", "USD": "$", "EUR": "€", "TRY": "₺"}.get(currency, currency + " ")
        property_name = (prop_doc or {}).get("name") or property_id

        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf, pagesize=landscape(A4),
            leftMargin=12 * mm, rightMargin=12 * mm,
            topMargin=12 * mm, bottomMargin=12 * mm,
            title=f"Bordro {period_label} — {property_name}",
        )
        styles = getSampleStyleSheet()
        small = ParagraphStyle("small", parent=styles["Normal"],
                               fontSize=8, leading=10, textColor=colors.HexColor("#525252"))
        h1 = ParagraphStyle("h1", parent=styles["Heading1"],
                            fontSize=14, leading=16, textColor=colors.HexColor("#0c0a09"))
        muted = ParagraphStyle("muted", parent=styles["Normal"],
                               fontSize=8, textColor=colors.HexColor("#737373"))
        story = []

        # Header
        story.append(Paragraph(f"<b>{property_name.upper()}</b> — ÜCRET BORDROSU", h1))
        story.append(Paragraph(
            f"Dönem: <b>{period_label}</b> · Para Birimi: <b>{currency}</b> · "
            f"Düzenlenme: {datetime.now(timezone.utc).strftime('%d.%m.%Y %H:%M')} UTC · "
            f"Düzenleyen: {current_user.get('name', '-')}", small))
        story.append(Spacer(1, 4 * mm))

        # Deduction policy footnote
        story.append(Paragraph(
            f"Yasal Kesintiler (4857/5510 sayılı kanunlar): "
            f"SGK İşçi %{sgk*100:.2f} · İşsizlik %{unemp*100:.2f} · "
            f"Gelir V. %{income_tax*100:.2f} · Damga V. %{stamp*100:.3f}", muted))
        story.append(Spacer(1, 3 * mm))

        # Main table
        header = ["#", "Personel", "Görev", "Vardiya", "Saat",
                  f"Brüt ({cur_sym})", f"SGK ({cur_sym})",
                  f"İşsizlik ({cur_sym})", f"Gelir V. ({cur_sym})",
                  f"Damga V. ({cur_sym})", f"Net ({cur_sym})", "İmza"]
        data = [header]
        for i, r in enumerate(rows, start=1):
            data.append([
                str(i),
                r["staff_name"] or "-",
                (r["role"] or "-")[:18],
                str(r["shift_count"]),
                f"{r['total_hours']:.1f}",
                f"{r['brut']:.2f}",
                f"{r['sgk']:.2f}",
                f"{r['issizlik']:.2f}",
                f"{r['gelir_vergisi']:.2f}",
                f"{r['damga_vergisi']:.2f}",
                f"{r['net']:.2f}",
                "",  # signature area
            ])
        # Totals row
        data.append([
            "", "TOPLAM", "", str(totals["shift_count"]),
            f"{totals['total_hours']:.1f}",
            f"{totals['brut']:.2f}", f"{totals['sgk']:.2f}",
            f"{totals['issizlik']:.2f}", f"{totals['gelir_vergisi']:.2f}",
            f"{totals['damga_vergisi']:.2f}", f"{totals['net']:.2f}", "",
        ])

        col_widths = [8 * mm, 38 * mm, 24 * mm, 14 * mm, 13 * mm,
                      24 * mm, 22 * mm, 22 * mm, 24 * mm, 22 * mm,
                      26 * mm, 36 * mm]
        tbl = Table(data, colWidths=col_widths, repeatRows=1)
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0c0a09")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 8),
            ("FONTSIZE", (0, 1), (-1, -2), 8),
            ("FONTSIZE", (0, -1), (-1, -1), 9),
            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
            ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#fef3c7")),
            ("ALIGN", (3, 1), (-2, -1), "RIGHT"),
            ("ALIGN", (0, 0), (0, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#a8a29e")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -2),
             [colors.white, colors.HexColor("#fafaf9")]),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(tbl)

        # Footer signature area
        story.append(Spacer(1, 8 * mm))
        sig_table = Table([
            [Paragraph("İşveren / Yetkili İmza ve Kaşe", small),
             "", Paragraph("Personel Tebliğ İmzası", small)],
            ["", "", ""],
            ["_______________________________________", "",
             "_______________________________________"],
            [Paragraph(f"Tarih: {datetime.now(timezone.utc).strftime('%d.%m.%Y')}", small),
             "", Paragraph("Tarih: __________________", small)],
        ], colWidths=[100 * mm, 30 * mm, 100 * mm], rowHeights=[6*mm, 18*mm, 6*mm, 6*mm])
        sig_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ]))
        story.append(sig_table)

        # Final notice
        story.append(Spacer(1, 6 * mm))
        story.append(Paragraph(
            "Bu bordro 4857 sayılı İş Kanunu Madde 32 ve 37 ile 5510 sayılı SGK Kanunu "
            "kapsamında düzenlenmiştir. Personel, ücret hesap pusulasını teslim aldığını "
            "imzasıyla teyit eder. Hesaplanan tutarlar yaklaşık değerlerdir; nihai vergi/SGK "
            "kesintileri muhasebe yazılımının ürettiği bordro üzerinden geçerli olacaktır.",
            muted))

        doc.build(story)
        buf.seek(0)
        filename = f"bordro_{property_id}_{month or week_start or 'all'}.pdf"
        return StreamingResponse(
            iter([buf.getvalue()]),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    # ============== TIP POOL ==============
    @router.post("/tip-pool/distribute")
    async def distribute_tips(data: Dict,
                              current_user: dict = Depends(require_roles("admin", "manager"))):
        """Distribute total tips across staff for a date.
        Three modes:
          - equal: split evenly
          - hours: weighted by hours_worked
          - role: role-based weighting (chef=1.5x, server=1.0x, kds=0.7x, default=1.0x)
        """
        property_id = data.get("property_id", "default")
        date = data.get("date") or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        total_tips = float(data.get("total_tips", 0))
        mode = data.get("mode", "hours")  # equal / hours / role
        role_weights = data.get("role_weights") or {
            "chef": 1.5, "head_chef": 1.7, "server": 1.0, "waiter": 1.0,
            "kds": 0.7, "kitchen": 1.2, "bartender": 1.3, "host": 0.8,
        }

        if total_tips <= 0:
            raise HTTPException(400, "total_tips must be > 0")

        # Get shifts working on that date
        prop_filter = {} if property_id == "all" else {"property_id": property_id}
        shifts = await db.shift_entries.find(
            {**prop_filter, "date": date,
             "status": {"$in": ["completed", "approved", "published", "planned"]}},
            {"_id": 0}
        ).to_list(200)

        if not shifts:
            return {"distributed": 0, "shares": [],
                    "note": f"No shifts on {date} for {property_id}"}

        # Compute weights
        weights = []
        for s in shifts:
            if mode == "equal":
                w = 1.0
            elif mode == "hours":
                w = max(0.5, float(s.get("hours_worked", 0) or 8))
            else:  # role
                role = (s.get("role") or "").lower()
                w = role_weights.get(role, 1.0) * max(0.5, float(s.get("hours_worked", 0) or 8))
            weights.append({"shift": s, "weight": w})
        total_w = sum(w["weight"] for w in weights) or 1
        shares = []
        now = datetime.now(timezone.utc).isoformat()
        for w in weights:
            share = round(total_tips * w["weight"] / total_w, 2)
            shares.append({
                "shift_id": w["shift"].get("id"),
                "staff_id": w["shift"].get("staff_id"),
                "staff_name": w["shift"].get("staff_name"),
                "role": w["shift"].get("role"),
                "hours": w["shift"].get("hours_worked"),
                "weight": round(w["weight"], 2),
                "share": share,
            })

        # Persist tip distribution record
        await db.tip_distributions.insert_one({
            "id": str(uuid.uuid4()),
            "property_id": property_id,
            "date": date,
            "total_tips": total_tips,
            "mode": mode,
            "shares": shares,
            "distributed_by": current_user.get("name", ""),
            "created_at": now,
        })

        return {
            "distributed": len(shares),
            "total_tips": total_tips,
            "mode": mode,
            "shares": sorted(shares, key=lambda x: -x["share"]),
        }

    @router.get("/tip-pool/history/{property_id}")
    async def tip_history(property_id: str, days: int = 30,
                          current_user: dict = Depends(require_roles("admin", "manager"))):
        cutoff = (datetime.now(timezone.utc) - timedelta(days=int(days or 30))).isoformat()
        query = {"created_at": {"$gte": cutoff}}
        if property_id != "all":
            query["property_id"] = property_id
        docs = await db.tip_distributions.find(query, {"_id": 0}).sort(
            "created_at", -1).to_list(100)
        return docs

    return router
