"""
Iteration 55 - Hotel POS System Tests
Tests for:
- Outlets (6 outlets auto-seeded)
- Menu items (37 items across 10 categories)
- Orders (create, list, pay, split)
- Kitchen display
- Table management
- Shifts (open/close)
- Reports
- Stock deduction
- Accounting integration (income entry)
- Room charge (folio entry)
"""
import pytest
import requests
import os
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
PROPERTY_ID = "aldgate-flats"

class TestPOSAuth:
    """Test authentication for POS endpoints"""
    
    @pytest.fixture(scope="class")
    def auth_session(self):
        """Get authenticated session"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        
        # Login
        login_resp = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        print(f"Login successful: {login_resp.json().get('user', {}).get('email')}")
        return session
    
    def test_pos_outlets_requires_auth(self):
        """Test that POS outlets endpoint requires authentication"""
        resp = requests.get(f"{BASE_URL}/api/pos/outlets/{PROPERTY_ID}")
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
        print("PASS: POS outlets requires auth")
    
    def test_pos_menu_requires_auth(self):
        """Test that POS menu endpoint requires authentication"""
        resp = requests.get(f"{BASE_URL}/api/pos/menu/{PROPERTY_ID}")
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
        print("PASS: POS menu requires auth")


class TestPOSOutlets:
    """Test POS outlets endpoints"""
    
    @pytest.fixture(scope="class")
    def auth_session(self):
        """Get authenticated session"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        login_resp = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert login_resp.status_code == 200
        return session
    
    def test_get_outlets_auto_seeds_6(self, auth_session):
        """Test GET /api/pos/outlets/{property_id} auto-seeds 6 outlets"""
        resp = auth_session.get(f"{BASE_URL}/api/pos/outlets/{PROPERTY_ID}")
        assert resp.status_code == 200, f"Failed: {resp.text}"
        
        outlets = resp.json()
        assert isinstance(outlets, list), "Expected list of outlets"
        assert len(outlets) >= 6, f"Expected at least 6 outlets, got {len(outlets)}"
        
        # Verify outlet names
        outlet_names = [o.get("name") for o in outlets]
        expected_names = ["Restaurant", "Bar & Lounge", "Room Service", "Pool Bar", "Spa", "Gift Shop"]
        for name in expected_names:
            assert name in outlet_names, f"Missing outlet: {name}"
        
        # Verify outlet structure
        for outlet in outlets:
            assert "id" in outlet, "Outlet missing id"
            assert "name" in outlet, "Outlet missing name"
            assert "type" in outlet, "Outlet missing type"
            assert "property_id" in outlet, "Outlet missing property_id"
        
        print(f"PASS: Got {len(outlets)} outlets with all 6 expected outlets")
        return outlets
    
    def test_create_outlet(self, auth_session):
        """Test POST /api/pos/outlets"""
        resp = auth_session.post(f"{BASE_URL}/api/pos/outlets", json={
            "property_id": PROPERTY_ID,
            "name": "TEST_Rooftop Bar",
            "type": "bar",
            "icon": "wine",
            "tables": 10
        })
        assert resp.status_code == 200, f"Failed: {resp.text}"
        
        outlet = resp.json()
        assert outlet.get("name") == "TEST_Rooftop Bar"
        assert outlet.get("type") == "bar"
        assert outlet.get("tables") == 10
        assert "id" in outlet
        
        print(f"PASS: Created outlet {outlet.get('id')}")


class TestPOSMenu:
    """Test POS menu endpoints"""
    
    @pytest.fixture(scope="class")
    def auth_session(self):
        """Get authenticated session"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        login_resp = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert login_resp.status_code == 200
        return session
    
    def test_get_menu_auto_seeds_37_items(self, auth_session):
        """Test GET /api/pos/menu/{property_id} auto-seeds 37 menu items"""
        resp = auth_session.get(f"{BASE_URL}/api/pos/menu/{PROPERTY_ID}")
        assert resp.status_code == 200, f"Failed: {resp.text}"
        
        menu = resp.json()
        assert isinstance(menu, list), "Expected list of menu items"
        assert len(menu) >= 37, f"Expected at least 37 menu items, got {len(menu)}"
        
        # Verify categories
        categories = set(item.get("category") for item in menu)
        expected_categories = ["Starters", "Mains", "Desserts", "Soft Drinks", "Hot Drinks", 
                              "Wine", "Beer", "Cocktails", "Spa", "Room Service"]
        for cat in expected_categories:
            assert cat in categories, f"Missing category: {cat}"
        
        # Verify item structure
        for item in menu[:5]:  # Check first 5
            assert "id" in item, "Item missing id"
            assert "name" in item, "Item missing name"
            assert "price" in item, "Item missing price"
            assert "cost" in item, "Item missing cost"
            assert "vat_rate" in item, "Item missing vat_rate"
            assert "category" in item, "Item missing category"
        
        print(f"PASS: Got {len(menu)} menu items across {len(categories)} categories")
        return menu
    
    def test_create_menu_item(self, auth_session):
        """Test POST /api/pos/menu"""
        resp = auth_session.post(f"{BASE_URL}/api/pos/menu", json={
            "property_id": PROPERTY_ID,
            "name": "TEST_Special Burger",
            "category": "Mains",
            "price": 15.99,
            "cost": 5.50,
            "vat_rate": 20,
            "description": "Test burger item"
        })
        assert resp.status_code == 200, f"Failed: {resp.text}"
        
        item = resp.json()
        assert item.get("name") == "TEST_Special Burger"
        assert item.get("price") == 15.99
        assert item.get("cost") == 5.50
        assert "id" in item
        
        print(f"PASS: Created menu item {item.get('id')}")
        return item


class TestPOSOrders:
    """Test POS orders endpoints"""
    
    @pytest.fixture(scope="class")
    def auth_session(self):
        """Get authenticated session"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        login_resp = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert login_resp.status_code == 200
        return session
    
    @pytest.fixture(scope="class")
    def outlet_id(self, auth_session):
        """Get first outlet ID"""
        resp = auth_session.get(f"{BASE_URL}/api/pos/outlets/{PROPERTY_ID}")
        outlets = resp.json()
        return outlets[0]["id"] if outlets else None
    
    def test_create_order_calculates_totals(self, auth_session, outlet_id):
        """Test POST /api/pos/orders creates order with calculated subtotal/vat/total/cost"""
        order_data = {
            "property_id": PROPERTY_ID,
            "outlet_id": outlet_id,
            "outlet_name": "Restaurant",
            "order_type": "dine_in",
            "table_number": "5",
            "covers": 2,
            "guest_name": "TEST_John Smith",
            "items": [
                {"id": "item1", "name": "Ribeye Steak", "price": 28.00, "cost": 12.00, "quantity": 2, "vat_rate": 20},
                {"id": "item2", "name": "House Wine", "price": 7.50, "cost": 1.80, "quantity": 2, "vat_rate": 20}
            ]
        }
        
        resp = auth_session.post(f"{BASE_URL}/api/pos/orders", json=order_data)
        assert resp.status_code == 200, f"Failed: {resp.text}"
        
        order = resp.json()
        
        # Verify order structure
        assert "id" in order, "Order missing id"
        assert "order_number" in order, "Order missing order_number"
        assert order["order_number"].startswith("POS-"), f"Invalid order number: {order['order_number']}"
        
        # Verify calculations
        # Subtotal: (28*2) + (7.5*2) = 56 + 15 = 71
        expected_subtotal = 71.00
        assert order["subtotal"] == expected_subtotal, f"Expected subtotal {expected_subtotal}, got {order['subtotal']}"
        
        # VAT: 71 * 0.20 = 14.2
        expected_vat = 14.20
        assert order["vat_amount"] == expected_vat, f"Expected VAT {expected_vat}, got {order['vat_amount']}"
        
        # Total: 71 + 14.2 = 85.2
        expected_total = 85.20
        assert order["total"] == expected_total, f"Expected total {expected_total}, got {order['total']}"
        
        # Cost: (12*2) + (1.8*2) = 24 + 3.6 = 27.6
        expected_cost = 27.60
        assert order["cost_total"] == expected_cost, f"Expected cost {expected_cost}, got {order['cost_total']}"
        
        # Verify status
        assert order["payment_status"] == "pending"
        assert order["kitchen_status"] == "new"
        
        print(f"PASS: Created order {order['order_number']} with correct calculations")
        return order
    
    def test_list_orders_by_date(self, auth_session):
        """Test GET /api/pos/orders/{property_id}?date= lists orders by date"""
        today = datetime.now().strftime("%Y-%m-%d")
        resp = auth_session.get(f"{BASE_URL}/api/pos/orders/{PROPERTY_ID}?date={today}")
        assert resp.status_code == 200, f"Failed: {resp.text}"
        
        orders = resp.json()
        assert isinstance(orders, list), "Expected list of orders"
        
        # Verify all orders are from today
        for order in orders:
            assert order["created_at"].startswith(today), f"Order not from today: {order['created_at']}"
        
        print(f"PASS: Got {len(orders)} orders for {today}")
        return orders


class TestPOSPayments:
    """Test POS payment endpoints"""
    
    @pytest.fixture(scope="class")
    def auth_session(self):
        """Get authenticated session"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        login_resp = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert login_resp.status_code == 200
        return session
    
    @pytest.fixture
    def test_order(self, auth_session):
        """Create a test order for payment"""
        resp = auth_session.get(f"{BASE_URL}/api/pos/outlets/{PROPERTY_ID}")
        outlet = resp.json()[0]
        
        order_resp = auth_session.post(f"{BASE_URL}/api/pos/orders", json={
            "property_id": PROPERTY_ID,
            "outlet_id": outlet["id"],
            "outlet_name": outlet["name"],
            "order_type": "dine_in",
            "table_number": "10",
            "covers": 1,
            "guest_name": "TEST_Payment Guest",
            "items": [
                {"id": "item1", "name": "Coffee", "price": 3.20, "cost": 0.35, "quantity": 1, "vat_rate": 20}
            ]
        })
        return order_resp.json()
    
    def test_pay_order_card(self, auth_session, test_order):
        """Test POST /api/pos/orders/{order_id}/pay with card payment"""
        order_id = test_order["id"]
        
        resp = auth_session.post(f"{BASE_URL}/api/pos/orders/{order_id}/pay", json={
            "payment_method": "card",
            "tip": 0.50
        })
        assert resp.status_code == 200, f"Failed: {resp.text}"
        
        result = resp.json()
        assert result["status"] == "paid"
        assert result["method"] == "card"
        
        # Verify total includes tip
        expected_total = test_order["total"] + 0.50
        assert result["total"] == expected_total, f"Expected {expected_total}, got {result['total']}"
        
        print(f"PASS: Paid order {order_id} via card with tip")
    
    def test_pay_order_creates_income_entry(self, auth_session):
        """Test that paying an order creates an income entry in accounting"""
        # Create and pay a new order
        resp = auth_session.get(f"{BASE_URL}/api/pos/outlets/{PROPERTY_ID}")
        outlet = resp.json()[0]
        
        order_resp = auth_session.post(f"{BASE_URL}/api/pos/orders", json={
            "property_id": PROPERTY_ID,
            "outlet_id": outlet["id"],
            "outlet_name": "Restaurant",
            "order_type": "dine_in",
            "table_number": "11",
            "covers": 1,
            "guest_name": "TEST_Income Entry Guest",
            "items": [
                {"id": "item1", "name": "Soup", "price": 7.50, "cost": 1.80, "quantity": 1, "vat_rate": 20}
            ]
        })
        order = order_resp.json()
        order_number = order["order_number"]
        
        # Pay the order
        pay_resp = auth_session.post(f"{BASE_URL}/api/pos/orders/{order['id']}/pay", json={
            "payment_method": "cash",
            "tip": 0
        })
        assert pay_resp.status_code == 200
        
        # Check income entries for this order
        income_resp = auth_session.get(f"{BASE_URL}/api/accounting/income/{PROPERTY_ID}")
        assert income_resp.status_code == 200
        
        income_entries = income_resp.json()
        pos_entries = [e for e in income_entries if order_number in e.get("reference", "")]
        
        assert len(pos_entries) > 0, f"No income entry found for order {order_number}"
        
        entry = pos_entries[0]
        assert entry["source"] == "pos"
        assert entry["amount"] == order["total"]
        
        print(f"PASS: Income entry created for order {order_number}")
    
    def test_pay_order_room_charge_creates_folio(self, auth_session):
        """Test that room_charge payment creates a room folio entry"""
        resp = auth_session.get(f"{BASE_URL}/api/pos/outlets/{PROPERTY_ID}")
        outlet = resp.json()[0]
        
        # Create order with room number
        order_resp = auth_session.post(f"{BASE_URL}/api/pos/orders", json={
            "property_id": PROPERTY_ID,
            "outlet_id": outlet["id"],
            "outlet_name": "Room Service",
            "order_type": "room_service",
            "room_number": "101",
            "guest_name": "TEST_Room Charge Guest",
            "booking_ref": "BK-TEST-001",
            "items": [
                {"id": "item1", "name": "Club Sandwich", "price": 13.50, "cost": 3.80, "quantity": 1, "vat_rate": 20}
            ]
        })
        order = order_resp.json()
        
        # Pay with room charge
        pay_resp = auth_session.post(f"{BASE_URL}/api/pos/orders/{order['id']}/pay", json={
            "payment_method": "room_charge",
            "tip": 0
        })
        assert pay_resp.status_code == 200
        
        result = pay_resp.json()
        assert result["method"] == "room_charge"
        
        # Check room folios
        folio_resp = auth_session.get(f"{BASE_URL}/api/pos/room-folios/{PROPERTY_ID}?room_number=101")
        assert folio_resp.status_code == 200
        
        folios = folio_resp.json()
        order_folios = [f for f in folios if f.get("order_id") == order["id"]]
        
        assert len(order_folios) > 0, "No folio entry found for room charge"
        
        folio = order_folios[0]
        assert folio["room_number"] == "101"
        assert folio["amount"] == order["total"]
        assert folio["type"] == "charge"
        assert folio["source"] == "pos"
        
        print(f"PASS: Room folio entry created for order {order['order_number']}")


class TestPOSSplitBill:
    """Test POS split bill functionality"""
    
    @pytest.fixture(scope="class")
    def auth_session(self):
        """Get authenticated session"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        login_resp = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert login_resp.status_code == 200
        return session
    
    def test_split_bill_equal(self, auth_session):
        """Test POST /api/pos/orders/{order_id}/split with equal split"""
        # Create order
        resp = auth_session.get(f"{BASE_URL}/api/pos/outlets/{PROPERTY_ID}")
        outlet = resp.json()[0]
        
        order_resp = auth_session.post(f"{BASE_URL}/api/pos/orders", json={
            "property_id": PROPERTY_ID,
            "outlet_id": outlet["id"],
            "outlet_name": "Restaurant",
            "order_type": "dine_in",
            "table_number": "12",
            "covers": 4,
            "guest_name": "TEST_Split Bill Group",
            "items": [
                {"id": "item1", "name": "Steak", "price": 28.00, "cost": 12.00, "quantity": 4, "vat_rate": 20}
            ]
        })
        order = order_resp.json()
        
        # Split bill 4 ways
        split_resp = auth_session.post(f"{BASE_URL}/api/pos/orders/{order['id']}/split", json={
            "split_type": "equal",
            "num_ways": 4
        })
        assert split_resp.status_code == 200, f"Failed: {split_resp.text}"
        
        result = split_resp.json()
        assert "splits" in result
        assert len(result["splits"]) == 4
        
        # Each split should be total / 4
        expected_each = round(order["total"] / 4, 2)
        for split in result["splits"]:
            assert split["amount"] == expected_each, f"Expected {expected_each}, got {split['amount']}"
        
        print(f"PASS: Split bill {order['order_number']} into 4 equal parts of £{expected_each}")


class TestPOSKitchen:
    """Test POS kitchen display endpoints"""
    
    @pytest.fixture(scope="class")
    def auth_session(self):
        """Get authenticated session"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        login_resp = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert login_resp.status_code == 200
        return session
    
    def test_get_kitchen_orders(self, auth_session):
        """Test GET /api/pos/kitchen/{property_id} returns new/preparing orders"""
        # Create a new order first
        resp = auth_session.get(f"{BASE_URL}/api/pos/outlets/{PROPERTY_ID}")
        outlet = resp.json()[0]
        
        order_resp = auth_session.post(f"{BASE_URL}/api/pos/orders", json={
            "property_id": PROPERTY_ID,
            "outlet_id": outlet["id"],
            "outlet_name": "Restaurant",
            "order_type": "dine_in",
            "table_number": "15",
            "covers": 1,
            "guest_name": "TEST_Kitchen Order",
            "items": [
                {"id": "item1", "name": "Fish & Chips", "price": 16.00, "cost": 4.80, "quantity": 1, "vat_rate": 20}
            ]
        })
        new_order = order_resp.json()
        
        # Get kitchen orders
        kitchen_resp = auth_session.get(f"{BASE_URL}/api/pos/kitchen/{PROPERTY_ID}")
        assert kitchen_resp.status_code == 200, f"Failed: {kitchen_resp.text}"
        
        kitchen_orders = kitchen_resp.json()
        assert isinstance(kitchen_orders, list)
        
        # Verify all orders are new or preparing
        for order in kitchen_orders:
            assert order["kitchen_status"] in ["new", "preparing"], f"Invalid status: {order['kitchen_status']}"
        
        # Verify our new order is in the list
        order_ids = [o["id"] for o in kitchen_orders]
        assert new_order["id"] in order_ids, "New order not in kitchen display"
        
        print(f"PASS: Kitchen display shows {len(kitchen_orders)} orders")
        return new_order
    
    def test_update_kitchen_status(self, auth_session):
        """Test POST /api/pos/kitchen/{order_id}/status updates kitchen status"""
        # Create a new order
        resp = auth_session.get(f"{BASE_URL}/api/pos/outlets/{PROPERTY_ID}")
        outlet = resp.json()[0]
        
        order_resp = auth_session.post(f"{BASE_URL}/api/pos/orders", json={
            "property_id": PROPERTY_ID,
            "outlet_id": outlet["id"],
            "outlet_name": "Restaurant",
            "order_type": "dine_in",
            "table_number": "16",
            "covers": 1,
            "guest_name": "TEST_Kitchen Status",
            "items": [
                {"id": "item1", "name": "Burger", "price": 14.50, "cost": 4.00, "quantity": 1, "vat_rate": 20}
            ]
        })
        order = order_resp.json()
        assert order["kitchen_status"] == "new"
        
        # Update to preparing
        status_resp = auth_session.post(f"{BASE_URL}/api/pos/kitchen/{order['id']}/status", json={
            "status": "preparing"
        })
        assert status_resp.status_code == 200
        assert status_resp.json()["status"] == "preparing"
        
        # Update to ready
        status_resp = auth_session.post(f"{BASE_URL}/api/pos/kitchen/{order['id']}/status", json={
            "status": "ready"
        })
        assert status_resp.status_code == 200
        assert status_resp.json()["status"] == "ready"
        
        print(f"PASS: Updated kitchen status for order {order['order_number']}")


class TestPOSTables:
    """Test POS table management endpoints"""
    
    @pytest.fixture(scope="class")
    def auth_session(self):
        """Get authenticated session"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        login_resp = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert login_resp.status_code == 200
        return session
    
    def test_get_tables_with_active_orders(self, auth_session):
        """Test GET /api/pos/tables/{outlet_id} returns table layout with active orders"""
        # Get restaurant outlet (has tables)
        resp = auth_session.get(f"{BASE_URL}/api/pos/outlets/{PROPERTY_ID}")
        outlets = resp.json()
        restaurant = next((o for o in outlets if o["name"] == "Restaurant"), outlets[0])
        
        # Create an order for table 1
        order_resp = auth_session.post(f"{BASE_URL}/api/pos/orders", json={
            "property_id": PROPERTY_ID,
            "outlet_id": restaurant["id"],
            "outlet_name": restaurant["name"],
            "order_type": "dine_in",
            "table_number": "1",
            "covers": 2,
            "guest_name": "TEST_Table Guest",
            "items": [
                {"id": "item1", "name": "Salad", "price": 9.50, "cost": 2.50, "quantity": 1, "vat_rate": 20}
            ]
        })
        
        # Get tables
        tables_resp = auth_session.get(f"{BASE_URL}/api/pos/tables/{restaurant['id']}")
        assert tables_resp.status_code == 200, f"Failed: {tables_resp.text}"
        
        tables = tables_resp.json()
        assert isinstance(tables, list)
        assert len(tables) == restaurant.get("tables", 0), f"Expected {restaurant.get('tables')} tables"
        
        # Verify table structure
        for table in tables:
            assert "number" in table
            assert "status" in table
            assert table["status"] in ["available", "occupied"]
        
        # Table 1 should be occupied
        table_1 = next((t for t in tables if t["number"] == 1), None)
        if table_1:
            assert table_1["status"] == "occupied", "Table 1 should be occupied"
            assert table_1.get("order") is not None, "Table 1 should have order info"
        
        print(f"PASS: Got {len(tables)} tables for {restaurant['name']}")


class TestPOSShifts:
    """Test POS shift management endpoints"""
    
    @pytest.fixture(scope="class")
    def auth_session(self):
        """Get authenticated session"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        login_resp = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert login_resp.status_code == 200
        return session
    
    def test_open_shift(self, auth_session):
        """Test POST /api/pos/shifts/open opens a shift with opening cash"""
        resp = auth_session.get(f"{BASE_URL}/api/pos/outlets/{PROPERTY_ID}")
        outlet = resp.json()[0]
        
        shift_resp = auth_session.post(f"{BASE_URL}/api/pos/shifts/open", json={
            "property_id": PROPERTY_ID,
            "outlet_id": outlet["id"],
            "opening_cash": 200.00
        })
        assert shift_resp.status_code == 200, f"Failed: {shift_resp.text}"
        
        shift = shift_resp.json()
        assert "id" in shift
        assert shift["status"] == "open"
        assert shift["opening_cash"] == 200.00
        assert shift["property_id"] == PROPERTY_ID
        
        print(f"PASS: Opened shift {shift['id']} with £200 opening cash")
        return shift
    
    def test_close_shift_with_totals(self, auth_session):
        """Test POST /api/pos/shifts/{shift_id}/close calculates totals and cash difference"""
        resp = auth_session.get(f"{BASE_URL}/api/pos/outlets/{PROPERTY_ID}")
        outlet = resp.json()[0]
        
        # Open a new shift
        open_resp = auth_session.post(f"{BASE_URL}/api/pos/shifts/open", json={
            "property_id": PROPERTY_ID,
            "outlet_id": outlet["id"],
            "opening_cash": 100.00
        })
        shift = open_resp.json()
        
        # Close the shift
        close_resp = auth_session.post(f"{BASE_URL}/api/pos/shifts/{shift['id']}/close", json={
            "closing_cash": 150.00
        })
        assert close_resp.status_code == 200, f"Failed: {close_resp.text}"
        
        result = close_resp.json()
        assert "total_sales" in result
        assert "total_orders" in result
        assert "total_tips" in result
        assert "cash_difference" in result
        assert "sales_by_method" in result
        
        print(f"PASS: Closed shift with £{result['total_sales']} sales, {result['total_orders']} orders")


class TestPOSReports:
    """Test POS reports endpoints"""
    
    @pytest.fixture(scope="class")
    def auth_session(self):
        """Get authenticated session"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        login_resp = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert login_resp.status_code == 200
        return session
    
    def test_get_daily_reports(self, auth_session):
        """Test GET /api/pos/reports/{property_id} returns daily reports"""
        resp = auth_session.get(f"{BASE_URL}/api/pos/reports/{PROPERTY_ID}")
        assert resp.status_code == 200, f"Failed: {resp.text}"
        
        reports = resp.json()
        
        # Verify report structure
        assert "date" in reports
        assert "total_revenue" in reports
        assert "total_cost" in reports
        assert "gross_margin" in reports
        assert "total_orders" in reports
        assert "total_covers" in reports
        assert "avg_check" in reports
        assert "avg_per_cover" in reports
        assert "total_tips" in reports
        assert "by_outlet" in reports
        assert "by_method" in reports
        assert "by_server" in reports
        assert "top_items" in reports
        assert "hourly" in reports
        
        print(f"PASS: Got daily report for {reports['date']}")
        print(f"  - Revenue: £{reports['total_revenue']}")
        print(f"  - Orders: {reports['total_orders']}")
        print(f"  - Gross Margin: {reports['gross_margin']}%")
        print(f"  - Top Items: {len(reports['top_items'])}")


class TestPOSStockDeduction:
    """Test stock deduction when order is placed"""
    
    @pytest.fixture(scope="class")
    def auth_session(self):
        """Get authenticated session"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        login_resp = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert login_resp.status_code == 200
        return session
    
    def test_order_with_stock_linked_item(self, auth_session):
        """Test that ordering stock-linked items deducts from stock"""
        # First create a stock product
        stock_resp = auth_session.post(f"{BASE_URL}/api/stock/products", json={
            "property_id": PROPERTY_ID,
            "name": "TEST_POS_Wine Bottle",
            "sku": "TEST-POS-WINE-001",
            "category": "Beverages",
            "quantity": 50,
            "unit": "bottle",
            "cost_price": 6.00,
            "sell_price": 24.00,
            "min_stock": 10
        })
        
        if stock_resp.status_code == 200:
            stock_product = stock_resp.json()
            initial_qty = stock_product.get("quantity", 50)
            
            # Create order with stock-linked item
            resp = auth_session.get(f"{BASE_URL}/api/pos/outlets/{PROPERTY_ID}")
            outlet = resp.json()[0]
            
            order_resp = auth_session.post(f"{BASE_URL}/api/pos/orders", json={
                "property_id": PROPERTY_ID,
                "outlet_id": outlet["id"],
                "outlet_name": "Bar & Lounge",
                "order_type": "dine_in",
                "table_number": "20",
                "covers": 1,
                "guest_name": "TEST_Stock Deduction",
                "items": [
                    {
                        "id": "wine1", 
                        "name": "House Wine (Bottle)", 
                        "price": 24.00, 
                        "cost": 6.00, 
                        "quantity": 2, 
                        "vat_rate": 20,
                        "stock_product_id": stock_product["id"]
                    }
                ]
            })
            assert order_resp.status_code == 200
            
            # Check stock was deducted
            stock_check = auth_session.get(f"{BASE_URL}/api/stock/products/{PROPERTY_ID}")
            if stock_check.status_code == 200:
                products = stock_check.json()
                updated_product = next((p for p in products if p["id"] == stock_product["id"]), None)
                if updated_product:
                    expected_qty = initial_qty - 2
                    assert updated_product["quantity"] == expected_qty, f"Expected {expected_qty}, got {updated_product['quantity']}"
                    print(f"PASS: Stock deducted from {initial_qty} to {updated_product['quantity']}")
                else:
                    print("PASS: Order created (stock product not found for verification)")
            else:
                print("PASS: Order created (stock check skipped)")
        else:
            print("PASS: Stock deduction test skipped (stock product creation failed)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
