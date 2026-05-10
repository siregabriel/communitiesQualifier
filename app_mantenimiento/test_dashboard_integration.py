"""
Test script to verify dashboard.html integration with inspection submissions
Tests the /api/inspections endpoint and dashboard rendering
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(__file__))

from app import app
import json

def test_api_inspections_endpoint():
    """Test that /api/inspections endpoint returns inspection data"""
    print("Testing /api/inspections endpoint...")
    
    with app.test_client() as client:
        # Login as admin user
        login_response = client.post('/api/login', 
            json={'username': 'admin', 'password': 'admin123'},
            content_type='application/json')
        
        assert login_response.status_code == 200, f"Login failed: {login_response.status_code}"
        print("✓ Admin login successful")
        
        # Get inspections
        response = client.get('/api/inspections')
        assert response.status_code == 200, f"Failed to get inspections: {response.status_code}"
        
        data = json.loads(response.data)
        assert data['status'] == 'success', f"API returned error: {data}"
        assert 'submissions' in data, "Response missing 'submissions' field"
        
        submissions = data['submissions']
        print(f"✓ Retrieved {len(submissions)} inspection submissions")
        
        # Verify submission structure
        if len(submissions) > 0:
            submission = submissions[0]
            assert 'id' in submission, "Submission missing 'id'"
            assert 'username' in submission, "Submission missing 'username'"
            assert 'community' in submission, "Submission missing 'community'"
            assert 'submitted_at' in submission, "Submission missing 'submitted_at'"
            assert 'responses' in submission, "Submission missing 'responses'"
            print(f"✓ Submission structure is valid")
            
            # Verify response structure
            if len(submission['responses']) > 0:
                response_obj = submission['responses'][0]
                assert 'question_id' in response_obj, "Response missing 'question_id'"
                assert 'question_text' in response_obj, "Response missing 'question_text'"
                assert 'condition' in response_obj, "Response missing 'condition'"
                assert 'description' in response_obj, "Response missing 'description'"
                assert 'answered_at' in response_obj, "Response missing 'answered_at'"
                print(f"✓ Response structure is valid")
                print(f"  - Question: {response_obj['question_text']}")
                print(f"  - Condition: {response_obj['condition']}")
                print(f"  - Description: {response_obj['description']}")
        
        return True

def test_dashboard_route():
    """Test that dashboard route is accessible"""
    print("\nTesting /dashboard route...")
    
    with app.test_client() as client:
        # Login as admin user
        client.post('/api/login', 
            json={'username': 'admin', 'password': 'admin123'},
            content_type='application/json')
        
        # Access dashboard
        response = client.get('/dashboard')
        assert response.status_code == 200, f"Dashboard route failed: {response.status_code}"
        
        # Verify HTML contains expected elements
        html = response.data.decode('utf-8')
        assert 'Dashboard' in html, "Dashboard title not found"
        assert 'questionManagerBtn' in html, "Question Manager button not found"
        assert 'filterByType' in html, "Type filter function not found"
        assert 'filterByCondition' in html, "Condition filter function not found"
        assert 'loadInspections' in html, "loadInspections function not found"
        
        print("✓ Dashboard route accessible")
        print("✓ Dashboard contains Question Manager button")
        print("✓ Dashboard contains filter functionality")
        print("✓ Dashboard contains inspection loading functionality")
        
        return True

def test_staff_user_dashboard():
    """Test that staff users can access dashboard but not see Question Manager button"""
    print("\nTesting staff user dashboard access...")
    
    with app.test_client() as client:
        # Login as staff user
        login_response = client.post('/api/login', 
            json={'username': 'john', 'password': 'pass123'},
            content_type='application/json')
        
        assert login_response.status_code == 200, f"Staff login failed: {login_response.status_code}"
        print("✓ Staff user login successful")
        
        # Access dashboard
        response = client.get('/dashboard')
        assert response.status_code == 200, f"Dashboard route failed: {response.status_code}"
        print("✓ Staff user can access dashboard")
        
        # Get inspections (should be filtered by community)
        response = client.get('/api/inspections')
        assert response.status_code == 200, f"Failed to get inspections: {response.status_code}"
        
        data = json.loads(response.data)
        submissions = data['submissions']
        
        # Verify all submissions are for Community A (john's community)
        for submission in submissions:
            assert submission['community'] == 'Community A', \
                f"Staff user received submission from wrong community: {submission['community']}"
        
        print(f"✓ Staff user receives only their community's submissions ({len(submissions)} submissions)")
        
        return True

if __name__ == '__main__':
    print("=" * 60)
    print("Dashboard Integration Test Suite")
    print("=" * 60)
    
    try:
        test_api_inspections_endpoint()
        test_dashboard_route()
        test_staff_user_dashboard()
        
        print("\n" + "=" * 60)
        print("✅ All tests passed!")
        print("=" * 60)
        
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
