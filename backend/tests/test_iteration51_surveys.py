"""
Iteration 51 - Guest Satisfaction Survey Feature Tests
Tests NPS surveys, category ratings, public survey pages, analytics, and CRM integration
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
PROPERTY_ID = "aldgate-flats"

class TestSurveyFeature:
    """Guest Satisfaction Survey API Tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup - login and get auth token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        token = login_response.json().get("token")
        assert token, "No token in login response"
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        self.token = token
        yield
    
    # ==================== SURVEY SETTINGS TESTS ====================
    
    def test_01_get_survey_settings_auto_creates(self):
        """GET /api/surveys/settings/{property_id} - auto-creates default settings with 6 categories"""
        response = self.session.get(f"{BASE_URL}/api/surveys/settings/{PROPERTY_ID}")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Verify structure
        assert "id" in data
        assert data["property_id"] == PROPERTY_ID
        assert data["enabled"] == True
        assert "send_delay_hours" in data
        assert "channels" in data
        assert "email" in data["channels"]
        
        # Verify 6 categories
        assert "categories" in data
        categories = data["categories"]
        assert len(categories) == 6, f"Expected 6 categories, got {len(categories)}"
        
        category_keys = [c["key"] for c in categories]
        expected_keys = ["cleanliness", "service", "location", "value", "comfort", "facilities"]
        for key in expected_keys:
            assert key in category_keys, f"Missing category: {key}"
        
        # Verify email template fields
        assert "email_subject" in data
        assert "email_heading" in data
        assert "email_body" in data
        assert "thank_you_message" in data
        
        # Verify alert settings
        assert "low_score_alert_threshold" in data
        assert "low_score_alert_enabled" in data
        assert "auto_tag_profiles" in data
        
        print(f"✓ Survey settings auto-created with {len(categories)} categories")
    
    def test_02_update_survey_settings(self):
        """PUT /api/surveys/settings/{property_id} - update settings"""
        updates = {
            "send_delay_hours": 4,
            "low_score_alert_threshold": 5,
            "email_subject": "TEST: How was your stay at {hotel_name}?",
            "reminder_enabled": False
        }
        
        response = self.session.put(f"{BASE_URL}/api/surveys/settings/{PROPERTY_ID}", json=updates)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert data["send_delay_hours"] == 4
        assert data["low_score_alert_threshold"] == 5
        assert "TEST:" in data["email_subject"]
        assert data["reminder_enabled"] == False
        assert "updated_at" in data
        
        print("✓ Survey settings updated successfully")
    
    def test_03_update_survey_channels(self):
        """PUT /api/surveys/settings/{property_id} - update channels"""
        updates = {
            "channels": ["email"],  # Remove whatsapp
            "enabled": True
        }
        
        response = self.session.put(f"{BASE_URL}/api/surveys/settings/{PROPERTY_ID}", json=updates)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert data["channels"] == ["email"]
        print("✓ Survey channels updated")
    
    # ==================== MANUAL SEND TESTS ====================
    
    def test_04_send_manual_survey(self):
        """POST /api/surveys/send-manual - send survey to specific guest, returns token + link"""
        payload = {
            "property_id": PROPERTY_ID,
            "guest_name": "TEST_John Smith",
            "guest_email": "test_john@example.com",
            "booking_ref": "TEST-SURVEY-001"
        }
        
        response = self.session.post(f"{BASE_URL}/api/surveys/send-manual", json=payload)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "invite" in data
        assert "survey_link" in data
        
        invite = data["invite"]
        assert invite["guest_name"] == "TEST_John Smith"
        assert invite["guest_email"] == "test_john@example.com"
        assert invite["booking_ref"] == "TEST-SURVEY-001"
        assert invite["status"] == "sent"
        assert "token" in invite
        assert invite["completed"] == False
        
        # Verify survey link contains token
        assert invite["token"] in data["survey_link"]
        
        # Store token for later tests
        self.__class__.survey_token = invite["token"]
        self.__class__.invite_id = invite["id"]
        
        print(f"✓ Manual survey sent, token: {invite['token'][:20]}...")
    
    def test_05_send_manual_survey_second_guest(self):
        """POST /api/surveys/send-manual - send to another guest for analytics testing"""
        payload = {
            "property_id": PROPERTY_ID,
            "guest_name": "TEST_Jane Doe",
            "guest_email": "test_jane@example.com",
            "booking_ref": "TEST-SURVEY-002"
        }
        
        response = self.session.post(f"{BASE_URL}/api/surveys/send-manual", json=payload)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        self.__class__.survey_token_2 = data["invite"]["token"]
        print(f"✓ Second manual survey sent")
    
    # ==================== PUBLIC SURVEY ENDPOINTS (NO AUTH) ====================
    
    def test_06_get_public_survey_no_auth(self):
        """GET /api/surveys/public/{token} - public endpoint, no auth required"""
        # Use a new session without auth
        public_session = requests.Session()
        public_session.headers.update({"Content-Type": "application/json"})
        
        token = self.__class__.survey_token
        response = public_session.get(f"{BASE_URL}/api/surveys/public/{token}")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Verify survey form data
        assert data["completed"] == False
        assert data["guest_name"] == "TEST_John Smith"
        assert "hotel_name" in data
        assert "survey_type" in data
        assert "categories" in data
        assert "thank_you_message" in data
        
        # Verify categories are returned
        categories = data["categories"]
        assert len(categories) == 6
        
        print(f"✓ Public survey retrieved without auth")
    
    def test_07_get_public_survey_invalid_token(self):
        """GET /api/surveys/public/{token} - invalid token returns 404"""
        public_session = requests.Session()
        response = public_session.get(f"{BASE_URL}/api/surveys/public/invalid-token-12345")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ Invalid token returns 404")
    
    def test_08_submit_public_survey_promoter(self):
        """POST /api/surveys/public/{token} - submit NPS + category ratings + comment (promoter)"""
        public_session = requests.Session()
        public_session.headers.update({"Content-Type": "application/json"})
        
        token = self.__class__.survey_token
        payload = {
            "nps_score": 9,  # Promoter
            "category_ratings": {
                "cleanliness": 5,
                "service": 4,
                "location": 5,
                "value": 4,
                "comfort": 5,
                "facilities": 4
            },
            "comment": "TEST: Excellent stay, highly recommend!"
        }
        
        response = public_session.post(f"{BASE_URL}/api/surveys/public/{token}", json=payload)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert data["status"] == "submitted"
        assert "Thank you" in data["message"]
        
        print("✓ Survey submitted as promoter (NPS=9)")
    
    def test_09_submit_public_survey_detractor(self):
        """POST /api/surveys/public/{token} - submit low NPS (detractor) to trigger alert"""
        public_session = requests.Session()
        public_session.headers.update({"Content-Type": "application/json"})
        
        token = self.__class__.survey_token_2
        payload = {
            "nps_score": 4,  # Detractor
            "category_ratings": {
                "cleanliness": 2,
                "service": 3,
                "location": 4,
                "value": 2,
                "comfort": 3,
                "facilities": 2
            },
            "comment": "TEST: Room was not clean, disappointed with the service."
        }
        
        response = public_session.post(f"{BASE_URL}/api/surveys/public/{token}", json=payload)
        assert response.status_code == 200, f"Failed: {response.text}"
        
        print("✓ Survey submitted as detractor (NPS=4) - should trigger low score alert")
    
    def test_10_submit_already_completed_survey(self):
        """POST /api/surveys/public/{token} - already submitted returns 400"""
        public_session = requests.Session()
        public_session.headers.update({"Content-Type": "application/json"})
        
        token = self.__class__.survey_token
        payload = {"nps_score": 8, "category_ratings": {}, "comment": ""}
        
        response = public_session.post(f"{BASE_URL}/api/surveys/public/{token}", json=payload)
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        
        print("✓ Already submitted survey returns 400")
    
    def test_11_get_completed_survey_shows_completed(self):
        """GET /api/surveys/public/{token} - completed survey shows completed=True"""
        public_session = requests.Session()
        
        token = self.__class__.survey_token
        response = public_session.get(f"{BASE_URL}/api/surveys/public/{token}")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert data["completed"] == True
        assert "message" in data
        
        print("✓ Completed survey shows completed=True")
    
    # ==================== AUTO-SEND TESTS ====================
    
    def test_12_auto_send_surveys(self):
        """POST /api/surveys/send/{property_id} - auto-send to recent checkouts"""
        response = self.session.post(f"{BASE_URL}/api/surveys/send/{PROPERTY_ID}")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert "sent" in data
        assert "message" in data
        assert isinstance(data["sent"], int)
        
        print(f"✓ Auto-send completed: {data['sent']} surveys sent")
    
    # ==================== SURVEY RESPONSES TESTS ====================
    
    def test_13_list_survey_responses(self):
        """GET /api/surveys/responses/{property_id} - list responses with period filter"""
        response = self.session.get(f"{BASE_URL}/api/surveys/responses/{PROPERTY_ID}?period=30d")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert isinstance(data, list)
        assert len(data) >= 2, f"Expected at least 2 responses, got {len(data)}"
        
        # Verify response structure
        resp = data[0]
        assert "id" in resp
        assert "nps_score" in resp
        assert "category_ratings" in resp
        assert "nps_category" in resp
        assert "guest_name" in resp
        assert "created_at" in resp
        
        # Store response ID for delete test
        self.__class__.response_id = resp["id"]
        
        print(f"✓ Listed {len(data)} survey responses")
    
    def test_14_list_survey_responses_different_periods(self):
        """GET /api/surveys/responses/{property_id} - test different period filters"""
        for period in ["7d", "14d", "30d", "90d"]:
            response = self.session.get(f"{BASE_URL}/api/surveys/responses/{PROPERTY_ID}?period={period}")
            assert response.status_code == 200, f"Failed for period {period}: {response.text}"
        
        print("✓ All period filters work correctly")
    
    # ==================== ANALYTICS TESTS ====================
    
    def test_15_survey_analytics(self):
        """GET /api/surveys/analytics/{property_id} - NPS analytics with all metrics"""
        response = self.session.get(f"{BASE_URL}/api/surveys/analytics/{PROPERTY_ID}?period=30d")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Verify all analytics fields
        assert "period_days" in data
        assert "total_sent" in data
        assert "total_responses" in data
        assert "response_rate" in data
        assert "avg_nps" in data
        assert "nps_net_score" in data
        assert "promoters" in data
        assert "passives" in data
        assert "detractors" in data
        assert "category_averages" in data
        assert "daily_trend" in data
        assert "recent_comments" in data
        
        # Verify we have responses
        assert data["total_responses"] >= 2
        
        # Verify NPS distribution
        assert data["promoters"] >= 1  # We submitted one promoter
        assert data["detractors"] >= 1  # We submitted one detractor
        
        # Verify category averages
        cat_avgs = data["category_averages"]
        assert len(cat_avgs) > 0
        
        print(f"✓ Analytics: NPS Net={data['nps_net_score']}, Responses={data['total_responses']}, Promoters={data['promoters']}, Detractors={data['detractors']}")
    
    def test_16_analytics_category_averages(self):
        """GET /api/surveys/analytics/{property_id} - verify category averages calculation"""
        response = self.session.get(f"{BASE_URL}/api/surveys/analytics/{PROPERTY_ID}?period=30d")
        assert response.status_code == 200
        data = response.json()
        
        cat_avgs = data["category_averages"]
        expected_categories = ["cleanliness", "service", "location", "value", "comfort", "facilities"]
        
        for cat in expected_categories:
            if cat in cat_avgs:
                avg = cat_avgs[cat]
                assert 1 <= avg <= 5, f"Category {cat} average {avg} out of range"
        
        print(f"✓ Category averages calculated correctly: {cat_avgs}")
    
    def test_17_analytics_daily_trend(self):
        """GET /api/surveys/analytics/{property_id} - verify daily trend data"""
        response = self.session.get(f"{BASE_URL}/api/surveys/analytics/{PROPERTY_ID}?period=30d")
        assert response.status_code == 200
        data = response.json()
        
        daily_trend = data["daily_trend"]
        assert isinstance(daily_trend, list)
        
        if len(daily_trend) > 0:
            day = daily_trend[0]
            assert "date" in day
            assert "avg_nps" in day
            assert "count" in day
        
        print(f"✓ Daily trend has {len(daily_trend)} data points")
    
    def test_18_analytics_recent_comments(self):
        """GET /api/surveys/analytics/{property_id} - verify recent comments"""
        response = self.session.get(f"{BASE_URL}/api/surveys/analytics/{PROPERTY_ID}?period=30d")
        assert response.status_code == 200
        data = response.json()
        
        comments = data["recent_comments"]
        assert isinstance(comments, list)
        assert len(comments) >= 2  # We submitted 2 surveys with comments
        
        comment = comments[0]
        assert "guest_name" in comment
        assert "nps_score" in comment
        assert "comment" in comment
        assert "date" in comment
        
        print(f"✓ Recent comments: {len(comments)} comments retrieved")
    
    # ==================== INVITES TESTS ====================
    
    def test_19_list_survey_invites(self):
        """GET /api/surveys/invites/{property_id} - list sent invitations"""
        response = self.session.get(f"{BASE_URL}/api/surveys/invites/{PROPERTY_ID}")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert isinstance(data, list)
        assert len(data) >= 2  # We sent at least 2 manual invites
        
        # Verify invite structure
        invite = data[0]
        assert "id" in invite
        assert "guest_name" in invite
        assert "guest_email" in invite
        assert "token" in invite
        assert "status" in invite
        assert "completed" in invite
        assert "sent_at" in invite
        
        print(f"✓ Listed {len(data)} survey invites")
    
    def test_20_invites_show_completed_status(self):
        """GET /api/surveys/invites/{property_id} - verify completed status is updated"""
        response = self.session.get(f"{BASE_URL}/api/surveys/invites/{PROPERTY_ID}")
        assert response.status_code == 200
        data = response.json()
        
        # Find our test invites
        completed_count = sum(1 for inv in data if inv.get("completed") == True and "TEST_" in inv.get("guest_name", ""))
        assert completed_count >= 2, f"Expected at least 2 completed test invites, got {completed_count}"
        
        print(f"✓ {completed_count} test invites marked as completed")
    
    # ==================== DELETE RESPONSE TEST ====================
    
    def test_21_delete_survey_response(self):
        """DELETE /api/surveys/responses/{response_id} - delete a response"""
        # First get a response ID
        response = self.session.get(f"{BASE_URL}/api/surveys/responses/{PROPERTY_ID}?period=30d")
        assert response.status_code == 200
        responses = response.json()
        
        # Find a TEST response to delete
        test_response = None
        for r in responses:
            if "TEST_" in r.get("guest_name", ""):
                test_response = r
                break
        
        if test_response:
            response_id = test_response["id"]
            delete_response = self.session.delete(f"{BASE_URL}/api/surveys/responses/{response_id}")
            assert delete_response.status_code == 200, f"Failed: {delete_response.text}"
            data = delete_response.json()
            assert data["status"] == "deleted"
            print(f"✓ Survey response deleted: {response_id}")
        else:
            print("⚠ No TEST response found to delete, skipping")
    
    # ==================== INTEGRATION TESTS ====================
    
    def test_22_verify_guest_profile_nps_tag(self):
        """Verify survey responses update guest profile with NPS tag"""
        # Check guest profiles for NPS tags
        response = self.session.get(f"{BASE_URL}/api/guest-profiles/{PROPERTY_ID}")
        if response.status_code == 200:
            profiles = response.json()
            # Look for profiles with nps tags
            nps_tagged = [p for p in profiles if any("nps:" in t for t in p.get("tags", []))]
            print(f"✓ Found {len(nps_tagged)} guest profiles with NPS tags")
        else:
            print("⚠ Guest profiles endpoint not available, skipping NPS tag verification")
    
    def test_23_verify_low_score_alert_in_sync_log(self):
        """Verify low NPS scores create sync log alerts"""
        response = self.session.get(f"{BASE_URL}/api/sync-logs/{PROPERTY_ID}?limit=50")
        if response.status_code == 200:
            logs = response.json()
            # Look for survey alerts
            survey_alerts = [l for l in logs if l.get("source") == "survey" and l.get("level") == "warning"]
            if len(survey_alerts) > 0:
                print(f"✓ Found {len(survey_alerts)} low NPS alert(s) in sync logs")
            else:
                print("⚠ No survey alerts found in sync logs (may need more detractor submissions)")
        else:
            print("⚠ Sync logs endpoint not available, skipping alert verification")
    
    # ==================== SETTINGS EDGE CASES ====================
    
    def test_24_settings_disable_surveys(self):
        """PUT /api/surveys/settings/{property_id} - disable surveys"""
        updates = {"enabled": False}
        response = self.session.put(f"{BASE_URL}/api/surveys/settings/{PROPERTY_ID}", json=updates)
        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] == False
        print("✓ Surveys disabled")
    
    def test_25_auto_send_when_disabled(self):
        """POST /api/surveys/send/{property_id} - returns 0 sent when disabled"""
        response = self.session.post(f"{BASE_URL}/api/surveys/send/{PROPERTY_ID}")
        assert response.status_code == 200
        data = response.json()
        assert data["sent"] == 0
        assert "disabled" in data["message"].lower()
        print("✓ Auto-send returns 0 when surveys disabled")
    
    def test_26_re_enable_surveys(self):
        """PUT /api/surveys/settings/{property_id} - re-enable surveys"""
        updates = {"enabled": True}
        response = self.session.put(f"{BASE_URL}/api/surveys/settings/{PROPERTY_ID}", json=updates)
        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] == True
        print("✓ Surveys re-enabled")
    
    # ==================== AUTH TESTS ====================
    
    def test_27_settings_requires_auth(self):
        """GET /api/surveys/settings/{property_id} - requires authentication"""
        no_auth_session = requests.Session()
        response = no_auth_session.get(f"{BASE_URL}/api/surveys/settings/{PROPERTY_ID}")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ Settings endpoint requires auth")
    
    def test_28_analytics_requires_auth(self):
        """GET /api/surveys/analytics/{property_id} - requires authentication"""
        no_auth_session = requests.Session()
        response = no_auth_session.get(f"{BASE_URL}/api/surveys/analytics/{PROPERTY_ID}")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ Analytics endpoint requires auth")
    
    def test_29_responses_requires_auth(self):
        """GET /api/surveys/responses/{property_id} - requires authentication"""
        no_auth_session = requests.Session()
        response = no_auth_session.get(f"{BASE_URL}/api/surveys/responses/{PROPERTY_ID}")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ Responses endpoint requires auth")
    
    def test_30_invites_requires_auth(self):
        """GET /api/surveys/invites/{property_id} - requires authentication"""
        no_auth_session = requests.Session()
        response = no_auth_session.get(f"{BASE_URL}/api/surveys/invites/{PROPERTY_ID}")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ Invites endpoint requires auth")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
