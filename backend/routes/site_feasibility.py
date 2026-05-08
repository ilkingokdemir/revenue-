"""
Site Feasibility & Investor Analysis — replicates the SE17 Pasha-style hotel
investment study inside our PMS.

Generates:
- Comp-set scrape window (mock Booking.com data, real key-gated)
- ADR curves & day-of-week structure
- 4× lease cost hurdle test
- Per-key economics
- Occupancy sensitivity (+/- 5 pp scenarios)
- Wholesaler / OTA haircut risk simulation
- Year-1 ramp-up working capital model
- AI investor verdict (LLM narrative)
- Investor-style PDF export

Endpoints
---------
POST   /feasibility/analysis                 create a study
GET    /feasibility/analyses/{property_id}   list studies
GET    /feasibility/analysis/{id}            single study
PUT    /feasibility/analysis/{id}            edit inputs
DELETE /feasibility/analysis/{id}            remove
POST   /feasibility/analysis/{id}/scrape     mock Booking.com comp scrape
GET    /feasibility/analysis/{id}/hurdle     4× lease hurdle test
GET    /feasibility/analysis/{id}/sensitivity occupancy sensitivity grid
GET    /feasibility/analysis/{id}/ramp-up    Y1 ramp-up working capital
GET    /feasibility/analysis/{id}/ota-risk   wholesaler/OTA haircut risk
GET    /feasibility/analysis/{id}/adr-curve  day-of-week ADR curve
POST   /feasibility/analysis/{id}/verdict    AI investor verdict (LLM)
GET    /feasibility/analysis/{id}/pdf        full investor PDF
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from datetime import datetime, timezone
from typing import List, Optional
import io
import os
import uuid
import math
import logging

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

logger = logging.getLogger(__name__)


class CompetitorHotel(BaseModel):
    name: str
    booking_url: Optional[str] = None
    rooms: Optional[int] = None
    adr: Optional[float] = None         # GBP / EUR / TRY — caller's currency
    occupancy_pct: Optional[float] = None  # 0-100
    excluded: bool = False
    exclude_reason: Optional[str] = None  # e.g. "single-flat homestay"


class FeasibilityCreateReq(BaseModel):
    property_id: str
    project_name: str
    location: str
    currency: str = "GBP"
    rooms: int = Field(..., ge=1)
    target_adr: float = Field(..., gt=0)
    target_occupancy_pct: float = Field(75.0, ge=0, le=100)
    annual_lease_cost: float = Field(0.0, ge=0)
    lease_multiple_target: float = Field(4.0, gt=0)  # 4× turnover hurdle
    ota_commission_pct: float = Field(15.0, ge=0, le=50)
    wholesaler_share_pct: float = Field(10.0, ge=0, le=100)
    wholesaler_haircut_pct: float = Field(10.0, ge=0, le=50)
    ramp_up_months: int = Field(15, ge=0, le=36)  # months to stabilised occupancy
    ramp_start_occupancy_pct: float = Field(40.0, ge=0, le=100)
    comp_set: List[CompetitorHotel] = []
    notes: Optional[str] = None


class FeasibilityUpdateReq(FeasibilityCreateReq):
    pass


# ---------------------------------------------------------------------------
# math helpers
# ---------------------------------------------------------------------------
def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _annual_turnover(adr: float, occupancy_pct: float, rooms: int) -> float:
    return round(adr * (occupancy_pct / 100) * rooms * 365, 2)


def _hurdle_test(adr: float, occupancy_pct: float, rooms: int,
                 lease: float, target_mult: float) -> dict:
    turnover = _annual_turnover(adr, occupancy_pct, rooms)
    hurdle = lease * target_mult
    headroom = round(turnover - hurdle, 2)
    multiple = round(turnover / lease, 2) if lease > 0 else None
    return {
        "annual_turnover": turnover,
        "lease_cost": lease,
        "hurdle_target": round(hurdle, 2),
        "headroom": headroom,
        "lease_multiple": multiple,
        "passes": headroom >= 0,
        "verdict": _hurdle_verdict(headroom, hurdle),
    }


def _hurdle_verdict(headroom: float, hurdle: float) -> str:
    if hurdle <= 0:
        return "no-lease"
    pct = (headroom / hurdle) * 100
    if pct < 0:
        return "fails"
    if pct < 5:
        return "on-the-line"
    if pct < 15:
        return "marginal-pass"
    return "comfortable-pass"


def _per_key(adr: float, occupancy_pct: float) -> float:
    """Per-key annual revenue."""
    return round(adr * (occupancy_pct / 100) * 365, 2)


def _sensitivity(req: dict, span: int = 5) -> List[dict]:
    """Generate +/- span pp occupancy scenarios in 1pp steps."""
    base_occ = req["target_occupancy_pct"]
    out = []
    for delta in range(-span, span + 1):
        occ = max(0.0, min(100.0, base_occ + delta))
        turnover = _annual_turnover(req["target_adr"], occ, req["rooms"])
        out.append({
            "occupancy_pct": round(occ, 1),
            "delta_pp": delta,
            "annual_turnover": turnover,
            "headroom": round(turnover - req["annual_lease_cost"] * req["lease_multiple_target"], 2),
            "passes": turnover >= req["annual_lease_cost"] * req["lease_multiple_target"],
        })
    return out


def _ota_risk(req: dict) -> dict:
    """Apply wholesaler haircut to the wholesaler-share portion of revenue."""
    occ = req["target_occupancy_pct"]
    base = _annual_turnover(req["target_adr"], occ, req["rooms"])
    ws_share = req["wholesaler_share_pct"] / 100
    haircut = req["wholesaler_haircut_pct"] / 100
    revenue_after = base * (1 - ws_share * haircut)
    revenue_loss = round(base - revenue_after, 2)
    hurdle = req["annual_lease_cost"] * req["lease_multiple_target"]
    after_headroom = round(revenue_after - hurdle, 2)
    ota_commission = round(base * req["ota_commission_pct"] / 100, 2)
    return {
        "base_turnover": base,
        "wholesaler_share_pct": req["wholesaler_share_pct"],
        "wholesaler_haircut_pct": req["wholesaler_haircut_pct"],
        "revenue_loss_to_wholesaler": revenue_loss,
        "turnover_after_haircut": round(revenue_after, 2),
        "ota_commission_loss": ota_commission,
        "net_after_commission": round(revenue_after - ota_commission, 2),
        "headroom_after_haircut": after_headroom,
        "still_passes": after_headroom >= 0,
    }


def _ramp_up(req: dict) -> dict:
    """Linear ramp from start_occupancy to target over ramp_up_months."""
    months = req["ramp_up_months"]
    start = req["ramp_start_occupancy_pct"]
    target = req["target_occupancy_pct"]
    rooms = req["rooms"]
    adr = req["target_adr"]
    lease_per_month = req["annual_lease_cost"] / 12
    schedule = []
    cumulative_shortfall = 0.0
    for m in range(1, max(months, 1) + 1):
        if months <= 1:
            occ = target
        else:
            occ = start + (target - start) * ((m - 1) / max(months - 1, 1))
        monthly_revenue = adr * (occ / 100) * rooms * 30
        # OPEX assumed to scale at 60% of revenue for upper-mid hotel
        opex = monthly_revenue * 0.60
        net = monthly_revenue - opex - lease_per_month
        if net < 0:
            cumulative_shortfall += -net
        schedule.append({
            "month": m,
            "occupancy_pct": round(occ, 1),
            "revenue": round(monthly_revenue, 2),
            "opex": round(opex, 2),
            "lease": round(lease_per_month, 2),
            "net": round(net, 2),
        })
    return {
        "months": months,
        "ramp_start_occupancy_pct": start,
        "target_occupancy_pct": target,
        "schedule": schedule,
        "working_capital_required": round(cumulative_shortfall, 2),
        "explanation": (
            f"Linear ramp-up across {months} months from {start}% to {target}%. "
            f"OPEX assumed at 60% of revenue. Required working capital to cover "
            f"shortfall before stabilisation = {round(cumulative_shortfall,2):,.2f}."
        ),
    }


def _adr_curve(req: dict) -> dict:
    """Synthetic ADR curve by day-of-week (until real Booking.com scrape)."""
    base = req["target_adr"]
    # Mid-scale London-style pattern: weekend uplift, Sun dip
    weights = {"Mon": 0.92, "Tue": 0.95, "Wed": 0.97, "Thu": 1.05, "Fri": 1.18, "Sat": 1.20, "Sun": 0.93}
    return {
        "currency": req.get("currency", "GBP"),
        "target_adr": base,
        "by_dow": {dow: round(base * w, 2) for dow, w in weights.items()},
        "weekly_avg": round(sum(base * w for w in weights.values()) / 7, 2),
        "note": "Synthetic ADR curve based on upper-midscale weekly pattern. "
                "Connect real Booking.com scrape for live data.",
    }


def _scrape_mock(req: dict) -> dict:
    """Mock Booking.com scrape returning estimated comp-set occupancy with ±5% band."""
    import random
    rng = random.Random(req["property_id"])  # deterministic per property
    out = []
    for c in req.get("comp_set", []):
        if c.get("excluded"):
            continue
        occ = c.get("occupancy_pct") or rng.uniform(78, 90)
        adr = c.get("adr") or req["target_adr"] * rng.uniform(0.8, 1.4)
        out.append({
            "name": c["name"],
            "estimated_adr": round(adr, 2),
            "estimated_occupancy_pct": round(occ, 1),
            "confidence_band_pp": 5.0,
            "rooms": c.get("rooms"),
            "revpar": round(adr * occ / 100, 2),
        })
    avg_adr = round(sum(r["estimated_adr"] for r in out) / len(out), 2) if out else 0
    avg_occ = round(sum(r["estimated_occupancy_pct"] for r in out) / len(out), 1) if out else 0
    return {
        "scrape_window": "next 30 nights",
        "comp_results": out,
        "comp_avg_adr": avg_adr,
        "comp_avg_occupancy": avg_occ,
        "scraped_at": _now(),
        "source": "mock-scrape (provide Booking.com partner key to switch live)",
    }


# ---------------------------------------------------------------------------
# AI verdict via Emergent LLM
# ---------------------------------------------------------------------------
async def _llm_verdict(req: dict, hurdle: dict, sens: list, ota: dict) -> dict:
    """Build an investor-style narrative using Emergent LLM."""
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
    except Exception:
        return {
            "narrative": "LLM library not available.",
            "confidence": 0.0,
            "available": False,
        }

    api_key = os.environ.get("EMERGENT_LLM_KEY")
    if not api_key:
        return {
            "narrative": "EMERGENT_LLM_KEY missing — verdict generation disabled.",
            "confidence": 0.0,
            "available": False,
        }

    sess = f"feasibility-{uuid.uuid4().hex[:8]}"
    chat = LlmChat(
        api_key=api_key,
        session_id=sess,
        system_message=(
            "You are a hotel investment analyst writing a one-paragraph verdict "
            "for the cover of an investor study. Cite the 4× lease hurdle, headroom, "
            "occupancy sensitivity, and wholesaler risk. Tone: direct, professional, "
            "no marketing fluff. 4–6 sentences max. Use the report's currency. "
            "End with a clear go/no-go recommendation. Reply in the same language as the project name."
        ),
    ).with_model("openai", "gpt-4o-mini")

    user_msg = UserMessage(text=(
        f"Project: {req['project_name']} ({req['location']})\n"
        f"Rooms: {req['rooms']}, target ADR: {req['target_adr']} {req['currency']}, "
        f"target occupancy: {req['target_occupancy_pct']}%\n"
        f"Annual lease: {req['annual_lease_cost']} {req['currency']}, "
        f"target multiple: {req['lease_multiple_target']}×\n"
        f"Hurdle test → turnover {hurdle['annual_turnover']}, hurdle {hurdle['hurdle_target']}, "
        f"headroom {hurdle['headroom']}, verdict: {hurdle['verdict']}\n"
        f"Sensitivity (best/worst): {sens[0]['headroom']} / {sens[-1]['headroom']}\n"
        f"OTA/wholesaler risk → loss {ota['revenue_loss_to_wholesaler']}, "
        f"still passes? {ota['still_passes']}\n"
        f"Comp set: {len(req.get('comp_set', []))} hotels\n"
        f"Write the investor verdict now."
    ))

    try:
        response = await chat.send_message(user_msg)
        text = response if isinstance(response, str) else getattr(response, "content", str(response))
        return {"narrative": text.strip(), "confidence": 0.78, "available": True, "model": "gpt-4o-mini"}
    except Exception as e:
        logger.error(f"LLM verdict failed: {e}")
        return {
            "narrative": f"LLM call failed: {e}",
            "confidence": 0.0,
            "available": False,
        }


# ---------------------------------------------------------------------------
# PDF rendering
# ---------------------------------------------------------------------------
def _render_pdf(study: dict) -> bytes:
    buf = io.BytesIO()
    pdf = SimpleDocTemplate(buf, pagesize=A4,
                            rightMargin=15 * mm, leftMargin=15 * mm,
                            topMargin=14 * mm, bottomMargin=14 * mm)
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=styles["Heading1"], fontSize=18,
                        textColor=colors.HexColor("#0f172a"), spaceAfter=4)
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], fontSize=12,
                        textColor=colors.HexColor("#334155"), spaceBefore=10, spaceAfter=4)
    body = ParagraphStyle("body", parent=styles["BodyText"], fontSize=9.5,
                          textColor=colors.HexColor("#1e293b"), leading=12)
    small = ParagraphStyle("small", parent=body, fontSize=8,
                           textColor=colors.HexColor("#64748b"))
    verdict_st = ParagraphStyle("verdict", parent=body, fontSize=10.5,
                                textColor=colors.HexColor("#0f172a"), leading=14,
                                backColor=colors.HexColor("#fef9c3"),
                                borderPadding=8, spaceBefore=6, spaceAfter=6)

    e = []
    cur = study.get("currency", "")
    e.append(Paragraph("<b>SITE FEASIBILITY · INVESTOR ANALYSIS</b>", h1))
    e.append(Paragraph(f"{study['project_name']} — {study['location']}", body))
    e.append(Paragraph(
        f"Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} · "
        f"Study {study['id'][:8]}", small))
    e.append(Spacer(1, 6))

    # Verdict at the top
    if study.get("verdict_narrative"):
        e.append(Paragraph("<b>INVESTOR VERDICT</b>", h2))
        e.append(Paragraph(study["verdict_narrative"], verdict_st))

    # Headline numbers
    h = study.get("hurdle", {})
    e.append(Paragraph("HEADLINE ECONOMICS", h2))
    rows = [
        ["Rooms", f"{study['rooms']}"],
        ["Target ADR", f"{study['target_adr']:,.2f} {cur}"],
        ["Target occupancy", f"{study['target_occupancy_pct']:.1f}%"],
        ["Annual turnover", f"{h.get('annual_turnover',0):,.2f} {cur}"],
        ["Annual lease", f"{study['annual_lease_cost']:,.2f} {cur}"],
        ["Hurdle target ({}×)".format(study["lease_multiple_target"]),
            f"{h.get('hurdle_target',0):,.2f} {cur}"],
        ["Headroom", f"{h.get('headroom',0):,.2f} {cur}"],
        ["Lease multiple", f"{h.get('lease_multiple','—')}×"],
        ["Per-key revenue", f"{study.get('per_key_revenue',0):,.2f} {cur}"],
        ["Verdict", h.get("verdict", "—").upper()],
    ]
    t = Table(rows, colWidths=[55 * mm, 110 * mm])
    t.setStyle(_grid_style())
    e.append(t)

    # Comp set
    if study.get("scrape", {}).get("comp_results"):
        e.append(Paragraph("COMP SET (Booking.com scrape window)", h2))
        cs = [["Hotel", "ADR", "Occ %", "RevPAR"]]
        for r in study["scrape"]["comp_results"]:
            cs.append([r["name"], f"{r['estimated_adr']:,.2f}",
                       f"{r['estimated_occupancy_pct']:.1f}%",
                       f"{r['revpar']:,.2f}"])
        cs.append(["AVERAGE", f"{study['scrape']['comp_avg_adr']:,.2f}",
                   f"{study['scrape']['comp_avg_occupancy']:.1f}%", "—"])
        ct = Table(cs, colWidths=[60 * mm, 35 * mm, 30 * mm, 35 * mm])
        ct.setStyle(_grid_style())
        e.append(ct)

    # Sensitivity
    if study.get("sensitivity"):
        e.append(Paragraph("OCCUPANCY SENSITIVITY (±5 pp)", h2))
        ss = [["Δ pp", "Occ %", "Turnover", "Headroom", "Pass?"]]
        for s in study["sensitivity"]:
            ss.append([f"{s['delta_pp']:+d}", f"{s['occupancy_pct']:.1f}%",
                       f"{s['annual_turnover']:,.0f}",
                       f"{s['headroom']:,.0f}",
                       "✓" if s["passes"] else "✗"])
        st = Table(ss, colWidths=[20 * mm, 30 * mm, 40 * mm, 40 * mm, 25 * mm])
        st.setStyle(_grid_style())
        e.append(st)

    # OTA risk
    o = study.get("ota_risk", {})
    if o:
        e.append(Paragraph("OTA / WHOLESALER HAIRCUT RISK", h2))
        rr = [
            ["Wholesaler share", f"{o.get('wholesaler_share_pct',0):.1f}%"],
            ["Haircut applied", f"{o.get('wholesaler_haircut_pct',0):.1f}%"],
            ["Revenue loss to wholesaler", f"{o.get('revenue_loss_to_wholesaler',0):,.2f} {cur}"],
            ["OTA commission loss", f"{o.get('ota_commission_loss',0):,.2f} {cur}"],
            ["Turnover after haircut", f"{o.get('turnover_after_haircut',0):,.2f} {cur}"],
            ["Headroom after haircut", f"{o.get('headroom_after_haircut',0):,.2f} {cur}"],
            ["Still passes hurdle", "YES" if o.get("still_passes") else "NO"],
        ]
        rt = Table(rr, colWidths=[60 * mm, 105 * mm])
        rt.setStyle(_grid_style())
        e.append(rt)

    # Ramp-up
    r = study.get("ramp_up", {})
    if r:
        e.append(Paragraph("YEAR-1 RAMP-UP & WORKING CAPITAL", h2))
        e.append(Paragraph(r.get("explanation", ""), body))
        rs = [["Month", "Occ %", "Revenue", "OPEX", "Lease", "Net"]]
        for s in r.get("schedule", [])[:18]:
            rs.append([str(s["month"]), f"{s['occupancy_pct']:.1f}%",
                       f"{s['revenue']:,.0f}", f"{s['opex']:,.0f}",
                       f"{s['lease']:,.0f}", f"{s['net']:,.0f}"])
        rt2 = Table(rs, colWidths=[20*mm, 25*mm, 30*mm, 30*mm, 25*mm, 30*mm])
        rt2.setStyle(_grid_style())
        e.append(rt2)
        e.append(Paragraph(
            f"<b>Working capital required:</b> {r.get('working_capital_required',0):,.2f} {cur}",
            body))

    # ADR curve
    a = study.get("adr_curve", {})
    if a:
        e.append(Paragraph("ADR CURVE — DAY-OF-WEEK STRUCTURE", h2))
        ar = [["Day", "ADR"]]
        for d, v in a.get("by_dow", {}).items():
            ar.append([d, f"{v:,.2f} {cur}"])
        ar.append(["Weekly avg", f"{a.get('weekly_avg',0):,.2f} {cur}"])
        at = Table(ar, colWidths=[60 * mm, 105 * mm])
        at.setStyle(_grid_style())
        e.append(at)
        e.append(Paragraph(a.get("note", ""), small))

    if study.get("notes"):
        e.append(Paragraph("ANALYST NOTES", h2))
        e.append(Paragraph(study["notes"], body))

    e.append(Spacer(1, 8))
    e.append(Paragraph(
        "This study is generated from in-PMS data and a synthetic comp-scrape model. "
        "Numbers should be validated against a live channel-manager feed and a "
        "physical site visit before commitment.", small))

    pdf.build(e)
    return buf.getvalue()


def _grid_style() -> TableStyle:
    return TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.HexColor("#94a3b8")),
        ("LINEBELOW", (0, 1), (-1, -1), 0.25, colors.HexColor("#e2e8f0")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ])


# ---------------------------------------------------------------------------
# router factory
# ---------------------------------------------------------------------------
def create_site_feasibility_router(db, require_roles):
    router = APIRouter()

    @router.post("/feasibility/analysis")
    async def create_study(req: FeasibilityCreateReq,
                           current_user: dict = Depends(require_roles("admin", "manager"))):
        doc = req.model_dump()
        doc.update({
            "id": str(uuid.uuid4()),
            "created_at": _now(),
            "created_by": current_user.get("email"),
            "updated_at": _now(),
        })
        # Pre-compute all derived sections so the UI loads instantly
        doc["hurdle"] = _hurdle_test(doc["target_adr"], doc["target_occupancy_pct"],
                                     doc["rooms"], doc["annual_lease_cost"],
                                     doc["lease_multiple_target"])
        doc["per_key_revenue"] = _per_key(doc["target_adr"], doc["target_occupancy_pct"])
        doc["sensitivity"] = _sensitivity(doc)
        doc["ota_risk"] = _ota_risk(doc)
        doc["ramp_up"] = _ramp_up(doc)
        doc["adr_curve"] = _adr_curve(doc)
        doc["scrape"] = _scrape_mock(doc)
        await db.feasibility_studies.insert_one(dict(doc))
        doc.pop("_id", None)
        return doc

    @router.get("/feasibility/analyses/{property_id}")
    async def list_studies(property_id: str,
                           current_user: dict = Depends(require_roles("admin", "manager"))):
        items = await db.feasibility_studies.find(
            {"property_id": property_id}, {"_id": 0}
        ).sort("created_at", -1).to_list(200)
        return {"items": items, "count": len(items)}

    @router.get("/feasibility/analysis/{study_id}")
    async def get_study(study_id: str,
                        current_user: dict = Depends(require_roles("admin", "manager"))):
        s = await db.feasibility_studies.find_one({"id": study_id}, {"_id": 0})
        if not s:
            raise HTTPException(404, "not found")
        return s

    @router.put("/feasibility/analysis/{study_id}")
    async def update_study(study_id: str, req: FeasibilityUpdateReq,
                           current_user: dict = Depends(require_roles("admin", "manager"))):
        existing = await db.feasibility_studies.find_one({"id": study_id}, {"_id": 0})
        if not existing:
            raise HTTPException(404, "not found")
        patch = req.model_dump()
        patch["hurdle"] = _hurdle_test(patch["target_adr"], patch["target_occupancy_pct"],
                                       patch["rooms"], patch["annual_lease_cost"],
                                       patch["lease_multiple_target"])
        patch["per_key_revenue"] = _per_key(patch["target_adr"], patch["target_occupancy_pct"])
        patch["sensitivity"] = _sensitivity(patch)
        patch["ota_risk"] = _ota_risk(patch)
        patch["ramp_up"] = _ramp_up(patch)
        patch["adr_curve"] = _adr_curve(patch)
        patch["scrape"] = _scrape_mock(patch)
        patch["updated_at"] = _now()
        patch["updated_by"] = current_user.get("email")
        await db.feasibility_studies.update_one({"id": study_id}, {"$set": patch})
        merged = {**existing, **patch}
        merged.pop("_id", None)
        return merged

    @router.delete("/feasibility/analysis/{study_id}")
    async def delete_study(study_id: str,
                           current_user: dict = Depends(require_roles("admin", "manager"))):
        r = await db.feasibility_studies.delete_one({"id": study_id})
        if r.deleted_count == 0:
            raise HTTPException(404, "not found")
        return {"deleted": study_id}

    @router.post("/feasibility/analysis/{study_id}/scrape")
    async def trigger_scrape(study_id: str,
                             current_user: dict = Depends(require_roles("admin", "manager"))):
        s = await db.feasibility_studies.find_one({"id": study_id}, {"_id": 0})
        if not s:
            raise HTTPException(404, "not found")
        scrape = _scrape_mock(s)
        await db.feasibility_studies.update_one({"id": study_id}, {"$set": {"scrape": scrape}})
        return scrape

    @router.get("/feasibility/analysis/{study_id}/hurdle")
    async def hurdle(study_id: str,
                     current_user: dict = Depends(require_roles("admin", "manager"))):
        s = await db.feasibility_studies.find_one({"id": study_id}, {"_id": 0})
        if not s:
            raise HTTPException(404, "not found")
        return _hurdle_test(s["target_adr"], s["target_occupancy_pct"],
                            s["rooms"], s["annual_lease_cost"],
                            s["lease_multiple_target"])

    @router.get("/feasibility/analysis/{study_id}/sensitivity")
    async def sensitivity(study_id: str, span: int = Query(5, ge=1, le=15),
                          current_user: dict = Depends(require_roles("admin", "manager"))):
        s = await db.feasibility_studies.find_one({"id": study_id}, {"_id": 0})
        if not s:
            raise HTTPException(404, "not found")
        return {"items": _sensitivity(s, span)}

    @router.get("/feasibility/analysis/{study_id}/ramp-up")
    async def ramp_up(study_id: str,
                      current_user: dict = Depends(require_roles("admin", "manager"))):
        s = await db.feasibility_studies.find_one({"id": study_id}, {"_id": 0})
        if not s:
            raise HTTPException(404, "not found")
        return _ramp_up(s)

    @router.get("/feasibility/analysis/{study_id}/ota-risk")
    async def ota_risk(study_id: str,
                       current_user: dict = Depends(require_roles("admin", "manager"))):
        s = await db.feasibility_studies.find_one({"id": study_id}, {"_id": 0})
        if not s:
            raise HTTPException(404, "not found")
        return _ota_risk(s)

    @router.get("/feasibility/analysis/{study_id}/adr-curve")
    async def adr_curve(study_id: str,
                        current_user: dict = Depends(require_roles("admin", "manager"))):
        s = await db.feasibility_studies.find_one({"id": study_id}, {"_id": 0})
        if not s:
            raise HTTPException(404, "not found")
        return _adr_curve(s)

    @router.post("/feasibility/analysis/{study_id}/verdict")
    async def verdict(study_id: str,
                      current_user: dict = Depends(require_roles("admin", "manager"))):
        s = await db.feasibility_studies.find_one({"id": study_id}, {"_id": 0})
        if not s:
            raise HTTPException(404, "not found")
        h = _hurdle_test(s["target_adr"], s["target_occupancy_pct"],
                         s["rooms"], s["annual_lease_cost"],
                         s["lease_multiple_target"])
        sens = _sensitivity(s)
        ota = _ota_risk(s)
        v = await _llm_verdict(s, h, sens, ota)
        await db.feasibility_studies.update_one(
            {"id": study_id},
            {"$set": {"verdict_narrative": v["narrative"],
                      "verdict_confidence": v.get("confidence", 0.0),
                      "verdict_at": _now(),
                      "verdict_by": current_user.get("email")}}
        )
        return v

    @router.get("/feasibility/analysis/{study_id}/pdf")
    async def export_pdf(study_id: str,
                         current_user: dict = Depends(require_roles("admin", "manager"))):
        s = await db.feasibility_studies.find_one({"id": study_id}, {"_id": 0})
        if not s:
            raise HTTPException(404, "not found")
        # Always recompute fresh in case inputs changed
        s["hurdle"] = _hurdle_test(s["target_adr"], s["target_occupancy_pct"],
                                   s["rooms"], s["annual_lease_cost"],
                                   s["lease_multiple_target"])
        s["per_key_revenue"] = _per_key(s["target_adr"], s["target_occupancy_pct"])
        s["sensitivity"] = _sensitivity(s)
        s["ota_risk"] = _ota_risk(s)
        s["ramp_up"] = _ramp_up(s)
        s["adr_curve"] = _adr_curve(s)
        if not s.get("scrape"):
            s["scrape"] = _scrape_mock(s)
        pdf_bytes = _render_pdf(s)
        fname = f"feasibility-{s['project_name'].replace(' ', '-').lower()}-{s['id'][:6]}.pdf"
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{fname}"'},
        )

    @router.get("/feasibility/dashboard/{property_id}")
    async def dashboard(property_id: str,
                        current_user: dict = Depends(require_roles("admin", "manager"))):
        items = await db.feasibility_studies.find(
            {"property_id": property_id}, {"_id": 0}
        ).to_list(200)
        passes = sum(1 for x in items if x.get("hurdle", {}).get("passes"))
        return {
            "total": len(items),
            "passing": passes,
            "failing": len(items) - passes,
            "latest": items[:5],
        }

    return router
