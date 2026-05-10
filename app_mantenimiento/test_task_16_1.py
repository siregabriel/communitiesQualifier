"""
Test Suite for Task 16.1: Comprehensive Error Handling
Tests all API endpoints for proper error handling including:
- JSON parsing errors (400 Bad Request)
- File system errors (500 Internal Server Error)
- Malformed JSON files (fallback to empty state)
- Missing files (initialize with empty structure)
- Input sanitization
- HTML escaping
"""

import pytest
import json
import os
import tempfile
import shutil
from io import BytesIO
from app import app
from services.question_manager import QuestionManager
from services.inspection_service import InspectionService
from services.input_sanitizer import InputSanitizer


@pytest.fixture
def client():
    """Create test client"""
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test-secret-key'
    
    with app.test_client() as client:
        yield client


@pytest.fixture
def temp_data_dir():
    """Create temporary directory for test data"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def authenticated_admin_client(client):
    """Create authenticated admin client"""
    with client.session_transaction() as sess:
        sess['user'] = 'admin'
        sess['community'] = None
    return client


@pytest.fixture
def authenticated_staff_client(client):
    """Create authenticated staff client"""
    with client.session_transaction() as sess:
        sess['user'] = 'john'
        sess['community'] = 'Community A'
    return client


class TestJSONParsingErrors:
    """Test JSON parsing error handling (400 Bad Request)"""
    
    def test_login_invalid_json(self, client):
        """Test login with invalid JSON format"""
        response = client.post('/api/login',
                              data='invalid json',
                              content_type='application/json')
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['status'] == 'error'
        assert 'JSON' in data['message']
    
    def test_login_missing_content_type(self, client):
        """Test login without JSON content type"""
        response = client.post('/api/login',
                              data=json.dumps({'username': 'test', 'password': 'test'}))
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['status'] == 'error'
    
    def test_create_question_invalid_json(self, authenticated_admin_client):
        """Test create question with invalid JSON"""
        response = authenticated_admin_client.post('/api/questions',
                                                   data='not valid json',
                                                   content_type='application/json')
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['status'] == 'error'
        assert 'JSON' in data['message']
    
    def test_create_question_non_dict_json(self, authenticated_admin_client):
        """Test create question with JSON array instead of object"""
        response = authenticated_admin_client.post('/api/questions',
                                                   data=json.dumps(['not', 'an', 'object']),
                                                   content_type='application/json')
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['status'] == 'error'
        assert 'object' in data['message'].lower()
    
    def test_update_question_invalid_json(self, authenticated_admin_client):
        """Test update question with invalid JSON"""
        response = authenticated_admin_client.put('/api/questions/test_id',
                                                  data='invalid json',
                                                  content_type='application/json')
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['status'] == 'error'
        assert 'JSON' in data['message']
    
    def test_submit_inspection_invalid_responses_json(self, authenticated_staff_client):
        """Test inspection submission with invalid JSON in responses field"""
        response = authenticated_staff_client.post('/api/inspections',
                                                   data={'responses': 'not valid json'})
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['status'] == 'error'
        assert 'JSON' in data['message']
    
    def test_submit_inspection_non_array_responses(self, authenticated_staff_client):
        """Test inspection submission with non-array responses"""
        response = authenticated_staff_client.post('/api/inspections',
                                                   data={'responses': json.dumps({'not': 'array'})})
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['status'] == 'error'
        assert 'array' in data['message'].lower()


class TestInputSanitization:
    """Test input sanitization and HTML escaping"""
    
    def test_sanitize_string_basic(self):
        """Test basic string sanitization"""
        result = InputSanitizer.sanitize_string('  test  ')
        assert result == 'test'
    
    def test_sanitize_string_html_escape(self):
        """Test HTML escaping in strings"""
        result = InputSanitizer.sanitize_string('<script>alert("xss")</script>')
        assert '&lt;script&gt;' in result
        assert '<script>' not in result
    
    def test_sanitize_question_text(self):
        """Test question text sanitization with HTML"""
        text = '<b>Is the area clean?</b>'
        result = InputSanitizer.sanitize_question_text(text)
        assert '&lt;b&gt;' in result
        assert '<b>' not in result
    
    def test_sanitize_description(self):
        """Test description sanitization with HTML"""
        desc = 'Everything is <strong>good</strong>'
        result = InputSanitizer.sanitize_description(desc)
        assert '&lt;strong&gt;' in result
        assert '<strong>' not in result
    
    def test_sanitize_question_data(self):
        """Test question data sanitization"""
        data = {
            'text': '<script>alert("xss")</script>Is this clean?',
            'photo_required': True,
            'communities': ['<b>Community A</b>', 'Community B']
        }
        result = InputSanitizer.sanitize_question_data(data)
        assert '&lt;script&gt;' in result['text']
        assert '<script>' not in result['text']
        assert '&lt;b&gt;' in result['communities'][0]
    
    def test_sanitize_response_data(self):
        """Test response data sanitization"""
        response = {
            'question_id': 'q_123_456',
            'question_text': '<b>Question</b>',
            'condition': 'Good',
            'description': '<script>alert("xss")</script>Description'
        }
        result = InputSanitizer.sanitize_response_data(response)
        assert '&lt;b&gt;' in result['question_text']
        assert '&lt;script&gt;' in result['description']
        assert '<script>' not in result['description']
    
    def test_create_question_with_html(self, authenticated_admin_client):
        """Test creating question with HTML in text"""
        response = authenticated_admin_client.post('/api/questions',
                                                   data=json.dumps({
                                                       'text': '<script>alert("xss")</script>Is this clean?',
                                                       'photo_required': False,
                                                       'communities': ['Community A']
                                                   }),
                                                   content_type='application/json')
        assert response.status_code == 201
        data = json.loads(response.data)
        # HTML should be escaped
        assert '&lt;script&gt;' in data['question']['text']
        assert '<script>' not in data['question']['text']


class TestMissingRequiredFields:
    """Test validation of missing required fields"""
    
    def test_login_missing_username(self, client):
        """Test login with missing username"""
        response = client.post('/api/login',
                              data=json.dumps({'password': 'test'}),
                              content_type='application/json')
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['status'] == 'error'
        assert 'username' in data['message'].lower()
    
    def test_login_missing_password(self, client):
        """Test login with missing password"""
        response = client.post('/api/login',
                              data=json.dumps({'username': 'test'}),
                              content_type='application/json')
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['status'] == 'error'
        assert 'password' in data['message'].lower()
    
    def test_create_question_empty_text(self, authenticated_admin_client):
        """Test creating question with empty text"""
        response = authenticated_admin_client.post('/api/questions',
                                                   data=json.dumps({
                                                       'text': '',
                                                       'photo_required': False,
                                                       'communities': ['Community A']
                                                   }),
                                                   content_type='application/json')
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['status'] == 'error'
        assert 'empty' in data['message'].lower()
    
    def test_create_question_empty_communities(self, authenticated_admin_client):
        """Test creating question with empty communities array"""
        response = authenticated_admin_client.post('/api/questions',
                                                   data=json.dumps({
                                                       'text': 'Test question',
                                                       'photo_required': False,
                                                       'communities': []
                                                   }),
                                                   content_type='application/json')
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['status'] == 'error'
        assert 'community' in data['message'].lower()
    
    def test_submit_inspection_missing_responses(self, authenticated_staff_client):
        """Test inspection submission without responses"""
        response = authenticated_staff_client.post('/api/inspections',
                                                   data={})
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['status'] == 'error'
        assert 'responses' in data['message'].lower()


class TestFileSystemErrors:
    """Test file system error handling (500 Internal Server Error)"""
    
    def test_question_manager_malformed_json(self, temp_data_dir):
        """Test QuestionManager with malformed JSON file"""
        # Create malformed JSON file
        questions_file = os.path.join(temp_data_dir, 'questions.json')
        with open(questions_file, 'w') as f:
            f.write('{ invalid json }')
        
        # QuestionManager should initialize with empty state
        qm = QuestionManager(questions_file)
        assert qm.questions == []
        assert qm.version == "1.0"
    
    def test_question_manager_missing_file(self, temp_data_dir):
        """Test QuestionManager with missing file"""
        # File doesn't exist
        questions_file = os.path.join(temp_data_dir, 'nonexistent.json')
        
        # QuestionManager should initialize with empty state
        qm = QuestionManager(questions_file)
        assert qm.questions == []
        assert qm.version == "1.0"
    
    def test_inspection_service_malformed_json(self, temp_data_dir):
        """Test InspectionService with malformed JSON file"""
        # Create malformed JSON file
        inspections_file = os.path.join(temp_data_dir, 'inspections.json')
        with open(inspections_file, 'w') as f:
            f.write('{ not valid json }')
        
        upload_dir = os.path.join(temp_data_dir, 'uploads')
        
        # InspectionService should initialize with empty state
        ins = InspectionService(inspections_file, upload_dir)
        assert ins.submissions == []
    
    def test_inspection_service_missing_file(self, temp_data_dir):
        """Test InspectionService with missing file"""
        # File doesn't exist
        inspections_file = os.path.join(temp_data_dir, 'nonexistent.json')
        upload_dir = os.path.join(temp_data_dir, 'uploads')
        
        # InspectionService should initialize with empty state
        ins = InspectionService(inspections_file, upload_dir)
        assert ins.submissions == []


class TestFileUploadValidation:
    """Test file upload validation"""
    
    def test_invalid_file_type(self, authenticated_staff_client):
        """Test uploading invalid file type"""
        # Create a fake text file
        data = {
            'responses': json.dumps([{
                'question_id': 'q_123',
                'question_text': 'Test',
                'condition': 'Good',
                'description': 'Test'
            }]),
            'photo_0': (BytesIO(b'test content'), 'test.txt')
        }
        
        response = authenticated_staff_client.post('/api/inspections',
                                                   data=data,
                                                   content_type='multipart/form-data')
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['status'] == 'error'
        assert 'file type' in data['message'].lower() or 'invalid' in data['message'].lower()
    
    def test_file_too_large(self, authenticated_staff_client):
        """Test uploading file that exceeds size limit"""
        # Create a fake large file (17MB, exceeds 16MB limit)
        large_content = b'x' * (17 * 1024 * 1024)
        
        data = {
            'responses': json.dumps([{
                'question_id': 'q_123',
                'question_text': 'Test',
                'condition': 'Good',
                'description': 'Test'
            }]),
            'photo_0': (BytesIO(large_content), 'large.jpg')
        }
        
        response = authenticated_staff_client.post('/api/inspections',
                                                   data=data,
                                                   content_type='multipart/form-data')
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['status'] == 'error'
        assert 'size' in data['message'].lower() or 'exceeds' in data['message'].lower()


class TestValidationEdgeCases:
    """Test edge cases in validation"""
    
    def test_question_id_sanitization(self):
        """Test question_id sanitization removes special characters"""
        response = {
            'question_id': 'q_123; DROP TABLE questions;--',
            'condition': 'Good'
        }
        result = InputSanitizer.sanitize_response_data(response)
        # Should only contain alphanumeric and underscores
        assert ';' not in result['question_id']
        assert 'DROP' not in result['question_id']
    
    def test_condition_validation(self):
        """Test condition field validation"""
        response = {
            'question_id': 'q_123',
            'condition': 'Invalid Condition'
        }
        result = InputSanitizer.sanitize_response_data(response)
        # Invalid condition should be empty
        assert result['condition'] == ''
    
    def test_max_length_enforcement(self):
        """Test maximum length enforcement"""
        long_text = 'x' * 2000
        result = InputSanitizer.sanitize_string(long_text, max_length=100)
        assert len(result) == 100


def test_comprehensive_error_handling_integration(authenticated_admin_client, authenticated_staff_client):
    """Integration test for comprehensive error handling"""
    
    # Test 1: Create question with sanitized input
    response = authenticated_admin_client.post('/api/questions',
                                               data=json.dumps({
                                                   'text': '<b>Is the area clean?</b>',
                                                   'photo_required': True,
                                                   'communities': ['Community A']
                                               }),
                                               content_type='application/json')
    assert response.status_code == 201
    data = json.loads(response.data)
    question_id = data['question']['id']
    # Verify HTML is escaped
    assert '&lt;b&gt;' in data['question']['text']
    
    # Test 2: Update question with invalid JSON
    response = authenticated_admin_client.put(f'/api/questions/{question_id}',
                                             data='invalid json',
                                             content_type='application/json')
    assert response.status_code == 400
    
    # Test 3: Get questions (should work)
    response = authenticated_staff_client.get('/api/questions')
    assert response.status_code == 200
    
    # Test 4: Submit inspection with invalid condition
    response = authenticated_staff_client.post('/api/inspections',
                                               data={
                                                   'responses': json.dumps([{
                                                       'question_id': question_id,
                                                       'question_text': 'Test',
                                                       'condition': 'Invalid',
                                                       'description': 'Test'
                                                   }])
                                               })
    assert response.status_code == 400
    
    # Test 5: Delete question (should work)
    response = authenticated_admin_client.delete(f'/api/questions/{question_id}')
    assert response.status_code == 200


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
