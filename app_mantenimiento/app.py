"""
Assisted Living Maintenance App - Backend Server
Flask application for managing maintenance and cleaning reports
With user authentication and automatic community detection
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from functools import wraps
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
import os
from datetime import datetime
import sqlite3
import json
from services.question_manager import QuestionManager
from services.inspection_service import InspectionService
from services.input_sanitizer import InputSanitizer

# Initialize Flask app
app = Flask(__name__)

# Configuration
app.config['SECRET_KEY'] = 'your-secret-key-change-this-in-production-12345'
app.config['SESSION_TYPE'] = 'filesystem'
app.config['PERMANENT_SESSION_LIFETIME'] = 86400  # 24 hours

# Configure upload folder
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Allowed file extensions for uploads
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif', 'webp'}

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ==================== SERVICE INITIALIZATION ====================

# Initialize data directory
DATA_FOLDER = os.path.join(os.path.dirname(__file__), 'data')
os.makedirs(DATA_FOLDER, exist_ok=True)

# Initialize QuestionManager service
QUESTIONS_FILE = os.path.join(DATA_FOLDER, 'questions.json')
question_manager = QuestionManager(QUESTIONS_FILE)

# Initialize InspectionService
INSPECTIONS_FILE = os.path.join(DATA_FOLDER, 'inspections.json')
from services.inspection_service import InspectionService
inspection_service = InspectionService(INSPECTIONS_FILE, UPLOAD_FOLDER)

# Initialize FileUploadHandler
from services.file_upload_handler import FileUploadHandler
file_upload_handler = FileUploadHandler(UPLOAD_FOLDER)


# ==================== DATABASE & USER MANAGEMENT ====================

# Sample user database - In production, use a real database
# Format: {username: {'password_hash': hash, 'community': 'Community Name'}}
USERS_DB = {
    'john': {
        'password': 'pass123',
        'community': 'Community A'
    },
    'maria': {
        'password': 'pass123',
        'community': 'Community B'
    },
    'carlos': {
        'password': 'pass123',
        'community': 'Community C'
    },
    'admin': {
        'password': 'admin123',
        'community': None  # Admin can see all communities
    }
}

# List of all available communities
ALL_COMMUNITIES = [
    f'Community {chr(65 + i)}' for i in range(38)  # Community A through Community AL (38 total)
]


def authenticate_user(username, password):
    """
    Authenticate user and return their community if successful
    Returns: (True, community_name) if successful, (False, None) if failed
    """
    if username in USERS_DB:
        user = USERS_DB[username]
        if user['password'] == password:  # In production, use password hash verification
            return (True, user['community'])
    return (False, None)


def login_required(f):
    """Decorator to require login for routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def require_admin(f):
    """
    Decorator to require admin role for routes
    Admin users have community set to None
    Non-admin users are redirected to the inspection form
    """
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        # Check if user is admin (community is None)
        if session.get('community') is not None:
            # Non-admin user, redirect to inspection form
            return redirect(url_for('report_form'))
        return f(*args, **kwargs)
    return decorated_function


# ==================== ROUTES ====================

@app.route('/login')
def login():
    """
    Display the login page
    """
    # If already logged in, redirect to report form
    if 'user' in session:
        return redirect(url_for('report_form'))
    return render_template('login.html')


@app.route('/api/login', methods=['POST'])
def api_login():
    """
    API endpoint for user authentication
    Expects JSON with username and password
    Returns user info and their assigned community
    
    Error Handling:
    - 400: JSON parsing errors or missing fields
    - 401: Invalid credentials
    - 500: Internal server errors
    """
    try:
        # Handle JSON parsing errors
        data = request.get_json(silent=True)
        
        if data is None:
            return jsonify({
                'status': 'error',
                'message': 'Invalid JSON format or Content-Type must be application/json'
            }), 400
        
        # Validate JSON structure
        if not InputSanitizer.validate_json_structure(data, dict):
            return jsonify({
                'status': 'error',
                'message': 'Request body must be a JSON object'
            }), 400
        
        # Sanitize and validate inputs
        username = InputSanitizer.sanitize_username(data.get('username', ''))
        password = data.get('password', '')
        
        if not username:
            return jsonify({
                'status': 'error',
                'message': 'Username is required'
            }), 400
        
        if not password:
            return jsonify({
                'status': 'error',
                'message': 'Password is required'
            }), 400

        # Authenticate user
        success, community = authenticate_user(username, password)

        if success:
            # Store user in session
            session['user'] = username
            session['community'] = community
            session.permanent = True

            return jsonify({
                'status': 'success',
                'message': 'Login successful',
                'username': username,
                'community': community
            }), 200
        else:
            return jsonify({
                'status': 'error',
                'message': 'Invalid username or password'
            }), 401

    except Exception as e:
        # Log the error for debugging
        app.logger.error(f'Login error: {str(e)}')
        return jsonify({
            'status': 'error',
            'message': 'Internal server error during login'
        }), 500


@app.route('/logout')
def logout():
    """
    Logout user and clear session
    """
    session.clear()
    return redirect(url_for('login'))


@app.route('/')
@login_required
def report_form():
    """
    Render the mobile report form (reporte.html)
    This page is designed for maintenance/cleaning staff using mobile devices
    User must be logged in and their community is automatically detected
    """
    communities = [session.get('community')] if session.get('community') else ALL_COMMUNITIES
    return render_template('reporte.html', 
                         community=session.get('community'),
                         communities=communities,
                         username=session.get('user'))


@app.route('/dashboard')
@login_required
def dashboard():
    """
    Render the admin dashboard (dashboard.html)
    This page is designed for managers to view reports from a desktop
    Admin users can see all communities
    """
    is_admin = session.get('community') is None
    return render_template('dashboard.html',
                         username=session.get('user'),
                         is_admin=is_admin,
                         community=session.get('community'))


@app.route('/api/submit-report', methods=['POST'])
@login_required
def submit_report():
    """
    API endpoint to receive report submissions from the mobile form
    Handles file upload with proper image processing and storage
    
    Error Handling:
    - 400: Missing required fields, invalid file types/sizes
    - 500: Internal server errors (file system, etc.)
    """
    try:
        # Get and sanitize form data
        community = InputSanitizer.sanitize_community_name(request.form.get('community', ''))
        location = InputSanitizer.sanitize_string(request.form.get('location', ''), max_length=200)
        condition = InputSanitizer.sanitize_string(request.form.get('condition', ''), max_length=50)
        description = InputSanitizer.sanitize_description(request.form.get('description', ''))
        username = InputSanitizer.sanitize_username(session.get('user', ''))

        # Validate required fields
        if not all([community, location, condition, description]):
            return jsonify({
                'status': 'error',
                'message': 'Missing required fields'
            }), 400

        # Handle file upload
        file_path = None
        if 'photo' in request.files:
            file = request.files['photo']
            if file and file.filename != '':
                # Validate file
                if not allowed_file(file.filename):
                    return jsonify({
                        'status': 'error',
                        'message': 'Invalid file type. Only images are allowed.'
                    }), 400

                try:
                    # Create secure filename with timestamp
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    file_ext = secure_filename(file.filename).rsplit('.', 1)[1].lower()
                    filename = f"{username}_{community}_{timestamp}.{file_ext}"
                    
                    # Create community folder if it doesn't exist
                    community_folder = os.path.join(app.config['UPLOAD_FOLDER'], 
                                                   secure_filename(community))
                    os.makedirs(community_folder, exist_ok=True)
                    
                    # Save file
                    file_path = os.path.join(community_folder, filename)
                    file.save(file_path)
                except IOError as e:
                    app.logger.error(f'File system error saving report photo: {str(e)}')
                    return jsonify({
                        'status': 'error',
                        'message': 'Internal server error: Failed to save photo'
                    }), 500

        # Create report record (in production, save to database)
        report = {
            'id': datetime.now().isoformat(),
            'username': username,
            'community': community,
            'location': location,
            'condition': condition,
            'description': description,
            'photo': file_path,
            'timestamp': datetime.now().isoformat()
        }

        # In production, save to database
        # For now, just return success
        return jsonify({
            'status': 'success',
            'message': 'Report submitted successfully',
            'report': report
        }), 200

    except Exception as e:
        app.logger.error(f'Unexpected error submitting report: {str(e)}')
        return jsonify({
            'status': 'error',
            'message': 'Internal server error while submitting report'
        }), 500


@app.route('/api/user-info')
@login_required
def get_user_info():
    """
    Get current user's information
    """
    return jsonify({
        'username': session.get('user'),
        'community': session.get('community'),
        'is_admin': session.get('community') is None
    }), 200


@app.route('/questions/manage')
@require_admin
def question_manager_ui():
    """
    Render the Question Manager UI (question_manager.html)
    This page is designed for admin users to create, edit, and manage inspection questions
    Requires admin authentication - non-admin users are redirected to inspection form
    
    Requirements: 1.1, 7.1
    """
    return render_template('question_manager.html',
                         username=session.get('user'),
                         communities=ALL_COMMUNITIES)


@app.route('/api/questions', methods=['GET'])
@login_required
def get_questions():
    """
    Get active questions with community filtering
    
    Query Parameters:
        community (optional): Filter questions by community name
        
    Behavior:
        - For staff users: Automatically filters by their assigned community
        - For admin users: Returns all active questions, or filters by community parameter if provided
        
    Returns:
        200: JSON with status and questions array
        500: Internal server error
    """
    try:
        # Sanitize community filter from query parameter
        community_filter = request.args.get('community')
        if community_filter:
            community_filter = InputSanitizer.sanitize_community_name(community_filter)
        
        # Check if user is admin
        user_community = session.get('community')
        is_admin = user_community is None
        
        # Determine which questions to return
        if is_admin:
            # Admin user
            if community_filter:
                # Admin requested specific community filter
                questions = question_manager.get_questions_for_community(community_filter)
            else:
                # Admin requested all questions
                questions = question_manager.get_all_active_questions()
        else:
            # Staff user - always filter by their assigned community
            questions = question_manager.get_questions_for_community(user_community)
        
        return jsonify({
            'status': 'success',
            'questions': questions
        }), 200
        
    except Exception as e:
        # Log the error for debugging
        app.logger.error(f'Error retrieving questions: {str(e)}')
        return jsonify({
            'status': 'error',
            'message': 'Internal server error while retrieving questions'
        }), 500


# ==================== QUESTION MANAGEMENT API ====================

@app.route('/api/questions', methods=['POST'])
@require_admin
def create_question():
    """
    API endpoint to create a new inspection question
    Requires admin authentication
    Expects JSON with text, photo_required, and communities array
    
    Error Handling:
    - 400: JSON parsing errors, validation errors, missing fields
    - 500: Internal server errors (file system, etc.)
    """
    try:
        # Handle JSON parsing errors
        data = request.get_json(silent=True)
        
        if data is None:
            return jsonify({
                'status': 'error',
                'message': 'Invalid JSON format or Content-Type must be application/json'
            }), 400
        
        # Validate JSON structure
        if not InputSanitizer.validate_json_structure(data, dict):
            return jsonify({
                'status': 'error',
                'message': 'Request body must be a JSON object'
            }), 400
        
        # Sanitize input data
        sanitized_data = InputSanitizer.sanitize_question_data(data)
        
        # Extract fields
        text = sanitized_data.get('text', '')
        photo_required = sanitized_data.get('photo_required', False)
        communities = sanitized_data.get('communities', [])
        
        # Validate text is non-empty
        if not text or not text.strip():
            return jsonify({
                'status': 'error',
                'message': 'Question text cannot be empty'
            }), 400
        
        # Validate communities array is non-empty
        if not communities or len(communities) == 0:
            return jsonify({
                'status': 'error',
                'message': 'At least one community must be selected'
            }), 400
        
        # Create question using QuestionManager
        question = question_manager.create_question(text, photo_required, communities)
        
        return jsonify({
            'status': 'success',
            'question': question
        }), 201
        
    except ValueError as e:
        # Validation errors from QuestionManager
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 400
    except IOError as e:
        # File system errors
        app.logger.error(f'File system error creating question: {str(e)}')
        return jsonify({
            'status': 'error',
            'message': 'Internal server error: Failed to save question'
        }), 500
    except Exception as e:
        # Unexpected errors
        app.logger.error(f'Unexpected error creating question: {str(e)}')
        return jsonify({
            'status': 'error',
            'message': 'Internal server error while creating question'
        }), 500


@app.route('/api/questions/<question_id>', methods=['PUT'])
@require_admin
def update_question(question_id):
    """
    API endpoint to update an existing inspection question
    Requires admin authentication
    Expects JSON with text, photo_required, and communities array
    
    Error Handling:
    - 400: JSON parsing errors, validation errors, missing fields
    - 404: Question not found
    - 500: Internal server errors (file system, etc.)
    """
    try:
        # Sanitize question_id
        question_id = InputSanitizer.sanitize_string(question_id, max_length=100)
        
        # Handle JSON parsing errors
        data = request.get_json(silent=True)
        
        if data is None:
            return jsonify({
                'status': 'error',
                'message': 'Invalid JSON format or Content-Type must be application/json'
            }), 400
        
        # Validate JSON structure
        if not InputSanitizer.validate_json_structure(data, dict):
            return jsonify({
                'status': 'error',
                'message': 'Request body must be a JSON object'
            }), 400
        
        # Sanitize input data
        sanitized_data = InputSanitizer.sanitize_question_data(data)
        
        # Extract fields
        text = sanitized_data.get('text', '')
        photo_required = sanitized_data.get('photo_required', False)
        communities = sanitized_data.get('communities', [])
        
        # Validate text is non-empty
        if not text or not text.strip():
            return jsonify({
                'status': 'error',
                'message': 'Question text cannot be empty'
            }), 400
        
        # Validate communities array is non-empty
        if not communities or len(communities) == 0:
            return jsonify({
                'status': 'error',
                'message': 'At least one community must be selected'
            }), 400
        
        # Update question using QuestionManager
        question = question_manager.update_question(question_id, text, photo_required, communities)
        
        # Check if question was found
        if question is None:
            return jsonify({
                'status': 'error',
                'message': 'Question not found'
            }), 404
        
        return jsonify({
            'status': 'success',
            'question': question
        }), 200
        
    except ValueError as e:
        # Validation errors from QuestionManager
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 400
    except IOError as e:
        # File system errors
        app.logger.error(f'File system error updating question: {str(e)}')
        return jsonify({
            'status': 'error',
            'message': 'Internal server error: Failed to save question'
        }), 500
    except Exception as e:
        # Unexpected errors
        app.logger.error(f'Unexpected error updating question: {str(e)}')
        return jsonify({
            'status': 'error',
            'message': 'Internal server error while updating question'
        }), 500


@app.route('/api/questions/<question_id>', methods=['DELETE'])
@require_admin
def delete_question(question_id):
    """
    API endpoint to delete an inspection question (soft delete)
    Requires admin authentication
    Performs soft delete by setting is_active to False
    
    Error Handling:
    - 404: Question not found
    - 500: Internal server errors (file system, etc.)
    """
    try:
        # Sanitize question_id
        question_id = InputSanitizer.sanitize_string(question_id, max_length=100)
        
        # Delete question using QuestionManager (soft delete)
        success = question_manager.delete_question(question_id)
        
        # Check if question was found
        if not success:
            return jsonify({
                'status': 'error',
                'message': 'Question not found'
            }), 404
        
        return jsonify({
            'status': 'success',
            'message': 'Question deleted successfully'
        }), 200
        
    except IOError as e:
        # File system errors
        app.logger.error(f'File system error deleting question: {str(e)}')
        return jsonify({
            'status': 'error',
            'message': 'Internal server error: Failed to save changes'
        }), 500
    except Exception as e:
        # Unexpected errors
        app.logger.error(f'Unexpected error deleting question: {str(e)}')
        return jsonify({
            'status': 'error',
            'message': 'Internal server error while deleting question'
        }), 500


# ==================== INSPECTION SUBMISSION API ====================

@app.route('/api/inspections', methods=['POST'])
@login_required
def submit_inspection():
    """
    API endpoint for inspection submission
    Requires authentication using @login_required decorator
    Accepts multipart/form-data with responses array
    Validates each response has question_id and condition
    Handles optional photo uploads for each response
    Saves photos using FileUploadHandler
    Creates submission using InspectionService
    Returns 201 with submission data on success
    Returns 400 with error message on validation failure
    
    Error Handling:
    - 400: JSON parsing errors, validation errors, missing fields, invalid file types/sizes
    - 500: Internal server errors (file system, etc.)
    
    Requirements: 3.1, 3.3, 4.1, 4.2, 4.3, 4.4, 5.1, 5.7, 5.8
    """
    try:
        # Get user info from session
        username = session.get('user')
        community = session.get('community')
        
        # Sanitize user info
        username = InputSanitizer.sanitize_username(username)
        if community:
            community = InputSanitizer.sanitize_community_name(community)
        
        # Validate user has a community (staff user)
        if not community:
            return jsonify({
                'status': 'error',
                'message': 'Admin users cannot submit inspections'
            }), 400
        
        # Parse responses from form data
        # Expected format: responses as JSON string in form data
        responses_json = request.form.get('responses')
        
        if not responses_json:
            return jsonify({
                'status': 'error',
                'message': 'No responses provided'
            }), 400
        
        # Parse JSON responses with error handling
        try:
            responses_data = json.loads(responses_json)
        except json.JSONDecodeError as e:
            return jsonify({
                'status': 'error',
                'message': f'Invalid JSON format for responses: {str(e)}'
            }), 400
        
        # Validate responses is a list
        if not InputSanitizer.validate_json_structure(responses_data, list):
            return jsonify({
                'status': 'error',
                'message': 'Responses must be an array'
            }), 400
        
        # Process each response
        processed_responses = []
        
        for idx, response in enumerate(responses_data):
            # Validate response is a dictionary
            if not isinstance(response, dict):
                return jsonify({
                    'status': 'error',
                    'message': f'Response {idx}: must be a JSON object'
                }), 400
            
            # Sanitize response data
            sanitized_response = InputSanitizer.sanitize_response_data(response)
            
            # Validate required fields: question_id and condition
            question_id = sanitized_response.get('question_id')
            condition = sanitized_response.get('condition')
            
            if not question_id:
                return jsonify({
                    'status': 'error',
                    'message': f'Response {idx}: question_id is required'
                }), 400
            
            if not condition:
                return jsonify({
                    'status': 'error',
                    'message': f'Response {idx}: condition is required'
                }), 400
            
            # Validate condition value
            if condition not in ['Good', 'Needs Attention']:
                return jsonify({
                    'status': 'error',
                    'message': f'Response {idx}: condition must be "Good" or "Needs Attention"'
                }), 400
            
            # Get optional fields
            question_text = sanitized_response.get('question_text', '')
            description = sanitized_response.get('description', '')
            
            # Handle optional photo upload
            photo_path = None
            photo_field_name = f'photo_{idx}'
            
            if photo_field_name in request.files:
                photo_file = request.files[photo_field_name]
                
                # Only process if file was actually uploaded
                if photo_file and photo_file.filename:
                    # Validate file using FileUploadHandler
                    is_valid, error_message = file_upload_handler.validate_file(photo_file)
                    
                    if not is_valid:
                        return jsonify({
                            'status': 'error',
                            'message': f'Response {idx}: {error_message}'
                        }), 400
                    
                    # Save photo using FileUploadHandler
                    try:
                        photo_path = file_upload_handler.save_file(photo_file, username, community)
                    except IOError as e:
                        app.logger.error(f'File system error saving photo: {str(e)}')
                        return jsonify({
                            'status': 'error',
                            'message': f'Response {idx}: Internal server error - Failed to save photo'
                        }), 500
                    except Exception as e:
                        app.logger.error(f'Unexpected error saving photo: {str(e)}')
                        return jsonify({
                            'status': 'error',
                            'message': f'Response {idx}: Failed to save photo'
                        }), 400
            
            # Create response object
            response_obj = {
                'question_id': question_id,
                'question_text': question_text,
                'condition': condition,
                'description': description,
                'photo_path': photo_path,
                'answered_at': datetime.now().isoformat()
            }
            
            processed_responses.append(response_obj)
        
        # Create submission using InspectionService
        try:
            submission = inspection_service.create_submission(
                username=username,
                community=community,
                responses=processed_responses
            )
        except ValueError as e:
            return jsonify({
                'status': 'error',
                'message': str(e)
            }), 400
        except IOError as e:
            app.logger.error(f'File system error creating submission: {str(e)}')
            return jsonify({
                'status': 'error',
                'message': 'Internal server error: Failed to save inspection'
            }), 500
        
        # Return success with submission data
        return jsonify({
            'status': 'success',
            'submission': submission
        }), 201
        
    except Exception as e:
        # Unexpected errors
        app.logger.error(f'Unexpected error submitting inspection: {str(e)}')
        return jsonify({
            'status': 'error',
            'message': 'Internal server error while submitting inspection'
        }), 500


@app.route('/api/inspections', methods=['GET'])
@login_required
def get_inspections():
    """
    Get inspection submissions with community filtering
    
    Query Parameters:
        community (optional): Filter submissions by community name (admin only)
        
    Behavior:
        - For staff users: Automatically filters by their assigned community
        - For admin users: Returns all submissions, or filters by community parameter if provided
        
    Returns:
        200: JSON with status and submissions array
        500: Internal server error
        
    Requirements: 9.1
    """
    try:
        # Sanitize community filter from query parameter
        community_filter = request.args.get('community')
        if community_filter:
            community_filter = InputSanitizer.sanitize_community_name(community_filter)
        
        # Check if user is admin
        user_community = session.get('community')
        is_admin = user_community is None
        
        # Determine which submissions to return
        if is_admin:
            # Admin user
            if community_filter:
                # Admin requested specific community filter
                submissions = inspection_service.get_submissions_by_community(community_filter)
            else:
                # Admin requested all submissions
                submissions = inspection_service.get_all_submissions()
        else:
            # Staff user - always filter by their assigned community
            submissions = inspection_service.get_submissions_by_community(user_community)
        
        return jsonify({
            'status': 'success',
            'submissions': submissions
        }), 200
        
    except Exception as e:
        # Log the error for debugging
        app.logger.error(f'Error retrieving inspections: {str(e)}')
        return jsonify({
            'status': 'error',
            'message': 'Internal server error while retrieving inspections'
        }), 500


# ==================== ERROR HANDLERS ====================

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return jsonify({'error': 'Not found'}), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    return jsonify({'error': 'Internal server error'}), 500


@app.errorhandler(401)
def unauthorized(error):
    """Handle 401 errors - redirect to login"""
    return redirect(url_for('login')), 401


# ==================== MAIN ====================

if __name__ == '__main__':
    # Run Flask development server
    # host='0.0.0.0' makes the app accessible from other machines
    # port=5001 (using 5001 instead of 5000 as 5000 may be in use by AirPlay Receiver)
    # debug=True enables auto-reloading and better error messages
    app.run(host='0.0.0.0', port=5001, debug=True)
