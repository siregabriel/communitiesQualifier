"""
Draft Notice Service

A note that somebody has a visit in progress — not the visit itself.

The answers and the photos stay in the browser's own storage on the device
where the visit is being filled in. That is deliberate: photos are the bulk of
a visit, and uploading them progressively over the mobile signal inside a
building is exactly what fails today. What the server keeps is the fact that a
draft exists, so that:

  * a regional signing in anywhere is told they have an unfinished visit,
    instead of having to guess the community and survey type that would make it
    reappear — the draft is keyed on both, so entering by a different route
    finds nothing and looks like the work was lost;

  * somebody asking for help can be told where the draft actually is, rather
    than being told it cannot be found. That happened: a regional asked for a
    draft to be deleted for her by someone with no way to see or touch it.

Nothing here can restore a draft. It is a signpost, and it says so.

Record:
  {
    "id": "smoke.user::standards::Kelley Place, Enterprise",
    "username": "marissa.scott",
    "community": "Kelley Place, Enterprise",
    "survey_type_id": "standards",
    "answered": 12, "total": 39,       # how far along, for the wording
    "device": "iPhone · Safari",       # which device holds the content
    "started_at": "ISO", "updated_at": "ISO"
  }

Persisted in data/draft_notices.json (git-ignored; created on the first one).
"""

import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from services.json_store import JsonFileBacked

# Matches the browser's own 7-day prune, so the two never disagree about
# whether a draft is still around.
TTL_DAYS = 7


class DraftNoticeService(JsonFileBacked):
    def __init__(self, storage_path: str):
        self.storage_path = storage_path
        self.notices: List[Dict] = []
        self._init_store()
        self.load_from_file()
        self._mark_loaded()

    # ------------------------------------------------------------ storage

    def load_from_file(self) -> None:
        try:
            if os.path.exists(self.storage_path):
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.notices = data.get('notices', []) if isinstance(data, dict) else (data or [])
        except (OSError, ValueError):
            self.notices = []

    def save_to_file(self) -> None:
        self._atomic_write({
            'version': 1,
            'last_modified': datetime.now().isoformat(),
            'notices': self.notices,
        })

    @staticmethod
    def key(username: str, survey_type_id: str, community: str) -> str:
        """The same three things the browser keys its draft on, plus who.

        Two people can have a draft for the same community at once, and neither
        should see the other's.
        """
        return f"{(username or '').strip()}::{(survey_type_id or '').strip()}::{(community or '').strip()}"

    # ------------------------------------------------------------- reading

    def for_user(self, username: str) -> List[Dict]:
        """Their unfinished visits, most recently touched first.

        Pruning replaces the list, so it happens under the lock even though
        this is a read — otherwise a write running at the same time could be
        walking the list as it is swapped out from under it.
        """
        with self._lock:
            self._ensure_fresh()
            self._prune()
            mine = [n for n in self.notices if n.get('username') == username]
        return sorted(mine, key=lambda n: n.get('updated_at', ''), reverse=True)

    def get(self, notice_id: str) -> Optional[Dict]:
        self._ensure_fresh()
        return next((n for n in self.notices if n.get('id') == notice_id), None)

    # ------------------------------------------------------------- writing

    def record(self, username: str, community: str, survey_type_id: str,
               answered: int = 0, total: int = 0, device: str = '') -> Optional[Dict]:
        """Note that this draft exists, or that it has moved along."""
        if not username or not community:
            return None
        with self._lock:
            self._ensure_fresh()
            now = datetime.now().isoformat()
            nid = self.key(username, survey_type_id, community)
            existing = next((n for n in self.notices if n.get('id') == nid), None)
            if existing:
                existing.update(answered=int(answered or 0), total=int(total or 0),
                                updated_at=now)
                if device:
                    existing['device'] = device
            else:
                existing = {
                    'id': nid,
                    'username': username,
                    'community': community,
                    'survey_type_id': survey_type_id or '',
                    'answered': int(answered or 0),
                    'total': int(total or 0),
                    'device': device or '',
                    'started_at': now,
                    'updated_at': now,
                }
                self.notices.append(existing)
            self._prune()
            self.save_to_file()
            return existing

    def clear(self, username: str, community: str, survey_type_id: str) -> bool:
        """The draft is gone — submitted, or discarded by the person."""
        with self._lock:
            self._ensure_fresh()
            nid = self.key(username, survey_type_id, community)
            before = len(self.notices)
            self.notices = [n for n in self.notices if n.get('id') != nid]
            if len(self.notices) != before:
                self.save_to_file()
                return True
            return False

    def _prune(self) -> None:
        """Drop notices past the TTL.

        The browser prunes its own drafts at seven days; a notice outliving the
        thing it points at would send somebody looking for work that is no
        longer there — worse than saying nothing.
        """
        cutoff = (datetime.now() - timedelta(days=TTL_DAYS)).isoformat()
        self.notices = [n for n in self.notices if (n.get('updated_at') or '') >= cutoff]
