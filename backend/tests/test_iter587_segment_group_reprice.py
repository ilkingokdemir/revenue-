"""Iteration 587: Segment pricing, Group approval, Reprice bridge, Lost demand feeding reprice."""
import os
import uuid
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://review-hub-108.preview.emergentagent.com").rstrip("/")
PID = "default"


@pytest.fixture(scope="session")
def token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": "admin@hotelbox.com", "password": "HotelAdmin2026!"}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json().get("token") or r.json().get("access_token")


@pytest.fixture(scope="session")
def client(token):
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    return s


# ---- Segment Pricing ----
class TestSegmentPricing:
    def test_get_default_segments(self, client):
        r = client.get(f"{BASE_URL}/api/segment-pricing/{PID}?date=2026-03-15")
        assert r.status_code == 200, r.text
        data = r.json()
        assert "segments" in data and "base_rate" in data
        codes = [s["code"] for s in data["segments"]]
        for c in ("direct", "corporate", "loyalty", "ota"):
            assert c in codes, f"missing segment {c}"
        # rates computed when base_rate present
        if data["base_rate"]:
            for s in data["segments"]:
                assert s.get("rate") is not None

    def test_put_and_persist(self, client):
        new_segs = [
            {"code": "direct", "name": "Direkt", "offset_pct": 0, "active": True},
            {"code": "corporate", "name": "Kurumsal", "offset_pct": -15, "active": True},
            {"code": "loyalty", "name": "Sadakat", "offset_pct": -7, "active": True},
            {"code": "ota", "name": "OTA", "offset_pct": 4, "active": True},
        ]
        r = client.put(f"{BASE_URL}/api/segment-pricing/{PID}", json={"segments": new_segs})
        assert r.status_code == 200, r.text
        r2 = client.get(f"{BASE_URL}/api/segment-pricing/{PID}")
        assert r2.status_code == 200
        got = {s["code"]: s["offset_pct"] for s in r2.json()["segments"]}
        assert got["corporate"] == -15
        assert got["ota"] == 4

    def test_offset_clamp(self, client):
        r = client.put(f"{BASE_URL}/api/segment-pricing/{PID}",
                       json={"segments": [{"code": "x", "name": "X", "offset_pct": 999, "active": True}]})
        assert r.status_code == 200
        clean = r.json()["segments"]
        assert clean[0]["offset_pct"] == 50.0
        # negative clamp
        r2 = client.put(f"{BASE_URL}/api/segment-pricing/{PID}",
                        json={"segments": [{"code": "y", "name": "Y", "offset_pct": -999, "active": True}]})
        assert r2.json()["segments"][0]["offset_pct"] == -50.0
        # restore defaults
        client.put(f"{BASE_URL}/api/segment-pricing/{PID}", json={"segments": [
            {"code": "direct", "name": "Direkt", "offset_pct": 0, "active": True},
            {"code": "corporate", "name": "Kurumsal", "offset_pct": -10, "active": True},
            {"code": "loyalty", "name": "Sadakat", "offset_pct": -5, "active": True},
            {"code": "ota", "name": "OTA", "offset_pct": 3, "active": True},
        ]})

    def test_put_empty_rejected(self, client):
        r = client.put(f"{BASE_URL}/api/segment-pricing/{PID}", json={"segments": []})
        assert r.status_code == 422


# ---- Group Approval ----
class TestGroupApproval:
    quote_id = None

    def test_validation_walk_gt_wish_rejected(self, client):
        r = client.post(f"{BASE_URL}/api/group-approval/{PID}/quotes",
                        json={"group_name": "TEST_bad", "rooms": 5, "nights": 2,
                              "check_in": "2026-05-01", "wish_price": 90, "walk_price": 120})
        assert r.status_code == 422

    def test_validation_zero_rejected(self, client):
        r = client.post(f"{BASE_URL}/api/group-approval/{PID}/quotes",
                        json={"group_name": "TEST_zero", "wish_price": 100, "walk_price": 0})
        assert r.status_code == 422

    def test_full_chain(self, client):
        r = client.post(f"{BASE_URL}/api/group-approval/{PID}/quotes",
                        json={"group_name": f"TEST_grp_{uuid.uuid4().hex[:6]}",
                              "rooms": 10, "nights": 3, "check_in": "2026-06-10",
                              "wish_price": 150, "walk_price": 110})
        assert r.status_code == 200, r.text
        q = r.json()
        assert q["status"] == "pending_revenue"
        assert q["wish_total"] == round(150 * 10 * 3, 2)
        qid = q["id"]
        TestGroupApproval.quote_id = qid

        # Out-of-order: sales before revenue
        r_bad = client.post(f"{BASE_URL}/api/group-approval/{PID}/quotes/{qid}/approve",
                            json={"role": "sales"})
        assert r_bad.status_code == 422

        # Revenue approval
        r1 = client.post(f"{BASE_URL}/api/group-approval/{PID}/quotes/{qid}/approve",
                         json={"role": "revenue"})
        assert r1.status_code == 200
        assert r1.json()["status"] == "pending_sales"

        # Sales approval
        r2 = client.post(f"{BASE_URL}/api/group-approval/{PID}/quotes/{qid}/approve",
                         json={"role": "sales"})
        assert r2.status_code == 200
        assert r2.json()["status"] == "approved"

        # Rejecting approved quote must 404
        r3 = client.post(f"{BASE_URL}/api/group-approval/{PID}/quotes/{qid}/reject",
                         json={"reason": "late"})
        assert r3.status_code == 404

    def test_reject_pending(self, client):
        r = client.post(f"{BASE_URL}/api/group-approval/{PID}/quotes",
                        json={"group_name": "TEST_reject", "rooms": 3, "nights": 2,
                              "check_in": "2026-07-01", "wish_price": 100, "walk_price": 80})
        qid = r.json()["id"]
        rj = client.post(f"{BASE_URL}/api/group-approval/{PID}/quotes/{qid}/reject",
                         json={"reason": "budget"})
        assert rj.status_code == 200


# ---- Reprice Bridge ----
class TestRepriceBridge:
    def test_manual_trigger(self, client):
        r = client.post(f"{BASE_URL}/api/reprice-bridge/{PID}/trigger")
        assert r.status_code == 200, r.text
        assert r.json().get("ok") is True

    def test_list_events(self, client):
        r = client.get(f"{BASE_URL}/api/reprice-bridge/{PID}/events")
        assert r.status_code == 200
        data = r.json()
        assert "events" in data
        if data["events"]:
            ev = data["events"][0]
            assert "reason" in ev and "latency_ms" in ev

    def test_booking_create_fires_event(self, client):
        # Create a booking
        payload = {
            "property_id": PID,
            "guest_name": f"TEST_iter587_{uuid.uuid4().hex[:6]}",
            "guest_email": "test587@example.com",
            "check_in": "2026-08-15",
            "check_out": "2026-08-17",
            "room_type": "Standard",
            "num_guests": 2,
            "total_amount": 200,
            "status": "confirmed"
        }
        r = client.post(f"{BASE_URL}/api/bookings", json=payload)
        # Booking might return 200/201
        assert r.status_code in (200, 201), r.text
        booking = r.json()
        bid = booking.get("id") or booking.get("_id")

        # Wait for background fire-and-forget event
        time.sleep(3)
        r_ev = client.get(f"{BASE_URL}/api/reprice-bridge/{PID}/events")
        reasons = [e["reason"] for e in r_ev.json()["events"]]
        assert any("booking_created" in x for x in reasons), f"no booking_created event found; reasons={reasons[:10]}"

        # Cancel
        if bid:
            rc = client.put(f"{BASE_URL}/api/bookings/{bid}/status?status=cancelled")
            if rc.status_code == 200:
                time.sleep(3)
                r_ev2 = client.get(f"{BASE_URL}/api/reprice-bridge/{PID}/events")
                reasons2 = [e["reason"] for e in r_ev2.json()["events"]]
                assert any("booking_cancelled" in x for x in reasons2), f"no cancel event; reasons={reasons2[:10]}"


# ---- Lost Demand → Reprice ----
class TestLostDemandReprice:
    def test_log_fires_reprice_event(self, client):
        r = client.post(f"{BASE_URL}/api/lost-demand/{PID}/log",
                        json={"check_in": "2026-09-10", "check_out": "2026-09-12",
                              "reason": "price_too_high", "rooms": 2, "quoted_rate": 250,
                              "channel": "phone", "note": "TEST_iter587"})
        assert r.status_code == 200, r.text
        entry = r.json()["entry"]
        assert entry["reason"] == "price_too_high"
        assert entry["est_lost_revenue"] == round(2 * 2 * 250, 2)

        time.sleep(3)
        r_ev = client.get(f"{BASE_URL}/api/reprice-bridge/{PID}/events")
        reasons = [e["reason"] for e in r_ev.json()["events"]]
        assert any("lost_demand_price_too_high" in x for x in reasons), f"reasons={reasons[:10]}"

    def test_summary(self, client):
        r = client.get(f"{BASE_URL}/api/lost-demand/{PID}?days=30")
        assert r.status_code == 200
        data = r.json()
        assert "summary" in data
        assert "by_reason" in data["summary"]
