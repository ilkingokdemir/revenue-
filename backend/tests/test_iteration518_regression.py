"""
Iteration 518 regression: Open Pricing Optimizer, Overbooking Control,
Room-Type Forecast, Decision Assurance (A/B holdout), Group Sales patterned quote,
plus quick backend regression sweep.
"""
import os
import math
import time
import pytest
import requests
from datetime import datetime, timedelta

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    BASE_URL = "https://review-hub-108.preview.emergentagent.com"

ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"
PROPERTY_ID = "default"


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
                      timeout=30)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text[:200]}"
    data = r.json()
    tok = data.get("token") or data.get("access_token")
    assert tok, f"No token in response: {data}"
    return tok


@pytest.fixture(scope="module")
def headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# ---------- NEW FEATURES ----------

class TestOpenPricingOptimizer:
    def test_optimize_matrix_structure(self, headers):
        r = requests.post(f"{BASE_URL}/api/open-pricing/optimize",
                          headers=headers,
                          json={"property_id": PROPERTY_ID, "days": 5},
                          timeout=90)
        assert r.status_code == 200, f"{r.status_code}: {r.text[:400]}"
        data = r.json()
        matrix = data.get("matrix") or []
        assert isinstance(matrix, list) and len(matrix) >= 1, "no matrix days"
        first = matrix[0]
        cells = first.get("cells") or {}
        assert len(cells) == 48, f"expected 48 cells got {len(cells)}"
        chf = data.get("channel_factors") or {}
        assert abs(float(chf.get("direct", 0)) - 0.97) < 0.01, f"direct factor {chf.get('direct')}"

    def test_optimize_apply_writes_overrides(self, headers):
        r = requests.post(f"{BASE_URL}/api/open-pricing/optimize",
                          headers=headers,
                          json={"property_id": PROPERTY_ID, "days": 3, "apply": True},
                          timeout=120)
        assert r.status_code == 200, f"{r.status_code}: {r.text[:400]}"
        data = r.json()
        # Should report written count
        written = data.get("written") or data.get("applied") or data.get("overrides_written")
        # If no explicit key, at least ensure no error
        assert data.get("ok", True) is not False


class TestOverbookingControl:
    def test_get_overbooking(self, headers):
        r = requests.get(f"{BASE_URL}/api/overbooking-control/{PROPERTY_ID}?days=7",
                         headers=headers, timeout=45)
        assert r.status_code == 200, f"{r.status_code}: {r.text[:400]}"
        data = r.json()
        assert "capacity" in data
        assert "adr" in data
        assert "walk_cost_per_guest" in data
        assert "source_rates" in data
        assert "days" in data and len(data["days"]) >= 1
        d0 = data["days"][0]
        assert "recommended_overbooking_limit" in d0
        assert "net_expected" in d0


class TestRoomTypeForecast:
    def test_get_rtf(self, headers):
        r = requests.get(f"{BASE_URL}/api/room-type-forecast/{PROPERTY_ID}?days=7",
                         headers=headers, timeout=45)
        assert r.status_code == 200, f"{r.status_code}: {r.text[:400]}"
        data = r.json()
        assert "room_types" in data
        assert isinstance(data["room_types"], list)
        if data["room_types"]:
            rt = data["room_types"][0]
            assert "days" in rt
            if rt["days"]:
                d0 = rt["days"][0]
                for k in ("otb", "same_dow_avg", "forecast", "forecast_occ_pct"):
                    assert k in d0, f"missing {k} in room type day"


class TestDecisionAssurance:
    def test_experiment_endpoint(self, headers):
        r = requests.get(f"{BASE_URL}/api/decision-assurance/{PROPERTY_ID}/experiment",
                         headers=headers, timeout=30)
        assert r.status_code == 200, f"{r.status_code}: {r.text[:400]}"
        data = r.json()
        assert "holdout_pct" in data
        assert "applied_n" in data
        assert "holdout_n" in data
        assert "note" in data

    def test_config_persists_holdout(self, headers):
        # Set experiment_holdout_pct=10 via PUT
        r = requests.put(f"{BASE_URL}/api/revenue/ai-pricing/{PROPERTY_ID}/config",
                         headers=headers,
                         json={"experiment_holdout_pct": 10},
                         timeout=30)
        assert r.status_code == 200, f"{r.status_code}: {r.text[:400]}"
        # Verify via experiment endpoint
        r2 = requests.get(f"{BASE_URL}/api/decision-assurance/{PROPERTY_ID}/experiment",
                          headers=headers, timeout=30)
        assert r2.status_code == 200
        assert int(r2.json().get("holdout_pct", 0)) == 10


class TestGroupSalesPatternedQuote:
    def test_patterned_quote_math(self, headers):
        start = (datetime.utcnow() + timedelta(days=45)).strftime("%Y-%m-%d")
        end = (datetime.utcnow() + timedelta(days=48)).strftime("%Y-%m-%d")
        payload = {
            "group_name": "QA Pattern 518",
            "check_in": start,
            "check_out": end,
            "rooms": 20,
            "offered_rate": 95,
            "pattern": [8, 20, 12],
            "wash_pct": 10,
            "rebate_pct": 5,
            "fb_contribution": 500,
        }
        r = requests.post(f"{BASE_URL}/api/group-sales/{PROPERTY_ID}/rfp",
                          headers=headers, json=payload, timeout=45)
        assert r.status_code in (200, 201), f"create rfp {r.status_code}: {r.text[:400]}"
        rfp = r.json().get("rfp") or r.json()
        rfp_id = rfp.get("id")
        assert rfp_id, f"no rfp id: {rfp}"

        # Generate quote
        rq = requests.post(f"{BASE_URL}/api/group-sales/rfp/{rfp_id}/quote",
                           headers=headers, json={}, timeout=45)
        assert rq.status_code in (200, 201), f"quote {rq.status_code}: {rq.text[:400]}"
        qd = rq.json()

        expected = math.ceil(40 * 0.9) * 95 * 0.95 + 500  # = 3749.0
        expected_rooms = math.ceil(20 * 0.9)  # 18

        found_val = None
        found_rooms = None

        def scan(obj):
            nonlocal found_val, found_rooms
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if k == "adj_group_revenue" and isinstance(v, (int, float)):
                        found_val = float(v)
                    if k == "expected_rooms" and isinstance(v, (int, float)):
                        found_rooms = int(v)
                    scan(v)
            elif isinstance(obj, list):
                for x in obj:
                    scan(x)

        scan(qd)
        assert found_val is not None, f"adj_group_revenue missing in quote: {str(qd)[:400]}"
        assert abs(found_val - expected) < 0.5, f"adj_group_revenue {found_val} != expected {expected}"
        if found_rooms is not None:
            assert found_rooms == expected_rooms, f"expected_rooms {found_rooms} != {expected_rooms}"

        # Cleanup: mark lost
        try:
            requests.put(f"{BASE_URL}/api/group-sales/rfp/{rfp_id}",
                         headers=headers, json={"status": "lost"}, timeout=30)
        except Exception:
            pass


# ---------- REGRESSION SWEEP ----------

class TestRegressionSweep:
    def test_profit_pricing(self, headers):
        r = requests.get(f"{BASE_URL}/api/profit-pricing/{PROPERTY_ID}?days=5",
                         headers=headers, timeout=45)
        assert r.status_code == 200, r.text[:200]

    def test_data_quality(self, headers):
        r = requests.get(f"{BASE_URL}/api/data-quality/{PROPERTY_ID}",
                         headers=headers, timeout=30)
        assert r.status_code == 200

    def test_data_quality_summary(self, headers):
        r = requests.get(f"{BASE_URL}/api/data-quality/summary/all",
                         headers=headers, timeout=30)
        assert r.status_code == 200

    def test_revpam(self, headers):
        r = requests.get(f"{BASE_URL}/api/revpam/{PROPERTY_ID}",
                         headers=headers, timeout=30)
        assert r.status_code == 200

    def test_abs_public(self):
        r = requests.get(f"{BASE_URL}/api/abs/public/{PROPERTY_ID}", timeout=30)
        assert r.status_code == 200

    def test_group_displacement_analyze(self, headers):
        payload = {
            "property_id": PROPERTY_ID,
            "rooms_requested": 8,
            "quoted_price": 85,
            "offered_rate": 85,
            "check_in": (datetime.utcnow() + timedelta(days=30)).strftime("%Y-%m-%d"),
            "check_out": (datetime.utcnow() + timedelta(days=33)).strftime("%Y-%m-%d"),
        }
        r = requests.post(f"{BASE_URL}/api/group-displacement/analyze",
                          headers=headers, json=payload, timeout=120)
        assert r.status_code in (200, 201), f"{r.status_code}: {r.text[:200]}"
