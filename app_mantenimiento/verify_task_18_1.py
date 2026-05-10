#!/usr/bin/env python3
"""
Verification Script for Task 18.1: Wire All Components Together

This script performs comprehensive verification of:
1. All routes are registered
2. All services are initialized
3. All templates exist and are accessible
4. End-to-end question creation and inspection submission flow
5. Existing maintenance report functionality still works

Requirements: 8.4, 8.5
"""

import sys
import os

# Color codes for output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

def print_success(message):
    print(f"{GREEN}✓{RESET} {message}")

def print_error(message):
    print(f"{RED}✗{RESET} {message}")

def print_info(message):
    print(f"{BLUE}ℹ{RESET} {message}")

def print_section(title):
    print(f"\n{YELLOW}{'=' * 60}{RESET}")
    print(f"{YELLOW}{title}{RESET}")
    print(f"{YELLOW}{'=' * 60}{RESET}")

def verify_imports():
    """Verify all required modules can be imported"""
    print_section("1. Verifying Imports")
    
    try:
        from app import app, question_manager, inspection_service, file_upload_handler, ALL_COMMUNITIES
        print_success("All modules imported successfully")
        return True, (app, question_manager, inspection_service, file_upload_handler, ALL_COMMUNITIES)
    except ImportError as e:
        print_error(f"Failed to import modules: {e}")
        return False, None

def verify_services(services):
    """Verify all services are properly initialized"""
    print_section("2. Verifying Service Initialization")
    
    app, question_manager, inspection_service, file_upload_handler, ALL_COMMUNITIES = services
    
    # Check QuestionManager
    if question_manager is None:
        print_error("QuestionManager is not initialized")
        return False
    
    required_methods = ['create_question', 'get_all_active_questions', 'get_questions_for_community', 
                       'update_question', 'delete_question', 'save_to_file', 'load_from_file']
    for method in required_methods:
        if not hasattr(question_manager, method):
            print_error(f"QuestionManager missing method: {method}")
            return False
    print_success(f"QuestionManager initialized with all required methods")
    
    # Check InspectionService
    if inspection_service is None:
        print_error("InspectionService is not initialized")
        return False
    
    required_methods = ['create_submission', 'get_all_submissions', 'get_submissions_by_community',
                       'save_to_file', 'load_from_file']
    for method in required_methods:
        if not hasattr(inspection_service, method):
            print_error(f"InspectionService missing method: {method}")
            return False
    print_success(f"InspectionService initialized with all required methods")
    
    # Check FileUploadHandler
    if file_upload_handler is None:
        print_error("FileUploadHandler is not initialized")
        return False
    
    required_methods = ['validate_file', 'save_file', 'ensure_community_folder']
    for method in required_methods:
        if not hasattr(file_upload_handler, method):
            print_error(f"FileUploadHandler missing method: {method}")
            return False
    print_success(f"FileUploadHandler initialized with all required methods")
    
    # Check communities
    if len(ALL_COMMUNITIES) != 38:
        print_error(f"Expected 38 communities, found {len(ALL_COMMUNITIES)}")
        return False
    print_success(f"All 38 communities configured")
    
    return True

def verify_routes(app):
    """Verify all required routes are registered"""
    print_section("3. Verifying Route Registration")
    
    required_routes = {
        '/login': ['GET'],
        '/api/login': ['POST'],
        '/logout': ['GET'],
        '/': ['GET'],
        '/dashboard': ['GET'],
        '/api/submit-report': ['POST'],
        '/api/user-info': ['GET'],
        '/questions/manage': ['GET'],
        '/api/questions': ['GET', 'POST'],
        '/api/questions/<question_id>': ['PUT', 'DELETE'],
        '/api/inspections': ['GET', 'POST']
    }
    
    # Flask registers each method as a separate rule, so we need to aggregate them
    registered_routes = {}
    for rule in app.url_map.iter_rules():
        if rule.endpoint != 'static':
            methods = list(rule.methods - {'HEAD', 'OPTIONS'})
            if rule.rule not in registered_routes:
                registered_routes[rule.rule] = []
            registered_routes[rule.rule].extend(methods)
    
    all_found = True
    for route, expected_methods in required_routes.items():
        if route not in registered_routes:
            print_error(f"Route not found: {route}")
            all_found = False
        else:
            for method in expected_methods:
                if method not in registered_routes[route]:
                    print_error(f"Route {route} missing method: {method}")
                    all_found = False
    
    if all_found:
        print_success(f"All {len(required_routes)} required routes registered correctly")
        print_info(f"Total unique routes in app: {len(registered_routes)}")
    
    return all_found

def verify_templates():
    """Verify all required templates exist"""
    print_section("4. Verifying Templates")
    
    required_templates = [
        'login.html',
        'reporte.html',
        'dashboard.html',
        'question_manager.html'
    ]
    
    templates_dir = os.path.join(os.path.dirname(__file__), 'templates')
    
    all_found = True
    for template in required_templates:
        template_path = os.path.join(templates_dir, template)
        if not os.path.exists(template_path):
            print_error(f"Template not found: {template}")
            all_found = False
        else:
            file_size = os.path.getsize(template_path)
            print_success(f"Template found: {template} ({file_size} bytes)")
    
    return all_found

def verify_data_structure():
    """Verify data directory and JSON files are properly set up"""
    print_section("5. Verifying Data Structure")
    
    data_dir = os.path.join(os.path.dirname(__file__), 'data')
    
    # Check data directory exists
    if not os.path.exists(data_dir):
        print_error("Data directory does not exist")
        return False
    print_success("Data directory exists")
    
    # Check questions.json
    questions_file = os.path.join(data_dir, 'questions.json')
    if not os.path.exists(questions_file):
        print_error("questions.json does not exist")
        return False
    
    import json
    try:
        with open(questions_file, 'r') as f:
            questions_data = json.load(f)
        
        if 'version' not in questions_data or 'questions' not in questions_data:
            print_error("questions.json has invalid structure")
            return False
        
        print_success(f"questions.json valid ({len(questions_data['questions'])} questions)")
    except json.JSONDecodeError:
        print_error("questions.json is not valid JSON")
        return False
    
    # Check inspections.json
    inspections_file = os.path.join(data_dir, 'inspections.json')
    if not os.path.exists(inspections_file):
        print_error("inspections.json does not exist")
        return False
    
    try:
        with open(inspections_file, 'r') as f:
            inspections_data = json.load(f)
        
        if 'version' not in inspections_data or 'submissions' not in inspections_data:
            print_error("inspections.json has invalid structure")
            return False
        
        print_success(f"inspections.json valid ({len(inspections_data['submissions'])} submissions)")
    except json.JSONDecodeError:
        print_error("inspections.json is not valid JSON")
        return False
    
    # Check uploads directory
    uploads_dir = os.path.join(os.path.dirname(__file__), 'static', 'uploads')
    if not os.path.exists(uploads_dir):
        print_error("Uploads directory does not exist")
        return False
    print_success("Uploads directory exists")
    
    return True

def verify_authentication_decorators():
    """Verify authentication decorators are in place"""
    print_section("6. Verifying Authentication & Authorization")
    
    from app import login_required, require_admin
    
    if login_required is None:
        print_error("login_required decorator not found")
        return False
    print_success("login_required decorator exists")
    
    if require_admin is None:
        print_error("require_admin decorator not found")
        return False
    print_success("require_admin decorator exists")
    
    return True

def verify_integration():
    """Verify end-to-end integration"""
    print_section("7. Verifying End-to-End Integration")
    
    from app import app, question_manager, inspection_service
    
    # Test question creation
    try:
        test_question = question_manager.create_question(
            text="Test integration question",
            photo_required=True,
            communities=["Community A"]
        )
        print_success("Question creation works")
        
        # Clean up test question
        question_manager.delete_question(test_question['id'])
        print_success("Question deletion works")
        
    except Exception as e:
        print_error(f"Question management failed: {e}")
        return False
    
    # Test inspection submission
    try:
        test_submission = inspection_service.create_submission(
            username="test_user",
            community="Community A",
            responses=[{
                'question_id': 'test_q_id',
                'question_text': 'Test question',
                'condition': 'Good',
                'description': 'Test description',
                'photo_path': None,
                'answered_at': '2024-01-01T00:00:00Z'
            }]
        )
        print_success("Inspection submission works")
        
    except Exception as e:
        print_error(f"Inspection submission failed: {e}")
        return False
    
    return True

def main():
    """Main verification function"""
    print(f"\n{BLUE}{'=' * 60}{RESET}")
    print(f"{BLUE}Task 18.1 Verification: Wire All Components Together{RESET}")
    print(f"{BLUE}{'=' * 60}{RESET}")
    
    results = []
    
    # 1. Verify imports
    success, services = verify_imports()
    results.append(("Imports", success))
    if not success:
        print_error("\nVerification failed at import stage")
        return False
    
    # 2. Verify services
    success = verify_services(services)
    results.append(("Services", success))
    
    # 3. Verify routes
    app = services[0]
    success = verify_routes(app)
    results.append(("Routes", success))
    
    # 4. Verify templates
    success = verify_templates()
    results.append(("Templates", success))
    
    # 5. Verify data structure
    success = verify_data_structure()
    results.append(("Data Structure", success))
    
    # 6. Verify authentication
    success = verify_authentication_decorators()
    results.append(("Authentication", success))
    
    # 7. Verify integration
    success = verify_integration()
    results.append(("Integration", success))
    
    # Print summary
    print_section("Verification Summary")
    
    all_passed = True
    for name, success in results:
        if success:
            print_success(f"{name}: PASSED")
        else:
            print_error(f"{name}: FAILED")
            all_passed = False
    
    print(f"\n{YELLOW}{'=' * 60}{RESET}")
    if all_passed:
        print(f"{GREEN}✓ ALL VERIFICATIONS PASSED{RESET}")
        print(f"{GREEN}✓ Task 18.1 Complete: All components wired together successfully{RESET}")
        print(f"{YELLOW}{'=' * 60}{RESET}\n")
        return True
    else:
        print(f"{RED}✗ SOME VERIFICATIONS FAILED{RESET}")
        print(f"{YELLOW}{'=' * 60}{RESET}\n")
        return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
