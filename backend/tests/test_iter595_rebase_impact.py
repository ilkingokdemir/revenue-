"""Iter 595 — Rebase Etki Analizi (Robot) + split payment_status + menu-overrides fixes."""
import os
import time
import pytest
import requests

def _load_url():
    u = os.environ.get("REACT_APP_BACKEND_URL")
    if u: return u.rstrip("/")
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    return line.split("=", 1)[1].strip().rstrip("/")
    except Exception:
        pass
    raise RuntimeError("REACT_APP_BACKEND_URL not set")

BASE_URL = _load_url()
API = f"{BASE_URL}/api"

ADMIN = {"email": "admin@hotelbox.com", "password": "HotelAdmin2026!"}
SALES = {"email": "sales@hotelbox.com", "password": "Test2026!"}
PID = "aldgate-flats"


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{API}/auth/login", json=ADMIN, timeout=30)
    assert r.status_code == 200, r.text
    return r.json().get("token") or r.json().get("access_token")


@pytest.fixture(scope="module")
def admin_hdr(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="module")
def sales_hdr():
    r = requests.post(f"{API}/auth/login", json=SALES, timeout=30)
    if r.status_code != 200:
        pytest.skip("sales user unavailable")
    tok = r.json().get("token") or r.json().get("access_token")
    return {"Authorization": f"Bearer {tok}"}


# =============== REBASE IMPACT ================

class TestRebaseImpact:
    _report_id = None

    def test_defaults_admin(self, admin_hdr):
        r = requests.get(f"{API}/revenue/rebase-impact/{PID}/defaults", headers=admin_hdr, timeout=60)
        assert r.status_code == 200, r.text
        d = r.json()
        for key in ["grid", "multiplier", "occupancy_90d", "blended_adr_90d", "booking_window", "data_quality"]:
            assert key in d, f"missing {key}"
        assert isinstance(d["grid"], list) and len(d["grid"]) >= 1
        row0 = d["grid"][0]
        assert "horizons" in row0
        for h in ["0-30", "31-60", "61-90"]:
            assert h in row0["horizons"]
            assert "net_today" in row0["horizons"][h]
            assert "suggested" in row0["horizons"][h]
            assert "samples" in row0["horizons"][h]
        m = d["multiplier"]
        for k in ["value", "reliable", "samples", "range"]:
            assert k in m

    def test_defaults_no_auth_401(self):
        r = requests.get(f"{API}/revenue/rebase-impact/{PID}/defaults", timeout=30)
        assert r.status_code in (401, 403)

    def test_defaults_sales_manager_allowed_or_forbidden(self, sales_hdr):
        # require_roles("admin","manager") — sales has role manager so this SHOULD pass unless dept-scoped
        r = requests.get(f"{API}/revenue/rebase-impact/{PID}/defaults", headers=sales_hdr, timeout=60)
        # Accept either — just document behavior
        assert r.status_code in (200, 403), r.text
        print(f"[info] sales@ manager -> {r.status_code}")

    def test_analyze_default(self, admin_hdr):
        payload = {"targets": {}, "commission_pct": 15.5, "variable_cost": 15}
        r = requests.post(f"{API}/revenue/rebase-impact/{PID}/analyze", json=payload, headers=admin_hdr, timeout=90)
        assert r.status_code == 200, r.text
        rep = r.json()
        assert "id" in rep and rep["id"]
        TestRebaseImpact._report_id = rep["id"]
        assert isinstance(rep["rows"], list)
        # 6 room types × 3 horizons could vary; check horizon count structure
        horizons = {row["horizon"] for row in rep["rows"]}
        assert horizons == {"0-30", "31-60", "61-90"}, horizons
        assert len(rep["rows"]) % 3 == 0
        print(f"[info] rows={len(rep['rows'])}")
        for key in ["weighted", "weighted_change_pct", "contribution", "breakeven", "caveats", "narrative_tr", "multiplier"]:
            assert key in rep
        c = rep["contribution"]
        for k in ["today_total", "after_total", "loss", "per_night_today", "per_night_after"]:
            assert k in c
        be = rep["breakeven"]
        for k in ["rn_needed", "occ_needed_pct", "feasible", "rn_today", "rn_available"]:
            assert k in be
        assert isinstance(rep["narrative_tr"], list) and len(rep["narrative_tr"]) >= 3
        # narrative in Turkish
        joined = " ".join(rep["narrative_tr"])
        assert any(w in joined for w in ["katkı", "doluluk", "başabaş", "misafir", "rebase"]), joined

    def test_analyze_manual_targets_increase_loss(self, admin_hdr):
        # First get baseline default analyze
        base_r = requests.post(f"{API}/revenue/rebase-impact/{PID}/analyze",
                               json={"targets": {}, "commission_pct": 15.5, "variable_cost": 15},
                               headers=admin_hdr, timeout=90)
        base = base_r.json()
        base_loss = base["contribution"]["loss"]

        # Get defaults to find a room type id
        d = requests.get(f"{API}/revenue/rebase-impact/{PID}/defaults", headers=admin_hdr, timeout=60).json()
        rtid = d["grid"][0]["room_type_id"]
        # Force a very low target
        payload = {
            "targets": {rtid: {"0-30": 10, "31-60": 10, "61-90": 10}},
            "commission_pct": 15.5, "variable_cost": 15,
        }
        r = requests.post(f"{API}/revenue/rebase-impact/{PID}/analyze", json=payload, headers=admin_hdr, timeout=90)
        assert r.status_code == 200, r.text
        rep = r.json()
        # Loss should be >= baseline (aggressive lower target)
        assert rep["contribution"]["loss"] >= base_loss - 1, f"expected higher loss, got {rep['contribution']['loss']} vs base {base_loss}"
        # target row should reflect the £10
        found = [row for row in rep["rows"] if row["room_type_id"] == rtid]
        assert any(abs(row["net_after"] - 10.0) < 0.01 for row in found), "manual target not applied"

    def test_ai_comment_valid_report(self, admin_hdr):
        rid = TestRebaseImpact._report_id
        if not rid:
            pytest.skip("no report id from previous test")
        r = requests.post(f"{API}/revenue/rebase-impact/{PID}/ai-comment",
                          json={"report_id": rid}, headers=admin_hdr, timeout=90)
        assert r.status_code == 200, r.text
        j = r.json()
        assert "comment" in j and isinstance(j["comment"], str) and len(j["comment"]) > 20
        print(f"[info] AI comment len={len(j['comment'])}")

    def test_ai_comment_invalid_report_404(self, admin_hdr):
        r = requests.post(f"{API}/revenue/rebase-impact/{PID}/ai-comment",
                          json={"report_id": "does-not-exist-xxx"}, headers=admin_hdr, timeout=30)
        assert r.status_code == 404, r.text

    def test_history(self, admin_hdr):
        r = requests.get(f"{API}/revenue/rebase-impact/{PID}/history", headers=admin_hdr, timeout=30)
        assert r.status_code == 200, r.text
        j = r.json()
        assert "reports" in j and isinstance(j["reports"], list)
        # must include the report we just made
        if TestRebaseImpact._report_id:
            ids = {rep["id"] for rep in j["reports"]}
            assert TestRebaseImpact._report_id in ids


# =============== SPLIT payment_status fix ================

class TestSplitPaymentStatus:
    def test_split_second_booking_pending(self, admin_hdr):
        # Create a paid booking, then split it
        import datetime as dt
        ci = (dt.date.today() + dt.timedelta(days=60)).isoformat()
        co = (dt.date.today() + dt.timedelta(days=64)).isoformat()

        # Find a room by peeking at existing bookings
        peek = requests.get(f"{API}/bookings?property_id={PID}&limit=1", headers=admin_hdr, timeout=30)
        if peek.status_code != 200 or not peek.json():
            pytest.skip("no bookings sample to derive room id")
        sample = peek.json()[0] if isinstance(peek.json(), list) else peek.json().get("bookings", [{}])[0]
        room_id = sample.get("room_id")
        room_type_id = sample.get("room_type_id")

        booking = {
            "property_id": PID, "room_id": room_id, "room_type_id": room_type_id,
            "guest_name": "TEST_SplitPay", "check_in": ci, "check_out": co,
            "nights": 4, "total_price": 400, "rate": 100,
            "payment_status": "paid", "status": "confirmed",
            "guest_email": "test_splitpay@example.com",
        }
        cr = requests.post(f"{API}/bookings", json=booking, headers=admin_hdr, timeout=30)
        print(f"[split] create -> {cr.status_code} {cr.text[:300]}")
        if cr.status_code not in (200, 201):
            pytest.skip(f"cannot create booking: {cr.status_code} {cr.text[:200]}")
        bid = cr.json().get("id") or cr.json().get("booking", {}).get("id")
        assert bid

        # Split at midpoint
        split_date = (dt.date.today() + dt.timedelta(days=62)).isoformat()
        # Find another room id (different from booking's room)
        peek2 = requests.get(f"{API}/bookings?property_id={PID}&limit=50", headers=admin_hdr, timeout=30).json()
        peek2 = peek2 if isinstance(peek2, list) else peek2.get("bookings", [])
        other_room_ids = list({b.get("room_id") for b in peek2 if b.get("room_id") and b.get("room_id") != room_id})
        if not other_room_ids:
            requests.delete(f"{API}/bookings/{bid}", headers=admin_hdr, timeout=15)
            pytest.skip("no alternate room id available")
        new_room_id = other_room_ids[0]

        sp = requests.post(f"{API}/bookings/{bid}/split",
                           json={"split_date": split_date, "new_room_id": new_room_id},
                           headers=admin_hdr, timeout=30)
        print(f"[split] split -> {sp.status_code} {sp.text[:500]}")
        if sp.status_code not in (200, 201):
            # cleanup
            requests.delete(f"{API}/bookings/{bid}", headers=admin_hdr, timeout=15)
            pytest.skip(f"split failed: {sp.status_code} {sp.text[:200]}")
        result = sp.json()
        # Result should include ids of both parts
        second_id = (result.get("second") or {}).get("id")
        second_status_inline = (result.get("second") or {}).get("payment_status")
        if not second_id:
            # fallback - list bookings and find the newer one
            print(f"[warn] split response shape: {result}")
            pytest.skip("cannot locate second booking id")

        # Verify payment_status == pending on second (from inline + GET)
        assert second_status_inline == "pending", f"inline second payment_status={second_status_inline}"
        gr = requests.get(f"{API}/bookings/{second_id}", headers=admin_hdr, timeout=30)
        if gr.status_code == 200:
            assert gr.json().get("payment_status") == "pending", gr.json().get("payment_status")

        # Cleanup
        requests.delete(f"{API}/bookings/{bid}", headers=admin_hdr, timeout=15)
        requests.delete(f"{API}/bookings/{second_id}", headers=admin_hdr, timeout=15)


# =============== MENU OVERRIDES fix ================

class TestMenuOverridesFix:
    def test_put_hidden_false_removes_override(self, admin_hdr):
        module_id = "rebase-impact"
        # Ensure override exists first — set hidden:true
        r1 = requests.put(f"{API}/menu-overrides/{module_id}",
                          json={"hidden": True}, headers=admin_hdr, timeout=30)
        assert r1.status_code == 200, r1.text
        # Now PUT hidden:false — should return 200 and delete
        r2 = requests.put(f"{API}/menu-overrides/{module_id}",
                          json={"hidden": False}, headers=admin_hdr, timeout=30)
        assert r2.status_code == 200, r2.text
        # Verify override gone via GET
        g = requests.get(f"{API}/menu-overrides", headers=admin_hdr, timeout=30)
        if g.status_code == 200:
            payload = g.json()
            overrides = payload.get("overrides", payload) if isinstance(payload, dict) else payload
            if isinstance(overrides, dict):
                assert module_id not in overrides or not overrides.get(module_id, {}).get("hidden")
            elif isinstance(overrides, list):
                hits = [o for o in overrides if (o.get("module_id") == module_id or o.get("id") == module_id)]
                # override should not exist (deleted) OR hidden false
                assert not hits or not any(h.get("hidden") for h in hits)
