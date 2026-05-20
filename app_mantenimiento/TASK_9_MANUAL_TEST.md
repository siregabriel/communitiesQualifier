# Task 9: Manual Testing Guide

## Quick Start

1. Start the Flask server:
```bash
cd /Users/GabrielRosales/Projects/CommunitiesQualifier/app_mantenimiento
python3 app.py
```

2. Open browser to: http://localhost:5000

3. Login with admin credentials:
   - Username: `admin`
   - Password: `admin123`

4. Navigate to Question Manager (Standards menu)

## Visual Checks

### ✅ Filter Section
- [ ] Filter dropdown appears above the table
- [ ] "All Types" is the default option
- [ ] All 6 survey types appear in dropdown
- [ ] Dropdown has proper styling (rounded corners, border)

### ✅ Table Display
- [ ] "Survey Types" column appears between "Photo Required" and "Assigned Communities"
- [ ] Column header is properly styled
- [ ] Table has 6 columns total

### ✅ Create Modal
- [ ] Click "Create New Question" button
- [ ] "Survey Types" section appears in modal
- [ ] Help text is visible: "Select which survey types this question applies to. Leave empty to include in all types."
- [ ] All 6 survey types appear with checkboxes
- [ ] Each type shows icon and name
- [ ] Icons have correct colors
- [ ] "Select All Types" checkbox appears at top
- [ ] Selected count shows "0 types selected (All Types)"

## Functional Tests

### Test 1: Create Question with Single Survey Type
1. Click "Create New Question"
2. Enter text: "Is the kitchen clean?"
3. Select at least one community
4. Check only "Dining Review"
5. Verify count shows "1 type selected"
6. Click "Save Question"
7. **Expected**: Question appears in table with orange "Dining Review" badge

### Test 2: Create Question with Multiple Survey Types
1. Click "Create New Question"
2. Enter text: "Are emergency exits clearly marked?"
3. Select at least one community
4. Check "Life Safety Review" and "Operational Review"
5. Verify count shows "2 types selected"
6. Click "Save Question"
7. **Expected**: Question appears with both badges (yellow and green)

### Test 3: Create Question with All Types (Empty)
1. Click "Create New Question"
2. Enter text: "Is the facility well-maintained?"
3. Select at least one community
4. Leave all survey types unchecked
5. Verify count shows "0 types selected (All Types)"
6. Click "Save Question"
7. **Expected**: Question appears with gray "All Types" badge

### Test 4: Select All Types
1. Click "Create New Question"
2. Click "Select All Types" checkbox
3. **Expected**: All 6 types are checked
4. **Expected**: Count shows "6 types selected"
5. Uncheck "Select All Types"
6. **Expected**: All types are unchecked
7. **Expected**: Count shows "0 types selected (All Types)"

### Test 5: Edit Question Survey Types
1. Find a question in the table
2. Click "Edit" button
3. **Expected**: Current survey types are pre-selected
4. Change the selection (add or remove types)
5. Click "Save Question"
6. **Expected**: Badges update in the table

### Test 6: Filter by Survey Type
1. Create at least 3 questions:
   - Question A: Only "Operational Review"
   - Question B: Only "Clinical Review"
   - Question C: No types (All Types)
2. Select "Operational Review" from filter
3. **Expected**: Only Question A and Question C appear
4. Select "Clinical Review" from filter
5. **Expected**: Only Question B and Question C appear
6. Select "All Types" from filter
7. **Expected**: All questions appear

### Test 7: Badge Colors
Verify each survey type displays with correct color:
- [ ] Full Regional Review: Blue (#3b82f6)
- [ ] Operational Review: Green (#10b981)
- [ ] Sales & Marketing: Purple (#8b5cf6)
- [ ] Clinical Review: Red (#ef4444)
- [ ] Dining Review: Orange (#f59e0b)
- [ ] Life Safety Review: Yellow (#eab308)
- [ ] All Types: Gray (#64748b)

### Test 8: Badge Icons
Verify each survey type displays with correct icon:
- [ ] Full Regional Review: fa-sitemap (network/hierarchy icon)
- [ ] Operational Review: fa-search-plus (magnifying glass with plus)
- [ ] Sales & Marketing: fa-chart-line (line chart)
- [ ] Clinical Review: fa-user-md (doctor icon)
- [ ] Dining Review: fa-utensils (fork and knife)
- [ ] Life Safety Review: fa-exclamation-triangle (warning triangle)
- [ ] All Types: fa-check-circle (check mark in circle)

## Browser Console Checks

1. Open browser DevTools (F12)
2. Go to Console tab
3. Refresh the page
4. **Expected**: No JavaScript errors
5. Check Network tab
6. **Expected**: `/api/survey-types` request returns 200 OK
7. **Expected**: Response contains 6 survey types

## API Verification

### Check Survey Types API
```bash
curl -X GET http://localhost:5000/api/survey-types \
  -H "Cookie: session=YOUR_SESSION_COOKIE"
```

**Expected Response**:
```json
{
  "survey_types": [
    {
      "id": "full-regional",
      "name": "Full Regional Review",
      "icon": "fa-sitemap",
      "color": "#3b82f6",
      ...
    },
    ...
  ]
}
```

### Create Question with Survey Types
```bash
curl -X POST http://localhost:5000/api/questions \
  -H "Content-Type: application/json" \
  -H "Cookie: session=YOUR_SESSION_COOKIE" \
  -d '{
    "text": "Test question",
    "photo_required": false,
    "communities": ["Test Community"],
    "survey_types": ["operational", "clinical"]
  }'
```

**Expected Response**:
```json
{
  "status": "success",
  "question": {
    "id": "...",
    "text": "Test question",
    "survey_types": ["operational", "clinical"],
    ...
  }
}
```

## Mobile Testing

1. Resize browser to mobile width (< 768px)
2. **Expected**: Filter dropdown is usable
3. **Expected**: Table scrolls horizontally
4. **Expected**: Modal survey type selector is usable
5. **Expected**: Badges wrap properly

## Edge Cases

### Empty State
1. Delete all questions
2. **Expected**: Empty state message appears
3. **Expected**: Message spans all 6 columns

### Many Survey Types
1. Create a question with all 6 survey types
2. **Expected**: All badges display in the table cell
3. **Expected**: Badges wrap to multiple lines if needed

### Long Question Text
1. Create a question with very long text (200+ characters)
2. **Expected**: Text truncates or wraps properly
3. **Expected**: Survey type badges still visible

## Success Criteria

All tests should pass with:
- ✅ No JavaScript errors in console
- ✅ All UI elements render correctly
- ✅ Survey types save and load correctly
- ✅ Filter works as expected
- ✅ Badges display with correct colors and icons
- ✅ Empty selection means "all types"
- ✅ Edit modal pre-selects current types

## Troubleshooting

### Survey types not loading
- Check browser console for errors
- Verify `/api/survey-types` endpoint returns data
- Check `data/survey_types.json` exists

### Badges not showing colors
- Inspect element to see inline styles
- Verify survey_types.json has color field
- Check CSS for `.survey-type-badge` class

### Filter not working
- Check browser console for JavaScript errors
- Verify `filterQuestions()` function is defined
- Check that `allQuestions` array is populated

### Survey types not saving
- Check Network tab for API request
- Verify request includes `survey_types` field
- Check API response for errors
