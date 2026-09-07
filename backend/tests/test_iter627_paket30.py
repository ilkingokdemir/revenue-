"""Iter 627 (Paket 30) — auto e-invoice on checkout, campaign short link/QR,
arrival reminder T-2 (WhatsApp + favorites), housekeeping conflict 409.

Coverage:
  - PUT /api/tr-compliance/efatura/default/settings auto_issue_on_checkout on/off
  - Checkout hook → /auto-log + /list contain auto invoice
  - GET /api/site-builder/public/c/{code} (302 + channel tracking + invalid ch)
  - GET .../c/{code}/qr.png (image/png)
  - GET .../c/NOPE (404)
  - GET /api/site-builder/default/campaign-stats channel counts
  - Arrival reminder run + log + stats + whatsapp_outbox
  - Housekeeping 409 conflict
"""
import os
import time
import uuid
import pytest
import requests
from datetime import datetime, timezone, timedelta
from pymongo import MongoClient

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL")
            or "https://review-hub-108.preview.emergentagent.com").rstrip("/")

ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASS = "HotelAdmin2026!"
PID = "default"

MONGO = MongoClient("mongodb://localhost:27017")
DB = MONGO["test_database"]


@pytest.fixture(scope="module")
def s():
    sess = requests.Session()
    sess.headers.update({"Content-Type": "application/json"})
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
    return requests.Session()


# ============ (1) Auto e-Invoice on checkout ============
class TestAutoEInvoice:
    booking_id = None
    booking_id2 = None

    def test_enable_auto(self, s):
        r = s.put(f"{s.base}/api/tr-compliance/efatura/{PID}/settings",
                  json={"auto_issue_on_checkout": True, "auto_submit": True,
                        "email_guest_copy": True, "auto_invoice_type": "earsiv"},
                  timeout=15)
        assert r.status_code == 200
        st = r.json()["settings"]
        assert st["auto_issue_on_checkout"] is True
        assert st["auto_submit"] is True
        assert st["email_guest_copy"] is True
        assert st["auto_invoice_type"] == "earsiv"

    def _pick_booking(self, s, exclude=None):
        r = s.get(f"{s.base}/api/bookings?property_id={PID}&limit=200", timeout=15)
        if r.status_code != 200:
            return None
        for b in r.json():
            if b.get("tr_invoice_uuid"):
                continue
            if not b.get("guest_email"):
                continue
            if b.get("status") not in ("confirmed", "checked_in"):
                continue
            if exclude and b.get("id") == exclude:
                continue
            return b.get("id")
        return None

    def test_checkout_triggers_auto_log(self, s):
        bid = self._pick_booking(s)
        if not bid:
            pytest.skip("No eligible booking")
        TestAutoEInvoice.booking_id = bid

        # count existing auto-log entries for this booking to see the new one
        r0 = s.get(f"{s.base}/api/tr-compliance/efatura/{PID}/auto-log", timeout=15)
        prev = [x for x in r0.json().get("log", []) if x.get("booking_id") == bid]

        r = s.put(f"{s.base}/api/bookings/{bid}/status?status=checked_out", timeout=20)
        assert r.status_code == 200, r.text

        # background asyncio.create_task → give it a moment
        for _ in range(6):
            time.sleep(2)
            r2 = s.get(f"{s.base}/api/tr-compliance/efatura/{PID}/auto-log", timeout=15)
            entries = [x for x in r2.json().get("log", []) if x.get("booking_id") == bid]
            if len(entries) > len(prev):
                entry = entries[0]
                assert entry.get("status") == "ok", entry
                assert entry.get("invoice_no")
                assert entry.get("ettn")
                assert entry.get("submitted") is True
                assert entry.get("simulated") is True
                assert entry.get("email_status") == "mocked"
                return
        pytest.fail("Auto-log entry not created after checkout within timeout")

    def test_invoice_in_list_auto_issued_sent(self, s):
        bid = TestAutoEInvoice.booking_id
        if not bid:
            pytest.skip("no booking")
        r = s.get(f"{s.base}/api/tr-compliance/efatura/{PID}/list?limit=200", timeout=15)
        assert r.status_code == 200
        invs = r.json().get("invoices", [])
        match = [i for i in invs if i.get("booking_id") == bid and i.get("auto_issued")]
        assert match, "No auto_issued invoice found for booking"
        assert match[0].get("status") == "sent"

    def test_disable_auto_no_new_log(self, s):
        # disable
        r = s.put(f"{s.base}/api/tr-compliance/efatura/{PID}/settings",
                  json={"auto_issue_on_checkout": False}, timeout=15)
        assert r.status_code == 200
        assert r.json()["settings"]["auto_issue_on_checkout"] is False

        bid2 = self._pick_booking(s, exclude=TestAutoEInvoice.booking_id)
        if not bid2:
            pytest.skip("no second booking")
        TestAutoEInvoice.booking_id2 = bid2

        r0 = s.get(f"{s.base}/api/tr-compliance/efatura/{PID}/auto-log", timeout=15)
        before_count = len(r0.json().get("log", []))

        r = s.put(f"{s.base}/api/bookings/{bid2}/status?status=checked_out", timeout=20)
        assert r.status_code == 200
        time.sleep(4)
        r1 = s.get(f"{s.base}/api/tr-compliance/efatura/{PID}/auto-log", timeout=15)
        after_count = len(r1.json().get("log", []))
        # No new entry expected (hook short-circuits before inserting log when disabled)
        assert after_count == before_count

    def test_restore_auto_setting_on(self, s):
        r = s.put(f"{s.base}/api/tr-compliance/efatura/{PID}/settings",
                  json={"auto_issue_on_checkout": True}, timeout=15)
        assert r.status_code == 200


# ============ (2) Campaign short link + QR ============
class TestCampaignShortLink:
    def test_302_valid_channel(self, public):
        r = public.get(f"{BASE_URL}/api/site-builder/public/c/QANOW10?ch=email",
                       allow_redirects=False, timeout=15)
        assert r.status_code == 302
        loc = r.headers.get("Location", "")
        assert "/site/default/blog/aktif-kampanya" in loc
        assert "utm_source=email" in loc
        assert "utm_campaign=QANOW10" in loc

    def test_302_invalid_channel_becomes_other(self, public):
        r = public.get(f"{BASE_URL}/api/site-builder/public/c/QANOW10?ch=zzz",
                       allow_redirects=False, timeout=15)
        assert r.status_code == 302
        loc = r.headers.get("Location", "")
        assert "utm_source=other" in loc

    def test_qr_png(self, public):
        r = public.get(f"{BASE_URL}/api/site-builder/public/c/QANOW10/qr.png",
                       timeout=15)
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("image/png")
        assert len(r.content) > 200
        assert r.content[:4] == b"\x89PNG"

    def test_404_unknown_code(self, public):
        r = public.get(f"{BASE_URL}/api/site-builder/public/c/NOPE-XYZ",
                       allow_redirects=False, timeout=15)
        assert r.status_code == 404

    def test_campaign_stats_reflects_clicks(self, s):
        r = s.get(f"{s.base}/api/site-builder/{PID}/campaign-stats", timeout=15)
        assert r.status_code == 200
        d = r.json()
        camp = next((c for c in d["campaigns"] if c["promo_code"] == "QANOW10"), None)
        assert camp
        assert camp["clicks"] >= 2
        assert "email" in camp["clicks_by_channel"]
        assert "other" in camp["clicks_by_channel"]
        assert camp["short_path"] == "/c/QANOW10"
        assert "clicks" in d["totals"]


# ============ (3) Arrival reminder T-2 ============
class TestArrivalReminder:
    booking_id = None
    prev_booking_id = None

    def test_seed_and_run(self, s):
        # Insert previous booking with Breakfast Package favorite (must be for property default)
        today = datetime.now(timezone.utc).date()
        prev_id = str(uuid.uuid4())
        DB.bookings.insert_one({
            "id": prev_id,
            "booking_ref": f"MHB-QA-PREV-{prev_id[:6].upper()}",
            "property_id": PID,
            "guest_name": "QA Arrival",
            "guest_email": "qa.arrival@example.com",
            "check_in": (today - timedelta(days=30)).isoformat(),
            "check_out": (today - timedelta(days=28)).isoformat(),
            "nights": 2,
            "status": "checked_out",
            "total_price": 200.0,
            "currency": "GBP",
            "post_upsells": [{"name": "Breakfast Package", "price": 15.0, "paid": True}],
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        TestArrivalReminder.prev_booking_id = prev_id

        # Insert current booking for T+2
        new_id = str(uuid.uuid4())
        DB.bookings.insert_one({
            "id": new_id,
            "booking_ref": f"MHB-QA-ARR-{new_id[:6].upper()}",
            "property_id": PID,
            "guest_name": "QA Arrival",
            "guest_email": "qa.arrival@example.com",
            "guest_phone": "+905551112233",
            "guest_lang": "en",
            "check_in": (today + timedelta(days=2)).isoformat(),
            "check_out": (today + timedelta(days=4)).isoformat(),
            "nights": 2,
            "status": "confirmed",
            "total_price": 250.0,
            "currency": "GBP",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        TestArrivalReminder.booking_id = new_id

        r = s.post(f"{s.base}/api/arrival-reminder/run/{PID}", timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["candidates"] >= 1
        assert d["mocked"] >= 1 or d["sent"] >= 1

    def test_log_entry(self, s):
        bid = TestArrivalReminder.booking_id
        if not bid:
            pytest.skip("no seed")
        r = s.get(f"{s.base}/api/arrival-reminder/log/{PID}", timeout=15)
        assert r.status_code == 200
        logs = r.json()
        mine = [l for l in logs if l.get("booking_id") == bid]
        assert mine, "No log for seeded booking"
        entry = mine[0]
        assert "email" in entry.get("channels", [])
        assert "whatsapp" in entry.get("channels", []), entry
        assert entry.get("whatsapp_status") == "mocked"
        # Favorite check: Breakfast Package must be an active upsell item for default → yes
        assert entry.get("favorites", 0) >= 1, entry

    def test_whatsapp_outbox(self):
        bid = TestArrivalReminder.booking_id
        if not bid:
            pytest.skip("no seed")
        doc = DB.whatsapp_outbox.find_one({"kind": "arrival_reminder", "booking_id": bid},
                                          {"_id": 0})
        assert doc, "No whatsapp_outbox document"
        assert doc.get("to") == "+905551112233"
        assert "/api/revenue/upsell/claim/" in (doc.get("body") or "")

    def test_stats_shape(self, s):
        r = s.get(f"{s.base}/api/arrival-reminder/stats/{PID}", timeout=15)
        assert r.status_code == 200
        d = r.json()
        for k in ("reminders", "whatsapp", "offers", "claimed",
                  "conversion_pct", "revenue", "by_label"):
            assert k in d
        assert d["reminders"] >= 1
        assert d["whatsapp"] >= 1
        assert d["offers"] >= 1

    def test_claim_increments_stats(self, s, public):
        bid = TestArrivalReminder.booking_id
        if not bid:
            pytest.skip("no seed")
        tok = DB.upsell_claim_tokens.find_one({"booking_id": bid, "used_at": {"$exists": False}},
                                              {"_id": 0, "token": 1})
        if not tok:
            pytest.skip("no unused claim token")
        stats0 = s.get(f"{s.base}/api/arrival-reminder/stats/{PID}", timeout=15).json()
        claimed0 = stats0["claimed"]
        r = public.get(f"{BASE_URL}/api/revenue/upsell/claim/{tok['token']}", timeout=15)
        assert r.status_code == 200
        assert "text/html" in r.headers.get("content-type", "")
        stats1 = s.get(f"{s.base}/api/arrival-reminder/stats/{PID}", timeout=15).json()
        assert stats1["claimed"] >= claimed0 + 1

    def test_cleanup(self):
        # Remove seed docs
        for bid in (TestArrivalReminder.booking_id, TestArrivalReminder.prev_booking_id):
            if bid:
                DB.bookings.delete_one({"id": bid})
                DB.whatsapp_outbox.delete_many({"booking_id": bid})
                DB.arrival_reminder_log.delete_many({"booking_id": bid})
                DB.upsell_claim_tokens.delete_many({"booking_id": bid})


# ============ (4) Housekeeping 409 conflict ============
class TestHousekeepingConflict:
    room_id = None
    original_status = None
    original_updated_at = None

    def test_pick_room(self, s):
        r = s.get(f"{s.base}/api/housekeeping/rooms/{PID}", timeout=15)
        assert r.status_code == 200
        rooms = r.json()
        assert rooms
        # pick room 101 if present else first
        room = next((rm for rm in rooms if rm.get("room_number") == "101"), rooms[0])
        TestHousekeepingConflict.room_id = room["id"]
        TestHousekeepingConflict.original_status = room.get("status")
        TestHousekeepingConflict.original_updated_at = room.get("updated_at")

    def test_transition_in_progress_ok(self, s):
        rid = TestHousekeepingConflict.room_id
        base = TestHousekeepingConflict.original_updated_at
        r = s.put(f"{s.base}/api/housekeeping/rooms/{rid}/status",
                  json={"status": "in_progress", "base_updated_at": base}, timeout=15)
        assert r.status_code == 200
        assert r.json()["status"] == "in_progress"

    def test_stale_base_conflict_409(self, s):
        rid = TestHousekeepingConflict.room_id
        old_base = TestHousekeepingConflict.original_updated_at
        r = s.put(f"{s.base}/api/housekeeping/rooms/{rid}/status",
                  json={"status": "clean", "base_updated_at": old_base}, timeout=15)
        assert r.status_code == 409, r.text
        body = r.json()
        # HTTPException(detail=dict) → body.detail is the dict
        detail = body.get("detail") if isinstance(body, dict) else {}
        assert isinstance(detail, dict)
        assert (detail.get("current") or {}).get("status") == "in_progress"

    def test_legacy_no_base_ok(self, s):
        rid = TestHousekeepingConflict.room_id
        r = s.put(f"{s.base}/api/housekeeping/rooms/{rid}/status",
                  json={"status": "clean"}, timeout=15)
        assert r.status_code == 200
        assert r.json()["status"] == "clean"

    def test_restore_original(self, s):
        rid = TestHousekeepingConflict.room_id
        orig = TestHousekeepingConflict.original_status or "clean"
        r = s.put(f"{s.base}/api/housekeeping/rooms/{rid}/status",
                  json={"status": orig}, timeout=15)
        assert r.status_code == 200
