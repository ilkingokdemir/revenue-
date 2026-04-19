"""
Iteration 152 - Multi-Currency Line Items on City Ledger Invoices
-----------------------------------------------------------------
Tests for:
1. GET /api/currency-fx/rates returns 41 currencies (expanded from 10)
2. Auto-seed-on-missing-codes: _get_rate_map fills missing codes from SEED_RATES_TO_GBP
3. POST /api/city-ledger/invoices with multi-currency lines
4. Invoice amount computed from line totals converted to invoice currency
5. line_total_native and line_total_invoice_cur on each line
6. GET /api/city-ledger/invoices/{id}/pdf returns valid PDF with line items
7. KWD rate > 1 GBP (2.58) - conversion math handles rates above 1
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestIteration152MultiCurrencyLines:
    """Test multi-currency line items on City Ledger invoices"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: login and get auth token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login as admin
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        token = login_resp.json().get("token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        yield
        self.session.close()
    
    # ==================== CURRENCY FX RATES TESTS ====================
    
    def test_fx_rates_returns_41_currencies(self):
        """GET /api/currency-fx/rates should return 41 currencies (expanded from 10)"""
        resp = self.session.get(f"{BASE_URL}/api/currency-fx/rates")
        assert resp.status_code == 200, f"Failed: {resp.text}"
        rates = resp.json()
        
        # Should have at least 41 currencies
        assert len(rates) >= 41, f"Expected 41+ currencies, got {len(rates)}"
        
        # Extract currency codes
        codes = [r["code"] for r in rates]
        print(f"Total currencies: {len(codes)}")
        
        # Verify new currencies are present (added in iteration 152)
        new_currencies = ["PLN", "SEK", "NOK", "DKK", "ZAR", "SGD", "HKD", "MXN", 
                         "BRL", "NZD", "SAR", "QAR", "KWD", "CZK", "HUF", "RON", 
                         "THB", "CNY", "KRW", "IDR", "MYR", "PHP", "VND"]
        for cur in new_currencies:
            assert cur in codes, f"Missing currency: {cur}"
        
        print(f"PASS: All 23 new currencies present. Total: {len(codes)}")
    
    def test_fx_rates_includes_kwd_above_1(self):
        """KWD (Kuwaiti Dinar) should have rate > 1 GBP (approx 2.58)"""
        resp = self.session.get(f"{BASE_URL}/api/currency-fx/rates")
        assert resp.status_code == 200
        rates = resp.json()
        
        kwd_rate = next((r for r in rates if r["code"] == "KWD"), None)
        assert kwd_rate is not None, "KWD not found in rates"
        assert kwd_rate["rate_to_base"] > 1, f"KWD rate should be > 1, got {kwd_rate['rate_to_base']}"
        print(f"PASS: KWD rate = {kwd_rate['rate_to_base']} (> 1 GBP)")
    
    def test_fx_settings_available_codes_41_plus(self):
        """GET /api/currency-fx/settings should return 41+ available_codes"""
        resp = self.session.get(f"{BASE_URL}/api/currency-fx/settings")
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        
        codes = data.get("available_codes", [])
        assert len(codes) >= 41, f"Expected 41+ available_codes, got {len(codes)}"
        print(f"PASS: Settings returns {len(codes)} available currencies")
    
    # ==================== CITY LEDGER INVOICE WITH LINES TESTS ====================
    
    def test_create_invoice_with_multicurrency_lines(self):
        """POST /api/city-ledger/invoices with multi-currency lines computes total correctly"""
        # First, create a test company
        company_resp = self.session.post(f"{BASE_URL}/api/city-ledger/companies", json={
            "name": "TEST_MultiCurrency Corp",
            "contact_name": "Test Contact",
            "email": "test@multicurrency.com",
            "payment_terms_days": 30
        })
        assert company_resp.status_code == 200, f"Company creation failed: {company_resp.text}"
        company_id = company_resp.json()["id"]
        
        try:
            # Create invoice with multi-currency lines
            # EUR 150×3 @ 0.86 = £387, USD 100×2 @ 0.79 = £158, GBP 50×1 = £50 → total £595
            invoice_resp = self.session.post(f"{BASE_URL}/api/city-ledger/invoices", json={
                "company_id": company_id,
                "amount": 0,  # Should be ignored when lines provided
                "currency": "GBP",
                "notes": "Multi-currency test invoice",
                "lines": [
                    {"description": "EUR Service", "amount": 150, "currency": "EUR", "quantity": 3},
                    {"description": "USD Service", "amount": 100, "currency": "USD", "quantity": 2},
                    {"description": "GBP Service", "amount": 50, "currency": "GBP", "quantity": 1}
                ]
            })
            assert invoice_resp.status_code == 200, f"Invoice creation failed: {invoice_resp.text}"
            invoice = invoice_resp.json()
            
            # Verify invoice has lines
            assert "lines" in invoice, "Invoice should have lines array"
            assert len(invoice["lines"]) == 3, f"Expected 3 lines, got {len(invoice['lines'])}"
            
            # Verify each line has line_total_native and line_total_invoice_cur
            for line in invoice["lines"]:
                assert "line_total_native" in line, f"Line missing line_total_native: {line}"
                assert "line_total_invoice_cur" in line, f"Line missing line_total_invoice_cur: {line}"
            
            # Verify line totals
            eur_line = next(l for l in invoice["lines"] if l["currency"] == "EUR")
            assert eur_line["line_total_native"] == 450, f"EUR native total should be 450, got {eur_line['line_total_native']}"
            
            usd_line = next(l for l in invoice["lines"] if l["currency"] == "USD")
            assert usd_line["line_total_native"] == 200, f"USD native total should be 200, got {usd_line['line_total_native']}"
            
            gbp_line = next(l for l in invoice["lines"] if l["currency"] == "GBP")
            assert gbp_line["line_total_native"] == 50, f"GBP native total should be 50, got {gbp_line['line_total_native']}"
            assert gbp_line["line_total_invoice_cur"] == 50, f"GBP invoice_cur should be 50, got {gbp_line['line_total_invoice_cur']}"
            
            # Verify total amount is computed from lines (approximately £595)
            # EUR: 450 * 0.86 = 387, USD: 200 * 0.79 = 158, GBP: 50 = 50 → 595
            total = invoice["amount"]
            assert 590 <= total <= 600, f"Expected total ~£595, got {total}"
            
            print(f"PASS: Invoice created with total £{total}")
            print(f"  EUR line: native={eur_line['line_total_native']}, invoice_cur={eur_line['line_total_invoice_cur']}")
            print(f"  USD line: native={usd_line['line_total_native']}, invoice_cur={usd_line['line_total_invoice_cur']}")
            print(f"  GBP line: native={gbp_line['line_total_native']}, invoice_cur={gbp_line['line_total_invoice_cur']}")
            
            # Cleanup: delete invoice
            self.session.delete(f"{BASE_URL}/api/city-ledger/invoices/{invoice['id']}")
            
        finally:
            # Cleanup: delete company
            self.session.delete(f"{BASE_URL}/api/city-ledger/companies/{company_id}")
    
    def test_invoice_amount_ignored_when_lines_provided(self):
        """When lines are provided, the posted amount should be ignored"""
        # Create test company
        company_resp = self.session.post(f"{BASE_URL}/api/city-ledger/companies", json={
            "name": "TEST_AmountIgnore Corp",
            "payment_terms_days": 30
        })
        company_id = company_resp.json()["id"]
        
        try:
            # Create invoice with amount=9999 but lines that sum to ~£86
            invoice_resp = self.session.post(f"{BASE_URL}/api/city-ledger/invoices", json={
                "company_id": company_id,
                "amount": 9999,  # Should be ignored
                "currency": "GBP",
                "lines": [
                    {"description": "Test", "amount": 100, "currency": "EUR", "quantity": 1}
                ]
            })
            assert invoice_resp.status_code == 200
            invoice = invoice_resp.json()
            
            # Amount should be ~86 (100 EUR * 0.86), not 9999
            assert invoice["amount"] < 100, f"Amount should be ~86, not {invoice['amount']}"
            print(f"PASS: Posted amount 9999 was ignored, computed amount = {invoice['amount']}")
            
            # Cleanup
            self.session.delete(f"{BASE_URL}/api/city-ledger/invoices/{invoice['id']}")
        finally:
            self.session.delete(f"{BASE_URL}/api/city-ledger/companies/{company_id}")
    
    def test_invoice_with_kwd_high_rate_conversion(self):
        """Test conversion with KWD (rate > 1 GBP) works correctly"""
        # Create test company
        company_resp = self.session.post(f"{BASE_URL}/api/city-ledger/companies", json={
            "name": "TEST_KWD Corp",
            "payment_terms_days": 30
        })
        company_id = company_resp.json()["id"]
        
        try:
            # Create invoice with KWD line: 100 KWD @ 2.58 = £258
            invoice_resp = self.session.post(f"{BASE_URL}/api/city-ledger/invoices", json={
                "company_id": company_id,
                "amount": 0,
                "currency": "GBP",
                "lines": [
                    {"description": "KWD Service", "amount": 100, "currency": "KWD", "quantity": 1}
                ]
            })
            assert invoice_resp.status_code == 200
            invoice = invoice_resp.json()
            
            kwd_line = invoice["lines"][0]
            assert kwd_line["line_total_native"] == 100, f"KWD native should be 100"
            # KWD rate is 2.58, so 100 KWD = £258
            assert kwd_line["line_total_invoice_cur"] > 200, f"KWD converted should be > 200, got {kwd_line['line_total_invoice_cur']}"
            
            print(f"PASS: KWD conversion correct - 100 KWD = £{kwd_line['line_total_invoice_cur']}")
            
            # Cleanup
            self.session.delete(f"{BASE_URL}/api/city-ledger/invoices/{invoice['id']}")
        finally:
            self.session.delete(f"{BASE_URL}/api/city-ledger/companies/{company_id}")
    
    # ==================== INVOICE PDF TESTS ====================
    
    def test_invoice_pdf_with_lines_returns_valid_pdf(self):
        """GET /api/city-ledger/invoices/{id}/pdf returns valid PDF with line items"""
        # Create test company
        company_resp = self.session.post(f"{BASE_URL}/api/city-ledger/companies", json={
            "name": "TEST_PDF Corp",
            "payment_terms_days": 30
        })
        company_id = company_resp.json()["id"]
        
        try:
            # Create invoice with lines
            invoice_resp = self.session.post(f"{BASE_URL}/api/city-ledger/invoices", json={
                "company_id": company_id,
                "amount": 0,
                "currency": "GBP",
                "lines": [
                    {"description": "PDF Test Line 1", "amount": 100, "currency": "EUR", "quantity": 2},
                    {"description": "PDF Test Line 2", "amount": 50, "currency": "USD", "quantity": 1}
                ]
            })
            assert invoice_resp.status_code == 200
            invoice = invoice_resp.json()
            
            # Get PDF
            pdf_resp = self.session.get(f"{BASE_URL}/api/city-ledger/invoices/{invoice['id']}/pdf")
            assert pdf_resp.status_code == 200, f"PDF request failed: {pdf_resp.text}"
            
            # Verify PDF magic bytes
            pdf_bytes = pdf_resp.content
            assert pdf_bytes[:4] == b'%PDF', f"Response does not start with %PDF magic bytes"
            assert len(pdf_bytes) > 1000, f"PDF seems too small: {len(pdf_bytes)} bytes"
            
            # Verify content type
            assert 'application/pdf' in pdf_resp.headers.get('Content-Type', ''), "Content-Type should be application/pdf"
            
            print(f"PASS: PDF generated successfully, {len(pdf_bytes)} bytes, starts with %PDF")
            
            # Cleanup
            self.session.delete(f"{BASE_URL}/api/city-ledger/invoices/{invoice['id']}")
        finally:
            self.session.delete(f"{BASE_URL}/api/city-ledger/companies/{company_id}")
    
    def test_invoice_without_lines_still_works(self):
        """Invoice without lines should still work (backward compatibility)"""
        # Create test company
        company_resp = self.session.post(f"{BASE_URL}/api/city-ledger/companies", json={
            "name": "TEST_NoLines Corp",
            "payment_terms_days": 30
        })
        company_id = company_resp.json()["id"]
        
        try:
            # Create invoice without lines
            invoice_resp = self.session.post(f"{BASE_URL}/api/city-ledger/invoices", json={
                "company_id": company_id,
                "amount": 500,
                "currency": "GBP",
                "notes": "No lines test"
            })
            assert invoice_resp.status_code == 200
            invoice = invoice_resp.json()
            
            assert invoice["amount"] == 500, f"Amount should be 500, got {invoice['amount']}"
            assert invoice.get("lines", []) == [], "Lines should be empty"
            
            print(f"PASS: Invoice without lines created with amount £{invoice['amount']}")
            
            # Cleanup
            self.session.delete(f"{BASE_URL}/api/city-ledger/invoices/{invoice['id']}")
        finally:
            self.session.delete(f"{BASE_URL}/api/city-ledger/companies/{company_id}")
    
    # ==================== CONVERSION MATH TESTS ====================
    
    def test_convert_endpoint_with_new_currencies(self):
        """POST /api/currency-fx/convert works with new currencies"""
        # Test PLN to GBP
        resp = self.session.post(f"{BASE_URL}/api/currency-fx/convert", json={
            "amount": 100,
            "source": "PLN",
            "target": "GBP"
        })
        assert resp.status_code == 200
        data = resp.json()
        # PLN rate is 0.20, so 100 PLN = £20
        assert 18 <= data["converted"] <= 22, f"100 PLN should be ~£20, got {data['converted']}"
        print(f"PASS: 100 PLN = £{data['converted']}")
        
        # Test KWD to GBP (rate > 1)
        resp = self.session.post(f"{BASE_URL}/api/currency-fx/convert", json={
            "amount": 10,
            "source": "KWD",
            "target": "GBP"
        })
        assert resp.status_code == 200
        data = resp.json()
        # KWD rate is 2.58, so 10 KWD = £25.80
        assert 24 <= data["converted"] <= 27, f"10 KWD should be ~£25.80, got {data['converted']}"
        print(f"PASS: 10 KWD = £{data['converted']}")
    
    def test_convert_cross_currency_via_base(self):
        """Cross-currency conversion (e.g., EUR to USD) via base works"""
        resp = self.session.post(f"{BASE_URL}/api/currency-fx/convert", json={
            "amount": 100,
            "source": "EUR",
            "target": "USD"
        })
        assert resp.status_code == 200
        data = resp.json()
        # EUR rate 0.86, USD rate 0.79 → 100 EUR = 86 GBP = 86/0.79 = ~108.86 USD
        assert 105 <= data["converted"] <= 115, f"100 EUR should be ~109 USD, got {data['converted']}"
        print(f"PASS: 100 EUR = ${data['converted']} USD")


class TestIteration152Regression:
    """Regression tests from iteration 151"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: login and get auth token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert login_resp.status_code == 200
        token = login_resp.json().get("token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        yield
        self.session.close()
    
    def test_fx_settings_endpoint(self):
        """GET /api/currency-fx/settings returns expected structure"""
        resp = self.session.get(f"{BASE_URL}/api/currency-fx/settings")
        assert resp.status_code == 200
        data = resp.json()
        assert "base_currency" in data
        assert "available_codes" in data
        assert "symbols" in data
        print(f"PASS: Settings endpoint returns base_currency={data['base_currency']}, {len(data['available_codes'])} codes")
    
    def test_fx_rates_endpoint(self):
        """GET /api/currency-fx/rates returns list of rates"""
        resp = self.session.get(f"{BASE_URL}/api/currency-fx/rates")
        assert resp.status_code == 200
        rates = resp.json()
        assert isinstance(rates, list)
        assert len(rates) > 0
        # Each rate should have code and rate_to_base
        for r in rates[:5]:
            assert "code" in r
            assert "rate_to_base" in r
        print(f"PASS: Rates endpoint returns {len(rates)} currencies")
    
    def test_city_ledger_companies_crud(self):
        """City ledger companies CRUD still works"""
        # Create
        resp = self.session.post(f"{BASE_URL}/api/city-ledger/companies", json={
            "name": "TEST_Regression Corp",
            "payment_terms_days": 30
        })
        assert resp.status_code == 200
        company = resp.json()
        company_id = company["id"]
        
        # Read
        resp = self.session.get(f"{BASE_URL}/api/city-ledger/companies")
        assert resp.status_code == 200
        companies = resp.json()
        assert any(c["id"] == company_id for c in companies)
        
        # Delete
        resp = self.session.delete(f"{BASE_URL}/api/city-ledger/companies/{company_id}")
        assert resp.status_code == 200
        print("PASS: City ledger companies CRUD works")
    
    def test_city_ledger_invoices_crud(self):
        """City ledger invoices CRUD still works"""
        # Create company first
        company_resp = self.session.post(f"{BASE_URL}/api/city-ledger/companies", json={
            "name": "TEST_InvoiceRegression Corp",
            "payment_terms_days": 30
        })
        company_id = company_resp.json()["id"]
        
        try:
            # Create invoice
            resp = self.session.post(f"{BASE_URL}/api/city-ledger/invoices", json={
                "company_id": company_id,
                "amount": 100,
                "currency": "GBP"
            })
            assert resp.status_code == 200
            invoice = resp.json()
            invoice_id = invoice["id"]
            
            # Read
            resp = self.session.get(f"{BASE_URL}/api/city-ledger/invoices")
            assert resp.status_code == 200
            
            # Delete
            resp = self.session.delete(f"{BASE_URL}/api/city-ledger/invoices/{invoice_id}")
            assert resp.status_code == 200
            print("PASS: City ledger invoices CRUD works")
        finally:
            self.session.delete(f"{BASE_URL}/api/city-ledger/companies/{company_id}")
    
    def test_ar_aging_endpoint(self):
        """GET /api/currency-fx/ar-aging returns aging buckets"""
        resp = self.session.get(f"{BASE_URL}/api/currency-fx/ar-aging")
        assert resp.status_code == 200
        data = resp.json()
        assert "buckets" in data
        assert "total" in data
        assert "by_currency" in data
        print(f"PASS: AR aging returns total={data['total']}, buckets={data['buckets']}")
    
    def test_portfolio_summary_endpoint(self):
        """GET /api/currency-fx/portfolio-summary returns property data"""
        resp = self.session.get(f"{BASE_URL}/api/currency-fx/portfolio-summary")
        assert resp.status_code == 200
        data = resp.json()
        assert "base_currency" in data
        assert "properties" in data
        assert "totals" in data
        print(f"PASS: Portfolio summary returns {len(data['properties'])} properties")
