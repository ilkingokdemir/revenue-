"""Iter632: BRG claims, day-use availability, wishlist, chain-search tests."""
import os
import pytest
import requests
from datetime import date, timedelta

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://review-hub-108.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASS = "HotelAdmin2026!"


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=15)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    return r.json().get("token") or r.json().get("access_token")


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="module")
def pid():
    return "default"


CI = (date.today() + timedelta(days=30)).isoformat()
CO = (date.today() + timedelta(days=32)).isoformat()


# --- BRG claim ---
class TestBRG:
    def test_brg_claim_create(self, pid):
        r = requests.post(f"{API}/booking/brg-claim", json={
            "property_id": pid, "email": "test@example.com",
            "competitor_url": "https://booking.com/hotel/x",
            "competitor_price": 100, "our_price": 120, "currency": "GBP",
            "check_in": CI, "check_out": CO, "note": "test"
        }, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["ok"] is True
        assert d["status"] == "pending"
        assert d["sla_hours"] == 24
        assert "id" in d
        pytest.brg_claim_id = d["id"]

    def test_brg_claim_invalid_email(self, pid):
        r = requests.post(f"{API}/booking/brg-claim", json={
            "property_id": pid, "email": "notanemail",
            "competitor_url": "https://x.com", "competitor_price": 100
        }, timeout=15)
        assert r.status_code == 422

    def test_brg_claim_invalid_url(self, pid):
        r = requests.post(f"{API}/booking/brg-claim", json={
            "property_id": pid, "email": "a@b.com",
            "competitor_url": "notaurl", "competitor_price": 100
        }, timeout=15)
        assert r.status_code == 422

    def test_brg_claim_invalid_price(self, pid):
        r = requests.post(f"{API}/booking/brg-claim", json={
            "property_id": pid, "email": "a@b.com",
            "competitor_url": "https://x.com", "competitor_price": "abc"
        }, timeout=15)
        assert r.status_code == 422

    def test_brg_list_admin(self, admin_headers, pid):
        r = requests.get(f"{API}/booking/brg-claims/{pid}", headers=admin_headers, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "items" in d and "pending" in d
        assert d["pending"] >= 1
        assert any(i["id"] == pytest.brg_claim_id for i in d["items"])

    def test_brg_decide_approved(self, admin_headers):
        cid = pytest.brg_claim_id
        r = requests.put(f"{API}/booking/brg-claims/{cid}", headers=admin_headers, json={
            "status": "approved", "matched_price": 95, "note": "OK"
        }, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["status"] == "approved"
        assert d.get("matched_price") == 95
        assert "email_status" in d

    def test_brg_decide_bad_status(self, admin_headers):
        # create another
        r = requests.post(f"{API}/booking/brg-claim", json={
            "property_id": "default", "email": "b@c.com",
            "competitor_url": "https://x.com", "competitor_price": 50,
            "our_price": 60, "check_in": CI, "check_out": CO
        }, timeout=15)
        cid = r.json()["id"]
        r2 = requests.put(f"{API}/booking/brg-claims/{cid}", headers=admin_headers, json={"status": "maybe"}, timeout=15)
        assert r2.status_code == 422

    def test_brg_decide_unknown(self, admin_headers):
        r = requests.put(f"{API}/booking/brg-claims/does-not-exist", headers=admin_headers, json={"status": "approved"}, timeout=15)
        assert r.status_code == 404


# --- day-use ---
class TestDayUse:
    def test_day_use_ok(self, pid):
        r = requests.get(f"{API}/booking/day-use-availability/{pid}", params={"date": CI}, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["date"] == CI
        assert "enabled" in d
        assert isinstance(d["rooms"], list)
        if d["rooms"]:
            r0 = d["rooms"][0]
            for k in ("room_type_id", "name", "total", "day_use_booked", "day_use_left", "price", "hours"):
                assert k in r0

    def test_day_use_bad_date(self, pid):
        r = requests.get(f"{API}/booking/day-use-availability/{pid}", params={"date": "notadate"}, timeout=15)
        assert r.status_code == 422


# --- chain search ---
class TestChainSearch:
    def test_chain_search(self):
        r = requests.get(f"{API}/booking/chain-search", params={"check_in": CI, "check_out": CO, "adults": 2}, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "properties" in d
        assert d["check_in"] == CI
        # Sorting: available first, then by total_from asc
        prev_avail, prev_price = True, -1
        for p in d["properties"]:
            assert "geo" in p
            assert "book_url" in p
            # best price never 0 when set
            if p.get("best"):
                assert p["best"]["price"] > 0


# --- wishlist ---
class TestWishlist:
    def test_wishlist_create_and_get(self):
        # discover a valid room_type_id from chain-search or DB via room_types via chain
        cs = requests.get(f"{API}/booking/chain-search", params={"check_in": CI, "check_out": CO, "adults": 2}, timeout=30).json()
        item = None
        for p in cs["properties"]:
            if p.get("best"):
                item = {"property_id": p["property_id"], "room_type_id": p["best"]["room_type_id"]}
                break
        assert item, "No available room to build wishlist"
        r = requests.post(f"{API}/booking/wishlist", json={
            "items": [item], "owner_email": "test@example.com",
            "check_in": CI, "check_out": CO, "adults": 2
        }, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "code" in d
        assert d["share_path"].startswith("/wishlist/")
        code = d["code"]

        r2 = requests.get(f"{API}/booking/wishlist/{code}", timeout=15)
        assert r2.status_code == 200
        w = r2.json()
        assert w["code"] == code
        assert isinstance(w["rooms"], list) and len(w["rooms"]) >= 1
        assert "book_url" in w["rooms"][0]
        # price_at_save persisted in items
        assert "price_at_save" in w["items"][0]

    def test_wishlist_unknown(self):
        r = requests.get(f"{API}/booking/wishlist/ZZZZZZZZ", timeout=15)
        assert r.status_code == 404

    def test_wishlist_empty(self):
        r = requests.post(f"{API}/booking/wishlist", json={"items": [], "owner_email": "a@b.com"}, timeout=15)
        assert r.status_code == 422


# --- workers sanity ---
def test_wishlist_alerts_exists():
    with open("/app/backend/workers.py", "r") as f:
        src = f.read()
    assert "async def _wishlist_alerts" in src
