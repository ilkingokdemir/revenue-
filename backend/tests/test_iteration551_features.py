"""Iteration 551 — Drift Alerts, Live Forecast Comparison, Rate Plan Mapping."""
import os
import datetime
import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
PID = "default"
ADMIN = {"email": "admin@hotelbox.com", "password": "HotelAdmin2026!"}

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")


@pytest.fixture(scope="module")
def db():
    return MongoClient(MONGO_URL)[DB_NAME]


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{BASE_URL}/api/auth/login", json=ADMIN)
    assert r.status_code == 200, f"Login failed: {r.text[:200]}"
    tok = r.json().get("access_token") or r.json().get("token")
    s.headers.update({"Authorization": f"Bearer {tok}"})
    return s


# ============ FEATURE 1: DRIFT ALERTS ============
def test_alerts_empty_initially(client, db):
    # Cleanup any prior test alerts
    db.pms_alerts.delete_many({"id": {"$regex": "^test-alert-"}})
    r = client.get(f"{BASE_URL}/api/pms-connect/alerts/{PID}")
    assert r.status_code == 200, r.text
    d = r.json()
    assert "alerts" in d and isinstance(d["alerts"], list)
    assert "active_count" in d and isinstance(d["active_count"], int)


def test_alert_insert_get_resolve_flow(client, db):
    db.pms_alerts.delete_many({"id": "test-alert-1"})
    now = datetime.datetime.utcnow().isoformat()
    db.pms_alerts.insert_one({
        "id": "test-alert-1",
        "property_id": PID,
        "provider": "mews",
        "type": "push_drift",
        "max_drift_pct": 2.5,
        "created_at": now,
    })
    r = client.get(f"{BASE_URL}/api/pms-connect/alerts/{PID}")
    assert r.status_code == 200
    d = r.json()
    ids = [a.get("id") for a in d["alerts"]]
    assert "test-alert-1" in ids, f"inserted alert not returned: {ids}"
    assert d["active_count"] >= 1

    r = client.post(f"{BASE_URL}/api/pms-connect/alerts/test-alert-1/resolve", json={})
    assert r.status_code == 200, r.text
    assert r.json().get("ok") is True

    r = client.get(f"{BASE_URL}/api/pms-connect/alerts/{PID}")
    d = r.json()
    ids = [a.get("id") for a in d["alerts"]]
    assert "test-alert-1" not in ids, "alert still active after resolve"

    r = client.post(f"{BASE_URL}/api/pms-connect/alerts/nonexistent-xyz/resolve", json={})
    assert r.status_code == 404


def test_health_has_active_alerts_field(client):
    r = client.get(f"{BASE_URL}/api/pms-connect/health/{PID}")
    assert r.status_code == 200
    d = r.json()
    assert "active_alerts" in d, f"active_alerts missing: {list(d.keys())}"
    assert isinstance(d["active_alerts"], int)


def test_morning_report_includes_drift_anomaly(client, db):
    # Insert a fresh unresolved alert
    db.pms_alerts.delete_many({"id": "test-alert-mr"})
    now = datetime.datetime.utcnow().isoformat()
    db.pms_alerts.insert_one({
        "id": "test-alert-mr",
        "property_id": PID,
        "provider": "mews",
        "type": "push_drift",
        "max_drift_pct": 3.1,
        "created_at": now,
    })
    r = client.post(f"{BASE_URL}/api/morning-report/{PID}/run", json={}, timeout=90)
    assert r.status_code == 200, r.text
    d = r.json()
    audit = d.get("audit") or d
    anomalies = audit.get("anomalies") or d.get("anomalies") or []
    joined = " ".join([str(a) for a in anomalies])
    assert "Dağıtım" in joined or "drift" in joined.lower() or "dağıtım" in joined.lower(), \
        f"expected drift anomaly in anomalies: {anomalies}"
    # cleanup
    db.pms_alerts.delete_many({"id": "test-alert-mr"})


# ============ FEATURE 2: FORECAST ACCURACY ============
def test_forecast_accuracy_shape(client):
    r = client.get(f"{BASE_URL}/api/pms-connect/forecast-accuracy/{PID}", timeout=60)
    assert r.status_code == 200, r.text
    d = r.json()
    assert "mae_occ_pts" in d
    assert "matured_points" in d and isinstance(d["matured_points"], int)
    assert "mews_impact" in d and isinstance(d["mews_impact"], list)
    assert len(d["mews_impact"]) == 14, f"expected 14 rows, got {len(d['mews_impact'])}"
    for row in d["mews_impact"]:
        assert "otb_with_mews" in row
        assert "otb_without_mews" in row
        assert "mews_contribution" in row
    assert "mews_total_contribution_14d" in d
    assert d["mews_total_contribution_14d"] >= 0


def test_morning_report_saves_forecast_snapshot(client, db):
    r = client.post(f"{BASE_URL}/api/morning-report/{PID}/run", json={}, timeout=90)
    assert r.status_code == 200
    today = datetime.date.today().isoformat()
    snap = db.forecast_snapshots.find_one({"property_id": PID, "snapshot_date": today})
    assert snap is not None, "no snapshot doc for today"
    rows = snap.get("rows") or snap.get("forecast") or snap.get("data") or []
    assert len(rows) == 14, f"expected 14 rows in snapshot, got {len(rows)}"


# ============ FEATURE 3: RATE PLAN MAPPING ============
def test_rate_mapping_get(client):
    r = client.get(f"{BASE_URL}/api/pms-connect/mews/rate-mapping/{PID}")
    assert r.status_code == 200, r.text
    d = r.json()
    assert "mappings" in d and isinstance(d["mappings"], list)
    assert "room_types" in d and isinstance(d["room_types"], list)
    # Expect 2 mappings pre-saved per problem statement
    assert len(d["mappings"]) >= 2, f"expected >=2 mappings, got {len(d['mappings'])}"


def test_rate_mapping_save_persist(client):
    # Read current
    r = client.get(f"{BASE_URL}/api/pms-connect/mews/rate-mapping/{PID}")
    original = r.json()
    mappings = original["mappings"]
    assert len(mappings) >= 1

    # Modify multiplier of first mapping (round-trip)
    first = dict(mappings[0])
    orig_mult = first.get("multiplier", 1.0)
    new_mult = round(orig_mult + 0.05, 2)
    first["multiplier"] = new_mult
    updated = [first] + mappings[1:]

    r = client.post(
        f"{BASE_URL}/api/pms-connect/mews/rate-mapping/{PID}",
        json={"mappings": updated},
    )
    assert r.status_code == 200, r.text

    r = client.get(f"{BASE_URL}/api/pms-connect/mews/rate-mapping/{PID}")
    d = r.json()
    saved_mult = d["mappings"][0].get("multiplier")
    assert abs(saved_mult - new_mult) < 1e-6, f"multiplier not persisted: {saved_mult} vs {new_mult}"

    # Restore original
    restored = [{**mappings[0], "multiplier": orig_mult}] + mappings[1:]
    client.post(f"{BASE_URL}/api/pms-connect/mews/rate-mapping/{PID}", json={"mappings": restored})


def test_push_from_rms_mews_mapping_loop_live(client):
    r = client.post(
        f"{BASE_URL}/api/pms-connect/mews/push-from-rms/{PID}",
        json={"days": 2},
        timeout=180,
    )
    assert r.status_code == 200, r.text
    d = r.json()
    assert "per_room_type" in d, f"per_room_type missing: {list(d.keys())}"
    assert isinstance(d["per_room_type"], list)
    assert len(d["per_room_type"]) == 2, f"expected 2 room-type entries, got {len(d['per_room_type'])}"
    for entry in d["per_room_type"]:
        assert entry.get("mocked") is False, f"expected live push, got mocked: {entry}"
    assert "2/2" in str(d.get("message", "")), f"message mismatch: {d.get('message')}"


def test_push_from_rms_siteminder_translated(client):
    r = client.post(
        f"{BASE_URL}/api/pms-connect/siteminder/push-from-rms/{PID}",
        json={"days": 2},
    )
    assert r.status_code == 200, r.text
    d = r.json()
    # siteminder has no mapping saved -> single push with translated_preview
    assert "translated_preview" in d or "per_room_type" in d, \
        f"expected translated_preview or per_room_type: {list(d.keys())}"


# ============ REGRESSIONS ============
def test_regression_verify_push_mews_live(client):
    r = client.post(f"{BASE_URL}/api/pms-connect/mews/verify-push/{PID}", json={}, timeout=120)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d.get("ok") is True
    assert d.get("mocked") is False


def test_regression_weekly_report(client):
    r = client.get(f"{BASE_URL}/api/pms-connect/weekly-report/{PID}", timeout=60)
    assert r.status_code == 200


def test_regression_night_push_run(client):
    client.post(f"{BASE_URL}/api/pms-connect/night-push/{PID}", json={"enabled": True})
    r = client.post(f"{BASE_URL}/api/pms-connect/night-push/{PID}/run", json={}, timeout=180)
    assert r.status_code == 200
    client.post(f"{BASE_URL}/api/pms-connect/night-push/{PID}", json={"enabled": False})


def test_regression_ai_pricing_suggestions(client):
    r = client.get(
        f"{BASE_URL}/api/revenue/ai-pricing/{PID}/suggestions?days=3&use_llm=false",
        timeout=60,
    )
    assert r.status_code == 200
