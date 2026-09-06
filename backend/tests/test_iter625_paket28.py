"""
Iter 625 (Paket 28) — Branch selector propagation, post-payment upsell add,
campaign date auto-activation, TR/EN translation diff QC.
Backend-focused pytest (frontend covered via Playwright).
"""
import os
import pytest
import requests

_PUB = os.environ.get("REACT_APP_BACKEND_URL", "https://review-hub-108.preview.emergentagent.com").rstrip("/")
_LOCAL = "http://localhost:8001"


def _pick_base():
    """Use public URL if reachable, else fall back to internal loopback."""
    try:
        requests.get(f"{_PUB}/api/upsells/default", timeout=5)
        return _PUB
    except Exception:
        return _LOCAL


BASE_URL = _pick_base()
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"

BOOKING_REF = "AB-316679AF"
GUEST_EMAIL = "ava.yıldız@example.com"
ALREADY_UPSELL = "6e4f2fce-cdb5-49a8-b75f-bac52f5283f2"


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=20)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def auth_headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# ---------- SITE / CAMPAIGN PROMO ----------

class TestCampaignPromoWindow:
    def test_get_site_default_has_two_campaign_posts(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/site-builder/default", headers=auth_headers, timeout=20)
        assert r.status_code == 200
        content = r.json()["site"].get("content", {})
        codes = {p.get("promo_code"): p for p in content.get("posts", [])}
        assert "QAWIN20" in codes, f"posts={list(codes)}"
        assert "QANOW10" in codes
        assert codes["QAWIN20"]["starts_at"].startswith("2030")
        assert codes["QANOW10"]["starts_at"].startswith("2026")
        assert content.get("headline") == "Şehrin kalbinde butik konfor"

    def test_qanow10_valid_now(self):
        r = requests.post(
            f"{BASE_URL}/api/promo-codes/validate",
            params={"code": "QANOW10", "property_id": "default", "nights": 2, "subtotal": 200},
            timeout=15,
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["valid"] is True
        assert d["code"] == "QANOW10"
        assert d["discount_type"] == "percentage"
        assert d["discount_value"] == 10
        # 10% of 200
        assert abs(d["discount_amount"] - 20.0) < 0.01

    def test_qawin20_not_yet_active(self):
        r = requests.post(
            f"{BASE_URL}/api/promo-codes/validate",
            params={"code": "QAWIN20", "property_id": "default", "nights": 2, "subtotal": 200},
            timeout=15,
        )
        # Either 400 (not yet active) or 404 (is_active=false due to window)
        assert r.status_code in (400, 404), r.text
        msg = (r.json().get("detail") or "").lower()
        # accept either message
        assert ("not yet active" in msg) or ("invalid" in msg) or ("expired" in msg)

    def test_save_site_preserves_and_expires_qanow10(self, auth_headers):
        """GET → mutate ends_at to past for QANOW10 → POST full content back → verify inactive → restore."""
        g = requests.get(f"{BASE_URL}/api/site-builder/default", headers=auth_headers, timeout=20)
        assert g.status_code == 200
        site = g.json()["site"]
        content = site.get("content") or {}
        original_ends_at = None
        for p in content.get("posts", []):
            if p.get("promo_code") == "QANOW10":
                original_ends_at = p.get("ends_at")
                p["ends_at"] = "2026-01-15"  # already past (today ~2026-09)
        payload = {"template": site.get("template", "classic"),
                   "content": content,
                   "mode": site.get("mode", "simple"),
                   "engine_template": site.get("engine_template", ""),
                   "published": bool(site.get("published"))}
        s = requests.post(f"{BASE_URL}/api/site-builder/default", headers=auth_headers,
                          json=payload, timeout=25)
        assert s.status_code == 200, s.text

        # Validate now should fail (inactive OR expired)
        v = requests.post(f"{BASE_URL}/api/promo-codes/validate",
                          params={"code": "QANOW10", "property_id": "default",
                                  "nights": 2, "subtotal": 200}, timeout=15)
        assert v.status_code in (400, 404), v.text

        # Restore
        for p in content.get("posts", []):
            if p.get("promo_code") == "QANOW10":
                p["ends_at"] = original_ends_at or "2027-01-01"
        payload["content"] = content
        r2 = requests.post(f"{BASE_URL}/api/site-builder/default", headers=auth_headers,
                           json=payload, timeout=25)
        assert r2.status_code == 200

        # And validate should now work
        v2 = requests.post(f"{BASE_URL}/api/promo-codes/validate",
                           params={"code": "QANOW10", "property_id": "default",
                                   "nights": 2, "subtotal": 200}, timeout=15)
        assert v2.status_code == 200, v2.text
        assert v2.json()["valid"] is True


# ---------- UPSELLS ----------

class TestUpsells:
    def test_get_upsells_default_public(self):
        r = requests.get(f"{BASE_URL}/api/upsells/default", timeout=15)
        assert r.status_code == 200
        arr = r.json()
        assert isinstance(arr, list) and len(arr) > 0
        ids = [u["id"] for u in arr]
        assert ALREADY_UPSELL in ids

    def test_add_upsell_already_added(self):
        r = requests.post(f"{BASE_URL}/api/booking/{BOOKING_REF}/add-upsell",
                          json={"upsell_id": ALREADY_UPSELL, "guest_email": GUEST_EMAIL},
                          timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("ok") is True
        assert d.get("already") is True

    def test_add_upsell_wrong_email(self):
        r = requests.post(f"{BASE_URL}/api/booking/{BOOKING_REF}/add-upsell",
                          json={"upsell_id": ALREADY_UPSELL, "guest_email": "wrong@example.com"},
                          timeout=15)
        assert r.status_code == 404

    def test_add_upsell_unknown_id(self):
        r = requests.post(f"{BASE_URL}/api/booking/{BOOKING_REF}/add-upsell",
                          json={"upsell_id": "does-not-exist-xxx", "guest_email": GUEST_EMAIL},
                          timeout=15)
        assert r.status_code == 404

    def test_add_new_upsell_success(self):
        # Pick a different upsell than the already-added one
        arr = requests.get(f"{BASE_URL}/api/upsells/default", timeout=15).json()
        candidate = next((u for u in arr if u["id"] != ALREADY_UPSELL), None)
        assert candidate is not None
        upsell_id = candidate["id"]
        r = requests.post(f"{BASE_URL}/api/booking/{BOOKING_REF}/add-upsell",
                          json={"upsell_id": upsell_id, "guest_email": GUEST_EMAIL},
                          timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("ok") is True
        # Either newly added or already added (idempotent replay)
        if not d.get("already"):
            assert "added" in d
            assert d["added"]["id"] == upsell_id
            assert isinstance(d["added"].get("price"), (int, float))
            assert "new_total" in d
            assert "balance_due" in d
