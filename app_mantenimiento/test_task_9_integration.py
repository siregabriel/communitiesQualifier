"""
Integration test for Task 9: Question Manager UI with Survey Types
Tests the complete flow of creating, editing, and filtering questions with survey types
"""

import pytest
import json
import os
from app import app, question_manager, survey_type_service

@pytest.fixture
def client():
    """Create a test client"""
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    
    with app.test_client() as client:
        # Login first
        client.post('/login', data={
            'username': 'admin',
            'password': 'admin123'
        }, follow_redirects=True)
        yield client

@pytest.fixture
def cleanup():
    """Cleanup test data after tests"""
    yield
    # Cleanup is handled by question_manager

def test_survey_types_api(client):
    """Test that survey types API returns correct data"""
    response = client.get('/api/survey-types')
    assert response.status_code == 200
    
    data = json.loads(response.data)
    assert 'survey_types' in data
    assert len(data['survey_types']) == 6
    
    # Verify all expected types are present
    type_ids = [t['id'] for t in data['survey_types']]
    expected_ids = ['full-regional', 'operational', 'sales-marketing', 
                    'clinical', 'dining', 'life-safety']
    for expected_id in expected_ids:
        assert expected_id in type_ids

def test_create_question_with_survey_types(client, cleanup):
    """Test creating a question with survey types"""
    question_data = {
        'text': 'Test question with survey types',
        'photo_required': True,
        'communities': ['Test Community'],
        'survey_types': ['operational', 'clinical']
    }
    
    response = client.post('/api/questions',
                          data=json.dumps(question_data),
                          content_type='application/json')
    
    assert response.status_code == 201
    data = json.loads(response.data)
    assert data['status'] == 'success'
    assert 'question' in data
    
    question = data['question']
    assert question['text'] == question_data['text']
    assert question['survey_types'] == question_data['survey_types']

def test_create_question_with_empty_survey_types(client, cleanup):
    """Test creating a question with empty survey types (all types)"""
    question_data = {
        'text': 'Test question for all types',
        'photo_required': False,
        'communities': ['Test Community'],
        'survey_types': []
    }
    
    response = client.post('/api/questions',
                          data=json.dumps(question_data),
                          content_type='application/json')
    
    assert response.status_code == 201
    data = json.loads(response.data)
    assert data['status'] == 'success'
    
    question = data['question']
    assert question['survey_types'] == []

def test_update_question_survey_types(client, cleanup):
    """Test updating a question's survey types"""
    # First create a question
    question_data = {
        'text': 'Test question to update',
        'photo_required': False,
        'communities': ['Test Community'],
        'survey_types': ['operational']
    }
    
    create_response = client.post('/api/questions',
                                  data=json.dumps(question_data),
                                  content_type='application/json')
    
    assert create_response.status_code == 201
    question_id = json.loads(create_response.data)['question']['id']
    
    # Update the survey types
    update_data = {
        'text': 'Test question to update',
        'photo_required': False,
        'communities': ['Test Community'],
        'survey_types': ['clinical', 'dining']
    }
    
    update_response = client.put(f'/api/questions/{question_id}',
                                 data=json.dumps(update_data),
                                 content_type='application/json')
    
    assert update_response.status_code == 200
    data = json.loads(update_response.data)
    assert data['status'] == 'success'
    
    question = data['question']
    assert question['survey_types'] == ['clinical', 'dining']

def test_question_manager_page_loads(client):
    """Test that the question manager page loads successfully"""
    response = client.get('/questions/manage')
    assert response.status_code == 200
    
    # Check for key UI elements
    html = response.data.decode('utf-8')
    assert 'surveyTypeFilter' in html
    assert 'survey-type-badge' in html
    assert 'loadSurveyTypes' in html
    assert 'filterQuestions' in html
    assert 'Survey Types' in html

def test_survey_type_colors_and_icons():
    """Test that survey types have correct colors and icons"""
    types = survey_type_service.get_all_survey_types()
    
    expected_data = {
        'full-regional': {'color': '#3b82f6', 'icon': 'fa-sitemap'},
        'operational': {'color': '#10b981', 'icon': 'fa-search-plus'},
        'sales-marketing': {'color': '#8b5cf6', 'icon': 'fa-chart-line'},
        'clinical': {'color': '#ef4444', 'icon': 'fa-user-md'},
        'dining': {'color': '#f59e0b', 'icon': 'fa-utensils'},
        'life-safety': {'color': '#eab308', 'icon': 'fa-exclamation-triangle'}
    }
    
    for survey_type in types:
        type_id = survey_type['id']
        assert type_id in expected_data
        assert survey_type['color'] == expected_data[type_id]['color']
        assert survey_type['icon'] == expected_data[type_id]['icon']

def test_filter_logic():
    """Test the filter logic for survey types"""
    # Create test questions
    questions = [
        {'id': '1', 'text': 'Q1', 'survey_types': ['operational']},
        {'id': '2', 'text': 'Q2', 'survey_types': ['clinical']},
        {'id': '3', 'text': 'Q3', 'survey_types': []},  # All types
        {'id': '4', 'text': 'Q4', 'survey_types': ['operational', 'clinical']},
    ]
    
    # Filter by operational
    filtered = [q for q in questions if not q['survey_types'] or 'operational' in q['survey_types']]
    assert len(filtered) == 3  # Q1, Q3, Q4
    assert '1' in [q['id'] for q in filtered]
    assert '3' in [q['id'] for q in filtered]
    assert '4' in [q['id'] for q in filtered]
    
    # Filter by clinical
    filtered = [q for q in questions if not q['survey_types'] or 'clinical' in q['survey_types']]
    assert len(filtered) == 3  # Q2, Q3, Q4
    assert '2' in [q['id'] for q in filtered]
    assert '3' in [q['id'] for q in filtered]
    assert '4' in [q['id'] for q in filtered]
    
    # No filter (all types)
    filtered = questions
    assert len(filtered) == 4

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
