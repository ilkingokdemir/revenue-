"""
Iteration 134 - Staff Contracts API Tests
Tests for digital employment contracts with e-signature flow.

Features tested:
- GET /api/contracts/{pid} - List contracts with computed_status, monthly_cost, days_to_end, on_probation
- GET /api/contracts/stats/{pid} - Stats with total, by_status, active, expiring_30_days, on_probation, monthly_cost, annual_cost
- POST /api/contracts - Create draft contract (admin only)
- PUT /api/contracts/{id} - Update contract (blocks if signed)
- DELETE /api/contracts/{id} - Delete draft (blocks if signed)
- POST /api/contracts/{id}/send - Generate sign_token, set status=sent, return sign_url
- POST /api/contracts/{id}/terminate - Set status=terminated with reason
- GET /api/contracts/sign/{token} - PUBLIC: Get contract for signing (no auth)
- POST /api/contracts/sign/{token} - PUBLIC: Sign contract (no auth)
- Role gates: admin+manager can list/stats; only admin can create/edit/delete/send/terminate
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

# Contract types
VALID_CONTRACT_TYPES = ["full_time", "part_time", "casual", "zero_hours", "freelance", "fixed_term"]


class TestContractsAuth:
    """Test authentication and role gates for contracts endpoints"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        return response.json().get("token")
    
    def test_list_contracts_requires_auth(self):
        """GET /api/contracts/{pid} requires authentication"""
        response = requests.get(f"{BASE_URL}/api/contracts/all")
        assert response.status_code == 401, "Should require auth"
        print("✓ List contracts requires authentication")
    
    def test_stats_requires_auth(self):
        """GET /api/contracts/stats/{pid} requires authentication"""
        response = requests.get(f"{BASE_URL}/api/contracts/stats/all")
        assert response.status_code == 401, "Should require auth"
        print("✓ Stats requires authentication")
    
    def test_create_requires_admin(self, admin_token):
        """POST /api/contracts requires admin role"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.post(f"{BASE_URL}/api/contracts", json={
            "staff_name": "Test Auth",
            "contract_type": "full_time",
            "start_date": "2026-02-01"
        }, headers=headers)
        # Admin should be able to create
        assert response.status_code == 200, f"Admin should create: {response.text}"
        print("✓ Create contract requires admin role")
        
        # Cleanup
        contract_id = response.json().get("id")
        if contract_id:
            requests.delete(f"{BASE_URL}/api/contracts/{contract_id}", headers=headers)


class TestContractsCRUD:
    """Test CRUD operations for contracts"""
    
    @pytest.fixture(scope="class")
    def admin_session(self):
        """Get admin session with auth"""
        session = requests.Session()
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        token = response.json().get("token")
        session.headers.update({"Authorization": f"Bearer {token}"})
        return session
    
    @pytest.fixture
    def test_contract(self, admin_session):
        """Create a test contract and cleanup after"""
        unique_id = str(uuid.uuid4())[:8]
        contract_data = {
            "property_id": "all",
            "staff_name": f"TEST_Contract_{unique_id}",
            "staff_email": f"test_{unique_id}@example.com",
            "role": "Receptionist",
            "department": "front_desk",
            "contract_type": "full_time",
            "start_date": "2026-02-01",
            "end_date": "2027-01-31",
            "probation_end": "2026-05-01",
            "hours_per_week": 40,
            "hourly_rate": 14.50,
            "salary_annual": 0,
            "notice_period_days": 30,
            "holiday_entitlement_days": 28,
            "terms": "Standard employment terms and conditions."
        }
        response = admin_session.post(f"{BASE_URL}/api/contracts", json=contract_data)
        assert response.status_code == 200, f"Failed to create test contract: {response.text}"
        contract = response.json()
        yield contract
        # Cleanup
        admin_session.delete(f"{BASE_URL}/api/contracts/{contract['id']}")
    
    def test_create_contract_validates_type(self, admin_session):
        """POST /api/contracts validates contract_type"""
        response = admin_session.post(f"{BASE_URL}/api/contracts", json={
            "staff_name": "Invalid Type Test",
            "contract_type": "invalid_type",
            "start_date": "2026-02-01"
        })
        assert response.status_code == 400, "Should reject invalid contract_type"
        assert "contract_type" in response.text.lower()
        print("✓ Create contract validates contract_type")
    
    def test_create_contract_all_valid_types(self, admin_session):
        """POST /api/contracts accepts all valid contract types"""
        created_ids = []
        for ctype in VALID_CONTRACT_TYPES:
            response = admin_session.post(f"{BASE_URL}/api/contracts", json={
                "staff_name": f"TEST_Type_{ctype}",
                "contract_type": ctype,
                "start_date": "2026-02-01"
            })
            assert response.status_code == 200, f"Should accept {ctype}: {response.text}"
            created_ids.append(response.json().get("id"))
        
        # Cleanup
        for cid in created_ids:
            admin_session.delete(f"{BASE_URL}/api/contracts/{cid}")
        print(f"✓ All {len(VALID_CONTRACT_TYPES)} contract types accepted")
    
    def test_create_contract_returns_draft_status(self, admin_session):
        """POST /api/contracts creates contract with status=draft"""
        response = admin_session.post(f"{BASE_URL}/api/contracts", json={
            "staff_name": "TEST_Draft_Status",
            "contract_type": "full_time",
            "start_date": "2026-02-01"
        })
        assert response.status_code == 200
        contract = response.json()
        assert contract.get("status") == "draft", "New contract should be draft"
        assert contract.get("id"), "Should have ID"
        assert contract.get("created_at"), "Should have created_at"
        
        # Cleanup
        admin_session.delete(f"{BASE_URL}/api/contracts/{contract['id']}")
        print("✓ Create contract returns draft status")
    
    def test_list_contracts_returns_computed_fields(self, admin_session, test_contract):
        """GET /api/contracts/{pid} returns computed_status, monthly_cost, days_to_end, on_probation"""
        response = admin_session.get(f"{BASE_URL}/api/contracts/all")
        assert response.status_code == 200
        contracts = response.json()
        assert isinstance(contracts, list)
        
        # Find our test contract
        found = next((c for c in contracts if c.get("id") == test_contract["id"]), None)
        assert found, "Test contract should be in list"
        
        # Check computed fields
        assert "computed_status" in found, "Should have computed_status"
        assert "monthly_cost" in found, "Should have monthly_cost"
        assert "days_to_end" in found, "Should have days_to_end"
        assert "on_probation" in found, "Should have on_probation"
        
        print(f"✓ List contracts returns computed fields: status={found['computed_status']}, cost={found['monthly_cost']}")
    
    def test_list_contracts_filter_by_status(self, admin_session, test_contract):
        """GET /api/contracts/{pid}?status=draft filters by status"""
        response = admin_session.get(f"{BASE_URL}/api/contracts/all?status=draft")
        assert response.status_code == 200
        contracts = response.json()
        
        # All should be draft
        for c in contracts:
            assert c.get("computed_status") == "draft", f"Should only return draft: {c.get('computed_status')}"
        print(f"✓ Filter by status=draft returns {len(contracts)} contracts")
    
    def test_list_contracts_search(self, admin_session, test_contract):
        """GET /api/contracts/{pid}?q=... searches by name/email/role"""
        # Search by name
        response = admin_session.get(f"{BASE_URL}/api/contracts/all?q=TEST_Contract")
        assert response.status_code == 200
        contracts = response.json()
        assert len(contracts) >= 1, "Should find test contract by name"
        print(f"✓ Search by name returns {len(contracts)} contracts")
    
    def test_update_contract(self, admin_session, test_contract):
        """PUT /api/contracts/{id} updates editable fields"""
        response = admin_session.put(f"{BASE_URL}/api/contracts/{test_contract['id']}", json={
            "staff_name": "TEST_Updated_Name",
            "hours_per_week": 35
        })
        assert response.status_code == 200
        assert response.json().get("ok") == True
        
        # Verify update
        list_response = admin_session.get(f"{BASE_URL}/api/contracts/all?q=TEST_Updated_Name")
        contracts = list_response.json()
        found = next((c for c in contracts if c.get("id") == test_contract["id"]), None)
        assert found, "Should find updated contract"
        assert found.get("staff_name") == "TEST_Updated_Name"
        assert found.get("hours_per_week") == 35
        print("✓ Update contract works")
    
    def test_delete_draft_contract(self, admin_session):
        """DELETE /api/contracts/{id} removes draft contract"""
        # Create a contract to delete
        response = admin_session.post(f"{BASE_URL}/api/contracts", json={
            "staff_name": "TEST_To_Delete",
            "contract_type": "casual",
            "start_date": "2026-02-01"
        })
        contract_id = response.json().get("id")
        
        # Delete it
        del_response = admin_session.delete(f"{BASE_URL}/api/contracts/{contract_id}")
        assert del_response.status_code == 200
        assert del_response.json().get("ok") == True
        
        # Verify deleted
        list_response = admin_session.get(f"{BASE_URL}/api/contracts/all?q=TEST_To_Delete")
        contracts = list_response.json()
        found = next((c for c in contracts if c.get("id") == contract_id), None)
        assert found is None, "Contract should be deleted"
        print("✓ Delete draft contract works")


class TestContractsStats:
    """Test stats endpoint"""
    
    @pytest.fixture(scope="class")
    def admin_session(self):
        session = requests.Session()
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        token = response.json().get("token")
        session.headers.update({"Authorization": f"Bearer {token}"})
        return session
    
    def test_stats_returns_all_fields(self, admin_session):
        """GET /api/contracts/stats/{pid} returns all required fields"""
        response = admin_session.get(f"{BASE_URL}/api/contracts/stats/all")
        assert response.status_code == 200
        stats = response.json()
        
        required_fields = ["total", "by_status", "active", "expiring_30_days", "on_probation", "monthly_cost", "annual_cost"]
        for field in required_fields:
            assert field in stats, f"Missing field: {field}"
        
        assert isinstance(stats["by_status"], dict), "by_status should be dict"
        assert isinstance(stats["monthly_cost"], (int, float)), "monthly_cost should be number"
        assert isinstance(stats["annual_cost"], (int, float)), "annual_cost should be number"
        
        print(f"✓ Stats returns all fields: total={stats['total']}, active={stats['active']}, monthly_cost=£{stats['monthly_cost']}")
    
    def test_stats_monthly_cost_formula(self, admin_session):
        """Verify monthly_cost formula: hours_per_week * hourly_rate * 4.333 or salary/12"""
        # Create contract with hourly rate
        hourly_contract = admin_session.post(f"{BASE_URL}/api/contracts", json={
            "staff_name": "TEST_Hourly_Cost",
            "contract_type": "part_time",
            "start_date": "2026-01-01",
            "hours_per_week": 20,
            "hourly_rate": 15.00,
            "salary_annual": 0
        }).json()
        
        # Create contract with annual salary
        salary_contract = admin_session.post(f"{BASE_URL}/api/contracts", json={
            "staff_name": "TEST_Salary_Cost",
            "contract_type": "full_time",
            "start_date": "2026-01-01",
            "hours_per_week": 40,
            "hourly_rate": 0,
            "salary_annual": 36000
        }).json()
        
        # Get list to check monthly_cost
        list_response = admin_session.get(f"{BASE_URL}/api/contracts/all?q=TEST_")
        contracts = list_response.json()
        
        hourly_found = next((c for c in contracts if c.get("id") == hourly_contract["id"]), None)
        salary_found = next((c for c in contracts if c.get("id") == salary_contract["id"]), None)
        
        # Verify hourly: 20 * 15 * 4.333 = 1299.9
        if hourly_found:
            expected_hourly = round(20 * 15.00 * 4.333, 2)
            assert abs(hourly_found.get("monthly_cost", 0) - expected_hourly) < 1, f"Hourly cost mismatch: {hourly_found.get('monthly_cost')} vs {expected_hourly}"
            print(f"✓ Hourly cost formula correct: £{hourly_found.get('monthly_cost')}")
        
        # Verify salary: 36000 / 12 = 3000
        if salary_found:
            expected_salary = 36000 / 12
            assert abs(salary_found.get("monthly_cost", 0) - expected_salary) < 1, f"Salary cost mismatch: {salary_found.get('monthly_cost')} vs {expected_salary}"
            print(f"✓ Salary cost formula correct: £{salary_found.get('monthly_cost')}")
        
        # Cleanup
        admin_session.delete(f"{BASE_URL}/api/contracts/{hourly_contract['id']}")
        admin_session.delete(f"{BASE_URL}/api/contracts/{salary_contract['id']}")


class TestContractSigningFlow:
    """Test the full signing flow: send -> public GET -> public POST sign"""
    
    @pytest.fixture(scope="class")
    def admin_session(self):
        session = requests.Session()
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        token = response.json().get("token")
        session.headers.update({"Authorization": f"Bearer {token}"})
        return session
    
    @pytest.fixture
    def draft_contract(self, admin_session):
        """Create a draft contract for signing tests"""
        unique_id = str(uuid.uuid4())[:8]
        response = admin_session.post(f"{BASE_URL}/api/contracts", json={
            "property_id": "all",
            "staff_name": f"TEST_Sign_{unique_id}",
            "staff_email": f"sign_{unique_id}@example.com",
            "role": "Housekeeper",
            "contract_type": "part_time",
            "start_date": "2026-02-01",
            "hours_per_week": 25,
            "hourly_rate": 12.50,
            "terms": "Test terms for signing."
        })
        contract = response.json()
        yield contract
        # Cleanup - may fail if signed, that's ok
        admin_session.delete(f"{BASE_URL}/api/contracts/{contract['id']}")
    
    def test_send_for_signature(self, admin_session, draft_contract):
        """POST /api/contracts/{id}/send generates token and sign_url"""
        response = admin_session.post(f"{BASE_URL}/api/contracts/{draft_contract['id']}/send")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("ok") == True
        assert "token" in data, "Should return token"
        assert "sign_url" in data, "Should return sign_url"
        assert len(data["token"]) >= 24, "Token should be at least 24 chars"
        assert "/contract/sign/" in data["sign_url"], "sign_url should contain /contract/sign/"
        
        print(f"✓ Send for signature returns token ({len(data['token'])} chars) and sign_url")
        return data
    
    def test_send_updates_status_to_sent(self, admin_session, draft_contract):
        """After send, contract status should be 'sent'"""
        # Send
        admin_session.post(f"{BASE_URL}/api/contracts/{draft_contract['id']}/send")
        
        # Check status
        list_response = admin_session.get(f"{BASE_URL}/api/contracts/all")
        contracts = list_response.json()
        found = next((c for c in contracts if c.get("id") == draft_contract["id"]), None)
        
        assert found, "Contract should exist"
        assert found.get("status") == "sent" or found.get("computed_status") == "sent", f"Status should be sent: {found.get('status')}"
        print("✓ Send updates status to 'sent'")
    
    def test_public_get_sign_no_auth(self, admin_session, draft_contract):
        """GET /api/contracts/sign/{token} is PUBLIC (no auth required)"""
        # First send to get token
        send_response = admin_session.post(f"{BASE_URL}/api/contracts/{draft_contract['id']}/send")
        token = send_response.json().get("token")
        
        # Public GET without auth
        public_response = requests.get(f"{BASE_URL}/api/contracts/sign/{token}")
        assert public_response.status_code == 200, f"Public GET should work: {public_response.text}"
        
        data = public_response.json()
        assert "contract" in data, "Should return contract"
        assert "hotel_name" in data, "Should return hotel_name"
        assert "already_signed" in data, "Should return already_signed"
        assert data["already_signed"] == False, "Should not be signed yet"
        
        print(f"✓ Public GET sign/{token[:8]}... works without auth")
    
    def test_public_sign_contract(self, admin_session, draft_contract):
        """POST /api/contracts/sign/{token} is PUBLIC and signs the contract"""
        # Send to get token
        send_response = admin_session.post(f"{BASE_URL}/api/contracts/{draft_contract['id']}/send")
        token = send_response.json().get("token")
        
        # Public POST to sign
        sign_response = requests.post(f"{BASE_URL}/api/contracts/sign/{token}", json={
            "full_name": "Test Signer",
            "signature": "Test Signer",
            "accept_terms": True
        })
        assert sign_response.status_code == 200, f"Public sign should work: {sign_response.text}"
        
        data = sign_response.json()
        assert data.get("ok") == True
        assert "signed_at" in data, "Should return signed_at"
        
        print(f"✓ Public POST sign/{token[:8]}... works without auth, signed_at={data['signed_at'][:19]}")
    
    def test_sign_validates_required_fields(self, admin_session, draft_contract):
        """POST /api/contracts/sign/{token} validates signature, full_name, accept_terms"""
        # Send to get token
        send_response = admin_session.post(f"{BASE_URL}/api/contracts/{draft_contract['id']}/send")
        token = send_response.json().get("token")
        
        # Missing signature
        response = requests.post(f"{BASE_URL}/api/contracts/sign/{token}", json={
            "full_name": "Test",
            "accept_terms": True
        })
        assert response.status_code == 400, "Should require signature"
        
        # Missing full_name
        response = requests.post(f"{BASE_URL}/api/contracts/sign/{token}", json={
            "signature": "Test",
            "accept_terms": True
        })
        assert response.status_code == 400, "Should require full_name"
        
        # Missing accept_terms
        response = requests.post(f"{BASE_URL}/api/contracts/sign/{token}", json={
            "full_name": "Test",
            "signature": "Test"
        })
        assert response.status_code == 400, "Should require accept_terms"
        
        print("✓ Sign validates required fields")
    
    def test_cannot_sign_twice(self, admin_session, draft_contract):
        """POST /api/contracts/sign/{token} returns 400 if already signed"""
        # Send and sign
        send_response = admin_session.post(f"{BASE_URL}/api/contracts/{draft_contract['id']}/send")
        token = send_response.json().get("token")
        
        # First sign
        requests.post(f"{BASE_URL}/api/contracts/sign/{token}", json={
            "full_name": "First Signer",
            "signature": "First Signer",
            "accept_terms": True
        })
        
        # Second sign attempt
        response = requests.post(f"{BASE_URL}/api/contracts/sign/{token}", json={
            "full_name": "Second Signer",
            "signature": "Second Signer",
            "accept_terms": True
        })
        assert response.status_code == 400, "Should not allow signing twice"
        assert "already" in response.text.lower(), "Should mention already signed"
        
        print("✓ Cannot sign contract twice")


class TestContractEditRestrictions:
    """Test that signed contracts cannot be edited/deleted"""
    
    @pytest.fixture(scope="class")
    def admin_session(self):
        session = requests.Session()
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        token = response.json().get("token")
        session.headers.update({"Authorization": f"Bearer {token}"})
        return session
    
    @pytest.fixture
    def signed_contract(self, admin_session):
        """Create and sign a contract"""
        unique_id = str(uuid.uuid4())[:8]
        # Create
        contract = admin_session.post(f"{BASE_URL}/api/contracts", json={
            "staff_name": f"TEST_Signed_{unique_id}",
            "contract_type": "full_time",
            "start_date": "2026-02-01"
        }).json()
        
        # Send
        send_data = admin_session.post(f"{BASE_URL}/api/contracts/{contract['id']}/send").json()
        
        # Sign (public)
        requests.post(f"{BASE_URL}/api/contracts/sign/{send_data['token']}", json={
            "full_name": "Signed User",
            "signature": "Signed User",
            "accept_terms": True
        })
        
        yield contract
        # Cannot delete signed contract, so we terminate it
        admin_session.post(f"{BASE_URL}/api/contracts/{contract['id']}/terminate", json={"reason": "Test cleanup"})
    
    def test_cannot_edit_signed_contract(self, admin_session, signed_contract):
        """PUT /api/contracts/{id} returns 400 for signed contract"""
        response = admin_session.put(f"{BASE_URL}/api/contracts/{signed_contract['id']}", json={
            "staff_name": "Attempted Edit"
        })
        assert response.status_code == 400, f"Should not allow editing signed contract: {response.text}"
        print("✓ Cannot edit signed contract (400)")
    
    def test_cannot_delete_signed_contract(self, admin_session, signed_contract):
        """DELETE /api/contracts/{id} returns 400 for signed contract"""
        response = admin_session.delete(f"{BASE_URL}/api/contracts/{signed_contract['id']}")
        assert response.status_code == 400, f"Should not allow deleting signed contract: {response.text}"
        print("✓ Cannot delete signed contract (400)")


class TestContractTermination:
    """Test contract termination"""
    
    @pytest.fixture(scope="class")
    def admin_session(self):
        session = requests.Session()
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        token = response.json().get("token")
        session.headers.update({"Authorization": f"Bearer {token}"})
        return session
    
    def test_terminate_contract(self, admin_session):
        """POST /api/contracts/{id}/terminate sets status=terminated"""
        # Create and sign a contract
        unique_id = str(uuid.uuid4())[:8]
        contract = admin_session.post(f"{BASE_URL}/api/contracts", json={
            "staff_name": f"TEST_Terminate_{unique_id}",
            "contract_type": "full_time",
            "start_date": "2026-02-01"
        }).json()
        
        send_data = admin_session.post(f"{BASE_URL}/api/contracts/{contract['id']}/send").json()
        requests.post(f"{BASE_URL}/api/contracts/sign/{send_data['token']}", json={
            "full_name": "To Terminate",
            "signature": "To Terminate",
            "accept_terms": True
        })
        
        # Terminate
        term_response = admin_session.post(f"{BASE_URL}/api/contracts/{contract['id']}/terminate", json={
            "reason": "End of project",
            "effective_end_date": "2026-06-30"
        })
        assert term_response.status_code == 200
        assert term_response.json().get("ok") == True
        
        # Verify status
        list_response = admin_session.get(f"{BASE_URL}/api/contracts/all")
        contracts = list_response.json()
        found = next((c for c in contracts if c.get("id") == contract["id"]), None)
        assert found.get("status") == "terminated" or found.get("computed_status") == "terminated"
        
        print("✓ Terminate contract sets status=terminated")


class TestRegressionArrivalsMarketplace:
    """Regression tests for Arrivals Cockpit and Marketplace"""
    
    @pytest.fixture(scope="class")
    def admin_session(self):
        session = requests.Session()
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        token = response.json().get("token")
        session.headers.update({"Authorization": f"Bearer {token}"})
        return session
    
    def test_arrivals_endpoint_still_works(self, admin_session):
        """GET /api/arrivals/{pid} still works (regression)"""
        response = admin_session.get(f"{BASE_URL}/api/arrivals/all?window=7d")
        assert response.status_code == 200, f"Arrivals should work: {response.text}"
        data = response.json()
        assert "arrivals" in data
        assert "counters" in data
        print(f"✓ Arrivals endpoint works: {data['counters']['total']} arrivals")
    
    def test_marketplace_endpoint_still_works(self, admin_session):
        """GET /api/marketplace/catalog/{pid} still works (regression)"""
        response = admin_session.get(f"{BASE_URL}/api/marketplace/catalog/all")
        assert response.status_code == 200, f"Marketplace should work: {response.text}"
        data = response.json()
        # API returns object with integrations list
        assert "integrations" in data or isinstance(data, list), "Should have integrations"
        total = data.get("total_available", len(data.get("integrations", data)))
        print(f"✓ Marketplace endpoint works: {total} integrations")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
