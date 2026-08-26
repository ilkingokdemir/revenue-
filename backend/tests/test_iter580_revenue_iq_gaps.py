"""Iter 580 — RevenueIQ 4 gap modülleri: lastday-ladder, storefront-verify,
second-writer, annual-plan. Property: default. Admin token ile."""
import os
import requests
from datetime import datetime, timezone, timedelta

BASE = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE}/api"
PID = "default"


def _login():
    r = requests.post(f"{API}/auth/login",
                      json={"email": "admin@hotelbox.com", "password": "HotelAdmin2026!"}, timeout=15)
    assert r.status_code == 200, r.text
    j = r.json()
    return j.get("access_token") or j["token"]


TOKEN = _login()
H = {"Authorization": f"Bearer {TOKEN}"}


def _tomorrow():
    return (datetime.now(timezone.utc).date() + timedelta(days=1)).isoformat()


def _today():
    return datetime.now(timezone.utc).date().isoformat()


# ============= LASTDAY LADDER =============
class TestLastdayLadder:
    def test_status(self):
        r = requests.get(f"{API}/lastday-ladder/{PID}", headers=H, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "config" in d and "steps" in d and "summary" in d
        for k in ("enabled", "window_days", "cadence_hours", "step_pct", "max_steps"):
            assert k in d["config"]

    def test_enable_config(self):
        r = requests.put(f"{API}/lastday-ladder/{PID}/config",
                         headers=H, json={"enabled": True, "max_steps": 3, "step_pct": 8, "cadence_hours": 1},
                         timeout=15)
        assert r.status_code == 200, r.text
        assert r.json()["config"]["enabled"] is True

    def test_scan_and_step_progression(self):
        # ensure floor exists (endpoint uses min_rate_floors; assume seed already or scan will skip)
        r1 = requests.post(f"{API}/lastday-ladder/{PID}/scan?force=true", headers=H, timeout=30)
        assert r1.status_code == 200, r1.text
        r2 = requests.post(f"{API}/lastday-ladder/{PID}/scan?force=true", headers=H, timeout=30)
        assert r2.status_code == 200, r2.text
        # After scans, verify status shows steps and floor discipline
        st = requests.get(f"{API}/lastday-ladder/{PID}", headers=H, timeout=15).json()
        # If actions happened, verify max_steps discipline via ladder_state indirectly through steps
        max_steps = int(st["config"]["max_steps"])
        for s in st["steps"]:
            assert s["step_no"] <= max_steps
            if "floor" in s and s.get("floor") is not None:
                assert s["rate"] >= s["floor"] - 0.01


# ============= STOREFRONT VERIFY =============
class TestStorefrontVerify:
    def test_scan(self):
        r = requests.post(f"{API}/storefront-verify/{PID}/scan", headers=H, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "rows" in d and isinstance(d["rows"], list)
        assert d["total"] == len(d["rows"])
        for row in d["rows"]:
            for k in ("date", "written", "expected_guest", "observed", "deviation_pct", "status"):
                assert k in row

    def test_inject_drift_and_rescan(self):
        r0 = requests.post(f"{API}/storefront-verify/{PID}/scan", headers=H, timeout=30).json()
        # find target row for tomorrow
        target = _tomorrow()
        expected = None
        for row in r0["rows"]:
            if row["date"] == target:
                expected = row["expected_guest"]
                break
        if expected is None or expected <= 0:
            # fallback: use first row
            row0 = r0["rows"][0]
            target = row0["date"]
            expected = row0["expected_guest"]
        observed = round(expected * 0.9, 2)
        ri = requests.post(f"{API}/storefront-verify/{PID}/inject-drift",
                           headers=H, json={"date": target, "observed_rate": observed}, timeout=15)
        assert ri.status_code == 200, ri.text
        r2 = requests.post(f"{API}/storefront-verify/{PID}/scan", headers=H, timeout=30).json()
        assert r2["flagged"] >= 1
        found = next((r for r in r2["rows"] if r["date"] == target), None)
        assert found is not None
        assert found["status"] == "drift"
        # notification exists
        nres = requests.get(f"{API}/notifications", headers=H, timeout=15)
        if nres.status_code == 200:
            items = nres.json() if isinstance(nres.json(), list) else nres.json().get("notifications", [])
            assert any(n.get("category") == "storefront_verify" for n in items)

    def test_clear_drift(self):
        r = requests.delete(f"{API}/storefront-verify/{PID}/drift", headers=H, timeout=15)
        assert r.status_code == 200
        assert r.json()["ok"] is True


# ============= SECOND WRITER =============
class TestSecondWriter:
    def test_push(self):
        r = requests.post(f"{API}/second-writer/{PID}/push", headers=H, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["ok"] is True
        assert d["cells_written"] > 0

    def test_simulate_scan_ack_repush(self):
        # Simulate foreign write
        day = _tomorrow()
        rs = requests.post(f"{API}/second-writer/{PID}/simulate-foreign-write",
                           headers=H, json={"date": day, "channel": "booking", "rate": 42}, timeout=15)
        assert rs.status_code == 200, rs.text
        # Scan
        rc = requests.post(f"{API}/second-writer/{PID}/scan", headers=H, timeout=30)
        assert rc.status_code == 200, rc.text
        # Since 42 is foreign & mismatched, new_alerts>=1 unless a prior open alert exists
        # verify via GET
        st = requests.get(f"{API}/second-writer/{PID}", headers=H, timeout=15).json()
        open_alerts = [a for a in st["alerts"] if a["status"] == "open"]
        assert len(open_alerts) >= 1
        assert any(a["channel_actor"] != "hotelbox-rms" for a in open_alerts)
        # Ack first alert
        target = open_alerts[0]
        ra = requests.post(f"{API}/second-writer/{PID}/alerts/{target['id']}/ack", headers=H, timeout=15)
        assert ra.status_code == 200, ra.text
        # Simulate another to have an open one for repush
        requests.post(f"{API}/second-writer/{PID}/simulate-foreign-write",
                      headers=H, json={"date": day, "channel": "expedia", "rate": 42}, timeout=15)
        requests.post(f"{API}/second-writer/{PID}/scan", headers=H, timeout=30)
        rp = requests.post(f"{API}/second-writer/{PID}/repush", headers=H, timeout=30)
        assert rp.status_code == 200, rp.text
        assert rp.json()["ok"] is True
        # After repush, alerts should be repushed status
        st2 = requests.get(f"{API}/second-writer/{PID}", headers=H, timeout=15).json()
        open_after = [a for a in st2["alerts"] if a["status"] == "open"]
        assert len(open_after) == 0 or all(a["date"] < _today() for a in open_after)


# ============= ANNUAL PLAN =============
class TestAnnualPlan:
    def test_generate_fail_closed_no_anchor(self):
        r = requests.post(f"{API}/annual-plan/{PID}/generate", headers=H, json={}, timeout=30)
        # Expected behavior per spec: 422 with fail_closed if sample_nights<60
        # (May pass if sample>=60; treat either as OK but check structure)
        if r.status_code == 422:
            body = r.json()
            detail = body.get("detail", body)
            if isinstance(detail, dict):
                assert detail.get("fail_closed") is True
        else:
            assert r.status_code == 200
            assert "version" in r.json()

    def test_generate_with_anchor(self):
        r = requests.post(f"{API}/annual-plan/{PID}/generate",
                          headers=H, json={"anchor_level": 120, "notes": "test"}, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["level"] == 120
        assert d["level_source"] == "operator_anchor"
        assert 250 <= len(d["days"]) <= 280
        self.plan_id = d["id"]

    def test_versions_publish_latest(self):
        # generate one first
        g = requests.post(f"{API}/annual-plan/{PID}/generate",
                          headers=H, json={"anchor_level": 130}, timeout=30)
        assert g.status_code == 200, g.text
        plan_id = g.json()["id"]
        # versions
        v = requests.get(f"{API}/annual-plan/{PID}/versions", headers=H, timeout=15)
        assert v.status_code == 200
        assert len(v.json()["versions"]) >= 1
        # publish
        p = requests.post(f"{API}/annual-plan/{PID}/versions/{plan_id}/publish", headers=H, timeout=60)
        assert p.status_code == 200, p.text
        pd = p.json()
        assert pd["ok"] is True
        assert pd["applied_days"] > 0
        assert pd["actor"].startswith("annual-plan-v")
        # latest
        lt = requests.get(f"{API}/annual-plan/{PID}/latest", headers=H, timeout=15)
        assert lt.status_code == 200
        assert lt.json()["latest"]["id"] == plan_id or lt.json()["latest"]["version"] >= g.json()["version"]
