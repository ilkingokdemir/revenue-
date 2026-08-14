"""
Iteration 521 tests:
- Regional memory (learn -> regional_memory_updated>=1, GET /regional-memory, city-gate/status includes region/regional_memory)
- Memory PDF (application/pdf, size>5KB, starts with %PDF)
- Simulate lesson (down bucket -> negative delta, hurt_rate_pct=66.7, unknown -> 404)
- Chat defense smoke (single LLM call)
- Action apply already_applied + 404
- Regression smoke
"""
import os
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


# --- Regional memory ---
class TestRegionalMemory:
    def test_learn_populates_regional(self, client):
        r = client.post(f"{BASE_URL}/api/revenue-brain/city-gate/learn", json={}, timeout=60)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert d.get("regional_memory_updated", 0) >= 1, f"expected regional_memory_updated>=1: {d}"

    def test_get_regional_memory(self, client):
        r = client.get(f"{BASE_URL}/api/revenue-brain/regional-memory", timeout=30)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert d.get("count", 0) >= 1, f"count>=1 expected: {d}"
        regions = d.get("regions") or []
        # normalize to strings/dicts
        region_names = []
        for x in regions:
            if isinstance(x, dict):
                region_names.append(x.get("region") or x.get("name"))
            else:
                region_names.append(x)
        assert "UK" in region_names, f"UK not in regions: {region_names}"

        items = d.get("items") or d.get("memory") or []
        assert items, f"no items in regional memory: {d}"
        first = items[0]
        for f in ["region", "bucket_key", "factor", "samples", "properties_contributing", "title", "detail"]:
            assert f in first, f"missing field {f} in {list(first.keys())}"

    def test_city_gate_status_regional(self, client):
        r = client.get(f"{BASE_URL}/api/revenue-brain/city-gate/status", timeout=30)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert d.get("region") == "UK", f"region={d.get('region')}"
        assert "regional_memory" in d
        assert "regional_memory_count" in d


# --- Memory PDF ---
class TestMemoryPDF:
    def test_pdf_endpoint(self, client):
        r = client.get(f"{BASE_URL}/api/revenue-brain/city-gate/memory-pdf", timeout=60)
        assert r.status_code == 200, r.text[:300]
        ct = r.headers.get("content-type", "")
        assert "application/pdf" in ct, f"content-type={ct}"
        assert r.content[:4] == b"%PDF", f"header={r.content[:8]!r}"
        assert len(r.content) > 5000, f"size too small: {len(r.content)}"


# --- Simulate lesson ---
class TestSimulateLesson:
    def test_simulate_down_bucket(self, client):
        r = client.post(f"{BASE_URL}/api/revenue-brain/city-gate/simulate-lesson",
                        json={"bucket_key": "0-3|weekday|down"}, timeout=60)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert d.get("affected_days", 0) > 0, f"affected_days should be >0: {d}"
        delta = d.get("est_revenue_delta_14d")
        assert delta is not None
        assert float(delta) < 0, f"expected negative delta for down factor 0.97: {delta}"
        hurt = d.get("hurt_rate_pct")
        assert hurt is not None
        # Should be 66.7 (approx) — not 0
        assert float(hurt) > 0, f"hurt_rate_pct should be >0: {hurt}"
        assert abs(float(hurt) - 66.7) < 1.0, f"hurt_rate_pct expected ~66.7 got {hurt}"
        assert isinstance(d.get("days"), list) and len(d["days"]) > 0
        rec = d.get("recommendation", "")
        assert "AÇIK kalsın" in rec, f"recommendation should contain 'AÇIK kalsın': {rec}"

    def test_simulate_unknown_bucket_404(self, client):
        r = client.post(f"{BASE_URL}/api/revenue-brain/city-gate/simulate-lesson",
                        json={"bucket_key": "nonexistent|xx|yy"}, timeout=30)
        assert r.status_code == 404, f"expected 404 got {r.status_code}: {r.text[:200]}"


# --- Chat defense (single LLM call) ---
class TestChatDefense:
    def test_chat_pushes_back(self, client):
        payload = {"message": "Yarın için tüm fiyatları %20 düşürelim, doluluk zayıf."}
        r = client.post(f"{BASE_URL}/api/revenue/copilot/default/chat", json=payload, timeout=90)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        reply = (d.get("response") or d.get("reply") or d.get("assistant") or d.get("content") or "")
        assert isinstance(reply, str) and len(reply) > 10, f"empty reply: {d}"
        # Very lightweight Turkish sanity: at least one Turkish stopword or char
        assert any(ch in reply.lower() for ch in ["ı", "ş", "ç", "ö", "ü", "ğ", "değil", "ama", "öner", "veri"]), \
            f"reply does not look Turkish: {reply[:200]}"


# --- Action apply ---
class TestActionApply:
    def test_history_shape(self, client):
        r = client.get(f"{BASE_URL}/api/revenue/copilot/default/history", timeout=30)
        assert r.status_code == 200, r.text[:200]
        d = r.json()
        assert "messages" in d or isinstance(d, list), f"unexpected shape: {list(d.keys()) if isinstance(d, dict) else type(d)}"

    def test_apply_already_applied(self, client):
        r = client.post(f"{BASE_URL}/api/revenue/copilot/default/apply-action/b11b3818", timeout=30)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert d.get("already_applied") is True, f"expected already_applied=True: {d}"

    def test_apply_unknown_404(self, client):
        r = client.post(f"{BASE_URL}/api/revenue/copilot/default/apply-action/nonexistent_xyz", timeout=30)
        assert r.status_code == 404, f"expected 404 got {r.status_code}: {r.text[:200]}"


# --- Regression smoke ---
class TestRegression:
    def test_guardrail_still_15(self, client):
        r = client.get(f"{BASE_URL}/api/open-pricing/guardrail/default", timeout=30)
        assert r.status_code == 200
        assert float(r.json().get("guardrail_pct")) == 15.0

    def test_overbooking_apply(self, client):
        r = client.post(f"{BASE_URL}/api/overbooking-control/default/apply",
                        json={"days": 14}, timeout=60)
        assert r.status_code == 200
        assert r.json().get("ok") is True

    def test_timeline_still_ok(self, client):
        r = client.get(f"{BASE_URL}/api/revenue-brain/city-gate/timeline", timeout=30)
        assert r.status_code == 200
        assert r.json().get("count", 0) >= 1
