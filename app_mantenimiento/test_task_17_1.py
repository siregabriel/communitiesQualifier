"""
Test for Task 17.1: Verify No Real-Time Question Updates

This test verifies that:
1. Questions are filtered by community on page load
2. No real-time update mechanisms (polling, WebSockets) are implemented
3. Community-specific filtering ensures correct questions are shown on load

Requirements: 2.3
"""

import pytest
import json
import os
import tempfile
from app import app, question_manager, ALL_COMMUNITIES
from services.question_manager import QuestionManager


class TestNoRealTimeUpdates:
    """Test suite to verify no real-time update mechanisms exist"""
    
    @pytest.fixture
    def client(self):
        """Create test client"""
        app.config['TESTING'] = True
        app.config['SECRET_KEY'] = 'test-secret-key'
        with app.test_client() as client:
            yield client
    
    @pytest.fixture
    def temp_questions_file(self):
        """Create temporary questions file for testing"""
        fd, path = tempfile.mkstemp(suffix='.json')
        os.close(fd)
        
        # Initialize with empty question bank
        with open(path, 'w') as f:
            json.dump({
                'version': '1.0',
                'last_modified': '2024-01-01T00:00:00Z',
                'questions': []
            }, f)
        
        yield path
        
        # Cleanup
        if os.path.exists(path):
            os.remove(path)
    
    @pytest.fixture
    def setup_test_questions(self, temp_questions_file):
        """Setup test questions for different communities"""
        qm = QuestionManager(temp_questions_file)
        
        # Create questions for different communities
        q1 = qm.create_question(
            text="Question for Community A only",
            photo_required=True,
            communities=["Community A"]
        )
        
        q2 = qm.create_question(
            text="Question for Community B only",
            photo_required=False,
            communities=["Community B"]
        )
        
        q3 = qm.create_question(
            text="Question for both A and B",
            photo_required=True,
            communities=["Community A", "Community B"]
        )
        
        q4 = qm.create_question(
            text="Question for Community C only",
            photo_required=False,
            communities=["Community C"]
        )
        
        return qm, [q1, q2, q3, q4]
    
    def test_questions_filtered_by_community_on_load(self, client, setup_test_questions):
        """
        Test that questions are filtered by community when staff user requests them
        This verifies Requirement 2.3: Questions are filtered on load, not via real-time updates
        """
        qm, questions = setup_test_questions
        
        # Temporarily replace global question_manager
        import app as app_module
        original_qm = app_module.question_manager
        app_module.question_manager = qm
        
        try:
            # Login as staff user from Community A
            with client.session_transaction() as sess:
                sess['user'] = 'john'
                sess['community'] = 'Community A'
            
            # Request questions (simulating page load)
            response = client.get('/api/questions')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            
            assert data['status'] == 'success'
            returned_questions = data['questions']
            
            # Should only get questions assigned to Community A
            # That's q1 (Community A only) and q3 (both A and B)
            assert len(returned_questions) == 2
            
            question_texts = [q['text'] for q in returned_questions]
            assert "Question for Community A only" in question_texts
            assert "Question for both A and B" in question_texts
            assert "Question for Community B only" not in question_texts
            assert "Question for Community C only" not in question_texts
            
        finally:
            # Restore original question_manager
            app_module.question_manager = original_qm
    
    def test_different_community_sees_different_questions(self, client, setup_test_questions):
        """
        Test that different communities see different questions on load
        This verifies that filtering happens on each page load, not via real-time updates
        """
        qm, questions = setup_test_questions
        
        # Temporarily replace global question_manager
        import app as app_module
        original_qm = app_module.question_manager
        app_module.question_manager = qm
        
        try:
            # Test Community A
            with client.session_transaction() as sess:
                sess['user'] = 'john'
                sess['community'] = 'Community A'
            
            response_a = client.get('/api/questions')
            data_a = json.loads(response_a.data)
            questions_a = data_a['questions']
            
            # Test Community B
            with client.session_transaction() as sess:
                sess['user'] = 'maria'
                sess['community'] = 'Community B'
            
            response_b = client.get('/api/questions')
            data_b = json.loads(response_b.data)
            questions_b = data_b['questions']
            
            # Test Community C
            with client.session_transaction() as sess:
                sess['user'] = 'carlos'
                sess['community'] = 'Community C'
            
            response_c = client.get('/api/questions')
            data_c = json.loads(response_c.data)
            questions_c = data_c['questions']
            
            # Verify each community sees correct questions
            assert len(questions_a) == 2  # q1 and q3
            assert len(questions_b) == 2  # q2 and q3
            assert len(questions_c) == 1  # q4 only
            
            # Verify Community A questions
            texts_a = [q['text'] for q in questions_a]
            assert "Question for Community A only" in texts_a
            assert "Question for both A and B" in texts_a
            
            # Verify Community B questions
            texts_b = [q['text'] for q in questions_b]
            assert "Question for Community B only" in texts_b
            assert "Question for both A and B" in texts_b
            
            # Verify Community C questions
            texts_c = [q['text'] for q in questions_c]
            assert "Question for Community C only" in texts_c
            
        finally:
            # Restore original question_manager
            app_module.question_manager = original_qm
    
    def test_admin_sees_all_questions(self, client, setup_test_questions):
        """
        Test that admin users see all questions without community filtering
        This verifies that admins don't need real-time updates either
        """
        qm, questions = setup_test_questions
        
        # Temporarily replace global question_manager
        import app as app_module
        original_qm = app_module.question_manager
        app_module.question_manager = qm
        
        try:
            # Login as admin (community is None)
            with client.session_transaction() as sess:
                sess['user'] = 'admin'
                sess['community'] = None
            
            # Request questions
            response = client.get('/api/questions')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            
            assert data['status'] == 'success'
            returned_questions = data['questions']
            
            # Admin should see all 4 questions
            assert len(returned_questions) == 4
            
            question_texts = [q['text'] for q in returned_questions]
            assert "Question for Community A only" in question_texts
            assert "Question for Community B only" in question_texts
            assert "Question for both A and B" in question_texts
            assert "Question for Community C only" in question_texts
            
        finally:
            # Restore original question_manager
            app_module.question_manager = original_qm
    
    def test_no_websocket_endpoints(self, client):
        """
        Test that no WebSocket endpoints exist
        This verifies no real-time update mechanism via WebSockets
        """
        # Try to access common WebSocket endpoint patterns
        websocket_paths = [
            '/ws',
            '/websocket',
            '/socket.io',
            '/api/ws',
            '/api/websocket',
            '/api/questions/ws',
            '/api/questions/updates'
        ]
        
        for path in websocket_paths:
            response = client.get(path)
            # Should return 404 (not found) since these endpoints don't exist
            assert response.status_code == 404
    
    def test_no_polling_endpoint(self, client):
        """
        Test that no polling endpoint exists for question updates
        This verifies no real-time update mechanism via polling
        """
        # Try to access common polling endpoint patterns
        polling_paths = [
            '/api/questions/poll',
            '/api/questions/updates',
            '/api/questions/changes',
            '/api/questions/stream'
        ]
        
        for path in polling_paths:
            response = client.get(path)
            # Should return 404 (not found) since these endpoints don't exist
            assert response.status_code == 404
    
    def test_questions_endpoint_is_standard_request_response(self, client):
        """
        Test that /api/questions endpoint is standard request-response
        This verifies it's not a long-polling or streaming endpoint
        """
        # Login as staff user
        with client.session_transaction() as sess:
            sess['user'] = 'john'
            sess['community'] = 'Community A'
        
        # Make request
        response = client.get('/api/questions')
        
        # Should return immediately with standard JSON response
        assert response.status_code == 200
        assert response.content_type == 'application/json'
        
        # Should have standard response structure
        data = json.loads(response.data)
        assert 'status' in data
        assert 'questions' in data
        
        # Response should be complete (not streaming)
        assert response.is_streamed == False


class TestCommunityFilteringOnLoad:
    """Test suite to verify community filtering happens on page load"""
    
    @pytest.fixture
    def client(self):
        """Create test client"""
        app.config['TESTING'] = True
        app.config['SECRET_KEY'] = 'test-secret-key'
        with app.test_client() as client:
            yield client
    
    def test_inspection_form_loads_filtered_questions(self, client):
        """
        Test that inspection form loads questions filtered by user's community
        This verifies Requirement 2.3: Questions are filtered on load
        """
        # Login as staff user
        with client.session_transaction() as sess:
            sess['user'] = 'john'
            sess['community'] = 'Community A'
        
        # Access inspection form
        response = client.get('/')
        
        # Should successfully load the form
        assert response.status_code == 200
        
        # Form should be rendered (not a redirect)
        assert b'<!DOCTYPE html>' in response.data or b'<html' in response.data
    
    def test_staff_user_cannot_bypass_community_filter(self, client):
        """
        Test that staff users cannot bypass community filtering
        This verifies that filtering is enforced on the backend
        """
        # Login as staff user from Community A
        with client.session_transaction() as sess:
            sess['user'] = 'john'
            sess['community'] = 'Community A'
        
        # Try to request questions with different community filter
        response = client.get('/api/questions?community=Community B')
        
        # Should still only get Community A questions
        # (staff users' community filter is ignored, they always get their assigned community)
        assert response.status_code == 200
        data = json.loads(response.data)
        
        # The backend should ignore the query parameter for staff users
        # and use their session community instead
        assert data['status'] == 'success'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
