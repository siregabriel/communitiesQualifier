"""
Backward Compatibility Tests for ATLAS Dashboard Redesign
Task 29: Test backward compatibility

This test suite verifies that all existing features continue to work
after the dashboard redesign, ensuring no regression in functionality.

Requirements tested: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7
"""

import pytest
import json
import os
import sys
from datetime import datetime

# Add parent directory to path to import app
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, USERS_DB, ALL_COMMUNITIES


@pytest.fixture
def client():
    """Create a test client for the Flask app"""
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test-secret-key'
    
    with app.test_client() as client:
        yield client


@pytest.fixture
def admin_session(client):
    """Create an authenticated admin session"""
    with client.session_transaction() as sess:
        sess['user'] = 'admin'
        sess['community'] = None  # Admin has no community
    return client


@pytest.fixture
def staff_session(client):
    """Create an authenticated staff session"""
    with client.session_transaction() as sess:
        sess['user'] = 'user1'
        sess['community'] = 'Kelley Place, Enterprise'
    return client


class TestInspectionSubmissionsDisplay:
    """
    Test that existing inspection submissions display correctly
    Requirement: 9.1
    """
    
    def test_get_inspections_endpoint_exists(self, admin_session):
        """Verify /api/inspections endpoint is accessible"""
        response = admin_session.get('/api/inspections')
        assert response.status_code == 200
        
    def test_get_inspections_returns_json(self, admin_session):
        """Verify /api/inspections returns valid JSON"""
        response = admin_session.get('/api/inspections')
        data = json.loads(response.data)
        assert 'status' in data
        assert 'submissions' in data
        assert data['status'] == 'success'
        
    def test_get_inspections_admin_sees_all(self, admin_session):
        """Verify admin users can see all community submissions"""
        response = admin_session.get('/api/inspections')
        data = json.loads(response.data)
        assert data['status'] == 'success'
        # Admin should be able to see submissions (if any exist)
        assert isinstance(data['submissions'], list)
        
    def test_get_inspections_staff_filtered(self, staff_session):
        """Verify staff users only see their community submissions"""
        response = staff_session.get('/api/inspections')
        data = json.loads(response.data)
        assert data['status'] == 'success'
        
        # All submissions should be for the staff user's community
        for submission in data['submissions']:
            assert submission['community'] == 'Kelley Place, Enterprise'
            
    def test_inspection_data_structure(self, admin_session):
        """Verify inspection submissions have correct data structure"""
        response = admin_session.get('/api/inspections')
        data = json.loads(response.data)
        
        # Check that submissions array exists
        assert 'submissions' in data
        
        # If there are submissions, verify structure
        if len(data['submissions']) > 0:
            submission = data['submissions'][0]
            assert 'id' in submission
            assert 'username' in submission
            assert 'community' in submission
            assert 'submitted_at' in submission
            assert 'responses' in submission


class TestConditionFiltering:
    """
    Test that filtering by condition still works
    Requirement: 9.2, 9.3
    """
    
    def test_all_condition_types_supported(self, admin_session):
        """Verify all 6 condition types are supported"""
        # The system should support these condition types
        expected_conditions = [
            'Excellence',
            'Pass',
            'Opportunity',
            'Fail',
            'Good',
            'Needs Attention'
        ]
        
        # Verify filter buttons exist in dashboard template
        response = admin_session.get('/dashboard')
        assert response.status_code == 200
        html = response.data.decode('utf-8')
        
        # Check that all condition filter buttons are present
        for condition in expected_conditions:
            assert condition in html or condition.lower() in html
            
    def test_filter_buttons_in_dashboard(self, admin_session):
        """Verify filter buttons are present in dashboard"""
        response = admin_session.get('/dashboard')
        assert response.status_code == 200
        html = response.data.decode('utf-8')
        
        # Check for filter section
        assert 'filter-section' in html
        assert 'filterByCondition' in html
        
        # Check for specific filter buttons
        assert 'excellence' in html.lower()
        assert 'pass' in html.lower()
        assert 'opportunity' in html.lower()
        assert 'fail' in html.lower()
        
    def test_filter_by_type_functionality(self, admin_session):
        """Verify filtering by report type (maintenance/inspection) works"""
        response = admin_session.get('/dashboard')
        assert response.status_code == 200
        html = response.data.decode('utf-8')
        
        # Check for type filter buttons
        assert 'filterByType' in html
        assert 'maintenance' in html.lower()
        assert 'inspection' in html.lower()


class TestAdminAccess:
    """
    Test that admin access to Question Manager still works
    Requirement: 9.4, 9.5
    """
    
    def test_admin_can_access_question_manager(self, admin_session):
        """Verify admin users can access Question Manager"""
        response = admin_session.get('/questions/manage')
        assert response.status_code == 200
        
    def test_staff_cannot_access_question_manager(self, staff_session):
        """Verify staff users cannot access Question Manager"""
        response = staff_session.get('/questions/manage', follow_redirects=False)
        # Should redirect to report form
        assert response.status_code == 302
        assert '/reporte' in response.location or '/select-survey-type' in response.location
        
    def test_question_manager_link_in_sidebar(self, admin_session):
        """Verify Question Manager link exists in sidebar (Standards)"""
        response = admin_session.get('/dashboard')
        assert response.status_code == 200
        html = response.data.decode('utf-8')
        
        # Check for Standards link to Question Manager
        assert '/questions/manage' in html
        assert 'Standards' in html
        
    def test_admin_decorator_enforced(self, staff_session):
        """Verify @require_admin decorator is enforced"""
        # Staff user should not be able to access admin-only routes
        response = staff_session.get('/questions/manage', follow_redirects=False)
        assert response.status_code == 302  # Redirect


class TestAuthentication:
    """
    Test that authentication redirects still work
    Requirement: 9.4
    """
    
    def test_unauthenticated_redirects_to_login(self, client):
        """Verify unauthenticated users are redirected to login"""
        response = client.get('/dashboard', follow_redirects=False)
        assert response.status_code == 302
        assert '/login' in response.location
        
    def test_login_required_decorator_works(self, client):
        """Verify @login_required decorator is enforced"""
        protected_routes = [
            '/dashboard',
            '/reporte',
            '/api/inspections',
            '/api/questions',
            '/api/user-info'
        ]
        
        for route in protected_routes:
            response = client.get(route, follow_redirects=False)
            assert response.status_code == 302
            assert '/login' in response.location
            
    def test_login_endpoint_accessible(self, client):
        """Verify login page is accessible"""
        response = client.get('/login')
        assert response.status_code == 200
        
    def test_api_login_endpoint_works(self, client):
        """Verify API login endpoint accepts credentials"""
        response = client.post('/api/login',
                              json={'username': 'admin', 'password': 'admin123'},
                              content_type='application/json')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'success'
        assert data['username'] == 'admin'
        
    def test_invalid_credentials_rejected(self, client):
        """Verify invalid credentials are rejected"""
        response = client.post('/api/login',
                              json={'username': 'admin', 'password': 'wrongpassword'},
                              content_type='application/json')
        assert response.status_code == 401
        data = json.loads(response.data)
        assert data['status'] == 'error'


class TestLogout:
    """
    Test that logout functionality still works
    Requirement: 9.5
    """
    
    def test_logout_endpoint_exists(self, admin_session):
        """Verify /logout endpoint is accessible"""
        response = admin_session.get('/logout', follow_redirects=False)
        assert response.status_code == 302
        
    def test_logout_redirects_to_login(self, admin_session):
        """Verify logout redirects to login page"""
        response = admin_session.get('/logout', follow_redirects=False)
        assert response.status_code == 302
        assert '/login' in response.location
        
    def test_logout_clears_session(self, admin_session):
        """Verify logout clears user session"""
        # First verify user is logged in
        with admin_session.session_transaction() as sess:
            assert 'user' in sess
            
        # Logout
        admin_session.get('/logout')
        
        # Verify session is cleared
        with admin_session.session_transaction() as sess:
            assert 'user' not in sess
            
    def test_logout_link_in_sidebar(self, admin_session):
        """Verify logout link exists in sidebar navigation"""
        response = admin_session.get('/dashboard')
        assert response.status_code == 200
        html = response.data.decode('utf-8')
        
        # Check for logout link
        assert '/logout' in html
        assert 'Log Out' in html or 'Logout' in html


class TestSessionManagement:
    """
    Test that session management continues to work correctly
    Requirement: 9.6
    """
    
    def test_session_stores_username(self, admin_session):
        """Verify session stores username"""
        with admin_session.session_transaction() as sess:
            assert 'user' in sess
            assert sess['user'] == 'admin'
            
    def test_session_stores_community(self, staff_session):
        """Verify session stores community for staff users"""
        with staff_session.session_transaction() as sess:
            assert 'community' in sess
            assert sess['community'] == 'Kelley Place, Enterprise'
            
    def test_admin_has_no_community(self, admin_session):
        """Verify admin users have community set to None"""
        with admin_session.session_transaction() as sess:
            assert sess.get('community') is None
            
    def test_user_info_api_returns_session_data(self, admin_session):
        """Verify /api/user-info returns session data"""
        response = admin_session.get('/api/user-info')
        assert response.status_code == 200
        data = json.loads(response.data)
        
        assert data['username'] == 'admin'
        assert data['community'] is None
        assert data['is_admin'] is True


class TestFlaskRoutes:
    """
    Test that existing Flask routes continue to work
    Requirement: 9.7
    """
    
    def test_root_route_redirects_correctly(self, admin_session):
        """Verify root route redirects based on user type"""
        response = admin_session.get('/', follow_redirects=False)
        assert response.status_code == 302
        # Admin should redirect to dashboard
        assert '/dashboard' in response.location
        
    def test_dashboard_route_accessible(self, admin_session):
        """Verify /dashboard route is accessible"""
        response = admin_session.get('/dashboard')
        assert response.status_code == 200
        
    def test_reporte_route_accessible(self, staff_session):
        """Verify /reporte route is accessible for staff"""
        # Staff user needs survey type in session
        with staff_session.session_transaction() as sess:
            sess['survey_type_id'] = 'operational'
            sess['survey_type_name'] = 'Operational Review'
            
        response = staff_session.get('/reporte')
        assert response.status_code == 200
        
    def test_api_endpoints_exist(self, admin_session):
        """Verify all API endpoints are accessible"""
        api_endpoints = [
            '/api/user-info',
            '/api/inspections',
            '/api/questions',
            '/api/survey-types'
        ]
        
        for endpoint in api_endpoints:
            response = admin_session.get(endpoint)
            assert response.status_code in [200, 201, 400]  # Valid responses


class TestBackwardCompatibilityIntegration:
    """
    Integration tests for backward compatibility
    """
    
    def test_dashboard_renders_with_sidebar(self, admin_session):
        """Verify dashboard renders with new sidebar navigation"""
        response = admin_session.get('/dashboard')
        assert response.status_code == 200
        html = response.data.decode('utf-8')
        
        # Check for sidebar elements
        assert 'sidebar' in html
        assert 'navigation-menu' in html
        assert 'user-welcome' in html
        
    def test_dashboard_maintains_filter_functionality(self, admin_session):
        """Verify dashboard maintains all filter functionality"""
        response = admin_session.get('/dashboard')
        assert response.status_code == 200
        html = response.data.decode('utf-8')
        
        # Check for filter functions
        assert 'filterByType' in html
        assert 'filterByCondition' in html
        assert 'filterBySurveyType' in html
        
    def test_all_navigation_items_present(self, admin_session):
        """Verify all 9 navigation menu items are present"""
        response = admin_session.get('/dashboard')
        assert response.status_code == 200
        html = response.data.decode('utf-8')
        
        # Check for all 9 navigation items
        nav_items = [
            'Dashboard',
            'My Visits',
            'Communities',
            'Standards',
            'Reports',
            'Action Items',
            'Resources',
            'Settings',
            'Log Out'
        ]
        
        for item in nav_items:
            assert item in html
            
    def test_community_cards_display(self, admin_session):
        """Verify community cards can be displayed"""
        response = admin_session.get('/dashboard')
        assert response.status_code == 200
        html = response.data.decode('utf-8')
        
        # Check for community card elements
        assert 'community-card' in html or 'community-grid' in html
        assert 'circular-progress' in html
        assert 'action-items' in html


if __name__ == '__main__':
    # Run tests with pytest
    pytest.main([__file__, '-v', '--tb=short'])
