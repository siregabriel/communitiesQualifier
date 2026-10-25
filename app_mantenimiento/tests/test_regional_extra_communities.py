"""
An administrator can let a regional visit named communities outside their region.

The Goldton at Venice moved to another region. Lauren Hamilton, the regional
for the region it left, still needed to visit it — and once it moved, the
visit form no longer offered it to her. "Can visit every community" would have
fixed that by giving her all thirty-nine. This gives her the one.

What has to hold: the grant reaches every check that decides scope (it goes
through regional_communities(), like the region itself); it is the admin's to
give, not the regional's; it changes nobody's email — the region that owns a
community is still the one told about it; and it follows a rename, because it
is stored by community name.

Run locally, never on the server.
"""

import json
import os
import sys

import pytest

_APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

import app as A  # noqa: E402
from services.profile_service import ProfileService  # noqa: E402
from services.region_service import RegionService  # noqa: E402

HEADERS = {'Origin': 'http://localhost', 'Referer': 'http://localhost/'}

LAUREN = 'lauren.hamilton'
PEER = 'other.regional'
VENICE = 'The Goldton at Venice, Venice'


@pytest.fixture
def world(monkeypatch, tmp_path):
    regions = tmp_path / 'regions.json'
    regions.write_text(json.dumps({'regions': [
        {'id': 'gulf', 'name': 'Gulf', 'communities': ['Tampa Place', 'Sarasota Place'],
         'leadership': [
             {'name': 'Lauren Hamilton', 'role': 'RDO', 'username': LAUREN,
              'email': 'lauren@example.com'},
             {'name': 'Other Regional', 'role': 'RDO', 'username': PEER,
              'email': 'other@example.com'},
         ]},
        {'id': 'south', 'name': 'South', 'communities': [VENICE, 'Naples Place'],
         'leadership': [{'name': 'South Lead', 'role': 'RDO', 'username': 'south.lead',
                         'email': 'south@example.com'}]},
        {'id': A.CORPORATE_ID, 'name': 'Corporate', 'kind': A.CORPORATE_KIND,
         'communities': [],
         'leadership': [{'name': 'Corp Person', 'role': 'VP', 'username': 'corp.person',
                         'email': 'corp@example.com'}]},
    ]}), encoding='utf-8')
    monkeypatch.setattr(A, 'region_service', RegionService(str(regions)))
    monkeypatch.setattr(A, 'REGIONS_FILE', str(regions))
    monkeypatch.setattr(A, 'profile_service', ProfileService(str(tmp_path / 'profiles.json')))
    A._regional_accounts_cache['accounts'] = None
    logged = []
    monkeypatch.setattr(A.activity_service, 'log',
                        lambda user, kind, detail='', meta=None: logged.append(
                            {'user': user, 'kind': kind, 'detail': detail, 'meta': meta or {}}))
    yield logged
    A._regional_accounts_cache['accounts'] = None


def as_user(username, region_id='gulf', role='regional'):
    c = A.app.test_client()
    with c.session_transaction() as s:
        s.update(user=username, role=role, region_id=region_id, display_name=username)
    return c


def as_admin():
    c = A.app.test_client()
    with c.session_transaction() as s:
        s.update(user='admin', role='admin', display_name='Administrator')
    return c


def communities_of(client):
    r = client.get('/api/communities', headers=HEADERS)
    assert r.status_code == 200, r.get_data(as_text=True)[:200]
    return r.get_json()['communities']


def grant(communities, who=LAUREN):
    return as_admin().post(f'/api/people/{who}/extra-communities',
                           headers=HEADERS, json={'communities': communities})


# ------------------------------------------------------------------ the reach

def test_without_it_lauren_cannot_reach_venice(world):
    assert VENICE not in communities_of(as_user(LAUREN))


def test_with_it_she_can(world):
    r = grant([VENICE])
    assert r.status_code == 200, r.get_data(as_text=True)[:200]
    assert communities_of(as_user(LAUREN)) == ['Tampa Place', 'Sarasota Place', VENICE]


def test_and_only_that_one(world):
    """The point of this over "every community"."""
    grant([VENICE])
    assert 'Naples Place' not in communities_of(as_user(LAUREN))


def test_every_check_agrees(world):
    """The visit route, the panel and raised items all ask _can_see_community;
    the lists ask visible_communities. Both go through regional_communities."""
    grant([VENICE])
    with A.app.test_request_context():
        A.session.update(user=LAUREN, role='regional', region_id='gulf')
        assert A._can_see_community(VENICE)
        assert VENICE in A.visible_communities()
        assert not A._can_see_community('Naples Place')


def test_it_is_hers_not_her_regions(world):
    grant([VENICE])
    assert VENICE not in communities_of(as_user(PEER))


def test_taking_it_away_takes_it_away(world):
    grant([VENICE])
    c = as_user(LAUREN)
    assert VENICE in communities_of(c)
    grant([])
    assert VENICE not in communities_of(c), 'still reachable after it was removed'


def test_a_community_removed_from_the_structure_is_not_reachable_through_it(world):
    grant([VENICE])
    A.region_service.remove_community(VENICE)
    assert VENICE not in communities_of(as_user(LAUREN))


# ------------------------------------------------------- what it does not change

def test_venice_is_still_reported_to_its_own_region(world):
    """Reach is not responsibility."""
    grant([VENICE])
    assert A.region_leader_emails(VENICE) == ['south@example.com']


# ------------------------------------------------------------------ the rename

def test_a_rename_carries_the_grant(world, monkeypatch):
    """Stored by name, so it has to join the rename walk — otherwise Lauren
    loses Venice the day somebody fixes its spelling, and nothing says why."""
    grant([VENICE])
    for svc in ('question_manager', 'inspection_service', 'movein_service',
                'raised_item_service', 'place_service'):
        monkeypatch.setattr(getattr(A, svc), 'rename_community' if svc != 'place_service' else 'rename',
                            lambda *a, **k: None)
    monkeypatch.setattr(A.community_cover_service, 'rename', lambda *a, **k: None)
    r = as_admin().post('/api/regions/rename-community', headers=HEADERS,
                        json={'old_name': VENICE, 'new_name': 'The Goldton at Venice'})
    assert r.status_code == 200, r.get_data(as_text=True)[:300]
    assert A.profile_service.get_extra_communities(LAUREN) == ['The Goldton at Venice']
    assert 'The Goldton at Venice' in communities_of(as_user(LAUREN))


# --------------------------------------------------------------- the switch

def test_only_an_admin_gives_it(world):
    r = as_user(LAUREN).post(f'/api/people/{LAUREN}/extra-communities',
                             headers=HEADERS, json={'communities': [VENICE]})
    assert r.status_code == 403
    assert A.profile_service.get_extra_communities(LAUREN) == []


def test_unknown_names_are_refused(world):
    r = grant(['Somewhere Made Up'])
    assert r.status_code == 400
    assert A.profile_service.get_extra_communities(LAUREN) == []


def test_her_own_region_is_not_stored(world):
    """She reaches those anyway. Stored, they would become a grant left
    behind the day one of them moves away."""
    grant([VENICE, 'Tampa Place'])
    assert A.profile_service.get_extra_communities(LAUREN) == [VENICE]


def test_corporate_and_eds_are_refused(world):
    assert grant([VENICE], who='corp.person').status_code == 400
    assert grant([VENICE], who='some.ed').status_code == 400


def test_the_change_is_in_the_feed(world):
    grant([VENICE])
    entry = next(e for e in world if e['kind'] == 'extra_communities_changed')
    assert entry['meta']['added'] == [VENICE]
    assert 'Lauren Hamilton' in entry['detail']


def test_saving_the_same_list_again_logs_nothing(world):
    grant([VENICE])
    world.clear()
    grant([VENICE])
    assert not any(e['kind'] == 'extra_communities_changed' for e in world)


# ------------------------------------------------------------- what it says

def test_people_shows_it(world):
    grant([VENICE])
    d = as_admin().get('/api/people', headers=HEADERS).get_json()
    lauren = next(p for p in d['people'] if p['username'] == LAUREN)
    assert lauren['extra_communities'] == [VENICE]
    assert lauren['scope'] == f'Gulf + {VENICE}'
    gulf = next(r for r in d['regions'] if r['id'] == 'gulf')
    assert gulf['communities'] == ['Tampa Place', 'Sarasota Place'], \
        'the form needs each region\'s communities to offer only the others'


def test_her_profile_says_it(world):
    grant([VENICE])
    r = as_user(LAUREN).get('/api/profile', headers=HEADERS)
    assert r.get_json()['community'] == 'Gulf region + 1 more'
