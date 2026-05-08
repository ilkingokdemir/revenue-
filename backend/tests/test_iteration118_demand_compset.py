"""
Iteration 118 - Demand Radar & Compset Intelligence API Tests
Tests for:
1. GET /api/revenue/demand-radar/{property_id}?days=N - Full demand radar dashboard
2. GET /api/revenue/demand-radar/{property_id}/booking-behavior - Lead time, LOS, DOW patterns
3. GET /api/revenue/compset-intel/{property_id}?days=N - Compset intelligence with rankings
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for admin user"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@hotelbox.com",
        "password": "HotelAdmin2026!"
    })
    assert response.status_code == 200, f"Login failed: {response.text}"
    data = response.json()
    # API returns 'token' not 'access_token'
    token = data.get("access_token") or data.get("token")
    assert token, f"No token in login response: {data.keys()}"
    return token

@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Headers with auth token"""
    return {"Authorization": f"Bearer {auth_token}"}


# ============ DEMAND RADAR TESTS ============

class TestDemandRadarEndpoint:
    """Tests for GET /api/revenue/demand-radar/{property_id}"""
    
    def test_demand_radar_default_days(self, auth_headers):
        """Test demand radar with default 90 days"""
        response = requests.get(f"{BASE_URL}/api/revenue/demand-radar/all", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Check top-level fields
        assert "status" in data, "Missing 'status' field"
        assert data["status"] in ["stable", "rising", "falling"], f"Invalid status: {data['status']}"
        assert "status_text" in data, "Missing 'status_text' field"
        assert "demand_change_pp" in data, "Missing 'demand_change_pp' field"
        assert "wap_change" in data, "Missing 'wap_change' field"
        
        # Check KPIs
        assert "kpis" in data, "Missing 'kpis' field"
        kpis = data["kpis"]
        assert "avg_demand" in kpis, "Missing 'avg_demand' in kpis"
        assert "avg_wap" in kpis, "Missing 'avg_wap' in kpis"
        assert "avg_supply" in kpis, "Missing 'avg_supply' in kpis"
        assert "high_demand_days" in kpis, "Missing 'high_demand_days' in kpis"
        assert "low_demand_days" in kpis, "Missing 'low_demand_days' in kpis"
        assert "peak_date" in kpis, "Missing 'peak_date' in kpis"
        assert "peak_demand" in kpis, "Missing 'peak_demand' in kpis"
        assert "quietest_date" in kpis, "Missing 'quietest_date' in kpis"
        assert "total_days" in kpis, "Missing 'total_days' in kpis"
        
        # Check daily data
        assert "daily" in data, "Missing 'daily' field"
        assert isinstance(data["daily"], list), "'daily' should be a list"
        
        # Check insights
        assert "insights" in data, "Missing 'insights' field"
        assert isinstance(data["insights"], list), "'insights' should be a list"
        
        # Check pickup_change
        assert "pickup_change" in data, "Missing 'pickup_change' field"
        assert isinstance(data["pickup_change"], list), "'pickup_change' should be a list"
        
        # Check opportunity_map
        assert "opportunity_map" in data, "Missing 'opportunity_map' field"
        assert isinstance(data["opportunity_map"], list), "'opportunity_map' should be a list"
        
        # Check supply_dynamics
        assert "supply_dynamics" in data, "Missing 'supply_dynamics' field"
        assert isinstance(data["supply_dynamics"], list), "'supply_dynamics' should be a list"
        
        print(f"Demand Radar default: status={data['status']}, avg_demand={kpis.get('avg_demand')}, avg_wap={kpis.get('avg_wap')}")
    
    def test_demand_radar_30_days(self, auth_headers):
        """Test demand radar with 30 days"""
        response = requests.get(f"{BASE_URL}/api/revenue/demand-radar/all?days=30", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data["kpis"]["total_days"] == 30, f"Expected 30 days, got {data['kpis']['total_days']}"
        assert len(data["daily"]) == 30, f"Expected 30 daily entries, got {len(data['daily'])}"
        print(f"Demand Radar 30d: {len(data['daily'])} daily entries")
    
    def test_demand_radar_60_days(self, auth_headers):
        """Test demand radar with 60 days"""
        response = requests.get(f"{BASE_URL}/api/revenue/demand-radar/all?days=60", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data["kpis"]["total_days"] == 60
        assert len(data["daily"]) == 60
        print(f"Demand Radar 60d: {len(data['daily'])} daily entries")
    
    def test_demand_radar_180_days(self, auth_headers):
        """Test demand radar with 180 days"""
        response = requests.get(f"{BASE_URL}/api/revenue/demand-radar/all?days=180", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data["kpis"]["total_days"] == 180
        assert len(data["daily"]) == 180
        print(f"Demand Radar 180d: {len(data['daily'])} daily entries")
    
    def test_demand_radar_365_days(self, auth_headers):
        """Test demand radar with 365 days (1 year)"""
        response = requests.get(f"{BASE_URL}/api/revenue/demand-radar/all?days=365", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data["kpis"]["total_days"] == 365
        assert len(data["daily"]) == 365
        print(f"Demand Radar 365d: {len(data['daily'])} daily entries")
    
    def test_demand_radar_daily_structure(self, auth_headers):
        """Test daily data structure"""
        response = requests.get(f"{BASE_URL}/api/revenue/demand-radar/all?days=30", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        if data["daily"]:
            day = data["daily"][0]
            assert "date" in day, "Missing 'date' in daily entry"
            assert "dow" in day, "Missing 'dow' in daily entry"
            assert "demand" in day, "Missing 'demand' in daily entry"
            assert "wap" in day, "Missing 'wap' in daily entry"
            assert "our_rate" in day, "Missing 'our_rate' in daily entry"
            assert "occupancy" in day, "Missing 'occupancy' in daily entry"
            print(f"Daily entry structure verified: date={day['date']}, dow={day['dow']}, demand={day['demand']}, wap={day['wap']}")
    
    def test_demand_radar_pickup_change_structure(self, auth_headers):
        """Test pickup change data structure"""
        response = requests.get(f"{BASE_URL}/api/revenue/demand-radar/all?days=30", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        if data["pickup_change"]:
            pickup = data["pickup_change"][0]
            assert "date" in pickup, "Missing 'date' in pickup_change"
            assert "dow" in pickup, "Missing 'dow' in pickup_change"
            assert "demand_change" in pickup, "Missing 'demand_change' in pickup_change"
            assert "price_change" in pickup, "Missing 'price_change' in pickup_change"
            assert "direction" in pickup, "Missing 'direction' in pickup_change"
            print(f"Pickup change structure verified: date={pickup['date']}, demand_change={pickup['demand_change']}, direction={pickup['direction']}")
    
    def test_demand_radar_opportunity_map_structure(self, auth_headers):
        """Test opportunity map data structure"""
        response = requests.get(f"{BASE_URL}/api/revenue/demand-radar/all?days=30", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        if data["opportunity_map"]:
            opp = data["opportunity_map"][0]
            assert "date" in opp, "Missing 'date' in opportunity_map"
            assert "demand" in opp, "Missing 'demand' in opportunity_map"
            assert "price" in opp, "Missing 'price' in opportunity_map"
            assert "color" in opp, "Missing 'color' in opportunity_map"
            assert opp["color"] in ["underpriced", "overpriced", "peak", "fair"], f"Invalid color: {opp['color']}"
            print(f"Opportunity map structure verified: date={opp['date']}, color={opp['color']}")


class TestBookingBehaviorEndpoint:
    """Tests for GET /api/revenue/demand-radar/{property_id}/booking-behavior"""
    
    def test_booking_behavior_endpoint(self, auth_headers):
        """Test booking behavior endpoint returns all required fields"""
        response = requests.get(f"{BASE_URL}/api/revenue/demand-radar/all/booking-behavior", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Check top-level fields
        assert "total_bookings" in data, "Missing 'total_bookings' field"
        assert "lead_time" in data, "Missing 'lead_time' field"
        assert "length_of_stay" in data, "Missing 'length_of_stay' field"
        assert "demand_by_lead_time" in data, "Missing 'demand_by_lead_time' field"
        assert "dow_patterns" in data, "Missing 'dow_patterns' field"
        
        print(f"Booking behavior: total_bookings={data['total_bookings']}")
    
    def test_lead_time_distribution(self, auth_headers):
        """Test lead time distribution structure"""
        response = requests.get(f"{BASE_URL}/api/revenue/demand-radar/all/booking-behavior", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        lt = data["lead_time"]
        assert "distribution" in lt, "Missing 'distribution' in lead_time"
        assert "avg_lead_time" in lt, "Missing 'avg_lead_time' in lead_time"
        assert "last_minute_pct" in lt, "Missing 'last_minute_pct' in lead_time"
        
        # Check distribution entries
        assert len(lt["distribution"]) == 5, f"Expected 5 lead time buckets, got {len(lt['distribution'])}"
        for bucket in lt["distribution"]:
            assert "label" in bucket, "Missing 'label' in lead_time bucket"
            assert "count" in bucket, "Missing 'count' in lead_time bucket"
            assert "pct" in bucket, "Missing 'pct' in lead_time bucket"
            assert "color" in bucket, "Missing 'color' in lead_time bucket"
        
        print(f"Lead time: avg={lt['avg_lead_time']} days, last_minute={lt['last_minute_pct']}%")
    
    def test_length_of_stay_distribution(self, auth_headers):
        """Test length of stay distribution structure"""
        response = requests.get(f"{BASE_URL}/api/revenue/demand-radar/all/booking-behavior", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        los = data["length_of_stay"]
        assert "distribution" in los, "Missing 'distribution' in length_of_stay"
        assert "avg_los" in los, "Missing 'avg_los' in length_of_stay"
        assert "long_stay_pct" in los, "Missing 'long_stay_pct' in length_of_stay"
        
        # Check distribution entries
        assert len(los["distribution"]) == 4, f"Expected 4 LOS buckets, got {len(los['distribution'])}"
        for bucket in los["distribution"]:
            assert "label" in bucket, "Missing 'label' in LOS bucket"
            assert "count" in bucket, "Missing 'count' in LOS bucket"
            assert "pct" in bucket, "Missing 'pct' in LOS bucket"
        
        print(f"Length of stay: avg={los['avg_los']} nights, long_stay={los['long_stay_pct']}%")
    
    def test_demand_by_lead_time(self, auth_headers):
        """Test demand by lead time windows"""
        response = requests.get(f"{BASE_URL}/api/revenue/demand-radar/all/booking-behavior", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        dblt = data["demand_by_lead_time"]
        assert len(dblt) == 4, f"Expected 4 lead time windows, got {len(dblt)}"
        
        expected_tags = ["URGENT", "TACTICAL", "STRATEGIC", "HORIZON"]
        for i, window in enumerate(dblt):
            assert "label" in window, "Missing 'label' in demand_by_lead_time"
            assert "tag" in window, "Missing 'tag' in demand_by_lead_time"
            assert window["tag"] == expected_tags[i], f"Expected tag {expected_tags[i]}, got {window['tag']}"
            assert "avg_demand" in window, "Missing 'avg_demand' in demand_by_lead_time"
            assert "avg_wap" in window, "Missing 'avg_wap' in demand_by_lead_time"
        
        print(f"Demand by lead time: {[w['tag'] for w in dblt]}")
    
    def test_dow_patterns(self, auth_headers):
        """Test day-of-week patterns"""
        response = requests.get(f"{BASE_URL}/api/revenue/demand-radar/all/booking-behavior", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        dow = data["dow_patterns"]
        assert len(dow) == 7, f"Expected 7 DOW entries, got {len(dow)}"
        
        expected_labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        for i, day in enumerate(dow):
            assert "dow" in day, "Missing 'dow' in dow_patterns"
            assert "label" in day, "Missing 'label' in dow_patterns"
            assert day["label"] == expected_labels[i], f"Expected label {expected_labels[i]}, got {day['label']}"
            assert "avg_demand" in day, "Missing 'avg_demand' in dow_patterns"
            assert "avg_wap" in day, "Missing 'avg_wap' in dow_patterns"
        
        print(f"DOW patterns: {[d['label'] for d in dow]}")


# ============ COMPSET INTELLIGENCE TESTS ============

class TestCompsetIntelligenceEndpoint:
    """Tests for GET /api/revenue/compset-intel/{property_id}"""
    
    def test_compset_intel_default_days(self, auth_headers):
        """Test compset intelligence with default 30 days"""
        response = requests.get(f"{BASE_URL}/api/revenue/compset-intel/all", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Check top-level fields
        assert "kpis" in data, "Missing 'kpis' field"
        assert "sentinel_insight" in data, "Missing 'sentinel_insight' field"
        assert "key_insights" in data, "Missing 'key_insights' field"
        assert "daily" in data, "Missing 'daily' field"
        assert "tier_distribution" in data, "Missing 'tier_distribution' field"
        assert "neighbourhoods" in data, "Missing 'neighbourhoods' field"
        assert "market_context" in data, "Missing 'market_context' field"
        assert "days" in data, "Missing 'days' field"
        
        print(f"Compset Intel default: days={data['days']}, sentinel={data['sentinel_insight'][:50]}...")
    
    def test_compset_intel_kpis_structure(self, auth_headers):
        """Test KPIs structure with rankings"""
        response = requests.get(f"{BASE_URL}/api/revenue/compset-intel/all", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        kpis = data["kpis"]
        # My metrics
        assert "my_occupancy" in kpis, "Missing 'my_occupancy' in kpis"
        assert "my_adr" in kpis, "Missing 'my_adr' in kpis"
        assert "my_revpar" in kpis, "Missing 'my_revpar' in kpis"
        
        # Comp metrics
        assert "comp_occupancy" in kpis, "Missing 'comp_occupancy' in kpis"
        assert "comp_adr" in kpis, "Missing 'comp_adr' in kpis"
        assert "comp_revpar" in kpis, "Missing 'comp_revpar' in kpis"
        
        # Rankings
        assert "occ_rank" in kpis, "Missing 'occ_rank' in kpis"
        assert "adr_rank" in kpis, "Missing 'adr_rank' in kpis"
        assert "revpar_rank" in kpis, "Missing 'revpar_rank' in kpis"
        assert "segment_size" in kpis, "Missing 'segment_size' in kpis"
        
        print(f"Compset KPIs: my_occ={kpis['my_occupancy']}%, my_adr={kpis['my_adr']}, occ_rank={kpis['occ_rank']}/{kpis['segment_size']}")
    
    def test_compset_intel_7_days(self, auth_headers):
        """Test compset intelligence with 7 days"""
        response = requests.get(f"{BASE_URL}/api/revenue/compset-intel/all?days=7", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data["days"] == 7, f"Expected 7 days, got {data['days']}"
        assert len(data["daily"]) == 7, f"Expected 7 daily entries, got {len(data['daily'])}"
        print(f"Compset Intel 7d: {len(data['daily'])} daily entries")
    
    def test_compset_intel_14_days(self, auth_headers):
        """Test compset intelligence with 14 days"""
        response = requests.get(f"{BASE_URL}/api/revenue/compset-intel/all?days=14", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["days"] == 14
        assert len(data["daily"]) == 14
        print(f"Compset Intel 14d: {len(data['daily'])} daily entries")
    
    def test_compset_intel_60_days(self, auth_headers):
        """Test compset intelligence with 60 days"""
        response = requests.get(f"{BASE_URL}/api/revenue/compset-intel/all?days=60", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["days"] == 60
        assert len(data["daily"]) == 60
        print(f"Compset Intel 60d: {len(data['daily'])} daily entries")
    
    def test_compset_intel_90_days(self, auth_headers):
        """Test compset intelligence with 90 days"""
        response = requests.get(f"{BASE_URL}/api/revenue/compset-intel/all?days=90", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["days"] == 90
        assert len(data["daily"]) == 90
        print(f"Compset Intel 90d: {len(data['daily'])} daily entries")
    
    def test_compset_intel_daily_structure(self, auth_headers):
        """Test daily data structure"""
        response = requests.get(f"{BASE_URL}/api/revenue/compset-intel/all?days=7", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        if data["daily"]:
            day = data["daily"][0]
            assert "date" in day, "Missing 'date' in daily entry"
            assert "dow" in day, "Missing 'dow' in daily entry"
            assert "my_occ" in day, "Missing 'my_occ' in daily entry"
            assert "comp_occ" in day, "Missing 'comp_occ' in daily entry"
            assert "my_adr" in day, "Missing 'my_adr' in daily entry"
            assert "comp_adr" in day, "Missing 'comp_adr' in daily entry"
            assert "my_revpar" in day, "Missing 'my_revpar' in daily entry"
            assert "comp_revpar" in day, "Missing 'comp_revpar' in daily entry"
            print(f"Daily structure: date={day['date']}, my_occ={day['my_occ']}%, comp_occ={day['comp_occ']}%")
    
    def test_compset_intel_key_insights(self, auth_headers):
        """Test key insights structure"""
        response = requests.get(f"{BASE_URL}/api/revenue/compset-intel/all", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        insights = data["key_insights"]
        assert len(insights) == 3, f"Expected 3 key insights, got {len(insights)}"
        
        expected_metrics = ["Occupancy", "ADR", "RevPAR"]
        for i, ins in enumerate(insights):
            assert "metric" in ins, "Missing 'metric' in key_insight"
            assert ins["metric"] == expected_metrics[i], f"Expected metric {expected_metrics[i]}, got {ins['metric']}"
            assert "diff" in ins, "Missing 'diff' in key_insight"
            assert "direction" in ins, "Missing 'direction' in key_insight"
            assert "text" in ins, "Missing 'text' in key_insight"
        
        print(f"Key insights: {[ins['metric'] for ins in insights]}")
    
    def test_compset_intel_tier_distribution(self, auth_headers):
        """Test tier distribution structure"""
        response = requests.get(f"{BASE_URL}/api/revenue/compset-intel/all", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        tiers = data["tier_distribution"]
        assert len(tiers) > 0, "tier_distribution should not be empty"
        
        for tier in tiers:
            assert "tier" in tier, "Missing 'tier' in tier_distribution"
            assert "count" in tier, "Missing 'count' in tier_distribution"
        
        print(f"Tier distribution: {[t['tier'] for t in tiers]}")
    
    def test_compset_intel_neighbourhoods(self, auth_headers):
        """Test neighbourhoods structure"""
        response = requests.get(f"{BASE_URL}/api/revenue/compset-intel/all", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        neighbourhoods = data["neighbourhoods"]
        assert len(neighbourhoods) > 0, "neighbourhoods should not be empty"
        
        for n in neighbourhoods:
            assert "area" in n, "Missing 'area' in neighbourhood"
            assert "hotels" in n, "Missing 'hotels' in neighbourhood"
        
        print(f"Neighbourhoods: {[n['area'] for n in neighbourhoods[:5]]}...")
    
    def test_compset_intel_market_context(self, auth_headers):
        """Test market context structure"""
        response = requests.get(f"{BASE_URL}/api/revenue/compset-intel/all", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        mc = data["market_context"]
        assert "segment_hotels" in mc, "Missing 'segment_hotels' in market_context"
        assert "segment_rooms" in mc, "Missing 'segment_rooms' in market_context"
        assert "market_hotels" in mc, "Missing 'market_hotels' in market_context"
        assert "market_rooms" in mc, "Missing 'market_rooms' in market_context"
        
        print(f"Market context: segment_hotels={mc['segment_hotels']}, market_hotels={mc['market_hotels']}")


# ============ AUTH TESTS ============

class TestAuthRequired:
    """Test that endpoints require authentication"""
    
    def test_demand_radar_requires_auth(self):
        """Test demand radar requires authentication"""
        response = requests.get(f"{BASE_URL}/api/revenue/demand-radar/all")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("Demand radar correctly requires auth")
    
    def test_booking_behavior_requires_auth(self):
        """Test booking behavior requires authentication"""
        response = requests.get(f"{BASE_URL}/api/revenue/demand-radar/all/booking-behavior")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("Booking behavior correctly requires auth")
    
    def test_compset_intel_requires_auth(self):
        """Test compset intelligence requires authentication"""
        response = requests.get(f"{BASE_URL}/api/revenue/compset-intel/all")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("Compset intel correctly requires auth")
