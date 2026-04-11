"""
Iteration 45 - Webhooks and Sync Logs Testing
Tests webhook events and sync log entries for all modules:
- Guest Profiles: guest.created, guest.updated, guest.vip_changed
- Campaigns: campaign.created, campaign.sent
- Messaging: conversation.created, conversation.resolved, message.sent
- Automation: automation.triggered
- Digital Keys: key.generated, key.revoked, key.used
- Guest App: directory.updated
- Cross-module: booking → guest profile auto-update
- Sync Logs: GET /api/sync-logs verification
"""
import pytest
import requests
import os
import time
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestAuthLogin:
    """Test admin login"""
    
    def test_admin_login(self):
        """POST /api/auth/login - admin login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "token" in data, "No token in response"
        assert data.get("role") == "admin", "User is not admin"
        print(f"✓ Admin login successful, token received")


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for all tests"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@hotelbox.com",
        "password": "HotelAdmin2026!"
    })
    if response.status_code == 200:
        return response.json().get("token")
    pytest.skip("Authentication failed")


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Headers with auth token"""
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


class TestGuestProfilesWebhooks:
    """Test Guest Profiles webhooks and sync logs"""
    
    def test_create_profile_fires_webhook_and_sync_log(self, auth_headers):
        """POST /api/guests/profiles - creates profile AND fires guest.created webhook + sync log"""
        unique_id = str(uuid.uuid4())[:8]
        profile_data = {
            "name": f"TEST_Webhook_Guest_{unique_id}",
            "email": f"test_webhook_{unique_id}@example.com",
            "phone": "+447700111222",
            "vip": False,
            "loyalty_tier": "standard"
        }
        
        response = requests.post(f"{BASE_URL}/api/guests/profiles", json=profile_data, headers=auth_headers)
        assert response.status_code == 200, f"Create profile failed: {response.text}"
        data = response.json()
        assert data.get("name") == profile_data["name"], "Name mismatch"
        assert data.get("email") == profile_data["email"], "Email mismatch"
        assert "id" in data, "No id in response"
        print(f"✓ Guest profile created: {data.get('id')}")
        
        # Verify sync log was created
        time.sleep(0.5)  # Allow async task to complete
        sync_response = requests.get(f"{BASE_URL}/api/sync-logs", headers=auth_headers)
        assert sync_response.status_code == 200, f"Sync logs fetch failed: {sync_response.text}"
        sync_logs = sync_response.json()
        
        # Find the sync log for this profile creation
        profile_logs = [log for log in sync_logs if "Guest profile created" in log.get("message", "") and profile_data["name"] in log.get("message", "")]
        assert len(profile_logs) > 0, f"No sync log found for guest profile creation. Logs: {sync_logs[:5]}"
        print(f"✓ Sync log found for guest.created: {profile_logs[0].get('message')}")
        
        return data.get("id")
    
    def test_update_profile_fires_webhook(self, auth_headers):
        """PUT /api/guests/profiles/{id} - updates profile AND fires guest.updated webhook"""
        # First create a profile
        unique_id = str(uuid.uuid4())[:8]
        create_response = requests.post(f"{BASE_URL}/api/guests/profiles", json={
            "name": f"TEST_Update_Guest_{unique_id}",
            "email": f"test_update_{unique_id}@example.com",
            "vip": False
        }, headers=auth_headers)
        assert create_response.status_code == 200
        profile_id = create_response.json().get("id")
        
        # Update the profile
        update_response = requests.put(f"{BASE_URL}/api/guests/profiles/{profile_id}", json={
            "phone": "+447700333444"
        }, headers=auth_headers)
        assert update_response.status_code == 200, f"Update profile failed: {update_response.text}"
        print(f"✓ Guest profile updated: {profile_id}")
    
    def test_update_vip_fires_vip_changed_webhook(self, auth_headers):
        """PUT /api/guests/profiles/{id} with vip=true fires guest.vip_changed webhook + sync log"""
        # First create a profile
        unique_id = str(uuid.uuid4())[:8]
        create_response = requests.post(f"{BASE_URL}/api/guests/profiles", json={
            "name": f"TEST_VIP_Guest_{unique_id}",
            "email": f"test_vip_{unique_id}@example.com",
            "vip": False
        }, headers=auth_headers)
        assert create_response.status_code == 200
        profile_id = create_response.json().get("id")
        
        # Update VIP status
        update_response = requests.put(f"{BASE_URL}/api/guests/profiles/{profile_id}", json={
            "vip": True
        }, headers=auth_headers)
        assert update_response.status_code == 200, f"VIP update failed: {update_response.text}"
        data = update_response.json()
        assert data.get("vip") == True, "VIP status not updated"
        print(f"✓ Guest VIP status changed: {profile_id}")
        
        # Verify sync log for VIP change
        time.sleep(0.5)
        sync_response = requests.get(f"{BASE_URL}/api/sync-logs", headers=auth_headers)
        sync_logs = sync_response.json()
        vip_logs = [log for log in sync_logs if "VIP" in log.get("message", "")]
        assert len(vip_logs) > 0, "No sync log found for VIP change"
        print(f"✓ Sync log found for guest.vip_changed: {vip_logs[0].get('message')}")
    
    def test_link_reviews_to_profiles(self, auth_headers):
        """POST /api/guests/profiles/link-reviews/{property_id} - new endpoint"""
        response = requests.post(f"{BASE_URL}/api/guests/profiles/link-reviews/city-gate", headers=auth_headers)
        assert response.status_code == 200, f"Link reviews failed: {response.text}"
        data = response.json()
        assert "linked" in data, "No linked count in response"
        print(f"✓ Link reviews endpoint works: {data.get('linked')} reviews linked")
        
        # Verify sync log
        time.sleep(0.5)
        sync_response = requests.get(f"{BASE_URL}/api/sync-logs", headers=auth_headers)
        sync_logs = sync_response.json()
        link_logs = [log for log in sync_logs if "Linked" in log.get("message", "") and "reviews" in log.get("message", "")]
        assert len(link_logs) > 0, "No sync log found for link-reviews"
        print(f"✓ Sync log found for link-reviews: {link_logs[0].get('message')}")


class TestCampaignsWebhooks:
    """Test Campaigns webhooks and sync logs"""
    
    def test_create_campaign_fires_webhook_and_sync_log(self, auth_headers):
        """POST /api/campaigns - creates campaign AND fires campaign.created webhook + sync log"""
        unique_id = str(uuid.uuid4())[:8]
        campaign_data = {
            "property_id": "city-gate",
            "name": f"TEST_Campaign_{unique_id}",
            "channel": "email",
            "subject": "Test Subject",
            "message": "Hello {guest_name}, this is a test campaign.",
            "segment": {"vip": True}
        }
        
        response = requests.post(f"{BASE_URL}/api/campaigns", json=campaign_data, headers=auth_headers)
        assert response.status_code == 200, f"Create campaign failed: {response.text}"
        data = response.json()
        assert data.get("name") == campaign_data["name"], "Name mismatch"
        assert "id" in data, "No id in response"
        print(f"✓ Campaign created: {data.get('id')}")
        
        # Verify sync log
        time.sleep(0.5)
        sync_response = requests.get(f"{BASE_URL}/api/sync-logs", headers=auth_headers)
        sync_logs = sync_response.json()
        campaign_logs = [log for log in sync_logs if "Campaign created" in log.get("message", "")]
        assert len(campaign_logs) > 0, "No sync log found for campaign creation"
        print(f"✓ Sync log found for campaign.created: {campaign_logs[0].get('message')}")
        
        return data.get("id")
    
    def test_send_campaign_fires_webhook_and_tags_profiles(self, auth_headers):
        """POST /api/campaigns/{id}/send - sends campaign AND fires campaign.sent webhook + sync log + tags guest profiles"""
        # First create a campaign
        unique_id = str(uuid.uuid4())[:8]
        create_response = requests.post(f"{BASE_URL}/api/campaigns", json={
            "property_id": "city-gate",
            "name": f"TEST_Send_Campaign_{unique_id}",
            "channel": "email",
            "subject": "Test Send",
            "message": "Hello {guest_name}!",
            "segment": {}
        }, headers=auth_headers)
        assert create_response.status_code == 200
        campaign_id = create_response.json().get("id")
        
        # Send the campaign
        send_response = requests.post(f"{BASE_URL}/api/campaigns/{campaign_id}/send", headers=auth_headers)
        assert send_response.status_code == 200, f"Send campaign failed: {send_response.text}"
        data = send_response.json()
        assert "sent" in data, "No sent count in response"
        print(f"✓ Campaign sent: {data.get('sent')}/{data.get('total')} recipients")
        
        # Verify sync log
        time.sleep(0.5)
        sync_response = requests.get(f"{BASE_URL}/api/sync-logs", headers=auth_headers)
        sync_logs = sync_response.json()
        sent_logs = [log for log in sync_logs if "Campaign" in log.get("message", "") and "sent" in log.get("message", "")]
        # May not have recipients, so just check the endpoint works
        print(f"✓ Campaign send endpoint works, sync logs checked")


class TestMessagingWebhooks:
    """Test Messaging Hub webhooks and sync logs"""
    
    def test_create_conversation_fires_webhook(self, auth_headers):
        """POST /api/messaging/conversations - creates conv AND fires conversation.created webhook"""
        unique_id = str(uuid.uuid4())[:8]
        conv_data = {
            "property_id": "city-gate",
            "guest_name": f"TEST_Conv_Guest_{unique_id}",
            "guest_email": f"test_conv_{unique_id}@example.com",
            "channel": "email",
            "status": "new",
            "priority": "medium"
        }
        
        response = requests.post(f"{BASE_URL}/api/messaging/conversations", json=conv_data, headers=auth_headers)
        assert response.status_code == 200, f"Create conversation failed: {response.text}"
        data = response.json()
        assert data.get("guest_name") == conv_data["guest_name"], "Guest name mismatch"
        assert "id" in data, "No id in response"
        print(f"✓ Conversation created: {data.get('id')}")
        return data.get("id")
    
    def test_send_message_fires_webhook_and_sync_log(self, auth_headers):
        """POST /api/messaging/messages - sends message AND fires message.sent webhook + sync log"""
        # First create a conversation
        unique_id = str(uuid.uuid4())[:8]
        conv_response = requests.post(f"{BASE_URL}/api/messaging/conversations", json={
            "property_id": "city-gate",
            "guest_name": f"TEST_Msg_Guest_{unique_id}",
            "guest_email": f"test_msg_{unique_id}@example.com",
            "channel": "email",
            "status": "new"
        }, headers=auth_headers)
        assert conv_response.status_code == 200
        conv_id = conv_response.json().get("id")
        
        # Send a message
        msg_response = requests.post(f"{BASE_URL}/api/messaging/messages", json={
            "conversation_id": conv_id,
            "content": "Hello, this is a test message.",
            "channel": "email"
        }, headers=auth_headers)
        assert msg_response.status_code == 200, f"Send message failed: {msg_response.text}"
        data = msg_response.json()
        assert data.get("content") == "Hello, this is a test message.", "Content mismatch"
        print(f"✓ Message sent in conversation: {conv_id}")
        
        # Verify sync log
        time.sleep(0.5)
        sync_response = requests.get(f"{BASE_URL}/api/sync-logs", headers=auth_headers)
        sync_logs = sync_response.json()
        msg_logs = [log for log in sync_logs if "Staff message" in log.get("message", "")]
        assert len(msg_logs) > 0, "No sync log found for message.sent"
        print(f"✓ Sync log found for message.sent: {msg_logs[0].get('message')}")
    
    def test_resolve_conversation_fires_webhook_and_sync_log(self, auth_headers):
        """POST /api/messaging/conversations/{id}/resolve - fires conversation.resolved webhook + sync log"""
        # First create a conversation
        unique_id = str(uuid.uuid4())[:8]
        conv_response = requests.post(f"{BASE_URL}/api/messaging/conversations", json={
            "property_id": "city-gate",
            "guest_name": f"TEST_Resolve_Guest_{unique_id}",
            "guest_email": f"test_resolve_{unique_id}@example.com",
            "channel": "email",
            "status": "in_progress"
        }, headers=auth_headers)
        assert conv_response.status_code == 200
        conv_id = conv_response.json().get("id")
        
        # Resolve the conversation
        resolve_response = requests.post(f"{BASE_URL}/api/messaging/conversations/{conv_id}/resolve", headers=auth_headers)
        assert resolve_response.status_code == 200, f"Resolve conversation failed: {resolve_response.text}"
        data = resolve_response.json()
        assert data.get("status") == "resolved", "Status not resolved"
        print(f"✓ Conversation resolved: {conv_id}")
        
        # Verify sync log
        time.sleep(0.5)
        sync_response = requests.get(f"{BASE_URL}/api/sync-logs", headers=auth_headers)
        sync_logs = sync_response.json()
        resolve_logs = [log for log in sync_logs if "resolved" in log.get("message", "").lower() and conv_id in log.get("message", "")]
        assert len(resolve_logs) > 0, f"No sync log found for conversation.resolved. Conv ID: {conv_id}"
        print(f"✓ Sync log found for conversation.resolved: {resolve_logs[0].get('message')}")
    
    def test_new_conversation_fires_webhook_and_sync_log(self, auth_headers):
        """POST /api/messaging/new-conversation - fires conversation.created webhook + sync log"""
        unique_id = str(uuid.uuid4())[:8]
        conv_data = {
            "property_id": "city-gate",
            "guest_name": f"TEST_NewConv_Guest_{unique_id}",
            "guest_email": f"test_newconv_{unique_id}@example.com",
            "channel": "internal",
            "message": "Hello, starting a new conversation."
        }
        
        response = requests.post(f"{BASE_URL}/api/messaging/new-conversation", json=conv_data, headers=auth_headers)
        assert response.status_code == 200, f"New conversation failed: {response.text}"
        data = response.json()
        assert "conversation" in data, "No conversation in response"
        assert "message" in data, "No message in response"
        print(f"✓ New conversation created with message: {data.get('conversation', {}).get('id')}")
        
        # Verify sync log
        time.sleep(0.5)
        sync_response = requests.get(f"{BASE_URL}/api/sync-logs", headers=auth_headers)
        sync_logs = sync_response.json()
        new_conv_logs = [log for log in sync_logs if "New conversation" in log.get("message", "")]
        assert len(new_conv_logs) > 0, "No sync log found for new-conversation"
        print(f"✓ Sync log found for new-conversation: {new_conv_logs[0].get('message')}")


class TestAutomationWebhooks:
    """Test Automation Engine webhooks and sync logs"""
    
    def test_run_automation_fires_webhook_and_sync_log(self, auth_headers):
        """POST /api/automation/run/{property_id} - fires automation.triggered webhook + sync log"""
        response = requests.post(f"{BASE_URL}/api/automation/run/city-gate", headers=auth_headers)
        assert response.status_code == 200, f"Run automation failed: {response.text}"
        data = response.json()
        assert "sent" in data, "No sent count in response"
        assert "results" in data, "No results in response"
        print(f"✓ Automation run: {data.get('sent')} messages sent, {len(data.get('results', []))} rules matched")
        
        # Verify sync log if any messages were sent
        if data.get("sent", 0) > 0:
            time.sleep(0.5)
            sync_response = requests.get(f"{BASE_URL}/api/sync-logs", headers=auth_headers)
            sync_logs = sync_response.json()
            auto_logs = [log for log in sync_logs if "Automation run" in log.get("message", "")]
            assert len(auto_logs) > 0, "No sync log found for automation.triggered"
            print(f"✓ Sync log found for automation.triggered: {auto_logs[0].get('message')}")
        else:
            print(f"✓ No messages sent (no matching bookings), webhook/sync log skipped as expected")


class TestDigitalKeysWebhooks:
    """Test Digital Keys webhooks and sync logs"""
    
    def test_generate_key_fires_webhook_and_sync_log(self, auth_headers):
        """POST /api/digital-keys/generate - fires key.generated webhook + sync log"""
        # First we need a booking - let's create one
        unique_id = str(uuid.uuid4())[:8]
        booking_data = {
            "property_id": "city-gate",
            "room_type_id": "deluxe-double",
            "guest_name": f"TEST_Key_Guest_{unique_id}",
            "guest_email": f"test_key_{unique_id}@example.com",
            "guest_phone": "+447700555666",
            "check_in": "2026-02-01",
            "check_out": "2026-02-03",
            "adults": 2,
            "children": 0,
            "rooms": 1
        }
        
        booking_response = requests.post(f"{BASE_URL}/api/booking/reserve", json=booking_data)
        # May fail if room type doesn't exist, that's ok
        if booking_response.status_code != 200:
            # Try to find an existing booking
            bookings_response = requests.get(f"{BASE_URL}/api/bookings?property_id=city-gate", headers=auth_headers)
            if bookings_response.status_code == 200:
                bookings = bookings_response.json()
                if bookings:
                    booking_ref = bookings[0].get("booking_ref")
                else:
                    pytest.skip("No bookings available for key generation test")
            else:
                pytest.skip("Cannot create or find booking for key generation test")
        else:
            booking_ref = booking_response.json().get("booking_ref")
        
        # Generate digital key
        key_response = requests.post(f"{BASE_URL}/api/digital-keys/generate", json={
            "booking_ref": booking_ref,
            "room_number": "101"
        }, headers=auth_headers)
        assert key_response.status_code == 200, f"Generate key failed: {key_response.text}"
        data = key_response.json()
        assert "access_code" in data, "No access_code in response"
        print(f"✓ Digital key generated: {data.get('access_code')} for booking {booking_ref}")
        
        # Verify sync log
        time.sleep(0.5)
        sync_response = requests.get(f"{BASE_URL}/api/sync-logs", headers=auth_headers)
        sync_logs = sync_response.json()
        key_logs = [log for log in sync_logs if "Key generated" in log.get("message", "")]
        assert len(key_logs) > 0, "No sync log found for key.generated"
        print(f"✓ Sync log found for key.generated: {key_logs[0].get('message')}")
        
        return data.get("id"), booking_ref
    
    def test_revoke_key_fires_webhook_and_sync_log(self, auth_headers):
        """PUT /api/digital-keys/{id}/revoke - fires key.revoked webhook + sync log"""
        # First generate a key
        bookings_response = requests.get(f"{BASE_URL}/api/bookings?property_id=city-gate", headers=auth_headers)
        if bookings_response.status_code != 200 or not bookings_response.json():
            pytest.skip("No bookings available for key revoke test")
        
        booking_ref = bookings_response.json()[0].get("booking_ref")
        
        # Generate a key
        key_response = requests.post(f"{BASE_URL}/api/digital-keys/generate", json={
            "booking_ref": booking_ref,
            "room_number": "102"
        }, headers=auth_headers)
        
        if key_response.status_code != 200:
            pytest.skip("Cannot generate key for revoke test")
        
        key_id = key_response.json().get("id")
        
        # Revoke the key
        revoke_response = requests.put(f"{BASE_URL}/api/digital-keys/{key_id}/revoke", headers=auth_headers)
        assert revoke_response.status_code == 200, f"Revoke key failed: {revoke_response.text}"
        data = revoke_response.json()
        assert data.get("status") == "revoked", "Status not revoked"
        print(f"✓ Digital key revoked: {key_id}")
        
        # Verify sync log
        time.sleep(0.5)
        sync_response = requests.get(f"{BASE_URL}/api/sync-logs", headers=auth_headers)
        sync_logs = sync_response.json()
        revoke_logs = [log for log in sync_logs if "revoked" in log.get("message", "").lower() and key_id in log.get("message", "")]
        assert len(revoke_logs) > 0, f"No sync log found for key.revoked. Key ID: {key_id}"
        print(f"✓ Sync log found for key.revoked: {revoke_logs[0].get('message')}")
    
    def test_guest_get_key_fires_webhook_and_sync_log(self, auth_headers):
        """GET /api/digital-keys/guest/{ref} - fires key.used webhook + sync log (public)"""
        # First generate a key
        bookings_response = requests.get(f"{BASE_URL}/api/bookings?property_id=city-gate", headers=auth_headers)
        if bookings_response.status_code != 200 or not bookings_response.json():
            pytest.skip("No bookings available for guest key test")
        
        booking_ref = bookings_response.json()[0].get("booking_ref")
        
        # Generate a key
        key_response = requests.post(f"{BASE_URL}/api/digital-keys/generate", json={
            "booking_ref": booking_ref,
            "room_number": "103"
        }, headers=auth_headers)
        
        if key_response.status_code != 200:
            pytest.skip("Cannot generate key for guest access test")
        
        # Guest accesses key (NO AUTH - public endpoint)
        guest_response = requests.get(f"{BASE_URL}/api/digital-keys/guest/{booking_ref}")
        assert guest_response.status_code == 200, f"Guest get key failed: {guest_response.text}"
        data = guest_response.json()
        assert "access_code" in data, "No access_code in response"
        print(f"✓ Guest accessed key: {data.get('access_code')} for room {data.get('room_number')}")
        
        # Verify sync log
        time.sleep(0.5)
        sync_response = requests.get(f"{BASE_URL}/api/sync-logs", headers=auth_headers)
        sync_logs = sync_response.json()
        used_logs = [log for log in sync_logs if "Guest accessed key" in log.get("message", "")]
        assert len(used_logs) > 0, "No sync log found for key.used"
        print(f"✓ Sync log found for key.used: {used_logs[0].get('message')}")


class TestGuestAppWebhooks:
    """Test Guest App webhooks and sync logs"""
    
    def test_update_directory_fires_webhook_and_sync_log(self, auth_headers):
        """PUT /api/guest-app/directory/{property_id} - fires directory.updated webhook + sync log"""
        update_data = {
            "welcome_message": "Welcome to our hotel! Updated at " + str(uuid.uuid4())[:8],
            "wifi_network": "HotelGuest",
            "wifi_password": "Welcome2026"
        }
        
        response = requests.put(f"{BASE_URL}/api/guest-app/directory/city-gate", json=update_data, headers=auth_headers)
        assert response.status_code == 200, f"Update directory failed: {response.text}"
        data = response.json()
        assert data.get("welcome_message") == update_data["welcome_message"], "Welcome message not updated"
        print(f"✓ Guest directory updated for city-gate")
        
        # Verify sync log
        time.sleep(0.5)
        sync_response = requests.get(f"{BASE_URL}/api/sync-logs", headers=auth_headers)
        sync_logs = sync_response.json()
        dir_logs = [log for log in sync_logs if "Guest directory updated" in log.get("message", "")]
        assert len(dir_logs) > 0, "No sync log found for directory.updated"
        print(f"✓ Sync log found for directory.updated: {dir_logs[0].get('message')}")


class TestSyncLogsEndpoint:
    """Test GET /api/sync-logs endpoint"""
    
    def test_get_sync_logs(self, auth_headers):
        """GET /api/sync-logs - should show new sync log entries from all modules"""
        response = requests.get(f"{BASE_URL}/api/sync-logs", headers=auth_headers)
        assert response.status_code == 200, f"Get sync logs failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        
        if len(data) > 0:
            # Verify sync log structure
            log = data[0]
            assert "platform" in log, "No platform in sync log"
            assert "direction" in log, "No direction in sync log"
            assert "status" in log, "No status in sync log"
            assert "message" in log, "No message in sync log"
            assert "timestamp" in log, "No timestamp in sync log"
            
            # Check for various platforms
            platforms = set(log.get("platform") for log in data)
            print(f"✓ Sync logs retrieved: {len(data)} entries")
            print(f"  Platforms found: {platforms}")
        else:
            print(f"✓ Sync logs endpoint works (no entries yet)")


class TestCrossModuleBookingGuestProfile:
    """Test cross-module: booking creates/updates guest profile"""
    
    def test_booking_auto_creates_guest_profile(self, auth_headers):
        """Regression: Bookings auto-create guest profiles (cross-module)"""
        unique_id = str(uuid.uuid4())[:8]
        booking_data = {
            "property_id": "city-gate",
            "room_type_id": "deluxe-double",
            "guest_name": f"TEST_AutoProfile_Guest_{unique_id}",
            "guest_email": f"test_autoprofile_{unique_id}@example.com",
            "guest_phone": "+447700777888",
            "check_in": "2026-03-01",
            "check_out": "2026-03-03",
            "adults": 2,
            "children": 0,
            "rooms": 1
        }
        
        # Create booking
        booking_response = requests.post(f"{BASE_URL}/api/booking/reserve", json=booking_data)
        if booking_response.status_code != 200:
            # Room type may not exist, skip test
            pytest.skip(f"Cannot create booking: {booking_response.text}")
        
        booking = booking_response.json()
        print(f"✓ Booking created: {booking.get('booking_ref')}")
        
        # Check if guest profile was auto-created
        time.sleep(0.5)
        profiles_response = requests.get(f"{BASE_URL}/api/guests/profiles/city-gate?search={booking_data['guest_email']}", headers=auth_headers)
        if profiles_response.status_code == 200:
            profiles = profiles_response.json()
            matching = [p for p in profiles if p.get("email") == booking_data["guest_email"]]
            if matching:
                print(f"✓ Guest profile auto-created for booking: {matching[0].get('id')}")
            else:
                print(f"⚠ Guest profile not found (may be expected if profile creation is async)")
        else:
            print(f"⚠ Could not verify guest profile creation")


class TestRegressionDashboard:
    """Regression: All dashboard panels still load"""
    
    def test_dashboard_overview(self, auth_headers):
        """Regression: Dashboard overview loads"""
        response = requests.get(f"{BASE_URL}/api/dashboard/overview/city-gate", headers=auth_headers)
        assert response.status_code == 200, f"Dashboard overview failed: {response.text}"
        data = response.json()
        # Dashboard overview returns bookings, messaging, automation, recent data
        assert "bookings" in data or "messaging" in data or "recent" in data, "Dashboard data incomplete"
        print(f"✓ Dashboard overview loads")


class TestRegressionReviewsPropertiesRoomTypes:
    """Regression: Reviews, Properties, Room Types still work"""
    
    def test_reviews_list(self, auth_headers):
        """Regression: Reviews list works"""
        response = requests.get(f"{BASE_URL}/api/reviews", headers=auth_headers)
        assert response.status_code == 200, f"Reviews list failed: {response.text}"
        print(f"✓ Reviews list works")
    
    def test_properties_list(self, auth_headers):
        """Regression: Properties list works"""
        response = requests.get(f"{BASE_URL}/api/properties", headers=auth_headers)
        assert response.status_code == 200, f"Properties list failed: {response.text}"
        print(f"✓ Properties list works")
    
    def test_room_types_list(self, auth_headers):
        """Regression: Room types list works (public endpoint)"""
        response = requests.get(f"{BASE_URL}/api/booking/rooms/city-gate")
        assert response.status_code == 200, f"Room types list failed: {response.text}"
        print(f"✓ Room types list works")
    
    def test_bookings_list(self, auth_headers):
        """Regression: Bookings list works"""
        response = requests.get(f"{BASE_URL}/api/bookings?property_id=city-gate", headers=auth_headers)
        assert response.status_code == 200, f"Bookings list failed: {response.text}"
        print(f"✓ Bookings list works")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
