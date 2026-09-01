"""UK Payroll (2026/27) — comprehensive backend tests for iter600."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # fallback to frontend .env
    try:
        with open("/app/frontend/.env") as f:
            for ln in f:
                if ln.startswith("REACT_APP_BACKEND_URL="):
                    BASE_URL = ln.split("=", 1)[1].strip().rstrip("/")
    except Exception:
        pass

ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASS = "HotelAdmin2026!"


@pytest.fixture(scope="module")
def s():
    sess = requests.Session()
    r = sess.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=60)
    assert r.status_code == 200, f"login failed {r.status_code} {r.text}"
    return sess


# ==================== RATES ====================
def test_rates(s):
    r = s.get(f"{BASE_URL}/api/uk-payroll/rates", timeout=15)
    assert r.status_code == 200
    d = r.json()
    assert d["tax_year"] == "2026/27"
    assert d["nmw"]["21_plus"] == 12.71
    assert d["nmw"]["18_20"] == 10.85
    assert d["ni_employee"]["main_rate"] == 0.08
    assert d["ni_employer"]["rate"] == 0.15


# ==================== EMPLOYEES LIST ====================
def test_employees_list_shape(s):
    r = s.get(f"{BASE_URL}/api/uk-payroll/employees/all", timeout=20)
    assert r.status_code == 200
    lst = r.json()
    assert isinstance(lst, list)
    assert len(lst) >= 1
    e = lst[0]
    for k in ("age", "nmw_rate", "hr_missing", "hr_complete", "employment_status"):
        assert k in e, f"missing key {k}"


# ==================== HR UPDATE ====================
def test_hr_update_and_invalid_ni(s):
    lst = s.get(f"{BASE_URL}/api/uk-payroll/employees/all", timeout=20).json()
    target = next((e for e in lst if e.get("employment_status") == "active"), lst[0])
    sid = target["id"]
    # invalid NI (8 chars)
    r_bad = s.put(f"{BASE_URL}/api/uk-payroll/employees/{sid}/hr", json={"ni_number": "AB123456"}, timeout=15)
    assert r_bad.status_code == 400
    # valid update — preserve tax_code
    orig_tc = target.get("tax_code") or "1257L"
    r_ok = s.put(f"{BASE_URL}/api/uk-payroll/employees/{sid}/hr",
                 json={"tax_code": orig_tc, "ni_number": target.get("ni_number") or "AB123456C"}, timeout=15)
    assert r_ok.status_code == 200
    # 404
    r_nf = s.put(f"{BASE_URL}/api/uk-payroll/employees/nonexistent-id/hr", json={"tax_code": "1257L"}, timeout=15)
    assert r_nf.status_code == 404


# ==================== PREVIEW ====================
def test_preview_may_2026(s):
    r = s.get(f"{BASE_URL}/api/uk-payroll/preview/all", params={"year": 2026, "month": 5}, timeout=25)
    assert r.status_code == 200
    d = r.json()
    for k in ("gross", "paye", "ni_employee", "ni_employer", "net", "nmw_topup", "employer_cost"):
        assert k in d["totals"]
    assert d["staff_count"] >= 1
    # Ayşe NMW top-up check
    ayse = next((r for r in d["rows"] if "Ayşe" in r["staff_name"]), None)
    if ayse:
        # 19 yaş → £10.85, 16h × £6.25 = £100 base, expected topup £73.60
        assert ayse["nmw_rate"] == 10.85, f"expected 10.85, got {ayse['nmw_rate']}"
        assert abs(ayse["nmw_topup"] - 73.60) < 0.5, f"topup={ayse['nmw_topup']}"
        assert abs(ayse["gross"] - 173.60) < 0.5


def test_preview_invalid_month(s):
    r = s.get(f"{BASE_URL}/api/uk-payroll/preview/all", params={"year": 2026, "month": 13}, timeout=15)
    assert r.status_code == 400


# ==================== RUN (409 + force) ====================
def test_run_dedupe_and_force(s):
    r = s.post(f"{BASE_URL}/api/uk-payroll/run/all", json={"year": 2026, "month": 5}, timeout=25)
    # already exists
    assert r.status_code == 409, f"expected 409 got {r.status_code} {r.text[:200]}"
    r2 = s.post(f"{BASE_URL}/api/uk-payroll/run/all", json={"year": 2026, "month": 5, "force": True}, timeout=30)
    assert r2.status_code == 200
    d = r2.json()
    assert d["payslips_created"] >= 1


# ==================== RUNS / PAYSLIPS / PDF / EMAIL ====================
def test_runs_payslips_pdf_email(s):
    runs = s.get(f"{BASE_URL}/api/uk-payroll/runs/all", timeout=15).json()
    assert len(runs) >= 1
    run_id = runs[0]["id"]
    slips = s.get(f"{BASE_URL}/api/uk-payroll/runs/all/{run_id}/payslips", timeout=15).json()
    assert len(slips) >= 1
    # find turkish-name payslip if exists
    tr_slip = next((sl for sl in slips if any(c in sl["staff_name"] for c in "şŞıİğĞüÜöÖçÇ")), slips[0])
    r_pdf = s.get(f"{BASE_URL}/api/uk-payroll/payslip/{tr_slip['id']}/pdf", timeout=20)
    assert r_pdf.status_code == 200
    assert r_pdf.headers.get("content-type", "").startswith("application/pdf")
    assert r_pdf.content[:4] == b"%PDF"
    # email one with email
    slip_with_email = next((sl for sl in slips if sl.get("email")), None)
    if slip_with_email:
        r_em = s.post(f"{BASE_URL}/api/uk-payroll/payslip/{slip_with_email['id']}/email", timeout=20)
        assert r_em.status_code == 200
        assert r_em.json()["status"] in ("mocked", "sent")
    # email without email → 400
    slip_no_email = next((sl for sl in slips if not sl.get("email")), None)
    if slip_no_email:
        r_ne = s.post(f"{BASE_URL}/api/uk-payroll/payslip/{slip_no_email['id']}/email", timeout=15)
        assert r_ne.status_code == 400
    # email-all
    r_all = s.post(f"{BASE_URL}/api/uk-payroll/runs/{run_id}/email-all", timeout=40)
    assert r_all.status_code == 200
    d = r_all.json()
    assert "sent" in d and "mocked" in d and "skipped_no_email" in d


# ==================== OFFBOARD / REINSTATE ====================
def test_offboard_and_reinstate(s):
    lst = s.get(f"{BASE_URL}/api/uk-payroll/employees/all", timeout=20).json()
    active = [e for e in lst if e.get("employment_status") == "active"]
    assert active, "no active staff to offboard"
    # pick last (least likely to affect May payroll data)
    target = active[-1]
    sid = target["id"]
    try:
        r_off = s.post(f"{BASE_URL}/api/uk-payroll/employees/{sid}/offboard",
                       json={"leaver_date": "2026-06-30", "reason": "TEST_offboard"}, timeout=20)
        assert r_off.status_code == 200
        fp = r_off.json()["final_pay"]
        assert "total_estimate" in fp and "holiday_pay" in fp and "unpaid_shifts" in fp
        # verify status
        lst2 = s.get(f"{BASE_URL}/api/uk-payroll/employees/all", timeout=15).json()
        e2 = next((e for e in lst2 if e["id"] == sid), None)
        assert e2 and e2["employment_status"] == "leaver"
    finally:
        # ALWAYS reinstate
        r_re = s.post(f"{BASE_URL}/api/uk-payroll/employees/{sid}/reinstate", timeout=15)
        assert r_re.status_code == 200
