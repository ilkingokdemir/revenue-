#!/usr/bin/env python3
"""
Comprehensive Backend API Testing for Hotel Review Management System
Tests all endpoints including AI response generation via GPT-5.2
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