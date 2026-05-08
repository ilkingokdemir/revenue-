"""
Iteration 21 Tests: MyHotelBox Branch Selector Feature
Tests:
- 9 MyHotelBox branches seeded on startup
- Branch selector in sidebar with 'All Branches' default
- GET /api/properties returns 10 properties (My Hotel + 9 branches)
- GET /api/reviews without property_id returns all reviews
- GET /api/reviews?property_id=aldgate-flats returns only that branch's reviews
- Each seeded branch has external_id, external_name, external_system=myhotelbox
- POST /api/platforms/booking.com/incoming with property_id creates review under that branch
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"
TEST_API_KEY = "rhk_17354979397db960bcb68db21ed42b7acc103e7940715667"

# Expected branches from seed_myhotelbox_branches
EXPECTED_BRANCHES = [
    {"id": "aldgate-flats", "name": "ALDGATE FLATS", "external_system": "myhotelbox"},
    {"id": "camden-suites", "name": "CAMDEN SUITES", "external_system": "myhotelbox"},
    {"id": "city-gate", "name": "CITY GATE", "external_system": "myhotelbox"},
    {"id": "city-rooms", "name": "CITY ROOMS", "external_system": "myhotelbox"},
    {"id": "london-suites", "name": "LONDON SUITES", "external_system": "myhotelbox"},
    {"id": "ryam-suites", "name": "Ryam Suites", "external_system": "myhotelbox"},
    {"id": "whitechapel-hotel", "name": "THE WHITECHAPEL HOTEL", "external_system": "myhotelbox"},
    {"id": "vilenza-hotel", "name": "VILENZA HOTEL", "external_system": "myhotelbox"},
    {"id": "whitechapel-grand", "name": "Whitechapel Grand", "external_system": "myhotelbox"},
]


@pytest.fixture(scope="module")
def session():
    """Create a requests session"""
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def auth_token(session):
    """Login and get auth token"""
    response = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    assert response.status_code == 200, f"Login failed: {response.text}"
    data = response.json()
    assert "token" in data, "No token in login response"
    return data["token"]


@pytest.fixture(scope="module")
def auth_session(session, auth_token):
    """Session with auth header"""
    session.headers.update({"Authorization": f"Bearer {auth_token}"})
    return session


class TestAdminLogin:
    """Test admin login with correct credentials"""
    
    def test_admin_login_success(self, session):
        """Admin login with admin@hotelbox.com / HotelAdmin2026!"""
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert data["email"] == ADMIN_EMAIL
        assert data["role"] == "admin"
        assert "token" in data
        print(f"✓ Admin login successful: {data['name']} ({data['role']})")


class TestPropertiesEndpoint:
    """Test GET /api/properties returns 10 properties (My Hotel + 9 branches)"""
    
    def test_get_properties_returns_10(self, auth_session):
        """GET /api/properties returns 10 properties"""
        response = auth_session.get(f"{BASE_URL}/api/properties")
        assert response.status_code == 200, f"Failed: {response.text}"
        properties = response.json()
        
        # Should have at least 10 properties (default + 9 branches)
        assert len(properties) >= 10, f"Expected at least 10 properties, got {len(properties)}"
        print(f"✓ GET /api/properties returns {len(properties)} properties")
        
        # Check for default property
        default_prop = next((p for p in properties if p["id"] == "default"), None)
        assert default_prop is not None, "Default property 'My Hotel' not found"
        print(f"✓ Default property found: {default_prop['name']}")
        
        return properties
    
    def test_all_branches_have_external_fields(self, auth_session):
        """Each seeded branch has external_id, external_name, external_system=myhotelbox"""
        response = auth_session.get(f"{BASE_URL}/api/properties")
        assert response.status_code == 200
        properties = response.json()
        
        for expected in EXPECTED_BRANCHES:
            prop = next((p for p in properties if p["id"] == expected["id"]), None)
            assert prop is not None, f"Branch {expected['id']} not found"
            
            # Check external fields
            assert prop.get("external_id"), f"Branch {expected['id']} missing external_id"
            assert prop.get("external_name"), f"Branch {expected['id']} missing external_name"
            assert prop.get("external_system") == "myhotelbox", f"Branch {expected['id']} external_system should be 'myhotelbox'"
            
            print(f"✓ Branch {expected['id']}: external_id={prop['external_id']}, external_system={prop['external_system']}")
    
    def test_branch_names_match(self, auth_session):
        """Verify all 9 branch names are correct"""
        response = auth_session.get(f"{BASE_URL}/api/properties")
        assert response.status_code == 200
        properties = response.json()
        
        for expected in EXPECTED_BRANCHES:
            prop = next((p for p in properties if p["id"] == expected["id"]), None)
            assert prop is not None, f"Branch {expected['id']} not found"
            assert prop["name"] == expected["name"], f"Branch name mismatch: expected {expected['name']}, got {prop['name']}"
        
        print(f"✓ All 9 branch names verified")


class TestReviewsFiltering:
    """Test reviews filtering by property_id"""
    
    def test_get_reviews_without_property_id(self, auth_session):
        """GET /api/reviews without property_id returns all reviews"""
        response = auth_session.get(f"{BASE_URL}/api/reviews")
        assert response.status_code == 200, f"Failed: {response.text}"
        reviews = response.json()
        
        # Should return reviews (may be empty if no reviews exist)
        assert isinstance(reviews, list), "Expected list of reviews"
        print(f"✓ GET /api/reviews (no filter) returns {len(reviews)} reviews")
        
        return reviews
    
    def test_get_reviews_with_property_id_filter(self, auth_session):
        """GET /api/reviews?property_id=aldgate-flats returns only that branch's reviews"""
        response = auth_session.get(f"{BASE_URL}/api/reviews?property_id=aldgate-flats")
        assert response.status_code == 200, f"Failed: {response.text}"
        reviews = response.json()
        
        # All returned reviews should have property_id=aldgate-flats
        for review in reviews:
            assert review.get("property_id") == "aldgate-flats", f"Review {review['id']} has wrong property_id: {review.get('property_id')}"
        
        print(f"✓ GET /api/reviews?property_id=aldgate-flats returns {len(reviews)} reviews (all filtered correctly)")
    
    def test_get_reviews_with_default_property_id(self, auth_session):
        """GET /api/reviews?property_id=default returns only default property reviews"""
        response = auth_session.get(f"{BASE_URL}/api/reviews?property_id=default")
        assert response.status_code == 200, f"Failed: {response.text}"
        reviews = response.json()
        
        for review in reviews:
            assert review.get("property_id") == "default", f"Review {review['id']} has wrong property_id"
        
        print(f"✓ GET /api/reviews?property_id=default returns {len(reviews)} reviews")


class TestInboundWebhookWithPropertyId:
    """Test POST /api/platforms/booking.com/incoming with property_id"""
    
    def test_create_review_with_property_id(self, auth_session):
        """POST /api/platforms/booking.com/incoming with property_id=aldgate-flats creates review under that branch"""
        unique_id = f"TEST_branch_{uuid.uuid4().hex[:8]}"
        
        payload = {
            "guest_name": "Branch Test Guest",
            "rating": 4,
            "review_text": "Testing branch assignment for Aldgate Flats property",
            "external_review_id": unique_id,
            "property_id": "aldgate-flats",
            "stay_date": "2026-01-10",
            "room_type": "Studio Apartment"
        }
        
        response = auth_session.post(
            f"{BASE_URL}/api/platforms/booking.com/incoming",
            json=payload,
            headers={"X-Platform-Secret": TEST_API_KEY}
        )
        
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert data.get("status") == "created", f"Expected status 'created', got {data.get('status')}"
        
        print(f"✓ Created review {data.get('review_id')} via inbound webhook")
        
        # Verify the review is in the correct property by fetching it
        review_id = data.get("review_id")
        verify_response = auth_session.get(f"{BASE_URL}/api/reviews/{review_id}")
        assert verify_response.status_code == 200
        review = verify_response.json()
        assert review["property_id"] == "aldgate-flats", f"Review property_id mismatch: expected 'aldgate-flats', got '{review.get('property_id')}'"
        
        print(f"✓ Verified review {review_id} has property_id=aldgate-flats")
    
    def test_create_review_with_different_branch(self, auth_session):
        """POST /api/platforms/booking.com/incoming with property_id=camden-suites"""
        unique_id = f"TEST_camden_{uuid.uuid4().hex[:8]}"
        
        payload = {
            "guest_name": "Camden Test Guest",
            "rating": 5,
            "review_text": "Testing Camden Suites branch assignment",
            "external_review_id": unique_id,
            "property_id": "camden-suites",
            "stay_date": "2026-01-11"
        }
        
        response = auth_session.post(
            f"{BASE_URL}/api/platforms/booking.com/incoming",
            json=payload,
            headers={"X-Platform-Secret": TEST_API_KEY}
        )
        
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data.get("status") == "created"
        
        # Verify the review is in the correct property
        review_id = data.get("review_id")
        verify_response = auth_session.get(f"{BASE_URL}/api/reviews/{review_id}")
        assert verify_response.status_code == 200
        review = verify_response.json()
        assert review["property_id"] == "camden-suites", f"Review property_id mismatch"
        
        print(f"✓ Created review {review_id} under property camden-suites")


class TestReviewStats:
    """Test stats endpoint with property filtering"""
    
    def test_stats_without_property_filter(self, auth_session):
        """GET /api/reviews/stats/summary returns stats for all reviews"""
        response = auth_session.get(f"{BASE_URL}/api/reviews/stats/summary")
        assert response.status_code == 200, f"Failed: {response.text}"
        stats = response.json()
        
        assert "total_reviews" in stats, "Missing total_reviews in stats"
        assert "average_rating" in stats, "Missing average_rating in stats"
        
        print(f"✓ Stats (all): total={stats['total_reviews']}, avg_rating={stats['average_rating']}")
    
    def test_stats_with_property_filter(self, auth_session):
        """GET /api/reviews/stats/summary?property_id=aldgate-flats returns filtered stats"""
        response = auth_session.get(f"{BASE_URL}/api/reviews/stats/summary?property_id=aldgate-flats")
        assert response.status_code == 200, f"Failed: {response.text}"
        stats = response.json()
        
        assert "total_reviews" in stats
        print(f"✓ Stats (aldgate-flats): total={stats['total_reviews']}, avg_rating={stats.get('average_rating', 'N/A')}")


class TestWidgetWithPropertyId:
    """Test widget API with property_id filter"""
    
    def test_widget_reviews_with_property_id(self):
        """GET /api/widget/reviews?api_key=xxx&property_id=aldgate-flats"""
        response = requests.get(
            f"{BASE_URL}/api/widget/reviews",
            params={"api_key": TEST_API_KEY, "property_id": "aldgate-flats"}
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        reviews = response.json()
        
        for review in reviews:
            assert review.get("property_id") == "aldgate-flats"
        
        print(f"✓ Widget API returns {len(reviews)} reviews for aldgate-flats")
    
    def test_widget_stats_with_property_id(self):
        """GET /api/widget/stats?api_key=xxx&property_id=aldgate-flats"""
        response = requests.get(
            f"{BASE_URL}/api/widget/stats",
            params={"api_key": TEST_API_KEY, "property_id": "aldgate-flats"}
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        stats = response.json()
        
        assert "total_reviews" in stats
        print(f"✓ Widget stats for aldgate-flats: total={stats['total_reviews']}")


class TestPropertyMappingPanel:
    """Test property mapping shows all 10 properties with Mapped badges"""
    
    def test_properties_have_mapping_fields(self, auth_session):
        """All seeded branches should have external_id (mapped)"""
        response = auth_session.get(f"{BASE_URL}/api/properties")
        assert response.status_code == 200
        properties = response.json()
        
        mapped_count = sum(1 for p in properties if p.get("external_id"))
        print(f"✓ {mapped_count} properties have external_id (mapped)")
        
        # At least 9 branches should be mapped
        assert mapped_count >= 9, f"Expected at least 9 mapped properties, got {mapped_count}"


class TestSyncLog:
    """Test sync log panel still works"""
    
    def test_get_sync_logs(self, auth_session):
        """GET /api/sync-logs returns sync activity"""
        response = auth_session.get(f"{BASE_URL}/api/sync-logs")
        assert response.status_code == 200, f"Failed: {response.text}"
        logs = response.json()
        
        assert isinstance(logs, list), "Expected list of sync logs"
        print(f"✓ GET /api/sync-logs returns {len(logs)} entries")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
