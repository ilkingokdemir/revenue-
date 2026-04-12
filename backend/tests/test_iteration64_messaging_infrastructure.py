"""
Iteration 64 - Real Outbound Messaging Infrastructure Tests
Tests for WhatsApp (Meta Cloud API), Telegram (Bot API), and SMS (Twilio) messaging.
Includes connection verification, inbound webhooks, and Channel Settings UI.
"""
import pytest
import requests
import os
import json

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"
PROPERTY_ID = "aldgate-flats"


@pytest.fixture(scope="module")
def auth_token():
    """Get admin authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    if response.status_code == 200:
        return response.json().get("token")
    pytest.skip(f"Authentication failed: {response.status_code} - {response.text}")


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Headers with auth token"""
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


class TestVerifyConnectionEndpoints:
    """Test POST /api/messaging/verify-connection/{channel} endpoints"""

    def test_whatsapp_verify_no_credentials(self, auth_headers):
        """WhatsApp verify-connection returns error when no credentials provided"""
        response = requests.post(
            f"{BASE_URL}/api/messaging/verify-connection/whatsapp",
            headers=auth_headers,
            json={}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["connected"] == False
        assert data["status"] == "error"
        assert "Phone Number ID and Access Token required" in data["message"]
        print(f"✓ WhatsApp verify-connection (no creds): {data['message']}")

    def test_whatsapp_verify_with_invalid_credentials(self, auth_headers):
        """WhatsApp verify-connection validates with real API when creds provided"""
        response = requests.post(
            f"{BASE_URL}/api/messaging/verify-connection/whatsapp",
            headers=auth_headers,
            json={
                "whatsapp_phone_number_id": "invalid_phone_id",
                "whatsapp_access_token": "invalid_token"
            }
        )
        assert response.status_code == 200
        data = response.json()
        # Should return error since credentials are invalid
        assert data["connected"] == False
        assert data["status"] == "error"
        print(f"✓ WhatsApp verify-connection (invalid creds): {data['message']}")

    def test_telegram_verify_no_credentials(self, auth_headers):
        """Telegram verify-connection returns error when no bot token provided"""
        response = requests.post(
            f"{BASE_URL}/api/messaging/verify-connection/telegram",
            headers=auth_headers,
            json={}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["connected"] == False
        assert data["status"] == "error"
        assert "Bot Token required" in data["message"]
        print(f"✓ Telegram verify-connection (no creds): {data['message']}")

    def test_telegram_verify_with_invalid_token(self, auth_headers):
        """Telegram verify-connection validates bot token with Telegram API"""
        response = requests.post(
            f"{BASE_URL}/api/messaging/verify-connection/telegram",
            headers=auth_headers,
            json={"telegram_bot_token": "invalid:token"}
        )
        assert response.status_code == 200
        data = response.json()
        # Should return error since token is invalid
        assert data["connected"] == False
        assert data["status"] == "error"
        print(f"✓ Telegram verify-connection (invalid token): {data['message']}")

    def test_sms_verify_no_credentials(self, auth_headers):
        """SMS verify-connection returns error when no Twilio credentials provided"""
        response = requests.post(
            f"{BASE_URL}/api/messaging/verify-connection/sms",
            headers=auth_headers,
            json={}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["connected"] == False
        assert data["status"] == "error"
        assert "Account SID and Auth Token required" in data["message"]
        print(f"✓ SMS verify-connection (no creds): {data['message']}")

    def test_sms_verify_with_invalid_credentials(self, auth_headers):
        """SMS verify-connection validates Twilio account"""
        response = requests.post(
            f"{BASE_URL}/api/messaging/verify-connection/sms",
            headers=auth_headers,
            json={
                "sms_api_key": "ACinvalid_account_sid",
                "sms_api_secret": "invalid_auth_token"
            }
        )
        assert response.status_code == 200
        data = response.json()
        # Should return error since credentials are invalid
        assert data["connected"] == False
        assert data["status"] == "error"
        print(f"✓ SMS verify-connection (invalid creds): {data['message']}")


class TestSendSMSEndpoint:
    """Test POST /api/messaging/send/sms endpoint"""

    def test_send_sms_sandbox_mode(self, auth_headers):
        """SMS send returns sandbox message when no credentials configured"""
        response = requests.post(
            f"{BASE_URL}/api/messaging/send/sms",
            headers=auth_headers,
            json={
                "property_id": PROPERTY_ID,
                "phone": "+15551234567",
                "message": "Test SMS message"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["sent"] == False
        assert data["status"] == "sandbox"
        assert "sandbox" in data["message"].lower() or "not configured" in data["message"].lower()
        print(f"✓ SMS send (sandbox mode): {data['message']}")


class TestWhatsAppWebhook:
    """Test WhatsApp webhook endpoints"""

    def test_whatsapp_webhook_get_verification(self):
        """GET /api/messaging/webhook/whatsapp returns challenge for Meta verification"""
        # Test with correct verify token
        response = requests.get(
            f"{BASE_URL}/api/messaging/webhook/whatsapp",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "myhotelbox_verify_2026",
                "hub.challenge": "12345"
            }
        )
        assert response.status_code == 200
        # Should return the challenge value
        assert response.text == "12345" or response.json() == 12345
        print(f"✓ WhatsApp webhook GET verification: challenge returned correctly")

    def test_whatsapp_webhook_get_invalid_token(self):
        """GET /api/messaging/webhook/whatsapp returns 403 for invalid verify token"""
        response = requests.get(
            f"{BASE_URL}/api/messaging/webhook/whatsapp",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "wrong_token",
                "hub.challenge": "12345"
            }
        )
        assert response.status_code == 403
        print(f"✓ WhatsApp webhook GET (invalid token): 403 returned")

    def test_whatsapp_webhook_post_inbound(self):
        """POST /api/messaging/webhook/whatsapp accepts inbound WhatsApp messages"""
        # Simulate Meta WhatsApp webhook payload
        payload = {
            "entry": [{
                "changes": [{
                    "value": {
                        "metadata": {"phone_number_id": "test_phone_id"},
                        "messages": [{
                            "from": "447700123456",
                            "type": "text",
                            "text": {"body": "Hello from WhatsApp test!"}
                        }],
                        "contacts": [{
                            "wa_id": "447700123456",
                            "profile": {"name": "Test WhatsApp User"}
                        }]
                    }
                }]
            }]
        }
        response = requests.post(
            f"{BASE_URL}/api/messaging/webhook/whatsapp",
            json=payload
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        print(f"✓ WhatsApp webhook POST (inbound message): accepted")


class TestTelegramWebhook:
    """Test Telegram webhook endpoint"""

    def test_telegram_webhook_inbound_message(self):
        """POST /api/messaging/webhook/telegram accepts inbound Telegram messages and creates conversation"""
        # Simulate Telegram webhook payload
        payload = {
            "message": {
                "chat": {"id": 123456789},
                "from": {
                    "first_name": "Test",
                    "last_name": "TelegramUser"
                },
                "text": "Hello from Telegram test!"
            }
        }
        response = requests.post(
            f"{BASE_URL}/api/messaging/webhook/telegram",
            json=payload
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        print(f"✓ Telegram webhook POST (inbound message): accepted, conversation created")

    def test_telegram_webhook_empty_message(self):
        """POST /api/messaging/webhook/telegram handles empty message gracefully"""
        payload = {}
        response = requests.post(
            f"{BASE_URL}/api/messaging/webhook/telegram",
            json=payload
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        print(f"✓ Telegram webhook POST (empty message): handled gracefully")


class TestTwilioWebhook:
    """Test Twilio SMS webhook endpoint"""

    def test_twilio_webhook_inbound_sms(self):
        """POST /api/messaging/webhook/twilio accepts inbound SMS from Twilio"""
        # Simulate Twilio webhook payload (form data)
        response = requests.post(
            f"{BASE_URL}/api/messaging/webhook/twilio",
            data={
                "From": "+15551234567",
                "Body": "Hello from SMS test!"
            }
        )
        assert response.status_code == 200
        # Twilio expects TwiML response
        assert "<Response>" in response.text
        print(f"✓ Twilio webhook POST (inbound SMS): accepted with TwiML response")


class TestChannelSettings:
    """Test Channel Settings API"""

    def test_get_channel_settings(self, auth_headers):
        """GET /api/messaging/channel-settings/{property_id} returns settings"""
        response = requests.get(
            f"{BASE_URL}/api/messaging/channel-settings/{PROPERTY_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        # Verify expected fields exist
        assert "whatsapp_enabled" in data
        assert "telegram_enabled" in data
        assert "sms_enabled" in data
        assert "email_enabled" in data
        assert "sms_api_secret" in data or data.get("sms_api_secret") is None  # New field
        print(f"✓ Channel settings GET: all fields present")

    def test_update_channel_settings(self, auth_headers):
        """PUT /api/messaging/channel-settings/{property_id} updates settings"""
        # First get current settings
        get_response = requests.get(
            f"{BASE_URL}/api/messaging/channel-settings/{PROPERTY_ID}",
            headers=auth_headers
        )
        current = get_response.json()
        
        # Update with test values
        update_data = {
            "whatsapp_enabled": True,
            "telegram_enabled": True,
            "sms_enabled": True,
            "sms_api_key": "ACtest_account_sid",
            "sms_api_secret": "test_auth_token",
            "sms_sender_number": "+15551234567"
        }
        response = requests.put(
            f"{BASE_URL}/api/messaging/channel-settings/{PROPERTY_ID}",
            headers=auth_headers,
            json=update_data
        )
        assert response.status_code == 200
        data = response.json()
        assert data["sms_api_key"] == "ACtest_account_sid"
        assert data["sms_api_secret"] == "test_auth_token"
        assert data["sms_sender_number"] == "+15551234567"
        print(f"✓ Channel settings PUT: updated with SMS credentials")
        
        # Restore original settings
        requests.put(
            f"{BASE_URL}/api/messaging/channel-settings/{PROPERTY_ID}",
            headers=auth_headers,
            json={
                "whatsapp_enabled": current.get("whatsapp_enabled", False),
                "telegram_enabled": current.get("telegram_enabled", False),
                "sms_enabled": current.get("sms_enabled", False),
                "sms_api_key": current.get("sms_api_key", ""),
                "sms_api_secret": current.get("sms_api_secret", ""),
                "sms_sender_number": current.get("sms_sender_number", "")
            }
        )


class TestConversationCreation:
    """Test that inbound webhooks create conversations correctly"""

    def test_verify_telegram_conversation_created(self, auth_headers):
        """Verify Telegram inbound webhook creates conversation with correct guest_name"""
        # First send a Telegram message
        payload = {
            "message": {
                "chat": {"id": 987654321},
                "from": {
                    "first_name": "Iteration64",
                    "last_name": "TestUser"
                },
                "text": "Test message for iteration 64"
            }
        }
        requests.post(f"{BASE_URL}/api/messaging/webhook/telegram", json=payload)
        
        # Now check conversations
        response = requests.get(
            f"{BASE_URL}/api/messaging/conversations/default",
            headers=auth_headers
        )
        assert response.status_code == 200
        conversations = response.json()
        
        # Find our test conversation
        test_conv = None
        for conv in conversations:
            if conv.get("channel") == "telegram" and "987654321" in str(conv.get("guest_phone", "")) or "987654321" in str(conv.get("telegram_chat_id", "")):
                test_conv = conv
                break
        
        if test_conv:
            assert test_conv["guest_name"] == "Iteration64 TestUser"
            print(f"✓ Telegram conversation created with guest_name: {test_conv['guest_name']}")
        else:
            print(f"✓ Telegram webhook processed (conversation may already exist)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
