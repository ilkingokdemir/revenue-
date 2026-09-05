"""Iter 621 backend tests: permission-matrix, permission-changes, location, hotel-ads geo,
journal calendar/resend, gift cards email (mocked)."""
import os, datetime as dt
import requests, pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"
PID = "aldgate-flats"


@pytest.fixture(scope="module")
def admin():
    s = requests.Session()
    s.headers["Content-Type"] = "application/json"
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, r.text
    tok = r.json().get("access_token") or r.json().get("token")
    s.headers["Authorization"] = f"Bearer {tok}"
    return s


# ---- Permission matrix ----
class TestPermissionMatrix:
    def test_matrix_all(self, admin):
        r = admin.get(f"{BASE_URL}/api/admin/permission-matrix?property_id=all")
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("properties", "modules", "actions", "roles", "rows"):
            assert k in d, f"missing {k}"
        assert isinstance(d["rows"], list) and len(d["rows"]) > 0
        row = d["rows"][0]
        for k in ("user_id", "name", "email", "role", "property_roles", "per_property"):
            assert k in row
        # Save admin row + non-admin row for later
        pytest.matrix_data = d

    def test_matrix_property_filter(self, admin):
        r = admin.get(f"{BASE_URL}/api/admin/permission-matrix?property_id={PID}")
        assert r.status_code == 200
        d = r.json()
        assert len(d["properties"]) == 1
        assert d["properties"][0].get("id") == PID or d["properties"][0].get("property_id") == PID

    def test_matrix_csv(self, admin):
        r = admin.get(f"{BASE_URL}/api/admin/permission-matrix.csv")
        assert r.status_code == 200, r.text
        ct = r.headers.get("content-type", "")
        assert "csv" in ct.lower(), ct
        cd = r.headers.get("content-disposition", "")
        assert "attachment" in cd.lower()
        first_line = r.text.splitlines()[0].lower()
        for col in ("user", "email", "role", "property"):
            assert col in first_line


# ---- Permission changes ----
class TestPermissionChanges:
    def test_history_and_trigger(self, admin):
        # get baseline count
        r0 = admin.get(f"{BASE_URL}/api/admin/permission-changes")
        assert r0.status_code == 200, r0.text
        base_items = r0.json().get("items", [])
        base_len = len(base_items)

        # pick a non-admin user
        mat = getattr(pytest, "matrix_data", None)
        if not mat:
            mat = admin.get(f"{BASE_URL}/api/admin/permission-matrix?property_id=all").json()
        non_admin_rows = [row for row in mat["rows"] if row.get("role") not in ("admin", "owner")]
        assert non_admin_rows, "no non-admin user to test"
        target = non_admin_rows[0]
        uid = target["user_id"]
        original_pr = target.get("property_roles") or {}

        # PUT property-roles change
        new_pr = dict(original_pr)
        new_pr[PID] = "receptionist"
        r1 = admin.put(f"{BASE_URL}/api/orgs/users/{uid}/property-roles", json={"property_roles": new_pr})
        assert r1.status_code in (200, 204), r1.text

        # verify new change entry
        r2 = admin.get(f"{BASE_URL}/api/admin/permission-changes")
        assert r2.status_code == 200
        items = r2.json().get("items", [])
        assert len(items) > base_len, "no new change recorded"
        newest = items[0]
        assert newest.get("field") in ("property_roles", "property-roles")
        assert newest.get("target_name") or newest.get("target_email")
        assert "before" in newest and "after" in newest

        # restore
        r3 = admin.put(f"{BASE_URL}/api/orgs/users/{uid}/property-roles", json={"property_roles": original_pr})
        assert r3.status_code in (200, 204)

        # no-op permissions change → no new entry
        role = target.get("role")
        if role:
            r4 = admin.get(f"{BASE_URL}/api/admin/permission-changes")
            len_before = len(r4.json().get("items", []))
            r5 = admin.put(f"{BASE_URL}/api/admin/users/{uid}/permissions", json={"role": role})
            assert r5.status_code in (200, 204), r5.text
            r6 = admin.get(f"{BASE_URL}/api/admin/permission-changes")
            len_after = len(r6.json().get("items", []))
            assert len_after == len_before, "no-op permission change should NOT log"


# ---- Property location ----
class TestPropertyLocation:
    def test_get_location(self, admin):
        r = admin.get(f"{BASE_URL}/api/properties/{PID}/location")
        assert r.status_code == 200, r.text
        d = r.json()
        assert abs(d.get("latitude", 0) - 51.5142) < 0.01
        assert abs(d.get("longitude", 0) - (-0.0755)) < 0.01

    def test_put_valid(self, admin):
        r = admin.put(f"{BASE_URL}/api/properties/{PID}/location",
                      json={"latitude": 51.5142, "longitude": -0.0755, "country_code": "GB"})
        assert r.status_code == 200, r.text

    def test_put_invalid_type(self, admin):
        r = admin.put(f"{BASE_URL}/api/properties/{PID}/location",
                      json={"latitude": "x", "longitude": 0})
        assert r.status_code == 422, r.status_code

    def test_put_out_of_range(self, admin):
        r = admin.put(f"{BASE_URL}/api/properties/{PID}/location",
                      json={"latitude": 99, "longitude": 0})
        assert r.status_code == 422, r.status_code

    def test_put_unknown_pid(self, admin):
        r = admin.put(f"{BASE_URL}/api/properties/no-such-pid-xyz/location",
                      json={"latitude": 10, "longitude": 10})
        assert r.status_code == 404, r.status_code

    def test_geocode(self, admin):
        r = admin.post(f"{BASE_URL}/api/properties/{PID}/geocode",
                       json={"query": "Aldgate High Street, London"})
        # Accept 502 (network blocked)
        assert r.status_code in (200, 502), r.status_code
        if r.status_code == 200:
            d = r.json()
            assert "latitude" in d and "longitude" in d

    def test_hotel_ads_status(self, admin):
        r = admin.get(f"{BASE_URL}/api/hotel-ads/status/{PID}")
        assert r.status_code == 200, r.text
        d = r.json()
        # geo check
        checks = d.get("checks") or d
        geo = None
        if isinstance(checks, dict):
            geo = checks.get("geo") or d.get("geo")
        if isinstance(geo, dict):
            assert geo.get("ok") is True
        assert d.get("ready") in (True, None) or d.get("ready") is True


# ---- Journal calendar ----
class TestJournalCalendar:
    def test_calendar_current_month(self, admin):
        month = dt.date.today().strftime("%Y-%m")
        r = admin.get(f"{BASE_URL}/api/accounting/journal/calendar/{PID}?month={month}")
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("month", "providers", "days", "counts", "resend_candidates"):
            assert k in d, f"missing {k}"
        assert isinstance(d["days"], list) and len(d["days"]) >= 28
        pytest.jc = d

    def test_calendar_invalid_month(self, admin):
        r = admin.get(f"{BASE_URL}/api/accounting/journal/calendar/{PID}?month=abc")
        assert r.status_code == 422, r.status_code

    def test_resend_yesterday(self, admin):
        y = (dt.date.today() - dt.timedelta(days=1)).isoformat()
        r = admin.post(f"{BASE_URL}/api/accounting/journal/resend/{PID}", json={"dates": [y]})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("ok") is True
        items = d.get("items") or []
        assert len(items) >= 1
        assert items[0].get("result", {}).get("ok") is True

        # cal reflects mock
        month = y[:7]
        r2 = admin.get(f"{BASE_URL}/api/accounting/journal/calendar/{PID}?month={month}")
        d2 = r2.json()
        day = next((x for x in d2["days"] if x["date"] == y), None)
        assert day is not None
        assert day["status"] in ("pushed", "mock"), day["status"]
        assert y not in (d2.get("resend_candidates") or [])

    def test_resend_empty(self, admin):
        r = admin.post(f"{BASE_URL}/api/accounting/journal/resend/{PID}", json={"dates": []})
        assert r.status_code == 422, r.status_code

    def test_resend_too_many(self, admin):
        dates = [(dt.date.today() - dt.timedelta(days=i)).isoformat() for i in range(1, 33)]
        r = admin.post(f"{BASE_URL}/api/accounting/journal/resend/{PID}", json={"dates": dates})
        assert r.status_code == 422, r.status_code


# ---- Gift cards email (mocked) ----
class TestGiftCards:
    def test_create_with_email(self, admin):
        r = admin.post(f"{BASE_URL}/api/gift-cards", json={
            "property_id": PID, "amount": 75,
            "recipient_name": "QA Rec", "recipient_email": "qa-rec@test.com",
            "purchaser_name": "QA Buyer", "message": "Test",
            "origin_url": "https://x.test",
        })
        assert r.status_code in (200, 201), r.text
        d = r.json()
        assert d.get("code")
        er = d.get("email_result") or {}
        assert er.get("recipient") == "mocked" or er.get("recipient")  # mocked value
        pytest.gc_id = d.get("id") or d.get("_id") or d.get("gift_card_id")
        pytest.gc_code = d.get("code")

    def test_list_shows_email_sent(self, admin):
        r = admin.get(f"{BASE_URL}/api/gift-cards")
        assert r.status_code == 200
        data = r.json()
        items = data if isinstance(data, list) else data.get("items", [])
        found = [c for c in items if c.get("code") == pytest.gc_code]
        assert found, "created gift card not in list"
        assert found[0].get("email_sent_at"), "email_sent_at not set"

    def test_resend_email(self, admin):
        gid = pytest.gc_id
        assert gid
        r = admin.post(f"{BASE_URL}/api/gift-cards/{gid}/resend-email",
                       json={"recipient_email": "qa-rec2@test.com"})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("ok") is True
        assert (d.get("result") or {}).get("recipient")

        # list reflects new recipient
        r2 = admin.get(f"{BASE_URL}/api/gift-cards")
        items = r2.json() if isinstance(r2.json(), list) else r2.json().get("items", [])
        found = [c for c in items if c.get("code") == pytest.gc_code]
        assert found and found[0].get("recipient_email") == "qa-rec2@test.com"

    def test_public_purchase_returns_stripe_url(self):
        r = requests.post(f"{BASE_URL}/api/booking/gift-cards/purchase", json={
            "property_id": PID, "amount": 50,
            "recipient_name": "Pub Rec", "recipient_email": "pub-rec@test.com",
            "purchaser_name": "Pub Buyer", "purchaser_email": "pub-buyer@test.com",
            "message": "hi", "origin_url": "https://x.test",
        })
        assert r.status_code in (200, 201), r.text
        d = r.json()
        assert d.get("url") or d.get("checkout_url") or d.get("stripe_url")
