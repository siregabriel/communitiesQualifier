"""
Input Sanitization Service
Provides utilities for sanitizing user inputs and escaping HTML
"""

import html
import re
from typing import Any, Dict, List


class InputSanitizer:
    """
    Service for sanitizing user inputs and escaping HTML content.
    Prevents XSS attacks and ensures data integrity.
    """
    
    @staticmethod
    def sanitize_string(value: str, max_length: int = None) -> str:
        """
        Sanitize a string input by stripping whitespace and escaping HTML.
        
        Args:
            value: String to sanitize
            max_length: Optional maximum length to enforce
            
        Returns:
            Sanitized string with HTML escaped
        """
        if not isinstance(value, str):
            return ""
        
        # Strip leading/trailing whitespace
        sanitized = value.strip()
        
        # Escape HTML entities to prevent XSS
        sanitized = html.escape(sanitized)
        
        # Enforce maximum length if specified
        if max_length and len(sanitized) > max_length:
            sanitized = sanitized[:max_length]
        
        return sanitized
    
    @staticmethod
    def sanitize_question_text(text: str) -> str:
        """
        Sanitize question text with HTML escaping.
        
        Args:
            text: Question text to sanitize
            
        Returns:
            Sanitized question text
        """
        return InputSanitizer.sanitize_string(text, max_length=1000)
    
    @staticmethod
    def sanitize_description(description: str) -> str:
        """
        Sanitize description text with HTML escaping.
        
        Args:
            description: Description text to sanitize
            
        Returns:
            Sanitized description text
        """
        return InputSanitizer.sanitize_string(description, max_length=5000)
    
    @staticmethod
    def sanitize_community_name(community: str) -> str:
        """
        Sanitize community name.
        
        Args:
            community: Community name to sanitize
            
        Returns:
            Sanitized community name
        """
        return InputSanitizer.sanitize_string(community, max_length=100)
    
    @staticmethod
    def sanitize_username(username: str) -> str:
        """
        Sanitize username.
        
        Args:
            username: Username to sanitize
            
        Returns:
            Sanitized username
        """
        return InputSanitizer.sanitize_string(username, max_length=50)
    
    @staticmethod
    def sanitize_question_data(data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitize question creation/update data.
        
        Args:
            data: Dictionary containing question data
            
        Returns:
            Dictionary with sanitized values
        """
        sanitized = {}
        
        # Sanitize text field
        if 'text' in data:
            sanitized['text'] = InputSanitizer.sanitize_question_text(data['text'])
        
        # photo_required should be boolean
        if 'photo_required' in data:
            sanitized['photo_required'] = bool(data['photo_required'])
        
        # Sanitize communities array
        if 'communities' in data:
            if isinstance(data['communities'], list):
                sanitized['communities'] = [
                    InputSanitizer.sanitize_community_name(c) 
                    for c in data['communities'] 
                    if isinstance(c, str)
                ]
            else:
                sanitized['communities'] = []
        
        return sanitized
    
    @staticmethod
    def sanitize_response_data(response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitize inspection response data.
        
        Args:
            response: Dictionary containing response data
            
        Returns:
            Dictionary with sanitized values
        """
        sanitized = {}
        
        # Sanitize question_id (alphanumeric with underscores only)
        if 'question_id' in response:
            question_id = str(response['question_id'])
            # Only allow alphanumeric and underscores
            sanitized['question_id'] = re.sub(r'[^a-zA-Z0-9_]', '', question_id)
        
        # Sanitize question_text
        if 'question_text' in response:
            sanitized['question_text'] = InputSanitizer.sanitize_question_text(
                response['question_text']
            )
        
        # Sanitize condition (must be exact match)
        if 'condition' in response:
            condition = str(response['condition']).strip()
            if condition in ['Good', 'Needs Attention']:
                sanitized['condition'] = condition
            else:
                sanitized['condition'] = ''
        
        # Sanitize description
        if 'description' in response:
            sanitized['description'] = InputSanitizer.sanitize_description(
                response['description']
            )
        
        # photo_path should be validated separately during file upload
        if 'photo_path' in response:
            sanitized['photo_path'] = response['photo_path']
        
        # answered_at should be ISO format timestamp
        if 'answered_at' in response:
            sanitized['answered_at'] = response['answered_at']
        
        return sanitized
    
    @staticmethod
    def validate_json_structure(data: Any, expected_type: type) -> bool:
        """
        Validate that parsed JSON has expected structure.
        
        Args:
            data: Parsed JSON data
            expected_type: Expected Python type (dict, list, etc.)
            
        Returns:
            True if structure matches, False otherwise
        """
        return isinstance(data, expected_type)
