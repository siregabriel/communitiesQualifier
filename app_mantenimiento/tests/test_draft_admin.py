"""
An administrator's side of somebody's unfinished visit: reminders, reading
it, and as a last resort sending it.

Greg Crutcher's Greystone visit sat for four days before anybody looked for
it, and unfinished visits expire after fourteen days without a save — photos
and all — without a word to anybody. Gabriel asked for a way to make sure the
work is followed up. Three pieces:

  1. The owner is reminded at 3 and 11 quiet days (once each per quiet spell),
     by the daily job, with the same dry-run and weekend rules as everything
     else it sends. An administrator can also send a reminder by hand.
  2. An administrator can read the draft — read-only.
  3. An administrator can send it on the owner's behalf. It goes out exactly
     like a visit they sent, marked "Sent by Excellence Administrator on <date>
     on behalf of <name>" (the administrator is never named on the visit —
     Gabriel's choice; the activity log says who). A Fail with no comment says
     none was written. The owner is emailed.

Run locally, never on the server.
"""

import io
import os
import sys
from datetime import datetime, timedelta

import pytest

_APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

import app as A  # noqa: E402
import send_reminders as S  # noqa: E402
from services.draft_notice_service import DraftNoticeService  # noqa: E402
from services.draft_service import DraftService  # noqa: E402
from services.email_service import EmailService, sent_on_behalf_line  # noqa: E402
from services.file_upload_handler import FileUploadHandler  # noqa: E402
from services.inspection_service import InspectionService  # noqa: E402

HEADERS = {'Origin': 'http://localhost', 'Referer': 'http://localhost/'}
GREG = 'greg.crutcher'
GREYSTONE = 'Monark Grove Greystone'
ST = 'sales-marketing'
QUESTIONS = [{'id': f'q{n}', 'text': f'Standard {n}'} for n in range(1, 6)]
JPEG = b'\xff\xd8\xff\xe0' + b'lobby' * 40


@pytest.fixture
def world(monkeypatch, tmp_path):
    uploads = tmp_path / 'uploads'
    uploads.mkdir()
    monkeypatch.setattr(A, 'draft_service', DraftService(str(tmp_path / 'drafts.json')))
    monkeypatch.setattr(A, 'draft_notice_service', DraftNoticeService(str(tmp_path / 'notices.json')))
    monkeypatch.setattr(A, 'file_upload_handler', FileUploadHandler(str(uploads)))
    monkeypatch.setattr(A, 'inspection_service',
                        InspectionService(str(tmp_path / 'inspections.json'), str(uploads)))
    monkeypatch.setattr(A.question_filter_service, 'get_questions_for_survey', lambda c, s: QUESTIONS)
    monkeypatch.setattr(A.survey_type_service, 'get_survey_type_name', lambda sid: 'Sales and Marketing')
    accounts = {GREG: {'exists': True, 'display_name': 'Greg Crutcher', 'email': 'greg@atlas.com'},
                'no.email': {'exists': True, 'display_name': 'No Email', 'email': ''}}
    monkeypatch.setattr(A, 'resolve_account_context', lambda u: accounts.get(u, {'exists': False}))
    monkeypatch.setattr(A, 'resolve_display_name', lambda u: accounts.get(u, {}).get('display_name', u))
    logged, mails = [], {'reminders': [], 'behalf': [], 'visit': []}
    monkeypatch.setattr(A.activity_service, 'log',
                        lambda user, kind, detail='', meta=None: logged.append(
                            {'user': user, 'kind': kind, 'detail': detail, 'meta': meta or {}}))
    monkeypatch.setattr(A.email_service, 'enabled', True)
    monkeypatch.setattr(A.email_service, 'app_base_url', 'https://standards.example')
    monkeypatch.setattr(A.email_service, 'send_draft_reminder',
                        lambda *a, **k: mails['reminders'].append(a) or (True, 'ok'))
    monkeypatch.setattr(A.email_service, 'send_sent_on_behalf',
                        lambda *a, **k: mails['behalf'].append(a) or (True, 'ok'))
    monkeypatch.setattr(A, '_send_visit_emails', lambda sub: mails['visit'].append(sub))
    return {'logged': logged, 'mails': mails, 'uploads': uploads}


def make_draft(username=GREG, days_quiet=0, responses=None, photo=True, notes='Good tour'):
    d = A.draft_service.save_content(
        username, GREYSTONE, ST,
        responses=responses if responses is not None else {
            'q1': {'condition': 'Pass', 'description': '', 'routeTo': ''},
            'q2': {'condition': 'Fail', 'description': 'Brochures out of date', 'routeTo': ''},
            'q3': {'condition': 'Fail', 'description': '', 'routeTo': ''},
        },
        action_items=[{'text': 'Order brochures', 'assigned_to': 'Sales', 'priority': 'high'}],
        notes=notes, total=5, saved_at=1)
    if photo:
        from werkzeug.datastructures import FileStorage
        path = A.file_upload_handler.save_draft_photo(
            FileStorage(io.BytesIO(JPEG), filename='lobby.jpg'), username, d['id'], 'q2')
        A.draft_service.set_photo(username, GREYSTONE, ST, 'q2', path, 'lobby.jpg', 'image/jpeg', len(JPEG))
    if days_quiet:
        for x in A.draft_service.drafts:
            if x['id'] == d['id']:
                x['updated_at'] = (datetime.now() - timedelta(days=days_quiet)).isoformat()
        A.draft_service.save_to_file()
    return A.draft_service.get(username, GREYSTONE, ST)


def as_(user='admin', role='admin'):
    c = A.app.test_client()
    with c.session_transaction() as s:
        s.update(user=user, role=role, display_name=user, community=None, region_id='north')
    return c


IDS = {'username': GREG, 'community': GREYSTONE, 'survey_type_id': ST}


# ------------------------------------------------------------- 1. reminders

def test_three_quiet_days_and_the_owner_is_due(world):
    make_draft(days_quiet=3)
    due = A.draft_service.due_reminders(datetime.now())
    assert len(due) == 1 and due[0]['stage'] == 3 and due[0]['days_left'] == 11


def test_two_quiet_days_is_too_soon(world):
    make_draft(days_quiet=2)
    assert A.draft_service.due_reminders(datetime.now()) == []


def test_once_per_mark(world):
    d = make_draft(days_quiet=4)
    A.draft_service.mark_reminded(d['id'], 4)
    assert A.draft_service.due_reminders(datetime.now()) == []


def test_eleven_days_is_the_second_and_last(world):
    d = make_draft(days_quiet=11)
    due = A.draft_service.due_reminders(datetime.now())
    assert due[0]['stage'] == 11, 'one reminder, the latest, not two at once'
    A.draft_service.mark_reminded(d['id'], 11)
    assert A.draft_service.due_reminders(datetime.now()) == [], 'the 3-day one is not sent late'


def test_a_reminder_does_not_postpone_expiry(world):
    d = make_draft(days_quiet=5)
    A.draft_service.mark_reminded(d['id'], 5)
    assert A.draft_service.get(GREG, GREYSTONE, ST)['updated_at'] == d['updated_at']


def test_working_on_it_again_starts_a_new_quiet_spell(world):
    d = make_draft(days_quiet=4, photo=False)
    A.draft_service.mark_reminded(d['id'], 4)
    A.draft_service.save_content(GREG, GREYSTONE, ST, responses=d['responses'],
                                 action_items=[], notes='', total=5, saved_at=2)
    assert A.draft_service.get(GREG, GREYSTONE, ST)['reminded'] == []


def test_an_empty_draft_is_not_chased(world):
    make_draft(days_quiet=5, responses={}, photo=False, notes='')
    A.draft_service.save_content  # keep the shape; nothing answered, nothing noted
    for x in A.draft_service.drafts:
        x['action_items'] = []
    A.draft_service.save_to_file()
    assert A.draft_service.due_reminders(datetime.now()) == []


def test_the_daily_job_does_not_send_unless_told(world, tmp_path, monkeypatch, capsys):
    from services import reminder_service as R
    monkeypatch.setattr(S, 'LEDGER', R.ReminderLedger(str(tmp_path / 'r.json')))
    S.LEDGER.arm(datetime.now() - timedelta(days=60))
    monkeypatch.setattr(A, 'community_account_emails', lambda *a, **k: [])
    make_draft(days_quiet=3)
    S.main(['--force'])
    assert world['mails']['reminders'] == [], 'a dry run reminded somebody'
    assert 'BORRADOR' in capsys.readouterr().out, 'and the dry run does not show it'


def test_the_daily_job_reminds_once(world, tmp_path, monkeypatch):
    from services import reminder_service as R
    monkeypatch.setattr(S, 'LEDGER', R.ReminderLedger(str(tmp_path / 'r.json')))
    S.LEDGER.arm(datetime.now() - timedelta(days=60))
    monkeypatch.setattr(A, 'community_account_emails', lambda *a, **k: [])
    make_draft(days_quiet=3)
    S.main(['--send', '--force'])
    assert len(world['mails']['reminders']) == 1
    to, name, community, survey, answered, total, quiet, left, link = world['mails']['reminders'][0]
    assert (to, community, answered, total, quiet, left) == ('greg@atlas.com', GREYSTONE, 3, 5, 3, 11)
    assert link.startswith('https://standards.example/reporte/resume?') and 'survey_type=sales-marketing' in link
    S.main(['--send', '--force'])
    assert len(world['mails']['reminders']) == 1, 'reminded twice for the same quiet spell'


def test_an_admin_reminds_by_hand(world):
    make_draft()
    r = as_().post('/api/drafts/remind', headers=HEADERS, json=IDS)
    assert r.status_code == 200, r.get_data(as_text=True)[:200]
    assert world['mails']['reminders'][0][0] == 'greg@atlas.com'
    assert any(e['kind'] == 'draft_reminded' for e in world['logged'])


def test_no_email_on_file_is_said(world):
    make_draft(username='no.email')
    r = as_().post('/api/drafts/remind', headers=HEADERS,
                   json={**IDS, 'username': 'no.email'})
    assert r.status_code == 400 and 'no email' in r.get_json()['message']


def test_the_reminder_email_says_when_it_goes():
    svc = EmailService(mail_from='x@example.com', region='us-east-1')
    sent = []
    svc._send = lambda to, subject, h, t: sent.append((subject, h, t)) or (True, 'ok')
    svc.send_draft_reminder('greg@atlas.com', 'Greg', GREYSTONE, 'Sales', 33, 35, 5, 9,
                            'https://x/reporte/resume?a=1')
    subject, h, t = sent[0]
    assert GREYSTONE in subject
    assert '33 of 35 answered' in h and 'deleted in 9 days' in h and 'any device' in h
    assert 'https://x/reporte/resume?a=1' in t


# ---------------------------------------------------------- 2. reading it

def test_an_admin_reads_it_in_survey_order(world):
    make_draft()
    r = as_().get('/api/drafts/review', headers=HEADERS, query_string=IDS)
    assert r.status_code == 200, r.get_data(as_text=True)[:200]
    d = r.get_json()['draft']
    assert [i['question_id'] for i in d['items']] == ['q1', 'q2', 'q3', 'q4', 'q5']
    assert d['items'][1]['description'] == 'Brochures out of date' and d['items'][1]['has_photo']
    assert (d['answered'], d['total'], d['fails_without_comment']) == (3, 5, 1)
    assert d['owner'] == 'Greg Crutcher'


def test_and_sees_its_photos(world):
    make_draft()
    r = as_().get('/api/drafts/review/photo', headers=HEADERS, query_string={**IDS, 'slot': 'q2'})
    assert r.status_code == 200 and r.data == JPEG


def test_nobody_else_does(world):
    make_draft()
    for c in (as_('another.regional', 'regional'), as_('an.ed', 'staff'), as_(GREG, 'regional')):
        assert c.get('/api/drafts/review', headers=HEADERS, query_string=IDS).status_code == 403
        assert c.get('/api/drafts/review/photo', headers=HEADERS,
                     query_string={**IDS, 'slot': 'q2'}).status_code == 403


def test_a_draft_that_is_not_on_the_server_says_so(world):
    r = as_().get('/api/drafts/review', headers=HEADERS, query_string=IDS)
    assert r.status_code == 404


# ------------------------------------------------- 3. sending on their behalf

def send(c=None, confirm=True):
    return (c or as_()).post('/api/drafts/send-on-behalf', headers=HEADERS,
                             json={**IDS, 'confirm': confirm})


def test_it_asks_for_confirmation(world):
    make_draft()
    assert send(confirm=False).status_code == 400
    assert A.inspection_service.get_all_submissions() == []


def test_only_an_admin_sends_it(world):
    make_draft()
    assert send(as_('another.regional', 'regional')).status_code == 403
    assert A.inspection_service.get_all_submissions() == []


def test_it_is_filed_as_the_inspectors_visit(world):
    make_draft()
    r = send()
    assert r.status_code == 200, r.get_data(as_text=True)[:300]
    sub = A.inspection_service.get_all_submissions()[0]
    assert sub['username'] == GREG and sub['inspector_name'] == 'Greg Crutcher'
    assert sub['community'] == GREYSTONE and sub['survey_type_id'] == ST
    assert [x['question_id'] for x in sub['responses']] == ['q1', 'q2', 'q3']
    assert sub['standards_total'] == 5, 'not marked partial'
    assert sub['notes'] == 'Good tour'
    assert sub['action_items'][0]['text'] == 'Order brochures'


def test_it_says_it_was_sent_for_them_without_naming_the_admin(world):
    make_draft()
    send()
    sub = A.inspection_service.get_all_submissions()[0]
    assert sub['sent_on_behalf']['at']
    assert 'admin' not in str(sub['sent_on_behalf']), 'the administrator is named on the visit'
    line = sent_on_behalf_line(sub)
    assert line.startswith('Sent by Excellence Administrator on ') and line.endswith('on behalf of Greg Crutcher')


def test_but_the_log_does(world):
    make_draft()
    send()
    e = next(e for e in world['logged'] if e['kind'] == 'inspection_sent_on_behalf')
    assert e['user'] == 'admin' and e['meta']['username'] == GREG and e['meta']['submission_id']


def test_a_fail_without_a_comment_says_so(world):
    make_draft()
    send()
    q3 = A.inspection_service.get_all_submissions()[0]['responses'][2]
    assert q3['condition'] == 'Fail' and q3['description'] == A.NO_COMMENT_ON_BEHALF


def test_its_photos_come_with_it(world):
    make_draft()
    send()
    q2 = A.inspection_service.get_all_submissions()[0]['responses'][1]
    assert q2['photo_path'] and not q2['photo_path'].startswith('drafts/'), \
        'the visit points at a draft photo that is about to be deleted'
    assert A.file_upload_handler.read_bytes(q2['photo_path']) == JPEG


def test_the_draft_is_gone_after(world):
    make_draft()
    A.draft_notice_service.record(GREG, GREYSTONE, ST, answered=3, total=5)
    send()
    assert A.draft_service.get(GREG, GREYSTONE, ST) is None
    assert A.draft_notice_service.for_user(GREG) == []
    left = [p for p in world['uploads'].rglob('*') if p.is_file() and 'drafts' in p.parts]
    assert left == [], 'the draft photos were left in the bucket'


def test_it_goes_out_like_any_visit_and_greg_is_told(world):
    make_draft()
    send()
    assert len(world['mails']['visit']) == 1, 'the visit emails did not go'
    to, name, community, survey, when = world['mails']['behalf'][0]
    assert (to, community) == ('greg@atlas.com', GREYSTONE)


def test_nothing_answered_nothing_sent(world):
    make_draft(responses={'q1': {'condition': '', 'description': 'note only', 'routeTo': ''}}, photo=False)
    r = send()
    assert r.status_code == 400
    assert A.inspection_service.get_all_submissions() == []
    assert A.draft_service.get(GREG, GREYSTONE, ST) is not None, 'the draft was thrown away anyway'


def test_the_leadership_report_carries_the_line():
    svc = EmailService(mail_from='x@example.com', region='us-east-1')
    sub = {'community': GREYSTONE, 'inspector_name': 'Greg Crutcher', 'submitted_at': '2026-11-07T10:00:00',
           'responses': [{'question_id': 'q1', 'condition': 'Pass'}],
           'sent_on_behalf': {'at': '2026-11-07T10:00:00'}}
    subject, h, t = svc._build(sub, 'Sales', {})
    assert 'Sent by Excellence Administrator on Nov 7 on behalf of Greg Crutcher' in h
    assert 'Sent by Excellence Administrator on Nov 7 on behalf of Greg Crutcher' in t
    plain = {**sub}
    plain.pop('sent_on_behalf')
    assert 'Excellence Administrator' not in svc._build(plain, 'Sales', {})[1]
