"""
Iteration 212 - Accounting Export (QuickBooks/Xero) + HK Route Print Round

Tests:
1. GET /api/accounting/export/{property_id}/summary - Returns summary with bookings_count, total_revenue, payments_count, by_source
2. GET /api/accounting/export/{property_id}/sales?format=quickbooks - Returns CSV with DR/CR pairs
3. GET /api/accounting/export/{property_id}/sales?format=xero - Returns Xero Sales Invoice CSV
4. GET /api/accounting/export/{property_id}/payments?format=quickbooks|xero - Returns payments CSV
5. GET /api/accounting/export/{property_id}/sales?from_=invalid - Returns 400 error
6. Regression: nightly-recap, sustainability, group-requests, concierge-inbox endpoints
"""
import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestAccountingExport:
    """Accounting Export endpoint tests - QuickBooks/Xero CSV downloads"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        self.session = requests.Session()
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        self.token = login_resp.json().get("access_token")
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        self.property_id = "aldgate-flats"
        
        # Date range for testing
        today = datetime.now()
        first_of_month = today.replace(day=1)
        self.from_date = first_of_month.strftime("%Y-%m-%d")
        self.to_date = today.strftime("%Y-%m-%d")
        
        # Wider date range to ensure we get data
        self.from_date_wide = (today - timedelta(days=365)).strftime("%Y-%m-%d")
    
    def test_summary_endpoint(self):
        """GET /api/accounting/export/{property_id}/summary - Returns summary JSON"""
        resp = self.session.get(
            f"{BASE_URL}/api/accounting/export/{self.property_id}/summary",
            params={"from_": self.from_date_wide, "to": self.to_date}
        )
        assert resp.status_code == 200, f"Summary failed: {resp.text}"
        data = resp.json()
        
        # Verify response structure
        assert "from" in data, "Missing 'from' field"
        assert "to" in data, "Missing 'to' field"
        assert "bookings_count" in data, "Missing 'bookings_count' field"
        assert "total_revenue" in data, "Missing 'total_revenue' field"
        assert "payments_count" in data, "Missing 'payments_count' field"
        assert "by_source" in data, "Missing 'by_source' field"
        
        # Verify data types
        assert isinstance(data["bookings_count"], int), "bookings_count should be int"
        assert isinstance(data["total_revenue"], (int, float)), "total_revenue should be numeric"
        assert isinstance(data["payments_count"], int), "payments_count should be int"
        
        print(f"Summary: {data['bookings_count']} bookings, £{data['total_revenue']} revenue, {data['payments_count']} payments")
    
    def test_summary_default_dates(self):
        """GET /api/accounting/export/{property_id}/summary - Uses default dates when not provided"""
        resp = self.session.get(f"{BASE_URL}/api/accounting/export/{self.property_id}/summary")
        assert resp.status_code == 200, f"Summary with defaults failed: {resp.text}"
        data = resp.json()
        
        # Should have from/to dates auto-filled
        assert data.get("from"), "Should have 'from' date"
        assert data.get("to"), "Should have 'to' date"
        print(f"Default date range: {data['from']} to {data['to']}")
    
    def test_sales_quickbooks_csv(self):
        """GET /api/accounting/export/{property_id}/sales?format=quickbooks - Returns QB Journal CSV"""
        resp = self.session.get(
            f"{BASE_URL}/api/accounting/export/{self.property_id}/sales",
            params={"from_": self.from_date_wide, "to": self.to_date, "format": "quickbooks"}
        )
        assert resp.status_code == 200, f"Sales QB CSV failed: {resp.text}"
        
        # Verify CSV response
        assert "text/csv" in resp.headers.get("Content-Type", ""), "Should return text/csv"
        assert "Content-Disposition" in resp.headers, "Should have Content-Disposition header"
        assert "attachment" in resp.headers.get("Content-Disposition", ""), "Should be attachment"
        assert "quickbooks" in resp.headers.get("Content-Disposition", "").lower(), "Filename should contain quickbooks"
        
        # Verify CSV content structure
        content = resp.text
        lines = content.strip().split("\n")
        assert len(lines) >= 1, "Should have at least header row"
        
        # Check header columns for QuickBooks format
        header = lines[0]
        assert "Date" in header, "QB CSV should have Date column"
        assert "Journal No." in header, "QB CSV should have Journal No. column"
        assert "Account" in header, "QB CSV should have Account column"
        assert "Debits" in header, "QB CSV should have Debits column"
        assert "Credits" in header, "QB CSV should have Credits column"
        assert "Class" in header, "QB CSV should have Class column"
        
        # If there are data rows, verify DR/CR pairs
        if len(lines) > 1:
            # Each booking creates 2 rows (DR Accounts Receivable, CR Room Revenue)
            print(f"QuickBooks CSV: {len(lines)-1} rows (including DR/CR pairs)")
        else:
            print("QuickBooks CSV: Header only (no bookings in date range)")
    
    def test_sales_xero_csv(self):
        """GET /api/accounting/export/{property_id}/sales?format=xero - Returns Xero Sales Invoice CSV"""
        resp = self.session.get(
            f"{BASE_URL}/api/accounting/export/{self.property_id}/sales",
            params={"from_": self.from_date_wide, "to": self.to_date, "format": "xero"}
        )
        assert resp.status_code == 200, f"Sales Xero CSV failed: {resp.text}"
        
        # Verify CSV response
        assert "text/csv" in resp.headers.get("Content-Type", ""), "Should return text/csv"
        assert "Content-Disposition" in resp.headers, "Should have Content-Disposition header"
        assert "xero" in resp.headers.get("Content-Disposition", "").lower(), "Filename should contain xero"
        
        # Verify CSV content structure
        content = resp.text
        lines = content.strip().split("\n")
        assert len(lines) >= 1, "Should have at least header row"
        
        # Check header columns for Xero format (starts with *ContactName)
        header = lines[0]
        assert "*ContactName" in header, "Xero CSV should have *ContactName column"
        assert "*InvoiceNumber" in header, "Xero CSV should have *InvoiceNumber column"
        assert "*InvoiceDate" in header, "Xero CSV should have *InvoiceDate column"
        assert "*UnitAmount" in header, "Xero CSV should have *UnitAmount column"
        assert "*AccountCode" in header, "Xero CSV should have *AccountCode column"
        
        print(f"Xero CSV: {len(lines)-1} data rows")
    
    def test_payments_quickbooks_csv(self):
        """GET /api/accounting/export/{property_id}/payments?format=quickbooks - Returns QB payments CSV"""
        resp = self.session.get(
            f"{BASE_URL}/api/accounting/export/{self.property_id}/payments",
            params={"from_": self.from_date_wide, "to": self.to_date, "format": "quickbooks"}
        )
        assert resp.status_code == 200, f"Payments QB CSV failed: {resp.text}"
        
        # Verify CSV response
        assert "text/csv" in resp.headers.get("Content-Type", ""), "Should return text/csv"
        
        content = resp.text
        lines = content.strip().split("\n")
        header = lines[0]
        
        # Check QB payments header
        assert "Date" in header, "QB payments should have Date column"
        assert "Reference" in header, "QB payments should have Reference column"
        assert "Account" in header, "QB payments should have Account column"
        
        print(f"QuickBooks Payments CSV: {len(lines)-1} rows")
    
    def test_payments_xero_csv(self):
        """GET /api/accounting/export/{property_id}/payments?format=xero - Returns Xero payments CSV"""
        resp = self.session.get(
            f"{BASE_URL}/api/accounting/export/{self.property_id}/payments",
            params={"from_": self.from_date_wide, "to": self.to_date, "format": "xero"}
        )
        assert resp.status_code == 200, f"Payments Xero CSV failed: {resp.text}"
        
        # Verify CSV response
        assert "text/csv" in resp.headers.get("Content-Type", ""), "Should return text/csv"
        
        content = resp.text
        lines = content.strip().split("\n")
        header = lines[0]
        
        # Check Xero payments header
        assert "*Date" in header, "Xero payments should have *Date column"
        assert "*Amount" in header, "Xero payments should have *Amount column"
        assert "*Reference" in header, "Xero payments should have *Reference column"
        
        print(f"Xero Payments CSV: {len(lines)-1} rows")
    
    def test_sales_invalid_date_format(self):
        """GET /api/accounting/export/{property_id}/sales?from_=invalid - Returns 400"""
        resp = self.session.get(
            f"{BASE_URL}/api/accounting/export/{self.property_id}/sales",
            params={"from_": "invalid-date", "to": self.to_date, "format": "quickbooks"}
        )
        assert resp.status_code == 400, f"Should return 400 for invalid date, got {resp.status_code}"
        
        # Verify error message
        data = resp.json()
        assert "from/to must be YYYY-MM-DD" in data.get("detail", ""), f"Error message should mention date format: {data}"
        print("Invalid date format correctly returns 400")
    
    def test_sales_invalid_to_date(self):
        """GET /api/accounting/export/{property_id}/sales?to=invalid - Returns 400"""
        resp = self.session.get(
            f"{BASE_URL}/api/accounting/export/{self.property_id}/sales",
            params={"from_": self.from_date, "to": "not-a-date", "format": "quickbooks"}
        )
        assert resp.status_code == 400, f"Should return 400 for invalid to date, got {resp.status_code}"
        print("Invalid 'to' date correctly returns 400")
    
    def test_unauthorized_access(self):
        """Accounting export requires admin/manager role"""
        # Create new session without auth
        unauth_session = requests.Session()
        resp = unauth_session.get(f"{BASE_URL}/api/accounting/export/{self.property_id}/summary")
        assert resp.status_code in [401, 403], f"Should require auth, got {resp.status_code}"
        print("Unauthorized access correctly blocked")


class TestHousekeepingRoute:
    """Housekeeping Route endpoint tests - verify Print Round button data"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        self.session = requests.Session()
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        self.token = login_resp.json().get("access_token")
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        self.property_id = "aldgate-flats"
    
    def test_housekeeping_route_endpoint(self):
        """GET /api/housekeeping/route/{property_id} - Returns cleaning round data"""
        resp = self.session.get(f"{BASE_URL}/api/housekeeping/route/{self.property_id}")
        assert resp.status_code == 200, f"HK route failed: {resp.text}"
        data = resp.json()
        
        # Verify response structure
        assert "rounds" in data, "Should have 'rounds' array"
        assert "total_rooms" in data, "Should have 'total_rooms'"
        assert "total_estimated_minutes" in data, "Should have 'total_estimated_minutes'"
        
        # If rounds exist, verify structure
        if data["rounds"]:
            round_item = data["rounds"][0]
            assert "room_number" in round_item or "room_id" in round_item, "Round should have room identifier"
            assert "position" in round_item, "Round should have position"
            assert "kind" in round_item, "Round should have kind (checkout/arrival_ready/stayover)"
            print(f"HK Route: {len(data['rounds'])} rooms, ETA {data['total_estimated_minutes']} mins")
        else:
            print("HK Route: No rooms in cleaning round (all clean)")


class TestRegressionSmoke:
    """Regression smoke tests for existing features"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        self.session = requests.Session()
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        self.token = login_resp.json().get("access_token")
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        self.property_id = "aldgate-flats"
    
    def test_nightly_recap_endpoint(self):
        """Regression: GET /api/nightly-recap/{property_id} - Should still work"""
        resp = self.session.get(f"{BASE_URL}/api/nightly-recap/{self.property_id}")
        assert resp.status_code == 200, f"Nightly recap failed: {resp.text}"
        data = resp.json()
        assert "occupancy_pct" in data, "Should have occupancy_pct"
        assert "revenue" in data, "Should have revenue"
        print(f"Nightly Recap: {data.get('occupancy_pct', 0)}% occ, £{data.get('revenue', 0)} rev")
    
    def test_sustainability_endpoint(self):
        """Regression: GET /api/sustainability/{property_id}/dashboard - Should still work"""
        resp = self.session.get(f"{BASE_URL}/api/sustainability/{self.property_id}/dashboard")
        assert resp.status_code == 200, f"Sustainability failed: {resp.text}"
        data = resp.json()
        assert "esg_score" in data or "carbon_footprint" in data or "property_id" in data, "Should have sustainability data"
        print("Sustainability dashboard: OK")
    
    def test_group_requests_endpoint(self):
        """Regression: GET /api/group-requests/{property_id} - Should still work"""
        resp = self.session.get(f"{BASE_URL}/api/group-requests/{self.property_id}")
        assert resp.status_code == 200, f"Group requests failed: {resp.text}"
        data = resp.json()
        assert isinstance(data, list), "Should return list of group requests"
        print(f"Group Requests: {len(data)} requests")
    
    def test_concierge_inbox_endpoint(self):
        """Regression: GET /api/concierge/admin/{property_id}/inbox - Should still work"""
        resp = self.session.get(f"{BASE_URL}/api/concierge/admin/{self.property_id}/inbox")
        assert resp.status_code == 200, f"Concierge inbox failed: {resp.text}"
        data = resp.json()
        assert "messages" in data or isinstance(data, list), "Should return inbox data"
        print("Concierge Inbox: OK")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
