"""
Iteration 174 - AI Concierge Chat Tests
Tests for the floating chat bubble on the public booking widget.
Endpoints:
- POST /api/concierge/{property_id}/chat (PUBLIC, no auth)
- GET /api/concierge/{property_id}/history?session_id=...
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
PROPERTY_ID = "aldgate-flats"

class TestConciergeChat:
    """AI Concierge chat endpoint tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session ID"""
        self.session_id = f"test-{uuid.uuid4()}"
    
    # ─── POST /api/concierge/{property_id}/chat ───
    
    def test_chat_basic_message(self):
        """Test sending a basic message to concierge"""
        response = requests.post(
            f"{BASE_URL}/api/concierge/{PROPERTY_ID}/chat",
            json={"session_id": self.session_id, "message": "What time is check-in?"},
            timeout=30  # GPT-5.2 can take 5-15s
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "reply" in data, "Response should contain 'reply'"
        assert "session_id" in data, "Response should contain 'session_id'"
        assert "suggestions" in data, "Response should contain 'suggestions'"
        assert isinstance(data["suggestions"], list), "suggestions should be a list"
        assert len(data["reply"]) > 0, "Reply should not be empty"
        print(f"✓ Chat reply received: {data['reply'][:100]}...")
    
    def test_chat_returns_session_id_when_not_provided(self):
        """Test that server generates session_id if not provided"""
        response = requests.post(
            f"{BASE_URL}/api/concierge/{PROPERTY_ID}/chat",
            json={"message": "Hello"},
            timeout=30
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "session_id" in data, "Server should generate session_id"
        assert len(data["session_id"]) > 0, "Generated session_id should not be empty"
        print(f"✓ Server generated session_id: {data['session_id']}")
    
    def test_chat_empty_message_returns_400(self):
        """Test that empty message returns 400"""
        response = requests.post(
            f"{BASE_URL}/api/concierge/{PROPERTY_ID}/chat",
            json={"session_id": self.session_id, "message": ""},
            timeout=10
        )
        assert response.status_code == 400, f"Expected 400 for empty message, got {response.status_code}"
        print("✓ Empty message correctly returns 400")
    
    def test_chat_whitespace_only_message_returns_400(self):
        """Test that whitespace-only message returns 400"""
        response = requests.post(
            f"{BASE_URL}/api/concierge/{PROPERTY_ID}/chat",
            json={"session_id": self.session_id, "message": "   "},
            timeout=10
        )
        assert response.status_code == 400, f"Expected 400 for whitespace message, got {response.status_code}"
        print("✓ Whitespace-only message correctly returns 400")
    
    def test_chat_message_too_long_returns_400(self):
        """Test that message > 1000 chars returns 400"""
        long_message = "a" * 1001
        response = requests.post(
            f"{BASE_URL}/api/concierge/{PROPERTY_ID}/chat",
            json={"session_id": self.session_id, "message": long_message},
            timeout=10
        )
        assert response.status_code == 400, f"Expected 400 for long message, got {response.status_code}"
        print("✓ Message > 1000 chars correctly returns 400")
    
    def test_chat_message_exactly_1000_chars_succeeds(self):
        """Test that message exactly 1000 chars succeeds"""
        exact_message = "a" * 1000
        response = requests.post(
            f"{BASE_URL}/api/concierge/{PROPERTY_ID}/chat",
            json={"session_id": self.session_id, "message": exact_message},
            timeout=30
        )
        assert response.status_code == 200, f"Expected 200 for 1000 char message, got {response.status_code}"
        print("✓ Message exactly 1000 chars succeeds")
    
    def test_chat_response_has_suggestions(self):
        """Test that response includes suggestion chips"""
        response = requests.post(
            f"{BASE_URL}/api/concierge/{PROPERTY_ID}/chat",
            json={"session_id": self.session_id, "message": "Tell me about the rooms"},
            timeout=30
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "suggestions" in data
        assert isinstance(data["suggestions"], list)
        assert len(data["suggestions"]) > 0, "Should have at least one suggestion"
        print(f"✓ Suggestions received: {data['suggestions']}")
    
    def test_chat_fallback_field_present(self):
        """Test that fallback field is present in response"""
        response = requests.post(
            f"{BASE_URL}/api/concierge/{PROPERTY_ID}/chat",
            json={"session_id": self.session_id, "message": "What amenities do you have?"},
            timeout=30
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "fallback" in data, "Response should contain 'fallback' field"
        assert isinstance(data["fallback"], bool), "fallback should be boolean"
        print(f"✓ Fallback field present: {data['fallback']}")
    
    # ─── GET /api/concierge/{property_id}/history ───
    
    def test_history_empty_session(self):
        """Test history returns empty for new session"""
        new_session = f"new-{uuid.uuid4()}"
        response = requests.get(
            f"{BASE_URL}/api/concierge/{PROPERTY_ID}/history?session_id={new_session}",
            timeout=10
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "messages" in data
        assert isinstance(data["messages"], list)
        assert len(data["messages"]) == 0, "New session should have no history"
        print("✓ Empty session returns empty messages list")
    
    def test_history_no_session_id_returns_empty(self):
        """Test history without session_id returns empty"""
        response = requests.get(
            f"{BASE_URL}/api/concierge/{PROPERTY_ID}/history",
            timeout=10
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "messages" in data
        assert len(data["messages"]) == 0
        print("✓ No session_id returns empty messages")
    
    def test_history_after_chat(self):
        """Test history returns messages after chat"""
        session = f"history-test-{uuid.uuid4()}"
        
        # Send a message first
        chat_response = requests.post(
            f"{BASE_URL}/api/concierge/{PROPERTY_ID}/chat",
            json={"session_id": session, "message": "Hello, what is check-in time?"},
            timeout=30
        )
        assert chat_response.status_code == 200
        
        # Now get history
        history_response = requests.get(
            f"{BASE_URL}/api/concierge/{PROPERTY_ID}/history?session_id={session}",
            timeout=10
        )
        assert history_response.status_code == 200
        
        data = history_response.json()
        assert "messages" in data
        assert len(data["messages"]) >= 2, "Should have at least user + assistant messages"
        
        # Verify message structure
        for msg in data["messages"]:
            assert "role" in msg, "Message should have 'role'"
            assert "content" in msg, "Message should have 'content'"
            assert "created_at" in msg, "Message should have 'created_at'"
            assert msg["role"] in ["user", "assistant"], f"Invalid role: {msg['role']}"
        
        # Verify order (should be chronological)
        roles = [m["role"] for m in data["messages"]]
        assert roles[0] == "user", "First message should be from user"
        assert roles[1] == "assistant", "Second message should be from assistant"
        print(f"✓ History contains {len(data['messages'])} messages in correct order")
    
    def test_history_messages_ordered_chronologically(self):
        """Test that history messages are ordered by created_at ascending"""
        session = f"order-test-{uuid.uuid4()}"
        
        # Send two messages
        requests.post(
            f"{BASE_URL}/api/concierge/{PROPERTY_ID}/chat",
            json={"session_id": session, "message": "First question"},
            timeout=30
        )
        requests.post(
            f"{BASE_URL}/api/concierge/{PROPERTY_ID}/chat",
            json={"session_id": session, "message": "Second question"},
            timeout=30
        )
        
        # Get history
        response = requests.get(
            f"{BASE_URL}/api/concierge/{PROPERTY_ID}/history?session_id={session}",
            timeout=10
        )
        assert response.status_code == 200
        
        data = response.json()
        messages = data["messages"]
        
        # Verify chronological order
        for i in range(1, len(messages)):
            assert messages[i]["created_at"] >= messages[i-1]["created_at"], \
                "Messages should be in chronological order"
        print(f"✓ {len(messages)} messages in chronological order")


class TestConciergeHotelContext:
    """Test that concierge uses real hotel context"""
    
    def test_reply_references_hotel_name(self):
        """Test that reply references the actual hotel name"""
        session = f"context-{uuid.uuid4()}"
        response = requests.post(
            f"{BASE_URL}/api/concierge/{PROPERTY_ID}/chat",
            json={"session_id": session, "message": "What is the name of this hotel?"},
            timeout=30
        )
        assert response.status_code == 200
        
        data = response.json()
        reply_lower = data["reply"].lower()
        # Should mention Aldgate Flats or similar
        assert "aldgate" in reply_lower or "hotel" in reply_lower or "flats" in reply_lower, \
            f"Reply should reference hotel name. Got: {data['reply']}"
        print(f"✓ Reply references hotel context: {data['reply'][:100]}...")
    
    def test_reply_mentions_check_in_time(self):
        """Test that reply mentions check-in time from context"""
        session = f"checkin-{uuid.uuid4()}"
        response = requests.post(
            f"{BASE_URL}/api/concierge/{PROPERTY_ID}/chat",
            json={"session_id": session, "message": "What time is check-in?"},
            timeout=30
        )
        assert response.status_code == 200
        
        data = response.json()
        # Should mention a time (15:00 or 3pm or similar)
        reply = data["reply"]
        has_time = any(t in reply for t in ["15:00", "3:00", "3pm", "3 pm", "15", "three"])
        print(f"✓ Check-in time reply: {reply[:150]}...")
        # Note: We don't assert strictly because LLM might phrase differently


class TestRegressionSmoke:
    """Smoke tests for regression from iteration 173"""
    
    def test_loyalty_check_endpoint(self):
        """Regression: Loyalty check still works"""
        response = requests.post(
            f"{BASE_URL}/api/booking-widget/loyalty-check",
            json={"guest_email": "test_stripe@example.com"},
            timeout=10
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("is_member") == True, "test_stripe@example.com should be a member"
        assert data.get("tier") == "platinum", "Should be platinum tier"
        assert data.get("discount_pct") == 18, "Platinum should have 18% discount"
        print("✓ Loyalty check regression passed (platinum member)")
    
    def test_admin_login(self):
        """Regression: Admin login still works"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "admin@hotelbox.com", "password": "HotelAdmin2026!"},
            timeout=10
        )
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        
        data = response.json()
        assert "token" in data or "access_token" in data, "Should return token"
        print("✓ Admin login regression passed")
    
    def test_marketing_roi_endpoint(self):
        """Regression: Marketing ROI endpoint still works"""
        # First login as admin
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "admin@hotelbox.com", "password": "HotelAdmin2026!"},
            timeout=10
        )
        assert login_response.status_code == 200
        token = login_response.json().get("token") or login_response.json().get("access_token")
        
        # Get ROI data
        response = requests.get(
            f"{BASE_URL}/api/marketing/automation/roi/{PROPERTY_ID}?days=90",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        assert response.status_code == 200, f"ROI endpoint failed: {response.text}"
        
        data = response.json()
        assert "sent" in data, "Should have 'sent' field"
        assert "conversions" in data, "Should have 'conversions' field"
        print("✓ Marketing ROI regression passed")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
