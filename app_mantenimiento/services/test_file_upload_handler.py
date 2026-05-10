"""
Unit tests for FileUploadHandler
Tests file validation, secure filename generation, and community folder creation
"""

import unittest
import os
import tempfile
import shutil
from io import BytesIO
from werkzeug.datastructures import FileStorage
from services.file_upload_handler import FileUploadHandler


class TestFileUploadHandler(unittest.TestCase):
    """Test cases for FileUploadHandler class"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Create a temporary directory for uploads
        self.test_upload_dir = tempfile.mkdtemp()
        self.handler = FileUploadHandler(self.test_upload_dir)
    
    def tearDown(self):
        """Clean up test fixtures"""
        # Remove the temporary directory
        if os.path.exists(self.test_upload_dir):
            shutil.rmtree(self.test_upload_dir)
    
    def test_validate_file_valid_jpg(self):
        """Test validation of valid JPG file"""
        # Create a mock file
        file_data = BytesIO(b"fake image data")
        file = FileStorage(
            stream=file_data,
            filename="test.jpg",
            content_type="image/jpeg"
        )
        
        valid, error_msg = self.handler.validate_file(file)
        
        self.assertTrue(valid)
        self.assertEqual(error_msg, "")
    
    def test_validate_file_valid_png(self):
        """Test validation of valid PNG file"""
        file_data = BytesIO(b"fake image data")
        file = FileStorage(
            stream=file_data,
            filename="test.png",
            content_type="image/png"
        )
        
        valid, error_msg = self.handler.validate_file(file)
        
        self.assertTrue(valid)
        self.assertEqual(error_msg, "")
    
    def test_validate_file_invalid_extension(self):
        """Test validation rejects invalid file extensions"""
        file_data = BytesIO(b"fake file data")
        file = FileStorage(
            stream=file_data,
            filename="test.txt",
            content_type="text/plain"
        )
        
        valid, error_msg = self.handler.validate_file(file)
        
        self.assertFalse(valid)
        self.assertIn("Invalid file type", error_msg)
    
    def test_validate_file_no_file(self):
        """Test validation rejects missing file"""
        valid, error_msg = self.handler.validate_file(None)
        
        self.assertFalse(valid)
        self.assertIn("No file provided", error_msg)
    
    def test_validate_file_empty_filename(self):
        """Test validation rejects empty filename"""
        file_data = BytesIO(b"fake image data")
        file = FileStorage(
            stream=file_data,
            filename="",
            content_type="image/jpeg"
        )
        
        valid, error_msg = self.handler.validate_file(file)
        
        self.assertFalse(valid)
        self.assertIn("No file provided", error_msg)
    
    def test_validate_file_exceeds_size_limit(self):
        """Test validation rejects files exceeding size limit"""
        # Create a file larger than 16MB
        large_data = b"x" * (17 * 1024 * 1024)  # 17MB
        file_data = BytesIO(large_data)
        file = FileStorage(
            stream=file_data,
            filename="large.jpg",
            content_type="image/jpeg"
        )
        
        valid, error_msg = self.handler.validate_file(file)
        
        self.assertFalse(valid)
        self.assertIn("exceeds maximum allowed size", error_msg)
    
    def test_ensure_community_folder_creates_folder(self):
        """Test community folder creation"""
        community = "Community A"
        
        folder_path = self.handler.ensure_community_folder(community)
        
        self.assertTrue(os.path.exists(folder_path))
        self.assertTrue(os.path.isdir(folder_path))
    
    def test_ensure_community_folder_sanitizes_name(self):
        """Test community folder name sanitization"""
        community = "Community A/B"  # Contains invalid path character
        
        folder_path = self.handler.ensure_community_folder(community)
        
        # Should sanitize the name
        self.assertTrue(os.path.exists(folder_path))
        self.assertNotIn("/", os.path.basename(folder_path))
    
    def test_ensure_community_folder_idempotent(self):
        """Test community folder creation is idempotent"""
        community = "Community A"
        
        # Create folder twice
        folder_path1 = self.handler.ensure_community_folder(community)
        folder_path2 = self.handler.ensure_community_folder(community)
        
        # Should return same path and not raise error
        self.assertEqual(folder_path1, folder_path2)
        self.assertTrue(os.path.exists(folder_path1))
    
    def test_save_file_creates_file(self):
        """Test file saving creates file with correct name"""
        file_data = BytesIO(b"fake image data")
        file = FileStorage(
            stream=file_data,
            filename="test.jpg",
            content_type="image/jpeg"
        )
        
        username = "john"
        community = "Community A"
        
        relative_path = self.handler.save_file(file, username, community)
        
        # Check relative path format
        self.assertIn(username, relative_path)
        self.assertIn(community.replace(" ", "_"), relative_path)
        self.assertTrue(relative_path.endswith(".jpg"))
        
        # Check file exists
        full_path = os.path.join(self.test_upload_dir, relative_path)
        self.assertTrue(os.path.exists(full_path))
    
    def test_save_file_filename_format(self):
        """Test saved file follows naming convention"""
        file_data = BytesIO(b"fake image data")
        file = FileStorage(
            stream=file_data,
            filename="test.jpg",
            content_type="image/jpeg"
        )
        
        username = "john"
        community = "Community A"
        
        relative_path = self.handler.save_file(file, username, community)
        filename = os.path.basename(relative_path)
        
        # Should match format: username_community_timestamp.ext
        # The filename uses raw community name (with spaces)
        self.assertIn(username, filename)
        self.assertIn(community, filename)
        # Should have timestamp (numeric) before extension
        name_without_ext = filename.rsplit('.', 1)[0]
        timestamp_part = name_without_ext.split('_')[-1]
        self.assertTrue(timestamp_part.isdigit(), f"Expected timestamp to be numeric, got: {timestamp_part}")
    
    def test_allowed_file_valid_extensions(self):
        """Test all allowed extensions are accepted"""
        allowed_extensions = ['jpg', 'jpeg', 'png', 'gif', 'webp']
        
        for ext in allowed_extensions:
            filename = f"test.{ext}"
            self.assertTrue(
                self.handler._allowed_file(filename),
                f"Extension {ext} should be allowed"
            )
    
    def test_allowed_file_case_insensitive(self):
        """Test file extension check is case insensitive"""
        self.assertTrue(self.handler._allowed_file("test.JPG"))
        self.assertTrue(self.handler._allowed_file("test.Png"))
        self.assertTrue(self.handler._allowed_file("test.JPEG"))
    
    def test_allowed_file_invalid_extension(self):
        """Test invalid extensions are rejected"""
        invalid_files = ["test.txt", "test.pdf", "test.exe", "test.doc"]
        
        for filename in invalid_files:
            self.assertFalse(
                self.handler._allowed_file(filename),
                f"File {filename} should not be allowed"
            )
    
    def test_allowed_file_no_extension(self):
        """Test files without extension are rejected"""
        self.assertFalse(self.handler._allowed_file("test"))
        self.assertFalse(self.handler._allowed_file("testjpg"))


if __name__ == '__main__':
    unittest.main()
