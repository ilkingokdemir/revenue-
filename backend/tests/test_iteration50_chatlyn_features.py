"""
Iteration 50 - Chatlyn Competitor Features Test Suite
Tests all 7 new features added to the Guest Messaging Hub:
1. Internal Notes with @mentions
2. Guest Booking Data Sidebar
3. Conversation Snooze
4. 1-Click Translate (AI GPT-5.2)
5. Conversation Analytics Dashboard
6. Webchat Widget Configurator
7. Contact Lists (static & dynamic)
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://review-hub-108.preview.emergentagent.com').rstrip('/')
PROPERTY_ID = "aldgate-flats"

class TestChatlynFeatures:
    """Test suite for all 7 chatlyn competitor features"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        self.token = data.get("token")
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        # Seed conversations for testing
        requests.post(f"{BASE_URL}/api/messaging/seed/{PROPERTY_ID}", headers=self.headers)
        yield
    
    # ==================== 1. INTERNAL NOTES ====================
    
    def test_create_internal_note(self):
        """Test creating an internal note with @mentions"""
        # First get a conversation
        convs = requests.get(f"{BASE_URL}/api/messaging/conversations/{PROPERTY_ID}", headers=self.headers)
        assert convs.status_code == 200
        conv_list = convs.json()
        assert len(conv_list) > 0, "No conversations found"
        conv_id = conv_list[0]["id"]
        
        # Create a note with mentions
        note_data = {
            "conversation_id": conv_id,
            "content": "Guest needs VIP treatment @manager @receptionist",
            "mentions": ["manager", "receptionist"]
        }
        response = requests.post(f"{BASE_URL}/api/messaging/notes", json=note_data, headers=self.headers)
        assert response.status_code == 200, f"Create note failed: {response.text}"
        note = response.json()
        assert note.get("id"), "Note ID missing"
        assert note.get("content") == note_data["content"]
        assert note.get("mentions") == ["manager", "receptionist"]
        assert note.get("author_name"), "Author name missing"
        self.created_note_id = note["id"]
        self.test_conv_id = conv_id
    
    def test_list_notes_for_conversation(self):
        """Test listing notes for a conversation"""
        # Get a conversation
        convs = requests.get(f"{BASE_URL}/api/messaging/conversations/{PROPERTY_ID}", headers=self.headers)
        conv_id = convs.json()[0]["id"]
        
        # Create a note first
        requests.post(f"{BASE_URL}/api/messaging/notes", json={
            "conversation_id": conv_id,
            "content": "Test note for listing",
            "mentions": []
        }, headers=self.headers)
        
        # List notes
        response = requests.get(f"{BASE_URL}/api/messaging/notes/{conv_id}", headers=self.headers)
        assert response.status_code == 200, f"List notes failed: {response.text}"
        notes = response.json()
        assert isinstance(notes, list)
        assert len(notes) > 0, "No notes returned"
    
    def test_delete_note(self):
        """Test deleting an internal note"""
        # Get a conversation and create a note
        convs = requests.get(f"{BASE_URL}/api/messaging/conversations/{PROPERTY_ID}", headers=self.headers)
        conv_id = convs.json()[0]["id"]
        
        create_resp = requests.post(f"{BASE_URL}/api/messaging/notes", json={
            "conversation_id": conv_id,
            "content": "Note to be deleted",
            "mentions": []
        }, headers=self.headers)
        note_id = create_resp.json()["id"]
        
        # Delete the note
        response = requests.delete(f"{BASE_URL}/api/messaging/notes/{note_id}", headers=self.headers)
        assert response.status_code == 200, f"Delete note failed: {response.text}"
        assert response.json().get("status") == "deleted"
    
    # ==================== 2. CONVERSATION SNOOZE ====================
    
    def test_snooze_conversation(self):
        """Test snoozing a conversation"""
        convs = requests.get(f"{BASE_URL}/api/messaging/conversations/{PROPERTY_ID}", headers=self.headers)
        conv_id = convs.json()[0]["id"]
        
        response = requests.post(f"{BASE_URL}/api/messaging/conversations/{conv_id}/snooze", 
                                json={"duration_minutes": 120}, headers=self.headers)
        assert response.status_code == 200, f"Snooze failed: {response.text}"
        data = response.json()
        assert data.get("status") == "snoozed"
        assert data.get("snoozed_until"), "snoozed_until missing"
    
    def test_unsnooze_conversation(self):
        """Test unsnoozing a conversation"""
        convs = requests.get(f"{BASE_URL}/api/messaging/conversations/{PROPERTY_ID}", headers=self.headers)
        conv_id = convs.json()[0]["id"]
        
        # First snooze
        requests.post(f"{BASE_URL}/api/messaging/conversations/{conv_id}/snooze", 
                     json={"duration_minutes": 60}, headers=self.headers)
        
        # Then unsnooze
        response = requests.post(f"{BASE_URL}/api/messaging/conversations/{conv_id}/unsnooze", headers=self.headers)
        assert response.status_code == 200, f"Unsnooze failed: {response.text}"
        assert response.json().get("status") == "unsnoozed"
    
    def test_check_snoozed_conversations(self):
        """Test auto-wake snoozed conversations endpoint"""
        response = requests.post(f"{BASE_URL}/api/messaging/snooze/check", headers=self.headers)
        assert response.status_code == 200, f"Snooze check failed: {response.text}"
        data = response.json()
        assert "woken_up" in data
    
    # ==================== 3. ONE-CLICK TRANSLATE ====================
    
    def test_translate_message(self):
        """Test translating text to target language using AI"""
        response = requests.post(f"{BASE_URL}/api/messaging/translate", json={
            "text": "Hello, how can I help you today?",
            "target_language": "Spanish"
        }, headers=self.headers)
        assert response.status_code == 200, f"Translate failed: {response.text}"
        data = response.json()
        assert data.get("translated_text"), "Translated text missing"
        assert data.get("target_language") == "Spanish"
        assert data.get("original_text") == "Hello, how can I help you today?"
    
    def test_translate_to_french(self):
        """Test translating to French"""
        response = requests.post(f"{BASE_URL}/api/messaging/translate", json={
            "text": "Good morning, your room is ready.",
            "target_language": "French"
        }, headers=self.headers)
        assert response.status_code == 200, f"Translate to French failed: {response.text}"
        data = response.json()
        assert data.get("translated_text")
        assert data.get("target_language") == "French"
    
    def test_detect_language(self):
        """Test language detection"""
        response = requests.post(f"{BASE_URL}/api/messaging/detect-language", json={
            "text": "Bonjour, comment puis-je vous aider?"
        }, headers=self.headers)
        assert response.status_code == 200, f"Detect language failed: {response.text}"
        data = response.json()
        assert data.get("language"), "Language detection result missing"
    
    def test_translate_empty_text(self):
        """Test translate with empty text returns error"""
        response = requests.post(f"{BASE_URL}/api/messaging/translate", json={
            "text": "",
            "target_language": "German"
        }, headers=self.headers)
        assert response.status_code == 400, "Should return 400 for empty text"
    
    # ==================== 4. GUEST BOOKING DATA SIDEBAR ====================
    
    def test_get_guest_booking_data(self):
        """Test getting guest booking data for a conversation"""
        convs = requests.get(f"{BASE_URL}/api/messaging/conversations/{PROPERTY_ID}", headers=self.headers)
        conv_id = convs.json()[0]["id"]
        
        response = requests.get(f"{BASE_URL}/api/messaging/guest-booking-data/{conv_id}", headers=self.headers)
        assert response.status_code == 200, f"Get booking data failed: {response.text}"
        data = response.json()
        assert "guest_name" in data
        assert "total_stays" in data
        assert "total_spent" in data
        assert "bookings" in data
        assert "vip" in data
        assert "loyalty_tier" in data
    
    def test_guest_booking_data_not_found(self):
        """Test getting booking data for non-existent conversation"""
        response = requests.get(f"{BASE_URL}/api/messaging/guest-booking-data/nonexistent-conv-id", headers=self.headers)
        assert response.status_code == 404
    
    # ==================== 5. CONVERSATION ANALYTICS ====================
    
    def test_conversation_analytics_30d(self):
        """Test conversation analytics for 30 days"""
        response = requests.get(f"{BASE_URL}/api/messaging/analytics/{PROPERTY_ID}?period=30d", headers=self.headers)
        assert response.status_code == 200, f"Analytics failed: {response.text}"
        data = response.json()
        
        # Verify all expected fields
        assert "period_days" in data
        assert data["period_days"] == 30
        assert "total_conversations" in data
        assert "avg_first_response_min" in data
        assert "avg_resolution_min" in data
        assert "resolution_rate" in data
        assert "by_channel" in data
        assert "by_status" in data
        assert "by_agent" in data
        assert "heatmap" in data
        assert "daily_trend" in data
        assert "sentiment" in data
    
    def test_conversation_analytics_7d(self):
        """Test conversation analytics for 7 days"""
        response = requests.get(f"{BASE_URL}/api/messaging/analytics/{PROPERTY_ID}?period=7d", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert data["period_days"] == 7
    
    def test_analytics_heatmap_structure(self):
        """Test that heatmap has correct structure (7 days x 24 hours)"""
        response = requests.get(f"{BASE_URL}/api/messaging/analytics/{PROPERTY_ID}?period=30d", headers=self.headers)
        data = response.json()
        heatmap = data.get("heatmap", [])
        assert len(heatmap) == 7, "Heatmap should have 7 days"
        for day in heatmap:
            assert len(day) == 24, "Each day should have 24 hours"
    
    # ==================== 6. WEBCHAT WIDGET CONFIGURATOR ====================
    
    def test_get_webchat_config(self):
        """Test getting webchat widget configuration"""
        response = requests.get(f"{BASE_URL}/api/messaging/webchat-config/{PROPERTY_ID}", headers=self.headers)
        assert response.status_code == 200, f"Get webchat config failed: {response.text}"
        data = response.json()
        
        # Verify default config fields
        assert "property_id" in data
        assert "enabled" in data
        assert "widget_color" in data
        assert "widget_position" in data
        assert "welcome_message" in data
        assert "offline_message" in data
        assert "ai_enabled" in data
        assert "require_name" in data
        assert "require_email" in data
        assert "bubble_text" in data
    
    def test_update_webchat_config(self):
        """Test updating webchat widget configuration"""
        updates = {
            "widget_color": "#FF5733",
            "welcome_message": "Welcome to our hotel! How can we assist you?",
            "bubble_text": "Need help?",
            "ai_enabled": True,
            "require_email": True
        }
        response = requests.put(f"{BASE_URL}/api/messaging/webchat-config/{PROPERTY_ID}", 
                               json=updates, headers=self.headers)
        assert response.status_code == 200, f"Update webchat config failed: {response.text}"
        data = response.json()
        assert data.get("widget_color") == "#FF5733"
        assert data.get("welcome_message") == "Welcome to our hotel! How can we assist you?"
        assert data.get("bubble_text") == "Need help?"
    
    def test_get_webchat_embed_code(self):
        """Test getting webchat embed code"""
        response = requests.get(f"{BASE_URL}/api/messaging/webchat-embed/{PROPERTY_ID}", headers=self.headers)
        assert response.status_code == 200, f"Get embed code failed: {response.text}"
        data = response.json()
        assert "embed_code" in data
        assert "config" in data
        assert "<script>" in data["embed_code"]
        assert PROPERTY_ID in data["embed_code"]
    
    # ==================== 7. CONTACT LISTS ====================
    
    def test_create_static_contact_list(self):
        """Test creating a static contact list"""
        list_data = {
            "property_id": PROPERTY_ID,
            "name": "TEST_VIP Guests",
            "description": "Our most valued guests",
            "list_type": "static",
            "members": [
                {"name": "John Doe", "email": "john@example.com", "phone": "+447700123456"}
            ]
        }
        response = requests.post(f"{BASE_URL}/api/messaging/contact-lists", json=list_data, headers=self.headers)
        assert response.status_code == 200, f"Create contact list failed: {response.text}"
        data = response.json()
        assert data.get("id")
        assert data.get("name") == "TEST_VIP Guests"
        assert data.get("list_type") == "static"
        self.created_list_id = data["id"]
    
    def test_create_dynamic_contact_list(self):
        """Test creating a dynamic contact list with filters"""
        list_data = {
            "property_id": PROPERTY_ID,
            "name": "TEST_Frequent Visitors",
            "description": "Guests with 3+ stays",
            "list_type": "dynamic",
            "filters": {"min_stays": 3}
        }
        response = requests.post(f"{BASE_URL}/api/messaging/contact-lists", json=list_data, headers=self.headers)
        assert response.status_code == 200, f"Create dynamic list failed: {response.text}"
        data = response.json()
        assert data.get("list_type") == "dynamic"
        assert data.get("filters", {}).get("min_stays") == 3
    
    def test_list_contact_lists(self):
        """Test listing contact lists for a property"""
        # Create a list first
        requests.post(f"{BASE_URL}/api/messaging/contact-lists", json={
            "property_id": PROPERTY_ID,
            "name": "TEST_List for Listing",
            "list_type": "static"
        }, headers=self.headers)
        
        response = requests.get(f"{BASE_URL}/api/messaging/contact-lists/{PROPERTY_ID}", headers=self.headers)
        assert response.status_code == 200, f"List contact lists failed: {response.text}"
        lists = response.json()
        assert isinstance(lists, list)
    
    def test_update_contact_list(self):
        """Test updating a contact list"""
        # Create a list
        create_resp = requests.post(f"{BASE_URL}/api/messaging/contact-lists", json={
            "property_id": PROPERTY_ID,
            "name": "TEST_List to Update",
            "list_type": "static"
        }, headers=self.headers)
        list_id = create_resp.json()["id"]
        
        # Update it
        response = requests.put(f"{BASE_URL}/api/messaging/contact-lists/{list_id}", json={
            "name": "TEST_Updated List Name",
            "description": "Updated description"
        }, headers=self.headers)
        assert response.status_code == 200, f"Update list failed: {response.text}"
        data = response.json()
        assert data.get("name") == "TEST_Updated List Name"
    
    def test_delete_contact_list(self):
        """Test deleting a contact list"""
        # Create a list
        create_resp = requests.post(f"{BASE_URL}/api/messaging/contact-lists", json={
            "property_id": PROPERTY_ID,
            "name": "TEST_List to Delete",
            "list_type": "static"
        }, headers=self.headers)
        list_id = create_resp.json()["id"]
        
        # Delete it
        response = requests.delete(f"{BASE_URL}/api/messaging/contact-lists/{list_id}", headers=self.headers)
        assert response.status_code == 200, f"Delete list failed: {response.text}"
        assert response.json().get("status") == "deleted"
    
    def test_get_list_members_static(self):
        """Test getting members of a static list"""
        # Create a list with members
        create_resp = requests.post(f"{BASE_URL}/api/messaging/contact-lists", json={
            "property_id": PROPERTY_ID,
            "name": "TEST_List with Members",
            "list_type": "static",
            "members": [
                {"name": "Alice", "email": "alice@test.com"},
                {"name": "Bob", "email": "bob@test.com"}
            ]
        }, headers=self.headers)
        list_id = create_resp.json()["id"]
        
        # Get members
        response = requests.get(f"{BASE_URL}/api/messaging/contact-lists/{list_id}/members", headers=self.headers)
        assert response.status_code == 200, f"Get members failed: {response.text}"
        data = response.json()
        assert data.get("list_type") == "static"
        assert "members" in data
        assert data.get("total") >= 2
    
    def test_add_member_to_list(self):
        """Test adding a member to a static list"""
        # Create a list
        create_resp = requests.post(f"{BASE_URL}/api/messaging/contact-lists", json={
            "property_id": PROPERTY_ID,
            "name": "TEST_List for Adding",
            "list_type": "static"
        }, headers=self.headers)
        list_id = create_resp.json()["id"]
        
        # Add member
        response = requests.post(f"{BASE_URL}/api/messaging/contact-lists/{list_id}/add-member", json={
            "name": "New Member",
            "email": "newmember@test.com",
            "phone": "+447700999888"
        }, headers=self.headers)
        assert response.status_code == 200, f"Add member failed: {response.text}"
        assert response.json().get("status") == "added"
    
    def test_remove_member_from_list(self):
        """Test removing a member from a list"""
        # Create a list with a member
        create_resp = requests.post(f"{BASE_URL}/api/messaging/contact-lists", json={
            "property_id": PROPERTY_ID,
            "name": "TEST_List for Removing",
            "list_type": "static",
            "members": [{"name": "To Remove", "email": "remove@test.com"}]
        }, headers=self.headers)
        list_id = create_resp.json()["id"]
        
        # Remove member
        response = requests.post(f"{BASE_URL}/api/messaging/contact-lists/{list_id}/remove-member", json={
            "email": "remove@test.com"
        }, headers=self.headers)
        assert response.status_code == 200, f"Remove member failed: {response.text}"
        assert response.json().get("status") == "removed"
    
    def test_get_list_members_not_found(self):
        """Test getting members of non-existent list"""
        response = requests.get(f"{BASE_URL}/api/messaging/contact-lists/nonexistent-list-id/members", headers=self.headers)
        assert response.status_code == 404


class TestExistingMessagingFeatures:
    """Regression tests for existing messaging features"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert response.status_code == 200
        self.token = response.json().get("token")
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        yield
    
    def test_list_conversations(self):
        """Test listing conversations"""
        response = requests.get(f"{BASE_URL}/api/messaging/conversations/{PROPERTY_ID}", headers=self.headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)
    
    def test_conversation_stats(self):
        """Test conversation stats endpoint"""
        response = requests.get(f"{BASE_URL}/api/messaging/conversations/{PROPERTY_ID}/stats", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "new" in data
        assert "in_progress" in data
    
    def test_list_messages(self):
        """Test listing messages for a conversation"""
        convs = requests.get(f"{BASE_URL}/api/messaging/conversations/{PROPERTY_ID}", headers=self.headers)
        if convs.json():
            conv_id = convs.json()[0]["id"]
            response = requests.get(f"{BASE_URL}/api/messaging/messages/{conv_id}", headers=self.headers)
            assert response.status_code == 200
            assert isinstance(response.json(), list)
    
    def test_send_message(self):
        """Test sending a message"""
        convs = requests.get(f"{BASE_URL}/api/messaging/conversations/{PROPERTY_ID}", headers=self.headers)
        if convs.json():
            conv_id = convs.json()[0]["id"]
            response = requests.post(f"{BASE_URL}/api/messaging/messages", json={
                "conversation_id": conv_id,
                "content": "Test message from automated test",
                "channel": "internal"
            }, headers=self.headers)
            assert response.status_code == 200
            assert response.json().get("id")
    
    def test_ai_suggest_reply(self):
        """Test AI suggest reply endpoint"""
        convs = requests.get(f"{BASE_URL}/api/messaging/conversations/{PROPERTY_ID}", headers=self.headers)
        if convs.json():
            conv_id = convs.json()[0]["id"]
            response = requests.post(
                f"{BASE_URL}/api/messaging/messages/ai-suggest?conversation_id={conv_id}&guest_message=What time is checkout?&property_id={PROPERTY_ID}",
                headers=self.headers
            )
            assert response.status_code == 200
            assert "suggestion" in response.json()
    
    def test_quick_replies(self):
        """Test quick replies endpoint"""
        response = requests.get(f"{BASE_URL}/api/messaging/quick-replies", headers=self.headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)
    
    def test_auto_replies(self):
        """Test auto-replies endpoint"""
        response = requests.get(f"{BASE_URL}/api/messaging/auto-replies/{PROPERTY_ID}", headers=self.headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)
    
    def test_resolve_conversation(self):
        """Test resolving a conversation"""
        convs = requests.get(f"{BASE_URL}/api/messaging/conversations/{PROPERTY_ID}", headers=self.headers)
        if convs.json():
            conv_id = convs.json()[0]["id"]
            response = requests.post(f"{BASE_URL}/api/messaging/conversations/{conv_id}/resolve", headers=self.headers)
            assert response.status_code == 200
    
    def test_assign_conversation(self):
        """Test assigning a conversation"""
        convs = requests.get(f"{BASE_URL}/api/messaging/conversations/{PROPERTY_ID}", headers=self.headers)
        if convs.json():
            conv_id = convs.json()[0]["id"]
            response = requests.post(
                f"{BASE_URL}/api/messaging/conversations/{conv_id}/assign?user_id=admin&user_name=Admin",
                headers=self.headers
            )
            assert response.status_code == 200
    
    def test_guest_directory(self):
        """Test guest directory endpoint"""
        response = requests.get(f"{BASE_URL}/api/messaging/guests/{PROPERTY_ID}", headers=self.headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)
    
    def test_channel_settings(self):
        """Test channel settings endpoint"""
        response = requests.get(f"{BASE_URL}/api/messaging/channel-settings/{PROPERTY_ID}", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert "whatsapp_enabled" in data
        assert "telegram_enabled" in data


class TestConversationStatusSnoozed:
    """Test that 'snoozed' status is properly integrated"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        self.token = response.json().get("token")
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        yield
    
    def test_filter_by_snoozed_status(self):
        """Test filtering conversations by snoozed status"""
        # First snooze a conversation
        convs = requests.get(f"{BASE_URL}/api/messaging/conversations/{PROPERTY_ID}", headers=self.headers)
        if convs.json():
            conv_id = convs.json()[0]["id"]
            requests.post(f"{BASE_URL}/api/messaging/conversations/{conv_id}/snooze", 
                         json={"duration_minutes": 60}, headers=self.headers)
        
        # Filter by snoozed status
        response = requests.get(f"{BASE_URL}/api/messaging/conversations/{PROPERTY_ID}?status=snoozed", headers=self.headers)
        assert response.status_code == 200
        # All returned conversations should be snoozed
        for conv in response.json():
            assert conv.get("status") == "snoozed"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
