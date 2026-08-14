#!/usr/bin/env python3
"""
Why does a visit say "No questions available for this survey type"?

Read-only. Reads the JSON files directly — no app import, no environment, no
risk of changing anything. Answers the only question that matters: at which
step do the standards disappear for this community and this survey type?

    python3 deploy/why_no_questions.py "The Overlook at Suwanee" sales-marketing

With no arguments it reports every community and survey type that would come
up empty, which is the version worth running after editing standards.
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


questions = [q for q in load('questions.json', 'questions') if q.get('is_active', True)]
survey_types = load('survey_types.json', 'survey_types')
regions = load('regions.json', 'regions')
communities = []
for r in regions:
    for c in (r.get('communities') or []):
        if c not in communities:
            communities.append(c)


def matches_type(q, type_id):
    """Empty or missing survey_types means the standard is used by every type."""
    types = q.get('survey_types')
    return not types or type_id in types


def for_survey(community, type_id):
    in_community = [q for q in questions if community in (q.get('communities') or [])]
    return in_community, [q for q in in_community if matches_type(q, type_id)]


if len(sys.argv) >= 3:
    community, type_id = sys.argv[1], sys.argv[2]
    name = next((s.get('name') for s in survey_types if s.get('id') == type_id), None)
    print(f'Community    : {community}')
    print(f'Survey type  : {type_id}' + (f'  ({name})' if name else '  << no survey type with this id'))
    print()

    if community not in communities:
        print('!! This community is not on any region roster. Closest names:')
        low = community.lower()
        for c in communities:
            if any(w in c.lower() for w in low.split() if len(w) > 3):
                print(f'     {c}')
        sys.exit(1)

    in_community, final = for_survey(community, type_id)
    print(f'  active standards, in total ........... {len(questions)}')
    print(f'  ... assigned to this community ....... {len(in_community)}')
    print(f'  ... and used by this survey type ..... {len(final)}')
    print()
    if final:
        print('These would appear on the form:')
        for q in final[:20]:
            print(f'  - {q.get("text", "")[:70]}')
    elif not in_community:
        print('CAUSE: no standard lists this community.')
        print('       Standards -> open each one -> add the community.')
    else:
        print(f'CAUSE: {len(in_community)} standards cover this community, but none of')
        print(f'       them is used by "{name or type_id}".')
        print('       Standards -> open a standard -> tick that survey type.')
        seen = {}
        for q in in_community:
            for t in (q.get('survey_types') or ['(every type)']):
                seen[t] = seen.get(t, 0) + 1
        print()
        print('       What this community does have:')
        for t, n in sorted(seen.items(), key=lambda x: -x[1]):
            label = next((s.get('name') for s in survey_types if s.get('id') == t), t)
            print(f'         {label:<28} {n}')
    sys.exit(0 if final else 1)

# No arguments: every empty combination, so nothing has to be found by a
# regional standing in a building.
print(f'{len(questions)} active standards, {len(communities)} communities, '
      f'{len(survey_types)} survey types\n')
broken = []
for st in survey_types:
    empty = [c for c in communities if not for_survey(c, st['id'])[1]]
    flag = 'OK' if not empty else f'{len(empty)} communities have nothing'
    print(f"  {st.get('name', st['id']):<28} {flag}")
    if empty:
        broken.append((st, empty))

if broken:
    print()
    for st, empty in broken:
        print(f"{st.get('name')} is empty for:")
        for c in empty[:40]:
            print(f'  - {c}')
    print('\nA regional picking one of those gets "No questions available".')
sys.exit(1 if broken else 0)
