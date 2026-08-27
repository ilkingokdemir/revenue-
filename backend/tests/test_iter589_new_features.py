"""Iter 589 — Space Dynamic Pricing + Group Wash + RMS Uplift + Rate Mix Weekly."""
import os
import pytest
import requests
from datetime import datetime, timedelta, timezone
import uuid
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

def _load_env(path):
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line and "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    v = v.strip().strip('"').strip("'")
                    os.environ.setdefault(k, v)
    except Exception:
        pass


_load_env("/app/frontend/.env")
_load_env("/app/backend/.env")
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME")


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": "admin@hotelbox.com",
                            "password": "HotelAdmin2026!"})
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def h(token):
    return {"Authorization": f"Bearer {token}"}


# ---------- Space Dynamic Pricing ----------
class TestSpaceDynamicPricing:
    def test_dynamic_pricing_get(self, h):
        r = requests.get(f"{BASE_URL}/api/function-space/city-gate/dynamic-pricing?days=14", headers=h)
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["days"] == 14
        assert j["spaces"] >= 1
        assert isinstance(j["suggestions"], list)
        assert len(j["suggestions"]) > 0
        s = j["suggestions"][0]
        for k in ("space_id", "date", "current_rate", "suggested_rate", "change_pct", "why"):
            assert k in s, f"missing {k}"

    def test_days_clamp_low(self, h):
        r = requests.get(f"{BASE_URL}/api/function-space/city-gate/dynamic-pricing?days=1", headers=h)
        assert r.status_code == 200
        assert r.json()["days"] == 7

    def test_days_clamp_high(self, h):
        r = requests.get(f"{BASE_URL}/api/function-space/city-gate/dynamic-pricing?days=200", headers=h)
        assert r.status_code == 200
        assert r.json()["days"] == 60

    def test_apply_and_reduce_suggestions(self, h):
        r0 = requests.get(f"{BASE_URL}/api/function-space/city-gate/dynamic-pricing?days=14", headers=h)
        before = len(r0.json()["suggestions"])
        r = requests.post(f"{BASE_URL}/api/function-space/city-gate/dynamic-pricing/apply",
                          json={"days": 14}, headers=h)
        assert r.status_code == 200, r.text
        assert r.json()["ok"] is True
        written = r.json()["written"]
        assert written > 0
        r2 = requests.get(f"{BASE_URL}/api/function-space/city-gate/dynamic-pricing?days=14", headers=h)
        after = len(r2.json()["suggestions"])
        assert after <= before, f"apply should reduce/match suggestions: before={before}, after={after}"


# ---------- RMS Uplift ----------
class TestRmsUplift:
    def test_uplift_default(self, h):
        r = requests.get(f"{BASE_URL}/api/rms-uplift/default?months=12", headers=h)
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["capacity"] == 20, f"expected capacity 20 (room_types sum), got {j['capacity']}"
        assert len(j["months"]) == 12
        assert "baseline_revpar" in j
        assert "total_uplift_gbp" in j
        assert "verdict" in j and j["verdict"]
        for m in j["months"]:
            assert m["occ_pct"] <= 100
            assert m["phase"] in ("baz", "robot", "baz*")
            if m["phase"].startswith("baz"):
                assert m["uplift_gbp"] is None

    def test_months_clamp(self, h):
        r = requests.get(f"{BASE_URL}/api/rms-uplift/default?months=2", headers=h)
        assert len(r.json()["months"]) == 4
        r = requests.get(f"{BASE_URL}/api/rms-uplift/default?months=100", headers=h)
        assert len(r.json()["months"]) == 24


# ---------- Group Wash ----------
class TestGroupWash:
    def test_wash_aldgate(self, h):
        r = requests.get(f"{BASE_URL}/api/group-wash/aldgate-flats", headers=h)
        assert r.status_code == 200, r.text
        j = r.json()
        assert "historical_wash_pct" in j
        assert "model" in j
        assert "active_blocks" in j

    def test_wash_with_seeded_active_block_quantity_key(self, h):
        """Seed a group_block with 'quantity' (not 'rooms') key to verify bug fix."""
        async def _seed_and_check():
            client = AsyncIOMotorClient(MONGO_URL)
            db = client[DB_NAME]
            future_from = (datetime.now(timezone.utc) + timedelta(days=10)).date().isoformat()
            future_to = (datetime.now(timezone.utc) + timedelta(days=13)).date().isoformat()
            cutoff = (datetime.now(timezone.utc) + timedelta(days=7)).date().isoformat()
            created = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
            bid = f"TEST_wash_{uuid.uuid4().hex[:8]}"
            doc = {
                "id": bid,
                "property_id": "aldgate-flats",
                "name": "TEST_QuantityBlock",
                "code": "TESTQTY",
                "from_date": future_from,
                "to_date": future_to,
                "cutoff_date": cutoff,
                "allocations": [{"room_type_id": "std", "quantity": 20, "picked_up": 5}],
                "created_at": created,
                "status": "tentative",
            }
            await db.group_blocks.insert_one(doc)
            return bid

        async def _cleanup(bid):
            client = AsyncIOMotorClient(MONGO_URL)
            db = client[DB_NAME]
            await db.group_blocks.delete_one({"id": bid})

        bid = asyncio.get_event_loop().run_until_complete(_seed_and_check())
        try:
            r = requests.get(f"{BASE_URL}/api/group-wash/aldgate-flats", headers=h)
            assert r.status_code == 200
            j = r.json()
            active = [b for b in j["active_blocks"] if b.get("name") == "TEST_QuantityBlock"]
            assert len(active) == 1, f"seeded block not found in active_blocks: {j['active_blocks']}"
            b = active[0]
            assert b["allocated"] == 20, f"quantity key not counted: allocated={b['allocated']}"
            assert b["picked_up"] == 5
            for k in ("pace_pct", "projected_final_pickup", "wash_forecast_pct", "confidence"):
                assert k in b, f"missing {k}"
            assert b["confidence"] in ("yüksek", "orta", "düşük")
        finally:
            asyncio.get_event_loop().run_until_complete(_cleanup(bid))


# ---------- Rate Mix Weekly ----------
class TestRateMixWeekly:
    def test_snapshot(self, h):
        r = requests.post(f"{BASE_URL}/api/rate-mix/all/weekly/snapshot", headers=h)
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["ok"] is True
        assert j["snapshots"] >= 1

    def test_weekly_get(self, h):
        r = requests.get(f"{BASE_URL}/api/rate-mix/all/weekly", headers=h)
        assert r.status_code == 200
        j = r.json()
        assert "properties" in j
        assert len(j["properties"]) >= 1
        p = j["properties"][0]
        assert "weeks" in p and len(p["weeks"]) >= 1
        w = p["weeks"][0]
        for k in ("week", "floor_share", "adr", "lmf"):
            assert k in w, f"missing {k}"
        assert w["week"].startswith("20") and "W" in w["week"]

    def test_snapshot_idempotent(self, h):
        r1 = requests.post(f"{BASE_URL}/api/rate-mix/all/weekly/snapshot", headers=h)
        r2 = requests.get(f"{BASE_URL}/api/rate-mix/all/weekly", headers=h)
        # Verify no duplicate weeks per property
        for p in r2.json()["properties"]:
            weeks = [w["week"] for w in p["weeks"]]
            assert len(weeks) == len(set(weeks)), f"duplicate weeks: {weeks}"


# ---------- Regression ----------
class TestRegression:
    def test_rate_mix_all(self, h):
        r = requests.get(f"{BASE_URL}/api/rate-mix/all", headers=h)
        assert r.status_code == 200
        j = r.json()
        assert len(j["properties"]) >= 1

    def test_los_default(self, h):
        r = requests.get(f"{BASE_URL}/api/los-pricing/default", headers=h)
        assert r.status_code == 200
