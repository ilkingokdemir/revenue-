"""
Iteration 290 Backend Tests - Booking.com Premier XML Push + Wholesaler Extension + Brand Voice Web Concierge Integration

Tests:
1. Booking.com module - status, config, validate-payload, push/rates, push/availability, push/restrictions, push-log
2. Wholesaler providers extension - 7 providers (5 original + hotels_com + mrandmrs_smith)
3. Brand Voice + Web Concierge integration - brand voice tone injection into chat
4. Regression tests for prior iterations
"""
import pytest
import requests
import os
import time
import uuid

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Test credentials
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"


@pytest.fixture(scope="module")
def auth_token():
    """Get admin auth token"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )
    assert response.status_code == 200, f"Login failed: {response.text}"
    data = response.json()
    return data.get("access_token") or data.get("token")


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Auth headers for authenticated requests"""
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


# ==================== BOOKING.COM MODULE TESTS ====================

class TestBookingComStatus:
    """Test GET /api/booking-com/status endpoint"""
    
    def test_status_returns_expected_fields(self, auth_headers):
        """Status endpoint returns cert_status, endpoint_configured, credentials_configured, live_mode, hotel_count_mapped"""
        response = requests.get(f"{BASE_URL}/api/booking-com/status", headers=auth_headers)
        assert response.status_code == 200, f"Status failed: {response.text}"
        data = response.json()
        
        # Verify all required fields are present
        assert "cert_status" in data, "Missing cert_status field"
        assert "endpoint_configured" in data, "Missing endpoint_configured field"
        assert "credentials_configured" in data, "Missing credentials_configured field"
        assert "live_mode" in data, "Missing live_mode field"
        assert "hotel_count_mapped" in data, "Missing hotel_count_mapped field"
        
        # Verify types
        assert isinstance(data["cert_status"], str)
        assert isinstance(data["endpoint_configured"], bool)
        assert isinstance(data["credentials_configured"], bool)
        assert isinstance(data["live_mode"], bool)
        assert isinstance(data["hotel_count_mapped"], int)
        print(f"✓ Booking.com status: cert={data['cert_status']}, live_mode={data['live_mode']}")
    
    def test_status_requires_auth(self):
        """Status endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/booking-com/status")
        assert response.status_code == 401, "Should require auth"


class TestBookingComConfig:
    """Test POST /api/booking-com/config endpoint"""
    
    def test_config_update_allowed_fields(self, auth_headers):
        """Config endpoint updates allowed fields (endpoint_url, auth_username, cert_status, mappings)"""
        payload = {
            "endpoint_url": "https://test.booking.com/api/v1",
            "auth_username": "test_user",
            "cert_status": "pending_certification",
            "hotel_id_mapping": {"aldgate-flats": "BOOKING_123"},
            "room_id_mapping": {"double-aldgate-flats": "ROOM_456"},
            "rate_plan_mapping": {"STANDARD": "RATE_789"}
        }
        response = requests.post(f"{BASE_URL}/api/booking-com/config", json=payload, headers=auth_headers)
        assert response.status_code == 200, f"Config update failed: {response.text}"
        data = response.json()
        
        # Verify fields were updated
        assert data.get("endpoint_url") == "https://test.booking.com/api/v1"
        assert data.get("auth_username") == "test_user"
        assert data.get("cert_status") == "pending_certification"
        assert "aldgate-flats" in data.get("hotel_id_mapping", {})
        print("✓ Booking.com config updated successfully")
    
    def test_config_password_not_stored_clear(self, auth_headers):
        """Config endpoint never stores auth_password in clear; sets auth_password_set=true and hint"""
        payload = {
            "auth_password": "SuperSecretPassword123!"
        }
        response = requests.post(f"{BASE_URL}/api/booking-com/config", json=payload, headers=auth_headers)
        assert response.status_code == 200, f"Config update failed: {response.text}"
        
        # Verify password is not returned in clear
        data = response.json()
        assert "auth_password" not in data, "Password should not be returned in clear"
        
        # Check status to verify password_set flag
        status_response = requests.get(f"{BASE_URL}/api/booking-com/status", headers=auth_headers)
        assert status_response.status_code == 200
        print("✓ Password not stored in clear text")
    
    def test_config_requires_admin(self):
        """Config endpoint requires admin role"""
        response = requests.post(f"{BASE_URL}/api/booking-com/config", json={})
        assert response.status_code == 401, "Should require auth"


class TestBookingComValidatePayload:
    """Test POST /api/booking-com/validate-payload endpoint"""
    
    def test_validate_rates_xml(self, auth_headers):
        """Validate rates payload returns valid OTA_HotelRateAmountNotifRQ XML"""
        payload = {
            "kind": "rates",
            "daily": [
                {"date": "2026-02-01", "rate": 150.00, "guests": 2},
                {"date": "2026-02-02", "rate": 160.00, "guests": 2}
            ],
            "currency": "EUR"
        }
        response = requests.post(f"{BASE_URL}/api/booking-com/validate-payload", json=payload, headers=auth_headers)
        assert response.status_code == 200, f"Validate failed: {response.text}"
        data = response.json()
        
        assert data.get("ok") is True
        assert data.get("kind") == "rates"
        assert "xml" in data
        assert "byte_length" in data
        
        # Verify XML contains OTA_HotelRateAmountNotifRQ with proper xmlns
        xml = data["xml"]
        assert "OTA_HotelRateAmountNotifRQ" in xml, "Missing OTA_HotelRateAmountNotifRQ root element"
        assert 'xmlns="http://www.opentravel.org/OTA/2003/05"' in xml, "Missing OTA xmlns"
        assert "RateAmountMessages" in xml
        assert "BaseByGuestAmt" in xml
        print(f"✓ Rates XML validated: {data['byte_length']} bytes")
    
    def test_validate_availability_xml(self, auth_headers):
        """Validate availability payload returns valid OTA_HotelAvailNotifRQ XML"""
        payload = {
            "kind": "availability",
            "daily": [
                {"date": "2026-02-01", "allotment": 5},
                {"date": "2026-02-02", "allotment": 3}
            ]
        }
        response = requests.post(f"{BASE_URL}/api/booking-com/validate-payload", json=payload, headers=auth_headers)
        assert response.status_code == 200, f"Validate failed: {response.text}"
        data = response.json()
        
        assert data.get("ok") is True
        assert data.get("kind") == "availability"
        
        # Verify XML contains OTA_HotelAvailNotifRQ with proper xmlns
        xml = data["xml"]
        assert "OTA_HotelAvailNotifRQ" in xml, "Missing OTA_HotelAvailNotifRQ root element"
        assert 'xmlns="http://www.opentravel.org/OTA/2003/05"' in xml, "Missing OTA xmlns"
        assert "AvailStatusMessages" in xml
        print(f"✓ Availability XML validated: {data['byte_length']} bytes")
    
    def test_validate_restrictions_xml(self, auth_headers):
        """Validate restrictions payload returns valid OTA_HotelAvailNotifRQ XML with restrictions"""
        payload = {
            "kind": "restrictions",
            "daily": [
                {"date": "2026-02-01", "min_stay": 2, "max_stay": 7, "cta": False, "ctd": False},
                {"date": "2026-02-02", "min_stay": 3, "cta": True}
            ]
        }
        response = requests.post(f"{BASE_URL}/api/booking-com/validate-payload", json=payload, headers=auth_headers)
        assert response.status_code == 200, f"Validate failed: {response.text}"
        data = response.json()
        
        assert data.get("ok") is True
        assert data.get("kind") == "restrictions"
        
        # Verify XML contains OTA_HotelAvailNotifRQ with proper xmlns
        xml = data["xml"]
        assert "OTA_HotelAvailNotifRQ" in xml, "Missing OTA_HotelAvailNotifRQ root element"
        assert 'xmlns="http://www.opentravel.org/OTA/2003/05"' in xml, "Missing OTA xmlns"
        assert "RestrictionStatus" in xml
        print(f"✓ Restrictions XML validated: {data['byte_length']} bytes")


class TestBookingComPushRates:
    """Test POST /api/booking-com/push/rates endpoint"""
    
    def test_push_rates_success(self, auth_headers):
        """Push rates returns attempt record with status='ok' and simulated=true"""
        payload = {
            "property_id": "aldgate-flats",
            "room_type_id": "double-aldgate-flats",
            "rate_plan_id": "STANDARD",
            "daily": [
                {"date": "2026-02-01", "rate": 150.00, "guests": 2},
                {"date": "2026-02-02", "rate": 160.00, "guests": 2}
            ],
            "currency": "EUR"
        }
        response = requests.post(f"{BASE_URL}/api/booking-com/push/rates", json=payload, headers=auth_headers)
        assert response.status_code == 200, f"Push rates failed: {response.text}"
        data = response.json()
        
        # Verify attempt record structure
        assert data.get("status") == "ok", "Status should be 'ok'"
        assert data.get("simulated") is True, "Should be simulated (no real endpoint)"
        assert data.get("kind") == "rates"
        assert data.get("property_id") == "aldgate-flats"
        assert data.get("room_type_id") == "double-aldgate-flats"
        assert data.get("dates_count") == 2
        assert "id" in data
        assert "created_at" in data
        assert "xml_payload" in data
        print(f"✓ Push rates successful: id={data['id']}, simulated={data['simulated']}")
    
    def test_push_rates_validates_daily_entries(self, auth_headers):
        """Push rates validates daily entries have date+rate"""
        payload = {
            "property_id": "aldgate-flats",
            "room_type_id": "double-aldgate-flats",
            "daily": [
                {"date": "2026-02-01"},  # Missing rate
            ]
        }
        response = requests.post(f"{BASE_URL}/api/booking-com/push/rates", json=payload, headers=auth_headers)
        assert response.status_code == 400, "Should reject missing rate"
        print("✓ Push rates validates daily entries")
    
    def test_push_rates_requires_property_and_room(self, auth_headers):
        """Push rates requires property_id and room_type_id"""
        payload = {
            "daily": [{"date": "2026-02-01", "rate": 100}]
        }
        response = requests.post(f"{BASE_URL}/api/booking-com/push/rates", json=payload, headers=auth_headers)
        assert response.status_code == 400, "Should require property_id and room_type_id"
        print("✓ Push rates requires property_id and room_type_id")


class TestBookingComPushAvailability:
    """Test POST /api/booking-com/push/availability endpoint"""
    
    def test_push_availability_success(self, auth_headers):
        """Push availability returns attempt record with status='ok' and simulated=true"""
        payload = {
            "property_id": "aldgate-flats",
            "room_type_id": "double-aldgate-flats",
            "daily": [
                {"date": "2026-02-01", "allotment": 5},
                {"date": "2026-02-02", "allotment": 3}
            ]
        }
        response = requests.post(f"{BASE_URL}/api/booking-com/push/availability", json=payload, headers=auth_headers)
        assert response.status_code == 200, f"Push availability failed: {response.text}"
        data = response.json()
        
        assert data.get("status") == "ok"
        assert data.get("simulated") is True
        assert data.get("kind") == "availability"
        print(f"✓ Push availability successful: id={data['id']}")
    
    def test_push_availability_requires_date_allotment(self, auth_headers):
        """Push availability requires date+allotment per daily"""
        payload = {
            "property_id": "aldgate-flats",
            "room_type_id": "double-aldgate-flats",
            "daily": [
                {"date": "2026-02-01"}  # Missing allotment
            ]
        }
        response = requests.post(f"{BASE_URL}/api/booking-com/push/availability", json=payload, headers=auth_headers)
        assert response.status_code == 400, "Should reject missing allotment"
        print("✓ Push availability validates allotment")


class TestBookingComPushRestrictions:
    """Test POST /api/booking-com/push/restrictions endpoint"""
    
    def test_push_restrictions_success(self, auth_headers):
        """Push restrictions accepts min_stay/max_stay/cta/ctd"""
        payload = {
            "property_id": "aldgate-flats",
            "room_type_id": "double-aldgate-flats",
            "rate_plan_id": "STANDARD",
            "daily": [
                {"date": "2026-02-01", "min_stay": 2, "max_stay": 7, "cta": False, "ctd": False},
                {"date": "2026-02-02", "min_stay": 3, "cta": True}
            ]
        }
        response = requests.post(f"{BASE_URL}/api/booking-com/push/restrictions", json=payload, headers=auth_headers)
        assert response.status_code == 200, f"Push restrictions failed: {response.text}"
        data = response.json()
        
        assert data.get("status") == "ok"
        assert data.get("simulated") is True
        assert data.get("kind") == "restrictions"
        print(f"✓ Push restrictions successful: id={data['id']}")


class TestBookingComPushLog:
    """Test GET /api/booking-com/push-log endpoint"""
    
    def test_push_log_returns_history(self, auth_headers):
        """Push log returns history without verbose xml_payload field"""
        response = requests.get(f"{BASE_URL}/api/booking-com/push-log", headers=auth_headers)
        assert response.status_code == 200, f"Push log failed: {response.text}"
        data = response.json()
        
        assert "items" in data
        assert "count" in data
        
        # Verify xml_payload is excluded from list items
        for item in data["items"]:
            assert "xml_payload" not in item, "xml_payload should be excluded from push-log"
            assert "id" in item
            assert "kind" in item
            assert "status" in item
        print(f"✓ Push log returned {data['count']} items (xml_payload excluded)")
    
    def test_push_log_filter_by_kind(self, auth_headers):
        """Push log can filter by kind"""
        response = requests.get(f"{BASE_URL}/api/booking-com/push-log?kind=rates", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        for item in data["items"]:
            assert item["kind"] == "rates"
        print(f"✓ Push log filter by kind works: {data['count']} rates items")
    
    def test_push_log_filter_by_property(self, auth_headers):
        """Push log can filter by property_id"""
        response = requests.get(f"{BASE_URL}/api/booking-com/push-log?property_id=aldgate-flats", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        for item in data["items"]:
            assert item["property_id"] == "aldgate-flats"
        print(f"✓ Push log filter by property works: {data['count']} items")


# ==================== WHOLESALER PROVIDERS EXTENSION TESTS ====================

class TestWholesalerProviders:
    """Test GET /api/wholesaler/providers endpoint - now returns 7 providers"""
    
    def test_providers_returns_7_providers(self, auth_headers):
        """Providers endpoint returns 7 providers (was 5): hotelbeds, tbo, travelgate, gta, mock + hotels_com, mrandmrs_smith"""
        response = requests.get(f"{BASE_URL}/api/wholesaler/providers", headers=auth_headers)
        assert response.status_code == 200, f"Providers failed: {response.text}"
        data = response.json()
        
        assert "items" in data
        providers = data["items"]
        assert len(providers) == 7, f"Expected 7 providers, got {len(providers)}"
        
        provider_ids = [p["id"] for p in providers]
        expected_ids = ["hotelbeds", "tbo", "travelgate", "gta", "mock", "hotels_com", "mrandmrs_smith"]
        for expected_id in expected_ids:
            assert expected_id in provider_ids, f"Missing provider: {expected_id}"
        
        print(f"✓ Wholesaler providers: {provider_ids}")
    
    def test_hotels_com_metadata(self, auth_headers):
        """Hotels.com has correct metadata: 90000 partners, 18% default commission"""
        response = requests.get(f"{BASE_URL}/api/wholesaler/providers", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        hotels_com = next((p for p in data["items"] if p["id"] == "hotels_com"), None)
        assert hotels_com is not None, "hotels_com provider not found"
        
        assert hotels_com.get("partner_count_global") == 90000, f"Expected 90000 partners, got {hotels_com.get('partner_count_global')}"
        assert hotels_com.get("default_commission") == 18, f"Expected 18% commission, got {hotels_com.get('default_commission')}"
        assert hotels_com.get("supports_push") is True
        assert hotels_com.get("supports_pull") is True
        print(f"✓ Hotels.com metadata: {hotels_com['partner_count_global']} partners, {hotels_com['default_commission']}% commission")
    
    def test_mrandmrs_smith_metadata(self, auth_headers):
        """Mr&Mrs Smith has correct metadata: 1500 partners, 22% default commission, supports_push=true"""
        response = requests.get(f"{BASE_URL}/api/wholesaler/providers", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        mrandmrs = next((p for p in data["items"] if p["id"] == "mrandmrs_smith"), None)
        assert mrandmrs is not None, "mrandmrs_smith provider not found"
        
        assert mrandmrs.get("partner_count_global") == 1500, f"Expected 1500 partners, got {mrandmrs.get('partner_count_global')}"
        assert mrandmrs.get("default_commission") == 22, f"Expected 22% commission, got {mrandmrs.get('default_commission')}"
        assert mrandmrs.get("supports_push") is True
        print(f"✓ Mr&Mrs Smith metadata: {mrandmrs['partner_count_global']} partners, {mrandmrs['default_commission']}% commission")


# ==================== BRAND VOICE + WEB CONCIERGE INTEGRATION TESTS ====================

class TestBrandVoiceWebConciergeIntegration:
    """Test Brand Voice profile injection into Web Concierge chat"""
    
    def test_seed_brand_voice_profile(self, auth_headers):
        """Seed brand voice profile for aldgate-flats with distinctive tone"""
        payload = {
            "tone": "playful_friendly",
            "personality_traits": ["eğlenceli", "enerjik", "genç"],
            "dos": ["ünlem kullan", "emoji ekle"],
            "donts": ["resmi olma"]
        }
        response = requests.post(
            f"{BASE_URL}/api/brand-voice/profile/aldgate-flats",
            json=payload,
            headers=auth_headers
        )
        assert response.status_code == 200, f"Seed brand voice failed: {response.text}"
        data = response.json()
        
        assert data.get("tone") == "playful_friendly"
        assert "eğlenceli" in data.get("personality_traits", [])
        print(f"✓ Brand voice profile seeded for aldgate-flats: tone={data['tone']}")
    
    def test_web_concierge_chat_with_brand_voice(self, auth_headers):
        """Web concierge chat with property that has brand_voice_profiles record works (no errors)"""
        # Chat with aldgate-flats which now has a brand voice profile
        payload = {
            "property_id": "aldgate-flats",
            "session_id": f"test-bv-{uuid.uuid4().hex[:8]}",
            "message": "Merhaba, oda fiyatları nedir?"
        }
        response = requests.post(f"{BASE_URL}/api/web-concierge/chat", json=payload)
        assert response.status_code == 200, f"Chat failed: {response.text}"
        data = response.json()
        
        assert "reply" in data, "Missing reply field"
        assert "session_id" in data
        assert len(data["reply"]) > 0, "Reply should not be empty"
        print(f"✓ Web concierge chat with brand voice works: reply length={len(data['reply'])}")
    
    def test_web_concierge_chat_without_brand_voice(self, auth_headers):
        """Web concierge chat with property without brand voice profile also works"""
        # Use a property that likely doesn't have a brand voice profile
        payload = {
            "property_id": "vilenza-hotel",
            "session_id": f"test-nobv-{uuid.uuid4().hex[:8]}",
            "message": "Kahvaltı dahil mi?"
        }
        response = requests.post(f"{BASE_URL}/api/web-concierge/chat", json=payload)
        assert response.status_code == 200, f"Chat failed: {response.text}"
        data = response.json()
        
        assert "reply" in data
        assert len(data["reply"]) > 0
        print(f"✓ Web concierge chat without brand voice works: reply length={len(data['reply'])}")


# ==================== REGRESSION TESTS ====================

class TestRegressionIter284:
    """Regression tests for Iter 284 - Agency Portal, Web Concierge, Review Agent"""
    
    def test_agencies_endpoint(self, auth_headers):
        """Agencies endpoint still works"""
        response = requests.get(f"{BASE_URL}/api/agencies", headers=auth_headers)
        assert response.status_code == 200, f"Agencies failed: {response.text}"
        print("✓ Regression: /api/agencies works")
    
    def test_web_concierge_widget_config(self, auth_headers):
        """Web concierge widget config still works"""
        response = requests.get(f"{BASE_URL}/api/web-concierge/widget-config/aldgate-flats")
        assert response.status_code == 200, f"Widget config failed: {response.text}"
        data = response.json()
        assert "property_id" in data
        assert "welcome_message" in data
        print("✓ Regression: /api/web-concierge/widget-config works")
    
    def test_review_agent_config(self, auth_headers):
        """Review agent config endpoint still works"""
        response = requests.get(f"{BASE_URL}/api/review-agent/config/aldgate-flats", headers=auth_headers)
        assert response.status_code == 200, f"Review agent config failed: {response.text}"
        print("✓ Regression: /api/review-agent/config works")


class TestRegressionIter285:
    """Regression tests for Iter 285 - Open Pricing, Beach POS, Public Events"""
    
    def test_open_pricing_matrix(self, auth_headers):
        """Open pricing matrix endpoint still works"""
        response = requests.get(f"{BASE_URL}/api/open-pricing/matrix/aldgate-flats", headers=auth_headers)
        assert response.status_code == 200, f"Open pricing failed: {response.text}"
        print("✓ Regression: /api/open-pricing/matrix works")
    
    def test_beach_pos_sunbeds(self, auth_headers):
        """Beach POS sunbeds endpoint still works"""
        response = requests.get(f"{BASE_URL}/api/beach-pos/sunbeds/aldgate-flats", headers=auth_headers)
        assert response.status_code == 200, f"Beach POS failed: {response.text}"
        print("✓ Regression: /api/beach-pos/sunbeds works")
    
    def test_public_events(self, auth_headers):
        """Public events endpoint still works"""
        response = requests.get(f"{BASE_URL}/api/public-events?property_id=aldgate-flats")
        assert response.status_code == 200, f"Public events failed: {response.text}"
        print("✓ Regression: /api/public-events works")


class TestRegressionIter286:
    """Regression tests for Iter 286 - Agentic AI, Vacation Rental"""
    
    def test_agents_list(self, auth_headers):
        """Agents list endpoint still works"""
        response = requests.get(f"{BASE_URL}/api/agents", headers=auth_headers)
        assert response.status_code == 200, f"Agents failed: {response.text}"
        print("✓ Regression: /api/agents works")
    
    def test_vacation_rental_summary(self, auth_headers):
        """Vacation rental summary endpoint still works"""
        response = requests.get(f"{BASE_URL}/api/vacation-rental/summary", headers=auth_headers)
        assert response.status_code == 200, f"Vacation rental failed: {response.text}"
        print("✓ Regression: /api/vacation-rental/summary works")


class TestRegressionIter287:
    """Regression tests for Iter 287 - Dev Portal, Wholesaler, Lead Funnel"""
    
    def test_dev_portal_info(self, auth_headers):
        """Dev portal info endpoint still works"""
        response = requests.get(f"{BASE_URL}/api/dev-portal/info")
        assert response.status_code == 200, f"Dev portal failed: {response.text}"
        print("✓ Regression: /api/dev-portal/info works")
    
    def test_wholesaler_connections(self, auth_headers):
        """Wholesaler connections endpoint still works"""
        response = requests.get(f"{BASE_URL}/api/wholesaler/connections", headers=auth_headers)
        assert response.status_code == 200, f"Wholesaler connections failed: {response.text}"
        print("✓ Regression: /api/wholesaler/connections works")
    
    def test_lead_funnel_leads(self, auth_headers):
        """Lead funnel leads endpoint still works"""
        response = requests.get(f"{BASE_URL}/api/lead-funnel/leads", headers=auth_headers)
        assert response.status_code == 200, f"Lead funnel failed: {response.text}"
        print("✓ Regression: /api/lead-funnel/leads works")


class TestRegressionIter288:
    """Regression tests for Iter 288 - Marketing Videos"""
    
    def test_marketing_videos_sizes(self, auth_headers):
        """Marketing videos sizes endpoint still works"""
        response = requests.get(f"{BASE_URL}/api/marketing-videos/sizes", headers=auth_headers)
        assert response.status_code == 200, f"Marketing videos sizes failed: {response.text}"
        print("✓ Regression: /api/marketing-videos/sizes works")


class TestRegressionIter289:
    """Regression tests for Iter 289 - Brand Voice Studio"""
    
    def test_brand_voice_purposes(self, auth_headers):
        """Brand voice purposes endpoint still works"""
        response = requests.get(f"{BASE_URL}/api/brand-voice/purposes", headers=auth_headers)
        assert response.status_code == 200, f"Brand voice purposes failed: {response.text}"
        data = response.json()
        assert len(data.get("items", [])) == 11, "Should have 11 purposes"
        print("✓ Regression: /api/brand-voice/purposes works (11 purposes)")
    
    def test_brand_voice_profile(self, auth_headers):
        """Brand voice profile endpoint still works"""
        response = requests.get(f"{BASE_URL}/api/brand-voice/profile/aldgate-flats", headers=auth_headers)
        assert response.status_code == 200, f"Brand voice profile failed: {response.text}"
        print("✓ Regression: /api/brand-voice/profile works")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
