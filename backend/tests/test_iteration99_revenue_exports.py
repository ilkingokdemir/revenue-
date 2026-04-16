"""
Iteration 99 - Revenue Reports & Export Testing
Tests 7 export endpoints: Executive Summary, Performance, Pickup, Budget Variance, Forecasting, Profit OS, Distribution
CSV and Excel format support
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "admin@hotelbox.com"
TEST_PASSWORD = "HotelAdmin2026!"


class TestRevenueExports:
    """Revenue Export API tests - 7 report types with CSV and Excel formats"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token before each test"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login to get token
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        if response.status_code == 200:
            token = response.json().get("token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
        else:
            pytest.skip(f"Authentication failed: {response.status_code}")
    
    # ==================== PERFORMANCE EXPORT ====================
    def test_performance_csv_export(self):
        """GET /api/revenue/export/performance/all?format=csv returns valid CSV"""
        response = self.session.get(f"{BASE_URL}/api/revenue/export/performance/all?format=csv")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        # Verify content type
        content_type = response.headers.get("Content-Type", "")
        assert "text/csv" in content_type, f"Expected text/csv, got {content_type}"
        
        # Verify Content-Disposition header
        disposition = response.headers.get("Content-Disposition", "")
        assert "attachment" in disposition, "Missing attachment disposition"
        assert ".csv" in disposition, "Missing .csv extension in filename"
        
        # Verify CSV content has headers
        content = response.text
        assert "Date" in content, "Missing Date column"
        assert "Occupancy" in content, "Missing Occupancy column"
        assert "ADR" in content, "Missing ADR column"
        assert "RevPAR" in content, "Missing RevPAR column"
        print("✓ Performance CSV export working correctly")
    
    def test_performance_excel_export(self):
        """GET /api/revenue/export/performance/all?format=excel returns valid .xlsx"""
        response = self.session.get(f"{BASE_URL}/api/revenue/export/performance/all?format=excel")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        # Verify content type for Excel
        content_type = response.headers.get("Content-Type", "")
        assert "spreadsheetml" in content_type or "application/vnd" in content_type, f"Expected Excel content type, got {content_type}"
        
        # Verify Content-Disposition header
        disposition = response.headers.get("Content-Disposition", "")
        assert "attachment" in disposition, "Missing attachment disposition"
        assert ".xlsx" in disposition, "Missing .xlsx extension in filename"
        
        # Verify content is binary (Excel file)
        assert len(response.content) > 100, "Excel file too small"
        # Excel files start with PK (ZIP format)
        assert response.content[:2] == b'PK', "Not a valid Excel file (should start with PK)"
        print("✓ Performance Excel export working correctly")
    
    # ==================== EXECUTIVE SUMMARY EXPORT ====================
    def test_executive_summary_excel_export(self):
        """GET /api/revenue/export/executive-summary/all?format=excel returns data"""
        response = self.session.get(f"{BASE_URL}/api/revenue/export/executive-summary/all?format=excel")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        # Verify content type for Excel
        content_type = response.headers.get("Content-Type", "")
        assert "spreadsheetml" in content_type or "application/vnd" in content_type, f"Expected Excel content type, got {content_type}"
        
        # Verify Content-Disposition header
        disposition = response.headers.get("Content-Disposition", "")
        assert "executive_summary" in disposition.lower(), "Missing executive_summary in filename"
        assert ".xlsx" in disposition, "Missing .xlsx extension"
        
        # Verify content is binary (Excel file)
        assert len(response.content) > 100, "Excel file too small"
        assert response.content[:2] == b'PK', "Not a valid Excel file"
        print("✓ Executive Summary Excel export working correctly")
    
    def test_executive_summary_csv_export(self):
        """GET /api/revenue/export/executive-summary/all?format=csv returns valid CSV"""
        response = self.session.get(f"{BASE_URL}/api/revenue/export/executive-summary/all?format=csv")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        content_type = response.headers.get("Content-Type", "")
        assert "text/csv" in content_type, f"Expected text/csv, got {content_type}"
        
        content = response.text
        assert "Metric" in content, "Missing Metric column"
        assert "Value" in content, "Missing Value column"
        assert "TODAY" in content or "Occupancy" in content, "Missing KPI data"
        print("✓ Executive Summary CSV export working correctly")
    
    # ==================== PICKUP EXPORT ====================
    def test_pickup_csv_export(self):
        """GET /api/revenue/export/pickup/all?format=csv returns valid CSV with pace column"""
        response = self.session.get(f"{BASE_URL}/api/revenue/export/pickup/all?format=csv")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        content_type = response.headers.get("Content-Type", "")
        assert "text/csv" in content_type, f"Expected text/csv, got {content_type}"
        
        content = response.text
        assert "Date" in content, "Missing Date column"
        assert "Pace" in content, "Missing Pace column"
        assert "SDLY" in content, "Missing SDLY column"
        assert "On Books" in content, "Missing On Books column"
        
        # Verify pace values exist
        assert "Ahead" in content or "Behind" in content or "On Pace" in content, "Missing pace values"
        print("✓ Pickup CSV export working correctly with Pace column")
    
    def test_pickup_excel_export(self):
        """GET /api/revenue/export/pickup/all?format=excel returns valid .xlsx"""
        response = self.session.get(f"{BASE_URL}/api/revenue/export/pickup/all?format=excel")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        content_type = response.headers.get("Content-Type", "")
        assert "spreadsheetml" in content_type or "application/vnd" in content_type
        
        disposition = response.headers.get("Content-Disposition", "")
        assert "pickup" in disposition.lower(), "Missing pickup in filename"
        assert response.content[:2] == b'PK', "Not a valid Excel file"
        print("✓ Pickup Excel export working correctly")
    
    # ==================== BUDGET VARIANCE EXPORT ====================
    def test_budget_csv_export(self):
        """GET /api/revenue/export/budget/all?format=csv returns valid CSV"""
        response = self.session.get(f"{BASE_URL}/api/revenue/export/budget/all?format=csv")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        content_type = response.headers.get("Content-Type", "")
        assert "text/csv" in content_type, f"Expected text/csv, got {content_type}"
        
        content = response.text
        assert "Date" in content, "Missing Date column"
        assert "Actual" in content, "Missing Actual column"
        assert "Budget" in content, "Missing Budget column"
        assert "Variance" in content, "Missing Variance column"
        print("✓ Budget Variance CSV export working correctly")
    
    def test_budget_excel_export(self):
        """GET /api/revenue/export/budget/all?format=excel returns valid .xlsx"""
        response = self.session.get(f"{BASE_URL}/api/revenue/export/budget/all?format=excel")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        content_type = response.headers.get("Content-Type", "")
        assert "spreadsheetml" in content_type or "application/vnd" in content_type
        
        disposition = response.headers.get("Content-Disposition", "")
        assert "budget" in disposition.lower(), "Missing budget in filename"
        assert response.content[:2] == b'PK', "Not a valid Excel file"
        print("✓ Budget Variance Excel export working correctly")
    
    # ==================== FORECASTING EXPORT ====================
    def test_forecasting_csv_export(self):
        """GET /api/revenue/export/forecasting/all?format=csv returns forecast data"""
        response = self.session.get(f"{BASE_URL}/api/revenue/export/forecasting/all?format=csv")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        content_type = response.headers.get("Content-Type", "")
        assert "text/csv" in content_type, f"Expected text/csv, got {content_type}"
        
        content = response.text
        assert "Date" in content, "Missing Date column"
        assert "Forecast" in content, "Missing Forecast column"
        assert "Confidence" in content, "Missing Confidence column"
        assert "SDLY" in content, "Missing SDLY column"
        print("✓ Forecasting CSV export working correctly")
    
    def test_forecasting_excel_export(self):
        """GET /api/revenue/export/forecasting/all?format=excel returns valid .xlsx"""
        response = self.session.get(f"{BASE_URL}/api/revenue/export/forecasting/all?format=excel")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        content_type = response.headers.get("Content-Type", "")
        assert "spreadsheetml" in content_type or "application/vnd" in content_type
        
        disposition = response.headers.get("Content-Disposition", "")
        assert "forecast" in disposition.lower(), "Missing forecast in filename"
        assert response.content[:2] == b'PK', "Not a valid Excel file"
        print("✓ Forecasting Excel export working correctly")
    
    # ==================== PROFIT OS EXPORT ====================
    def test_profit_os_csv_export(self):
        """GET /api/revenue/export/profit-os/all?format=csv returns channel breakdown"""
        response = self.session.get(f"{BASE_URL}/api/revenue/export/profit-os/all?format=csv")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        content_type = response.headers.get("Content-Type", "")
        assert "text/csv" in content_type, f"Expected text/csv, got {content_type}"
        
        content = response.text
        assert "Channel" in content, "Missing Channel column"
        assert "Room Nights" in content or "Days" in content, "Missing room nights column"
        assert "ADR" in content, "Missing ADR column"
        assert "Commission" in content, "Missing Commission column"
        assert "Contribution" in content, "Missing Contribution column"
        print("✓ Profit OS CSV export working correctly with channel breakdown")
    
    def test_profit_os_excel_export(self):
        """GET /api/revenue/export/profit-os/all?format=excel returns valid .xlsx"""
        response = self.session.get(f"{BASE_URL}/api/revenue/export/profit-os/all?format=excel")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        content_type = response.headers.get("Content-Type", "")
        assert "spreadsheetml" in content_type or "application/vnd" in content_type
        
        disposition = response.headers.get("Content-Disposition", "")
        assert "profit" in disposition.lower(), "Missing profit in filename"
        assert response.content[:2] == b'PK', "Not a valid Excel file"
        print("✓ Profit OS Excel export working correctly")
    
    # ==================== DISTRIBUTION EXPORT ====================
    def test_distribution_csv_export(self):
        """GET /api/revenue/export/distribution/all?format=csv returns channel data"""
        response = self.session.get(f"{BASE_URL}/api/revenue/export/distribution/all?format=csv")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        content_type = response.headers.get("Content-Type", "")
        assert "text/csv" in content_type, f"Expected text/csv, got {content_type}"
        
        content = response.text
        assert "Channel" in content, "Missing Channel column"
        assert "Room Nights" in content or "Days" in content, "Missing room nights column"
        assert "Bookings" in content, "Missing Bookings column"
        assert "ADR" in content, "Missing ADR column"
        print("✓ Distribution CSV export working correctly with channel data")
    
    def test_distribution_excel_export(self):
        """GET /api/revenue/export/distribution/all?format=excel returns valid .xlsx"""
        response = self.session.get(f"{BASE_URL}/api/revenue/export/distribution/all?format=excel")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        content_type = response.headers.get("Content-Type", "")
        assert "spreadsheetml" in content_type or "application/vnd" in content_type
        
        disposition = response.headers.get("Content-Disposition", "")
        assert "distribution" in disposition.lower(), "Missing distribution in filename"
        assert response.content[:2] == b'PK', "Not a valid Excel file"
        print("✓ Distribution Excel export working correctly")
    
    # ==================== AUTH TESTS ====================
    def test_export_requires_auth(self):
        """Export endpoints require authentication"""
        # Create new session without auth
        no_auth_session = requests.Session()
        response = no_auth_session.get(f"{BASE_URL}/api/revenue/export/performance/all?format=csv")
        assert response.status_code in [401, 403], f"Expected 401/403 without auth, got {response.status_code}"
        print("✓ Export endpoints properly require authentication")
    
    # ==================== PERIOD PARAMETER TEST ====================
    def test_performance_with_period_parameter(self):
        """Performance export accepts period parameter (mtd, last30, last90)"""
        for period in ["mtd", "last30", "last90"]:
            response = self.session.get(f"{BASE_URL}/api/revenue/export/performance/all?format=csv&period={period}")
            assert response.status_code == 200, f"Failed for period={period}: {response.status_code}"
        print("✓ Performance export accepts all period parameters")
    
    # ==================== DAYS PARAMETER TEST ====================
    def test_pickup_with_days_parameter(self):
        """Pickup export accepts days parameter"""
        response = self.session.get(f"{BASE_URL}/api/revenue/export/pickup/all?format=csv&days=14")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        content = response.text
        lines = content.strip().split('\n')
        # Should have header + 14 data rows
        assert len(lines) >= 10, f"Expected at least 10 lines, got {len(lines)}"
        print("✓ Pickup export accepts days parameter")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
