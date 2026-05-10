#!/usr/bin/env python3
"""
Manual test script for inspection form submission
Tests the complete flow: login -> load questions -> submit inspection
"""

import requests
import json
import os

BASE_URL = "http://127.0.0.1:5001"

def test_inspection_flow():
    """Test the complete inspection submission flow"""
    
    # Create a session to maintain cookies
    session = requests.Session()
    
    print("=" * 60)
    print("Testing Inspection Form Submission Flow")
    print("=" * 60)
    
    # Step 1: Login
    print("\n1. Logging in as 'john' (Community A)...")
    login_response = session.post(
        f"{BASE_URL}/api/login",
        json={"username": "john", "password": "pass123"}
    )
    
    if login_response.status_code == 200:
        print("✅ Login successful")
        print(f"   User: {login_response.json()['username']}")
        print(f"   Community: {login_response.json()['community']}")
    else:
        print(f"❌ Login failed: {login_response.text}")
        return
    
    # Step 2: Load questions
    print("\n2. Loading questions for Community A...")
    questions_response = session.get(f"{BASE_URL}/api/questions")
    
    if questions_response.status_code == 200:
        questions_data = questions_response.json()
        questions = questions_data['questions']
        print(f"✅ Loaded {len(questions)} questions")
        for i, q in enumerate(questions, 1):
            print(f"   Q{i}: {q['text']}")
            print(f"       Photo required: {q['photo_required']}")
            print(f"       Communities: {', '.join(q['communities'])}")
    else:
        print(f"❌ Failed to load questions: {questions_response.text}")
        return
    
    # Step 3: Submit inspection (answer first 2 questions)
    print("\n3. Submitting inspection with 2 answered questions...")
    
    if len(questions) < 2:
        print("❌ Not enough questions to test submission")
        return
    
    # Create responses for first 2 questions
    responses = [
        {
            "question_id": questions[0]['id'],
            "question_text": questions[0]['text'],
            "condition": "Good",
            "description": "Everything looks clean and well-maintained"
        },
        {
            "question_id": questions[1]['id'],
            "question_text": questions[1]['text'],
            "condition": "Needs Attention",
            "description": "Some equipment needs to be reorganized"
        }
    ]
    
    # Create form data
    form_data = {
        'responses': json.dumps(responses)
    }
    
    # Submit inspection
    inspection_response = session.post(
        f"{BASE_URL}/api/inspections",
        data=form_data
    )
    
    if inspection_response.status_code == 201:
        print("✅ Inspection submitted successfully")
        submission = inspection_response.json()['submission']
        print(f"   Submission ID: {submission['id']}")
        print(f"   Username: {submission['username']}")
        print(f"   Community: {submission['community']}")
        print(f"   Responses: {len(submission['responses'])}")
        for i, resp in enumerate(submission['responses'], 1):
            print(f"   Response {i}:")
            print(f"     Question: {resp['question_text']}")
            print(f"     Condition: {resp['condition']}")
            print(f"     Description: {resp['description']}")
    else:
        print(f"❌ Inspection submission failed: {inspection_response.text}")
        return
    
    # Step 4: Verify inspection was saved
    print("\n4. Verifying inspection was saved...")
    inspections_response = session.get(f"{BASE_URL}/api/inspections")
    
    if inspections_response.status_code == 200:
        inspections_data = inspections_response.json()
        inspections = inspections_data['submissions']
        print(f"✅ Found {len(inspections)} inspection(s) in the system")
        if len(inspections) > 0:
            latest = inspections[-1]
            print(f"   Latest inspection:")
            print(f"     ID: {latest['id']}")
            print(f"     User: {latest['username']}")
            print(f"     Community: {latest['community']}")
            print(f"     Responses: {len(latest['responses'])}")
    else:
        print(f"❌ Failed to retrieve inspections: {inspections_response.text}")
    
    print("\n" + "=" * 60)
    print("Test completed successfully!")
    print("=" * 60)

if __name__ == "__main__":
    test_inspection_flow()
