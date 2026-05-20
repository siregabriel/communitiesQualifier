"""
Test for POST /api/inspections endpoint
Tests the inspection submission endpoint with various scenarios
"""

import pytest
import json
import os
import sys
from io import BytesIO

# Add parent directory to path to import app
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, inspection_service, file_upload_handler


@pytest.fixture
def client():
    """Create test client"""
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test-secret-key'
    
    with app.test_client() as client:
        yield client


@pytest.fixture
def authenticated_client(client):
    """Create authenticated test client with staff user"""
    with client.session_transaction() as sess:
        sess['user'] = 'john'
        sess['community'] = 'Community A'
    return client


@pytest.fixture
def admin_client(client):
    """Create authenticated test client with admin user"""
    with client.session_transaction() as sess:
        sess['user'] = 'admin'
        sess['community'] = None
    return client


def test_submit_inspection_requires_authentication(client):
    """Test that endpoint requires authentication"""
    response = client.post('/api/inspections')
    
    # Should redirect to login
    assert response.status_code == 302
    assert '/login' in response.location


def test_submit_inspection_admin_cannot_submit(admin_client):
    """Test that admin users cannot submit inspections"""
    data = {
        'responses': json.dumps([])
    }
    
    response = admin_client.post('/api/inspections', data=data)
    
    assert response.status_code == 400
    json_data = response.get_json()
    assert json_data['status'] == 'error'
    assert 'Admin users cannot submit inspections' in json_data['message']


def test_submit_inspection_no_responses(authenticated_client):
    """Test validation when no responses provided"""
    response = authenticated_client.post('/api/inspections', data={})
    
    assert response.status_code == 400
    json_data = response.get_json()
    assert json_data['status'] == 'error'
    assert 'No responses provided' in json_data['message']


def test_submit_inspection_invalid_json(authenticated_client):
    """Test validation with invalid JSON format"""
    data = {
        'responses': 'not valid json'
    }
    
    response = authenticated_client.post('/api/inspections', data=data)
    
    assert response.status_code == 400
    json_data = response.get_json()
    assert json_data['status'] == 'error'
    assert 'Invalid JSON format' in json_data['message']


def test_submit_inspection_responses_not_array(authenticated_client):
    """Test validation when responses is not an array"""
    data = {
        'responses': json.dumps({'not': 'an array'})
    }
    
    response = authenticated_client.post('/api/inspections', data=data)
    
    assert response.status_code == 400
    json_data = response.get_json()
    assert json_data['status'] == 'error'
    assert 'Responses must be an array' in json_data['message']


def test_submit_inspection_missing_question_id(authenticated_client):
    """Test validation when question_id is missing"""
    responses = [
        {
            'condition': 'Good',
            'description': 'Test description'
        }
    ]
    
    data = {
        'responses': json.dumps(responses)
    }
    
    response = authenticated_client.post('/api/inspections', data=data)
    
    assert response.status_code == 400
    json_data = response.get_json()
    assert json_data['status'] == 'error'
    assert 'question_id is required' in json_data['message']


def test_submit_inspection_missing_condition(authenticated_client):
    """Test validation when condition is missing"""
    responses = [
        {
            'question_id': 'q_123_456',
            'description': 'Test description'
        }
    ]
    
    data = {
        'responses': json.dumps(responses)
    }
    
    response = authenticated_client.post('/api/inspections', data=data)
    
    assert response.status_code == 400
    json_data = response.get_json()
    assert json_data['status'] == 'error'
    assert 'condition is required' in json_data['message']


def test_submit_inspection_invalid_condition(authenticated_client):
    """Test validation with invalid condition value"""
    responses = [
        {
            'question_id': 'q_123_456',
            'condition': 'Invalid Condition',
            'description': 'Test description'
        }
    ]
    
    data = {
        'responses': json.dumps(responses)
    }
    
    response = authenticated_client.post('/api/inspections', data=data)
    
    assert response.status_code == 400
    json_data = response.get_json()
    assert json_data['status'] == 'error'
    # InputSanitizer filters out invalid conditions, so it appears as "required"
    assert 'condition' in json_data['message'].lower()


def test_submit_inspection_success_without_photos(authenticated_client):
    """Test successful submission without photos"""
    responses = [
        {
            'question_id': 'q_123_456',
            'question_text': 'Is the area clean?',
            'condition': 'Pass',
            'description': 'Everything looks good'
        },
        {
            'question_id': 'q_789_012',
            'question_text': 'Are lights working?',
            'condition': 'Opportunity',
            'description': 'One bulb is out'
        }
    ]
    
    data = {
        'responses': json.dumps(responses)
    }
    
    response = authenticated_client.post('/api/inspections', data=data)
    
    assert response.status_code == 201
    json_data = response.get_json()
    assert json_data['status'] == 'success'
    assert 'submission' in json_data
    
    submission = json_data['submission']
    assert submission['username'] == 'john'
    assert submission['community'] == 'Community A'
    assert len(submission['responses']) == 2
    assert submission['responses'][0]['question_id'] == 'q_123_456'
    assert submission['responses'][0]['condition'] == 'Pass'
    assert submission['responses'][1]['question_id'] == 'q_789_012'
    assert submission['responses'][1]['condition'] == 'Opportunity'


def test_submit_inspection_with_photo(authenticated_client):
    """Test successful submission with photo upload"""
    responses = [
        {
            'question_id': 'q_123_456',
            'question_text': 'Is the area clean?',
            'condition': 'Excellence',
            'description': 'Everything looks good'
        }
    ]
    
    # Create a fake image file
    fake_image = BytesIO(b'fake image content')
    fake_image.name = 'test.jpg'
    
    data = {
        'responses': json.dumps(responses),
        'photo_0': (fake_image, 'test.jpg')
    }
    
    response = authenticated_client.post(
        '/api/inspections',
        data=data,
        content_type='multipart/form-data'
    )
    
    assert response.status_code == 201
    json_data = response.get_json()
    assert json_data['status'] == 'success'
    assert 'submission' in json_data
    
    submission = json_data['submission']
    assert len(submission['responses']) == 1
    assert submission['responses'][0]['photo_path'] is not None
    assert 'Community_A' in submission['responses'][0]['photo_path']


def test_submit_inspection_invalid_file_type(authenticated_client):
    """Test validation with invalid file type"""
    responses = [
        {
            'question_id': 'q_123_456',
            'question_text': 'Is the area clean?',
            'condition': 'Fail',
            'description': 'Everything looks good'
        }
    ]
    
    # Create a fake non-image file
    fake_file = BytesIO(b'fake file content')
    fake_file.name = 'test.txt'
    
    data = {
        'responses': json.dumps(responses),
        'photo_0': (fake_file, 'test.txt')
    }
    
    response = authenticated_client.post(
        '/api/inspections',
        data=data,
        content_type='multipart/form-data'
    )
    
    assert response.status_code == 400
    json_data = response.get_json()
    assert json_data['status'] == 'error'
    assert 'Invalid file type' in json_data['message']


def test_submit_inspection_empty_responses_array(authenticated_client):
    """Test submission with empty responses array (partial submission)"""
    data = {
        'responses': json.dumps([])
    }
    
    response = authenticated_client.post('/api/inspections', data=data)
    
    # Should succeed with empty responses (partial submission allowed)
    assert response.status_code == 201
    json_data = response.get_json()
    assert json_data['status'] == 'success'
    assert 'submission' in json_data
    assert len(json_data['submission']['responses']) == 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
