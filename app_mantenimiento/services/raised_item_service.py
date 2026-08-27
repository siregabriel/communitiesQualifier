"""
Raised Item Service

Things a community raises for itself, rather than things a regional found on a
visit. An Executive Director noticing that the living room needs new furniture,
or that a fire extinguisher is out of date, had nowhere to put it: the only way
to write anything was to comment on a finding that already existed, so if
nothing had failed in that area there was no channel at all.

Deliberately kept apart from the action items on a visit. Those say "this is
wrong, fix it" and travel downward; these say "I need this" or "I noticed this"
and travel upward. Mixed into one list, a regional's queue stops meaning
anything — so they are stored separately and shown separately, even though they
look alike.

They never affect a score. Nothing here is part of a visit.

Record:
  {
    "id": "raised_...",
    "community": "Kelley Place, Enterprise",
    "text": "Living room furniture is worn and needs replacing",
    "category": "capex",                  # id from raised_category_service
    "priority": "high" | "medium" | "low",
    "photo": "Community/file.jpg",        # optional, relative like every other
    "raised_by": "jazmyn.frasier",        # the account, never a display name
    "raised_by_name": "Jazmyn Frazier",   # what to show, resolved at write time
    "raised_at": "ISO",
    "resolved": false,
    "resolved_at": "", "resolved_by": "", "resolution_note": "",
    "comments": [ {id, username, author, text, photo, at} ]
  }

Persisted in data/raised_items.json (git-ignored; created on the first one).
"""

import json
import os
import random
import time
from datetime import datetime
from typing import Dict, List, Optional

from services.json_store import JsonFileBacked

PRIORITIES = ('high', 'medium', 'low')
MAX_TEXT = 500


class RaisedItemService(JsonFileBacked):
    def __init__(self, storage_path: str):
        self.storage_path = storage_path
        self.items = []
        self._init_store()
        self.load_from_file()
        self._mark_loaded()

    def load_from_file(self) -> None:
        try:
            if os.path.exists(self.storage_path):
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                rows = data.get('items') if isinstance(data, dict) else data
                self.items = rows if isinstance(rows, list) else []
            else:
                self.items = []
        except (json.JSONDecodeError, OSError):
            self.items = []

    def save_to_file(self) -> None:
        self._atomic_write({'version': '1.0', 'items': self.items,
                            'last_modified': datetime.now().isoformat()}, indent=2)

    # ------------------------------------------------------------------

    def create(self, community: str, text: str, username: str, display_name: str,
               priority: str = 'medium', photo: str = '',
               category: str = '') -> Optional[Dict]:
        community = (community or '').strip()
        text = (text or '').strip()
        if not community or not text:
            return None
        priority = (priority or 'medium').strip().lower()
        if priority not in PRIORITIES:
            priority = 'medium'

        item = {
            'id': f"raised_{int(time.time() * 1000)}_{random.randint(1000, 9999)}",
            'community': community,
            'text': text[:MAX_TEXT],
            # The category's id, never its name — see raised_category_service.
            # Renaming a category must not orphan the items that chose it.
            'category': (category or '').strip(),
            'priority': priority,
            'photo': (photo or '').strip(),
            'raised_by': (username or '').strip(),
            'raised_by_name': (display_name or username or '').strip(),
            'raised_at': datetime.now().isoformat(),
            'resolved': False,
            'resolved_at': '',
            'resolved_by': '',
            'resolution_note': '',
            'comments': [],
        }
        with self._lock:
            self._ensure_fresh()
            self.items.append(item)
            self.save_to_file()
        return item

    def get(self, item_id: str) -> Optional[Dict]:
        self._ensure_fresh()
        return next((i for i in self.items if i.get('id') == item_id), None)

    def for_communities(self, communities, include_resolved: bool = False) -> List[Dict]:
        """Everything raised by the given communities, newest first.

        Takes a list rather than one name because a regional covers several and
        an Executive Director can stand in for a neighbour."""
        self._ensure_fresh()
        wanted = set(communities or [])
        rows = [i for i in self.items
                if i.get('community') in wanted
                and (include_resolved or not i.get('resolved'))]
        return sorted(rows, key=lambda i: i.get('raised_at', ''), reverse=True)

    def resolve(self, item_id: str, username: str, note: str = '',
                resolved: bool = True) -> Optional[Dict]:
        with self._lock:
            self._ensure_fresh()
            for item in self.items:
                if item.get('id') != item_id:
                    continue
                if resolved:
                    item['resolved'] = True
                    item['resolved_at'] = datetime.now().isoformat()
                    item['resolved_by'] = (username or '').strip()
                    item['resolution_note'] = (note or '').strip()[:500]
                else:
                    item['resolved'] = False
                    item['resolved_at'] = ''
                    item['resolved_by'] = ''
                    item['resolution_note'] = ''
                self.save_to_file()
                return item
            return None

    def add_comment(self, item_id: str, username: str, display_name: str,
                    text: str, photo: str = '') -> Optional[Dict]:
        """Append a reply to something a community raised.

        The same conversation a failed standard already has, on this side of
        the fence: the community says what they need, leadership answers. One
        rule for both kinds of item is one thing to remember instead of two.

        Older items carry no 'comments' key at all — they were written before
        this existed — so it is created on first use rather than migrated.
        """
        text = (text or '').strip()
        if not text and not photo:
            return None
        with self._lock:
            self._ensure_fresh()
            for item in self.items:
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

    def delete_comment(self, item_id: str, comment_id: str) -> bool:
        with self._lock:
            self._ensure_fresh()
            for item in self.items:
                if item.get('id') != item_id:
                    continue
                before = len(item.get('comments') or [])
                item['comments'] = [c for c in (item.get('comments') or [])
                                    if c.get('id') != comment_id]
                if len(item['comments']) != before:
                    self.save_to_file()
                    return True
            return False

    def delete(self, item_id: str) -> bool:
        with self._lock:
            self._ensure_fresh()
            before = len(self.items)
            self.items = [i for i in self.items if i.get('id') != item_id]
            if len(self.items) != before:
                self.save_to_file()
                return True
            return False

    def rename_community(self, old_name: str, new_name: str) -> int:
        """Keep raised items with their community when it is renamed.

        Every other store does this, and the one that didn't cost a regional a
        wasted trip — a community whose name moved out from under its data."""
        changed = 0
        with self._lock:
            self._ensure_fresh()
            for item in self.items:
                if item.get('community') == old_name:
                    item['community'] = new_name
                    changed += 1
            if changed:
                self.save_to_file()
        return changed
