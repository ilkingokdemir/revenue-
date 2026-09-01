"""UK-compliant HR & Payroll — employee lifecycle, NMW age bands, PAYE, NI Class 1, payslips (2026/27)."""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from datetime import datetime, timezone, date
from typing import Dict
import calendar
import io
import os
import uuid
import logging

logger = logging.getLogger(__name__)

try:
    import resend
except Exception:
    resend = None

# ==================== UK 2026/27 CONSTANTS ====================
TAX_YEAR = "2026/27"
NMW_BANDS = [(21, 12.71), (18, 10.85), (0, 8.00)]  # (min_age, hourly rate £)
APPRENTICE_RATE = 8.00
DEFAULT_TAX_CODE = "1257L"
BASIC_LIMIT_M = 37700 / 12
HIGHER_LIMIT_M = 125140 / 12
NI_PT_M = 1048.0          # employee primary threshold / month
NI_UEL_M = 4189.0         # upper earnings limit / month
NI_MAIN, NI_UPPER = 0.08, 0.02
ER_ST_M = 5000 / 12       # employer secondary threshold / month
ER_RATE = 0.15
SL_THRESH_M = {"plan_1": 26065 / 12, "plan_2": 28470 / 12, "plan_4": 32745 / 12, "postgraduate": 21000 / 12}
SL_RATE = {"plan_1": 0.09, "plan_2": 0.09, "plan_4": 0.09, "postgraduate": 0.06}
HOLIDAY_ACCRUAL_PCT = 0.1207  # 12.07% statutory holiday accrual for irregular hours

HR_FIELDS = ["dob", "ni_number", "tax_code", "starter_declaration", "contract_type",
             "start_date", "bank_sort_code", "bank_account_no", "student_loan_plans",
             "is_apprentice", "pension_optin", "address", "postcode", "emergency_contact"]


def _age_on(dob: str, ref: date) -> int | None:
    try:
        d = datetime.strptime(dob[:10], "%Y-%m-%d").date()
        return ref.year - d.year - ((ref.month, ref.day) < (d.month, d.day))
    except Exception:
        return None


def _nmw_rate(age: int | None, apprentice: bool = False) -> float:
    if apprentice:
        return APPRENTICE_RATE
    if age is None:
        age = 21  # assume adult when DOB missing (warning raised separately)
    for min_age, rate in NMW_BANDS:
        if age >= min_age:
            return rate
    return NMW_BANDS[-1][1]


def _parse_tax_code(code: str):
    """Returns (monthly_free_pay, flat_rate_or_None)."""
    c = (code or DEFAULT_TAX_CODE).upper().replace(" ", "")
    for suf in ("W1", "M1", "X"):
        if c.endswith(suf):
            c = c[: -len(suf)]
    c = c.rstrip("/")
    if c == "NT":
        return (0.0, 0.0)
    if c == "BR":
        return (0.0, 0.20)
    if c == "D0":
        return (0.0, 0.40)
    if c == "D1":
        return (0.0, 0.45)
    if c == "0T":
        return (0.0, None)
    negative = c.startswith("K")
    digits = "".join(ch for ch in c if ch.isdigit())
    if not digits:
        return (12579 / 12, None)
    allowance = int(digits) * 10 + 9
    if negative:
        allowance = -allowance
    return (allowance / 12, None)


def _paye(gross_m: float, tax_code: str) -> float:
    free_pay, flat = _parse_tax_code(tax_code)
    if flat is not None:
        return round(gross_m * flat, 2)
    taxable = max(0.0, gross_m - free_pay)
    tax = 0.0
    basic = min(taxable, BASIC_LIMIT_M)
    tax += basic * 0.20
    if taxable > BASIC_LIMIT_M:
        higher = min(taxable, HIGHER_LIMIT_M) - BASIC_LIMIT_M
        tax += higher * 0.40
    if taxable > HIGHER_LIMIT_M:
        tax += (taxable - HIGHER_LIMIT_M) * 0.45
    return round(tax, 2)


def _ni_employee(gross_m: float) -> float:
    ni = 0.0
    if gross_m > NI_PT_M:
        ni += (min(gross_m, NI_UEL_M) - NI_PT_M) * NI_MAIN
    if gross_m > NI_UEL_M:
        ni += (gross_m - NI_UEL_M) * NI_UPPER
    return round(ni, 2)


def _ni_employer(gross_m: float) -> float:
    return round(max(0.0, gross_m - ER_ST_M) * ER_RATE, 2)


def _student_loan(gross_m: float, plans: list) -> float:
    total = 0.0
    for p in plans or []:
        th = SL_THRESH_M.get(p)
        if th and gross_m > th:
            total += (gross_m - th) * SL_RATE[p]
    return round(total, 2)


def _month_bounds(year: int, month: int):
    return date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])


def _tax_year_start(ref: date) -> date:
    return date(ref.year if (ref.month, ref.day) >= (4, 6) else ref.year - 1, 4, 6)


async def _send_email(to_email: str, subject: str, html: str, attachment: tuple | None = None) -> str:
    api_key = os.environ.get("RESEND_API_KEY", "")
    if not resend or not api_key or api_key.startswith("re_1234"):
        logger.info(f"[MOCK EMAIL] to={to_email} subject={subject}")
        return "mocked"
    try:
        import base64
        resend.api_key = api_key
        payload = {
            "from": os.environ.get("RESEND_FROM", "MyHotelBox <onboarding@resend.dev>"),
            "to": [to_email], "subject": subject, "html": html,
        }
        if attachment:
            fname, fbytes = attachment
            payload["attachments"] = [{"filename": fname, "content": base64.b64encode(fbytes).decode()}]
        resend.Emails.send(payload)
        return "sent"
    except Exception as e:
        logger.error(f"payslip email failed: {e}")
        return "error"


def create_uk_payroll_router(db, require_roles):
    router = APIRouter()

    # ==================== RATES REFERENCE ====================
    @router.get("/uk-payroll/rates")
    async def rates(current_user: dict = Depends(require_roles("admin", "manager"))):
        return {
            "tax_year": TAX_YEAR,
            "nmw": {"21_plus": 12.71, "18_20": 10.85, "under_18": 8.00, "apprentice": APPRENTICE_RATE},
            "personal_allowance": 12570, "default_tax_code": DEFAULT_TAX_CODE,
            "ni_employee": {"threshold_monthly": NI_PT_M, "uel_monthly": NI_UEL_M, "main_rate": NI_MAIN, "upper_rate": NI_UPPER},
            "ni_employer": {"threshold_monthly": round(ER_ST_M, 2), "rate": ER_RATE},
            "tax_bands_monthly": {"basic_to": round(BASIC_LIMIT_M, 2), "higher_to": round(HIGHER_LIMIT_M, 2),
                                  "rates": {"basic": 0.20, "higher": 0.40, "additional": 0.45}},
            "holiday_accrual_pct": HOLIDAY_ACCRUAL_PCT,
        }

    # ==================== EMPLOYEES (HR VIEW) ====================
    @router.get("/uk-payroll/employees/{property_id}")
    async def employees(property_id: str, include_leavers: bool = True,
                        current_user: dict = Depends(require_roles("admin", "manager"))):
        query = {} if property_id == "all" else {"property_id": property_id}
        staff = await db.shift_staff.find(query, {"_id": 0}).sort("name", 1).to_list(300)
        # onboarding enrichment via users email match
        emails = [s.get("email") for s in staff if s.get("email")]
        users = await db.users.find({"email": {"$in": emails}}, {"_id": 0, "id": 1, "email": 1}).to_list(300)
        uid_by_email = {u["email"]: u["id"] for u in users}
        onb_docs = await db.staff_onboarding.find(
            {"user_id": {"$in": list(uid_by_email.values())}}, {"_id": 0, "user_id": 1, "hmrc_data": 1, "hmrc_submitted": 1}
        ).to_list(300)
        onb_by_uid = {o["user_id"]: o for o in onb_docs}
        today = datetime.now(timezone.utc).date()
        out = []
        for s in staff:
            onb = onb_by_uid.get(uid_by_email.get(s.get("email", ""), ""), {})
            hmrc = onb.get("hmrc_data", {}) or {}
            dob = s.get("dob") or hmrc.get("dob", "")
            ni = s.get("ni_number") or hmrc.get("ni_number", "")
            age = _age_on(dob, today) if dob else None
            apprentice = bool(s.get("is_apprentice")) or s.get("contract_type") == "apprentice"
            nmw = _nmw_rate(age, apprentice)
            pay_rate = float(s.get("pay_rate", 0) or 0)
            hourly_ok = None
            if s.get("pay_type") == "hourly" and pay_rate > 0:
                hourly_ok = pay_rate >= nmw
            missing = [f for f, v in (("Doğum tarihi", dob), ("NI numarası", ni),
                                      ("Vergi kodu", s.get("tax_code")), ("Banka bilgisi", s.get("bank_account_no")),
                                      ("İşe giriş tarihi", s.get("start_date") or hmrc.get("start_date"))) if not v]
            is_leaver = bool(s.get("leaver_date"))
            if is_leaver and not include_leavers:
                continue
            out.append({**s,
                        "dob": dob, "ni_number": ni,
                        "tax_code": s.get("tax_code") or DEFAULT_TAX_CODE,
                        "start_date": s.get("start_date") or hmrc.get("start_date", ""),
                        "age": age, "nmw_rate": nmw, "nmw_compliant": hourly_ok,
                        "onboarding_submitted": bool(onb.get("hmrc_submitted")),
                        "hr_missing": missing, "hr_complete": len(missing) == 0,
                        "employment_status": "leaver" if is_leaver else "active"})
        return out

    @router.put("/uk-payroll/employees/{staff_id}/hr")
    async def update_hr(staff_id: str, data: Dict,
                        current_user: dict = Depends(require_roles("admin", "manager"))):
        updates = {k: data[k] for k in HR_FIELDS if k in data}
        base = {k: data[k] for k in ("name", "email", "phone", "role", "pay_type", "pay_rate") if k in data}
        updates.update(base)
        if not updates:
            raise HTTPException(400, "No valid HR fields provided")
        ni = (updates.get("ni_number") or "").replace(" ", "").upper()
        if ni and len(ni) != 9:
            raise HTTPException(400, "NI numarası 9 karakter olmalı (örn. AB123456C)")
        if ni:
            updates["ni_number"] = ni
        if updates.get("tax_code"):
            updates["tax_code"] = updates["tax_code"].upper().replace(" ", "")
        updates["hr_updated_at"] = datetime.now(timezone.utc).isoformat()
        res = await db.shift_staff.update_one({"id": staff_id}, {"$set": updates})
        if res.matched_count == 0:
            raise HTTPException(404, "Personel bulunamadı")
        return await db.shift_staff.find_one({"id": staff_id}, {"_id": 0})

    # ==================== OFFBOARDING ====================
    @router.post("/uk-payroll/employees/{staff_id}/offboard")
    async def offboard(staff_id: str, data: Dict,
                       current_user: dict = Depends(require_roles("admin", "manager"))):
        leaver_date = data.get("leaver_date", "")
        if not leaver_date:
            raise HTTPException(400, "leaver_date required")
        s = await db.shift_staff.find_one({"id": staff_id}, {"_id": 0})
        if not s:
            raise HTTPException(404, "Personel bulunamadı")
        today = datetime.now(timezone.utc).date()
        ty_start = _tax_year_start(today)
        shifts = await db.shift_entries.find(
            {"staff_id": staff_id, "status": {"$in": ["completed", "approved"]},
             "date": {"$gte": ty_start.isoformat(), "$lte": leaver_date}},
            {"_id": 0, "hours_worked": 1, "earned_amount": 1}).to_list(2000)
        hours_ty = sum(float(x.get("hours_worked", 0) or 0) for x in shifts)
        earned_ty = sum(float(x.get("earned_amount", 0) or 0) for x in shifts)
        avg_rate = round(earned_ty / hours_ty, 2) if hours_ty else float(s.get("pay_rate", 0) or 0)
        holiday_hours = round(hours_ty * HOLIDAY_ACCRUAL_PCT, 2)
        holiday_pay = round(holiday_hours * avg_rate, 2)
        # unpaid = shifts not yet in a payroll run
        paid_ids = set()
        slips = await db.uk_payslips.find({"staff_id": staff_id}, {"_id": 0, "shift_ids": 1}).to_list(100)
        for sl in slips:
            paid_ids.update(sl.get("shift_ids", []))
        unpaid = await db.shift_entries.find(
            {"staff_id": staff_id, "status": {"$in": ["completed", "approved"]},
             "id": {"$nin": list(paid_ids)}}, {"_id": 0, "earned_amount": 1}).to_list(2000)
        unpaid_total = round(sum(float(x.get("earned_amount", 0) or 0) for x in unpaid), 2)
        await db.shift_staff.update_one({"id": staff_id}, {"$set": {
            "is_active": False, "leaver_date": leaver_date,
            "leaver_reason": data.get("reason", ""),
            "final_pay_estimate": round(unpaid_total + holiday_pay, 2),
            "offboarded_at": datetime.now(timezone.utc).isoformat(),
            "offboarded_by": current_user.get("name", ""),
        }})
        return {"ok": True, "leaver_date": leaver_date,
                "final_pay": {"unpaid_shifts": unpaid_total, "holiday_hours_accrued": holiday_hours,
                              "holiday_pay": holiday_pay, "avg_hourly_rate": avg_rate,
                              "total_estimate": round(unpaid_total + holiday_pay, 2)},
                "note": "Son FPS'te leaver olarak işaretleyin ve P45 düzenleyin. Kalan ödemelerde 0T (W1/M1) vergi kodu kullanılır."}

    @router.post("/uk-payroll/employees/{staff_id}/reinstate")
    async def reinstate(staff_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        res = await db.shift_staff.update_one({"id": staff_id}, {
            "$set": {"is_active": True},
            "$unset": {"leaver_date": "", "leaver_reason": "", "final_pay_estimate": "", "offboarded_at": ""}})
        if res.matched_count == 0:
            raise HTTPException(404, "Personel bulunamadı")
        return {"ok": True}

    # ==================== PAYROLL COMPUTE ====================
    async def _compute_month(property_id: str, year: int, month: int):
        start, end = _month_bounds(year, month)
        query = {"date": {"$gte": start.isoformat(), "$lte": end.isoformat()},
                 "status": {"$in": ["completed", "approved"]}}
        if property_id != "all":
            query["property_id"] = property_id
        shifts = await db.shift_entries.find(query, {"_id": 0}).to_list(5000)
        sq = {} if property_id == "all" else {"property_id": property_id}
        staff_docs = await db.shift_staff.find(sq, {"_id": 0}).to_list(300)
        smap = {s["id"]: s for s in staff_docs}
        adj_docs = await db.payroll_adjustments.find({"year": year, "month": month}, {"_id": 0}).to_list(500)
        adj_by_staff: dict = {}
        for a in adj_docs:
            adj_by_staff.setdefault(a.get("staff_id"), []).append(a)

        by_staff: dict = {}
        for sh in shifts:
            by_staff.setdefault(sh.get("staff_id", ""), []).append(sh)

        rows, warnings = [], []
        totals = {"hours": 0.0, "gross": 0.0, "paye": 0.0, "ni_employee": 0.0, "ni_employer": 0.0,
                  "student_loan": 0.0, "net": 0.0, "nmw_topup": 0.0, "employer_cost": 0.0}
        for sid, items in by_staff.items():
            s = smap.get(sid, {})
            name = s.get("name") or (items[0].get("staff_name", "?"))
            hours = sum(float(x.get("hours_worked", 0) or 0) for x in items)
            base_earned = sum(float(x.get("earned_amount", 0) or 0) for x in items)
            dob = s.get("dob", "")
            age = _age_on(dob, end) if dob else None
            apprentice = bool(s.get("is_apprentice")) or s.get("contract_type") == "apprentice"
            nmw = _nmw_rate(age, apprentice)
            staff_warn = []
            if not dob:
                staff_warn.append("Doğum tarihi eksik — NMW için 21+ varsayıldı")
            if not s.get("ni_number"):
                staff_warn.append("NI numarası eksik")
            tax_code = s.get("tax_code") or DEFAULT_TAX_CODE
            if not s.get("tax_code"):
                staff_warn.append(f"Vergi kodu eksik — {DEFAULT_TAX_CODE} varsayıldı")
            # NMW top-up
            nmw_topup = 0.0
            implied = round(base_earned / hours, 2) if hours else 0
            if hours > 0 and implied < nmw:
                nmw_topup = round(nmw * hours - base_earned, 2)
                staff_warn.append(f"Ücret NMW altında (£{implied:.2f} < £{nmw:.2f}) — £{nmw_topup:.2f} tamamlama eklendi")
            adjs = adj_by_staff.get(sid, [])
            adj_add = sum(a.get("amount", 0) for a in adjs if a.get("type") not in ("deduction", "tax"))
            adj_ded = sum(a.get("amount", 0) for a in adjs if a.get("type") in ("deduction", "tax"))
            gross = round(base_earned + nmw_topup + adj_add - adj_ded, 2)
            paye = _paye(gross, tax_code)
            ni_ee = _ni_employee(gross)
            ni_er = _ni_employer(gross)
            sloan = _student_loan(gross, s.get("student_loan_plans", []))
            net = round(gross - paye - ni_ee - sloan, 2)
            row = {"staff_id": sid, "staff_name": name, "role": s.get("role", items[0].get("role", "")),
                   "email": s.get("email", ""), "ni_number": s.get("ni_number", ""), "tax_code": tax_code,
                   "age": age, "nmw_rate": nmw, "shifts": len(items), "hours": round(hours, 2),
                   "implied_hourly": implied, "base_earned": round(base_earned, 2), "nmw_topup": nmw_topup,
                   "adjustments": round(adj_add - adj_ded, 2), "gross": gross, "paye": paye,
                   "ni_employee": ni_ee, "ni_employer": ni_er, "student_loan": sloan, "net": net,
                   "employer_cost": round(gross + ni_er, 2),
                   "shift_ids": [x.get("id") for x in items], "warnings": staff_warn}
            rows.append(row)
            if staff_warn:
                warnings.append({"staff_name": name, "issues": staff_warn})
            for k, rk in (("hours", "hours"), ("gross", "gross"), ("paye", "paye"),
                          ("ni_employee", "ni_employee"), ("ni_employer", "ni_employer"),
                          ("student_loan", "student_loan"), ("net", "net"),
                          ("nmw_topup", "nmw_topup"), ("employer_cost", "employer_cost")):
                totals[k] = round(totals[k] + row[rk], 2)
        rows.sort(key=lambda r: r["staff_name"])
        return {"tax_year": TAX_YEAR, "year": year, "month": month,
                "period": {"start": start.isoformat(), "end": end.isoformat()},
                "rows": rows, "totals": totals, "warnings": warnings, "staff_count": len(rows)}

    @router.get("/uk-payroll/preview/{property_id}")
    async def preview(property_id: str, year: int = 0, month: int = 0,
                      current_user: dict = Depends(require_roles("admin", "manager"))):
        now = datetime.now(timezone.utc)
        year, month = year or now.year, month or now.month
        if not (1 <= month <= 12):
            raise HTTPException(400, "month 1-12 olmalı")
        return await _compute_month(property_id, year, month)

    # ==================== PAYROLL RUN ====================
    @router.post("/uk-payroll/run/{property_id}")
    async def run_payroll(property_id: str, data: Dict,
                          current_user: dict = Depends(require_roles("admin", "manager"))):
        now = datetime.now(timezone.utc)
        year = int(data.get("year") or now.year)
        month = int(data.get("month") or now.month)
        force = bool(data.get("force"))
        existing = await db.uk_payroll_runs.find_one({"property_id": property_id, "year": year, "month": month}, {"_id": 0})
        if existing and not force:
            raise HTTPException(409, f"{year}-{month:02d} bordrosu zaten çalıştırılmış. Yeniden çalıştırmak için force:true gönderin.")
        result = await _compute_month(property_id, year, month)
        if not result["rows"]:
            raise HTTPException(400, "Bu dönemde onaylanmış/tamamlanmış vardiya bulunamadı")
        run_id = str(uuid.uuid4())
        if existing:
            await db.uk_payslips.delete_many({"run_id": existing["id"]})
            await db.uk_payroll_runs.delete_one({"id": existing["id"]})
        run_doc = {"id": run_id, "property_id": property_id, "year": year, "month": month,
                   "tax_year": TAX_YEAR, "period": result["period"], "totals": result["totals"],
                   "staff_count": result["staff_count"], "warning_count": len(result["warnings"]),
                   "status": "completed", "created_by": current_user.get("name", ""),
                   "created_at": now.isoformat()}
        await db.uk_payroll_runs.insert_one({**run_doc})
        slips = []
        for r in result["rows"]:
            slips.append({**r, "id": str(uuid.uuid4()), "run_id": run_id, "property_id": property_id,
                          "year": year, "month": month, "tax_year": TAX_YEAR,
                          "period": result["period"], "email_status": None, "created_at": now.isoformat()})
        await db.uk_payslips.insert_many([{**s} for s in slips])
        return {"ok": True, "run": run_doc, "payslips_created": len(slips)}

    @router.get("/uk-payroll/runs/{property_id}")
    async def list_runs(property_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        q = {} if property_id == "all" else {"property_id": property_id}
        return await db.uk_payroll_runs.find(q, {"_id": 0}).sort("created_at", -1).to_list(60)

    @router.get("/uk-payroll/runs/{property_id}/{run_id}/payslips")
    async def run_payslips(property_id: str, run_id: str,
                           current_user: dict = Depends(require_roles("admin", "manager"))):
        return await db.uk_payslips.find({"run_id": run_id}, {"_id": 0}).sort("staff_name", 1).to_list(300)

    # ==================== PAYSLIP PDF ====================
    def _payslip_pdf(slip: dict, prop_name: str) -> bytes:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.pdfgen import canvas as rl_canvas
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        candidates = {
            "Helvetica": ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                          "/usr/share/fonts/truetype/freefont/FreeSans.ttf"],
            "Helvetica-Bold": ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                               "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf"],
        }
        fonts = {}
        for logical, paths in candidates.items():
            reg = "UKP-" + logical
            if reg not in pdfmetrics.getRegisteredFontNames():
                for p in paths:
                    if os.path.exists(p):
                        pdfmetrics.registerFont(TTFont(reg, p))
                        break
            fonts[logical] = reg if reg in pdfmetrics.getRegisteredFontNames() else logical
        buf = io.BytesIO()
        c = rl_canvas.Canvas(buf, pagesize=A4)
        _orig_setfont = c.setFont
        c.setFont = lambda name, size, leading=None: _orig_setfont(fonts.get(name, name), size, leading)
        w, h = A4
        c.setFillColorRGB(0.11, 0.13, 0.18)
        c.rect(0, h - 30 * mm, w, 30 * mm, fill=1, stroke=0)
        c.setFillColorRGB(1, 1, 1)
        c.setFont("Helvetica-Bold", 16)
        c.drawString(20 * mm, h - 15 * mm, prop_name or "MyHotelBox")
        c.setFont("Helvetica", 10)
        c.drawString(20 * mm, h - 22 * mm, f"PAYSLIP — {slip['period']['start']} / {slip['period']['end']}  ·  Tax Year {slip.get('tax_year', TAX_YEAR)}")
        c.setFillColorRGB(0, 0, 0)
        y = h - 42 * mm
        c.setFont("Helvetica-Bold", 12)
        c.drawString(20 * mm, y, slip.get("staff_name", ""))
        c.setFont("Helvetica", 9)
        y -= 6 * mm
        c.drawString(20 * mm, y, f"Rol: {slip.get('role','')}   NI No: {slip.get('ni_number') or '—'}   Vergi Kodu: {slip.get('tax_code','')}")
        y -= 12 * mm
        c.setFont("Helvetica-Bold", 10)
        c.drawString(20 * mm, y, "KAZANÇLAR")
        c.drawString(120 * mm, y, "KESİNTİLER")
        c.setFont("Helvetica", 9)
        earn = [("Vardiya kazancı", slip.get("base_earned", 0)),
                ("NMW tamamlama", slip.get("nmw_topup", 0)),
                ("Düzeltmeler", slip.get("adjustments", 0))]
        ded = [("PAYE Gelir Vergisi", slip.get("paye", 0)),
               ("National Insurance", slip.get("ni_employee", 0)),
               ("Öğrenci Kredisi", slip.get("student_loan", 0))]
        ey = y - 6 * mm
        for label, val in earn:
            if val:
                c.drawString(20 * mm, ey, label)
                c.drawRightString(100 * mm, ey, f"£{val:,.2f}")
                ey -= 5.5 * mm
        dy = y - 6 * mm
        for label, val in ded:
            c.drawString(120 * mm, dy, label)
            c.drawRightString(190 * mm, dy, f"£{val:,.2f}")
            dy -= 5.5 * mm
        yy = min(ey, dy) - 6 * mm
        c.line(20 * mm, yy, 190 * mm, yy)
        yy -= 8 * mm
        c.setFont("Helvetica", 9)
        c.drawString(20 * mm, yy, f"Çalışılan saat: {slip.get('hours', 0)}  ·  Vardiya: {slip.get('shifts', 0)}  ·  Saatlik (efektif): £{slip.get('implied_hourly', 0):,.2f}")
        yy -= 7 * mm
        c.drawString(20 * mm, yy, f"Brüt Ücret: £{slip.get('gross', 0):,.2f}")
        c.drawString(90 * mm, yy, f"İşveren NI: £{slip.get('ni_employer', 0):,.2f}")
        yy -= 12 * mm
        c.setFillColorRGB(0.06, 0.45, 0.30)
        c.rect(20 * mm, yy - 4 * mm, 170 * mm, 11 * mm, fill=1, stroke=0)
        c.setFillColorRGB(1, 1, 1)
        c.setFont("Helvetica-Bold", 13)
        c.drawString(24 * mm, yy - 0.5 * mm, "NET ÖDEME")
        c.drawRightString(186 * mm, yy - 0.5 * mm, f"£{slip.get('net', 0):,.2f}")
        c.setFillColorRGB(0.4, 0.4, 0.4)
        c.setFont("Helvetica", 7)
        c.drawString(20 * mm, 15 * mm, f"Bu bordro {TAX_YEAR} UK vergi yılı oran ve eşiklerine göre otomatik hesaplanmıştır (ay bazlı). MyHotelBox İK & Bordro")
        c.showPage()
        c.save()
        return buf.getvalue()

    @router.get("/uk-payroll/payslip/{payslip_id}/pdf")
    async def payslip_pdf(payslip_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        slip = await db.uk_payslips.find_one({"id": payslip_id}, {"_id": 0})
        if not slip:
            raise HTTPException(404, "Payslip bulunamadı")
        prop = await db.properties.find_one({"id": slip.get("property_id", "")}, {"_id": 0, "name": 1})
        pdf = _payslip_pdf(slip, (prop or {}).get("name", "MyHotelBox"))
        import unicodedata
        safe_name = unicodedata.normalize("NFKD", slip["staff_name"]).encode("ascii", "ignore").decode() or "payslip"
        fname = f"payslip_{safe_name.replace(' ', '_')}_{slip['year']}-{slip['month']:02d}.pdf"
        return Response(content=pdf, media_type="application/pdf",
                        headers={"Content-Disposition": f'attachment; filename="{fname}"'})

    @router.post("/uk-payroll/payslip/{payslip_id}/email")
    async def email_payslip(payslip_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        slip = await db.uk_payslips.find_one({"id": payslip_id}, {"_id": 0})
        if not slip:
            raise HTTPException(404, "Payslip bulunamadı")
        if not slip.get("email"):
            raise HTTPException(400, "Personelin e-posta adresi kayıtlı değil")
        prop = await db.properties.find_one({"id": slip.get("property_id", "")}, {"_id": 0, "name": 1})
        prop_name = (prop or {}).get("name", "MyHotelBox")
        pdf = _payslip_pdf(slip, prop_name)
        html = (f"<div style='font-family:sans-serif'><h2>{prop_name} — Maaş Bordronuz</h2>"
                f"<p>Merhaba {slip['staff_name']},</p>"
                f"<p>{slip['year']}-{slip['month']:02d} dönemi bordronuz ekte yer almaktadır.</p>"
                f"<table style='border-collapse:collapse'>"
                f"<tr><td style='padding:4px 12px'>Brüt</td><td><b>£{slip['gross']:,.2f}</b></td></tr>"
                f"<tr><td style='padding:4px 12px'>PAYE</td><td>£{slip['paye']:,.2f}</td></tr>"
                f"<tr><td style='padding:4px 12px'>NI</td><td>£{slip['ni_employee']:,.2f}</td></tr>"
                f"<tr><td style='padding:4px 12px'>Net Ödeme</td><td><b style='color:#0a7a4f'>£{slip['net']:,.2f}</b></td></tr>"
                f"</table></div>")
        fname = f"payslip_{slip['year']}-{slip['month']:02d}.pdf"
        status = await _send_email(slip["email"], f"{prop_name} Bordro — {slip['year']}-{slip['month']:02d}", html, (fname, pdf))
        await db.uk_payslips.update_one({"id": payslip_id}, {"$set": {
            "email_status": status, "emailed_at": datetime.now(timezone.utc).isoformat()}})
        return {"ok": True, "status": status}

    @router.post("/uk-payroll/runs/{run_id}/email-all")
    async def email_all(run_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        slips = await db.uk_payslips.find({"run_id": run_id}, {"_id": 0}).to_list(300)
        if not slips:
            raise HTTPException(404, "Run bulunamadı veya payslip yok")
        sent = mocked = skipped = 0
        for slip in slips:
            if not slip.get("email"):
                skipped += 1
                continue
            prop = await db.properties.find_one({"id": slip.get("property_id", "")}, {"_id": 0, "name": 1})
            prop_name = (prop or {}).get("name", "MyHotelBox")
            pdf = _payslip_pdf(slip, prop_name)
            html = f"<p>Merhaba {slip['staff_name']}, {slip['year']}-{slip['month']:02d} bordronuz ektedir. Net: £{slip['net']:,.2f}</p>"
            status = await _send_email(slip["email"], f"{prop_name} Bordro — {slip['year']}-{slip['month']:02d}", html,
                                       (f"payslip_{slip['year']}-{slip['month']:02d}.pdf", pdf))
            await db.uk_payslips.update_one({"id": slip["id"]}, {"$set": {
                "email_status": status, "emailed_at": datetime.now(timezone.utc).isoformat()}})
            if status == "sent":
                sent += 1
            else:
                mocked += 1
        return {"ok": True, "sent": sent, "mocked": mocked, "skipped_no_email": skipped}

    return router
