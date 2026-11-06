"""
Draft Service

The content of an unfinished visit, kept on the server as well as the phone.

Until November 2026 an unfinished visit lived only in the browser of the
device it was started on, and the server held a signpost saying it existed
(draft_notice_service). Greg Crutcher answered 33 of 35 standards at Monark
Grove Greystone; four days later a bug in the form overwrote them on his
phone, and there was no other copy anywhere. That bug is fixed, but the lesson
is the single copy: anything that goes wrong in one browser — a private tab, a
different app opening the link, a phone replaced — loses the work.

So the phone still saves first (it works with no signal), and every save is
also sent here when there is signal. Photos go to the bucket under drafts/ as
they are taken, not at the end. Resuming on any device brings the visit back.

What this is not:
  * not readable by anybody but the person who started it — not even an
    administrator. Admins see the signpost (who, where, how far) for support;
    the content is somebody's half-written findings.
  * not capped. One draft per person + community + survey type, as before.
    Unfinished visits expire after TTL_DAYS without a save, and their photos
    are deleted with them.

Record (data/drafts.json):
  {
    "id": "greg.crutcher::sales-marketing::Monark Grove Greystone",
    "username": "greg.crutcher", "community": "...", "survey_type_id": "...",
    "responses": {"<question id>": {"condition": "Pass|Fail|", "description": "", "routeTo": ""}},
    "action_items": [{"text": "", "assigned_to": "", "priority": "low|medium|high"}],
    "notes": "",
    "photos": {"<question id or __notes__>": {"path": "drafts/...", "name": "", "type": "", "size": 0}},
    "total": 35,
    "saved_at": 1730620000000,          # the phone's own clock, ms — to pick the newer copy
    "created_at": "ISO", "updated_at": "ISO"
  }

Text is stored as typed, length-capped, not HTML-escaped: it only ever goes
back into form fields as .value, never into markup, and escaping it here would
put "&#39;" into somebody's sentence when it came back.
"""

import json
import os
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from services.json_store import JsonFileBacked
from services.conditions import ANSWERS

TTL_DAYS = 14

# Days without a save after which the owner is reminded, once each per quiet
# spell. A draft expires at TTL_DAYS and its photos with it, so the second
# reminder has to land with time to act.
REMIND_AT_DAYS = (3, 11)

NOTES_SLOT = '__notes__'
_SLOT_RE = re.compile(r'^[A-Za-z0-9_\-]{1,80}$')

MAX_RESPONSES = 400
MAX_ACTION_ITEMS = 60
MAX_DESCRIPTION = 4000
MAX_NOTES = 8000
_CONDITIONS = ANSWERS + ('',)
_PRIORITIES = ('low', 'medium', 'high')


def valid_slot(slot: str) -> bool:
    """A question id, or the visit-notes photo. Nothing that could walk a path."""
    return bool(slot) and (slot == NOTES_SLOT or bool(_SLOT_RE.match(slot)))


def _text(value, limit: int) -> str:
    s = value if isinstance(value, str) else ''
    # Control characters other than newline and tab have no business in a
    # finding, and some of them break JSON readers downstream.
    s = ''.join(ch for ch in s if ch in '\n\t' or ord(ch) >= 32)
    return s[:limit]


def clean_responses(raw) -> Dict[str, Dict]:
    out = {}
    if not isinstance(raw, dict):
        return out
    for qid, r in list(raw.items())[:MAX_RESPONSES]:
        if not isinstance(qid, str) or not _SLOT_RE.match(qid) or not isinstance(r, dict):
            continue
        condition = r.get('condition') if r.get('condition') in _CONDITIONS else ''
        description = _text(r.get('description'), MAX_DESCRIPTION)
        route = _text(r.get('routeTo'), 80)
        if condition or description.strip() or route:
            out[qid] = {'condition': condition, 'description': description, 'routeTo': route}
    return out


def clean_action_items(raw) -> List[Dict]:
    out = []
    if not isinstance(raw, list):
        return out
    for it in raw[:MAX_ACTION_ITEMS]:
        if not isinstance(it, dict):
            continue
        text = _text(it.get('text'), 1000)
        if not text.strip():
            continue
        out.append({
            'text': text,
            'assigned_to': _text(it.get('assigned_to'), 120),
            'priority': it.get('priority') if it.get('priority') in _PRIORITIES else 'medium',
        })
    return out


class DraftService(JsonFileBacked):
    def __init__(self, storage_path: str):
        self.storage_path = storage_path
        self.drafts: List[Dict] = []
        self._init_store()
        self.load_from_file()
        self._mark_loaded()

    # ------------------------------------------------------------ storage

    def load_from_file(self) -> None:
        try:
            if os.path.exists(self.storage_path):
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.drafts = data.get('drafts', []) if isinstance(data, dict) else []
            else:
                self.drafts = []
        except (OSError, ValueError):
            self.drafts = []

    def save_to_file(self) -> None:
        self._atomic_write({
            'version': 1,
            'last_modified': datetime.now().isoformat(),
            'drafts': self.drafts,
        })

    @staticmethod
    def key(username: str, survey_type_id: str, community: str) -> str:
        """Same key as the signpost and as the browser's own store, plus who."""
        return f"{(username or '').strip()}::{(survey_type_id or '').strip()}::{(community or '').strip()}"

    def _find(self, did: str) -> Optional[Dict]:
        return next((d for d in self.drafts if d.get('id') == did), None)

    def _new(self, username, community, survey_type_id) -> Dict:
        now = datetime.now().isoformat()
        d = {
            'id': self.key(username, survey_type_id, community),
            'username': username, 'community': community,
            'survey_type_id': survey_type_id or '',
            'responses': {}, 'action_items': [], 'notes': '', 'photos': {},
            'total': 0, 'saved_at': 0, 'created_at': now, 'updated_at': now,
        }
        self.drafts.append(d)
        return d

    # ------------------------------------------------------------- reading

    def get(self, username: str, community: str, survey_type_id: str) -> Optional[Dict]:
        with self._lock:
            self._ensure_fresh()
            d = self._find(self.key(username, survey_type_id, community))
            return json.loads(json.dumps(d)) if d else None

    # ------------------------------------------------------------- writing

    def save_content(self, username: str, community: str, survey_type_id: str, *,
                     responses, action_items, notes, total: int = 0,
                     saved_at: int = 0) -> Dict:
        """Everything typed so far. Photos are sent on their own."""
        with self._lock:
            self._ensure_fresh()
            d = self._find(self.key(username, survey_type_id, community)) \
                or self._new(username, community, survey_type_id)
            d['responses'] = clean_responses(responses)
            d['action_items'] = clean_action_items(action_items)
            d['notes'] = _text(notes, MAX_NOTES)
            try:
                d['total'] = max(0, min(int(total or 0), 9999))
            except (TypeError, ValueError):
                d['total'] = 0
            try:
                d['saved_at'] = max(0, int(saved_at or 0))
            except (TypeError, ValueError):
                d['saved_at'] = 0
            d['updated_at'] = datetime.now().isoformat()
            # Working on it again starts a new quiet spell.
            d['reminded'] = []
            self.save_to_file()
            return json.loads(json.dumps(d))

    def set_photo(self, username: str, community: str, survey_type_id: str,
                  slot: str, path: str, name: str, ctype: str, size: int) -> Optional[str]:
        """Record a photo for a slot. Returns the path it replaced, for deletion."""
        if not valid_slot(slot):
            return None
        with self._lock:
            self._ensure_fresh()
            d = self._find(self.key(username, survey_type_id, community)) \
                or self._new(username, community, survey_type_id)
            old = (d.get('photos') or {}).get(slot, {}).get('path')
            d.setdefault('photos', {})[slot] = {
                'path': path, 'name': _text(name, 200) or 'photo.jpg',
                'type': _text(ctype, 60) or 'image/jpeg', 'size': int(size or 0),
            }
            d['updated_at'] = datetime.now().isoformat()
            d['reminded'] = []
            self.save_to_file()
            return old if old and old != path else None

    def all(self) -> List[Dict]:
        """Every draft, copied. For the daily reminder pass and admin support."""
        with self._lock:
            self._ensure_fresh()
            return json.loads(json.dumps(self.drafts))

    def due_reminders(self, now: datetime) -> List[Dict]:
        """Drafts owed a reminder: quiet for at least one REMIND_AT_DAYS mark
        not yet reminded in this quiet spell. One reminder per draft per run,
        however many marks a missed weekend has carried it past."""
        out = []
        for d in self.all():
            if not (d.get('responses') or d.get('action_items') or (d.get('notes') or '').strip()
                    or d.get('photos')):
                continue
            try:
                quiet = (now - datetime.fromisoformat(d.get('updated_at') or '')).days
            except ValueError:
                continue
            done = set(d.get('reminded') or [])
            due = [m for m in REMIND_AT_DAYS if quiet >= m and m not in done]
            if due and quiet < TTL_DAYS:
                out.append({**d, 'quiet_days': quiet, 'stage': max(due),
                            'days_left': max(0, TTL_DAYS - quiet)})
        return out

    def mark_reminded(self, draft_id: str, quiet_days: int) -> None:
        """Record every mark up to quiet_days as reminded. Does not touch
        updated_at: a reminder is not activity, and must not postpone expiry."""
        with self._lock:
            self._ensure_fresh()
            d = self._find(draft_id)
            if not d:
                return
            d['reminded'] = sorted({*(d.get('reminded') or []),
                                    *[m for m in REMIND_AT_DAYS if quiet_days >= m]})
            self.save_to_file()

    def remove_photo(self, username: str, community: str, survey_type_id: str,
                     slot: str) -> Optional[str]:
        """Forget a slot's photo. Returns its path, for deletion."""
        with self._lock:
            self._ensure_fresh()
            d = self._find(self.key(username, survey_type_id, community))
            if not d or slot not in (d.get('photos') or {}):
                return None
            old = d['photos'].pop(slot).get('path')
            d['updated_at'] = datetime.now().isoformat()
            self.save_to_file()
            return old

    def discard(self, username: str, community: str, survey_type_id: str) -> List[str]:
        """The visit was sent, or thrown away. Returns photo paths to delete."""
        with self._lock:
            self._ensure_fresh()
            did = self.key(username, survey_type_id, community)
            d = self._find(did)
            if not d:
                return []
            self.drafts = [x for x in self.drafts if x.get('id') != did]
            self.save_to_file()
            return [p.get('path') for p in (d.get('photos') or {}).values() if p.get('path')]

    def prune(self) -> List[str]:
        """Drop drafts not saved for TTL_DAYS. Returns their photo paths."""
        cutoff = (datetime.now() - timedelta(days=TTL_DAYS)).isoformat()
        with self._lock:
            self._ensure_fresh()
            old = [d for d in self.drafts if (d.get('updated_at') or '') < cutoff]
            if not old:
                return []
            self.drafts = [d for d in self.drafts if (d.get('updated_at') or '') >= cutoff]
            self.save_to_file()
        return [p.get('path') for d in old for p in (d.get('photos') or {}).values() if p.get('path')]

    def rename_community(self, old_name: str, new_name: str) -> int:
        """A draft is keyed on the community's name, so a rename moves it."""
        changed = 0
        with self._lock:
            self._ensure_fresh()
            for d in self.drafts:
                if d.get('community') == old_name:
                    d['community'] = new_name
                    d['id'] = self.key(d.get('username'), d.get('survey_type_id'), new_name)
                    changed += 1
            if changed:
                self.save_to_file()
        return changed
