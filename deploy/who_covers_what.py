#!/usr/bin/env python3
"""
Who covers which communities.

Read-only. Answers the question that comes up whenever a regional says they
can't see a building: which region owns it, and who is on that region.

    python3 deploy/who_covers_what.py                 # every region
    python3 deploy/who_covers_what.py Marissa         # what this person covers
    python3 deploy/who_covers_what.py Simpsonville    # who covers this community
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(os.path.dirname(HERE), 'app_mantenimiento', 'data')


def load(name, key):
    with open(os.path.join(DATA, name), encoding='utf-8') as f:
        d = json.load(f)
    return d.get(key, d) if isinstance(d, dict) else d


regions = load('regions.json', 'regions')

# users.json is keyed by username, so carry the key onto each record.
_raw_users = load('users.json', 'users')
users = ([{**v, 'username': k} for k, v in _raw_users.items()]
         if isinstance(_raw_users, dict) else list(_raw_users or []))
needle = ' '.join(sys.argv[1:]).strip().lower()


def leaders(r):
    out = []
    for l in (r.get('leadership') or []):
        name = (l.get('name') or '').strip()
        if not name or name.lower() == 'open':
            continue
        out.append((name, (l.get('email') or '').strip()))
    return out


if not needle:
    for r in regions:
        comms = r.get('communities') or []
        if not comms and not leaders(r):
            continue
        kind = ' (company-wide)' if r.get('kind') == 'corporate' else ''
        print(f"\n{r.get('name', r['id'])}{kind} — {len(comms)} communities")
        for name, email in leaders(r):
            print(f"    {name}{'' if email else '   << no email on file'}")
        for c in comms:
            print(f'      - {c}')
    sys.exit(0)

# A person?
hits = []
for r in regions:
    for name, email in leaders(r):
        if needle in name.lower():
            hits.append((name, email, r))
for u in users:
    nm = (u.get('display_name') or u.get('username') or '')
    if needle in nm.lower():
        hits.append((nm, u.get('email', ''), None if u.get('role') == 'staff' else
                     next((r for r in regions if r.get('id') == u.get('region_id')), None)))
        if u.get('role') == 'staff':
            print(f"\n{nm} — Executive Director")
            for c in (u.get('communities') or [u.get('community')]):
                if c:
                    print(f'    covers: {c}')

for name, email, r in hits:
    if r is None:
        continue
    comms = r.get('communities') or []
    print(f"\n{name} — {r.get('name', r['id'])} region, {len(comms)} communities")
    if not email:
        print('    << no email address on file — visit and move-in emails will skip them')
    for c in comms:
        print(f'      - {c}')

# A community?
matches = [(c, r) for r in regions for c in (r.get('communities') or [])
           if needle in c.lower()]
for c, r in matches:
    print(f"\n{c}")
    print(f"    region : {r.get('name', r['id'])}")
    people = leaders(r)
    print(f"    covered by: {', '.join(n for n, _ in people) if people else 'nobody on this region'}")

if not hits and not matches:
    print(f'Nothing matches "{needle}".')
    print('Try part of a person\'s name, or part of a community name.')
