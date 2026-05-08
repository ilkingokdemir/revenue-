"""
Iteration 164 - Inventory Allocations + Derived Rates + Stop-Sell Tests
Tests the 3 new tabs added to ChannelManagerHub:
1. Allocations (pooled/dedicated/capped inventory per channel×room)
2. Derived Rates (child rate plans floating X% above/below parent)
3. Stop-Sell (channel×date heatmap with toggle)
"""
import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
PROPERTY_ID = "aldgate-flats"

class TestAuth:
    """Authentication setup"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get admin auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "token" in data, f"Token not in response: {data}"
        return data["token"]
    
    @pytest.fixture(scope="class")
    def auth_headers(self, auth_token):
        """Headers with auth token"""
        return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


class TestSeedDemo(TestAuth):
    """Seed demo data before testing"""
    
    def test_seed_demo_data(self, auth_headers):
        """Seed demo channels and room types"""
        response = requests.post(f"{BASE_URL}/api/channel-hub/{PROPERTY_ID}/seed-demo", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "seeded" in data or "status" in data
        print(f"Seed demo response: {data}")


class TestInventoryAllocationsRules(TestAuth):
    """Test /api/inventory-allocations endpoints for allocation rules"""
    
    def test_list_rules_requires_auth(self):
        """GET /api/inventory-allocations/{pid} requires auth"""
        response = requests.get(f"{BASE_URL}/api/inventory-allocations/{PROPERTY_ID}")
        assert response.status_code == 401
        print("PASS: List rules requires auth")
    
    def test_list_rules_returns_structure(self, auth_headers):
        """GET returns {rules, channels, room_types}"""
        response = requests.get(f"{BASE_URL}/api/inventory-allocations/{PROPERTY_ID}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "rules" in data
        assert "channels" in data
        assert "room_types" in data
        assert isinstance(data["rules"], list)
        assert isinstance(data["channels"], list)
        assert isinstance(data["room_types"], list)
        print(f"PASS: List rules returns structure - {len(data['rules'])} rules, {len(data['channels'])} channels, {len(data['room_types'])} rooms")
    
    def test_upsert_rule_missing_fields(self, auth_headers):
        """PUT /upsert with missing fields returns 400"""
        response = requests.put(
            f"{BASE_URL}/api/inventory-allocations/{PROPERTY_ID}/upsert",
            headers=auth_headers,
            json={"channel_id": "booking_com"}  # missing room_type_id and mode
        )
        assert response.status_code == 400
        print("PASS: Upsert missing fields returns 400")
    
    def test_upsert_rule_invalid_mode(self, auth_headers):
        """PUT /upsert with invalid mode returns 400"""
        response = requests.put(
            f"{BASE_URL}/api/inventory-allocations/{PROPERTY_ID}/upsert",
            headers=auth_headers,
            json={"channel_id": "booking_com", "room_type_id": "double-aldgate-flats", "mode": "invalid"}
        )
        assert response.status_code == 400
        assert "mode must be" in response.json().get("detail", "")
        print("PASS: Upsert invalid mode returns 400")
    
    def test_upsert_dedicated_requires_cap(self, auth_headers):
        """PUT /upsert mode=dedicated with cap=0 returns 400"""
        response = requests.put(
            f"{BASE_URL}/api/inventory-allocations/{PROPERTY_ID}/upsert",
            headers=auth_headers,
            json={"channel_id": "booking_com", "room_type_id": "double-aldgate-flats", "mode": "dedicated", "allocation_cap": 0}
        )
        assert response.status_code == 400
        assert "allocation_cap > 0 required" in response.json().get("detail", "")
        print("PASS: Dedicated mode requires cap > 0")
    
    def test_upsert_capped_requires_cap(self, auth_headers):
        """PUT /upsert mode=capped with cap=0 returns 400"""
        response = requests.put(
            f"{BASE_URL}/api/inventory-allocations/{PROPERTY_ID}/upsert",
            headers=auth_headers,
            json={"channel_id": "booking_com", "room_type_id": "double-aldgate-flats", "mode": "capped", "allocation_cap": 0}
        )
        assert response.status_code == 400
        print("PASS: Capped mode requires cap > 0")
    
    def test_upsert_pooled_allows_zero_cap(self, auth_headers):
        """PUT /upsert mode=pooled with cap=0 is allowed"""
        response = requests.put(
            f"{BASE_URL}/api/inventory-allocations/{PROPERTY_ID}/upsert",
            headers=auth_headers,
            json={"channel_id": "booking_com", "room_type_id": "double-aldgate-flats", "mode": "pooled", "allocation_cap": 0, "buffer": 1}
        )
        assert response.status_code == 200
        assert response.json().get("status") == "ok"
        print("PASS: Pooled mode allows cap=0")
    
    def test_upsert_dedicated_rule(self, auth_headers):
        """PUT /upsert creates dedicated rule with cap=5"""
        response = requests.put(
            f"{BASE_URL}/api/inventory-allocations/{PROPERTY_ID}/upsert",
            headers=auth_headers,
            json={
                "channel_id": "expedia",
                "room_type_id": "double-aldgate-flats",
                "mode": "dedicated",
                "allocation_cap": 5,
                "buffer": 1,
                "spillover_priority": 5
            }
        )
        assert response.status_code == 200
        assert response.json().get("status") == "ok"
        print("PASS: Created dedicated rule with cap=5")
    
    def test_upsert_capped_rule(self, auth_headers):
        """PUT /upsert creates capped rule"""
        response = requests.put(
            f"{BASE_URL}/api/inventory-allocations/{PROPERTY_ID}/upsert",
            headers=auth_headers,
            json={
                "channel_id": "airbnb",
                "room_type_id": "double-aldgate-flats",
                "mode": "capped",
                "allocation_cap": 3,
                "buffer": 0,
                "spillover_priority": 10
            }
        )
        assert response.status_code == 200
        print("PASS: Created capped rule")
    
    def test_list_rules_after_create(self, auth_headers):
        """GET returns created rules"""
        response = requests.get(f"{BASE_URL}/api/inventory-allocations/{PROPERTY_ID}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        rules = data["rules"]
        # Should have at least the rules we created
        modes = [r["mode"] for r in rules]
        assert "pooled" in modes or "dedicated" in modes or "capped" in modes
        print(f"PASS: Found {len(rules)} rules after create")
    
    def test_delete_rule_not_found(self, auth_headers):
        """DELETE nonexistent rule returns not_found"""
        response = requests.delete(f"{BASE_URL}/api/inventory-allocations/nonexistent-id", headers=auth_headers)
        assert response.status_code == 200
        assert response.json().get("status") == "not_found"
        print("PASS: Delete nonexistent returns not_found")


class TestInventoryAllocationsCalendar(TestAuth):
    """Test /api/inventory-allocations/{pid}/calendar endpoint"""
    
    def test_calendar_requires_auth(self):
        """GET /calendar requires auth"""
        response = requests.get(f"{BASE_URL}/api/inventory-allocations/{PROPERTY_ID}/calendar")
        assert response.status_code == 401
        print("PASS: Calendar requires auth")
    
    def test_calendar_default_14_days(self, auth_headers):
        """GET /calendar without dates returns 14-day range"""
        response = requests.get(f"{BASE_URL}/api/inventory-allocations/{PROPERTY_ID}/calendar", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "dates" in data
        assert "grid" in data
        assert len(data["dates"]) == 15  # 14 days inclusive = 15 dates
        print(f"PASS: Calendar returns {len(data['dates'])} dates (default 14-day range)")
    
    def test_calendar_custom_range(self, auth_headers):
        """GET /calendar with from_date/to_date"""
        today = datetime.now().strftime("%Y-%m-%d")
        end = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
        response = requests.get(
            f"{BASE_URL}/api/inventory-allocations/{PROPERTY_ID}/calendar?from_date={today}&to_date={end}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["dates"]) == 8  # 7 days inclusive = 8 dates
        print(f"PASS: Calendar custom range returns {len(data['dates'])} dates")
    
    def test_calendar_max_90_days(self, auth_headers):
        """GET /calendar with >90 day range returns 400"""
        today = datetime.now().strftime("%Y-%m-%d")
        end = (datetime.now() + timedelta(days=100)).strftime("%Y-%m-%d")
        response = requests.get(
            f"{BASE_URL}/api/inventory-allocations/{PROPERTY_ID}/calendar?from_date={today}&to_date={end}",
            headers=auth_headers
        )
        assert response.status_code == 400
        assert "90 days" in response.json().get("detail", "")
        print("PASS: Calendar rejects >90 day range")
    
    def test_calendar_grid_structure(self, auth_headers):
        """GET /calendar grid has correct structure"""
        response = requests.get(f"{BASE_URL}/api/inventory-allocations/{PROPERTY_ID}/calendar", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        if len(data["grid"]) > 0:
            row = data["grid"][0]
            assert "room_type_id" in row
            assert "room_type_name" in row
            assert "channel_id" in row
            assert "channel_name" in row
            assert "mode" in row
            assert "cells" in row
            assert isinstance(row["cells"], list)
            if len(row["cells"]) > 0:
                cell = row["cells"][0]
                assert "date" in cell
                assert "available" in cell
                assert "sold_on_channel" in cell
                assert "sold_all" in cell
                assert "total_inventory" in cell
            print(f"PASS: Calendar grid has correct structure - {len(data['grid'])} rows")
        else:
            print("PASS: Calendar grid empty (no channels configured)")


class TestDerivedRates(TestAuth):
    """Test /api/rate-structure/derived endpoints"""
    
    created_product_id = None
    created_derived_id = None
    
    def test_list_products(self, auth_headers):
        """GET /rate-structure/products returns list"""
        response = requests.get(f"{BASE_URL}/api/rate-structure/products?property_id={PROPERTY_ID}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"PASS: List products returns {len(data)} products")
    
    def test_create_product(self, auth_headers):
        """POST /rate-structure/products creates a rate product"""
        response = requests.post(
            f"{BASE_URL}/api/rate-structure/products",
            headers=auth_headers,
            json={
                "property_id": PROPERTY_ID,
                "name": "TEST_BAR Rate",
                "code": "TEST_BAR",
                "kind": "flex",
                "meal_plan": "bed_breakfast",
                "cancellation_policy": "free_24h",
                "min_los": 1,
                "max_los": 14,
                "active": True
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["name"] == "TEST_BAR Rate"
        assert data["code"] == "TEST_BAR"
        TestDerivedRates.created_product_id = data["id"]
        print(f"PASS: Created rate product {data['id']}")
    
    def test_list_derived_rates(self, auth_headers):
        """GET /rate-structure/derived returns list"""
        response = requests.get(f"{BASE_URL}/api/rate-structure/derived?property_id={PROPERTY_ID}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"PASS: List derived rates returns {len(data)} rates")
    
    def test_create_derived_missing_parent(self, auth_headers):
        """POST /rate-structure/derived with invalid parent returns 404"""
        response = requests.post(
            f"{BASE_URL}/api/rate-structure/derived",
            headers=auth_headers,
            json={
                "property_id": PROPERTY_ID,
                "name": "TEST_Derived",
                "parent_product_id": "nonexistent-id",
                "basis": "percent",
                "adjustment": -10
            }
        )
        assert response.status_code == 404
        print("PASS: Create derived with invalid parent returns 404")
    
    def test_create_derived_rate(self, auth_headers):
        """POST /rate-structure/derived creates derived rate"""
        if not TestDerivedRates.created_product_id:
            pytest.skip("No parent product created")
        response = requests.post(
            f"{BASE_URL}/api/rate-structure/derived",
            headers=auth_headers,
            json={
                "property_id": PROPERTY_ID,
                "name": "TEST_Non-Refundable -15%",
                "parent_product_id": TestDerivedRates.created_product_id,
                "basis": "percent",
                "adjustment": -15,
                "active": True
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["name"] == "TEST_Non-Refundable -15%"
        assert data["adjustment"] == -15
        TestDerivedRates.created_derived_id = data["id"]
        print(f"PASS: Created derived rate {data['id']}")
    
    def test_evaluate_derived_rate(self, auth_headers):
        """POST /rate-structure/derived/{id}/evaluate computes derived price"""
        if not TestDerivedRates.created_derived_id:
            pytest.skip("No derived rate created")
        response = requests.post(
            f"{BASE_URL}/api/rate-structure/derived/{TestDerivedRates.created_derived_id}/evaluate",
            headers=auth_headers,
            json={"base": 150}
        )
        assert response.status_code == 200
        data = response.json()
        assert "base" in data
        assert "derived" in data
        assert data["base"] == 150
        # -15% of 150 = 127.5
        assert data["derived"] == 127.5
        print(f"PASS: Evaluate derived rate: base={data['base']} -> derived={data['derived']}")
    
    def test_delete_derived_rate(self, auth_headers):
        """DELETE /rate-structure/derived/{id} removes rate"""
        if not TestDerivedRates.created_derived_id:
            pytest.skip("No derived rate created")
        response = requests.delete(
            f"{BASE_URL}/api/rate-structure/derived/{TestDerivedRates.created_derived_id}",
            headers=auth_headers
        )
        assert response.status_code == 200
        assert response.json().get("deleted") == 1
        print("PASS: Deleted derived rate")
    
    def test_delete_product(self, auth_headers):
        """DELETE /rate-structure/products/{id} removes product"""
        if not TestDerivedRates.created_product_id:
            pytest.skip("No product created")
        response = requests.delete(
            f"{BASE_URL}/api/rate-structure/products/{TestDerivedRates.created_product_id}",
            headers=auth_headers
        )
        assert response.status_code == 200
        assert response.json().get("deleted") == 1
        print("PASS: Deleted rate product")


class TestChannelRestrictions(TestAuth):
    """Test /api/channel-restrictions endpoints (Stop-Sell)"""
    
    def test_list_restrictions_requires_auth(self):
        """GET /channel-restrictions/{pid} requires auth"""
        response = requests.get(f"{BASE_URL}/api/channel-restrictions/{PROPERTY_ID}")
        assert response.status_code == 401
        print("PASS: List restrictions requires auth")
    
    def test_list_restrictions_returns_structure(self, auth_headers):
        """GET returns {dates, channels, restrictions, index}"""
        response = requests.get(f"{BASE_URL}/api/channel-restrictions/{PROPERTY_ID}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "dates" in data
        assert "channels" in data
        assert "restrictions" in data
        assert "index" in data
        assert "from_date" in data
        assert "to_date" in data
        print(f"PASS: List restrictions returns structure - {len(data['dates'])} dates, {len(data['channels'])} channels")
    
    def test_bulk_upsert_missing_dates(self, auth_headers):
        """PUT /bulk with missing dates returns 400"""
        response = requests.put(
            f"{BASE_URL}/api/channel-restrictions/{PROPERTY_ID}/bulk",
            headers=auth_headers,
            json={"channel_ids": ["booking_com"]}
        )
        assert response.status_code == 400
        print("PASS: Bulk upsert missing dates returns 400")
    
    def test_bulk_upsert_missing_channels(self, auth_headers):
        """PUT /bulk with empty channel_ids returns 400"""
        today = datetime.now().strftime("%Y-%m-%d")
        response = requests.put(
            f"{BASE_URL}/api/channel-restrictions/{PROPERTY_ID}/bulk",
            headers=auth_headers,
            json={"from_date": today, "to_date": today, "channel_ids": []}
        )
        assert response.status_code == 400
        print("PASS: Bulk upsert empty channels returns 400")
    
    def test_bulk_upsert_stop_sell(self, auth_headers):
        """PUT /bulk sets stop_sell=true for a date"""
        today = datetime.now().strftime("%Y-%m-%d")
        response = requests.put(
            f"{BASE_URL}/api/channel-restrictions/{PROPERTY_ID}/bulk",
            headers=auth_headers,
            json={
                "from_date": today,
                "to_date": today,
                "channel_ids": ["booking_com"],
                "room_type_id": "all",
                "stop_sell": True
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "upserted" in data
        print(f"PASS: Bulk upsert stop_sell=true - {data['upserted']} upserted")
    
    def test_verify_stop_sell_set(self, auth_headers):
        """GET verifies stop_sell was set"""
        today = datetime.now().strftime("%Y-%m-%d")
        response = requests.get(
            f"{BASE_URL}/api/channel-restrictions/{PROPERTY_ID}?from_date={today}&to_date={today}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        # Check if booking_com has stop_sell=true for today
        found = False
        for r in data["restrictions"]:
            if r.get("channel_id") == "booking_com" and r.get("date") == today:
                assert r.get("stop_sell") == True
                found = True
                break
        assert found, "Stop-sell restriction not found"
        print("PASS: Verified stop_sell=true in restrictions")
    
    def test_bulk_upsert_clear_stop_sell(self, auth_headers):
        """PUT /bulk sets stop_sell=false to clear"""
        today = datetime.now().strftime("%Y-%m-%d")
        response = requests.put(
            f"{BASE_URL}/api/channel-restrictions/{PROPERTY_ID}/bulk",
            headers=auth_headers,
            json={
                "from_date": today,
                "to_date": today,
                "channel_ids": ["booking_com"],
                "room_type_id": "all",
                "stop_sell": False
            }
        )
        assert response.status_code == 200
        print("PASS: Cleared stop_sell")
    
    def test_bulk_upsert_min_los(self, auth_headers):
        """PUT /bulk sets min_los"""
        today = datetime.now().strftime("%Y-%m-%d")
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        response = requests.put(
            f"{BASE_URL}/api/channel-restrictions/{PROPERTY_ID}/bulk",
            headers=auth_headers,
            json={
                "from_date": today,
                "to_date": tomorrow,
                "channel_ids": ["expedia"],
                "room_type_id": "all",
                "min_los": 3,
                "max_los": 7
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["upserted"] >= 2  # 2 days
        print(f"PASS: Set min_los=3, max_los=7 - {data['upserted']} upserted")
    
    def test_clear_range(self, auth_headers):
        """POST /clear-range removes restrictions"""
        today = datetime.now().strftime("%Y-%m-%d")
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        response = requests.post(
            f"{BASE_URL}/api/channel-restrictions/{PROPERTY_ID}/clear-range",
            headers=auth_headers,
            json={
                "from_date": today,
                "to_date": tomorrow,
                "channel_ids": ["expedia"]
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "deleted" in data
        print(f"PASS: Clear range deleted {data['deleted']} restrictions")


class TestCleanup(TestAuth):
    """Cleanup test data"""
    
    def test_cleanup_allocation_rules(self, auth_headers):
        """Delete test allocation rules"""
        response = requests.get(f"{BASE_URL}/api/inventory-allocations/{PROPERTY_ID}", headers=auth_headers)
        if response.status_code == 200:
            rules = response.json().get("rules", [])
            for rule in rules:
                if rule.get("room_type_id") == "double-aldgate-flats":
                    requests.delete(f"{BASE_URL}/api/inventory-allocations/{rule['id']}", headers=auth_headers)
        print("PASS: Cleanup completed")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
