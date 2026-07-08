"""Iter 379 regression tests: POST /api/bookings, /api/pos/public/menu, /api/admin/diagnostics/tasks."""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://review-hub-108.preview.emergentagent.com").rstrip("/")


@pytest.fixture(scope="module")
def token():
    last = None
    for _ in range(3):
        r = requests.post(f"{BASE_URL}/api/auth/login",
                          json={"email": "admin@hotelbox.com", "password": "HotelAdmin2026!"},
                          timeout=30)
        last = r
        if r.status_code == 200:
            return r.json().get("token")
        time.sleep(2)
    pytest.skip(f"Login failed: {last.status_code} {last.text[:200] if last else 'n/a'}")


@pytest.fixture(scope="module")
def hdr(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# --- POST /api/bookings (manual staff booking creation) ---
class TestBookingsPost:
    def test_create_booking_success(self, hdr):
        payload = {
            "property_id": "default",
            "guest_name": "TEST_Iter379",
            "guest_email": "test_iter379@example.com",
            "check_in": "2026-12-01",
            "check_out": "2026-12-03",
            "rate": 100,
        }
        r = requests.post(f"{BASE_URL}/api/bookings", json=payload, headers=hdr, timeout=30)
        assert r.status_code in (200, 201), f"{r.status_code} {r.text[:400]}"
        data = r.json()
        assert "id" in data, data
        assert data.get("booking_ref", "").startswith("BK-"), data
        assert data.get("nights") == 2, data
        assert float(data.get("total_price", 0)) == 200.0, data
        assert data.get("status") in ("confirmed", "pending", "reserved"), data
        pytest.booking_id = data["id"]

    def test_create_booking_missing_fields(self, hdr):
        r = requests.post(f"{BASE_URL}/api/bookings", json={"property_id": "default"}, headers=hdr, timeout=30)
        assert r.status_code in (400, 422), f"Expected 400/422 got {r.status_code}"

    def test_create_booking_invalid_dates(self, hdr):
        payload = {
            "property_id": "default",
            "guest_name": "TEST_bad_dates",
            "guest_email": "bad@example.com",
            "check_in": "2026-12-05",
            "check_out": "2026-12-03",
            "rate": 100,
        }
        r = requests.post(f"{BASE_URL}/api/bookings", json=payload, headers=hdr, timeout=30)
        assert r.status_code == 400, f"Expected 400 got {r.status_code}: {r.text[:200]}"

    def test_lifecycle_checkin_charge_checkout(self, hdr):
        bid = getattr(pytest, "booking_id", None)
        if not bid:
            pytest.skip("No booking id from create test")
        # check in (status as query param)
        r = requests.put(f"{BASE_URL}/api/bookings/{bid}/status", params={"status": "checked_in"}, headers=hdr, timeout=30)
        assert r.status_code == 200, f"checkin: {r.status_code} {r.text[:200]}"
        # add charge
        r2 = requests.post(f"{BASE_URL}/api/folio/{bid}/add-charge",
                           json={"description": "Minibar", "amount": 15, "category": "misc"},
                           headers=hdr, timeout=30)
        assert r2.status_code == 200, f"charge: {r2.status_code} {r2.text[:200]}"
        # check out
        r3 = requests.put(f"{BASE_URL}/api/bookings/{bid}/status", params={"status": "checked_out"}, headers=hdr, timeout=30)
        assert r3.status_code == 200, f"checkout: {r3.status_code} {r3.text[:200]}"


# --- Public QR menu (no auth) ---
class TestPublicMenu:
    def test_public_menu_success(self):
        url = f"{BASE_URL}/api/pos/public/menu/aldgate-flats/7eb31a3a-413d-4ede-9804-40a5c0e175d1?table=1"
        r = requests.get(url, timeout=30)
        assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
        data = r.json()
        # Should have menu items or categories
        assert isinstance(data, dict), data
        # Common shapes
        has_items = "items" in data or "menu" in data or "categories" in data or "outlet" in data
        assert has_items, f"Unexpected menu shape: {list(data.keys())}"

    def test_public_menu_invalid_outlet(self):
        url = f"{BASE_URL}/api/pos/public/menu/default/fake-outlet-does-not-exist"
        r = requests.get(url, timeout=30)
        assert r.status_code == 404, f"Expected 404, got {r.status_code}: {r.text[:200]}"


# --- Admin diagnostics tasks ---
class TestAdminDiagnostics:
    def test_diagnostics_tasks(self, hdr):
        r = requests.get(f"{BASE_URL}/api/admin/diagnostics/tasks", headers=hdr, timeout=30)
        assert r.status_code == 200, f"{r.status_code} {r.text[:200]}"
        data = r.json()
        assert "total_tasks" in data or "tasks" in data, data
