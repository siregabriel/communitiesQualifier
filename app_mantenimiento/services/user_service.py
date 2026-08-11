"""
User Service
Stores admin-created login accounts (in addition to the built-in seed users in
app.py and the per-person regional accounts derived from regions.json).

Each user record:
  {
    "display_name": "John Smith",
    "role": "admin" | "staff" | "regional",
    "community": "Community, City"   # staff only, else None
    "region_id": "coastal"           # regional only, else None
    "password_hash": "...",          # werkzeug hash
    "created_at": "ISO-8601",
    "created_by": "admin"
  }

Persisted in data/users.json (git-ignored; created on first write).
"""

import json
import os
from datetime import datetime

from services.json_store import JsonFileBacked


class UserService(JsonFileBacked):
    def __init__(self, storage_path: str):
        self.storage_path = storage_path
        self.users = {}   # username -> record
        self._init_store()
        self.load_from_file()
        self._mark_loaded()

    def load_from_file(self) -> None:
        try:
            if os.path.exists(self.storage_path):
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                users = data.get('users') if isinstance(data, dict) else None
                self.users = users if isinstance(users, dict) else {}
            else:
                self.users = {}
        except (json.JSONDecodeError, OSError):
            self.users = {}

    def _save(self) -> None:
        data = {
            'version': '1.0',
            'last_modified': datetime.now().isoformat(),
            'users': self.users,
        }
        self._atomic_write(data, indent=2)

    # --- Reads ---
    def exists(self, username: str) -> bool:
        self._ensure_fresh()
        return username in self.users

    def get(self, username: str):
        self._ensure_fresh()
        return self.users.get(username)

    def get_all(self) -> list:
        """Sanitized list (no password hashes), newest first."""
        self._ensure_fresh()
        out = []
        for username, rec in self.users.items():
            out.append({
                'username': username,
                'display_name': rec.get('display_name', username),
                'role': rec.get('role', 'staff'),
                'community': rec.get('community'),
                # Callers scope data by this, so it must survive the copy —
                # dropping it here silently narrowed every account to one site.
                'communities': rec.get('communities')
                               or ([rec.get('community')] if rec.get('community') else []),
                'region_id': rec.get('region_id'),
                'email': rec.get('email'),
                'created_at': rec.get('created_at'),
                'created_by': rec.get('created_by'),
            })
        out.sort(key=lambda u: u.get('created_at') or '', reverse=True)
        return out

    # --- Writes ---
    def create(self, username, display_name, role, password_hash,
               community=None, region_id=None, created_by=None, email=None,
               communities=None) -> dict:
        with self._lock:
            self._ensure_fresh()
            rec = {
                'display_name': display_name,
                'role': role,
                'community': community,
                # A community account can cover more than one site — an ED
                # standing in for a neighbour, for instance. `community` stays
                # as the primary so older records and code keep working.
                'communities': [c for c in (communities or ([community] if community else []))],
                'region_id': region_id,
                'email': email,
                'password_hash': password_hash,
                'created_at': datetime.now().isoformat(),
                'created_by': created_by,
            }
            self.users[username] = rec
            self._save()
            return rec

    def set_password_hash(self, username: str, password_hash: str) -> bool:
        with self._lock:
            self._ensure_fresh()
            if username not in self.users:
                return False
            self.users[username]['password_hash'] = password_hash
            self._save()
            return True

    def update(self, username: str, **fields) -> bool:
        """Update editable profile fields on a stored user. Only the keys passed
        in are touched; the username and password hash are never changed here."""
        allowed = {'display_name', 'role', 'community', 'communities', 'region_id', 'email'}
        with self._lock:
            self._ensure_fresh()
            if username not in self.users:
                return False
            for key, value in fields.items():
                if key in allowed:
                    self.users[username][key] = value
            self._save()
            return True

    def ensure(self, username: str, **fields) -> bool:
        """Create the user record if it doesn't exist yet (used to migrate
        built-in accounts into editable storage). Returns True if created."""
        with self._lock:
            self._ensure_fresh()
            if username in self.users:
                return False
            rec = {
                'display_name': fields.get('display_name') or username,
                'role': fields.get('role', 'staff'),
                'community': fields.get('community'),
                'communities': fields.get('communities')
                               or ([fields.get('community')] if fields.get('community') else []),
                'region_id': fields.get('region_id'),
                'email': fields.get('email'),
                'password_hash': fields.get('password_hash'),
                'created_at': datetime.now().isoformat(),
                'created_by': fields.get('created_by', 'system'),
                'builtin': bool(fields.get('builtin')),
            }
            self.users[username] = rec
            self._save()
            return True

    def delete(self, username: str) -> bool:
        with self._lock:
            self._ensure_fresh()
            if username not in self.users:
                return False
            del self.users[username]
            self._save()
            return True
