"""Iter 383 — full-system audit (per E1 review request).
Covers: auth, dashboard, bookings, housekeeping (new predictive), revenue
(new hurdle-LRV, LRV guardrail in AI pricing, segment forecast), guests/CRM,
finance, channel manager, marketing, public pages, admin/settings, and a
broad smoke of critical endpoints for 500-error hunting.
"""
import os
import pytest
import requests
from datetime import datetime, timedelta, timezone

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://review-hub-108.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASS = "HotelAdmin2026!"


@pytest.fixture(scope="session")
def token():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=15)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    j = r.json()
    tok = j.get("token") or j.get("access_token")
    assert tok, f"no token in response: {j}"
    return tok


@pytest.fixture(scope="session")
def hdr(token):
    return {"Authorization": f"Bearer {token}"}


# --------------- AUTH ---------------
class TestAuth:
    def test_login_bad_password(self):
        r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": "wrong"}, timeout=15)
        assert r.status_code in (400, 401, 403), r.status_code

    def test_protected_requires_auth(self):
        r = requests.get(f"{API}/users", timeout=15)
        assert r.status_code in (401, 403, 422), r.status_code

    def test_me(self, hdr):
        r = requests.get(f"{API}/auth/me", headers=hdr, timeout=15)
        assert r.status_code == 200
        assert r.json().get("email") == ADMIN_EMAIL


# --------------- DASHBOARD / KPIs ---------------
class TestDashboard:
    def test_dashboard(self, hdr):
        r = requests.get(f"{API}/analytics/dashboard", headers=hdr, timeout=20)
        assert r.status_code == 200
        j = r.json()
        assert isinstance(j, dict)

    def test_properties_list(self, hdr):
        r = requests.get(f"{API}/properties", headers=hdr, timeout=15)
        assert r.status_code == 200
        assert isinstance(r.json(), list)


# --------------- BOOKINGS ---------------
class TestBookings:
    def test_list_bookings(self, hdr):
        r = requests.get(f"{API}/bookings", headers=hdr, timeout=20)
        assert r.status_code == 200

    def test_create_booking(self, hdr):
        ci = (datetime.now().date() + timedelta(days=45)).isoformat()
        co = (datetime.now().date() + timedelta(days=48)).isoformat()
        payload = {
            "property_id": "aldgate-flats", "guest_name": "TEST_Iter383",
            "guest_email": "iter383@test.local", "guest_phone": "+441234567890",
            "check_in": ci, "check_out": co, "adults": 2, "children": 0,
            "room_type_id": "", "total_price": 300.0, "source": "direct",
        }
        r = requests.post(f"{API}/bookings", headers=hdr, json=payload, timeout=20)
        assert r.status_code in (200, 201), f"{r.status_code}: {r.text[:200]}"


# --------------- PREDICTIVE HK (NEW) ---------------
class TestPredictiveHK:
    def test_forecast(self, hdr):
        r = requests.get(f"{API}/housekeeping/predictive/aldgate-flats?days=7", headers=hdr, timeout=20)
        assert r.status_code == 200, r.text[:200]
        j = r.json()
        assert "forecast" in j and isinstance(j["forecast"], list) and len(j["forecast"]) == 7
        assert "housekeeper_count" in j
        for day in j["forecast"]:
            assert {"date", "workload_minutes", "staff_needed"}.issubset(day.keys())

    def test_forecast_all_properties(self, hdr):
        r = requests.get(f"{API}/housekeeping/predictive/all?days=7", headers=hdr, timeout=20)
        assert r.status_code == 200

    def test_generate_tasks(self, hdr):
        d = (datetime.now(timezone.utc).date() + timedelta(days=2)).isoformat()
        r = requests.post(f"{API}/housekeeping/predictive/aldgate-flats/generate",
                          headers=hdr, json={"date": d}, timeout=20)
        assert r.status_code == 200, r.text[:200]
        first = r.json()
        # rerun -> should dedupe
        r2 = requests.post(f"{API}/housekeeping/predictive/aldgate-flats/generate",
                           headers=hdr, json={"date": d}, timeout=20)
        assert r2.status_code == 200
        j2 = r2.json()
        # If first created N, second should skip >= N
        assert j2["skipped_duplicates"] >= first["created"], f"dedup failed: {first} -> {j2}"

    def test_generate_bad_date(self, hdr):
        r = requests.post(f"{API}/housekeeping/predictive/aldgate-flats/generate",
                          headers=hdr, json={"date": "not-a-date"}, timeout=15)
        assert r.status_code == 422

    def test_generate_all_rejected(self, hdr):
        d = (datetime.now(timezone.utc).date() + timedelta(days=1)).isoformat()
        r = requests.post(f"{API}/housekeeping/predictive/all/generate",
                          headers=hdr, json={"date": d}, timeout=15)
        assert r.status_code == 400

    def test_suggest_shifts(self, hdr):
        d = (datetime.now(timezone.utc).date() + timedelta(days=2)).isoformat()
        r = requests.post(f"{API}/housekeeping/predictive/aldgate-flats/suggest-shifts",
                          headers=hdr, json={"date": d}, timeout=20)
        assert r.status_code in (200, 400)  # 400 possible if no housekeepers
        if r.status_code == 200:
            j = r.json()
            assert "staff_needed" in j and "created" in j
            # dedupe rerun
            r2 = requests.post(f"{API}/housekeeping/predictive/aldgate-flats/suggest-shifts",
                               headers=hdr, json={"date": d}, timeout=20)
            assert r2.status_code == 200
            j2 = r2.json()
            if j.get("created", 0) > 0:
                assert j2.get("skipped_existing", 0) >= j["created"]


# --------------- HURDLE / LRV (NEW) ---------------
class TestHurdleLRV:
    def test_hurdle_forecast(self, hdr):
        r = requests.get(f"{API}/revenue/hurdle/city-gate?days=14", headers=hdr, timeout=20)
        assert r.status_code == 200, r.text[:200]
        j = r.json()
        assert "days" in j and isinstance(j["days"], list) and len(j["days"]) >= 7
        for day in j["days"][:3]:
            assert {"date", "lrv", "band", "noshow_rate", "occupancy"}.issubset(day.keys())

    def test_save_config(self, hdr):
        payload = {"min_rate": 50.0, "overbooking_cap": 3, "pricing_guardrail": True}
        r = requests.post(f"{API}/revenue/hurdle/city-gate/config", headers=hdr, json=payload, timeout=15)
        assert r.status_code == 200, r.text[:200]
        j = r.json()
        assert j["min_rate"] == 50.0 and j["overbooking_cap"] == 3
        assert j["pricing_guardrail"] is True

    def test_save_config_invalid(self, hdr):
        r = requests.post(f"{API}/revenue/hurdle/city-gate/config",
                          headers=hdr, json={"overbooking_cap": 999}, timeout=15)
        assert r.status_code == 422


# --------------- AI PRICING LRV GUARDRAIL ---------------
class TestAIPricingGuardrail:
    def test_lrv_guardrail_clamp(self, hdr):
        # First ensure guardrail enabled + min_rate baseline
        requests.post(f"{API}/revenue/hurdle/city-gate/config", headers=hdr,
                      json={"min_rate": 0, "overbooking_cap": 3, "pricing_guardrail": True}, timeout=15)
        # Get LRV floor for a future date
        r = requests.get(f"{API}/revenue/hurdle/city-gate?days=14", headers=hdr, timeout=20)
        assert r.status_code == 200
        days = r.json()["days"]
        # pick a day with lrv > 30 (our suggested_rate=30)
        target = next((d for d in days if d["lrv"] > 30), days[0])
        payload = {"items": [{
            "date": target["date"],
            "room_type_id": "double-city-gate",
            "suggested_rate": 30,
            "current_rate": 107,
            "delta_vs_current_pct": -70,
        }]}
        r2 = requests.post(f"{API}/revenue/ai-pricing/city-gate/accept",
                           headers=hdr, json=payload, timeout=20)
        assert r2.status_code == 200, r2.text[:300]
        j = r2.json()
        assert j.get("accepted", 0) >= 1
        assert j.get("lrv_clamped", 0) >= 1, f"expected clamping, got {j}"


# --------------- SEGMENT FORECAST ---------------
class TestSegmentForecast:
    def test_segments_all(self, hdr):
        r = requests.get(f"{API}/forecast-v2/segments/all?months=6", headers=hdr, timeout=25)
        assert r.status_code == 200, r.text[:300]
        j = r.json()
        assert "segments" in j and isinstance(j["segments"], list)
        assert "history" in j and "forecast" in j
        assert len(j["forecast"]) == 6

    def test_segments_property(self, hdr):
        r = requests.get(f"{API}/forecast-v2/segments/aldgate-flats?months=6", headers=hdr, timeout=25)
        assert r.status_code == 200


# --------------- BROAD SMOKE — 500 error hunt ---------------
SMOKE_ENDPOINTS = [
    # revenue & rates
    "/revenue/dashboard/aldgate-flats",
    "/revenue/rates-grid/aldgate-flats?days=14",
    "/revenue/ai-pricing/aldgate-flats/suggestions?days=14&use_llm=false",
    "/revenue/ai-pricing/aldgate-flats/config",
    "/revenue/ai-pricing/aldgate-flats/history",
    "/revenue/pace/aldgate-flats",
    "/revenue/compset/aldgate-flats",
    "/revenue/parity-heatmap/aldgate-flats?days=14",
    "/forecast-v2/horizon/aldgate-flats?months=12",
    "/forecast-v2/demand-calendar/aldgate-flats?days=30",
    "/forecast-v2/two-year-summary/aldgate-flats",
    # housekeeping / ops
    "/housekeeping/tasks",
    "/housekeeping/rooms",
    "/housekeeping/checklists",
    "/housekeeping/laundry",
    "/housekeeping/laundry/settings",
    "/housekeeping/turnover-board/aldgate-flats",
    "/housekeeping/ai-score/aldgate-flats",
    "/housekeeping/routes/aldgate-flats",
    "/housekeeping/qr-codes/aldgate-flats",
    # guests / CRM
    "/guests",
    "/crm/360/summary",
    "/crm/rfm/aldgate-flats",
    "/reviews/inbox",
    # finance
    "/finance/dashboard/aldgate-flats",
    "/finance/expenses",
    "/finance/payroll/shifts",
    # channel manager
    "/channel-manager-v2/connections",
    "/channel-manager-v2/sync-logs",
    # marketing / automation
    "/marketing/campaigns",
    "/marketing/automations",
    "/upsell/stats/aldgate-flats",
    # admin
    "/users",
    "/admin/diagnostics/tasks",
    # roomtypes
    "/room-types?property_id=aldgate-flats",
]


@pytest.mark.parametrize("path", SMOKE_ENDPOINTS)
def test_smoke_no_500(hdr, path):
    r = requests.get(f"{API}{path}", headers=hdr, timeout=25)
    assert r.status_code < 500, f"{path} → {r.status_code}: {r.text[:200]}"


# --------------- PUBLIC PAGES ---------------
class TestPublic:
    def test_booking_widget_data(self):
        r = requests.get(f"{API}/public/booking-widget/aldgate-flats", timeout=15)
        # Endpoint may vary; if 404, tolerate — actual widget uses /book/{slug} frontend
        assert r.status_code in (200, 404), r.status_code
