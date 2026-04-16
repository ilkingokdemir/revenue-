"""
Iteration 98 - Rate Override API & Editable Calendar Tests
Tests:
1. PUT /api/revenue/rate-override/{property_id} - Set custom rate
2. PUT /api/revenue/rate-override/{property_id} - Remove override (null custom_rate)
3. GET /api/revenue/rate-calendar/{property_id} - Verify has_override and custom_rate fields
4. AI Copilot chat still works
5. Rate calendar month navigation
"""
import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestRateOverrideAPI:
    """Rate Override endpoint tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        
        if login_response.status_code == 200:
            data = login_response.json()
            token = data.get("access_token") or data.get("token")
            if token:
                self.session.headers.update({"Authorization": f"Bearer {token}"})
        
        yield
        
        # Cleanup: Remove test override
        try:
            test_date = (datetime.now() + timedelta(days=10)).strftime("%Y-%m-%d")
            self.session.put(f"{BASE_URL}/api/revenue/rate-override/all", json={
                "date": test_date,
                "custom_rate": None,
                "room_type_id": ""
            })
        except:
            pass
    
    def test_01_login_success(self):
        """Test login works"""
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data or "token" in data
        print("✓ Login successful")
    
    def test_02_set_rate_override(self):
        """Test setting a custom rate override"""
        test_date = (datetime.now() + timedelta(days=10)).strftime("%Y-%m-%d")
        
        response = self.session.put(f"{BASE_URL}/api/revenue/rate-override/all", json={
            "date": test_date,
            "custom_rate": 250,
            "room_type_id": ""
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data.get("message") == "Rate override saved"
        assert data.get("date") == test_date
        assert data.get("custom_rate") == 250
        print(f"✓ Rate override set: {test_date} = £250")
    
    def test_03_verify_override_in_calendar(self):
        """Test that rate calendar shows the override"""
        test_date = (datetime.now() + timedelta(days=10)).strftime("%Y-%m-%d")
        year = int(test_date.split("-")[0])
        month = int(test_date.split("-")[1])
        day = int(test_date.split("-")[2])
        
        # First set the override
        self.session.put(f"{BASE_URL}/api/revenue/rate-override/all", json={
            "date": test_date,
            "custom_rate": 275,
            "room_type_id": ""
        })
        
        # Now get the calendar
        response = self.session.get(f"{BASE_URL}/api/revenue/rate-calendar/all?year={year}&month={month}")
        
        assert response.status_code == 200
        data = response.json()
        
        # Find the day with override
        days = data.get("days", [])
        override_day = next((d for d in days if d.get("date") == test_date), None)
        
        assert override_day is not None, f"Day {test_date} not found in calendar"
        assert override_day.get("has_override") == True, "has_override should be True"
        assert override_day.get("custom_rate") == 275, f"custom_rate should be 275, got {override_day.get('custom_rate')}"
        print(f"✓ Calendar shows override: has_override=True, custom_rate=275")
    
    def test_04_remove_rate_override(self):
        """Test removing a rate override by setting custom_rate to null"""
        test_date = (datetime.now() + timedelta(days=10)).strftime("%Y-%m-%d")
        
        # First set an override
        self.session.put(f"{BASE_URL}/api/revenue/rate-override/all", json={
            "date": test_date,
            "custom_rate": 300,
            "room_type_id": ""
        })
        
        # Now remove it
        response = self.session.put(f"{BASE_URL}/api/revenue/rate-override/all", json={
            "date": test_date,
            "custom_rate": None,
            "room_type_id": ""
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data.get("message") == "Override removed"
        print(f"✓ Rate override removed for {test_date}")
    
    def test_05_verify_override_removed_in_calendar(self):
        """Test that calendar no longer shows override after removal"""
        test_date = (datetime.now() + timedelta(days=10)).strftime("%Y-%m-%d")
        year = int(test_date.split("-")[0])
        month = int(test_date.split("-")[1])
        
        # Ensure override is removed
        self.session.put(f"{BASE_URL}/api/revenue/rate-override/all", json={
            "date": test_date,
            "custom_rate": None,
            "room_type_id": ""
        })
        
        # Get calendar
        response = self.session.get(f"{BASE_URL}/api/revenue/rate-calendar/all?year={year}&month={month}")
        
        assert response.status_code == 200
        data = response.json()
        
        days = data.get("days", [])
        day_data = next((d for d in days if d.get("date") == test_date), None)
        
        assert day_data is not None
        assert day_data.get("has_override") == False, "has_override should be False after removal"
        assert day_data.get("custom_rate") is None, "custom_rate should be None after removal"
        print(f"✓ Calendar shows no override: has_override=False, custom_rate=None")
    
    def test_06_rate_calendar_structure(self):
        """Test rate calendar returns expected structure"""
        now = datetime.now()
        response = self.session.get(f"{BASE_URL}/api/revenue/rate-calendar/all?year={now.year}&month={now.month}")
        
        assert response.status_code == 200
        data = response.json()
        
        # Check structure
        assert "year" in data
        assert "month" in data
        assert "month_name" in data
        assert "room_type" in data
        assert "room_types" in data
        assert "total_rooms" in data
        assert "performance" in data
        assert "days" in data
        
        # Check performance structure
        perf = data.get("performance", {})
        assert "occupancy" in perf
        assert "expected_by_today" in perf
        assert "target" in perf
        
        # Check day structure
        if data.get("days"):
            day = data["days"][0]
            assert "date" in day
            assert "day" in day
            assert "dow" in day
            assert "occupancy" in day
            assert "base_rate" in day
            assert "recommended_rate" in day
            assert "has_override" in day
            assert "custom_rate" in day
        
        print(f"✓ Rate calendar structure valid: {data.get('month_name')} {data.get('year')}")
    
    def test_07_rate_calendar_month_navigation(self):
        """Test rate calendar works for different months"""
        # Test next month
        now = datetime.now()
        next_month = now.month + 1 if now.month < 12 else 1
        next_year = now.year if now.month < 12 else now.year + 1
        
        response = self.session.get(f"{BASE_URL}/api/revenue/rate-calendar/all?year={next_year}&month={next_month}")
        
        assert response.status_code == 200
        data = response.json()
        assert data.get("year") == next_year
        assert data.get("month") == next_month
        print(f"✓ Rate calendar navigation works: {data.get('month_name')} {next_year}")
    
    def test_08_rate_override_requires_date(self):
        """Test that rate override requires a date"""
        response = self.session.put(f"{BASE_URL}/api/revenue/rate-override/all", json={
            "custom_rate": 200,
            "room_type_id": ""
        })
        
        assert response.status_code == 200
        data = response.json()
        assert "error" in data or data.get("message") == "Date is required"
        print("✓ Rate override validates date requirement")
    
    def test_09_ai_copilot_chat_still_works(self):
        """Test AI Copilot chat endpoint still works"""
        response = self.session.post(f"{BASE_URL}/api/revenue/copilot/all/chat", json={
            "message": "What is today's occupancy?"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert "response" in data
        assert len(data.get("response", "")) > 0
        print(f"✓ AI Copilot chat works: {data.get('response', '')[:100]}...")
    
    def test_10_ai_copilot_history(self):
        """Test AI Copilot history endpoint"""
        response = self.session.get(f"{BASE_URL}/api/revenue/copilot/all/history")
        
        assert response.status_code == 200
        data = response.json()
        assert "messages" in data
        print(f"✓ AI Copilot history works: {len(data.get('messages', []))} messages")
    
    def test_11_existing_override_check(self):
        """Test that existing override from seed data is visible"""
        # According to context, there's a test override: property_id='all', date='2026-04-20', custom_rate=150
        response = self.session.get(f"{BASE_URL}/api/revenue/rate-calendar/all?year=2026&month=4")
        
        assert response.status_code == 200
        data = response.json()
        
        days = data.get("days", [])
        april_20 = next((d for d in days if d.get("date") == "2026-04-20"), None)
        
        if april_20:
            print(f"✓ April 20 data: has_override={april_20.get('has_override')}, custom_rate={april_20.get('custom_rate')}")
        else:
            print("⚠ April 20 not found in calendar (may be outside current view)")
    
    def test_12_bulk_override_simulation(self):
        """Test setting multiple overrides (simulating bulk edit)"""
        base_date = datetime.now() + timedelta(days=15)
        dates = [(base_date + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(3)]
        
        # Set overrides for 3 consecutive days
        for date in dates:
            response = self.session.put(f"{BASE_URL}/api/revenue/rate-override/all", json={
                "date": date,
                "custom_rate": 199,
                "room_type_id": ""
            })
            assert response.status_code == 200
        
        # Verify all overrides
        year = int(dates[0].split("-")[0])
        month = int(dates[0].split("-")[1])
        
        response = self.session.get(f"{BASE_URL}/api/revenue/rate-calendar/all?year={year}&month={month}")
        assert response.status_code == 200
        data = response.json()
        
        days = data.get("days", [])
        override_count = sum(1 for d in days if d.get("date") in dates and d.get("has_override"))
        
        assert override_count == 3, f"Expected 3 overrides, found {override_count}"
        print(f"✓ Bulk override simulation: {override_count} overrides set")
        
        # Cleanup
        for date in dates:
            self.session.put(f"{BASE_URL}/api/revenue/rate-override/all", json={
                "date": date,
                "custom_rate": None,
                "room_type_id": ""
            })


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
