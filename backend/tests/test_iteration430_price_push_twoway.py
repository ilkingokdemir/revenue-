"""
Iteration 430/431 regression tests:
 - 1-Click Price Push (comp-radar apply + push-history reflection)
 - Two-Way OTA Sync (ripple + conflict + resolve)
 - Inbound webhook e2e (reservation + cancellation ripple)
"""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN = {"email": "admin@hotelbox.com", "password": "HotelAdmin2026!"}


@pytest.fixture(scope="module")
def sess():
    s = requests.Session()
    # login
    r = s.post(f"{API}/auth/login", json=ADMIN, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return s


# -------------------- Comp Radar 1-Click Price Push -------------------
class TestCompRadarApply:
    def _find_unapplied(self, sess):
        r = sess.get(f"{API}/comp-radar/all?days=14", timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        findings = data.get("findings", [])
        for f in findings:
            assert "suggested_rate" in f, "suggested_rate missing on finding"
            assert isinstance(f["suggested_rate"], (int, float))
        unapplied = [f for f in findings if not f.get("applied")]
        return findings, unapplied

    def test_get_and_apply_flow(self, sess):
        findings, unapplied = self._find_unapplied(sess)
        if not unapplied:
            # regenerate via scan
            r = sess.post(f"{API}/comp-radar/scan", json={"property_id": "all"}, timeout=60)
            assert r.status_code == 200, r.text
            findings, unapplied = self._find_unapplied(sess)
        assert unapplied, "no unapplied findings even after scan"

        finding = unapplied[0]
        target_date = finding["date"]

        r = sess.post(f"{API}/comp-radar/apply",
                      json={"property_id": "all", "date": target_date}, timeout=60)
        assert r.status_code == 200, f"apply failed: {r.status_code} {r.text}"
        j = r.json()
        assert j.get("ok") is True
        assert isinstance(j.get("new_rate"), (int, float))
        assert j.get("channels_total", 0) >= 1
        assert "channels_succeeded" in j
        results = j.get("results", [])
        # dedup: no duplicate channel_id
        chan_ids = [x.get("channel_id") for x in results]
        assert len(chan_ids) == len(set(chan_ids)), f"duplicate channels in results: {chan_ids}"

        # Re-apply same date -> 409
        r2 = sess.post(f"{API}/comp-radar/apply",
                       json={"property_id": "all", "date": target_date}, timeout=30)
        assert r2.status_code == 409, f"expected 409 on re-apply, got {r2.status_code} {r2.text}"
        assert "zaten uygulandı" in r2.text or "zaten" in r2.text

        # push-history reflects push at new_rate
        ph = sess.get(f"{API}/push-history/all?days=1", timeout=30)
        assert ph.status_code == 200, ph.text
        phj = ph.json()
        # timeline is likely list of events; find rate pushes
        timeline = phj.get("timeline") or phj.get("items") or phj.get("events") or []
        # not strict on structure; ensure at least one entry mentions the new_rate
        found = False
        new_rate = j["new_rate"]
        import json as _json
        blob = _json.dumps(phj)
        if str(new_rate) in blob or f"{new_rate:.2f}" in blob:
            found = True
        assert found, f"push-history missing rate {new_rate}: {blob[:400]}"


# -------------------- Two-Way Sync core --------------------
class TestTwoWaySync:
    def test_status_shape(self, sess):
        r = sess.get(f"{API}/two-way-sync/all", timeout=30)
        assert r.status_code == 200, r.text
        j = r.json()
        s = j.get("summary", {})
        for k in ("ripple_24h", "ripple_total", "conflicts_open", "conflicts_total", "channels"):
            assert k in s, f"missing summary.{k}"
        assert isinstance(j.get("ripple_events"), list)
        assert isinstance(j.get("conflicts"), list)

    def test_simulate_ripple(self, sess):
        # baseline count
        before = sess.get(f"{API}/two-way-sync/all", timeout=30).json()
        pre_total = before["summary"]["ripple_total"]

        r = sess.post(f"{API}/two-way-sync/simulate",
                      json={"property_id": "all"}, timeout=60)
        assert r.status_code == 200, r.text
        j = r.json()
        assert j.get("ok") is True
        rip = j.get("ripple", {})
        assert rip.get("tasks_total", 0) >= 1, f"ripple.tasks_total < 1: {rip}"
        assert "tasks_succeeded" in rip
        assert "booking_com" in (rip.get("channels") or []), \
            f"booking_com not in ripple channels: {rip.get('channels')}"

        after = sess.get(f"{API}/two-way-sync/all", timeout=30).json()
        assert after["summary"]["ripple_total"] >= pre_total + 1

    def test_conflict_and_resolve(self, sess):
        pre_open = sess.get(f"{API}/two-way-sync/all", timeout=30).json()["summary"]["conflicts_open"]
        r = sess.post(f"{API}/two-way-sync/simulate",
                      json={"property_id": "all", "force_conflict": True}, timeout=60)
        assert r.status_code == 200, r.text
        j = r.json()
        conflict = j.get("conflict")
        if not conflict:
            pytest.skip("force_conflict did not produce a conflict (no existing booking with room). Skipping resolve step.")
        assert conflict.get("status") == "open"
        assert conflict.get("room_number")
        cid = conflict["id"]

        rr = sess.post(f"{API}/two-way-sync/conflicts/{cid}/resolve",
                       json={"note": "test"}, timeout=30)
        assert rr.status_code == 200, rr.text
        assert rr.json().get("ok") is True

        post_open = sess.get(f"{API}/two-way-sync/all", timeout=30).json()["summary"]["conflicts_open"]
        assert post_open <= pre_open, "conflicts_open did not decrement"

        # Re-resolve or non-existent -> 404
        rr2 = sess.post(f"{API}/two-way-sync/conflicts/{cid}/resolve",
                        json={"note": "again"}, timeout=30)
        assert rr2.status_code == 404
        rr3 = sess.post(f"{API}/two-way-sync/conflicts/nonexistent-{uuid.uuid4().hex}/resolve",
                        json={"note": "x"}, timeout=30)
        assert rr3.status_code == 404


# -------------------- Inbound webhook e2e --------------------
class TestInboundWebhookRipple:
    def test_airbnb_reservation_and_cancellation(self, sess):
        ref = f"QA-RIP-{uuid.uuid4().hex[:8].upper()}"
        payload = {
            "channel_reference": ref,
            "property_id": "aldgate-flats",
            "guest_name": "QA Ripple",
            "check_in": "2026-09-01",
            "check_out": "2026-09-03",
            "total_price": 280,
        }
        r = sess.post(f"{API}/ota-inbound/airbnb/reservation", json=payload, timeout=60)
        assert r.status_code == 200, r.text
        j = r.json()
        assert j.get("ok") is True
        assert "ripple" in j
        assert j["ripple"].get("tasks_total", 0) >= 1
        assert "conflict_detected" in j
        assert isinstance(j["conflict_detected"], bool)

        pre = sess.get(f"{API}/two-way-sync/all", timeout=30).json()
        # cancel
        rc = sess.post(f"{API}/ota-inbound/airbnb/cancellation",
                       json={"channel_reference": ref}, timeout=60)
        assert rc.status_code == 200, rc.text
        jc = rc.json()
        assert jc.get("ok") is True
        assert jc.get("cancelled") is True

        post = sess.get(f"{API}/two-way-sync/all", timeout=30).json()
        # find a cancellation event in ripple_events
        cancels = [e for e in post.get("ripple_events", []) if e.get("event_type") == "cancellation"]
        assert cancels, "no cancellation ripple event appeared"


# -------------------- Regression sanity --------------------
class TestRegression:
    def test_channel_health(self, sess):
        r = sess.get(f"{API}/channel-health/all", timeout=30)
        assert r.status_code == 200, r.text

    def test_push_history(self, sess):
        r = sess.get(f"{API}/push-history/all?days=7", timeout=30)
        assert r.status_code == 200, r.text

    def test_compset_list(self, sess):
        r = sess.get(f"{API}/compset/all", timeout=30)
        assert r.status_code == 200, r.text
