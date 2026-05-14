"""
Iteration 288 - Marketing Videos (Sora 2 Integration) Tests

Tests for:
- GET /api/marketing-videos/sizes - supported sizes/durations/models
- POST /api/marketing-videos/generate - create video job
- GET /api/marketing-videos - list jobs
- GET /api/marketing-videos/{job_id} - single job
- POST /api/marketing-videos/from-event/{event_id} - auto-prompt from event
- Validation: empty prompt, invalid size/duration/model
- Regression: prior iter modules still working
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

class TestMarketingVideosBackend:
    """Marketing Videos (Sora 2) backend API tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login as admin before each test"""
        self.session = requests.Session()
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        self.token = login_resp.json().get("access_token")
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        yield
        self.session.close()
    
    # ==================== /api/marketing-videos/sizes ====================
    
    def test_sizes_endpoint_returns_config(self):
        """GET /api/marketing-videos/sizes returns supported sizes, durations, models, and defaults"""
        resp = self.session.get(f"{BASE_URL}/api/marketing-videos/sizes")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        
        # Verify 4 sizes
        assert "sizes" in data
        assert len(data["sizes"]) == 4
        assert "1024x1792" in data["sizes"]  # portrait for IG/TikTok
        assert "1280x720" in data["sizes"]
        assert "1792x1024" in data["sizes"]
        assert "1024x1024" in data["sizes"]
        
        # Verify 3 durations (4/8/12)
        assert "durations" in data
        assert data["durations"] == [4, 8, 12]
        
        # Verify 2 models
        assert "models" in data
        assert "sora-2" in data["models"]
        assert "sora-2-pro" in data["models"]
        
        # Verify defaults
        assert data["default_size"] == "1024x1792"
        assert data["default_duration"] == 8
        assert data["default_model"] == "sora-2"
        print("✓ Sizes endpoint returns correct config with 4 sizes, 3 durations, 2 models")
    
    def test_sizes_requires_auth(self):
        """GET /api/marketing-videos/sizes requires admin/manager role"""
        resp = requests.get(f"{BASE_URL}/api/marketing-videos/sizes")
        assert resp.status_code == 401, f"Expected 401 without auth, got {resp.status_code}"
        print("✓ Sizes endpoint requires authentication")
    
    # ==================== /api/marketing-videos/generate ====================
    
    def test_generate_creates_queued_job(self):
        """POST /api/marketing-videos/generate with valid prompt creates job with status='queued'"""
        payload = {
            "prompt": "A cinematic 8-second video of a luxury hotel lobby at sunset, golden hour lighting, elegant guests, marble floors, crystal chandeliers",
            "size": "1024x1792",
            "duration": 8,
            "model": "sora-2"
        }
        resp = self.session.post(f"{BASE_URL}/api/marketing-videos/generate", json=payload)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        
        # Verify job structure
        assert "id" in data
        assert data["status"] == "queued"
        assert data["prompt"] == payload["prompt"]
        assert data["size"] == payload["size"]
        assert data["duration"] == payload["duration"]
        assert data["model"] == payload["model"]
        assert data["source_type"] == "manual"
        assert "created_at" in data
        assert "note" in data  # Should mention polling
        
        self.created_job_id = data["id"]
        print(f"✓ Generate creates queued job: {data['id']}")
        return data["id"]
    
    def test_generate_rejects_empty_prompt(self):
        """POST /api/marketing-videos/generate rejects empty prompt with 400"""
        payload = {"prompt": "", "size": "1024x1792", "duration": 8, "model": "sora-2"}
        resp = self.session.post(f"{BASE_URL}/api/marketing-videos/generate", json=payload)
        assert resp.status_code == 400, f"Expected 400 for empty prompt, got {resp.status_code}"
        print("✓ Generate rejects empty prompt with 400")
    
    def test_generate_rejects_whitespace_prompt(self):
        """POST /api/marketing-videos/generate rejects whitespace-only prompt with 400"""
        payload = {"prompt": "   ", "size": "1024x1792", "duration": 8, "model": "sora-2"}
        resp = self.session.post(f"{BASE_URL}/api/marketing-videos/generate", json=payload)
        assert resp.status_code == 400, f"Expected 400 for whitespace prompt, got {resp.status_code}"
        print("✓ Generate rejects whitespace-only prompt with 400")
    
    def test_generate_rejects_invalid_size(self):
        """POST /api/marketing-videos/generate rejects invalid size with 400"""
        payload = {"prompt": "Test video", "size": "999x999", "duration": 8, "model": "sora-2"}
        resp = self.session.post(f"{BASE_URL}/api/marketing-videos/generate", json=payload)
        assert resp.status_code == 400, f"Expected 400 for invalid size, got {resp.status_code}"
        assert "size" in resp.text.lower()
        print("✓ Generate rejects invalid size with 400")
    
    def test_generate_rejects_invalid_duration(self):
        """POST /api/marketing-videos/generate rejects invalid duration with 400"""
        payload = {"prompt": "Test video", "size": "1024x1792", "duration": 15, "model": "sora-2"}
        resp = self.session.post(f"{BASE_URL}/api/marketing-videos/generate", json=payload)
        assert resp.status_code == 400, f"Expected 400 for invalid duration, got {resp.status_code}"
        assert "duration" in resp.text.lower()
        print("✓ Generate rejects invalid duration with 400")
    
    def test_generate_rejects_invalid_model(self):
        """POST /api/marketing-videos/generate rejects invalid model with 400"""
        payload = {"prompt": "Test video", "size": "1024x1792", "duration": 8, "model": "sora-3"}
        resp = self.session.post(f"{BASE_URL}/api/marketing-videos/generate", json=payload)
        assert resp.status_code == 400, f"Expected 400 for invalid model, got {resp.status_code}"
        assert "model" in resp.text.lower()
        print("✓ Generate rejects invalid model with 400")
    
    def test_generate_uses_defaults(self):
        """POST /api/marketing-videos/generate uses defaults when not specified"""
        payload = {"prompt": "A beautiful hotel terrace with ocean view at golden hour"}
        resp = self.session.post(f"{BASE_URL}/api/marketing-videos/generate", json=payload)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        
        # Should use defaults
        assert data["size"] == "1024x1792"
        assert data["duration"] == 8
        assert data["model"] == "sora-2"
        print("✓ Generate uses defaults when not specified")
    
    # ==================== /api/marketing-videos (list) ====================
    
    def test_list_jobs_returns_items(self):
        """GET /api/marketing-videos returns list of jobs"""
        resp = self.session.get(f"{BASE_URL}/api/marketing-videos")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        
        assert "items" in data
        assert "count" in data
        assert isinstance(data["items"], list)
        print(f"✓ List jobs returns {data['count']} items")
    
    def test_list_jobs_filter_by_status(self):
        """GET /api/marketing-videos?status=queued filters by status"""
        resp = self.session.get(f"{BASE_URL}/api/marketing-videos?status=queued")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        
        # All returned items should have status=queued
        for item in data["items"]:
            assert item["status"] == "queued", f"Expected status=queued, got {item['status']}"
        print(f"✓ List jobs filters by status=queued ({data['count']} items)")
    
    def test_list_jobs_filter_by_source_type(self):
        """GET /api/marketing-videos?source_type=manual filters by source_type"""
        resp = self.session.get(f"{BASE_URL}/api/marketing-videos?source_type=manual")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        
        for item in data["items"]:
            assert item["source_type"] == "manual", f"Expected source_type=manual, got {item['source_type']}"
        print(f"✓ List jobs filters by source_type=manual ({data['count']} items)")
    
    # ==================== /api/marketing-videos/{job_id} ====================
    
    def test_get_single_job(self):
        """GET /api/marketing-videos/{job_id} returns single job"""
        # First create a job
        payload = {"prompt": "Test video for single job retrieval"}
        create_resp = self.session.post(f"{BASE_URL}/api/marketing-videos/generate", json=payload)
        assert create_resp.status_code == 200
        job_id = create_resp.json()["id"]
        
        # Get single job
        resp = self.session.get(f"{BASE_URL}/api/marketing-videos/{job_id}")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        
        assert data["id"] == job_id
        assert data["prompt"] == "Test video for single job retrieval"
        print(f"✓ Get single job returns correct data for {job_id}")
    
    def test_get_nonexistent_job_returns_404(self):
        """GET /api/marketing-videos/{job_id} returns 404 for nonexistent job"""
        resp = self.session.get(f"{BASE_URL}/api/marketing-videos/nonexistent-job-id-12345")
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}"
        print("✓ Get nonexistent job returns 404")
    
    # ==================== /api/marketing-videos/from-event/{event_id} ====================
    
    def test_from_event_creates_job_with_auto_prompt(self):
        """POST /api/marketing-videos/from-event/{event_id} creates job with auto-generated prompt"""
        # First, we need to find or create a public event
        # Check if there are any existing events
        events_resp = self.session.get(f"{BASE_URL}/api/public-events?include_drafts=true&limit=1")
        
        if events_resp.status_code == 200 and events_resp.json().get("items"):
            event = events_resp.json()["items"][0]
            event_id = event["id"]
        else:
            # Create a test event
            props_resp = self.session.get(f"{BASE_URL}/api/properties?limit=1")
            property_id = "default"
            if props_resp.status_code == 200 and props_resp.json():
                props = props_resp.json()
                if isinstance(props, list) and len(props) > 0:
                    property_id = props[0].get("id", "default")
            
            event_payload = {
                "title": "TEST_Yaz Şefler Akşamı 2026",
                "date": "2026-07-15",
                "start_time": "19:00",
                "end_time": "23:00",
                "description": "Michelin yıldızlı şeflerimizle unutulmaz bir akşam yemeği deneyimi. Taze deniz ürünleri, yerel malzemeler.",
                "capacity": 50,
                "price_from": 500,
                "tags": ["gastronomi", "şef", "fine dining", "deniz ürünleri"],
                "property_id": property_id
            }
            create_event_resp = self.session.post(f"{BASE_URL}/api/public-events", json=event_payload)
            assert create_event_resp.status_code in [200, 201], f"Failed to create event: {create_event_resp.text}"
            event_id = create_event_resp.json()["id"]
        
        # Now create video from event
        resp = self.session.post(f"{BASE_URL}/api/marketing-videos/from-event/{event_id}", json={})
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        
        # Verify job structure
        assert data["status"] == "queued"
        assert data["source_type"] == "public_event"
        assert data["source_id"] == event_id
        assert "prompt" in data
        assert len(data["prompt"]) > 50  # Auto-generated prompt should be substantial
        assert "cinematic" in data["prompt"].lower() or "video" in data["prompt"].lower()
        print(f"✓ From-event creates job with auto-prompt for event {event_id}")
        print(f"  Auto-prompt preview: {data['prompt'][:100]}...")
    
    def test_from_event_with_prompt_override(self):
        """POST /api/marketing-videos/from-event/{event_id} with prompt_override uses custom prompt"""
        # Get an event
        events_resp = self.session.get(f"{BASE_URL}/api/public-events?include_drafts=true&limit=1")
        if events_resp.status_code != 200 or not events_resp.json().get("items"):
            pytest.skip("No events available for testing")
        
        event_id = events_resp.json()["items"][0]["id"]
        custom_prompt = "Custom override prompt for testing - luxury hotel event with champagne toast"
        
        resp = self.session.post(f"{BASE_URL}/api/marketing-videos/from-event/{event_id}", json={
            "prompt_override": custom_prompt
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        
        assert data["prompt"] == custom_prompt
        assert data["source_type"] == "public_event"
        print("✓ From-event with prompt_override uses custom prompt")
    
    def test_from_event_nonexistent_returns_404(self):
        """POST /api/marketing-videos/from-event/{event_id} returns 404 for nonexistent event"""
        resp = self.session.post(f"{BASE_URL}/api/marketing-videos/from-event/nonexistent-event-id", json={})
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}"
        print("✓ From-event with nonexistent event returns 404")
    
    def test_from_event_rejects_invalid_size(self):
        """POST /api/marketing-videos/from-event/{event_id} rejects invalid size"""
        events_resp = self.session.get(f"{BASE_URL}/api/public-events?include_drafts=true&limit=1")
        if events_resp.status_code != 200 or not events_resp.json().get("items"):
            pytest.skip("No events available for testing")
        
        event_id = events_resp.json()["items"][0]["id"]
        resp = self.session.post(f"{BASE_URL}/api/marketing-videos/from-event/{event_id}", json={
            "size": "invalid-size"
        })
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}"
        print("✓ From-event rejects invalid size with 400")


class TestMarketingVideosJobStatus:
    """Test job status transitions (without waiting for completion)"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login as admin"""
        self.session = requests.Session()
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert login_resp.status_code == 200
        token = login_resp.json().get("token") or login_resp.json().get("access_token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        yield
        self.session.close()
    
    def test_job_transitions_to_rendering(self):
        """Job should transition from queued to rendering (check after short delay)"""
        # Create a job
        payload = {"prompt": "A serene hotel pool at twilight with ambient lighting and palm trees"}
        resp = self.session.post(f"{BASE_URL}/api/marketing-videos/generate", json=payload)
        assert resp.status_code == 200
        job_id = resp.json()["id"]
        initial_status = resp.json()["status"]
        assert initial_status == "queued"
        
        # Wait a bit and check status (should be rendering or still queued)
        time.sleep(2)
        status_resp = self.session.get(f"{BASE_URL}/api/marketing-videos/{job_id}")
        assert status_resp.status_code == 200
        current_status = status_resp.json()["status"]
        
        # Status should be queued, rendering, completed, or failed
        assert current_status in ["queued", "rendering", "completed", "failed"], f"Unexpected status: {current_status}"
        print(f"✓ Job {job_id} status after 2s: {current_status}")


class TestRegressionPriorModules:
    """Regression tests for prior iteration modules"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login as admin"""
        self.session = requests.Session()
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert login_resp.status_code == 200
        token = login_resp.json().get("token") or login_resp.json().get("access_token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        yield
        self.session.close()
    
    def test_agencies_endpoint(self):
        """GET /api/agencies works (Iter 284)"""
        resp = self.session.get(f"{BASE_URL}/api/agencies")
        assert resp.status_code == 200, f"Agencies endpoint failed: {resp.status_code}"
        print("✓ Agencies endpoint works")
    
    def test_web_concierge_sessions(self):
        """GET /api/web-concierge/sessions/default works (Iter 284)"""
        resp = self.session.get(f"{BASE_URL}/api/web-concierge/sessions/default")
        assert resp.status_code == 200, f"Web concierge sessions failed: {resp.status_code}"
        print("✓ Web concierge sessions works")
    
    def test_review_agent_queue(self):
        """GET /api/review-agent/queue/default works (Iter 284)"""
        resp = self.session.get(f"{BASE_URL}/api/review-agent/queue/default")
        assert resp.status_code == 200, f"Review agent queue failed: {resp.status_code}"
        print("✓ Review agent queue works")
    
    def test_open_pricing_segments(self):
        """GET /api/open-pricing/segments works (Iter 285)"""
        resp = self.session.get(f"{BASE_URL}/api/open-pricing/segments")
        assert resp.status_code == 200, f"Open pricing segments failed: {resp.status_code}"
        print("✓ Open pricing segments works")
    
    def test_beach_pos_sunbeds(self):
        """GET /api/beach-pos/sunbeds/default works (Iter 285)"""
        resp = self.session.get(f"{BASE_URL}/api/beach-pos/sunbeds/default")
        assert resp.status_code == 200, f"Beach POS sunbeds failed: {resp.status_code}"
        print("✓ Beach POS sunbeds works")
    
    def test_public_events_list(self):
        """GET /api/public-events works (Iter 285)"""
        resp = self.session.get(f"{BASE_URL}/api/public-events")
        assert resp.status_code == 200, f"Public events failed: {resp.status_code}"
        print("✓ Public events list works")
    
    def test_agents_list(self):
        """GET /api/agents works (Iter 286)"""
        resp = self.session.get(f"{BASE_URL}/api/agents")
        assert resp.status_code == 200, f"Agents list failed: {resp.status_code}"
        print("✓ Agents list works")
    
    def test_vacation_rental_summary(self):
        """GET /api/vacation-rental/summary works (Iter 286)"""
        resp = self.session.get(f"{BASE_URL}/api/vacation-rental/summary")
        assert resp.status_code == 200, f"Vacation rental summary failed: {resp.status_code}"
        print("✓ Vacation rental summary works")
    
    def test_dev_portal_info(self):
        """GET /api/dev-portal/info works (Iter 287)"""
        resp = requests.get(f"{BASE_URL}/api/dev-portal/info")  # No auth required
        assert resp.status_code == 200, f"Dev portal info failed: {resp.status_code}"
        print("✓ Dev portal info works")
    
    def test_wholesaler_providers(self):
        """GET /api/wholesaler/providers works (Iter 287)"""
        resp = self.session.get(f"{BASE_URL}/api/wholesaler/providers")
        assert resp.status_code == 200, f"Wholesaler providers failed: {resp.status_code}"
        print("✓ Wholesaler providers works")
    
    def test_lead_funnel_leads(self):
        """GET /api/lead-funnel/leads works (Iter 287)"""
        resp = self.session.get(f"{BASE_URL}/api/lead-funnel/leads")
        assert resp.status_code == 200, f"Lead funnel leads failed: {resp.status_code}"
        print("✓ Lead funnel leads works")
    
    def test_lighthouse_adapter_status(self):
        """GET /api/lighthouse-adapter/status works (Iter 287)"""
        resp = self.session.get(f"{BASE_URL}/api/lighthouse-adapter/status")
        assert resp.status_code == 200, f"Lighthouse adapter status failed: {resp.status_code}"
        print("✓ Lighthouse adapter status works")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
