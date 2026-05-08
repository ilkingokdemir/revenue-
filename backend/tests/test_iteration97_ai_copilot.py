"""
Iteration 97 - AI Revenue Copilot Tests
Tests the GPT-5.2 powered chat assistant for revenue management.
Endpoints: POST /api/revenue/copilot/{property_id}/chat
           GET /api/revenue/copilot/{property_id}/history
           DELETE /api/revenue/copilot/{property_id}/clear
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for admin user"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    if response.status_code == 200:
        data = response.json()
        return data.get("access_token") or data.get("token")
    pytest.skip(f"Authentication failed: {response.status_code} - {response.text}")


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Headers with authentication token"""
    return {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json"
    }


class TestAICopilotEndpoints:
    """Test AI Revenue Copilot API endpoints"""
    
    def test_copilot_chat_requires_auth(self):
        """POST /api/revenue/copilot/all/chat requires authentication"""
        response = requests.post(f"{BASE_URL}/api/revenue/copilot/all/chat", json={
            "message": "How is today's performance?"
        })
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ Copilot chat endpoint requires authentication")
    
    def test_copilot_history_requires_auth(self):
        """GET /api/revenue/copilot/all/history requires authentication"""
        response = requests.get(f"{BASE_URL}/api/revenue/copilot/all/history")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ Copilot history endpoint requires authentication")
    
    def test_copilot_clear_requires_auth(self):
        """DELETE /api/revenue/copilot/all/clear requires authentication"""
        response = requests.delete(f"{BASE_URL}/api/revenue/copilot/all/clear")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ Copilot clear endpoint requires authentication")
    
    def test_clear_chat_history(self, auth_headers):
        """DELETE /api/revenue/copilot/all/clear - Clear chat history before tests"""
        response = requests.delete(f"{BASE_URL}/api/revenue/copilot/all/clear", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "message" in data
        print(f"✓ Cleared chat history: {data['message']}")
    
    def test_get_empty_history(self, auth_headers):
        """GET /api/revenue/copilot/all/history - Returns empty after clear"""
        response = requests.get(f"{BASE_URL}/api/revenue/copilot/all/history", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "messages" in data
        assert isinstance(data["messages"], list)
        print(f"✓ History endpoint returns messages array (count: {len(data['messages'])})")
    
    def test_copilot_chat_sends_message(self, auth_headers):
        """POST /api/revenue/copilot/all/chat - Send message and get AI response"""
        response = requests.post(
            f"{BASE_URL}/api/revenue/copilot/all/chat",
            headers=auth_headers,
            json={"message": "How is today's performance?"},
            timeout=60  # AI responses can take time
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "response" in data, "Response should contain 'response' field"
        assert "message_id" in data, "Response should contain 'message_id' field"
        assert isinstance(data["response"], str), "Response should be a string"
        assert len(data["response"]) > 0, "Response should not be empty"
        
        print(f"✓ Chat endpoint returns AI response (length: {len(data['response'])} chars)")
        print(f"  Message ID: {data['message_id']}")
        print(f"  Response preview: {data['response'][:200]}...")
    
    def test_copilot_response_contains_hotel_data(self, auth_headers):
        """POST /api/revenue/copilot/all/chat - AI response should reference hotel data"""
        response = requests.post(
            f"{BASE_URL}/api/revenue/copilot/all/chat",
            headers=auth_headers,
            json={"message": "What is my current occupancy rate and ADR?"},
            timeout=60
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        ai_response = data.get("response", "").lower()
        
        # Check if response mentions hotel metrics (occupancy, ADR, RevPAR, etc.)
        hotel_terms = ["occupancy", "adr", "revpar", "rate", "revenue", "booking", "%", "£"]
        found_terms = [term for term in hotel_terms if term in ai_response]
        
        assert len(found_terms) > 0, f"AI response should mention hotel data. Response: {ai_response[:300]}"
        print(f"✓ AI response contains hotel data terms: {found_terms}")
    
    def test_get_history_after_messages(self, auth_headers):
        """GET /api/revenue/copilot/all/history - Returns messages after chat"""
        response = requests.get(f"{BASE_URL}/api/revenue/copilot/all/history", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        messages = data.get("messages", [])
        assert len(messages) >= 2, f"Expected at least 2 messages (user + assistant), got {len(messages)}"
        
        # Verify message structure
        for msg in messages:
            assert "id" in msg, "Message should have 'id'"
            assert "role" in msg, "Message should have 'role'"
            assert "content" in msg, "Message should have 'content'"
            assert "created_at" in msg, "Message should have 'created_at'"
            assert msg["role"] in ["user", "assistant"], f"Invalid role: {msg['role']}"
        
        # Check we have both user and assistant messages
        roles = [msg["role"] for msg in messages]
        assert "user" in roles, "Should have user messages"
        assert "assistant" in roles, "Should have assistant messages"
        
        print(f"✓ History contains {len(messages)} messages with proper structure")
        print(f"  Roles: {roles}")
    
    def test_copilot_empty_message_handling(self, auth_headers):
        """POST /api/revenue/copilot/all/chat - Handle empty message"""
        response = requests.post(
            f"{BASE_URL}/api/revenue/copilot/all/chat",
            headers=auth_headers,
            json={"message": ""}
        )
        # Should return error for empty message
        data = response.json()
        assert "error" in data or response.status_code != 200, "Empty message should return error"
        print("✓ Empty message handled correctly")
    
    def test_copilot_quick_prompt_rate_recommendations(self, auth_headers):
        """POST /api/revenue/copilot/all/chat - Test rate recommendations prompt"""
        response = requests.post(
            f"{BASE_URL}/api/revenue/copilot/all/chat",
            headers=auth_headers,
            json={"message": "Based on current occupancy patterns and demand, what specific rate changes do you recommend for the next 7 days? Give me exact numbers."},
            timeout=60
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "response" in data
        assert len(data["response"]) > 50, "Rate recommendations should be detailed"
        print(f"✓ Rate recommendations prompt works (response length: {len(data['response'])} chars)")
    
    def test_clear_chat_history_final(self, auth_headers):
        """DELETE /api/revenue/copilot/all/clear - Clear history and verify"""
        # Clear
        response = requests.delete(f"{BASE_URL}/api/revenue/copilot/all/clear", headers=auth_headers)
        assert response.status_code == 200
        
        # Verify cleared
        response = requests.get(f"{BASE_URL}/api/revenue/copilot/all/history", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data.get("messages", [])) == 0, "History should be empty after clear"
        print("✓ Chat history cleared and verified empty")


class TestAICopilotWithPropertyId:
    """Test AI Copilot with specific property ID"""
    
    def test_copilot_with_specific_property(self, auth_headers):
        """POST /api/revenue/copilot/{property_id}/chat - Works with specific property"""
        # First get a property ID
        props_response = requests.get(f"{BASE_URL}/api/properties", headers=auth_headers)
        if props_response.status_code == 200:
            properties = props_response.json()
            if properties and len(properties) > 0:
                prop_id = properties[0].get("id", "all")
                
                response = requests.post(
                    f"{BASE_URL}/api/revenue/copilot/{prop_id}/chat",
                    headers=auth_headers,
                    json={"message": "Give me a quick summary of this property's performance."},
                    timeout=60
                )
                assert response.status_code == 200, f"Expected 200, got {response.status_code}"
                data = response.json()
                assert "response" in data
                print(f"✓ Copilot works with specific property ID: {prop_id}")
                
                # Clean up
                requests.delete(f"{BASE_URL}/api/revenue/copilot/{prop_id}/clear", headers=auth_headers)
                return
        
        print("✓ Skipped specific property test (no properties found)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
