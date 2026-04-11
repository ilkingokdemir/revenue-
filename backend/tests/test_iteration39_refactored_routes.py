"""
Iteration 39 - Regression Tests for Refactored Routes
Tests messaging, automation, and dashboard routes extracted from server.py
Property ID: myhotelbox-london
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://review-hub-108.preview.emergentagent.com')

class TestAuth:
    """Authentication tests"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get auth token for admin user"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "token" in data, "No token in response"
        return data["token"]
    
    def test_login_success(self):
        """Test admin login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert data["email"] == "admin@hotelbox.com"
        assert data["role"] == "admin"
        print(f"✓ Login successful: {data['email']}")


class TestMessagingRoutes:
    """Tests for /api/messaging/* routes extracted to routes/messaging.py"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        token = response.json()["token"]
        return {"Authorization": f"Bearer {token}"}
    
    @pytest.fixture(scope="class")
    def property_id(self):
        return "myhotelbox-london"
    
    def test_seed_conversations(self, auth_headers, property_id):
        """POST /api/messaging/seed/{property_id} - Seed demo conversations"""
        response = requests.post(
            f"{BASE_URL}/api/messaging/seed/{property_id}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "count" in data
        print(f"✓ Seed conversations: {data['message']}")
    
    def test_list_conversations(self, auth_headers, property_id):
        """GET /api/messaging/conversations/{property_id} - List conversations"""
        response = requests.get(
            f"{BASE_URL}/api/messaging/conversations/{property_id}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ List conversations: {len(data)} conversations found")
    
    def test_conversation_stats(self, auth_headers, property_id):
        """GET /api/messaging/conversations/{property_id}/stats - Conversation stats"""
        response = requests.get(
            f"{BASE_URL}/api/messaging/conversations/{property_id}/stats",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "new" in data
        assert "in_progress" in data
        assert "waiting" in data
        assert "resolved" in data
        assert "unread" in data
        assert "by_channel" in data
        print(f"✓ Conversation stats: total={data['total']}, new={data['new']}")
    
    def test_create_conversation(self, auth_headers, property_id):
        """POST /api/messaging/conversations - Create conversation"""
        response = requests.post(
            f"{BASE_URL}/api/messaging/conversations",
            headers=auth_headers,
            json={
                "property_id": property_id,
                "guest_name": "Test Guest Iteration39",
                "guest_email": "test39@example.com",
                "channel": "email",
                "status": "new",
                "priority": "medium"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["guest_name"] == "Test Guest Iteration39"
        print(f"✓ Create conversation: {data['id']}")
        return data["id"]
    
    def test_list_messages(self, auth_headers, property_id):
        """GET /api/messaging/messages/{conv_id} - List messages"""
        # First get a conversation
        convs = requests.get(
            f"{BASE_URL}/api/messaging/conversations/{property_id}",
            headers=auth_headers
        ).json()
        if convs:
            conv_id = convs[0]["id"]
            response = requests.get(
                f"{BASE_URL}/api/messaging/messages/{conv_id}",
                headers=auth_headers
            )
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)
            print(f"✓ List messages: {len(data)} messages for conv {conv_id[:8]}...")
        else:
            pytest.skip("No conversations to test messages")
    
    def test_send_message(self, auth_headers, property_id):
        """POST /api/messaging/messages - Send message"""
        # First get a conversation
        convs = requests.get(
            f"{BASE_URL}/api/messaging/conversations/{property_id}",
            headers=auth_headers
        ).json()
        if convs:
            conv_id = convs[0]["id"]
            response = requests.post(
                f"{BASE_URL}/api/messaging/messages",
                headers=auth_headers,
                json={
                    "conversation_id": conv_id,
                    "content": "Test message from iteration 39"
                }
            )
            assert response.status_code == 200
            data = response.json()
            assert "id" in data
            assert data["content"] == "Test message from iteration 39"
            print(f"✓ Send message: {data['id']}")
        else:
            pytest.skip("No conversations to send message")
    
    def test_quick_replies(self, auth_headers):
        """GET /api/messaging/quick-replies - Quick reply templates"""
        response = requests.get(
            f"{BASE_URL}/api/messaging/quick-replies",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Quick replies: {len(data)} templates")
    
    def test_channel_settings_get(self, auth_headers, property_id):
        """GET /api/messaging/channel-settings/{property_id} - Get channel settings"""
        response = requests.get(
            f"{BASE_URL}/api/messaging/channel-settings/{property_id}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "property_id" in data
        print(f"✓ Get channel settings for {property_id}")
    
    def test_channel_settings_update(self, auth_headers, property_id):
        """PUT /api/messaging/channel-settings/{property_id} - Update channel settings"""
        response = requests.put(
            f"{BASE_URL}/api/messaging/channel-settings/{property_id}",
            headers=auth_headers,
            json={
                "email_enabled": True,
                "email_signature": "Test Signature Iteration 39"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("email_signature") == "Test Signature Iteration 39"
        print(f"✓ Update channel settings")
    
    def test_guest_directory(self, auth_headers, property_id):
        """GET /api/messaging/guests/{property_id} - Guest directory"""
        response = requests.get(
            f"{BASE_URL}/api/messaging/guests/{property_id}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Guest directory: {len(data)} guests")
    
    def test_auto_replies_list(self, auth_headers, property_id):
        """GET /api/messaging/auto-replies/{property_id} - Auto reply rules"""
        response = requests.get(
            f"{BASE_URL}/api/messaging/auto-replies/{property_id}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Auto replies: {len(data)} rules")
    
    def test_auto_reply_create(self, auth_headers, property_id):
        """POST /api/messaging/auto-replies - Create auto reply"""
        response = requests.post(
            f"{BASE_URL}/api/messaging/auto-replies",
            headers=auth_headers,
            json={
                "property_id": property_id,
                "name": "Test Auto Reply Iteration39",
                "keywords": ["test39", "iteration"],
                "response": "This is a test auto reply",
                "enabled": True
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["name"] == "Test Auto Reply Iteration39"
        print(f"✓ Create auto reply: {data['id']}")
    
    def test_messaging_calendar(self, auth_headers, property_id):
        """GET /api/messaging/calendar/{property_id} - Messaging calendar"""
        response = requests.get(
            f"{BASE_URL}/api/messaging/calendar/{property_id}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "month" in data
        assert "bookings" in data
        assert "day_events" in data
        assert "stats" in data
        print(f"✓ Messaging calendar: month={data['month']}")
    
    def test_send_whatsapp_sandbox(self, auth_headers, property_id):
        """POST /api/messaging/send/whatsapp - WhatsApp sandbox mode"""
        response = requests.post(
            f"{BASE_URL}/api/messaging/send/whatsapp",
            headers=auth_headers,
            json={
                "property_id": property_id,
                "phone": "+447700123456",
                "message": "Test WhatsApp message"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "sandbox"
        assert data["sent"] == False
        print(f"✓ WhatsApp sandbox mode: {data['message'][:50]}...")
    
    def test_send_telegram_sandbox(self, auth_headers, property_id):
        """POST /api/messaging/send/telegram - Telegram sandbox mode"""
        response = requests.post(
            f"{BASE_URL}/api/messaging/send/telegram",
            headers=auth_headers,
            json={
                "property_id": property_id,
                "chat_id": "123456789",
                "message": "Test Telegram message"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "sandbox"
        assert data["sent"] == False
        print(f"✓ Telegram sandbox mode: {data['message'][:50]}...")
    
    def test_send_email(self, auth_headers, property_id):
        """POST /api/messaging/send/email - Send email"""
        response = requests.post(
            f"{BASE_URL}/api/messaging/send/email",
            headers=auth_headers,
            json={
                "email": "test@example.com",
                "subject": "Test Email Iteration 39",
                "message": "This is a test email"
            }
        )
        assert response.status_code == 200
        data = response.json()
        # Email may succeed or fail depending on Resend config
        assert "status" in data
        print(f"✓ Send email: status={data['status']}")


class TestAutomationRoutes:
    """Tests for /api/automation/* routes extracted to routes/automation.py"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        token = response.json()["token"]
        return {"Authorization": f"Bearer {token}"}
    
    @pytest.fixture(scope="class")
    def property_id(self):
        return "myhotelbox-london"
    
    def test_list_automation_rules(self, auth_headers, property_id):
        """GET /api/automation/rules/{property_id} - List automation rules"""
        response = requests.get(
            f"{BASE_URL}/api/automation/rules/{property_id}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ List automation rules: {len(data)} rules")
    
    def test_create_automation_rule(self, auth_headers, property_id):
        """POST /api/automation/rules - Create automation rule"""
        response = requests.post(
            f"{BASE_URL}/api/automation/rules",
            headers=auth_headers,
            json={
                "property_id": property_id,
                "name": "Test Rule Iteration39",
                "trigger": "pre_arrival",
                "timing_hours": -24,
                "channel": "email",
                "subject": "Test Subject",
                "message_template": "Hello {guest_name}, welcome!",
                "enabled": False
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["name"] == "Test Rule Iteration39"
        print(f"✓ Create automation rule: {data['id']}")
        return data["id"]
    
    def test_update_automation_rule(self, auth_headers, property_id):
        """PUT /api/automation/rules/{rule_id} - Update rule"""
        # First create a rule
        create_resp = requests.post(
            f"{BASE_URL}/api/automation/rules",
            headers=auth_headers,
            json={
                "property_id": property_id,
                "name": "Rule to Update Iteration39",
                "trigger": "day_of_arrival",
                "channel": "email",
                "message_template": "Original message",
                "enabled": False
            }
        )
        rule_id = create_resp.json()["id"]
        
        # Update it
        response = requests.put(
            f"{BASE_URL}/api/automation/rules/{rule_id}",
            headers=auth_headers,
            json={
                "name": "Updated Rule Iteration39",
                "message_template": "Updated message"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Rule Iteration39"
        print(f"✓ Update automation rule: {rule_id}")
    
    def test_toggle_automation_rule(self, auth_headers, property_id):
        """POST /api/automation/rules/{rule_id}/toggle - Toggle rule"""
        # Get existing rules
        rules = requests.get(
            f"{BASE_URL}/api/automation/rules/{property_id}",
            headers=auth_headers
        ).json()
        
        if rules:
            rule_id = rules[0]["id"]
            original_state = rules[0].get("enabled", True)
            
            response = requests.post(
                f"{BASE_URL}/api/automation/rules/{rule_id}/toggle",
                headers=auth_headers
            )
            assert response.status_code == 200
            data = response.json()
            assert "enabled" in data
            assert data["enabled"] != original_state
            print(f"✓ Toggle automation rule: {rule_id} -> enabled={data['enabled']}")
            
            # Toggle back
            requests.post(
                f"{BASE_URL}/api/automation/rules/{rule_id}/toggle",
                headers=auth_headers
            )
        else:
            pytest.skip("No rules to toggle")
    
    def test_delete_automation_rule(self, auth_headers, property_id):
        """DELETE /api/automation/rules/{rule_id} - Delete rule"""
        # Create a rule to delete
        create_resp = requests.post(
            f"{BASE_URL}/api/automation/rules",
            headers=auth_headers,
            json={
                "property_id": property_id,
                "name": "Rule to Delete Iteration39",
                "trigger": "post_checkout",
                "channel": "email",
                "message_template": "Delete me",
                "enabled": False
            }
        )
        rule_id = create_resp.json()["id"]
        
        response = requests.delete(
            f"{BASE_URL}/api/automation/rules/{rule_id}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "deleted"
        print(f"✓ Delete automation rule: {rule_id}")
    
    def test_run_automation(self, auth_headers, property_id):
        """POST /api/automation/run/{property_id} - Run automation"""
        response = requests.post(
            f"{BASE_URL}/api/automation/run/{property_id}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "sent" in data
        assert "results" in data
        print(f"✓ Run automation: {data['message']}")
    
    def test_automation_logs(self, auth_headers, property_id):
        """GET /api/automation/logs/{property_id} - Automation logs"""
        response = requests.get(
            f"{BASE_URL}/api/automation/logs/{property_id}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Automation logs: {len(data)} entries")
    
    def test_automation_stats(self, auth_headers, property_id):
        """GET /api/automation/stats/{property_id} - Automation stats"""
        response = requests.get(
            f"{BASE_URL}/api/automation/stats/{property_id}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "total_rules" in data
        assert "active_rules" in data
        assert "total_sent" in data
        assert "sent_today" in data
        assert "failed" in data
        assert "queued" in data
        assert "by_channel" in data
        assert "by_rule" in data
        print(f"✓ Automation stats: total_rules={data['total_rules']}, active={data['active_rules']}")
    
    def test_automation_preview(self, auth_headers, property_id):
        """POST /api/automation/preview - Preview automation template"""
        response = requests.post(
            f"{BASE_URL}/api/automation/preview",
            headers=auth_headers,
            json={
                "property_id": property_id,
                "message_template": "Hello {guest_name}, your booking {booking_ref} is confirmed for {check_in}."
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "preview" in data
        assert "John Smith" in data["preview"]
        assert "BK-2026-0412" in data["preview"]
        print(f"✓ Automation preview: {data['preview'][:60]}...")


class TestDashboardRoutes:
    """Tests for /api/dashboard/* and related routes extracted to routes/dashboard.py"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        token = response.json()["token"]
        return {"Authorization": f"Bearer {token}"}
    
    @pytest.fixture(scope="class")
    def property_id(self):
        return "myhotelbox-london"
    
    def test_dashboard_overview(self, auth_headers, property_id):
        """GET /api/dashboard/overview/{property_id} - Dashboard overview"""
        response = requests.get(
            f"{BASE_URL}/api/dashboard/overview/{property_id}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify all sections exist
        assert "bookings" in data
        assert "revenue" in data
        assert "messaging" in data
        assert "reviews" in data
        assert "automation" in data
        assert "recent" in data
        
        # Verify bookings section
        bookings = data["bookings"]
        assert "today_checkins" in bookings
        assert "today_checkouts" in bookings
        assert "current_guests" in bookings
        assert "tomorrow_checkins" in bookings
        assert "total" in bookings
        assert "total_rooms" in bookings
        assert "occupancy" in bookings
        
        # Verify revenue section
        revenue = data["revenue"]
        assert "month_total" in revenue
        assert "month_bookings" in revenue
        assert "week_total" in revenue
        assert "week_bookings" in revenue
        
        # Verify messaging section
        messaging = data["messaging"]
        assert "unread" in messaging
        assert "open" in messaging
        assert "total" in messaging
        
        # Verify reviews section
        reviews = data["reviews"]
        assert "total" in reviews
        assert "pending" in reviews
        assert "avg_rating" in reviews
        
        # Verify automation section
        automation = data["automation"]
        assert "sent_today" in automation
        assert "failed_today" in automation
        
        # Verify recent section
        recent = data["recent"]
        assert "bookings" in recent
        assert "messages" in recent
        assert "reviews" in recent
        
        print(f"✓ Dashboard overview: bookings={bookings['total']}, revenue_month={revenue['month_total']}")
    
    def test_dashboard_overview_all_properties(self, auth_headers):
        """GET /api/dashboard/overview/all - Dashboard overview for all properties"""
        response = requests.get(
            f"{BASE_URL}/api/dashboard/overview/all",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "bookings" in data
        assert "revenue" in data
        print(f"✓ Dashboard overview (all properties): total_bookings={data['bookings']['total']}")
    
    def test_concierge_analytics(self, auth_headers, property_id):
        """GET /api/concierge/analytics/{property_id} - Concierge analytics"""
        response = requests.get(
            f"{BASE_URL}/api/concierge/analytics/{property_id}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "total_sessions" in data
        assert "total_messages" in data
        assert "user_messages" in data
        assert "ai_messages" in data
        assert "recent_sessions" in data
        print(f"✓ Concierge analytics: sessions={data['total_sessions']}, messages={data['total_messages']}")
    
    def test_space_bookings_admin(self, auth_headers, property_id):
        """GET /api/spaces/admin/bookings/{property_id} - Space bookings admin"""
        response = requests.get(
            f"{BASE_URL}/api/spaces/admin/bookings/{property_id}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Space bookings admin: {len(data)} bookings")
    
    def test_space_booking_stats(self, auth_headers, property_id):
        """GET /api/spaces/admin/stats/{property_id} - Space booking stats"""
        response = requests.get(
            f"{BASE_URL}/api/spaces/admin/stats/{property_id}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "total_bookings" in data
        assert "confirmed" in data
        assert "today" in data
        assert "total_revenue" in data
        assert "total_hours" in data
        assert "spaces_count" in data
        print(f"✓ Space booking stats: total={data['total_bookings']}, revenue={data['total_revenue']}")


class TestAuthRequired:
    """Test that routes require authentication"""
    
    def test_messaging_requires_auth(self):
        """Messaging routes require authentication"""
        response = requests.get(f"{BASE_URL}/api/messaging/conversations/test")
        assert response.status_code == 401
        print("✓ Messaging routes require auth")
    
    def test_automation_requires_auth(self):
        """Automation routes require authentication"""
        response = requests.get(f"{BASE_URL}/api/automation/rules/test")
        assert response.status_code == 401
        print("✓ Automation routes require auth")
    
    def test_dashboard_requires_auth(self):
        """Dashboard routes require authentication"""
        response = requests.get(f"{BASE_URL}/api/dashboard/overview/test")
        assert response.status_code == 401
        print("✓ Dashboard routes require auth")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
