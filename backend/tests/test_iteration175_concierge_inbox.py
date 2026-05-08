"""
Iteration 175 - Concierge Inbox Admin Panel Tests
Tests for the admin endpoints that allow reception to view guest↔AI chats,
flag bad AI replies, and unflag them.

Endpoints tested:
- GET /api/concierge/admin/{property_id}/sessions
- GET /api/concierge/admin/{property_id}/session/{session_id}
- POST /api/concierge/admin/messages/{message_id}/flag
- POST /api/concierge/admin/messages/{message_id}/unflag
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestConciergeInboxAdmin:
    """Tests for Concierge Inbox admin endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test data"""
        self.property_id = "aldgate-flats"
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
    
    def test_get_sessions_returns_list(self):
        """GET /api/concierge/admin/{property_id}/sessions returns sessions list"""
        response = self.session.get(f"{BASE_URL}/api/concierge/admin/{self.property_id}/sessions")
        assert response.status_code == 200
        
        data = response.json()
        assert "sessions" in data
        assert "total_sessions" in data
        assert "total_messages" in data
        assert "flagged_messages" in data
        assert isinstance(data["sessions"], list)
        assert isinstance(data["total_sessions"], int)
        assert isinstance(data["total_messages"], int)
        assert isinstance(data["flagged_messages"], int)
        print(f"✓ Sessions endpoint returned {data['total_sessions']} sessions, {data['total_messages']} messages")
    
    def test_sessions_have_required_fields(self):
        """Each session has required fields: session_id, first_at, last_at, last_role, last_preview, messages, flagged"""
        response = self.session.get(f"{BASE_URL}/api/concierge/admin/{self.property_id}/sessions")
        assert response.status_code == 200
        
        data = response.json()
        if len(data["sessions"]) > 0:
            session = data["sessions"][0]
            required_fields = ["session_id", "first_at", "last_at", "last_role", "last_preview", "messages", "flagged"]
            for field in required_fields:
                assert field in session, f"Missing field: {field}"
            print(f"✓ Session has all required fields: {required_fields}")
        else:
            pytest.skip("No sessions available to test")
    
    def test_get_session_detail(self):
        """GET /api/concierge/admin/{property_id}/session/{session_id} returns message list"""
        # First get a session_id
        sessions_resp = self.session.get(f"{BASE_URL}/api/concierge/admin/{self.property_id}/sessions")
        assert sessions_resp.status_code == 200
        sessions = sessions_resp.json()["sessions"]
        
        if len(sessions) == 0:
            pytest.skip("No sessions available to test")
        
        session_id = sessions[0]["session_id"]
        
        # Get session detail
        response = self.session.get(f"{BASE_URL}/api/concierge/admin/{self.property_id}/session/{session_id}")
        assert response.status_code == 200
        
        data = response.json()
        assert "session_id" in data
        assert "messages" in data
        assert data["session_id"] == session_id
        assert isinstance(data["messages"], list)
        print(f"✓ Session detail returned {len(data['messages'])} messages")
    
    def test_session_messages_have_required_fields(self):
        """Each message has required fields: id, session_id, property_id, role, content, created_at"""
        sessions_resp = self.session.get(f"{BASE_URL}/api/concierge/admin/{self.property_id}/sessions")
        sessions = sessions_resp.json()["sessions"]
        
        if len(sessions) == 0:
            pytest.skip("No sessions available to test")
        
        session_id = sessions[0]["session_id"]
        response = self.session.get(f"{BASE_URL}/api/concierge/admin/{self.property_id}/session/{session_id}")
        data = response.json()
        
        if len(data["messages"]) > 0:
            msg = data["messages"][0]
            required_fields = ["id", "session_id", "property_id", "role", "content", "created_at"]
            for field in required_fields:
                assert field in msg, f"Missing field: {field}"
            print(f"✓ Message has all required fields: {required_fields}")
        else:
            pytest.skip("No messages in session")
    
    def test_flag_unknown_message_returns_404(self):
        """POST /api/concierge/admin/messages/{unknown_id}/flag returns 404"""
        unknown_id = f"unknown-{uuid.uuid4()}"
        response = self.session.post(
            f"{BASE_URL}/api/concierge/admin/messages/{unknown_id}/flag",
            json={"reason": "test reason"}
        )
        assert response.status_code == 404
        print("✓ Flag unknown message returns 404")
    
    def test_unflag_unknown_message_returns_404(self):
        """POST /api/concierge/admin/messages/{unknown_id}/unflag returns 404"""
        unknown_id = f"unknown-{uuid.uuid4()}"
        response = self.session.post(f"{BASE_URL}/api/concierge/admin/messages/{unknown_id}/unflag")
        assert response.status_code == 404
        print("✓ Unflag unknown message returns 404")
    
    def test_flag_and_unflag_message(self):
        """Flag and unflag a real message"""
        # Get a session with messages
        sessions_resp = self.session.get(f"{BASE_URL}/api/concierge/admin/{self.property_id}/sessions")
        sessions = sessions_resp.json()["sessions"]
        
        if len(sessions) == 0:
            pytest.skip("No sessions available to test")
        
        session_id = sessions[0]["session_id"]
        detail_resp = self.session.get(f"{BASE_URL}/api/concierge/admin/{self.property_id}/session/{session_id}")
        messages = detail_resp.json()["messages"]
        
        # Find an assistant message to flag
        assistant_msgs = [m for m in messages if m["role"] == "assistant"]
        if len(assistant_msgs) == 0:
            pytest.skip("No assistant messages to flag")
        
        msg_id = assistant_msgs[0]["id"]
        
        # Flag the message
        flag_resp = self.session.post(
            f"{BASE_URL}/api/concierge/admin/messages/{msg_id}/flag",
            json={"reason": "TEST_FLAG_REASON"}
        )
        assert flag_resp.status_code == 200
        assert flag_resp.json()["ok"] == True
        print(f"✓ Flagged message {msg_id}")
        
        # Verify flag was applied
        verify_resp = self.session.get(f"{BASE_URL}/api/concierge/admin/{self.property_id}/session/{session_id}")
        flagged_msg = [m for m in verify_resp.json()["messages"] if m["id"] == msg_id][0]
        assert flagged_msg.get("flagged") == True
        assert flagged_msg.get("flag_reason") == "TEST_FLAG_REASON"
        print("✓ Flag verified in database")
        
        # Unflag the message
        unflag_resp = self.session.post(f"{BASE_URL}/api/concierge/admin/messages/{msg_id}/unflag")
        assert unflag_resp.status_code == 200
        assert unflag_resp.json()["ok"] == True
        print(f"✓ Unflagged message {msg_id}")
        
        # Verify unflag was applied
        verify_resp2 = self.session.get(f"{BASE_URL}/api/concierge/admin/{self.property_id}/session/{session_id}")
        unflagged_msg = [m for m in verify_resp2.json()["messages"] if m["id"] == msg_id][0]
        assert unflagged_msg.get("flagged") == False
        assert "unflagged_at" in unflagged_msg
        print("✓ Unflag verified in database")


class TestConciergeRegressionSmoke:
    """Smoke tests for existing concierge functionality"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.property_id = "aldgate-flats"
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
    
    def test_concierge_chat_endpoint_works(self):
        """POST /api/concierge/{property_id}/chat still works"""
        response = self.session.post(
            f"{BASE_URL}/api/concierge/{self.property_id}/chat",
            json={"session_id": f"test-regression-{uuid.uuid4()}", "message": "Hello"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "reply" in data
        assert "session_id" in data
        print(f"✓ Concierge chat endpoint works, reply: {data['reply'][:50]}...")
    
    def test_concierge_history_endpoint_works(self):
        """GET /api/concierge/{property_id}/history still works"""
        response = self.session.get(
            f"{BASE_URL}/api/concierge/{self.property_id}/history",
            params={"session_id": "test-session-001"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "messages" in data
        print(f"✓ Concierge history endpoint works, {len(data['messages'])} messages")


class TestLoyaltyRegression:
    """Regression test for loyalty API"""
    
    def test_loyalty_check_api(self):
        """POST /api/booking-widget/loyalty-check still works"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        response = session.post(
            f"{BASE_URL}/api/booking-widget/loyalty-check",
            json={"guest_email": "test_stripe@example.com"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "tier" in data or "is_member" in data
        print(f"✓ Loyalty check API works, response: {data}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
