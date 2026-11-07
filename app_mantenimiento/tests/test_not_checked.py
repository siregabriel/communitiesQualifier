"""
"Not checked": a standard that could not be looked at on the day.

Greg Crutcher asked for it (Nov 2026): a walk where the kitchen was closed or
a room was locked left two bad choices, a Pass nobody verified or a Fail
nobody found. Leaving it blank worked but read as "forgot" and marked the
visit partial. He agreed it must carry a reason, because it is left out of the
score and would otherwise be an easy way to turn a Fail into a better number.

So these hold down: it is accepted only with a reason; it never moves a score
or a pass rate; it does not make a visit partial; and it is shown in every
place the visit is read back, so the regional knows what still needs a look.
The browser side is test_not_checked.mjs and test_not_checked_panel.mjs.
"""

import json
import os
import sys

import pytest

_APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

import app as A  # noqa: E402
from services.conditions import NOT_CHECKED  # noqa: E402
from services.draft_notice_service import DraftNoticeService  # noqa: E402
from services.draft_service import DraftService  # noqa: E402
from services.email_service import EmailService  # noqa: E402
from services.file_upload_handler import FileUploadHandler  # noqa: E402
from services.input_sanitizer import InputSanitizer  # noqa: E402
from services.inspection_service import InspectionService  # noqa: E402

HEADERS = {'Origin': 'http://localhost', 'Referer': 'http://localhost/'}
KELLEY = 'Kelley Place, Enterprise'
ST = 'standards'
QUESTIONS = [{'id': f'q{n}', 'text': f'Standard {n}'} for n in range(1, 5)]
REASON = 'Kitchen closed for deep cleaning'


@pytest.fixture
def world(monkeypatch, tmp_path):
    uploads = tmp_path / 'uploads'
    uploads.mkdir()
    monkeypatch.setattr(A, 'inspection_service',
                        InspectionService(str(tmp_path / 'inspections.json'), str(uploads)))
    monkeypatch.setattr(A, 'file_upload_handler', FileUploadHandler(str(uploads)))
    monkeypatch.setattr(A, 'draft_service', DraftService(str(tmp_path / 'drafts.json')))
    monkeypatch.setattr(A, 'draft_notice_service', DraftNoticeService(str(tmp_path / 'notices.json')))
    monkeypatch.setattr(A.question_filter_service, 'get_questions_for_survey', lambda c, s: QUESTIONS)
    monkeypatch.setattr(A.survey_type_service, 'validate_survey_type', lambda *a: True)
    monkeypatch.setattr(A.survey_type_service, 'get_survey_type_name', lambda sid: 'Standards')
    monkeypatch.setattr(A, 'regional_communities', lambda *a, **k: [KELLEY])
    monkeypatch.setattr(A, '_can_see_community', lambda *a, **k: True)
    monkeypatch.setattr(A, 'visible_communities', lambda *a, **k: [KELLEY])
    monkeypatch.setattr(A.activity_service, 'log', lambda *a, **k: None)
    sent = []
    monkeypatch.setattr(A, '_send_visit_emails', lambda sub: sent.append(sub))
    monkeypatch.setattr(A.email_service, 'send_sent_on_behalf', lambda *a, **k: (True, 'ok'))
    return {'sent': sent}


def regional():
    c = A.app.test_client()
    with c.session_transaction() as s:
        s.update(user='greg.crutcher', role='regional', display_name='Greg Crutcher',
                 community=None, survey_type_id=ST, survey_type_name='Standards')
    return c


def submit(responses, total=len(QUESTIONS)):
    return regional().post('/api/inspections', headers=HEADERS, data={
        'community': KELLEY, 'standards_total': str(total), 'responses': json.dumps(responses)})


A_VISIT = [
    {'question_id': 'q1', 'question_text': 'Standard 1', 'condition': 'Pass'},
    {'question_id': 'q2', 'question_text': 'Standard 2', 'condition': 'Fail', 'description': 'Exit sign out'},
    {'question_id': 'q3', 'question_text': 'Standard 3', 'condition': NOT_CHECKED, 'description': REASON},
    {'question_id': 'q4', 'question_text': 'Standard 4', 'condition': 'Pass'},
]


def history():
    r = regional().get(f'/api/communities/{KELLEY}/history?track=6', headers=HEADERS)
    assert r.status_code == 200, r.get_data(as_text=True)[:300]
    return r.get_json()


# ------------------------------------------------------------- sending one

def test_it_is_accepted_with_a_reason(world):
    r = submit(A_VISIT)
    assert r.status_code in (200, 201), r.get_data(as_text=True)[:300]
    sub = A.inspection_service.get_all_submissions()[0]
    q3 = next(x for x in sub['responses'] if x['question_id'] == 'q3')
    assert q3['condition'] == NOT_CHECKED
    assert q3['description'] == REASON


def test_without_a_reason_it_is_refused(world):
    """The form stops it too; this is the backstop."""
    blank = [dict(x) for x in A_VISIT]
    blank[2]['description'] = '   '
    r = submit(blank)
    assert r.status_code == 400
    assert 'say why' in r.get_json()['message']
    assert A.inspection_service.get_all_submissions() == []


def test_anything_else_is_still_refused(world):
    r = submit([{'question_id': 'q1', 'condition': 'N/A', 'description': 'x'}])
    assert r.status_code == 400
    assert InputSanitizer.sanitize_response_data({'condition': 'N/A'})['condition'] == ''
    assert InputSanitizer.sanitize_response_data({'condition': NOT_CHECKED})['condition'] == NOT_CHECKED


# ------------------------------------------------------- the score and partial

def test_it_does_not_move_the_score(world):
    """Two passes and a fail are 67%, with or without a Not checked beside them."""
    submit(A_VISIT)
    v = history()['visits'][0]
    assert v['visit_score'] == 67
    assert v['passed'] == 2 and v['failed'] == 1
    assert v['not_checked'] == 1


def test_it_does_not_make_the_visit_partial(world):
    """Every standard was answered: three verdicts and one honest skip."""
    submit(A_VISIT)
    v = history()['visits'][0]
    assert v['partial'] is False
    assert v['answered'] == 4


def test_a_blank_one_still_does(world):
    submit(A_VISIT[:3])
    assert history()['visits'][0]['partial'] is True


def test_the_timeline_marks_it_without_counting_it_as_seen(world):
    submit(A_VISIT)
    t = next(x for x in history()['standards'] if x['question_id'] == 'q3')
    assert t['results'][0] == 'not_checked'
    assert t['seen'] == 0 and t['fails'] == 0, 'nobody looked at it'


def test_atlasai_counts_it_apart(world):
    submit(A_VISIT)
    s = A._atlasai_scores(A.inspection_service.get_all_submissions()[0])
    assert s['visit_score'] == 67 and s['not_checked'] == 1


def test_the_export_pass_rate_leaves_it_out(world):
    """It divided by every response, so a Not checked would have read as a miss."""
    submit(A_VISIT)
    with A.app.test_request_context():
        A.session.update(user='admin', role='admin')
        s = A._export_summary()
    assert s['not_checked'] == 1
    assert s['passes'] == 2 and s['fails'] == 1
    assert s['pass_rate'] == 67


# ------------------------------------------------------------------- emails

SUB = {'community': KELLEY, 'inspector_name': 'Greg Crutcher', 'submitted_at': '2026-11-06T10:00:00',
       'responses': A_VISIT, 'action_items': []}


def test_the_leadership_report_lists_it_with_its_reason():
    subject, html_body, text = EmailService()._build(SUB)
    assert '67%' in subject, 'the score is the same'
    # The section title reads "Not checked · 1" since the email redesign (Nov 2026).
    assert 'Not checked &middot; 1' in html_body and REASON in html_body
    assert 'Not checked: 1 (not scored)' in text
    # Under its own heading, not loose after the failed items, where the reason
    # would read as a finding.
    head = text.index('Not checked (left out of the score):')
    assert text.index(f'Standard 3: {REASON}') > head


def test_a_clean_visit_with_one_does_not_say_all_passed():
    only = {**SUB, 'responses': [A_VISIT[0], A_VISIT[2]]}
    _, html_body, _ = EmailService()._build(only)
    assert 'All items passed' not in html_body
    assert 'Everything checked passed' in html_body


def test_the_community_hears_about_it_too(monkeypatch):
    es = EmailService()
    monkeypatch.setattr(es, 'enabled', True)
    got = {}
    monkeypatch.setattr(es, '_send', lambda to, subject, body, text: got.update(
        subject=subject, body=body, text=text) or (True, 'ok'))
    es.send_community_findings(['ed@kelley.com'], KELLEY, 'Greg Crutcher', '2026-11-06',
                               [], [], passed_items=[A_VISIT[0]], score=100,
                               not_checked_items=[A_VISIT[2]])
    assert 'Not checked this time' in got['body'] and REASON in got['body']
    assert REASON in got['text']
    assert 'Everything checked passed' in got['body']


def test_sent_to_a_department_it_says_it_was_not_checked(monkeypatch):
    """The reason is not a finding. Directed to Ops bare, "Kitchen closed"
    would read like something Ops has to fix."""
    es = EmailService()
    monkeypatch.setattr(es, 'enabled', True)
    got = {}
    monkeypatch.setattr(es, '_send', lambda to, subject, body, text: got.update(body=body, text=text) or (True, 'ok'))
    es.send_directed_comments(['ops@atlas.com'], 'ops', SUB, [A_VISIT[2], A_VISIT[1]])
    assert f'Not checked: {REASON}' in got['text']
    assert f'Not checked: {REASON}' in got['body']
    assert 'Not checked: Exit sign out' not in got['text'], 'a Fail comment is left as it was'


def test_the_visit_hands_it_to_the_community_email(monkeypatch):
    """The call site, not just the template: the list has to be passed in."""
    got = {}
    monkeypatch.setattr(A.email_service, 'enabled', True)
    monkeypatch.setattr(A, 'community_account_emails', lambda c: ['ed@kelley.com'])
    monkeypatch.setattr(A, 'region_leader_emails', lambda c: ['lead@atlas.com'])
    monkeypatch.setattr(A, 'resolve_account_context', lambda u: {})
    monkeypatch.setattr(A.email_service, 'send_inspection_report', lambda *a, **k: (True, 'ok'))
    monkeypatch.setattr(A.email_service, 'send_directed_comments', lambda *a, **k: (True, 'ok'))
    monkeypatch.setattr(A.email_service, 'send_community_findings',
                        lambda *a, **k: got.update(k) or (True, 'ok'))
    A._send_visit_emails({**SUB, 'id': 's1', 'username': 'greg.crutcher'})
    assert [r['question_id'] for r in got.get('not_checked_items', [])] == ['q3']


# ------------------------------------------------- unfinished visits

def test_a_draft_keeps_it(world):
    d = A.draft_service.save_content('greg.crutcher', KELLEY, ST,
                                     responses={'q3': {'condition': NOT_CHECKED, 'description': REASON}},
                                     action_items=[], notes='', total=4, saved_at=1)
    assert d['responses']['q3']['condition'] == NOT_CHECKED


def test_sent_on_behalf_it_goes_with_a_sentence_when_there_is_no_reason(world):
    A.draft_service.save_content('greg.crutcher', KELLEY, ST, responses={
        'q1': {'condition': 'Pass', 'description': ''},
        'q3': {'condition': NOT_CHECKED, 'description': ''},
    }, action_items=[], notes='', total=4, saved_at=1)
    ids = {'username': 'greg.crutcher', 'community': KELLEY, 'survey_type_id': ST}
    c = A.app.test_client()
    with c.session_transaction() as s:
        s.update(user='admin', role='admin', display_name='admin', community=None)
    review = c.get('/api/drafts/review', headers=HEADERS, query_string=ids).get_json()['draft']
    assert review['answered'] == 2
    assert review['not_checked_without_reason'] == 1
    r = c.post('/api/drafts/send-on-behalf', headers=HEADERS, json={**ids, 'confirm': True})
    assert r.status_code == 200, r.get_data(as_text=True)[:300]
    q3 = next(x for x in A.inspection_service.get_all_submissions()[0]['responses'] if x['question_id'] == 'q3')
    assert q3['condition'] == NOT_CHECKED
    assert q3['description'] == A.NO_REASON_ON_BEHALF
