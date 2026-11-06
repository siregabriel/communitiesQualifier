"""
Staff positions, run from People instead of from the code.

Gabriel needed to add a Move In Coordinator (Nov 2026) and the position list
was fixed in app.py: the server refused anything else, so a new kind of job
meant a deploy. Admins now add and remove positions in the Add/Edit person
form. A person keeps the position's name as text, so removing one must never
take it away from whoever holds it, nor stop an admin fixing their email.

The form side is test_team_positions.mjs.
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import app as A  # noqa: E402
from services.team_position_service import DEFAULT_POSITIONS, TeamPositionService  # noqa: E402
from services.user_service import UserService  # noqa: E402

HEADERS = {'Origin': 'http://localhost', 'Referer': 'http://localhost/'}
VENICE = 'The Goldton at Venice, Venice'
MIC = 'Move In Coordinator'


@pytest.fixture
def world(monkeypatch, tmp_path):
    monkeypatch.setattr(A, 'user_service', UserService(str(tmp_path / 'users.json')))
    monkeypatch.setattr(A, 'team_position_service',
                        TeamPositionService(str(tmp_path / 'team_positions.json')))
    monkeypatch.setattr(A, 'all_communities', lambda: [VENICE])
    monkeypatch.setattr(A.email_service, 'enabled', False)
    monkeypatch.setattr(A.activity_service, 'log', lambda *a, **k: None)
    monkeypatch.setattr(A.profile_service, 'set_display_name', lambda *a, **k: None)
    monkeypatch.setattr(A.profile_service, 'set_must_change', lambda *a, **k: None)
    monkeypatch.setattr(A.profile_service, 'set_password_hash', lambda *a, **k: None)
    # The Mac's system Python has no scrypt; the hash is not what is tested.
    monkeypatch.setattr(A, 'generate_password_hash', lambda pw: 'hash')
    A.user_service.create('chris.oconnor', 'Chris OConnor', A.TEAM_ROLE, 'x',
                          community=VENICE, communities=[VENICE], email='chris@venice.com',
                          position='Executive Chef')
    return tmp_path


def as_(username, role, community=None):
    c = A.app.test_client()
    with c.session_transaction() as s:
        s.update(user=username, role=role, community=community,
                 communities=[community] if community else [], display_name=username)
    return c


def admin():
    return as_('admin', 'admin')


def add(name, who=None):
    return (who or admin()).post('/api/team-positions', headers=HEADERS, json={'name': name})


def remove(name, who=None):
    return (who or admin()).post('/api/team-positions/remove', headers=HEADERS, json={'name': name})


def offered():
    return admin().get('/api/people', headers=HEADERS).get_json()['team_positions']


def new_staff(position, name='Maria Lopez'):
    return admin().post('/api/people', headers=HEADERS, json={
        'name': name, 'role': 'team', 'community': VENICE, 'position': position})


def edit_chris(position):
    return admin().put('/api/people/chris.oconnor', headers=HEADERS, json={
        'name': 'Chris OConnor', 'email': 'chris@venice.com', 'role': 'team',
        'community': VENICE, 'position': position})


# ------------------------------------------------------------------ the list

def test_it_starts_as_the_six_in_gabriels_order(world):
    """A server that never touched the list offers what it offered before."""
    assert offered() == DEFAULT_POSITIONS
    assert not (world / 'team_positions.json').exists(), 'reading writes nothing'


def test_a_move_in_coordinator_can_be_added_and_then_hired(world):
    """The case that started this."""
    assert new_staff(MIC).status_code == 400, 'not before it is in the list'
    r = add(MIC)
    assert r.status_code == 201, r.get_data(as_text=True)[:200]
    assert r.get_json()['positions'] == DEFAULT_POSITIONS + [MIC]
    assert offered()[-1] == MIC
    r = new_staff(MIC)
    assert r.status_code == 200, r.get_data(as_text=True)[:200]
    assert A.user_service.get(r.get_json()['username'])['position'] == MIC


def test_it_survives_a_restart(world):
    add(MIC)
    again = TeamPositionService(str(world / 'team_positions.json'))
    assert again.active() == DEFAULT_POSITIONS + [MIC]


def test_a_duplicate_or_an_empty_name_is_refused(world):
    assert add('executive  chef').status_code == 400, 'same name, other case and spacing'
    assert add('   ').status_code == 400
    assert add(None).status_code == 400
    assert offered() == DEFAULT_POSITIONS


def test_the_name_is_tidied_not_escaped(world):
    """Stored escaped, an ampersand would show as &amp; once the page escapes it."""
    r = add('  Sales   &  Events <b>Lead</b> ')
    assert r.get_json()['name'] == 'Sales & Events bLead/b'
    assert offered()[-1] == 'Sales & Events bLead/b'


def test_removing_takes_it_out_of_the_form(world):
    r = remove('Wellness Director')
    assert r.status_code == 200
    assert 'Wellness Director' not in offered()
    assert new_staff('Wellness Director').status_code == 400


def test_removing_one_that_is_not_there_says_so(world):
    assert remove('Chief Fun Officer').status_code == 404


def test_the_last_one_stays(world):
    """With none left, Staff could not be added at all."""
    for name in DEFAULT_POSITIONS[:-1]:
        assert remove(name).status_code == 200
    r = remove(DEFAULT_POSITIONS[-1])
    assert r.status_code == 400
    assert offered() == [DEFAULT_POSITIONS[-1]]


def test_adding_a_removed_one_brings_it_back_in_its_place(world):
    remove('Wellness Director')
    assert add('wellness director').get_json()['name'] == 'Wellness Director'
    assert offered() == DEFAULT_POSITIONS


# --------------------------------------------------------- who already holds it

def test_whoever_holds_a_removed_position_keeps_it(world):
    remove('Executive Chef')
    assert A.user_service.get('chris.oconnor')['position'] == 'Executive Chef'
    row = next(p for p in admin().get('/api/people', headers=HEADERS).get_json()['people']
               if p['username'] == 'chris.oconnor')
    assert row['position'] == 'Executive Chef'


def test_and_can_still_be_edited_without_picking_another(world):
    """Fixing Chris's email must not fail because his position left the list."""
    remove('Executive Chef')
    r = edit_chris('Executive Chef')
    assert r.status_code == 200, r.get_data(as_text=True)[:200]
    assert A.user_service.get('chris.oconnor')['position'] == 'Executive Chef'


def test_but_nobody_else_can_be_given_it(world):
    """Holding it is Chris's; it is not a way back into the list for others."""
    remove('Executive Chef')
    assert new_staff('Executive Chef').status_code == 400
    A.user_service.create('ann.boc', 'Ann BOC', A.TEAM_ROLE, 'x', community=VENICE,
                          communities=[VENICE], position='Business Office Director')
    r = admin().put('/api/people/ann.boc', headers=HEADERS, json={
        'name': 'Ann BOC', 'role': 'team', 'community': VENICE, 'position': 'Executive Chef'})
    assert r.status_code == 400


# ------------------------------------------------------------------ who may

@pytest.mark.parametrize('role', ['staff', A.TEAM_ROLE, 'regional', 'corporate'])
def test_only_an_admin_changes_the_list(world, role):
    who = as_('someone', role, VENICE)
    assert add(MIC, who).status_code == 403
    assert remove('Executive Chef', who).status_code == 403
    assert offered() == DEFAULT_POSITIONS
    assert not (world / 'team_positions.json').exists()


def test_a_broken_file_falls_back_to_the_defaults(world):
    path = world / 'team_positions.json'
    path.write_text('{not json')
    assert TeamPositionService(str(path)).active() == DEFAULT_POSITIONS
    path.write_text(json.dumps({'positions': [{'name': MIC}, {'name': 'Gone', 'active': False}, 'junk']}))
    assert TeamPositionService(str(path)).active() == [MIC]
