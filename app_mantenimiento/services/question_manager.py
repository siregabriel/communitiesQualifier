"""
Question Manager Service
Handles CRUD operations for inspection questions with JSON persistence
"""

import json
import os
import time
import random
from datetime import datetime
from typing import List, Dict, Optional


class QuestionManager:
    """
    Manages inspection questions with JSON file-based storage.
    Supports CRUD operations, community-based filtering, and soft deletes.
    """

    def __init__(self, storage_path: str):
        """
        Initialize QuestionManager with path to questions.json
        
        Args:
            storage_path: Absolute path to the questions.json file
        """
        self.storage_path = storage_path
        self.questions = []
        self.version = "1.0"
        self.last_modified = None
        
        # Load existing questions if file exists
        if os.path.exists(storage_path):
            self.load_from_file()

    def create_question(self, text: str, photo_required: bool, communities: List[str]) -> Dict:
        """
        Create new question with validation
        
        Args:
            text: Question text (required, non-empty after stripping)
            photo_required: Whether photo upload is required
            communities: Array of community names (required, non-empty)
            
        Returns:
            Dict containing the created question
            
        Raises:
            ValueError: If validation fails
        """
        # Validate question text
        if not text or not text.strip():
            raise ValueError("Question text cannot be empty")
        
        # Validate communities array
        if not communities or len(communities) == 0:
            raise ValueError("At least one community must be selected")
        
        # Generate unique ID using timestamp and random number
        question_id = f"q_{int(time.time() * 1000)}_{random.randint(1000, 9999)}"
        
        # Create timestamp in ISO 8601 format
        now = datetime.now().isoformat()
        
        # Create question object
        question = {
            "id": question_id,
            "text": text.strip(),
            "photo_required": photo_required,
            "communities": communities,
            "created_at": now,
            "updated_at": now,
            "is_active": True
        }
        
        # Add to questions list
        self.questions.append(question)
        
        # Save to file
        self.save_to_file()
        
        return question

    def get_question(self, question_id: str) -> Optional[Dict]:
        """
        Retrieve question by ID
        
        Args:
            question_id: Unique question identifier
            
        Returns:
            Question dict if found, None otherwise
        """
        for question in self.questions:
            if question["id"] == question_id:
                return question
        return None

    def get_all_active_questions(self) -> List[Dict]:
        """
        Retrieve all active questions
        
        Returns:
            List of active question dicts, sorted by created_at descending (newest first)
        """
        active_questions = [q for q in self.questions if q.get("is_active", True)]
        
        # Sort by created_at descending (newest first)
        active_questions.sort(key=lambda q: q.get("created_at", ""), reverse=True)
        
        return active_questions

    def get_questions_for_community(self, community: str) -> List[Dict]:
        """
        Retrieve active questions assigned to specific community
        
        Args:
            community: Community name to filter by
            
        Returns:
            List of active question dicts for the specified community,
            sorted by created_at descending (newest first)
        """
        community_questions = [
            q for q in self.questions 
            if q.get("is_active", True) and community in q.get("communities", [])
        ]
        
        # Sort by created_at descending (newest first)
        community_questions.sort(key=lambda q: q.get("created_at", ""), reverse=True)
        
        return community_questions

    def update_question(self, question_id: str, text: str, photo_required: bool, 
                       communities: List[str]) -> Optional[Dict]:
        """
        Update existing question, preserving ID and created_at timestamp
        
        Args:
            question_id: Unique question identifier
            text: Updated question text (required, non-empty after stripping)
            photo_required: Updated photo requirement flag
            communities: Updated array of community names (required, non-empty)
            
        Returns:
            Updated question dict if found, None otherwise
            
        Raises:
            ValueError: If validation fails
        """
        # Validate question text
        if not text or not text.strip():
            raise ValueError("Question text cannot be empty")
        
        # Validate communities array
        if not communities or len(communities) == 0:
            raise ValueError("At least one community must be selected")
        
        # Find question
        question = self.get_question(question_id)
        if not question:
            return None
        
        # Update fields (preserving id and created_at)
        question["text"] = text.strip()
        question["photo_required"] = photo_required
        question["communities"] = communities
        question["updated_at"] = datetime.now().isoformat()
        
        # Save to file
        self.save_to_file()
        
        return question

    def delete_question(self, question_id: str) -> bool:
        """
        Soft delete question by setting is_active to False
        
        Args:
            question_id: Unique question identifier
            
        Returns:
            True if question was found and deleted, False otherwise
        """
        question = self.get_question(question_id)
        if not question:
            return False
        
        # Soft delete by setting is_active to False
        question["is_active"] = False
        question["updated_at"] = datetime.now().isoformat()
        
        # Save to file
        self.save_to_file()
        
        return True

    def save_to_file(self) -> None:
        """
        Persist Question Bank to JSON file
        
        Raises:
            IOError: If file cannot be written
        """
        try:
            # Update last_modified timestamp
            self.last_modified = datetime.now().isoformat()
            
            # Create data structure
            data = {
                "version": self.version,
                "last_modified": self.last_modified,
                "questions": self.questions
            }
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
            
            # Write to file
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
        except (OSError, IOError) as e:
            raise IOError(f"Failed to save questions to file: {str(e)}")

    def load_from_file(self) -> None:
        """
        Load Question Bank from JSON file with error handling
        
        If file doesn't exist or is malformed, initializes with empty state
        """
        try:
            if not os.path.exists(self.storage_path):
                # Initialize with empty state
                self.questions = []
                self.version = "1.0"
                self.last_modified = None
                return
            
            with open(self.storage_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Load data
            self.version = data.get("version", "1.0")
            self.last_modified = data.get("last_modified")
            self.questions = data.get("questions", [])
            
        except (json.JSONDecodeError, IOError) as e:
            # If file is malformed or cannot be read, initialize with empty state
            print(f"Warning: Could not load questions from {self.storage_path}: {e}")
            self.questions = []
            self.version = "1.0"
            self.last_modified = None
