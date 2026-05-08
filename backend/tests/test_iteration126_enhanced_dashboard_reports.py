"""
Iteration 126 - Enhanced Dashboard, Reports Hub, Finance P&L Tests
Tests for:
- GET /api/dashboard/enhanced/{property_id} - Enhanced dashboard with KPIs, financial overview, 7-day revenue, staff, HK, bookings
- GET /api/reports/overview/{property_id} - Reports overview with KPIs, revenue by source/category
- GET /api/reports/revenue/{property_id} - Revenue report with daily timeline, breakdowns
- GET /api/reports/occupancy/{property_id} - Occupancy report with daily table, category breakdown
- GET /api/reports/commission/{property_id} - Commission report by source
- GET /api/finance/pl/{property_id} - P&L dashboard with operating ledger
- GET /api/finance/pl/{property_id}/trend - 6-month financial trend
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestEnhancedDashboard:
    """Enhanced Dashboard API tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        self.token = response.json().get("token")
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_enhanced_dashboard_all_properties(self):
        """Test enhanced dashboard for all properties"""
        response = requests.get(f"{BASE_URL}/api/dashboard/enhanced/all", headers=self.headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        
        # Verify KPIs structure
        assert "kpis" in data
        kpis = data["kpis"]
        assert "in_house_guests" in kpis
        assert "occupancy_pct" in kpis
        assert "arrivals_today" in kpis
        assert "departures_today" in kpis
        assert "daily_income" in kpis
        assert "total_rooms" in kpis
        assert "pending_payment" in kpis
        
        # Verify financial overview structure
        assert "financial_overview" in data
        fo = data["financial_overview"]
        assert "this_month" in fo
        assert "previous_month" in fo
        assert "next_month" in fo
        assert "same_month_last_year" in fo
        
        # Verify month data structure
        for month_key in ["this_month", "previous_month", "next_month", "same_month_last_year"]:
            month_data = fo[month_key]
            assert "gross" in month_data
            assert "room_revenue" in month_data
            assert "adr" in month_data
            assert "commission" in month_data
            assert "net" in month_data
            assert "bookings" in month_data
            assert "room_nights" in month_data
        
        # Verify 7-day revenue chart
        assert "daily_revenue_7d" in data
        assert len(data["daily_revenue_7d"]) == 7
        for day in data["daily_revenue_7d"]:
            assert "date" in day
            assert "dow" in day
            assert "revenue" in day
            assert "bookings" in day
        
        # Verify staff on duty
        assert "staff_on_duty" in data
        
        # Verify housekeeping widget
        assert "housekeeping" in data
        hk = data["housekeeping"]
        assert "clean" in hk
        assert "dirty" in hk
        assert "total" in hk
        assert "completion_pct" in hk
        
        # Verify recent bookings
        assert "recent_bookings" in data
        
        # Verify other fields
        assert "total_7d_revenue" in data
        assert "avg_daily_revenue" in data
        assert "stayovers" in data
        assert "date" in data
        
        print(f"✓ Enhanced dashboard returned: {len(data['daily_revenue_7d'])} days revenue, {len(data['staff_on_duty'])} staff, HK {hk['completion_pct']}%")


class TestReportsHub:
    """Reports Hub API tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert response.status_code == 200
        self.token = response.json().get("token")
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_reports_overview(self):
        """Test reports overview endpoint"""
        response = requests.get(f"{BASE_URL}/api/reports/overview/all", headers=self.headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        
        # Verify period
        assert "period" in data
        assert "start" in data["period"]
        assert "end" in data["period"]
        assert "days" in data["period"]
        
        # Verify KPIs
        assert "kpis" in data
        kpis = data["kpis"]
        assert "room_revenue" in kpis
        assert "sold_room_nights" in kpis
        assert "occupancy_rate" in kpis
        assert "adr" in kpis
        assert "total_commission" in kpis
        
        # Verify breakdowns
        assert "revenue_by_source" in data
        assert "revenue_by_category" in data
        assert "availability_by_category" in data
        assert "room_availability" in data
        
        print(f"✓ Reports overview: Revenue £{kpis['room_revenue']}, {kpis['sold_room_nights']} nights, {kpis['occupancy_rate']}% occ")
    
    def test_revenue_report(self):
        """Test revenue report endpoint"""
        response = requests.get(f"{BASE_URL}/api/reports/revenue/all", headers=self.headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        
        # Verify period
        assert "period" in data
        
        # Verify KPIs
        assert "kpis" in data
        kpis = data["kpis"]
        assert "room_revenue" in kpis
        assert "avg_period" in kpis
        assert "top_source" in kpis
        assert "top_source_revenue" in kpis
        
        # Verify daily timeline
        assert "daily_timeline" in data
        assert len(data["daily_timeline"]) > 0
        for day in data["daily_timeline"]:
            assert "date" in day
            assert "dow" in day
            assert "revenue" in day
            assert "bookings" in day
        
        # Verify breakdowns
        assert "revenue_by_category" in data
        assert "revenue_by_source" in data
        
        print(f"✓ Revenue report: £{kpis['room_revenue']}, Top source: {kpis['top_source']} (£{kpis['top_source_revenue']})")
    
    def test_occupancy_report(self):
        """Test occupancy report endpoint"""
        response = requests.get(f"{BASE_URL}/api/reports/occupancy/all", headers=self.headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        
        # Verify period
        assert "period" in data
        
        # Verify KPIs
        assert "kpis" in data
        kpis = data["kpis"]
        assert "avg_occupancy" in kpis
        assert "sold_room_nights" in kpis
        assert "available_nights" in kpis
        assert "peak_day" in kpis
        assert "peak_occupancy" in kpis
        
        # Verify daily breakdown
        assert "daily" in data
        assert len(data["daily"]) > 0
        for day in data["daily"]:
            assert "date" in day
            assert "dow" in day
            assert "total_rooms" in day
            assert "sold" in day
            assert "occupancy_pct" in day
        
        # Verify category breakdown
        assert "by_category" in data
        
        # Verify availability
        assert "availability" in data
        
        print(f"✓ Occupancy report: {kpis['avg_occupancy']}% avg, Peak: {kpis['peak_day']} ({kpis['peak_occupancy']}%)")
    
    def test_commission_report(self):
        """Test commission report endpoint"""
        response = requests.get(f"{BASE_URL}/api/reports/commission/all", headers=self.headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        
        # Verify period
        assert "period" in data
        
        # Verify KPIs
        assert "kpis" in data
        kpis = data["kpis"]
        assert "gross_bookings" in kpis
        assert "net_after_commission" in kpis
        assert "total_commission" in kpis
        assert "pending" in kpis
        assert "collection_rate" in kpis
        
        # Verify by source breakdown
        assert "by_source" in data
        for source in data["by_source"]:
            assert "source" in source
            assert "gross" in source
            assert "rate_pct" in source
            assert "commission" in source
            assert "paid" in source
            assert "pending" in source
            assert "net" in source
            assert "bookings" in source
        
        print(f"✓ Commission report: Gross £{kpis['gross_bookings']}, Commission £{kpis['total_commission']}, Net £{kpis['net_after_commission']}")


class TestFinancePL:
    """Finance P&L API tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert response.status_code == 200
        self.token = response.json().get("token")
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_pl_dashboard(self):
        """Test P&L dashboard endpoint"""
        response = requests.get(f"{BASE_URL}/api/finance/pl/all", headers=self.headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        
        # Verify month and period
        assert "month" in data
        assert "period" in data
        
        # Verify KPIs
        assert "kpis" in data
        kpis = data["kpis"]
        assert "gross" in kpis
        assert "room_revenue" in kpis
        assert "adr" in kpis
        assert "commission" in kpis
        assert "total_costs" in kpis
        assert "payroll" in kpis
        assert "operating_profit" in kpis
        assert "margin_pct" in kpis
        
        # Verify revenue items
        assert "revenue_items" in data
        for item in data["revenue_items"]:
            assert "source" in item
            assert "revenue" in item
            assert "bookings" in item
        
        # Verify cost items
        assert "cost_items" in data
        for item in data["cost_items"]:
            assert "category" in item
            assert "description" in item
            assert "amount" in item
            assert "status" in item
        
        print(f"✓ P&L dashboard: Gross £{kpis['gross']}, Costs £{kpis['total_costs']}, Profit £{kpis['operating_profit']} ({kpis['margin_pct']}%)")
    
    def test_pl_trend(self):
        """Test P&L 6-month trend endpoint"""
        response = requests.get(f"{BASE_URL}/api/finance/pl/all/trend?months=6", headers=self.headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        
        # Verify trend data
        assert "trend" in data
        assert "months" in data
        assert data["months"] == 6
        assert len(data["trend"]) == 6
        
        for month in data["trend"]:
            assert "month" in month
            assert "label" in month
            assert "revenue" in month
            assert "costs" in month
            assert "profit" in month
        
        print(f"✓ P&L trend: {len(data['trend'])} months of data")
        for m in data["trend"]:
            print(f"  - {m['label']}: Revenue £{m['revenue']}, Costs £{m['costs']}, Profit £{m['profit']}")


class TestUnauthorizedAccess:
    """Test unauthorized access to endpoints"""
    
    def test_enhanced_dashboard_unauthorized(self):
        """Test enhanced dashboard without auth"""
        response = requests.get(f"{BASE_URL}/api/dashboard/enhanced/all")
        assert response.status_code == 401
    
    def test_reports_overview_unauthorized(self):
        """Test reports overview without auth"""
        response = requests.get(f"{BASE_URL}/api/reports/overview/all")
        assert response.status_code == 401
    
    def test_finance_pl_unauthorized(self):
        """Test finance P&L without auth"""
        response = requests.get(f"{BASE_URL}/api/finance/pl/all")
        assert response.status_code == 401


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
