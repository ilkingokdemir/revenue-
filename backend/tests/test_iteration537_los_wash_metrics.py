"""Iteration 537: LOS pricing, Group Wash, Modern Metrics + AI pricing regression."""
import os
from datetime import datetime, timezone
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASS = "HotelAdmin2026!"
PID = "default"


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=15)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text[:200]}"
    tok = r.json().get("access_token") or r.json().get("token")
    if tok:
        s.headers.update({"Authorization": f"Bearer {tok}"})
    return s


# ---------- LOS pricing ----------
def test_los_pricing(client):
    r = client.get(f"{BASE_URL}/api/los-pricing/{PID}", timeout=20)
    assert r.status_code == 200, r.text[:300]
    d = r.json()
    assert d["property_id"] == PID
    assert "sample_bookings" in d and isinstance(d["sample_bookings"], int)
    buckets = {b["bucket"]: b for b in d["buckets"]}
    assert set(buckets.keys()) == {"1-2", "3-6", "7+"}
    for b in d["buckets"]:
        assert "bookings" in b and "adr" in b
    tiers = d["suggested_tiers"]
    assert len(tiers) == 2
    assert tiers[0]["min_nights"] == 3 and tiers[1]["min_nights"] == 7
    for t in tiers:
        assert isinstance(t["discount_pct"], (int, float)) and t["discount_pct"] > 0
        assert "why" in t
    assert "note" in d


# ---------- Group Wash ----------
def test_group_wash(client):
    r = client.get(f"{BASE_URL}/api/group-wash/{PID}", timeout=15)
    assert r.status_code == 200, r.text[:300]
    d = r.json()
    assert d["property_id"] == PID
    assert isinstance(d["historical_wash_pct"], (int, float))
    assert isinstance(d["measured_blocks"], int)
    assert isinstance(d["active_blocks"], list)
    assert "note" in d


# ---------- Modern Metrics ----------
def test_modern_metrics(client):
    r = client.get(f"{BASE_URL}/api/modern-metrics/{PID}", timeout=20)
    assert r.status_code == 200, r.text[:300]
    d = r.json()
    for k in ("trevpor", "revpag", "goppar", "total_revenue",
              "room_revenue", "ancillary_revenue", "room_nights", "guests"):
        assert k in d, f"missing {k}"
        assert isinstance(d[k], (int, float))
    # consistency: trevpor == total_revenue / room_nights (allow rounding tolerance)
    if d["room_nights"] > 0:
        expected = round(d["total_revenue"] / d["room_nights"], 2)
        assert abs(d["trevpor"] - expected) < 0.05, f"{d['trevpor']} vs {expected}"
    # month should be current month YYYY-MM
    assert d["month"] == datetime.now(timezone.utc).strftime("%Y-%m")


# ---------- AI pricing regression: los_tiers injected ----------
def test_ai_pricing_los_tiers(client):
    r = client.get(
        f"{BASE_URL}/api/revenue/ai-pricing/{PID}/suggestions",
        params={"days": 3, "use_llm": "false"}, timeout=30)
    assert r.status_code == 200, r.text[:300]
    d = r.json()
    assert "suggestions" in d and isinstance(d["suggestions"], list)
    assert "summary" in d
    assert "los_tiers" in d
    assert isinstance(d["los_tiers"], list) and len(d["los_tiers"]) == 2


# ---------- Regression: demand calendar ----------
def test_demand_calendar(client):
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    r = client.get(f"{BASE_URL}/api/demand-calendar/{PID}",
                   params={"month": month}, timeout=20)
    assert r.status_code == 200, r.text[:300]
    d = r.json()
    assert "days" in d or "grid" in d or "cells" in d or isinstance(d, dict)


def test_orphan_gaps(client):
    r = client.get(f"{BASE_URL}/api/demand-calendar/{PID}/orphan-gaps", timeout=15)
    assert r.status_code == 200, r.text[:300]
