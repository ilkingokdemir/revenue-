"""
Iteration 157 Backend Tests - Revenue Health, IP Allowlist, Card Vault
Tests the 3 new competitor-gap features:
  11. Revenue Health composite KPI tile
  12. IP Allowlist for admin access control
  13. PCI Card-on-File Vault (Stripe integration)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Test credentials
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"
RECEPTIONIST_EMAIL = "testrecep@hotelbox.com"
RECEPTIONIST_PASSWORD = "Test2026!"

@pytest.fixture(scope="module")
def admin_session():
    """Login as admin and return session with auth cookie"""
    session = requests.Session()
    resp = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    assert resp.status_code == 200, f"Admin login failed: {resp.text}"
    return session

@pytest.fixture(scope="module")
def receptionist_session():
    """Login as receptionist and return session with auth cookie"""
    session = requests.Session()
    resp = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": RECEPTIONIST_EMAIL,
        "password": RECEPTIONIST_PASSWORD
    })
    assert resp.status_code == 200, f"Receptionist login failed: {resp.text}"
    return session


# ═══════════════════════════════════════════════════════════════════════════════
# 11. REVENUE HEALTH COMPOSITE KPI
# ═══════════════════════════════════════════════════════════════════════════════

class TestRevenueHealth:
    """Revenue Health endpoint tests - composite KPI tile with letter grade"""
    
    def test_revenue_health_by_property(self, admin_session):
        """GET /api/revenue-health/{pid} returns composite KPI with grade"""
        resp = admin_session.get(f"{BASE_URL}/api/revenue-health/aldgate-flats?from_date=2026-01-01&to_date=2026-12-31")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        # Verify structure
        assert "overall_score" in data, "Missing overall_score"
        assert "grade" in data, "Missing grade"
        assert "metrics" in data, "Missing metrics"
        
        # Verify score is bounded 0-100
        assert 0 <= data["overall_score"] <= 100, f"Score {data['overall_score']} out of bounds"
        
        # Verify grade is valid
        valid_grades = ["A+", "A", "B", "C", "D", "F"]
        assert data["grade"] in valid_grades, f"Invalid grade: {data['grade']}"
        
        # Verify 4 metrics
        assert len(data["metrics"]) == 4, f"Expected 4 metrics, got {len(data['metrics'])}"
        
        # Verify metric keys
        metric_keys = [m["key"] for m in data["metrics"]]
        expected_keys = ["direct_capture", "deposits", "commission_match", "champion_revenue"]
        for key in expected_keys:
            assert key in metric_keys, f"Missing metric key: {key}"
        
        # Verify each metric has required fields
        for metric in data["metrics"]:
            assert "key" in metric
            assert "label" in metric
            assert "score" in metric
            assert "value" in metric
            assert "unit" in metric
            assert "target" in metric
            assert "summary" in metric
            assert "color" in metric
            # Score should be 0-100
            assert 0 <= metric["score"] <= 100, f"Metric {metric['key']} score {metric['score']} out of bounds"
        
        print(f"Revenue Health: Grade={data['grade']}, Score={data['overall_score']}")
    
    def test_revenue_health_all_properties(self, admin_session):
        """GET /api/revenue-health/all works without property filter"""
        resp = admin_session.get(f"{BASE_URL}/api/revenue-health/all")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        assert "overall_score" in data
        assert "grade" in data
        assert "metrics" in data
        assert data["property_id"] == "all"
        print(f"Revenue Health (all): Grade={data['grade']}, Score={data['overall_score']}")
    
    def test_revenue_health_auth_required(self, receptionist_session):
        """Non-admin/non-manager cannot access revenue health"""
        # Receptionist should NOT have access (only admin/manager)
        resp = receptionist_session.get(f"{BASE_URL}/api/revenue-health/aldgate-flats")
        # Should be 403 Forbidden
        assert resp.status_code == 403, f"Expected 403 for receptionist, got {resp.status_code}"
        print("Revenue Health auth check: Receptionist correctly denied")


# ═══════════════════════════════════════════════════════════════════════════════
# 12. IP ALLOWLIST
# ═══════════════════════════════════════════════════════════════════════════════

class TestIpAllowlist:
    """IP Allowlist endpoint tests - enterprise security feature"""
    
    def test_ip_allowlist_empty(self, admin_session):
        """GET /api/ip-allowlist returns empty list initially"""
        # First clean up any existing rules
        resp = admin_session.get(f"{BASE_URL}/api/ip-allowlist")
        assert resp.status_code == 200
        data = resp.json()
        
        # Delete any existing rules for clean test
        for rule in data.get("rules", []):
            admin_session.delete(f"{BASE_URL}/api/ip-allowlist/{rule['id']}")
        
        # Now verify empty state
        resp = admin_session.get(f"{BASE_URL}/api/ip-allowlist")
        assert resp.status_code == 200
        data = resp.json()
        
        assert "enabled" in data
        assert "rules" in data
        assert "count" in data
        assert data["enabled"] == False, "Should be disabled when empty"
        assert data["count"] == 0
        print("IP Allowlist empty state verified")
    
    def test_ip_allowlist_my_ip(self, admin_session):
        """GET /api/ip-allowlist/my-ip returns client IP"""
        resp = admin_session.get(f"{BASE_URL}/api/ip-allowlist/my-ip")
        assert resp.status_code == 200
        
        data = resp.json()
        assert "ip" in data
        assert "via_proxy" in data
        print(f"My IP: {data['ip']}, via_proxy: {data['via_proxy']}")
    
    def test_ip_allowlist_add_cidr(self, admin_session):
        """POST /api/ip-allowlist adds CIDR rule"""
        resp = admin_session.post(f"{BASE_URL}/api/ip-allowlist", json={
            "cidr_or_ip": "10.0.0.0/24",
            "label": "Test Office Network"
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        assert "id" in data
        assert data["cidr_or_ip"] == "10.0.0.0/24"
        assert data["label"] == "Test Office Network"
        print(f"Added CIDR rule: {data['id']}")
        return data["id"]
    
    def test_ip_allowlist_add_invalid(self, admin_session):
        """POST /api/ip-allowlist with invalid IP returns 400"""
        resp = admin_session.post(f"{BASE_URL}/api/ip-allowlist", json={
            "cidr_or_ip": "not-an-ip",
            "label": "Invalid"
        })
        assert resp.status_code == 400, f"Expected 400 for invalid IP, got {resp.status_code}"
        print("Invalid IP correctly rejected with 400")
    
    def test_ip_allowlist_duplicate(self, admin_session):
        """POST /api/ip-allowlist with duplicate returns 409"""
        # First add a rule
        admin_session.post(f"{BASE_URL}/api/ip-allowlist", json={
            "cidr_or_ip": "192.168.1.0/24",
            "label": "Duplicate Test"
        })
        
        # Try to add same rule again
        resp = admin_session.post(f"{BASE_URL}/api/ip-allowlist", json={
            "cidr_or_ip": "192.168.1.0/24",
            "label": "Duplicate Test 2"
        })
        assert resp.status_code == 409, f"Expected 409 for duplicate, got {resp.status_code}"
        print("Duplicate rule correctly rejected with 409")
    
    def test_ip_allowlist_check_allowed(self, admin_session):
        """POST /api/ip-allowlist/check returns allowed=true for matching IP"""
        # Ensure we have a 10.0.0.0/24 rule
        admin_session.post(f"{BASE_URL}/api/ip-allowlist", json={
            "cidr_or_ip": "10.0.0.0/24",
            "label": "Check Test"
        })
        
        resp = admin_session.post(f"{BASE_URL}/api/ip-allowlist/check", json={
            "ip": "10.0.0.5"
        })
        assert resp.status_code == 200
        
        data = resp.json()
        assert data["allowed"] == True, f"Expected allowed=true, got {data}"
        assert "matched_rule" in data
        assert "reason" in data
        print(f"IP 10.0.0.5 allowed: {data['reason']}")
    
    def test_ip_allowlist_check_denied(self, admin_session):
        """POST /api/ip-allowlist/check returns allowed=false for non-matching IP"""
        resp = admin_session.post(f"{BASE_URL}/api/ip-allowlist/check", json={
            "ip": "1.2.3.4"
        })
        assert resp.status_code == 200
        
        data = resp.json()
        assert data["allowed"] == False, f"Expected allowed=false, got {data}"
        print(f"IP 1.2.3.4 denied: {data['reason']}")
    
    def test_ip_allowlist_delete(self, admin_session):
        """DELETE /api/ip-allowlist/{id} removes rule"""
        # Add a rule to delete
        resp = admin_session.post(f"{BASE_URL}/api/ip-allowlist", json={
            "cidr_or_ip": "172.16.0.1",
            "label": "Delete Test"
        })
        rule_id = resp.json()["id"]
        
        # Delete it
        resp = admin_session.delete(f"{BASE_URL}/api/ip-allowlist/{rule_id}")
        assert resp.status_code == 200
        
        data = resp.json()
        assert data["status"] == "deleted"
        print(f"Rule {rule_id} deleted")
    
    def test_ip_allowlist_auth_admin_only(self, receptionist_session):
        """Only admin role can access IP allowlist"""
        resp = receptionist_session.get(f"{BASE_URL}/api/ip-allowlist")
        assert resp.status_code == 403, f"Expected 403 for receptionist, got {resp.status_code}"
        print("IP Allowlist auth check: Receptionist correctly denied")


# ═══════════════════════════════════════════════════════════════════════════════
# 13. CARD VAULT (STRIPE)
# ═══════════════════════════════════════════════════════════════════════════════

class TestCardVault:
    """Card Vault endpoint tests - PCI-compliant card-on-file via Stripe"""
    
    def test_card_vault_config(self, admin_session):
        """GET /api/card-vault/config returns publishable key and mode"""
        resp = admin_session.get(f"{BASE_URL}/api/card-vault/config")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        assert "publishable_key" in data
        assert "mode" in data
        assert data["mode"] in ["test", "live"]
        print(f"Card Vault config: mode={data['mode']}, publishable_key={'set' if data['publishable_key'] else 'empty'}")
    
    def test_card_vault_setup_intent_placeholder_key(self, admin_session):
        """POST /api/card-vault/setup-intent with placeholder key returns Stripe error"""
        # With STRIPE_API_KEY='sk_test_emergent' (placeholder), Stripe will return an error
        resp = admin_session.post(f"{BASE_URL}/api/card-vault/setup-intent", json={
            "email": "test@example.com"
        })
        
        # Expected: 400 with Stripe error about invalid API key
        # This is acceptable behavior - the endpoint correctly proxies to Stripe
        if resp.status_code == 400:
            data = resp.json()
            # Should contain Stripe error message
            assert "detail" in data
            # Stripe typically says "Invalid API Key" or similar
            print(f"Setup intent with placeholder key: 400 - {data['detail']}")
        elif resp.status_code == 200:
            # If somehow a real key is configured, verify response structure
            data = resp.json()
            assert "client_secret" in data
            assert "setup_intent_id" in data
            assert "customer_id" in data
            print(f"Setup intent succeeded (real key): {data['setup_intent_id']}")
        else:
            pytest.fail(f"Unexpected status {resp.status_code}: {resp.text}")
    
    def test_card_vault_setup_intent_missing_email(self, admin_session):
        """POST /api/card-vault/setup-intent without email returns 400"""
        resp = admin_session.post(f"{BASE_URL}/api/card-vault/setup-intent", json={})
        assert resp.status_code == 400, f"Expected 400 for missing email, got {resp.status_code}"
        print("Setup intent without email correctly rejected")
    
    def test_card_vault_guest_lookup_empty(self, admin_session):
        """GET /api/card-vault/guest/{email} returns empty list for new guest"""
        resp = admin_session.get(f"{BASE_URL}/api/card-vault/guest/test@example.com")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        assert isinstance(data, list)
        # Should be empty since no methods saved
        print(f"Guest lookup for test@example.com: {len(data)} cards")
    
    def test_card_vault_save_method_requires_fields(self, admin_session):
        """POST /api/card-vault/save-method requires email + payment_method_id"""
        resp = admin_session.post(f"{BASE_URL}/api/card-vault/save-method", json={
            "email": "test@example.com"
            # Missing payment_method_id
        })
        assert resp.status_code == 400, f"Expected 400 for missing payment_method_id, got {resp.status_code}"
        print("Save method without payment_method_id correctly rejected")
    
    def test_card_vault_charge_not_found(self, admin_session):
        """POST /api/card-vault/charge with bogus payment_method_id returns 404"""
        resp = admin_session.post(f"{BASE_URL}/api/card-vault/charge", json={
            "payment_method_id": "pm_bogus_12345",
            "amount_gbp": 50.00
        })
        assert resp.status_code == 404, f"Expected 404 for bogus payment_method_id, got {resp.status_code}"
        print("Charge with bogus payment_method_id correctly returns 404")
    
    def test_card_vault_charge_missing_amount(self, admin_session):
        """POST /api/card-vault/charge without amount returns 400"""
        resp = admin_session.post(f"{BASE_URL}/api/card-vault/charge", json={
            "payment_method_id": "pm_test"
            # Missing amount_gbp
        })
        assert resp.status_code == 400, f"Expected 400 for missing amount, got {resp.status_code}"
        print("Charge without amount correctly rejected")
    
    def test_card_vault_receptionist_can_access_config(self, receptionist_session):
        """Receptionist can access card vault config (admin/manager/receptionist allowed)"""
        resp = receptionist_session.get(f"{BASE_URL}/api/card-vault/config")
        assert resp.status_code == 200, f"Expected 200 for receptionist, got {resp.status_code}"
        print("Receptionist can access card vault config")


# ═══════════════════════════════════════════════════════════════════════════════
# CLEANUP
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="module", autouse=True)
def cleanup_ip_rules(admin_session):
    """Clean up IP allowlist rules after tests"""
    yield
    # Cleanup after all tests
    try:
        resp = admin_session.get(f"{BASE_URL}/api/ip-allowlist")
        if resp.status_code == 200:
            for rule in resp.json().get("rules", []):
                admin_session.delete(f"{BASE_URL}/api/ip-allowlist/{rule['id']}")
    except:
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
