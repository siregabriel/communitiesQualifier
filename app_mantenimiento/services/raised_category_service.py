"""
Raised Item Category Service

The kind of thing a community is asking for — CapEx, Sales, Clinical and so on.
Greg asked for these so the raised items can be filtered; the list is his and
Angie's to run, not something that needs a code change to extend.

Two decisions worth keeping:

  * An item stores the category's **id**, never its name. Rename "Admin/
    Personnel" to "People" a year from now and every past item follows, with no
    migration. Names were stored as text once before, for communities, and one
    rename left a regional driving to a building that Atlas no longer listed.

  * Nothing is ever really deleted. Retiring a category takes it out of the
    dropdown and leaves it on the items that already carry it. A hard delete
    would leave those items pointing at nothing, and that surfaces months
    later as a blank chip nobody can explain.

Record:
  {
    "id": "capex",              # stable, generated from the first name given
    "name": "CapEx",            # what people see; freely renameable
    "order": 0,                 # where it sits in the dropdown
    "active": true,             # false = retired: hidden from new items, kept on old
    "created_at": "ISO", "updated_at": "ISO"
  }

Persisted in data/raised_categories.json (git-ignored; seeded on first run).
"""

import json
import os
import re
from datetime import datetime
from typing import Dict, List, Optional

from services.json_store import JsonFileBacked

MAX_NAME = 40

# What Greg proposed, with Angie invited to add to it. "Other" is deliberate:
# the category is required, so there has to be somewhere to put the thing that
# genuinely fits nowhere — otherwise people pick a wrong one to get past the
# form, and the filter quietly fills with noise.
DEFAULT_CATEGORIES = [
    'CapEx',
    'Sales',
    'Clinical',
    'Maintenance',
    'Dining',
    'Lifestyles',
    'Admin/Personnel',
    'Other',
]


def _slug(name: str) -> str:
    s = re.sub(r'[^a-z0-9]+', '-', (name or '').lower()).strip('-')
    return s or 'category'


class RaisedCategoryService(JsonFileBacked):
    def __init__(self, storage_path: str):
        self.storage_path = storage_path
        self.categories: List[Dict] = []
        self._init_store()
        self.load_from_file()
        self._mark_loaded()
        if not self.categories:
            self._seed()

    # ------------------------------------------------------------ storage

    def load_from_file(self) -> None:
        try:
            if os.path.exists(self.storage_path):
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.categories = data.get('categories', []) if isinstance(data, dict) else (data or [])
        except (OSError, ValueError):
            self.categories = []

    def save_to_file(self) -> None:
        self._atomic_write({
            'version': 1,
            'last_modified': datetime.now().isoformat(),
            'categories': self.categories,
        })

    def _seed(self) -> None:
        now = datetime.now().isoformat()
        self.categories = [
            {'id': _slug(n), 'name': n, 'order': i, 'active': True,
             'created_at': now, 'updated_at': now}
            for i, n in enumerate(DEFAULT_CATEGORIES)
        ]
        self.save_to_file()

    # ------------------------------------------------------------- reading

    def all(self) -> List[Dict]:
        """Every category, retired ones included, in dropdown order."""
        self._ensure_fresh()
        return sorted(self.categories, key=lambda c: (c.get('order', 0), c.get('name', '')))

    def active(self) -> List[Dict]:
        """The ones a person may still choose."""
        return [c for c in self.all() if c.get('active', True)]

    def get(self, category_id: str) -> Optional[Dict]:
        self._ensure_fresh()
        return next((c for c in self.categories if c.get('id') == category_id), None)

    def name_for(self, category_id: str) -> str:
        """The label to show, resolved at read time so renames are free.

        Items raised before categories existed carry nothing; they are not
        broken, they simply predate the field, and they say so.
        """
        if not category_id:
            return 'Uncategorised'
        c = self.get(category_id)
        return c['name'] if c else 'Uncategorised'

    def is_choosable(self, category_id: str) -> bool:
        c = self.get(category_id)
        return bool(c and c.get('active', True))

    # ------------------------------------------------------------- writing

    def create(self, name: str) -> Optional[Dict]:
        name = (name or '').strip()[:MAX_NAME]
        if not name:
            return None
        self._ensure_fresh()
        if any((c.get('name') or '').lower() == name.lower() for c in self.categories):
            return None                       # same name twice helps nobody
        base = _slug(name)
        cid, n = base, 2
        while any(c.get('id') == cid for c in self.categories):
            cid, n = f'{base}-{n}', n + 1
        now = datetime.now().isoformat()
        cat = {'id': cid, 'name': name, 'active': True,
               'order': max([c.get('order', 0) for c in self.categories] + [-1]) + 1,
               'created_at': now, 'updated_at': now}
        self.categories.append(cat)
        self.save_to_file()
        return cat

    def rename(self, category_id: str, name: str) -> Optional[Dict]:
        """Rename in place. The id does not move, so items keep pointing here."""
        name = (name or '').strip()[:MAX_NAME]
        if not name:
            return None
        self._ensure_fresh()
        cat = self.get(category_id)
        if not cat:
            return None
        if any(c.get('id') != category_id and (c.get('name') or '').lower() == name.lower()
               for c in self.categories):
            return None
        cat['name'] = name
        cat['updated_at'] = datetime.now().isoformat()
        self.save_to_file()
        return cat

    def set_active(self, category_id: str, active: bool) -> Optional[Dict]:
        """Retire or bring back. Never removes the record."""
        self._ensure_fresh()
        cat = self.get(category_id)
        if not cat:
            return None
        if not active and len([c for c in self.categories if c.get('active', True)]) <= 1:
            return None                       # something has to stay choosable
        cat['active'] = bool(active)
        cat['updated_at'] = datetime.now().isoformat()
        self.save_to_file()
        return cat

    def reorder(self, ordered_ids: List[str]) -> List[Dict]:
        self._ensure_fresh()
        pos = {cid: i for i, cid in enumerate(ordered_ids or [])}
        for c in self.categories:
            if c.get('id') in pos:
                c['order'] = pos[c['id']]
        self.save_to_file()
        return self.all()
