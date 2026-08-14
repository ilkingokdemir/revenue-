"""Iteration 522 backend tests: RM expertise + Chat run_optimizer capability + learn cycle sensitivity refresh."""
import os
import time
import requests
import pytest

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://review-hub-108.preview.emergentagent.com").rstrip("/")
PID = "city-gate"


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE}/api/auth/login",
                      json={"email": "admin@hotelbox.com", "password": "HotelAdmin2026!"},
                      timeout=30)
    assert r.status_code == 200, r.text
    j = r.json()
    return j.get("access_token") or j.get("token")


@pytest.fixture(scope="module")
def H(token):
    return {"Authorization": f"Bearer {token}"}


# ---- RM Expertise Knowledge ----
def test_knowledge_all(H):
    r = requests.get(f"{BASE}/api/rm-expertise/knowledge", headers=H, timeout=30)
    assert r.status_code == 200
    d = r.json()
    assert d["count"] >= 24, f"expected >=24, got {d['count']}"
    cats = set(d["categories"])
    assert {"pazar", "prensipler", "rakipler", "stratejiler"}.issubset(cats), cats


def test_knowledge_filter_rakipler(H):
    r = requests.get(f"{BASE}/api/rm-expertise/knowledge?category=rakipler", headers=H, timeout=30)
    assert r.status_code == 200
    d = r.json()
    assert d["count"] >= 1
    assert all(it["category"] == "rakipler" for it in d["items"])
    titles = " ".join(it.get("title", "") for it in d["items"]).lower()
    for expected in ("roompricegenie", "ideas", "duetto", "atomize"):
        assert expected in titles, f"missing competitor {expected} in {titles}"


# ---- Sensitivity ----
def test_analyze_sensitivity(H):
    r = requests.post(f"{BASE}/api/rm-expertise/{PID}/analyze-sensitivity", headers=H, timeout=60)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d.get("sample_total", 0) >= 6, d
    buckets = d.get("buckets", [])
    assert len(buckets) >= 1
    keys = {"bucket", "dow_type", "band", "elasticity", "samples", "label", "advice"}
    for b in buckets:
        assert keys.issubset(b.keys()), f"missing keys in bucket {b}"


def test_get_sensitivity(H):
    r = requests.get(f"{BASE}/api/rm-expertise/{PID}/sensitivity", headers=H, timeout=30)
    assert r.status_code == 200
    d = r.json()
    assert d.get("property_id") == PID
    assert len(d.get("buckets", [])) >= 1


# ---- Expert Brief ----
def test_expert_brief_latest_ok(H):
    r = requests.get(f"{BASE}/api/rm-expertise/{PID}/expert-brief/latest", headers=H, timeout=30)
    assert r.status_code == 200
    # content may be None
    d = r.json()
    assert "content" in d or "property_id" in d


# ---- Chat run_optimizer capability (1 LLM call) ----
def test_chat_run_optimizer_and_apply(H):
    r = requests.post(
        f"{BASE}/api/revenue/copilot/{PID}/chat",
        headers=H,
        json={"message": "Optimizer'ı şimdi çalıştır ve fiyatları uygula, onaylıyorum"},
        timeout=120,
    )
    assert r.status_code == 200, r.text
    d = r.json()
    action = d.get("action")
    assert action, f"no action in chat response: {d}"
    assert action.get("type") == "run_optimizer", f"expected run_optimizer, got {action}"
    aid = action.get("id")
    assert aid
    r2 = requests.post(
        f"{BASE}/api/revenue/copilot/{PID}/apply-action/{aid}", headers=H, timeout=120)
    assert r2.status_code == 200, r2.text
    d2 = r2.json()
    detail = (d2.get("detail") or d2.get("message") or "") + str(d2)
    assert "Optimizer" in detail or "optimizer" in detail.lower(), f"detail missing: {d2}"


# ---- Learn cycle refreshes sensitivity ----
def test_learn_refreshes_sensitivity(H):
    # capture prior computed_at
    r0 = requests.get(f"{BASE}/api/rm-expertise/{PID}/sensitivity", headers=H, timeout=30)
    prior = (r0.json() or {}).get("computed_at")

    time.sleep(1.1)
    r = requests.post(f"{BASE}/api/revenue-brain/{PID}/learn", headers=H, timeout=120)
    assert r.status_code == 200, r.text
    d = r.json()
    assert "regional_memory_updated" in d, d

    r2 = requests.get(f"{BASE}/api/rm-expertise/{PID}/sensitivity", headers=H, timeout=30)
    assert r2.status_code == 200
    after = (r2.json() or {}).get("computed_at")
    assert after, "computed_at missing after learn"
    if prior:
        assert after != prior, f"computed_at not refreshed: {prior} == {after}"


# ---- Regression smoke ----
def test_regression_status(H):
    r = requests.get(f"{BASE}/api/revenue-brain/{PID}/status", headers=H, timeout=30)
    assert r.status_code == 200
