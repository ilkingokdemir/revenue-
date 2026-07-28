"""
Iteration 481 - Revenue Brain (Öğrenen Beyin) E2E tests.
- Learning cycle for 'aldgate-flats'
- Goal layer (valid + invalid)
- Self-tuning E2E: seed TEST_BRAIN outcomes, verify learned_mult in suggestions, then cleanup
- Cron evidence
- Strategist lessons feed code path (static grep)
- Regression: /api/revenue/ai-pricing/default/suggestions still returns 200 with str_mult+learned_mult
"""
import os
import re
import pytest
import requests
from motor.motor_asyncio import AsyncIOMotorClient
import asyncio

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")

ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASS = "HotelAdmin2026!"


@pytest.fixture(scope="module")
def api():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    tok = r.json().get("access_token") or r.json().get("token")
    if tok:
        s.headers.update({"Authorization": f"Bearer {tok}"})
    return s


@pytest.fixture(scope="module")
def loop():
    l = asyncio.new_event_loop()
    yield l
    l.close()


@pytest.fixture(scope="module")
def db(loop):
    client = AsyncIOMotorClient(MONGO_URL)
    return client[DB_NAME]


# ---------- Learning cycle: aldgate-flats ----------
class TestLearnAldgate:
    def test_learn_cycle(self, api):
        r = api.post(f"{BASE_URL}/api/revenue-brain/aldgate-flats/learn", timeout=60)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert "measured" in d and "weights_updated" in d and "lessons" in d
        assert isinstance(d["measured"], int)

    def test_status(self, api):
        r = api.get(f"{BASE_URL}/api/revenue-brain/aldgate-flats/status", timeout=30)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        # aldgate has 8 real past decisions per spec
        assert d["outcomes_measured"] == 8, f"expected 8 outcomes, got {d['outcomes_measured']}"
        for k in ("success_rate", "hurt", "weights", "lessons", "recent_outcomes",
                  "last_cycle_at", "goal"):
            assert k in d, f"missing key {k}"
        assert isinstance(d["weights"], list)
        assert isinstance(d["lessons"], list)
        assert isinstance(d["recent_outcomes"], list)
        assert len(d["recent_outcomes"]) >= 1
        # Verify recent_outcomes fields
        o = d["recent_outcomes"][0]
        for k in ("stay_date", "delta_pct", "final_occ", "baseline_occ", "verdict"):
            assert k in o, f"outcome missing {k}"
        assert o["verdict"] in ("worked", "neutral", "hurt")
        # goal block
        for k in ("month", "mtd_revenue", "projection"):
            assert k in d["goal"]


# ---------- Goal layer ----------
class TestGoal:
    def test_set_goal_valid(self, api):
        r = api.put(f"{BASE_URL}/api/revenue-brain/default/goal",
                    json={"target_revenue": 45000}, timeout=30)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert d["target_revenue"] == 45000
        for k in ("mtd_revenue", "projection", "progress_pct", "on_track", "recommendation"):
            assert k in d, f"missing {k}"
        # Turkish recommendation
        assert isinstance(d["recommendation"], str) and len(d["recommendation"]) > 10

    def test_set_goal_zero(self, api):
        r = api.put(f"{BASE_URL}/api/revenue-brain/default/goal",
                    json={"target_revenue": 0}, timeout=15)
        assert r.status_code == 400

    def test_set_goal_negative(self, api):
        r = api.put(f"{BASE_URL}/api/revenue-brain/default/goal",
                    json={"target_revenue": -100}, timeout=15)
        assert r.status_code == 400

    def test_status_has_goal(self, api):
        r = api.get(f"{BASE_URL}/api/revenue-brain/default/status", timeout=30)
        assert r.status_code == 200
        g = r.json()["goal"]
        assert g.get("target_revenue") == 45000


# ---------- Self-tuning E2E ----------
class TestSelfTuningE2E:
    def _dates(self, db, loop):
        """Get 5 weekday dates in the 8-21 day-out band"""
        from datetime import datetime, timezone, timedelta
        today = datetime.now(timezone.utc).date()
        dates = []
        d = today + timedelta(days=8)
        while len(dates) < 5 and (d - today).days <= 21:
            # weekday means Mon-Thu/Sun (not Fri/Sat as per code weekday() in (4,5))
            if d.weekday() not in (4, 5):
                dates.append(d.strftime("%Y-%m-%d"))
            d += timedelta(days=1)
        return dates

    def test_full_flow(self, api, db, loop):
        from datetime import datetime, timezone
        import uuid

        pid = "default"
        dates = self._dates(db, loop)
        assert len(dates) >= 4, "need 4+ weekday dates 8-21 out"

        async def seed():
            # Store any existing base_rate on any default room_type to restore later
            rt = await db.room_types.find_one({"property_id": pid}, {"_id": 0, "id": 1, "base_rate": 1})
            orig_rate = rt.get("base_rate") if rt else None
            rt_id = rt.get("id") if rt else None
            if rt_id:
                await db.room_types.update_one({"id": rt_id}, {"$set": {"base_rate": 120}})

            # Insert 5 TEST_BRAIN outcomes, all hurt, direction up, bucket 8-21|weekday|up
            now = datetime.now(timezone.utc).isoformat()
            for i, ds in enumerate(dates[:5]):
                await db.ai_pricing_outcomes.insert_one({
                    "id": f"TEST_BRAIN_{i}_{uuid.uuid4()}",
                    "property_id": pid,
                    "stay_date": ds,
                    "room_type_id": "TEST_BRAIN",
                    "delta_pct": 8.0,
                    "direction": "up",
                    "days_out": 10 + i,
                    "band": "8-21",
                    "dow_type": "weekday",
                    "bucket_key": "8-21|weekday|up",
                    "decision_occ": 50,
                    "final_occ": 30.0,
                    "baseline_occ": 60.0,
                    "verdict": "hurt",
                    "measured_at": now,
                })
            return rt_id, orig_rate

        rt_id, orig_rate = loop.run_until_complete(seed())

        try:
            # Run learn cycle
            r = api.post(f"{BASE_URL}/api/revenue-brain/{pid}/learn", timeout=60)
            assert r.status_code == 200, r.text[:300]

            # Verify learned_pricing_weights has 0.95 factor
            async def check_weight():
                w = await db.learned_pricing_weights.find_one(
                    {"property_id": pid, "bucket_key": "8-21|weekday|up"}, {"_id": 0})
                return w
            w = loop.run_until_complete(check_weight())
            assert w is not None, "learned weight not created"
            assert w["factor"] == 0.95, f"expected 0.95 got {w['factor']}"

            # Get suggestions and verify learned_mult=0.95 for at least one weekday 8-21 up
            r = api.get(f"{BASE_URL}/api/revenue/ai-pricing/{pid}/suggestions",
                        params={"days": 21, "use_llm": "false"}, timeout=90)
            assert r.status_code == 200, r.text[:300]
            items = r.json().get("items") or r.json().get("suggestions") or []
            assert len(items) > 0, "no suggestions returned"
            # Check fields present
            first = items[0]
            assert "str_mult" in first, "regression: str_mult missing"
            assert "learned_mult" in first, "regression: learned_mult missing"

            # Find weekday 8-21 up suggestion with learned_mult=0.95
            matched = [it for it in items
                       if it.get("learned_mult") == 0.95
                       and it.get("learned_bucket") == "8-21|weekday|up"]
            assert len(matched) >= 1, f"no suggestion with learned_mult 0.95 & bucket 8-21|weekday|up. Sample: {items[0]}"

            # Verify status lessons include Turkish 'frenliyor'
            r = api.get(f"{BASE_URL}/api/revenue-brain/{pid}/status", timeout=30)
            assert r.status_code == 200
            lessons_text = " ".join(l.get("lesson", "") for l in r.json().get("lessons", []))
            assert "frenliyor" in lessons_text, f"missing 'frenliyor' lesson. Got: {lessons_text[:400]}"

        finally:
            # CLEANUP
            async def cleanup():
                await db.ai_pricing_outcomes.delete_many(
                    {"property_id": pid, "room_type_id": "TEST_BRAIN"})
                await db.learned_pricing_weights.delete_many({"property_id": pid})
                if rt_id:
                    await db.room_types.update_one(
                        {"id": rt_id}, {"$set": {"base_rate": orig_rate}})
            loop.run_until_complete(cleanup())
            # Re-run learn to normalize
            api.post(f"{BASE_URL}/api/revenue-brain/{pid}/learn", timeout=60)


# ---------- Cron evidence ----------
class TestCronEvidence:
    def test_brain_state_entries(self, db, loop):
        async def q():
            return await db.revenue_brain_state.find({}, {"_id": 0}).to_list(50)
        docs = loop.run_until_complete(q())
        assert len(docs) >= 1, "no revenue_brain_state entries"
        for d in docs:
            assert d.get("last_cycle_at"), f"missing last_cycle_at in {d}"


# ---------- Strategist lessons code path ----------
class TestStrategistLessonsCode:
    def test_prompt_includes_lessons(self):
        with open("/app/backend/routes/revenue_ext/revenue_strategist.py") as f:
            src = f.read()
        assert "ÖĞRENİLMİŞ DERSLER" in src, "strategist prompt lacks ÖĞRENİLMİŞ DERSLER injection"
        assert "revenue_brain_lessons" in src, "strategist not reading brain lessons"


# ---------- Regression ----------
class TestRegression:
    def test_ai_pricing_suggestions_default(self, api):
        r = api.get(f"{BASE_URL}/api/revenue/ai-pricing/default/suggestions",
                    params={"days": 14, "use_llm": "false"}, timeout=90)
        assert r.status_code == 200
        items = r.json().get("items") or r.json().get("suggestions") or []
        if items:
            it = items[0]
            assert "str_mult" in it
            assert "learned_mult" in it
