"""
Iteration 434 regression tests — VCC recovery, guest incidents, chain benchmark,
weekly report, ROI time-saved + VCC row, team chat translate, HK my-tasks smoke,
and legacy smoke checks (iter 432/433 features).
"""
import os
import time
import uuid
import pytest
import requests
from datetime import datetime, timezone, date, timedelta
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"

# Load backend env for direct DB seeding (test-only, does not modify prod config)
def _load_backend_env():
    env = {}
    try:
        with open("/app/backend/.env") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    except Exception:
        pass
    return env

_ENV = _load_backend_env()
_MONGO = MongoClient(_ENV.get("MONGO_URL", "mongodb://localhost:27017"))
DB = _MONGO[_ENV.get("DB_NAME", "test_database")]

ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASS = "HotelAdmin2026!"
HK_EMAIL = "testhk@hotelbox.com"
HK_PASS = "Test2026!"

PID = "aldgate-flats"
VRQA = "vrqa2-"
REGQA = "regqa"


def _now():
    return datetime.now(timezone.utc).isoformat()


@pytest.fixture(scope="session")
def admin_token():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="session")
def hk_token():
    r = requests.post(f"{API}/auth/login", json={"email": HK_EMAIL, "password": HK_PASS}, timeout=15)
    if r.status_code != 200:
        pytest.skip(f"HK login failed: {r.status_code} {r.text[:200]}")
    return r.json()["token"]


@pytest.fixture(scope="session")
def admin_h(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


# ==============================================================
# 1. VCC GELİR KURTARMA (backend + cleanup)
# ==============================================================

@pytest.fixture(scope="module")
def seed_vcc(admin_h):
    today = date.today()
    y3 = (today - timedelta(days=3)).isoformat()
    ci = today.isoformat()
    co = (today + timedelta(days=2)).isoformat()

    docs = [
        ("bookings", {"id": f"{VRQA}bk-a", "property_id": PID, "guest_email": f"{VRQA}a@t.com",
                      "guest_name": "VRQA A", "status": "confirmed", "total_price": 200,
                      "check_in": ci, "check_out": co}),
        ("vcc_cards", {"id": f"{VRQA}c-a", "booking_id": f"{VRQA}bk-a", "property_id": PID,
                       "guest_name": "VRQA A", "channel": "booking.com", "currency": "GBP",
                       "amount": 200, "status": "pending", "activation_date": y3,
                       "expiry_date": co, "attempts": 0}),
        ("bookings", {"id": f"{VRQA}bk-b", "property_id": PID, "guest_email": f"{VRQA}b@t.com",
                      "guest_name": "VRQA B", "status": "confirmed", "total_price": 150,
                      "check_in": ci, "check_out": co}),
        ("vcc_cards", {"id": f"{VRQA}c-b", "booking_id": f"{VRQA}bk-b", "property_id": PID,
                       "guest_name": "VRQA B", "channel": "expedia", "currency": "GBP",
                       "amount": 150, "status": "expired", "activation_date": y3,
                       "expiry_date": y3}),
        ("bookings", {"id": f"{VRQA}bk-c", "property_id": PID, "guest_email": f"{VRQA}c@t.com",
                      "guest_name": "VRQA C", "status": "confirmed", "total_price": 260,
                      "check_in": ci, "check_out": co}),
        ("vcc_cards", {"id": f"{VRQA}c-c", "booking_id": f"{VRQA}bk-c", "property_id": PID,
                       "guest_name": "VRQA C", "channel": "booking.com", "currency": "GBP",
                       "amount": 200, "status": "pending", "activation_date": ci,
                       "expiry_date": co}),
        ("bookings", {"id": f"{VRQA}bk-d", "property_id": PID, "guest_email": f"{VRQA}d@t.com",
                      "guest_name": "VRQA D", "status": "cancelled", "total_price": 300,
                      "check_in": ci, "check_out": co, "cancelled_at": _now()}),
        ("vcc_cards", {"id": f"{VRQA}c-d", "booking_id": f"{VRQA}bk-d", "property_id": PID,
                       "guest_name": "VRQA D", "channel": "booking.com", "currency": "GBP",
                       "amount": 300, "status": "pending", "activation_date": y3,
                       "expiry_date": co}),
    ]
    for coll, doc in docs:
        DB[coll].replace_one({"id": doc["id"]}, doc, upsert=True)

    yield

    for coll, doc in docs:
        DB[coll].delete_one({"id": doc["id"]})
    DB.ota_disputes.delete_many({"vcc_id": {"$regex": f"^{VRQA}"}})


class TestVccRecovery:
    def test_scan_returns_all_4_types(self, admin_h, seed_vcc):
        r = requests.get(f"{API}/vcc-recovery/{PID}/scan", headers=admin_h, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        my_items = [i for i in data.get("items", []) if i["vcc_id"].startswith(VRQA)]
        types = {i["type"] for i in my_items}
        assert {"missed_charge", "expired", "underfunded", "cancel_fee"} <= types, f"got types: {types}"
        # underfunded amt = 60
        uf = next(i for i in my_items if i["type"] == "underfunded")
        assert abs(uf["recoverable"] - 60.0) < 0.01
        cf = next(i for i in my_items if i["type"] == "cancel_fee")
        assert abs(cf["recoverable"] - 150.0) < 0.01
        assert data["total_recoverable"] >= sum(i["recoverable"] for i in my_items) - 0.01

    def test_dispute_flow(self, admin_h, seed_vcc):
        vid = f"{VRQA}c-b"
        r = requests.post(f"{API}/vcc-recovery/dispute/{vid}",
                          json={"type": "expired", "amount": 150, "reason": "test qa"},
                          headers=admin_h, timeout=15)
        assert r.status_code == 200, r.text
        did = r.json()["id"]
        # duplicate → 400
        r2 = requests.post(f"{API}/vcc-recovery/dispute/{vid}",
                           json={"type": "expired", "amount": 150, "reason": "x"},
                           headers=admin_h, timeout=15)
        assert r2.status_code == 400, r2.text
        # resolve recovered
        r3 = requests.post(f"{API}/vcc-recovery/dispute/{did}/resolve",
                           json={"outcome": "recovered", "amount": 150}, headers=admin_h, timeout=15)
        assert r3.status_code == 200, r3.text
        assert r3.json().get("status") == "recovered"
        # rescan excludes disputed
        rs = requests.get(f"{API}/vcc-recovery/{PID}/scan", headers=admin_h, timeout=15).json()
        assert not any(i["vcc_id"] == vid for i in rs.get("items", []))
        assert rs.get("recovered_to_date", 0) >= 150

    def test_disputes_list(self, admin_h, seed_vcc):
        r = requests.get(f"{API}/vcc-recovery/{PID}/disputes", headers=admin_h, timeout=15)
        assert r.status_code == 200, r.text
        assert "disputes" in r.json()


# ==============================================================
# 3. ROI VCC row + time-saved
# ==============================================================

class TestRoiTimeSaved:
    def test_roi_all_has_vcc_recovery(self, admin_h):
        r = requests.get(f"{API}/automation/roi/all?days=30", headers=admin_h, timeout=20)
        assert r.status_code == 200, r.text
        rows = r.json().get("rows", [])
        keys = {row.get("key") for row in rows}
        assert "vcc_recovery" in keys
        vcc = next(row for row in rows if row["key"] == "vcc_recovery")
        assert isinstance(vcc.get("count"), (int, float))
        assert isinstance(vcc.get("revenue"), (int, float))

    def test_time_saved(self, admin_h):
        r = requests.get(f"{API}/automation/roi/all/time-saved?days=30", headers=admin_h, timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "hours_saved" in d
        assert "fte_equivalent" in d


# ==============================================================
# 4. Weekly report
# ==============================================================

class TestWeeklyReport:
    def test_preview_has_automation_wins(self, admin_h):
        r = requests.get(f"{API}/reports/weekly-management/preview/all", headers=admin_h, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        aw = d.get("automation_wins")
        assert isinstance(aw, dict)
        for k in ("rows", "total_actions", "money_touched", "hours_saved"):
            assert k in aw, f"missing key {k}"

    def test_send_mock(self, admin_h):
        r = requests.post(f"{API}/reports/weekly-management/send",
                          json={"property_id": "all", "force": True}, headers=admin_h, timeout=60)
        assert r.status_code == 200, r.text
        assert r.json().get("ok") is True


# ==============================================================
# 5. Chain benchmark
# ==============================================================

class TestChainBenchmark:
    def test_benchmark(self, admin_h):
        r = requests.get(f"{API}/chain/benchmark?days=30", headers=admin_h, timeout=45)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "properties" in d
        assert "chain" in d
        if d["properties"]:
            row = d["properties"][0]
            for k in ("rank", "score", "occupancy", "adr", "revpar", "review", "quality", "automation", "badges", "actions"):
                assert k in row, f"missing {k}"
            assert 0 <= row["score"] <= 100
            for act in row["actions"]:
                assert "view" in act


# ==============================================================
# 6. Guest incidents + returning
# ==============================================================

@pytest.fixture(scope="module")
def seed_returning_booking(admin_h):
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    booking = {"id": f"{REGQA}-b1", "property_id": PID, "guest_email": "regqa@test.com",
               "guest_name": "Reg QA", "status": "confirmed", "total_price": 100,
               "check_in": tomorrow, "check_out": (date.today() + timedelta(days=3)).isoformat()}
    DB.bookings.replace_one({"id": booking["id"]}, booking, upsert=True)
    yield booking
    DB.bookings.delete_one({"id": booking["id"]})
    DB.guest_incidents.delete_many({"guest_email": "regqa@test.com"})
    DB.shift_handover.delete_many({"content": {"$regex": "Reg QA|regqa"}})
    DB.notifications.delete_many({"category": "returning_guest",
                                  "title": {"$regex": "Reg QA|regqa"}})


class TestGuestIncidents:
    incident_id = None

    def test_create_incident_creates_handover(self, admin_h, seed_returning_booking):
        r = requests.post(f"{API}/guest-incidents", json={
            "guest_email": "regqa@test.com", "guest_name": "Reg QA", "severity": "high",
            "text": "Astımı var - tüy yastık kullanmayın", "handover": True, "property_id": PID,
        }, headers=admin_h, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["status"] == "open"
        TestGuestIncidents.incident_id = d["id"]

    def test_by_guest(self, admin_h):
        r = requests.get(f"{API}/guest-incidents/by-guest/regqa@test.com", headers=admin_h, timeout=10)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["incident_count"] >= 1
        assert d["open_incidents"] >= 1

    def test_watch_run_idempotent(self, admin_h, seed_returning_booking):
        r1 = requests.post(f"{API}/guest-incidents/watch-run/{PID}", headers=admin_h, timeout=20)
        assert r1.status_code == 200, r1.text
        first_flagged = r1.json().get("newly_flagged", 0)
        assert first_flagged >= 1
        r2 = requests.post(f"{API}/guest-incidents/watch-run/{PID}", headers=admin_h, timeout=20)
        assert r2.status_code == 200
        assert r2.json().get("newly_flagged", 0) == 0

    def test_returning_list(self, admin_h):
        r = requests.get(f"{API}/guest-incidents/returning/{PID}", headers=admin_h, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        emails = [g.get("guest_email") for g in d.get("guests", [])]
        assert "regqa@test.com" in emails

    def test_resolve(self, admin_h):
        iid = TestGuestIncidents.incident_id
        if not iid:
            pytest.skip("no incident id")
        r = requests.put(f"{API}/guest-incidents/{iid}/resolve", headers=admin_h, timeout=10)
        assert r.status_code == 200, r.text


# ==============================================================
# 8. Team chat translate
# ==============================================================

@pytest.fixture(scope="module")
def seed_chat(admin_h):
    r = requests.post(f"{API}/team-chat/channels", json={
        "name": "regqa-ceviri", "kind": "general", "department": "",
        "property_id": "all", "members": [], "description": "qa"
    }, headers=admin_h, timeout=10)
    if r.status_code not in (200, 201):
        pytest.skip(f"create channel failed: {r.status_code} {r.text[:200]}")
    ch = r.json()
    cid = ch["id"]

    m1 = requests.post(f"{API}/team-chat/channels/{cid}/messages",
                       json={"body": "Oda 101 musluk damlatıyor"}, headers=admin_h, timeout=10)
    m2 = requests.post(f"{API}/team-chat/channels/{cid}/messages",
                       json={"body": "Please restock minibar in 202"}, headers=admin_h, timeout=10)
    assert m1.status_code in (200, 201), m1.text
    assert m2.status_code in (200, 201), m2.text
    yield cid
    # cleanup
    try:
        requests.delete(f"{API}/team-chat/channels/{cid}", headers=admin_h, timeout=10)
    except Exception:
        pass
    DB.chat_messages.delete_many({"channel_id": cid})
    DB.chat_channels.delete_many({"id": cid})


class TestTeamChatTranslate:
    def test_translate_en(self, admin_h, seed_chat):
        cid = seed_chat
        r = requests.post(f"{API}/team-chat/channels/{cid}/translate",
                          json={"lang": "en"}, headers=admin_h, timeout=60)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["lang"] == "en"
        assert isinstance(d.get("translations"), dict)
        assert len(d["translations"]) >= 1

    def test_translate_cache_fast(self, admin_h, seed_chat):
        cid = seed_chat
        t0 = time.time()
        r = requests.post(f"{API}/team-chat/channels/{cid}/translate",
                          json={"lang": "en"}, headers=admin_h, timeout=30)
        assert r.status_code == 200
        # cached should be well under 5s
        assert time.time() - t0 < 10

    def test_translate_bad_lang(self, admin_h, seed_chat):
        cid = seed_chat
        r = requests.post(f"{API}/team-chat/channels/{cid}/translate",
                          json={"lang": "xx"}, headers=admin_h, timeout=10)
        assert r.status_code == 400


# ==============================================================
# 9. HK My tasks smoke
# ==============================================================

class TestMyTasksHk:
    def test_hk_my_tasks(self, hk_token):
        h = {"Authorization": f"Bearer {hk_token}"}
        r = requests.get(f"{API}/my-tasks", headers=h, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "hk_tasks" in d
        summary = d.get("summary", {})
        assert "hk_open" in summary
        assert "hk_urgent" in summary


# ==============================================================
# 10. Regression smoke
# ==============================================================

SMOKE_ENDPOINTS = [
    "/automation/settings",
    "/ar-agent/overview",
    "/waitlist/all",
    "/inbox/agent/config",
    "/hk-dispatch/all/board",
    "/res-quality/all?days=7",
    "/lost-found/all",
]


@pytest.mark.parametrize("ep", SMOKE_ENDPOINTS)
def test_smoke_endpoint(admin_h, ep):
    r = requests.get(f"{API}{ep}", headers=admin_h, timeout=20)
    assert r.status_code == 200, f"{ep} → {r.status_code}: {r.text[:200]}"
    if ep == "/automation/settings":
        d = r.json()
        # locate motors list
        motors = d.get("motors") or d.get("settings") or d
        # Just search substrings in the raw text response
        text = r.text
        assert "returning_guest_watch" in text
        assert "vcc_recovery" in text
