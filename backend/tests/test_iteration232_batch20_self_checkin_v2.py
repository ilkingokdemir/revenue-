"""
Iteration 232 - Batch 20: Self Check-in v2 (Pre-arrival link + 5-step wizard)

Tests:
1. POST /api/self-checkin-v2/token/{booking_id} - Generate token (admin)
2. GET /api/self-checkin-v2/verify/{token} - Verify token (public)
3. POST /api/self-checkin-v2/reg-card/{token} - Submit reg-card (public)
4. POST /api/self-checkin-v2/slot/{token} - Book arrival slot (public)
5. GET /api/self-checkin-v2/pipeline/{property_id} - Pipeline dashboard (admin)
6. GET /api/self-checkin-v2/reg-card/{token} - Get reg-card (admin)
7. Regression tests for Batches 12-19
"""

import pytest
import requests
import os
import uuid
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestSelfCheckInV2:
    """Self Check-in v2 API tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup - login as admin"""
        self.session = requests.Session()
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        self.token = login_resp.json().get("access_token")
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        
        # Get a valid booking for testing
        bookings_resp = self.session.get(f"{BASE_URL}/api/bookings?property_id=default&limit=50")
        if bookings_resp.status_code == 200:
            bookings = bookings_resp.json()
            if isinstance(bookings, list) and len(bookings) > 0:
                # Find a booking without self_checkin_v2_token
                for b in bookings:
                    if not b.get("self_checkin_v2_token"):
                        self.test_booking_id = b.get("id")
                        self.test_booking = b
                        break
                else:
                    # Use first booking if all have tokens
                    self.test_booking_id = bookings[0].get("id")
                    self.test_booking = bookings[0]
            else:
                self.test_booking_id = None
                self.test_booking = None
        else:
            self.test_booking_id = None
            self.test_booking = None
    
    # ===== Token Generation Tests =====
    
    def test_01_generate_token_valid_booking(self):
        """POST /api/self-checkin-v2/token/{booking_id} - Generate token for valid booking"""
        if not self.test_booking_id:
            pytest.skip("No booking available for testing")
        
        resp = self.session.post(f"{BASE_URL}/api/self-checkin-v2/token/{self.test_booking_id}?expiry_hours=72")
        assert resp.status_code == 200, f"Token generation failed: {resp.text}"
        
        data = resp.json()
        assert "token" in data, "Response missing 'token'"
        assert len(data["token"]) == 32, f"Token should be 32-char hex, got {len(data['token'])}"
        assert "link" in data, "Response missing 'link'"
        assert data["link"].startswith("/selfcheckin-v2/"), f"Link format wrong: {data['link']}"
        assert "expires_at" in data, "Response missing 'expires_at'"
        assert "booking_id" in data, "Response missing 'booking_id'"
        assert data["booking_id"] == self.test_booking_id
        
        # Store token for subsequent tests
        self.__class__.generated_token = data["token"]
        print(f"✓ Token generated: {data['token'][:8]}... expires {data['expires_at']}")
    
    def test_02_generate_token_invalid_booking(self):
        """POST /api/self-checkin-v2/token/{invalid_id} - Should return 404"""
        resp = self.session.post(f"{BASE_URL}/api/self-checkin-v2/token/invalid-booking-id-12345?expiry_hours=72")
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}"
        print("✓ Invalid booking returns 404")
    
    # ===== Token Verification Tests (PUBLIC) =====
    
    def test_03_verify_token_valid(self):
        """GET /api/self-checkin-v2/verify/{token} - Verify valid token (PUBLIC)"""
        token = getattr(self.__class__, 'generated_token', None)
        if not token:
            pytest.skip("No token generated in previous test")
        
        # Use a new session without auth (public endpoint)
        public_session = requests.Session()
        resp = public_session.get(f"{BASE_URL}/api/self-checkin-v2/verify/{token}")
        assert resp.status_code == 200, f"Token verification failed: {resp.text}"
        
        data = resp.json()
        assert "token" in data
        assert "status" in data
        assert data["status"] in ["issued", "started", "reg_card_filled", "slot_booked", "completed"]
        assert "booking" in data
        assert "property" in data
        assert "default_slots" in data
        assert len(data["default_slots"]) == 11, f"Expected 11 slots, got {len(data['default_slots'])}"
        assert "reg_card_filled" in data
        assert "slot_booked" in data
        
        # Verify booking structure
        booking = data["booking"]
        assert "id" in booking
        assert "guest_name" in booking
        assert "check_in" in booking
        assert "check_out" in booking
        
        # Verify property structure
        prop = data["property"]
        assert "name" in prop
        assert "check_in_time" in prop
        assert "check_out_time" in prop
        
        print(f"✓ Token verified: status={data['status']}, guest={booking.get('guest_name')}")
    
    def test_04_verify_token_invalid(self):
        """GET /api/self-checkin-v2/verify/{invalid_token} - Should return 404"""
        public_session = requests.Session()
        resp = public_session.get(f"{BASE_URL}/api/self-checkin-v2/verify/invalid-token-12345")
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}"
        print("✓ Invalid token returns 404")
    
    # ===== Reg-Card Submission Tests (PUBLIC) =====
    
    def test_05_submit_reg_card(self):
        """POST /api/self-checkin-v2/reg-card/{token} - Submit registration card (PUBLIC)"""
        token = getattr(self.__class__, 'generated_token', None)
        if not token:
            pytest.skip("No token generated in previous test")
        
        public_session = requests.Session()
        reg_card_data = {
            "first_name": "Test",
            "last_name": "Guest",
            "date_of_birth": "1990-01-15",
            "nationality": "TR",
            "id_doc_type": "passport",
            "id_doc_no": "U12345678",
            "address": "123 Test Street, Istanbul",
            "phone": "+905551234567",
            "email": "test.guest@example.com",
            "signature_svg": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
            "marketing_consent": True
        }
        
        resp = public_session.post(f"{BASE_URL}/api/self-checkin-v2/reg-card/{token}", json=reg_card_data)
        assert resp.status_code == 200, f"Reg-card submission failed: {resp.text}"
        
        data = resp.json()
        assert data.get("status") == "reg_card_filled", f"Expected status 'reg_card_filled', got {data.get('status')}"
        assert "submitted_at" in data
        
        print(f"✓ Reg-card submitted: status={data['status']}, submitted_at={data['submitted_at']}")
    
    def test_06_submit_reg_card_invalid_token(self):
        """POST /api/self-checkin-v2/reg-card/{invalid_token} - Should return 404"""
        public_session = requests.Session()
        resp = public_session.post(f"{BASE_URL}/api/self-checkin-v2/reg-card/invalid-token-12345", json={
            "first_name": "Test",
            "last_name": "Guest"
        })
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}"
        print("✓ Invalid token returns 404 for reg-card")
    
    # ===== Slot Booking Tests (PUBLIC) =====
    
    def test_07_book_slot_valid(self):
        """POST /api/self-checkin-v2/slot/{token} - Book arrival slot (PUBLIC)"""
        token = getattr(self.__class__, 'generated_token', None)
        if not token:
            pytest.skip("No token generated in previous test")
        
        public_session = requests.Session()
        resp = public_session.post(f"{BASE_URL}/api/self-checkin-v2/slot/{token}", json={
            "arrival_slot": "15:00-16:00"
        })
        assert resp.status_code == 200, f"Slot booking failed: {resp.text}"
        
        data = resp.json()
        assert data.get("status") == "completed", f"Expected status 'completed', got {data.get('status')}"
        assert data.get("arrival_slot") == "15:00-16:00"
        assert "completed_at" in data
        
        print(f"✓ Slot booked: status={data['status']}, slot={data['arrival_slot']}")
    
    def test_08_book_slot_invalid_slot(self):
        """POST /api/self-checkin-v2/slot/{token} - Invalid slot should return 400"""
        token = getattr(self.__class__, 'generated_token', None)
        if not token:
            pytest.skip("No token generated in previous test")
        
        public_session = requests.Session()
        resp = public_session.post(f"{BASE_URL}/api/self-checkin-v2/slot/{token}", json={
            "arrival_slot": "25:00-26:00"  # Invalid slot
        })
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}"
        print("✓ Invalid slot returns 400")
    
    # ===== Pipeline Dashboard Tests (ADMIN) =====
    
    def test_09_pipeline_dashboard(self):
        """GET /api/self-checkin-v2/pipeline/{property_id} - Pipeline dashboard"""
        resp = self.session.get(f"{BASE_URL}/api/self-checkin-v2/pipeline/default?days_ahead=14")
        assert resp.status_code == 200, f"Pipeline fetch failed: {resp.text}"
        
        data = resp.json()
        assert "rows" in data
        assert "count" in data
        assert "issued" in data
        assert "reg_card_filled" in data
        assert "completed" in data
        assert "completion_pct" in data
        
        # Verify row structure if rows exist
        if data["rows"]:
            row = data["rows"][0]
            assert "booking_id" in row
            assert "guest_name" in row
            assert "check_in" in row
            assert "token_issued" in row
            assert "reg_card_filled" in row
            assert "has_signature" in row
            assert "has_id_photo" in row
            assert "slot_booked" in row
            assert "fast_track" in row
            assert "status" in row
        
        print(f"✓ Pipeline: {data['count']} bookings, {data['issued']} issued, {data['completed']} completed ({data['completion_pct']}%)")
    
    def test_10_pipeline_different_days(self):
        """GET /api/self-checkin-v2/pipeline/{property_id}?days_ahead=30 - Different horizon"""
        resp = self.session.get(f"{BASE_URL}/api/self-checkin-v2/pipeline/default?days_ahead=30")
        assert resp.status_code == 200, f"Pipeline fetch failed: {resp.text}"
        
        data = resp.json()
        assert "rows" in data
        assert "count" in data
        print(f"✓ Pipeline (30 days): {data['count']} bookings")
    
    # ===== Admin Reg-Card View Tests =====
    
    def test_11_get_reg_card_admin(self):
        """GET /api/self-checkin-v2/reg-card/{token} - Admin view of submitted reg-card"""
        token = getattr(self.__class__, 'generated_token', None)
        if not token:
            pytest.skip("No token generated in previous test")
        
        resp = self.session.get(f"{BASE_URL}/api/self-checkin-v2/reg-card/{token}")
        assert resp.status_code == 200, f"Reg-card fetch failed: {resp.text}"
        
        data = resp.json()
        assert "first_name" in data
        assert "last_name" in data
        assert "submitted_at" in data
        assert data["first_name"] == "Test"
        assert data["last_name"] == "Guest"
        
        print(f"✓ Admin reg-card view: {data['first_name']} {data['last_name']}")
    
    def test_12_get_reg_card_unsubmitted(self):
        """GET /api/self-checkin-v2/reg-card/{unsubmitted_token} - Should return 404"""
        resp = self.session.get(f"{BASE_URL}/api/self-checkin-v2/reg-card/unsubmitted-token-12345")
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}"
        print("✓ Unsubmitted token returns 404 for reg-card view")


class TestRegressionBatches12to19:
    """Regression tests for Batches 12-19"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup - login as admin"""
        self.session = requests.Session()
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        self.token = login_resp.json().get("access_token")
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
    
    def test_regression_batch13_tr_compliance(self):
        """Batch 13: TR Compliance - KBS history"""
        resp = self.session.get(f"{BASE_URL}/api/tr-compliance/kbs/default/history")
        assert resp.status_code == 200, f"TR Compliance failed: {resp.text}"
        print("✓ Batch 13 TR Compliance: PASSED")
    
    def test_regression_batch14_ai_predictions(self):
        """Batch 14: AI Predictions - Cancel risk"""
        resp = self.session.get(f"{BASE_URL}/api/ai-predictions/cancel-risk/default")
        assert resp.status_code == 200, f"AI Predictions failed: {resp.text}"
        print("✓ Batch 14 AI Predictions: PASSED")
    
    def test_regression_batch15_eu_compliance(self):
        """Batch 15: EU Compliance - Catalog"""
        resp = self.session.get(f"{BASE_URL}/api/eu-compliance/catalog")
        assert resp.status_code == 200, f"EU Compliance failed: {resp.text}"
        print("✓ Batch 15 EU Compliance: PASSED")
    
    def test_regression_batch16_channel_revenue(self):
        """Batch 16: Channel Revenue"""
        resp = self.session.get(f"{BASE_URL}/api/channel-revenue/channels/default")
        assert resp.status_code == 200, f"Channel Revenue failed: {resp.text}"
        print("✓ Batch 16 Channel Revenue: PASSED")
    
    def test_regression_batch17_kds(self):
        """Batch 17: KDS (Kitchen Display System)"""
        resp = self.session.get(f"{BASE_URL}/api/kds/default")
        assert resp.status_code == 200, f"KDS failed: {resp.text}"
        print("✓ Batch 17 KDS: PASSED")
    
    def test_regression_batch18_loyalty_v2_benefits(self):
        """Batch 18: Loyalty V2 - Benefits"""
        resp = self.session.get(f"{BASE_URL}/api/loyalty-v2/benefits/default")
        assert resp.status_code == 200, f"Loyalty V2 Benefits failed: {resp.text}"
        print("✓ Batch 18 Loyalty V2 Benefits: PASSED")
    
    def test_regression_batch18_loyalty_v2_packages(self):
        """Batch 18: Loyalty V2 - Packages"""
        resp = self.session.get(f"{BASE_URL}/api/loyalty-v2/packages/default")
        assert resp.status_code == 200, f"Loyalty V2 Packages failed: {resp.text}"
        print("✓ Batch 18 Loyalty V2 Packages: PASSED")
    
    def test_regression_batch19_sentiment_heatmap(self):
        """Batch 19: Sentiment Heatmap"""
        resp = self.session.get(f"{BASE_URL}/api/sentiment/heatmap/default?days=90")
        assert resp.status_code == 200, f"Sentiment Heatmap failed: {resp.text}"
        print("✓ Batch 19 Sentiment Heatmap: PASSED")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
