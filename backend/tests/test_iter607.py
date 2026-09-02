"""Iteration 607 backend tests: widget i18n, OTA banner conversion tracking, ramp ladder event_premium config."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://review-hub-108.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASS = "HotelAdmin2026!"


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=15)
    assert r.status_code == 200, f"Login failed {r.status_code}: {r.text[:200]}"
    return s


# ---------------- Widget i18n German ----------------
class TestWidgetGerman:
    def test_check_availability_de_signals(self):
        r = requests.post(
            f"{API}/booking-widget/check-availability",
            json={"property_id": "default", "check_in": "2026-09-12", "check_out": "2026-09-16"},
            timeout=20,
        )
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        rooms = data.get("available_rooms") or []
        assert rooms, "no available rooms"
        pe = rooms[0].get("price_explanation") or {}
        assert "headline_de" in pe, f"missing headline_de: keys={list(pe.keys())}"
        assert isinstance(pe.get("headline_de"), str) and len(pe["headline_de"]) > 0
        # Signals/drivers may be empty; if present must expose label_de
        for sig in pe.get("signals", []) or []:
            assert "label_de" in sig, f"signal missing label_de: {sig}"
        for drv in pe.get("drivers", []) or []:
            assert "label_de" in drv, f"driver missing label_de: {drv}"

    def test_minstay_restriction_de(self):
        r = requests.post(
            f"{API}/booking-widget/check-availability",
            json={"property_id": "default", "check_in": "2026-09-05", "check_out": "2026-09-06"},
            timeout=20,
        )
        assert r.status_code == 200
        data = r.json()
        # Look for restriction (may be nested under a room or top-level)
        blob = str(data)
        # Try to find restriction with message_de
        found = False
        def walk(o):
            nonlocal found
            if isinstance(o, dict):
                if "message_de" in o and "Mindestaufenthalt" in str(o.get("message_de", "")):
                    found = True
                for v in o.values():
                    walk(v)
            elif isinstance(o, list):
                for v in o:
                    walk(v)
        walk(data)
        assert found, f"Mindestaufenthalt message_de not found. Response snippet: {blob[:500]}"


# ---------------- OTA Banner + Conversion ----------------
class TestOtaConversion:
    def test_banner_view_and_booking_and_report(self, admin_session):
        # 1. Log banner view
        r = requests.post(
            f"{API}/booking-widget/ota-banner-view",
            json={"property_id": "default", "ota": "Expedia", "lang": "de"},
            timeout=15,
        )
        assert r.status_code == 200, r.text[:300]
        assert r.json().get("ok") is True

        # 2. Public booking with channel_source
        book_payload = {
            "property_id": "default",
            "room_type": "Standard Double",
            "check_in": "2026-09-05",
            "check_out": "2026-09-07",
            "guest_name": "Test Iter607",
            "guest_email": "iter607@example.com",
            "rate": 1,
            "pay_now": False,
            "channel_source": "ota_banner:Expedia",
            "lang": "de",
        }
        r = requests.post(f"{API}/booking-widget/book", json=book_payload, timeout=25)
        assert r.status_code == 200, r.text[:400]
        data = r.json()
        booking = data.get("booking") or data
        assert booking.get("channel_source") == "ota_banner:Expedia", f"channel_source={booking.get('channel_source')}"
        assert booking.get("guest_lang") == "de", f"guest_lang={booking.get('guest_lang')}"

        # 3. Auth conversion report for property
        r = admin_session.get(f"{API}/booking-widget/ota-conversion/default?days=30", timeout=20)
        assert r.status_code == 200, r.text[:400]
        rep = r.json()
        assert rep.get("banner_views", 0) >= 1, f"banner_views={rep.get('banner_views')}"
        assert rep.get("bookings", 0) >= 1, f"bookings={rep.get('bookings')}"
        by_ota = rep.get("by_ota") or {}
        # by_ota might be dict or list
        if isinstance(by_ota, dict):
            assert any("Expedia" in k for k in by_ota.keys()), f"Expedia missing in {by_ota}"
        else:
            assert any("Expedia" in str(x) for x in by_ota), f"Expedia missing in {by_ota}"
        assert (rep.get("commission_saved") or 0) > 0, f"commission_saved={rep.get('commission_saved')}"

        # 4. /all works
        r = admin_session.get(f"{API}/booking-widget/ota-conversion/all?days=30", timeout=20)
        assert r.status_code == 200, r.text[:300]

    def test_cleanup(self, admin_session):
        # Delete the test booking directly via mongo
        try:
            import pymongo
            client = pymongo.MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
            db = client[os.environ.get("DB_NAME", "test_database")]
            res = db.bookings.delete_many({"guest_email": "iter607@example.com"})
            print(f"Cleanup: deleted {res.deleted_count} bookings")
        except Exception as e:
            print(f"Cleanup warning: {e}")


# ---------------- Ramp Ladder config ----------------
class TestRampLadderConfig:
    def test_put_get_config_and_scan(self, admin_session):
        # Change config
        r = admin_session.put(
            f"{API}/ramp-ladder/default/config",
            json={"event_premium": False, "event_min_score": 75},
            timeout=15,
        )
        assert r.status_code == 200, r.text[:300]

        r = admin_session.get(f"{API}/ramp-ladder/default", timeout=15)
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        cfg = data.get("config") or data
        # find event_premium and event_min_score anywhere
        def find(o, key):
            if isinstance(o, dict):
                if key in o:
                    return o[key]
                for v in o.values():
                    x = find(v, key)
                    if x is not None:
                        return x
            elif isinstance(o, list):
                for v in o:
                    x = find(v, key)
                    if x is not None:
                        return x
            return None
        ep = find(data, "event_premium")
        ems = find(data, "event_min_score")
        assert ep is False, f"event_premium={ep}"
        assert ems == 75, f"event_min_score={ems}"

        # Restore
        r = admin_session.put(
            f"{API}/ramp-ladder/default/config",
            json={"event_premium": True, "event_min_score": 60},
            timeout=15,
        )
        assert r.status_code == 200

        # Scan
        r = admin_session.post(f"{API}/ramp-ladder/default/scan?force=true", timeout=45)
        assert r.status_code == 200, r.text[:400]
        sd = r.json()
        assert "actions" in sd or "skips" in sd, f"missing actions/skips: keys={list(sd.keys())}"
