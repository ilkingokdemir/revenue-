"""
Test suite for 14 platform integrations in Hotel Review Management System
Tests: GET /api/integrations, GET /api/integrations/requirements, PUT /api/integrations/{platform}/configure
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://review-hub-108.preview.emergentagent.com')

# All 14 platforms that should be supported
EXPECTED_PLATFORMS = [
    "google", "booking.com", "tripadvisor", "airbnb", "expedia", "trip.com",
    "agoda", "hotels.com", "yelp", "facebook", "makemytrip", "hrs", "despegar", "hostelworld"
]

# New 8 platforms added in this iteration
NEW_PLATFORMS = ["agoda", "hotels.com", "yelp", "facebook", "makemytrip", "hrs", "despegar", "hostelworld"]

class TestIntegrationsEndpoint:
    """Test GET /api/integrations returns all 14 platforms"""
    
    def test_integrations_returns_14_platforms(self):
        """Verify all 14 platforms are returned"""
        response = requests.get(f"{BASE_URL}/api/integrations")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert len(data) == 14, f"Expected 14 platforms, got {len(data)}"
        
        platforms = [p['platform'] for p in data]
        for expected in EXPECTED_PLATFORMS:
            assert expected in platforms, f"Missing platform: {expected}"
        print(f"✓ All 14 platforms returned: {platforms}")
    
    def test_new_platforms_present(self):
        """Verify all 8 new platforms are present"""
        response = requests.get(f"{BASE_URL}/api/integrations")
        assert response.status_code == 200
        
        data = response.json()
        platforms = [p['platform'] for p in data]
        
        for new_platform in NEW_PLATFORMS:
            assert new_platform in platforms, f"New platform missing: {new_platform}"
        print(f"✓ All 8 new platforms present: {NEW_PLATFORMS}")
    
    def test_integration_structure(self):
        """Verify each integration has required fields"""
        response = requests.get(f"{BASE_URL}/api/integrations")
        assert response.status_code == 200
        
        data = response.json()
        required_fields = ['id', 'platform', 'status', 'credentials_configured', 'sync_enabled', 'total_reviews_synced']
        
        for integration in data:
            for field in required_fields:
                assert field in integration, f"Missing field '{field}' in {integration['platform']}"
        print(f"✓ All integrations have required fields")


class TestRequirementsEndpoint:
    """Test GET /api/integrations/requirements returns all platform requirements"""
    
    def test_requirements_returns_all_platforms(self):
        """Verify requirements for all 14 platforms"""
        response = requests.get(f"{BASE_URL}/api/integrations/requirements")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        # Should have 14 platforms + manual_import = 15
        assert len(data) >= 14, f"Expected at least 14 platforms, got {len(data)}"
        
        for platform in EXPECTED_PLATFORMS:
            assert platform in data, f"Missing requirements for: {platform}"
        print(f"✓ Requirements available for all 14 platforms")
    
    def test_new_platform_requirements(self):
        """Verify requirements for new 8 platforms"""
        response = requests.get(f"{BASE_URL}/api/integrations/requirements")
        assert response.status_code == 200
        
        data = response.json()
        
        for platform in NEW_PLATFORMS:
            assert platform in data, f"Missing requirements for new platform: {platform}"
            req = data[platform]
            assert 'name' in req, f"Missing 'name' in {platform} requirements"
            assert 'requirements' in req, f"Missing 'requirements' in {platform} requirements"
            assert 'setup_url' in req, f"Missing 'setup_url' in {platform} requirements"
            assert 'fields_needed' in req, f"Missing 'fields_needed' in {platform} requirements"
        print(f"✓ All 8 new platforms have complete requirements")
    
    def test_platform_names_correct(self):
        """Verify platform display names are correct"""
        response = requests.get(f"{BASE_URL}/api/integrations/requirements")
        assert response.status_code == 200
        
        data = response.json()
        expected_names = {
            "agoda": "Agoda",
            "hotels.com": "Hotels.com",
            "yelp": "Yelp",
            "facebook": "Facebook Reviews",
            "makemytrip": "MakeMyTrip",
            "hrs": "HRS",
            "despegar": "Despegar",
            "hostelworld": "Hostelworld"
        }
        
        for platform, expected_name in expected_names.items():
            assert data[platform]['name'] == expected_name, f"Wrong name for {platform}: expected '{expected_name}', got '{data[platform]['name']}'"
        print(f"✓ All platform names are correct")


class TestConfigureEndpoint:
    """Test PUT /api/integrations/{platform}/configure for new platforms"""
    
    def test_configure_agoda(self):
        """Test configuring Agoda platform"""
        response = requests.put(
            f"{BASE_URL}/api/integrations/agoda/configure",
            json={
                "platform": "agoda",
                "credentials": {"api_key": "test_agoda_key", "property_id": "AGD123"},
                "location_id": "AGD123",
                "property_name": "Test Agoda Hotel"
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data['status'] == 'configured'
        print(f"✓ Agoda configuration saved successfully")
    
    def test_configure_hotels_com(self):
        """Test configuring Hotels.com platform"""
        response = requests.put(
            f"{BASE_URL}/api/integrations/hotels.com/configure",
            json={
                "platform": "hotels.com",
                "credentials": {"api_key": "test_hotels_key", "secret_key": "test_secret", "property_id": "HTL123"},
                "location_id": "HTL123",
                "property_name": "Test Hotels.com Property"
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data['status'] == 'configured'
        print(f"✓ Hotels.com configuration saved successfully")
    
    def test_configure_yelp(self):
        """Test configuring Yelp platform"""
        response = requests.put(
            f"{BASE_URL}/api/integrations/yelp/configure",
            json={
                "platform": "yelp",
                "credentials": {"api_key": "test_yelp_key", "business_id": "test-hotel-city"},
                "location_id": "test-hotel-city",
                "property_name": "Test Yelp Business"
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data['status'] == 'configured'
        print(f"✓ Yelp configuration saved successfully")
    
    def test_configure_facebook(self):
        """Test configuring Facebook platform"""
        response = requests.put(
            f"{BASE_URL}/api/integrations/facebook/configure",
            json={
                "platform": "facebook",
                "credentials": {"access_token": "test_fb_token", "page_id": "123456789"},
                "location_id": "123456789",
                "property_name": "Test Facebook Page"
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data['status'] == 'configured'
        print(f"✓ Facebook configuration saved successfully")
    
    def test_configure_makemytrip(self):
        """Test configuring MakeMyTrip platform"""
        response = requests.put(
            f"{BASE_URL}/api/integrations/makemytrip/configure",
            json={
                "platform": "makemytrip",
                "credentials": {"api_key": "test_mmt_key", "property_id": "MMT123"},
                "location_id": "MMT123",
                "property_name": "Test MMT Hotel"
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data['status'] == 'configured'
        print(f"✓ MakeMyTrip configuration saved successfully")
    
    def test_configure_hrs(self):
        """Test configuring HRS platform"""
        response = requests.put(
            f"{BASE_URL}/api/integrations/hrs/configure",
            json={
                "platform": "hrs",
                "credentials": {"api_key": "test_hrs_key", "hotel_id": "HRS123"},
                "location_id": "HRS123",
                "property_name": "Test HRS Hotel"
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data['status'] == 'configured'
        print(f"✓ HRS configuration saved successfully")
    
    def test_configure_despegar(self):
        """Test configuring Despegar platform"""
        response = requests.put(
            f"{BASE_URL}/api/integrations/despegar/configure",
            json={
                "platform": "despegar",
                "credentials": {"api_key": "test_despegar_key", "property_id": "DSP123"},
                "location_id": "DSP123",
                "property_name": "Test Despegar Hotel"
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data['status'] == 'configured'
        print(f"✓ Despegar configuration saved successfully")
    
    def test_configure_hostelworld(self):
        """Test configuring Hostelworld platform"""
        response = requests.put(
            f"{BASE_URL}/api/integrations/hostelworld/configure",
            json={
                "platform": "hostelworld",
                "credentials": {"api_key": "test_hw_key", "property_id": "HW123"},
                "location_id": "HW123",
                "property_name": "Test Hostelworld Property"
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data['status'] == 'configured'
        print(f"✓ Hostelworld configuration saved successfully")


class TestRegressionExistingFeatures:
    """Regression tests for existing features"""
    
    def test_reviews_endpoint(self):
        """Test reviews endpoint still works"""
        response = requests.get(f"{BASE_URL}/api/reviews")
        assert response.status_code == 200, f"Reviews endpoint failed: {response.status_code}"
        print(f"✓ Reviews endpoint working")
    
    def test_reviews_stats(self):
        """Test reviews stats endpoint"""
        response = requests.get(f"{BASE_URL}/api/reviews/stats/summary")
        assert response.status_code == 200, f"Stats endpoint failed: {response.status_code}"
        data = response.json()
        assert 'total_reviews' in data
        assert 'average_rating' in data
        print(f"✓ Reviews stats endpoint working")
    
    def test_analytics_dashboard(self):
        """Test analytics dashboard endpoint"""
        response = requests.get(f"{BASE_URL}/api/analytics/dashboard")
        assert response.status_code == 200, f"Analytics endpoint failed: {response.status_code}"
        data = response.json()
        assert 'overview' in data
        print(f"✓ Analytics dashboard endpoint working")
    
    def test_templates_endpoint(self):
        """Test templates endpoint"""
        response = requests.get(f"{BASE_URL}/api/templates")
        assert response.status_code == 200, f"Templates endpoint failed: {response.status_code}"
        print(f"✓ Templates endpoint working")
    
    def test_original_6_platforms_still_work(self):
        """Test original 6 platforms are still present"""
        response = requests.get(f"{BASE_URL}/api/integrations")
        assert response.status_code == 200
        
        data = response.json()
        platforms = [p['platform'] for p in data]
        
        original_platforms = ["google", "booking.com", "tripadvisor", "airbnb", "expedia", "trip.com"]
        for platform in original_platforms:
            assert platform in platforms, f"Original platform missing: {platform}"
        print(f"✓ All 6 original platforms still present")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
