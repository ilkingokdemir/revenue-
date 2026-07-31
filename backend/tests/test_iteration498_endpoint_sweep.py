"""Iteration 498: Full backend GET endpoint sweep from OpenAPI schema.

Goal: Find HTTP 500s across all GET endpoints using admin token, with
sensible defaults for path parameters.
"""
import os
import re
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://review-hub-108.preview.emergentagent.com").rstrip("/")

ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"

# Path-param default values (best-effort; 404 is OK, only 500 is a bug)
PARAM_DEFAULTS = {
    "property_id": "default",
    "propertyId": "default",
    "property": "default",
    "date": "2026-01-15",
    "start_date": "2026-01-01",
    "end_date": "2026-01-31",
    "from_date": "2026-01-01",
    "to_date": "2026-01-31",
    "year": "2026",
    "month": "01",
    "day": "15",
    "id": "test-id",
    "user_id": "test-user",
    "room_id": "test-room",
    "guest_id": "test-guest",
    "booking_id": "test-booking",
    "reservation_id": "test-reservation",
    "owner_id": "dd497e9d-4382-4d70-9814-13cd3bbd8355",
    "unit_id": "test-unit",
    "channel_id": "test-channel",
    "campaign_id": "test-campaign",
    "template_id": "test-template",
    "task_id": "test-task",
    "order_id": "test-order",
    "invoice_id": "test-invoice",
    "vendor_id": "test-vendor",
    "employee_id": "test-employee",
    "shift_id": "test-shift",
    "code": "TEST",
    "key": "test-key",
    "slug": "test",
    "type": "default",
    "category": "default",
    "status": "active",
    "name": "test",
    "email": "test@example.com",
    "phone": "+905551234567",
    "token": "test-token",
    "session_id": "test-session",
    "path": "test",
}


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=30,
    )
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text[:200]}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def openapi_schema():
    r = requests.get(f"{BASE_URL}/api/openapi.json", timeout=120)
    assert r.status_code == 200, f"openapi.json failed: {r.status_code}"
    return r.json()


def _substitute_path(path: str) -> str:
    def repl(m):
        name = m.group(1)
        return str(PARAM_DEFAULTS.get(name, "test"))
    return re.sub(r"\{([^}]+)\}", repl, path)


def test_openapi_available(openapi_schema):
    assert "paths" in openapi_schema
    assert len(openapi_schema["paths"]) > 0


def test_get_endpoints_no_500(admin_token, openapi_schema):
    """Sweep every GET endpoint; fail listing all 500s."""
    headers = {"Authorization": f"Bearer {admin_token}"}
    paths = openapi_schema["paths"]

    errors_500 = []
    unexpected_4xx = []  # 400/422 without params - potential bug
    checked = 0

    # Skip patterns that are known to be intentionally long / mutating / heavy scrapers
    skip_patterns = [
        "/api/auth/logout",
        "/download",
        "/export",
        "/pdf",
        "/stream",
        "/sse",
        "/websocket",
        "/ws/",
        "/openapi",
        "/scrape",
        "/scraper",
        "/scan",
        "/vision",
        "/enrich",
        "/booking-com",
        "/warm-up",
        "/screenshot",
        "/generate-video",
        "/sora",
    ]

    for path, methods in paths.items():
        if "get" not in methods:
            continue
        if any(sp in path for sp in skip_patterns):
            continue
        if not path.startswith("/api"):
            continue

        real_path = _substitute_path(path)
        url = f"{BASE_URL}{real_path}"

        # Query params: add common defaults
        params = {"property_id": "default", "limit": 5}

        try:
            r = requests.get(url, headers=headers, params=params, timeout=15)
        except requests.RequestException as e:
            errors_500.append((path, f"REQUEST-ERROR: {type(e).__name__} {str(e)[:120]}"))
            continue

        checked += 1
        if r.status_code >= 500:
            errors_500.append((path, f"{r.status_code} {r.text[:200]}"))
        elif r.status_code == 400 and "{" not in path:
            # 400 on no-param endpoint may indicate a bug
            unexpected_4xx.append((path, f"400 {r.text[:150]}"))

    # Save results to a report file for the main agent
    report_path = "/app/test_reports/iteration_498_endpoint_sweep.txt"
    with open(report_path, "w") as f:
        f.write(f"Checked: {checked} GET endpoints\n")
        f.write(f"500 errors: {len(errors_500)}\n\n")
        for p, e in errors_500:
            f.write(f"[500] {p} -> {e}\n")
        f.write(f"\nSuspicious 400s: {len(unexpected_4xx)}\n")
        for p, e in unexpected_4xx:
            f.write(f"[400] {p} -> {e}\n")

    print(f"\n=== Endpoint sweep complete: {checked} checked, {len(errors_500)} 500s, {len(unexpected_4xx)} suspicious 400s ===")
    for p, e in errors_500[:30]:
        print(f"  500 {p} -> {e[:120]}")

    assert not errors_500, f"{len(errors_500)} endpoints returned 500. See {report_path}"
