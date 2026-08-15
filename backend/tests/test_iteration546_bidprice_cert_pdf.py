"""Iteration 546 - Bid-Price Network, Publisher Certification, Simulator PDF."""
import os
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'http://localhost:8001').rstrip('/')
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PW = "HotelAdmin2026!"
PROP = "default"


@pytest.fixture(scope="module")
def token():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": ADMIN_EMAIL, "password": ADMIN_PW}, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    j = r.json()
    tok = j.get("access_token") or j.get("token")
    assert tok, f"no token in {j}"
    return tok


@pytest.fixture(scope="module")
def h(token):
    return {"Authorization": f"Bearer {token}"}


# ---- Auth basic ----
def test_login_returns_token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PW}, timeout=30)
    assert r.status_code == 200
    j = r.json()
    assert j.get("access_token") or j.get("token")


# ---- Simulator bid-price ----
def test_bid_price_endpoint(h):
    r = requests.get(f"{BASE_URL}/api/simulator/{PROP}/bid-price?days=14",
                     headers=h, timeout=30)
    assert r.status_code == 200, r.text[:300]
    j = r.json()
    assert "ref_adr" in j
    assert "rows" in j and isinstance(j["rows"], list) and len(j["rows"]) > 0
    row = j["rows"][0]
    for k in ["date", "net_occupancy_pct", "bid_price", "min_los", "cta", "ctd", "reason"]:
        assert k in row, f"missing {k} in row: {row}"


# ---- AI pricing suggestions with bid fields ----
def test_ai_pricing_bid_fields(h):
    r = requests.get(
        f"{BASE_URL}/api/revenue/ai-pricing/{PROP}/suggestions?days=5&use_llm=false",
        headers=h, timeout=60)
    assert r.status_code == 200, r.text[:300]
    j = r.json()
    suggs = j.get("suggestions") or j.get("items") or j
    if isinstance(suggs, dict) and "suggestions" in suggs:
        suggs = suggs["suggestions"]
    assert isinstance(suggs, list) and len(suggs) > 0, f"no suggestions: {j}"
    s0 = suggs[0]
    # regression fields
    for k in ["confidence", "evidence", "waterfall", "net_new_rate"]:
        assert k in s0, f"missing regression field {k}"
    # new bid-price fields
    assert "bid_price" in s0 and isinstance(s0["bid_price"], (int, float))
    assert "bid_floor_applied" in s0 and isinstance(s0["bid_floor_applied"], bool)
    assert "restrictions" in s0 and isinstance(s0["restrictions"], dict)
    for rk in ["min_los", "cta", "ctd"]:
        assert rk in s0["restrictions"], f"missing restriction {rk}"
    # invariant: if bid_floor_applied then suggested_rate >= bid_price
    for s in suggs:
        if s.get("bid_floor_applied"):
            sr = s.get("suggested_rate") or s.get("net_new_rate")
            assert sr >= s["bid_price"] - 0.01, f"floor violated: {sr} < {s['bid_price']}"


# ---- HotelRunner certify ----
def test_hotelrunner_certify(h):
    r = requests.post(f"{BASE_URL}/api/hotelrunner/certify/{PROP}",
                      headers=h, timeout=30)
    assert r.status_code == 200, r.text[:300]
    j = r.json()
    assert "checks" in j and isinstance(j["checks"], list) and len(j["checks"]) >= 3
    labels = " ".join([str(c) for c in j["checks"]])
    assert "Kimlik" in labels or "kimlik" in labels.lower()
    assert "Test push" in labels or "test push" in labels.lower()
    assert "Geri okuma" in labels or "geri okuma" in labels.lower()
    assert j.get("passed") is True


def test_hotelrunner_status_has_certification(h):
    r = requests.get(f"{BASE_URL}/api/hotelrunner/status/{PROP}",
                     headers=h, timeout=30)
    assert r.status_code == 200, r.text[:300]
    j = r.json()
    assert "certification" in j


def test_hotelrunner_mock_push_not_blocked(h):
    r = requests.post(f"{BASE_URL}/api/hotelrunner/push-from-rms/{PROP}",
                      headers=h, json={"days": 3}, timeout=30)
    assert r.status_code == 200, r.text[:300]
    j = r.json()
    assert j.get("mocked") is True, f"expected mocked:true, got {j}"


# ---- Simulator PDF ----
def test_simulator_report_pdf(h):
    r = requests.get(
        f"{BASE_URL}/api/simulator/{PROP}/report-pdf?days=7&base_rate=100",
        headers=h, timeout=60)
    assert r.status_code == 200, r.text[:300]
    ct = r.headers.get("content-type", "")
    assert "application/pdf" in ct, f"ct={ct}"
    assert r.content[:4] == b"%PDF"
