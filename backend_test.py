#!/usr/bin/env python3
"""
Comprehensive Backend API Testing for Hotel Review Management System
Tests all endpoints including AI response generation via GPT-5.2 and Platform Integrations
"""

import requests
import sys
import json
from datetime import datetime
from typing import Dict, Any, Optional

class ReviewAPITester:
    def __init__(self, base_url: str = "https://review-hub-108.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []
        self.created_review_id = None

    def log_test(self, name: str, success: bool, details: str = "", response_data: Any = None):
        """Log test result"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
            print(f"✅ {name}: PASSED")
        else:
            print(f"❌ {name}: FAILED - {details}")
        
        self.test_results.append({
            "test": name,
            "success": success,
            "details": details,
            "response_data": response_data
        })

    def run_test(self, name: str, method: str, endpoint: str, expected_status: int, 
                 data: Optional[Dict] = None, params: Optional[Dict] = None) -> tuple[bool, Any]:
        """Run a single API test"""
        url = f"{self.api_url}/{endpoint}"
        headers = {'Content-Type': 'application/json'}
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, params=params, timeout=30)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=30)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=headers, timeout=30)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers, timeout=30)
            else:
                self.log_test(name, False, f"Unsupported method: {method}")
                return False, {}

            success = response.status_code == expected_status
            response_data = {}
            
            try:
                response_data = response.json()
            except:
                response_data = {"raw_response": response.text}

            if success:
                self.log_test(name, True, f"Status: {response.status_code}", response_data)
            else:
                self.log_test(name, False, f"Expected {expected_status}, got {response.status_code}", response_data)

            return success, response_data

        except Exception as e:
            self.log_test(name, False, f"Exception: {str(e)}")
            return False, {}

    def test_root_endpoint(self):
        """Test API root endpoint"""
        return self.run_test("API Root", "GET", "", 200)

    def test_status_endpoints(self):
        """Test status check endpoints"""
        # Create status check
        success, response = self.run_test(
            "Create Status Check", 
            "POST", 
            "status", 
            200,
            data={"client_name": "test_client"}
        )
        
        if success:
            # Get status checks
            self.run_test("Get Status Checks", "GET", "status", 200)
        
        return success

    def test_seed_reviews(self):
        """Test seeding mock reviews"""
        # First clear any existing reviews
        self.run_test("Clear Reviews", "DELETE", "reviews/clear", 200)
        
        # Seed new reviews
        success, response = self.run_test("Seed Reviews", "POST", "reviews/seed", 200)
        
        if success and response.get("seeded"):
            print(f"   📊 Seeded {response.get('message', 'unknown')} reviews")
        
        return success

    def test_get_reviews(self):
        """Test getting reviews with various filters"""
        # Get all reviews
        success, response = self.run_test("Get All Reviews", "GET", "reviews", 200)
        
        if success and isinstance(response, list) and len(response) > 0:
            print(f"   📊 Found {len(response)} reviews")
            
            # Test platform filter
            self.run_test("Filter by Platform", "GET", "reviews", 200, 
                         params={"platform": "booking.com"})
            
            # Test status filter
            self.run_test("Filter by Status", "GET", "reviews", 200, 
                         params={"status": "pending"})
            
            # Test combined filters
            self.run_test("Combined Filters", "GET", "reviews", 200, 
                         params={"platform": "airbnb", "status": "pending"})
            
            return True, response
        
        return success, response

    def test_single_review(self, review_id: str):
        """Test getting a single review"""
        return self.run_test(f"Get Review {review_id[:8]}", "GET", f"reviews/{review_id}", 200)

    def test_create_review(self):
        """Test creating a new review"""
        review_data = {
            "platform": "booking.com",
            "guest_name": "Test Guest",
            "rating": 4,
            "review_text": "This is a test review for API testing purposes.",
            "stay_date": "January 2026",
            "room_type": "Test Suite"
        }
        
        success, response = self.run_test("Create Review", "POST", "reviews", 200, data=review_data)
        
        if success and response.get("id"):
            self.created_review_id = response["id"]
            print(f"   📝 Created review with ID: {self.created_review_id[:8]}...")
        
        return success, response

    def test_ai_response_generation(self, review_id: str):
        """Test AI response generation - CRITICAL TEST"""
        print(f"\n🤖 Testing AI Response Generation (GPT-5.2)...")
        
        # Test different tones
        tones = ["professional", "friendly", "apologetic"]
        ai_success_count = 0
        
        for tone in tones:
            ai_data = {
                "review_id": review_id,
                "tone": tone
            }
            
            print(f"   Testing {tone} tone...")
            success, response = self.run_test(
                f"AI Generate ({tone})", 
                "POST", 
                "reviews/generate-ai-response", 
                200, 
                data=ai_data
            )
            
            if success and response.get("generated_text"):
                ai_success_count += 1
                generated_text = response["generated_text"]
                print(f"   ✨ Generated {len(generated_text)} characters")
                print(f"   📝 Preview: {generated_text[:100]}...")
            else:
                print(f"   ❌ Failed to generate {tone} response")
        
        return ai_success_count > 0, ai_success_count

    def test_submit_response(self, review_id: str):
        """Test submitting a response to a review"""
        response_data = {
            "response_text": "Thank you for your feedback! We appreciate your review and look forward to welcoming you back. - The Management Team"
        }
        
        success, response = self.run_test(
            "Submit Response", 
            "PUT", 
            f"reviews/{review_id}/respond", 
            200, 
            data=response_data
        )
        
        if success and response.get("response_status") == "responded":
            print(f"   ✅ Review status updated to 'responded'")
        
        return success, response

    def test_stats_summary(self):
        """Test getting review statistics"""
        success, response = self.run_test("Get Stats Summary", "GET", "reviews/stats/summary", 200)
        
        if success:
            stats = response
            print(f"   📊 Total Reviews: {stats.get('total_reviews', 0)}")
            print(f"   ⭐ Average Rating: {stats.get('average_rating', 0)}")
            print(f"   📈 Response Rate: {stats.get('response_rate', 0)}%")
            print(f"   ⏳ Pending: {stats.get('pending', 0)}")
            print(f"   ✅ Responded: {stats.get('responded', 0)}")
            
            platforms = stats.get('by_platform', {})
            if platforms:
                print(f"   🏢 Platforms: {', '.join(platforms.keys())}")
        
        return success, response

    def test_notification_settings(self):
        """Test notification settings endpoints"""
        print(f"\n📧 Testing Email Notification Settings...")
        
        # 1. Get current notification settings
        success, response = self.run_test("Get Notification Settings", "GET", "notifications/settings", 200)
        
        if success:
            print(f"   📋 Current settings: enabled={response.get('enabled', False)}, email={response.get('email', 'none')}")
            print(f"   🎯 Threshold: {response.get('negative_threshold', 2)} stars")
        
        # 2. Update notification settings
        settings_data = {
            "email": "test@hotel.com",
            "notify_negative_reviews": True,
            "negative_threshold": 2,
            "enabled": True
        }
        
        success, response = self.run_test(
            "Update Notification Settings", 
            "PUT", 
            "notifications/settings", 
            200, 
            data=settings_data
        )
        
        if success:
            print(f"   ✅ Settings updated: enabled={response.get('enabled', False)}")
        
        # 3. Get notification log
        success, response = self.run_test("Get Notification Log", "GET", "notifications/log", 200)
        
        if success and isinstance(response, list):
            print(f"   📜 Found {len(response)} notification log entries")
        
        return success

    def test_notification_trigger(self):
        """Test that negative reviews trigger notifications"""
        print(f"\n🚨 Testing Negative Review Notification Trigger...")
        
        # Create a negative review (rating <= 2)
        negative_review_data = {
            "platform": "google",
            "guest_name": "Unhappy Guest",
            "rating": 2,  # This should trigger notification
            "review_text": "Very disappointed with the service. Room was dirty and staff was unhelpful.",
            "stay_date": "January 2026",
            "room_type": "Standard Room"
        }
        
        success, response = self.run_test(
            "Create Negative Review (Should Trigger Notification)", 
            "POST", 
            "reviews", 
            200, 
            data=negative_review_data
        )
        
        if success and response.get("id"):
            print(f"   📝 Created negative review with ID: {response['id'][:8]}...")
            print(f"   ⭐ Rating: {response.get('rating')}/5 (should trigger notification)")
            
            # Check notification log for new entry
            import time
            time.sleep(1)  # Give time for notification to be processed
            
            log_success, log_response = self.run_test("Check Notification Log After Negative Review", "GET", "notifications/log", 200)
            
            if log_success and isinstance(log_response, list) and len(log_response) > 0:
                latest_log = log_response[0]  # Most recent log entry
                if latest_log.get('review_id') == response['id']:
                    print(f"   ✅ Notification logged for review: status={latest_log.get('status', 'unknown')}")
                else:
                    print(f"   ⚠️ No notification log found for this review")
        
        return success

    def test_notification_test_endpoint(self):
        """Test the test notification endpoint"""
        print(f"\n🧪 Testing Test Notification Endpoint...")
        
        # First ensure settings are enabled
        settings_data = {
            "email": "test@hotel.com",
            "enabled": True
        }
        self.run_test("Enable Notifications for Test", "PUT", "notifications/settings", 200, data=settings_data)
        
        # Send test notification
        success, response = self.run_test("Send Test Notification", "POST", "notifications/test", 200)
        
        if success:
            print(f"   ✅ Test notification sent: {response.get('message', 'success')}")
        
        return success

    def test_response_templates(self):
        """Test response templates endpoints - NEW FEATURE"""
        print(f"\n📝 Testing Response Templates Feature...")
        
        # 1. Seed default templates
        success, response = self.run_test("Seed Default Templates", "POST", "templates/seed", 200)
        
        if success:
            print(f"   📊 {response.get('message', 'Templates seeded')}")
        
        # 2. Get all templates
        success, templates = self.run_test("Get All Templates", "GET", "templates", 200)
        
        template_id = None
        if success and isinstance(templates, list) and len(templates) > 0:
            print(f"   📋 Found {len(templates)} templates")
            template_id = templates[0]["id"]
            
            # Test category filtering
            categories = ["positive", "negative", "neutral", "complaint", "praise"]
            for category in categories:
                self.run_test(f"Filter Templates by {category}", "GET", "templates", 200, 
                             params={"category": category})
        
        # 3. Get single template
        if template_id:
            success, template = self.run_test(f"Get Single Template", "GET", f"templates/{template_id}", 200)
            
            if success:
                print(f"   📄 Template: {template.get('name', 'Unknown')}")
                print(f"   🏷️ Category: {template.get('category', 'Unknown')}")
                print(f"   📊 Usage count: {template.get('usage_count', 0)}")
        
        # 4. Create new template
        new_template_data = {
            "name": "Test Template",
            "category": "positive",
            "content": "Dear {guest_name},\n\nThank you for your wonderful review! We're delighted you enjoyed your stay.\n\nBest regards,\nThe Management Team",
            "tone": "friendly"
        }
        
        success, new_template = self.run_test("Create New Template", "POST", "templates", 200, data=new_template_data)
        
        created_template_id = None
        if success and new_template.get("id"):
            created_template_id = new_template["id"]
            print(f"   ✅ Created template with ID: {created_template_id[:8]}...")
        
        # 5. Update template
        if created_template_id:
            update_data = {
                "name": "Updated Test Template",
                "content": "Dear {guest_name},\n\nThank you for your updated review! We appreciate your feedback.\n\nBest regards,\nThe Management Team"
            }
            
            success, updated = self.run_test(f"Update Template", "PUT", f"templates/{created_template_id}", 200, data=update_data)
            
            if success:
                print(f"   ✅ Template updated: {updated.get('name', 'Unknown')}")
        
        # 6. Use template (increment usage count)
        if template_id:
            success, usage_response = self.run_test(f"Use Template", "POST", f"templates/{template_id}/use", 200)
            
            if success:
                print(f"   📈 Usage count incremented: {usage_response.get('usage_count', 0)}")
        
        # 7. Delete created template
        if created_template_id:
            success, delete_response = self.run_test(f"Delete Template", "DELETE", f"templates/{created_template_id}", 200)
            
            if success:
                print(f"   🗑️ Template deleted: {delete_response.get('message', 'success')}")
        
        return True

    def test_sentiment_analysis(self):
        """Test sentiment analysis endpoints - NEW FEATURE"""
        print(f"\n🧠 Testing AI Sentiment Analysis Feature...")
        
        # First ensure we have reviews to analyze
        success, reviews = self.run_test("Get Reviews for Analysis", "GET", "reviews", 200)
        
        if not success or not reviews or len(reviews) == 0:
            print("   ⚠️ No reviews found for sentiment analysis")
            return False
        
        review_id = reviews[0]["id"]
        
        # 1. Test individual review sentiment analysis
        success, analysis_response = self.run_test(
            "Analyze Individual Review Sentiment", 
            "POST", 
            f"reviews/{review_id}/analyze", 
            200
        )
        
        if success and analysis_response.get("analysis"):
            analysis = analysis_response["analysis"]
            print(f"   🎯 Sentiment: {analysis.get('sentiment', 'unknown')}")
            print(f"   📊 Score: {analysis.get('score', 0)}")
            print(f"   🚨 Urgency: {analysis.get('urgency', 'unknown')}")
            print(f"   🏷️ Topics: {', '.join(analysis.get('topics', [])[:3])}")
            print(f"   💡 Suggested tone: {analysis.get('suggested_tone', 'unknown')}")
            
            # Check for suggested templates
            templates = analysis_response.get("suggested_templates", [])
            if templates:
                print(f"   📝 Suggested templates: {len(templates)} found")
        
        # 2. Test batch sentiment analysis
        success, batch_response = self.run_test(
            "Run Batch Sentiment Analysis", 
            "POST", 
            "reviews/analyze-batch", 
            200
        )
        
        if success:
            analyzed_count = batch_response.get("analyzed", 0)
            total_count = batch_response.get("total", 0)
            print(f"   📊 Batch analysis: {analyzed_count}/{total_count} reviews analyzed")
        
        return True

    def test_analytics_dashboard(self):
        """Test analytics dashboard endpoint - NEW FEATURE"""
        print(f"\n📊 Testing Analytics Dashboard Feature...")
        
        # Get comprehensive analytics data
        success, analytics = self.run_test("Get Analytics Dashboard", "GET", "analytics/dashboard", 200)
        
        if success and analytics:
            # Check overview data
            overview = analytics.get("overview", {})
            print(f"   📈 Overview - Total Reviews: {overview.get('total_reviews', 0)}")
            print(f"   ⭐ Average Rating: {overview.get('avg_rating', 0)}")
            print(f"   📝 Response Rate: {overview.get('response_rate', 0)}%")
            print(f"   ⏳ Pending: {overview.get('pending', 0)}")
            
            # Check rating distribution
            rating_dist = analytics.get("rating_distribution", {})
            if rating_dist:
                print(f"   📊 Rating Distribution: {dict(rating_dist)}")
            
            # Check sentiment distribution
            sentiment_dist = analytics.get("sentiment_distribution", {})
            if sentiment_dist:
                print(f"   🧠 Sentiment Distribution: {dict(sentiment_dist)}")
            
            # Check urgency distribution
            urgency_dist = analytics.get("urgency_distribution", {})
            if urgency_dist:
                print(f"   🚨 Urgency Distribution: {dict(urgency_dist)}")
            
            # Check platform stats
            platform_stats = analytics.get("platform_stats", [])
            if platform_stats:
                print(f"   🏢 Platform Stats: {len(platform_stats)} platforms")
            
            # Check top topics
            top_topics = analytics.get("top_topics", [])
            if top_topics:
                print(f"   🏷️ Top Topics: {len(top_topics)} topics found")
            
            # Check priority queue
            priority_queue = analytics.get("priority_queue", [])
            if priority_queue:
                print(f"   🔥 Priority Queue: {len(priority_queue)} urgent reviews")
            
            # Check common issues and praises
            common_issues = analytics.get("common_issues", [])
            common_praises = analytics.get("common_praises", [])
            print(f"   ⚠️ Common Issues: {len(common_issues)} identified")
            print(f"   ✨ Common Praises: {len(common_praises)} identified")
        
        return success

    def test_competitor_benchmarking(self):
        """Test competitor benchmarking endpoints - NEW FEATURE"""
        print(f"\n🏆 Testing Competitor Benchmarking Feature...")
        
        # 1. Clear existing competitors and seed demo data
        success, response = self.run_test("Seed Demo Competitors", "POST", "competitors/seed", 200)
        
        if success:
            print(f"   📊 {response.get('message', 'Competitors seeded')}")
        
        # 2. Get all competitors
        success, competitors = self.run_test("Get All Competitors", "GET", "competitors", 200)
        
        competitor_id = None
        if success and isinstance(competitors, list):
            print(f"   🏢 Found {len(competitors)} competitors")
            if len(competitors) > 0:
                competitor_id = competitors[0]["id"]
                comp = competitors[0]
                print(f"   📋 Sample: {comp.get('name', 'Unknown')} - {comp.get('avg_rating', 0)}/5")
        
        # 3. Add a new competitor
        new_competitor_data = {
            "name": "Test Competitor Hotel",
            "platform": "all",
            "avg_rating": 4.2,
            "total_reviews": 500,
            "response_rate": 75.0
        }
        
        success, new_competitor = self.run_test(
            "Add New Competitor", 
            "POST", 
            "competitors", 
            200, 
            data=new_competitor_data
        )
        
        created_competitor_id = None
        if success and new_competitor.get("id"):
            created_competitor_id = new_competitor["id"]
            print(f"   ✅ Created competitor: {new_competitor.get('name', 'Unknown')}")
        
        # 4. Update competitor
        if created_competitor_id:
            update_data = {
                "name": "Updated Test Competitor",
                "avg_rating": 4.5,
                "total_reviews": 600,
                "response_rate": 80.0
            }
            
            success, updated = self.run_test(
                "Update Competitor", 
                "PUT", 
                f"competitors/{created_competitor_id}", 
                200, 
                data=update_data
            )
            
            if success:
                print(f"   📝 Updated competitor: {updated.get('name', 'Unknown')}")
        
        # 5. Get benchmark comparison
        success, benchmark = self.run_test("Get Competitor Benchmark", "GET", "competitors/benchmark", 200)
        
        if success and benchmark:
            your_hotel = benchmark.get("your_hotel", {})
            ranking = benchmark.get("ranking", {})
            competitors_list = benchmark.get("competitors", [])
            
            print(f"   🏨 Your Hotel - Rating: {your_hotel.get('avg_rating', 0)}/5")
            print(f"   📊 Your Hotel - Reviews: {your_hotel.get('total_reviews', 0)}")
            print(f"   📝 Your Hotel - Response Rate: {your_hotel.get('response_rate', 0)}%")
            print(f"   🏆 Rating Rank: #{ranking.get('rating_rank', 'N/A')} of {ranking.get('total_competitors', 'N/A')}")
            print(f"   📈 Response Rate Rank: #{ranking.get('response_rate_rank', 'N/A')}")
            print(f"   🏢 Competitors in benchmark: {len(competitors_list)}")
        
        # 6. Delete created competitor
        if created_competitor_id:
            success, delete_response = self.run_test(
                "Delete Competitor", 
                "DELETE", 
                f"competitors/{created_competitor_id}", 
                200
            )
            
            if success:
                print(f"   🗑️ Competitor deleted: {delete_response.get('message', 'success')}")
        
        return True

    def test_scheduled_reports(self):
        """Test scheduled reports endpoints - NEW FEATURE"""
        print(f"\n📊 Testing Scheduled Reports Feature...")
        
        # 1. Get current report settings
        success, settings = self.run_test("Get Report Settings", "GET", "reports/settings", 200)
        
        if success:
            print(f"   📋 Current settings: enabled={settings.get('enabled', False)}, email={settings.get('email', 'none')}")
            print(f"   📅 Frequency: {settings.get('frequency', 'weekly')}")
            print(f"   🏆 Include competitors: {settings.get('include_competitor_comparison', False)}")
            print(f"   🧠 Include sentiment: {settings.get('include_sentiment_summary', False)}")
            print(f"   📋 Include actions: {settings.get('include_action_items', False)}")
        
        # 2. Update report settings
        settings_data = {
            "email": "test@hotel.com",
            "frequency": "weekly",
            "include_competitor_comparison": True,
            "include_sentiment_summary": True,
            "include_action_items": True,
            "enabled": True
        }
        
        success, response = self.run_test(
            "Update Report Settings", 
            "PUT", 
            "reports/settings", 
            200, 
            data=settings_data
        )
        
        if success:
            print(f"   ✅ Settings updated: enabled={response.get('enabled', False)}")
            print(f"   📧 Email: {response.get('email', 'none')}")
        
        # 3. Get report preview
        success, preview = self.run_test("Get Report Preview", "GET", "reports/preview", 200)
        
        if success and preview.get("html"):
            html_content = preview["html"]
            print(f"   📄 Preview generated: {len(html_content)} characters")
            print(f"   📊 Contains metrics: {'total_reviews' in html_content}")
            print(f"   ⭐ Contains ratings: {'Rating Distribution' in html_content}")
            print(f"   🏆 Contains competitors: {'Competitive Position' in html_content}")
            print(f"   📋 Contains actions: {'Action Items' in html_content}")
        
        # 4. Send report now
        success, send_response = self.run_test("Send Report Now", "POST", "reports/send-now", 200)
        
        if success:
            status = send_response.get("status", "unknown")
            message = send_response.get("message", "")
            print(f"   📤 Send status: {status}")
            print(f"   💬 Message: {message}")
        
        # 5. Get report log
        success, log = self.run_test("Get Report Log", "GET", "reports/log", 200)
        
        if success and isinstance(log, list):
            print(f"   📜 Report log entries: {len(log)}")
            if len(log) > 0:
                latest = log[0]
                print(f"   📧 Latest: {latest.get('email', 'unknown')} - {latest.get('status', 'unknown')}")
        
        return True

    def test_platform_integrations(self):
        """Test platform integrations endpoints"""
        print("   Testing platform integrations...")
        
        # Test 1: Get all integrations
        success, response = self.run_test(
            "Get Platform Integrations",
            "GET", "integrations", 200
        )
        
        if success:
            platforms = [item.get('platform') for item in response]
            expected_platforms = ["google", "booking.com", "tripadvisor", "airbnb", "expedia", "trip.com"]
            
            if all(platform in platforms for platform in expected_platforms):
                self.log_test("Platform Integrations - All 6 platforms present", True, 
                             f"Found platforms: {platforms}")
            else:
                missing = set(expected_platforms) - set(platforms)
                self.log_test("Platform Integrations - Missing platforms", False, 
                             f"Missing: {missing}")
        else:
            self.log_test("Platform Integrations - Get integrations", False, "API call failed")
        
        # Test 2: Get requirements
        success, response = self.run_test(
            "Get Integration Requirements",
            "GET", "integrations/requirements", 200
        )
        
        if success:
            required_platforms = ["google", "booking.com", "tripadvisor", "airbnb", "expedia", "trip.com"]
            all_present = all(platform in response for platform in required_platforms)
            
            if all_present:
                self.log_test("Integration Requirements - All platforms", True, 
                             f"Requirements for {len(response)} platforms")
            else:
                missing = set(required_platforms) - set(response.keys())
                self.log_test("Integration Requirements - Missing platforms", False, 
                             f"Missing requirements for: {missing}")
                
            # Check if each platform has required fields
            for platform, req in response.items():
                if platform != "manual_import":
                    required_fields = ["name", "requirements", "fields_needed"]
                    missing_fields = [field for field in required_fields if field not in req]
                    if not missing_fields:
                        self.log_test(f"Requirements Structure - {platform}", True, 
                                     "All required fields present")
                    else:
                        self.log_test(f"Requirements Structure - {platform}", False, 
                                     f"Missing fields: {missing_fields}")
        else:
            self.log_test("Integration Requirements - Get requirements", False, "API call failed")
        
        # Test 3: Manual import
        test_review = {
            "platform": "google",
            "guest_name": "Test Integration Guest",
            "rating": 4,
            "review_text": "This is a test review imported manually for integration testing.",
            "stay_date": "January 2026",
            "room_type": "Test Room"
        }
        
        success, response = self.run_test(
            "Manual Review Import",
            "POST", "integrations/import", 200,
            data=[test_review]
        )
        
        if success:
            imported = response.get('imported', 0)
            if imported > 0:
                self.log_test("Manual Import - Import review", True, 
                             f"Successfully imported {imported} review(s)")
            else:
                self.log_test("Manual Import - Import review", False, 
                             "No reviews imported")
        else:
            self.log_test("Manual Import - Import review", False, "API call failed")
        
        # Test 4: Platform sync (test all platforms)
        platforms_to_test = ["google", "booking.com", "tripadvisor", "airbnb", "expedia", "trip.com"]
        
        for platform in platforms_to_test:
            success, response = self.run_test(
                f"Platform Sync - {platform}",
                "POST", f"integrations/{platform}/sync", None  # Don't expect specific status
            )
            
            # For platforms without credentials, we expect 400 with helpful message
            # For platforms with credentials, we expect 200 with sync results
            if success and response.get('reviews_synced') is not None:
                # Got 200 with sync response
                reviews_synced = response.get('reviews_synced', 0)
                errors = response.get('errors', [])
                status = response.get('status', 'unknown')
                
                if errors and any("requires" in error.lower() or "approval" in error.lower() for error in errors):
                    self.log_test(f"Platform Sync - {platform} (Expected)", True, 
                                 f"Returned helpful message: {errors[0][:100]}...")
                elif reviews_synced > 0:
                    self.log_test(f"Platform Sync - {platform}", True, 
                                 f"Synced {reviews_synced} reviews")
                else:
                    self.log_test(f"Platform Sync - {platform}", True, 
                                 f"Sync completed with status: {status}")
            else:
                # Check if it's the expected 400 error for unconfigured credentials
                try:
                    import requests
                    url = f"{self.api_url}/integrations/{platform}/sync"
                    resp = requests.post(url, headers={'Content-Type': 'application/json'}, timeout=30)
                    if resp.status_code == 400 and "credentials not configured" in resp.text.lower():
                        self.log_test(f"Platform Sync - {platform} (Expected)", True, 
                                     "Correctly returned 400 - credentials not configured")
                    else:
                        self.log_test(f"Platform Sync - {platform}", False, 
                                     f"Unexpected response: {resp.status_code} - {resp.text[:100]}")
                except Exception as e:
                    self.log_test(f"Platform Sync - {platform}", False, f"Request failed: {str(e)}")

        # Test 5: Configuration wizard endpoints
        print("   Testing configuration wizard...")
        
        # Test Google configuration
        google_config = {
            "platform": "google",
            "credentials": {
                "client_id": "test-client-id.apps.googleusercontent.com",
                "client_secret": "GOCSPX-test-secret",
                "refresh_token": "1//test-refresh-token",
                "location_id": "accounts/123/locations/456",
                "property_name": "Test Hotel"
            },
            "location_id": "accounts/123/locations/456",
            "property_name": "Test Hotel"
        }
        
        success, response = self.run_test(
            "Configure Google Integration",
            "PUT", "integrations/google/configure", 200,
            data=google_config
        )
        
        if success:
            self.log_test("Configuration Wizard - Google", True, 
                         f"Google integration configured successfully")
        else:
            self.log_test("Configuration Wizard - Google", False, "Failed to configure Google")
        
        # Test Booking.com configuration
        booking_config = {
            "platform": "booking.com",
            "credentials": {
                "username": "test-username",
                "password": "test-password",
                "property_id": "12345",
                "property_name": "Test Hotel"
            },
            "location_id": "12345",
            "property_name": "Test Hotel"
        }
        
        success, response = self.run_test(
            "Configure Booking.com Integration",
            "PUT", "integrations/booking.com/configure", 200,
            data=booking_config
        )
        
        if success:
            self.log_test("Configuration Wizard - Booking.com", True, 
                         f"Booking.com integration configured successfully")
        else:
            self.log_test("Configuration Wizard - Booking.com", False, "Failed to configure Booking.com")

        # Verify configuration was saved by checking integrations status
        success, response = self.run_test(
            "Verify Configuration Saved",
            "GET", "integrations", 200
        )
        
        if success:
            configured_platforms = [item for item in response if item.get('credentials_configured')]
            if len(configured_platforms) >= 2:
                self.log_test("Configuration Verification", True, 
                             f"Found {len(configured_platforms)} configured platforms")
            else:
                self.log_test("Configuration Verification", False, 
                             f"Expected at least 2 configured platforms, found {len(configured_platforms)}")

    def run_comprehensive_test(self):
        """Run all tests in sequence"""
        print("🏨 Hotel Review Management API Testing")
        print("=" * 50)
        print(f"Testing against: {self.base_url}")
        print()

        # 1. Test basic connectivity
        print("1️⃣ Testing Basic Connectivity...")
        if not self.test_root_endpoint()[0]:
            print("❌ Cannot connect to API. Stopping tests.")
            return False

        # 2. Test status endpoints
        print("\n2️⃣ Testing Status Endpoints...")
        self.test_status_endpoints()

        # 3. Seed reviews
        print("\n3️⃣ Seeding Mock Reviews...")
        if not self.test_seed_reviews():
            print("❌ Failed to seed reviews. Some tests may fail.")

        # 4. Test review retrieval
        print("\n4️⃣ Testing Review Retrieval...")
        success, reviews = self.test_get_reviews()
        
        if success and reviews and len(reviews) > 0:
            # Test single review
            first_review_id = reviews[0]["id"]
            self.test_single_review(first_review_id)
            
            # 5. Test AI response generation on existing review
            print("\n5️⃣ Testing AI Response Generation...")
            ai_success, ai_count = self.test_ai_response_generation(first_review_id)
            
            if ai_success:
                print(f"   🎉 AI generation working! {ai_count}/3 tones successful")
            else:
                print("   ⚠️ AI generation failed - check EMERGENT_LLM_KEY")
            
            # 6. Test response submission
            print("\n6️⃣ Testing Response Submission...")
            self.test_submit_response(first_review_id)

        # 7. Test review creation
        print("\n7️⃣ Testing Review Creation...")
        self.test_create_review()

        # 8. Test stats
        print("\n8️⃣ Testing Statistics...")
        self.test_stats_summary()

        # 9. Test notification settings
        print("\n9️⃣ Testing Notification Settings...")
        self.test_notification_settings()

        # 10. Test notification trigger
        print("\n🔟 Testing Notification Trigger...")
        self.test_notification_trigger()

        # 11. Test notification test endpoint
        print("\n1️⃣1️⃣ Testing Test Notification...")
        self.test_notification_test_endpoint()

        # 12. Test response templates feature
        print("\n1️⃣2️⃣ Testing Response Templates Feature...")
        self.test_response_templates()

        # 13. Test sentiment analysis features
        print("\n1️⃣3️⃣ Testing Sentiment Analysis Features...")
        self.test_sentiment_analysis()

        # 14. Test analytics dashboard
        print("\n1️⃣4️⃣ Testing Analytics Dashboard...")
        self.test_analytics_dashboard()

        # 15. Test competitor benchmarking
        print("\n1️⃣5️⃣ Testing Competitor Benchmarking...")
        self.test_competitor_benchmarking()

        # 16. Test scheduled reports feature
        print("\n1️⃣6️⃣ Testing Scheduled Reports Feature...")
        self.test_scheduled_reports()

        # 17. Test platform integrations feature
        print("\n1️⃣7️⃣ Testing Platform Integrations Feature...")
        self.test_platform_integrations()

        # Print summary
        print("\n" + "=" * 50)
        print("📊 TEST SUMMARY")
        print("=" * 50)
        print(f"Tests Run: {self.tests_run}")
        print(f"Tests Passed: {self.tests_passed}")
        print(f"Success Rate: {(self.tests_passed/self.tests_run*100):.1f}%")
        
        if self.tests_passed == self.tests_run:
            print("🎉 ALL TESTS PASSED!")
            return True
        else:
            print(f"⚠️ {self.tests_run - self.tests_passed} tests failed")
            return False

def main():
    """Main test execution"""
    tester = ReviewAPITester()
    success = tester.run_comprehensive_test()
    
    # Save detailed results
    with open("/app/backend_test_results.json", "w") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "total_tests": tester.tests_run,
            "passed_tests": tester.tests_passed,
            "success_rate": (tester.tests_passed/tester.tests_run*100) if tester.tests_run > 0 else 0,
            "all_passed": success,
            "detailed_results": tester.test_results
        }, f, indent=2)
    
    print(f"\n📄 Detailed results saved to: /app/backend_test_results.json")
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())