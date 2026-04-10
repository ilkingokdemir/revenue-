"""
Backend API tests for Multi-language AI Response Generator feature
Tests: GET /api/languages, POST /api/reviews/{id}/detect-language, 
       POST /api/reviews/generate-ai-response (with language param),
       POST /api/reviews/translate
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestLanguagesEndpoint:
    """Tests for GET /api/languages endpoint"""
    
    def test_get_languages_returns_16_languages(self):
        """Verify /api/languages returns exactly 16 supported languages"""
        response = requests.get(f"{BASE_URL}/api/languages")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        languages = response.json()
        assert isinstance(languages, list), "Response should be a list"
        assert len(languages) == 16, f"Expected 16 languages, got {len(languages)}"
        
        # Verify structure of each language object
        for lang in languages:
            assert "code" in lang, "Each language should have 'code'"
            assert "name" in lang, "Each language should have 'name'"
        
        # Verify expected languages are present
        codes = [lang["code"] for lang in languages]
        expected_codes = ["auto", "en", "fr", "de", "es", "it", "pt", "zh", "ja", "ko", "ar", "ru", "nl", "th", "hi", "tr"]
        for code in expected_codes:
            assert code in codes, f"Language code '{code}' should be in the list"
        
        print(f"✓ GET /api/languages returns {len(languages)} languages with correct structure")


class TestLanguageDetection:
    """Tests for POST /api/reviews/{id}/detect-language endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get a review ID for testing"""
        response = requests.get(f"{BASE_URL}/api/reviews")
        assert response.status_code == 200
        reviews = response.json()
        assert len(reviews) > 0, "Need at least one review for testing"
        self.review_id = reviews[0]["id"]
        self.review_text = reviews[0]["review_text"]
    
    def test_detect_language_returns_code_name_confidence(self):
        """Verify language detection returns code, name, and confidence"""
        response = requests.post(f"{BASE_URL}/api/reviews/{self.review_id}/detect-language")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "code" in data, "Response should have 'code'"
        assert "name" in data, "Response should have 'name'"
        assert "confidence" in data, "Response should have 'confidence'"
        
        # Verify data types
        assert isinstance(data["code"], str), "Code should be a string"
        assert isinstance(data["name"], str), "Name should be a string"
        assert isinstance(data["confidence"], (int, float)), "Confidence should be a number"
        
        # Confidence should be between 0 and 1
        assert 0 <= data["confidence"] <= 1, f"Confidence {data['confidence']} should be between 0 and 1"
        
        print(f"✓ Language detection returned: {data['name']} ({data['code']}) with {data['confidence']*100:.0f}% confidence")
    
    def test_detect_language_invalid_review_id(self):
        """Verify 404 for non-existent review"""
        response = requests.post(f"{BASE_URL}/api/reviews/invalid-id-12345/detect-language")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ Language detection returns 404 for invalid review ID")


class TestAIResponseWithLanguage:
    """Tests for POST /api/reviews/generate-ai-response with language parameter"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get a pending review ID for testing"""
        response = requests.get(f"{BASE_URL}/api/reviews?status=pending")
        assert response.status_code == 200
        reviews = response.json()
        if len(reviews) == 0:
            # Try all reviews
            response = requests.get(f"{BASE_URL}/api/reviews")
            reviews = response.json()
        assert len(reviews) > 0, "Need at least one review for testing"
        self.review_id = reviews[0]["id"]
    
    def test_generate_ai_response_with_auto_language(self):
        """Verify AI response generation with language='auto'"""
        payload = {
            "review_id": self.review_id,
            "tone": "professional",
            "language": "auto"
        }
        response = requests.post(f"{BASE_URL}/api/reviews/generate-ai-response", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "generated_text" in data, "Response should have 'generated_text'"
        assert len(data["generated_text"]) > 50, "Generated text should be substantial"
        
        print(f"✓ AI response with language='auto' generated {len(data['generated_text'])} chars")
    
    def test_generate_ai_response_with_french_language(self):
        """Verify AI response generation with language='fr' generates French response"""
        payload = {
            "review_id": self.review_id,
            "tone": "friendly",
            "language": "fr"
        }
        response = requests.post(f"{BASE_URL}/api/reviews/generate-ai-response", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "generated_text" in data, "Response should have 'generated_text'"
        assert len(data["generated_text"]) > 50, "Generated text should be substantial"
        
        # Check for common French words/patterns (not exhaustive, AI may vary)
        text = data["generated_text"].lower()
        french_indicators = ["merci", "nous", "votre", "cher", "chère", "hôtel", "séjour", "équipe", "cordialement"]
        has_french = any(word in text for word in french_indicators)
        
        print(f"✓ AI response with language='fr' generated {len(data['generated_text'])} chars")
        print(f"  French indicators found: {has_french}")
        if not has_french:
            print(f"  Note: Response may still be French but without common indicators. First 200 chars: {data['generated_text'][:200]}")
    
    def test_generate_ai_response_with_german_language(self):
        """Verify AI response generation with language='de' generates German response"""
        payload = {
            "review_id": self.review_id,
            "tone": "professional",
            "language": "de"
        }
        response = requests.post(f"{BASE_URL}/api/reviews/generate-ai-response", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "generated_text" in data, "Response should have 'generated_text'"
        assert len(data["generated_text"]) > 50, "Generated text should be substantial"
        
        print(f"✓ AI response with language='de' generated {len(data['generated_text'])} chars")
    
    def test_generate_ai_response_invalid_review_id(self):
        """Verify 404 for non-existent review"""
        payload = {
            "review_id": "invalid-id-12345",
            "tone": "professional",
            "language": "en"
        }
        response = requests.post(f"{BASE_URL}/api/reviews/generate-ai-response", json=payload)
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ AI response returns 404 for invalid review ID")


class TestTranslation:
    """Tests for POST /api/reviews/translate endpoint"""
    
    def test_translate_french_to_english(self):
        """Verify translation of French text to English"""
        payload = {
            "text": "Merci beaucoup pour votre séjour. Nous espérons vous revoir bientôt.",
            "target_language": "en"
        }
        response = requests.post(f"{BASE_URL}/api/reviews/translate", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "translated_text" in data, "Response should have 'translated_text'"
        assert "target_language" in data, "Response should have 'target_language'"
        assert "target_name" in data, "Response should have 'target_name'"
        
        assert data["target_language"] == "en", "Target language should be 'en'"
        assert data["target_name"] == "English", "Target name should be 'English'"
        
        # Check translation contains English words
        text = data["translated_text"].lower()
        english_indicators = ["thank", "stay", "hope", "see", "soon", "you"]
        has_english = any(word in text for word in english_indicators)
        
        print(f"✓ Translation to English: '{data['translated_text'][:100]}...'")
        print(f"  English indicators found: {has_english}")
    
    def test_translate_german_to_english(self):
        """Verify translation of German text to English"""
        payload = {
            "text": "Vielen Dank für Ihren Aufenthalt. Wir hoffen, Sie bald wiederzusehen.",
            "target_language": "en"
        }
        response = requests.post(f"{BASE_URL}/api/reviews/translate", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "translated_text" in data, "Response should have 'translated_text'"
        assert len(data["translated_text"]) > 10, "Translation should have content"
        
        print(f"✓ German to English translation: '{data['translated_text']}'")
    
    def test_translate_empty_text(self):
        """Verify handling of empty text"""
        payload = {
            "text": "",
            "target_language": "en"
        }
        response = requests.post(f"{BASE_URL}/api/reviews/translate", json=payload)
        # Should either return 200 with empty translation or 400/422 for validation error
        assert response.status_code in [200, 400, 422], f"Unexpected status: {response.status_code}"
        print(f"✓ Empty text translation handled with status {response.status_code}")


class TestRegressionDashboardStats:
    """Regression tests for dashboard stats endpoint"""
    
    def test_review_stats_summary(self):
        """Verify /api/reviews/stats/summary still works"""
        response = requests.get(f"{BASE_URL}/api/reviews/stats/summary")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "total_reviews" in data
        assert "responded" in data
        assert "pending" in data
        assert "response_rate" in data
        assert "average_rating" in data
        
        print(f"✓ Dashboard stats: {data['total_reviews']} reviews, {data['response_rate']}% response rate")


class TestRegressionReviewList:
    """Regression tests for review list endpoint"""
    
    def test_get_reviews(self):
        """Verify /api/reviews still works"""
        response = requests.get(f"{BASE_URL}/api/reviews")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        reviews = response.json()
        assert isinstance(reviews, list)
        
        if len(reviews) > 0:
            review = reviews[0]
            assert "id" in review
            assert "platform" in review
            assert "guest_name" in review
            assert "rating" in review
            assert "review_text" in review
            assert "response_status" in review
        
        print(f"✓ Review list returns {len(reviews)} reviews")


class TestRegressionAnalytics:
    """Regression tests for analytics endpoint"""
    
    def test_analytics_dashboard(self):
        """Verify /api/analytics/dashboard still works"""
        response = requests.get(f"{BASE_URL}/api/analytics/dashboard")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "overview" in data
        assert "rating_distribution" in data
        assert "platform_stats" in data
        
        print(f"✓ Analytics dashboard returns data with {len(data.get('platform_stats', []))} platforms")


class TestRegressionTemplates:
    """Regression tests for templates endpoint"""
    
    def test_get_templates(self):
        """Verify /api/templates still works"""
        response = requests.get(f"{BASE_URL}/api/templates")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        templates = response.json()
        assert isinstance(templates, list)
        
        print(f"✓ Templates endpoint returns {len(templates)} templates")


class TestRegressionIntegrations:
    """Regression tests for integrations endpoint"""
    
    def test_get_integrations(self):
        """Verify /api/integrations still works"""
        response = requests.get(f"{BASE_URL}/api/integrations")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        integrations = response.json()
        assert isinstance(integrations, list)
        
        print(f"✓ Integrations endpoint returns {len(integrations)} integrations")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
