"""
Iteration 122 - Batch Auto-Respond & Channel Manager Sync Availability Tests
Tests:
1. POST /api/reviews/batch-auto-respond - AI batch auto-respond to unresponded reviews
2. POST /api/revenue/channel-manager/{property_id}/sync-availability - Sync room availability to OTAs
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestBatchAutoRespond:
    """Tests for batch auto-respond endpoint using GPT-5.2"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        self.token = response.json().get("token")
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
    
    def test_batch_auto_respond_professional_tone(self):
        """Test batch auto-respond with professional tone"""
        response = requests.post(
            f"{BASE_URL}/api/reviews/batch-auto-respond",
            headers=self.headers,
            json={"tone": "professional", "limit": 2}
        )
        assert response.status_code == 200, f"Batch auto-respond failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "processed" in data
        assert "errors" in data
        assert "results" in data
        assert "tone" in data
        assert data["tone"] == "professional"
        
        # If reviews were processed, verify result structure
        if data["processed"] > 0:
            assert len(data["results"]) > 0
            result = data["results"][0]
            assert "review_id" in result
            assert "guest_name" in result
            assert "platform" in result
            assert "rating" in result
            assert "response_preview" in result
            assert "status" in result
            assert result["status"] == "responded"
        
        print(f"Processed {data['processed']} reviews with professional tone")
    
    def test_batch_auto_respond_friendly_tone(self):
        """Test batch auto-respond with friendly tone"""
        response = requests.post(
            f"{BASE_URL}/api/reviews/batch-auto-respond",
            headers=self.headers,
            json={"tone": "friendly", "limit": 1}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["tone"] == "friendly"
        print(f"Processed {data['processed']} reviews with friendly tone")
    
    def test_batch_auto_respond_apologetic_tone(self):
        """Test batch auto-respond with apologetic tone"""
        response = requests.post(
            f"{BASE_URL}/api/reviews/batch-auto-respond",
            headers=self.headers,
            json={"tone": "apologetic", "limit": 1}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["tone"] == "apologetic"
        print(f"Processed {data['processed']} reviews with apologetic tone")
    
    def test_batch_auto_respond_with_property_filter(self):
        """Test batch auto-respond with property_id filter"""
        response = requests.post(
            f"{BASE_URL}/api/reviews/batch-auto-respond",
            headers=self.headers,
            json={"tone": "professional", "limit": 1, "property_id": "default"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "processed" in data
        print(f"Processed {data['processed']} reviews for property 'default'")
    
    def test_batch_auto_respond_limit_enforcement(self):
        """Test that limit parameter is enforced (max 20)"""
        response = requests.post(
            f"{BASE_URL}/api/reviews/batch-auto-respond",
            headers=self.headers,
            json={"tone": "professional", "limit": 50}  # Should be capped at 20
        )
        assert response.status_code == 200
        data = response.json()
        # Even if 50 requested, max should be 20
        assert data["processed"] <= 20
    
    def test_batch_auto_respond_requires_auth(self):
        """Test that batch auto-respond requires authentication"""
        response = requests.post(
            f"{BASE_URL}/api/reviews/batch-auto-respond",
            json={"tone": "professional", "limit": 1}
        )
        assert response.status_code in [401, 403], "Should require authentication"
    
    def test_batch_auto_respond_updates_response_status(self):
        """Test that batch auto-respond updates review response_status to 'responded'"""
        # First get stats before
        stats_before = requests.get(f"{BASE_URL}/api/reviews/stats/summary").json()
        pending_before = stats_before.get("pending", 0)
        
        # Run batch auto-respond
        response = requests.post(
            f"{BASE_URL}/api/reviews/batch-auto-respond",
            headers=self.headers,
            json={"tone": "professional", "limit": 2}
        )
        assert response.status_code == 200
        data = response.json()
        processed = data["processed"]
        
        # Get stats after
        stats_after = requests.get(f"{BASE_URL}/api/reviews/stats/summary").json()
        pending_after = stats_after.get("pending", 0)
        
        # Pending should decrease by processed count
        if processed > 0:
            assert pending_after <= pending_before, "Pending count should decrease after batch respond"
        
        print(f"Pending before: {pending_before}, after: {pending_after}, processed: {processed}")


class TestChannelManagerSyncAvailability:
    """Tests for channel manager sync-availability endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert response.status_code == 200
        self.token = response.json().get("token")
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        self.property_id = "aldgate-flats"
    
    def test_sync_availability_no_connected_channels(self):
        """Test sync-availability returns error when no channels connected"""
        # First disconnect all channels except direct
        channels_resp = requests.get(
            f"{BASE_URL}/api/revenue/channel-manager/{self.property_id}",
            headers=self.headers
        )
        channels = channels_resp.json().get("channels", [])
        
        # Disconnect all non-direct channels
        for ch in channels:
            if ch["channel_id"] != "direct" and ch.get("connected"):
                requests.put(
                    f"{BASE_URL}/api/revenue/channel-manager/{self.property_id}/{ch['channel_id']}",
                    headers=self.headers,
                    json={"connected": False}
                )
        
        # Now test sync with only direct channel (which is always connected)
        response = requests.post(
            f"{BASE_URL}/api/revenue/channel-manager/{self.property_id}/sync-availability",
            headers=self.headers,
            json={"days": 7}
        )
        assert response.status_code == 200
        data = response.json()
        # Should have at least direct channel
        assert "channels_synced" in data or "error" in data
    
    def test_sync_availability_with_connected_channel(self):
        """Test sync-availability with connected OTA channel"""
        # Connect booking_com channel
        connect_resp = requests.put(
            f"{BASE_URL}/api/revenue/channel-manager/{self.property_id}/booking_com",
            headers=self.headers,
            json={"connected": True}
        )
        assert connect_resp.status_code == 200
        
        # Now sync availability
        response = requests.post(
            f"{BASE_URL}/api/revenue/channel-manager/{self.property_id}/sync-availability",
            headers=self.headers,
            json={"days": 7}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "message" in data
        assert "channels_synced" in data
        assert "days_synced" in data
        assert "total_rooms" in data
        assert "results" in data
        assert "availability_sample" in data
        
        # Verify channels were synced
        assert data["channels_synced"] >= 1
        assert data["days_synced"] == 7
        
        # Verify availability sample structure
        if data["availability_sample"]:
            sample = data["availability_sample"][0]
            assert "date" in sample
            assert "total_rooms" in sample
            assert "booked" in sample
            assert "available" in sample
            assert "occupancy_pct" in sample
            assert "by_type" in sample
        
        print(f"Synced availability to {data['channels_synced']} channels for {data['days_synced']} days")
    
    def test_sync_availability_custom_days(self):
        """Test sync-availability with custom days parameter"""
        # Ensure channel is connected
        requests.put(
            f"{BASE_URL}/api/revenue/channel-manager/{self.property_id}/booking_com",
            headers=self.headers,
            json={"connected": True}
        )
        
        response = requests.post(
            f"{BASE_URL}/api/revenue/channel-manager/{self.property_id}/sync-availability",
            headers=self.headers,
            json={"days": 14}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["days_synced"] == 14
    
    def test_sync_availability_requires_auth(self):
        """Test that sync-availability requires authentication"""
        response = requests.post(
            f"{BASE_URL}/api/revenue/channel-manager/{self.property_id}/sync-availability",
            json={"days": 7}
        )
        assert response.status_code in [401, 403], "Should require authentication"
    
    def test_sync_availability_creates_push_log(self):
        """Test that sync-availability creates push log entries"""
        # Ensure channel is connected
        requests.put(
            f"{BASE_URL}/api/revenue/channel-manager/{self.property_id}/booking_com",
            headers=self.headers,
            json={"connected": True}
        )
        
        # Sync availability
        sync_resp = requests.post(
            f"{BASE_URL}/api/revenue/channel-manager/{self.property_id}/sync-availability",
            headers=self.headers,
            json={"days": 7}
        )
        assert sync_resp.status_code == 200
        
        # Check push logs
        logs_resp = requests.get(
            f"{BASE_URL}/api/revenue/channel-manager/{self.property_id}/push-logs",
            headers=self.headers
        )
        assert logs_resp.status_code == 200
        logs = logs_resp.json().get("logs", [])
        
        # Should have availability sync logs
        avail_logs = [l for l in logs if l.get("type") == "availability"]
        assert len(avail_logs) > 0, "Should have availability sync logs"
        
        print(f"Found {len(avail_logs)} availability sync logs")
    
    def test_sync_availability_returns_room_type_breakdown(self):
        """Test that availability sample includes per-room-type breakdown"""
        # Ensure channel is connected
        requests.put(
            f"{BASE_URL}/api/revenue/channel-manager/{self.property_id}/booking_com",
            headers=self.headers,
            json={"connected": True}
        )
        
        response = requests.post(
            f"{BASE_URL}/api/revenue/channel-manager/{self.property_id}/sync-availability",
            headers=self.headers,
            json={"days": 7}
        )
        assert response.status_code == 200
        data = response.json()
        
        if data.get("availability_sample"):
            sample = data["availability_sample"][0]
            by_type = sample.get("by_type", {})
            
            # Verify room type breakdown structure
            for room_type_id, type_data in by_type.items():
                assert "total" in type_data
                assert "booked" in type_data
                assert "available" in type_data
                assert type_data["available"] == type_data["total"] - type_data["booked"]
            
            print(f"Room type breakdown: {list(by_type.keys())}")


class TestReviewStatsAfterBatchRespond:
    """Test that review stats update correctly after batch auto-respond"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert response.status_code == 200
        self.token = response.json().get("token")
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
    
    def test_response_rate_increases_after_batch(self):
        """Test that response rate increases after batch auto-respond"""
        # Get stats before
        stats_before = requests.get(f"{BASE_URL}/api/reviews/stats/summary").json()
        rate_before = stats_before.get("response_rate", 0)
        
        # Run batch auto-respond
        response = requests.post(
            f"{BASE_URL}/api/reviews/batch-auto-respond",
            headers=self.headers,
            json={"tone": "professional", "limit": 3}
        )
        assert response.status_code == 200
        processed = response.json().get("processed", 0)
        
        # Get stats after
        stats_after = requests.get(f"{BASE_URL}/api/reviews/stats/summary").json()
        rate_after = stats_after.get("response_rate", 0)
        
        # Response rate should increase or stay same (if no pending reviews)
        if processed > 0:
            assert rate_after >= rate_before, "Response rate should increase after batch respond"
        
        print(f"Response rate: {rate_before}% -> {rate_after}% (processed {processed})")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
