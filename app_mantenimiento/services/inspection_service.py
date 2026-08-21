"""
Inspection Service Module

Handles inspection submission management, response validation,
photo file management, and submission persistence.
"""

import os
import json
import time
import random
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from werkzeug.utils import secure_filename

from services.json_store import JsonFileBacked


# Allowed file extensions for photo uploads
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif', 'webp'}

# Maximum file size in bytes (16MB)
MAX_FILE_SIZE = 16 * 1024 * 1024


class InspectionService(JsonFileBacked):
    """
    Service class for managing inspection submissions.
    
    Responsibilities:
    - Inspection submission handling
    - Response validation
    - Photo file management
    - Submission persistence
    """
    
    def __init__(self, storage_path: str, upload_path: str):
        """
        Initialize InspectionService with storage and upload paths.
        
        Args:
            storage_path: Path to inspections.json file
            upload_path: Path to uploads folder for photos
        """
        self.storage_path = storage_path
        self.upload_path = upload_path
        self.submissions = []

        # Ensure upload directory exists
        os.makedirs(upload_path, exist_ok=True)

        # Load existing submissions if file exists
        self._init_store()
        self.load_from_file()
        self._mark_loaded()
    
    # Action items raised by hand during a visit (not tied to a standard).
    ACTION_PRIORITIES = ('high', 'medium', 'low')

    @staticmethod
    def _clean_manual_items(items) -> List[Dict]:
        """Validate the ad-hoc action items captured at the end of a visit.
        These are follow-up tasks, not standards, so they never affect scoring."""
        out = []
        for it in (items or []):
            if not isinstance(it, dict):
                continue
            text = (it.get('text') or '').strip()
            if not text:
                continue
            priority = (it.get('priority') or 'medium').strip().lower()
            if priority not in InspectionService.ACTION_PRIORITIES:
                priority = 'medium'
            out.append({
                'id': f"act_{int(time.time() * 1000)}_{random.randint(1000, 9999)}",
                'text': text[:500],
                'assigned_to': (it.get('assigned_to') or '').strip()[:80],
                'priority': priority,
                'photo': (it.get('photo') or '').strip(),
                'resolved': False,
                'resolved_at': '',
                'resolved_by': '',
                'resolution_note': '',
            })
        return out

    def resolve_response(self, submission_id: str, question_id: str, username: str,
                         note: str = '', photo: str = '', resolved: bool = True) -> Optional[Dict]:
        """Record that a failed standard has been addressed between visits.

        The response's own verdict (Pass/Fail) is never changed — the visit stays
        a faithful record of what was found, and the score is untouched. We only
        attach follow-up information alongside it."""
        with self._lock:
            self._ensure_fresh()
            for sub in self.submissions:
                if sub.get('id') != submission_id:
                    continue
                for resp in sub.get('responses', []):
                    if resp.get('question_id') != question_id:
                        continue
                    if resolved:
                        resp['addressed'] = True
                        resp['addressed_at'] = datetime.now().isoformat()
                        resp['addressed_by'] = (username or '').strip()
                        resp['addressed_note'] = (note or '').strip()[:500]
                        if photo:
                            resp['addressed_photo'] = photo
                    else:
                        resp['addressed'] = False
                        for k in ('addressed_at', 'addressed_by', 'addressed_note', 'addressed_photo'):
                            resp.pop(k, None)
                    self.save_to_file()
                    return resp
            return None

    def add_comment(self, submission_id: str, question_id: str, username: str,
                    display_name: str, text: str, photo: str = '') -> Optional[Dict]:
        """Append a comment to a failed standard.

        Comments are the community's channel: an Executive Director reports that
        something is fixed and attaches a photo, and leadership replies or asks
        for more. None of this touches the verdict or the score — closing the
        item stays a separate, deliberate act by a regional."""
        text = (text or '').strip()
        if not text and not photo:
            return None
        with self._lock:
            self._ensure_fresh()
            for sub in self.submissions:
                if sub.get('id') != submission_id:
                    continue
                for resp in sub.get('responses', []):
                    if resp.get('question_id') != question_id:
                        continue
                    comment = {
                        'id': f"cm_{int(time.time() * 1000)}_{random.randint(1000, 9999)}",
                        'username': (username or '').strip(),
                        'author': (display_name or username or '').strip(),
                        'text': text[:1000],
                        'photo': (photo or '').strip(),
                        'at': datetime.now().isoformat(),
                    }
                    resp.setdefault('comments', []).append(comment)
                    self.save_to_file()
                    return comment
            return None

    def add_item_comment(self, submission_id: str, item_id: str, username: str,
                         display_name: str, text: str, photo: str = '') -> Optional[Dict]:
        """Same conversation, on an item raised by hand during the visit.

        These don't affect the score, but the rule people are asked to remember
        should be one rule: the community reports, leadership closes. Splitting
        it by item type would just be something else to explain."""
        text = (text or '').strip()
        if not text and not photo:
            return None
        with self._lock:
            self._ensure_fresh()
            for sub in self.submissions:
                if sub.get('id') != submission_id:
                    continue
                for item in sub.get('action_items', []):
                    if item.get('id') != item_id:
                        continue
                    comment = {
                        'id': f"cm_{int(time.time() * 1000)}_{random.randint(1000, 9999)}",
                        'username': (username or '').strip(),
                        'author': (display_name or username or '').strip(),
                        'text': text[:1000],
                        'photo': (photo or '').strip(),
                        'at': datetime.now().isoformat(),
                    }
                    item.setdefault('comments', []).append(comment)
                    self.save_to_file()
                    return comment
            return None

    def delete_item_comment(self, submission_id: str, item_id: str,
                            comment_id: str, username: str, is_admin: bool = False) -> bool:
        """Remove a comment from an ad-hoc item. Authors and admins only."""
        with self._lock:
            self._ensure_fresh()
            for sub in self.submissions:
                if sub.get('id') != submission_id:
                    continue
                for item in sub.get('action_items', []):
                    if item.get('id') != item_id:
                        continue
                    comments = item.get('comments') or []
                    for i, c in enumerate(comments):
                        if c.get('id') != comment_id:
                            continue
                        if not is_admin and c.get('username') != username:
                            return False
                        comments.pop(i)
                        self.save_to_file()
                        return True
            return False

    def delete_comment(self, submission_id: str, question_id: str,
                       comment_id: str, username: str, is_admin: bool = False) -> bool:
        """Remove a comment. Authors can delete their own; admins any."""
        with self._lock:
            self._ensure_fresh()
            for sub in self.submissions:
                if sub.get('id') != submission_id:
                    continue
                for resp in sub.get('responses', []):
                    if resp.get('question_id') != question_id:
                        continue
                    comments = resp.get('comments') or []
                    for i, c in enumerate(comments):
                        if c.get('id') != comment_id:
                            continue
                        if not is_admin and c.get('username') != username:
                            return False
                        comments.pop(i)
                        self.save_to_file()
                        return True
            return False

    def resolve_action_item(self, submission_id: str, item_id: str, username: str,
                            note: str = '', resolved: bool = True) -> Optional[Dict]:
        """Mark a manual action item as done (or reopen it). The original
        inspection record is never altered — we only track the follow-up."""
        with self._lock:
            self._ensure_fresh()
            for sub in self.submissions:
                if sub.get('id') != submission_id:
                    continue
                for item in sub.get('action_items', []):
                    if item.get('id') != item_id:
                        continue
                    item['resolved'] = bool(resolved)
                    item['resolved_at'] = datetime.now().isoformat() if resolved else ''
                    item['resolved_by'] = (username or '').strip() if resolved else ''
                    item['resolution_note'] = (note or '').strip()[:500] if resolved else ''
                    self.save_to_file()
                    return item
            return None

    def create_submission(self, username: str, community: str,
                         responses: List[Dict], survey_type_id: Optional[str] = None,
                         inspector_name: Optional[str] = None,
                         action_items: Optional[List[Dict]] = None,
                         standards_total: Optional[int] = None,
                         notes: str = '', notes_photo: str = '') -> Dict:
        """
        Create new inspection submission.
        
        Args:
            username: Staff member username
            community: Community name
            responses: List of response dictionaries
            survey_type_id: Survey type ID (optional for backward compatibility)
            
        Returns:
            InspectionSubmission dictionary
            
        Raises:
            ValueError: If validation fails
        """
        # Validate inputs
        if not username or not username.strip():
            raise ValueError("Username cannot be empty")
        if not community or not community.strip():
            raise ValueError("Community cannot be empty")
        
        # Filter and validate responses (only store answered questions)
        validated_responses = []
        for response in responses:
            # Skip empty responses (unanswered questions)
            if not response.get('question_id') or not response.get('condition'):
                continue
                
            # Validate response
            if not self.validate_response(response):
                raise ValueError(f"Invalid response data for question {response.get('question_id')}")
            
            validated_responses.append(response)
        
        # Generate unique submission ID
        submission_id = f"insp_{int(time.time() * 1000)}_{random.randint(1000, 9999)}"
        
        # Create submission object
        submission = {
            'id': submission_id,
            'username': username.strip(),
            'inspector_name': (inspector_name or username).strip(),
            'community': community.strip(),
            'submitted_at': datetime.now().isoformat(),
            'responses': validated_responses,
            # Follow-up tasks raised by the inspector; excluded from scoring.
            'action_items': self._clean_manual_items(action_items),
        }

        # Notes about the visit as a whole. Everything else recorded here is a
        # problem — a failed standard or a task. This is the one place to say
        # that it went well, or to explain a score: a community mid-renovation
        # and a community that isn't trying both score 60, and the number alone
        # can't tell them apart. Stored only when there is something to store,
        # so older visits stay exactly as they were.
        notes = (notes or '').strip()
        if notes:
            submission['notes'] = notes[:2000]
        if notes_photo:
            submission['notes_photo'] = notes_photo

        # Add survey_type_id if provided (backward compatibility)
        if survey_type_id:
            submission['survey_type_id'] = survey_type_id

        # How many standards the survey held when this was walked.
        #
        # Only answered standards are stored, and the score is worked out over
        # those — so three of eight, all passed, reads as 100% and looks just
        # like a complete clean visit. Keeping the total is what lets a partial
        # visit be told apart later. Visits recorded before this existed simply
        # don't carry it, and are left unlabelled rather than guessed at.
        try:
            total = int(standards_total)
            if total >= len(validated_responses) and total > 0:
                submission['standards_total'] = total
        except (TypeError, ValueError):
            pass
        
        # Reload latest from disk, then append, so concurrent submissions
        # from another process aren't lost.
        with self._lock:
            self._ensure_fresh()
            self.submissions.append(submission)
            self.save_to_file()

        return submission
    
    def validate_response(self, response: Dict) -> bool:
        """
        Validate individual response data.
        
        Args:
            response: Response dictionary to validate
            
        Returns:
            True if valid, False otherwise
        """
        # Check required fields
        if 'question_id' not in response or not response['question_id']:
            return False
        
        if 'condition' not in response:
            return False
        
        # Validate condition value
        valid_conditions = ['Excellence', 'Pass', 'Opportunity', 'Fail']
        if response['condition'] not in valid_conditions:
            return False
        
        # question_text is required
        if 'question_text' not in response:
            return False
        
        # description can be empty but must exist
        if 'description' not in response:
            return False
        
        # photo_path can be null or a string
        if 'photo_path' in response and response['photo_path'] is not None:
            if not isinstance(response['photo_path'], str):
                return False
        
        # answered_at must be present
        if 'answered_at' not in response:
            return False
        
        return True
    
    def save_photo(self, file, username: str, community: str) -> str:
        """
        Save uploaded photo and return relative path.
        
        Args:
            file: File object from request.files
            username: Staff member username
            community: Community name
            
        Returns:
            Relative path to saved photo
            
        Raises:
            ValueError: If file validation fails
        """
        # Validate file exists
        if not file or not file.filename:
            raise ValueError("No file provided")
        
        # Validate file extension
        if not self._allowed_file(file.filename):
            raise ValueError(
                f"Invalid file type. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"
            )
        
        # Validate file size
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)  # Reset file pointer
        
        if file_size > MAX_FILE_SIZE:
            raise ValueError(f"File size exceeds maximum of {MAX_FILE_SIZE / (1024 * 1024)}MB")
        
        # Generate filename: {username}_{community}_{timestamp}.{ext}
        timestamp = int(time.time() * 1000)
        file_ext = secure_filename(file.filename).rsplit('.', 1)[1].lower()
        filename = f"{username}_{community}_{timestamp}.{file_ext}"
        
        # Create community folder
        community_folder = os.path.join(
            self.upload_path, 
            secure_filename(community)
        )
        os.makedirs(community_folder, exist_ok=True)
        
        # Save file
        file_path = os.path.join(community_folder, filename)
        file.save(file_path)
        
        # Return relative path from uploads directory
        relative_path = os.path.join(
            'uploads',
            secure_filename(community),
            filename
        )
        
        return relative_path
    
    def get_submissions_by_community(self, community: str) -> List[Dict]:
        """
        Retrieve submissions for specific community.
        
        Args:
            community: Community name to filter by
            
        Returns:
            List of InspectionSubmission dictionaries
        """
        self._ensure_fresh()
        return [
            submission for submission in self.submissions
            if submission['community'] == community
        ]

    def get_all_submissions(self) -> List[Dict]:
        """
        Retrieve all submissions (admin only).

        Returns:
            List of all InspectionSubmission dictionaries
        """
        self._ensure_fresh()
        return self.submissions.copy()

    def reset_all(self) -> int:
        """Delete every submission and start fresh. Returns how many were removed.
        Photo files are intentionally left on disk/S3 — only the records are cleared."""
        with self._lock:
            self._ensure_fresh()
            count = len(self.submissions)
            self.submissions = []
            self.save_to_file()
            return count

    def rename_community(self, old_name: str, new_name: str) -> int:
        """Rename a community on every historical submission.
        Returns the number of submissions updated."""
        old_name = (old_name or '').strip()
        new_name = (new_name or '').strip()
        if not old_name or not new_name or old_name == new_name:
            return 0
        with self._lock:
            self._ensure_fresh()
            count = 0
            for s in self.submissions:
                if s.get('community') == old_name:
                    s['community'] = new_name
                    count += 1
            if count:
                self.save_to_file()
            return count
    
    def save_to_file(self) -> None:
        """
        Persist submissions to JSON file.
        
        Raises:
            IOError: If file write fails
        """
        try:
            # Create submissions collection structure
            data = {
                'version': '1.0',
                'last_modified': datetime.now().isoformat(),
                'submissions': self.submissions
            }

            # Atomic write (temp file + os.replace)
            self._atomic_write(data, indent=2)

        except Exception as e:
            raise IOError(f"Failed to save submissions to file: {str(e)}")
    
    def load_from_file(self) -> None:
        """
        Load submissions from JSON file with error handling.
        
        If file doesn't exist or is malformed, initializes with empty state.
        """
        try:
            if os.path.exists(self.storage_path):
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                # Validate structure
                if isinstance(data, dict) and 'submissions' in data:
                    self.submissions = data['submissions']
                else:
                    # Malformed data, initialize empty
                    self.submissions = []
            else:
                # File doesn't exist, initialize empty
                self.submissions = []
                
        except json.JSONDecodeError:
            # Malformed JSON, initialize empty
            self.submissions = []
        except Exception as e:
            # Other errors, initialize empty
            self.submissions = []
    
    def _allowed_file(self, filename: str) -> bool:
        """
        Check if file extension is allowed.
        
        Args:
            filename: Name of file to check
            
        Returns:
            True if extension is allowed, False otherwise
        """
        return '.' in filename and \
               filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
