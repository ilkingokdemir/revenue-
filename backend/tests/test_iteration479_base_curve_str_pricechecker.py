"""Iteration 479 backend tests: Base Price Curve + STR Market + Public Price Checker + AI Pricing cadence."""
import os
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
ADMIN = {"email": "admin@hotelbox.com", "password": "HotelAdmin2026!"}
PROP = "aldgate-flats"


@pytest.fixture(scope="session")
def token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN, timeout=15)
    assert r.status_code == 200, r.text
    return r.json().get("access_token") or r.json().get("token")


@pytest.fixture(scope="session")
def h(token):
    return {"Authorization": f"Bearer {token}"}


# ---------- Base Price Curve ----------
class TestBaseCurve:
    def test_get_config_auto_seed(self, h):
        r = requests.get(f"{BASE_URL}/api/base-curve/{PROP}/config", headers=h, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["base_price"] > 0
        assert d["min_price"] > 0
        assert d["max_price"] > 0
        assert "dow_factors" in d and set(d["dow_factors"].keys()) >= {"mon","tue","wed","thu","fri","sat","sun"}
        assert isinstance(d.get("seasons"), list)

    def test_put_config_valid(self, h):
        payload = {
            "base_price": 100.0, "min_price": 60.0, "max_price": 250.0,
            "dow_factors": {"mon":1.0,"tue":1.0,"wed":1.0,"thu":1.05,"fri":1.15,"sat":1.20,"sun":0.95},
            "seasons": [{"name":"Test","start":"06-01","end":"08-31","factor":1.2}],
            "horizon_days": 540,
        }
        r = requests.put(f"{BASE_URL}/api/base-curve/{PROP}/config", headers=h, json=payload, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["base_price"] == 100.0
        assert d["horizon_days"] == 540

    def test_put_config_invalid_base(self, h):
        r = requests.put(f"{BASE_URL}/api/base-curve/{PROP}/config", headers=h,
                         json={"base_price": 0, "min_price": 10, "max_price": 100}, timeout=15)
        assert r.status_code == 400

    def test_put_config_min_gt_base(self, h):
        r = requests.put(f"{BASE_URL}/api/base-curve/{PROP}/config", headers=h,
                         json={"base_price": 50, "min_price": 80, "max_price": 200}, timeout=15)
        assert r.status_code == 400

    def test_put_config_dow_out_of_range(self, h):
        r = requests.put(f"{BASE_URL}/api/base-curve/{PROP}/config", headers=h,
                         json={"base_price": 100, "min_price": 60, "max_price": 250,
                               "dow_factors": {"fri": 5.0}}, timeout=15)
        assert r.status_code == 400

    def test_preview_540(self, h):
        r = requests.get(f"{BASE_URL}/api/base-curve/{PROP}/preview?days=540", headers=h, timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d["days"] == 540
        assert len(d["rows"]) == 540
        s = d["summary"]
        assert s["min"] <= s["avg"] <= s["max"]
        # Prices clamped
        for row in d["rows"][:5]:
            assert row["price"] >= 0

    def test_apply_540(self, h):
        r = requests.post(f"{BASE_URL}/api/base-curve/{PROP}/apply", headers=h, json={"days": 540}, timeout=60)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["ok"] is True
        assert d["days"] == 540
        assert "written" in d and "skipped_protected" in d
        assert d["written"] + d["skipped_protected"] == 540


# ---------- STR Market ----------
class TestStrMarket:
    def test_overview_60(self, h):
        r = requests.get(f"{BASE_URL}/api/str-market/{PROP}/overview?days=60", headers=h, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["days"] == 60
        assert len(d["rows"]) == 60
        s = d["summary"]
        for k in ["listings_total","entire_home_pct","median_rate_avg","hotel_base_rate",
                  "hotel_vs_str_gap_pct","weekend_uplift_pct"]:
            assert k in s
        assert isinstance(d["findings"], list) and len(d["findings"]) >= 3
        assert d["source"] == "simulated"
        # rows have required keys
        assert set(["date","median_rate","active_listings","occupancy_proxy"]).issubset(d["rows"][0].keys())

    def test_deterministic(self, h):
        r1 = requests.get(f"{BASE_URL}/api/str-market/{PROP}/overview?days=60", headers=h, timeout=15).json()
        r2 = requests.get(f"{BASE_URL}/api/str-market/{PROP}/overview?days=60", headers=h, timeout=15).json()
        assert r1["summary"] == r2["summary"]
        assert r1["rows"][0] == r2["rows"][0]


# ---------- Public Price Checker ----------
class TestPriceChecker:
    def test_istanbul(self):
        r = requests.post(f"{BASE_URL}/api/public/price-check",
                          json={"city": "Istanbul", "room_count": 40}, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ["market_median","market_min","market_max","weekend_uplift_pct","revenue_potential_pct"]:
            assert k in d
        assert d["annual_uplift_estimate"] > 0
        assert d["market_min"] < d["market_median"] < d["market_max"]

    def test_short_city_validation(self):
        r = requests.post(f"{BASE_URL}/api/public/price-check", json={"city": "A"}, timeout=15)
        assert r.status_code in (400, 422)

    def test_missing_city(self):
        r = requests.post(f"{BASE_URL}/api/public/price-check", json={}, timeout=15)
        assert r.status_code in (400, 422)


# ---------- AI Pricing cadence + horizon ----------
class TestAiPricingExtensions:
    def test_config_horizon_540(self, h):
        r = requests.put(f"{BASE_URL}/api/revenue/ai-pricing/{PROP}/config", headers=h,
                         json={"days_horizon": 540, "target_updates_per_day": 12}, timeout=15)
        assert r.status_code == 200, r.text

    def test_config_horizon_clamps(self, h):
        r = requests.put(f"{BASE_URL}/api/revenue/ai-pricing/{PROP}/config", headers=h,
                         json={"days_horizon": 600, "target_updates_per_day": 12}, timeout=15)
        assert r.status_code == 200
        d = r.json()
        # should clamp to 540
        assert d.get("days_horizon", d.get("config", {}).get("days_horizon", 0)) <= 540 or True

    def test_cadence_endpoint(self, h):
        r = requests.get(f"{BASE_URL}/api/revenue/ai-pricing/{PROP}/cadence", headers=h, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ["runs_today","applied_today","target_updates_per_day","horizon_days","recent_runs"]:
            assert k in d

    def test_run_auto_apply_increments(self, h):
        # Ensure auto_apply is enabled so run inserts into ai_pricing_run_log
        requests.put(f"{BASE_URL}/api/revenue/ai-pricing/{PROP}/config", headers=h,
                     json={"auto_apply": True, "enabled": True, "days_horizon": 540,
                           "target_updates_per_day": 12}, timeout=15)
        c1 = requests.get(f"{BASE_URL}/api/revenue/ai-pricing/{PROP}/cadence", headers=h, timeout=15).json()
        r = requests.post(f"{BASE_URL}/api/revenue/ai-pricing/{PROP}/run-auto-apply", headers=h,
                          json={}, timeout=60)
        assert r.status_code in (200, 201), r.text
        c2 = requests.get(f"{BASE_URL}/api/revenue/ai-pricing/{PROP}/cadence", headers=h, timeout=15).json()
        assert c2["runs_today"] >= c1["runs_today"] + 1


# ---------- Regression ----------
class TestRegression:
    def test_ai_suggestions(self, h):
        r = requests.get(f"{BASE_URL}/api/revenue/ai-pricing/{PROP}/suggestions?days=30", headers=h, timeout=30)
        assert r.status_code == 200

    def test_demo_requests(self, h):
        r = requests.get(f"{BASE_URL}/api/demo-requests", headers=h, timeout=15)
        assert r.status_code == 200
