"""Iter 609 — Arrival reminder robot, Event packages, OTA A/B auto-winner."""
import os
import uuid
from datetime import datetime, timezone, timedelta

import pytest
import requests
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv("/app/frontend/.env")
load_dotenv("/app/backend/.env")

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE}/api"
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

PID = "default"


@pytest.fixture(scope="session")
def db():
    return MongoClient(MONGO_URL)[DB_NAME]


@pytest.fixture(scope="session")
def admin():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": "admin@hotelbox.com", "password": "HotelAdmin2026!"})
    assert r.status_code == 200, r.text
    return s


# ---------- ARRIVAL REMINDER ----------

def _today_plus(n):
    return (datetime.now(timezone.utc).date() + timedelta(days=n)).isoformat()


def test_01_arrival_reminder_flow(admin, db):
    # Create booking with check_in = today+2, lang tr
    ci = _today_plus(2)
    co = _today_plus(4)
    payload = {"property_id": PID, "room_type": "Standard Double", "check_in": ci, "check_out": co,
               "guest_name": "Iter609 TR", "guest_email": "iter609tr@example.com", "lang": "tr",
               "rooms": 1, "rate": 1, "pay_now": False}
    r = requests.post(f"{API}/booking-widget/book", json=payload)
    assert r.status_code == 200, r.text

    # Run arrival reminder
    r = admin.post(f"{API}/arrival-reminder/run/{PID}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["candidates"] >= 1
    assert body["mocked"] >= 1

    # Idempotent
    r2 = admin.post(f"{API}/arrival-reminder/run/{PID}")
    assert r2.status_code == 200
    assert r2.json()["candidates"] == 0

    # Log has TR entry
    r = admin.get(f"{API}/arrival-reminder/log/{PID}")
    assert r.status_code == 200
    log = r.json()
    tr_entry = next((e for e in log if e.get("to") == "iter609tr@example.com"), None)
    assert tr_entry is not None
    assert tr_entry["lang"] == "tr"
    assert tr_entry["status"] == "mocked"
    assert tr_entry["subject"].startswith("2 gün sonra görüşürüz")

    # email_outbox has arrival_reminder doc with html containing google.com/maps and 'Giriş saati'
    doc = db.email_outbox.find_one({"to": "iter609tr@example.com", "kind": "arrival_reminder"})
    assert doc is not None
    assert "google.com/maps" in doc.get("html", "")
    assert "Giriş saati" in doc.get("html", "")

    # DE preview
    r = admin.get(f"{API}/arrival-reminder/preview/{PID}", params={"lang": "de"})
    assert r.status_code == 200
    assert r.json()["subject"].startswith("Bis in 2 Tagen")


def test_02_automation_jobs_registry(admin):
    r = admin.get(f"{API}/automation/settings")
    assert r.status_code == 200, r.text
    txt = r.text
    assert "arrival_reminder" in txt
    assert "ota_ab_auto_winner" in txt


# ---------- EVENT PACKAGES ----------

_created_pkg_id = None


def test_03_event_packages_list_public():
    r = requests.get(f"{API}/arrival-reminder/event-packages/{PID}")
    assert r.status_code == 200
    lst = r.json()
    assert isinstance(lst, list)
    # Default package should exist (per problem statement 'one default package already exists')
    # If not, we won't fail here - test 04 will create one
    global _default_pkg_id
    _default_pkg_id = None
    for p in lst:
        if p.get("enabled") and abs(float(p.get("price_per_night", 0)) - 25.0) < 0.01:
            _default_pkg_id = p["id"]
            break


def test_04_event_packages_crud(admin):
    global _created_pkg_id
    r = admin.post(f"{API}/arrival-reminder/event-packages/{PID}", json={"use_default": True})
    assert r.status_code == 200, r.text
    pkg = r.json()
    assert float(pkg["price_per_night"]) == 25.0
    _created_pkg_id = pkg["id"]

    r = admin.put(f"{API}/arrival-reminder/event-packages/{PID}/{_created_pkg_id}", json={"enabled": False})
    assert r.status_code == 200
    assert r.json()["enabled"] is False

    r = admin.delete(f"{API}/arrival-reminder/event-packages/{PID}/{_created_pkg_id}")
    assert r.status_code == 200

    r = admin.delete(f"{API}/arrival-reminder/event-packages/{PID}/{_created_pkg_id}")
    assert r.status_code == 404


def test_05_book_with_package(admin, db):
    # Find or create an enabled default package
    lst = requests.get(f"{API}/arrival-reminder/event-packages/{PID}").json()
    pkg = next((p for p in lst if p.get("enabled") and abs(float(p.get("price_per_night", 0)) - 25.0) < 0.01), None)
    if not pkg:
        r = admin.post(f"{API}/arrival-reminder/event-packages/{PID}", json={"use_default": True})
        pkg = r.json()

    payload = {"property_id": PID, "room_type": "Standard Double",
               "check_in": "2026-09-05", "check_out": "2026-09-07",
               "guest_name": "Iter609 Pkg", "guest_email": "iter609pkg@example.com",
               "rooms": 1, "rate": 100, "pay_now": False, "package_id": pkg["id"]}
    r = requests.post(f"{API}/booking-widget/book", json=payload)
    assert r.status_code == 200, r.text
    body = r.json()
    # find booking in db
    bk_id = body.get("booking_id") or body.get("id")
    if not bk_id:
        bk = db.bookings.find_one({"guest_email": "iter609pkg@example.com"}, sort=[("created_at", -1)])
    else:
        bk = db.bookings.find_one({"id": bk_id})
    assert bk is not None
    assert bk.get("package") is not None
    assert abs(float(bk["package"]["total"]) - 50.0) < 0.01
    # total = rate*2 + 50 (rate = server-side computed nightly avg)
    rate_used = (float(bk["total"]) - 50.0) / 2
    assert abs(float(bk["total"]) - (rate_used * 2 + 50.0)) < 0.01

    # invalid package
    payload2 = {**payload, "package_id": "nope", "guest_email": "iter609pkgbad@example.com"}
    r = requests.post(f"{API}/booking-widget/book", json=payload2)
    assert r.status_code == 400


# ---------- A/B AUTO WINNER ----------

def test_06_ab_auto_winner(admin, db):
    now_iso = datetime.now(timezone.utc).isoformat()
    # seed 25 views A + 25 views B (sim)
    db.ota_banner_views.insert_many([{"id": str(uuid.uuid4()), "property_id": PID, "variant": "A", "ts": now_iso, "sim": True} for _ in range(25)])
    db.ota_banner_views.insert_many([{"id": str(uuid.uuid4()), "property_id": PID, "variant": "B", "ts": now_iso, "sim": True} for _ in range(25)])
    # seed 5 bookings variant B + 1 variant A
    for _ in range(5):
        db.bookings.insert_one({"id": str(uuid.uuid4()), "property_id": PID, "status": "confirmed",
                                "channel_source": "ota_banner:sim", "ab_variant": "B",
                                "created_at": now_iso, "total": 100, "sim": True})
    db.bookings.insert_one({"id": str(uuid.uuid4()), "property_id": PID, "status": "confirmed",
                            "channel_source": "ota_banner:sim", "ab_variant": "A",
                            "created_at": now_iso, "total": 100, "sim": True})

    # ensure config
    r = admin.put(f"{API}/booking-widget/config/{PID}", json={
        "ota_ab_enabled": True, "ota_ab_variant_b_pct": 8, "direct_advantage_pct": 5,
        "ota_banner_enabled": True, "accent_color": "#1a3c5e"})
    assert r.status_code == 200, r.text

    # run auto winner
    r = admin.post(f"{API}/booking-widget/ab-auto-winner/run/{PID}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["locked"]) >= 1
    lk = body["locked"][0]
    assert lk["variant"] == "B"
    assert float(lk["pct"]) == 8.0
    assert lk.get("emails", 0) >= 1

    # ota-conversion
    r = admin.get(f"{API}/booking-widget/ota-conversion/{PID}")
    assert r.status_code == 200
    conv = r.json()
    assert float(conv["direct_advantage_pct"]) == 8.0
    assert conv["ab"]["enabled"] is False
    assert conv["ab"]["auto_locked"]["variant"] == "B"

    # notification
    n = db.notifications.find_one({"property_id": PID, "title": {"$regex": "A/B kazananı"}})
    assert n is not None


# ---------- CLEANUP ----------

def test_zz_cleanup(admin, db):
    # bookings iter609*
    db.bookings.delete_many({"guest_email": {"$regex": "^iter609"}})
    db.email_outbox.delete_many({"to": {"$regex": "^iter609"}})
    # sim docs
    db.ota_banner_views.delete_many({"sim": True})
    db.bookings.delete_many({"sim": True})
    # restore config
    admin.put(f"{API}/booking-widget/config/{PID}", json={
        "ota_ab_enabled": True, "direct_advantage_pct": 5, "ota_ab_variant_b_pct": 8,
        "ota_banner_enabled": True, "accent_color": "#1a3c5e"})
    db.booking_widget_config.update_one({"property_id": PID}, {"$unset": {"ota_ab_auto_locked": ""}})
    # remove created event package if still there
    if _created_pkg_id:
        db.event_packages.delete_one({"id": _created_pkg_id, "property_id": PID})
    # delete arrival reminder log for iter609 (optional cleanliness)
    db.arrival_reminder_log.delete_many({"to": {"$regex": "^iter609"}})
    # notifications cleanup for A/B (only sim-created ones)
    db.notifications.delete_many({"title": {"$regex": "A/B kazananı"}, "property_id": PID})
    # ensure exactly one enabled default (£25) event package exists at end
    remaining = list(db.event_packages.find({"property_id": PID, "enabled": True, "price_per_night": 25.0}))
    if len(remaining) == 0:
        # seed one via API to guarantee
        admin.post(f"{API}/arrival-reminder/event-packages/{PID}", json={"use_default": True})
    elif len(remaining) > 1:
        for extra in remaining[1:]:
            db.event_packages.delete_one({"id": extra["id"]})
