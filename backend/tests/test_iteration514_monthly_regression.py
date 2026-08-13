"""Iteration 514 — Aylık Sağlık Taraması (Monthly Full Regression)
Covers: PMS core, revenue suite (profit-pricing, decision-assurance, data-quality,
revpam, ABS, group-displacement), Group Sales OS lifecycle (RFP -> quote -> alt ->
reschedule -> won -> lost), GDPR erasure, public survey/photo-contest vote.
"""
import os
import time
import uuid
import pytest
import requests
from datetime import datetime, timezone, timedelta
from pymongo import MongoClient

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = BASE_URL + "/api"
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")

ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASS = "HotelAdmin2026!"

TIMEOUT_LONG = 120  # alternatives search takes 30-60s


# ---------- fixtures ----------
@pytest.fixture(scope="session")
def db():
    return MongoClient(MONGO_URL)[DB_NAME]


@pytest.fixture(scope="session")
def auth():
    r = requests.post(f"{API}/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASS},
                      timeout=15)
    assert r.status_code == 200, r.text
    tok = r.json().get("token") or r.json().get("access_token")
    assert tok
    return {"Authorization": f"Bearer {tok}"}


# ---------- PMS CORE ----------
class TestCoreRegression:
    def test_login(self, auth):
        assert "Authorization" in auth

    def test_properties(self, auth):
        r = requests.get(f"{API}/properties", headers=auth, timeout=15)
        assert r.status_code == 200
        assert isinstance(r.json(), list) and len(r.json()) >= 1

    def test_portfolio_report(self, auth):
        r = requests.get(f"{API}/ai-agent/portfolio-report", headers=auth, timeout=30)
        assert r.status_code == 200

    def test_reviews_list_and_stats(self, auth):
        r = requests.get(f"{API}/reviews?property_id=default",
                         headers=auth, timeout=15)
        assert r.status_code == 200, r.text

    def test_booking_widget_book_no_abs(self):
        payload = {
            "property_id": "default",
            "guest_name": "TEST_iter514",
            "guest_email": "iter514@test.com",
            "guest_phone": "+905551110000",
            "check_in": "2026-07-04",
            "check_out": "2026-07-06",
            "adults": 2,
            "room_type": "Standard",
        }
        r = requests.post(f"{API}/booking-widget/book", json=payload, timeout=20)
        assert r.status_code == 200, r.text
        ref = r.json().get("booking_ref") or r.json().get("ref")
        assert ref

    def test_survey_public_submit(self):
        r = requests.post(f"{API}/surveys/public/qr-default",
                          json={"nps_score": 9}, timeout=10)
        assert r.status_code == 200
        assert r.json().get("property_id") == "default"

    def test_photo_contest_public_and_vote(self, db):
        r = requests.get(f"{API}/reputation/public/photo-contest/default", timeout=10)
        assert r.status_code == 200
        cands = r.json().get("candidates", [])
        seeded = None
        if not cands:
            seeded = f"TEST_CAND_{uuid.uuid4().hex[:8]}"
            db.survey_responses.insert_one({
                "id": seeded, "property_id": "default",
                "guest_name": "TEST_Voter514", "guest_email": "",
                "photo_consent": True,
                "photo_url": "/api/uploads/survey_photos/nx.jpg",
                "gallery_votes": 0,
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
            cands = requests.get(
                f"{API}/reputation/public/photo-contest/default",
                timeout=10).json().get("candidates", [])
        assert cands
        cid = cands[0]["id"]
        ip = f"203.0.113.{(int(time.time()) % 240) + 5}"
        tok = uuid.uuid4().hex
        h = {"X-Forwarded-For": ip}
        r1 = requests.post(
            f"{API}/reputation/public/photo-contest/default/vote",
            headers=h, json={"candidate_id": cid, "client_token": tok}, timeout=10)
        assert r1.status_code == 200, r1.text
        r2 = requests.post(
            f"{API}/reputation/public/photo-contest/default/vote",
            headers=h, json={"candidate_id": cid, "client_token": tok}, timeout=10)
        assert r2.status_code == 429
        if seeded:
            db.survey_responses.delete_one({"id": seeded})
        db.photo_votes.delete_many({"candidate_id": cid})


# ---------- GDPR ----------
class TestGdpr:
    def test_erasure_full_flow(self, db, auth):
        email = f"test_erasure_{uuid.uuid4().hex[:6]}@test.com"
        sr_id = f"TEST_SR_{uuid.uuid4().hex[:8]}"
        db.survey_responses.insert_one({
            "id": sr_id, "property_id": "default",
            "guest_email": email, "guest_name": "TEST_Erasure514",
            "photo_consent": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        r = requests.post(f"{API}/gdpr/erasure", headers=auth,
                          json={"email": email, "reason": "iter514 monthly"},
                          timeout=20)
        assert r.status_code == 200, r.text
        aff = r.json().get("affected", {})
        assert aff.get("survey_responses", 0) >= 1
        db.survey_responses.delete_one({"id": sr_id})


# ---------- REVENUE SUITE ----------
class TestRevenueSuite:
    def test_profit_pricing_matrix(self, auth):
        r = requests.get(f"{API}/profit-pricing/default?days=7",
                         headers=auth, timeout=30)
        assert r.status_code == 200, r.text
        j = r.json()
        assert "matrix" in j or "cells" in j or "days" in j
        # Look for deductions in at least one cell
        cells = j.get("matrix") or j.get("cells") or j.get("days") or []
        if isinstance(cells, list) and cells:
            sample = cells[0]
            # findings + deductions expected somewhere in response
        assert "findings" in j or "matrix" in j

    def test_profit_autopilot_run(self, auth):
        r = requests.post(f"{API}/profit-pricing/default/autopilot/run",
                          headers=auth, timeout=45)
        assert r.status_code == 200, r.text

    def test_decision_assurance(self, auth):
        r = requests.get(f"{API}/decision-assurance/aldgate-flats?days=120",
                         headers=auth, timeout=45)
        assert r.status_code == 200, r.text
        j = r.json()
        assert "summary" in j
        decisions = j["summary"].get("decisions", 0)
        assert decisions >= 0

    def test_data_quality_property(self, auth):
        r = requests.get(f"{API}/data-quality/default", headers=auth, timeout=30)
        assert r.status_code == 200
        j = r.json()
        assert "health_score" in j or "score" in j
        assert "issues" in j

    def test_data_quality_summary_all(self, auth):
        r = requests.get(f"{API}/data-quality/summary/all",
                         headers=auth, timeout=30)
        assert r.status_code == 200
        j = r.json()
        assert "avg_score" in j
        assert "properties" in j

    def test_revpam(self, auth):
        r = requests.get(f"{API}/revpam/default?days=14",
                         headers=auth, timeout=30)
        assert r.status_code == 200
        j = r.json()
        spaces = j.get("spaces") or j.get("items") or []
        assert isinstance(spaces, list) and len(spaces) >= 2

    def test_abs_public(self):
        r = requests.get(f"{API}/abs/public/default", timeout=15)
        assert r.status_code == 200
        j = r.json()
        attrs = j.get("attributes") or j.get("items") or j
        if isinstance(attrs, dict):
            attrs = attrs.get("attributes", [])
        assert isinstance(attrs, list) and len(attrs) >= 5
        # image_url present, sorted by sales
        assert any("image_url" in a for a in attrs)

    def test_group_displacement_analyze(self, auth):
        base = datetime.now(timezone.utc).date() + timedelta(days=45)
        payload = {
            "property_id": "default",
            "check_in": base.isoformat(),
            "check_out": (base + timedelta(days=3)).isoformat(),
            "rooms_requested": 60, "offered_rate": 70,
        }
        r = requests.post(f"{API}/group-displacement/analyze",
                          json=payload, headers=auth, timeout=60)
        assert r.status_code == 200, r.text
        j = r.json()
        # new net fields
        assert any(k in j for k in ("net_displacement_cost",
                                    "net_value_after_commission",
                                    "breakeven_rate_net",
                                    "suggested_min_rate_net"))


# ---------- GROUP SALES OS LIFECYCLE ----------
class TestGroupSalesLifecycle:
    RFP_ID = None

    def test_full_lifecycle(self, auth, db):
        base = datetime.now(timezone.utc).date() + timedelta(days=60)
        # 1) create
        create_payload = {
            "group_name": "Regresyon QA Grubu",
            "contact_email": "regqa@test.com",
            "check_in": base.isoformat(),
            "check_out": (base + timedelta(days=3)).isoformat(),
            "rooms": 12,
            "offered_rate": 85,
        }
        r = requests.post(f"{API}/group-sales/default/rfp",
                          json=create_payload, headers=auth, timeout=30)
        assert r.status_code == 200, r.text
        rfp = r.json()["rfp"]
        rid = rfp["id"]

        # 2) quote (may auto-produce alternatives if reject)
        rq = requests.post(f"{API}/group-sales/rfp/{rid}/quote",
                           json={"note": "iter514"}, headers=auth,
                           timeout=TIMEOUT_LONG)
        assert rq.status_code == 200, rq.text
        qj = rq.json()
        assert "version" in qj
        v = qj["version"]
        assert v.get("v") == 1
        assert "recommendation" in v

        alts = qj.get("alternatives") or []
        # 3) reschedule using an alternative or a shifted date
        if alts:
            alt = alts[0]
            sched = {"check_in": alt.get("check_in"),
                     "check_out": alt.get("check_out")}
        else:
            sched = {"check_in": (base + timedelta(days=14)).isoformat(),
                     "check_out": (base + timedelta(days=17)).isoformat()}
        rr = requests.post(f"{API}/group-sales/rfp/{rid}/reschedule",
                           json=sched, headers=auth, timeout=TIMEOUT_LONG)
        assert rr.status_code == 200, rr.text
        rj = rr.json()
        assert rj.get("version", {}).get("v") == 2

        # 4) status won -> block booking created
        rw = requests.put(f"{API}/group-sales/rfp/{rid}",
                          json={"status": "won"}, headers=auth, timeout=30)
        assert rw.status_code == 200, rw.text
        wj = rw.json()
        block = wj.get("block")
        assert block and block.get("action") == "created", wj
        booking_ref = block.get("booking_ref")
        assert booking_ref
        # verify booking doc
        bk = db.bookings.find_one({"booking_ref": booking_ref}, {"_id": 0})
        assert bk and bk.get("room_type") == "Group Block"
        assert bk.get("status") == "confirmed"

        # 5) email endpoint (mocked -> "mock")
        re = requests.post(f"{API}/group-sales/rfp/{rid}/email",
                           json={}, headers=auth, timeout=30)
        assert re.status_code == 200, re.text
        assert re.json().get("status") in ("mock", "sent")

        # 6) revert status -> lost -> block released (cancelled)
        rl = requests.put(f"{API}/group-sales/rfp/{rid}",
                          json={"status": "lost"}, headers=auth, timeout=30)
        assert rl.status_code == 200, rl.text
        lj = rl.json()
        assert lj.get("block", {}).get("action") == "released", lj
        bk2 = db.bookings.find_one({"booking_ref": booking_ref}, {"_id": 0})
        assert bk2 and bk2.get("status") == "cancelled"


# ---------- RFP EMAIL (standalone smoke) ----------
def test_rfp_email_mock_signature(auth, db):
    # Reuse the RFP created above by fetching the most recent "Regresyon QA Grubu"
    rfp = db.group_rfps.find_one(
        {"group_name": "Regresyon QA Grubu"}, {"_id": 0},
        sort=[("created_at", -1)])
    if not rfp:
        pytest.skip("no QA RFP available")
    r = requests.post(f"{API}/group-sales/rfp/{rfp['id']}/email",
                      json={"to": "qa514@test.com"}, headers=auth, timeout=30)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j.get("status") in ("mock", "sent")
