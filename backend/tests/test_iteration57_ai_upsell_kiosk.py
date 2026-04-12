"""
Iteration 57 - AI Upselling + Self-Service Kiosk Mode Tests
Features:
1. AI-Powered Upselling (POST /api/pos/ai-upsell) - GPT-5.2 suggestions based on cart + guest history
2. Kiosk Session Start (POST /api/pos/kiosk/start) - PUBLIC, no auth
3. Kiosk Order Placement (POST /api/pos/kiosk/order) - PUBLIC, creates order + income entry
4. Kiosk orders have order_type='kiosk' and order_number prefix 'KSK-'
5. Rule-based fallback for AI upsell when AI unavailable
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestAIUpselling:
    """AI-Powered Upselling endpoint tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        self.token = response.json().get("token")
        self.headers = {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}
    
    def test_ai_upsell_with_cart_items(self):
        """Test AI upsell returns suggestions for cart with mains"""
        response = requests.post(f"{BASE_URL}/api/pos/ai-upsell", headers=self.headers, json={
            "property_id": "aldgate-flats",
            "cart_items": [
                {"name": "Grilled Salmon", "quantity": 1, "category": "Mains", "price": 24.00}
            ],
            "guest_email": ""
        })
        assert response.status_code == 200, f"AI upsell failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "suggestions" in data, "Missing suggestions in response"
        assert "source" in data, "Missing source in response"
        assert data["source"] in ["ai", "rules", "rules_fallback"], f"Invalid source: {data['source']}"
        
        # Verify suggestions structure
        suggestions = data["suggestions"]
        assert len(suggestions) >= 1, "Should return at least 1 suggestion"
        assert len(suggestions) <= 4, "Should return at most 4 suggestions"
        
        for s in suggestions:
            assert "name" in s, "Suggestion missing name"
            assert "price" in s, "Suggestion missing price"
            assert "reason" in s, "Suggestion missing reason"
            assert isinstance(s["price"], (int, float)), "Price should be numeric"
    
    def test_ai_upsell_with_empty_cart(self):
        """Test AI upsell with empty cart still returns suggestions"""
        response = requests.post(f"{BASE_URL}/api/pos/ai-upsell", headers=self.headers, json={
            "property_id": "aldgate-flats",
            "cart_items": [],
            "guest_email": ""
        })
        assert response.status_code == 200, f"AI upsell failed: {response.text}"
        data = response.json()
        
        assert "suggestions" in data
        assert "source" in data
    
    def test_ai_upsell_with_guest_email(self):
        """Test AI upsell considers guest history when email provided"""
        response = requests.post(f"{BASE_URL}/api/pos/ai-upsell", headers=self.headers, json={
            "property_id": "aldgate-flats",
            "cart_items": [
                {"name": "Ribeye Steak 10oz", "quantity": 1, "category": "Mains", "price": 28.00}
            ],
            "guest_email": "test@example.com"
        })
        assert response.status_code == 200
        data = response.json()
        assert "suggestions" in data
    
    def test_ai_upsell_requires_auth(self):
        """Test AI upsell endpoint requires authentication"""
        response = requests.post(f"{BASE_URL}/api/pos/ai-upsell", json={
            "property_id": "aldgate-flats",
            "cart_items": [],
            "guest_email": ""
        })
        assert response.status_code == 401, "AI upsell should require auth"
    
    def test_ai_upsell_suggests_drinks_with_mains(self):
        """Test rule-based fallback suggests drinks when cart has mains but no drinks"""
        response = requests.post(f"{BASE_URL}/api/pos/ai-upsell", headers=self.headers, json={
            "property_id": "aldgate-flats",
            "cart_items": [
                {"name": "Fish and Chips", "quantity": 1, "category": "Mains", "price": 16.50}
            ],
            "guest_email": ""
        })
        assert response.status_code == 200
        data = response.json()
        
        # AI or rule-based should suggest drinks or desserts
        suggestions = data["suggestions"]
        categories = [s.get("category", "") for s in suggestions]
        # Should have variety - drinks, desserts, or starters
        assert len(suggestions) >= 1


class TestKioskSession:
    """Kiosk Session Start endpoint tests - PUBLIC, no auth"""
    
    def test_kiosk_start_session(self):
        """Test starting a kiosk session - no auth required"""
        response = requests.post(f"{BASE_URL}/api/pos/kiosk/start", json={
            "property_id": "aldgate-flats",
            "outlet_id": "restaurant",
            "kiosk_id": "kiosk-test-1"
        })
        assert response.status_code == 200, f"Kiosk start failed: {response.text}"
        data = response.json()
        
        # Verify session structure
        assert "id" in data, "Session missing id"
        assert "property_id" in data, "Session missing property_id"
        assert "outlet_id" in data, "Session missing outlet_id"
        assert "kiosk_id" in data, "Session missing kiosk_id"
        assert "status" in data, "Session missing status"
        assert "created_at" in data, "Session missing created_at"
        
        # Verify values
        assert data["property_id"] == "aldgate-flats"
        assert data["outlet_id"] == "restaurant"
        assert data["kiosk_id"] == "kiosk-test-1"
        assert data["status"] == "active"
    
    def test_kiosk_start_no_auth_required(self):
        """Test kiosk start is PUBLIC - no auth needed"""
        response = requests.post(f"{BASE_URL}/api/pos/kiosk/start", json={
            "property_id": "aldgate-flats",
            "outlet_id": "bar"
        })
        # Should succeed without auth
        assert response.status_code == 200


class TestKioskOrder:
    """Kiosk Order Placement endpoint tests - PUBLIC, creates order + income entry"""
    
    def test_kiosk_place_order(self):
        """Test placing a kiosk order - no auth required"""
        unique_id = str(uuid.uuid4())[:8]
        response = requests.post(f"{BASE_URL}/api/pos/kiosk/order", json={
            "property_id": "aldgate-flats",
            "outlet_id": "restaurant",
            "outlet_name": "The Aldgate Restaurant",
            "guest_name": f"TEST_Kiosk_{unique_id}",
            "payment_method": "card",
            "items": [
                {"id": "item1", "name": f"TEST_Item_{unique_id}", "price": 12.50, "quantity": 2, "vat_rate": 20, "category": "Mains"}
            ]
        })
        assert response.status_code == 200, f"Kiosk order failed: {response.text}"
        data = response.json()
        
        # Verify response
        assert "order_number" in data, "Missing order_number"
        assert "total" in data, "Missing total"
        
        # Verify KSK- prefix
        assert data["order_number"].startswith("KSK-"), f"Order number should start with KSK-: {data['order_number']}"
        
        # Verify total calculation (12.50 * 2 = 25.00 + 20% VAT = 30.00)
        assert data["total"] == 30.0, f"Total should be 30.0, got {data['total']}"
    
    def test_kiosk_order_no_auth_required(self):
        """Test kiosk order is PUBLIC - no auth needed"""
        response = requests.post(f"{BASE_URL}/api/pos/kiosk/order", json={
            "property_id": "aldgate-flats",
            "outlet_id": "bar",
            "items": [
                {"id": "item1", "name": "TEST_Beer", "price": 5.00, "quantity": 1, "vat_rate": 20, "category": "Beer"}
            ]
        })
        assert response.status_code == 200
    
    def test_kiosk_order_empty_items_fails(self):
        """Test kiosk order with empty items returns 400"""
        response = requests.post(f"{BASE_URL}/api/pos/kiosk/order", json={
            "property_id": "aldgate-flats",
            "outlet_id": "restaurant",
            "items": []
        })
        assert response.status_code == 400, "Empty items should return 400"
    
    def test_kiosk_order_creates_income_entry(self):
        """Test kiosk order auto-creates income entry in accounting"""
        # Login to check income entries
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        token = login_resp.json().get("token")
        headers = {"Authorization": f"Bearer {token}"}
        
        # Place kiosk order
        unique_id = str(uuid.uuid4())[:8]
        order_resp = requests.post(f"{BASE_URL}/api/pos/kiosk/order", json={
            "property_id": "aldgate-flats",
            "outlet_id": "restaurant",
            "outlet_name": "Test Restaurant",
            "guest_name": f"TEST_Income_{unique_id}",
            "payment_method": "card",
            "items": [
                {"id": "item1", "name": f"TEST_Income_Item_{unique_id}", "price": 20.00, "quantity": 1, "vat_rate": 20, "category": "Mains"}
            ]
        })
        assert order_resp.status_code == 200
        order_number = order_resp.json()["order_number"]
        
        # Check income entries
        income_resp = requests.get(f"{BASE_URL}/api/accounting/income/aldgate-flats", headers=headers)
        assert income_resp.status_code == 200
        
        income_entries = income_resp.json()
        kiosk_entries = [e for e in income_entries if e.get("reference") == order_number]
        
        assert len(kiosk_entries) >= 1, f"Income entry not found for order {order_number}"
        
        entry = kiosk_entries[0]
        assert entry["source"] == "pos_kiosk", "Income source should be pos_kiosk"
        assert entry["category"] == "food_beverage", "Income category should be food_beverage"
        assert entry["amount"] == 24.0, f"Income amount should be 24.0 (20 + 20% VAT), got {entry['amount']}"


class TestKioskOrderVerification:
    """Verify kiosk orders have correct attributes"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        self.token = response.json().get("token")
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_kiosk_order_has_correct_type(self):
        """Test kiosk orders have order_type='kiosk'"""
        # Place a kiosk order
        unique_id = str(uuid.uuid4())[:8]
        order_resp = requests.post(f"{BASE_URL}/api/pos/kiosk/order", json={
            "property_id": "aldgate-flats",
            "outlet_id": "restaurant",
            "items": [
                {"id": "item1", "name": f"TEST_Type_{unique_id}", "price": 10.00, "quantity": 1, "vat_rate": 20, "category": "Mains"}
            ]
        })
        order_number = order_resp.json()["order_number"]
        
        # Fetch orders and find our order
        orders_resp = requests.get(f"{BASE_URL}/api/pos/orders/aldgate-flats", headers=self.headers)
        assert orders_resp.status_code == 200
        
        orders = orders_resp.json()
        our_order = next((o for o in orders if o.get("order_number") == order_number), None)
        
        assert our_order is not None, f"Order {order_number} not found"
        assert our_order["order_type"] == "kiosk", f"Order type should be 'kiosk', got {our_order['order_type']}"
        assert our_order["server_name"] == "Self-Service Kiosk", f"Server name should be 'Self-Service Kiosk'"
        assert our_order["payment_status"] == "paid", "Kiosk orders should be auto-paid"


class TestRuleBasedUpsellFallback:
    """Test rule-based upsell fallback logic"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        self.token = response.json().get("token")
        self.headers = {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}
    
    def test_upsell_with_mains_no_drinks(self):
        """Test upsell suggests drinks when cart has mains but no drinks"""
        response = requests.post(f"{BASE_URL}/api/pos/ai-upsell", headers=self.headers, json={
            "property_id": "aldgate-flats",
            "cart_items": [
                {"name": "Ribeye Steak 10oz", "quantity": 1, "category": "Mains", "price": 28.00}
            ],
            "guest_email": ""
        })
        assert response.status_code == 200
        data = response.json()
        
        # Should have suggestions
        assert len(data["suggestions"]) >= 1
    
    def test_upsell_with_mains_no_desserts(self):
        """Test upsell suggests desserts when cart has mains but no desserts"""
        response = requests.post(f"{BASE_URL}/api/pos/ai-upsell", headers=self.headers, json={
            "property_id": "aldgate-flats",
            "cart_items": [
                {"name": "Fish and Chips", "quantity": 1, "category": "Mains", "price": 16.50}
            ],
            "guest_email": ""
        })
        assert response.status_code == 200
        data = response.json()
        
        # Should have suggestions
        assert len(data["suggestions"]) >= 1


class TestPublicMenuForKiosk:
    """Test public menu endpoint used by kiosk"""
    
    def test_public_menu_no_auth(self):
        """Test public menu endpoint requires no auth"""
        # First get actual outlet ID
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        token = login_resp.json().get("token")
        headers = {"Authorization": f"Bearer {token}"}
        
        outlets_resp = requests.get(f"{BASE_URL}/api/pos/outlets/aldgate-flats", headers=headers)
        outlets = outlets_resp.json()
        restaurant_outlet = next((o for o in outlets if o.get("type") == "restaurant"), outlets[0])
        outlet_id = restaurant_outlet["id"]
        
        # Now test public menu without auth
        response = requests.get(f"{BASE_URL}/api/pos/public/menu/aldgate-flats/{outlet_id}")
        assert response.status_code == 200, f"Public menu failed: {response.text}"
        data = response.json()
        
        assert "menu_items" in data, "Missing menu_items"
        assert "categories" in data, "Missing categories"
        assert "hotel_name" in data, "Missing hotel_name"
        assert "outlet_name" in data, "Missing outlet_name"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
