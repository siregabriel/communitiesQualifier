"""
File Upload Handler Service
Handles file validation, secure filename generation, and file storage
"""

import os
from datetime import datetime
from werkzeug.utils import secure_filename
from typing import Tuple


class FileUploadHandler:
    """
    Handles file upload operations including validation, secure filename generation,
    and community-based folder organization.
    """
    
    # Allowed file extensions for uploads
    ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif', 'webp'}
    
    # Maximum file size in bytes (16MB)
    MAX_FILE_SIZE = 16 * 1024 * 1024
    
    def __init__(self, upload_folder: str):
        """
        Initialize the FileUploadHandler with the base upload folder path.
        
        Args:
            upload_folder: Base path for file uploads
        """
        self.upload_folder = upload_folder
        
    def validate_file(self, file) -> Tuple[bool, str]:
        """
        Validate file type and size.
        
        Args:
            file: FileStorage object from Flask request
            
        Returns:
            Tuple of (valid: bool, error_message: str)
            If valid is True, error_message will be empty string
            If valid is False, error_message contains the validation error
        """
        # Check if file exists
        if not file or file.filename == '':
            return (False, "No file provided")
        
        # Check file extension
        if not self._allowed_file(file.filename):
            allowed_exts = ', '.join(self.ALLOWED_EXTENSIONS)
            return (False, f"Invalid file type. Allowed types: {allowed_exts}")
        
        # Check file size
        # Seek to end to get file size
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)  # Reset to beginning
        
        if file_size > self.MAX_FILE_SIZE:
            max_size_mb = self.MAX_FILE_SIZE / (1024 * 1024)
            return (False, f"File size exceeds maximum allowed size of {max_size_mb}MB")
        
        return (True, "")
    
    def save_file(self, file, username: str, community: str) -> str:
        """
        Save file with secure filename generation and return relative path.
        
        Args:
            file: FileStorage object from Flask request
            username: Username of the person uploading the file
            community: Community name for folder organization
            
        Returns:
            Relative path to the saved file (e.g., "uploads/Community_A/john_Community_A_1705317600.jpg")
            
        Raises:
            IOError: If file cannot be saved to disk
        """
        try:
            # Ensure community folder exists
            community_folder_path = self.ensure_community_folder(community)
            
            # Generate secure filename
            timestamp = int(datetime.now().timestamp())
            file_ext = secure_filename(file.filename).rsplit('.', 1)[1].lower()
            filename = f"{username}_{community}_{timestamp}.{file_ext}"
            
            # Full path for saving
            full_path = os.path.join(community_folder_path, filename)
            
            # Save the file
            file.save(full_path)
            
            # Return relative path from upload folder
            relative_path = os.path.join(
                secure_filename(community),
                filename
            )
            
            return relative_path
        except (OSError, IOError) as e:
            raise IOError(f"Failed to save file: {str(e)}")
    
    def ensure_community_folder(self, community: str) -> str:
        """
        Create community folder if it doesn't exist.
        
        Args:
            community: Community name
            
        Returns:
            Full path to the community folder
            
        Raises:
            IOError: If folder cannot be created
        """
        try:
            # Sanitize community name for filesystem
            safe_community_name = secure_filename(community)
            community_folder_path = os.path.join(self.upload_folder, safe_community_name)
            
            # Create folder if it doesn't exist
            os.makedirs(community_folder_path, exist_ok=True)
            
            return community_folder_path
        except (OSError, IOError) as e:
            raise IOError(f"Failed to create community folder: {str(e)}")
    
    def _allowed_file(self, filename: str) -> bool:
        """
        Check if file extension is allowed.
        
        Args:
            filename: Name of the file
            
        Returns:
            True if file extension is allowed, False otherwise
        """
        return '.' in filename and \
               filename.rsplit('.', 1)[1].lower() in self.ALLOWED_EXTENSIONS
