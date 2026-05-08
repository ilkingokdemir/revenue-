"""
Iteration 48 - Hotel Stock Management Upgrade Testing
9 new Apicbase-level features:
1. Menu Engineering (Stars/Puzzles/Plowhorses/Dogs)
2. Food Cost % Dashboard
3. Par Level Auto-Ordering
4. Allergen & Nutrition Tracking
5. Supplier Price History
6. Yield Management
7. Perishable Forecasting (FIFO)
8. Multi-Outlet Transfers
9. Inventory Turnover Rate
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
PROPERTY_ID = "city-gate"

def get_auth_headers():
    """Get authentication headers"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@hotelbox.com",
        "password": "HotelAdmin2026!"
    })
    if response.status_code != 200:
        pytest.skip(f"Login failed: {response.text}")
    data = response.json()
    token = data.get("token")  # Note: field is 'token', not 'access_token'
    if not token:
        pytest.skip("No token in login response")
    return {"Authorization": f"Bearer {token}"}


class TestAuth:
    """Authentication tests"""
    
    def test_login_success(self):
        """Test admin login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "token" in data, "No token in response"
        assert "email" in data, "No email in response"
        assert data["email"] == "admin@hotelbox.com"
        print(f"✓ Login successful, token obtained")


class TestMenuEngineering:
    """Menu Engineering - Stars/Puzzles/Plowhorses/Dogs classification"""
    
    def test_menu_engineering_endpoint(self):
        """GET /api/stock/menu-engineering/{property_id} - profitability matrix"""
        headers = get_auth_headers()
        response = requests.get(f"{BASE_URL}/api/stock/menu-engineering/{PROPERTY_ID}", headers=headers)
        assert response.status_code == 200, f"Menu engineering failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "recipes" in data, "Missing 'recipes' in response"
        assert "summary" in data, "Missing 'summary' in response"
        
        # If recipes exist, verify classification
        if data["recipes"]:
            recipe = data["recipes"][0]
            assert "menu_class" in recipe, "Missing menu_class in recipe"
            assert recipe["menu_class"] in ["star", "puzzle", "plowhorse", "dog"], f"Invalid menu_class: {recipe['menu_class']}"
            assert "contribution" in recipe, "Missing contribution in recipe"
        
        # Verify summary structure
        summary = data.get("summary", {})
        if summary:
            assert "stars" in summary or "avg_margin" in summary, "Summary missing expected fields"
        
        print(f"✓ Menu Engineering: {len(data['recipes'])} recipes classified")
        print(f"  Summary: {data.get('summary', {})}")


class TestFoodCostDashboard:
    """Food Cost % Dashboard with COGS formula"""
    
    def test_food_cost_dashboard(self):
        """GET /api/stock/food-cost-dashboard/{property_id} - real-time food cost %"""
        headers = get_auth_headers()
        response = requests.get(f"{BASE_URL}/api/stock/food-cost-dashboard/{PROPERTY_ID}", headers=headers)
        assert response.status_code == 200, f"Food cost dashboard failed: {response.text}"
        data = response.json()
        
        # Verify COGS formula fields
        assert "food_cost_pct" in data, "Missing food_cost_pct"
        assert "target_range" in data, "Missing target_range"
        assert "cogs" in data, "Missing cogs"
        assert "revenue" in data, "Missing revenue"
        assert "status" in data, "Missing status"
        
        # Verify target range (28-35%)
        target = data["target_range"]
        assert target.get("min") == 28, f"Expected target min 28, got {target.get('min')}"
        assert target.get("max") == 35, f"Expected target max 35, got {target.get('max')}"
        
        # Verify status is valid
        assert data["status"] in ["on_target", "high", "low"], f"Invalid status: {data['status']}"
        
        print(f"✓ Food Cost Dashboard: {data['food_cost_pct']}% (target: {target['min']}-{target['max']}%)")
        print(f"  Status: {data['status']}, COGS: £{data['cogs']}, Revenue: £{data['revenue']}")


class TestAutoOrdering:
    """Par Level Auto-Ordering"""
    
    def test_auto_order_generation(self):
        """POST /api/stock/auto-order/{property_id} - auto-generate POs from par levels"""
        headers = get_auth_headers()
        response = requests.post(f"{BASE_URL}/api/stock/auto-order/{PROPERTY_ID}", headers=headers)
        assert response.status_code == 200, f"Auto-order failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "message" in data, "Missing message in response"
        assert "orders" in data, "Missing orders in response"
        
        # Orders should be a list
        assert isinstance(data["orders"], list), "Orders should be a list"
        
        # If orders were created, verify structure
        if data["orders"]:
            order = data["orders"][0]
            assert "supplier" in order, "Missing supplier in order"
            assert "items" in order, "Missing items count in order"
            assert "total" in order, "Missing total in order"
        
        print(f"✓ Auto-Order: {data['message']}")
        print(f"  Orders created: {len(data['orders'])}")


class TestAllergenTracking:
    """Allergen & Nutrition Tracking"""
    
    def test_allergen_report(self):
        """GET /api/stock/allergens/{property_id} - allergen report per recipe"""
        headers = get_auth_headers()
        response = requests.get(f"{BASE_URL}/api/stock/allergens/{PROPERTY_ID}", headers=headers)
        assert response.status_code == 200, f"Allergen report failed: {response.text}"
        data = response.json()
        
        # Should return a list
        assert isinstance(data, list), "Allergen report should return a list"
        
        # If recipes exist, verify structure
        if data:
            recipe = data[0]
            assert "recipe_id" in recipe, "Missing recipe_id"
            assert "name" in recipe, "Missing name"
            assert "allergens" in recipe, "Missing allergens"
            assert isinstance(recipe["allergens"], list), "Allergens should be a list"
        
        print(f"✓ Allergen Report: {len(data)} recipes with allergen info")


class TestPriceHistory:
    """Supplier Price History"""
    
    def test_price_history_get(self):
        """GET /api/stock/price-history/{product_id} - supplier price history"""
        headers = get_auth_headers()
        
        # First get a product ID
        products_resp = requests.get(f"{BASE_URL}/api/stock/products/{PROPERTY_ID}", headers=headers)
        if products_resp.status_code != 200 or not products_resp.json():
            pytest.skip("No products available for price history test")
        
        product_id = products_resp.json()[0]["id"]
        
        response = requests.get(f"{BASE_URL}/api/stock/price-history/{product_id}", headers=headers)
        assert response.status_code == 200, f"Price history failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "product" in data, "Missing product name"
        assert "current_price" in data, "Missing current_price"
        assert "price_history" in data, "Missing price_history"
        assert "purchase_prices" in data, "Missing purchase_prices"
        
        print(f"✓ Price History for '{data['product']}': current £{data['current_price']}")
        print(f"  History entries: {len(data['price_history'])}, Purchase records: {len(data['purchase_prices'])}")
    
    def test_price_update(self):
        """POST /api/stock/price-update/{product_id} - update price with history log"""
        headers = get_auth_headers()
        
        # First get a product ID
        products_resp = requests.get(f"{BASE_URL}/api/stock/products/{PROPERTY_ID}", headers=headers)
        if products_resp.status_code != 200 or not products_resp.json():
            pytest.skip("No products available for price update test")
        
        product_id = products_resp.json()[0]["id"]
        
        new_price = 6.50
        response = requests.post(f"{BASE_URL}/api/stock/price-update/{product_id}", headers=headers, json={
            "cost_price": new_price,
            "supplier": "Test Supplier"
        })
        assert response.status_code == 200, f"Price update failed: {response.text}"
        data = response.json()
        
        # Verify response
        assert "product" in data, "Missing product name"
        assert "old_price" in data, "Missing old_price"
        assert "new_price" in data, "Missing new_price"
        assert data["new_price"] == new_price, f"New price mismatch: expected {new_price}, got {data['new_price']}"
        
        print(f"✓ Price Update: {data['product']} £{data['old_price']} → £{data['new_price']} ({data.get('change_pct', 0)}%)")


class TestYieldManagement:
    """Yield Management - ingredient yield tracking"""
    
    def test_yield_analysis(self):
        """GET /api/stock/yield-analysis/{property_id} - ingredient yield tracking"""
        headers = get_auth_headers()
        response = requests.get(f"{BASE_URL}/api/stock/yield-analysis/{PROPERTY_ID}", headers=headers)
        assert response.status_code == 200, f"Yield analysis failed: {response.text}"
        data = response.json()
        
        # Should return a list
        assert isinstance(data, list), "Yield analysis should return a list"
        
        # If products with yield exist, verify structure
        if data:
            product = data[0]
            assert "product_id" in product, "Missing product_id"
            assert "name" in product, "Missing name"
            assert "yield_pct" in product, "Missing yield_pct"
            assert "raw_cost_per_unit" in product, "Missing raw_cost_per_unit"
            assert "effective_cost_per_unit" in product, "Missing effective_cost_per_unit"
            assert "waste_pct" in product, "Missing waste_pct"
        
        print(f"✓ Yield Analysis: {len(data)} products with yield tracking")


class TestPerishableAlerts:
    """Perishable Forecasting (FIFO) - expiry alerts"""
    
    def test_perishable_alerts(self):
        """GET /api/stock/perishable-alerts/{property_id} - FIFO expiry alerts"""
        headers = get_auth_headers()
        response = requests.get(f"{BASE_URL}/api/stock/perishable-alerts/{PROPERTY_ID}", headers=headers)
        assert response.status_code == 200, f"Perishable alerts failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "alerts" in data, "Missing alerts"
        assert "total_at_risk_value" in data, "Missing total_at_risk_value"
        assert "count" in data, "Missing count"
        
        # Alerts should be a list
        assert isinstance(data["alerts"], list), "Alerts should be a list"
        
        # If alerts exist, verify structure
        if data["alerts"]:
            alert = data["alerts"][0]
            assert "product_id" in alert, "Missing product_id"
            assert "name" in alert, "Missing name"
            assert "days_remaining" in alert, "Missing days_remaining"
            assert "status" in alert, "Missing status"
            assert alert["status"] in ["expired", "critical", "warning", "ok"], f"Invalid status: {alert['status']}"
        
        print(f"✓ Perishable Alerts: {data['count']} alerts, £{data['total_at_risk_value']} at risk")


class TestMultiOutletTransfer:
    """Multi-Outlet Transfers"""
    
    def test_stock_transfer(self):
        """POST /api/stock/transfer - multi-outlet stock transfer"""
        headers = get_auth_headers()
        
        # First get a product ID
        products_resp = requests.get(f"{BASE_URL}/api/stock/products/{PROPERTY_ID}", headers=headers)
        if products_resp.status_code != 200 or not products_resp.json():
            pytest.skip("No products available for transfer test")
        
        product_id = products_resp.json()[0]["id"]
        
        response = requests.post(f"{BASE_URL}/api/stock/transfer", headers=headers, json={
            "property_id": PROPERTY_ID,
            "product_id": product_id,
            "from_outlet": "Kitchen Store",
            "to_outlet": "Main Restaurant",
            "quantity": 2
        })
        assert response.status_code == 200, f"Transfer failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "status" in data, "Missing status"
        assert data["status"] == "transferred", f"Expected status 'transferred', got '{data['status']}'"
        assert "product" in data, "Missing product"
        assert "quantity" in data, "Missing quantity"
        assert "from" in data, "Missing from outlet"
        assert "to" in data, "Missing to outlet"
        assert "cost" in data, "Missing cost"
        
        print(f"✓ Transfer: {data['product']} x{data['quantity']} from '{data['from']}' to '{data['to']}' (£{data['cost']})")


class TestInventoryTurnover:
    """Inventory Turnover Rate"""
    
    def test_turnover_rate(self):
        """GET /api/stock/turnover-rate/{property_id} - inventory turnover calculation"""
        headers = get_auth_headers()
        response = requests.get(f"{BASE_URL}/api/stock/turnover-rate/{PROPERTY_ID}", headers=headers)
        assert response.status_code == 200, f"Turnover rate failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "turnover_rate" in data, "Missing turnover_rate"
        assert "monthly_turnover" in data, "Missing monthly_turnover"
        assert "target" in data, "Missing target"
        assert "status" in data, "Missing status"
        assert "cogs" in data, "Missing cogs"
        assert "avg_inventory_value" in data, "Missing avg_inventory_value"
        
        # Verify target range (4-8x monthly)
        target = data["target"]
        assert target.get("min") == 4, f"Expected target min 4, got {target.get('min')}"
        assert target.get("max") == 8, f"Expected target max 8, got {target.get('max')}"
        
        # Verify status is valid
        assert data["status"] in ["optimal", "slow", "fast"], f"Invalid status: {data['status']}"
        
        # Verify slow movers info
        assert "slow_movers_count" in data, "Missing slow_movers_count"
        assert "slow_movers_value" in data, "Missing slow_movers_value"
        
        print(f"✓ Turnover Rate: {data['monthly_turnover']}x monthly (target: {target['min']}-{target['max']}x)")
        print(f"  Status: {data['status']}, COGS: £{data['cogs']}, Avg Inventory: £{data['avg_inventory_value']}")
        print(f"  Slow movers: {data['slow_movers_count']} (£{data['slow_movers_value']})")


class TestWasteTracking:
    """Waste Tracking with Reason Codes"""
    
    def test_record_waste(self):
        """POST /api/stock/waste - record waste with reason code"""
        headers = get_auth_headers()
        
        # First get a product ID
        products_resp = requests.get(f"{BASE_URL}/api/stock/products/{PROPERTY_ID}", headers=headers)
        if products_resp.status_code != 200 or not products_resp.json():
            pytest.skip("No products available for waste test")
        
        product_id = products_resp.json()[0]["id"]
        
        response = requests.post(f"{BASE_URL}/api/stock/waste", headers=headers, json={
            "property_id": PROPERTY_ID,
            "product_id": product_id,
            "quantity": 0.5,
            "reason": "expired",
            "notes": "Test waste entry"
        })
        assert response.status_code == 200, f"Record waste failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "id" in data, "Missing id"
        assert "movement_type" in data, "Missing movement_type"
        assert data["movement_type"] == "waste", f"Expected movement_type 'waste', got '{data['movement_type']}'"
        assert "quantity" in data, "Missing quantity"
        assert "cost" in data, "Missing cost"
        
        print(f"✓ Waste Recorded: {data.get('product_name', 'product')} x{data['quantity']} (£{data['cost']})")
    
    def test_waste_report(self):
        """GET /api/stock/waste-report/{property_id} - waste breakdown by reason"""
        headers = get_auth_headers()
        response = requests.get(f"{BASE_URL}/api/stock/waste-report/{PROPERTY_ID}", headers=headers)
        assert response.status_code == 200, f"Waste report failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "total_waste_cost" in data, "Missing total_waste_cost"
        assert "by_reason" in data, "Missing by_reason"
        assert "top_products" in data, "Missing top_products"
        assert "period_days" in data, "Missing period_days"
        
        print(f"✓ Waste Report: £{data['total_waste_cost']} total waste over {data['period_days']} days")
        print(f"  By reason: {list(data['by_reason'].keys())}")


class TestRegressionExistingFeatures:
    """Regression tests for existing stock features"""
    
    def test_products_list(self):
        """GET /api/stock/products/{property_id} - list products"""
        headers = get_auth_headers()
        response = requests.get(f"{BASE_URL}/api/stock/products/{PROPERTY_ID}", headers=headers)
        assert response.status_code == 200, f"Products list failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Products should be a list"
        print(f"✓ Products List: {len(data)} products")
    
    def test_recipes_list(self):
        """GET /api/stock/recipes/{property_id} - list recipes"""
        headers = get_auth_headers()
        response = requests.get(f"{BASE_URL}/api/stock/recipes/{PROPERTY_ID}", headers=headers)
        assert response.status_code == 200, f"Recipes list failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Recipes should be a list"
        print(f"✓ Recipes List: {len(data)} recipes")
    
    def test_movements_list(self):
        """GET /api/stock/movements/{property_id} - list movements"""
        headers = get_auth_headers()
        response = requests.get(f"{BASE_URL}/api/stock/movements/{PROPERTY_ID}", headers=headers)
        assert response.status_code == 200, f"Movements list failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Movements should be a list"
        print(f"✓ Movements List: {len(data)} movements")
    
    def test_stock_stats(self):
        """GET /api/stock/stats/{property_id} - stock statistics"""
        headers = get_auth_headers()
        response = requests.get(f"{BASE_URL}/api/stock/stats/{PROPERTY_ID}", headers=headers)
        assert response.status_code == 200, f"Stock stats failed: {response.text}"
        data = response.json()
        assert "total_products" in data, "Missing total_products"
        assert "total_recipes" in data, "Missing total_recipes"
        assert "stock_value" in data, "Missing stock_value"
        print(f"✓ Stock Stats: {data['total_products']} products, {data['total_recipes']} recipes, £{data['stock_value']} value")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
