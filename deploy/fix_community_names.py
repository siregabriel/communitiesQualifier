#!/usr/bin/env python3
"""
Repair community names stored under a spelling the app no longer uses.

Standards used to offer their community checkboxes from a fixed list in the
code, while visits used the region rosters. The two drifted on two names, so a
standard could be assigned to "The Overlook at Suwanee, Suwanee" while a visit
for "The Overlook at Suwanee" found no standards at all — the checkbox looked
ticked and the regional got "No questions available" standing in a building.

The code now reads one list. This repairs what was written under the old
spelling.

    python3 deploy/fix_community_names.py            # report only, changes nothing
    python3 deploy/fix_community_names.py --apply    # writes, after a backup

Safe to run twice: once the names match there is nothing left to change.
"""
import json
import os
import shutil
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(os.path.dirname(HERE), 'app_mantenimiento', 'data')
APPLY = '--apply' in sys.argv

# Old spelling -> the name the region rosters use.
RENAMES = {
    'The Overlook at Suwanee, Suwanee': 'The Overlook at Suwanee',
    'The Oscar at Veramendi (June 2026)': 'The Oscar at Veramendi',
}

# Where a community name can be stored. Each entry: file, the key holding the
# records, and how to find community names inside one record.
TARGETS = [
    ('questions.json', 'questions', 'communities'),   # list of names
    ('inspections.json', 'submissions', 'community'),  # single name
    ('moveins.json', 'moveins', 'community'),
    ('community_covers.json', None, 'community'),
]


def load(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def records(doc, key):
    if key and isinstance(doc, dict):
        return doc.get(key) or []
    if isinstance(doc, dict):
        return list(doc.values())
    return doc or []


changes = []
for filename, key, field in TARGETS:
    path = os.path.join(DATA, filename)
    if not os.path.exists(path):
        continue
    doc = load(path)
    hits = 0
    for rec in records(doc, key):
        if not isinstance(rec, dict):
            continue
        value = rec.get(field)
        if isinstance(value, list):
            for i, name in enumerate(value):
                if name in RENAMES:
                    value[i] = RENAMES[name]
                    hits += 1
        elif value in RENAMES:
            rec[field] = RENAMES[value]
            hits += 1
    if hits:
        changes.append((filename, hits, doc, path))

if not changes:
    print('Nothing to repair — every community name already matches the rosters.')
    sys.exit(0)

print('Names to repair:')
for old, new in RENAMES.items():
    print(f'  {old!r}\n    -> {new!r}')
print()
for filename, hits, _, _ in changes:
    print(f'  {filename:<24} {hits} reference{"s" if hits != 1 else ""}')

if not APPLY:
    print('\nNothing was written. Re-run with --apply to make these changes.')
    sys.exit(0)

stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
print()
for filename, hits, doc, path in changes:
    backup = f'{path}.before-rename-{stamp}'
    shutil.copy2(path, backup)
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(doc, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)          # atomic, so a reader never sees half a file
    print(f'  {filename}: {hits} repaired  (backup: {os.path.basename(backup)})')

# Read back from disk rather than trusting what we just held in memory.
print()
left = 0
for filename, key, field in TARGETS:
    path = os.path.join(DATA, filename)
    if os.path.exists(path):
        left += sum(json.dumps(load(path)).count(old) for old in RENAMES)
print('Old names still present after the repair:', left)
sys.exit(0 if left == 0 else 1)
