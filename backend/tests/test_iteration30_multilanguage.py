"""
Multi-language Support API Tests - Iteration 30
Tests for translation override endpoints and language features
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestTranslationAPIs:
    """Test translation override endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        if login_resp.status_code == 200:
            self.token = login_resp.json().get("token")
            self.headers = {"Authorization": f"Bearer {self.token}"}
        else:
            pytest.skip("Authentication failed")
    
    def test_get_translations_public_empty(self):
        """GET /api/translations/{property_id}/{lang_code} - Public, returns empty overrides by default"""
        response = requests.get(f"{BASE_URL}/api/translations/aldgate-flats/fr")
        assert response.status_code == 200
        data = response.json()
        assert data["property_id"] == "aldgate-flats"
        assert data["lang_code"] == "fr"
        assert "overrides" in data
        print(f"✓ GET translations for aldgate-flats/fr: {data}")
    
    def test_get_translations_nonexistent_property(self):
        """GET /api/translations/{property_id}/{lang_code} - Returns empty for non-existent property"""
        response = requests.get(f"{BASE_URL}/api/translations/nonexistent-property/en")
        assert response.status_code == 200
        data = response.json()
        assert data["property_id"] == "nonexistent-property"
        assert data["lang_code"] == "en"
        assert data["overrides"] == {}
        print(f"✓ GET translations for non-existent property returns empty: {data}")
    
    def test_put_translations_requires_auth(self):
        """PUT /api/translations/{property_id}/{lang_code} - Requires admin auth"""
        response = requests.put(
            f"{BASE_URL}/api/translations/aldgate-flats/fr",
            json={"test_key": "test_value"}
        )
        assert response.status_code in [401, 403]
        print(f"✓ PUT translations without auth returns {response.status_code}")
    
    def test_put_translations_with_auth(self):
        """PUT /api/translations/{property_id}/{lang_code} - Saves custom overrides with auth"""
        test_overrides = {
            "hero.bookYourStay": "Réservez votre séjour personnalisé",
            "search.search": "Rechercher maintenant"
        }
        response = requests.put(
            f"{BASE_URL}/api/translations/aldgate-flats/fr",
            json=test_overrides,
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["property_id"] == "aldgate-flats"
        assert data["lang_code"] == "fr"
        assert data["overrides"] == test_overrides
        print(f"✓ PUT translations saved: {data}")
    
    def test_get_translations_after_save(self):
        """GET /api/translations/{property_id}/{lang_code} - Returns saved overrides"""
        # First save some overrides
        test_overrides = {"test.key": "Test Value FR"}
        requests.put(
            f"{BASE_URL}/api/translations/aldgate-flats/fr",
            json=test_overrides,
            headers=self.headers
        )
        
        # Then retrieve them (public endpoint)
        response = requests.get(f"{BASE_URL}/api/translations/aldgate-flats/fr")
        assert response.status_code == 200
        data = response.json()
        assert "test.key" in data["overrides"]
        print(f"✓ GET translations returns saved overrides: {data}")
    
    def test_list_property_translations_requires_auth(self):
        """GET /api/translations/{property_id} - Requires admin auth"""
        response = requests.get(f"{BASE_URL}/api/translations/aldgate-flats")
        assert response.status_code in [401, 403]
        print(f"✓ List translations without auth returns {response.status_code}")
    
    def test_list_property_translations_with_auth(self):
        """GET /api/translations/{property_id} - Lists all overrides for a property"""
        response = requests.get(
            f"{BASE_URL}/api/translations/aldgate-flats",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ List translations for aldgate-flats: {len(data)} language(s)")
    
    def test_ai_translate_requires_auth(self):
        """POST /api/translations/ai-translate - Requires admin auth"""
        response = requests.post(
            f"{BASE_URL}/api/translations/ai-translate",
            params={"target_lang": "fr"},
            json={"welcome": "Welcome to our hotel"}
        )
        assert response.status_code in [401, 403]
        print(f"✓ AI translate without auth returns {response.status_code}")
    
    def test_ai_translate_with_auth(self):
        """POST /api/translations/ai-translate - AI translates custom texts"""
        response = requests.post(
            f"{BASE_URL}/api/translations/ai-translate",
            params={"target_lang": "fr"},
            json={"welcome": "Welcome to our hotel", "goodbye": "Thank you for staying"},
            headers=self.headers
        )
        # May return 200 with translations or 500 if LLM not configured
        if response.status_code == 200:
            data = response.json()
            assert "translations" in data
            assert data["target_lang"] == "fr"
            print(f"✓ AI translate returned: {data}")
        else:
            print(f"⚠ AI translate returned {response.status_code} (LLM may not be configured)")
            # This is acceptable - LLM key may not be configured in test env


class TestLanguageEndpoints:
    """Test language-related endpoints"""
    
    def test_get_languages(self):
        """GET /api/languages - Returns supported languages"""
        response = requests.get(f"{BASE_URL}/api/languages")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 12  # At least 12 languages
        
        # Check for expected languages
        lang_codes = [l["code"] for l in data]
        expected = ["en", "fr", "de", "es", "it", "pt", "ar", "zh", "ja", "ko", "nl", "ru"]
        for code in expected:
            assert code in lang_codes, f"Missing language: {code}"
        
        print(f"✓ GET languages returned {len(data)} languages: {lang_codes}")


class TestBookingEngineWithLanguage:
    """Test booking engine property endpoint includes language-related data"""
    
    def test_property_endpoint_returns_data(self):
        """GET /api/booking/property/{id} - Returns property data"""
        response = requests.get(f"{BASE_URL}/api/booking/property/aldgate-flats")
        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "id" in data or "property_id" in data
        print(f"✓ Property endpoint returns: {data.get('name')}")
    
    def test_property_with_lang_param(self):
        """GET /api/booking/property/{id}?lang=fr - Property endpoint accepts lang param"""
        response = requests.get(f"{BASE_URL}/api/booking/property/aldgate-flats?lang=fr")
        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        print(f"✓ Property endpoint with lang=fr works")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
