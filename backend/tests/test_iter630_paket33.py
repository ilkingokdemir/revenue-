"""Iteration 630 / Paket33 – BE gap MVP:
    settings, agent-code, waitlist + worker, reserve-multi hold/LOS/agent/flex + hold expiry worker, live FX.
"""
import os
import asyncio
from datetime import datetime, timedelta, timezone

import pytest
import requests
from motor.motor_asyncio import AsyncIOMotorClient

def _load_env():
    for p in ("/app/frontend/.env", "/app/backend/.env"):
        try:
            for line in open(p):
                if "=" in line and not line.strip().startswith("#"):
                    k, v = line.strip().split("=", 1)
                    os.environ.setdefault(k, v.strip('"').strip("'"))
        except FileNotFoundError:
            pass
_load_env()
BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE}/api"
PID = "default"


@pytest.fixture(scope="session")
def token():
    r = requests.post(f"{API}/auth/login", json={"email": "admin@hotelbox.com", "password": "HotelAdmin2026!"}, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="session")
def hdr(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="session")
def db():
    return None


def _db():
    cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
    return cli[os.environ["DB_NAME"]]


def _rooms_list(payload):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        return payload.get("rooms") or payload.get("items") or []
    return []


# ---------------- BE settings ----------------
class TestBeSettings:
    def test_get_public_defaults(self):
        r = requests.get(f"{API}/booking/be-settings/{PID}", timeout=10)
        assert r.status_code == 200, r.text
        j = r.json()
        for k in ["base_occupancy", "extra_adult_per_night", "los_tiers", "flex_cancel_pct",
                  "hold_hours", "hold_enabled", "waitlist_enabled", "agent_code_enabled"]:
            assert k in j, f"missing {k}"
        assert j["extra_adult_per_night"] == 20 or float(j["extra_adult_per_night"]) == 20.0, j["extra_adult_per_night"]
        assert j["flex_cancel_pct"] in (8, 8.0) or float(j["flex_cancel_pct"]) == 8.0
        assert j["hold_hours"] == 24

    def test_put_invalid_pct(self, hdr):
        r = requests.put(f"{API}/booking/be-settings/{PID}", json={"flex_cancel_pct": 150}, headers=hdr, timeout=10)
        assert r.status_code == 422, r.text

    def test_put_invalid_type(self, hdr):
        r = requests.put(f"{API}/booking/be-settings/{PID}", json={"extra_adult_per_night": "x"}, headers=hdr, timeout=10)
        assert r.status_code == 422, r.text

    def test_put_ok_and_restore(self, hdr):
        r = requests.put(f"{API}/booking/be-settings/{PID}", json={"hold_hours": 12}, headers=hdr, timeout=10)
        assert r.status_code == 200
        assert r.json()["hold_hours"] == 12
        r = requests.put(f"{API}/booking/be-settings/{PID}", json={"hold_hours": 24}, headers=hdr, timeout=10)
        assert r.json()["hold_hours"] == 24


# ---------------- agent code ----------------
class TestAgentCode:
    def test_valid_case_insensitive(self):
        r = requests.post(f"{API}/booking/agent-code/validate", json={"property_id": PID, "code": "acme2026"}, timeout=10)
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["valid"] is True
        assert j.get("agent_name") == "ACME Travel"
        assert float(j.get("discount_pct")) == 15.0

    def test_unknown_code(self):
        r = requests.post(f"{API}/booking/agent-code/validate", json={"property_id": PID, "code": "NOPE"}, timeout=10)
        assert r.status_code == 404

    def test_empty_code(self):
        r = requests.post(f"{API}/booking/agent-code/validate", json={"property_id": PID, "code": ""}, timeout=10)
        assert r.status_code == 422


# ---------------- waitlist ----------------
class TestWaitlist:
    def test_add_and_dup(self, hdr):
        payload = {"property_id": PID, "email": "wl2@example.com", "name": "W",
                   "check_in": "2027-04-01", "check_out": "2027-04-03", "adults": 2}
        r = requests.post(f"{API}/booking/waitlist", json=payload, timeout=10)
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["ok"] and "id" in j
        r2 = requests.post(f"{API}/booking/waitlist", json=payload, timeout=10)
        assert r2.status_code == 200 and r2.json().get("already") is True

    def test_bad_dates(self):
        r = requests.post(f"{API}/booking/waitlist", json={"property_id": PID, "email": "x@e.com",
                                                            "check_in": "2027-05-05", "check_out": "2027-05-05"}, timeout=10)
        assert r.status_code == 422

    def test_bad_email(self):
        r = requests.post(f"{API}/booking/waitlist", json={"property_id": PID, "email": "noemail",
                                                            "check_in": "2027-04-01", "check_out": "2027-04-02"}, timeout=10)
        assert r.status_code == 422

    def test_list_admin(self, hdr):
        r = requests.get(f"{API}/booking/waitlist/{PID}", headers=hdr, timeout=10)
        assert r.status_code == 200
        j = r.json()
        assert "items" in j and "waiting" in j

    def test_worker_notify(self, db):
        async def go():
            db = _db()
            from workers import _notify_waitlist
            await _notify_waitlist(db)
            entry = await db.be_waitlist.find_one({"property_id": PID, "email": "wl2@example.com",
                                                   "check_in": "2027-04-01"}, {"_id": 0})
            outbox = await db.email_outbox.find_one({"kind": "waitlist", "waitlist_id": entry["id"] if entry else ""}, {"_id": 0}) if entry else None
            if not outbox:
                outbox = await db.outbound_email_queue.find_one({"type": "waitlist"}, {"_id": 0})
            return entry, outbox
        entry, row = asyncio.run(go())
        assert entry is not None, "waitlist entry gone"
        assert entry.get("status") == "notified", entry
        assert entry.get("email_status") in ("mocked", "mocked_email_queued", "queued", "sent"), entry.get("email_status")
        assert row is not None, "no email row"
        body = (row.get("html") or row.get("body") or "")
        assert "/book?property=default&check_in=2027-04-01" in body, body[:400]


# ---------------- reserve-multi + hold + expiry ----------------
class TestReserveMulti:
    def test_full_flow(self, db):
        # Find available room
        r = requests.get(f"{API}/booking/rooms/{PID}",
                         params={"check_in": "2027-05-01", "check_out": "2027-05-08", "adults": 3, "children": 0},
                         timeout=15)
        assert r.status_code == 200, r.text
        rooms = _rooms_list(r.json())
        avail = [x for x in rooms if x.get("available", True) and (x.get("id") or x.get("room_type_id"))]
        assert avail, f"no rooms: {r.json()}"
        rt = avail[0]
        rid = rt.get("id") or rt.get("room_type_id")

        payload = {"property_id": PID, "guest_name": "Gap QA", "guest_email": "gapqa@example.com",
                   "guest_phone": "+44", "check_in": "2027-05-01", "check_out": "2027-05-08",
                   "adults": 3, "agent_code": "ACME2026", "flex_cancel": True, "payment_method": "hold",
                   "items": [{"room_type_id": rid, "qty": 1}]}
        r = requests.post(f"{API}/booking/reserve-multi", json=payload, timeout=20)
        assert r.status_code == 200, r.text
        j = r.json()
        assert j.get("status") == "hold", j
        ref = j.get("booking_ref") or j.get("ref")

        async def fetch():
            return await _db().bookings.find_one({"booking_ref": ref}, {"_id": 0})
        booking = asyncio.run(fetch())
        assert booking, f"booking not found for ref {ref}"
        assert booking["status"] == "hold"
        assert booking.get("hold_expires_at")
        # extra adults = max(0, 3 - 2*1) = 1
        assert booking.get("extra_adults") == 1, booking.get("extra_adults")
        assert abs(float(booking.get("extra_adult_total") or 0) - 140.0) < 0.5, booking.get("extra_adult_total")
        assert float(booking.get("los_discount_pct") or 0) == 10.0
        assert float(booking.get("agent_discount") or 0) > 0
        assert float(booking.get("flex_cancel_fee") or 0) > 0
        assert booking.get("cancellation_type") == "free"

        # Force hold expire
        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()

        async def expire():
            db = _db()
            await db.bookings.update_one({"booking_ref": ref}, {"$set": {"hold_expires_at": past}})
            from workers import _expire_holds
            await _expire_holds(db)
            return await db.bookings.find_one({"booking_ref": ref}, {"_id": 0})
        after = asyncio.run(expire())
        assert after["status"] == "cancelled", after
        assert after.get("cancel_reason") == "hold_expired"

    def test_simple_confirm_no_addons(self, db):
        r = requests.get(f"{API}/booking/rooms/{PID}",
                         params={"check_in": "2027-06-10", "check_out": "2027-06-12", "adults": 2, "children": 0},
                         timeout=15)
        assert r.status_code == 200
        rooms = _rooms_list(r.json())
        avail = [x for x in rooms if x.get("available", True) and (x.get("id") or x.get("room_type_id"))]
        assert avail
        rid = avail[0].get("id") or avail[0].get("room_type_id")
        payload = {"property_id": PID, "guest_name": "Simple QA", "guest_email": "simpleqa@example.com",
                   "guest_phone": "+44", "check_in": "2027-06-10", "check_out": "2027-06-12",
                   "adults": 2, "items": [{"room_type_id": rid, "qty": 1}]}
        r = requests.post(f"{API}/booking/reserve-multi", json=payload, timeout=20)
        assert r.status_code == 200, r.text
        j = r.json()
        assert j.get("status") == "confirmed", j
        ref = j.get("booking_ref")

        async def fetch():
            return await _db().bookings.find_one({"booking_ref": ref}, {"_id": 0})
        b = asyncio.run(fetch())
        assert float(b.get("los_discount") or 0) == 0
        assert float(b.get("agent_discount") or 0) == 0
        assert float(b.get("flex_cancel_fee") or 0) == 0


# ---------------- FX ----------------
class TestFx:
    def test_fx_public(self):
        r = requests.get(f"{API}/booking/fx-rates", timeout=15)
        assert r.status_code == 200
        j = r.json()
        assert j["count"] >= 30, j["count"]
        eur = j["rates"].get("EUR")
        assert eur and 1.0 <= float(eur) <= 1.5, eur
        try_r = j["rates"].get("TRY")
        assert try_r and float(try_r) > 30, try_r
