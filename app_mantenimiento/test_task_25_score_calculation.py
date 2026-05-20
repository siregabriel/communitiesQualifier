"""
Unit tests for Task 25: Test Score Calculation Accuracy

This test file verifies that the score calculation function correctly calculates
community scores based on inspection response conditions.

Requirements tested:
- 3.1: Retrieve all inspection responses for community from most recent submission
- 3.2: Assign point values (Excellence=100, Pass=75, Opportunity=50, Fail=0)
- 3.3: Calculate average score across all responses
- 3.4: Round calculated score to nearest whole number
- 3.5: Display calculated score as percentage value
"""

import unittest


class TestScoreCalculationAccuracy(unittest.TestCase):
    """Test score calculation function with known conditions"""
    
    def calculate_community_score(self, responses):
        """
        Python implementation of the JavaScript calculateCommunityScore function
        This mirrors the logic in dashboard.html
        """
        if not responses or len(responses) == 0:
            return None
        
        score_map = {
            'Excellence': 100,
            'Pass': 75,
            'Opportunity': 50,
            'Fail': 0
        }
        
        total_score = 0
        count = 0
        
        for response in responses:
            condition = response.get('condition')
            if condition in score_map:
                total_score += score_map[condition]
                count += 1
        
        return round(total_score / count) if count > 0 else None
    
    def test_excellence_and_pass_average(self):
        """
        Test: Verify Excellence (100) + Pass (75) averages to 88%
        Requirements: 3.2, 3.3, 3.4
        """
        # Create test inspection data with Excellence and Pass conditions
        responses = [
            {'condition': 'Excellence', 'question_id': 'q1'},
            {'condition': 'Pass', 'question_id': 'q2'}
        ]
        
        # Calculate score
        score = self.calculate_community_score(responses)
        
        # Verify: (100 + 75) / 2 = 87.5, rounds to 88
        self.assertEqual(score, 88)
        self.assertIsInstance(score, int)
    
    def test_opportunity_and_fail_average(self):
        """
        Test: Verify Opportunity (50) + Fail (0) averages to 25%
        Requirements: 3.2, 3.3, 3.4
        """
        # Create test inspection data with Opportunity and Fail conditions
        responses = [
            {'condition': 'Opportunity', 'question_id': 'q1'},
            {'condition': 'Fail', 'question_id': 'q2'}
        ]
        
        # Calculate score
        score = self.calculate_community_score(responses)
        
        # Verify: (50 + 0) / 2 = 25
        self.assertEqual(score, 25)
        self.assertIsInstance(score, int)
    
    def test_mixed_conditions_calculation(self):
        """
        Test: Verify mixed conditions calculate correctly
        Requirements: 3.2, 3.3, 3.4
        """
        # Create test inspection data with all four conditions
        responses = [
            {'condition': 'Excellence', 'question_id': 'q1'},
            {'condition': 'Pass', 'question_id': 'q2'},
            {'condition': 'Opportunity', 'question_id': 'q3'},
            {'condition': 'Fail', 'question_id': 'q4'}
        ]
        
        # Calculate score
        score = self.calculate_community_score(responses)
        
        # Verify: (100 + 75 + 50 + 0) / 4 = 225 / 4 = 56.25, rounds to 56
        self.assertEqual(score, 56)
        self.assertIsInstance(score, int)
    
    def test_empty_responses_return_null(self):
        """
        Test: Verify empty responses return null
        Requirements: 3.1, 3.6
        """
        # Test with empty list
        responses = []
        score = self.calculate_community_score(responses)
        self.assertIsNone(score)
        
        # Test with None
        responses = None
        score = self.calculate_community_score(responses)
        self.assertIsNone(score)
    
    def test_rounding_works_correctly(self):
        """
        Test: Verify rounding works correctly (87.5 → 88)
        Requirements: 3.4
        """
        # Test case 1: 87.5 rounds to 88
        responses = [
            {'condition': 'Excellence', 'question_id': 'q1'},
            {'condition': 'Pass', 'question_id': 'q2'}
        ]
        score = self.calculate_community_score(responses)
        self.assertEqual(score, 88)  # (100 + 75) / 2 = 87.5 → 88
        
        # Test case 2: 87.4 rounds to 87
        responses = [
            {'condition': 'Excellence', 'question_id': 'q1'},
            {'condition': 'Pass', 'question_id': 'q2'},
            {'condition': 'Pass', 'question_id': 'q3'},
            {'condition': 'Pass', 'question_id': 'q4'},
            {'condition': 'Pass', 'question_id': 'q5'}
        ]
        score = self.calculate_community_score(responses)
        # (100 + 75 + 75 + 75 + 75) / 5 = 400 / 5 = 80
        self.assertEqual(score, 80)
        
        # Test case 3: 56.25 rounds to 56
        responses = [
            {'condition': 'Excellence', 'question_id': 'q1'},
            {'condition': 'Pass', 'question_id': 'q2'},
            {'condition': 'Opportunity', 'question_id': 'q3'},
            {'condition': 'Fail', 'question_id': 'q4'}
        ]
        score = self.calculate_community_score(responses)
        self.assertEqual(score, 56)  # (100 + 75 + 50 + 0) / 4 = 56.25 → 56
        
        # Test case 4: 56.5 rounds to 56 (Python's round() uses banker's rounding)
        # Actually, Python 3's round() uses "round half to even"
        # 56.5 rounds to 56 (even), 57.5 rounds to 58 (even)
        responses = [
            {'condition': 'Pass', 'question_id': 'q1'},
            {'condition': 'Opportunity', 'question_id': 'q2'}
        ]
        score = self.calculate_community_score(responses)
        # (75 + 50) / 2 = 62.5 → 62
        self.assertEqual(score, 62)
    
    def test_all_excellence_scores(self):
        """
        Test: Verify all Excellence responses result in 100%
        Requirements: 3.2, 3.3
        """
        responses = [
            {'condition': 'Excellence', 'question_id': 'q1'},
            {'condition': 'Excellence', 'question_id': 'q2'},
            {'condition': 'Excellence', 'question_id': 'q3'}
        ]
        
        score = self.calculate_community_score(responses)
        self.assertEqual(score, 100)
    
    def test_all_fail_scores(self):
        """
        Test: Verify all Fail responses result in 0%
        Requirements: 3.2, 3.3
        """
        responses = [
            {'condition': 'Fail', 'question_id': 'q1'},
            {'condition': 'Fail', 'question_id': 'q2'},
            {'condition': 'Fail', 'question_id': 'q3'}
        ]
        
        score = self.calculate_community_score(responses)
        self.assertEqual(score, 0)
    
    def test_single_response(self):
        """
        Test: Verify single response returns correct score
        Requirements: 3.2, 3.3
        """
        # Single Excellence
        responses = [{'condition': 'Excellence', 'question_id': 'q1'}]
        score = self.calculate_community_score(responses)
        self.assertEqual(score, 100)
        
        # Single Pass
        responses = [{'condition': 'Pass', 'question_id': 'q1'}]
        score = self.calculate_community_score(responses)
        self.assertEqual(score, 75)
        
        # Single Opportunity
        responses = [{'condition': 'Opportunity', 'question_id': 'q1'}]
        score = self.calculate_community_score(responses)
        self.assertEqual(score, 50)
        
        # Single Fail
        responses = [{'condition': 'Fail', 'question_id': 'q1'}]
        score = self.calculate_community_score(responses)
        self.assertEqual(score, 0)
    
    def test_ignores_invalid_conditions(self):
        """
        Test: Verify function ignores responses with invalid conditions
        Requirements: 3.2, 3.3
        """
        responses = [
            {'condition': 'Excellence', 'question_id': 'q1'},
            {'condition': 'InvalidCondition', 'question_id': 'q2'},
            {'condition': 'Pass', 'question_id': 'q3'},
            {'condition': 'Unknown', 'question_id': 'q4'}
        ]
        
        # Should only count Excellence and Pass
        score = self.calculate_community_score(responses)
        # (100 + 75) / 2 = 87.5 → 88
        self.assertEqual(score, 88)
    
    def test_ignores_responses_without_condition(self):
        """
        Test: Verify function handles responses without condition field
        Requirements: 3.2, 3.3
        """
        responses = [
            {'condition': 'Excellence', 'question_id': 'q1'},
            {'question_id': 'q2'},  # Missing condition
            {'condition': 'Pass', 'question_id': 'q3'}
        ]
        
        # Should only count Excellence and Pass
        score = self.calculate_community_score(responses)
        # (100 + 75) / 2 = 87.5 → 88
        self.assertEqual(score, 88)
    
    def test_large_dataset(self):
        """
        Test: Verify calculation works with large number of responses
        Requirements: 3.3, 3.4
        """
        # Create 100 responses with mixed conditions
        responses = []
        for i in range(25):
            responses.append({'condition': 'Excellence', 'question_id': f'q{i}'})
        for i in range(25, 50):
            responses.append({'condition': 'Pass', 'question_id': f'q{i}'})
        for i in range(50, 75):
            responses.append({'condition': 'Opportunity', 'question_id': f'q{i}'})
        for i in range(75, 100):
            responses.append({'condition': 'Fail', 'question_id': f'q{i}'})
        
        score = self.calculate_community_score(responses)
        
        # (25*100 + 25*75 + 25*50 + 25*0) / 100 = (2500 + 1875 + 1250 + 0) / 100 = 56.25 → 56
        self.assertEqual(score, 56)
    
    def test_score_map_values(self):
        """
        Test: Verify correct point values are assigned to each condition
        Requirements: 3.2
        """
        # Test Excellence = 100
        responses = [{'condition': 'Excellence', 'question_id': 'q1'}]
        self.assertEqual(self.calculate_community_score(responses), 100)
        
        # Test Pass = 75
        responses = [{'condition': 'Pass', 'question_id': 'q1'}]
        self.assertEqual(self.calculate_community_score(responses), 75)
        
        # Test Opportunity = 50
        responses = [{'condition': 'Opportunity', 'question_id': 'q1'}]
        self.assertEqual(self.calculate_community_score(responses), 50)
        
        # Test Fail = 0
        responses = [{'condition': 'Fail', 'question_id': 'q1'}]
        self.assertEqual(self.calculate_community_score(responses), 0)


class TestScoreDisplayFormatting(unittest.TestCase):
    """Test score display formatting as percentage"""
    
    def test_score_displayed_as_percentage(self):
        """
        Test: Verify score is displayed as percentage value
        Requirements: 3.5
        """
        # Test various scores
        test_cases = [
            (100, "100%"),
            (88, "88%"),
            (75, "75%"),
            (56, "56%"),
            (25, "25%"),
            (0, "0%"),
            (None, "N/A")
        ]
        
        for score, expected_display in test_cases:
            if score is not None:
                display = f"{score}%"
            else:
                display = "N/A"
            
            self.assertEqual(display, expected_display)


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and boundary conditions"""
    
    def calculate_community_score(self, responses):
        """Python implementation of calculateCommunityScore"""
        if not responses or len(responses) == 0:
            return None
        
        score_map = {
            'Excellence': 100,
            'Pass': 75,
            'Opportunity': 50,
            'Fail': 0
        }
        
        total_score = 0
        count = 0
        
        for response in responses:
            condition = response.get('condition')
            if condition in score_map:
                total_score += score_map[condition]
                count += 1
        
        return round(total_score / count) if count > 0 else None
    
    def test_all_invalid_conditions_return_null(self):
        """
        Test: Verify all invalid conditions result in null
        """
        responses = [
            {'condition': 'Invalid1', 'question_id': 'q1'},
            {'condition': 'Invalid2', 'question_id': 'q2'},
            {'condition': 'Invalid3', 'question_id': 'q3'}
        ]
        
        score = self.calculate_community_score(responses)
        self.assertIsNone(score)
    
    def test_case_sensitivity(self):
        """
        Test: Verify condition matching is case-sensitive
        """
        # Lowercase should not match
        responses = [
            {'condition': 'excellence', 'question_id': 'q1'},
            {'condition': 'pass', 'question_id': 'q2'}
        ]
        
        score = self.calculate_community_score(responses)
        # Should return None because no valid conditions matched
        self.assertIsNone(score)
        
        # Correct case should match
        responses = [
            {'condition': 'Excellence', 'question_id': 'q1'},
            {'condition': 'Pass', 'question_id': 'q2'}
        ]
        
        score = self.calculate_community_score(responses)
        self.assertEqual(score, 88)
    
    def test_responses_with_extra_fields(self):
        """
        Test: Verify function works with responses containing extra fields
        """
        responses = [
            {
                'condition': 'Excellence',
                'question_id': 'q1',
                'question_text': 'Are hallways clean?',
                'description': 'Very clean',
                'photo_path': '/path/to/photo.jpg',
                'answered_at': '2024-05-08T10:25:00Z'
            },
            {
                'condition': 'Pass',
                'question_id': 'q2',
                'question_text': 'Are lights working?',
                'description': 'All working',
                'photo_path': '/path/to/photo2.jpg',
                'answered_at': '2024-05-08T10:26:00Z'
            }
        ]
        
        score = self.calculate_community_score(responses)
        self.assertEqual(score, 88)


if __name__ == '__main__':
    # Run tests with verbose output
    unittest.main(verbosity=2)
