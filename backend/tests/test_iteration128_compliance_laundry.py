"""
Iteration 128 - Compliance Register & Laundry Management Backend Tests
Tests for:
- Compliance Register: categories, items CRUD, check, status computation
- Laundry Management: dispatches, stock, contracts, catalog
"""
import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestAuth:
    """Authentication helper"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        return response.cookies.get('access_token') or response.json().get('access_token')
    
    @pytest.fixture(scope="class")
    def admin_session(self, admin_token):
        """Session with admin auth"""
        session = requests.Session()
        session.cookies.set('access_token', admin_token)
        session.headers.update({"Content-Type": "application/json"})
        return session


class TestComplianceCategories(TestAuth):
    """Test Compliance Categories endpoint"""
    
    def test_get_categories_returns_7_defaults(self, admin_session):
        """GET /api/compliance/categories/all returns 7 default categories"""
        response = admin_session.get(f"{BASE_URL}/api/compliance/categories/all")
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        assert "categories" in data
        categories = data["categories"]
        
        # Should have 7 default categories
        assert len(categories) >= 7, f"Expected at least 7 categories, got {len(categories)}"
        
        # Check expected category IDs
        expected_ids = {"fire", "food", "hs", "license", "insurance", "gdpr", "training"}
        actual_ids = {c["id"] for c in categories}
        assert expected_ids.issubset(actual_ids), f"Missing categories: {expected_ids - actual_ids}"
        
        # Each category should have counts
        for cat in categories:
            assert "total" in cat, f"Category {cat['id']} missing 'total'"
            assert "overdue" in cat, f"Category {cat['id']} missing 'overdue'"
            assert "expiring_soon" in cat, f"Category {cat['id']} missing 'expiring_soon'"
            assert "name" in cat
            assert "icon" in cat
            assert "color" in cat
        
        print(f"✓ GET /api/compliance/categories/all returns {len(categories)} categories with counts")


class TestComplianceItems(TestAuth):
    """Test Compliance Items CRUD"""
    
    def test_get_items_returns_kpis(self, admin_session):
        """GET /api/compliance/items/all returns items and KPIs"""
        response = admin_session.get(f"{BASE_URL}/api/compliance/items/all")
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        assert "items" in data
        assert "kpis" in data
        
        kpis = data["kpis"]
        assert "total" in kpis
        assert "compliant" in kpis
        assert "overdue" in kpis
        assert "expiring_soon" in kpis
        assert "action_needed" in kpis
        
        print(f"✓ GET /api/compliance/items/all returns items and KPIs: {kpis}")
    
    def test_create_item_success(self, admin_session):
        """POST /api/compliance/items/all creates item with computed status"""
        # Create item with future due date (should be compliant)
        future_date = (datetime.now() + timedelta(days=60)).strftime("%Y-%m-%d")
        payload = {
            "title": "TEST_Fire Extinguisher Inspection",
            "category": "fire",
            "due_date": future_date,
            "frequency": "annual",
            "description": "Annual fire extinguisher inspection"
        }
        
        response = admin_session.post(f"{BASE_URL}/api/compliance/items/all", json=payload)
        assert response.status_code == 200, f"Failed: {response.text}"
        
        item = response.json()
        assert item["title"] == payload["title"]
        assert item["category"] == "fire"
        assert item["due_date"] == future_date
        assert item["frequency"] == "annual"
        assert "id" in item
        
        # Store for cleanup
        self.__class__.created_item_id = item["id"]
        print(f"✓ POST /api/compliance/items/all created item: {item['id']}")
        return item["id"]
    
    def test_create_item_missing_title_returns_400(self, admin_session):
        """POST /api/compliance/items/all returns 400 when title missing"""
        payload = {
            "category": "fire",
            "due_date": "2026-06-01"
        }
        
        response = admin_session.post(f"{BASE_URL}/api/compliance/items/all", json=payload)
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("✓ POST /api/compliance/items/all returns 400 when title missing")
    
    def test_get_items_with_category_filter(self, admin_session):
        """GET /api/compliance/items/all?category=fire filters by category"""
        response = admin_session.get(f"{BASE_URL}/api/compliance/items/all?category=fire")
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        for item in data["items"]:
            assert item["category"] == "fire", f"Item {item['id']} has wrong category"
        
        print(f"✓ GET /api/compliance/items/all?category=fire filters correctly")
    
    def test_get_items_with_status_filter(self, admin_session):
        """GET /api/compliance/items/all?status=compliant filters by status"""
        response = admin_session.get(f"{BASE_URL}/api/compliance/items/all?status=compliant")
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        for item in data["items"]:
            assert item["computed_status"] == "compliant", f"Item {item['id']} has wrong status"
        
        print(f"✓ GET /api/compliance/items/all?status=compliant filters correctly")
    
    def test_update_item(self, admin_session):
        """PUT /api/compliance/items/all/{id} updates allowed fields"""
        item_id = getattr(self.__class__, 'created_item_id', None)
        if not item_id:
            pytest.skip("No item created to update")
        
        update_payload = {
            "title": "TEST_Updated Fire Inspection",
            "assigned_to": "John Smith",
            "notes": "Updated notes"
        }
        
        response = admin_session.put(f"{BASE_URL}/api/compliance/items/all/{item_id}", json=update_payload)
        assert response.status_code == 200, f"Failed: {response.text}"
        
        updated = response.json()
        assert updated["title"] == update_payload["title"]
        assert updated["assigned_to"] == "John Smith"
        assert updated["notes"] == "Updated notes"
        
        print(f"✓ PUT /api/compliance/items/all/{item_id} updated successfully")
    
    def test_mark_checked(self, admin_session):
        """POST /api/compliance/items/all/{id}/check sets last_checked and status"""
        item_id = getattr(self.__class__, 'created_item_id', None)
        if not item_id:
            pytest.skip("No item created to check")
        
        response = admin_session.post(f"{BASE_URL}/api/compliance/items/all/{item_id}/check")
        assert response.status_code == 200, f"Failed: {response.text}"
        
        result = response.json()
        assert result["ok"] == True
        assert "last_checked" in result
        assert result["last_checked"] == datetime.now().strftime("%Y-%m-%d")
        
        print(f"✓ POST /api/compliance/items/all/{item_id}/check marked as checked")
    
    def test_delete_item(self, admin_session):
        """DELETE /api/compliance/items/all/{id} removes item"""
        item_id = getattr(self.__class__, 'created_item_id', None)
        if not item_id:
            pytest.skip("No item created to delete")
        
        response = admin_session.delete(f"{BASE_URL}/api/compliance/items/all/{item_id}")
        assert response.status_code == 200, f"Failed: {response.text}"
        
        result = response.json()
        assert result["deleted"] == True
        
        print(f"✓ DELETE /api/compliance/items/all/{item_id} deleted successfully")
    
    def test_delete_unknown_item_returns_404(self, admin_session):
        """DELETE /api/compliance/items/all/{id} returns 404 for unknown id"""
        response = admin_session.delete(f"{BASE_URL}/api/compliance/items/all/nonexistent-id-12345")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ DELETE /api/compliance/items/all returns 404 for unknown id")


class TestComplianceStatusComputation(TestAuth):
    """Test compliance status computation based on due_date"""
    
    def test_overdue_status(self, admin_session):
        """Item with past due_date gets 'overdue' status"""
        past_date = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")
        payload = {
            "title": "TEST_Overdue Item",
            "category": "hs",
            "due_date": past_date
        }
        
        response = admin_session.post(f"{BASE_URL}/api/compliance/items/all", json=payload)
        assert response.status_code == 200
        item = response.json()
        
        # Verify via GET
        get_response = admin_session.get(f"{BASE_URL}/api/compliance/items/all")
        items = get_response.json()["items"]
        created_item = next((i for i in items if i["id"] == item["id"]), None)
        
        assert created_item is not None
        assert created_item["computed_status"] == "overdue", f"Expected 'overdue', got '{created_item['computed_status']}'"
        
        # Cleanup
        admin_session.delete(f"{BASE_URL}/api/compliance/items/all/{item['id']}")
        print("✓ Item with past due_date gets 'overdue' status")
    
    def test_expiring_soon_status(self, admin_session):
        """Item with due_date within 30 days gets 'expiring_soon' status"""
        soon_date = (datetime.now() + timedelta(days=15)).strftime("%Y-%m-%d")
        payload = {
            "title": "TEST_Expiring Soon Item",
            "category": "license",
            "due_date": soon_date
        }
        
        response = admin_session.post(f"{BASE_URL}/api/compliance/items/all", json=payload)
        assert response.status_code == 200
        item = response.json()
        
        # Verify via GET
        get_response = admin_session.get(f"{BASE_URL}/api/compliance/items/all")
        items = get_response.json()["items"]
        created_item = next((i for i in items if i["id"] == item["id"]), None)
        
        assert created_item is not None
        assert created_item["computed_status"] == "expiring_soon", f"Expected 'expiring_soon', got '{created_item['computed_status']}'"
        
        # Cleanup
        admin_session.delete(f"{BASE_URL}/api/compliance/items/all/{item['id']}")
        print("✓ Item with due_date within 30 days gets 'expiring_soon' status")


class TestLaundryCatalog(TestAuth):
    """Test Laundry Catalog endpoint"""
    
    def test_get_catalog_returns_11_items(self, admin_session):
        """GET /api/laundry/catalog returns 11 default items"""
        response = admin_session.get(f"{BASE_URL}/api/laundry/catalog")
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        assert "items" in data
        items = data["items"]
        
        assert len(items) == 11, f"Expected 11 items, got {len(items)}"
        
        # Check expected item IDs
        expected_ids = {
            "bed_sheet_single", "bed_sheet_double", "bed_sheet_king",
            "pillow_case", "duvet_cover", "bath_towel", "hand_towel",
            "face_cloth", "bath_mat", "table_cloth", "napkin"
        }
        actual_ids = {i["id"] for i in items}
        assert expected_ids == actual_ids, f"Missing items: {expected_ids - actual_ids}"
        
        print(f"✓ GET /api/laundry/catalog returns 11 items: {[i['name'] for i in items]}")


class TestLaundryDispatches(TestAuth):
    """Test Laundry Dispatches CRUD"""
    
    def test_get_dispatches_returns_kpis(self, admin_session):
        """GET /api/laundry/dispatches/all returns dispatches and KPIs"""
        response = admin_session.get(f"{BASE_URL}/api/laundry/dispatches/all")
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        assert "dispatches" in data
        assert "kpis" in data
        
        kpis = data["kpis"]
        assert "pending" in kpis
        assert "sent" in kpis
        assert "received" in kpis
        assert "total_items" in kpis
        assert "total_cost" in kpis
        
        print(f"✓ GET /api/laundry/dispatches/all returns KPIs: {kpis}")
    
    def test_create_dispatch_success(self, admin_session):
        """POST /api/laundry/dispatches/all creates dispatch with status='sent'"""
        payload = {
            "vendor": "TEST_CleanLinens Ltd",
            "sent_date": datetime.now().strftime("%Y-%m-%d"),
            "items": [
                {"item_id": "bed_sheet_single", "name": "Bed Sheet (Single)", "qty_sent": 10, "rate": 2.50},
                {"item_id": "bath_towel", "name": "Bath Towel", "qty_sent": 20, "rate": 1.50}
            ],
            "notes": "Test dispatch"
        }
        
        response = admin_session.post(f"{BASE_URL}/api/laundry/dispatches/all", json=payload)
        assert response.status_code == 200, f"Failed: {response.text}"
        
        dispatch = response.json()
        assert dispatch["vendor"] == payload["vendor"]
        assert dispatch["status"] == "sent"
        assert len(dispatch["items"]) == 2
        assert dispatch["total_cost"] == 55.0  # (10*2.50) + (20*1.50)
        assert "id" in dispatch
        
        # Store for later tests
        self.__class__.created_dispatch_id = dispatch["id"]
        print(f"✓ POST /api/laundry/dispatches/all created dispatch: {dispatch['id']}")
    
    def test_create_dispatch_missing_vendor_returns_400(self, admin_session):
        """POST /api/laundry/dispatches/all returns 400 when vendor missing"""
        payload = {
            "items": [{"item_id": "bed_sheet_single", "qty_sent": 5, "rate": 2.0}]
        }
        
        response = admin_session.post(f"{BASE_URL}/api/laundry/dispatches/all", json=payload)
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("✓ POST /api/laundry/dispatches/all returns 400 when vendor missing")
    
    def test_receive_dispatch(self, admin_session):
        """POST /api/laundry/dispatches/all/{id}/receive moves items to received"""
        dispatch_id = getattr(self.__class__, 'created_dispatch_id', None)
        if not dispatch_id:
            pytest.skip("No dispatch created to receive")
        
        # Receive with full quantities
        payload = {
            "items": [
                {"item_id": "bed_sheet_single", "qty_received": 10},
                {"item_id": "bath_towel", "qty_received": 20}
            ]
        }
        
        response = admin_session.post(f"{BASE_URL}/api/laundry/dispatches/all/{dispatch_id}/receive", json=payload)
        assert response.status_code == 200, f"Failed: {response.text}"
        
        result = response.json()
        assert result["ok"] == True
        
        # Verify dispatch status changed
        get_response = admin_session.get(f"{BASE_URL}/api/laundry/dispatches/all")
        dispatches = get_response.json()["dispatches"]
        received_dispatch = next((d for d in dispatches if d["id"] == dispatch_id), None)
        
        assert received_dispatch is not None
        assert received_dispatch["status"] == "received"
        
        print(f"✓ POST /api/laundry/dispatches/all/{dispatch_id}/receive marked as received")


class TestLaundryStock(TestAuth):
    """Test Laundry Stock endpoint"""
    
    def test_get_stock_returns_11_rows(self, admin_session):
        """GET /api/laundry/stock/all returns 11 rows with stock counts"""
        response = admin_session.get(f"{BASE_URL}/api/laundry/stock/all")
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        assert "stock" in data
        stock = data["stock"]
        
        assert len(stock) >= 11, f"Expected at least 11 stock rows, got {len(stock)}"
        
        # Each row should have required fields
        for row in stock:
            assert "item_id" in row
            assert "name" in row
            assert "on_hand_clean" in row
            assert "dirty" in row
            assert "in_transit" in row
            assert "damaged" in row
            assert "total" in row
        
        print(f"✓ GET /api/laundry/stock/all returns {len(stock)} stock rows")
    
    def test_update_stock(self, admin_session):
        """PUT /api/laundry/stock/all/{item_id} upserts stock counts"""
        payload = {
            "on_hand_clean": 50,
            "dirty": 10,
            "damaged": 2,
            "name": "Bed Sheet (Single)"
        }
        
        response = admin_session.put(f"{BASE_URL}/api/laundry/stock/all/bed_sheet_single", json=payload)
        assert response.status_code == 200, f"Failed: {response.text}"
        
        updated = response.json()
        assert updated["on_hand_clean"] == 50
        assert updated["dirty"] == 10
        assert updated["damaged"] == 2
        
        print(f"✓ PUT /api/laundry/stock/all/bed_sheet_single updated stock")


class TestLaundryContracts(TestAuth):
    """Test Laundry Contracts CRUD"""
    
    def test_get_contracts(self, admin_session):
        """GET /api/laundry/contracts/all returns contracts list"""
        response = admin_session.get(f"{BASE_URL}/api/laundry/contracts/all")
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        assert "contracts" in data
        print(f"✓ GET /api/laundry/contracts/all returns {len(data['contracts'])} contracts")
    
    def test_create_contract(self, admin_session):
        """POST /api/laundry/contracts/all creates contract with rate card"""
        payload = {
            "vendor": "TEST_Premium Laundry Services",
            "contact_name": "Jane Doe",
            "contact_email": "jane@premiumlaundry.com",
            "contact_phone": "+44 123 456 7890",
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
            "pickup_schedule": "weekly",
            "terms": "Net 30 payment terms",
            "rates": [
                {"item_id": "bed_sheet_single", "name": "Bed Sheet (Single)", "rate": 2.00},
                {"item_id": "bath_towel", "name": "Bath Towel", "rate": 1.25}
            ],
            "active": True
        }
        
        response = admin_session.post(f"{BASE_URL}/api/laundry/contracts/all", json=payload)
        assert response.status_code == 200, f"Failed: {response.text}"
        
        contract = response.json()
        assert contract["vendor"] == payload["vendor"]
        assert contract["contact_name"] == "Jane Doe"
        assert contract["pickup_schedule"] == "weekly"
        assert len(contract["rates"]) == 2
        assert contract["active"] == True
        assert "id" in contract
        
        self.__class__.created_contract_id = contract["id"]
        print(f"✓ POST /api/laundry/contracts/all created contract: {contract['id']}")
    
    def test_create_contract_missing_vendor_returns_400(self, admin_session):
        """POST /api/laundry/contracts/all returns 400 when vendor missing"""
        payload = {
            "contact_name": "Test",
            "rates": []
        }
        
        response = admin_session.post(f"{BASE_URL}/api/laundry/contracts/all", json=payload)
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("✓ POST /api/laundry/contracts/all returns 400 when vendor missing")
    
    def test_delete_contract(self, admin_session):
        """DELETE /api/laundry/contracts/all/{id} removes contract"""
        contract_id = getattr(self.__class__, 'created_contract_id', None)
        if not contract_id:
            pytest.skip("No contract created to delete")
        
        response = admin_session.delete(f"{BASE_URL}/api/laundry/contracts/all/{contract_id}")
        assert response.status_code == 200, f"Failed: {response.text}"
        
        result = response.json()
        assert result["deleted"] == True
        
        print(f"✓ DELETE /api/laundry/contracts/all/{contract_id} deleted successfully")
    
    def test_delete_unknown_contract_returns_404(self, admin_session):
        """DELETE /api/laundry/contracts/all/{id} returns 404 for unknown id"""
        response = admin_session.delete(f"{BASE_URL}/api/laundry/contracts/all/nonexistent-contract-12345")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ DELETE /api/laundry/contracts/all returns 404 for unknown id")


class TestAuthorizationCompliance(TestAuth):
    """Test role-based authorization for Compliance endpoints"""
    
    def test_compliance_create_requires_admin_manager(self):
        """Compliance create/update/delete require admin/manager role"""
        # Test without auth
        response = requests.post(f"{BASE_URL}/api/compliance/items/all", json={
            "title": "Unauthorized Test"
        })
        assert response.status_code == 401, f"Expected 401 without auth, got {response.status_code}"
        print("✓ Compliance create requires authentication")


class TestAuthorizationLaundry(TestAuth):
    """Test role-based authorization for Laundry endpoints"""
    
    def test_laundry_contracts_requires_admin_manager(self):
        """Laundry contracts require admin/manager role"""
        # Test without auth
        response = requests.get(f"{BASE_URL}/api/laundry/contracts/all")
        assert response.status_code == 401, f"Expected 401 without auth, got {response.status_code}"
        print("✓ Laundry contracts require authentication")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
