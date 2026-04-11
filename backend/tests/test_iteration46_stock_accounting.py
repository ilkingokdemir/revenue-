"""
Iteration 46 - Stock Management & Hotel Accounting Tests
Tests for the two new modules:
1. Stock Management: Products, Recipes, Movements, Outlets, Variance, All-Inclusive Cost
2. Hotel Accounting: Income, Expenses, P&L, Budgets, Budget vs Actual, Sync Revenue
"""
import pytest
import requests
import os
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
PROPERTY_ID = "city-gate"

class TestAuth:
    """Authentication tests"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Login and get auth token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "admin@hotelbox.com", "password": "HotelAdmin2026!"}
        )
        assert response.status_code == 200, f"Login failed: {response.text}"
        cookies = response.cookies
        return cookies
    
    def test_admin_login(self, auth_token):
        """Test admin login works"""
        assert auth_token is not None
        print("PASS: Admin login successful")


class TestStockProducts:
    """Stock Product CRUD tests"""
    
    @pytest.fixture(scope="class")
    def session(self):
        """Create authenticated session"""
        s = requests.Session()
        response = s.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "admin@hotelbox.com", "password": "HotelAdmin2026!"}
        )
        assert response.status_code == 200
        return s
    
    @pytest.fixture(scope="class")
    def test_product_id(self, session):
        """Create a test product and return its ID"""
        product_data = {
            "property_id": PROPERTY_ID,
            "name": "TEST_Olive_Oil_Premium",
            "category": "food",
            "unit": "l",
            "cost_price": 12.50,
            "sell_price": 0,
            "reorder_level": 5,
            "current_stock": 20
        }
        response = session.post(f"{BASE_URL}/api/stock/products", json=product_data)
        assert response.status_code == 200, f"Create product failed: {response.text}"
        data = response.json()
        assert "id" in data
        yield data["id"]
        # Cleanup
        session.delete(f"{BASE_URL}/api/stock/products/{data['id']}")
    
    def test_create_product(self, session):
        """Test POST /api/stock/products"""
        product_data = {
            "property_id": PROPERTY_ID,
            "name": "TEST_Tomatoes_Fresh",
            "category": "produce",
            "unit": "kg",
            "cost_price": 2.50,
            "reorder_level": 10,
            "current_stock": 50
        }
        response = session.post(f"{BASE_URL}/api/stock/products", json=product_data)
        assert response.status_code == 200, f"Create product failed: {response.text}"
        data = response.json()
        assert data["name"] == "TEST_Tomatoes_Fresh"
        assert data["category"] == "produce"
        assert data["cost_price"] == 2.50
        assert data["current_stock"] == 50
        print(f"PASS: Created product {data['id']}")
        # Cleanup
        session.delete(f"{BASE_URL}/api/stock/products/{data['id']}")
    
    def test_list_products(self, session, test_product_id):
        """Test GET /api/stock/products/{property_id}"""
        response = session.get(f"{BASE_URL}/api/stock/products/{PROPERTY_ID}")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # Check our test product is in the list
        product_ids = [p["id"] for p in data]
        assert test_product_id in product_ids
        print(f"PASS: Listed {len(data)} products")
    
    def test_list_products_with_search(self, session, test_product_id):
        """Test GET /api/stock/products/{property_id}?search=..."""
        response = session.get(f"{BASE_URL}/api/stock/products/{PROPERTY_ID}?search=TEST_Olive")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert any("Olive" in p["name"] for p in data)
        print(f"PASS: Search returned {len(data)} products")
    
    def test_update_product(self, session, test_product_id):
        """Test PUT /api/stock/products/{product_id}"""
        updates = {"cost_price": 15.00, "current_stock": 25}
        response = session.put(f"{BASE_URL}/api/stock/products/{test_product_id}", json=updates)
        assert response.status_code == 200
        data = response.json()
        assert data["cost_price"] == 15.00
        assert data["current_stock"] == 25
        print(f"PASS: Updated product {test_product_id}")
    
    def test_delete_product(self, session):
        """Test DELETE /api/stock/products/{product_id}"""
        # Create a product to delete
        product_data = {
            "property_id": PROPERTY_ID,
            "name": "TEST_ToDelete_Product",
            "category": "other",
            "unit": "pcs",
            "cost_price": 1.00
        }
        create_resp = session.post(f"{BASE_URL}/api/stock/products", json=product_data)
        assert create_resp.status_code == 200
        product_id = create_resp.json()["id"]
        
        # Delete it
        response = session.delete(f"{BASE_URL}/api/stock/products/{product_id}")
        assert response.status_code == 200
        assert response.json()["status"] == "deleted"
        print(f"PASS: Deleted product {product_id}")


class TestStockRecipes:
    """Stock Recipe tests"""
    
    @pytest.fixture(scope="class")
    def session(self):
        s = requests.Session()
        s.post(f"{BASE_URL}/api/auth/login", json={"email": "admin@hotelbox.com", "password": "HotelAdmin2026!"})
        return s
    
    @pytest.fixture(scope="class")
    def test_product_for_recipe(self, session):
        """Create a product to use in recipe"""
        product_data = {
            "property_id": PROPERTY_ID,
            "name": "TEST_Rum_White",
            "category": "spirits",
            "unit": "ml",
            "cost_price": 0.05
        }
        response = session.post(f"{BASE_URL}/api/stock/products", json=product_data)
        data = response.json()
        yield data
        session.delete(f"{BASE_URL}/api/stock/products/{data['id']}")
    
    def test_create_recipe(self, session, test_product_for_recipe):
        """Test POST /api/stock/recipes"""
        recipe_data = {
            "property_id": PROPERTY_ID,
            "name": "TEST_Mojito_Classic",
            "outlet": "bar",
            "sell_price": 12.00,
            "ingredients": [
                {"product_id": test_product_for_recipe["id"], "quantity": 50, "unit": "ml"}
            ]
        }
        response = session.post(f"{BASE_URL}/api/stock/recipes", json=recipe_data)
        assert response.status_code == 200, f"Create recipe failed: {response.text}"
        data = response.json()
        assert data["name"] == "TEST_Mojito_Classic"
        assert data["sell_price"] == 12.00
        assert data["total_cost"] >= 0  # Should be calculated
        assert "margin_pct" in data
        print(f"PASS: Created recipe {data['id']} with cost £{data['total_cost']} and margin {data['margin_pct']}%")
        # Cleanup
        session.delete(f"{BASE_URL}/api/stock/recipes/{data['id']}")
    
    def test_list_recipes(self, session):
        """Test GET /api/stock/recipes/{property_id}"""
        response = session.get(f"{BASE_URL}/api/stock/recipes/{PROPERTY_ID}")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"PASS: Listed {len(data)} recipes")


class TestStockMovements:
    """Stock Movement tests"""
    
    @pytest.fixture(scope="class")
    def session(self):
        s = requests.Session()
        s.post(f"{BASE_URL}/api/auth/login", json={"email": "admin@hotelbox.com", "password": "HotelAdmin2026!"})
        return s
    
    @pytest.fixture(scope="class")
    def test_product_for_movement(self, session):
        """Create a product for movement tests"""
        product_data = {
            "property_id": PROPERTY_ID,
            "name": "TEST_Coffee_Beans",
            "category": "beverage",
            "unit": "kg",
            "cost_price": 15.00,
            "current_stock": 10
        }
        response = session.post(f"{BASE_URL}/api/stock/products", json=product_data)
        data = response.json()
        yield data
        session.delete(f"{BASE_URL}/api/stock/products/{data['id']}")
    
    def test_record_purchase_movement(self, session, test_product_for_movement):
        """Test POST /api/stock/movements - purchase"""
        movement_data = {
            "property_id": PROPERTY_ID,
            "product_id": test_product_for_movement["id"],
            "movement_type": "purchase",
            "quantity": 5,
            "notes": "Weekly delivery"
        }
        response = session.post(f"{BASE_URL}/api/stock/movements", json=movement_data)
        assert response.status_code == 200, f"Record movement failed: {response.text}"
        data = response.json()
        assert data["movement_type"] == "purchase"
        assert data["quantity"] == 5
        assert data["cost"] == 75.00  # 5 * 15.00
        assert data["product_name"] == "TEST_Coffee_Beans"
        print(f"PASS: Recorded purchase movement {data['id']} with cost £{data['cost']}")
        
        # Verify stock was updated
        prod_resp = session.get(f"{BASE_URL}/api/stock/products/{PROPERTY_ID}?search=TEST_Coffee_Beans")
        products = prod_resp.json()
        updated_product = next((p for p in products if p["id"] == test_product_for_movement["id"]), None)
        assert updated_product is not None
        assert updated_product["current_stock"] == 15  # 10 + 5
        print(f"PASS: Stock updated to {updated_product['current_stock']}")
    
    def test_record_usage_movement(self, session, test_product_for_movement):
        """Test POST /api/stock/movements - usage"""
        movement_data = {
            "property_id": PROPERTY_ID,
            "product_id": test_product_for_movement["id"],
            "movement_type": "usage",
            "quantity": 2,
            "outlet": "restaurant"
        }
        response = session.post(f"{BASE_URL}/api/stock/movements", json=movement_data)
        assert response.status_code == 200
        data = response.json()
        assert data["movement_type"] == "usage"
        print(f"PASS: Recorded usage movement {data['id']}")
    
    def test_list_movements(self, session, test_product_for_movement):
        """Test GET /api/stock/movements/{property_id}"""
        response = session.get(f"{BASE_URL}/api/stock/movements/{PROPERTY_ID}")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"PASS: Listed {len(data)} movements")


class TestStockOutlets:
    """Stock Outlets tests"""
    
    @pytest.fixture(scope="class")
    def session(self):
        s = requests.Session()
        s.post(f"{BASE_URL}/api/auth/login", json={"email": "admin@hotelbox.com", "password": "HotelAdmin2026!"})
        return s
    
    def test_list_outlets_auto_seeds(self, session):
        """Test GET /api/stock/outlets/{property_id} - auto-seeds 4 outlets"""
        response = session.get(f"{BASE_URL}/api/stock/outlets/{PROPERTY_ID}")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 4  # Should have at least 4 default outlets
        outlet_names = [o["name"] for o in data]
        assert "Main Restaurant" in outlet_names
        assert "Lobby Bar" in outlet_names
        assert "Pool Café" in outlet_names
        assert "Kitchen Store" in outlet_names
        print(f"PASS: Listed {len(data)} outlets (auto-seeded)")


class TestStockVariance:
    """Stock Variance / Theft Detection tests"""
    
    @pytest.fixture(scope="class")
    def session(self):
        s = requests.Session()
        s.post(f"{BASE_URL}/api/auth/login", json={"email": "admin@hotelbox.com", "password": "HotelAdmin2026!"})
        return s
    
    def test_run_variance_check(self, session):
        """Test POST /api/stock/variance/{property_id}"""
        response = session.post(f"{BASE_URL}/api/stock/variance/{PROPERTY_ID}")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "flagged" in data
        assert "variances" in data
        print(f"PASS: Variance check complete - {data['flagged']} products flagged")
    
    def test_list_variances(self, session):
        """Test GET /api/stock/variances/{property_id}"""
        response = session.get(f"{BASE_URL}/api/stock/variances/{PROPERTY_ID}")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"PASS: Listed {len(data)} variances")


class TestStockAllInclusiveCost:
    """All-Inclusive Cost Calculation tests"""
    
    @pytest.fixture(scope="class")
    def session(self):
        s = requests.Session()
        s.post(f"{BASE_URL}/api/auth/login", json={"email": "admin@hotelbox.com", "password": "HotelAdmin2026!"})
        return s
    
    def test_all_inclusive_cost(self, session):
        """Test GET /api/stock/all-inclusive-cost/{property_id}"""
        response = session.get(f"{BASE_URL}/api/stock/all-inclusive-cost/{PROPERTY_ID}")
        assert response.status_code == 200
        data = response.json()
        assert "period_days" in data
        assert "total_fb_cost" in data
        assert "total_waste_cost" in data
        assert "total_guest_nights" in data
        assert "cost_per_guest_night" in data
        assert "waste_per_guest_night" in data
        assert "by_category" in data
        assert "low_stock_alerts" in data
        print(f"PASS: All-inclusive cost: £{data['cost_per_guest_night']}/guest/night, {data['total_guest_nights']} guest nights")


class TestStockStats:
    """Stock Dashboard Stats tests"""
    
    @pytest.fixture(scope="class")
    def session(self):
        s = requests.Session()
        s.post(f"{BASE_URL}/api/auth/login", json={"email": "admin@hotelbox.com", "password": "HotelAdmin2026!"})
        return s
    
    def test_stock_stats(self, session):
        """Test GET /api/stock/stats/{property_id}"""
        response = session.get(f"{BASE_URL}/api/stock/stats/{PROPERTY_ID}")
        assert response.status_code == 200
        data = response.json()
        assert "total_products" in data
        assert "total_recipes" in data
        assert "total_movements" in data
        assert "flagged_variances" in data
        assert "stock_value" in data
        assert "low_stock_count" in data
        print(f"PASS: Stock stats - {data['total_products']} products, £{data['stock_value']} value")


class TestAccountingIncome:
    """Accounting Income tests"""
    
    @pytest.fixture(scope="class")
    def session(self):
        s = requests.Session()
        s.post(f"{BASE_URL}/api/auth/login", json={"email": "admin@hotelbox.com", "password": "HotelAdmin2026!"})
        return s
    
    @pytest.fixture(scope="class")
    def test_income_id(self, session):
        """Create a test income entry"""
        income_data = {
            "property_id": PROPERTY_ID,
            "category": "food_beverage",
            "amount": 1500.00,
            "department": "food_beverage",
            "date": datetime.now().strftime("%Y-%m-%d"),
            "description": "TEST_Restaurant_Revenue"
        }
        response = session.post(f"{BASE_URL}/api/accounting/income", json=income_data)
        assert response.status_code == 200
        data = response.json()
        yield data["id"]
        session.delete(f"{BASE_URL}/api/accounting/income/{data['id']}")
    
    def test_create_income(self, session):
        """Test POST /api/accounting/income"""
        income_data = {
            "property_id": PROPERTY_ID,
            "category": "spa_wellness",
            "amount": 500.00,
            "department": "spa",
            "date": datetime.now().strftime("%Y-%m-%d"),
            "description": "TEST_Spa_Services"
        }
        response = session.post(f"{BASE_URL}/api/accounting/income", json=income_data)
        assert response.status_code == 200, f"Create income failed: {response.text}"
        data = response.json()
        assert data["category"] == "spa_wellness"
        assert data["amount"] == 500.00
        assert data["department"] == "spa"
        print(f"PASS: Created income entry {data['id']}")
        session.delete(f"{BASE_URL}/api/accounting/income/{data['id']}")
    
    def test_list_income(self, session, test_income_id):
        """Test GET /api/accounting/income/{property_id}"""
        current_month = datetime.now().strftime("%Y-%m")
        response = session.get(f"{BASE_URL}/api/accounting/income/{PROPERTY_ID}?month={current_month}")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"PASS: Listed {len(data)} income entries")


class TestAccountingExpenses:
    """Accounting Expenses tests"""
    
    @pytest.fixture(scope="class")
    def session(self):
        s = requests.Session()
        s.post(f"{BASE_URL}/api/auth/login", json={"email": "admin@hotelbox.com", "password": "HotelAdmin2026!"})
        return s
    
    @pytest.fixture(scope="class")
    def test_expense_id(self, session):
        """Create a test expense entry"""
        expense_data = {
            "property_id": PROPERTY_ID,
            "category": "food_cost",
            "amount": 800.00,
            "department": "food_beverage",
            "date": datetime.now().strftime("%Y-%m-%d"),
            "description": "TEST_Food_Supplies",
            "vendor": "Local Supplier"
        }
        response = session.post(f"{BASE_URL}/api/accounting/expenses", json=expense_data)
        assert response.status_code == 200
        data = response.json()
        yield data["id"]
        session.delete(f"{BASE_URL}/api/accounting/expenses/{data['id']}")
    
    def test_create_expense(self, session):
        """Test POST /api/accounting/expenses"""
        expense_data = {
            "property_id": PROPERTY_ID,
            "category": "utilities",
            "amount": 2500.00,
            "department": "admin",
            "date": datetime.now().strftime("%Y-%m-%d"),
            "description": "TEST_Electricity_Bill",
            "vendor": "Power Company"
        }
        response = session.post(f"{BASE_URL}/api/accounting/expenses", json=expense_data)
        assert response.status_code == 200, f"Create expense failed: {response.text}"
        data = response.json()
        assert data["category"] == "utilities"
        assert data["amount"] == 2500.00
        print(f"PASS: Created expense entry {data['id']}")
        session.delete(f"{BASE_URL}/api/accounting/expenses/{data['id']}")
    
    def test_list_expenses(self, session, test_expense_id):
        """Test GET /api/accounting/expenses/{property_id}"""
        current_month = datetime.now().strftime("%Y-%m")
        response = session.get(f"{BASE_URL}/api/accounting/expenses/{PROPERTY_ID}?month={current_month}")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"PASS: Listed {len(data)} expense entries")


class TestAccountingPnL:
    """Accounting P&L Statement tests"""
    
    @pytest.fixture(scope="class")
    def session(self):
        s = requests.Session()
        s.post(f"{BASE_URL}/api/auth/login", json={"email": "admin@hotelbox.com", "password": "HotelAdmin2026!"})
        return s
    
    def test_pnl_statement(self, session):
        """Test GET /api/accounting/pnl/{property_id}"""
        current_month = datetime.now().strftime("%Y-%m")
        response = session.get(f"{BASE_URL}/api/accounting/pnl/{PROPERTY_ID}?period={current_month}")
        assert response.status_code == 200
        data = response.json()
        assert "period" in data
        assert "total_income" in data
        assert "total_expenses" in data
        assert "net_profit" in data
        assert "profit_margin" in data
        assert "income_breakdown" in data
        assert "expense_breakdown" in data
        assert "departments" in data
        print(f"PASS: P&L for {data['period']}: Income £{data['total_income']}, Expenses £{data['total_expenses']}, Net £{data['net_profit']}")


class TestAccountingBudgets:
    """Accounting Budget tests"""
    
    @pytest.fixture(scope="class")
    def session(self):
        s = requests.Session()
        s.post(f"{BASE_URL}/api/auth/login", json={"email": "admin@hotelbox.com", "password": "HotelAdmin2026!"})
        return s
    
    @pytest.fixture(scope="class")
    def test_budget_id(self, session):
        """Create a test budget"""
        current_month = datetime.now().strftime("%Y-%m")
        budget_data = {
            "property_id": PROPERTY_ID,
            "department": "food_beverage",
            "category": "food_cost",
            "month": current_month,
            "budgeted_amount": 5000.00
        }
        response = session.post(f"{BASE_URL}/api/accounting/budgets", json=budget_data)
        assert response.status_code == 200
        data = response.json()
        yield data["id"]
        # No delete endpoint for budgets, but that's fine
    
    def test_create_budget(self, session):
        """Test POST /api/accounting/budgets"""
        current_month = datetime.now().strftime("%Y-%m")
        budget_data = {
            "property_id": PROPERTY_ID,
            "department": "admin",
            "category": "utilities",
            "month": current_month,
            "budgeted_amount": 3000.00
        }
        response = session.post(f"{BASE_URL}/api/accounting/budgets", json=budget_data)
        assert response.status_code == 200, f"Create budget failed: {response.text}"
        data = response.json()
        assert data["department"] == "admin"
        assert data["budgeted_amount"] == 3000.00
        print(f"PASS: Created budget {data['id']}")
    
    def test_budget_vs_actual(self, session, test_budget_id):
        """Test GET /api/accounting/budget-vs-actual/{property_id}"""
        current_month = datetime.now().strftime("%Y-%m")
        response = session.get(f"{BASE_URL}/api/accounting/budget-vs-actual/{PROPERTY_ID}?month={current_month}")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # Each budget should have variance info
        for budget in data:
            assert "budgeted_amount" in budget
            assert "actual_amount" in budget
            assert "variance" in budget
            assert "variance_pct" in budget
            assert "status" in budget
        print(f"PASS: Budget vs Actual - {len(data)} budgets compared")


class TestAccountingStats:
    """Accounting Dashboard Stats tests"""
    
    @pytest.fixture(scope="class")
    def session(self):
        s = requests.Session()
        s.post(f"{BASE_URL}/api/auth/login", json={"email": "admin@hotelbox.com", "password": "HotelAdmin2026!"})
        return s
    
    def test_accounting_stats(self, session):
        """Test GET /api/accounting/stats/{property_id}"""
        response = session.get(f"{BASE_URL}/api/accounting/stats/{PROPERTY_ID}")
        assert response.status_code == 200
        data = response.json()
        assert "current_month" in data
        assert "income" in data
        assert "expenses" in data
        assert "net_profit" in data
        assert "margin" in data
        assert "prev_month" in data
        assert "booking_revenue" in data
        print(f"PASS: Accounting stats - Income £{data['income']}, Expenses £{data['expenses']}, Net £{data['net_profit']}")


class TestAccountingSyncRevenue:
    """Accounting Sync Revenue tests"""
    
    @pytest.fixture(scope="class")
    def session(self):
        s = requests.Session()
        s.post(f"{BASE_URL}/api/auth/login", json={"email": "admin@hotelbox.com", "password": "HotelAdmin2026!"})
        return s
    
    def test_sync_booking_revenue(self, session):
        """Test POST /api/accounting/sync-revenue/{property_id}"""
        current_month = datetime.now().strftime("%Y-%m")
        response = session.post(f"{BASE_URL}/api/accounting/sync-revenue/{PROPERTY_ID}?month={current_month}")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "entries" in data
        print(f"PASS: Sync revenue - {data['message']}")


class TestRegressionDashboard:
    """Regression tests for existing features"""
    
    @pytest.fixture(scope="class")
    def session(self):
        s = requests.Session()
        s.post(f"{BASE_URL}/api/auth/login", json={"email": "admin@hotelbox.com", "password": "HotelAdmin2026!"})
        return s
    
    def test_dashboard_overview(self, session):
        """Test GET /api/dashboard/overview/{property_id}"""
        response = session.get(f"{BASE_URL}/api/dashboard/overview/{PROPERTY_ID}")
        assert response.status_code == 200
        print("PASS: Dashboard overview works")
    
    def test_reviews_list(self, session):
        """Test GET /api/reviews"""
        response = session.get(f"{BASE_URL}/api/reviews")
        assert response.status_code == 200
        print("PASS: Reviews list works")
    
    def test_bookings_list(self, session):
        """Test GET /api/bookings"""
        response = session.get(f"{BASE_URL}/api/bookings")
        assert response.status_code == 200
        print("PASS: Bookings list works")
    
    def test_properties_list(self, session):
        """Test GET /api/properties"""
        response = session.get(f"{BASE_URL}/api/properties")
        assert response.status_code == 200
        print("PASS: Properties list works")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
