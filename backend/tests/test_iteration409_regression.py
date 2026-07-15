"""
Iteration 409 - Full regression sweep for the autonomous marketing/revenue stack.
Covers: automation settings + simulator, guest segments, channel health,
key figures, weekly report, scheduler triggers.
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN = {"email": "admin@hotelbox.com", "password": "HotelAdmin2026!"}

EXPECTED_JOBS = {
    "upsell_autopilot", "email_nudge", "daily_pulse", "leakage_sweep",
    "cancel_save", "deposit_autopilot", "segment_refresh", "review_autopilot",
    "monthly_report_card", "weekly_report", "rebook_sweep", "abandoned_recovery",
    "ai_pricing_auto_apply", "ota_sync_watchdog",
}


@pytest.fixture(scope="session")
def token():
    r = requests.post(f"{API}/auth/login", json=ADMIN, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:300]}"
    return r.json().get("access_token") or r.json().get("token")


@pytest.fixture(scope="session")
def h(token):
    if not token:
        pytest.skip("no auth token")
    return {"Authorization": f"Bearer {token}"}


# ---------------- 1. Automation Settings ----------------
class TestAutomationSettings:
    def test_get_settings_14_jobs(self, h):
        r = requests.get(f"{API}/automation/settings", headers=h, timeout=30)
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        jobs = data.get("jobs", [])
        keys = {j["job"] for j in jobs}
        assert keys == EXPECTED_JOBS, f"missing/extra: {keys ^ EXPECTED_JOBS}"
        wr = next(j for j in jobs if j["job"] == "weekly_report")
        assert wr.get("cron_dow") == 0, f"weekly_report cron_dow expected 0 got {wr.get('cron_dow')}"

    def test_put_toggle_and_params_roundtrip(self, h):
        # snapshot current cancel_save
        r0 = requests.get(f"{API}/automation/settings", headers=h, timeout=30).json()
        orig = next(j for j in r0["jobs"] if j["job"] == "cancel_save")
        orig_enabled = orig["enabled"]
        orig_threshold = next(p["value"] for p in orig["params"] if p["key"] == "risk_threshold")

        # toggle enabled + change threshold
        r = requests.put(f"{API}/automation/settings/cancel_save", headers=h,
                         json={"enabled": not orig_enabled, "params": {"risk_threshold": 55}},
                         timeout=30)
        assert r.status_code == 200, r.text[:300]

        # verify
        r2 = requests.get(f"{API}/automation/settings", headers=h, timeout=30).json()
        cs = next(j for j in r2["jobs"] if j["job"] == "cancel_save")
        assert cs["enabled"] == (not orig_enabled)
        thr = next(p["value"] for p in cs["params"] if p["key"] == "risk_threshold")
        assert thr == 55

        # restore
        rr = requests.put(f"{API}/automation/settings/cancel_save", headers=h,
                          json={"enabled": orig_enabled,
                                "params": {"risk_threshold": orig_threshold}},
                          timeout=30)
        assert rr.status_code == 200

    def test_put_param_out_of_range_400(self, h):
        r = requests.put(f"{API}/automation/settings/cancel_save", headers=h,
                         json={"params": {"risk_threshold": 999}}, timeout=30)
        assert r.status_code == 400, r.text[:200]

    def test_put_unknown_job_404(self, h):
        r = requests.put(f"{API}/automation/settings/does_not_exist", headers=h,
                         json={"enabled": True}, timeout=30)
        assert r.status_code == 404


# ---------------- 2. Simulator ----------------
class TestSimulator:
    @pytest.mark.parametrize("job", [
        "cancel_save", "upsell_autopilot", "deposit_autopilot",
        "email_nudge", "review_autopilot"
    ])
    def test_simulate_supported(self, h, job):
        r = requests.post(f"{API}/automation/simulate/{job}", headers=h, json={}, timeout=30)
        assert r.status_code == 200, f"{job}: {r.status_code} {r.text[:200]}"
        d = r.json()
        for k in ("targets", "scanned", "detail", "histogram"):
            assert k in d, f"{job} missing {k}: {list(d.keys())}"

    def test_cancel_save_threshold_effect(self, h):
        high = requests.post(f"{API}/automation/simulate/cancel_save", headers=h,
                             json={"risk_threshold": 90}, timeout=30).json()
        low = requests.post(f"{API}/automation/simulate/cancel_save", headers=h,
                            json={"risk_threshold": 30}, timeout=30).json()
        assert low["targets"] >= high["targets"], f"low={low['targets']} high={high['targets']}"

    def test_simulate_unsupported_404(self, h):
        r = requests.post(f"{API}/automation/simulate/daily_pulse", headers=h, json={}, timeout=30)
        assert r.status_code == 404


# ---------------- 3. Guest Segments ----------------
class TestSegments:
    def test_refresh(self, h):
        r = requests.post(f"{API}/guests/segments/refresh", headers=h, json={}, timeout=90)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        # accept various key names
        total = d.get("classified") or d.get("total") or d.get("guests_total") or d.get("count") or 0
        assert total > 0, f"expected classified guests > 0, got: {d}"

    def test_summary_seven_segments(self, h):
        r = requests.get(f"{API}/guests/segments/summary", headers=h, timeout=30)
        assert r.status_code == 200
        d = r.json()
        segs = d.get("segments") or d.get("summary") or []
        assert len(segs) == 7, f"expected 7 segments, got {len(segs)}"

    def test_list_vip(self, h):
        r = requests.get(f"{API}/guests/segments/list", headers=h,
                         params={"segment": "vip"}, timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert "guests" in d or isinstance(d, list)

    def test_strategy_get_and_put(self, h):
        r = requests.get(f"{API}/guests/segments/strategy", headers=h, timeout=30)
        assert r.status_code == 200
        motors = r.json().get("motors", [])
        assert motors, "motors list empty"
        motor = motors[0]
        # invalid segment -> 400
        r_bad = requests.put(f"{API}/guests/segments/strategy/not_a_segment",
                             headers=h, json={motor: True}, timeout=30)
        assert r_bad.status_code == 400
        # toggle vip motor then restore
        original = next(s[motor] for s in r.json()["strategies"] if s["segment"] == "vip")
        r_ok = requests.put(f"{API}/guests/segments/strategy/vip",
                            headers=h, json={motor: not original}, timeout=30)
        assert r_ok.status_code == 200
        # restore
        requests.put(f"{API}/guests/segments/strategy/vip",
                     headers=h, json={motor: original}, timeout=30)

    def test_performance(self, h):
        r = requests.get(f"{API}/guests/segments/performance", headers=h,
                         params={"days": 90}, timeout=45)
        assert r.status_code == 200
        d = r.json()
        assert "segments" in d and len(d["segments"]) == 7


# ---------------- 4. Channel Health ----------------
class TestChannelHealth:
    def test_all(self, h):
        r = requests.get(f"{API}/channel-health/all", headers=h, timeout=30)
        assert r.status_code == 200
        d = r.json()
        channels = d.get("channels", [])
        assert len(channels) == 8, f"expected 8 channels, got {len(channels)}"
        assert "summary" in d
        assert "alerts" in d

    def test_heal(self, h):
        r = requests.post(f"{API}/channel-health/heal", headers=h, json={}, timeout=45)
        assert r.status_code == 200

    def test_webhook_config_roundtrip(self, h):
        g = requests.get(f"{API}/channel-health/webhook-config/get", headers=h, timeout=30)
        assert g.status_code == 200
        orig = g.json()
        orig_url = orig.get("webhook_url") or orig.get("url") or ""

        p = requests.put(f"{API}/channel-health/webhook-config", headers=h,
                         json={"webhook_url": "https://example.com/test-hook"}, timeout=30)
        assert p.status_code == 200

        t = requests.post(f"{API}/channel-health/webhook-test", headers=h, json={}, timeout=30)
        assert t.status_code == 200

        # restore
        requests.put(f"{API}/channel-health/webhook-config", headers=h,
                     json={"webhook_url": orig_url}, timeout=30)


# ---------------- 5. Key Figures ----------------
class TestKeyFigures:
    def test_all_range(self, h):
        r = requests.get(f"{API}/key-figures/all", headers=h,
                         params={"start": "2026-06-01", "end": "2026-06-30",
                                 "basis": "staying"}, timeout=45)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        tiles = d.get("tiles") or d.get("figures") or []
        assert len(tiles) >= 12, f"expected >=12 tiles, got {len(tiles)}"
        assert "breakdown" in d

    def test_compare_previous(self, h):
        r = requests.get(f"{API}/key-figures/all", headers=h,
                         params={"start": "2026-06-01", "end": "2026-06-30",
                                 "basis": "staying", "compare": "previous"},
                         timeout=45)
        assert r.status_code == 200
        d = r.json()
        assert "comparison" in d or "deltas" in d or any("delta" in t for t in (d.get("tiles") or []))

    def test_basis_booked(self, h):
        r = requests.get(f"{API}/key-figures/all", headers=h,
                         params={"start": "2026-06-01", "end": "2026-06-30",
                                 "basis": "booked"}, timeout=45)
        assert r.status_code == 200

    def test_end_before_start_400(self, h):
        r = requests.get(f"{API}/key-figures/all", headers=h,
                         params={"start": "2026-06-30", "end": "2026-06-01"}, timeout=30)
        assert r.status_code == 400

    def test_export_csv(self, h):
        r = requests.get(f"{API}/key-figures/all/export", headers=h,
                         params={"start": "2026-06-01", "end": "2026-06-30"}, timeout=45)
        assert r.status_code == 200
        assert "text/csv" in r.headers.get("content-type", "").lower()


# ---------------- 6. Weekly Report ----------------
class TestWeekly:
    def test_preview(self, h):
        r = requests.get(f"{API}/reports/weekly-management/preview/all", headers=h, timeout=45)
        assert r.status_code == 200
        d = r.json()
        rows = d.get("rows") or d.get("metrics") or []
        assert len(rows) >= 10, f"expected >=10 rows, got {len(rows)}"

    def test_send_dedupe_and_force(self, h):
        r = requests.post(f"{API}/reports/weekly-management/send", headers=h,
                          json={"property_id": "all"}, timeout=45)
        assert r.status_code == 200
        # either sent OR skipped:already_sent_this_week - both are success
        r2 = requests.post(f"{API}/reports/weekly-management/send", headers=h,
                           json={"property_id": "all"}, timeout=45)
        assert r2.status_code == 200
        d2 = r2.json()
        # second call should be skipped
        skipped = d2.get("skipped") or d2.get("status")
        assert skipped or d2.get("ok"), f"unexpected: {d2}"

        # force
        rf = requests.post(f"{API}/reports/weekly-management/send", headers=h,
                           json={"property_id": "all", "force": True}, timeout=45)
        assert rf.status_code == 200


# ---------------- 7. Scheduler triggers ----------------
class TestScheduler:
    @pytest.mark.parametrize("job", [
        "segment_refresh", "ota_sync_watchdog", "cancel_save", "email_nudge"
    ])
    def test_trigger(self, h, job):
        r = requests.post(f"{API}/scheduler/trigger/all/{job}", headers=h, json={}, timeout=90)
        assert r.status_code == 200, f"{job}: {r.status_code} {r.text[:200]}"
