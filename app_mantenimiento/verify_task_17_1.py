"""
Manual Verification Script for Task 17.1: No Real-Time Question Updates

This script verifies that:
1. Questions are filtered by community on page load
2. No real-time update mechanisms (polling, WebSockets) are implemented
3. Community-specific filtering ensures correct questions are shown on load

Requirements: 2.3
"""

import os
import re
import json


def check_file_for_patterns(filepath, patterns, description):
    """Check if file contains any of the given patterns"""
    print(f"\n{'='*70}")
    print(f"Checking: {description}")
    print(f"File: {filepath}")
    print(f"{'='*70}")
    
    if not os.path.exists(filepath):
        print(f"❌ File not found: {filepath}")
        return False
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    found_patterns = []
    for pattern_name, pattern in patterns.items():
        matches = re.findall(pattern, content, re.IGNORECASE)
        if matches:
            found_patterns.append((pattern_name, matches))
    
    if found_patterns:
        print(f"❌ FOUND real-time update patterns:")
        for pattern_name, matches in found_patterns:
            print(f"   - {pattern_name}: {len(matches)} occurrence(s)")
            for match in matches[:3]:  # Show first 3 matches
                print(f"     • {match[:100]}")
        return False
    else:
        print(f"✅ No real-time update patterns found")
        return True


def check_api_endpoints(filepath):
    """Check API endpoints for real-time update mechanisms"""
    print(f"\n{'='*70}")
    print(f"Checking API Endpoints")
    print(f"File: {filepath}")
    print(f"{'='*70}")
    
    if not os.path.exists(filepath):
        print(f"❌ File not found: {filepath}")
        return False
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check for WebSocket imports
    websocket_imports = re.findall(r'from.*websocket|import.*websocket|from.*socketio|import.*socketio', content, re.IGNORECASE)
    if websocket_imports:
        print(f"❌ Found WebSocket imports: {websocket_imports}")
        return False
    else:
        print(f"✅ No WebSocket imports found")
    
    # Check for streaming endpoints
    streaming_patterns = [
        r'@app\.route.*stream',
        r'@app\.route.*poll',
        r'@app\.route.*ws',
        r'@app\.route.*websocket',
        r'Response.*stream=True',
        r'generate\(\)',
    ]
    
    found_streaming = []
    for pattern in streaming_patterns:
        matches = re.findall(pattern, content, re.IGNORECASE)
        if matches:
            found_streaming.extend(matches)
    
    if found_streaming:
        print(f"❌ Found streaming endpoint patterns: {found_streaming}")
        return False
    else:
        print(f"✅ No streaming endpoint patterns found")
    
    return True


def check_questions_endpoint_implementation(filepath):
    """Check that /api/questions endpoint uses standard request-response"""
    print(f"\n{'='*70}")
    print(f"Checking /api/questions Endpoint Implementation")
    print(f"File: {filepath}")
    print(f"{'='*70}")
    
    if not os.path.exists(filepath):
        print(f"❌ File not found: {filepath}")
        return False
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find the get_questions function
    get_questions_match = re.search(
        r'@app\.route\(\'/api/questions\'.*?\)\s*@login_required\s*def get_questions\(\):.*?(?=\n@app\.route|\nif __name__|$)',
        content,
        re.DOTALL
    )
    
    if not get_questions_match:
        print(f"❌ Could not find /api/questions endpoint")
        return False
    
    endpoint_code = get_questions_match.group(0)
    
    # Check for community filtering
    if 'get_questions_for_community' in endpoint_code:
        print(f"✅ Endpoint uses community filtering")
    else:
        print(f"❌ Endpoint does not use community filtering")
        return False
    
    # Check for standard JSON response
    if 'jsonify' in endpoint_code and 'return' in endpoint_code:
        print(f"✅ Endpoint returns standard JSON response")
    else:
        print(f"❌ Endpoint does not return standard JSON response")
        return False
    
    # Check that it's NOT streaming
    if 'stream' not in endpoint_code.lower() and 'generate' not in endpoint_code:
        print(f"✅ Endpoint is NOT streaming")
    else:
        print(f"❌ Endpoint appears to be streaming")
        return False
    
    return True


def check_frontend_load_pattern(filepath, page_name):
    """Check that frontend loads questions once on page load"""
    print(f"\n{'='*70}")
    print(f"Checking Frontend Load Pattern: {page_name}")
    print(f"File: {filepath}")
    print(f"{'='*70}")
    
    if not os.path.exists(filepath):
        print(f"❌ File not found: {filepath}")
        return False
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check for loadQuestions function
    if 'loadQuestions' not in content:
        print(f"❌ No loadQuestions function found")
        return False
    else:
        print(f"✅ loadQuestions function exists")
    
    # Check that loadQuestions is called on page load
    load_on_init = re.search(r'window\.addEventListener\([\'"]load[\'"]\s*,.*?loadQuestions', content, re.DOTALL)
    if load_on_init:
        print(f"✅ loadQuestions is called on page load")
    else:
        # Check alternative pattern
        load_on_init = re.search(r'await loadQuestions\(\)', content)
        if load_on_init:
            print(f"✅ loadQuestions is called during initialization")
        else:
            print(f"⚠️  Could not verify loadQuestions is called on page load")
    
    # Check for setInterval with loadQuestions (polling)
    polling = re.search(r'setInterval\(.*?loadQuestions', content, re.DOTALL)
    if polling:
        print(f"❌ Found polling with setInterval")
        return False
    else:
        print(f"✅ No polling with setInterval found")
    
    return True


def main():
    """Run all verification checks"""
    print("\n" + "="*70)
    print("TASK 17.1 VERIFICATION: No Real-Time Question Updates")
    print("="*70)
    
    base_path = os.path.dirname(os.path.abspath(__file__))
    
    all_passed = True
    
    # 1. Check reporte.html (inspection form)
    reporte_patterns = {
        'setInterval with fetch': r'setInterval\(.*?fetch.*?questions',
        'setInterval with load': r'setInterval\(.*?loadQuestions',
        'WebSocket': r'new WebSocket|WebSocket\(',
        'EventSource': r'new EventSource|EventSource\(',
        'Server-Sent Events': r'text/event-stream',
    }
    
    result = check_file_for_patterns(
        os.path.join(base_path, 'templates', 'reporte.html'),
        reporte_patterns,
        "Inspection Form (reporte.html) - Real-time Update Patterns"
    )
    all_passed = all_passed and result
    
    # 2. Check question_manager.html
    result = check_file_for_patterns(
        os.path.join(base_path, 'templates', 'question_manager.html'),
        reporte_patterns,
        "Question Manager (question_manager.html) - Real-time Update Patterns"
    )
    all_passed = all_passed and result
    
    # 3. Check dashboard.html
    result = check_file_for_patterns(
        os.path.join(base_path, 'templates', 'dashboard.html'),
        reporte_patterns,
        "Dashboard (dashboard.html) - Real-time Update Patterns"
    )
    all_passed = all_passed and result
    
    # 4. Check API endpoints in app.py
    result = check_api_endpoints(
        os.path.join(base_path, 'app.py')
    )
    all_passed = all_passed and result
    
    # 5. Check /api/questions endpoint implementation
    result = check_questions_endpoint_implementation(
        os.path.join(base_path, 'app.py')
    )
    all_passed = all_passed and result
    
    # 6. Check frontend load patterns
    result = check_frontend_load_pattern(
        os.path.join(base_path, 'templates', 'reporte.html'),
        "Inspection Form"
    )
    all_passed = all_passed and result
    
    result = check_frontend_load_pattern(
        os.path.join(base_path, 'templates', 'question_manager.html'),
        "Question Manager"
    )
    all_passed = all_passed and result
    
    # Final summary
    print("\n" + "="*70)
    print("VERIFICATION SUMMARY")
    print("="*70)
    
    if all_passed:
        print("✅ ALL CHECKS PASSED")
        print("\nConclusion:")
        print("- No real-time update mechanisms (polling, WebSockets) found")
        print("- Questions are loaded once on page load")
        print("- Community-specific filtering happens on the backend")
        print("- Standard request-response pattern is used")
        print("\nRequirement 2.3 is correctly implemented:")
        print("'WHEN a Staff_User accesses the Inspection_Form,")
        print(" THE Inspection_System SHALL display only questions")
        print(" assigned to the user's community'")
        print("\nQuestions are filtered on load, not via real-time updates.")
    else:
        print("❌ SOME CHECKS FAILED")
        print("\nPlease review the failed checks above.")
    
    print("="*70 + "\n")
    
    return all_passed


if __name__ == '__main__':
    success = main()
    exit(0 if success else 1)
