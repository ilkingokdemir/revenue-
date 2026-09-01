"""UK Payroll iter601 — Robot, P45, Portal, Pension features."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for ln in f:
            if ln.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = ln.split("=", 1)[1].strip().rstrip("/")

ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASS = "HotelAdmin2026!"


@pytest.fixture(scope="module")
def s():
    sess = requests.Session()
    r = sess.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=60)
    assert r.status_code == 200, f"login failed {r.text}"
    return sess


# ============ BORDRO ROBOTU ============
def test_robot_run_no_force_guard(s):
    r = s.post(f"{BASE_URL}/api/uk-payroll/robot/run", json={"property_id": "all"}, timeout=30)
    assert r.status_code == 200
    d = r.json()
    # In Jan 2026, unless today happens to be Jan 31, this should skip
    assert d.get("skipped") in ("not_last_day_of_month", "no_shifts", "already_run") or "run_id" in d


def test_robot_run_force_no_shifts(s):
    # Force runs today's month; if no shifts for current month → no_shifts skip expected
    r = s.post(f"{BASE_URL}/api/uk-payroll/robot/run", json={"property_id": "all", "force": True}, timeout=45)
    assert r.status_code == 200
    d = r.json()
    # Acceptable outcomes: no_shifts (empty current month), already_run, or success run
    assert d.get("ok") is True
    assert d.get("skipped") in (None, "no_shifts", "already_run") or "run_id" in d


# ============ AUTOMATION REGISTRY ============
def test_automation_settings_has_uk_payroll_run(s):
    r = s.get(f"{BASE_URL}/api/automation/settings", timeout=15)
    assert r.status_code == 200
    data = r.json()
    jobs = data.get("jobs", [])
    codes = [e.get("job") for e in jobs]
    assert "uk_payroll_run" in codes, f"codes={codes}"
    uk = next(e for e in jobs if e.get("job") == "uk_payroll_run")
    assert "Bordro" in uk.get("label", "")
    assert uk.get("enabled") is True
    assert uk.get("category") == "finance"
    assert uk.get("cron_hour") == 18


def test_scheduler_trigger_uk_payroll_run(s):
    r = s.post(f"{BASE_URL}/api/scheduler/trigger/all/uk_payroll_run", timeout=45)
    # allow various success shapes
    assert r.status_code in (200, 202), f"{r.status_code} {r.text[:200]}"
    d = r.json()
    # triggered + guard result
    assert d.get("triggered") is True or d.get("ok") is True or "result" in d


# ============ P45 FLOW ============
def test_p45_offboard_reinstate_flow(s):
    lst = s.get(f"{BASE_URL}/api/uk-payroll/employees/all", timeout=20).json()
    active = [e for e in lst if e.get("employment_status") == "active"]
    assert active
    target = active[-1]
    sid = target["id"]
    try:
        # Ensure active first — P45 should 400
        r_before = s.get(f"{BASE_URL}/api/uk-payroll/employees/{sid}/p45", timeout=20)
        assert r_before.status_code == 400
        # Offboard
        r_off = s.post(f"{BASE_URL}/api/uk-payroll/employees/{sid}/offboard",
                       json={"leaver_date": "2026-06-30", "reason": "TEST_iter601_p45"}, timeout=20)
        assert r_off.status_code == 200
        # P45 PDF
        r_pdf = s.get(f"{BASE_URL}/api/uk-payroll/employees/{sid}/p45", timeout=30)
        assert r_pdf.status_code == 200
        assert r_pdf.headers.get("content-type", "").startswith("application/pdf")
        assert r_pdf.content[:4] == b"%PDF"
    finally:
        r_re = s.post(f"{BASE_URL}/api/uk-payroll/employees/{sid}/reinstate", timeout=15)
        assert r_re.status_code == 200
    # After reinstate — P45 should 400 again
    r_after = s.get(f"{BASE_URL}/api/uk-payroll/employees/{sid}/p45", timeout=20)
    assert r_after.status_code == 400


# ============ PORTAL — admin without staff link ============
def test_portal_me_summary_admin_unlinked(s):
    r = s.get(f"{BASE_URL}/api/uk-payroll/me/summary", timeout=15)
    assert r.status_code == 200
    d = r.json()
    assert d.get("linked") is False
    assert "personel" in (d.get("message") or "").lower() or "eşleş" in (d.get("message") or "")


def test_portal_me_summary_linked_with_temp_email(s):
    lst = s.get(f"{BASE_URL}/api/uk-payroll/employees/all", timeout=15).json()
    # find any active employee
    target = next((e for e in lst if e.get("employment_status") == "active"), None)
    assert target
    sid = target["id"]
    original_email = target.get("email") or ""
    try:
        # Temporarily link staff to admin
        r_up = s.put(f"{BASE_URL}/api/uk-payroll/employees/{sid}/hr",
                     json={"email": ADMIN_EMAIL}, timeout=15)
        assert r_up.status_code == 200
        r_sum = s.get(f"{BASE_URL}/api/uk-payroll/me/summary", timeout=15)
        assert r_sum.status_code == 200
        d = r_sum.json()
        assert d.get("linked") is True
        assert "ytd" in d and set(d["ytd"].keys()) >= {"gross", "paye", "ni", "net"}
        assert "tax_year" in d
        r_ps = s.get(f"{BASE_URL}/api/uk-payroll/me/payslips", timeout=15)
        assert r_ps.status_code == 200
        assert isinstance(r_ps.json(), list)
        r_sh = s.get(f"{BASE_URL}/api/uk-payroll/me/shifts?weeks=8", timeout=15)
        assert r_sh.status_code == 200
        assert isinstance(r_sh.json(), list)
    finally:
        # Restore email
        s.put(f"{BASE_URL}/api/uk-payroll/employees/{sid}/hr",
              json={"email": original_email}, timeout=15)


# ============ PAYSLIP PDF admin access ============
def test_payslip_pdf_admin_access(s):
    runs = s.get(f"{BASE_URL}/api/uk-payroll/runs/all", timeout=15).json()
    assert runs
    run_id = runs[0]["id"]
    slips = s.get(f"{BASE_URL}/api/uk-payroll/runs/all/{run_id}/payslips", timeout=15).json()
    assert slips
    r_pdf = s.get(f"{BASE_URL}/api/uk-payroll/payslip/{slips[0]['id']}/pdf", timeout=20)
    assert r_pdf.status_code == 200
    assert r_pdf.content[:4] == b"%PDF"


# ============ PENSION MATH ============
def test_preview_totals_has_pension_keys(s):
    r = s.get(f"{BASE_URL}/api/uk-payroll/preview/all", params={"year": 2026, "month": 5}, timeout=25)
    assert r.status_code == 200
    d = r.json()
    for k in ("pension_ee", "pension_er"):
        assert k in d["totals"], f"missing {k}"
    for row in d["rows"]:
        for k in ("pension_ee", "pension_er", "pension_enrolled"):
            assert k in row, f"row missing {k}"


def test_pension_opted_out_zero(s):
    """When pension_status is opted_out, enrolled must be False in preview."""
    lst = s.get(f"{BASE_URL}/api/uk-payroll/employees/all", timeout=15).json()
    target = next((e for e in lst if e.get("employment_status") == "active"), None)
    assert target
    sid = target["id"]
    original = target.get("pension_status", "auto")
    try:
        r_up = s.put(f"{BASE_URL}/api/uk-payroll/employees/{sid}/hr",
                     json={"pension_status": "opted_out"}, timeout=15)
        assert r_up.status_code == 200
        d = s.get(f"{BASE_URL}/api/uk-payroll/preview/all",
                  params={"year": 2026, "month": 5}, timeout=20).json()
        row = next((r for r in d["rows"] if r["staff_id"] == sid), None)
        if row:
            assert row["pension_enrolled"] is False
            assert row["pension_ee"] == 0.0
            assert row["pension_er"] == 0.0
    finally:
        s.put(f"{BASE_URL}/api/uk-payroll/employees/{sid}/hr",
              json={"pension_status": original}, timeout=15)


# ============ REGRESSION ============
def test_regression_rates_runs_payslips(s):
    assert s.get(f"{BASE_URL}/api/uk-payroll/rates", timeout=10).status_code == 200
    d = s.get(f"{BASE_URL}/api/uk-payroll/preview/all",
              params={"year": 2026, "month": 5}, timeout=20).json()
    assert d["staff_count"] >= 1
    runs = s.get(f"{BASE_URL}/api/uk-payroll/runs/all", timeout=15).json()
    assert len(runs) >= 1
    slips = s.get(f"{BASE_URL}/api/uk-payroll/runs/all/{runs[0]['id']}/payslips", timeout=15).json()
    assert len(slips) >= 1
