"""Iteration 433 - HK Auto-Dispatch + Res Quality + Time-Saved/FTE + Regression."""
import os
import re
import pytest
import requests
from datetime import datetime, timezone, timedelta
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv("/app/frontend/.env")
load_dotenv("/app/backend/.env")

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE}/api"
PID = "aldgate-flats"
TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")
TOMORROW = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%d")
DAY_AFTER = (datetime.now(timezone.utc) + timedelta(days=2)).strftime("%Y-%m-%d")

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]
_mc = MongoClient(MONGO_URL)
db = _mc[DB_NAME]


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{API}/auth/login",
                      json={"email": "admin@hotelbox.com", "password": "HotelAdmin2026!"})
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def H(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module", autouse=True)
def seed_and_cleanup():
    # Cleanup existing test data first
    db.bookings.delete_many({"id": {"$regex": "^hkd-qa"}})
    db.housekeeping_tasks.delete_many({"booking_id": {"$regex": "^hkd-qa"}})
    db.housekeeping_tasks.delete_many({"property_id": PID, "due_date": TODAY, "auto_dispatch": True, "room_number": {"$in": ["901", "902", "903"]}})
    db.bookings.delete_many({"id": {"$regex": "^rq-qa"}})
    db.guest_profiles.delete_many({"email": "rq-qa-profile@test.local"})

    # Seed HK dispatch: 3 checkouts (901/902/903) + 1 arrival on room 902
    now = datetime.now(timezone.utc).isoformat()
    checkouts = []
    for rn in ["901", "902", "903"]:
        checkouts.append({
            "id": f"hkd-qa-out-{rn}", "property_id": PID,
            "guest_name": f"QA Out {rn}", "guest_email": "", "guest_phone": "",
            "room_number": rn, "room_type": "Standard",
            "check_in": (datetime.now(timezone.utc) - timedelta(days=2)).strftime("%Y-%m-%d"),
            "check_out": TODAY, "status": "checked_out", "total_price": 100,
            "created_at": now,
        })
    checkouts.append({
        "id": "hkd-qa-in-902", "property_id": PID,
        "guest_name": "QA Arriving 902", "room_number": "902", "room_type": "Standard",
        "check_in": TODAY, "check_out": TOMORROW, "status": "confirmed", "total_price": 150,
        "created_at": now,
    })
    db.bookings.insert_many(checkouts)

    # Seed Res Quality: booking with missing email/phone + matching guest_profile
    db.guest_profiles.insert_one({
        "id": "rq-qa-prof-1", "name": "QA Profile Guest",
        "email": "rq-qa-profile@test.local", "phone": "+905551112233",
    })
    db.bookings.insert_one({
        "id": "rq-qa-booking-1", "property_id": PID,
        "guest_name": "QA Profile Guest", "guest_email": "", "guest_phone": "",
        "room_number": "710", "room_type": "Standard",
        "check_in": TOMORROW, "check_out": DAY_AFTER,
        "status": "confirmed", "total_price": 200, "created_at": now,
    })

    yield

    # Cleanup
    db.bookings.delete_many({"id": {"$regex": "^hkd-qa"}})
    db.housekeeping_tasks.delete_many({"booking_id": {"$regex": "^hkd-qa"}})
    db.housekeeping_tasks.delete_many({"property_id": PID, "due_date": TODAY, "auto_dispatch": True, "room_number": {"$in": ["901", "902", "903"]}})
    db.bookings.delete_many({"id": {"$regex": "^rq-qa"}})
    db.guest_profiles.delete_many({"email": "rq-qa-profile@test.local"})


# =========== HK AUTO-DISPATCH ===========
class TestHkDispatch:
    def test_run_dispatch(self, H):
        r = requests.post(f"{API}/hk-dispatch/{PID}/run", headers=H)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["tasks_created"] == 3, d
        assert d["urgent"] == 1, d
        assert d["housekeepers"] >= 4
        # Verify balanced across different housekeepers
        tasks = list(db.housekeeping_tasks.find(
            {"booking_id": {"$regex": "^hkd-qa"}}, {"_id": 0, "assigned_to": 1, "priority": 1, "room_number": 1}))
        assert len(tasks) == 3
        assigned = {t["assigned_to"] for t in tasks}
        assert len(assigned) >= 2, f"tasks not distributed: {tasks}"
        # Exactly one urgent, and it's room 902
        urgent = [t for t in tasks if t["priority"] == "urgent"]
        assert len(urgent) == 1
        assert urgent[0]["room_number"] == "902"

    def test_rerun_idempotent(self, H):
        r = requests.post(f"{API}/hk-dispatch/{PID}/run", headers=H)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["tasks_created"] == 0
        assert d["skipped_duplicates"] == 3

    def test_board(self, H):
        r = requests.get(f"{API}/hk-dispatch/{PID}/board", headers=H)
        assert r.status_code == 200, r.text
        b = r.json()
        assert "columns" in b and isinstance(b["columns"], list)
        assert "unassigned" in b and "counts" in b and "urgent_rooms" in b and "total" in b
        # 902 should be in urgent_rooms
        assert "902" in b["urgent_rooms"]
        for col in b["columns"]:
            assert set(col.keys()) >= {"name", "tasks", "open", "done", "minutes"}


# =========== RES QUALITY ===========
class TestResQuality:
    def test_scan_shape_and_clamp(self, H):
        r = requests.get(f"{API}/res-quality/{PID}?days=14", headers=H)
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("scanned", "clean", "with_issues", "quality_score", "by_code", "issues"):
            assert k in d
        # Our seed should appear as missing_email + missing_phone
        our = [i for i in d["issues"] if i["booking_id"] == "rq-qa-booking-1"]
        assert len(our) == 1, "seed missing from scan"
        codes = {p["code"] for p in our[0]["problems"]}
        assert "missing_email" in codes and "missing_phone" in codes

        # days clamp
        r2 = requests.get(f"{API}/res-quality/{PID}?days=200", headers=H)
        assert r2.status_code == 200
        assert r2.json()["days"] == 60
        r3 = requests.get(f"{API}/res-quality/{PID}?days=0", headers=H)
        assert r3.status_code == 200
        assert r3.json()["days"] == 1

    def test_autofix(self, H):
        r = requests.post(f"{API}/res-quality/{PID}/autofix", headers=H)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["fixed_email"] >= 1
        assert d["fixed_phone"] >= 1
        bk = db.bookings.find_one({"id": "rq-qa-booking-1"}, {"_id": 0})
        assert bk["guest_email"] == "rq-qa-profile@test.local"
        assert bk["guest_phone"] == "+905551112233"
        assert "quality_fixed_at" in bk


# =========== TIME-SAVED / FTE ===========
class TestTimeSaved:
    def test_time_saved_shape(self, H):
        r = requests.get(f"{API}/automation/roi/all/time-saved?days=30", headers=H)
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("days", "rows", "total_actions", "hours_saved", "fte_equivalent"):
            assert k in d
        assert d["days"] == 30
        # Consistency: hours_saved ~= sum(minutes) / 60
        total_min = sum(r["minutes"] for r in d["rows"])
        assert abs(d["hours_saved"] - round(total_min / 60, 1)) <= 0.2
        # FTE ~= hours / 160
        assert abs(d["fte_equivalent"] - round(d["hours_saved"] / 160, 2)) <= 0.05
        for row in d["rows"]:
            assert set(row.keys()) >= {"label", "minutes_each", "count", "minutes"}


# =========== AUTOMATION SETTINGS + SCHEDULER ===========
class TestAutomationSettings:
    def test_settings_23_motors(self, H):
        r = requests.get(f"{API}/automation/settings", headers=H)
        assert r.status_code == 200, r.text
        d = r.json()
        # Try common keys
        motors = d.get("jobs") or d.get("motors") or d.get("items")
        assert isinstance(motors, list), f"Unexpected shape: {str(d)[:200]}"
        keys = {m.get("job") or m.get("key") or m.get("id") for m in motors}
        assert "hk_dispatch" in keys, keys
        assert "res_quality" in keys, keys
        assert len(motors) >= 23, f"expected >=23, got {len(motors)}"

    def test_scheduler_trigger_hk_dispatch(self, H):
        r = requests.post(f"{API}/scheduler/trigger/all/hk_dispatch", headers=H)
        assert r.status_code == 200, r.text

    def test_scheduler_trigger_res_quality(self, H):
        r = requests.post(f"{API}/scheduler/trigger/all/res_quality", headers=H)
        assert r.status_code == 200, r.text


# =========== REGRESSION 432 ===========
class TestRegression432:
    def test_ar_overview(self, H):
        r = requests.get(f"{API}/ar-agent/overview", headers=H)
        assert r.status_code == 200, r.text

    def test_waitlist_all(self, H):
        r = requests.get(f"{API}/waitlist/all", headers=H)
        assert r.status_code == 200, r.text

    def test_nl_parse_short_400(self, H):
        r = requests.post(f"{API}/automation/v2/nl-parse", headers=H, json={"text": "hi"})
        assert r.status_code == 400, r.text

    def test_inbox_agent_config(self, H):
        r = requests.get(f"{API}/inbox/agent/config", headers=H)
        assert r.status_code == 200, r.text
