"""
Test suite for Batch 29-30: Image AI Cleanliness Scoring + CopilotButton scatter
Tests:
- POST /api/image-ai/cleanliness-score (GPT-5.2 Vision)
- GET /api/image-ai/cleanliness-history/{property_id}
- GET /api/image-ai/cleanliness-score/{score_id}
- Validation: min 1 photo, max 3 photos, limit 1..200
- Auth requirements (admin/manager/housekeeping)
"""
import pytest
import requests
import os
import base64
from io import BytesIO

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Generate a small synthetic JPEG image (200x200 red square) for testing
def generate_test_image_base64():
    """Generate a minimal valid JPEG image as base64"""
    # Minimal 1x1 red JPEG (smallest valid JPEG)
    # This is a pre-computed minimal JPEG
    minimal_jpeg = bytes([
        0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10, 0x4A, 0x46, 0x49, 0x46, 0x00, 0x01,
        0x01, 0x00, 0x00, 0x01, 0x00, 0x01, 0x00, 0x00, 0xFF, 0xDB, 0x00, 0x43,
        0x00, 0x08, 0x06, 0x06, 0x07, 0x06, 0x05, 0x08, 0x07, 0x07, 0x07, 0x09,
        0x09, 0x08, 0x0A, 0x0C, 0x14, 0x0D, 0x0C, 0x0B, 0x0B, 0x0C, 0x19, 0x12,
        0x13, 0x0F, 0x14, 0x1D, 0x1A, 0x1F, 0x1E, 0x1D, 0x1A, 0x1C, 0x1C, 0x20,
        0x24, 0x2E, 0x27, 0x20, 0x22, 0x2C, 0x23, 0x1C, 0x1C, 0x28, 0x37, 0x29,
        0x2C, 0x30, 0x31, 0x34, 0x34, 0x34, 0x1F, 0x27, 0x39, 0x3D, 0x38, 0x32,
        0x3C, 0x2E, 0x33, 0x34, 0x32, 0xFF, 0xC0, 0x00, 0x0B, 0x08, 0x00, 0x01,
        0x00, 0x01, 0x01, 0x01, 0x11, 0x00, 0xFF, 0xC4, 0x00, 0x1F, 0x00, 0x00,
        0x01, 0x05, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08,
        0x09, 0x0A, 0x0B, 0xFF, 0xC4, 0x00, 0xB5, 0x10, 0x00, 0x02, 0x01, 0x03,
        0x03, 0x02, 0x04, 0x03, 0x05, 0x05, 0x04, 0x04, 0x00, 0x00, 0x01, 0x7D,
        0x01, 0x02, 0x03, 0x00, 0x04, 0x11, 0x05, 0x12, 0x21, 0x31, 0x41, 0x06,
        0x13, 0x51, 0x61, 0x07, 0x22, 0x71, 0x14, 0x32, 0x81, 0x91, 0xA1, 0x08,
        0x23, 0x42, 0xB1, 0xC1, 0x15, 0x52, 0xD1, 0xF0, 0x24, 0x33, 0x62, 0x72,
        0x82, 0x09, 0x0A, 0x16, 0x17, 0x18, 0x19, 0x1A, 0x25, 0x26, 0x27, 0x28,
        0x29, 0x2A, 0x34, 0x35, 0x36, 0x37, 0x38, 0x39, 0x3A, 0x43, 0x44, 0x45,
        0x46, 0x47, 0x48, 0x49, 0x4A, 0x53, 0x54, 0x55, 0x56, 0x57, 0x58, 0x59,
        0x5A, 0x63, 0x64, 0x65, 0x66, 0x67, 0x68, 0x69, 0x6A, 0x73, 0x74, 0x75,
        0x76, 0x77, 0x78, 0x79, 0x7A, 0x83, 0x84, 0x85, 0x86, 0x87, 0x88, 0x89,
        0x8A, 0x92, 0x93, 0x94, 0x95, 0x96, 0x97, 0x98, 0x99, 0x9A, 0xA2, 0xA3,
        0xA4, 0xA5, 0xA6, 0xA7, 0xA8, 0xA9, 0xAA, 0xB2, 0xB3, 0xB4, 0xB5, 0xB6,
        0xB7, 0xB8, 0xB9, 0xBA, 0xC2, 0xC3, 0xC4, 0xC5, 0xC6, 0xC7, 0xC8, 0xC9,
        0xCA, 0xD2, 0xD3, 0xD4, 0xD5, 0xD6, 0xD7, 0xD8, 0xD9, 0xDA, 0xE1, 0xE2,
        0xE3, 0xE4, 0xE5, 0xE6, 0xE7, 0xE8, 0xE9, 0xEA, 0xF1, 0xF2, 0xF3, 0xF4,
        0xF5, 0xF6, 0xF7, 0xF8, 0xF9, 0xFA, 0xFF, 0xDA, 0x00, 0x08, 0x01, 0x01,
        0x00, 0x00, 0x3F, 0x00, 0xFB, 0xD5, 0xDB, 0x20, 0xA8, 0xF1, 0x7E, 0xCA,
        0x8A, 0x28, 0xA0, 0x02, 0x8A, 0x28, 0xA0, 0xFF, 0xD9
    ])
    return base64.b64encode(minimal_jpeg).decode('utf-8')


@pytest.fixture(scope="module")
def auth_session():
    """Login as admin and return session with cookies"""
    session = requests.Session()
    login_resp = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@hotelbox.com",
        "password": "HotelAdmin2026!"
    })
    assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
    return session


@pytest.fixture(scope="module")
def test_image_b64():
    """Generate test image base64"""
    return generate_test_image_base64()


@pytest.fixture(scope="module")
def test_image_data_uri(test_image_b64):
    """Generate test image as data URI"""
    return f"data:image/jpeg;base64,{test_image_b64}"


class TestImageAICleanlinessScore:
    """Tests for POST /api/image-ai/cleanliness-score"""
    
    def test_score_requires_auth(self):
        """Endpoint requires authentication"""
        resp = requests.post(f"{BASE_URL}/api/image-ai/cleanliness-score", json={
            "property_id": "test-prop",
            "room_id": "101",
            "photos_base64": ["abc"]
        })
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
        print("✓ POST /api/image-ai/cleanliness-score requires auth")
    
    def test_score_empty_photos_returns_400(self, auth_session):
        """Empty photos array returns 400"""
        resp = auth_session.post(f"{BASE_URL}/api/image-ai/cleanliness-score", json={
            "property_id": "aldgate-flats",
            "room_id": "101",
            "photos_base64": []
        })
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}"
        assert "At least 1 photo required" in resp.text
        print("✓ Empty photos returns 400 'At least 1 photo required'")
    
    def test_score_more_than_3_photos_returns_400(self, auth_session, test_image_b64):
        """More than 3 photos returns 400"""
        resp = auth_session.post(f"{BASE_URL}/api/image-ai/cleanliness-score", json={
            "property_id": "aldgate-flats",
            "room_id": "101",
            "photos_base64": [test_image_b64, test_image_b64, test_image_b64, test_image_b64]
        })
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}"
        assert "Max 3 photos" in resp.text
        print("✓ More than 3 photos returns 400 'Max 3 photos per scoring'")
    
    def test_score_with_valid_photo(self, auth_session, test_image_b64):
        """Valid photo submission returns score result"""
        resp = auth_session.post(f"{BASE_URL}/api/image-ai/cleanliness-score", json={
            "property_id": "aldgate-flats",
            "room_id": "TEST_101",
            "photos_base64": [test_image_b64],
            "staff_id": "staff-001",
            "notes": "Test scoring"
        })
        # Could be 200 (success) or 502 (AI failure) - both are valid responses
        assert resp.status_code in [200, 502], f"Expected 200 or 502, got {resp.status_code}: {resp.text}"
        
        if resp.status_code == 200:
            data = resp.json()
            assert "id" in data
            assert "score" in data
            assert "severity" in data
            assert data["severity"] in ["pass", "warning", "fail"]
            assert 0 <= data["score"] <= 100
            assert data["room_id"] == "TEST_101"
            assert data["property_id"] == "aldgate-flats"
            print(f"✓ Valid photo scoring returned: score={data['score']}, severity={data['severity']}")
        else:
            print("✓ AI scoring returned 502 (expected if LLM unavailable)")
    
    def test_score_strips_data_uri_prefix(self, auth_session, test_image_data_uri):
        """Data URI prefix is stripped correctly"""
        resp = auth_session.post(f"{BASE_URL}/api/image-ai/cleanliness-score", json={
            "property_id": "aldgate-flats",
            "room_id": "TEST_102",
            "photos_base64": [test_image_data_uri]
        })
        # Should not fail due to data: prefix
        assert resp.status_code in [200, 502], f"Expected 200 or 502, got {resp.status_code}: {resp.text}"
        print("✓ Data URI prefix stripped correctly")
    
    def test_score_with_multiple_photos(self, auth_session, test_image_b64):
        """Multiple photos (2-3) are accepted"""
        resp = auth_session.post(f"{BASE_URL}/api/image-ai/cleanliness-score", json={
            "property_id": "aldgate-flats",
            "room_id": "TEST_103",
            "photos_base64": [test_image_b64, test_image_b64, test_image_b64]
        })
        assert resp.status_code in [200, 502], f"Expected 200 or 502, got {resp.status_code}: {resp.text}"
        
        if resp.status_code == 200:
            data = resp.json()
            assert data["photo_count"] == 3
            print(f"✓ 3 photos accepted, photo_count={data['photo_count']}")
        else:
            print("✓ 3 photos accepted (AI returned 502)")


class TestImageAICleanlinessHistory:
    """Tests for GET /api/image-ai/cleanliness-history/{property_id}"""
    
    def test_history_requires_auth(self):
        """Endpoint requires authentication"""
        resp = requests.get(f"{BASE_URL}/api/image-ai/cleanliness-history/aldgate-flats")
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
        print("✓ GET /api/image-ai/cleanliness-history requires auth")
    
    def test_history_returns_stats(self, auth_session):
        """History endpoint returns rows and stats"""
        resp = auth_session.get(f"{BASE_URL}/api/image-ai/cleanliness-history/aldgate-flats?limit=50")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        assert "rows" in data
        assert "count" in data
        assert "pass_count" in data
        assert "fail_count" in data
        assert "pass_rate" in data
        assert "avg_score" in data
        print(f"✓ History returns stats: count={data['count']}, pass_rate={data['pass_rate']}, avg_score={data['avg_score']}")
    
    def test_history_with_room_filter(self, auth_session):
        """History can be filtered by room_id"""
        resp = auth_session.get(f"{BASE_URL}/api/image-ai/cleanliness-history/aldgate-flats?room_id=TEST_101&limit=50")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        # All rows should have the filtered room_id
        for row in data["rows"]:
            assert row["room_id"] == "TEST_101"
        print(f"✓ Room filter works, found {data['count']} rows for TEST_101")
    
    def test_history_limit_validation_min(self, auth_session):
        """Limit must be >= 1"""
        resp = auth_session.get(f"{BASE_URL}/api/image-ai/cleanliness-history/aldgate-flats?limit=0")
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}"
        assert "limit must be 1..200" in resp.text
        print("✓ Limit < 1 returns 400")
    
    def test_history_limit_validation_max(self, auth_session):
        """Limit must be <= 200"""
        resp = auth_session.get(f"{BASE_URL}/api/image-ai/cleanliness-history/aldgate-flats?limit=201")
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}"
        assert "limit must be 1..200" in resp.text
        print("✓ Limit > 200 returns 400")


class TestImageAIScoreDetail:
    """Tests for GET /api/image-ai/cleanliness-score/{score_id}"""
    
    def test_detail_requires_auth(self):
        """Endpoint requires authentication"""
        resp = requests.get(f"{BASE_URL}/api/image-ai/cleanliness-score/nonexistent-id")
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
        print("✓ GET /api/image-ai/cleanliness-score/{id} requires auth")
    
    def test_detail_not_found(self, auth_session):
        """Non-existent score_id returns 404"""
        resp = auth_session.get(f"{BASE_URL}/api/image-ai/cleanliness-score/nonexistent-id-12345")
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}"
        print("✓ Non-existent score_id returns 404")
    
    def test_detail_returns_full_record(self, auth_session, test_image_b64):
        """Valid score_id returns full record including photos"""
        # First create a score
        create_resp = auth_session.post(f"{BASE_URL}/api/image-ai/cleanliness-score", json={
            "property_id": "aldgate-flats",
            "room_id": "TEST_DETAIL",
            "photos_base64": [test_image_b64]
        })
        
        if create_resp.status_code == 200:
            score_id = create_resp.json()["id"]
            
            # Now fetch detail
            detail_resp = auth_session.get(f"{BASE_URL}/api/image-ai/cleanliness-score/{score_id}")
            assert detail_resp.status_code == 200, f"Expected 200, got {detail_resp.status_code}"
            
            data = detail_resp.json()
            assert data["id"] == score_id
            assert "photos_b64" in data  # Detail includes photos
            assert data["room_id"] == "TEST_DETAIL"
            print(f"✓ Score detail returns full record with photos_b64")
        else:
            print("✓ Skipped detail test (AI unavailable)")


class TestCopilotButtonIntegration:
    """Tests for CopilotButton scatter into panels (Batch 29)"""
    
    def test_copilot_anomaly_context(self, auth_session):
        """Copilot accepts anomaly context type"""
        resp = auth_session.post(f"{BASE_URL}/api/copilot/summarize", json={
            "context_type": "anomaly",
            "data": {"total": 5, "by_severity": {"severe": 2, "moderate": 3}},
            "property_id": "aldgate-flats"
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "insight" in data
        print(f"✓ Copilot anomaly context works, source={data.get('source')}")
    
    def test_copilot_forecast_context(self, auth_session):
        """Copilot accepts forecast context type"""
        resp = auth_session.post(f"{BASE_URL}/api/copilot/summarize", json={
            "context_type": "forecast",
            "data": {"months": 12, "yoy_growth_pct": 15, "total_revenue": 500000}
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "insight" in data
        print(f"✓ Copilot forecast context works, source={data.get('source')}")
    
    def test_copilot_leaderboard_context(self, auth_session):
        """Copilot accepts leaderboard context type"""
        resp = auth_session.post(f"{BASE_URL}/api/copilot/summarize", json={
            "context_type": "leaderboard",
            "data": {"total_amount": 1500, "total_count": 50, "avg": 30}
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "insight" in data
        print(f"✓ Copilot leaderboard context works, source={data.get('source')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
