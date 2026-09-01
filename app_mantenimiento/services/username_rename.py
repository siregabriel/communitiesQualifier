"""
Changing somebody's sign-in name.

People get married, and names get typed wrong the first time. The username was
never meant to move — it is the key everything else is filed under — so moving
it means moving every record that points at it, in one go:

    users.json          the account itself (admin-created people)
    regions.json        the account itself (region and corporate members, whose
                        username is pinned on their leadership entry)
    profiles.json       their display name, photo, and the password they set —
                        miss this one and they simply cannot sign in
    inspections.json    every visit they sent, and inside those, every finding
                        they addressed and every comment they left
    activity.json       their trail in Live
    raised_items.json   items they raised, and comments on anyone's item
    draft_notices.json  the note that they have a visit in progress
    presence.json       when they were last seen

Two decisions worth knowing about:

Rather than listing the paths where a username can appear, this walks the whole
document and replaces it wherever it sits under a field that holds one. The
paths are nested several levels deep — a comment on a finding inside a response
inside a submission — and a list written by hand is a list with something
missing from it, which here means somebody's work quietly detached from them.

And it copies every file before touching it, then reads them all back and
counts. If what came out does not match what went in, it puts the copies back
and reports the failure rather than leaving a person split across two names.
There is no transaction across eight files; this is the next best thing, and
the operation is safe to simply run again.
"""

import json
import os
import re
import shutil
from datetime import datetime
from typing import Dict, List, Tuple

# Fields whose value is a username. Deliberately excludes 'author' and
# 'raised_by_name': those hold the display name as it read at the time, which
# is a record of what was shown, not a reference to the account.
IDENTITY_FIELDS = (
    'username',
    'raised_by',
    'resolved_by',
    'addressed_by',
    'created_by',
    'deleted_by',
    'verified_by',
)

# Files where the username is also a key in a map, not just a value in a field.
KEYED_MAPS = {
    'users.json': ('users',),
    'profiles.json': ('profiles',),
    'presence.json': ('users',),
}

TOUCHED = ('users.json', 'regions.json', 'profiles.json', 'inspections.json',
           'activity.json', 'raised_items.json', 'draft_notices.json',
           'presence.json')

USERNAME_RE = re.compile(r'^[a-z0-9][a-z0-9._-]{1,58}[a-z0-9]$')


class RenameError(Exception):
    """Refused before anything was written."""


def validate(new_name: str) -> str:
    """The shape a username has to have, or raise saying why."""
    name = (new_name or '').strip().lower()
    if not name:
        raise RenameError('Enter the new username.')
    if not USERNAME_RE.match(name):
        raise RenameError(
            'Use lowercase letters, numbers, dots, dashes or underscores — '
            'no spaces, and it cannot start or end with punctuation.')
    return name


def _swap(node, old: str, new: str) -> int:
    """Replace old with new anywhere it sits under an identity field.

    Returns how many values were changed, which is what the verification pass
    afterwards is counting.
    """
    changed = 0
    if isinstance(node, dict):
        for key, value in node.items():
            if key in IDENTITY_FIELDS and isinstance(value, str) and value == old:
                node[key] = new
                changed += 1
            # A draft notice's id is built from the username, so it moves too,
            # or the browser and the server disagree about which draft is which.
            elif key == 'id' and isinstance(value, str) and value.startswith(old + '::'):
                node[key] = new + value[len(old):]
                changed += 1
            else:
                changed += _swap(value, old, new)
    elif isinstance(node, list):
        for item in node:
            changed += _swap(item, old, new)
    return changed


def _count(node, name: str) -> int:
    """How many identity fields (and composite ids) point at this name."""
    found = 0
    if isinstance(node, dict):
        for key, value in node.items():
            if key in IDENTITY_FIELDS and value == name:
                found += 1
            elif key == 'id' and isinstance(value, str) and value.startswith(name + '::'):
                found += 1
            else:
                found += _count(value, name)
    elif isinstance(node, list):
        for item in node:
            found += _count(item, name)
    return found


def _keys_named(doc, filename: str, name: str) -> int:
    total = 0
    for map_name in KEYED_MAPS.get(filename, ()):
        section = doc.get(map_name) if isinstance(doc, dict) else None
        if isinstance(section, dict) and name in section:
            total += 1
    return total


class UsernameRenamer:
    """Moves a person's sign-in name across every file that records it."""

    def __init__(self, data_folder: str):
        self.data_folder = data_folder

    def _path(self, filename: str) -> str:
        return os.path.join(self.data_folder, filename)

    def _read(self, filename: str):
        path = self._path(filename)
        if not os.path.exists(path):
            return None
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _write(self, filename: str, doc) -> None:
        """Write via a temp file and replace, so a file is never half-written."""
        path = self._path(filename)
        tmp = path + '.rename.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(doc, f, indent=2, ensure_ascii=False)
        os.replace(tmp, path)
        if filename == self.RETIRED_FILE:
            # This process just changed it; never answer from what it read
            # before, whatever the timestamp says.
            self._retired_cache = None

    # ------------------------------------------------------------------ read

    def occurrences(self, name: str) -> Dict[str, int]:
        """Everywhere this name appears, per file. Reads only."""
        found = {}
        for filename in TOUCHED:
            doc = self._read(filename)
            if doc is None:
                continue
            n = _count(doc, name) + _keys_named(doc, filename, name)
            if n:
                found[filename] = n
        return found

    # ----------------------------------------------------------------- write

    def rename(self, old: str, new: str) -> Dict:
        """Move the name. Returns what was changed, per file.

        Raises RenameError without writing anything if the request does not
        make sense. If a write goes wrong partway, the copies taken at the
        start are put back before the error is raised.
        """
        old = (old or '').strip()
        new = validate(new)

        if old == new:
            raise RenameError('That is already their username.')
        if not old:
            raise RenameError('No account given.')

        before = self.occurrences(old)
        if not before:
            raise RenameError('No account found under "%s".' % old)
        if self.occurrences(new):
            raise RenameError('"%s" is already in use.' % new)

        backup = self._back_up()
        changed: Dict[str, int] = {}
        try:
            for filename in TOUCHED:
                doc = self._read(filename)
                if doc is None:
                    continue
                moved = 0
                # The account maps are keyed by username, so the entry moves
                # rather than having a field rewritten.
                for map_name in KEYED_MAPS.get(filename, ()):
                    section = doc.get(map_name) if isinstance(doc, dict) else None
                    if isinstance(section, dict) and old in section:
                        section[new] = section.pop(old)
                        moved += 1
                moved += _swap(doc, old, new)
                if moved:
                    if isinstance(doc, dict) and 'last_modified' in doc:
                        doc['last_modified'] = datetime.now().isoformat()
                    self._write(filename, doc)
                    changed[filename] = moved

            self._verify(old, new, before, changed)
        except Exception:
            self._restore(backup)
            raise

        # Only once the move is known to be sound, so a failed run does not
        # leave a live account listed as retired and sign that person out.
        self._remember_retired(old, new)

        return {'from': old, 'to': new, 'changed': changed,
                'total': sum(changed.values()), 'backup': backup}

    # ---------------------------------------------------------------- safety

    def _back_up(self) -> str:
        stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        folder = os.path.join(self.data_folder, 'renames', stamp)
        os.makedirs(folder, exist_ok=True)
        for filename in TOUCHED:
            path = self._path(filename)
            if os.path.exists(path):
                shutil.copy2(path, os.path.join(folder, filename))
        return folder

    def _restore(self, folder: str) -> None:
        for filename in os.listdir(folder):
            shutil.copy2(os.path.join(folder, filename), self._path(filename))

    def _verify(self, old: str, new: str, before: Dict[str, int],
                changed: Dict[str, int]) -> None:
        """Read everything back and check the person came out whole.

        The failure this is here to catch is the quiet one: the account moves,
        some of their history does not, and nobody notices until they open the
        app and their visits are gone.
        """
        after_old = self.occurrences(old)
        if after_old:
            raise RenameError(
                'Some records still point at "%s" (%s) — nothing was changed.'
                % (old, ', '.join('%s: %d' % kv for kv in sorted(after_old.items()))))

        after_new = self.occurrences(new)
        if after_new != before:
            raise RenameError(
                'The records did not come out matching what went in '
                '(expected %s, found %s) — nothing was changed.'
                % (before, after_new))

    # ------------------------------------------------- names left behind

    RETIRED_FILE = 'renames.json'
    # Long enough that anybody's open session has expired by then.
    RETIRED_DAYS = 30

    def _retired_path(self) -> str:
        return self._path(self.RETIRED_FILE)

    def _remember_retired(self, old: str, new: str) -> None:
        """Note that this name is no longer anybody's.

        A signed-in browser keeps the old name in its cookie, and it does not
        stop working on its own — it keeps reading, and anything written goes
        in under a person who is no longer there, which recreates the very
        orphans the rename just cleaned up. Recorded here so the session can be
        ended for exactly the name that moved, and nobody else's.
        """
        try:
            with open(self._retired_path(), encoding='utf-8') as f:
                doc = json.load(f)
        except (OSError, ValueError):
            doc = {}
        if not isinstance(doc, dict):
            doc = {}
        now = datetime.now()
        cutoff = now.timestamp() - self.RETIRED_DAYS * 86400
        doc = {k: v for k, v in doc.items()
               if isinstance(v, dict) and (v.get('ts') or 0) >= cutoff}
        doc[old] = {'to': new, 'at': now.isoformat(), 'ts': now.timestamp()}
        # The name being moved onto is in use again, so it must stop being
        # treated as retired. Undoing a rename — correcting a spelling the
        # other way — otherwise leaves that person bounced back to the sign-in
        # page every time they get past it.
        doc.pop(new, None)
        self._write(self.RETIRED_FILE, doc)

    def un_retire(self, name: str) -> None:
        """This name belongs to somebody again.

        Called when an account is created under a name that used to be
        somebody else's, so the new owner is not signed out on their behalf.
        """
        name = (name or '').strip()
        if not name:
            return
        try:
            with open(self._retired_path(), encoding='utf-8') as f:
                doc = json.load(f)
        except (OSError, ValueError):
            return
        if isinstance(doc, dict) and name in doc:
            doc.pop(name)
            self._write(self.RETIRED_FILE, doc)

    def retired(self, name: str):
        """What this name became, or None if it is not a retired name.

        Read on every signed-in request, so the file is not parsed each time.
        The cache is keyed on the file's timestamp *and its size*, not the
        timestamp alone: two writes close together land on the same timestamp
        — measured here, identical down to the nanosecond — and a timestamp
        alone would have gone on serving the previous answer. Undoing a rename
        does exactly that, and the stale answer signs the person out.
        """
        path = self._retired_path()
        try:
            st = os.stat(path)
            stamp = (st.st_mtime_ns, st.st_size)
        except OSError:
            self._retired_cache = None
            return None
        cache = getattr(self, '_retired_cache', None)
        if not cache or cache.get('stamp') != stamp:
            try:
                with open(path, encoding='utf-8') as f:
                    doc = json.load(f)
            except (OSError, ValueError):
                doc = {}
            cache = {'stamp': stamp, 'doc': doc if isinstance(doc, dict) else {}}
            self._retired_cache = cache
        entry = cache['doc'].get(name)
        return entry.get('to') if isinstance(entry, dict) else None

    # -------------------------------------------------------------- listing

    def backups(self) -> List[Tuple[str, str]]:
        """Past renames, newest first, as (stamp, path)."""
        root = os.path.join(self.data_folder, 'renames')
        if not os.path.isdir(root):
            return []
        stamps = sorted(os.listdir(root), reverse=True)
        return [(s, os.path.join(root, s)) for s in stamps]
