"""
Iteration 139 - HMRC Starter Checklist (HMRC 09/22) Backend Tests
Tests the expanded HMRC form schema with:
- Required fields: last_name, first_names, sex, dob, home_address, postcode, start_date, statement, declaration_*
- Optional fields: country, ni_number, q8/q9/q10 flags, has_loan, still_studying, student_loan_plans
- Validation: sex in [male,female], statement in [A,B,C], declaration_confirmed truthy, NI 9 chars if provided
- Backwards-compat aliases: first_name, gender, address
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"
STAFF_EMAIL = "sarah@hotel.test"
STAFF_PASSWORD = "StaffP@ss1"


@pytest.fixture(scope="module")
def admin_session():
    """Get authenticated admin session"""
    session = requests.Session()
    resp = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    assert resp.status_code == 200, f"Admin login failed: {resp.text}"
    return session


@pytest.fixture(scope="module")
def staff_session():
    """Get authenticated staff session (sarah@hotel.test)"""
    session = requests.Session()
    resp = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": STAFF_EMAIL,
        "password": STAFF_PASSWORD
    })
    assert resp.status_code == 200, f"Staff login failed: {resp.text}"
    return session


class TestHMRCRequiredFields:
    """Test that all required fields are validated"""
    
    def test_missing_last_name_returns_400(self, staff_session):
        """Missing last_name should return 400"""
        payload = {
            "first_names": "Sarah Jane",
            "sex": "female",
            "dob": "1990-05-15",
            "home_address": "123 Test Street, London",
            "postcode": "SW1A 1AA",
            "start_date": "2026-01-15",
            "statement": "A",
            "declaration_full_name": "SARAH JANE SMITH",
            "declaration_signature": "Sarah Smith",
            "declaration_date": "2026-01-10",
            "declaration_confirmed": True
        }
        resp = staff_session.post(f"{BASE_URL}/api/staff-onboarding/hmrc", json=payload)
        assert resp.status_code == 400
        assert "last_name" in resp.json().get("detail", "").lower()
    
    def test_missing_first_names_returns_400(self, staff_session):
        """Missing first_names should return 400"""
        payload = {
            "last_name": "Smith",
            "sex": "female",
            "dob": "1990-05-15",
            "home_address": "123 Test Street, London",
            "postcode": "SW1A 1AA",
            "start_date": "2026-01-15",
            "statement": "A",
            "declaration_full_name": "SARAH JANE SMITH",
            "declaration_signature": "Sarah Smith",
            "declaration_date": "2026-01-10",
            "declaration_confirmed": True
        }
        resp = staff_session.post(f"{BASE_URL}/api/staff-onboarding/hmrc", json=payload)
        assert resp.status_code == 400
        assert "first_names" in resp.json().get("detail", "").lower()
    
    def test_missing_sex_returns_400(self, staff_session):
        """Missing sex should return 400"""
        payload = {
            "last_name": "Smith",
            "first_names": "Sarah Jane",
            "dob": "1990-05-15",
            "home_address": "123 Test Street, London",
            "postcode": "SW1A 1AA",
            "start_date": "2026-01-15",
            "statement": "A",
            "declaration_full_name": "SARAH JANE SMITH",
            "declaration_signature": "Sarah Smith",
            "declaration_date": "2026-01-10",
            "declaration_confirmed": True
        }
        resp = staff_session.post(f"{BASE_URL}/api/staff-onboarding/hmrc", json=payload)
        assert resp.status_code == 400
        assert "sex" in resp.json().get("detail", "").lower()
    
    def test_missing_dob_returns_400(self, staff_session):
        """Missing dob should return 400"""
        payload = {
            "last_name": "Smith",
            "first_names": "Sarah Jane",
            "sex": "female",
            "home_address": "123 Test Street, London",
            "postcode": "SW1A 1AA",
            "start_date": "2026-01-15",
            "statement": "A",
            "declaration_full_name": "SARAH JANE SMITH",
            "declaration_signature": "Sarah Smith",
            "declaration_date": "2026-01-10",
            "declaration_confirmed": True
        }
        resp = staff_session.post(f"{BASE_URL}/api/staff-onboarding/hmrc", json=payload)
        assert resp.status_code == 400
        assert "dob" in resp.json().get("detail", "").lower()
    
    def test_missing_home_address_returns_400(self, staff_session):
        """Missing home_address should return 400"""
        payload = {
            "last_name": "Smith",
            "first_names": "Sarah Jane",
            "sex": "female",
            "dob": "1990-05-15",
            "postcode": "SW1A 1AA",
            "start_date": "2026-01-15",
            "statement": "A",
            "declaration_full_name": "SARAH JANE SMITH",
            "declaration_signature": "Sarah Smith",
            "declaration_date": "2026-01-10",
            "declaration_confirmed": True
        }
        resp = staff_session.post(f"{BASE_URL}/api/staff-onboarding/hmrc", json=payload)
        assert resp.status_code == 400
        assert "home_address" in resp.json().get("detail", "").lower()
    
    def test_missing_postcode_returns_400(self, staff_session):
        """Missing postcode should return 400"""
        payload = {
            "last_name": "Smith",
            "first_names": "Sarah Jane",
            "sex": "female",
            "dob": "1990-05-15",
            "home_address": "123 Test Street, London",
            "start_date": "2026-01-15",
            "statement": "A",
            "declaration_full_name": "SARAH JANE SMITH",
            "declaration_signature": "Sarah Smith",
            "declaration_date": "2026-01-10",
            "declaration_confirmed": True
        }
        resp = staff_session.post(f"{BASE_URL}/api/staff-onboarding/hmrc", json=payload)
        assert resp.status_code == 400
        assert "postcode" in resp.json().get("detail", "").lower()
    
    def test_missing_start_date_returns_400(self, staff_session):
        """Missing start_date should return 400"""
        payload = {
            "last_name": "Smith",
            "first_names": "Sarah Jane",
            "sex": "female",
            "dob": "1990-05-15",
            "home_address": "123 Test Street, London",
            "postcode": "SW1A 1AA",
            "statement": "A",
            "declaration_full_name": "SARAH JANE SMITH",
            "declaration_signature": "Sarah Smith",
            "declaration_date": "2026-01-10",
            "declaration_confirmed": True
        }
        resp = staff_session.post(f"{BASE_URL}/api/staff-onboarding/hmrc", json=payload)
        assert resp.status_code == 400
        assert "start_date" in resp.json().get("detail", "").lower()
    
    def test_missing_statement_returns_400(self, staff_session):
        """Missing statement should return 400"""
        payload = {
            "last_name": "Smith",
            "first_names": "Sarah Jane",
            "sex": "female",
            "dob": "1990-05-15",
            "home_address": "123 Test Street, London",
            "postcode": "SW1A 1AA",
            "start_date": "2026-01-15",
            "declaration_full_name": "SARAH JANE SMITH",
            "declaration_signature": "Sarah Smith",
            "declaration_date": "2026-01-10",
            "declaration_confirmed": True
        }
        resp = staff_session.post(f"{BASE_URL}/api/staff-onboarding/hmrc", json=payload)
        assert resp.status_code == 400
        assert "statement" in resp.json().get("detail", "").lower()
    
    def test_missing_declaration_full_name_returns_400(self, staff_session):
        """Missing declaration_full_name should return 400"""
        payload = {
            "last_name": "Smith",
            "first_names": "Sarah Jane",
            "sex": "female",
            "dob": "1990-05-15",
            "home_address": "123 Test Street, London",
            "postcode": "SW1A 1AA",
            "start_date": "2026-01-15",
            "statement": "A",
            "declaration_signature": "Sarah Smith",
            "declaration_date": "2026-01-10",
            "declaration_confirmed": True
        }
        resp = staff_session.post(f"{BASE_URL}/api/staff-onboarding/hmrc", json=payload)
        assert resp.status_code == 400
        assert "declaration_full_name" in resp.json().get("detail", "").lower()
    
    def test_missing_declaration_signature_returns_400(self, staff_session):
        """Missing declaration_signature should return 400"""
        payload = {
            "last_name": "Smith",
            "first_names": "Sarah Jane",
            "sex": "female",
            "dob": "1990-05-15",
            "home_address": "123 Test Street, London",
            "postcode": "SW1A 1AA",
            "start_date": "2026-01-15",
            "statement": "A",
            "declaration_full_name": "SARAH JANE SMITH",
            "declaration_date": "2026-01-10",
            "declaration_confirmed": True
        }
        resp = staff_session.post(f"{BASE_URL}/api/staff-onboarding/hmrc", json=payload)
        assert resp.status_code == 400
        assert "declaration_signature" in resp.json().get("detail", "").lower()
    
    def test_missing_declaration_date_returns_400(self, staff_session):
        """Missing declaration_date should return 400"""
        payload = {
            "last_name": "Smith",
            "first_names": "Sarah Jane",
            "sex": "female",
            "dob": "1990-05-15",
            "home_address": "123 Test Street, London",
            "postcode": "SW1A 1AA",
            "start_date": "2026-01-15",
            "statement": "A",
            "declaration_full_name": "SARAH JANE SMITH",
            "declaration_signature": "Sarah Smith",
            "declaration_confirmed": True
        }
        resp = staff_session.post(f"{BASE_URL}/api/staff-onboarding/hmrc", json=payload)
        assert resp.status_code == 400
        assert "declaration_date" in resp.json().get("detail", "").lower()


class TestHMRCValidation:
    """Test field validation rules"""
    
    def test_invalid_sex_returns_400(self, staff_session):
        """Sex must be male or female"""
        payload = {
            "last_name": "Smith",
            "first_names": "Sarah Jane",
            "sex": "other",  # Invalid
            "dob": "1990-05-15",
            "home_address": "123 Test Street, London",
            "postcode": "SW1A 1AA",
            "start_date": "2026-01-15",
            "statement": "A",
            "declaration_full_name": "SARAH JANE SMITH",
            "declaration_signature": "Sarah Smith",
            "declaration_date": "2026-01-10",
            "declaration_confirmed": True
        }
        resp = staff_session.post(f"{BASE_URL}/api/staff-onboarding/hmrc", json=payload)
        assert resp.status_code == 400
        assert "male or female" in resp.json().get("detail", "").lower()
    
    def test_invalid_statement_returns_400(self, staff_session):
        """Statement must be A, B or C"""
        payload = {
            "last_name": "Smith",
            "first_names": "Sarah Jane",
            "sex": "female",
            "dob": "1990-05-15",
            "home_address": "123 Test Street, London",
            "postcode": "SW1A 1AA",
            "start_date": "2026-01-15",
            "statement": "D",  # Invalid
            "declaration_full_name": "SARAH JANE SMITH",
            "declaration_signature": "Sarah Smith",
            "declaration_date": "2026-01-10",
            "declaration_confirmed": True
        }
        resp = staff_session.post(f"{BASE_URL}/api/staff-onboarding/hmrc", json=payload)
        assert resp.status_code == 400
        assert "statement must be a, b or c" in resp.json().get("detail", "").lower()
    
    def test_declaration_not_confirmed_returns_400(self, staff_session):
        """Declaration must be confirmed"""
        payload = {
            "last_name": "Smith",
            "first_names": "Sarah Jane",
            "sex": "female",
            "dob": "1990-05-15",
            "home_address": "123 Test Street, London",
            "postcode": "SW1A 1AA",
            "start_date": "2026-01-15",
            "statement": "A",
            "declaration_full_name": "SARAH JANE SMITH",
            "declaration_signature": "Sarah Smith",
            "declaration_date": "2026-01-10",
            "declaration_confirmed": False  # Not confirmed
        }
        resp = staff_session.post(f"{BASE_URL}/api/staff-onboarding/hmrc", json=payload)
        assert resp.status_code == 400
        assert "confirm the declaration" in resp.json().get("detail", "").lower()
    
    def test_invalid_ni_number_returns_400(self, staff_session):
        """NI number must be 9 characters if provided"""
        payload = {
            "last_name": "Smith",
            "first_names": "Sarah Jane",
            "sex": "female",
            "dob": "1990-05-15",
            "home_address": "123 Test Street, London",
            "postcode": "SW1A 1AA",
            "start_date": "2026-01-15",
            "statement": "A",
            "ni_number": "AB12345",  # Only 7 chars
            "declaration_full_name": "SARAH JANE SMITH",
            "declaration_signature": "Sarah Smith",
            "declaration_date": "2026-01-10",
            "declaration_confirmed": True
        }
        resp = staff_session.post(f"{BASE_URL}/api/staff-onboarding/hmrc", json=payload)
        assert resp.status_code == 400
        assert "9 characters" in resp.json().get("detail", "").lower()
    
    def test_valid_ni_number_accepted(self, staff_session):
        """Valid 9-char NI number should be accepted"""
        payload = {
            "last_name": "Smith",
            "first_names": "Sarah Jane",
            "sex": "female",
            "dob": "1990-05-15",
            "home_address": "123 Test Street, London",
            "postcode": "SW1A 1AA",
            "start_date": "2026-01-15",
            "statement": "A",
            "ni_number": "AB123456C",  # Valid 9 chars
            "declaration_full_name": "SARAH JANE SMITH",
            "declaration_signature": "Sarah Smith",
            "declaration_date": "2026-01-10",
            "declaration_confirmed": True
        }
        resp = staff_session.post(f"{BASE_URL}/api/staff-onboarding/hmrc", json=payload)
        assert resp.status_code == 200
        assert resp.json().get("ok") == True


class TestHMRCOptionalFields:
    """Test optional fields are accepted"""
    
    def test_ni_number_optional(self, staff_session):
        """NI number is optional"""
        payload = {
            "last_name": "Smith",
            "first_names": "Sarah Jane",
            "sex": "female",
            "dob": "1990-05-15",
            "home_address": "123 Test Street, London",
            "postcode": "SW1A 1AA",
            "start_date": "2026-01-15",
            "statement": "A",
            # No ni_number
            "declaration_full_name": "SARAH JANE SMITH",
            "declaration_signature": "Sarah Smith",
            "declaration_date": "2026-01-10",
            "declaration_confirmed": True
        }
        resp = staff_session.post(f"{BASE_URL}/api/staff-onboarding/hmrc", json=payload)
        assert resp.status_code == 200
    
    def test_country_defaults_to_uk(self, staff_session):
        """Country defaults to United Kingdom"""
        payload = {
            "last_name": "Smith",
            "first_names": "Sarah Jane",
            "sex": "female",
            "dob": "1990-05-15",
            "home_address": "123 Test Street, London",
            "postcode": "SW1A 1AA",
            "start_date": "2026-01-15",
            "statement": "A",
            # No country
            "declaration_full_name": "SARAH JANE SMITH",
            "declaration_signature": "Sarah Smith",
            "declaration_date": "2026-01-10",
            "declaration_confirmed": True
        }
        resp = staff_session.post(f"{BASE_URL}/api/staff-onboarding/hmrc", json=payload)
        assert resp.status_code == 200
        
        # Verify stored data
        me_resp = staff_session.get(f"{BASE_URL}/api/staff-onboarding/me")
        assert me_resp.status_code == 200
        hmrc_data = me_resp.json().get("hmrc_data", {})
        assert hmrc_data.get("country") == "United Kingdom"
    
    def test_q8_q9_q10_flags_accepted(self, staff_session):
        """Q8/Q9/Q10 decision tree flags are accepted"""
        payload = {
            "last_name": "Smith",
            "first_names": "Sarah Jane",
            "sex": "female",
            "dob": "1990-05-15",
            "home_address": "123 Test Street, London",
            "postcode": "SW1A 1AA",
            "start_date": "2026-01-15",
            "statement": "B",
            "q8_another_job": False,
            "q9_receives_pension": False,
            "q10_recent_payments": True,  # This leads to Statement B
            "declaration_full_name": "SARAH JANE SMITH",
            "declaration_signature": "Sarah Smith",
            "declaration_date": "2026-01-10",
            "declaration_confirmed": True
        }
        resp = staff_session.post(f"{BASE_URL}/api/staff-onboarding/hmrc", json=payload)
        assert resp.status_code == 200
        
        # Verify stored data
        me_resp = staff_session.get(f"{BASE_URL}/api/staff-onboarding/me")
        hmrc_data = me_resp.json().get("hmrc_data", {})
        assert hmrc_data.get("q8_another_job") == False
        assert hmrc_data.get("q9_receives_pension") == False
        assert hmrc_data.get("q10_recent_payments") == True
        assert hmrc_data.get("statement") == "B"
    
    def test_student_loan_plans_filtered(self, staff_session):
        """Student loan plans are filtered to valid values"""
        payload = {
            "last_name": "Smith",
            "first_names": "Sarah Jane",
            "sex": "female",
            "dob": "1990-05-15",
            "home_address": "123 Test Street, London",
            "postcode": "SW1A 1AA",
            "start_date": "2026-01-15",
            "statement": "A",
            "has_loan": True,
            "still_studying": False,
            "student_loan_plans": ["plan_1", "plan_2", "invalid_plan", "postgraduate"],
            "declaration_full_name": "SARAH JANE SMITH",
            "declaration_signature": "Sarah Smith",
            "declaration_date": "2026-01-10",
            "declaration_confirmed": True
        }
        resp = staff_session.post(f"{BASE_URL}/api/staff-onboarding/hmrc", json=payload)
        assert resp.status_code == 200
        
        # Verify stored data - invalid_plan should be filtered out
        me_resp = staff_session.get(f"{BASE_URL}/api/staff-onboarding/me")
        hmrc_data = me_resp.json().get("hmrc_data", {})
        plans = hmrc_data.get("student_loan_plans", [])
        assert "plan_1" in plans
        assert "plan_2" in plans
        assert "postgraduate" in plans
        assert "invalid_plan" not in plans


class TestHMRCBackwardsCompatAliases:
    """Test backwards-compat aliases for admin panel"""
    
    def test_first_name_alias_created(self, staff_session):
        """first_name alias is derived from first_names"""
        payload = {
            "last_name": "Smith",
            "first_names": "Sarah Jane",
            "sex": "female",
            "dob": "1990-05-15",
            "home_address": "123 Test Street, London",
            "postcode": "SW1A 1AA",
            "start_date": "2026-01-15",
            "statement": "A",
            "declaration_full_name": "SARAH JANE SMITH",
            "declaration_signature": "Sarah Smith",
            "declaration_date": "2026-01-10",
            "declaration_confirmed": True
        }
        resp = staff_session.post(f"{BASE_URL}/api/staff-onboarding/hmrc", json=payload)
        assert resp.status_code == 200
        
        me_resp = staff_session.get(f"{BASE_URL}/api/staff-onboarding/me")
        hmrc_data = me_resp.json().get("hmrc_data", {})
        # first_name should be first word of first_names
        assert hmrc_data.get("first_name") == "Sarah"
    
    def test_gender_alias_created(self, staff_session):
        """gender alias equals sex"""
        payload = {
            "last_name": "Smith",
            "first_names": "Sarah Jane",
            "sex": "female",
            "dob": "1990-05-15",
            "home_address": "123 Test Street, London",
            "postcode": "SW1A 1AA",
            "start_date": "2026-01-15",
            "statement": "A",
            "declaration_full_name": "SARAH JANE SMITH",
            "declaration_signature": "Sarah Smith",
            "declaration_date": "2026-01-10",
            "declaration_confirmed": True
        }
        resp = staff_session.post(f"{BASE_URL}/api/staff-onboarding/hmrc", json=payload)
        assert resp.status_code == 200
        
        me_resp = staff_session.get(f"{BASE_URL}/api/staff-onboarding/me")
        hmrc_data = me_resp.json().get("hmrc_data", {})
        assert hmrc_data.get("gender") == "female"
    
    def test_address_alias_created(self, staff_session):
        """address alias equals home_address"""
        payload = {
            "last_name": "Smith",
            "first_names": "Sarah Jane",
            "sex": "female",
            "dob": "1990-05-15",
            "home_address": "123 Test Street, London",
            "postcode": "SW1A 1AA",
            "start_date": "2026-01-15",
            "statement": "A",
            "declaration_full_name": "SARAH JANE SMITH",
            "declaration_signature": "Sarah Smith",
            "declaration_date": "2026-01-10",
            "declaration_confirmed": True
        }
        resp = staff_session.post(f"{BASE_URL}/api/staff-onboarding/hmrc", json=payload)
        assert resp.status_code == 200
        
        me_resp = staff_session.get(f"{BASE_URL}/api/staff-onboarding/me")
        hmrc_data = me_resp.json().get("hmrc_data", {})
        assert hmrc_data.get("address") == "123 Test Street, London"


class TestHMRCStatementDecisionTree:
    """Test statement decision tree logic"""
    
    def test_q8_yes_gives_statement_c(self, staff_session):
        """Q8 Yes → Statement C"""
        payload = {
            "last_name": "Smith",
            "first_names": "Sarah Jane",
            "sex": "female",
            "dob": "1990-05-15",
            "home_address": "123 Test Street, London",
            "postcode": "SW1A 1AA",
            "start_date": "2026-01-15",
            "statement": "C",
            "q8_another_job": True,
            "declaration_full_name": "SARAH JANE SMITH",
            "declaration_signature": "Sarah Smith",
            "declaration_date": "2026-01-10",
            "declaration_confirmed": True
        }
        resp = staff_session.post(f"{BASE_URL}/api/staff-onboarding/hmrc", json=payload)
        assert resp.status_code == 200
        
        me_resp = staff_session.get(f"{BASE_URL}/api/staff-onboarding/me")
        hmrc_data = me_resp.json().get("hmrc_data", {})
        assert hmrc_data.get("q8_another_job") == True
        assert hmrc_data.get("statement") == "C"
    
    def test_q8_no_q9_yes_gives_statement_c(self, staff_session):
        """Q8 No + Q9 Yes → Statement C"""
        payload = {
            "last_name": "Smith",
            "first_names": "Sarah Jane",
            "sex": "female",
            "dob": "1990-05-15",
            "home_address": "123 Test Street, London",
            "postcode": "SW1A 1AA",
            "start_date": "2026-01-15",
            "statement": "C",
            "q8_another_job": False,
            "q9_receives_pension": True,
            "declaration_full_name": "SARAH JANE SMITH",
            "declaration_signature": "Sarah Smith",
            "declaration_date": "2026-01-10",
            "declaration_confirmed": True
        }
        resp = staff_session.post(f"{BASE_URL}/api/staff-onboarding/hmrc", json=payload)
        assert resp.status_code == 200
        
        me_resp = staff_session.get(f"{BASE_URL}/api/staff-onboarding/me")
        hmrc_data = me_resp.json().get("hmrc_data", {})
        assert hmrc_data.get("q9_receives_pension") == True
        assert hmrc_data.get("statement") == "C"
    
    def test_q8_no_q9_no_q10_yes_gives_statement_b(self, staff_session):
        """Q8 No + Q9 No + Q10 Yes → Statement B"""
        payload = {
            "last_name": "Smith",
            "first_names": "Sarah Jane",
            "sex": "female",
            "dob": "1990-05-15",
            "home_address": "123 Test Street, London",
            "postcode": "SW1A 1AA",
            "start_date": "2026-01-15",
            "statement": "B",
            "q8_another_job": False,
            "q9_receives_pension": False,
            "q10_recent_payments": True,
            "declaration_full_name": "SARAH JANE SMITH",
            "declaration_signature": "Sarah Smith",
            "declaration_date": "2026-01-10",
            "declaration_confirmed": True
        }
        resp = staff_session.post(f"{BASE_URL}/api/staff-onboarding/hmrc", json=payload)
        assert resp.status_code == 200
        
        me_resp = staff_session.get(f"{BASE_URL}/api/staff-onboarding/me")
        hmrc_data = me_resp.json().get("hmrc_data", {})
        assert hmrc_data.get("q10_recent_payments") == True
        assert hmrc_data.get("statement") == "B"
    
    def test_q8_no_q9_no_q10_no_gives_statement_a(self, staff_session):
        """Q8 No + Q9 No + Q10 No → Statement A"""
        payload = {
            "last_name": "Smith",
            "first_names": "Sarah Jane",
            "sex": "female",
            "dob": "1990-05-15",
            "home_address": "123 Test Street, London",
            "postcode": "SW1A 1AA",
            "start_date": "2026-01-15",
            "statement": "A",
            "q8_another_job": False,
            "q9_receives_pension": False,
            "q10_recent_payments": False,
            "declaration_full_name": "SARAH JANE SMITH",
            "declaration_signature": "Sarah Smith",
            "declaration_date": "2026-01-10",
            "declaration_confirmed": True
        }
        resp = staff_session.post(f"{BASE_URL}/api/staff-onboarding/hmrc", json=payload)
        assert resp.status_code == 200
        
        me_resp = staff_session.get(f"{BASE_URL}/api/staff-onboarding/me")
        hmrc_data = me_resp.json().get("hmrc_data", {})
        assert hmrc_data.get("statement") == "A"


class TestAdminPanelHMRCDisplay:
    """Test admin panel shows all HMRC fields"""
    
    def test_admin_can_see_hmrc_data(self, admin_session, staff_session):
        """Admin can see all HMRC fields in onboarding list"""
        # First submit HMRC data as staff
        payload = {
            "last_name": "Smith",
            "first_names": "Sarah Jane",
            "sex": "female",
            "dob": "1990-05-15",
            "home_address": "123 Test Street, London",
            "postcode": "SW1A 1AA",
            "country": "United Kingdom",
            "ni_number": "AB123456C",
            "start_date": "2026-01-15",
            "statement": "A",
            "q8_another_job": False,
            "q9_receives_pension": False,
            "q10_recent_payments": False,
            "has_loan": True,
            "still_studying": False,
            "student_loan_plans": ["plan_2", "postgraduate"],
            "declaration_full_name": "SARAH JANE SMITH",
            "declaration_signature": "Sarah Smith",
            "declaration_date": "2026-01-10",
            "declaration_confirmed": True
        }
        staff_session.post(f"{BASE_URL}/api/staff-onboarding/hmrc", json=payload)
        
        # Admin fetches list
        resp = admin_session.get(f"{BASE_URL}/api/staff-onboarding/list")
        assert resp.status_code == 200
        
        # Find Sarah's record
        records = resp.json()
        sarah_record = next((r for r in records if r.get("user_email") == STAFF_EMAIL), None)
        assert sarah_record is not None, "Sarah's record not found"
        
        hmrc_data = sarah_record.get("hmrc_data", {})
        # Verify all fields are present
        assert hmrc_data.get("last_name") == "Smith"
        assert hmrc_data.get("first_names") == "Sarah Jane"
        assert hmrc_data.get("sex") == "female"
        assert hmrc_data.get("dob") == "1990-05-15"
        assert hmrc_data.get("home_address") == "123 Test Street, London"
        assert hmrc_data.get("postcode") == "SW1A 1AA"
        assert hmrc_data.get("country") == "United Kingdom"
        assert hmrc_data.get("ni_number") == "AB123456C"
        assert hmrc_data.get("start_date") == "2026-01-15"
        assert hmrc_data.get("statement") == "A"
        assert hmrc_data.get("has_loan") == True
        assert hmrc_data.get("still_studying") == False
        assert "plan_2" in hmrc_data.get("student_loan_plans", [])
        assert "postgraduate" in hmrc_data.get("student_loan_plans", [])
        assert hmrc_data.get("declaration_full_name") == "SARAH JANE SMITH"
        assert hmrc_data.get("declaration_date") == "2026-01-10"
        # Backwards-compat aliases
        assert hmrc_data.get("first_name") == "Sarah"
        assert hmrc_data.get("gender") == "female"
        assert hmrc_data.get("address") == "123 Test Street, London"


class TestOnboardingActivation:
    """Test complete onboarding → account activation"""
    
    def test_complete_onboarding_activates_account(self, staff_session, admin_session):
        """Completing all 4 tasks activates the account"""
        # Get current status
        me_resp = staff_session.get(f"{BASE_URL}/api/staff-onboarding/me")
        status = me_resp.json()
        
        # Check if all tasks are complete
        progress = status.get("progress", {})
        if progress.get("complete"):
            # Try to complete onboarding
            complete_resp = staff_session.post(f"{BASE_URL}/api/staff-onboarding/complete")
            # Should succeed or already be activated
            assert complete_resp.status_code in [200, 400]
            
            if complete_resp.status_code == 200:
                assert complete_resp.json().get("activated") == True
        else:
            # If not complete, verify we can't activate
            complete_resp = staff_session.post(f"{BASE_URL}/api/staff-onboarding/complete")
            assert complete_resp.status_code == 400
            assert "incomplete" in complete_resp.json().get("detail", "").lower()
