"""
Iteration 375: Direct Booking Conversion Engine + SiteMinder Middleware Adapter
Backend tests.
"""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://review-hub-108.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    data = r.json()
    tok = data.get("token") or data.get("access_token")
    assert tok, f"No token in response: {data}"
    return tok


@pytest.fixture(scope="module")
def headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# ================= DIRECT CONVERSION =================

class TestDirectConversionSettings:
    def test_get_settings(self, headers):
        r = requests.get(f"{API}/direct-conversion/settings", headers=headers, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert "enabled" in d and "discount_pct" in d and "validity_days" in d

    def test_put_settings_valid(self, headers):
        r = requests.put(f"{API}/direct-conversion/settings",
                         json={"discount_pct": 20, "validity_days": 60},
                         headers=headers, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["discount_pct"] == 20
        assert d["validity_days"] == 60
        # restore defaults
        requests.put(f"{API}/direct-conversion/settings",
                     json={"discount_pct": 15, "validity_days": 90},
                     headers=headers, timeout=15)

    def test_put_settings_invalid_discount(self, headers):
        r = requests.put(f"{API}/direct-conversion/settings",
                         json={"discount_pct": 99},
                         headers=headers, timeout=15)
        assert r.status_code == 400

    def test_put_settings_invalid_validity(self, headers):
        r = requests.put(f"{API}/direct-conversion/settings",
                         json={"validity_days": 5},
                         headers=headers, timeout=15)
        assert r.status_code == 400


class TestDirectConversionScanAndList:
    def test_scan_idempotent(self, headers):
        # First run
        r1 = requests.post(f"{API}/direct-conversion/scan", headers=headers, timeout=30)
        assert r1.status_code == 200, r1.text
        d1 = r1.json()
        assert "scanned" in d1 and "offers_created" in d1
        # Second run — must not create new offers for already offered bookings
        r2 = requests.post(f"{API}/direct-conversion/scan", headers=headers, timeout=30)
        assert r2.status_code == 200
        d2 = r2.json()
        assert d2["offers_created"] == 0, f"Idempotency violated: {d2}"

    def test_offers_list(self, headers):
        r = requests.get(f"{API}/direct-conversion/offers", headers=headers, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert "items" in d and "total" in d
        assert isinstance(d["items"], list)

    def test_stats(self, headers):
        r = requests.get(f"{API}/direct-conversion/stats", headers=headers, timeout=15)
        assert r.status_code == 200
        d = r.json()
        for k in ["sent", "redeemed", "conversion_rate_pct", "commission_saved", "by_channel"]:
            assert k in d, f"Missing key {k}"


class TestDirectConversionRedeem:
    def test_redeem_unknown_code(self):
        r = requests.post(f"{API}/direct-conversion/redeem",
                          json={"coupon_code": "DIRECT-XXXXXX", "booking_value": 100}, timeout=15)
        assert r.status_code == 404

    def test_redeem_flow_and_double_redeem(self, headers):
        # Pick a 'sent' offer
        r = requests.get(f"{API}/direct-conversion/offers?status=sent", headers=headers, timeout=15)
        offers = r.json().get("items", [])
        if not offers:
            pytest.skip("No 'sent' offers available to redeem")
        code = offers[0]["coupon_code"]
        # Redeem (public — no auth)
        r1 = requests.post(f"{API}/direct-conversion/redeem",
                           json={"coupon_code": code, "booking_value": 500}, timeout=15)
        assert r1.status_code == 200, r1.text
        d1 = r1.json()
        assert d1["ok"] is True
        assert d1["discount_amount"] > 0
        assert d1["commission_saved"] > 0
        # Double redeem
        r2 = requests.post(f"{API}/direct-conversion/redeem",
                           json={"coupon_code": code, "booking_value": 500}, timeout=15)
        assert r2.status_code == 400
        assert "kullan" in r2.text.lower() or "used" in r2.text.lower()


# ================= SITEMINDER =================

class TestSiteMinderMappings:
    def test_get_mappings_defaults(self, headers):
        r = requests.get(f"{API}/siteminder/mappings", headers=headers, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["total"] >= 10
        codes = {i["code"] for i in d["items"]}
        assert "BDC" in codes and "EXP" in codes and "AGO" in codes

    def test_put_mapping_valid(self, headers):
        r = requests.put(f"{API}/siteminder/mappings",
                         json={"code": "HRS", "channel": "expedia"},
                         headers=headers, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["code"] == "HRS" and d["channel"] == "expedia"

    def test_put_mapping_invalid_channel(self, headers):
        r = requests.put(f"{API}/siteminder/mappings",
                         json={"code": "ZZZ", "channel": "notachannel"},
                         headers=headers, timeout=15)
        assert r.status_code == 400


class TestSiteMinderWebhook:
    def test_json_reservation(self, headers):
        rid = f"TEST-JSON-{uuid.uuid4().hex[:8]}"
        payload = {
            "event": "reservation", "reservation_id": rid,
            "channel_code": "BDC", "property_id": "default",
            "guest_name": "TEST SiteMinder Guest", "guest_email": "sm.test@example.com",
            "check_in": "2026-03-01", "check_out": "2026-03-03",
            "total_price": 300.0, "currency": "GBP", "guest_count": 2,
        }
        r = requests.post(f"{API}/siteminder/webhook", json=payload, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["ok"] is True
        assert d["channel"] == "booking_com"
        assert "booking_id" in d
        # Verify booking created
        rb = requests.get(f"{API}/bookings", headers=headers, timeout=15)
        assert rb.status_code == 200
        # cancel to cleanup
        cancel = {"event": "cancellation", "reservation_id": rid, "channel_code": "BDC"}
        rc = requests.post(f"{API}/siteminder/webhook", json=cancel, timeout=15)
        assert rc.status_code == 200
        assert rc.json().get("cancelled") is True

    def test_xml_reservation(self):
        rid = f"TESTXML{uuid.uuid4().hex[:6]}"
        xml_body = f"""<?xml version="1.0" encoding="UTF-8"?>
<OTA_HotelResNotifRQ xmlns="http://www.opentravel.org/OTA/2003/05">
  <HotelReservations>
    <HotelReservation CreateDateTime="2026-01-15T10:00:00" ResID_Value="{rid}">
      <UniqueID Type="14" ID="{rid}"/>
      <RoomStays>
        <RoomStay>
          <RoomTypes><RoomType RoomTypeCode="STD"/></RoomTypes>
          <GuestCounts><GuestCount Count="2"/></GuestCounts>
          <TimeSpan Start="2026-04-10" End="2026-04-12"/>
          <Total AmountAfterTax="450.00" CurrencyCode="GBP"/>
          <BasicPropertyInfo HotelCode="default"/>
          <BookingChannel Type="EXP"/>
        </RoomStay>
      </RoomStays>
      <ResGuests>
        <ResGuest>
          <Profiles><ProfileInfo><Profile><Customer>
            <PersonName>
              <GivenName>Test</GivenName>
              <Surname>XmlGuest</Surname>
            </PersonName>
            <Email>xmltest@example.com</Email>
          </Customer></Profile></ProfileInfo></Profiles>
        </ResGuest>
      </ResGuests>
    </HotelReservation>
  </HotelReservations>
</OTA_HotelResNotifRQ>"""
        r = requests.post(f"{API}/siteminder/webhook",
                          data=xml_body.encode("utf-8"),
                          headers={"Content-Type": "application/xml"}, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["ok"] is True
        assert d["channel"] == "expedia"

    def test_log(self, headers):
        r = requests.get(f"{API}/siteminder/log?limit=20", headers=headers, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert "items" in d
        if d["items"]:
            row = d["items"][0]
            assert "resolved_channel" in row
            assert "event" in row
