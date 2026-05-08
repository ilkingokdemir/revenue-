"""
Iteration 37 - Channel Settings & Regression Tests
Tests for:
1. Channel Settings API (GET/PUT /api/messaging/channel-settings/{property_id})
2. Automation Engine regression (6 rules still working)
3. Messaging Hub regression (conversations, guest directory, calendar, FAQ bot)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestAuth:
    """Authentication tests"""
    
    @pytest.fixture(scope="class")
    def session(self):
        return requests.Session()
    
    def test_login_success(self, session):
        """Test admin login"""
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "token" in data
        assert data["email"] == "admin@hotelbox.com"
        assert data["role"] == "admin"
        print(f"✓ Login successful: {data['email']} ({data['role']})")
        return data["token"]


class TestChannelSettingsAPI:
    """Channel Settings API tests"""
    
    @pytest.fixture(scope="class")
    def auth_session(self):
        session = requests.Session()
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        return session
    
    def test_get_channel_settings_default(self, auth_session):
        """GET /api/messaging/channel-settings/{property_id} - returns default settings"""
        response = auth_session.get(f"{BASE_URL}/api/messaging/channel-settings/aldgate-flats")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Verify default structure
        assert data["property_id"] == "aldgate-flats"
        assert "whatsapp_enabled" in data
        assert "telegram_enabled" in data
        assert "sms_enabled" in data
        assert "email_enabled" in data
        assert "auto_reply_enabled" in data
        
        # Email should be enabled by default
        assert data["email_enabled"] == True
        
        # WhatsApp fields
        assert "whatsapp_phone_number_id" in data
        assert "whatsapp_access_token" in data
        assert "whatsapp_business_id" in data
        
        # Telegram fields
        assert "telegram_bot_token" in data
        assert "telegram_bot_username" in data
        
        # SMS fields
        assert "sms_provider" in data
        assert "sms_api_key" in data
        assert "sms_sender_number" in data
        
        # Auto-reply fields
        assert "welcome_message" in data
        assert "auto_reply_message" in data
        
        print(f"✓ Channel settings retrieved: email_enabled={data['email_enabled']}, whatsapp_enabled={data['whatsapp_enabled']}")
    
    def test_update_channel_settings_whatsapp(self, auth_session):
        """PUT /api/messaging/channel-settings/{property_id} - update WhatsApp settings"""
        update_data = {
            "whatsapp_enabled": True,
            "whatsapp_phone_number_id": "123456789012345",
            "whatsapp_access_token": "EAAtest123token",
            "whatsapp_business_id": "987654321012345"
        }
        response = auth_session.put(f"{BASE_URL}/api/messaging/channel-settings/aldgate-flats", json=update_data)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert data["whatsapp_enabled"] == True
        assert data["whatsapp_phone_number_id"] == "123456789012345"
        assert data["whatsapp_access_token"] == "EAAtest123token"
        assert data["whatsapp_business_id"] == "987654321012345"
        print("✓ WhatsApp settings updated successfully")
    
    def test_update_channel_settings_telegram(self, auth_session):
        """PUT /api/messaging/channel-settings/{property_id} - update Telegram settings"""
        update_data = {
            "telegram_enabled": True,
            "telegram_bot_token": "123456:ABC-DEF1234ghIkl-zyx57W2v",
            "telegram_bot_username": "@MyHotelBot"
        }
        response = auth_session.put(f"{BASE_URL}/api/messaging/channel-settings/aldgate-flats", json=update_data)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert data["telegram_enabled"] == True
        assert data["telegram_bot_token"] == "123456:ABC-DEF1234ghIkl-zyx57W2v"
        assert data["telegram_bot_username"] == "@MyHotelBot"
        print("✓ Telegram settings updated successfully")
    
    def test_update_channel_settings_sms(self, auth_session):
        """PUT /api/messaging/channel-settings/{property_id} - update SMS settings"""
        update_data = {
            "sms_enabled": True,
            "sms_provider": "twilio",
            "sms_api_key": "test_api_key_123",
            "sms_sender_number": "+447123456789"
        }
        response = auth_session.put(f"{BASE_URL}/api/messaging/channel-settings/aldgate-flats", json=update_data)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert data["sms_enabled"] == True
        assert data["sms_provider"] == "twilio"
        assert data["sms_api_key"] == "test_api_key_123"
        assert data["sms_sender_number"] == "+447123456789"
        print("✓ SMS settings updated successfully")
    
    def test_update_channel_settings_auto_reply(self, auth_session):
        """PUT /api/messaging/channel-settings/{property_id} - update auto-reply settings"""
        update_data = {
            "auto_reply_enabled": True,
            "welcome_message": "Welcome to Aldgate Flats! How can we help?",
            "auto_reply_message": "Thanks for your message. Our team will respond within 30 minutes."
        }
        response = auth_session.put(f"{BASE_URL}/api/messaging/channel-settings/aldgate-flats", json=update_data)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert data["auto_reply_enabled"] == True
        assert data["welcome_message"] == "Welcome to Aldgate Flats! How can we help?"
        assert data["auto_reply_message"] == "Thanks for your message. Our team will respond within 30 minutes."
        print("✓ Auto-reply settings updated successfully")
    
    def test_get_channel_settings_persisted(self, auth_session):
        """GET /api/messaging/channel-settings/{property_id} - verify persistence"""
        response = auth_session.get(f"{BASE_URL}/api/messaging/channel-settings/aldgate-flats")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Verify all updates persisted
        assert data["whatsapp_enabled"] == True
        assert data["telegram_enabled"] == True
        assert data["sms_enabled"] == True
        assert data["auto_reply_enabled"] == True
        print("✓ All channel settings persisted correctly")
    
    def test_disable_channels(self, auth_session):
        """PUT /api/messaging/channel-settings/{property_id} - disable channels"""
        update_data = {
            "whatsapp_enabled": False,
            "telegram_enabled": False,
            "sms_enabled": False,
            "auto_reply_enabled": False
        }
        response = auth_session.put(f"{BASE_URL}/api/messaging/channel-settings/aldgate-flats", json=update_data)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert data["whatsapp_enabled"] == False
        assert data["telegram_enabled"] == False
        assert data["sms_enabled"] == False
        assert data["auto_reply_enabled"] == False
        print("✓ Channels disabled successfully")


class TestMessagingSendEndpoints:
    """Test messaging send endpoints (sandbox mode)"""
    
    @pytest.fixture(scope="class")
    def auth_session(self):
        session = requests.Session()
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert response.status_code == 200
        return session
    
    def test_send_whatsapp_sandbox(self, auth_session):
        """POST /api/messaging/send/whatsapp - sandbox mode response"""
        response = auth_session.post(f"{BASE_URL}/api/messaging/send/whatsapp", json={
            "property_id": "aldgate-flats",
            "phone": "+0000000000",
            "message": "Test message from MyHotelBox"
        })
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        # In sandbox mode, should return a message about sandbox
        assert "sent" in data or "message" in data
        print(f"✓ WhatsApp send endpoint works (sandbox): {data}")
    
    def test_send_telegram_sandbox(self, auth_session):
        """POST /api/messaging/send/telegram - sandbox mode response"""
        response = auth_session.post(f"{BASE_URL}/api/messaging/send/telegram", json={
            "property_id": "aldgate-flats",
            "chat_id": "test",
            "message": "Test message from MyHotelBox"
        })
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "sent" in data or "message" in data
        print(f"✓ Telegram send endpoint works (sandbox): {data}")
    
    def test_send_email_sandbox(self, auth_session):
        """POST /api/messaging/send/email - sandbox mode response"""
        response = auth_session.post(f"{BASE_URL}/api/messaging/send/email", json={
            "email": "test@example.com",
            "subject": "MyHotelBox Test",
            "message": "This is a test email from MyHotelBox."
        })
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "sent" in data or "message" in data
        print(f"✓ Email send endpoint works (sandbox): {data}")


class TestAutomationRegression:
    """Automation Engine regression tests"""
    
    @pytest.fixture(scope="class")
    def auth_session(self):
        session = requests.Session()
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert response.status_code == 200
        return session
    
    def test_get_automation_rules(self, auth_session):
        """GET /api/automation/rules/{property_id} - returns 6 default rules"""
        response = auth_session.get(f"{BASE_URL}/api/automation/rules/aldgate-flats")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert isinstance(data, list)
        assert len(data) >= 6, f"Expected at least 6 rules, got {len(data)}"
        
        # Verify rule structure
        for rule in data:
            assert "id" in rule
            assert "name" in rule
            assert "trigger" in rule
            assert "channel" in rule
            assert "enabled" in rule
        
        print(f"✓ Automation rules retrieved: {len(data)} rules")
    
    def test_automation_stats(self, auth_session):
        """GET /api/automation/stats/{property_id} - returns stats"""
        response = auth_session.get(f"{BASE_URL}/api/automation/stats/aldgate-flats")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert "total_rules" in data
        assert "active_rules" in data
        assert "total_sent" in data
        assert "by_channel" in data
        
        print(f"✓ Automation stats: {data['active_rules']} active rules")


class TestMessagingHubRegression:
    """Messaging Hub regression tests"""
    
    @pytest.fixture(scope="class")
    def auth_session(self):
        session = requests.Session()
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert response.status_code == 200
        return session
    
    def test_get_conversations(self, auth_session):
        """GET /api/messaging/conversations/{property_id} - returns conversations"""
        response = auth_session.get(f"{BASE_URL}/api/messaging/conversations/aldgate-flats")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Conversations retrieved: {len(data)} conversations")
    
    def test_get_guest_directory(self, auth_session):
        """GET /api/messaging/guests/{property_id} - returns guest directory"""
        response = auth_session.get(f"{BASE_URL}/api/messaging/guests/aldgate-flats")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Guest directory retrieved: {len(data)} guests")
    
    def test_get_faq_rules(self, auth_session):
        """GET /api/messaging/auto-replies/{property_id} - returns FAQ bot rules"""
        response = auth_session.get(f"{BASE_URL}/api/messaging/auto-replies/aldgate-flats")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 10, f"Expected at least 10 FAQ rules, got {len(data)}"
        print(f"✓ FAQ rules retrieved: {len(data)} rules")
    
    def test_get_quick_replies(self, auth_session):
        """GET /api/messaging/quick-replies - returns quick reply templates"""
        response = auth_session.get(f"{BASE_URL}/api/messaging/quick-replies")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Quick replies retrieved: {len(data)} templates")


class TestUnifiedInboxRegression:
    """Unified Inbox regression tests"""
    
    @pytest.fixture(scope="class")
    def auth_session(self):
        session = requests.Session()
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert response.status_code == 200
        return session
    
    def test_get_inbox_stats(self, auth_session):
        """GET /api/messaging/conversations/{property_id}/stats - returns inbox stats"""
        response = auth_session.get(f"{BASE_URL}/api/messaging/conversations/aldgate-flats/stats")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Verify stats structure
        assert "total" in data or "by_channel" in data
        assert "by_channel" in data
        
        print(f"✓ Inbox stats retrieved: {data}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
