# Implementation Plan: Community Details Slide-In Panel

## Overview

This implementation plan breaks down the Community Details Slide-In Panel feature into discrete, actionable coding tasks. The panel will display detailed visit information for a selected community in the ATLAS dashboard, sliding in from the right with a dark overlay. The implementation follows a vanilla JavaScript approach, integrating with the existing Flask backend and CSS styles already present in dashboard.html.

## Tasks

- [x] 1. Set up HTML structure for slide panel and overlay
  - Add slide panel container with header and body sections to dashboard.html
  - Add overlay element for background dimming
  - Add close button with Font Awesome icon
  - Ensure proper semantic HTML structure with ARIA labels for accessibility
  - _Design: Components and Interfaces - SlidePanel Manager_

- [ ] 2. Implement core data processing functions
  - [x] 2.1 Create filterByCommunity function
    - Filter inspections array by community name
    - Return array of inspections matching the specified community
    - Handle edge cases (empty arrays, null values)
    - _Design: Component 2 - Data Processor, Algorithm: Main Panel Opening (Step 2)_
  
  - [x] 2.2 Create calculateScore function
    - Map condition types to numeric scores (Excellence=100, Pass=75, Good=75, Opportunity=50, Needs Attention=25, Fail=0)
    - Calculate average score from all inspections
    - Return null if no scoreable inspections exist
    - Return rounded integer between 0-100
    - _Design: Component 2 - Data Processor, Algorithm: Score Calculation_
  
  - [x] 2.3 Create countActionItems function
    - Count inspections with conditions: 'Fail', 'Opportunity', 'Needs Attention'
    - Return non-negative integer count
    - _Design: Component 2 - Data Processor, Algorithm: Action Items Counting_
  
  - [x] 2.4 Create groupResponsesByCondition function
    - Group inspections by condition type
    - Map each inspection to ResponseGroup format with condition class and icon
    - Use existing getBadgeClass() and getBadgeIcon() helper functions
    - Sort by condition severity (Fail first, Excellence last)
    - _Design: Component 2 - Data Processor, Model 3 - ResponseGroup_
  
  - [x] 2.5 Create extractPhotos function
    - Extract all non-null photo paths from inspections
    - Deduplicate photos by path
    - Create Photo objects with path, alt text, and timestamp
    - _Design: Component 2 - Data Processor, Model 4 - Photo_

- [x] 3. Implement panel rendering functions
  - [x] 3.1 Create renderHeader function
    - Generate HTML for panel header with community name and last visit date
    - Include close button with proper event attributes
    - Apply appropriate CSS classes
    - _Design: Component 3 - Panel Renderer_
  
  - [x] 3.2 Create renderStats function
    - Generate HTML for stats section with score and action items count
    - Handle null score case (display "N/A" or appropriate message)
    - Use Font Awesome icons for visual indicators
    - Apply color coding based on score ranges (green >80, yellow 50-80, red <50)
    - _Design: Component 3 - Panel Renderer_
  
  - [x] 3.3 Create renderResponses function
    - Generate HTML for responses section grouped by condition
    - Display question text, description, timestamp, and photo thumbnail if available
    - Apply condition-specific badge classes and icons
    - Handle empty responses array with appropriate message
    - _Design: Component 3 - Panel Renderer, Model 3 - ResponseGroup_
  
  - [x] 3.4 Create renderPhotos function
    - Generate HTML for photos gallery section
    - Create grid layout of photo thumbnails
    - Add click handlers for photo enlargement (optional enhancement)
    - Handle empty photos array with appropriate message
    - Add img onerror handlers for missing photos
    - _Design: Component 3 - Panel Renderer, Model 4 - Photo_
  
  - [x] 3.5 Create renderEmptyState function
    - Generate HTML for empty state when no data is available
    - Display user-friendly message with icon
    - Provide consistent styling with rest of panel
    - _Design: Component 3 - Panel Renderer_

- [x] 4. Implement main panel management functions
  - [x] 4.1 Create openSlidePanel function
    - Accept communityName parameter
    - Fetch data from /api/inspections endpoint
    - Filter inspections by community name
    - Calculate all metrics (score, action items, last visit date)
    - Process responses and photos
    - Call renderPanelContent with processed data
    - Add 'show' class to panel and overlay
    - Handle API errors with user-friendly messages
    - _Design: Component 1 - SlidePanel Manager, Algorithm: Main Panel Opening_
  
  - [x] 4.2 Create closeSlidePanel function
    - Remove 'show' class from panel and overlay
    - Re-enable body scroll if disabled
    - Ensure idempotent behavior (can be called multiple times safely)
    - _Design: Component 1 - SlidePanel Manager, Algorithm: Panel Closing_
  
  - [x] 4.3 Create renderPanelContent function
    - Accept CommunityDetailData object
    - Call all render functions (header, stats, responses, photos)
    - Update panel body innerHTML with combined HTML
    - Ensure proper HTML escaping to prevent XSS
    - _Design: Component 1 - SlidePanel Manager, Function 3_

- [x] 5. Implement event handlers
  - [x] 5.1 Add click event listener to community cards
    - Select all .community-card elements
    - Extract community name from card title
    - Call openSlidePanel with community name
    - Add debouncing to prevent rapid multiple clicks (300ms)
    - _Design: Component 4 - Event Handler, Example Usage 1_
  
  - [x] 5.2 Add click event listener to close button
    - Select .slide-panel-close element
    - Call closeSlidePanel on click
    - Prevent event bubbling
    - _Design: Component 4 - Event Handler, Example Usage 2_
  
  - [x] 5.3 Add click event listener to overlay
    - Select .slide-panel-overlay element
    - Call closeSlidePanel on click
    - _Design: Component 4 - Event Handler, Example Usage 3_
  
  - [x] 5.4 Add keydown event listener for ESC key
    - Listen for 'Escape' key on document
    - Check if panel is currently visible (has 'show' class)
    - Call closeSlidePanel if panel is open
    - _Design: Component 4 - Event Handler, Example Usage 4_

- [x] 6. Add error handling and edge cases
  - [x] 6.1 Add API error handling
    - Wrap fetch calls in try-catch blocks
    - Log errors to console for debugging
    - Display user-friendly alert messages on failure
    - Ensure panel doesn't open on API errors
    - _Design: Error Handling - Error Scenario 1_
  
  - [x] 6.2 Add input validation
    - Validate communityName is non-empty string
    - Check for null/undefined parameters
    - Log warnings and return early for invalid inputs
    - _Design: Error Handling - Error Scenario 2_
  
  - [x] 6.3 Add DOM element existence checks
    - Verify panel and overlay elements exist before manipulation
    - Log errors if required elements are missing
    - Provide graceful degradation
    - _Design: Error Handling - Error Scenario 3_
  
  - [x] 6.4 Add photo loading error handlers
    - Implement img onerror handlers for missing photos
    - Replace failed photos with placeholder icon
    - Log missing photo paths for debugging
    - _Design: Error Handling - Error Scenario 5_

- [~] 7. Checkpoint - Test basic functionality
  - Manually test opening panel by clicking community cards
  - Verify data is fetched and displayed correctly
  - Test all three close methods (button, overlay, ESC key)
  - Check browser console for errors
  - Ensure all tests pass, ask the user if questions arise.

- [ ]* 8. Write unit tests for data processing functions
  - [ ]* 8.1 Test filterByCommunity function
    - Test with various community names
    - Test with empty arrays
    - Test with null/undefined inputs
    - Verify all returned inspections match community name
    - _Design: Testing Strategy - Unit Testing Approach, Data Processing Tests_
  
  - [ ]* 8.2 Test calculateScore function
    - Test with different condition combinations
    - Test with empty array (should return null)
    - Test with all same conditions
    - Test with mixed conditions
    - Verify score is between 0-100 or null
    - _Design: Testing Strategy - Unit Testing Approach, Data Processing Tests_
  
  - [ ]* 8.3 Test countActionItems function
    - Test with various inspection arrays
    - Test with no action items
    - Test with all action items
    - Verify count is non-negative and ≤ total inspections
    - _Design: Testing Strategy - Unit Testing Approach, Data Processing Tests_
  
  - [ ]* 8.4 Test groupResponsesByCondition function
    - Test with various condition types
    - Test with empty array
    - Verify correct grouping and sorting
    - _Design: Testing Strategy - Unit Testing Approach, Data Processing Tests_
  
  - [ ]* 8.5 Test extractPhotos function
    - Test with null photo paths
    - Test deduplication logic
    - Test with empty array
    - _Design: Testing Strategy - Unit Testing Approach, Data Processing Tests_

- [ ]* 9. Write property-based tests for correctness properties
  - [ ]* 9.1 Property test for score validity
    - **Property 3: Score Validity**
    - **Validates: All calculated scores are either null or within 0-100 range**
    - Generate random inspection arrays with various conditions
    - Verify calculateScore always returns null or 0-100
    - Use fast-check library for property-based testing
    - _Design: Correctness Properties - Property 3, Testing Strategy - Property-Based Testing_
  
  - [ ]* 9.2 Property test for action items accuracy
    - **Property 4: Action Items Accuracy**
    - **Validates: Action item count equals number of Fail/Opportunity/Needs Attention conditions**
    - Generate random inspection arrays
    - Verify countActionItems matches manual count of action conditions
    - _Design: Correctness Properties - Property 4, Testing Strategy - Property-Based Testing_
  
  - [ ]* 9.3 Property test for data integrity
    - **Property 2: Data Integrity**
    - **Validates: All displayed inspections belong to selected community**
    - Generate random inspection arrays with various community names
    - Verify filterByCommunity returns only matching inspections
    - _Design: Correctness Properties - Property 2, Testing Strategy - Property-Based Testing_
  
  - [ ]* 9.4 Property test for panel visibility consistency
    - **Property 1: Panel Visibility Consistency**
    - **Validates: Panel and overlay are always in sync (both visible or both hidden)**
    - Test opening and closing panel multiple times
    - Verify panel and overlay always have matching 'show' class state
    - _Design: Correctness Properties - Property 1, Testing Strategy - Property-Based Testing_
  
  - [ ]* 9.5 Property test for close handler idempotency
    - **Property 5: Close Handler Idempotency**
    - **Validates: Calling closeSlidePanel multiple times has same effect as calling once**
    - Call closeSlidePanel n times (n = random 1-10)
    - Verify final state is same as calling once
    - _Design: Correctness Properties - Property 5, Testing Strategy - Property-Based Testing_

- [ ]* 10. Write integration tests
  - [ ]* 10.1 Test end-to-end panel opening flow
    - Mock /api/inspections endpoint
    - Simulate community card click
    - Verify panel opens with correct data
    - Verify all sections render correctly
    - _Design: Testing Strategy - Integration Testing Approach_
  
  - [ ]* 10.2 Test close interaction flows
    - Test close button click
    - Test overlay click
    - Test ESC key press
    - Verify panel closes with animation in all cases
    - _Design: Testing Strategy - Integration Testing Approach_
  
  - [ ]* 10.3 Test error scenarios
    - Test with API returning 404/500 errors
    - Test with malformed API response
    - Test with missing DOM elements
    - Verify graceful error handling
    - _Design: Testing Strategy - Integration Testing Approach_

- [~] 11. Implement performance optimizations
  - [x] 11.1 Add API response caching
    - Cache /api/inspections response for 30 seconds
    - Avoid re-fetching on every panel open
    - Implement simple in-memory cache with timestamp
    - _Design: Performance Considerations - Optimization Strategies_
  
  - [x] 11.2 Add click debouncing
    - Debounce community card clicks (300ms)
    - Prevent multiple simultaneous panel openings
    - Use simple timeout-based debounce function
    - _Design: Performance Considerations - Optimization Strategies_
  
  - [~] 11.3 Optimize rendering performance
    - Use document fragments for building large HTML structures
    - Batch DOM updates to minimize reflows
    - Ensure CSS transitions handle animations (not JavaScript)
    - _Design: Performance Considerations - Optimization Strategies_

- [x] 12. Add accessibility enhancements
  - [x] 12.1 Add ARIA labels and roles
    - Add role="dialog" to panel
    - Add aria-label to close button
    - Add aria-hidden to overlay
    - Add aria-live regions for dynamic content updates
    - _Design: Testing Strategy - Integration Testing Approach, Accessibility Testing_
  
  - [x] 12.2 Implement focus management
    - Move focus to panel when opened
    - Trap focus within panel while open
    - Restore focus to triggering element when closed
    - _Design: Testing Strategy - Integration Testing Approach, Accessibility Testing_
  
  - [x] 12.3 Add keyboard navigation support
    - Ensure all interactive elements are keyboard accessible
    - Add visible focus indicators
    - Test tab order is logical
    - _Design: Testing Strategy - Integration Testing Approach, Accessibility Testing_

- [~] 13. Final checkpoint - Comprehensive testing
  - Test on multiple browsers (Chrome, Firefox, Safari, Edge)
  - Test responsive behavior on mobile and desktop viewports
  - Verify all error scenarios are handled gracefully
  - Check accessibility with keyboard-only navigation
  - Run all unit and integration tests
  - Verify performance targets are met (panel opens <1s, animations <400ms)
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- The design uses JavaScript with existing vanilla JS architecture in dashboard.html
- All CSS styles for the panel already exist in dashboard.html (lines 924-1100)
- The /api/inspections endpoint already exists and returns inspection data
- Helper functions getBadgeClass() and getBadgeIcon() are already available
- Focus on integration with existing codebase rather than introducing new libraries
- Property-based tests validate universal correctness properties from the design
- Unit tests validate specific examples and edge cases
- Integration tests verify end-to-end workflows

## Task Dependency Graph

```json
{
  "waves": [
    {
      "id": 0,
      "tasks": ["1"]
    },
    {
      "id": 1,
      "tasks": ["2.1", "2.2", "2.3", "2.4", "2.5"]
    },
    {
      "id": 2,
      "tasks": ["3.1", "3.2", "3.3", "3.4", "3.5"]
    },
    {
      "id": 3,
      "tasks": ["4.1", "4.2", "4.3"]
    },
    {
      "id": 4,
      "tasks": ["5.1", "5.2", "5.3", "5.4"]
    },
    {
      "id": 5,
      "tasks": ["6.1", "6.2", "6.3", "6.4"]
    },
    {
      "id": 6,
      "tasks": ["8.1", "8.2", "8.3", "8.4", "8.5", "9.1", "9.2", "9.3", "9.4", "9.5"]
    },
    {
      "id": 7,
      "tasks": ["10.1", "10.2", "10.3"]
    },
    {
      "id": 8,
      "tasks": ["11.1", "11.2", "11.3"]
    },
    {
      "id": 9,
      "tasks": ["12.1", "12.2", "12.3"]
    }
  ]
}
```
