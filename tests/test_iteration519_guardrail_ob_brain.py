"""
Iteration 519 - Test:
- Open Pricing Optimizer guardrail (±15%)
- Overbooking apply-limits endpoint
- Revenue Brain permanent memory (append-only)
"""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://review-hub-108.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASS = "HotelAdmin2026!"


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    tok = r.json().get("access_token") or r.json().get("token")
    if tok:
        s.headers.update({"Authorization": f"Bearer {tok}"})
    return s


# --- Open Pricing Optimizer guardrail ---
class TestOpenPricingGuardrail:
    def test_optimize_twice_within_15pct(self, client):
        r1 = client.post(f"{BASE_URL}/api/open-pricing/optimize",
                         json={"property_id": "default", "days": 5, "apply": True}, timeout=60)
        assert r1.status_code == 200, r1.text[:300]
        d1 = r1.json()
        assert d1.get("ok") is True
        matrix1 = d1.get("matrix") or []
        assert matrix1, f"No matrix returned: {d1}"

        def flat(matrix):
            m = {}
            for row in matrix:
                d = row.get("date")
                for k, v in (row.get("cells") or {}).items():
                    m[(d, k)] = v
            return m

        first = flat(matrix1)
        time.sleep(1)

        r2 = client.post(f"{BASE_URL}/api/open-pricing/optimize",
                         json={"property_id": "default", "days": 5, "apply": True}, timeout=60)
        assert r2.status_code == 200, r2.text[:300]
        d2 = r2.json()
        second = flat(d2.get("matrix") or [])
        assert second, f"No matrix on second call: {d2}"

        violations = []
        for k, r_new in second.items():
            r_prev = first.get(k)
            if r_prev is None or not r_prev:
                continue
            change = abs(r_new - r_prev) / r_prev
            if change > 0.1501:
                violations.append((k, r_prev, r_new, round(change, 4)))
        print(f"Compared {len(second)} cells, {len(violations)} violations")
        assert not violations, f"Guardrail violated ({len(violations)} cells): {violations[:5]}"


# --- Overbooking apply limits ---
class TestOverbookingApply:
    def test_apply_and_verify(self, client):
        r = client.post(f"{BASE_URL}/api/overbooking-control/default/apply",
                        json={"days": 14}, timeout=60)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert d.get("ok") is True
        assert d.get("applied_days") == 14
        assert "extra_capacity" in d
        assert "expected_extra_revenue" in d

        g = client.get(f"{BASE_URL}/api/overbooking-control/default?days=14", timeout=30)
        assert g.status_code == 200, g.text[:300]
        gd = g.json()
        assert gd.get("applied_count", 0) > 0, f"applied_count not > 0: {gd.get('applied_count')}"
        days = gd.get("days") or gd.get("items") or []
        applied_items = [x for x in days if x.get("applied_limit") is not None and x.get("applied_at")]
        assert applied_items, "No days with applied_limit / applied_at"


# --- Revenue Brain permanent memory ---
class TestRevenueBrainMemory:
    def test_learn_then_memory_permanence(self, client):
        # First learn
        r = client.post(f"{BASE_URL}/api/revenue-brain/city-gate/learn", json={}, timeout=60)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert d.get("memory_consolidated", 0) >= 1, f"expected consolidated>=1: {d}"

        m = client.get(f"{BASE_URL}/api/revenue-brain/city-gate/memory", timeout=30)
        assert m.status_code == 200, m.text[:300]
        md = m.json()
        assert md.get("count", 0) >= 1
        items = md.get("items") or md.get("memory") or []
        assert items, f"no memory items: {md}"
        first_item = items[0]
        for f in ["importance", "status", "factor", "times_confirmed", "first_learned"]:
            assert f in first_item, f"missing field {f} in {first_item.keys()}"

        # Pick a stable identifier
        ident = first_item.get("_key") or first_item.get("key") or (first_item.get("factor"), first_item.get("bucket") or first_item.get("cohort"))
        prev_times = first_item.get("times_confirmed")
        prev_first_learned = first_item.get("first_learned")

        # Re-learn
        time.sleep(1)
        r2 = client.post(f"{BASE_URL}/api/revenue-brain/city-gate/learn", json={}, timeout=60)
        assert r2.status_code == 200
        m2 = client.get(f"{BASE_URL}/api/revenue-brain/city-gate/memory", timeout=30)
        items2 = m2.json().get("items") or m2.json().get("memory") or []
        # Find matching item
        def match(it):
            ident2 = it.get("_key") or it.get("key") or (it.get("factor"), it.get("bucket") or it.get("cohort"))
            return ident2 == ident
        candidates = [it for it in items2 if match(it)]
        assert candidates, f"item not found second time; identifiers: {[(i.get('factor'), i.get('bucket')) for i in items2[:5]]}"
        after = candidates[0]
        assert after.get("times_confirmed") >= (prev_times or 0) + 1, \
            f"times_confirmed did not increment: {prev_times} -> {after.get('times_confirmed')}"
        assert after.get("first_learned") == prev_first_learned, \
            f"first_learned changed: {prev_first_learned} -> {after.get('first_learned')}"

    def test_status_includes_permanent_memory(self, client):
        s = client.get(f"{BASE_URL}/api/revenue-brain/city-gate/status", timeout=30)
        assert s.status_code == 200, s.text[:300]
        sd = s.json()
        assert "permanent_memory" in sd, f"missing permanent_memory: keys={list(sd.keys())}"
        assert "memory_count" in sd


# --- Smoke regression ---
class TestSmoke:
    def test_dashboard_reachable(self, client):
        # try a common endpoint
        for path in ["/api/dashboard/summary", "/api/bookings?limit=1", "/api/bookings"]:
            r = client.get(f"{BASE_URL}{path}", timeout=30)
            if r.status_code == 200:
                return
        pytest.fail("no dashboard/booking endpoint responded 200")
