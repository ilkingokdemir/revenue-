"""
Iteration 96 - Revenue Management Phase 2 Testing
Tests 12 NEW modules: Forecasting, Analytics (Performance, Pickup, Budget), 
Playbooks, Experiments, Parity, Overbooking, Action Center, Profit OS, Distribution, Competitors
"""
import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "admin@hotelbox.com"
TEST_PASSWORD = "HotelAdmin2026!"
PROPERTY_ID = "all"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for all tests"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    assert response.status_code == 200, f"Login failed: {response.text}"
    data = response.json()
    assert "token" in data, f"No token in response: {data}"
    return data["token"]


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Headers with auth token"""
    return {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json"
    }


class TestForecasting:
    """1. Forecasting Module Tests"""
    
    def test_get_forecasting_returns_kpis(self, auth_headers):
        """GET /api/revenue/forecasting/all returns KPIs and forecast data"""
        response = requests.get(
            f"{BASE_URL}/api/revenue/forecasting/{PROPERTY_ID}?days=30",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Verify KPIs structure
        assert "kpis" in data
        kpis = data["kpis"]
        assert "avg_forecast_occ" in kpis
        assert "avg_forecast_adr" in kpis
        assert "forecast_revpar" in kpis
        assert "total_on_books" in kpis
        
        # Verify forecast data with SDLY
        assert "forecast" in data
        assert len(data["forecast"]) > 0
        first_day = data["forecast"][0]
        assert "date" in first_day
        assert "forecast_occ" in first_day
        assert "sdly_occ" in first_day
        assert "vs_sdly" in first_day
        assert "confidence" in first_day
        
        # Verify accuracy metric
        assert "accuracy" in data
        print(f"Forecasting: KPIs={kpis}, Accuracy={data['accuracy']}%, Days={len(data['forecast'])}")


class TestAnalyticsPerformance:
    """2. Analytics > Performance Module Tests"""
    
    def test_get_performance_returns_kpis_and_dow(self, auth_headers):
        """GET /api/revenue/analytics/performance/all returns KPIs, DOW, segments"""
        response = requests.get(
            f"{BASE_URL}/api/revenue/analytics/performance/{PROPERTY_ID}?period=mtd",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Verify KPIs
        assert "kpis" in data
        kpis = data["kpis"]
        assert "occupancy" in kpis
        assert "adr" in kpis
        assert "revpar" in kpis
        assert "room_revenue" in kpis
        assert "sdly_occ" in kpis
        
        # Verify DOW performance
        assert "dow_performance" in data
        dow = data["dow_performance"]
        assert len(dow) == 7  # 7 days of week
        assert all("dow" in d and "occupancy" in d and "adr" in d for d in dow)
        
        # Verify segments
        assert "segments" in data
        
        # Verify trends
        assert "trends" in data
        assert "occupancy" in data["trends"]
        assert "adr" in data["trends"]
        
        print(f"Performance: Occ={kpis['occupancy']}%, ADR=£{kpis['adr']}, DOW days={len(dow)}")


class TestAnalyticsPickup:
    """3. Analytics > Pickup Report Module Tests"""
    
    def test_get_pickup_returns_kpis_and_rows(self, auth_headers):
        """GET /api/revenue/analytics/pickup/all returns KPIs and rows with pace"""
        response = requests.get(
            f"{BASE_URL}/api/revenue/analytics/pickup/{PROPERTY_ID}?days=30",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Verify KPIs
        assert "kpis" in data
        kpis = data["kpis"]
        assert "total_on_books" in kpis
        assert "remaining_to_sell" in kpis
        assert "avg_occupancy" in kpis
        assert "room_revenue" in kpis
        
        # Verify rows with pace indicators
        assert "rows" in data
        assert len(data["rows"]) > 0
        first_row = data["rows"][0]
        assert "date" in first_row
        assert "on_books" in first_row
        assert "remaining" in first_row
        assert "pace" in first_row  # Ahead/Behind/On Pace
        assert "vs_sdly" in first_row
        
        print(f"Pickup: On Books={kpis['total_on_books']}, Remaining={kpis['remaining_to_sell']}, Rows={len(data['rows'])}")


class TestAnalyticsBudget:
    """4. Analytics > Budget Variance Module Tests"""
    
    def test_get_budget_variance(self, auth_headers):
        """GET /api/revenue/analytics/budget/all returns budget data"""
        response = requests.get(
            f"{BASE_URL}/api/revenue/analytics/budget/{PROPERTY_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Verify structure
        assert "has_budget" in data
        assert "kpis" in data
        assert "daily" in data
        
        kpis = data["kpis"]
        assert "occupancy" in kpis
        assert "adr" in kpis
        assert "budget_occ" in kpis
        assert "budget_adr" in kpis
        
        print(f"Budget: Has Budget={data['has_budget']}, Occ={kpis['occupancy']}%")
    
    def test_set_budget(self, auth_headers):
        """POST /api/revenue/analytics/budget/all sets budget targets"""
        budget_data = {
            "target_occupancy": 75,
            "target_adr": 85,
            "target_revenue": 10000
        }
        response = requests.post(
            f"{BASE_URL}/api/revenue/analytics/budget/{PROPERTY_ID}",
            headers=auth_headers,
            json=budget_data
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "message" in data
        assert "saved" in data["message"].lower()
        
        # Verify budget was saved
        verify_response = requests.get(
            f"{BASE_URL}/api/revenue/analytics/budget/{PROPERTY_ID}",
            headers=auth_headers
        )
        verify_data = verify_response.json()
        assert verify_data["has_budget"] == True
        assert verify_data["kpis"]["budget_occ"] == 75
        
        print(f"Budget Set: Occ={budget_data['target_occupancy']}%, ADR=£{budget_data['target_adr']}")


class TestPlaybooks:
    """5. Playbooks Module Tests"""
    
    created_playbook_id = None
    
    def test_create_playbook_with_rules(self, auth_headers):
        """POST /api/revenue/playbooks/all creates playbook with IF/THEN rules"""
        playbook_data = {
            "name": "TEST_Weekend Surge Pricing",
            "description": "Increase rates when weekend occupancy is high",
            "trigger_type": "automatic",
            "rules": [
                {"condition": "Occupancy", "value": 80, "action": "Increase", "by": 15},
                {"condition": "Lead Time", "value": 3, "action": "Increase", "by": 10}
            ]
        }
        response = requests.post(
            f"{BASE_URL}/api/revenue/playbooks/{PROPERTY_ID}",
            headers=auth_headers,
            json=playbook_data
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert "id" in data
        assert data["name"] == playbook_data["name"]
        assert data["trigger_type"] == "automatic"
        assert len(data["rules"]) == 2
        
        TestPlaybooks.created_playbook_id = data["id"]
        print(f"Playbook Created: ID={data['id']}, Rules={len(data['rules'])}")
    
    def test_list_playbooks(self, auth_headers):
        """GET /api/revenue/playbooks/all lists playbooks"""
        response = requests.get(
            f"{BASE_URL}/api/revenue/playbooks/{PROPERTY_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert "items" in data
        # Should have at least the one we created
        test_playbooks = [p for p in data["items"] if p["name"].startswith("TEST_")]
        assert len(test_playbooks) >= 1
        
        print(f"Playbooks Listed: Total={len(data['items'])}")
    
    def test_delete_playbook(self, auth_headers):
        """DELETE /api/revenue/playbooks/{id} deletes playbook"""
        if TestPlaybooks.created_playbook_id:
            response = requests.delete(
                f"{BASE_URL}/api/revenue/playbooks/{TestPlaybooks.created_playbook_id}",
                headers=auth_headers
            )
            assert response.status_code == 200, f"Failed: {response.text}"
            print(f"Playbook Deleted: ID={TestPlaybooks.created_playbook_id}")


class TestExperiments:
    """6. Experiments Module Tests"""
    
    created_experiment_id = None
    
    def test_create_experiment(self, auth_headers):
        """POST /api/revenue/experiments/all creates A/B experiment"""
        today = datetime.now().strftime("%Y-%m-%d")
        end_date = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
        
        experiment_data = {
            "name": "TEST_Weekend Price Test",
            "description": "Testing 10% price increase on weekends",
            "target_room_category": "All Categories",
            "target_rate_plan": "All Plans",
            "start_date": today,
            "end_date": end_date,
            "treatment_adjustment": 10
        }
        response = requests.post(
            f"{BASE_URL}/api/revenue/experiments/{PROPERTY_ID}",
            headers=auth_headers,
            json=experiment_data
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert "id" in data
        assert data["name"] == experiment_data["name"]
        assert data["treatment_adjustment"] == 10
        assert data["status"] == "active"
        
        TestExperiments.created_experiment_id = data["id"]
        print(f"Experiment Created: ID={data['id']}, Adjustment={data['treatment_adjustment']}%")
    
    def test_list_experiments(self, auth_headers):
        """GET /api/revenue/experiments/all lists experiments"""
        response = requests.get(
            f"{BASE_URL}/api/revenue/experiments/{PROPERTY_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert "items" in data
        test_experiments = [e for e in data["items"] if e["name"].startswith("TEST_")]
        assert len(test_experiments) >= 1
        
        print(f"Experiments Listed: Total={len(data['items'])}")
    
    def test_delete_experiment(self, auth_headers):
        """DELETE /api/revenue/experiments/{id} deletes experiment"""
        if TestExperiments.created_experiment_id:
            response = requests.delete(
                f"{BASE_URL}/api/revenue/experiments/{TestExperiments.created_experiment_id}",
                headers=auth_headers
            )
            assert response.status_code == 200, f"Failed: {response.text}"
            print(f"Experiment Deleted: ID={TestExperiments.created_experiment_id}")


class TestParity:
    """7. Parity Module Tests"""
    
    def test_get_parity_violations(self, auth_headers):
        """GET /api/revenue/parity/all returns violations list"""
        response = requests.get(
            f"{BASE_URL}/api/revenue/parity/{PROPERTY_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert "items" in data
        assert "counts" in data
        assert "open" in data["counts"]
        assert "fixed" in data["counts"]
        assert "total" in data["counts"]
        
        print(f"Parity: Open={data['counts']['open']}, Fixed={data['counts']['fixed']}, Total={data['counts']['total']}")
    
    def test_detect_parity_violations(self, auth_headers):
        """POST /api/revenue/parity/all/detect detects violations"""
        response = requests.post(
            f"{BASE_URL}/api/revenue/parity/{PROPERTY_ID}/detect",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert "message" in data
        assert "count" in data
        
        print(f"Parity Detection: {data['message']}, Count={data['count']}")
    
    def test_fix_parity_violation(self, auth_headers):
        """PUT /api/revenue/parity/{id}/fix marks violation as fixed"""
        # First get a violation to fix
        list_response = requests.get(
            f"{BASE_URL}/api/revenue/parity/{PROPERTY_ID}",
            headers=auth_headers
        )
        violations = list_response.json()["items"]
        open_violations = [v for v in violations if v.get("status") == "open"]
        
        if open_violations:
            violation_id = open_violations[0]["id"]
            response = requests.put(
                f"{BASE_URL}/api/revenue/parity/{violation_id}/fix",
                headers=auth_headers
            )
            assert response.status_code == 200, f"Failed: {response.text}"
            print(f"Parity Fix: ID={violation_id}")
        else:
            print("Parity Fix: No open violations to fix (skipped)")


class TestOverbooking:
    """8. Overbooking Module Tests"""
    
    def test_get_overbooking_policies(self, auth_headers):
        """GET /api/revenue/overbooking/all returns policies"""
        response = requests.get(
            f"{BASE_URL}/api/revenue/overbooking/{PROPERTY_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert "policies" in data
        print(f"Overbooking Policies: Count={len(data['policies'])}")
    
    def test_run_overbooking_simulation(self, auth_headers):
        """POST /api/revenue/overbooking/all/simulate runs simulation"""
        response = requests.post(
            f"{BASE_URL}/api/revenue/overbooking/{PROPERTY_ID}/simulate",
            headers=auth_headers,
            json={}
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert "simulation" in data
        assert len(data["simulation"]) > 0
        
        first_day = data["simulation"][0]
        assert "date" in first_day
        assert "on_books" in first_day
        assert "optimal_overbook" in first_day
        assert "expected_revenue" in first_day
        assert "walk_risk" in first_day
        
        print(f"Overbooking Simulation: Days={len(data['simulation'])}")
    
    def test_save_overbooking_policy(self, auth_headers):
        """POST /api/revenue/overbooking/all saves policy"""
        policy_data = {
            "room_category": "TEST_Standard",
            "buffer_rooms": 2,
            "max_overbook_pct": 5,
            "walk_cost": 150,
            "no_show_rate": 0.05,
            "cancellation_rate": 0.1
        }
        response = requests.post(
            f"{BASE_URL}/api/revenue/overbooking/{PROPERTY_ID}",
            headers=auth_headers,
            json=policy_data
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert "id" in data
        assert data["room_category"] == "TEST_Standard"
        assert data["max_overbook_pct"] == 5
        
        print(f"Overbooking Policy Saved: ID={data['id']}")


class TestActionCenter:
    """9. Action Center Module Tests"""
    
    def test_get_actions(self, auth_headers):
        """GET /api/revenue/action-center/all returns actions"""
        response = requests.get(
            f"{BASE_URL}/api/revenue/action-center/{PROPERTY_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert "items" in data
        assert "counts" in data
        assert "total" in data["counts"]
        assert "open" in data["counts"]
        assert "applied" in data["counts"]
        
        print(f"Action Center: Total={data['counts']['total']}, Open={data['counts']['open']}")
    
    def test_refresh_actions(self, auth_headers):
        """POST /api/revenue/action-center/all/refresh generates actions"""
        response = requests.post(
            f"{BASE_URL}/api/revenue/action-center/{PROPERTY_ID}/refresh",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert "message" in data
        assert "count" in data
        
        print(f"Action Center Refresh: {data['message']}")
    
    def test_apply_action(self, auth_headers):
        """PUT /api/revenue/action-center/{id}/applied applies action"""
        # First get an action to apply
        list_response = requests.get(
            f"{BASE_URL}/api/revenue/action-center/{PROPERTY_ID}",
            headers=auth_headers
        )
        actions = list_response.json()["items"]
        open_actions = [a for a in actions if a.get("status") == "open"]
        
        if open_actions:
            action_id = open_actions[0]["id"]
            response = requests.put(
                f"{BASE_URL}/api/revenue/action-center/{action_id}/applied",
                headers=auth_headers
            )
            assert response.status_code == 200, f"Failed: {response.text}"
            print(f"Action Applied: ID={action_id}")
        else:
            print("Action Apply: No open actions to apply (skipped)")


class TestProfitOS:
    """10. Profit OS Module Tests"""
    
    def test_get_profit_os(self, auth_headers):
        """GET /api/revenue/profit-os/all returns KPIs and channel breakdown"""
        response = requests.get(
            f"{BASE_URL}/api/revenue/profit-os/{PROPERTY_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Verify KPIs
        assert "kpis" in data
        kpis = data["kpis"]
        assert "avg_gross_adr" in kpis
        assert "avg_net_adr" in kpis
        assert "avg_contribution_par" in kpis
        
        # Verify channels
        assert "channels" in data
        if len(data["channels"]) > 0:
            first_channel = data["channels"][0]
            assert "channel" in first_channel
            assert "gross_adr" in first_channel
            assert "net_adr" in first_channel
            assert "contribution_par" in first_channel
        
        print(f"Profit OS: Gross ADR=£{kpis['avg_gross_adr']}, Net ADR=£{kpis['avg_net_adr']}, Channels={len(data['channels'])}")


class TestDistribution:
    """11. Distribution Cockpit Module Tests"""
    
    def test_get_distribution(self, auth_headers):
        """GET /api/revenue/distribution/all returns channels sorted by ContributionPAR"""
        response = requests.get(
            f"{BASE_URL}/api/revenue/distribution/{PROPERTY_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert "channels" in data
        assert "period" in data
        
        if len(data["channels"]) > 0:
            first_channel = data["channels"][0]
            assert "channel" in first_channel
            assert "avg_gross_adr" in first_channel
            assert "avg_net_adr" in first_channel
            assert "avg_contribution_par" in first_channel
            
            # Verify sorted by contribution_par (descending)
            if len(data["channels"]) > 1:
                for i in range(len(data["channels"]) - 1):
                    assert data["channels"][i]["avg_contribution_par"] >= data["channels"][i+1]["avg_contribution_par"]
        
        print(f"Distribution: Channels={len(data['channels'])}, Period={data['period']}")


class TestCompetitors:
    """12. Competitor Intelligence Module Tests"""
    
    def test_get_competitors(self, auth_headers):
        """GET /api/revenue/competitors/all returns competitor data with daily rates"""
        response = requests.get(
            f"{BASE_URL}/api/revenue/competitors/{PROPERTY_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Verify your ADR
        assert "your_adr" in data
        
        # Verify competitors
        assert "competitors" in data
        assert len(data["competitors"]) > 0
        
        first_comp = data["competitors"][0]
        assert "name" in first_comp
        assert "stars" in first_comp
        assert "rooms" in first_comp
        assert "avg_rate" in first_comp
        assert "delta_vs_you" in first_comp
        assert "position" in first_comp
        assert "daily_rates" in first_comp
        
        # Verify daily rates
        assert len(first_comp["daily_rates"]) > 0
        first_rate = first_comp["daily_rates"][0]
        assert "date" in first_rate
        assert "rate" in first_rate
        assert "dow" in first_rate
        
        # Verify market average
        assert "market_avg" in data
        
        print(f"Competitors: Your ADR=£{data['your_adr']}, Market Avg=£{data['market_avg']}, Competitors={len(data['competitors'])}")


class TestAuthProtection:
    """Verify all endpoints require authentication"""
    
    def test_forecasting_requires_auth(self):
        """Forecasting endpoint requires auth"""
        response = requests.get(f"{BASE_URL}/api/revenue/forecasting/{PROPERTY_ID}")
        assert response.status_code in [401, 403]
    
    def test_performance_requires_auth(self):
        """Performance endpoint requires auth"""
        response = requests.get(f"{BASE_URL}/api/revenue/analytics/performance/{PROPERTY_ID}")
        assert response.status_code in [401, 403]
    
    def test_pickup_requires_auth(self):
        """Pickup endpoint requires auth"""
        response = requests.get(f"{BASE_URL}/api/revenue/analytics/pickup/{PROPERTY_ID}")
        assert response.status_code in [401, 403]
    
    def test_budget_requires_auth(self):
        """Budget endpoint requires auth"""
        response = requests.get(f"{BASE_URL}/api/revenue/analytics/budget/{PROPERTY_ID}")
        assert response.status_code in [401, 403]
    
    def test_playbooks_requires_auth(self):
        """Playbooks endpoint requires auth"""
        response = requests.get(f"{BASE_URL}/api/revenue/playbooks/{PROPERTY_ID}")
        assert response.status_code in [401, 403]
    
    def test_experiments_requires_auth(self):
        """Experiments endpoint requires auth"""
        response = requests.get(f"{BASE_URL}/api/revenue/experiments/{PROPERTY_ID}")
        assert response.status_code in [401, 403]
    
    def test_parity_requires_auth(self):
        """Parity endpoint requires auth"""
        response = requests.get(f"{BASE_URL}/api/revenue/parity/{PROPERTY_ID}")
        assert response.status_code in [401, 403]
    
    def test_overbooking_requires_auth(self):
        """Overbooking endpoint requires auth"""
        response = requests.get(f"{BASE_URL}/api/revenue/overbooking/{PROPERTY_ID}")
        assert response.status_code in [401, 403]
    
    def test_action_center_requires_auth(self):
        """Action Center endpoint requires auth"""
        response = requests.get(f"{BASE_URL}/api/revenue/action-center/{PROPERTY_ID}")
        assert response.status_code in [401, 403]
    
    def test_profit_os_requires_auth(self):
        """Profit OS endpoint requires auth"""
        response = requests.get(f"{BASE_URL}/api/revenue/profit-os/{PROPERTY_ID}")
        assert response.status_code in [401, 403]
    
    def test_distribution_requires_auth(self):
        """Distribution endpoint requires auth"""
        response = requests.get(f"{BASE_URL}/api/revenue/distribution/{PROPERTY_ID}")
        assert response.status_code in [401, 403]
    
    def test_competitors_requires_auth(self):
        """Competitors endpoint requires auth"""
        response = requests.get(f"{BASE_URL}/api/revenue/competitors/{PROPERTY_ID}")
        assert response.status_code in [401, 403]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
