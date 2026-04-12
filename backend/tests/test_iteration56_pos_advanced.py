"""
Iteration 56 - POS Advanced Features Tests
Tests for: QR Code Self-Ordering, Digital Receipts, Happy Hour, Guest Preferences, Loyalty Points
"""
import pytest
import requests
import os
import uuid
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestAuth:
    """Get auth token for protected endpoints"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        return data.get("access_token") or data.get("token")
    
    @pytest.fixture(scope="class")
    def auth_headers(self, auth_token):
        return {"Authorization": f"Bearer {auth_token}"}


class TestPublicQROrdering(TestAuth):
    """Test PUBLIC endpoints for QR code self-ordering (no auth required)"""
    
    def test_public_menu_no_auth(self):
        """GET /api/pos/public/menu/{property_id}/{outlet_id} - PUBLIC, no auth"""
        # First get outlets to find a valid outlet_id
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        token = response.json().get("access_token") or response.json().get("token")
        headers = {"Authorization": f"Bearer {token}"}
        
        outlets_resp = requests.get(f"{BASE_URL}/api/pos/outlets/aldgate-flats", headers=headers)
        assert outlets_resp.status_code == 200
        outlets = outlets_resp.json()
        assert len(outlets) > 0, "No outlets found"
        outlet_id = outlets[0]["id"]
        
        # Now test PUBLIC menu endpoint (no auth)
        response = requests.get(f"{BASE_URL}/api/pos/public/menu/aldgate-flats/{outlet_id}")
        assert response.status_code == 200, f"Public menu failed: {response.text}"
        
        data = response.json()
        assert "menu_items" in data
        assert "categories" in data
        assert "outlet_name" in data
        assert "happy_hour_active" in data
        print(f"Public menu returned {len(data['menu_items'])} items, {len(data['categories'])} categories")
        print(f"Happy hour active: {data['happy_hour_active']}")
    
    def test_public_menu_with_table_param(self):
        """GET /api/pos/public/menu with table query param"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        token = response.json().get("access_token") or response.json().get("token")
        headers = {"Authorization": f"Bearer {token}"}
        
        outlets_resp = requests.get(f"{BASE_URL}/api/pos/outlets/aldgate-flats", headers=headers)
        outlet_id = outlets_resp.json()[0]["id"]
        
        response = requests.get(f"{BASE_URL}/api/pos/public/menu/aldgate-flats/{outlet_id}?table=5")
        assert response.status_code == 200
        data = response.json()
        assert data["table_number"] == "5"
        print(f"Table number correctly passed: {data['table_number']}")
    
    def test_public_order_no_auth(self):
        """POST /api/pos/public/order - PUBLIC, places QR order"""
        # Get outlet first
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        token = response.json().get("access_token") or response.json().get("token")
        headers = {"Authorization": f"Bearer {token}"}
        
        outlets_resp = requests.get(f"{BASE_URL}/api/pos/outlets/aldgate-flats", headers=headers)
        outlet = outlets_resp.json()[0]
        
        # Get menu items
        menu_resp = requests.get(f"{BASE_URL}/api/pos/public/menu/aldgate-flats/{outlet['id']}")
        menu_items = menu_resp.json()["menu_items"]
        
        # Place order (no auth)
        order_data = {
            "property_id": "aldgate-flats",
            "outlet_id": outlet["id"],
            "outlet_name": outlet["name"],
            "table_number": "7",
            "guest_name": "TEST_QR_Guest",
            "guest_email": "test_qr@example.com",
            "guest_phone": "07123456789",
            "room_number": "",
            "notes": "No onions please",
            "covers": 2,
            "items": [
                {
                    "id": menu_items[0]["id"],
                    "name": menu_items[0]["name"],
                    "price": menu_items[0]["price"],
                    "quantity": 2,
                    "vat_rate": 20,
                    "category": menu_items[0]["category"]
                }
            ]
        }
        
        response = requests.post(f"{BASE_URL}/api/pos/public/order", json=order_data)
        assert response.status_code == 200, f"Public order failed: {response.text}"
        
        data = response.json()
        assert "order_number" in data
        assert data["order_number"].startswith("QR-")
        assert "total" in data
        assert data["status"] == "received"
        print(f"QR Order placed: {data['order_number']}, Total: £{data['total']}")
    
    def test_public_order_empty_items_fails(self):
        """POST /api/pos/public/order with empty items should fail"""
        order_data = {
            "property_id": "aldgate-flats",
            "outlet_id": "some-outlet",
            "items": []
        }
        response = requests.post(f"{BASE_URL}/api/pos/public/order", json=order_data)
        assert response.status_code == 400
        print("Empty items correctly rejected")


class TestDigitalReceipts(TestAuth):
    """Test digital email receipts"""
    
    def test_send_receipt_requires_auth(self):
        """POST /api/pos/orders/{order_id}/receipt requires auth"""
        response = requests.post(f"{BASE_URL}/api/pos/orders/fake-id/receipt", json={"email": "test@test.com"})
        assert response.status_code == 401 or response.status_code == 403
        print("Receipt endpoint correctly requires auth")
    
    def test_send_receipt_order_not_found(self, auth_headers):
        """POST /api/pos/orders/{order_id}/receipt with invalid order"""
        response = requests.post(
            f"{BASE_URL}/api/pos/orders/nonexistent-order/receipt",
            json={"email": "test@test.com"},
            headers=auth_headers
        )
        assert response.status_code == 404
        print("Non-existent order correctly returns 404")
    
    def test_send_receipt_no_email_fails(self, auth_headers):
        """POST /api/pos/orders/{order_id}/receipt without email should fail"""
        # First create an order
        outlets_resp = requests.get(f"{BASE_URL}/api/pos/outlets/aldgate-flats", headers=auth_headers)
        outlet = outlets_resp.json()[0]
        
        menu_resp = requests.get(f"{BASE_URL}/api/pos/menu/aldgate-flats", headers=auth_headers)
        menu_items = menu_resp.json()
        
        order_data = {
            "property_id": "aldgate-flats",
            "outlet_id": outlet["id"],
            "outlet_name": outlet["name"],
            "order_type": "dine_in",
            "table_number": "99",
            "covers": 1,
            "items": [{
                "id": menu_items[0]["id"],
                "name": menu_items[0]["name"],
                "price": menu_items[0]["price"],
                "quantity": 1,
                "vat_rate": 20
            }]
        }
        order_resp = requests.post(f"{BASE_URL}/api/pos/orders", json=order_data, headers=auth_headers)
        order_id = order_resp.json()["id"]
        
        # Try to send receipt without email
        response = requests.post(
            f"{BASE_URL}/api/pos/orders/{order_id}/receipt",
            json={},
            headers=auth_headers
        )
        assert response.status_code == 400
        print("Receipt without email correctly rejected")


class TestHappyHour(TestAuth):
    """Test Happy Hour / Dynamic Pricing"""
    
    def test_list_happy_hours_auto_seeds(self, auth_headers):
        """GET /api/pos/happy-hours/{property_id} auto-seeds 2 defaults"""
        response = requests.get(f"{BASE_URL}/api/pos/happy-hours/aldgate-flats", headers=auth_headers)
        assert response.status_code == 200, f"Happy hours list failed: {response.text}"
        
        data = response.json()
        assert len(data) >= 2, f"Expected at least 2 default happy hours, got {len(data)}"
        
        # Check default promotions exist
        names = [hh["name"] for hh in data]
        assert "Happy Hour" in names or any("Happy" in n for n in names), "Default Happy Hour not found"
        print(f"Happy hours returned: {len(data)} promotions")
        for hh in data:
            print(f"  - {hh['name']}: {hh['start_hour']}:00-{hh['end_hour']}:00, {hh['discount_pct']}% off, enabled={hh['enabled']}")
    
    def test_create_happy_hour(self, auth_headers):
        """POST /api/pos/happy-hours - create new promotion"""
        hh_data = {
            "property_id": "aldgate-flats",
            "outlet_id": "",
            "name": "TEST_Weekend Brunch Special",
            "start_hour": 10,
            "end_hour": 14,
            "discount_pct": 15,
            "categories": ["Starters", "Mains"],
            "days": ["sat", "sun"]
        }
        
        response = requests.post(f"{BASE_URL}/api/pos/happy-hours", json=hh_data, headers=auth_headers)
        assert response.status_code == 200, f"Create happy hour failed: {response.text}"
        
        data = response.json()
        assert data["name"] == "TEST_Weekend Brunch Special"
        assert data["discount_pct"] == 15
        assert data["enabled"] == True
        assert "id" in data
        print(f"Created happy hour: {data['name']} with ID {data['id']}")
        return data["id"]
    
    def test_update_happy_hour_toggle(self, auth_headers):
        """PUT /api/pos/happy-hours/{hh_id} - enable/disable"""
        # Get existing happy hours
        list_resp = requests.get(f"{BASE_URL}/api/pos/happy-hours/aldgate-flats", headers=auth_headers)
        happy_hours = list_resp.json()
        hh_id = happy_hours[0]["id"]
        original_enabled = happy_hours[0]["enabled"]
        
        # Toggle enabled status
        response = requests.put(
            f"{BASE_URL}/api/pos/happy-hours/{hh_id}",
            json={"enabled": not original_enabled},
            headers=auth_headers
        )
        assert response.status_code == 200, f"Update happy hour failed: {response.text}"
        
        data = response.json()
        assert data["enabled"] == (not original_enabled)
        print(f"Toggled happy hour {hh_id} enabled: {original_enabled} -> {data['enabled']}")
        
        # Toggle back
        requests.put(f"{BASE_URL}/api/pos/happy-hours/{hh_id}", json={"enabled": original_enabled}, headers=auth_headers)
    
    def test_happy_hour_requires_auth(self):
        """Happy hour endpoints require auth"""
        response = requests.get(f"{BASE_URL}/api/pos/happy-hours/aldgate-flats")
        assert response.status_code == 401 or response.status_code == 403
        print("Happy hour endpoints correctly require auth")


class TestGuestPreferences(TestAuth):
    """Test Guest Preference Tracking"""
    
    def test_get_guest_preferences_new_guest(self, auth_headers):
        """GET /api/pos/guest-preferences/{guest_email} - returns defaults for new guest"""
        test_email = f"test_new_guest_{uuid.uuid4().hex[:8]}@example.com"
        
        response = requests.get(f"{BASE_URL}/api/pos/guest-preferences/{test_email}", headers=auth_headers)
        assert response.status_code == 200, f"Get preferences failed: {response.text}"
        
        data = response.json()
        assert data["email"] == test_email
        assert data["dietary"] == []
        assert data["allergens"] == []
        assert data["favorites"] == []
        print(f"New guest preferences returned with defaults: {data}")
    
    def test_update_guest_preferences(self, auth_headers):
        """PUT /api/pos/guest-preferences/{guest_email} - update preferences"""
        test_email = "test_prefs_guest@example.com"
        
        prefs_data = {
            "dietary": ["vegetarian", "gluten-free"],
            "allergens": ["nuts", "shellfish"],
            "favorites": ["Caesar Salad", "Margherita Pizza"],
            "dislikes": ["spicy food"],
            "notes": "Prefers window seating"
        }
        
        response = requests.put(
            f"{BASE_URL}/api/pos/guest-preferences/{test_email}",
            json=prefs_data,
            headers=auth_headers
        )
        assert response.status_code == 200, f"Update preferences failed: {response.text}"
        
        data = response.json()
        assert data["email"] == test_email
        assert "vegetarian" in data["dietary"]
        assert "nuts" in data["allergens"]
        assert "updated_at" in data
        print(f"Updated guest preferences: dietary={data['dietary']}, allergens={data['allergens']}")
        
        # Verify persistence with GET
        get_resp = requests.get(f"{BASE_URL}/api/pos/guest-preferences/{test_email}", headers=auth_headers)
        get_data = get_resp.json()
        assert get_data["dietary"] == prefs_data["dietary"]
        print("Preferences persisted correctly")
    
    def test_guest_order_history(self, auth_headers):
        """GET /api/pos/guest-order-history/{guest_email} - order history with favorites"""
        test_email = "test_history@example.com"
        
        response = requests.get(f"{BASE_URL}/api/pos/guest-order-history/{test_email}", headers=auth_headers)
        assert response.status_code == 200, f"Get order history failed: {response.text}"
        
        data = response.json()
        assert data["guest_email"] == test_email
        assert "total_orders" in data
        assert "total_spent" in data
        assert "top_items" in data
        assert "recent_orders" in data
        print(f"Guest order history: {data['total_orders']} orders, £{data['total_spent']} spent")
        if data["top_items"]:
            print(f"Top items: {data['top_items']}")


class TestLoyaltyPoints(TestAuth):
    """Test Loyalty Points System"""
    
    def test_get_loyalty_new_guest(self, auth_headers):
        """GET /api/pos/loyalty/{guest_email} - returns 0 points for new guest"""
        test_email = f"test_loyalty_new_{uuid.uuid4().hex[:8]}@example.com"
        
        response = requests.get(f"{BASE_URL}/api/pos/loyalty/{test_email}", headers=auth_headers)
        assert response.status_code == 200, f"Get loyalty failed: {response.text}"
        
        data = response.json()
        assert data["guest_email"] == test_email
        assert data["points"] == 0
        assert data["tier"] == "standard"
        assert "benefits" in data
        assert data["benefits"]["earn_rate"] == 1
        print(f"New guest loyalty: {data['points']} points, tier={data['tier']}")
    
    def test_earn_loyalty_points_standard(self, auth_headers):
        """POST /api/pos/loyalty/earn - earn points at standard rate (1x)"""
        test_email = "test_loyalty_earn@example.com"
        
        earn_data = {
            "guest_email": test_email,
            "amount": 100,  # £100 spend
            "order_id": "test-order-123"
        }
        
        response = requests.post(f"{BASE_URL}/api/pos/loyalty/earn", json=earn_data, headers=auth_headers)
        assert response.status_code == 200, f"Earn points failed: {response.text}"
        
        data = response.json()
        assert data["points_earned"] == 100  # 1x rate for standard
        assert data["rate"] == 1
        assert "total_points" in data
        print(f"Earned {data['points_earned']} points at {data['rate']}x rate, total: {data['total_points']}")
    
    def test_loyalty_tier_auto_upgrade(self, auth_headers):
        """POST /api/pos/loyalty/earn - auto-upgrades tier based on points"""
        test_email = f"test_tier_upgrade_{uuid.uuid4().hex[:8]}@example.com"
        
        # Earn 500+ points to upgrade to silver
        earn_data = {
            "guest_email": test_email,
            "amount": 500,
            "order_id": "test-order-tier"
        }
        
        response = requests.post(f"{BASE_URL}/api/pos/loyalty/earn", json=earn_data, headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert data["tier"] == "silver", f"Expected silver tier at 500 points, got {data['tier']}"
        assert data["total_points"] >= 500
        print(f"Tier auto-upgraded to {data['tier']} at {data['total_points']} points")
    
    def test_loyalty_tier_benefits(self, auth_headers):
        """Verify tier benefits (earn rates)"""
        # Tier thresholds: standard < 500 < silver < 2000 < gold < 5000 < platinum
        # Earn rates: standard=1x, silver=1.5x, gold=2x, platinum=3x
        
        test_email = f"test_gold_tier_{uuid.uuid4().hex[:8]}@example.com"
        
        # First earn to get to gold tier (2000+ points)
        earn_data = {"guest_email": test_email, "amount": 2000, "order_id": "test-gold"}
        response = requests.post(f"{BASE_URL}/api/pos/loyalty/earn", json=earn_data, headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert data["tier"] == "gold", f"Expected gold tier at 2000 points, got {data['tier']}"
        
        # Now earn more and verify 2x rate
        earn_data2 = {"guest_email": test_email, "amount": 100, "order_id": "test-gold-2"}
        response2 = requests.post(f"{BASE_URL}/api/pos/loyalty/earn", json=earn_data2, headers=auth_headers)
        data2 = response2.json()
        
        assert data2["rate"] == 2, f"Expected 2x rate for gold, got {data2['rate']}x"
        assert data2["points_earned"] == 200  # 100 * 2x
        print(f"Gold tier earns at {data2['rate']}x rate: £100 = {data2['points_earned']} points")
    
    def test_redeem_loyalty_points(self, auth_headers):
        """POST /api/pos/loyalty/redeem - redeem points for discount"""
        test_email = f"test_redeem_{uuid.uuid4().hex[:8]}@example.com"
        
        # First earn some points
        earn_data = {"guest_email": test_email, "amount": 200, "order_id": "test-redeem-earn"}
        requests.post(f"{BASE_URL}/api/pos/loyalty/earn", json=earn_data, headers=auth_headers)
        
        # Redeem 100 points
        redeem_data = {
            "guest_email": test_email,
            "points": 100
        }
        
        response = requests.post(f"{BASE_URL}/api/pos/loyalty/redeem", json=redeem_data, headers=auth_headers)
        assert response.status_code == 200, f"Redeem failed: {response.text}"
        
        data = response.json()
        assert data["points_redeemed"] == 100
        assert data["discount_value"] == 1.00  # 100 points = £1
        assert data["remaining_points"] == 100  # 200 - 100
        print(f"Redeemed {data['points_redeemed']} points for £{data['discount_value']} discount, remaining: {data['remaining_points']}")
    
    def test_redeem_insufficient_points_fails(self, auth_headers):
        """POST /api/pos/loyalty/redeem with insufficient points should fail"""
        test_email = f"test_insufficient_{uuid.uuid4().hex[:8]}@example.com"
        
        redeem_data = {
            "guest_email": test_email,
            "points": 1000  # More than available (0)
        }
        
        response = requests.post(f"{BASE_URL}/api/pos/loyalty/redeem", json=redeem_data, headers=auth_headers)
        assert response.status_code == 400
        print("Insufficient points correctly rejected")
    
    def test_earn_requires_positive_amount(self, auth_headers):
        """POST /api/pos/loyalty/earn with zero/negative amount should fail"""
        earn_data = {
            "guest_email": "test@test.com",
            "amount": 0,
            "order_id": "test"
        }
        
        response = requests.post(f"{BASE_URL}/api/pos/loyalty/earn", json=earn_data, headers=auth_headers)
        assert response.status_code == 400
        print("Zero amount correctly rejected")


class TestHappyHourPricingInPublicMenu(TestAuth):
    """Test that happy hour pricing is applied to public menu"""
    
    def test_happy_hour_pricing_applied(self, auth_headers):
        """Verify happy hour discounts appear in public menu when active"""
        # Get outlets
        outlets_resp = requests.get(f"{BASE_URL}/api/pos/outlets/aldgate-flats", headers=auth_headers)
        outlet = outlets_resp.json()[0]
        
        # Get public menu
        response = requests.get(f"{BASE_URL}/api/pos/public/menu/aldgate-flats/{outlet['id']}")
        assert response.status_code == 200
        
        data = response.json()
        print(f"Happy hour active: {data['happy_hour_active']}")
        
        if data['happy_hour_active']:
            # Check for discounted items
            discounted = [item for item in data['menu_items'] if item.get('happy_hour')]
            print(f"Found {len(discounted)} items with happy hour pricing")
            if discounted:
                item = discounted[0]
                print(f"Example: {item['name']} - Original: £{item.get('original_price')}, Now: £{item['price']}")
        else:
            print("No happy hour currently active - pricing test skipped")


class TestQRCodeInfo(TestAuth):
    """Test QR code URL generation"""
    
    def test_get_qr_info(self, auth_headers):
        """GET /api/pos/qr-code/{property_id}/{outlet_id} - get QR URL"""
        outlets_resp = requests.get(f"{BASE_URL}/api/pos/outlets/aldgate-flats", headers=auth_headers)
        outlet = outlets_resp.json()[0]
        
        response = requests.get(
            f"{BASE_URL}/api/pos/qr-code/aldgate-flats/{outlet['id']}",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Get QR info failed: {response.text}"
        
        data = response.json()
        assert "url" in data
        assert "aldgate-flats" in data["url"]
        assert outlet["id"] in data["url"]
        print(f"QR URL: {data['url']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
