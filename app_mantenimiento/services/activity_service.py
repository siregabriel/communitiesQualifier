"""
Activity Service
Lightweight audit log of user actions (inspections, question changes, region
changes). Powers the profile activity feed and stats. Designed to be safe:
logging never raises in a way that could break the underlying action.
"""

import json
import os
import time
import random
from datetime import datetime

from services.json_store import JsonFileBacked


class ActivityService(JsonFileBacked):
    MAX_EVENTS = 5000  # keep the log bounded

    def __init__(self, storage_path: str):
        self.storage_path = storage_path
        self.events = []
        self._init_store()
        self.load_from_file()
        self._mark_loaded()

    def load_from_file(self) -> None:
        try:
            if os.path.exists(self.storage_path):
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if isinstance(data, dict) and isinstance(data.get('events'), list):
                    self.events = data['events']
                else:
                    self.events = []
            else:
                self.events = []
        except (json.JSONDecodeError, OSError):
            self.events = []

    def _save(self) -> None:
        try:
            data = {'version': '1.0', 'events': self.events[-self.MAX_EVENTS:]}
            self._atomic_write(data, indent=2)
        except OSError:
            pass  # never let logging break the request

    def log(self, username: str, event_type: str, detail: str = "", meta: dict = None) -> None:
        """Record an event. Swallows all errors by design.
        `meta` carries optional structured data (e.g. {'community': '...'}) used
        to build links in the UI without parsing the detail text."""
        try:
            if not username:
                return
            event = {
                'id': f"act_{int(time.time() * 1000)}_{random.randint(1000, 9999)}",
                'username': username,
                'type': event_type,
                'detail': detail,
                'meta': meta or {},
                'timestamp': datetime.now().isoformat()
            }
            with self._lock:
                self._ensure_fresh()   # don't drop events logged by another process
                self.events.append(event)
                self._save()
        except Exception:
            pass

    def purge_types(self, types) -> int:
        """Remove every logged event whose type is in `types`. Used when the
        underlying records are deleted (e.g. an inspection data reset) so the
        activity log doesn't point at things that no longer exist.
        Returns how many events were removed."""
        wanted = set(types or [])
        if not wanted:
            return 0
        with self._lock:
            self._ensure_fresh()
            before = len(self.events)
            self.events = [e for e in self.events if e.get('type') not in wanted]
            removed = before - len(self.events)
            if removed:
                self._save()
            return removed

    def get_for_user(self, username: str, limit: int = 20) -> list:
        """Most recent events for a user (newest first)."""
        self._ensure_fresh()
        items = [e for e in self.events if e.get('username') == username]
        items.sort(key=lambda e: e.get('timestamp', ''), reverse=True)
        return items[:limit]

    def count_for_user(self, username: str, event_type: str = None) -> int:
        self._ensure_fresh()
        return sum(
            1 for e in self.events
            if e.get('username') == username and (event_type is None or e.get('type') == event_type)
        )

    def last_active(self, username: str):
        self._ensure_fresh()
        items = [e.get('timestamp') for e in self.events if e.get('username') == username]
        return max(items) if items else None
