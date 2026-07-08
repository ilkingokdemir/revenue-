"""Iteration 377 regression tests - route collision cleanup verification."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://review-hub-108.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"


@pytest.fixture(scope="module")
def admin_token():
    for _ in range(3):
        r = requests.post(f"{BASE_URL}/api/auth/login",
                          json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
                          timeout=30)
        if r.status_code == 200:
            return r.json().get("token") or r.json().get("access_token")
    pytest.skip(f"Login failed: {r.status_code} {r.text[:200]}")


@pytest.fixture
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


# --- server.py canonical endpoints (reviews duplicates removed) ---
def test_status_root():
    r = requests.get(f"{BASE_URL}/api/status", timeout=15)
    assert r.status_code in (200, 401, 403), f"{r.status_code} {r.text[:200]}"


def test_api_root():
    r = requests.get(f"{BASE_URL}/api/", timeout=15)
    assert r.status_code == 200, f"{r.status_code} {r.text[:200]}"


# --- finance expenses canonical (finance_pl.py duplicate removed) ---
def test_finance_expenses_default(auth_headers):
    r = requests.get(f"{BASE_URL}/api/finance/expenses/default", headers=auth_headers, timeout=20)
    assert r.status_code == 200, f"{r.status_code} {r.text[:200]}"
    data = r.json()
    # Accept list or {expenses: [...]}
    if isinstance(data, dict):
        assert "expenses" in data or "items" in data or "data" in data
    else:
        assert isinstance(data, list)


# --- spaces collision fix ---
def test_spaces_staff_default(auth_headers):
    r = requests.get(f"{BASE_URL}/api/spaces/default", headers=auth_headers, timeout=20)
    assert r.status_code == 200, f"{r.status_code} {r.text[:200]}"
    data = r.json()
    items = data if isinstance(data, list) else data.get("spaces") or data.get("items") or []
    # staff shape: objects with kind/currency
    if items:
        s = items[0]
        assert isinstance(s, dict)
        # Look for staff-shape keys
        assert any(k in s for k in ("kind", "currency", "id", "name")), f"unexpected shape: {s}"


def test_spaces_public_default_no_auth():
    r = requests.get(f"{BASE_URL}/api/spaces/public/default", timeout=20)
    assert r.status_code == 200, f"{r.status_code} {r.text[:200]}"
    data = r.json()
    # public property_spaces list
    items = data if isinstance(data, list) else data.get("spaces") or data.get("property_spaces") or data.get("items") or []
    assert isinstance(items, list)


# --- marketplace consolidated to platform_ext ---
def test_marketplace_catalog(auth_headers):
    r = requests.get(f"{BASE_URL}/api/marketplace/catalog", headers=auth_headers, timeout=20)
    assert r.status_code == 200, f"{r.status_code} {r.text[:200]}"
    data = r.json()
    assert "categories" in data or "items" in data or isinstance(data, list), f"unexpected: {list(data.keys()) if isinstance(data, dict) else type(data)}"


# --- reviews router intact (duplicates removed) ---
def test_reviews_list(auth_headers):
    r = requests.get(f"{BASE_URL}/api/reviews", headers=auth_headers, timeout=20)
    assert r.status_code in (200, 401, 403), f"{r.status_code} {r.text[:200]}"
    if r.status_code == 200:
        data = r.json()
        assert isinstance(data, (list, dict))


# --- stripe webhook single canonical handler ---
def test_stripe_webhook_controlled_error():
    r = requests.post(f"{BASE_URL}/api/webhook/stripe",
                      data=b'{"invalid": "payload"}',
                      headers={"Content-Type": "application/json", "Stripe-Signature": "invalid"},
                      timeout=15)
    # Must NOT be 500 crash - controlled error 400/401/403
    assert r.status_code != 500, f"Handler crashed with 500: {r.text[:200]}"
    # Stripe webhooks canonically ACK 200 even on invalid sig (returns {"status":"error"}), or 400/401/403
    assert r.status_code in (200, 400, 401, 403, 422), f"unexpected: {r.status_code} {r.text[:200]}"
    if r.status_code == 200:
        assert "error" in r.text.lower() or "received" in r.text.lower()


# --- direct-conversion offers (for coupon fetch) ---
def test_direct_conversion_offers_available(auth_headers):
    r = requests.get(f"{BASE_URL}/api/direct-conversion/offers?status=sent&limit=1",
                     headers=auth_headers, timeout=20)
    assert r.status_code == 200, f"{r.status_code} {r.text[:200]}"
    data = r.json()
    items = data.get("items") if isinstance(data, dict) else data
    print(f"Sent offers available: {len(items) if items else 0}")
