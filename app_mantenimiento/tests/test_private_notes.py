"""
Visit notes are private to the Executive Director and leadership by default.

Lauren Hamilton asked (Nov 2026) whether a community's whole management team
could read the notes a visitor writes to the Executive Director: "if ops does
a visit, will the whole management team be able to see their notes to Laura?
Or mine if I do a sales visit?" They could. Every account at the community,
Staff included, got the full visit, note and all, and the panel showed it.
Gabriel had just told her they could not.

Now a note is private unless the visitor ticks "Share this note with the
community's staff". Staff still get the visit and its findings, which are
what they are there to fix; only the note and its photo are held back, on the
server, in both places a visit is served. The form side is
test_private_notes.mjs.
"""

import json
import os
import sys

import pytest

_APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

import app as A  # noqa: E402
from services.draft_notice_service import DraftNoticeService  # noqa: E402
from services.draft_service import DraftService  # noqa: E402
from services.file_upload_handler import FileUploadHandler  # noqa: E402
from services.inspection_service import InspectionService  # noqa: E402

HEADERS = {'Origin': 'http://localhost', 'Referer': 'http://localhost/'}
VENICE = 'The Goldton at Venice, Venice'
ST = 'standards'
NOTE = 'Talk to Laura about her sales numbers before the review.'
FINDING = 'Lobby carpet stained near the entrance'


@pytest.fixture
def world(monkeypatch, tmp_path):
    uploads = tmp_path / 'uploads'
    uploads.mkdir()
    monkeypatch.setattr(A, 'inspection_service',
                        InspectionService(str(tmp_path / 'inspections.json'), str(uploads)))
    monkeypatch.setattr(A, 'file_upload_handler', FileUploadHandler(str(uploads)))
    monkeypatch.setattr(A, 'draft_service', DraftService(str(tmp_path / 'drafts.json')))
    monkeypatch.setattr(A, 'draft_notice_service', DraftNoticeService(str(tmp_path / 'notices.json')))
    monkeypatch.setattr(A.question_filter_service, 'get_questions_for_survey',
                        lambda c, s: [{'id': 'q1', 'text': 'Lobby clean'}])
    monkeypatch.setattr(A.survey_type_service, 'validate_survey_type', lambda *a: True)
    monkeypatch.setattr(A.survey_type_service, 'get_survey_type_name', lambda sid: 'Standards')
    monkeypatch.setattr(A, 'regional_communities', lambda *a, **k: [VENICE])
    monkeypatch.setattr(A.activity_service, 'log', lambda *a, **k: None)
    monkeypatch.setattr(A, '_send_visit_emails', lambda sub: None)
    monkeypatch.setattr(A.email_service, 'send_sent_on_behalf', lambda *a, **k: (True, 'ok'))


def client(user, role, community=VENICE, **extra):
    c = A.app.test_client()
    with c.session_transaction() as s:
        s.update(user=user, role=role, display_name=user, community=community,
                 communities=[community] if community else [], **extra)
    return c


def lauren():
    return client('lauren.hamilton', 'regional', None, survey_type_id=ST, survey_type_name='Standards')


def chef():
    return client('cait.chef', A.TEAM_ROLE)


def laura():
    return client('laura.blakeman', 'staff')


def visit(shared=None):
    data = {'community': VENICE, 'visit_notes': NOTE, 'responses': json.dumps([
        {'question_id': 'q1', 'question_text': 'Lobby clean', 'condition': 'Fail', 'description': FINDING}])}
    if shared is not None:
        data['visit_notes_shared'] = shared
    r = lauren().post('/api/inspections', headers=HEADERS, data=data)
    assert r.status_code in (200, 201), r.get_data(as_text=True)[:300]
    return A.inspection_service.get_all_submissions()[-1]


def served(c):
    """The visit as /api/inspections and the history give it to this account."""
    subs = c.get('/api/inspections', headers=HEADERS).get_json()['submissions']
    hist = c.get(f'/api/communities/{VENICE}/history', headers=HEADERS)
    assert hist.status_code == 200, hist.get_data(as_text=True)[:200]
    return subs[-1], hist.get_json()['visits'][0]


# ------------------------------------------------------------ the default

def test_a_note_is_private_unless_shared(world):
    sub = visit()
    assert sub['notes'] == NOTE
    assert not sub.get('notes_shared')


def test_staff_do_not_get_a_private_note(world):
    visit()
    listed, history = served(chef())
    assert 'notes' not in listed and 'notes_photo' not in listed
    assert history['notes'] == '' and history['notes_photo'] == ''
    assert NOTE not in json.dumps(listed) + json.dumps(history), 'the note leaked somewhere else'


def test_nor_its_photo(world):
    sub = visit()
    for s in A.inspection_service.submissions:
        if s['id'] == sub['id']:
            s['notes_photo'] = 'Venice/note.jpg'
    A.inspection_service.save_to_file()
    listed, history = served(chef())
    assert 'Venice/note.jpg' not in json.dumps(listed) + json.dumps(history)


def test_but_they_still_see_the_findings(world):
    """What they are there to fix."""
    visit()
    listed, history = served(chef())
    assert listed['responses'][0]['description'] == FINDING
    assert history['failed'] == 1


@pytest.mark.parametrize('who', ['ed', 'regional', 'admin'])
def test_the_ed_and_leadership_do(world, who):
    visit()
    c = {'ed': laura, 'regional': lambda: client('lauren.hamilton', 'regional', None),
         'admin': lambda: client('admin', 'admin', None)}[who]()
    listed, history = served(c)
    assert listed['notes'] == NOTE
    assert history['notes'] == NOTE
    assert history['notes_shared'] is False, 'so the panel can say it is private'


def test_staff_with_admin_privileges_are_admins_here(world, monkeypatch):
    visit()
    monkeypatch.setattr(A, 'is_admin', lambda: True)
    listed, _ = served(chef())
    assert listed['notes'] == NOTE


# ------------------------------------------------------------- shared

@pytest.mark.parametrize('flag', ['1', 'true', 'on'])
def test_a_shared_note_reaches_staff(world, flag):
    sub = visit(flag)
    assert sub['notes_shared'] is True
    listed, history = served(chef())
    assert listed['notes'] == NOTE
    assert history['notes'] == NOTE and history['notes_shared'] is True


@pytest.mark.parametrize('flag', ['', '0', 'false', 'no'])
def test_anything_else_stays_private(world, flag):
    assert not visit(flag).get('notes_shared')
    listed, _ = served(chef())
    assert 'notes' not in listed


def test_older_visits_stay_private(world):
    """Filed before the choice existed: no flag, so private."""
    sub = visit()
    for s in A.inspection_service.submissions:
        s.pop('notes_shared', None)
    A.inspection_service.save_to_file()
    listed, _ = served(chef())
    assert 'notes' not in listed


# -------------------------------------------------- unfinished visits

def test_the_choice_rides_with_the_draft_and_its_on_behalf_send(world):
    c = client('lauren.hamilton', 'regional', None)
    r = c.put('/api/drafts/content', headers=HEADERS, json={
        'community': VENICE, 'survey_type_id': ST, 'notes': NOTE, 'notes_shared': True,
        'responses': {'q1': {'condition': 'Pass', 'description': ''}}, 'total': 1, 'saved_at': 1})
    assert r.status_code == 200, r.get_data(as_text=True)[:200]
    back = c.get('/api/drafts/content', headers=HEADERS,
                 query_string={'community': VENICE, 'survey_type_id': ST}).get_json()['draft']
    assert back['notes_shared'] is True

    ids = {'username': 'lauren.hamilton', 'community': VENICE, 'survey_type_id': ST}
    r = client('admin', 'admin', None).post('/api/drafts/send-on-behalf', headers=HEADERS,
                                             json={**ids, 'confirm': True})
    assert r.status_code == 200, r.get_data(as_text=True)[:200]
    assert A.inspection_service.get_all_submissions()[-1]['notes_shared'] is True


def test_a_draft_only_shares_on_a_real_true(world):
    d = A.draft_service.save_content('x', VENICE, ST, responses={}, action_items=[], notes=NOTE,
                                     notes_shared='yes')
    assert d['notes_shared'] is False
