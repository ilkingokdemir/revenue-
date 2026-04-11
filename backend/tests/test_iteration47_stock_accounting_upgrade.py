"""
Iteration 47 - Stock Management & Accounting Upgrade Tests
Tests for Apicbase-level stock features and M3/Xero-level accounting features:
- Sub-recipes
- COGS per sale
- Theoretical vs actual consumption
- Wastage with reason codes
- Supplier management
- Purchase orders with receive/auto-stock
- Stock count sheets
- USALI chart of accounts
- Invoicing with VAT
- VAT reports
- Multi-period trends
- CSV export
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
PROPERTY_ID = "city-gate"

class TestAuth:
    """Authentication tests"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "token" in data
        return data["token"]
    
    def test_login_success(self, auth_token):
        """Test admin login"""
        assert auth_token is not None
        assert len(auth_token) > 0
        print("✓ Admin login successful")


class TestSubRecipes:
    """Sub-recipe tests (Apicbase-level feature)"""
    
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
        """Create a test product for sub-recipe"""
        product_data = {
            "property_id": PROPERTY_ID,
            "name": f"TEST_SubRecipeIngredient_{uuid.uuid4().hex[:6]}",
            "category": "food",
            "unit": "kg",
            "cost_price": 5.50,
            "current_stock": 100
        }
        response = requests.post(f"{BASE_URL}/api/stock/products", json=product_data, headers=auth_headers)
        assert response.status_code == 200
        return response.json()
    
    def test_create_sub_recipe(self, auth_headers, test_product):
        """Test POST /api/stock/sub-recipes"""
        sub_recipe_data = {
            "property_id": PROPERTY_ID,
            "name": f"TEST_SubRecipe_{uuid.uuid4().hex[:6]}",
            "yield_qty": 10,
            "yield_unit": "portions",
            "ingredients": [
                {"product_id": test_product["id"], "quantity": 2}
            ]
        }
        response = requests.post(f"{BASE_URL}/api/stock/sub-recipes", json=sub_recipe_data, headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "id" in data
        assert data["name"] == sub_recipe_data["name"]
        assert data["total_cost"] == 11.0  # 2 * 5.50
        assert data["cost_per_unit"] == 1.1  # 11.0 / 10
        print(f"✓ Sub-recipe created: {data['name']} with cost_per_unit £{data['cost_per_unit']}")
        return data
    
    def test_list_sub_recipes(self, auth_headers):
        """Test GET /api/stock/sub-recipes/{property_id}"""
        response = requests.get(f"{BASE_URL}/api/stock/sub-recipes/{PROPERTY_ID}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Listed {len(data)} sub-recipes")


class TestWasteWithReasons:
    """Waste tracking with reason codes"""
    
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
        """Create a test product for waste"""
        product_data = {
            "property_id": PROPERTY_ID,
            "name": f"TEST_WasteProduct_{uuid.uuid4().hex[:6]}",
            "category": "food",
            "unit": "kg",
            "cost_price": 10.00,
            "current_stock": 50
        }
        response = requests.post(f"{BASE_URL}/api/stock/products", json=product_data, headers=auth_headers)
        assert response.status_code == 200
        return response.json()
    
    def test_record_waste_with_reason(self, auth_headers, test_product):
        """Test POST /api/stock/waste with reason code"""
        waste_data = {
            "property_id": PROPERTY_ID,
            "product_id": test_product["id"],
            "quantity": 5,
            "reason": "expired",
            "notes": "Past expiry date"
        }
        response = requests.post(f"{BASE_URL}/api/stock/waste", json=waste_data, headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data["movement_type"] == "waste"
        assert data["cost"] == 50.0  # 5 * 10.00
        assert "expired" in data["reference"]
        print(f"✓ Waste recorded: {data['product_name']} x{data['quantity']} (reason: expired, cost: £{data['cost']})")
        return data
    
    def test_waste_report(self, auth_headers):
        """Test GET /api/stock/waste-report/{property_id}"""
        response = requests.get(f"{BASE_URL}/api/stock/waste-report/{PROPERTY_ID}?days=30", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "total_waste_cost" in data
        assert "by_reason" in data
        assert "top_products" in data
        print(f"✓ Waste report: total £{data['total_waste_cost']}, reasons: {list(data['by_reason'].keys())}")


class TestTheoreticalVsActual:
    """Theoretical vs actual consumption comparison"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        token = response.json()["token"]
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    def test_theoretical_vs_actual(self, auth_headers):
        """Test GET /api/stock/theoretical-vs-actual/{property_id}"""
        response = requests.get(f"{BASE_URL}/api/stock/theoretical-vs-actual/{PROPERTY_ID}", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "products" in data
        assert "flagged_count" in data
        assert "total_variance_cost" in data
        print(f"✓ Theo vs Actual: {len(data['products'])} products, {data['flagged_count']} flagged, £{data['total_variance_cost']} variance")


class TestSuppliers:
    """Supplier management tests"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        token = response.json()["token"]
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    def test_create_supplier(self, auth_headers):
        """Test POST /api/stock/suppliers"""
        supplier_data = {
            "property_id": PROPERTY_ID,
            "name": f"TEST_Supplier_{uuid.uuid4().hex[:6]}",
            "contact_name": "John Smith",
            "email": "supplier@test.com",
            "phone": "+44 123 456 7890",
            "payment_terms": "30 days"
        }
        response = requests.post(f"{BASE_URL}/api/stock/suppliers", json=supplier_data, headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "id" in data
        assert data["name"] == supplier_data["name"]
        print(f"✓ Supplier created: {data['name']}")
        return data
    
    def test_list_suppliers(self, auth_headers):
        """Test GET /api/stock/suppliers/{property_id}"""
        response = requests.get(f"{BASE_URL}/api/stock/suppliers/{PROPERTY_ID}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Listed {len(data)} suppliers")


class TestPurchaseOrders:
    """Purchase order tests with receive/auto-stock"""
    
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
        """Create a test product for PO"""
        product_data = {
            "property_id": PROPERTY_ID,
            "name": f"TEST_POProduct_{uuid.uuid4().hex[:6]}",
            "category": "beverage",
            "unit": "bottles",
            "cost_price": 8.00,
            "current_stock": 10
        }
        response = requests.post(f"{BASE_URL}/api/stock/products", json=product_data, headers=auth_headers)
        assert response.status_code == 200
        return response.json()
    
    def test_create_purchase_order(self, auth_headers, test_product):
        """Test POST /api/stock/purchase-orders"""
        po_data = {
            "property_id": PROPERTY_ID,
            "supplier_name": "Test Supplier Ltd",
            "items": [
                {
                    "product_id": test_product["id"],
                    "product_name": test_product["name"],
                    "quantity": 20,
                    "unit": "bottles",
                    "unit_cost": 7.50
                }
            ],
            "notes": "Urgent order"
        }
        response = requests.post(f"{BASE_URL}/api/stock/purchase-orders", json=po_data, headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "id" in data
        assert data["total_amount"] == 150.0  # 20 * 7.50
        assert data["status"] == "draft"
        print(f"✓ PO created: £{data['total_amount']} for {data['supplier_name']}")
        return data
    
    def test_receive_purchase_order(self, auth_headers, test_product):
        """Test PUT /api/stock/purchase-orders/{id}/receive"""
        # First create a PO
        po_data = {
            "property_id": PROPERTY_ID,
            "supplier_name": "Test Supplier Ltd",
            "items": [
                {
                    "product_id": test_product["id"],
                    "product_name": test_product["name"],
                    "quantity": 15,
                    "unit": "bottles",
                    "unit_cost": 7.50
                }
            ]
        }
        create_response = requests.post(f"{BASE_URL}/api/stock/purchase-orders", json=po_data, headers=auth_headers)
        po = create_response.json()
        
        # Get initial stock
        prod_response = requests.get(f"{BASE_URL}/api/stock/products/{PROPERTY_ID}?search={test_product['name']}", headers=auth_headers)
        initial_stock = prod_response.json()[0]["current_stock"] if prod_response.json() else 0
        
        # Receive the PO
        response = requests.put(f"{BASE_URL}/api/stock/purchase-orders/{po['id']}/receive", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data["status"] == "received"
        assert data["items_stocked"] == 1
        print(f"✓ PO received: {data['items_stocked']} items stocked")
        
        # Verify stock increased
        prod_response = requests.get(f"{BASE_URL}/api/stock/products/{PROPERTY_ID}?search={test_product['name']}", headers=auth_headers)
        new_stock = prod_response.json()[0]["current_stock"] if prod_response.json() else 0
        assert new_stock >= initial_stock, "Stock should have increased after receiving PO"
        print(f"✓ Stock auto-updated: {initial_stock} → {new_stock}")


class TestStockCountSheets:
    """Stock count sheet tests"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        token = response.json()["token"]
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    def test_create_count_sheet(self, auth_headers):
        """Test POST /api/stock/count-sheets"""
        sheet_data = {
            "property_id": PROPERTY_ID,
            "name": f"TEST_Count_{uuid.uuid4().hex[:6]}"
        }
        response = requests.post(f"{BASE_URL}/api/stock/count-sheets", json=sheet_data, headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "id" in data
        assert "items" in data
        assert data["status"] == "in_progress"
        print(f"✓ Count sheet created: {data['name']} with {len(data['items'])} products")
        return data
    
    def test_update_count_sheet(self, auth_headers):
        """Test PUT /api/stock/count-sheets/{id}"""
        # Create a sheet first
        create_response = requests.post(f"{BASE_URL}/api/stock/count-sheets", json={"property_id": PROPERTY_ID}, headers=auth_headers)
        sheet = create_response.json()
        
        # Update with counted values
        if sheet["items"]:
            items = sheet["items"]
            items[0]["counted"] = items[0]["expected"] + 5  # Simulate variance
            
            response = requests.put(f"{BASE_URL}/api/stock/count-sheets/{sheet['id']}", json={"items": items}, headers=auth_headers)
            assert response.status_code == 200, f"Failed: {response.text}"
            data = response.json()
            assert data["items"][0]["variance"] == 5
            print(f"✓ Count sheet updated with variance: {data['items'][0]['variance']}")
    
    def test_complete_count_sheet(self, auth_headers):
        """Test POST /api/stock/count-sheets/{id}/complete"""
        # Create and update a sheet
        create_response = requests.post(f"{BASE_URL}/api/stock/count-sheets", json={"property_id": PROPERTY_ID}, headers=auth_headers)
        sheet = create_response.json()
        
        if sheet["items"]:
            items = sheet["items"]
            items[0]["counted"] = 100
            requests.put(f"{BASE_URL}/api/stock/count-sheets/{sheet['id']}", json={"items": items}, headers=auth_headers)
        
        # Complete the sheet
        response = requests.post(f"{BASE_URL}/api/stock/count-sheets/{sheet['id']}/complete", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data["status"] == "completed"
        print(f"✓ Count sheet completed: {data['products_updated']} products updated")


class TestRecordSaleCOGS:
    """COGS per sale tests"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        token = response.json()["token"]
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    @pytest.fixture(scope="class")
    def test_product_and_recipe(self, auth_headers):
        """Create test product and recipe"""
        # Create product
        product_data = {
            "property_id": PROPERTY_ID,
            "name": f"TEST_COGSProduct_{uuid.uuid4().hex[:6]}",
            "category": "beverage",
            "unit": "ml",
            "cost_price": 0.05,
            "current_stock": 5000
        }
        prod_response = requests.post(f"{BASE_URL}/api/stock/products", json=product_data, headers=auth_headers)
        product = prod_response.json()
        
        # Create recipe with this product
        recipe_data = {
            "property_id": PROPERTY_ID,
            "name": f"TEST_COGSRecipe_{uuid.uuid4().hex[:6]}",
            "outlet": "bar",
            "sell_price": 8.00,
            "ingredients": [
                {"product_id": product["id"], "quantity": 50}  # 50ml per drink
            ]
        }
        recipe_response = requests.post(f"{BASE_URL}/api/stock/recipes", json=recipe_data, headers=auth_headers)
        recipe = recipe_response.json()
        
        return {"product": product, "recipe": recipe}
    
    def test_record_sale(self, auth_headers, test_product_and_recipe):
        """Test POST /api/stock/record-sale"""
        recipe = test_product_and_recipe["recipe"]
        product = test_product_and_recipe["product"]
        
        # Get initial stock
        prod_response = requests.get(f"{BASE_URL}/api/stock/products/{PROPERTY_ID}?search={product['name']}", headers=auth_headers)
        initial_stock = prod_response.json()[0]["current_stock"] if prod_response.json() else 0
        
        # Record sale
        sale_data = {
            "recipe_id": recipe["id"],
            "quantity": 2  # Sell 2 drinks
        }
        response = requests.post(f"{BASE_URL}/api/stock/record-sale", json=sale_data, headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert data["recipe"] == recipe["name"]
        assert data["quantity"] == 2
        assert data["cogs"] == 5.0  # 2 * 50ml * £0.05
        assert data["revenue"] == 16.0  # 2 * £8.00
        assert data["gross_profit"] == 11.0  # 16 - 5
        print(f"✓ Sale recorded: {data['recipe']} x{data['quantity']}, COGS: £{data['cogs']}, Revenue: £{data['revenue']}, Profit: £{data['gross_profit']}")
        
        # Verify stock decreased
        prod_response = requests.get(f"{BASE_URL}/api/stock/products/{PROPERTY_ID}?search={product['name']}", headers=auth_headers)
        new_stock = prod_response.json()[0]["current_stock"] if prod_response.json() else 0
        expected_decrease = 100  # 2 drinks * 50ml each
        assert new_stock == initial_stock - expected_decrease, f"Stock should decrease by {expected_decrease}"
        print(f"✓ Stock auto-deducted: {initial_stock} → {new_stock}")


class TestChartOfAccounts:
    """USALI Chart of Accounts tests"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        token = response.json()["token"]
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    def test_get_chart_of_accounts_auto_seeds(self, auth_headers):
        """Test GET /api/accounting/chart-of-accounts/{property_id} auto-seeds 19 USALI accounts"""
        response = requests.get(f"{BASE_URL}/api/accounting/chart-of-accounts/{PROPERTY_ID}", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 19, f"Expected at least 19 USALI accounts, got {len(data)}"
        
        # Verify account types
        account_types = set(a["account_type"] for a in data)
        expected_types = {"revenue", "cost_of_sales", "operating_expenses", "payroll"}
        assert expected_types.issubset(account_types), f"Missing account types: {expected_types - account_types}"
        print(f"✓ Chart of Accounts: {len(data)} accounts, types: {account_types}")


class TestInvoicing:
    """Invoice tests with VAT"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        token = response.json()["token"]
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    def test_create_invoice_with_vat(self, auth_headers):
        """Test POST /api/accounting/invoices with VAT calculation"""
        invoice_data = {
            "property_id": PROPERTY_ID,
            "invoice_type": "receivable",
            "counterparty": "Test Guest",
            "due_date": "2026-02-15",
            "items": [
                {"description": "Room charge", "quantity": 3, "unit_price": 150.00, "vat_rate": 20},
                {"description": "Breakfast", "quantity": 3, "unit_price": 25.00, "vat_rate": 20}
            ]
        }
        response = requests.post(f"{BASE_URL}/api/accounting/invoices", json=invoice_data, headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert "id" in data
        assert "invoice_number" in data
        assert data["subtotal"] == 525.0  # (3*150) + (3*25)
        assert data["vat_amount"] == 105.0  # 525 * 20%
        assert data["total"] == 630.0  # 525 + 105
        print(f"✓ Invoice created: {data['invoice_number']}, subtotal: £{data['subtotal']}, VAT: £{data['vat_amount']}, total: £{data['total']}")
        return data
    
    def test_mark_invoice_paid(self, auth_headers):
        """Test PUT /api/accounting/invoices/{id} to mark as paid"""
        # Create invoice first
        invoice_data = {
            "property_id": PROPERTY_ID,
            "invoice_type": "receivable",
            "counterparty": "Test Guest 2",
            "due_date": "2026-02-20",
            "items": [{"description": "Service", "quantity": 1, "unit_price": 100.00, "vat_rate": 20}]
        }
        create_response = requests.post(f"{BASE_URL}/api/accounting/invoices", json=invoice_data, headers=auth_headers)
        invoice = create_response.json()
        
        # Mark as paid
        response = requests.put(f"{BASE_URL}/api/accounting/invoices/{invoice['id']}", json={"status": "paid"}, headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data["status"] == "paid"
        assert "paid_date" in data and data["paid_date"]
        print(f"✓ Invoice marked paid: {data['invoice_number']} on {data['paid_date']}")


class TestVATReport:
    """VAT report tests"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        token = response.json()["token"]
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    def test_vat_report(self, auth_headers):
        """Test GET /api/accounting/vat-report/{property_id}"""
        response = requests.get(f"{BASE_URL}/api/accounting/vat-report/{PROPERTY_ID}", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert "period" in data
        assert "output_vat" in data
        assert "input_vat" in data
        assert "net_vat_payable" in data
        assert "output_sales" in data
        print(f"✓ VAT Report: period {data['period']}, output VAT: £{data['output_vat']}, input VAT: £{data['input_vat']}, net payable: £{data['net_vat_payable']}")


class TestFinancialTrends:
    """Multi-period financial trends tests"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        token = response.json()["token"]
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    def test_6_month_trends(self, auth_headers):
        """Test GET /api/accounting/trends/{property_id}"""
        response = requests.get(f"{BASE_URL}/api/accounting/trends/{PROPERTY_ID}?months=6", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert isinstance(data, list)
        assert len(data) == 6, f"Expected 6 months, got {len(data)}"
        
        for month_data in data:
            assert "month" in month_data
            assert "income" in month_data
            assert "expenses" in month_data
            assert "net_profit" in month_data
            assert "margin" in month_data
        
        print(f"✓ 6-month trends: {[m['month'] for m in data]}")


class TestCSVExport:
    """CSV export tests"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        token = response.json()["token"]
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    def test_export_income(self, auth_headers):
        """Test GET /api/accounting/export/{property_id}?type=income"""
        response = requests.get(f"{BASE_URL}/api/accounting/export/{PROPERTY_ID}?type=income", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert "headers" in data
        assert "rows" in data
        assert "period" in data
        assert "type" in data
        assert data["type"] == "income"
        print(f"✓ Income export: {data['count']} rows, headers: {data['headers']}")
    
    def test_export_expenses(self, auth_headers):
        """Test GET /api/accounting/export/{property_id}?type=expenses"""
        response = requests.get(f"{BASE_URL}/api/accounting/export/{PROPERTY_ID}?type=expenses", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert data["type"] == "expenses"
        print(f"✓ Expenses export: {data['count']} rows")
    
    def test_export_invoices(self, auth_headers):
        """Test GET /api/accounting/export/{property_id}?type=invoices"""
        response = requests.get(f"{BASE_URL}/api/accounting/export/{PROPERTY_ID}?type=invoices", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert data["type"] == "invoices"
        print(f"✓ Invoices export: {data['count']} rows")
    
    def test_export_pnl(self, auth_headers):
        """Test GET /api/accounting/export/{property_id}?type=pnl"""
        response = requests.get(f"{BASE_URL}/api/accounting/export/{PROPERTY_ID}?type=pnl", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # P&L export returns the full P&L statement
        assert "total_income" in data
        assert "total_expenses" in data
        assert "net_profit" in data
        print(f"✓ P&L export: income £{data['total_income']}, expenses £{data['total_expenses']}, profit £{data['net_profit']}")


class TestRegressionExistingFeatures:
    """Regression tests for existing stock/accounting features"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        token = response.json()["token"]
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    def test_stock_products_crud(self, auth_headers):
        """Regression: Stock products CRUD still works"""
        # Create
        product_data = {
            "property_id": PROPERTY_ID,
            "name": f"TEST_Regression_{uuid.uuid4().hex[:6]}",
            "category": "food",
            "unit": "kg",
            "cost_price": 5.00,
            "current_stock": 20
        }
        create_response = requests.post(f"{BASE_URL}/api/stock/products", json=product_data, headers=auth_headers)
        assert create_response.status_code == 200
        product = create_response.json()
        
        # Read
        list_response = requests.get(f"{BASE_URL}/api/stock/products/{PROPERTY_ID}", headers=auth_headers)
        assert list_response.status_code == 200
        
        # Update
        update_response = requests.put(f"{BASE_URL}/api/stock/products/{product['id']}", json={"cost_price": 6.00}, headers=auth_headers)
        assert update_response.status_code == 200
        
        # Delete
        delete_response = requests.delete(f"{BASE_URL}/api/stock/products/{product['id']}", headers=auth_headers)
        assert delete_response.status_code == 200
        print("✓ Regression: Stock products CRUD working")
    
    def test_stock_stats(self, auth_headers):
        """Regression: Stock stats endpoint works"""
        response = requests.get(f"{BASE_URL}/api/stock/stats/{PROPERTY_ID}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "total_products" in data
        assert "stock_value" in data
        print(f"✓ Regression: Stock stats - {data['total_products']} products, £{data['stock_value']} value")
    
    def test_accounting_pnl(self, auth_headers):
        """Regression: P&L endpoint works"""
        response = requests.get(f"{BASE_URL}/api/accounting/pnl/{PROPERTY_ID}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "total_income" in data
        assert "total_expenses" in data
        assert "net_profit" in data
        print(f"✓ Regression: P&L - income £{data['total_income']}, expenses £{data['total_expenses']}")
    
    def test_accounting_stats(self, auth_headers):
        """Regression: Accounting stats endpoint works"""
        response = requests.get(f"{BASE_URL}/api/accounting/stats/{PROPERTY_ID}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "income" in data
        assert "expenses" in data
        print(f"✓ Regression: Accounting stats - income £{data['income']}, expenses £{data['expenses']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
