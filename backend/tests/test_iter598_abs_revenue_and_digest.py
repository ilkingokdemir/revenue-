"""Iter 598: ABS Revenue Dashboard + Weekly Digest rebase section."""
import os
import requests
import pytest

def _load_url():
    url = os.environ.get("REACT_APP_BACKEND_URL")
    if not url:
        try:
            with open("/app/frontend/.env") as f:
                for line in f:
                    if line.startswith("REACT_APP_BACKEND_URL="):
                        url = line.split("=", 1)[1].strip()
                        break
        except Exception:
            pass
    assert url, "REACT_APP_BACKEND_URL not set"
    return url.rstrip("/")

BASE = _load_url()
PID = "aldgate-flats"


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE}/api/auth/login",
                      json={"email": "admin@hotelbox.com", "password": "HotelAdmin2026!"})
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def hdr(token):
    return {"Authorization": f"Bearer {token}"}


# ------------- ABS Revenue Dashboard -------------

def test_revenue_dashboard_requires_auth():
    r = requests.get(f"{BASE}/api/abs/{PID}/revenue-dashboard")
    assert r.status_code in (401, 403)


def test_revenue_dashboard_shape(hdr):
    r = requests.get(f"{BASE}/api/abs/{PID}/revenue-dashboard", headers=hdr)
    assert r.status_code == 200, r.text
    d = r.json()
    for k in ("monthly", "by_attribute", "total_abs_revenue", "attach_rate_pct", "total_bookings"):
        assert k in d, f"missing {k}"
    # monthly window: max 6 months (approx: last ~183 days)
    assert isinstance(d["monthly"], list)
    assert len(d["monthly"]) <= 7  # at most 6-7 buckets due to 183-day window
    # ordered ascending by month
    months = [m["month"] for m in d["monthly"]]
    assert months == sorted(months)
    # by_attribute sorted desc by revenue
    revs = [a["revenue"] for a in d["by_attribute"]]
    assert revs == sorted(revs, reverse=True)
    # total_abs_revenue matches sum of monthly abs_revenue
    total_monthly = round(sum(m["abs_revenue"] for m in d["monthly"]), 2)
    assert abs(total_monthly - d["total_abs_revenue"]) < 0.01


def test_revenue_dashboard_no_future_months(hdr):
    from datetime import datetime, timezone
    r = requests.get(f"{BASE}/api/abs/{PID}/revenue-dashboard", headers=hdr)
    d = r.json()
    cur_month = datetime.now(timezone.utc).strftime("%Y-%m")
    for m in d["monthly"]:
        assert m["month"] <= cur_month, f"future month leaked: {m['month']}"


# ------------- Weekly Digest send-now -------------

def test_send_now_returns_rebase_and_abs_changes(hdr):
    r = requests.post(f"{BASE}/api/weekly-digest/{PID}/send-now", headers=hdr)
    assert r.status_code == 200, r.text
    body = r.json()
    # send-now is forced; must return a digest doc
    assert "digest" in body, f"unexpected body: {body}"
    dg = body["digest"]
    assert "abs_price_changes_7d" in dg
    assert isinstance(dg["abs_price_changes_7d"], int)
    # rebase may be None if no recent rebase report — but key must be present
    assert "rebase" in dg
    if dg["rebase"]:
        for k in ("date", "weighted_change_pct", "loss", "breakeven_feasible", "occ_needed_pct"):
            assert k in dg["rebase"], f"rebase missing {k}"


def test_latest_html_contains_rebase_section(hdr):
    # Send once (forced) then check latest doc
    requests.post(f"{BASE}/api/weekly-digest/{PID}/send-now", headers=hdr)
    r = requests.get(f"{BASE}/api/weekly-digest/{PID}/latest", headers=hdr)
    assert r.status_code == 200
    body = r.json()
    assert body["latest"] is not None
    dg = body["live_preview"]
    assert "abs_price_changes_7d" in dg
    # Check email outbox for weekly_digest email
    ob = requests.get(f"{BASE}/api/email-outbox", headers=hdr)
    if ob.status_code == 200:
        rows = ob.json() if isinstance(ob.json(), list) else ob.json().get("outbox", [])
        digest_emails = [e for e in rows if "Haftalık Bülten" in (e.get("subject") or "")]
        if digest_emails:
            html = digest_emails[0].get("body") or digest_emails[0].get("html") or ""
            # Rebase section appears only if there's a recent report OR abs changes
            if dg.get("rebase") or dg.get("abs_price_changes_7d"):
                assert "Rebase analizi" in html or "ABS otomatik fiyat" in html


def test_send_now_requires_auth():
    r = requests.post(f"{BASE}/api/weekly-digest/{PID}/send-now")
    assert r.status_code in (401, 403)


# ------------- Regression: price-log -------------

def test_price_log_still_works(hdr):
    r = requests.get(f"{BASE}/api/abs/{PID}/price-log", headers=hdr)
    assert r.status_code == 200, r.text
    assert "log" in r.json()
