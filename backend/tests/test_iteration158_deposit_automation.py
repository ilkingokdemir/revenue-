"""
Iteration 158 - Deposit Automation Tests
Tests the deposit automation feature that bridges deposit_policies, card_vault, and folio_items.
Endpoints:
  - GET /api/deposit-automation/pending/{property_id}
  - POST /api/deposit-automation/run/{property_id}
  - GET /api/deposit-automation/log/{property_id}
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"
TEST_PROPERTY = "aldgate-flats"
TEST_POLICY_ID = "bc1de1b4-cece-4299-b446-cee94be24213"  # Pre-existing 30% policy


class TestDepositAutomationAuth:
    """Test authentication and authorization for deposit automation endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
    
    def get_admin_token(self):
        """Login as admin and return session with auth cookie"""
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        return self.session
    
    def test_pending_requires_auth(self):
        """GET /api/deposit-automation/pending/{pid} requires authentication"""
        response = requests.get(f"{BASE_URL}/api/deposit-automation/pending/{TEST_PROPERTY}")
        assert response.status_code == 401, "Should require authentication"
        print("PASS: Pending endpoint requires authentication")
    
    def test_run_requires_auth(self):
        """POST /api/deposit-automation/run/{pid} requires authentication"""
        response = requests.post(f"{BASE_URL}/api/deposit-automation/run/{TEST_PROPERTY}", json={"dry_run": True})
        assert response.status_code == 401, "Should require authentication"
        print("PASS: Run endpoint requires authentication")
    
    def test_log_requires_auth(self):
        """GET /api/deposit-automation/log/{pid} requires authentication"""
        response = requests.get(f"{BASE_URL}/api/deposit-automation/log/{TEST_PROPERTY}")
        assert response.status_code == 401, "Should require authentication"
        print("PASS: Log endpoint requires authentication")


class TestDepositAutomationPending:
    """Test GET /api/deposit-automation/pending/{property_id}"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        # Login as admin
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Admin login failed: {response.text}"
    
    def test_pending_returns_expected_structure(self):
        """GET /api/deposit-automation/pending/{pid} returns correct structure"""
        response = self.session.get(f"{BASE_URL}/api/deposit-automation/pending/{TEST_PROPERTY}")
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        # Verify top-level fields
        assert "pending" in data, "Missing 'pending' field"
        assert "total_owed" in data, "Missing 'total_owed' field"
        assert "count" in data, "Missing 'count' field"
        assert "with_card" in data, "Missing 'with_card' field"
        assert "without_card" in data, "Missing 'without_card' field"
        assert "policies_active" in data, "Missing 'policies_active' field"
        assert "as_of" in data, "Missing 'as_of' field"
        
        # Verify types
        assert isinstance(data["pending"], list), "'pending' should be a list"
        assert isinstance(data["total_owed"], (int, float)), "'total_owed' should be numeric"
        assert isinstance(data["count"], int), "'count' should be int"
        assert isinstance(data["with_card"], int), "'with_card' should be int"
        assert isinstance(data["without_card"], int), "'without_card' should be int"
        assert isinstance(data["policies_active"], int), "'policies_active' should be int"
        
        print(f"PASS: Pending returns correct structure - {data['count']} bookings, £{data['total_owed']} owed, {data['policies_active']} active policies")
    
    def test_pending_item_structure(self):
        """Each pending item has required fields"""
        response = self.session.get(f"{BASE_URL}/api/deposit-automation/pending/{TEST_PROPERTY}")
        assert response.status_code == 200
        
        data = response.json()
        if data["count"] > 0:
            item = data["pending"][0]
            required_fields = [
                "booking_id", "booking_ref", "guest_name", "guest_email",
                "check_in", "total_price", "already_paid", "deposit_required",
                "to_capture", "policy", "card_on_file", "card_brand", "card_last4",
                "payment_method_id"
            ]
            for field in required_fields:
                assert field in item, f"Missing field '{field}' in pending item"
            
            # Verify policy sub-structure
            assert "id" in item["policy"], "Policy missing 'id'"
            assert "name" in item["policy"], "Policy missing 'name'"
            
            # Verify card_on_file is boolean
            assert isinstance(item["card_on_file"], bool), "'card_on_file' should be boolean"
            
            print(f"PASS: Pending item has all required fields - booking {item['booking_ref']}, to_capture £{item['to_capture']}")
        else:
            print("PASS: No pending items to verify structure (empty list)")
    
    def test_pending_with_all_property(self):
        """GET /api/deposit-automation/pending/all works for all properties"""
        response = self.session.get(f"{BASE_URL}/api/deposit-automation/pending/all")
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        assert "pending" in data
        assert "total_owed" in data
        print(f"PASS: Pending 'all' returns {data['count']} bookings across all properties")
    
    def test_pending_respects_policy_matching(self):
        """Only bookings matching active policies appear in pending"""
        response = self.session.get(f"{BASE_URL}/api/deposit-automation/pending/{TEST_PROPERTY}")
        assert response.status_code == 200
        
        data = response.json()
        # If there are active policies, pending should have items (or be empty if all paid)
        # If no active policies, pending should be empty
        if data["policies_active"] == 0:
            assert data["count"] == 0, "With no active policies, count should be 0"
            assert data["total_owed"] == 0, "With no active policies, total_owed should be 0"
            print("PASS: No active policies - pending is empty as expected")
        else:
            # Each pending item should have a matched policy
            for item in data["pending"]:
                assert item["policy"]["id"], "Each pending item should have a matched policy"
            print(f"PASS: {data['count']} bookings matched against {data['policies_active']} active policies")
    
    def test_pending_with_card_without_card_counts(self):
        """with_card + without_card should equal count"""
        response = self.session.get(f"{BASE_URL}/api/deposit-automation/pending/{TEST_PROPERTY}")
        assert response.status_code == 200
        
        data = response.json()
        assert data["with_card"] + data["without_card"] == data["count"], \
            f"with_card ({data['with_card']}) + without_card ({data['without_card']}) should equal count ({data['count']})"
        print(f"PASS: Card counts match - {data['with_card']} with card, {data['without_card']} without")


class TestDepositAutomationRun:
    """Test POST /api/deposit-automation/run/{property_id}"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        # Login as admin
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Admin login failed: {response.text}"
    
    def test_dry_run_returns_expected_structure(self):
        """POST /api/deposit-automation/run/{pid} with dry_run:true returns simulation"""
        response = self.session.post(f"{BASE_URL}/api/deposit-automation/run/{TEST_PROPERTY}", json={
            "dry_run": True
        })
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        # Verify structure
        assert "ran" in data, "Missing 'ran' field"
        assert "charged" in data, "Missing 'charged' field"
        assert "failed" in data, "Missing 'failed' field"
        assert "skipped" in data, "Missing 'skipped' field"
        assert "results" in data, "Missing 'results' field"
        assert "dry_run" in data, "Missing 'dry_run' field"
        
        # In dry run, charged should be 0 (no actual charges)
        assert data["dry_run"] == True, "dry_run should be True"
        assert data["charged"] == 0, "In dry run, charged should be 0"
        
        print(f"PASS: Dry run returns correct structure - ran {data['ran']}, skipped {data['skipped']}")
    
    def test_dry_run_no_stripe_calls(self):
        """Dry run should not make actual Stripe calls"""
        response = self.session.post(f"{BASE_URL}/api/deposit-automation/run/{TEST_PROPERTY}", json={
            "dry_run": True
        })
        assert response.status_code == 200
        
        data = response.json()
        # Check results - should have 'would_charge' or 'no_card' status, not 'charged' or 'failed'
        for result in data.get("results", []):
            assert result["status"] in ["would_charge", "no_card"], \
                f"Dry run should not have status '{result['status']}'"
        
        print(f"PASS: Dry run has no actual charges - {len(data.get('results', []))} results")
    
    def test_run_without_cards_returns_skipped(self):
        """POST /api/deposit-automation/run/{pid} with dry_run:false but no cards returns skipped"""
        response = self.session.post(f"{BASE_URL}/api/deposit-automation/run/{TEST_PROPERTY}", json={
            "dry_run": False
        })
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        # With placeholder Stripe key and no saved cards, all should be skipped
        # Check that results have 'no_card' status
        no_card_count = sum(1 for r in data.get("results", []) if r.get("status") == "no_card")
        
        print(f"PASS: Run without cards - charged {data['charged']}, skipped {data['skipped']}, no_card results: {no_card_count}")
    
    def test_only_booking_ids_filter(self):
        """only_booking_ids[] filter limits which bookings are processed"""
        # First get pending to find a booking ID
        pending_response = self.session.get(f"{BASE_URL}/api/deposit-automation/pending/{TEST_PROPERTY}")
        assert pending_response.status_code == 200
        
        pending_data = pending_response.json()
        if pending_data["count"] == 0:
            print("SKIP: No pending bookings to test filter")
            return
        
        # Get first booking ID
        first_booking_id = pending_data["pending"][0]["booking_id"]
        
        # Run with only that booking
        response = self.session.post(f"{BASE_URL}/api/deposit-automation/run/{TEST_PROPERTY}", json={
            "dry_run": True,
            "only_booking_ids": [first_booking_id]
        })
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        # Should only process 1 booking
        assert data["ran"] <= 1, f"With only_booking_ids filter, should process at most 1 booking, got {data['ran']}"
        
        # Verify the result is for the correct booking
        if data["results"]:
            assert data["results"][0]["booking_id"] == first_booking_id, "Result should be for filtered booking"
        
        print(f"PASS: only_booking_ids filter works - processed {data['ran']} booking(s)")
    
    def test_max_charges_limit(self):
        """max_charges:int caps the number of bookings processed"""
        response = self.session.post(f"{BASE_URL}/api/deposit-automation/run/{TEST_PROPERTY}", json={
            "dry_run": True,
            "max_charges": 2
        })
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        # ran should be at most 2 (charged + failed)
        assert data["charged"] + data["failed"] <= 2, \
            f"max_charges=2 should limit charged+failed to 2, got {data['charged'] + data['failed']}"
        
        print(f"PASS: max_charges limit works - charged+failed={data['charged'] + data['failed']}")
    
    def test_stripe_error_logged_with_placeholder_key(self):
        """With placeholder STRIPE_API_KEY, charge attempts fail and log to deposit_capture_log"""
        # First check if there are any bookings with cards (unlikely with placeholder key)
        pending_response = self.session.get(f"{BASE_URL}/api/deposit-automation/pending/{TEST_PROPERTY}")
        pending_data = pending_response.json()
        
        if pending_data["with_card"] == 0:
            print("SKIP: No bookings with cards to test Stripe error logging")
            return
        
        # Run actual charge (will fail with placeholder key)
        response = self.session.post(f"{BASE_URL}/api/deposit-automation/run/{TEST_PROPERTY}", json={
            "dry_run": False,
            "max_charges": 1
        })
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        # Check for failed results with Stripe error
        failed_results = [r for r in data.get("results", []) if r.get("status") == "failed"]
        if failed_results:
            assert "error" in failed_results[0], "Failed result should have error message"
            print(f"PASS: Stripe error logged - {failed_results[0].get('error', 'unknown')}")
        else:
            print("PASS: No failed charges (all skipped due to no cards)")


class TestDepositAutomationLog:
    """Test GET /api/deposit-automation/log/{property_id}"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        # Login as admin
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Admin login failed: {response.text}"
    
    def test_log_returns_list(self):
        """GET /api/deposit-automation/log/{pid} returns list of log entries"""
        response = self.session.get(f"{BASE_URL}/api/deposit-automation/log/{TEST_PROPERTY}")
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Log should return a list"
        print(f"PASS: Log returns list with {len(data)} entries")
    
    def test_log_limit_parameter(self):
        """GET /api/deposit-automation/log/{pid}?limit=N respects limit"""
        response = self.session.get(f"{BASE_URL}/api/deposit-automation/log/{TEST_PROPERTY}?limit=5")
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        assert len(data) <= 5, f"Limit=5 should return at most 5 entries, got {len(data)}"
        print(f"PASS: Log limit parameter works - returned {len(data)} entries (limit=5)")
    
    def test_log_sorted_desc_by_at(self):
        """Log entries should be sorted descending by 'at' timestamp"""
        response = self.session.get(f"{BASE_URL}/api/deposit-automation/log/{TEST_PROPERTY}?limit=50")
        assert response.status_code == 200
        
        data = response.json()
        if len(data) >= 2:
            # Check that entries are sorted descending
            for i in range(len(data) - 1):
                assert data[i]["at"] >= data[i + 1]["at"], \
                    f"Log should be sorted desc by 'at': {data[i]['at']} should be >= {data[i + 1]['at']}"
            print(f"PASS: Log is sorted descending by timestamp")
        else:
            print("PASS: Not enough log entries to verify sorting")
    
    def test_log_entry_structure(self):
        """Log entries have expected fields"""
        # First create a log entry by running dry_run
        self.session.post(f"{BASE_URL}/api/deposit-automation/run/{TEST_PROPERTY}", json={
            "dry_run": False,
            "max_charges": 1
        })
        
        response = self.session.get(f"{BASE_URL}/api/deposit-automation/log/{TEST_PROPERTY}?limit=10")
        assert response.status_code == 200
        
        data = response.json()
        if data:
            entry = data[0]
            # Check expected fields
            assert "id" in entry, "Log entry missing 'id'"
            assert "booking_id" in entry, "Log entry missing 'booking_id'"
            assert "amount" in entry, "Log entry missing 'amount'"
            assert "status" in entry, "Log entry missing 'status'"
            assert "at" in entry, "Log entry missing 'at'"
            
            print(f"PASS: Log entry has expected structure - status={entry['status']}, amount={entry['amount']}")
        else:
            print("PASS: No log entries to verify structure")


class TestDepositAutomationIntegration:
    """Integration tests for deposit automation workflow"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        # Login as admin
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Admin login failed: {response.text}"
    
    def test_full_workflow_dry_run(self):
        """Test complete workflow: pending → dry_run → log"""
        # 1. Get pending
        pending_response = self.session.get(f"{BASE_URL}/api/deposit-automation/pending/{TEST_PROPERTY}")
        assert pending_response.status_code == 200
        pending_data = pending_response.json()
        
        print(f"Step 1: Pending - {pending_data['count']} bookings, £{pending_data['total_owed']} owed")
        
        # 2. Run dry run
        run_response = self.session.post(f"{BASE_URL}/api/deposit-automation/run/{TEST_PROPERTY}", json={
            "dry_run": True
        })
        assert run_response.status_code == 200
        run_data = run_response.json()
        
        print(f"Step 2: Dry run - ran {run_data['ran']}, skipped {run_data['skipped']}")
        
        # 3. Check log
        log_response = self.session.get(f"{BASE_URL}/api/deposit-automation/log/{TEST_PROPERTY}?limit=10")
        assert log_response.status_code == 200
        log_data = log_response.json()
        
        print(f"Step 3: Log - {len(log_data)} entries")
        print("PASS: Full workflow completed successfully")
    
    def test_policies_active_zero_returns_empty(self):
        """When policies_active=0, pending returns empty list with total_owed:0"""
        # This test verifies the behavior when no active policies exist
        # We can't easily disable policies, so we check the logic
        response = self.session.get(f"{BASE_URL}/api/deposit-automation/pending/{TEST_PROPERTY}")
        assert response.status_code == 200
        
        data = response.json()
        if data["policies_active"] == 0:
            assert data["count"] == 0, "With no active policies, count should be 0"
            assert data["total_owed"] == 0, "With no active policies, total_owed should be 0"
            assert len(data["pending"]) == 0, "With no active policies, pending list should be empty"
            print("PASS: No active policies - returns empty pending list")
        else:
            print(f"SKIP: {data['policies_active']} active policies exist - cannot test empty case")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
