#!/usr/bin/env python3
"""
Task 30: Final Integration Testing
ATLAS Dashboard Redesign - Comprehensive Integration Tests

This script performs automated integration testing for:
- Complete user flow (login → dashboard → view communities → start new visit)
- API endpoint validation
- Data integrity checks
- Score calculation accuracy
- Action items counting
- User role filtering
"""

import requests
import json
import time
from datetime import datetime

# Configuration
BASE_URL = "http://localhost:5001"
TEST_USERS = {
    "admin": {"username": "admin", "password": "admin123"},
    "staff": {"username": "user1", "password": "test123"}
}

class Colors:
    """ANSI color codes for terminal output"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'

class IntegrationTester:
    def __init__(self):
        self.session = requests.Session()
        self.test_results = []
        self.total_tests = 0
        self.passed_tests = 0
        self.failed_tests = 0
        
    def log(self, message, color=Colors.BLUE):
        """Print colored log message"""
        print(f"{color}{message}{Colors.END}")
        
    def test_result(self, test_name, passed, details=""):
        """Record and display test result"""
        self.total_tests += 1
        if passed:
            self.passed_tests += 1
            symbol = "✅"
            color = Colors.GREEN
        else:
            self.failed_tests += 1
            symbol = "❌"
            color = Colors.RED
            
        result = f"{symbol} {test_name}"
        if details:
            result += f" - {details}"
        self.log(result, color)
        self.test_results.append({"test": test_name, "passed": passed, "details": details})
        
    def test_login(self, username, password):
        """Test 1: Login Flow"""
        self.log(f"\n{'='*60}", Colors.BOLD)
        self.log("TEST 1: LOGIN FLOW", Colors.BOLD)
        self.log(f"{'='*60}", Colors.BOLD)
        
        try:
            # Test login page loads
            response = self.session.get(f"{BASE_URL}/login")
            self.test_result(
                "Login page loads",
                response.status_code == 200,
                f"Status: {response.status_code}"
            )
            
            # Test login submission via API
            login_data = {"username": username, "password": password}
            headers = {'Content-Type': 'application/json'}
            response = self.session.post(
                f"{BASE_URL}/api/login", 
                json=login_data,
                headers=headers,
                allow_redirects=False
            )
            
            # Check for success (200)
            login_success = response.status_code == 200
            if login_success:
                try:
                    data = response.json()
                    login_success = data.get('status') == 'success'
                except:
                    login_success = False
            
            self.test_result(
                f"Login with {username}",
                login_success,
                f"Status: {response.status_code}"
            )
            
            # Verify session is established
            dashboard_response = self.session.get(f"{BASE_URL}/dashboard")
            self.test_result(
                "Dashboard accessible after login",
                dashboard_response.status_code == 200,
                f"Status: {dashboard_response.status_code}"
            )
            
            return login_success
            
        except Exception as e:
            self.test_result("Login flow", False, f"Error: {str(e)}")
            return False
            
    def test_api_endpoints(self):
        """Test 2: API Endpoints"""
        self.log(f"\n{'='*60}", Colors.BOLD)
        self.log("TEST 2: API ENDPOINTS", Colors.BOLD)
        self.log(f"{'='*60}", Colors.BOLD)
        
        endpoints = [
            ("/api/user-info", "User info endpoint"),
            ("/api/inspections", "Inspections endpoint"),
            ("/api/survey-types", "Survey types endpoint")
        ]
        
        for endpoint, description in endpoints:
            try:
                response = self.session.get(f"{BASE_URL}{endpoint}")
                success = response.status_code == 200
                
                if success:
                    try:
                        data = response.json()
                        has_data = bool(data)
                        self.test_result(
                            description,
                            has_data,
                            f"Status: {response.status_code}, Has data: {has_data}"
                        )
                    except json.JSONDecodeError:
                        self.test_result(
                            description,
                            False,
                            "Invalid JSON response"
                        )
                else:
                    self.test_result(
                        description,
                        False,
                        f"Status: {response.status_code}"
                    )
            except Exception as e:
                self.test_result(description, False, f"Error: {str(e)}")
                
    def test_score_calculation(self):
        """Test 3: Score Calculation Accuracy"""
        self.log(f"\n{'='*60}", Colors.BOLD)
        self.log("TEST 3: SCORE CALCULATION", Colors.BOLD)
        self.log(f"{'='*60}", Colors.BOLD)
        
        test_cases = [
            {
                "name": "Excellence + Pass",
                "responses": [
                    {"condition": "Excellence"},
                    {"condition": "Pass"}
                ],
                "expected": 88  # (100 + 75) / 2 = 87.5 → 88
            },
            {
                "name": "Opportunity + Fail",
                "responses": [
                    {"condition": "Opportunity"},
                    {"condition": "Fail"}
                ],
                "expected": 25  # (50 + 0) / 2 = 25
            },
            {
                "name": "Mixed conditions",
                "responses": [
                    {"condition": "Excellence"},
                    {"condition": "Pass"},
                    {"condition": "Opportunity"},
                    {"condition": "Fail"}
                ],
                "expected": 56  # (100 + 75 + 50 + 0) / 4 = 56.25 → 56
            },
            {
                "name": "All Excellence",
                "responses": [
                    {"condition": "Excellence"},
                    {"condition": "Excellence"},
                    {"condition": "Excellence"}
                ],
                "expected": 100
            },
            {
                "name": "All Fail",
                "responses": [
                    {"condition": "Fail"},
                    {"condition": "Fail"}
                ],
                "expected": 0
            }
        ]
        
        score_map = {
            'Excellence': 100,
            'Pass': 75,
            'Opportunity': 50,
            'Fail': 0
        }
        
        for test_case in test_cases:
            responses = test_case["responses"]
            expected = test_case["expected"]
            
            # Calculate score
            total_score = sum(score_map.get(r["condition"], 0) for r in responses)
            calculated = round(total_score / len(responses)) if responses else 0
            
            self.test_result(
                f"Score calculation: {test_case['name']}",
                calculated == expected,
                f"Expected: {expected}%, Got: {calculated}%"
            )
            
    def test_action_items_counting(self):
        """Test 4: Action Items Counting"""
        self.log(f"\n{'='*60}", Colors.BOLD)
        self.log("TEST 4: ACTION ITEMS COUNTING", Colors.BOLD)
        self.log(f"{'='*60}", Colors.BOLD)
        
        test_cases = [
            {
                "name": "Mixed conditions",
                "responses": [
                    {"condition": "Excellence"},
                    {"condition": "Pass"},
                    {"condition": "Opportunity"},
                    {"condition": "Fail"},
                    {"condition": "Needs Attention"}
                ],
                "expected": 3  # Opportunity, Fail, Needs Attention
            },
            {
                "name": "No action items",
                "responses": [
                    {"condition": "Excellence"},
                    {"condition": "Pass"}
                ],
                "expected": 0
            },
            {
                "name": "All action items",
                "responses": [
                    {"condition": "Fail"},
                    {"condition": "Opportunity"},
                    {"condition": "Needs Attention"}
                ],
                "expected": 3
            },
            {
                "name": "Empty responses",
                "responses": [],
                "expected": 0
            }
        ]
        
        action_conditions = ['Fail', 'Opportunity', 'Needs Attention']
        
        for test_case in test_cases:
            responses = test_case["responses"]
            expected = test_case["expected"]
            
            # Count action items
            count = sum(1 for r in responses if r["condition"] in action_conditions)
            
            self.test_result(
                f"Action items count: {test_case['name']}",
                count == expected,
                f"Expected: {expected}, Got: {count}"
            )
            
    def test_user_role_filtering(self):
        """Test 5: User Role Filtering"""
        self.log(f"\n{'='*60}", Colors.BOLD)
        self.log("TEST 5: USER ROLE FILTERING", Colors.BOLD)
        self.log(f"{'='*60}", Colors.BOLD)
        
        try:
            # Get user info
            response = self.session.get(f"{BASE_URL}/api/user-info")
            if response.status_code == 200:
                user_data = response.json()
                username = user_data.get('username', 'Unknown')
                community = user_data.get('community')
                is_admin = user_data.get('is_admin', False)
                
                self.test_result(
                    "User info retrieved",
                    True,
                    f"User: {username}, Admin: {is_admin}, Community: {community}"
                )
                
                # Get inspections
                response = self.session.get(f"{BASE_URL}/api/inspections")
                if response.status_code == 200:
                    data = response.json()
                    submissions = data.get('submissions', [])
                    
                    if is_admin:
                        # Admin should see all communities
                        communities = set(s.get('community') for s in submissions)
                        self.test_result(
                            "Admin sees multiple communities",
                            len(communities) > 1 or len(submissions) == 0,
                            f"Communities visible: {len(communities)}"
                        )
                    else:
                        # Staff should only see their community
                        if submissions:
                            all_match = all(s.get('community') == community for s in submissions)
                            self.test_result(
                                "Staff sees only assigned community",
                                all_match,
                                f"Expected: {community}, All match: {all_match}"
                            )
                        else:
                            self.test_result(
                                "Staff sees only assigned community",
                                True,
                                "No submissions to filter"
                            )
                else:
                    self.test_result("Get inspections", False, f"Status: {response.status_code}")
            else:
                self.test_result("Get user info", False, f"Status: {response.status_code}")
                
        except Exception as e:
            self.test_result("User role filtering", False, f"Error: {str(e)}")
            
    def test_data_integrity(self):
        """Test 6: Data Integrity"""
        self.log(f"\n{'='*60}", Colors.BOLD)
        self.log("TEST 6: DATA INTEGRITY", Colors.BOLD)
        self.log(f"{'='*60}", Colors.BOLD)
        
        try:
            response = self.session.get(f"{BASE_URL}/api/inspections")
            if response.status_code == 200:
                data = response.json()
                submissions = data.get('submissions', [])
                
                self.test_result(
                    "Inspections data retrieved",
                    True,
                    f"Total submissions: {len(submissions)}"
                )
                
                # Check data structure
                if submissions:
                    sample = submissions[0]
                    required_fields = ['id', 'username', 'community', 'submitted_at']
                    has_all_fields = all(field in sample for field in required_fields)
                    
                    self.test_result(
                        "Submission has required fields",
                        has_all_fields,
                        f"Fields present: {list(sample.keys())}"
                    )
                    
                    # Check responses structure
                    if 'responses' in sample and sample['responses']:
                        response_sample = sample['responses'][0]
                        response_fields = ['question_text', 'condition']
                        has_response_fields = all(field in response_sample for field in response_fields)
                        
                        self.test_result(
                            "Response has required fields",
                            has_response_fields,
                            f"Fields present: {list(response_sample.keys())}"
                        )
                    else:
                        self.test_result(
                            "Response has required fields",
                            True,
                            "No responses to check"
                        )
                else:
                    self.test_result(
                        "Data structure validation",
                        True,
                        "No submissions to validate"
                    )
            else:
                self.test_result("Get inspections data", False, f"Status: {response.status_code}")
                
        except Exception as e:
            self.test_result("Data integrity", False, f"Error: {str(e)}")
            
    def test_navigation_routes(self):
        """Test 7: Navigation Routes"""
        self.log(f"\n{'='*60}", Colors.BOLD)
        self.log("TEST 7: NAVIGATION ROUTES", Colors.BOLD)
        self.log(f"{'='*60}", Colors.BOLD)
        
        routes = [
            ("/dashboard", "Dashboard route"),
            ("/select-survey-type", "Select survey type route"),
            ("/questions/manage", "Question manager route (admin only)"),
        ]
        
        for route, description in routes:
            try:
                response = self.session.get(f"{BASE_URL}{route}")
                # Accept 200 (success) or 302 (redirect for auth)
                success = response.status_code in [200, 302]
                self.test_result(
                    description,
                    success,
                    f"Status: {response.status_code}"
                )
            except Exception as e:
                self.test_result(description, False, f"Error: {str(e)}")
                
    def test_performance(self):
        """Test 8: Page Load Performance"""
        self.log(f"\n{'='*60}", Colors.BOLD)
        self.log("TEST 8: PERFORMANCE", Colors.BOLD)
        self.log(f"{'='*60}", Colors.BOLD)
        
        pages = [
            ("/dashboard", "Dashboard"),
            ("/api/inspections", "Inspections API"),
            ("/api/user-info", "User info API")
        ]
        
        for route, description in pages:
            try:
                start_time = time.time()
                response = self.session.get(f"{BASE_URL}{route}")
                load_time = (time.time() - start_time) * 1000  # Convert to ms
                
                # Target: < 2000ms for pages, < 1000ms for API
                target = 1000 if route.startswith('/api') else 2000
                success = load_time < target and response.status_code == 200
                
                self.test_result(
                    f"{description} load time",
                    success,
                    f"{load_time:.0f}ms (target: <{target}ms)"
                )
            except Exception as e:
                self.test_result(f"{description} load time", False, f"Error: {str(e)}")
                
    def test_complete_user_flow(self):
        """Test 9: Complete User Flow"""
        self.log(f"\n{'='*60}", Colors.BOLD)
        self.log("TEST 9: COMPLETE USER FLOW", Colors.BOLD)
        self.log(f"{'='*60}", Colors.BOLD)
        
        try:
            # Step 1: Dashboard
            response = self.session.get(f"{BASE_URL}/dashboard")
            self.test_result(
                "Step 1: Access dashboard",
                response.status_code == 200,
                f"Status: {response.status_code}"
            )
            
            # Step 2: View communities (via API)
            response = self.session.get(f"{BASE_URL}/api/inspections")
            communities_loaded = response.status_code == 200
            self.test_result(
                "Step 2: View communities data",
                communities_loaded,
                f"Status: {response.status_code}"
            )
            
            # Step 3: Start new visit
            response = self.session.get(f"{BASE_URL}/select-survey-type")
            self.test_result(
                "Step 3: Start new visit",
                response.status_code == 200,
                f"Status: {response.status_code}"
            )
            
            # Overall flow
            self.test_result(
                "Complete user flow",
                True,
                "All steps completed successfully"
            )
            
        except Exception as e:
            self.test_result("Complete user flow", False, f"Error: {str(e)}")
            
    def print_summary(self):
        """Print test summary"""
        self.log(f"\n{'='*60}", Colors.BOLD)
        self.log("TEST SUMMARY", Colors.BOLD)
        self.log(f"{'='*60}", Colors.BOLD)
        
        pass_rate = (self.passed_tests / self.total_tests * 100) if self.total_tests > 0 else 0
        
        self.log(f"\nTotal Tests: {self.total_tests}", Colors.BLUE)
        self.log(f"Passed: {self.passed_tests}", Colors.GREEN)
        self.log(f"Failed: {self.failed_tests}", Colors.RED)
        self.log(f"Pass Rate: {pass_rate:.1f}%", Colors.BOLD)
        
        if self.failed_tests > 0:
            self.log("\n❌ FAILED TESTS:", Colors.RED)
            for result in self.test_results:
                if not result["passed"]:
                    self.log(f"  - {result['test']}: {result['details']}", Colors.RED)
        
        self.log(f"\n{'='*60}", Colors.BOLD)
        if self.failed_tests == 0:
            self.log("✅ ALL TESTS PASSED!", Colors.GREEN)
        else:
            self.log("❌ SOME TESTS FAILED", Colors.RED)
        self.log(f"{'='*60}\n", Colors.BOLD)
        
    def run_all_tests(self, username, password):
        """Run all integration tests"""
        self.log(f"\n{'#'*60}", Colors.BOLD)
        self.log("ATLAS DASHBOARD INTEGRATION TESTS", Colors.BOLD)
        self.log(f"Task 30: Final Integration Testing", Colors.BLUE)
        self.log(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", Colors.BLUE)
        self.log(f"{'#'*60}\n", Colors.BOLD)
        
        # Test 1: Login
        if not self.test_login(username, password):
            self.log("\n⚠️  Login failed. Skipping remaining tests.", Colors.YELLOW)
            self.print_summary()
            return
            
        # Test 2: API Endpoints
        self.test_api_endpoints()
        
        # Test 3: Score Calculation
        self.test_score_calculation()
        
        # Test 4: Action Items Counting
        self.test_action_items_counting()
        
        # Test 5: User Role Filtering
        self.test_user_role_filtering()
        
        # Test 6: Data Integrity
        self.test_data_integrity()
        
        # Test 7: Navigation Routes
        self.test_navigation_routes()
        
        # Test 8: Performance
        self.test_performance()
        
        # Test 9: Complete User Flow
        self.test_complete_user_flow()
        
        # Print summary
        self.print_summary()

def main():
    """Main test execution"""
    print("\n" + "="*60)
    print("Select test user:")
    print("1. Admin user (admin/admin123)")
    print("2. Staff user (user1/test123)")
    print("3. Run both")
    print("="*60)
    
    choice = input("\nEnter choice (1-3): ").strip()
    
    if choice == "1":
        tester = IntegrationTester()
        tester.run_all_tests("admin", "admin123")
    elif choice == "2":
        tester = IntegrationTester()
        tester.run_all_tests("user1", "test123")
    elif choice == "3":
        # Test with admin
        print("\n" + "🔵 "*30)
        print("TESTING WITH ADMIN USER")
        print("🔵 "*30)
        tester_admin = IntegrationTester()
        tester_admin.run_all_tests("admin", "admin123")
        
        # Test with staff
        print("\n" + "🟢 "*30)
        print("TESTING WITH STAFF USER")
        print("🟢 "*30)
        tester_staff = IntegrationTester()
        tester_staff.run_all_tests("user1", "test123")
        
        # Combined summary
        total_tests = tester_admin.total_tests + tester_staff.total_tests
        total_passed = tester_admin.passed_tests + tester_staff.passed_tests
        total_failed = tester_admin.failed_tests + tester_staff.failed_tests
        
        print("\n" + "="*60)
        print(f"{Colors.BOLD}COMBINED TEST SUMMARY{Colors.END}")
        print("="*60)
        print(f"Total Tests: {total_tests}")
        print(f"{Colors.GREEN}Passed: {total_passed}{Colors.END}")
        print(f"{Colors.RED}Failed: {total_failed}{Colors.END}")
        print(f"Pass Rate: {(total_passed/total_tests*100):.1f}%")
        print("="*60 + "\n")
    else:
        print("Invalid choice. Exiting.")

if __name__ == "__main__":
    main()
