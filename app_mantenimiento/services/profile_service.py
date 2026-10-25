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

    # --- Administrator privileges granted on top of a person's normal role ---
    def get_admin_extra(self, username: str) -> bool:
        """True when this person has been granted administrator privileges in
        addition to their own role (e.g. a Corporate member who also manages
        standards and people). Only the main administrator can grant this."""
        self._ensure_fresh()
        return bool(self.profiles.get(username, {}).get('admin_extra'))

    def set_admin_extra(self, username: str, value: bool) -> None:
        with self._lock:
            self._ensure_fresh()
            self.profiles.setdefault(username, {})['admin_extra'] = bool(value)
            self._save()

    def admin_extra_usernames(self) -> list:
        """Everyone currently holding the admin accessory."""
        self._ensure_fresh()
        return [u for u, p in self.profiles.items() if p.get('admin_extra')]

    # --- A regional who may visit every community, not just their region ---
    def get_all_communities(self, username: str) -> bool:
        """True when this regional's reach is the whole company while they stay
        in their own region.

        Kept here, keyed by username, rather than on the leader record in
        regions.json: that record is rebuilt from scratch when a leader is
        edited and re-created when they move region, and a flag stored there
        would silently fall off. A profile survives both, and a username
        change carries it along with everything else."""
        self._ensure_fresh()
        return bool(self.profiles.get(username, {}).get('all_communities'))

    def set_all_communities(self, username: str, value: bool) -> None:
        with self._lock:
            self._ensure_fresh()
            self.profiles.setdefault(username, {})['all_communities'] = bool(value)
            self._save()

    # --- Communities outside their region that a regional may also visit ---
    def get_extra_communities(self, username: str) -> list:
        """Named communities, chosen by an administrator, that this regional
        may visit on top of their own region.

        The Goldton at Venice moved to another region, and Lauren Hamilton —
        still the regional for the region it left — kept needing to visit it.
        "Every community" would have handed her thirty-nine to fix one.

        Kept here, keyed by username, for the same reason as all_communities:
        the leader record is rebuilt on every edit. Community names are
        stored, so a rename has to walk this too (rename_community below)."""
        self._ensure_fresh()
        extras = self.profiles.get(username, {}).get('extra_communities') or []
        return [c for c in extras if isinstance(c, str) and c.strip()]

    def set_extra_communities(self, username: str, communities) -> None:
        clean = []
        for c in communities or []:
            c = (c or '').strip()
            if c and c not in clean:
                clean.append(c)
        with self._lock:
            self._ensure_fresh()
            self.profiles.setdefault(username, {})['extra_communities'] = clean
            self._save()

    def rename_community(self, old_name: str, new_name: str) -> int:
        """Carry extra-community grants across a rename. Returns how many
        profiles changed."""
        changed = 0
        with self._lock:
            self._ensure_fresh()
            for prof in self.profiles.values():
                extras = prof.get('extra_communities') or []
                if old_name in extras:
                    out = []
                    for c in extras:
                        c = new_name if c == old_name else c
                        if c not in out:
                            out.append(c)
                    prof['extra_communities'] = out
                    changed += 1
            if changed:
                self._save()
        return changed

    # --- The email Atlerts knows this person by, when it is not their own ---
    def get_atlerts_email(self, username: str) -> str:
        """A second address that signs this account in from Atlerts.

        Excellence accounts carry the corporate address; many people set up
        Atlerts with a personal one, and the SSO matched on the email alone,
        so they were sent to the password screen every time. The person links
        it themselves, after proving both sides: Atlerts verified the address,
        and they then typed this account's password. Used only to sign in —
        nothing is ever emailed to it."""
        self._ensure_fresh()
        return (self.profiles.get(username, {}).get('atlerts_email') or '').strip()

    def set_atlerts_email(self, username: str, email: str) -> None:
        with self._lock:
            self._ensure_fresh()
            self.profiles.setdefault(username, {})['atlerts_email'] = \
                (email or '').strip().lower()
            self._save()

    def username_for_atlerts_email(self, email: str):
        """Whose account this Atlerts address is linked to, or None."""
        target = (email or '').strip().lower()
        if not target:
            return None
        self._ensure_fresh()
        for username, prof in self.profiles.items():
            if (prof.get('atlerts_email') or '').strip().lower() == target:
                return username
        return None

    # --- Force a password change on next login (after an admin reset) ---
    def get_must_change(self, username: str) -> bool:
        self._ensure_fresh()
        return bool(self.profiles.get(username, {}).get('must_change'))

    def set_must_change(self, username: str, value: bool) -> None:
        with self._lock:
            self._ensure_fresh()
            self.profiles.setdefault(username, {})['must_change'] = bool(value)
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
