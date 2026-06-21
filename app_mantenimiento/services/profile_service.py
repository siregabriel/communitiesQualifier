"""
Profile Service
Stores per-user profile extras and editable account fields:
  - photo (uploaded avatar path)
  - display_name (friendly name shown across the UI)
  - password_hash (override for changed passwords; auth falls back to the seed)
Also stores per-leader photos for region leadership cards.
Persisted in data/profiles.json.
"""

import json
import os
from datetime import datetime

from services.json_store import JsonFileBacked


class ProfileService(JsonFileBacked):
    def __init__(self, storage_path: str):
        self.storage_path = storage_path
        self.profiles = {}   # username -> { photo, display_name, password_hash }
        self.leaders = {}    # "regionId::Leader Name" -> { photo }
        self._init_store()
        self.load_from_file()
        self._mark_loaded()

    def load_from_file(self) -> None:
        try:
            if os.path.exists(self.storage_path):
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    self.profiles = data.get('profiles', {}) if isinstance(data.get('profiles'), dict) else {}
                    self.leaders = data.get('leaders', {}) if isinstance(data.get('leaders'), dict) else {}
                else:
                    self.profiles, self.leaders = {}, {}
            else:
                self.profiles, self.leaders = {}, {}
        except (json.JSONDecodeError, OSError):
            self.profiles, self.leaders = {}, {}

    def _save(self) -> None:
        data = {
            'version': '1.0',
            'last_modified': datetime.now().isoformat(),
            'profiles': self.profiles,
            'leaders': self.leaders
        }
        self._atomic_write(data, indent=2)

    # --- Photo ---
    def get_photo(self, username: str):
        self._ensure_fresh()
        return self.profiles.get(username, {}).get('photo')

    def set_photo(self, username: str, relative_path: str) -> None:
        with self._lock:
            self._ensure_fresh()
            self.profiles.setdefault(username, {})['photo'] = relative_path
            self._save()

    # --- Display name ---
    def get_display_name(self, username: str):
        self._ensure_fresh()
        return self.profiles.get(username, {}).get('display_name')

    def set_display_name(self, username: str, display_name: str) -> None:
        with self._lock:
            self._ensure_fresh()
            self.profiles.setdefault(username, {})['display_name'] = display_name
            self._save()

    # --- Password override (hashed) ---
    def get_password_hash(self, username: str):
        self._ensure_fresh()
        return self.profiles.get(username, {}).get('password_hash')

    def set_password_hash(self, username: str, password_hash: str) -> None:
        with self._lock:
            self._ensure_fresh()
            self.profiles.setdefault(username, {})['password_hash'] = password_hash
            self._save()

    # --- Region leadership photos ---
    @staticmethod
    def leader_key(region_id: str, leader_name: str) -> str:
        return f"{region_id}::{leader_name}"

    def get_leader_photo(self, region_id: str, leader_name: str):
        self._ensure_fresh()
        return self.leaders.get(self.leader_key(region_id, leader_name), {}).get('photo')

    def set_leader_photo(self, region_id: str, leader_name: str, relative_path: str) -> None:
        with self._lock:
            self._ensure_fresh()
            self.leaders.setdefault(self.leader_key(region_id, leader_name), {})['photo'] = relative_path
            self._save()
