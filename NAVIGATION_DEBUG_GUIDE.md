# Navigation Debug Guide

## Issue Reported
Some sidebar navigation sections are not working.

## Diagnostic Steps Added

I've added console logging to help identify which sections are not working.

### How to Test

1. **Open the dashboard**
   ```
   http://localhost:5000/dashboard
   ```

2. **Open Browser DevTools**
   - Press `F12` (Windows/Linux)
   - Press `Cmd+Option+I` (Mac)
   - Or right-click → "Inspect"

3. **Go to Console tab**

4. **Look for setup messages**
   When the page loads, you should see:
   ```
   🔧 Setting up navigation event listeners...
   📋 Found 6 navigation items with data-view attribute
     1. Setting up listener for: dashboard
     2. Setting up listener for: my-visits
     3. Setting up listener for: communities
     4. Setting up listener for: reports
     5. Setting up listener for: action-items
     6. Setting up listener for: resources
     7. Setting up listener for: settings
   ✅ Navigation event listeners setup complete
   ```

5. **Click each sidebar section** and note which ones work:
   - ☐ Dashboard
   - ☐ My Visits
   - ☐ Communities
   - ☐ Standards (this one goes to /questions/manage - different behavior)
   - ☐ Reports
   - ☐ Action Items
   - ☐ Resources
   - ☐ Settings

6. **Check console output** when clicking:
   ```
   🖱️ Navigation clicked: dashboard
   📍 showView called with view: dashboard
   ⏳ Loading indicator displayed
   ```

## Expected Behavior

### Working Sections
All sections with `data-view` attribute should:
1. Show loading spinner immediately
2. Display content after ~50-100ms
3. Log messages in console

### Special Cases

**Standards Section:**
- Does NOT have `data-view` attribute
- Links directly to `/questions/manage`
- This is expected behavior (not a bug)

**Log Out:**
- Does NOT have `data-view` attribute
- Links directly to `/logout`
- This is expected behavior (not a bug)

## Common Issues

### Issue 1: No console messages appear
**Cause:** JavaScript not loading or error before setup  
**Solution:** Check for JavaScript errors above the navigation setup

### Issue 2: Setup messages appear but clicks don't work
**Cause:** Event listener not attached or being overridden  
**Solution:** Check if there are multiple event listeners or conflicts

### Issue 3: Some sections work, others don't
**Cause:** Missing render functions or JavaScript errors in specific render functions  
**Solution:** Check which sections fail and look for errors when clicking them

### Issue 4: Click works but nothing renders
**Cause:** Render function has an error  
**Solution:** Check console for errors when clicking that specific section

## Troubleshooting by Section

### Dashboard
- Calls: `renderCommunityCards()`
- Requires: `communityData` array
- Check: Are there communities loaded?

### My Visits
- Calls: `renderMyVisits()`
- Requires: `allInspections` array
- Check: Are there inspections loaded?

### Communities
- Calls: `renderCommunityCards()`
- Same as Dashboard

### Reports
- Calls: `renderReports()`
- Requires: `allInspections`, `surveyTypes`, `communityData`
- Check: Are all data arrays loaded?

### Action Items
- Calls: `renderActionItems()`
- Requires: `allInspections` array
- Check: Are there inspections with Fail/Opportunity/Needs Attention?

### Resources
- Calls: `renderResources()`
- No data required (static content)
- Should always work

### Settings
- Calls: `renderSettings()`
- Requires: `currentUsername`, `isAdmin`, `currentUserCommunity`
- Check: Is user info loaded?

## What to Report Back

Please provide:

1. **Which sections are NOT working?**
   - List the specific section names

2. **Console output**
   - Copy the setup messages
   - Copy any error messages (in red)
   - Copy the click messages when you click a non-working section

3. **What happens when you click?**
   - Nothing happens?
   - Loading spinner appears but no content?
   - Error message?
   - Page refreshes?

4. **Browser information**
   - Which browser? (Chrome, Firefox, Safari, etc.)
   - Version?

## Quick Fix Attempts

### If no sections work:
```javascript
// Try running this in the browser console:
document.querySelectorAll('.nav-item[data-view]').forEach(item => {
    console.log(item.dataset.view, item);
});
```

### If specific section doesn't work:
```javascript
// Try calling the render function directly in console:
renderResources();  // Replace with the section that's not working
```

### Force reload:
- Clear cache: `Cmd+Shift+R` (Mac) or `Ctrl+Shift+R` (Windows)
- Hard refresh
- Close and reopen browser

---

**Next Steps:** Please test and report back which sections are not working and what the console shows.
