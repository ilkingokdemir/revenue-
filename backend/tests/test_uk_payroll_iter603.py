"""UK Payroll iter603 — Leave Balance, Payroll Comparison, HR Documents, WhatsApp Reminder."""
import os
import io
import subprocess
import uuid
import json as _json
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


# ==================== LEAVE BALANCE ====================
def test_leave_balance_full_flow(s):
    lst = s.get(f"{BASE_URL}/api/uk-payroll/employees/all", timeout=20).json()
    target = next((e for e in lst if e.get("employment_status") == "active"), None)
    assert target
    sid = target["id"]
    original_email = target.get("email") or ""
    original_days = target.get("annual_leave_days") or 28
    created_leave_id = None
    try:
        # Set email=admin + annual_leave_days=5
        r_up = s.put(f"{BASE_URL}/api/uk-payroll/employees/{sid}/hr",
                     json={"email": ADMIN_EMAIL, "annual_leave_days": 5}, timeout=15)
        assert r_up.status_code == 200

        # GET /me/leave-balance -> entitled:5, remaining:5
        r_bal = s.get(f"{BASE_URL}/api/uk-payroll/me/leave-balance", timeout=15)
        assert r_bal.status_code == 200
        b = r_bal.json()
        assert b["entitled"] == 5, f"entitled expected 5 got {b}"
        assert b["remaining"] == 5, f"remaining expected 5 got {b}"
        assert b["used"] == 0
        assert b["pending"] == 0

        year = datetime.now(timezone.utc).year
        # 10-day annual request -> 400
        r_over = s.post(f"{BASE_URL}/api/uk-payroll/me/leave-request",
                        json={"leave_type": "annual",
                              "start_date": f"{year}-11-01",
                              "end_date": f"{year}-11-10",
                              "reason": "TEST_iter603_over"}, timeout=15)
        assert r_over.status_code == 400, f"expected 400 got {r_over.status_code} {r_over.text}"
        assert "Yetersiz izin bakiyesi" in r_over.text

        # 3-day annual -> 200, pending:3, remaining:2
        r_ok = s.post(f"{BASE_URL}/api/uk-payroll/me/leave-request",
                      json={"leave_type": "annual",
                            "start_date": f"{year}-11-01",
                            "end_date": f"{year}-11-03",
                            "reason": "TEST_iter603_ok"}, timeout=15)
        assert r_ok.status_code == 200, r_ok.text
        lv = r_ok.json()
        created_leave_id = lv["id"]
        assert lv["days"] == 3

        r_bal2 = s.get(f"{BASE_URL}/api/uk-payroll/me/leave-balance", timeout=15).json()
        assert r_bal2["pending"] == 3, f"pending expected 3 got {r_bal2}"
        assert r_bal2["remaining"] == 2, f"remaining expected 2 got {r_bal2}"

        # Sick doesn't hit balance
        sick_start = f"{year}-11-15"
        sick_end = f"{year}-11-25"  # 11 days > 5 entitled
        r_sick = s.post(f"{BASE_URL}/api/uk-payroll/me/leave-request",
                        json={"leave_type": "sick",
                              "start_date": sick_start, "end_date": sick_end,
                              "reason": "TEST_iter603_sick"}, timeout=15)
        assert r_sick.status_code == 200, f"sick should not hit balance: {r_sick.text}"
        sick_id = r_sick.json()["id"]

    finally:
        # Restore email + annual_leave_days
        s.put(f"{BASE_URL}/api/uk-payroll/employees/{sid}/hr",
              json={"email": original_email, "annual_leave_days": original_days}, timeout=15)
        # Clean up leaves + hr_leave notifications with TEST_iter603
        _mongo('db.shift_leave_requests.deleteMany({reason:{$regex:"TEST_iter603"}}); '
               'db.notifications.deleteMany({category:"hr_leave", message:{$regex:"'
               + target.get("name", "").split(" ")[0] + '"}, created_at:{$gte:"'
               + (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat() + '"}});')


# ==================== PAYROLL COMPARISON ====================
def test_compare_april_may_2026(s):
    r = s.get(f"{BASE_URL}/api/uk-payroll/compare/all",
              params={"y1": 2026, "m1": 4, "y2": 2026, "m2": 5}, timeout=25)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["period_a"]["year"] == 2026 and d["period_a"]["month"] == 4
    assert d["period_b"]["year"] == 2026 and d["period_b"]["month"] == 5
    totals = d["totals"]
    for m in ("hours", "gross", "paye", "ni_employee", "pension_ee", "net", "employer_cost"):
        assert m in totals, f"missing metric {m}"
        assert "a" in totals[m] and "b" in totals[m] and "delta" in totals[m]
    rows = d["rows"]
    assert len(rows) >= 1
    statuses = {r["status"] for r in rows}
    assert statuses.issubset({"yeni", "ayrıldı", "her iki dönem"})


def test_compare_nonexistent_period_404(s):
    r = s.get(f"{BASE_URL}/api/uk-payroll/compare/all",
              params={"y1": 2020, "m1": 1, "y2": 2026, "m2": 5}, timeout=15)
    assert r.status_code == 404


# ==================== HR DOCUMENTS ====================
@pytest.fixture(scope="module")
def target_staff(s):
    lst = s.get(f"{BASE_URL}/api/uk-payroll/employees/all", timeout=20).json()
    return next(e for e in lst if e.get("employment_status") == "active")


def test_document_upload_list_download_delete(s, target_staff):
    sid = target_staff["id"]
    pdf_bytes = b"%PDF-1.4\n%TEST_iter603\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"
    # invalid doc_type
    r_bad_type = s.post(f"{BASE_URL}/api/uk-payroll/employees/{sid}/documents",
                        files={"file": ("t.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
                        data={"doc_type": "invalid_type"}, timeout=25)
    assert r_bad_type.status_code == 400

    # invalid ext
    r_bad_ext = s.post(f"{BASE_URL}/api/uk-payroll/employees/{sid}/documents",
                       files={"file": ("t.exe", io.BytesIO(b"MZ..."), "application/octet-stream")},
                       data={"doc_type": "contract"}, timeout=25)
    assert r_bad_ext.status_code == 400

    # valid upload
    r_up = s.post(f"{BASE_URL}/api/uk-payroll/employees/{sid}/documents",
                  files={"file": ("TEST_iter603_contract.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
                  data={"doc_type": "contract"}, timeout=25)
    assert r_up.status_code == 200, r_up.text
    doc = r_up.json()
    doc_id = doc["id"]
    assert doc["doc_type"] == "contract"
    assert doc["ext"] == "pdf"
    assert doc["size"] == len(pdf_bytes)

    # list
    r_list = s.get(f"{BASE_URL}/api/uk-payroll/employees/{sid}/documents", timeout=15)
    assert r_list.status_code == 200
    assert any(d["id"] == doc_id for d in r_list.json())

    # download
    r_dl = s.get(f"{BASE_URL}/api/uk-payroll/documents/{doc_id}/download", timeout=15)
    assert r_dl.status_code == 200
    assert r_dl.content == pdf_bytes

    # delete
    r_del = s.delete(f"{BASE_URL}/api/uk-payroll/documents/{doc_id}", timeout=15)
    assert r_del.status_code == 200

    # delete again -> 404
    r_del2 = s.delete(f"{BASE_URL}/api/uk-payroll/documents/{doc_id}", timeout=15)
    assert r_del2.status_code == 404


# ==================== WHATSAPP REMINDER ====================
def test_whatsapp_reminder_mocked(s, target_staff):
    sid = target_staff["id"]
    original_phone = target_staff.get("phone") or ""
    tomorrow = (datetime.now(timezone.utc) + timedelta(days=1)).date().isoformat()
    shift_id = None
    try:
        # Add phone
        r_up = s.put(f"{BASE_URL}/api/uk-payroll/employees/{sid}/hr",
                     json={"phone": "+447700900123"}, timeout=15)
        assert r_up.status_code == 200

        # Create shift via API
        r_sh = s.post(f"{BASE_URL}/api/shifts/entries", json={
            "property_id": target_staff.get("property_id", ""),
            "staff_id": sid, "staff_name": target_staff.get("name", ""),
            "role": target_staff.get("role", "staff"),
            "date": tomorrow, "start_time": "09:00", "end_time": "17:00",
            "status": "published"}, timeout=15)
        assert r_sh.status_code == 200, r_sh.text
        shift_id = r_sh.json()["id"]

        r_run = s.post(f"{BASE_URL}/api/uk-payroll/reminders/run", json={}, timeout=25)
        assert r_run.status_code == 200
        d = r_run.json()
        # WhatsApp mocked (no Twilio key) — since we set phone, expect ≥1
        assert d.get("whatsapp_mocked", 0) >= 1, f"expected whatsapp_mocked>=1 got {d}"
        # Total notify attempts (email + whatsapp) should be ≥1
        assert d.get("reminders_sent", 0) + d.get("whatsapp_mocked", 0) >= 1, f"no notify sent: {d}"
    finally:
        s.put(f"{BASE_URL}/api/uk-payroll/employees/{sid}/hr",
              json={"phone": original_phone}, timeout=15)
        if shift_id:
            _mongo(f'db.shift_entries.deleteOne({{id:"{shift_id}"}});')


# ==================== REGRESSION SPOT-CHECK ====================
def test_rates_preview_payslip_pdf(s):
    assert s.get(f"{BASE_URL}/api/uk-payroll/rates", timeout=10).status_code == 200
    r = s.get(f"{BASE_URL}/api/uk-payroll/preview/all",
              params={"year": 2026, "month": 5}, timeout=25)
    assert r.status_code == 200
    runs = s.get(f"{BASE_URL}/api/uk-payroll/runs/all", timeout=15).json()
    assert runs
    slips = s.get(f"{BASE_URL}/api/uk-payroll/runs/all/{runs[0]['id']}/payslips", timeout=15).json()
    assert slips
    r_pdf = s.get(f"{BASE_URL}/api/uk-payroll/payslip/{slips[0]['id']}/pdf", timeout=20)
    assert r_pdf.status_code == 200 and r_pdf.content[:4] == b"%PDF"


def test_p45_p60_bacs_spot(s):
    runs = s.get(f"{BASE_URL}/api/uk-payroll/runs/all", timeout=15).json()
    may = next((r for r in runs if r.get("year") == 2026 and r.get("month") == 5), None)
    if may:
        r_bacs = s.get(f"{BASE_URL}/api/uk-payroll/runs/{may['id']}/bacs", timeout=15)
        assert r_bacs.status_code == 200
    lst = s.get(f"{BASE_URL}/api/uk-payroll/employees/all", timeout=15).json()
    active = next((e for e in lst if e.get("employment_status") == "active"), None)
    if active:
        r_p60 = s.get(f"{BASE_URL}/api/uk-payroll/employees/{active['id']}/p60", timeout=20)
        assert r_p60.status_code == 200 and r_p60.content[:4] == b"%PDF"
