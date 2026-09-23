"""
Nudging the things that went quiet.

Greg asked for an automatic email to the people holding open action items
that have had no update in 15 or 30 days. The criterion he chose is the
right one and worth keeping in view: *no update*, not *not closed*. An item
somebody commented on three days ago is being worked; chasing it teaches
people to filter the sender. Silence is what this is for.

Three different things count as an open action item, because all three are
what the Action Items view shows:

  - a standard that failed and has not been marked addressed
  - an item raised by hand at the end of a visit, still unresolved
  - an issue raised from the dashboard, still unresolved

They live in different files and carry their dates differently, so most of
this module is about reading all three as one kind of thing.

Two rules are not negotiable:

  - An internal item never appears in an Executive Director's email. The
    whole point of that flag is that leadership can raise something the
    community does not see, and a reminder is a new place for it to leak.
  - Nothing is sent twice. The job runs daily; without a record of what has
    already gone out, every run repeats yesterday.

And one deliberate limitation: the clock starts when the ledger is armed,
not when the item was opened. Switching this on should not empty two months
of backlog into everybody's inbox on a Tuesday morning.
"""

import json
import os
import re
from datetime import datetime
from typing import Callable, Dict, List, Optional

from .json_store import JsonFileBacked

# The two nudges, in days of silence. Ordered, because an item that has been
# quiet for 40 days is past both and should be reported at the later one.
STAGES = (15, 30)

# Kinds, kept as constants so a typo in one place cannot quietly mean
# "no items of this kind" somewhere else.
KIND_STANDARD = 'standard'
KIND_MANUAL = 'manual'
KIND_RAISED = 'raised'


# --------------------------------------------------------------- reading time

def _parse(ts) -> Optional[datetime]:
    """A stored timestamp, or None if it is missing or unreadable.

    Everything here is written by datetime.isoformat(), but data that has
    survived a few migrations is worth reading defensively: a date that does
    not parse must not become "opened at the epoch" and fire immediately.
    """
    if not ts or not isinstance(ts, str):
        return None
    try:
        return datetime.fromisoformat(ts.strip())
    except ValueError:
        return None


_ID_MILLIS = re.compile(r'^[a-z]+_(\d{10,})_')


def _opened_from_id(item_id: str) -> Optional[datetime]:
    """Manual and raised items embed their creation time in their id.

    `act_1758312094123_4821` — the middle number is milliseconds. Manual
    items carry no created_at of their own, so this is the only record of
    when one was written. It is read rather than guessed at, and anything
    that does not match falls back to the visit's own date.
    """
    m = _ID_MILLIS.match((item_id or '').strip())
    if not m:
        return None
    try:
        return datetime.fromtimestamp(int(m.group(1)) / 1000.0)
    except (ValueError, OverflowError, OSError):
        return None


def _latest_comment(comments) -> Optional[datetime]:
    """When somebody last said something on this item."""
    best = None
    for c in (comments or []):
        if not isinstance(c, dict):
            continue
        at = _parse(c.get('at'))
        if at and (best is None or at > best):
            best = at
    return best


# ------------------------------------------------------- what is open, and when

def _item(kind, key, community, text, opened, comments, internal=False):
    """One open item, flattened into the shape the rest of this works on.

    last_activity is what the whole feature turns on: the most recent thing
    that happened to this item. A comment counts. Being opened counts. If
    neither parses, the item is skipped rather than treated as ancient.
    """
    opened = opened or None
    last = _latest_comment(comments)
    if opened and (last is None or opened > last):
        last = opened
    if last is None:
        return None
    return {
        'kind': kind,
        'key': key,
        'community': (community or '').strip(),
        'text': (text or '').strip(),
        'opened': opened,
        'last_activity': last,
        'internal': bool(internal),
    }


def open_items(submissions, raised=None) -> List[Dict]:
    """Every open action item, from all three places they live.

    Pure: give it data, get a list. No disk, no clock, no email — which is
    what makes the rules above testable without sending anything.
    """
    out = []

    for sub in (submissions or []):
        if not isinstance(sub, dict):
            continue
        sub_id = sub.get('id') or ''
        community = sub.get('community') or ''
        submitted = _parse(sub.get('submitted_at'))

        # A failed standard, until somebody marks it addressed.
        for resp in (sub.get('responses') or []):
            if not isinstance(resp, dict) or resp.get('condition') != 'Fail':
                continue
            if resp.get('addressed'):
                continue
            qid = resp.get('question_id') or ''
            it = _item(
                KIND_STANDARD, f'{KIND_STANDARD}::{sub_id}::{qid}', community,
                resp.get('question_text') or resp.get('description') or qid,
                _parse(resp.get('answered_at')) or submitted,
                resp.get('comments'))
            if it:
                out.append(it)

        # An item written by hand at the end of the visit.
        for ai in (sub.get('action_items') or []):
            if not isinstance(ai, dict) or ai.get('resolved'):
                continue
            aid = ai.get('id') or ''
            it = _item(
                KIND_MANUAL, f'{KIND_MANUAL}::{sub_id}::{aid}', community,
                ai.get('text'),
                _opened_from_id(aid) or submitted,
                ai.get('comments'))
            if it:
                out.append(it)

    # An issue raised from the dashboard.
    for r in (raised or []):
        if not isinstance(r, dict) or r.get('resolved'):
            continue
        rid = r.get('id') or ''
        it = _item(
            KIND_RAISED, f'{KIND_RAISED}::{rid}', r.get('community'),
            r.get('text'),
            _parse(r.get('raised_at')) or _opened_from_id(rid),
            r.get('comments'),
            internal=(r.get('visibility') == 'internal'))
        if it:
            out.append(it)

    return out


def due(items, now: datetime, armed_at: Optional[datetime],
        already: Callable[[str, int], bool], stages=STAGES) -> List[Dict]:
    """Which items have gone quiet long enough, and at which stage.

    Each item is reported at the highest stage it has reached and has not
    already been told about, so an item that has been silent for 40 days on
    the day this is switched on reports once at 30 rather than twice.

    `armed_at` is the backstop against emptying the backlog: an item whose
    silence began before the feature existed is not somebody ignoring a
    reminder, because there was no reminder. Its clock starts at the moment
    the ledger was armed.
    """
    out = []
    for it in (items or []):
        last = it.get('last_activity')
        if not isinstance(last, datetime):
            continue
        # Silence only counts from when there was somebody listening.
        began = max(last, armed_at) if armed_at else last
        quiet = (now - began).days
        if quiet < 0:
            continue
        reached = [s for s in sorted(stages) if quiet >= s]
        if not reached:
            continue
        # Only stages above the highest one already sent are still owed.
        #
        # Looking for "the highest unsent stage" instead is wrong in a way
        # that is easy to miss: an item that already had its 30-day notice
        # has never had a 15-day one, so that reading hands it the 15-day
        # email next — escalating and then de-escalating, about an item that
        # has only got quieter.
        told = [s for s in reached if already(it['key'], s)]
        owed = [s for s in reached if not told or s > max(told)]
        if not owed:
            continue
        stage = max(owed)
        row = dict(it)
        row['stage'] = stage
        row['quiet_days'] = quiet
        out.append(row)
    return out


def for_executive_director(rows) -> Dict[str, List[Dict]]:
    """Due items grouped by community, with internal ones removed.

    The filter is here rather than at the call site on purpose: an ED digest
    is only ever built through this function, so there is one place to read
    to know the rule holds, and one place for a test to aim at.
    """
    out: Dict[str, List[Dict]] = {}
    for r in rows:
        if r.get('internal'):
            continue
        if not r.get('community'):
            continue
        out.setdefault(r['community'], []).append(r)
    return out


def for_regional(rows, stage=30) -> Dict[str, List[Dict]]:
    """Due items for the regional's own digest: one stage, grouped by community.

    Internal items are kept. Regionals are the leadership that flag is for,
    and this email is theirs alone — it is not the ED's message with somebody
    copied in, precisely so that keeping them does not leak them.
    """
    out: Dict[str, List[Dict]] = {}
    for r in rows:
        if r.get('stage') != stage or not r.get('community'):
            continue
        out.setdefault(r['community'], []).append(r)
    return out


# --------------------------------------------------------------- the ledger

class ReminderLedger(JsonFileBacked):
    """What has already been said, and when we started saying it.

    Small on purpose, and in its own file. The alternative — a flag on each
    item — means every run writes inspections.json, which is where the real
    visits live and where a bad write costs the most.
    """

    def __init__(self, storage_path: str):
        self.storage_path = storage_path
        self.armed_at: str = ''
        self.paused: bool = False
        self.sent: Dict[str, Dict[str, str]] = {}
        self._init_store()
        self.load_from_file()
        self._mark_loaded()

    # ------------------------------------------------------------ storage

    def load_from_file(self) -> None:
        try:
            if os.path.exists(self.storage_path):
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    self.armed_at = data.get('armed_at') or ''
                    self.paused = bool(data.get('paused'))
                    self.sent = data.get('sent') or {}
        except (OSError, ValueError):
            self.armed_at, self.paused, self.sent = '', False, {}

    def save_to_file(self) -> None:
        self._atomic_write({
            'version': 1,
            'last_modified': datetime.now().isoformat(),
            'armed_at': self.armed_at,
            'paused': self.paused,
            'sent': self.sent,
        })

    # ------------------------------------------------------------- arming

    def arm(self, when: Optional[datetime] = None) -> datetime:
        """Start the clock, once. Returns the moment it started.

        Idempotent: calling it again on a ledger that is already armed keeps
        the original date, so a redeploy or a second run cannot silently
        reset everybody's clock to today.
        """
        with self._lock:
            self._ensure_fresh()
            if not self.armed_at:
                self.armed_at = (when or datetime.now()).isoformat()
                self.save_to_file()
            return _parse(self.armed_at)

    def armed(self) -> Optional[datetime]:
        self._ensure_fresh()
        return _parse(self.armed_at)

    def set_paused(self, paused: bool) -> bool:
        """The stop button.

        Lives in the data rather than in the code so that turning it off is a
        ten-second edit on the server at six in the morning, not a deploy.
        Stopping the timer works too; this exists so that either one is enough.
        """
        with self._lock:
            self._ensure_fresh()
            self.paused = bool(paused)
            self.save_to_file()
            return self.paused

    def is_paused(self) -> bool:
        self._ensure_fresh()
        return bool(self.paused)

    # -------------------------------------------------------- what was sent

    def already(self, key: str, stage: int) -> bool:
        self._ensure_fresh()
        return str(stage) in (self.sent.get(key) or {})

    def mark(self, key: str, stage: int, when: Optional[datetime] = None) -> None:
        with self._lock:
            self._ensure_fresh()
            self.sent.setdefault(key, {})[str(stage)] = (when or datetime.now()).isoformat()
            self.save_to_file()

    def mark_many(self, rows, when: Optional[datetime] = None) -> int:
        """Record a whole run at once — one write instead of one per item."""
        if not rows:
            return 0
        stamp = (when or datetime.now()).isoformat()
        with self._lock:
            self._ensure_fresh()
            for r in rows:
                self.sent.setdefault(r['key'], {})[str(r['stage'])] = stamp
            self.save_to_file()
        return len(rows)

    def forget_closed(self, live_keys) -> int:
        """Drop the record of items that no longer exist.

        Without this the ledger grows forever. An item that was closed is
        never coming back — its key contains the submission and question it
        belonged to — so nothing is lost by forgetting it was nudged.
        """
        live = set(live_keys or [])
        with self._lock:
            self._ensure_fresh()
            gone = [k for k in self.sent if k not in live]
            for k in gone:
                del self.sent[k]
            if gone:
                self.save_to_file()
            return len(gone)
