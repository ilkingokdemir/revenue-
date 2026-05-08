"""
Iteration 62 - Payment Reminders Feature Tests
Tests for automated payment reminder system:
- GET /api/guest-payment/reminder-settings/{property_id} - Get reminder settings
- PUT /api/guest-payment/reminder-settings/{property_id} - Update reminder settings
- POST /api/guest-payment/send-reminders/{property_id} - Send reminders to unpaid bookings
- GET /api/guest-payment/reminder-history/{property_id} - Get reminder history
"""
import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
PROPERTY_ID = "aldgate-flats"

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
    """Get headers with auth token"""
    return {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json"
    }


class TestReminderSettings:
    """Tests for reminder settings endpoints"""
    
    def test_get_reminder_settings_returns_defaults(self, auth_headers):
        """GET /api/guest-payment/reminder-settings/{property_id} returns default settings"""
        response = requests.get(
            f"{BASE_URL}/api/guest-payment/reminder-settings/{PROPERTY_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Verify default settings structure
        assert "enabled" in data, "Missing 'enabled' field"
        assert "first_reminder_hours" in data, "Missing 'first_reminder_hours' field"
        assert "second_reminder_hours" in data, "Missing 'second_reminder_hours' field"
        assert "max_reminders_per_booking" in data, "Missing 'max_reminders_per_booking' field"
        assert "property_id" in data, "Missing 'property_id' field"
        
        # Verify default values
        assert data["property_id"] == PROPERTY_ID
        assert isinstance(data["enabled"], bool)
        assert isinstance(data["first_reminder_hours"], int)
        assert isinstance(data["second_reminder_hours"], int)
        assert isinstance(data["max_reminders_per_booking"], int)
        print(f"✓ Reminder settings retrieved: enabled={data['enabled']}, first={data['first_reminder_hours']}h, second={data['second_reminder_hours']}h, max={data['max_reminders_per_booking']}")
    
    def test_get_reminder_settings_unauthorized(self):
        """GET /api/guest-payment/reminder-settings/{property_id} requires auth"""
        response = requests.get(
            f"{BASE_URL}/api/guest-payment/reminder-settings/{PROPERTY_ID}"
        )
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ Unauthorized access correctly rejected")
    
    def test_update_reminder_settings(self, auth_headers):
        """PUT /api/guest-payment/reminder-settings/{property_id} updates settings"""
        # Update settings
        update_data = {
            "enabled": True,
            "first_reminder_hours": 48,
            "second_reminder_hours": 12,
            "max_reminders_per_booking": 2,
            "send_to_unpaid_bookings": True
        }
        
        response = requests.put(
            f"{BASE_URL}/api/guest-payment/reminder-settings/{PROPERTY_ID}",
            headers=auth_headers,
            json=update_data
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["first_reminder_hours"] == 48, f"Expected first_reminder_hours=48, got {data['first_reminder_hours']}"
        assert data["second_reminder_hours"] == 12, f"Expected second_reminder_hours=12, got {data['second_reminder_hours']}"
        assert data["max_reminders_per_booking"] == 2, f"Expected max_reminders_per_booking=2, got {data['max_reminders_per_booking']}"
        print(f"✓ Settings updated: first={data['first_reminder_hours']}h, second={data['second_reminder_hours']}h, max={data['max_reminders_per_booking']}")
        
        # Verify persistence with GET
        get_response = requests.get(
            f"{BASE_URL}/api/guest-payment/reminder-settings/{PROPERTY_ID}",
            headers=auth_headers
        )
        assert get_response.status_code == 200
        get_data = get_response.json()
        assert get_data["first_reminder_hours"] == 48, "Settings not persisted correctly"
        print("✓ Settings persisted and verified via GET")
    
    def test_update_reminder_settings_toggle_enabled(self, auth_headers):
        """PUT /api/guest-payment/reminder-settings/{property_id} can toggle enabled"""
        # Disable reminders
        response = requests.put(
            f"{BASE_URL}/api/guest-payment/reminder-settings/{PROPERTY_ID}",
            headers=auth_headers,
            json={"enabled": False}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] == False, "Failed to disable reminders"
        print("✓ Reminders disabled")
        
        # Re-enable reminders
        response = requests.put(
            f"{BASE_URL}/api/guest-payment/reminder-settings/{PROPERTY_ID}",
            headers=auth_headers,
            json={"enabled": True}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] == True, "Failed to enable reminders"
        print("✓ Reminders re-enabled")
    
    def test_reset_reminder_settings_to_defaults(self, auth_headers):
        """Reset settings to defaults for other tests"""
        update_data = {
            "enabled": True,
            "first_reminder_hours": 24,
            "second_reminder_hours": 6,
            "max_reminders_per_booking": 3,
            "send_to_unpaid_bookings": True
        }
        
        response = requests.put(
            f"{BASE_URL}/api/guest-payment/reminder-settings/{PROPERTY_ID}",
            headers=auth_headers,
            json=update_data
        )
        assert response.status_code == 200
        print("✓ Settings reset to defaults")


class TestSendReminders:
    """Tests for send reminders endpoint"""
    
    def test_send_reminders_returns_results(self, auth_headers):
        """POST /api/guest-payment/send-reminders/{property_id} returns results"""
        response = requests.post(
            f"{BASE_URL}/api/guest-payment/send-reminders/{PROPERTY_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Verify response structure
        assert "sent" in data, "Missing 'sent' field"
        assert "skipped" in data, "Missing 'skipped' field"
        assert "total_unpaid" in data, "Missing 'total_unpaid' field"
        assert "results" in data, "Missing 'results' field"
        assert "message" in data, "Missing 'message' field"
        
        # Verify data types
        assert isinstance(data["sent"], int)
        assert isinstance(data["skipped"], int)
        assert isinstance(data["total_unpaid"], int)
        assert isinstance(data["results"], list)
        
        print(f"✓ Send reminders response: sent={data['sent']}, skipped={data['skipped']}, total_unpaid={data['total_unpaid']}")
        print(f"  Message: {data['message']}")
        
        # If there are results, verify structure
        if data["results"]:
            result = data["results"][0]
            assert "booking_ref" in result, "Result missing 'booking_ref'"
            assert "status" in result, "Result missing 'status'"
            print(f"  First result: {result['booking_ref']} - {result['status']}")
    
    def test_send_reminders_unauthorized(self):
        """POST /api/guest-payment/send-reminders/{property_id} requires auth"""
        response = requests.post(
            f"{BASE_URL}/api/guest-payment/send-reminders/{PROPERTY_ID}"
        )
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ Unauthorized access correctly rejected")
    
    def test_send_reminders_when_disabled(self, auth_headers):
        """POST /api/guest-payment/send-reminders returns message when disabled"""
        # First disable reminders
        requests.put(
            f"{BASE_URL}/api/guest-payment/reminder-settings/{PROPERTY_ID}",
            headers=auth_headers,
            json={"enabled": False}
        )
        
        # Try to send reminders
        response = requests.post(
            f"{BASE_URL}/api/guest-payment/send-reminders/{PROPERTY_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["sent"] == 0, "Should not send when disabled"
        assert "disabled" in data.get("message", "").lower(), f"Expected 'disabled' in message, got: {data.get('message')}"
        print(f"✓ Reminders disabled: {data['message']}")
        
        # Re-enable reminders
        requests.put(
            f"{BASE_URL}/api/guest-payment/reminder-settings/{PROPERTY_ID}",
            headers=auth_headers,
            json={"enabled": True}
        )
        print("✓ Reminders re-enabled")
    
    def test_send_reminders_result_structure(self, auth_headers):
        """Verify detailed result structure for sent reminders"""
        response = requests.post(
            f"{BASE_URL}/api/guest-payment/send-reminders/{PROPERTY_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Check for sent results with full details
        for result in data.get("results", []):
            if result.get("status") == "sent":
                assert "booking_ref" in result
                assert "guest_name" in result or "guest_email" in result
                assert "amount" in result
                assert "hours_left" in result
                assert "reminder_number" in result
                print(f"  Sent: {result['booking_ref']} - £{result.get('amount', 0):.2f} - {result.get('hours_left', 0)}h left - Reminder #{result.get('reminder_number', 1)}")
            elif result.get("status") == "max_reached":
                print(f"  Skipped (max): {result['booking_ref']} - {result.get('reminders_sent', 0)} reminders already sent")
            elif result.get("status") == "no_email":
                print(f"  Skipped (no email): {result['booking_ref']}")
        
        print(f"✓ Result structure verified for {len(data.get('results', []))} bookings")


class TestReminderHistory:
    """Tests for reminder history endpoint"""
    
    def test_get_reminder_history(self, auth_headers):
        """GET /api/guest-payment/reminder-history/{property_id} returns history"""
        response = requests.get(
            f"{BASE_URL}/api/guest-payment/reminder-history/{PROPERTY_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Expected list response"
        print(f"✓ Reminder history retrieved: {len(data)} records")
        
        # If there are records, verify structure
        if data:
            record = data[0]
            assert "booking_id" in record or "booking_ref" in record, "Missing booking identifier"
            assert "sent_at" in record, "Missing 'sent_at' field"
            assert "property_id" in record, "Missing 'property_id' field"
            print(f"  Latest: {record.get('booking_ref', record.get('booking_id', 'N/A'))} - sent at {record.get('sent_at', 'N/A')}")
    
    def test_get_reminder_history_unauthorized(self):
        """GET /api/guest-payment/reminder-history/{property_id} requires auth"""
        response = requests.get(
            f"{BASE_URL}/api/guest-payment/reminder-history/{PROPERTY_ID}"
        )
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ Unauthorized access correctly rejected")
    
    def test_reminder_history_sorted_by_date(self, auth_headers):
        """Verify reminder history is sorted by sent_at descending"""
        response = requests.get(
            f"{BASE_URL}/api/guest-payment/reminder-history/{PROPERTY_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        if len(data) >= 2:
            # Check that records are sorted descending by sent_at
            for i in range(len(data) - 1):
                current_date = data[i].get("sent_at", "")
                next_date = data[i + 1].get("sent_at", "")
                if current_date and next_date:
                    assert current_date >= next_date, f"History not sorted: {current_date} should be >= {next_date}"
            print(f"✓ History sorted correctly (newest first)")
        else:
            print(f"✓ Not enough records to verify sorting ({len(data)} records)")


class TestExistingGuestPaymentFeatures:
    """Regression tests for existing guest payment features"""
    
    def test_list_payment_links(self, auth_headers):
        """GET /api/guest-payment/links/{property_id} still works"""
        response = requests.get(
            f"{BASE_URL}/api/guest-payment/links/{PROPERTY_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Expected list response"
        print(f"✓ Payment links endpoint working: {len(data)} links")
    
    def test_send_payment_link_to_booking(self, auth_headers):
        """POST /api/guest-payment/send-link still works"""
        # First get a booking to send link to
        bookings_response = requests.get(
            f"{BASE_URL}/api/bookings/{PROPERTY_ID}",
            headers=auth_headers
        )
        
        if bookings_response.status_code != 200:
            pytest.skip("Could not fetch bookings")
        
        bookings = bookings_response.json()
        if not bookings:
            pytest.skip("No bookings available")
        
        # Find an unpaid booking
        unpaid_booking = None
        for b in bookings:
            if b.get("payment_status") != "paid" and b.get("guest_email"):
                unpaid_booking = b
                break
        
        if not unpaid_booking:
            print("✓ No unpaid bookings with email found - skipping send link test")
            return
        
        # Send payment link
        response = requests.post(
            f"{BASE_URL}/api/guest-payment/send-link",
            headers=auth_headers,
            json={
                "booking_id": unpaid_booking["id"],
                "extra_charges": [],
                "notes": "Test reminder iteration 62"
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "payment_link_id" in data or "token" in data, "Missing payment link identifier"
        print(f"✓ Payment link sent: {data.get('url', 'N/A')}")


class TestIntegration:
    """Integration tests for the full reminder flow"""
    
    def test_full_reminder_flow(self, auth_headers):
        """Test complete flow: settings -> send -> history"""
        # 1. Get settings
        settings_response = requests.get(
            f"{BASE_URL}/api/guest-payment/reminder-settings/{PROPERTY_ID}",
            headers=auth_headers
        )
        assert settings_response.status_code == 200
        settings = settings_response.json()
        print(f"1. Settings: enabled={settings['enabled']}, first={settings['first_reminder_hours']}h")
        
        # 2. Ensure enabled
        if not settings.get("enabled"):
            requests.put(
                f"{BASE_URL}/api/guest-payment/reminder-settings/{PROPERTY_ID}",
                headers=auth_headers,
                json={"enabled": True}
            )
            print("   Enabled reminders")
        
        # 3. Send reminders
        send_response = requests.post(
            f"{BASE_URL}/api/guest-payment/send-reminders/{PROPERTY_ID}",
            headers=auth_headers
        )
        assert send_response.status_code == 200
        send_data = send_response.json()
        print(f"2. Sent: {send_data['sent']}, Skipped: {send_data['skipped']}, Total unpaid: {send_data['total_unpaid']}")
        
        # 4. Check history
        history_response = requests.get(
            f"{BASE_URL}/api/guest-payment/reminder-history/{PROPERTY_ID}",
            headers=auth_headers
        )
        assert history_response.status_code == 200
        history = history_response.json()
        print(f"3. History: {len(history)} records")
        
        print("✓ Full reminder flow completed successfully")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
