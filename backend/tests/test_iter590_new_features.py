"""Iter 590 — 4 new features:
(1) Approval RBAC (segment_group), (2) Forecast 730, (3) Comp Anomaly, (4) Profit Benchmark.
"""
import os
import pytest
import requests


def _load_env(path):
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line and "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    v = v.strip().strip('"').strip("'")
                    os.environ.setdefault(k, v)
    except Exception:
        pass


_load_env("/app/frontend/.env")
_load_env("/app/backend/.env")
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")

ADMIN = {"email": "admin@hotelbox.com", "password": "HotelAdmin2026!"}
REV = {"email": "revenue@hotelbox.com", "password": "Test2026!"}
SLS = {"email": "sales@hotelbox.com", "password": "Test2026!"}


def _login(creds):
    r = requests.post(f"{BASE_URL}/api/auth/login", json=creds, timeout=15)
    assert r.status_code == 200, f"login {creds['email']} failed: {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def admin_h():
    return {"Authorization": f"Bearer {_login(ADMIN)}"}


@pytest.fixture(scope="module")
def rev_h():
    return {"Authorization": f"Bearer {_login(REV)}"}


@pytest.fixture(scope="module")
def sales_h():
    return {"Authorization": f"Bearer {_login(SLS)}"}


# ------------------- Approval RBAC -------------------
class TestApprovalRBAC:
    def test_get_config_default(self, admin_h):
        r = requests.get(f"{BASE_URL}/api/group-approval/default/config", headers=admin_h)
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["chain"] == ["revenue", "sales"]
        steps = j["steps"]
        assert "revenue" in steps["revenue"] and "management" in steps["revenue"]
        assert "sales" in steps["sales"] and "management" in steps["sales"]

    def test_put_config_manager_forbidden(self, rev_h):
        r = requests.put(f"{BASE_URL}/api/group-approval/default/config",
                         json={"steps": {"revenue": ["revenue"], "sales": ["sales"]}}, headers=rev_h)
        assert r.status_code == 403, r.text

    def test_put_config_admin_ok_and_restore(self, admin_h):
        r = requests.put(f"{BASE_URL}/api/group-approval/default/config",
                         json={"steps": {"revenue": ["revenue"], "sales": ["sales"]}}, headers=admin_h)
        assert r.status_code == 200, r.text
        assert r.json()["steps"]["revenue"] == ["revenue"]
        # restore defaults
        r2 = requests.put(f"{BASE_URL}/api/group-approval/default/config",
                          json={"steps": {"revenue": ["revenue", "management"],
                                          "sales": ["sales", "management"]}}, headers=admin_h)
        assert r2.status_code == 200
        assert "management" in r2.json()["steps"]["revenue"]

    def test_full_rbac_flow(self, admin_h, rev_h, sales_h):
        # create quote as admin
        payload = {"group_name": "TEST_RBAC", "rooms": 5, "nights": 2, "check_in": "2026-06-01",
                   "wish_price": 200, "walk_price": 150}
        r = requests.post(f"{BASE_URL}/api/group-approval/default/quotes",
                          json=payload, headers=admin_h)
        assert r.status_code == 200, r.text
        qid = r.json()["id"]
        assert r.json()["status"] == "pending_revenue"

        # sales trying to approve revenue → 403 (Turkish message)
        r1 = requests.post(f"{BASE_URL}/api/group-approval/default/quotes/{qid}/approve",
                           json={"role": "revenue"}, headers=sales_h)
        assert r1.status_code == 403, r1.text
        assert "departman" in r1.json().get("detail", "").lower()

        # revenue approves revenue → pending_sales
        r2 = requests.post(f"{BASE_URL}/api/group-approval/default/quotes/{qid}/approve",
                           json={"role": "revenue"}, headers=rev_h)
        assert r2.status_code == 200, r2.text
        assert r2.json()["status"] == "pending_sales"

        # revenue trying to approve sales → 403
        r3 = requests.post(f"{BASE_URL}/api/group-approval/default/quotes/{qid}/approve",
                           json={"role": "sales"}, headers=rev_h)
        assert r3.status_code == 403, r3.text

        # sales approves sales → approved
        r4 = requests.post(f"{BASE_URL}/api/group-approval/default/quotes/{qid}/approve",
                           json={"role": "sales"}, headers=sales_h)
        assert r4.status_code == 200, r4.text
        assert r4.json()["status"] == "approved"

    def test_admin_bypass(self, admin_h):
        payload = {"group_name": "TEST_ADMIN_BYPASS", "rooms": 2, "nights": 1, "check_in": "2026-07-01",
                   "wish_price": 180, "walk_price": 120}
        r = requests.post(f"{BASE_URL}/api/group-approval/default/quotes",
                          json=payload, headers=admin_h)
        qid = r.json()["id"]
        r1 = requests.post(f"{BASE_URL}/api/group-approval/default/quotes/{qid}/approve",
                           json={"role": "revenue"}, headers=admin_h)
        assert r1.status_code == 200 and r1.json()["status"] == "pending_sales"
        r2 = requests.post(f"{BASE_URL}/api/group-approval/default/quotes/{qid}/approve",
                           json={"role": "sales"}, headers=admin_h)
        assert r2.status_code == 200 and r2.json()["status"] == "approved"


# ------------------- Forecast 730 -------------------
class TestForecast730:
    def test_get(self, admin_h):
        r = requests.get(f"{BASE_URL}/api/forecast-730/default", headers=admin_h)
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["capacity"] == 20, f"expected 20 got {j['capacity']}"
        assert len(j["months"]) == 24
        for m in j["months"]:
            for k in ("month", "seasonality_idx", "projected_occ_pct",
                      "otb_room_nights", "otb_occ_pct", "stance"):
                assert k in m, f"missing {k}"
            assert isinstance(m["stance"], str) and len(m["stance"]) > 0

    def test_auth_required(self):
        r = requests.get(f"{BASE_URL}/api/forecast-730/default")
        assert r.status_code in (401, 403)


# ------------------- Comp Anomaly -------------------
class TestCompAnomaly:
    def test_scan(self, admin_h):
        r = requests.get(f"{BASE_URL}/api/comp-anomaly/default?days=90", headers=admin_h)
        assert r.status_code == 200, r.text
        j = r.json()
        assert "config" in j
        cfg = j["config"]
        for k in ("enabled", "z_threshold", "low_pct", "high_pct"):
            assert k in cfg
        assert j["total"] >= 1
        assert len(j["anomalies"]) >= 1
        a = j["anomalies"][0]
        for k in ("comp_name", "date", "rate", "median", "z", "reason", "key", "ignored", "source"):
            assert k in a, f"missing {k}"
        assert a["source"] in ("compset", "scraper")

    def test_config_clamps(self, admin_h):
        r = requests.put(f"{BASE_URL}/api/comp-anomaly/default/config",
                         json={"z_threshold": 100, "low_pct": 5, "high_pct": 999},
                         headers=admin_h)
        assert r.status_code == 200
        c = r.json()["config"]
        assert c["z_threshold"] == 6.0
        assert c["low_pct"] == 10.0
        assert c["high_pct"] == 500.0
        # restore
        requests.put(f"{BASE_URL}/api/comp-anomaly/default/config",
                     json={"z_threshold": 3.0, "low_pct": 45.0, "high_pct": 250.0},
                     headers=admin_h)

    def test_ignore_one(self, admin_h):
        r = requests.get(f"{BASE_URL}/api/comp-anomaly/default?days=90", headers=admin_h)
        anomalies = r.json()["anomalies"]
        target = next((a for a in anomalies if not a["ignored"]), None)
        if not target:
            pytest.skip("no active anomaly to ignore")
        key = target["key"]
        r2 = requests.post(f"{BASE_URL}/api/comp-anomaly/default/ignore",
                           json={"key": key, "reason": "TEST"}, headers=admin_h)
        assert r2.status_code == 200 and r2.json()["ok"] is True
        r3 = requests.get(f"{BASE_URL}/api/comp-anomaly/default?days=90", headers=admin_h)
        found = [a for a in r3.json()["anomalies"] if a["key"] == key]
        assert found and found[0]["ignored"] is True

    def test_clean_median(self, admin_h):
        r = requests.get(f"{BASE_URL}/api/comp-anomaly/default?days=90", headers=admin_h)
        # pick a date from an anomaly
        anomalies = r.json()["anomalies"]
        target_date = next((a["date"] for a in anomalies if a.get("source") == "compset"), None)
        if not target_date:
            pytest.skip("no compset date")
        r2 = requests.get(f"{BASE_URL}/api/comp-anomaly/default/clean-median?date={target_date}",
                          headers=admin_h)
        assert r2.status_code == 200
        j = r2.json()
        assert "raw_median" in j and "clean_median" in j
        assert "raw_count" in j and "clean_count" in j


# ------------------- Profit Benchmark -------------------
class TestProfitBenchmark:
    def test_league(self, admin_h):
        r = requests.get(f"{BASE_URL}/api/profit-benchmark?months=3", headers=admin_h)
        assert r.status_code == 200, r.text
        j = r.json()
        assert "portfolio_goppar" in j
        props = j["properties"]
        assert len(props) >= 1
        # sorted desc by goppar
        for i in range(1, len(props)):
            assert props[i - 1]["goppar"] >= props[i]["goppar"]
        for i, p in enumerate(props):
            assert p["rank"] == i + 1
            assert p["occ_pct"] <= 100
            for k in ("adr", "revpar", "trevpar", "goppar", "badge", "insight"):
                assert k in p
            assert p["badge"] in ("lider", "ortalama üstü", "ortalama altı")

    def test_months_clamp(self, admin_h):
        r = requests.get(f"{BASE_URL}/api/profit-benchmark?months=0", headers=admin_h)
        assert r.status_code == 200
        r2 = requests.get(f"{BASE_URL}/api/profit-benchmark?months=100", headers=admin_h)
        assert r2.status_code == 200


# ------------------- Regression -------------------
class TestRegression:
    def test_rate_mix_all(self, admin_h):
        r = requests.get(f"{BASE_URL}/api/rate-mix/all", headers=admin_h)
        assert r.status_code == 200

    def test_rms_uplift(self, admin_h):
        r = requests.get(f"{BASE_URL}/api/rms-uplift/default", headers=admin_h)
        assert r.status_code == 200

    def test_group_approval_list(self, admin_h):
        r = requests.get(f"{BASE_URL}/api/group-approval/default", headers=admin_h)
        assert r.status_code == 200
        assert "quotes" in r.json()

    def test_segment_pricing(self, admin_h):
        r = requests.get(f"{BASE_URL}/api/segment-pricing/default", headers=admin_h)
        assert r.status_code == 200
        assert "segments" in r.json()
