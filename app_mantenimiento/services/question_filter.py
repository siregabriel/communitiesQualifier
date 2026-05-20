"""
Question Filter Service
Filters questions based on survey type
"""

from typing import List, Dict, Optional


class QuestionFilterService:
    """
    Service for filtering questions by survey type
    
    Handles the logic for determining which questions belong to
    which survey types, including backward compatibility for
    questions without survey type assignments.
    """
    
    def __init__(self, question_manager, survey_type_service):
        """
        Initialize the QuestionFilterService
        
        Args:
            question_manager: Instance of QuestionManager service
            survey_type_service: Instance of SurveyTypeService
        """
        self.question_manager = question_manager
        self.survey_type_service = survey_type_service
    
    def filter_by_survey_type(self, questions: List[Dict], survey_type_id: str) -> List[Dict]:
        """
        Filter questions by survey type
        
        Filtering Rules:
        1. If question has empty survey_types array, include in all types
        2. If question has survey_types array with values, check if survey_type_id is in it
        3. If question doesn't have survey_types field, include in all types (backward compatibility)
        
        Args:
            questions: List of question dictionaries
            survey_type_id: The survey type ID to filter by
            
        Returns:
            List of questions that belong to the specified survey type
            
        Example:
            >>> questions = [
            ...     {"id": "q1", "text": "Question 1", "survey_types": ["full-regional"]},
            ...     {"id": "q2", "text": "Question 2", "survey_types": []},
            ...     {"id": "q3", "text": "Question 3"}  # No survey_types field
            ... ]
            >>> filtered = service.filter_by_survey_type(questions, "full-regional")
            >>> len(filtered)
            3  # All three questions are included
        """
        if not questions:
            return []
        
        # Validate survey type
        if not self.survey_type_service.validate_survey_type(survey_type_id):
            raise ValueError(f"Invalid survey type ID: {survey_type_id}")
        
        filtered = []
        
        for question in questions:
            # Get survey_types field (default to empty list if not present)
            survey_types = question.get('survey_types', [])
            
            # Rule 1 & 3: Empty array or missing field = belongs to all types
            if not survey_types:
                filtered.append(question)
            # Rule 2: Check if survey type is in the list
            elif survey_type_id in survey_types:
                filtered.append(question)
        
        return filtered
    
    def get_questions_for_survey(self, community: str, survey_type_id: str) -> List[Dict]:
        """
        Get questions for a specific community and survey type
        
        This is the main method used by the application to get the
        appropriate questions for a user's inspection.
        
        Args:
            community: The community name
            survey_type_id: The survey type ID
            
        Returns:
            List of questions filtered by community and survey type
            
        Raises:
            ValueError: If survey type ID is invalid
            
        Example:
            >>> questions = service.get_questions_for_survey(
            ...     "Community A",
            ...     "full-regional"
            ... )
            >>> len(questions)
            10
        """
        # Validate survey type first
        if not self.survey_type_service.validate_survey_type(survey_type_id):
            raise ValueError(f"Invalid survey type ID: {survey_type_id}")
        
        # Get all questions for the community
        all_questions = self.question_manager.get_questions_for_community(community)
        
        # Filter by survey type
        filtered_questions = self.filter_by_survey_type(all_questions, survey_type_id)
        
        return filtered_questions
    
    def get_question_survey_types(self, question: Dict) -> List[str]:
        """
        Get the list of survey types a question belongs to
        
        Args:
            question: Question dictionary
            
        Returns:
            List of survey type IDs, or empty list if question belongs to all types
            
        Example:
            >>> question = {"id": "q1", "survey_types": ["full-regional", "operational"]}
            >>> types = service.get_question_survey_types(question)
            >>> types
            ["full-regional", "operational"]
        """
        return question.get('survey_types', [])
    
    def question_belongs_to_survey_type(self, question: Dict, survey_type_id: str) -> bool:
        """
        Check if a specific question belongs to a survey type
        
        Args:
            question: Question dictionary
            survey_type_id: Survey type ID to check
            
        Returns:
            True if question belongs to the survey type, False otherwise
            
        Example:
            >>> question = {"id": "q1", "survey_types": ["full-regional"]}
            >>> service.question_belongs_to_survey_type(question, "full-regional")
            True
            >>> service.question_belongs_to_survey_type(question, "operational")
            False
        """
        survey_types = question.get('survey_types', [])
        
        # Empty or missing = belongs to all types
        if not survey_types:
            return True
        
        return survey_type_id in survey_types
    
    def get_questions_count_by_survey_type(self, community: str) -> Dict[str, int]:
        """
        Get count of questions for each survey type in a community
        
        Args:
            community: The community name
            
        Returns:
            Dictionary mapping survey type IDs to question counts
            
        Example:
            >>> counts = service.get_questions_count_by_survey_type("Community A")
            >>> counts
            {
                "full-regional": 15,
                "operational": 10,
                "sales-marketing": 8,
                ...
            }
        """
        all_questions = self.question_manager.get_questions_for_community(community)
        all_survey_types = self.survey_type_service.get_survey_type_ids()
        
        counts = {}
        for survey_type_id in all_survey_types:
            filtered = self.filter_by_survey_type(all_questions, survey_type_id)
            counts[survey_type_id] = len(filtered)
        
        return counts
    
    def validate_questions_exist(self, community: str, survey_type_id: str) -> bool:
        """
        Check if any questions exist for a community and survey type combination
        
        Args:
            community: The community name
            survey_type_id: The survey type ID
            
        Returns:
            True if at least one question exists, False otherwise
            
        Example:
            >>> service.validate_questions_exist("Community A", "full-regional")
            True
        """
        try:
            questions = self.get_questions_for_survey(community, survey_type_id)
            return len(questions) > 0
        except ValueError:
            return False
