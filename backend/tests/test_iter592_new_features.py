"""Iter 592 — Object Storage uploads, Sentiment AI themes, Mobile approvals sound.

Tests:
1. Object storage e2e: upload room photo → file NOT on local disk → GET url served from cloud.
2. Other upload smoke: maintenance photo upload.
3. Legacy /api/uploads serving: existing local file, 404 for missing, 400/404 for path traversal.
4. Sentiment analyze-themes: correct property with reviews, cache, and 422 for <3 reviews.
5. Regression: sentiment-pricing/default, rate-mix/all, login.
"""
import io
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
LOCAL_UPLOADS = "/app/backend/uploads"

ADMIN = {"email": "admin@hotelbox.com", "password": "HotelAdmin2026!"}


# ---------- fixtures ----------
@pytest.fixture(scope="session")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN, timeout=30)
    assert r.status_code == 200, f"login failed {r.status_code}: {r.text[:200]}"
    return r.json()["token"]


@pytest.fixture
def A(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


def _small_jpeg_bytes() -> bytes:
    # Minimal valid JPEG (SOI + trivial DQT + EOI). Enough bytes to be an actual file.
    return (
        b"\xff\xd8\xff\xdb\x00C\x00" + b"\x08" * 64
        + b"\xff\xd9" + b"TEST_" + uuid.uuid4().hex.encode()
    )


# ---------- 1. Object storage upload e2e ----------
class TestRoomPhotoUpload:
    """POST /api/booking-widget/room-photo/{room_id} → cloud storage."""

    def test_upload_room_photo_to_cloud(self, admin_token):
        rid = "rt-standard-1"
        data = _small_jpeg_bytes()
        files = {"file": (f"TEST_{uuid.uuid4().hex[:6]}.jpg", data, "image/jpeg")}
        r = requests.post(
            f"{BASE_URL}/api/booking-widget/room-photo/{rid}",
            files=files,
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=60,
        )
        assert r.status_code == 200, f"upload failed {r.status_code}: {r.text[:300]}"
        d = r.json()
        assert d.get("status") == "uploaded"
        assert d.get("url", "").startswith("/api/uploads/rooms/"), f"bad url {d}"
        pytest.shared_upload_url = d["url"]  # type: ignore
        pytest.shared_upload_filename = d["url"].split("/")[-1]  # type: ignore

    def test_file_NOT_on_local_disk(self):
        """File must be served from cloud storage, not local disk."""
        fn = getattr(pytest, "shared_upload_filename", None)
        assert fn, "prior upload test did not run"
        local_path = os.path.join(LOCAL_UPLOADS, "rooms", fn)
        assert not os.path.isfile(local_path), (
            f"File found on local disk {local_path} — should be cloud-only"
        )

    def test_get_upload_url_serves_from_cloud(self):
        url = getattr(pytest, "shared_upload_url", None)
        assert url, "prior upload test did not run"
        # Cloud fetch may take up to a few seconds
        deadline = time.time() + 30
        last = None
        while time.time() < deadline:
            r = requests.get(f"{BASE_URL}{url}", timeout=30)
            last = r
            if r.status_code == 200:
                break
            time.sleep(1.5)
        assert last is not None and last.status_code == 200, (
            f"cloud fetch failed {getattr(last,'status_code',None)}: {getattr(last,'text','')[:200]}"
        )
        ct = last.headers.get("Content-Type", "")
        assert "image" in ct or "octet-stream" in ct, f"content-type {ct}"
        assert len(last.content) >= 50


# ---------- 2. Other upload smoke: maintenance ----------
class TestMaintenancePhotoUpload:
    def test_upload_maintenance_photo(self, admin_token):
        # Create an issue first
        A = {"Authorization": f"Bearer {admin_token}"}
        issue_payload = {
            "property_id": "default",
            "title": "TEST_ObjStore_issue",
            "description": "seed for photo upload test",
            "priority": "low",
            "category": "other",
        }
        r = requests.post(f"{BASE_URL}/api/maintenance/issues", json=issue_payload,
                          headers=A, timeout=30)
        assert r.status_code in (200, 201), f"issue create {r.status_code}: {r.text[:200]}"
        issue = r.json()
        issue_id = issue.get("id") or issue.get("issue", {}).get("id")
        assert issue_id, f"no issue id in {issue}"

        files = {"file": (f"TEST_maint_{uuid.uuid4().hex[:6]}.jpg",
                          _small_jpeg_bytes(), "image/jpeg")}
        r2 = requests.post(
            f"{BASE_URL}/api/maintenance/upload-photo/{issue_id}",
            files=files, data={"photo_type": "before"},
            headers=A, timeout=60,
        )
        assert r2.status_code == 200, f"maint upload {r2.status_code}: {r2.text[:200]}"
        d = r2.json()
        assert d.get("status") == "uploaded"
        url = d.get("url", "")
        assert url.startswith("/api/uploads/maintenance/"), f"bad url {url}"

        # Ensure file not on local disk
        fn = url.split("/")[-1]
        local = os.path.join(LOCAL_UPLOADS, "maintenance", fn)
        assert not os.path.isfile(local), f"maint file on local {local}"

        # GET the url (retry for cloud sync)
        deadline = time.time() + 30
        last = None
        while time.time() < deadline:
            g = requests.get(f"{BASE_URL}{url}", timeout=30)
            last = g
            if g.status_code == 200:
                break
            time.sleep(1.5)
        assert last is not None and last.status_code == 200, (
            f"cloud fetch of maint photo failed {getattr(last,'status_code',None)}"
        )


# ---------- 3. Legacy /api/uploads serving ----------
class TestUploadsServing:
    def test_serve_existing_local_file(self):
        """Existing local files in /app/backend/uploads/rooms should serve 200."""
        rooms_dir = os.path.join(LOCAL_UPLOADS, "rooms")
        files = [f for f in os.listdir(rooms_dir) if os.path.isfile(os.path.join(rooms_dir, f))]
        if not files:
            pytest.skip("no local room files to test")
        fn = files[0]
        r = requests.get(f"{BASE_URL}/api/uploads/rooms/{fn}", timeout=30)
        assert r.status_code == 200, f"legacy fetch {r.status_code}: {r.text[:200]}"
        assert len(r.content) > 0

    def test_serve_nonexistent_404(self):
        r = requests.get(
            f"{BASE_URL}/api/uploads/nonexistent/TEST_nope_{uuid.uuid4().hex}.jpg",
            timeout=30,
        )
        assert r.status_code == 404, f"expected 404 got {r.status_code}"

    def test_path_traversal_blocked(self):
        # requests will normalize .. path segments; use raw URL via urllib3 to preserve
        # Just check via a crafted URL: ../etc/passwd
        # Server-side normpath check: local = normpath(uploads + "../etc/passwd") -> "/app/backend/etc/passwd"
        # which does NOT start with /app/backend/uploads → 400
        # But requests strips ".." from url. Use urllib3 low-level to keep them.
        import urllib.parse
        # send the raw traversal path
        r = requests.get(
            f"{BASE_URL}/api/uploads/%2E%2E/etc/passwd", timeout=30,
        )
        assert r.status_code in (400, 404), f"traversal not blocked, got {r.status_code}: {r.text[:200]}"


# ---------- 4. Sentiment AI themes ----------
class TestSentimentThemes:
    def test_analyze_themes_success_or_422(self, admin_token):
        """POST analyze-themes → returns themes+pricing_note OR 422 if <3 reviews."""
        A = {"Authorization": f"Bearer {admin_token}"}
        # Clear today's cache first to force fresh (best-effort)
        r = requests.post(
            f"{BASE_URL}/api/sentiment-pricing/default/analyze-themes",
            headers=A, timeout=120,
        )
        if r.status_code == 422:
            pytest.shared_themes_skip = True  # type: ignore
            pytest.skip("default property has <3 text reviews (422 as documented)")
        assert r.status_code == 200, f"analyze-themes {r.status_code}: {r.text[:400]}"
        d = r.json()
        assert "themes" in d and isinstance(d["themes"], list)
        assert "pricing_note" in d
        assert "reviews_analyzed" in d
        assert d["reviews_analyzed"] >= 3
        if d["themes"]:
            t0 = d["themes"][0]
            for k in ["theme", "score", "summary"]:
                assert k in t0, f"missing {k} in theme: {t0}"

    def test_analyze_themes_cached_fast(self, admin_token):
        """Second call same day should be cached (<3s)."""
        if getattr(pytest, "shared_themes_skip", False):
            pytest.skip("<3 reviews")
        A = {"Authorization": f"Bearer {admin_token}"}
        t0 = time.time()
        r = requests.post(
            f"{BASE_URL}/api/sentiment-pricing/default/analyze-themes",
            headers=A, timeout=30,
        )
        elapsed = time.time() - t0
        assert r.status_code == 200
        assert elapsed < 5, f"cached call slow: {elapsed:.1f}s"

    def test_analyze_themes_low_reviews_422(self, admin_token):
        """Property with no/<3 reviews should return 422."""
        A = {"Authorization": f"Bearer {admin_token}"}
        fake_pid = f"TEST_no_reviews_{uuid.uuid4().hex[:8]}"
        r = requests.post(
            f"{BASE_URL}/api/sentiment-pricing/{fake_pid}/analyze-themes",
            headers=A, timeout=30,
        )
        assert r.status_code == 422, f"expected 422 got {r.status_code}: {r.text[:200]}"


# ---------- 5. Regression ----------
class TestRegression:
    def test_sentiment_pricing_get(self, admin_token):
        A = {"Authorization": f"Bearer {admin_token}"}
        r = requests.get(f"{BASE_URL}/api/sentiment-pricing/default", headers=A, timeout=30)
        assert r.status_code == 200
        d = r.json()
        for k in ["property_id", "index", "signal", "suggested_adj_pct"]:
            assert k in d

    def test_rate_mix_all(self, admin_token):
        A = {"Authorization": f"Bearer {admin_token}"}
        r = requests.get(f"{BASE_URL}/api/rate-mix/all", headers=A, timeout=30)
        assert r.status_code == 200

    def test_login_ok(self):
        r = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN, timeout=30)
        assert r.status_code == 200
        assert "token" in r.json()
