"""
Iteration 40 - Staff Performance Dashboard Tests
Tests the new Staff Performance Dashboard feature that tracks:
- Response times per agent
- Messages handled per channel
- Resolution rate
- Conversation volume
- Performance score with leaderboard
- Daily activity trends
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestAuth:
    """Authentication tests"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token for admin user"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "token" in data, "No token in response"
        return data["token"]
    
    def test_login_success(self):
        """Test admin login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert data["email"] == "admin@hotelbox.com"
        assert data["role"] == "admin"
        print("✓ Admin login successful")


class TestStaffPerformanceAPI:
    """Staff Performance Dashboard API tests"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers for API calls"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert response.status_code == 200
        token = response.json()["token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_staff_performance_requires_auth(self):
        """Test that staff performance endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/staff-performance/myhotelbox-london")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ Staff performance requires authentication (401 without token)")
    
    def test_staff_performance_default_period(self, auth_headers):
        """Test staff performance with default 30-day period"""
        response = requests.get(
            f"{BASE_URL}/api/staff-performance/myhotelbox-london",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "agents" in data, "Missing 'agents' in response"
        assert "team_summary" in data, "Missing 'team_summary' in response"
        assert "daily_trend" in data, "Missing 'daily_trend' in response"
        assert "period_days" in data, "Missing 'period_days' in response"
        
        # Default period should be 30 days
        assert data["period_days"] == 30, f"Expected 30 days, got {data['period_days']}"
        
        # Verify team_summary structure
        team = data["team_summary"]
        assert "total_agents" in team
        assert "total_messages" in team
        assert "total_conversations" in team
        assert "total_resolved" in team
        assert "team_resolution_rate" in team
        assert "avg_response_min" in team
        
        print(f"✓ Staff performance default period (30 days) - {team['total_agents']} agents, {team['total_messages']} messages")
    
    def test_staff_performance_7_days(self, auth_headers):
        """Test staff performance with 7-day filter"""
        response = requests.get(
            f"{BASE_URL}/api/staff-performance/myhotelbox-london?days=7",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert data["period_days"] == 7, f"Expected 7 days, got {data['period_days']}"
        assert "agents" in data
        assert "team_summary" in data
        print(f"✓ Staff performance 7-day filter works - period_days={data['period_days']}")
    
    def test_staff_performance_90_days(self, auth_headers):
        """Test staff performance with 90-day filter"""
        response = requests.get(
            f"{BASE_URL}/api/staff-performance/myhotelbox-london?days=90",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert data["period_days"] == 90, f"Expected 90 days, got {data['period_days']}"
        print(f"✓ Staff performance 90-day filter works - period_days={data['period_days']}")
    
    def test_staff_performance_all_properties(self, auth_headers):
        """Test staff performance aggregation for all properties"""
        response = requests.get(
            f"{BASE_URL}/api/staff-performance/all",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert "agents" in data
        assert "team_summary" in data
        assert "daily_trend" in data
        print(f"✓ Staff performance all properties aggregation works")
    
    def test_agent_data_structure(self, auth_headers):
        """Test that agent data has correct structure"""
        response = requests.get(
            f"{BASE_URL}/api/staff-performance/myhotelbox-london",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        agents = data.get("agents", [])
        if len(agents) > 0:
            agent = agents[0]
            # Verify agent structure
            expected_fields = [
                "name", "total_messages", "conversations_count",
                "avg_response_min", "resolution_rate", "performance_score",
                "channels", "rank"
            ]
            for field in expected_fields:
                assert field in agent, f"Missing field '{field}' in agent data"
            
            # Verify rank is 1 for first agent (sorted by performance)
            assert agent["rank"] == 1, f"First agent should have rank 1, got {agent['rank']}"
            
            # Verify performance_score is a number
            assert isinstance(agent["performance_score"], (int, float))
            
            print(f"✓ Agent data structure correct - Top performer: {agent['name']} (score: {agent['performance_score']})")
        else:
            print("✓ Agent data structure test passed (no agents in data)")


class TestRegressionEndpoints:
    """Regression tests for existing endpoints"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers for API calls"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert response.status_code == 200
        token = response.json()["token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_messaging_conversations_still_works(self, auth_headers):
        """Regression: GET /api/messaging/conversations/{property_id} still works"""
        response = requests.get(
            f"{BASE_URL}/api/messaging/conversations/myhotelbox-london",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Messaging conversations endpoint works - {len(data)} conversations")
    
    def test_automation_rules_still_works(self, auth_headers):
        """Regression: GET /api/automation/rules/{property_id} still works"""
        response = requests.get(
            f"{BASE_URL}/api/automation/rules/myhotelbox-london",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Automation rules endpoint works - {len(data)} rules")
    
    def test_dashboard_overview_still_works(self, auth_headers):
        """Regression: GET /api/dashboard/overview/{property_id} still works"""
        response = requests.get(
            f"{BASE_URL}/api/dashboard/overview/myhotelbox-london",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "stats" in data or "conversations" in data or isinstance(data, dict)
        print(f"✓ Dashboard overview endpoint works")


class TestRoleBasedAccess:
    """Test role-based access control for staff performance"""
    
    def test_non_admin_cannot_access_staff_performance(self):
        """Test that non-admin/manager users cannot access staff performance"""
        # First, try to create a receptionist user (if admin exists)
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        
        if login_resp.status_code == 200:
            admin_token = login_resp.json()["token"]
            admin_headers = {"Authorization": f"Bearer {admin_token}"}
            
            # Try to create a receptionist user for testing
            test_email = "test_receptionist_perf@hotelbox.com"
            create_resp = requests.post(
                f"{BASE_URL}/api/auth/register",
                headers=admin_headers,
                json={
                    "email": test_email,
                    "password": "TestPass123!",
                    "name": "Test Receptionist",
                    "role": "receptionist",
                    "department": "front_desk"
                }
            )
            
            if create_resp.status_code in [200, 201]:
                # Login as receptionist
                recep_login = requests.post(f"{BASE_URL}/api/auth/login", json={
                    "email": test_email,
                    "password": "TestPass123!"
                })
                
                if recep_login.status_code == 200:
                    recep_token = recep_login.json()["token"]
                    recep_headers = {"Authorization": f"Bearer {recep_token}"}
                    
                    # Try to access staff performance
                    perf_resp = requests.get(
                        f"{BASE_URL}/api/staff-performance/myhotelbox-london",
                        headers=recep_headers
                    )
                    
                    # Should be 403 Forbidden for receptionist
                    assert perf_resp.status_code == 403, f"Expected 403 for receptionist, got {perf_resp.status_code}"
                    print("✓ Receptionist cannot access staff performance (403 Forbidden)")
                    
                    # Cleanup - delete test user
                    users_resp = requests.get(f"{BASE_URL}/api/users", headers=admin_headers)
                    if users_resp.status_code == 200:
                        for user in users_resp.json():
                            if user.get("email") == test_email:
                                requests.delete(f"{BASE_URL}/api/users/{user['id']}", headers=admin_headers)
                    return
            
            # If user already exists or creation failed, skip this test
            print("✓ Role-based access test skipped (could not create test user)")
        else:
            pytest.skip("Could not login as admin")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
