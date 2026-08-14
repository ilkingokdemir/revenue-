"""Iteration 524 — internalize_expertise + Uzman Kuralları + chat expert persona."""
import os
import pytest
import requests

def _load_backend_url():
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if v:
        return v.rstrip("/")
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                return line.split("=", 1)[1].strip().rstrip("/")
    raise RuntimeError("REACT_APP_BACKEND_URL not set")


BASE_URL = _load_backend_url()
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PW = "HotelAdmin2026!"


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PW}, timeout=30)
    assert r.status_code == 200, r.text
    tok = r.json().get("access_token") or r.json().get("token")
    assert tok
    return tok


@pytest.fixture(scope="module")
def hdr(token):
    return {"Authorization": f"Bearer {token}"}


# ── Internalize (default) ──────────────────────────────────────────────
def test_internalize_default_returns_rules(hdr):
    r = requests.post(f"{BASE_URL}/api/rm-expertise/default/internalize", headers=hdr, timeout=60)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["property_id"] == "default"
    assert data["rules_count"] >= 5, data
    assert isinstance(data["rules"], list)
    required_sources = {"edu_overbooking_model", "strat_max_profit_deep",
                        "study_variability", "tech_pace_signals"}
    got_sources = {r_["source_id"] for r_ in data["rules"]}
    missing = required_sources - got_sources
    assert not missing, f"missing source_ids: {missing}; got={got_sources}"
    for rule in data["rules"]:
        for k in ("sira", "baslik", "kural", "rakamlar", "source_id", "computed_at"):
            assert k in rule, f"missing field {k} in {rule}"


def test_expert_rules_persisted_and_idempotent(hdr):
    r1 = requests.post(f"{BASE_URL}/api/rm-expertise/default/internalize", headers=hdr, timeout=60)
    assert r1.status_code == 200
    count1 = r1.json()["rules_count"]

    g1 = requests.get(f"{BASE_URL}/api/rm-expertise/default/expert-rules", headers=hdr, timeout=30)
    assert g1.status_code == 200
    gdata = g1.json()
    assert gdata["count"] == count1
    assert len(gdata["rules"]) == count1
    # No mongo _id leakage
    for r_ in gdata["rules"]:
        assert "_id" not in r_

    # Re-run — no duplication (delete+insert)
    r2 = requests.post(f"{BASE_URL}/api/rm-expertise/default/internalize", headers=hdr, timeout=60)
    assert r2.status_code == 200
    count2 = r2.json()["rules_count"]
    g2 = requests.get(f"{BASE_URL}/api/rm-expertise/default/expert-rules", headers=hdr, timeout=30)
    assert g2.json()["count"] == count2 == count1, (count1, count2, g2.json()["count"])


# ── Learning cycle auto-refresh (city-gate) ────────────────────────────
def test_learning_cycle_refreshes_rules(hdr):
    # Baseline
    b0 = requests.get(f"{BASE_URL}/api/rm-expertise/city-gate/expert-rules", headers=hdr, timeout=30).json()
    old_ts = None
    if b0.get("rules"):
        old_ts = b0["rules"][0].get("computed_at")

    lr = requests.post(f"{BASE_URL}/api/revenue-brain/city-gate/learn", headers=hdr, timeout=120)
    assert lr.status_code == 200, lr.text

    g = requests.get(f"{BASE_URL}/api/rm-expertise/city-gate/expert-rules", headers=hdr, timeout=30)
    assert g.status_code == 200
    data = g.json()
    assert data["count"] >= 4, data
    new_ts = data["rules"][0]["computed_at"]
    if old_ts:
        assert new_ts >= old_ts  # refreshed


# ── Chat expert persona (1 LLM call max) ───────────────────────────────
def test_chat_expert_no_citations(hdr):
    payload = {"message": "Maksimum kâr için bu hafta ne yapmalıyım?"}
    r = requests.post(f"{BASE_URL}/api/revenue/copilot/default/chat",
                      headers=hdr, json=payload, timeout=120)
    assert r.status_code == 200, r.text
    body = r.json()
    reply = (body.get("reply") or body.get("response") or body.get("content") or "").lower()
    assert reply, f"empty reply: {body}"
    # Forbidden citation language
    for banned in ["kaynak", "kütüphane", "bilgi taban"]:
        assert banned not in reply, f"forbidden token '{banned}' in reply: {reply[:400]}"
