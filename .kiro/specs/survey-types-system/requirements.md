# Survey Types System - Requirements

## Overview
Implement a survey type selection system that allows users to choose from different types of inspections/visits before starting a questionnaire. Each survey type will have its own set of questions tailored to that specific type of review.

---

## R1: Survey Type Selection Screen
**Priority**: High  
**Category**: User Interface

### Description
Create a survey type selection screen that appears after login and before the questionnaire form. Users must select one survey type to proceed with the inspection.

### Acceptance Criteria
- Screen displays after user logs in and clicks "Start New Visit"
- Shows title: "What type of visit are you conducting?"
- Displays 6 survey type options with icons and labels
- Only one survey type can be selected at a time (radio button behavior)
- "Continue" button is enabled only when a survey type is selected
- Mobile-responsive design matching the provided reference image

### Survey Types
1. **Full Regional Review** - Icon: Organization chart (🏢)
2. **Operational Review** - Icon: Magnifying glass with checkmark (🔍)
3. **Sales & Marketing** - Icon: Chart/presentation (📊)
4. **Clinical Review** - Icon: Medical cross (⚕️)
5. **Dining Review** - Icon: Utensils (🍴)
6. **Life Safety Review** - Icon: Warning triangle (⚠️)

---

## R2: Survey Type Data Model
**Priority**: High  
**Category**: Data Structure

### Description
Extend the data model to support survey types for questions and inspection submissions.

### Acceptance Criteria
- Questions have a `survey_types` field (array of survey type IDs)
- Inspection submissions have a `survey_type` field (single survey type ID)
- Survey type IDs are standardized: `full-regional`, `operational`, `sales-marketing`, `clinical`, `dining`, `life-safety`
- Backward compatibility: existing questions without survey_types are treated as belonging to all types
- Existing inspection submissions without survey_type continue to work

### Data Structure
```json
{
  "survey_types": [
    {
      "id": "full-regional",
      "name": "Full Regional Review",
      "icon": "fa-sitemap",
      "description": "Comprehensive review covering all aspects"
    },
    {
      "id": "operational",
      "name": "Operational Review",
      "icon": "fa-search-plus",
      "description": "Focus on operational procedures and efficiency"
    },
    {
      "id": "sales-marketing",
      "name": "Sales & Marketing",
      "icon": "fa-chart-line",
      "description": "Review of sales processes and marketing materials"
    },
    {
      "id": "clinical",
      "name": "Clinical Review",
      "icon": "fa-user-md",
      "description": "Medical and clinical standards review"
    },
    {
      "id": "dining",
      "name": "Dining Review",
      "icon": "fa-utensils",
      "description": "Food service and dining area inspection"
    },
    {
      "id": "life-safety",
      "name": "Life Safety Review",
      "icon": "fa-exclamation-triangle",
      "description": "Safety equipment and emergency procedures"
    }
  ]
}
```

---

## R3: Question Filtering by Survey Type
**Priority**: High  
**Category**: Business Logic

### Description
Filter questions based on the selected survey type when loading the questionnaire form.

### Acceptance Criteria
- API endpoint `/api/questions` accepts `survey_type` query parameter
- Returns only questions assigned to the specified survey type
- Questions without survey_types assignment are included in all survey types (backward compatibility)
- Questions can belong to multiple survey types
- Filtering works for all 38 communities

---

## R4: Survey Type Storage in Submissions
**Priority**: High  
**Category**: Data Persistence

### Description
Store the selected survey type with each inspection submission.

### Acceptance Criteria
- Inspection submission includes `survey_type` field
- Survey type is validated against the list of valid types
- Survey type is stored in `inspections.json`
- Survey type is returned when fetching inspection details
- Existing submissions without survey_type continue to work

---

## R5: Question Manager - Survey Type Assignment
**Priority**: High  
**Category**: Admin Interface

### Description
Allow administrators to assign questions to one or more survey types in the Question Manager.

### Acceptance Criteria
- Question creation form includes survey type selection (multi-select)
- Question edit form shows current survey type assignments
- Survey types are displayed as tags/badges on question cards
- Can filter questions by survey type in Question Manager
- Default behavior: if no survey types selected, question belongs to all types

### UI Elements
- Multi-select dropdown or checkbox group for survey types
- Visual tags showing assigned survey types (color-coded)
- Filter dropdown to view questions by survey type
- "All Types" option to show questions available in all surveys

---

## R6: Dashboard - Survey Type Display
**Priority**: Medium  
**Category**: Reporting

### Description
Display survey type information in the dashboard and inspection details modal.

### Acceptance Criteria
- Inspection details modal shows survey type badge
- Survey type is displayed in metadata section
- Survey type badge uses appropriate icon and color
- Community cards can optionally show survey type of last inspection
- "My Visits" view shows survey type for each inspection

### Visual Design
- Badge format: `[Icon] Survey Type Name`
- Color coding:
  - Full Regional: Blue (#3b82f6)
  - Operational: Green (#10b981)
  - Sales & Marketing: Purple (#8b5cf6)
  - Clinical: Red (#ef4444)
  - Dining: Orange (#f59e0b)
  - Life Safety: Yellow (#eab308)

---

## R7: Survey Type Filtering in Dashboard
**Priority**: Low  
**Category**: Reporting

### Description
Allow users to filter inspections by survey type in the dashboard.

### Acceptance Criteria
- Add survey type filter buttons to filter section
- Filter works in "My Visits" view
- Filter works in "Reports" view
- Can combine survey type filter with condition filters
- Filter state is preserved when switching views

---

## R8: Mobile UI - Survey Type Selection
**Priority**: High  
**Category**: User Interface

### Description
Implement mobile-optimized survey type selection screen matching the reference design.

### Acceptance Criteria
- Full-screen modal or dedicated page
- Large touch-friendly buttons (minimum 44px height)
- Clear visual feedback for selected option
- Back button to return to previous screen
- Smooth transitions and animations
- Works on iOS and Android devices
- Responsive design for tablets

### Design Specifications
- Background: White
- Selected state: Filled radio button (black)
- Unselected state: Empty radio button (gray)
- Button hover: Light gray background
- Continue button: Black background, white text
- Font: System font, clean and readable

---

## R9: Routing and Navigation
**Priority**: High  
**Category**: Application Flow

### Description
Update application routing to include survey type selection in the inspection flow.

### Acceptance Criteria
- New route: `/select-survey-type` or `/start-visit`
- "Start New Visit" button redirects to survey type selection
- After selecting survey type, redirect to `/reporte` with survey_type parameter
- Survey type is passed to questionnaire form
- Back button on questionnaire returns to survey type selection
- Survey type selection is required (cannot skip)

### Flow
```
Login → Dashboard → "Start New Visit" → Survey Type Selection → Questionnaire → Submit → Dashboard
```

---

## R10: Session Management
**Priority**: Medium  
**Category**: State Management

### Description
Manage survey type selection in user session to prevent data loss.

### Acceptance Criteria
- Selected survey type is stored in session
- Survey type persists if user navigates away and returns
- Survey type is cleared after successful submission
- Survey type is cleared on logout
- Session timeout does not lose survey type selection

---

## R11: Validation and Error Handling
**Priority**: Medium  
**Category**: Quality Assurance

### Description
Implement validation and error handling for survey type functionality.

### Acceptance Criteria
- Validate survey type on submission (must be one of the 6 valid types)
- Handle case where no questions exist for selected survey type
- Display user-friendly error messages
- Prevent submission without survey type selection
- Log errors for debugging

### Error Messages
- "Please select a survey type to continue"
- "No questions available for this survey type. Please contact administrator."
- "Invalid survey type selected. Please try again."

---

## R12: Backward Compatibility
**Priority**: High  
**Category**: Data Migration

### Description
Ensure existing data and functionality continue to work after implementing survey types.

### Acceptance Criteria
- Existing questions without survey_types field work correctly
- Existing inspections without survey_type field display properly
- Dashboard shows existing inspections without errors
- Question Manager displays existing questions
- No data loss during migration
- Gradual migration path: admins can assign survey types over time

### Migration Strategy
- Add survey_types field to questions.json schema (optional)
- Add survey_type field to inspections.json schema (optional)
- Treat null/undefined survey_types as "all types"
- Treat null/undefined survey_type in submissions as "legacy" or "unspecified"

---

## R13: Performance Optimization
**Priority**: Low  
**Category**: Performance

### Description
Ensure survey type functionality does not degrade application performance.

### Acceptance Criteria
- Question filtering by survey type is fast (<100ms)
- Survey type selection screen loads quickly (<500ms)
- No noticeable delay when switching between survey types
- Efficient data structure for survey type lookups
- Minimal impact on existing API response times

---

## R14: Documentation
**Priority**: Medium  
**Category**: Documentation

### Description
Provide comprehensive documentation for survey types feature.

### Acceptance Criteria
- User guide for selecting survey types
- Admin guide for assigning questions to survey types
- API documentation for survey type endpoints
- Data model documentation
- Migration guide for existing installations

---

## R15: Testing Requirements
**Priority**: High  
**Category**: Quality Assurance

### Description
Comprehensive testing coverage for survey types functionality.

### Acceptance Criteria
- Unit tests for survey type validation
- Integration tests for question filtering
- UI tests for survey type selection screen
- End-to-end tests for complete inspection flow
- Backward compatibility tests
- Mobile device testing (iOS and Android)
- Browser compatibility testing

### Test Scenarios
1. Select each survey type and verify correct questions load
2. Submit inspection with survey type and verify storage
3. View inspection details and verify survey type display
4. Filter inspections by survey type
5. Assign questions to multiple survey types
6. Test with existing data (no survey types assigned)
7. Test session persistence
8. Test error handling

---

## Non-Functional Requirements

### NFR1: Usability
- Survey type selection should be intuitive and require no training
- Icons should be universally recognizable
- Mobile UI should be thumb-friendly

### NFR2: Accessibility
- Screen reader support for survey type selection
- Keyboard navigation support
- WCAG 2.1 AA compliance
- High contrast mode support

### NFR3: Security
- Survey type validation on server side
- Prevent survey type tampering
- Maintain existing authentication and authorization

### NFR4: Scalability
- Support for adding new survey types in the future
- Support for 100+ questions per survey type
- Support for 1000+ inspections per survey type

### NFR5: Maintainability
- Clean separation of survey type logic
- Reusable components
- Clear code documentation
- Easy to add new survey types

---

## Dependencies

### Internal Dependencies
- Existing authentication system
- Question Manager functionality
- Inspection submission system
- Dashboard and reporting

### External Dependencies
- Font Awesome icons (for survey type icons)
- Flask backend
- JSON file storage system

---

## Assumptions

1. Survey types are predefined and fixed (6 types)
2. Users can only select one survey type per inspection
3. Questions can belong to multiple survey types
4. Survey types do not affect scoring or action items calculation
5. All communities use the same survey types
6. Survey type selection is mandatory (cannot be skipped)

---

## Out of Scope

1. Custom survey types created by users
2. Survey type templates or presets
3. Survey type scheduling or calendar integration
4. Survey type-specific scoring algorithms
5. Survey type permissions (all users can access all types)
6. Survey type analytics or reporting dashboards
7. Multi-language support for survey type names
8. Survey type versioning or history

---

## Success Metrics

1. **Adoption Rate**: 90% of inspections include a survey type within 30 days
2. **User Satisfaction**: Survey type selection rated 4+ stars by users
3. **Performance**: Survey type selection adds <1 second to inspection flow
4. **Error Rate**: <1% of submissions fail due to survey type issues
5. **Admin Efficiency**: Admins can assign survey types to questions in <30 seconds

---

## Risks and Mitigation

### Risk 1: User Confusion
**Impact**: Medium  
**Probability**: Low  
**Mitigation**: Clear UI design, tooltips, user training

### Risk 2: Data Migration Issues
**Impact**: High  
**Probability**: Low  
**Mitigation**: Thorough testing, backward compatibility, gradual rollout

### Risk 3: Performance Degradation
**Impact**: Medium  
**Probability**: Low  
**Mitigation**: Performance testing, optimization, caching

### Risk 4: Incomplete Question Assignment
**Impact**: Medium  
**Probability**: Medium  
**Mitigation**: Default to "all types", admin notifications, bulk assignment tools

---

## Implementation Priority

### Phase 1: Core Functionality (High Priority)
- R1: Survey Type Selection Screen
- R2: Survey Type Data Model
- R3: Question Filtering by Survey Type
- R4: Survey Type Storage in Submissions
- R9: Routing and Navigation

### Phase 2: Admin Tools (High Priority)
- R5: Question Manager - Survey Type Assignment
- R12: Backward Compatibility

### Phase 3: Reporting (Medium Priority)
- R6: Dashboard - Survey Type Display
- R10: Session Management
- R11: Validation and Error Handling

### Phase 4: Enhancements (Low Priority)
- R7: Survey Type Filtering in Dashboard
- R13: Performance Optimization
- R14: Documentation
- R15: Testing Requirements

---

## Approval

**Product Owner**: _________________  
**Date**: _________________

**Technical Lead**: _________________  
**Date**: _________________

**QA Lead**: _________________  
**Date**: _________________
