"""Iteration 504: End-to-end regression for the Social Media Module inside AI Reply Robot > Benchmark tab.

Covers: social drafts, image gen (Gemini), variants+select, refine, send-package (idempotent), publish (simulated), performance, best-time, drafts-pending + bulk approve, weekly report + PDF, guest photo upload flow, guest-photo-to-draft (with dedupe), photo-contest (Ayın Karesi) dedupe, and automation triggers.
"""
import os
import io
import time
import pytest
import requests
from PIL import Image

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://review-hub-108.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASS = "HotelAdmin2026!"
PID = "default"


# ---------- fixtures ----------
@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def H(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def state():
    """Shared state dict passed between tests."""
    return {}


# ---------- Auth / list ----------
def test_admin_login_and_drafts_list(H, state):
    r = requests.get(f"{BASE_URL}/api/reputation/social-drafts/{PID}", headers=H, timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "items" in data and isinstance(data["items"], list)
    state["initial_drafts_count"] = len(data["items"])


# ---------- Survey → Draft ----------
def test_survey_to_draft_praise(H, state):
    # First attempt
    r = requests.post(f"{BASE_URL}/api/reputation/survey-to-draft/{PID}", headers=H, timeout=60)
    if r.status_code == 404:
        # Seed a fresh 10/10 praise via public QR survey
        payload = {"nps_score": 10, "comment": "Harika bir tatildi, personel çok ilgiliydi.",
                   "guest_name": "TEST_Ayşe Yılmaz", "category_ratings": {"cleanliness": 5, "staff": 5}}
        sub = requests.post(f"{BASE_URL}/api/surveys/public/qr-{PID}", json=payload, timeout=30)
        assert sub.status_code in (200, 201), sub.text
        # retry
        r = requests.post(f"{BASE_URL}/api/reputation/survey-to-draft/{PID}", headers=H, timeout=60)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("draft_id") and body.get("draft")
    state["survey_draft_id"] = body["draft_id"]


# ---------- Image generation single (Gemini) ----------
def test_generate_image_single(H, state):
    draft_id = state["survey_draft_id"]
    r = requests.post(f"{BASE_URL}/api/reputation/social-drafts/{draft_id}/image",
                      headers=H, json={"style": "sicak"}, timeout=120)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["image_url"].startswith("/api/uploads/social_images/")
    assert body["style"] == "sicak"
    state["single_image_url"] = body["image_url"]


# ---------- Image variants + select ----------
def test_generate_variants_and_select(H, state):
    draft_id = state["survey_draft_id"]
    r = requests.post(f"{BASE_URL}/api/reputation/social-drafts/{draft_id}/image",
                      headers=H, json={"style": "minimal", "variants": 3}, timeout=180)
    assert r.status_code == 200, r.text
    variants = r.json().get("variants") or []
    assert 1 <= len(variants) <= 3
    state["variants"] = variants

    # Invalid select
    bad = requests.post(f"{BASE_URL}/api/reputation/social-drafts/{draft_id}/select-image",
                        headers=H, json={"image_url": "/api/uploads/social_images/notreal.png"},
                        timeout=30)
    assert bad.status_code == 400

    # Valid select
    ok = requests.post(f"{BASE_URL}/api/reputation/social-drafts/{draft_id}/select-image",
                       headers=H, json={"image_url": variants[0]}, timeout=30)
    assert ok.status_code == 200
    assert ok.json()["image_url"] == variants[0]


# ---------- Refine image ----------
def test_refine_image(H, state):
    draft_id = state["survey_draft_id"]
    # empty note → 400
    bad = requests.post(f"{BASE_URL}/api/reputation/social-drafts/{draft_id}/refine-image",
                        headers=H, json={"note": ""}, timeout=30)
    assert bad.status_code == 400
    # real refine
    r = requests.post(f"{BASE_URL}/api/reputation/social-drafts/{draft_id}/refine-image",
                      headers=H, json={"note": "daha aydınlık olsun"}, timeout=120)
    assert r.status_code == 200, r.text
    assert r.json().get("image_url")


# ---------- Send package (idempotent) ----------
def test_send_package_and_calendar(H, state):
    draft_id = state["survey_draft_id"]
    body = {"publish_date": "2026-08-25", "publish_time": "21:00"}
    r1 = requests.post(f"{BASE_URL}/api/reputation/social-drafts/{draft_id}/send-package",
                       headers=H, json=body, timeout=30)
    assert r1.status_code == 200, r1.text
    d1 = r1.json()
    assert d1.get("task_created") is True and d1.get("task_id")

    r2 = requests.post(f"{BASE_URL}/api/reputation/social-drafts/{draft_id}/send-package",
                       headers=H, json=body, timeout=30)
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2.get("task_created") is False
    assert d2.get("date_updated") is True

    cal = requests.get(f"{BASE_URL}/api/reputation/social-calendar/{PID}", headers=H, timeout=30)
    assert cal.status_code == 200
    items = cal.json()["items"]
    match = [i for i in items if i["draft_id"] == draft_id]
    assert match and match[0]["publish_time"] == "21:00"


# ---------- Publish (simulated) + performance + best-time ----------
def test_publish_simulated_and_performance(H, state):
    draft_id = state["survey_draft_id"]
    r = requests.post(f"{BASE_URL}/api/reputation/social-drafts/{draft_id}/publish",
                      headers=H, timeout=30)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("published") is True
    assert body.get("mode") == "simulated"

    p = requests.post(f"{BASE_URL}/api/reputation/social-drafts/{draft_id}/performance",
                      headers=H, json={"likes": 245, "reach": 4200, "comments": 18}, timeout=30)
    assert p.status_code == 200
    assert p.json()["performance"]["likes"] == 245

    perf = requests.get(f"{BASE_URL}/api/reputation/social-performance/{PID}", headers=H, timeout=30)
    assert perf.status_code == 200
    pd = perf.json()
    assert "rows" in pd and "insight" in pd


def test_best_time(H):
    r = requests.get(f"{BASE_URL}/api/reputation/best-time/{PID}", headers=H, timeout=30)
    assert r.status_code == 200
    body = r.json()
    assert body.get("has_data") is True
    assert body.get("best_day") and body.get("best_hour") is not None


# ---------- Drafts pending + bulk approve + single approve ----------
def test_drafts_pending_and_bulk_approve(H, state):
    r = requests.get(f"{BASE_URL}/api/reputation/social-drafts-pending", headers=H, timeout=30)
    assert r.status_code == 200
    items = r.json()["items"]
    assert isinstance(items, list)
    # every pending item should have a property_name field
    for i in items[:5]:
        assert "property_name" in i
    state["pending_items"] = items

    # If there are auto drafts, do bulk approve
    ids = [i["id"] for i in items[:2]]
    if ids:
        b = requests.post(f"{BASE_URL}/api/reputation/social-drafts/approve-bulk",
                          headers=H, json={"draft_ids": ids}, timeout=30)
        assert b.status_code == 200
        assert "approved" in b.json()

    # Single approve on the survey draft
    sd = state.get("survey_draft_id")
    if sd:
        s = requests.put(f"{BASE_URL}/api/reputation/social-drafts/{sd}/approve",
                         headers=H, timeout=30)
        assert s.status_code == 200


# ---------- Weekly report + PDF ----------
def test_weekly_report_and_pdf(H):
    r = requests.post(f"{BASE_URL}/api/reputation/social-report/run", headers=H, timeout=90)
    assert r.status_code == 200, r.text
    body = r.json()
    # workers.run_social_weekly_report should have queued mocked email
    assert isinstance(body, dict)

    p = requests.post(f"{BASE_URL}/api/reputation/social-report/pdf", headers=H, timeout=60)
    assert p.status_code == 200, p.text
    pdf_url = p.json().get("pdf_url")
    assert pdf_url
    # Download
    full = pdf_url if pdf_url.startswith("http") else f"{BASE_URL}{pdf_url}"
    d = requests.get(full, headers=H, timeout=60)
    assert d.status_code == 200
    ct = d.headers.get("content-type", "")
    assert "pdf" in ct.lower() or d.content[:4] == b"%PDF"


# ---------- Guest photo flow ----------
def test_guest_photo_flow(H, state):
    # create small test JPEG
    img = Image.new("RGB", (400, 400), color=(120, 180, 220))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=80)
    buf.seek(0)
    files = {"file": ("test.jpg", buf, "image/jpeg")}
    up = requests.post(f"{BASE_URL}/api/surveys/public/qr-{PID}/photo", files=files, timeout=30)
    assert up.status_code == 200, up.text
    photo_url = up.json()["photo_url"]
    assert photo_url.startswith("/api/uploads/survey_photos/")

    sub = requests.post(f"{BASE_URL}/api/surveys/public/qr-{PID}", json={
        "nps_score": 10, "guest_name": "TEST_Mert Kaya",
        "comment": "Muhteşem manzara!", "photo_url": photo_url,
        "photo_consent": True}, timeout=30)
    assert sub.status_code in (200, 201), sub.text

    photos = requests.get(f"{BASE_URL}/api/reputation/guest-photos/{PID}", headers=H, timeout=30)
    assert photos.status_code == 200
    items = photos.json()["items"]
    assert any(i.get("photo_url") == photo_url for i in items), "uploaded photo not listed"
    # find matching response id
    target = next(i for i in items if i.get("photo_url") == photo_url)
    resp_id = target["id"]
    state["photo_response_id"] = resp_id

    # convert
    c = requests.post(f"{BASE_URL}/api/reputation/guest-photo-to-draft/{resp_id}",
                      headers=H, timeout=30)
    assert c.status_code == 200, c.text
    assert c.json().get("draft_id")

    # dedupe
    c2 = requests.post(f"{BASE_URL}/api/reputation/guest-photo-to-draft/{resp_id}",
                       headers=H, timeout=30)
    assert c2.status_code == 400


# ---------- Photo contest (Ayın Karesi) ----------
def test_photo_contest_dedupe_and_draft_present(H):
    # First call may create OR return existing (0)
    r1 = requests.post(f"{BASE_URL}/api/reputation/photo-contest/run", headers=H, timeout=60)
    assert r1.status_code == 200, r1.text
    b1 = r1.json()
    assert "drafts_created" in b1 and "month" in b1

    # Second call must be dedupe (0)
    r2 = requests.post(f"{BASE_URL}/api/reputation/photo-contest/run", headers=H, timeout=60)
    assert r2.status_code == 200
    assert r2.json()["drafts_created"] == 0

    # Verify a photo_contest draft exists for property `default`
    lst = requests.get(f"{BASE_URL}/api/reputation/social-drafts/{PID}", headers=H, timeout=30)
    items = lst.json()["items"]
    pc = [i for i in items if i.get("source") == "photo_contest"]
    assert pc, "no photo_contest draft found in default property"
    d = pc[0]
    assert d.get("topic") == "ayın karesi"
    assert d.get("auto") is True
    assert d.get("image_url")


# ---------- Automation triggers ----------
def test_automation_triggers(H):
    endpoints = [
        "/api/reputation/trend-alerts/run",
        "/api/reputation/publish-alerts/run",
        "/api/reputation/winning-topic/run",
        "/api/ai-agent/winback-reminders/run",
    ]
    for ep in endpoints:
        r = requests.post(f"{BASE_URL}{ep}", headers=H, timeout=60)
        assert r.status_code == 200, f"{ep} → {r.status_code} {r.text[:200]}"


# ---------- Social connection GET/POST/masking, cleanup ----------
def test_social_connection_lifecycle(H):
    # initially disconnected
    r = requests.get(f"{BASE_URL}/api/reputation/social-connection/{PID}", headers=H, timeout=30)
    assert r.status_code == 200
    assert r.json()["connected"] is False

    # save test values
    s = requests.post(f"{BASE_URL}/api/reputation/social-connection/{PID}", headers=H, json={
        "meta_access_token": "EAABsbCS0testtokenvalue123456789",
        "ig_business_id": "17841400000000000",
        "fb_page_id": "1234567890"
    }, timeout=30)
    assert s.status_code == 200

    r2 = requests.get(f"{BASE_URL}/api/reputation/social-connection/{PID}", headers=H, timeout=30)
    body = r2.json()
    assert body["connected"] is True
    masked = body["meta_access_token_masked"]
    assert "…" in masked or "***" in masked
    assert "testtokenvalue" not in masked

    # CLEANUP — delete connection to preserve simulated mode for other tests
    from pymongo import MongoClient
    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    dbname = os.environ.get("DB_NAME", "test_database")
    MongoClient(mongo_url)[dbname].social_connections.delete_one({"property_id": PID})
    # verify cleaned
    r3 = requests.get(f"{BASE_URL}/api/reputation/social-connection/{PID}", headers=H, timeout=30)
    assert r3.json()["connected"] is False
