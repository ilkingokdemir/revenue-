"""Iter 378 regression: perf fixes + reports/preview + diagnostics/tasks."""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
ADMIN = {"email": "admin@hotelbox.com", "password": "HotelAdmin2026!"}


@pytest.fixture(scope="module")
def token():
    for _ in range(3):
        r = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN, timeout=30)
        if r.status_code == 200:
            return r.json().get("token") or r.json().get("access_token")
        time.sleep(2)
    pytest.skip(f"login failed: {r.status_code} {r.text[:200]}")


@pytest.fixture(scope="module")
def h(token):
    return {"Authorization": f"Bearer {token}"}


PERF_ENDPOINTS = [
    "/api/crm/segments",
    "/api/crm/winback/candidates",
    "/api/loyalty-tiers/members",
    "/api/pms-crs/conflicts",
    "/api/revenue/heatmap",
    "/api/revenue/yoy-tables",
]


@pytest.mark.parametrize("ep", PERF_ENDPOINTS)
def test_perf_endpoint(h, ep):
    t0 = time.time()
    r = requests.get(f"{BASE_URL}{ep}", headers=h, timeout=20)
    dt = time.time() - t0
    assert r.status_code == 200, f"{ep} -> {r.status_code} {r.text[:200]}"
    assert dt < 15, f"{ep} too slow: {dt:.1f}s"
    print(f"OK {ep} {dt:.2f}s")


def test_reports_preview(h):
    r = requests.get(f"{BASE_URL}/api/reports/preview", headers=h, timeout=30)
    assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
    data = r.json()
    assert "html" in data
    assert isinstance(data["html"], str) and len(data["html"]) > 0


def test_diagnostics_tasks(h):
    r = requests.get(f"{BASE_URL}/api/admin/diagnostics/tasks", headers=h, timeout=15)
    assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
    data = r.json()
    total = data.get("total_tasks", data.get("total", 0))
    assert isinstance(total, int), f"total_tasks not int: {data}"
    assert total < 100, f"task leak: {total} tasks"
    print(f"total_tasks={total}")
