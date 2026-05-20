# Task 28: User Role Filtering - Manual Test Guide

## Overview
This guide provides step-by-step instructions to manually test user role filtering functionality.

**Requirements Being Tested:**
- **Requirement 12.3**: Staff users should only see their assigned community
- **Requirement 12.4**: Admin users should see all communities

---

## Prerequisites

1. Flask application must be running on `http://localhost:5000`
2. Browser with developer tools (Chrome, Firefox, Safari, etc.)
3. Test user credentials from TEST_USERS.md

---

## Test 1: Staff User Filtering (Requirement 12.3)

### Objective
Verify that a staff user only sees their assigned community card on the dashboard.

### Steps

1. **Open Browser**
   - Navigate to: `http://localhost:5000/login`
   - Clear any existing session (logout if needed)

2. **Login as Staff User (user1)**
   - Username: `user1`
   - Password: `test123`
   - Click "Login"

3. **Verify User Info**
   - You should be redirected to the dashboard
   - Check the sidebar user welcome section:
     - Should show: "Welcome back, user1"
     - Should show community: "Kelley Place, Enterprise"
   - Check that "Question Manager" button is NOT visible (staff users don't have access)

4. **Verify Community Cards**
   - Look at the main content area with community cards
   - **Expected Result**: Only ONE community card should be displayed
   - **Expected Community**: "Kelley Place, Enterprise"
   - The card should show:
     - Community name: "Kelley Place, Enterprise"
     - Last visit date (or "No visits yet")
     - Score percentage (or "N/A")
     - Open actions count

5. **Verify No Other Communities**
   - Scroll through the entire dashboard
   - **Expected Result**: No other community cards should be visible
   - Only "Kelley Place, Enterprise" should appear

6. **Check Browser Console (Optional)**
   - Open Developer Tools (F12)
   - Go to Console tab
   - Look for any JavaScript errors (there should be none)
   - Check Network tab for `/api/inspections` request
   - Verify response only contains submissions for "Kelley Place, Enterprise"

### Expected Results ✓
- ✓ User logged in successfully as user1
- ✓ Sidebar shows "Kelley Place, Enterprise" as user's community
- ✓ Only 1 community card is displayed
- ✓ Community card is for "Kelley Place, Enterprise"
- ✓ No other community cards are visible
- ✓ Question Manager button is hidden

---

## Test 2: Admin User Sees All Communities (Requirement 12.4)

### Objective
Verify that an admin user sees all 38 community cards on the dashboard.

### Steps

1. **Logout from Staff User**
   - Click "Log Out" in the sidebar navigation
   - Or navigate to: `http://localhost:5000/logout`

2. **Login as Admin User**
   - Navigate to: `http://localhost:5000/login`
   - Username: `admin`
   - Password: `admin123`
   - Click "Login"

3. **Verify Admin User Info**
   - You should be redirected to the dashboard
   - Check the sidebar user welcome section:
     - Should show: "Welcome back, admin"
     - Should show role: "Admin" (not a specific community)
   - Check that "Question Manager" button IS visible (admin users have access)

4. **Verify All Community Cards**
   - Look at the main content area with community cards
   - **Expected Result**: ALL 38 community cards should be displayed
   - Scroll through the dashboard to see all cards
   - Cards should be displayed in a responsive grid layout

5. **Verify Community Names**
   - Check that cards include communities from different states:
     - **Georgia**: Kelley Place, Madison Heights Enterprise, Monark Grove Madison, etc.
     - **Florida**: Madison at Clermont, Madison at Ocoee, The Goldton at Venice, etc.
     - **North Carolina**: Madison Heights Evans, Legacy at Savannah Quarters, etc.
     - **South Carolina**: Oakview Park, Spring Park, etc.
     - **Tennessee**: The Goldton at Spring Hill
     - **Texas**: The Oscar at Georgetown, The Oscar at Veramendi
     - **Maryland**: Tribute at Black Hill, Tribute at Melford
     - **Virginia**: Tribute at One Loudoun, Tribute at The Glen
     - And more...

6. **Count Community Cards**
   - Scroll through the entire dashboard
   - Count the total number of community cards
   - **Expected Result**: 38 community cards total

7. **Check Browser Console (Optional)**
   - Open Developer Tools (F12)
   - Go to Console tab
   - Check Network tab for `/api/inspections` request
   - Verify response contains submissions from multiple communities (not filtered)

### Expected Results ✓
- ✓ User logged in successfully as admin
- ✓ Sidebar shows "Admin" as user's role
- ✓ Question Manager button is visible
- ✓ All 38 community cards are displayed
- ✓ Cards include communities from all states
- ✓ No filtering is applied to community cards

---

## Test 3: Different Staff Users See Different Communities

### Objective
Verify that different staff users see their respective assigned communities.

### Test Cases

#### Test Case 3.1: user3 (Monark Grove Madison)

1. Logout and login as:
   - Username: `user3`
   - Password: `test123`

2. **Expected Results:**
   - ✓ Sidebar shows "Monark Grove Madison"
   - ✓ Only 1 community card displayed
   - ✓ Card is for "Monark Grove Madison"

#### Test Case 3.2: user9 (Madison at Clermont, Clermont)

1. Logout and login as:
   - Username: `user9`
   - Password: `test123`

2. **Expected Results:**
   - ✓ Sidebar shows "Madison at Clermont, Clermont"
   - ✓ Only 1 community card displayed
   - ✓ Card is for "Madison at Clermont, Clermont"

#### Test Case 3.3: user28 (Oakview Park, Greenville)

1. Logout and login as:
   - Username: `user28`
   - Password: `test123`

2. **Expected Results:**
   - ✓ Sidebar shows "Oakview Park, Greenville"
   - ✓ Only 1 community card displayed
   - ✓ Card is for "Oakview Park, Greenville"

---

## Test 4: Navigation and Filtering

### Objective
Verify that role filtering persists across different views and filters.

### Steps

1. **Login as Staff User (user1)**
   - Username: `user1`
   - Password: `test123`

2. **Test Dashboard View**
   - Click "Dashboard" in sidebar
   - **Expected**: Only "Kelley Place, Enterprise" card visible

3. **Test Communities View**
   - Click "Communities" in sidebar
   - **Expected**: Only "Kelley Place, Enterprise" card visible

4. **Test Condition Filters**
   - Click different condition filter buttons (Excellence, Pass, Opportunity, Fail)
   - **Expected**: Filtering works, but still only shows "Kelley Place, Enterprise"
   - If no data matches filter, shows "No communities match this filter"

5. **Login as Admin**
   - Logout and login as admin

6. **Test Admin Dashboard View**
   - Click "Dashboard" in sidebar
   - **Expected**: All 38 community cards visible

7. **Test Admin Communities View**
   - Click "Communities" in sidebar
   - **Expected**: All 38 community cards visible

8. **Test Admin Condition Filters**
   - Click different condition filter buttons
   - **Expected**: Filtering works across all communities
   - Shows communities matching the selected condition

---

## Verification Checklist

### Staff User (user1) ✓
- [ ] Logs in successfully
- [ ] Sidebar shows correct username and community
- [ ] Only 1 community card displayed
- [ ] Card matches assigned community
- [ ] Question Manager button hidden
- [ ] Filtering works correctly
- [ ] No other communities visible

### Admin User ✓
- [ ] Logs in successfully
- [ ] Sidebar shows "Admin" role
- [ ] All 38 community cards displayed
- [ ] Question Manager button visible
- [ ] Cards from all states visible
- [ ] Filtering works across all communities
- [ ] No community restrictions applied

### Different Staff Users ✓
- [ ] user3 sees only "Monark Grove Madison"
- [ ] user9 sees only "Madison at Clermont, Clermont"
- [ ] user28 sees only "Oakview Park, Greenville"
- [ ] Each user sees only their assigned community

---

## Troubleshooting

### Issue: No community cards displayed
- **Solution**: Check if there are any inspection submissions in the database
- **Note**: Cards will still display with "N/A" score and "No visits yet" even without data

### Issue: Wrong community displayed for staff user
- **Solution**: Check USERS_DB in app.py to verify user-community mapping
- **Solution**: Clear browser cache and cookies, then login again

### Issue: Admin sees filtered communities
- **Solution**: Check that admin user has `community: None` in USERS_DB
- **Solution**: Verify `is_admin` flag is set correctly in session

### Issue: JavaScript errors in console
- **Solution**: Check browser console for specific error messages
- **Solution**: Verify all API endpoints are responding correctly

---

## Success Criteria

**Task 28 is complete when:**

1. ✅ Staff users (like user1) only see their assigned community card
2. ✅ Admin user sees all 38 community cards
3. ✅ Different staff users see different communities
4. ✅ Role filtering persists across views and filters
5. ✅ No JavaScript errors in browser console
6. ✅ All requirements 12.3 and 12.4 are satisfied

---

## Notes

- This test verifies the frontend filtering logic in dashboard.html
- The filtering is implemented in the `loadCommunityData()` JavaScript function
- Backend API `/api/inspections` also filters by user role
- Admin users have `community: None` in the session
- Staff users have their specific community name in the session

---

**Test Date**: _____________

**Tester**: _____________

**Result**: ⬜ PASS  ⬜ FAIL

**Comments**:
_____________________________________________________________________________
_____________________________________________________________________________
_____________________________________________________________________________
