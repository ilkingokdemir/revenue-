"""
Iteration 497 — Full SEAL regression covering iter 483-496 modules.
Tests:
- AUTH: admin login/logout/me/wrong-password
- ONBOARDING iter 483: quick-start idempotent + drip enroll/run-now/preview
- DEPARTMENT SHORTCUTS iter 488/489: GET/PUT + badges
- GROUP DISPLACEMENT iter 490-492: analyze accept/reject + history + verdicts
- DAMAGE PROTECTION iter 493-496: config, claims lifecycle, stats, public waiver, /booking/reserve fee, attach, owner-pulse digest card

Cleanup: All test artifacts (temp property, group bookings, waivers, claims) are removed.
"""
import os
import time
import uuid
import pytest
import requests

def _load_frontend_env():
    env_path = "/app/frontend/.env"
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    return line.split("=", 1)[1].strip().strip('"')
    return os.environ.get("REACT_APP_BACKEND_URL", "")

BASE_URL = _load_frontend_env().rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL missing"
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASS = "HotelAdmin2026!"

TEST_PID = f"TEST_ITER497_{uuid.uuid4().hex[:8]}"
CREATED = {"group_bookings": [], "claims": [], "bookings_waivered": [], "temp_bookings": []}


# ----- Fixtures -----
@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{API}/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=20)
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text[:200]}"
    data = r.json()
    tok = data.get("access_token") or data.get("token")
    assert tok, f"No token in response: {data}"
    return tok


@pytest.fixture(scope="module")
def hdr(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


# ----- AUTH -----
class TestAuth:
    def test_login_wrong_password(self):
        r = requests.post(f"{API}/auth/login",
                          json={"email": ADMIN_EMAIL, "password": "WrongPass!"}, timeout=15)
        assert r.status_code in (400, 401, 403), f"Expected auth reject, got {r.status_code}"

    def test_me_endpoint(self, hdr):
        r = requests.get(f"{API}/auth/me", headers=hdr, timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert data.get("email") == ADMIN_EMAIL


# ----- Onboarding iter 483 -----
class TestOnboarding:
    def test_quick_start_idempotent(self, hdr):
        r1 = requests.post(f"{API}/property-onboarding/quick-start/{TEST_PID}",
                           headers=hdr, json={}, timeout=60)
        assert r1.status_code == 200, f"quick-start failed: {r1.status_code} {r1.text[:200]}"
        d1 = r1.json()
        c1 = d1.get("created", {})
        assert c1.get("rooms", 0) >= 3, f"rooms<3: {d1}"
        assert c1.get("rate_products", 0) >= 2, f"rate<2: {d1}"
        assert c1.get("bookings", 0) >= 10, f"bookings<10: {d1}"

        # Idempotency
        r2 = requests.post(f"{API}/property-onboarding/quick-start/{TEST_PID}",
                           headers=hdr, json={}, timeout=60)
        assert r2.status_code == 200
        d2 = r2.json()
        rooms2 = d2.get("created", {}).get("rooms", 0)
        assert rooms2 == 0, f"Rooms should not duplicate: {d2}"

    # Status status endpoint doesn't take property_id for /status?
    def test_drip_status(self, hdr):
        r = requests.get(f"{API}/onboarding-drip/status/{TEST_PID}", headers=hdr, timeout=15)
        assert r.status_code == 200
        r = requests.post(f"{API}/onboarding-drip/enroll/{TEST_PID}",
                          headers=hdr, json={"email": ADMIN_EMAIL}, timeout=15)
        assert r.status_code in (200, 201), f"enroll: {r.status_code} {r.text[:200]}"

        # Run-now — no path param, no body
        r = requests.post(f"{API}/onboarding-drip/run-now", headers=hdr, timeout=30)
        assert r.status_code == 200, f"run-now: {r.status_code} {r.text[:200]}"
        data = r.json()
        assert isinstance(data, dict)

    def test_drip_preview_welcome(self, hdr):
        r = requests.get(f"{API}/onboarding-drip/preview/welcome", headers=hdr, timeout=15)
        assert r.status_code == 200
        html = r.text
        assert "<html" in html.lower() or "<!doctype" in html.lower() or "MyHotelBox" in html


# ----- Department Shortcuts iter 488/489 -----
class TestDeptShortcuts:
    def test_get_all_and_management(self, hdr):
        r = requests.get(f"{API}/department-shortcuts", headers=hdr, timeout=15)
        assert r.status_code == 200
        r = requests.get(f"{API}/department-shortcuts/management", headers=hdr, timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert data["department"] == "management"

    def test_put_and_restore_management(self, hdr):
        # Save original
        orig = requests.get(f"{API}/department-shortcuts/management", headers=hdr, timeout=15).json()
        orig_items = orig.get("items", [])
        # PUT test list
        test_items = ["dashboard", "revenue", "analytics"]
        r = requests.put(f"{API}/department-shortcuts/management",
                         headers=hdr, json={"items": test_items}, timeout=15)
        assert r.status_code == 200
        assert r.json()["items"] == test_items

        # Verify GET
        got = requests.get(f"{API}/department-shortcuts/management", headers=hdr, timeout=15).json()
        assert got["items"] == test_items

        # Restore
        restore_items = orig_items if orig_items else ["dashboard", "tier1-dashboard", "revenue",
                                                       "finance", "analytics", "team"]
        r = requests.put(f"{API}/department-shortcuts/management",
                         headers=hdr, json={"items": restore_items}, timeout=15)
        assert r.status_code == 200

    def test_badges(self, hdr):
        r = requests.get(f"{API}/department-shortcuts/badges/default", headers=hdr, timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert "arrivals" in data
        assert isinstance(data["arrivals"], int)


# ----- Group Displacement iter 490-492 -----
class TestGroupDisplacement:
    def test_analyze_accept(self, hdr):
        payload = {
            "property_id": "default",
            "check_in": "2026-11-01",
            "check_out": "2026-11-04",
            "rooms_requested": 10,
            "offered_rate": 300.0,
            "group_name": "TEST_ITER497_ACCEPT",
        }
        r = requests.post(f"{API}/group-displacement/analyze", headers=hdr, json=payload, timeout=30)
        assert r.status_code == 200, f"analyze accept: {r.status_code} {r.text[:200]}"
        d = r.json()
        assert d["nights"] == 3
        assert d["recommendation"] in ("accept", "negotiate", "reject")
        assert len(d["per_night"]) == 3
        # High rate = should typically accept
        assert d["total_group_revenue"] > 0

    def test_analyze_reject_lowrate(self, hdr):
        payload = {
            "property_id": "default",
            "check_in": "2026-11-01",
            "check_out": "2026-11-04",
            "rooms_requested": 18,
            "offered_rate": 50.0,
            "group_name": "TEST_ITER497_REJECT",
        }
        r = requests.post(f"{API}/group-displacement/analyze", headers=hdr, json=payload, timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d["recommendation"] in ("reject", "negotiate")
        assert d["suggested_min_rate"] >= 50.0

    def test_history_and_verdicts(self, hdr):
        r = requests.get(f"{API}/group-displacement/history/default", headers=hdr, timeout=15)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

        r = requests.get(f"{API}/group-displacement/verdicts/default", headers=hdr, timeout=30)
        assert r.status_code == 200
        assert isinstance(r.json(), dict)


# ----- Damage Protection iter 493-496 -----
class TestDamageProtection:
    def test_config_get_put(self, hdr):
        # Backup current
        orig = requests.get(f"{API}/damage-protection/config/default", headers=hdr, timeout=15).json()

        cfg = {"enabled": True, "fee_per_night": 4.5, "coverage_limit": 5000, "currency": "GBP"}
        r = requests.put(f"{API}/damage-protection/config/default", headers=hdr, json=cfg, timeout=15)
        assert r.status_code == 200

        got = requests.get(f"{API}/damage-protection/config/default", headers=hdr, timeout=15).json()
        assert got["enabled"] is True
        assert got["fee_per_night"] == 4.5

        # Leave enabled=True for downstream tests (public waiver/reserve)
        # Restore original values but keep enabled True if it was False
        keep_cfg = {
            "enabled": True,  # keep enabled for other tests
            "fee_per_night": orig.get("fee_per_night", 3.0),
            "coverage_limit": orig.get("coverage_limit", 5000.0),
            "currency": orig.get("currency", "GBP"),
        }
        requests.put(f"{API}/damage-protection/config/default", headers=hdr, json=keep_cfg, timeout=15)

    def test_public_waiver(self):
        r = requests.get(f"{API}/booking/damage-waiver/default", timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d.get("enabled") is True
        assert d.get("fee_per_night", 0) > 0

    def test_claim_lifecycle(self, hdr):
        payload = {
            "property_id": "default",
            "booking_id": "",
            "guest_name": "TEST_ITER497_Guest",
            "description": "Broken lamp",
            "amount": 120.0,
        }
        r = requests.post(f"{API}/damage-protection/claims", headers=hdr, json=payload, timeout=15)
        assert r.status_code == 200
        claim = r.json()
        cid = claim["id"]
        CREATED["claims"].append(cid)
        assert claim["status"] == "open"

        # Approve
        r = requests.put(f"{API}/damage-protection/claims/{cid}", headers=hdr,
                         json={"status": "approved"}, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["status"] == "approved"
        assert d["approved_amount"] == 120.0, f"approved_amount should auto-fill: {d}"

        # Settle
        r = requests.put(f"{API}/damage-protection/claims/{cid}", headers=hdr,
                         json={"status": "settled", "approved_amount": 100.0,
                               "resolution_note": "Partial refund"}, timeout=15)
        assert r.status_code == 200
        assert r.json()["approved_amount"] == 100.0

    def test_stats_math(self, hdr):
        r = requests.get(f"{API}/damage-protection/stats/default", headers=hdr, timeout=20)
        assert r.status_code == 200
        d = r.json()
        # Basic math: net = collected - paid
        assert abs(d["net_pool_90d"] - (d["estimated_collected_90d"] - d["claims_paid_amount"])) < 0.01
        assert d["claims_total"] >= 1

    def test_booking_reserve_with_waiver(self, hdr):
        # find any active room type on default
        r = requests.get(f"{API}/booking/rooms/default?check_in=2026-12-01&check_out=2026-12-03",
                         timeout=15)
        assert r.status_code == 200
        rooms = r.json()  # list
        assert rooms, "No rooms available on default for 2026-12-01"
        # rooms are room_type docs with 'id'; pick first available
        room = next((x for x in rooms if x.get("available_rooms", 0) > 0), rooms[0])
        room_type_id = room["id"]

        # get fee
        wcfg = requests.get(f"{API}/booking/damage-waiver/default", timeout=10).json()
        fee_per_night = wcfg["fee_per_night"]

        # Reserve WITHOUT waiver
        base_payload = {
            "property_id": "default",
            "room_type_id": room_type_id,
            "guest_name": "TEST_ITER497_NoWaiver",
            "guest_email": "test_iter497@example.com",
            "guest_phone": "+441234567890",
            "check_in": "2026-12-01",
            "check_out": "2026-12-03",
            "adults": 1, "children": 0, "rooms": 1,
            "damage_waiver": False,
        }
        r = requests.post(f"{API}/booking/reserve", json=base_payload, timeout=20)
        assert r.status_code == 200, f"reserve base: {r.status_code} {r.text[:200]}"
        no_waiver = r.json()
        CREATED["temp_bookings"].append(no_waiver["id"])
        total_no = no_waiver["total_price"]

        # Reserve WITH waiver
        w_payload = dict(base_payload)
        w_payload["guest_name"] = "TEST_ITER497_Waiver"
        w_payload["damage_waiver"] = True
        r = requests.post(f"{API}/booking/reserve", json=w_payload, timeout=20)
        assert r.status_code == 200
        with_waiver = r.json()
        CREATED["temp_bookings"].append(with_waiver["id"])

        expected_fee = fee_per_night * 2 * 1  # 2 nights, 1 room
        actual_delta = with_waiver["total_price"] - total_no
        assert abs(actual_delta - expected_fee) < 0.01, \
            f"Waiver fee mismatch: delta={actual_delta} expected={expected_fee}"

    def test_owner_pulse_digest_contains_damage_card(self, hdr):
        r = requests.get(f"{API}/owner-pulse/default/digest/preview", headers=hdr, timeout=30)
        assert r.status_code == 200, f"owner-pulse digest: {r.status_code} {r.text[:200]}"
        # HTML or JSON with html
        body = r.text
        # Look for Turkish or English label
        assert ("Hasar" in body or "damage" in body.lower() or "waiver" in body.lower()), \
            "Damage protection card missing from digest"


# ----- Cleanup -----
def test_zzz_cleanup(hdr):
    """Runs last (alphabetical): cleanup all test artifacts."""
    # Delete claims
    from motor.motor_asyncio import AsyncIOMotorClient
    import asyncio

    async def _clean():
        # Load MONGO_URL/DB_NAME from backend/.env
        from dotenv import dotenv_values
        env = dotenv_values("/app/backend/.env")
        mongo_url = env.get("MONGO_URL") or os.environ.get("MONGO_URL")
        db_name = env.get("DB_NAME") or os.environ.get("DB_NAME")
        client = AsyncIOMotorClient(mongo_url)
        db = client[db_name]

        # Temp property + related
        await db.property_onboarding.delete_many({"property_id": TEST_PID})
        await db.onboarding_drip.delete_many({"property_id": TEST_PID})
        await db.room_types.delete_many({"property_id": TEST_PID})
        await db.rate_products.delete_many({"property_id": TEST_PID})
        await db.tax_profiles.delete_many({"property_id": TEST_PID})
        await db.bookings.delete_many({"property_id": TEST_PID})
        await db.properties.delete_many({"id": TEST_PID})

        # Test claims
        for cid in CREATED["claims"]:
            await db.damage_claims.delete_one({"id": cid})

        # Temp bookings on default (waiver tests)
        for bid in CREATED["temp_bookings"]:
            await db.bookings.delete_one({"id": bid})

        # Test group displacement analyses
        await db.group_displacement_analyses.delete_many({"group_name": {"$regex": "^TEST_ITER497"}})

        client.close()

    asyncio.get_event_loop().run_until_complete(_clean())
    assert True
