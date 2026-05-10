"""
Inspection Service Module

Handles inspection submission management, response validation,
photo file management, and submission persistence.
"""

import os
import json
import time
import random
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from werkzeug.utils import secure_filename


# Allowed file extensions for photo uploads
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif', 'webp'}

# Maximum file size in bytes (16MB)
MAX_FILE_SIZE = 16 * 1024 * 1024


class InspectionService:
    """
    Service class for managing inspection submissions.
    
    Responsibilities:
    - Inspection submission handling
    - Response validation
    - Photo file management
    - Submission persistence
    """
    
    def __init__(self, storage_path: str, upload_path: str):
        """
        Initialize InspectionService with storage and upload paths.
        
        Args:
            storage_path: Path to inspections.json file
            upload_path: Path to uploads folder for photos
        """
        self.storage_path = storage_path
        self.upload_path = upload_path
        self.submissions = []
        
        # Ensure upload directory exists
        os.makedirs(upload_path, exist_ok=True)
        
        # Load existing submissions if file exists
        self.load_from_file()
    
    def create_submission(self, username: str, community: str, 
                         responses: List[Dict]) -> Dict:
        """
        Create new inspection submission.
        
        Args:
            username: Staff member username
            community: Community name
            responses: List of response dictionaries
            
        Returns:
            InspectionSubmission dictionary
            
        Raises:
            ValueError: If validation fails
        """
        # Validate inputs
        if not username or not username.strip():
            raise ValueError("Username cannot be empty")
        if not community or not community.strip():
            raise ValueError("Community cannot be empty")
        
        # Filter and validate responses (only store answered questions)
        validated_responses = []
        for response in responses:
            # Skip empty responses (unanswered questions)
            if not response.get('question_id') or not response.get('condition'):
                continue
                
            # Validate response
            if not self.validate_response(response):
                raise ValueError(f"Invalid response data for question {response.get('question_id')}")
            
            validated_responses.append(response)
        
        # Generate unique submission ID
        submission_id = f"insp_{int(time.time() * 1000)}_{random.randint(1000, 9999)}"
        
        # Create submission object
        submission = {
            'id': submission_id,
            'username': username.strip(),
            'community': community.strip(),
            'submitted_at': datetime.now().isoformat(),
            'responses': validated_responses
        }
        
        # Add to submissions list
        self.submissions.append(submission)
        
        # Persist to file
        self.save_to_file()
        
        return submission
    
    def validate_response(self, response: Dict) -> bool:
        """
        Validate individual response data.
        
        Args:
            response: Response dictionary to validate
            
        Returns:
            True if valid, False otherwise
        """
        # Check required fields
        if 'question_id' not in response or not response['question_id']:
            return False
        
        if 'condition' not in response:
            return False
        
        # Validate condition value
        valid_conditions = ['Good', 'Needs Attention']
        if response['condition'] not in valid_conditions:
            return False
        
        # question_text is required
        if 'question_text' not in response:
            return False
        
        # description can be empty but must exist
        if 'description' not in response:
            return False
        
        # photo_path can be null or a string
        if 'photo_path' in response and response['photo_path'] is not None:
            if not isinstance(response['photo_path'], str):
                return False
        
        # answered_at must be present
        if 'answered_at' not in response:
            return False
        
        return True
    
    def save_photo(self, file, username: str, community: str) -> str:
        """
        Save uploaded photo and return relative path.
        
        Args:
            file: File object from request.files
            username: Staff member username
            community: Community name
            
        Returns:
            Relative path to saved photo
            
        Raises:
            ValueError: If file validation fails
        """
        # Validate file exists
        if not file or not file.filename:
            raise ValueError("No file provided")
        
        # Validate file extension
        if not self._allowed_file(file.filename):
            raise ValueError(
                f"Invalid file type. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"
            )
        
        # Validate file size
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)  # Reset file pointer
        
        if file_size > MAX_FILE_SIZE:
            raise ValueError(f"File size exceeds maximum of {MAX_FILE_SIZE / (1024 * 1024)}MB")
        
        # Generate filename: {username}_{community}_{timestamp}.{ext}
        timestamp = int(time.time() * 1000)
        file_ext = secure_filename(file.filename).rsplit('.', 1)[1].lower()
        filename = f"{username}_{community}_{timestamp}.{file_ext}"
        
        # Create community folder
        community_folder = os.path.join(
            self.upload_path, 
            secure_filename(community)
        )
        os.makedirs(community_folder, exist_ok=True)
        
        # Save file
        file_path = os.path.join(community_folder, filename)
        file.save(file_path)
        
        # Return relative path from uploads directory
        relative_path = os.path.join(
            'uploads',
            secure_filename(community),
            filename
        )
        
        return relative_path
    
    def get_submissions_by_community(self, community: str) -> List[Dict]:
        """
        Retrieve submissions for specific community.
        
        Args:
            community: Community name to filter by
            
        Returns:
            List of InspectionSubmission dictionaries
        """
        return [
            submission for submission in self.submissions
            if submission['community'] == community
        ]
    
    def get_all_submissions(self) -> List[Dict]:
        """
        Retrieve all submissions (admin only).
        
        Returns:
            List of all InspectionSubmission dictionaries
        """
        return self.submissions.copy()
    
    def save_to_file(self) -> None:
        """
        Persist submissions to JSON file.
        
        Raises:
            IOError: If file write fails
        """
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
            
            # Create submissions collection structure
            data = {
                'version': '1.0',
                'last_modified': datetime.now().isoformat(),
                'submissions': self.submissions
            }
            
            # Write to file with pretty formatting
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            raise IOError(f"Failed to save submissions to file: {str(e)}")
    
    def load_from_file(self) -> None:
        """
        Load submissions from JSON file with error handling.
        
        If file doesn't exist or is malformed, initializes with empty state.
        """
        try:
            if os.path.exists(self.storage_path):
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                # Validate structure
                if isinstance(data, dict) and 'submissions' in data:
                    self.submissions = data['submissions']
                else:
                    # Malformed data, initialize empty
                    self.submissions = []
            else:
                # File doesn't exist, initialize empty
                self.submissions = []
                
        except json.JSONDecodeError:
            # Malformed JSON, initialize empty
            self.submissions = []
        except Exception as e:
            # Other errors, initialize empty
            self.submissions = []
    
    def _allowed_file(self, filename: str) -> bool:
        """
        Check if file extension is allowed.
        
        Args:
            filename: Name of file to check
            
        Returns:
            True if extension is allowed, False otherwise
        """
        return '.' in filename and \
               filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
