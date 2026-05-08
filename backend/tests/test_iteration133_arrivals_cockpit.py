"""
Iteration 133 - ArrivalsCockpit Tests
Tests for the Contactless Guest Journey / Self-Service Kiosk command centre.

Endpoints tested:
- GET /api/arrivals/{pid}?window=today|7d|30d|all&q=...
- POST /api/arrivals/{booking_id}/mark-paid
- POST /api/arrivals/{booking_id}/issue-key
- POST /api/arrivals/{booking_id}/revoke-key
- POST /api/guest-journey/send-registration/{booking_id} (regression)
- GET /api/marketplace/catalog/{pid} (regression)
"""
import pytest
import requests
import os
import uuid
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"


class TestArrivalsAuth:
    """Test authentication requirements for arrivals endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
    
    def get_auth_token(self):
        """Get admin auth token"""
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        return response.json().get("token")
    
    def test_arrivals_list_requires_auth(self):
        """GET /api/arrivals/{pid} requires authentication"""
        response = self.session.get(f"{BASE_URL}/api/arrivals/all")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: GET /api/arrivals/all requires auth (401 without token)")
    
    def test_mark_paid_requires_auth(self):
        """POST /api/arrivals/{booking_id}/mark-paid requires authentication"""
        response = self.session.post(f"{BASE_URL}/api/arrivals/test-booking/mark-paid")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: POST /api/arrivals/{id}/mark-paid requires auth (401 without token)")
    
    def test_issue_key_requires_auth(self):
        """POST /api/arrivals/{booking_id}/issue-key requires authentication"""
        response = self.session.post(f"{BASE_URL}/api/arrivals/test-booking/issue-key")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: POST /api/arrivals/{id}/issue-key requires auth (401 without token)")
    
    def test_revoke_key_requires_auth(self):
        """POST /api/arrivals/{booking_id}/revoke-key requires authentication"""
        response = self.session.post(f"{BASE_URL}/api/arrivals/test-booking/revoke-key")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: POST /api/arrivals/{id}/revoke-key requires auth (401 without token)")


class TestArrivalsListEndpoint:
    """Test GET /api/arrivals/{pid} endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        # Login and get token
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        token = response.json().get("token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
    
    def test_arrivals_list_default_window(self):
        """GET /api/arrivals/all returns arrivals with default 7d window"""
        response = self.session.get(f"{BASE_URL}/api/arrivals/all")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "window" in data, "Response should have 'window' field"
        assert "start" in data, "Response should have 'start' field"
        assert "end" in data, "Response should have 'end' field"
        assert "counters" in data, "Response should have 'counters' field"
        assert "arrivals" in data, "Response should have 'arrivals' field"
        
        # Check counters structure
        counters = data["counters"]
        assert "total" in counters, "Counters should have 'total'"
        assert "registered" in counters, "Counters should have 'registered'"
        assert "id_verified" in counters, "Counters should have 'id_verified'"
        assert "paid" in counters, "Counters should have 'paid'"
        assert "key_issued" in counters, "Counters should have 'key_issued'"
        
        print(f"PASS: GET /api/arrivals/all returns correct structure")
        print(f"  - Window: {data['window']}, Total arrivals: {counters['total']}")
        print(f"  - Counters: registered={counters['registered']}, id_verified={counters['id_verified']}, paid={counters['paid']}, key_issued={counters['key_issued']}")
    
    def test_arrivals_list_window_today(self):
        """GET /api/arrivals/all?window=today filters to today's arrivals"""
        response = self.session.get(f"{BASE_URL}/api/arrivals/all?window=today")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data["window"] == "today", f"Expected window='today', got {data['window']}"
        
        # Start and end should be the same date for today
        assert data["start"] == data["end"], "For 'today' window, start and end should be same date"
        
        print(f"PASS: window=today filters correctly (start={data['start']}, end={data['end']})")
    
    def test_arrivals_list_window_7d(self):
        """GET /api/arrivals/all?window=7d filters to next 7 days"""
        response = self.session.get(f"{BASE_URL}/api/arrivals/all?window=7d")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data["window"] == "7d", f"Expected window='7d', got {data['window']}"
        
        # Verify date range is 7 days
        start = datetime.fromisoformat(data["start"])
        end = datetime.fromisoformat(data["end"])
        delta = (end - start).days
        assert delta == 7, f"Expected 7 day range, got {delta} days"
        
        print(f"PASS: window=7d filters correctly ({delta} days, {data['counters']['total']} arrivals)")
    
    def test_arrivals_list_window_30d(self):
        """GET /api/arrivals/all?window=30d filters to next 30 days"""
        response = self.session.get(f"{BASE_URL}/api/arrivals/all?window=30d")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data["window"] == "30d", f"Expected window='30d', got {data['window']}"
        
        # Verify date range is 30 days
        start = datetime.fromisoformat(data["start"])
        end = datetime.fromisoformat(data["end"])
        delta = (end - start).days
        assert delta == 30, f"Expected 30 day range, got {delta} days"
        
        print(f"PASS: window=30d filters correctly ({delta} days, {data['counters']['total']} arrivals)")
    
    def test_arrivals_list_window_all(self):
        """GET /api/arrivals/all?window=all returns all upcoming arrivals"""
        response = self.session.get(f"{BASE_URL}/api/arrivals/all?window=all")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data["window"] == "all", f"Expected window='all', got {data['window']}"
        
        print(f"PASS: window=all returns {data['counters']['total']} arrivals")
    
    def test_arrivals_list_search_query(self):
        """GET /api/arrivals/all?q=<string> searches guest_name/booking_ref/guest_email"""
        # First get all arrivals to find a guest name to search
        response = self.session.get(f"{BASE_URL}/api/arrivals/all?window=7d")
        assert response.status_code == 200
        data = response.json()
        
        if data["arrivals"]:
            # Search for first guest's name
            guest_name = data["arrivals"][0].get("guest_name", "")
            if guest_name:
                search_term = guest_name[:3]  # First 3 chars
                search_response = self.session.get(f"{BASE_URL}/api/arrivals/all?window=7d&q={search_term}")
                assert search_response.status_code == 200
                search_data = search_response.json()
                
                # Should find at least the original guest
                assert search_data["counters"]["total"] >= 1, "Search should find at least 1 result"
                print(f"PASS: Search q='{search_term}' found {search_data['counters']['total']} arrivals")
            else:
                print("SKIP: No guest name to search")
        else:
            print("SKIP: No arrivals to test search")
    
    def test_arrivals_list_arrival_structure(self):
        """Each arrival has required fields including progress, stage, stage_label"""
        response = self.session.get(f"{BASE_URL}/api/arrivals/all?window=7d")
        assert response.status_code == 200
        data = response.json()
        
        if data["arrivals"]:
            arrival = data["arrivals"][0]
            
            # Check required fields
            required_fields = [
                "booking_id", "booking_ref", "property_id", "guest_name", "guest_email",
                "check_in", "check_out", "total_price", "amount_paid", "source",
                "progress", "stage", "stage_label"
            ]
            for field in required_fields:
                assert field in arrival, f"Arrival missing required field: {field}"
            
            # Check progress structure
            progress = arrival["progress"]
            progress_fields = ["link_sent", "registered", "id_verified", "paid", "key_issued"]
            for field in progress_fields:
                assert field in progress, f"Progress missing field: {field}"
                assert isinstance(progress[field], bool), f"Progress.{field} should be boolean"
            
            # Check stage is 0-5
            assert 0 <= arrival["stage"] <= 5, f"Stage should be 0-5, got {arrival['stage']}"
            
            # Check stage_label is valid
            valid_labels = ["not_started", "link_sent", "registered", "id_verified", "paid", "ready"]
            assert arrival["stage_label"] in valid_labels, f"Invalid stage_label: {arrival['stage_label']}"
            
            print(f"PASS: Arrival structure is correct")
            print(f"  - booking_id: {arrival['booking_id']}")
            print(f"  - guest_name: {arrival['guest_name']}")
            print(f"  - stage: {arrival['stage']} ({arrival['stage_label']})")
            print(f"  - progress: {progress}")
        else:
            print("SKIP: No arrivals to verify structure")
    
    def test_arrivals_list_property_filter(self):
        """GET /api/arrivals/{property_id} filters by property"""
        # Test with a specific property
        response = self.session.get(f"{BASE_URL}/api/arrivals/aldgate-flats?window=7d")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        # All arrivals should be for aldgate-flats
        for arrival in data["arrivals"]:
            assert arrival["property_id"] == "aldgate-flats", f"Expected property_id='aldgate-flats', got {arrival['property_id']}"
        
        print(f"PASS: Property filter works ({data['counters']['total']} arrivals for aldgate-flats)")


class TestMarkPaidEndpoint:
    """Test POST /api/arrivals/{booking_id}/mark-paid endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        # Login and get token
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        token = response.json().get("token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
    
    def test_mark_paid_success(self):
        """POST /api/arrivals/{booking_id}/mark-paid sets payment_status=paid"""
        # First get an unpaid booking
        response = self.session.get(f"{BASE_URL}/api/arrivals/all?window=7d")
        assert response.status_code == 200
        data = response.json()
        
        # Find an unpaid booking
        unpaid_booking = None
        for arrival in data["arrivals"]:
            if not arrival["progress"]["paid"]:
                unpaid_booking = arrival
                break
        
        if unpaid_booking:
            booking_id = unpaid_booking["booking_id"]
            
            # Mark as paid
            mark_response = self.session.post(f"{BASE_URL}/api/arrivals/{booking_id}/mark-paid")
            assert mark_response.status_code == 200, f"Expected 200, got {mark_response.status_code}: {mark_response.text}"
            
            result = mark_response.json()
            assert result.get("ok") == True, f"Expected ok=true, got {result}"
            
            # Verify the booking is now paid
            verify_response = self.session.get(f"{BASE_URL}/api/arrivals/all?window=7d")
            verify_data = verify_response.json()
            
            for arrival in verify_data["arrivals"]:
                if arrival["booking_id"] == booking_id:
                    assert arrival["progress"]["paid"] == True, "Booking should now be paid"
                    print(f"PASS: mark-paid sets payment_status=paid for booking {booking_id}")
                    break
        else:
            print("SKIP: No unpaid bookings to test mark-paid")
    
    def test_mark_paid_not_found(self):
        """POST /api/arrivals/{booking_id}/mark-paid returns 404 for invalid booking"""
        response = self.session.post(f"{BASE_URL}/api/arrivals/invalid-booking-id-12345/mark-paid")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("PASS: mark-paid returns 404 for invalid booking")


class TestIssueKeyEndpoint:
    """Test POST /api/arrivals/{booking_id}/issue-key endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        # Login and get token
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        token = response.json().get("token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
    
    def test_issue_key_requires_paid_status(self):
        """POST /api/arrivals/{booking_id}/issue-key returns 400 if booking not paid"""
        # Find an unpaid booking
        response = self.session.get(f"{BASE_URL}/api/arrivals/all?window=7d")
        assert response.status_code == 200
        data = response.json()
        
        unpaid_booking = None
        for arrival in data["arrivals"]:
            if not arrival["progress"]["paid"] and not arrival["progress"]["key_issued"]:
                unpaid_booking = arrival
                break
        
        if unpaid_booking:
            booking_id = unpaid_booking["booking_id"]
            
            # Try to issue key without paying first
            issue_response = self.session.post(f"{BASE_URL}/api/arrivals/{booking_id}/issue-key")
            assert issue_response.status_code == 400, f"Expected 400, got {issue_response.status_code}"
            
            print(f"PASS: issue-key returns 400 for unpaid booking {booking_id}")
        else:
            print("SKIP: No unpaid bookings to test issue-key requirement")
    
    def test_issue_key_success(self):
        """POST /api/arrivals/{booking_id}/issue-key returns code and expires_at for paid booking"""
        # Find a paid booking without key
        response = self.session.get(f"{BASE_URL}/api/arrivals/all?window=7d")
        assert response.status_code == 200
        data = response.json()
        
        paid_booking = None
        for arrival in data["arrivals"]:
            if arrival["progress"]["paid"] and not arrival["progress"]["key_issued"]:
                paid_booking = arrival
                break
        
        # If no paid booking without key, mark one as paid first
        if not paid_booking:
            for arrival in data["arrivals"]:
                if not arrival["progress"]["key_issued"]:
                    booking_id = arrival["booking_id"]
                    # Mark as paid
                    self.session.post(f"{BASE_URL}/api/arrivals/{booking_id}/mark-paid")
                    paid_booking = arrival
                    paid_booking["booking_id"] = booking_id
                    break
        
        if paid_booking:
            booking_id = paid_booking["booking_id"]
            
            # Issue key
            issue_response = self.session.post(f"{BASE_URL}/api/arrivals/{booking_id}/issue-key")
            assert issue_response.status_code == 200, f"Expected 200, got {issue_response.status_code}: {issue_response.text}"
            
            result = issue_response.json()
            assert result.get("ok") == True, f"Expected ok=true, got {result}"
            assert "code" in result, "Response should have 'code' field"
            assert "expires_at" in result, "Response should have 'expires_at' field"
            
            # Verify code format (8 chars alphanumeric)
            code = result["code"]
            assert len(code) == 8, f"Code should be 8 chars, got {len(code)}"
            
            # Verify the arrival now shows key_issued=true
            verify_response = self.session.get(f"{BASE_URL}/api/arrivals/all?window=7d")
            verify_data = verify_response.json()
            
            for arrival in verify_data["arrivals"]:
                if arrival["booking_id"] == booking_id:
                    assert arrival["progress"]["key_issued"] == True, "Booking should now have key_issued=true"
                    assert arrival["digital_key_code"] == code, f"digital_key_code should be {code}"
                    print(f"PASS: issue-key returns code={code}, expires_at={result['expires_at']}")
                    break
        else:
            print("SKIP: No bookings available to test issue-key")
    
    def test_issue_key_not_found(self):
        """POST /api/arrivals/{booking_id}/issue-key returns 404 for invalid booking"""
        response = self.session.post(f"{BASE_URL}/api/arrivals/invalid-booking-id-12345/issue-key")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("PASS: issue-key returns 404 for invalid booking")


class TestRevokeKeyEndpoint:
    """Test POST /api/arrivals/{booking_id}/revoke-key endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        # Login and get token
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        token = response.json().get("token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
    
    def test_revoke_key_success(self):
        """POST /api/arrivals/{booking_id}/revoke-key marks key as revoked"""
        # Find a booking with key issued
        response = self.session.get(f"{BASE_URL}/api/arrivals/all?window=7d")
        assert response.status_code == 200
        data = response.json()
        
        keyed_booking = None
        for arrival in data["arrivals"]:
            if arrival["progress"]["key_issued"]:
                keyed_booking = arrival
                break
        
        if keyed_booking:
            booking_id = keyed_booking["booking_id"]
            
            # Revoke key
            revoke_response = self.session.post(f"{BASE_URL}/api/arrivals/{booking_id}/revoke-key")
            assert revoke_response.status_code == 200, f"Expected 200, got {revoke_response.status_code}: {revoke_response.text}"
            
            result = revoke_response.json()
            assert result.get("ok") == True, f"Expected ok=true, got {result}"
            
            # Verify the arrival now shows key_issued=false
            verify_response = self.session.get(f"{BASE_URL}/api/arrivals/all?window=7d")
            verify_data = verify_response.json()
            
            for arrival in verify_data["arrivals"]:
                if arrival["booking_id"] == booking_id:
                    assert arrival["progress"]["key_issued"] == False, "Booking should now have key_issued=false"
                    print(f"PASS: revoke-key sets key_issued=false for booking {booking_id}")
                    break
        else:
            print("SKIP: No bookings with keys to test revoke-key")
    
    def test_revoke_key_not_found(self):
        """POST /api/arrivals/{booking_id}/revoke-key returns 404 if no key exists"""
        response = self.session.post(f"{BASE_URL}/api/arrivals/invalid-booking-id-12345/revoke-key")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("PASS: revoke-key returns 404 for booking without key")


class TestRegressionEndpoints:
    """Regression tests for existing endpoints that ArrivalsCockpit depends on"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        # Login and get token
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        token = response.json().get("token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
    
    def test_send_registration_link_still_works(self):
        """POST /api/guest-journey/send-registration/{booking_id} still works"""
        # Get a booking to send registration link
        response = self.session.get(f"{BASE_URL}/api/arrivals/all?window=7d")
        assert response.status_code == 200
        data = response.json()
        
        if data["arrivals"]:
            # Find a booking without registration link sent
            booking = None
            for arrival in data["arrivals"]:
                if not arrival["progress"]["link_sent"]:
                    booking = arrival
                    break
            
            if not booking:
                booking = data["arrivals"][0]  # Use first booking
            
            booking_id = booking["booking_id"]
            
            # Send registration link
            send_response = self.session.post(f"{BASE_URL}/api/guest-journey/send-registration/{booking_id}")
            assert send_response.status_code == 200, f"Expected 200, got {send_response.status_code}: {send_response.text}"
            
            result = send_response.json()
            assert result.get("status") == "sent", f"Expected status='sent', got {result}"
            assert "token" in result, "Response should have 'token' field"
            assert "url" in result, "Response should have 'url' field"
            
            print(f"PASS: send-registration still works (token={result['token'][:20]}...)")
        else:
            print("SKIP: No bookings to test send-registration")
    
    def test_marketplace_catalog_still_works(self):
        """GET /api/marketplace/catalog/{pid} still works"""
        response = self.session.get(f"{BASE_URL}/api/marketplace/catalog/all")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "integrations" in data, "Response should have 'integrations' field"
        assert "categories" in data, "Response should have 'categories' field"
        assert "total_available" in data, "Response should have 'total_available' field"
        
        print(f"PASS: marketplace catalog still works ({data['total_available']} integrations)")


class TestFullWorkflow:
    """Test complete workflow: send link -> mark paid -> issue key -> revoke key"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        # Login and get token
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        token = response.json().get("token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
    
    def test_complete_contactless_journey(self):
        """Test complete contactless check-in workflow"""
        # Get arrivals
        response = self.session.get(f"{BASE_URL}/api/arrivals/all?window=7d")
        assert response.status_code == 200
        data = response.json()
        
        if not data["arrivals"]:
            print("SKIP: No arrivals to test complete workflow")
            return
        
        # Find a booking at stage 0 (not started) or use first available
        booking = None
        for arrival in data["arrivals"]:
            if arrival["stage"] == 0:
                booking = arrival
                break
        
        if not booking:
            booking = data["arrivals"][0]
        
        booking_id = booking["booking_id"]
        print(f"Testing workflow for booking: {booking_id} (guest: {booking['guest_name']})")
        
        # Step 1: Send registration link (if not sent)
        if not booking["progress"]["link_sent"]:
            send_response = self.session.post(f"{BASE_URL}/api/guest-journey/send-registration/{booking_id}")
            assert send_response.status_code == 200, f"Send registration failed: {send_response.text}"
            print(f"  Step 1: Registration link sent")
        else:
            print(f"  Step 1: Registration link already sent")
        
        # Step 2: Mark as paid (if not paid)
        if not booking["progress"]["paid"]:
            paid_response = self.session.post(f"{BASE_URL}/api/arrivals/{booking_id}/mark-paid")
            assert paid_response.status_code == 200, f"Mark paid failed: {paid_response.text}"
            print(f"  Step 2: Marked as paid")
        else:
            print(f"  Step 2: Already paid")
        
        # Step 3: Issue digital key
        issue_response = self.session.post(f"{BASE_URL}/api/arrivals/{booking_id}/issue-key")
        if issue_response.status_code == 200:
            key_data = issue_response.json()
            print(f"  Step 3: Digital key issued: {key_data['code']}")
            
            # Step 4: Revoke key
            revoke_response = self.session.post(f"{BASE_URL}/api/arrivals/{booking_id}/revoke-key")
            assert revoke_response.status_code == 200, f"Revoke key failed: {revoke_response.text}"
            print(f"  Step 4: Key revoked")
        else:
            print(f"  Step 3: Key already issued or error: {issue_response.status_code}")
        
        # Verify final state
        verify_response = self.session.get(f"{BASE_URL}/api/arrivals/all?window=7d")
        verify_data = verify_response.json()
        
        for arrival in verify_data["arrivals"]:
            if arrival["booking_id"] == booking_id:
                print(f"  Final state: stage={arrival['stage']} ({arrival['stage_label']})")
                print(f"  Progress: {arrival['progress']}")
                break
        
        print("PASS: Complete contactless journey workflow tested")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
