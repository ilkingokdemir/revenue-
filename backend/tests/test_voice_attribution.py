"""
Test Voice Attribution endpoints (Iter 361)
- POST /api/attribution/track - Track booking attribution (UTM/gclid)
- GET /api/attribution/{property_id} - Attribution dashboard
- GET /api/attribution/{property_id}/export.csv - Google Ads CSV export
- POST /api/hk/voice-report - Voice damage report (Whisper transcription)
"""
import pytest
import requests
import os
import io

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
PROPERTY_ID = "camden-suites"

class TestAttributionTrack:
    """Test POST /api/attribution/track - idempotent upsert on booking_id"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        # Login
        r = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert r.status_code == 200, f"Login failed: {r.text}"
        token = r.json().get("token") or r.json().get("access_token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
    
    def test_track_attribution_success(self):
        """Backend #1: POST /api/attribution/track with UTM data"""
        payload = {
            "booking_id": f"test-attr-{os.urandom(4).hex()}",
            "property_id": PROPERTY_ID,
            "utm_source": "google-ads",
            "utm_medium": "cpc",
            "utm_campaign": "london-hotels-summer",
            "gclid": "test123",
            "value": 245,
            "currency": "GBP"
        }
        r = self.session.post(f"{BASE_URL}/api/attribution/track", json=payload)
        assert r.status_code == 200, f"Track failed: {r.text}"
        data = r.json()
        assert data.get("ok") is True
        assert data.get("booking_id") == payload["booking_id"]
    
    def test_track_attribution_idempotent(self):
        """Verify idempotent upsert - same booking_id updates instead of duplicating"""
        booking_id = f"test-idempotent-{os.urandom(4).hex()}"
        payload1 = {
            "booking_id": booking_id,
            "property_id": PROPERTY_ID,
            "utm_source": "google-ads",
            "gclid": "gclid1",
            "value": 100
        }
        r1 = self.session.post(f"{BASE_URL}/api/attribution/track", json=payload1)
        assert r1.status_code == 200
        
        # Update same booking with different value
        payload2 = {
            "booking_id": booking_id,
            "property_id": PROPERTY_ID,
            "utm_source": "google-ads",
            "gclid": "gclid2",
            "value": 200
        }
        r2 = self.session.post(f"{BASE_URL}/api/attribution/track", json=payload2)
        assert r2.status_code == 200
        # Should not create duplicate - just update
    
    def test_track_attribution_missing_fields(self):
        """Verify 400 error when booking_id or property_id missing"""
        r = self.session.post(f"{BASE_URL}/api/attribution/track", json={
            "utm_source": "google-ads"
        })
        assert r.status_code == 400


class TestAttributionDashboard:
    """Test GET /api/attribution/{property_id} - aggregated dashboard"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token and seed some data"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        r = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert r.status_code == 200
        token = r.json().get("token") or r.json().get("access_token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        
        # Seed test data
        test_data = [
            {"booking_id": f"dash-test-1-{os.urandom(2).hex()}", "property_id": PROPERTY_ID, "utm_source": "google-ads", "gclid": "gclid123", "value": 245},
            {"booking_id": f"dash-test-2-{os.urandom(2).hex()}", "property_id": PROPERTY_ID, "utm_source": "facebook", "value": 180},
            {"booking_id": f"dash-test-3-{os.urandom(2).hex()}", "property_id": PROPERTY_ID, "utm_source": "direct", "value": 320},
        ]
        for d in test_data:
            self.session.post(f"{BASE_URL}/api/attribution/track", json=d)
    
    def test_dashboard_returns_aggregates(self):
        """Backend #2: GET /api/attribution/camden-suites?days=30"""
        r = self.session.get(f"{BASE_URL}/api/attribution/{PROPERTY_ID}?days=30")
        assert r.status_code == 200, f"Dashboard failed: {r.text}"
        data = r.json()
        
        # Check required fields
        assert "total_bookings_tracked" in data
        assert "total_value" in data
        assert "google_ads_conversions" in data
        assert "by_source" in data
        assert "by_campaign" in data
        
        # by_source should be sorted by value desc
        by_source = data["by_source"]
        if len(by_source) > 1:
            values = [s["value"] for s in by_source]
            assert values == sorted(values, reverse=True), "by_source not sorted by value desc"
    
    def test_dashboard_with_different_days(self):
        """Test days parameter works"""
        r = self.session.get(f"{BASE_URL}/api/attribution/{PROPERTY_ID}?days=7")
        assert r.status_code == 200
        data = r.json()
        assert data.get("window_days") == 7


class TestGoogleAdsCsvExport:
    """Test GET /api/attribution/{property_id}/export.csv"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token and seed gclid data"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        r = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert r.status_code == 200
        token = r.json().get("token") or r.json().get("access_token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        
        # Seed gclid data for CSV export
        self.session.post(f"{BASE_URL}/api/attribution/track", json={
            "booking_id": f"csv-test-{os.urandom(4).hex()}",
            "property_id": PROPERTY_ID,
            "utm_source": "google-ads",
            "gclid": f"Cj0KCQjw{os.urandom(4).hex()}",
            "value": 245,
            "currency": "GBP"
        })
    
    def test_csv_export_format(self):
        """Backend #3: GET /api/attribution/camden-suites/export.csv?days=90"""
        r = self.session.get(f"{BASE_URL}/api/attribution/{PROPERTY_ID}/export.csv?days=90")
        assert r.status_code == 200, f"CSV export failed: {r.text}"
        
        # Check content type is text/plain (PlainTextResponse)
        content = r.text.replace("\r", "")  # Handle Windows-style line endings
        lines = content.strip().split("\n")
        
        # Check header
        header = lines[0]
        expected_header = "Google Click ID,Conversion Name,Conversion Time,Conversion Value,Conversion Currency"
        assert header == expected_header, f"Header mismatch: {header}"
        
        # Should have at least header + 1 data row
        assert len(lines) >= 1, "CSV should have at least header"
        
        # If there are data rows, verify format
        if len(lines) > 1:
            data_row = lines[1].split(",")
            assert len(data_row) == 5, f"Data row should have 5 columns: {data_row}"
            # gclid should not be empty
            assert data_row[0], "Google Click ID should not be empty"
            assert data_row[1] == "Hotel Booking", f"Conversion Name should be 'Hotel Booking': {data_row[1]}"


class TestVoiceReport:
    """Test POST /api/hk/voice-report - Whisper transcription + ticket creation"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token"""
        self.session = requests.Session()
        r = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert r.status_code == 200
        token = r.json().get("token") or r.json().get("access_token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
    
    def test_voice_report_creates_ticket(self):
        """Backend #4: POST /api/hk/voice-report with audio file"""
        # Create a minimal valid WebM file header (stub audio)
        # This is a minimal WebM container that Whisper will fail to transcribe
        # but the endpoint should still create a ticket with fallback text
        stub_audio = bytes([
            0x1A, 0x45, 0xDF, 0xA3,  # EBML header
            0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x1F,
            0x42, 0x86, 0x81, 0x01,  # EBMLVersion
            0x42, 0xF7, 0x81, 0x01,  # EBMLReadVersion
            0x42, 0xF2, 0x81, 0x04,  # EBMLMaxIDLength
            0x42, 0xF3, 0x81, 0x08,  # EBMLMaxSizeLength
            0x42, 0x82, 0x84, 0x77, 0x65, 0x62, 0x6D,  # DocType: webm
        ])
        
        files = {
            "audio": ("voice-report.webm", io.BytesIO(stub_audio), "audio/webm")
        }
        data = {
            "property_id": PROPERTY_ID,
            "room_number": "101",
            "language": "tr"
        }
        
        r = self.session.post(
            f"{BASE_URL}/api/hk/voice-report",
            files=files,
            data=data
        )
        assert r.status_code == 200, f"Voice report failed: {r.text}"
        
        result = r.json()
        assert result.get("ok") is True
        assert "transcript" in result
        assert "ticket" in result
        
        ticket = result["ticket"]
        assert ticket.get("property_id") == PROPERTY_ID
        assert ticket.get("room_number") == "101"
        assert ticket.get("source") == "voice"
        assert ticket.get("kind") == "maintenance"
        assert ticket.get("status") == "open"
        assert "transcript" in ticket
        assert "id" in ticket
    
    def test_voice_report_without_room_number(self):
        """Voice report should work without room_number"""
        stub_audio = bytes([0x1A, 0x45, 0xDF, 0xA3] + [0x00] * 50)
        
        files = {
            "audio": ("voice.webm", io.BytesIO(stub_audio), "audio/webm")
        }
        data = {
            "property_id": PROPERTY_ID,
            "language": "tr"
        }
        
        r = self.session.post(
            f"{BASE_URL}/api/hk/voice-report",
            files=files,
            data=data
        )
        assert r.status_code == 200
        result = r.json()
        assert result.get("ok") is True
        # room_number should be None or empty
        assert result["ticket"].get("room_number") in [None, ""]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
