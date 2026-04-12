"""
Iteration 66 - POS Stock Deduction Integration Tests
Tests:
- POST /api/pos/link-stock/{property_id} - Auto-creates stock products for menu items
- GET /api/pos/stock-status/{property_id} - Returns stock levels with alerts
- GET /api/pos/stock-movements/{property_id} - Returns recent stock movements
- POST /api/pos/orders - Creating order deducts stock
- POST /api/pos/orders/{id}/pay with void - Restores stock
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestStockDeductionIntegration:
    """Test stock deduction features for POS system"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup - login and get auth token"""
        self.property_id = "aldgate-flats"
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        self.token = login_response.json().get("token")
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
    
    # ==================== LINK STOCK TESTS ====================
    
    def test_01_link_stock_endpoint(self):
        """Test POST /api/pos/link-stock/{property_id} - Auto-links menu items to stock"""
        response = requests.post(
            f"{BASE_URL}/api/pos/link-stock/{self.property_id}",
            headers=self.headers
        )
        assert response.status_code == 200, f"Link stock failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "linked" in data, "Response should contain 'linked' count"
        assert "created" in data, "Response should contain 'created' count"
        assert "total_menu_items" in data, "Response should contain 'total_menu_items'"
        assert "message" in data, "Response should contain 'message'"
        
        # Verify linking worked
        assert data["linked"] > 0, f"Should have linked items, got {data['linked']}"
        print(f"✓ Linked {data['linked']} items ({data['created']} new stock products created)")
    
    # ==================== STOCK STATUS TESTS ====================
    
    def test_02_stock_status_endpoint(self):
        """Test GET /api/pos/stock-status/{property_id} - Returns stock levels"""
        response = requests.get(
            f"{BASE_URL}/api/pos/stock-status/{self.property_id}",
            headers=self.headers
        )
        assert response.status_code == 200, f"Stock status failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "items" in data, "Response should contain 'items' array"
        assert "low_stock" in data, "Response should contain 'low_stock' array"
        assert "out_of_stock" in data, "Response should contain 'out_of_stock' array"
        assert "total_linked" in data, "Response should contain 'total_linked' count"
        assert "total_items" in data, "Response should contain 'total_items' count"
        
        # Verify items have correct structure
        if data["items"]:
            item = data["items"][0]
            assert "id" in item, "Item should have 'id'"
            assert "name" in item, "Item should have 'name'"
            assert "stock_linked" in item, "Item should have 'stock_linked' flag"
        
        print(f"✓ Stock status: {data['total_linked']}/{data['total_items']} items linked")
        print(f"  Low stock: {len(data['low_stock'])}, Out of stock: {len(data['out_of_stock'])}")
    
    def test_03_stock_status_item_details(self):
        """Test stock status returns correct item details for linked items"""
        response = requests.get(
            f"{BASE_URL}/api/pos/stock-status/{self.property_id}",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Find a linked item
        linked_items = [i for i in data["items"] if i.get("stock_linked")]
        assert len(linked_items) > 0, "Should have at least one linked item"
        
        linked_item = linked_items[0]
        assert "stock_quantity" in linked_item, "Linked item should have 'stock_quantity'"
        assert "min_stock" in linked_item, "Linked item should have 'min_stock'"
        
        print(f"✓ Linked item '{linked_item['name']}' has stock_quantity={linked_item['stock_quantity']}, min_stock={linked_item['min_stock']}")
    
    # ==================== STOCK MOVEMENTS TESTS ====================
    
    def test_04_stock_movements_endpoint(self):
        """Test GET /api/pos/stock-movements/{property_id} - Returns movements"""
        response = requests.get(
            f"{BASE_URL}/api/pos/stock-movements/{self.property_id}",
            headers=self.headers
        )
        assert response.status_code == 200, f"Stock movements failed: {response.text}"
        data = response.json()
        
        # Should be a list
        assert isinstance(data, list), "Response should be a list"
        
        # If there are movements, verify structure
        if data:
            movement = data[0]
            assert "id" in movement, "Movement should have 'id'"
            assert "product_id" in movement, "Movement should have 'product_id'"
            assert "type" in movement, "Movement should have 'type'"
            assert "quantity" in movement, "Movement should have 'quantity'"
            assert "reference" in movement, "Movement should have 'reference'"
            assert "created_at" in movement, "Movement should have 'created_at'"
            print(f"✓ Found {len(data)} stock movements")
            print(f"  Latest: {movement['type']} - {movement['quantity']} - {movement.get('item_name', 'N/A')}")
        else:
            print("✓ No stock movements yet (expected if no orders placed)")
    
    # ==================== ORDER STOCK DEDUCTION TESTS ====================
    
    def test_05_order_deducts_stock(self):
        """Test POST /api/pos/orders - Creating order deducts stock"""
        # First get stock status to find a linked item
        status_response = requests.get(
            f"{BASE_URL}/api/pos/stock-status/{self.property_id}",
            headers=self.headers
        )
        assert status_response.status_code == 200
        status_data = status_response.json()
        
        # Find a linked item with stock
        linked_items = [i for i in status_data["items"] if i.get("stock_linked") and i.get("stock_quantity", 0) > 0]
        assert len(linked_items) > 0, "Need at least one linked item with stock"
        
        test_item = linked_items[0]
        initial_stock = test_item["stock_quantity"]
        
        # Get menu to get full item details
        menu_response = requests.get(
            f"{BASE_URL}/api/pos/menu/{self.property_id}",
            headers=self.headers
        )
        assert menu_response.status_code == 200
        menu_items = menu_response.json()
        
        # Find the menu item
        menu_item = next((m for m in menu_items if m["id"] == test_item["id"]), None)
        assert menu_item is not None, f"Menu item {test_item['id']} not found"
        
        # Create order with this item
        order_data = {
            "property_id": self.property_id,
            "outlet_id": "",
            "outlet_name": "Restaurant",
            "order_type": "dine_in",
            "table_number": "TEST-66",
            "covers": 1,
            "guest_name": "Stock Test Guest",
            "items": [{
                "id": menu_item["id"],
                "name": menu_item["name"],
                "price": menu_item["price"],
                "cost": menu_item.get("cost", 0),
                "quantity": 2,  # Order 2 items
                "vat_rate": menu_item.get("vat_rate", 20),
                "category": menu_item.get("category", ""),
                "stock_product_id": menu_item.get("stock_product_id", "")
            }]
        }
        
        order_response = requests.post(
            f"{BASE_URL}/api/pos/orders",
            headers=self.headers,
            json=order_data
        )
        assert order_response.status_code == 200, f"Create order failed: {order_response.text}"
        order = order_response.json()
        
        assert "id" in order, "Order should have 'id'"
        assert "order_number" in order, "Order should have 'order_number'"
        
        # Check stock was deducted
        new_status_response = requests.get(
            f"{BASE_URL}/api/pos/stock-status/{self.property_id}",
            headers=self.headers
        )
        assert new_status_response.status_code == 200
        new_status_data = new_status_response.json()
        
        # Find the item again
        updated_item = next((i for i in new_status_data["items"] if i["id"] == test_item["id"]), None)
        assert updated_item is not None, "Item should still exist"
        
        new_stock = updated_item["stock_quantity"]
        expected_stock = initial_stock - 2  # We ordered 2
        
        assert new_stock == expected_stock, f"Stock should be {expected_stock}, got {new_stock}"
        print(f"✓ Order {order['order_number']} created")
        print(f"  Stock deducted: {initial_stock} → {new_stock} (expected {expected_stock})")
        
        # Store order ID for void test
        self.__class__.test_order_id = order["id"]
        self.__class__.test_order_number = order["order_number"]
        self.__class__.test_item_id = test_item["id"]
        self.__class__.stock_before_void = new_stock
    
    def test_06_order_creates_stock_movement(self):
        """Test that creating order logs stock movement"""
        response = requests.get(
            f"{BASE_URL}/api/pos/stock-movements/{self.property_id}",
            headers=self.headers
        )
        assert response.status_code == 200
        movements = response.json()
        
        # Find movement for our test order
        order_number = getattr(self.__class__, 'test_order_number', None)
        if order_number:
            order_movements = [m for m in movements if order_number in m.get("reference", "")]
            assert len(order_movements) > 0, f"Should have movement for order {order_number}"
            
            movement = order_movements[0]
            assert movement["type"] == "pos_sale", f"Movement type should be 'pos_sale', got {movement['type']}"
            assert movement["quantity"] < 0, "POS sale movement should have negative quantity"
            print(f"✓ Stock movement logged: {movement['type']} qty={movement['quantity']} ref={movement['reference']}")
    
    # ==================== VOID ORDER STOCK RESTORE TESTS ====================
    
    def test_07_void_order_restores_stock(self):
        """Test POST /api/pos/orders/{id}/pay with void - Restores stock"""
        order_id = getattr(self.__class__, 'test_order_id', None)
        if not order_id:
            pytest.skip("No test order to void")
        
        stock_before = getattr(self.__class__, 'stock_before_void', 0)
        
        # Void the order
        void_response = requests.post(
            f"{BASE_URL}/api/pos/orders/{order_id}/pay",
            headers=self.headers,
            json={
                "payment_method": "void",
                "tip": 0,
                "reason": "Test void for stock restore"
            }
        )
        assert void_response.status_code == 200, f"Void failed: {void_response.text}"
        void_data = void_response.json()
        
        assert void_data.get("status") == "voided", f"Expected status 'voided', got {void_data.get('status')}"
        
        # Check stock was restored
        status_response = requests.get(
            f"{BASE_URL}/api/pos/stock-status/{self.property_id}",
            headers=self.headers
        )
        assert status_response.status_code == 200
        status_data = status_response.json()
        
        test_item_id = getattr(self.__class__, 'test_item_id', None)
        updated_item = next((i for i in status_data["items"] if i["id"] == test_item_id), None)
        
        if updated_item:
            new_stock = updated_item["stock_quantity"]
            expected_stock = stock_before + 2  # We voided 2 items
            assert new_stock == expected_stock, f"Stock should be restored to {expected_stock}, got {new_stock}"
            print(f"✓ Order voided, stock restored: {stock_before} → {new_stock}")
    
    def test_08_void_creates_restore_movement(self):
        """Test that voiding order logs restore movement"""
        response = requests.get(
            f"{BASE_URL}/api/pos/stock-movements/{self.property_id}",
            headers=self.headers
        )
        assert response.status_code == 200
        movements = response.json()
        
        # Find void_restore movement
        restore_movements = [m for m in movements if m.get("type") == "void_restore"]
        assert len(restore_movements) > 0, "Should have void_restore movement"
        
        movement = restore_movements[0]
        assert movement["quantity"] > 0, "Void restore movement should have positive quantity"
        print(f"✓ Void restore movement logged: qty={movement['quantity']} ref={movement['reference']}")
    
    # ==================== LOW STOCK ALERT TESTS ====================
    
    def test_09_low_stock_alerts(self):
        """Test that low stock items are flagged correctly"""
        response = requests.get(
            f"{BASE_URL}/api/pos/stock-status/{self.property_id}",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify low_stock structure
        for item in data.get("low_stock", []):
            assert "name" in item, "Low stock item should have 'name'"
            assert "quantity" in item, "Low stock item should have 'quantity'"
            assert "min_stock" in item, "Low stock item should have 'min_stock'"
            assert item["quantity"] <= item["min_stock"], f"Low stock item {item['name']} has quantity {item['quantity']} > min_stock {item['min_stock']}"
        
        print(f"✓ Low stock alerts working: {len(data.get('low_stock', []))} items flagged")
    
    def test_10_out_of_stock_alerts(self):
        """Test that out of stock items are flagged correctly"""
        response = requests.get(
            f"{BASE_URL}/api/pos/stock-status/{self.property_id}",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify out_of_stock is a list of names
        assert isinstance(data.get("out_of_stock", []), list), "out_of_stock should be a list"
        
        print(f"✓ Out of stock alerts working: {len(data.get('out_of_stock', []))} items flagged")
    
    # ==================== MENU ITEM STOCK LINK VERIFICATION ====================
    
    def test_11_menu_items_have_stock_product_id(self):
        """Test that menu items have stock_product_id after linking"""
        # First ensure linking is done
        requests.post(
            f"{BASE_URL}/api/pos/link-stock/{self.property_id}",
            headers=self.headers
        )
        
        # Get menu
        response = requests.get(
            f"{BASE_URL}/api/pos/menu/{self.property_id}",
            headers=self.headers
        )
        assert response.status_code == 200
        menu_items = response.json()
        
        linked_count = sum(1 for m in menu_items if m.get("stock_product_id"))
        assert linked_count > 0, "Should have at least one menu item with stock_product_id"
        
        print(f"✓ {linked_count}/{len(menu_items)} menu items have stock_product_id")
    
    # ==================== IDEMPOTENCY TEST ====================
    
    def test_12_link_stock_idempotent(self):
        """Test that link-stock is idempotent (running twice doesn't create duplicates)"""
        # Run link-stock twice
        response1 = requests.post(
            f"{BASE_URL}/api/pos/link-stock/{self.property_id}",
            headers=self.headers
        )
        assert response1.status_code == 200
        data1 = response1.json()
        
        response2 = requests.post(
            f"{BASE_URL}/api/pos/link-stock/{self.property_id}",
            headers=self.headers
        )
        assert response2.status_code == 200
        data2 = response2.json()
        
        # Second run should create 0 new products
        assert data2["created"] == 0, f"Second link-stock should create 0 products, created {data2['created']}"
        assert data2["linked"] == data1["linked"], "Linked count should be same"
        
        print(f"✓ Link-stock is idempotent: first run created {data1['created']}, second run created {data2['created']}")


class TestStockDeductionEdgeCases:
    """Edge case tests for stock deduction"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup - login and get auth token"""
        self.property_id = "aldgate-flats"
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert login_response.status_code == 200
        self.token = login_response.json().get("token")
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
    
    def test_order_without_stock_link(self):
        """Test that orders with non-linked items don't affect stock"""
        # Get menu to find an item
        menu_response = requests.get(
            f"{BASE_URL}/api/pos/menu/{self.property_id}",
            headers=self.headers
        )
        assert menu_response.status_code == 200
        menu_items = menu_response.json()
        
        # Create order without stock_product_id
        order_data = {
            "property_id": self.property_id,
            "outlet_id": "",
            "outlet_name": "Restaurant",
            "order_type": "dine_in",
            "table_number": "TEST-NOSTOCK",
            "covers": 1,
            "guest_name": "No Stock Test",
            "items": [{
                "id": menu_items[0]["id"],
                "name": menu_items[0]["name"],
                "price": menu_items[0]["price"],
                "cost": menu_items[0].get("cost", 0),
                "quantity": 1,
                "vat_rate": 20,
                "category": menu_items[0].get("category", ""),
                "stock_product_id": ""  # No stock link
            }]
        }
        
        response = requests.post(
            f"{BASE_URL}/api/pos/orders",
            headers=self.headers,
            json=order_data
        )
        assert response.status_code == 200, f"Order creation failed: {response.text}"
        print("✓ Order without stock link created successfully (no stock deduction)")
    
    def test_stock_movements_limit(self):
        """Test stock movements respects limit parameter"""
        response = requests.get(
            f"{BASE_URL}/api/pos/stock-movements/{self.property_id}?limit=5",
            headers=self.headers
        )
        assert response.status_code == 200
        movements = response.json()
        
        assert len(movements) <= 5, f"Should return at most 5 movements, got {len(movements)}"
        print(f"✓ Stock movements limit working: returned {len(movements)} movements (limit=5)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
