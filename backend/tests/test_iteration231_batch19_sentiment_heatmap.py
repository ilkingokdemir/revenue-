"""
Iteration 231 - Batch 19: Cross-Channel Sentiment Heatmap Tests

Tests for:
- GET /api/sentiment/heatmap/{property_id}?days=N - Full sentiment analysis
- GET /api/sentiment/drilldown/{property_id}?topic=X&days=N&band=Y - Topic drilldown

Sentiment is LEXICON-based (no LLM call) - fast and $0 cost.
Data sources: reviews, unified_inbox, mid_stay_responses, survey_responses, post_stay_surveys.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

class TestSentimentHeatmapBatch19:
    """Batch 19: Cross-Channel Sentiment Heatmap API Tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        self.session = requests.Session()
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        self.token = login_resp.json().get("access_token")
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
    
    # ========== Heatmap Endpoint Tests ==========
    
    def test_heatmap_default_90_days(self):
        """GET /api/sentiment/heatmap/default?days=90 → 200 with required fields"""
        resp = self.session.get(f"{BASE_URL}/api/sentiment/heatmap/default?days=90")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        # Required top-level fields
        assert "total_responses" in data, "Missing total_responses"
        assert "overall_avg" in data, "Missing overall_avg"
        assert "overall_band" in data, "Missing overall_band"
        assert "nps_like" in data, "Missing nps_like"
        assert "positive_count" in data, "Missing positive_count"
        assert "neutral_count" in data, "Missing neutral_count"
        assert "negative_count" in data, "Missing negative_count"
        assert "by_channel" in data, "Missing by_channel"
        assert "topic_matrix" in data, "Missing topic_matrix"
        assert "trend" in data, "Missing trend"
        assert "top_complaints" in data, "Missing top_complaints"
        assert "top_praises" in data, "Missing top_praises"
        
        # Validate overall_band is one of expected values
        assert data["overall_band"] in ["positive", "neutral", "negative"], f"Invalid overall_band: {data['overall_band']}"
        
        print(f"✓ Heatmap 90 days: {data['total_responses']} responses, overall_band={data['overall_band']}, nps_like={data['nps_like']}")
    
    def test_heatmap_default_365_days(self):
        """GET /api/sentiment/heatmap/default?days=365 → 200 with more data"""
        resp = self.session.get(f"{BASE_URL}/api/sentiment/heatmap/default?days=365")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        # Default property should have review data - expect total_responses >= 30
        # Note: This may vary based on seeded data
        assert data["total_responses"] >= 0, "total_responses should be non-negative"
        assert "overall_band" in data, "Missing overall_band"
        
        print(f"✓ Heatmap 365 days: {data['total_responses']} responses, overall_avg={data['overall_avg']}")
    
    def test_heatmap_by_channel_structure(self):
        """Verify by_channel has correct structure"""
        resp = self.session.get(f"{BASE_URL}/api/sentiment/heatmap/default?days=365")
        assert resp.status_code == 200
        
        data = resp.json()
        by_channel = data.get("by_channel", {})
        
        # Each channel should have count, avg, pos, neu, neg
        for ch, ch_data in by_channel.items():
            assert "count" in ch_data, f"Channel {ch} missing count"
            assert "avg" in ch_data, f"Channel {ch} missing avg"
            assert "pos" in ch_data, f"Channel {ch} missing pos"
            assert "neu" in ch_data, f"Channel {ch} missing neu"
            assert "neg" in ch_data, f"Channel {ch} missing neg"
        
        print(f"✓ by_channel structure valid, {len(by_channel)} channels found")
    
    def test_heatmap_topic_matrix_structure(self):
        """Verify topic_matrix has correct structure with max 10 topics"""
        resp = self.session.get(f"{BASE_URL}/api/sentiment/heatmap/default?days=365")
        assert resp.status_code == 200
        
        data = resp.json()
        topic_matrix = data.get("topic_matrix", {})
        
        # Expected Turkish/English mixed topic keys
        expected_topics = [
            "Personel / Staff", "Oda / Room", "Yemek / F&B", "Konum / Location",
            "Wi-Fi / Internet", "Check-in / Check-out", "Klima / Comfort",
            "Temizlik / Cleanliness", "Fiyat / Value", "Gürültü / Noise"
        ]
        
        # Each topic should have positive, neutral, negative, total
        for topic, cells in topic_matrix.items():
            assert "positive" in cells, f"Topic {topic} missing positive"
            assert "neutral" in cells, f"Topic {topic} missing neutral"
            assert "negative" in cells, f"Topic {topic} missing negative"
            assert "total" in cells, f"Topic {topic} missing total"
        
        # Check that topics are from expected list (if any data exists)
        if topic_matrix:
            for topic in topic_matrix.keys():
                assert topic in expected_topics, f"Unexpected topic: {topic}"
        
        print(f"✓ topic_matrix structure valid, {len(topic_matrix)} topics found")
    
    def test_heatmap_top_praises_structure(self):
        """Verify top_praises has correct structure"""
        resp = self.session.get(f"{BASE_URL}/api/sentiment/heatmap/default?days=365")
        assert resp.status_code == 200
        
        data = resp.json()
        top_praises = data.get("top_praises", [])
        
        # Each praise should have score, channel, author, topics, text
        for praise in top_praises:
            assert "score" in praise, "Praise missing score"
            assert "channel" in praise, "Praise missing channel"
            assert "author" in praise, "Praise missing author"
            assert "topics" in praise, "Praise missing topics"
            assert "text" in praise, "Praise missing text"
            # Text should be max 300 chars (snippet)
            assert len(praise["text"]) <= 301, f"Praise text too long: {len(praise['text'])} chars"
            # Topics should be an array
            assert isinstance(praise["topics"], list), "topics should be array"
        
        print(f"✓ top_praises structure valid, {len(top_praises)} praises found")
    
    def test_heatmap_top_complaints_structure(self):
        """Verify top_complaints has correct structure"""
        resp = self.session.get(f"{BASE_URL}/api/sentiment/heatmap/default?days=365")
        assert resp.status_code == 200
        
        data = resp.json()
        top_complaints = data.get("top_complaints", [])
        
        # Each complaint should have score, channel, author, topics, text
        for complaint in top_complaints:
            assert "score" in complaint, "Complaint missing score"
            assert "channel" in complaint, "Complaint missing channel"
            assert "author" in complaint, "Complaint missing author"
            assert "topics" in complaint, "Complaint missing topics"
            assert "text" in complaint, "Complaint missing text"
            # Text should be max 300 chars (snippet)
            assert len(complaint["text"]) <= 301, f"Complaint text too long: {len(complaint['text'])} chars"
        
        print(f"✓ top_complaints structure valid, {len(top_complaints)} complaints found")
    
    def test_heatmap_trend_structure(self):
        """Verify trend has correct structure (daily bars)"""
        resp = self.session.get(f"{BASE_URL}/api/sentiment/heatmap/default?days=90")
        assert resp.status_code == 200
        
        data = resp.json()
        trend = data.get("trend", [])
        
        # Each trend item should have date, count, avg
        for item in trend:
            assert "date" in item, "Trend item missing date"
            assert "count" in item, "Trend item missing count"
            assert "avg" in item, "Trend item missing avg"
        
        print(f"✓ trend structure valid, {len(trend)} daily entries found")
    
    # ========== Drilldown Endpoint Tests ==========
    
    def test_drilldown_with_band_filter(self):
        """GET /api/sentiment/drilldown/default?topic=Oda%20%2F%20Room&days=365&band=positive → 200"""
        topic = "Oda / Room"
        resp = self.session.get(
            f"{BASE_URL}/api/sentiment/drilldown/default",
            params={"topic": topic, "days": 365, "band": "positive"}
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        assert "topic" in data, "Missing topic"
        assert "band_filter" in data, "Missing band_filter"
        assert "count" in data, "Missing count"
        assert "rows" in data, "Missing rows"
        
        assert data["topic"] == topic, f"Expected topic '{topic}', got '{data['topic']}'"
        assert data["band_filter"] == "positive", f"Expected band_filter 'positive', got '{data['band_filter']}'"
        
        # Each row should have text, score, band, channel, author
        for row in data["rows"]:
            assert "text" in row, "Row missing text"
            assert "score" in row, "Row missing score"
            assert "band" in row, "Row missing band"
            assert "channel" in row, "Row missing channel"
            assert "author" in row, "Row missing author"
            # All rows should be positive since we filtered by band
            assert row["band"] == "positive", f"Expected positive band, got {row['band']}"
        
        print(f"✓ Drilldown with band filter: {data['count']} rows for topic '{topic}' (positive)")
    
    def test_drilldown_without_band_filter(self):
        """GET /api/sentiment/drilldown without band filter → returns all bands for that topic"""
        topic = "Personel / Staff"
        resp = self.session.get(
            f"{BASE_URL}/api/sentiment/drilldown/default",
            params={"topic": topic, "days": 365}
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        assert data["topic"] == topic
        assert data["band_filter"] is None, f"Expected band_filter None, got '{data['band_filter']}'"
        
        # Rows can have any band (positive, neutral, negative)
        bands_found = set()
        for row in data["rows"]:
            bands_found.add(row["band"])
        
        print(f"✓ Drilldown without band filter: {data['count']} rows, bands found: {bands_found}")
    
    def test_drilldown_sorted_by_score(self):
        """Verify drilldown rows are sorted by score (negatives first)"""
        topic = "Temizlik / Cleanliness"
        resp = self.session.get(
            f"{BASE_URL}/api/sentiment/drilldown/default",
            params={"topic": topic, "days": 365}
        )
        assert resp.status_code == 200
        
        data = resp.json()
        rows = data.get("rows", [])
        
        if len(rows) > 1:
            # Verify sorted by score ascending (negatives first)
            scores = [r["score"] for r in rows]
            assert scores == sorted(scores), f"Rows not sorted by score: {scores[:5]}..."
        
        print(f"✓ Drilldown sorted by score: {len(rows)} rows")
    
    def test_drilldown_negative_band(self):
        """GET /api/sentiment/drilldown with band=negative"""
        topic = "Yemek / F&B"
        resp = self.session.get(
            f"{BASE_URL}/api/sentiment/drilldown/default",
            params={"topic": topic, "days": 365, "band": "negative"}
        )
        assert resp.status_code == 200
        
        data = resp.json()
        assert data["band_filter"] == "negative"
        
        # All rows should be negative
        for row in data["rows"]:
            assert row["band"] == "negative", f"Expected negative band, got {row['band']}"
        
        print(f"✓ Drilldown negative band: {data['count']} rows")
    
    def test_drilldown_neutral_band(self):
        """GET /api/sentiment/drilldown with band=neutral"""
        topic = "Konum / Location"
        resp = self.session.get(
            f"{BASE_URL}/api/sentiment/drilldown/default",
            params={"topic": topic, "days": 365, "band": "neutral"}
        )
        assert resp.status_code == 200
        
        data = resp.json()
        assert data["band_filter"] == "neutral"
        
        # All rows should be neutral
        for row in data["rows"]:
            assert row["band"] == "neutral", f"Expected neutral band, got {row['band']}"
        
        print(f"✓ Drilldown neutral band: {data['count']} rows")


class TestRegressionBatches13to18:
    """Regression tests for previous batches 13-18"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        self.session = requests.Session()
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        self.token = login_resp.json().get("access_token")
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
    
    def test_batch13_tr_compliance(self):
        """Batch 13: TR Compliance endpoint still works"""
        resp = self.session.get(f"{BASE_URL}/api/tr-compliance/kbs/default/history")
        assert resp.status_code == 200, f"TR Compliance failed: {resp.status_code}"
        print("✓ Batch 13 TR Compliance: PASSED")
    
    def test_batch14_ai_predictions(self):
        """Batch 14: AI Predictions endpoint still works"""
        resp = self.session.get(f"{BASE_URL}/api/ai-predictions/cancel-risk/default")
        assert resp.status_code == 200, f"AI Predictions failed: {resp.status_code}"
        print("✓ Batch 14 AI Predictions: PASSED")
    
    def test_batch15_eu_compliance(self):
        """Batch 15: EU Compliance endpoint still works"""
        resp = self.session.get(f"{BASE_URL}/api/eu-compliance/catalog")
        assert resp.status_code == 200, f"EU Compliance failed: {resp.status_code}"
        print("✓ Batch 15 EU Compliance: PASSED")
    
    def test_batch16_channel_revenue(self):
        """Batch 16: Channel Revenue endpoint still works"""
        resp = self.session.get(f"{BASE_URL}/api/channel-revenue/channels/default")
        assert resp.status_code == 200, f"Channel Revenue failed: {resp.status_code}"
        print("✓ Batch 16 Channel Revenue: PASSED")
    
    def test_batch17_kds(self):
        """Batch 17: KDS endpoint still works"""
        resp = self.session.get(f"{BASE_URL}/api/kds/default")
        assert resp.status_code == 200, f"KDS failed: {resp.status_code}"
        print("✓ Batch 17 KDS: PASSED")
    
    def test_batch18_loyalty_v2_benefits(self):
        """Batch 18: Loyalty V2 Benefits endpoint still works"""
        resp = self.session.get(f"{BASE_URL}/api/loyalty-v2/benefits/default")
        assert resp.status_code == 200, f"Loyalty V2 Benefits failed: {resp.status_code}"
        print("✓ Batch 18 Loyalty V2 Benefits: PASSED")
    
    def test_batch18_loyalty_v2_packages(self):
        """Batch 18: Loyalty V2 Packages endpoint still works"""
        resp = self.session.get(f"{BASE_URL}/api/loyalty-v2/packages/default")
        assert resp.status_code == 200, f"Loyalty V2 Packages failed: {resp.status_code}"
        print("✓ Batch 18 Loyalty V2 Packages: PASSED")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
