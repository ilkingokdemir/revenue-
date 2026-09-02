"""Iteration 608 backend tests: guest email i18n, upcoming events, OTA A/B config & conversion."""
import os
import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://review-hub-108.preview.emergentagent.com").rstrip("/")
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")


@pytest.fixture(scope="module")
def sess():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def admin(sess):
    r = sess.post(f"{BASE_URL}/api/auth/login", json={"email": "admin@hotelbox.com", "password": "HotelAdmin2026!"})
    assert r.status_code == 200, r.text
    return sess  # cookies attached


# ---------- 1. Confirmation email i18n ----------

@pytest.mark.parametrize("lang,subj_prefix,html_token", [
    ("de", "Buchung bestätigt", "Anreise"),
    ("tr", "Rezervasyonunuz onaylandı", "Giriş"),
    ("en", "Booking confirmed", "Check-in"),
])
def test_book_email_i18n(sess, lang, subj_prefix, html_token):
    email = f"iter608{lang}@example.com"
    payload = {
        "property_id": "default", "room_type": "Standard Double",
        "check_in": "2026-09-05", "check_out": "2026-09-07",
        "guest_name": f"Test {lang.upper()}", "guest_email": email,
        "rate": 1, "pay_now": False, "lang": lang,
        "channel_source": "ota_banner:Expedia", "ab_variant": "B",
    }
    r = sess.post(f"{BASE_URL}/api/booking-widget/book", json=payload)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["email"]["status"] == "mocked"
    assert d["email"]["lang"] == lang
    assert d["email"]["subject"].startswith(subj_prefix), f"subject={d['email']['subject']}"
    assert d["booking"]["ab_variant"] == "B"


def test_book_email_missing_lang_defaults_english(sess):
    payload = {
        "property_id": "default", "room_type": "Standard Double",
        "check_in": "2026-09-05", "check_out": "2026-09-07",
        "guest_name": "Test Default", "guest_email": "iter608default@example.com",
        "rate": 1, "pay_now": False,
    }
    r = sess.post(f"{BASE_URL}/api/booking-widget/book", json=payload)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["email"]["subject"].startswith("Booking confirmed")


def test_email_outbox_and_log_persisted():
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    doc = db.email_outbox.find_one({"to": "iter608de@example.com"}, sort=[("created_at", -1)])
    assert doc is not None, "email_outbox missing DE mock"
    assert doc.get("lang") == "de" or "de" in (doc.get("meta", {}) or {}).get("lang", "")
    assert "Anreise" in (doc.get("html") or "")
    log = db.booking_email_log.find_one({"to": "iter608de@example.com"})
    assert log is not None
    assert log.get("type") == "booking_confirmation"
    assert log.get("lang") == "de"
    client.close()


# ---------- 2. Upcoming events ----------

def test_upcoming_events(sess):
    r = sess.get(f"{BASE_URL}/api/booking-widget/upcoming-events/default?days=90&limit=4")
    assert r.status_code == 200, r.text
    d = r.json()
    events = d["events"]
    assert isinstance(events, list) and len(events) <= 4
    if not events:
        pytest.skip("No market_events in window")
    from datetime import datetime
    for e in events:
        for k in ("name", "date", "end_date", "icon", "label_en", "label_tr", "label_de", "suggest_check_in", "suggest_check_out"):
            assert k in e, f"missing {k}"
        ci = datetime.strptime(e["suggest_check_in"], "%Y-%m-%d")
        co = datetime.strptime(e["suggest_check_out"], "%Y-%m-%d")
        assert (co - ci).days >= 2, f"suggested nights < 2: {e}"
    # sorted by date
    dates = [e["date"] for e in events]
    assert dates == sorted(dates)
    # dedup: no same icon with overlapping ranges
    for i, a in enumerate(events):
        for b in events[i+1:]:
            if a["icon"] == b["icon"]:
                assert a["end_date"] < b["date"] or b["end_date"] < a["date"], f"overlap dup: {a} vs {b}"


# ---------- 3. OTA A/B config + conversion ----------

def test_ota_banner_view_public(sess):
    r = sess.post(f"{BASE_URL}/api/booking-widget/ota-banner-view",
                  json={"property_id": "default", "ota": "Expedia", "variant": "B", "pct": 8})
    assert r.status_code == 200
    assert r.json().get("ok") is True


def test_ab_config_and_conversion(admin):
    put = admin.put(f"{BASE_URL}/api/booking-widget/config/default",
                    json={"ota_ab_enabled": True, "ota_ab_variant_b_pct": 8,
                          "direct_advantage_pct": 5, "ota_banner_enabled": True,
                          "accent_color": "#1a3c5e"})
    assert put.status_code == 200, put.text

    info = admin.get(f"{BASE_URL}/api/booking-widget/info/default")
    assert info.status_code == 200
    theme = info.json()["theme"]
    assert theme["ota_ab_enabled"] is True
    assert float(theme["ota_ab_variant_b_pct"]) == 8.0

    conv = admin.get(f"{BASE_URL}/api/booking-widget/ota-conversion/default?days=30")
    assert conv.status_code == 200, conv.text
    d = conv.json()
    assert "ab" in d
    assert d["ab"]["enabled"] is True
    variants = {v["variant"]: v for v in d["ab"]["variants"]}
    assert "A" in variants and "B" in variants
    for v in variants.values():
        assert "views" in v and "bookings" in v and "conversion_pct" in v
    assert d["ab"]["winner"] is None  # insufficient views
    assert d["ab"]["min_views_for_winner"] == 20


# ---------- Cleanup ----------

def test_zz_cleanup():
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    r1 = db.bookings.delete_many({"guest_email": {"$regex": "^iter608"}})
    r2 = db.email_outbox.delete_many({"to": {"$regex": "^iter608"}})
    r3 = db.booking_email_log.delete_many({"to": {"$regex": "^iter608"}})
    print(f"Cleaned bookings={r1.deleted_count} outbox={r2.deleted_count} log={r3.deleted_count}")
    client.close()
