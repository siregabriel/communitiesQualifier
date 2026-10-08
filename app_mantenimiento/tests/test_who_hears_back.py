"""
The person who did the work hears about it.

Carol Brinegar was given every community while staying the regional for her
own region. Before turning that on, the question was whether she would still
hear back from a community outside her region. Two emails said no:

  - Her own visit report. It went to the leaders of the region that owns the
    community, plus the Settings subscribers. The inspector got a copy only by
    being one of those leaders — so Corporate never had, and Carol would not
    outside North.
  - Replies to something she raised. They went to the region's leaders and
    the community. Whoever raised the item was not on the list.

Fixing the second turned up a third, worse one in the same function: a reply
on an item raised for the leadership side was emailed to the community's own
accounts, unconditionally. The screens hide those items from the Executive
Director by every route; the first comment on one sent its text to them.

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

HEADERS = {'Origin': 'http://localhost', 'Referer': 'http://localhost/'}

EMAILS = {
    'carol.brinegar': 'carol@atlas.com',
    'south.lead': 'south@atlas.com',
    'the.ed': 'ed@atlas.com',
    'corp.person': 'corp@atlas.com',
}


def _accounts(monkeypatch):
    monkeypatch.setattr(A, 'resolve_account_context',
                        lambda u: ({'exists': True, 'email': EMAILS[u]}
                                   if u in EMAILS else {'exists': False}))


# ------------------------------------------------------ replies to a raised item

@pytest.fixture
def replies(monkeypatch):
    sent = []
    _accounts(monkeypatch)
    monkeypatch.setattr(A.email_service, 'enabled', True)
    monkeypatch.setattr(A.email_service, 'send_standard_comment',
                        lambda to, *a, **k: sent.append(list(to)))
    monkeypatch.setattr(A, 'region_leader_emails', lambda c: ['south@atlas.com'])
    monkeypatch.setattr(A, 'community_account_emails',
                        lambda c, exclude_username=None:
                        [] if exclude_username == 'the.ed' else ['ed@atlas.com'])

    def reply(item, author):
        with A.app.test_request_context():
            A.session['user'] = author
            A.notify_raised_item_comment(item, {'author': author, 'text': 'hello'})
        return sent[-1] if sent else None
    return reply


def item(raised_by='carol.brinegar', visibility='community'):
    return {'id': 'x1', 'community': 'Charlie', 'text': 'Lobby carpet',
            'raised_by': raised_by, 'visibility': visibility}


def test_the_raiser_hears_when_the_community_answers(replies):
    """Carol raised it in a community outside her region; the ED replied."""
    to = replies(item(), author='the.ed')
    assert 'carol@atlas.com' in to, f'the person who raised it was not told ({to})'
    assert 'south@atlas.com' in to, 'and the region that owns it still is'


def test_but_not_about_her_own_reply(replies):
    to = replies(item(), author='carol.brinegar')
    assert 'carol@atlas.com' not in to
    assert 'ed@atlas.com' in to, 'the community still hears that she answered'


def test_corporate_too(replies):
    """Corporate owns no region, so a Corporate raiser never heard back at all."""
    to = replies(item(raised_by='corp.person'), author='the.ed')
    assert 'corp@atlas.com' in to


def test_an_item_from_before_raised_by_existed_still_sends(replies):
    to = replies(item(raised_by=''), author='the.ed')
    assert to == ['south@atlas.com'], to


def test_once_each(replies, monkeypatch):
    """The regional who raised it in their own region is also its leader."""
    monkeypatch.setattr(A, 'region_leader_emails', lambda c: ['carol@atlas.com'])
    to = replies(item(), author='the.ed')
    assert to.count('carol@atlas.com') == 1, to


def test_a_reply_on_an_internal_item_never_reaches_the_community(replies):
    """The leak this turned up. Raised for the leadership side means the ED
    does not see it on any screen — and until now, the first reply emailed
    them its text anyway."""
    to = replies(item(visibility='internal'), author='south.lead')
    assert 'ed@atlas.com' not in to, \
        'the community was emailed a reply on an item raised behind them'
    assert 'carol@atlas.com' in to, 'while the side it was raised for still hears'


def test_an_ordinary_item_still_reaches_the_community(replies):
    """The filter is for internal items only."""
    to = replies(item(), author='south.lead')
    assert 'ed@atlas.com' in to


# ------------------------------------------------------- the visit report

def _submit(monkeypatch, inspector):
    """Through the real route, with everything that leaves the machine caught."""
    reports = []
    _accounts(monkeypatch)
    monkeypatch.setattr(A.activity_service, 'log', lambda *a, **k: None)
    monkeypatch.setattr(A.email_service, 'enabled', True)
    monkeypatch.setattr(A.email_service, 'send_inspection_report',
                        lambda sub, to, *a, **k: reports.append(list(to)))
    monkeypatch.setattr(A.email_service, 'send_community_findings', lambda *a, **k: None)
    monkeypatch.setattr(A.email_service, 'send_directed_comments', lambda *a, **k: None)
    monkeypatch.setattr(A, 'community_account_emails', lambda *a, **k: [])
    monkeypatch.setattr(A, 'region_leader_emails', lambda c: ['south@atlas.com'])
    monkeypatch.setattr(A.settings_service, 'recipients_for_inspection', lambda *a, **k: [])

    community = (A.all_communities() or [''])[0]
    region = next((r for r in A.region_service.get_all_regions()
                   if community in (r.get('communities') or [])), None)
    if not community or not region:
        pytest.skip('needs a community inside a region')
    types = [t for t in A.survey_type_service.get_all_survey_types() if t.get('id')]
    if not types:
        pytest.skip('needs a survey type')

    monkeypatch.setattr(A.inspection_service, 'create_submission',
                        lambda *a, **k: {
                            'id': 'hear-back', 'username': inspector,
                            'community': community, 'submitted_at': '2026-10-08T10:00:00',
                            'survey_type_id': types[0]['id'],
                            'responses': [{'question_id': 'q1', 'condition': 'Pass'}],
                            'action_items': []})

    c = A.app.test_client()
    with c.session_transaction() as s:
        s.update(user=inspector, role='regional', community=None,
                 region_id=region['id'], display_name=inspector,
                 survey_type_id=types[0]['id'],
                 survey_type_name=types[0].get('name', ''))
    r = c.post('/api/inspections',
               data={'community': community,
                     'responses': json.dumps([{'question_id': 'q1', 'condition': 'Pass'}])},
               headers=HEADERS)
    assert r.status_code in (200, 201), r.get_data(as_text=True)[:200]
    assert reports, 'no report was sent at all — the test reached nothing'
    return reports[0]


def test_the_inspector_gets_their_own_report(monkeypatch):
    to = _submit(monkeypatch, 'carol.brinegar')
    assert 'carol@atlas.com' in to, f'the person who walked it was not sent it ({to})'
    assert 'south@atlas.com' in to, 'and the owning region still is'


def test_an_inspector_with_no_address_changes_nothing(monkeypatch):
    to = _submit(monkeypatch, 'nobody.on.file')
    assert to == ['south@atlas.com'], to
