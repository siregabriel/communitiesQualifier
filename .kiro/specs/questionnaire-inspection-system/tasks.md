# Implementation Plan: Questionnaire-Based Inspection System

## Overview

This implementation plan transforms the existing maintenance report system into a questionnaire-based inspection system with community-specific question assignment. The system will enable administrators to create and manage inspection questions through a web interface, assigning them to specific communities. Staff members will see only questions assigned to their community when completing inspections. The implementation maintains the existing Flask architecture, session-based authentication, and file-based storage while introducing new data models, services, and UI components.

## Tasks

- [x] 1. Set up data structures and storage foundation
  - Create `data/` directory in `app_mantenimiento/`
  - Initialize `questions.json` with empty Question Bank structure (version, last_modified, questions array)
  - Initialize `inspections.json` with empty Inspection Submissions structure (version, last_modified, submissions array)
  - Verify existing `uploads/` directory structure
  - _Requirements: 1.5, 5.5, 8.1, 8.2, 8.3_

- [x] 2. Implement Question Manager Service with community assignment
  - [x] 2.1 Create `QuestionManager` class in new `services/question_manager.py` file
    - Implement `__init__` method with storage path parameter
    - Implement `create_question` method with text, photo_required, and communities array parameters, generating unique ID using timestamp and random number
    - Implement `get_question` method to retrieve question by ID
    - Implement `get_all_active_questions` method to retrieve only active questions
    - Implement `get_questions_for_community` method to filter questions by community membership
    - Implement `update_question` method preserving ID and created_at timestamp, allowing community assignment updates
    - Implement `delete_question` method for soft delete (set is_active to False)
    - Implement `save_to_file` method for JSON persistence
    - Implement `load_from_file` method for JSON loading with error handling
    - Use ISO 8601 timestamps for all datetime fields
    - Validate question text is non-empty after stripping whitespace
    - Validate communities array is non-empty (empty array = inactive question)
    - _Requirements: 1.2, 1.3, 1.4, 1.5, 1.8, 2.1, 2.2, 2.3, 2.5, 2.8_

  - [ ]* 2.2 Write property test for Question Manager Service
    - **Property 2: Question Creation Persistence** (includes community assignment validation)
    - **Property 3: Question Edit Invariants** (includes community assignment updates)
    - **Property 4: Soft Delete Preservation**
    - **Property 5: Question Bank Serialization Round-Trip**
    - **Property 7: Question ID Uniqueness**
    - **Property 9: Community Assignment Validation**
    - **Validates: Requirements 1.2, 1.3, 1.4, 1.5, 1.8, 2.1, 2.2, 2.5, 2.8**

- [x] 3. Implement Inspection Service
  - [x] 3.1 Create `InspectionService` class in new `services/inspection_service.py` file
    - Implement `__init__` method with storage path and upload path parameters
    - Implement `create_submission` method accepting username, community, and responses list
    - Implement `validate_response` method checking condition values and required fields
    - Implement `save_photo` method with filename format: `{username}_{community}_{timestamp}.{ext}`
    - Implement `get_submissions_by_community` method for filtering by community
    - Implement `get_all_submissions` method for admin access
    - Implement `save_to_file` method for JSON persistence
    - Implement `load_from_file` method for JSON loading with error handling
    - Create community-specific folders in uploads directory
    - Validate file extensions against ALLOWED_EXTENSIONS
    - Validate file size does not exceed 16MB
    - Store only answered questions (skip empty responses)
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_

  - [ ]* 3.2 Write property test for Inspection Service
    - **Property 11: Partial Submission Acceptance**
    - **Property 15: Submission Response Completeness**
    - **Property 16: Photo Organization by Community**
    - **Property 17: Photo Filename Format and Uniqueness**
    - **Property 18: Inspection Submission Serialization Round-Trip**
    - **Validates: Requirements 3.1, 3.3, 5.1, 5.2, 5.3, 5.4, 5.5, 5.6**

- [x] 4. Implement File Upload Handler
  - [x] 4.1 Create `FileUploadHandler` class in new `services/file_upload_handler.py` file
    - Implement `__init__` method with upload folder path parameter
    - Implement `validate_file` method returning (valid, error_message) tuple
    - Implement `save_file` method with secure filename generation
    - Implement `ensure_community_folder` method creating folders with `os.makedirs(exist_ok=True)`
    - Use `werkzeug.utils.secure_filename()` for sanitization
    - Check file extension against ALLOWED_EXTENSIONS
    - Check file size before saving
    - _Requirements: 4.6, 4.7_

  - [ ]* 4.2 Write unit tests for File Upload Handler
    - Test file validation with valid and invalid file types
    - Test file size validation
    - Test secure filename generation
    - Test community folder creation
    - _Requirements: 4.6, 4.7_

- [x] 5. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Add authentication and authorization decorators
  - [x] 6.1 Create `require_admin` decorator in `app.py`
    - Check if user's community is None (admin indicator)
    - Redirect non-admin users to inspection form
    - Reuse existing `login_required` decorator
    - _Requirements: 1.1, 7.1, 7.2, 7.3_

  - [ ]* 6.2 Write unit tests for authentication decorators
    - Test admin access with admin user
    - Test admin access denial with staff user
    - Test redirect behavior
    - _Requirements: 1.1, 7.1, 7.2_

- [x] 7. Implement Question Management API endpoints with community assignment
  - [x] 7.1 Add POST `/api/questions` endpoint for question creation
    - Require admin authentication using `@require_admin` decorator
    - Accept JSON with text, photo_required, and communities array fields
    - Validate text is non-empty
    - Validate communities array is non-empty (return 400 with "At least one community must be selected")
    - Return 201 with created question on success
    - Return 400 with error message on validation failure
    - _Requirements: 1.2, 1.7, 2.1, 2.8_

  - [x] 7.2 Add GET `/api/questions` endpoint for retrieving active questions with community filtering
    - Require authentication using `@login_required` decorator
    - Accept optional community query parameter for filtering
    - For staff users, automatically filter by their assigned community
    - For admin users, return all active questions or filter by community parameter if provided
    - Return 200 with questions array
    - _Requirements: 1.6, 2.1, 2.2, 2.3_

  - [x] 7.3 Add PUT `/api/questions/<question_id>` endpoint for question updates
    - Require admin authentication using `@require_admin` decorator
    - Accept JSON with text, photo_required, and communities array fields
    - Validate question exists
    - Validate communities array is non-empty (return 400 with "At least one community must be selected")
    - Return 200 with updated question on success
    - Return 404 if question not found
    - _Requirements: 1.3, 2.5, 2.8_

  - [x] 7.4 Add DELETE `/api/questions/<question_id>` endpoint for question deletion
    - Require admin authentication using `@require_admin` decorator
    - Perform soft delete (set is_active to False)
    - Return 200 with success message
    - Return 404 if question not found
    - _Requirements: 1.4_

  - [ ]* 7.5 Write integration tests for Question Management API
    - Test question creation with community assignment
    - Test question creation with empty communities array (should fail)
    - Test question retrieval with community filtering
    - Test staff user sees only their community's questions
    - Test question update with community assignment changes
    - Test question deletion flow
    - Test authentication and authorization
    - _Requirements: 1.2, 1.3, 1.4, 1.6, 2.1, 2.3, 2.5, 2.8, 7.1, 7.2_

- [x] 8. Implement Inspection Submission API endpoints
  - [x] 8.1 Add POST `/api/inspections` endpoint for inspection submission
    - Require authentication using `@login_required` decorator
    - Accept multipart/form-data with responses array
    - Validate each response has question_id and condition
    - Handle optional photo uploads for each response
    - Save photos using FileUploadHandler
    - Create submission using InspectionService
    - Return 201 with submission data on success
    - Return 400 with error message on validation failure
    - _Requirements: 3.1, 3.3, 4.1, 4.2, 4.3, 4.4, 5.1, 5.7, 5.8_

  - [x] 8.2 Add GET `/api/inspections` endpoint for retrieving submissions
    - Require authentication using `@login_required` decorator
    - Filter by community for staff users
    - Allow admin users to filter by community via query parameter
    - Return 200 with submissions array
    - _Requirements: 9.1_

  - [ ]* 8.3 Write integration tests for Inspection Submission API
    - Test inspection submission with all questions answered
    - Test inspection submission with partial answers
    - Test photo upload handling
    - Test community filtering
    - Test validation errors
    - _Requirements: 3.1, 3.3, 5.1, 5.7, 5.8_

- [x] 9. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 10. Create Question Manager UI template with community multi-select
  - [x] 10.1 Create `question_manager.html` template in `templates/` directory
    - Add header with "Question Manager" title and logout button
    - Add "Create New Question" button (prominent, top-right)
    - Add question list table with columns: Question Text, Photo Required, Assigned Communities, Created Date, Actions
    - Add modal for create/edit form with:
      - Text input for question text
      - Checkbox for photo required
      - Multi-select dropdown for communities with "Select All" option
      - Visual indicator showing count of selected communities
      - Community badges or comma-separated list display
    - Add modal for delete confirmation with warning message
    - Use desktop-first design consistent with existing dashboard
    - Display questions sorted by created_at descending (newest first)
    - Display assigned communities as badges or comma-separated list in table
    - Add JavaScript for modal interactions and AJAX API calls
    - Add JavaScript for community multi-select functionality
    - _Requirements: 1.1, 1.6, 2.4, 2.6, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8_

  - [ ]* 10.2 Write property test for Question Manager UI rendering
    - **Property 6: Question List Rendering Completeness** (includes assigned communities display)
    - **Property 19: Edit Form Pre-Population** (includes community assignments)
    - **Property 20: Delete Confirmation Dialog**
    - **Validates: Requirements 1.6, 2.6, 6.1, 6.3, 6.4, 6.6**

- [x] 11. Update Inspection Form template with community-specific question filtering
  - [x] 11.1 Modify `reporte.html` template to display community-specific questions from Question Bank
    - Replace hardcoded location/condition fields with dynamic question sections
    - Load questions via AJAX, filtering by user's assigned community
    - Display only questions where user's community is in the question's communities array
    - For each question, add section with question text, radio buttons for "Good"/"Needs Attention", textarea for description
    - Add photo upload button only when question's photo_required is true
    - Add photo preview display for uploaded photos
    - Maintain mobile-first responsive design with touch-optimized controls (44x44px minimum)
    - Use existing gradient backgrounds and rounded corners
    - Add JavaScript for dynamic question loading via AJAX with community filtering
    - Add JavaScript for photo preview functionality
    - Add JavaScript for form submission with multipart/form-data
    - _Requirements: 2.2, 2.3, 3.1, 3.4, 4.1, 4.2, 4.3, 4.4, 4.8, 4.9, 10.1, 10.2, 10.3, 10.4, 10.5, 10.6_

  - [ ]* 11.2 Write property test for Inspection Form rendering
    - **Property 8: Community-Specific Question Filtering**
    - **Property 10: Multi-Community Question Assignment**
    - **Property 12: Question Section Rendering**
    - **Property 13: Conditional Photo Upload Display**
    - **Property 14: Photo Preview Display**
    - **Property 24: Touch Target Minimum Size**
    - **Validates: Requirements 2.2, 2.3, 2.4, 2.7, 4.1, 4.2, 4.3, 4.4, 4.8, 10.2**

- [x] 12. Enhance Dashboard template
  - [x] 12.1 Modify `dashboard.html` template to display inspection submissions
    - Add filter toggle for inspection vs. maintenance report types
    - Display inspection responses as cards with question text, condition badge, description, photo, username, community, timestamp
    - Apply existing card gallery layout
    - Add condition rating filter functionality
    - Add navigation link to Question Manager UI (visible only for admin users)
    - Use color-coded badges for condition ratings
    - Add JavaScript for filter functionality
    - Add JavaScript for loading inspection submissions via AJAX
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_

  - [ ]* 12.2 Write property test for Dashboard rendering
    - **Property 21: Dashboard Card Rendering**
    - **Property 22: Dashboard Condition Filter**
    - **Property 23: Admin Navigation Link Visibility**
    - **Validates: Requirements 9.1, 9.2, 9.3, 9.4, 9.5**

- [x] 13. Add Question Manager UI route
  - [x] 13.1 Add GET `/questions/manage` route in `app.py`
    - Require admin authentication using `@require_admin` decorator
    - Render `question_manager.html` template
    - _Requirements: 1.1, 7.1_

  - [ ]* 13.2 Write integration test for Question Manager UI route
    - Test admin access
    - Test staff user redirect
    - _Requirements: 1.1, 7.1, 7.2_

- [x] 14. Initialize services on application startup
  - [x] 14.1 Add service initialization in `app.py`
    - Create `data/` directory if it doesn't exist
    - Initialize QuestionManager instance with path to `questions.json`
    - Initialize InspectionService instance with paths to `inspections.json` and uploads folder
    - Initialize FileUploadHandler instance with uploads folder path
    - Load existing data from JSON files on startup
    - _Requirements: 1.5, 5.5, 8.1, 8.2_

  - [ ]* 14.2 Write integration test for service initialization
    - Test data directory creation
    - Test JSON file initialization
    - Test data loading on startup
    - _Requirements: 1.5, 5.5, 8.1, 8.2_

- [x] 15. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 16. Add error handling and validation
  - [x] 16.1 Add comprehensive error handling to all API endpoints
    - Handle JSON parsing errors with 400 Bad Request
    - Handle file system errors with 500 Internal Server Error
    - Handle malformed JSON files with fallback to empty state
    - Handle missing files by initializing with empty structure
    - Add input sanitization for all user inputs
    - Escape HTML in question text and descriptions
    - _Requirements: 1.7, 4.6, 4.7, 5.8_

  - [ ]* 16.2 Write integration tests for error handling
    - Test validation errors
    - Test file system errors
    - Test JSON parsing errors
    - Test authentication errors
    - _Requirements: 1.7, 4.6, 4.7, 5.8_

- [x] 17. Remove immediate question availability feature (no longer needed)
  - [x] 17.1 Remove real-time question update implementation
    - Community-specific filtering means questions are already filtered on load
    - No need for polling or WebSocket updates
    - Questions are loaded fresh on each inspection form access
    - _Requirements: 2.3_

  - [ ]* 17.2 Write integration test for community-specific question loading
    - Test that staff users see only their community's questions
    - Test that questions assigned to multiple communities appear for all assigned communities
    - Test that questions with empty communities array do not appear
    - **Property 8: Community-Specific Question Filtering**
    - **Property 10: Multi-Community Question Assignment**
    - **Validates: Requirements 2.3, 2.4, 2.7, 2.8**

- [x] 18. Final integration and wiring
  - [x] 18.1 Wire all components together
    - Verify all routes are registered
    - Verify all services are initialized
    - Verify all templates are rendering correctly
    - Test end-to-end question creation and inspection submission flow
    - Verify existing maintenance report functionality still works
    - _Requirements: 8.4, 8.5_

  - [ ]* 18.2 Write end-to-end integration tests
    - Test complete question management workflow with community assignment
    - Test complete inspection submission workflow with community-specific questions
    - Test multi-community question assignment and visibility
    - Test authentication and authorization across all routes
    - Test mobile responsiveness (manual testing required)
    - Test camera access on mobile devices (manual testing required)
    - _Requirements: 2.3, 2.4, 2.7, 8.4, 8.5, 10.3_

- [x] 19. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- The implementation maintains backward compatibility with existing maintenance report functionality
- All new code follows the existing Flask application structure and patterns
- Mobile optimization is critical for the Inspection Form as staff will use it in the field
- Admin UI is desktop-optimized as managers will use it from office computers
- **Community-specific question assignment is a core feature**: Questions are assigned to specific communities, and staff users only see questions for their assigned community
- **Multi-select community picker** in Question Manager UI allows assigning questions to multiple communities simultaneously
- **Empty communities array** is treated as an inactive question (validation error on create/update)

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1"] },
    { "id": 1, "tasks": ["2.1", "3.1", "4.1"] },
    { "id": 2, "tasks": ["2.2", "3.2", "4.2", "6.1"] },
    { "id": 3, "tasks": ["6.2", "7.1", "7.2", "7.3", "7.4"] },
    { "id": 4, "tasks": ["7.5", "8.1", "8.2"] },
    { "id": 5, "tasks": ["8.3", "10.1", "11.1", "12.1", "13.1"] },
    { "id": 6, "tasks": ["10.2", "11.2", "12.2", "13.2", "14.1"] },
    { "id": 7, "tasks": ["14.2", "16.1", "17.1"] },
    { "id": 8, "tasks": ["16.2", "17.2", "18.1"] },
    { "id": 9, "tasks": ["18.2"] }
  ]
}
```
