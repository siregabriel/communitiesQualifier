# Task 30: Quick Start Guide

## Running Automated Tests

### Prerequisites
1. Flask server running on port 5001
2. Python 3.x installed
3. `requests` library installed

### Start Server
```bash
cd app_mantenimiento
python3 app.py
```

### Run Tests
```bash
cd app_mantenimiento
python3 test_integration_task30.py
```

### Test Options
1. **Admin user only** - Tests admin functionality
2. **Staff user only** - Tests staff functionality  
3. **Both users** - Comprehensive test suite (recommended)

### Expected Output
```
✅ ALL TESTS PASSED!
Total Tests: 59
Passed: 59
Failed: 0
Pass Rate: 100.0%
```

---

## Manual Testing

### Quick Manual Test
1. Open browser: `http://localhost:5001/login`
2. Login as admin: `admin` / `admin123`
3. Verify dashboard displays correctly
4. Test responsive design (F12 → Responsive Mode)
5. Test keyboard navigation (Tab key)
6. Check console for errors (F12 → Console)

### Full Manual Test
Follow: `TASK_30_MANUAL_TEST_GUIDE.md`

---

## Test Files

| File | Purpose |
|------|---------|
| `test_integration_task30.py` | Automated test suite |
| `TASK_30_MANUAL_TEST_GUIDE.md` | Manual testing checklist |
| `TASK_30_INTEGRATION_TEST.md` | Comprehensive test documentation |
| `TASK_30_COMPLETION_SUMMARY.md` | Test results and summary |

---

## Quick Checks

### ✅ Automated Tests
- [x] Login flow
- [x] API endpoints
- [x] Score calculation
- [x] Action items counting
- [x] User role filtering
- [x] Data integrity
- [x] Navigation routes
- [x] Performance
- [x] Complete user flow

### ⏳ Manual Tests Required
- [ ] Responsive design (320px, 768px, 1024px, 1440px)
- [ ] Keyboard navigation
- [ ] Cross-browser compatibility
- [ ] Accessibility compliance
- [ ] Visual design consistency

---

## Test Accounts

| Username | Password | Role | Community |
|----------|----------|------|-----------|
| admin | admin123 | Admin | All communities |
| user1 | test123 | Staff | Kelley Place, Enterprise |

---

## Common Issues

### Port 5000 in use
**Solution:** App runs on port 5001 (not 5000)

### Tests fail to connect
**Solution:** Ensure Flask server is running

### Import errors
**Solution:** Install requests: `pip3 install requests`

---

## Quick Commands

```bash
# Start server
cd app_mantenimiento && python3 app.py

# Run tests (in new terminal)
cd app_mantenimiento && python3 test_integration_task30.py

# View test results
cat TASK_30_COMPLETION_SUMMARY.md

# View manual test guide
cat TASK_30_MANUAL_TEST_GUIDE.md
```

---

## Test Status

**Automated:** ✅ 59/59 passed (100%)  
**Manual:** ⏳ Pending  
**Overall:** ⏳ In Progress

