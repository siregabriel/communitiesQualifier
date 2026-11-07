"""
A move-in's date can be changed by the people running it, and the day it
was completed is kept for the calendar.

Nov 2026: Betty Smith moved in at The Goldton at Venice and the move-in was
marked complete that day, but the calendar did not show it. The record still
had the target date it was created with (2026-10-12), and nothing let anybody
change it, so the calendar kept it a month back. Gabriel: the date is edited by
whoever runs the move-in, not by him.

So POST /api/moveins/<id>/date follows the same rule as completing or deleting
a move-in: anyone who can open it (the community's ED, its regional, an admin),
nobody else — not the community's team, not another community's ED.

Run locally, never on the server.
"""

import os
import sys

import pytest

_APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

import app as A  # noqa: E402
from services.move_in_service import MoveInService  # noqa: E402

HEADERS = {'Origin': 'http://localhost', 'Referer': 'http://localhost/'}
VENICE = 'The Goldton at Venice, Venice'
NAPLES = 'Naples Place'


@pytest.fixture
def mv(monkeypatch, tmp_path):
    monkeypatch.setattr(A, 'movein_service', MoveInService(str(tmp_path / 'moveins.json')))
    monkeypatch.setattr(A, 'all_communities', lambda: [VENICE, NAPLES])
    monkeypatch.setattr(A.activity_service, 'log', lambda *a, **k: None)
    return A.movein_service.create('Betty Smith', VENICE, '2026-10-12', created_by='laura.blakeman')


def as_(username, role, community=VENICE):
    c = A.app.test_client()
    with c.session_transaction() as s:
        s.update(user=username, role=role, community=community,
                 communities=[community] if community else [], display_name=username)
    return c


def move(client, mv_id, date):
    return client.post(f'/api/moveins/{mv_id}/date', json={'target_date': date}, headers=HEADERS)


def stored_date(mv_id):
    return A.movein_service.get(mv_id)['target_date']


def test_the_communitys_ed_moves_the_date_and_the_calendar_feed_follows(mv):
    ed = as_('laura.blakeman', 'staff')
    r = move(ed, mv['id'], '2026-11-07')
    assert r.status_code == 200, r.get_json()
    assert stored_date(mv['id']) == '2026-11-07'
    rows = ed.get('/api/moveins', headers=HEADERS).get_json()['moveins']
    assert [m['target_date'] for m in rows if m['id'] == mv['id']] == ['2026-11-07']


def test_an_admin_can_move_it_too(mv):
    r = move(as_('admin', 'admin', None), mv['id'], '2026-11-07')
    assert r.status_code == 200
    assert stored_date(mv['id']) == '2026-11-07'


def test_another_communitys_ed_cannot(mv):
    r = move(as_('naples.ed', 'staff', NAPLES), mv['id'], '2026-11-07')
    assert r.status_code == 404
    assert stored_date(mv['id']) == '2026-10-12'


def test_the_communitys_team_cannot(mv):
    r = move(as_('chris.oconnor', A.TEAM_ROLE), mv['id'], '2026-11-07')
    assert r.status_code == 404
    assert stored_date(mv['id']) == '2026-10-12'


@pytest.mark.parametrize('bad', ['', '11/07/2026', '2026-13-01', 'tomorrow'])
def test_only_a_real_date_is_stored(mv, bad):
    r = move(as_('laura.blakeman', 'staff'), mv['id'], bad)
    assert r.status_code == 400
    assert stored_date(mv['id']) == '2026-10-12'


def test_the_move_in_page_offers_the_date_editor():
    html = open(os.path.join(_APP_DIR, 'templates', 'dashboard.html'), encoding='utf-8').read()
    assert 'onclick="editMoveInDate()"' in html
    assert "/date`, {" in html and 'JSON.stringify({ target_date })' in html


def _status(client, mv_id, status):
    return client.post(f'/api/moveins/{mv_id}/status', json={'status': status}, headers=HEADERS)


def test_completing_records_the_day_and_the_calendar_feed_carries_it(mv, monkeypatch):
    """Betty's move-in closed on Nov 7 but the calendar only knew Oct 12. The
    moment it is completed is stored, in UTC with its offset, and listed."""
    monkeypatch.setattr(A.email_service, 'enabled', False)
    monkeypatch.setattr(A, '_movein_blockers', lambda rec: [])  # checklist done
    ed = as_('laura.blakeman', 'staff')
    assert _status(ed, mv['id'], 'completed').status_code == 200
    stamp = A.movein_service.get(mv['id']).get('completed_at') or ''
    assert stamp.endswith('+00:00'), stamp
    rows = ed.get('/api/moveins', headers=HEADERS).get_json()['moveins']
    assert [m['completed_at'] for m in rows] == [stamp]


def test_reopening_clears_it_and_archiving_keeps_it(mv, monkeypatch):
    monkeypatch.setattr(A.email_service, 'enabled', False)
    monkeypatch.setattr(A, '_movein_blockers', lambda rec: [])  # checklist done
    ed = as_('laura.blakeman', 'staff')
    assert _status(ed, mv['id'], 'completed').status_code == 200
    stamp = A.movein_service.get(mv['id'])['completed_at']
    _status(ed, mv['id'], 'archived')
    assert A.movein_service.get(mv['id'])['completed_at'] == stamp
    _status(ed, mv['id'], 'active')
    assert 'completed_at' not in A.movein_service.get(mv['id'])
