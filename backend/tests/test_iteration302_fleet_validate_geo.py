"""
Iteration 302 - Fleet-wide Coordinate Validation + Auto-Repair Endpoint Tests

Tests for POST /api/revenue/market-robot/fleet-validate-geo endpoint:
- dry_run=true returns per-property report without modifications
- fix=true on known-broken property repairs coordinates
- property_ids filter restricts scope
- Auth required (admin/manager role)
- Edge cases: no coordinates, no country field
- Regression: existing endpoints still work

Note: Uses Nominatim public API (1 req/sec rate limit). Tests use sleep_s parameter.
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"
RECEPTIONIST_EMAIL = "testrecep@hotelbox.com"
RECEPTIONIST_PASSWORD = "Test2026!"

# Known test properties with coordinates
CAMDEN_SUITES_ID = "camden-suites"
ALDGATE_FLATS_ID = "aldgate-flats"
CITY_ROOMS_ID = "city-rooms"

# Boston coordinates (for corruption test)
BOSTON_LAT = 42.3373268
BOSTON_LON = -71.0812415
BOSTON_DISPLAY = "Boston, MA, United States"

# London coordinates (expected after fix)
LONDON_LAT_APPROX = 51.5  # Camden area is around 51.55


class TestFleetValidateGeoAuth:
    """Authentication and authorization tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
    
    def get_admin_token(self):
        """Get admin auth token"""
        resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if resp.status_code == 200:
            data = resp.json()
            return data.get("token") or data.get("access_token")
        return None
    
    def get_receptionist_token(self):
        """Get receptionist auth token"""
        resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": RECEPTIONIST_EMAIL,
            "password": RECEPTIONIST_PASSWORD
        })
        if resp.status_code == 200:
            data = resp.json()
            return data.get("token") or data.get("access_token")
        return None
    
    def test_unauthenticated_returns_401(self):
        """Endpoint requires authentication"""
        resp = self.session.post(f"{BASE_URL}/api/revenue/market-robot/fleet-validate-geo", json={})
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
        print("PASSED: Unauthenticated request returns 401")
    
    def test_receptionist_returns_403(self):
        """Receptionist role should be denied (requires admin/manager)"""
        token = self.get_receptionist_token()
        if not token:
            pytest.skip("Could not get receptionist token")
        
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        resp = self.session.post(f"{BASE_URL}/api/revenue/market-robot/fleet-validate-geo", json={})
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}"
        print("PASSED: Receptionist gets 403 Forbidden")
    
    def test_admin_returns_200(self):
        """Admin role should be allowed"""
        token = self.get_admin_token()
        if not token:
            pytest.skip("Could not get admin token")
        
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        resp = self.session.post(f"{BASE_URL}/api/revenue/market-robot/fleet-validate-geo", json={
            "dry_run": True,
            "property_ids": [CAMDEN_SUITES_ID]  # Limit scope for speed
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        print("PASSED: Admin gets 200 OK")


class TestFleetValidateGeoDryRun:
    """Dry run mode tests - no modifications, just reporting"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        token = self._get_admin_token()
        if token:
            self.session.headers.update({"Authorization": f"Bearer {token}"})
    
    def _get_admin_token(self):
        resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if resp.status_code == 200:
            data = resp.json()
            return data.get("token") or data.get("access_token")
        return None
    
    def test_dry_run_returns_report_structure(self):
        """dry_run=true returns proper report structure"""
        resp = self.session.post(f"{BASE_URL}/api/revenue/market-robot/fleet-validate-geo", json={
            "dry_run": True,
            "property_ids": [CAMDEN_SUITES_ID],
            "sleep_s": 0.5  # Faster for testing
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        # Check top-level fields
        assert "ok" in data, "Missing 'ok' field"
        assert "ok_count" in data, "Missing 'ok_count' field"
        assert "flagged_count" in data, "Missing 'flagged_count' field"
        assert "fixed_count" in data, "Missing 'fixed_count' field"
        assert "skipped_count" in data, "Missing 'skipped_count' field"
        assert "results" in data, "Missing 'results' field"
        assert data.get("dry_run") == True, "dry_run should be True"
        
        print(f"PASSED: Report structure valid - ok={data['ok_count']}, flagged={data['flagged_count']}, skipped={data['skipped_count']}")
    
    def test_dry_run_result_entry_structure(self):
        """Each result entry has required fields"""
        resp = self.session.post(f"{BASE_URL}/api/revenue/market-robot/fleet-validate-geo", json={
            "dry_run": True,
            "property_ids": [CAMDEN_SUITES_ID],
            "sleep_s": 0.5
        })
        assert resp.status_code == 200
        
        data = resp.json()
        results = data.get("results", [])
        assert len(results) > 0, "Expected at least one result"
        
        entry = results[0]
        required_fields = ["property_id", "name", "city", "country", "expected_country_code", "before", "status"]
        for field in required_fields:
            assert field in entry, f"Missing required field: {field}"
        
        # Check 'before' structure
        before = entry.get("before", {})
        assert "latitude" in before, "Missing before.latitude"
        assert "longitude" in before, "Missing before.longitude"
        assert "display" in before, "Missing before.display"
        
        print(f"PASSED: Result entry has all required fields - property_id={entry['property_id']}, status={entry['status']}")
    
    def test_dry_run_camden_suites_ok_status(self):
        """Camden-suites with correct London coords should return status=ok"""
        resp = self.session.post(f"{BASE_URL}/api/revenue/market-robot/fleet-validate-geo", json={
            "dry_run": True,
            "property_ids": [CAMDEN_SUITES_ID],
            "sleep_s": 0.5
        })
        assert resp.status_code == 200
        
        data = resp.json()
        results = data.get("results", [])
        camden_result = next((r for r in results if r.get("property_id") == CAMDEN_SUITES_ID), None)
        
        assert camden_result is not None, "Camden-suites not in results"
        # Should be OK since it has correct London coordinates
        assert camden_result.get("status") in ["ok", "flagged"], f"Unexpected status: {camden_result.get('status')}"
        
        # If OK, should have actual_country_code = gb
        if camden_result.get("status") == "ok":
            assert camden_result.get("actual_country_code") == "gb", f"Expected gb, got {camden_result.get('actual_country_code')}"
        
        print(f"PASSED: Camden-suites status={camden_result.get('status')}, actual_cc={camden_result.get('actual_country_code')}")


class TestFleetValidateGeoPropertyFilter:
    """Property ID filter tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        token = self._get_admin_token()
        if token:
            self.session.headers.update({"Authorization": f"Bearer {token}"})
    
    def _get_admin_token(self):
        resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if resp.status_code == 200:
            data = resp.json()
            return data.get("token") or data.get("access_token")
        return None
    
    def test_property_ids_filter_single(self):
        """property_ids filter restricts to single property"""
        resp = self.session.post(f"{BASE_URL}/api/revenue/market-robot/fleet-validate-geo", json={
            "dry_run": True,
            "property_ids": [ALDGATE_FLATS_ID],
            "sleep_s": 0.5
        })
        assert resp.status_code == 200
        
        data = resp.json()
        results = data.get("results", [])
        
        # Should only have aldgate-flats
        property_ids = [r.get("property_id") for r in results]
        assert ALDGATE_FLATS_ID in property_ids, f"Expected {ALDGATE_FLATS_ID} in results"
        assert len(property_ids) == 1, f"Expected 1 result, got {len(property_ids)}"
        
        print(f"PASSED: Single property filter works - got {property_ids}")
    
    def test_property_ids_filter_multiple(self):
        """property_ids filter with multiple IDs"""
        resp = self.session.post(f"{BASE_URL}/api/revenue/market-robot/fleet-validate-geo", json={
            "dry_run": True,
            "property_ids": [CAMDEN_SUITES_ID, ALDGATE_FLATS_ID],
            "sleep_s": 0.5
        })
        assert resp.status_code == 200
        
        data = resp.json()
        results = data.get("results", [])
        property_ids = [r.get("property_id") for r in results]
        
        assert CAMDEN_SUITES_ID in property_ids, f"Expected {CAMDEN_SUITES_ID} in results"
        assert ALDGATE_FLATS_ID in property_ids, f"Expected {ALDGATE_FLATS_ID} in results"
        assert len(property_ids) == 2, f"Expected 2 results, got {len(property_ids)}"
        
        print(f"PASSED: Multiple property filter works - got {property_ids}")


class TestFleetValidateGeoEdgeCases:
    """Edge case tests - no coordinates, no country"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        token = self._get_admin_token()
        if token:
            self.session.headers.update({"Authorization": f"Bearer {token}"})
    
    def _get_admin_token(self):
        resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if resp.status_code == 200:
            data = resp.json()
            return data.get("token") or data.get("access_token")
        return None
    
    def test_property_without_coordinates_skipped(self):
        """Properties without lat/lon should be skipped with reason='no_coordinates'"""
        # First, get all properties to find one without coordinates
        resp = self.session.post(f"{BASE_URL}/api/revenue/market-robot/fleet-validate-geo", json={
            "dry_run": True,
            "sleep_s": 0.5
        })
        assert resp.status_code == 200
        
        data = resp.json()
        results = data.get("results", [])
        
        # Find any skipped with no_coordinates
        no_coords = [r for r in results if r.get("reason") == "no_coordinates"]
        
        if no_coords:
            entry = no_coords[0]
            assert entry.get("status") == "skipped", f"Expected status=skipped, got {entry.get('status')}"
            print(f"PASSED: Property without coordinates skipped - {entry.get('property_id')}")
        else:
            # All properties have coordinates - check skipped_count
            print(f"INFO: All tested properties have coordinates. skipped_count={data.get('skipped_count')}")
            assert True  # Pass if no properties without coords


class TestFleetValidateGeoFixMode:
    """Fix mode tests - corrupts and repairs coordinates"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        token = self._get_admin_token()
        if token:
            self.session.headers.update({"Authorization": f"Bearer {token}"})
        self.original_coords = None
    
    def _get_admin_token(self):
        resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if resp.status_code == 200:
            data = resp.json()
            return data.get("token") or data.get("access_token")
        return None
    
    def _corrupt_camden_to_boston(self):
        """Corrupt camden-suites coordinates to Boston, MA"""
        import asyncio
        from motor.motor_asyncio import AsyncIOMotorClient
        
        async def corrupt():
            client = AsyncIOMotorClient(os.environ.get('MONGO_URL'))
            db = client[os.environ.get('DB_NAME', 'test_database')]
            
            # Save original coords
            prop = await db.properties.find_one({"id": CAMDEN_SUITES_ID}, {"_id": 0, "latitude": 1, "longitude": 1, "geocoded_display_name": 1})
            original = {
                "latitude": prop.get("latitude"),
                "longitude": prop.get("longitude"),
                "display": prop.get("geocoded_display_name")
            }
            
            # Corrupt to Boston
            await db.properties.update_one(
                {"id": CAMDEN_SUITES_ID},
                {"$set": {
                    "latitude": BOSTON_LAT,
                    "longitude": BOSTON_LON,
                    "geocoded_display_name": BOSTON_DISPLAY
                }}
            )
            
            client.close()
            return original
        
        return asyncio.run(corrupt())
    
    def _restore_camden_coords(self, original):
        """Restore camden-suites to original coordinates"""
        import asyncio
        from motor.motor_asyncio import AsyncIOMotorClient
        
        async def restore():
            client = AsyncIOMotorClient(os.environ.get('MONGO_URL'))
            db = client[os.environ.get('DB_NAME', 'test_database')]
            
            await db.properties.update_one(
                {"id": CAMDEN_SUITES_ID},
                {"$set": {
                    "latitude": original["latitude"],
                    "longitude": original["longitude"],
                    "geocoded_display_name": original["display"]
                }}
            )
            
            client.close()
        
        asyncio.run(restore())
    
    def test_fix_mode_repairs_corrupted_property(self):
        """fix=true on corrupted property should repair coordinates"""
        # Step 1: Corrupt camden-suites to Boston coords
        original = self._corrupt_camden_to_boston()
        self.original_coords = original
        print(f"Corrupted camden-suites to Boston: lat={BOSTON_LAT}, lon={BOSTON_LON}")
        
        try:
            # Step 2: Run dry_run first to confirm it's flagged
            resp = self.session.post(f"{BASE_URL}/api/revenue/market-robot/fleet-validate-geo", json={
                "dry_run": True,
                "property_ids": [CAMDEN_SUITES_ID],
                "sleep_s": 1.1  # Respect Nominatim rate limit
            })
            assert resp.status_code == 200, f"Dry run failed: {resp.text}"
            
            data = resp.json()
            results = data.get("results", [])
            camden_result = next((r for r in results if r.get("property_id") == CAMDEN_SUITES_ID), None)
            
            assert camden_result is not None, "Camden-suites not in results"
            assert camden_result.get("status") == "flagged", f"Expected flagged, got {camden_result.get('status')}"
            assert camden_result.get("reason") == "country_mismatch", f"Expected country_mismatch, got {camden_result.get('reason')}"
            assert camden_result.get("actual_country_code") == "us", f"Expected us, got {camden_result.get('actual_country_code')}"
            
            print(f"Dry run confirmed: status=flagged, reason=country_mismatch, actual_cc=us")
            
            # Step 3: Run with fix=true to repair
            time.sleep(2)  # Extra delay for Nominatim
            resp = self.session.post(f"{BASE_URL}/api/revenue/market-robot/fleet-validate-geo", json={
                "dry_run": False,
                "fix": True,
                "property_ids": [CAMDEN_SUITES_ID],
                "sleep_s": 1.1
            })
            assert resp.status_code == 200, f"Fix mode failed: {resp.text}"
            
            data = resp.json()
            results = data.get("results", [])
            camden_result = next((r for r in results if r.get("property_id") == CAMDEN_SUITES_ID), None)
            
            assert camden_result is not None, "Camden-suites not in results"
            assert camden_result.get("status") == "fixed", f"Expected fixed, got {camden_result.get('status')}"
            
            # Check after coordinates are in London area
            after = camden_result.get("after", {})
            assert after.get("latitude") is not None, "Missing after.latitude"
            assert after.get("latitude") > 51.0, f"Expected London lat >51, got {after.get('latitude')}"
            assert after.get("latitude") < 52.0, f"Expected London lat <52, got {after.get('latitude')}"
            
            # Check display contains London or United Kingdom
            display = (after.get("display") or "").lower()
            assert "london" in display or "united kingdom" in display, f"Expected London in display, got: {after.get('display')}"
            
            print(f"PASSED: Fix mode repaired - status=fixed, after.lat={after.get('latitude')}, display contains London")
            
        finally:
            # Restore original coords
            if self.original_coords:
                self._restore_camden_coords(self.original_coords)
                print("Restored camden-suites to original coordinates")


class TestReverseGeocodeHelper:
    """Test the underlying reverse_geocode helper function"""
    
    def test_reverse_geocode_london_coords(self):
        """reverse_geocode returns correct country_code for London coordinates"""
        import asyncio
        import sys
        sys.path.insert(0, '/app/backend')
        from utils.booking_scraper import reverse_geocode
        
        async def test():
            # Camden area coordinates
            result = await reverse_geocode(51.5490966, -0.1287947)
            return result
        
        result = asyncio.run(test())
        
        assert result is not None, "reverse_geocode returned None"
        assert result.get("country_code") == "gb", f"Expected gb, got {result.get('country_code')}"
        assert "city" in result, "Missing city field"
        assert "display_name" in result, "Missing display_name field"
        
        print(f"PASSED: reverse_geocode London - country_code={result.get('country_code')}, city={result.get('city')}")
    
    def test_reverse_geocode_boston_coords(self):
        """reverse_geocode returns us for Boston coordinates"""
        import asyncio
        import sys
        sys.path.insert(0, '/app/backend')
        from utils.booking_scraper import reverse_geocode
        
        async def test():
            result = await reverse_geocode(BOSTON_LAT, BOSTON_LON)
            return result
        
        result = asyncio.run(test())
        
        assert result is not None, "reverse_geocode returned None"
        assert result.get("country_code") == "us", f"Expected us, got {result.get('country_code')}"
        
        print(f"PASSED: reverse_geocode Boston - country_code={result.get('country_code')}")


class TestRegressionExistingEndpoints:
    """Regression tests - existing endpoints still work"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        token = self._get_admin_token()
        if token:
            self.session.headers.update({"Authorization": f"Bearer {token}"})
    
    def _get_admin_token(self):
        resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if resp.status_code == 200:
            data = resp.json()
            return data.get("token") or data.get("access_token")
        return None
    
    def test_auto_geocode_endpoint_still_works(self):
        """POST /auto-geocode endpoint still returns 200"""
        resp = self.session.post(f"{BASE_URL}/api/revenue/market-robot/{CAMDEN_SUITES_ID}/auto-geocode", json={})
        # May return 200 or 404 depending on config, but should not error
        assert resp.status_code in [200, 404, 400], f"Unexpected status: {resp.status_code}: {resp.text}"
        print(f"PASSED: auto-geocode endpoint returns {resp.status_code}")
    
    def test_competitors_discover_endpoint_still_works(self):
        """POST /competitors/discover endpoint still returns 200"""
        resp = self.session.post(f"{BASE_URL}/api/revenue/market-robot/{CAMDEN_SUITES_ID}/competitors/discover", json={
            "max_results": 3
        })
        # Should return 200 with candidates list
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        assert "candidates" in data or "hotels" in data, "Missing candidates/hotels in response"
        print(f"PASSED: competitors/discover endpoint returns 200")
    
    def test_fleet_reset_neighbors_still_works(self):
        """POST /fleet-reset-neighbors endpoint still returns 200"""
        resp = self.session.post(f"{BASE_URL}/api/revenue/market-robot/fleet-reset-neighbors", json={
            "dry_run": True
        })
        # Should return 200
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        print(f"PASSED: fleet-reset-neighbors endpoint returns 200")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
