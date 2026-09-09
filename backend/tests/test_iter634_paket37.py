"""Iter634 Paket37: Webhook retry, API key expiry, PMS sync-timeline/resync, chain geo."""
import os
import time
import pytest
import requests
from datetime import date, timedelta

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://review-hub-108.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASS = "HotelAdmin2026!"
PID = "aldgate-flats"


@pytest.fixture(scope="module")
def admin_headers():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=15)
    assert r.status_code == 200, r.text
    t = r.json().get("token") or r.json().get("access_token")
    return {"Authorization": f"Bearer {t}"}


# =============== Webhooks ===============
class TestWebhooks:
    def test_full_flow(self, admin_headers):
        # 1. Clean up any prior test subscriptions
        r = requests.get(f"{API}/webhook-subs/{PID}", headers=admin_headers, timeout=15)
        assert r.status_code == 200, r.text
        for s in r.json().get("subscriptions", []):
            if "httpstat.us" in s.get("url", ""):
                requests.delete(f"{API}/webhook-subs/{PID}/{s['id']}", headers=admin_headers, timeout=15)

        # 2. Add sub with url that will fail
        r = requests.post(f"{API}/webhook-subs/{PID}", headers=admin_headers,
                          json={"url": "https://httpstat.us/500", "events": ["*"]}, timeout=15)
        assert r.status_code == 200, r.text
        sub = r.json()
        assert "id" in sub and "secret" in sub
        pytest.sub_id = sub["id"]

        # 3. Fire test event
        r = requests.post(f"{API}/webhook-subs/{PID}/test", headers=admin_headers, timeout=30)
        assert r.status_code == 200, r.text
        # sent==0 because delivery fails (backoff)
        assert r.json().get("sent") == 0

        # 4. List — recent_deliveries[0].status == retrying, attempts 1, no payload
        r = requests.get(f"{API}/webhook-subs/{PID}", headers=admin_headers, timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert data["counts"].get("retrying", 0) >= 1
        rd = data["recent_deliveries"][0]
        assert rd["status"] == "retrying"
        assert rd["attempts"] == 1
        assert rd.get("next_retry_at")
        assert "payload" not in rd
        pytest.delivery_id = rd["id"]

        # 5. Deliveries filter by status=retrying
        r = requests.get(f"{API}/webhook-subs/{PID}/deliveries?status=retrying",
                         headers=admin_headers, timeout=15)
        assert r.status_code == 200
        ids = [d["id"] for d in r.json()["deliveries"]]
        assert pytest.delivery_id in ids

        # 6. Retry now → attempts 2, still retrying
        r = requests.post(f"{API}/webhook-subs/{PID}/deliveries/{pytest.delivery_id}/retry",
                          headers=admin_headers, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["attempts"] == 2
        assert d["status"] == "retrying"
        assert "payload" not in d

        # 7. Deactivate sub → test → no new delivery for that sub
        r = requests.put(f"{API}/webhook-subs/{PID}/{pytest.sub_id}",
                         headers=admin_headers, json={"active": False}, timeout=15)
        assert r.status_code == 200
        before = requests.get(f"{API}/webhook-subs/{PID}/deliveries", headers=admin_headers, timeout=15).json()
        before_count = sum(1 for d in before["deliveries"] if d.get("subscription_id") == pytest.sub_id)
        r = requests.post(f"{API}/webhook-subs/{PID}/test", headers=admin_headers, timeout=30)
        assert r.json().get("sent") == 0
        after = requests.get(f"{API}/webhook-subs/{PID}/deliveries", headers=admin_headers, timeout=15).json()
        after_count = sum(1 for d in after["deliveries"] if d.get("subscription_id") == pytest.sub_id)
        assert after_count == before_count, "Inactive sub should not produce new deliveries"

        # 8. Delete sub
        r = requests.delete(f"{API}/webhook-subs/{PID}/{pytest.sub_id}",
                            headers=admin_headers, timeout=15)
        assert r.status_code == 200


# =============== API Key Expiry ===============
class TestApiKeyExpiry:
    def test_create_with_days_and_extend(self, admin_headers):
        r = requests.post(f"{API}/public-keys/{PID}", headers=admin_headers,
                          json={"name": "TEST_exp", "expires_in_days": 3}, timeout=15)
        assert r.status_code == 200, r.text
        key = r.json()
        assert key.get("expires_at")
        pytest.exp_id = key["id"]

        # list — days_left 2 or 3
        r = requests.get(f"{API}/public-keys/{PID}", headers=admin_headers, timeout=15)
        row = next(k for k in r.json()["keys"] if k["id"] == pytest.exp_id)
        assert row["days_left"] in (2, 3), row
        assert row["expired"] is False

        # extend 90 days
        r = requests.put(f"{API}/public-keys/{PID}/{pytest.exp_id}",
                         headers=admin_headers, json={"extend_days": 90}, timeout=15)
        assert r.status_code == 200, r.text
        r = requests.get(f"{API}/public-keys/{PID}", headers=admin_headers, timeout=15)
        row = next(k for k in r.json()["keys"] if k["id"] == pytest.exp_id)
        assert 90 <= row["days_left"] <= 94, row  # roughly 92

    def test_expired_key_401_and_expiry_check(self, admin_headers):
        # create already-expired key
        r = requests.post(f"{API}/public-keys/{PID}", headers=admin_headers,
                          json={"name": "TEST_dead", "expires_at": "2020-01-01T00:00:00+00:00"}, timeout=15)
        assert r.status_code == 200, r.text
        raw = r.json()["key"]
        dead_id = r.json()["id"]
        pytest.dead_id = dead_id

        # Using expired key should 401
        r = requests.get(f"{API}/public/v1/rate-plans", headers={"X-API-Key": raw}, timeout=15)
        assert r.status_code == 401, r.text
        assert "süresi dolmuş" in r.text.lower() or "süresi doldu" in r.text.lower()

        # list shows expired true
        r = requests.get(f"{API}/public-keys/{PID}", headers=admin_headers, timeout=15)
        row = next(k for k in r.json()["keys"] if k["id"] == dead_id)
        assert row["expired"] is True

        # expiry-check: warned/expired >=1
        r = requests.post(f"{API}/public-keys/{PID}/expiry-check", headers=admin_headers, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("expired", 0) + d.get("warned", 0) >= 1

        # idempotent second call returns 0/0
        r = requests.post(f"{API}/public-keys/{PID}/expiry-check", headers=admin_headers, timeout=30)
        d = r.json()
        assert d.get("expired", 0) == 0 and d.get("warned", 0) == 0

    def test_invalid_expires_at_422(self, admin_headers):
        r = requests.put(f"{API}/public-keys/{PID}/{pytest.exp_id}",
                         headers=admin_headers, json={"expires_at": "abc"}, timeout=15)
        assert r.status_code == 422, r.text

    def test_cleanup(self, admin_headers):
        # cleanup TEST_ keys
        r = requests.get(f"{API}/public-keys/{PID}", headers=admin_headers, timeout=15)
        # Note: no DELETE endpoint for keys; leave as-is (they are safe / TEST_-prefixed)
        assert r.status_code == 200


# =============== PMS Connector sync ===============
class TestPmsConnectorSync:
    def test_push_and_log(self, admin_headers):
        r = requests.post(f"{API}/pms-connect/opera-cloud/push-from-rms/{PID}?days=3",
                          headers=admin_headers, json={}, timeout=30)
        assert r.status_code == 200, r.text
        # mocked path OK

        r = requests.get(f"{API}/pms-connect/opera-cloud/log/{PID}?limit=1",
                         headers=admin_headers, timeout=15)
        assert r.status_code == 200
        rows = r.json().get("log", [])
        assert len(rows) >= 1
        pytest.pms_log_id = rows[0]["id"]

    def test_resync(self, admin_headers):
        r = requests.post(f"{API}/pms-connect/opera-cloud/resync/{PID}/{pytest.pms_log_id}",
                          headers=admin_headers, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("ok") is True
        assert d.get("resynced_from") == pytest.pms_log_id

    def test_sync_timeline(self, admin_headers):
        r = requests.get(f"{API}/pms-connect/opera-cloud/sync-timeline/{PID}",
                         headers=admin_headers, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("health") in ("healthy", "degraded", "no_data")
        assert d.get("totals", {}).get("mocked", 0) >= 2
        assert isinstance(d.get("timeline"), list)
        assert isinstance(d.get("failed_entries"), list)
        # today present in timeline
        today = date.today().isoformat()
        assert any(t["date"] == today for t in d["timeline"])

    def test_unknown_provider_404(self, admin_headers):
        r = requests.get(f"{API}/pms-connect/foo-bar/sync-timeline/{PID}",
                         headers=admin_headers, timeout=15)
        assert r.status_code == 404

    def test_unknown_log_id_404(self, admin_headers):
        r = requests.post(f"{API}/pms-connect/opera-cloud/resync/{PID}/nonexistent-id-xyz",
                          headers=admin_headers, timeout=15)
        assert r.status_code == 404


# =============== Chain search geo ===============
class TestChainGeo:
    def test_chain_search_has_geo(self):
        params = {"check_in": "2026-09-20", "check_out": "2026-09-22", "adults": 2}
        t0 = time.time()
        r = requests.get(f"{API}/booking/chain-search", params=params, timeout=60)
        elapsed1 = time.time() - t0
        assert r.status_code == 200, r.text
        props = r.json().get("properties") or r.json().get("results") or []
        assert len(props) > 0
        for p in props:
            assert "centre_km" in p
            assert "station" in p
            # centre_km number or None
            if p["centre_km"] is not None:
                assert isinstance(p["centre_km"], (int, float))
            if p["station"] is not None:
                assert "name" in p["station"] and "km" in p["station"]

        # 2nd call — cached, should be faster
        t0 = time.time()
        r2 = requests.get(f"{API}/booking/chain-search", params=params, timeout=30)
        elapsed2 = time.time() - t0
        assert r2.status_code == 200
        print(f"chain-search timings: first={elapsed1:.2f}s cached={elapsed2:.2f}s")
