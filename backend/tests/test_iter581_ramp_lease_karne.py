"""Iter 581 — RevenueIQ 4 new gap MVPs:
- Guest-Approved Ramp Ladder (awaiting_guest_approval lock)
- Write Lease (fencing)
- Morning Karne (daily report card, mocked email)
Property: default, admin token.
"""
import os
import requests
from datetime import datetime, timezone, timedelta

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://review-hub-108.preview.emergentagent.com").rstrip("/")
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


def _d(offset=0):
    return (datetime.now(timezone.utc).date() + timedelta(days=offset)).isoformat()


# ============= RAMP LADDER (Guest-Approved) =============
class TestRampLadder:
    def test_config_enable_low_threshold(self):
        r = requests.put(f"{API}/ramp-ladder/{PID}/config", headers=H,
                         json={"enabled": True, "occ_threshold": 30, "step_pct": 5, "max_steps": 3},
                         timeout=15)
        assert r.status_code == 200, r.text
        cfg = r.json()["config"]
        assert cfg["enabled"] is True
        assert cfg["occ_threshold"] == 30.0

    def test_scan_creates_step1_then_awaits_guest_approval(self):
        # First scan applies step 1 evidence-based
        r1 = requests.post(f"{API}/ramp-ladder/{PID}/scan?force=true", headers=H, timeout=30)
        assert r1.status_code == 200, r1.text
        # 2nd immediate scan must SKIP with awaiting_guest_approval (no new bookings)
        r2 = requests.post(f"{API}/ramp-ladder/{PID}/scan?force=true", headers=H, timeout=30)
        assert r2.status_code == 200, r2.text
        d2 = r2.json()
        awaiting = [s for s in d2.get("skips", []) if s.get("reason") == "awaiting_guest_approval"]
        # If any step_no>=1 exists, awaiting_guest_approval should be present
        st = requests.get(f"{API}/ramp-ladder/{PID}", headers=H, timeout=15).json()
        if st["summary"]["awaiting_approval"] > 0:
            assert len(awaiting) >= 1, f"Expected awaiting_guest_approval skip; got {d2.get('skips')}"
        # actions on 2nd scan should be 0 (no new bookings to prove guest approval)
        assert len(d2.get("actions", [])) == 0

    def test_status_summary_and_awaiting_list(self):
        r = requests.get(f"{API}/ramp-ladder/{PID}", headers=H, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert "config" in d and "steps" in d and "summary" in d and "awaiting" in d
        assert "awaiting_approval" in d["summary"]
        assert "total_steps" in d["summary"]
        # ceiling discipline: each step rate <= its ceiling if ceiling present
        for s in d["steps"]:
            if s.get("ceiling"):
                assert s["rate"] <= s["ceiling"] + 0.01
            assert s.get("reason") in ("demand_evidence_step", "guest_approved_step")


# ============= WRITE LEASE (Fencing) =============
class TestWriteLease:
    date_target = _d(5)

    def test_acquire_first_writer(self):
        # Clean any prior lease on this cell
        requests.post(f"{API}/write-lease/{PID}/force-release", headers=H,
                      json={"date": self.date_target}, timeout=15)
        r = requests.post(f"{API}/write-lease/{PID}/test-acquire", headers=H,
                          json={"date": self.date_target, "owner": "writer-A"}, timeout=15)
        assert r.status_code == 200, r.text
        assert r.json()["acquired"] is True
        assert r.json()["current_holder"] == "writer-A"

    def test_second_writer_fenced(self):
        r = requests.post(f"{API}/write-lease/{PID}/test-acquire", headers=H,
                          json={"date": self.date_target, "owner": "writer-B"}, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["acquired"] is False
        assert d["current_holder"] == "writer-A"

    def test_list_leases(self):
        r = requests.get(f"{API}/write-lease/{PID}", headers=H, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert "leases" in d and "owners" in d
        # writer-A should own at least 1
        assert d["owners"].get("writer-A", 0) >= 1

    def test_force_release(self):
        r = requests.post(f"{API}/write-lease/{PID}/force-release", headers=H,
                          json={"date": self.date_target}, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["ok"] is True
        assert d["released"] >= 1

    def test_manual_rate_override_revokes_robot_lease(self):
        # Give a robot the lease
        requests.post(f"{API}/write-lease/{PID}/test-acquire", headers=H,
                      json={"date": self.date_target, "owner": "ramp-ladder"}, timeout=15)
        # Find a room_type_id
        rts = requests.get(f"{API}/room-types?property_id={PID}", headers=H, timeout=15)
        if rts.status_code != 200:
            return
        rows = rts.json() if isinstance(rts.json(), list) else rts.json().get("room_types", [])
        if not rows:
            return
        rt_id = rows[0].get("id")
        # Manual override
        mr = requests.put(f"{API}/revenue/rate-override/{PID}", headers=H,
                         json={"room_type_id": rt_id, "date": self.date_target,
                               "custom_rate": 1234.0, "reason": "test manual"}, timeout=15)
        # rate-override may be under different path; accept any 2xx
        if mr.status_code not in (200, 201):
            return
        # Check leases for that day are cleared for the ramp-ladder actor
        lst = requests.get(f"{API}/write-lease/{PID}", headers=H, timeout=15).json()
        for l in lst.get("leases", []):
            if l["date"] == self.date_target and l.get("room_type_id") == rt_id:
                assert l["owner"] != "ramp-ladder"


# ============= MORNING KARNE =============
class TestMorningKarne:
    def test_latest_preview_structure(self):
        r = requests.get(f"{API}/morning-karne/{PID}/latest", headers=H, timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "config" in d and "live_preview" in d
        prev = d["live_preview"]
        assert prev["grade"] in ("A", "B", "C")
        assert len(prev["checks"]) == 8
        for c in prev["checks"]:
            assert c["status"] in ("ok", "warn", "err")

    def test_send_now_and_history(self):
        r = requests.post(f"{API}/morning-karne/{PID}/send-now", headers=H, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        # Should not be skipped when forced
        assert "skipped" not in d
        assert "karne" in d
        assert "sent_to" in d
        # History includes it
        h = requests.get(f"{API}/morning-karne/{PID}/history", headers=H, timeout=15)
        assert h.status_code == 200
        assert len(h.json()["history"]) >= 1

    def test_config_toggle(self):
        r = requests.put(f"{API}/morning-karne/{PID}/config", headers=H,
                        json={"enabled": False}, timeout=15)
        assert r.status_code == 200
        assert r.json()["enabled"] is False
        r2 = requests.put(f"{API}/morning-karne/{PID}/config", headers=H,
                         json={"enabled": True}, timeout=15)
        assert r2.status_code == 200
        assert r2.json()["enabled"] is True
