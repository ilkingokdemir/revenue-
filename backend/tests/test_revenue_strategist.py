"""Backend tests for AI Revenue Strategist endpoints."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://review-hub-108.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PW = "HotelAdmin2026!"
PID = "default"


@pytest.fixture(scope="module")
def api():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": ADMIN_EMAIL, "password": ADMIN_PW}, timeout=20)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    data = r.json()
    tok = data.get("access_token") or data.get("token")
    if tok:
        s.headers.update({"Authorization": f"Bearer {tok}"})
    return s


# ---------- config endpoints ----------
class TestConfig:
    def test_get_default_config(self, api):
        r = api.get(f"{BASE_URL}/api/strategist/{PID}/config", timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert set(["auto_apply", "language", "horizon_days"]).issubset(d.keys())
        assert d["language"] in ("tr", "en")
        assert d["horizon_days"] in (30, 90, 365)
        assert isinstance(d["auto_apply"], bool)

    def test_put_config_validates_language(self, api):
        # invalid lang -> silently dropped, existing lang preserved
        r = api.put(f"{BASE_URL}/api/strategist/{PID}/config",
                    json={"language": "fr"}, timeout=15)
        assert r.status_code == 200
        assert r.json()["language"] in ("tr", "en")

    def test_put_config_validates_horizon(self, api):
        r = api.put(f"{BASE_URL}/api/strategist/{PID}/config",
                    json={"horizon_days": 45}, timeout=15)
        assert r.status_code == 200
        assert r.json()["horizon_days"] in (30, 90, 365)

    def test_put_config_updates_valid(self, api):
        r = api.put(f"{BASE_URL}/api/strategist/{PID}/config",
                    json={"language": "en", "horizon_days": 30, "auto_apply": False}, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["language"] == "en"
        assert d["horizon_days"] == 30
        assert d["auto_apply"] is False
        # verify persistence
        d2 = api.get(f"{BASE_URL}/api/strategist/{PID}/config", timeout=15).json()
        assert d2["language"] == "en" and d2["horizon_days"] == 30

    def test_reset_config(self, api):
        # reset to tr / 90 / auto_apply=false per handoff note
        r = api.put(f"{BASE_URL}/api/strategist/{PID}/config",
                    json={"language": "tr", "horizon_days": 90, "auto_apply": False}, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["language"] == "tr" and d["horizon_days"] == 90 and d["auto_apply"] is False


# ---------- reports listing ----------
class TestReports:
    def test_list_reports(self, api):
        r = api.get(f"{BASE_URL}/api/strategist/{PID}/reports", timeout=20)
        assert r.status_code == 200
        items = r.json().get("items", [])
        assert isinstance(items, list)
        assert len(items) >= 1, "expected at least one existing report from dev"
        rep = items[0]
        for k in ("id", "situation_report", "market_analysis", "past_performance",
                  "what_was_done", "risks", "opportunities", "recommendations", "kpis"):
            assert k in rep, f"missing field {k}"
        assert isinstance(rep["recommendations"], list)
        for a in rep["recommendations"]:
            assert "id" in a and "action_type" in a and "priority" in a and "status" in a

    def test_apply_already_applied_returns_400(self, api):
        items = api.get(f"{BASE_URL}/api/strategist/{PID}/reports", timeout=20).json()["items"]
        rid = None
        aid = None
        for rep in items:
            for a in rep["recommendations"]:
                if a.get("status") in ("applied", "auto_applied"):
                    rid = rep["id"]; aid = a["id"]; break
            if rid:
                break
        if not rid:
            pytest.skip("No already-applied action found to test 400 flow")
        r = api.post(f"{BASE_URL}/api/strategist/{PID}/reports/{rid}/actions/{aid}/apply", timeout=20)
        assert r.status_code == 400

    def test_dismiss_flow(self, api):
        """Pick a suggested action from latest report, dismiss it, verify status changed."""
        items = api.get(f"{BASE_URL}/api/strategist/{PID}/reports", timeout=20).json()["items"]
        target = None
        for rep in items:
            for a in rep["recommendations"]:
                if a.get("status") == "suggested":
                    target = (rep["id"], a["id"]); break
            if target:
                break
        if not target:
            pytest.skip("No 'suggested' action available to dismiss")
        rid, aid = target
        r = api.post(f"{BASE_URL}/api/strategist/{PID}/reports/{rid}/actions/{aid}/dismiss", timeout=20)
        assert r.status_code == 200
        assert r.json().get("ok") is True
        # verify status changed
        rep2 = next(x for x in api.get(f"{BASE_URL}/api/strategist/{PID}/reports", timeout=20).json()["items"] if x["id"] == rid)
        a2 = next(x for x in rep2["recommendations"] if x["id"] == aid)
        assert a2["status"] == "dismissed"

    def test_apply_unknown_action_returns_404(self, api):
        items = api.get(f"{BASE_URL}/api/strategist/{PID}/reports", timeout=20).json()["items"]
        if not items:
            pytest.skip("no reports")
        rid = items[0]["id"]
        r = api.post(f"{BASE_URL}/api/strategist/{PID}/reports/{rid}/actions/does-not-exist/apply", timeout=20)
        assert r.status_code == 404

    def test_unknown_report_returns_404(self, api):
        r = api.post(f"{BASE_URL}/api/strategist/{PID}/reports/deadbeef/actions/xyz/apply", timeout=20)
        assert r.status_code == 404
