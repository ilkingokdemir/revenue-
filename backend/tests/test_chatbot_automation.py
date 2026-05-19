"""
Test suite for Chatbot Automation and Automation Parity features (Iter 327)

Tests:
1. Chatbot Settings CRUD
2. Chatbot Intents CRUD
3. Chatbot Keywords CRUD
4. Chatbot Sentiment Actions CRUD
5. Chatbot Test endpoint (intent matching, handoff, fallback)
6. Chatbot Runs log
7. Automation rule duplicate endpoint
8. Automation rule skip-guest endpoint
9. Automation rule history endpoint
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
PROPERTY_ID = "aldgate-flats"

# Session-scoped auth token
_AUTH_TOKEN = None

def get_auth_headers():
    """Get auth headers, caching the token"""
    global _AUTH_TOKEN
    if _AUTH_TOKEN is None:
        resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert resp.status_code == 200, f"Login failed: {resp.text}"
        data = resp.json()
        _AUTH_TOKEN = data.get("access_token") or data.get("token")
    return {"Authorization": f"Bearer {_AUTH_TOKEN}"}


# ==================== CHATBOT SETTINGS ====================
class TestChatbotSettings:
    """Chatbot settings CRUD tests"""
    
    def test_get_settings_returns_defaults(self):
        """GET /chatbot/{property_id}/settings returns default config"""
        headers = get_auth_headers()
        resp = requests.get(f"{BASE_URL}/api/chatbot/{PROPERTY_ID}/settings", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "enabled" in data
        assert "default_language" in data
        assert "default_tone" in data
        assert "fallback_message" in data
        assert "handoff_keywords" in data
        print(f"✓ Settings returned: enabled={data.get('enabled')}, language={data.get('default_language')}")
    
    def test_put_settings_persists(self):
        """PUT /chatbot/{property_id}/settings persists updates"""
        headers = get_auth_headers()
        new_fallback = f"Test fallback message {uuid.uuid4().hex[:8]}"
        resp = requests.put(f"{BASE_URL}/api/chatbot/{PROPERTY_ID}/settings", headers=headers, json={
            "enabled": True,
            "default_tone": "professional",
            "default_language": "tr",
            "fallback_message": new_fallback,
            "handoff_keywords": ["agent", "human", "operatör"]
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("fallback_message") == new_fallback
        assert data.get("default_tone") == "professional"
        
        # Verify persistence with GET
        resp2 = requests.get(f"{BASE_URL}/api/chatbot/{PROPERTY_ID}/settings", headers=headers)
        assert resp2.status_code == 200
        assert resp2.json().get("fallback_message") == new_fallback
        print(f"✓ Settings persisted: fallback_message updated")


# ==================== CHATBOT INTENTS ====================
class TestChatbotIntents:
    """Chatbot intents CRUD tests"""
    
    def test_create_intent(self):
        """POST /chatbot/{property_id}/intents creates intent"""
        headers = get_auth_headers()
        resp = requests.post(f"{BASE_URL}/api/chatbot/{PROPERTY_ID}/intents", headers=headers, json={
            "name": f"TEST_Breakfast_Intent_{uuid.uuid4().hex[:6]}",
            "trigger_phrases": ["kahvaltı", "breakfast", "yemek"],
            "action_type": "reply_guest",
            "reply_text": "Kahvaltı 07:00-10:00 arası servis edilmektedir."
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "id" in data
        assert data.get("name").startswith("TEST_Breakfast")
        assert len(data.get("trigger_phrases", [])) == 3
        print(f"✓ Intent created: {data.get('name')}")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/chatbot/intents/{data['id']}", headers=headers)
    
    def test_list_intents(self):
        """GET /chatbot/{property_id}/intents lists intents"""
        headers = get_auth_headers()
        resp = requests.get(f"{BASE_URL}/api/chatbot/{PROPERTY_ID}/intents", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "count" in data
        print(f"✓ Listed {data.get('count')} intents")
    
    def test_patch_intent(self):
        """PATCH /chatbot/intents/{intent_id} updates intent"""
        headers = get_auth_headers()
        # Create first
        resp = requests.post(f"{BASE_URL}/api/chatbot/{PROPERTY_ID}/intents", headers=headers, json={
            "name": f"TEST_WiFi_Patch_{uuid.uuid4().hex[:6]}",
            "trigger_phrases": ["wifi", "internet"],
            "action_type": "reply_guest",
            "reply_text": "WiFi şifremiz: HotelGuest2026"
        })
        assert resp.status_code == 200
        intent_id = resp.json().get("id")
        
        # Patch
        resp2 = requests.patch(f"{BASE_URL}/api/chatbot/intents/{intent_id}", headers=headers, json={
            "reply_text": "Updated WiFi password: NewPass2026"
        })
        assert resp2.status_code == 200
        data = resp2.json()
        assert "Updated WiFi" in data.get("reply_text", "")
        print(f"✓ Intent patched: reply_text updated")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/chatbot/intents/{intent_id}", headers=headers)
    
    def test_delete_intent(self):
        """DELETE /chatbot/intents/{intent_id} removes intent"""
        headers = get_auth_headers()
        # Create first
        resp = requests.post(f"{BASE_URL}/api/chatbot/{PROPERTY_ID}/intents", headers=headers, json={
            "name": f"TEST_ToDelete_{uuid.uuid4().hex[:6]}",
            "trigger_phrases": ["delete", "test"],
            "action_type": "reply_guest",
            "reply_text": "Test"
        })
        intent_id = resp.json().get("id")
        
        # Delete
        resp2 = requests.delete(f"{BASE_URL}/api/chatbot/intents/{intent_id}", headers=headers)
        assert resp2.status_code == 200
        assert resp2.json().get("status") == "deleted"
        print(f"✓ Intent deleted")


# ==================== CHATBOT KEYWORDS ====================
class TestChatbotKeywords:
    """Chatbot keywords CRUD tests"""
    
    def test_create_keyword(self):
        """POST /chatbot/{property_id}/keywords creates keyword"""
        headers = get_auth_headers()
        resp = requests.post(f"{BASE_URL}/api/chatbot/{PROPERTY_ID}/keywords", headers=headers, json={
            "command": f"test_refund_{uuid.uuid4().hex[:6]}",
            "action_type": "create_ticket",
            "reply_text": "İade talebiniz oluşturuldu."
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "id" in data
        assert data.get("action_type") == "create_ticket"
        print(f"✓ Keyword created: {data.get('command')}")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/chatbot/keywords/{data['id']}", headers=headers)
    
    def test_list_keywords(self):
        """GET /chatbot/{property_id}/keywords lists keywords"""
        headers = get_auth_headers()
        resp = requests.get(f"{BASE_URL}/api/chatbot/{PROPERTY_ID}/keywords", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        print(f"✓ Listed {data.get('count')} keywords")
    
    def test_delete_keyword(self):
        """DELETE /chatbot/keywords/{keyword_id} removes keyword"""
        headers = get_auth_headers()
        # Create first
        resp = requests.post(f"{BASE_URL}/api/chatbot/{PROPERTY_ID}/keywords", headers=headers, json={
            "command": f"test_del_{uuid.uuid4().hex[:6]}",
            "action_type": "reply_guest",
            "reply_text": "Test"
        })
        kw_id = resp.json().get("id")
        
        # Delete
        resp2 = requests.delete(f"{BASE_URL}/api/chatbot/keywords/{kw_id}", headers=headers)
        assert resp2.status_code == 200
        print(f"✓ Keyword deleted")


# ==================== CHATBOT SENTIMENT ACTIONS ====================
class TestChatbotSentimentActions:
    """Chatbot sentiment actions CRUD tests"""
    
    def test_create_sentiment_action_positive(self):
        """POST /chatbot/{property_id}/sentiment-actions creates positive action"""
        headers = get_auth_headers()
        resp = requests.post(f"{BASE_URL}/api/chatbot/{PROPERTY_ID}/sentiment-actions", headers=headers, json={
            "sentiment": "positive",
            "action_type": "notify_team_chat",
            "reply_text": "Teşekkür ederiz! Memnuniyetiniz bizim için önemli."
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("sentiment") == "positive"
        print(f"✓ Positive sentiment action created")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/chatbot/sentiment-actions/{data['id']}", headers=headers)
    
    def test_create_sentiment_action_negative(self):
        """POST /chatbot/{property_id}/sentiment-actions creates negative action"""
        headers = get_auth_headers()
        resp = requests.post(f"{BASE_URL}/api/chatbot/{PROPERTY_ID}/sentiment-actions", headers=headers, json={
            "sentiment": "negative",
            "action_type": "create_ticket",
            "reply_text": "Şikayetiniz için özür dileriz. Ekibimiz en kısa sürede sizinle iletişime geçecek."
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("sentiment") == "negative"
        print(f"✓ Negative sentiment action created")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/chatbot/sentiment-actions/{data['id']}", headers=headers)


# ==================== CHATBOT TEST ENDPOINT ====================
class TestChatbotTestEndpoint:
    """Chatbot test/match endpoint tests"""
    
    def test_test_with_matching_intent(self):
        """POST /chatbot/{property_id}/test with matching text returns intent"""
        headers = get_auth_headers()
        # Create a WiFi intent first
        resp = requests.post(f"{BASE_URL}/api/chatbot/{PROPERTY_ID}/intents", headers=headers, json={
            "name": "TEST_WiFi_Match",
            "trigger_phrases": ["wifi", "wifi şifresi", "internet", "şifre nedir"],
            "action_type": "reply_guest",
            "reply_text": "WiFi şifremiz: HotelGuest2026"
        })
        intent_id = resp.json().get("id")
        
        # Test matching
        resp2 = requests.post(f"{BASE_URL}/api/chatbot/{PROPERTY_ID}/test", headers=headers, json={
            "text": "wifi şifresi nedir"
        })
        assert resp2.status_code == 200
        data = resp2.json()
        assert data.get("matched") == True
        assert data.get("match_type") == "intent"
        assert "intent" in data
        print(f"✓ Test matched intent: {data.get('intent', {}).get('name')}")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/chatbot/intents/{intent_id}", headers=headers)
    
    def test_test_with_handoff_keyword(self):
        """POST /chatbot/{property_id}/test with handoff keyword returns handoff"""
        headers = get_auth_headers()
        resp = requests.post(f"{BASE_URL}/api/chatbot/{PROPERTY_ID}/test", headers=headers, json={
            "text": "operatör ile görüşmek istiyorum"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("matched") == True
        assert data.get("match_type") == "handoff"
        print(f"✓ Test matched handoff keyword")
    
    def test_test_with_no_match_returns_fallback(self):
        """POST /chatbot/{property_id}/test with no match returns fallback"""
        headers = get_auth_headers()
        resp = requests.post(f"{BASE_URL}/api/chatbot/{PROPERTY_ID}/test", headers=headers, json={
            "text": f"random gibberish {uuid.uuid4().hex}"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("matched") == False
        assert data.get("match_type") == "none"
        assert "fallback_message" in data
        print(f"✓ Test returned fallback: {data.get('fallback_message', '')[:50]}...")


# ==================== CHATBOT RUNS LOG ====================
class TestChatbotRuns:
    """Chatbot runs audit log tests"""
    
    def test_get_runs_returns_log(self):
        """GET /chatbot/{property_id}/runs returns audit log"""
        headers = get_auth_headers()
        # First trigger a test to create a run
        requests.post(f"{BASE_URL}/api/chatbot/{PROPERTY_ID}/test", headers=headers, json={
            "text": "test message for runs log"
        })
        
        resp = requests.get(f"{BASE_URL}/api/chatbot/{PROPERTY_ID}/runs?limit=50", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "count" in data
        print(f"✓ Runs log returned {data.get('count')} entries")


# ==================== AUTOMATION DUPLICATE ====================
class TestAutomationDuplicate:
    """Automation rule duplicate endpoint tests"""
    
    def test_duplicate_rule_creates_copy(self):
        """POST /automation/rules/{rule_id}/duplicate creates copy with 'Copy of' prefix"""
        headers = get_auth_headers()
        # List existing rules
        resp = requests.get(f"{BASE_URL}/api/automation/rules/{PROPERTY_ID}", headers=headers)
        rules = resp.json()
        
        if not rules or len(rules) == 0:
            # Create one if none exist
            resp = requests.post(f"{BASE_URL}/api/automation/rules", headers=headers, json={
                "property_id": PROPERTY_ID,
                "name": "TEST_Rule_For_Duplicate",
                "trigger": "pre_arrival",
                "timing_hours": -24,
                "channel": "email",
                "message_template": "Test message",
                "enabled": True
            })
            rule_id = resp.json().get("id")
        else:
            rule_id = rules[0].get("id")
        
        # Duplicate
        resp2 = requests.post(f"{BASE_URL}/api/automation/rules/{rule_id}/duplicate", headers=headers)
        assert resp2.status_code == 200
        data = resp2.json()
        assert data.get("name", "").startswith("Copy of")
        assert data.get("enabled") == False  # Should be disabled by default
        assert data.get("id") != rule_id  # New ID
        print(f"✓ Rule duplicated: {data.get('name')}, enabled={data.get('enabled')}")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/automation/rules/{data['id']}", headers=headers)


# ==================== AUTOMATION SKIP-GUEST ====================
class TestAutomationSkipGuest:
    """Automation rule skip-guest endpoint tests"""
    
    def test_skip_guest_adds_to_list(self):
        """POST /automation/rules/{rule_id}/skip-guest adds booking_ref to skip list"""
        headers = get_auth_headers()
        resp = requests.get(f"{BASE_URL}/api/automation/rules/{PROPERTY_ID}", headers=headers)
        rules = resp.json()
        
        if not rules or len(rules) == 0:
            pytest.skip("No rules available")
        
        rule_id = rules[0].get("id")
        test_booking_ref = f"TEST-BK-{uuid.uuid4().hex[:8]}"
        resp2 = requests.post(f"{BASE_URL}/api/automation/rules/{rule_id}/skip-guest", headers=headers, json={
            "booking_ref": test_booking_ref
        })
        assert resp2.status_code == 200
        data = resp2.json()
        assert data.get("status") == "skipped"
        assert data.get("booking_ref") == test_booking_ref
        print(f"✓ Skip-guest added: {test_booking_ref}")


# ==================== AUTOMATION HISTORY ====================
class TestAutomationHistory:
    """Automation rule history endpoint tests"""
    
    def test_get_rule_history(self):
        """GET /automation/rules/{rule_id}/history returns logs for rule"""
        headers = get_auth_headers()
        resp = requests.get(f"{BASE_URL}/api/automation/rules/{PROPERTY_ID}", headers=headers)
        rules = resp.json()
        
        if not rules or len(rules) == 0:
            pytest.skip("No rules available")
        
        rule_id = rules[0].get("id")
        resp2 = requests.get(f"{BASE_URL}/api/automation/rules/{rule_id}/history?limit=50", headers=headers)
        assert resp2.status_code == 200
        data = resp2.json()
        assert "rule_id" in data
        assert "items" in data
        assert "count" in data
        print(f"✓ Rule history returned {data.get('count')} entries")


# ==================== CONTENT SOURCES (AI GENERATE - SKIP ACTUAL CALL) ====================
class TestChatbotContentSources:
    """Chatbot content sources tests (skip actual AI generation to save tokens)"""
    
    def test_generate_endpoint_validates_url(self):
        """POST /chatbot/{property_id}/content-sources/generate validates URL required"""
        headers = get_auth_headers()
        resp = requests.post(f"{BASE_URL}/api/chatbot/{PROPERTY_ID}/content-sources/generate", headers=headers, json={
            "tone": "friendly"
            # Missing URL
        })
        assert resp.status_code == 400
        assert "url" in resp.json().get("detail", "").lower()
        print(f"✓ Generate endpoint validates URL required")
    
    def test_list_content_sources(self):
        """GET /chatbot/{property_id}/content-sources lists sources"""
        headers = get_auth_headers()
        resp = requests.get(f"{BASE_URL}/api/chatbot/{PROPERTY_ID}/content-sources", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        print(f"✓ Content sources listed: {data.get('count')} sources")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
