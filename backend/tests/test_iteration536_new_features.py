"""Iteration 536 — Backend tests for 5 new features:
A) Marketing Radar, B) BI Chat, C) Strategy Directives, D) ROI (frontend), E) Parking RMS.
"""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
PID = "default"


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": "admin@hotelbox.com", "password": "HotelAdmin2026!"},
                      timeout=30)
    assert r.status_code == 200, r.text
    return r.json().get("access_token") or r.json().get("token")


@pytest.fixture(scope="module")
def h(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# --- A) Marketing Radar ---
class TestMarketingRadar:
    def test_get_radar(self, h):
        r = requests.get(f"{BASE_URL}/api/marketing-radar/{PID}?days=60", headers=h, timeout=60)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "windows" in d
        assert "scanned_days" in d and d["scanned_days"] > 0
        assert isinstance(d["windows"], list)

    def test_activate_campaign(self, h):
        # Get some low-demand dates first
        r = requests.get(f"{BASE_URL}/api/marketing-radar/{PID}?days=60", headers=h, timeout=60)
        wins = r.json().get("windows", [])
        if not wins:
            pytest.skip("No opportunity windows found for activation test")
        dates = wins[0]["dates"]
        r2 = requests.post(f"{BASE_URL}/api/marketing-radar/{PID}/activate",
                           headers=h, json={"dates": dates}, timeout=30)
        assert r2.status_code == 200, r2.text
        j = r2.json()
        assert j["ok"] is True
        assert len(j["campaign_dates"]) == len(dates[:14])


# --- B) BI Chat ---
class TestBIChat:
    def test_ask_and_history(self, h):
        payload = {"question": "Son 7 günün doluluğu ne?", "session_id": ""}
        r = requests.post(f"{BASE_URL}/api/bi-chat/{PID}", headers=h, json=payload, timeout=90)
        assert r.status_code == 200, r.text
        j = r.json()
        assert "answer" in j and len(j["answer"]) > 0
        assert "session_id" in j
        sid = j["session_id"]

        # Multi-turn (session continuity)
        r2 = requests.post(f"{BASE_URL}/api/bi-chat/{PID}", headers=h,
                           json={"question": "Peki bu ay kanal kırılımı nasıl?", "session_id": sid},
                           timeout=90)
        assert r2.status_code == 200, r2.text
        j2 = r2.json()
        assert j2["session_id"] == sid
        assert len(j2["answer"]) > 0

        # History
        r3 = requests.get(f"{BASE_URL}/api/bi-chat/{PID}/history?session_id={sid}",
                          headers=h, timeout=30)
        assert r3.status_code == 200
        items = r3.json().get("items", [])
        # 2 user + 2 assistant
        assert len(items) >= 4


# --- C) Strategy Directives ---
class TestStrategyDirectives:
    def test_add_list_delete(self, h):
        payload = {"text": "Aralık ayında ADR önceliği, agresif fiyatla"}
        r = requests.post(f"{BASE_URL}/api/strategy-directives/{PID}",
                          headers=h, json=payload, timeout=60)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["text"] == payload["text"]
        assert "parsed" in d
        assert "priority" in d["parsed"]
        did = d["id"]

        # List
        rl = requests.get(f"{BASE_URL}/api/strategy-directives/{PID}", headers=h, timeout=15)
        assert rl.status_code == 200
        assert any(x["id"] == did for x in rl.json()["items"])

        # Delete
        rd = requests.delete(f"{BASE_URL}/api/strategy-directives/{PID}/{did}", headers=h, timeout=15)
        assert rd.status_code == 200

        rl2 = requests.get(f"{BASE_URL}/api/strategy-directives/{PID}", headers=h, timeout=15)
        assert not any(x["id"] == did for x in rl2.json()["items"])

    def test_too_short(self, h):
        r = requests.post(f"{BASE_URL}/api/strategy-directives/{PID}",
                          headers=h, json={"text": "abc"}, timeout=15)
        assert r.status_code == 400


# --- E) Parking RMS ---
class TestParkingRMS:
    def test_get(self, h):
        r = requests.get(f"{BASE_URL}/api/parking-rms/{PID}", headers=h, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "days" in d and len(d["days"]) == 14
        assert "avg_revpas" in d
        for row in d["days"]:
            assert "date" in row and "suggested_price" in row

    def test_save_settings(self, h):
        r = requests.post(f"{BASE_URL}/api/parking-rms/{PID}/settings",
                          headers=h, json={"spaces": 25, "base_rate": 20.0}, timeout=15)
        assert r.status_code == 200
        assert r.json()["spaces"] == 25
        assert r.json()["base_rate"] == 20.0
        # Verify persistence via GET
        r2 = requests.get(f"{BASE_URL}/api/parking-rms/{PID}", headers=h, timeout=30)
        assert r2.json()["spaces"] == 25
        assert r2.json()["base_rate"] == 20.0
