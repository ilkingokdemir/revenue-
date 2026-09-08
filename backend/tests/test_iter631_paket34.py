"""Iteration 631 / Paket34 BE-gap 2: chain-search, wishlist, day-use, BE settings."""
import os
import time
import requests
import pytest

BASE = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE}/api"

ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


# ---- Chain search ----
class TestChainSearch:
    def test_chain_ok(self):
        r = requests.get(f"{API}/booking/chain-search", params={"check_in": "2027-06-01", "check_out": "2027-06-03", "adults": 2})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["nights"] == 2
        assert len(d["properties"]) >= 1
        # sorted: available first
        seen_unavail = False
        for p in d["properties"]:
            assert "book_url" in p and "check_in=2027-06-01" in p["book_url"]
            assert "best" in p and "total_from" in p
            if p["available"]:
                assert seen_unavail is False, "available property after an unavailable one"
                assert p["best"] is not None
                assert "room_name" in p["best"] and "price" in p["best"] and "rooms_left" in p["best"]
            else:
                seen_unavail = True
        # sortedness for available block: available first, then price ascending (skip 0.0 fallback)
        avail = [p for p in d["properties"] if p["available"]]
        totals = [p["total_from"] for p in avail if p["total_from"]]
        assert totals == sorted(totals)

    def test_chain_high_adults(self):
        r = requests.get(f"{API}/booking/chain-search", params={"check_in": "2027-06-01", "check_out": "2027-06-03", "adults": 99})
        assert r.status_code == 200
        for p in r.json()["properties"]:
            assert p["available"] is False
            assert p["best"] is None

    def test_chain_bad_date(self):
        r = requests.get(f"{API}/booking/chain-search", params={"check_in": "not-a-date", "check_out": "2027-06-03", "adults": 2})
        assert r.status_code == 422


# ---- Wishlist ----
class TestWishlist:
    @pytest.fixture(scope="class")
    def room_id(self):
        r = requests.get(f"{API}/booking/rooms/default", params={"check_in": "2027-06-10", "check_out": "2027-06-12", "adults": 2, "children": 0})
        assert r.status_code == 200
        data = r.json()
        rooms = data["rooms"] if isinstance(data, dict) and "rooms" in data else data
        assert rooms
        for rm in rooms:
            if rm.get("id"):
                return rm["id"]
        pytest.skip("no room id")

    def test_wishlist_flow(self, room_id):
        payload = {"items": [{"property_id": "default", "room_type_id": room_id}],
                   "check_in": "2027-06-10", "check_out": "2027-06-12", "adults": 2}
        r = requests.post(f"{API}/booking/wishlist", json=payload)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "code" in d and len(d["code"]) == 8
        assert d["share_path"] == f"/wishlist/{d['code']}"
        code = d["code"]

        # GET
        r1 = requests.get(f"{API}/booking/wishlist/{code}")
        assert r1.status_code == 200
        w = r1.json()
        assert w["rooms"][0]["book_url"].find("property=default") >= 0
        assert w["rooms"][0]["book_url"].find("room=") >= 0
        v1 = w["views"]

        # views should increment on subsequent GET (post-increment; check that value after 2nd get > after 1st)
        requests.get(f"{API}/booking/wishlist/{code}")
        r3 = requests.get(f"{API}/booking/wishlist/{code}")
        v3 = r3.json()["views"]
        assert v3 > v1

    def test_wishlist_unknown_404(self):
        r = requests.get(f"{API}/booking/wishlist/NOPENOPE")
        assert r.status_code == 404

    def test_wishlist_empty_422(self):
        r = requests.post(f"{API}/booking/wishlist", json={"items": [], "check_in": "2027-06-10", "check_out": "2027-06-12", "adults": 2})
        assert r.status_code == 422


# ---- Day-use ----
class TestDayUse:
    def test_settings_put_day_use(self, admin_headers):
        r = requests.put(f"{API}/booking/be-settings/default",
                         json={"day_use_enabled": True, "day_use_pct": 50, "day_use_start": "09:00", "day_use_end": "18:00"},
                         headers=admin_headers)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["day_use_enabled"] is True
        assert d["day_use_pct"] == 50
        assert d["day_use_start"] == "09:00"
        assert d["day_use_end"] == "18:00"

    def test_reserve_multi_day_use(self, admin_headers):
        # Fetch a room
        rr = requests.get(f"{API}/booking/rooms/default", params={"check_in": "2027-07-15", "check_out": "2027-07-17", "adults": 2, "children": 0})
        data = rr.json()
        rooms = data["rooms"] if isinstance(data, dict) and "rooms" in data else data
        room_id = None
        base_price = None
        for rm in rooms:
            if rm.get("id"):
                room_id = rm["id"]
                base_price = float(rm.get("base_price") or rm.get("price_per_night") or 0)
                break
        assert room_id
        payload = {
            "property_id": "default",
            "guest_name": "Day Use QA",
            "guest_email": "dayuseqa@example.com",
            "guest_phone": "+441111000000",
            "check_in": "2027-07-15",
            "check_out": "2027-07-17",
            "adults": 2,
            "children": 0,
            "day_use": True,
            "items": [{"room_type_id": room_id, "qty": 1}]
        }
        r = requests.post(f"{API}/booking/reserve-multi", json=payload)
        assert r.status_code == 200, r.text
        booking = r.json()
        ref = booking["booking_ref"]

        # Fetch directly from Mongo to avoid pagination
        from pymongo import MongoClient
        mc = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
        dbn = os.environ.get("DB_NAME", "test_database")
        match = mc[dbn].bookings.find_one({"booking_ref": ref})
        assert match, f"booking {ref} not found"
        assert match.get("day_use") is True
        assert match.get("check_out") == match.get("check_in")
        assert match.get("day_use_hours") == "09:00-18:00"
        cart_total = float(booking.get("cart_total") or 0)
        # 50% of room subtotal (approx). 2 nights * base_price -> 50% discount
        expected_sub = base_price * 2 * 0.5
        # allow VAT etc; check cart_total roughly ~ expected_sub
        assert cart_total > 0
        assert abs(cart_total - expected_sub) / max(expected_sub, 1) < 0.6, f"cart_total={cart_total}, expected~{expected_sub}"

    def test_restore_day_use(self, admin_headers):
        r = requests.put(f"{API}/booking/be-settings/default",
                         json={"day_use_start": "10:00", "day_use_end": "17:00"},
                         headers=admin_headers)
        assert r.status_code == 200
        d = r.json()
        assert d["day_use_start"] == "10:00"
        assert d["day_use_end"] == "17:00"
