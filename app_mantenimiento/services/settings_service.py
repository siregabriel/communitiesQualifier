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

    @staticmethod
    def _normalize_subscribers(subs):
        """Each subscriber: {email, name, regions:[ids], inspectors:[names]}.
        Empty regions AND empty inspectors = subscribed to everything."""
        out, seen = [], set()
        for s in (subs or []):
            if not isinstance(s, dict):
                continue
            email = (s.get('email') or '').strip()
            if not _EMAIL_RE.match(email) or email.lower() in seen:
                continue
            seen.add(email.lower())
            regions = [r for r in (s.get('regions') or []) if isinstance(r, str) and r]
            inspectors = [i.strip() for i in (s.get('inspectors') or []) if isinstance(i, str) and i.strip()]
            out.append({'email': email, 'name': (s.get('name') or '').strip(),
                        'regions': regions, 'inspectors': inspectors})
        return out

    def get_email_settings(self) -> dict:
        self._ensure_fresh()
        email = self.data.get('email', {}) if isinstance(self.data.get('email'), dict) else {}
        subs = email.get('subscribers')
        if subs is None and email.get('inspection_cc'):
            # migrate the old flat "always copy" list -> all-regions subscribers
            subs = [{'email': e, 'name': '', 'regions': []} for e in email.get('inspection_cc', [])]
        return {
            'subscribers': self._normalize_subscribers(subs),
            'admin_notify': clean_emails(email.get('admin_notify', [])),
            'clinical': clean_emails(email.get('clinical', [])),
            'ops': clean_emails(email.get('ops', [])),
            'sales': clean_emails(email.get('sales', [])),
        }

    def set_email_settings(self, subscribers=None, admin_notify=None,
                           clinical=None, ops=None, sales=None) -> dict:
        with self._lock:
            self._ensure_fresh()
            email = self.data.get('email', {}) if isinstance(self.data.get('email'), dict) else {}
            if subscribers is not None:
                email['subscribers'] = self._normalize_subscribers(subscribers)
                email.pop('inspection_cc', None)  # superseded by subscribers
            if admin_notify is not None:
                email['admin_notify'] = clean_emails(admin_notify)
            if clinical is not None:
                email['clinical'] = clean_emails(clinical)
            if ops is not None:
                email['ops'] = clean_emails(ops)
            if sales is not None:
                email['sales'] = clean_emails(sales)
            self.data['email'] = email
            self._save()
            return self.get_email_settings()

    # How often a community is expected to be visited. Used to work out which
    # ones are falling behind. A target, not a rule — nothing is blocked by it.
    DEFAULT_CADENCE_DAYS = 30

    def get_visit_cadence_days(self) -> int:
        self._ensure_fresh()
        try:
            v = int(self.data.get('visit_cadence_days', self.DEFAULT_CADENCE_DAYS))
        except (TypeError, ValueError):
            return self.DEFAULT_CADENCE_DAYS
        # Bounded so a stray value can't mark everything overdue or nothing.
        return max(7, min(v, 365))

    def set_visit_cadence_days(self, days) -> int:
        with self._lock:
            self._ensure_fresh()
            try:
                v = max(7, min(int(days), 365))
            except (TypeError, ValueError):
                v = self.DEFAULT_CADENCE_DAYS
            self.data['visit_cadence_days'] = v
            self._save()
            return v

    # Company-level teams a comment can be directed to from a visit.
    ROUTES = ('clinical', 'ops', 'sales')
    ROUTE_LABELS = {'clinical': 'Clinical', 'ops': 'Operations (Ops)', 'sales': 'Sales'}

    def recipients_for_route(self, route) -> list:
        """Recipient list for one of the company-level teams (see ROUTES)."""
        if route not in self.ROUTES:
            return []
        return self.get_email_settings().get(route, [])

    def recipients_for_inspection(self, region_id, inspector_name=None) -> list:
        """Subscriber emails whose scope covers this inspection.
        empty regions AND empty inspectors = everything; otherwise match on
        the inspection's region OR its inspector."""
        out = []
        for s in self.get_email_settings()['subscribers']:
            regions = s.get('regions') or []
            inspectors = s.get('inspectors') or []
            match = (not regions and not inspectors) \
                or (region_id and region_id in regions) \
                or (inspector_name and inspector_name in inspectors)
            if match and s['email'] not in out:
                out.append(s['email'])
        return out

    def seed_subscribers(self, emails) -> None:
        """One-time: turn env MAIL_EXTRA_RECIPIENTS into all-regions subscribers."""
        cleaned = clean_emails(emails)
        if not cleaned:
            return
        with self._lock:
            self._ensure_fresh()
            email = self.data.get('email', {}) if isinstance(self.data.get('email'), dict) else {}
            if not email.get('subscribers') and not email.get('inspection_cc'):
                email['subscribers'] = [{'email': e, 'name': '', 'regions': []} for e in cleaned]
                self.data['email'] = email
                self._save()
