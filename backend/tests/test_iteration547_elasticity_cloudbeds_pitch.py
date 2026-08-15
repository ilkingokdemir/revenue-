"""Iteration 547 - Elasticity, Cloudbeds PMS adapter, Event v2, Pitch PDF."""
import os
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'http://localhost:8001').rstrip('/')
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PW = "HotelAdmin2026!"
PROP = "default"


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PW}, timeout=30)
    assert r.status_code == 200, r.text[:300]
    j = r.json()
    tok = j.get("access_token") or j.get("token")
    assert tok
    return tok


@pytest.fixture(scope="module")
def h(token):
    return {"Authorization": f"Bearer {token}"}


# ---- K12 Elasticity ----
def test_elasticity_default(h):
    r = requests.get(f"{BASE_URL}/api/elasticity/{PROP}", headers=h, timeout=60)
    assert r.status_code == 200, r.text[:300]
    j = r.json()
    for k in ["elasticity", "r2", "sample_days", "aggressiveness", "verdict", "computed_at"]:
        assert k in j, f"missing {k}: {j}"
    assert isinstance(j["elasticity"], (int, float))
    assert isinstance(j["aggressiveness"], (int, float))


def test_elasticity_idempotent(h):
    r1 = requests.get(f"{BASE_URL}/api/elasticity/{PROP}", headers=h, timeout=60)
    r2 = requests.get(f"{BASE_URL}/api/elasticity/{PROP}", headers=h, timeout=60)
    assert r1.status_code == 200 and r2.status_code == 200


def test_ai_pricing_has_elasticity_agg(h):
    r = requests.get(
        f"{BASE_URL}/api/revenue/ai-pricing/{PROP}/suggestions?days=4&use_llm=false",
        headers=h, timeout=60)
    assert r.status_code == 200, r.text[:300]
    j = r.json()
    suggs = j.get("suggestions") or j.get("items") or j
    if isinstance(suggs, dict) and "suggestions" in suggs:
        suggs = suggs["suggestions"]
    assert isinstance(suggs, list) and len(suggs) > 0
    s0 = suggs[0]
    assert "elasticity_aggressiveness" in s0, f"missing elasticity_aggressiveness: {list(s0.keys())}"
    # regression fields
    for k in ["bid_price", "restrictions", "confidence", "waterfall"]:
        assert k in s0, f"missing regression field {k}"
    # If agg != 1.0, evidence should mention "Esneklik ayarı"
    agg = s0["elasticity_aggressiveness"]
    if isinstance(agg, (int, float)) and abs(agg - 1.0) > 0.001:
        ev_text = " ".join(str(e) for s in suggs for e in (s.get("evidence") or []))
        assert "Esneklik" in ev_text, f"expected 'Esneklik ayarı' in evidence when agg={agg}"


# ---- K14 Cloudbeds ----
def test_cloudbeds_status_mocked(h):
    r = requests.get(f"{BASE_URL}/api/cloudbeds/status/{PROP}", headers=h, timeout=30)
    assert r.status_code == 200, r.text[:300]
    j = r.json()
    assert j.get("mode") == "mocked", f"expected mocked, got {j}"
    assert "note" in j


def test_cloudbeds_config(h):
    r = requests.post(f"{BASE_URL}/api/cloudbeds/config/{PROP}", headers=h,
                      json={"cb_property_id": "x", "rate_id": "RMS-RATE"}, timeout=30)
    assert r.status_code == 200, r.text[:300]
    j = r.json()
    assert j.get("ok") is True


def test_cloudbeds_push_from_rms(h):
    r = requests.post(f"{BASE_URL}/api/cloudbeds/push-from-rms/{PROP}", headers=h,
                      json={"days": 5}, timeout=60)
    assert r.status_code == 200, r.text[:300]
    j = r.json()
    assert j.get("mocked") is True
    assert j.get("pushed_days", 0) > 0, f"expected pushed_days>0: {j}"
    # sample intervals
    sample = j.get("sample") or j.get("intervals") or j.get("samples")
    assert sample is not None, f"no sample field: {list(j.keys())}"


def test_cloudbeds_pull_reservations(h):
    r = requests.post(f"{BASE_URL}/api/cloudbeds/pull-reservations/{PROP}",
                      headers=h, json={}, timeout=30)
    assert r.status_code == 200, r.text[:300]
    j = r.json()
    assert j.get("mocked") is True


def test_cloudbeds_test_connection_without_key(h):
    r = requests.post(f"{BASE_URL}/api/cloudbeds/test-connection/{PROP}",
                      headers=h, json={}, timeout=30)
    assert r.status_code == 400, f"expected 400 without api_key, got {r.status_code} {r.text[:200]}"


def test_cloudbeds_log(h):
    r = requests.get(f"{BASE_URL}/api/cloudbeds/log/{PROP}", headers=h, timeout=30)
    assert r.status_code == 200, r.text[:300]
    j = r.json()
    # accept list or {"rows":[...]}
    rows = j if isinstance(j, list) else (j.get("rows") or j.get("items") or [])
    assert isinstance(rows, list)


# ---- Event Signal v2 ----
def test_public_event_venue_distance_crud(h):
    payload = {
        "title": "TEST_Event_v2",
        "property_id": PROP,
        "date": "2026-06-15",
        "venue_name": "Arena",
        "distance_km": 3.5,
        "capacity": 4000,
    }
    r = requests.post(f"{BASE_URL}/api/public-events", headers=h, json=payload, timeout=30)
    assert r.status_code in (200, 201), r.text[:300]
    j = r.json()
    ev_id = j.get("id") or j.get("_id") or j.get("event_id")
    assert ev_id, f"no id in {j}"
    # verify persisted fields
    assert j.get("venue_name") == "Arena" or j.get("venue") == "Arena", f"venue_name not persisted: {j}"
    assert j.get("distance_km") == 3.5, f"distance_km not persisted: {j}"

    # PATCH distance_km
    pr = requests.patch(f"{BASE_URL}/api/public-events/{ev_id}", headers=h,
                        json={"distance_km": 5.0}, timeout=30)
    assert pr.status_code == 200, pr.text[:300]
    pj = pr.json()
    assert pj.get("distance_km") == 5.0 or pj.get("ok") is True, f"patch failed: {pj}"

    # DELETE
    dr = requests.delete(f"{BASE_URL}/api/public-events/{ev_id}", headers=h, timeout=30)
    assert dr.status_code in (200, 204), dr.text[:300]


# ---- Pilot Pitch Mode ----
def test_branding_set_and_get(h):
    r = requests.post(f"{BASE_URL}/api/simulator/{PROP}/branding", headers=h,
                      json={"logo_url": "https://dummyimage.com/200x100/000/fff.png"},
                      timeout=30)
    assert r.status_code == 200, r.text[:300]
    j = r.json()
    assert j.get("ok") is True or "logo_url" in j

    gr = requests.get(f"{BASE_URL}/api/simulator/{PROP}/branding", headers=h, timeout=30)
    assert gr.status_code == 200
    gj = gr.json()
    assert "dummyimage.com" in (gj.get("logo_url") or ""), f"branding not persisted: {gj}"


def test_pitch_pdf(h):
    r = requests.get(f"{BASE_URL}/api/simulator/{PROP}/pitch-pdf?days=7&base_rate=100",
                     headers=h, timeout=90)
    assert r.status_code == 200, r.text[:300]
    ct = r.headers.get("content-type", "")
    assert "application/pdf" in ct, f"ct={ct}"
    assert r.content[:4] == b"%PDF", f"bad magic: {r.content[:8]!r}"


# ---- Regression ----
def test_simulator_run(h):
    r = requests.get(f"{BASE_URL}/api/simulator/{PROP}/run?days=7&base_rate=100",
                     headers=h, timeout=60)
    # Some sims are POST; try POST fallback
    if r.status_code == 405:
        r = requests.post(f"{BASE_URL}/api/simulator/{PROP}/run",
                          headers=h, json={"days": 7, "base_rate": 100}, timeout=60)
    assert r.status_code == 200, r.text[:300]


def test_simulator_bid_price(h):
    r = requests.get(f"{BASE_URL}/api/simulator/{PROP}/bid-price?days=7",
                     headers=h, timeout=30)
    assert r.status_code == 200, r.text[:300]
    j = r.json()
    assert "rows" in j and len(j["rows"]) > 0


def test_hotelrunner_certify(h):
    r = requests.post(f"{BASE_URL}/api/hotelrunner/certify/{PROP}", headers=h, timeout=30)
    assert r.status_code == 200, r.text[:300]
    assert r.json().get("passed") is True


def test_hotelrunner_status(h):
    r = requests.get(f"{BASE_URL}/api/hotelrunner/status/{PROP}", headers=h, timeout=30)
    assert r.status_code == 200, r.text[:300]
    assert "certification" in r.json()
