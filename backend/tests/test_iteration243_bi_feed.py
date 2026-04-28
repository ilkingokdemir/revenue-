"""
Iteration 243 — Enterprise BI Feed: OData v4 + Tableau WDC + CSV Download
Tests for:
- POST /api/bi/tokens (admin) - create token
- GET /api/bi/tokens/{property_id} (admin) - list tokens with masked values
- DELETE /api/bi/tokens/{token_id} (admin) - soft revoke
- GET /api/bi/odata?token=X (PUBLIC) - service catalog
- GET /api/bi/odata/$metadata?token=X - XML EDM metadata
- GET /api/bi/odata/{Entity}?token=X - entity collection with $top, $skip, $filter
- GET /api/bi/csv/{Entity}?token=X - RFC 4180 CSV download
- GET /api/bi/tableau-wdc.html - Tableau Web Data Connector HTML
- GET /api/bi/sample-urls/{token_id} (admin) - connection URL examples
"""
import pytest
import requests
import os
import uuid
from datetime import datetime

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"
TEST_PROPERTY_ID = "aldgate-flats"

VALID_ENTITIES = ["Bookings", "Tips", "FnbTabs", "Inquiries", "CleanlinessScores", "WorkOrders"]


@pytest.fixture(scope="module")
def admin_session():
    """Login as admin and return session with cookies"""
    session = requests.Session()
    resp = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    assert resp.status_code == 200, f"Admin login failed: {resp.text}"
    return session


@pytest.fixture(scope="module")
def created_token(admin_session):
    """Create a test token and return its data"""
    resp = admin_session.post(f"{BASE_URL}/api/bi/tokens", json={
        "property_id": TEST_PROPERTY_ID,
        "name": f"TEST_BiToken_{uuid.uuid4().hex[:8]}",
        "expires_days": 30
    })
    assert resp.status_code == 200, f"Token creation failed: {resp.text}"
    data = resp.json()
    assert "token" in data
    assert data["token"].startswith("hbk_")
    return data


class TestBiTokenManagement:
    """Token CRUD operations (admin only)"""

    def test_create_token_requires_auth(self):
        """POST /api/bi/tokens without auth returns 401"""
        resp = requests.post(f"{BASE_URL}/api/bi/tokens", json={
            "property_id": TEST_PROPERTY_ID,
            "name": "Unauthorized Token",
            "expires_days": 30
        })
        assert resp.status_code == 401
        print("✓ Token creation requires authentication")

    def test_create_token_success(self, admin_session):
        """POST /api/bi/tokens creates token with hbk_ prefix"""
        resp = admin_session.post(f"{BASE_URL}/api/bi/tokens", json={
            "property_id": TEST_PROPERTY_ID,
            "name": f"TEST_PowerBI_{uuid.uuid4().hex[:6]}",
            "expires_days": 365
        })
        assert resp.status_code == 200
        data = resp.json()
        
        # Verify token format
        assert "token" in data
        assert data["token"].startswith("hbk_")
        assert len(data["token"]) == 36  # hbk_ + 32 hex chars
        
        # Verify other fields
        assert data["name"].startswith("TEST_PowerBI_")
        assert data["property_id"] == TEST_PROPERTY_ID
        assert data["revoked"] == False
        assert data["use_count"] == 0
        assert "id" in data
        assert "created_at" in data
        assert "expires_at" in data
        print(f"✓ Token created: {data['token'][:10]}...")

    def test_create_token_invalid_expires_days_low(self, admin_session):
        """POST /api/bi/tokens with expires_days < 1 returns 400"""
        resp = admin_session.post(f"{BASE_URL}/api/bi/tokens", json={
            "property_id": TEST_PROPERTY_ID,
            "name": "Invalid Token",
            "expires_days": 0
        })
        assert resp.status_code == 400
        assert "1..3650" in resp.text
        print("✓ expires_days < 1 rejected")

    def test_create_token_invalid_expires_days_high(self, admin_session):
        """POST /api/bi/tokens with expires_days > 3650 returns 400"""
        resp = admin_session.post(f"{BASE_URL}/api/bi/tokens", json={
            "property_id": TEST_PROPERTY_ID,
            "name": "Invalid Token",
            "expires_days": 4000
        })
        assert resp.status_code == 400
        assert "1..3650" in resp.text
        print("✓ expires_days > 3650 rejected")

    def test_create_token_empty_name(self, admin_session):
        """POST /api/bi/tokens with empty name returns 400"""
        resp = admin_session.post(f"{BASE_URL}/api/bi/tokens", json={
            "property_id": TEST_PROPERTY_ID,
            "name": "   ",
            "expires_days": 30
        })
        assert resp.status_code == 400
        assert "name" in resp.text.lower()
        print("✓ Empty name rejected")

    def test_list_tokens_requires_auth(self):
        """GET /api/bi/tokens/{property_id} without auth returns 401"""
        resp = requests.get(f"{BASE_URL}/api/bi/tokens/{TEST_PROPERTY_ID}")
        assert resp.status_code == 401
        print("✓ Token listing requires authentication")

    def test_list_tokens_success(self, admin_session, created_token):
        """GET /api/bi/tokens/{property_id} returns list with masked tokens"""
        resp = admin_session.get(f"{BASE_URL}/api/bi/tokens/{TEST_PROPERTY_ID}")
        assert resp.status_code == 200
        data = resp.json()
        
        assert "rows" in data
        assert "count" in data
        assert data["count"] >= 1
        
        # Find our created token
        found = False
        for row in data["rows"]:
            if row["id"] == created_token["id"]:
                found = True
                # Verify masking
                assert "token_masked" in row
                assert "..." in row["token_masked"]
                # First 6 chars + ... + last 4 chars
                assert row["token_masked"].startswith(created_token["token"][:6])
                assert row["token_masked"].endswith(created_token["token"][-4:])
                break
        
        assert found, "Created token not found in list"
        print(f"✓ Token list returned {data['count']} tokens with masked values")

    def test_revoke_token_requires_auth(self, created_token):
        """DELETE /api/bi/tokens/{token_id} without auth returns 401"""
        resp = requests.delete(f"{BASE_URL}/api/bi/tokens/{created_token['id']}")
        assert resp.status_code == 401
        print("✓ Token revocation requires authentication")

    def test_revoke_token_not_found(self, admin_session):
        """DELETE /api/bi/tokens/{token_id} with invalid ID returns 404"""
        resp = admin_session.delete(f"{BASE_URL}/api/bi/tokens/nonexistent-id")
        assert resp.status_code == 404
        print("✓ Revoke non-existent token returns 404")


class TestODataServiceCatalog:
    """OData v4 service catalog and metadata"""

    def test_odata_root_requires_token(self):
        """GET /api/bi/odata without token returns 401"""
        resp = requests.get(f"{BASE_URL}/api/bi/odata")
        assert resp.status_code == 401
        assert "Token required" in resp.text
        print("✓ OData root requires token")

    def test_odata_root_invalid_token(self):
        """GET /api/bi/odata with invalid token returns 401"""
        resp = requests.get(f"{BASE_URL}/api/bi/odata?token=invalid_token")
        assert resp.status_code == 401
        assert "Invalid token" in resp.text
        print("✓ OData root rejects invalid token")

    def test_odata_root_success(self, created_token):
        """GET /api/bi/odata?token=X returns service catalog with 6 entities"""
        resp = requests.get(f"{BASE_URL}/api/bi/odata?token={created_token['token']}")
        assert resp.status_code == 200
        data = resp.json()
        
        assert "@odata.context" in data
        assert "value" in data
        
        entity_names = [e["name"] for e in data["value"]]
        for entity in VALID_ENTITIES:
            assert entity in entity_names, f"Missing entity: {entity}"
        
        # Verify structure
        for entity in data["value"]:
            assert "name" in entity
            assert "kind" in entity
            assert entity["kind"] == "EntitySet"
            assert "url" in entity
        
        print(f"✓ OData root returned {len(data['value'])} entities: {entity_names}")

    def test_odata_metadata_success(self, created_token):
        """GET /api/bi/odata/$metadata?token=X returns XML EDM v4"""
        resp = requests.get(f"{BASE_URL}/api/bi/odata/$metadata?token={created_token['token']}")
        assert resp.status_code == 200
        assert "application/xml" in resp.headers.get("content-type", "")
        
        content = resp.text
        # Verify EDM v4 structure
        assert '<?xml version="1.0"' in content
        assert 'edmx:Edmx' in content
        assert 'Version="4.0"' in content
        assert 'Namespace="HotelBox"' in content
        
        # Verify entities are defined
        for entity in VALID_ENTITIES:
            assert f'EntityType Name="{entity}"' in content
            assert f'EntitySet Name="{entity}"' in content
        
        print("✓ OData $metadata returned valid XML EDM v4")


class TestODataEntityCollection:
    """OData entity collection queries"""

    def test_entity_unknown_returns_404(self, created_token):
        """GET /api/bi/odata/UnknownEntity returns 404"""
        resp = requests.get(f"{BASE_URL}/api/bi/odata/UnknownEntity?token={created_token['token']}")
        assert resp.status_code == 404
        assert "Unknown entity" in resp.text
        print("✓ Unknown entity returns 404")

    def test_entity_bookings_success(self, created_token):
        """GET /api/bi/odata/Bookings returns collection with proper structure"""
        resp = requests.get(f"{BASE_URL}/api/bi/odata/Bookings?token={created_token['token']}&top=10")
        assert resp.status_code == 200
        data = resp.json()
        
        assert "@odata.context" in data
        assert "@odata.count" in data
        assert "value" in data
        assert isinstance(data["value"], list)
        
        print(f"✓ Bookings entity returned {data['@odata.count']} rows")

    def test_entity_top_parameter(self, created_token):
        """GET /api/bi/odata/Bookings?top=5 limits results"""
        resp = requests.get(f"{BASE_URL}/api/bi/odata/Bookings?token={created_token['token']}&top=5")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["value"]) <= 5
        print("✓ $top parameter limits results")

    def test_entity_top_invalid_low(self, created_token):
        """GET /api/bi/odata/Bookings?top=0 returns 400"""
        resp = requests.get(f"{BASE_URL}/api/bi/odata/Bookings?token={created_token['token']}&top=0")
        assert resp.status_code == 400
        assert "1..5000" in resp.text
        print("✓ $top < 1 rejected")

    def test_entity_top_invalid_high(self, created_token):
        """GET /api/bi/odata/Bookings?top=10000 returns 400"""
        resp = requests.get(f"{BASE_URL}/api/bi/odata/Bookings?token={created_token['token']}&top=10000")
        assert resp.status_code == 400
        assert "1..5000" in resp.text
        print("✓ $top > 5000 rejected")

    def test_entity_skip_parameter(self, created_token):
        """GET /api/bi/odata/Bookings?skip=N works"""
        resp = requests.get(f"{BASE_URL}/api/bi/odata/Bookings?token={created_token['token']}&skip=0&top=10")
        assert resp.status_code == 200
        print("✓ $skip parameter works")

    def test_entity_filter_eq(self, created_token):
        """GET /api/bi/odata/Bookings?filter=status eq 'confirmed' parses correctly"""
        resp = requests.get(f"{BASE_URL}/api/bi/odata/Bookings?token={created_token['token']}&filter=status eq 'confirmed'")
        assert resp.status_code == 200
        data = resp.json()
        # All returned bookings should have status=confirmed (if any)
        for row in data["value"]:
            if "status" in row:
                assert row["status"] == "confirmed"
        print("✓ $filter with eq operator works")

    def test_entity_filter_and_clause(self, created_token):
        """GET /api/bi/odata/Bookings?filter=status eq 'confirmed' and channel eq 'direct' works"""
        resp = requests.get(f"{BASE_URL}/api/bi/odata/Bookings?token={created_token['token']}&filter=status eq 'confirmed' and channel eq 'direct'")
        assert resp.status_code == 200
        print("✓ $filter with 'and' clause works")

    def test_all_entities_accessible(self, created_token):
        """All 6 entities are accessible"""
        for entity in VALID_ENTITIES:
            resp = requests.get(f"{BASE_URL}/api/bi/odata/{entity}?token={created_token['token']}&top=1")
            assert resp.status_code == 200, f"Entity {entity} failed: {resp.text}"
            print(f"  ✓ {entity} accessible")
        print("✓ All 6 entities accessible")

    def test_entity_stamps_usage(self, admin_session, created_token):
        """Entity access stamps last_used_at and increments use_count"""
        # Get initial state
        resp = admin_session.get(f"{BASE_URL}/api/bi/tokens/{TEST_PROPERTY_ID}")
        initial_data = resp.json()
        initial_token = next((t for t in initial_data["rows"] if t["id"] == created_token["id"]), None)
        initial_count = initial_token["use_count"] if initial_token else 0
        
        # Access entity
        requests.get(f"{BASE_URL}/api/bi/odata/Bookings?token={created_token['token']}&top=1")
        
        # Check updated state
        resp = admin_session.get(f"{BASE_URL}/api/bi/tokens/{TEST_PROPERTY_ID}")
        updated_data = resp.json()
        updated_token = next((t for t in updated_data["rows"] if t["id"] == created_token["id"]), None)
        
        assert updated_token is not None
        assert updated_token["use_count"] > initial_count
        assert updated_token["last_used_at"] is not None
        print(f"✓ Token usage stamped: use_count={updated_token['use_count']}")


class TestCsvDownload:
    """CSV download endpoint"""

    def test_csv_requires_token(self):
        """GET /api/bi/csv/Bookings without token returns 401"""
        resp = requests.get(f"{BASE_URL}/api/bi/csv/Bookings")
        assert resp.status_code == 401
        print("✓ CSV download requires token")

    def test_csv_unknown_entity(self, created_token):
        """GET /api/bi/csv/UnknownEntity returns 404"""
        resp = requests.get(f"{BASE_URL}/api/bi/csv/UnknownEntity?token={created_token['token']}")
        assert resp.status_code == 404
        print("✓ CSV unknown entity returns 404")

    def test_csv_download_success(self, created_token):
        """GET /api/bi/csv/Bookings returns RFC 4180 CSV with header"""
        resp = requests.get(f"{BASE_URL}/api/bi/csv/Bookings?token={created_token['token']}")
        assert resp.status_code == 200
        
        # Check content type
        assert "text/csv" in resp.headers.get("content-type", "")
        
        # Check Content-Disposition
        content_disp = resp.headers.get("content-disposition", "")
        assert "attachment" in content_disp
        assert "Bookings" in content_disp
        assert ".csv" in content_disp
        
        # Check CSV structure
        lines = resp.text.strip().split("\n")
        assert len(lines) >= 1  # At least header
        
        # Verify header contains expected fields
        header = lines[0]
        assert "id" in header
        assert "booking_ref" in header or "guest_name" in header
        
        print(f"✓ CSV download returned {len(lines)} lines with proper headers")

    def test_csv_all_entities(self, created_token):
        """All 6 entities support CSV download"""
        for entity in VALID_ENTITIES:
            resp = requests.get(f"{BASE_URL}/api/bi/csv/{entity}?token={created_token['token']}&top=10")
            assert resp.status_code == 200, f"CSV for {entity} failed: {resp.text}"
            assert "text/csv" in resp.headers.get("content-type", "")
            print(f"  ✓ {entity} CSV works")
        print("✓ All 6 entities support CSV download")


class TestTableauWdc:
    """Tableau Web Data Connector"""

    def test_tableau_wdc_no_auth_required(self):
        """GET /api/bi/tableau-wdc.html is public (no auth needed)"""
        resp = requests.get(f"{BASE_URL}/api/bi/tableau-wdc.html")
        assert resp.status_code == 200
        print("✓ Tableau WDC is publicly accessible")

    def test_tableau_wdc_html_structure(self):
        """GET /api/bi/tableau-wdc.html returns valid HTML with WDC 2.3 script"""
        resp = requests.get(f"{BASE_URL}/api/bi/tableau-wdc.html")
        assert resp.status_code == 200
        
        content = resp.text
        assert "text/html" in resp.headers.get("content-type", "")
        
        # Check HTML structure
        assert "<!DOCTYPE html>" in content
        assert "<html>" in content or "<html " in content
        assert "HotelBox" in content
        
        # Check Tableau WDC 2.3 script
        assert "tableauwdc-2.3" in content
        assert "tableau.makeConnector" in content
        assert "tableau.registerConnector" in content
        
        # Check entity options
        for entity in VALID_ENTITIES:
            assert entity in content
        
        # Check token input
        assert 'id="tok"' in content
        assert 'hbk_' in content  # Placeholder hint
        
        print("✓ Tableau WDC HTML contains WDC 2.3 script and all entities")


class TestSampleUrls:
    """Sample URLs endpoint for BI tool connection instructions"""

    def test_sample_urls_requires_auth(self, created_token):
        """GET /api/bi/sample-urls/{token_id} without auth returns 401"""
        resp = requests.get(f"{BASE_URL}/api/bi/sample-urls/{created_token['id']}")
        assert resp.status_code == 401
        print("✓ Sample URLs requires authentication")

    def test_sample_urls_not_found(self, admin_session):
        """GET /api/bi/sample-urls/{token_id} with invalid ID returns 404"""
        resp = admin_session.get(f"{BASE_URL}/api/bi/sample-urls/nonexistent-id")
        assert resp.status_code == 404
        print("✓ Sample URLs for non-existent token returns 404")

    def test_sample_urls_success(self, admin_session, created_token):
        """GET /api/bi/sample-urls/{token_id} returns connection examples"""
        resp = admin_session.get(f"{BASE_URL}/api/bi/sample-urls/{created_token['id']}")
        assert resp.status_code == 200
        data = resp.json()
        
        # Check required fields
        assert "odata_root" in data
        assert "odata_metadata" in data
        assert "csv_examples" in data
        assert "odata_examples" in data
        assert "tableau_wdc" in data
        assert "powerbi_instructions" in data
        assert "excel_instructions" in data
        assert "entities" in data
        
        # Verify URLs contain token
        assert created_token["token"] in data["odata_root"]
        assert created_token["token"] in data["odata_metadata"]
        
        # Verify all entities have examples
        for entity in VALID_ENTITIES:
            assert entity in data["csv_examples"]
            assert entity in data["odata_examples"]
        
        # Verify instructions
        assert len(data["powerbi_instructions"]) >= 2
        assert len(data["excel_instructions"]) >= 2
        
        print("✓ Sample URLs returned all connection examples")


class TestTokenRevocationFlow:
    """Test token revocation and subsequent access denial"""

    def test_revoke_and_deny_access(self, admin_session):
        """Revoked token should be denied access to OData"""
        # Create a new token
        resp = admin_session.post(f"{BASE_URL}/api/bi/tokens", json={
            "property_id": TEST_PROPERTY_ID,
            "name": f"TEST_ToRevoke_{uuid.uuid4().hex[:6]}",
            "expires_days": 30
        })
        assert resp.status_code == 200
        token_data = resp.json()
        token = token_data["token"]
        token_id = token_data["id"]
        
        # Verify token works
        resp = requests.get(f"{BASE_URL}/api/bi/odata?token={token}")
        assert resp.status_code == 200
        print("  ✓ Token works before revocation")
        
        # Revoke token
        resp = admin_session.delete(f"{BASE_URL}/api/bi/tokens/{token_id}")
        assert resp.status_code == 200
        assert resp.json()["revoked"] == True
        print("  ✓ Token revoked")
        
        # Verify token is denied
        resp = requests.get(f"{BASE_URL}/api/bi/odata?token={token}")
        assert resp.status_code == 401
        assert "Invalid token" in resp.text
        print("  ✓ Revoked token denied access")
        
        # Verify token shows as revoked in list
        resp = admin_session.get(f"{BASE_URL}/api/bi/tokens/{TEST_PROPERTY_ID}")
        tokens = resp.json()["rows"]
        revoked_token = next((t for t in tokens if t["id"] == token_id), None)
        assert revoked_token is not None
        assert revoked_token["revoked"] == True
        print("✓ Full revocation flow works correctly")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
