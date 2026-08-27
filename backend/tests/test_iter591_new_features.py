"""Iter 591 — Sentiment Pricing, Owner Weekly Summary, Comp Anomaly integration,
PWA basics and regression tests for refactored league/uplift computes."""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

ADMIN = {"email": "admin@hotelbox.com", "password": "HotelAdmin2026!"}
REVENUE = {"email": "revenue@hotelbox.com", "password": "Test2026!"}
MANAGER_EMAILS = ["revenue@hotelbox.com", "sales@hotelbox.com"]


# ---------- fixtures ----------
@pytest.fixture(scope="session")
def s():
    # Don't share session across users — cookies would leak between admin/revenue
    sess = requests.Session()
    sess.headers.update({"Content-Type": "application/json"})
    return sess


def _clear_cookies(s):
    s.cookies.clear()


def _login(s, creds):
    # Use fresh session to avoid cookie contamination across users
    r = requests.post(f"{BASE_URL}/api/auth/login", json=creds, timeout=30)
    assert r.status_code == 200, f"login failed {r.status_code} {r.text[:200]}"
    return r.json()["token"]


@pytest.fixture(scope="session")
def admin_token(s):
    return _login(s, ADMIN)


@pytest.fixture(scope="session")
def revenue_token(s):
    return _login(s, REVENUE)


@pytest.fixture
def A(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


@pytest.fixture
def R(revenue_token):
    return {"Authorization": f"Bearer {revenue_token}", "Content-Type": "application/json"}


# ---------- 1. Sentiment Pricing ----------
class TestSentimentPricing:
    def test_get_default(self, s, A):
        r = s.get(f"{BASE_URL}/api/sentiment-pricing/default", headers=A, timeout=30)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        for k in ["property_id", "index", "avg_rating", "trend", "reviews_90d",
                  "suggested_adj_pct", "signal", "risk_reviews", "applies", "note"]:
            assert k in d, f"missing {k}: {list(d)}"
        # index should be number 0-100 (or None if no reviews)
        if d["index"] is not None:
            assert 0 <= d["index"] <= 100
        assert isinstance(d["risk_reviews"], list)
        assert isinstance(d["applies"], list)

    def test_apply_zero_adj_returns_422(self, s, A):
        # first check suggested; if 0, POST {} must 422
        g = s.get(f"{BASE_URL}/api/sentiment-pricing/default", headers=A, timeout=30).json()
        suggested = g.get("suggested_adj_pct") or 0
        r = s.post(f"{BASE_URL}/api/sentiment-pricing/default/apply",
                   headers=A, json={}, timeout=30)
        if suggested == 0:
            assert r.status_code == 422, r.text[:200]
            assert "Sıfır" in r.text or "nötr" in r.text
        else:
            # if non-zero suggested, apply should succeed
            assert r.status_code == 200

    def test_apply_positive_adj(self, s, A):
        r = s.post(f"{BASE_URL}/api/sentiment-pricing/default/apply",
                   headers=A, json={"adj_pct": 2}, timeout=60)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert d.get("ok") is True
        assert "written" in d and "skipped" in d
        assert d["adj_pct"] == 2.0
        # index in log
        assert "index" in d
        # fires reprice event — verify shortly after
        time.sleep(3)
        ev = s.get(f"{BASE_URL}/api/reprice-bridge/default/events", headers=A, timeout=30)
        if ev.status_code == 200:
            events = ev.json().get("events") or ev.json() if isinstance(ev.json(), list) else ev.json().get("events", [])
            # find sentiment_apply event
            body = ev.text
            assert "sentiment_apply" in body, "no sentiment_apply event fired"

    def test_apply_clamps_to_5(self, s, A):
        r = s.post(f"{BASE_URL}/api/sentiment-pricing/default/apply",
                   headers=A, json={"adj_pct": 20}, timeout=60)
        assert r.status_code == 200, r.text[:200]
        assert r.json()["adj_pct"] == 5.0

    def test_apply_clamps_to_negative_5(self, s, A):
        r = s.post(f"{BASE_URL}/api/sentiment-pricing/default/apply",
                   headers=A, json={"adj_pct": -50}, timeout=60)
        assert r.status_code == 200
        assert r.json()["adj_pct"] == -5.0


# ---------- 2. Owner Weekly ----------
class TestOwnerWeekly:
    def test_preview(self, s, A):
        r = s.get(f"{BASE_URL}/api/owner-weekly/preview", headers=A, timeout=60)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        for k in ["week_key", "league", "uplifts", "html"]:
            assert k in d, f"missing {k}"
        assert len(d["html"]) > 1000, f"html too short: {len(d['html'])}"
        assert "GOPPAR Ligi" in d["html"]
        assert isinstance(d["uplifts"], list)
        assert "properties" in d["league"]
        assert "portfolio_goppar" in d["league"]

    def test_send_now_admin(self, s, A):
        r = s.post(f"{BASE_URL}/api/owner-weekly/send-now", headers=A, timeout=60)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert "sent_to" in d
        assert isinstance(d["sent_to"], list)
        assert len(d["sent_to"]) >= 1, "should send to at least 1 admin/manager"

    def test_send_now_manager_forbidden(self, s, R):
        s.cookies.clear()
        r = requests.post(f"{BASE_URL}/api/owner-weekly/send-now", headers=R, timeout=30)
        assert r.status_code == 403, f"manager should get 403, got {r.status_code}"

    def test_history(self, s, A):
        # ensure at least one send exists
        s.post(f"{BASE_URL}/api/owner-weekly/send-now", headers=A, timeout=60)
        r = s.get(f"{BASE_URL}/api/owner-weekly/history", headers=A, timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert "sends" in d
        assert isinstance(d["sends"], list)
        assert len(d["sends"]) >= 1

    def test_send_forced_twice_works(self, s, A):
        r1 = s.post(f"{BASE_URL}/api/owner-weekly/send-now", headers=A, timeout=60)
        r2 = s.post(f"{BASE_URL}/api/owner-weekly/send-now", headers=A, timeout=60)
        assert r1.status_code == 200 and r2.status_code == 200
        # both should return sent_to (forced=True bypasses skip)
        assert "sent_to" in r1.json() and "sent_to" in r2.json()


# ---------- 3. Comp Anomaly integration ----------
class TestCompAnomalyIntegration:
    def test_comp_radar_scan_has_anomalies_excluded(self, s, A):
        r = s.post(f"{BASE_URL}/api/comp-radar/scan?property_id=default",
                   headers=A, timeout=90)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert d.get("ok") is True
        assert "findings" in d
        # verify anomalies_excluded field exists in stored findings
        radar = s.get(f"{BASE_URL}/api/comp-radar/default", headers=A, timeout=30)
        assert radar.status_code == 200
        findings = radar.json().get("findings", [])
        if findings:
            # at least one finding should have anomalies_excluded field
            with_field = [f for f in findings if "anomalies_excluded" in f]
            assert len(with_field) > 0, "no findings have anomalies_excluded field"
            for f in with_field:
                assert isinstance(f["anomalies_excluded"], int)
                assert f["anomalies_excluded"] >= 0

    def test_clean_median_endpoint(self, s, A):
        r = s.get(f"{BASE_URL}/api/comp-anomaly/default/clean-median",
                  headers=A, timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert "raw_median" in d and "clean_median" in d
        assert "raw_count" in d and "clean_count" in d


# ---------- 4. PWA basics ----------
class TestPWA:
    def test_manifest(self, s):
        r = s.get(f"{BASE_URL}/manifest.json", timeout=30)
        assert r.status_code == 200, r.status_code
        # content
        try:
            m = r.json()
            assert "MyHotelBox" in (m.get("name", "") + m.get("short_name", ""))
        except Exception:
            assert "MyHotelBox" in r.text

    def test_service_worker(self, s):
        r = s.get(f"{BASE_URL}/sw.js", timeout=30)
        assert r.status_code == 200


# ---------- 5. Notifications ----------
class TestNotifications:
    def test_notifications_unread(self, s, A):
        r = s.get(f"{BASE_URL}/api/notifications?unread_only=true",
                  headers=A, timeout=30)
        assert r.status_code == 200, r.text[:200]
        d = r.json()
        assert "notifications" in d
        assert "unread_count" in d
        assert isinstance(d["notifications"], list)


# ---------- 6. Regression ----------
class TestRegression:
    def test_profit_benchmark(self, s, A):
        r = s.get(f"{BASE_URL}/api/profit-benchmark?months=3", headers=A, timeout=60)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert "properties" in d
        assert "portfolio_goppar" in d
        for p in d["properties"][:3]:
            for k in ["rank", "goppar", "badge", "name", "property_id"]:
                assert k in p, f"missing {k} in property {p}"

    def test_rms_uplift(self, s, A):
        r = s.get(f"{BASE_URL}/api/rms-uplift/default", headers=A, timeout=60)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        for k in ["baseline_revpar", "months", "verdict"]:
            assert k in d, f"missing {k}"

    def test_rate_mix_all(self, s, A):
        r = s.get(f"{BASE_URL}/api/rate-mix/all", headers=A, timeout=60)
        assert r.status_code == 200
