"""
Iteration 292 - Revenue Management Module Full Regression Test
Tests ALL Revenue Management endpoints including:
- Revenue dashboard, forecasting, segments, smart-pricing
- Revenue intelligence (forecast, booking-pace, recommendations)
- Competitors, compset-intel, demand-radar, playbooks, experiments
- Parity, overbooking, profit-os, distribution, rate-calendar
- Rate scraper, approvals, historical-pricing, pricing-strategy
- Analytics (budget, performance, pickup)
- Rates grid, win/loss, rate-manager
- Forecast endpoints (occupancy, accuracy, pace, demand-calendar, horizon)
- Pricing explain, auto-apply rules, smart-rate-control
- Market Robot (config, supply, logs, adjustments, competitors, competitor-prices)
- Market Robot new features (competitor-pulse, fleet-pulse, close-gap)
- Channel revenue, OTA forecast, logbook, loyalty, parity-defender
- RBAC tests (receptionist should get 403 on admin endpoints)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
PROPERTY_ID = "aldgate-flats"  # Has 5 competitors seeded
PROPERTY_ID_GAP = "camden-suites"  # Has biggest gap (-53.7%)

# Test credentials
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"
RECEPTIONIST_EMAIL = "testrecep@hotelbox.com"
RECEPTIONIST_PASSWORD = "Test2026!"


@pytest.fixture(scope="module")
def admin_token():
    """Get admin auth token"""
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    }, timeout=30)
    if resp.status_code == 200:
        return resp.json().get("token")
    pytest.skip(f"Admin login failed: {resp.status_code} - {resp.text[:200]}")


@pytest.fixture(scope="module")
def receptionist_token():
    """Get receptionist auth token for RBAC tests"""
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": RECEPTIONIST_EMAIL,
        "password": RECEPTIONIST_PASSWORD
    }, timeout=30)
    if resp.status_code == 200:
        return resp.json().get("token")
    pytest.skip(f"Receptionist login failed: {resp.status_code}")


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def receptionist_headers(receptionist_token):
    return {"Authorization": f"Bearer {receptionist_token}", "Content-Type": "application/json"}


# ============================================================================
# SECTION 1: Core Revenue Dashboard Endpoints
# ============================================================================
class TestRevenueDashboard:
    """Revenue dashboard and enhanced dashboard endpoints"""
    
    def test_revenue_dashboard(self, admin_headers):
        """GET /api/revenue/dashboard/{property_id}"""
        resp = requests.get(f"{BASE_URL}/api/revenue/dashboard/{PROPERTY_ID}", headers=admin_headers, timeout=30)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        assert "property_id" in data or "revenue" in data or "occupancy" in data or isinstance(data, dict)
    
    def test_revenue_dashboard_enhanced(self, admin_headers):
        """GET /api/revenue/dashboard-enhanced/{property_id}"""
        resp = requests.get(f"{BASE_URL}/api/revenue/dashboard-enhanced/{PROPERTY_ID}", headers=admin_headers, timeout=30)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
    
    def test_revenue_forecasting(self, admin_headers):
        """GET /api/revenue/forecasting/{property_id}"""
        resp = requests.get(f"{BASE_URL}/api/revenue/forecasting/{PROPERTY_ID}", headers=admin_headers, timeout=30)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
    
    def test_revenue_segments(self, admin_headers):
        """GET /api/revenue/segments/{property_id}"""
        resp = requests.get(f"{BASE_URL}/api/revenue/segments/{PROPERTY_ID}", headers=admin_headers, timeout=30)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
    
    def test_revenue_setup_wizard(self, admin_headers):
        """GET /api/revenue/setup-wizard/{property_id}"""
        resp = requests.get(f"{BASE_URL}/api/revenue/setup-wizard/{PROPERTY_ID}", headers=admin_headers, timeout=30)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
    
    def test_revenue_smart_pricing(self, admin_headers):
        """GET /api/revenue/smart-pricing/{property_id}"""
        resp = requests.get(f"{BASE_URL}/api/revenue/smart-pricing/{PROPERTY_ID}", headers=admin_headers, timeout=30)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"


# ============================================================================
# SECTION 2: Revenue Intelligence Endpoints
# ============================================================================
class TestRevenueIntelligence:
    """Revenue intelligence forecast, booking-pace, recommendations"""
    
    def test_intelligence_forecast(self, admin_headers):
        """GET /api/revenue/intelligence/{property_id}/forecast"""
        resp = requests.get(f"{BASE_URL}/api/revenue/intelligence/{PROPERTY_ID}/forecast", headers=admin_headers, timeout=30)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
    
    def test_intelligence_booking_pace(self, admin_headers):
        """GET /api/revenue/intelligence/{property_id}/booking-pace"""
        resp = requests.get(f"{BASE_URL}/api/revenue/intelligence/{PROPERTY_ID}/booking-pace", headers=admin_headers, timeout=30)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
    
    def test_intelligence_recommendations(self, admin_headers):
        """GET /api/revenue/intelligence/{property_id}/recommendations"""
        resp = requests.get(f"{BASE_URL}/api/revenue/intelligence/{PROPERTY_ID}/recommendations", headers=admin_headers, timeout=30)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"


# ============================================================================
# SECTION 3: Competitors and Compset Endpoints
# ============================================================================
class TestCompetitorsCompset:
    """Competitors, compset-intel, demand-radar, playbooks, experiments"""
    
    def test_revenue_competitors(self, admin_headers):
        """GET /api/revenue/competitors/{property_id}"""
        resp = requests.get(f"{BASE_URL}/api/revenue/competitors/{PROPERTY_ID}", headers=admin_headers, timeout=30)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
    
    def test_revenue_compset_intel(self, admin_headers):
        """GET /api/revenue/compset-intel/{property_id}"""
        resp = requests.get(f"{BASE_URL}/api/revenue/compset-intel/{PROPERTY_ID}", headers=admin_headers, timeout=30)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
    
    def test_revenue_demand_radar(self, admin_headers):
        """GET /api/revenue/demand-radar/{property_id}"""
        resp = requests.get(f"{BASE_URL}/api/revenue/demand-radar/{PROPERTY_ID}", headers=admin_headers, timeout=30)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
    
    def test_revenue_playbooks(self, admin_headers):
        """GET /api/revenue/playbooks/{property_id}"""
        resp = requests.get(f"{BASE_URL}/api/revenue/playbooks/{PROPERTY_ID}", headers=admin_headers, timeout=30)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
    
    def test_revenue_experiments(self, admin_headers):
        """GET /api/revenue/experiments/{property_id}"""
        resp = requests.get(f"{BASE_URL}/api/revenue/experiments/{PROPERTY_ID}", headers=admin_headers, timeout=30)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"


# ============================================================================
# SECTION 4: Parity, Overbooking, Profit-OS, Distribution
# ============================================================================
class TestParityOverbookingDistribution:
    """Parity, overbooking, profit-os, distribution, rate-calendar"""
    
    def test_revenue_parity(self, admin_headers):
        """GET /api/revenue/parity/{property_id}"""
        resp = requests.get(f"{BASE_URL}/api/revenue/parity/{PROPERTY_ID}", headers=admin_headers, timeout=30)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
    
    def test_revenue_overbooking(self, admin_headers):
        """GET /api/revenue/overbooking/{property_id}"""
        resp = requests.get(f"{BASE_URL}/api/revenue/overbooking/{PROPERTY_ID}", headers=admin_headers, timeout=30)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
    
    def test_revenue_profit_os(self, admin_headers):
        """GET /api/revenue/profit-os/{property_id}"""
        resp = requests.get(f"{BASE_URL}/api/revenue/profit-os/{PROPERTY_ID}", headers=admin_headers, timeout=30)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
    
    def test_revenue_distribution(self, admin_headers):
        """GET /api/revenue/distribution/{property_id}"""
        resp = requests.get(f"{BASE_URL}/api/revenue/distribution/{PROPERTY_ID}", headers=admin_headers, timeout=30)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
    
    def test_revenue_rate_calendar(self, admin_headers):
        """GET /api/revenue/rate-calendar/{property_id}"""
        resp = requests.get(f"{BASE_URL}/api/revenue/rate-calendar/{PROPERTY_ID}", headers=admin_headers, timeout=30)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"


# ============================================================================
# SECTION 5: Rate Scraper, Approvals, Historical Pricing, Pricing Strategy
# ============================================================================
class TestRateScraperApprovals:
    """Rate scraper, approvals, historical-pricing, pricing-strategy"""
    
    def test_revenue_rate_scraper(self, admin_headers):
        """GET /api/revenue/rate-scraper/{property_id}"""
        resp = requests.get(f"{BASE_URL}/api/revenue/rate-scraper/{PROPERTY_ID}", headers=admin_headers, timeout=30)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
    
    def test_revenue_approvals(self, admin_headers):
        """GET /api/revenue/approvals/{property_id}"""
        resp = requests.get(f"{BASE_URL}/api/revenue/approvals/{PROPERTY_ID}", headers=admin_headers, timeout=30)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
    
    def test_revenue_historical_pricing(self, admin_headers):
        """GET /api/revenue/historical-pricing/{property_id}"""
        resp = requests.get(f"{BASE_URL}/api/revenue/historical-pricing/{PROPERTY_ID}", headers=admin_headers, timeout=30)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
    
    def test_revenue_pricing_strategy(self, admin_headers):
        """GET /api/revenue/pricing-strategy/{property_id}"""
        resp = requests.get(f"{BASE_URL}/api/revenue/pricing-strategy/{PROPERTY_ID}", headers=admin_headers, timeout=30)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
    
    def test_revenue_pricing_strategy_full(self, admin_headers):
        """GET /api/revenue/pricing-strategy-full/{property_id}"""
        resp = requests.get(f"{BASE_URL}/api/revenue/pricing-strategy-full/{PROPERTY_ID}", headers=admin_headers, timeout=30)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
    
    def test_revenue_action_center(self, admin_headers):
        """GET /api/revenue/action-center/{property_id}"""
        resp = requests.get(f"{BASE_URL}/api/revenue/action-center/{PROPERTY_ID}", headers=admin_headers, timeout=30)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"


# ============================================================================
# SECTION 6: Revenue Analytics (Budget, Performance, Pickup)
# ============================================================================
class TestRevenueAnalytics:
    """Revenue analytics endpoints"""
    
    def test_analytics_budget(self, admin_headers):
        """GET /api/revenue/analytics/budget/{property_id}"""
        resp = requests.get(f"{BASE_URL}/api/revenue/analytics/budget/{PROPERTY_ID}", headers=admin_headers, timeout=30)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
    
    def test_analytics_performance(self, admin_headers):
        """GET /api/revenue/analytics/performance/{property_id}"""
        resp = requests.get(f"{BASE_URL}/api/revenue/analytics/performance/{PROPERTY_ID}", headers=admin_headers, timeout=30)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
    
    def test_analytics_pickup(self, admin_headers):
        """GET /api/revenue/analytics/pickup/{property_id}"""
        resp = requests.get(f"{BASE_URL}/api/revenue/analytics/pickup/{PROPERTY_ID}", headers=admin_headers, timeout=30)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"


# ============================================================================
# SECTION 7: Rates Grid and Rate Manager
# ============================================================================
class TestRatesGrid:
    """Rates grid, insights, explain, win/loss, rate-manager"""
    
    def test_rates_grid(self, admin_headers):
        """GET /api/rates/grid/{property_id}"""
        resp = requests.get(f"{BASE_URL}/api/rates/grid/{PROPERTY_ID}", headers=admin_headers, timeout=30)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
    
    def test_rates_grid_insights(self, admin_headers):
        """GET /api/rates/grid/insights/{property_id}"""
        resp = requests.get(f"{BASE_URL}/api/rates/grid/insights/{PROPERTY_ID}", headers=admin_headers, timeout=30)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
    
    def test_rates_grid_explain(self, admin_headers):
        """GET /api/rates/grid/explain/{property_id}/{date}"""
        from datetime import datetime, timedelta
        test_date = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
        resp = requests.get(f"{BASE_URL}/api/rates/grid/explain/{PROPERTY_ID}/{test_date}", headers=admin_headers, timeout=30)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
    
    def test_rates_winloss(self, admin_headers):
        """GET /api/rates/winloss/{property_id}"""
        resp = requests.get(f"{BASE_URL}/api/rates/winloss/{PROPERTY_ID}", headers=admin_headers, timeout=30)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
    
    def test_rate_manager_plans(self, admin_headers):
        """GET /api/rate-manager/plans/{property_id}"""
        resp = requests.get(f"{BASE_URL}/api/rate-manager/plans/{PROPERTY_ID}", headers=admin_headers, timeout=30)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
    
    def test_rate_manager_seasons(self, admin_headers):
        """GET /api/rate-manager/seasons/{property_id}"""
        resp = requests.get(f"{BASE_URL}/api/rate-manager/seasons/{PROPERTY_ID}", headers=admin_headers, timeout=30)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"


# ============================================================================
# SECTION 8: Forecast Endpoints
# ============================================================================
class TestForecast:
    """Forecast occupancy, accuracy, pace, demand-calendar, horizon"""
    
    def test_forecast_occupancy(self, admin_headers):
        """GET /api/forecast/occupancy/{property_id} - RECENTLY FIXED (round(None) crash)"""
        resp = requests.get(f"{BASE_URL}/api/forecast/occupancy/{PROPERTY_ID}", headers=admin_headers, timeout=30)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        # Verify the fix - should not crash on None values
        assert isinstance(data, (dict, list)), "Response should be dict or list"
    
    def test_forecast_accuracy(self, admin_headers):
        """GET /api/forecast/accuracy/{property_id}"""
        resp = requests.get(f"{BASE_URL}/api/forecast/accuracy/{PROPERTY_ID}", headers=admin_headers, timeout=30)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
    
    def test_forecast_pace(self, admin_headers):
        """GET /api/forecast/pace/{property_id}"""
        resp = requests.get(f"{BASE_URL}/api/forecast/pace/{PROPERTY_ID}", headers=admin_headers, timeout=30)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
    
    def test_forecast_v2_demand_calendar(self, admin_headers):
        """GET /api/forecast-v2/demand-calendar/{property_id}"""
        resp = requests.get(f"{BASE_URL}/api/forecast-v2/demand-calendar/{PROPERTY_ID}", headers=admin_headers, timeout=30)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
    
    def test_forecast_v2_horizon(self, admin_headers):
        """GET /api/forecast-v2/horizon/{property_id}"""
        resp = requests.get(f"{BASE_URL}/api/forecast-v2/horizon/{PROPERTY_ID}", headers=admin_headers, timeout=30)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"


# ============================================================================
# SECTION 9: Pricing Explain and Auto-Apply
# ============================================================================
class TestPricingExplain:
    """Pricing explain dashboard, history, auto-apply rules, smart-rate-control"""
    
    def test_pricing_explain_dashboard(self, admin_headers):
        """GET /api/pricing/explain/dashboard/{property_id}"""
        resp = requests.get(f"{BASE_URL}/api/pricing/explain/dashboard/{PROPERTY_ID}", headers=admin_headers, timeout=30)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
    
    def test_pricing_explain_history(self, admin_headers):
        """GET /api/pricing/explain/history/{property_id}"""
        resp = requests.get(f"{BASE_URL}/api/pricing/explain/history/{PROPERTY_ID}", headers=admin_headers, timeout=30)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
    
    def test_pricing_auto_apply_rules(self, admin_headers):
        """GET /api/pricing/auto-apply/rules/{property_id}"""
        resp = requests.get(f"{BASE_URL}/api/pricing/auto-apply/rules/{PROPERTY_ID}", headers=admin_headers, timeout=30)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
    
    def test_smart_rate_control_calendar(self, admin_headers):
        """GET /api/smart-rate-control/{property_id}/calendar"""
        resp = requests.get(f"{BASE_URL}/api/smart-rate-control/{PROPERTY_ID}/calendar", headers=admin_headers, timeout=30)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"


# ============================================================================
# SECTION 10: Market Robot Core Endpoints
# ============================================================================
class TestMarketRobotCore:
    """Market Robot config, supply, logs, adjustments, competitors, competitor-prices"""
    
    def test_market_robot_config(self, admin_headers):
        """GET /api/revenue/market-robot/{property_id}/config"""
        resp = requests.get(f"{BASE_URL}/api/revenue/market-robot/{PROPERTY_ID}/config", headers=admin_headers, timeout=30)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
    
    def test_market_robot_supply(self, admin_headers):
        """GET /api/revenue/market-robot/{property_id}/supply"""
        resp = requests.get(f"{BASE_URL}/api/revenue/market-robot/{PROPERTY_ID}/supply", headers=admin_headers, timeout=30)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
    
    def test_market_robot_logs(self, admin_headers):
        """GET /api/revenue/market-robot/{property_id}/logs"""
        resp = requests.get(f"{BASE_URL}/api/revenue/market-robot/{PROPERTY_ID}/logs", headers=admin_headers, timeout=30)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
    
    def test_market_robot_adjustments(self, admin_headers):
        """GET /api/revenue/market-robot/{property_id}/adjustments"""
        resp = requests.get(f"{BASE_URL}/api/revenue/market-robot/{PROPERTY_ID}/adjustments", headers=admin_headers, timeout=30)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
    
    def test_market_robot_competitors(self, admin_headers):
        """GET /api/revenue/market-robot/{property_id}/competitors"""
        resp = requests.get(f"{BASE_URL}/api/revenue/market-robot/{PROPERTY_ID}/competitors", headers=admin_headers, timeout=30)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        # aldgate-flats should have 5 competitors seeded
        if isinstance(data, list):
            print(f"Found {len(data)} competitors for {PROPERTY_ID}")
    
    def test_market_robot_competitor_prices(self, admin_headers):
        """GET /api/revenue/market-robot/{property_id}/competitor-prices"""
        resp = requests.get(f"{BASE_URL}/api/revenue/market-robot/{PROPERTY_ID}/competitor-prices", headers=admin_headers, timeout=30)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"


# ============================================================================
# SECTION 11: Market Robot New Features (Iter 295-299)
# ============================================================================
class TestMarketRobotNewFeatures:
    """Market Robot competitor-pulse, fleet-pulse, close-gap (Iter 295-299)"""
    
    def test_competitor_pulse(self, admin_headers):
        """GET /api/revenue/market-robot/{property_id}/competitor-pulse?days=14"""
        resp = requests.get(f"{BASE_URL}/api/revenue/market-robot/{PROPERTY_ID}/competitor-pulse?days=14", headers=admin_headers, timeout=30)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        assert isinstance(data, dict), "Response should be a dict"
        print(f"Competitor pulse data keys: {list(data.keys())[:10]}")
    
    def test_fleet_pulse(self, admin_headers):
        """GET /api/revenue/market-robot/fleet-pulse?days=14"""
        resp = requests.get(f"{BASE_URL}/api/revenue/market-robot/fleet-pulse?days=14", headers=admin_headers, timeout=30)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        assert isinstance(data, (dict, list)), "Response should be dict or list"
        print(f"Fleet pulse response type: {type(data).__name__}")
    
    def test_close_gap_dry_run_full(self, admin_headers):
        """POST /api/revenue/market-robot/{property_id}/close-gap with strategy=full, dry_run=true"""
        resp = requests.post(
            f"{BASE_URL}/api/revenue/market-robot/{PROPERTY_ID_GAP}/close-gap",
            headers=admin_headers,
            json={"strategy": "full", "dry_run": True},
            timeout=30
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        assert "dry_run" in data or "preview" in data or "changes" in data or isinstance(data, dict)
    
    def test_close_gap_dry_run_half(self, admin_headers):
        """POST /api/revenue/market-robot/{property_id}/close-gap with strategy=half, dry_run=true"""
        resp = requests.post(
            f"{BASE_URL}/api/revenue/market-robot/{PROPERTY_ID_GAP}/close-gap",
            headers=admin_headers,
            json={"strategy": "half", "dry_run": True},
            timeout=30
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
    
    def test_close_gap_dry_run_floor(self, admin_headers):
        """POST /api/revenue/market-robot/{property_id}/close-gap with strategy=floor, dry_run=true"""
        resp = requests.post(
            f"{BASE_URL}/api/revenue/market-robot/{PROPERTY_ID_GAP}/close-gap",
            headers=admin_headers,
            json={"strategy": "floor", "dry_run": True},
            timeout=30
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
    
    def test_close_gap_dry_run_value(self, admin_headers):
        """POST /api/revenue/market-robot/{property_id}/close-gap with strategy=value, dry_run=true"""
        resp = requests.post(
            f"{BASE_URL}/api/revenue/market-robot/{PROPERTY_ID_GAP}/close-gap",
            headers=admin_headers,
            json={"strategy": "value", "dry_run": True},
            timeout=30
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
    
    def test_market_robot_health(self, admin_headers):
        """GET /api/revenue/market-robot/health"""
        resp = requests.get(f"{BASE_URL}/api/revenue/market-robot/health", headers=admin_headers, timeout=30)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
    
    def test_competitors_scan(self, admin_headers):
        """POST /api/revenue/market-robot/{property_id}/competitors/scan"""
        resp = requests.post(
            f"{BASE_URL}/api/revenue/market-robot/{PROPERTY_ID}/competitors/scan",
            headers=admin_headers,
            json={},
            timeout=60  # Scan can take longer
        )
        # 200 or 202 (accepted) are both valid
        assert resp.status_code in [200, 202], f"Expected 200/202, got {resp.status_code}: {resp.text[:200]}"
    
    def test_auto_bootstrap(self, admin_headers):
        """POST /api/revenue/market-robot/auto-bootstrap"""
        resp = requests.post(
            f"{BASE_URL}/api/revenue/market-robot/auto-bootstrap",
            headers=admin_headers,
            json={},
            timeout=30
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"


# ============================================================================
# SECTION 12: Channel Revenue and OTA Forecast
# ============================================================================
class TestChannelRevenueOTA:
    """Channel revenue, OTA stop sell forecast"""
    
    def test_channel_revenue_channels(self, admin_headers):
        """GET /api/channel-revenue/channels/{property_id}"""
        resp = requests.get(f"{BASE_URL}/api/channel-revenue/channels/{PROPERTY_ID}", headers=admin_headers, timeout=30)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
    
    def test_channel_revenue_rules(self, admin_headers):
        """GET /api/channel-revenue/rules/{property_id}"""
        resp = requests.get(f"{BASE_URL}/api/channel-revenue/rules/{PROPERTY_ID}", headers=admin_headers, timeout=30)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
    
    def test_ota_forecast(self, admin_headers):
        """GET /api/ota-forecast/{property_id}"""
        resp = requests.get(f"{BASE_URL}/api/ota-forecast/{PROPERTY_ID}", headers=admin_headers, timeout=30)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"


# ============================================================================
# SECTION 13: Logbook, Loyalty, Parity Defender
# ============================================================================
class TestLogbookLoyaltyParity:
    """Logbook entries, loyalty leaderboard, parity defender"""
    
    def test_logbook_entries(self, admin_headers):
        """GET /api/logbook/entries/{property_id}"""
        resp = requests.get(f"{BASE_URL}/api/logbook/entries/{PROPERTY_ID}", headers=admin_headers, timeout=30)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
    
    def test_loyalty_leaderboard(self, admin_headers):
        """GET /api/loyalty/leaderboard/{property_id}"""
        resp = requests.get(f"{BASE_URL}/api/loyalty/leaderboard/{PROPERTY_ID}", headers=admin_headers, timeout=30)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
    
    def test_parity_defender_config(self, admin_headers):
        """GET /api/parity-defender/{property_id}/config"""
        resp = requests.get(f"{BASE_URL}/api/parity-defender/{PROPERTY_ID}/config", headers=admin_headers, timeout=30)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
    
    def test_parity_defender_recommendation(self, admin_headers):
        """GET /api/parity-defender/{property_id}/recommendation"""
        resp = requests.get(f"{BASE_URL}/api/parity-defender/{PROPERTY_ID}/recommendation", headers=admin_headers, timeout=30)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"


# ============================================================================
# SECTION 14: RBAC Tests - Receptionist should get 403 on admin endpoints
# ============================================================================
class TestRBACReceptionist:
    """RBAC tests - receptionist should get 403 on admin-only endpoints"""
    
    def test_close_gap_receptionist_forbidden(self, receptionist_headers):
        """POST /api/revenue/market-robot/{property_id}/close-gap should return 403 for receptionist"""
        resp = requests.post(
            f"{BASE_URL}/api/revenue/market-robot/{PROPERTY_ID}/close-gap",
            headers=receptionist_headers,
            json={"strategy": "full", "dry_run": True},
            timeout=30
        )
        # Receptionist should be forbidden from applying pricing changes
        assert resp.status_code == 403, f"Expected 403 for receptionist, got {resp.status_code}: {resp.text[:200]}"
    
    def test_auto_bootstrap_receptionist_forbidden(self, receptionist_headers):
        """POST /api/revenue/market-robot/auto-bootstrap should return 403 for receptionist"""
        resp = requests.post(
            f"{BASE_URL}/api/revenue/market-robot/auto-bootstrap",
            headers=receptionist_headers,
            json={},
            timeout=30
        )
        # Receptionist should be forbidden from admin operations
        assert resp.status_code == 403, f"Expected 403 for receptionist, got {resp.status_code}: {resp.text[:200]}"
    
    def test_competitors_scan_receptionist_forbidden(self, receptionist_headers):
        """POST /api/revenue/market-robot/{property_id}/competitors/scan should return 403 for receptionist"""
        resp = requests.post(
            f"{BASE_URL}/api/revenue/market-robot/{PROPERTY_ID}/competitors/scan",
            headers=receptionist_headers,
            json={},
            timeout=30
        )
        # Receptionist should be forbidden from triggering scans
        assert resp.status_code == 403, f"Expected 403 for receptionist, got {resp.status_code}: {resp.text[:200]}"


# ============================================================================
# SECTION 15: Additional Market Robot Endpoints
# ============================================================================
class TestMarketRobotAdditional:
    """Additional Market Robot endpoints for completeness"""
    
    def test_market_robot_demand_dashboard(self, admin_headers):
        """GET /api/revenue/market-robot/{property_id}/demand-dashboard"""
        resp = requests.get(f"{BASE_URL}/api/revenue/market-robot/{PROPERTY_ID}/demand-dashboard", headers=admin_headers, timeout=30)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
    
    def test_market_robot_performance(self, admin_headers):
        """GET /api/revenue/market-robot/{property_id}/performance"""
        resp = requests.get(f"{BASE_URL}/api/revenue/market-robot/{PROPERTY_ID}/performance", headers=admin_headers, timeout=30)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
    
    def test_market_robot_action_feed(self, admin_headers):
        """GET /api/revenue/market-robot/{property_id}/action-feed"""
        resp = requests.get(f"{BASE_URL}/api/revenue/market-robot/{PROPERTY_ID}/action-feed", headers=admin_headers, timeout=30)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
    
    def test_market_robot_ranking(self, admin_headers):
        """GET /api/revenue/market-robot/{property_id}/ranking"""
        resp = requests.get(f"{BASE_URL}/api/revenue/market-robot/{PROPERTY_ID}/ranking", headers=admin_headers, timeout=30)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
    
    def test_market_robot_market_pulse(self, admin_headers):
        """GET /api/revenue/market-robot/{property_id}/market-pulse"""
        resp = requests.get(f"{BASE_URL}/api/revenue/market-robot/{PROPERTY_ID}/market-pulse", headers=admin_headers, timeout=30)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
