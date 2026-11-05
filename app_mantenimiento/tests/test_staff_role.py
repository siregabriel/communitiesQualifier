"""
Staff: a member of one community's team.

Laura Blakeman, Executive Director of The Goldton at Venice, sent her team:
Chris (maintenance), Ann (business office), Cait (chef), Kelly (sales), Dianne
(wellness), Meredith (lifestyles). They need to see what is open at Venice and
be able to answer it — and raise what they find.

The first attempt was an "Area Manager" option in the Add person form that
stored the role as 'staff'. In this application 'staff' means Executive
Director, so every one of them would have received the ED's findings email and
both reminders, could close items, and could be put on other communities. Six
copies of every reminder to every community is how a sender gets filtered.

So Staff is its own role, stored as 'team':
  * one community, never "Also covers" (an ED can stand in for a neighbour;
    a chef cannot);
  * sees the community's items, never the internal ones;
  * comments on them and raises issues; never closes, never visits;
  * no move-ins (they name residents);
  * none of the ED's email — only the welcome, and replies on threads they
    wrote on.

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
from services.inspection_service import InspectionService  # noqa: E402
from services.move_in_service import MoveInService  # noqa: E402
from services.raised_item_service import RaisedItemService  # noqa: E402
from services.user_service import UserService  # noqa: E402

HEADERS = {'Origin': 'http://localhost', 'Referer': 'http://localhost/'}
VENICE = 'The Goldton at Venice, Venice'
NAPLES = 'Naples Place'


@pytest.fixture
def world(monkeypatch, tmp_path):
    monkeypatch.setattr(A, 'user_service', UserService(str(tmp_path / 'users.json')))
    monkeypatch.setattr(A, 'raised_item_service', RaisedItemService(str(tmp_path / 'raised.json')))
    monkeypatch.setattr(A, 'inspection_service',
                        InspectionService(str(tmp_path / 'inspections.json'), str(tmp_path / 'up')))
    monkeypatch.setattr(A, 'movein_service', MoveInService(str(tmp_path / 'moveins.json')))
    monkeypatch.setattr(A, 'all_communities', lambda: [VENICE, NAPLES])
    monkeypatch.setattr(A.email_service, 'enabled', False)
    monkeypatch.setattr(A.activity_service, 'log', lambda *a, **k: None)
    monkeypatch.setattr(A.profile_service, 'set_display_name', lambda *a, **k: None)
    monkeypatch.setattr(A.profile_service, 'set_must_change', lambda *a, **k: None)
    A.user_service.create('laura.blakeman', 'Laura Blakeman', 'staff', 'x',
                          community=VENICE, communities=[VENICE], email='laura@venice.com')
    A.user_service.create('chris.oconnor', 'Chris OConnor', A.TEAM_ROLE, 'x',
                          community=VENICE, communities=[VENICE], email='chris@venice.com')


def as_(username, role, community=VENICE):
    c = A.app.test_client()
    with c.session_transaction() as s:
        s.update(user=username, role=role, community=community,
                 communities=[community] if community else [], display_name=username)
    return c


def admin():
    return as_('admin', 'admin', None)


def chris():
    return as_('chris.oconnor', A.TEAM_ROLE)


def laura():
    return as_('laura.blakeman', 'staff')


def raise_item(visibility='community', community=VENICE):
    cat = A.raised_category_service.active()[0]['id']
    return A.raised_item_service.create(community, 'Lobby light out', 'regional.x', 'Regional',
                                        category=cat, visibility=visibility)


# ---------------------------------------------------------------- creating one

def test_greg_adds_staff_from_people(world):
    r = admin().post('/api/people', headers=HEADERS, json={
        'name': 'Cait Chef', 'email': 'cait@thegoldtonatvenice.com', 'role': 'team',
        'community': VENICE})
    assert r.status_code == 200, r.get_data(as_text=True)[:200]
    rec = A.user_service.get(r.get_json()['username'])
    assert rec['role'] == 'team', 'stored as an Executive Director again'
    assert rec['community'] == VENICE and rec['communities'] == [VENICE]


def test_one_community_whatever_the_form_sends(world):
    """'Also covers' is an Executive Director's. A chef belongs to one kitchen."""
    r = admin().post('/api/people', headers=HEADERS, json={
        'name': 'Kelly Sales', 'role': 'team', 'community': VENICE, 'communities': [VENICE, NAPLES]})
    rec = A.user_service.get(r.get_json()['username'])
    assert rec['communities'] == [VENICE], rec['communities']


def test_a_community_is_required(world):
    r = admin().post('/api/people', headers=HEADERS, json={'name': 'Nobody', 'role': 'team'})
    assert r.status_code == 400


def test_an_unknown_community_is_refused(world):
    r = admin().post('/api/people', headers=HEADERS, json={
        'name': 'Typo', 'role': 'team', 'community': 'The Goldton at Venise'})
    assert r.status_code == 400


def test_only_an_admin_adds_them(world):
    r = laura().post('/api/people', headers=HEADERS, json={
        'name': 'Ann BOC', 'role': 'team', 'community': VENICE})
    assert r.status_code == 403


def test_the_welcome_says_staff_and_nothing_else_is_sent(world, monkeypatch):
    sent = {'welcome': [], 'handover': []}
    monkeypatch.setattr(A.email_service, 'enabled', True)
    monkeypatch.setattr(A.email_service, 'send_welcome',
                        lambda to, name, user, pw, label: sent['welcome'].append(label) or (True, ''))
    monkeypatch.setattr(A.email_service, 'send_new_user_alert', lambda *a, **k: None)
    monkeypatch.setattr(A, 'send_community_handover', lambda *a, **k: sent['handover'].append(a))
    admin().post('/api/people', headers=HEADERS, json={
        'name': 'Dianne Wellness', 'email': 'dianne@venice.com', 'role': 'team', 'community': VENICE})
    assert sent['welcome'] == [f'Staff · {VENICE}']
    assert sent['handover'] == [], 'Staff were sent the ED\'s backlog of findings'


def test_editing_into_staff_drops_the_extra_communities(world):
    A.user_service.create('meredith', 'Meredith', 'staff', 'x', community=VENICE,
                          communities=[VENICE, NAPLES])
    r = admin().put('/api/people/meredith', headers=HEADERS, json={
        'name': 'Meredith', 'role': 'team', 'community': VENICE, 'communities': [VENICE, NAPLES]})
    assert r.status_code == 200, r.get_data(as_text=True)[:200]
    rec = A.user_service.get('meredith')
    assert rec['role'] == 'team' and rec['communities'] == [VENICE]


# ------------------------------------------------------------------ what they see

def test_they_see_their_community_only(world):
    d = chris().get('/api/communities', headers=HEADERS).get_json()
    assert d['communities'] == [VENICE]


def test_they_see_its_open_items_but_never_the_internal_ones(world):
    open_item = raise_item()
    internal = raise_item('internal')
    elsewhere = raise_item(community=NAPLES)
    ids = {i['id'] for i in chris().get('/api/raised-items', headers=HEADERS).get_json()['items']}
    assert open_item['id'] in ids
    assert internal['id'] not in ids, 'an item raised behind the community reached its staff'
    assert elsewhere['id'] not in ids


def test_no_move_ins(world):
    """They name residents."""
    A.movein_service.create('A Resident', VENICE, '2026-12-01', created_by='laura.blakeman')
    r = chris().get('/api/moveins', headers=HEADERS)
    rows = (r.get_json() or {}).get('moveins') or (r.get_json() or {}).get('items') or []
    assert r.status_code in (200, 403) and rows == []
    ed_rows = laura().get('/api/moveins', headers=HEADERS).get_json()
    assert (ed_rows.get('moveins') or ed_rows.get('items')), \
        'the fixture never contained a move-in, so the line above proved nothing'


def test_what_the_page_is_told(world):
    d = chris().get('/api/user-info', headers=HEADERS).get_json()
    assert d['can_run_visits'] is False
    assert d['can_verify_fixes'] is False
    assert d['can_close_raised'] is False
    assert laura().get('/api/user-info', headers=HEADERS).get_json()['can_close_raised'] is True


# ------------------------------------------------------------------ what they do

def test_they_raise_an_issue(world):
    cat = A.raised_category_service.active()[0]['id']
    r = chris().post('/api/raised-items', headers=HEADERS,
                     data={'text': 'Walk-in cooler is warm', 'category': cat})
    assert r.status_code in (200, 201), r.get_data(as_text=True)[:200]
    item = r.get_json()['item']
    assert item['community'] == VENICE


def test_but_never_an_internal_one(world):
    cat = A.raised_category_service.active()[0]['id']
    r = chris().post('/api/raised-items', headers=HEADERS,
                     data={'text': 'x', 'category': cat, 'visibility': 'internal'})
    assert r.get_json()['item']['visibility'] == 'community'


def test_they_comment_but_do_not_close(world):
    item = raise_item()
    c = chris()
    r = c.post(f"/api/raised-items/{item['id']}/comment", headers=HEADERS, data={'text': 'Fixed, new bulb'})
    assert r.status_code in (200, 201), r.get_data(as_text=True)[:200]
    r = c.post(f"/api/raised-items/{item['id']}/resolve", headers=HEADERS, json={'resolved': True})
    assert r.status_code == 403
    assert 'Executive Director' in r.get_json()['message']
    assert A.raised_item_service.get(item['id'])['resolved'] is False
    r = laura().post(f"/api/raised-items/{item['id']}/resolve", headers=HEADERS, json={'resolved': True})
    assert r.status_code == 200, 'the ED could no longer close it either'


def test_they_cannot_run_a_visit(world):
    r = chris().get('/reporte')
    assert r.status_code == 302


# ------------------------------------------------------------------- the email

def test_none_of_the_eds_email(world):
    """Findings, reminders and handovers all go to community_account_emails."""
    assert A.community_account_emails(VENICE) == ['laura@venice.com']


def test_their_side_of_a_thread_is_the_communitys(world):
    """Reminders read 'leadership spoke last' from this; Chris saying 'done'
    is the community's answer, not leadership's."""
    assert 'chris.oconnor' in A._community_account_usernames()


def test_a_reply_reaches_staff_who_wrote_on_the_thread(world, monkeypatch):
    sent = []
    monkeypatch.setattr(A.email_service, 'enabled', True)
    monkeypatch.setattr(A.email_service, 'send_standard_comment',
                        lambda to, *a, **k: sent.append(list(to)))
    monkeypatch.setattr(A, 'region_leader_emails', lambda c: ['regional@atlas.com'])
    item = raise_item()
    item['comments'] = [{'username': 'chris.oconnor', 'text': 'On it'}]
    with A.app.test_request_context():
        A.session['user'] = 'regional.x'
        A.notify_raised_item_comment(item, {'author': 'Regional', 'text': 'Thanks'})
    assert 'chris@venice.com' in sent[-1], sent


def test_but_not_on_an_internal_item(world, monkeypatch):
    sent = []
    monkeypatch.setattr(A.email_service, 'enabled', True)
    monkeypatch.setattr(A.email_service, 'send_standard_comment',
                        lambda to, *a, **k: sent.append(list(to)))
    monkeypatch.setattr(A, 'region_leader_emails', lambda c: ['regional@atlas.com'])
    item = raise_item('internal')
    item['comments'] = [{'username': 'chris.oconnor', 'text': 'old'}]
    with A.app.test_request_context():
        A.session['user'] = 'regional.x'
        A.notify_raised_item_comment(item, {'author': 'Regional', 'text': 'Thanks'})
    assert 'chris@venice.com' not in sent[-1]


def test_a_reply_on_a_finding_reaches_them_too(world, monkeypatch):
    sent = []
    monkeypatch.setattr(A.email_service, 'enabled', True)
    monkeypatch.setattr(A.email_service, 'send_standard_comment',
                        lambda to, *a, **k: sent.append(list(to)))
    monkeypatch.setattr(A, 'region_leader_emails', lambda c: ['regional@atlas.com'])
    sub = {'community': VENICE, 'username': 'regional.x', 'responses': [
        {'question_id': 'q1', 'question_text': 'Kitchen clean', 'condition': 'Fail',
         'comments': [{'username': 'chris.oconnor', 'text': 'Cleaned'}]}]}
    with A.app.test_request_context():
        A.session['user'] = 'regional.x'
        A.notify_comment(sub, 'q1', {'author': 'Regional', 'text': 'Looks good'})
    assert 'chris@venice.com' in sent[-1], sent


# ------------------------------------------------------------------ the form

def test_the_area_manager_option_is_gone():
    """It created Executive Directors."""
    with open(os.path.join(_APP_DIR, 'templates', 'dashboard.html'), encoding='utf-8') as f:
        html = f.read()
    assert 'Area Manager' not in html
    assert '<option value="team">Staff — one community</option>' in html
