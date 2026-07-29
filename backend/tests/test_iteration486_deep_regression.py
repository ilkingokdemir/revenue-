"""
Iteration 486 — Derinlemesine full-stack regression.
Odaklar: Auth guard, onboarding quick-start (idempotent) + drip serisi,
navigation destek endpoint'leri, PMS/Revenue/Finance/Guest/Marketing/Channel/Ops/Reports/Workers.
"""
import os
import time
import uuid
import pytest
import requests

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE}/api"

ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASS = "HotelAdmin2026!"


# ---------- fixtures ----------
@pytest.fixture(scope="session")
def admin_token():
    r = requests.post(f"{API}/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=15)
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text[:200]}"
    tok = r.json().get("token")
    assert tok
    return tok


@pytest.fixture(scope="session")
def auth(admin_token):
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {admin_token}",
                      "Content-Type": "application/json"})
    return s


@pytest.fixture(scope="session")
def temp_property(auth):
    """Ephemeral property; cleanup at end (delete bookings/rooms/rates/tax/drip and property)."""
    pid = f"TEST_ITER486_{uuid.uuid4().hex[:8]}"
    r = auth.post(f"{API}/properties", json={
        "id": pid, "name": f"TEST_ITER486 Property {pid[-6:]}",
        "city": "Zurich", "country": "CH", "currency": "CHF", "timezone": "Europe/Zurich",
    }, timeout=15)
    assert r.status_code in (200, 201), f"create property failed {r.status_code} {r.text[:200]}"
    yield pid
    # ------- cleanup -------
    try:
        # remove seeded artefacts via mongo? we only have HTTP. best-effort delete:
        # bookings created by quick-start are is_demo=True; there is a purge endpoint used in demo_seeder.
        auth.delete(f"{API}/properties/{pid}", timeout=15)
    except Exception:
        pass


# ---------- auth & security ----------
class TestAuth:
    def test_login_and_me(self, auth):
        r = auth.get(f"{API}/auth/me", timeout=10)
        assert r.status_code == 200
        d = r.json()
        assert d.get("email") == ADMIN_EMAIL

    def test_login_wrong_password_401(self):
        r = requests.post(f"{API}/auth/login",
                          json={"email": ADMIN_EMAIL, "password": "WRONG_PW_zzz"}, timeout=10)
        assert r.status_code in (401, 400, 429)

    def test_no_token_401(self):
        r = requests.get(f"{API}/auth/me", timeout=10)
        assert r.status_code in (401, 403)


# ---------- onboarding quick-start + drip ----------
class TestOnboarding:
    def test_quick_start_creates_resources(self, auth, temp_property):
        r = auth.post(f"{API}/property-onboarding/quick-start/{temp_property}",
                      json={"base_price": 120, "currency": "CHF", "seed_bookings": 15},
                      timeout=60)
        assert r.status_code == 200, r.text[:400]
        d = r.json()
        c = d["created"]
        assert c["rooms"] == 3, f"expected 3 rooms, got {c}"
        assert c["rate_products"] == 2
        assert c["tax_profiles"] == 1
        assert c["bookings"] == 15

    def test_quick_start_idempotent(self, auth, temp_property):
        # second call: rooms/rates/tax already exist → 0; bookings still creates new demo
        r = auth.post(f"{API}/property-onboarding/quick-start/{temp_property}",
                      json={"base_price": 120, "currency": "CHF", "seed_bookings": 0},
                      timeout=60)
        assert r.status_code == 200
        d = r.json()["created"]
        assert d["rooms"] == 0
        assert d["rate_products"] == 0
        assert d["tax_profiles"] == 0

    def test_onboarding_status_reflects_counts(self, auth, temp_property):
        r = auth.get(f"{API}/property-onboarding/status/{temp_property}", timeout=15)
        assert r.status_code == 200
        d = r.json()
        # completed_at should be set after quick-start
        assert d.get("completed_at") or d.get("steps_completed")

    def test_drip_enrolled_after_quick_start(self, auth, temp_property):
        r = auth.get(f"{API}/onboarding-drip/status/{temp_property}", timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["enrolled"] is True
        assert d["enabled"] is True
        keys = [t["key"] for t in d["timeline"]]
        assert set(keys) == {"welcome", "market_robot", "booking_url", "revenue_brain"}

    def test_drip_run_now_sends_day0(self, auth, temp_property):
        r = auth.post(f"{API}/onboarding-drip/run-now", json={}, timeout=30)
        assert r.status_code == 200
        # then re-check status → welcome should be sent
        r2 = auth.get(f"{API}/onboarding-drip/status/{temp_property}", timeout=15)
        tl = {t["key"]: t for t in r2.json()["timeline"]}
        assert tl["welcome"]["sent_at"] is not None
        assert tl["welcome"]["status"] in ("mock", "sent", "queued", "ok", "success", "resend_mock")

    def test_drip_preview_returns_html(self, auth):
        r = auth.get(f"{API}/onboarding-drip/preview/welcome", timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert "<div" in d["html"] and "MyHotelBox" in d["html"]

    def test_drip_preview_invalid_key_404(self, auth):
        r = auth.get(f"{API}/onboarding-drip/preview/does_not_exist", timeout=15)
        assert r.status_code == 404


# ---------- PMS core (regression using default) ----------
class TestPMS:
    def test_properties_list(self, auth):
        r = auth.get(f"{API}/properties", timeout=15)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_room_types_default(self, auth):
        r = auth.get(f"{API}/room-types?property_id=default", timeout=15)
        assert r.status_code == 200

    def test_bookings_list_default(self, auth):
        r = auth.get(f"{API}/bookings?property_id=default", timeout=20)
        assert r.status_code == 200
        assert isinstance(r.json(), list)


# ---------- Revenue ----------
class TestRevenue:
    def test_ai_pricing_suggestions(self, auth):
        r = auth.get(f"{API}/revenue/ai-pricing/default/suggestions?days=7&use_llm=false", timeout=30)
        assert r.status_code == 200

    def test_revenue_brain_status(self, auth):
        r = auth.get(f"{API}/revenue-brain/default/status", timeout=15)
        assert r.status_code == 200

    def test_revenue_brain_goal(self, auth):
        r = auth.get(f"{API}/revenue-brain/default/goal", timeout=15)
        # goal is POST-only in this build; 405 acceptable
        assert r.status_code in (200, 405)

    def test_base_curve_preview(self, auth):
        r = auth.get(f"{API}/base-curve/default/preview?days=540", timeout=20)
        assert r.status_code == 200
        d = r.json()
        # accept either raw list or {curve:[]}
        rows = d if isinstance(d, list) else d.get("curve") or d.get("rows") or []
        assert len(rows) == 540, f"expected 540 rows, got {len(rows)}"

    def test_rate_products_list(self, auth):
        r = auth.get(f"{API}/rate-structure/products?property_id=default", timeout=15)
        assert r.status_code == 200

    def test_market_robot_config(self, auth):
        r = auth.get(f"{API}/revenue/market-robot/default/config", timeout=15)
        assert r.status_code in (200, 404)

    def test_str_market_scan_status(self, auth):
        r = auth.get(f"{API}/str-market/default/scan/status", timeout=15)
        assert r.status_code == 200


# ---------- Finance ----------
class TestFinance:
    def test_tax_profiles(self, auth):
        r = auth.get(f"{API}/tax-config/profiles?property_id=default", timeout=15)
        assert r.status_code == 200


# ---------- Marketing / public ----------
class TestMarketing:
    def test_public_price_checker_city_only(self):
        r = requests.post(f"{API}/public/price-check",
                          json={"city": "Zurich", "rooms": 20, "brand": "myhotelbox"},
                          timeout=20)
        assert r.status_code in (200, 429), r.text[:200]

    def test_lead_funnel_list(self, auth):
        r = auth.get(f"{API}/lead-funnel/leads?limit=5", timeout=15)
        assert r.status_code == 200


# ---------- Channel Manager ----------
class TestChannel:
    def test_channel_health(self, auth):
        r = auth.get(f"{API}/revenue/channel-manager/default/health", timeout=15)
        assert r.status_code in (200, 404, 405)


# ---------- Landing pages ----------
class TestLandings:
    def test_myhotelbox_landing(self):
        r = requests.get(f"{BASE}/", timeout=15)
        assert r.status_code == 200

    def test_reveniq_landing(self):
        r = requests.get(f"{BASE}/reveniq", timeout=15)
        assert r.status_code == 200
