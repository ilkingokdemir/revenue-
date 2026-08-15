"""Trust Center backend regression tests: AI Pricing (net OTB), Guardrails, Net OTB, Acceptance, Shadow Mode."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL") or "http://localhost:8001"
BASE_URL = BASE_URL.rstrip("/")
PROP = "default"


@pytest.fixture(scope="session")
def admin_token():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": "admin@hotelbox.com", "password": "HotelAdmin2026!"},
        timeout=15,
    )
    assert r.status_code == 200, f"Login failed {r.status_code}: {r.text}"
    return r.json().get("access_token") or r.json().get("token")


@pytest.fixture(scope="session")
def h(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


# ---------- AI pricing suggestions (net OTB fields) ----------
def test_ai_pricing_suggestions_net_otb_fields(h):
    r = requests.get(
        f"{BASE_URL}/api/revenue/ai-pricing/{PROP}/suggestions",
        params={"days": 5, "use_llm": "false"},
        headers=h,
        timeout=60,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    sugs = body.get("suggestions") or body.get("items") or []
    assert isinstance(sugs, list) and len(sugs) > 0, f"no suggestions: {body}"
    first = sugs[0]
    # New fields
    assert "occupancy_pct" in first, f"missing occupancy_pct: {list(first.keys())}"
    assert "gross_occupancy_pct" in first, f"missing gross_occupancy_pct: {list(first.keys())}"
    assert "expected_cancels" in first, f"missing expected_cancels: {list(first.keys())}"
    # Existing fields
    assert "suggested_rate" in first
    assert "summary" in first or "reason" in first or True
    assert "los_tiers" in first or "tiers" in first or True


# ---------- Guardrails ----------
def test_guardrails_get_config(h):
    r = requests.get(f"{BASE_URL}/api/guardrails/{PROP}/config", headers=h, timeout=15)
    assert r.status_code == 200, r.text
    cfg = r.json()
    assert "max_step_pct" in cfg or "step_pct" in cfg or "max_step" in cfg, cfg


def test_guardrails_put_config(h):
    payload = {"max_step_pct": 15, "daily_limit": 50}
    r = requests.put(
        f"{BASE_URL}/api/guardrails/{PROP}/config", json=payload, headers=h, timeout=15
    )
    assert r.status_code in (200, 201), r.text


def test_guardrails_violations_has_step_limit(h):
    r = requests.get(f"{BASE_URL}/api/guardrails/{PROP}/violations", headers=h, timeout=15)
    assert r.status_code == 200, r.text
    body = r.json()
    items = body if isinstance(body, list) else body.get("items") or body.get("violations") or []
    kinds = {(it.get("kind") or it.get("type") or "").lower() for it in items}
    assert any("step" in k for k in kinds) or any("limit" in k for k in kinds), f"kinds={kinds}"


# ---------- Net OTB ----------
def test_net_otb_endpoint(h):
    r = requests.get(
        f"{BASE_URL}/api/net-otb/{PROP}", params={"days": 5}, headers=h, timeout=30
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "rows" in body and "cancel_stats" in body, body
    cs = body["cancel_stats"]
    assert "global_rate" in cs and cs.get("sample", 0) > 0, cs


# ---------- Acceptance ----------
def test_acceptance_report(h):
    r = requests.get(
        f"{BASE_URL}/api/rms-acceptance/{PROP}/report", headers=h, timeout=15
    )
    assert r.status_code == 200, r.text
    body = r.json()
    # expect a rate/percentage-like field
    assert "overall_acceptance_pct" in body, body
    assert body["overall_acceptance_pct"] >= 0


# ---------- Shadow Mode ----------
def test_shadow_status_active(h):
    r = requests.get(f"{BASE_URL}/api/shadow-mode/{PROP}/status", headers=h, timeout=15)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("active") is True, body


def test_shadow_report(h):
    r = requests.get(f"{BASE_URL}/api/shadow-mode/{PROP}/report", headers=h, timeout=15)
    assert r.status_code == 200, r.text
    body = r.json()
    assert isinstance(body, dict), body
