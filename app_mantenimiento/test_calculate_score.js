// Test file for calculateScore function
// Run with: node test_calculate_score.js

// Copy the function implementation from dashboard.html
function calculateScore(inspections) {
    // Handle edge cases
    if (!inspections || !Array.isArray(inspections)) {
        return null;
    }
    
    if (inspections.length === 0) {
        return null;
    }
    
    // Map condition types to numeric scores
    function getConditionScore(condition) {
        const scoreMap = {
            'Excellence': 100,
            'Pass': 75,
            'Good': 75,
            'Opportunity': 50,
            'Needs Attention': 25,
            'Fail': 0
        };
        
        return scoreMap[condition] !== undefined ? scoreMap[condition] : null;
    }
    
    let totalScore = 0;
    let scoredCount = 0;
    
    // Calculate total score from all inspections with valid conditions
    for (const inspection of inspections) {
        if (!inspection || !inspection.condition) {
            continue;
        }
        
        const conditionScore = getConditionScore(inspection.condition);
        
        if (conditionScore !== null) {
            totalScore += conditionScore;
            scoredCount++;
        }
    }
    
    // Return null if no scoreable inspections exist
    if (scoredCount === 0) {
        return null;
    }
    
    // Calculate average and round to nearest integer
    const averageScore = totalScore / scoredCount;
    return Math.round(averageScore);
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

console.log('=== calculateScore Function Tests ===\n');

// Test 1: All Excellence conditions
test('All Excellence conditions', 100, calculateScore([
    { condition: 'Excellence' },
    { condition: 'Excellence' },
    { condition: 'Excellence' }
]));

// Test 2: All Fail conditions
test('All Fail conditions', 0, calculateScore([
    { condition: 'Fail' },
    { condition: 'Fail' }
]));

// Test 3: Mixed Excellence and Fail
test('Mixed Excellence and Fail', 50, calculateScore([
    { condition: 'Excellence' },
    { condition: 'Fail' }
]));

// Test 4: Pass and Good conditions
test('Pass and Good conditions', 75, calculateScore([
    { condition: 'Pass' },
    { condition: 'Good' }
]));

// Test 5: Opportunity condition
test('Opportunity condition', 50, calculateScore([
    { condition: 'Opportunity' }
]));

// Test 6: Needs Attention condition
test('Needs Attention condition', 25, calculateScore([
    { condition: 'Needs Attention' }
]));

// Test 7: Empty array
test('Empty array', null, calculateScore([]));

// Test 8: Null input
test('Null input', null, calculateScore(null));

// Test 9: Undefined input
test('Undefined input', null, calculateScore(undefined));

// Test 10: Invalid condition types
test('Invalid condition types', null, calculateScore([
    { condition: 'InvalidCondition' },
    { condition: 'AnotherInvalid' }
]));

// Test 11: Mixed valid and invalid conditions
test('Mixed valid and invalid', 50, calculateScore([
    { condition: 'Excellence' },
    { condition: 'InvalidCondition' },
    { condition: 'Fail' }
]));

// Test 12: Missing condition field
test('Missing condition field', 88, calculateScore([
    { condition: 'Excellence' },
    { noCondition: 'test' },
    { condition: 'Pass' }
]));

// Test 13: Null inspection objects
test('Null inspection objects', 50, calculateScore([
    { condition: 'Excellence' },
    null,
    { condition: 'Fail' }
]));

// Test 14: Rounding test
test('Rounding test', 83, calculateScore([
    { condition: 'Excellence' }, // 100
    { condition: 'Pass' },       // 75
    { condition: 'Pass' }        // 75
]));

// Test 15: Real-world scenario
test('Real-world scenario', 60, calculateScore([
    { condition: 'Excellence' },
    { condition: 'Pass' },
    { condition: 'Good' },
    { condition: 'Opportunity' },
    { condition: 'Fail' }
]));

// Test 16: Score range validation
const score = calculateScore([
    { condition: 'Excellence' },
    { condition: 'Good' },
    { condition: 'Opportunity' },
    { condition: 'Needs Attention' },
    { condition: 'Fail' }
]);
const inRange = score !== null && score >= 0 && score <= 100;
test('Score range validation (0-100)', true, inRange);

// Test 17: All condition types average
test('All condition types average', 54, calculateScore([
    { condition: 'Excellence' },   // 100
    { condition: 'Pass' },         // 75
    { condition: 'Good' },         // 75
    { condition: 'Opportunity' },  // 50
    { condition: 'Needs Attention' }, // 25
    { condition: 'Fail' }          // 0
])); // (100+75+75+50+25+0)/6 = 325/6 = 54.166... rounds to 54

console.log('\n=== Test Summary ===');
console.log(`Total Tests: ${passCount + failCount}`);
console.log(`Passed: ${passCount}`);
console.log(`Failed: ${failCount}`);
console.log(`Success Rate: ${((passCount / (passCount + failCount)) * 100).toFixed(1)}%`);

// Exit with appropriate code
process.exit(failCount > 0 ? 1 : 0);
