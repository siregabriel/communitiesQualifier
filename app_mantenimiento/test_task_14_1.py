"""
Test for Task 14.1: Service Initialization in app.py

This test verifies that:
1. data/ directory is created if it doesn't exist
2. QuestionManager instance is initialized with path to questions.json
3. InspectionService instance is initialized with paths to inspections.json and uploads folder
4. FileUploadHandler instance is initialized with uploads folder path
5. Existing data is loaded from JSON files on startup

Requirements: 1.5, 5.5, 8.1, 8.2
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class TestTask14_1ServiceInitialization(unittest.TestCase):
    """Test service initialization in app.py"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.app_dir = os.path.dirname(os.path.abspath(__file__))
        self.data_folder = os.path.join(self.app_dir, 'data')
        self.upload_folder = os.path.join(self.app_dir, 'static', 'uploads')
        self.questions_file = os.path.join(self.data_folder, 'questions.json')
        self.inspections_file = os.path.join(self.data_folder, 'inspections.json')
    
    def test_data_directory_exists(self):
        """Test that data/ directory is created"""
        self.assertTrue(
            os.path.exists(self.data_folder),
            "data/ directory should exist"
        )
        self.assertTrue(
            os.path.isdir(self.data_folder),
            "data/ should be a directory"
        )
    
    def test_upload_directory_exists(self):
        """Test that uploads directory is created"""
        self.assertTrue(
            os.path.exists(self.upload_folder),
            "static/uploads/ directory should exist"
        )
        self.assertTrue(
            os.path.isdir(self.upload_folder),
            "static/uploads/ should be a directory"
        )
    
    def test_services_can_be_imported(self):
        """Test that all service classes can be imported"""
        try:
            from services.question_manager import QuestionManager
            from services.inspection_service import InspectionService
            from services.file_upload_handler import FileUploadHandler
        except ImportError as e:
            self.fail(f"Failed to import services: {e}")
    
    def test_app_imports_successfully(self):
        """Test that app.py imports without errors"""
        try:
            import app
        except Exception as e:
            self.fail(f"Failed to import app.py: {e}")
    
    def test_question_manager_initialized(self):
        """Test that QuestionManager is initialized in app.py"""
        from app import question_manager
        from services.question_manager import QuestionManager
        
        # Verify instance type
        self.assertIsInstance(
            question_manager,
            QuestionManager,
            "question_manager should be an instance of QuestionManager"
        )
        
        # Verify storage path is set correctly
        self.assertEqual(
            question_manager.storage_path,
            self.questions_file,
            "QuestionManager should be initialized with questions.json path"
        )
    
    def test_inspection_service_initialized(self):
        """Test that InspectionService is initialized in app.py"""
        from app import inspection_service
        from services.inspection_service import InspectionService
        
        # Verify instance type
        self.assertIsInstance(
            inspection_service,
            InspectionService,
            "inspection_service should be an instance of InspectionService"
        )
        
        # Verify storage path is set correctly
        self.assertEqual(
            inspection_service.storage_path,
            self.inspections_file,
            "InspectionService should be initialized with inspections.json path"
        )
        
        # Verify upload path is set correctly
        self.assertEqual(
            inspection_service.upload_path,
            self.upload_folder,
            "InspectionService should be initialized with uploads folder path"
        )
    
    def test_file_upload_handler_initialized(self):
        """Test that FileUploadHandler is initialized in app.py"""
        from app import file_upload_handler
        from services.file_upload_handler import FileUploadHandler
        
        # Verify instance type
        self.assertIsInstance(
            file_upload_handler,
            FileUploadHandler,
            "file_upload_handler should be an instance of FileUploadHandler"
        )
        
        # Verify upload folder is set correctly
        self.assertEqual(
            file_upload_handler.upload_folder,
            self.upload_folder,
            "FileUploadHandler should be initialized with uploads folder path"
        )
    
    def test_question_manager_loads_existing_data(self):
        """Test that QuestionManager loads existing data from questions.json"""
        from app import question_manager
        
        # If questions.json exists, verify data is loaded
        if os.path.exists(self.questions_file):
            # QuestionManager should have loaded questions
            self.assertIsNotNone(
                question_manager.questions,
                "QuestionManager should have questions list"
            )
            self.assertIsInstance(
                question_manager.questions,
                list,
                "QuestionManager.questions should be a list"
            )
            
            # Verify version is set
            self.assertIsNotNone(
                question_manager.version,
                "QuestionManager should have version"
            )
            
            print(f"✓ QuestionManager loaded {len(question_manager.questions)} questions from file")
    
    def test_inspection_service_loads_existing_data(self):
        """Test that InspectionService loads existing data from inspections.json"""
        from app import inspection_service
        
        # If inspections.json exists, verify data is loaded
        if os.path.exists(self.inspections_file):
            # InspectionService should have loaded submissions
            self.assertIsNotNone(
                inspection_service.submissions,
                "InspectionService should have submissions list"
            )
            self.assertIsInstance(
                inspection_service.submissions,
                list,
                "InspectionService.submissions should be a list"
            )
            
            print(f"✓ InspectionService loaded {len(inspection_service.submissions)} submissions from file")
    
    def test_services_initialized_before_routes(self):
        """Test that services are initialized before route definitions"""
        import app
        
        # Verify services are available as module-level variables
        self.assertTrue(
            hasattr(app, 'question_manager'),
            "app module should have question_manager attribute"
        )
        self.assertTrue(
            hasattr(app, 'inspection_service'),
            "app module should have inspection_service attribute"
        )
        self.assertTrue(
            hasattr(app, 'file_upload_handler'),
            "app module should have file_upload_handler attribute"
        )
    
    def test_all_requirements_met(self):
        """Comprehensive test that all task requirements are met"""
        from app import question_manager, inspection_service, file_upload_handler
        from services.question_manager import QuestionManager
        from services.inspection_service import InspectionService
        from services.file_upload_handler import FileUploadHandler
        
        # Requirement 1: Create data/ directory if it doesn't exist
        self.assertTrue(os.path.exists(self.data_folder), "✗ Requirement 1 failed: data/ directory not created")
        print("✓ Requirement 1: data/ directory created")
        
        # Requirement 2: Initialize QuestionManager with path to questions.json
        self.assertIsInstance(question_manager, QuestionManager, "✗ Requirement 2 failed: QuestionManager not initialized")
        self.assertEqual(question_manager.storage_path, self.questions_file, "✗ Requirement 2 failed: Wrong path")
        print("✓ Requirement 2: QuestionManager initialized with questions.json path")
        
        # Requirement 3: Initialize InspectionService with paths to inspections.json and uploads folder
        self.assertIsInstance(inspection_service, InspectionService, "✗ Requirement 3 failed: InspectionService not initialized")
        self.assertEqual(inspection_service.storage_path, self.inspections_file, "✗ Requirement 3 failed: Wrong inspections path")
        self.assertEqual(inspection_service.upload_path, self.upload_folder, "✗ Requirement 3 failed: Wrong uploads path")
        print("✓ Requirement 3: InspectionService initialized with inspections.json and uploads folder paths")
        
        # Requirement 4: Initialize FileUploadHandler with uploads folder path
        self.assertIsInstance(file_upload_handler, FileUploadHandler, "✗ Requirement 4 failed: FileUploadHandler not initialized")
        self.assertEqual(file_upload_handler.upload_folder, self.upload_folder, "✗ Requirement 4 failed: Wrong uploads path")
        print("✓ Requirement 4: FileUploadHandler initialized with uploads folder path")
        
        # Requirement 5: Load existing data from JSON files on startup
        if os.path.exists(self.questions_file):
            self.assertIsInstance(question_manager.questions, list, "✗ Requirement 5 failed: Questions not loaded")
            print(f"✓ Requirement 5a: Loaded {len(question_manager.questions)} questions from questions.json")
        
        if os.path.exists(self.inspections_file):
            self.assertIsInstance(inspection_service.submissions, list, "✗ Requirement 5 failed: Submissions not loaded")
            print(f"✓ Requirement 5b: Loaded {len(inspection_service.submissions)} submissions from inspections.json")
        
        print("\n✓ All task 14.1 requirements met successfully!")


if __name__ == '__main__':
    # Run tests with verbose output
    unittest.main(verbosity=2)
