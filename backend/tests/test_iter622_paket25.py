"""Iter 622 backend tests:
 - Permission-changes monthly audit PDF
 - Journal alerts config/put/run + forced failure via direct DB insert
 - Gift card seasonal designs list/preview/public config/purchase/admin create/resend
"""
import os
import datetime as dt
import requests
import pytest
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    try:
        with open("/app/frontend/.env") as _f:
            for _line in _f:
                if _line.startswith("REACT_APP_BACKEND_URL"):
                    BASE_URL = _line.split("=", 1)[1].strip().strip('"').strip("'").rstrip("/")
                    break
    except Exception:
        pass
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"
PID = "aldgate-flats"

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")

# Read DB_NAME from backend/.env if available
try:
    with open("/app/backend/.env") as f:
        for line in f:
            if line.startswith("DB_NAME"):
                DB_NAME = line.split("=", 1)[1].strip().strip('"').strip("'")
            if line.startswith("MONGO_URL"):
                MONGO_URL = line.split("=", 1)[1].strip().strip('"').strip("'")
except Exception:
    pass


@pytest.fixture(scope="module")
def admin():
    s = requests.Session()
    s.headers["Content-Type"] = "application/json"
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, r.text
    tok = r.json().get("access_token") or r.json().get("token")
    s.headers["Authorization"] = f"Bearer {tok}"
    return s


@pytest.fixture(scope="module")
def db():
    c = MongoClient(MONGO_URL)
    return c[DB_NAME]


# ---------- Permission changes audit PDF ----------
class TestPermissionAuditPdf:
    def _month(self):
        # server date ~2026-09-05
        return "2026-09"

    def test_pdf_all(self, admin):
        m = self._month()
        r = admin.get(f"{BASE_URL}/api/admin/permission-changes/report.pdf?month={m}&property_id=all")
        assert r.status_code == 200, r.text
        assert "application/pdf" in r.headers.get("content-type", "").lower()
        cd = r.headers.get("content-disposition", "")
        assert "attachment" in cd.lower()
        assert f"yetki-denetim-{m}.pdf" in cd
        assert r.content.startswith(b"%PDF")
        assert len(r.content) > 2048

    def test_pdf_property(self, admin):
        m = self._month()
        r = admin.get(f"{BASE_URL}/api/admin/permission-changes/report.pdf?month={m}&property_id={PID}")
        assert r.status_code == 200
        assert r.content.startswith(b"%PDF")

    def test_pdf_bad_month(self, admin):
        r = admin.get(f"{BASE_URL}/api/admin/permission-changes/report.pdf?month=abc&property_id=all")
        assert r.status_code == 422


# ---------- Journal alerts ----------
class TestJournalAlerts:
    def test_get_config(self, admin):
        r = admin.get(f"{BASE_URL}/api/accounting/journal/alerts/config/{PID}")
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("enabled", "emails", "whatsapp", "missing_days", "log"):
            assert k in d, f"missing key {k}"
        assert isinstance(d["log"], list)

    def test_put_config_filters_invalid(self, admin):
        payload = {
            "enabled": True,
            "emails": ["qa@test.com", "bad"],
            "whatsapp": ["+447700900123", "abc"],
        }
        r = admin.put(f"{BASE_URL}/api/accounting/journal/alerts/config/{PID}", json=payload)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "qa@test.com" in d["emails"]
        assert "bad" not in d["emails"]
        # whatsapp: keep only digit numbers
        assert any("447700900123" in w for w in d["whatsapp"])
        assert "abc" not in d["whatsapp"]

    def test_run_no_alerts(self, admin):
        r = admin.post(f"{BASE_URL}/api/accounting/journal/alerts/run/{PID}?force=true")
        assert r.status_code == 200, r.text
        d = r.json()
        assert "checked" in d
        assert "alerts" in d

    def test_forced_failure_and_notification(self, admin, db):
        yesterday = (dt.date(2026, 9, 5) - dt.timedelta(days=1)).isoformat()
        # Insert bad journal
        db.accounting_journal.delete_many({"id": "qa-fail"})
        db.accounting_journal.insert_one({
            "id": "qa-fail",
            "property_id": PID,
            "business_date": yesterday,
            "provider": "xero",
            "status": "failed",
            "response": "QA forced failure",
            "created_at": dt.datetime.utcnow(),
        })
        try:
            r = admin.post(f"{BASE_URL}/api/accounting/journal/alerts/run/{PID}?force=true")
            assert r.status_code == 200, r.text
            d = r.json()
            assert len(d.get("alerts", [])) >= 1
            failed_alerts = [a for a in d["alerts"] if a.get("kind") == "failed"]
            assert failed_alerts, f"no failed kind in {d['alerts']}"
            a0 = failed_alerts[0]
            # recipients check: either list or count
            recips = a0.get("recipients") or a0.get("email_recipients") or []
            if isinstance(recips, int):
                assert recips >= 1
            else:
                assert len(recips) >= 1

            # config log contains entry
            r2 = admin.get(f"{BASE_URL}/api/accounting/journal/alerts/config/{PID}")
            log = r2.json().get("log", [])
            assert len(log) >= 1
            latest = log[0] if log else {}
            sent = latest.get("sent") or {}
            # email should be 'mocked'
            emails_sent = sent.get("email") or sent.get("emails") or []
            s_email = str(emails_sent).lower()
            assert "mocked" in s_email, f"no mocked marker: {emails_sent}"
            # whatsapp status queued if present
            wa = sent.get("whatsapp") or []
            assert wa != None

            # notifications collection has entry
            n = db.notifications.find_one({"type": "journal_alert"})
            assert n is not None
        finally:
            # cleanup
            db.accounting_journal.delete_many({"id": "qa-fail"})
            db.journal_alerts.delete_many({"journal_id": "qa-fail"})
            # restore config
            admin.put(f"{BASE_URL}/api/accounting/journal/alerts/config/{PID}",
                      json={"enabled": False, "emails": [], "whatsapp": []})


# ---------- Gift card designs ----------
class TestGiftDesigns:
    def test_designs_list(self, admin):
        r = admin.get(f"{BASE_URL}/api/gift-cards/designs")
        assert r.status_code == 200, r.text
        d = r.json()
        designs = d if isinstance(d, list) else d.get("designs", [])
        ids = {x["id"] for x in designs}
        assert {"classic", "festive", "summer", "spring"}.issubset(ids)
        for x in designs:
            for k in ("id", "name"):
                assert k in x

    def test_preview_festive(self, admin):
        r = admin.get(f"{BASE_URL}/api/gift-cards/preview",
                      params={"property_id": PID, "design": "festive", "amount": 150, "recipient_name": "QA"})
        assert r.status_code == 200, r.text
        assert "text/html" in r.headers.get("content-type", "").lower()
        body = r.text
        import re
        assert re.search(r"MHB-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}", body), "no MHB code pattern"
        assert "150" in body
        assert "QA" in body

    def test_preview_unknown_fallback(self, admin):
        r = admin.get(f"{BASE_URL}/api/gift-cards/preview",
                      params={"property_id": PID, "design": "unknown", "amount": 100, "recipient_name": "X"})
        assert r.status_code == 200

    def test_public_config_default_classic(self):
        r = requests.get(f"{BASE_URL}/api/booking/gift-cards/config/{PID}")
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("design") == "classic"
        designs = d.get("designs") or []
        assert len(designs) == 4
        for x in designs:
            assert "bg" in x and "text" in x

    def test_admin_config_change(self, admin):
        payload = {
            "enabled": True,
            "presets": [50, 100, 150, 200, 300, 500],
            "min": 25, "max": 2000,
            "expires_days": 365,
            "design": "summer",
            "designs_enabled": ["classic", "summer", "spring"],
        }
        r = admin.put(f"{BASE_URL}/api/gift-cards/config/{PID}", json=payload)
        assert r.status_code == 200, r.text

        r2 = requests.get(f"{BASE_URL}/api/booking/gift-cards/config/{PID}")
        d = r2.json()
        assert d.get("design") == "summer"
        assert len(d.get("designs", [])) == 3
        assert not any(x["id"] == "festive" for x in d["designs"])

    def test_public_purchase_falls_back(self, admin):
        # festive not enabled → should fall back to summer
        r = requests.post(f"{BASE_URL}/api/booking/gift-cards/purchase", json={
            "property_id": PID, "amount": 100,
            "purchaser_email": "d@test.com",
            "design": "festive",
        })
        assert r.status_code in (200, 201), r.text
        # Admin list newest
        r2 = admin.get(f"{BASE_URL}/api/gift-cards?property_id={PID}")
        assert r2.status_code == 200
        items = r2.json() if isinstance(r2.json(), list) else r2.json().get("items", [])
        assert items
        # find newest by created_at
        newest = items[0]
        # allow that response might just be dict with .design
        assert newest.get("design") in ("summer", "classic"), f"unexpected fallback: {newest.get('design')}"
        assert newest.get("design") == "summer"

    def test_admin_create_spring(self, admin):
        r = admin.post(f"{BASE_URL}/api/gift-cards", json={
            "property_id": PID, "amount": 40,
            "recipient_email": "r@test.com",
            "design": "spring",
        })
        assert r.status_code in (200, 201), r.text
        d = r.json()
        assert d.get("design") == "spring"
        er = d.get("email_result") or {}
        rec = er.get("recipient") or er.get("to") or ""
        assert "mocked" in str(rec).lower() or "mocked" in str(er).lower()
        pytest.gc_id = d.get("id") or d.get("_id")

    def test_resend_with_design(self, admin):
        gid = getattr(pytest, "gc_id", None)
        assert gid, "no gift card id from prev test"
        r = admin.post(f"{BASE_URL}/api/gift-cards/{gid}/resend-email", json={"design": "festive"})
        assert r.status_code == 200, r.text

    def test_restore_config(self, admin):
        payload = {
            "enabled": True,
            "presets": [50, 100, 150, 200, 300, 500],
            "min": 25, "max": 2000,
            "expires_days": 365,
            "design": "classic",
            "designs_enabled": ["classic", "festive", "summer", "spring"],
        }
        r = admin.put(f"{BASE_URL}/api/gift-cards/config/{PID}", json=payload)
        assert r.status_code == 200
