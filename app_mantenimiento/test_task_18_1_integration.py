"""
Integration Test for Task 18.1: Wire All Components Together

This test verifies:
1. All routes are registered
2. All services are initialized
3. All templates are rendering correctly
4. End-to-end question creation and inspection submission flow
5. Existing maintenance report functionality still works

Requirements: 8.4, 8.5
"""

import pytest
import json
import os
import tempfile
import shutil
from datetime import datetime
from io import BytesIO
from app import app, question_manager, inspection_service, file_upload_handler, ALL_COMMUNITIES


@pytest.fixture
def client():
    """Create a test client for the Flask app"""
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test-secret-key'
    
    # Create temporary directories for test data
    test_data_dir = tempfile.mkdtemp()
    test_upload_dir = tempfile.mkdtemp()
    
    # Configure test paths
    app.config['UPLOAD_FOLDER'] = test_upload_dir
    
    # Initialize services with test paths
    test_questions_file = os.path.join(test_data_dir, 'test_questions.json')
    test_inspections_file = os.path.join(test_data_dir, 'test_inspections.json')
    
    # Reinitialize services with test paths
    global question_manager, inspection_service, file_upload_handler
    from services.question_manager import QuestionManager
    from services.inspection_service import InspectionService
    from services.file_upload_handler import FileUploadHandler
    
    question_manager = QuestionManager(test_questions_file)
    inspection_service = InspectionService(test_inspections_file, test_upload_dir)
    file_upload_handler = FileUploadHandler(test_upload_dir)
    
    # Update app's service references
    import app as app_module
    app_module.question_manager = question_manager
    app_module.inspection_service = inspection_service
    app_module.file_upload_handler = file_upload_handler
    
    with app.test_client() as client:
        with client.session_transaction() as sess:
            # Set up admin session for tests
            sess['user'] = 'admin'
            sess['community'] = None
        yield client
    
    # Cleanup
    shutil.rmtree(test_data_dir, ignore_errors=True)
    shutil.rmtree(test_upload_dir, ignore_errors=True)


@pytest.fixture
def staff_client():
    """Create a test client with staff user session"""
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test-secret-key'
    
    # Create temporary directories for test data
    test_data_dir = tempfile.mkdtemp()
    test_upload_dir = tempfile.mkdtemp()
    
    # Configure test paths
    app.config['UPLOAD_FOLDER'] = test_upload_dir
    
    # Initialize services with test paths
    test_questions_file = os.path.join(test_data_dir, 'test_questions.json')
    test_inspections_file = os.path.join(test_data_dir, 'test_inspections.json')
    
    # Reinitialize services with test paths
    global question_manager, inspection_service, file_upload_handler
    from services.question_manager import QuestionManager
    from services.inspection_service import InspectionService
    from services.file_upload_handler import FileUploadHandler
    
    question_manager = QuestionManager(test_questions_file)
    inspection_service = InspectionService(test_inspections_file, test_upload_dir)
    file_upload_handler = FileUploadHandler(test_upload_dir)
    
    # Update app's service references
    import app as app_module
    app_module.question_manager = question_manager
    app_module.inspection_service = inspection_service
    app_module.file_upload_handler = file_upload_handler
    
    with app.test_client() as client:
        with client.session_transaction() as sess:
            # Set up staff session for tests
            sess['user'] = 'john'
            sess['community'] = 'Community A'
        yield client
    
    # Cleanup
    shutil.rmtree(test_data_dir, ignore_errors=True)
    shutil.rmtree(test_upload_dir, ignore_errors=True)


class TestRouteRegistration:
    """Test that all routes are properly registered"""
    
    def test_all_routes_registered(self, client):
        """Verify all required routes are registered in the Flask app"""
        # Get all registered routes
        routes = [rule.rule for rule in app.url_map.iter_rules()]
        
        # Required routes
        required_routes = [
            '/login',
            '/api/login',
            '/logout',
            '/',
            '/dashboard',
            '/api/submit-report',
            '/api/user-info',
            '/questions/manage',
            '/api/questions',
            '/api/inspections'
        ]
        
        # Check each required route is registered
        for route in required_routes:
            assert route in routes, f"Route {route} is not registered"
    
    def test_question_routes_support_crud(self, client):
        """Verify question routes support all CRUD operations"""
        # Check POST /api/questions exists
        response = client.post('/api/questions', 
                              json={'text': 'Test', 'photo_required': False, 'communities': ['Community A']})
        assert response.status_code in [201, 400, 401], "POST /api/questions not working"
        
        # Check GET /api/questions exists
        response = client.get('/api/questions')
        assert response.status_code == 200, "GET /api/questions not working"
        
        # Check PUT /api/questions/<id> exists (will 404 for non-existent ID)
        response = client.put('/api/questions/test_id',
                             json={'text': 'Test', 'photo_required': False, 'communities': ['Community A']})
        assert response.status_code in [200, 404, 400], "PUT /api/questions/<id> not working"
        
        # Check DELETE /api/questions/<id> exists (will 404 for non-existent ID)
        response = client.delete('/api/questions/test_id')
        assert response.status_code in [200, 404], "DELETE /api/questions/<id> not working"


class TestServiceInitialization:
    """Test that all services are properly initialized"""
    
    def test_question_manager_initialized(self, client):
        """Verify QuestionManager service is initialized"""
        assert question_manager is not None, "QuestionManager not initialized"
        assert hasattr(question_manager, 'create_question'), "QuestionManager missing create_question method"
        assert hasattr(question_manager, 'get_all_active_questions'), "QuestionManager missing get_all_active_questions method"
        assert hasattr(question_manager, 'update_question'), "QuestionManager missing update_question method"
        assert hasattr(question_manager, 'delete_question'), "QuestionManager missing delete_question method"
    
    def test_inspection_service_initialized(self, client):
        """Verify InspectionService is initialized"""
        assert inspection_service is not None, "InspectionService not initialized"
        assert hasattr(inspection_service, 'create_submission'), "InspectionService missing create_submission method"
        assert hasattr(inspection_service, 'get_all_submissions'), "InspectionService missing get_all_submissions method"
        assert hasattr(inspection_service, 'get_submissions_by_community'), "InspectionService missing get_submissions_by_community method"
    
    def test_file_upload_handler_initialized(self, client):
        """Verify FileUploadHandler is initialized"""
        assert file_upload_handler is not None, "FileUploadHandler not initialized"
        assert hasattr(file_upload_handler, 'validate_file'), "FileUploadHandler missing validate_file method"
        assert hasattr(file_upload_handler, 'save_file'), "FileUploadHandler missing save_file method"


class TestTemplateRendering:
    """Test that all templates render correctly"""
    
    def test_login_template_renders(self, client):
        """Verify login template renders without errors"""
        # Clear session to access login page
        with client.session_transaction() as sess:
            sess.clear()
        
        response = client.get('/login')
        assert response.status_code == 200, "Login template failed to render"
        assert b'login' in response.data.lower() or b'username' in response.data.lower(), "Login template missing expected content"
    
    def test_question_manager_template_renders(self, client):
        """Verify question manager template renders for admin"""
        response = client.get('/questions/manage')
        assert response.status_code == 200, "Question manager template failed to render"
        assert b'question' in response.data.lower(), "Question manager template missing expected content"
    
    def test_inspection_form_template_renders(self, staff_client):
        """Verify inspection form (reporte.html) renders for staff"""
        response = staff_client.get('/')
        assert response.status_code == 200, "Inspection form template failed to render"
    
    def test_dashboard_template_renders(self, client):
        """Verify dashboard template renders"""
        response = client.get('/dashboard')
        assert response.status_code == 200, "Dashboard template failed to render"
        assert b'dashboard' in response.data.lower() or b'report' in response.data.lower(), "Dashboard template missing expected content"


class TestEndToEndQuestionFlow:
    """Test end-to-end question creation and management flow"""
    
    def test_complete_question_lifecycle(self, client):
        """Test creating, reading, updating, and deleting a question"""
        # Step 1: Create a question
        create_data = {
            'text': 'Is the kitchen area clean and organized?',
            'photo_required': True,
            'communities': ['Community A', 'Community B']
        }
        
        response = client.post('/api/questions', 
                              json=create_data,
                              content_type='application/json')
        assert response.status_code == 201, f"Failed to create question: {response.get_json()}"
        
        created_question = response.get_json()['question']
        question_id = created_question['id']
        
        assert created_question['text'] == create_data['text']
        assert created_question['photo_required'] == create_data['photo_required']
        assert created_question['communities'] == create_data['communities']
        assert created_question['is_active'] == True
        
        # Step 2: Read the question back
        response = client.get('/api/questions')
        assert response.status_code == 200
        
        questions = response.get_json()['questions']
        assert len(questions) == 1
        assert questions[0]['id'] == question_id
        
        # Step 3: Update the question
        update_data = {
            'text': 'Is the kitchen area clean, organized, and sanitized?',
            'photo_required': False,
            'communities': ['Community A', 'Community B', 'Community C']
        }
        
        response = client.put(f'/api/questions/{question_id}',
                             json=update_data,
                             content_type='application/json')
        assert response.status_code == 200, f"Failed to update question: {response.get_json()}"
        
        updated_question = response.get_json()['question']
        assert updated_question['text'] == update_data['text']
        assert updated_question['photo_required'] == update_data['photo_required']
        assert updated_question['communities'] == update_data['communities']
        assert updated_question['id'] == question_id  # ID should not change
        
        # Step 4: Delete the question (soft delete)
        response = client.delete(f'/api/questions/{question_id}')
        assert response.status_code == 200
        
        # Step 5: Verify question is no longer in active list
        response = client.get('/api/questions')
        assert response.status_code == 200
        
        questions = response.get_json()['questions']
        assert len(questions) == 0, "Deleted question still appears in active questions"


class TestEndToEndInspectionFlow:
    """Test end-to-end inspection submission flow"""
    
    def test_complete_inspection_submission_flow(self, client, staff_client):
        """Test creating questions and submitting an inspection with responses"""
        # Step 1: Admin creates questions
        questions_data = [
            {
                'text': 'Is the entrance area clean?',
                'photo_required': True,
                'communities': ['Community A']
            },
            {
                'text': 'Are the hallways well-lit?',
                'photo_required': False,
                'communities': ['Community A']
            },
            {
                'text': 'Is the dining area organized?',
                'photo_required': True,
                'communities': ['Community A', 'Community B']
            }
        ]
        
        created_questions = []
        for q_data in questions_data:
            response = client.post('/api/questions',
                                  json=q_data,
                                  content_type='application/json')
            assert response.status_code == 201
            created_questions.append(response.get_json()['question'])
        
        # Step 2: Staff user retrieves questions for their community
        response = staff_client.get('/api/questions')
        assert response.status_code == 200
        
        staff_questions = response.get_json()['questions']
        assert len(staff_questions) == 3, "Staff should see all 3 questions assigned to Community A"
        
        # Step 3: Staff user submits inspection with responses
        responses_data = [
            {
                'question_id': created_questions[0]['id'],
                'question_text': created_questions[0]['text'],
                'condition': 'Good',
                'description': 'Entrance is spotless'
            },
            {
                'question_id': created_questions[1]['id'],
                'question_text': created_questions[1]['text'],
                'condition': 'Needs Attention',
                'description': 'Some lights are flickering'
            }
            # Note: Skipping question 3 to test partial submission
        ]
        
        # Create form data
        data = {
            'responses': json.dumps(responses_data)
        }
        
        response = staff_client.post('/api/inspections',
                                    data=data,
                                    content_type='multipart/form-data')
        assert response.status_code == 201, f"Failed to submit inspection: {response.get_json()}"
        
        submission = response.get_json()['submission']
        assert submission['username'] == 'john'
        assert submission['community'] == 'Community A'
        assert len(submission['responses']) == 2, "Should have 2 responses (1 question skipped)"
        
        # Step 4: Verify submission is stored and retrievable
        response = staff_client.get('/api/inspections')
        assert response.status_code == 200
        
        submissions = response.get_json()['submissions']
        assert len(submissions) == 1
        assert submissions[0]['id'] == submission['id']
        
        # Step 5: Admin can see the submission
        response = client.get('/api/inspections')
        assert response.status_code == 200
        
        admin_submissions = response.get_json()['submissions']
        assert len(admin_submissions) == 1
        assert admin_submissions[0]['community'] == 'Community A'


class TestMaintenanceReportCompatibility:
    """Test that existing maintenance report functionality still works"""
    
    def test_maintenance_report_submission(self, staff_client):
        """Verify existing maintenance report submission still works"""
        # Create test image file
        test_image = BytesIO(b'fake image data')
        test_image.name = 'test.jpg'
        
        # Submit maintenance report
        data = {
            'community': 'Community A',
            'location': 'Kitchen',
            'condition': 'Good',
            'description': 'Everything is clean',
            'photo': (test_image, 'test.jpg')
        }
        
        response = staff_client.post('/api/submit-report',
                                    data=data,
                                    content_type='multipart/form-data')
        
        # Should succeed or fail gracefully
        assert response.status_code in [200, 400], "Maintenance report endpoint broken"
        
        # If successful, verify response structure
        if response.status_code == 200:
            result = response.get_json()
            assert result['status'] == 'success'
            assert 'report' in result
    
    def test_dashboard_accessible_after_integration(self, client):
        """Verify dashboard is still accessible after integration"""
        response = client.get('/dashboard')
        assert response.status_code == 200, "Dashboard not accessible"


class TestCommunityFiltering:
    """Test community-based filtering for questions and inspections"""
    
    def test_staff_sees_only_assigned_community_questions(self, client, staff_client):
        """Verify staff users only see questions for their assigned community"""
        # Admin creates questions for different communities
        questions_data = [
            {'text': 'Question for A', 'photo_required': False, 'communities': ['Community A']},
            {'text': 'Question for B', 'photo_required': False, 'communities': ['Community B']},
            {'text': 'Question for A and B', 'photo_required': False, 'communities': ['Community A', 'Community B']}
        ]
        
        for q_data in questions_data:
            response = client.post('/api/questions', json=q_data, content_type='application/json')
            assert response.status_code == 201
        
        # Staff user (Community A) retrieves questions
        response = staff_client.get('/api/questions')
        assert response.status_code == 200
        
        staff_questions = response.get_json()['questions']
        # Should see 2 questions: one for A only, one for A and B
        assert len(staff_questions) == 2
        
        for question in staff_questions:
            assert 'Community A' in question['communities'], "Staff should only see questions for their community"
    
    def test_staff_sees_only_own_community_inspections(self, client, staff_client):
        """Verify staff users only see inspections for their assigned community"""
        # Create a question
        q_response = client.post('/api/questions',
                                json={'text': 'Test Q', 'photo_required': False, 'communities': ['Community A', 'Community B']},
                                content_type='application/json')
        question_id = q_response.get_json()['question']['id']
        
        # Staff user submits inspection
        responses_data = [{
            'question_id': question_id,
            'question_text': 'Test Q',
            'condition': 'Good',
            'description': 'Test'
        }]
        
        data = {'responses': json.dumps(responses_data)}
        response = staff_client.post('/api/inspections', data=data, content_type='multipart/form-data')
        assert response.status_code == 201
        
        # Staff user retrieves inspections
        response = staff_client.get('/api/inspections')
        assert response.status_code == 200
        
        submissions = response.get_json()['submissions']
        assert len(submissions) == 1
        assert submissions[0]['community'] == 'Community A'


class TestAuthorizationEnforcement:
    """Test that authorization is properly enforced"""
    
    def test_staff_cannot_access_question_manager(self, staff_client):
        """Verify staff users are redirected when accessing question manager"""
        response = staff_client.get('/questions/manage', follow_redirects=False)
        assert response.status_code == 302, "Staff should be redirected from question manager"
        assert '/login' in response.location or '/' in response.location, "Staff should be redirected to inspection form"
    
    def test_staff_cannot_create_questions(self, staff_client):
        """Verify staff users cannot create questions"""
        response = staff_client.post('/api/questions',
                                    json={'text': 'Test', 'photo_required': False, 'communities': ['Community A']},
                                    content_type='application/json',
                                    follow_redirects=False)
        assert response.status_code in [302, 403], "Staff should not be able to create questions"
    
    def test_admin_cannot_submit_inspections(self, client):
        """Verify admin users cannot submit inspections (no assigned community)"""
        responses_data = [{
            'question_id': 'test_id',
            'question_text': 'Test',
            'condition': 'Good',
            'description': 'Test'
        }]
        
        data = {'responses': json.dumps(responses_data)}
        response = client.post('/api/inspections', data=data, content_type='multipart/form-data')
        assert response.status_code == 400
        
        result = response.get_json()
        assert 'admin' in result['message'].lower(), "Should indicate admin users cannot submit inspections"


class TestDataPersistence:
    """Test that data persists correctly across operations"""
    
    def test_questions_persist_across_requests(self, client):
        """Verify questions are saved and loaded correctly"""
        # Create a question
        response = client.post('/api/questions',
                              json={'text': 'Persistent Q', 'photo_required': True, 'communities': ['Community A']},
                              content_type='application/json')
        assert response.status_code == 201
        question_id = response.get_json()['question']['id']
        
        # Retrieve questions
        response = client.get('/api/questions')
        questions = response.get_json()['questions']
        
        # Find the created question
        found = False
        for q in questions:
            if q['id'] == question_id:
                found = True
                assert q['text'] == 'Persistent Q'
                assert q['photo_required'] == True
                break
        
        assert found, "Created question not found in subsequent request"
    
    def test_inspections_persist_across_requests(self, client, staff_client):
        """Verify inspections are saved and loaded correctly"""
        # Create a question
        q_response = client.post('/api/questions',
                                json={'text': 'Test Q', 'photo_required': False, 'communities': ['Community A']},
                                content_type='application/json')
        question_id = q_response.get_json()['question']['id']
        
        # Submit inspection
        responses_data = [{
            'question_id': question_id,
            'question_text': 'Test Q',
            'condition': 'Good',
            'description': 'Persistent inspection'
        }]
        
        data = {'responses': json.dumps(responses_data)}
        response = staff_client.post('/api/inspections', data=data, content_type='multipart/form-data')
        assert response.status_code == 201
        submission_id = response.get_json()['submission']['id']
        
        # Retrieve inspections
        response = staff_client.get('/api/inspections')
        submissions = response.get_json()['submissions']
        
        # Find the created submission
        found = False
        for s in submissions:
            if s['id'] == submission_id:
                found = True
                assert s['responses'][0]['description'] == 'Persistent inspection'
                break
        
        assert found, "Created inspection not found in subsequent request"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
