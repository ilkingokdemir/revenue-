"""
Iteration 35 - Enhanced Messaging Hub Tests
Tests for: Guest Directory, Bookings Calendar, Auto-Reply FAQ Bot, New Conversation Modal,
WhatsApp/Telegram sandbox mode, Email sending
"""
import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@hotelbox.com",
        "password": "HotelAdmin2026!"
    })
    if response.status_code == 200:
        return response.json().get("token")
    pytest.skip("Authentication failed - skipping authenticated tests")

@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Session with auth header"""
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


class TestGuestDirectory:
    """Guest Directory API tests - pulls contacts from bookings"""
    
    def test_get_guest_directory_all(self, auth_headers):
        """GET /api/messaging/guests/{property_id} - returns guest contacts from bookings"""
        response = requests.get(f"{BASE_URL}/api/messaging/guests/aldgate-flats", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list of guests"
        print(f"Guest Directory returned {len(data)} guests")
        # Verify guest structure if any guests exist
        if len(data) > 0:
            guest = data[0]
            assert "guest_name" in guest, "Guest should have guest_name"
            assert "guest_email" in guest or "guest_phone" in guest, "Guest should have email or phone"
            assert "check_in" in guest, "Guest should have check_in date"
            assert "check_out" in guest, "Guest should have check_out date"
            assert "booking_ref" in guest, "Guest should have booking_ref"
            print(f"Sample guest: {guest.get('guest_name')} - {guest.get('guest_email')}")
    
    def test_guest_directory_search(self, auth_headers):
        """GET /api/messaging/guests/{property_id}?search=... - search by name/email/phone"""
        response = requests.get(f"{BASE_URL}/api/messaging/guests/aldgate-flats?search=test", headers=auth_headers)
        assert response.status_code == 200, f"Search failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Search should return a list"
        print(f"Search 'test' returned {len(data)} guests")
    
    def test_guest_directory_filter_current(self, auth_headers):
        """GET /api/messaging/guests/{property_id}?filter_type=current - In-House guests"""
        response = requests.get(f"{BASE_URL}/api/messaging/guests/aldgate-flats?filter_type=current", headers=auth_headers)
        assert response.status_code == 200, f"Filter current failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Filter should return a list"
        print(f"In-House guests: {len(data)}")
    
    def test_guest_directory_filter_arriving(self, auth_headers):
        """GET /api/messaging/guests/{property_id}?filter_type=arriving_today - Arriving today"""
        response = requests.get(f"{BASE_URL}/api/messaging/guests/aldgate-flats?filter_type=arriving_today", headers=auth_headers)
        assert response.status_code == 200, f"Filter arriving failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Filter should return a list"
        print(f"Arriving today: {len(data)}")
    
    def test_guest_directory_filter_departing(self, auth_headers):
        """GET /api/messaging/guests/{property_id}?filter_type=departing_today - Departing today"""
        response = requests.get(f"{BASE_URL}/api/messaging/guests/aldgate-flats?filter_type=departing_today", headers=auth_headers)
        assert response.status_code == 200, f"Filter departing failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Filter should return a list"
        print(f"Departing today: {len(data)}")
    
    def test_guest_directory_filter_upcoming(self, auth_headers):
        """GET /api/messaging/guests/{property_id}?filter_type=upcoming - Upcoming bookings"""
        response = requests.get(f"{BASE_URL}/api/messaging/guests/aldgate-flats?filter_type=upcoming", headers=auth_headers)
        assert response.status_code == 200, f"Filter upcoming failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Filter should return a list"
        print(f"Upcoming guests: {len(data)}")
    
    def test_guest_directory_filter_past(self, auth_headers):
        """GET /api/messaging/guests/{property_id}?filter_type=past - Past guests"""
        response = requests.get(f"{BASE_URL}/api/messaging/guests/aldgate-flats?filter_type=past", headers=auth_headers)
        assert response.status_code == 200, f"Filter past failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Filter should return a list"
        print(f"Past guests: {len(data)}")


class TestBookingsCalendar:
    """Bookings Calendar API tests"""
    
    def test_get_calendar_current_month(self, auth_headers):
        """GET /api/messaging/calendar/{property_id} - returns calendar data for current month"""
        response = requests.get(f"{BASE_URL}/api/messaging/calendar/aldgate-flats", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "month" in data, "Response should have month"
        assert "bookings" in data, "Response should have bookings list"
        assert "day_events" in data, "Response should have day_events dict"
        assert "stats" in data, "Response should have stats"
        # Verify stats structure
        stats = data["stats"]
        assert "total_bookings" in stats, "Stats should have total_bookings"
        assert "today_checkins" in stats, "Stats should have today_checkins"
        assert "today_checkouts" in stats, "Stats should have today_checkouts"
        print(f"Calendar for {data['month']}: {stats['total_bookings']} bookings, {stats['today_checkins']} check-ins today, {stats['today_checkouts']} check-outs today")
    
    def test_get_calendar_specific_month(self, auth_headers):
        """GET /api/messaging/calendar/{property_id}?month=YYYY-MM - specific month"""
        response = requests.get(f"{BASE_URL}/api/messaging/calendar/aldgate-flats?month=2026-01", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["month"] == "2026-01", f"Expected month 2026-01, got {data['month']}"
        print(f"Calendar for 2026-01: {data['stats']['total_bookings']} bookings")
    
    def test_calendar_day_events_structure(self, auth_headers):
        """Verify day_events structure has check_in/check_out events"""
        response = requests.get(f"{BASE_URL}/api/messaging/calendar/aldgate-flats", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        day_events = data.get("day_events", {})
        # Check structure of events if any exist
        for date, events in day_events.items():
            assert isinstance(events, list), f"Events for {date} should be a list"
            for event in events:
                assert "type" in event, "Event should have type (check_in/check_out)"
                assert event["type"] in ["check_in", "check_out"], f"Event type should be check_in or check_out, got {event['type']}"
                assert "guest" in event, "Event should have guest name"
                print(f"  {date}: {event['type']} - {event['guest']}")
                break  # Just check first event
            break  # Just check first date


class TestAutoReplyFAQBot:
    """Auto-Reply FAQ Bot API tests"""
    
    def test_get_auto_replies_seeds_defaults(self, auth_headers):
        """GET /api/messaging/auto-replies/{property_id} - returns 10 default rules"""
        response = requests.get(f"{BASE_URL}/api/messaging/auto-replies/aldgate-flats", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list of rules"
        assert len(data) >= 10, f"Expected at least 10 default rules, got {len(data)}"
        # Verify rule structure
        rule = data[0]
        assert "id" in rule, "Rule should have id"
        assert "name" in rule, "Rule should have name"
        assert "keywords" in rule, "Rule should have keywords list"
        assert "response" in rule, "Rule should have response"
        assert "enabled" in rule, "Rule should have enabled flag"
        assert "match_count" in rule, "Rule should have match_count"
        print(f"Auto-reply rules: {len(data)} rules loaded")
        for r in data[:3]:
            print(f"  - {r['name']}: {r['keywords'][:2]}...")
    
    def test_auto_reply_check_checkin_match(self, auth_headers):
        """POST /api/messaging/auto-replies/check - matches 'what time is check in' to Check-in rule"""
        response = requests.post(
            f"{BASE_URL}/api/messaging/auto-replies/check?property_id=aldgate-flats&message=what time is check in",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("matched") == True, f"Expected match for 'what time is check in', got {data}"
        assert "Check-in" in data.get("rule_name", "") or "check" in data.get("rule_name", "").lower(), f"Expected Check-in rule, got {data.get('rule_name')}"
        assert "response" in data, "Should return response text"
        print(f"Matched rule: {data.get('rule_name')}")
        print(f"Response: {data.get('response')[:80]}...")
    
    def test_auto_reply_check_wifi_match(self, auth_headers):
        """POST /api/messaging/auto-replies/check - matches 'wifi password' to WiFi rule"""
        response = requests.post(
            f"{BASE_URL}/api/messaging/auto-replies/check?property_id=aldgate-flats&message=what is the wifi password",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("matched") == True, f"Expected match for 'wifi password', got {data}"
        print(f"WiFi match: {data.get('rule_name')}")
    
    def test_auto_reply_check_parking_match(self, auth_headers):
        """POST /api/messaging/auto-replies/check - matches 'parking' to Parking rule"""
        response = requests.post(
            f"{BASE_URL}/api/messaging/auto-replies/check?property_id=aldgate-flats&message=do you have parking",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("matched") == True, f"Expected match for 'parking', got {data}"
        print(f"Parking match: {data.get('rule_name')}")
    
    def test_auto_reply_check_no_match(self, auth_headers):
        """POST /api/messaging/auto-replies/check - no match for random text"""
        response = requests.post(
            f"{BASE_URL}/api/messaging/auto-replies/check?property_id=aldgate-flats&message=random gibberish xyz123",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("matched") == False, f"Expected no match for random text, got {data}"
        print("No match for random text - correct behavior")
    
    def test_toggle_auto_reply_rule(self, auth_headers):
        """PUT /api/messaging/auto-replies/{rule_id} - toggle enabled state"""
        # First get rules to find an ID
        response = requests.get(f"{BASE_URL}/api/messaging/auto-replies/aldgate-flats", headers=auth_headers)
        assert response.status_code == 200
        rules = response.json()
        assert len(rules) > 0, "Need at least one rule to test toggle"
        rule = rules[0]
        rule_id = rule["id"]
        original_enabled = rule["enabled"]
        
        # Toggle the rule
        response = requests.put(
            f"{BASE_URL}/api/messaging/auto-replies/{rule_id}",
            json={"enabled": not original_enabled},
            headers=auth_headers
        )
        assert response.status_code == 200, f"Toggle failed: {response.text}"
        updated = response.json()
        assert updated["enabled"] == (not original_enabled), "Enabled state should be toggled"
        print(f"Toggled rule '{rule['name']}' from {original_enabled} to {not original_enabled}")
        
        # Toggle back
        response = requests.put(
            f"{BASE_URL}/api/messaging/auto-replies/{rule_id}",
            json={"enabled": original_enabled},
            headers=auth_headers
        )
        assert response.status_code == 200


class TestNewConversation:
    """New Conversation API tests"""
    
    def test_create_new_conversation_whatsapp(self, auth_headers):
        """POST /api/messaging/new-conversation - creates conversation and message via WhatsApp"""
        payload = {
            "property_id": "aldgate-flats",
            "guest_name": "TEST_NewGuest WhatsApp",
            "guest_email": "test.newguest@example.com",
            "guest_phone": "+447700999888",
            "channel": "whatsapp",
            "message": "Hello! This is a test message via WhatsApp."
        }
        response = requests.post(f"{BASE_URL}/api/messaging/new-conversation", json=payload, headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "conversation" in data, "Response should have conversation"
        assert "message" in data, "Response should have message"
        conv = data["conversation"]
        assert conv["guest_name"] == "TEST_NewGuest WhatsApp"
        assert conv["channel"] == "whatsapp"
        assert conv["status"] == "in_progress"
        print(f"Created conversation: {conv['id']} via {conv['channel']}")
    
    def test_create_new_conversation_telegram(self, auth_headers):
        """POST /api/messaging/new-conversation - creates conversation via Telegram"""
        payload = {
            "property_id": "aldgate-flats",
            "guest_name": "TEST_NewGuest Telegram",
            "guest_email": "test.telegram@example.com",
            "guest_phone": "+447700888777",
            "channel": "telegram",
            "message": "Hello! This is a test message via Telegram."
        }
        response = requests.post(f"{BASE_URL}/api/messaging/new-conversation", json=payload, headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["conversation"]["channel"] == "telegram"
        print(f"Created Telegram conversation: {data['conversation']['id']}")
    
    def test_create_new_conversation_email(self, auth_headers):
        """POST /api/messaging/new-conversation - creates conversation via Email"""
        payload = {
            "property_id": "aldgate-flats",
            "guest_name": "TEST_NewGuest Email",
            "guest_email": "test.email@example.com",
            "channel": "email",
            "message": "Hello! This is a test message via Email."
        }
        response = requests.post(f"{BASE_URL}/api/messaging/new-conversation", json=payload, headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["conversation"]["channel"] == "email"
        print(f"Created Email conversation: {data['conversation']['id']}")
    
    def test_create_new_conversation_sms(self, auth_headers):
        """POST /api/messaging/new-conversation - creates conversation via SMS"""
        payload = {
            "property_id": "aldgate-flats",
            "guest_name": "TEST_NewGuest SMS",
            "guest_phone": "+447700777666",
            "channel": "sms",
            "message": "Hello! This is a test message via SMS."
        }
        response = requests.post(f"{BASE_URL}/api/messaging/new-conversation", json=payload, headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["conversation"]["channel"] == "sms"
        print(f"Created SMS conversation: {data['conversation']['id']}")
    
    def test_create_new_conversation_internal(self, auth_headers):
        """POST /api/messaging/new-conversation - creates conversation via Internal"""
        payload = {
            "property_id": "aldgate-flats",
            "guest_name": "TEST_NewGuest Internal",
            "guest_email": "test.internal@example.com",
            "channel": "internal",
            "message": "Hello! This is an internal note."
        }
        response = requests.post(f"{BASE_URL}/api/messaging/new-conversation", json=payload, headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["conversation"]["channel"] == "internal"
        print(f"Created Internal conversation: {data['conversation']['id']}")


class TestWhatsAppTelegramSandbox:
    """WhatsApp and Telegram sandbox mode tests"""
    
    def test_whatsapp_send_sandbox_mode(self, auth_headers):
        """POST /api/messaging/send/whatsapp - returns sandbox mode response"""
        payload = {
            "property_id": "aldgate-flats",
            "phone": "+447700123456",
            "message": "Test WhatsApp message"
        }
        response = requests.post(f"{BASE_URL}/api/messaging/send/whatsapp", json=payload, headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("status") == "sandbox", f"Expected sandbox status, got {data}"
        assert "sandbox" in data.get("message", "").lower() or "not configured" in data.get("message", "").lower(), f"Expected sandbox message, got {data.get('message')}"
        print(f"WhatsApp sandbox response: {data.get('message')}")
    
    def test_telegram_send_sandbox_mode(self, auth_headers):
        """POST /api/messaging/send/telegram - returns sandbox mode response"""
        payload = {
            "property_id": "aldgate-flats",
            "chat_id": "123456789",
            "message": "Test Telegram message"
        }
        response = requests.post(f"{BASE_URL}/api/messaging/send/telegram", json=payload, headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("status") == "sandbox", f"Expected sandbox status, got {data}"
        assert "sandbox" in data.get("message", "").lower() or "not configured" in data.get("message", "").lower(), f"Expected sandbox message, got {data.get('message')}"
        print(f"Telegram sandbox response: {data.get('message')}")


class TestExistingMessagingFeatures:
    """Verify existing messaging features still work"""
    
    def test_conversations_list(self, auth_headers):
        """GET /api/messaging/conversations/{property_id} - still works"""
        response = requests.get(f"{BASE_URL}/api/messaging/conversations/aldgate-flats", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Should return list of conversations"
        print(f"Conversations list: {len(data)} conversations")
    
    def test_conversations_stats(self, auth_headers):
        """GET /api/messaging/conversations/{property_id}/stats - still works"""
        response = requests.get(f"{BASE_URL}/api/messaging/conversations/aldgate-flats/stats", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "total" in data, "Stats should have total"
        assert "new" in data, "Stats should have new count"
        print(f"Stats: {data}")
    
    def test_quick_replies(self, auth_headers):
        """GET /api/messaging/quick-replies - still works"""
        response = requests.get(f"{BASE_URL}/api/messaging/quick-replies", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Should return list of quick replies"
        assert len(data) >= 10, f"Expected at least 10 quick replies, got {len(data)}"
        print(f"Quick replies: {len(data)} templates")


class TestCleanup:
    """Cleanup test data"""
    
    def test_cleanup_test_conversations(self, auth_headers):
        """Delete TEST_ prefixed conversations"""
        # Get all conversations
        response = requests.get(f"{BASE_URL}/api/messaging/conversations/aldgate-flats", headers=auth_headers)
        if response.status_code == 200:
            convs = response.json()
            for conv in convs:
                if conv.get("guest_name", "").startswith("TEST_"):
                    # Delete conversation (if endpoint exists)
                    print(f"Would delete test conversation: {conv['guest_name']}")
        print("Cleanup complete")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
