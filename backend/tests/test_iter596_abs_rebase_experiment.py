"""Iter 596 — ABS Room Matrix/Availability + Booking Guarantee + Rebase Experiments."""
import os
import uuid
import pytest
import requests

def _load_backend_url():
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if not v:
        try:
            for line in open("/app/frontend/.env"):
                if line.startswith("REACT_APP_BACKEND_URL="):
                    v = line.split("=", 1)[1].strip()
                    break
        except OSError:
            pass
    assert v, "REACT_APP_BACKEND_URL missing"
    return v.rstrip("/")


BASE_URL = _load_backend_url()
PID = "aldgate-flats"


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": "admin@hotelbox.com", "password": "HotelAdmin2026!"},
                      timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def auth(token):
    return {"Authorization": f"Bearer {token}"}


# ---------- ABS: Room Matrix ----------

class TestAbsMatrix:
    def test_room_matrix(self, auth):
        r = requests.get(f"{BASE_URL}/api/abs/{PID}/room-matrix", headers=auth, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert isinstance(d.get("rooms"), list) and len(d["rooms"]) >= 1
        assert isinstance(d.get("attributes"), list) and len(d["attributes"]) >= 1
        for room in d["rooms"][:3]:
            assert "id" in room and "abs_attrs" in room or "abs_attrs" not in room  # optional field ok
        print(f"matrix: {len(d['rooms'])} rooms × {len(d['attributes'])} attrs")

    def test_room_attrs_put_404(self, auth):
        r = requests.put(f"{BASE_URL}/api/abs/{PID}/room-attrs/NONEXISTENT_{uuid.uuid4()}",
                         json={"attr_ids": []}, headers=auth, timeout=15)
        assert r.status_code == 404

    def test_room_attrs_put_ok(self, auth):
        m = requests.get(f"{BASE_URL}/api/abs/{PID}/room-matrix", headers=auth, timeout=15).json()
        room = m["rooms"][0]
        attrs = m["attributes"]
        original = room.get("abs_attrs", [])
        # PUT with all attribute ids
        new_ids = [a["id"] for a in attrs]
        r = requests.put(f"{BASE_URL}/api/abs/{PID}/room-attrs/{room['id']}",
                         json={"attr_ids": new_ids}, headers=auth, timeout=15)
        assert r.status_code == 200
        assert r.json()["attr_ids"] == new_ids
        # GET back to verify persistence
        m2 = requests.get(f"{BASE_URL}/api/abs/{PID}/room-matrix", headers=auth, timeout=15).json()
        got = next(r for r in m2["rooms"] if r["id"] == room["id"])
        assert set(got.get("abs_attrs", [])) == set(new_ids)
        # Restore
        requests.put(f"{BASE_URL}/api/abs/{PID}/room-attrs/{room['id']}",
                     json={"attr_ids": original}, headers=auth, timeout=15)

    def test_auto_seed(self, auth):
        r = requests.post(f"{BASE_URL}/api/abs/{PID}/room-attrs/auto-seed", headers=auth, timeout=15)
        assert r.status_code == 200
        assert r.json().get("rooms_mapped", 0) >= 1


# ---------- ABS: Public availability ----------

class TestAbsAvailability:
    def test_missing_dates_422(self):
        r = requests.post(f"{BASE_URL}/api/abs/public/{PID}/availability", json={}, timeout=15)
        assert r.status_code == 422

    def test_availability_no_auth_needed(self):
        r = requests.post(f"{BASE_URL}/api/abs/public/{PID}/availability",
                          json={"check_in": "2026-06-01", "check_out": "2026-06-03"}, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert isinstance(d["per_attribute"], dict)
        assert isinstance(d["combined_free_rooms"], int)
        assert isinstance(d["total_free_rooms"], int)

    def test_availability_with_attrs(self, auth):
        m = requests.get(f"{BASE_URL}/api/abs/{PID}/room-matrix", headers=auth, timeout=15).json()
        attrs = m["attributes"][:2]
        attr_ids = [a["id"] for a in attrs]
        r = requests.post(f"{BASE_URL}/api/abs/public/{PID}/availability",
                          json={"check_in": "2026-06-01", "check_out": "2026-06-03",
                                "attr_ids": attr_ids}, timeout=15)
        assert r.status_code == 200
        d = r.json()
        for aid in attr_ids:
            assert aid in d["per_attribute"]
        assert d["combined_free_rooms"] <= d["total_free_rooms"]


# ---------- ABS Booking Guarantee ----------

class TestAbsBookingGuarantee:
    def test_book_with_abs_assigns_room(self, auth):
        m = requests.get(f"{BASE_URL}/api/abs/{PID}/room-matrix", headers=auth, timeout=15).json()
        attrs = m["attributes"]
        # Find a room that has attrs, pick 1 of its attrs
        room_with_attrs = next((r for r in m["rooms"] if r.get("abs_attrs")), None)
        if not room_with_attrs:
            pytest.skip("no room with abs_attrs")
        pick = room_with_attrs["abs_attrs"][:1]
        payload = {
            "property_id": PID, "room_type": "Standard",
            "check_in": "2027-01-15", "check_out": "2027-01-17",
            "guest_name": "TEST_ABS_Guest", "guest_email": f"test_abs_{uuid.uuid4().hex[:6]}@example.com",
            "rate": 100.0, "rooms": 1, "pay_now": False,
            "abs_attribute_ids": pick,
        }
        r = requests.post(f"{BASE_URL}/api/booking-widget/book", json=payload, timeout=20)
        assert r.status_code == 200, r.text
        b = r.json().get("booking", {})
        assert b.get("abs_room_guaranteed") is True
        assert b.get("room_id")
        # Cleanup
        # No easy delete endpoint — leave TEST_ prefixed

    def test_book_with_impossible_combo_409(self, auth):
        """Set one room to have all attrs, fill it up, then re-book same attrs → 409."""
        m = requests.get(f"{BASE_URL}/api/abs/{PID}/room-matrix", headers=auth, timeout=15).json()
        attrs = m["attributes"]
        # Pick a highly unlikely combo — first + last attr should limit rooms
        if len(attrs) < 2:
            pytest.skip("need 2 attrs")
        # Use an attr combination present in at least one room
        # Find rooms that have both first attrs
        aid1, aid2 = attrs[0]["id"], attrs[1]["id"]
        matching = [r for r in m["rooms"] if aid1 in (r.get("abs_attrs") or []) and aid2 in (r.get("abs_attrs") or [])]
        if not matching:
            pytest.skip("no room has both attrs — cannot test 409 path deterministically")
        # Fill all matching rooms
        ci, co = "2027-02-10", "2027-02-12"
        booked = []
        for room in matching:
            b = {"id": str(uuid.uuid4()), "property_id": PID, "room_id": room["id"],
                 "room_number": room.get("name", ""),
                 "check_in": ci, "check_out": co, "status": "confirmed",
                 "guest_name": "TEST_FILL", "guest_email": "fill@t.co",
                 "nights": 2, "rate": 100, "total": 200, "total_price": 200,
                 "created_at": "2027-01-01T00:00:00+00:00", "source": "test"}
            # Insert via API — no direct API to seed; use widget book without abs
            r = requests.post(f"{BASE_URL}/api/booking-widget/book",
                              json={"property_id": PID, "room_type": "X",
                                    "check_in": ci, "check_out": co,
                                    "guest_name": "TEST_FILL", "guest_email": f"fill_{uuid.uuid4().hex[:6]}@t.co",
                                    "rate": 100, "rooms": 1, "pay_now": False,
                                    "abs_attribute_ids": [aid1, aid2]},
                              timeout=20)
            if r.status_code == 409:
                # Already filled — good, try booking one more
                break
            booked.append(r.json().get("booking", {}).get("id"))
        # Now attempt one more booking → should 409
        r = requests.post(f"{BASE_URL}/api/booking-widget/book",
                          json={"property_id": PID, "room_type": "X",
                                "check_in": ci, "check_out": co,
                                "guest_name": "TEST_OVERFLOW", "guest_email": "overflow@t.co",
                                "rate": 100, "rooms": 1, "pay_now": False,
                                "abs_attribute_ids": [aid1, aid2]},
                          timeout=20)
        assert r.status_code == 409, f"Expected 409, got {r.status_code}: {r.text}"

    def test_book_with_unmapped_attr_legacy(self, auth):
        """If NO room has a given attr, should NOT 409 — legacy behavior (ek ücret, no assignment)."""
        # Create a new attribute that no room has
        payload = {"name": f"TEST_ORPHAN_{uuid.uuid4().hex[:6]}", "price": 5.0}
        r = requests.post(f"{BASE_URL}/api/abs/{PID}", json=payload, headers=auth, timeout=15)
        assert r.status_code == 200
        aid = r.json()["attribute"]["id"]
        try:
            book = requests.post(f"{BASE_URL}/api/booking-widget/book",
                                 json={"property_id": PID, "room_type": "Std",
                                       "check_in": "2027-03-10", "check_out": "2027-03-12",
                                       "guest_name": "TEST_LEGACY", "guest_email": f"leg_{uuid.uuid4().hex[:6]}@t.co",
                                       "rate": 100, "rooms": 1, "pay_now": False,
                                       "abs_attribute_ids": [aid]},
                                 timeout=20)
            assert book.status_code == 200, book.text
            b = book.json().get("booking", {})
            # No room assignment because no room has this attr
            assert not b.get("abs_room_guaranteed")
            assert b.get("abs_total", 0) > 0
        finally:
            requests.delete(f"{BASE_URL}/api/abs/{PID}/{aid}", headers=auth, timeout=10)


# ---------- Rebase Experiment ----------

class TestRebaseExperiment:
    @pytest.fixture(scope="class")
    def report_id(self, auth):
        r = requests.post(f"{BASE_URL}/api/revenue/rebase-impact/{PID}/analyze",
                          json={"commission_pct": 15, "variable_cost": 15},
                          headers=auth, timeout=30)
        assert r.status_code == 200, r.text
        return r.json()["id"]

    def test_start_invalid_report_404(self, auth):
        r = requests.post(f"{BASE_URL}/api/revenue/rebase-impact/{PID}/experiment/start",
                          json={"report_id": "NONEXISTENT"}, headers=auth, timeout=15)
        assert r.status_code == 404

    def test_start_and_duplicate_409_and_stop(self, auth, report_id):
        # Ensure no running experiment first
        exps = requests.get(f"{BASE_URL}/api/revenue/rebase-impact/{PID}/experiments",
                            headers=auth, timeout=15).json()["experiments"]
        for e in exps:
            if e.get("status") == "running":
                requests.post(f"{BASE_URL}/api/revenue/rebase-impact/{PID}/experiment/{e['id']}/stop",
                              headers=auth, timeout=10)

        # Start
        r = requests.post(f"{BASE_URL}/api/revenue/rebase-impact/{PID}/experiment/start",
                          json={"report_id": report_id}, headers=auth, timeout=15)
        assert r.status_code == 200, r.text
        exp_id = r.json()["id"]

        # Duplicate → 409
        r2 = requests.post(f"{BASE_URL}/api/revenue/rebase-impact/{PID}/experiment/start",
                           json={"report_id": report_id}, headers=auth, timeout=15)
        assert r2.status_code == 409

        # List → progress fields
        lst = requests.get(f"{BASE_URL}/api/revenue/rebase-impact/{PID}/experiments",
                           headers=auth, timeout=15).json()["experiments"]
        me = next(e for e in lst if e["id"] == exp_id)
        p = me["progress"]
        for k in ("elapsed_days", "pickup_before", "pickup_after",
                  "pickup_change_pct", "adr_change_pct",
                  "contribution_before", "contribution_after", "verdict_tr"):
            assert k in p, f"missing progress key: {k}"
        # New experiment → verdict says "yeni başladı"
        assert "yeni başladı" in p["verdict_tr"] or "Deney yeni" in p["verdict_tr"]

        # Stop
        s = requests.post(f"{BASE_URL}/api/revenue/rebase-impact/{PID}/experiment/{exp_id}/stop",
                          headers=auth, timeout=15)
        assert s.status_code == 200

        # Stop nonexistent → 404
        s2 = requests.post(f"{BASE_URL}/api/revenue/rebase-impact/{PID}/experiment/BAD/stop",
                           headers=auth, timeout=10)
        assert s2.status_code == 404
