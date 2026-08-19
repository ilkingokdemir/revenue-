"""Batch tests: Site Builder + Terminal + Presets + AI Copilot."""
import os
import uuid
import time
import pytest
import requests
from pymongo import MongoClient

BASE = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE:
    # fallback to reading frontend .env
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE = line.split("=", 1)[1].strip().rstrip("/")

API = f"{BASE}/api"
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PW = "HotelAdmin2026!"


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PW})
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def h(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def mongo_db():
    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME")
    if not mongo_url:
        # read from backend/.env
        with open("/app/backend/.env") as f:
            for line in f:
                if line.startswith("MONGO_URL="):
                    mongo_url = line.split("=", 1)[1].strip().strip('"').strip("'")
                elif line.startswith("DB_NAME="):
                    db_name = line.split("=", 1)[1].strip().strip('"').strip("'")
    return MongoClient(mongo_url)[db_name]


# =========== Site Builder ===========
class TestSiteBuilder:
    def test_get_default(self, h):
        r = requests.get(f"{API}/site-builder/default", headers=h)
        assert r.status_code == 200
        assert "site" in r.json() and "templates" in r.json()

    def test_invalid_template_422(self, h):
        r = requests.post(f"{API}/site-builder/default",
                          json={"template": "bogus", "content": {}, "published": False}, headers=h)
        assert r.status_code == 422

    def test_save_unpublished_then_public_404(self, h):
        r = requests.post(f"{API}/site-builder/default",
                          json={"template": "boutique",
                                "content": {"headline": "temp", "about": "x"},
                                "published": False}, headers=h)
        assert r.status_code == 200
        # public should 404
        r2 = requests.get(f"{API}/site-builder/public/site/default")
        assert r2.status_code == 404

    def test_publish_modern_and_public_ok(self, h):
        # Final: leave site published with modern template + specific headline
        r = requests.post(f"{API}/site-builder/default",
                          json={"template": "modern",
                                "content": {"headline": "Şehrin kalbinde konfor",
                                            "about": "Konforlu konaklama",
                                            "amenities": "Ücretsiz Wi-Fi, Kahvaltı, Spa",
                                            "phone": "+90 000",
                                            "email": "info@hotel.tr",
                                            "address": "Istanbul"},
                                "published": True}, headers=h)
        assert r.status_code == 200
        assert r.json().get("published") is True

        r2 = requests.get(f"{API}/site-builder/public/site/default")
        assert r2.status_code == 200, r2.text
        data = r2.json()
        assert "site" in data and "property" in data and "room_types" in data
        assert data["site"]["template"] == "modern"
        assert data["site"]["content"]["headline"] == "Şehrin kalbinde konfor"


# =========== Terminal ===========
class TestTerminal:
    def test_register_simulated_reader(self, h, request):
        r = requests.post(f"{API}/terminal/default/readers/register",
                          json={"registration_code": "simulated-wpe", "label": "TEST_Sim"}, headers=h)
        assert r.status_code == 200, r.text
        j = r.json()
        assert j.get("simulated") is True
        assert j["reader"]["id"].startswith("tmr_")
        request.config._reader_id = j["reader"]["id"]

    def test_list_readers(self, h):
        r = requests.get(f"{API}/terminal/default/readers", headers=h)
        assert r.status_code == 200
        assert isinstance(r.json().get("readers"), list)
        assert len(r.json()["readers"]) >= 1

    def test_charge_missing_amount_400(self, h, request):
        rid = getattr(request.config, "_reader_id", None)
        r = requests.post(f"{API}/terminal/default/charge",
                          json={"reader_id": rid}, headers=h)
        assert r.status_code == 400

    def test_charge_succeeded(self, h, request):
        rid = getattr(request.config, "_reader_id", None)
        assert rid, "reader missing"
        r = requests.post(f"{API}/terminal/default/charge",
                          json={"amount": 10.5, "reader_id": rid, "booking_id": "t1"}, headers=h)
        assert r.status_code == 200, r.text
        pay = r.json()["payment"]
        assert pay["status"] == "succeeded", pay
        assert pay["amount"] == 10.5

    def test_payments_log(self, h):
        r = requests.get(f"{API}/terminal/default/payments", headers=h)
        assert r.status_code == 200
        assert any(p.get("status") == "succeeded" for p in r.json()["payments"])


# =========== AI Copilot ===========
class TestAiCopilot:
    def test_summary(self, h):
        r = requests.get(f"{API}/ai-copilot/summary/default", headers=h)
        assert r.status_code == 200
        j = r.json()
        expected = {"copilot_pending", "guard_actions_24h", "open_conflicts",
                    "unread_ai_alerts", "comp_triggers_on", "autopilot_on"}
        assert expected.issubset(j.keys())
        for k in expected:
            assert isinstance(j[k], int), f"{k} not int: {j[k]}"


# =========== Presets ===========
class TestPresets:
    def test_catalog_5(self, h):
        r = requests.get(f"{API}/property-presets", headers=h)
        assert r.status_code == 200
        assert len(r.json()["presets"]) == 5

    def test_invalid_preset_422(self, h):
        # use a scratch pid so it doesn't matter
        pid = f"TEST_{uuid.uuid4().hex[:8]}"
        r = requests.post(f"{API}/property-presets/apply/{pid}",
                          json={"preset": "bogus"}, headers=h)
        assert r.status_code == 422

    def test_apply_hostel_on_temp(self, h, mongo_db):
        pid = f"TEST_scratch_{uuid.uuid4().hex[:8]}"
        # Create scratch property directly in DB
        mongo_db.properties.insert_one({"id": pid, "name": "TEST_ScratchHotel",
                                        "tenant_id": "TEST_tenant", "plan": "trial"})
        try:
            r = requests.post(f"{API}/property-presets/apply/{pid}",
                              json={"preset": "hostel"}, headers=h)
            assert r.status_code == 200, r.text
            j = r.json()
            assert j["preset"] == "hostel"
            assert j["room_types_created"] == 2
            assert j["rooms_skipped"] is False
            assert j["rms_defaults"]["base_price"] == 22
            # rms_setup persisted
            rs = mongo_db.rms_setup.find_one({"property_id": pid})
            assert rs and rs["mode"] == "autopilot"

            # apply again should skip room creation
            r2 = requests.post(f"{API}/property-presets/apply/{pid}",
                               json={"preset": "hostel"}, headers=h)
            assert r2.status_code == 200
            assert r2.json()["rooms_skipped"] is True
            assert r2.json()["room_types_created"] == 0
        finally:
            # CLEANUP
            mongo_db.room_types.delete_many({"property_id": pid})
            mongo_db.rms_setup.delete_many({"property_id": pid})
            mongo_db.properties.delete_many({"id": pid})
