# Task 30: Manual Integration Testing Guide

## Overview
This guide provides step-by-step instructions for manually testing the ATLAS Dashboard Redesign to verify all requirements are met.

**Test Date:** May 19, 2026  
**Tester:** _________________  
**Status:** ✅ READY FOR TESTING

---

## Prerequisites

1. **Server Running:** Ensure Flask app is running on port 5001
   ```bash
   cd app_mantenimiento
   python3 app.py
   ```

2. **Test Accounts:**
   - Admin: `admin` / `admin123`
   - Staff: `user1` / `test123`

3. **Browser:** Chrome, Firefox, Safari, or Edge (latest version)

4. **Tools:**
   - Browser DevTools (F12)
   - Responsive Design Mode
   - Console for errors

---

## Test 1: Complete User Flow

### 1.1 Login Flow
- [ ] Navigate to `http://localhost:5001/login`
- [ ] Verify login page displays correctly
- [ ] Enter credentials: `admin` / `admin123`
- [ ] Click "Login" button
- [ ] Verify redirect to dashboard
- [ ] Verify no console errors

**Expected Result:** ✅ User successfully logs in and sees dashboard

---

### 1.2 Dashboard View
- [ ] Verify ATLAS logo displays in sidebar
- [ ] Verify welcome message shows "Welcome back, admin"
- [ ] Verify user role shows "Admin"
- [ ] Verify all 9 navigation items are visible:
  - Dashboard
  - My Visits
  - Communities
  - Standards
  - Reports
  - Action Items
  - Resources
  - Settings
  - Log Out
- [ ] Verify community cards display in grid layout
- [ ] Verify each card shows:
  - Community photo or gradient
  - Community name
  - Last visit date
  - Circular progress indicator with score
  - Action items count
  - "View Details" button

**Expected Result:** ✅ Dashboard displays all elements correctly

---

### 1.3 View Communities
- [ ] Click "Communities" in navigation menu
- [ ] Verify active state highlights "Communities" menu item
- [ ] Verify all community cards are visible
- [ ] Verify cards are responsive and well-spaced

**Expected Result:** ✅ Communities view displays correctly

---

### 1.4 Start New Visit
- [ ] Locate "Start New Visit" button (bottom right, floating)
- [ ] Verify button is visible and accessible
- [ ] Click "Start New Visit" button
- [ ] Verify navigation to survey type selection page
- [ ] Verify page loads without errors

**Expected Result:** ✅ User can start a new visit successfully

---

## Test 2: Responsive Behavior Across Breakpoints

### 2.1 Mobile (320px)
- [ ] Open DevTools (F12)
- [ ] Enable Responsive Design Mode
- [ ] Set viewport to 320px × 568px
- [ ] Verify sidebar is hidden by default
- [ ] Verify hamburger menu is visible in top-left
- [ ] Click hamburger menu
- [ ] Verify sidebar slides in from left
- [ ] Verify overlay appears behind sidebar
- [ ] Click overlay
- [ ] Verify sidebar closes
- [ ] Verify community grid shows 1 card per row
- [ ] Verify all text is readable
- [ ] Verify buttons are accessible
- [ ] Verify "Start New Visit" button is visible

**Expected Result:** ✅ Mobile layout works correctly at 320px

---

### 2.2 Tablet (768px)
- [ ] Set viewport to 768px × 1024px
- [ ] Verify sidebar becomes visible
- [ ] Verify sidebar width is 260px
- [ ] Verify main content has 260px left margin
- [ ] Verify hamburger menu is hidden
- [ ] Verify community grid shows 2 cards per row
- [ ] Verify navigation menu is fully visible
- [ ] Verify all hover effects work

**Expected Result:** ✅ Tablet layout works correctly at 768px

---

### 2.3 Desktop (1024px)
- [ ] Set viewport to 1024px × 768px
- [ ] Verify sidebar is persistent and visible
- [ ] Verify community grid shows 2-3 cards per row
- [ ] Verify spacing and typography are optimal
- [ ] Hover over navigation items
- [ ] Verify hover effects work
- [ ] Hover over community cards
- [ ] Verify card elevation effect
- [ ] Verify circular progress indicators display correctly

**Expected Result:** ✅ Desktop layout works correctly at 1024px

---

### 2.4 Large Desktop (1440px)
- [ ] Set viewport to 1440px × 900px
- [ ] Verify community grid shows 3-4 cards per row
- [ ] Verify content is centered with max-width constraint
- [ ] Verify no horizontal scrolling
- [ ] Verify all elements are properly scaled

**Expected Result:** ✅ Large desktop layout works correctly at 1440px

---

## Test 3: Keyboard Navigation

### 3.1 Tab Order
- [ ] Reload page
- [ ] Press Tab key repeatedly
- [ ] Verify focus moves through elements in logical order:
  1. Mobile menu toggle (if mobile)
  2. Sidebar navigation items (9 items)
  3. Community cards
  4. View Details buttons
  5. Start New Visit button
- [ ] Verify all focused elements have visible focus ring
- [ ] Verify focus ring has sufficient contrast

**Expected Result:** ✅ Tab order is logical and focus indicators are visible

---

### 3.2 Enter Key Activation
- [ ] Tab to "Dashboard" navigation item
- [ ] Press Enter
- [ ] Verify navigation works
- [ ] Tab to a "View Details" button
- [ ] Press Enter
- [ ] Verify modal opens
- [ ] Press Escape
- [ ] Verify modal closes
- [ ] Tab to "Start New Visit" button
- [ ] Press Enter
- [ ] Verify navigation to form

**Expected Result:** ✅ Enter key activates all interactive elements

---

## Test 4: Real Inspection Data

### 4.1 Score Calculation Accuracy
- [ ] Open browser console (F12 → Console tab)
- [ ] Paste and run the following test:
```javascript
// Test score calculation
const scoreMap = {
  'Excellence': 100,
  'Pass': 75,
  'Opportunity': 50,
  'Fail': 0
};

function calculateScore(responses) {
  if (!responses || responses.length === 0) return null;
  const total = responses.reduce((sum, r) => sum + (scoreMap[r.condition] || 0), 0);
  return Math.round(total / responses.length);
}

// Test cases
console.log('Excellence + Pass:', calculateScore([{condition: 'Excellence'}, {condition: 'Pass'}]), '(expected: 88)');
console.log('Opportunity + Fail:', calculateScore([{condition: 'Opportunity'}, {condition: 'Fail'}]), '(expected: 25)');
console.log('Mixed:', calculateScore([{condition: 'Excellence'}, {condition: 'Pass'}, {condition: 'Opportunity'}, {condition: 'Fail'}]), '(expected: 56)');
```
- [ ] Verify all calculations match expected values

**Expected Result:** ✅ Score calculations are accurate

---

### 4.2 Action Items Count Accuracy
- [ ] Run the following test in console:
```javascript
// Test action items counting
function countActionItems(responses) {
  const actionConditions = ['Fail', 'Opportunity', 'Needs Attention'];
  return responses.filter(r => actionConditions.includes(r.condition)).length;
}

// Test cases
console.log('Mixed conditions:', countActionItems([
  {condition: 'Excellence'},
  {condition: 'Pass'},
  {condition: 'Opportunity'},
  {condition: 'Fail'},
  {condition: 'Needs Attention'}
]), '(expected: 3)');

console.log('No action items:', countActionItems([
  {condition: 'Excellence'},
  {condition: 'Pass'}
]), '(expected: 0)');
```
- [ ] Verify all counts match expected values

**Expected Result:** ✅ Action items counting is accurate

---

### 4.3 Community Data Integration
- [ ] Verify all communities from system are displayed
- [ ] Check a community with no data
- [ ] Verify it shows "N/A" for score
- [ ] Verify it shows "No visits yet" for last visit
- [ ] Check a community with data
- [ ] Verify score is displayed as percentage
- [ ] Verify last visit date is formatted correctly (e.g., "May 8, 2024")

**Expected Result:** ✅ Community data displays correctly

---

### 4.4 User Role Filtering

**Admin User Test:**
- [ ] Log in as admin (`admin` / `admin123`)
- [ ] Verify "Admin" role is displayed in sidebar
- [ ] Count visible community cards
- [ ] Verify multiple communities are visible

**Staff User Test:**
- [ ] Log out
- [ ] Log in as user1 (`user1` / `test123`)
- [ ] Verify "Kelley Place, Enterprise" is displayed in sidebar
- [ ] Verify only 1 community card is displayed (if data exists)
- [ ] Verify community name matches user's assigned community

**Expected Result:** ✅ User role filtering works correctly

---

## Test 5: Console Errors and Warnings

### 5.1 Page Load Monitoring
- [ ] Open DevTools Console before loading page
- [ ] Navigate to dashboard
- [ ] Monitor console for:
  - ❌ Errors (red)
  - ⚠️ Warnings (yellow)
  - ℹ️ Info messages (blue)
- [ ] Verify no 404 errors for missing resources
- [ ] Verify no CORS errors
- [ ] Verify no JavaScript syntax errors
- [ ] Verify no unhandled promise rejections

**Expected Result:** ✅ No console errors or warnings

---

### 5.2 Network Tab Validation
- [ ] Open DevTools Network tab
- [ ] Reload page
- [ ] Verify all requests return 200 OK:
  - GET /dashboard → 200
  - GET /api/user-info → 200
  - GET /api/inspections → 200
  - GET /api/survey-types → 200
  - GET /static/atlas-globe-1.png → 200
  - GET /static/manifest.json → 200
- [ ] Verify all CSS files load successfully
- [ ] Verify all JavaScript files load successfully
- [ ] Verify Font Awesome icons load correctly
- [ ] Verify Google Fonts load correctly

**Expected Result:** ✅ All resources load successfully

---

## Test 6: Page Load Performance

### 6.1 Lighthouse Audit
- [ ] Open DevTools
- [ ] Go to Lighthouse tab
- [ ] Select "Performance" category
- [ ] Click "Analyze page load"
- [ ] Verify metrics:
  - First Contentful Paint (FCP): < 1.8s
  - Largest Contentful Paint (LCP): < 2.5s
  - Time to Interactive (TTI): < 3.8s
  - Total Blocking Time (TBT): < 300ms
  - Cumulative Layout Shift (CLS): < 0.1

**Expected Result:** ✅ Performance metrics meet targets

---

### 6.2 Manual Performance Check
- [ ] Open DevTools Console
- [ ] Paste and run:
```javascript
window.addEventListener('load', () => {
  const perfData = performance.getEntriesByType('navigation')[0];
  console.log('DOM Content Loaded:', Math.round(perfData.domContentLoadedEventEnd - perfData.domContentLoadedEventStart), 'ms');
  console.log('Load Complete:', Math.round(perfData.loadEventEnd - perfData.loadEventStart), 'ms');
  console.log('Total Page Load:', Math.round(perfData.loadEventEnd - perfData.fetchStart), 'ms');
});
```
- [ ] Reload page
- [ ] Verify total page load < 2000ms

**Expected Result:** ✅ Page loads in under 2 seconds

---

## Test 7: Cross-Browser Compatibility

### 7.1 Chrome
- [ ] Open in Chrome
- [ ] Verify all features work
- [ ] Verify layout renders correctly
- [ ] Verify animations are smooth
- [ ] Verify no console errors

**Expected Result:** ✅ Works in Chrome

---

### 7.2 Firefox
- [ ] Open in Firefox
- [ ] Verify all features work
- [ ] Verify layout renders correctly
- [ ] Verify animations are smooth
- [ ] Verify no console errors

**Expected Result:** ✅ Works in Firefox

---

### 7.3 Safari
- [ ] Open in Safari
- [ ] Verify all features work
- [ ] Verify layout renders correctly
- [ ] Verify animations are smooth
- [ ] Verify no console errors

**Expected Result:** ✅ Works in Safari

---

### 7.4 Edge
- [ ] Open in Edge
- [ ] Verify all features work
- [ ] Verify layout renders correctly
- [ ] Verify animations are smooth
- [ ] Verify no console errors

**Expected Result:** ✅ Works in Edge

---

## Test 8: Accessibility Compliance

### 8.1 Color Contrast
- [ ] Use browser extension (e.g., WAVE, axe DevTools)
- [ ] Run accessibility audit
- [ ] Verify sidebar text on dark background: ≥ 4.5:1
- [ ] Verify body text on white background: ≥ 4.5:1
- [ ] Verify button text on colored backgrounds: ≥ 4.5:1
- [ ] Verify progress indicator values: ≥ 4.5:1

**Expected Result:** ✅ All text meets contrast requirements

---

### 8.2 Semantic HTML
- [ ] Inspect page source
- [ ] Verify proper heading hierarchy (h1 → h2 → h3)
- [ ] Verify navigation wrapped in `<nav>` element
- [ ] Verify buttons use `<button>` element
- [ ] Verify links use `<a>` element
- [ ] Verify images have alt text

**Expected Result:** ✅ Semantic HTML is correct

---

### 8.3 ARIA Attributes
- [ ] Inspect hamburger menu button
- [ ] Verify `aria-label="Toggle navigation menu"`
- [ ] Inspect active nav item
- [ ] Verify `aria-current="page"`
- [ ] Inspect decorative icons
- [ ] Verify `aria-hidden="true"`

**Expected Result:** ✅ ARIA attributes are present

---

## Test 9: Mobile-Specific Tests

### 9.1 Touch Targets
- [ ] Switch to mobile view (320px)
- [ ] Verify all buttons are ≥ 44x44px
- [ ] Verify adequate spacing between touch targets
- [ ] Tap various buttons
- [ ] Verify no accidental taps

**Expected Result:** ✅ Touch targets are appropriately sized

---

### 9.2 Sidebar Behavior
- [ ] Verify sidebar is hidden by default on mobile
- [ ] Tap hamburger menu
- [ ] Verify sidebar slides in smoothly
- [ ] Verify overlay appears
- [ ] Tap overlay
- [ ] Verify sidebar closes
- [ ] Open sidebar again
- [ ] Tap a nav item
- [ ] Verify sidebar closes automatically

**Expected Result:** ✅ Mobile sidebar behavior works correctly

---

## Test 10: Data Integrity Tests

### 10.1 Empty State Handling
- [ ] Log in as a user with no data
- [ ] Verify empty state message displays
- [ ] Verify "No visits yet" shows for last visit
- [ ] Verify "N/A" shows for score
- [ ] Verify "0 Open Actions" shows

**Expected Result:** ✅ Empty states display correctly

---

### 10.2 Edge Cases
- [ ] Find a community with score = 0%
- [ ] Verify it displays correctly
- [ ] Find a community with score = 100%
- [ ] Verify it displays correctly
- [ ] Find a community with a very long name
- [ ] Verify name wraps correctly
- [ ] Find a community with special characters in name
- [ ] Verify it displays correctly

**Expected Result:** ✅ Edge cases are handled correctly

---

## Test Results Summary

| Test Category | Status | Notes |
|--------------|--------|-------|
| Complete User Flow | ⏳ | |
| Responsive Design (320px) | ⏳ | |
| Responsive Design (768px) | ⏳ | |
| Responsive Design (1024px) | ⏳ | |
| Responsive Design (1440px) | ⏳ | |
| Keyboard Navigation | ⏳ | |
| Score Calculation | ⏳ | |
| Action Items Counting | ⏳ | |
| Community Data Integration | ⏳ | |
| User Role Filtering | ⏳ | |
| Console Errors | ⏳ | |
| Network Resources | ⏳ | |
| Performance (Lighthouse) | ⏳ | |
| Performance (Manual) | ⏳ | |
| Chrome Compatibility | ⏳ | |
| Firefox Compatibility | ⏳ | |
| Safari Compatibility | ⏳ | |
| Edge Compatibility | ⏳ | |
| Color Contrast | ⏳ | |
| Semantic HTML | ⏳ | |
| ARIA Attributes | ⏳ | |
| Touch Targets | ⏳ | |
| Mobile Sidebar | ⏳ | |
| Empty States | ⏳ | |
| Edge Cases | ⏳ | |

**Legend:**
- ⏳ Pending
- ✅ Passed
- ❌ Failed
- ⚠️ Needs Attention

---

## Issues Found

### Critical Issues
- None

### Medium Issues
- None

### Minor Issues
- None

---

## Sign-Off

**Tester Name:** _________________  
**Date:** _________________  
**Signature:** _________________  

**Overall Status:** ⏳ PENDING COMPLETION

---

## Notes

- All automated tests passed (59/59)
- Manual testing required for visual verification
- Accessibility audit recommended
- Cross-browser testing recommended

