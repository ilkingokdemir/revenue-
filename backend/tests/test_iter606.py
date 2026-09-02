"""Iteration 606 backend tests: booking widget signals/OTA compare + UK payroll notifications."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/") or "http://localhost:8001"
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"


@pytest.fixture(scope="module")
def sess():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return s


# ==================== Booking Widget: signals + OTA compare ====================
class TestWidgetSignals:
    def test_check_availability_sports_signal(self):
        r = requests.post(f"{BASE_URL}/api/booking-widget/check-availability",
                          json={"property_id": "default", "check_in": "2026-09-12", "check_out": "2026-09-16"})
        assert r.status_code == 200, r.text
        data = r.json()
        rooms = data.get("available_rooms", [])
        assert len(rooms) > 0, "expected available rooms"
        for room in rooms:
            pe = room.get("price_explanation", {})
            signals = pe.get("signals", [])
            assert isinstance(signals, list) and len(signals) > 0, f"signals empty for {room.get('name')}"
            icons = [s.get("icon") for s in signals]
            # unique icons per kind
            assert len(icons) == len(set(icons)), f"duplicate icon kinds: {icons}"
            oc = room.get("ota_compare", {})
            assert "ota_total" in oc and "direct_total" in oc and "saving" in oc and "pct" in oc
            assert oc["pct"] == 5, f"expected default pct=5, got {oc['pct']}"
            assert oc["ota_total"] >= oc["direct_total"]
        # sports signal present
        signals0 = rooms[0]["price_explanation"]["signals"]
        assert any(s.get("icon") == "🏟️" and s.get("label_en") == "Major sports event in town"
                   for s in signals0), f"missing sports signal: {signals0}"

    def test_check_availability_public_holiday_signal(self):
        r = requests.post(f"{BASE_URL}/api/booking-widget/check-availability",
                          json={"property_id": "default", "check_in": "2026-09-09", "check_out": "2026-09-11"})
        assert r.status_code == 200, r.text
        rooms = r.json().get("available_rooms", [])
        assert rooms
        signals = rooms[0]["price_explanation"]["signals"]
        assert any(s.get("kind") == "holiday" and "Jeûne genevois" in (s.get("label_en") or "")
                   for s in signals), f"missing holiday signal: {signals}"


# ==================== Widget config theme (pct + OTA banner) ====================
class TestWidgetConfig:
    def test_info_theme_defaults(self):
        r = requests.get(f"{BASE_URL}/api/booking-widget/info/default")
        assert r.status_code == 200, r.text
        theme = r.json().get("theme", {})
        assert theme.get("direct_advantage_pct") == 5
        assert theme.get("ota_banner_enabled") is True

    def test_update_pct_then_restore(self, sess):
        # PUT to 8
        r = sess.put(f"{BASE_URL}/api/booking-widget/config/default",
                     json={"direct_advantage_pct": 8, "ota_banner_enabled": True, "accent_color": "#1a3c5e"})
        assert r.status_code == 200, r.text
        # info should reflect
        info = requests.get(f"{BASE_URL}/api/booking-widget/info/default").json()
        assert info["theme"]["direct_advantage_pct"] == 8
        # availability ota_compare.pct==8
        avail = requests.post(f"{BASE_URL}/api/booking-widget/check-availability",
                              json={"property_id": "default", "check_in": "2026-09-12", "check_out": "2026-09-16"}).json()
        assert avail["available_rooms"][0]["ota_compare"]["pct"] == 8
        # restore to 5
        r2 = sess.put(f"{BASE_URL}/api/booking-widget/config/default",
                      json={"direct_advantage_pct": 5, "ota_banner_enabled": True, "accent_color": "#1a3c5e"})
        assert r2.status_code == 200
        info2 = requests.get(f"{BASE_URL}/api/booking-widget/info/default").json()
        assert info2["theme"]["direct_advantage_pct"] == 5


# ==================== UK Payroll notifications (mock delivery) ====================
class TestPayrollNotifications:
    def test_april_run_flow(self, sess):
        # Find April 2026 run
        r = sess.get(f"{BASE_URL}/api/uk-payroll/runs/all")
        assert r.status_code == 200, r.text
        runs = r.json()
        april = next((x for x in runs if x.get("month") == 4 and x.get("year") == 2026), None)
        assert april, f"no April 2026 run; runs={[(x.get('year'), x.get('month')) for x in runs]}"
        run_id = april["id"]

        # Ensure locked
        if not april.get("locked"):
            rL = sess.post(f"{BASE_URL}/api/uk-payroll/runs/{run_id}/lock")
            assert rL.status_code == 200, rL.text

        # Clean any existing pending correction for this run to avoid 409
        cs = sess.get(f"{BASE_URL}/api/uk-payroll/corrections/all").json()
        # No delete endpoint; if a pending one exists, decide it as reject to clear
        for c in cs:
            if c.get("run_id") == run_id and c.get("status") == "pending":
                sess.post(f"{BASE_URL}/api/uk-payroll/corrections/{c['id']}/decide",
                          json={"decision": "reject", "note": "cleanup"})

        # Ensure locked (in case a prior approve unlocked)
        cur = sess.get(f"{BASE_URL}/api/uk-payroll/runs/all").json()
        cur_april = next(x for x in cur if x["id"] == run_id)
        if not cur_april.get("locked"):
            sess.post(f"{BASE_URL}/api/uk-payroll/runs/{run_id}/lock")

        # correction-request
        rC = sess.post(f"{BASE_URL}/api/uk-payroll/runs/{run_id}/correction-request",
                       json={"reason": "Bildirim testi"})
        assert rC.status_code == 200, rC.text
        cr = rC.json()
        delivery = cr.get("delivery") or {}
        assert delivery.get("mode") == "mock", f"expected mock, got {delivery}"
        assert delivery.get("emails", 0) >= 1, f"expected >=1 emails, got {delivery}"
        # whatsapp may be 0
        assert "whatsapp" in delivery
        corr_id = cr["id"]

        # decide reject
        rD = sess.post(f"{BASE_URL}/api/uk-payroll/corrections/{corr_id}/decide",
                       json={"decision": "reject"})
        assert rD.status_code == 200, rD.text
        d_delivery = rD.json().get("delivery") or {}
        assert d_delivery.get("mode") == "mock"
        assert "emails" in d_delivery

        # unlock
        rU = sess.post(f"{BASE_URL}/api/uk-payroll/runs/{run_id}/unlock",
                       json={"reason": "test unlock"})
        assert rU.status_code == 200, rU.text
        u_delivery = rU.json().get("delivery") or {}
        assert u_delivery.get("mode") == "mock"
        assert "emails" in u_delivery

        # re-lock as required by request
        rL2 = sess.post(f"{BASE_URL}/api/uk-payroll/runs/{run_id}/lock")
        assert rL2.status_code == 200

        # notification log has entries with email_mocked>0
        rL = sess.get(f"{BASE_URL}/api/uk-payroll/notification-log")
        assert rL.status_code == 200
        log = rL.json()
        assert isinstance(log, list) and len(log) > 0
        assert any(e.get("email_mocked", 0) > 0 for e in log), f"no email_mocked>0 in log: {log[:3]}"
