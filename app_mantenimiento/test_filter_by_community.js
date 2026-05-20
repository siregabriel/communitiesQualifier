/**
 * Unit Tests for filterByCommunity Function
 * Task 2.1: Create filterByCommunity function
 */

// Copy the function implementation
function filterByCommunity(inspections, communityName) {
    // Handle edge cases
    if (!inspections || !Array.isArray(inspections)) {
        return [];
    }
    
    if (!communityName || typeof communityName !== 'string' || communityName.trim() === '') {
        return [];
    }
    
    // Filter inspections that match the specified community name
    return inspections.filter(inspection => {
        // Handle null/undefined inspection or community field
        if (!inspection || !inspection.community) {
            return false;
        }
        
        // Case-sensitive exact match
        return inspection.community === communityName;
    });
}

// Test data
const testInspections = [
    { id: 1, community: 'Kelley Place, Enterprise', condition: 'Pass', questionText: 'Test 1' },
    { id: 2, community: 'Madison Heights Enterprise, Enterprise', condition: 'Fail', questionText: 'Test 2' },
    { id: 3, community: 'Kelley Place, Enterprise', condition: 'Excellence', questionText: 'Test 3' },
    { id: 4, community: 'Monark Grove Madison', condition: 'Opportunity', questionText: 'Test 4' },
    { id: 5, community: 'Kelley Place, Enterprise', condition: 'Pass', questionText: 'Test 5' },
    { id: 6, community: null, condition: 'Pass', questionText: 'Test 6' },
];

// Test 1: Filter by valid community name
console.log('Test 1: Filter by valid community name');
const result1 = filterByCommunity(testInspections, 'Kelley Place, Enterprise');
console.log('Expected: 3 inspections');
console.log('Actual:', result1.length);
console.log('Pass:', result1.length === 3 && result1.every(i => i.community === 'Kelley Place, Enterprise'));
console.log('');

// Test 2: Filter by community with no matches
console.log('Test 2: Filter by community with no matches');
const result2 = filterByCommunity(testInspections, 'Nonexistent Community');
console.log('Expected: 0 inspections');
console.log('Actual:', result2.length);
console.log('Pass:', result2.length === 0);
console.log('');

// Test 3: Empty array input
console.log('Test 3: Empty array input');
const result3 = filterByCommunity([], 'Kelley Place, Enterprise');
console.log('Expected: 0 inspections');
console.log('Actual:', result3.length);
console.log('Pass:', result3.length === 0);
console.log('');

// Test 4: Null inspections array
console.log('Test 4: Null inspections array');
const result4 = filterByCommunity(null, 'Kelley Place, Enterprise');
console.log('Expected: 0 inspections (empty array)');
console.log('Actual:', result4.length);
console.log('Pass:', result4.length === 0);
console.log('');

// Test 5: Undefined inspections array
console.log('Test 5: Undefined inspections array');
const result5 = filterByCommunity(undefined, 'Kelley Place, Enterprise');
console.log('Expected: 0 inspections (empty array)');
console.log('Actual:', result5.length);
console.log('Pass:', result5.length === 0);
console.log('');

// Test 6: Empty community name
console.log('Test 6: Empty community name');
const result6 = filterByCommunity(testInspections, '');
console.log('Expected: 0 inspections');
console.log('Actual:', result6.length);
console.log('Pass:', result6.length === 0);
console.log('');

// Test 7: Null community name
console.log('Test 7: Null community name');
const result7 = filterByCommunity(testInspections, null);
console.log('Expected: 0 inspections');
console.log('Actual:', result7.length);
console.log('Pass:', result7.length === 0);
console.log('');

// Test 8: Whitespace-only community name
console.log('Test 8: Whitespace-only community name');
const result8 = filterByCommunity(testInspections, '   ');
console.log('Expected: 0 inspections');
console.log('Actual:', result8.length);
console.log('Pass:', result8.length === 0);
console.log('');

// Test 9: Inspections with null community field
console.log('Test 9: Inspections with null community field');
const result9 = filterByCommunity(testInspections, 'Kelley Place, Enterprise');
console.log('Expected: Should not include inspection with null community');
console.log('Actual:', result9.length, 'inspections');
console.log('Pass:', result9.every(i => i.community !== null));
console.log('');

// Test 10: Case sensitivity
console.log('Test 10: Case sensitivity');
const result10 = filterByCommunity(testInspections, 'kelley place, enterprise');
console.log('Expected: 0 inspections (case-sensitive match)');
console.log('Actual:', result10.length);
console.log('Pass:', result10.length === 0);
console.log('');

// Test 11: Multiple communities
console.log('Test 11: Filter different community');
const result11 = filterByCommunity(testInspections, 'Madison Heights Enterprise, Enterprise');
console.log('Expected: 1 inspection');
console.log('Actual:', result11.length);
console.log('Pass:', result11.length === 1 && result11[0].id === 2);
console.log('');

// Summary
console.log('=== Test Summary ===');
console.log('All tests completed. Review results above.');
console.log('Function handles:');
console.log('✓ Valid community names');
console.log('✓ Empty arrays');
console.log('✓ Null/undefined inputs');
console.log('✓ Empty/whitespace community names');
console.log('✓ Null community fields in inspections');
console.log('✓ Case-sensitive matching');
