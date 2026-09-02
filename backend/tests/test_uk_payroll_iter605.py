"""Iteration 605 backend tests: SMP/SPP, leave cancellation, payroll lock/correction,
booking widget dynamic pricing/LOS/price-explain, ramp ladder forecast toggle."""
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for ln in f:
            if ln.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = ln.split("=", 1)[1].strip().rstrip("/")

ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASS = "HotelAdmin2026!"
FATMA_ID = "52c4271e-e333-4dec-958d-d6220482e9f6"


@pytest.fixture(scope="module")
def s():
    sess = requests.Session()
    r = sess.post(f"{BASE_URL}/api/auth/login",
                  json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=60)
    assert r.status_code == 200, f"login failed: {r.text}"
    return sess


# =========================================================
# A. Parental Leave (SMP)
# =========================================================
class TestParentalLeaveSMP:
    created_ids = []

    def test_awe_below_lel_returns_400(self, s):
        r = s.post(
            f"{BASE_URL}/api/uk-payroll/employees/{FATMA_ID}/parental-leave",
            json={"type": "maternity", "start_date": "2026-06-08", "awe": 100},
            timeout=30,
        )
        assert r.status_code == 400, r.text

    def test_create_maternity_leave(self, s):
        r = s.post(
            f"{BASE_URL}/api/uk-payroll/employees/{FATMA_ID}/parental-leave",
            json={"type": "maternity", "start_date": "2026-06-08", "awe": 400},
            timeout=30,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("total_weeks") == 39
        assert abs(data.get("weekly_first", 0) - 360.0) < 0.5
        assert abs(data.get("weekly_standard", 0) - 194.32) < 0.5
        assert abs(data.get("total_pay", 0) - 8572.56) < 5.0
        pid = data.get("id") or data.get("parental_leave_id")
        assert pid
        TestParentalLeaveSMP.created_ids.append(pid)

    def test_duplicate_active_leave_conflict(self, s):
        r = s.post(
            f"{BASE_URL}/api/uk-payroll/employees/{FATMA_ID}/parental-leave",
            json={"type": "maternity", "start_date": "2026-06-08", "awe": 400},
            timeout=30,
        )
        assert r.status_code == 409, r.text

    def test_preview_june_smp(self, s):
        r = s.get(f"{BASE_URL}/api/uk-payroll/preview/all?year=2026&month=6", timeout=45)
        assert r.status_code == 200, r.text
        payload = r.json()
        rows = payload.get("rows") or payload.get("data") or payload
        if isinstance(rows, dict) and "rows" in rows:
            rows = rows["rows"]
        # find fatma
        fatma = None
        for row in rows if isinstance(rows, list) else []:
            if row.get("staff_id") == FATMA_ID or "fatma" in (row.get("name") or row.get("staff_name") or "").lower():
                fatma = row
                break
        assert fatma, f"Fatma row missing. rows: {rows}"
        smp = fatma.get("smp") or fatma.get("SMP") or 0
        assert abs(smp - 1440.0) < 10.0, f"expected ~1440 got {smp}"
        assert (fatma.get("smp_type") or "").lower() == "maternity"
        totals = payload.get("totals") or {}
        assert "smp" in totals
        assert "smp_recovery" in totals

    def test_preview_july_smp(self, s):
        r = s.get(f"{BASE_URL}/api/uk-payroll/preview/all?year=2026&month=7", timeout=45)
        assert r.status_code == 200
        payload = r.json()
        rows = payload.get("rows") or payload
        if isinstance(rows, dict) and "rows" in rows:
            rows = rows["rows"]
        fatma = None
        for row in rows if isinstance(rows, list) else []:
            if row.get("staff_id") == FATMA_ID or "fatma" in (row.get("name") or row.get("staff_name") or "").lower():
                fatma = row
                break
        assert fatma
        smp = fatma.get("smp") or 0
        assert abs(smp - 1108.64) < 15.0, f"expected ~1108.64 got {smp}"

    def test_list_parental_leaves(self, s):
        r = s.get(f"{BASE_URL}/api/uk-payroll/parental-leave/all", timeout=30)
        assert r.status_code == 200
        lst = r.json()
        assert any((it.get("id") in TestParentalLeaveSMP.created_ids) for it in (lst if isinstance(lst, list) else lst.get("items", [])))

    def test_zzz_end_parental_leave(self, s):
        for pid in TestParentalLeaveSMP.created_ids:
            r = s.delete(f"{BASE_URL}/api/uk-payroll/parental-leave/{pid}", timeout=30)
            assert r.status_code in (200, 204), r.text
            if r.status_code == 200 and r.headers.get("content-type", "").startswith("application/json"):
                body = r.json()
                if isinstance(body, dict) and body.get("status"):
                    assert body["status"] == "ended"


# =========================================================
# B. Leave cancellation
# =========================================================
class TestLeaveCancellation:
    hr_restored = False

    @classmethod
    def teardown_class(cls):
        # ensure HR email restored
        try:
            sess = requests.Session()
            sess.post(f"{BASE_URL}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=30)
            sess.put(f"{BASE_URL}/api/uk-payroll/employees/{FATMA_ID}/hr",
                     json={"email": ""}, timeout=30)
        except Exception:
            pass

    def test_link_admin_email_to_fatma(self, s):
        r = s.put(f"{BASE_URL}/api/uk-payroll/employees/{FATMA_ID}/hr",
                  json={"email": ADMIN_EMAIL}, timeout=30)
        assert r.status_code == 200, r.text

    def test_pending_cancel_immediate(self, s):
        r = s.post(f"{BASE_URL}/api/uk-payroll/me/leave-request",
                   json={"leave_type": "annual",
                         "start_date": "2026-11-02", "end_date": "2026-11-03"},
                   timeout=30)
        assert r.status_code == 200, r.text
        lid = r.json().get("id") or r.json().get("leave_id")
        assert lid
        rc = s.post(f"{BASE_URL}/api/uk-payroll/me/leaves/{lid}/cancel", timeout=30)
        assert rc.status_code == 200, rc.text
        assert (rc.json().get("status") or "").lower() == "cancelled"

        # cancel again -> 400
        rc2 = s.post(f"{BASE_URL}/api/uk-payroll/me/leaves/{lid}/cancel", timeout=30)
        assert rc2.status_code == 400

    def test_approved_cancel_flow(self, s):
        # get balance before
        b0 = s.get(f"{BASE_URL}/api/uk-payroll/me/leave-balance", timeout=30).json()
        used0 = b0.get("used", b0.get("annual", {}).get("used", 0)) if isinstance(b0, dict) else 0

        # Create a leave
        r = s.post(f"{BASE_URL}/api/uk-payroll/me/leave-request",
                   json={"leave_type": "annual",
                         "start_date": "2026-11-16", "end_date": "2026-11-17"},
                   timeout=30)
        assert r.status_code == 200, r.text
        lid = r.json().get("id") or r.json().get("leave_id")

        # Approve
        ra = s.put(f"{BASE_URL}/api/shifts/leaves/{lid}",
                   json={"status": "approved"}, timeout=30)
        assert ra.status_code == 200, ra.text

        # Cancel -> cancel_requested
        rc = s.post(f"{BASE_URL}/api/uk-payroll/me/leaves/{lid}/cancel", timeout=30)
        assert rc.status_code == 200, rc.text
        assert (rc.json().get("status") or "").lower() == "cancel_requested"

        # Balance still counts
        b1 = s.get(f"{BASE_URL}/api/uk-payroll/me/leave-balance", timeout=30).json()
        used1 = b1.get("used", b1.get("annual", {}).get("used", 0)) if isinstance(b1, dict) else 0
        assert used1 >= used0

        # Listed
        rlist = s.get(f"{BASE_URL}/api/shifts/leaves/all?status=cancel_requested", timeout=30)
        assert rlist.status_code == 200
        items = rlist.json()
        assert any((it.get("id") == lid) for it in (items if isinstance(items, list) else items.get("items", [])))

        # Decide approve
        rd = s.post(f"{BASE_URL}/api/uk-payroll/leaves/{lid}/cancel-decision",
                    json={"approve": True}, timeout=30)
        assert rd.status_code == 200, rd.text
        assert (rd.json().get("status") or "").lower() == "cancelled"

        # Balance now decreased
        b2 = s.get(f"{BASE_URL}/api/uk-payroll/me/leave-balance", timeout=30).json()
        used2 = b2.get("used", b2.get("annual", {}).get("used", 0)) if isinstance(b2, dict) else 0
        assert used2 <= used1


# =========================================================
# C. Payroll lock + correction + unlock
# =========================================================
class TestPayrollLock:
    run_id = None
    correction_id = None

    def test_run_all_locks(self, s):
        r = s.post(f"{BASE_URL}/api/uk-payroll/run/all",
                   json={"year": 2026, "month": 4, "force": True}, timeout=120)
        assert r.status_code == 200, r.text
        data = r.json()
        run = data.get("run") or data
        assert run.get("locked") in (True, "true") or run.get("locked") is True
        TestPayrollLock.run_id = run.get("id") or run.get("run_id") or run.get("_id")
        assert TestPayrollLock.run_id

    def test_rerun_blocked_423(self, s):
        r = s.post(f"{BASE_URL}/api/uk-payroll/run/all",
                   json={"year": 2026, "month": 4, "force": True}, timeout=60)
        assert r.status_code == 423, f"expected 423 got {r.status_code}: {r.text}"

    def test_correction_request_flow(self, s):
        rid = TestPayrollLock.run_id
        # short reason -> 400
        r_bad = s.post(f"{BASE_URL}/api/uk-payroll/runs/{rid}/correction-request",
                       json={"reason": "abc"}, timeout=30)
        assert r_bad.status_code == 400

        r = s.post(f"{BASE_URL}/api/uk-payroll/runs/{rid}/correction-request",
                   json={"reason": "test gerekçe"}, timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        cid = body.get("id") or body.get("correction_id")
        assert cid
        assert (body.get("status") or "").lower() == "pending"
        TestPayrollLock.correction_id = cid

        # duplicate -> 409
        rdup = s.post(f"{BASE_URL}/api/uk-payroll/runs/{rid}/correction-request",
                      json={"reason": "test gerekçe 2"}, timeout=30)
        assert rdup.status_code == 409

    def test_correction_approve_unlocks(self, s):
        cid = TestPayrollLock.correction_id
        r = s.post(f"{BASE_URL}/api/uk-payroll/corrections/{cid}/decide",
                   json={"decision": "approve"}, timeout=30)
        assert r.status_code == 200, r.text
        # verify run unlocked
        rl = s.get(f"{BASE_URL}/api/uk-payroll/runs/all", timeout=30).json()
        items = rl if isinstance(rl, list) else rl.get("items", [])
        run = next((x for x in items if (x.get("id") or x.get("run_id")) == TestPayrollLock.run_id), None)
        assert run and run.get("locked") is False, f"run: {run}"

    def test_rerun_applied_and_relocks(self, s):
        r = s.post(f"{BASE_URL}/api/uk-payroll/run/all",
                   json={"year": 2026, "month": 4, "force": True}, timeout=120)
        assert r.status_code == 200, r.text
        run = r.json().get("run") or r.json()
        assert run.get("locked") is True
        TestPayrollLock.run_id = run.get("id") or run.get("run_id") or TestPayrollLock.run_id

        cl = s.get(f"{BASE_URL}/api/uk-payroll/corrections/all", timeout=30).json()
        items = cl if isinstance(cl, list) else cl.get("items", [])
        corr = next((c for c in items if (c.get("id") or c.get("correction_id")) == TestPayrollLock.correction_id), None)
        assert corr and (corr.get("status") or "").lower() == "applied", f"corr: {corr}"

    def test_unlock_and_lock_direct(self, s):
        rid = TestPayrollLock.run_id
        ru = s.post(f"{BASE_URL}/api/uk-payroll/runs/{rid}/unlock",
                    json={"reason": "admin acil"}, timeout=30)
        assert ru.status_code == 200, ru.text
        cl = s.get(f"{BASE_URL}/api/uk-payroll/corrections/all", timeout=30).json()
        items = cl if isinstance(cl, list) else cl.get("items", [])
        direct = [c for c in items if c.get("run_id") == rid and c.get("direct") is True]
        assert direct, "expected direct:true correction logged"

        rl = s.post(f"{BASE_URL}/api/uk-payroll/runs/{rid}/lock", timeout=30)
        assert rl.status_code == 200, rl.text


# =========================================================
# D/E/F. Booking widget dynamic pricing + LOS + explain
# =========================================================
class TestBookingWidget:
    def test_min_stay_restriction(self):
        r = requests.post(f"{BASE_URL}/api/booking-widget/check-availability",
                          json={"property_id": "default",
                                "check_in": "2026-09-05",
                                "check_out": "2026-09-06"},
                          timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("available_rooms") == [] or not data.get("available_rooms")
        restriction = data.get("restriction") or {}
        assert restriction.get("type") == "min_stay"
        assert restriction.get("value") == 2

    def test_nightly_pricing_and_explain(self):
        r = requests.post(f"{BASE_URL}/api/booking-widget/check-availability",
                          json={"property_id": "default",
                                "check_in": "2026-09-05",
                                "check_out": "2026-09-07"},
                          timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        rooms = data.get("available_rooms") or []
        assert rooms, f"no rooms: {data}"
        rm = rooms[0]
        nightly = rm.get("nightly") or []
        assert len(nightly) == 2
        for n in nightly:
            assert "date" in n and "rate" in n and "source" in n and "base" in n
        pe = rm.get("price_explanation") or {}
        for key in ("vs_base_pct", "headline_en", "drivers", "base_total", "total"):
            assert key in pe, f"missing {key} in price_explanation: {pe}"
        assert abs(rm.get("total_rate", 0) - sum(n["rate"] for n in nightly)) < 0.5
        assert abs(rm.get("base_rate", 0) - (sum(n["rate"] for n in nightly) / 2)) < 0.5

    def test_book_server_reprices(self):
        # 2-night booking with rate=1.0 -> server should override
        email = f"test_iter605_{int(time.time())}@example.com"
        r = requests.post(f"{BASE_URL}/api/booking-widget/book",
                          json={"property_id": "default",
                                "room_type": "Standard Double",
                                "check_in": "2026-09-05",
                                "check_out": "2026-09-07",
                                "guest_name": "Iter605 Test",
                                "guest_email": email,
                                "guest_phone": "+441234567890",
                                "rate": 1.0,
                                "pay_now": False,
                                "adults": 2},
                          timeout=45)
        assert r.status_code == 200, r.text
        booking = r.json().get("booking") or r.json()
        assert booking.get("rate", 0) > 5, f"rate not repriced: {booking.get('rate')}"
        assert booking.get("nightly_rates"), "nightly_rates missing"

    def test_book_1_night_blocked_by_los(self):
        email = f"test_iter605_los_{int(time.time())}@example.com"
        r = requests.post(f"{BASE_URL}/api/booking-widget/book",
                          json={"property_id": "default",
                                "room_type": "Standard Double",
                                "check_in": "2026-09-05",
                                "check_out": "2026-09-06",
                                "guest_name": "Iter605 LOS",
                                "guest_email": email,
                                "guest_phone": "+441234567890",
                                "rate": 100.0,
                                "pay_now": False,
                                "adults": 2},
                          timeout=45)
        assert r.status_code == 409, f"expected 409 got {r.status_code}: {r.text}"


# =========================================================
# G. Ramp ladder forecast toggle
# =========================================================
class TestRampLadderForecast:
    def test_toggle_forecast_boost(self, s):
        r0 = s.get(f"{BASE_URL}/api/ramp-ladder/default", timeout=30)
        assert r0.status_code == 200, r0.text
        cfg0 = r0.json().get("config") or r0.json()
        original = cfg0.get("forecast_boost", True)

        r1 = s.put(f"{BASE_URL}/api/ramp-ladder/default/config",
                   json={"forecast_boost": False}, timeout=30)
        assert r1.status_code == 200, r1.text
        cfg1 = r1.json().get("config") or r1.json()
        assert cfg1.get("forecast_boost") is False

        r2 = s.put(f"{BASE_URL}/api/ramp-ladder/default/config",
                   json={"forecast_boost": True}, timeout=30)
        assert r2.status_code == 200
        cfg2 = r2.json().get("config") or r2.json()
        assert cfg2.get("forecast_boost") is True

    def test_scan_no_crash(self, s):
        r = s.post(f"{BASE_URL}/api/ramp-ladder/default/scan?force=true", timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "actions" in data or "skips" in data or "results" in data

    def test_get_config_shows_forecast_boost(self, s):
        r = s.get(f"{BASE_URL}/api/ramp-ladder/default", timeout=30)
        assert r.status_code == 200
        cfg = r.json().get("config") or r.json()
        assert "forecast_boost" in cfg
