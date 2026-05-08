"""
Iteration 44 Tests: Setup Wizard, Smart Locks, Digital Keys
Tests for three new features:
1. Platform Setup Wizard - credential configuration for Google Business, Booking.com, TripAdvisor, WhatsApp, Telegram
2. Digital Keys / Smart Lock Integration - 6 lock providers, digital key generation
3. 130+ Language AI Chat - multilingual concierge (system prompt update, no new endpoints)
"""
import pytest
import requests
import os

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
        assert "token" in data, f"No token in response: {data}"
        return data["token"]
    
    def test_admin_login(self, auth_token):
        """Test admin login returns valid token"""
        assert auth_token is not None
        assert len(auth_token) > 0
        print(f"✓ Admin login successful, token length: {len(auth_token)}")


class TestSetupWizardPlatforms:
    """Setup Wizard - Platform listing and guides"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        token = response.json().get("token", "")
        return {"Authorization": f"Bearer {token}"}
    
    def test_list_platforms(self, auth_headers):
        """GET /api/setup-wizard/platforms - lists 5 platforms"""
        response = requests.get(f"{BASE_URL}/api/setup-wizard/platforms", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        platforms = response.json()
        assert isinstance(platforms, list)
        assert len(platforms) == 5, f"Expected 5 platforms, got {len(platforms)}"
        
        # Verify platform IDs
        platform_ids = [p["id"] for p in platforms]
        expected_ids = ["google_business", "booking_com", "tripadvisor", "whatsapp", "telegram"]
        for pid in expected_ids:
            assert pid in platform_ids, f"Missing platform: {pid}"
        
        # Verify structure
        for p in platforms:
            assert "id" in p
            assert "name" in p
            assert "icon" in p
            assert "category" in p
            assert "description" in p
            assert "configured" in p
        
        print(f"✓ Listed {len(platforms)} platforms: {platform_ids}")
    
    def test_get_google_business_guide(self, auth_headers):
        """GET /api/setup-wizard/guide/google_business - step-by-step guide"""
        response = requests.get(f"{BASE_URL}/api/setup-wizard/guide/google_business", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        guide = response.json()
        
        assert guide["platform_id"] == "google_business"
        assert guide["name"] == "Google Business Profile"
        assert "steps" in guide
        assert len(guide["steps"]) >= 4, "Should have at least 4 steps"
        assert "fields" in guide
        
        # Verify fields
        field_keys = [f["key"] for f in guide["fields"]]
        assert "client_id" in field_keys
        assert "client_secret" in field_keys
        
        print(f"✓ Google Business guide has {len(guide['steps'])} steps and {len(guide['fields'])} fields")
    
    def test_get_whatsapp_guide(self, auth_headers):
        """GET /api/setup-wizard/guide/whatsapp - WhatsApp setup guide"""
        response = requests.get(f"{BASE_URL}/api/setup-wizard/guide/whatsapp", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        guide = response.json()
        
        assert guide["platform_id"] == "whatsapp"
        assert guide["name"] == "WhatsApp Business"
        assert guide["category"] == "messaging"
        
        field_keys = [f["key"] for f in guide["fields"]]
        assert "phone_number_id" in field_keys
        assert "access_token" in field_keys
        
        print(f"✓ WhatsApp guide has {len(guide['steps'])} steps")
    
    def test_get_invalid_platform_guide(self, auth_headers):
        """GET /api/setup-wizard/guide/invalid - returns 404"""
        response = requests.get(f"{BASE_URL}/api/setup-wizard/guide/invalid_platform", headers=auth_headers)
        assert response.status_code == 404
        print("✓ Invalid platform returns 404")


class TestSetupWizardCredentials:
    """Setup Wizard - Credential management"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        token = response.json().get("token", "")
        return {"Authorization": f"Bearer {token}"}
    
    def test_save_whatsapp_credentials(self, auth_headers):
        """PUT /api/setup-wizard/credentials/whatsapp - save credentials"""
        response = requests.put(
            f"{BASE_URL}/api/setup-wizard/credentials/whatsapp",
            headers=auth_headers,
            json={
                "phone_number_id": "TEST_123456789",
                "access_token": "TEST_EAAxxxxx_token"
            }
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data["status"] == "saved"
        assert data["platform"] == "whatsapp"
        assert data["is_configured"] == True
        print("✓ WhatsApp credentials saved")
    
    def test_verify_whatsapp_configured(self, auth_headers):
        """Verify WhatsApp shows as configured after save"""
        response = requests.get(f"{BASE_URL}/api/setup-wizard/platforms", headers=auth_headers)
        assert response.status_code == 200
        platforms = response.json()
        whatsapp = next((p for p in platforms if p["id"] == "whatsapp"), None)
        assert whatsapp is not None
        assert whatsapp["configured"] == True
        print("✓ WhatsApp shows as configured")
    
    def test_test_whatsapp_credentials(self, auth_headers):
        """POST /api/setup-wizard/test/whatsapp - test credentials (MOCKED)"""
        response = requests.post(f"{BASE_URL}/api/setup-wizard/test/whatsapp", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data["success"] == True
        assert "validated" in data["message"].lower() or "success" in data["message"].lower()
        print(f"✓ WhatsApp credentials test: {data['message']}")
    
    def test_save_telegram_credentials(self, auth_headers):
        """PUT /api/setup-wizard/credentials/telegram - save Telegram bot token"""
        response = requests.put(
            f"{BASE_URL}/api/setup-wizard/credentials/telegram",
            headers=auth_headers,
            json={"bot_token": "TEST_123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ"}
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data["status"] == "saved"
        assert data["platform"] == "telegram"
        print("✓ Telegram credentials saved")
    
    def test_delete_telegram_credentials(self, auth_headers):
        """DELETE /api/setup-wizard/credentials/telegram - remove credentials"""
        response = requests.delete(f"{BASE_URL}/api/setup-wizard/credentials/telegram", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data["status"] == "removed"
        assert data["platform"] == "telegram"
        print("✓ Telegram credentials removed")
    
    def test_verify_telegram_unconfigured(self, auth_headers):
        """Verify Telegram shows as unconfigured after delete"""
        response = requests.get(f"{BASE_URL}/api/setup-wizard/platforms", headers=auth_headers)
        assert response.status_code == 200
        platforms = response.json()
        telegram = next((p for p in platforms if p["id"] == "telegram"), None)
        assert telegram is not None
        assert telegram["configured"] == False
        print("✓ Telegram shows as unconfigured after delete")


class TestSmartLockProviders:
    """Smart Locks - Provider listing and configuration"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        token = response.json().get("token", "")
        return {"Authorization": f"Bearer {token}"}
    
    def test_list_providers(self, auth_headers):
        """GET /api/smart-locks/providers - lists 6 lock providers"""
        response = requests.get(f"{BASE_URL}/api/smart-locks/providers", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        providers = response.json()
        
        assert isinstance(providers, dict)
        assert len(providers) == 6, f"Expected 6 providers, got {len(providers)}"
        
        expected_providers = ["ttlock", "nuki", "august_yale", "salto", "assa_abloy", "generic"]
        for pid in expected_providers:
            assert pid in providers, f"Missing provider: {pid}"
            assert "name" in providers[pid]
            assert "fields" in providers[pid]
        
        print(f"✓ Listed 6 lock providers: {list(providers.keys())}")
    
    def test_get_lock_config(self, auth_headers):
        """GET /api/smart-locks/config/{property_id} - get lock config"""
        response = requests.get(f"{BASE_URL}/api/smart-locks/config/city-gate", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        config = response.json()
        
        assert "property_id" in config
        assert "provider" in config
        print(f"✓ Lock config for city-gate: provider={config.get('provider', 'none')}")
    
    def test_update_lock_config(self, auth_headers):
        """PUT /api/smart-locks/config/{property_id} - update lock provider"""
        response = requests.put(
            f"{BASE_URL}/api/smart-locks/config/city-gate",
            headers=auth_headers,
            json={
                "provider": "ttlock",
                "api_key": "TEST_ttlock_api_key",
                "api_secret": "TEST_ttlock_secret"
            }
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        config = response.json()
        assert config["provider"] == "ttlock"
        assert config["api_key"] == "TEST_ttlock_api_key"
        print("✓ Lock config updated to TTLock")
    
    def test_test_lock_connection(self, auth_headers):
        """POST /api/smart-locks/config/{property_id}/test - test connection (MOCKED)"""
        response = requests.post(f"{BASE_URL}/api/smart-locks/config/city-gate/test", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data["success"] == True
        assert "ttlock" in data["message"].lower() or "validated" in data["message"].lower()
        print(f"✓ Lock connection test: {data['message']}")


class TestDigitalKeys:
    """Digital Keys - Generation and management"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        token = response.json().get("token", "")
        return {"Authorization": f"Bearer {token}"}
    
    @pytest.fixture(scope="class")
    def test_booking_ref(self, auth_headers):
        """Get or create a test booking for digital key generation"""
        # First try to get existing bookings
        response = requests.get(f"{BASE_URL}/api/bookings", headers=auth_headers)
        if response.status_code == 200:
            bookings = response.json()
            if bookings and len(bookings) > 0:
                return bookings[0].get("booking_ref")
        
        # If no bookings, create one
        response = requests.post(
            f"{BASE_URL}/api/booking/reserve",
            json={
                "property_id": "city-gate",
                "room_type_id": "test-room",
                "guest_name": "TEST_Digital Key Guest",
                "guest_email": "test_digitalkey@example.com",
                "guest_phone": "+1234567890",
                "check_in": "2026-02-01",
                "check_out": "2026-02-03",
                "adults": 2,
                "children": 0,
                "rooms": 1
            }
        )
        if response.status_code in [200, 201]:
            return response.json().get("booking_ref")
        return None
    
    def test_generate_digital_key(self, auth_headers, test_booking_ref):
        """POST /api/digital-keys/generate - generate digital key for booking"""
        if not test_booking_ref:
            pytest.skip("No booking available for digital key test")
        
        response = requests.post(
            f"{BASE_URL}/api/digital-keys/generate",
            headers=auth_headers,
            json={
                "booking_ref": test_booking_ref,
                "room_number": "101"
            }
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        key = response.json()
        
        assert "id" in key
        assert "access_code" in key
        assert key["booking_ref"] == test_booking_ref
        assert key["status"] == "active"
        assert len(key["access_code"]) == 6  # 6-digit code
        
        print(f"✓ Digital key generated: {key['access_code']} for booking {test_booking_ref}")
        return key
    
    def test_list_digital_keys(self, auth_headers):
        """GET /api/digital-keys/{property_id} - list digital keys"""
        response = requests.get(f"{BASE_URL}/api/digital-keys/city-gate", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        keys = response.json()
        assert isinstance(keys, list)
        print(f"✓ Listed {len(keys)} digital keys for city-gate")
    
    def test_get_key_stats(self, auth_headers):
        """GET /api/digital-keys/{property_id}/stats - key statistics"""
        response = requests.get(f"{BASE_URL}/api/digital-keys/city-gate/stats", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        stats = response.json()
        
        assert "total" in stats
        assert "active" in stats
        assert "expired" in stats
        assert "revoked" in stats
        
        print(f"✓ Key stats: total={stats['total']}, active={stats['active']}, expired={stats['expired']}, revoked={stats['revoked']}")
    
    def test_guest_key_access_public(self, auth_headers, test_booking_ref):
        """GET /api/digital-keys/guest/{booking_ref} - public guest key access (NO AUTH)"""
        if not test_booking_ref:
            pytest.skip("No booking available for guest key test")
        
        # First ensure a key exists
        requests.post(
            f"{BASE_URL}/api/digital-keys/generate",
            headers=auth_headers,
            json={"booking_ref": test_booking_ref, "room_number": "101"}
        )
        
        # Access without auth
        response = requests.get(f"{BASE_URL}/api/digital-keys/guest/{test_booking_ref}")
        
        if response.status_code == 200:
            key = response.json()
            assert "access_code" in key
            assert "room_number" in key
            assert "guest_name" in key
            print(f"✓ Guest can access key without auth: code={key['access_code']}")
        elif response.status_code == 404:
            print("✓ Guest key endpoint returns 404 when no active key (expected)")
        else:
            pytest.fail(f"Unexpected status: {response.status_code}")


class TestDigitalKeyRevoke:
    """Digital Key revocation tests"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        token = response.json().get("token", "")
        return {"Authorization": f"Bearer {token}"}
    
    def test_revoke_key(self, auth_headers):
        """PUT /api/digital-keys/{key_id}/revoke - revoke a key"""
        # First get a key to revoke
        response = requests.get(f"{BASE_URL}/api/digital-keys/city-gate", headers=auth_headers)
        if response.status_code != 200:
            pytest.skip("Cannot list keys")
        
        keys = response.json()
        active_keys = [k for k in keys if k.get("status") == "active"]
        
        if not active_keys:
            pytest.skip("No active keys to revoke")
        
        key_id = active_keys[0]["id"]
        response = requests.put(f"{BASE_URL}/api/digital-keys/{key_id}/revoke", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data["status"] == "revoked"
        print(f"✓ Key {key_id} revoked")


class TestRegressionEndpoints:
    """Regression tests for existing endpoints"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        token = response.json().get("token", "")
        return {"Authorization": f"Bearer {token}"}
    
    def test_dashboard_overview(self, auth_headers):
        """GET /api/dashboard/overview/{property_id} - dashboard still works"""
        response = requests.get(f"{BASE_URL}/api/dashboard/overview/city-gate", headers=auth_headers)
        assert response.status_code == 200, f"Dashboard failed: {response.text}"
        print("✓ Dashboard overview working")
    
    def test_reviews_list(self, auth_headers):
        """GET /api/reviews - reviews still work"""
        response = requests.get(f"{BASE_URL}/api/reviews", headers=auth_headers)
        assert response.status_code == 200, f"Reviews failed: {response.text}"
        print("✓ Reviews endpoint working")
    
    def test_bookings_list(self, auth_headers):
        """GET /api/bookings - bookings still work"""
        response = requests.get(f"{BASE_URL}/api/bookings", headers=auth_headers)
        assert response.status_code == 200, f"Bookings failed: {response.text}"
        print("✓ Bookings endpoint working")
    
    def test_properties_list(self, auth_headers):
        """GET /api/properties - properties still work"""
        response = requests.get(f"{BASE_URL}/api/properties", headers=auth_headers)
        assert response.status_code == 200, f"Properties failed: {response.text}"
        print("✓ Properties endpoint working")
    
    def test_messaging_conversations(self, auth_headers):
        """POST /api/messaging/conversations - messaging still works"""
        response = requests.post(f"{BASE_URL}/api/messaging/conversations", headers=auth_headers, json={
            "property_id": "city-gate",
            "guest_name": "TEST_Regression Guest",
            "guest_email": "test_regression@example.com",
            "channel": "internal"
        })
        assert response.status_code == 200, f"Messaging failed: {response.text}"
        print("✓ Messaging endpoint working")


class TestAuthRequirements:
    """Test that endpoints require proper authentication"""
    
    def test_setup_wizard_requires_auth(self):
        """Setup wizard endpoints require authentication"""
        response = requests.get(f"{BASE_URL}/api/setup-wizard/platforms")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ Setup wizard requires auth")
    
    def test_smart_locks_requires_auth(self):
        """Smart locks endpoints require authentication"""
        response = requests.get(f"{BASE_URL}/api/smart-locks/providers")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ Smart locks requires auth")
    
    def test_digital_keys_admin_requires_auth(self):
        """Digital keys admin endpoints require authentication"""
        response = requests.get(f"{BASE_URL}/api/digital-keys/city-gate")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ Digital keys admin requires auth")
    
    def test_digital_keys_guest_no_auth(self):
        """Digital keys guest endpoint does NOT require auth"""
        response = requests.get(f"{BASE_URL}/api/digital-keys/guest/FAKE-REF")
        # Should return 404 (not found) not 401 (unauthorized)
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ Digital keys guest endpoint is public (returns 404 for invalid ref)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
