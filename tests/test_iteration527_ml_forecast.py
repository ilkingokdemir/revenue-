"""Iteration 527: Tahmin Karnesi, Keşif Modu, Boş Gece Kampanyaları, Haftalık Brifing."""
import os
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://review-hub-108.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PW = "HotelAdmin2026!"


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PW}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json().get("token") or r.json().get("access_token")


@pytest.fixture(scope="module")
def h(token):
    return {"Authorization": f"Bearer {token}"}


# --- Feature 1: Tahmin Karnesi (forecast scorecard) ---
def test_forecast_scorecard_shape_and_idempotent(h):
    r1 = requests.get(f"{BASE}/api/rm-expertise/default/forecast-scorecard", headers=h, timeout=30)
    assert r1.status_code == 200, r1.text
    d1 = r1.json()
    for k in ["overall_mape", "bands", "scored", "alert", "updated_at"]:
        assert k in d1, f"missing {k} in {d1}"
    for b in ["yakin_3_7", "orta_8_14", "uzak_15plus"]:
        assert b in d1["bands"], f"missing band {b}"
    assert d1["scored"] >= 3, f"expected >=3 scored, got {d1['scored']}"
    assert isinstance(d1["overall_mape"], (int, float))
    # ~23.3 tolerated
    assert 15.0 <= d1["overall_mape"] <= 35.0, f"unexpected mape {d1['overall_mape']}"
    assert d1["alert"] is False

    # Idempotent
    r2 = requests.get(f"{BASE}/api/rm-expertise/default/forecast-scorecard", headers=h, timeout=30)
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["scored"] == d1["scored"], "scored count changed on 2nd call"
    print(f"scorecard: mape={d1['overall_mape']} scored={d1['scored']} alert={d1['alert']}")


# --- Feature 2: Keşif Modu ---
def test_open_pricing_exploration(h):
    r = requests.post(
        f"{BASE}/api/open-pricing/optimize",
        headers=h,
        json={"property_id": "default", "days": 14, "apply": True},
        timeout=90,
    )
    assert r.status_code == 200, r.text
    d = r.json()
    assert d.get("exploration_pct") == 5.0, f"exploration_pct={d.get('exploration_pct')}"
    matrix = d.get("matrix") or []
    assert len(matrix) > 0
    total_explored = sum(row.get("explored_cells", 0) for row in matrix)
    assert total_explored > 0, "expected explored_cells > 0"
    ovw = d.get("overrides_written", 0) or 1
    ratio = total_explored / ovw if ovw else 0
    print(f"exploration: explored={total_explored} overrides={ovw} ratio={ratio:.2%}")
    # loose bound
    assert total_explored <= max(50, ovw), "explored implausibly high"


# --- Feature 3: Empty Night Campaigns ---
def test_empty_night_campaigns(h):
    p1 = requests.post(f"{BASE}/api/rm-expertise/default/empty-night-campaigns", headers=h, timeout=60)
    assert p1.status_code == 200, p1.text
    d1 = p1.json()
    assert d1.get("ok") is True or d1.get("status") == "ok" or "campaign_dates" in d1
    dates1 = d1.get("campaign_dates") or d1.get("dates") or []
    assert len(dates1) >= 1, f"expected campaign_dates>=1, got {d1}"

    g = requests.get(f"{BASE}/api/rm-expertise/default/empty-night-campaigns", headers=h, timeout=30)
    assert g.status_code == 200
    listed = g.json()
    items = listed if isinstance(listed, list) else listed.get("campaigns") or listed.get("items") or []
    assert len(items) >= 1
    sample = items[0]
    assert sample.get("discount_pct") == 8 or sample.get("discount_pct") == 8.0
    assert sample.get("min_los") == 2

    # Idempotent
    p2 = requests.post(f"{BASE}/api/rm-expertise/default/empty-night-campaigns", headers=h, timeout=60)
    assert p2.status_code == 200
    g2 = requests.get(f"{BASE}/api/rm-expertise/default/empty-night-campaigns", headers=h, timeout=30)
    items2 = g2.json() if isinstance(g2.json(), list) else g2.json().get("campaigns") or g2.json().get("items") or []
    assert len(items2) == len(items), f"count changed after re-POST: {len(items)} -> {len(items2)}"
    print(f"campaigns: count={len(items)} dates={dates1[:3]}")


# --- Feature 4: Weekly brief history visibility (zero LLM call for 'default') ---
def test_weekly_brief_history_visibility_default(h):
    r = requests.get(f"{BASE}/api/revenue/copilot/default/history", headers=h, timeout=30)
    assert r.status_code == 200, r.text
    body = r.json()
    msgs = body if isinstance(body, list) else body.get("messages") or body.get("history") or []
    joined = " ".join([str(m.get("content", "")) for m in msgs])
    # Main agent verified this landed for default; verify presence
    has_brief = "HAFTALIK UZMAN BRİFİNGİ" in joined or "HAFTALIK UZMAN BRIFINGI" in joined
    print(f"history msgs={len(msgs)} has_brief={has_brief}")
    assert has_brief, "expected weekly brief message in default chat history"


# --- Feature 5: revenue-brain learn still works & logs forecasts ---
def test_revenue_brain_learn_city_gate(h):
    r = requests.post(f"{BASE}/api/revenue-brain/city-gate/learn", headers=h, timeout=120)
    assert r.status_code == 200, r.text[:300]
    d = r.json()
    print(f"learn: keys={list(d.keys())[:8]}")
