"""
Resource Service
Admin-managed library of downloadable resources (guides, training, FAQ...).
Each resource is either an uploaded file or an external link.

Record:
  {
    "id": "res_...",
    "title": "Inspection Guidelines",
    "description": "Standard procedures...",
    "kind": "file" | "link",
    "url": "https://..."          # link only
    "file_path": "resources/...", # file only (relative; S3 key = uploads/<path>)
    "filename": "guidelines.pdf", # file only (original name)
    "content_type": "application/pdf",
    "created_at": "ISO",
    "created_by": "admin"
  }

Persisted in data/resources.json (git-ignored; created on first add).
"""

import json
import os
import time
import random
from datetime import datetime

from services.json_store import JsonFileBacked


class ResourceService(JsonFileBacked):
    def __init__(self, storage_path: str):
        self.storage_path = storage_path
        self.resources = []
        self._init_store()
        self.load_from_file()
        self._mark_loaded()

    def load_from_file(self) -> None:
        try:
            if os.path.exists(self.storage_path):
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                items = data.get('resources') if isinstance(data, dict) else None
                self.resources = items if isinstance(items, list) else []
            else:
                self.resources = []
        except (json.JSONDecodeError, OSError):
            self.resources = []

    def _save(self) -> None:
        self._atomic_write({
            'version': '1.0',
            'last_modified': datetime.now().isoformat(),
            'resources': self.resources,
        }, indent=2)

    def get_all(self) -> list:
        self._ensure_fresh()
        return list(self.resources)

    def get(self, resource_id: str):
        self._ensure_fresh()
        return next((r for r in self.resources if r.get('id') == resource_id), None)

    def add(self, title, description, kind, url=None, file_path=None,
            filename=None, content_type=None, created_by=None) -> dict:
        with self._lock:
            self._ensure_fresh()
            rec = {
                'id': f"res_{int(time.time() * 1000)}_{random.randint(1000, 9999)}",
                'title': title,
                'description': description or '',
                'kind': kind,
                'url': url,
                'file_path': file_path,
                'filename': filename,
                'content_type': content_type,
                'created_at': datetime.now().isoformat(),
                'created_by': created_by,
            }
            self.resources.append(rec)
            self._save()
            return rec

    def attach(self, resource_id: str, kind: str, url=None, file_path=None,
               filename=None, content_type=None) -> dict:
        """Turn a 'pending' resource into a real file/link (or replace one)."""
        with self._lock:
            self._ensure_fresh()
            rec = next((r for r in self.resources if r.get('id') == resource_id), None)
            if rec is None:
                return None
            rec['kind'] = kind
            rec['url'] = url
            rec['file_path'] = file_path
            rec['filename'] = filename
            rec['content_type'] = content_type
            self._save()
            return rec

    def delete(self, resource_id: str):
        """Remove a resource; returns the removed record (so callers can also
        delete the underlying file) or None."""
        with self._lock:
            self._ensure_fresh()
            idx = next((i for i, r in enumerate(self.resources)
                        if r.get('id') == resource_id), None)
            if idx is None:
                return None
            rec = self.resources.pop(idx)
            self._save()
            return rec
