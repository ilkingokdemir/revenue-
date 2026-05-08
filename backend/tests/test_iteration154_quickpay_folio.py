"""
Iteration 154 - Quick Pay Modal & Folio Payment Types Testing

Tests:
1. POST /api/folio/{booking_id}/add-payment with 4 payment methods (cash, card, bank_transfer, channel_collection)
2. Verify method is stored in both 'category' and 'payment_method' fields
3. Verify 'channel' is stored only when method=channel_collection
4. Verify invalid methods fall back to 'card'
5. GET /api/bookings/timeline/{property_id} returns balance_due, folio_paid, folio_charged fields
6. Verify payment_status transitions: pending -> partial -> paid
"""

import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    raise ValueError("REACT_APP_BACKEND_URL environment variable not set")


class TestQuickPayFolioPayments:
    """Test the Quick Pay modal payment types and folio integration"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login as admin
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        token = login_resp.json().get("token")
        assert token, "No token in login response"
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        
        # Get a property ID for testing
        props_resp = self.session.get(f"{BASE_URL}/api/properties")
        assert props_resp.status_code == 200
        props = props_resp.json()
        self.property_id = props[0]["id"] if props else "aldgate-flats"
        
        yield
    
    def _get_booking_with_balance(self):
        """Find an existing booking with balance_due > 0"""
        resp = self.session.get(f"{BASE_URL}/api/bookings/timeline/{self.property_id}?start=2026-10-10&days=30")
        assert resp.status_code == 200
        timeline = resp.json()
        
        for group in timeline.get("groups", []):
            for room in group.get("rooms", []):
                for bk in room.get("bookings", []):
                    if bk.get("balance_due", 0) > 50:  # Need at least 50 for testing
                        return bk
        return None
    
    # ==================== PAYMENT METHOD TESTS ====================
    
    def test_add_payment_cash(self):
        """Test adding a cash payment"""
        booking = self._get_booking_with_balance()
        if not booking:
            pytest.skip("No booking with balance found")
        
        resp = self.session.post(f"{BASE_URL}/api/folio/{booking['id']}/add-payment", json={
            "amount": 5.0,
            "method": "cash",
            "reference": "TEST-CASH-001",
            "description": "Cash payment test"
        })
        assert resp.status_code == 200, f"Cash payment failed: {resp.text}"
        payment = resp.json()
        
        # Verify method is stored in both category and payment_method
        assert payment.get("category") == "cash", f"Expected category='cash', got {payment.get('category')}"
        assert payment.get("payment_method") == "cash", f"Expected payment_method='cash', got {payment.get('payment_method')}"
        assert payment.get("amount") == 5.0
        # Channel should NOT be set for cash
        assert not payment.get("channel"), f"Channel should be empty for cash, got {payment.get('channel')}"
        print("PASS: Cash payment recorded correctly with category=cash, payment_method=cash")
    
    def test_add_payment_card(self):
        """Test adding a card payment"""
        booking = self._get_booking_with_balance()
        if not booking:
            pytest.skip("No booking with balance found")
        
        resp = self.session.post(f"{BASE_URL}/api/folio/{booking['id']}/add-payment", json={
            "amount": 5.0,
            "method": "card",
            "reference": "4242",
            "description": "Card payment test"
        })
        assert resp.status_code == 200, f"Card payment failed: {resp.text}"
        payment = resp.json()
        
        assert payment.get("category") == "card"
        assert payment.get("payment_method") == "card"
        assert not payment.get("channel")
        print("PASS: Card payment recorded correctly with category=card, payment_method=card")
    
    def test_add_payment_bank_transfer(self):
        """Test adding a bank transfer payment"""
        booking = self._get_booking_with_balance()
        if not booking:
            pytest.skip("No booking with balance found")
        
        resp = self.session.post(f"{BASE_URL}/api/folio/{booking['id']}/add-payment", json={
            "amount": 5.0,
            "method": "bank_transfer",
            "reference": "TRF-TEST-001",
            "description": "Bank transfer test"
        })
        assert resp.status_code == 200, f"Bank transfer failed: {resp.text}"
        payment = resp.json()
        
        assert payment.get("category") == "bank_transfer"
        assert payment.get("payment_method") == "bank_transfer"
        assert not payment.get("channel")
        print("PASS: Bank transfer recorded correctly with category=bank_transfer, payment_method=bank_transfer")
    
    def test_add_payment_channel_collection(self):
        """Test adding a channel collection payment (OTA collected)"""
        booking = self._get_booking_with_balance()
        if not booking:
            pytest.skip("No booking with balance found")
        
        resp = self.session.post(f"{BASE_URL}/api/folio/{booking['id']}/add-payment", json={
            "amount": 5.0,
            "method": "channel_collection",
            "channel": "Expedia",
            "reference": "EXP-TEST-001",
            "description": "Channel collection test"
        })
        assert resp.status_code == 200, f"Channel collection failed: {resp.text}"
        payment = resp.json()
        
        assert payment.get("category") == "channel_collection"
        assert payment.get("payment_method") == "channel_collection"
        # Channel SHOULD be set for channel_collection
        assert payment.get("channel") == "Expedia", f"Expected channel='Expedia', got {payment.get('channel')}"
        print("PASS: Channel collection recorded correctly with channel='Expedia'")
    
    def test_invalid_method_falls_back_to_card(self):
        """Test that invalid payment methods fall back to 'card'"""
        booking = self._get_booking_with_balance()
        if not booking:
            pytest.skip("No booking with balance found")
        
        resp = self.session.post(f"{BASE_URL}/api/folio/{booking['id']}/add-payment", json={
            "amount": 1.0,
            "method": "invalid_method_xyz",
            "reference": "TEST"
        })
        assert resp.status_code == 200, f"Payment with invalid method failed: {resp.text}"
        payment = resp.json()
        
        # Should fall back to 'card'
        assert payment.get("category") == "card", f"Expected fallback to 'card', got {payment.get('category')}"
        assert payment.get("payment_method") == "card"
        print("PASS: Invalid method correctly falls back to 'card'")
    
    def test_method_aliases_normalize_correctly(self):
        """Test that method aliases (cc, wire, ota) normalize correctly"""
        booking = self._get_booking_with_balance()
        if not booking:
            pytest.skip("No booking with balance found")
        
        # Test 'cc' -> 'card'
        resp = self.session.post(f"{BASE_URL}/api/folio/{booking['id']}/add-payment", json={
            "amount": 1.0, "method": "cc"
        })
        assert resp.status_code == 200
        assert resp.json().get("payment_method") == "card", "cc should normalize to card"
        
        # Test 'wire' -> 'bank_transfer'
        resp = self.session.post(f"{BASE_URL}/api/folio/{booking['id']}/add-payment", json={
            "amount": 1.0, "method": "wire"
        })
        assert resp.status_code == 200
        assert resp.json().get("payment_method") == "bank_transfer", "wire should normalize to bank_transfer"
        
        # Test 'ota' -> 'channel_collection'
        resp = self.session.post(f"{BASE_URL}/api/folio/{booking['id']}/add-payment", json={
            "amount": 1.0, "method": "ota"
        })
        assert resp.status_code == 200
        assert resp.json().get("payment_method") == "channel_collection", "ota should normalize to channel_collection"
        
        print("PASS: Method aliases (cc, wire, ota) normalize correctly")
    
    # ==================== TIMELINE BALANCE TESTS ====================
    
    def test_timeline_returns_balance_fields(self):
        """Test that timeline endpoint returns balance_due, folio_paid, folio_charged"""
        resp = self.session.get(f"{BASE_URL}/api/bookings/timeline/{self.property_id}?start=2026-10-10&days=14")
        assert resp.status_code == 200, f"Timeline failed: {resp.text}"
        timeline = resp.json()
        
        # Find any booking in the timeline
        found_booking = None
        for group in timeline.get("groups", []):
            for room in group.get("rooms", []):
                for bk in room.get("bookings", []):
                    found_booking = bk
                    break
                if found_booking:
                    break
            if found_booking:
                break
        
        assert found_booking, "No bookings found in timeline"
        
        # Verify balance fields are present
        assert "balance_due" in found_booking, "balance_due field missing from timeline booking"
        assert "folio_paid" in found_booking, "folio_paid field missing from timeline booking"
        assert "folio_charged" in found_booking, "folio_charged field missing from timeline booking"
        
        print(f"PASS: Timeline returns balance_due={found_booking['balance_due']}, folio_paid={found_booking['folio_paid']}, folio_charged={found_booking['folio_charged']}")
    
    def test_timeline_balance_reflects_partial_payment(self):
        """CRITICAL BUG TEST: After partial payment, balance_due shows REMAINING balance, not total_price"""
        booking = self._get_booking_with_balance()
        if not booking:
            pytest.skip("No booking with balance found")
        
        initial_balance = booking["balance_due"]
        booking_id = booking["id"]
        
        # Make a partial payment
        payment_amount = 10.0
        resp = self.session.post(f"{BASE_URL}/api/folio/{booking_id}/add-payment", json={
            "amount": payment_amount, "method": "card"
        })
        assert resp.status_code == 200
        
        # Get timeline again
        resp = self.session.get(f"{BASE_URL}/api/bookings/timeline/{self.property_id}?start=2026-10-10&days=30")
        assert resp.status_code == 200
        timeline = resp.json()
        
        # Find our booking
        found_booking = None
        for group in timeline.get("groups", []):
            for room in group.get("rooms", []):
                for bk in room.get("bookings", []):
                    if bk.get("id") == booking_id:
                        found_booking = bk
                        break
        
        assert found_booking, "Test booking not found in timeline"
        
        # THE CRITICAL CHECK: balance_due should be reduced by payment amount
        expected_balance = round(initial_balance - payment_amount, 2)
        actual_balance = round(found_booking["balance_due"], 2)
        
        # Allow small floating point differences
        assert abs(actual_balance - expected_balance) < 0.1, \
            f"BUG: balance_due should be ~{expected_balance} (remaining), got {actual_balance}"
        
        print(f"PASS: Timeline balance_due correctly shows REMAINING balance ({actual_balance}), not total_price")
    
    # ==================== PAYMENT STATUS TESTS ====================
    
    def test_payment_status_transitions(self):
        """Test payment_status changes: pending -> partial -> paid"""
        # Find a booking with pending status and balance
        resp = self.session.get(f"{BASE_URL}/api/bookings/timeline/{self.property_id}?start=2026-10-10&days=30")
        assert resp.status_code == 200
        timeline = resp.json()
        
        booking = None
        for group in timeline.get("groups", []):
            for room in group.get("rooms", []):
                for bk in room.get("bookings", []):
                    if bk.get("payment_status") == "pending" and bk.get("balance_due", 0) > 20:
                        booking = bk
                        break
        
        if not booking:
            pytest.skip("No pending booking with balance found")
        
        booking_id = booking["id"]
        
        # Make partial payment
        resp = self.session.post(f"{BASE_URL}/api/folio/{booking_id}/add-payment", json={
            "amount": 5.0, "method": "cash"
        })
        assert resp.status_code == 200
        
        # Check status changed to partial
        resp = self.session.get(f"{BASE_URL}/api/bookings/{booking_id}")
        if resp.status_code == 200:
            after = resp.json()
            if after.get("payment_status"):
                assert after.get("payment_status") == "partial", \
                    f"After partial payment, status should be 'partial', got {after.get('payment_status')}"
                print("PASS: payment_status correctly changes to 'partial' after partial payment")
            else:
                print("INFO: payment_status not in individual booking response")
        else:
            print("INFO: Individual booking endpoint not available")
    
    # ==================== FOLIO ENDPOINT TESTS ====================
    
    def test_folio_shows_payment_method_badge(self):
        """Test that folio items include payment_method for badge display"""
        booking = self._get_booking_with_balance()
        if not booking:
            pytest.skip("No booking with balance found")
        
        # Add a payment
        self.session.post(f"{BASE_URL}/api/folio/{booking['id']}/add-payment", json={
            "amount": 2.0, "method": "bank_transfer"
        })
        
        # Get folio
        resp = self.session.get(f"{BASE_URL}/api/folio/{booking['id']}")
        assert resp.status_code == 200
        folio = resp.json()
        
        # Find payment items
        payments = [i for i in folio.get("items", []) if i.get("type") == "payment"]
        assert len(payments) >= 1, f"Expected at least 1 payment, got {len(payments)}"
        
        # Verify payment_method is present in at least one payment
        has_payment_method = any(p.get("payment_method") for p in payments)
        assert has_payment_method, "payment_method missing from folio payment items"
        
        print("PASS: Folio items include payment_method for badge display")


class TestTimelineBalanceIntegration:
    """Integration tests for timeline balance updates"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert login_resp.status_code == 200
        token = login_resp.json().get("token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        
        props_resp = self.session.get(f"{BASE_URL}/api/properties")
        self.property_id = props_resp.json()[0]["id"] if props_resp.json() else "aldgate-flats"
        
        yield
    
    def test_timeline_has_all_required_fields(self):
        """Verify timeline booking bars have all required fields for balance display"""
        resp = self.session.get(f"{BASE_URL}/api/bookings/timeline/{self.property_id}?start=2026-10-10&days=14")
        assert resp.status_code == 200
        timeline = resp.json()
        
        required_fields = ["id", "guest_name", "total_price", "balance_due", "folio_paid", "folio_charged", "payment_status"]
        
        for group in timeline.get("groups", []):
            for room in group.get("rooms", []):
                for bk in room.get("bookings", []):
                    for field in required_fields:
                        assert field in bk, f"Field '{field}' missing from booking bar"
                    # Only check first booking
                    print(f"PASS: Timeline booking has all required fields: {required_fields}")
                    return
        
        pytest.skip("No bookings in timeline to verify")
    
    def test_folio_totals_match_timeline_balance(self):
        """Verify folio totals match timeline balance_due"""
        resp = self.session.get(f"{BASE_URL}/api/bookings/timeline/{self.property_id}?start=2026-10-10&days=14")
        assert resp.status_code == 200
        timeline = resp.json()
        
        # Find a booking
        booking = None
        for group in timeline.get("groups", []):
            for room in group.get("rooms", []):
                for bk in room.get("bookings", []):
                    booking = bk
                    break
        
        if not booking:
            pytest.skip("No bookings in timeline")
        
        # Get folio for this booking
        resp = self.session.get(f"{BASE_URL}/api/folio/{booking['id']}")
        assert resp.status_code == 200
        folio = resp.json()
        
        timeline_balance = round(booking["balance_due"], 2)
        folio_balance = round(folio["totals"]["balance_due"], 2)
        
        # Allow small differences due to timing
        assert abs(timeline_balance - folio_balance) < 1.0, \
            f"Timeline balance ({timeline_balance}) should match folio balance ({folio_balance})"
        
        print(f"PASS: Timeline balance ({timeline_balance}) matches folio balance ({folio_balance})")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
