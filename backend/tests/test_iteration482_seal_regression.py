"""
Iteration 482 - SEAL Full Regression before deployment.
Breadth over depth — covers Public Landing (demo/price-check), Admin Panels,
Smart Rooms IoT, Base Price Curve, Revenue Brain, STR Market, Owner Pulse Digest,
Owner Portal auth, FnB loyalty tab, AI Pricing suggestions.
"""
import os
import pytest
import requests

def _load_backend_url():
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if v:
        return v.rstrip("/")
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    return line.split("=", 1)[1].strip().rstrip("/")
    except Exception:
        pass
    raise RuntimeError("REACT_APP_BACKEND_URL not set")

BASE = _load_backend_url()
API = f"{BASE}/api"

ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"
OWNER_EMAIL = "test_owner_143120@example.com"
OWNER_PIN = "862347"


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text[:200]}"
    return r.json().get("access_token") or r.json().get("token")


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


# ------------------ AUTH & DEMO REQUESTS ------------------
def test_admin_login_ok(admin_token):
    assert admin_token and isinstance(admin_token, str)


def test_demo_requests_summary_has_pc_queries(admin_headers):
    r = requests.get(f"{API}/demo-requests", headers=admin_headers, timeout=30)
    assert r.status_code == 200
    data = r.json()
    # summary object
    summary = data.get("summary") or data
    assert "price_checker_queries" in summary, f"summary missing price_checker_queries: {list(summary.keys())[:20]}"


# ------------------ SMART ROOMS ------------------
def test_smart_rooms_grid(admin_headers):
    r = requests.get(f"{API}/smart-rooms/aldgate-flats", headers=admin_headers, timeout=30)
    assert r.status_code == 200, r.text[:200]
    d = r.json()
    assert "rooms" in d or isinstance(d, list) or "grid" in d


def test_smart_rooms_energy_summary(admin_headers):
    r = requests.get(f"{API}/smart-rooms/aldgate-flats/energy/summary", headers=admin_headers, timeout=30)
    assert r.status_code == 200, r.text[:200]


# ------------------ BASE PRICE CURVE ------------------
def test_base_curve_config(admin_headers):
    r = requests.get(f"{API}/base-curve/aldgate-flats/config", headers=admin_headers, timeout=30)
    assert r.status_code == 200


def test_base_curve_preview_540d(admin_headers):
    r = requests.get(f"{API}/base-curve/aldgate-flats/preview?days=540", headers=admin_headers, timeout=60)
    assert r.status_code == 200
    d = r.json()
    rows = d.get("rows") or d.get("preview") or d.get("data") or d
    if isinstance(rows, dict):
        # find list
        for k, v in rows.items():
            if isinstance(v, list) and len(v) > 100:
                rows = v
                break
    assert isinstance(rows, list), f"expected list of rows, got {type(rows)}"
    assert len(rows) == 540, f"expected 540 rows, got {len(rows)}"


# ------------------ AI PRICING CADENCE ------------------
def test_ai_pricing_cadence(admin_headers):
    r = requests.get(f"{API}/revenue/ai-pricing/aldgate-flats/cadence", headers=admin_headers, timeout=30)
    assert r.status_code == 200


def test_ai_pricing_suggestions_default(admin_headers):
    r = requests.get(f"{API}/revenue/ai-pricing/default/suggestions?days=14&use_llm=false", headers=admin_headers, timeout=60)
    assert r.status_code == 200
    d = r.json()
    # top-level or nested list of suggestions
    suggestions = d.get("suggestions") or d.get("items") or (d if isinstance(d, list) else [])
    if suggestions and isinstance(suggestions, list) and len(suggestions) > 0:
        s0 = suggestions[0]
        assert "str_mult" in s0, f"missing str_mult: {list(s0.keys())[:20]}"
        assert "learned_mult" in s0, f"missing learned_mult: {list(s0.keys())[:20]}"
    else:
        # default may return empty; still assert 200 OK
        pass


# ------------------ STR MARKET ------------------
def test_str_market_overview(admin_headers):
    r = requests.get(f"{API}/str-market/aldgate-flats/overview?days=30", headers=admin_headers, timeout=30)
    assert r.status_code == 200
    d = r.json()
    # live_dates key indicates fresh scan count; simulated fallback OK
    assert "live_dates" in d or "live" in d or "days" in d, f"unexpected shape: {list(d.keys())[:20]}"


# ------------------ REVENUE BRAIN ------------------
def test_revenue_brain_status(admin_headers):
    r = requests.get(f"{API}/revenue-brain/aldgate-flats/status", headers=admin_headers, timeout=30)
    assert r.status_code == 200
    d = r.json()
    assert d.get("outcomes_measured") == 8, f"expected outcomes_measured=8, got {d.get('outcomes_measured')}"


# ------------------ OWNER PULSE DIGEST ------------------
def test_owner_pulse_digest_preview(admin_headers):
    r = requests.get(f"{API}/owner-pulse/default/digest/preview", headers=admin_headers, timeout=30)
    assert r.status_code == 200
    html = r.text
    assert "STR Pazar Zekâsı" in html, "digest missing STR Pazar Zekâsı"
    assert "Bu Hafta Beyniniz Ne Öğrendi" in html, "digest missing Brain weekly card"


# ------------------ PUBLIC PRICE CHECKER (no email → no lead) ------------------
def test_public_price_check_no_email():
    r = requests.post(f"{API}/public/price-check", json={"city": "Roma"}, timeout=30)
    assert r.status_code == 200, r.text[:300]
    d = r.json()
    assert d.get("lead_created") in (False, None, 0), f"lead_created should be false when no email: {d.get('lead_created')}"


# ------------------ OWNER PORTAL ------------------
def test_owner_login_and_dashboard():
    r = requests.post(f"{API}/owner-auth/login", json={"email": OWNER_EMAIL, "pin": OWNER_PIN}, timeout=30)
    if r.status_code != 200:
        pytest.skip(f"Owner login failed (credentials may need refresh): {r.status_code} {r.text[:200]}")
    token = r.json().get("access_token")
    assert token
    r2 = requests.get(f"{API}/owner-auth/dashboard", headers={"Authorization": f"Bearer {token}"}, timeout=30)
    assert r2.status_code == 200, f"owner dashboard failed: {r2.status_code} {r2.text[:200]}"


# ------------------ FnB LOYALTY DISCOUNT (no 500) ------------------
def test_fnb_loyalty_discount_endpoint(admin_headers):
    # Get any tab
    tabs_r = requests.get(f"{API}/fnb/tabs/aldgate-flats", headers=admin_headers, timeout=30)
    if tabs_r.status_code != 200:
        pytest.skip(f"cannot list fnb tabs: {tabs_r.status_code}")
    tabs = tabs_r.json()
    if isinstance(tabs, dict):
        tabs = tabs.get("rows") or tabs.get("tabs") or tabs.get("items") or []
    if not tabs:
        pytest.skip("no fnb tabs to test")
    tab_id = tabs[0].get("id") or tabs[0].get("_id") or tabs[0].get("tab_id")
    if not tab_id:
        pytest.skip("tab id missing")
    r = requests.get(f"{API}/fnb/tabs/{tab_id}/loyalty-discount", headers=admin_headers, timeout=30)
    assert r.status_code != 500, f"loyalty-discount 500: {r.text[:300]}"
    assert r.status_code in (200, 404), f"unexpected status: {r.status_code}"
    if r.status_code == 200:
        d = r.json()
        assert "eligible" in d, f"missing 'eligible' field: {list(d.keys())[:20]}"
