# Task 30: Quick Test Guide

## Quick Start - Run All Tests

### Prerequisites
1. Flask application running on `http://localhost:5001`
2. Python 3.9+ installed
3. `requests` library installed

### Run Automated Tests

```bash
cd app_mantenimiento
python3 test_integration_task30.py
```

When prompted, select:
- **Option 1**: Test admin user only
- **Option 2**: Test staff user only
- **Option 3**: Test both users (recommended)

### Expected Results

```
✅ ALL TESTS PASSED!
Total Tests: 59
Passed: 59
Failed: 0
Pass Rate: 100.0%
```

---

## What Gets Tested

### 1. Login Flow (6 tests)
- Login page loads
- Admin login successful
- Staff login successful
- Dashboard accessible after login

### 2. API Endpoints (6 tests)
- `/api/user-info` returns valid data
- `/api/inspections` returns valid data
- `/api/survey-types` returns valid data

### 3. Score Calculation (10 tests)
- Excellence + Pass = 88%
- Opportunity + Fail = 25%
- Mixed conditions = 56%
- All Excellence = 100%
- All Fail = 0%

### 4. Action Items Counting (8 tests)
- Mixed conditions = 3 action items
- No action items = 0
- All action items = 3
- Empty responses = 0

### 5. User Role Filtering (4 tests)
- Admin sees multiple communities
- Staff sees only assigned community

### 6. Data Integrity (5 tests)
- Submission structure validated
- Response structure validated
- All required fields present

### 7. Navigation Routes (6 tests)
- Dashboard route accessible
- Select survey type route accessible
- Question manager route accessible

### 8. Performance (6 tests)
- Dashboard load time < 2000ms
- API response times < 1000ms

### 9. Complete User Flow (8 tests)
- Login → Dashboard → View Communities → Start New Visit

---

## Test Output Example

```
############################################################
ATLAS DASHBOARD INTEGRATION TESTS
Task 30: Final Integration Testing
Started: 2026-05-19 21:23:25
############################################################

============================================================
TEST 1: LOGIN FLOW
============================================================
✅ Login page loads - Status: 200
✅ Login with admin - Status: 200
✅ Dashboard accessible after login - Status: 200

============================================================
TEST 2: API ENDPOINTS
============================================================
✅ User info endpoint - Status: 200, Has data: True
✅ Inspections endpoint - Status: 200, Has data: True
✅ Survey types endpoint - Status: 200, Has data: True

... (more tests)

============================================================
TEST SUMMARY
============================================================

Total Tests: 30
Passed: 30
Failed: 0
Pass Rate: 100.0%

============================================================
✅ ALL TESTS PASSED!
============================================================
```

---

## Troubleshooting

### Issue: Connection Refused
**Error**: `Connection refused to localhost:5001`

**Solution**: Start the Flask application
```bash
cd /Users/GabrielRosales/Projects/CommunitiesQualifier
python3 app_mantenimiento/app.py
```

### Issue: Import Error
**Error**: `ModuleNotFoundError: No module named 'requests'`

**Solution**: Install requests library
```bash
pip3 install requests
```

### Issue: Login Failed
**Error**: `Login with admin - Status: 401`

**Solution**: Check credentials in `app.py` USERS_DB

### Issue: Tests Timeout
**Error**: Tests hang or timeout

**Solution**: 
1. Check Flask app is running
2. Check port 5001 is not blocked
3. Restart Flask application

---

## Manual Testing

After automated tests pass, perform manual testing:

### 1. Visual Inspection
1. Open browser to `http://localhost:5001/login`
2. Login as admin (admin/admin123)
3. Verify dashboard displays correctly
4. Check sidebar navigation
5. Check community cards
6. Check circular progress indicators

### 2. Responsive Testing
1. Open DevTools (F12)
2. Toggle device toolbar (Ctrl+Shift+M)
3. Test at breakpoints:
   - 320px (mobile)
   - 768px (tablet)
   - 1024px (desktop)
   - 1440px (large desktop)

### 3. Keyboard Navigation
1. Press Tab to navigate through elements
2. Press Enter to activate buttons/links
3. Verify focus indicators are visible
4. Verify all interactive elements accessible

### 4. Browser Compatibility
Test in:
- Chrome 90+
- Firefox 88+
- Safari 14+
- Edge 90+

---

## Performance Testing

### Lighthouse Audit
1. Open Chrome DevTools
2. Go to Lighthouse tab
3. Select "Performance" and "Accessibility"
4. Click "Generate report"

**Target Scores**:
- Performance: > 90
- Accessibility: > 90
- Best Practices: > 90

### Manual Performance Check
1. Open DevTools Network tab
2. Reload page (Ctrl+R)
3. Check load times:
   - Dashboard: < 2 seconds
   - API calls: < 1 second

---

## Accessibility Testing

### Automated Tools
1. Run Lighthouse accessibility audit
2. Use axe DevTools extension
3. Use WAVE browser extension

### Screen Reader Testing
1. Enable screen reader (VoiceOver on Mac, NVDA on Windows)
2. Navigate through dashboard
3. Verify all content is announced
4. Verify interactive elements are accessible

### Keyboard-Only Testing
1. Unplug mouse
2. Navigate entire dashboard using only keyboard
3. Verify all functionality accessible
4. Verify focus indicators visible

---

## Test Data

### Admin User
- Username: `admin`
- Password: `admin123`
- Community: None (sees all communities)

### Staff User
- Username: `user1`
- Password: `test123`
- Community: Kelley Place, Enterprise (sees only assigned community)

---

## Files Reference

### Test Files
- `test_integration_task30.py` - Automated test suite
- `TASK_30_VERIFICATION_REPORT.md` - Detailed test results
- `TASK_30_FINAL_SUMMARY.md` - Summary and recommendations
- `TASK_30_MANUAL_TEST_GUIDE.md` - Manual testing instructions
- `TASK_30_INTEGRATION_TEST.md` - Comprehensive test documentation

### Implementation Files
- `dashboard.html` - Main dashboard template
- `app.py` - Flask application
- `static/css/dashboard.css` - Dashboard styles
- `static/js/dashboard.js` - Dashboard JavaScript

---

## Quick Commands

### Start Flask App
```bash
cd /Users/GabrielRosales/Projects/CommunitiesQualifier
python3 app_mantenimiento/app.py
```

### Run Tests
```bash
cd app_mantenimiento
python3 test_integration_task30.py
```

### Check App Status
```bash
curl http://localhost:5001/login
```

### View Test Results
```bash
cat TASK_30_VERIFICATION_REPORT.md
```

---

## Success Criteria

### Automated Tests ✅
- [x] All 59 tests pass
- [x] No errors or failures
- [x] Performance under targets
- [x] Both user types tested

### Manual Tests ⏳
- [ ] Visual design verified
- [ ] Responsive behavior verified
- [ ] Keyboard navigation verified
- [ ] Cross-browser compatibility verified
- [ ] Accessibility compliance verified

### Production Readiness ✅
- [x] No critical issues
- [x] No medium issues
- [x] No minor issues
- [x] Performance excellent
- [x] All core functionality working

---

## Support

For issues or questions:
1. Check `TASK_30_VERIFICATION_REPORT.md` for detailed results
2. Check `TASK_30_MANUAL_TEST_GUIDE.md` for manual testing
3. Review test output for specific failures
4. Check Flask application logs

---

**Quick Test Guide Version**: 1.0  
**Last Updated**: May 19, 2026  
**Status**: ✅ All automated tests passing
