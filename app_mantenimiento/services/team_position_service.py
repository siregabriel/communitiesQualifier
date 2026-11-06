"""
Team Position Service

The positions a Staff member can hold: Executive Chef, Wellness Director and so
on. They began as a fixed list in app.py, and the first person who did not fit
it (a Move In Coordinator, Nov 2026) needed a deploy to be added. Admins run
the list from Settings now; the person form only picks from it, so nobody
invents a position while adding somebody.

Two decisions worth keeping:

  * A person stores the position's **name**, as text, the way it was stored
    before this list could change. So there is no rename: renaming would have
    to walk every account holding the old name. Remove and add instead.

  * Removing only takes a position out of the dropdown. Whoever already holds
    it keeps it, and can still be edited without being forced to pick another.
    Adding a removed name again brings it back in its old place.

Record:
  {"positions": [{"name": "Executive Chef", "active": true}, ...]}

Persisted in data/team_positions.json (git-ignored). Until the first change
the list is the defaults below; nothing is written just by reading.
"""

import json
import os
import re
from datetime import datetime
from typing import List, Optional

from services.json_store import JsonFileBacked

MAX_NAME = 60

# In Gabriel's order. Only used while data/team_positions.json does not exist.
DEFAULT_POSITIONS = [
    'Sales and Marketing Director',
    'Business Office Director',
    'Wellness Director',
    'Lifestyles Director',
    'Executive Chef',
    'Director of Buildings Services',
]


def clean_name(name) -> str:
    """One line, single spaces, no angle brackets, at most MAX_NAME characters.

    Not HTML-escaped here: stored escaped, "Sales & Marketing" would show as
    "Sales &amp; Marketing" wherever the page escapes it again on output.
    """
    if not isinstance(name, str):
        return ''
    return re.sub(r'\s+', ' ', re.sub(r'[<>]', '', name)).strip()[:MAX_NAME]


class TeamPositionService(JsonFileBacked):
    def __init__(self, storage_path: str):
        self.storage_path = storage_path
        self.positions = []
        self._init_store()
        self.load_from_file()
        self._mark_loaded()

    def load_from_file(self) -> None:
        rows = None
        try:
            if os.path.exists(self.storage_path):
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    d = json.load(f)
                if isinstance(d, dict) and isinstance(d.get('positions'), list):
                    rows = d['positions']
        except (json.JSONDecodeError, OSError):
            rows = None
        if rows is None:
            self.positions = [{'name': n, 'active': True} for n in DEFAULT_POSITIONS]
            return
        out, seen = [], set()
        for r in rows:
            if not isinstance(r, dict):
                continue
            name = clean_name(r.get('name'))
            if name and name.lower() not in seen:
                seen.add(name.lower())
                out.append({'name': name, 'active': r.get('active', True) is not False})
        self.positions = out

    def _save(self) -> None:
        self._atomic_write({'positions': self.positions,
                            'last_modified': datetime.now().isoformat()})

    def _find(self, name: str) -> Optional[dict]:
        key = clean_name(name).lower()
        return next((p for p in self.positions if p['name'].lower() == key), None)

    def active(self) -> List[str]:
        """The names the form offers, in order."""
        with self._lock:
            self._ensure_fresh()
            return [p['name'] for p in self.positions if p['active']]

    def all(self) -> List[dict]:
        """Every position, removed ones too, for the Settings list."""
        with self._lock:
            self._ensure_fresh()
            return [dict(p) for p in self.positions]

    def is_choosable(self, name) -> bool:
        """Exactly one of the offered names, as the form sends it."""
        return bool(name) and name in self.active()

    def add(self, name) -> Optional[str]:
        """Offer a position. Returns its name, or None if it is empty or
        already offered. A removed one comes back with its old spelling."""
        name = clean_name(name)
        if not name:
            return None
        with self._lock:
            self._ensure_fresh()
            existing = self._find(name)
            if existing:
                if existing['active']:
                    return None
                existing['active'] = True
                self._save()
                return existing['name']
            self.positions.append({'name': name, 'active': True})
            self._save()
            return name

    def remove(self, name) -> Optional[str]:
        """Stop offering a position. Returns its name, or None if it was not
        offered. The last one stays: Staff cannot be added without one."""
        with self._lock:
            self._ensure_fresh()
            existing = self._find(name)
            if not existing or not existing['active']:
                return None
            if sum(1 for p in self.positions if p['active']) <= 1:
                return None
            existing['active'] = False
            self._save()
            return existing['name']
