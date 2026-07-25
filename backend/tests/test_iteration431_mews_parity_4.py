"""Iteration 431 — Mews parity: Public Spaces booking, VCC automation,
Invoice reminders, Kiosk ID capture + dispatch."""
import os
import time
import uuid
import pytest
import requests
from datetime import datetime, timedelta, timezone

BASE = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE:
    with open("/app/frontend/.env") as f:
        for ln in f:
            if ln.startswith("REACT_APP_BACKEND_URL="):
                BASE = ln.split("=", 1)[1].strip().rstrip("/")

ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PW = "HotelAdmin2026!"


@pytest.fixture(scope="module")
def auth():
    s = requests.Session()
    r = s.post(f"{BASE}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PW}, timeout=20)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:300]}"
    tok = r.json().get("token")
    s.headers.update({"Authorization": f"Bearer {tok}"})
    return s


# ===================== (a) Public Spaces =====================

class TestPublicSpaces:
    def test_public_spaces_all(self):
        r = requests.get(f"{BASE}/api/public/spaces/all", timeout=20)
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        assert "property_name" in data
        assert "spaces" in data and isinstance(data["spaces"], list)
        # No guest data leak in busy windows
        for sp in data["spaces"]:
            for b in sp.get("busy", []):
                assert "guest_name" not in b
                assert "start" in b and "end" in b
            assert "rate_per_unit" in sp
            assert "open_hour" in sp and "close_hour" in sp

    def test_public_book_and_conflict_meeting_room(self):
        r = requests.get(f"{BASE}/api/public/spaces/all", timeout=20)
        data = r.json()
        # find a meeting_room
        mr = next((s for s in data["spaces"] if s.get("kind") == "meeting_room" and s.get("unit_minutes")), None)
        if not mr:
            pytest.skip("No meeting_room space available to test exclusivity")
        # pick a random far-future slot to avoid clash across test runs
        import random
        days_ahead = random.randint(30, 200)
        future = (datetime.now(timezone.utc) + timedelta(days=days_ahead)).date().isoformat()
        oh = int(mr.get("open_hour", 9))
        ch = int(mr.get("close_hour", 22))
        hr = random.randint(max(oh, 9), max(oh + 1, ch - 2))
        start = f"{future}T{hr:02d}:00:00"
        end = f"{future}T{hr+1:02d}:00:00"
        payload = {"space_id": mr["id"], "start": start, "end": end,
                   "guest_name": f"QA_{uuid.uuid4().hex[:6]}"}
        r1 = requests.post(f"{BASE}/api/public/spaces/book", json=payload, timeout=20)
        assert r1.status_code == 200, r1.text[:300]
        b = r1.json()["booking"]
        assert b["source"] == "public"
        # price = 1 hour × rate
        assert abs(float(b["price"]) - float(mr["rate_per_unit"])) < 0.01
        # 2nd booking same slot => 409
        payload2 = dict(payload, guest_name=f"QA_{uuid.uuid4().hex[:6]}")
        r2 = requests.post(f"{BASE}/api/public/spaces/book", json=payload2, timeout=20)
        assert r2.status_code == 409, f"expected 409, got {r2.status_code} {r2.text[:200]}"

    def test_public_book_price_multi_hour(self):
        r = requests.get(f"{BASE}/api/public/spaces/all", timeout=20)
        data = r.json()
        sp = next((s for s in data["spaces"] if s.get("unit_minutes") == 60 and s.get("kind") != "meeting_room"), None)
        if not sp:
            pytest.skip("No hourly non-meeting space")
        future = (datetime.now(timezone.utc) + timedelta(days=21)).date().isoformat()
        oh = int(sp.get("open_hour", 8))
        hr = max(oh, 9)
        payload = {"space_id": sp["id"],
                   "start": f"{future}T{hr:02d}:00:00",
                   "end": f"{future}T{hr+3:02d}:00:00",
                   "guest_name": f"QA_{uuid.uuid4().hex[:6]}"}
        r1 = requests.post(f"{BASE}/api/public/spaces/book", json=payload, timeout=20)
        assert r1.status_code == 200, r1.text[:300]
        b = r1.json()["booking"]
        expected = round(3 * float(sp["rate_per_unit"]), 2)
        assert abs(float(b["price"]) - expected) < 0.01


# ===================== (b) VCC automation =====================

class TestVCC:
    def test_vcc_summary(self, auth):
        r = auth.get(f"{BASE}/api/vcc/all", timeout=20)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        s = d.get("summary", {})
        for k in ("pending_count", "pending_amount", "due_today_count",
                  "due_today_amount", "failed_count", "charged_30d_amount"):
            assert k in s, f"missing {k}"
        assert "cards" in d

    def test_vcc_scan_idempotent(self, auth):
        r1 = auth.post(f"{BASE}/api/vcc/scan", json={}, timeout=30)
        assert r1.status_code == 200, r1.text[:300]
        r2 = auth.post(f"{BASE}/api/vcc/scan", json={}, timeout=30)
        assert r2.status_code == 200
        assert r2.json().get("created", 0) == 0, f"2nd scan should be idempotent: {r2.json()}"

    def test_vcc_charge_and_conflict(self, auth):
        # trigger scan for cards to exist
        auth.post(f"{BASE}/api/vcc/scan", json={}, timeout=30)
        cards = auth.get(f"{BASE}/api/vcc/all", timeout=20).json().get("cards", [])
        pending = [c for c in cards if c.get("status") == "pending"]
        if not pending:
            pytest.skip("No pending VCCs to charge")
        cid = pending[0]["id"]
        r1 = auth.post(f"{BASE}/api/vcc/{cid}/charge", timeout=30)
        assert r1.status_code == 200, r1.text[:300]
        assert r1.json().get("charged", 0) >= 1
        r2 = auth.post(f"{BASE}/api/vcc/{cid}/charge", timeout=30)
        assert r2.status_code == 409, f"expected 409 repeat charge, got {r2.status_code}"

    def test_vcc_run(self, auth):
        r = auth.post(f"{BASE}/api/vcc/run", timeout=30)
        assert r.status_code == 200, r.text[:300]
        assert "charged" in r.json()

    def test_automation_settings_includes_jobs(self, auth):
        r = auth.get(f"{BASE}/api/automation/settings", timeout=20)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        blob = str(d)
        assert "vcc_auto_charge" in blob, f"vcc_auto_charge job missing"
        assert "invoice_reminders" in blob, f"invoice_reminders job missing"


# ===================== (c) Invoice reminders =====================

class TestInvoiceReminders:
    def test_list(self, auth):
        r = auth.get(f"{BASE}/api/invoice-reminders", timeout=20)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert "overdue_invoices" in d
        assert "summary" in d
        assert "reminder_log" in d
        # validate level assignment
        for inv in d["overdue_invoices"]:
            days = inv["days_overdue"]
            exp = 1 if days <= 7 else (2 if days <= 21 else 3)
            assert inv["level"] == exp, f"level mismatch days={days} lvl={inv['level']}"

    def test_run_idempotent(self, auth):
        r1 = auth.post(f"{BASE}/api/invoice-reminders/run", timeout=30)
        assert r1.status_code == 200, r1.text[:300]
        r2 = auth.post(f"{BASE}/api/invoice-reminders/run", timeout=30)
        assert r2.status_code == 200
        d2 = r2.json()
        # After first run, 2nd should send 0 (per-level idempotent) OR maintain skipped
        assert d2.get("reminders_sent", 0) == 0, f"2nd run not idempotent: {d2}"

    def test_manual_send(self, auth):
        d = auth.get(f"{BASE}/api/invoice-reminders", timeout=20).json()
        ov = d.get("overdue_invoices", [])
        if not ov:
            pytest.skip("No overdue invoices to send manual reminder")
        inv_id = ov[0]["id"]
        r = auth.post(f"{BASE}/api/invoice-reminders/{inv_id}/send", timeout=20)
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        assert body.get("ok") is True
        # mock email is expected behavior
        assert body.get("email_status") in ("mock", "sent"), body

    def test_manual_send_404(self, auth):
        r = auth.post(f"{BASE}/api/invoice-reminders/does-not-exist-xyz/send", timeout=20)
        assert r.status_code == 404


# ===================== (d) Kiosk =====================

class TestKiosk:
    def _get_booking_id(self, auth):
        # find any booking
        for endpoint in ("/api/bookings", "/api/bookings/all"):
            r = auth.get(f"{BASE}{endpoint}", timeout=20)
            if r.status_code == 200:
                data = r.json()
                if isinstance(data, list) and data:
                    return data[0].get("id")
                if isinstance(data, dict):
                    for k in ("bookings", "items", "results"):
                        if isinstance(data.get(k), list) and data[k]:
                            return data[k][0].get("id")
        return None

    def test_kiosk_dispatch_and_claim(self, auth):
        bid = self._get_booking_id(auth)
        if not bid:
            pytest.skip("No booking id available")
        r = auth.post(f"{BASE}/api/guest-journey/kiosk-dispatch", json={"booking_id": bid}, timeout=20)
        assert r.status_code == 200, r.text[:300]
        qid = r.json()["queue"]["id"]

        r2 = requests.get(f"{BASE}/api/guest-journey/kiosk-queue/all", timeout=20)
        assert r2.status_code == 200
        rows = r2.json()
        assert any(row["id"] == qid for row in rows), f"queue entry {qid} not found in {rows}"

        r3 = requests.post(f"{BASE}/api/guest-journey/kiosk-queue/{qid}/claim", timeout=20)
        assert r3.status_code == 200

        r4 = requests.get(f"{BASE}/api/guest-journey/kiosk-queue/all", timeout=20)
        rows2 = r4.json()
        assert not any(row["id"] == qid for row in rows2), "queue entry not cleared after claim"

    def test_kiosk_id_capture(self, auth):
        bid = self._get_booking_id(auth)
        if not bid:
            pytest.skip("No booking id available")
        big = "A" * 500
        r = requests.post(f"{BASE}/api/guest-journey/kiosk-id-capture/{bid}",
                          json={"kind": "id", "image_base64": big}, timeout=20)
        assert r.status_code == 200, r.text[:300]
        assert "scan_id" in r.json()

        r2 = requests.post(f"{BASE}/api/guest-journey/kiosk-id-capture/{bid}",
                           json={"kind": "selfie", "image_base64": big}, timeout=20)
        assert r2.status_code == 200

        # invalid kind
        r3 = requests.post(f"{BASE}/api/guest-journey/kiosk-id-capture/{bid}",
                           json={"kind": "bogus", "image_base64": big}, timeout=20)
        assert r3.status_code == 400

        # small image
        r4 = requests.post(f"{BASE}/api/guest-journey/kiosk-id-capture/{bid}",
                           json={"kind": "id", "image_base64": "x"}, timeout=20)
        assert r4.status_code == 400

    def test_kiosk_id_scans_list(self, auth):
        bid = self._get_booking_id(auth)
        if not bid:
            pytest.skip("No booking id available")
        r = auth.get(f"{BASE}/api/guest-journey/kiosk-id-scans/{bid}", timeout=20)
        assert r.status_code == 200
        assert isinstance(r.json(), list)
