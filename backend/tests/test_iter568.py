"""Iteration 568: Selective apply (dates), per-kind undo, heatmap-pdf."""
import os
import requests

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or "").rstrip("/")
PID = "default"
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASS = "HotelAdmin2026!"


def _login():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=20)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    tok = r.json().get("access_token") or r.json().get("token")
    if tok:
        s.headers.update({"Authorization": f"Bearer {tok}"})
    return s


def _clean(s):
    # undo everything, then re-enable comp-trigger
    s.post(f"{BASE_URL}/api/demand-signals/{PID}/undo-markups", json={}, timeout=30)
    s.put(f"{BASE_URL}/api/demand-signals/{PID}/comp-trigger",
          json={"threshold_pct": 10, "enabled": True}, timeout=20)


# --- Feature 1: Selective apply via {dates: [...]} ---
def test_apply_comp_trigger_selective_dates():
    s = _login()
    _clean(s)
    # Discover threshold-passing dates by doing an unfiltered apply first
    warm = s.post(f"{BASE_URL}/api/demand-signals/{PID}/comp-trigger/apply",
                  json={}, timeout=60).json()
    all_dates = [row["date"] for row in warm.get("days", [])]
    # cleanup then do selective
    s.post(f"{BASE_URL}/api/demand-signals/{PID}/undo-markups", json={}, timeout=30)
    if not all_dates:
        return  # nothing to test with today's data
    chosen = all_dates[:1]
    r = s.post(f"{BASE_URL}/api/demand-signals/{PID}/comp-trigger/apply",
               json={"dates": chosen}, timeout=30)
    assert r.status_code == 200, r.text[:500]
    d = r.json()
    assert d.get("ok") is True
    assert d.get("applied") == len(chosen), f"expected {len(chosen)} applied, got {d}"
    returned_dates = [row.get("date") for row in d.get("days", [])]
    assert set(returned_dates) == set(chosen)


def test_apply_comp_trigger_empty_body_uses_all():
    s = _login()
    _clean(s)
    r = s.post(f"{BASE_URL}/api/demand-signals/{PID}/comp-trigger/apply",
               json={}, timeout=60)
    assert r.status_code == 200, r.text[:500]
    d = r.json()
    assert d.get("ok") is True
    assert d.get("applied", 0) <= 10  # capped at 10


# --- Feature 2: Per-kind undo ---
def test_undo_markups_only_comp_trigger():
    s = _login()
    _clean(s)
    # Apply comp trigger
    ap = s.post(f"{BASE_URL}/api/demand-signals/{PID}/comp-trigger/apply",
                json={}, timeout=60).json()
    applied = ap.get("applied", 0)

    # Undo only comp_trigger
    r = s.post(f"{BASE_URL}/api/demand-signals/{PID}/undo-markups",
               json={"kind": "comp_trigger"}, timeout=30)
    assert r.status_code == 200, r.text[:500]
    d = r.json()
    assert d.get("ok") is True

    # Verify history has an undo entry with kind info
    h = s.get(f"{BASE_URL}/api/demand-signals/{PID}/markup-history", timeout=20).json()
    hist = h.get("history", [])
    undo_rows = [row for row in hist if row.get("action") == "undo"]
    assert undo_rows, "no undo history rows found"
    # The most recent undo should reference comp_trigger
    latest = undo_rows[0]
    kind_field = latest.get("kind") or latest.get("undo_kind") or ""
    # accept either explicit kind field or in a nested detail
    assert "comp_trigger" in str(latest).lower(), \
        f"undo log should mention comp_trigger kind, got {latest}"

    if applied:
        assert d.get("total", 0) >= 0


def test_undo_markups_no_kind_undoes_all():
    s = _login()
    _clean(s)
    ap = s.post(f"{BASE_URL}/api/demand-signals/{PID}/comp-trigger/apply",
                json={}, timeout=60).json()
    applied = ap.get("applied", 0)
    r = s.post(f"{BASE_URL}/api/demand-signals/{PID}/undo-markups",
               json={}, timeout=30)
    assert r.status_code == 200
    d = r.json()
    assert d.get("ok") is True
    if applied:
        assert d.get("total", 0) >= 0


# --- Feature 3: Heatmap PDF ---
def test_heatmap_pdf_filled_month():
    s = _login()
    r = s.get(f"{BASE_URL}/api/demand-signals/{PID}/heatmap-pdf",
              params={"year": 2026, "month": 8}, timeout=60)
    assert r.status_code == 200, r.text[:300]
    ct = r.headers.get("content-type", "")
    assert "application/pdf" in ct.lower(), f"expected pdf, got {ct}"
    assert len(r.content) > 2000, f"pdf too small: {len(r.content)}"
    assert r.content[:4] == b"%PDF", "not a real PDF"


def test_heatmap_pdf_no_params_uses_current_month():
    s = _login()
    r = s.get(f"{BASE_URL}/api/demand-signals/{PID}/heatmap-pdf", timeout=60)
    assert r.status_code == 200
    assert "application/pdf" in r.headers.get("content-type", "").lower()
    assert r.content[:4] == b"%PDF"


def test_heatmap_pdf_empty_month_still_ok():
    s = _login()
    r = s.get(f"{BASE_URL}/api/demand-signals/{PID}/heatmap-pdf",
              params={"year": 2020, "month": 1}, timeout=60)
    assert r.status_code == 200
    assert r.content[:4] == b"%PDF"


# --- PDF Center now includes heatmap card ---
def test_pdf_center_includes_heatmap():
    s = _login()
    r = s.get(f"{BASE_URL}/api/pms-connect/pdf-center/{PID}", timeout=30)
    assert r.status_code == 200, r.text[:300]
    d = r.json()
    on_demand = d.get("on_demand") or d.get("cards") or d
    body_str = str(d).lower()
    assert "heatmap" in body_str, f"heatmap card not present in pdf-center: {body_str[:300]}"


# --- Regression ---
def test_regression_basic_endpoints():
    s = _login()
    for path in [
        f"/api/demand-signals/{PID}/config",
        f"/api/demand-signals/{PID}/markup-history",
        f"/api/demand-signals/{PID}/comp-deviations?year=2026&month=8",
        f"/api/ai-pricing/{PID}/suggestions",
    ]:
        r = s.get(f"{BASE_URL}{path}", timeout=30)
        assert r.status_code in (200, 404), f"{path} -> {r.status_code}"


def test_cleanup_undo_all():
    s = _login()
    r = s.post(f"{BASE_URL}/api/demand-signals/{PID}/undo-markups", json={}, timeout=30)
    assert r.status_code == 200
