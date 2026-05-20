# Survey Types System - Technical Design

## Architecture Overview

The Survey Types System extends the existing questionnaire-based inspection system by adding a type classification layer. This allows different types of inspections to use different sets of questions while maintaining the existing data structures and workflows.

---

## System Components

### 1. Survey Type Selection Interface
**Location**: New template `select_survey_type.html`  
**Purpose**: Allow users to select inspection type before starting questionnaire

**Components**:
- Survey type cards with icons and descriptions
- Radio button selection mechanism
- Continue button with validation
- Back navigation to dashboard

### 2. Survey Type Data Layer
**Location**: New file `survey_types.json` + modifications to `questions.json` and `inspections.json`  
**Purpose**: Store survey type definitions and associations

**Structure**:
```json
// survey_types.json
{
  "version": "1.0",
  "last_modified": "2026-05-18T00:00:00Z",
  "survey_types": [
    {
      "id": "full-regional",
      "name": "Full Regional Review",
      "icon": "fa-sitemap",
      "color": "#3b82f6",
      "description": "Comprehensive review covering all aspects",
      "is_active": true
    },
    // ... other survey types
  ]
}
```

### 3. Question Filtering Service
**Location**: `services/question_filter.py` (new file)  
**Purpose**: Filter questions based on survey type

**Methods**:
- `get_questions_by_survey_type(survey_type_id, community)`
- `get_survey_types()`
- `validate_survey_type(survey_type_id)`

### 4. Session Management
**Location**: Flask session (existing)  
**Purpose**: Store selected survey type during inspection flow

**Session Keys**:
- `selected_survey_type`: Current survey type ID
- `survey_type_timestamp`: When survey type was selected

### 5. Updated Question Manager
**Location**: `templates/question_manager.html` + backend modifications  
**Purpose**: Allow admins to assign survey types to questions

**New Features**:
- Multi-select survey type dropdown
- Survey type tags on question cards
- Filter by survey type
- Bulk assignment tool

### 6. Updated Dashboard
**Location**: `templates/dashboard.html` + JavaScript modifications  
**Purpose**: Display survey type information in inspection details

**New Features**:
- Survey type badge in inspection modal
- Survey type filter in filter section
- Survey type indicator on community cards

---

## Data Model Changes

### Questions Schema Update
```json
{
  "id": "q_1234567890_1234",
  "text": "Is the common area clean?",
  "photo_required": true,
  "communities": ["Community A", "Community B"],
  "survey_types": ["full-regional", "operational", "life-safety"],  // NEW
  "created_at": "2026-05-18T00:00:00Z",
  "updated_at": "2026-05-18T00:00:00Z",
  "is_active": true,
  "template_id": "q_template_123"
}
```

**Migration Strategy**:
- Add `survey_types` field (optional, defaults to empty array)
- Empty array means question belongs to all survey types (backward compatibility)
- Existing questions without this field are treated as having empty array

### Inspections Schema Update
```json
{
  "id": "insp_1234567890_1234",
  "username": "user1",
  "community": "Community A",
  "survey_type": "full-regional",  // NEW
  "submitted_at": "2026-05-18T00:00:00Z",
  "responses": [
    // ... existing response structure
  ]
}
```

**Migration Strategy**:
- Add `survey_type` field (optional, defaults to null)
- Null value means legacy inspection (before survey types were implemented)
- Display as "Unspecified" or "Legacy" in UI

---

## API Endpoints

### New Endpoints

#### GET `/api/survey-types`
**Purpose**: Get list of all survey types  
**Authentication**: Required  
**Response**:
```json
{
  "status": "success",
  "survey_types": [
    {
      "id": "full-regional",
      "name": "Full Regional Review",
      "icon": "fa-sitemap",
      "color": "#3b82f6",
      "description": "Comprehensive review covering all aspects"
    }
  ]
}
```

#### POST `/api/select-survey-type`
**Purpose**: Store selected survey type in session  
**Authentication**: Required  
**Request Body**:
```json
{
  "survey_type": "full-regional"
}
```
**Response**:
```json
{
  "status": "success",
  "message": "Survey type selected",
  "survey_type": "full-regional"
}
```

### Modified Endpoints

#### GET `/api/questions`
**Changes**: Add `survey_type` query parameter  
**Example**: `/api/questions?community=Community+A&survey_type=full-regional`  
**Behavior**:
- If `survey_type` provided, return only questions assigned to that type
- If question has empty `survey_types` array, include in all types
- Maintain existing community filtering

#### POST `/api/inspections`
**Changes**: Include `survey_type` in submission  
**Request Body** (modified):
```json
{
  "responses": "...",  // existing
  "survey_type": "full-regional"  // NEW - from session
}
```

#### GET `/api/inspections`
**Changes**: Add `survey_type` query parameter for filtering  
**Example**: `/api/inspections?survey_type=full-regional`

---

## Routing Changes

### New Routes

#### `/select-survey-type`
**Method**: GET  
**Template**: `select_survey_type.html`  
**Authentication**: Required  
**Purpose**: Display survey type selection screen

**Flow**:
1. User clicks "Start New Visit" from dashboard
2. Redirect to `/select-survey-type`
3. User selects survey type and clicks Continue
4. POST to `/api/select-survey-type` to store in session
5. Redirect to `/reporte` (questionnaire form)

### Modified Routes

#### `/reporte`
**Changes**: Check for survey type in session  
**Behavior**:
- If no survey type in session, redirect to `/select-survey-type`
- Pass survey type to template for question filtering
- Clear survey type from session after successful submission

#### `/`
**Changes**: Redirect to `/select-survey-type` instead of `/reporte`  
**Behavior**:
- After login, "Start New Visit" goes to survey type selection
- Maintains existing authentication checks

---

## Frontend Components

### Survey Type Selection Screen

**File**: `templates/select_survey_type.html`

**Structure**:
```html
<!DOCTYPE html>
<html>
<head>
    <title>Start Visit</title>
    <!-- Mobile-optimized viewport -->
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body>
    <div class="container">
        <header>
            <button class="back-btn">←</button>
            <h1>Start Visit</h1>
        </header>
        
        <h2>What type of visit are you conducting?</h2>
        
        <form id="surveyTypeForm">
            <div class="survey-type-option">
                <input type="radio" name="survey_type" value="full-regional" id="full-regional">
                <label for="full-regional">
                    <i class="fas fa-sitemap"></i>
                    <span>Full Regional Review</span>
                </label>
            </div>
            
            <!-- Repeat for other survey types -->
            
            <button type="submit" class="continue-btn" disabled>Continue</button>
        </form>
    </div>
</body>
</html>
```

**Styling**:
- Mobile-first design
- Large touch targets (min 44px)
- Clear visual feedback for selection
- Disabled state for Continue button until selection made

**JavaScript**:
```javascript
// Enable Continue button when survey type selected
document.querySelectorAll('input[name="survey_type"]').forEach(radio => {
    radio.addEventListener('change', () => {
        document.querySelector('.continue-btn').disabled = false;
    });
});

// Handle form submission
document.getElementById('surveyTypeForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const surveyType = document.querySelector('input[name="survey_type"]:checked').value;
    
    const response = await fetch('/api/select-survey-type', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ survey_type: surveyType })
    });
    
    if (response.ok) {
        window.location.href = '/reporte';
    }
});
```

### Question Manager Updates

**File**: `templates/question_manager.html`

**New Elements**:
1. **Survey Type Multi-Select**:
```html
<div class="form-group">
    <label>Survey Types</label>
    <select multiple id="surveyTypes" class="form-control">
        <option value="full-regional">Full Regional Review</option>
        <option value="operational">Operational Review</option>
        <!-- ... other options -->
    </select>
    <small>Leave empty to include in all survey types</small>
</div>
```

2. **Survey Type Tags**:
```html
<div class="survey-type-tags">
    <span class="badge badge-blue">Full Regional</span>
    <span class="badge badge-green">Operational</span>
</div>
```

3. **Survey Type Filter**:
```html
<select id="filterSurveyType" class="form-control">
    <option value="">All Survey Types</option>
    <option value="full-regional">Full Regional Review</option>
    <!-- ... other options -->
</select>
```

### Dashboard Updates

**File**: `templates/dashboard.html`

**New Elements in Inspection Modal**:
```html
<div class="meta-item">
    <div class="meta-label">Survey Type</div>
    <div class="meta-value">
        <span class="survey-type-badge" style="background: #3b82f6;">
            <i class="fas fa-sitemap"></i>
            Full Regional Review
        </span>
    </div>
</div>
```

**New Filter Buttons**:
```html
<button class="filter-btn" data-survey-type="full-regional">
    <i class="fas fa-sitemap"></i> Full Regional
</button>
<!-- ... other survey type filters -->
```

---

## Backend Services

### Survey Type Service

**File**: `services/survey_type_service.py` (new)

```python
import json
import os
from datetime import datetime

class SurveyTypeService:
    def __init__(self, survey_types_file):
        self.survey_types_file = survey_types_file
        self._ensure_file_exists()
    
    def _ensure_file_exists(self):
        """Create survey_types.json if it doesn't exist"""
        if not os.path.exists(self.survey_types_file):
            default_data = {
                "version": "1.0",
                "last_modified": datetime.utcnow().isoformat() + "Z",
                "survey_types": [
                    {
                        "id": "full-regional",
                        "name": "Full Regional Review",
                        "icon": "fa-sitemap",
                        "color": "#3b82f6",
                        "description": "Comprehensive review covering all aspects",
                        "is_active": True
                    },
                    # ... other survey types
                ]
            }
            with open(self.survey_types_file, 'w') as f:
                json.dump(default_data, f, indent=2)
    
    def get_all_survey_types(self):
        """Get all active survey types"""
        with open(self.survey_types_file, 'r') as f:
            data = json.load(f)
        return [st for st in data['survey_types'] if st.get('is_active', True)]
    
    def get_survey_type_by_id(self, survey_type_id):
        """Get specific survey type by ID"""
        survey_types = self.get_all_survey_types()
        return next((st for st in survey_types if st['id'] == survey_type_id), None)
    
    def validate_survey_type(self, survey_type_id):
        """Check if survey type ID is valid"""
        return self.get_survey_type_by_id(survey_type_id) is not None
```

### Question Filter Service

**File**: `services/question_filter.py` (new)

```python
class QuestionFilterService:
    def __init__(self, question_manager, survey_type_service):
        self.question_manager = question_manager
        self.survey_type_service = survey_type_service
    
    def filter_by_survey_type(self, questions, survey_type_id):
        """
        Filter questions by survey type
        
        Rules:
        - If question has empty survey_types array, include in all types
        - If question has survey_types array, check if survey_type_id is in it
        - If question doesn't have survey_types field, include in all types (backward compatibility)
        """
        filtered = []
        for question in questions:
            survey_types = question.get('survey_types', [])
            
            # Empty array or missing field = belongs to all types
            if not survey_types:
                filtered.append(question)
            # Check if survey type is in the list
            elif survey_type_id in survey_types:
                filtered.append(question)
        
        return filtered
    
    def get_questions_for_survey(self, community, survey_type_id):
        """Get questions for a specific community and survey type"""
        # Get all questions for community
        all_questions = self.question_manager.get_questions_for_community(community)
        
        # Filter by survey type
        filtered_questions = self.filter_by_survey_type(all_questions, survey_type_id)
        
        return filtered_questions
```

---

## Database/Storage Changes

### New File: `survey_types.json`
**Location**: `app_mantenimiento/data/survey_types.json`  
**Purpose**: Store survey type definitions  
**Created**: Automatically on first run

### Modified File: `questions.json`
**Changes**: Add `survey_types` field to each question  
**Migration**: Field is optional, defaults to empty array

### Modified File: `inspections.json`
**Changes**: Add `survey_type` field to each submission  
**Migration**: Field is optional, defaults to null

---

## Security Considerations

### 1. Survey Type Validation
- Validate survey type on server side before storing
- Reject invalid survey type IDs
- Prevent survey type tampering via session manipulation

### 2. Authorization
- Maintain existing role-based access control
- Survey type selection available to all authenticated users
- Survey type assignment in Question Manager restricted to admins

### 3. Data Integrity
- Validate survey type exists before filtering questions
- Handle missing survey type gracefully
- Maintain data consistency during migration

---

## Performance Optimization

### 1. Caching
- Cache survey type list in memory (rarely changes)
- Cache question-survey type mappings
- Invalidate cache on question updates

### 2. Query Optimization
- Filter questions by survey type in memory (JSON file storage)
- Consider indexing if migrating to database
- Minimize API calls by bundling survey type data

### 3. Frontend Optimization
- Lazy load survey type icons
- Minimize re-renders when filtering
- Use CSS for visual feedback (no JavaScript animations)

---

## Error Handling

### 1. Missing Survey Type
**Scenario**: User tries to access questionnaire without selecting survey type  
**Handling**: Redirect to survey type selection screen

### 2. Invalid Survey Type
**Scenario**: Invalid survey type ID in session or API request  
**Handling**: Clear session, redirect to survey type selection, log error

### 3. No Questions for Survey Type
**Scenario**: Selected survey type has no questions for user's community  
**Handling**: Display friendly message, allow user to go back and select different type

### 4. Session Timeout
**Scenario**: Survey type selection expires before submission  
**Handling**: Prompt user to reselect survey type, preserve form data if possible

---

## Testing Strategy

### 1. Unit Tests
- Survey type validation
- Question filtering logic
- Session management
- Data migration

### 2. Integration Tests
- Survey type selection flow
- Question filtering with survey types
- Inspection submission with survey type
- Dashboard display of survey types

### 3. UI Tests
- Survey type selection screen
- Question Manager survey type assignment
- Dashboard survey type filters
- Mobile responsiveness

### 4. End-to-End Tests
- Complete inspection flow with survey type
- Admin assigns survey types to questions
- User selects survey type and completes inspection
- Dashboard displays survey type correctly

---

## Deployment Plan

### Phase 1: Data Model (Week 1)
1. Create `survey_types.json` with default data
2. Add `survey_types` field to questions schema
3. Add `survey_type` field to inspections schema
4. Deploy backend changes
5. Test backward compatibility

### Phase 2: Backend Services (Week 2)
1. Implement SurveyTypeService
2. Implement QuestionFilterService
3. Add new API endpoints
4. Modify existing endpoints
5. Add validation and error handling
6. Deploy and test

### Phase 3: Frontend - Survey Selection (Week 3)
1. Create survey type selection screen
2. Implement routing changes
3. Add session management
4. Test mobile responsiveness
5. Deploy and test

### Phase 4: Frontend - Question Manager (Week 4)
1. Add survey type multi-select to question form
2. Add survey type tags to question cards
3. Add survey type filter
4. Test admin workflow
5. Deploy and test

### Phase 5: Frontend - Dashboard (Week 5)
1. Add survey type to inspection modal
2. Add survey type filters
3. Add survey type badges
4. Test reporting features
5. Deploy and test

### Phase 6: Testing & Documentation (Week 6)
1. Comprehensive testing
2. User acceptance testing
3. Documentation
4. Training materials
5. Final deployment

---

## Rollback Plan

### If Issues Arise:
1. **Data Issues**: Restore from backup, survey_types field is optional
2. **Frontend Issues**: Revert frontend changes, backend remains compatible
3. **Backend Issues**: Revert API changes, frontend falls back to legacy behavior
4. **Complete Rollback**: Remove survey_types.json, revert all changes, existing data unaffected

### Rollback Safety:
- All new fields are optional
- Backward compatibility maintained
- No data loss on rollback
- Gradual rollout allows partial rollback

---

## Future Enhancements

### 1. Custom Survey Types
- Allow admins to create custom survey types
- Survey type templates
- Survey type cloning

### 2. Survey Type Analytics
- Reports by survey type
- Trends over time
- Comparison between survey types

### 3. Survey Type Scheduling
- Schedule inspections by survey type
- Recurring survey type assignments
- Calendar integration

### 4. Survey Type Permissions
- Role-based survey type access
- Community-specific survey types
- User-specific survey type restrictions

### 5. Survey Type Workflows
- Multi-step survey types
- Conditional questions based on survey type
- Survey type dependencies

---

## Technical Debt

### Known Limitations:
1. JSON file storage (not scalable for large datasets)
2. No survey type versioning
3. No survey type audit trail
4. Limited survey type metadata

### Future Improvements:
1. Migrate to database (PostgreSQL/MySQL)
2. Add survey type versioning
3. Add audit logging
4. Expand survey type metadata
5. Add survey type templates

---

## Dependencies

### Python Packages (Existing):
- Flask
- Werkzeug
- JSON (standard library)

### Frontend Libraries (Existing):
- Font Awesome (icons)
- Vanilla JavaScript (no new dependencies)

### New Files:
- `survey_types.json`
- `services/survey_type_service.py`
- `services/question_filter.py`
- `templates/select_survey_type.html`

---

## Monitoring & Logging

### Metrics to Track:
1. Survey type selection rate
2. Questions per survey type
3. Inspections per survey type
4. Survey type selection time
5. Error rates by survey type

### Logging:
- Survey type selection events
- Survey type validation failures
- Question filtering operations
- Survey type assignment changes

---

## Documentation Requirements

### User Documentation:
1. How to select a survey type
2. What each survey type means
3. How to complete an inspection

### Admin Documentation:
1. How to assign survey types to questions
2. How to manage survey types
3. Best practices for survey type organization

### Developer Documentation:
1. API documentation
2. Data model documentation
3. Service layer documentation
4. Testing documentation

---

## Success Criteria

### Technical Success:
- ✅ All tests pass
- ✅ No performance degradation
- ✅ Backward compatibility maintained
- ✅ Zero data loss

### Business Success:
- ✅ 90% adoption rate within 30 days
- ✅ User satisfaction >4 stars
- ✅ <1% error rate
- ✅ Admin efficiency improved

---

## Sign-Off

**Technical Lead**: _________________  
**Date**: _________________

**QA Lead**: _________________  
**Date**: _________________

**Product Owner**: _________________  
**Date**: _________________
