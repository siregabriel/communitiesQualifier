#!/usr/bin/env python3
"""
Which visits lost photos to the filename collision.

Photos used to be named "<user>_<unix seconds>". Every photo in a visit is
saved inside the same second, so they overwrote each other in S3 and every
standard ended up pointing at whichever one was written last. The naming is
fixed; this reports what the old naming already cost.

Read-only — it only reads inspections.json.

    python3 deploy/photo_collisions.py
"""
import json
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(os.path.dirname(HERE), 'app_mantenimiento', 'data')

with open(os.path.join(DATA, 'inspections.json'), encoding='utf-8') as f:
    doc = json.load(f)
submissions = doc.get('submissions', doc) if isinstance(doc, dict) else doc

affected = []
for sub in submissions:
    seen = defaultdict(list)
    for r in (sub.get('responses') or []):
        p = r.get('photo_path')
        if p:
            seen[p].append(r.get('question_text') or r.get('question_id') or '?')

    shared = {p: qs for p, qs in seen.items() if len(qs) > 1}
    if shared:
        lost = sum(len(qs) - 1 for qs in shared.values())
        affected.append({
            'id': sub.get('id'),
            'community': sub.get('community', ''),
            'when': (sub.get('submitted_at') or '')[:10],
            'who': sub.get('inspector_name') or sub.get('username', ''),
            'photos_kept': len(seen),
            'photos_lost': lost,
            'standards': sorted({q for qs in shared.values() for q in qs}),
        })

with_photos = sum(1 for s in submissions
                  if any(r.get('photo_path') for r in (s.get('responses') or [])))
print(f'{len(submissions)} visits on record, {with_photos} of them with photos.')
print()

if not affected:
    print('No visit has two standards sharing one photo. Nothing was lost.')
    sys.exit(0)

affected.sort(key=lambda a: -a['photos_lost'])
total = sum(a['photos_lost'] for a in affected)
print(f'{len(affected)} visits lost photos — {total} in total:')
print()
for a in affected:
    print(f"  {a['when']}  {a['community']}")
    print(f"      by {a['who']} · {a['photos_lost']} photo"
          f"{'s' if a['photos_lost'] != 1 else ''} lost, {a['photos_kept']} kept")
    for s in a['standards'][:8]:
        print(f'        - {s[:66]}')
    if len(a['standards']) > 8:
        print(f'        ... and {len(a["standards"]) - 8} more')
    print()

print('These standards now show the same picture as each other. The originals')
print('were overwritten in S3 and the bucket has no versioning, so they cannot')
print('be recovered — the photos would have to be taken again and attached as')
print('comments, or the community re-visited.')
sys.exit(1)
