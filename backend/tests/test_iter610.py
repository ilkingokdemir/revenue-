"""Iter 610 — Upsell one-click claim link, post-stay review request, package sales report."""
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


def _today_plus(n):
    return (datetime.now(timezone.utc).date() + timedelta(days=n)).isoformat()


# ============ (a) UPSELL ONE-CLICK CLAIM ============

_claim_booking_id = None
_claim_token = None


def test_01a_create_booking_and_arrival_reminder(admin, db):
    global _claim_booking_id
    payload = {"property_id": PID, "room_type": "Standard Double",
               "check_in": _today_plus(2), "check_out": _today_plus(4),
               "guest_name": "Iter610 Claim", "guest_email": "iter610claim@example.com",
               "lang": "tr", "rooms": 1, "rate": 1, "pay_now": False}
    r = requests.post(f"{API}/booking-widget/book", json=payload)
    assert r.status_code == 200, r.text
    body = r.json()
    _claim_booking_id = body.get("booking_id") or body.get("id")
    if not _claim_booking_id:
        bk = db.bookings.find_one({"guest_email": "iter610claim@example.com"}, sort=[("created_at", -1)])
        assert bk is not None
        _claim_booking_id = bk["id"]

    # Run arrival reminder
    r = admin.post(f"{API}/arrival-reminder/run/{PID}")
    assert r.status_code == 200, r.text
    assert r.json()["candidates"] >= 1

    # upsell_claim_tokens for this booking
    tokens = list(db.upsell_claim_tokens.find({"booking_id": _claim_booking_id}))
    assert len(tokens) == 3, f"Expected 3 tokens, got {len(tokens)}"
    for t in tokens:
        assert t.get("lang") == "tr"
        # expires in ~14 days
        exp = datetime.fromisoformat(t["expires_at"].replace("Z", "+00:00"))
        delta_days = (exp - datetime.now(timezone.utc)).days
        assert 12 <= delta_days <= 14, f"expires_at delta unexpected: {delta_days}"

    # email_outbox has arrival_reminder with claim URL + 'Rezervasyonuma ekle'
    doc = db.email_outbox.find_one({"to": "iter610claim@example.com", "kind": "arrival_reminder"})
    assert doc is not None
    html = doc.get("html", "")
    assert "/api/revenue/upsell/claim/" in html
    assert "Rezervasyonuma ekle" in html

    # save one token for next test
    global _claim_token
    _claim_token = tokens[0]["token"]


def test_01b_public_claim_link_first_time(db):
    global _claim_token
    r = requests.get(f"{API}/revenue/upsell/claim/{_claim_token}")
    assert r.status_code == 200
    assert "Rezervasyonunuza eklendi" in r.text

    # folio_items has upsell item
    tk = db.upsell_claim_tokens.find_one({"token": _claim_token})
    folio = list(db.folio_items.find({"booking_id": _claim_booking_id, "category": "upsell"}))
    assert len(folio) == 1
    assert abs(float(folio[0].get("amount") or folio[0].get("total") or 0) - float(tk["amount"])) < 0.01

    # upsell_log entry with source pre_arrival_email
    lg = db.upsell_log.find_one({"booking_id": _claim_booking_id, "source": "pre_arrival_email"})
    assert lg is not None


def test_01c_claim_link_second_time_idempotent(db):
    r = requests.get(f"{API}/revenue/upsell/claim/{_claim_token}")
    assert r.status_code == 200
    assert "Zaten eklenmiş" in r.text
    # still exactly one folio_item
    folio = list(db.folio_items.find({"booking_id": _claim_booking_id, "category": "upsell"}))
    assert len(folio) == 1


def test_01d_invalid_token():
    r = requests.get(f"{API}/revenue/upsell/claim/invalidtoken")
    assert r.status_code == 200
    assert "Link ungültig" in r.text or "Link not valid" in r.text or "Bağlantı geçersiz" in r.text


def test_01e_staff_accept_still_works(admin, db):
    r = admin.post(f"{API}/revenue/upsell/{_claim_booking_id}/accept",
                   json={"type": "addon", "price": 10, "description": "x"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("status") == "accepted"


# ============ (b) POST-STAY REVIEW REQUEST ============

def test_02a_review_request_flow(admin, db):
    # insert booking directly
    db.bookings.insert_one({
        "id": "iter610rev", "property_id": PID, "booking_ref": "WEB-ITER610",
        "status": "checked_out", "check_in": _today_plus(-3), "check_out": _today_plus(-1),
        "guest_name": "Rev Test", "guest_email": "iter610rev@example.com",
        "guest_lang": "de", "created_at": datetime.now(timezone.utc).isoformat(),
    })
    r = admin.post(f"{API}/review-collection/send/{PID}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("candidates", 0) >= 1
    assert body.get("mocked", 0) >= 1

    # email_outbox review_request
    doc = db.email_outbox.find_one({"to": "iter610rev@example.com", "kind": "review_request"})
    assert doc is not None
    assert doc.get("subject", "").startswith("Wie war Ihr Aufenthalt im ")
    html = doc.get("html", "")
    assert "Bewertung abgeben" in html
    assert "/review?property=default&ref=WEB-ITER610&lang=de" in html

    # booking updated
    bk = db.bookings.find_one({"id": "iter610rev"})
    assert bk.get("review_request_sent_at")
    assert bk.get("review_request_lang") == "de"


def test_02b_review_request_idempotent(admin):
    r = admin.post(f"{API}/review-collection/send/{PID}")
    assert r.status_code == 200
    body = r.json()
    # our booking already sent; but there might be others - check that iter610rev is not re-sent
    # We check candidates=0 unless other test data pre-existed. Be lenient:
    assert body.get("candidates", 0) == 0 or body.get("mocked", 0) == 0
    # More precisely: our specific booking should have review_request_sent_at unchanged relative status
    # Since arrival test doesn't touch review, assert candidates==0 (idempotent)
    assert body.get("candidates", 0) == 0


def test_02c_automation_jobs_registry(admin):
    r = admin.get(f"{API}/automation/settings")
    assert r.status_code == 200, r.text
    body = r.json()
    # settings returns list or dict - just check review_request appears somewhere with category guest
    txt = r.text
    assert "review_request" in txt
    # category=guest
    if isinstance(body, dict) and "jobs" in body:
        jobs = body["jobs"]
    elif isinstance(body, list):
        jobs = body
    else:
        jobs = []
    rr = next((j for j in jobs if (j.get("job") == "review_request" or j.get("id") == "review_request")), None)
    if rr:
        assert rr.get("category") == "guest"


# ============ (c) PACKAGE SALES REPORT ============

def test_03_package_sales_report(admin, db):
    # find enabled default package
    lst = requests.get(f"{API}/arrival-reminder/event-packages/{PID}").json()
    pkg = next((p for p in lst if p.get("enabled")), None)
    assert pkg is not None, "Expected an enabled default event package to exist"

    payload = {"property_id": PID, "room_type": "Standard Double",
               "check_in": "2026-09-05", "check_out": "2026-09-07",
               "guest_name": "Iter610 Pkg", "guest_email": "iter610pkg@example.com",
               "rooms": 1, "rate": 100, "pay_now": False, "package_id": pkg["id"]}
    r = requests.post(f"{API}/booking-widget/book", json=payload)
    assert r.status_code == 200, r.text

    r = admin.get(f"{API}/booking-widget/ota-conversion/{PID}?days=90")
    assert r.status_code == 200
    body = r.json()
    pkgs = body.get("packages") or {}
    assert pkgs.get("bookings", 0) >= 1
    assert float(pkgs.get("revenue", 0)) >= 50
    assert isinstance(pkgs.get("by_package"), list) and len(pkgs["by_package"]) >= 1
    assert float(pkgs.get("attach_rate_pct", 0)) > 0


# ============ CLEANUP ============

def test_zz_cleanup(admin, db):
    # iter610claim booking + related
    for bk in db.bookings.find({"guest_email": {"$regex": "^iter610"}}):
        bid = bk["id"]
        db.folio_items.delete_many({"booking_id": bid})
        db.upsell_log.delete_many({"booking_id": bid})
        db.upsell_claim_tokens.delete_many({"booking_id": bid})
    db.bookings.delete_many({"guest_email": {"$regex": "^iter610"}})
    db.bookings.delete_many({"id": "iter610rev"})
    db.email_outbox.delete_many({"to": {"$regex": "^iter610"}})
    db.arrival_reminder_log.delete_many({"to": {"$regex": "^iter610"}})
