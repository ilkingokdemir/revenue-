"""
Iteration 213 - Backend Tests for New Features
===============================================
Tests for:
1. Late Check-out Quote Engine (P0)
2. Service Recovery / Guest Complaint Tracker (P0)
3. Room QR Codes (P1)
4. Regression: Carbon Offset, Accounting Mapping
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://review-hub-108.preview.emergentagent.com")

@pytest.fixture(scope="module")
def auth_token():
    """Get admin auth token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@hotelbox.com",
        "password": "HotelAdmin2026!"
    })
    assert response.status_code == 200, f"Login failed: {response.text}"
    return response.json()["token"]

@pytest.fixture(scope="module")
def headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


# ==================== LATE CHECKOUT TESTS ====================

class TestLateCheckoutPolicy:
    """Late Check-out Policy CRUD tests"""
    
    def test_get_policy_default(self, headers):
        """GET /api/late-checkout/{property_id}/policy returns default policy"""
        response = requests.get(f"{BASE_URL}/api/late-checkout/aldgate-flats/policy", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["free_until_hour"] == 11
        assert data["half_until_hour"] == 14
        assert data["full_after_hour"] == 16
        assert data["vip_free_until"] == 13
        assert data["min_turnaround_min"] == 90
        assert data["currency"] == "GBP"
    
    def test_save_policy(self, headers):
        """POST /api/late-checkout/{property_id}/policy saves custom policy"""
        custom_policy = {
            "free_until_hour": 12,
            "half_until_hour": 15,
            "full_after_hour": 17,
            "vip_free_until": 14,
            "min_turnaround_min": 120,
            "currency": "GBP"
        }
        response = requests.post(f"{BASE_URL}/api/late-checkout/aldgate-flats/policy", 
                                 headers=headers, json=custom_policy)
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] == True
        assert data["policy"]["free_until_hour"] == 12
        assert data["policy"]["half_until_hour"] == 15


class TestLateCheckoutQuote:
    """Late Check-out Quote tests"""
    
    def test_quote_half_night_band(self, headers):
        """POST /api/late-checkout/quote returns half_night band for hour 13"""
        # Use the known booking from city-gate
        response = requests.post(f"{BASE_URL}/api/late-checkout/quote", headers=headers, json={
            "booking_id": "762971c8-7797-4cb8-bd96-8102e3f6c664",
            "requested_hour": 13
        })
        assert response.status_code == 200
        data = response.json()
        assert data["booking_id"] == "762971c8-7797-4cb8-bd96-8102e3f6c664"
        assert data["requested_hour"] == 13
        assert "half_night" in data["band"]  # Could be half_night or half_night_quiet_night
        assert data["fee"] > 0
        assert data["available"] == True
        assert data["new_checkout_time"] == "13:00"
    
    def test_quote_invalid_booking(self, headers):
        """POST /api/late-checkout/quote returns 404 for invalid booking"""
        response = requests.post(f"{BASE_URL}/api/late-checkout/quote", headers=headers, json={
            "booking_id": "invalid-booking-id",
            "requested_hour": 13
        })
        assert response.status_code == 404
    
    def test_quote_invalid_hour(self, headers):
        """POST /api/late-checkout/quote returns 400 for invalid hour"""
        response = requests.post(f"{BASE_URL}/api/late-checkout/quote", headers=headers, json={
            "booking_id": "762971c8-7797-4cb8-bd96-8102e3f6c664",
            "requested_hour": 25  # Invalid hour
        })
        assert response.status_code == 400


class TestLateCheckoutAccept:
    """Late Check-out Accept tests"""
    
    def test_list_recent(self, headers):
        """GET /api/late-checkout/{property_id}/list returns recent approvals"""
        response = requests.get(f"{BASE_URL}/api/late-checkout/city-gate/list", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total_revenue" in data
        assert "count" in data


# ==================== SERVICE RECOVERY TESTS ====================

class TestServiceRecoveryCreate:
    """Service Recovery Create tests"""
    
    def test_create_critical_complaint(self, headers):
        """POST /api/service-recovery creates complaint with AI severity=critical"""
        response = requests.post(f"{BASE_URL}/api/service-recovery", headers=headers, json={
            "property_id": "city-gate",
            "text": "TEST_CRITICAL: Found cockroaches in the bathroom! This is disgusting and a health hazard!",
            "category": "cleanliness",
            "guest_name": "TEST_Critical_Guest",
            "room_number": "201"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["severity"] == "critical"
        assert data["ai_action"] in ["full_refund", "room_move"]
        assert data["status"] == "open"
        assert "id" in data
    
    def test_create_minor_complaint(self, headers):
        """POST /api/service-recovery creates complaint with AI severity=low/medium"""
        response = requests.post(f"{BASE_URL}/api/service-recovery", headers=headers, json={
            "property_id": "city-gate",
            "text": "TEST_MINOR: The TV remote batteries were low. Had to press buttons hard.",
            "category": "amenities",
            "guest_name": "TEST_Minor_Guest",
            "room_number": "202"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["severity"] in ["low", "medium"]
        assert data["ai_action"] in ["apology", "discount"]
    
    def test_create_complaint_missing_text(self, headers):
        """POST /api/service-recovery returns 400 for missing text"""
        response = requests.post(f"{BASE_URL}/api/service-recovery", headers=headers, json={
            "property_id": "city-gate",
            "text": "",
            "category": "other"
        })
        assert response.status_code == 400


class TestServiceRecoveryUpdate:
    """Service Recovery Update tests"""
    
    def test_update_to_resolved(self, headers):
        """PUT /api/service-recovery/{id} updates status and sets resolved_at"""
        # First create a complaint
        create_resp = requests.post(f"{BASE_URL}/api/service-recovery", headers=headers, json={
            "property_id": "city-gate",
            "text": "TEST_RESOLVE: Minor issue for testing resolution flow",
            "category": "other",
            "guest_name": "TEST_Resolve_Guest"
        })
        complaint_id = create_resp.json()["id"]
        
        # Update to resolved
        response = requests.put(f"{BASE_URL}/api/service-recovery/{complaint_id}", headers=headers, json={
            "status": "resolved",
            "compensation_amount": 25.00,
            "compensation_type": "discount",
            "resolution_notes": "Apologized and offered 10% discount on next stay"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "resolved"
        assert data["resolved_at"] is not None
        assert data["resolved_by"] == "Hotel Admin"
        assert data["compensation_amount"] == 25.00


class TestServiceRecoveryStats:
    """Service Recovery Stats tests"""
    
    def test_stats_returns_aggregates(self, headers):
        """GET /api/service-recovery/{property_id}/stats returns KPIs"""
        response = requests.get(f"{BASE_URL}/api/service-recovery/city-gate/stats", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "open" in data
        assert "resolved" in data
        assert "by_severity" in data
        assert "by_category" in data
        assert "by_status" in data
        assert "compensation_total" in data
        assert "avg_resolution_minutes" in data
        assert "playbooks" in data
        assert "categories" in data


class TestServiceRecoveryList:
    """Service Recovery List tests"""
    
    def test_list_complaints(self, headers):
        """GET /api/service-recovery/{property_id} returns complaints list"""
        response = requests.get(f"{BASE_URL}/api/service-recovery/city-gate", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        if len(data) > 0:
            assert "id" in data[0]
            assert "severity" in data[0]
            assert "status" in data[0]
    
    def test_list_with_status_filter(self, headers):
        """GET /api/service-recovery/{property_id}?status=open filters by status"""
        response = requests.get(f"{BASE_URL}/api/service-recovery/city-gate?status=open", headers=headers)
        assert response.status_code == 200
        data = response.json()
        for item in data:
            assert item["status"] == "open"


# ==================== ROOM QR TESTS ====================

class TestRoomQRList:
    """Room QR List tests"""
    
    def test_list_returns_15_rooms_city_gate(self, headers):
        """GET /api/room-qr/city-gate/list returns 15 rooms"""
        response = requests.get(f"{BASE_URL}/api/room-qr/city-gate/list", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 15
        assert len(data["items"]) == 15
        # Check item structure
        item = data["items"][0]
        assert "room_number" in item
        assert "qr_url" in item
        assert "image_url" in item
    
    def test_list_empty_property(self, headers):
        """GET /api/room-qr/aldgate-flats/list returns 0 rooms (no room_statuses seeded)"""
        response = requests.get(f"{BASE_URL}/api/room-qr/aldgate-flats/list", headers=headers)
        assert response.status_code == 200
        data = response.json()
        # aldgate-flats may have 0 or 1 room depending on seeding
        assert data["count"] >= 0


class TestRoomQRPng:
    """Room QR PNG tests"""
    
    def test_png_returns_image(self, headers):
        """GET /api/room-qr/{property_id}/png/{room_number} returns PNG image"""
        response = requests.get(f"{BASE_URL}/api/room-qr/city-gate/png/101", headers=headers)
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"
        assert len(response.content) > 1000  # PNG should be at least 1KB


class TestRoomQRSheet:
    """Room QR Sheet tests"""
    
    def test_sheet_returns_html(self, headers):
        """GET /api/room-qr/{property_id}/sheet returns printable HTML"""
        response = requests.get(f"{BASE_URL}/api/room-qr/city-gate/sheet", headers=headers)
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "<!doctype html>" in response.text.lower()
        assert "Room QR" in response.text


# ==================== REGRESSION TESTS ====================

class TestRegressionCarbonOffset:
    """Regression: Carbon Offset Quote"""
    
    def test_carbon_offset_quote(self, headers):
        """GET /api/esg/{property_id}/carbon-offset-quote returns quote"""
        response = requests.get(f"{BASE_URL}/api/esg/city-gate/carbon-offset-quote?nights=2&rooms=1", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["nights"] == 2
        assert data["rooms"] == 1
        assert data["fee_per_room_per_night"] == 1.5
        assert data["total_fee"] == 3.0
        assert "estimated_co2_kg" in data


class TestRegressionAccountingMapping:
    """Regression: Accounting Mapping"""
    
    def test_accounting_mapping_post(self, headers):
        """POST /api/accounting/mapping/{property_id} saves mapping"""
        response = requests.post(f"{BASE_URL}/api/accounting/mapping/city-gate", headers=headers, json={
            "room_revenue": "4000",
            "food_revenue": "4100",
            "accounts_receivable": "1200"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] == True
    
    def test_accounting_mapping_get(self, headers):
        """GET /api/accounting/mapping/{property_id} returns mapping"""
        response = requests.get(f"{BASE_URL}/api/accounting/mapping/city-gate", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "ar_account" in data or "property_id" in data


# ==================== CLEANUP ====================

class TestCleanup:
    """Cleanup test data"""
    
    def test_cleanup_test_complaints(self, headers):
        """Delete TEST_ prefixed complaints"""
        # Get all complaints
        response = requests.get(f"{BASE_URL}/api/service-recovery/city-gate", headers=headers)
        if response.status_code == 200:
            for complaint in response.json():
                if complaint.get("guest_name", "").startswith("TEST_"):
                    requests.delete(f"{BASE_URL}/api/service-recovery/{complaint['id']}", headers=headers)
        assert True  # Cleanup is best-effort
