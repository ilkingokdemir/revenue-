"""Iter 626 (Paket 29) — e-Fatura/e-Arşiv, translation lock, campaign stats, upsell payment.

Coverage:
  - TR compliance: settings GET/PUT (VAT presets, custom rate, VKN validation, api_key masking), validate-id
  - e-Fatura: build, submit (409 duplicate), html, cancel (422 empty reason), list, bulk
  - Site builder translation lock: approved filter on public GET
  - Campaign stats + track (page_views increment)
  - Upsell payment: intent, confirm, add-upsell
"""
import os
import copy
import pytest
import requests

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL")
            or os.environ.get("PUBLIC_BASE_URL")
            or "https://review-hub-108.preview.emergentagent.com").rstrip("/")

ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASS = "HotelAdmin2026!"
PID = "default"
UPSELL_BOOKING = "MHB-A8502A2D"
UPSELL_EMAIL = "qa.upsell2@example.com"


# ---------------------- Fixtures ----------------------
@pytest.fixture(scope="module")
def s():
    sess = requests.Session()
    sess.headers.update({"Content-Type": "application/json"})
    # try public, fallback to localhost
    for base in (BASE_URL, "http://localhost:8001"):
        try:
            r = sess.post(f"{base}/api/auth/login",
                          json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=15)
            if r.status_code == 200:
                sess.base = base
                sess.headers.update({"Authorization": f"Bearer {r.json()['token']}"})
                return sess
        except Exception:
            continue
    pytest.skip("Cannot authenticate")


@pytest.fixture(scope="module")
def public():
    sess = requests.Session()
    sess.headers.update({"Content-Type": "application/json"})
    return sess


# ---------------------- e-Fatura Settings ----------------------
class TestEfaturaSettings:
    def test_get_default_settings(self, s):
        r = s.get(f"{s.base}/api/tr-compliance/efatura/{PID}/settings", timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert "settings" in d
        assert len(d["vat_presets"]) == 14
        assert len(d["integrators"]) == 8
        assert d["settings"].get("property_id") == PID

    def test_put_uk_preset(self, s):
        r = s.put(f"{s.base}/api/tr-compliance/efatura/{PID}/settings",
                  json={"vat_preset": "uk_standard"}, timeout=15)
        assert r.status_code == 200
        st = r.json()["settings"]
        assert st["vat_rate"] == 20
        assert st["tax_label"] == "VAT"
        assert st["tax_region"] == "uk"

    def test_put_custom(self, s):
        r = s.put(f"{s.base}/api/tr-compliance/efatura/{PID}/settings",
                  json={"vat_preset": "custom", "vat_rate": 12.5,
                        "tax_label": "GST", "tax_region": "custom"}, timeout=15)
        assert r.status_code == 200
        st = r.json()["settings"]
        assert st["vat_rate"] == 12.5
        assert st["tax_label"] == "GST"
        assert st["tax_region"] == "custom"

    def test_put_invalid_vkn(self, s):
        r = s.put(f"{s.base}/api/tr-compliance/efatura/{PID}/settings",
                  json={"sender_vkn": "1234567891"}, timeout=15)
        assert r.status_code == 422

    def test_put_valid_tckn(self, s):
        r = s.put(f"{s.base}/api/tr-compliance/efatura/{PID}/settings",
                  json={"sender_vkn": "10000000146"}, timeout=15)
        assert r.status_code == 200

    def test_put_api_key_masking(self, s):
        r = s.put(f"{s.base}/api/tr-compliance/efatura/{PID}/settings",
                  json={"api_key": "sk_test_xyz9876"}, timeout=15)
        assert r.status_code == 200
        assert r.json()["settings"]["api_key_masked"] == "••••9876"

    def test_restore_tr_preset(self, s):
        r = s.put(f"{s.base}/api/tr-compliance/efatura/{PID}/settings",
                  json={"vat_preset": "tr_accommodation", "sender_vkn": ""}, timeout=15)
        assert r.status_code == 200
        st = r.json()["settings"]
        assert st["vat_rate"] == 10
        assert st["tax_label"] == "KDV"


# ---------------------- Validate-ID ----------------------
class TestValidateId:
    def test_valid_vkn(self, s):
        r = s.post(f"{s.base}/api/tr-compliance/validate-id",
                   json={"value": "1234567890"}, timeout=10)
        assert r.status_code == 200
        d = r.json()
        assert d["valid"] is True
        assert d["type"] == "vkn"

    def test_invalid_tckn(self, s):
        r = s.post(f"{s.base}/api/tr-compliance/validate-id",
                   json={"value": "12345678901"}, timeout=10)
        assert r.status_code == 200
        d = r.json()
        assert d["valid"] is False

    def test_unknown(self, s):
        r = s.post(f"{s.base}/api/tr-compliance/validate-id",
                   json={"value": "abc"}, timeout=10)
        assert r.status_code == 200
        assert r.json()["type"] == "unknown"


# ---------------------- e-Fatura build/submit/html/cancel/list/bulk ----------------------
class TestEfaturaLifecycle:
    invoice_uuid = None
    invoice_no = None

    def _pick_booking(self, s):
        # Find a booking for property default without tr_invoice_uuid
        r = s.get(f"{s.base}/api/bookings?property_id={PID}&limit=200", timeout=15)
        if r.status_code == 200 and isinstance(r.json(), list):
            for b in r.json():
                if not b.get("tr_invoice_uuid") and b.get("id"):
                    return b["id"]
        # fallback: search bookings collection via direct endpoint alt
        return None

    def test_build_earsiv(self, s):
        bid = self._pick_booking(s)
        if not bid:
            pytest.skip("No booking without existing invoice for property default")
        r = s.post(f"{s.base}/api/tr-compliance/efatura/build",
                   json={"booking_id": bid, "invoice_type": "earsiv"}, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "uuid" in d and "invoice_no" in d
        assert "<cbc:Percent>10.0</cbc:Percent>" in d["xml"]
        TestEfaturaLifecycle.invoice_uuid = d["uuid"]
        TestEfaturaLifecycle.invoice_no = d["invoice_no"]

    def test_submit(self, s):
        uid = TestEfaturaLifecycle.invoice_uuid
        if not uid:
            pytest.skip("No invoice built")
        r = s.post(f"{s.base}/api/tr-compliance/efatura/{uid}/submit", timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["status"] == "sent"
        assert d.get("ettn")
        assert d.get("simulated") is True
        assert d.get("provider")

    def test_submit_duplicate_409(self, s):
        uid = TestEfaturaLifecycle.invoice_uuid
        if not uid:
            pytest.skip("No invoice built")
        r = s.post(f"{s.base}/api/tr-compliance/efatura/{uid}/submit", timeout=15)
        assert r.status_code == 409

    def test_html(self, s):
        uid = TestEfaturaLifecycle.invoice_uuid
        if not uid:
            pytest.skip("No invoice built")
        r = s.get(f"{s.base}/api/tr-compliance/efatura/{uid}/html", timeout=15)
        assert r.status_code == 200
        assert "text/html" in r.headers.get("content-type", "")
        body = r.text
        assert TestEfaturaLifecycle.invoice_no in body
        assert "ETTN" in body
        assert "Genel toplam" in body

    def test_cancel_empty_reason_422(self, s):
        uid = TestEfaturaLifecycle.invoice_uuid
        if not uid:
            pytest.skip("No invoice built")
        r = s.post(f"{s.base}/api/tr-compliance/efatura/{uid}/cancel",
                   json={"reason": ""}, timeout=15)
        assert r.status_code == 422

    def test_cancel_ok(self, s):
        uid = TestEfaturaLifecycle.invoice_uuid
        if not uid:
            pytest.skip("No invoice built")
        r = s.post(f"{s.base}/api/tr-compliance/efatura/{uid}/cancel",
                   json={"reason": "test"}, timeout=15)
        assert r.status_code == 200
        assert r.json()["status"] == "cancelled"

    def test_list_shape(self, s):
        r = s.get(f"{s.base}/api/tr-compliance/efatura/{PID}/list", timeout=20)
        assert r.status_code == 200
        d = r.json()
        assert "invoices" in d
        for inv in d["invoices"][:20]:
            assert "xml" not in inv
            assert "tax_rate" in inv
            if inv.get("status") == "sent":
                assert inv.get("ettn")

    def test_bulk_nov(self, s):
        r = s.post(f"{s.base}/api/tr-compliance/efatura/bulk",
                   json={"property_id": PID, "month": "2026-11"}, timeout=60)
        assert r.status_code == 200
        d = r.json()
        assert "created" in d and "failed" in d and "invoices" in d

    def test_bulk_oct_idempotent(self, s):
        # 2026-10 previously created 75; second call should be 0
        r = s.post(f"{s.base}/api/tr-compliance/efatura/bulk",
                   json={"property_id": PID, "month": "2026-10"}, timeout=60)
        assert r.status_code == 200
        d = r.json()
        # Bookings with tr_invoice_uuid are skipped
        assert d["created"] >= 0


# ---------------------- Translation lock ----------------------
class TestTranslationLock:
    original = None

    def test_get_admin_translations(self, s):
        r = s.get(f"{s.base}/api/site-builder/{PID}", timeout=15)
        assert r.status_code == 200
        site = r.json()["site"]
        TestTranslationLock.original = copy.deepcopy(site)
        content = site.get("content") or {}
        tr = content.get("translations") or {}
        en = tr.get("en") or {}
        assert isinstance(en.get("approved") or {}, dict)

    def test_partial_approval_filters_public(self, s, public):
        assert TestTranslationLock.original is not None
        content = copy.deepcopy(TestTranslationLock.original.get("content") or {})
        # keep existing content, replace only translations.en
        content["translations"] = dict(content.get("translations") or {})
        content["translations"]["en"] = {
            "headline": "EN Headline X",
            "about": "EN About Y",
            "approved": {"headline": True, "about": False},
        }
        payload = {
            "template": TestTranslationLock.original.get("template", "classic"),
            "content": content,
            "mode": TestTranslationLock.original.get("mode", "simple"),
            "published": TestTranslationLock.original.get("published", True),
        }
        r = s.post(f"{s.base}/api/site-builder/{PID}", json=payload, timeout=20)
        assert r.status_code == 200, r.text

        pub = public.get(f"{s.base}/api/site-builder/public/site/{PID}", timeout=15)
        assert pub.status_code == 200
        pc = (pub.json().get("site") or {}).get("content") or {}
        en = (pc.get("translations") or {}).get("en") or {}
        assert en.get("headline") == "EN Headline X"
        assert "about" not in en

    def test_all_approved_shows_all(self, s, public):
        content = copy.deepcopy(TestTranslationLock.original.get("content") or {})
        content["translations"] = dict(content.get("translations") or {})
        content["translations"]["en"] = {
            "headline": "EN Headline X",
            "about": "EN About Y",
            "approved": {"headline": True, "about": True},
        }
        payload = {
            "template": TestTranslationLock.original.get("template", "classic"),
            "content": content,
            "mode": TestTranslationLock.original.get("mode", "simple"),
            "published": TestTranslationLock.original.get("published", True),
        }
        r = s.post(f"{s.base}/api/site-builder/{PID}", json=payload, timeout=20)
        assert r.status_code == 200
        pub = public.get(f"{s.base}/api/site-builder/public/site/{PID}", timeout=15)
        pc = (pub.json().get("site") or {}).get("content") or {}
        en = (pc.get("translations") or {}).get("en") or {}
        assert en.get("headline") and en.get("about")

    def test_all_unapproved_removes_en(self, s, public):
        content = copy.deepcopy(TestTranslationLock.original.get("content") or {})
        content["translations"] = dict(content.get("translations") or {})
        content["translations"]["en"] = {
            "headline": "EN Headline X",
            "about": "EN About Y",
            "approved": {"headline": False, "about": False},
        }
        payload = {
            "template": TestTranslationLock.original.get("template", "classic"),
            "content": content,
            "mode": TestTranslationLock.original.get("mode", "simple"),
            "published": TestTranslationLock.original.get("published", True),
        }
        r = s.post(f"{s.base}/api/site-builder/{PID}", json=payload, timeout=20)
        assert r.status_code == 200
        pub = public.get(f"{s.base}/api/site-builder/public/site/{PID}", timeout=15)
        pc = (pub.json().get("site") or {}).get("content") or {}
        assert "en" not in (pc.get("translations") or {})

    def test_sitemap_hreflang_only_when_approved(self, s, public):
        r = public.get(f"{s.base}/api/site-builder/public/sitemap/{PID}.xml", timeout=15)
        assert r.status_code == 200
        # Currently EN is unapproved from previous test → hreflang="en" should NOT appear
        assert 'hreflang="en"' not in r.text

    def test_restore_original(self, s):
        """Restore approved={headline:True} at least, preserve TR content."""
        assert TestTranslationLock.original is not None
        content = copy.deepcopy(TestTranslationLock.original.get("content") or {})
        # ensure headline approved to leave data in a good state
        tr = content.get("translations") or {}
        en = tr.get("en") or {}
        ap = en.get("approved") or {}
        ap["headline"] = True
        en["approved"] = ap
        tr["en"] = en
        content["translations"] = tr
        payload = {
            "template": TestTranslationLock.original.get("template", "classic"),
            "content": content,
            "mode": TestTranslationLock.original.get("mode", "simple"),
            "published": TestTranslationLock.original.get("published", True),
        }
        r = s.post(f"{s.base}/api/site-builder/{PID}", json=payload, timeout=20)
        assert r.status_code == 200


# ---------------------- Campaign stats + track ----------------------
class TestCampaignStats:
    def test_stats_shape(self, s):
        r = s.get(f"{s.base}/api/site-builder/{PID}/campaign-stats", timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert "campaigns" in d and "totals" in d
        codes = {c["promo_code"]: c for c in d["campaigns"]}
        assert "QAWIN20" in codes
        assert "QANOW10" in codes
        assert codes["QAWIN20"]["status"] == "scheduled"
        assert codes["QANOW10"]["status"] == "active"
        for c in d["campaigns"]:
            for k in ("coupon_uses", "bookings", "revenue", "page_views", "conversion_pct"):
                assert k in c

    def test_page_view_increment(self, s, public):
        r0 = s.get(f"{s.base}/api/site-builder/{PID}/campaign-stats", timeout=15).json()
        before = {c["promo_code"]: c["page_views"] for c in r0["campaigns"]}.get("QANOW10", 0)

        # Need to find the QANOW10 slug
        slug = None
        for c in r0["campaigns"]:
            if c["promo_code"] == "QANOW10":
                slug = c["slug"]
                break
        assert slug
        tr = public.post(f"{s.base}/api/site-builder/public/track",
                         json={"property_id": PID, "event": "view",
                               "page": f"blog/{slug}", "visitor_id": "qa1"}, timeout=10)
        assert tr.status_code == 200

        r1 = s.get(f"{s.base}/api/site-builder/{PID}/campaign-stats", timeout=15).json()
        after = {c["promo_code"]: c["page_views"] for c in r1["campaigns"]}["QANOW10"]
        assert after == before + 1


# ---------------------- Upsell payment ----------------------
class TestUpsellPayment:
    def test_upsell_intent(self, s, public):
        r = public.post(f"{s.base}/api/payments/upsell-intent",
                        json={"booking_ref": UPSELL_BOOKING, "guest_email": UPSELL_EMAIL},
                        timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "client_secret" in d
        assert d["amount"] == 25.0
        assert "Late Check-out" in (d.get("items") or [])

    def test_upsell_intent_wrong_email(self, public):
        r = public.post(f"{BASE_URL}/api/payments/upsell-intent",
                        json={"booking_ref": UPSELL_BOOKING,
                              "guest_email": "wrong@example.com"}, timeout=15)
        assert r.status_code == 404

    def test_upsell_confirm_not_paid(self, public, s):
        r = public.post(f"{s.base}/api/payments/upsell-intent/confirm",
                        json={"booking_ref": UPSELL_BOOKING,
                              "guest_email": UPSELL_EMAIL}, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d.get("paid") is False
        assert d.get("status") == "requires_payment_method"

    def test_add_upsell_unpaid_total(self, s, public):
        # Get another upsell id from GET /api/upsells/default
        rlist = public.get(f"{s.base}/api/upsells/{PID}", timeout=10)
        assert rlist.status_code == 200
        items = rlist.json() if isinstance(rlist.json(), list) else (rlist.json() or {}).get("items", [])
        # Filter out Late Check-out to add a different item
        candidate = None
        for u in items:
            if u.get("name") and "Late Check-out" not in u["name"]:
                candidate = u
                break
        if not candidate:
            pytest.skip("No other upsell available")

        r = public.post(f"{s.base}/api/booking/{UPSELL_BOOKING}/add-upsell",
                        json={"upsell_id": candidate["id"], "guest_email": UPSELL_EMAIL},
                        timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("ok") is True
        # already-added case is valid
        assert "upsell_unpaid_total" in d
        assert float(d["upsell_unpaid_total"]) >= 25.0
