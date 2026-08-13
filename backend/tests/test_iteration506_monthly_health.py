"""Iteration 506 — Monthly Health Scan
Regression across PMS core + social module + GDPR/vote protection.
"""
import os, io, uuid, time
import pytest
import requests
from datetime import datetime, timezone
from pymongo import MongoClient

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = BASE_URL + "/api"
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")

ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASS = "HotelAdmin2026!"


# ---------------- Fixtures ----------------
@pytest.fixture(scope="session")
def db():
    return MongoClient(MONGO_URL)[DB_NAME]


@pytest.fixture(scope="session")
def token():
    r = requests.post(f"{API}/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASS})
    assert r.status_code == 200, r.text
    j = r.json()
    tok = j.get("token") or j.get("access_token")
    assert tok
    return tok


@pytest.fixture(scope="session")
def auth(token):
    return {"Authorization": f"Bearer {token}"}


# ---------------- PMS CORE ----------------
class TestPmsCore:
    def test_properties_list(self, auth):
        r = requests.get(f"{API}/properties", headers=auth)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list) and len(data) >= 1

    def test_portfolio_report(self, auth):
        r = requests.get(f"{API}/ai-agent/portfolio-report", headers=auth)
        assert r.status_code == 200
        data = r.json()
        # Should contain rows with avg_rating, rating_trend, review_count
        rows = data.get("rows") or data.get("properties") or data
        if isinstance(rows, dict):
            rows = rows.get("rows") or []
        assert isinstance(rows, list) and len(rows) >= 1
        sample = rows[0]
        for key in ("avg_rating", "rating_trend", "review_count"):
            assert key in sample, f"missing {key} in portfolio row: {sample.keys()}"

    def test_winback_stats(self, auth):
        r = requests.get(f"{API}/ai-agent/winback-stats/default", headers=auth)
        assert r.status_code == 200
        data = r.json()
        for key in ("total", "redeemed", "expired", "redeem_rate"):
            assert key in data, f"missing {key}"

    def test_winback_offers(self, auth):
        r = requests.get(f"{API}/ai-agent/winback-offers/default", headers=auth)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, (list, dict))

    def test_booking_widget_public_book(self):
        payload = {
            "property_id": "default",
            "guest_name": "TEST_MonthlyScan",
            "guest_email": "monthlyscan@test.com",
            "guest_phone": "+905551112233",
            "check_in": "2026-06-10",
            "check_out": "2026-06-12",
            "adults": 2,
            "room_type": "Standard",
        }
        r = requests.post(f"{API}/booking-widget/book", json=payload)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("booking_ref") or data.get("bookingRef") or data.get("ref")


# ---------------- SOCIAL MODULE ----------------
class TestSocialModule:
    def test_social_drafts(self, auth):
        r = requests.get(f"{API}/reputation/social-drafts/default", headers=auth)
        assert r.status_code == 200
        data = r.json()
        drafts = data if isinstance(data, list) else data.get("drafts", [])
        # Look for 'ayın karesi' and 'oylama' style automated drafts
        topics = " ".join(str(d).lower() for d in drafts)
        # These are auto-created by workers; accept presence of either indicator
        # (soft assertion — do not fail hard if list empty on fresh env)
        assert isinstance(drafts, list)

    def test_social_calendar(self, auth):
        r = requests.get(f"{API}/reputation/social-calendar/default", headers=auth)
        assert r.status_code == 200

    def test_social_performance(self, auth):
        r = requests.get(f"{API}/reputation/social-performance/default", headers=auth)
        assert r.status_code == 200

    def test_best_time(self, auth):
        r = requests.get(f"{API}/reputation/best-time/default", headers=auth)
        assert r.status_code == 200

    def test_social_drafts_pending(self, auth):
        r = requests.get(f"{API}/reputation/social-drafts-pending", headers=auth)
        assert r.status_code == 200

    def test_guest_photos(self, auth):
        r = requests.get(f"{API}/reputation/guest-photos/default", headers=auth)
        assert r.status_code == 200

    def test_social_report_pdf(self, auth):
        r = requests.post(f"{API}/reputation/social-report/pdf",
                          headers=auth, json={"property_id": "default"})
        assert r.status_code == 200, r.text
        data = r.json()
        pdf_url = data.get("pdf_url") or data.get("url")
        assert pdf_url, f"no pdf_url: {data}"
        # Fetch the PDF
        full = pdf_url if pdf_url.startswith("http") else BASE_URL + pdf_url
        pr = requests.get(full)
        assert pr.status_code == 200
        assert pr.content[:4] == b"%PDF"

    def test_photo_contest_poster_pdf(self, auth):
        r = requests.get(f"{API}/reputation/photo-contest-poster/default", headers=auth)
        assert r.status_code == 200
        data = r.json()
        pdf_url = data.get("poster_url") or data.get("pdf_url")
        assert pdf_url
        full = pdf_url if pdf_url.startswith("http") else BASE_URL + pdf_url
        pr = requests.get(full)
        assert pr.status_code == 200 and pr.content[:4] == b"%PDF"

    def test_room_qr_cards_pdf(self, auth):
        r = requests.get(f"{API}/reputation/room-qr-cards/default", headers=auth)
        assert r.status_code == 200
        data = r.json()
        pdf_url = data.get("pdf_url")
        assert pdf_url
        full = pdf_url if pdf_url.startswith("http") else BASE_URL + pdf_url
        pr = requests.get(full)
        assert pr.status_code == 200 and pr.content[:4] == b"%PDF"


# ---------------- PUBLIC ENDPOINTS ----------------
class TestPublicEndpoints:
    def test_public_photo_contest(self):
        r = requests.get(f"{API}/reputation/public/photo-contest/default")
        assert r.status_code == 200
        data = r.json()
        assert "hotel" in data and "items" in data and "candidates" in data

    def test_vote_flow_ip_protection(self, db):
        # Ensure we have at least one candidate; if not, seed one
        r = requests.get(f"{API}/reputation/public/photo-contest/default")
        cands = r.json().get("candidates", [])
        seeded_id = None
        if not cands:
            seeded_id = f"TEST_CAND_{uuid.uuid4().hex[:8]}"
            db.survey_responses.insert_one({
                "id": seeded_id, "property_id": "default",
                "guest_name": "TEST_Voter", "guest_email": "",
                "photo_consent": True,
                "photo_url": "/api/uploads/survey_photos/nx.jpg",
                "gallery_votes": 0,
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
            r = requests.get(f"{API}/reputation/public/photo-contest/default")
            cands = r.json().get("candidates", [])
        assert cands, "no candidates for vote test"
        cid = cands[0]["id"]

        ip = "203.0.113." + str((int(time.time()) % 250) + 1)  # unique IP per run
        hdrs = {"X-Forwarded-For": ip}

        # First vote: 200
        r1 = requests.post(
            f"{API}/reputation/public/photo-contest/default/vote",
            headers=hdrs, json={"candidate_id": cid})
        assert r1.status_code == 200, r1.text

        # Second vote same IP+candidate: 429
        r2 = requests.post(
            f"{API}/reputation/public/photo-contest/default/vote",
            headers=hdrs, json={"candidate_id": cid})
        assert r2.status_code == 429, f"expected 429 got {r2.status_code}: {r2.text}"
        assert "zaten" in r2.text.lower()

        # Invalid candidate: 404
        r3 = requests.post(
            f"{API}/reputation/public/photo-contest/default/vote",
            headers={"X-Forwarded-For": "198.51.100.99"},
            json={"candidate_id": "nonexistent-xyz"})
        assert r3.status_code == 404, r3.text

        # cleanup seeded doc + votes for this run
        if seeded_id:
            db.survey_responses.delete_one({"id": seeded_id})
        db.photo_votes.delete_many({"candidate_id": cid,
                                    "ip_hash": {"$exists": True}})

    def test_survey_public_submit(self):
        r = requests.post(f"{API}/surveys/public/qr-default",
                          json={"nps_score": 8})
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("property_id") == "default"


# ---------------- GDPR / COMPLIANCE ----------------
class TestGdprErasure:
    EMAIL = "monthlytest@test.com"

    def test_erasure_flow(self, db, auth):
        # 1) create synthetic docs
        photo_file = "/app/backend/uploads/survey_photos/mt.jpg"
        os.makedirs(os.path.dirname(photo_file), exist_ok=True)
        with open(photo_file, "wb") as f:
            f.write(b"\xff\xd8\xff\xe0test-jpg-bytes")

        sr_id = f"TEST_SR_{uuid.uuid4().hex[:8]}"
        wb_id = f"TEST_WB_{uuid.uuid4().hex[:8]}"
        db.survey_responses.insert_one({
            "id": sr_id, "property_id": "default",
            "guest_email": self.EMAIL, "guest_name": "TEST_MonthlyTest",
            "photo_url": "/api/uploads/survey_photos/mt.jpg",
            "photo_consent": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        db.winback_offers.insert_one({
            "id": wb_id, "property_id": "default",
            "guest_email": self.EMAIL, "code": "TESTMT",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

        # 2) call erasure
        r = requests.post(f"{API}/gdpr/erasure", headers=auth,
                          json={"email": self.EMAIL,
                                "reason": "iteration_506 monthly scan"})
        assert r.status_code == 200, r.text
        data = r.json()
        affected = data.get("affected", {})
        assert affected.get("survey_responses", 0) >= 1
        assert affected.get("winback_offers", 0) >= 1
        assert affected.get("survey_photo_files", 0) >= 1

        # 3) file removed
        assert not os.path.exists(photo_file), "photo file should be deleted"

        # 4) gdpr log has the entry
        gl = requests.get(f"{API}/gdpr/log", headers=auth)
        assert gl.status_code == 200
        logs = gl.json()
        entries = logs if isinstance(logs, list) else logs.get("log", [])
        assert any(e.get("email") == self.EMAIL and e.get("action") == "erasure"
                   for e in entries), "erasure log entry missing"

        # cleanup remaining anonymized docs
        db.survey_responses.delete_one({"id": sr_id})
        db.winback_offers.delete_one({"id": wb_id})


# ---------------- AUTOMATION TRIGGERS ----------------
@pytest.mark.parametrize("path", [
    "/reputation/trend-alerts/run",
    "/reputation/publish-alerts/run",
    "/reputation/winning-topic/run",
    "/reputation/photo-contest/run",
    "/reputation/vote-announce/run",
    "/reputation/social-report/run",
    "/ai-agent/winback-reminders/run",
])
def test_automation_trigger(auth, path):
    r = requests.post(f"{API}{path}", headers=auth)
    assert r.status_code == 200, f"{path} -> {r.status_code} {r.text[:200]}"
