"""Iter 623 - Paket 26: unified pricing, member rate, LOS, translations/posts/analytics/brand, spam/rate-limit."""
import os
import re
import time
import pytest
import requests
from datetime import date, timedelta
from pymongo import MongoClient

def _read_env(key, path="/app/frontend/.env"):
    try:
        with open(path) as f:
            for line in f:
                if line.startswith(key + "="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    except Exception:
        return None
    return None

BASE = (os.environ.get("REACT_APP_BACKEND_URL") or _read_env("REACT_APP_BACKEND_URL")).rstrip("/")
API = f"{BASE}/api"
PID = "aldgate-flats"
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PW = "HotelAdmin2026!"

MONGO_URL = "mongodb://localhost:27017"
DB_NAME = "test_database"


@pytest.fixture(scope="module")
def db():
    c = MongoClient(MONGO_URL)
    return c[DB_NAME]


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PW}, timeout=15)
    assert r.status_code == 200, r.text
    return r.json().get("token") or r.json().get("access_token")


@pytest.fixture(scope="module")
def H(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="module")
def dates():
    ci = (date.today() + timedelta(days=15)).isoformat()
    co = (date.today() + timedelta(days=17)).isoformat()
    return ci, co


# ---------- unified pricing ----------

def test_rooms_have_nightly_and_explanation(dates):
    ci, co = dates
    r = requests.get(f"{API}/booking/rooms/{PID}", params={"check_in": ci, "check_out": co, "adults": 2}, timeout=20)
    assert r.status_code == 200, r.text
    rooms = r.json()
    assert isinstance(rooms, list) and len(rooms) > 0
    room = next((x for x in rooms if x["id"] == "double-aldgate-flats"), rooms[0])
    assert "nightly" in room and isinstance(room["nightly"], list)
    n0 = room["nightly"][0]
    for k in ("date", "rate", "source", "base"):
        assert k in n0, f"nightly missing {k}"
    assert "stay_total" in room and "avg_nightly" in room
    pe = room["price_explanation"]
    for k in ("vs_base_pct", "headline_tr", "headline_en", "headline_de", "drivers"):
        assert k in pe
    for k in ("vat_rate", "city_tax_per_night", "extra_bed_price", "child_policy"):
        assert k in room


def test_rooms_stay_total_matches_widget(dates):
    """Compare unified rooms endpoint to widget search endpoint."""
    ci, co = dates
    r1 = requests.get(f"{API}/booking/rooms/{PID}", params={"check_in": ci, "check_out": co, "adults": 2}, timeout=20)
    assert r1.status_code == 200
    rooms = r1.json()
    r2 = requests.get(f"{API}/booking-widget/{PID}/search", params={"check_in": ci, "check_out": co, "adults": 2}, timeout=20)
    if r2.status_code != 200:
        pytest.skip(f"widget search not available: {r2.status_code}")
    w = r2.json()
    # widget shapes vary; do a lenient nightly total comparison per room id if possible
    widget_rooms = w.get("rooms") or w.get("results") or []
    if not widget_rooms:
        pytest.skip("widget returned no rooms to compare")
    by_id = {r["id"]: r for r in rooms if r.get("id")}
    matched = 0
    for wr in widget_rooms:
        rid = wr.get("id") or wr.get("room_type_id")
        if rid in by_id:
            wt = wr.get("stay_total") or wr.get("total") or wr.get("total_price")
            if wt:
                assert abs(float(wt) - by_id[rid]["stay_total"]) < 0.02, f"mismatch for {rid}: widget={wt} rooms={by_id[rid]['stay_total']}"
                matched += 1
    assert matched >= 1, "no room totals compared"


def test_price_calendar_current_month():
    m = date.today().strftime("%Y-%m")
    r = requests.get(f"{API}/booking/price-calendar/{PID}", params={"month": m}, timeout=15)
    assert r.status_code == 200, r.text
    j = r.json()
    assert "min_price" in j and "max_price" in j


# ---------- pricing settings + reserve-multi taxes/extra bed/children/member ----------

def test_pricing_settings_put_and_get(H):
    payload = {"vat_rate": 20, "city_tax_per_night": 2, "extra_bed_price": 15,
               "child_policy": {"free_under_age": 3, "child_price_per_night": 10, "max_child_age": 12}}
    r = requests.put(f"{API}/booking/pricing-settings/{PID}", json=payload, headers=H, timeout=15)
    assert r.status_code == 200, r.text
    r = requests.get(f"{API}/booking/pricing-settings/{PID}", headers=H, timeout=15)
    assert r.status_code == 200
    j = r.json()
    assert j["vat_rate"] == 20 and j["city_tax_per_night"] == 2 and j["extra_bed_price"] == 15
    assert j["child_policy"]["child_price_per_night"] == 10


def test_reserve_multi_taxes_extra_bed_children_baseline(H, dates):
    ci, co = dates
    # Ensure pricing settings applied
    requests.put(f"{API}/booking/pricing-settings/{PID}",
                 json={"vat_rate": 20, "city_tax_per_night": 2, "extra_bed_price": 15,
                       "child_policy": {"free_under_age": 3, "child_price_per_night": 10, "max_child_age": 12}},
                 headers=H, timeout=15)
    nights = 2
    # first get the room stay_total (member off)
    rr = requests.get(f"{API}/booking/rooms/{PID}", params={"check_in": ci, "check_out": co, "adults": 2}, timeout=20).json()
    room = next(x for x in rr if x["id"] == "double-aldgate-flats")
    stay_total = room["stay_total"]
    plan_id = "flexible"
    body = {"property_id": PID, "check_in": ci, "check_out": co, "adults": 2, "children": 2,
            "guest_name": "TEST Base Guest", "guest_email": "test.base@example.com", "guest_phone": "+441111",
            "items": [{"room_type_id": "double-aldgate-flats", "rate_plan_id": plan_id, "qty": 1,
                       "extra_beds": 1, "children_ages": [2, 8]}]}
    r = requests.post(f"{API}/booking/reserve-multi", json=body, timeout=20)
    assert r.status_code == 200, r.text
    j = r.json()
    tb = j["tax_breakdown"]
    assert tb["vat_rate"] == 20 and tb["vat_included"] > 0
    assert abs(tb["city_tax"] - (2 * nights * 1)) < 0.01
    # total = stay_total (subtotal for flexible = stay_total*mult, assume flexible has no mult) + extra_bed 15*2 + child(8) 10*2 + city_tax(2*2)
    # child aged 2 free (<3), child aged 8 charged
    expected_min = stay_total + 15 * nights + 10 * nights + 2 * nights
    # not accounting for potential plan adjustments; check reasonable
    assert j["subtotal"] >= stay_total + 15 * nights + 10 * nights - 1
    assert j["total_price"] >= expected_min - 2
    assert j.get("manage_url", "").startswith("/guest-portal-v2?ref=")


def test_reserve_multi_reflects_stay_total_not_base(dates):
    """total ≠ base_price*nights when RMS overrides exist (approximate check via room.stay_total)."""
    ci, co = dates
    rr = requests.get(f"{API}/booking/rooms/{PID}", params={"check_in": ci, "check_out": co, "adults": 2}, timeout=20).json()
    room = next(x for x in rr if x["id"] == "double-aldgate-flats")
    stay_total = room["stay_total"]
    body = {"property_id": PID, "check_in": ci, "check_out": co, "adults": 2, "children": 0,
            "guest_name": "TEST Nobed", "guest_email": "test.nobed@example.com", "guest_phone": "+441111",
            "items": [{"room_type_id": "double-aldgate-flats", "rate_plan_id": "flexible", "qty": 1}]}
    r = requests.post(f"{API}/booking/reserve-multi", json=body, timeout=20)
    assert r.status_code == 200, r.text
    j = r.json()
    # subtotal (before city tax/vat effect) should equal stay_total approx
    assert abs(j["subtotal"] - stay_total) < 0.5, f"subtotal {j['subtotal']} vs stay_total {stay_total}"


# ---------- member rate ----------

def test_member_rate_no_member():
    r = requests.post(f"{API}/booking/member-rate", json={"email": "nobody@x.com"}, timeout=10)
    assert r.status_code == 200
    j = r.json()
    assert j["member"] is False


def test_member_rate_gold_member_and_reserve_discount(db, dates):
    ci, co = dates
    db.loyalty_members.delete_many({"email": "gold@test.com"})
    db.loyalty_members.insert_one({"email": "gold@test.com", "tier": "gold", "name": "Gold QA"})
    try:
        r = requests.post(f"{API}/booking/member-rate", json={"email": "gold@test.com"}, timeout=10)
        assert r.status_code == 200
        j = r.json()
        assert j["member"] is True and j["discount_pct"] == 10

        base_body = {"property_id": PID, "check_in": ci, "check_out": co, "adults": 2, "children": 0,
                     "guest_name": "TEST NoMember", "guest_email": "test.nomember@example.com", "guest_phone": "+441111",
                     "items": [{"room_type_id": "double-aldgate-flats", "rate_plan_id": "flexible", "qty": 1}]}
        r1 = requests.post(f"{API}/booking/reserve-multi", json=base_body, timeout=20).json()

        mem_body = dict(base_body, guest_email="test.member@example.com", guest_name="TEST Member", loyalty_email="gold@test.com")
        r2 = requests.post(f"{API}/booking/reserve-multi", json=mem_body, timeout=20).json()
        assert r2.get("member_discount_pct") == 10
        # 10% lower — city tax stays constant, so approximate check
        assert r2["subtotal"] < r1["subtotal"], f"member subtotal {r2['subtotal']} not < {r1['subtotal']}"
        # roughly 10% reduction on subtotal (approx, since discount is on nightly not on tax additions)
        ratio = r2["subtotal"] / r1["subtotal"]
        assert 0.87 < ratio < 0.94, f"ratio {ratio}"
        assert r2["manage_url"].startswith("/guest-portal-v2?ref=")
    finally:
        db.loyalty_members.delete_many({"email": "gold@test.com"})


# ---------- LOS restrictions ----------

def test_los_blocks_1_night(db):
    db.los_restrictions.delete_many({"property_id": PID, "type": "min_stay", "value": 3})
    db.los_restrictions.insert_one({"property_id": PID, "type": "min_stay", "value": 3, "enabled": True})
    try:
        ci = (date.today() + timedelta(days=20)).isoformat()
        co = (date.today() + timedelta(days=21)).isoformat()
        r = requests.get(f"{API}/booking/rooms/{PID}", params={"check_in": ci, "check_out": co, "adults": 2}, timeout=15)
        assert r.status_code == 200
        rooms = r.json()
        blocked = [x for x in rooms if x.get("los_block")]
        assert blocked, "expected los_block on rooms for 1-night search"
        assert all(x["is_available"] is False for x in blocked)
        body = {"property_id": PID, "check_in": ci, "check_out": co, "adults": 2, "children": 0,
                "guest_name": "TEST Los", "guest_email": "test.los@example.com", "guest_phone": "+441111",
                "items": [{"room_type_id": "double-aldgate-flats", "rate_plan_id": "flexible", "qty": 1}]}
        r2 = requests.post(f"{API}/booking/reserve-multi", json=body, timeout=15)
        assert r2.status_code == 400, r2.text
    finally:
        db.los_restrictions.delete_many({"property_id": PID, "type": "min_stay", "value": 3})


# ---------- site builder translations/posts/analytics/brand ----------

@pytest.fixture(scope="module")
def saved_site(H):
    # get existing to preserve
    r = requests.get(f"{API}/site-builder/{PID}", headers=H, timeout=15)
    assert r.status_code == 200
    cfg = r.json()["site"]
    prev_content = cfg.get("content") or {}
    prev_content_copy = dict(prev_content)
    new_content = dict(prev_content)
    new_content["translations"] = {
        "en": {"headline": "A calm escape", "about": "English about text", "seo_title": "Aldgate Flats EN"},
        "de": {"headline": "Ruhige Oase"},
    }
    new_content["posts"] = [{"title": "Yaz Kampanyası %20", "excerpt": "Erken rezervasyon", "body": "Detaylar…",
                             "type": "campaign", "date": "2026-09-01", "published": True,
                             "cta_url": f"/book?property={PID}"}]
    new_content["analytics"] = {"ga4_id": "G-TEST12345", "gtm_id": "GTM-QA1", "pixel_id": "123456"}
    new_content["brand"] = {"accent": "#b45309", "radius": "8px"}
    pe = list(new_content.get("pages_enabled") or ["home", "rooms", "gallery", "reviews", "contact"])
    if "blog" not in pe:
        pe.append("blog")
    new_content["pages_enabled"] = pe
    payload = {"template": "coastal", "published": True, "content": new_content, "mode": cfg.get("mode", "simple")}
    r = requests.post(f"{API}/site-builder/{PID}", json=payload, headers=H, timeout=15)
    assert r.status_code == 200, r.text
    yield
    # keep site published as spec says, but reset brand accent
    prev_content_copy["brand"] = {}
    r = requests.post(f"{API}/site-builder/{PID}", json={"template": "coastal", "published": True,
                                                         "content": {**new_content, "brand": {}}}, headers=H, timeout=15)


def test_public_site_has_translations_posts_analytics(saved_site):
    r = requests.get(f"{API}/site-builder/public/site/{PID}", timeout=15)
    assert r.status_code == 200, r.text
    j = r.json()
    c = j["site"]["content"]
    assert c["translations"]["en"]["headline"] == "A calm escape"
    assert c["posts"] and c["posts"][0]["slug"]
    assert "yaz-kampanyasi-20" in c["posts"][0]["slug"] or "yaz" in c["posts"][0]["slug"]
    an = c["analytics"]
    assert an["ga4_id"] == "G-TEST12345"
    assert c["brand"]["accent"] == "#b45309"


def test_invalid_brand_accent_dropped(H, saved_site):
    r = requests.get(f"{API}/site-builder/{PID}", headers=H, timeout=15)
    content = r.json()["site"]["content"]
    content["brand"] = {"accent": "red", "radius": "8px"}
    r = requests.post(f"{API}/site-builder/{PID}",
                      json={"template": "coastal", "published": True, "content": content}, headers=H, timeout=15)
    assert r.status_code == 200
    r = requests.get(f"{API}/site-builder/public/site/{PID}", timeout=15)
    br = r.json()["site"]["content"]["brand"]
    assert "accent" not in br or br.get("accent") != "red"
    # restore
    content["brand"] = {"accent": "#b45309", "radius": "8px"}
    requests.post(f"{API}/site-builder/{PID}",
                  json={"template": "coastal", "published": True, "content": content}, headers=H, timeout=15)


def test_public_analytics_endpoint(saved_site):
    r = requests.get(f"{API}/site-builder/public/analytics/{PID}", timeout=10)
    assert r.status_code == 200
    j = r.json()
    assert j["analytics"]["ga4_id"] == "G-TEST12345"
    assert j["brand"]["accent"] == "#b45309"


def test_sitemap_xml(saved_site):
    r = requests.get(f"{API}/site-builder/public/sitemap/{PID}.xml", timeout=10)
    assert r.status_code == 200, r.text
    body = r.text
    assert f"/site/{PID}" in body
    assert "/rooms/" in body
    assert "/blog/" in body
    assert 'hreflang="tr"' in body and 'hreflang="en"' in body and 'hreflang="de"' in body


def test_robots_txt(saved_site):
    r = requests.get(f"{API}/site-builder/public/robots/{PID}.txt", timeout=10)
    assert r.status_code == 200
    assert "Sitemap:" in r.text


# ---------- contact spam / rate-limit ----------

def test_contact_honeypot_ignored(H):
    before = requests.get(f"{API}/site-builder/{PID}/inquiries", headers=H, timeout=10).json().get("items", [])
    r = requests.post(f"{API}/site-builder/public/contact",
                      json={"property_id": PID, "name": "Spam", "email": "s@s.com",
                            "message": "hello there message", "website": "http://spam"}, timeout=10)
    assert r.status_code == 200
    assert r.json().get("id") == "spam-ignored"
    after = requests.get(f"{API}/site-builder/{PID}/inquiries", headers=H, timeout=10).json().get("items", [])
    assert len(after) == len(before), "honeypot should not create inquiry"


def test_contact_rate_limit_429():
    # code allows 5 per hour, so 6th should 429
    payload = {"property_id": PID, "name": "RL", "email": "rl@t.com", "message": "hello valid message"}
    statuses = []
    for i in range(6):
        r = requests.post(f"{API}/site-builder/public/contact", json=payload, timeout=10)
        statuses.append(r.status_code)
        time.sleep(0.05)
    # last should be 429; earlier at least one 200
    assert 429 in statuses, f"expected 429 in {statuses}"


# ---------- teardown pricing settings ----------

def test_zzz_restore_pricing_settings(H):
    r = requests.put(f"{API}/booking/pricing-settings/{PID}",
                     json={"vat_rate": 0, "city_tax_per_night": 0, "extra_bed_price": 0,
                           "child_policy": {"free_under_age": 0, "child_price_per_night": 0, "max_child_age": 12}},
                     headers=H, timeout=10)
    assert r.status_code == 200
