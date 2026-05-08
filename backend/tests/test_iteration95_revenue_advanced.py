"""
Iteration 95 - Revenue Management Advanced Module Testing
Tests: Enhanced Dashboard, Smart Pricing, Approvals, Segments, Rate Resolver, Setup Wizard
Plus: 7 Pricing Strategy sub-tabs (Rooms Setup, DOW, Monthly, Occupancy, Min Stay, Lead Time, Surge Protection)
"""
import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    BASE_URL = "https://review-hub-108.preview.emergentagent.com"

# Test credentials
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"


class TestRevenueAuth:
    """Authentication for Revenue module tests"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get admin auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        # Token field is "token" in this API
        assert "token" in data, f"No token in response: {data}"
        return data["token"]
    
    @pytest.fixture(scope="class")
    def auth_headers(self, auth_token):
        """Auth headers for API calls"""
        return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


class TestEnhancedDashboard(TestRevenueAuth):
    """Enhanced Dashboard API tests"""
    
    def test_enhanced_dashboard_all_properties(self, auth_headers):
        """GET /api/revenue/dashboard-enhanced/all - Returns enhanced KPIs"""
        response = requests.get(f"{BASE_URL}/api/revenue/dashboard-enhanced/all", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        # Verify KPIs structure
        assert "kpis" in data
        kpis = data["kpis"]
        assert "today_occupancy" in kpis
        assert "rooms_occupied" in kpis
        assert "total_rooms" in kpis
        assert "adr" in kpis
        assert "revpar" in kpis
        
        # Verify 7-day occupancy
        assert "seven_day_occupancy" in data
        assert len(data["seven_day_occupancy"]) == 7
        
        # Verify demand index
        assert "demand" in data
        assert "score" in data["demand"]
        assert "label" in data["demand"]
        
        # Verify booking pace
        assert "booking_pace" in data
        assert "count" in data["booking_pace"]
        
        # Verify AI confidence
        assert "ai_confidence" in data
        assert "pct" in data["ai_confidence"]
        
        # Verify readiness
        assert "readiness" in data
        assert "pct" in data["readiness"]
        assert "items" in data["readiness"]
        
        # Verify opportunities and risk alerts
        assert "opportunities" in data
        assert "risk_alerts" in data
        
        print(f"Enhanced Dashboard: Occupancy={kpis['today_occupancy']}%, ADR=£{kpis['adr']}, RevPAR=£{kpis['revpar']}")
        print(f"Demand Index: {data['demand']['score']} ({data['demand']['label']})")
        print(f"AI Confidence: {data['ai_confidence']['pct']}%")
        print(f"Revenue Readiness: {data['readiness']['pct']}%")
    
    def test_enhanced_dashboard_specific_property(self, auth_headers):
        """GET /api/revenue/dashboard-enhanced/{property_id} - Returns property-specific KPIs"""
        response = requests.get(f"{BASE_URL}/api/revenue/dashboard-enhanced/aldgate-flats", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "kpis" in data
        assert "readiness" in data


class TestSmartPricing(TestRevenueAuth):
    """Smart Pricing API tests"""
    
    def test_smart_pricing_get(self, auth_headers):
        """GET /api/revenue/smart-pricing/all - Returns smart pricing data"""
        response = requests.get(f"{BASE_URL}/api/revenue/smart-pricing/all", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        # Verify structure
        assert "system_active" in data
        assert "currency" in data
        assert "kpis" in data
        
        # Verify KPIs
        kpis = data["kpis"]
        assert "avg_daily_rate" in kpis
        assert "occupancy_forecast" in kpis
        assert "projected_revenue" in kpis
        assert "strategy_mode" in kpis
        assert "aggressiveness" in kpis
        
        # Verify price evolution (30 days)
        assert "price_evolution" in data
        assert len(data["price_evolution"]) == 30
        for day in data["price_evolution"][:3]:
            assert "date" in day
            assert "recommended" in day
            assert "min_limit" in day
            assert "max_limit" in day
            assert "occupancy" in day
        
        # Verify recommendation calendar
        assert "recommendation_calendar" in data
        
        # Verify AI insights
        assert "ai_insights" in data
        
        print(f"Smart Pricing: ADR=£{kpis['avg_daily_rate']}, Forecast={kpis['occupancy_forecast']}%, Mode={kpis['strategy_mode']}")
        print(f"Price Evolution: {len(data['price_evolution'])} days")
        print(f"AI Insights: {len(data['ai_insights'])} insights")
    
    def test_smart_pricing_recalculate(self, auth_headers):
        """POST /api/revenue/smart-pricing/all/recalculate - Generates new recommendations"""
        response = requests.post(f"{BASE_URL}/api/revenue/smart-pricing/all/recalculate", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "count" in data
        print(f"Recalculate: {data['message']}, Count={data['count']}")


class TestApprovals(TestRevenueAuth):
    """Approvals API tests"""
    
    def test_approvals_get(self, auth_headers):
        """GET /api/revenue/approvals/all - Returns approvals list"""
        response = requests.get(f"{BASE_URL}/api/revenue/approvals/all", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        assert "items" in data
        assert "counts" in data
        assert "draft" in data["counts"]
        assert "accepted" in data["counts"]
        assert "rejected" in data["counts"]
        
        print(f"Approvals: Draft={data['counts']['draft']}, Accepted={data['counts']['accepted']}, Rejected={data['counts']['rejected']}")
    
    def test_approvals_filter_by_status(self, auth_headers):
        """GET /api/revenue/approvals/all?status=draft - Filter by status"""
        response = requests.get(f"{BASE_URL}/api/revenue/approvals/all?status=draft", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        # All items should be draft
        for item in data["items"]:
            assert item["status"] == "draft"


class TestSegments(TestRevenueAuth):
    """Segments CRUD tests"""
    
    def test_segments_get(self, auth_headers):
        """GET /api/revenue/segments/all - Returns segments list"""
        response = requests.get(f"{BASE_URL}/api/revenue/segments/all", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        print(f"Segments: {len(data['items'])} segments")
    
    def test_segments_create_and_delete(self, auth_headers):
        """POST /api/revenue/segments/all - Create segment, then DELETE"""
        # Create
        segment_data = {
            "code": "TEST_MOBILE",
            "name": "Test Mobile Segment",
            "description": "Test segment for mobile users",
            "priority": 5
        }
        response = requests.post(f"{BASE_URL}/api/revenue/segments/all", json=segment_data, headers=auth_headers)
        assert response.status_code == 200
        created = response.json()
        assert created["code"] == "TEST_MOBILE"
        assert created["name"] == "Test Mobile Segment"
        assert "id" in created
        segment_id = created["id"]
        print(f"Created segment: {segment_id}")
        
        # Verify in list
        response = requests.get(f"{BASE_URL}/api/revenue/segments/all", headers=auth_headers)
        assert response.status_code == 200
        items = response.json()["items"]
        assert any(s["id"] == segment_id for s in items)
        
        # Delete
        response = requests.delete(f"{BASE_URL}/api/revenue/segments/{segment_id}", headers=auth_headers)
        assert response.status_code == 200
        print(f"Deleted segment: {segment_id}")


class TestRateResolver(TestRevenueAuth):
    """Rate Resolver API tests"""
    
    def test_rate_resolver(self, auth_headers):
        """POST /api/revenue/rate-resolver - Resolve rate with layers"""
        today = datetime.now().strftime("%Y-%m-%d")
        response = requests.post(f"{BASE_URL}/api/revenue/rate-resolver", json={
            "property_id": "all",
            "date": today,
            "room_category": "",
            "rate_plan": "base"
        }, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        assert "resolved_rate" in data
        assert "room_type" in data
        assert "date" in data
        assert "layers" in data
        assert "guardrails" in data
        
        # Verify layers structure
        assert len(data["layers"]) >= 1
        for layer in data["layers"]:
            assert "name" in layer
            assert "value" in layer
            assert "adjustment" in layer
        
        # Verify guardrails
        assert "min" in data["guardrails"]
        assert "max" in data["guardrails"]
        
        print(f"Resolved Rate: £{data['resolved_rate']} for {data['room_type']} on {data['date']}")
        print(f"Layers: {len(data['layers'])}, Guardrails: £{data['guardrails']['min']}-£{data['guardrails']['max']}")


class TestSetupWizard(TestRevenueAuth):
    """Setup Wizard API tests"""
    
    def test_setup_wizard_get(self, auth_headers):
        """GET /api/revenue/setup-wizard/all - Returns wizard state"""
        response = requests.get(f"{BASE_URL}/api/revenue/setup-wizard/all", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        assert "property_id" in data
        assert "steps" in data
        assert "checklist" in data
        
        # Verify 6 steps
        assert len(data["steps"]) == 6
        for step in data["steps"]:
            assert "id" in step
            assert "name" in step
            assert "completed" in step
        
        # Verify checklist items
        assert len(data["checklist"]) >= 5
        for item in data["checklist"]:
            assert "key" in item
            assert "label" in item
            assert "status" in item
        
        completed = sum(1 for s in data["steps"] if s["completed"])
        print(f"Setup Wizard: {completed}/{len(data['steps'])} steps completed")
        print(f"Checklist: {len(data['checklist'])} items")


class TestPricingStrategyFull(TestRevenueAuth):
    """Full Pricing Strategy API tests (7 sub-tabs)"""
    
    def test_pricing_strategy_full_get(self, auth_headers):
        """GET /api/revenue/pricing-strategy-full/all - Returns full strategy"""
        response = requests.get(f"{BASE_URL}/api/revenue/pricing-strategy-full/all", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        assert "rooms_setup" in data
        assert "strategy" in data
        assert "room_types" in data
        
        # Verify strategy structure
        strategy = data["strategy"]
        assert "property_id" in strategy
        
        print(f"Pricing Strategy: {len(data['rooms_setup'])} rooms, {len(data['room_types'])} room types")
    
    def test_pricing_strategy_dow_save(self, auth_headers):
        """PUT /api/revenue/pricing-strategy/all - Save DOW adjustments"""
        dow_data = {
            "dow_adjustments": {
                "mon": 0,
                "tue": 0,
                "wed": 0,
                "thu": 5,
                "fri": 15,
                "sat": 20,
                "sun": 10
            }
        }
        response = requests.put(f"{BASE_URL}/api/revenue/pricing-strategy/all", json=dow_data, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "dow_adjustments" in data
        assert data["dow_adjustments"]["fri"] == 15
        assert data["dow_adjustments"]["sat"] == 20
        print(f"DOW Adjustments saved: Fri={data['dow_adjustments']['fri']}%, Sat={data['dow_adjustments']['sat']}%")
    
    def test_pricing_strategy_monthly_save(self, auth_headers):
        """PUT /api/revenue/pricing-strategy/all - Save Monthly adjustments"""
        monthly_data = {
            "monthly_adjustments": {
                "jan": -10,
                "feb": -5,
                "mar": 0,
                "apr": 5,
                "may": 10,
                "jun": 15,
                "jul": 20,
                "aug": 20,
                "sep": 10,
                "oct": 5,
                "nov": 0,
                "dec": 25
            }
        }
        response = requests.put(f"{BASE_URL}/api/revenue/pricing-strategy/all", json=monthly_data, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "monthly_adjustments" in data
        assert data["monthly_adjustments"]["dec"] == 25
        print(f"Monthly Adjustments saved: Dec={data['monthly_adjustments']['dec']}%")
    
    def test_pricing_strategy_lead_time_save(self, auth_headers):
        """PUT /api/revenue/pricing-strategy/all - Save Lead Time adjustments"""
        lead_time_data = {
            "lead_time_adjustments": {
                "6_months_plus": -15,
                "3_months_plus": -10,
                "1_5_3_months": -5,
                "4_6_weeks": 0,
                "2_4_weeks": 5,
                "1_2_weeks": 10,
                "4_7_days": 15,
                "2_3_days": 20,
                "last_day": 25
            }
        }
        response = requests.put(f"{BASE_URL}/api/revenue/pricing-strategy/all", json=lead_time_data, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "lead_time_adjustments" in data
        assert data["lead_time_adjustments"]["last_day"] == 25
        print(f"Lead Time saved: Last Day={data['lead_time_adjustments']['last_day']}%")
    
    def test_pricing_strategy_occupancy_save(self, auth_headers):
        """PUT /api/revenue/pricing-strategy/all - Save Target Occupancy and Aggressiveness"""
        occ_data = {
            "target_occupancy": {
                "jan": 50, "feb": 55, "mar": 60, "apr": 65,
                "may": 70, "jun": 75, "jul": 80, "aug": 80,
                "sep": 70, "oct": 65, "nov": 55, "dec": 60
            },
            "aggressiveness": 1.2
        }
        response = requests.put(f"{BASE_URL}/api/revenue/pricing-strategy/all", json=occ_data, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "target_occupancy" in data
        assert "aggressiveness" in data
        assert data["aggressiveness"] == 1.2
        print(f"Occupancy Strategy saved: Aggressiveness={data['aggressiveness']}x")
    
    def test_pricing_strategy_min_stay_save(self, auth_headers):
        """PUT /api/revenue/pricing-strategy/all - Save Min Stay settings"""
        min_stay_data = {
            "min_stay_settings": {
                "min_stay": 2,
                "orphan_gap_enabled": True,
                "fixed_override": False,
                "room_types": []
            }
        }
        response = requests.put(f"{BASE_URL}/api/revenue/pricing-strategy/all", json=min_stay_data, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "min_stay_settings" in data
        assert data["min_stay_settings"]["min_stay"] == 2
        print(f"Min Stay saved: {data['min_stay_settings']['min_stay']} nights")
    
    def test_pricing_strategy_surge_save(self, auth_headers):
        """PUT /api/revenue/pricing-strategy/all - Save Surge Protection settings"""
        surge_data = {
            "surge_protection": {
                "enabled": True,
                "booking_threshold": 50,
                "days_to_go": 14,
                "recipients": [],
                "dont_send_email": False
            }
        }
        response = requests.put(f"{BASE_URL}/api/revenue/pricing-strategy/all", json=surge_data, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "surge_protection" in data
        assert data["surge_protection"]["enabled"] == True
        assert data["surge_protection"]["booking_threshold"] == 50
        print(f"Surge Protection saved: Threshold={data['surge_protection']['booking_threshold']} bookings")


class TestRateCalendar(TestRevenueAuth):
    """Rate Calendar API tests"""
    
    def test_rate_calendar_get(self, auth_headers):
        """GET /api/revenue/rate-calendar/aldgate-flats - Returns calendar data"""
        response = requests.get(f"{BASE_URL}/api/revenue/rate-calendar/aldgate-flats", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        assert "year" in data
        assert "month" in data
        assert "month_name" in data
        assert "room_type" in data
        assert "room_types" in data
        assert "total_rooms" in data
        assert "performance" in data
        assert "days" in data
        
        # Verify days structure
        assert len(data["days"]) >= 28  # At least 28 days in a month
        for day in data["days"][:3]:
            assert "date" in day
            assert "day" in day
            assert "dow" in day
            assert "occupancy" in day
            assert "recommended_rate" in day
            assert "pms_rate" in day
        
        print(f"Rate Calendar: {data['month_name']} {data['year']}, {len(data['days'])} days")
        print(f"Performance: Occupancy={data['performance']['occupancy']}%, Target={data['performance']['target']}%")


class TestDashboardKPIs(TestRevenueAuth):
    """Original Dashboard KPIs tests"""
    
    def test_dashboard_kpis(self, auth_headers):
        """GET /api/revenue/dashboard/all - Returns basic KPIs"""
        response = requests.get(f"{BASE_URL}/api/revenue/dashboard/all", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        assert "last_month" in data
        assert "current_month" in data
        assert "next_month" in data
        assert "properties_count" in data
        
        # Verify month structure
        for key in ["last_month", "current_month", "next_month"]:
            month = data[key]
            assert "revenue" in month
            assert "occupancy" in month
            assert "adr" in month
            assert "label" in month
            assert "yoy" in month
        
        print(f"Dashboard KPIs: {data['properties_count']} properties")
        print(f"Current Month: £{data['current_month']['revenue']}, {data['current_month']['occupancy']}% occ")


class TestHeatmapAndYOY(TestRevenueAuth):
    """Heatmap and YOY Tables tests"""
    
    def test_heatmap(self, auth_headers):
        """GET /api/revenue/heatmap - Returns occupancy heatmap"""
        response = requests.get(f"{BASE_URL}/api/revenue/heatmap", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        assert "dates" in data
        assert "properties" in data
        assert len(data["dates"]) == 30  # Default 30 days
        
        for prop in data["properties"]:
            assert "property_id" in prop
            assert "name" in prop
            assert "daily" in prop
        
        print(f"Heatmap: {len(data['properties'])} properties, {len(data['dates'])} days")
    
    def test_yoy_tables(self, auth_headers):
        """GET /api/revenue/yoy-tables - Returns YOY comparison"""
        response = requests.get(f"{BASE_URL}/api/revenue/yoy-tables", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        for prop in data:
            assert "property_id" in prop
            assert "name" in prop
            assert "months" in prop
            assert len(prop["months"]) == 6  # First 6 months
        
        print(f"YOY Tables: {len(data)} properties")


class TestAuthRequired(TestRevenueAuth):
    """Test that all endpoints require authentication"""
    
    def test_endpoints_require_auth(self):
        """All revenue endpoints should return 401 without auth"""
        endpoints = [
            "/api/revenue/dashboard/all",
            "/api/revenue/dashboard-enhanced/all",
            "/api/revenue/smart-pricing/all",
            "/api/revenue/approvals/all",
            "/api/revenue/segments/all",
            "/api/revenue/setup-wizard/all",
            "/api/revenue/rate-calendar/aldgate-flats",
            "/api/revenue/heatmap",
            "/api/revenue/yoy-tables",
            "/api/revenue/pricing-strategy/all",
            "/api/revenue/pricing-strategy-full/all",
        ]
        
        for endpoint in endpoints:
            response = requests.get(f"{BASE_URL}{endpoint}")
            assert response.status_code in [401, 403], f"{endpoint} should require auth, got {response.status_code}"
        
        print(f"Auth required: All {len(endpoints)} endpoints protected")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
