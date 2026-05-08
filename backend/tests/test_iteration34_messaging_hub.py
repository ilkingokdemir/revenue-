"""
Iteration 34 - Unified Messaging Hub Backend Tests
Tests for: conversations, messages, AI suggest, quick replies, resolve/assign, channel settings
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
PROPERTY_ID = "aldgate-flats"

class TestAuth:
    """Get auth token for protected endpoints"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Login and get token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "token" in data, "No token in response"
        return data["token"]
    
    @pytest.fixture(scope="class")
    def auth_headers(self, auth_token):
        """Headers with auth token"""
        return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


class TestMessagingSeed(TestAuth):
    """Test seeding demo conversations"""
    
    def test_seed_conversations(self, auth_headers):
        """POST /api/messaging/seed/{property_id} - seeds demo conversations"""
        response = requests.post(f"{BASE_URL}/api/messaging/seed/{PROPERTY_ID}", headers=auth_headers)
        assert response.status_code == 200, f"Seed failed: {response.text}"
        data = response.json()
        # Should return count (either newly seeded or existing)
        assert "count" in data, "No count in seed response"
        assert data["count"] >= 0, "Count should be >= 0"
        print(f"Seed result: {data}")


class TestConversations(TestAuth):
    """Test conversation listing and stats"""
    
    def test_list_conversations(self, auth_headers):
        """GET /api/messaging/conversations/{property_id} - returns conversations"""
        response = requests.get(f"{BASE_URL}/api/messaging/conversations/{PROPERTY_ID}", headers=auth_headers)
        assert response.status_code == 200, f"List conversations failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        # Should have 6 demo conversations
        assert len(data) >= 6, f"Expected at least 6 conversations, got {len(data)}"
        # Verify conversation structure
        if len(data) > 0:
            conv = data[0]
            assert "id" in conv, "Conversation missing id"
            assert "guest_name" in conv, "Conversation missing guest_name"
            assert "channel" in conv, "Conversation missing channel"
            assert "status" in conv, "Conversation missing status"
            assert "priority" in conv, "Conversation missing priority"
            print(f"Found {len(data)} conversations")
    
    def test_list_conversations_filter_status(self, auth_headers):
        """GET /api/messaging/conversations/{property_id}?status=new - filter by status"""
        response = requests.get(f"{BASE_URL}/api/messaging/conversations/{PROPERTY_ID}?status=new", headers=auth_headers)
        assert response.status_code == 200, f"Filter by status failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        # All returned should have status=new
        for conv in data:
            assert conv["status"] == "new", f"Expected status=new, got {conv['status']}"
        print(f"Found {len(data)} new conversations")
    
    def test_list_conversations_filter_channel(self, auth_headers):
        """GET /api/messaging/conversations/{property_id}?channel=whatsapp - filter by channel"""
        response = requests.get(f"{BASE_URL}/api/messaging/conversations/{PROPERTY_ID}?channel=whatsapp", headers=auth_headers)
        assert response.status_code == 200, f"Filter by channel failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        for conv in data:
            assert conv["channel"] == "whatsapp", f"Expected channel=whatsapp, got {conv['channel']}"
        print(f"Found {len(data)} WhatsApp conversations")
    
    def test_conversation_stats(self, auth_headers):
        """GET /api/messaging/conversations/{property_id}/stats - returns correct counts"""
        response = requests.get(f"{BASE_URL}/api/messaging/conversations/{PROPERTY_ID}/stats", headers=auth_headers)
        assert response.status_code == 200, f"Stats failed: {response.text}"
        data = response.json()
        # Verify stats structure
        assert "total" in data, "Stats missing total"
        assert "new" in data, "Stats missing new count"
        assert "in_progress" in data, "Stats missing in_progress count"
        assert "waiting" in data, "Stats missing waiting count"
        assert "resolved" in data, "Stats missing resolved count"
        assert "by_channel" in data, "Stats missing by_channel breakdown"
        # Total should be >= 6 (demo conversations)
        assert data["total"] >= 6, f"Expected total >= 6, got {data['total']}"
        print(f"Stats: total={data['total']}, new={data['new']}, in_progress={data['in_progress']}")


class TestMessages(TestAuth):
    """Test message operations"""
    
    @pytest.fixture(scope="class")
    def conversation_id(self, auth_headers):
        """Get a conversation ID for testing"""
        response = requests.get(f"{BASE_URL}/api/messaging/conversations/{PROPERTY_ID}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) > 0, "No conversations found"
        return data[0]["id"]
    
    def test_list_messages(self, auth_headers, conversation_id):
        """GET /api/messaging/messages/{conv_id} - returns messages"""
        response = requests.get(f"{BASE_URL}/api/messaging/messages/{conversation_id}", headers=auth_headers)
        assert response.status_code == 200, f"List messages failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        # Demo conversations have messages
        assert len(data) >= 1, f"Expected at least 1 message, got {len(data)}"
        # Verify message structure
        msg = data[0]
        assert "id" in msg, "Message missing id"
        assert "content" in msg, "Message missing content"
        assert "sender_type" in msg, "Message missing sender_type"
        print(f"Found {len(data)} messages in conversation")
    
    def test_send_message(self, auth_headers, conversation_id):
        """POST /api/messaging/messages - sends staff message"""
        test_content = f"TEST_message_{int(time.time())}"
        response = requests.post(f"{BASE_URL}/api/messaging/messages", headers=auth_headers, json={
            "conversation_id": conversation_id,
            "content": test_content,
            "channel": "whatsapp"
        })
        assert response.status_code == 200, f"Send message failed: {response.text}"
        data = response.json()
        assert "id" in data, "Response missing message id"
        assert data["content"] == test_content, "Content mismatch"
        assert data["sender_type"] == "staff", "Sender type should be staff"
        print(f"Sent message: {data['id']}")
        
        # Verify message appears in conversation
        response2 = requests.get(f"{BASE_URL}/api/messaging/messages/{conversation_id}", headers=auth_headers)
        assert response2.status_code == 200
        messages = response2.json()
        found = any(m["content"] == test_content for m in messages)
        assert found, "Sent message not found in conversation"


class TestAISuggest(TestAuth):
    """Test AI suggestion endpoint"""
    
    @pytest.fixture(scope="class")
    def conversation_id(self, auth_headers):
        """Get a conversation ID for testing"""
        response = requests.get(f"{BASE_URL}/api/messaging/conversations/{PROPERTY_ID}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) > 0, "No conversations found"
        return data[0]["id"]
    
    def test_ai_suggest_reply(self, auth_headers, conversation_id):
        """POST /api/messaging/messages/ai-suggest - returns AI suggestion"""
        guest_message = "The air conditioning in my room isn't working"
        response = requests.post(
            f"{BASE_URL}/api/messaging/messages/ai-suggest?conversation_id={conversation_id}&guest_message={guest_message}&property_id={PROPERTY_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200, f"AI suggest failed: {response.text}"
        data = response.json()
        assert "suggestion" in data, "Response missing suggestion"
        assert "conversation_id" in data, "Response missing conversation_id"
        assert len(data["suggestion"]) > 10, "Suggestion too short"
        print(f"AI suggestion: {data['suggestion'][:100]}...")


class TestQuickReplies(TestAuth):
    """Test quick reply templates"""
    
    def test_list_quick_replies(self, auth_headers):
        """GET /api/messaging/quick-replies - returns templates"""
        response = requests.get(f"{BASE_URL}/api/messaging/quick-replies", headers=auth_headers)
        assert response.status_code == 200, f"List quick replies failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        # Should have default templates (10 seeded)
        assert len(data) >= 10, f"Expected at least 10 quick replies, got {len(data)}"
        # Verify structure
        qr = data[0]
        assert "id" in qr, "Quick reply missing id"
        assert "name" in qr, "Quick reply missing name"
        assert "content" in qr, "Quick reply missing content"
        print(f"Found {len(data)} quick reply templates")
    
    def test_use_quick_reply(self, auth_headers):
        """POST /api/messaging/quick-replies/{id}/use - increments usage count"""
        # Get a quick reply
        response = requests.get(f"{BASE_URL}/api/messaging/quick-replies", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) > 0, "No quick replies found"
        qr_id = data[0]["id"]
        
        # Use it
        response2 = requests.post(f"{BASE_URL}/api/messaging/quick-replies/{qr_id}/use", headers=auth_headers)
        assert response2.status_code == 200, f"Use quick reply failed: {response2.text}"
        result = response2.json()
        assert result.get("status") == "incremented", "Expected status=incremented"
        print(f"Used quick reply: {qr_id}")


class TestConversationActions(TestAuth):
    """Test assign and resolve actions"""
    
    @pytest.fixture(scope="class")
    def conversation_id(self, auth_headers):
        """Get a conversation ID for testing (preferably new status)"""
        response = requests.get(f"{BASE_URL}/api/messaging/conversations/{PROPERTY_ID}?status=new", headers=auth_headers)
        if response.status_code == 200 and len(response.json()) > 0:
            return response.json()[0]["id"]
        # Fallback to any conversation
        response = requests.get(f"{BASE_URL}/api/messaging/conversations/{PROPERTY_ID}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) > 0, "No conversations found"
        return data[0]["id"]
    
    def test_assign_conversation(self, auth_headers, conversation_id):
        """POST /api/messaging/conversations/{id}/assign - assigns to user"""
        response = requests.post(
            f"{BASE_URL}/api/messaging/conversations/{conversation_id}/assign?user_id=admin&user_name=Admin",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Assign failed: {response.text}"
        data = response.json()
        assert data.get("status") == "assigned", "Expected status=assigned"
        print(f"Assigned conversation: {conversation_id}")
    
    def test_resolve_conversation(self, auth_headers, conversation_id):
        """POST /api/messaging/conversations/{id}/resolve - resolves conversation"""
        response = requests.post(
            f"{BASE_URL}/api/messaging/conversations/{conversation_id}/resolve",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Resolve failed: {response.text}"
        data = response.json()
        assert data.get("status") == "resolved", "Expected status=resolved"
        
        # Verify status changed
        response2 = requests.get(f"{BASE_URL}/api/messaging/conversations/{PROPERTY_ID}", headers=auth_headers)
        assert response2.status_code == 200
        convs = response2.json()
        conv = next((c for c in convs if c["id"] == conversation_id), None)
        assert conv is not None, "Conversation not found"
        assert conv["status"] == "resolved", f"Expected status=resolved, got {conv['status']}"
        print(f"Resolved conversation: {conversation_id}")


class TestSpaceBookingsAdmin(TestAuth):
    """Test space bookings admin endpoints"""
    
    def test_space_booking_stats(self, auth_headers):
        """GET /api/spaces/admin/stats/{property_id} - returns stats"""
        response = requests.get(f"{BASE_URL}/api/spaces/admin/stats/{PROPERTY_ID}", headers=auth_headers)
        assert response.status_code == 200, f"Space stats failed: {response.text}"
        data = response.json()
        assert "total_bookings" in data, "Stats missing total_bookings"
        assert "confirmed" in data, "Stats missing confirmed"
        assert "spaces_count" in data, "Stats missing spaces_count"
        # Should have 8 seeded spaces
        assert data["spaces_count"] >= 8, f"Expected spaces_count >= 8, got {data['spaces_count']}"
        print(f"Space stats: {data}")
    
    def test_list_admin_bookings(self, auth_headers):
        """GET /api/spaces/admin/bookings/{property_id} - returns bookings"""
        response = requests.get(f"{BASE_URL}/api/spaces/admin/bookings/{PROPERTY_ID}", headers=auth_headers)
        assert response.status_code == 200, f"List admin bookings failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"Found {len(data)} space bookings")


class TestConciergeAnalytics(TestAuth):
    """Test AI concierge analytics endpoint"""
    
    def test_concierge_analytics(self, auth_headers):
        """GET /api/concierge/analytics/{property_id} - returns analytics data"""
        response = requests.get(f"{BASE_URL}/api/concierge/analytics/{PROPERTY_ID}", headers=auth_headers)
        assert response.status_code == 200, f"Concierge analytics failed: {response.text}"
        data = response.json()
        assert "total_sessions" in data, "Analytics missing total_sessions"
        assert "total_messages" in data, "Analytics missing total_messages"
        assert "user_messages" in data, "Analytics missing user_messages"
        assert "ai_messages" in data, "Analytics missing ai_messages"
        assert "recent_sessions" in data, "Analytics missing recent_sessions"
        print(f"Concierge analytics: sessions={data['total_sessions']}, messages={data['total_messages']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
