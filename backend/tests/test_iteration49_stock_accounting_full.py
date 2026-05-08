"""
Iteration 49 - Full Regression Test for Stock Management & Accounting
Tests 128-item product catalog, all 9 advanced stock features, and full accounting suite
"""
import pytest
import requests
import os
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestAuth:
    """Authentication tests"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get admin auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "token" in data, "No token in response"
        return data["token"]
    
    def test_admin_login(self, auth_token):
        """Test admin login returns valid token"""
        assert auth_token is not None
        assert len(auth_token) > 20
        print(f"✓ Admin login successful, token length: {len(auth_token)}")


class TestProductCatalog:
    """Test 128-item product catalog endpoints"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        token = response.json()["token"]
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    def test_get_catalog_returns_128_products(self, auth_headers):
        """GET /api/stock/catalog returns 128 products organized by category"""
        response = requests.get(f"{BASE_URL}/api/stock/catalog", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "categories" in data
        assert "total" in data
        assert data["total"] == 128, f"Expected 128 products, got {data['total']}"
        # Verify categories exist
        expected_cats = ["spirits", "wine", "beer", "soft_drinks", "dairy", "meat", "produce", "dry_goods", "cleaning", "supplies", "beverage"]
        for cat in expected_cats:
            assert cat in data["categories"], f"Missing category: {cat}"
        print(f"✓ Catalog has {data['total']} products across {len(data['categories'])} categories")
    
    def test_add_products_from_catalog(self, auth_headers):
        """POST /api/stock/catalog/add adds selected products"""
        response = requests.post(f"{BASE_URL}/api/stock/catalog/add", headers=auth_headers, json={
            "property_id": "city-gate",
            "products": ["Vodka (Absolut)", "Gin (Bombay Sapphire)"]
        })
        assert response.status_code == 200
        data = response.json()
        assert "added" in data or "skipped" in data
        print(f"✓ Catalog add: added={data.get('added', 0)}, skipped={data.get('skipped', 0)}")
    
    def test_add_all_category_from_catalog(self, auth_headers):
        """POST /api/stock/catalog/add-all adds all products from a category"""
        response = requests.post(f"{BASE_URL}/api/stock/catalog/add-all", headers=auth_headers, json={
            "property_id": "city-gate",
            "category": "beverage"
        })
        assert response.status_code == 200
        data = response.json()
        assert "added" in data
        print(f"✓ Bulk add beverage category: {data.get('added', 0)} products added")


class TestStockProducts:
    """Test stock product CRUD operations"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        token = response.json()["token"]
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    @pytest.fixture(scope="class")
    def test_product(self, auth_headers):
        """Create a test product for other tests"""
        response = requests.post(f"{BASE_URL}/api/stock/products", headers=auth_headers, json={
            "property_id": "city-gate",
            "name": f"TEST_Product_{datetime.now().timestamp()}",
            "category": "food",
            "unit": "kg",
            "cost_price": 10.50,
            "current_stock": 50,
            "reorder_level": 10,
            "par_level": 30
        })
        assert response.status_code == 200
        return response.json()
    
    def test_create_product(self, auth_headers):
        """POST /api/stock/products creates a new product"""
        response = requests.post(f"{BASE_URL}/api/stock/products", headers=auth_headers, json={
            "property_id": "city-gate",
            "name": f"TEST_Chicken_{datetime.now().timestamp()}",
            "category": "meat",
            "unit": "kg",
            "cost_price": 8.50,
            "current_stock": 25,
            "reorder_level": 5,
            "expiry_days": 3,
            "yield_pct": 85
        })
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["name"].startswith("TEST_Chicken")
        print(f"✓ Created product: {data['name']} (id: {data['id']})")
    
    def test_list_products(self, auth_headers):
        """GET /api/stock/products/{property_id} lists products"""
        response = requests.get(f"{BASE_URL}/api/stock/products/city-gate", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Listed {len(data)} products for city-gate")
    
    def test_update_product(self, auth_headers, test_product):
        """PUT /api/stock/products/{id} updates a product"""
        product_id = test_product["id"]
        response = requests.put(f"{BASE_URL}/api/stock/products/{product_id}", headers=auth_headers, json={
            "cost_price": 12.00,
            "current_stock": 60
        })
        assert response.status_code == 200
        data = response.json()
        assert data["cost_price"] == 12.00
        print(f"✓ Updated product {product_id}: cost_price=12.00")
    
    def test_delete_product(self, auth_headers):
        """DELETE /api/stock/products/{id} deletes a product"""
        # Create a product to delete
        create_resp = requests.post(f"{BASE_URL}/api/stock/products", headers=auth_headers, json={
            "property_id": "city-gate",
            "name": f"TEST_ToDelete_{datetime.now().timestamp()}",
            "category": "other",
            "unit": "pcs",
            "cost_price": 1.00
        })
        product_id = create_resp.json()["id"]
        
        response = requests.delete(f"{BASE_URL}/api/stock/products/{product_id}", headers=auth_headers)
        assert response.status_code == 200
        print(f"✓ Deleted product {product_id}")


class TestRecipes:
    """Test recipe CRUD and COGS tracking"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        token = response.json()["token"]
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    @pytest.fixture(scope="class")
    def test_recipe_product(self, auth_headers):
        """Create a product for recipe testing"""
        response = requests.post(f"{BASE_URL}/api/stock/products", headers=auth_headers, json={
            "property_id": "city-gate",
            "name": f"TEST_RecipeIngredient_{datetime.now().timestamp()}",
            "category": "food",
            "unit": "kg",
            "cost_price": 5.00,
            "current_stock": 100
        })
        return response.json()
    
    def test_create_recipe(self, auth_headers, test_recipe_product):
        """POST /api/stock/recipes creates a recipe with ingredients"""
        response = requests.post(f"{BASE_URL}/api/stock/recipes", headers=auth_headers, json={
            "property_id": "city-gate",
            "name": f"TEST_Recipe_{datetime.now().timestamp()}",
            "outlet": "restaurant",
            "sell_price": 25.00,
            "ingredients": [
                {"product_id": test_recipe_product["id"], "quantity": 0.5}
            ]
        })
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "total_cost" in data
        assert "margin_pct" in data
        print(f"✓ Created recipe: {data['name']}, cost={data['total_cost']}, margin={data['margin_pct']}%")
        return data
    
    def test_list_recipes(self, auth_headers):
        """GET /api/stock/recipes/{property_id} lists recipes"""
        response = requests.get(f"{BASE_URL}/api/stock/recipes/city-gate", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Listed {len(data)} recipes")
    
    def test_record_sale_deducts_stock(self, auth_headers, test_recipe_product):
        """POST /api/stock/record-sale records sale and deducts ingredients"""
        # First create a recipe
        recipe_resp = requests.post(f"{BASE_URL}/api/stock/recipes", headers=auth_headers, json={
            "property_id": "city-gate",
            "name": f"TEST_SaleRecipe_{datetime.now().timestamp()}",
            "outlet": "restaurant",
            "sell_price": 20.00,
            "ingredients": [
                {"product_id": test_recipe_product["id"], "quantity": 0.25}
            ]
        })
        recipe = recipe_resp.json()
        
        # Record a sale
        response = requests.post(f"{BASE_URL}/api/stock/record-sale", headers=auth_headers, json={
            "recipe_id": recipe["id"],
            "quantity": 2
        })
        assert response.status_code == 200
        data = response.json()
        assert "cogs" in data
        assert "revenue" in data
        assert "gross_profit" in data
        assert "margin_pct" in data
        print(f"✓ Recorded sale: COGS={data['cogs']}, revenue={data['revenue']}, profit={data['gross_profit']}")


class TestStockMovements:
    """Test stock movement recording"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        token = response.json()["token"]
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    @pytest.fixture(scope="class")
    def movement_product(self, auth_headers):
        """Create a product for movement testing"""
        response = requests.post(f"{BASE_URL}/api/stock/products", headers=auth_headers, json={
            "property_id": "city-gate",
            "name": f"TEST_MovementProduct_{datetime.now().timestamp()}",
            "category": "food",
            "unit": "kg",
            "cost_price": 7.50,
            "current_stock": 50
        })
        return response.json()
    
    def test_record_movement(self, auth_headers, movement_product):
        """POST /api/stock/movements records a stock movement"""
        response = requests.post(f"{BASE_URL}/api/stock/movements", headers=auth_headers, json={
            "property_id": "city-gate",
            "product_id": movement_product["id"],
            "movement_type": "purchase",
            "quantity": 10,
            "notes": "Test purchase"
        })
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["movement_type"] == "purchase"
        print(f"✓ Recorded movement: {data['movement_type']} x{data['quantity']}")
    
    def test_list_movements(self, auth_headers):
        """GET /api/stock/movements/{property_id} lists movements"""
        response = requests.get(f"{BASE_URL}/api/stock/movements/city-gate", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Listed {len(data)} movements")


class TestOutlets:
    """Test outlet management"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        token = response.json()["token"]
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    def test_list_outlets_auto_seeds(self, auth_headers):
        """GET /api/stock/outlets/{property_id} auto-seeds 4 default outlets"""
        response = requests.get(f"{BASE_URL}/api/stock/outlets/city-gate", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 4, f"Expected at least 4 outlets, got {len(data)}"
        outlet_names = [o["name"] for o in data]
        print(f"✓ Outlets: {outlet_names}")


class TestSuppliers:
    """Test supplier management"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        token = response.json()["token"]
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    def test_create_supplier(self, auth_headers):
        """POST /api/stock/suppliers creates a supplier"""
        response = requests.post(f"{BASE_URL}/api/stock/suppliers", headers=auth_headers, json={
            "property_id": "city-gate",
            "name": f"TEST_Supplier_{datetime.now().timestamp()}",
            "email": "supplier@test.com",
            "phone": "+44123456789",
            "payment_terms": "Net 30"
        })
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        print(f"✓ Created supplier: {data['name']}")
    
    def test_list_suppliers(self, auth_headers):
        """GET /api/stock/suppliers/{property_id} lists suppliers"""
        response = requests.get(f"{BASE_URL}/api/stock/suppliers/city-gate", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Listed {len(data)} suppliers")


class TestPurchaseOrders:
    """Test purchase order workflow"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        token = response.json()["token"]
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    @pytest.fixture(scope="class")
    def po_product(self, auth_headers):
        """Create a product for PO testing"""
        response = requests.post(f"{BASE_URL}/api/stock/products", headers=auth_headers, json={
            "property_id": "city-gate",
            "name": f"TEST_POProduct_{datetime.now().timestamp()}",
            "category": "food",
            "unit": "kg",
            "cost_price": 15.00,
            "current_stock": 10
        })
        return response.json()
    
    def test_create_purchase_order(self, auth_headers, po_product):
        """POST /api/stock/purchase-orders creates a PO"""
        response = requests.post(f"{BASE_URL}/api/stock/purchase-orders", headers=auth_headers, json={
            "property_id": "city-gate",
            "supplier_name": "Test Supplier",
            "items": [
                {"product_id": po_product["id"], "product_name": po_product["name"], "quantity": 20, "unit": "kg", "unit_cost": 14.00}
            ]
        })
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "total_amount" in data
        assert data["total_amount"] == 280.00
        print(f"✓ Created PO: £{data['total_amount']}")
        return data
    
    def test_receive_purchase_order(self, auth_headers, po_product):
        """PUT /api/stock/purchase-orders/{id}/receive receives PO and updates stock"""
        # Create a PO first
        po_resp = requests.post(f"{BASE_URL}/api/stock/purchase-orders", headers=auth_headers, json={
            "property_id": "city-gate",
            "supplier_name": "Test Supplier",
            "items": [
                {"product_id": po_product["id"], "product_name": po_product["name"], "quantity": 5, "unit": "kg", "unit_cost": 14.00}
            ]
        })
        po = po_resp.json()
        
        # Receive the PO
        response = requests.put(f"{BASE_URL}/api/stock/purchase-orders/{po['id']}/receive", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "received"
        assert "items_stocked" in data
        print(f"✓ Received PO: {data['items_stocked']} items stocked")


class TestStockCounts:
    """Test stock count sheet workflow"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        token = response.json()["token"]
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    def test_create_count_sheet(self, auth_headers):
        """POST /api/stock/count-sheets creates a stock count sheet"""
        response = requests.post(f"{BASE_URL}/api/stock/count-sheets", headers=auth_headers, json={
            "property_id": "city-gate",
            "name": f"TEST_Count_{datetime.now().strftime('%Y-%m-%d')}"
        })
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "items" in data
        print(f"✓ Created count sheet with {len(data['items'])} items")
        return data
    
    def test_complete_count_sheet(self, auth_headers):
        """POST /api/stock/count-sheets/{id}/complete finalizes count"""
        # Create a count sheet
        create_resp = requests.post(f"{BASE_URL}/api/stock/count-sheets", headers=auth_headers, json={
            "property_id": "city-gate"
        })
        sheet = create_resp.json()
        
        # Complete it
        response = requests.post(f"{BASE_URL}/api/stock/count-sheets/{sheet['id']}/complete", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        print(f"✓ Completed count sheet: {data['products_updated']} products updated")


class TestWasteTracking:
    """Test waste recording with reason codes"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        token = response.json()["token"]
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    @pytest.fixture(scope="class")
    def waste_product(self, auth_headers):
        """Create a product for waste testing"""
        response = requests.post(f"{BASE_URL}/api/stock/products", headers=auth_headers, json={
            "property_id": "city-gate",
            "name": f"TEST_WasteProduct_{datetime.now().timestamp()}",
            "category": "food",
            "unit": "kg",
            "cost_price": 12.00,
            "current_stock": 50
        })
        return response.json()
    
    def test_record_waste(self, auth_headers, waste_product):
        """POST /api/stock/waste records waste with reason code"""
        response = requests.post(f"{BASE_URL}/api/stock/waste", headers=auth_headers, json={
            "property_id": "city-gate",
            "product_id": waste_product["id"],
            "quantity": 2,
            "reason": "expired",
            "notes": "Past expiry date"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["movement_type"] == "waste"
        assert "cost" in data
        print(f"✓ Recorded waste: {data['quantity']} {data['unit']}, cost=£{data['cost']}")
    
    def test_waste_report(self, auth_headers):
        """GET /api/stock/waste-report/{property_id} returns waste breakdown"""
        response = requests.get(f"{BASE_URL}/api/stock/waste-report/city-gate", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "total_waste_cost" in data
        assert "by_reason" in data
        print(f"✓ Waste report: total=£{data['total_waste_cost']}, reasons={list(data['by_reason'].keys())}")


class TestAdvancedStockFeatures:
    """Test 9 advanced Apicbase-level stock features"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        token = response.json()["token"]
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    def test_menu_engineering(self, auth_headers):
        """GET /api/stock/menu-engineering/{property_id} returns Star/Puzzle/Plowhorse/Dog classification"""
        response = requests.get(f"{BASE_URL}/api/stock/menu-engineering/city-gate", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "recipes" in data
        assert "summary" in data
        if data["summary"]:
            assert "stars" in data["summary"]
            assert "puzzles" in data["summary"]
            assert "plowhorses" in data["summary"]
            assert "dogs" in data["summary"]
        print(f"✓ Menu Engineering: {data['summary']}")
    
    def test_food_cost_dashboard(self, auth_headers):
        """GET /api/stock/food-cost-dashboard/{property_id} returns food cost % with COGS"""
        response = requests.get(f"{BASE_URL}/api/stock/food-cost-dashboard/city-gate", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "food_cost_pct" in data
        assert "cogs" in data
        assert "target_range" in data
        assert "status" in data
        print(f"✓ Food Cost Dashboard: {data['food_cost_pct']}% (target: {data['target_range']['min']}-{data['target_range']['max']}%)")
    
    def test_auto_order_from_par_levels(self, auth_headers):
        """POST /api/stock/auto-order/{property_id} generates POs from par levels"""
        response = requests.post(f"{BASE_URL}/api/stock/auto-order/city-gate", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        # API returns 'orders' list and 'message' field
        assert "orders" in data or "orders_created" in data or "message" in data
        orders_count = len(data.get("orders", [])) if "orders" in data else data.get("orders_created", 0)
        print(f"✓ Auto-order: {orders_count} POs created")
    
    def test_allergen_report(self, auth_headers):
        """GET /api/stock/allergens/{property_id} returns allergen report"""
        response = requests.get(f"{BASE_URL}/api/stock/allergens/city-gate", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "recipes" in data or isinstance(data, list)
        print(f"✓ Allergen report retrieved")
    
    def test_price_history(self, auth_headers):
        """GET /api/stock/price-history/{product_id} returns price history"""
        # Get a product first
        products = requests.get(f"{BASE_URL}/api/stock/products/city-gate", headers=auth_headers).json()
        if products:
            product_id = products[0]["id"]
            response = requests.get(f"{BASE_URL}/api/stock/price-history/{product_id}", headers=auth_headers)
            assert response.status_code == 200
            print(f"✓ Price history for product {product_id}")
    
    def test_price_update_with_log(self, auth_headers):
        """POST /api/stock/price-update/{product_id} updates price with history log"""
        # Get a product first
        products = requests.get(f"{BASE_URL}/api/stock/products/city-gate", headers=auth_headers).json()
        if products:
            product_id = products[0]["id"]
            response = requests.post(f"{BASE_URL}/api/stock/price-update/{product_id}", headers=auth_headers, json={
                "new_price": 15.50,
                "reason": "Supplier price increase"
            })
            assert response.status_code == 200
            print(f"✓ Price updated for product {product_id}")
    
    def test_yield_analysis(self, auth_headers):
        """GET /api/stock/yield-analysis/{property_id} returns yield tracking"""
        response = requests.get(f"{BASE_URL}/api/stock/yield-analysis/city-gate", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        # API returns list directly or wrapped in 'products' key
        if isinstance(data, list):
            products = data
        else:
            products = data.get("products", [])
        print(f"✓ Yield analysis: {len(products)} products")
    
    def test_perishable_alerts(self, auth_headers):
        """GET /api/stock/perishable-alerts/{property_id} returns FIFO expiry alerts"""
        response = requests.get(f"{BASE_URL}/api/stock/perishable-alerts/city-gate", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "alerts" in data
        assert "count" in data
        assert "total_at_risk_value" in data
        print(f"✓ Perishable alerts: {data['count']} alerts, £{data['total_at_risk_value']} at risk")
    
    def test_multi_outlet_transfer(self, auth_headers):
        """POST /api/stock/transfer creates multi-outlet transfer"""
        # Get a product and outlets
        products = requests.get(f"{BASE_URL}/api/stock/products/city-gate", headers=auth_headers).json()
        outlets = requests.get(f"{BASE_URL}/api/stock/outlets/city-gate", headers=auth_headers).json()
        
        if products and len(outlets) >= 2:
            response = requests.post(f"{BASE_URL}/api/stock/transfer", headers=auth_headers, json={
                "property_id": "city-gate",
                "product_id": products[0]["id"],
                "from_outlet": outlets[0]["name"],
                "to_outlet": outlets[1]["name"],
                "quantity": 1
            })
            assert response.status_code == 200
            print(f"✓ Transfer: {products[0]['name']} from {outlets[0]['name']} to {outlets[1]['name']}")
    
    def test_inventory_turnover_rate(self, auth_headers):
        """GET /api/stock/turnover-rate/{property_id} returns inventory turnover"""
        response = requests.get(f"{BASE_URL}/api/stock/turnover-rate/city-gate", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "monthly_turnover" in data
        assert "target" in data
        assert "status" in data
        print(f"✓ Turnover rate: {data['monthly_turnover']}x (target: {data['target']['min']}-{data['target']['max']}x)")


class TestVarianceAndTheft:
    """Test variance/theft detection"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        token = response.json()["token"]
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    def test_theoretical_vs_actual(self, auth_headers):
        """GET /api/stock/theoretical-vs-actual/{property_id} compares theo vs actual"""
        response = requests.get(f"{BASE_URL}/api/stock/theoretical-vs-actual/city-gate", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "products" in data
        assert "flagged_count" in data
        assert "total_variance_cost" in data
        print(f"✓ Theo vs Actual: {data['flagged_count']} flagged, £{data['total_variance_cost']} variance")
    
    def test_variance_check(self, auth_headers):
        """POST /api/stock/variance/{property_id} runs variance/theft check"""
        response = requests.post(f"{BASE_URL}/api/stock/variance/city-gate", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "flagged" in data
        print(f"✓ Variance check: {data['flagged']} products flagged")
    
    def test_all_inclusive_cost(self, auth_headers):
        """GET /api/stock/all-inclusive-cost/{property_id} returns cost per guest"""
        response = requests.get(f"{BASE_URL}/api/stock/all-inclusive-cost/city-gate", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "cost_per_guest_night" in data
        assert "total_fb_cost" in data
        print(f"✓ All-inclusive cost: £{data['cost_per_guest_night']}/guest/night")
    
    def test_stock_stats(self, auth_headers):
        """GET /api/stock/stats/{property_id} returns dashboard stats"""
        response = requests.get(f"{BASE_URL}/api/stock/stats/city-gate", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "total_products" in data
        assert "total_recipes" in data
        assert "stock_value" in data
        print(f"✓ Stock stats: {data['total_products']} products, £{data['stock_value']} value")


class TestAccounting:
    """Test accounting endpoints"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        token = response.json()["token"]
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    def test_create_income(self, auth_headers):
        """POST /api/accounting/income creates income entry"""
        response = requests.post(f"{BASE_URL}/api/accounting/income", headers=auth_headers, json={
            "property_id": "city-gate",
            "category": "food_beverage",
            "amount": 1500.00,
            "department": "food_beverage",
            "date": datetime.now().strftime("%Y-%m-%d"),
            "description": "TEST Restaurant sales"
        })
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["amount"] == 1500.00
        print(f"✓ Created income: £{data['amount']}")
    
    def test_list_income(self, auth_headers):
        """GET /api/accounting/income/{property_id} lists income"""
        response = requests.get(f"{BASE_URL}/api/accounting/income/city-gate", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Listed {len(data)} income entries")
    
    def test_create_expense(self, auth_headers):
        """POST /api/accounting/expenses creates expense entry"""
        response = requests.post(f"{BASE_URL}/api/accounting/expenses", headers=auth_headers, json={
            "property_id": "city-gate",
            "category": "food_cost",
            "amount": 500.00,
            "department": "food_beverage",
            "date": datetime.now().strftime("%Y-%m-%d"),
            "description": "TEST Food supplies",
            "vendor": "Test Supplier"
        })
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["amount"] == 500.00
        print(f"✓ Created expense: £{data['amount']}")
    
    def test_list_expenses(self, auth_headers):
        """GET /api/accounting/expenses/{property_id} lists expenses"""
        response = requests.get(f"{BASE_URL}/api/accounting/expenses/city-gate", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Listed {len(data)} expense entries")
    
    def test_pnl_statement(self, auth_headers):
        """GET /api/accounting/pnl/{property_id} returns P&L statement"""
        response = requests.get(f"{BASE_URL}/api/accounting/pnl/city-gate", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "total_income" in data
        assert "total_expenses" in data
        assert "net_profit" in data
        assert "profit_margin" in data
        print(f"✓ P&L: Income=£{data['total_income']}, Expenses=£{data['total_expenses']}, Net=£{data['net_profit']}")
    
    def test_accounting_stats(self, auth_headers):
        """GET /api/accounting/stats/{property_id} returns accounting stats"""
        response = requests.get(f"{BASE_URL}/api/accounting/stats/city-gate", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "income" in data
        assert "expenses" in data
        assert "net_profit" in data
        print(f"✓ Accounting stats: Net profit=£{data['net_profit']}")
    
    def test_chart_of_accounts_usali(self, auth_headers):
        """GET /api/accounting/chart-of-accounts/{property_id} returns USALI accounts"""
        response = requests.get(f"{BASE_URL}/api/accounting/chart-of-accounts/city-gate", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 19, f"Expected at least 19 USALI accounts, got {len(data)}"
        print(f"✓ Chart of accounts: {len(data)} USALI accounts")
    
    def test_create_invoice_with_vat(self, auth_headers):
        """POST /api/accounting/invoices creates invoice with VAT"""
        response = requests.post(f"{BASE_URL}/api/accounting/invoices", headers=auth_headers, json={
            "property_id": "city-gate",
            "invoice_type": "receivable",
            "counterparty": "TEST Guest",
            "due_date": "2026-02-15",
            "items": [
                {"description": "Room charge", "quantity": 3, "unit_price": 150.00, "vat_rate": 20}
            ]
        })
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "invoice_number" in data
        assert "subtotal" in data
        assert "vat_amount" in data
        assert "total" in data
        assert data["subtotal"] == 450.00
        assert data["vat_amount"] == 90.00
        assert data["total"] == 540.00
        print(f"✓ Created invoice {data['invoice_number']}: £{data['total']} (incl. £{data['vat_amount']} VAT)")
        return data
    
    def test_mark_invoice_paid(self, auth_headers):
        """PUT /api/accounting/invoices/{id} marks invoice as paid"""
        # Create an invoice first
        inv_resp = requests.post(f"{BASE_URL}/api/accounting/invoices", headers=auth_headers, json={
            "property_id": "city-gate",
            "invoice_type": "receivable",
            "counterparty": "TEST Guest 2",
            "due_date": "2026-02-20",
            "items": [{"description": "Service", "quantity": 1, "unit_price": 100.00, "vat_rate": 20}]
        })
        invoice = inv_resp.json()
        
        # Mark as paid
        response = requests.put(f"{BASE_URL}/api/accounting/invoices/{invoice['id']}", headers=auth_headers, json={
            "status": "paid"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "paid"
        assert "paid_date" in data
        print(f"✓ Invoice {data['invoice_number']} marked as paid")
    
    def test_vat_report(self, auth_headers):
        """GET /api/accounting/vat-report/{property_id} returns VAT report"""
        response = requests.get(f"{BASE_URL}/api/accounting/vat-report/city-gate", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "output_vat" in data
        assert "input_vat" in data
        assert "net_vat_payable" in data
        print(f"✓ VAT report: Output=£{data['output_vat']}, Input=£{data['input_vat']}, Net=£{data['net_vat_payable']}")
    
    def test_financial_trends(self, auth_headers):
        """GET /api/accounting/trends/{property_id} returns 6-month trends"""
        response = requests.get(f"{BASE_URL}/api/accounting/trends/city-gate?months=6", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) <= 6
        if data:
            assert "month" in data[0]
            assert "income" in data[0]
            assert "expenses" in data[0]
            assert "net_profit" in data[0]
        print(f"✓ Financial trends: {len(data)} months")
    
    def test_csv_export(self, auth_headers):
        """GET /api/accounting/export/{property_id} returns CSV-ready data"""
        response = requests.get(f"{BASE_URL}/api/accounting/export/city-gate?type=income", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "headers" in data
        assert "rows" in data
        print(f"✓ CSV export: {len(data['rows'])} rows")
    
    def test_create_budget(self, auth_headers):
        """POST /api/accounting/budgets creates a budget"""
        response = requests.post(f"{BASE_URL}/api/accounting/budgets", headers=auth_headers, json={
            "property_id": "city-gate",
            "month": datetime.now().strftime("%Y-%m"),
            "department": "food_beverage",
            "category": "food_cost",
            "budgeted_amount": 5000.00
        })
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        print(f"✓ Created budget: £{data['budgeted_amount']} for {data['department']}")
    
    def test_budget_vs_actual(self, auth_headers):
        """GET /api/accounting/budget-vs-actual/{property_id} returns budget comparison"""
        response = requests.get(f"{BASE_URL}/api/accounting/budget-vs-actual/city-gate", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Budget vs actual: {len(data)} budget items")
    
    def test_sync_booking_revenue(self, auth_headers):
        """POST /api/accounting/sync-revenue/{property_id} syncs booking revenue"""
        response = requests.post(f"{BASE_URL}/api/accounting/sync-revenue/city-gate", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        print(f"✓ Sync revenue: {data['message']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
