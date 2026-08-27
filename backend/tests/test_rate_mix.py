"""Rate Mix (Fiyat Karışımı) tests — iteration 588."""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://review-hub-108.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASS = "HotelAdmin2026!"
PID = "aldgate-flats"


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=20)
    assert r.status_code == 200, r.text
    j = r.json()
    tok = j.get("token") or j.get("access_token")
    assert tok
    return tok


@pytest.fixture(scope="module")
def h(token):
    return {"Authorization": f"Bearer {token}"}


# ---------------- GET all ----------------
def test_rate_mix_all(h):
    r = requests.get(f"{BASE_URL}/api/rate-mix/all?days=365", headers=h, timeout=60)
    assert r.status_code == 200, r.text
    j = r.json()
    assert isinstance(j.get("properties"), list) and len(j["properties"]) >= 1
    assert j.get("days") == 365
    seen_rec = False
    for p in j["properties"]:
        assert p["property_id"] and p["name"]
        tiers = p["tiers"]
        assert len(tiers) == 3
        # order floor/mid/high
        assert [t["tier"] for t in tiers] == ["floor", "mid", "high"]
        # share_pct sums ~100
        s = sum(t["share_pct"] for t in tiers)
        assert 98.0 <= s <= 102.0, f"share sum {s}"
        # avg_rate ascending
        rates = [t["avg_rate"] for t in tiers if t["avg_rate"]]
        assert rates == sorted(rates), f"avg_rate not ascending: {rates}"
        assert "adr" in p and "lmf" in p and "rooms" in p and "occ_pct" in p and "sample" in p
        rec = p.get("recommendation")
        if rec:
            seen_rec = True
            assert rec["uplift_pct"] > 0
            assert rec["floor_rate"] <= rec["sweet_spot"] <= rec["high_rate"] + 0.01
            assert isinstance(rec["message"], str) and "%" in rec["message"]
            # Turkish
            assert any(w in rec["message"] for w in ["taban", "gelir", "tarih"])
        # if floor share < 45 → rec must be None
        if tiers[0]["share_pct"] < 45:
            assert rec is None
    assert seen_rec, "expected at least one recommendation"


def test_rate_mix_single_property(h):
    r = requests.get(f"{BASE_URL}/api/rate-mix/{PID}?days=365", headers=h, timeout=30)
    assert r.status_code == 200
    j = r.json()
    assert len(j["properties"]) == 1
    assert j["properties"][0]["property_id"] == PID


def test_rate_mix_nonexistent_404(h):
    r = requests.get(f"{BASE_URL}/api/rate-mix/nonexistent-prop-xyz", headers=h, timeout=30)
    assert r.status_code == 404


def test_rate_mix_days_clamp(h):
    r = requests.get(f"{BASE_URL}/api/rate-mix/all?days=10", headers=h, timeout=60)
    assert r.status_code == 200
    assert r.json()["days"] == 30
    r2 = requests.get(f"{BASE_URL}/api/rate-mix/all?days=9999", headers=h, timeout=60)
    assert r2.status_code == 200
    assert r2.json()["days"] == 730


def test_rate_mix_days_changes_window(h):
    a = requests.get(f"{BASE_URL}/api/rate-mix/{PID}?days=365", headers=h, timeout=30).json()
    b = requests.get(f"{BASE_URL}/api/rate-mix/{PID}?days=90", headers=h, timeout=30).json()
    assert a["properties"][0]["sample"]["days"] == 365
    assert b["properties"][0]["sample"]["days"] == 90


# ---------------- Auth ----------------
def test_apply_requires_auth():
    r = requests.post(f"{BASE_URL}/api/rate-mix/{PID}/apply",
                      json={"rate": 158, "start_offset": 14, "end_offset": 20}, timeout=20)
    assert r.status_code in (401, 403)


def test_apply_invalid_rate(h):
    r = requests.post(f"{BASE_URL}/api/rate-mix/{PID}/apply",
                      json={"rate": 0, "start_offset": 14, "end_offset": 20},
                      headers=h, timeout=20)
    assert r.status_code == 422


# ---------------- Apply flow ----------------
def test_apply_writes_and_scales(h):
    from motor.motor_asyncio import AsyncIOMotorClient
    import asyncio
    payload = {"rate": 158, "start_offset": 14, "end_offset": 20}
    r = requests.post(f"{BASE_URL}/api/rate-mix/{PID}/apply", json=payload, headers=h, timeout=60)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["ok"] is True
    assert j["written"] >= 1
    assert "skipped" in j
    written_1 = j["written"]

    # verify DB directly
    async def _check():
        cli = AsyncIOMotorClient(os.environ.get("MONGO_URL"))
        db = cli[os.environ.get("DB_NAME", "test_database")]
        docs = await db.rate_overrides.find(
            {"property_id": PID, "set_by": "rate-mix"}, {"_id": 0}).to_list(500)
        rts = await db.room_types.find({"property_id": PID}, {"_id": 0}).to_list(50)
        cli.close()
        return docs, rts

    docs, rts = asyncio.get_event_loop().run_until_complete(_check())
    assert len(docs) >= 1
    # Scaling check: cheapest room ~= 158, others scaled up
    if rts:
        min_bp = min(float(r.get("base_price") or 158) for r in rts)
        by_rt = {r["id"]: float(r.get("base_price") or min_bp) for r in rts}
        for d in docs[:5]:
            bp = by_rt.get(d["room_type_id"], min_bp)
            expected = round(158 * (bp / min_bp), 0)
            assert abs(d["custom_rate"] - expected) <= 1, f"scaling off: {d['custom_rate']} vs {expected}"

    # idempotent re-apply
    r2 = requests.post(f"{BASE_URL}/api/rate-mix/{PID}/apply", json=payload, headers=h, timeout=60)
    assert r2.status_code == 200
    # same or more (overwrites its own)
    assert r2.json()["written"] >= 1


def test_apply_skips_human_overrides(h):
    """Insert a human-set override then apply and confirm skipped."""
    from motor.motor_asyncio import AsyncIOMotorClient
    import asyncio
    from datetime import date, timedelta

    day = (date.today() + timedelta(days=15)).isoformat()

    async def _seed():
        cli = AsyncIOMotorClient(os.environ.get("MONGO_URL"))
        db = cli[os.environ.get("DB_NAME", "test_database")]
        rt = await db.room_types.find_one({"property_id": PID}, {"_id": 0, "id": 1})
        rt_id = (rt or {}).get("id", "")
        # human — email set_by
        await db.rate_overrides.update_one(
            {"property_id": PID, "room_type_id": rt_id, "date": day},
            {"$set": {"custom_rate": 999.0, "set_by": "human@test.com",
                      "reason": "manual test"}}, upsert=True)
        cli.close()
        return rt_id

    rt_id = asyncio.get_event_loop().run_until_complete(_seed())
    r = requests.post(f"{BASE_URL}/api/rate-mix/{PID}/apply",
                      json={"rate": 158, "start_offset": 15, "end_offset": 15},
                      headers=h, timeout=30)
    assert r.status_code == 200
    j = r.json()
    assert j["skipped"] >= 1

    async def _verify():
        cli = AsyncIOMotorClient(os.environ.get("MONGO_URL"))
        db = cli[os.environ.get("DB_NAME", "test_database")]
        d = await db.rate_overrides.find_one(
            {"property_id": PID, "room_type_id": rt_id, "date": day}, {"_id": 0})
        # cleanup
        await db.rate_overrides.delete_one({"property_id": PID, "room_type_id": rt_id, "date": day})
        cli.close()
        return d

    d = asyncio.get_event_loop().run_until_complete(_verify())
    assert d and d.get("set_by") == "human@test.com", f"human override overwritten: {d}"
    assert d["custom_rate"] == 999.0


def test_reprice_bridge_event(h):
    # fire apply
    requests.post(f"{BASE_URL}/api/rate-mix/{PID}/apply",
                  json={"rate": 160, "start_offset": 14, "end_offset": 16},
                  headers=h, timeout=30)
    # bridge is async ~2-3s
    time.sleep(4)
    r = requests.get(f"{BASE_URL}/api/reprice-bridge/{PID}/events", headers=h, timeout=20)
    if r.status_code != 200:
        pytest.skip(f"reprice-bridge not accessible: {r.status_code}")
    ev = r.json()
    # accept various shapes
    events = ev.get("events") or ev.get("items") or (ev if isinstance(ev, list) else [])
    joined = str(events)
    assert "rate_mix_apply" in joined, f"missing rate_mix_apply in {joined[:400]}"


def test_applies_history(h):
    r = requests.get(f"{BASE_URL}/api/rate-mix/{PID}/applies", headers=h, timeout=20)
    assert r.status_code == 200
    assert isinstance(r.json().get("applies"), list)
    assert len(r.json()["applies"]) >= 1
