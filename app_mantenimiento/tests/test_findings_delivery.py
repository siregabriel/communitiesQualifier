"""
A visit whose community never got its copy says so.

Two emails go out when a visit is submitted: the leadership report, and a
narrower one to the community itself — what was found here and what to do
about it. The second was conditional on there being an address to send to,
and said nothing when there was not.

So a community that has silently missed every report since its first visit
looked exactly like one that reads them. The way it surfaced was Greg
noticing an Executive Director was not on a thread and asking whether
somebody had forgotten to click something. That is not a way of finding
things out.

The note distinguishes two causes on purpose, because they have different
answers: nobody holds an account here yet (create one) versus the account
has no address on it (open it and add one).

Run locally, never on the server.
"""

import os
import sys

import pytest

_APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

import app as A  # noqa: E402

VISIT = {'id': 's-smoke', 'username': 'jennifer.oscar',
         'community': 'The Goldton At Lake Nona'}


@pytest.fixture
def logged(monkeypatch):
    entries = []
    monkeypatch.setattr(A.activity_service, 'log',
                        lambda user, kind, detail='', meta=None: entries.append(
                            {'user': user, 'kind': kind, 'detail': detail, 'meta': meta or {}}))
    return entries


# ------------------------------------------------- the two causes, apart

def test_no_account_for_the_community_yet(logged, monkeypatch):
    monkeypatch.setattr(A, 'community_has_accounts', lambda c: False)
    A.note_findings_undelivered(VISIT)

    assert len(logged) == 1
    e = logged[0]
    assert e['kind'] == 'findings_undelivered'
    assert e['meta']['reason'].startswith(VISIT['community']), \
        'the detail line truncates, so the community has to lead'
    assert 'no account here yet' in e['meta']['reason']
    assert e['meta']['community'] == VISIT['community']


def test_an_account_that_has_no_address_on_it(logged, monkeypatch):
    """A different problem with a different answer, so it says which."""
    monkeypatch.setattr(A, 'community_has_accounts', lambda c: True)
    A.note_findings_undelivered(VISIT)

    assert 'no email address' in logged[0]['meta']['reason']
    assert 'no account here yet' not in logged[0]['meta']['reason']


def test_it_names_the_community_in_words_too(logged, monkeypatch):
    """The feed shows the sentence; the meta is for the link."""
    monkeypatch.setattr(A, 'community_has_accounts', lambda c: False)
    A.note_findings_undelivered(VISIT)
    assert VISIT['community'] in logged[0]['detail']
    assert logged[0]['meta']['submission_id'] == 's-smoke'


def test_it_is_filed_under_the_visit_it_belongs_to(logged, monkeypatch):
    """Whoever ran the visit, because that is where somebody would look —
    not because it is their fault, which is why the wording says what to do
    rather than what went wrong."""
    monkeypatch.setattr(A, 'community_has_accounts', lambda c: False)
    A.note_findings_undelivered(VISIT)
    assert logged[0]['user'] == 'jennifer.oscar'
    assert 'forgot' not in logged[0]['detail'].lower()
    assert 'failed' not in logged[0]['detail'].lower()


# --------------------------------------------- telling the causes apart

def test_community_has_accounts_reads_the_roster(monkeypatch):
    monkeypatch.setattr(A.user_service, 'get_all', lambda: [
        {'username': 'a', 'role': 'staff', 'community': 'Lake Nona'},
        {'username': 'b', 'role': 'regional', 'community': None},
    ])
    monkeypatch.setattr(A, 'account_communities',
                        lambda u: [u['community']] if u.get('community') else [])

    assert A.community_has_accounts('Lake Nona') is True
    assert A.community_has_accounts('Somewhere Else') is False
    assert A.community_has_accounts('') is False


def test_a_regional_covering_it_does_not_count(monkeypatch):
    """The community's own account is the one that gets this email.

    A regional already had the leadership report; counting them here would
    report the problem as solved while the community still hears nothing.
    """
    monkeypatch.setattr(A.user_service, 'get_all', lambda: [
        {'username': 'lauren', 'role': 'regional', 'community': 'Lake Nona'},
    ])
    monkeypatch.setattr(A, 'account_communities', lambda u: ['Lake Nona'])
    assert A.community_has_accounts('Lake Nona') is False


# ----------------------------------------------- the branch that was mute

def test_the_send_no_longer_passes_in_silence():
    """Counted against the route, so the condition cannot go back to having
    no else without this saying so."""
    with open(os.path.join(_APP_DIR, 'app.py'), encoding='utf-8') as f:
        src = f.read()
    i = src.index('ed_emails = community_account_emails(community)')
    window = src[i:i + 300]
    assert 'note_findings_undelivered' in window, \
        'the community email can still go nowhere without a word'
    assert 'if not ed_emails:' in window


def test_the_feed_knows_how_to_draw_it():
    with open(os.path.join(_APP_DIR, 'templates', 'dashboard.html'), encoding='utf-8') as f:
        html = f.read()
    assert 'findings_undelivered:' in html, \
        'the entry would be in the feed with no icon and no wording'


def _submit_a_visit(monkeypatch, ed_emails):
    """Put a visit through the real route and return what was logged and sent.

    Everything that leaves the machine is replaced; the branch being tested is
    not. An earlier version of this asserted that a function returned what it
    had just been monkeypatched to return, which is a test of the patch.
    """
    logged, sent = [], []
    monkeypatch.setattr(A.activity_service, 'log',
                        lambda user, kind, detail='', meta=None: logged.append(
                            {'kind': kind, 'detail': detail, 'meta': meta or {}}))
    monkeypatch.setattr(A.email_service, 'enabled', True)
    monkeypatch.setattr(A.email_service, 'send_inspection_report',
                        lambda *a, **k: None)
    monkeypatch.setattr(A.email_service, 'send_community_findings',
                        lambda to, *a, **k: sent.append(list(to)))
    monkeypatch.setattr(A.email_service, 'send_directed_comments', lambda *a, **k: None)
    monkeypatch.setattr(A, 'community_account_emails', lambda *a, **k: list(ed_emails))
    monkeypatch.setattr(A, 'region_leader_emails', lambda c: ['regional@atlas.com'])
    monkeypatch.setattr(A, 'community_has_accounts', lambda c: False)

    # A real community and the region that covers it: the route refuses a
    # community outside the visitor's reach, and rightly — a session invented
    # without one gets a 400 that has nothing to do with what is being tested.
    community = (A.all_communities() or [''])[0]
    region = next((r for r in A.region_service.get_all_regions()
                   if community in (r.get('communities') or [])), None)
    if not community or not region:
        pytest.skip('needs a community inside a region')

    made = []
    monkeypatch.setattr(A.inspection_service, 'create_submission',
                        lambda *a, **k: made.append(1) or {
                            'id': 'smoke-delivery', 'username': 'smoke.deliver',
                            'community': community, 'submitted_at': '2026-09-16T10:00:00',
                            'survey_type_id': 'standards',
                            'responses': [{'question_id': 'q1', 'condition': 'Pass'}],
                            'action_items': []})

    types = [t for t in A.survey_type_service.get_all_survey_types() if t.get('id')]
    if not types:
        pytest.skip('needs a survey type')

    c = A.app.test_client()
    with c.session_transaction() as s:
        # The survey type lives in the session, chosen on the screen before
        # the form — a visit posted without one is refused there and never
        # reaches the branch being tested.
        s.update(user='smoke.deliver', role='regional', community=None,
                 region_id=region['id'], display_name='Smoke',
                 survey_type_id=types[0]['id'],
                 survey_type_name=types[0].get('name', ''))
    # Form data, not JSON: the route reads request.form and takes the
    # responses as a JSON string inside it, because a visit arrives as
    # multipart with the photos attached.
    import json as _json
    r = c.post('/api/inspections',
               data={'community': community,
                     'responses': _json.dumps([{'question_id': 'q1',
                                                'condition': 'Pass'}])},
               headers={'Origin': 'http://localhost', 'Referer': 'http://localhost/'})
    return r, logged, sent


def test_a_visit_whose_community_cannot_be_reached_says_so(monkeypatch):
    r, logged, sent = _submit_a_visit(monkeypatch, ed_emails=[])
    assert r.status_code in (200, 201), r.get_data(as_text=True)[:200]
    assert sent == [], 'an email went out with no address'
    assert any(e['kind'] == 'findings_undelivered' for e in logged), \
        'the community heard nothing and so did anybody who might fix it'


def test_a_visit_that_reaches_its_community_says_nothing(monkeypatch):
    """The note is for the silence, not for every visit."""
    r, logged, sent = _submit_a_visit(monkeypatch, ed_emails=['ed@atlas.com'])
    assert r.status_code in (200, 201)
    assert sent == [['ed@atlas.com']], 'the community email did not go'
    assert not any(e['kind'] == 'findings_undelivered' for e in logged), \
        'a delivered visit was reported as undelivered'
