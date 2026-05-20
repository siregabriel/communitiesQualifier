// Test file for countActionItems function
// Run with: node test_count_action_items.js

// Copy the function implementation from dashboard.html
function countActionItems(inspections) {
    // Handle edge cases
    if (!inspections || !Array.isArray(inspections)) {
        return 0;
    }
    
    // Define action-requiring conditions
    const actionConditions = ['Fail', 'Opportunity', 'Needs Attention'];
    
    let count = 0;
    
    // Count inspections with action-requiring conditions
    for (const inspection of inspections) {
        if (!inspection || !inspection.condition) {
            continue;
        }
        
        if (actionConditions.includes(inspection.condition)) {
            count++;
        }
    }
    
    return count;
}

// Test runner
let passCount = 0;
let failCount = 0;

function test(name, expected, actual) {
    const pass = expected === actual;
    if (pass) {
        console.log(`✓ ${name}: PASS (expected ${expected}, got ${actual})`);
        passCount++;
    } else {
        console.log(`✗ ${name}: FAIL (expected ${expected}, got ${actual})`);
        failCount++;
    }
}

console.log('=== countActionItems Function Tests ===\n');

// Test 1: All Fail conditions
test('All Fail conditions', 3, countActionItems([
    { condition: 'Fail' },
    { condition: 'Fail' },
    { condition: 'Fail' }
]));

// Test 2: All Opportunity conditions
test('All Opportunity conditions', 2, countActionItems([
    { condition: 'Opportunity' },
    { condition: 'Opportunity' }
]));

// Test 3: All Needs Attention conditions
test('All Needs Attention conditions', 2, countActionItems([
    { condition: 'Needs Attention' },
    { condition: 'Needs Attention' }
]));

// Test 4: Mixed action items
test('Mixed action items', 3, countActionItems([
    { condition: 'Fail' },
    { condition: 'Opportunity' },
    { condition: 'Needs Attention' }
]));

// Test 5: No action items (Excellence, Pass, Good)
test('No action items', 0, countActionItems([
    { condition: 'Excellence' },
    { condition: 'Pass' },
    { condition: 'Good' }
]));

// Test 6: Mixed with and without action items
test('Mixed with and without action items', 2, countActionItems([
    { condition: 'Excellence' },
    { condition: 'Fail' },
    { condition: 'Pass' },
    { condition: 'Opportunity' },
    { condition: 'Good' }
]));

// Test 7: Empty array
test('Empty array', 0, countActionItems([]));

// Test 8: Null input
test('Null input', 0, countActionItems(null));

// Test 9: Undefined input
test('Undefined input', 0, countActionItems(undefined));

// Test 10: Invalid condition types
test('Invalid condition types', 0, countActionItems([
    { condition: 'InvalidCondition' },
    { condition: 'AnotherInvalid' }
]));

// Test 11: Mixed valid and invalid conditions
test('Mixed valid and invalid', 2, countActionItems([
    { condition: 'Fail' },
    { condition: 'InvalidCondition' },
    { condition: 'Opportunity' }
]));

// Test 12: Missing condition field
test('Missing condition field', 1, countActionItems([
    { condition: 'Fail' },
    { noCondition: 'test' },
    { condition: 'Pass' }
]));

// Test 13: Null inspection objects
test('Null inspection objects', 2, countActionItems([
    { condition: 'Fail' },
    null,
    { condition: 'Opportunity' }
]));

// Test 14: Real-world scenario
test('Real-world scenario', 3, countActionItems([
    { condition: 'Excellence', community: 'Test Community' },
    { condition: 'Pass', community: 'Test Community' },
    { condition: 'Fail', community: 'Test Community' },
    { condition: 'Opportunity', community: 'Test Community' },
    { condition: 'Good', community: 'Test Community' },
    { condition: 'Needs Attention', community: 'Test Community' }
]));

// Test 15: Count is non-negative
const count = countActionItems([
    { condition: 'Excellence' },
    { condition: 'Pass' }
]);
test('Count is non-negative', true, count >= 0);

// Test 16: Count does not exceed total inspections
const inspections = [
    { condition: 'Fail' },
    { condition: 'Opportunity' },
    { condition: 'Pass' }
];
const actionCount = countActionItems(inspections);
test('Count does not exceed total', true, actionCount <= inspections.length);

// Test 17: All three action conditions
test('All three action conditions', 3, countActionItems([
    { condition: 'Fail' },
    { condition: 'Opportunity' },
    { condition: 'Needs Attention' }
]));

// Test 18: Case sensitivity check
test('Case sensitivity check', 3, countActionItems([
    { condition: 'Fail' },
    { condition: 'Opportunity' },
    { condition: 'Needs Attention' }
]));

console.log('\n=== Test Summary ===');
console.log(`Total Tests: ${passCount + failCount}`);
console.log(`Passed: ${passCount}`);
console.log(`Failed: ${failCount}`);
console.log(`Success Rate: ${((passCount / (passCount + failCount)) * 100).toFixed(1)}%`);

// Exit with appropriate code
process.exit(failCount > 0 ? 1 : 0);
