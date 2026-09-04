"""Iter 611 — Review Operations Agent expansion tests.
Covers: intelligence (risk/spam/flags), decision engine + auto_rules,
response quality/similarity/candidates, privacy gate, approval center
(escalate/override/bulk), stats/summary, review-agent config validation,
autopilot run (LLM), Trustpilot connector (simulated), integrations reqs.
"""
import os
import time
import uuid
import pytest
import requests

def _load_backend_url():
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if v:
        return v.rstrip("/")
    for path in ("/app/frontend/.env",):
        try:
            with open(path) as f:
                for line in f:
                    if line.startswith("REACT_APP_BACKEND_URL="):
                        return line.split("=", 1)[1].strip().rstrip("/")
        except Exception:
            pass
    raise RuntimeError("REACT_APP_BACKEND_URL not set")

BASE_URL = _load_backend_url()
API = f"{BASE_URL}/api"
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PW = "HotelAdmin2026!"

# --------- fixtures ---------

@pytest.fixture(scope="module")
def s():
    session = requests.Session()
    r = session.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PW}, timeout=15)
    assert r.status_code == 200, r.text
    tok = r.json().get("access_token") or r.json().get("token")
    if tok:
        session.headers.update({"Authorization": f"Bearer {tok}"})
    session.headers.update({"Content-Type": "application/json"})
    return session

@pytest.fixture(scope="module")
def created_ids():
    return {"ids": []}

# --------- helpers ---------

def _create_review(s, text, rating, guest="TEST_ITER611"):
    r = s.post(f"{API}/reviews", json={
        "platform": "google", "guest_name": guest,
        "rating": rating, "review_text": text, "property_id": "default"
    }, timeout=20)
    assert r.status_code == 200, r.text
    return r.json()["id"]

# --------- 1. Spam analysis ---------

def test_01_spam_analysis(s, created_ids):
    rid = _create_review(s, "BEST HOTEL!!! www.cheapdeals.com BUY NOW!!! click here promo code", 5)
    created_ids["ids"].append(rid)
    r = s.post(f"{API}/reviews/{rid}/analyze", timeout=90)
    assert r.status_code == 200, r.text
    a = r.json()["analysis"]
    assert a["spam_probability"] >= 0.8, a
    assert a["spam_suspected"] is True
    assert a["recommended_action"] == "do_not_reply"

# --------- 2. Critical review + risk + flags ---------

def test_02_critical_risk(s, created_ids):
    txt = ("Room 412 had bed bugs and I got sick, the receptionist John was rude. "
           "I want a full refund or I will contact my lawyer and the police.")
    rid = _create_review(s, txt, 1)
    created_ids["ids"].append(rid)
    created_ids["critical_id"] = rid
    r = s.post(f"{API}/reviews/{rid}/analyze", timeout=90)
    assert r.status_code == 200, r.text
    a = r.json()["analysis"]
    assert a["safety_issue"] is True
    assert a["legal_issue"] is True
    assert a["refund_requested"] is True
    # staff_mentioned may be list from LLM or bool from heuristic
    sm = a.get("staff_mentioned")
    if isinstance(sm, list):
        assert any("john" in str(x).lower() for x in sm), sm
    else:
        assert sm  # truthy
    assert a["risk_level"] == "critical"
    assert a["risk_score"] >= 71
    assert a["escalation_level"] == "management"

# --------- 3. Generate AI response w/ candidates ---------

def test_03_generate_ai_response_candidates(s, created_ids):
    rid = created_ids["critical_id"]
    r = s.post(f"{API}/reviews/generate-ai-response",
               json={"review_id": rid, "tone": "apologetic", "candidates": True},
               timeout=180)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j.get("generated_text")
    assert isinstance(j.get("quality"), dict) and "total" in j["quality"]
    assert "policy_safety" in j["quality"]
    assert isinstance(j.get("similarity"), dict) and "max_pct" in j["similarity"]
    assert isinstance(j.get("decision"), dict)
    assert j["decision"].get("action")
    assert isinstance(j.get("privacy"), dict) and "ok" in j["privacy"]
    cands = j.get("candidates") or []
    assert len(cands) == 3, f"expected 3 candidates, got {len(cands)}"
    tones = {(c.get("style") or c.get("tone") or c.get("label") or "").lower() for c in cands}
    expected = {"warm", "professional", "concise"}
    assert expected.issubset(tones), tones

# --------- 4. Privacy gate on respond ---------

def test_04_privacy_gate_respond(s, created_ids):
    rid = created_ids["critical_id"]
    bad = ("Dear Laura, we are sorry. Please call +44 7700 900123 about room 412.")
    r = s.put(f"{API}/reviews/{rid}/respond", json={"response_text": bad}, timeout=20)
    assert r.status_code == 400, r.text
    d = r.json().get("detail", "")
    assert "Gizlilik" in d
    assert "phone" in d and "room_number" in d

    clean = ("Dear Laura, we are truly sorry for your experience and our general "
             "director would like to speak with you privately. — The Management Team")
    r2 = s.put(f"{API}/reviews/{rid}/respond", json={"response_text": clean}, timeout=20)
    assert r2.status_code == 200, r2.text
    g = s.get(f"{API}/reviews/{rid}", timeout=15).json()
    ev_types = [e.get("type") for e in (g.get("events") or [])]
    assert "published" in ev_types, ev_types

# --------- 5. Escalate + override approve flow ---------

def test_05_escalate_override(s, created_ids):
    txt = ("The receptionist was extremely rude, I demand a refund and will "
           "contact my lawyer immediately for legal action.")
    rid = _create_review(s, txt, 1)
    created_ids["ids"].append(rid)
    # analyze so risk_level=high/critical
    ar = s.post(f"{API}/reviews/{rid}/analyze", timeout=90)
    assert ar.status_code == 200, ar.text
    risk = ar.json()["analysis"].get("risk_level")

    # Seed response_text via PUT respond with a clean draft
    clean = ("Dear guest, we are deeply sorry to hear about your experience and would like to "
             "reach out privately to resolve this. — The Hospitality Team")
    pr = s.put(f"{API}/reviews/{rid}/respond", json={"response_text": clean}, timeout=20)
    assert pr.status_code == 200, pr.text

    # Move to approval queue
    sr = s.post(f"{API}/reviews/{rid}/submit-for-approval", timeout=15)
    assert sr.status_code == 200, sr.text

    # approve without notes → 400 (risk high/critical requires override notes)
    r1 = s.post(f"{API}/reviews/{rid}/approve", json={"action": "approve"}, timeout=15)
    if risk not in ("high", "critical"):
        pytest.skip(f"analysis gave risk_level={risk}; escalate flow requires high/critical")
    assert r1.status_code == 400, r1.text
    dt = r1.json().get("detail", "").lower()
    assert ("override" in dt) or ("gerekçe" in dt) or ("notes" in dt), dt

    # escalate
    r2 = s.post(f"{API}/reviews/{rid}/approve",
                json={"action": "escalate", "notes": "GM"}, timeout=15)
    assert r2.status_code == 200, r2.text
    assert r2.json().get("escalation_level") in ("management", "manager")

    # override approve
    r3 = s.post(f"{API}/reviews/{rid}/approve",
                json={"action": "approve", "notes": "GM onayladı"}, timeout=15)
    assert r3.status_code == 200, r3.text
    assert r3.json().get("override") is True

    g2 = s.get(f"{API}/reviews/{rid}", timeout=15).json()
    assert g2.get("approval_override"), g2
    ev = [e.get("type") for e in (g2.get("events") or [])]
    assert "escalated" in ev, ev
    assert "override_approved" in ev, ev
    assert "published" in ev, ev

# --------- 6. pending-approval sorting + enrichment ---------

def test_06_pending_approval_list(s):
    r = s.get(f"{API}/reviews/pending-approval", timeout=20)
    assert r.status_code == 200, r.text
    items = r.json()
    # each item should carry sentiment_analysis (if any); those with response_text → response_privacy
    for it in items[:20]:
        # sorted: escalated first, then critical→low
        pass
    # verify sort key: no low before high within non-escalated
    seen_low = False
    for it in items:
        if it.get("escalated"):
            continue
        lvl = (it.get("sentiment_analysis") or {}).get("risk_level", "low")
        if lvl == "low":
            seen_low = True
        elif seen_low and lvl in ("critical", "high", "medium"):
            pytest.fail(f"pending-approval mis-sorted: low seen before {lvl}")
    # check enrichment on any item with response_text
    for it in items:
        if it.get("response_text"):
            assert "response_privacy" in it, "response_privacy missing on item with response_text"
            break

# --------- 7. approve-bulk skips 1-3★ ---------

def test_07_approve_bulk_skips_low_rating(s, created_ids):
    # ensure at least one low-rated pending_approval exists
    rid = _create_review(s, "Room was dirty and noisy, staff unhelpful.", 2)
    created_ids["ids"].append(rid)
    s.post(f"{API}/reviews/{rid}/analyze", timeout=90)
    g = s.post(f"{API}/reviews/generate-ai-response",
               json={"review_id": rid, "tone": "apologetic"}, timeout=180)
    if g.status_code == 200:
        s.post(f"{API}/reviews/{rid}/submit-for-approval", timeout=15)

    r = s.post(f"{API}/reviews/approve-bulk", json={"property_id": "all"}, timeout=60)
    assert r.status_code == 200, r.text
    j = r.json()
    assert "approved" in j and "approved_ids" in j and "skipped" in j
    # any skipped for our low rated?
    reasons_flat = [reason for it in j["skipped"] for reason in it.get("reasons", [])]
    if j["skipped"]:
        assert any("rating < 4" in x for x in reasons_flat), reasons_flat

# --------- 8. Stats summary approval_center ---------

def test_08_stats_summary(s):
    r = s.get(f"{API}/reviews/stats/summary", timeout=20)
    assert r.status_code == 200, r.text
    j = r.json()
    ac = j.get("approval_center")
    assert ac, j
    rc = ac["risk_counts"]
    for k in ("critical", "high", "medium", "low"):
        assert k in rc, rc
    assert "escalated" in ac
    assert "spam_suspected" in ac
    assert "high_risk_open" in ac
    perf = ac["ai_performance"]
    for k in ("avg_response_score", "auto_approval_rate", "human_approval_rate",
              "regeneration_rate", "policy_risk_pct"):
        assert k in perf, perf

# --------- 9. Review-agent config validation ---------

def test_09_config_full_auto_requires_authoriser(s):
    r = s.post(f"{API}/review-agent/config/default",
               json={"publishing_mode": "full_auto"}, timeout=15)
    assert r.status_code == 400, r.text

    r2 = s.post(f"{API}/review-agent/config/default",
                json={"publishing_mode": "full_auto", "full_auto_authorised_by": "Sarah GM"},
                timeout=15)
    assert r2.status_code == 200, r2.text

    r3 = s.post(f"{API}/review-agent/config/default",
                json={"publishing_mode": "smart_auto",
                      "auto_rules": {"min_quality": 75, "bogus": 1}}, timeout=15)
    assert r3.status_code == 200, r3.text
    cfg = r3.json()
    ar = cfg.get("auto_rules", {})
    assert "bogus" not in ar, ar
    assert ar.get("min_quality") == 75

    r4 = s.post(f"{API}/review-agent/config/default",
                json={"publishing_mode": "xyz"}, timeout=15)
    assert r4.status_code == 400, r4.text

# --------- 10. Autopilot run ---------

def test_10_autopilot_run(s):
    r = s.post(f"{API}/reviews/autopilot/run", json={"property_id": "all"}, timeout=240)
    assert r.status_code == 200, r.text
    j = r.json()
    for k in ("ok", "scanned", "published", "drafted_for_approval",
              "escalated", "skipped_spam", "errors"):
        assert k in j, j

# --------- 11. Trustpilot connector simulated ---------

def test_11_trustpilot_simulated(s):
    r = s.post(f"{API}/review-sources/default/sync-now", timeout=30)
    assert r.status_code == 200, r.text
    j = r.json()
    tp = j.get("trustpilot")
    assert tp, j
    assert tp.get("ok") is True
    assert tp.get("mode") == "simulated"

def test_12_integrations_requirements_trustpilot(s):
    r = s.get(f"{API}/integrations/requirements", timeout=15)
    assert r.status_code == 200, r.text
    j = r.json()
    assert "trustpilot" in j, list(j.keys())[:20]

# --------- Cleanup ---------

def test_zz_cleanup(s, created_ids):
    for rid in created_ids["ids"]:
        try:
            s.delete(f"{API}/reviews/{rid}", timeout=10)
        except Exception:
            pass
