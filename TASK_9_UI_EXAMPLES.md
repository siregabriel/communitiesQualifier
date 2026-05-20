# Task 9: UI Examples and Screenshots Guide

## Visual Layout

### 1. Filter Section (Above Table)

```
┌─────────────────────────────────────────────────────────────┐
│  🔍 Filter by Survey Type:  [All Types ▼]                   │
└─────────────────────────────────────────────────────────────┘
```

**Dropdown Options:**
- All Types (default)
- 🌐 Full Regional Review
- 🔍 Operational Review
- 📈 Sales & Marketing
- 👨‍⚕️ Clinical Review
- 🍴 Dining Review
- ⚠️ Life Safety Review

### 2. Table with Survey Type Column

```
┌──────────────────────┬───────────────┬─────────────────────────────┬──────────────────┬──────────────┬─────────┐
│ Question Text        │ Photo Required│ Survey Types                │ Communities      │ Created Date │ Actions │
├──────────────────────┼───────────────┼─────────────────────────────┼──────────────────┼──────────────┼─────────┤
│ Is kitchen clean?    │ ✓ Yes         │ 🍴 Dining Review            │ 3 communities    │ Jan 15, 2024 │ ✏️ 🗑️   │
├──────────────────────┼───────────────┼─────────────────────────────┼──────────────────┼──────────────┼─────────┤
│ Emergency exits OK?  │ No            │ ⚠️ Life Safety Review       │ 5 communities    │ Jan 14, 2024 │ ✏️ 🗑️   │
│                      │               │ 🔍 Operational Review       │                  │              │         │
├──────────────────────┼───────────────┼─────────────────────────────┼──────────────────┼──────────────┼─────────┤
│ General maintenance? │ ✓ Yes         │ ✓ All Types                 │ 8 communities    │ Jan 13, 2024 │ ✏️ 🗑️   │
└──────────────────────┴───────────────┴─────────────────────────────┴──────────────────┴──────────────┴─────────┘
```

### 3. Create/Edit Modal - Survey Types Section

```
┌─────────────────────────────────────────────────────────────┐
│  📋 Survey Types                                             │
│  ℹ️ Select which survey types this question applies to.     │
│     Leave empty to include in all types.                    │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ ☑️ Select All Types                                     │ │
│  ├────────────────────────────────────────────────────────┤ │
│  │ ☐ 🌐 Full Regional Review                              │ │
│  │ ☑️ 🔍 Operational Review                                │ │
│  │ ☐ 📈 Sales & Marketing                                 │ │
│  │ ☑️ 👨‍⚕️ Clinical Review                                   │ │
│  │ ☐ 🍴 Dining Review                                     │ │
│  │ ☐ ⚠️ Life Safety Review                                │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  [2 types selected]                                          │
└─────────────────────────────────────────────────────────────┘
```

## Badge Examples

### Single Type Badge
```
┌─────────────────────────┐
│ 🔍 Operational Review   │  (Green background)
└─────────────────────────┘
```

### Multiple Type Badges
```
┌─────────────────────┐  ┌──────────────────┐
│ 👨‍⚕️ Clinical Review │  │ 🍴 Dining Review │
└─────────────────────┘  └──────────────────┘
  (Red background)         (Orange background)
```

### All Types Badge
```
┌──────────────────┐
│ ✓ All Types      │  (Gray background)
└──────────────────┘
```

## Color Scheme

### Survey Type Colors

**Full Regional Review**
- Color: #3b82f6 (Blue)
- Icon: fa-sitemap (🌐)
- Badge: Light blue background with blue text

**Operational Review**
- Color: #10b981 (Green)
- Icon: fa-search-plus (🔍)
- Badge: Light green background with green text

**Sales & Marketing**
- Color: #8b5cf6 (Purple)
- Icon: fa-chart-line (📈)
- Badge: Light purple background with purple text

**Clinical Review**
- Color: #ef4444 (Red)
- Icon: fa-user-md (👨‍⚕️)
- Badge: Light red background with red text

**Dining Review**
- Color: #f59e0b (Orange)
- Icon: fa-utensils (🍴)
- Badge: Light orange background with orange text

**Life Safety Review**
- Color: #eab308 (Yellow)
- Icon: fa-exclamation-triangle (⚠️)
- Badge: Light yellow background with yellow text

**All Types**
- Color: #64748b (Gray)
- Icon: fa-check-circle (✓)
- Badge: Light gray background with gray text

## User Flows

### Flow 1: Create Question with Specific Types

```
1. Click "Create New Question"
   ↓
2. Fill in question text
   ↓
3. Select communities
   ↓
4. Check "Dining Review" and "Life Safety Review"
   ↓
5. See count: "2 types selected"
   ↓
6. Click "Save Question"
   ↓
7. Question appears with two badges:
   🍴 Dining Review  ⚠️ Life Safety Review
```

### Flow 2: Create Question for All Types

```
1. Click "Create New Question"
   ↓
2. Fill in question text
   ↓
3. Select communities
   ↓
4. Leave all survey types unchecked
   ↓
5. See count: "0 types selected (All Types)"
   ↓
6. Click "Save Question"
   ↓
7. Question appears with badge:
   ✓ All Types
```

### Flow 3: Filter Questions by Type

```
1. View all questions in table
   ↓
2. Select "Operational Review" from filter
   ↓
3. Table updates to show only:
   - Questions with "Operational Review" badge
   - Questions with "All Types" badge
   ↓
4. Other questions are hidden
   ↓
5. Select "All Types" from filter
   ↓
6. All questions reappear
```

### Flow 4: Edit Question Types

```
1. Click "Edit" on a question
   ↓
2. Modal opens with current types pre-selected
   ↓
3. Change selection (add/remove types)
   ↓
4. Click "Save Question"
   ↓
5. Badges update in table immediately
```

## Responsive Design

### Desktop (> 768px)
- Filter dropdown: 200px width
- Table: Full width with all columns
- Modal: 600px max width
- Badges: Display inline with wrapping

### Tablet (768px - 1024px)
- Filter dropdown: Full width
- Table: Horizontal scroll
- Modal: 90% width
- Badges: May wrap to multiple lines

### Mobile (< 768px)
- Filter dropdown: Full width
- Table: Horizontal scroll (min-width: 800px)
- Modal: Full width with padding
- Badges: Stack vertically if needed

## Accessibility

### Keyboard Navigation
- Tab through filter dropdown
- Tab through checkboxes in modal
- Enter to toggle checkboxes
- Escape to close modal

### Screen Readers
- Filter labeled: "Filter by Survey Type"
- Checkboxes labeled with type names
- Badge text includes icon description
- Count updates announced

### Color Contrast
- All badges meet WCAG AA standards
- Text readable on colored backgrounds
- Focus indicators visible

## Animation & Transitions

### Filter Dropdown
- Smooth border color change on focus
- Box shadow appears on focus

### Checkboxes
- Hover effect on checkbox rows
- Background color change on hover

### Badges
- No animation (static display)
- Consistent styling across all types

### Modal
- Fade in animation (0.3s)
- Slide up animation (0.3s)
- Smooth close transition

## Error States

### No Survey Types Loaded
```
┌─────────────────────────────────────────────────────────────┐
│  📋 Survey Types                                             │
│  ⚠️ Unable to load survey types. Please refresh the page.   │
└─────────────────────────────────────────────────────────────┘
```

### API Error
```
Browser Console:
❌ Error loading survey types: Failed to fetch
```

### Empty Filter Result
```
┌──────────────────────────────────────────────────────────────┐
│                                                               │
│                    🔍                                         │
│         No questions match the selected filter                │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

## Best Practices

### For Admins
1. **Use Specific Types**: Assign questions to specific types when possible
2. **Use "All Types" Sparingly**: Only for truly universal questions
3. **Consistent Naming**: Keep question text clear about which type it's for
4. **Regular Review**: Periodically review type assignments

### For Developers
1. **Maintain survey_types.json**: Keep colors and icons consistent
2. **Test Filtering**: Verify filter logic with various combinations
3. **Check Responsiveness**: Test on different screen sizes
4. **Monitor Performance**: Ensure client-side filtering is fast

## Testing Checklist

### Visual Testing
- [ ] All badges display with correct colors
- [ ] Icons are visible and correct
- [ ] Filter dropdown is styled properly
- [ ] Modal checkboxes are aligned
- [ ] Count updates correctly

### Functional Testing
- [ ] Filter works correctly
- [ ] Create saves survey types
- [ ] Edit loads current types
- [ ] "Select All" works
- [ ] Empty selection = all types

### Browser Testing
- [ ] Chrome/Edge
- [ ] Firefox
- [ ] Safari
- [ ] Mobile browsers

### Accessibility Testing
- [ ] Keyboard navigation works
- [ ] Screen reader announces changes
- [ ] Color contrast is sufficient
- [ ] Focus indicators visible

## Common Issues & Solutions

### Issue: Badges not showing colors
**Solution**: Check that survey_types.json has valid hex colors

### Issue: Filter not working
**Solution**: Verify `allQuestions` array is populated on page load

### Issue: Types not saving
**Solution**: Check API request includes `survey_types` field

### Issue: Icons not displaying
**Solution**: Verify Font Awesome CSS is loaded

### Issue: Count not updating
**Solution**: Check `updateSelectedSurveyTypesCount()` is called on change

## Future UI Enhancements

1. **Color Indicators in Filter**
   - Show colored dot next to each type in dropdown
   - Visual consistency with badges

2. **Badge Tooltips**
   - Hover over badge to see full description
   - Show question count for each type

3. **Drag & Drop**
   - Drag questions between types
   - Visual feedback during drag

4. **Bulk Edit**
   - Select multiple questions
   - Assign types to all at once

5. **Type Statistics**
   - Show count of questions per type
   - Visual chart or graph

## Conclusion

The Survey Types UI provides a clean, intuitive interface for managing question assignments. The color-coded badges, filtering capabilities, and multi-select functionality make it easy for admins to organize and find questions by survey type.
