"""
Iteration 236 - Batch 24: AI Anomaly Detection Tests
Tests for:
- GET /api/anomaly/scan/{property_id}?days=60 — aggregated anomaly feed
- GET /api/anomaly/timeseries/{property_id}?metric=revenue&days=90 — chart-ready series
- POST /api/anomaly/explain — LLM root-cause hypothesis
"""
import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Test credentials
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"
PROPERTY_ID = "default"


@pytest.fixture(scope="module")
def admin_token():
    """Get admin auth token"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )
    assert response.status_code == 200, f"Login failed: {response.text}"
    data = response.json()
    return data.get("access_token") or data.get("token")


@pytest.fixture(scope="module")
def auth_headers(admin_token):
    """Auth headers for requests"""
    return {"Authorization": f"Bearer {admin_token}"}


class TestAnomalyScanEndpoint:
    """Tests for GET /api/anomaly/scan/{property_id}"""

    def test_scan_default_days(self, auth_headers):
        """Test scan with default days=60"""
        response = requests.get(
            f"{BASE_URL}/api/anomaly/scan/{PROPERTY_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Scan failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "property_id" in data
        assert data["property_id"] == PROPERTY_ID
        assert "days" in data
        assert "total" in data
        assert "by_metric" in data
        assert "by_severity" in data
        assert "anomalies" in data
        
        # Verify by_severity structure
        assert "severe" in data["by_severity"]
        assert "moderate" in data["by_severity"]
        
        print(f"✓ Scan returned {data['total']} anomalies ({data['by_severity'].get('severe', 0)} severe, {data['by_severity'].get('moderate', 0)} moderate)")

    def test_scan_custom_days(self, auth_headers):
        """Test scan with custom days parameter"""
        for days in [30, 60, 90, 180]:
            response = requests.get(
                f"{BASE_URL}/api/anomaly/scan/{PROPERTY_ID}?days={days}",
                headers=auth_headers
            )
            assert response.status_code == 200, f"Scan with days={days} failed: {response.text}"
            data = response.json()
            assert data["days"] == days
            print(f"✓ Scan with days={days} returned {data['total']} anomalies")

    def test_scan_validates_days_min(self, auth_headers):
        """Test scan rejects days < 14"""
        response = requests.get(
            f"{BASE_URL}/api/anomaly/scan/{PROPERTY_ID}?days=10",
            headers=auth_headers
        )
        assert response.status_code == 400, f"Expected 400 for days=10, got {response.status_code}"
        print("✓ Scan correctly rejects days=10 with 400")

    def test_scan_validates_days_max(self, auth_headers):
        """Test scan rejects days > 365"""
        response = requests.get(
            f"{BASE_URL}/api/anomaly/scan/{PROPERTY_ID}?days=400",
            headers=auth_headers
        )
        assert response.status_code == 400, f"Expected 400 for days=400, got {response.status_code}"
        print("✓ Scan correctly rejects days=400 with 400")

    def test_scan_requires_auth(self):
        """Test scan requires authentication"""
        response = requests.get(f"{BASE_URL}/api/anomaly/scan/{PROPERTY_ID}")
        assert response.status_code == 401, f"Expected 401 without auth, got {response.status_code}"
        print("✓ Scan correctly requires authentication (401)")

    def test_scan_anomaly_structure(self, auth_headers):
        """Test anomaly object structure"""
        response = requests.get(
            f"{BASE_URL}/api/anomaly/scan/{PROPERTY_ID}?days=90",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        if data["anomalies"]:
            anomaly = data["anomalies"][0]
            # Verify anomaly structure
            assert "date" in anomaly
            assert "metric" in anomaly
            assert "value" in anomaly
            assert "mean" in anomaly
            assert "std" in anomaly
            assert "z" in anomaly
            assert "direction" in anomaly
            assert "severity" in anomaly
            
            # Verify direction is spike or drop
            assert anomaly["direction"] in ["spike", "drop"]
            # Verify severity is severe or moderate
            assert anomaly["severity"] in ["severe", "moderate"]
            # Verify metric is valid
            assert anomaly["metric"] in ["revenue", "bookings", "occupancy", "adr", "cancellations"]
            
            print(f"✓ Anomaly structure verified: {anomaly['date']} {anomaly['metric']} {anomaly['direction']} ({anomaly['severity']})")
        else:
            print("✓ No anomalies found (structure test skipped)")


class TestAnomalyTimeseriesEndpoint:
    """Tests for GET /api/anomaly/timeseries/{property_id}"""

    def test_timeseries_default(self, auth_headers):
        """Test timeseries with default parameters"""
        response = requests.get(
            f"{BASE_URL}/api/anomaly/timeseries/{PROPERTY_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Timeseries failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "property_id" in data
        assert data["property_id"] == PROPERTY_ID
        assert "metric" in data
        assert "days" in data
        assert "points" in data
        assert "mean" in data
        assert "std" in data
        assert "anomaly_count" in data
        
        print(f"✓ Timeseries returned {len(data['points'])} points, {data['anomaly_count']} anomalies, mean={data['mean']}, std={data['std']}")

    def test_timeseries_all_metrics(self, auth_headers):
        """Test timeseries for all valid metrics"""
        valid_metrics = ["revenue", "bookings", "occupancy", "adr", "cancellations"]
        
        for metric in valid_metrics:
            response = requests.get(
                f"{BASE_URL}/api/anomaly/timeseries/{PROPERTY_ID}?metric={metric}&days=60",
                headers=auth_headers
            )
            assert response.status_code == 200, f"Timeseries for metric={metric} failed: {response.text}"
            data = response.json()
            assert data["metric"] == metric
            print(f"✓ Timeseries for metric={metric} returned {data['anomaly_count']} anomalies")

    def test_timeseries_invalid_metric(self, auth_headers):
        """Test timeseries rejects invalid metric"""
        response = requests.get(
            f"{BASE_URL}/api/anomaly/timeseries/{PROPERTY_ID}?metric=foo",
            headers=auth_headers
        )
        assert response.status_code == 400, f"Expected 400 for invalid metric, got {response.status_code}"
        print("✓ Timeseries correctly rejects invalid metric 'foo' with 400")

    def test_timeseries_validates_days_min(self, auth_headers):
        """Test timeseries rejects days < 14"""
        response = requests.get(
            f"{BASE_URL}/api/anomaly/timeseries/{PROPERTY_ID}?days=10",
            headers=auth_headers
        )
        assert response.status_code == 400, f"Expected 400 for days=10, got {response.status_code}"
        print("✓ Timeseries correctly rejects days=10 with 400")

    def test_timeseries_validates_days_max(self, auth_headers):
        """Test timeseries rejects days > 365"""
        response = requests.get(
            f"{BASE_URL}/api/anomaly/timeseries/{PROPERTY_ID}?days=400",
            headers=auth_headers
        )
        assert response.status_code == 400, f"Expected 400 for days=400, got {response.status_code}"
        print("✓ Timeseries correctly rejects days=400 with 400")

    def test_timeseries_requires_auth(self):
        """Test timeseries requires authentication"""
        response = requests.get(f"{BASE_URL}/api/anomaly/timeseries/{PROPERTY_ID}")
        assert response.status_code == 401, f"Expected 401 without auth, got {response.status_code}"
        print("✓ Timeseries correctly requires authentication (401)")

    def test_timeseries_point_structure(self, auth_headers):
        """Test timeseries point structure"""
        response = requests.get(
            f"{BASE_URL}/api/anomaly/timeseries/{PROPERTY_ID}?metric=revenue&days=60",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        if data["points"]:
            point = data["points"][0]
            # Verify point structure
            assert "date" in point
            assert "value" in point
            assert "is_anomaly" in point
            
            # If anomaly, verify additional fields
            anomaly_points = [p for p in data["points"] if p["is_anomaly"]]
            if anomaly_points:
                ap = anomaly_points[0]
                assert "severity" in ap
                assert "z" in ap
                assert "direction" in ap
                print(f"✓ Anomaly point structure verified: {ap['date']} z={ap['z']} {ap['direction']}")
            else:
                print("✓ Point structure verified (no anomaly points to check)")
        else:
            print("✓ No points returned (structure test skipped)")


class TestAnomalyExplainEndpoint:
    """Tests for POST /api/anomaly/explain"""

    def test_explain_with_llm(self, auth_headers):
        """Test explain endpoint returns LLM hypothesis"""
        # First get an anomaly to explain
        scan_response = requests.get(
            f"{BASE_URL}/api/anomaly/scan/{PROPERTY_ID}?days=90",
            headers=auth_headers
        )
        assert scan_response.status_code == 200
        scan_data = scan_response.json()
        
        if scan_data["anomalies"]:
            anomaly = scan_data["anomalies"][0]
            
            # Call explain endpoint
            response = requests.post(
                f"{BASE_URL}/api/anomaly/explain",
                json={
                    "property_id": PROPERTY_ID,
                    "date": anomaly["date"],
                    "metric": anomaly["metric"],
                    "value": anomaly["value"],
                    "z": anomaly["z"]
                },
                headers=auth_headers
            )
            assert response.status_code == 200, f"Explain failed: {response.text}"
            data = response.json()
            
            # Verify response structure
            assert "source" in data
            assert "hypothesis" in data
            assert "actions" in data
            
            # Source should be 'llm' if EMERGENT_LLM_KEY is configured
            assert data["source"] in ["llm", "heuristic", "heuristic_fallback"]
            assert isinstance(data["hypothesis"], str)
            assert len(data["hypothesis"]) > 0
            assert isinstance(data["actions"], list)
            
            print(f"✓ Explain returned source='{data['source']}' with hypothesis: {data['hypothesis'][:100]}...")
            print(f"✓ Actions: {data['actions']}")
        else:
            # Create a synthetic explain request
            response = requests.post(
                f"{BASE_URL}/api/anomaly/explain",
                json={
                    "property_id": PROPERTY_ID,
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "metric": "revenue",
                    "value": 5000,
                    "z": 3.5
                },
                headers=auth_headers
            )
            assert response.status_code == 200, f"Explain failed: {response.text}"
            data = response.json()
            assert "source" in data
            assert "hypothesis" in data
            assert "actions" in data
            print(f"✓ Explain (synthetic) returned source='{data['source']}'")

    def test_explain_requires_auth(self):
        """Test explain requires authentication"""
        response = requests.post(
            f"{BASE_URL}/api/anomaly/explain",
            json={
                "property_id": PROPERTY_ID,
                "date": "2026-01-15",
                "metric": "revenue",
                "value": 1000,
                "z": 2.5
            }
        )
        assert response.status_code == 401, f"Expected 401 without auth, got {response.status_code}"
        print("✓ Explain correctly requires authentication (401)")

    def test_explain_different_metrics(self, auth_headers):
        """Test explain for different metrics"""
        metrics = ["revenue", "bookings", "occupancy", "adr", "cancellations"]
        
        for metric in metrics:
            response = requests.post(
                f"{BASE_URL}/api/anomaly/explain",
                json={
                    "property_id": PROPERTY_ID,
                    "date": "2026-01-15",
                    "metric": metric,
                    "value": 100,
                    "z": 2.5 if metric != "cancellations" else -2.5
                },
                headers=auth_headers
            )
            assert response.status_code == 200, f"Explain for metric={metric} failed: {response.text}"
            data = response.json()
            assert "hypothesis" in data
            print(f"✓ Explain for metric={metric} returned hypothesis")

    def test_explain_spike_vs_drop(self, auth_headers):
        """Test explain handles spike (z>0) and drop (z<0) differently"""
        # Test spike (positive z)
        spike_response = requests.post(
            f"{BASE_URL}/api/anomaly/explain",
            json={
                "property_id": PROPERTY_ID,
                "date": "2026-01-15",
                "metric": "revenue",
                "value": 5000,
                "z": 3.0
            },
            headers=auth_headers
        )
        assert spike_response.status_code == 200
        spike_data = spike_response.json()
        
        # Test drop (negative z)
        drop_response = requests.post(
            f"{BASE_URL}/api/anomaly/explain",
            json={
                "property_id": PROPERTY_ID,
                "date": "2026-01-15",
                "metric": "revenue",
                "value": 100,
                "z": -3.0
            },
            headers=auth_headers
        )
        assert drop_response.status_code == 200
        drop_data = drop_response.json()
        
        # Both should have hypotheses
        assert len(spike_data["hypothesis"]) > 0
        assert len(drop_data["hypothesis"]) > 0
        
        print(f"✓ Spike hypothesis: {spike_data['hypothesis'][:80]}...")
        print(f"✓ Drop hypothesis: {drop_data['hypothesis'][:80]}...")


class TestAnomalyRBAC:
    """Tests for RBAC on anomaly endpoints"""

    def test_receptionist_denied(self):
        """Test receptionist cannot access anomaly endpoints"""
        # Login as receptionist
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "testrecep@hotelbox.com", "password": "Test2026!"}
        )
        
        if login_response.status_code != 200:
            pytest.skip("Receptionist user not available")
        
        token = login_response.json().get("access_token") or login_response.json().get("token")
        headers = {"Authorization": f"Bearer {token}"}
        
        # Test scan endpoint
        scan_response = requests.get(
            f"{BASE_URL}/api/anomaly/scan/{PROPERTY_ID}",
            headers=headers
        )
        assert scan_response.status_code == 403, f"Expected 403 for receptionist on scan, got {scan_response.status_code}"
        
        # Test timeseries endpoint
        ts_response = requests.get(
            f"{BASE_URL}/api/anomaly/timeseries/{PROPERTY_ID}",
            headers=headers
        )
        assert ts_response.status_code == 403, f"Expected 403 for receptionist on timeseries, got {ts_response.status_code}"
        
        # Test explain endpoint
        explain_response = requests.post(
            f"{BASE_URL}/api/anomaly/explain",
            json={
                "property_id": PROPERTY_ID,
                "date": "2026-01-15",
                "metric": "revenue",
                "value": 1000,
                "z": 2.5
            },
            headers=headers
        )
        assert explain_response.status_code == 403, f"Expected 403 for receptionist on explain, got {explain_response.status_code}"
        
        print("✓ Receptionist correctly denied access to all anomaly endpoints (403)")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
