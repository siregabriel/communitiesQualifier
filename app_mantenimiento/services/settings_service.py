"""
Settings Service
Small key/value store for app-wide settings that admins can edit at runtime.
Currently holds email routing:
  - inspection_cc: addresses always copied on every inspection email
                   (in addition to the community's region leadership)
  - admin_notify:  addresses alerted when a new user account is created

Persisted in data/settings.json (git-ignored; created on first write).
"""

import json
import os
import re
from datetime import datetime

from services.json_store import JsonFileBacked

_EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


def clean_emails(values):
    """Normalize a list (or comma/newline string) into unique valid emails."""
    if isinstance(values, str):
        values = re.split(r'[,\n;]+', values)
    out = []
    for v in (values or []):
        a = (v or '').strip()
        if _EMAIL_RE.match(a) and a.lower() not in [x.lower() for x in out]:
            out.append(a)
    return out


class SettingsService(JsonFileBacked):
    def __init__(self, storage_path: str):
        self.storage_path = storage_path
        self.data = {}
        self._init_store()
        self.load_from_file()
        self._mark_loaded()

    def load_from_file(self) -> None:
        try:
            if os.path.exists(self.storage_path):
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    d = json.load(f)
                self.data = d if isinstance(d, dict) else {}
            else:
                self.data = {}
        except (json.JSONDecodeError, OSError):
            self.data = {}

    def _save(self) -> None:
        self._atomic_write({**self.data, 'last_modified': datetime.now().isoformat()}, indent=2)

    def get_email_settings(self) -> dict:
        self._ensure_fresh()
        email = self.data.get('email', {}) if isinstance(self.data.get('email'), dict) else {}
        return {
            'inspection_cc': list(email.get('inspection_cc', [])),
            'admin_notify': list(email.get('admin_notify', [])),
        }

    def set_email_settings(self, inspection_cc=None, admin_notify=None) -> dict:
        with self._lock:
            self._ensure_fresh()
            email = self.data.get('email', {}) if isinstance(self.data.get('email'), dict) else {}
            if inspection_cc is not None:
                email['inspection_cc'] = clean_emails(inspection_cc)
            if admin_notify is not None:
                email['admin_notify'] = clean_emails(admin_notify)
            self.data['email'] = email
            self._save()
            return self.get_email_settings()

    def seed_inspection_cc(self, emails) -> None:
        """One-time: populate inspection_cc from env if it's currently empty."""
        cleaned = clean_emails(emails)
        if not cleaned:
            return
        with self._lock:
            self._ensure_fresh()
            email = self.data.get('email', {}) if isinstance(self.data.get('email'), dict) else {}
            if not email.get('inspection_cc'):
                email['inspection_cc'] = cleaned
                self.data['email'] = email
                self._save()
