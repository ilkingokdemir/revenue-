"""
Night Audit Wizard API Tests - Iteration 70
Tests for end-of-day reconciliation, verification, and revenue reporting
"""
import pytest
import requests
import os
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"
PROPERTY_ID = "aldgate-flats"


class TestNightAuditAPI:
    """Night Audit API endpoint tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with authentication"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login to get auth cookie
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        self.auth_token = login_response.json().get("token")
        if self.auth_token:
            self.session.headers.update({"Authorization": f"Bearer {self.auth_token}"})
        yield
        self.session.close()
    
    def test_run_night_audit(self):
        """Test POST /api/night-audit/run/{property_id} - Run night audit"""
        response = self.session.post(f"{BASE_URL}/api/night-audit/run/{PROPERTY_ID}")
        
        assert response.status_code == 200, f"Run audit failed: {response.text}"
        data = response.json()
        
        # Verify audit structure
        assert "id" in data, "Audit should have an ID"
        assert data["property_id"] == PROPERTY_ID, "Property ID should match"
        assert "audit_date" in data, "Audit should have a date"
        assert "overall_status" in data, "Audit should have overall status"
        assert data["overall_status"] in ["pass", "warning", "fail"], "Status should be pass/warning/fail"
        
        # Verify checks structure
        assert "checks" in data, "Audit should have checks"
        checks = data["checks"]
        assert "checkins" in checks, "Should have check-in verification"
        assert "checkouts" in checks, "Should have check-out verification"
        assert "payments" in checks, "Should have payment reconciliation"
        assert "pos" in checks, "Should have POS closure check"
        assert "housekeeping" in checks, "Should have housekeeping check"
        
        # Verify check-in details
        checkin = checks["checkins"]
        assert "status" in checkin, "Check-in should have status"
        assert "expected" in checkin, "Check-in should have expected count"
        assert "actual" in checkin, "Check-in should have actual count"
        assert "no_shows" in checkin, "Check-in should have no-shows count"
        
        # Verify check-out details
        checkout = checks["checkouts"]
        assert "status" in checkout, "Check-out should have status"
        assert "expected" in checkout, "Check-out should have expected count"
        assert "actual" in checkout, "Check-out should have actual count"
        assert "overstays" in checkout, "Check-out should have overstays count"
        
        # Verify payment details
        payment = checks["payments"]
        assert "status" in payment, "Payment should have status"
        assert "total_room_revenue" in payment, "Payment should have total room revenue"
        assert "total_paid" in payment, "Payment should have total paid"
        assert "total_unpaid" in payment, "Payment should have total unpaid"
        
        # Verify POS details
        pos = checks["pos"]
        assert "status" in pos, "POS should have status"
        assert "total_orders" in pos, "POS should have total orders"
        assert "paid_orders" in pos, "POS should have paid orders"
        assert "revenue" in pos, "POS should have revenue"
        
        # Verify housekeeping details
        housekeeping = checks["housekeeping"]
        assert "status" in housekeeping, "Housekeeping should have status"
        assert "dirty_rooms" in housekeeping, "Housekeeping should have dirty rooms count"
        assert "pending_tasks" in housekeeping, "Housekeeping should have pending tasks count"
        
        # Verify occupancy stats
        assert "occupancy" in data, "Audit should have occupancy stats"
        occupancy = data["occupancy"]
        assert "total_rooms" in occupancy, "Occupancy should have total rooms"
        assert "occupied" in occupancy, "Occupancy should have occupied count"
        assert "occupancy_pct" in occupancy, "Occupancy should have percentage"
        assert "adr" in occupancy, "Occupancy should have ADR"
        assert "revpar" in occupancy, "Occupancy should have RevPAR"
        
        # Verify revenue summary
        assert "revenue" in data, "Audit should have revenue summary"
        revenue = data["revenue"]
        assert "room_revenue" in revenue, "Revenue should have room revenue"
        assert "pos_revenue" in revenue, "Revenue should have POS revenue"
        assert "total_revenue" in revenue, "Revenue should have total revenue"
        
        # Store audit ID for later tests
        self.audit_id = data["id"]
        print(f"✓ Night audit run successfully: {data['pass_count']}/{data['total_checks']} checks passed")
        print(f"  Overall status: {data['overall_status']}")
        print(f"  Total revenue: £{data['revenue']['total_revenue']}")
        print(f"  Occupancy: {data['occupancy']['occupancy_pct']}%")
        
        return data
    
    def test_get_audit_history(self):
        """Test GET /api/night-audit/history/{property_id} - Get audit history"""
        response = self.session.get(f"{BASE_URL}/api/night-audit/history/{PROPERTY_ID}")
        
        assert response.status_code == 200, f"Get history failed: {response.text}"
        data = response.json()
        
        assert isinstance(data, list), "History should be a list"
        
        if len(data) > 0:
            audit = data[0]
            assert "id" in audit, "History item should have ID"
            assert "audit_date" in audit, "History item should have date"
            assert "overall_status" in audit, "History item should have status"
            assert "pass_count" in audit, "History item should have pass count"
            assert "total_checks" in audit, "History item should have total checks"
            print(f"✓ Audit history retrieved: {len(data)} audits found")
        else:
            print("✓ Audit history retrieved: No audits yet")
    
    def test_get_latest_audit(self):
        """Test GET /api/night-audit/latest/{property_id} - Get most recent audit"""
        response = self.session.get(f"{BASE_URL}/api/night-audit/latest/{PROPERTY_ID}")
        
        assert response.status_code == 200, f"Get latest failed: {response.text}"
        data = response.json()
        
        if data:
            assert "id" in data, "Latest audit should have ID"
            assert "audit_date" in data, "Latest audit should have date"
            assert "overall_status" in data, "Latest audit should have status"
            print(f"✓ Latest audit retrieved: {data['audit_date']} - {data['overall_status']}")
        else:
            print("✓ Latest audit endpoint works (no audits yet)")
    
    def test_complete_audit(self):
        """Test POST /api/night-audit/complete/{audit_id} - Complete audit with notes"""
        # First run an audit to get an ID
        run_response = self.session.post(f"{BASE_URL}/api/night-audit/run/{PROPERTY_ID}")
        assert run_response.status_code == 200, f"Run audit failed: {run_response.text}"
        audit_id = run_response.json()["id"]
        
        # Complete the audit with notes
        complete_response = self.session.post(
            f"{BASE_URL}/api/night-audit/complete/{audit_id}",
            json={"notes": "Test shift notes - all systems verified"}
        )
        
        assert complete_response.status_code == 200, f"Complete audit failed: {complete_response.text}"
        data = complete_response.json()
        
        assert data["status"] == "completed", "Should return completed status"
        assert "message" in data, "Should have completion message"
        print(f"✓ Audit completed successfully: {data['message']}")
    
    def test_mark_no_show(self):
        """Test POST /api/night-audit/mark-no-show/{booking_id} - Mark booking as no-show"""
        # Use a test booking ID (this may not exist, but we test the endpoint)
        test_booking_id = "test-booking-123"
        
        response = self.session.post(f"{BASE_URL}/api/night-audit/mark-no-show/{test_booking_id}")
        
        # Should succeed even if booking doesn't exist (updates 0 documents)
        assert response.status_code == 200, f"Mark no-show failed: {response.text}"
        data = response.json()
        
        assert data["status"] == "marked_no_show", "Should return marked_no_show status"
        print("✓ Mark no-show endpoint works correctly")
    
    def test_audit_without_auth(self):
        """Test that audit endpoints require authentication"""
        # Create a new session without auth
        no_auth_session = requests.Session()
        no_auth_session.headers.update({"Content-Type": "application/json"})
        
        response = no_auth_session.post(f"{BASE_URL}/api/night-audit/run/{PROPERTY_ID}")
        
        # Should return 401 Unauthorized
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ Audit endpoints properly require authentication")
        
        no_auth_session.close()
    
    def test_audit_data_persistence(self):
        """Test that audit data is properly persisted"""
        # Run an audit
        run_response = self.session.post(f"{BASE_URL}/api/night-audit/run/{PROPERTY_ID}")
        assert run_response.status_code == 200
        audit_id = run_response.json()["id"]
        
        # Verify it appears in history
        history_response = self.session.get(f"{BASE_URL}/api/night-audit/history/{PROPERTY_ID}")
        assert history_response.status_code == 200
        history = history_response.json()
        
        audit_ids = [a["id"] for a in history]
        assert audit_id in audit_ids, "New audit should appear in history"
        print("✓ Audit data properly persisted to database")


class TestNightAuditChecks:
    """Tests for individual audit check calculations"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with authentication"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert login_response.status_code == 200
        self.auth_token = login_response.json().get("token")
        if self.auth_token:
            self.session.headers.update({"Authorization": f"Bearer {self.auth_token}"})
        yield
        self.session.close()
    
    def test_check_status_values(self):
        """Test that all checks return valid status values"""
        response = self.session.post(f"{BASE_URL}/api/night-audit/run/{PROPERTY_ID}")
        assert response.status_code == 200
        
        data = response.json()
        checks = data["checks"]
        
        valid_statuses = ["pass", "warning", "fail"]
        
        for check_name, check_data in checks.items():
            assert check_data["status"] in valid_statuses, f"{check_name} has invalid status: {check_data['status']}"
        
        print("✓ All check statuses are valid (pass/warning/fail)")
    
    def test_revenue_calculations(self):
        """Test that revenue calculations are correct"""
        response = self.session.post(f"{BASE_URL}/api/night-audit/run/{PROPERTY_ID}")
        assert response.status_code == 200
        
        data = response.json()
        revenue = data["revenue"]
        
        # All revenue values should be non-negative
        assert revenue["room_revenue"] >= 0, "Room revenue should be non-negative"
        assert revenue["pos_revenue"] >= 0, "POS revenue should be non-negative"
        assert revenue["total_revenue"] >= 0, "Total revenue should be non-negative"
        
        # Total should be sum of components (approximately, due to payment_transactions)
        expected_min = revenue["room_revenue"] + revenue["pos_revenue"]
        assert revenue["total_revenue"] >= expected_min, "Total revenue should include room + POS"
        
        print(f"✓ Revenue calculations valid: Room £{revenue['room_revenue']}, POS £{revenue['pos_revenue']}, Total £{revenue['total_revenue']}")
    
    def test_occupancy_calculations(self):
        """Test that occupancy calculations are correct"""
        response = self.session.post(f"{BASE_URL}/api/night-audit/run/{PROPERTY_ID}")
        assert response.status_code == 200
        
        data = response.json()
        occupancy = data["occupancy"]
        
        # Occupancy percentage should be between 0 and 100
        assert 0 <= occupancy["occupancy_pct"] <= 100, "Occupancy percentage should be 0-100"
        
        # Occupied + available should equal total
        assert occupancy["occupied"] + occupancy["available"] == occupancy["total_rooms"], \
            "Occupied + available should equal total rooms"
        
        # ADR and RevPAR should be non-negative
        assert occupancy["adr"] >= 0, "ADR should be non-negative"
        assert occupancy["revpar"] >= 0, "RevPAR should be non-negative"
        
        print(f"✓ Occupancy calculations valid: {occupancy['occupied']}/{occupancy['total_rooms']} rooms ({occupancy['occupancy_pct']}%)")
        print(f"  ADR: £{occupancy['adr']}, RevPAR: £{occupancy['revpar']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
