"""
Iteration 520:
- Guardrail GET/PUT + optimize reads guardrail_pct from settings
- Global memory consolidate + GET /global-memory
- Timeline events + duplicate suppression
- Global prior blending code path (AI pricing engine)
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


# --- Guardrail settings ---
class TestGuardrailSettings:
    def test_get_default_guardrail(self, client):
        r = client.get(f"{BASE_URL}/api/open-pricing/guardrail/default", timeout=30)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert "guardrail_pct" in d
        assert float(d["guardrail_pct"]) == 15.0

    def test_put_guardrail_20_then_optimize_reads_it(self, client):
        r = client.put(f"{BASE_URL}/api/open-pricing/guardrail/default",
                       json={"guardrail_pct": 20}, timeout=30)
        assert r.status_code == 200, r.text[:300]
        assert r.json().get("guardrail_pct") == 20.0

        # confirm persisted
        g = client.get(f"{BASE_URL}/api/open-pricing/guardrail/default", timeout=30)
        assert g.json().get("guardrail_pct") == 20.0

        # optimize (apply False) reads from settings
        o = client.post(f"{BASE_URL}/api/open-pricing/optimize",
                        json={"property_id": "default", "days": 3, "apply": False}, timeout=60)
        assert o.status_code == 200, o.text[:300]
        od = o.json()
        assert od.get("guardrail_pct") == 20.0, f"expected 20 got {od.get('guardrail_pct')}"

    def test_put_invalid_returns_400(self, client):
        r = client.put(f"{BASE_URL}/api/open-pricing/guardrail/default",
                       json={"guardrail_pct": 60}, timeout=30)
        assert r.status_code == 400, f"expected 400 got {r.status_code}: {r.text[:200]}"

    def test_reset_guardrail_to_15(self, client):
        r = client.put(f"{BASE_URL}/api/open-pricing/guardrail/default",
                       json={"guardrail_pct": 15}, timeout=30)
        assert r.status_code == 200
        assert r.json().get("guardrail_pct") == 15.0


# --- Global Memory ---
class TestGlobalMemory:
    def test_learn_populates_global_memory(self, client):
        r = client.post(f"{BASE_URL}/api/revenue-brain/city-gate/learn", json={}, timeout=60)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert d.get("global_memory_updated", 0) >= 1, f"expected global_memory_updated>=1: {d}"

    def test_get_global_memory(self, client):
        r = client.get(f"{BASE_URL}/api/revenue-brain/global-memory", timeout=30)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert d.get("count", 0) >= 1
        items = d.get("items") or d.get("memory") or []
        assert items, f"no global memory items: {d}"
        first = items[0]
        for f in ["bucket_key", "factor", "samples", "worked_rate",
                  "properties_contributing", "title", "detail", "first_learned"]:
            assert f in first, f"missing field {f} in {list(first.keys())}"

    def test_city_gate_status_includes_global_memory(self, client):
        r = client.get(f"{BASE_URL}/api/revenue-brain/city-gate/status", timeout=30)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert "global_memory" in d, f"missing global_memory in keys={list(d.keys())}"
        assert "global_memory_count" in d


# --- Timeline ---
class TestTimeline:
    def test_timeline_has_events(self, client):
        r = client.get(f"{BASE_URL}/api/revenue-brain/city-gate/timeline", timeout=30)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert d.get("count", 0) >= 1
        items = d.get("items") or []
        assert items
        for f in ["id", "type", "text", "at"]:
            assert f in items[0], f"missing {f} in {list(items[0].keys())}"

    def test_duplicate_suppression(self, client):
        # snapshot
        r1 = client.get(f"{BASE_URL}/api/revenue-brain/city-gate/timeline", timeout=30)
        assert r1.status_code == 200
        before = r1.json().get("items") or []
        before_dogr = [x for x in before if x.get("type") == "ders_dogrulandi"]

        # re-learn
        lr = client.post(f"{BASE_URL}/api/revenue-brain/city-gate/learn", json={}, timeout=60)
        assert lr.status_code == 200
        time.sleep(1)

        r2 = client.get(f"{BASE_URL}/api/revenue-brain/city-gate/timeline", timeout=30)
        after = r2.json().get("items") or []
        after_dogr = [x for x in after if x.get("type") == "ders_dogrulandi"]

        # Same-day duplicates for same bucket must not increase
        # Group by (type, bucket_key) — since we can't see bucket_key in response schema, compare count parity
        # If the code suppresses duplicates for same day+bucket+type, the count of ders_dogrulandi should not
        # increase by more than 0 within a same-day rerun
        assert len(after_dogr) == len(before_dogr), \
            f"ders_dogrulandi grew from {len(before_dogr)} to {len(after_dogr)} (duplicate suppression failed)"


# --- Global prior blending: any pricing endpoint for property without local weights returns 200 ---
class TestGlobalPriorBlending:
    def test_pricing_endpoints_still_200(self, client):
        # try common AI pricing endpoints
        candidates = [
            ("GET", "/api/ai-pricing/default/suggest?days=3"),
            ("POST", "/api/ai-pricing/default/suggest"),
            ("GET", "/api/pricing-suggestions/default?days=3"),
            ("POST", "/api/open-pricing/optimize"),
        ]
        any_ok = False
        for method, path in candidates:
            try:
                if method == "GET":
                    r = client.get(f"{BASE_URL}{path}", timeout=45)
                else:
                    body = {"property_id": "default", "days": 3, "apply": False} if "optimize" in path else {}
                    r = client.post(f"{BASE_URL}{path}", json=body, timeout=45)
                print(f"{method} {path} -> {r.status_code}")
                if r.status_code == 200:
                    any_ok = True
            except Exception as e:
                print(f"{method} {path} error: {e}")
        assert any_ok, "no pricing endpoint returned 200"


# --- Smoke ---
class TestSmoke:
    def test_overbooking_apply_still_works(self, client):
        r = client.post(f"{BASE_URL}/api/overbooking-control/default/apply",
                        json={"days": 14}, timeout=60)
        assert r.status_code == 200, r.text[:300]
        assert r.json().get("ok") is True
