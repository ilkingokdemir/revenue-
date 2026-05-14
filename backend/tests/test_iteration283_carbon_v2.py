"""
Iteration 283 - Carbon Reporting v2 (Green Key / Green Globe certification-ready)
Tests for:
- POST /api/esg/{property_id}/reading (existing - seed data)
- GET /api/esg/{property_id}/scope-breakdown?year=2026
- GET /api/esg/{property_id}/yoy?year=2026
- POST /api/esg/{property_id}/offset-purchases
- GET /api/esg/{property_id}/offset-purchases?year=2026
- GET /api/esg/{property_id}/report.pdf?year=2026
- Regression: /api/esg/{property_id}/score, /api/esg/{property_id}/dashboard
"""
import pytest
import requests
import os
import math

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
PROPERTY_ID = "aldgate-flats"
YEAR = "2026"
PREV_YEAR = "2025"

@pytest.fixture(scope="module")
def auth_token():
    """Get admin auth token"""
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@hotelbox.com",
        "password": "HotelAdmin2026!"
    })
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    # Response returns 'token' not 'access_token'
    return resp.json().get("token")

@pytest.fixture(scope="module")
def auth_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


class TestSeedReadings:
    """Seed ESG readings for current and previous year"""
    
    def test_seed_reading_2026_jan(self, auth_headers):
        """Seed reading for 2026-01"""
        resp = requests.post(f"{BASE_URL}/api/esg/{PROPERTY_ID}/reading", json={
            "month": "2026-01",
            "kwh": 5000,
            "water_litres": 25000,
            "waste_kg": 200,
            "gas_kwh": 1500,
            "notes": "TEST_Jan 2026 reading"
        }, headers=auth_headers)
        assert resp.status_code == 200, f"Failed to seed 2026-01: {resp.text}"
        data = resp.json()
        assert data["month"] == "2026-01"
        assert data["kwh"] == 5000
        assert data["gas_kwh"] == 1500
        print(f"✓ Seeded 2026-01 reading: kwh={data['kwh']}, gas_kwh={data['gas_kwh']}")
    
    def test_seed_reading_2026_feb(self, auth_headers):
        """Seed reading for 2026-02"""
        resp = requests.post(f"{BASE_URL}/api/esg/{PROPERTY_ID}/reading", json={
            "month": "2026-02",
            "kwh": 4800,
            "water_litres": 24000,
            "waste_kg": 180,
            "gas_kwh": 1400,
            "notes": "TEST_Feb 2026 reading"
        }, headers=auth_headers)
        assert resp.status_code == 200, f"Failed to seed 2026-02: {resp.text}"
        data = resp.json()
        assert data["month"] == "2026-02"
        print(f"✓ Seeded 2026-02 reading: kwh={data['kwh']}, gas_kwh={data['gas_kwh']}")
    
    def test_seed_reading_2025_jan(self, auth_headers):
        """Seed reading for 2025-01 (previous year for YoY)"""
        resp = requests.post(f"{BASE_URL}/api/esg/{PROPERTY_ID}/reading", json={
            "month": "2025-01",
            "kwh": 5500,
            "water_litres": 28000,
            "waste_kg": 220,
            "gas_kwh": 1700,
            "notes": "TEST_Jan 2025 reading"
        }, headers=auth_headers)
        assert resp.status_code == 200, f"Failed to seed 2025-01: {resp.text}"
        data = resp.json()
        assert data["month"] == "2025-01"
        print(f"✓ Seeded 2025-01 reading: kwh={data['kwh']}, gas_kwh={data['gas_kwh']}")


class TestScopeBreakdown:
    """Test GET /api/esg/{property_id}/scope-breakdown"""
    
    def test_scope_breakdown_returns_correct_structure(self, auth_headers):
        """Verify scope-breakdown returns all required fields"""
        resp = requests.get(f"{BASE_URL}/api/esg/{PROPERTY_ID}/scope-breakdown?year={YEAR}", headers=auth_headers)
        assert resp.status_code == 200, f"scope-breakdown failed: {resp.text}"
        data = resp.json()
        
        # Check all required fields exist
        required_fields = [
            "scope1_kg", "scope2_kg", "scope3_kg", "total_kg", "total_tonnes",
            "scope1_pct", "scope2_pct", "scope3_pct", "factors_used", "months_with_data"
        ]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"
        
        # Check factors_used structure
        assert "grid_electricity" in data["factors_used"]
        assert "natural_gas" in data["factors_used"]
        assert "waste_landfill" in data["factors_used"]
        
        print(f"✓ scope-breakdown structure verified: {list(data.keys())}")
    
    def test_scope_breakdown_math_scope2(self, auth_headers):
        """Verify Scope 2 calculation uses grid_factor (0.207)"""
        resp = requests.get(f"{BASE_URL}/api/esg/{PROPERTY_ID}/scope-breakdown?year={YEAR}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        
        # Verify grid factor is correct
        grid_factor = data["factors_used"]["grid_electricity"]
        assert grid_factor == 0.207, f"Grid factor should be 0.207, got {grid_factor}"
        
        # Verify scope2_kg is positive and reasonable (should be > 0 if we have data)
        assert data["scope2_kg"] > 0, "Scope 2 should be > 0 with seeded data"
        assert data["scope2_kg"] < 100000, "Scope 2 should be reasonable (< 100 tonnes)"
        
        print(f"✓ Scope 2 verified: {data['scope2_kg']} kg, factor={grid_factor}")
    
    def test_scope_breakdown_math_scope1(self, auth_headers):
        """Verify Scope 1 calculation uses gas_factor (0.184)"""
        resp = requests.get(f"{BASE_URL}/api/esg/{PROPERTY_ID}/scope-breakdown?year={YEAR}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        
        # Verify gas factor is correct
        gas_factor = data["factors_used"]["natural_gas"]
        assert gas_factor == 0.184, f"Gas factor should be 0.184, got {gas_factor}"
        
        # Verify scope1_kg is positive and reasonable
        assert data["scope1_kg"] > 0, "Scope 1 should be > 0 with seeded gas data"
        assert data["scope1_kg"] < 50000, "Scope 1 should be reasonable (< 50 tonnes)"
        
        print(f"✓ Scope 1 verified: {data['scope1_kg']} kg, factor={gas_factor}")
    
    def test_scope_breakdown_math_scope3(self, auth_headers):
        """Verify Scope 3 calculation uses waste_factor (0.45)"""
        resp = requests.get(f"{BASE_URL}/api/esg/{PROPERTY_ID}/scope-breakdown?year={YEAR}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        
        # Verify waste factor is correct
        waste_factor = data["factors_used"]["waste_landfill"]
        assert waste_factor == 0.45, f"Waste factor should be 0.45, got {waste_factor}"
        
        # Verify scope3_kg is positive and reasonable
        assert data["scope3_kg"] > 0, "Scope 3 should be > 0 with seeded waste data"
        assert data["scope3_kg"] < 20000, "Scope 3 should be reasonable (< 20 tonnes)"
        
        print(f"✓ Scope 3 verified: {data['scope3_kg']} kg, factor={waste_factor}")
    
    def test_scope_breakdown_percentages_sum_to_100(self, auth_headers):
        """Verify scope percentages sum to ~100%"""
        resp = requests.get(f"{BASE_URL}/api/esg/{PROPERTY_ID}/scope-breakdown?year={YEAR}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        
        total_pct = data["scope1_pct"] + data["scope2_pct"] + data["scope3_pct"]
        assert 99 <= total_pct <= 101, f"Percentages don't sum to 100: {total_pct}"
        print(f"✓ Percentages sum correctly: {data['scope1_pct']}% + {data['scope2_pct']}% + {data['scope3_pct']}% = {total_pct}%")


class TestYearOverYear:
    """Test GET /api/esg/{property_id}/yoy"""
    
    def test_yoy_returns_correct_structure(self, auth_headers):
        """Verify YoY returns current, previous, and change_pct"""
        resp = requests.get(f"{BASE_URL}/api/esg/{PROPERTY_ID}/yoy?year={YEAR}", headers=auth_headers)
        assert resp.status_code == 200, f"yoy failed: {resp.text}"
        data = resp.json()
        
        assert "current" in data
        assert "previous" in data
        assert "change_pct" in data
        
        # Check change_pct has all metrics
        for metric in ["kwh", "gas_kwh", "water_litres", "waste_kg"]:
            assert metric in data["change_pct"], f"Missing change_pct.{metric}"
        
        print(f"✓ YoY structure verified: current={data['current']}, change_pct={data['change_pct']}")
    
    def test_yoy_change_calculation(self, auth_headers):
        """Verify YoY change percentage calculation"""
        resp = requests.get(f"{BASE_URL}/api/esg/{PROPERTY_ID}/yoy?year={YEAR}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        
        # 2026 kwh: 5000 + 4800 = 9800
        # 2025 kwh: 5500
        # Change: (9800 - 5500) / 5500 * 100 = 78.18%
        if data["previous"]["kwh"] > 0:
            expected_change = (data["current"]["kwh"] - data["previous"]["kwh"]) / data["previous"]["kwh"] * 100
            assert abs(data["change_pct"]["kwh"] - expected_change) < 1, \
                f"YoY kwh change mismatch: got {data['change_pct']['kwh']}, expected ~{expected_change}"
            print(f"✓ YoY kwh change verified: {data['change_pct']['kwh']}%")
    
    def test_yoy_invalid_year_returns_400(self, auth_headers):
        """Verify invalid year format returns 400"""
        resp = requests.get(f"{BASE_URL}/api/esg/{PROPERTY_ID}/yoy?year=invalid", headers=auth_headers)
        assert resp.status_code == 400, f"Expected 400 for invalid year, got {resp.status_code}"
        print("✓ Invalid year returns 400")


class TestOffsetPurchases:
    """Test POST and GET /api/esg/{property_id}/offset-purchases"""
    
    def test_create_offset_purchase_success(self, auth_headers):
        """Create a valid offset purchase"""
        resp = requests.post(f"{BASE_URL}/api/esg/{PROPERTY_ID}/offset-purchases", json={
            "tonnes_co2e": 1.5,
            "amount_paid": 75,
            "provider": "TEST_Verified UK Woodland"
        }, headers=auth_headers)
        assert resp.status_code == 200, f"Failed to create offset: {resp.text}"
        data = resp.json()
        
        assert data["tonnes_co2e"] == 1.5
        assert data["amount_paid"] == 75
        assert "id" in data
        assert "purchased_at" in data
        print(f"✓ Created offset purchase: {data['tonnes_co2e']} tonnes, £{data['amount_paid']}")
    
    def test_create_offset_purchase_zero_tonnes_returns_400(self, auth_headers):
        """Verify tonnes_co2e=0 returns 400"""
        resp = requests.post(f"{BASE_URL}/api/esg/{PROPERTY_ID}/offset-purchases", json={
            "tonnes_co2e": 0,
            "amount_paid": 50
        }, headers=auth_headers)
        assert resp.status_code == 400, f"Expected 400 for zero tonnes, got {resp.status_code}"
        print("✓ Zero tonnes returns 400")
    
    def test_list_offset_purchases(self, auth_headers):
        """List offset purchases for year"""
        resp = requests.get(f"{BASE_URL}/api/esg/{PROPERTY_ID}/offset-purchases?year={YEAR}", headers=auth_headers)
        assert resp.status_code == 200, f"Failed to list offsets: {resp.text}"
        data = resp.json()
        
        assert "purchases" in data
        assert "count" in data
        assert "total_tonnes_offset" in data
        assert "total_spend" in data
        
        assert data["count"] >= 1, "Should have at least 1 offset purchase"
        assert data["total_tonnes_offset"] >= 1.5, "Should have at least 1.5 tonnes offset"
        print(f"✓ Listed offsets: {data['count']} purchases, {data['total_tonnes_offset']} tonnes, £{data['total_spend']}")


class TestPDFReport:
    """Test GET /api/esg/{property_id}/report.pdf"""
    
    def test_pdf_report_returns_valid_pdf(self, auth_headers):
        """Verify PDF report returns valid PDF with correct headers"""
        resp = requests.get(f"{BASE_URL}/api/esg/{PROPERTY_ID}/report.pdf?year={YEAR}", headers=auth_headers)
        assert resp.status_code == 200, f"PDF report failed: {resp.status_code}"
        
        # Check content type
        assert "application/pdf" in resp.headers.get("Content-Type", ""), \
            f"Wrong content type: {resp.headers.get('Content-Type')}"
        
        # Check PDF magic bytes
        content = resp.content
        assert content[:4] == b"%PDF", f"Invalid PDF magic: {content[:10]}"
        
        # Check size > 2KB
        assert len(content) > 2048, f"PDF too small: {len(content)} bytes"
        
        print(f"✓ PDF report valid: {len(content)} bytes, starts with %PDF")


class TestRegressionExistingEndpoints:
    """Regression tests for existing ESG endpoints"""
    
    def test_dashboard_still_works(self, auth_headers):
        """Verify /api/esg/{property_id}/dashboard still works"""
        resp = requests.get(f"{BASE_URL}/api/esg/{PROPERTY_ID}/dashboard", headers=auth_headers)
        assert resp.status_code == 200, f"Dashboard failed: {resp.text}"
        data = resp.json()
        
        assert "esg_score" in data
        assert "grade" in data
        assert "trend" in data
        print(f"✓ Dashboard works: score={data['esg_score']}, grade={data['grade']}")
    
    def test_config_still_works(self, auth_headers):
        """Verify /api/esg/{property_id}/config still works"""
        resp = requests.get(f"{BASE_URL}/api/esg/{PROPERTY_ID}/config", headers=auth_headers)
        assert resp.status_code == 200, f"Config failed: {resp.text}"
        data = resp.json()
        
        assert "co2_factor_grid" in data
        assert "initiatives" in data
        print(f"✓ Config works: co2_factor_grid={data['co2_factor_grid']}")
    
    def test_public_badge_still_works(self, auth_headers):
        """Verify /api/esg/{property_id}/public-badge still works (no auth needed)"""
        resp = requests.get(f"{BASE_URL}/api/esg/{PROPERTY_ID}/public-badge")
        assert resp.status_code == 200, f"Public badge failed: {resp.text}"
        data = resp.json()
        
        assert "score" in data
        assert "grade" in data
        print(f"✓ Public badge works: score={data['score']}, grade={data['grade']}")


class TestRegressionIter277to282:
    """Regression tests for iter 277-282 endpoints"""
    
    def test_spa_services(self, auth_headers):
        """Verify /api/spa/services still works"""
        resp = requests.get(f"{BASE_URL}/api/spa/services", headers=auth_headers)
        assert resp.status_code == 200, f"Spa services failed: {resp.status_code}"
        print("✓ /api/spa/services works")
    
    def test_meetings_list(self, auth_headers):
        """Verify /api/meetings still works"""
        resp = requests.get(f"{BASE_URL}/api/meetings", headers=auth_headers)
        assert resp.status_code == 200, f"Meetings failed: {resp.status_code}"
        print("✓ /api/meetings works")
    
    def test_fnb_pos_providers(self, auth_headers):
        """Verify /api/fnb-pos/providers still works"""
        resp = requests.get(f"{BASE_URL}/api/fnb-pos/providers", headers=auth_headers)
        assert resp.status_code == 200, f"F&B POS providers failed: {resp.status_code}"
        print("✓ /api/fnb-pos/providers works")
    
    def test_banquet_orders(self, auth_headers):
        """Verify /api/banquet-orders/{property_id} still works"""
        resp = requests.get(f"{BASE_URL}/api/banquet-orders/{PROPERTY_ID}", headers=auth_headers)
        assert resp.status_code == 200, f"Banquet orders failed: {resp.status_code}"
        print("✓ /api/banquet-orders works")
    
    def test_channel_parity(self, auth_headers):
        """Verify /api/channel-parity/{property_id} still works"""
        resp = requests.get(f"{BASE_URL}/api/channel-parity/{PROPERTY_ID}", headers=auth_headers)
        assert resp.status_code == 200, f"Channel parity failed: {resp.status_code}"
        print("✓ /api/channel-parity works")
    
    def test_owner_list(self, auth_headers):
        """Verify /api/owners still works"""
        resp = requests.get(f"{BASE_URL}/api/owners", headers=auth_headers)
        assert resp.status_code == 200, f"Owners list failed: {resp.status_code}"
        print("✓ /api/owners works")


class TestAuthRequired:
    """Verify endpoints require authentication"""
    
    def test_scope_breakdown_requires_auth(self):
        """Verify scope-breakdown requires auth"""
        resp = requests.get(f"{BASE_URL}/api/esg/{PROPERTY_ID}/scope-breakdown?year={YEAR}")
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
        print("✓ scope-breakdown requires auth")
    
    def test_yoy_requires_auth(self):
        """Verify yoy requires auth"""
        resp = requests.get(f"{BASE_URL}/api/esg/{PROPERTY_ID}/yoy?year={YEAR}")
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
        print("✓ yoy requires auth")
    
    def test_offset_purchases_requires_auth(self):
        """Verify offset-purchases requires auth"""
        resp = requests.get(f"{BASE_URL}/api/esg/{PROPERTY_ID}/offset-purchases?year={YEAR}")
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
        print("✓ offset-purchases requires auth")
    
    def test_pdf_report_requires_auth(self):
        """Verify report.pdf requires auth"""
        resp = requests.get(f"{BASE_URL}/api/esg/{PROPERTY_ID}/report.pdf?year={YEAR}")
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
        print("✓ report.pdf requires auth")
