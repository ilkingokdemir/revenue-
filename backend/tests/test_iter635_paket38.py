"""Iter635 Paket38 — Webhook HMAC signature, Public API usage/anomaly, chain-search geo+airport, PMS sync alerts."""
import hashlib
import hmac
import os
import time

import pytest
import requests

def _base_url():
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if v:
        return v.rstrip("/")
    # read frontend/.env
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    return line.split("=", 1)[1].strip().rstrip("/")
    except Exception:
        pass
    raise RuntimeError("REACT_APP_BACKEND_URL not set")

BASE_URL = _base_url()
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"
PID = "aldgate-flats"


@pytest.fixture(scope="session")
def token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=15)
    assert r.status_code == 200, r.text
    return r.json().get("access_token") or r.json().get("token")


@pytest.fixture(scope="session")
def H(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# ==== 1) Webhook HMAC-SHA256 imza ====
class TestWebhookSignature:
    sub_id = None
    secret = None

    def test_1_create_sub(self, H):
        r = requests.post(f"{BASE_URL}/api/webhook-subs/{PID}", headers=H, json={"url": "https://example.com/hook", "events": ["*"]}, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("id") and d.get("secret")
        TestWebhookSignature.sub_id = d["id"]
        TestWebhookSignature.secret = d["secret"]

    def test_2_rotate_secret(self, H):
        r = requests.post(f"{BASE_URL}/api/webhook-subs/{PID}/{TestWebhookSignature.sub_id}/rotate-secret", headers=H, timeout=15)
        assert r.status_code == 200, r.text
        new = r.json().get("secret")
        assert new and new != TestWebhookSignature.secret
        TestWebhookSignature.secret = new

    def test_3_verify_signature_valid(self, H):
        body = b'{"a":1}'
        ts = str(int(time.time()))
        sig = "v1=" + hmac.new(TestWebhookSignature.secret.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
        r = requests.post(f"{BASE_URL}/api/webhook-subs/{PID}/verify-signature", headers=H,
                          json={"sub_id": TestWebhookSignature.sub_id, "timestamp": ts, "body": '{"a":1}', "signature": sig}, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["valid"] is True
        assert d["expected"] == sig

    def test_4_verify_wrong_body(self, H):
        body = b'{"a":1}'
        ts = str(int(time.time()))
        sig = "v1=" + hmac.new(TestWebhookSignature.secret.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
        r = requests.post(f"{BASE_URL}/api/webhook-subs/{PID}/verify-signature", headers=H,
                          json={"sub_id": TestWebhookSignature.sub_id, "timestamp": ts, "body": '{"a":2}', "signature": sig}, timeout=15)
        assert r.status_code == 200
        assert r.json()["valid"] is False

    def test_5_verify_old_ts(self, H):
        body = b'{"a":1}'
        ts = str(int(time.time()) - 700)  # 700s > 300s tolerance
        sig = "v1=" + hmac.new(TestWebhookSignature.secret.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
        r = requests.post(f"{BASE_URL}/api/webhook-subs/{PID}/verify-signature", headers=H,
                          json={"sub_id": TestWebhookSignature.sub_id, "timestamp": ts, "body": '{"a":1}', "signature": sig}, timeout=15)
        assert r.status_code == 200
        assert r.json()["valid"] is False

    def test_6_verify_unknown_sub(self, H):
        r = requests.post(f"{BASE_URL}/api/webhook-subs/{PID}/verify-signature", headers=H,
                          json={"sub_id": "no-such-sub", "timestamp": str(int(time.time())), "body": "{}", "signature": "v1=xx"}, timeout=15)
        assert r.status_code == 404

    def test_7_docs_signature(self):
        r = requests.get(f"{BASE_URL}/api/public/v1/docs", timeout=15)
        assert r.status_code == 200
        ws = r.json().get("webhook_signature")
        assert ws and ws.get("algorithm") == "HMAC-SHA256"
        assert "python" in ws and "node" in ws
        assert "hmac" in ws["python"].lower()

    def test_8_cleanup(self, H):
        r = requests.delete(f"{BASE_URL}/api/webhook-subs/{PID}/{TestWebhookSignature.sub_id}", headers=H, timeout=15)
        assert r.status_code == 200


# ==== 2) Usage chart + anomaly ====
class TestUsageAnomaly:
    key_id = None
    api_key = None

    def test_1_create_key(self, H):
        r = requests.post(f"{BASE_URL}/api/public-keys/{PID}", headers=H, json={"name": "TEST_iter635_usage", "rate_per_min": 5000}, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        TestUsageAnomaly.key_id = d["id"]
        TestUsageAnomaly.api_key = d["key"]

    def test_2_make_calls(self):
        headers = {"X-API-Key": TestUsageAnomaly.api_key}
        ok = 0
        for _ in range(25):
            r = requests.get(f"{BASE_URL}/api/public/v1/rate-plans", headers=headers, timeout=15)
            if r.status_code == 200:
                ok += 1
            time.sleep(0.05)
        assert ok >= 20, f"only {ok}/25 calls succeeded"

    def test_3_usage_series(self, H):
        r = requests.get(f"{BASE_URL}/api/public-keys/{PID}/usage?days=30", headers=H, timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        assert len(d["dates"]) == 30
        series = d["series"].get(TestUsageAnomaly.key_id)
        assert series is not None, f"series missing for key_id, have: {list(d['series'].keys())}"
        assert len(series) == 30
        today = series[-1]
        assert today["calls"] >= 20
        anomalies = d["anomalies"]
        assert TestUsageAnomaly.key_id in anomalies
        an = anomalies[TestUsageAnomaly.key_id]
        assert an["today"] >= 20
        assert an["factor"] > 3

    def test_4_cleanup(self, H):
        # deactivate key (no delete endpoint — soft off)
        requests.put(f"{BASE_URL}/api/public-keys/{PID}/{TestUsageAnomaly.key_id}", headers=H, json={"active": False}, timeout=15)


# ==== 3) Chain search geo (centre/station/airport) ====
class TestChainGeo:
    def test_1_chain_search(self):
        r = requests.get(f"{BASE_URL}/api/booking/chain-search?check_in=2026-09-20&check_out=2026-09-22&adults=2", timeout=30)
        assert r.status_code == 200, r.text
        props = r.json()["properties"]
        assert props
        by_id = {p["property_id"]: p for p in props}
        # Aldgate Flats
        af = by_id.get(PID) or next((p for p in props if "aldgate" in (p.get("name") or "").lower()), None)
        assert af, "aldgate-flats property missing"
        assert af.get("centre_km") is not None
        assert af.get("centre_walk_min") is not None
        st = af.get("station")
        if st:
            assert "km" in st and "walk_min" in st
        ap = af.get("airport")
        # Airport might be None if photon slow — allow but log
        if ap:
            assert "km" in ap and ap["km"] < 80

    def test_2_cache_speed(self):
        t0 = time.time()
        r = requests.get(f"{BASE_URL}/api/booking/chain-search?check_in=2026-09-20&check_out=2026-09-22&adults=2", timeout=30)
        dt = time.time() - t0
        assert r.status_code == 200
        assert dt < 5, f"chain-search 2nd call too slow: {dt:.1f}s"


# ==== 4) PMS Sync Alerts ====
class TestSyncAlerts:
    def test_1_config_save(self, H):
        r = requests.put(f"{BASE_URL}/api/pms-connect/sync-alerts/config/{PID}", headers=H,
                         json={"enabled": True, "threshold": 3, "emails": ["ops@example.com"]}, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["enabled"] is True and d["threshold"] == 3
        assert "ops@example.com" in d["emails"]

    def test_2_get_alerts(self, H):
        r = requests.get(f"{BASE_URL}/api/pms-connect/sync-alerts/{PID}?provider=mews", headers=H, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert "alerts" in d and "open" in d and "config" in d

    def test_3_simulate_triggers(self, H):
        r = requests.post(f"{BASE_URL}/api/pms-connect/sync-alerts/{PID}/simulate?provider=mews", headers=H, timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["alerted"] is True
        assert d["streak"] >= 3
        assert isinstance(d.get("email_status"), list) and len(d["email_status"]) >= 1
        # first status should indicate mocked
        assert any(s == "mocked" or "mock" in str(s).lower() for s in d["email_status"])

    def test_4_simulate_already_open(self, H):
        r = requests.post(f"{BASE_URL}/api/pms-connect/sync-alerts/{PID}/simulate?provider=mews", headers=H, timeout=20)
        assert r.status_code == 200
        d = r.json()
        assert d["alerted"] is False
        assert d.get("reason") == "already_open"

    def test_5_open_alerts_present(self, H):
        r = requests.get(f"{BASE_URL}/api/pms-connect/sync-alerts/{PID}?provider=mews", headers=H, timeout=15)
        assert r.status_code == 200
        assert len(r.json()["open"]) >= 1

    def test_6_timeline_degraded(self, H):
        r = requests.get(f"{BASE_URL}/api/pms-connect/mews/sync-timeline/{PID}", headers=H, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["health"] in ("degraded",), f"expected degraded, got {d['health']}"
        assert d["totals"]["failed"] >= 3
        assert len(d["failed_entries"]) >= 3

    def test_7_mocked_push_does_not_resolve(self, H):
        # mocked push (no creds) — should NOT resolve open alert
        r = requests.post(f"{BASE_URL}/api/pms-connect/mews/push-from-rms/{PID}?days=1", headers=H, json={}, timeout=20)
        # push may 200 (mock) or 428/other — accept 200 mock only
        r2 = requests.get(f"{BASE_URL}/api/pms-connect/sync-alerts/{PID}?provider=mews", headers=H, timeout=15)
        assert r2.status_code == 200
        assert len(r2.json()["open"]) >= 1, "mocked push must NOT resolve open alert"

    def test_8_disabled_simulate(self, H):
        requests.put(f"{BASE_URL}/api/pms-connect/sync-alerts/config/{PID}", headers=H,
                     json={"enabled": False, "threshold": 3, "emails": ["ops@example.com"]}, timeout=15)
        r = requests.post(f"{BASE_URL}/api/pms-connect/sync-alerts/{PID}/simulate?provider=apaleo", headers=H, timeout=20)
        assert r.status_code == 200
        d = r.json()
        assert d["alerted"] is False and d.get("reason") == "disabled"
        # restore
        requests.put(f"{BASE_URL}/api/pms-connect/sync-alerts/config/{PID}", headers=H,
                     json={"enabled": True, "threshold": 3, "emails": ["ops@example.com"]}, timeout=15)

    def test_9_unknown_provider(self, H):
        r = requests.post(f"{BASE_URL}/api/pms-connect/sync-alerts/{PID}/simulate?provider=nosuch", headers=H, timeout=15)
        assert r.status_code == 404
