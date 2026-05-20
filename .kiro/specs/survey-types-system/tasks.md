# Survey Types System - Implementation Tasks

## Task 1: Create Survey Types Data File
**Status**: not_started  
**Priority**: High  
**Estimated Time**: 1 hour

### Description
Create the `survey_types.json` file with the 6 predefined survey types and their metadata.

### Subtasks
- 1.1: Create `data/survey_types.json` file
- 1.2: Define schema with version, last_modified, and survey_types array
- 1.3: Add all 6 survey types with id, name, icon, color, description, is_active
- 1.4: Validate JSON structure
- 1.5: Add file to version control

### Acceptance Criteria
- File exists at `app_mantenimiento/data/survey_types.json`
- Contains all 6 survey types with correct metadata
- JSON is valid and properly formatted
- Icons use Font Awesome class names
- Colors are valid hex codes

### Files to Create
- `app_mantenimiento/data/survey_types.json`

---

## Task 2: Create Survey Type Service
**Status**: not_started  
**Priority**: High  
**Estimated Time**: 2 hours  
**Dependencies**: Task 1

### Description
Implement the SurveyTypeService class to manage survey type data and operations.

### Subtasks
- 2.1: Create `services/survey_type_service.py` file
- 2.2: Implement `__init__` method with file path parameter
- 2.3: Implement `_ensure_file_exists` method
- 2.4: Implement `get_all_survey_types` method
- 2.5: Implement `get_survey_type_by_id` method
- 2.6: Implement `validate_survey_type` method
- 2.7: Add error handling for file operations
- 2.8: Add docstrings and type hints

### Acceptance Criteria
- Service class is properly structured
- All methods work correctly
- File is created automatically if missing
- Returns only active survey types
- Validation works for valid and invalid IDs
- Error handling is robust

### Files to Create
- `app_mantenimiento/services/survey_type_service.py`

---

## Task 3: Create Question Filter Service
**Status**: not_started  
**Priority**: High  
**Estimated Time**: 2 hours  
**Dependencies**: Task 2

### Description
Implement the QuestionFilterService class to filter questions by survey type.

### Subtasks
- 3.1: Create `services/question_filter.py` file
- 3.2: Implement `__init__` with dependencies
- 3.3: Implement `filter_by_survey_type` method
- 3.4: Implement `get_questions_for_survey` method
- 3.5: Handle backward compatibility (empty survey_types array)
- 3.6: Add unit tests
- 3.7: Add docstrings and type hints

### Acceptance Criteria
- Filtering logic works correctly
- Questions without survey_types are included in all types
- Questions with survey_types are filtered correctly
- Backward compatibility is maintained
- Unit tests pass

### Files to Create
- `app_mantenimiento/services/question_filter.py`
- `app_mantenimiento/services/test_question_filter.py`

---

## Task 4: Add Survey Type API Endpoints
**Status**: not_started  
**Priority**: High  
**Estimated Time**: 3 hours  
**Dependencies**: Task 2, Task 3

### Description
Add new API endpoints for survey type operations and modify existing endpoints.

### Subtasks
- 4.1: Add GET `/api/survey-types` endpoint
- 4.2: Add POST `/api/select-survey-type` endpoint
- 4.3: Modify GET `/api/questions` to accept survey_type parameter
- 4.4: Modify POST `/api/inspections` to include survey_type
- 4.5: Modify GET `/api/inspections` to filter by survey_type
- 4.6: Add input validation and sanitization
- 4.7: Add error handling
- 4.8: Update API documentation

### Acceptance Criteria
- All endpoints work correctly
- Input validation prevents invalid data
- Error messages are user-friendly
- Session management works properly
- Backward compatibility is maintained

### Files to Modify
- `app_mantenimiento/app.py`

---

## Task 5: Update Questions Data Model
**Status**: not_started  
**Priority**: High  
**Estimated Time**: 1 hour  
**Dependencies**: Task 1

### Description
Add survey_types field to questions schema and update QuestionManager service.

### Subtasks
- 5.1: Update QuestionManager.create_question to accept survey_types parameter
- 5.2: Update QuestionManager.update_question to handle survey_types
- 5.3: Add survey_types field to question creation
- 5.4: Handle empty survey_types array (all types)
- 5.5: Update validation logic
- 5.6: Test with existing questions

### Acceptance Criteria
- Questions can have survey_types array
- Empty array means all types
- Existing questions without field work correctly
- Create and update operations work
- Validation prevents invalid survey type IDs

### Files to Modify
- `app_mantenimiento/services/question_manager.py`

---

## Task 6: Update Inspections Data Model
**Status**: not_started  
**Priority**: High  
**Estimated Time**: 1 hour  
**Dependencies**: Task 4

### Description
Add survey_type field to inspection submissions schema.

### Subtasks
- 6.1: Update InspectionService.create_submission to accept survey_type
- 6.2: Add survey_type field to submission data
- 6.3: Validate survey_type before storing
- 6.4: Handle null survey_type (legacy submissions)
- 6.5: Update get_submissions methods to return survey_type
- 6.6: Test with existing submissions

### Acceptance Criteria
- Submissions include survey_type field
- Validation works correctly
- Existing submissions without field work
- Survey type is stored and retrieved correctly

### Files to Modify
- `app_mantenimiento/services/inspection_service.py`

---

## Task 7: Create Survey Type Selection Screen
**Status**: not_started  
**Priority**: High  
**Estimated Time**: 4 hours  
**Dependencies**: Task 4

### Description
Create the mobile-optimized survey type selection interface.

### Subtasks
- 7.1: Create `templates/select_survey_type.html` file
- 7.2: Add HTML structure with header and form
- 7.3: Create survey type option cards with icons
- 7.4: Implement radio button selection
- 7.5: Add Continue button with disabled state
- 7.6: Style for mobile (responsive design)
- 7.7: Add JavaScript for selection handling
- 7.8: Add form submission logic
- 7.9: Add back button navigation
- 7.10: Test on mobile devices

### Acceptance Criteria
- Screen matches reference design
- Touch targets are minimum 44px
- Only one survey type can be selected
- Continue button enables on selection
- Form submits to API correctly
- Mobile responsive
- Works on iOS and Android

### Files to Create
- `app_mantenimiento/templates/select_survey_type.html`

---

## Task 8: Update Application Routing
**Status**: not_started  
**Priority**: High  
**Estimated Time**: 2 hours  
**Dependencies**: Task 7

### Description
Add new routes and update existing routes for survey type flow.

### Subtasks
- 8.1: Add GET `/select-survey-type` route
- 8.2: Update `/reporte` route to check for survey type in session
- 8.3: Update "Start New Visit" button to redirect to survey type selection
- 8.4: Add redirect logic if survey type not selected
- 8.5: Clear survey type from session after submission
- 8.6: Add back button handling
- 8.7: Test complete flow

### Acceptance Criteria
- New route works correctly
- Survey type selection is required
- Redirects work properly
- Session management is correct
- Back navigation works
- Flow is intuitive

### Files to Modify
- `app_mantenimiento/app.py`
- `app_mantenimiento/templates/dashboard.html`

---

## Task 9: Update Question Manager UI
**Status**: not_started  
**Priority**: High  
**Estimated Time**: 4 hours  
**Dependencies**: Task 5

### Description
Add survey type assignment functionality to Question Manager.

### Subtasks
- 9.1: Add survey type multi-select to question creation form
- 9.2: Add survey type multi-select to question edit form
- 9.3: Display survey type tags on question cards
- 9.4: Add survey type filter dropdown
- 9.5: Implement filter functionality
- 9.6: Add "All Types" default behavior
- 9.7: Style survey type badges with colors
- 9.8: Add tooltips/help text
- 9.9: Test admin workflow

### Acceptance Criteria
- Multi-select works correctly
- Tags display with correct colors
- Filter works properly
- Empty selection means all types
- UI is intuitive
- Changes save correctly

### Files to Modify
- `app_mantenimiento/templates/question_manager.html`

---

## Task 10: Update Dashboard - Inspection Modal
**Status**: not_started  
**Priority**: Medium  
**Estimated Time**: 2 hours  
**Dependencies**: Task 6

### Description
Display survey type information in the inspection details modal.

### Subtasks
- 10.1: Add survey type to metadata section
- 10.2: Create survey type badge component
- 10.3: Style badge with icon and color
- 10.4: Handle null survey type (legacy)
- 10.5: Update displayInspectionModal function
- 10.6: Test with different survey types

### Acceptance Criteria
- Survey type displays in modal
- Badge shows correct icon and color
- Legacy inspections show "Unspecified"
- Styling matches design
- Works for all survey types

### Files to Modify
- `app_mantenimiento/templates/dashboard.html`

---

## Task 11: Update Dashboard - Survey Type Filters
**Status**: not_started  
**Priority**: Low  
**Estimated Time**: 3 hours  
**Dependencies**: Task 10

### Description
Add survey type filtering to dashboard views.

### Subtasks
- 11.1: Add survey type filter buttons to filter section
- 11.2: Implement filterBySurveyType function
- 11.3: Update renderCards to apply survey type filter
- 11.4: Update renderMyVisits to apply survey type filter
- 11.5: Combine with existing condition filters
- 11.6: Add "All Survey Types" option
- 11.7: Style filter buttons
- 11.8: Test filtering logic

### Acceptance Criteria
- Filter buttons work correctly
- Can filter by survey type
- Can combine with condition filters
- "All" option shows all inspections
- Filter state persists across views
- UI is intuitive

### Files to Modify
- `app_mantenimiento/templates/dashboard.html`

---

## Task 12: Update Questionnaire Form
**Status**: not_started  
**Priority**: High  
**Estimated Time**: 2 hours  
**Dependencies**: Task 8

### Description
Update questionnaire form to load questions based on selected survey type.

### Subtasks
- 12.1: Get survey type from session in backend
- 12.2: Pass survey type to template
- 12.3: Update question loading to filter by survey type
- 12.4: Display survey type indicator on form
- 12.5: Handle case where no questions exist
- 12.6: Test with different survey types

### Acceptance Criteria
- Questions are filtered by survey type
- Survey type is visible on form
- Error handling for no questions
- Form works correctly
- Submission includes survey type

### Files to Modify
- `app_mantenimiento/app.py`
- `app_mantenimiento/templates/reporte.html`

---

## Task 13: Add Session Management
**Status**: not_started  
**Priority**: Medium  
**Estimated Time**: 2 hours  
**Dependencies**: Task 8

### Description
Implement robust session management for survey type selection.

### Subtasks
- 13.1: Store survey type in session on selection
- 13.2: Add timestamp for session expiry
- 13.3: Clear survey type after submission
- 13.4: Clear survey type on logout
- 13.5: Handle session timeout
- 13.6: Add session validation
- 13.7: Test session persistence

### Acceptance Criteria
- Survey type persists in session
- Session clears appropriately
- Timeout handling works
- No data loss on navigation
- Session is secure

### Files to Modify
- `app_mantenimiento/app.py`

---

## Task 14: Add Input Validation
**Status**: not_started  
**Priority**: High  
**Estimated Time**: 2 hours  
**Dependencies**: Task 4

### Description
Implement comprehensive input validation for survey type operations.

### Subtasks
- 14.1: Add survey type validation in InputSanitizer
- 14.2: Validate survey type on selection
- 14.3: Validate survey type on submission
- 14.4: Add error messages for invalid types
- 14.5: Handle edge cases
- 14.6: Add unit tests for validation
- 14.7: Test with invalid inputs

### Acceptance Criteria
- All inputs are validated
- Invalid survey types are rejected
- Error messages are clear
- Edge cases are handled
- Unit tests pass

### Files to Modify
- `app_mantenimiento/services/input_sanitizer.py`

---

## Task 15: Add Error Handling
**Status**: not_started  
**Priority**: Medium  
**Estimated Time**: 2 hours  
**Dependencies**: Task 14

### Description
Implement comprehensive error handling for survey type functionality.

### Subtasks
- 15.1: Handle missing survey type in session
- 15.2: Handle invalid survey type ID
- 15.3: Handle no questions for survey type
- 15.4: Handle file read/write errors
- 15.5: Add user-friendly error messages
- 15.6: Add error logging
- 15.7: Test error scenarios

### Acceptance Criteria
- All error cases are handled
- Error messages are user-friendly
- Errors are logged properly
- Application doesn't crash
- Users can recover from errors

### Files to Modify
- `app_mantenimiento/app.py`
- `app_mantenimiento/services/survey_type_service.py`
- `app_mantenimiento/services/question_filter.py`

---

## Task 16: Write Unit Tests
**Status**: not_started  
**Priority**: High  
**Estimated Time**: 4 hours  
**Dependencies**: Task 2, Task 3, Task 5, Task 6

### Description
Write comprehensive unit tests for all new services and functions.

### Subtasks
- 16.1: Test SurveyTypeService methods
- 16.2: Test QuestionFilterService methods
- 16.3: Test survey type validation
- 16.4: Test question filtering logic
- 16.5: Test backward compatibility
- 16.6: Test error handling
- 16.7: Achieve >80% code coverage

### Acceptance Criteria
- All unit tests pass
- Code coverage >80%
- Edge cases are tested
- Backward compatibility is verified
- Tests are maintainable

### Files to Create
- `app_mantenimiento/services/test_survey_type_service.py`
- `app_mantenimiento/services/test_question_filter.py`

---

## Task 17: Write Integration Tests
**Status**: not_started  
**Priority**: Medium  
**Estimated Time**: 4 hours  
**Dependencies**: Task 4, Task 8

### Description
Write integration tests for API endpoints and complete flows.

### Subtasks
- 17.1: Test GET `/api/survey-types` endpoint
- 17.2: Test POST `/api/select-survey-type` endpoint
- 17.3: Test GET `/api/questions` with survey_type parameter
- 17.4: Test POST `/api/inspections` with survey_type
- 17.5: Test complete inspection flow
- 17.6: Test session management
- 17.7: Test error scenarios

### Acceptance Criteria
- All integration tests pass
- API endpoints work correctly
- Complete flow works end-to-end
- Error handling is verified
- Tests are reliable

### Files to Create
- `app_mantenimiento/test_survey_type_integration.py`

---

## Task 18: Write UI Tests
**Status**: not_started  
**Priority**: Low  
**Estimated Time**: 3 hours  
**Dependencies**: Task 7, Task 9, Task 10

### Description
Write UI tests for survey type selection and display.

### Subtasks
- 18.1: Test survey type selection screen
- 18.2: Test radio button selection
- 18.3: Test Continue button enable/disable
- 18.4: Test form submission
- 18.5: Test Question Manager UI
- 18.6: Test Dashboard modal display
- 18.7: Test mobile responsiveness

### Acceptance Criteria
- All UI tests pass
- User interactions work correctly
- Mobile responsiveness is verified
- Tests are maintainable

### Files to Create
- `app_mantenimiento/test_survey_type_ui.py`

---

## Task 19: Test Backward Compatibility
**Status**: not_started  
**Priority**: High  
**Estimated Time**: 2 hours  
**Dependencies**: Task 5, Task 6

### Description
Verify that existing data and functionality work correctly after changes.

### Subtasks
- 19.1: Test existing questions without survey_types field
- 19.2: Test existing inspections without survey_type field
- 19.3: Test Question Manager with existing questions
- 19.4: Test Dashboard with existing inspections
- 19.5: Verify no data loss
- 19.6: Test gradual migration path

### Acceptance Criteria
- Existing questions work correctly
- Existing inspections display properly
- No data is lost
- No errors with legacy data
- Migration path is clear

### Files to Test
- All existing functionality

---

## Task 20: Mobile Device Testing
**Status**: not_started  
**Priority**: High  
**Estimated Time**: 3 hours  
**Dependencies**: Task 7

### Description
Test survey type selection on actual mobile devices.

### Subtasks
- 20.1: Test on iPhone (iOS)
- 20.2: Test on Android phone
- 20.3: Test on iPad (tablet)
- 20.4: Test on Android tablet
- 20.5: Test touch interactions
- 20.6: Test different screen sizes
- 20.7: Test landscape orientation
- 20.8: Fix any mobile-specific issues

### Acceptance Criteria
- Works on iOS devices
- Works on Android devices
- Touch targets are adequate
- Responsive design works
- No mobile-specific bugs

### Devices to Test
- iPhone 12/13/14
- Samsung Galaxy S21/S22
- iPad Pro
- Samsung Galaxy Tab

---

## Task 21: Browser Compatibility Testing
**Status**: not_started  
**Priority**: Medium  
**Estimated Time**: 2 hours  
**Dependencies**: Task 7, Task 9, Task 10

### Description
Test survey type functionality across different browsers.

### Subtasks
- 21.1: Test on Chrome
- 21.2: Test on Firefox
- 21.3: Test on Safari
- 21.4: Test on Edge
- 21.5: Test on mobile browsers
- 21.6: Fix browser-specific issues

### Acceptance Criteria
- Works on all major browsers
- No browser-specific bugs
- Consistent appearance
- All features work

### Browsers to Test
- Chrome (latest)
- Firefox (latest)
- Safari (latest)
- Edge (latest)

---

## Task 22: Performance Testing
**Status**: not_started  
**Priority**: Low  
**Estimated Time**: 2 hours  
**Dependencies**: Task 4, Task 7

### Description
Verify that survey type functionality doesn't degrade performance.

### Subtasks
- 22.1: Measure survey type selection load time
- 22.2: Measure question filtering performance
- 22.3: Measure API response times
- 22.4: Test with large datasets
- 22.5: Identify bottlenecks
- 22.6: Optimize if necessary

### Acceptance Criteria
- Survey type selection loads <500ms
- Question filtering <100ms
- API responses <200ms
- No noticeable delays
- Performance is acceptable

### Tools
- Browser DevTools
- Python profiler
- Load testing tools

---

## Task 23: Create User Documentation
**Status**: not_started  
**Priority**: Medium  
**Estimated Time**: 3 hours  
**Dependencies**: Task 20

### Description
Create user-facing documentation for survey type feature.

### Subtasks
- 23.1: Write user guide for selecting survey types
- 23.2: Document each survey type and its purpose
- 23.3: Create screenshots/videos
- 23.4: Write FAQ section
- 23.5: Create quick start guide
- 23.6: Review and edit

### Acceptance Criteria
- Documentation is clear and complete
- Screenshots are up-to-date
- FAQ covers common questions
- Quick start guide is helpful
- Documentation is accessible

### Files to Create
- `docs/survey-types-user-guide.md`
- `docs/survey-types-faq.md`

---

## Task 24: Create Admin Documentation
**Status**: not_started  
**Priority**: Medium  
**Estimated Time**: 3 hours  
**Dependencies**: Task 9

### Description
Create admin documentation for managing survey types.

### Subtasks
- 24.1: Write guide for assigning survey types to questions
- 24.2: Document best practices
- 24.3: Create admin workflow diagrams
- 24.4: Write troubleshooting guide
- 24.5: Document data model
- 24.6: Review and edit

### Acceptance Criteria
- Documentation is comprehensive
- Best practices are clear
- Workflows are documented
- Troubleshooting guide is helpful
- Data model is explained

### Files to Create
- `docs/survey-types-admin-guide.md`
- `docs/survey-types-troubleshooting.md`

---

## Task 25: Create Developer Documentation
**Status**: not_started  
**Priority**: Low  
**Estimated Time**: 2 hours  
**Dependencies**: Task 2, Task 3, Task 4

### Description
Create technical documentation for developers.

### Subtasks
- 25.1: Document API endpoints
- 25.2: Document data models
- 25.3: Document service classes
- 25.4: Create code examples
- 25.5: Document testing approach
- 25.6: Review and edit

### Acceptance Criteria
- API is fully documented
- Data models are explained
- Code examples are provided
- Testing is documented
- Documentation is maintainable

### Files to Create
- `docs/survey-types-api.md`
- `docs/survey-types-architecture.md`

---

## Task 26: User Acceptance Testing
**Status**: not_started  
**Priority**: High  
**Estimated Time**: 4 hours  
**Dependencies**: Task 20, Task 21

### Description
Conduct user acceptance testing with real users.

### Subtasks
- 26.1: Recruit test users (staff and admins)
- 26.2: Create test scenarios
- 26.3: Conduct testing sessions
- 26.4: Collect feedback
- 26.5: Document issues
- 26.6: Prioritize fixes
- 26.7: Implement critical fixes

### Acceptance Criteria
- At least 5 users test the feature
- Feedback is collected and documented
- Critical issues are identified
- User satisfaction is measured
- Fixes are prioritized

### Deliverables
- UAT report
- Feedback summary
- Issue list

---

## Task 27: Deploy to Staging
**Status**: not_started  
**Priority**: High  
**Estimated Time**: 2 hours  
**Dependencies**: Task 26

### Description
Deploy survey type feature to staging environment.

### Subtasks
- 27.1: Prepare deployment package
- 27.2: Backup staging database/files
- 27.3: Deploy code changes
- 27.4: Run database migrations
- 27.5: Verify deployment
- 27.6: Test in staging
- 27.7: Monitor for errors

### Acceptance Criteria
- Deployment is successful
- No errors in staging
- All features work correctly
- Backward compatibility verified
- Rollback plan is ready

### Environment
- Staging server

---

## Task 28: Deploy to Production
**Status**: not_started  
**Priority**: High  
**Estimated Time**: 2 hours  
**Dependencies**: Task 27

### Description
Deploy survey type feature to production environment.

### Subtasks
- 28.1: Schedule deployment window
- 28.2: Notify users of deployment
- 28.3: Backup production database/files
- 28.4: Deploy code changes
- 28.5: Run database migrations
- 28.6: Verify deployment
- 28.7: Monitor for errors
- 28.8: Announce feature to users

### Acceptance Criteria
- Deployment is successful
- No errors in production
- All features work correctly
- Users are notified
- Monitoring is active

### Environment
- Production server

---

## Task 29: Post-Deployment Monitoring
**Status**: not_started  
**Priority**: High  
**Estimated Time**: Ongoing  
**Dependencies**: Task 28

### Description
Monitor survey type feature after production deployment.

### Subtasks
- 29.1: Monitor error logs
- 29.2: Track usage metrics
- 29.3: Collect user feedback
- 29.4: Monitor performance
- 29.5: Address issues promptly
- 29.6: Create weekly reports

### Acceptance Criteria
- Monitoring is active
- Metrics are tracked
- Issues are addressed quickly
- Reports are generated
- Feature is stable

### Duration
- First 2 weeks after deployment

---

## Task 30: Feature Retrospective
**Status**: not_started  
**Priority**: Low  
**Estimated Time**: 2 hours  
**Dependencies**: Task 29

### Description
Conduct retrospective on survey type feature implementation.

### Subtasks
- 30.1: Schedule retrospective meeting
- 30.2: Review what went well
- 30.3: Review what could be improved
- 30.4: Document lessons learned
- 30.5: Create action items for future
- 30.6: Share findings with team

### Acceptance Criteria
- Retrospective is conducted
- Lessons are documented
- Action items are created
- Team is aligned
- Improvements are identified

### Deliverables
- Retrospective notes
- Lessons learned document
- Action items list

---

## Summary

**Total Tasks**: 30  
**Estimated Total Time**: 75 hours (approximately 2-3 weeks for 1 developer)

### By Priority:
- **High Priority**: 18 tasks (core functionality)
- **Medium Priority**: 8 tasks (enhancements and documentation)
- **Low Priority**: 4 tasks (nice-to-have features)

### By Phase:
- **Phase 1 (Backend)**: Tasks 1-6 (11 hours)
- **Phase 2 (Frontend)**: Tasks 7-12 (19 hours)
- **Phase 3 (Testing)**: Tasks 13-22 (28 hours)
- **Phase 4 (Documentation)**: Tasks 23-25 (8 hours)
- **Phase 5 (Deployment)**: Tasks 26-30 (12 hours)

### Critical Path:
Task 1 → Task 2 → Task 3 → Task 4 → Task 5 → Task 6 → Task 7 → Task 8 → Task 12 → Task 19 → Task 20 → Task 26 → Task 27 → Task 28

---

## Notes

- Tasks can be parallelized where dependencies allow
- Testing tasks can run concurrently with development
- Documentation can be written alongside implementation
- UAT should involve real users from different roles
- Deployment should follow standard change management process
