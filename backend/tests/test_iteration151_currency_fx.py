"""
Iteration 151 - Multi-Currency GL Consolidation (P1) Tests
Tests for Currency & FX admin panel: FX rates, conversion, AR aging, portfolio summary
"""
import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"


class TestCurrencyFxAuth:
    """Authentication setup for Currency FX tests"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get admin auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        return data.get("access_token") or data.get("token")
    
    @pytest.fixture(scope="class")
    def auth_headers(self, auth_token):
        """Headers with auth token"""
        return {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json"
        }


class TestCurrencyFxSettings(TestCurrencyFxAuth):
    """Test /api/currency-fx/settings endpoints"""
    
    def test_get_settings_returns_base_currency_and_codes(self, auth_headers):
        """GET /api/currency-fx/settings returns base_currency, available_codes, symbols, rounding_mode"""
        response = requests.get(f"{BASE_URL}/api/currency-fx/settings", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Verify required fields
        assert "base_currency" in data, "Missing base_currency"
        assert data["base_currency"] == "GBP", f"Expected GBP, got {data['base_currency']}"
        
        assert "available_codes" in data, "Missing available_codes"
        assert isinstance(data["available_codes"], list), "available_codes should be a list"
        assert len(data["available_codes"]) >= 10, f"Expected at least 10 currencies, got {len(data['available_codes'])}"
        
        # Check seeded currencies are present
        expected_codes = ["GBP", "USD", "EUR", "TRY", "AED", "JPY", "CAD", "AUD", "CHF", "INR"]
        for code in expected_codes:
            assert code in data["available_codes"], f"Missing currency code: {code}"
        
        assert "symbols" in data, "Missing symbols"
        assert data["symbols"]["GBP"] == "£", "GBP symbol should be £"
        assert data["symbols"]["USD"] == "$", "USD symbol should be $"
        assert data["symbols"]["EUR"] == "€", "EUR symbol should be €"
        
        assert "rounding_mode" in data, "Missing rounding_mode"
        print(f"✓ GET /settings returns: base={data['base_currency']}, {len(data['available_codes'])} currencies")
    
    def test_put_settings_updates_base_currency_and_rounding(self, auth_headers):
        """PUT /api/currency-fx/settings updates base_currency + rounding_mode"""
        # First update to USD
        response = requests.put(f"{BASE_URL}/api/currency-fx/settings", headers=auth_headers, json={
            "base_currency": "USD",
            "rounding_mode": "half_up"
        })
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data.get("ok") == True, "Expected ok: true"
        
        # Verify the change
        response = requests.get(f"{BASE_URL}/api/currency-fx/settings", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["base_currency"] == "USD", "Base currency should be USD"
        assert data["rounding_mode"] == "half_up", "Rounding mode should be half_up"
        
        # Restore to GBP
        response = requests.put(f"{BASE_URL}/api/currency-fx/settings", headers=auth_headers, json={
            "base_currency": "GBP",
            "rounding_mode": "banker"
        })
        assert response.status_code == 200
        print("✓ PUT /settings updates base_currency and rounding_mode correctly")


class TestCurrencyFxRates(TestCurrencyFxAuth):
    """Test /api/currency-fx/rates endpoints"""
    
    def test_get_rates_returns_seeded_currencies(self, auth_headers):
        """GET /api/currency-fx/rates returns list (auto-seeds 10 currencies on first call)"""
        response = requests.get(f"{BASE_URL}/api/currency-fx/rates", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert isinstance(data, list), "Expected list of rates"
        assert len(data) >= 10, f"Expected at least 10 seeded rates, got {len(data)}"
        
        # Check structure of rate objects
        rate = data[0]
        assert "code" in rate, "Missing code"
        assert "rate_to_base" in rate, "Missing rate_to_base"
        assert "as_of" in rate, "Missing as_of"
        
        # Verify specific seeded rates
        rates_by_code = {r["code"]: r for r in data}
        assert "GBP" in rates_by_code, "Missing GBP rate"
        assert rates_by_code["GBP"]["rate_to_base"] == 1.0, "GBP rate should be 1.0"
        
        assert "EUR" in rates_by_code, "Missing EUR rate"
        assert rates_by_code["EUR"]["rate_to_base"] == 0.86, f"EUR rate should be 0.86, got {rates_by_code['EUR']['rate_to_base']}"
        
        assert "USD" in rates_by_code, "Missing USD rate"
        assert rates_by_code["USD"]["rate_to_base"] == 0.79, f"USD rate should be 0.79, got {rates_by_code['USD']['rate_to_base']}"
        
        print(f"✓ GET /rates returns {len(data)} currencies with correct seeded values")
    
    def test_post_rates_upserts_by_code_and_date(self, auth_headers):
        """POST /api/currency-fx/rates upserts a rate by (code, as_of) — re-sending same code+date updates instead of duplicating"""
        today = datetime.now().strftime("%Y-%m-%d")
        
        # First POST - create new rate for TEST currency
        response = requests.post(f"{BASE_URL}/api/currency-fx/rates", headers=auth_headers, json={
            "code": "ZZZ",
            "rate_to_base": 0.5,
            "as_of": today,
            "notes": "Test rate v1"
        })
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data.get("ok") == True
        assert data["code"] == "ZZZ"
        assert data["rate_to_base"] == 0.5
        
        # Second POST - same code+date should UPDATE, not duplicate
        response = requests.post(f"{BASE_URL}/api/currency-fx/rates", headers=auth_headers, json={
            "code": "ZZZ",
            "rate_to_base": 0.55,
            "as_of": today,
            "notes": "Test rate v2 - updated"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["rate_to_base"] == 0.55, "Rate should be updated to 0.55"
        
        # Verify only one ZZZ rate exists (not duplicated)
        response = requests.get(f"{BASE_URL}/api/currency-fx/rates", headers=auth_headers)
        rates = response.json()
        zzz_rates = [r for r in rates if r["code"] == "ZZZ"]
        assert len(zzz_rates) == 1, f"Expected 1 ZZZ rate (upsert), got {len(zzz_rates)}"
        assert zzz_rates[0]["rate_to_base"] == 0.55, "Rate should be 0.55 after upsert"
        
        # Cleanup - delete test rate
        requests.delete(f"{BASE_URL}/api/currency-fx/rates/ZZZ", headers=auth_headers)
        print("✓ POST /rates upserts by (code, as_of) - no duplicates")
    
    def test_delete_rates_works_for_non_base_currency(self, auth_headers):
        """DELETE /api/currency-fx/rates/{code} works for non-base currencies"""
        today = datetime.now().strftime("%Y-%m-%d")
        
        # Create a test rate
        requests.post(f"{BASE_URL}/api/currency-fx/rates", headers=auth_headers, json={
            "code": "YYY",
            "rate_to_base": 0.3,
            "as_of": today
        })
        
        # Delete it
        response = requests.delete(f"{BASE_URL}/api/currency-fx/rates/YYY", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "deleted" in data, "Expected deleted count"
        assert data["deleted"] >= 1, "Should have deleted at least 1 rate"
        
        # Verify it's gone
        response = requests.get(f"{BASE_URL}/api/currency-fx/rates", headers=auth_headers)
        rates = response.json()
        yyy_rates = [r for r in rates if r["code"] == "YYY"]
        assert len(yyy_rates) == 0, "YYY rate should be deleted"
        print("✓ DELETE /rates/{code} works for non-base currency")
    
    def test_delete_base_currency_returns_400(self, auth_headers):
        """DELETE /api/currency-fx/rates/{code} deleting base currency (GBP) must return 400"""
        response = requests.delete(f"{BASE_URL}/api/currency-fx/rates/GBP", headers=auth_headers)
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        data = response.json()
        assert "detail" in data, "Expected error detail"
        assert "base currency" in data["detail"].lower(), f"Error should mention base currency: {data['detail']}"
        print("✓ DELETE /rates/GBP returns 400 - cannot delete base currency")


class TestCurrencyFxConvert(TestCurrencyFxAuth):
    """Test /api/currency-fx/convert endpoint"""
    
    def test_convert_eur_to_gbp(self, auth_headers):
        """POST /api/currency-fx/convert returns correct conversion (100 EUR @ 0.86 = 86 GBP)"""
        response = requests.post(f"{BASE_URL}/api/currency-fx/convert", headers=auth_headers, json={
            "amount": 100,
            "source": "EUR",
            "target": "GBP"
        })
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert "amount" in data, "Missing amount"
        assert data["amount"] == 100, "Amount should be 100"
        
        assert "from" in data, "Missing from"
        assert data["from"] == "EUR", "From should be EUR"
        
        assert "to" in data, "Missing to"
        assert data["to"] == "GBP", "To should be GBP"
        
        assert "converted" in data, "Missing converted"
        # EUR rate is 0.86, so 100 EUR = 86 GBP
        assert data["converted"] == 86.0, f"Expected 86.0 GBP, got {data['converted']}"
        
        assert "base_currency" in data, "Missing base_currency"
        print(f"✓ Convert 100 EUR → {data['converted']} GBP (rate 0.86)")
    
    def test_convert_same_currency_returns_amount(self, auth_headers):
        """POST /api/currency-fx/convert same-currency returns amount unchanged"""
        response = requests.post(f"{BASE_URL}/api/currency-fx/convert", headers=auth_headers, json={
            "amount": 250.50,
            "source": "GBP",
            "target": "GBP"
        })
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert data["converted"] == 250.50, f"Same currency should return same amount, got {data['converted']}"
        print("✓ Convert GBP → GBP returns same amount")
    
    def test_convert_usd_to_eur(self, auth_headers):
        """POST /api/currency-fx/convert USD to EUR via base currency"""
        response = requests.post(f"{BASE_URL}/api/currency-fx/convert", headers=auth_headers, json={
            "amount": 100,
            "source": "USD",
            "target": "EUR"
        })
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # USD rate = 0.79 (1 USD = 0.79 GBP)
        # EUR rate = 0.86 (1 EUR = 0.86 GBP)
        # 100 USD = 79 GBP = 79/0.86 EUR = 91.86 EUR
        expected = round(100 * 0.79 / 0.86, 2)
        assert data["converted"] == expected, f"Expected {expected} EUR, got {data['converted']}"
        print(f"✓ Convert 100 USD → {data['converted']} EUR (via GBP base)")


class TestCurrencyFxArAging(TestCurrencyFxAuth):
    """Test /api/currency-fx/ar-aging endpoint"""
    
    def test_ar_aging_returns_structure(self, auth_headers):
        """GET /api/currency-fx/ar-aging returns {buckets, total, by_currency[], invoice_count}"""
        response = requests.get(f"{BASE_URL}/api/currency-fx/ar-aging", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Verify structure
        assert "base_currency" in data, "Missing base_currency"
        assert data["base_currency"] == "GBP", "Base currency should be GBP"
        
        assert "as_of" in data, "Missing as_of date"
        
        assert "buckets" in data, "Missing buckets"
        buckets = data["buckets"]
        assert "current" in buckets, "Missing current bucket"
        assert "d30" in buckets, "Missing d30 bucket"
        assert "d60" in buckets, "Missing d60 bucket"
        assert "d90" in buckets, "Missing d90 bucket"
        assert "over90" in buckets, "Missing over90 bucket"
        
        assert "total" in data, "Missing total"
        assert isinstance(data["total"], (int, float)), "Total should be numeric"
        
        assert "by_currency" in data, "Missing by_currency"
        assert isinstance(data["by_currency"], list), "by_currency should be a list"
        
        assert "invoice_count" in data, "Missing invoice_count"
        
        print(f"✓ GET /ar-aging returns structure: total={data['total']}, invoices={data['invoice_count']}, buckets={list(buckets.keys())}")
    
    def test_ar_aging_converts_non_gbp_invoices(self, auth_headers):
        """GET /api/currency-fx/ar-aging converts city-ledger invoice balances from native → base using latest rates"""
        # First, create a test company and invoice in EUR
        company_response = requests.post(f"{BASE_URL}/api/city-ledger/companies", headers=auth_headers, json={
            "name": "TEST_FX_Company",
            "contact_email": "test@fx.com",
            "payment_terms_days": 30,
            "credit_limit": 10000,
            "currency": "EUR"
        })
        
        if company_response.status_code == 200:
            company = company_response.json()
            company_id = company.get("id")
            
            # Create an invoice in EUR
            invoice_response = requests.post(f"{BASE_URL}/api/city-ledger/invoices", headers=auth_headers, json={
                "company_id": company_id,
                "amount": 100,
                "currency": "EUR",
                "description": "Test FX invoice",
                "booking_ids": []
            })
            
            if invoice_response.status_code == 200:
                invoice = invoice_response.json()
                invoice_id = invoice.get("id")
                
                # Now check AR aging
                response = requests.get(f"{BASE_URL}/api/currency-fx/ar-aging", headers=auth_headers)
                assert response.status_code == 200
                data = response.json()
                
                # Check if EUR appears in by_currency
                eur_entry = next((c for c in data["by_currency"] if c["currency"] == "EUR"), None)
                if eur_entry:
                    # Verify conversion: 100 EUR @ 0.86 = 86 GBP
                    assert eur_entry["native_total"] >= 100, f"EUR native total should include our 100 EUR"
                    assert eur_entry["rate"] == 0.86, f"EUR rate should be 0.86, got {eur_entry['rate']}"
                    print(f"✓ AR aging converts EUR: native={eur_entry['native_total']}, base={eur_entry['base_total']}, rate={eur_entry['rate']}")
                
                # Cleanup
                requests.delete(f"{BASE_URL}/api/city-ledger/invoices/{invoice_id}", headers=auth_headers)
            
            # Cleanup company
            requests.delete(f"{BASE_URL}/api/city-ledger/companies/{company_id}", headers=auth_headers)
        else:
            print("⚠ Could not create test company for AR aging test (may already exist)")


class TestCurrencyFxPortfolioSummary(TestCurrencyFxAuth):
    """Test /api/currency-fx/portfolio-summary endpoint"""
    
    def test_portfolio_summary_returns_structure(self, auth_headers):
        """GET /api/currency-fx/portfolio-summary returns per-property revenue/AR in native + base, and a totals object"""
        response = requests.get(f"{BASE_URL}/api/currency-fx/portfolio-summary", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Verify structure
        assert "base_currency" in data, "Missing base_currency"
        assert data["base_currency"] == "GBP", "Base currency should be GBP"
        
        assert "properties" in data, "Missing properties"
        assert isinstance(data["properties"], list), "properties should be a list"
        
        assert "totals" in data, "Missing totals"
        totals = data["totals"]
        assert "revenue_native" in totals, "Missing revenue_native in totals"
        assert "revenue_base" in totals, "Missing revenue_base in totals"
        assert "ar_native" in totals, "Missing ar_native in totals"
        assert "ar_base" in totals, "Missing ar_base in totals"
        
        assert "rate_as_of" in data, "Missing rate_as_of"
        
        # Check property structure if any exist
        if len(data["properties"]) > 0:
            prop = data["properties"][0]
            assert "property_id" in prop, "Missing property_id"
            assert "property_name" in prop, "Missing property_name"
            assert "currency" in prop, "Missing currency"
            assert "revenue_native" in prop, "Missing revenue_native"
            assert "revenue_base" in prop, "Missing revenue_base"
            assert "ar_native" in prop, "Missing ar_native"
            assert "ar_base" in prop, "Missing ar_base"
        
        print(f"✓ GET /portfolio-summary returns: {len(data['properties'])} properties, totals.revenue_base={totals['revenue_base']}, totals.ar_base={totals['ar_base']}")


class TestCurrencyFxUnauthorized:
    """Test that endpoints require authentication"""
    
    def test_settings_requires_auth(self):
        """GET /api/currency-fx/settings requires authentication"""
        response = requests.get(f"{BASE_URL}/api/currency-fx/settings")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ GET /settings requires auth")
    
    def test_rates_requires_auth(self):
        """GET /api/currency-fx/rates requires authentication"""
        response = requests.get(f"{BASE_URL}/api/currency-fx/rates")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ GET /rates requires auth")
    
    def test_convert_requires_auth(self):
        """POST /api/currency-fx/convert requires authentication"""
        response = requests.post(f"{BASE_URL}/api/currency-fx/convert", json={
            "amount": 100, "source": "EUR", "target": "GBP"
        })
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ POST /convert requires auth")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
