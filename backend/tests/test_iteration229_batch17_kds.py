"""
Batch 17 - Kitchen Display System (KDS) + 86 List + Recipe Inventory Tests
Tests: KDS stream, station filtering, bump workflow, 86 list toggle, recipe CRUD
"""
import pytest
import requests
import os
from datetime import datetime, timezone, timedelta
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestBatch17KDS:
    """Kitchen Display System + 86 List + Recipe Inventory tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login as admin
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        token = login_resp.json().get("access_token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        self.property_id = "default"
        yield
    
    # ========== KDS Stream Tests ==========
    
    def test_kds_stream_default(self):
        """GET /api/kds/default → 200, orders[], by_station{}, counters{}, oldest_age_minutes"""
        resp = self.session.get(f"{BASE_URL}/api/kds/{self.property_id}")
        assert resp.status_code == 200, f"KDS stream failed: {resp.text}"
        data = resp.json()
        
        # Verify response structure
        assert "orders" in data, "Missing orders[] in response"
        assert "by_station" in data, "Missing by_station{} in response"
        assert "counters" in data, "Missing counters{} in response"
        assert "oldest_age_minutes" in data, "Missing oldest_age_minutes in response"
        
        # Verify counters structure
        counters = data["counters"]
        assert "new" in counters, "Missing 'new' counter"
        assert "preparing" in counters, "Missing 'preparing' counter"
        assert "ready" in counters, "Missing 'ready' counter"
        
        print(f"✓ KDS stream: {len(data['orders'])} orders, counters={counters}")
    
    def test_kds_stream_station_filter(self):
        """GET /api/kds/default?station=hot → 200, filtered to hot station only"""
        resp = self.session.get(f"{BASE_URL}/api/kds/{self.property_id}?station=hot")
        assert resp.status_code == 200, f"KDS station filter failed: {resp.text}"
        data = resp.json()
        
        # Verify response structure
        assert "orders" in data
        assert "by_station" in data
        
        print(f"✓ KDS station filter (hot): {len(data['orders'])} orders")
    
    def test_kds_order_age_color(self):
        """Verify orders have age_color (green/amber/red) based on age"""
        resp = self.session.get(f"{BASE_URL}/api/kds/{self.property_id}")
        assert resp.status_code == 200
        data = resp.json()
        
        for order in data.get("orders", []):
            assert "age_minutes" in order, f"Order {order.get('id')} missing age_minutes"
            assert "age_color" in order, f"Order {order.get('id')} missing age_color"
            assert order["age_color"] in ["green", "amber", "red"], f"Invalid age_color: {order['age_color']}"
        
        print(f"✓ All {len(data['orders'])} orders have valid age_color")
    
    def test_kds_by_station_grouping(self):
        """Verify by_station groups items correctly"""
        resp = self.session.get(f"{BASE_URL}/api/kds/{self.property_id}")
        assert resp.status_code == 200
        data = resp.json()
        
        by_station = data.get("by_station", {})
        for station, items in by_station.items():
            assert isinstance(items, list), f"Station {station} items should be a list"
            for item in items:
                assert "order_id" in item, f"Item missing order_id"
                assert "name" in item, f"Item missing name"
                assert "age_color" in item, f"Item missing age_color"
        
        print(f"✓ by_station grouping: {list(by_station.keys())}")
    
    # ========== KDS Bump Tests ==========
    
    def test_kds_bump_invalid_status(self):
        """POST /api/kds/bump with invalid next_status → 400"""
        resp = self.session.post(f"{BASE_URL}/api/kds/bump", json={
            "order_id": "test-order-123",
            "next_status": "invalid_status"
        })
        assert resp.status_code == 400, f"Expected 400 for invalid status, got {resp.status_code}"
        print("✓ KDS bump rejects invalid status with 400")
    
    def test_kds_bump_invalid_order(self):
        """POST /api/kds/bump with invalid order_id → 404"""
        resp = self.session.post(f"{BASE_URL}/api/kds/bump", json={
            "order_id": "nonexistent-order-id",
            "next_status": "preparing"
        })
        assert resp.status_code == 404, f"Expected 404 for invalid order, got {resp.status_code}"
        print("✓ KDS bump returns 404 for nonexistent order")
    
    # ========== 86 List Tests ==========
    
    def test_86_list_get(self):
        """GET /api/86-list/default → 200, items[], count"""
        resp = self.session.get(f"{BASE_URL}/api/86-list/{self.property_id}")
        assert resp.status_code == 200, f"86 list GET failed: {resp.text}"
        data = resp.json()
        
        assert "items" in data, "Missing items[] in response"
        assert "count" in data, "Missing count in response"
        assert data["count"] == len(data["items"]), "Count mismatch"
        
        print(f"✓ 86 list: {data['count']} items currently on 86")
    
    def test_86_toggle_invalid_item(self):
        """POST /api/86-list/toggle with invalid menu_item_id → 404"""
        resp = self.session.post(f"{BASE_URL}/api/86-list/toggle", json={
            "menu_item_id": "nonexistent-menu-item",
            "on_86": True,
            "reason": "Test reason"
        })
        assert resp.status_code == 404, f"Expected 404 for invalid menu item, got {resp.status_code}"
        print("✓ 86 toggle returns 404 for nonexistent menu item")
    
    def test_86_toggle_workflow(self):
        """Test 86 toggle on/off workflow with valid menu item"""
        # First get a valid menu item from pos_menu_items
        menu_resp = self.session.get(f"{BASE_URL}/api/pos/menu/{self.property_id}")
        if menu_resp.status_code != 200:
            pytest.skip("No POS menu items available for 86 toggle test")
        
        menu_data = menu_resp.json()
        items = menu_data.get("items", menu_data) if isinstance(menu_data, dict) else menu_data
        if not items or len(items) == 0:
            pytest.skip("No menu items available for 86 toggle test")
        
        test_item = items[0]
        item_id = test_item.get("id")
        
        # Toggle ON
        resp_on = self.session.post(f"{BASE_URL}/api/86-list/toggle", json={
            "menu_item_id": item_id,
            "on_86": True,
            "reason": "Test - out of stock"
        })
        assert resp_on.status_code == 200, f"86 toggle ON failed: {resp_on.text}"
        data_on = resp_on.json()
        assert data_on.get("on_86") == True, "Expected on_86=True after toggle ON"
        
        # Verify item appears in 86 list
        list_resp = self.session.get(f"{BASE_URL}/api/86-list/{self.property_id}")
        assert list_resp.status_code == 200
        list_data = list_resp.json()
        item_ids_on_86 = [i.get("id") for i in list_data.get("items", [])]
        assert item_id in item_ids_on_86, "Item should appear in 86 list after toggle ON"
        
        # Toggle OFF
        resp_off = self.session.post(f"{BASE_URL}/api/86-list/toggle", json={
            "menu_item_id": item_id,
            "on_86": False
        })
        assert resp_off.status_code == 200, f"86 toggle OFF failed: {resp_off.text}"
        data_off = resp_off.json()
        assert data_off.get("on_86") == False, "Expected on_86=False after toggle OFF"
        
        print(f"✓ 86 toggle workflow: ON → verified in list → OFF for item {item_id}")
    
    # ========== Recipe Tests ==========
    
    def test_recipe_get_nonexistent(self):
        """GET /api/recipes/{menu_item_id} for nonexistent → 200 with empty components"""
        resp = self.session.get(f"{BASE_URL}/api/recipes/nonexistent-item")
        assert resp.status_code == 200, f"Recipe GET failed: {resp.text}"
        data = resp.json()
        
        assert "menu_item_id" in data, "Missing menu_item_id in response"
        assert "components" in data, "Missing components in response"
        assert data["components"] == [], "Expected empty components for nonexistent recipe"
        
        print("✓ Recipe GET returns empty components for nonexistent item")
    
    def test_recipe_upsert(self):
        """POST /api/recipes upsert with components[] → 200, component_count"""
        test_menu_item_id = f"test-recipe-item-{uuid.uuid4().hex[:8]}"
        
        # Create recipe with components
        resp = self.session.post(f"{BASE_URL}/api/recipes", json={
            "menu_item_id": test_menu_item_id,
            "components": [
                {"stock_item_id": "stock-1", "qty": 2, "unit": "adet"},
                {"stock_item_id": "stock-2", "qty": 0.5, "unit": "kg"}
            ]
        })
        assert resp.status_code == 200, f"Recipe upsert failed: {resp.text}"
        data = resp.json()
        
        assert "menu_item_id" in data, "Missing menu_item_id in response"
        assert "component_count" in data, "Missing component_count in response"
        assert data["component_count"] == 2, f"Expected 2 components, got {data['component_count']}"
        
        # Verify recipe was saved
        get_resp = self.session.get(f"{BASE_URL}/api/recipes/{test_menu_item_id}")
        assert get_resp.status_code == 200
        get_data = get_resp.json()
        assert len(get_data.get("components", [])) == 2, "Recipe components not persisted"
        
        print(f"✓ Recipe upsert: created recipe with 2 components for {test_menu_item_id}")
    
    def test_recipe_property_list(self):
        """GET /api/recipes/property/default → 200, rows[], total, with_recipe"""
        resp = self.session.get(f"{BASE_URL}/api/recipes/property/{self.property_id}")
        assert resp.status_code == 200, f"Recipe property list failed: {resp.text}"
        data = resp.json()
        
        assert "rows" in data, "Missing rows[] in response"
        assert "total" in data, "Missing total in response"
        assert "with_recipe" in data, "Missing with_recipe in response"
        
        # Verify row structure
        for row in data.get("rows", [])[:5]:  # Check first 5
            assert "menu_item_id" in row, "Row missing menu_item_id"
            assert "menu_item_name" in row, "Row missing menu_item_name"
            assert "has_recipe" in row, "Row missing has_recipe"
            assert "component_count" in row, "Row missing component_count"
        
        print(f"✓ Recipe property list: {data['total']} items, {data['with_recipe']} with recipes")
    
    # ========== Regression Tests ==========
    
    def test_regression_auth_login(self):
        """Regression: Auth login still works"""
        resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert resp.status_code == 200, f"Auth login regression failed: {resp.text}"
        print("✓ Regression: Auth login working")
    
    def test_regression_batch16_channel_revenue(self):
        """Regression: Batch 16 channel revenue endpoints still work"""
        resp = self.session.get(f"{BASE_URL}/api/channel-revenue/channels/{self.property_id}")
        assert resp.status_code == 200, f"Channel revenue regression failed: {resp.text}"
        data = resp.json()
        assert "channels" in data, "Missing channels in response"
        print(f"✓ Regression: Batch 16 channel revenue working ({len(data['channels'])} channels)")
    
    def test_regression_batch15_eu_compliance(self):
        """Regression: Batch 15 EU compliance endpoints still work"""
        resp = self.session.get(f"{BASE_URL}/api/eu-compliance/catalog")
        assert resp.status_code == 200, f"EU compliance regression failed: {resp.text}"
        print("✓ Regression: Batch 15 EU compliance working")
    
    def test_regression_batch14_ai_predictions(self):
        """Regression: Batch 14 AI predictions endpoints still work"""
        resp = self.session.get(f"{BASE_URL}/api/ai-predictions/cancel-risk/{self.property_id}")
        assert resp.status_code == 200, f"AI predictions regression failed: {resp.text}"
        print("✓ Regression: Batch 14 AI predictions working")
    
    def test_regression_batch13_tr_compliance(self):
        """Regression: Batch 13 TR compliance endpoints still work"""
        resp = self.session.get(f"{BASE_URL}/api/tr-compliance/kbs/{self.property_id}/history")
        assert resp.status_code == 200, f"TR compliance regression failed: {resp.text}"
        print("✓ Regression: Batch 13 TR compliance working")
    
    def test_regression_enhanced_dashboard(self):
        """Regression: Enhanced dashboard endpoint still works"""
        resp = self.session.get(f"{BASE_URL}/api/dashboard/enhanced/{self.property_id}")
        assert resp.status_code == 200, f"Enhanced dashboard regression failed: {resp.text}"
        print("✓ Regression: Enhanced dashboard working")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
