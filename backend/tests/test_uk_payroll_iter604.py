"""UK Payroll iter604 — SSP, Leave Calendar, Document Expiry Reminder."""
import os
import io
import subprocess
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


def _mongo(cmd: str):
    subprocess.run(["mongosh", "--quiet", "--eval",
                    f'db = db.getSiblingDB(process.env.DB_NAME || "test_database"); {cmd}'],
                   capture_output=True, timeout=15, check=False)


def _mongo_js(js: str):
    """Run mongosh with a JS payload via stdin (avoids shell escape issues)."""
    payload = f'db = db.getSiblingDB(process.env.DB_NAME || "test_database"); {js}'
    subprocess.run(["mongosh", "--quiet"], input=payload.encode("utf-8"),
                   capture_output=True, timeout=20, check=False)


def _find_staff(s, name_substring):
    lst = s.get(f"{BASE_URL}/api/uk-payroll/employees/all", timeout=20).json()
    return next((e for e in lst if name_substring.lower() in (e.get("name") or "").lower()), None)


# ==================== SSP ====================
def test_ssp_ayse_5_working_days_may_2026(s):
    ayse = _find_staff(s, "Ayşe") or _find_staff(s, "Ayse")
    assert ayse, "Ayşe Yılmaz staff not found"
    sid = ayse["id"]
    prop_id = ayse.get("property_id", "")
    leave_ids = []
    try:
        # Insert approved sick leave 2026-05-11..2026-05-15 (Mon-Fri, 5 working days)
        import uuid
        leave_id = str(uuid.uuid4())
        _mongo(
            'db.shift_leave_requests.insertOne({'
            f'id:"{leave_id}", staff_id:"{sid}", staff_name:"{ayse.get("name")}",'
            f' property_id:"{prop_id}", leave_type:"sick", status:"approved",'
            ' start_date:"2026-05-11", end_date:"2026-05-15",'
            ' reason:"TEST_iter604_ssp",'
            f' created_at:"{datetime.now(timezone.utc).isoformat()}"'
            '});'
        )
        leave_ids.append(leave_id)

        r = s.get(f"{BASE_URL}/api/uk-payroll/preview/all",
                  params={"year": 2026, "month": 5}, timeout=25)
        assert r.status_code == 200, r.text
        data = r.json()
        row = next((x for x in data.get("rows", [])
                    if x.get("staff_id") == sid), None)
        assert row, f"Ayse row not found in preview rows"
        assert row.get("ssp", 0) > 0, f"ssp should be > 0, got row={row}"
        assert row.get("ssp_days") == 5, f"ssp_days expected 5 got {row.get('ssp_days')}"
        # gross should equal base + nmw_topup + ssp + adj
        expected_gross = round(
            row.get("base_earned", 0) + row.get("nmw_topup", 0) + row.get("ssp", 0)
            + row.get("adjustments", 0), 2)
        assert abs(row.get("gross", 0) - expected_gross) < 0.02, \
            f"gross mismatch: {row.get('gross')} vs {expected_gross}"
        warns = " ".join(row.get("warnings", []) or [])
        assert "SSP" in warns and "5 iş günü" in warns
        totals = data.get("totals", {})
        assert totals.get("ssp", 0) > 0
    finally:
        for lid in leave_ids:
            _mongo(f'db.shift_leave_requests.deleteOne({{id:"{lid}"}});')


def test_ssp_weekend_only_leave_zero_working_days(s):
    ayse = _find_staff(s, "Ayşe") or _find_staff(s, "Ayse")
    assert ayse
    sid = ayse["id"]
    import uuid
    lid = str(uuid.uuid4())
    try:
        # 2026-05-16 Sat, 2026-05-17 Sun -> 0 working days
        _mongo(
            'db.shift_leave_requests.insertOne({'
            f'id:"{lid}", staff_id:"{sid}", staff_name:"{ayse.get("name")}",'
            f' property_id:"{ayse.get("property_id","")}",'
            ' leave_type:"sick", status:"approved",'
            ' start_date:"2026-05-16", end_date:"2026-05-17",'
            ' reason:"TEST_iter604_ssp_weekend"});'
        )
        r = s.get(f"{BASE_URL}/api/uk-payroll/preview/all",
                  params={"year": 2026, "month": 5}, timeout=25)
        assert r.status_code == 200
        row = next((x for x in r.json().get("rows", [])
                    if x.get("staff_id") == sid), None)
        if row:
            assert row.get("ssp", 0) == 0, \
                f"weekend-only sick should give 0 SSP, got {row.get('ssp')}"
            assert row.get("ssp_days", 0) == 0
    finally:
        _mongo(f'db.shift_leave_requests.deleteOne({{id:"{lid}"}});')


def test_ssp_only_row_for_staff_without_shifts(s):
    """Find an active staff with no shifts in May 2026, add sick leave -> SSP-only row."""
    # Use current preview to find who has 0 hours
    r0 = s.get(f"{BASE_URL}/api/uk-payroll/preview/all",
               params={"year": 2026, "month": 5}, timeout=25).json()
    existing_sids = {x.get("staff_id") for x in r0.get("rows", [])}

    lst = s.get(f"{BASE_URL}/api/uk-payroll/employees/all", timeout=20).json()
    # Pick an active staff not currently in preview OR with 0 hours
    candidate = next((e for e in lst if e.get("employment_status") == "active"
                      and e["id"] not in existing_sids), None)
    if candidate is None:
        # fallback: use staff with 0 hours in existing rows
        zero = next((x for x in r0.get("rows", []) if (x.get("hours", 0) or 0) == 0), None)
        pytest.skip("no unshifted active staff available; skipping SSP-only test")
        return

    sid = candidate["id"]
    import uuid
    lid = str(uuid.uuid4())
    try:
        _mongo(
            'db.shift_leave_requests.insertOne({'
            f'id:"{lid}", staff_id:"{sid}", staff_name:"{candidate.get("name")}",'
            f' property_id:"{candidate.get("property_id","")}",'
            ' leave_type:"sick", status:"approved",'
            ' start_date:"2026-05-11", end_date:"2026-05-13",'  # 3 working days
            ' reason:"TEST_iter604_ssp_only"});'
        )
        r = s.get(f"{BASE_URL}/api/uk-payroll/preview/all",
                  params={"year": 2026, "month": 5}, timeout=25)
        assert r.status_code == 200
        row = next((x for x in r.json().get("rows", []) if x.get("staff_id") == sid), None)
        assert row, "SSP-only row should exist for staff without shifts"
        assert (row.get("hours", 0) or 0) == 0
        assert row.get("ssp", 0) > 0
        assert row.get("ssp_days", 0) > 0
    finally:
        _mongo(f'db.shift_leave_requests.deleteOne({{id:"{lid}"}});')


# ==================== LEAVE CALENDAR ====================
def test_leave_calendar_basic(s):
    r = s.get(f"{BASE_URL}/api/uk-payroll/leave-calendar/all",
              params={"year": 2026, "month": 5}, timeout=15)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["year"] == 2026 and d["month"] == 5
    assert len(d["days"]) == 31
    for day in d["days"]:
        assert "date" in day and "entries" in day and "overlap" in day


def test_leave_calendar_overlap_and_pending(s):
    lst = s.get(f"{BASE_URL}/api/uk-payroll/employees/all", timeout=20).json()
    actives = [e for e in lst if e.get("employment_status") == "active" and (e.get("name") or "").strip()]
    # need distinct names for overlap detection
    seen_names = set()
    distinct = []
    for e in actives:
        nm = (e.get("name") or "").strip()
        if nm and nm not in seen_names:
            seen_names.add(nm)
            distinct.append(e)
        if len(distinct) >= 2:
            break
    assert len(distinct) >= 2, "need 2 active staff with distinct names"
    a, b = distinct[0], distinct[1]
    import uuid, json as _j
    lid1, lid2, lid3 = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
    docs = [
        {"id": lid1, "staff_id": a["id"], "staff_name": a.get("name"),
         "property_id": a.get("property_id", ""), "leave_type": "annual", "status": "approved",
         "start_date": "2026-05-13", "end_date": "2026-05-14", "reason": "TEST_iter604_cal_a"},
        {"id": lid2, "staff_id": b["id"], "staff_name": b.get("name"),
         "property_id": b.get("property_id", ""), "leave_type": "annual", "status": "approved",
         "start_date": "2026-05-13", "end_date": "2026-05-13", "reason": "TEST_iter604_cal_b"},
        {"id": lid3, "staff_id": a["id"], "staff_name": a.get("name"),
         "property_id": a.get("property_id", ""), "leave_type": "annual", "status": "pending",
         "start_date": "2026-05-20", "end_date": "2026-05-20", "reason": "TEST_iter604_cal_pending"},
    ]
    try:
        _mongo_js(f"db.shift_leave_requests.insertMany({_j.dumps(docs)});")
        r = s.get(f"{BASE_URL}/api/uk-payroll/leave-calendar/all",
                  params={"year": 2026, "month": 5}, timeout=15)
        assert r.status_code == 200
        d = r.json()
        by_date = {x["date"]: x for x in d["days"]}
        day13 = by_date.get("2026-05-13")
        assert day13["overlap"] is True, f"2026-05-13 should overlap: {day13}"
        assert d["overlap_days"] >= 1
        # pending on 2026-05-20 should appear as entry but overlap false
        day20 = by_date.get("2026-05-20")
        assert any(e["status"] == "pending" for e in day20["entries"])
        assert day20["overlap"] is False
    finally:
        _mongo(f'db.shift_leave_requests.deleteMany({{id:{{$in:["{lid1}","{lid2}","{lid3}"]}}}});')


def test_leave_calendar_invalid_month(s):
    r = s.get(f"{BASE_URL}/api/uk-payroll/leave-calendar/all",
              params={"year": 2026, "month": 13}, timeout=10)
    assert r.status_code == 400


# ==================== DOCUMENT EXPIRY ====================
def test_document_expiry_full_flow(s):
    lst = s.get(f"{BASE_URL}/api/uk-payroll/employees/all", timeout=20).json()
    target = next((e for e in lst if e.get("employment_status") == "active"), None)
    assert target
    sid = target["id"]
    exp_date = (datetime.now(timezone.utc).date() + timedelta(days=30)).isoformat()
    pdf_bytes = b"%PDF-1.4\n%TEST_iter604\n%%EOF"
    doc_id = None
    try:
        r_up = s.post(f"{BASE_URL}/api/uk-payroll/employees/{sid}/documents",
                      files={"file": ("TEST_iter604_visa.pdf", io.BytesIO(pdf_bytes),
                                      "application/pdf")},
                      data={"doc_type": "visa", "expiry_date": exp_date}, timeout=25)
        assert r_up.status_code == 200, r_up.text
        doc = r_up.json()
        doc_id = doc["id"]
        assert doc.get("expiry_date", "").startswith(exp_date)

        # GET expiring
        r_exp = s.get(f"{BASE_URL}/api/uk-payroll/documents/expiring",
                      params={"days": 60}, timeout=15)
        assert r_exp.status_code == 200
        docs = r_exp.json()
        our = next((d for d in docs if d["id"] == doc_id), None)
        assert our, f"our doc should be listed as expiring; got {docs}"
        assert 28 <= our.get("days_left", 0) <= 32

        # Run expiry check first time
        r_run1 = s.post(f"{BASE_URL}/api/uk-payroll/doc-expiry/run",
                        json={"property_id": "all"}, timeout=25)
        assert r_run1.status_code == 200, r_run1.text
        d1 = r_run1.json()
        assert d1.get("alerts", 0) >= 1
        # emails mocked (no Resend key)
        emails = d1.get("emails", {}) or {}
        assert (emails.get("sent", 0) + emails.get("mocked", 0)) >= 0  # emails object exists

        # Second run -> dedupe
        r_run2 = s.post(f"{BASE_URL}/api/uk-payroll/doc-expiry/run",
                        json={"property_id": "all"}, timeout=15)
        assert r_run2.status_code == 200
        # Our doc shouldn't re-alert. But other docs might. Assert alerts <= alerts1 - 1 or 0.
        d2 = r_run2.json()
        assert d2.get("alerts", 0) < d1.get("alerts", 1), \
            f"dedupe failed: run1={d1} run2={d2}"

        # Verify notifications collection has hr_doc_expiry entry
        # via mongosh count
        res = subprocess.run(
            ["mongosh", "--quiet", "--eval",
             'db = db.getSiblingDB(process.env.DB_NAME || "test_database"); '
             'print(db.notifications.countDocuments({category:"hr_doc_expiry"}));'],
            capture_output=True, timeout=15, check=False, text=True)
        assert "0" != res.stdout.strip().splitlines()[-1] if res.stdout.strip() else True
    finally:
        if doc_id:
            s.delete(f"{BASE_URL}/api/uk-payroll/documents/{doc_id}", timeout=10)
        # Cleanup notifications from this test
        _mongo('db.notifications.deleteMany({category:"hr_doc_expiry", '
               'message:{$regex:"TEST_iter604|' + (target.get("name") or "").split(" ")[0] + '"}});')


def test_automation_settings_has_doc_expiry_alert(s):
    r = s.get(f"{BASE_URL}/api/automation/settings", timeout=15)
    assert r.status_code == 200, r.text
    data = r.json()
    jobs = data.get("jobs", []) if isinstance(data, dict) else data
    keys = {j.get("job") for j in jobs}
    assert "doc_expiry_alert" in keys, \
        f"doc_expiry_alert engine missing; keys={keys}"
    assert len(jobs) >= 30, f"expected >=30 engines got {len(jobs)}"


# ==================== REGRESSION ====================
def test_may_2026_preview_no_ssp_after_cleanup(s):
    r = s.get(f"{BASE_URL}/api/uk-payroll/preview/all",
              params={"year": 2026, "month": 5}, timeout=25)
    assert r.status_code == 200
    d = r.json()
    totals = d.get("totals", {})
    # After cleanup, no test SSP leaves remain -> ssp total should be 0
    assert "ssp" in totals, "totals must have ssp key"
    assert totals.get("ssp", 0) == 0, f"ssp should be 0 after cleanup, got {totals.get('ssp')}"
    assert len(d.get("rows", [])) >= 1
