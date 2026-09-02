"""UK-compliant HR & Payroll — employee lifecycle, NMW age bands, PAYE, NI Class 1, payslips (2026/27)."""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import Response
from datetime import datetime, timezone, date, timedelta
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
# Auto-enrolment (workplace pension) monthly figures 2026/27 — Sage/BrightPay parity
PEN_LEL_M, PEN_TRIGGER_M, PEN_UEL_M = 520.0, 833.0, 4189.0
PEN_EE_RATE, PEN_ER_RATE = 0.05, 0.03
PEN_MIN_AGE, PEN_MAX_AGE = 22, 66
# Statutory Sick Pay 2026/27 (from 6 Apr 2026: no waiting days, no LEL; lower of flat rate or 80% AWE)
SSP_WEEKLY = 123.25
SSP_AWE_PCT = 0.80
SSP_QUALIFYING_DAYS_PER_WEEK = 5
# Statutory Maternity / Paternity Pay 2026/27 (from 6 Apr 2026)
SMP_WEEKLY = 194.32
SMP_AWE_PCT = 0.90
SMP_LEL_WEEKLY = 129.0
SMP_WEEKS, SMP_ENHANCED_WEEKS, SPP_MAX_WEEKS = 39, 6, 2
SMP_RECOVERY_PCT = 0.92
DOC_EXPIRY_HORIZON_DAYS = 60
LEAVE_ACTIVE_STATUSES = ["approved", "cancel_requested"]

HR_FIELDS = ["dob", "ni_number", "tax_code", "starter_declaration", "contract_type",
             "start_date", "bank_sort_code", "bank_account_no", "student_loan_plans",
             "is_apprentice", "pension_optin", "pension_status", "annual_leave_days",
             "address", "postcode", "emergency_contact"]


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


def _parental_weeks(pl: dict) -> int:
    if pl.get("type") == "maternity":
        return SMP_WEEKS
    return max(1, min(SPP_MAX_WEEKS, int(pl.get("weeks") or SPP_MAX_WEEKS)))


def _parental_weekly(pl: dict, week_idx: int) -> float:
    awe = float(pl.get("awe") or 0)
    if pl.get("type") == "maternity" and week_idx < SMP_ENHANCED_WEEKS:
        return round(awe * SMP_AWE_PCT, 2)
    return round(min(SMP_WEEKLY, awe * SMP_AWE_PCT), 2)


def compute_parental_pay(leaves: list, start: date, end: date) -> dict:
    """Sum of statutory weekly payments whose week-start falls inside [start, end]."""
    total, weeks, ptype = 0.0, 0, ""
    for pl in leaves:
        try:
            s = datetime.strptime(pl["start_date"], "%Y-%m-%d").date()
        except Exception:
            continue
        for i in range(_parental_weeks(pl)):
            wk = s + timedelta(days=7 * i)
            if start <= wk <= end:
                total += _parental_weekly(pl, i)
                weeks += 1
                ptype = pl.get("type", "")
    return {"amount": round(total, 2), "weeks": weeks, "type": ptype}


def _working_days(d1: date, d2: date) -> int:
    if d2 < d1:
        return 0
    return sum(1 for i in range((d2 - d1).days + 1) if (d1 + timedelta(days=i)).weekday() < 5)


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

        # Approved sick leaves overlapping this month (SSP)
        sick_q = {"leave_type": "sick", "status": {"$in": LEAVE_ACTIVE_STATUSES},
                  "start_date": {"$lte": end.isoformat()}, "end_date": {"$gte": start.isoformat()}}
        if property_id != "all":
            sick_q["property_id"] = property_id
        sick_docs = await db.shift_leave_requests.find(sick_q, {"_id": 0}).to_list(500)
        sick_by_staff: dict = {}
        for lv in sick_docs:
            sick_by_staff.setdefault(lv.get("staff_id"), []).append(lv)
        # Active maternity/paternity leaves that started on/before month end (SMP/SPP)
        par_q = {"status": "active", "start_date": {"$lte": end.isoformat()}}
        if property_id != "all":
            par_q["property_id"] = property_id
        par_docs = await db.staff_parental_leaves.find(par_q, {"_id": 0}).to_list(300)
        par_by_staff: dict = {}
        for pl in par_docs:
            par_by_staff.setdefault(pl.get("staff_id"), []).append(pl)
        # AWE estimate: last 2 months' payslip gross / 8.667 weeks
        prev1_y, prev1_m = (year, month - 1) if month > 1 else (year - 1, 12)
        prev2_y, prev2_m = (prev1_y, prev1_m - 1) if prev1_m > 1 else (prev1_y - 1, 12)
        prev_slips = await db.uk_payslips.find(
            {"staff_id": {"$in": list(sick_by_staff.keys())},
             "$or": [{"year": prev1_y, "month": prev1_m}, {"year": prev2_y, "month": prev2_m}]},
            {"_id": 0, "staff_id": 1, "gross": 1}).to_list(600) if sick_by_staff else []
        awe_gross: dict = {}
        for sl in prev_slips:
            awe_gross[sl["staff_id"]] = awe_gross.get(sl["staff_id"], 0.0) + float(sl.get("gross", 0) or 0)

        def _ssp_for(sid: str, current_base: float) -> tuple:
            leaves = sick_by_staff.get(sid, [])
            if not leaves:
                return 0.0, 0
            days = 0
            for lv in leaves:
                try:
                    d1 = max(datetime.strptime(lv["start_date"], "%Y-%m-%d").date(), start)
                    d2 = min(datetime.strptime(lv["end_date"], "%Y-%m-%d").date(), end)
                except Exception:
                    continue
                days += _working_days(d1, d2)
            if days == 0:
                return 0.0, 0
            awe = awe_gross.get(sid, 0.0) / 8.667 if awe_gross.get(sid) else (current_base / 4.345 if current_base else 0.0)
            weekly = min(SSP_WEEKLY, round(awe * SSP_AWE_PCT, 2)) if awe > 0 else SSP_WEEKLY
            return round(weekly / SSP_QUALIFYING_DAYS_PER_WEEK * days, 2), days

        rows, warnings = [], []
        totals = {"hours": 0.0, "gross": 0.0, "paye": 0.0, "ni_employee": 0.0, "ni_employer": 0.0,
                  "student_loan": 0.0, "pension_ee": 0.0, "pension_er": 0.0, "ssp": 0.0, "smp": 0.0, "net": 0.0,
                  "nmw_topup": 0.0, "employer_cost": 0.0}
        # staff with approved sick leave / active parental leave but no shifts this month still get a payslip
        for sid in list(sick_by_staff) + list(par_by_staff):
            if sid and sid not in by_staff and sid in smap:
                by_staff[sid] = []
        for sid, items in by_staff.items():
            s = smap.get(sid, {})
            name = s.get("name") or (items[0].get("staff_name", "?") if items else "?")
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
            ssp, ssp_days = _ssp_for(sid, base_earned)
            if ssp > 0:
                staff_warn.append(f"SSP: {ssp_days} iş günü yasal hastalık ödemesi (£{ssp:.2f}) eklendi")
            par = compute_parental_pay(par_by_staff.get(sid, []), start, end)
            smp = par["amount"]
            if smp > 0:
                lbl = "SMP (annelik)" if par["type"] == "maternity" else "SPP (babalık)"
                staff_warn.append(f"{lbl}: {par['weeks']} hafta yasal doğum ödemesi (£{smp:.2f}) eklendi")
            gross = round(base_earned + nmw_topup + ssp + smp + adj_add - adj_ded, 2)
            paye = _paye(gross, tax_code)
            ni_ee = _ni_employee(gross)
            ni_er = _ni_employer(gross)
            sloan = _student_loan(gross, s.get("student_loan_plans", []))
            # Workplace pension (auto-enrolment)
            pen_status = s.get("pension_status", "auto")
            ae_eligible = age is not None and PEN_MIN_AGE <= age <= PEN_MAX_AGE and gross > PEN_TRIGGER_M
            enrolled = pen_status == "opted_in" or (pen_status == "auto" and ae_eligible)
            if pen_status == "opted_out":
                enrolled = False
            qual = max(0.0, min(gross, PEN_UEL_M) - PEN_LEL_M) if enrolled else 0.0
            pension_ee = round(qual * PEN_EE_RATE, 2)
            pension_er = round(qual * PEN_ER_RATE, 2)
            net = round(gross - paye - ni_ee - sloan - pension_ee, 2)
            row = {"staff_id": sid, "staff_name": name,
                   "role": s.get("role") or (items[0].get("role", "") if items else ""),
                   "email": s.get("email", ""), "ni_number": s.get("ni_number", ""), "tax_code": tax_code,
                   "age": age, "nmw_rate": nmw, "shifts": len(items), "hours": round(hours, 2),
                   "implied_hourly": implied, "base_earned": round(base_earned, 2), "nmw_topup": nmw_topup,
                   "adjustments": round(adj_add - adj_ded, 2), "ssp": ssp, "ssp_days": ssp_days,
                   "smp": smp, "smp_weeks": par["weeks"], "smp_type": par["type"],
                   "gross": gross, "paye": paye,
                   "ni_employee": ni_ee, "ni_employer": ni_er, "student_loan": sloan,
                   "pension_ee": pension_ee, "pension_er": pension_er, "pension_enrolled": enrolled,
                   "net": net,
                   "employer_cost": round(gross + ni_er + pension_er, 2),
                   "shift_ids": [x.get("id") for x in items], "warnings": staff_warn}
            rows.append(row)
            if staff_warn:
                warnings.append({"staff_name": name, "issues": staff_warn})
            for k, rk in (("hours", "hours"), ("gross", "gross"), ("paye", "paye"),
                          ("ni_employee", "ni_employee"), ("ni_employer", "ni_employer"),
                          ("student_loan", "student_loan"), ("pension_ee", "pension_ee"),
                          ("pension_er", "pension_er"), ("ssp", "ssp"), ("smp", "smp"), ("net", "net"),
                          ("nmw_topup", "nmw_topup"), ("employer_cost", "employer_cost")):
                totals[k] = round(totals[k] + row[rk], 2)
        totals["smp_recovery"] = round(totals["smp"] * SMP_RECOVERY_PCT, 2)
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
    async def _persist_run(property_id: str, year: int, month: int, actor: str, force: bool):
        now = datetime.now(timezone.utc)
        existing = await db.uk_payroll_runs.find_one({"property_id": property_id, "year": year, "month": month}, {"_id": 0})
        if existing and existing.get("locked"):
            return {"ok": False, "skipped": "locked", "run_id": existing["id"]}
        if existing and not force:
            return {"ok": False, "skipped": "already_run", "run_id": existing["id"]}
        result = await _compute_month(property_id, year, month)
        if not result["rows"]:
            return {"ok": False, "skipped": "no_shifts"}
        run_id = str(uuid.uuid4())
        if existing:
            await db.uk_payslips.delete_many({"run_id": existing["id"]})
            await db.uk_payroll_runs.delete_one({"id": existing["id"]})
        run_doc = {"id": run_id, "property_id": property_id, "year": year, "month": month,
                   "tax_year": TAX_YEAR, "period": result["period"], "totals": result["totals"],
                   "staff_count": result["staff_count"], "warning_count": len(result["warnings"]),
                   "status": "completed", "created_by": actor, "created_at": now.isoformat(),
                   "locked": True, "locked_at": now.isoformat(),
                   "revision": int(existing.get("revision", 1)) + 1 if existing else 1}
        await db.uk_payroll_runs.insert_one({**run_doc})
        if existing:
            await db.uk_payroll_corrections.update_many(
                {"property_id": property_id, "year": year, "month": month, "status": "approved"},
                {"$set": {"status": "applied", "applied_at": now.isoformat(), "new_run_id": run_id}})
        slips = []
        for r in result["rows"]:
            slips.append({**r, "id": str(uuid.uuid4()), "run_id": run_id, "property_id": property_id,
                          "year": year, "month": month, "tax_year": TAX_YEAR,
                          "period": result["period"], "email_status": None, "created_at": now.isoformat()})
        await db.uk_payslips.insert_many([{**s} for s in slips])
        return {"ok": True, "run": run_doc, "payslips_created": len(slips), "warnings": result["warnings"]}

    @router.post("/uk-payroll/run/{property_id}")
    async def run_payroll(property_id: str, data: Dict,
                          current_user: dict = Depends(require_roles("admin", "manager"))):
        now = datetime.now(timezone.utc)
        year = int(data.get("year") or now.year)
        month = int(data.get("month") or now.month)
        res = await _persist_run(property_id, year, month, current_user.get("name", ""), bool(data.get("force")))
        if res.get("skipped") == "locked":
            raise HTTPException(423, f"{year}-{month:02d} bordrosu kilitli (ödendi). Değişiklik için Düzeltme Talebi oluşturun; admin onayıyla kilit açılır.")
        if res.get("skipped") == "already_run":
            raise HTTPException(409, f"{year}-{month:02d} bordrosu zaten çalıştırılmış. Yeniden çalıştırmak için force:true gönderin.")
        if res.get("skipped") == "no_shifts":
            raise HTTPException(400, "Bu dönemde onaylanmış/tamamlanmış vardiya bulunamadı")
        return {"ok": True, "run": res["run"], "payslips_created": res["payslips_created"]}

    # ==================== PAYROLL LOCK & CORRECTIONS ====================
    async def _run_or_404(run_id: str) -> dict:
        run = await db.uk_payroll_runs.find_one({"id": run_id}, {"_id": 0})
        if not run:
            raise HTTPException(404, "Run bulunamadı")
        return run

    async def _notify(title: str, message: str, property_id: str, category: str = "hr_payroll", priority: str = "high",
                      push: bool = False):
        await db.notifications.insert_one({
            "id": str(uuid.uuid4()), "category": category, "priority": priority, "title": title,
            "message": message, "property_id": property_id or "", "read": False,
            "created_at": datetime.now(timezone.utc).isoformat()})
        if not push:
            return {"emails": 0, "whatsapp": 0}
        recipients = await db.users.find(
            {"role": {"$in": ["admin", "manager"]}}, {"_id": 0, "email": 1, "phone": 1, "name": 1}).to_list(30)
        try:
            from routes.marketing.whatsapp_voice import _send_whatsapp_reply
        except Exception:
            _send_whatsapp_reply = None
        html = (f"<div style='font-family:sans-serif'><h3>🔒 {title}</h3><p>{message}</p>"
                "<p style='color:#777;font-size:12px'>İK &amp; Bordro (UK) › Bordro Geçmişi ekranından işlem yapabilirsiniz.</p></div>")
        email_st, wa_st = [], []
        for r in recipients:
            if r.get("email"):
                email_st.append(await _send_email(r["email"], f"Bordro — {title}", html))
            phone = (r.get("phone") or "").strip()
            if phone and _send_whatsapp_reply:
                to = phone if phone.startswith("whatsapp:") else f"whatsapp:{phone if phone.startswith('+') else '+' + phone}"
                wa_st.append((await _send_whatsapp_reply(to, f"🔒 {title}\n{message}")).get("status"))
        await db.hr_notification_log.insert_one({
            "id": str(uuid.uuid4()), "title": title, "message": message, "property_id": property_id or "",
            "recipients": len(recipients), "email_sent": email_st.count("sent"), "email_mocked": email_st.count("mocked"),
            "whatsapp_sent": wa_st.count("sent"), "whatsapp_mocked": len(wa_st) - wa_st.count("sent"),
            "created_at": datetime.now(timezone.utc).isoformat()})
        return {"emails": len(email_st), "whatsapp": len(wa_st),
                "mode": "live" if "sent" in email_st or "sent" in wa_st else "mock"}

    @router.get("/uk-payroll/notification-log")
    async def hr_notification_log(current_user: dict = Depends(require_roles("admin", "manager"))):
        return await db.hr_notification_log.find({}, {"_id": 0}).sort("created_at", -1).to_list(30)

    @router.post("/uk-payroll/runs/{run_id}/correction-request")
    async def correction_request(run_id: str, data: Dict,
                                 current_user: dict = Depends(require_roles("admin", "manager"))):
        run = await _run_or_404(run_id)
        reason = (data.get("reason") or "").strip()
        if len(reason) < 5:
            raise HTTPException(400, "Gerekçe en az 5 karakter olmalı")
        if not run.get("locked"):
            raise HTTPException(400, "Bu bordro zaten açık — doğrudan yeniden çalıştırabilirsiniz")
        dup = await db.uk_payroll_corrections.find_one({"run_id": run_id, "status": "pending"}, {"_id": 0})
        if dup:
            raise HTTPException(409, "Bu bordro için bekleyen bir düzeltme talebi zaten var")
        now = datetime.now(timezone.utc).isoformat()
        corr = {"id": str(uuid.uuid4()), "run_id": run_id, "property_id": run["property_id"],
                "year": run["year"], "month": run["month"], "reason": reason[:500],
                "requested_by": current_user.get("name", ""), "requested_at": now,
                "status": "pending", "direct": False}
        await db.uk_payroll_corrections.insert_one({**corr})
        delivery = await _notify("Bordro düzeltme talebi",
                                 f"{corr['requested_by']} — {run['year']}-{run['month']:02d} bordrosu için kilit açma talebi: {reason[:120]}",
                                 run["property_id"], push=True)
        return {**corr, "delivery": delivery}

    @router.get("/uk-payroll/corrections/{property_id}")
    async def list_corrections(property_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        q = {} if property_id == "all" else {"property_id": property_id}
        return await db.uk_payroll_corrections.find(q, {"_id": 0}).sort("requested_at", -1).to_list(100)

    @router.post("/uk-payroll/corrections/{corr_id}/decide")
    async def decide_correction(corr_id: str, data: Dict, current_user: dict = Depends(require_roles("admin"))):
        corr = await db.uk_payroll_corrections.find_one({"id": corr_id}, {"_id": 0})
        if not corr:
            raise HTTPException(404, "Düzeltme talebi bulunamadı")
        if corr.get("status") != "pending":
            raise HTTPException(400, "Bu talep zaten karara bağlanmış")
        decision = data.get("decision")
        if decision not in ("approve", "reject"):
            raise HTTPException(400, "decision approve/reject olmalı")
        now = datetime.now(timezone.utc).isoformat()
        upd = {"status": "approved" if decision == "approve" else "rejected",
               "decided_by": current_user.get("name", ""), "decided_at": now, "decision_note": (data.get("note") or "")[:300]}
        await db.uk_payroll_corrections.update_one({"id": corr_id}, {"$set": upd})
        if decision == "approve":
            await db.uk_payroll_runs.update_one({"id": corr["run_id"]}, {"$set": {
                "locked": False, "unlocked_at": now, "unlocked_by": upd["decided_by"],
                "unlock_reason": corr["reason"], "correction_id": corr_id}})
        delivery = await _notify("Bordro düzeltme talebi " + ("onaylandı" if decision == "approve" else "reddedildi"),
                                 f"{corr['year']}-{corr['month']:02d} — {corr['requested_by']} talebi {upd['decided_by']} tarafından "
                                 f"{'onaylandı, kilit açıldı' if decision == 'approve' else 'reddedildi'}",
                                 corr["property_id"], priority="normal", push=True)
        return {**corr, **upd, "delivery": delivery}

    @router.post("/uk-payroll/runs/{run_id}/unlock")
    async def unlock_run(run_id: str, data: Dict, current_user: dict = Depends(require_roles("admin"))):
        run = await _run_or_404(run_id)
        reason = (data.get("reason") or "").strip()
        if len(reason) < 5:
            raise HTTPException(400, "Gerekçe en az 5 karakter olmalı")
        if not run.get("locked"):
            raise HTTPException(400, "Bordro zaten açık")
        now = datetime.now(timezone.utc).isoformat()
        actor = current_user.get("name", "")
        corr = {"id": str(uuid.uuid4()), "run_id": run_id, "property_id": run["property_id"],
                "year": run["year"], "month": run["month"], "reason": reason[:500],
                "requested_by": actor, "requested_at": now, "status": "approved", "direct": True,
                "decided_by": actor, "decided_at": now, "decision_note": "Admin doğrudan kilit açtı"}
        await db.uk_payroll_corrections.insert_one({**corr})
        await db.uk_payroll_runs.update_one({"id": run_id}, {"$set": {
            "locked": False, "unlocked_at": now, "unlocked_by": actor, "unlock_reason": reason, "correction_id": corr["id"]}})
        await db.uk_payroll_corrections.update_many(
            {"run_id": run_id, "status": "pending"},
            {"$set": {"status": "approved", "decided_by": actor, "decided_at": now, "decision_note": "Admin doğrudan kilit açtı"}})
        delivery = await _notify("Bordro kilidi açıldı", f"{run['year']}-{run['month']:02d} — {actor}: {reason[:120]}",
                                 run["property_id"], priority="normal", push=True)
        return {"ok": True, "correction": corr, "delivery": delivery}

    @router.post("/uk-payroll/runs/{run_id}/lock")
    async def lock_run(run_id: str, current_user: dict = Depends(require_roles("admin"))):
        await _run_or_404(run_id)
        now = datetime.now(timezone.utc).isoformat()
        await db.uk_payroll_runs.update_one({"id": run_id}, {"$set": {"locked": True, "locked_at": now, "locked_by": current_user.get("name", "")}})
        return {"ok": True}

    # ==================== PAYROLL ROBOT (last day of month) ====================
    async def run_monthly_payroll_internal(property_id: str = "all", force: bool = False) -> dict:
        now = datetime.now(timezone.utc)
        last_day = calendar.monthrange(now.year, now.month)[1]
        if now.day != last_day and not force:
            return {"ok": True, "skipped": "not_last_day_of_month", "today": now.day, "last_day": last_day}
        pid = property_id or "all"
        res = await _persist_run(pid, now.year, now.month, "payroll-robot", False)
        if res.get("skipped") in ("already_run", "locked"):
            return {"ok": True, "skipped": "already_run"}
        if res.get("skipped") == "no_shifts":
            return {"ok": True, "skipped": "no_shifts"}
        # summary email to managers
        t = res["run"]["totals"]
        warn_html = ""
        if res.get("warnings"):
            items = "".join(f"<li><b>{w['staff_name']}:</b> {' · '.join(w['issues'])}</li>" for w in res["warnings"][:10])
            warn_html = f"<h3 style='color:#b45309'>Uyum uyarıları ({len(res['warnings'])})</h3><ul>{items}</ul>"
        html = (f"<div style='font-family:sans-serif'><h2>🤖 Bordro Robotu — {now.year}-{now.month:02d} bordrosu çalıştırıldı</h2>"
                f"<table style='border-collapse:collapse'>"
                f"<tr><td style='padding:4px 12px'>Personel</td><td><b>{res['run']['staff_count']}</b></td></tr>"
                f"<tr><td style='padding:4px 12px'>Toplam saat</td><td>{t['hours']}</td></tr>"
                f"<tr><td style='padding:4px 12px'>Brüt</td><td>£{t['gross']:,.2f}</td></tr>"
                f"<tr><td style='padding:4px 12px'>PAYE</td><td>£{t['paye']:,.2f}</td></tr>"
                f"<tr><td style='padding:4px 12px'>NI (çalışan/işveren)</td><td>£{t['ni_employee']:,.2f} / £{t['ni_employer']:,.2f}</td></tr>"
                f"<tr><td style='padding:4px 12px'>Emeklilik (çalışan/işveren)</td><td>£{t.get('pension_ee',0):,.2f} / £{t.get('pension_er',0):,.2f}</td></tr>"
                f"<tr><td style='padding:4px 12px'>Net ödeme</td><td><b style='color:#0a7a4f'>£{t['net']:,.2f}</b></td></tr>"
                f"<tr><td style='padding:4px 12px'>Toplam işveren maliyeti</td><td><b>£{t['employer_cost']:,.2f}</b></td></tr>"
                f"</table>{warn_html}<p>Payslip'ler hazır — İK &amp; Bordro (UK) &gt; Bordro Geçmişi ekranından indirebilir veya personele e-postalayabilirsiniz.</p></div>")
        recipients = await db.users.find(
            {"role": {"$in": ["admin", "manager"]}, "email": {"$not": {"$regex": "test|example"}}},
            {"_id": 0, "email": 1}).to_list(20)
        statuses = []
        for r in recipients:
            statuses.append(await _send_email(r["email"], f"Bordro Robotu — {now.year}-{now.month:02d} özeti", html))
        return {"ok": True, "run_id": res["run"]["id"], "payslips_created": res["payslips_created"],
                "emails": {"sent": statuses.count("sent"), "mocked": statuses.count("mocked")}}

    router.run_monthly_payroll_internal = run_monthly_payroll_internal

    @router.post("/uk-payroll/robot/run")
    async def robot_run(data: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        return await run_monthly_payroll_internal(data.get("property_id", "all"), force=bool(data.get("force")))

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
                ("SSP (Yasal Hastalık Ödemesi)", slip.get("ssp", 0)),
                ("SMP (Yasal Annelik Ödemesi)" if slip.get("smp_type") == "maternity" else "SPP (Yasal Babalık Ödemesi)", slip.get("smp", 0)),
                ("Düzeltmeler", slip.get("adjustments", 0))]
        ded = [("PAYE Gelir Vergisi", slip.get("paye", 0)),
               ("National Insurance", slip.get("ni_employee", 0)),
               ("Öğrenci Kredisi", slip.get("student_loan", 0)),
               ("Emeklilik (%5)", slip.get("pension_ee", 0))]
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
        c.drawString(80 * mm, yy, f"İşveren NI: £{slip.get('ni_employer', 0):,.2f}")
        c.drawString(135 * mm, yy, f"İşveren Emeklilik: £{slip.get('pension_er', 0):,.2f}")
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
    async def payslip_pdf(payslip_id: str,
                          current_user: dict = Depends(require_roles("admin", "manager", "receptionist", "housekeeper", "maintenance"))):
        slip = await db.uk_payslips.find_one({"id": payslip_id}, {"_id": 0})
        if not slip:
            raise HTTPException(404, "Payslip bulunamadı")
        if current_user.get("role") not in ("admin", "manager"):
            if not slip.get("email") or slip.get("email", "").lower() != (current_user.get("email") or "").lower():
                raise HTTPException(403, "Sadece kendi bordronuzu görüntüleyebilirsiniz")
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

    # ==================== P45 (LEAVER DOCUMENT) ====================
    @router.get("/uk-payroll/employees/{staff_id}/p45")
    async def p45_pdf(staff_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        s = await db.shift_staff.find_one({"id": staff_id}, {"_id": 0})
        if not s:
            raise HTTPException(404, "Personel bulunamadı")
        if not s.get("leaver_date"):
            raise HTTPException(400, "P45 sadece işten ayrılmış personel için düzenlenebilir")
        leaver = datetime.strptime(s["leaver_date"][:10], "%Y-%m-%d").date()
        ty_start = _tax_year_start(leaver)
        slips = await db.uk_payslips.find({"staff_id": staff_id}, {"_id": 0}).to_list(50)
        total_pay = total_tax = 0.0
        for sl in slips:
            try:
                p_start = datetime.strptime(sl["period"]["start"], "%Y-%m-%d").date()
            except Exception:
                continue
            if ty_start <= p_start <= leaver:
                total_pay += float(sl.get("gross", 0) or 0)
                total_tax += float(sl.get("paye", 0) or 0)
        tax_month = ((leaver.month - 4) % 12) + 1  # HMRC tax month (April=1)
        prop = await db.properties.find_one({"id": s.get("property_id", "")}, {"_id": 0, "name": 1})
        prop_name = (prop or {}).get("name", "MyHotelBox")

        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.pdfgen import canvas as rl_canvas
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        for reg, paths in {"UKP-Helvetica": ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                                             "/usr/share/fonts/truetype/freefont/FreeSans.ttf"],
                           "UKP-Helvetica-Bold": ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                                                  "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf"]}.items():
            if reg not in pdfmetrics.getRegisteredFontNames():
                for p in paths:
                    if os.path.exists(p):
                        pdfmetrics.registerFont(TTFont(reg, p))
                        break
        buf = io.BytesIO()
        c = rl_canvas.Canvas(buf, pagesize=A4)
        w, h = A4
        c.setFillColorRGB(0.75, 0.16, 0.16)
        c.rect(0, h - 28 * mm, w, 28 * mm, fill=1, stroke=0)
        c.setFillColorRGB(1, 1, 1)
        c.setFont("UKP-Helvetica-Bold", 18)
        c.drawString(20 * mm, h - 14 * mm, "P45 — Part 1A")
        c.setFont("UKP-Helvetica", 10)
        c.drawString(20 * mm, h - 21 * mm, "Details of employee leaving work / İşten ayrılan çalışan bilgileri")
        c.setFillColorRGB(0, 0, 0)
        y = h - 40 * mm
        rows_data = [
            ("1. Employer PAYE reference / İşveren", prop_name),
            ("2. Employee's National Insurance number", s.get("ni_number") or "—"),
            ("3. Surname & first name / Ad Soyad", s.get("name", "")),
            ("4. Leaving date / Ayrılış tarihi", s["leaver_date"]),
            ("5. Student Loan deductions", "Yes" if s.get("student_loan_plans") else "No"),
            ("6. Tax code at leaving date / Vergi kodu", s.get("tax_code") or DEFAULT_TAX_CODE),
            ("7. Tax month / Vergi ayı", str(tax_month)),
            ("   Total pay to date / Yıl içi toplam ücret", f"£{total_pay:,.2f}"),
            ("   Total tax to date / Yıl içi toplam vergi", f"£{total_tax:,.2f}"),
            ("8. Works number / Personel no", s.get("id", "")[:8]),
            ("   Department / Departman", s.get("role", "")),
        ]
        for label, value in rows_data:
            c.setFont("UKP-Helvetica", 9)
            c.setFillColorRGB(0.35, 0.35, 0.35)
            c.drawString(20 * mm, y, label)
            c.setFont("UKP-Helvetica-Bold", 10)
            c.setFillColorRGB(0, 0, 0)
            c.drawString(110 * mm, y, str(value))
            c.setStrokeColorRGB(0.85, 0.85, 0.85)
            c.line(20 * mm, y - 2.5 * mm, 190 * mm, y - 2.5 * mm)
            y -= 10 * mm
        y -= 4 * mm
        c.setFont("UKP-Helvetica", 8)
        c.setFillColorRGB(0.4, 0.4, 0.4)
        c.drawString(20 * mm, y, f"Tax year / Vergi yılı: {ty_start.isoformat()} — {leaver.isoformat()} · Certified by {prop_name} payroll")
        c.drawString(20 * mm, y - 5 * mm, "To the employee: keep this document safe — your new employer will need Parts 2 and 3.")
        c.drawString(20 * mm, 15 * mm, "Bu belge MyHotelBox İK & Bordro tarafından HMRC P45 formatı esas alınarak otomatik üretilmiştir.")
        c.showPage()
        c.save()
        import unicodedata
        safe = unicodedata.normalize("NFKD", s.get("name", "staff")).encode("ascii", "ignore").decode() or "staff"
        return Response(content=buf.getvalue(), media_type="application/pdf",
                        headers={"Content-Disposition": f'attachment; filename="P45_{safe.replace(" ", "_")}.pdf"'})

    # ==================== STAFF SELF-SERVICE PORTAL ====================
    ALL_STAFF_ROLES = ("admin", "manager", "receptionist", "housekeeper", "maintenance")

    async def _my_staff_doc(current_user: dict):
        import re as _re
        email = (current_user.get("email") or "").lower()
        if not email:
            return None
        return await db.shift_staff.find_one({"email": {"$regex": f"^{_re.escape(email)}$", "$options": "i"}}, {"_id": 0})

    @router.get("/uk-payroll/me/summary")
    async def my_summary(current_user: dict = Depends(require_roles(*ALL_STAFF_ROLES))):
        s = await _my_staff_doc(current_user)
        if not s:
            return {"linked": False, "message": "E-posta adresinizle eşleşen personel kaydı bulunamadı. Yöneticinizden İK kaydınıza e-posta eklemesini isteyin."}
        today = datetime.now(timezone.utc).date()
        ty_start = _tax_year_start(today)
        slips = await db.uk_payslips.find({"staff_id": s["id"]}, {"_id": 0, "gross": 1, "paye": 1, "ni_employee": 1, "net": 1, "period": 1}).to_list(50)
        ytd = {"gross": 0.0, "paye": 0.0, "ni": 0.0, "net": 0.0}
        for sl in slips:
            try:
                if datetime.strptime(sl["period"]["start"], "%Y-%m-%d").date() >= ty_start:
                    ytd["gross"] += sl.get("gross", 0)
                    ytd["paye"] += sl.get("paye", 0)
                    ytd["ni"] += sl.get("ni_employee", 0)
                    ytd["net"] += sl.get("net", 0)
            except Exception:
                continue
        return {"linked": True,
                "staff": {k: s.get(k) for k in ("id", "name", "role", "pay_type", "pay_rate", "tax_code",
                                                "ni_number", "start_date", "leaver_date", "contract_type")},
                "tax_year": TAX_YEAR,
                "ytd": {k: round(v, 2) for k, v in ytd.items()}}

    @router.get("/uk-payroll/me/payslips")
    async def my_payslips(current_user: dict = Depends(require_roles(*ALL_STAFF_ROLES))):
        s = await _my_staff_doc(current_user)
        if not s:
            return []
        return await db.uk_payslips.find(
            {"staff_id": s["id"]},
            {"_id": 0, "id": 1, "year": 1, "month": 1, "hours": 1, "gross": 1, "paye": 1,
             "ni_employee": 1, "pension_ee": 1, "student_loan": 1, "net": 1, "period": 1}
        ).sort([("year", -1), ("month", -1)]).to_list(36)

    @router.get("/uk-payroll/me/shifts")
    async def my_shifts(weeks: int = 6, current_user: dict = Depends(require_roles(*ALL_STAFF_ROLES))):
        s = await _my_staff_doc(current_user)
        if not s:
            return []
        cutoff = (datetime.now(timezone.utc) - timedelta(weeks=min(weeks, 26))).date().isoformat()
        return await db.shift_entries.find(
            {"staff_id": s["id"], "date": {"$gte": cutoff}},
            {"_id": 0, "date": 1, "start_time": 1, "end_time": 1, "hours_worked": 1,
             "status": 1, "role": 1, "earned_amount": 1}
        ).sort("date", -1).to_list(200)

    # ==================== P60 (END OF YEAR CERTIFICATE) ====================
    async def _build_p60(staff: dict, ty_start_year: int) -> bytes:
        ty_start = date(ty_start_year, 4, 6)
        ty_end = date(ty_start_year + 1, 4, 5)
        slips = await db.uk_payslips.find({"staff_id": staff["id"]}, {"_id": 0}).to_list(50)
        tot = {"gross": 0.0, "paye": 0.0, "ni": 0.0, "pension": 0.0, "sloan": 0.0, "net": 0.0}
        months = 0
        for sl in slips:
            try:
                p_start = datetime.strptime(sl["period"]["start"], "%Y-%m-%d").date()
            except Exception:
                continue
            if ty_start <= p_start <= ty_end:
                months += 1
                tot["gross"] += sl.get("gross", 0)
                tot["paye"] += sl.get("paye", 0)
                tot["ni"] += sl.get("ni_employee", 0)
                tot["pension"] += sl.get("pension_ee", 0)
                tot["sloan"] += sl.get("student_loan", 0)
                tot["net"] += sl.get("net", 0)
        prop = await db.properties.find_one({"id": staff.get("property_id", "")}, {"_id": 0, "name": 1})
        prop_name = (prop or {}).get("name", "MyHotelBox")

        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.pdfgen import canvas as rl_canvas
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        for reg, paths in {"UKP-Helvetica": ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                                             "/usr/share/fonts/truetype/freefont/FreeSans.ttf"],
                           "UKP-Helvetica-Bold": ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                                                  "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf"]}.items():
            if reg not in pdfmetrics.getRegisteredFontNames():
                for p in paths:
                    if os.path.exists(p):
                        pdfmetrics.registerFont(TTFont(reg, p))
                        break
        buf = io.BytesIO()
        c = rl_canvas.Canvas(buf, pagesize=A4)
        w, h = A4
        c.setFillColorRGB(0.09, 0.28, 0.55)
        c.rect(0, h - 28 * mm, w, 28 * mm, fill=1, stroke=0)
        c.setFillColorRGB(1, 1, 1)
        c.setFont("UKP-Helvetica-Bold", 18)
        c.drawString(20 * mm, h - 14 * mm, "P60 — End of Year Certificate")
        c.setFont("UKP-Helvetica", 10)
        c.drawString(20 * mm, h - 21 * mm, f"Tax year to 5 April {ty_start_year + 1} / {ty_start_year}-{str(ty_start_year + 1)[2:]} vergi yılı özeti")
        c.setFillColorRGB(0, 0, 0)
        y = h - 40 * mm
        rows_data = [
            ("Employer / İşveren", prop_name),
            ("Employee / Çalışan", staff.get("name", "")),
            ("National Insurance number", staff.get("ni_number") or "—"),
            ("Final tax code / Vergi kodu", staff.get("tax_code") or DEFAULT_TAX_CODE),
            ("Pay periods included / Dahil edilen bordro", f"{months} ay"),
            ("Total pay for year / Yıllık toplam ücret", f"£{tot['gross']:,.2f}"),
            ("Total tax deducted / Yıllık toplam vergi (PAYE)", f"£{tot['paye']:,.2f}"),
            ("Employee NIC in this employment / Yıllık NI", f"£{tot['ni']:,.2f}"),
            ("Pension contributions / Emeklilik kesintisi", f"£{tot['pension']:,.2f}"),
            ("Student Loan deductions / Öğrenci kredisi", f"£{tot['sloan']:,.2f}"),
            ("Net pay / Yıllık net ödeme", f"£{tot['net']:,.2f}"),
        ]
        for label, value in rows_data:
            c.setFont("UKP-Helvetica", 9)
            c.setFillColorRGB(0.35, 0.35, 0.35)
            c.drawString(20 * mm, y, label)
            c.setFont("UKP-Helvetica-Bold", 10)
            c.setFillColorRGB(0, 0, 0)
            c.drawString(115 * mm, y, str(value))
            c.setStrokeColorRGB(0.85, 0.85, 0.85)
            c.line(20 * mm, y - 2.5 * mm, 190 * mm, y - 2.5 * mm)
            y -= 10 * mm
        c.setFont("UKP-Helvetica", 8)
        c.setFillColorRGB(0.4, 0.4, 0.4)
        c.drawString(20 * mm, y - 4 * mm, "Keep this certificate — you may need it for a tax return, tax credits or a loan application.")
        c.drawString(20 * mm, 15 * mm, f"Bu belge MyHotelBox İK & Bordro tarafından {TAX_YEAR} kayıtlarından otomatik üretilmiştir (HMRC P60 formatı esas alınmıştır).")
        c.showPage()
        c.save()
        return buf.getvalue()

    def _current_ty_start_year() -> int:
        today = datetime.now(timezone.utc).date()
        return _tax_year_start(today).year

    @router.get("/uk-payroll/employees/{staff_id}/p60")
    async def p60_pdf(staff_id: str, year: int = 0,
                      current_user: dict = Depends(require_roles("admin", "manager"))):
        s = await db.shift_staff.find_one({"id": staff_id}, {"_id": 0})
        if not s:
            raise HTTPException(404, "Personel bulunamadı")
        if year and not (2020 <= year <= 2100):
            raise HTTPException(400, "Geçersiz vergi yılı")
        ty_year = year or _current_ty_start_year()
        pdf = await _build_p60(s, ty_year)
        import unicodedata
        safe = unicodedata.normalize("NFKD", s.get("name", "staff")).encode("ascii", "ignore").decode() or "staff"
        return Response(content=pdf, media_type="application/pdf",
                        headers={"Content-Disposition": f'attachment; filename="P60_{safe.replace(" ", "_")}_{ty_year}-{str(ty_year + 1)[2:]}.pdf"'})

    @router.get("/uk-payroll/me/p60")
    async def my_p60(year: int = 0, current_user: dict = Depends(require_roles(*ALL_STAFF_ROLES))):
        s = await _my_staff_doc(current_user)
        if not s:
            raise HTTPException(404, "E-posta adresinizle eşleşen personel kaydı bulunamadı")
        ty_year = year or _current_ty_start_year()
        pdf = await _build_p60(s, ty_year)
        return Response(content=pdf, media_type="application/pdf",
                        headers={"Content-Disposition": f'attachment; filename="P60_{ty_year}-{str(ty_year + 1)[2:]}.pdf"'})

    # ==================== LEAVE REQUESTS (SELF-SERVICE) ====================
    # ==================== LEAVE BALANCE ====================
    async def _leave_balance(staff: dict) -> dict:
        entitled = int(staff.get("annual_leave_days") or 28)  # UK statutory 5.6 weeks
        year = str(datetime.now(timezone.utc).year)
        leaves = await db.shift_leave_requests.find(
            {"staff_id": staff["id"], "leave_type": "annual",
             "start_date": {"$regex": f"^{year}"}}, {"_id": 0, "days": 1, "status": 1}).to_list(100)
        used = sum(int(lv.get("days", 0)) for lv in leaves if lv.get("status") in LEAVE_ACTIVE_STATUSES)
        pending = sum(int(lv.get("days", 0)) for lv in leaves if lv.get("status") == "pending")
        return {"entitled": entitled, "used": used, "pending": pending,
                "remaining": max(0, entitled - used - pending), "year": int(year)}

    @router.get("/uk-payroll/me/leave-balance")
    async def my_leave_balance(current_user: dict = Depends(require_roles(*ALL_STAFF_ROLES))):
        s = await _my_staff_doc(current_user)
        if not s:
            raise HTTPException(404, "E-posta adresinizle eşleşen personel kaydı bulunamadı")
        return await _leave_balance(s)

    @router.post("/uk-payroll/me/leave-request")
    async def my_leave_request(data: Dict, current_user: dict = Depends(require_roles(*ALL_STAFF_ROLES))):
        s = await _my_staff_doc(current_user)
        if not s:
            raise HTTPException(404, "E-posta adresinizle eşleşen personel kaydı bulunamadı")
        start_date = data.get("start_date", "")
        end_date = data.get("end_date", "")
        if not start_date or not end_date:
            raise HTTPException(400, "start_date ve end_date zorunlu")
        try:
            d1 = datetime.strptime(start_date, "%Y-%m-%d").date()
            d2 = datetime.strptime(end_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(400, "Tarih formatı YYYY-MM-DD olmalı")
        if d2 < d1:
            raise HTTPException(400, "Bitiş tarihi başlangıçtan önce olamaz")
        leave_type = data.get("leave_type", "annual")
        if leave_type not in ("annual", "sick", "unpaid", "toil"):
            raise HTTPException(400, "leave_type annual/sick/unpaid/toil olmalı")
        days = (d2 - d1).days + 1
        if leave_type == "annual":
            bal = await _leave_balance(s)
            if days > bal["remaining"]:
                raise HTTPException(400, f"Yetersiz izin bakiyesi: kalan {bal['remaining']} gün, talep {days} gün "
                                          f"(hak {bal['entitled']}, kullanılan {bal['used']}, bekleyen {bal['pending']})")
        leave = {
            "id": str(uuid.uuid4()),
            "property_id": s.get("property_id", ""),
            "staff_id": s["id"],
            "staff_name": s.get("name", ""),
            "leave_type": leave_type,
            "start_date": start_date, "end_date": end_date, "days": days,
            "reason": (data.get("reason") or "")[:300],
            "status": "pending",
            "source": "staff_portal",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": s.get("name", ""),
        }
        await db.shift_leave_requests.insert_one(leave)
        leave.pop("_id", None)
        await db.notifications.insert_one({
            "id": str(uuid.uuid4()), "category": "hr_leave", "priority": "normal",
            "title": "Yeni izin talebi",
            "message": f"{s.get('name')} — {start_date} → {end_date} ({days} gün, {leave['leave_type']})",
            "property_id": s.get("property_id", ""), "read": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        return leave

    @router.get("/uk-payroll/me/leaves")
    async def my_leaves(current_user: dict = Depends(require_roles(*ALL_STAFF_ROLES))):
        s = await _my_staff_doc(current_user)
        if not s:
            return []
        return await db.shift_leave_requests.find(
            {"staff_id": s["id"]}, {"_id": 0}).sort("created_at", -1).to_list(50)

    @router.post("/uk-payroll/me/leaves/{leave_id}/cancel")
    async def my_leave_cancel(leave_id: str, current_user: dict = Depends(require_roles(*ALL_STAFF_ROLES))):
        s = await _my_staff_doc(current_user)
        if not s:
            raise HTTPException(404, "E-posta adresinizle eşleşen personel kaydı bulunamadı")
        lv = await db.shift_leave_requests.find_one({"id": leave_id, "staff_id": s["id"]}, {"_id": 0})
        if not lv:
            raise HTTPException(404, "İzin talebi bulunamadı")
        now = datetime.now(timezone.utc).isoformat()
        if lv.get("status") == "pending":
            new_status = "cancelled"
            await db.shift_leave_requests.update_one({"id": leave_id}, {"$set": {
                "status": "cancelled", "cancelled_at": now, "cancelled_by": s.get("name", "")}})
        elif lv.get("status") == "approved":
            new_status = "cancel_requested"
            await db.shift_leave_requests.update_one({"id": leave_id}, {"$set": {
                "status": "cancel_requested", "cancel_requested_at": now}})
            await _notify("İzin iptal talebi",
                          f"{s.get('name')} onaylı iznini iptal etmek istiyor — {lv['start_date']} → {lv['end_date']} ({lv.get('days')} gün)",
                          s.get("property_id", ""), category="hr_leave", priority="normal")
        else:
            raise HTTPException(400, "Sadece bekleyen veya onaylı izinler iptal edilebilir")
        return {"ok": True, "status": new_status}

    @router.post("/uk-payroll/leaves/{leave_id}/cancel-decision")
    async def leave_cancel_decision(leave_id: str, data: Dict,
                                    current_user: dict = Depends(require_roles("admin", "manager"))):
        lv = await db.shift_leave_requests.find_one({"id": leave_id}, {"_id": 0})
        if not lv:
            raise HTTPException(404, "İzin talebi bulunamadı")
        if lv.get("status") != "cancel_requested":
            raise HTTPException(400, "Bu izin için bekleyen iptal talebi yok")
        approve = bool(data.get("approve"))
        now = datetime.now(timezone.utc).isoformat()
        upd = {"status": "cancelled" if approve else "approved",
               "cancel_decided_by": current_user.get("name", ""), "cancel_decided_at": now}
        if approve:
            upd["cancelled_at"] = now
            upd["cancelled_by"] = current_user.get("name", "")
        await db.shift_leave_requests.update_one({"id": leave_id}, {"$set": upd})
        return {**lv, **upd}

    # ==================== BACS PAYMENT FILE ====================
    @router.get("/uk-payroll/runs/{run_id}/bacs")
    async def bacs_file(run_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        run = await db.uk_payroll_runs.find_one({"id": run_id}, {"_id": 0})
        if not run:
            raise HTTPException(404, "Run bulunamadı")
        slips = await db.uk_payslips.find({"run_id": run_id}, {"_id": 0}).to_list(300)
        staff_ids = [sl["staff_id"] for sl in slips]
        staff_docs = await db.shift_staff.find({"id": {"$in": staff_ids}}, {"_id": 0}).to_list(300)
        smap = {s["id"]: s for s in staff_docs}
        origin_sort = os.environ.get("BACS_ORIGIN_SORT_CODE", "000000")
        origin_acct = os.environ.get("BACS_ORIGIN_ACCOUNT", "00000000")
        lines, skipped = [], []
        import unicodedata
        for sl in slips:
            st = smap.get(sl["staff_id"], {})
            sort_code = (st.get("bank_sort_code") or "").replace("-", "").replace(" ", "")
            acct = (st.get("bank_account_no") or "").replace(" ", "")
            if len(sort_code) != 6 or len(acct) != 8 or sl.get("net", 0) <= 0:
                skipped.append(sl.get("staff_name", "?"))
                continue
            pence = int(round(float(sl["net"]) * 100))
            name = unicodedata.normalize("NFKD", sl.get("staff_name", "")).encode("ascii", "ignore").decode().upper()[:18]
            ref = f"SALARY {sl['year']}{sl['month']:02d}"[:18]
            # BACS Standard 18: dest sort(6) dest acct(8) type(1) txn code(2=99 credit)
            # origin sort(6) origin acct(8) filler(4) amount pence(11) originator(18) ref(18) beneficiary(18)
            line = (f"{sort_code}{acct}0" f"99"
                    f"{origin_sort}{origin_acct}"
                    f"    "
                    f"{pence:011d}"
                    f"{'MYHOTELBOX PAYROLL':<18.18}"
                    f"{ref:<18.18}"
                    f"{name:<18.18}")
            lines.append(line)
        if not lines:
            raise HTTPException(400, "Hiçbir personelde geçerli banka bilgisi yok (sort code 6 hane + hesap no 8 hane gerekli)")
        content = "\r\n".join(lines) + "\r\n"
        fname = f"BACS_{run['year']}-{run['month']:02d}.txt"
        headers = {"Content-Disposition": f'attachment; filename="{fname}"',
                   "X-Bacs-Included": str(len(lines)), "X-Bacs-Skipped": str(len(skipped))}
        return Response(content=content, media_type="text/plain", headers=headers)

    # ==================== PAYROLL COMPARISON ====================
    @router.get("/uk-payroll/compare/{property_id}")
    async def compare_payroll(property_id: str, y1: int, m1: int, y2: int, m2: int,
                              current_user: dict = Depends(require_roles("admin", "manager"))):
        base_q = {} if property_id == "all" else {"property_id": property_id}
        slips_a = await db.uk_payslips.find({**base_q, "year": y1, "month": m1}, {"_id": 0}).to_list(300)
        slips_b = await db.uk_payslips.find({**base_q, "year": y2, "month": m2}, {"_id": 0}).to_list(300)
        if not slips_a or not slips_b:
            raise HTTPException(404, "Karşılaştırma için her iki dönemin bordrosu da çalıştırılmış olmalı")
        metrics = ("hours", "gross", "paye", "ni_employee", "pension_ee", "net", "employer_cost")

        def _tot(slips):
            return {m: round(sum(float(s.get(m, 0) or 0) for s in slips), 2) for m in metrics}
        tot_a, tot_b = _tot(slips_a), _tot(slips_b)
        totals = {m: {"a": tot_a[m], "b": tot_b[m], "delta": round(tot_b[m] - tot_a[m], 2),
                      "pct": round((tot_b[m] - tot_a[m]) / tot_a[m] * 100, 1) if tot_a[m] else None}
                  for m in metrics}
        map_a = {s["staff_id"]: s for s in slips_a}
        map_b = {s["staff_id"]: s for s in slips_b}
        rows = []
        for sid in sorted(set(map_a) | set(map_b), key=lambda x: (map_b.get(x) or map_a.get(x)).get("staff_name", "")):
            a, b = map_a.get(sid), map_b.get(sid)
            rows.append({"staff_id": sid,
                         "staff_name": (b or a).get("staff_name", ""),
                         "net_a": round(float(a["net"]), 2) if a else None,
                         "net_b": round(float(b["net"]), 2) if b else None,
                         "hours_a": a.get("hours") if a else None,
                         "hours_b": b.get("hours") if b else None,
                         "delta": round(float((b or {}).get("net", 0)) - float((a or {}).get("net", 0)), 2),
                         "status": "yeni" if not a else ("ayrıldı" if not b else "her iki dönem")})
        return {"period_a": {"year": y1, "month": m1, "staff": len(slips_a)},
                "period_b": {"year": y2, "month": m2, "staff": len(slips_b)},
                "totals": totals, "rows": rows}

    # ==================== HR DOCUMENTS ====================
    DOC_TYPES = ("contract", "passport", "visa", "address_proof", "certificate", "other")
    DOC_EXTS = {"pdf", "jpg", "jpeg", "png", "webp", "heic", "docx"}

    @router.post("/uk-payroll/employees/{staff_id}/documents")
    async def upload_document(staff_id: str, doc_type: str = Form("other"), expiry_date: str = Form(""),
                              file: UploadFile = File(...),
                              current_user: dict = Depends(require_roles("admin", "manager"))):
        s = await db.shift_staff.find_one({"id": staff_id}, {"_id": 0, "id": 1, "name": 1})
        if not s:
            raise HTTPException(404, "Personel bulunamadı")
        if doc_type not in DOC_TYPES:
            raise HTTPException(400, f"doc_type şunlardan biri olmalı: {', '.join(DOC_TYPES)}")
        ext = (file.filename or "").rsplit(".", 1)[-1].lower() if "." in (file.filename or "") else ""
        if ext not in DOC_EXTS:
            raise HTTPException(400, "Desteklenmeyen dosya türü (pdf/jpg/png/webp/heic/docx)")
        content = await file.read()
        if len(content) > 15 * 1024 * 1024:
            raise HTTPException(400, "Dosya 15MB'ı aşamaz")
        doc_id = str(uuid.uuid4())
        subpath = f"hr_docs/{staff_id}/{doc_id}.{ext}"
        from object_storage import save_upload
        await save_upload(subpath, content)
        doc = {"id": doc_id, "staff_id": staff_id, "staff_name": s.get("name", ""),
               "doc_type": doc_type, "orig_name": file.filename, "ext": ext,
               "size": len(content), "subpath": subpath,
               "expiry_date": expiry_date[:10] if expiry_date else None,
               "uploaded_by": current_user.get("name", ""),
               "uploaded_at": datetime.now(timezone.utc).isoformat()}
        await db.hr_documents.insert_one({**doc})
        return doc

    @router.get("/uk-payroll/employees/{staff_id}/documents")
    async def list_documents(staff_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        return await db.hr_documents.find({"staff_id": staff_id}, {"_id": 0}).sort("uploaded_at", -1).to_list(100)

    @router.get("/uk-payroll/documents/{doc_id}/download")
    async def download_document(doc_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        doc = await db.hr_documents.find_one({"id": doc_id}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "Belge bulunamadı")
        from object_storage import fetch_upload
        result = await fetch_upload(doc["subpath"])
        if not result:
            raise HTTPException(404, "Dosya depoda bulunamadı")
        data, ct = result
        import unicodedata
        safe = unicodedata.normalize("NFKD", doc.get("orig_name") or f"belge.{doc['ext']}").encode("ascii", "ignore").decode() or f"belge.{doc['ext']}"
        return Response(content=data, media_type=ct or "application/octet-stream",
                        headers={"Content-Disposition": f'attachment; filename="{safe}"'})

    @router.delete("/uk-payroll/documents/{doc_id}")
    async def delete_document(doc_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        res = await db.hr_documents.delete_one({"id": doc_id})
        if res.deleted_count == 0:
            raise HTTPException(404, "Belge bulunamadı")
        return {"ok": True}

    # ==================== LEAVE CALENDAR ====================
    # ==================== PARENTAL LEAVE (SMP / SPP) ====================
    async def _estimate_awe(staff_id: str) -> float:
        slips = await db.uk_payslips.find({"staff_id": staff_id}, {"_id": 0, "gross": 1, "year": 1, "month": 1}) \
            .sort([("year", -1), ("month", -1)]).to_list(2)
        if not slips:
            return 0.0
        return round(sum(float(s.get("gross", 0) or 0) for s in slips) / (4.345 * len(slips)), 2)

    def _parental_view(pl: dict) -> dict:
        weeks = _parental_weeks(pl)
        try:
            s = datetime.strptime(pl["start_date"], "%Y-%m-%d").date()
            end_date = (s + timedelta(days=7 * weeks - 1)).isoformat()
        except Exception:
            end_date = ""
        total = round(sum(_parental_weekly(pl, i) for i in range(weeks)), 2)
        return {**pl, "total_weeks": weeks, "end_date": end_date, "total_pay": total,
                "weekly_first": _parental_weekly(pl, 0), "weekly_standard": _parental_weekly(pl, SMP_ENHANCED_WEEKS)}

    @router.get("/uk-payroll/parental-leave/{property_id}")
    async def list_parental(property_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        q = {} if property_id == "all" else {"property_id": property_id}
        docs = await db.staff_parental_leaves.find(q, {"_id": 0}).sort("start_date", -1).to_list(200)
        return [_parental_view(d) for d in docs]

    @router.post("/uk-payroll/employees/{staff_id}/parental-leave")
    async def create_parental(staff_id: str, data: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        s = await db.shift_staff.find_one({"id": staff_id}, {"_id": 0})
        if not s:
            raise HTTPException(404, "Personel bulunamadı")
        ptype = data.get("type")
        if ptype not in ("maternity", "paternity"):
            raise HTTPException(400, "type maternity/paternity olmalı")
        start_date = data.get("start_date", "")
        try:
            datetime.strptime(start_date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(400, "start_date YYYY-MM-DD olmalı")
        awe = float(data.get("awe") or 0) or await _estimate_awe(staff_id)
        if awe <= 0:
            raise HTTPException(400, "Ortalama haftalık kazanç (AWE) girin — geçmiş bordro bulunamadı")
        if awe < SMP_LEL_WEEKLY:
            raise HTTPException(400, f"AWE £{awe:.2f} < £{SMP_LEL_WEEKLY:.0f} (LEL) — yasal doğum ödemesi hakkı yok")
        dup = await db.staff_parental_leaves.find_one({"staff_id": staff_id, "status": "active"}, {"_id": 0})
        if dup:
            raise HTTPException(409, "Bu personelin zaten aktif bir doğum izni var")
        pl = {"id": str(uuid.uuid4()), "staff_id": staff_id, "staff_name": s.get("name", ""),
              "property_id": s.get("property_id", ""), "type": ptype, "start_date": start_date,
              "weeks": SMP_WEEKS if ptype == "maternity" else max(1, min(SPP_MAX_WEEKS, int(data.get("weeks") or SPP_MAX_WEEKS))),
              "awe": round(awe, 2), "status": "active", "note": (data.get("note") or "")[:300],
              "created_by": current_user.get("name", ""), "created_at": datetime.now(timezone.utc).isoformat()}
        await db.staff_parental_leaves.insert_one({**pl})
        return _parental_view(pl)

    @router.delete("/uk-payroll/parental-leave/{leave_id}")
    async def end_parental(leave_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        upd = await db.staff_parental_leaves.update_one(
            {"id": leave_id}, {"$set": {"status": "ended", "ended_at": datetime.now(timezone.utc).isoformat(),
                                        "ended_by": current_user.get("name", "")}})
        if upd.matched_count == 0:
            raise HTTPException(404, "Doğum izni kaydı bulunamadı")
        return {"ok": True}

    @router.get("/uk-payroll/leave-calendar/{property_id}")
    async def leave_calendar(property_id: str, year: int = 0, month: int = 0,
                             current_user: dict = Depends(require_roles("admin", "manager"))):
        now = datetime.now(timezone.utc)
        year, month = year or now.year, month or now.month
        if not (1 <= month <= 12):
            raise HTTPException(400, "month 1-12 olmalı")
        start, end = _month_bounds(year, month)
        q = {"status": {"$in": ["approved", "cancel_requested", "pending"]},
             "start_date": {"$lte": end.isoformat()}, "end_date": {"$gte": start.isoformat()}}
        if property_id != "all":
            q["property_id"] = property_id
        leaves = await db.shift_leave_requests.find(q, {"_id": 0}).to_list(500)
        days = {}
        for lv in leaves:
            try:
                d1 = max(datetime.strptime(lv["start_date"], "%Y-%m-%d").date(), start)
                d2 = min(datetime.strptime(lv["end_date"], "%Y-%m-%d").date(), end)
            except Exception:
                continue
            for i in range((d2 - d1).days + 1):
                key = (d1 + timedelta(days=i)).isoformat()
                days.setdefault(key, []).append({"staff_id": lv.get("staff_id"), "staff_name": lv.get("staff_name"),
                                                 "leave_type": lv.get("leave_type"), "status": lv.get("status")})
        calendar_days = []
        for i in range((end - start).days + 1):
            d = start + timedelta(days=i)
            key = d.isoformat()
            entries = days.get(key, [])
            approved_ids = {e["staff_id"] for e in entries if e["status"] in LEAVE_ACTIVE_STATUSES}
            calendar_days.append({"date": key, "weekday": d.weekday(), "entries": entries,
                                  "overlap": len(approved_ids) >= 2})
        return {"year": year, "month": month, "first_weekday": start.weekday(),
                "days": calendar_days, "leaves": leaves,
                "overlap_days": sum(1 for d in calendar_days if d["overlap"])}

    # ==================== DOCUMENT EXPIRY TRACKING ====================
    @router.get("/uk-payroll/documents/expiring")
    async def expiring_documents(days: int = DOC_EXPIRY_HORIZON_DAYS,
                                 current_user: dict = Depends(require_roles("admin", "manager"))):
        today = datetime.now(timezone.utc).date()
        horizon = (today + timedelta(days=min(days, 365))).isoformat()
        docs = await db.hr_documents.find(
            {"expiry_date": {"$ne": None, "$lte": horizon}}, {"_id": 0}).sort("expiry_date", 1).to_list(100)
        out = []
        for d in docs:
            try:
                exp = datetime.strptime(d["expiry_date"][:10], "%Y-%m-%d").date()
                d["days_left"] = (exp - today).days
            except Exception:
                d["days_left"] = None
            out.append(d)
        return out

    async def run_doc_expiry_check_internal(property_id: str = "all") -> dict:
        today = datetime.now(timezone.utc).date()
        horizon = (today + timedelta(days=DOC_EXPIRY_HORIZON_DAYS)).isoformat()
        docs = await db.hr_documents.find(
            {"expiry_date": {"$ne": None, "$lte": horizon}, "expiry_alerted_at": {"$exists": False}},
            {"_id": 0}).to_list(100)
        if not docs:
            return {"ok": True, "alerts": 0}
        now_iso = datetime.now(timezone.utc).isoformat()
        lines = []
        for d in docs:
            try:
                days_left = (datetime.strptime(d["expiry_date"][:10], "%Y-%m-%d").date() - today).days
            except Exception:
                days_left = "?"
            label = {"passport": "Pasaport/Kimlik", "visa": "Vize/Çalışma izni", "contract": "Sözleşme",
                     "address_proof": "Adres belgesi", "certificate": "Sertifika"}.get(d.get("doc_type"), d.get("doc_type"))
            msg = f"{d.get('staff_name')} — {label} {d.get('expiry_date')} tarihinde sona eriyor ({days_left} gün kaldı)"
            lines.append(msg)
            await db.notifications.insert_one({
                "id": str(uuid.uuid4()), "category": "hr_doc_expiry", "priority": "high",
                "title": "Belge süresi doluyor", "message": msg, "read": False, "created_at": now_iso})
            await db.hr_documents.update_one({"id": d["id"]}, {"$set": {"expiry_alerted_at": now_iso}})
        recipients = await db.users.find(
            {"role": {"$in": ["admin", "manager"]}, "email": {"$not": {"$regex": "test|example"}}},
            {"_id": 0, "email": 1}).to_list(20)
        html = ("<div style='font-family:sans-serif'><h3>⚠️ Belge Süresi Uyarısı</h3><ul>"
                + "".join(f"<li>{ln}</li>" for ln in lines)
                + "</ul><p>İK &amp; Bordro (UK) &gt; Personel &amp; İK ekranından belgeleri yenileyebilirsiniz.</p></div>")
        statuses = [await _send_email(r["email"], f"Belge süresi uyarısı — {len(lines)} belge", html) for r in recipients]
        return {"ok": True, "alerts": len(lines),
                "emails": {"sent": statuses.count("sent"), "mocked": statuses.count("mocked")}}

    router.run_doc_expiry_check_internal = run_doc_expiry_check_internal

    @router.post("/uk-payroll/doc-expiry/run")
    async def doc_expiry_run(data: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        return await run_doc_expiry_check_internal(data.get("property_id", "all"))

    # ==================== SHIFT REMINDER ROBOT ====================
    async def run_shift_reminders_internal(property_id: str = "all") -> dict:
        tomorrow = (datetime.now(timezone.utc) + timedelta(days=1)).date().isoformat()
        query = {"date": tomorrow, "status": {"$in": ["planned", "published", "approved"]},
                 "reminder_sent_at": {"$exists": False}}
        if property_id and property_id != "all":
            query["property_id"] = property_id
        shifts = await db.shift_entries.find(query, {"_id": 0}).to_list(300)
        if not shifts:
            return {"ok": True, "date": tomorrow, "reminders_sent": 0, "skipped_no_email": 0}
        staff_ids = list({sh.get("staff_id") for sh in shifts})
        staff_docs = await db.shift_staff.find({"id": {"$in": staff_ids}}, {"_id": 0}).to_list(300)
        smap = {s["id"]: s for s in staff_docs}
        sent = skipped = wa_sent = wa_queued = 0
        now_iso = datetime.now(timezone.utc).isoformat()
        try:
            from routes.marketing.whatsapp_voice import _send_whatsapp_reply
        except Exception:
            _send_whatsapp_reply = None
        for sh in shifts:
            st = smap.get(sh.get("staff_id"), {})
            email = st.get("email")
            phone = (st.get("phone") or "").strip()
            if not email and not phone:
                skipped += 1
                continue
            body_txt = (f"Vardiya Hatırlatması 📅 Merhaba {sh.get('staff_name')}, yarın ({sh.get('date')}) "
                        f"{sh.get('start_time')}–{sh.get('end_time')} saatleri arasında {sh.get('role', '')} vardiyanız var. İyi çalışmalar!")
            if email:
                html = (f"<div style='font-family:sans-serif'><h3>Vardiya Hatırlatması 📅</h3>"
                        f"<p>Merhaba {sh.get('staff_name')},</p>"
                        f"<p>Yarın (<b>{sh.get('date')}</b>) <b>{sh.get('start_time')}–{sh.get('end_time')}</b> "
                        f"saatleri arasında <b>{sh.get('role', '')}</b> vardiyanız bulunuyor.</p>"
                        f"<p>İyi çalışmalar!</p></div>")
                await _send_email(email, f"Yarınki vardiyanız — {sh.get('date')} {sh.get('start_time')}", html)
                sent += 1
            if phone and _send_whatsapp_reply:
                to = phone if phone.startswith("whatsapp:") else f"whatsapp:{phone if phone.startswith('+') else '+' + phone}"
                wa = await _send_whatsapp_reply(to, body_txt)
                if wa.get("status") == "sent":
                    wa_sent += 1
                else:
                    wa_queued += 1
                    logger.info(f"[MOCK WHATSAPP] to={to} shift={sh.get('date')} ({wa.get('reason') or wa.get('error', '')})")
            await db.shift_entries.update_one({"id": sh["id"]}, {"$set": {"reminder_sent_at": now_iso}})
        return {"ok": True, "date": tomorrow, "reminders_sent": sent, "skipped_no_email": skipped,
                "whatsapp_sent": wa_sent, "whatsapp_mocked": wa_queued}

    router.run_shift_reminders_internal = run_shift_reminders_internal

    @router.post("/uk-payroll/reminders/run")
    async def reminders_run(data: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        return await run_shift_reminders_internal(data.get("property_id", "all"))

    return router
