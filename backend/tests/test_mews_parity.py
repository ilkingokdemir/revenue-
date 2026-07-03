"""
Test suite for Mews-parity AI features (iter 356):
1. Smart Tips - POST /api/mews-ai/smart-tips
2. Duplicate Guest Auto-Merge - GET /api/mews-ai/duplicate-guests, POST /api/mews-ai/merge-guests
3. BI AI Summary - POST /api/mews-ai/bi-summary
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

@pytest.fixture(scope="module")
def auth_token():
    """Get admin auth token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@hotelbox.com",
        "password": "HotelAdmin2026!"
    })
    if response.status_code == 200:
        data = response.json()
        # Token can be in 'token' or 'access_token' field
        return data.get("token") or data.get("access_token")
    pytest.skip("Authentication failed - skipping tests")

@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Headers with auth token"""
    return {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json"
    }


class TestSmartTips:
    """Test POST /api/mews-ai/smart-tips endpoint"""
    
    def test_smart_tips_with_inline_profile_vip(self, auth_headers):
        """Test smart tips with inline VIP profile - should return at least 3 tips"""
        payload = {
            "profile": {
                "first_name": "John",
                "last_name": "Smith",
                "tags": ["VIP", "business"],
                "preferences": "quiet room, early breakfast",
                "notes": "Returning guest, prefers high floor"
            }
        }
        response = requests.post(
            f"{BASE_URL}/api/mews-ai/smart-tips",
            json=payload,
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "tips" in data, "Response should contain 'tips' array"
        assert "model" in data, "Response should contain 'model' field"
        assert "generated_at" in data, "Response should contain 'generated_at' field"
        
        # Verify at least 3 tips returned
        tips = data["tips"]
        assert len(tips) >= 3, f"Expected at least 3 tips, got {len(tips)}"
        
        # Verify tip structure
        for tip in tips:
            assert "icon" in tip, "Each tip should have 'icon'"
            assert "title" in tip, "Each tip should have 'title'"
            assert "action" in tip, "Each tip should have 'action'"
        
        # Verify model is either gpt-4o-mini or fallback
        assert data["model"] in ["gpt-4o-mini", "fallback"], f"Unexpected model: {data['model']}"
        print(f"✓ Smart tips returned {len(tips)} tips via {data['model']}")
    
    def test_smart_tips_with_minimal_profile(self, auth_headers):
        """Test smart tips with minimal profile - should still return tips (fallback)"""
        payload = {
            "profile": {
                "first_name": "Jane",
                "last_name": "Doe"
            }
        }
        response = requests.post(
            f"{BASE_URL}/api/mews-ai/smart-tips",
            json=payload,
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Should still return at least 1 tip (fallback)
        assert len(data["tips"]) >= 1, "Should return at least 1 tip even with minimal profile"
        print(f"✓ Minimal profile returned {len(data['tips'])} tips")
    
    def test_smart_tips_missing_profile_and_guest_id(self, auth_headers):
        """Test smart tips with neither guest_id nor profile - should return 400"""
        payload = {}
        response = requests.post(
            f"{BASE_URL}/api/mews-ai/smart-tips",
            json=payload,
            headers=auth_headers
        )
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("✓ Missing profile/guest_id correctly returns 400")
    
    def test_smart_tips_with_nonexistent_guest_id(self, auth_headers):
        """Test smart tips with non-existent guest_id - should return 404"""
        payload = {"guest_id": "nonexistent-guest-id-12345"}
        response = requests.post(
            f"{BASE_URL}/api/mews-ai/smart-tips",
            json=payload,
            headers=auth_headers
        )
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ Non-existent guest_id correctly returns 404")
    
    def test_smart_tips_unauthorized(self):
        """Test smart tips without auth - should return 401"""
        payload = {"profile": {"first_name": "Test"}}
        response = requests.post(
            f"{BASE_URL}/api/mews-ai/smart-tips",
            json=payload
        )
        
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ Unauthorized request correctly returns 401")


class TestDuplicateGuests:
    """Test GET /api/mews-ai/duplicate-guests endpoint"""
    
    def test_find_duplicates_basic(self, auth_headers):
        """Test finding duplicate guests - verify response structure"""
        response = requests.get(
            f"{BASE_URL}/api/mews-ai/duplicate-guests?limit=50",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "total_guests_scanned" in data, "Response should contain 'total_guests_scanned'"
        assert "clusters_found" in data, "Response should contain 'clusters_found'"
        assert "clusters" in data, "Response should contain 'clusters' array"
        assert "generated_at" in data, "Response should contain 'generated_at'"
        
        print(f"✓ Scanned {data['total_guests_scanned']} guests, found {data['clusters_found']} clusters")
        
        # Verify cluster structure if any found
        if data["clusters"]:
            cluster = data["clusters"][0]
            assert "cluster_id" in cluster, "Cluster should have 'cluster_id'"
            assert "reason" in cluster, "Cluster should have 'reason'"
            assert "size" in cluster, "Cluster should have 'size'"
            assert "guests" in cluster, "Cluster should have 'guests' array"
            
            # Each cluster should have at least 2 guests
            assert cluster["size"] >= 2, f"Cluster size should be >= 2, got {cluster['size']}"
            assert len(cluster["guests"]) >= 2, f"Cluster should have >= 2 guests"
            
            # Verify reason string format
            reason = cluster["reason"]
            assert isinstance(reason, str) and len(reason) > 0, "Reason should be non-empty string"
            print(f"✓ First cluster reason: '{reason}' with {cluster['size']} guests")
    
    def test_find_duplicates_with_limit(self, auth_headers):
        """Test duplicate guests with custom limit"""
        response = requests.get(
            f"{BASE_URL}/api/mews-ai/duplicate-guests?limit=5",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should respect limit
        assert len(data["clusters"]) <= 5, f"Should return at most 5 clusters, got {len(data['clusters'])}"
        print(f"✓ Limit=5 returned {len(data['clusters'])} clusters")
    
    def test_find_duplicates_unauthorized(self):
        """Test duplicate guests without auth - should return 401"""
        response = requests.get(f"{BASE_URL}/api/mews-ai/duplicate-guests")
        
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ Unauthorized request correctly returns 401")


class TestMergeGuests:
    """Test POST /api/mews-ai/merge-guests endpoint"""
    
    def test_merge_guests_missing_params(self, auth_headers):
        """Test merge with missing parameters - should return 400"""
        # Missing duplicate_ids
        response = requests.post(
            f"{BASE_URL}/api/mews-ai/merge-guests",
            json={"primary_id": "some-id"},
            headers=auth_headers
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        
        # Missing primary_id
        response = requests.post(
            f"{BASE_URL}/api/mews-ai/merge-guests",
            json={"duplicate_ids": ["id1", "id2"]},
            headers=auth_headers
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        
        # Empty duplicate_ids
        response = requests.post(
            f"{BASE_URL}/api/mews-ai/merge-guests",
            json={"primary_id": "some-id", "duplicate_ids": []},
            headers=auth_headers
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        
        print("✓ Missing/empty params correctly return 400")
    
    def test_merge_guests_primary_in_duplicates(self, auth_headers):
        """Test merge with primary_id in duplicate_ids - should return 400"""
        response = requests.post(
            f"{BASE_URL}/api/mews-ai/merge-guests",
            json={
                "primary_id": "guest-123",
                "duplicate_ids": ["guest-123", "guest-456"]
            },
            headers=auth_headers
        )
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("✓ Primary in duplicates correctly returns 400")
    
    def test_merge_guests_nonexistent_primary(self, auth_headers):
        """Test merge with non-existent primary - should return 404"""
        response = requests.post(
            f"{BASE_URL}/api/mews-ai/merge-guests",
            json={
                "primary_id": "nonexistent-primary-id",
                "duplicate_ids": ["dup-1", "dup-2"]
            },
            headers=auth_headers
        )
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ Non-existent primary correctly returns 404")
    
    def test_merge_guests_with_real_cluster(self, auth_headers):
        """Test merge using a real duplicate cluster from find-duplicates"""
        # First, get duplicate clusters
        find_response = requests.get(
            f"{BASE_URL}/api/mews-ai/duplicate-guests?limit=50",
            headers=auth_headers
        )
        
        if find_response.status_code != 200:
            pytest.skip("Could not fetch duplicate clusters")
        
        clusters = find_response.json().get("clusters", [])
        if not clusters:
            pytest.skip("No duplicate clusters found to test merge")
        
        # Use first cluster
        cluster = clusters[0]
        guests = cluster["guests"]
        
        if len(guests) < 2:
            pytest.skip("Cluster has less than 2 guests")
        
        primary_id = guests[0]["id"]
        duplicate_ids = [g["id"] for g in guests[1:]]
        
        print(f"Testing merge: primary={primary_id}, duplicates={duplicate_ids}")
        
        # Perform merge
        merge_response = requests.post(
            f"{BASE_URL}/api/mews-ai/merge-guests",
            json={
                "primary_id": primary_id,
                "duplicate_ids": duplicate_ids
            },
            headers=auth_headers
        )
        
        assert merge_response.status_code == 200, f"Expected 200, got {merge_response.status_code}: {merge_response.text}"
        data = merge_response.json()
        
        # Verify response structure
        assert data.get("ok") == True, "Response should have ok=True"
        assert "primary_id" in data, "Response should contain 'primary_id'"
        assert "removed_dupes" in data, "Response should contain 'removed_dupes'"
        assert "moved_bookings" in data, "Response should contain 'moved_bookings'"
        
        print(f"✓ Merge successful: removed {data['removed_dupes']} dupes, moved {data['moved_bookings']} bookings")
    
    def test_merge_guests_unauthorized(self):
        """Test merge without auth - should return 401"""
        response = requests.post(
            f"{BASE_URL}/api/mews-ai/merge-guests",
            json={"primary_id": "id1", "duplicate_ids": ["id2"]}
        )
        
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ Unauthorized request correctly returns 401")


class TestBiAiSummary:
    """Test POST /api/mews-ai/bi-summary endpoint"""
    
    def test_bi_summary_camden_suites(self, auth_headers):
        """Test BI summary for camden-suites property"""
        payload = {"property_id": "camden-suites"}
        
        # Allow extra time for LLM response
        response = requests.post(
            f"{BASE_URL}/api/mews-ai/bi-summary",
            json=payload,
            headers=auth_headers,
            timeout=60
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "summary_md" in data, "Response should contain 'summary_md'"
        assert "snapshot" in data, "Response should contain 'snapshot'"
        assert "model" in data, "Response should contain 'model'"
        assert "generated_at" in data, "Response should contain 'generated_at'"
        
        summary = data["summary_md"]
        snapshot = data["snapshot"]
        
        # Verify summary contains emoji bullets or action line
        has_emoji = any(c in summary for c in ["📈", "📉", "⚠️", "💡", "🎯", "📊", "💰", "📁"])
        has_action = "ÖNCELİK" in summary.upper() or "HAFTA" in summary.upper() or "öneri" in summary.lower()
        
        assert has_emoji or has_action, f"Summary should contain emoji bullets or action line. Got: {summary[:200]}"
        
        # Verify snapshot structure
        assert "property_name" in snapshot, "Snapshot should contain 'property_name'"
        assert "currency" in snapshot, "Snapshot should contain 'currency'"
        assert "bookings_last_30d" in snapshot, "Snapshot should contain 'bookings_last_30d'"
        assert "bookings_delta_pct" in snapshot, "Snapshot should contain 'bookings_delta_pct'"
        
        print(f"✓ BI Summary generated via {data['model']}")
        print(f"  Property: {snapshot['property_name']}")
        print(f"  Last 30d bookings: {snapshot['bookings_last_30d']} ({snapshot['bookings_delta_pct']}% delta)")
        print(f"  Summary preview: {summary[:150]}...")
    
    def test_bi_summary_missing_property_id(self, auth_headers):
        """Test BI summary without property_id - should return 400"""
        response = requests.post(
            f"{BASE_URL}/api/mews-ai/bi-summary",
            json={},
            headers=auth_headers
        )
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("✓ Missing property_id correctly returns 400")
    
    def test_bi_summary_unauthorized(self):
        """Test BI summary without auth - should return 401"""
        response = requests.post(
            f"{BASE_URL}/api/mews-ai/bi-summary",
            json={"property_id": "camden-suites"}
        )
        
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ Unauthorized request correctly returns 401")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
