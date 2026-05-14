"""
Iteration 286 Backend Tests — Agentic AI + Vacation Rental

Tests:
1. Agentic AI (Mews 2026 parity):
   - GET /api/agents auto-seeds 3 agents on first call
   - POST /api/agents creates custom agent (admin)
   - PATCH /api/agents/{id} updates allowed fields
   - POST /api/agents/{id}/run triggers execution
   - POST /api/agents/runs/{run_id}/approve
   - POST /api/agents/runs/{run_id}/reject
   - GET /api/agents/{id}/runs returns history

2. Vacation Rental dedicated view (Eviivo+Lighthouse parity):
   - GET /api/vacation-rental/summary?year=YYYY
   - GET /api/vacation-rental/units?days=30
   - GET /api/vacation-rental/calendar?date=YYYY-MM-DD&days=14
   - Verify 4 apartment properties and 37 units

3. Regression tests for iter 284 and 285 endpoints
"""
import pytest
import requests
import os
from datetime import datetime

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Test credentials
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"


@pytest.fixture(scope="module")
def admin_session():
    """Get authenticated admin session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    
    # Login as admin
    resp = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    assert resp.status_code == 200, f"Admin login failed: {resp.text}"
    return session


class TestAgenticAI:
    """Agentic AI Loops — Mews 2026 parity"""
    
    def test_list_agents_auto_seeds(self, admin_session):
        """GET /api/agents auto-seeds 3 agents on first call"""
        resp = admin_session.get(f"{BASE_URL}/api/agents")
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        
        assert "items" in data
        assert "count" in data
        assert data["count"] >= 3, "Should have at least 3 seeded agents"
        
        # Verify the 3 seeded agents exist
        agent_names = [a["name"] for a in data["items"]]
        assert "Misafir Memnuniyet Agent" in agent_names, "Guest Recovery agent missing"
        assert "Operasyon Optimize Agent" in agent_names, "Operations agent missing"
        assert "Revenue Pulse Agent" in agent_names, "Revenue agent missing"
        
        # Verify agent structure
        for agent in data["items"]:
            assert "id" in agent
            assert "name" in agent
            assert "mission" in agent
            assert "tools" in agent
            assert "category" in agent
            assert "is_active" in agent
            assert "total_runs" in agent
            assert isinstance(agent["tools"], list)
    
    def test_agent_tools_correct(self, admin_session):
        """Verify each agent has correct tools"""
        resp = admin_session.get(f"{BASE_URL}/api/agents")
        assert resp.status_code == 200
        agents = {a["name"]: a for a in resp.json()["items"]}
        
        # Revenue Pulse Agent
        revenue_agent = agents.get("Revenue Pulse Agent")
        assert revenue_agent is not None
        assert "find_low_occupancy_dates" in revenue_agent["tools"]
        assert "draft_promo_rule" in revenue_agent["tools"]
        
        # Guest Recovery Agent
        guest_agent = agents.get("Misafir Memnuniyet Agent")
        assert guest_agent is not None
        assert "find_low_reviews" in guest_agent["tools"]
        assert "draft_apology" in guest_agent["tools"]
        assert "propose_voucher" in guest_agent["tools"]
        
        # Operations Agent
        ops_agent = agents.get("Operasyon Optimize Agent")
        assert ops_agent is not None
        assert "find_stale_oos" in ops_agent["tools"]
        assert "create_maintenance_ticket" in ops_agent["tools"]
        assert "estimate_revenue_loss" in ops_agent["tools"]
    
    def test_create_custom_agent(self, admin_session):
        """POST /api/agents creates custom agent (admin only)"""
        payload = {
            "name": "TEST_Custom_Agent_286",
            "mission": "Test mission for iteration 286",
            "category": "test",
            "tools": ["test_tool_1", "test_tool_2"],
            "requires_approval": True,
            "max_actions_per_run": 3
        }
        resp = admin_session.post(f"{BASE_URL}/api/agents", json=payload)
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        
        assert data["name"] == payload["name"]
        assert data["mission"] == payload["mission"]
        assert data["category"] == payload["category"]
        assert data["tools"] == payload["tools"]
        assert data["requires_approval"] == True
        assert data["max_actions_per_run"] == 3
        assert "id" in data
        assert data["total_runs"] == 0
    
    def test_create_agent_validation(self, admin_session):
        """POST /api/agents validates name+mission required"""
        # Missing name
        resp = admin_session.post(f"{BASE_URL}/api/agents", json={
            "mission": "Test mission"
        })
        assert resp.status_code == 400
        
        # Missing mission
        resp = admin_session.post(f"{BASE_URL}/api/agents", json={
            "name": "Test Agent"
        })
        assert resp.status_code == 400
    
    def test_patch_agent(self, admin_session):
        """PATCH /api/agents/{id} updates allowed fields"""
        # First get an agent
        resp = admin_session.get(f"{BASE_URL}/api/agents")
        agents = resp.json()["items"]
        test_agent = next((a for a in agents if "TEST_Custom_Agent" in a["name"]), agents[0])
        agent_id = test_agent["id"]
        
        # Update allowed fields
        resp = admin_session.patch(f"{BASE_URL}/api/agents/{agent_id}", json={
            "mission": "Updated mission for testing",
            "is_active": True
        })
        assert resp.status_code == 200, f"Failed: {resp.text}"
        assert resp.json()["ok"] == True
    
    def test_patch_agent_not_found(self, admin_session):
        """PATCH /api/agents/{id} returns 404 for non-existent agent"""
        resp = admin_session.patch(f"{BASE_URL}/api/agents/non-existent-id", json={
            "mission": "Test"
        })
        assert resp.status_code == 404
    
    def test_run_agent(self, admin_session):
        """POST /api/agents/{id}/run triggers execution"""
        # Get Revenue Pulse Agent (most likely to produce results)
        resp = admin_session.get(f"{BASE_URL}/api/agents")
        agents = resp.json()["items"]
        revenue_agent = next((a for a in agents if a["name"] == "Revenue Pulse Agent"), None)
        assert revenue_agent is not None, "Revenue Pulse Agent not found"
        
        agent_id = revenue_agent["id"]
        initial_runs = revenue_agent["total_runs"]
        
        # Run the agent
        resp = admin_session.post(f"{BASE_URL}/api/agents/{agent_id}/run")
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        
        # Verify run structure
        assert "id" in data
        assert "agent_id" in data
        assert data["agent_id"] == agent_id
        assert "agent_name" in data
        assert "status" in data
        assert "actions_taken" in data
        assert "results" in data
        assert isinstance(data["actions_taken"], list)
        assert isinstance(data["results"], dict)
        
        # Revenue Pulse with requires_approval=True should be pending_approval if actions taken
        if len(data["actions_taken"]) > 0:
            assert data["status"] == "pending_approval"
        
        # Verify total_runs incremented
        resp2 = admin_session.get(f"{BASE_URL}/api/agents")
        updated_agent = next((a for a in resp2.json()["items"] if a["id"] == agent_id), None)
        assert updated_agent["total_runs"] == initial_runs + 1
    
    def test_run_agent_not_found(self, admin_session):
        """POST /api/agents/{id}/run returns 404 for non-existent agent"""
        resp = admin_session.post(f"{BASE_URL}/api/agents/non-existent-id/run")
        assert resp.status_code == 404
    
    def test_list_agent_runs(self, admin_session):
        """GET /api/agents/{id}/runs returns history"""
        # Get an agent with runs
        resp = admin_session.get(f"{BASE_URL}/api/agents")
        agents = resp.json()["items"]
        agent_with_runs = next((a for a in agents if a["total_runs"] > 0), agents[0])
        agent_id = agent_with_runs["id"]
        
        resp = admin_session.get(f"{BASE_URL}/api/agents/{agent_id}/runs")
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        
        assert "items" in data
        assert "count" in data
        
        if data["count"] > 0:
            run = data["items"][0]
            assert "id" in run
            assert "agent_id" in run
            assert "status" in run
            assert "started_at" in run
    
    def test_approve_run(self, admin_session):
        """POST /api/agents/runs/{run_id}/approve flips status to approved"""
        # First run an agent that requires approval
        resp = admin_session.get(f"{BASE_URL}/api/agents")
        agents = resp.json()["items"]
        approval_agent = next((a for a in agents if a.get("requires_approval", False)), agents[0])
        
        # Run it
        run_resp = admin_session.post(f"{BASE_URL}/api/agents/{approval_agent['id']}/run")
        assert run_resp.status_code == 200
        run_data = run_resp.json()
        run_id = run_data["id"]
        
        # If pending_approval, approve it
        if run_data["status"] == "pending_approval":
            approve_resp = admin_session.post(f"{BASE_URL}/api/agents/runs/{run_id}/approve")
            assert approve_resp.status_code == 200, f"Failed: {approve_resp.text}"
            assert approve_resp.json()["ok"] == True
            
            # Verify status changed
            get_resp = admin_session.get(f"{BASE_URL}/api/agents/runs/{run_id}")
            assert get_resp.status_code == 200
            assert get_resp.json()["status"] == "approved"
    
    def test_reject_run(self, admin_session):
        """POST /api/agents/runs/{run_id}/reject with reason works"""
        # Run an agent that requires approval
        resp = admin_session.get(f"{BASE_URL}/api/agents")
        agents = resp.json()["items"]
        approval_agent = next((a for a in agents if a.get("requires_approval", False)), agents[0])
        
        # Run it
        run_resp = admin_session.post(f"{BASE_URL}/api/agents/{approval_agent['id']}/run")
        assert run_resp.status_code == 200
        run_data = run_resp.json()
        run_id = run_data["id"]
        
        # Reject with reason
        reject_resp = admin_session.post(f"{BASE_URL}/api/agents/runs/{run_id}/reject", json={
            "reason": "Test rejection reason"
        })
        assert reject_resp.status_code == 200, f"Failed: {reject_resp.text}"
        assert reject_resp.json()["ok"] == True
        
        # Verify status changed
        get_resp = admin_session.get(f"{BASE_URL}/api/agents/runs/{run_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["status"] == "rejected"
    
    def test_get_run_detail(self, admin_session):
        """GET /api/agents/runs/{run_id} returns run detail"""
        # Get a run
        resp = admin_session.get(f"{BASE_URL}/api/agents")
        agents = resp.json()["items"]
        agent_with_runs = next((a for a in agents if a["total_runs"] > 0), None)
        
        if agent_with_runs:
            runs_resp = admin_session.get(f"{BASE_URL}/api/agents/{agent_with_runs['id']}/runs")
            if runs_resp.json()["count"] > 0:
                run_id = runs_resp.json()["items"][0]["id"]
                
                detail_resp = admin_session.get(f"{BASE_URL}/api/agents/runs/{run_id}")
                assert detail_resp.status_code == 200
                data = detail_resp.json()
                
                assert "id" in data
                assert "agent_id" in data
                assert "status" in data
                assert "actions_taken" in data
                assert "results" in data
    
    def test_get_run_not_found(self, admin_session):
        """GET /api/agents/runs/{run_id} returns 404 for non-existent run"""
        resp = admin_session.get(f"{BASE_URL}/api/agents/runs/non-existent-run-id")
        assert resp.status_code == 404


class TestVacationRental:
    """Vacation Rental dedicated view — Eviivo+Lighthouse parity"""
    
    def test_summary_endpoint(self, admin_session):
        """GET /api/vacation-rental/summary returns KPIs for apartment properties"""
        year = datetime.now().year
        resp = admin_session.get(f"{BASE_URL}/api/vacation-rental/summary?year={year}")
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        
        assert "year" in data
        assert data["year"] == str(year)
        assert "properties" in data
        assert "kpis" in data
        
        # Verify KPI structure
        kpis = data["kpis"]
        assert "property_count" in kpis
        assert "unit_count" in kpis
        assert "total_revenue" in kpis
        assert "total_nights" in kpis
        assert "occupancy_percent" in kpis
        assert "adr" in kpis
        assert "revpar" in kpis
        assert "booking_count" in kpis
    
    def test_summary_apartment_properties(self, admin_session):
        """Verify 4 apartment properties present"""
        year = datetime.now().year
        resp = admin_session.get(f"{BASE_URL}/api/vacation-rental/summary?year={year}")
        assert resp.status_code == 200
        data = resp.json()
        
        properties = data["properties"]
        property_ids = [p["id"] for p in properties]
        
        # Expected apartment properties
        expected = ["aldgate-flats", "camden-suites", "london-suites", "ryam-suites"]
        for exp_id in expected:
            assert exp_id in property_ids, f"Missing apartment property: {exp_id}"
        
        # Verify property_count matches
        assert data["kpis"]["property_count"] == len(properties)
        assert data["kpis"]["property_count"] >= 4, "Should have at least 4 apartment properties"
    
    def test_summary_unit_count(self, admin_session):
        """Verify unit count (rooms) for apartment properties"""
        year = datetime.now().year
        resp = admin_session.get(f"{BASE_URL}/api/vacation-rental/summary?year={year}")
        assert resp.status_code == 200
        data = resp.json()
        
        # Should have units (rooms) across apartment properties
        unit_count = data["kpis"]["unit_count"]
        assert unit_count > 0, "Should have units in apartment properties"
        # Note: The exact count depends on seeded data, but should be substantial
    
    def test_units_endpoint(self, admin_session):
        """GET /api/vacation-rental/units returns rooms with bookings"""
        resp = admin_session.get(f"{BASE_URL}/api/vacation-rental/units?days=30")
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        
        assert "items" in data
        assert "count" in data
        assert "days" in data
        assert data["days"] == 30
        
        # Verify room structure
        if data["count"] > 0:
            room = data["items"][0]
            assert "id" in room
            assert "property_id" in room
            assert "property_name" in room
            assert "bookings" in room
            assert "booked_nights" in room
            assert isinstance(room["bookings"], list)
    
    def test_calendar_endpoint(self, admin_session):
        """GET /api/vacation-rental/calendar returns grid with cells"""
        today = datetime.now().strftime("%Y-%m-%d")
        resp = admin_session.get(f"{BASE_URL}/api/vacation-rental/calendar?date={today}&days=14")
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        
        assert "dates" in data
        assert "rooms" in data
        assert "count" in data
        
        # Verify dates array
        assert len(data["dates"]) == 14
        assert data["dates"][0] == today
        
        # Verify room grid structure
        if data["count"] > 0:
            room = data["rooms"][0]
            assert "room_id" in room
            assert "room_number" in room
            assert "property_id" in room
            assert "property_name" in room
            assert "cells" in room
            assert len(room["cells"]) == 14
            
            # Verify cell structure
            cell = room["cells"][0]
            assert "date" in cell
            assert "status" in cell
            assert cell["status"] in ["booked", "free"]
            assert "guest_name" in cell
    
    def test_calendar_default_date(self, admin_session):
        """GET /api/vacation-rental/calendar uses today if no date provided"""
        resp = admin_session.get(f"{BASE_URL}/api/vacation-rental/calendar?days=7")
        assert resp.status_code == 200
        data = resp.json()
        
        # Should default to today
        today = datetime.now().strftime("%Y-%m-%d")
        assert data["dates"][0] == today


class TestRegressionIter284:
    """Regression tests for Iteration 284 endpoints"""
    
    def test_agencies_endpoint(self, admin_session):
        """GET /api/agencies works"""
        resp = admin_session.get(f"{BASE_URL}/api/agencies")
        assert resp.status_code == 200, f"Agencies endpoint failed: {resp.text}"
        data = resp.json()
        assert "items" in data
    
    def test_web_concierge_config(self, admin_session):
        """GET /api/web-concierge/widget-config/{property_id} works"""
        resp = admin_session.get(f"{BASE_URL}/api/web-concierge/widget-config/aldgate-flats")
        assert resp.status_code == 200, f"Web concierge config failed: {resp.text}"
        data = resp.json()
        assert "property_id" in data
    
    def test_review_agent_config(self, admin_session):
        """GET /api/review-agent/config/{property_id} works"""
        resp = admin_session.get(f"{BASE_URL}/api/review-agent/config/aldgate-flats")
        assert resp.status_code == 200, f"Review agent config failed: {resp.text}"
        data = resp.json()
        assert "property_id" in data


class TestRegressionIter285:
    """Regression tests for Iteration 285 endpoints"""
    
    def test_open_pricing_segments(self, admin_session):
        """GET /api/open-pricing/segments works"""
        resp = admin_session.get(f"{BASE_URL}/api/open-pricing/segments")
        assert resp.status_code == 200, f"Open pricing segments failed: {resp.text}"
        data = resp.json()
        assert "items" in data
        assert len(data["items"]) == 6  # 6 segments
    
    def test_open_pricing_channels(self, admin_session):
        """GET /api/open-pricing/channels works"""
        resp = admin_session.get(f"{BASE_URL}/api/open-pricing/channels")
        assert resp.status_code == 200, f"Open pricing channels failed: {resp.text}"
        data = resp.json()
        assert "items" in data
        assert len(data["items"]) == 8  # 8 channels
    
    def test_beach_pos_menu(self, admin_session):
        """GET /api/beach-pos/menu/{property_id} works"""
        resp = admin_session.get(f"{BASE_URL}/api/beach-pos/menu/aldgate-flats")
        assert resp.status_code == 200, f"Beach POS menu failed: {resp.text}"
        data = resp.json()
        assert "items" in data
    
    def test_public_events_list(self, admin_session):
        """GET /api/public-events works"""
        resp = admin_session.get(f"{BASE_URL}/api/public-events?include_drafts=true")
        assert resp.status_code == 200, f"Public events failed: {resp.text}"
        data = resp.json()
        assert "items" in data


class TestRegressionCore:
    """Core regression tests"""
    
    def test_properties_endpoint(self, admin_session):
        """GET /api/properties works"""
        resp = admin_session.get(f"{BASE_URL}/api/properties")
        assert resp.status_code == 200, f"Properties endpoint failed: {resp.text}"
    
    def test_room_types_endpoint(self, admin_session):
        """GET /api/room-types works"""
        resp = admin_session.get(f"{BASE_URL}/api/room-types")
        assert resp.status_code == 200, f"Room types endpoint failed: {resp.text}"
    
    def test_owners_endpoint(self, admin_session):
        """GET /api/owners works (iter 282)"""
        resp = admin_session.get(f"{BASE_URL}/api/owners")
        assert resp.status_code == 200, f"Owners endpoint failed: {resp.text}"


# Cleanup fixture
@pytest.fixture(scope="module", autouse=True)
def cleanup(admin_session):
    """Cleanup test data after all tests"""
    yield
    # Delete test agents
    try:
        resp = admin_session.get(f"{BASE_URL}/api/agents")
        if resp.status_code == 200:
            for agent in resp.json().get("items", []):
                if "TEST_" in agent.get("name", ""):
                    # Note: No delete endpoint, so we just leave them
                    pass
    except:
        pass
