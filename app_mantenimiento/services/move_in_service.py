"""
Move-In module services.

Two JSON-backed stores:
  * MoveInTemplateService — the editable checklist template (phases -> items).
    Persisted in data/movein_template.json (seeded from data/seeds/).
  * MoveInService — one record per resident move-in, holding per-item completion
    metadata (done / date / initials / attachment). data/moveins.json.

A "move-in" is a per-resident event that runs through the template's phases.
Progress is computed by comparing completed items against the template total.
"""

import json
import os
import time
import random
from datetime import datetime

from services.json_store import JsonFileBacked


def _new_id(prefix):
    return f"{prefix}_{int(time.time() * 1000)}_{random.randint(1000, 9999)}"


class MoveInTemplateService(JsonFileBacked):
    def __init__(self, storage_path: str):
        self.storage_path = storage_path
        self.phases = []
        self._init_store()
        self.load_from_file()
        self._mark_loaded()

    def load_from_file(self) -> None:
        try:
            if os.path.exists(self.storage_path):
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                ph = data.get('phases') if isinstance(data, dict) else None
                self.phases = ph if isinstance(ph, list) else []
            else:
                self.phases = []
        except (json.JSONDecodeError, OSError):
            self.phases = []

    def _save(self) -> None:
        self._atomic_write({
            'version': '1.0',
            'last_modified': datetime.now().isoformat(),
            'phases': self.phases,
        }, indent=2)

    def get_template(self) -> dict:
        self._ensure_fresh()
        return {'phases': json.loads(json.dumps(self.phases))}

    def all_item_ids(self) -> list:
        self._ensure_fresh()
        ids = []
        for ph in self.phases:
            for it in (ph.get('items') or []):
                if it.get('id'):
                    ids.append(it['id'])
        return ids

    def save_template(self, phases) -> dict:
        """Replace the whole template. Normalizes ids so new phases/items get one."""
        clean = []
        for ph in (phases or []):
            if not isinstance(ph, dict):
                continue
            name = (ph.get('name') or '').strip()
            if not name:
                continue
            items = []
            for it in (ph.get('items') or []):
                if isinstance(it, dict):
                    text = (it.get('text') or '').strip()
                elif isinstance(it, str):
                    text = it.strip()
                else:
                    text = ''
                if not text:
                    continue
                items.append({'id': (it.get('id') if isinstance(it, dict) else None) or _new_id('itm'),
                              'text': text})
            clean.append({'id': ph.get('id') or _new_id('phase'), 'name': name, 'items': items})
        with self._lock:
            self._ensure_fresh()
            self.phases = clean
            self._save()
        return self.get_template()


class MoveInService(JsonFileBacked):
    def __init__(self, storage_path: str):
        self.storage_path = storage_path
        self.moveins = []
        self._init_store()
        self.load_from_file()
        self._mark_loaded()

    def load_from_file(self) -> None:
        try:
            if os.path.exists(self.storage_path):
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                items = data.get('moveins') if isinstance(data, dict) else None
                self.moveins = items if isinstance(items, list) else []
            else:
                self.moveins = []
        except (json.JSONDecodeError, OSError):
            self.moveins = []

    def _save(self) -> None:
        self._atomic_write({
            'version': '1.0',
            'last_modified': datetime.now().isoformat(),
            'moveins': self.moveins,
        }, indent=2)

    def get_all(self) -> list:
        self._ensure_fresh()
        return json.loads(json.dumps(self.moveins))

    def get(self, mv_id: str):
        self._ensure_fresh()
        rec = next((m for m in self.moveins if m.get('id') == mv_id), None)
        return json.loads(json.dumps(rec)) if rec else None

    def create(self, resident_name, community, target_date, created_by=None) -> dict:
        with self._lock:
            self._ensure_fresh()
            rec = {
                'id': _new_id('mv'),
                'resident_name': resident_name,
                'community': community,
                'target_date': target_date or '',
                'status': 'active',
                'created_at': datetime.now().isoformat(),
                'created_by': created_by,
                'completions': {},
            }
            self.moveins.append(rec)
            self._save()
            return json.loads(json.dumps(rec))

    def update_item(self, mv_id, item_id, done=None, date=None, initials=None,
                    updated_by=None) -> dict:
        with self._lock:
            self._ensure_fresh()
            rec = next((m for m in self.moveins if m.get('id') == mv_id), None)
            if rec is None:
                return None
            comps = rec.setdefault('completions', {})
            entry = comps.setdefault(item_id, {})
            if done is not None:
                entry['done'] = bool(done)
            if date is not None:
                entry['date'] = (date or '').strip()
            if initials is not None:
                entry['initials'] = (initials or '').strip()[:8]
            entry['updated_at'] = datetime.now().isoformat()
            entry['updated_by'] = updated_by
            self._save()
            return json.loads(json.dumps(rec))

    def set_attachment(self, mv_id, item_id, path, filename) -> dict:
        with self._lock:
            self._ensure_fresh()
            rec = next((m for m in self.moveins if m.get('id') == mv_id), None)
            if rec is None:
                return None
            entry = rec.setdefault('completions', {}).setdefault(item_id, {})
            entry['attachment_path'] = path
            entry['attachment_name'] = filename
            entry['updated_at'] = datetime.now().isoformat()
            self._save()
            return json.loads(json.dumps(rec))

    def set_status(self, mv_id, status) -> dict:
        with self._lock:
            self._ensure_fresh()
            rec = next((m for m in self.moveins if m.get('id') == mv_id), None)
            if rec is None:
                return None
            rec['status'] = status
            self._save()
            return json.loads(json.dumps(rec))

    def delete(self, mv_id):
        with self._lock:
            self._ensure_fresh()
            idx = next((i for i, m in enumerate(self.moveins) if m.get('id') == mv_id), None)
            if idx is None:
                return None
            rec = self.moveins.pop(idx)
            self._save()
            return rec
