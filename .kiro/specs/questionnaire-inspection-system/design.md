# Technical Design Document

## Overview

This document describes the technical design for transforming the existing maintenance report system into a questionnaire-based inspection system. The system will enable administrators to create and manage inspection questions through a web interface, while staff members complete inspections by answering these questions with optional photo uploads. The design maintains the existing Flask architecture, session-based authentication, and JSON file-based storage while introducing new data models and UI components.

## Architecture

### System Architecture

The system follows a three-tier architecture:

1. **Presentation Layer**: HTML templates with JavaScript for dynamic interactions
   - Question Manager UI (desktop-optimized for admins)
   - Inspection Form (mobile-optimized for staff)
   - Dashboard (enhanced to display inspection submissions)

2. **Application Layer**: Flask web server with route handlers
   - Question management endpoints (CRUD operations)
   - Inspection submission endpoints
   - Authentication and authorization middleware
   - File upload handling

3. **Data Layer**: JSON file-based storage
   - Question Bank (questions.json)
   - Inspection Submissions (inspections.json)
   - Photo storage (filesystem with community-based organization)

### Component Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     Presentation Layer                       │
├──────────────────┬──────────────────┬──────────────────────┤
│ Question Manager │ Inspection Form  │ Dashboard            │
│ UI (Admin)       │ (Staff Mobile)   │ (Admin/Staff)        │
└────────┬─────────┴────────┬─────────┴──────────┬───────────┘
         │                  │                    │
         └──────────────────┼────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│                    Application Layer                         │
├──────────────────┬──────────────────┬──────────────────────┤
│ Question Manager │ Inspection       │ Auth & Session       │
│ Service          │ Service          │ Manager              │
├──────────────────┼──────────────────┼──────────────────────┤
│ File Upload      │ JSON Serializer  │ Validation           │
│ Handler          │                  │ Service              │
└────────┬─────────┴────────┬─────────┴──────────┬───────────┘
         │                  │                    │
         └──────────────────┼────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│                       Data Layer                             │
├──────────────────┬──────────────────┬──────────────────────┤
│ questions.json   │ inspections.json │ uploads/             │
│ (Question Bank)  │ (Submissions)    │ (Photos by community)│
└──────────────────┴──────────────────┴──────────────────────┘
```

## Data Models

### Question Model

Represents an inspection question in the Question Bank.

```python
{
    "id": str,              # Unique identifier (timestamp-based: "q_<timestamp>_<random>")
    "text": str,            # Question text (required, non-empty)
    "photo_required": bool, # Whether photo upload is required
    "communities": [str],   # Array of community names this question applies to
    "created_at": str,      # ISO 8601 timestamp
    "updated_at": str,      # ISO 8601 timestamp
    "is_active": bool       # Soft delete flag (true = active, false = deleted)
}
```

**Validation Rules:**
- `text`: Must be non-empty after stripping whitespace
- `id`: Must be unique across all questions
- `communities`: Must be a non-empty array of community names; empty array treated as inactive
- `created_at`: Set once on creation, never modified
- `updated_at`: Updated on every edit operation
- `is_active`: Defaults to `true` on creation

### Question Bank Model

Container for all questions, stored in `questions.json`.

```python
{
    "version": str,         # Schema version (e.g., "1.0")
    "last_modified": str,   # ISO 8601 timestamp
    "questions": [          # Array of Question objects
        {Question},
        {Question},
        ...
    ]
}
```

### Inspection Response Model

Represents a staff member's answer to a single question.

```python
{
    "question_id": str,     # References Question.id
    "question_text": str,   # Snapshot of question text at submission time
    "condition": str,       # "Good" or "Needs Attention"
    "description": str,     # Free-text description
    "photo_path": str,      # Relative path to photo file (null if no photo)
    "answered_at": str      # ISO 8601 timestamp
}
```

**Validation Rules:**
- `question_id`: Must reference an existing question
- `condition`: Must be exactly "Good" or "Needs Attention"
- `description`: Can be empty string
- `photo_path`: Must be valid file path if present

### Inspection Submission Model

Represents a complete inspection submission by a staff member.

```python
{
    "id": str,              # Unique identifier (timestamp-based: "insp_<timestamp>_<random>")
    "username": str,        # Staff member username
    "community": str,       # Community name (from user's assignment)
    "submitted_at": str,    # ISO 8601 timestamp
    "responses": [          # Array of InspectionResponse objects
        {InspectionResponse},
        {InspectionResponse},
        ...
    ]
}
```

### Inspection Submissions Collection

Container for all submissions, stored in `inspections.json`.

```python
{
    "version": str,         # Schema version (e.g., "1.0")
    "last_modified": str,   # ISO 8601 timestamp
    "submissions": [        # Array of InspectionSubmission objects
        {InspectionSubmission},
        {InspectionSubmission},
        ...
    ]
}
```

## Core Components

### 1. Question Manager Service

**Responsibilities:**
- CRUD operations for questions
- Question Bank persistence
- Question validation
- Soft delete implementation

**Key Methods:**

```python
class QuestionManager:
    def __init__(self, storage_path: str):
        """Initialize with path to questions.json"""
        
    def create_question(self, text: str, photo_required: bool, communities: List[str]) -> Question:
        """Create new question with validation"""
        
    def get_question(self, question_id: str) -> Question:
        """Retrieve question by ID"""
        
    def get_all_active_questions(self) -> List[Question]:
        """Retrieve all active questions"""
        
    def get_questions_for_community(self, community: str) -> List[Question]:
        """Retrieve active questions assigned to specific community"""
        
    def update_question(self, question_id: str, text: str, photo_required: bool, communities: List[str]) -> Question:
        """Update existing question, preserving ID and created_at"""
        
    def delete_question(self, question_id: str) -> bool:
        """Soft delete question by setting is_active to False"""
        
    def save_to_file(self) -> None:
        """Persist Question Bank to JSON file"""
        
    def load_from_file(self) -> None:
        """Load Question Bank from JSON file"""
```

**Implementation Notes:**
- Use `datetime.now().isoformat()` for timestamps
- Generate IDs using `f"q_{int(time.time() * 1000)}_{random.randint(1000, 9999)}"`
- Validate text is non-empty after `strip()`
- Validate communities array is non-empty (empty array = inactive question)
- Filter questions by community membership when loading for staff users
- Maintain questions sorted by `created_at` descending for UI display

### 2. Inspection Service

**Responsibilities:**
- Inspection submission handling
- Response validation
- Photo file management
- Submission persistence

**Key Methods:**

```python
class InspectionService:
    def __init__(self, storage_path: str, upload_path: str):
        """Initialize with paths to inspections.json and uploads folder"""
        
    def create_submission(self, username: str, community: str, 
                         responses: List[Dict]) -> InspectionSubmission:
        """Create new inspection submission"""
        
    def validate_response(self, response: Dict) -> bool:
        """Validate individual response data"""
        
    def save_photo(self, file, username: str, community: str) -> str:
        """Save uploaded photo and return relative path"""
        
    def get_submissions_by_community(self, community: str) -> List[InspectionSubmission]:
        """Retrieve submissions for specific community"""
        
    def get_all_submissions(self) -> List[InspectionSubmission]:
        """Retrieve all submissions (admin only)"""
        
    def save_to_file(self) -> None:
        """Persist submissions to JSON file"""
        
    def load_from_file(self) -> None:
        """Load submissions from JSON file"""
```

**Implementation Notes:**
- Photo filename format: `{username}_{community}_{timestamp}.{ext}`
- Community folders: `uploads/{secure_filename(community)}/`
- Validate file extensions: jpg, jpeg, png, gif, webp
- Validate file size: max 16MB
- Store only answered questions (skip empty responses)

### 3. Authentication & Authorization Service

**Responsibilities:**
- User authentication
- Session management
- Role-based access control
- Route protection

**Key Methods:**

```python
class AuthService:
    def authenticate(self, username: str, password: str) -> Tuple[bool, Optional[str]]:
        """Authenticate user and return (success, community)"""
        
    def is_admin(self, username: str) -> bool:
        """Check if user has admin role (community is None)"""
        
    def require_login(self, f):
        """Decorator for routes requiring authentication"""
        
    def require_admin(self, f):
        """Decorator for routes requiring admin role"""
```

**Implementation Notes:**
- Reuse existing `USERS_DB` structure
- Admin users have `community: None`
- Session stores: `user`, `community`, `is_admin`
- Redirect non-admin users attempting to access admin routes

### 4. File Upload Handler

**Responsibilities:**
- File validation
- Secure filename generation
- Community folder management
- File storage

**Key Methods:**

```python
class FileUploadHandler:
    def __init__(self, upload_folder: str):
        """Initialize with base upload folder path"""
        
    def validate_file(self, file) -> Tuple[bool, str]:
        """Validate file type and size, return (valid, error_message)"""
        
    def save_file(self, file, username: str, community: str) -> str:
        """Save file and return relative path"""
        
    def ensure_community_folder(self, community: str) -> str:
        """Create community folder if it doesn't exist"""
```

**Implementation Notes:**
- Use `werkzeug.utils.secure_filename()` for sanitization
- Check file extension against `ALLOWED_EXTENSIONS`
- Check file size before saving
- Create community folders with `os.makedirs(exist_ok=True)`

## API Endpoints

### Question Management Endpoints

#### Create Question
```
POST /api/questions
Authorization: Admin only
Content-Type: application/json

Request Body:
{
    "text": "Is the common area clean?",
    "photo_required": true,
    "communities": ["Community A", "Community B", "Community C"]
}

Response (201):
{
    "status": "success",
    "question": {Question}
}

Response (400):
{
    "status": "error",
    "message": "Question text cannot be empty"
}

Response (400):
{
    "status": "error",
    "message": "At least one community must be selected"
}
```

#### Get All Active Questions
```
GET /api/questions
Authorization: Required
Query Parameters:
  - community: string (optional, filters questions by community)

Response (200):
{
    "status": "success",
    "questions": [{Question}, {Question}, ...]
}

Note: If community parameter is provided, returns only questions assigned to that community.
      Admin users without community parameter receive all active questions.
      Staff users automatically filtered by their assigned community.
```

#### Update Question
```
PUT /api/questions/<question_id>
Authorization: Admin only
Content-Type: application/json

Request Body:
{
    "text": "Updated question text",
    "photo_required": false,
    "communities": ["Community A", "Community D"]
}

Response (200):
{
    "status": "success",
    "question": {Question}
}

Response (404):
{
    "status": "error",
    "message": "Question not found"
}

Response (400):
{
    "status": "error",
    "message": "At least one community must be selected"
}
```

#### Delete Question
```
DELETE /api/questions/<question_id>
Authorization: Admin only

Response (200):
{
    "status": "success",
    "message": "Question deleted successfully"
}

Response (404):
{
    "status": "error",
    "message": "Question not found"
}
```

### Inspection Endpoints

#### Submit Inspection
```
POST /api/inspections
Authorization: Required (Staff)
Content-Type: multipart/form-data

Request Body:
{
    "responses": [
        {
            "question_id": "q_1234567890_5678",
            "condition": "Good",
            "description": "Everything looks clean",
            "photo": <file> (optional)
        },
        ...
    ]
}

Response (201):
{
    "status": "success",
    "submission": {InspectionSubmission}
}

Response (400):
{
    "status": "error",
    "message": "Invalid response data"
}
```

#### Get Inspections
```
GET /api/inspections
Authorization: Required
Query Parameters:
  - community: string (optional, admin can filter by community)

Response (200):
{
    "status": "success",
    "submissions": [{InspectionSubmission}, ...]
}
```

### UI Routes

#### Question Manager UI
```
GET /questions/manage
Authorization: Admin only
Returns: HTML page with question management interface
```

#### Inspection Form
```
GET /
Authorization: Required (Staff)
Returns: HTML page with inspection form
```

#### Dashboard
```
GET /dashboard
Authorization: Required
Returns: HTML page with inspection submissions
```

## User Interface Design

### Question Manager UI (Admin)

**Layout:**
- Header with "Question Manager" title and logout button
- "Create New Question" button (prominent, top-right)
- Question list table with columns:
  - Question Text
  - Photo Required (Yes/No badge)
  - Assigned Communities (comma-separated list or count badge)
  - Created Date
  - Actions (Edit, Delete buttons)
- Questions sorted newest first

**Create/Edit Form (Modal):**
- Text input for question text (required)
- Checkbox for "Photo Required"
- Multi-select dropdown for communities with:
  - "Select All" checkbox option at top
  - Individual community checkboxes
  - Visual indicator showing count of selected communities
- Save and Cancel buttons
- Validation error display

**Delete Confirmation (Modal):**
- Warning message
- Confirm and Cancel buttons

**Styling:**
- Desktop-first design
- Consistent with existing dashboard
- Table with hover effects
- Action buttons with icons
- Community badges with color coding

### Inspection Form (Staff Mobile)

**Layout:**
- Header with community name and username
- Question sections (scrollable vertical list)
  - **Only displays questions assigned to user's community**
- Each question section contains:
  - Question text (bold, readable)
  - Radio buttons for "Good" / "Needs Attention"
  - Textarea for description
  - Photo upload button (if required)
  - Photo preview (if uploaded)
- Submit button (fixed at bottom)

**Interaction Flow:**
1. Staff member sees only questions for their assigned community
2. Staff member scrolls through filtered questions
3. For each question, selects condition rating
4. Optionally adds description
5. Uploads photo if required
6. Can skip questions
7. Submits form
8. Sees success message

**Styling:**
- Mobile-first responsive design
- Touch-optimized controls (44x44px minimum)
- Gradient backgrounds
- Rounded corners
- Visual feedback on touch
- Camera icon for photo upload
- Preview thumbnails for uploaded photos

### Dashboard Enhancement

**New Features:**
- Filter by inspection vs. maintenance report
- Display inspection responses as cards
- Each card shows:
  - Question text
  - Condition rating (color-coded badge)
  - Description
  - Photo (if present)
  - Username, community, timestamp
- Filter by condition rating
- Navigation link to Question Manager (admin only)

**Card Layout:**
```
┌─────────────────────────────────────┐
│ Question: Is the common area clean? │
│                                     │
│ Condition: ● Good                   │
│                                     │
│ Description: Everything looks clean │
│                                     │
│ [Photo Preview]                     │
│                                     │
│ john | Community A | 2024-01-15     │
└─────────────────────────────────────┘
```

## Data Storage

### File Structure

```
app_mantenimiento/
├── data/
│   ├── questions.json          # Question Bank
│   └── inspections.json        # Inspection Submissions
├── static/
│   └── uploads/
│       ├── Community_A/        # Photos for Community A
│       ├── Community_B/        # Photos for Community B
│       └── ...
```

### JSON Schema

**questions.json:**
```json
{
    "version": "1.0",
    "last_modified": "2024-01-15T10:30:00Z",
    "questions": [
        {
            "id": "q_1705315800000_5678",
            "text": "Is the common area clean?",
            "photo_required": true,
            "communities": ["Community A", "Community B", "Community C"],
            "created_at": "2024-01-15T10:30:00Z",
            "updated_at": "2024-01-15T10:30:00Z",
            "is_active": true
        }
    ]
}
```

**inspections.json:**
```json
{
    "version": "1.0",
    "last_modified": "2024-01-15T11:00:00Z",
    "submissions": [
        {
            "id": "insp_1705317600000_1234",
            "username": "john",
            "community": "Community A",
            "submitted_at": "2024-01-15T11:00:00Z",
            "responses": [
                {
                    "question_id": "q_1705315800000_5678",
                    "question_text": "Is the common area clean?",
                    "condition": "Good",
                    "description": "Everything looks clean",
                    "photo_path": "uploads/Community_A/john_Community_A_1705317600.jpg",
                    "answered_at": "2024-01-15T11:00:00Z"
                }
            ]
        }
    ]
}
```

## Error Handling

### Validation Errors

**Question Creation/Update:**
- Empty question text → 400 Bad Request with message
- Invalid photo_required value → 400 Bad Request with message
- Empty communities array → 400 Bad Request with message "At least one community must be selected"
- Invalid community name → 400 Bad Request with message

**Inspection Submission:**
- Invalid condition value → 400 Bad Request with message
- Invalid file type → 400 Bad Request with message
- File size exceeds 16MB → 400 Bad Request with message
- Missing required photo → 400 Bad Request with message

### Storage Errors

**File System Errors:**
- Cannot create directory → 500 Internal Server Error
- Cannot write file → 500 Internal Server Error
- Cannot read file → 500 Internal Server Error

**JSON Errors:**
- Malformed JSON → 500 Internal Server Error with fallback to empty state
- Missing file → Initialize with empty structure

### Authentication Errors

**Unauthorized Access:**
- Not logged in → 302 Redirect to login
- Staff accessing admin route → 302 Redirect to inspection form
- Invalid credentials → 401 Unauthorized with message

## Security Considerations

### Input Validation

- Sanitize all user inputs
- Validate file extensions against whitelist
- Validate file sizes before processing
- Use `secure_filename()` for all file operations
- Escape HTML in question text and descriptions

### Authentication & Authorization

- Maintain session-based authentication
- Check user role on every admin route
- Use `@login_required` and `@require_admin` decorators
- Store minimal data in session

### File Upload Security

- Validate file type by extension and MIME type
- Limit file size to 16MB
- Store files outside web root if possible
- Use secure, non-guessable filenames
- Prevent directory traversal attacks

### Data Protection

- Do not expose internal IDs in URLs where possible
- Validate all question_id references
- Prevent SQL injection (not applicable with JSON storage)
- Sanitize community names in file paths

## Migration Strategy

### Phase 1: Data Structure Setup

1. Create `data/` directory
2. Initialize `questions.json` with empty structure
3. Initialize `inspections.json` with empty structure
4. Verify existing `uploads/` directory structure

### Phase 2: Backend Implementation

1. Implement `QuestionManager` service
2. Implement `InspectionService` service
3. Add new API endpoints
4. Add route protection for admin endpoints
5. Update existing routes to coexist with new system

### Phase 3: Frontend Implementation

1. Create Question Manager UI template
2. Update Inspection Form template
3. Enhance Dashboard template
4. Add JavaScript for dynamic interactions
5. Test on mobile and desktop devices

### Phase 4: Testing & Deployment

1. Test question CRUD operations
2. Test inspection submission flow
3. Test file uploads
4. Test authentication and authorization
5. Verify existing maintenance reports still work
6. Deploy to production

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property Reflection

After reviewing all testable properties from the prework analysis, the following redundancies were identified:

**Redundant Properties:**
- 3.5 (skipped questions not stored) is redundant with 3.3 (only answered questions stored)
- 4.5 (no photo upload when flag false) is redundant with 4.4 (photo upload when flag true)
- 7.1 (admin access restriction) is redundant with 1.1 (Question Manager UI admin-only access)

**Combined Properties:**
- 5.2 and 5.6 can be combined into a single property about response data completeness
- 6.1 and 6.6 can be combined into a single property about question list rendering

**Community-Specific Updates:**
- Property 2 now includes community assignment validation
- Property 3 now includes community assignment updates
- Property 6 now includes displaying assigned communities
- Properties 8-10 are new properties specifically for community-based filtering and assignment

These redundancies have been eliminated in the properties below, ensuring each property provides unique validation value.

### Property 1: Admin-Only Access Control

*For any* user account, if the user is not an admin (community is not None), then attempting to access the Question Manager UI should result in a redirect to the Inspection Form

**Validates: Requirements 1.1, 7.1, 7.2**

### Property 2: Question Creation Persistence

*For any* valid question data (non-empty text, boolean photo requirement, and non-empty communities array), creating a question should result in the question being stored in the Question Bank JSON file with all required fields: unique ID, text, photo_required flag, communities array, created_at timestamp, updated_at timestamp, and is_active flag set to true

**Validates: Requirements 1.2, 2.1, 2.2**

### Property 3: Question Edit Invariants

*For any* existing question, editing the question text, photo requirement, or community assignments should update those fields and the updated_at timestamp while preserving the original unique identifier and created_at timestamp unchanged

**Validates: Requirements 1.3, 2.5**

### Property 4: Soft Delete Preservation

*For any* question in the Question Bank, deleting the question should set is_active to false while preserving all other question data in the JSON file

**Validates: Requirements 1.4**

### Property 5: Question Bank Serialization Round-Trip

*For any* Question Bank state, saving to JSON and then loading from JSON should produce an equivalent Question Bank with all questions and their properties preserved

**Validates: Requirements 1.5**

### Property 6: Question List Rendering Completeness

*For any* set of questions in the Question Bank, rendering the Question Manager UI should display all questions with their text, photo requirement status, assigned communities, creation date, and edit/delete action buttons, sorted by creation date with newest first

**Validates: Requirements 1.6, 2.6, 6.1, 6.6**

### Property 7: Question ID Uniqueness

*For any* sequence of question creation operations, all generated question IDs should be unique across the entire Question Bank

**Validates: Requirements 1.8**

### Property 8: Community-Specific Question Filtering

*For any* staff user with an assigned community, the Inspection Form should display only active questions where the user's community is included in the question's communities array

**Validates: Requirements 2.3**

### Property 9: Community Assignment Validation

*For any* question creation or update operation, if the communities array is empty, the operation should fail with a validation error message "At least one community must be selected"

**Validates: Requirements 2.8**

### Property 10: Multi-Community Question Assignment

*For any* question assigned to multiple communities, the question should appear in the Inspection Form for staff users from each of those assigned communities

**Validates: Requirements 2.4, 2.7**

### Property 11: Partial Submission Acceptance

*For any* subset of questions from the Question Bank (including empty subset), a staff user should be able to submit an Inspection Submission containing only responses to that subset without validation errors

**Validates: Requirements 3.1, 3.3**

### Property 12: Question Section Rendering

*For any* set of active questions assigned to a staff user's community, rendering the Inspection Form should display each question as a separate section containing the question text, radio buttons for "Good" and "Needs Attention", and a textarea for description

**Validates: Requirements 4.1, 4.2, 4.3**

### Property 13: Conditional Photo Upload Display

*For any* question in the Inspection Form, a photo upload button should be displayed if and only if the question's photo_required flag is true

**Validates: Requirements 4.4**

### Property 14: Photo Preview Display

*For any* photo uploaded in the Inspection Form, a preview of the photo should be displayed in the UI before submission

**Validates: Requirements 4.8**

### Property 15: Submission Response Completeness

*For any* Inspection Submission, each stored response should contain all required fields: question_id, question_text, condition rating, description text, photo_path (or null), answered_at timestamp, and the submission should include username, community, and submitted_at timestamp

**Validates: Requirements 5.1, 5.2, 5.6**

### Property 16: Photo Organization by Community

*For any* photo uploaded as part of an inspection response, the photo file should be stored in a folder named after the user's assigned community within the uploads directory

**Validates: Requirements 5.3**

### Property 17: Photo Filename Format and Uniqueness

*For any* photo uploaded as part of an inspection response, the generated filename should match the pattern `{username}_{community}_{timestamp}.{extension}` and should be unique across all uploaded photos

**Validates: Requirements 5.4**

### Property 18: Inspection Submission Serialization Round-Trip

*For any* Inspection Submission, saving to JSON and then loading from JSON should produce an equivalent submission with all responses and metadata preserved

**Validates: Requirements 5.5**

### Property 19: Edit Form Pre-Population

*For any* question in the Question Manager UI, clicking the edit button should open a form pre-populated with that question's current text, photo_required value, and assigned communities

**Validates: Requirements 6.3**

### Property 20: Delete Confirmation Dialog

*For any* question in the Question Manager UI, clicking the delete button should display a confirmation dialog before performing the deletion

**Validates: Requirements 6.4**

### Property 21: Dashboard Card Rendering

*For any* inspection response, rendering the dashboard should display a card containing the question text, condition rating, description, photo (if present), username, community, and submission timestamp

**Validates: Requirements 9.1, 9.2, 9.4**

### Property 22: Dashboard Condition Filter

*For any* condition rating filter selection ("Good" or "Needs Attention"), the dashboard should display only inspection response cards matching that condition rating

**Validates: Requirements 9.3**

### Property 23: Admin Navigation Link Visibility

*For any* user viewing the dashboard, a navigation link to the Question Manager UI should be visible if and only if the user has admin role (community is None)

**Validates: Requirements 9.5**

### Property 24: Touch Target Minimum Size

*For any* radio button control in the Inspection Form, the touch target size should be at least 44x44 pixels to ensure mobile accessibility

**Validates: Requirements 10.2**

## Testing Strategy

### Unit Testing

Unit tests will focus on:
- Question validation logic (empty text rejection, empty communities array rejection)
- Community assignment validation
- ID generation uniqueness
- Soft delete behavior
- File upload validation (type and size)
- Filename generation format
- JSON serialization/deserialization
- Authentication and authorization logic
- Community filtering logic

### Property-Based Testing

Property tests will verify universal properties across randomized inputs:
- Question CRUD operations with random text, flags, and community assignments
- Community filtering with random user assignments
- Inspection submissions with random question subsets
- Photo uploads with random filenames and communities
- Access control with random user roles
- UI rendering with random question sets and community filters
- Filter operations with random condition ratings
- Multi-community question assignments

**Configuration:**
- Minimum 100 iterations per property test
- Each test tagged with feature name and property number
- Example tag: `Feature: questionnaire-inspection-system, Property 8: Community-Specific Question Filtering`

### Integration Testing

Integration tests will verify:
- End-to-end question creation flow with community assignments
- End-to-end inspection submission flow with community filtering
- Community-specific question visibility
- Multi-community question assignment
- File upload and storage
- Session management
- Route protection
- Dashboard filtering
- Mobile responsiveness (manual)
- Camera access on mobile devices (manual)

### Test Data Generators

Property-based tests will use generators for:
- Random question text (including edge cases: empty, whitespace, special characters, very long)
- Random boolean values for photo_required
- Random community assignments (single, multiple, all 38 communities, empty array)
- Random user accounts (admin and staff with various community assignments)
- Random condition ratings ("Good", "Needs Attention")
- Random file uploads (valid images, invalid types, oversized files)
- Random question subsets for partial submissions
- Random timestamps for ordering tests
- Random community names from the 38 available communities
- Mobile responsiveness (manual)
- Camera access on mobile devices (manual)

### Test Data Generators

Property-based tests will use generators for:
- Random question text (including edge cases: empty, whitespace, special characters, very long)
- Random boolean values for photo_required
- Random user accounts (admin and staff with various communities)
- Random condition ratings ("Good", "Needs Attention")
- Random file uploads (valid images, invalid types, oversized files)
- Random question subsets for partial submissions
- Random timestamps for ordering tests

## Performance Considerations

### JSON File Size Management

- Monitor `questions.json` and `inspections.json` file sizes
- Consider pagination for dashboard if submissions exceed 1000
- Implement archival strategy for old submissions if needed

### Photo Storage

- Implement file size limits (16MB per photo)
- Monitor disk space usage
- Consider compression for uploaded photos
- Implement cleanup for orphaned photos

### UI Performance

- Lazy load photos in dashboard
- Implement virtual scrolling for large question lists
- Optimize mobile form rendering for 50+ questions
- Cache active questions in memory

## Future Enhancements

### Potential Features

1. **Question Categories**: Group questions by area (kitchen, bathroom, common areas)
2. **Question Templates**: Pre-defined question sets for different inspection types
3. **Scheduled Inspections**: Automatic reminders for periodic inspections
4. **Analytics Dashboard**: Trends and statistics on inspection results
5. **Export Functionality**: PDF reports of inspection submissions
6. **Photo Annotations**: Draw on photos to highlight issues
7. **Offline Support**: Complete inspections without internet connection
8. **Multi-language Support**: Questions and UI in multiple languages

### Scalability Considerations

- Migrate from JSON to SQLite or PostgreSQL for better performance
- Implement caching layer (Redis) for frequently accessed data
- Add search functionality for questions and submissions
- Implement pagination for all list views
- Add bulk operations for question management

## Appendix

### Technology Stack

- **Backend**: Python 3.x, Flask 2.x
- **Frontend**: HTML5, CSS3, JavaScript (ES6+)
- **Storage**: JSON files, filesystem
- **Authentication**: Flask sessions
- **File Upload**: Werkzeug utilities

### Dependencies

- Flask
- Werkzeug
- Python standard library (json, datetime, os, random)

### Browser Support

- Chrome/Edge (latest 2 versions)
- Safari (latest 2 versions)
- Firefox (latest 2 versions)
- Mobile Safari (iOS 14+)
- Chrome Mobile (Android 10+)

### Accessibility

- WCAG 2.1 Level AA compliance target
- Keyboard navigation support
- Screen reader compatibility
- Touch target sizing (44x44px minimum)
- Color contrast ratios (4.5:1 for text)
