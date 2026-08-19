#!/usr/bin/env python3
"""
Compare a proposed list of standards against the ones already in the app.

Capturing a standard that already exists is the mistake worth avoiding: it
appears twice on the form and counts twice toward the score. This says which
proposals are genuinely new, which already exist, and — for the ones that
exist — which reviews they are already ticked for.

Read-only. Nothing is written.

    python3 deploy/compare_standards.py                 # the built-in list
    python3 deploy/compare_standards.py proposals.txt   # one standard per line
"""
import difflib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(os.path.dirname(HERE), 'app_mantenimiento', 'data')

# Angie's list for the Operations walk, as sent.
DEFAULT = [
    "First Impression of the community is withing the Atlas Standard",
    "Vacant Rooms Rent Readies",
    "Check for current Fire Drills and Elopement Drills",
    "Inspect the Emergency State Binder - must be updated",
    "Check dates on Fire Extinguisher - must be current",
    "Pull the Missed Meds and Exceptions in clinical",
    "Memory Care - check for chemicals in residents' rooms and common areas",
    "ED Follow up call being completed - pull report in Welcome Home",
    "Pendant response time - less than 5 minutes",
    "Speak 2 in apartments - including NFS and working - ask staff to return demonstrate",
]

STOP = {'the', 'a', 'an', 'of', 'is', 'in', 'and', 'for', 'to', 'be', 'are',
        'on', 'at', 'with', 'must', 'check', 'that', 'this', 'it'}


def load(name, key):
    with open(os.path.join(DATA, name), encoding='utf-8') as f:
        d = json.load(f)
    return d.get(key, d) if isinstance(d, dict) else d


def normalise(text):
    text = re.sub(r'<[^>]+>', ' ', text or '')
    text = re.sub(r"[^a-z0-9 ]+", ' ', text.lower())
    return ' '.join(w for w in text.split() if w not in STOP)


def score(a, b):
    """0..1 similarity, blending word overlap with sequence similarity so that
    "Vacant Rooms Rent Readies" still finds "Vacant Rooms are Rent Ready"."""
    na, nb = normalise(a), normalise(b)
    if not na or not nb:
        return 0.0
    wa, wb = set(na.split()), set(nb.split())
    overlap = len(wa & wb) / max(1, min(len(wa), len(wb)))
    return max(overlap, difflib.SequenceMatcher(None, na, nb).ratio())


proposals = DEFAULT
if len(sys.argv) > 1:
    with open(sys.argv[1], encoding='utf-8') as f:
        proposals = [l.strip() for l in f if l.strip()]

questions = [q for q in load('questions.json', 'questions') if q.get('is_active', True)]
types = {t['id']: t.get('name', t['id']) for t in load('survey_types.json', 'survey_types')}

print(f'{len(proposals)} proposed, {len(questions)} active standards in the app.\n')

new, existing = [], []
for p in proposals:
    ranked = sorted(((score(p, q.get('text', '')), q) for q in questions),
                    key=lambda x: -x[0])
    best, match = ranked[0] if ranked else (0.0, None)
    if best >= 0.55:
        existing.append((p, match, best))
    else:
        new.append((p, match, best))

if existing:
    print('ALREADY IN THE APP — tick the review, do not create these again')
    print('=' * 72)
    for p, q, s in existing:
        marks = q.get('survey_types') or []
        where = ', '.join(types.get(t, t) for t in marks) if marks else 'every review'
        print(f'\n  proposed : {p}')
        print(f'  existing : {q.get("text", "")}')
        print(f'  match    : {int(s * 100)}%   already in: {where}')
        crit = q.get('pass_criteria') or []
        print(f'  criteria : {len(crit)} already written'
              + (f' — e.g. "{crit[0][:56]}"' if crit else ''))
    print()

if new:
    print('NOT IN THE APP — these would be created')
    print('=' * 72)
    for p, q, s in new:
        print(f'\n  {p}')
        if q is not None and s >= 0.3:
            print(f'      closest existing: "{q.get("text", "")}" ({int(s * 100)}%)')

print()
print(f'Summary: {len(existing)} already exist, {len(new)} would be new.')
if existing:
    print('For the ones that exist, adding the review to them keeps one history')
    print('per standard. Creating a second copy splits it, and the score counts')
    print('the item twice.')
