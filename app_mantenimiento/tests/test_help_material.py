"""
Help material on a standard: a flyer or guide offered during the visit,
and sent to the Executive Director when the standard fails.

Gabriel (Nov 2026): on the "Atlerts App" standard, a regional should be able
to download the Atlerts flyer during the visit and pass it to the ED to put
up — and when that standard fails, the ED should get it without anybody
remembering to send it. A standard points at an item in Resources (one
place for files: the private bucket, signed downloads). The page side is
test_help_material.mjs.
"""

import os
import sys
import time

import pytest

_APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

import app as A  # noqa: E402
from services.question_manager import QuestionManager  # noqa: E402
from services.resource_service import ResourceService  # noqa: E402
from services.email_service import EmailService  # noqa: E402

HEADERS = {'Origin': 'http://localhost', 'Referer': 'http://localhost/'}
COMM = 'Kelley Place'


@pytest.fixture
def env(monkeypatch, tmp_path):
    qm = QuestionManager(str(tmp_path / 'questions.json'))
    rs = ResourceService(str(tmp_path / 'resources.json'))
    monkeypatch.setattr(A, 'question_manager', qm)
    monkeypatch.setattr(A.question_filter_service, 'question_manager', qm)
    monkeypatch.setattr(A, 'resource_service', rs)
    monkeypatch.setattr(A.survey_type_service, 'validate_survey_type', lambda *a: True)
    monkeypatch.setattr(A.activity_service, 'log', lambda *a, **k: None)
    monkeypatch.setattr(A, 'all_communities', lambda: [COMM])
    files = {}
    monkeypatch.setattr(A.file_upload_handler, 'read_bytes', lambda rel: files[rel])
    return qm, rs, files


def as_(role='admin', community=None):
    c = A.app.test_client()
    with c.session_transaction() as s:
        s.update(user='someone', role=role, display_name='someone', community=community,
                 communities=[community] if community else [])
    return c


def flyer(rs, files, name='atlerts-flyer.pdf', claimed='application/pdf', body=b'%PDF-1.4 flyer'):
    rec = rs.add('Atlerts flyer', '', 'file', file_path=f'resources/{name}', filename=name,
                 content_type=claimed, created_by='admin')
    files[f'resources/{name}'] = body
    return rec


def payload(**kw):
    base = {'text': 'Atlerts App is in use', 'photo_required': False,
            'communities': [COMM], 'survey_types': []}
    base.update(kw)
    return base


def test_a_standard_keeps_its_help_material(env):
    qm, rs, files = env
    rec = flyer(rs, files)
    r = as_().post('/api/questions', json=payload(help_resource_id=rec['id']), headers=HEADERS)
    assert r.status_code == 201
    q = r.get_json()['question']
    assert q['help_resource_id'] == rec['id']


def test_one_that_does_not_exist_is_refused(env):
    r = as_().post('/api/questions', json=payload(help_resource_id='res_nothing'), headers=HEADERS)
    assert r.status_code == 400 and 'no longer exists' in r.get_json()['message']


def test_editing_without_it_leaves_it_and_empty_takes_it_off(env):
    """Other edits never drop it by accident; clearing it is a choice."""
    qm, rs, files = env
    rec = flyer(rs, files)
    q = qm.create_question('Atlerts App is in use', False, [COMM], help_resource_id=rec['id'])
    c = as_()
    c.put(f"/api/questions/{q['id']}", json=payload(text='Atlerts App in use'), headers=HEADERS)
    assert qm.get_question(q['id']).get('help_resource_id') == rec['id']
    c.put(f"/api/questions/{q['id']}", json=payload(help_resource_id=''), headers=HEADERS)
    assert 'help_resource_id' not in qm.get_question(q['id'])


def test_the_visit_form_gets_title_kind_and_where(env):
    """The ED and their staff can see it too: it is information, nothing private."""
    qm, rs, files = env
    rec = flyer(rs, files)
    qm.create_question('Atlerts App is in use', False, [COMM], help_resource_id=rec['id'])
    for role in ('admin', 'staff', 'team'):
        qs = as_(role, None if role == 'admin' else COMM).get('/api/questions').get_json()['questions']
        h = qs[0].get('help')
        assert h and h['title'] == 'Atlerts flyer', role
        assert h['download'] == f"/api/resources/{rec['id']}/download"
        assert h['file'] == f"/api/resources/{rec['id']}/file"


def test_deleting_the_resource_takes_it_off_the_standard(env):
    qm, rs, files = env
    rec = flyer(rs, files)
    q = qm.create_question('Atlerts App is in use', False, [COMM], help_resource_id=rec['id'])
    r = as_().delete(f"/api/resources/{rec['id']}", headers=HEADERS)
    assert r.get_json()['standards_unlinked'] == 1
    assert 'help_resource_id' not in qm.get_question(q['id'])


def test_the_file_is_served_from_this_site_for_sharing(env):
    """A phone's share sheet needs the bytes in the page; S3 is another site."""
    qm, rs, files = env
    rec = flyer(rs, files)
    r = as_('team', COMM).get(f"/api/resources/{rec['id']}/file")
    assert r.status_code == 200 and r.data == b'%PDF-1.4 flyer'
    assert r.mimetype == 'application/pdf'
    assert r.headers['Content-Disposition'].startswith('attachment')


def test_a_claimed_type_is_never_trusted(env):
    """A ".pdf" claimed as text/html, served from this site, would run as a page."""
    qm, rs, files = env
    rec = flyer(rs, files, name='flyer.pdf', claimed='text/html', body=b'<script>alert(1)</script>')
    r = as_().get(f"/api/resources/{rec['id']}/file")
    assert r.mimetype == 'application/pdf'
    assert 'sandbox' in r.headers.get('Content-Security-Policy', '')
    assert r.headers.get('X-Content-Type-Options') == 'nosniff'
    odd = flyer(rs, files, name='notes.html', claimed='text/html', body=b'<b>x</b>')
    assert as_().get(f"/api/resources/{odd['id']}/file").mimetype == 'application/octet-stream'


def test_signed_in_only(env):
    qm, rs, files = env
    rec = flyer(rs, files)
    r = A.app.test_client().get(f"/api/resources/{rec['id']}/file")
    assert r.status_code in (302, 401)


def test_a_failed_standard_brings_its_help_material_to_the_ed(env, monkeypatch):
    """Phase two: nobody has to remember to send the flyer."""
    qm, rs, files = env
    rec = flyer(rs, files)
    q = qm.create_question('Atlerts App is in use', False, [COMM], help_resource_id=rec['id'])
    other = qm.create_question('Lobby clean', False, [COMM])
    sent = []
    es = EmailService(mail_from='x@y.z', app_base_url='https://excellence.example')
    monkeypatch.setattr(es, '_send', lambda to, subj, html_body, text: sent.append((html_body, text)) or (True, 'ok'))
    monkeypatch.setattr(A, 'question_manager', qm)
    failed = [{'question_id': q['id'], 'question_text': q['text'], 'condition': 'Fail'},
              {'question_id': other['id'], 'question_text': other['text'], 'condition': 'Fail'}]
    es.send_community_findings(['ed@x.com'], COMM, 'Greg', '2026-11-07', failed, [], {},
                               help_map=A._help_map())
    html_body, text = sent[0]
    link = f"https://excellence.example/api/resources/{rec['id']}/download"
    assert link in html_body and 'Atlerts flyer' in html_body
    assert html_body.count('Help material:') == 1, 'only the standard that has one'
    assert link in text
