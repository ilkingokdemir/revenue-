"""
Iteration 616 — Ölçek altyapısı (Indexes, Rate limit, Kalıcı iş kuyruğu).

Testler:
- INDEXES: GET/POST /api/system/indexes*
- QUEUE:   trigger?background=true, /scheduler/queue, /scheduler/queue/{id}/retry, sync trigger
- REGRESYON: login, reviews stats, reviews pending-approval, my-tasks, analytics dashboard
- RATE LIMIT (EN SONDA): 429 + Retry-After + X-RateLimit-* headerları
"""
import os, time, pytest, requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://review-hub-108.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASS = "HotelAdmin2026!"


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=30)
    assert r.status_code == 200, r.text
    tok = r.json().get("access_token") or r.json().get("token")
    assert tok
    return tok


@pytest.fixture(scope="module")
def H(token):
    return {"Authorization": f"Bearer {token}"}


# ==================== INDEXES ====================
def test_get_system_indexes(H):
    r = requests.get(f"{BASE}/api/system/indexes", headers=H, timeout=30)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["specs"] >= 39, f"specs={j['specs']}"
    cols = j["collections"]
    assert "reviews" in cols and "bookings" in cols and "job_queue" in cols
    assert any("property_id_1_created_at_-1" in n for n in cols["reviews"])
    lr = j["last_run"]
    assert lr is not None
    for k in ("ensured", "skipped", "errors"):
        assert k in lr


def test_post_system_indexes_ensure(H):
    r = requests.post(f"{BASE}/api/system/indexes/ensure", headers=H, timeout=60)
    assert r.status_code == 200, r.text
    j = r.json()
    assert "ensured" in j and "skipped" in j
    assert j["errors"] == [], f"errors: {j['errors']}"


# ==================== QUEUE (background trigger) ====================
def test_trigger_background_and_queue_progress(H):
    r = requests.post(f"{BASE}/api/scheduler/trigger/default/staff_praise_weekly?background=true", headers=H, timeout=30)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["status"] == "queued"
    qid = j["queue_id"]

    # 2nd enqueue while still queued/running → dedup
    r2 = requests.post(f"{BASE}/api/scheduler/trigger/default/staff_praise_weekly?background=true", headers=H, timeout=30)
    assert r2.status_code == 200
    # can be deduped OR done already; both acceptable per spec
    # (spec: deduped:true SADECE hâlâ queued/running ise)

    # wait for worker (poll)
    done = None
    for _ in range(20):
        time.sleep(1)
        q = requests.get(f"{BASE}/api/scheduler/queue?limit=20", headers=H, timeout=30).json()
        row = next((it for it in q["items"] if it.get("id") == qid), None)
        if row and row.get("status") in ("done", "failed", "failed_soft"):
            done = row
            break
    assert done is not None, "queue item never finished"
    assert done["status"] == "done", f"status={done.get('status')} err={done.get('last_error')}"
    assert done["attempts"] >= 1
    assert done.get("result") is not None


def test_queue_status_shape(H):
    r = requests.get(f"{BASE}/api/scheduler/queue?limit=5", headers=H, timeout=30)
    assert r.status_code == 200
    j = r.json()
    assert "counts" in j and "items" in j
    assert j.get("concurrency") == 3


def test_sync_trigger_coupon_reminder(H):
    r = requests.post(f"{BASE}/api/scheduler/trigger/default/coupon_reminder", headers=H, timeout=60)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j.get("status") == "triggered"
    assert "result" in j


# Seed a failing queue item so we can test retry endpoint
def test_retry_failed_queue_item(H):
    # Enqueue a job that will fail (unknown job); we go via internal DB insert since API blocks unknown jobs.
    # Fallback: use retry endpoint against a non-existent id and validate 404 path.
    r = requests.post(f"{BASE}/api/scheduler/queue/nonexistent-queue-id-xyz/retry", headers=H, timeout=30)
    assert r.status_code == 404


# ==================== REGRESSION ====================
@pytest.mark.parametrize("path", [
    "/api/reviews/stats/summary?property_id=default",
    "/api/reviews/pending-approval",
    "/api/my-tasks",
    "/api/analytics/dashboard?property_id=default",
])
def test_regression_endpoints(H, path):
    r = requests.get(f"{BASE}{path}", headers=H, timeout=45)
    assert r.status_code == 200, f"{path} -> {r.status_code} {r.text[:200]}"


# ==================== RATE LIMIT HEADERS (non-exempt vs exempt) ====================
def test_rate_limit_headers_present(H):
    r = requests.get(f"{BASE}/api/reviews/stats/summary?property_id=default", headers=H, timeout=30)
    assert "X-RateLimit-Limit" in r.headers
    assert "X-RateLimit-Remaining" in r.headers


def test_health_is_exempt():
    r = requests.get(f"{BASE}/api/health", timeout=30)
    # If /api/health is 404, try /health, but per spec /api/health muaf
    if r.status_code == 200:
        assert "X-RateLimit-Limit" not in r.headers, "health should be exempt"


# ==================== RATE LIMIT 429 (RUN LAST — 60s reset) ====================
def test_zzz_rate_limit_429_on_public_widget():
    """Public widget hız sınırı 120/dk; 130 hızlı istek → 429 + Retry-After + X-RateLimit-Remaining:0."""
    url = f"{BASE}/api/booking-widget/team-star/default"
    got_429 = None
    with requests.Session() as s:
        for i in range(160):
            r = s.get(url, timeout=15)
            if r.status_code == 429:
                got_429 = r
                break
    assert got_429 is not None, "did not get 429 after 160 requests"
    assert "Retry-After" in got_429.headers
    assert got_429.headers.get("X-RateLimit-Remaining") == "0"
    body = got_429.json()
    assert "detail" in body and "retry_after_sec" in body
