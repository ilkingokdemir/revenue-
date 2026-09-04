"""Iter 615: competitor gap act, team-star public, monthly report impact panel."""
import os, requests, pytest, datetime as dt
from dotenv import load_dotenv
load_dotenv("/app/frontend/.env")
BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
ADMIN = {"email": "admin@hotelbox.com", "password": "HotelAdmin2026!"}
PID = "default"


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE}/api/auth/login", json=ADMIN, timeout=30)
    assert r.status_code == 200, r.text
    return r.json().get("access_token") or r.json().get("token")


@pytest.fixture(scope="module")
def H(token):
    return {"Authorization": f"Bearer {token}"}


# ---- Competitor gap act ----
class TestCompetitorAct:
    def test_feasibility_task_creates_and_duplicate(self, H):
        body = {"item": "balcony", "action": "feasibility_task"}
        r1 = requests.post(f"{BASE}/api/reputation/competitor-intel/{PID}/act", json=body, headers=H, timeout=30)
        assert r1.status_code == 200, r1.text
        j1 = r1.json()
        assert j1["ok"] is True
        assert "task_id" in j1
        tid = j1["task_id"]
        # my-tasks contains it
        mt = requests.get(f"{BASE}/api/my-tasks", headers=H, timeout=30)
        assert mt.status_code == 200
        rct = mt.json().get("root_cause_tasks") or []
        match = [t for t in rct if t.get("id") == tid or t.get("title") == "Fizibilite: balcony"]
        assert match, f"task not in root_cause_tasks: {[t.get('title') for t in rct][:10]}"
        assert match[0].get("source") == "competitor_gap"
        # duplicate call
        r2 = requests.post(f"{BASE}/api/reputation/competitor-intel/{PID}/act", json=body, headers=H, timeout=30)
        assert r2.status_code == 200
        assert r2.json().get("duplicate") is True
        # Complete
        cc = requests.put(f"{BASE}/api/my-tasks/staff-task/{tid}/complete", headers=H, timeout=30)
        assert cc.status_code == 200, cc.text
        assert cc.json().get("ok") is True

    def test_add_amenity(self, H):
        body = {"item": "free breakfast", "action": "add_amenity"}
        r = requests.post(f"{BASE}/api/reputation/competitor-intel/{PID}/act", json=body, headers=H, timeout=30)
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["ok"] is True
        assert j.get("matched") == 1
        # intel should now not list 'free breakfast'
        g = requests.get(f"{BASE}/api/reputation/competitor-intel/{PID}", headers=H, timeout=45)
        assert g.status_code == 200
        items = [x.get("item") for x in (g.json().get("they_have_we_dont") or [])]
        assert "free breakfast" not in items, items

    def test_invalid_action(self, H):
        r = requests.post(f"{BASE}/api/reputation/competitor-intel/{PID}/act",
                          json={"item": "spa", "action": "bogus"}, headers=H, timeout=30)
        assert r.status_code == 400


# ---- Team star public ----
class TestTeamStar:
    def test_public_and_toggle(self, H):
        r = requests.get(f"{BASE}/api/booking-widget/team-star/{PID}", timeout=30)  # no auth
        assert r.status_code == 200, r.text
        j = r.json()
        assert j.get("enabled") is True
        assert j.get("star") and j["star"].get("name")
        # disable
        cfg = requests.post(f"{BASE}/api/review-agent/config/{PID}", json={"show_team_star": False}, headers=H, timeout=30)
        assert cfg.status_code in (200, 201), cfg.text
        r2 = requests.get(f"{BASE}/api/booking-widget/team-star/{PID}", timeout=30)
        assert r2.status_code == 200
        assert r2.json().get("enabled") is False
        # re-enable
        cfg2 = requests.post(f"{BASE}/api/review-agent/config/{PID}", json={"show_team_star": True}, headers=H, timeout=30)
        assert cfg2.status_code in (200, 201)
        r3 = requests.get(f"{BASE}/api/booking-widget/team-star/{PID}", timeout=30)
        assert r3.json().get("enabled") is True


# ---- Monthly report impact ----
class TestMonthlyReportImpact:
    def test_send_now_and_render(self, H):
        month = dt.datetime.utcnow().strftime("%Y-%m")
        r = requests.post(f"{BASE}/api/monthly-report/{PID}/send-now",
                          json={"month": month, "forced": True}, headers=H, timeout=60)
        assert r.status_code == 200, r.text
        j = r.json()
        rep = j.get("report") or j
        imp = rep.get("impact") or j.get("impact")
        assert imp, f"no impact in response keys: {list(rep.keys())}"
        for k in ["closed_tasks_month", "reported_month", "improved", "worse",
                  "total_rating_gain", "cumulative_rating_gain", "items"]:
            assert k in imp, f"missing {k} in impact: {list(imp.keys())}"
        # history + render
        h = requests.get(f"{BASE}/api/monthly-report/{PID}/history", headers=H, timeout=30)
        assert h.status_code == 200
        items = h.json().get("items") or h.json().get("reports") or h.json()
        assert items, "no report history"
        rid = items[0].get("id") if isinstance(items, list) else None
        if rid:
            rn = requests.get(f"{BASE}/api/monthly-report/{PID}/render/{rid}", headers=H, timeout=30)
            assert rn.status_code == 200
            html = rn.text if "Etki Panosu" in rn.text else rn.json().get("html", "")
            assert "Etki Panosu" in html, "Etki Panosu not in rendered HTML"
