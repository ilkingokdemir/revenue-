"""
Iteration 507 tests:
- Public photo vote client_token shared-IP dedupe fix
- GDPR erasure path traversal hardening
"""
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def unique_ip():
    # unique per-run x-forwarded-for so vote dedupe stays deterministic
    return f"198.51.100.{(int(time.time()) % 250) + 1}"


# ---------- Vote client_token dedupe (shared IP fix) ----------

class TestPhotoVoteClientToken:
    def _pick_candidate(self):
        # public endpoint, no auth required
        r = requests.get(
            f"{BASE_URL}/api/reputation/public/photo-contest/default",
            timeout=10)
        assert r.status_code == 200, r.text
        data = r.json()
        cands = data.get("candidates") or []
        assert cands, "no candidates available for default property"
        return cands[0]["id"]

    def test_vote_same_ip_different_tokens_both_succeed(self, unique_ip):
        cid = self._pick_candidate()
        headers = {"x-forwarded-for": unique_ip}
        token_a = f"tokA-{uuid.uuid4().hex[:8]}"
        token_b = f"tokB-{uuid.uuid4().hex[:8]}"

        # 1st vote — IP=A + tokenA + cid -> ok
        r1 = requests.post(
            f"{BASE_URL}/api/reputation/public/photo-contest/default/vote",
            json={"candidate_id": cid, "client_token": token_a},
            headers=headers, timeout=10)
        assert r1.status_code == 200, r1.text
        assert r1.json().get("ok") is True

        # 2nd vote — SAME IP + SAME token + SAME cid -> 429 duplicate
        r2 = requests.post(
            f"{BASE_URL}/api/reputation/public/photo-contest/default/vote",
            json={"candidate_id": cid, "client_token": token_a},
            headers=headers, timeout=10)
        assert r2.status_code == 429, r2.text
        assert "zaten" in r2.text.lower()

        # 3rd vote — SAME IP + DIFFERENT token + SAME cid -> should succeed
        # (shared-IP fix: different devices behind NAT can each vote once)
        r3 = requests.post(
            f"{BASE_URL}/api/reputation/public/photo-contest/default/vote",
            json={"candidate_id": cid, "client_token": token_b},
            headers=headers, timeout=10)
        assert r3.status_code == 200, r3.text
        assert r3.json().get("ok") is True


# ---------- GDPR erasure path traversal ----------

class TestGdprErasurePathTraversal:
    def test_traversal_photo_url_does_not_delete_outside(self, admin_token):
        from pymongo import MongoClient
        mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
        db_name = os.environ.get("DB_NAME", "test_database")
        client = MongoClient(mongo_url)
        db = client[db_name]

        base_dir = "/app/backend/uploads/survey_photos"
        os.makedirs(base_dir, exist_ok=True)
        legit_fname = f"iter507_{uuid.uuid4().hex[:8]}.jpg"
        legit_path = os.path.join(base_dir, legit_fname)
        with open(legit_path, "wb") as f:
            f.write(b"\xff\xd8\xff\xe0" + b"0" * 32)  # minimal jpg-ish
        assert os.path.exists(legit_path)

        # sentinel file to verify it stays intact
        server_py = "/app/backend/server.py"
        server_size_before = os.path.getsize(server_py)

        email = f"iter507_{uuid.uuid4().hex[:8]}@test.com"
        docs = [
            # traversal attempts (should be rejected by allowlist regex)
            {"id": str(uuid.uuid4()), "property_id": "default", "guest_email": email,
             "photo_url": "../../server.py", "photo_consent": True},
            {"id": str(uuid.uuid4()), "property_id": "default", "guest_email": email,
             "photo_url": "/api/uploads/survey_photos/../../server.py",
             "photo_consent": True},
            {"id": str(uuid.uuid4()), "property_id": "default", "guest_email": email,
             "photo_url": "/etc/passwd", "photo_consent": True},
            # legit file — must be deleted
            {"id": str(uuid.uuid4()), "property_id": "default", "guest_email": email,
             "photo_url": f"/api/uploads/survey_photos/{legit_fname}",
             "photo_consent": True},
        ]
        db.survey_responses.insert_many(docs)

        try:
            r = requests.post(
                f"{BASE_URL}/api/gdpr/erasure",
                json={"email": email, "reason": "iter507 traversal test"},
                headers={"Authorization": f"Bearer {admin_token}"}, timeout=15)
            assert r.status_code == 200, r.text
            affected = r.json().get("affected", {})
            # Only 1 legit file should be deleted, and traversal attempts filtered out
            assert affected.get("survey_photo_files") == 1, affected
            # server.py must remain intact
            assert os.path.exists(server_py)
            assert os.path.getsize(server_py) == server_size_before
            # legit file must be gone
            assert not os.path.exists(legit_path)
        finally:
            db.survey_responses.delete_many({"guest_email": {"$in": [email, "[REDACTED]"]}})
            if os.path.exists(legit_path):
                os.remove(legit_path)
            client.close()
