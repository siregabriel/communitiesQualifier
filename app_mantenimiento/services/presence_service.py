"""
Presence Service

Tracks when each account last signed in and when it was last seen doing
anything, so the People directory can show "Active now" and "Last seen".

Design notes
------------
Writing on every request would hammer the JSON file, so `touch()` only
persists when the stored timestamp is older than WRITE_EVERY seconds. That
caps writes at roughly one per user per minute regardless of traffic, which
keeps this cheap even with several gunicorn workers.

Nothing here is allowed to break a request: every public method swallows its
own errors. Presence is a convenience, never a reason to fail a page load.
"""

import os
import json
import time
from datetime import datetime, timedelta

from services.json_store import JsonFileBacked


class PresenceService(JsonFileBacked):
    # Don't persist a "last seen" more often than this (seconds).
    WRITE_EVERY = 60
    # How recently someone must have been seen to count as active now (minutes).
    ACTIVE_WINDOW_MIN = 5

    def __init__(self, storage_path: str):
        self.storage_path = storage_path
        self.users = {}          # username -> {last_seen, last_login, logins}
        self._init_store()
        self.load_from_file()
        self._mark_loaded()

    def load_from_file(self) -> None:
        try:
            if os.path.exists(self.storage_path):
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.users = data.get('users', {}) if isinstance(data, dict) else {}
            else:
                self.users = {}
        except (json.JSONDecodeError, OSError):
            self.users = {}

    def _save(self) -> None:
        try:
            self._atomic_write({'version': '1.0', 'users': self.users}, indent=2)
        except OSError:
            pass  # presence is never worth failing a request over

    # -- writes ------------------------------------------------------------

    def touch(self, username: str) -> None:
        """Record that the user is active right now (throttled)."""
        try:
            if not username:
                return
            now = time.time()
            rec = self.users.get(username)
            if rec and (now - rec.get('_ts', 0)) < self.WRITE_EVERY:
                return  # seen very recently; skip the write
            with self._lock:
                self._ensure_fresh()
                rec = self.users.setdefault(username, {})
                rec['last_seen'] = datetime.now().isoformat()
                rec['_ts'] = now
                self._save()
        except Exception:
            pass

    def record_login(self, username: str) -> None:
        """Record a successful sign-in. Always written, never throttled."""
        try:
            if not username:
                return
            with self._lock:
                self._ensure_fresh()
                rec = self.users.setdefault(username, {})
                stamp = datetime.now().isoformat()
                rec['last_login'] = stamp
                rec['last_seen'] = stamp
                rec['_ts'] = time.time()
                rec['logins'] = int(rec.get('logins', 0)) + 1
                self._save()
        except Exception:
            pass

    def forget(self, username: str) -> None:
        """Drop a user's presence record (called when an account is deleted)."""
        try:
            with self._lock:
                self._ensure_fresh()
                if self.users.pop(username, None) is not None:
                    self._save()
        except Exception:
            pass

    def rename(self, old_username: str, new_username: str) -> None:
        """Carry presence across a username change."""
        try:
            if not old_username or not new_username or old_username == new_username:
                return
            with self._lock:
                self._ensure_fresh()
                rec = self.users.pop(old_username, None)
                if rec is not None:
                    self.users[new_username] = rec
                    self._save()
        except Exception:
            pass

    # -- reads -------------------------------------------------------------

    def get(self, username: str) -> dict:
        """Presence for one user: last_seen, last_login, logins, active."""
        self._ensure_fresh()
        rec = self.users.get(username) or {}
        return {
            'last_seen': rec.get('last_seen', ''),
            'last_login': rec.get('last_login', ''),
            'logins': int(rec.get('logins', 0)),
            'active': self.is_active(rec.get('last_seen', '')),
        }

    def all(self) -> dict:
        """Presence for everyone, keyed by username."""
        self._ensure_fresh()
        return {u: self.get(u) for u in self.users}

    def active_usernames(self) -> list:
        """Everyone seen inside the active window, most recent first."""
        self._ensure_fresh()
        seen = [(u, r.get('last_seen', '')) for u, r in self.users.items()
                if self.is_active(r.get('last_seen', ''))]
        seen.sort(key=lambda x: x[1], reverse=True)
        return [u for u, _ in seen]

    @classmethod
    def is_active(cls, last_seen: str) -> bool:
        """True if the timestamp falls inside the active window."""
        if not last_seen:
            return False
        try:
            ts = datetime.fromisoformat(last_seen)
        except (TypeError, ValueError):
            return False
        return datetime.now() - ts <= timedelta(minutes=cls.ACTIVE_WINDOW_MIN)
