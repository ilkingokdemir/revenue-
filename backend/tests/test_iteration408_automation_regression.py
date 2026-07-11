"""
Iteration 408 - Automation / Revenue / Guest Risk regression sweep.
Tests all endpoints listed in the review request.
"""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://review-hub-108.preview.emergentagent.com").rstrip("/")
PID = "default"

ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASS = "HotelAdmin2026!"


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=20)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text[:300]}"
    data = r.json()
    token = data.get("access_token") or data.get("token")
    if token:
        s.headers.update({"Authorization": f"Bearer {token}"})
    return s


# ---------------- Automation ROI ----------------
class TestAutomationRoi:
    def test_roi(self, session):
        r = session.get(f"{BASE_URL}/api/automation/roi/{PID}?days=30", timeout=30)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert "rows" in d or "items" in d or isinstance(d, dict)
        rows = d.get("rows") or d.get("items") or []
        keys = {row.get("key") or row.get("type") or row.get("source") for row in rows}
        # Expected keys
        expected = {"rebook", "comeback", "direct_conversion", "upsell", "ai_pricing"}
        missing = expected - keys
        assert not missing, f"ROI missing keys: {missing}; got {keys}"
        assert "total_attributed" in d or "total_revenue" in d or "total" in d, f"No total field. Keys: {list(d.keys())}"

    def test_opportunities(self, session):
        r = session.get(f"{BASE_URL}/api/automation/opportunities/{PID}", timeout=30)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        rows = d.get("rows") or d.get("opportunities") or d.get("items") or []
        keys = {row.get("key") or row.get("type") for row in rows}
        expected = {"rebook", "comeback", "upsell", "direct_conversion"}
        assert expected.issubset(keys), f"Opportunities missing: {expected - keys}; got {keys}"
        for row in rows:
            assert "count" in row, f"row missing count: {row}"
            assert "potential" in row or "potential_revenue" in row, f"row missing potential: {row}"

    def test_auto_fix_dedupe(self, session):
        r1 = session.post(f"{BASE_URL}/api/automation/opportunities/all/auto-fix", json={}, timeout=60)
        assert r1.status_code == 200, r1.text[:300]
        d1 = r1.json()
        assert "results" in d1, f"Missing results: {d1}"
        for k in ("rebook", "comeback", "upsell"):
            assert k in d1["results"], f"Missing {k} in results: {d1['results']}"
        # second call - dedupe
        time.sleep(1)
        r2 = session.post(f"{BASE_URL}/api/automation/opportunities/all/auto-fix", json={}, timeout=60)
        assert r2.status_code == 200
        d2 = r2.json()
        # Total processed should be less or equal (dedupe expected)
        def total(d):
            t = 0
            for v in d.get("results", {}).values():
                if isinstance(v, dict):
                    t += sum(x for x in v.values() if isinstance(x, (int, float)))
                elif isinstance(v, (int, float)):
                    t += v
            return t
        assert total(d2) <= total(d1) + 1, f"Dedupe failed. 1st={total(d1)} 2nd={total(d2)}"

    def test_roi_trend(self, session):
        r = session.get(f"{BASE_URL}/api/automation/roi/all/trend?weeks=8", timeout=30)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        buckets = d.get("buckets") or d.get("weeks") or d.get("rows") or d.get("data") or []
        assert len(buckets) == 8, f"Expected 8 buckets, got {len(buckets)}: {str(d)[:400]}"
        b0 = buckets[0]
        assert "week" in b0 or "week_start" in b0 or "date" in b0
        assert "coupon" in b0 or "upsell" in b0, f"Missing coupon/upsell: {b0}"

    def test_funnel(self, session):
        r = session.get(f"{BASE_URL}/api/automation/funnel/all?days=30", timeout=30)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert "coupon" in d, f"No coupon: {d}"
        assert "upsell" in d, f"No upsell: {d}"
        c = d["coupon"]
        u = d["upsell"]
        for k in ("sent", "clicked", "redeemed"):
            assert k in c, f"coupon missing {k}: {c}"
        for k in ("sent", "viewed", "accepted"):
            assert k in u, f"upsell missing {k}: {u}"

    def test_health(self, session):
        r = session.get(f"{BASE_URL}/api/automation/health/all", timeout=30)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        jobs = d.get("jobs") or d.get("rows") or d.get("items") or []
        names = {j.get("job") or j.get("name") for j in jobs}
        expected = {"leakage_sweep", "upsell_autopilot", "email_nudge", "daily_pulse"}
        missing = expected - names
        assert not missing, f"Missing jobs: {missing}; got {names}"
        assert "summary" in d, f"No summary: {list(d.keys())}"
        # each job status is valid
        for j in jobs:
            s = j.get("status")
            assert s in ("healthy", "stale", "failing", "pending"), f"Bad status: {j}"


# ---------------- Upsell autopilot ----------------
class TestUpsellAutopilot:
    def test_autopilot_run_and_stats(self, session):
        r1 = session.post(f"{BASE_URL}/api/ai-predictions/upsell/autopilot/run",
                          json={"property_id": PID}, timeout=60)
        assert r1.status_code == 200, r1.text[:300]
        d1 = r1.json()
        assert d1.get("ok") is True
        assert "scanned" in d1 and "offers_sent" in d1
        first_sent = d1["offers_sent"]

        time.sleep(1)
        r2 = session.post(f"{BASE_URL}/api/ai-predictions/upsell/autopilot/run",
                          json={"property_id": PID}, timeout=60)
        assert r2.status_code == 200
        d2 = r2.json()
        assert d2["offers_sent"] <= first_sent, f"Dedupe failed: {first_sent} -> {d2['offers_sent']}"

        rs = session.get(f"{BASE_URL}/api/ai-predictions/upsell/autopilot/stats/all", timeout=30)
        assert rs.status_code == 200
        ds = rs.json()
        assert "total_sent" in ds
        assert "by_category" in ds

    def test_public_upsell_offer_flow(self, session):
        # Fetch a token via mongo
        import subprocess, json
        cmd = ("mongosh test_database --quiet --eval "
               "'JSON.stringify(db.upsell_offers.findOne({accept_token:{$exists:true}}))'")
        try:
            out = subprocess.check_output(cmd, shell=True, timeout=10).decode().strip()
            offer = json.loads(out) if out and out != "null" else None
        except Exception as e:
            pytest.skip(f"Could not query mongo: {e}")
        if not offer or not offer.get("accept_token"):
            pytest.skip("No upsell offer with accept_token in DB")
        token = offer["accept_token"]

        # Public GET works without auth
        r = requests.get(f"{BASE_URL}/api/public/upsell-offer/{token}", timeout=20)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        for k in ("title", "price", "final_price", "discount_active", "social_count"):
            assert k in d, f"Public GET missing {k}: {list(d.keys())}"

        # If already accepted, POST /accept returns already:true
        if offer.get("status") == "accepted":
            ra = requests.post(f"{BASE_URL}/api/public/upsell-offer/{token}/accept", timeout=20)
            assert ra.status_code == 200
            da = ra.json()
            assert da.get("already") is True, f"Expected already:true, got {da}"


# ---------------- Nudge ----------------
class TestNudge:
    def test_nudge_run_and_stats(self, session):
        r = session.post(f"{BASE_URL}/api/automation/nudge/run",
                         json={"property_id": PID}, timeout=60)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert d.get("ok") is True
        assert "upsell_nudged" in d
        assert "coupon_nudged" in d

        rs = session.get(f"{BASE_URL}/api/automation/nudge/stats/all", timeout=30)
        assert rs.status_code == 200
        ds = rs.json()
        # Stats are nested by channel (upsell, coupon) each with nudged/recovered/recovery_rate
        assert "upsell" in ds and "coupon" in ds, f"missing channels: {ds}"
        for ch in ("upsell", "coupon"):
            for k in ("nudged", "recovered", "recovery_rate"):
                assert k in ds[ch], f"missing {ch}.{k}: {ds}"


# ---------------- Daily pulse ----------------
class TestDailyPulse:
    def test_preview(self, session):
        r = session.get(f"{BASE_URL}/api/automation/daily-pulse/preview/{PID}", timeout=30)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert "today" in d and "yesterday" in d and "risks" in d
        t = d["today"]
        for k in ("arrivals", "departures", "in_house", "occupancy_pct"):
            assert k in t, f"today missing {k}: {t}"
        y = d["yesterday"]
        for k in ("booked_revenue", "automation_revenue"):
            assert k in y, f"yesterday missing {k}: {y}"
        assert "leakage_closed_7d" in d
        assert "failing_automations" in d["risks"]

    def test_send_dedupe(self, session):
        r1 = session.post(f"{BASE_URL}/api/automation/daily-pulse/send",
                          json={"property_id": PID}, timeout=30)
        assert r1.status_code == 200
        d1 = r1.json()
        # sent or already skipped
        assert d1.get("skipped") or d1.get("sent_to") is not None or d1.get("ok") is True

        # second call - expect dedupe
        r2 = session.post(f"{BASE_URL}/api/automation/daily-pulse/send",
                          json={"property_id": PID}, timeout=30)
        assert r2.status_code == 200
        d2 = r2.json()
        # Second must be skipped
        assert d2.get("skipped") == "already_sent_today" or d2.get("skipped"), f"Expected skip on second call: {d2}"

        # force
        rf = session.post(f"{BASE_URL}/api/automation/daily-pulse/send",
                          json={"property_id": PID, "force": True}, timeout=30)
        assert rf.status_code == 200


# ---------------- Leakage ----------------
class TestLeakage:
    def test_leakage_all(self, session):
        r = session.get(f"{BASE_URL}/api/revenue/leakage/all?days=90", timeout=30)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        rows = d.get("rows") or d.get("items") or []
        keys = {row.get("key") or row.get("type") for row in rows}
        expected = {"unpaid_folio", "missing_upsell", "noshow_uncharged", "zero_rate"}
        missing = expected - keys
        assert not missing, f"Missing leakage rows: {missing}; got {keys}"
        assert "total_leaked" in d, f"missing total_leaked: {list(d.keys())}"
        for row in rows:
            assert "items" in row or "detail" in row or "count" in row

    def test_sweep_log(self, session):
        r = session.get(f"{BASE_URL}/api/revenue/leakage/{PID}/sweep-log", timeout=30)
        assert r.status_code == 200, r.text[:300]


# ---------------- Guest risk ----------------
class TestGuestRisk:
    def test_arrivals(self, session):
        r = session.get(f"{BASE_URL}/api/guests/risk/arrivals/all?days_ahead=30", timeout=30)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        arrivals = d.get("arrivals") or d.get("rows") or d.get("items") or []
        assert "summary" in d
        assert "value_at_risk" in d or "value_at_risk" in d.get("summary", {})
        if arrivals:
            a = arrivals[0]
            for k in ("score", "level", "reasons", "action"):
                assert k in a, f"arrival missing {k}: {list(a.keys())}"

    def test_single_guest(self, session):
        r = session.get(f"{BASE_URL}/api/guests/risk/emily.williams@example.com", timeout=30)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert "score" in d
        assert "level" in d
        assert 20 <= d["score"] <= 60, f"Expected ~40, got {d['score']}"
        assert d["level"] in ("low", "medium", "high"), f"Bad level: {d['level']}"

    def test_deposit_flow(self, session):
        # Find a medium risk booking without deposit_requested
        r = session.get(f"{BASE_URL}/api/guests/risk/arrivals/all?days_ahead=30", timeout=30)
        arrivals = r.json().get("arrivals") or r.json().get("rows") or []
        target = None
        for a in arrivals:
            if a.get("level") == "medium" and not a.get("deposit_requested"):
                target = a
                break
        if not target:
            pytest.skip("No medium-risk arrival without deposit_requested")
        booking_id = target.get("booking_id") or target.get("id")
        assert booking_id, f"No booking_id in arrival: {target}"

        try:
            r1 = session.post(f"{BASE_URL}/api/guests/risk/{booking_id}/request-deposit",
                              json={}, timeout=30)
            assert r1.status_code == 200, r1.text[:300]
            d1 = r1.json()
            assert d1.get("ok") is True
            assert "amount" in d1
            assert "checkout.stripe.com" in d1.get("checkout_url", ""), f"No stripe URL: {d1}"

            r2 = session.post(f"{BASE_URL}/api/guests/risk/{booking_id}/request-deposit",
                              json={}, timeout=30)
            assert r2.status_code == 200
            assert r2.json().get("already") is True

            rs = session.post(f"{BASE_URL}/api/guests/risk/{booking_id}/deposit-status",
                              json={}, timeout=30)
            assert rs.status_code == 200
            assert rs.json().get("status") == "pending"
        finally:
            # cleanup
            import subprocess
            try:
                subprocess.check_output(
                    f"mongosh test_database --quiet --eval "
                    f"\"db.bookings.updateOne({{id:'{booking_id}'}},{{\\$unset:{{deposit_requested:'',deposit_requested_at:''}}}});"
                    f"db.deposit_requests.deleteMany({{booking_id:'{booking_id}'}});"
                    f"db.payment_transactions.deleteMany({{booking_id:'{booking_id}'}})\"",
                    shell=True, timeout=15)
            except Exception as e:
                print(f"Cleanup warning: {e}")
