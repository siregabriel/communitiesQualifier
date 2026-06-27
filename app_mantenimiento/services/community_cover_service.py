"""
Community Cover Service
Stores the cover image chosen for each community (admin-uploaded).

Record (keyed by community slug):
  {
    "<slug>": {
        "name": "Lake Howard Heights, Winter Haven",  # display name at upload time
        "path": "community_covers/<slug>.jpg",         # relative (S3 key = uploads/<path>)
        "filename": "lake.jpg",                         # original file name
        "updated_at": "ISO"
    }
}

Persisted in data/community_covers.json (git-ignored; created on first upload).
"""

import json
import os
from datetime import datetime

from services.json_store import JsonFileBacked


class CommunityCoverService(JsonFileBacked):
    def __init__(self, storage_path: str):
        self.storage_path = storage_path
        self.covers = {}
        self._init_store()
        self.load_from_file()
        self._mark_loaded()

    def load_from_file(self) -> None:
        try:
            if os.path.exists(self.storage_path):
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                items = data.get('covers') if isinstance(data, dict) else None
                self.covers = items if isinstance(items, dict) else {}
            else:
                self.covers = {}
        except (json.JSONDecodeError, OSError):
            self.covers = {}

    def _save(self) -> None:
        self._atomic_write({
            'version': '1.0',
            'last_modified': datetime.now().isoformat(),
            'covers': self.covers,
        }, indent=2)

    def get_all(self) -> dict:
        """Return {slug: record} for every community that has a cover."""
        self._ensure_fresh()
        return dict(self.covers)

    def get(self, slug: str):
        self._ensure_fresh()
        return self.covers.get(slug)

    def set(self, slug: str, name: str, path: str, filename: str) -> dict:
        with self._lock:
            self._ensure_fresh()
            rec = {
                'name': name or '',
                'path': path,
                'filename': filename or '',
                'updated_at': datetime.now().isoformat(),
            }
            self.covers[slug] = rec
            self._save()
            return rec

    def delete(self, slug: str):
        """Remove a cover; returns the removed record (so the caller can also
        delete the underlying file) or None."""
        with self._lock:
            self._ensure_fresh()
            rec = self.covers.pop(slug, None)
            if rec is not None:
                self._save()
            return rec
