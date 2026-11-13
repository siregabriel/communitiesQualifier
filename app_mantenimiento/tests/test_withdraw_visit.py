"""
Withdrawing a visit.

Katie Beattie filed a Community Sales Improvement Plan at The Goldton At Lake
Nona on Nov 3 2026, saw she had done it wrong, and emailed asking whether she
could restart it after sending it, or remove it and redo it. There was no way
to: Gabriel had to stop the app and cut the visit out of inspections.json on
the server by hand. His rules for doing it in the app:

  * whoever filed it may take it back for 24 hours, while nobody has followed
    it up (a finding addressed, a comment, an item closed);
  * an administrator may at any time;
  * withdrawn, not deleted: kept aside, out of everything that reads visits;
  * everyone who was sent its report, and the Executive Director, are told;
  * optionally it comes back as an unfinished visit with the same answers.

Run locally, never on the server.
"""

import os
import sys
from datetime import datetime, timedelta

import pytest

_APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

import app as A  # noqa: E402
from services.draft_notice_service import DraftNoticeService  # noqa: E402
from services.draft_service import DraftService  # noqa: E402
from services.inspection_service import InspectionService  # noqa: E402
from services.username_rename import IDENTITY_FIELDS  # noqa: E402

HEADERS = {'Origin': 'http://localhost', 'Referer': 'http://localhost/'}
NONA = 'The Goldton At Lake Nona'
ST = 'community-sales-improvement-plan'
KATIE = 'katie.beattie'
OTHER = 'carol.brinegar'


@pytest.fixture
def world(monkeypatch, tmp_path):
    uploads = tmp_path / 'uploads'
    uploads.mkdir()
    store = str(tmp_path / 'inspections.json')
    monkeypatch.setattr(A, 'inspection_service', InspectionService(store, str(uploads)))
    monkeypatch.setattr(A, 'draft_service', DraftService(str(tmp_path / 'drafts.json')))
    monkeypatch.setattr(A, 'draft_notice_service', DraftNoticeService(str(tmp_path / 'notices.json')))
    monkeypatch.setattr(A.survey_type_service, 'get_survey_type_name',
                        lambda sid: 'Community Sales Improvement Plan')
    monkeypatch.setattr(A, 'regional_communities', lambda *a, **k: [NONA])
    monkeypatch.setattr(A, 'region_for_community', lambda c: {'id': 'florida'})
    monkeypatch.setattr(A, 'region_leader_emails', lambda c: ['regional@atlas.com'])
    monkeypatch.setattr(A.settings_service, 'recipients_for_inspection', lambda *a: ['corp@atlas.com'])
    monkeypatch.setattr(A, 'community_account_emails', lambda c, **k: ['ed.nona@atlas.com'])
    monkeypatch.setattr(A, 'resolve_account_context',
                        lambda u: {'exists': True, 'email': f'{u}@atlas.com', 'display_name': u})
    logged, mails = [], []
    monkeypatch.setattr(A.activity_service, 'log',
                        lambda user, kind, detail='', meta=None: logged.append(
                            {'user': user, 'kind': kind, 'detail': detail, 'meta': meta or {}}))
    monkeypatch.setattr(A.email_service, 'enabled', True)
    monkeypatch.setattr(A.email_service, 'send_visit_withdrawn',
                        lambda *a, **k: mails.append(a) or (True, 'ok'))
    return {'logged': logged, 'mails': mails, 'store': store, 'uploads': str(uploads)}


def client(user, role, community=None):
    c = A.app.test_client()
    with c.session_transaction() as s:
        s.update(user=user, role=role, display_name=user, community=community,
                 communities=[community] if community else [])
    return c


def katie():
    return client(KATIE, 'regional')


def admin():
    return client('gabriel', 'admin')


def visit(hours_ago=0):
    sub = A.inspection_service.create_submission(
        username=KATIE, community=NONA, survey_type_id=ST, inspector_name='Katie Beattie',
        responses=[
            {'question_id': 'q1', 'question_text': 'Tour route', 'condition': 'Pass',
             'description': '', 'photo_path': None, 'answered_at': 'x'},
            # Stored escaped, the way submit_inspection stores it.
            {'question_id': 'q2', 'question_text': 'Follow-up calls', 'condition': 'Fail',
             'description': 'Calls weren&#x27;t logged', 'photo_path': 'uploads/x/p.jpg',
             'route_to': None, 'answered_at': 'x'},
        ],
        action_items=[{'text': 'Retrain on CRM', 'assigned_to': 'Sales', 'priority': 'high'}],
        standards_total=14, notes='Good energy')
    if hours_ago:
        for s in A.inspection_service.submissions:
            if s['id'] == sub['id']:
                s['submitted_at'] = (datetime.now() - timedelta(hours=hours_ago)).isoformat()
        A.inspection_service.save_to_file()
    return sub['id']


def withdraw(c, sid, reason='Did this review incorrectly', redo=False):
    return c.post(f'/api/inspections/{sid}/withdraw', headers=HEADERS,
                  json={'reason': reason, 'redo': redo})


def listed(c):
    return {s['id']: s for s in c.get('/api/inspections', headers=HEADERS).get_json()['submissions']}


# ------------------------------------------------------------- who may

def test_katie_can_take_back_her_own_visit_the_same_day(world):
    sid = visit(hours_ago=3)
    r = withdraw(katie(), sid)
    assert r.status_code == 200, r.get_json()
    assert sid not in {s['id'] for s in A.inspection_service.get_all_submissions()}


def test_a_day_later_it_takes_an_administrator(world):
    sid = visit(hours_ago=25)
    r = withdraw(katie(), sid)
    assert r.status_code == 403 and 'administrator' in r.get_json()['message']
    assert withdraw(admin(), sid).status_code == 200


def test_another_regional_cannot_withdraw_her_visit(world):
    sid = visit()
    assert withdraw(client(OTHER, 'regional'), sid).status_code == 403
    assert sid in {s['id'] for s in A.inspection_service.get_all_submissions()}


def test_the_community_cannot_withdraw_a_visit_to_itself(world):
    sid = visit()
    assert withdraw(client('ed.nona', 'staff', NONA), sid).status_code == 403
    assert withdraw(client('chef.nona', A.TEAM_ROLE, NONA), sid).status_code == 403


@pytest.mark.parametrize('follow_up', ['comment', 'addressed', 'item_closed', 'item_comment'])
def test_once_somebody_follows_it_up_only_an_administrator_can(world, follow_up):
    """The ED's work on the findings would go with the visit."""
    sid = visit()
    sub = next(s for s in A.inspection_service.submissions if s['id'] == sid)
    if follow_up == 'comment':
        A.inspection_service.add_comment(sid, 'q2', 'ed.nona', 'ED', 'On it')
    elif follow_up == 'addressed':
        A.inspection_service.resolve_response(sid, 'q2', 'ed.nona', note='Done')
    elif follow_up == 'item_closed':
        A.inspection_service.resolve_action_item(sid, sub['action_items'][0]['id'], 'gabriel')
    else:
        A.inspection_service.add_item_comment(sid, sub['action_items'][0]['id'], 'ed.nona', 'ED', 'Booked')
    r = withdraw(katie(), sid)
    assert r.status_code == 403 and 'followed' in r.get_json()['message']
    assert withdraw(admin(), sid).status_code == 200


def test_a_reason_is_required(world):
    sid = visit()
    assert withdraw(katie(), sid, reason='   ').status_code == 400
    assert sid in {s['id'] for s in A.inspection_service.get_all_submissions()}


def test_an_unknown_visit_is_a_404(world):
    assert withdraw(admin(), 'insp_nope').status_code == 404


def test_withdrawing_twice_finds_nothing_the_second_time(world):
    sid = visit()
    assert withdraw(admin(), sid).status_code == 200
    assert withdraw(admin(), sid).status_code == 404


# ------------------------------------------------- what the panel is told

def test_the_panel_offers_it_only_where_the_server_would_accept_it(world):
    sid = visit()
    assert listed(katie())[sid].get('can_withdraw') is True
    assert 'can_withdraw' not in listed(client(OTHER, 'regional'))[sid]
    assert 'can_withdraw' not in listed(client('ed.nona', 'staff', NONA))[sid]


def test_the_offer_goes_after_24_hours(world):
    sid = visit(hours_ago=25)
    assert 'can_withdraw' not in listed(katie())[sid]
    assert listed(admin())[sid].get('can_withdraw') is True


def test_an_administrator_is_warned_when_it_has_been_followed_up(world):
    sid = visit()
    assert listed(admin())[sid]['worked_on'] is False
    A.inspection_service.add_comment(sid, 'q2', 'ed.nona', 'ED', 'On it')
    assert listed(admin())[sid]['worked_on'] is True


# ------------------------------------------------- gone, but kept

def test_it_leaves_every_reader_and_is_kept_aside(world):
    sid = visit()
    withdraw(katie(), sid)
    assert sid not in listed(admin())
    assert A.inspection_service.get_submissions_by_community(NONA) == []
    kept = next(s for s in A.inspection_service.withdrawn if s['id'] == sid)
    assert kept['withdrawn']['withdrawn_by'] == KATIE
    assert kept['withdrawn']['reason'] == 'Did this review incorrectly'
    assert kept['responses'][1]['description'] == 'Calls weren&#x27;t logged', 'record untouched'


def test_the_withdrawn_record_survives_a_restart(world):
    sid = visit()
    withdraw(katie(), sid)
    again = InspectionService(world['store'], world['uploads'])
    assert [s['id'] for s in again.withdrawn] == [sid]
    assert again.submissions == []


def test_a_community_rename_carries_withdrawn_visits_too(world):
    sid = visit()
    withdraw(katie(), sid)
    A.inspection_service.rename_community(NONA, 'Goldton Lake Nona')
    assert A.inspection_service.withdrawn[0]['community'] == 'Goldton Lake Nona'


def test_a_username_rename_carries_who_withdrew_it():
    assert 'withdrawn_by' in IDENTITY_FIELDS


def test_reset_clears_withdrawn_visits_too(world):
    sid = visit()
    withdraw(katie(), sid)
    A.inspection_service.reset_all()
    assert A.inspection_service.withdrawn == []


def test_the_activity_log_names_who_did_it(world):
    sid = visit()
    withdraw(admin(), sid)
    e = next(e for e in world['logged'] if e['kind'] == 'inspection_withdrawn')
    assert e['user'] == 'gabriel'
    assert e['meta']['submission_id'] == sid and e['meta']['username'] == KATIE
    assert "Katie Beattie's visit" in e['detail']


# ------------------------------------------------- who is told

def test_the_ed_and_everyone_on_the_report_are_told(world):
    sid = visit()
    withdraw(katie(), sid)
    (recipients, community, survey, when, inspector, by, reason), = world['mails']
    assert {'ed.nona@atlas.com', 'regional@atlas.com', 'corp@atlas.com',
            f'{KATIE}@atlas.com'} <= set(recipients)
    assert community == NONA and survey == 'Community Sales Improvement Plan'
    assert by == 'Katie Beattie' and reason == 'Did this review incorrectly'


def test_an_administrator_is_not_named_in_the_email(world):
    """Same rule as a visit sent on somebody's behalf (Gabriel's choice)."""
    sid = visit()
    withdraw(admin(), sid)
    assert world['mails'][0][5] == 'the Excellence Administrator'


def test_a_refused_withdrawal_tells_nobody(world):
    sid = visit(hours_ago=25)
    withdraw(katie(), sid)
    assert world['mails'] == [] and not any(e['kind'] == 'inspection_withdrawn' for e in world['logged'])


def test_the_email_escapes_the_reason(monkeypatch):
    sent = []
    svc = A.EmailService.__new__(A.EmailService)
    svc.enabled = True
    svc.app_base_url = ''
    monkeypatch.setattr(svc, '_send', lambda to, subj, html, text: sent.append((to, subj, html, text)) or (True, 'ok'))
    svc.send_visit_withdrawn(['ed@atlas.com'], NONA, 'Community Sales Improvement Plan',
                             'Nov 3, 2026', 'Katie Beattie', 'Katie Beattie', '<b>wrong</b> form')
    to, subj, html, text = sent[0]
    assert subj == f'Visit withdrawn: {NONA}'
    assert '&lt;b&gt;wrong&lt;/b&gt;' in html and '<b>wrong</b>' not in html
    assert 'withdrawn by Katie Beattie' in text and 'Reason: <b>wrong</b> form' in text


# ------------------------------------------------- doing it again

def test_redo_gives_her_an_unfinished_visit_with_her_answers(world):
    sid = visit()
    r = withdraw(katie(), sid, redo=True)
    assert r.get_json()['redo'] == 'created'
    d = A.draft_service.get(KATIE, NONA, ST)
    assert d['responses']['q2'] == {'condition': 'Fail',
                                    'description': "Calls weren't logged", 'routeTo': ''}, \
        'typed text goes back into the form unescaped'
    assert d['responses']['q1']['condition'] == 'Pass'
    assert d['action_items'] == [{'text': 'Retrain on CRM', 'assigned_to': 'Sales', 'priority': 'high'}]
    assert d['notes'] == 'Good energy' and d['total'] == 14
    assert d['photos'] == {}, 'photos stay with the withdrawn record'
    assert d['saved_at'] > 0, 'newer than any copy the phone kept'
    notice = A.draft_notice_service.for_user(KATIE)
    assert len(notice) == 1 and notice[0]['answered'] == 2


def test_redo_never_overwrites_an_unfinished_visit_already_there(world):
    sid = visit()
    A.draft_service.save_content(KATIE, NONA, ST, responses={'q9': {'condition': 'Pass'}},
                                 action_items=[], notes='started again already')
    r = withdraw(katie(), sid, redo=True)
    assert r.status_code == 200 and r.get_json()['redo'] == 'exists'
    assert A.draft_service.get(KATIE, NONA, ST)['notes'] == 'started again already'


def test_without_redo_no_draft_is_made(world):
    sid = visit()
    withdraw(katie(), sid)
    assert A.draft_service.get(KATIE, NONA, ST) is None


def test_redo_by_an_administrator_goes_to_whoever_filed_it(world):
    sid = visit(hours_ago=48)
    withdraw(admin(), sid, redo=True)
    assert A.draft_service.get(KATIE, NONA, ST) is not None
    assert A.draft_service.get('gabriel', NONA, ST) is None


# ------------------------------------------------- found on a second look

def test_a_comment_written_just_before_the_withdrawal_is_not_taken_with_it(world):
    """The route checks, then writes. Somebody else's process can comment in
    between; the service checks again under its lock, from the file."""
    sid = visit()
    other = InspectionService(world['store'], world['uploads'])   # the other worker
    real = A._withdraw_refusal

    def check_then_comment(sub):
        verdict = real(sub)
        other.add_comment(sid, 'q2', 'ed.nona', 'ED', 'Booked the training')
        return verdict
    A._withdraw_refusal = check_then_comment
    try:
        r = withdraw(katie(), sid)
    finally:
        A._withdraw_refusal = real
    assert r.status_code == 403
    assert sid in {s['id'] for s in A.inspection_service.get_all_submissions()}


def test_an_old_visit_without_a_survey_type_is_not_reopened_as_a_dead_draft(world):
    sid = visit()
    for s in A.inspection_service.submissions:
        s.pop('survey_type_id', None)
    A.inspection_service.save_to_file()
    r = withdraw(admin(), sid, redo=True)
    assert r.status_code == 200 and r.get_json()['redo'] == 'unavailable'
    assert A.draft_service.drafts == []
