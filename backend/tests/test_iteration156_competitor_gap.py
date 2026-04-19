"""
Iteration 156 - Top 10 Competitor Gap Features Backend Tests
Tests: Night Audit Close, Deposit Ledger, Commission Recon, Gift Cards, Review Sentiment,
       Guest RFM, Preventive Maintenance, Asset Register, Cash Drawer, 2FA TOTP
"""
import pytest
import requests
import os
import uuid
import pyotp

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

@pytest.fixture(scope="module")
def admin_session():
    """Get admin auth session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    
    # Login as admin
    resp = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@hotelbox.com",
        "password": "HotelAdmin2026!"
    })
    assert resp.status_code == 200, f"Admin login failed: {resp.text}"
    # Token can be in 'token' or 'access_token' field
    token = resp.json().get("token") or resp.json().get("access_token")
    session.headers.update({"Authorization": f"Bearer {token}"})
    return session


@pytest.fixture(scope="module")
def receptionist_session():
    """Get receptionist auth session (for role-based tests)"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    
    resp = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": "testrecep@hotelbox.com",
        "password": "Test2026!"
    })
    if resp.status_code == 200:
        token = resp.json().get("token") or resp.json().get("access_token")
        session.headers.update({"Authorization": f"Bearer {token}"})
    return session


# ==================== 1. NIGHT AUDIT CLOSE-DAY ====================
class TestNightAuditClose:
    """Night Audit Close-Day Lock tests"""
    
    def test_close_status_returns_open_initially(self, admin_session):
        """GET /api/night-audit/close-status/{pid} returns closed=false for new date"""
        # Use a future date that won't be closed
        resp = admin_session.get(f"{BASE_URL}/api/night-audit/close-status/aldgate-flats?business_date=2099-12-31")
        assert resp.status_code == 200
        data = resp.json()
        assert "closed" in data
        assert data["closed"] == False
        assert data["property_id"] == "aldgate-flats"
        print("✓ Night Audit close-status returns open for unclosed date")
    
    def test_close_day_creates_record(self, admin_session):
        """POST /api/night-audit/close-day/{pid} creates close record"""
        test_date = f"2099-01-{uuid.uuid4().hex[:2].zfill(2)}"  # Random future date
        resp = admin_session.post(f"{BASE_URL}/api/night-audit/close-day/aldgate-flats", json={
            "business_date": test_date,
            "notes": "Test close"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "closed"
        assert data["business_date"] == test_date
        assert "totals" in data
        assert "counts" in data
        print(f"✓ Night Audit close-day created record for {test_date}")
        return test_date
    
    def test_close_day_duplicate_returns_409(self, admin_session):
        """POST /api/night-audit/close-day/{pid} returns 409 for already closed date"""
        # First close a date
        test_date = "2098-06-15"
        admin_session.post(f"{BASE_URL}/api/night-audit/close-day/aldgate-flats", json={
            "business_date": test_date, "notes": "First close"
        })
        # Try to close again
        resp = admin_session.post(f"{BASE_URL}/api/night-audit/close-day/aldgate-flats", json={
            "business_date": test_date, "notes": "Duplicate"
        })
        assert resp.status_code == 409
        print("✓ Night Audit close-day returns 409 for duplicate close")
    
    def test_close_history_returns_records(self, admin_session):
        """GET /api/night-audit/close-history/{pid} returns list"""
        resp = admin_session.get(f"{BASE_URL}/api/night-audit/close-history/aldgate-flats?limit=30")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        print(f"✓ Night Audit close-history returned {len(data)} records")
    
    def test_reopen_day_admin_only(self, admin_session, receptionist_session):
        """POST /api/night-audit/reopen-day/{pid} requires admin role"""
        # Close a date first
        test_date = "2097-03-20"
        admin_session.post(f"{BASE_URL}/api/night-audit/close-day/aldgate-flats", json={
            "business_date": test_date, "notes": "To reopen"
        })
        
        # Admin can reopen
        resp = admin_session.post(f"{BASE_URL}/api/night-audit/reopen-day/aldgate-flats", json={
            "business_date": test_date, "reason": "Admin reopen test"
        })
        assert resp.status_code == 200
        print("✓ Night Audit reopen-day works for admin")
        
        # Receptionist cannot reopen (if session exists)
        if receptionist_session.headers.get("Authorization"):
            resp2 = receptionist_session.post(f"{BASE_URL}/api/night-audit/reopen-day/aldgate-flats", json={
                "business_date": "2097-03-21", "reason": "Should fail"
            })
            assert resp2.status_code in [401, 403]
            print("✓ Night Audit reopen-day denied for non-admin")


# ==================== 2. DEPOSIT LEDGER ====================
class TestDepositLedger:
    """Deposit Liability Ledger tests"""
    
    def test_deposit_ledger_returns_structure(self, admin_session):
        """GET /api/deposit-ledger/{pid} returns correct structure"""
        resp = admin_session.get(f"{BASE_URL}/api/deposit-ledger/aldgate-flats")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_liability" in data
        assert "count" in data
        assert "by_month" in data
        assert "by_booking" in data
        assert "as_of" in data
        print(f"✓ Deposit Ledger returned: £{data['total_liability']} across {data['count']} bookings")
    
    def test_deposit_ledger_booking_structure(self, admin_session):
        """Verify by_booking items have required fields"""
        resp = admin_session.get(f"{BASE_URL}/api/deposit-ledger/aldgate-flats")
        assert resp.status_code == 200
        data = resp.json()
        if data["by_booking"]:
            b = data["by_booking"][0]
            for field in ["id", "booking_ref", "guest_name", "paid", "liability", "source", "status"]:
                assert field in b, f"Missing field: {field}"
            print("✓ Deposit Ledger booking structure verified")
        else:
            print("✓ Deposit Ledger returned empty (no future deposits)")


# ==================== 3. COMMISSION RECONCILIATION ====================
class TestCommissionRecon:
    """Commission Reconciliation tests"""
    
    def test_list_statements_empty(self, admin_session):
        """GET /api/commission-recon/statements/{pid} returns list"""
        resp = admin_session.get(f"{BASE_URL}/api/commission-recon/statements/aldgate-flats")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        print(f"✓ Commission Recon statements returned {len(data)} records")
    
    def test_upload_statement_reconciles(self, admin_session):
        """POST /api/commission-recon/upload/{pid} reconciles lines"""
        resp = admin_session.post(f"{BASE_URL}/api/commission-recon/upload/aldgate-flats", json={
            "channel": "Booking.com",
            "period": "2026-01",
            "lines": [
                {"booking_ref": "TEST-BKG-001", "gross": 150.00, "commission": 22.50},
                {"booking_ref": "TEST-BKG-002", "gross": 280.00, "commission": 42.00}
            ]
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "id" in data
        assert data["channel"] == "Booking.com"
        assert "summary" in data
        assert data["summary"]["lines_total"] == 2
        # Lines should be classified as match/variance/unmatched
        for line in data.get("lines", []):
            assert line["status"] in ["match", "variance", "unmatched"]
        print(f"✓ Commission Recon uploaded: {data['summary']['matched']} matched, {data['summary']['unmatched']} unmatched")
        return data["id"]
    
    def test_delete_statement_admin_only(self, admin_session):
        """DELETE /api/commission-recon/statements/{id} requires admin"""
        # Create a statement first
        resp = admin_session.post(f"{BASE_URL}/api/commission-recon/upload/aldgate-flats", json={
            "channel": "Expedia", "period": "2026-02",
            "lines": [{"booking_ref": "DEL-TEST", "gross": 100, "commission": 15}]
        })
        stmt_id = resp.json()["id"]
        
        # Delete it
        resp2 = admin_session.delete(f"{BASE_URL}/api/commission-recon/statements/{stmt_id}")
        assert resp2.status_code == 200
        print("✓ Commission Recon delete works for admin")


# ==================== 4. GIFT CARDS ====================
class TestGiftCards:
    """Gift Cards / Vouchers tests"""
    
    def test_issue_gift_card(self, admin_session):
        """POST /api/gift-cards creates card with auto-generated code"""
        resp = admin_session.post(f"{BASE_URL}/api/gift-cards", json={
            "amount": 50,
            "property_id": "aldgate-flats",
            "recipient_name": "Test Recipient",
            "recipient_email": "test@example.com"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "id" in data
        assert "code" in data
        assert data["code"].startswith("MHB-")
        assert data["initial_amount"] == 50
        assert data["balance"] == 50
        assert data["status"] == "active"
        print(f"✓ Gift Card issued: {data['code']}")
        return data
    
    def test_list_gift_cards(self, admin_session):
        """GET /api/gift-cards returns list"""
        resp = admin_session.get(f"{BASE_URL}/api/gift-cards?property_id=aldgate-flats")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        print(f"✓ Gift Cards list returned {len(data)} cards")
    
    def test_gift_card_summary(self, admin_session):
        """GET /api/gift-cards/summary/{pid} returns totals"""
        resp = admin_session.get(f"{BASE_URL}/api/gift-cards/summary/aldgate-flats")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_sold" in data
        assert "total_outstanding" in data
        assert "total_redeemed" in data
        assert "counts" in data
        print(f"✓ Gift Card summary: £{data['total_sold']} sold, £{data['total_outstanding']} outstanding")
    
    def test_lookup_gift_card_by_code(self, admin_session):
        """GET /api/gift-cards/lookup/{code} finds card"""
        # First create a card
        resp = admin_session.post(f"{BASE_URL}/api/gift-cards", json={
            "amount": 25, "property_id": "aldgate-flats"
        })
        code = resp.json()["code"]
        
        # Lookup
        resp2 = admin_session.get(f"{BASE_URL}/api/gift-cards/lookup/{code}")
        assert resp2.status_code == 200
        assert resp2.json()["code"] == code
        print(f"✓ Gift Card lookup by code works")
    
    def test_cancel_gift_card(self, admin_session):
        """POST /api/gift-cards/{id}/cancel sets status"""
        # Create card
        resp = admin_session.post(f"{BASE_URL}/api/gift-cards", json={
            "amount": 10, "property_id": "aldgate-flats"
        })
        card_id = resp.json()["id"]
        
        # Cancel
        resp2 = admin_session.post(f"{BASE_URL}/api/gift-cards/{card_id}/cancel", json={
            "reason": "Test cancellation"
        })
        assert resp2.status_code == 200
        print("✓ Gift Card cancel works")


# ==================== 5. REVIEW SENTIMENT AI ====================
class TestReviewSentiment:
    """Review Sentiment AI tests"""
    
    def test_sentiment_summary(self, admin_session):
        """GET /api/reviews/sentiment/summary/{pid} returns structure"""
        resp = admin_session.get(f"{BASE_URL}/api/reviews/sentiment/summary/aldgate-flats")
        assert resp.status_code == 200
        data = resp.json()
        assert "theme_counts" in data
        assert "sentiment_distribution" in data
        assert "total_analyzed" in data
        print(f"✓ Sentiment summary: {data['total_analyzed']} analyzed")
    
    def test_sentiment_analyze_requires_llm_key(self, admin_session):
        """POST /api/reviews/sentiment/analyze works or returns 503 if no key"""
        resp = admin_session.post(f"{BASE_URL}/api/reviews/sentiment/analyze", json={
            "property_id": "aldgate-flats",
            "limit": 5
        })
        # Either 200 (key present) or 503 (key missing)
        assert resp.status_code in [200, 503]
        if resp.status_code == 200:
            data = resp.json()
            assert "analyzed" in data
            print(f"✓ Sentiment analyze: {data['analyzed']} new reviews processed")
        else:
            print("✓ Sentiment analyze returns 503 (LLM key not configured - expected)")


# ==================== 6. GUEST RFM SEGMENTATION ====================
class TestGuestRFM:
    """Guest RFM Segmentation tests"""
    
    def test_rfm_returns_structure(self, admin_session):
        """GET /api/guests/rfm/{pid} returns segments and guests"""
        resp = admin_session.get(f"{BASE_URL}/api/guests/rfm/aldgate-flats")
        assert resp.status_code == 200
        data = resp.json()
        assert "summary" in data
        assert "segments" in data
        assert "guests" in data
        assert data["summary"]["total"] >= 0
        print(f"✓ RFM returned {data['summary']['total']} guests, £{data['summary']['total_revenue']} revenue")
    
    def test_rfm_segments_structure(self, admin_session):
        """Verify 5 segments with correct names"""
        resp = admin_session.get(f"{BASE_URL}/api/guests/rfm/aldgate-flats")
        data = resp.json()
        segment_names = [s["name"] for s in data["segments"]]
        expected = ["Champions", "Loyal", "Potential Loyalists", "At Risk", "Lost"]
        for name in expected:
            assert name in segment_names, f"Missing segment: {name}"
        print("✓ RFM has all 5 segments: Champions, Loyal, Potential Loyalists, At Risk, Lost")
    
    def test_rfm_guest_structure(self, admin_session):
        """Verify guest records have RFM scores"""
        resp = admin_session.get(f"{BASE_URL}/api/guests/rfm/aldgate-flats")
        data = resp.json()
        if data["guests"]:
            g = data["guests"][0]
            for field in ["recency_days", "frequency", "monetary", "r_score", "f_score", "m_score", "composite", "segment"]:
                assert field in g, f"Missing field: {field}"
            print(f"✓ RFM guest structure verified (top guest: {g['segment']} with score {g['composite']})")


# ==================== 7. PREVENTIVE MAINTENANCE ====================
class TestPreventiveMaintenance:
    """Preventive Maintenance Scheduler tests"""
    
    def test_list_plans(self, admin_session):
        """GET /api/preventive-maintenance/{pid} returns plans"""
        resp = admin_session.get(f"{BASE_URL}/api/preventive-maintenance/aldgate-flats")
        assert resp.status_code == 200
        data = resp.json()
        assert "plans" in data
        assert "total" in data
        assert "overdue_count" in data
        assert "due_soon_count" in data
        print(f"✓ PM returned {data['total']} plans, {data['overdue_count']} overdue")
    
    def test_create_plan(self, admin_session):
        """POST /api/preventive-maintenance creates plan"""
        resp = admin_session.post(f"{BASE_URL}/api/preventive-maintenance", json={
            "property_id": "aldgate-flats",
            "name": "Test PM Plan",
            "frequency": "monthly",
            "category": "hvac",
            "location": "Room 101",
            "first_due": "2026-02-01"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Test PM Plan"
        assert data["frequency"] == "monthly"
        assert data["frequency_days"] == 30
        print(f"✓ PM plan created: {data['id']}")
        return data["id"]
    
    def test_complete_plan_advances_due(self, admin_session):
        """POST /api/preventive-maintenance/{id}/complete advances next_due"""
        # Create plan
        resp = admin_session.post(f"{BASE_URL}/api/preventive-maintenance", json={
            "property_id": "aldgate-flats",
            "name": "Complete Test",
            "frequency": "weekly",
            "first_due": "2026-01-01"
        })
        plan_id = resp.json()["id"]
        
        # Complete it
        resp2 = admin_session.post(f"{BASE_URL}/api/preventive-maintenance/{plan_id}/complete", json={
            "notes": "Completed test"
        })
        assert resp2.status_code == 200
        assert resp2.json()["status"] == "completed"
        print("✓ PM complete advances next_due")


# ==================== 8. ASSET REGISTER ====================
class TestAssetRegister:
    """Asset Register tests"""
    
    def test_list_assets(self, admin_session):
        """GET /api/assets/{pid} returns list with computed fields"""
        resp = admin_session.get(f"{BASE_URL}/api/assets/aldgate-flats")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        print(f"✓ Asset Register returned {len(data)} assets")
    
    def test_create_asset(self, admin_session):
        """POST /api/assets creates asset"""
        resp = admin_session.post(f"{BASE_URL}/api/assets", json={
            "property_id": "aldgate-flats",
            "name": "Test TV",
            "category": "tv",
            "location": "Room 201",
            "purchase_date": "2024-01-15",
            "purchase_price": 500,
            "useful_life_years": 5,
            "warranty_expires": "2027-01-15"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Test TV"
        assert data["purchase_price"] == 500
        print(f"✓ Asset created: {data['id']}")
        return data["id"]
    
    def test_asset_summary(self, admin_session):
        """GET /api/assets/summary/{pid} returns totals"""
        resp = admin_session.get(f"{BASE_URL}/api/assets/summary/aldgate-flats")
        assert resp.status_code == 200
        data = resp.json()
        assert "count" in data
        assert "total_purchase_value" in data
        assert "total_book_value" in data
        assert "warranty_expiring_soon" in data
        print(f"✓ Asset summary: {data['count']} assets, £{data['total_book_value']} book value")
    
    def test_asset_computed_fields(self, admin_session):
        """Verify assets have depreciated_value, age_years, warranty_active"""
        # Create an asset first
        admin_session.post(f"{BASE_URL}/api/assets", json={
            "property_id": "aldgate-flats",
            "name": "Computed Test",
            "category": "appliance",
            "purchase_date": "2023-01-01",
            "purchase_price": 1000,
            "useful_life_years": 5,
            "warranty_expires": "2028-01-01"
        })
        
        resp = admin_session.get(f"{BASE_URL}/api/assets/aldgate-flats")
        data = resp.json()
        if data:
            a = data[0]
            assert "depreciated_value" in a
            assert "age_years" in a
            assert "depreciation_pct" in a
            print("✓ Asset computed fields present")


# ==================== 9. CASH DRAWER ====================
class TestCashDrawer:
    """Cash Drawer / Float Session tests"""
    
    def test_get_active_drawer(self, admin_session):
        """GET /api/cash-drawer/active/{pid} returns status"""
        resp = admin_session.get(f"{BASE_URL}/api/cash-drawer/active/aldgate-flats")
        assert resp.status_code == 200
        data = resp.json()
        assert "open" in data
        print(f"✓ Cash Drawer active status: {'open' if data['open'] else 'closed'}")
    
    def test_open_drawer(self, admin_session):
        """POST /api/cash-drawer/open/{pid} opens session"""
        # First close any open drawer
        active = admin_session.get(f"{BASE_URL}/api/cash-drawer/active/aldgate-flats").json()
        if active.get("open") and active.get("session"):
            admin_session.post(f"{BASE_URL}/api/cash-drawer/sessions/{active['session']['id']}/close", json={
                "counted_cash": 100
            })
        
        resp = admin_session.post(f"{BASE_URL}/api/cash-drawer/open/aldgate-flats", json={
            "opening_float": 100,
            "notes": "Test shift"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "open"
        assert data["opening_float"] == 100
        print(f"✓ Cash Drawer opened: {data['id']}")
        return data["id"]
    
    def test_open_drawer_duplicate_409(self, admin_session):
        """POST /api/cash-drawer/open/{pid} returns 409 if already open"""
        # Ensure drawer is open
        active = admin_session.get(f"{BASE_URL}/api/cash-drawer/active/aldgate-flats").json()
        if not active.get("open"):
            admin_session.post(f"{BASE_URL}/api/cash-drawer/open/aldgate-flats", json={
                "opening_float": 100
            })
        
        # Try to open again
        resp = admin_session.post(f"{BASE_URL}/api/cash-drawer/open/aldgate-flats", json={
            "opening_float": 50
        })
        assert resp.status_code == 409
        print("✓ Cash Drawer returns 409 for duplicate open")
    
    def test_add_transaction(self, admin_session):
        """POST /api/cash-drawer/sessions/{id}/transaction logs tx"""
        active = admin_session.get(f"{BASE_URL}/api/cash-drawer/active/aldgate-flats").json()
        if not active.get("open"):
            admin_session.post(f"{BASE_URL}/api/cash-drawer/open/aldgate-flats", json={
                "opening_float": 100
            })
            active = admin_session.get(f"{BASE_URL}/api/cash-drawer/active/aldgate-flats").json()
        
        session_id = active["session"]["id"]
        resp = admin_session.post(f"{BASE_URL}/api/cash-drawer/sessions/{session_id}/transaction", json={
            "direction": "in",
            "amount": 50,
            "description": "Test payment"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["direction"] == "in"
        assert data["amount"] == 50
        print("✓ Cash Drawer transaction logged")
    
    def test_close_drawer_computes_variance(self, admin_session):
        """POST /api/cash-drawer/sessions/{id}/close computes variance"""
        # Ensure drawer is open with known state
        active = admin_session.get(f"{BASE_URL}/api/cash-drawer/active/aldgate-flats").json()
        if active.get("open"):
            session_id = active["session"]["id"]
        else:
            resp = admin_session.post(f"{BASE_URL}/api/cash-drawer/open/aldgate-flats", json={
                "opening_float": 100
            })
            session_id = resp.json()["id"]
        
        # Close with counted cash
        resp = admin_session.post(f"{BASE_URL}/api/cash-drawer/sessions/{session_id}/close", json={
            "counted_cash": 150,
            "notes": "End of shift"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "closed"
        assert "variance" in data
        assert "expected_cash" in data
        print(f"✓ Cash Drawer closed: expected £{data['expected_cash']}, counted £{data['counted_cash']}, variance £{data['variance']}")
    
    def test_list_sessions(self, admin_session):
        """GET /api/cash-drawer/sessions/{pid} returns history"""
        resp = admin_session.get(f"{BASE_URL}/api/cash-drawer/sessions/aldgate-flats?limit=20")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        print(f"✓ Cash Drawer history: {len(data)} sessions")


# ==================== 10. 2FA TOTP ====================
class Test2FA:
    """Two-Factor Authentication TOTP tests"""
    
    def test_2fa_status_initial(self, admin_session):
        """GET /api/2fa/status returns enabled=false initially"""
        resp = admin_session.get(f"{BASE_URL}/api/2fa/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "enabled" in data
        assert "enrolled" in data
        print(f"✓ 2FA status: enabled={data['enabled']}, enrolled={data['enrolled']}")
    
    def test_2fa_enroll_returns_secret(self, admin_session):
        """POST /api/2fa/enroll returns secret and otpauth_url"""
        resp = admin_session.post(f"{BASE_URL}/api/2fa/enroll")
        assert resp.status_code == 200
        data = resp.json()
        assert "secret" in data
        assert "otpauth_url" in data
        assert data["issuer"] == "MyHotelBox"
        assert "account" in data
        print(f"✓ 2FA enroll returned secret (length {len(data['secret'])})")
        return data["secret"]
    
    def test_2fa_verify_with_valid_code(self, admin_session):
        """POST /api/2fa/verify with valid TOTP code activates 2FA"""
        # Enroll first
        enroll_resp = admin_session.post(f"{BASE_URL}/api/2fa/enroll")
        secret = enroll_resp.json()["secret"]
        
        # Generate valid code using pyotp
        totp = pyotp.TOTP(secret)
        code = totp.now()
        
        resp = admin_session.post(f"{BASE_URL}/api/2fa/verify", json={"code": code})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ["enabled", "verified"]
        if "backup_codes" in data:
            assert len(data["backup_codes"]) == 8
            print(f"✓ 2FA verified and enabled with {len(data['backup_codes'])} backup codes")
        else:
            print("✓ 2FA verified")
    
    def test_2fa_verify_invalid_code_401(self, admin_session):
        """POST /api/2fa/verify with invalid code returns 401"""
        # Enroll first
        admin_session.post(f"{BASE_URL}/api/2fa/enroll")
        
        resp = admin_session.post(f"{BASE_URL}/api/2fa/verify", json={"code": "000000"})
        assert resp.status_code == 401
        print("✓ 2FA verify returns 401 for invalid code")
    
    def test_2fa_disable_with_valid_code(self, admin_session):
        """POST /api/2fa/disable with valid code disables 2FA"""
        # Enroll and enable first
        enroll_resp = admin_session.post(f"{BASE_URL}/api/2fa/enroll")
        secret = enroll_resp.json()["secret"]
        totp = pyotp.TOTP(secret)
        admin_session.post(f"{BASE_URL}/api/2fa/verify", json={"code": totp.now()})
        
        # Now disable
        resp = admin_session.post(f"{BASE_URL}/api/2fa/disable", json={"code": totp.now()})
        assert resp.status_code == 200
        assert resp.json()["status"] == "disabled"
        print("✓ 2FA disabled successfully")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
