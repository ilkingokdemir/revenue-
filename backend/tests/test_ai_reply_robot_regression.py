"""
Comprehensive regression tests for AI Reply Robot (AI Yanıt Robotu) feature set.
Covers: learning_agent, service_recovery, surveys public/qr, review_sources,
reputation_benchmark, gbp_publish, mobile push prefs, scheduler triggers.
"""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://review-hub-108.preview.emergentagent.com").rstrip("/")
PROPERTY_ID = "default"

ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"


@pytest.fixture(scope="session")
def token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:300]}"
    tok = r.json().get("token")
    assert tok
    return tok


@pytest.fixture(scope="session")
def H(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# ---------- 1. Auth ----------
def test_login(token):
    assert token and len(token) > 20


# ---------- 2. Inbox ----------
def test_inbox(H):
    r = requests.get(f"{BASE_URL}/api/ai-agent/inbox/{PROPERTY_ID}", headers=H, timeout=30)
    assert r.status_code == 200, r.text[:200]
    j = r.json()
    assert "review_count" in j and "complaint_count" in j
    assert "items" in j
    # save for later
    pytest.INBOX = j


# ---------- 3. Draft (LLM 10-20s) ----------
def test_draft_generate(H):
    inbox = getattr(pytest, "INBOX", None) or requests.get(
        f"{BASE_URL}/api/ai-agent/inbox/{PROPERTY_ID}", headers=H, timeout=30).json()
    items = inbox.get("items", [])
    if not items:
        pytest.skip("no inbox items")
    src = items[0]
    r = requests.post(f"{BASE_URL}/api/ai-agent/draft", headers=H, timeout=60,
                      json={"property_id": PROPERTY_ID,
                            "source_type": src["source_type"],
                            "source_id": src.get("source_id") or src.get("id")})
    assert r.status_code == 200, r.text[:400]
    j = r.json()
    assert j.get("ai_text") or j.get("draft_text") or j.get("text")
    assert "lessons_applied" in j or "draft_id" in j or "id" in j
    pytest.LAST_DRAFT = j


def test_draft_paste(H):
    r = requests.post(f"{BASE_URL}/api/ai-agent/draft/paste", headers=H, timeout=60,
                      json={"property_id": PROPERTY_ID, "kind": "complaint",
                            "text": "Odada su sızıntısı vardı ve resepsiyon çok geç ilgilendi."})
    assert r.status_code == 200, r.text[:400]
    j = r.json()
    assert j.get("ai_text") or j.get("draft_text") or j.get("text")
    assert "draft_id" in j or "id" in j
    pytest.PASTE_DRAFT_ID = j.get("draft_id") or j.get("id")


# ---------- 4. Quality check ----------
def test_quality_junk(H):
    draft_id = getattr(pytest, "PASTE_DRAFT_ID", None)
    if not draft_id:
        pytest.skip("no draft")
    r = requests.post(f"{BASE_URL}/api/ai-agent/quality-check", headers=H, timeout=30,
                      json={"draft_id": draft_id, "final_text": "tamam bakarız işte olur"})
    assert r.status_code == 200, r.text[:200]
    j = r.json()
    assert 0 <= j["score"] <= 100
    assert j["warn"] is True


def test_quality_polite(H):
    draft_id = getattr(pytest, "PASTE_DRAFT_ID", None)
    if not draft_id:
        pytest.skip("no draft")
    polite = ("Değerli misafirimiz, yaşadığınız rahatsızlık için içtenlikle özür dileriz. "
              "Bakım ekibimiz konuyu inceledi, süreç iyileştirme planımıza dahil edildi. "
              "Bir sonraki konaklamanızda telafi etmekten memnuniyet duyarız. Saygılarımızla.")
    r = requests.post(f"{BASE_URL}/api/ai-agent/quality-check", headers=H, timeout=30,
                      json={"draft_id": draft_id, "final_text": polite})
    assert r.status_code == 200
    assert r.json()["warn"] is False


# ---------- 5. Send draft ----------
def test_send_draft(H):
    draft_id = getattr(pytest, "PASTE_DRAFT_ID", None)
    if not draft_id:
        pytest.skip("no draft")
    edited = ("Değerli misafirimiz, geri bildiriminiz için teşekkür ederiz. Sorunu inceledik. "
              "Saygılarımızla, Hotel Ekibi.")
    r = requests.post(f"{BASE_URL}/api/ai-agent/send/{draft_id}", headers=H, timeout=30,
                      json={"final_text": edited})
    assert r.status_code == 200, r.text[:300]
    j = r.json()
    assert j.get("was_edited") is True
    assert j.get("learned_count", 0) >= 0


# ---------- 6. Lessons CRUD ----------
def test_lessons_flow(H):
    r = requests.get(f"{BASE_URL}/api/ai-agent/lessons/{PROPERTY_ID}", headers=H, timeout=15)
    assert r.status_code == 200
    lst_before = r.json()

    r2 = requests.post(f"{BASE_URL}/api/ai-agent/lessons/{PROPERTY_ID}", headers=H, timeout=15,
                       json={"rule": "TEST_regression rule always end with saygılarımızla"})
    assert r2.status_code in (200, 201), r2.text[:200]
    new_id = r2.json().get("id") or r2.json().get("_id") or r2.json().get("rule_id")

    if new_id:
        rd = requests.delete(f"{BASE_URL}/api/ai-agent/lessons/{PROPERTY_ID}/{new_id}", headers=H, timeout=15)
        assert rd.status_code in (200, 204)


# ---------- 7. Stats & Report ----------
def test_stats(H):
    r = requests.get(f"{BASE_URL}/api/ai-agent/stats/{PROPERTY_ID}", headers=H, timeout=15)
    assert r.status_code == 200
    j = r.json()
    for k in ("sent", "edited", "approval_rate", "avg_quality", "by_type"):
        assert k in j, f"missing {k}"


def test_report(H):
    r = requests.get(f"{BASE_URL}/api/ai-agent/report/{PROPERTY_ID}", headers=H, timeout=15)
    assert r.status_code == 200
    j = r.json()
    assert "weekly" in j or "series" in j or "weekly_series" in j
    assert "totals" in j or "totals_7d" in j or "sent_total" in j
    assert "gbp_queue_pending" in j


# ---------- 8. Batch draft ----------
def test_batch_draft(H):
    r = requests.post(f"{BASE_URL}/api/ai-agent/batch-draft/{PROPERTY_ID}", headers=H, timeout=120)
    assert r.status_code == 200, r.text[:200]
    j = r.json()
    assert "drafted_count" in j and "skipped_existing" in j


# ---------- 9. Portfolio ----------
def test_portfolio(H):
    r = requests.get(f"{BASE_URL}/api/ai-agent/portfolio-report", headers=H, timeout=30)
    assert r.status_code == 200
    j = r.json()
    rows = j.get("rows") or j.get("properties") or j
    assert isinstance(rows, list)
    assert len(rows) >= 1


# ---------- 10. Categorize ----------
def test_categorize(H):
    r = requests.post(f"{BASE_URL}/api/ai-agent/categorize/{PROPERTY_ID}", headers=H, timeout=120)
    assert r.status_code == 200, r.text[:200]
    r2 = requests.get(f"{BASE_URL}/api/ai-agent/categories/{PROPERTY_ID}", headers=H, timeout=30)
    assert r2.status_code == 200
    j = r2.json()
    assert "averages" in j or "categories" in j
    assert "weakest" in j


# ---------- 11. Weak area task ----------
def test_weak_area(H):
    r = requests.post(f"{BASE_URL}/api/ai-agent/weak-area-task/{PROPERTY_ID}", headers=H, timeout=30)
    assert r.status_code == 200, r.text[:200]
    j = r.json()
    assert "created" in j


# ---------- 12. Config ----------
def test_config(H):
    r = requests.get(f"{BASE_URL}/api/ai-agent/config/{PROPERTY_ID}", headers=H, timeout=15)
    assert r.status_code == 200
    cfg = r.json()
    payload = {
        "sign_off": cfg.get("sign_off", "Saygılarımızla"),
        "tone": cfg.get("tone", "professional"),
        "warn_threshold": 70,
        "report_email": "regression@test.com",
    }
    r2 = requests.put(f"{BASE_URL}/api/ai-agent/config/{PROPERTY_ID}", headers=H, json=payload, timeout=15)
    assert r2.status_code == 200
    r3 = requests.get(f"{BASE_URL}/api/ai-agent/config/{PROPERTY_ID}", headers=H, timeout=15)
    assert r3.json().get("report_email") == "regression@test.com"


# ---------- 13. Review sources ----------
def test_review_sources_flow(H):
    r = requests.get(f"{BASE_URL}/api/review-sources/{PROPERTY_ID}", headers=H, timeout=15)
    assert r.status_code == 200
    original = r.json()

    payload = {
        "google_place_id": "",
        "booking_url": "",
        "tripadvisor_url": "https://tripadvisor.com/hotel-regression"
    }
    r2 = requests.put(f"{BASE_URL}/api/review-sources/{PROPERTY_ID}", headers=H, json=payload, timeout=15)
    assert r2.status_code == 200

    r3 = requests.post(f"{BASE_URL}/api/review-sources/{PROPERTY_ID}/sync-now", headers=H, timeout=60)
    assert r3.status_code == 200
    assert "total_new" in r3.json()

    pytest.SOURCES_SET = True


# ---------- 14. Reputation ----------
def test_reputation(H):
    payload = {"competitors": [{"name": "Competitor Regression", "google_place_id": "test123"}]}
    r = requests.put(f"{BASE_URL}/api/reputation/config/{PROPERTY_ID}", headers=H, json=payload, timeout=15)
    assert r.status_code == 200
    r2 = requests.post(f"{BASE_URL}/api/reputation/scan/{PROPERTY_ID}", headers=H, timeout=60)
    assert r2.status_code == 200
    r3 = requests.get(f"{BASE_URL}/api/reputation/benchmark/{PROPERTY_ID}", headers=H, timeout=30)
    assert r3.status_code == 200
    j = r3.json()
    rows = j.get("rows") or j.get("benchmark") or j
    text = str(rows)
    assert "Bizim Otel" in text or "bizim" in text.lower()


# ---------- 15. Public survey ----------
def test_public_survey_get():
    r = requests.get(f"{BASE_URL}/api/surveys/public/qr-{PROPERTY_ID}", timeout=15)
    assert r.status_code == 200, r.text[:200]
    assert r.json().get("anytime") is True


def test_public_survey_nps10_review_prompt():
    # sources set with tripadvisor_url in previous test
    r = requests.post(f"{BASE_URL}/api/surveys/public/qr-{PROPERTY_ID}", timeout=15,
                      json={"nps_score": 10, "guest_name": "TEST_regression", "answers": {}})
    assert r.status_code == 200, r.text[:200]
    j = r.json()
    rp = j.get("review_prompt", {})
    assert rp.get("show") is True, f"expected show True, got {rp}"


def test_public_survey_nps2_complaint():
    r = requests.post(f"{BASE_URL}/api/surveys/public/qr-{PROPERTY_ID}", timeout=15,
                      json={"nps_score": 2, "guest_name": "TEST_regression_low",
                            "answers": {"comment": "temizlik kötüydü"}})
    assert r.status_code == 200
    time.sleep(2)
    # complaint should appear in inbox
    h = {"Authorization": f"Bearer {token_module_scope()}"}
    r2 = requests.get(f"{BASE_URL}/api/ai-agent/inbox/{PROPERTY_ID}", headers=h, timeout=30)
    items = r2.json().get("items", [])
    names = [str(i) for i in items]
    joined = " ".join(names)
    assert "TEST_regression_low" in joined or any(i.get("source_type") == "complaint" for i in items)


def token_module_scope():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    return r.json().get("token")


def test_qr_image(H):
    r = requests.get(f"{BASE_URL}/api/surveys/qr-image/{PROPERTY_ID}", headers=H, timeout=30)
    assert r.status_code == 200
    assert "image/png" in r.headers.get("content-type", "")


# ---------- 16. Service recovery / complaint routing ----------
def test_service_recovery_create_and_track(H):
    payload = {
        "property_id": PROPERTY_ID,
        "guest_name": "TEST_regression_recovery",
        "category": "cleanliness",
        "text": "Room dirty TEST",
        "severity": "medium",
    }
    r = requests.post(f"{BASE_URL}/api/service-recovery", headers=H, json=payload, timeout=30)
    assert r.status_code in (200, 201), r.text[:300]
    j = r.json()
    assert j.get("routed_department") == "housekeeping"
    assert j.get("routed_task_id")
    cid = j.get("id") or j.get("_id") or j.get("complaint_id")
    assert cid

    # tracking-link
    rt = requests.get(f"{BASE_URL}/api/service-recovery/{cid}/tracking-link", headers=H, timeout=15)
    assert rt.status_code == 200, rt.text[:200]
    link = rt.json().get("tracking_link") or rt.json().get("url")
    assert link and link.startswith("https://")
    token_val = link.rstrip("/").split("/")[-1]

    # public track (no auth)
    rp = requests.get(f"{BASE_URL}/api/public/complaint-track/{token_val}", timeout=15)
    assert rp.status_code == 200, rp.text[:200]
    pj = rp.json()
    assert "status" in pj and "guest_name" in pj
    pytest.TRACK_TOKEN = token_val


def test_service_recovery_wifi_maintenance(H):
    payload = {
        "property_id": PROPERTY_ID,
        "guest_name": "TEST_regression_wifi",
        "category": "wifi",
        "text": "Wifi çalışmıyor",
    }
    r = requests.post(f"{BASE_URL}/api/service-recovery", headers=H, json=payload, timeout=30)
    assert r.status_code in (200, 201)
    assert r.json().get("routed_department") == "maintenance"


# ---------- 17. Mobile push prefs ----------
def test_mobile_push_prefs(H):
    r = requests.get(f"{BASE_URL}/api/mobile/push-prefs", headers=H, timeout=15)
    assert r.status_code == 200
    j = r.json()
    assert "new_complaint" in j
    keys = [k for k in j.keys() if isinstance(j[k], bool)]
    assert len(keys) >= 4, f"expected >=4 pref keys, got {list(j.keys())}"

    r2 = requests.post(f"{BASE_URL}/api/mobile/push-prefs", headers=H,
                       json={**j, "new_complaint": True}, timeout=15)
    assert r2.status_code == 200


# ---------- 18. Scheduler triggers ----------
@pytest.mark.parametrize("job", ["ai_morning_drafts", "ai_weekly_summary", "review_source_sync", "reputation_scan"])
def test_scheduler_trigger(H, job):
    r = requests.post(f"{BASE_URL}/api/scheduler/trigger/all/{job}", headers=H, timeout=120)
    assert r.status_code == 200, f"{job}: {r.text[:200]}"
    j = r.json()
    st = j.get("status") or j.get("result") or ""
    assert st in ("ok", "success", "triggered") or j.get("ok") is True or j.get("success") is True


# ---------- 19. Regression: /api/reviews ----------
def test_reviews_regression(H):
    r = requests.get(f"{BASE_URL}/api/reviews", headers=H, params={"property_id": PROPERTY_ID}, timeout=30)
    assert r.status_code == 200


# ---------- 20. Cleanup: reset sources to empty ----------
def test_zzz_cleanup_sources(H):
    payload = {"google_place_id": "", "booking_url": "", "tripadvisor_url": ""}
    r = requests.put(f"{BASE_URL}/api/review-sources/{PROPERTY_ID}", headers=H, json=payload, timeout=60)
    assert r.status_code == 200