"""
Iteration 123 - Weather Intelligence & SEO Meta Tags Testing
Tests:
1. Weather Intelligence API - GET /api/revenue/weather/{property_id}
2. Weather forecast from Open-Meteo (real API, no key needed)
3. Weather score calculation (0-100)
4. Pricing opportunities detection
5. SEO Meta Tags component integration
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestWeatherIntelligenceAPI:
    """Weather Intelligence endpoint tests"""
    
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
    
    def test_weather_api_returns_200(self):
        """Test weather API returns 200 with valid property_id"""
        response = self.session.get(f"{BASE_URL}/api/revenue/weather/all?days=14")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print("PASS: Weather API returns 200")
    
    def test_weather_api_returns_city(self):
        """Test weather API returns city name"""
        response = self.session.get(f"{BASE_URL}/api/revenue/weather/all?days=14")
        data = response.json()
        assert "city" in data, "Response missing 'city' field"
        assert isinstance(data["city"], str), "City should be a string"
        print(f"PASS: Weather API returns city: {data['city']}")
    
    def test_weather_api_returns_coordinates(self):
        """Test weather API returns coordinates"""
        response = self.session.get(f"{BASE_URL}/api/revenue/weather/all?days=14")
        data = response.json()
        assert "coordinates" in data, "Response missing 'coordinates' field"
        assert "lat" in data["coordinates"], "Coordinates missing 'lat'"
        assert "lon" in data["coordinates"], "Coordinates missing 'lon'"
        print(f"PASS: Weather API returns coordinates: {data['coordinates']}")
    
    def test_weather_api_returns_summary(self):
        """Test weather API returns summary with avg_temp, sunny_days, rainy_days, best/worst day"""
        response = self.session.get(f"{BASE_URL}/api/revenue/weather/all?days=14")
        data = response.json()
        assert "summary" in data, "Response missing 'summary' field"
        summary = data["summary"]
        assert "avg_temp" in summary, "Summary missing 'avg_temp'"
        assert "sunny_days" in summary, "Summary missing 'sunny_days'"
        assert "rainy_days" in summary, "Summary missing 'rainy_days'"
        assert "best_day" in summary, "Summary missing 'best_day'"
        assert "worst_day" in summary, "Summary missing 'worst_day'"
        print(f"PASS: Weather summary - avg_temp: {summary['avg_temp']}C, sunny: {summary['sunny_days']}, rainy: {summary['rainy_days']}")
    
    def test_weather_api_returns_opportunities(self):
        """Test weather API returns pricing opportunities array"""
        response = self.session.get(f"{BASE_URL}/api/revenue/weather/all?days=14")
        data = response.json()
        assert "opportunities" in data, "Response missing 'opportunities' field"
        assert isinstance(data["opportunities"], list), "Opportunities should be a list"
        print(f"PASS: Weather API returns {len(data['opportunities'])} pricing opportunities")
        
        # If there are opportunities, validate structure
        if data["opportunities"]:
            opp = data["opportunities"][0]
            assert "type" in opp, "Opportunity missing 'type'"
            assert "title" in opp, "Opportunity missing 'title'"
            assert "suggestion" in opp, "Opportunity missing 'suggestion'"
            assert "impact" in opp, "Opportunity missing 'impact'"
            assert "date" in opp, "Opportunity missing 'date'"
            assert "weather_score" in opp, "Opportunity missing 'weather_score'"
            print(f"PASS: Opportunity structure valid - type: {opp['type']}, impact: {opp['impact']}")
    
    def test_weather_api_returns_daily_forecast(self):
        """Test weather API returns daily forecast array with required fields"""
        response = self.session.get(f"{BASE_URL}/api/revenue/weather/all?days=14")
        data = response.json()
        assert "daily" in data, "Response missing 'daily' field"
        assert isinstance(data["daily"], list), "Daily should be a list"
        assert len(data["daily"]) > 0, "Daily forecast should not be empty"
        
        # Validate first day structure
        day = data["daily"][0]
        required_fields = ["date", "day", "dow", "month", "is_weekend", "weather_code", 
                          "description", "icon", "temp_max", "temp_min", "temp_avg",
                          "precip_mm", "precip_prob", "wind_max", "uv_index", 
                          "sunshine_hrs", "weather_score"]
        for field in required_fields:
            assert field in day, f"Daily forecast missing '{field}'"
        
        print(f"PASS: Daily forecast has {len(data['daily'])} days with all required fields")
        print(f"  First day: {day['date']} - {day['description']}, {day['temp_max']}C, score: {day['weather_score']}")
    
    def test_weather_score_range(self):
        """Test weather score is between 0-100"""
        response = self.session.get(f"{BASE_URL}/api/revenue/weather/all?days=14")
        data = response.json()
        
        for day in data["daily"]:
            score = day["weather_score"]
            assert 0 <= score <= 100, f"Weather score {score} out of range 0-100"
        
        print("PASS: All weather scores are within 0-100 range")
    
    def test_weather_api_days_parameter(self):
        """Test weather API respects days parameter"""
        # Test with 7 days
        response = self.session.get(f"{BASE_URL}/api/revenue/weather/all?days=7")
        data = response.json()
        assert data["days"] <= 7, f"Expected max 7 days, got {data['days']}"
        print(f"PASS: Weather API with days=7 returns {data['days']} days")
        
        # Test with 14 days
        response = self.session.get(f"{BASE_URL}/api/revenue/weather/all?days=14")
        data = response.json()
        assert data["days"] <= 14, f"Expected max 14 days, got {data['days']}"
        print(f"PASS: Weather API with days=14 returns {data['days']} days")
    
    def test_weather_api_requires_auth(self):
        """Test weather API requires authentication"""
        # Create new session without auth
        no_auth_session = requests.Session()
        response = no_auth_session.get(f"{BASE_URL}/api/revenue/weather/all?days=14")
        assert response.status_code == 401, f"Expected 401 without auth, got {response.status_code}"
        print("PASS: Weather API requires authentication")
    
    def test_weather_demand_correlation(self):
        """Test weather API includes demand correlation fields"""
        response = self.session.get(f"{BASE_URL}/api/revenue/weather/all?days=14")
        data = response.json()
        
        # Check that daily forecast includes demand and rate fields
        day = data["daily"][0]
        assert "demand" in day, "Daily forecast missing 'demand' field"
        assert "our_rate" in day, "Daily forecast missing 'our_rate' field"
        print(f"PASS: Weather API includes demand correlation - demand: {day['demand']}, rate: {day['our_rate']}")
    
    def test_weather_opportunity_types(self):
        """Test weather opportunity types are valid"""
        response = self.session.get(f"{BASE_URL}/api/revenue/weather/all?days=14")
        data = response.json()
        
        valid_types = ["sunny_weekend", "sunny_event", "bad_weather_weekend", "exceptional_weather"]
        valid_impacts = ["high", "medium"]
        
        for opp in data["opportunities"]:
            assert opp["type"] in valid_types, f"Invalid opportunity type: {opp['type']}"
            assert opp["impact"] in valid_impacts, f"Invalid impact: {opp['impact']}"
        
        print(f"PASS: All {len(data['opportunities'])} opportunities have valid types and impacts")


class TestBookingEngineSEO:
    """Test SEO Meta Tags in Booking Engine"""
    
    def test_booking_engine_loads(self):
        """Test booking engine page loads"""
        response = requests.get(f"{BASE_URL}/book?property=aldgate-flats")
        # This will return HTML from frontend, but we can check the API endpoint
        # For SEO, we test the property endpoint that provides data for SEO tags
        response = requests.get(f"{BASE_URL}/api/booking/property/aldgate-flats")
        assert response.status_code == 200, f"Booking property API failed: {response.status_code}"
        data = response.json()
        assert "name" in data, "Property missing 'name' for SEO title"
        print(f"PASS: Booking property API returns data for SEO - name: {data.get('name')}")
    
    def test_property_has_seo_fields(self):
        """Test property has fields needed for SEO meta tags"""
        response = requests.get(f"{BASE_URL}/api/booking/property/aldgate-flats")
        data = response.json()
        
        # Check fields used by SEOMetaTags component
        assert "name" in data, "Property missing 'name'"
        # template_settings may contain seo_title, seo_description, etc.
        print(f"PASS: Property has SEO-relevant fields - name: {data.get('name')}")
        if data.get("template_settings"):
            ts = data["template_settings"]
            print(f"  Template settings: hotel_name={ts.get('hotel_name')}, description={ts.get('description')[:50] if ts.get('description') else 'N/A'}...")


class TestWeatherIconsAndDescriptions:
    """Test weather icons and descriptions mapping"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        self.session = requests.Session()
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        self.token = login_resp.json().get("access_token")
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
    
    def test_weather_icons_present(self):
        """Test all daily forecasts have valid icons"""
        response = self.session.get(f"{BASE_URL}/api/revenue/weather/all?days=14")
        data = response.json()
        
        valid_icons = ["sun", "cloud-sun", "cloud", "cloud-fog", "cloud-drizzle", 
                      "cloud-rain", "cloud-rain-heavy", "snowflake", "cloud-lightning"]
        
        for day in data["daily"]:
            assert day["icon"] in valid_icons, f"Invalid icon: {day['icon']}"
        
        print("PASS: All daily forecasts have valid weather icons")
    
    def test_weather_descriptions_present(self):
        """Test all daily forecasts have descriptions"""
        response = self.session.get(f"{BASE_URL}/api/revenue/weather/all?days=14")
        data = response.json()
        
        for day in data["daily"]:
            assert day["description"], f"Missing description for {day['date']}"
            assert isinstance(day["description"], str), "Description should be string"
        
        print("PASS: All daily forecasts have weather descriptions")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
