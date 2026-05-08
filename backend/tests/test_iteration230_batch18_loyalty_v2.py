"""
Iteration 230 - Batch 18: Loyalty Enterprise (Tier Benefits + Referral Program + Dynamic Packaging)
Tests for /api/loyalty-v2/* endpoints

Endpoints tested:
- GET /api/loyalty-v2/benefits/{property_id} - List tier benefits (auto-seeds 4 tiers)
- PUT /api/loyalty-v2/benefits/{property_id}/{tier} - Update tier benefit
- POST /api/loyalty-v2/benefits/apply/{booking_id} - Apply benefits to booking
- POST /api/loyalty-v2/referrals - Create referral code
- GET /api/loyalty-v2/referrals/{property_id} - List referrals with KPIs
- POST /api/loyalty-v2/referrals/claim - Claim referral code
- GET /api/loyalty-v2/packages/{property_id} - List packages with savings
- POST /api/loyalty-v2/packages/{property_id}/seed-defaults - Seed 3 default packages
- POST /api/loyalty-v2/packages - Create package
- PUT /api/loyalty-v2/packages/{package_id} - Update package
- DELETE /api/loyalty-v2/packages/{package_id} - Delete package
"""

import pytest
import requests
import os
import uuid
from datetime import datetime

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

@pytest.fixture(scope="module")
def auth_token():
    """Get auth token for admin user"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@hotelbox.com",
        "password": "HotelAdmin2026!"
    })
    if response.status_code == 200:
        return response.cookies.get("access_token") or response.json().get("access_token")
    pytest.skip("Authentication failed")

@pytest.fixture(scope="module")
def auth_session(auth_token):
    """Create authenticated session"""
    session = requests.Session()
    session.cookies.set("access_token", auth_token)
    session.headers.update({"Content-Type": "application/json"})
    return session

@pytest.fixture(scope="module")
def test_guest_id(auth_session):
    """Create or get a test guest for referral tests"""
    # First try to get existing guests
    response = auth_session.get(f"{BASE_URL}/api/guest-profiles/default")
    if response.status_code == 200:
        guests = response.json().get("guests", [])
        if guests:
            return guests[0].get("id")
    
    # Create a test guest if none exist
    guest_data = {
        "property_id": "default",
        "first_name": "TEST_Referrer",
        "last_name": "Guest",
        "email": f"test_referrer_{uuid.uuid4().hex[:6]}@test.com",
        "phone": "+905551234567",
        "loyalty_tier": "gold"
    }
    response = auth_session.post(f"{BASE_URL}/api/guest-profiles", json=guest_data)
    if response.status_code in [200, 201]:
        return response.json().get("id")
    pytest.skip("Could not create test guest")

@pytest.fixture(scope="module")
def test_booking_id(auth_session, test_guest_id):
    """Create or get a test booking for benefits apply tests"""
    # First try to get existing bookings
    response = auth_session.get(f"{BASE_URL}/api/bookings?property_id=default&limit=5")
    if response.status_code == 200:
        bookings = response.json().get("bookings", [])
        if bookings:
            return bookings[0].get("id")
    
    # Create a test booking if none exist
    booking_data = {
        "property_id": "default",
        "guest_id": test_guest_id,
        "guest_name": "TEST_Booking Guest",
        "guest_email": f"test_booking_{uuid.uuid4().hex[:6]}@test.com",
        "check_in": "2026-02-01",
        "check_out": "2026-02-03",
        "room_type_id": "double-default",
        "total_price": 200.00,
        "status": "confirmed"
    }
    response = auth_session.post(f"{BASE_URL}/api/bookings", json=booking_data)
    if response.status_code in [200, 201]:
        return response.json().get("id")
    pytest.skip("Could not create test booking")


class TestTierBenefits:
    """Tests for Tier Benefits endpoints"""
    
    def test_get_benefits_default_seeds_4_tiers(self, auth_session):
        """GET /api/loyalty-v2/benefits/default → 200, benefits[] seeded with 4 tiers"""
        response = auth_session.get(f"{BASE_URL}/api/loyalty-v2/benefits/default")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "benefits" in data, "Response should have 'benefits' key"
        benefits = data["benefits"]
        
        # Should have 4 tiers
        assert len(benefits) >= 4, f"Expected at least 4 tiers, got {len(benefits)}"
        
        # Check tier order: bronze → silver → gold → platinum
        tier_names = [b["tier"] for b in benefits[:4]]
        assert tier_names == ["bronze", "silver", "gold", "platinum"], f"Tiers not in order: {tier_names}"
        
        # Check each tier has required fields
        for benefit in benefits[:4]:
            assert "tier" in benefit
            assert "property_id" in benefit
            # 6 boolean perks
            assert "early_check_in" in benefit
            assert "late_check_out" in benefit
            assert "room_upgrade" in benefit
            assert "free_breakfast" in benefit
            assert "welcome_amenity" in benefit
            assert "birthday_gift" in benefit
            # 2 numeric perks
            assert "fnb_discount_pct" in benefit
            assert "spa_discount_pct" in benefit
        
        print(f"✓ GET /api/loyalty-v2/benefits/default → 200 with {len(benefits)} tiers in correct order")
    
    def test_bronze_has_minimal_perks(self, auth_session):
        """Bronze tier should have minimal perks"""
        response = auth_session.get(f"{BASE_URL}/api/loyalty-v2/benefits/default")
        assert response.status_code == 200
        
        benefits = response.json()["benefits"]
        bronze = next((b for b in benefits if b["tier"] == "bronze"), None)
        assert bronze is not None, "Bronze tier not found"
        
        # Bronze should have minimal perks (mostly false/0)
        assert bronze.get("early_check_in") == False
        assert bronze.get("late_check_out") == False
        assert bronze.get("room_upgrade") == False
        assert bronze.get("free_breakfast") == False
        assert bronze.get("fnb_discount_pct", 0) == 0
        assert bronze.get("spa_discount_pct", 0) == 0
        # Bronze has birthday_gift as true by default
        assert bronze.get("birthday_gift") == True
        
        print("✓ Bronze tier has minimal perks as expected")
    
    def test_platinum_has_all_perks_and_20_percent(self, auth_session):
        """Platinum tier should have all perks + 20% discounts"""
        response = auth_session.get(f"{BASE_URL}/api/loyalty-v2/benefits/default")
        assert response.status_code == 200
        
        benefits = response.json()["benefits"]
        platinum = next((b for b in benefits if b["tier"] == "platinum"), None)
        assert platinum is not None, "Platinum tier not found"
        
        # Platinum should have all perks
        assert platinum.get("early_check_in") == True
        assert platinum.get("late_check_out") == True
        assert platinum.get("room_upgrade") == True
        assert platinum.get("free_breakfast") == True
        assert platinum.get("welcome_amenity") == True
        assert platinum.get("birthday_gift") == True
        # 20% discounts
        assert platinum.get("fnb_discount_pct") == 20
        assert platinum.get("spa_discount_pct") == 20
        
        print("✓ Platinum tier has all perks + 20% discounts")
    
    def test_update_gold_tier_benefit(self, auth_session):
        """PUT /api/loyalty-v2/benefits/default/gold → 200, subsequent GET shows change"""
        # First get current gold benefits
        response = auth_session.get(f"{BASE_URL}/api/loyalty-v2/benefits/default")
        assert response.status_code == 200
        benefits = response.json()["benefits"]
        gold = next((b for b in benefits if b["tier"] == "gold"), None)
        assert gold is not None
        
        original_room_upgrade = gold.get("room_upgrade", True)
        
        # Update gold tier - toggle room_upgrade
        update_data = {
            "property_id": "default",
            "tier": "gold",
            "room_upgrade": not original_room_upgrade
        }
        response = auth_session.put(f"{BASE_URL}/api/loyalty-v2/benefits/default/gold", json=update_data)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Verify change persisted
        response = auth_session.get(f"{BASE_URL}/api/loyalty-v2/benefits/default")
        assert response.status_code == 200
        benefits = response.json()["benefits"]
        gold_updated = next((b for b in benefits if b["tier"] == "gold"), None)
        assert gold_updated.get("room_upgrade") == (not original_room_upgrade), "room_upgrade should be toggled"
        
        # Restore original value
        update_data["room_upgrade"] = original_room_upgrade
        auth_session.put(f"{BASE_URL}/api/loyalty-v2/benefits/default/gold", json=update_data)
        
        print("✓ PUT /api/loyalty-v2/benefits/default/gold → 200, change persisted")


class TestBenefitsApply:
    """Tests for applying benefits to bookings"""
    
    def test_apply_benefits_to_valid_booking(self, auth_session, test_booking_id):
        """POST /api/loyalty-v2/benefits/apply/{booking_id} → 200 with booking_id, tier, applied[]"""
        response = auth_session.post(f"{BASE_URL}/api/loyalty-v2/benefits/apply/{test_booking_id}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "booking_id" in data, "Response should have 'booking_id'"
        assert "tier" in data, "Response should have 'tier'"
        assert "applied" in data, "Response should have 'applied'"
        assert isinstance(data["applied"], list), "'applied' should be a list"
        
        # Each applied item should have 'perk' string
        for item in data["applied"]:
            assert "perk" in item, f"Applied item should have 'perk': {item}"
            assert isinstance(item["perk"], str), "'perk' should be a string"
        
        print(f"✓ POST /api/loyalty-v2/benefits/apply/{test_booking_id} → 200 with tier={data['tier']}, {len(data['applied'])} perks applied")
    
    def test_apply_benefits_invalid_booking_404(self, auth_session):
        """POST /api/loyalty-v2/benefits/apply/{invalid_id} → 404"""
        invalid_id = "nonexistent-booking-id-12345"
        response = auth_session.post(f"{BASE_URL}/api/loyalty-v2/benefits/apply/{invalid_id}")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"
        
        print("✓ POST /api/loyalty-v2/benefits/apply/{invalid_id} → 404")


class TestReferralProgram:
    """Tests for Referral Program endpoints"""
    
    def test_create_referral_code(self, auth_session, test_guest_id):
        """POST /api/loyalty-v2/referrals → 200 with code starting 'REF', expires_at, active:true"""
        referral_data = {
            "property_id": "default",
            "referrer_guest_id": test_guest_id,
            "benefit_for_referee_pct": 15,
            "benefit_for_referrer_points": 500
        }
        response = auth_session.post(f"{BASE_URL}/api/loyalty-v2/referrals", json=referral_data)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "code" in data, "Response should have 'code'"
        assert data["code"].startswith("REF"), f"Code should start with 'REF': {data['code']}"
        assert "expires_at" in data, "Response should have 'expires_at'"
        assert data.get("active") == True, "Referral should be active"
        assert data.get("benefit_for_referee_pct") == 15
        assert data.get("benefit_for_referrer_points") == 500
        
        # Store for later tests
        TestReferralProgram.created_code = data["code"]
        
        print(f"✓ POST /api/loyalty-v2/referrals → 200 with code={data['code']}, active=true")
    
    def test_create_referral_invalid_guest_404(self, auth_session):
        """POST /api/loyalty-v2/referrals with invalid guest → 404"""
        referral_data = {
            "property_id": "default",
            "referrer_guest_id": "nonexistent-guest-id-12345",
            "benefit_for_referee_pct": 10,
            "benefit_for_referrer_points": 500
        }
        response = auth_session.post(f"{BASE_URL}/api/loyalty-v2/referrals", json=referral_data)
        assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"
        
        print("✓ POST /api/loyalty-v2/referrals with invalid guest → 404")
    
    def test_list_referrals_with_kpis(self, auth_session):
        """GET /api/loyalty-v2/referrals/default → 200 with rows[], total_earned_points, total_bookings_generated"""
        response = auth_session.get(f"{BASE_URL}/api/loyalty-v2/referrals/default")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "rows" in data, "Response should have 'rows'"
        assert "total_earned_points" in data, "Response should have 'total_earned_points'"
        assert "total_bookings_generated" in data, "Response should have 'total_bookings_generated'"
        assert isinstance(data["rows"], list)
        
        print(f"✓ GET /api/loyalty-v2/referrals/default → 200 with {len(data['rows'])} rows, {data['total_earned_points']} points, {data['total_bookings_generated']} bookings")
    
    def test_claim_referral_invalid_code_404(self, auth_session, test_booking_id):
        """POST /api/loyalty-v2/referrals/claim with invalid code → 404"""
        claim_data = {
            "code": "INVALID_CODE_12345",
            "booking_id": test_booking_id
        }
        response = auth_session.post(f"{BASE_URL}/api/loyalty-v2/referrals/claim", json=claim_data)
        assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"
        
        print("✓ POST /api/loyalty-v2/referrals/claim with invalid code → 404")
    
    def test_claim_referral_valid_code(self, auth_session, test_booking_id):
        """POST /api/loyalty-v2/referrals/claim → 200 with referee_discount_amount, new_booking_total, referrer_points_awarded"""
        # Use the code created earlier
        code = getattr(TestReferralProgram, 'created_code', None)
        if not code:
            pytest.skip("No referral code created in previous test")
        
        claim_data = {
            "code": code,
            "booking_id": test_booking_id
        }
        response = auth_session.post(f"{BASE_URL}/api/loyalty-v2/referrals/claim", json=claim_data)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "referee_discount_amount" in data, "Response should have 'referee_discount_amount'"
        assert "new_booking_total" in data, "Response should have 'new_booking_total'"
        assert "referrer_points_awarded" in data, "Response should have 'referrer_points_awarded'"
        
        print(f"✓ POST /api/loyalty-v2/referrals/claim → 200 with discount={data['referee_discount_amount']}, new_total={data['new_booking_total']}, points={data['referrer_points_awarded']}")


class TestDynamicPackaging:
    """Tests for Dynamic Packaging endpoints"""
    
    def test_seed_default_packages(self, auth_session):
        """POST /api/loyalty-v2/packages/default/seed-defaults → 200 with seeded:3 or note"""
        response = auth_session.post(f"{BASE_URL}/api/loyalty-v2/packages/default/seed-defaults")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "seeded" in data, "Response should have 'seeded'"
        
        if data["seeded"] == 0:
            assert "note" in data, "If seeded=0, should have 'note'"
            print(f"✓ POST /api/loyalty-v2/packages/default/seed-defaults → 200 with seeded=0, note={data['note']}")
        else:
            assert data["seeded"] == 3, f"Expected seeded=3, got {data['seeded']}"
            print(f"✓ POST /api/loyalty-v2/packages/default/seed-defaults → 200 with seeded=3")
    
    def test_list_packages_with_savings(self, auth_session):
        """GET /api/loyalty-v2/packages/default → 200 with packages[] having alacarte_total, savings, savings_pct"""
        response = auth_session.get(f"{BASE_URL}/api/loyalty-v2/packages/default")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "packages" in data, "Response should have 'packages'"
        packages = data["packages"]
        
        # Should have at least 3 packages after seeding
        assert len(packages) >= 3, f"Expected at least 3 packages, got {len(packages)}"
        
        # Check expected package names (Turkish)
        package_names = [p["name"] for p in packages]
        expected_names = ["Romantik Kaçamak", "İş Gezisi Kompakt", "Aile Hafta Sonu"]
        for name in expected_names:
            assert name in package_names, f"Expected package '{name}' not found"
        
        # Check each package has computed savings fields
        for pkg in packages:
            assert "alacarte_total" in pkg, f"Package should have 'alacarte_total': {pkg.get('name')}"
            assert "savings" in pkg, f"Package should have 'savings': {pkg.get('name')}"
            assert "savings_pct" in pkg, f"Package should have 'savings_pct': {pkg.get('name')}"
            assert "components" in pkg, f"Package should have 'components': {pkg.get('name')}"
            
            # Verify savings calculation
            if pkg["alacarte_total"] > 0:
                expected_savings = round(pkg["alacarte_total"] - pkg["package_price"], 2)
                assert abs(pkg["savings"] - expected_savings) < 0.01, f"Savings mismatch for {pkg['name']}"
        
        print(f"✓ GET /api/loyalty-v2/packages/default → 200 with {len(packages)} packages, all have savings computed")
    
    def test_create_package(self, auth_session):
        """POST /api/loyalty-v2/packages → 200 with id"""
        package_data = {
            "property_id": "default",
            "name": "TEST_Package",
            "description": "Test package for automated testing",
            "active": True,
            "components": [
                {"type": "room", "name": "Test Room", "alacarte_price": 100, "qty": 1},
                {"type": "fnb", "name": "Test Breakfast", "alacarte_price": 20, "qty": 1}
            ],
            "package_price": 99,
            "currency": "GBP"
        }
        response = auth_session.post(f"{BASE_URL}/api/loyalty-v2/packages", json=package_data)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "id" in data, "Response should have 'id'"
        assert data["name"] == "TEST_Package"
        
        # Store for later tests
        TestDynamicPackaging.created_package_id = data["id"]
        
        print(f"✓ POST /api/loyalty-v2/packages → 200 with id={data['id']}")
    
    def test_update_package(self, auth_session):
        """PUT /api/loyalty-v2/packages/{id} → 200"""
        package_id = getattr(TestDynamicPackaging, 'created_package_id', None)
        if not package_id:
            pytest.skip("No package created in previous test")
        
        update_data = {
            "property_id": "default",
            "name": "TEST_Package_Updated",
            "description": "Updated test package",
            "active": False,
            "components": [
                {"type": "room", "name": "Test Room", "alacarte_price": 100, "qty": 1}
            ],
            "package_price": 89,
            "currency": "GBP"
        }
        response = auth_session.put(f"{BASE_URL}/api/loyalty-v2/packages/{package_id}", json=update_data)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("updated") == True
        
        print(f"✓ PUT /api/loyalty-v2/packages/{package_id} → 200")
    
    def test_update_package_invalid_id_404(self, auth_session):
        """PUT /api/loyalty-v2/packages/{invalid_id} → 404"""
        invalid_id = "nonexistent-package-id-12345"
        update_data = {
            "property_id": "default",
            "name": "Test",
            "components": [],
            "package_price": 100
        }
        response = auth_session.put(f"{BASE_URL}/api/loyalty-v2/packages/{invalid_id}", json=update_data)
        assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"
        
        print("✓ PUT /api/loyalty-v2/packages/{invalid_id} → 404")
    
    def test_delete_package(self, auth_session):
        """DELETE /api/loyalty-v2/packages/{id} → 200"""
        package_id = getattr(TestDynamicPackaging, 'created_package_id', None)
        if not package_id:
            pytest.skip("No package created in previous test")
        
        response = auth_session.delete(f"{BASE_URL}/api/loyalty-v2/packages/{package_id}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("deleted") == True
        
        print(f"✓ DELETE /api/loyalty-v2/packages/{package_id} → 200")
    
    def test_delete_package_invalid_id_404(self, auth_session):
        """DELETE /api/loyalty-v2/packages/{invalid_id} → 404"""
        invalid_id = "nonexistent-package-id-12345"
        response = auth_session.delete(f"{BASE_URL}/api/loyalty-v2/packages/{invalid_id}")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"
        
        print("✓ DELETE /api/loyalty-v2/packages/{invalid_id} → 404")


class TestRegressionBatch17:
    """Regression tests for previous batches"""
    
    def test_kds_stream_still_works(self, auth_session):
        """Batch 17: GET /api/kds/default still works"""
        response = auth_session.get(f"{BASE_URL}/api/kds/default")
        assert response.status_code == 200, f"KDS endpoint failed: {response.status_code}"
        print("✓ Regression: Batch 17 KDS endpoint working")
    
    def test_channel_revenue_still_works(self, auth_session):
        """Batch 16: GET /api/channel-revenue/default still works"""
        response = auth_session.get(f"{BASE_URL}/api/channel-revenue/default")
        assert response.status_code == 200, f"Channel revenue endpoint failed: {response.status_code}"
        print("✓ Regression: Batch 16 Channel Revenue endpoint working")
    
    def test_eu_compliance_still_works(self, auth_session):
        """Batch 15: GET /api/eu-compliance/catalog still works"""
        response = auth_session.get(f"{BASE_URL}/api/eu-compliance/catalog")
        assert response.status_code == 200, f"EU Compliance endpoint failed: {response.status_code}"
        print("✓ Regression: Batch 15 EU Compliance endpoint working")
    
    def test_ai_predictions_still_works(self, auth_session):
        """Batch 14: GET /api/ai-predictions/cancel-risk/default still works"""
        response = auth_session.get(f"{BASE_URL}/api/ai-predictions/cancel-risk/default")
        assert response.status_code == 200, f"AI Predictions endpoint failed: {response.status_code}"
        print("✓ Regression: Batch 14 AI Predictions endpoint working")
    
    def test_tr_compliance_still_works(self, auth_session):
        """Batch 13: GET /api/tr-compliance/kbs/history/default still works"""
        response = auth_session.get(f"{BASE_URL}/api/tr-compliance/kbs/history/default")
        assert response.status_code == 200, f"TR Compliance endpoint failed: {response.status_code}"
        print("✓ Regression: Batch 13 TR Compliance endpoint working")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
