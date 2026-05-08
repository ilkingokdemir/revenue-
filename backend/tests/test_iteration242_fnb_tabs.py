"""
Batch 31 — F&B Tab Transfer: Cross-outlet guest tab management (bar→restaurant→room folio)

Tests:
- POST /api/fnb/tabs - Open tab with outlet/guest/table/party_size/booking_id validation
- GET /api/fnb/tabs/{property_id} - List tabs with by_outlet aggregation
- GET /api/fnb/tabs/detail/{tab_id} - Single tab detail
- POST /api/fnb/tabs/{tab_id}/items - Add items with qty/price validation
- DELETE /api/fnb/tabs/{tab_id}/items/{item_id} - Remove item, recompute totals
- POST /api/fnb/tabs/{tab_id}/transfer - Transfer to new outlet with audit log
- POST /api/fnb/tabs/{tab_id}/close - Close with payment/tip/discount, room_folio requires booking
- GET /api/fnb/tabs/transfers/{property_id} - Transfer audit log
- GET /api/fnb/tabs/dashboard/{property_id} - KPIs (open_tabs, closed_today, revenue, tips, transfers)
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

VALID_OUTLETS = ["bar", "pool_bar", "restaurant", "rooftop", "spa", "poolside", "lounge", "in_room"]
VALID_PAYMENTS = ["cash", "card", "room_folio", "complimentary", "voucher"]


@pytest.fixture(scope="module")
def auth_session():
    """Login and return authenticated session"""
    session = requests.Session()
    login_resp = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@hotelbox.com",
        "password": "HotelAdmin2026!"
    })
    assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
    return session


@pytest.fixture(scope="module")
def test_booking(auth_session):
    """Create a test booking for room_folio tests"""
    booking_data = {
        "property_id": "default",
        "guest_name": "TEST_FnbFolioGuest",
        "guest_email": f"fnb_test_{uuid.uuid4().hex[:6]}@test.com",
        "room_type_id": "standard",
        "check_in": "2026-02-01",
        "check_out": "2026-02-03",
        "total_price": 200,
        "status": "confirmed"
    }
    resp = auth_session.post(f"{BASE_URL}/api/bookings", json=booking_data)
    if resp.status_code == 201:
        return resp.json()
    # If booking creation fails, return None (some tests will skip)
    return None


class TestFnbTabsAuth:
    """Test authentication requirements"""
    
    def test_open_tab_requires_auth(self):
        """POST /api/fnb/tabs requires authentication"""
        resp = requests.post(f"{BASE_URL}/api/fnb/tabs", json={
            "property_id": "default",
            "outlet": "bar"
        })
        assert resp.status_code == 401
    
    def test_list_tabs_requires_auth(self):
        """GET /api/fnb/tabs/{property_id} requires authentication"""
        resp = requests.get(f"{BASE_URL}/api/fnb/tabs/default")
        assert resp.status_code == 401
    
    def test_dashboard_requires_auth(self):
        """GET /api/fnb/tabs/dashboard/{property_id} requires authentication"""
        resp = requests.get(f"{BASE_URL}/api/fnb/tabs/dashboard/default")
        assert resp.status_code == 401


class TestOpenTab:
    """Test POST /api/fnb/tabs - Open new tab"""
    
    def test_open_tab_invalid_outlet(self, auth_session):
        """Invalid outlet returns 400 with valid list"""
        resp = auth_session.post(f"{BASE_URL}/api/fnb/tabs", json={
            "property_id": "default",
            "outlet": "alien"
        })
        assert resp.status_code == 400
        assert "outlet must be one of" in resp.json()["detail"]
    
    def test_open_tab_party_size_too_small(self, auth_session):
        """party_size < 1 returns 400"""
        resp = auth_session.post(f"{BASE_URL}/api/fnb/tabs", json={
            "property_id": "default",
            "outlet": "bar",
            "party_size": 0
        })
        assert resp.status_code == 400
        assert "party_size must be 1..50" in resp.json()["detail"]
    
    def test_open_tab_party_size_too_large(self, auth_session):
        """party_size > 50 returns 400"""
        resp = auth_session.post(f"{BASE_URL}/api/fnb/tabs", json={
            "property_id": "default",
            "outlet": "bar",
            "party_size": 51
        })
        assert resp.status_code == 400
        assert "party_size must be 1..50" in resp.json()["detail"]
    
    def test_open_tab_invalid_booking_id(self, auth_session):
        """Non-existent booking_id returns 404"""
        resp = auth_session.post(f"{BASE_URL}/api/fnb/tabs", json={
            "property_id": "default",
            "outlet": "bar",
            "booking_id": "nonexistent-booking-id"
        })
        assert resp.status_code == 404
        assert "Booking not found" in resp.json()["detail"]
    
    def test_open_tab_success(self, auth_session):
        """Valid tab creation returns doc with auto ref"""
        resp = auth_session.post(f"{BASE_URL}/api/fnb/tabs", json={
            "property_id": "default",
            "outlet": "pool_bar",
            "guest_name": "TEST_Anna",
            "table_number": "P5",
            "party_size": 3
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["outlet"] == "pool_bar"
        assert data["guest_name"] == "TEST_Anna"
        assert data["party_size"] == 3
        assert data["status"] == "open"
        assert data["ref"].startswith("TAB-")
        assert "id" in data
        assert data["subtotal"] == 0
        assert data["total"] == 0
        assert len(data["transfer_history"]) == 1
        return data["id"]


class TestListTabs:
    """Test GET /api/fnb/tabs/{property_id}"""
    
    def test_list_tabs_with_aggregation(self, auth_session):
        """List returns rows and by_outlet aggregation"""
        resp = auth_session.get(f"{BASE_URL}/api/fnb/tabs/default")
        assert resp.status_code == 200
        data = resp.json()
        assert "rows" in data
        assert "count" in data
        assert "by_outlet" in data
        assert isinstance(data["by_outlet"], dict)
    
    def test_list_tabs_filter_by_outlet(self, auth_session):
        """Filter by outlet works"""
        resp = auth_session.get(f"{BASE_URL}/api/fnb/tabs/default?outlet=pool_bar")
        assert resp.status_code == 200
        data = resp.json()
        for row in data["rows"]:
            assert row["outlet"] == "pool_bar"


class TestTabDetail:
    """Test GET /api/fnb/tabs/detail/{tab_id}"""
    
    def test_tab_detail_not_found(self, auth_session):
        """Non-existent tab returns 404"""
        resp = auth_session.get(f"{BASE_URL}/api/fnb/tabs/detail/nonexistent-tab-id")
        assert resp.status_code == 404
        assert "Tab not found" in resp.json()["detail"]
    
    def test_tab_detail_success(self, auth_session):
        """Get existing tab detail"""
        # First create a tab
        create_resp = auth_session.post(f"{BASE_URL}/api/fnb/tabs", json={
            "property_id": "default",
            "outlet": "restaurant",
            "guest_name": "TEST_DetailGuest"
        })
        assert create_resp.status_code == 200
        tab_id = create_resp.json()["id"]
        
        # Get detail
        resp = auth_session.get(f"{BASE_URL}/api/fnb/tabs/detail/{tab_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == tab_id
        assert data["guest_name"] == "TEST_DetailGuest"
        assert data["outlet"] == "restaurant"


class TestAddItems:
    """Test POST /api/fnb/tabs/{tab_id}/items"""
    
    @pytest.fixture
    def open_tab(self, auth_session):
        """Create an open tab for item tests"""
        resp = auth_session.post(f"{BASE_URL}/api/fnb/tabs", json={
            "property_id": "default",
            "outlet": "bar",
            "guest_name": "TEST_ItemsGuest"
        })
        assert resp.status_code == 200
        return resp.json()
    
    def test_add_item_qty_zero(self, auth_session, open_tab):
        """qty <= 0 returns 400"""
        resp = auth_session.post(f"{BASE_URL}/api/fnb/tabs/{open_tab['id']}/items", json={
            "name": "Mojito",
            "qty": 0,
            "unit_price": 12
        })
        assert resp.status_code == 400
        assert "qty must be > 0" in resp.json()["detail"]
    
    def test_add_item_negative_price(self, auth_session, open_tab):
        """unit_price < 0 returns 400"""
        resp = auth_session.post(f"{BASE_URL}/api/fnb/tabs/{open_tab['id']}/items", json={
            "name": "Mojito",
            "qty": 1,
            "unit_price": -5
        })
        assert resp.status_code == 400
        assert "unit_price must be >= 0" in resp.json()["detail"]
    
    def test_add_item_success(self, auth_session, open_tab):
        """Add item recomputes subtotal and total"""
        # Add first item
        resp1 = auth_session.post(f"{BASE_URL}/api/fnb/tabs/{open_tab['id']}/items", json={
            "name": "Mojito",
            "qty": 2,
            "unit_price": 12,
            "category": "beverage"
        })
        assert resp1.status_code == 200
        data1 = resp1.json()
        assert data1["subtotal"] == 24  # 2 * 12
        assert data1["total"] == 24
        assert data1["items_count"] == 1
        
        # Add second item
        resp2 = auth_session.post(f"{BASE_URL}/api/fnb/tabs/{open_tab['id']}/items", json={
            "name": "Club Sandwich",
            "qty": 3,
            "unit_price": 18,
            "category": "food",
            "note": "No mayo"
        })
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data2["subtotal"] == 78  # 24 + (3 * 18)
        assert data2["items_count"] == 2
    
    def test_add_item_to_nonexistent_tab(self, auth_session):
        """Adding to non-existent tab returns 404"""
        resp = auth_session.post(f"{BASE_URL}/api/fnb/tabs/nonexistent-tab/items", json={
            "name": "Test",
            "qty": 1,
            "unit_price": 10
        })
        assert resp.status_code == 404


class TestRemoveItems:
    """Test DELETE /api/fnb/tabs/{tab_id}/items/{item_id}"""
    
    def test_remove_item_success(self, auth_session):
        """Remove item recomputes totals"""
        # Create tab
        tab_resp = auth_session.post(f"{BASE_URL}/api/fnb/tabs", json={
            "property_id": "default",
            "outlet": "lounge",
            "guest_name": "TEST_RemoveItemGuest"
        })
        tab_id = tab_resp.json()["id"]
        
        # Add items
        item1_resp = auth_session.post(f"{BASE_URL}/api/fnb/tabs/{tab_id}/items", json={
            "name": "Wine",
            "qty": 1,
            "unit_price": 25
        })
        item1_id = item1_resp.json()["item"]["id"]
        
        auth_session.post(f"{BASE_URL}/api/fnb/tabs/{tab_id}/items", json={
            "name": "Cheese Board",
            "qty": 1,
            "unit_price": 15
        })
        
        # Remove first item
        del_resp = auth_session.delete(f"{BASE_URL}/api/fnb/tabs/{tab_id}/items/{item1_id}")
        assert del_resp.status_code == 200
        data = del_resp.json()
        assert data["removed"] == True
        assert data["subtotal"] == 15  # Only cheese board remains
    
    def test_remove_nonexistent_item(self, auth_session):
        """Removing non-existent item returns 404"""
        # Create tab
        tab_resp = auth_session.post(f"{BASE_URL}/api/fnb/tabs", json={
            "property_id": "default",
            "outlet": "bar",
            "guest_name": "TEST_RemoveNonexistent"
        })
        tab_id = tab_resp.json()["id"]
        
        resp = auth_session.delete(f"{BASE_URL}/api/fnb/tabs/{tab_id}/items/nonexistent-item-id")
        assert resp.status_code == 404
        assert "Item not found" in resp.json()["detail"]


class TestTransferTab:
    """Test POST /api/fnb/tabs/{tab_id}/transfer"""
    
    def test_transfer_invalid_outlet(self, auth_session):
        """Invalid new_outlet returns 400"""
        # Create tab
        tab_resp = auth_session.post(f"{BASE_URL}/api/fnb/tabs", json={
            "property_id": "default",
            "outlet": "bar",
            "guest_name": "TEST_TransferInvalid"
        })
        tab_id = tab_resp.json()["id"]
        
        resp = auth_session.post(f"{BASE_URL}/api/fnb/tabs/{tab_id}/transfer", json={
            "new_outlet": "invalid_outlet"
        })
        assert resp.status_code == 400
        assert "new_outlet must be one of" in resp.json()["detail"]
    
    def test_transfer_same_outlet(self, auth_session):
        """Transfer to same outlet returns 400"""
        # Create tab at bar
        tab_resp = auth_session.post(f"{BASE_URL}/api/fnb/tabs", json={
            "property_id": "default",
            "outlet": "bar",
            "guest_name": "TEST_TransferSame"
        })
        tab_id = tab_resp.json()["id"]
        
        resp = auth_session.post(f"{BASE_URL}/api/fnb/tabs/{tab_id}/transfer", json={
            "new_outlet": "bar"
        })
        assert resp.status_code == 400
        assert "Already at this outlet" in resp.json()["detail"]
    
    def test_transfer_success(self, auth_session):
        """Successful transfer updates outlet and adds history"""
        # Create tab at pool_bar
        tab_resp = auth_session.post(f"{BASE_URL}/api/fnb/tabs", json={
            "property_id": "default",
            "outlet": "pool_bar",
            "guest_name": "TEST_TransferSuccess"
        })
        tab_id = tab_resp.json()["id"]
        
        # Add an item
        auth_session.post(f"{BASE_URL}/api/fnb/tabs/{tab_id}/items", json={
            "name": "Pina Colada",
            "qty": 1,
            "unit_price": 14
        })
        
        # Transfer to restaurant
        resp = auth_session.post(f"{BASE_URL}/api/fnb/tabs/{tab_id}/transfer", json={
            "new_outlet": "restaurant",
            "new_table_number": "R7"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["transferred"] == True
        assert data["from"] == "pool_bar"
        assert data["to"] == "restaurant"
        assert data["history_len"] == 2  # Initial + transfer
        
        # Verify tab detail
        detail_resp = auth_session.get(f"{BASE_URL}/api/fnb/tabs/detail/{tab_id}")
        detail = detail_resp.json()
        assert detail["outlet"] == "restaurant"
        assert detail["table_number"] == "R7"
        assert len(detail["transfer_history"]) == 2


class TestCloseTab:
    """Test POST /api/fnb/tabs/{tab_id}/close"""
    
    def test_close_invalid_payment(self, auth_session):
        """Invalid payment_method returns 400"""
        # Create tab
        tab_resp = auth_session.post(f"{BASE_URL}/api/fnb/tabs", json={
            "property_id": "default",
            "outlet": "bar",
            "guest_name": "TEST_CloseInvalidPayment"
        })
        tab_id = tab_resp.json()["id"]
        
        resp = auth_session.post(f"{BASE_URL}/api/fnb/tabs/{tab_id}/close", json={
            "payment_method": "bitcoin"
        })
        assert resp.status_code == 400
        assert "payment_method must be one of" in resp.json()["detail"]
    
    def test_close_discount_too_high(self, auth_session):
        """discount_pct > 50 returns 400"""
        tab_resp = auth_session.post(f"{BASE_URL}/api/fnb/tabs", json={
            "property_id": "default",
            "outlet": "bar",
            "guest_name": "TEST_CloseHighDiscount"
        })
        tab_id = tab_resp.json()["id"]
        
        resp = auth_session.post(f"{BASE_URL}/api/fnb/tabs/{tab_id}/close", json={
            "payment_method": "cash",
            "discount_pct": 60
        })
        assert resp.status_code == 400
        assert "discount_pct must be 0..50" in resp.json()["detail"]
    
    def test_close_negative_tip(self, auth_session):
        """tip_amount < 0 returns 400"""
        tab_resp = auth_session.post(f"{BASE_URL}/api/fnb/tabs", json={
            "property_id": "default",
            "outlet": "bar",
            "guest_name": "TEST_CloseNegativeTip"
        })
        tab_id = tab_resp.json()["id"]
        
        resp = auth_session.post(f"{BASE_URL}/api/fnb/tabs/{tab_id}/close", json={
            "payment_method": "cash",
            "tip_amount": -5
        })
        assert resp.status_code == 400
        assert "tip_amount must be >= 0" in resp.json()["detail"]
    
    def test_close_room_folio_without_booking(self, auth_session):
        """room_folio without booking_id returns 400"""
        tab_resp = auth_session.post(f"{BASE_URL}/api/fnb/tabs", json={
            "property_id": "default",
            "outlet": "restaurant",
            "guest_name": "TEST_CloseNoBooking"
        })
        tab_id = tab_resp.json()["id"]
        
        resp = auth_session.post(f"{BASE_URL}/api/fnb/tabs/{tab_id}/close", json={
            "payment_method": "room_folio"
        })
        assert resp.status_code == 400
        assert "Cannot charge to room folio: no booking linked" in resp.json()["detail"]
    
    def test_close_with_cash_success(self, auth_session):
        """Close with cash, tip, and discount calculates total correctly"""
        # Create tab
        tab_resp = auth_session.post(f"{BASE_URL}/api/fnb/tabs", json={
            "property_id": "default",
            "outlet": "rooftop",
            "guest_name": "TEST_CloseCash"
        })
        tab_id = tab_resp.json()["id"]
        
        # Add items totaling £100
        auth_session.post(f"{BASE_URL}/api/fnb/tabs/{tab_id}/items", json={
            "name": "Wagyu Steak",
            "qty": 2,
            "unit_price": 50
        })
        
        # Close with 10% discount and £5 tip
        # Expected: 100 - 10 + 5 = 95
        resp = auth_session.post(f"{BASE_URL}/api/fnb/tabs/{tab_id}/close", json={
            "payment_method": "cash",
            "tip_amount": 5,
            "discount_pct": 10
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["closed"] == True
        assert data["total"] == 95
        assert data["payment_method"] == "cash"
        assert data["charged_to_folio"] == False
        
        # Verify tab is now closed
        detail_resp = auth_session.get(f"{BASE_URL}/api/fnb/tabs/detail/{tab_id}")
        detail = detail_resp.json()
        assert detail["status"] == "closed"
    
    def test_close_room_folio_with_booking(self, auth_session, test_booking):
        """room_folio with valid booking_id writes to guest_folio_charges"""
        if not test_booking:
            pytest.skip("Test booking not available")
        
        # Create tab with booking_id
        tab_resp = auth_session.post(f"{BASE_URL}/api/fnb/tabs", json={
            "property_id": "default",
            "outlet": "in_room",
            "guest_name": "TEST_FolioGuest",
            "booking_id": test_booking["id"]
        })
        assert tab_resp.status_code == 200
        tab_id = tab_resp.json()["id"]
        
        # Add item
        auth_session.post(f"{BASE_URL}/api/fnb/tabs/{tab_id}/items", json={
            "name": "Room Service Breakfast",
            "qty": 1,
            "unit_price": 35
        })
        
        # Close with room_folio
        resp = auth_session.post(f"{BASE_URL}/api/fnb/tabs/{tab_id}/close", json={
            "payment_method": "room_folio"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["charged_to_folio"] == True


class TestTransfersAudit:
    """Test GET /api/fnb/tabs/transfers/{property_id}"""
    
    def test_transfers_list(self, auth_session):
        """List transfer audit log"""
        resp = auth_session.get(f"{BASE_URL}/api/fnb/tabs/transfers/default")
        assert resp.status_code == 200
        data = resp.json()
        assert "rows" in data
        assert "count" in data
        # Each row should have from_outlet, to_outlet, tab_ref
        if data["count"] > 0:
            row = data["rows"][0]
            assert "from_outlet" in row
            assert "to_outlet" in row
            assert "tab_ref" in row


class TestDashboard:
    """Test GET /api/fnb/tabs/dashboard/{property_id}"""
    
    def test_dashboard_kpis(self, auth_session):
        """Dashboard returns all required KPIs"""
        resp = auth_session.get(f"{BASE_URL}/api/fnb/tabs/dashboard/default")
        assert resp.status_code == 200
        data = resp.json()
        
        # Check all required fields
        assert "open_tabs" in data
        assert "closed_today" in data
        assert "revenue_today" in data
        assert "tips_today" in data
        assert "transfers_today" in data
        assert "by_outlet_today" in data
        assert "by_payment_today" in data
        
        # Types
        assert isinstance(data["open_tabs"], int)
        assert isinstance(data["closed_today"], int)
        assert isinstance(data["revenue_today"], (int, float))
        assert isinstance(data["tips_today"], (int, float))
        assert isinstance(data["transfers_today"], int)
        assert isinstance(data["by_outlet_today"], dict)
        assert isinstance(data["by_payment_today"], dict)


class TestFullWorkflow:
    """Test complete F&B tab workflow: open → add items → transfer → add more → close"""
    
    def test_complete_workflow(self, auth_session):
        """Full workflow as described by main agent"""
        # 1. Open tab at pool_bar for Anna, 3 people
        tab_resp = auth_session.post(f"{BASE_URL}/api/fnb/tabs", json={
            "property_id": "default",
            "outlet": "pool_bar",
            "guest_name": "TEST_WorkflowAnna",
            "party_size": 3
        })
        assert tab_resp.status_code == 200
        tab = tab_resp.json()
        tab_id = tab["id"]
        assert tab["ref"].startswith("TAB-")
        
        # 2. Add Mojito x2 @ £12 = £24
        auth_session.post(f"{BASE_URL}/api/fnb/tabs/{tab_id}/items", json={
            "name": "Mojito",
            "qty": 2,
            "unit_price": 12,
            "category": "beverage"
        })
        
        # 3. Add Pina Colada x1 @ £14 = £14
        auth_session.post(f"{BASE_URL}/api/fnb/tabs/{tab_id}/items", json={
            "name": "Pina Colada",
            "qty": 1,
            "unit_price": 14,
            "category": "beverage"
        })
        
        # 4. Add Club Sandwich x3 @ £18 = £54
        item_resp = auth_session.post(f"{BASE_URL}/api/fnb/tabs/{tab_id}/items", json={
            "name": "Club Sandwich",
            "qty": 3,
            "unit_price": 18,
            "category": "food"
        })
        assert item_resp.json()["subtotal"] == 92  # 24 + 14 + 54
        
        # 5. Transfer to restaurant table R7
        transfer_resp = auth_session.post(f"{BASE_URL}/api/fnb/tabs/{tab_id}/transfer", json={
            "new_outlet": "restaurant",
            "new_table_number": "R7"
        })
        assert transfer_resp.status_code == 200
        assert transfer_resp.json()["history_len"] == 2
        
        # 6. Add Wagyu Steak x2 @ £85 = £170
        steak_resp = auth_session.post(f"{BASE_URL}/api/fnb/tabs/{tab_id}/items", json={
            "name": "Wagyu Steak",
            "qty": 2,
            "unit_price": 85,
            "category": "food"
        })
        assert steak_resp.json()["subtotal"] == 262  # 92 + 170
        
        # 7. Close with cash + £5 tip + 10% discount
        # Expected: 262 - 26.2 + 5 = 240.80
        close_resp = auth_session.post(f"{BASE_URL}/api/fnb/tabs/{tab_id}/close", json={
            "payment_method": "cash",
            "tip_amount": 5,
            "discount_pct": 10
        })
        assert close_resp.status_code == 200
        close_data = close_resp.json()
        assert close_data["closed"] == True
        assert close_data["total"] == 240.8
        
        # Verify final state
        detail_resp = auth_session.get(f"{BASE_URL}/api/fnb/tabs/detail/{tab_id}")
        detail = detail_resp.json()
        assert detail["status"] == "closed"
        assert detail["outlet"] == "restaurant"
        assert len(detail["items"]) == 4
        assert len(detail["transfer_history"]) == 2


class TestClosedTabRestrictions:
    """Test that closed tabs cannot be modified"""
    
    def test_cannot_add_to_closed_tab(self, auth_session):
        """Cannot add items to closed tab"""
        # Create and close tab
        tab_resp = auth_session.post(f"{BASE_URL}/api/fnb/tabs", json={
            "property_id": "default",
            "outlet": "bar",
            "guest_name": "TEST_ClosedAddItem"
        })
        tab_id = tab_resp.json()["id"]
        
        auth_session.post(f"{BASE_URL}/api/fnb/tabs/{tab_id}/close", json={
            "payment_method": "cash"
        })
        
        # Try to add item
        resp = auth_session.post(f"{BASE_URL}/api/fnb/tabs/{tab_id}/items", json={
            "name": "Beer",
            "qty": 1,
            "unit_price": 8
        })
        assert resp.status_code == 400
        assert "closed" in resp.json()["detail"].lower()
    
    def test_cannot_transfer_closed_tab(self, auth_session):
        """Cannot transfer closed tab"""
        # Create and close tab
        tab_resp = auth_session.post(f"{BASE_URL}/api/fnb/tabs", json={
            "property_id": "default",
            "outlet": "bar",
            "guest_name": "TEST_ClosedTransfer"
        })
        tab_id = tab_resp.json()["id"]
        
        auth_session.post(f"{BASE_URL}/api/fnb/tabs/{tab_id}/close", json={
            "payment_method": "card"
        })
        
        # Try to transfer
        resp = auth_session.post(f"{BASE_URL}/api/fnb/tabs/{tab_id}/transfer", json={
            "new_outlet": "restaurant"
        })
        assert resp.status_code == 400
        assert "closed" in resp.json()["detail"].lower()
    
    def test_cannot_close_already_closed_tab(self, auth_session):
        """Cannot close already closed tab"""
        # Create and close tab
        tab_resp = auth_session.post(f"{BASE_URL}/api/fnb/tabs", json={
            "property_id": "default",
            "outlet": "spa",
            "guest_name": "TEST_DoubleClose"
        })
        tab_id = tab_resp.json()["id"]
        
        auth_session.post(f"{BASE_URL}/api/fnb/tabs/{tab_id}/close", json={
            "payment_method": "complimentary"
        })
        
        # Try to close again
        resp = auth_session.post(f"{BASE_URL}/api/fnb/tabs/{tab_id}/close", json={
            "payment_method": "cash"
        })
        assert resp.status_code == 400
        assert "already closed" in resp.json()["detail"].lower()
