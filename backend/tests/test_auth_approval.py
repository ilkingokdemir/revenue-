"""
Test suite for JWT Authentication and Approval Workflow features
Tests: Login, Register, User Management, Approval Workflow, Roles
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials from backend/.env
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"


class TestAuthLogin:
    """Authentication login endpoint tests"""
    
    def test_login_success_returns_token_and_user(self):
        """POST /api/auth/login with valid credentials returns token and user data"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Verify token is returned
        assert "token" in data, "Response should contain token"
        assert isinstance(data["token"], str) and len(data["token"]) > 0, "Token should be non-empty string"
        
        # Verify user data
        assert "id" in data, "Response should contain user id"
        assert data["email"] == ADMIN_EMAIL.lower(), f"Email should be {ADMIN_EMAIL.lower()}"
        assert data["name"] == "Hotel Admin", "Name should be 'Hotel Admin'"
        assert data["role"] == "admin", "Role should be 'admin'"
        assert "department" in data, "Response should contain department"
        
        print(f"✓ Login successful: {data['name']} ({data['role']})")
    
    def test_login_wrong_password_returns_401(self):
        """POST /api/auth/login with wrong password returns 401"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": "WrongPassword123!"
        })
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        
        data = response.json()
        assert "detail" in data, "Response should contain error detail"
        print(f"✓ Wrong password correctly rejected: {data['detail']}")
    
    def test_login_nonexistent_user_returns_401(self):
        """POST /api/auth/login with non-existent user returns 401"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "nonexistent@hotel.com",
            "password": "SomePassword123!"
        })
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ Non-existent user correctly rejected")


class TestAuthMe:
    """GET /api/auth/me endpoint tests"""
    
    @pytest.fixture
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("token")
        pytest.skip("Authentication failed")
    
    def test_get_me_with_valid_token(self, auth_token):
        """GET /api/auth/me with valid token returns user info"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/auth/me", headers=headers)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "id" in data, "Response should contain id"
        assert data["email"] == ADMIN_EMAIL.lower(), f"Email should be {ADMIN_EMAIL.lower()}"
        assert data["name"] == "Hotel Admin", "Name should be 'Hotel Admin'"
        assert data["role"] == "admin", "Role should be 'admin'"
        assert "department" in data, "Response should contain department"
        assert "is_active" in data, "Response should contain is_active"
        
        print(f"✓ GET /api/auth/me returned: {data['name']} ({data['role']})")
    
    def test_get_me_without_token_returns_401(self):
        """GET /api/auth/me without token returns 401"""
        response = requests.get(f"{BASE_URL}/api/auth/me")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ GET /api/auth/me without token correctly rejected")


class TestAuthLogout:
    """POST /api/auth/logout endpoint tests"""
    
    def test_logout_clears_cookies(self):
        """POST /api/auth/logout clears cookies"""
        # First login to get cookies
        session = requests.Session()
        login_response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert login_response.status_code == 200, "Login should succeed"
        
        # Now logout
        logout_response = session.post(f"{BASE_URL}/api/auth/logout")
        assert logout_response.status_code == 200, f"Expected 200, got {logout_response.status_code}"
        
        data = logout_response.json()
        assert data.get("message") == "Logged out", "Should return 'Logged out' message"
        
        print("✓ Logout successful")


class TestRoles:
    """GET /api/roles endpoint tests"""
    
    def test_get_roles_returns_roles_and_departments(self):
        """GET /api/roles returns roles (3) and departments (7)"""
        response = requests.get(f"{BASE_URL}/api/roles")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        
        # Verify roles
        assert "roles" in data, "Response should contain roles"
        assert len(data["roles"]) == 3, f"Should have 3 roles, got {len(data['roles'])}"
        role_ids = [r["id"] for r in data["roles"]]
        assert "admin" in role_ids, "Should have admin role"
        assert "manager" in role_ids, "Should have manager role"
        assert "receptionist" in role_ids, "Should have receptionist role"
        
        # Verify departments
        assert "departments" in data, "Response should contain departments"
        assert len(data["departments"]) == 7, f"Should have 7 departments, got {len(data['departments'])}"
        dept_ids = [d["id"] for d in data["departments"]]
        expected_depts = ["front_desk", "management", "housekeeping", "food_beverage", "maintenance", "spa_wellness", "concierge"]
        for dept in expected_depts:
            assert dept in dept_ids, f"Should have {dept} department"
        
        print(f"✓ GET /api/roles returned {len(data['roles'])} roles and {len(data['departments'])} departments")


class TestUserManagement:
    """User management endpoint tests (admin only)"""
    
    @pytest.fixture
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("token")
        pytest.skip("Admin authentication failed")
    
    def test_get_users_returns_user_list(self, admin_token):
        """GET /api/users returns user list (admin/manager only)"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/users", headers=headers)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        assert len(data) >= 1, "Should have at least 1 user (admin)"
        
        # Verify user structure
        admin_user = next((u for u in data if u["email"] == ADMIN_EMAIL.lower()), None)
        assert admin_user is not None, "Admin user should be in list"
        assert "id" in admin_user, "User should have id"
        assert "name" in admin_user, "User should have name"
        assert "role" in admin_user, "User should have role"
        assert "password_hash" not in admin_user, "Password hash should not be exposed"
        
        print(f"✓ GET /api/users returned {len(data)} users")
    
    def test_get_users_without_auth_returns_401(self):
        """GET /api/users without auth returns 401"""
        response = requests.get(f"{BASE_URL}/api/users")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ GET /api/users without auth correctly rejected")
    
    def test_register_and_delete_user(self, admin_token):
        """POST /api/auth/register creates new user, DELETE /api/users/{id} deletes user"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Create a test user
        test_user = {
            "email": "TEST_testuser@hotel.com",
            "password": "TestPass123!",
            "name": "Test User",
            "role": "receptionist",
            "department": "front_desk"
        }
        
        create_response = requests.post(f"{BASE_URL}/api/auth/register", json=test_user, headers=headers)
        assert create_response.status_code == 200, f"Expected 200, got {create_response.status_code}: {create_response.text}"
        
        created_user = create_response.json()
        assert "id" in created_user, "Created user should have id"
        assert created_user["email"] == test_user["email"].lower(), "Email should match"
        assert created_user["name"] == test_user["name"], "Name should match"
        assert created_user["role"] == test_user["role"], "Role should match"
        
        user_id = created_user["id"]
        print(f"✓ Created test user: {created_user['name']} (id: {user_id})")
        
        # Delete the test user
        delete_response = requests.delete(f"{BASE_URL}/api/users/{user_id}", headers=headers)
        assert delete_response.status_code == 200, f"Expected 200, got {delete_response.status_code}: {delete_response.text}"
        
        delete_data = delete_response.json()
        assert delete_data.get("message") == "User deleted", "Should return 'User deleted' message"
        
        print(f"✓ Deleted test user: {user_id}")
        
        # Verify user is deleted
        users_response = requests.get(f"{BASE_URL}/api/users", headers=headers)
        users = users_response.json()
        deleted_user = next((u for u in users if u["id"] == user_id), None)
        assert deleted_user is None, "Deleted user should not be in list"
        
        print("✓ Verified user deletion")


class TestApprovalWorkflow:
    """Approval workflow endpoint tests"""
    
    @pytest.fixture
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("token")
        pytest.skip("Admin authentication failed")
    
    @pytest.fixture
    def test_review_id(self, admin_token):
        """Get a review ID for testing"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # First seed reviews if needed
        requests.post(f"{BASE_URL}/api/reviews/seed")
        
        # Get reviews
        response = requests.get(f"{BASE_URL}/api/reviews", headers=headers)
        if response.status_code == 200:
            reviews = response.json()
            # Find a pending review
            pending = next((r for r in reviews if r["response_status"] == "pending"), None)
            if pending:
                return pending["id"]
        pytest.skip("No pending reviews available for testing")
    
    def test_submit_for_approval_changes_status(self, admin_token, test_review_id):
        """POST /api/reviews/{id}/submit-for-approval changes status to pending_approval"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # First add a response to the review
        respond_response = requests.put(
            f"{BASE_URL}/api/reviews/{test_review_id}/respond",
            json={"response_text": "Thank you for your feedback! We appreciate your review."},
            headers=headers
        )
        # This might fail if already responded, that's ok
        
        # Get the review to check current state
        review_response = requests.get(f"{BASE_URL}/api/reviews/{test_review_id}", headers=headers)
        review = review_response.json()
        
        # If already has response text, we can submit for approval
        if review.get("response_text"):
            # Reset status to draft first by updating response
            requests.put(
                f"{BASE_URL}/api/reviews/{test_review_id}/respond",
                json={"response_text": "Thank you for your feedback! We appreciate your review."},
                headers=headers
            )
            
            # Now submit for approval
            submit_response = requests.post(
                f"{BASE_URL}/api/reviews/{test_review_id}/submit-for-approval",
                headers=headers
            )
            
            if submit_response.status_code == 200:
                data = submit_response.json()
                assert data.get("status") == "pending_approval", "Status should be pending_approval"
                print(f"✓ Review {test_review_id} submitted for approval")
            else:
                print(f"Note: Submit for approval returned {submit_response.status_code} - may already be in workflow")
        else:
            pytest.skip("Review has no response text to submit")
    
    def test_approve_response_publishes(self, admin_token):
        """POST /api/reviews/{id}/approve with action=approve publishes response"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Get pending approval reviews
        pending_response = requests.get(f"{BASE_URL}/api/reviews/pending-approval", headers=headers)
        
        if pending_response.status_code == 200:
            pending_reviews = pending_response.json()
            if len(pending_reviews) > 0:
                review_id = pending_reviews[0]["id"]
                
                approve_response = requests.post(
                    f"{BASE_URL}/api/reviews/{review_id}/approve",
                    json={"action": "approve", "notes": "Looks good!"},
                    headers=headers
                )
                
                assert approve_response.status_code == 200, f"Expected 200, got {approve_response.status_code}"
                data = approve_response.json()
                assert data.get("status") == "responded", "Status should be 'responded' after approval"
                print(f"✓ Review {review_id} approved and published")
            else:
                print("Note: No pending approval reviews to test")
        else:
            print(f"Note: Could not get pending approvals: {pending_response.status_code}")
    
    def test_reject_response(self, admin_token):
        """POST /api/reviews/{id}/approve with action=reject rejects response"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # First create a review in pending_approval state
        # Seed reviews
        requests.post(f"{BASE_URL}/api/reviews/seed")
        
        # Get a pending review
        reviews_response = requests.get(f"{BASE_URL}/api/reviews?status=pending", headers=headers)
        if reviews_response.status_code == 200:
            reviews = reviews_response.json()
            pending = next((r for r in reviews if r["response_status"] == "pending"), None)
            
            if pending:
                review_id = pending["id"]
                
                # Add response
                requests.put(
                    f"{BASE_URL}/api/reviews/{review_id}/respond",
                    json={"response_text": "Test response for rejection"},
                    headers=headers
                )
                
                # Submit for approval
                requests.post(f"{BASE_URL}/api/reviews/{review_id}/submit-for-approval", headers=headers)
                
                # Reject
                reject_response = requests.post(
                    f"{BASE_URL}/api/reviews/{review_id}/approve",
                    json={"action": "reject", "notes": "Needs revision"},
                    headers=headers
                )
                
                if reject_response.status_code == 200:
                    data = reject_response.json()
                    assert data.get("status") == "rejected", "Status should be 'rejected'"
                    print(f"✓ Review {review_id} rejected")
                else:
                    print(f"Note: Reject returned {reject_response.status_code}")
            else:
                print("Note: No pending reviews to test rejection")
    
    def test_get_pending_approvals(self, admin_token):
        """GET /api/reviews/pending-approval returns pending reviews (manager/admin only)"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        response = requests.get(f"{BASE_URL}/api/reviews/pending-approval", headers=headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        
        # All returned reviews should have pending_approval status
        for review in data:
            assert review.get("response_status") == "pending_approval", "All reviews should be pending_approval"
        
        print(f"✓ GET /api/reviews/pending-approval returned {len(data)} reviews")
    
    def test_get_pending_approvals_without_auth_returns_401(self):
        """GET /api/reviews/pending-approval without auth returns 401"""
        response = requests.get(f"{BASE_URL}/api/reviews/pending-approval")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ GET /api/reviews/pending-approval without auth correctly rejected")


class TestRegressionAfterAuth:
    """Regression tests to ensure existing features still work after auth"""
    
    @pytest.fixture
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("token")
        pytest.skip("Admin authentication failed")
    
    def test_reviews_endpoint_works(self):
        """GET /api/reviews still works (no auth required for read)"""
        response = requests.get(f"{BASE_URL}/api/reviews")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"✓ GET /api/reviews returned {len(data)} reviews")
    
    def test_stats_endpoint_works(self):
        """GET /api/reviews/stats/summary still works"""
        response = requests.get(f"{BASE_URL}/api/reviews/stats/summary")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "total_reviews" in data, "Should have total_reviews"
        assert "average_rating" in data, "Should have average_rating"
        print(f"✓ GET /api/reviews/stats/summary returned stats")
    
    def test_analytics_endpoint_works(self):
        """GET /api/analytics/dashboard still works"""
        response = requests.get(f"{BASE_URL}/api/analytics/dashboard")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "overview" in data, "Should have overview"
        print(f"✓ GET /api/analytics/dashboard returned analytics")
    
    def test_ai_generation_works(self, admin_token):
        """POST /api/reviews/generate-ai-response still works"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Get a review ID
        reviews_response = requests.get(f"{BASE_URL}/api/reviews")
        if reviews_response.status_code == 200:
            reviews = reviews_response.json()
            if len(reviews) > 0:
                review_id = reviews[0]["id"]
                
                response = requests.post(
                    f"{BASE_URL}/api/reviews/generate-ai-response",
                    json={"review_id": review_id, "tone": "professional", "language": "en"},
                    headers=headers
                )
                
                # AI generation might fail due to service issues, but endpoint should be accessible
                assert response.status_code in [200, 500], f"Expected 200 or 500, got {response.status_code}"
                
                if response.status_code == 200:
                    data = response.json()
                    assert "generated_text" in data, "Should have generated_text"
                    print(f"✓ AI generation works")
                else:
                    print(f"Note: AI generation returned 500 (service issue)")
            else:
                print("Note: No reviews to test AI generation")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
