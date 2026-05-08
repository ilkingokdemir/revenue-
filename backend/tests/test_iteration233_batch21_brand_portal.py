"""
Iteration 233 - Batch 21: Brand Portal / Chain HQ + White-Label
Tests for:
- GET /api/brand-portal/branding/{property_id} - auto-seeds defaults on first call
- PUT /api/brand-portal/branding/{property_id} - update branding
- GET /api/brand-portal/public-branding/{property_id} - public endpoint (no auth, strips from_email)
- GET /api/brand-portal/overview?days=30 - consolidated KPIs across all properties
- GET /api/brand-portal/alerts?days=7 - cross-property alerts
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    BASE_URL = "https://review-hub-108.preview.emergentagent.com"

# Test credentials
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"


class TestBrandPortalBatch21:
    """Brand Portal / Chain HQ + White-Label tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: login and get auth token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        token = login_resp.json().get("token")
        assert token, "No token in login response"
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        yield
        self.session.close()
    
    # ========== Branding Endpoints ==========
    
    def test_01_get_branding_auto_seeds_defaults(self):
        """GET /api/brand-portal/branding/{property_id} → 200, auto-seeds defaults on first call"""
        # Use a test property ID
        property_id = "aldgate-flats"
        
        resp = self.session.get(f"{BASE_URL}/api/brand-portal/branding/{property_id}")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        assert data.get("property_id") == property_id, f"Expected property_id={property_id}, got {data.get('property_id')}"
        assert data.get("primary_color") == "#0f172a", f"Expected primary_color=#0f172a, got {data.get('primary_color')}"
        assert data.get("secondary_color") == "#f59e0b", f"Expected secondary_color=#f59e0b, got {data.get('secondary_color')}"
        assert "created_at" in data, "Expected created_at in response"
        print(f"✓ GET branding auto-seeds defaults: {data}")
    
    def test_02_get_branding_for_default_property(self):
        """GET /api/brand-portal/branding/default → 200, auto-seeds defaults"""
        resp = self.session.get(f"{BASE_URL}/api/brand-portal/branding/default")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        assert data.get("property_id") == "default"
        assert data.get("primary_color") == "#0f172a"
        assert data.get("secondary_color") == "#f59e0b"
        print(f"✓ GET branding for default property: {data}")
    
    def test_03_put_branding_update(self):
        """PUT /api/brand-portal/branding/default → 200 updated:true"""
        payload = {
            "property_id": "default",
            "primary_color": "#ff0000",
            "logo_url": "https://example.com/logo.png",
            "custom_domain": "reservations.example.com",
            "from_email": "reservations@example.com"
        }
        
        resp = self.session.put(f"{BASE_URL}/api/brand-portal/branding/default", json=payload)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        assert data.get("updated") == True, f"Expected updated=True, got {data}"
        print(f"✓ PUT branding update: {data}")
    
    def test_04_get_branding_shows_updated_values(self):
        """GET /api/brand-portal/branding/default → shows updated values"""
        resp = self.session.get(f"{BASE_URL}/api/brand-portal/branding/default")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        assert data.get("primary_color") == "#ff0000", f"Expected primary_color=#ff0000, got {data.get('primary_color')}"
        assert data.get("logo_url") == "https://example.com/logo.png", f"Expected logo_url, got {data.get('logo_url')}"
        assert data.get("custom_domain") == "reservations.example.com"
        assert data.get("from_email") == "reservations@example.com"
        print(f"✓ GET branding shows updated values: {data}")
    
    # ========== Public Branding Endpoint ==========
    
    def test_05_public_branding_no_auth(self):
        """GET /api/brand-portal/public-branding/{property_id} → 200 WITHOUT auth"""
        # Use a fresh session without auth
        public_session = requests.Session()
        public_session.headers.update({"Content-Type": "application/json"})
        
        resp = public_session.get(f"{BASE_URL}/api/brand-portal/public-branding/default")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        assert data.get("property_id") == "default"
        # from_email should be stripped from response
        assert "from_email" not in data, f"from_email should be stripped, but found: {data.get('from_email')}"
        print(f"✓ Public branding (no auth, from_email stripped): {data}")
        public_session.close()
    
    def test_06_public_branding_nonexistent_property(self):
        """GET /api/brand-portal/public-branding/{nonexistent} → 200 with defaults"""
        public_session = requests.Session()
        public_session.headers.update({"Content-Type": "application/json"})
        
        resp = public_session.get(f"{BASE_URL}/api/brand-portal/public-branding/nonexistent-property-xyz")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        assert data.get("property_id") == "nonexistent-property-xyz"
        assert data.get("primary_color") == "#0f172a"  # Default color
        print(f"✓ Public branding for nonexistent property returns defaults: {data}")
        public_session.close()
    
    # ========== Overview Endpoint ==========
    
    def test_07_overview_30_days(self):
        """GET /api/brand-portal/overview?days=30 → 200 with total, properties, by_revenue, by_occupancy, lowest_rating"""
        resp = self.session.get(f"{BASE_URL}/api/brand-portal/overview?days=30")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        
        # Check total structure
        total = data.get("total", {})
        assert "properties" in total, "Expected total.properties"
        assert "rooms" in total, "Expected total.rooms"
        assert "bookings" in total, "Expected total.bookings"
        assert "revenue" in total, "Expected total.revenue"
        assert "avg_occupancy" in total, "Expected total.avg_occupancy"
        assert "avg_adr" in total, "Expected total.avg_adr"
        assert "avg_revpar" in total, "Expected total.avg_revpar"
        assert "avg_rating" in total, "Expected total.avg_rating"
        
        # Check properties array
        properties = data.get("properties", [])
        assert isinstance(properties, list), "Expected properties to be a list"
        
        # Check by_revenue array (sorted desc)
        by_revenue = data.get("by_revenue", [])
        assert isinstance(by_revenue, list), "Expected by_revenue to be a list"
        
        # Check by_occupancy array
        by_occupancy = data.get("by_occupancy", [])
        assert isinstance(by_occupancy, list), "Expected by_occupancy to be a list"
        
        # Check lowest_rating array
        lowest_rating = data.get("lowest_rating", [])
        assert isinstance(lowest_rating, list), "Expected lowest_rating to be a list"
        
        print(f"✓ Overview 30 days: total={total}, properties_count={len(properties)}, by_revenue_count={len(by_revenue)}")
    
    def test_08_overview_property_structure(self):
        """GET /api/brand-portal/overview → each property has kpis + name + city + country"""
        resp = self.session.get(f"{BASE_URL}/api/brand-portal/overview?days=30")
        assert resp.status_code == 200
        
        data = resp.json()
        properties = data.get("properties", [])
        
        if len(properties) > 0:
            prop = properties[0]
            # Check property structure
            assert "property_id" in prop, "Expected property_id in property"
            assert "name" in prop, "Expected name in property"
            assert "city" in prop, "Expected city in property"
            assert "country" in prop, "Expected country in property"
            # Check KPIs
            assert "rooms" in prop, "Expected rooms in property"
            assert "bookings" in prop, "Expected bookings in property"
            assert "revenue" in prop, "Expected revenue in property"
            assert "occupancy_pct" in prop, "Expected occupancy_pct in property"
            assert "adr" in prop, "Expected adr in property"
            assert "revpar" in prop, "Expected revpar in property"
            assert "avg_rating" in prop, "Expected avg_rating in property"
            print(f"✓ Property structure verified: {prop.get('name')}")
        else:
            print("⚠ No properties found in overview")
    
    def test_09_overview_by_revenue_sorted_desc(self):
        """GET /api/brand-portal/overview → by_revenue sorted descending"""
        resp = self.session.get(f"{BASE_URL}/api/brand-portal/overview?days=30")
        assert resp.status_code == 200
        
        data = resp.json()
        by_revenue = data.get("by_revenue", [])
        
        if len(by_revenue) > 1:
            # Verify sorted descending by revenue
            for i in range(len(by_revenue) - 1):
                assert by_revenue[i]["revenue"] >= by_revenue[i+1]["revenue"], \
                    f"by_revenue not sorted desc: {by_revenue[i]['revenue']} < {by_revenue[i+1]['revenue']}"
            print(f"✓ by_revenue sorted descending: top={by_revenue[0]['name']} (£{by_revenue[0]['revenue']})")
        else:
            print("⚠ Not enough properties to verify sorting")
    
    def test_10_overview_different_days(self):
        """GET /api/brand-portal/overview?days=7 → works with different day windows"""
        resp = self.session.get(f"{BASE_URL}/api/brand-portal/overview?days=7")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        assert data.get("window_days") == 7, f"Expected window_days=7, got {data.get('window_days')}"
        print(f"✓ Overview with 7 days window: {data.get('total', {})}")
    
    # ========== Alerts Endpoint ==========
    
    def test_11_alerts_7_days(self):
        """GET /api/brand-portal/alerts?days=7 → 200 with alerts[] and count"""
        resp = self.session.get(f"{BASE_URL}/api/brand-portal/alerts?days=7")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        assert "alerts" in data, "Expected alerts in response"
        assert "count" in data, "Expected count in response"
        assert isinstance(data["alerts"], list), "Expected alerts to be a list"
        assert data["count"] == len(data["alerts"]), f"count mismatch: {data['count']} != {len(data['alerts'])}"
        print(f"✓ Alerts endpoint: count={data['count']}")
    
    def test_12_alerts_structure(self):
        """GET /api/brand-portal/alerts → each alert has property_id, property_name, type, severity, count, message"""
        resp = self.session.get(f"{BASE_URL}/api/brand-portal/alerts?days=7")
        assert resp.status_code == 200
        
        data = resp.json()
        alerts = data.get("alerts", [])
        
        if len(alerts) > 0:
            alert = alerts[0]
            assert "property_id" in alert, "Expected property_id in alert"
            assert "property_name" in alert, "Expected property_name in alert"
            assert "type" in alert, "Expected type in alert"
            assert "severity" in alert, "Expected severity in alert"
            assert "count" in alert, "Expected count in alert"
            assert "message" in alert, "Expected message in alert"
            
            # Verify type is one of expected values
            valid_types = ["unread_inbox", "unanswered_reviews", "low_occupancy"]
            assert alert["type"] in valid_types, f"Unexpected alert type: {alert['type']}"
            
            # Verify severity is one of expected values
            valid_severities = ["warn", "info"]
            assert alert["severity"] in valid_severities, f"Unexpected severity: {alert['severity']}"
            
            print(f"✓ Alert structure verified: {alert['property_name']} - {alert['type']} ({alert['severity']})")
        else:
            print("⚠ No alerts found (this may be expected if all properties are healthy)")
    
    # ========== Regression Tests for Previous Batches ==========
    
    def test_13_regression_auth_login(self):
        """Regression: Auth login still works"""
        session = requests.Session()
        resp = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert resp.status_code == 200, f"Auth login failed: {resp.text}"
        print("✓ Regression: Auth login works")
        session.close()
    
    def test_14_regression_batch13_tr_compliance(self):
        """Regression: Batch 13 TR Compliance still works"""
        resp = self.session.get(f"{BASE_URL}/api/tr-compliance/kbs/default/history")
        assert resp.status_code == 200, f"TR Compliance failed: {resp.text}"
        print("✓ Regression: Batch 13 TR Compliance works")
    
    def test_15_regression_batch14_ai_predictions(self):
        """Regression: Batch 14 AI Predictions still works"""
        resp = self.session.get(f"{BASE_URL}/api/ai-predictions/cancel-risk/default")
        assert resp.status_code == 200, f"AI Predictions failed: {resp.text}"
        print("✓ Regression: Batch 14 AI Predictions works")
    
    def test_16_regression_batch15_eu_compliance(self):
        """Regression: Batch 15 EU Compliance still works"""
        resp = self.session.get(f"{BASE_URL}/api/eu-compliance/catalog")
        assert resp.status_code == 200, f"EU Compliance failed: {resp.text}"
        print("✓ Regression: Batch 15 EU Compliance works")
    
    def test_17_regression_batch16_channel_revenue(self):
        """Regression: Batch 16 Channel Revenue still works"""
        resp = self.session.get(f"{BASE_URL}/api/channel-revenue/channels/default")
        assert resp.status_code == 200, f"Channel Revenue failed: {resp.text}"
        print("✓ Regression: Batch 16 Channel Revenue works")
    
    def test_18_regression_batch17_kds(self):
        """Regression: Batch 17 KDS still works"""
        resp = self.session.get(f"{BASE_URL}/api/kds/default")
        assert resp.status_code == 200, f"KDS failed: {resp.text}"
        print("✓ Regression: Batch 17 KDS works")
    
    def test_19_regression_batch18_loyalty_v2(self):
        """Regression: Batch 18 Loyalty V2 still works"""
        resp = self.session.get(f"{BASE_URL}/api/loyalty-v2/benefits/default")
        assert resp.status_code == 200, f"Loyalty V2 benefits failed: {resp.text}"
        print("✓ Regression: Batch 18 Loyalty V2 works")
    
    def test_20_regression_batch19_sentiment_heatmap(self):
        """Regression: Batch 19 Sentiment Heatmap still works"""
        resp = self.session.get(f"{BASE_URL}/api/sentiment/heatmap/default?days=90")
        assert resp.status_code == 200, f"Sentiment Heatmap failed: {resp.text}"
        print("✓ Regression: Batch 19 Sentiment Heatmap works")
    
    def test_21_regression_batch20_self_checkin_v2(self):
        """Regression: Batch 20 Self Check-in V2 pipeline still works"""
        resp = self.session.get(f"{BASE_URL}/api/self-checkin-v2/pipeline/default?days_ahead=14")
        assert resp.status_code == 200, f"Self Check-in V2 pipeline failed: {resp.text}"
        print("✓ Regression: Batch 20 Self Check-in V2 works")
    
    def test_22_properties_endpoint(self):
        """GET /api/properties → returns list of properties (used by frontend dropdown)"""
        resp = self.session.get(f"{BASE_URL}/api/properties")
        assert resp.status_code == 200, f"Properties endpoint failed: {resp.text}"
        
        data = resp.json()
        # Could be array or object with properties key
        properties = data if isinstance(data, list) else data.get("properties", [])
        assert len(properties) >= 9, f"Expected at least 9 properties (MyHotelBox branches), got {len(properties)}"
        print(f"✓ Properties endpoint: {len(properties)} properties found")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
