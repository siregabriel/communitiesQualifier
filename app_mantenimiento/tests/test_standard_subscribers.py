"""
A subscriber can ask for only some standards.

Visit report subscribers in Settings got the whole report or nothing, scoped
only by region or inspector. Somebody who follows one thing (the Social Media
standard, say) had to read every visit to find it. Now a subscriber can pick
standards: they are sent a short email with those answers only, and only
when the visit answered one of them. The pick narrows what they get; it never
adds visits outside their region/inspector scope.

Run locally, never on the server.
"""

import os
import sys

import pytest

_APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

import app as A  # noqa: E402
from services.email_service import EmailService  # noqa: E402
from services.settings_service import SettingsService  # noqa: E402

HEADERS = {'Origin': 'http://localhost', 'Referer': 'http://localhost/'}


@pytest.fixture
def settings(tmp_path, monkeypatch):
    s = SettingsService(str(tmp_path / 'settings.json'))
    monkeypatch.setattr(A, 'settings_service', s)
    return s


def subs(settings, *rows):
    settings.set_email_settings(subscribers=list(rows))


# --------------------------------------------------------------- who matches

def test_a_standards_subscriber_is_not_sent_the_whole_report(settings):
    subs(settings, {'email': 'social@atlas.com', 'standards': ['q_social']},
         {'email': 'all@atlas.com'})
    assert settings.recipients_for_inspection('north') == ['all@atlas.com']
    assert settings.standard_subscribers('north') == [
        {'email': 'social@atlas.com', 'standards': ['q_social']}]


def test_the_standards_narrow_the_scope_never_widen_it(settings):
    """South only + Social Media: a North visit sends them nothing."""
    subs(settings, {'email': 'social@atlas.com', 'regions': ['south'],
                    'standards': ['q_social']})
    assert settings.standard_subscribers('north') == []
    assert settings.standard_subscribers('south')[0]['email'] == 'social@atlas.com'


def test_the_pick_survives_a_save(settings):
    subs(settings, {'email': 'social@atlas.com', 'standards': ['q_social', 'q_social', ' ', 7]})
    assert settings.get_email_settings()['subscribers'][0]['standards'] == ['q_social']


# --------------------------------------------------------------- the visit

@pytest.fixture
def visit(settings, monkeypatch):
    sent = {'full': [], 'short': []}
    monkeypatch.setattr(A.email_service, 'enabled', True)
    monkeypatch.setattr(A.email_service, 'extra_recipients', [])
    monkeypatch.setattr(A.email_service, 'send_inspection_report',
                        lambda sub, to, *a, **k: sent['full'].append(list(to)))
    monkeypatch.setattr(A.email_service, 'send_selected_standards',
                        lambda to, sub, answers, *a, **k:
                        sent['short'].append((list(to), [r['question_id'] for r in answers])))
    monkeypatch.setattr(A.email_service, 'send_community_findings', lambda *a, **k: None)
    monkeypatch.setattr(A.email_service, 'send_directed_comments', lambda *a, **k: None)
    monkeypatch.setattr(A, 'community_account_emails', lambda *a, **k: [])
    monkeypatch.setattr(A, 'note_findings_undelivered', lambda *a, **k: None)
    monkeypatch.setattr(A, 'region_leader_emails', lambda c: ['lead@atlas.com'])
    monkeypatch.setattr(A, 'region_for_community', lambda c: {'id': 'north'})
    monkeypatch.setattr(A, 'resolve_account_context', lambda u: {'exists': False})

    def run(responses):
        A._send_visit_emails({'id': 's1', 'community': 'Alpha', 'username': 'x',
                              'submitted_at': '2026-11-10T10:00:00',
                              'responses': responses, 'action_items': []})
        return sent
    return run


ANSWERS = [{'question_id': 'q_social', 'condition': 'Fail', 'question_text': 'Social Media'},
           {'question_id': 'q_lobby', 'condition': 'Pass', 'question_text': 'Lobby'}]


def test_they_get_only_their_standard(settings, visit):
    subs(settings, {'email': 'social@atlas.com', 'standards': ['q_social']})
    sent = visit(ANSWERS)
    assert sent['short'] == [(['social@atlas.com'], ['q_social'])]
    assert 'social@atlas.com' not in sent['full'][0], 'and not the whole report as well'


def test_a_visit_without_their_standard_sends_nothing(settings, visit):
    subs(settings, {'email': 'social@atlas.com', 'standards': ['q_social']})
    assert visit(ANSWERS[1:])['short'] == []


def test_somebody_already_sent_the_whole_report_is_not_sent_both(settings, visit):
    """A region leader who also follows a standard reads it in their report."""
    subs(settings, {'email': 'Lead@atlas.com', 'standards': ['q_social']})
    assert visit(ANSWERS)['short'] == []


# --------------------------------------------------------------- the email

def test_the_email_carries_their_answers_and_nothing_else(monkeypatch):
    e = EmailService(mail_from='x@atlas.com')
    out = []
    monkeypatch.setattr(e, '_send', lambda to, subj, html_body, text: out.append((subj, html_body, text)))
    e.send_selected_standards(
        ['social@atlas.com'],
        {'community': 'Alpha', 'inspector_name': 'Carol', 'notes': 'PRIVATE NOTE',
         'responses': ANSWERS},
        [{**ANSWERS[0], 'description': 'No posts in a month'}])
    subj, html_body, text = out[0]
    for body in (html_body, text):
        assert 'Social Media' in body and 'No posts in a month' in body
        assert 'Lobby' not in body, 'a standard they did not pick'
        assert 'PRIVATE NOTE' not in body, 'the visit note is not theirs to read'
    assert '1 failed' in subj


# --------------------------------------------------------------- Settings

def _admin_client():
    c = A.app.test_client()
    with c.session_transaction() as s:
        s.update(user='admin', role='admin', display_name='Admin')
    return c


def test_settings_keeps_only_standards_that_exist(settings, monkeypatch):
    monkeypatch.setattr(A.activity_service, 'log', lambda *a, **k: None)
    monkeypatch.setattr(A.question_manager, 'get_all_active_questions',
                        lambda: [{'id': 'q_social', 'text': 'Social Media'}])
    r = _admin_client().post('/api/settings/email/subscriber', headers=HEADERS,
                             json={'email': 'social@atlas.com',
                                   'standards': ['q_social', 'q_gone']})
    assert r.status_code == 200, r.get_data(as_text=True)[:200]
    assert settings.get_email_settings()['subscribers'][0]['standards'] == ['q_social']


def test_removing_somebody_else_keeps_their_pick(settings, monkeypatch):
    monkeypatch.setattr(A.activity_service, 'log', lambda *a, **k: None)
    subs(settings, {'email': 'social@atlas.com', 'standards': ['q_social']},
         {'email': 'other@atlas.com'})
    r = _admin_client().delete('/api/settings/email/recipient', headers=HEADERS,
                               json={'email': 'other@atlas.com'})
    assert r.status_code == 200
    assert settings.get_email_settings()['subscribers'] == [
        {'email': 'social@atlas.com', 'name': '', 'regions': [], 'inspectors': [],
         'standards': ['q_social']}]


def test_the_summary_says_so(settings, monkeypatch):
    monkeypatch.setattr(A.question_manager, 'get_all_active_questions',
                        lambda: [{'id': 'q_social', 'text': 'Social Media'}])
    subs(settings, {'email': 'social@atlas.com', 'standards': ['q_social']})
    d = _admin_client().get('/api/settings/email/summary').get_json()
    rec = next(p for p in d['people'] if p['email'] == 'social@atlas.com')
    assert {'label': 'Selected standards only', 'detail': 'Standards: Social Media',
            'kind': 'scoped'} in rec['items']
