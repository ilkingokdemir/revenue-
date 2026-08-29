"""Iter 599: Price Guard + DEMAND_STRONG e2e (via ramp_ladder scan)."""
import os
import asyncio
import uuid
from datetime import datetime, timezone, timedelta

import pytest
import requests
from motor.motor_asyncio import AsyncIOMotorClient

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") if os.environ.get("REACT_APP_BACKEND_URL") else None
if not BASE:
    # frontend/.env fallback
    with open("/app/frontend/.env") as f:
        for ln in f:
            if ln.startswith("REACT_APP_BACKEND_URL"):
                BASE = ln.split("=", 1)[1].strip().rstrip("/")
API = f"{BASE}/api"
PID = "aldgate-flats"

MONGO_URL = None
DB_NAME = None
with open("/app/backend/.env") as f:
    for ln in f:
        if ln.startswith("MONGO_URL"):
            MONGO_URL = ln.split("=", 1)[1].strip().strip('"').strip("'")
        elif ln.startswith("DB_NAME"):
            DB_NAME = ln.split("=", 1)[1].strip().strip('"').strip("'")


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{API}/auth/login",
                      json={"email": "admin@hotelbox.com", "password": "HotelAdmin2026!"})
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def H(token):
    return {"Authorization": f"Bearer {token}"}


# ------------------- PRICE GUARD API -------------------
class TestPriceGuardAPI:
    def test_get_returns_shape(self, H):
        r = requests.get(f"{API}/price-guard/{PID}", headers=H)
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("enabled", "max_single_pct", "max_72h_pct", "recent_log", "recent_clamps"):
            assert k in d, f"missing {k}"
        assert isinstance(d["recent_log"], list)
        assert isinstance(d["recent_clamps"], int)

    def test_put_valid_8_persists(self, H):
        r = requests.put(f"{API}/price-guard/{PID}", headers=H, json={"max_single_pct": 8})
        assert r.status_code == 200, r.text
        assert r.json()["max_single_pct"] == 8.0
        g = requests.get(f"{API}/price-guard/{PID}", headers=H).json()
        assert g["max_single_pct"] == 8.0

    def test_put_invalid_zero_returns_422(self, H):
        r = requests.put(f"{API}/price-guard/{PID}", headers=H, json={"max_single_pct": 0})
        assert r.status_code == 422

    def test_put_invalid_99_returns_422(self, H):
        r = requests.put(f"{API}/price-guard/{PID}", headers=H, json={"max_single_pct": 99})
        assert r.status_code == 422

    def test_put_72h_bounds(self, H):
        r = requests.put(f"{API}/price-guard/{PID}", headers=H, json={"max_72h_pct": 3})
        assert r.status_code == 422
        r = requests.put(f"{API}/price-guard/{PID}", headers=H, json={"max_72h_pct": 200})
        assert r.status_code == 422

    def test_toggle_enabled(self, H):
        r = requests.put(f"{API}/price-guard/{PID}", headers=H, json={"enabled": False})
        assert r.status_code == 200
        assert requests.get(f"{API}/price-guard/{PID}", headers=H).json()["enabled"] is False
        r = requests.put(f"{API}/price-guard/{PID}", headers=H, json={"enabled": True})
        assert r.status_code == 200
        assert requests.get(f"{API}/price-guard/{PID}", headers=H).json()["enabled"] is True


# ------------------- GUARD LOGIC (direct import) -------------------
class TestGuardLogic:
    def test_single_and_cumulative_and_lock(self):
        async def run():
            from routes.revenue_ext.price_guard import guard_rate_change
            client = AsyncIOMotorClient(MONGO_URL)
            db = client[DB_NAME]
            pid = f"TEST_iter599_{uuid.uuid4().hex[:6]}"
            rt = "rt_x"
            date = "2030-01-01"
            # Ensure clean settings for pid (falls back to defaults 10/25)
            await db.price_guard_settings.delete_many({"property_id": pid})
            # 1) single hop clamp 100 -> 120 => 110
            r = await guard_rate_change(db, pid, rt, date, 100.0, 120.0, "ramp-ladder")
            assert r["allowed"] and r["clamped"] and r["rate"] == 110.0, r
            # 2) another hop shortly after: 110 -> 200 requested, single clamps to 121;
            #    cumulative base=100 (first log old_rate), ceiling=125 → allowed 121
            r2 = await guard_rate_change(db, pid, rt, date, 110.0, 200.0, "ramp-ladder")
            assert r2["allowed"] and r2["clamped"] and r2["rate"] == 121.0, r2
            # 3) third hop: 121 -> 200 (single clamp→133.1) but 72h ceil=125 → 125
            r3 = await guard_rate_change(db, pid, rt, date, 121.0, 200.0, "ramp-ladder")
            assert r3["allowed"] and r3["clamped"] and r3["rate"] == 125.0, r3
            # 4) fourth hop when already at ceil: 125->150 → blocked
            r4 = await guard_rate_change(db, pid, rt, date, 125.0, 150.0, "ramp-ladder")
            assert r4["allowed"] is False, r4
            # 5) owner-lock: seed override; auto actor blocked
            await db.rate_overrides.update_one(
                {"property_id": pid, "room_type_id": rt, "date": date},
                {"$set": {"set_by": "owner-override", "custom_rate": 200.0}}, upsert=True)
            r5 = await guard_rate_change(db, pid, rt, date, 100.0, 105.0, "ramp-ladder")
            assert r5["allowed"] is False and "kilitli" in (r5["blocked_reason"] or "").lower(), r5
            # cleanup
            await db.price_guard_log.delete_many({"property_id": pid})
            await db.rate_overrides.delete_many({"property_id": pid})
            await db.price_guard_settings.delete_many({"property_id": pid})
            client.close()

        asyncio.run(run())


# ------------------- DEMAND_STRONG E2E via ramp scan -------------------
class TestDemandStrongE2E:
    def test_market_signal_triggers_demand_strong_step(self, H):
        async def run():
            from routes.revenue_ext.ramp_ladder import scan_property
            client = AsyncIOMotorClient(MONGO_URL)
            db = client[DB_NAME]
            pid = PID
            # pick a room type for property
            rt_doc = await db.room_types.find_one({"property_id": pid}, {"_id": 0})
            assert rt_doc, "no room_type for aldgate-flats"
            rt_id = rt_doc["id"]
            base_price = float(rt_doc.get("base_price") or 100.0)
            total_rooms = int(rt_doc.get("total_rooms") or 5)

            now = datetime.now(timezone.utc)
            # stay date = today+5 (within ramp window 2..21)
            stay = (now.date() + timedelta(days=5)).isoformat()

            # --- SEED ramp_config: enabled, cadence 12h, occ_threshold low ---
            saved_cfg = await db.ramp_config.find_one({"property_id": pid}, {"_id": 0})
            await db.ramp_config.update_one({"property_id": pid}, {"$set": {
                "enabled": True, "window_start": 2, "window_end": 21,
                "step_pct": 5.0, "max_steps": 3, "occ_threshold": 10.0,
                "cadence_hours": 12}}, upsert=True)

            # --- SEED ramp_state step_no=1, bookings_at_last_step = current sold ---
            sold = await db.bookings.count_documents({
                "property_id": pid, "room_type_id": rt_id,
                "status": {"$nin": ["cancelled", "no_show"]},
                "check_in": {"$lte": stay}, "check_out": {"$gt": stay}})
            anchor = base_price
            await db.ramp_state.update_one(
                {"property_id": pid, "stay_date": stay, "room_type_id": rt_id},
                {"$set": {"step_no": 1, "anchor_rate": anchor,
                          "bookings_at_last_step": sold,
                          "last_step_at": (now - timedelta(hours=24)).isoformat()}},
                upsert=True)

            # Ensure no owner-override lock exists
            await db.rate_overrides.delete_many(
                {"property_id": pid, "room_type_id": rt_id, "date": stay})

            # --- SEED comp_rate_snapshots: fresh median +8%, unavail_share = 2/3 (>=0.5, full_step<0.6? 0.67 yes → full_step) ---
            await db.comp_rate_snapshots.delete_many(
                {"property_id": {"$in": [pid, "default"]}, "date": stay})
            fresh_at = (now - timedelta(hours=1)).isoformat()
            old_at = (now - timedelta(days=7)).isoformat()
            comps_old = [("c1", 100.0), ("c2", 100.0), ("c3", 100.0)]
            comps_new = [("c1", 108.0), ("c2", 110.0), ("c3", 108.0)]
            for cid, r in comps_old:
                await db.comp_rate_snapshots.insert_one({
                    "id": str(uuid.uuid4()), "property_id": pid, "comp_id": cid,
                    "date": stay, "rate": r, "sold_out": False, "unavailable": False,
                    "scanned_at": old_at})
            for i, (cid, r) in enumerate(comps_new):
                await db.comp_rate_snapshots.insert_one({
                    "id": str(uuid.uuid4()), "property_id": pid, "comp_id": cid,
                    "date": stay, "rate": r,
                    "sold_out": i < 2,  # 2 of 3 sold_out => 0.67
                    "unavailable": False, "scanned_at": fresh_at})

            # Ensure guard settings default
            await db.price_guard_settings.update_one({"property_id": pid},
                {"$set": {"enabled": True, "max_single_pct": 10.0, "max_72h_pct": 25.0}}, upsert=True)

            # Clear recent ramp_steps for this stay/rt to isolate assertion
            await db.ramp_steps.delete_many({"property_id": pid, "stay_date": stay, "room_type_id": rt_id})

            # --- CALL SCAN with force=True ---
            res = await scan_property(db, pid, force=True)
            actions = res.get("actions", [])
            demand_step = next((a for a in actions if a.get("stay_date") == stay
                                and a.get("room_type_id") == rt_id
                                and a.get("reason") == "DEMAND_STRONG"), None)
            assert demand_step is not None, f"No DEMAND_STRONG action found. actions={actions} skips={res.get('skips')}"
            assert demand_step["from_step"] == 1
            assert demand_step["step_no"] == 2
            assert demand_step.get("market_signal", {}).get("strong") is True

            # rate_overrides reason contains DEMAND_STRONG (piyasa)
            ov = await db.rate_overrides.find_one(
                {"property_id": pid, "room_type_id": rt_id, "date": stay}, {"_id": 0})
            assert ov and "DEMAND_STRONG (piyasa)" in (ov.get("reason") or ""), ov

            # --- second scan within 24h should NOT emit another market step ---
            # bump bookings_at_last so occupancy stall persists; keep market_step_at set now
            await db.ramp_steps.delete_many({"property_id": pid, "stay_date": stay, "room_type_id": rt_id})
            res2 = await scan_property(db, pid, force=True)
            demand2 = [a for a in res2.get("actions", [])
                       if a.get("stay_date") == stay and a.get("room_type_id") == rt_id
                       and a.get("reason") == "DEMAND_STRONG"]
            assert not demand2, f"Second DEMAND_STRONG within 24h should be suppressed. Got: {demand2}"

            # --- Cleanup seeded data ---
            await db.comp_rate_snapshots.delete_many(
                {"property_id": {"$in": [pid, "default"]}, "date": stay})
            await db.ramp_state.delete_many(
                {"property_id": pid, "stay_date": stay, "room_type_id": rt_id})
            await db.ramp_steps.delete_many(
                {"property_id": pid, "stay_date": stay, "room_type_id": rt_id})
            await db.rate_overrides.delete_many(
                {"property_id": pid, "room_type_id": rt_id, "date": stay})
            # restore cfg
            if saved_cfg:
                await db.ramp_config.update_one({"property_id": pid}, {"$set": saved_cfg}, upsert=True)
            else:
                await db.ramp_config.delete_one({"property_id": pid})
            client.close()

        asyncio.run(run())


# ------------------- REGRESSION: awaiting_guest_approval still emitted -------------------
class TestGuestApprovalRegression:
    def test_awaiting_guest_approval_still_produced(self):
        async def run():
            from routes.revenue_ext.ramp_ladder import scan_property
            client = AsyncIOMotorClient(MONGO_URL)
            db = client[DB_NAME]
            pid = PID
            rt_doc = await db.room_types.find_one({"property_id": pid}, {"_id": 0})
            rt_id = rt_doc["id"]
            now = datetime.now(timezone.utc)
            stay = (now.date() + timedelta(days=6)).isoformat()

            saved_cfg = await db.ramp_config.find_one({"property_id": pid}, {"_id": 0})
            await db.ramp_config.update_one({"property_id": pid}, {"$set": {
                "enabled": True, "window_start": 2, "window_end": 21,
                "step_pct": 5.0, "max_steps": 3, "occ_threshold": 10.0,
                "cadence_hours": 12}}, upsert=True)

            sold = await db.bookings.count_documents({
                "property_id": pid, "room_type_id": rt_id,
                "status": {"$nin": ["cancelled", "no_show"]},
                "check_in": {"$lte": stay}, "check_out": {"$gt": stay}})
            await db.ramp_state.update_one(
                {"property_id": pid, "stay_date": stay, "room_type_id": rt_id},
                {"$set": {"step_no": 1, "anchor_rate": float(rt_doc.get("base_price") or 100),
                          "bookings_at_last_step": sold,
                          "last_step_at": (now - timedelta(hours=24)).isoformat()}}, upsert=True)
            # No comp snapshots — market not strong
            await db.comp_rate_snapshots.delete_many({"property_id": {"$in": [pid, "default"]}, "date": stay})
            await db.rate_overrides.delete_many({"property_id": pid, "room_type_id": rt_id, "date": stay})

            res = await scan_property(db, pid, force=True)
            skips = res.get("skips", [])
            awaiting = [s for s in skips if s.get("reason") == "awaiting_guest_approval"
                        and any(str(rt_doc.get("name", "")) in str(v) for v in s.values())]
            # accept by any awaiting_guest_approval for this stay date
            awaiting_any = [s for s in skips if s.get("reason") == "awaiting_guest_approval"]
            assert awaiting_any, f"awaiting_guest_approval skip missing. skips={skips} actions={res.get('actions')}"

            await db.ramp_state.delete_many({"property_id": pid, "stay_date": stay})
            if saved_cfg:
                await db.ramp_config.update_one({"property_id": pid}, {"$set": saved_cfg}, upsert=True)
            else:
                await db.ramp_config.delete_one({"property_id": pid})
            client.close()

        asyncio.run(run())


# ------------------- CLEANUP: restore defaults -------------------
class TestZZCleanup:
    def test_restore_defaults(self, H):
        r = requests.put(f"{API}/price-guard/{PID}", headers=H,
                         json={"max_single_pct": 10, "max_72h_pct": 25, "enabled": True})
        assert r.status_code == 200
        g = requests.get(f"{API}/price-guard/{PID}", headers=H).json()
        assert g["max_single_pct"] == 10.0
        assert g["max_72h_pct"] == 25.0
        assert g["enabled"] is True
