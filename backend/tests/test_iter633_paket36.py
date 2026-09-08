"""Iter633: Public API v1 (keys/scopes/rate-limits/idempotency/CRUD) + Opera Cloud connector."""
import os
import time
import uuid
import pytest
import requests
from datetime import date, timedelta

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://review-hub-108.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASS = "HotelAdmin2026!"
PID = "aldgate-flats"

CI = (date.today() + timedelta(days=45)).isoformat()
CO = (date.today() + timedelta(days=47)).isoformat()


@pytest.fixture(scope="module")
def admin_headers():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=15)
    assert r.status_code == 200, r.text
    t = r.json().get("token") or r.json().get("access_token")
    return {"Authorization": f"Bearer {t}"}


@pytest.fixture(scope="module")
def read_key(admin_headers):
    r = requests.post(f"{API}/public-keys/{PID}", headers=admin_headers,
                      json={"name": "TEST_read_key", "rate_per_min": 50, "scopes": ["read:availability"]}, timeout=15)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["key"].startswith("hbx_")
    assert d["scopes"] == ["read:availability"]
    assert d["rate_per_min"] == 50
    return d


@pytest.fixture(scope="module")
def write_key(admin_headers):
    r = requests.post(f"{API}/public-keys/{PID}", headers=admin_headers,
                      json={"name": "TEST_write_key", "rate_per_min": 120}, timeout=15)
    assert r.status_code == 200, r.text
    d = r.json()
    assert "write:bookings" in d["scopes"]
    return d


class TestKeyMgmt:
    def test_docs_no_auth(self):
        r = requests.get(f"{API}/public/v1/docs", timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert len(d["endpoints"]) == 8
        assert d.get("curl_examples") and len(d["curl_examples"]) >= 4
        assert any("https://" in c["cmd"] for c in d["curl_examples"])

    def test_list_keys(self, admin_headers, read_key):
        r = requests.get(f"{API}/public-keys/{PID}", headers=admin_headers, timeout=15)
        assert r.status_code == 200
        keys = r.json()["keys"]
        assert any(k["id"] == read_key["id"] for k in keys)

    def test_key_usage(self, admin_headers, read_key):
        # trigger a call
        requests.get(f"{API}/public/v1/rate-plans", headers={"X-API-Key": read_key["key"]}, timeout=15)
        r = requests.get(f"{API}/public-keys/{PID}/usage", headers=admin_headers, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert "calls" in d and "by_key" in d


class TestAvailabilityAndScopes:
    def test_availability_headers(self, read_key):
        r = requests.get(f"{API}/public/v1/availability",
                         params={"check_in": CI, "check_out": CO, "adults": 2},
                         headers={"X-API-Key": read_key["key"]}, timeout=15)
        assert r.status_code == 200, r.text
        assert r.headers.get("X-RateLimit-Limit") == "50"
        assert r.headers.get("X-RateLimit-Remaining") is not None
        assert r.headers.get("X-RateLimit-Reset") is not None
        d = r.json()
        assert isinstance(d["rooms"], list) and len(d["rooms"]) > 0
        r0 = d["rooms"][0]
        for k in ("rooms_left", "available", "stay_total", "room_type_id"):
            assert k in r0
        pytest.available_rt = next((x["room_type_id"] for x in d["rooms"] if x.get("available")), d["rooms"][0]["room_type_id"])

    def test_no_key_401(self):
        r = requests.get(f"{API}/public/v1/availability",
                         params={"check_in": CI, "check_out": CO}, timeout=15)
        assert r.status_code == 401

    def test_read_key_cannot_write(self, read_key):
        r = requests.post(f"{API}/public/v1/bookings", headers={"X-API-Key": read_key["key"]},
                          json={"room_type_id": "x", "guest_name": "x", "guest_email": "a@b.com",
                                "check_in": CI, "check_out": CO, "adults": 1}, timeout=15)
        assert r.status_code == 403


class TestBookingsCRUD:
    def test_create_booking_201(self, write_key):
        rt = getattr(pytest, "available_rt", None)
        assert rt, "no available room type"
        idem = f"idem-{uuid.uuid4()}"
        ext = f"OTA-{uuid.uuid4().hex[:8]}"
        pytest.idem = idem
        pytest.ext = ext
        r = requests.post(f"{API}/public/v1/bookings",
                          headers={"X-API-Key": write_key["key"], "Idempotency-Key": idem},
                          json={"room_type_id": rt, "guest_name": "Ada Lovelace",
                                "guest_email": "ada@example.com", "check_in": CI, "check_out": CO,
                                "adults": 2, "external_ref": ext}, timeout=20)
        assert r.status_code == 201, r.text
        d = r.json()
        assert d["booking_ref"].startswith("MHB-")
        assert d["source"] == "public_api"
        pytest.booking_ref = d["booking_ref"]

    def test_idempotent_replay(self, write_key):
        rt = pytest.available_rt
        r = requests.post(f"{API}/public/v1/bookings",
                          headers={"X-API-Key": write_key["key"], "Idempotency-Key": pytest.idem},
                          json={"room_type_id": rt, "guest_name": "Ada Lovelace",
                                "guest_email": "ada@example.com", "check_in": CI, "check_out": CO,
                                "adults": 2, "external_ref": pytest.ext}, timeout=15)
        # Should not duplicate — either 200 or 201 with same ref
        assert r.status_code in (200, 201)
        assert r.json()["booking_ref"] == pytest.booking_ref

    def test_invalid_room_type(self, write_key):
        r = requests.post(f"{API}/public/v1/bookings", headers={"X-API-Key": write_key["key"]},
                          json={"room_type_id": "does-not-exist", "guest_name": "X",
                                "guest_email": "x@y.com", "check_in": CI, "check_out": CO, "adults": 1}, timeout=15)
        assert r.status_code == 422

    def test_missing_email(self, write_key):
        rt = pytest.available_rt
        r = requests.post(f"{API}/public/v1/bookings", headers={"X-API-Key": write_key["key"]},
                          json={"room_type_id": rt, "guest_name": "X", "check_in": CI, "check_out": CO, "adults": 1}, timeout=15)
        assert r.status_code == 422

    def test_bad_dates(self, write_key):
        rt = pytest.available_rt
        r = requests.post(f"{API}/public/v1/bookings", headers={"X-API-Key": write_key["key"]},
                          json={"room_type_id": rt, "guest_name": "X", "guest_email": "a@b.com",
                                "check_in": CO, "check_out": CI, "adults": 1}, timeout=15)
        assert r.status_code == 422

    def test_over_capacity_409(self, write_key):
        rt = pytest.available_rt
        r = requests.post(f"{API}/public/v1/bookings", headers={"X-API-Key": write_key["key"]},
                          json={"room_type_id": rt, "guest_name": "X", "guest_email": "a@b.com",
                                "check_in": CI, "check_out": CO, "adults": 1, "rooms": 999}, timeout=15)
        assert r.status_code == 409

    def test_get_by_ref(self, write_key):
        r = requests.get(f"{API}/public/v1/bookings/{pytest.booking_ref}",
                         headers={"X-API-Key": write_key["key"]}, timeout=15)
        assert r.status_code == 200
        assert r.json()["booking_ref"] == pytest.booking_ref

    def test_get_by_external_ref(self, write_key):
        r = requests.get(f"{API}/public/v1/bookings/{pytest.ext}",
                         headers={"X-API-Key": write_key["key"]}, timeout=15)
        assert r.status_code == 200

    def test_cancel_and_idempotent(self, write_key):
        r = requests.post(f"{API}/public/v1/bookings/{pytest.booking_ref}/cancel",
                          headers={"X-API-Key": write_key["key"]}, json={"reason": "test"}, timeout=15)
        assert r.status_code == 200
        assert r.json()["status"] == "cancelled"
        # second cancel idempotent
        r2 = requests.post(f"{API}/public/v1/bookings/{pytest.booking_ref}/cancel",
                           headers={"X-API-Key": write_key["key"]}, timeout=15)
        assert r2.status_code == 200
        assert r2.json()["status"] == "cancelled"

    def test_list_cancelled(self, write_key):
        r = requests.get(f"{API}/public/v1/bookings?status=cancelled",
                         headers={"X-API-Key": write_key["key"]}, timeout=15)
        assert r.status_code == 200
        refs = [b["booking_ref"] for b in r.json()["bookings"]]
        assert pytest.booking_ref in refs


class TestRateLimit:
    def test_rate_limit_429(self, admin_headers):
        r = requests.post(f"{API}/public-keys/{PID}", headers=admin_headers,
                          json={"name": "TEST_rl_key", "rate_per_min": 10,
                                "scopes": ["read:availability"]}, timeout=15)
        assert r.status_code == 200
        key = r.json()["key"]
        last = None
        for _ in range(11):
            last = requests.get(f"{API}/public/v1/rate-plans",
                                headers={"X-API-Key": key}, timeout=15)
        assert last.status_code == 429, f"expected 429, got {last.status_code}"
        assert last.headers.get("Retry-After") is not None
        assert last.headers.get("X-RateLimit-Remaining") == "0"


class TestKeyUpdate:
    def test_deactivate_key(self, admin_headers, read_key):
        r = requests.put(f"{API}/public-keys/{PID}/{read_key['id']}",
                         headers=admin_headers, json={"active": False}, timeout=15)
        assert r.status_code == 200
        r2 = requests.get(f"{API}/public/v1/rate-plans",
                          headers={"X-API-Key": read_key["key"]}, timeout=15)
        assert r2.status_code == 401


# ================= Opera Cloud connector =================
class TestOperaCloud:
    def test_providers_includes_opera(self, admin_headers):
        r = requests.get(f"{API}/pms-connect/providers/{PID}", headers=admin_headers, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        provs = d.get("providers") if isinstance(d, dict) and "providers" in d else d
        opera = next((p for p in provs if p.get("id") == "opera-cloud"), None)
        assert opera is not None
        assert len(opera.get("auth_fields", [])) == 8
        assert opera.get("mode") == "mocked"

    def test_save_partial_config(self, admin_headers):
        r = requests.post(f"{API}/pms-connect/opera-cloud/config/{PID}",
                          headers=admin_headers, json={"host": "x"}, timeout=15)
        assert r.status_code == 200
        assert r.json().get("mode") == "mocked"

    def test_test_connection_missing_creds(self, admin_headers):
        # Save empty first
        requests.post(f"{API}/pms-connect/opera-cloud/config/{PID}",
                      headers=admin_headers, json={}, timeout=15)
        r = requests.post(f"{API}/pms-connect/opera-cloud/test-connection/{PID}",
                          headers=admin_headers, json={}, timeout=15)
        assert r.status_code == 400, r.text

    def test_push_preview(self, admin_headers):
        r = requests.get(f"{API}/pms-connect/opera-cloud/push-preview/{PID}",
                         headers=admin_headers, timeout=15)
        assert r.status_code == 200

    def test_catalog_opera(self, admin_headers):
        r = requests.get(f"{API}/connector-catalog/{PID}", headers=admin_headers, timeout=15)
        assert r.status_code == 200, r.text
        items = r.json().get("connectors") or r.json().get("items") or r.json()
        if isinstance(items, dict):
            items = items.get("items", [])
        opera = next((c for c in items if c.get("id") == "opera-cloud" or c.get("key") == "opera-cloud"), None)
        assert opera is not None
        assert opera.get("panel") == "pms-connect"
        assert opera.get("status") in ("ready", "connected")
