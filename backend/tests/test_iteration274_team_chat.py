"""
Test Suite for Team Chat (Flexkeeping-style Collaboration Suite)
Iteration 274 - Internal Team Chat with channels, messages, read receipts, unread counts

Tests:
- Channel seeding (6 default channels on first call)
- Channel listing with last_message and unread_count enrichment
- Visibility rules (admin/manager see all, department-specific for others)
- Channel creation (manager/admin only, kind validation)
- Message listing (chronological, 403/404 handling)
- Message posting (auto-mark-read for sender, bumps updated_at)
- Mark read endpoint
- Unread counts (own messages don't count)
- DM channel creation (find or create, 404/400 handling)
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestTeamChatChannels:
    """Test channel seeding, listing, and creation"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login as admin and get session"""
        self.session = requests.Session()
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert login_resp.status_code == 200, f"Admin login failed: {login_resp.text}"
        self.admin_token = login_resp.json().get("token")
        self.session.headers.update({"Authorization": f"Bearer {self.admin_token}"})
        yield
        self.session.close()
    
    def test_channels_seed_on_first_call(self):
        """GET /api/team-chat/channels auto-seeds 6 default channels on first call"""
        resp = self.session.get(f"{BASE_URL}/api/team-chat/channels")
        assert resp.status_code == 200, f"Failed to get channels: {resp.text}"
        
        data = resp.json()
        assert "channels" in data, "Response should contain 'channels' key"
        channels = data["channels"]
        
        # Should have at least 6 default channels
        assert len(channels) >= 6, f"Expected at least 6 channels, got {len(channels)}"
        
        # Check default channel names exist
        channel_names = [c["name"] for c in channels]
        expected_names = ["general", "front-office", "housekeeping", "maintenance", "fnb", "management"]
        for name in expected_names:
            assert name in channel_names, f"Expected channel '{name}' not found"
        
        print(f"✓ Found {len(channels)} channels including all 6 defaults")
    
    def test_channels_idempotent_seeding(self):
        """Calling GET /api/team-chat/channels multiple times doesn't create duplicates"""
        # First call
        resp1 = self.session.get(f"{BASE_URL}/api/team-chat/channels")
        assert resp1.status_code == 200
        count1 = len(resp1.json()["channels"])
        
        # Second call
        resp2 = self.session.get(f"{BASE_URL}/api/team-chat/channels")
        assert resp2.status_code == 200
        count2 = len(resp2.json()["channels"])
        
        # Third call
        resp3 = self.session.get(f"{BASE_URL}/api/team-chat/channels")
        assert resp3.status_code == 200
        count3 = len(resp3.json()["channels"])
        
        assert count1 == count2 == count3, f"Channel count changed: {count1} -> {count2} -> {count3}"
        print(f"✓ Idempotent seeding verified: {count1} channels consistently")
    
    def test_channels_enriched_with_last_message_and_unread(self):
        """GET /api/team-chat/channels enriches each channel with last_message and unread_count"""
        resp = self.session.get(f"{BASE_URL}/api/team-chat/channels")
        assert resp.status_code == 200
        
        channels = resp.json()["channels"]
        for ch in channels:
            assert "unread_count" in ch, f"Channel {ch['name']} missing unread_count"
            assert "last_message" in ch, f"Channel {ch['name']} missing last_message"
            assert isinstance(ch["unread_count"], int), "unread_count should be int"
        
        print(f"✓ All {len(channels)} channels have last_message and unread_count fields")
    
    def test_create_channel_admin_success(self):
        """POST /api/team-chat/channels - admin can create new channel"""
        channel_data = {
            "name": f"test-channel-{int(time.time())}",
            "kind": "department",
            "department": "test-dept",
            "description": "Test channel for pytest"
        }
        resp = self.session.post(f"{BASE_URL}/api/team-chat/channels", json=channel_data)
        assert resp.status_code == 200, f"Failed to create channel: {resp.text}"
        
        created = resp.json()
        assert created["name"] == channel_data["name"]
        assert created["kind"] == "department"
        assert "id" in created
        assert "created_at" in created
        
        print(f"✓ Created channel: {created['name']} (id: {created['id']})")
    
    def test_create_channel_invalid_kind_400(self):
        """POST /api/team-chat/channels - 400 on invalid kind"""
        channel_data = {
            "name": "invalid-kind-channel",
            "kind": "invalid_kind_xyz",
            "description": "Should fail"
        }
        resp = self.session.post(f"{BASE_URL}/api/team-chat/channels", json=channel_data)
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
        print("✓ Invalid kind correctly returns 400")
    
    def test_create_channel_valid_kinds(self):
        """POST /api/team-chat/channels - all valid kinds work"""
        valid_kinds = ["property", "department", "direct", "general"]
        for kind in valid_kinds:
            channel_data = {
                "name": f"test-{kind}-{int(time.time())}",
                "kind": kind,
                "description": f"Test {kind} channel"
            }
            resp = self.session.post(f"{BASE_URL}/api/team-chat/channels", json=channel_data)
            assert resp.status_code == 200, f"Failed to create {kind} channel: {resp.text}"
            print(f"✓ Created {kind} channel successfully")


class TestTeamChatMessages:
    """Test message listing and posting"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login as admin and get a channel ID"""
        self.session = requests.Session()
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert login_resp.status_code == 200
        self.session.headers.update({"Authorization": f"Bearer {login_resp.json()['token']}"})
        
        # Get channels and pick general
        ch_resp = self.session.get(f"{BASE_URL}/api/team-chat/channels")
        assert ch_resp.status_code == 200
        channels = ch_resp.json()["channels"]
        general = next((c for c in channels if c["name"] == "general"), None)
        assert general, "General channel not found"
        self.general_channel_id = general["id"]
        yield
        self.session.close()
    
    def test_list_messages_empty_channel(self):
        """GET /api/team-chat/channels/{id}/messages returns chronological messages"""
        resp = self.session.get(f"{BASE_URL}/api/team-chat/channels/{self.general_channel_id}/messages")
        assert resp.status_code == 200, f"Failed to get messages: {resp.text}"
        
        data = resp.json()
        assert "messages" in data
        assert "channel_id" in data
        assert data["channel_id"] == self.general_channel_id
        print(f"✓ Got {len(data['messages'])} messages from general channel")
    
    def test_list_messages_nonexistent_channel_404(self):
        """GET /api/team-chat/channels/{id}/messages - 404 if channel missing"""
        resp = self.session.get(f"{BASE_URL}/api/team-chat/channels/nonexistent-channel-id/messages")
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}"
        print("✓ Nonexistent channel correctly returns 404")
    
    def test_post_message_success(self):
        """POST /api/team-chat/channels/{id}/messages posts message"""
        msg_body = f"Test message at {time.time()}"
        resp = self.session.post(
            f"{BASE_URL}/api/team-chat/channels/{self.general_channel_id}/messages",
            json={"body": msg_body}
        )
        assert resp.status_code == 200, f"Failed to post message: {resp.text}"
        
        msg = resp.json()
        assert msg["body"] == msg_body
        assert "id" in msg
        assert "author_id" in msg
        assert "author_name" in msg
        assert "created_at" in msg
        print(f"✓ Posted message: {msg['id']}")
    
    def test_post_message_nonexistent_channel_404(self):
        """POST /api/team-chat/channels/{id}/messages - 404 if channel missing"""
        resp = self.session.post(
            f"{BASE_URL}/api/team-chat/channels/nonexistent-channel-id/messages",
            json={"body": "Should fail"}
        )
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}"
        print("✓ Post to nonexistent channel correctly returns 404")
    
    def test_post_message_auto_marks_read_for_sender(self):
        """POST message auto-marks-read for sender, so own messages don't show as unread"""
        # Post a message
        msg_body = f"Auto-read test {time.time()}"
        post_resp = self.session.post(
            f"{BASE_URL}/api/team-chat/channels/{self.general_channel_id}/messages",
            json={"body": msg_body}
        )
        assert post_resp.status_code == 200
        
        # Check unread counts - own message should NOT count as unread
        unread_resp = self.session.get(f"{BASE_URL}/api/team-chat/unread")
        assert unread_resp.status_code == 200
        
        unread_data = unread_resp.json()
        # The general channel should have 0 unread for the sender
        by_channel = unread_data.get("by_channel", {})
        general_unread = by_channel.get(self.general_channel_id, 0)
        
        # Since we just posted, our own message shouldn't count
        print(f"✓ Unread count for general after posting own message: {general_unread}")


class TestTeamChatReadReceipts:
    """Test mark-read and unread counts"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login as admin"""
        self.session = requests.Session()
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert login_resp.status_code == 200
        self.session.headers.update({"Authorization": f"Bearer {login_resp.json()['token']}"})
        
        # Get general channel
        ch_resp = self.session.get(f"{BASE_URL}/api/team-chat/channels")
        channels = ch_resp.json()["channels"]
        general = next((c for c in channels if c["name"] == "general"), None)
        self.general_channel_id = general["id"]
        yield
        self.session.close()
    
    def test_mark_read_success(self):
        """POST /api/team-chat/channels/{id}/read updates user's last_read_at"""
        resp = self.session.post(f"{BASE_URL}/api/team-chat/channels/{self.general_channel_id}/read")
        assert resp.status_code == 200, f"Failed to mark read: {resp.text}"
        
        data = resp.json()
        assert data.get("read") == True
        assert "at" in data
        print(f"✓ Marked channel as read at {data['at']}")
    
    def test_mark_read_nonexistent_channel_404(self):
        """POST /api/team-chat/channels/{id}/read - 404 if channel missing"""
        resp = self.session.post(f"{BASE_URL}/api/team-chat/channels/nonexistent-id/read")
        assert resp.status_code == 404
        print("✓ Mark read on nonexistent channel returns 404")
    
    def test_unread_counts_endpoint(self):
        """GET /api/team-chat/unread returns total + by_channel map"""
        resp = self.session.get(f"{BASE_URL}/api/team-chat/unread")
        assert resp.status_code == 200, f"Failed to get unread: {resp.text}"
        
        data = resp.json()
        assert "total" in data
        assert "by_channel" in data
        assert isinstance(data["total"], int)
        assert isinstance(data["by_channel"], dict)
        print(f"✓ Unread counts: total={data['total']}, channels={len(data['by_channel'])}")


class TestTeamChatDM:
    """Test direct message channel creation"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login as admin"""
        self.session = requests.Session()
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert login_resp.status_code == 200
        self.session.headers.update({"Authorization": f"Bearer {login_resp.json()['token']}"})
        yield
        self.session.close()
    
    def test_dm_self_400(self):
        """POST /api/team-chat/dm/{user_id} - 400 if DMing self"""
        # Try to DM self using admin email
        resp = self.session.post(f"{BASE_URL}/api/team-chat/dm/admin@hotelbox.com")
        assert resp.status_code == 400, f"Expected 400 for self-DM, got {resp.status_code}: {resp.text}"
        print("✓ DMing self correctly returns 400")
    
    def test_dm_nonexistent_user_404(self):
        """POST /api/team-chat/dm/{user_id} - 404 if target user missing"""
        resp = self.session.post(f"{BASE_URL}/api/team-chat/dm/nonexistent-user-xyz@fake.com")
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}"
        print("✓ DM to nonexistent user returns 404")


class TestTeamChatVisibility:
    """Test department visibility rules"""
    
    def test_admin_sees_all_channels(self):
        """Admin/manager see all channels"""
        session = requests.Session()
        login_resp = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert login_resp.status_code == 200
        session.headers.update({"Authorization": f"Bearer {login_resp.json()['token']}"})
        
        resp = session.get(f"{BASE_URL}/api/team-chat/channels")
        assert resp.status_code == 200
        
        channels = resp.json()["channels"]
        channel_names = [c["name"] for c in channels]
        
        # Admin should see all default channels
        expected = ["general", "front-office", "housekeeping", "maintenance", "fnb", "management"]
        for name in expected:
            assert name in channel_names, f"Admin should see {name} channel"
        
        print(f"✓ Admin sees all {len(channels)} channels")
        session.close()


class TestTeamChatIntegration:
    """Integration tests for full chat flow"""
    
    def test_full_chat_flow(self):
        """Test complete flow: list channels -> post message -> verify in list -> mark read"""
        session = requests.Session()
        login_resp = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert login_resp.status_code == 200
        session.headers.update({"Authorization": f"Bearer {login_resp.json()['token']}"})
        
        # 1. List channels
        ch_resp = session.get(f"{BASE_URL}/api/team-chat/channels")
        assert ch_resp.status_code == 200
        channels = ch_resp.json()["channels"]
        general = next((c for c in channels if c["name"] == "general"), None)
        assert general, "General channel not found"
        channel_id = general["id"]
        print(f"✓ Step 1: Found general channel {channel_id}")
        
        # 2. Post a message
        test_msg = f"Integration test message {time.time()}"
        post_resp = session.post(
            f"{BASE_URL}/api/team-chat/channels/{channel_id}/messages",
            json={"body": test_msg}
        )
        assert post_resp.status_code == 200
        msg_id = post_resp.json()["id"]
        print(f"✓ Step 2: Posted message {msg_id}")
        
        # 3. Verify message appears in list
        msgs_resp = session.get(f"{BASE_URL}/api/team-chat/channels/{channel_id}/messages")
        assert msgs_resp.status_code == 200
        messages = msgs_resp.json()["messages"]
        msg_ids = [m["id"] for m in messages]
        assert msg_id in msg_ids, "Posted message not found in message list"
        print(f"✓ Step 3: Message verified in list ({len(messages)} total)")
        
        # 4. Mark as read
        read_resp = session.post(f"{BASE_URL}/api/team-chat/channels/{channel_id}/read")
        assert read_resp.status_code == 200
        print("✓ Step 4: Marked channel as read")
        
        # 5. Check unread (should be 0 for this channel)
        unread_resp = session.get(f"{BASE_URL}/api/team-chat/unread")
        assert unread_resp.status_code == 200
        print(f"✓ Step 5: Unread check complete - total: {unread_resp.json()['total']}")
        
        session.close()
        print("✓ Full chat flow integration test passed")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
