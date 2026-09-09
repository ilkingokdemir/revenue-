"""Iter638 - Paket 40 tests: funnel alerts, review auto-tag, installments settings + intent."""
import os
import time
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
ADMIN = {"email": "admin@hotelbox.com", "password": "HotelAdmin2026!"}
PID = "aldgate-flats"
NEW_PID = "city-rooms"  # separate property for fresh funnel alert test


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE}/api/auth/login", json=ADMIN, timeout=15)
    assert r.status_code == 200, r.text
    return r.json().get("access_token") or r.json().get("token")


@pytest.fixture(scope="module")
def H(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


# ---------------- Funnel alerts ----------------
class TestFunnelAlerts:
    def test_seed_events_and_check_alerts(self, H):
        # Seed 25 sessions with only search+rooms+rate_select (large drop before details/confirm) for NEW_PID
        for i in range(25):
            sid = f"sess-i638-{uuid.uuid4().hex[:8]}"
            for step in ("search", "rooms", "rate_select"):
                r = requests.post(f"{BASE}/api/booking/funnel/event",
                                  json={"property_id": NEW_PID, "session_id": sid, "step": step, "device": "desktop"}, timeout=10)
                assert r.status_code == 200, f"seed failed: {r.status_code} {r.text}"
        # First check → should create alert(s) with drop_24h >= 60 for details/payment/confirm
        r = requests.post(f"{BASE}/api/booking/funnel-alerts/{NEW_PID}/check", headers=H, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["checked"] >= 1
        alerts = data["alerts"]
        # Expect at least one alert on details/payment/confirm with drop_24h >= 60
        assert alerts, f"expected alerts, got {data}"
        for a in alerts:
            assert a["drop_24h"] >= 60
            assert a["email_status"] == ["mocked"] or all(s == "mocked" for s in a["email_status"])
            assert a["property_id"] == NEW_PID

    def test_dedupe_second_check(self, H):
        r = requests.post(f"{BASE}/api/booking/funnel-alerts/{NEW_PID}/check", headers=H, timeout=30)
        assert r.status_code == 200
        # Same-day dedupe → alerts empty
        assert r.json()["alerts"] == []

    def test_list_alerts(self, H):
        r = requests.get(f"{BASE}/api/booking/funnel-alerts/{NEW_PID}", headers=H, timeout=15)
        assert r.status_code == 200
        alerts = r.json()["alerts"]
        assert isinstance(alerts, list) and len(alerts) >= 1
        assert all(a["property_id"] == NEW_PID for a in alerts)

    def test_disabled_setting_skips(self, H):
        r = requests.put(f"{BASE}/api/booking/be-settings/{NEW_PID}", headers=H,
                         json={"funnel_alert_enabled": False}, timeout=10)
        assert r.status_code == 200
        assert r.json()["funnel_alert_enabled"] is False
        r2 = requests.post(f"{BASE}/api/booking/funnel-alerts/{NEW_PID}/check", headers=H, timeout=15)
        assert r2.status_code == 200
        assert r2.json()["checked"] == 0
        assert r2.json()["alerts"] == []
        # restore
        requests.put(f"{BASE}/api/booking/be-settings/{NEW_PID}", headers=H, json={"funnel_alert_enabled": True}, timeout=10)


# ---------------- Auto-tag reviews ----------------
class TestAutoTag:
    def test_reset_then_autotag(self, H):
        r = requests.post(f"{BASE}/api/booking/room-reviews/{PID}/reset-tags", headers=H, timeout=15)
        assert r.status_code == 200
        reset_count = r.json().get("reset", 0)
        assert isinstance(reset_count, int)

        r = requests.post(f"{BASE}/api/booking/room-reviews/{PID}/auto-tag?limit=10", headers=H, timeout=90)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "tagged" in d and "processed" in d
        assert d["source"] in ("ai", "heuristic", "none")

    def test_second_autotag_processes_zero(self, H):
        r = requests.post(f"{BASE}/api/booking/room-reviews/{PID}/auto-tag?limit=10", headers=H, timeout=60)
        assert r.status_code == 200
        # Already attempted → processed 0
        assert r.json()["processed"] == 0

    def test_room_reviews_lists_rooms(self):
        r = requests.get(f"{BASE}/api/booking/room-reviews/{PID}", timeout=15)
        assert r.status_code == 200
        rooms = r.json().get("rooms") or []
        assert isinstance(rooms, list)
        # At least one room may have count>0 with avg
        for room in rooms:
            if room.get("count", 0) > 0:
                assert isinstance(room.get("avg"), (int, float))


# ---------------- Installments settings ----------------
class TestInstallmentsSettings:
    def test_defaults_present(self):
        r = requests.get(f"{BASE}/api/booking/be-settings/{PID}", timeout=10)
        assert r.status_code == 200
        s = r.json()
        assert s.get("installments_enabled") is True
        assert s.get("installments_count") == 3
        assert s.get("installments_min_amount") == 500
        assert s.get("loyalty_show_points") is True
        assert s.get("loyalty_points_per_unit") == 10

    def test_put_persist_and_restore(self, H):
        r = requests.put(f"{BASE}/api/booking/be-settings/{PID}", headers=H,
                         json={"installments_min_amount": 100}, timeout=10)
        assert r.status_code == 200
        assert r.json()["installments_min_amount"] == 100
        # restore
        r = requests.put(f"{BASE}/api/booking/be-settings/{PID}", headers=H,
                         json={"installments_min_amount": 500}, timeout=10)
        assert r.status_code == 200
        assert r.json()["installments_min_amount"] == 500


# ---------------- Installments e2e ----------------
class TestInstallmentsE2E:
    @pytest.fixture(scope="class")
    def booking_ref(self, H):
        # Find a room ≥£500 for 3 nights. Use king-aldgate-flats (per instructions).
        ci = (datetime.now(timezone.utc) + timedelta(days=45)).date().isoformat()
        co = (datetime.now(timezone.utc) + timedelta(days=48)).date().isoformat()
        # Query rooms
        rs = requests.get(f"{BASE}/api/booking/availability", params={"property_id": PID, "check_in": ci, "check_out": co, "adults": 2}, timeout=15)
        room_id = None
        if rs.status_code == 200:
            for room in rs.json().get("rooms", []):
                if "king" in (room.get("name") or "").lower() or float(room.get("base_price") or 0) * 3 >= 500:
                    room_id = room.get("id")
                    break
        if not room_id:
            pytest.skip("No suitable room found >=£500/3n")
        # Use reserve-multi like BE flow
        payload = {
            "property_id": PID,
            "cart": [{"room_type_id": room_id, "check_in": ci, "check_out": co, "adults": 2, "children": 0, "rate_plan_id": None, "qty": 1}],
            "guest": {"first_name": "TestInst", "last_name": "Guest", "email": f"test-inst-{uuid.uuid4().hex[:6]}@example.com", "phone": "+441234567890"},
            "payment_method": "pay_at_hotel",
            "special_requests": "",
            "lang": "en",
        }
        r = requests.post(f"{BASE}/api/booking/reserve-multi", json=payload, timeout=30)
        if r.status_code != 200:
            pytest.skip(f"reserve-multi failed {r.status_code}: {r.text[:200]}")
        d = r.json()
        ref = d.get("booking_ref") or (d.get("bookings") or [{}])[0].get("booking_ref")
        booking_id = d.get("booking_id") or (d.get("bookings") or [{}])[0].get("id")
        total = d.get("total") or d.get("cart_total") or 0
        return {"ref": ref, "id": booking_id, "email": payload["guest"]["email"], "total": total, "check_in": ci}

    def test_intent_installments(self, booking_ref):
        if not booking_ref.get("id"):
            pytest.skip("No booking id from reserve-multi")
        total = float(booking_ref["total"] or 0)
        if total < 500:
            pytest.skip(f"Total {total} < 500; installments won't apply")
        r = requests.post(f"{BASE}/api/payments/intent",
                          json={"booking_id": booking_ref["id"], "amount_mode": "installments"}, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("client_secret")
        # First installment ≈ total/3
        expected = round(total / 3, 2)
        assert abs(float(d["amount"]) - expected) < 0.5, f"amount {d['amount']} vs expected {expected}"
