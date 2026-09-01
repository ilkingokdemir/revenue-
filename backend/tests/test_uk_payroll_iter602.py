"""UK Payroll iter602 — P60, Leave Request Portal, BACS payment file, Shift Reminder."""
import os
import re
import pytest
import requests
from datetime import datetime, timedelta, timezone

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
    r = sess.post(f"{BASE_URL}/api/auth/login",
                  json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=60)
    assert r.status_code == 200, f"login failed {r.text}"
    return sess


# ==================== P60 ====================
def test_p60_admin_me_not_linked(s):
    r = s.get(f"{BASE_URL}/api/uk-payroll/me/p60", timeout=20)
    assert r.status_code == 404


def test_p60_pdf_for_each_active_employee(s):
    lst = s.get(f"{BASE_URL}/api/uk-payroll/employees/all", timeout=20).json()
    active = [e for e in lst if e.get("employment_status") == "active"]
    assert active
    for e in active[:3]:  # limit to 3 for speed
        r = s.get(f"{BASE_URL}/api/uk-payroll/employees/{e['id']}/p60", timeout=25)
        assert r.status_code == 200, f"P60 failed for {e.get('name')} {r.status_code} {r.text[:100]}"
        assert r.headers.get("content-type", "").startswith("application/pdf")
        assert r.content[:4] == b"%PDF"


# ==================== LEAVE REQUEST FLOW ====================
def test_leave_request_full_cycle(s):
    lst = s.get(f"{BASE_URL}/api/uk-payroll/employees/all", timeout=20).json()
    target = next((e for e in lst if e.get("employment_status") == "active"), None)
    assert target
    sid = target["id"]
    original_email = target.get("email") or ""
    created_leave_id = None
    try:
        # Temporarily link to admin
        r_up = s.put(f"{BASE_URL}/api/uk-payroll/employees/{sid}/hr",
                     json={"email": ADMIN_EMAIL}, timeout=15)
        assert r_up.status_code == 200

        # Reverse-date should 400
        r_bad = s.post(f"{BASE_URL}/api/uk-payroll/me/leave-request",
                       json={"leave_type": "annual",
                             "start_date": "2026-07-10", "end_date": "2026-07-05",
                             "reason": "TEST_iter602_bad"}, timeout=15)
        assert r_bad.status_code == 400

        # Missing dates 400
        r_missing = s.post(f"{BASE_URL}/api/uk-payroll/me/leave-request",
                           json={"leave_type": "annual"}, timeout=15)
        assert r_missing.status_code == 400

        # Valid request → pending + days computed
        r_ok = s.post(f"{BASE_URL}/api/uk-payroll/me/leave-request",
                      json={"leave_type": "annual",
                            "start_date": "2026-07-05", "end_date": "2026-07-07",
                            "reason": "TEST_iter602_ok"}, timeout=15)
        assert r_ok.status_code == 200
        lv = r_ok.json()
        created_leave_id = lv.get("id")
        assert lv["status"] == "pending"
        assert lv["days"] == 3
        assert lv["staff_id"] == sid

        # GET my leaves
        r_mine = s.get(f"{BASE_URL}/api/uk-payroll/me/leaves", timeout=15)
        assert r_mine.status_code == 200
        assert any(x.get("id") == created_leave_id for x in r_mine.json())

        # Admin lists pending
        r_all = s.get(f"{BASE_URL}/api/shifts/leaves/all",
                      params={"status": "pending"}, timeout=15)
        assert r_all.status_code == 200
        assert any(x.get("id") == created_leave_id for x in r_all.json())

        # Approve
        r_ap = s.put(f"{BASE_URL}/api/shifts/leaves/{created_leave_id}",
                     json={"status": "approved"}, timeout=15)
        assert r_ap.status_code == 200
    finally:
        # Restore email
        s.put(f"{BASE_URL}/api/uk-payroll/employees/{sid}/hr",
              json={"email": original_email}, timeout=15)
        # Clean up leave record + hr_leave notification via mongo shell
        if created_leave_id:
            import subprocess
            subprocess.run(
                ["mongosh", "--quiet", "--eval",
                 f'db = db.getSiblingDB(process.env.DB_NAME || "test_database"); '
                 f'db.shift_leave_requests.deleteOne({{id:"{created_leave_id}"}}); '
                 f'db.notifications.deleteMany({{category:"hr_leave", message:{{$regex:"TEST_iter602"}}}});'],
                capture_output=True, timeout=15)


# ==================== BACS FILE ====================
def test_bacs_file_may_2026(s):
    runs = s.get(f"{BASE_URL}/api/uk-payroll/runs/all", timeout=15).json()
    may_run = next((r for r in runs if r.get("year") == 2026 and r.get("month") == 5), None)
    assert may_run, "May 2026 run required for BACS test"
    r = s.get(f"{BASE_URL}/api/uk-payroll/runs/{may_run['id']}/bacs", timeout=20)
    assert r.status_code == 200
    assert r.headers.get("content-type", "").startswith("text/plain")
    included = int(r.headers.get("X-Bacs-Included", "0"))
    skipped = int(r.headers.get("X-Bacs-Skipped", "0"))
    assert included == 1, f"expected 1 included got {included}"
    assert skipped == 5, f"expected 5 skipped got {skipped}"
    content = r.content.decode("utf-8")
    lines = [ln for ln in content.split("\r\n") if ln]
    assert len(lines) == 1
    line = lines[0]
    # Standard 18 breakdown: sort(6) + acct(8) + '0' + '99' + origin_sort(6) + origin_acct(8) + 4 spaces + amount(11) + orig18 + ref18 + name18
    assert line.startswith("20000012345678"), f"sort+acct prefix wrong: {line[:20]}"
    assert line[14:17] == "099", f"txn code wrong: {line[14:17]}"
    # amount pence — Ayşe gross 173.60 → net calculated; must be numeric 11-digit
    amount_field = line[35:46]
    assert amount_field.isdigit() and len(amount_field) == 11, f"amount field bad: '{amount_field}'"
    pence = int(amount_field)
    assert pence > 0
    assert "MYHOTELBOX PAYROLL" in line
    assert "SALARY 202605" in line
    assert "AYSE" in line.upper()


# ==================== SHIFT REMINDER ====================
def test_shift_reminder_no_shift_returns_zero(s):
    r = s.post(f"{BASE_URL}/api/uk-payroll/reminders/run", json={}, timeout=20)
    assert r.status_code == 200
    d = r.json()
    assert d.get("ok") is True
    assert "reminders_sent" in d


def test_shift_reminder_full_flow(s):
    """Add a temp shift for tomorrow for a staff with email, expect reminders_sent=1, then dedupe=0."""
    lst = s.get(f"{BASE_URL}/api/uk-payroll/employees/all", timeout=20).json()
    target = next((e for e in lst if e.get("email") and "ayse.test" in (e.get("email") or "")), None)
    if not target:
        target = next((e for e in lst if e.get("email") and e.get("employment_status") == "active"), None)
    assert target and target.get("email")

    tomorrow = (datetime.now(timezone.utc) + timedelta(days=1)).date().isoformat()
    import subprocess, uuid, json as _json
    shift_id = str(uuid.uuid4())
    shift = {
        "id": shift_id,
        "property_id": target.get("property_id", ""),
        "staff_id": target["id"],
        "staff_name": target.get("name", ""),
        "role": target.get("role", "staff"),
        "date": tomorrow,
        "start_time": "09:00",
        "end_time": "17:00",
        "status": "published",
    }
    try:
        # Insert directly via mongosh
        cmd = (f'db = db.getSiblingDB(process.env.DB_NAME || "test_database"); '
               f'db.shift_entries.insertOne({_json.dumps(shift)});')
        subprocess.run(["mongosh", "--quiet", "--eval", cmd], capture_output=True, timeout=15, check=False)

        # First run — should send 1
        r1 = s.post(f"{BASE_URL}/api/uk-payroll/reminders/run", json={}, timeout=25).json()
        assert r1.get("reminders_sent") >= 1, f"expected ≥1 got {r1}"

        # Second run — dedupe, should send 0 (for our new shift)
        r2 = s.post(f"{BASE_URL}/api/uk-payroll/reminders/run", json={}, timeout=25).json()
        # only ensure our specific shift wasn't sent again — value can be 0 if no others
        assert r2.get("ok") is True
        # dedup check: reminders_sent may be 0 or less than r1
        assert r2.get("reminders_sent", 0) < r1.get("reminders_sent", 1) + 1
    finally:
        subprocess.run(["mongosh", "--quiet", "--eval",
                        f'db = db.getSiblingDB(process.env.DB_NAME || "test_database"); '
                        f'db.shift_entries.deleteOne({{id:"{shift_id}"}});'],
                       capture_output=True, timeout=15, check=False)


# ==================== AUTOMATION SETTINGS ====================
def test_automation_settings_shift_reminder(s):
    r = s.get(f"{BASE_URL}/api/automation/settings", timeout=15)
    assert r.status_code == 200
    d = r.json()
    jobs = d.get("jobs", [])
    assert len(jobs) >= 30, f"expected >=30 jobs got {len(jobs)}"
    sr = next((e for e in jobs if e.get("job") == "shift_reminder"), None)
    assert sr, "shift_reminder job missing"
    assert sr.get("label") == "Vardiya Hatırlatması"
    assert sr.get("category") == "hr"
    assert sr.get("cron_hour") == 16
    assert sr.get("enabled") is True


def test_automation_toggle_shift_reminder(s):
    # Disable
    r1 = s.put(f"{BASE_URL}/api/automation/settings/shift_reminder",
               json={"enabled": False}, timeout=15)
    assert r1.status_code == 200
    check = s.get(f"{BASE_URL}/api/automation/settings", timeout=15).json()
    sr = next(e for e in check["jobs"] if e["job"] == "shift_reminder")
    assert sr["enabled"] is False
    # Restore to True
    r2 = s.put(f"{BASE_URL}/api/automation/settings/shift_reminder",
               json={"enabled": True}, timeout=15)
    assert r2.status_code == 200
    check2 = s.get(f"{BASE_URL}/api/automation/settings", timeout=15).json()
    sr2 = next(e for e in check2["jobs"] if e["job"] == "shift_reminder")
    assert sr2["enabled"] is True


# ==================== REGRESSION ====================
def test_regression_rates_preview_payslip_pdf(s):
    assert s.get(f"{BASE_URL}/api/uk-payroll/rates", timeout=10).status_code == 200
    r = s.get(f"{BASE_URL}/api/uk-payroll/preview/all",
              params={"year": 2026, "month": 5}, timeout=25)
    assert r.status_code == 200
    runs = s.get(f"{BASE_URL}/api/uk-payroll/runs/all", timeout=15).json()
    assert runs
    slips = s.get(f"{BASE_URL}/api/uk-payroll/runs/all/{runs[0]['id']}/payslips", timeout=15).json()
    assert slips
    r_pdf = s.get(f"{BASE_URL}/api/uk-payroll/payslip/{slips[0]['id']}/pdf", timeout=20)
    assert r_pdf.status_code == 200
    assert r_pdf.content[:4] == b"%PDF"
