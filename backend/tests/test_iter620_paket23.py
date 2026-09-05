"""Iteration 620 - Paket 2 (Site Builder) & Paket 3 (Hotel Ads, Embed, Gift Cards, Exit Intent, Deposit)"""
import os
import time
from datetime import date, timedelta

import pytest
import requests

_url = os.environ.get("REACT_APP_BACKEND_URL")
if not _url:
    # read from frontend/.env
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    _url = line.split("=", 1)[1].strip()
                    break
    except Exception:
        pass
BASE_URL = (_url or "").rstrip("/")
API = BASE_URL + "/api"
PID = "aldgate-flats"

ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASS = "HotelAdmin2026!"


# ---------------- fixtures ----------------
@pytest.fixture(scope="session")
def admin_token():
    s = requests.Session()
    # Try common login endpoints
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=15)
    if r.status_code == 200:
        data = r.json()
        tok = data.get("access_token") or data.get("token")
        if tok:
            return tok
    pytest.skip(f"Admin login failed: {r.status_code} {r.text[:200]}")


@pytest.fixture(scope="session")
def admin_client(admin_token):
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"})
    return s


@pytest.fixture(scope="session")
def rate_plans():
    r = requests.get(f"{API}/booking/rate-plans/{PID}", timeout=15)
    assert r.status_code == 200
    return r.json()


def _plan_id(rate_plans, code):
    plans = rate_plans if isinstance(rate_plans, list) else rate_plans.get("plans") or rate_plans.get("items") or []
    for p in plans:
        if p.get("code") == code or p.get("id") == code:
            return p.get("id")
    return None


# ---------------- Site Builder ----------------
class TestSiteBuilder:
    def test_public_site(self):
        r = requests.get(f"{API}/site-builder/public/site/{PID}", timeout=15)
        assert r.status_code == 200
        d = r.json()
        site = d["site"]
        assert site["template"] in ("coastal", "classic", "modern", "boutique", "urban", "nature")
        content = site["content"]
        assert isinstance(content["blocks"], list) and len(content["blocks"]) == 10
        for b in content["blocks"]:
            assert "id" in b and "enabled" in b
        assert "pages_enabled" in content
        assert isinstance(d.get("room_types"), list)
        assert isinstance(d.get("photos"), list)
        assert isinstance(d.get("reviews"), list)

    def test_templates_admin(self, admin_client):
        r = admin_client.get(f"{API}/site-builder/templates", timeout=15)
        assert r.status_code == 200
        tpls = r.json()["templates"]
        ids = {t["id"] for t in tpls}
        assert ids == {"classic", "modern", "boutique", "coastal", "urban", "nature"}

    def test_save_and_restore(self, admin_client):
        # Read current
        r = admin_client.get(f"{API}/site-builder/{PID}", timeout=15)
        assert r.status_code == 200
        current = r.json()["site"]
        orig_content = current.get("content") or {}

        # Save with nature + reorder (reviews to 2nd) + disable one block + reduced pages
        new_blocks = [
            {"id": "hero", "enabled": True},
            {"id": "reviews", "enabled": True},
            {"id": "availability", "enabled": True},
            {"id": "about", "enabled": True},
            {"id": "rooms", "enabled": True},
            {"id": "amenities", "enabled": False},  # disabled
            {"id": "gallery", "enabled": True},
            {"id": "map", "enabled": True},
            {"id": "faq", "enabled": True},
            {"id": "contact", "enabled": True},
        ]
        faqs = orig_content.get("faqs") or [
            {"q": "Check-in?", "a": "3 pm"},
            {"q": "Parking?", "a": "Yes"},
            {"q": "Pets?", "a": "No"},
        ]
        payload = {
            "template": "nature",
            "published": True,
            "content": {
                **orig_content,
                "blocks": new_blocks,
                "faqs": faqs,
                "pages_enabled": ["home", "rooms", "contact"],
            },
        }
        r = admin_client.post(f"{API}/site-builder/{PID}", json=payload, timeout=15)
        assert r.status_code == 200
        assert r.json()["published"] is True

        # Verify public reflects
        r2 = requests.get(f"{API}/site-builder/public/site/{PID}", timeout=15)
        assert r2.status_code == 200
        pub = r2.json()["site"]
        assert pub["template"] == "nature"
        blocks = pub["content"]["blocks"]
        assert blocks[1]["id"] == "reviews"
        assert any(b["id"] == "amenities" and b["enabled"] is False for b in blocks)
        assert set(pub["content"]["pages_enabled"]) == {"home", "rooms", "contact"}

        # Invalid template
        bad = admin_client.post(f"{API}/site-builder/{PID}", json={"template": "hackz"}, timeout=15)
        assert bad.status_code == 422

        # RESTORE to coastal defaults
        default_blocks = [
            {"id": "hero", "enabled": True}, {"id": "availability", "enabled": True},
            {"id": "about", "enabled": True}, {"id": "rooms", "enabled": True},
            {"id": "amenities", "enabled": True}, {"id": "gallery", "enabled": True},
            {"id": "reviews", "enabled": True}, {"id": "map", "enabled": True},
            {"id": "faq", "enabled": True}, {"id": "contact", "enabled": True},
        ]
        restore_content = {
            **orig_content,
            "headline": "Şehrin kalbinde sakin bir kaçış",
            "address": "12 Aldgate High St, London EC3N 1AL",
            "phone": "+44 20 7123 4567",
            "email": "stay@aldgateflats.com",
            "map_query": "Aldgate High Street, London",
            "about": orig_content.get("about") or "Aldgate Flats — luxury flats in the heart of the City of London.",
            "blocks": default_blocks,
            "faqs": faqs,
            "pages_enabled": ["home", "rooms", "gallery", "location", "faq", "contact"],
        }
        rr = admin_client.post(f"{API}/site-builder/{PID}",
                               json={"template": "coastal", "published": True, "content": restore_content},
                               timeout=15)
        assert rr.status_code == 200
        # verify restored
        r3 = requests.get(f"{API}/site-builder/public/site/{PID}", timeout=15)
        assert r3.status_code == 200
        assert r3.json()["site"]["template"] == "coastal"


# ---------------- Contact / Inquiries ----------------
class TestContact:
    inquiry_id = None

    def test_public_contact(self):
        r = requests.post(f"{API}/site-builder/public/contact", json={
            "property_id": PID, "name": "QA Test", "email": "qa@test.com",
            "phone": "123", "message": "Test message from QA"
        }, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d.get("ok") is True
        assert d.get("id")
        TestContact.inquiry_id = d["id"]

    def test_contact_validation(self):
        r = requests.post(f"{API}/site-builder/public/contact", json={
            "property_id": PID, "name": "X", "email": "not-an-email", "message": "hi"
        }, timeout=15)
        assert r.status_code == 422

    def test_admin_inquiries(self, admin_client):
        assert TestContact.inquiry_id
        r = admin_client.get(f"{API}/site-builder/{PID}/inquiries", timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["new_count"] >= 1
        ids = [i["id"] for i in d["items"]]
        assert TestContact.inquiry_id in ids

        # update status
        r2 = admin_client.put(f"{API}/site-builder/{PID}/inquiries/{TestContact.inquiry_id}",
                              json={"status": "replied"}, timeout=15)
        assert r2.status_code == 200

        # invalid status
        r3 = admin_client.put(f"{API}/site-builder/{PID}/inquiries/{TestContact.inquiry_id}",
                              json={"status": "hacked"}, timeout=15)
        assert r3.status_code == 422


# ---------------- Hotel Ads ----------------
class TestHotelAds:
    def test_hotel_list_feed(self):
        r = requests.get(f"{API}/hotel-ads/hotel-list/{PID}.xml", timeout=15)
        assert r.status_code == 200
        assert "application/xml" in r.headers.get("content-type", "")
        body = r.text
        assert "<listings" in body
        assert f"<id>{PID}</id>" in body
        assert "<name>" in body

    def test_ari_feed(self):
        r = requests.get(f"{API}/hotel-ads/ari/{PID}.xml?days=3", timeout=20)
        assert r.status_code == 200
        assert "application/xml" in r.headers.get("content-type", "")
        body = r.text
        assert "<Transaction" in body
        assert "<Result>" in body
        assert "<Property>" in body
        assert "<Checkin>" in body
        assert "<Nights>" in body
        assert "<RoomID>" in body
        assert "<RatePlanID>" in body
        assert 'currency="GBP"' in body
        assert "<Refundable" in body

    def test_landing_redirect(self):
        ci = (date.today() + timedelta(days=10)).isoformat()
        r = requests.get(f"{API}/hotel-ads/landing?property={PID}&checkin={ci}&nights=2&adults=2",
                         timeout=15, allow_redirects=False)
        assert r.status_code == 302
        loc = r.headers.get("location", "")
        assert f"/book?property={PID}" in loc
        assert "check_in=" in loc
        assert "check_out=" in loc
        assert "utm_source=google_hotel_ads" in loc

    def test_status(self, admin_client):
        r = admin_client.get(f"{API}/hotel-ads/status/{PID}", timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert len(d["checks"]) == 6
        assert "hotel_list" in d["feeds"]
        assert "ari" in d["feeds"]
        assert "point_of_sale" in d["feeds"]
        assert "stats" in d
        assert isinstance(d["steps"], list) and len(d["steps"]) >= 3


# ---------------- Embed ----------------
class TestEmbed:
    def test_widget_js(self):
        r = requests.get(f"{API}/embed/widget.js?property={PID}", timeout=15)
        assert r.status_code == 200
        assert "javascript" in r.headers.get("content-type", "")
        assert "mhb-booking-widget" in r.text
        assert f"/book?property={PID}" in r.text

    def test_widget_invalid_property(self):
        r = requests.get(f"{API}/embed/widget.js?property=a b", timeout=15)
        assert r.status_code == 422

    def test_snippet(self, admin_client):
        r = admin_client.get(f"{API}/embed/snippet/{PID}", timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert "snippet" in d and "iframe" in d and "params" in d
        assert "mhb-booking-widget" in d["snippet"]


# ---------------- Gift Cards ----------------
class TestGiftCards:
    admin_card_code = None
    admin_card_id = None

    def test_config_public(self):
        r = requests.get(f"{API}/booking/gift-cards/config/{PID}", timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["enabled"] is True
        assert d["presets"] == [50, 100, 150, 200, 300, 500]
        assert d["currency"] == "GBP"

    def test_purchase(self):
        r = requests.post(f"{API}/booking/gift-cards/purchase", json={
            "property_id": PID, "amount": 100, "purchaser_email": "buyer@test.com",
            "purchaser_name": "Buyer", "recipient_name": "Rec", "origin_url": "https://x.test"
        }, timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d.get("card_id")
        # either stripe url OR mock:true+code
        assert d.get("url") or d.get("mock")

    def test_purchase_min_amount(self):
        r = requests.post(f"{API}/booking/gift-cards/purchase", json={
            "property_id": PID, "amount": 10, "purchaser_email": "buyer@test.com",
            "purchaser_name": "B"
        }, timeout=15)
        assert r.status_code == 400

    def test_purchase_missing_email(self):
        r = requests.post(f"{API}/booking/gift-cards/purchase", json={
            "property_id": PID, "amount": 100
        }, timeout=15)
        assert r.status_code == 422

    def test_admin_create_and_redeem(self, admin_client, rate_plans):
        # Admin create gift card (active immediately)
        r = admin_client.post(f"{API}/gift-cards", json={
            "property_id": PID, "amount": 60, "recipient_name": "QA"
        }, timeout=15)
        assert r.status_code in (200, 201), f"{r.status_code} {r.text[:200]}"
        d = r.json()
        code = d.get("code") or (d.get("card") or {}).get("code")
        cid = d.get("id") or (d.get("card") or {}).get("id")
        assert code
        TestGiftCards.admin_card_code = code
        TestGiftCards.admin_card_id = cid

        # Check card
        r2 = requests.post(f"{API}/booking/gift-cards/check",
                           json={"code": code, "property_id": PID}, timeout=15)
        assert r2.status_code == 200
        assert r2.json()["valid"] is True
        assert r2.json()["balance"] == 60

        # Wrong code
        r_wrong = requests.post(f"{API}/booking/gift-cards/check",
                                json={"code": "WRONG-XXXX-XXXX", "property_id": PID}, timeout=15)
        assert r_wrong.status_code == 404

        # Reserve-multi with gift_card_code
        flex_id = _plan_id(rate_plans, "flexible")
        if not flex_id:
            pytest.skip("no flexible plan found")
        ci = (date.today() + timedelta(days=40)).isoformat()
        co = (date.today() + timedelta(days=41)).isoformat()
        r3 = requests.post(f"{API}/booking/reserve-multi", json={
            "property_id": PID, "check_in": ci, "check_out": co,
            "guest_name": "QA Redeem", "guest_email": "qa@test.com", "guest_phone": "1",
            "adults": 2, "children": 0,
            "items": [{"room_type_id": "double-aldgate-flats", "rate_plan_id": flex_id, "qty": 1}],
            "gift_card_code": code
        }, timeout=30)
        assert r3.status_code == 200, r3.text[:300]
        rd = r3.json()
        assert rd["gift_card_applied"] == 60
        # base 89 - 60 = 29
        assert abs(rd["total_price"] - 29) < 0.5

        # Recheck: redeemed → 404
        r4 = requests.post(f"{API}/booking/gift-cards/check",
                           json={"code": code, "property_id": PID}, timeout=15)
        assert r4.status_code == 404

    def test_admin_config_save(self, admin_client):
        r = admin_client.put(f"{API}/gift-cards/config/{PID}", json={
            "enabled": True, "presets": [50, 100, 150, 200, 300, 500],
            "min": 25, "max": 2000, "expires_days": 365
        }, timeout=15)
        assert r.status_code == 200


# ---------------- Exit Intent ----------------
class TestExitIntent:
    def test_public_config(self):
        r = requests.get(f"{API}/booking/exit-intent/{PID}", timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["enabled"] is True
        assert d["code"] == "STAYDIRECT10"
        assert d["discount_pct"] == 10
        assert "delay_sec" in d

    def test_save_and_promo_auto(self, admin_client):
        r = admin_client.put(f"{API}/exit-intent/config/{PID}", json={
            "enabled": True, "discount_pct": 12, "code": "QAEXIT12",
            "delay_sec": 5, "title": "Bekle!", "body": "%{pct} indirim"
        }, timeout=15)
        assert r.status_code == 200

        # promo auto-created and validates
        r2 = requests.post(
            f"{API}/promo-codes/validate?code=QAEXIT12&property_id={PID}&nights=1&subtotal=100",
            timeout=15
        )
        assert r2.status_code == 200
        d = r2.json()
        assert d.get("valid") is True
        assert abs(d.get("discount_amount", 0) - 12) < 0.5

    def test_admin_get_stats(self, admin_client):
        r = admin_client.get(f"{API}/exit-intent/config/{PID}", timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert "stats" in d

    def test_shown(self):
        r = requests.post(f"{API}/booking/exit-intent/{PID}/shown", timeout=15)
        assert r.status_code == 200

    def test_restore_default(self, admin_client):
        r = admin_client.put(f"{API}/exit-intent/config/{PID}", json={
            "enabled": True, "discount_pct": 10, "code": "STAYDIRECT10",
            "delay_sec": 8, "title": "", "body": ""
        }, timeout=15)
        assert r.status_code == 200


# ---------------- Source & Deposit ----------------
class TestSourceAndDeposit:
    def test_source_google_hotel_ads(self, rate_plans):
        flex_id = _plan_id(rate_plans, "flexible")
        if not flex_id:
            pytest.skip("no flexible plan")
        ci = (date.today() + timedelta(days=60)).isoformat()
        co = (date.today() + timedelta(days=61)).isoformat()
        r = requests.post(f"{API}/booking/reserve-multi", json={
            "property_id": PID, "check_in": ci, "check_out": co,
            "guest_name": "QA Source", "guest_email": "qa@test.com", "guest_phone": "1",
            "adults": 2, "children": 0,
            "items": [{"room_type_id": "double-aldgate-flats", "rate_plan_id": flex_id, "qty": 1}],
            "source": "google_hotel_ads"
        }, timeout=30)
        assert r.status_code == 200, r.text[:300]
        ref = r.json()["booking_ref"]

        rr = requests.get(f"{API}/booking/reservation/{ref}", timeout=15)
        assert rr.status_code == 200
        assert rr.json().get("source") == "google_hotel_ads"

    def test_source_fallback_hacker(self, rate_plans):
        flex_id = _plan_id(rate_plans, "flexible")
        if not flex_id:
            pytest.skip("no flexible plan")
        ci = (date.today() + timedelta(days=70)).isoformat()
        co = (date.today() + timedelta(days=71)).isoformat()
        r = requests.post(f"{API}/booking/reserve-multi", json={
            "property_id": PID, "check_in": ci, "check_out": co,
            "guest_name": "QA Src2", "guest_email": "qa@test.com", "guest_phone": "1",
            "adults": 2, "children": 0,
            "items": [{"room_type_id": "double-aldgate-flats", "rate_plan_id": flex_id, "qty": 1}],
            "source": "hacker"
        }, timeout=30)
        assert r.status_code == 200
        ref = r.json()["booking_ref"]
        rr = requests.get(f"{API}/booking/reservation/{ref}", timeout=15)
        assert rr.status_code == 200
        assert rr.json().get("source") == "booking_engine"

    def test_deposit(self, rate_plans):
        flex_id = _plan_id(rate_plans, "flexible")
        nonref_id = _plan_id(rate_plans, "non_refundable")
        if not (flex_id and nonref_id):
            pytest.skip("plans not found")
        ci = (date.today() + timedelta(days=80)).isoformat()
        co = (date.today() + timedelta(days=81)).isoformat()
        r = requests.post(f"{API}/booking/reserve-multi", json={
            "property_id": PID, "check_in": ci, "check_out": co,
            "guest_name": "QA Dep", "guest_email": "qa@test.com", "guest_phone": "1",
            "adults": 2, "children": 0,
            "items": [
                {"room_type_id": "double-aldgate-flats", "rate_plan_id": nonref_id, "qty": 1},
                {"room_type_id": "double-aldgate-flats", "rate_plan_id": flex_id, "qty": 1},
            ],
        }, timeout=30)
        assert r.status_code == 200, r.text[:300]
        master = r.json()
        booking_id = master["id"]
        master_ref = master["booking_ref"]

        r2 = requests.post(f"{API}/payments/booking-checkout", json={
            "booking_id": booking_id, "origin_url": "https://x.test", "amount_mode": "deposit"
        }, timeout=30)
        assert r2.status_code == 200, r2.text[:300]
        assert r2.json().get("url")

        rr = requests.get(f"{API}/booking/reservation/{master_ref}", timeout=15)
        assert rr.status_code == 200
        rd = rr.json()
        assert rd.get("payment_plan") == "deposit"
        assert rd.get("deposit_due") is not None
        assert rd.get("balance_due") is not None
        # non_refundable line ~ 89 (deposit 100%), flexible ~ 89 (deposit 0%) → deposit_due ≈ 89
        assert rd["deposit_due"] > 0
        assert rd["deposit_due"] < float(rd.get("cart_total") or rd.get("total_price") or 999)
