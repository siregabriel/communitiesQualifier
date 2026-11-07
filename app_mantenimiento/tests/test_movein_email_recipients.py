"""
Who is told about a move-in, and what Settings says about it.

Nov 2026: Betty Smith's move-in at The Goldton at Venice was completed and the
email reached only Laura Blakeman (the ED) and Gabriel (Administrator
notifications). Settings → Email listed every regional with "Move-in emails ·
Reminders and completion summaries", but since Aug 2026 the move-in emails had
gone to the community only — the list was never updated, so it told Gabriel
something untrue for three months.

Gabriel chose both fixes: completions go to the region's leadership too (one
email per resident), reminders stay with the community; and the Settings list
says exactly that, including the EDs, who were missing from it.

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
from services.user_service import UserService  # noqa: E402

HEADERS = {'Origin': 'http://localhost', 'Referer': 'http://localhost/'}
VENICE = 'The Goldton at Venice, Venice'
REGIONS = [
    {'id': 'coastal', 'name': 'Coastal', 'communities': [VENICE],
     'leadership': [{'name': 'Katie Beattie', 'email': 'kbeattie@atlas.test'}]},
    {'id': 'corporate', 'name': 'Corporate', 'kind': A.CORPORATE_KIND, 'communities': [],
     'leadership': [{'name': 'Keely Mcdonald', 'email': 'kmcdonald@atlas.test'}]},
]


@pytest.fixture
def world(monkeypatch, tmp_path):
    monkeypatch.setattr(A, 'user_service', UserService(str(tmp_path / 'users.json')))
    monkeypatch.setattr(A, 'movein_service', MoveInService(str(tmp_path / 'moveins.json')))
    monkeypatch.setattr(A.region_service, 'get_all_regions', lambda: REGIONS)
    monkeypatch.setattr(A.settings_service, 'get_email_settings', lambda: {
        'subscribers': [], 'admin_notify': ['gabriel@atlas.test'],
        'clinical': [], 'ops': [], 'sales': []})
    monkeypatch.setattr(A.activity_service, 'log', lambda *a, **k: None)
    monkeypatch.setattr(A, '_movein_blockers', lambda rec: [])
    A.user_service.create('laura.blakeman', 'Laura Blakeman', 'staff', 'x',
                          community=VENICE, communities=[VENICE], email='laura@venice.test')


def as_(username, role, community=None):
    c = A.app.test_client()
    with c.session_transaction() as s:
        s.update(user=username, role=role, community=community,
                 communities=[community] if community else [], display_name=username)
    return c


def test_a_completion_reaches_the_ed_the_admin_list_and_the_regional(world, monkeypatch):
    sent = []
    monkeypatch.setattr(A.email_service, 'send_movein_completed',
                        lambda recipients, *a, **k: sent.append(list(recipients)))
    mv = A.movein_service.create('Betty Smith', VENICE, '2026-11-07')
    r = as_('laura.blakeman', 'staff', VENICE).post(
        f"/api/moveins/{mv['id']}/status", json={'status': 'completed'}, headers=HEADERS)
    assert r.status_code == 200, r.get_json()
    assert sent == [['laura@venice.test', 'gabriel@atlas.test', 'kbeattie@atlas.test']]


def test_reminders_still_skip_the_regional(world):
    assert 'kbeattie@atlas.test' not in A.movein_recipients(VENICE)


def _summary(world):
    rows = as_('admin', 'admin').get('/api/settings/email/summary', headers=HEADERS).get_json()['people']
    return {p['email']: [i['label'] for i in p['items']] for p in rows}


def test_settings_lists_what_is_really_sent(world):
    who = _summary(world)
    # The regional: completions, not "reminders and completion summaries".
    assert who['kbeattie@atlas.test'] == ['Inspection reports', 'Move-in completions']
    # Corporate owns no community, so it is told of none.
    assert who['kmcdonald@atlas.test'] == ['Inspection reports']
    # The ED, who actually receives every move-in email, is on the list.
    assert who['laura@venice.test'] == ['Move-in emails']
    assert not any('Reminders and completion summaries' in str(v) for v in who.values())


def test_a_role_row_says_which_account_to_open(world):
    """Gabriel saw a lock on most rows, hovered it, got a "?" cursor and no
    explanation (Nov 2026). The lock became "Edit in People", which needs the
    account behind the row: the regional's and the ED's username. A row that
    only comes from this page's lists has none to open."""
    rows = as_('admin', 'admin').get('/api/settings/email/summary', headers=HEADERS).get_json()['people']
    by = {p['email']: p for p in rows}
    assert by['kbeattie@atlas.test']['username'] == 'katie.beattie'
    assert by['kmcdonald@atlas.test']['username'] == 'keely.mcdonald'
    assert by['laura@venice.test']['username'] == 'laura.blakeman'
    assert 'username' not in by['gabriel@atlas.test']
    assert by['gabriel@atlas.test']['removable'] and not by['laura@venice.test']['removable']
