"""
Manual test for POST /api/inspections endpoint
Tests the inspection submission endpoint without pytest
"""

import json
import sys
import os
from io import BytesIO

# Add parent directory to path to import app
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app


def test_endpoint():
    """Run manual tests on the inspection endpoint"""
    
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test-secret-key'
    
    client = app.test_client()
    
    print("=" * 60)
    print("Testing POST /api/inspections endpoint")
    print("=" * 60)
    
    # Test 1: Unauthenticated request
    print("\n1. Testing unauthenticated request...")
    response = client.post('/api/inspections')
    assert response.status_code == 302, f"Expected 302, got {response.status_code}"
    print("   ✓ Correctly redirects to login")
    
    # Test 2: Admin user cannot submit
    print("\n2. Testing admin user cannot submit...")
    with client.session_transaction() as sess:
        sess['user'] = 'admin'
        sess['community'] = None
    
    data = {'responses': json.dumps([])}
    response = client.post('/api/inspections', data=data)
    assert response.status_code == 400, f"Expected 400, got {response.status_code}"
    json_data = response.get_json()
    assert 'Admin users cannot submit' in json_data['message']
    print("   ✓ Admin users correctly rejected")
    
    # Test 3: Missing responses
    print("\n3. Testing missing responses...")
    with client.session_transaction() as sess:
        sess['user'] = 'john'
        sess['community'] = 'Community A'
    
    response = client.post('/api/inspections', data={})
    assert response.status_code == 400, f"Expected 400, got {response.status_code}"
    json_data = response.get_json()
    assert 'No responses provided' in json_data['message']
    print("   ✓ Missing responses correctly rejected")
    
    # Test 4: Invalid JSON
    print("\n4. Testing invalid JSON...")
    data = {'responses': 'not valid json'}
    response = client.post('/api/inspections', data=data)
    assert response.status_code == 400, f"Expected 400, got {response.status_code}"
    json_data = response.get_json()
    assert 'Invalid JSON format' in json_data['message']
    print("   ✓ Invalid JSON correctly rejected")
    
    # Test 5: Responses not an array
    print("\n5. Testing responses not an array...")
    data = {'responses': json.dumps({'not': 'an array'})}
    response = client.post('/api/inspections', data=data)
    assert response.status_code == 400, f"Expected 400, got {response.status_code}"
    json_data = response.get_json()
    assert 'Responses must be an array' in json_data['message']
    print("   ✓ Non-array responses correctly rejected")
    
    # Test 6: Missing question_id
    print("\n6. Testing missing question_id...")
    responses = [{'condition': 'Good', 'description': 'Test'}]
    data = {'responses': json.dumps(responses)}
    response = client.post('/api/inspections', data=data)
    assert response.status_code == 400, f"Expected 400, got {response.status_code}"
    json_data = response.get_json()
    assert 'question_id is required' in json_data['message']
    print("   ✓ Missing question_id correctly rejected")
    
    # Test 7: Missing condition
    print("\n7. Testing missing condition...")
    responses = [{'question_id': 'q_123_456', 'description': 'Test'}]
    data = {'responses': json.dumps(responses)}
    response = client.post('/api/inspections', data=data)
    assert response.status_code == 400, f"Expected 400, got {response.status_code}"
    json_data = response.get_json()
    assert 'condition is required' in json_data['message']
    print("   ✓ Missing condition correctly rejected")
    
    # Test 8: Invalid condition value
    print("\n8. Testing invalid condition value...")
    responses = [{'question_id': 'q_123_456', 'condition': 'Invalid', 'description': 'Test'}]
    data = {'responses': json.dumps(responses)}
    response = client.post('/api/inspections', data=data)
    assert response.status_code == 400, f"Expected 400, got {response.status_code}"
    json_data = response.get_json()
    assert 'condition must be' in json_data['message']
    print("   ✓ Invalid condition correctly rejected")
    
    # Test 9: Successful submission without photos
    print("\n9. Testing successful submission without photos...")
    responses = [
        {
            'question_id': 'q_123_456',
            'question_text': 'Is the area clean?',
            'condition': 'Good',
            'description': 'Everything looks good'
        },
        {
            'question_id': 'q_789_012',
            'question_text': 'Are lights working?',
            'condition': 'Needs Attention',
            'description': 'One bulb is out'
        }
    ]
    data = {'responses': json.dumps(responses)}
    response = client.post('/api/inspections', data=data)
    assert response.status_code == 201, f"Expected 201, got {response.status_code}"
    json_data = response.get_json()
    assert json_data['status'] == 'success'
    assert 'submission' in json_data
    submission = json_data['submission']
    assert submission['username'] == 'john'
    assert submission['community'] == 'Community A'
    assert len(submission['responses']) == 2
    print("   ✓ Successful submission without photos")
    print(f"     - Submission ID: {submission['id']}")
    print(f"     - Username: {submission['username']}")
    print(f"     - Community: {submission['community']}")
    print(f"     - Responses: {len(submission['responses'])}")
    
    # Test 10: Empty responses array (partial submission)
    print("\n10. Testing empty responses array (partial submission)...")
    data = {'responses': json.dumps([])}
    response = client.post('/api/inspections', data=data)
    assert response.status_code == 201, f"Expected 201, got {response.status_code}"
    json_data = response.get_json()
    assert json_data['status'] == 'success'
    assert len(json_data['submission']['responses']) == 0
    print("   ✓ Empty responses array accepted (partial submission)")
    
    # Test 11: Successful submission with photo
    print("\n11. Testing successful submission with photo...")
    responses = [
        {
            'question_id': 'q_photo_test',
            'question_text': 'Photo test question',
            'condition': 'Good',
            'description': 'Testing photo upload'
        }
    ]
    
    # Create a fake image file
    fake_image = BytesIO(b'fake image content for testing')
    
    data = {
        'responses': json.dumps(responses),
        'photo_0': (fake_image, 'test.jpg')
    }
    
    response = client.post(
        '/api/inspections',
        data=data,
        content_type='multipart/form-data'
    )
    assert response.status_code == 201, f"Expected 201, got {response.status_code}"
    json_data = response.get_json()
    assert json_data['status'] == 'success'
    submission = json_data['submission']
    assert len(submission['responses']) == 1
    assert submission['responses'][0]['photo_path'] is not None
    print("   ✓ Successful submission with photo")
    print(f"     - Photo path: {submission['responses'][0]['photo_path']}")
    
    # Test 12: Invalid file type
    print("\n12. Testing invalid file type...")
    responses = [
        {
            'question_id': 'q_invalid_file',
            'question_text': 'Invalid file test',
            'condition': 'Good',
            'description': 'Testing invalid file'
        }
    ]
    
    fake_file = BytesIO(b'fake file content')
    
    data = {
        'responses': json.dumps(responses),
        'photo_0': (fake_file, 'test.txt')
    }
    
    response = client.post(
        '/api/inspections',
        data=data,
        content_type='multipart/form-data'
    )
    assert response.status_code == 400, f"Expected 400, got {response.status_code}"
    json_data = response.get_json()
    assert 'Invalid file type' in json_data['message']
    print("   ✓ Invalid file type correctly rejected")
    
    print("\n" + "=" * 60)
    print("All tests passed! ✓")
    print("=" * 60)


if __name__ == '__main__':
    try:
        test_endpoint()
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
