"""Iteration 577 — Test:
   1) Public signup: trial_ends_at ~14d ahead, welcome email mocked in email_outbox.
   2) Channel Listings (Kanal Listing Açma): draft -> submit -> in_review -> live (mock 60s).
   3) Tenant isolation on /api/data-quality/summary/all: user scoped to own pid; admin sees 13+.
"""
import os
import time
import uuid
import pytest
import requests
from datetime import datetime, timezone

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASS = "HotelAdmin2026!"


# ---------------- fixtures ----------------
@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=30)
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def signup_user():
    """Create a self-signup account (only ONE per module — rate limit is 3/IP/10min)."""
    suffix = uuid.uuid4().hex[:6]
    email = f"iter577_{suffix}@test.com"
    hotel = f"Iter577 Otel {suffix}"
    body = {"hotel_name": hotel, "name": "Iter 577 Owner",
            "email": email, "password": "Sifre12345", "plan": "cm"}
    r = requests.post(f"{BASE_URL}/api/auth/signup", json=body, timeout=30)
    assert r.status_code == 200, f"signup failed: {r.status_code} {r.text}"
    d = r.json()
    return {"email": email, "token": d["token"], "pid": d["property_id"],
            "hotel": hotel, "plan": d["plan"]}


# ---------------- (1) Signup + trial + welcome email ----------------
class TestSignupTrialWelcome:
    def test_signup_returns_token_and_pid(self, signup_user):
        assert signup_user["token"]
        assert signup_user["pid"]
        assert signup_user["plan"] == "cm"

    def test_property_has_trial_ends_at_14d(self, signup_user):
        # GET /properties with user token — should return ONLY their property
        r = requests.get(f"{BASE_URL}/api/properties",
                         headers={"Authorization": f"Bearer {signup_user['token']}"}, timeout=30)
        assert r.status_code == 200
        props = r.json()
        assert isinstance(props, list) and len(props) == 1, f"expected 1 prop, got {len(props)}"
        p = props[0]
        assert p["id"] == signup_user["pid"]
        assert "trial_ends_at" in p and p["trial_ends_at"]
        te = datetime.fromisoformat(p["trial_ends_at"])
        delta_days = (te - datetime.now(timezone.utc)).total_seconds() / 86400.0
        assert 13.5 < delta_days < 14.5, f"trial_ends_at not ~14d away: {delta_days}"

    def test_welcome_email_mocked_in_outbox(self, signup_user):
        # Admin visibility — use direct mongo via a debug endpoint? Instead use pymongo.
        from pymongo import MongoClient
        m = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
        db = m[os.environ.get("DB_NAME", "test_database")]
        doc = db.email_outbox.find_one({"to": signup_user["email"], "kind": "welcome"})
        assert doc is not None, "welcome email doc not found in outbox"
        assert doc.get("status") == "mocked", f"expected 'mocked', got {doc.get('status')}"
        assert signup_user["hotel"] in (doc.get("subject") or "")
        m.close()


# ---------------- (2) Channel Listings flow ----------------
class TestChannelListings:
    def test_missing_description_400(self, signup_user):
        r = requests.post(f"{BASE_URL}/api/cm/listings/{signup_user['pid']}",
                          headers={"Authorization": f"Bearer {signup_user['token']}"},
                          json={"channel_id": "airbnb", "content": {}}, timeout=30)
        assert r.status_code == 400, f"expected 400 got {r.status_code}: {r.text}"

    def test_invalid_channel_422(self, signup_user):
        r = requests.post(f"{BASE_URL}/api/cm/listings/{signup_user['pid']}",
                          headers={"Authorization": f"Bearer {signup_user['token']}"},
                          json={"channel_id": "nope_channel", "content": {"description": "x"}},
                          timeout=30)
        assert r.status_code == 422, f"expected 422 got {r.status_code}: {r.text}"

    def test_create_listing_draft(self, signup_user):
        r = requests.post(f"{BASE_URL}/api/cm/listings/{signup_user['pid']}",
                          headers={"Authorization": f"Bearer {signup_user['token']}"},
                          json={"channel_id": "airbnb", "content": {"description": "Cozy hotel"}},
                          timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["ok"] is True
        lst = d["listing"]
        assert lst["status"] == "draft"
        assert lst["channel_id"] == "airbnb"
        assert len(lst["timeline"]) == 1 and lst["timeline"][0]["step"] == "draft"
        # stash id for next tests
        signup_user["_lid"] = lst["id"]

    def test_submit_listing(self, signup_user):
        lid = signup_user["_lid"]
        r = requests.post(f"{BASE_URL}/api/cm/listings/{signup_user['pid']}/{lid}/submit",
                          headers={"Authorization": f"Bearer {signup_user['token']}"}, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["status"] == "in_review"
        assert d["mocked"] is True
        # verify timeline via GET
        g = requests.get(f"{BASE_URL}/api/cm/listings/{signup_user['pid']}",
                         headers={"Authorization": f"Bearer {signup_user['token']}"}, timeout=30)
        rec = next((x for x in g.json()["listings"] if x["id"] == lid), None)
        assert rec is not None
        steps = [t["step"] for t in rec["timeline"]]
        assert steps == ["draft", "submitted", "in_review"]

    def test_submit_again_400(self, signup_user):
        lid = signup_user["_lid"]
        r = requests.post(f"{BASE_URL}/api/cm/listings/{signup_user['pid']}/{lid}/submit",
                          headers={"Authorization": f"Bearer {signup_user['token']}"}, timeout=30)
        assert r.status_code == 400, r.text

    def test_auto_progress_to_live_after_60s(self, signup_user):
        # We already submitted a few seconds ago; wait until >60s from submission.
        lid = signup_user["_lid"]
        # wait a bit less than 65s if some tests ran in between
        time.sleep(65)
        g = requests.get(f"{BASE_URL}/api/cm/listings/{signup_user['pid']}",
                         headers={"Authorization": f"Bearer {signup_user['token']}"}, timeout=30)
        assert g.status_code == 200
        rec = next((x for x in g.json()["listings"] if x["id"] == lid), None)
        assert rec is not None
        assert rec["status"] == "live", f"expected live, got {rec['status']}"
        assert rec["timeline"][-1]["step"] == "live"


# ---------------- (3) Tenant isolation on /api/data-quality/summary/all ----------------
class TestDataQualitySummaryScoping:
    def test_signup_user_only_own_pid(self, signup_user):
        r = requests.get(f"{BASE_URL}/api/data-quality/summary/all",
                         headers={"Authorization": f"Bearer {signup_user['token']}"}, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        # payload could be {properties:[...]} or list. Handle both.
        props = data.get("properties") if isinstance(data, dict) else data
        assert isinstance(props, list) and len(props) == 1, f"expected 1 prop got {len(props)}"
        pid = props[0].get("property_id") or props[0].get("id")
        assert pid == signup_user["pid"], f"expected {signup_user['pid']} got {pid}"

    def test_admin_sees_13_plus_properties(self, admin_token):
        r = requests.get(f"{BASE_URL}/api/data-quality/summary/all",
                         headers={"Authorization": f"Bearer {admin_token}"}, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        props = data.get("properties") if isinstance(data, dict) else data
        assert isinstance(props, list)
        assert len(props) >= 13, f"admin should see 13+ props got {len(props)}"


# ---------------- cleanup: mandatory ----------------
def test_zzz_cleanup(signup_user):
    """Delete signup test tenant + pre-existing 'trial-test-otel-263ce8' + all 'mock-mail-otel-*'."""
    from pymongo import MongoClient
    m = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
    db = m[os.environ.get("DB_NAME", "test_database")]

    # collect pids to purge
    pids_to_delete = {signup_user["pid"], "trial-test-otel-263ce8"}
    # also gather mock-mail-otel-* pids
    for p in db.properties.find({"id": {"$regex": "^mock-mail-otel-"}}, {"id": 1}):
        pids_to_delete.add(p["id"])
    # any leftover iter577 pids
    for p in db.properties.find({"name": {"$regex": "Iter577"}}, {"id": 1}):
        pids_to_delete.add(p["id"])

    pids = list(pids_to_delete)
    print(f"cleanup pids: {pids}")

    coll_names = ["properties", "room_types", "rate_plans", "channel_connections",
                  "channel_mappings", "cm_setup", "channel_listings", "push_history",
                  "bookings", "rate_overrides", "price_guard_log"]
    for cname in coll_names:
        db[cname].delete_many({"property_id": {"$in": pids}})
    # users tied to these pids
    db.users.delete_many({"property_ids": {"$in": pids}})
    # welcome email_outbox docs
    db.email_outbox.delete_many({"kind": "welcome", "property_id": {"$in": pids}})
    # signup_log for these emails
    db.signup_log.delete_many({"property_id": {"$in": pids}})

    # ensure default plan preserved
    default = db.properties.find_one({"id": "default"})
    if default and default.get("plan") != "full":
        db.properties.update_one({"id": "default"}, {"$set": {"plan": "full"}})

    m.close()
