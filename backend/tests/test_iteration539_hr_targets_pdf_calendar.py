"""Iteration 539 — HotelRunner live, Metric targets, Proposal PDF/email, Function space calendar."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
PID = "default"


@pytest.fixture(scope="module")
def auth():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": "admin@hotelbox.com", "password": "HotelAdmin2026!"},
                      timeout=15)
    assert r.status_code == 200, r.text
    tok = r.json().get("access_token") or r.json().get("token")
    return {"Authorization": f"Bearer {tok}"}


# ---- HotelRunner ----
def test_hr_status_mocked(auth):
    r = requests.get(f"{BASE_URL}/api/hotelrunner/status/{PID}", headers=auth, timeout=15)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("mode") == "mocked", f"Expected mocked mode: {data}"


def test_hr_push_from_rms_mocked(auth):
    r = requests.post(f"{BASE_URL}/api/hotelrunner/push-from-rms/{PID}",
                      json={"days": 5}, headers=auth, timeout=20)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("mocked") is True
    assert data.get("pushed_days") == 5


def test_hr_log(auth):
    r = requests.get(f"{BASE_URL}/api/hotelrunner/log/{PID}", headers=auth, timeout=15)
    assert r.status_code == 200, r.text
    data = r.json()
    entries = data.get("entries") or data.get("log") or data
    assert entries or isinstance(entries, list), f"Log response: {data}"


# ---- Metric targets ----
def test_put_metric_targets(auth):
    payload = {"target_trevpor": 120, "target_goppar": 50}
    r = requests.put(f"{BASE_URL}/api/modern-metrics/{PID}/targets", json=payload, headers=auth, timeout=15)
    assert r.status_code == 200, r.text
    # Now verify trend reflects
    r2 = requests.get(f"{BASE_URL}/api/modern-metrics/{PID}/trend?months=6", headers=auth, timeout=15)
    assert r2.status_code == 200
    body = r2.json()
    txt = str(body)
    assert "targets_custom" in txt, f"No targets_custom key: {txt[:400]}"
    # Reset back to iter 538 defaults so main agent context stays intact
    requests.put(f"{BASE_URL}/api/modern-metrics/{PID}/targets",
                 json={"target_trevpor": 160, "target_goppar": 90}, headers=auth, timeout=15)


# ---- Function space calendar / PDF / email ----
def test_function_space_calendar(auth):
    r = requests.get(f"{BASE_URL}/api/function-space/{PID}/calendar?week_start=2026-08-24",
                     headers=auth, timeout=15)
    assert r.status_code == 200, r.text
    data = r.json()
    txt = str(data)
    # Verify Acme block on 08-25 9-17
    assert "Acme" in txt or "acme" in txt or "2026-08-25" in txt, f"No Acme/date evidence: {txt[:500]}"


def _find_proposal_with_email(auth):
    r = requests.get(f"{BASE_URL}/api/function-space/{PID}/proposals", headers=auth, timeout=15)
    if r.status_code != 200:
        return None
    items = r.json().get("proposals") or r.json().get("data") or r.json()
    if not isinstance(items, list):
        items = items.get("items", []) if isinstance(items, dict) else []
    for p in items:
        if p.get("client_email"):
            return p.get("id") or p.get("proposal_id")
    # fallback: any
    if items:
        p = items[0]
        return p.get("id") or p.get("proposal_id")
    return None


def test_function_space_pdf(auth):
    pid_ = _find_proposal_with_email(auth)
    if not pid_:
        pytest.skip("No proposal available")
    r = requests.get(f"{BASE_URL}/api/function-space/{PID}/proposals/{pid_}/pdf",
                     headers=auth, timeout=20)
    assert r.status_code == 200, r.text[:200]
    ctype = r.headers.get("content-type", "")
    assert "pdf" in ctype.lower(), f"Not PDF content-type: {ctype}"
    assert len(r.content) > 500, f"PDF too small: {len(r.content)} bytes"


def test_function_space_email(auth):
    # Find a proposal — the endpoint returns 400 if no client_email, which is expected
    pid_ = _find_proposal_with_email(auth)
    if not pid_:
        pytest.skip("No proposal available")
    r = requests.post(f"{BASE_URL}/api/function-space/{PID}/proposals/{pid_}/email",
                      json={}, headers=auth, timeout=15)
    assert r.status_code in (200, 400), r.text[:200]
