"""
A regional who can visit every community without leaving their region.

Carol Brinegar asked for access to all communities. The obvious move was to
put her in Corporate, which reaches everything — and which would have quietly
cost her the other half of being a regional. Visit reports, raised items and
the 30-day reminder go to the leaders of the region that owns a community.
Corporate owns none. She would have seen every building and stopped hearing
about her own, and nothing would have said so.

Putting her in both lists was no better: the login is built by walking the
regions, so whichever one came last in the file would have won.

So reach and region are now separate. The region still decides who is told;
a switch on the person decides how far they can go.

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

CAROL = 'carol.brinegar'
PEER = 'other.regional'


@pytest.fixture
def world(monkeypatch, tmp_path):
    """Two regions and Corporate, in files of their own."""
    regions = tmp_path / 'regions.json'
    regions.write_text(json.dumps({'regions': [
        {'id': 'north', 'name': 'North', 'communities': ['Alpha', 'Bravo'],
         'leadership': [
             {'name': 'Carol Brinegar', 'role': 'RDO', 'username': CAROL,
              'email': 'carol@example.com'},
             {'name': 'Other Regional', 'role': 'RDO', 'username': PEER,
              'email': 'other@example.com'},
         ]},
        {'id': 'south', 'name': 'South', 'communities': ['Charlie'],
         'leadership': [{'name': 'Southern Lead', 'role': 'RDO',
                         'username': 'southern.lead', 'email': 'south@example.com'}]},
        {'id': A.CORPORATE_ID, 'name': 'Corporate', 'kind': A.CORPORATE_KIND,
         'communities': [],
         'leadership': [{'name': 'Corp Person', 'role': 'VP',
                         'username': 'corp.person', 'email': 'corp@example.com'}]},
    ]}), encoding='utf-8')
    monkeypatch.setattr(A, 'region_service', RegionService(str(regions)))
    monkeypatch.setattr(A, 'profile_service', ProfileService(str(tmp_path / 'profiles.json')))
    monkeypatch.setattr(A, 'REGIONS_FILE', str(regions))
    A._regional_accounts_cache['accounts'] = None
    yield
    A._regional_accounts_cache['accounts'] = None


def signed_in(username, role='regional', region_id='north'):
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


# ---------------------------------------------------------------- the reach

def test_a_regional_sees_their_region_by_default(world):
    assert communities_of(signed_in(CAROL)) == ['Alpha', 'Bravo']


def test_with_the_switch_she_sees_every_community(world):
    A.profile_service.set_all_communities(CAROL, True)
    assert sorted(communities_of(signed_in(CAROL))) == ['Alpha', 'Bravo', 'Charlie']


def test_and_can_open_one_outside_her_region(world):
    """The list is one thing; the per-community check is what guards a
    visit, a panel, a raised item. Both go through regional_communities()."""
    A.profile_service.set_all_communities(CAROL, True)
    with A.app.test_request_context():
        A.session.update(user=CAROL, role='regional', region_id='north')
        assert A._can_see_community('Charlie')
        assert 'Charlie' in A.visible_communities()


def test_it_is_hers_not_her_regions(world):
    """The switch is on a person. The other regional in North keeps North."""
    A.profile_service.set_all_communities(CAROL, True)
    assert communities_of(signed_in(PEER)) == ['Alpha', 'Bravo']
    with A.app.test_request_context():
        A.session.update(user=PEER, role='regional', region_id='north')
        assert not A._can_see_community('Charlie')


def test_it_takes_effect_without_signing_in_again(world):
    """Read on every request, not copied into the session at login — so
    turning it on or off is felt on her next click, and turning it off really
    does take it away."""
    c = signed_in(CAROL)
    assert 'Charlie' not in communities_of(c)
    A.profile_service.set_all_communities(CAROL, True)
    assert 'Charlie' in communities_of(c)
    A.profile_service.set_all_communities(CAROL, False)
    assert 'Charlie' not in communities_of(c)


# ----------------------------------------------- what she does not lose

def test_she_is_still_told_about_her_own_region(world):
    """The reason this is not Corporate. Reports, raised items and reminders
    for a community go to its region's leaders."""
    A.profile_service.set_all_communities(CAROL, True)
    assert 'carol@example.com' in A.region_leader_emails('Alpha')
    assert 'carol@example.com' in A.region_leader_emails('Bravo')


def test_and_is_not_added_to_every_other_regions_mail(world):
    """Reach is not responsibility. South's reports still go to South."""
    A.profile_service.set_all_communities(CAROL, True)
    assert A.region_leader_emails('Charlie') == ['south@example.com']


def test_editing_her_keeps_the_switch(world):
    """update_leader rebuilds the leader record from scratch. A flag stored
    on that record would have fallen off the first time somebody fixed her
    title — which is why it lives in her profile instead."""
    A.profile_service.set_all_communities(CAROL, True)
    r = as_admin().put(f'/api/people/{CAROL}', headers=HEADERS, json={
        'name': 'Carol Brinegar', 'email': 'carol@example.com',
        'title': 'Senior RDO', 'role': 'regional', 'region_id': 'north'})
    assert r.status_code == 200, r.get_data(as_text=True)[:200]
    assert A.region_service.find_leader_by_username(CAROL)[2]['role'] == 'Senior RDO'
    assert sorted(communities_of(signed_in(CAROL))) == ['Alpha', 'Bravo', 'Charlie']


def test_moving_her_region_keeps_it_too(world):
    """A move removes the leader and adds a new record in the other region."""
    A.profile_service.set_all_communities(CAROL, True)
    r = as_admin().put(f'/api/people/{CAROL}', headers=HEADERS, json={
        'name': 'Carol Brinegar', 'email': 'carol@example.com',
        'role': 'regional', 'region_id': 'south'})
    assert r.status_code == 200, r.get_data(as_text=True)[:200]
    assert 'carol@example.com' in A.region_leader_emails('Charlie')
    c = signed_in(CAROL, region_id='south')
    assert sorted(communities_of(c)) == ['Alpha', 'Bravo', 'Charlie']


def test_making_her_an_executive_director_drops_it(world, monkeypatch):
    """Left set, it would come back by itself if she were ever made a
    regional again — a grant nobody remembers making."""
    monkeypatch.setattr(A.user_service, 'ensure', lambda *a, **k: True)
    monkeypatch.setattr(A.user_service, 'exists', lambda *a, **k: False)
    A.profile_service.set_all_communities(CAROL, True)
    r = as_admin().put(f'/api/people/{CAROL}', headers=HEADERS, json={
        'name': 'Carol Brinegar', 'email': 'carol@example.com',
        'role': 'staff', 'community': 'Alpha'})
    assert r.status_code == 200, r.get_data(as_text=True)[:200]
    assert A.profile_service.get_all_communities(CAROL) is False


# ---------------------------------------------------------- the switch

def test_an_admin_turns_it_on(world):
    r = as_admin().post(f'/api/people/{CAROL}/all-communities',
                        headers=HEADERS, json={'grant': True})
    assert r.status_code == 200, r.get_data(as_text=True)[:200]
    assert A.profile_service.get_all_communities(CAROL) is True
    assert 'North' in r.get_json()['message'], 'the message does not say she keeps her region'


def test_and_off(world):
    A.profile_service.set_all_communities(CAROL, True)
    r = as_admin().post(f'/api/people/{CAROL}/all-communities',
                        headers=HEADERS, json={'grant': False})
    assert r.status_code == 200
    assert A.profile_service.get_all_communities(CAROL) is False


def test_nobody_grants_it_to_themselves(world):
    r = signed_in(CAROL).post(f'/api/people/{CAROL}/all-communities',
                              headers=HEADERS, json={'grant': True})
    assert r.status_code == 403
    assert A.profile_service.get_all_communities(CAROL) is False


def test_corporate_is_told_it_already_has_it(world):
    r = as_admin().post('/api/people/corp.person/all-communities',
                        headers=HEADERS, json={'grant': True})
    assert r.status_code == 400
    assert 'already' in r.get_json()['message']


def test_an_executive_director_cannot_be_given_it(world):
    """An ED's scope is a list of sites picked one by one. A company-wide
    switch there would be a different decision made by accident."""
    r = as_admin().post('/api/people/some.ed/all-communities',
                        headers=HEADERS, json={'grant': True})
    assert r.status_code == 400
    assert A.profile_service.get_all_communities('some.ed') is False


# ------------------------------------------------------- what it says

def test_people_says_it(world):
    A.profile_service.set_all_communities(CAROL, True)
    people = as_admin().get('/api/people', headers=HEADERS).get_json()['people']
    carol = next(p for p in people if p['username'] == CAROL)
    peer = next(p for p in people if p['username'] == PEER)
    assert carol['all_communities'] is True
    assert carol['scope'] == 'All communities · North'
    assert peer['all_communities'] is False
    assert peer['scope'] == 'North'


def test_her_profile_says_it(world):
    """Her profile used to be the place that lied about scope (Michael
    Hamilton's 'All communities'). It names both halves now."""
    A.profile_service.set_all_communities(CAROL, True)
    r = signed_in(CAROL).get('/api/profile', headers=HEADERS)
    assert r.status_code == 200, r.get_data(as_text=True)[:200]
    assert r.get_json()['community'] == 'All communities · North region'
    r = signed_in(PEER).get('/api/profile', headers=HEADERS)
    assert r.get_json()['community'] == 'North region'
