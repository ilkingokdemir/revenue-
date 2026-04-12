"""
Iteration 53 - Bank Reconciliation & Messaging Delivery Status Tests
Tests for:
1. Bank Reconciliation endpoints (bank accounts, transactions, auto-match, manual-match, summary)
2. Messaging delivery_status field (sandbox/delivered/failed/internal)
3. Existing accounting features regression
"""
import pytest
import requests
import os
import uuid
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestAuth:
    """Authentication tests"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get auth token for admin user"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        # Token is returned as 'token' in body
        assert "token" in data, f"Expected 'token' in response: {data}"
        return data["token"]
    
    @pytest.fixture(scope="class")
    def auth_headers(self, auth_token):
        """Get auth headers"""
        return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


class TestBankAccounts(TestAuth):
    """Bank Accounts CRUD tests"""
    
    def test_get_bank_accounts_auto_creates_default(self, auth_headers):
        """GET /api/accounting/bank-accounts/{property_id} - auto-creates default account"""
        response = requests.get(f"{BASE_URL}/api/accounting/bank-accounts/aldgate-flats", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        # Check default account structure
        account = data[0]
        assert "id" in account
        assert "property_id" in account
        assert "name" in account
        assert "bank_name" in account
        assert "currency" in account
        print(f"✓ Bank accounts returned: {len(data)} accounts")
    
    def test_create_bank_account(self, auth_headers):
        """POST /api/accounting/bank-accounts - create new bank account"""
        payload = {
            "property_id": "aldgate-flats",
            "name": f"TEST_Account_{uuid.uuid4().hex[:6]}",
            "bank_name": "HSBC",
            "account_number": "****5678",
            "sort_code": "40-00-00",
            "currency": "GBP",
            "opening_balance": 5000
        }
        response = requests.post(f"{BASE_URL}/api/accounting/bank-accounts", json=payload, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == payload["name"]
        assert data["bank_name"] == "HSBC"
        assert data["opening_balance"] == 5000
        assert data["current_balance"] == 5000
        print(f"✓ Created bank account: {data['id']}")
        return data["id"]
    
    def test_bank_accounts_require_auth(self):
        """Bank accounts endpoints require authentication"""
        response = requests.get(f"{BASE_URL}/api/accounting/bank-accounts/aldgate-flats")
        assert response.status_code == 401
        print("✓ Bank accounts require auth")


class TestBankTransactions(TestAuth):
    """Bank Transactions import and CRUD tests"""
    
    @pytest.fixture(scope="class")
    def account_id(self, auth_headers):
        """Get or create a bank account for testing"""
        response = requests.get(f"{BASE_URL}/api/accounting/bank-accounts/aldgate-flats", headers=auth_headers)
        data = response.json()
        return data[0]["id"] if data else ""
    
    def test_import_bank_transactions(self, auth_headers, account_id):
        """POST /api/accounting/bank-transactions/import - import bank statement transactions"""
        transactions = [
            {"date": "2026-01-15", "description": "TEST_Room Payment", "amount": 450, "reference": f"REF{uuid.uuid4().hex[:6]}"},
            {"date": "2026-01-16", "description": "TEST_Supplier Payment", "amount": -120, "reference": f"REF{uuid.uuid4().hex[:6]}"},
            {"date": "2026-01-17", "description": "TEST_Booking Deposit", "amount": 200, "reference": f"REF{uuid.uuid4().hex[:6]}"},
        ]
        payload = {
            "property_id": "aldgate-flats",
            "account_id": account_id,
            "transactions": transactions
        }
        response = requests.post(f"{BASE_URL}/api/accounting/bank-transactions/import", json=payload, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "imported" in data
        assert "duplicates" in data
        assert "total" in data
        assert data["total"] == 3
        print(f"✓ Imported {data['imported']} transactions ({data['duplicates']} duplicates)")
    
    def test_import_deduplication(self, auth_headers, account_id):
        """Import same transactions again - should detect duplicates"""
        transactions = [
            {"date": "2026-01-15", "description": "TEST_Room Payment", "amount": 450, "reference": "DEDUP_TEST_001"},
        ]
        payload = {
            "property_id": "aldgate-flats",
            "account_id": account_id,
            "transactions": transactions
        }
        # First import
        response1 = requests.post(f"{BASE_URL}/api/accounting/bank-transactions/import", json=payload, headers=auth_headers)
        assert response1.status_code == 200
        data1 = response1.json()
        
        # Second import - should be duplicate
        response2 = requests.post(f"{BASE_URL}/api/accounting/bank-transactions/import", json=payload, headers=auth_headers)
        assert response2.status_code == 200
        data2 = response2.json()
        assert data2["duplicates"] >= 1
        print(f"✓ Deduplication working: {data2['duplicates']} duplicates detected")
    
    def test_add_manual_transaction(self, auth_headers, account_id):
        """POST /api/accounting/bank-transactions/manual - add single transaction"""
        payload = {
            "property_id": "aldgate-flats",
            "account_id": account_id,
            "date": "2026-01-20",
            "description": f"TEST_Manual Transaction {uuid.uuid4().hex[:6]}",
            "reference": "MANUAL001",
            "amount": 350
        }
        response = requests.post(f"{BASE_URL}/api/accounting/bank-transactions/manual", json=payload, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["amount"] == 350
        assert data["type"] == "credit"  # positive amount = credit
        assert data["matched"] == False
        print(f"✓ Added manual transaction: {data['id']}")
        return data["id"]
    
    def test_list_bank_transactions(self, auth_headers):
        """GET /api/accounting/bank-transactions/{property_id} - list with filters"""
        response = requests.get(f"{BASE_URL}/api/accounting/bank-transactions/aldgate-flats", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Listed {len(data)} bank transactions")
    
    def test_list_transactions_with_month_filter(self, auth_headers):
        """GET /api/accounting/bank-transactions/{property_id}?month=2026-01"""
        response = requests.get(f"{BASE_URL}/api/accounting/bank-transactions/aldgate-flats?month=2026-01", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # All transactions should be from 2026-01
        for tx in data:
            if tx.get("date"):
                assert tx["date"].startswith("2026-01")
        print(f"✓ Month filter working: {len(data)} transactions for 2026-01")
    
    def test_list_transactions_matched_filter(self, auth_headers):
        """GET /api/accounting/bank-transactions/{property_id}?matched=false"""
        response = requests.get(f"{BASE_URL}/api/accounting/bank-transactions/aldgate-flats?matched=false", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        for tx in data:
            assert tx["matched"] == False
        print(f"✓ Matched filter working: {len(data)} unmatched transactions")
    
    def test_delete_transaction(self, auth_headers, account_id):
        """DELETE /api/accounting/bank-transactions/{tx_id}"""
        # First create a transaction to delete
        payload = {
            "property_id": "aldgate-flats",
            "account_id": account_id,
            "date": "2026-01-25",
            "description": "TEST_To Delete",
            "amount": 100
        }
        create_resp = requests.post(f"{BASE_URL}/api/accounting/bank-transactions/manual", json=payload, headers=auth_headers)
        tx_id = create_resp.json()["id"]
        
        # Delete it
        response = requests.delete(f"{BASE_URL}/api/accounting/bank-transactions/{tx_id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "deleted"
        print(f"✓ Deleted transaction: {tx_id}")


class TestBankReconciliation(TestAuth):
    """Bank Reconciliation auto-match, manual-match, unmatch tests"""
    
    def test_auto_match_transactions(self, auth_headers):
        """POST /api/accounting/bank-reconciliation/auto-match/{property_id}"""
        response = requests.post(f"{BASE_URL}/api/accounting/bank-reconciliation/auto-match/aldgate-flats", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "matched" in data
        assert "remaining_unmatched" in data
        print(f"✓ Auto-match: {data['matched']} matched, {data['remaining_unmatched']} remaining")
    
    def test_manual_match_transaction(self, auth_headers):
        """POST /api/accounting/bank-reconciliation/manual-match"""
        # First get an unmatched transaction
        tx_resp = requests.get(f"{BASE_URL}/api/accounting/bank-transactions/aldgate-flats?matched=false", headers=auth_headers)
        transactions = tx_resp.json()
        
        if transactions:
            tx_id = transactions[0]["id"]
            payload = {
                "transaction_id": tx_id,
                "matched_to": "manual-match-test-id",
                "match_type": "manual"
            }
            response = requests.post(f"{BASE_URL}/api/accounting/bank-reconciliation/manual-match", json=payload, headers=auth_headers)
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "matched"
            print(f"✓ Manual match successful for transaction: {tx_id}")
            return tx_id
        else:
            print("✓ No unmatched transactions to test manual match (skipped)")
            return None
    
    def test_unmatch_transaction(self, auth_headers):
        """POST /api/accounting/bank-reconciliation/unmatch/{tx_id}"""
        # First get a matched transaction
        tx_resp = requests.get(f"{BASE_URL}/api/accounting/bank-transactions/aldgate-flats?matched=true", headers=auth_headers)
        transactions = tx_resp.json()
        
        if transactions:
            tx_id = transactions[0]["id"]
            response = requests.post(f"{BASE_URL}/api/accounting/bank-reconciliation/unmatch/{tx_id}", headers=auth_headers)
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "unmatched"
            print(f"✓ Unmatch successful for transaction: {tx_id}")
        else:
            print("✓ No matched transactions to test unmatch (skipped)")
    
    def test_reconciliation_summary(self, auth_headers):
        """GET /api/accounting/bank-reconciliation/summary/{property_id}"""
        response = requests.get(f"{BASE_URL}/api/accounting/bank-reconciliation/summary/aldgate-flats", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        # Check all required fields
        assert "month" in data
        assert "total_transactions" in data
        assert "matched" in data
        assert "unmatched" in data
        assert "match_rate" in data
        assert "bank_credits" in data
        assert "bank_debits" in data
        assert "bank_net" in data
        assert "system_income" in data
        assert "system_expenses" in data
        assert "system_net" in data
        assert "discrepancy" in data
        assert "reconciled" in data
        
        print(f"✓ Reconciliation summary: {data['match_rate']}% match rate, £{data['discrepancy']} discrepancy")
    
    def test_reconciliation_summary_with_month(self, auth_headers):
        """GET /api/accounting/bank-reconciliation/summary/{property_id}?month=2026-01"""
        response = requests.get(f"{BASE_URL}/api/accounting/bank-reconciliation/summary/aldgate-flats?month=2026-01", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["month"] == "2026-01"
        print(f"✓ Summary for 2026-01: {data['total_transactions']} transactions")


class TestMessagingDeliveryStatus(TestAuth):
    """Messaging delivery_status field tests"""
    
    @pytest.fixture(scope="class")
    def conversation_id(self, auth_headers):
        """Create a test conversation"""
        payload = {
            "property_id": "aldgate-flats",
            "guest_name": f"TEST_Guest_{uuid.uuid4().hex[:6]}",
            "guest_email": "test@example.com",
            "guest_phone": "+447700123456",
            "channel": "whatsapp",
            "status": "new",
            "priority": "medium"
        }
        response = requests.post(f"{BASE_URL}/api/messaging/conversations", json=payload, headers=auth_headers)
        if response.status_code == 200:
            return response.json()["id"]
        return None
    
    def test_send_message_returns_delivery_status(self, auth_headers, conversation_id):
        """POST /api/messaging/messages - returns delivery_status field"""
        if not conversation_id:
            pytest.skip("No conversation created")
        
        payload = {
            "conversation_id": conversation_id,
            "content": f"TEST_Message {uuid.uuid4().hex[:6]}"
        }
        response = requests.post(f"{BASE_URL}/api/messaging/messages", json=payload, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        # Check delivery_status field exists
        assert "delivery_status" in data
        # Should be sandbox/internal since no real credentials configured
        assert data["delivery_status"] in ["sandbox", "internal", "delivered", "failed"]
        print(f"✓ Message sent with delivery_status: {data['delivery_status']}")
    
    def test_send_message_internal_channel(self, auth_headers):
        """Send message on internal channel - should return 'internal' status"""
        # Create internal conversation
        conv_payload = {
            "property_id": "aldgate-flats",
            "guest_name": f"TEST_Internal_{uuid.uuid4().hex[:6]}",
            "channel": "internal",
            "status": "new"
        }
        conv_resp = requests.post(f"{BASE_URL}/api/messaging/conversations", json=conv_payload, headers=auth_headers)
        if conv_resp.status_code != 200:
            pytest.skip("Could not create conversation")
        
        conv_id = conv_resp.json()["id"]
        
        msg_payload = {
            "conversation_id": conv_id,
            "content": "TEST_Internal message"
        }
        response = requests.post(f"{BASE_URL}/api/messaging/messages", json=msg_payload, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["delivery_status"] == "internal"
        print(f"✓ Internal channel message has delivery_status: internal")
    
    def test_send_whatsapp_message_sandbox(self, auth_headers):
        """Send WhatsApp message without credentials - should return 'sandbox' or 'failed'"""
        # Create WhatsApp conversation
        conv_payload = {
            "property_id": "aldgate-flats",
            "guest_name": f"TEST_WhatsApp_{uuid.uuid4().hex[:6]}",
            "guest_phone": "+447700999888",
            "channel": "whatsapp",
            "status": "new"
        }
        conv_resp = requests.post(f"{BASE_URL}/api/messaging/conversations", json=conv_payload, headers=auth_headers)
        if conv_resp.status_code != 200:
            pytest.skip("Could not create conversation")
        
        conv_id = conv_resp.json()["id"]
        
        msg_payload = {
            "conversation_id": conv_id,
            "content": "TEST_WhatsApp message"
        }
        response = requests.post(f"{BASE_URL}/api/messaging/messages", json=msg_payload, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        # Without credentials, should be sandbox, internal, or failed (if API call attempted)
        assert data["delivery_status"] in ["sandbox", "internal", "failed"]
        print(f"✓ WhatsApp message without credentials: {data['delivery_status']}")


class TestExistingAccountingRegression(TestAuth):
    """Regression tests for existing accounting features"""
    
    def test_pnl_still_works(self, auth_headers):
        """GET /api/accounting/pnl/{property_id}"""
        response = requests.get(f"{BASE_URL}/api/accounting/pnl/aldgate-flats?period=2026-01", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "total_income" in data
        assert "total_expenses" in data
        assert "net_profit" in data
        print(f"✓ P&L working: Net profit £{data['net_profit']}")
    
    def test_income_still_works(self, auth_headers):
        """GET /api/accounting/income/{property_id}"""
        response = requests.get(f"{BASE_URL}/api/accounting/income/aldgate-flats", headers=auth_headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)
        print("✓ Income endpoint working")
    
    def test_expenses_still_works(self, auth_headers):
        """GET /api/accounting/expenses/{property_id}"""
        response = requests.get(f"{BASE_URL}/api/accounting/expenses/aldgate-flats", headers=auth_headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)
        print("✓ Expenses endpoint working")
    
    def test_invoices_still_works(self, auth_headers):
        """GET /api/accounting/invoices/{property_id}"""
        response = requests.get(f"{BASE_URL}/api/accounting/invoices/aldgate-flats", headers=auth_headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)
        print("✓ Invoices endpoint working")
    
    def test_payments_still_works(self, auth_headers):
        """GET /api/accounting/payments/{property_id}"""
        response = requests.get(f"{BASE_URL}/api/accounting/payments/aldgate-flats", headers=auth_headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)
        print("✓ Payments endpoint working")
    
    def test_journal_entries_still_works(self, auth_headers):
        """GET /api/accounting/journal-entries/{property_id}"""
        response = requests.get(f"{BASE_URL}/api/accounting/journal-entries/aldgate-flats", headers=auth_headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)
        print("✓ Journal entries endpoint working")
    
    def test_balance_sheet_still_works(self, auth_headers):
        """GET /api/accounting/balance-sheet/{property_id}"""
        response = requests.get(f"{BASE_URL}/api/accounting/balance-sheet/aldgate-flats", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "assets" in data
        assert "liabilities" in data
        assert "equity" in data
        print("✓ Balance sheet endpoint working")
    
    def test_forecast_still_works(self, auth_headers):
        """GET /api/accounting/forecast/{property_id}"""
        response = requests.get(f"{BASE_URL}/api/accounting/forecast/aldgate-flats", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "forecasts" in data
        print("✓ Forecast endpoint working")


class TestExistingMessagingRegression(TestAuth):
    """Regression tests for existing messaging features"""
    
    def test_conversations_list(self, auth_headers):
        """GET /api/messaging/conversations/{property_id}"""
        response = requests.get(f"{BASE_URL}/api/messaging/conversations/aldgate-flats", headers=auth_headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)
        print("✓ Conversations list working")
    
    def test_conversation_stats(self, auth_headers):
        """GET /api/messaging/conversations/{property_id}/stats"""
        response = requests.get(f"{BASE_URL}/api/messaging/conversations/aldgate-flats/stats", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        print(f"✓ Conversation stats: {data['total']} total")
    
    def test_quick_replies(self, auth_headers):
        """GET /api/messaging/quick-replies"""
        response = requests.get(f"{BASE_URL}/api/messaging/quick-replies", headers=auth_headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)
        print("✓ Quick replies working")
    
    def test_channel_settings(self, auth_headers):
        """GET /api/messaging/channel-settings/{property_id}"""
        response = requests.get(f"{BASE_URL}/api/messaging/channel-settings/aldgate-flats", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "property_id" in data
        print("✓ Channel settings working")


class TestAuthEndpoints:
    """Auth endpoint tests"""
    
    def test_login_success(self):
        """POST /api/auth/login - successful login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert "email" in data
        print("✓ Login successful")
    
    def test_login_invalid_credentials(self):
        """POST /api/auth/login - invalid credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "wrong@example.com",
            "password": "wrongpassword"
        })
        assert response.status_code in [401, 400]
        print("✓ Invalid credentials rejected")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
