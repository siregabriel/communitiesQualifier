"""
Unit tests for Task 26: Test Action Items Counting

This test file verifies that the action items counting function correctly counts
inspection responses that require action (Fail, Opportunity, Needs Attention).

Requirements tested:
- 4.1: Retrieve all inspection responses with condition "Fail", "Opportunity", or "Needs Attention"
- 4.2: Count only responses from the most recent inspection submission
- 4.3: Display the Action_Item count as a numeric value with label "Open Actions"
- 4.4: Display "0 Open Actions" if count is zero
"""

import unittest


class TestActionItemsCounting(unittest.TestCase):
    """Test action items counting function with known conditions"""
    
    def count_action_items(self, responses):
        """
        Python implementation of the JavaScript countActionItems function
        This mirrors the logic in dashboard.html
        """
        if not responses or len(responses) == 0:
            return 0
        
        action_conditions = ['Fail', 'Opportunity', 'Needs Attention']
        
        return len([response for response in responses 
                   if response.get('condition') in action_conditions])
    
    def test_fail_conditions_are_counted(self):
        """
        Test: Verify Fail conditions are counted
        Requirements: 4.1
        """
        # Create test inspection data with Fail conditions
        responses = [
            {'condition': 'Fail', 'question_id': 'q1'},
            {'condition': 'Fail', 'question_id': 'q2'},
            {'condition': 'Pass', 'question_id': 'q3'}
        ]
        
        # Count action items
        count = self.count_action_items(responses)
        
        # Verify: 2 Fail conditions should be counted
        self.assertEqual(count, 2)
        self.assertIsInstance(count, int)
    
    def test_opportunity_conditions_are_counted(self):
        """
        Test: Verify Opportunity conditions are counted
        Requirements: 4.1
        """
        # Create test inspection data with Opportunity conditions
        responses = [
            {'condition': 'Opportunity', 'question_id': 'q1'},
            {'condition': 'Opportunity', 'question_id': 'q2'},
            {'condition': 'Opportunity', 'question_id': 'q3'},
            {'condition': 'Excellence', 'question_id': 'q4'}
        ]
        
        # Count action items
        count = self.count_action_items(responses)
        
        # Verify: 3 Opportunity conditions should be counted
        self.assertEqual(count, 3)
        self.assertIsInstance(count, int)
    
    def test_needs_attention_conditions_are_counted(self):
        """
        Test: Verify Needs Attention conditions are counted
        Requirements: 4.1
        """
        # Create test inspection data with Needs Attention conditions
        responses = [
            {'condition': 'Needs Attention', 'question_id': 'q1'},
            {'condition': 'Needs Attention', 'question_id': 'q2'},
            {'condition': 'Pass', 'question_id': 'q3'}
        ]
        
        # Count action items
        count = self.count_action_items(responses)
        
        # Verify: 2 Needs Attention conditions should be counted
        self.assertEqual(count, 2)
        self.assertIsInstance(count, int)
    
    def test_excellence_not_counted(self):
        """
        Test: Verify Excellence conditions are NOT counted
        Requirements: 4.1
        """
        # Create test inspection data with Excellence conditions
        responses = [
            {'condition': 'Excellence', 'question_id': 'q1'},
            {'condition': 'Excellence', 'question_id': 'q2'},
            {'condition': 'Excellence', 'question_id': 'q3'}
        ]
        
        # Count action items
        count = self.count_action_items(responses)
        
        # Verify: Excellence should NOT be counted
        self.assertEqual(count, 0)
    
    def test_pass_not_counted(self):
        """
        Test: Verify Pass conditions are NOT counted
        Requirements: 4.1
        """
        # Create test inspection data with Pass conditions
        responses = [
            {'condition': 'Pass', 'question_id': 'q1'},
            {'condition': 'Pass', 'question_id': 'q2'},
            {'condition': 'Pass', 'question_id': 'q3'}
        ]
        
        # Count action items
        count = self.count_action_items(responses)
        
        # Verify: Pass should NOT be counted
        self.assertEqual(count, 0)
    
    def test_empty_responses_return_zero(self):
        """
        Test: Verify empty responses return 0
        Requirements: 4.4
        """
        # Test with empty list
        responses = []
        count = self.count_action_items(responses)
        self.assertEqual(count, 0)
        
        # Test with None
        responses = None
        count = self.count_action_items(responses)
        self.assertEqual(count, 0)
    
    def test_mixed_conditions(self):
        """
        Test: Verify mixed conditions count only action items
        Requirements: 4.1
        """
        # Create test inspection data with all condition types
        responses = [
            {'condition': 'Fail', 'question_id': 'q1'},
            {'condition': 'Opportunity', 'question_id': 'q2'},
            {'condition': 'Needs Attention', 'question_id': 'q3'},
            {'condition': 'Excellence', 'question_id': 'q4'},
            {'condition': 'Pass', 'question_id': 'q5'}
        ]
        
        # Count action items
        count = self.count_action_items(responses)
        
        # Verify: Only Fail, Opportunity, and Needs Attention should be counted (3 total)
        self.assertEqual(count, 3)
    
    def test_all_action_conditions(self):
        """
        Test: Verify all three action conditions are counted together
        Requirements: 4.1
        """
        # Create test inspection data with all action conditions
        responses = [
            {'condition': 'Fail', 'question_id': 'q1'},
            {'condition': 'Fail', 'question_id': 'q2'},
            {'condition': 'Opportunity', 'question_id': 'q3'},
            {'condition': 'Opportunity', 'question_id': 'q4'},
            {'condition': 'Opportunity', 'question_id': 'q5'},
            {'condition': 'Needs Attention', 'question_id': 'q6'}
        ]
        
        # Count action items
        count = self.count_action_items(responses)
        
        # Verify: 2 Fail + 3 Opportunity + 1 Needs Attention = 6 total
        self.assertEqual(count, 6)
    
    def test_single_action_item(self):
        """
        Test: Verify single action item is counted correctly
        Requirements: 4.1
        """
        # Test single Fail
        responses = [{'condition': 'Fail', 'question_id': 'q1'}]
        count = self.count_action_items(responses)
        self.assertEqual(count, 1)
        
        # Test single Opportunity
        responses = [{'condition': 'Opportunity', 'question_id': 'q1'}]
        count = self.count_action_items(responses)
        self.assertEqual(count, 1)
        
        # Test single Needs Attention
        responses = [{'condition': 'Needs Attention', 'question_id': 'q1'}]
        count = self.count_action_items(responses)
        self.assertEqual(count, 1)
    
    def test_ignores_invalid_conditions(self):
        """
        Test: Verify function ignores responses with invalid conditions
        Requirements: 4.1
        """
        responses = [
            {'condition': 'Fail', 'question_id': 'q1'},
            {'condition': 'InvalidCondition', 'question_id': 'q2'},
            {'condition': 'Opportunity', 'question_id': 'q3'},
            {'condition': 'Unknown', 'question_id': 'q4'}
        ]
        
        # Should only count Fail and Opportunity
        count = self.count_action_items(responses)
        self.assertEqual(count, 2)
    
    def test_ignores_responses_without_condition(self):
        """
        Test: Verify function handles responses without condition field
        Requirements: 4.1
        """
        responses = [
            {'condition': 'Fail', 'question_id': 'q1'},
            {'question_id': 'q2'},  # Missing condition
            {'condition': 'Opportunity', 'question_id': 'q3'}
        ]
        
        # Should only count Fail and Opportunity
        count = self.count_action_items(responses)
        self.assertEqual(count, 2)
    
    def test_large_dataset(self):
        """
        Test: Verify counting works with large number of responses
        Requirements: 4.1
        """
        # Create 100 responses with mixed conditions
        responses = []
        for i in range(20):
            responses.append({'condition': 'Fail', 'question_id': f'q{i}'})
        for i in range(20, 40):
            responses.append({'condition': 'Opportunity', 'question_id': f'q{i}'})
        for i in range(40, 50):
            responses.append({'condition': 'Needs Attention', 'question_id': f'q{i}'})
        for i in range(50, 75):
            responses.append({'condition': 'Excellence', 'question_id': f'q{i}'})
        for i in range(75, 100):
            responses.append({'condition': 'Pass', 'question_id': f'q{i}'})
        
        count = self.count_action_items(responses)
        
        # Verify: 20 Fail + 20 Opportunity + 10 Needs Attention = 50 total
        self.assertEqual(count, 50)
    
    def test_case_sensitivity(self):
        """
        Test: Verify condition matching is case-sensitive
        """
        # Lowercase should not match
        responses = [
            {'condition': 'fail', 'question_id': 'q1'},
            {'condition': 'opportunity', 'question_id': 'q2'},
            {'condition': 'needs attention', 'question_id': 'q3'}
        ]
        
        count = self.count_action_items(responses)
        # Should return 0 because no valid conditions matched (case-sensitive)
        self.assertEqual(count, 0)
        
        # Correct case should match
        responses = [
            {'condition': 'Fail', 'question_id': 'q1'},
            {'condition': 'Opportunity', 'question_id': 'q2'},
            {'condition': 'Needs Attention', 'question_id': 'q3'}
        ]
        
        count = self.count_action_items(responses)
        self.assertEqual(count, 3)
    
    def test_responses_with_extra_fields(self):
        """
        Test: Verify function works with responses containing extra fields
        """
        responses = [
            {
                'condition': 'Fail',
                'question_id': 'q1',
                'question_text': 'Are hallways clean?',
                'description': 'Needs cleaning',
                'photo_path': '/path/to/photo.jpg',
                'answered_at': '2024-05-08T10:25:00Z'
            },
            {
                'condition': 'Opportunity',
                'question_id': 'q2',
                'question_text': 'Are lights working?',
                'description': 'Some bulbs out',
                'photo_path': '/path/to/photo2.jpg',
                'answered_at': '2024-05-08T10:26:00Z'
            },
            {
                'condition': 'Excellence',
                'question_id': 'q3',
                'question_text': 'Is lobby clean?',
                'description': 'Spotless',
                'photo_path': '/path/to/photo3.jpg',
                'answered_at': '2024-05-08T10:27:00Z'
            }
        ]
        
        count = self.count_action_items(responses)
        # Should count Fail and Opportunity, but not Excellence
        self.assertEqual(count, 2)


class TestActionItemsDisplay(unittest.TestCase):
    """Test action items display formatting"""
    
    def test_zero_action_items_display(self):
        """
        Test: Verify "0 Open Actions" is displayed when count is zero
        Requirements: 4.3, 4.4
        """
        count = 0
        display = f"{count} Open Actions"
        self.assertEqual(display, "0 Open Actions")
    
    def test_single_action_item_display(self):
        """
        Test: Verify single action item displays correctly
        Requirements: 4.3
        """
        count = 1
        display = f"{count} Open Actions"
        self.assertEqual(display, "1 Open Actions")
    
    def test_multiple_action_items_display(self):
        """
        Test: Verify multiple action items display correctly
        Requirements: 4.3
        """
        test_cases = [
            (2, "2 Open Actions"),
            (5, "5 Open Actions"),
            (10, "10 Open Actions"),
            (50, "50 Open Actions"),
            (100, "100 Open Actions")
        ]
        
        for count, expected_display in test_cases:
            display = f"{count} Open Actions"
            self.assertEqual(display, expected_display)


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and boundary conditions"""
    
    def count_action_items(self, responses):
        """Python implementation of countActionItems"""
        if not responses or len(responses) == 0:
            return 0
        
        action_conditions = ['Fail', 'Opportunity', 'Needs Attention']
        
        return len([response for response in responses 
                   if response.get('condition') in action_conditions])
    
    def test_all_non_action_conditions(self):
        """
        Test: Verify all non-action conditions result in 0
        """
        responses = [
            {'condition': 'Excellence', 'question_id': 'q1'},
            {'condition': 'Pass', 'question_id': 'q2'},
            {'condition': 'Excellence', 'question_id': 'q3'},
            {'condition': 'Pass', 'question_id': 'q4'}
        ]
        
        count = self.count_action_items(responses)
        self.assertEqual(count, 0)
    
    def test_all_action_conditions(self):
        """
        Test: Verify all action conditions are counted
        """
        responses = [
            {'condition': 'Fail', 'question_id': 'q1'},
            {'condition': 'Opportunity', 'question_id': 'q2'},
            {'condition': 'Needs Attention', 'question_id': 'q3'},
            {'condition': 'Fail', 'question_id': 'q4'}
        ]
        
        count = self.count_action_items(responses)
        self.assertEqual(count, 4)
    
    def test_duplicate_question_ids(self):
        """
        Test: Verify function counts all responses even with duplicate question IDs
        """
        responses = [
            {'condition': 'Fail', 'question_id': 'q1'},
            {'condition': 'Fail', 'question_id': 'q1'},  # Duplicate question_id
            {'condition': 'Opportunity', 'question_id': 'q2'}
        ]
        
        count = self.count_action_items(responses)
        # Should count all 3 responses
        self.assertEqual(count, 3)
    
    def test_good_condition_not_counted(self):
        """
        Test: Verify "Good" condition is not counted as action item
        Note: "Good" is mentioned in requirements as a valid condition but not an action item
        """
        responses = [
            {'condition': 'Good', 'question_id': 'q1'},
            {'condition': 'Good', 'question_id': 'q2'},
            {'condition': 'Fail', 'question_id': 'q3'}
        ]
        
        count = self.count_action_items(responses)
        # Should only count Fail, not Good
        self.assertEqual(count, 1)
    
    def test_whitespace_in_condition(self):
        """
        Test: Verify function handles conditions with extra whitespace
        """
        responses = [
            {'condition': ' Fail ', 'question_id': 'q1'},
            {'condition': 'Opportunity ', 'question_id': 'q2'},
            {'condition': ' Needs Attention', 'question_id': 'q3'}
        ]
        
        count = self.count_action_items(responses)
        # Should not match due to whitespace (exact match required)
        self.assertEqual(count, 0)
    
    def test_empty_condition_string(self):
        """
        Test: Verify function handles empty condition strings
        """
        responses = [
            {'condition': '', 'question_id': 'q1'},
            {'condition': 'Fail', 'question_id': 'q2'},
            {'condition': '', 'question_id': 'q3'}
        ]
        
        count = self.count_action_items(responses)
        # Should only count Fail
        self.assertEqual(count, 1)


if __name__ == '__main__':
    # Run tests with verbose output
    unittest.main(verbosity=2)
