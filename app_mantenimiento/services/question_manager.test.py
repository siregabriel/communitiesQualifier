"""
Unit tests for QuestionManager service
Tests CRUD operations, validation, and JSON persistence
"""

import unittest
import os
import json
import tempfile
import time
from question_manager import QuestionManager


class TestQuestionManager(unittest.TestCase):
    """Test suite for QuestionManager class"""

    def setUp(self):
        """Set up test fixtures before each test"""
        # Create a temporary file for testing
        self.temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json')
        self.temp_file.close()
        self.storage_path = self.temp_file.name
        self.manager = QuestionManager(self.storage_path)

    def tearDown(self):
        """Clean up after each test"""
        # Remove temporary file
        if os.path.exists(self.storage_path):
            os.remove(self.storage_path)

    def test_init_creates_empty_manager(self):
        """Test that initialization creates an empty QuestionManager"""
        self.assertEqual(len(self.manager.questions), 0)
        self.assertEqual(self.manager.version, "1.0")

    def test_create_question_success(self):
        """Test successful question creation"""
        question = self.manager.create_question(
            text="Is the common area clean?",
            photo_required=True,
            communities=["Community A", "Community B"]
        )
        
        # Verify question structure
        self.assertIn("id", question)
        self.assertTrue(question["id"].startswith("q_"))
        self.assertEqual(question["text"], "Is the common area clean?")
        self.assertTrue(question["photo_required"])
        self.assertEqual(question["communities"], ["Community A", "Community B"])
        self.assertIn("created_at", question)
        self.assertIn("updated_at", question)
        self.assertTrue(question["is_active"])
        
        # Verify it's in the manager's list
        self.assertEqual(len(self.manager.questions), 1)

    def test_create_question_strips_whitespace(self):
        """Test that question text is stripped of whitespace"""
        question = self.manager.create_question(
            text="  Question with spaces  ",
            photo_required=False,
            communities=["Community A"]
        )
        
        self.assertEqual(question["text"], "Question with spaces")

    def test_create_question_empty_text_raises_error(self):
        """Test that empty question text raises ValueError"""
        with self.assertRaises(ValueError) as context:
            self.manager.create_question(
                text="",
                photo_required=False,
                communities=["Community A"]
            )
        
        self.assertIn("Question text cannot be empty", str(context.exception))

    def test_create_question_whitespace_only_text_raises_error(self):
        """Test that whitespace-only question text raises ValueError"""
        with self.assertRaises(ValueError) as context:
            self.manager.create_question(
                text="   ",
                photo_required=False,
                communities=["Community A"]
            )
        
        self.assertIn("Question text cannot be empty", str(context.exception))

    def test_create_question_empty_communities_raises_error(self):
        """Test that empty communities array raises ValueError"""
        with self.assertRaises(ValueError) as context:
            self.manager.create_question(
                text="Valid question",
                photo_required=False,
                communities=[]
            )
        
        self.assertIn("At least one community must be selected", str(context.exception))

    def test_get_question_by_id(self):
        """Test retrieving a question by ID"""
        created = self.manager.create_question(
            text="Test question",
            photo_required=False,
            communities=["Community A"]
        )
        
        retrieved = self.manager.get_question(created["id"])
        
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved["id"], created["id"])
        self.assertEqual(retrieved["text"], "Test question")

    def test_get_question_nonexistent_returns_none(self):
        """Test that getting a nonexistent question returns None"""
        result = self.manager.get_question("nonexistent_id")
        self.assertIsNone(result)

    def test_get_all_active_questions(self):
        """Test retrieving all active questions"""
        # Create multiple questions
        q1 = self.manager.create_question("Question 1", False, ["Community A"])
        time.sleep(0.01)  # Ensure different timestamps
        q2 = self.manager.create_question("Question 2", True, ["Community B"])
        time.sleep(0.01)
        q3 = self.manager.create_question("Question 3", False, ["Community C"])
        
        active = self.manager.get_all_active_questions()
        
        # Should return all 3 questions
        self.assertEqual(len(active), 3)
        
        # Should be sorted by created_at descending (newest first)
        self.assertEqual(active[0]["id"], q3["id"])
        self.assertEqual(active[1]["id"], q2["id"])
        self.assertEqual(active[2]["id"], q1["id"])

    def test_get_all_active_questions_excludes_inactive(self):
        """Test that get_all_active_questions excludes soft-deleted questions"""
        q1 = self.manager.create_question("Question 1", False, ["Community A"])
        q2 = self.manager.create_question("Question 2", True, ["Community B"])
        
        # Soft delete q1
        self.manager.delete_question(q1["id"])
        
        active = self.manager.get_all_active_questions()
        
        # Should only return q2
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0]["id"], q2["id"])

    def test_get_questions_for_community(self):
        """Test filtering questions by community"""
        q1 = self.manager.create_question("Q1", False, ["Community A"])
        q2 = self.manager.create_question("Q2", True, ["Community B"])
        q3 = self.manager.create_question("Q3", False, ["Community A", "Community B"])
        
        # Get questions for Community A
        community_a_questions = self.manager.get_questions_for_community("Community A")
        
        # Should return q1 and q3
        self.assertEqual(len(community_a_questions), 2)
        question_ids = [q["id"] for q in community_a_questions]
        self.assertIn(q1["id"], question_ids)
        self.assertIn(q3["id"], question_ids)
        self.assertNotIn(q2["id"], question_ids)

    def test_get_questions_for_community_excludes_inactive(self):
        """Test that community filtering excludes soft-deleted questions"""
        q1 = self.manager.create_question("Q1", False, ["Community A"])
        q2 = self.manager.create_question("Q2", True, ["Community A"])
        
        # Soft delete q1
        self.manager.delete_question(q1["id"])
        
        community_questions = self.manager.get_questions_for_community("Community A")
        
        # Should only return q2
        self.assertEqual(len(community_questions), 1)
        self.assertEqual(community_questions[0]["id"], q2["id"])

    def test_update_question_success(self):
        """Test successful question update"""
        original = self.manager.create_question(
            text="Original text",
            photo_required=False,
            communities=["Community A"]
        )
        
        original_id = original["id"]
        original_created_at = original["created_at"]
        original_updated_at = original["updated_at"]
        
        time.sleep(0.1)  # Ensure different timestamp
        
        # Update the question
        updated = self.manager.update_question(
            question_id=original_id,
            text="Updated text",
            photo_required=True,
            communities=["Community B", "Community C"]
        )
        
        # Verify updates
        self.assertIsNotNone(updated)
        self.assertEqual(updated["id"], original_id)  # ID preserved
        self.assertEqual(updated["created_at"], original_created_at)  # created_at preserved
        self.assertEqual(updated["text"], "Updated text")
        self.assertTrue(updated["photo_required"])
        self.assertEqual(updated["communities"], ["Community B", "Community C"])
        self.assertGreater(updated["updated_at"], original_updated_at)  # updated_at changed

    def test_update_question_preserves_id_and_created_at(self):
        """Test that update preserves ID and created_at"""
        original = self.manager.create_question("Original", False, ["Community A"])
        
        time.sleep(0.01)
        
        updated = self.manager.update_question(
            question_id=original["id"],
            text="Updated",
            photo_required=True,
            communities=["Community B"]
        )
        
        self.assertEqual(updated["id"], original["id"])
        self.assertEqual(updated["created_at"], original["created_at"])

    def test_update_question_empty_text_raises_error(self):
        """Test that updating with empty text raises ValueError"""
        question = self.manager.create_question("Original", False, ["Community A"])
        
        with self.assertRaises(ValueError) as context:
            self.manager.update_question(
                question_id=question["id"],
                text="",
                photo_required=False,
                communities=["Community A"]
            )
        
        self.assertIn("Question text cannot be empty", str(context.exception))

    def test_update_question_empty_communities_raises_error(self):
        """Test that updating with empty communities raises ValueError"""
        question = self.manager.create_question("Original", False, ["Community A"])
        
        with self.assertRaises(ValueError) as context:
            self.manager.update_question(
                question_id=question["id"],
                text="Updated",
                photo_required=False,
                communities=[]
            )
        
        self.assertIn("At least one community must be selected", str(context.exception))

    def test_update_question_nonexistent_returns_none(self):
        """Test that updating a nonexistent question returns None"""
        result = self.manager.update_question(
            question_id="nonexistent_id",
            text="Text",
            photo_required=False,
            communities=["Community A"]
        )
        
        self.assertIsNone(result)

    def test_delete_question_soft_delete(self):
        """Test that delete performs soft delete"""
        question = self.manager.create_question("To delete", False, ["Community A"])
        question_id = question["id"]
        
        # Delete the question
        result = self.manager.delete_question(question_id)
        
        self.assertTrue(result)
        
        # Question should still exist but be inactive
        deleted = self.manager.get_question(question_id)
        self.assertIsNotNone(deleted)
        self.assertFalse(deleted["is_active"])
        
        # Should not appear in active questions
        active = self.manager.get_all_active_questions()
        self.assertEqual(len(active), 0)

    def test_delete_question_nonexistent_returns_false(self):
        """Test that deleting a nonexistent question returns False"""
        result = self.manager.delete_question("nonexistent_id")
        self.assertFalse(result)

    def test_save_and_load_from_file(self):
        """Test JSON persistence round-trip"""
        # Create questions
        q1 = self.manager.create_question("Question 1", True, ["Community A"])
        q2 = self.manager.create_question("Question 2", False, ["Community B", "Community C"])
        
        # Create a new manager instance with the same file
        new_manager = QuestionManager(self.storage_path)
        
        # Verify questions were loaded
        self.assertEqual(len(new_manager.questions), 2)
        
        loaded_q1 = new_manager.get_question(q1["id"])
        self.assertIsNotNone(loaded_q1)
        self.assertEqual(loaded_q1["text"], "Question 1")
        self.assertTrue(loaded_q1["photo_required"])
        self.assertEqual(loaded_q1["communities"], ["Community A"])
        
        loaded_q2 = new_manager.get_question(q2["id"])
        self.assertIsNotNone(loaded_q2)
        self.assertEqual(loaded_q2["text"], "Question 2")
        self.assertFalse(loaded_q2["photo_required"])
        self.assertEqual(loaded_q2["communities"], ["Community B", "Community C"])

    def test_load_from_nonexistent_file(self):
        """Test loading from nonexistent file initializes empty state"""
        nonexistent_path = "/tmp/nonexistent_questions.json"
        if os.path.exists(nonexistent_path):
            os.remove(nonexistent_path)
        
        manager = QuestionManager(nonexistent_path)
        
        self.assertEqual(len(manager.questions), 0)
        self.assertEqual(manager.version, "1.0")
        self.assertIsNone(manager.last_modified)

    def test_load_from_malformed_json(self):
        """Test loading from malformed JSON initializes empty state"""
        # Write malformed JSON
        with open(self.storage_path, 'w') as f:
            f.write("{ invalid json }")
        
        manager = QuestionManager(self.storage_path)
        
        # Should initialize with empty state
        self.assertEqual(len(manager.questions), 0)
        self.assertEqual(manager.version, "1.0")

    def test_question_id_uniqueness(self):
        """Test that generated question IDs are unique"""
        ids = set()
        
        # Create multiple questions rapidly
        for i in range(10):
            question = self.manager.create_question(
                text=f"Question {i}",
                photo_required=False,
                communities=["Community A"]
            )
            ids.add(question["id"])
        
        # All IDs should be unique
        self.assertEqual(len(ids), 10)

    def test_iso_8601_timestamps(self):
        """Test that timestamps are in ISO 8601 format"""
        question = self.manager.create_question(
            text="Test question",
            photo_required=False,
            communities=["Community A"]
        )
        
        # Verify ISO 8601 format (contains 'T' separator)
        self.assertIn("T", question["created_at"])
        self.assertIn("T", question["updated_at"])
        
        # Verify timestamps can be parsed
        from datetime import datetime
        created = datetime.fromisoformat(question["created_at"])
        updated = datetime.fromisoformat(question["updated_at"])
        
        self.assertIsInstance(created, datetime)
        self.assertIsInstance(updated, datetime)


if __name__ == '__main__':
    unittest.main()
