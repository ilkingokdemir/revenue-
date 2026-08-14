"""Iteration 525-526: RM Library (45 entries incl veri_muhendisligi), ML Pickup, Internalize spillage, chat."""
import os
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://review-hub-108.preview.emergentagent.com").rstrip("/")
API = f"{BASE}/api"
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PW = "HotelAdmin2026!"


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PW}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def H(token):
    return {"Authorization": f"Bearer {token}"}


# --- Library ---
def test_library_total_45_and_categories(H):
    r = requests.get(f"{API}/rm-expertise/library", headers=H, timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["total"] == 45, f"total={d['total']}"
    assert "veri_muhendisligi" in d["categories"], d["categories"]
    assert len(d["categories"]) >= 6


def test_library_search_endojenite(H):
    r = requests.get(f"{API}/rm-expertise/library", headers=H, params={"q": "endojenite"}, timeout=30)
    assert r.status_code == 200
    titles = " | ".join(i.get("title", "") for i in r.json()["items"])
    assert "Endojenite" in titles, titles


def test_library_search_lightgbm(H):
    r = requests.get(f"{API}/rm-expertise/library", headers=H, params={"q": "lightgbm"}, timeout=30)
    assert r.status_code == 200
    titles = " | ".join(i.get("title", "") for i in r.json()["items"]).lower()
    assert "lightgbm" in titles, titles


def test_library_veri_muhendisligi_10(H):
    r = requests.get(f"{API}/rm-expertise/library", headers=H, params={"category": "veri_muhendisligi"}, timeout=30)
    assert r.status_code == 200
    d = r.json()
    assert d["count"] == 10, f"count={d['count']}"
    for it in d["items"]:
        assert it["category"] == "veri_muhendisligi"


# --- ML Pickup ---
def test_ml_pickup_default(H):
    r = requests.get(f"{API}/rm-expertise/default/ml-pickup", headers=H, params={"days": 24}, timeout=60)
    assert r.status_code == 200, r.text
    d = r.json()
    for k in ("capacity", "days", "empty_risk_dates", "hot_dates", "model", "note"):
        assert k in d, f"missing {k}"
    assert d["days"], "days empty"
    days_out_first = d["days"][0]["days_out"]
    assert days_out_first == 3, days_out_first
    rooms_vals = {r["ml_final_rooms"] for r in d["days"]}
    assert len(rooms_vals) > 1, f"ml_final_rooms constant: {rooms_vals}"
    for row in d["days"]:
        assert row["ml_final_rooms"] >= row["otb"] * 0.85 - 0.05, row
        for k in ("date", "days_out", "otb", "pickup_last7", "ml_final_rooms",
                 "ml_final_occ_pct", "naive_final_rooms", "risk"):
            assert k in row, f"missing {k} in row"
    occs = [r["ml_final_occ_pct"] for r in d["days"]]
    assert len(set(occs)) > 1
    # some low occ flagged bos_gece
    low = [r for r in d["days"] if r["ml_final_occ_pct"] < 50]
    if low:
        assert any(r["risk"] == "bos_gece" for r in low)


def test_ml_pickup_city_gate(H):
    r = requests.get(f"{API}/rm-expertise/city-gate/ml-pickup", headers=H, params={"days": 10}, timeout=60)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["capacity"] == 20, d["capacity"]
    assert d["days"]


# --- Internalize ---
def test_internalize_returns_6_or_7_rules(H):
    r = requests.post(f"{API}/rm-expertise/default/internalize", headers=H, timeout=60)
    assert r.status_code == 200, r.text
    d = r.json()
    assert 6 <= d["rules_count"] <= 7, f"rules_count={d['rules_count']}"
    ids = [rl.get("source_id") for rl in d["rules"]]
    # If spillage/spoilage days exist, edu_spillage_spoilage must be present
    # Otherwise, 6 rules acceptable.
    if d["rules_count"] == 7:
        assert "edu_spillage_spoilage" in ids, ids


# --- Chat (max 1 call) ---
def test_chat_risk_dates_reference(H):
    payload = {"message": "Önümüzdeki 2 haftada boş kalma riski olan geceler hangileri, ne yapalım?"}
    r = requests.post(f"{API}/revenue/copilot/default/chat", headers=H, json=payload, timeout=120)
    assert r.status_code == 200, r.text
    d = r.json()
    reply = (d.get("response") or d.get("reply") or d.get("content") or d.get("answer") or "").lower()
    assert reply, f"empty reply: {d}"
    assert "kaynak" not in reply
    assert "kütüphane" not in reply


# --- Regression ---
def test_city_gate_learn_regression(H):
    r = requests.post(f"{API}/revenue-brain/city-gate/learn", headers=H, timeout=60)
    assert r.status_code == 200, r.text
