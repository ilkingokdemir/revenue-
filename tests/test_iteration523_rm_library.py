"""Iteration 523: RM knowledge library (deep 25-entry seed) backend tests."""
import os
import requests
import pytest

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://review-hub-108.preview.emergentagent.com").rstrip("/")
PID = "city-gate"

EXPECTED_CATEGORIES = {
    "derin_stratejiler",
    "egitim",
    "teknik_modeller",
    "vaka_calismalari",
    "yazilim_prensipleri",
}


@pytest.fixture(scope="module")
def H():
    r = requests.post(f"{BASE}/api/auth/login",
                      json={"email": "admin@hotelbox.com", "password": "HotelAdmin2026!"},
                      timeout=30)
    assert r.status_code == 200, r.text
    tok = r.json().get("access_token") or r.json().get("token")
    return {"Authorization": f"Bearer {tok}"}


def test_library_total_and_categories(H):
    r = requests.get(f"{BASE}/api/rm-expertise/library", headers=H, timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    total = d.get("total") if "total" in d else d.get("count")
    assert total == 25, f"expected total=25, got {total} :: {d}"
    cats = set(d.get("categories") or [])
    assert EXPECTED_CATEGORIES.issubset(cats), f"missing categories, got {cats}"
    items = d.get("items") or []
    assert len(items) == 25
    sample = items[0]
    for k in ("id", "category", "title", "tags", "body"):
        assert k in sample, f"item missing key {k}: {sample}"


def test_library_search_overbooking(H):
    r = requests.get(f"{BASE}/api/rm-expertise/library", params={"q": "overbooking"}, headers=H, timeout=30)
    assert r.status_code == 200
    items = r.json().get("items") or []
    assert len(items) >= 1
    titles = " | ".join(it.get("title", "") for it in items).lower()
    assert "overbooking" in titles or "newsvendor" in titles, f"titles: {titles}"


def test_library_search_ihg(H):
    r = requests.get(f"{BASE}/api/rm-expertise/library", params={"q": "IHG"}, headers=H, timeout=30)
    assert r.status_code == 200
    items = r.json().get("items") or []
    assert len(items) >= 1
    hay = " | ".join((it.get("title", "") + " " + it.get("body", "")) for it in items).lower()
    assert "ihg" in hay, f"IHG not found in results: {hay[:400]}"


def test_library_filter_yazilim_prensipleri(H):
    r = requests.get(f"{BASE}/api/rm-expertise/library",
                     params={"category": "yazilim_prensipleri"}, headers=H, timeout=30)
    assert r.status_code == 200
    items = r.json().get("items") or []
    assert len(items) == 5, f"expected 5 in yazilim_prensipleri, got {len(items)}"
    assert all(it.get("category") == "yazilim_prensipleri" for it in items)
    titles = " | ".join(it.get("title", "") for it in items).lower()
    for kw in ("ideas", "duetto", "atomize"):
        assert kw in titles, f"missing {kw} in {titles}"


def test_library_idempotent(H):
    r1 = requests.get(f"{BASE}/api/rm-expertise/library", headers=H, timeout=30)
    r2 = requests.get(f"{BASE}/api/rm-expertise/library", headers=H, timeout=30)
    t1 = r1.json().get("total") or r1.json().get("count")
    t2 = r2.json().get("total") or r2.json().get("count")
    assert t1 == t2 == 25


def test_chat_knowledge_injection_booking_curve(H):
    """1 LLM call: Turkish expert must reference booking curve / pickup / MAPE."""
    r = requests.post(
        f"{BASE}/api/revenue/copilot/{PID}/chat",
        headers=H,
        json={"message": "Rezervasyon eğrisi ve pickup tahmini nasıl çalışır, MAPE hedefi ne olmalı?"},
        timeout=180,
    )
    assert r.status_code == 200, r.text
    d = r.json()
    resp = (d.get("response") or d.get("message") or "").lower()
    assert len(resp) > 50, f"empty/short response: {d}"
    # At least one of the core concepts should be present
    hits = sum(1 for kw in ("pickup", "mape", "eğri", "egri", "booking curve", "rezervasyon eğrisi") if kw in resp)
    assert hits >= 1, f"no knowledge concepts referenced in response: {resp[:500]}"
