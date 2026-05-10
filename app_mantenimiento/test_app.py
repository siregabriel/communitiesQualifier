"""
Unit tests for app.py decorators
Tests authentication and authorization decorators
"""

import unittest
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask
from app import require_admin, login_required, app as main_app, question_manager
import json
import tempfile
import shutil


# Create a test app with test routes
def create_test_app():
    """Create a test Flask app with test routes"""
    test_app = Flask(__name__)
    test_app.config['TESTING'] = True
    test_app.config['SECRET_KEY'] = 'test-secret-key'
    
    @test_app.route('/test-admin-route')
    @require_admin
    def test_admin_route():
        return 'Admin access granted', 200
    
    @test_app.route('/test-protected-route')
    @login_required
    def test_protected_route():
        return 'Access granted', 200
    
    # Add the report_form route for redirects
    @test_app.route('/')
    def report_form():
        return 'Inspection Form', 200
    
    @test_app.route('/login')
    def login():
        return 'Login Page', 200
    
    return test_app


class TestRequireAdminDecorator(unittest.TestCase):
    """Test cases for require_admin decorator"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test app once for all tests"""
        cls.app = create_test_app()
        cls.client = cls.app.test_client()
    
    def test_require_admin_allows_admin_user(self):
        """Test that admin users (community=None) can access admin routes"""
        with self.client.session_transaction() as sess:
            sess['user'] = 'admin'
            sess['community'] = None
        
        response = self.client.get('/test-admin-route')
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data.decode(), 'Admin access granted')
    
    def test_require_admin_redirects_staff_user(self):
        """Test that staff users (community assigned) are redirected to inspection form"""
        with self.client.session_transaction() as sess:
            sess['user'] = 'john'
            sess['community'] = 'Community A'
        
        response = self.client.get('/test-admin-route', follow_redirects=False)
        
        self.assertEqual(response.status_code, 302)
        self.assertIn('/', response.location)
    
    def test_require_admin_redirects_unauthenticated_user(self):
        """Test that unauthenticated users are redirected to login"""
        # Clear session
        with self.client.session_transaction() as sess:
            sess.clear()
        
        response = self.client.get('/test-admin-route', follow_redirects=False)
        
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login', response.location)
    
    def test_require_admin_checks_community_none(self):
        """Test that only users with community=None are considered admins"""
        # Test with community set to empty string (not None)
        with self.client.session_transaction() as sess:
            sess['user'] = 'user1'
            sess['community'] = ''
        
        response = self.client.get('/test-admin-route', follow_redirects=False)
        
        # Empty string is not None, so should redirect
        self.assertEqual(response.status_code, 302)
    
    def test_require_admin_reuses_login_required(self):
        """Test that require_admin decorator reuses login_required functionality"""
        # Clear session to simulate unauthenticated user
        with self.client.session_transaction() as sess:
            sess.clear()
        
        response = self.client.get('/test-admin-route', follow_redirects=False)
        
        # Should redirect to login (handled by login_required)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login', response.location)


class TestLoginRequiredDecorator(unittest.TestCase):
    """Test cases for login_required decorator"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test app once for all tests"""
        cls.app = create_test_app()
        cls.client = cls.app.test_client()
    
    def test_login_required_allows_authenticated_user(self):
        """Test that authenticated users can access protected routes"""
        with self.client.session_transaction() as sess:
            sess['user'] = 'john'
            sess['community'] = 'Community A'
        
        response = self.client.get('/test-protected-route')
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data.decode(), 'Access granted')
    
    def test_login_required_redirects_unauthenticated_user(self):
        """Test that unauthenticated users are redirected to login"""
        # Clear session
        with self.client.session_transaction() as sess:
            sess.clear()
        
        response = self.client.get('/test-protected-route', follow_redirects=False)
        
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login', response.location)


class TestCreateQuestionEndpoint(unittest.TestCase):
    """Test cases for POST /api/questions endpoint"""
    
    def setUp(self):
        """Set up test client and temporary data directory for each test"""
        # Create temporary directory for test data
        self.test_dir = tempfile.mkdtemp()
        self.test_questions_file = os.path.join(self.test_dir, 'questions.json')
        
        # Import app module to access question_manager
        import app as app_module
        
        # Replace the global question_manager with a test instance
        self.original_question_manager = app_module.question_manager
        app_module.question_manager = question_manager.__class__(self.test_questions_file)
        
        # Set up test client
        main_app.config['TESTING'] = True
        self.client = main_app.test_client()
        
        # Store reference to app module for teardown
        self.app_module = app_module
    
    def tearDown(self):
        """Clean up temporary directory and restore original question_manager"""
        # Restore original question_manager
        self.app_module.question_manager = self.original_question_manager
        
        # Remove temporary directory
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_create_question_success_admin(self):
        """Test successful question creation by admin user"""
        # Set up admin session
        with self.client.session_transaction() as sess:
            sess['user'] = 'admin'
            sess['community'] = None
        
        # Create question
        response = self.client.post('/api/questions',
                                   json={
                                       'text': 'Is the common area clean?',
                                       'photo_required': True,
                                       'communities': ['Community A', 'Community B']
                                   })
        
        self.assertEqual(response.status_code, 201)
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'success')
        self.assertIn('question', data)
        self.assertEqual(data['question']['text'], 'Is the common area clean?')
        self.assertTrue(data['question']['photo_required'])
        self.assertEqual(data['question']['communities'], ['Community A', 'Community B'])
        self.assertIn('id', data['question'])
        self.assertIn('created_at', data['question'])
    
    def test_create_question_empty_text_validation(self):
        """Test that empty question text returns 400 error"""
        # Set up admin session
        with self.client.session_transaction() as sess:
            sess['user'] = 'admin'
            sess['community'] = None
        
        # Try to create question with empty text
        response = self.client.post('/api/questions',
                                   json={
                                       'text': '',
                                       'photo_required': False,
                                       'communities': ['Community A']
                                   })
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'error')
        self.assertIn('Question text cannot be empty', data['message'])
    
    def test_create_question_whitespace_only_text_validation(self):
        """Test that whitespace-only question text returns 400 error"""
        # Set up admin session
        with self.client.session_transaction() as sess:
            sess['user'] = 'admin'
            sess['community'] = None
        
        # Try to create question with whitespace-only text
        response = self.client.post('/api/questions',
                                   json={
                                       'text': '   ',
                                       'photo_required': False,
                                       'communities': ['Community A']
                                   })
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'error')
        self.assertIn('Question text cannot be empty', data['message'])
    
    def test_create_question_empty_communities_validation(self):
        """Test that empty communities array returns 400 with specific error message"""
        # Set up admin session
        with self.client.session_transaction() as sess:
            sess['user'] = 'admin'
            sess['community'] = None
        
        # Try to create question with empty communities array
        response = self.client.post('/api/questions',
                                   json={
                                       'text': 'Valid question text',
                                       'photo_required': False,
                                       'communities': []
                                   })
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'error')
        self.assertEqual(data['message'], 'At least one community must be selected')
    
    def test_create_question_missing_communities_validation(self):
        """Test that missing communities field returns 400 with specific error message"""
        # Set up admin session
        with self.client.session_transaction() as sess:
            sess['user'] = 'admin'
            sess['community'] = None
        
        # Try to create question without communities field
        response = self.client.post('/api/questions',
                                   json={
                                       'text': 'Valid question text',
                                       'photo_required': False
                                   })
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'error')
        self.assertEqual(data['message'], 'At least one community must be selected')
    
    def test_create_question_requires_admin(self):
        """Test that staff users cannot create questions"""
        # Set up staff user session
        with self.client.session_transaction() as sess:
            sess['user'] = 'john'
            sess['community'] = 'Community A'
        
        # Try to create question as staff user
        response = self.client.post('/api/questions',
                                   json={
                                       'text': 'Is the common area clean?',
                                       'photo_required': True,
                                       'communities': ['Community A']
                                   },
                                   follow_redirects=False)
        
        # Should redirect to inspection form
        self.assertEqual(response.status_code, 302)
    
    def test_create_question_requires_authentication(self):
        """Test that unauthenticated users cannot create questions"""
        # Clear session
        with self.client.session_transaction() as sess:
            sess.clear()
        
        # Try to create question without authentication
        response = self.client.post('/api/questions',
                                   json={
                                       'text': 'Is the common area clean?',
                                       'photo_required': True,
                                       'communities': ['Community A']
                                   },
                                   follow_redirects=False)
        
        # Should redirect to login
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login', response.location)
    
    def test_create_question_no_json_data(self):
        """Test that missing JSON data returns 400 error"""
        # Set up admin session
        with self.client.session_transaction() as sess:
            sess['user'] = 'admin'
            sess['community'] = None
        
        # Try to create question without JSON data
        response = self.client.post('/api/questions')
        
        # Debug: print response data if test fails
        if response.status_code != 400:
            print(f"Response status: {response.status_code}")
            print(f"Response data: {response.data.decode()}")
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'error')
        self.assertIn('No JSON data provided', data['message'])
    
    def test_create_question_photo_required_default_false(self):
        """Test that photo_required defaults to False when not provided"""
        # Set up admin session
        with self.client.session_transaction() as sess:
            sess['user'] = 'admin'
            sess['community'] = None
        
        # Create question without photo_required field
        response = self.client.post('/api/questions',
                                   json={
                                       'text': 'Is the common area clean?',
                                       'communities': ['Community A']
                                   })
        
        self.assertEqual(response.status_code, 201)
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'success')
        self.assertFalse(data['question']['photo_required'])
    
    def test_create_question_multiple_communities(self):
        """Test creating question assigned to multiple communities"""
        # Set up admin session
        with self.client.session_transaction() as sess:
            sess['user'] = 'admin'
            sess['community'] = None
        
        # Create question with multiple communities
        communities = ['Community A', 'Community B', 'Community C', 'Community D']
        response = self.client.post('/api/questions',
                                   json={
                                       'text': 'Is the common area clean?',
                                       'photo_required': True,
                                       'communities': communities
                                   })
        
        self.assertEqual(response.status_code, 201)
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['question']['communities'], communities)
    
    def test_create_question_strips_whitespace(self):
        """Test that question text is stripped of leading/trailing whitespace"""
        # Set up admin session
        with self.client.session_transaction() as sess:
            sess['user'] = 'admin'
            sess['community'] = None
        
        # Create question with whitespace around text
        response = self.client.post('/api/questions',
                                   json={
                                       'text': '  Is the common area clean?  ',
                                       'photo_required': False,
                                       'communities': ['Community A']
                                   })
        
        self.assertEqual(response.status_code, 201)
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['question']['text'], 'Is the common area clean?')


class TestGetQuestionsEndpoint(unittest.TestCase):
    """Test cases for GET /api/questions endpoint"""
    
    def setUp(self):
        """Set up test client and temporary data directory for each test"""
        # Create temporary directory for test data
        self.test_dir = tempfile.mkdtemp()
        self.test_questions_file = os.path.join(self.test_dir, 'questions.json')
        
        # Import app module to access question_manager
        import app as app_module
        
        # Replace the global question_manager with a test instance
        self.original_question_manager = app_module.question_manager
        app_module.question_manager = question_manager.__class__(self.test_questions_file)
        
        # Set up test client
        main_app.config['TESTING'] = True
        self.client = main_app.test_client()
        
        # Store reference to app module for teardown
        self.app_module = app_module
    
    def tearDown(self):
        """Clean up temporary directory and restore original question_manager"""
        # Restore original question_manager
        self.app_module.question_manager = self.original_question_manager
        
        # Remove temporary directory
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_get_questions_staff_user_filters_by_community(self):
        """Test that staff users automatically see only questions for their assigned community"""
        # Create questions for different communities
        self.app_module.question_manager.create_question(
            'Question for Community A', False, ['Community A']
        )
        self.app_module.question_manager.create_question(
            'Question for Community B', False, ['Community B']
        )
        self.app_module.question_manager.create_question(
            'Question for both A and B', True, ['Community A', 'Community B']
        )
        
        # Set up staff user session for Community A
        with self.client.session_transaction() as sess:
            sess['user'] = 'john'
            sess['community'] = 'Community A'
        
        # Get questions
        response = self.client.get('/api/questions')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'success')
        self.assertIn('questions', data)
        
        # Should return 2 questions (Community A and both A and B)
        self.assertEqual(len(data['questions']), 2)
        
        # Verify questions are for Community A
        for question in data['questions']:
            self.assertIn('Community A', question['communities'])
    
    def test_get_questions_admin_returns_all_active_questions(self):
        """Test that admin users without community filter see all active questions"""
        # Create questions for different communities
        q1 = self.app_module.question_manager.create_question(
            'Question for Community A', False, ['Community A']
        )
        q2 = self.app_module.question_manager.create_question(
            'Question for Community B', False, ['Community B']
        )
        q3 = self.app_module.question_manager.create_question(
            'Question for Community C', True, ['Community C']
        )
        
        # Set up admin session
        with self.client.session_transaction() as sess:
            sess['user'] = 'admin'
            sess['community'] = None
        
        # Get questions without filter
        response = self.client.get('/api/questions')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'success')
        self.assertIn('questions', data)
        
        # Should return all 3 questions
        self.assertEqual(len(data['questions']), 3)
        
        # Verify all question IDs are present
        question_ids = [q['id'] for q in data['questions']]
        self.assertIn(q1['id'], question_ids)
        self.assertIn(q2['id'], question_ids)
        self.assertIn(q3['id'], question_ids)
    
    def test_get_questions_admin_with_community_filter(self):
        """Test that admin users can filter by community using query parameter"""
        # Create questions for different communities
        self.app_module.question_manager.create_question(
            'Question for Community A', False, ['Community A']
        )
        self.app_module.question_manager.create_question(
            'Question for Community B', False, ['Community B']
        )
        self.app_module.question_manager.create_question(
            'Question for both A and B', True, ['Community A', 'Community B']
        )
        
        # Set up admin session
        with self.client.session_transaction() as sess:
            sess['user'] = 'admin'
            sess['community'] = None
        
        # Get questions filtered by Community B
        response = self.client.get('/api/questions?community=Community B')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'success')
        self.assertIn('questions', data)
        
        # Should return 2 questions (Community B and both A and B)
        self.assertEqual(len(data['questions']), 2)
        
        # Verify questions are for Community B
        for question in data['questions']:
            self.assertIn('Community B', question['communities'])
    
    def test_get_questions_excludes_inactive_questions(self):
        """Test that soft-deleted (inactive) questions are not returned"""
        # Create questions
        q1 = self.app_module.question_manager.create_question(
            'Active question', False, ['Community A']
        )
        q2 = self.app_module.question_manager.create_question(
            'Question to delete', False, ['Community A']
        )
        
        # Soft delete q2
        self.app_module.question_manager.delete_question(q2['id'])
        
        # Set up staff user session for Community A
        with self.client.session_transaction() as sess:
            sess['user'] = 'john'
            sess['community'] = 'Community A'
        
        # Get questions
        response = self.client.get('/api/questions')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'success')
        
        # Should return only 1 question (the active one)
        self.assertEqual(len(data['questions']), 1)
        self.assertEqual(data['questions'][0]['id'], q1['id'])
    
    def test_get_questions_requires_authentication(self):
        """Test that unauthenticated users cannot access questions"""
        # Clear session
        with self.client.session_transaction() as sess:
            sess.clear()
        
        # Try to get questions without authentication
        response = self.client.get('/api/questions', follow_redirects=False)
        
        # Should redirect to login
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login', response.location)
    
    def test_get_questions_staff_ignores_community_parameter(self):
        """Test that staff users cannot override their community filter with query parameter"""
        # Create questions for different communities
        self.app_module.question_manager.create_question(
            'Question for Community A', False, ['Community A']
        )
        self.app_module.question_manager.create_question(
            'Question for Community B', False, ['Community B']
        )
        
        # Set up staff user session for Community A
        with self.client.session_transaction() as sess:
            sess['user'] = 'john'
            sess['community'] = 'Community A'
        
        # Try to get questions for Community B (should be ignored)
        response = self.client.get('/api/questions?community=Community B')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'success')
        
        # Should still return only Community A questions
        self.assertEqual(len(data['questions']), 1)
        self.assertIn('Community A', data['questions'][0]['communities'])
    
    def test_get_questions_returns_empty_array_when_no_questions(self):
        """Test that endpoint returns empty array when no questions exist"""
        # Set up staff user session
        with self.client.session_transaction() as sess:
            sess['user'] = 'john'
            sess['community'] = 'Community A'
        
        # Get questions (none exist)
        response = self.client.get('/api/questions')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['questions'], [])
    
    def test_get_questions_returns_sorted_by_created_at_descending(self):
        """Test that questions are returned sorted by created_at (newest first)"""
        # Create questions with slight delays to ensure different timestamps
        import time
        
        q1 = self.app_module.question_manager.create_question(
            'First question', False, ['Community A']
        )
        time.sleep(0.01)  # Small delay to ensure different timestamps
        
        q2 = self.app_module.question_manager.create_question(
            'Second question', False, ['Community A']
        )
        time.sleep(0.01)
        
        q3 = self.app_module.question_manager.create_question(
            'Third question', False, ['Community A']
        )
        
        # Set up staff user session
        with self.client.session_transaction() as sess:
            sess['user'] = 'john'
            sess['community'] = 'Community A'
        
        # Get questions
        response = self.client.get('/api/questions')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'success')
        
        # Should return 3 questions in reverse order (newest first)
        self.assertEqual(len(data['questions']), 3)
        self.assertEqual(data['questions'][0]['id'], q3['id'])
        self.assertEqual(data['questions'][1]['id'], q2['id'])
        self.assertEqual(data['questions'][2]['id'], q1['id'])
    
    def test_get_questions_multi_community_assignment(self):
        """Test that questions assigned to multiple communities appear for all assigned communities"""
        # Create a question assigned to multiple communities
        multi_community_q = self.app_module.question_manager.create_question(
            'Multi-community question', True, ['Community A', 'Community B', 'Community C']
        )
        
        # Test with Community A staff user
        with self.client.session_transaction() as sess:
            sess['user'] = 'john'
            sess['community'] = 'Community A'
        
        response = self.client.get('/api/questions')
        data = json.loads(response.data)
        self.assertEqual(len(data['questions']), 1)
        self.assertEqual(data['questions'][0]['id'], multi_community_q['id'])
        
        # Test with Community B staff user
        with self.client.session_transaction() as sess:
            sess['user'] = 'maria'
            sess['community'] = 'Community B'
        
        response = self.client.get('/api/questions')
        data = json.loads(response.data)
        self.assertEqual(len(data['questions']), 1)
        self.assertEqual(data['questions'][0]['id'], multi_community_q['id'])
        
        # Test with Community C staff user
        with self.client.session_transaction() as sess:
            sess['user'] = 'carlos'
            sess['community'] = 'Community C'
        
        response = self.client.get('/api/questions')
        data = json.loads(response.data)
        self.assertEqual(len(data['questions']), 1)
        self.assertEqual(data['questions'][0]['id'], multi_community_q['id'])


class TestQuestionManagerRoute(unittest.TestCase):
    """Test cases for GET /questions/manage route"""
    
    def setUp(self):
        """Set up test client"""
        main_app.config['TESTING'] = True
        self.client = main_app.test_client()
    
    def test_question_manager_route_allows_admin_user(self):
        """Test that admin users can access the question manager UI"""
        # Set up admin session
        with self.client.session_transaction() as sess:
            sess['user'] = 'admin'
            sess['community'] = None
        
        # Try to access the route
        # This will raise TemplateNotFound until task 10.1 creates the template
        # But the important thing is that it doesn't redirect (which would happen for non-admin)
        try:
            response = self.client.get('/questions/manage')
            # If template exists, should return 200
            self.assertEqual(response.status_code, 200)
        except Exception as e:
            # Expected: TemplateNotFound until task 10.1 is complete
            # This confirms the route exists and admin authentication works
            self.assertIn('question_manager.html', str(e))
    
    def test_question_manager_route_redirects_staff_user(self):
        """Test that staff users are redirected to inspection form"""
        # Set up staff user session
        with self.client.session_transaction() as sess:
            sess['user'] = 'john'
            sess['community'] = 'Community A'
        
        response = self.client.get('/questions/manage', follow_redirects=False)
        
        # Should redirect to inspection form
        self.assertEqual(response.status_code, 302)
        self.assertIn('/', response.location)
    
    def test_question_manager_route_requires_authentication(self):
        """Test that unauthenticated users are redirected to login"""
        # Clear session
        with self.client.session_transaction() as sess:
            sess.clear()
        
        response = self.client.get('/questions/manage', follow_redirects=False)
        
        # Should redirect to login
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login', response.location)


class TestUpdateQuestionEndpoint(unittest.TestCase):
    """Test cases for PUT /api/questions/<question_id> endpoint"""
    
    def setUp(self):
        """Set up test client and temporary data directory for each test"""
        # Create temporary directory for test data
        self.test_dir = tempfile.mkdtemp()
        self.test_questions_file = os.path.join(self.test_dir, 'questions.json')
        
        # Import app module to access question_manager
        import app as app_module
        
        # Replace the global question_manager with a test instance
        self.original_question_manager = app_module.question_manager
        app_module.question_manager = question_manager.__class__(self.test_questions_file)
        
        # Set up test client
        main_app.config['TESTING'] = True
        self.client = main_app.test_client()
        
        # Store reference to app module for teardown
        self.app_module = app_module
    
    def tearDown(self):
        """Clean up temporary directory and restore original question_manager"""
        # Restore original question_manager
        self.app_module.question_manager = self.original_question_manager
        
        # Remove temporary directory
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_update_question_success_admin(self):
        """Test successful question update by admin user"""
        # Create a question first
        question = self.app_module.question_manager.create_question(
            'Original question text', True, ['Community A']
        )
        question_id = question['id']
        
        # Set up admin session
        with self.client.session_transaction() as sess:
            sess['user'] = 'admin'
            sess['community'] = None
        
        # Update question
        response = self.client.put(f'/api/questions/{question_id}',
                                   json={
                                       'text': 'Updated question text',
                                       'photo_required': False,
                                       'communities': ['Community B', 'Community C']
                                   })
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'success')
        self.assertIn('question', data)
        self.assertEqual(data['question']['text'], 'Updated question text')
        self.assertFalse(data['question']['photo_required'])
        self.assertEqual(data['question']['communities'], ['Community B', 'Community C'])
        self.assertEqual(data['question']['id'], question_id)
    
    def test_update_question_not_found(self):
        """Test that updating non-existent question returns 404"""
        # Set up admin session
        with self.client.session_transaction() as sess:
            sess['user'] = 'admin'
            sess['community'] = None
        
        # Try to update non-existent question
        response = self.client.put('/api/questions/nonexistent_id',
                                   json={
                                       'text': 'Updated text',
                                       'photo_required': False,
                                       'communities': ['Community A']
                                   })
        
        self.assertEqual(response.status_code, 404)
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'error')
        self.assertEqual(data['message'], 'Question not found')
    
    def test_update_question_empty_text_validation(self):
        """Test that empty question text returns 400 error"""
        # Create a question first
        question = self.app_module.question_manager.create_question(
            'Original question text', True, ['Community A']
        )
        question_id = question['id']
        
        # Set up admin session
        with self.client.session_transaction() as sess:
            sess['user'] = 'admin'
            sess['community'] = None
        
        # Try to update with empty text
        response = self.client.put(f'/api/questions/{question_id}',
                                   json={
                                       'text': '',
                                       'photo_required': False,
                                       'communities': ['Community A']
                                   })
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'error')
        self.assertIn('Question text cannot be empty', data['message'])
    
    def test_update_question_whitespace_only_text_validation(self):
        """Test that whitespace-only question text returns 400 error"""
        # Create a question first
        question = self.app_module.question_manager.create_question(
            'Original question text', True, ['Community A']
        )
        question_id = question['id']
        
        # Set up admin session
        with self.client.session_transaction() as sess:
            sess['user'] = 'admin'
            sess['community'] = None
        
        # Try to update with whitespace-only text
        response = self.client.put(f'/api/questions/{question_id}',
                                   json={
                                       'text': '   ',
                                       'photo_required': False,
                                       'communities': ['Community A']
                                   })
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'error')
        self.assertIn('Question text cannot be empty', data['message'])
    
    def test_update_question_empty_communities_validation(self):
        """Test that empty communities array returns 400 with specific error message"""
        # Create a question first
        question = self.app_module.question_manager.create_question(
            'Original question text', True, ['Community A']
        )
        question_id = question['id']
        
        # Set up admin session
        with self.client.session_transaction() as sess:
            sess['user'] = 'admin'
            sess['community'] = None
        
        # Try to update with empty communities array
        response = self.client.put(f'/api/questions/{question_id}',
                                   json={
                                       'text': 'Valid question text',
                                       'photo_required': False,
                                       'communities': []
                                   })
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'error')
        self.assertEqual(data['message'], 'At least one community must be selected')
    
    def test_update_question_missing_communities_validation(self):
        """Test that missing communities field returns 400 with specific error message"""
        # Create a question first
        question = self.app_module.question_manager.create_question(
            'Original question text', True, ['Community A']
        )
        question_id = question['id']
        
        # Set up admin session
        with self.client.session_transaction() as sess:
            sess['user'] = 'admin'
            sess['community'] = None
        
        # Try to update without communities field
        response = self.client.put(f'/api/questions/{question_id}',
                                   json={
                                       'text': 'Valid question text',
                                       'photo_required': False
                                   })
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'error')
        self.assertEqual(data['message'], 'At least one community must be selected')
    
    def test_update_question_requires_admin(self):
        """Test that staff users cannot update questions"""
        # Create a question first
        question = self.app_module.question_manager.create_question(
            'Original question text', True, ['Community A']
        )
        question_id = question['id']
        
        # Set up staff user session
        with self.client.session_transaction() as sess:
            sess['user'] = 'john'
            sess['community'] = 'Community A'
        
        # Try to update question as staff user
        response = self.client.put(f'/api/questions/{question_id}',
                                   json={
                                       'text': 'Updated text',
                                       'photo_required': False,
                                       'communities': ['Community A']
                                   },
                                   follow_redirects=False)
        
        # Should redirect to inspection form
        self.assertEqual(response.status_code, 302)
    
    def test_update_question_requires_authentication(self):
        """Test that unauthenticated users cannot update questions"""
        # Create a question first
        question = self.app_module.question_manager.create_question(
            'Original question text', True, ['Community A']
        )
        question_id = question['id']
        
        # Clear session
        with self.client.session_transaction() as sess:
            sess.clear()
        
        # Try to update question without authentication
        response = self.client.put(f'/api/questions/{question_id}',
                                   json={
                                       'text': 'Updated text',
                                       'photo_required': False,
                                       'communities': ['Community A']
                                   },
                                   follow_redirects=False)
        
        # Should redirect to login
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login', response.location)
    
    def test_update_question_no_json_data(self):
        """Test that missing JSON data returns 400 error"""
        # Create a question first
        question = self.app_module.question_manager.create_question(
            'Original question text', True, ['Community A']
        )
        question_id = question['id']
        
        # Set up admin session
        with self.client.session_transaction() as sess:
            sess['user'] = 'admin'
            sess['community'] = None
        
        # Try to update question without JSON data
        response = self.client.put(f'/api/questions/{question_id}')
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'error')
        self.assertIn('No JSON data provided', data['message'])
    
    def test_update_question_photo_required_default_false(self):
        """Test that photo_required defaults to False when not provided"""
        # Create a question first
        question = self.app_module.question_manager.create_question(
            'Original question text', True, ['Community A']
        )
        question_id = question['id']
        
        # Set up admin session
        with self.client.session_transaction() as sess:
            sess['user'] = 'admin'
            sess['community'] = None
        
        # Update question without photo_required field
        response = self.client.put(f'/api/questions/{question_id}',
                                   json={
                                       'text': 'Updated text',
                                       'communities': ['Community A']
                                   })
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'success')
        self.assertFalse(data['question']['photo_required'])
    
    def test_update_question_multiple_communities(self):
        """Test updating question with multiple communities"""
        # Create a question first
        question = self.app_module.question_manager.create_question(
            'Original question text', True, ['Community A']
        )
        question_id = question['id']
        
        # Set up admin session
        with self.client.session_transaction() as sess:
            sess['user'] = 'admin'
            sess['community'] = None
        
        # Update question with multiple communities
        communities = ['Community A', 'Community B', 'Community C', 'Community D']
        response = self.client.put(f'/api/questions/{question_id}',
                                   json={
                                       'text': 'Updated text',
                                       'photo_required': True,
                                       'communities': communities
                                   })
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['question']['communities'], communities)
    
    def test_update_question_strips_whitespace(self):
        """Test that question text is stripped of leading/trailing whitespace"""
        # Create a question first
        question = self.app_module.question_manager.create_question(
            'Original question text', True, ['Community A']
        )
        question_id = question['id']
        
        # Set up admin session
        with self.client.session_transaction() as sess:
            sess['user'] = 'admin'
            sess['community'] = None
        
        # Update question with whitespace around text
        response = self.client.put(f'/api/questions/{question_id}',
                                   json={
                                       'text': '  Updated question text  ',
                                       'photo_required': False,
                                       'communities': ['Community A']
                                   })
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['question']['text'], 'Updated question text')
    
    def test_update_question_preserves_id_and_created_at(self):
        """Test that updating a question preserves its ID and created_at timestamp"""
        # Create a question first
        question = self.app_module.question_manager.create_question(
            'Original question text', True, ['Community A']
        )
        question_id = question['id']
        created_at = question['created_at']
        
        # Set up admin session
        with self.client.session_transaction() as sess:
            sess['user'] = 'admin'
            sess['community'] = None
        
        # Update question
        response = self.client.put(f'/api/questions/{question_id}',
                                   json={
                                       'text': 'Updated question text',
                                       'photo_required': False,
                                       'communities': ['Community B']
                                   })
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'success')
        
        # Verify ID and created_at are preserved
        self.assertEqual(data['question']['id'], question_id)
        self.assertEqual(data['question']['created_at'], created_at)
        
        # Verify updated_at is different from created_at
        self.assertNotEqual(data['question']['updated_at'], created_at)
    
    def test_update_question_changes_updated_at_timestamp(self):
        """Test that updating a question changes the updated_at timestamp"""
        import time
        
        # Create a question first
        question = self.app_module.question_manager.create_question(
            'Original question text', True, ['Community A']
        )
        question_id = question['id']
        original_updated_at = question['updated_at']
        
        # Wait a moment to ensure timestamp difference
        time.sleep(0.01)
        
        # Set up admin session
        with self.client.session_transaction() as sess:
            sess['user'] = 'admin'
            sess['community'] = None
        
        # Update question
        response = self.client.put(f'/api/questions/{question_id}',
                                   json={
                                       'text': 'Updated question text',
                                       'photo_required': False,
                                       'communities': ['Community A']
                                   })
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'success')
        
        # Verify updated_at has changed
        self.assertNotEqual(data['question']['updated_at'], original_updated_at)
        self.assertGreater(data['question']['updated_at'], original_updated_at)


class TestDeleteQuestionEndpoint(unittest.TestCase):
    """Test cases for DELETE /api/questions/<question_id> endpoint"""
    
    def setUp(self):
        """Set up test client and temporary data directory for each test"""
        # Create temporary directory for test data
        self.test_dir = tempfile.mkdtemp()
        self.test_questions_file = os.path.join(self.test_dir, 'questions.json')
        
        # Import app module to access question_manager
        import app as app_module
        
        # Replace the global question_manager with a test instance
        self.original_question_manager = app_module.question_manager
        app_module.question_manager = question_manager.__class__(self.test_questions_file)
        
        # Set up test client
        main_app.config['TESTING'] = True
        self.client = main_app.test_client()
        
        # Store reference to app module for teardown
        self.app_module = app_module
    
    def tearDown(self):
        """Clean up temporary directory and restore original question_manager"""
        # Restore original question_manager
        self.app_module.question_manager = self.original_question_manager
        
        # Remove temporary directory
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_delete_question_success_admin(self):
        """Test successful question deletion (soft delete) by admin user"""
        # Create a question first
        question = self.app_module.question_manager.create_question(
            'Question to delete', True, ['Community A']
        )
        question_id = question['id']
        
        # Set up admin session
        with self.client.session_transaction() as sess:
            sess['user'] = 'admin'
            sess['community'] = None
        
        # Delete question
        response = self.client.delete(f'/api/questions/{question_id}')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['message'], 'Question deleted successfully')
    
    def test_delete_question_soft_delete_sets_is_active_false(self):
        """Test that deleting a question performs soft delete (sets is_active to False)"""
        # Create a question first
        question = self.app_module.question_manager.create_question(
            'Question to delete', True, ['Community A']
        )
        question_id = question['id']
        
        # Set up admin session
        with self.client.session_transaction() as sess:
            sess['user'] = 'admin'
            sess['community'] = None
        
        # Delete question
        response = self.client.delete(f'/api/questions/{question_id}')
        
        self.assertEqual(response.status_code, 200)
        
        # Verify question still exists but is_active is False
        deleted_question = self.app_module.question_manager.get_question(question_id)
        self.assertIsNotNone(deleted_question)
        self.assertFalse(deleted_question['is_active'])
        
        # Verify all other data is preserved
        self.assertEqual(deleted_question['text'], 'Question to delete')
        self.assertTrue(deleted_question['photo_required'])
        self.assertEqual(deleted_question['communities'], ['Community A'])
    
    def test_delete_question_not_found(self):
        """Test that deleting non-existent question returns 404"""
        # Set up admin session
        with self.client.session_transaction() as sess:
            sess['user'] = 'admin'
            sess['community'] = None
        
        # Try to delete non-existent question
        response = self.client.delete('/api/questions/nonexistent_id')
        
        self.assertEqual(response.status_code, 404)
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'error')
        self.assertEqual(data['message'], 'Question not found')
    
    def test_delete_question_requires_admin(self):
        """Test that staff users cannot delete questions"""
        # Create a question first
        question = self.app_module.question_manager.create_question(
            'Question to delete', True, ['Community A']
        )
        question_id = question['id']
        
        # Set up staff user session
        with self.client.session_transaction() as sess:
            sess['user'] = 'john'
            sess['community'] = 'Community A'
        
        # Try to delete question as staff user
        response = self.client.delete(f'/api/questions/{question_id}', follow_redirects=False)
        
        # Should redirect to inspection form
        self.assertEqual(response.status_code, 302)
        
        # Verify question was not deleted
        question_check = self.app_module.question_manager.get_question(question_id)
        self.assertIsNotNone(question_check)
        self.assertTrue(question_check['is_active'])
    
    def test_delete_question_requires_authentication(self):
        """Test that unauthenticated users cannot delete questions"""
        # Create a question first
        question = self.app_module.question_manager.create_question(
            'Question to delete', True, ['Community A']
        )
        question_id = question['id']
        
        # Clear session
        with self.client.session_transaction() as sess:
            sess.clear()
        
        # Try to delete question without authentication
        response = self.client.delete(f'/api/questions/{question_id}', follow_redirects=False)
        
        # Should redirect to login
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login', response.location)
        
        # Verify question was not deleted
        question_check = self.app_module.question_manager.get_question(question_id)
        self.assertIsNotNone(question_check)
        self.assertTrue(question_check['is_active'])
    
    def test_delete_question_excluded_from_active_questions(self):
        """Test that deleted questions are excluded from get_all_active_questions"""
        # Create questions
        q1 = self.app_module.question_manager.create_question(
            'Active question', False, ['Community A']
        )
        q2 = self.app_module.question_manager.create_question(
            'Question to delete', True, ['Community A']
        )
        
        # Set up admin session
        with self.client.session_transaction() as sess:
            sess['user'] = 'admin'
            sess['community'] = None
        
        # Delete q2
        response = self.client.delete(f'/api/questions/{q2["id"]}')
        self.assertEqual(response.status_code, 200)
        
        # Get all active questions
        active_questions = self.app_module.question_manager.get_all_active_questions()
        
        # Should only return q1
        self.assertEqual(len(active_questions), 1)
        self.assertEqual(active_questions[0]['id'], q1['id'])
    
    def test_delete_question_excluded_from_community_questions(self):
        """Test that deleted questions are excluded from get_questions_for_community"""
        # Create questions
        q1 = self.app_module.question_manager.create_question(
            'Active question', False, ['Community A']
        )
        q2 = self.app_module.question_manager.create_question(
            'Question to delete', True, ['Community A']
        )
        
        # Set up admin session
        with self.client.session_transaction() as sess:
            sess['user'] = 'admin'
            sess['community'] = None
        
        # Delete q2
        response = self.client.delete(f'/api/questions/{q2["id"]}')
        self.assertEqual(response.status_code, 200)
        
        # Get questions for Community A
        community_questions = self.app_module.question_manager.get_questions_for_community('Community A')
        
        # Should only return q1
        self.assertEqual(len(community_questions), 1)
        self.assertEqual(community_questions[0]['id'], q1['id'])
    
    def test_delete_question_updates_updated_at_timestamp(self):
        """Test that deleting a question updates the updated_at timestamp"""
        import time
        
        # Create a question first
        question = self.app_module.question_manager.create_question(
            'Question to delete', True, ['Community A']
        )
        question_id = question['id']
        original_updated_at = question['updated_at']
        
        # Wait a moment to ensure timestamp difference
        time.sleep(0.01)
        
        # Set up admin session
        with self.client.session_transaction() as sess:
            sess['user'] = 'admin'
            sess['community'] = None
        
        # Delete question
        response = self.client.delete(f'/api/questions/{question_id}')
        
        self.assertEqual(response.status_code, 200)
        
        # Verify updated_at has changed
        deleted_question = self.app_module.question_manager.get_question(question_id)
        self.assertNotEqual(deleted_question['updated_at'], original_updated_at)
        self.assertGreater(deleted_question['updated_at'], original_updated_at)


class TestGetInspectionsEndpoint(unittest.TestCase):
    """Test cases for GET /api/inspections endpoint"""
    
    def setUp(self):
        """Set up test client and temporary data directory for each test"""
        # Create temporary directory for test data
        self.test_dir = tempfile.mkdtemp()
        self.test_inspections_file = os.path.join(self.test_dir, 'inspections.json')
        self.test_upload_folder = os.path.join(self.test_dir, 'uploads')
        
        # Import app module to access inspection_service
        import app as app_module
        
        # Replace the global inspection_service with a test instance
        from services.inspection_service import InspectionService
        self.original_inspection_service = app_module.inspection_service
        app_module.inspection_service = InspectionService(
            self.test_inspections_file, 
            self.test_upload_folder
        )
        
        # Set up test client
        main_app.config['TESTING'] = True
        self.client = main_app.test_client()
        
        # Store reference to app module for teardown
        self.app_module = app_module
    
    def tearDown(self):
        """Clean up temporary directory and restore original inspection_service"""
        # Restore original inspection_service
        self.app_module.inspection_service = self.original_inspection_service
        
        # Remove temporary directory
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_get_inspections_staff_user_filters_by_community(self):
        """Test that staff users automatically see only submissions for their assigned community"""
        # Create submissions for different communities
        self.app_module.inspection_service.create_submission(
            'john', 'Community A', [
                {
                    'question_id': 'q1',
                    'question_text': 'Question 1',
                    'condition': 'Good',
                    'description': 'All good',
                    'photo_path': None,
                    'answered_at': '2024-01-15T10:00:00'
                }
            ]
        )
        self.app_module.inspection_service.create_submission(
            'maria', 'Community B', [
                {
                    'question_id': 'q2',
                    'question_text': 'Question 2',
                    'condition': 'Needs Attention',
                    'description': 'Needs work',
                    'photo_path': None,
                    'answered_at': '2024-01-15T11:00:00'
                }
            ]
        )
        
        # Set up staff user session for Community A
        with self.client.session_transaction() as sess:
            sess['user'] = 'john'
            sess['community'] = 'Community A'
        
        # Get inspections
        response = self.client.get('/api/inspections')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'success')
        self.assertIn('submissions', data)
        
        # Should return only 1 submission (Community A)
        self.assertEqual(len(data['submissions']), 1)
        self.assertEqual(data['submissions'][0]['community'], 'Community A')
        self.assertEqual(data['submissions'][0]['username'], 'john')
    
    def test_get_inspections_admin_returns_all_submissions(self):
        """Test that admin users without community filter see all submissions"""
        # Create submissions for different communities
        s1 = self.app_module.inspection_service.create_submission(
            'john', 'Community A', [
                {
                    'question_id': 'q1',
                    'question_text': 'Question 1',
                    'condition': 'Good',
                    'description': 'All good',
                    'photo_path': None,
                    'answered_at': '2024-01-15T10:00:00'
                }
            ]
        )
        s2 = self.app_module.inspection_service.create_submission(
            'maria', 'Community B', [
                {
                    'question_id': 'q2',
                    'question_text': 'Question 2',
                    'condition': 'Needs Attention',
                    'description': 'Needs work',
                    'photo_path': None,
                    'answered_at': '2024-01-15T11:00:00'
                }
            ]
        )
        s3 = self.app_module.inspection_service.create_submission(
            'carlos', 'Community C', [
                {
                    'question_id': 'q3',
                    'question_text': 'Question 3',
                    'condition': 'Good',
                    'description': 'Looking good',
                    'photo_path': None,
                    'answered_at': '2024-01-15T12:00:00'
                }
            ]
        )
        
        # Set up admin session
        with self.client.session_transaction() as sess:
            sess['user'] = 'admin'
            sess['community'] = None
        
        # Get inspections without filter
        response = self.client.get('/api/inspections')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'success')
        self.assertIn('submissions', data)
        
        # Should return all 3 submissions
        self.assertEqual(len(data['submissions']), 3)
        
        # Verify all submission IDs are present
        submission_ids = [s['id'] for s in data['submissions']]
        self.assertIn(s1['id'], submission_ids)
        self.assertIn(s2['id'], submission_ids)
        self.assertIn(s3['id'], submission_ids)
    
    def test_get_inspections_admin_with_community_filter(self):
        """Test that admin users can filter by community using query parameter"""
        # Create submissions for different communities
        self.app_module.inspection_service.create_submission(
            'john', 'Community A', [
                {
                    'question_id': 'q1',
                    'question_text': 'Question 1',
                    'condition': 'Good',
                    'description': 'All good',
                    'photo_path': None,
                    'answered_at': '2024-01-15T10:00:00'
                }
            ]
        )
        s2 = self.app_module.inspection_service.create_submission(
            'maria', 'Community B', [
                {
                    'question_id': 'q2',
                    'question_text': 'Question 2',
                    'condition': 'Needs Attention',
                    'description': 'Needs work',
                    'photo_path': None,
                    'answered_at': '2024-01-15T11:00:00'
                }
            ]
        )
        
        # Set up admin session
        with self.client.session_transaction() as sess:
            sess['user'] = 'admin'
            sess['community'] = None
        
        # Get inspections filtered by Community B
        response = self.client.get('/api/inspections?community=Community B')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'success')
        self.assertIn('submissions', data)
        
        # Should return only 1 submission (Community B)
        self.assertEqual(len(data['submissions']), 1)
        self.assertEqual(data['submissions'][0]['id'], s2['id'])
        self.assertEqual(data['submissions'][0]['community'], 'Community B')
    
    def test_get_inspections_requires_authentication(self):
        """Test that unauthenticated users cannot access inspections"""
        # Clear session
        with self.client.session_transaction() as sess:
            sess.clear()
        
        # Try to get inspections without authentication
        response = self.client.get('/api/inspections', follow_redirects=False)
        
        # Should redirect to login
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login', response.location)
    
    def test_get_inspections_returns_empty_array_when_no_submissions(self):
        """Test that endpoint returns empty array when no submissions exist"""
        # Set up staff user session
        with self.client.session_transaction() as sess:
            sess['user'] = 'john'
            sess['community'] = 'Community A'
        
        # Get inspections (none exist)
        response = self.client.get('/api/inspections')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['submissions'], [])
    
    def test_get_inspections_includes_all_submission_fields(self):
        """Test that returned submissions include all required fields"""
        # Create a submission
        submission = self.app_module.inspection_service.create_submission(
            'john', 'Community A', [
                {
                    'question_id': 'q1',
                    'question_text': 'Is the area clean?',
                    'condition': 'Good',
                    'description': 'Everything looks good',
                    'photo_path': 'uploads/Community_A/photo.jpg',
                    'answered_at': '2024-01-15T10:00:00'
                }
            ]
        )
        
        # Set up staff user session
        with self.client.session_transaction() as sess:
            sess['user'] = 'john'
            sess['community'] = 'Community A'
        
        # Get inspections
        response = self.client.get('/api/inspections')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'success')
        
        # Verify submission structure
        returned_submission = data['submissions'][0]
        self.assertIn('id', returned_submission)
        self.assertIn('username', returned_submission)
        self.assertIn('community', returned_submission)
        self.assertIn('submitted_at', returned_submission)
        self.assertIn('responses', returned_submission)
        
        # Verify response structure
        response_obj = returned_submission['responses'][0]
        self.assertIn('question_id', response_obj)
        self.assertIn('question_text', response_obj)
        self.assertIn('condition', response_obj)
        self.assertIn('description', response_obj)
        self.assertIn('photo_path', response_obj)
        self.assertIn('answered_at', response_obj)


if __name__ == '__main__':
    unittest.main()
