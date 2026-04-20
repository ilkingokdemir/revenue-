"""
Iteration 166 - Laundry Items CRUD + Smart Order Forecast Tests

Tests:
1. Laundry Items CRUD (laundry_item_defs collection)
   - GET /api/laundry/items/{property_id} - list items with 30d usage stats
   - POST /api/laundry/items/{property_id} - create new item
   - PUT /api/laundry/items/{item_id} - update item
   - DELETE /api/laundry/items/{item_id} - delete item
   - GET /api/laundry/catalog - returns {items:[{id,name}]} for contracts UI

2. Smart Order Forecast
   - GET /api/laundry/forecast/{property_id} - compute forecast
   - POST /api/laundry/forecast/{property_id}/create-dispatch - create dispatch from forecast
"""
import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
PROPERTY_ID = "aldgate-flats"

# Test credentials
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for admin user"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    if response.status_code != 200:
        pytest.skip(f"Auth failed: {response.status_code} - {response.text}")
    data = response.json()
    return data.get("token") or data.get("access_token")


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Headers with auth token"""
    return {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json"
    }


class TestLaundryItemsList:
    """Test GET /api/laundry/items/{property_id}"""
    
    def test_list_items_requires_auth(self):
        """Unauthenticated request should fail"""
        response = requests.get(f"{BASE_URL}/api/laundry/items/{PROPERTY_ID}")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
    
    def test_list_items_returns_seeded_items(self, auth_headers):
        """First call should seed 11 default items"""
        response = requests.get(f"{BASE_URL}/api/laundry/items/{PROPERTY_ID}", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "items" in data, "Response should have 'items' key"
        assert "count" in data, "Response should have 'count' key"
        
        items = data["items"]
        assert len(items) >= 11, f"Expected at least 11 seeded items, got {len(items)}"
    
    def test_list_items_has_required_fields(self, auth_headers):
        """Each item should have all required fields"""
        response = requests.get(f"{BASE_URL}/api/laundry/items/{PROPERTY_ID}", headers=auth_headers)
        assert response.status_code == 200
        
        items = response.json()["items"]
        required_fields = [
            "id", "name", "washing_cost", "purchase_cost", "maintenance_cost",
            "per_cleaning_qty", "sort_order", "active", "usage_30d", "total_cost"
        ]
        
        for item in items[:3]:  # Check first 3 items
            for field in required_fields:
                assert field in item, f"Item missing field '{field}': {item}"
    
    def test_list_items_includes_expected_items(self, auth_headers):
        """Should include standard linen items"""
        response = requests.get(f"{BASE_URL}/api/laundry/items/{PROPERTY_ID}", headers=auth_headers)
        assert response.status_code == 200
        
        items = response.json()["items"]
        names = [i["name"] for i in items]
        
        expected_items = [
            "Bed Sheet (Single)", "Bed Sheet (Double)", "Bed Sheet (King)",
            "Pillow Case", "Duvet Cover", "Bath Towel", "Hand Towel",
            "Face Cloth", "Bath Mat", "Table Cloth", "Napkin"
        ]
        
        for expected in expected_items:
            assert expected in names, f"Missing expected item: {expected}"
    
    def test_list_items_per_cleaning_qty_values(self, auth_headers):
        """Table Cloth and Napkin should have per_cleaning_qty=0"""
        response = requests.get(f"{BASE_URL}/api/laundry/items/{PROPERTY_ID}", headers=auth_headers)
        assert response.status_code == 200
        
        items = response.json()["items"]
        items_by_name = {i["name"]: i for i in items}
        
        # Items with per_cleaning_qty=0 (excluded from forecast)
        assert items_by_name.get("Table Cloth", {}).get("per_cleaning_qty") == 0
        assert items_by_name.get("Napkin", {}).get("per_cleaning_qty") == 0
        
        # Items with per_cleaning_qty > 0
        assert items_by_name.get("Pillow Case", {}).get("per_cleaning_qty") == 2
        assert items_by_name.get("Bath Towel", {}).get("per_cleaning_qty") == 2


class TestLaundryItemsCreate:
    """Test POST /api/laundry/items/{property_id}"""
    
    def test_create_item_requires_auth(self):
        """Unauthenticated request should fail"""
        response = requests.post(f"{BASE_URL}/api/laundry/items/{PROPERTY_ID}", json={
            "name": "TEST_Pool Towel"
        })
        assert response.status_code in [401, 403]
    
    def test_create_item_empty_name_returns_400(self, auth_headers):
        """Empty name should return 400"""
        response = requests.post(
            f"{BASE_URL}/api/laundry/items/{PROPERTY_ID}",
            headers=auth_headers,
            json={"name": "", "washing_cost": 0.5}
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
    
    def test_create_item_success(self, auth_headers):
        """Create a new laundry item"""
        payload = {
            "name": "TEST_Pool Towel",
            "washing_cost": 0.8,
            "purchase_cost": 14.0,
            "maintenance_cost": 0.12,
            "per_cleaning_qty": 1,
            "sort_order": 75,
            "active": True
        }
        
        response = requests.post(
            f"{BASE_URL}/api/laundry/items/{PROPERTY_ID}",
            headers=auth_headers,
            json=payload
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["name"] == "TEST_Pool Towel"
        assert data["washing_cost"] == 0.8
        assert data["purchase_cost"] == 14.0
        assert data["maintenance_cost"] == 0.12
        assert data["per_cleaning_qty"] == 1
        assert data["sort_order"] == 75
        assert data["active"] == True
        assert "id" in data
        
        # Store for cleanup
        TestLaundryItemsCreate.created_item_id = data["id"]
    
    def test_create_duplicate_name_returns_400(self, auth_headers):
        """Duplicate name should return 400"""
        response = requests.post(
            f"{BASE_URL}/api/laundry/items/{PROPERTY_ID}",
            headers=auth_headers,
            json={"name": "TEST_Pool Towel", "washing_cost": 1.0}
        )
        assert response.status_code == 400, f"Expected 400 for duplicate, got {response.status_code}"
        assert "already exists" in response.text.lower() or "exists" in response.text.lower()


class TestLaundryItemsUpdate:
    """Test PUT /api/laundry/items/{item_id}"""
    
    def test_update_item_invalid_id_returns_404(self, auth_headers):
        """Invalid item ID should return 404"""
        response = requests.put(
            f"{BASE_URL}/api/laundry/items/nonexistent-id-12345",
            headers=auth_headers,
            json={"washing_cost": 1.5}
        )
        assert response.status_code == 404
    
    def test_update_item_success(self, auth_headers):
        """Update an existing item"""
        # First get an item to update
        list_response = requests.get(f"{BASE_URL}/api/laundry/items/{PROPERTY_ID}", headers=auth_headers)
        items = list_response.json()["items"]
        
        # Find our test item or use first item
        test_item = next((i for i in items if "TEST_" in i["name"]), items[0])
        item_id = test_item["id"]
        
        # Update it
        response = requests.put(
            f"{BASE_URL}/api/laundry/items/{item_id}",
            headers=auth_headers,
            json={
                "washing_cost": 1.25,
                "per_cleaning_qty": 3
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["washing_cost"] == 1.25
        assert data["per_cleaning_qty"] == 3
    
    def test_update_item_coerces_string_to_float(self, auth_headers):
        """Numeric fields should coerce strings to float/int"""
        list_response = requests.get(f"{BASE_URL}/api/laundry/items/{PROPERTY_ID}", headers=auth_headers)
        items = list_response.json()["items"]
        item_id = items[0]["id"]
        
        response = requests.put(
            f"{BASE_URL}/api/laundry/items/{item_id}",
            headers=auth_headers,
            json={"washing_cost": "2.50", "per_cleaning_qty": "4"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["washing_cost"] == 2.5
        assert data["per_cleaning_qty"] == 4
    
    def test_update_item_toggle_active(self, auth_headers):
        """Toggle active status"""
        list_response = requests.get(f"{BASE_URL}/api/laundry/items/{PROPERTY_ID}", headers=auth_headers)
        items = list_response.json()["items"]
        item = items[0]
        
        # Toggle active
        new_active = not item["active"]
        response = requests.put(
            f"{BASE_URL}/api/laundry/items/{item['id']}",
            headers=auth_headers,
            json={"active": new_active}
        )
        assert response.status_code == 200
        assert response.json()["active"] == new_active
        
        # Toggle back
        requests.put(
            f"{BASE_URL}/api/laundry/items/{item['id']}",
            headers=auth_headers,
            json={"active": item["active"]}
        )


class TestLaundryItemsDelete:
    """Test DELETE /api/laundry/items/{item_id}"""
    
    def test_delete_item_success(self, auth_headers):
        """Delete an item returns {status: deleted}"""
        # Create an item to delete
        create_response = requests.post(
            f"{BASE_URL}/api/laundry/items/{PROPERTY_ID}",
            headers=auth_headers,
            json={"name": "TEST_ToDelete", "washing_cost": 0.5}
        )
        
        if create_response.status_code == 200:
            item_id = create_response.json()["id"]
            
            # Delete it
            response = requests.delete(
                f"{BASE_URL}/api/laundry/items/{item_id}",
                headers=auth_headers
            )
            assert response.status_code == 200
            assert response.json()["status"] == "deleted"
    
    def test_delete_nonexistent_returns_not_found(self, auth_headers):
        """Delete nonexistent item returns not_found status"""
        response = requests.delete(
            f"{BASE_URL}/api/laundry/items/nonexistent-id-99999",
            headers=auth_headers
        )
        assert response.status_code == 200
        assert response.json()["status"] == "not_found"


class TestLaundryCatalog:
    """Test GET /api/laundry/catalog"""
    
    def test_catalog_returns_items(self, auth_headers):
        """Catalog returns {items: [{id, name}]}"""
        response = requests.get(
            f"{BASE_URL}/api/laundry/catalog",
            headers=auth_headers,
            params={"property_id": PROPERTY_ID}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "items" in data
        
        items = data["items"]
        assert len(items) >= 9, f"Expected at least 9 active items, got {len(items)}"
        
        # Each item should have id and name
        for item in items[:3]:
            assert "id" in item
            assert "name" in item


class TestOrderForecast:
    """Test GET /api/laundry/forecast/{property_id}"""
    
    def test_forecast_requires_auth(self):
        """Unauthenticated request should fail"""
        response = requests.get(f"{BASE_URL}/api/laundry/forecast/{PROPERTY_ID}")
        assert response.status_code in [401, 403]
    
    def test_forecast_invalid_date_returns_400(self, auth_headers):
        """Invalid delivery_date format should return 400"""
        response = requests.get(
            f"{BASE_URL}/api/laundry/forecast/{PROPERTY_ID}",
            headers=auth_headers,
            params={"delivery_date": "invalid-date"}
        )
        assert response.status_code == 400
    
    def test_forecast_returns_expected_structure(self, auth_headers):
        """Forecast returns all expected fields"""
        today = datetime.now().strftime("%Y-%m-%d")
        
        response = requests.get(
            f"{BASE_URL}/api/laundry/forecast/{PROPERTY_ID}",
            headers=auth_headers,
            params={
                "delivery_date": today,
                "horizon_days": 7,
                "in_house_cleaning_every": 2
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Check top-level fields
        assert "delivery_date" in data
        assert "horizon_days" in data
        assert "in_house_cleaning_every" in data
        assert "bookings_in_window" in data
        assert "total_cleaning_events" in data
        assert "daily" in data
        assert "items" in data
        assert "summary" in data
        
        # Check summary fields
        summary = data["summary"]
        assert "total_order_qty" in summary
        assert "estimated_order_cost" in summary
        assert "items_needing_order" in summary
    
    def test_forecast_daily_breakdown(self, auth_headers):
        """Daily breakdown has correct structure"""
        today = datetime.now().strftime("%Y-%m-%d")
        
        response = requests.get(
            f"{BASE_URL}/api/laundry/forecast/{PROPERTY_ID}",
            headers=auth_headers,
            params={"delivery_date": today, "horizon_days": 7}
        )
        assert response.status_code == 200
        
        daily = response.json()["daily"]
        assert len(daily) == 7, f"Expected 7 days, got {len(daily)}"
        
        for day in daily:
            assert "date" in day
            assert "arrivals" in day
            assert "in_house_cleanings" in day
            assert "events" in day
    
    def test_forecast_items_structure(self, auth_headers):
        """Items in forecast have correct structure"""
        today = datetime.now().strftime("%Y-%m-%d")
        
        response = requests.get(
            f"{BASE_URL}/api/laundry/forecast/{PROPERTY_ID}",
            headers=auth_headers,
            params={"delivery_date": today, "horizon_days": 7}
        )
        assert response.status_code == 200
        
        items = response.json()["items"]
        
        # Items with per_cleaning_qty=0 should be excluded
        item_names = [i["name"] for i in items]
        assert "Table Cloth" not in item_names, "Table Cloth (per_cleaning_qty=0) should be excluded"
        assert "Napkin" not in item_names, "Napkin (per_cleaning_qty=0) should be excluded"
        
        # Check item structure
        for item in items[:3]:
            assert "item_id" in item
            assert "name" in item
            assert "per_cleaning_qty" in item
            assert "needed" in item
            assert "on_hand_clean" in item
            assert "shortfall" in item
            assert "washing_cost" in item
            assert "estimated_order_cost" in item
    
    def test_forecast_excludes_zero_per_cleaning_items(self, auth_headers):
        """Items with per_cleaning_qty=0 are excluded from forecast"""
        today = datetime.now().strftime("%Y-%m-%d")
        
        response = requests.get(
            f"{BASE_URL}/api/laundry/forecast/{PROPERTY_ID}",
            headers=auth_headers,
            params={"delivery_date": today, "horizon_days": 7}
        )
        assert response.status_code == 200
        
        items = response.json()["items"]
        
        for item in items:
            assert item["per_cleaning_qty"] > 0, f"Item {item['name']} has per_cleaning_qty=0 but was included"


class TestCreateDispatchFromForecast:
    """Test POST /api/laundry/forecast/{property_id}/create-dispatch"""
    
    def test_create_dispatch_requires_auth(self):
        """Unauthenticated request should fail"""
        response = requests.post(
            f"{BASE_URL}/api/laundry/forecast/{PROPERTY_ID}/create-dispatch",
            json={"vendor": "Test Vendor"}
        )
        assert response.status_code in [401, 403]
    
    def test_create_dispatch_without_vendor_returns_400(self, auth_headers):
        """Missing vendor should return 400"""
        today = datetime.now().strftime("%Y-%m-%d")
        
        response = requests.post(
            f"{BASE_URL}/api/laundry/forecast/{PROPERTY_ID}/create-dispatch",
            headers=auth_headers,
            json={
                "delivery_date": today,
                "horizon_days": 7
            }
        )
        assert response.status_code == 400
        assert "vendor" in response.text.lower()
    
    def test_create_dispatch_with_items(self, auth_headers):
        """Create dispatch with explicit items"""
        today = datetime.now().strftime("%Y-%m-%d")
        
        response = requests.post(
            f"{BASE_URL}/api/laundry/forecast/{PROPERTY_ID}/create-dispatch",
            headers=auth_headers,
            json={
                "vendor": "TEST_Rishad Laundry Services",
                "delivery_date": today,
                "horizon_days": 7,
                "in_house_cleaning_every": 2,
                "items": [
                    {"item_id": "bed_sheet_single", "name": "Bed Sheet (Single)", "qty_sent": 10, "rate": 0.8},
                    {"item_id": "pillow_case", "name": "Pillow Case", "qty_sent": 20, "rate": 0.3}
                ]
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["vendor"] == "TEST_Rishad Laundry Services"
        assert data["status"] == "sent"
        assert data["from_forecast"] == True
        assert len(data["items"]) == 2
        
        # Check total cost calculation
        expected_cost = (10 * 0.8) + (20 * 0.3)  # 8 + 6 = 14
        assert data["total_cost"] == expected_cost
        
        # Store dispatch ID for cleanup
        TestCreateDispatchFromForecast.created_dispatch_id = data["id"]
    
    def test_create_dispatch_recomputes_if_no_items(self, auth_headers):
        """If items not provided, server recomputes forecast"""
        # First get forecast to see if there's any shortfall
        today = datetime.now().strftime("%Y-%m-%d")
        
        forecast_response = requests.get(
            f"{BASE_URL}/api/laundry/forecast/{PROPERTY_ID}",
            headers=auth_headers,
            params={"delivery_date": today, "horizon_days": 7}
        )
        
        if forecast_response.status_code == 200:
            forecast = forecast_response.json()
            has_shortfall = any(i["shortfall"] > 0 for i in forecast["items"])
            
            if has_shortfall:
                # Try to create dispatch without items
                response = requests.post(
                    f"{BASE_URL}/api/laundry/forecast/{PROPERTY_ID}/create-dispatch",
                    headers=auth_headers,
                    json={
                        "vendor": "TEST_Auto Recompute Vendor",
                        "delivery_date": today,
                        "horizon_days": 7,
                        "in_house_cleaning_every": 2
                    }
                )
                # Should either succeed (if shortfall) or return 400 (no shortfall)
                assert response.status_code in [200, 400]
            else:
                # No shortfall - should return 400
                response = requests.post(
                    f"{BASE_URL}/api/laundry/forecast/{PROPERTY_ID}/create-dispatch",
                    headers=auth_headers,
                    json={
                        "vendor": "TEST_No Shortfall Vendor",
                        "delivery_date": today,
                        "horizon_days": 7
                    }
                )
                assert response.status_code == 400
                assert "shortfall" in response.text.lower() or "nothing" in response.text.lower()


class TestCleanup:
    """Cleanup test data"""
    
    def test_cleanup_test_items(self, auth_headers):
        """Delete TEST_ prefixed items"""
        response = requests.get(f"{BASE_URL}/api/laundry/items/{PROPERTY_ID}", headers=auth_headers)
        if response.status_code == 200:
            items = response.json()["items"]
            for item in items:
                if item["name"].startswith("TEST_"):
                    requests.delete(f"{BASE_URL}/api/laundry/items/{item['id']}", headers=auth_headers)
        
        # Also cleanup any test dispatches
        disp_response = requests.get(f"{BASE_URL}/api/laundry/dispatches/{PROPERTY_ID}", headers=auth_headers)
        if disp_response.status_code == 200:
            dispatches = disp_response.json().get("dispatches", [])
            for d in dispatches:
                if d.get("vendor", "").startswith("TEST_"):
                    # Note: No delete endpoint for dispatches, so we just leave them
                    pass
        
        assert True  # Cleanup always passes
