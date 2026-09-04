"""
Iteration 612 tests: Root Cause / Staff Intelligence / DCV coupon reminders /
Service Recovery quick actions / Admin phone+karne_whatsapp / Morning karne extension.
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://review-hub-108.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    assert r.status_code == 200, r.text
    j = r.json()
    return j.get("access_token") or j.get("token")


@pytest.fixture(scope="module")
def client(token):
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    return s


# ---------- Root Cause ----------
def test_root_cause_endpoint(client):
    r = client.get(f"{BASE_URL}/api/reviews/root-cause?property_id=all&days=30", timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    for k in ("days", "negative_reviews", "previous_negative_reviews", "items", "top"):
        assert k in d, f"missing {k}: {d.keys()}"
    assert d["days"] == 30
    assert isinstance(d["items"], list)
    if d["items"]:
        it = d["items"][0]
        for k in ("topic", "count", "frequency_pct", "prev_pct", "trend_pts", "severity", "recurring", "action"):
            assert k in it, f"item missing {k}: {it.keys()}"


# ---------- Staff Intelligence ----------
def test_staff_intelligence_endpoint(client):
    r = client.get(f"{BASE_URL}/api/reviews/staff-intelligence?property_id=all&days=90", timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    for k in ("staff", "top_praised", "recurring_complaints"):
        assert k in d
    assert isinstance(d["staff"], list)
    # Check John has negative mentions
    john = next((s for s in d["staff"] if s.get("name") == "John"), None)
    assert john is not None, f"John not in staff list: {[s.get('name') for s in d['staff']]}"
    assert john.get("negative", 0) >= 1, f"John negatives should be >=1, got {john}"
    for k in ("mentions", "positive", "negative", "avg_rating"):
        assert k in john


# ---------- Analytics Dashboard extension ----------
def test_analytics_dashboard_has_new_keys(client):
    r = client.get(f"{BASE_URL}/api/analytics/dashboard", timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    assert "root_cause" in d, f"root_cause missing: {list(d.keys())}"
    assert "staff_intelligence" in d, f"staff_intelligence missing: {list(d.keys())}"


# ---------- Admin permissions phone + karne_whatsapp ----------
def test_admin_permissions_phone_karne(client):
    # find admin user id
    r = client.get(f"{BASE_URL}/api/admin/users", timeout=30)
    assert r.status_code == 200, r.text
    users = r.json()
    if isinstance(users, dict) and "users" in users:
        users = users["users"]
    admin = next((u for u in users if u.get("email") == ADMIN_EMAIL), None)
    assert admin is not None, "admin user not found"
    uid = admin.get("id") or admin.get("_id")

    r = client.put(f"{BASE_URL}/api/admin/users/{uid}/permissions",
                   json={"phone": "+447700900123", "karne_whatsapp": False}, timeout=20)
    assert r.status_code == 200, r.text
    d = r.json()
    # Response should reflect phone and karne_whatsapp:false (either at top-level or in a user obj)
    def _get(dct, key):
        if key in dct:
            return dct[key]
        u = dct.get("user") or {}
        return u.get(key)
    assert _get(d, "phone") == "+447700900123", d
    assert _get(d, "karne_whatsapp") is False, d

    # set back to true
    r2 = client.put(f"{BASE_URL}/api/admin/users/{uid}/permissions",
                    json={"phone": "+447700900123", "karne_whatsapp": True}, timeout=20)
    assert r2.status_code == 200, r2.text
    assert _get(r2.json(), "karne_whatsapp") is True


# ---------- Morning Karne ----------
def test_morning_karne_send_now(client):
    r = client.post(f"{BASE_URL}/api/morning-karne/default/send-now", json={}, timeout=60)
    assert r.status_code == 200, r.text
    d = r.json()
    karne = d.get("karne") or d
    checks = karne.get("checks") or d.get("checks") or []
    names = [c.get("name") for c in checks if isinstance(c, dict)]
    assert any("Kök neden" in (n or "") for n in names), f"Kök neden not in checks: {names}"
    wa = d.get("whatsapp") or karne.get("whatsapp") or []
    # Ensure admin phone appears in whatsapp with queued status
    found = False
    for w in wa:
        to = w.get("to") or w.get("phone") or ""
        st = w.get("status") or ""
        if "447700900123" in to and st == "queued":
            found = True
            break
    assert found, f"admin phone queued whatsapp entry missing: {wa}"


# ---------- Direct Conversion coupon reminders ----------
def test_dcv_stats_review_coupons(client):
    r = client.get(f"{BASE_URL}/api/direct-conversion/stats", timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    rc = d.get("review_coupons")
    assert rc is not None, f"review_coupons missing: {list(d.keys())}"
    for k in ("issued", "used", "reminded", "expiring_30d", "expired", "usage_pct", "revenue"):
        assert k in rc, f"review_coupons missing {k}: {rc.keys()}"


def test_dcv_coupon_reminders_all(client):
    r = client.post(f"{BASE_URL}/api/review-collection/coupon-reminders/all", json={}, timeout=60)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d.get("ok") is True, d
    for k in ("candidates", "sent", "mocked"):
        assert k in d, f"missing {k}: {d}"


# ---------- Service Recovery ----------
def test_service_recovery_flow(client):
    # create
    r = client.post(f"{BASE_URL}/api/service-recovery", json={
        "property_id": "default", "text": "Test şikayet: gürültü",
        "category": "noise", "channel": "review", "guest_name": "Test Guest"
    }, timeout=30)
    assert r.status_code in (200, 201), r.text
    d = r.json()
    cid = d.get("id") or d.get("_id")
    assert cid, d

    # mark called
    r2 = client.put(f"{BASE_URL}/api/service-recovery/{cid}",
                    json={"called": True, "call_notes": "görüşüldü"}, timeout=30)
    assert r2.status_code == 200, r2.text
    d2 = r2.json()
    assert d2.get("status") == "in_progress", d2
    assert d2.get("called_at"), d2
    assert d2.get("called_by"), d2

    # resolve
    r3 = client.put(f"{BASE_URL}/api/service-recovery/{cid}",
                    json={"status": "resolved"}, timeout=30)
    assert r3.status_code == 200, r3.text
    d3 = r3.json()
    assert d3.get("resolved_at"), d3

    # cleanup
    rd = client.delete(f"{BASE_URL}/api/service-recovery/{cid}", timeout=30)
    assert rd.status_code in (200, 204), rd.text
