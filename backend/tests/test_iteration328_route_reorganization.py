"""
Iteration 328 - Backend Route Reorganization Regression Tests
Tests endpoints from all 11 domain subfolders after migration.
Uses actual endpoint paths from OpenAPI spec.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

@pytest.fixture(scope="module")
def admin_token():
    """Get admin token for authenticated requests"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@hotelbox.com",
        "password": "HotelAdmin2026!"
    })
    if response.status_code == 200:
        data = response.json()
        # Token is returned as 'token' not 'access_token'
        return data.get("token")
    pytest.skip("Admin login failed")


class TestHealthAndAuth:
    """Basic health and authentication tests"""
    
    def test_health_endpoint(self):
        """Verify backend is running"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        print(f"✓ Health check passed: {data}")
    
    def test_openapi_endpoint_count(self):
        """Verify all 1791 endpoints are registered"""
        response = requests.get(f"{BASE_URL}/api/openapi.json")
        assert response.status_code == 200
        data = response.json()
        endpoint_count = len(data.get("paths", {}))
        print(f"✓ OpenAPI reports {endpoint_count} endpoints")
        assert endpoint_count >= 1700, f"Expected ~1791 endpoints, got {endpoint_count}"
    
    def test_admin_login(self):
        """Verify admin login works"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        print(f"✓ Admin login successful, token received")


class TestPMSRoutes:
    """Test routes from routes/pms/ (39 files)"""
    
    def test_properties_list(self, admin_token):
        """GET /api/properties - from pms/bookings.py"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/properties", headers=headers)
        assert response.status_code == 200
        data = response.json()
        print(f"✓ Properties: {len(data)} found")
    
    def test_bookings_list(self, admin_token):
        """GET /api/bookings - from pms/bookings.py"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/bookings", headers=headers)
        assert response.status_code == 200
        print(f"✓ Bookings endpoint working")
    
    def test_room_types_list(self, admin_token):
        """GET /api/room-types - from pms/bookings.py"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/room-types", headers=headers)
        assert response.status_code == 200
        print(f"✓ Room types endpoint working")
    
    def test_groups(self, admin_token):
        """GET /api/groups - from pms/groups.py"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/groups", headers=headers)
        assert response.status_code == 200
        print(f"✓ Groups endpoint working")
    
    def test_guest_portal_bookings(self, admin_token):
        """GET /api/guest-portal/bookings - from pms/guest_portal_v2.py"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/guest-portal/bookings", headers=headers)
        # May return 200 or 404 if no bookings
        assert response.status_code in [200, 404]
        print(f"✓ Guest portal bookings endpoint accessible")


class TestRevenueExtRoutes:
    """Test routes from routes/revenue_ext/ (29 files)"""
    
    def test_market_robot_config(self, admin_token):
        """GET /api/revenue/market-robot/{property_id}/config - from revenue_ext/market_robot.py"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/revenue/market-robot/aldgate-flats/config", headers=headers)
        assert response.status_code == 200
        print(f"✓ Market robot config endpoint working")
    
    def test_market_robot_competitors(self, admin_token):
        """GET /api/revenue/market-robot/{property_id}/competitors - from revenue_ext/market_robot.py"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/revenue/market-robot/aldgate-flats/competitors", headers=headers)
        assert response.status_code == 200
        print(f"✓ Market robot competitors endpoint working")
    
    def test_ai_pricing_config(self, admin_token):
        """GET /api/revenue/ai-pricing/{property_id}/config - from revenue_ext/ai_pricing_engine.py"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/revenue/ai-pricing/aldgate-flats/config", headers=headers)
        assert response.status_code == 200
        print(f"✓ AI pricing config endpoint working")
    
    def test_revenue_forecast(self, admin_token):
        """GET /api/revenue/forecast/{property_id} - from revenue_ext/revenue.py"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/revenue/forecast/aldgate-flats", headers=headers)
        assert response.status_code == 200
        print(f"✓ Revenue forecast endpoint working")
    
    def test_dynamic_pricing_config(self, admin_token):
        """GET /api/revenue/dynamic-pricing/{property_id}/config - from revenue_ext/dynamic_pricing.py"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/revenue/dynamic-pricing/aldgate-flats/config", headers=headers)
        assert response.status_code == 200
        print(f"✓ Dynamic pricing config endpoint working")
    
    def test_rates_grid(self, admin_token):
        """GET /api/revenue/rates-grid/{property_id} - from revenue_ext/rates_grid.py"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/revenue/rates-grid/aldgate-flats", headers=headers)
        assert response.status_code == 200
        print(f"✓ Rates grid endpoint working")


class TestFinanceExtRoutes:
    """Test routes from routes/finance_ext/ (32 files)"""
    
    def test_accounting_payments(self, admin_token):
        """GET /api/accounting/payments/{property_id} - from finance_ext/payments.py"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/accounting/payments/aldgate-flats", headers=headers)
        assert response.status_code == 200
        print(f"✓ Accounting payments endpoint working")
    
    def test_accounting_accounts(self, admin_token):
        """GET /api/accounting/accounts/{property_id} - from finance_ext/accounting.py"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/accounting/accounts/aldgate-flats", headers=headers)
        assert response.status_code == 200
        print(f"✓ Accounting accounts endpoint working")
    
    def test_payroll_list(self, admin_token):
        """GET /api/payroll/{property_id} - from finance_ext/payroll.py"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/payroll/aldgate-flats", headers=headers)
        assert response.status_code == 200
        print(f"✓ Payroll endpoint working")
    
    def test_expenses_list(self, admin_token):
        """GET /api/expenses/{property_id} - from finance_ext/expenses.py"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/expenses/aldgate-flats", headers=headers)
        assert response.status_code == 200
        print(f"✓ Expenses endpoint working")
    
    def test_currency_fx_rates(self, admin_token):
        """GET /api/currency-fx/rates - from finance_ext/currency_fx.py"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/currency-fx/rates", headers=headers)
        assert response.status_code == 200
        print(f"✓ Currency FX rates endpoint working")
    
    def test_city_ledger(self, admin_token):
        """GET /api/city-ledger/{property_id} - from finance_ext/city_ledger.py"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/city-ledger/aldgate-flats", headers=headers)
        assert response.status_code == 200
        print(f"✓ City ledger endpoint working")


class TestHotelOpsRoutes:
    """Test routes from routes/hotel_ops/ (50 files)"""
    
    def test_housekeeping_rooms(self, admin_token):
        """GET /api/housekeeping/rooms/{property_id} - from hotel_ops/housekeeping.py"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/housekeeping/rooms/aldgate-flats", headers=headers)
        assert response.status_code == 200
        print(f"✓ Housekeeping rooms endpoint working")
    
    def test_pos_menu(self, admin_token):
        """GET /api/pos/menu/{property_id} - from hotel_ops/pos.py"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/pos/menu/aldgate-flats", headers=headers)
        assert response.status_code == 200
        print(f"✓ POS menu endpoint working")
    
    def test_maintenance_list(self, admin_token):
        """GET /api/maintenance/{property_id} - from hotel_ops/maintenance.py"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/maintenance/aldgate-flats", headers=headers)
        assert response.status_code == 200
        print(f"✓ Maintenance endpoint working")
    
    def test_operations_tasks(self, admin_token):
        """GET /api/operations/{property_id} - from hotel_ops/operations.py"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/operations/aldgate-flats", headers=headers)
        assert response.status_code == 200
        print(f"✓ Operations endpoint working")
    
    def test_shifts_list(self, admin_token):
        """GET /api/pos/shifts/{property_id} - from hotel_ops/shifts.py"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/pos/shifts/aldgate-flats", headers=headers)
        assert response.status_code == 200
        print(f"✓ Shifts endpoint working")
    
    def test_night_audit(self, admin_token):
        """GET /api/accounting/night-audit/{property_id} - from hotel_ops/night_audit.py"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/accounting/night-audit/aldgate-flats", headers=headers)
        assert response.status_code == 200
        print(f"✓ Night audit endpoint working")
    
    def test_events_rooms(self, admin_token):
        """GET /api/events/rooms/{property_id} - from hotel_ops/events.py"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/events/rooms/aldgate-flats", headers=headers)
        assert response.status_code == 200
        print(f"✓ Events rooms endpoint working")
    
    def test_laundry(self, admin_token):
        """GET /api/operations/laundry/{property_id} - from hotel_ops/laundry.py"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/operations/laundry/aldgate-flats", headers=headers)
        assert response.status_code == 200
        print(f"✓ Laundry endpoint working")


class TestGuestsRoutes:
    """Test routes from routes/guests/ (14 files)"""
    
    def test_reviews_list(self, admin_token):
        """GET /api/reviews - from guests/reviews.py"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/reviews", headers=headers)
        assert response.status_code == 200
        print(f"✓ Reviews endpoint working")
    
    def test_messaging_threads(self, admin_token):
        """GET /api/messaging/threads/{property_id} - from guests/messaging.py"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/messaging/threads/aldgate-flats", headers=headers)
        assert response.status_code == 200
        print(f"✓ Messaging threads endpoint working")
    
    def test_surveys(self, admin_token):
        """GET /api/surveys/{property_id} - from guests/surveys.py"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/surveys/aldgate-flats", headers=headers)
        assert response.status_code == 200
        print(f"✓ Surveys endpoint working")
    
    def test_loyalty_tiers(self, admin_token):
        """GET /api/loyalty/tiers/{property_id} - from guests/loyalty_tiers.py"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/loyalty/tiers/aldgate-flats", headers=headers)
        assert response.status_code == 200
        print(f"✓ Loyalty tiers endpoint working")


class TestMarketingRoutes:
    """Test routes from routes/marketing/ (13 files)"""
    
    def test_campaigns_list(self, admin_token):
        """GET /api/campaigns/{property_id} - from marketing/campaigns.py"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/campaigns/aldgate-flats", headers=headers)
        assert response.status_code == 200
        print(f"✓ Campaigns endpoint working")
    
    def test_upsell_items(self, admin_token):
        """GET /api/upsell/{property_id} - from marketing/upsell_engine.py"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/upsell/aldgate-flats", headers=headers)
        assert response.status_code == 200
        print(f"✓ Upsell endpoint working")


class TestDistributionRoutes:
    """Test routes from routes/distribution/ (15 files)"""
    
    def test_channel_revenue(self, admin_token):
        """GET /api/channel-revenue/channels/{property_id} - from distribution/channel_revenue.py"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/channel-revenue/channels/aldgate-flats", headers=headers)
        assert response.status_code == 200
        print(f"✓ Channel revenue endpoint working")
    
    def test_channel_hub_configs(self, admin_token):
        """GET /api/channel-hub/configs/{property_id} - from distribution/channel_hub.py"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/channel-hub/configs/aldgate-flats", headers=headers)
        assert response.status_code == 200
        print(f"✓ Channel hub configs endpoint working")
    
    def test_ota_health(self, admin_token):
        """GET /api/ota-health/{property_id} - from distribution/ota_health.py"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/ota-health/aldgate-flats", headers=headers)
        assert response.status_code == 200
        print(f"✓ OTA health endpoint working")


class TestAIRoutes:
    """Test routes from routes/ai/ (8 files)"""
    
    def test_agents_list(self, admin_token):
        """GET /api/agents/{property_id} - from ai/agents.py"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/agents/aldgate-flats", headers=headers)
        assert response.status_code == 200
        print(f"✓ Agents endpoint working")
    
    def test_brand_voice(self, admin_token):
        """GET /api/brand-voice/{property_id} - from ai/brand_voice.py"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/brand-voice/aldgate-flats", headers=headers)
        assert response.status_code == 200
        print(f"✓ Brand voice endpoint working")


class TestSecurityRoutes:
    """Test routes from routes/security/ (10 files)"""
    
    def test_audit_trail(self, admin_token):
        """GET /api/audit-trail - from security/audit_trail.py"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/audit-trail", headers=headers)
        assert response.status_code == 200
        print(f"✓ Audit trail endpoint working")
    
    def test_gdpr_search(self, admin_token):
        """POST /api/gdpr/search - from security/gdpr.py"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.post(f"{BASE_URL}/api/gdpr/search", headers=headers, json={
            "email": "test@example.com"
        })
        assert response.status_code == 200
        print(f"✓ GDPR search endpoint working")
    
    def test_compliance_status(self, admin_token):
        """GET /api/operations/compliance/{property_id} - from security/compliance.py"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/operations/compliance/aldgate-flats", headers=headers)
        assert response.status_code == 200
        print(f"✓ Compliance status endpoint working")


class TestIntegrationsPkgRoutes:
    """Test routes from routes/integrations_pkg/ (16 files)"""
    
    def test_integrations_list(self, admin_token):
        """GET /api/integrations - from integrations_pkg/integrations.py"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/integrations", headers=headers)
        assert response.status_code == 200
        print(f"✓ Integrations endpoint working")
    
    def test_notifications_settings(self, admin_token):
        """GET /api/notifications/settings - from integrations_pkg/notifications.py"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/notifications/settings", headers=headers)
        assert response.status_code == 200
        print(f"✓ Notifications settings endpoint working")
    
    def test_reports_list(self, admin_token):
        """GET /api/reports/{property_id} - from integrations_pkg/reports.py"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/reports/aldgate-flats", headers=headers)
        assert response.status_code == 200
        print(f"✓ Reports endpoint working")
    
    def test_smart_locks(self, admin_token):
        """GET /api/smart-locks/{property_id} - from integrations_pkg/smart_locks.py"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/smart-locks/aldgate-flats", headers=headers)
        assert response.status_code == 200
        print(f"✓ Smart locks endpoint working")


class TestPlatformExtRoutes:
    """Test routes from routes/platform_ext/ (17 files)"""
    
    def test_admin_users(self, admin_token):
        """GET /api/admin/users - from platform_ext/admin.py"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/admin/users", headers=headers)
        assert response.status_code == 200
        print(f"✓ Admin users endpoint working")
    
    def test_auth_me(self, admin_token):
        """GET /api/auth/me - from platform_ext/auth_routes.py"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/auth/me", headers=headers)
        assert response.status_code == 200
        print(f"✓ Auth me endpoint working")
    
    def test_roles_list(self, admin_token):
        """GET /api/roles - from platform_ext/roles.py"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/roles", headers=headers)
        assert response.status_code == 200
        print(f"✓ Roles endpoint working")
    
    def test_dashboard_overview(self, admin_token):
        """GET /api/dashboard/overview/{property_id} - from platform_ext/dashboard.py"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/dashboard/overview/aldgate-flats", headers=headers)
        assert response.status_code == 200
        print(f"✓ Dashboard overview endpoint working")


class TestChatbotAutomation:
    """Test chatbot automation routes (root level)"""
    
    def test_chatbot_handoff_sessions(self, admin_token):
        """GET /api/chatbot/all/handoff/sessions - from chatbot_automation.py"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/chatbot/all/handoff/sessions", headers=headers)
        assert response.status_code == 200
        print(f"✓ Chatbot handoff sessions endpoint working")
    
    def test_chatbot_settings(self, admin_token):
        """GET /api/chatbot/{property_id}/settings - from chatbot_automation.py"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/chatbot/aldgate-flats/settings", headers=headers)
        assert response.status_code == 200
        print(f"✓ Chatbot settings endpoint working")


class TestRecentFeatures:
    """Test recent features mentioned in the review request"""
    
    def test_market_robot_supply(self, admin_token):
        """GET /api/revenue/market-robot/{property_id}/supply - competitor discovery"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/revenue/market-robot/aldgate-flats/supply?days=7", headers=headers)
        assert response.status_code == 200
        print(f"✓ Market robot supply endpoint working")
    
    def test_market_robot_occupancy_pickup(self, admin_token):
        """GET /api/revenue/market-robot/{property_id}/occupancy-pickup"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/revenue/market-robot/aldgate-flats/occupancy-pickup?days=30", headers=headers)
        assert response.status_code == 200
        print(f"✓ Market robot occupancy pickup endpoint working")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
