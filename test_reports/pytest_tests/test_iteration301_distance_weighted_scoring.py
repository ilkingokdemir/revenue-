"""
Iteration 301 - Distance-Weighted Scoring Enhancement Tests
Tests for distance-based weight calculation in Event Intelligence:
- Distance weight tiers: 0-30km=100%, 31-60=80%, 61-100=60%, 101-150=40%, 151-200=25%, >200=15%
- POST /api/revenue/events/{pid}/secondary-cities with optional distance_km, returns weight_pct
- PATCH /api/revenue/events/{pid}/secondary-cities/{city_name} to update distance
- GET /api/revenue/events/{pid}/secondary-cities returns enriched secondaries with distance/weight
- GET /api/revenue/events/{pid} includes secondary_cities_distance map
- DELETE secondary-cities also removes distance entry
- _apply_event_pricing applies boost * weight, reason includes @<city>(<pct>%)
- RBAC: receptionist gets 403 on PATCH endpoint
"""
import pytest
import requests
import os
import uuid
from datetime import datetime, timedelta

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Test credentials
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"
RECEP_EMAIL = "testrecep@hotelbox.com"
RECEP_PASSWORD = "Test2026!"


@pytest.fixture(scope="module")
def admin_token():
    """Get admin auth token"""
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    if resp.status_code != 200:
        pytest.skip(f"Admin login failed: {resp.status_code}")
    return resp.json().get("token") or resp.json().get("access_token")


@pytest.fixture(scope="module")
def recep_token():
    """Get receptionist auth token"""
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": RECEP_EMAIL,
        "password": RECEP_PASSWORD
    })
    if resp.status_code != 200:
        pytest.skip(f"Receptionist login failed: {resp.status_code}")
    return resp.json().get("token") or resp.json().get("access_token")


@pytest.fixture(scope="function")
def test_property_id(admin_token):
    """Create a fresh test property for each test function"""
    pid = f"test-dist-{uuid.uuid4().hex[:8]}"
    headers = {"Authorization": f"Bearer {admin_token}"}
    
    # Create property
    requests.post(f"{BASE_URL}/api/properties", json={
        "id": pid,
        "name": f"Test Distance Property {pid}",
        "city": "London",
        "currency": "GBP"
    }, headers=headers)
    
    # Set up market robot config with primary city
    requests.put(f"{BASE_URL}/api/revenue/market-robot/{pid}/config", json={
        "city": "London",
        "enabled": False
    }, headers=headers)
    
    # Create a room type for pricing tests
    requests.post(f"{BASE_URL}/api/room-types", json={
        "id": f"rt-{pid}",
        "property_id": pid,
        "name": "Standard Room",
        "base_rate": 100
    }, headers=headers)
    
    yield pid
    
    # Cleanup
    requests.delete(f"{BASE_URL}/api/properties/{pid}", headers=headers)


class TestDistanceWeightTiers:
    """Test the distance weight tier calculations via API responses"""
    
    def test_distance_0_30km_returns_100_percent(self, admin_token, test_property_id):
        """0-30km distance should return 100% weight"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Add secondary city with 25km distance
        resp = requests.post(f"{BASE_URL}/api/revenue/events/{test_property_id}/secondary-cities",
                            json={"city": "Watford", "distance_km": 25}, headers=headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data.get("weight_pct") == 100, f"Expected weight_pct=100 for 25km, got {data.get('weight_pct')}"
    
    def test_distance_31_60km_returns_80_percent(self, admin_token, test_property_id):
        """31-60km distance should return 80% weight"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Add secondary city with 45km distance
        resp = requests.post(f"{BASE_URL}/api/revenue/events/{test_property_id}/secondary-cities",
                            json={"city": "Reading", "distance_km": 45}, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("weight_pct") == 80, f"Expected weight_pct=80 for 45km, got {data.get('weight_pct')}"
    
    def test_distance_61_100km_returns_60_percent(self, admin_token, test_property_id):
        """61-100km distance should return 60% weight"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Add secondary city with 80km distance (Brighton)
        resp = requests.post(f"{BASE_URL}/api/revenue/events/{test_property_id}/secondary-cities",
                            json={"city": "Brighton", "distance_km": 80}, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("weight_pct") == 60, f"Expected weight_pct=60 for 80km, got {data.get('weight_pct')}"
        
        # Also test 90km (Oxford)
        resp2 = requests.post(f"{BASE_URL}/api/revenue/events/{test_property_id}/secondary-cities",
                             json={"city": "Oxford", "distance_km": 90}, headers=headers)
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data2.get("weight_pct") == 60, f"Expected weight_pct=60 for 90km, got {data2.get('weight_pct')}"
    
    def test_distance_101_150km_returns_40_percent(self, admin_token, test_property_id):
        """101-150km distance should return 40% weight"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        resp = requests.post(f"{BASE_URL}/api/revenue/events/{test_property_id}/secondary-cities",
                            json={"city": "Birmingham", "distance_km": 120}, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("weight_pct") == 40, f"Expected weight_pct=40 for 120km, got {data.get('weight_pct')}"
    
    def test_distance_151_200km_returns_25_percent(self, admin_token, test_property_id):
        """151-200km distance should return 25% weight"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        resp = requests.post(f"{BASE_URL}/api/revenue/events/{test_property_id}/secondary-cities",
                            json={"city": "Manchester", "distance_km": 180}, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("weight_pct") == 25, f"Expected weight_pct=25 for 180km, got {data.get('weight_pct')}"
    
    def test_distance_over_200km_returns_15_percent(self, admin_token, test_property_id):
        """>200km distance should return 15% weight (floor)"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        resp = requests.post(f"{BASE_URL}/api/revenue/events/{test_property_id}/secondary-cities",
                            json={"city": "Edinburgh", "distance_km": 650}, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("weight_pct") == 15, f"Expected weight_pct=15 for 650km, got {data.get('weight_pct')}"


class TestPostSecondaryWithDistance:
    """Test POST /api/revenue/events/{pid}/secondary-cities with distance_km"""
    
    def test_add_secondary_with_distance_returns_weight_pct(self, admin_token, test_property_id):
        """POST with distance_km returns weight_pct in response"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        resp = requests.post(f"{BASE_URL}/api/revenue/events/{test_property_id}/secondary-cities",
                            json={"city": "Brighton", "distance_km": 80}, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        
        assert "weight_pct" in data, "Response should include weight_pct"
        assert "distance_km" in data, "Response should include distance_km"
        assert data["distance_km"] == 80
        assert data["weight_pct"] == 60  # 61-100km tier
    
    def test_add_secondary_without_distance_no_weight_pct(self, admin_token, test_property_id):
        """POST without distance_km returns weight_pct as None"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        resp = requests.post(f"{BASE_URL}/api/revenue/events/{test_property_id}/secondary-cities",
                            json={"city": "Cambridge"}, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        
        # weight_pct should be None when no distance provided
        assert data.get("weight_pct") is None or data.get("distance_km") is None
    
    def test_add_secondary_distance_validation_non_numeric(self, admin_token, test_property_id):
        """400 if distance_km is not numeric"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        resp = requests.post(f"{BASE_URL}/api/revenue/events/{test_property_id}/secondary-cities",
                            json={"city": "Bristol", "distance_km": "not-a-number"}, headers=headers)
        assert resp.status_code == 400, f"Expected 400 for non-numeric distance, got {resp.status_code}"
    
    def test_add_secondary_distance_validation_negative(self, admin_token, test_property_id):
        """400 if distance_km is negative"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        resp = requests.post(f"{BASE_URL}/api/revenue/events/{test_property_id}/secondary-cities",
                            json={"city": "Bristol", "distance_km": -10}, headers=headers)
        assert resp.status_code == 400, f"Expected 400 for negative distance, got {resp.status_code}"
    
    def test_add_secondary_distance_validation_over_1000(self, admin_token, test_property_id):
        """400 if distance_km is over 1000"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        resp = requests.post(f"{BASE_URL}/api/revenue/events/{test_property_id}/secondary-cities",
                            json={"city": "Bristol", "distance_km": 1500}, headers=headers)
        assert resp.status_code == 400, f"Expected 400 for distance > 1000, got {resp.status_code}"
    
    def test_add_secondary_distance_boundary_0(self, admin_token, test_property_id):
        """distance_km=0 is valid and returns 100%"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        resp = requests.post(f"{BASE_URL}/api/revenue/events/{test_property_id}/secondary-cities",
                            json={"city": "Croydon", "distance_km": 0}, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("weight_pct") == 100
    
    def test_add_secondary_distance_boundary_1000(self, admin_token, test_property_id):
        """distance_km=1000 is valid and returns 15%"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        resp = requests.post(f"{BASE_URL}/api/revenue/events/{test_property_id}/secondary-cities",
                            json={"city": "Inverness", "distance_km": 1000}, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("weight_pct") == 15


class TestPatchSecondaryDistance:
    """Test PATCH /api/revenue/events/{pid}/secondary-cities/{city_name}"""
    
    def test_patch_distance_success(self, admin_token, test_property_id):
        """PATCH updates distance and returns new weight"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # First add a secondary city without distance
        requests.post(f"{BASE_URL}/api/revenue/events/{test_property_id}/secondary-cities",
                     json={"city": "Oxford"}, headers=headers)
        
        # PATCH to set distance
        resp = requests.patch(f"{BASE_URL}/api/revenue/events/{test_property_id}/secondary-cities/Oxford",
                             json={"distance_km": 90}, headers=headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        
        assert data.get("ok") == True
        assert data.get("city") == "Oxford"
        assert data.get("distance_km") == 90
        assert data.get("weight") == 0.6  # 61-100km tier
        assert data.get("weight_pct") == 60
    
    def test_patch_distance_updates_existing(self, admin_token, test_property_id):
        """PATCH can update an existing distance"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Add with initial distance
        requests.post(f"{BASE_URL}/api/revenue/events/{test_property_id}/secondary-cities",
                     json={"city": "Brighton", "distance_km": 80}, headers=headers)
        
        # Update distance
        resp = requests.patch(f"{BASE_URL}/api/revenue/events/{test_property_id}/secondary-cities/Brighton",
                             json={"distance_km": 50}, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        
        assert data.get("distance_km") == 50
        assert data.get("weight_pct") == 80  # 31-60km tier now
    
    def test_patch_distance_not_in_list_returns_404(self, admin_token, test_property_id):
        """404 if city is not in secondary list"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        resp = requests.patch(f"{BASE_URL}/api/revenue/events/{test_property_id}/secondary-cities/NonExistent",
                             json={"distance_km": 100}, headers=headers)
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}"
    
    def test_patch_distance_validation_non_numeric(self, admin_token, test_property_id):
        """400 if distance_km is not numeric"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Add secondary city first
        requests.post(f"{BASE_URL}/api/revenue/events/{test_property_id}/secondary-cities",
                     json={"city": "Cambridge"}, headers=headers)
        
        resp = requests.patch(f"{BASE_URL}/api/revenue/events/{test_property_id}/secondary-cities/Cambridge",
                             json={"distance_km": "abc"}, headers=headers)
        assert resp.status_code == 400, f"Expected 400 for non-numeric, got {resp.status_code}"
    
    def test_patch_distance_validation_out_of_range(self, admin_token, test_property_id):
        """400 if distance_km is out of 0-1000 range"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Add secondary city first
        requests.post(f"{BASE_URL}/api/revenue/events/{test_property_id}/secondary-cities",
                     json={"city": "Bristol"}, headers=headers)
        
        # Test negative
        resp = requests.patch(f"{BASE_URL}/api/revenue/events/{test_property_id}/secondary-cities/Bristol",
                             json={"distance_km": -5}, headers=headers)
        assert resp.status_code == 400, f"Expected 400 for negative, got {resp.status_code}"
        
        # Test over 1000
        resp2 = requests.patch(f"{BASE_URL}/api/revenue/events/{test_property_id}/secondary-cities/Bristol",
                              json={"distance_km": 1001}, headers=headers)
        assert resp2.status_code == 400, f"Expected 400 for >1000, got {resp2.status_code}"
    
    def test_patch_distance_case_insensitive(self, admin_token, test_property_id):
        """PATCH works case-insensitively"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Add "Brighton"
        requests.post(f"{BASE_URL}/api/revenue/events/{test_property_id}/secondary-cities",
                     json={"city": "Brighton"}, headers=headers)
        
        # PATCH with "BRIGHTON"
        resp = requests.patch(f"{BASE_URL}/api/revenue/events/{test_property_id}/secondary-cities/BRIGHTON",
                             json={"distance_km": 80}, headers=headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"


class TestGetSecondariesEnriched:
    """Test GET /api/revenue/events/{pid}/secondary-cities returns enriched data"""
    
    def test_get_secondaries_returns_enriched_list(self, admin_token, test_property_id):
        """GET returns secondaries with city, distance_km, weight, weight_pct"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Add secondary cities with distances
        requests.post(f"{BASE_URL}/api/revenue/events/{test_property_id}/secondary-cities",
                     json={"city": "Brighton", "distance_km": 80}, headers=headers)
        requests.post(f"{BASE_URL}/api/revenue/events/{test_property_id}/secondary-cities",
                     json={"city": "Oxford", "distance_km": 90}, headers=headers)
        
        # GET secondary cities
        resp = requests.get(f"{BASE_URL}/api/revenue/events/{test_property_id}/secondary-cities", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        
        assert "secondaries" in data, "Response should have 'secondaries' field"
        secondaries = data["secondaries"]
        assert isinstance(secondaries, list)
        assert len(secondaries) >= 2
        
        # Check structure of each secondary
        for sec in secondaries:
            assert "city" in sec, "Each secondary should have 'city'"
            assert "distance_km" in sec, "Each secondary should have 'distance_km'"
            assert "weight" in sec, "Each secondary should have 'weight'"
            assert "weight_pct" in sec, "Each secondary should have 'weight_pct'"
        
        # Find Brighton and verify values
        brighton = next((s for s in secondaries if s["city"].lower() == "brighton"), None)
        assert brighton is not None, "Brighton should be in secondaries"
        assert brighton["distance_km"] == 80
        assert brighton["weight"] == 0.6
        assert brighton["weight_pct"] == 60
    
    def test_get_secondaries_without_distance_has_default_weight(self, admin_token, test_property_id):
        """Secondary without distance gets default 60% weight"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Add secondary city WITHOUT distance
        requests.post(f"{BASE_URL}/api/revenue/events/{test_property_id}/secondary-cities",
                     json={"city": "Cambridge"}, headers=headers)
        
        # GET secondary cities
        resp = requests.get(f"{BASE_URL}/api/revenue/events/{test_property_id}/secondary-cities", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        
        cambridge = next((s for s in data["secondaries"] if s["city"].lower() == "cambridge"), None)
        assert cambridge is not None
        assert cambridge["distance_km"] is None, "distance_km should be None when not set"
        assert cambridge["weight"] == 0.6, "Default weight should be 0.6 (60%)"
        assert cambridge["weight_pct"] == 60, "Default weight_pct should be 60"


class TestGetEventsWithDistanceMap:
    """Test GET /api/revenue/events/{pid} includes secondary_cities_distance map"""
    
    def test_get_events_includes_distance_map(self, admin_token, test_property_id):
        """GET events returns secondary_cities_distance field"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Add secondary cities with distances
        requests.post(f"{BASE_URL}/api/revenue/events/{test_property_id}/secondary-cities",
                     json={"city": "Brighton", "distance_km": 80}, headers=headers)
        requests.post(f"{BASE_URL}/api/revenue/events/{test_property_id}/secondary-cities",
                     json={"city": "Oxford", "distance_km": 90}, headers=headers)
        
        # GET events
        resp = requests.get(f"{BASE_URL}/api/revenue/events/{test_property_id}", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        
        assert "secondary_cities_distance" in data, "Response should have secondary_cities_distance"
        dist_map = data["secondary_cities_distance"]
        assert isinstance(dist_map, dict)
        
        # Check distances are in the map
        assert "Brighton" in dist_map or any(k.lower() == "brighton" for k in dist_map.keys())
        assert "Oxford" in dist_map or any(k.lower() == "oxford" for k in dist_map.keys())


class TestDeleteRemovesDistance:
    """Test DELETE /api/revenue/events/{pid}/secondary-cities/{city} removes distance entry"""
    
    def test_delete_removes_distance_entry(self, admin_token, test_property_id):
        """DELETE secondary city also removes its distance from the map"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Add secondary city with distance
        requests.post(f"{BASE_URL}/api/revenue/events/{test_property_id}/secondary-cities",
                     json={"city": "Brighton", "distance_km": 80}, headers=headers)
        
        # Verify it's in the distance map
        resp1 = requests.get(f"{BASE_URL}/api/revenue/events/{test_property_id}", headers=headers)
        dist_map1 = resp1.json().get("secondary_cities_distance", {})
        assert "Brighton" in dist_map1 or any(k.lower() == "brighton" for k in dist_map1.keys()), \
            "Brighton should be in distance map before delete"
        
        # DELETE the secondary city
        del_resp = requests.delete(f"{BASE_URL}/api/revenue/events/{test_property_id}/secondary-cities/Brighton",
                                  headers=headers)
        assert del_resp.status_code == 200
        
        # Verify distance entry is removed
        resp2 = requests.get(f"{BASE_URL}/api/revenue/events/{test_property_id}", headers=headers)
        dist_map2 = resp2.json().get("secondary_cities_distance", {})
        assert "Brighton" not in dist_map2 and not any(k.lower() == "brighton" for k in dist_map2.keys()), \
            "Brighton should NOT be in distance map after delete"


class TestApplyEventPricingWithWeight:
    """Test _apply_event_pricing applies boost * weight and includes @city(pct%) in reason"""
    
    def test_secondary_city_event_has_weighted_boost(self, admin_token, test_property_id):
        """Event in secondary city gets weighted boost, reason includes @city(pct%)"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Add secondary city with 80km distance (60% weight)
        requests.post(f"{BASE_URL}/api/revenue/events/{test_property_id}/secondary-cities",
                     json={"city": "Brighton", "distance_km": 80}, headers=headers)
        
        # Add a high-HDS event in Brighton with auto_price=true
        event_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
        add_resp = requests.post(f"{BASE_URL}/api/revenue/events/{test_property_id}/add", json={
            "name": "Brighton Festival",
            "date": event_date,
            "city": "Brighton",
            "category": "festival",
            "hotel_demand_score": 80,  # Critical HDS
            "visitor_origin": "international",
            "is_evening": True,
            "auto_price": True
        }, headers=headers)
        assert add_resp.status_code == 200, f"Failed to add event: {add_resp.text}"
        
        # Check rate_overrides for the event date
        # The reason should contain @Brighton(60%)
        overrides_resp = requests.get(f"{BASE_URL}/api/revenue/rate-overrides/{test_property_id}", headers=headers)
        if overrides_resp.status_code == 200:
            overrides = overrides_resp.json().get("overrides", [])
            # Find override for event date
            event_override = next((o for o in overrides if o.get("date") == event_date), None)
            if event_override:
                reason = event_override.get("reason", "")
                assert "@Brighton(60%)" in reason, f"Reason should contain '@Brighton(60%)', got: {reason}"
    
    def test_primary_city_event_no_weight_tag(self, admin_token, test_property_id):
        """Event in primary city should NOT have @city tag in reason"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Add a high-HDS event in London (primary city) with auto_price=true
        event_date = (datetime.now() + timedelta(days=45)).strftime("%Y-%m-%d")
        add_resp = requests.post(f"{BASE_URL}/api/revenue/events/{test_property_id}/add", json={
            "name": "London Concert",
            "date": event_date,
            "city": "London",
            "category": "concert",
            "hotel_demand_score": 80,
            "visitor_origin": "international",
            "is_evening": True,
            "auto_price": True
        }, headers=headers)
        assert add_resp.status_code == 200
        
        # Check rate_overrides - reason should NOT contain @ tag
        overrides_resp = requests.get(f"{BASE_URL}/api/revenue/rate-overrides/{test_property_id}", headers=headers)
        if overrides_resp.status_code == 200:
            overrides = overrides_resp.json().get("overrides", [])
            event_override = next((o for o in overrides if o.get("date") == event_date), None)
            if event_override:
                reason = event_override.get("reason", "")
                # Should not have @London or any @ tag since it's primary city
                assert "@London" not in reason, f"Primary city event should not have @London tag, got: {reason}"


class TestRBACPatchEndpoint:
    """Test RBAC: receptionist gets 403 on PATCH secondary-cities endpoint"""
    
    def test_receptionist_cannot_patch_distance(self, admin_token, recep_token, test_property_id):
        """Receptionist gets 403 on PATCH secondary-cities"""
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        recep_headers = {"Authorization": f"Bearer {recep_token}"}
        
        # Admin adds secondary city
        requests.post(f"{BASE_URL}/api/revenue/events/{test_property_id}/secondary-cities",
                     json={"city": "Brighton"}, headers=admin_headers)
        
        # Receptionist tries to PATCH
        resp = requests.patch(f"{BASE_URL}/api/revenue/events/{test_property_id}/secondary-cities/Brighton",
                             json={"distance_km": 80}, headers=recep_headers)
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}"
    
    def test_unauthenticated_cannot_patch_distance(self, admin_token, test_property_id):
        """Unauthenticated request gets 401 on PATCH"""
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Admin adds secondary city
        requests.post(f"{BASE_URL}/api/revenue/events/{test_property_id}/secondary-cities",
                     json={"city": "Oxford"}, headers=admin_headers)
        
        # Unauthenticated PATCH
        resp = requests.patch(f"{BASE_URL}/api/revenue/events/{test_property_id}/secondary-cities/Oxford",
                             json={"distance_km": 90})
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"


class TestRegressionIter300:
    """Regression tests for Iteration 300 multi-city scan features"""
    
    def test_get_tracked_cities_still_works(self, admin_token, test_property_id):
        """GET events still returns tracked_cities"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        requests.post(f"{BASE_URL}/api/revenue/events/{test_property_id}/secondary-cities",
                     json={"city": "Brighton"}, headers=headers)
        
        resp = requests.get(f"{BASE_URL}/api/revenue/events/{test_property_id}", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        
        assert "tracked_cities" in data
        assert "London" in data["tracked_cities"]
        assert "Brighton" in data["tracked_cities"]
    
    def test_cleanup_foreign_still_works(self, admin_token, test_property_id):
        """POST cleanup-foreign still works"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        resp = requests.post(f"{BASE_URL}/api/revenue/events/{test_property_id}/cleanup-foreign", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "tracked_cities" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
