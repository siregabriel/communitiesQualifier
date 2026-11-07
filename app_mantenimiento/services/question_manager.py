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

from services.json_store import JsonFileBacked


class QuestionManager(JsonFileBacked):
    """
    Manages inspection questions with JSON file-based storage.
    Supports CRUD operations, community-based filtering, and soft deletes.
    Reloads from disk before every read/write so a stale in-memory copy can
    never clobber changes made by another process or an external edit.
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
        self.migrations = []

        self._init_store()
        self.load_from_file()
        self._mark_loaded()

    @staticmethod
    def _ordered(questions: List[Dict]) -> List[Dict]:
        """The order every screen shows: the one an admin set in Standards.

        Greg Crutcher asked to change the order of the questions (Nov 2026);
        until then they came newest first, which is also what an install that
        has never reordered keeps. Once somebody reorders, every active
        question carries an "order", and a new one is put at the end. A
        question without one (from before) sorts after those, newest first.
        """
        placed = sorted((q for q in questions if isinstance(q.get("order"), int)),
                        key=lambda q: q["order"])
        rest = sorted((q for q in questions if not isinstance(q.get("order"), int)),
                      key=lambda q: q.get("created_at", ""), reverse=True)
        return placed + rest

    def reorder(self, ids: List[str]) -> List[Dict]:
        """Put the active questions in this order. Ids that are not active
        questions are ignored; active questions left out keep their place
        after the ones given, so a stale page can never drop one."""
        with self._lock:
            self._ensure_fresh()
            active = self._ordered([q for q in self.questions if q.get("is_active", True)])
            by_id = {q["id"]: q for q in active}
            seen, out = set(), []
            for qid in ids or []:
                if qid in by_id and qid not in seen:
                    seen.add(qid)
                    out.append(by_id[qid])
            out += [q for q in active if q["id"] not in seen]
            for i, q in enumerate(out):
                q["order"] = i
            self.save_to_file()
            return list(out)

    @staticmethod
    def _clean_criteria(items):
        """Normalize the 'must include to pass' list: strip, drop blanks."""
        if isinstance(items, str):
            items = items.split('\n')
        return [s.strip() for s in (items or []) if isinstance(s, str) and s.strip()]

    def create_question(self, text: str, photo_required: bool, communities: List[str],
                       survey_types: Optional[List[str]] = None,
                       interpretive_guideline: str = "", pass_criteria=None,
                       all_communities: bool = False, help_resource_id: str = "") -> Dict:
        """
        Create new question with validation
        
        Args:
            text: Question text (required, non-empty after stripping)
            photo_required: Whether photo upload is required
            communities: Array of community names (required, non-empty)
            survey_types: Array of survey type IDs (optional, empty means all types)
            
        Returns:
            Dict containing the created question
            
        Raises:
            ValueError: If validation fails
        """
        # Validate question text
        if not text or not text.strip():
            raise ValueError("Question text cannot be empty")
        
        # Validate communities array. "Every community" needs no list: it is
        # every community there is, including ones added later.
        communities = list(communities or [])
        if not all_communities and not communities:
            raise ValueError("At least one community must be selected")
        
        # Handle survey_types: None or empty list means all types (backward compatibility)
        if survey_types is None:
            survey_types = []
        
        # Generate unique ID using timestamp and random number
        question_id = f"q_{int(time.time() * 1000)}_{random.randint(1000, 9999)}"
        
        # Create timestamp in ISO 8601 format
        now = datetime.now().isoformat()
        
        # Create question object
        question = {
            "id": question_id,
            "text": text.strip(),
            "interpretive_guideline": (interpretive_guideline or "").strip(),
            "pass_criteria": self._clean_criteria(pass_criteria),
            "photo_required": photo_required,
            "communities": communities,
            "survey_types": survey_types,  # Empty array means all types
            "created_at": now,
            "updated_at": now,
            "is_active": True
        }
        if all_communities:
            question["all_communities"] = True
        if help_resource_id:
            question["help_resource_id"] = help_resource_id
        
        # Reload latest from disk before appending so we never clobber
        # changes made by another process or an external edit.
        with self._lock:
            self._ensure_fresh()
            # Once an order has been set, a new question goes to the end of it.
            orders = [q["order"] for q in self.questions if isinstance(q.get("order"), int)]
            if orders:
                question["order"] = max(orders) + 1
            self.questions.append(question)
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
        self._ensure_fresh()
        for question in self.questions:
            if question["id"] == question_id:
                return question
        return None

    def get_all_active_questions(self) -> List[Dict]:
        """
        Retrieve all active questions
        
        Returns:
            List of active question dicts, in the order set in Standards (see _ordered)
        """
        self._ensure_fresh()
        return self._ordered([q for q in self.questions if q.get("is_active", True)])

    def get_questions_for_community(self, community: str) -> List[Dict]:
        """
        Retrieve active questions assigned to specific community
        
        Args:
            community: Community name to filter by
            
        Returns:
            List of active question dicts for the specified community,
            in the order set in Standards (see _ordered)
        """
        self._ensure_fresh()
        return self._ordered([
            q for q in self.questions
            if q.get("is_active", True)
            and (q.get("all_communities") or community in q.get("communities", []))
        ])

    def update_question(self, question_id: str, text: str, photo_required: bool,
                       communities: List[str], survey_types: Optional[List[str]] = None,
                       interpretive_guideline: str = "", pass_criteria=None,
                       all_communities: bool = False,
                       help_resource_id: Optional[str] = None) -> Optional[Dict]:
        """
        Update existing question, preserving ID and created_at timestamp
        
        Args:
            question_id: Unique question identifier
            text: Updated question text (required, non-empty after stripping)
            photo_required: Updated photo requirement flag
            communities: Updated array of community names (required, non-empty)
            survey_types: Updated array of survey type IDs (optional, empty means all types)
            
        Returns:
            Updated question dict if found, None otherwise
            
        Raises:
            ValueError: If validation fails
        """
        # Validate question text
        if not text or not text.strip():
            raise ValueError("Question text cannot be empty")
        
        # Validate communities array (not needed for "Every community")
        communities = list(communities or [])
        if not all_communities and not communities:
            raise ValueError("At least one community must be selected")
        
        # Handle survey_types: None or empty list means all types (backward compatibility)
        if survey_types is None:
            survey_types = []
        
        # Find question
        question = self.get_question(question_id)
        if not question:
            return None
        
        # Update fields (preserving id and created_at)
        question["text"] = text.strip()
        question["interpretive_guideline"] = (interpretive_guideline or "").strip()
        question["pass_criteria"] = self._clean_criteria(pass_criteria)
        question["photo_required"] = photo_required
        question["communities"] = communities
        if all_communities:
            question["all_communities"] = True
        else:
            question.pop("all_communities", None)
        question["survey_types"] = survey_types  # Empty array means all types
        # None leaves the help material as it was; "" takes it off.
        if help_resource_id is not None:
            if help_resource_id:
                question["help_resource_id"] = help_resource_id
            else:
                question.pop("help_resource_id", None)
        question["updated_at"] = datetime.now().isoformat()
        
        # Save to file
        self.save_to_file()
        
        return question

    def clear_help_resource(self, resource_id: str) -> int:
        """Take a deleted resource off every standard that showed it.
        Returns how many standards changed."""
        if not resource_id:
            return 0
        with self._lock:
            self._ensure_fresh()
            changed = 0
            for q in self.questions:
                if q.get("help_resource_id") == resource_id:
                    q.pop("help_resource_id", None)
                    changed += 1
            if changed:
                self.save_to_file()
        return changed

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

    @staticmethod
    def covers(question: Dict, community: str) -> bool:
        """Whether a standard applies at this community."""
        return bool(question.get("all_communities")) or community in (question.get("communities") or [])

    def change_communities(self, ids: List[str], community: str, action: str,
                           everyone: List[str]) -> Dict:
        """Add or remove one community on several standards at once.

        Greg Crutcher asked (Nov 2026) for an easier way than opening every
        standard to add a new community. Adding to an "Every community"
        standard changes nothing: it already has it. Removing from one turns
        it into a plain list of everyone else, so it stops picking up new
        communities on its own. A standard is never left with no community;
        those are reported back, untouched.
        """
        if action not in ("add", "remove") or not community:
            raise ValueError("Say which community, and add or remove")
        wanted = set(ids or [])
        changed, unchanged, refused = [], [], []
        with self._lock:
            self._ensure_fresh()
            for q in self.questions:
                if q.get("id") not in wanted or not q.get("is_active", True):
                    continue
                comms = list(q.get("communities") or [])
                if action == "add":
                    if self.covers(q, community):
                        unchanged.append(q["id"])
                        continue
                    comms.append(community)
                    q["communities"] = comms
                else:
                    if not self.covers(q, community):
                        unchanged.append(q["id"])
                        continue
                    if q.get("all_communities"):
                        comms = [c for c in everyone if c != community]
                    else:
                        comms = [c for c in comms if c != community]
                    if not comms:
                        refused.append(q["id"])
                        continue
                    q.pop("all_communities", None)
                    q["communities"] = comms
                q["updated_at"] = datetime.now().isoformat()
                changed.append(q["id"])
            if changed:
                self.save_to_file()
        return {"changed": changed, "unchanged": unchanged, "refused": refused}

    EVERY_COMMUNITY_MIGRATION = "every_community_v1"

    def adopt_every_community(self, everyone: List[str]) -> int:
        """Once: a standard that already lists every community becomes
        "Every community", so the next community added gets it too.

        Greg agreed to switch them automatically (Nov 2026). Run once and
        remembered in the file: a standard somebody later ticks every box on
        by hand is left as the list they chose. Returns how many changed.
        """
        everyone = [c for c in (everyone or []) if c]
        if not everyone:
            return 0
        with self._lock:
            self._ensure_fresh()
            if self.EVERY_COMMUNITY_MIGRATION in self.migrations:
                return 0
            need = set(everyone)
            count = 0
            for q in self.questions:
                if q.get("is_active", True) and not q.get("all_communities") \
                        and need <= set(q.get("communities") or []):
                    q["all_communities"] = True
                    count += 1
            self.migrations.append(self.EVERY_COMMUNITY_MIGRATION)
            self.save_to_file()
            return count

    def rename_community(self, old_name: str, new_name: str) -> int:
        """Rename a community across every question's communities list.
        Returns the number of questions affected."""
        old_name = (old_name or '').strip()
        new_name = (new_name or '').strip()
        if not old_name or not new_name or old_name == new_name:
            return 0
        with self._lock:
            self._ensure_fresh()
            count = 0
            for q in self.questions:
                comms = q.get('communities', [])
                if old_name in comms:
                    q['communities'] = [new_name if c == old_name else c for c in comms]
                    # de-dup
                    seen, deduped = set(), []
                    for c in q['communities']:
                        if c not in seen:
                            seen.add(c); deduped.append(c)
                    q['communities'] = deduped
                    count += 1
            if count:
                self.save_to_file()
            return count

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
            if self.migrations:
                data["migrations"] = self.migrations
            
            # Atomic write (temp file + os.replace)
            self._atomic_write(data, indent=4)
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
            self.migrations = [m for m in (data.get("migrations") or []) if isinstance(m, str)]
            
        except (json.JSONDecodeError, IOError) as e:
            # If file is malformed or cannot be read, initialize with empty state
            print(f"Warning: Could not load questions from {self.storage_path}: {e}")
            self.questions = []
            self.version = "1.0"
            self.last_modified = None
