"""Iter 628 (Paket 31) backend tests: Guest Pass, e-Fatura Archive ZIP, Campaign A/B, HK Mobile issue."""
import io
import os
import zipfile

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://review-hub-108.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"
PROP = "default"
REF = "MHB-A8502A2D"
GUEST_EMAIL = "qa.upsell2@example.com"


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def admin_headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# ========== GUEST PASS ==========
class TestGuestPass:
    def test_pass_data_ok(self):
        r = requests.get(f"{API}/guest-pass/{REF}", params={"email": GUEST_EMAIL}, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["booking_ref"] == REF
        assert d["hotel"]["name"], "hotel.name missing"
        assert isinstance(d["extras"], list)
        assert len(d["extras"]) == 2, f"Expected 2 extras, got {len(d['extras'])}"
        assert d["wallet"]["apple_ready"] is False
        assert d["wallet"]["google_ready"] is False

    def test_pass_wrong_email(self):
        r = requests.get(f"{API}/guest-pass/{REF}", params={"email": "wrong@example.com"}, timeout=15)
        assert r.status_code == 404

    def test_qr(self):
        r = requests.get(f"{API}/guest-pass/{REF}/qr.png", params={"email": GUEST_EMAIL}, timeout=15)
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("image/png")
        assert r.content[:8] == b"\x89PNG\r\n\x1a\n"

    def test_ics(self):
        r = requests.get(f"{API}/guest-pass/{REF}/calendar.ics", params={"email": GUEST_EMAIL}, timeout=15)
        assert r.status_code == 200
        assert "text/calendar" in r.headers["content-type"]
        body = r.text
        assert "BEGIN:VEVENT" in body
        assert "DTSTART;VALUE=DATE:20261026" in body, f"Missing DTSTART 20261026 in ics: {body[:400]}"

    def test_apple_pkpass_503_no_cert(self):
        r = requests.get(f"{API}/guest-pass/{REF}/apple.pkpass", params={"email": GUEST_EMAIL}, timeout=15)
        assert r.status_code == 503

    def test_google_503_no_sa(self):
        r = requests.get(f"{API}/guest-pass/{REF}/google", params={"email": GUEST_EMAIL}, timeout=15)
        assert r.status_code == 503


class TestWalletSettings:
    def test_get_defaults(self, admin_headers):
        r = requests.get(f"{API}/wallet-settings/{PROP}", headers=admin_headers, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert "apple_pass_type_id" in d
        assert "apple_cert_present" in d

    def test_put_apple_cert_and_ready_flip(self, admin_headers):
        # Enable apple
        r = requests.put(f"{API}/wallet-settings/{PROP}", headers=admin_headers,
                         json={"apple_pass_type_id": "pass.com.test",
                               "apple_cert_pem": "-----BEGIN CERT-----x"}, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["apple_cert_present"] is True
        assert d["apple_pass_type_id"] == "pass.com.test"

        # Pass data should now reflect apple_ready=true
        p = requests.get(f"{API}/guest-pass/{REF}", params={"email": GUEST_EMAIL}, timeout=15).json()
        assert p["wallet"]["apple_ready"] is True

        # apple.pkpass should now 501
        pk = requests.get(f"{API}/guest-pass/{REF}/apple.pkpass", params={"email": GUEST_EMAIL}, timeout=15)
        assert pk.status_code == 501, pk.text

        # Clear apple_pass_type_id
        r2 = requests.put(f"{API}/wallet-settings/{PROP}", headers=admin_headers,
                          json={"apple_pass_type_id": ""}, timeout=15)
        assert r2.status_code == 200
        p2 = requests.get(f"{API}/guest-pass/{REF}", params={"email": GUEST_EMAIL}, timeout=15).json()
        assert p2["wallet"]["apple_ready"] is False


# ========== E-INVOICE ARCHIVE ==========
class TestArchiveZip:
    def test_archive_ok(self, admin_headers):
        r = requests.get(f"{API}/tr-compliance/efatura/{PROP}/archive.zip",
                         params={"month": "2026-09"}, headers=admin_headers, timeout=30)
        assert r.status_code == 200, r.text[:500]
        assert r.headers["content-type"] == "application/zip"
        zf = zipfile.ZipFile(io.BytesIO(r.content))
        names = zf.namelist()
        assert f"ozet_2026-09.csv" in names, names
        pdfs = [n for n in names if n.startswith("pdf/") and n.endswith(".pdf")]
        xmls = [n for n in names if n.startswith("xml/") and n.endswith(".xml")]
        assert len(pdfs) >= 1, f"No PDFs in archive: {names}"
        # CSV header check
        csv_body = zf.read(f"ozet_2026-09.csv").decode("utf-8-sig")
        assert csv_body.split("\n")[0].startswith("invoice_no,"), csv_body[:200]
        # Verify PDFs start with %PDF-
        for p in pdfs[:3]:
            assert zf.read(p)[:5] == b"%PDF-", f"{p} not PDF"
        # XMLs count either 0 or equal to some — if any exist, sample well-formed
        for x in xmls[:2]:
            assert zf.read(x).lstrip().startswith(b"<"), f"{x} not xml-ish"

    def test_archive_empty_month_404(self, admin_headers):
        r = requests.get(f"{API}/tr-compliance/efatura/{PROP}/archive.zip",
                         params={"month": "2031-01"}, headers=admin_headers, timeout=15)
        assert r.status_code == 404

    def test_archive_bad_month_422(self, admin_headers):
        r = requests.get(f"{API}/tr-compliance/efatura/{PROP}/archive.zip",
                         params={"month": "bad"}, headers=admin_headers, timeout=15)
        assert r.status_code == 422


# ========== CAMPAIGN A/B ==========
class TestCampaignAB:
    def test_short_link_variant_and_cookie_sticky(self):
        s = requests.Session()
        r = s.get(f"{API}/site-builder/public/c/QANOW10", params={"ch": "email"},
                  allow_redirects=False, timeout=15)
        assert r.status_code == 302
        loc = r.headers["location"]
        assert loc.endswith("&v=A") or loc.endswith("&v=B"), loc
        assert "abv_QANOW10" in r.headers.get("set-cookie", ""), r.headers
        first_variant = loc[-1]
        # Second call same session — sticky
        r2 = s.get(f"{API}/site-builder/public/c/QANOW10", params={"ch": "email"},
                   allow_redirects=False, timeout=15)
        assert r2.headers["location"].endswith(f"&v={first_variant}")

    def test_short_link_both_variants_over_sessions(self):
        seen = set()
        for _ in range(20):
            s = requests.Session()
            r = s.get(f"{API}/site-builder/public/c/QANOW10", params={"ch": "email"},
                      allow_redirects=False, timeout=15)
            assert r.status_code == 302
            seen.add(r.headers["location"][-1])
            if seen == {"A", "B"}:
                break
        assert seen == {"A", "B"}, f"Only saw variants: {seen}"

    def test_track_and_stats(self, admin_headers):
        # Track view + cta for B
        for ev in ("view", "cta_click"):
            r = requests.post(f"{API}/site-builder/public/track",
                              json={"property_id": PROP, "event": ev, "page": "blog/aktif-kampanya",
                                    "variant": "B", "visitor_id": "abx"}, timeout=15)
            assert r.status_code == 200
        # Also A for balance
        requests.post(f"{API}/site-builder/public/track",
                      json={"property_id": PROP, "event": "view", "page": "blog/aktif-kampanya",
                            "variant": "A", "visitor_id": "abxa"}, timeout=15)
        # Stats
        r = requests.get(f"{API}/site-builder/{PROP}/campaign-stats", headers=admin_headers, timeout=15)
        assert r.status_code == 200
        body = r.json()
        rows = body["campaigns"] if isinstance(body, dict) and "campaigns" in body else body
        qanow = next((x for x in rows if x.get("promo_code") == "QANOW10"), None)
        assert qanow, rows
        ab = qanow.get("ab")
        assert ab, f"No ab block on QANOW10: {qanow}"
        for v in ("A", "B"):
            assert "clicks" in ab[v] and "views" in ab[v] and "cta" in ab[v] and "cta_rate_pct" in ab[v]
        assert ab.get("leader") in ("A", "B")
        assert ab.get("active") is True

    def test_apply_winner_and_restore(self, admin_headers):
        # Fetch site content first (need full doc to POST back)
        cfg_full = requests.get(f"{API}/site-builder/{PROP}", headers=admin_headers, timeout=15).json()
        site = cfg_full.get("site") or cfg_full
        posts = site.get("content", {}).get("posts", [])
        # locate QANOW10
        p_orig = next(p for p in posts if p.get("promo_code") == "QANOW10")
        orig_title = p_orig.get("title")
        orig_title_b = p_orig.get("title_b")
        assert orig_title_b == "Şimdi rezerve et, %10 kazan!", f"pre-condition failed: title_b={orig_title_b}"

        # Apply winner B
        r = requests.post(f"{API}/site-builder/{PROP}/campaign-ab/QANOW10/apply-winner",
                          headers=admin_headers, json={"winner": "B"}, timeout=15)
        assert r.status_code == 200
        assert r.json().get("ok") is True

        # Verify
        cfg2 = requests.get(f"{API}/site-builder/{PROP}", headers=admin_headers, timeout=15).json()
        site2 = cfg2.get("site") or cfg2
        p_after = next(p for p in site2.get("content", {}).get("posts", []) if p.get("promo_code") == "QANOW10")
        assert p_after["title"] == "Şimdi rezerve et, %10 kazan!"
        assert p_after.get("title_b", "") == ""
        assert p_after.get("ab_winner") == "B"

        # Restore: set title back to 'Aktif Kampanya' and title_b back
        content = site2.get("content", {})
        for p in content.get("posts", []):
            if p.get("promo_code") == "QANOW10":
                p["title"] = "Aktif Kampanya"
                p["title_b"] = "Şimdi rezerve et, %10 kazan!"
                p["ab_winner"] = ""
        payload = {
            "template": site2.get("template", "classic"),
            "content": content,
            "mode": site2.get("mode", "simple"),
            "engine_template": site2.get("engine_template", ""),
            "published": bool(site2.get("published")),
        }
        rp = requests.post(f"{API}/site-builder/{PROP}", headers=admin_headers, json=payload, timeout=20)
        assert rp.status_code in (200, 201), rp.text[:500]

        # Verify restored
        cfg3 = requests.get(f"{API}/site-builder/{PROP}", headers=admin_headers, timeout=15).json()
        site3 = cfg3.get("site") or cfg3
        p3 = next(p for p in site3.get("content", {}).get("posts", []) if p.get("promo_code") == "QANOW10")
        assert p3["title"] == "Aktif Kampanya"
        assert p3.get("title_b") == "Şimdi rezerve et, %10 kazan!"


# ========== HK MOBILE ISSUE ==========
class TestHKIssue:
    def test_create_issue(self, admin_headers):
        payload = {
            "property_id": PROP,
            "title": "Oda 104 — Tesisat",
            "description": "test",
            "category": "plumbing",
            "priority": "medium",
            "location": "Oda 104",
            "room_number": "104",
            "photos_before": ["data:image/jpeg;base64,/9j/4AAQ"],
            "source": "hk_mobile",
            "offline_reported_at": "2026-09-07T10:00:00Z",
        }
        r = requests.post(f"{API}/maintenance/issues", headers=admin_headers, json=payload, timeout=15)
        assert r.status_code in (200, 201), r.text[:500]
        d = r.json()
        assert "id" in d
        assert d.get("title") == "Oda 104 — Tesisat"
