#!/usr/bin/env python3
"""
Are the Executive Directors actually set up?

Having an account is only the first of three things. An ED with no email
address receives nothing after a visit, and an ED who has never signed in
isn't using it however well it was set up. This reports all three per
community, so "have we onboarded the EDs" has an answer instead of a guess.

Read-only.

    python3 deploy/ed_readiness.py            # summary + anything that needs fixing
    python3 deploy/ed_readiness.py --all      # every community
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(os.path.dirname(HERE), 'app_mantenimiento', 'data')
SHOW_ALL = '--all' in sys.argv


def load(name, key=None):
    path = os.path.join(DATA, name)
    if not os.path.exists(path):
        return {} if key is None else []
    with open(path, encoding='utf-8') as f:
        d = json.load(f)
    if key is None:
        return d
    return d.get(key, d) if isinstance(d, dict) else d


regions = load('regions.json', 'regions')
raw_users = load('users.json', 'users')
users = ([{**v, 'username': k} for k, v in raw_users.items()]
         if isinstance(raw_users, dict) else list(raw_users or []))
presence = (load('presence.json') or {}).get('users', {}) or {}

communities = []
for r in regions:
    for c in (r.get('communities') or []):
        if c not in communities:
            communities.append((c, r.get('name', r.get('id'))))

# community -> the staff accounts covering it
by_community = {}
for u in users:
    if u.get('role') != 'staff':
        continue
    covered = u.get('communities') or ([u.get('community')] if u.get('community') else [])
    for c in covered:
        by_community.setdefault(c, []).append(u)

rows = []
for name, region in communities:
    eds = by_community.get(name, [])
    if not eds:
        rows.append((name, region, None, False, False))
        continue
    for u in eds:
        has_email = bool((u.get('email') or '').strip())
        signed_in = bool(presence.get(u.get('username'), {}).get('last_login'))
        rows.append((name, region, u, has_email, signed_in))

total = len(communities)
with_ed = sum(1 for r in rows if r[2])
with_email = sum(1 for r in rows if r[2] and r[3])
signed = sum(1 for r in rows if r[2] and r[4])

print(f'{total} communities\n')
print(f'  have an ED account ........... {with_ed}')
print(f'  ... with an email address .... {with_email}')
print(f'  ... who has signed in ........ {signed}')
print()

problems = [r for r in rows if not r[2] or not r[3] or not r[4]]
listing = rows if SHOW_ALL else problems

if not problems:
    print('Every community has an ED with an email address who has signed in.')
    sys.exit(0)

print('Needs attention:' if not SHOW_ALL else 'All communities:')
print('  ' + '-' * 74)
for name, region, u, has_email, signed_in in listing:
    if u is None:
        print(f'  {name[:44]:<44} {region[:10]:<10} no ED account')
        continue
    flags = []
    if not has_email:
        flags.append('NO EMAIL — gets nothing after a visit')
    if not signed_in:
        flags.append('never signed in')
    label = ', '.join(flags) if flags else 'ok'
    print(f'  {name[:44]:<44} {region[:10]:<10} {u.get("display_name", u["username"])[:18]:<18} {label}')

print()
if any(r[2] and not r[3] for r in rows):
    print('An ED with no email address is invisible to the app: no findings email,')
    print('no move-in reminders, no password reset. Fix those first — People, then')
    print('the pencil on their row.')
if any(r[2] and not r[4] for r in rows):
    print('"Never signed in" usually means the welcome email went to Junk. Worth')
    print('re-sending from People rather than assuming they chose not to use it.')
sys.exit(1)
