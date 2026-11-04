"""
Unfinished visits are kept on the server too, photos included.

Greg Crutcher answered 33 of 35 standards at Monark Grove Greystone, and a bug
in the form overwrote them on his phone four days later. They existed nowhere
else. The form bug is fixed; this is the second half: every save on the phone
is also sent here, photos go to the bucket under drafts/ as they are taken,
and resuming on any device brings the visit back.

What has to hold, besides it working:
  * a draft is readable only by the person who started it — not another
    regional, not an Executive Director, not an administrator (who keeps the
    signpost for support, never the content);
  * only for a community that person can see;
  * photos cannot be written outside the person's own drafts folder;
  * nothing lingers: sending the visit, discarding it, or two weeks without a
    save removes the draft and deletes its photos;
  * a community rename carries the draft with it.

Run locally, never on the server.
"""

import io
import json
import os
import sys
from datetime import datetime, timedelta

import pytest

_APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

import app as A  # noqa: E402
from services.draft_notice_service import DraftNoticeService  # noqa: E402
from services.draft_service import DraftService, clean_responses  # noqa: E402
from services.file_upload_handler import FileUploadHandler  # noqa: E402

HEADERS = {'Origin': 'http://localhost', 'Referer': 'http://localhost/'}
GREYSTONE = 'Monark Grove Greystone'
ELSEWHERE = 'Somewhere Else Place'
ST = 'sales-marketing'
JPEG = b'\xff\xd8\xff\xe0' + b'greystone-lobby' * 50


@pytest.fixture
def world(monkeypatch, tmp_path):
    uploads = tmp_path / 'uploads'
    uploads.mkdir()
    monkeypatch.setattr(A, 'draft_service', DraftService(str(tmp_path / 'drafts.json')))
    monkeypatch.setattr(A, 'draft_notice_service', DraftNoticeService(str(tmp_path / 'notices.json')))
    monkeypatch.setattr(A, 'file_upload_handler', FileUploadHandler(str(uploads)))
    monkeypatch.setattr(A, 'regional_communities', lambda: [GREYSTONE])
    monkeypatch.setattr(A.activity_service, 'log', lambda *a, **k: None)
    return uploads


def as_user(user='greg.crutcher', role='regional'):
    c = A.app.test_client()
    with c.session_transaction() as s:
        s.update(user=user, role=role, region_id='north', display_name=user,
                 community='Greystone ED Place' if role == 'staff' else None)
    return c


def put(c, responses=None, community=GREYSTONE, **extra):
    body = {'community': community, 'survey_type_id': ST, 'total': 35, 'saved_at': 1000,
            'responses': responses if responses is not None else {
                'q1': {'condition': 'Pass', 'description': '', 'routeTo': ''},
                'q2': {'condition': 'Fail', 'description': "Greg's note: brochures out of date", 'routeTo': ''},
            },
            'action_items': [{'text': 'Order new brochures', 'assigned_to': 'Sales', 'priority': 'high'}],
            'notes': 'Good tour.', 'device': 'iPhone · Safari'}
    body.update(extra)
    return c.put('/api/drafts/content', headers=HEADERS, json=body)


def get(c, community=GREYSTONE):
    return c.get(f'/api/drafts/content?community={community}&survey_type_id={ST}', headers=HEADERS)


def photo(c, slot='q2', data=JPEG, name='lobby.jpg'):
    return c.post('/api/drafts/photo', headers=HEADERS, content_type='multipart/form-data',
                  data={'community': GREYSTONE, 'survey_type_id': ST, 'slot': slot,
                        'photo': (io.BytesIO(data), name)})


def files(root):
    return sorted(str(p.relative_to(root)) for p in root.rglob('*') if p.is_file())


# ---------------------------------------------------------------- it works

def test_a_save_comes_back(world):
    c = as_user()
    assert put(c).status_code == 200
    d = get(c).get_json()['draft']
    assert d['responses']['q2']['condition'] == 'Fail'
    assert d['action_items'][0]['text'] == 'Order new brochures'
    assert d['notes'] == 'Good tour.'
    assert d['saved_at'] == 1000


def test_text_comes_back_as_typed(world):
    """It only ever goes back into form fields. Escaped here, it would come
    back as "Greg&#39;s" in his own sentence."""
    c = as_user()
    put(c)
    assert get(c).get_json()['draft']['responses']['q2']['description'] == \
        "Greg's note: brochures out of date"


def test_the_dashboard_count_comes_from_what_the_server_holds(world):
    c = as_user()
    put(c)
    notice = A.draft_notice_service.for_user('greg.crutcher')[0]
    assert (notice['answered'], notice['total']) == (2, 35)


def test_a_photo_comes_back_byte_for_byte(world):
    c = as_user()
    put(c)
    assert photo(c).status_code == 200
    d = get(c).get_json()['draft']
    assert d['photos']['q2']['name'] == 'lobby.jpg'
    assert d['photos']['q2']['size'] == len(JPEG)
    r = c.get(f'/api/drafts/photo?community={GREYSTONE}&survey_type_id={ST}&slot=q2', headers=HEADERS)
    assert r.status_code == 200 and r.data == JPEG


def test_photos_are_kept_under_drafts(world):
    c = as_user()
    photo(c)
    stored = files(world)
    assert len(stored) == 1 and stored[0].startswith('drafts/greg.crutcher/'), stored


def test_storage_paths_are_never_sent_to_the_phone(world):
    c = as_user()
    photo(c)
    assert 'drafts/' not in get(c).get_data(as_text=True)


def test_retaking_a_photo_replaces_it(world):
    c = as_user()
    photo(c, data=JPEG)
    photo(c, data=JPEG + b'retake')
    assert len(files(world)) == 1, 'the replaced photo was left in the bucket'


def test_removing_a_photo_deletes_it(world):
    c = as_user()
    photo(c)
    r = c.delete('/api/drafts/photo', headers=HEADERS,
                 json={'community': GREYSTONE, 'survey_type_id': ST, 'slot': 'q2'})
    assert r.status_code == 200
    assert files(world) == []
    assert get(c).get_json()['draft']['photos'] == {}


def test_the_notes_photo_has_its_own_slot(world):
    c = as_user()
    assert photo(c, slot='__notes__').status_code == 200
    assert '__notes__' in get(c).get_json()['draft']['photos']


# --------------------------------------------------------------- who reads it

def test_nobody_else_reads_it(world):
    put(as_user())
    assert get(as_user('another.regional')).get_json()['draft'] is None


def test_not_even_an_administrator(world):
    """Admins see who has an unfinished visit, where, and how far along — to
    help find work. Not the half-written findings themselves."""
    put(as_user())
    admin = A.app.test_client()
    with admin.session_transaction() as s:
        s.update(user='admin', role='admin', display_name='Administrator')
    assert get(admin).status_code == 403
    listing = admin.get('/api/drafts', headers=HEADERS).get_data(as_text=True)
    assert 'Greystone' in listing, 'the signpost is still there for support'
    assert 'brochures' not in listing, 'the content leaked into the signpost list'


def test_an_executive_director_keeps_no_drafts(world):
    assert put(as_user('the.ed', role='staff')).status_code == 403


def test_only_for_a_community_you_can_see(world):
    c = as_user()
    assert put(c, community=ELSEWHERE).status_code == 400
    assert get(c, community=ELSEWHERE).status_code == 400
    assert A.draft_service.drafts == []


def test_signed_out_gets_nothing(world):
    r = A.app.test_client().put('/api/drafts/content', headers=HEADERS,
                                json={'community': GREYSTONE, 'survey_type_id': ST})
    assert r.status_code in (302, 401)


# ---------------------------------------------------------------- what it refuses

@pytest.mark.parametrize('slot', ['../../etc', 'q1/../../x', '', 'a' * 81, 'q 1'])
def test_a_slot_cannot_walk_a_path(world, slot):
    assert photo(as_user(), slot=slot).status_code == 400
    assert files(world) == []


def test_not_an_image_is_refused(world):
    assert photo(as_user(), name='script.html', data=b'<script>').status_code == 400
    assert files(world) == []


def test_junk_in_the_answers_is_dropped():
    out = clean_responses({
        'q1': {'condition': 'Pass'},
        'q2': {'condition': 'Maybe', 'description': ''},        # unknown verdict, nothing else
        '../q3': {'condition': 'Fail'},                          # not a question id
        'q4': 'not a dict',
        'q5': {'condition': '', 'description': 'note only'},
        'q6': {'condition': 'Fail', 'description': 'x' * 10000},
    })
    assert set(out) == {'q1', 'q5', 'q6'}
    assert len(out['q6']['description']) == 4000


# ------------------------------------------------------------- nothing lingers

def test_discarding_removes_it_and_its_photos(world):
    c = as_user()
    put(c)
    photo(c)
    r = c.delete('/api/drafts', headers=HEADERS, json={'community': GREYSTONE, 'survey_type_id': ST})
    assert r.status_code == 200
    assert get(c).get_json()['draft'] is None
    assert files(world) == []
    assert A.draft_notice_service.for_user('greg.crutcher') == []


def test_sending_the_visit_removes_it_too(world, monkeypatch):
    """Not only when the phone remembers to say so."""
    c = as_user()
    put(c)
    photo(c)
    types = [t for t in A.survey_type_service.get_all_survey_types() if t.get('id')]
    if not types:
        pytest.skip('needs a survey type')
    monkeypatch.setattr(A.email_service, 'enabled', False)
    monkeypatch.setattr(A.inspection_service, 'create_submission',
                        lambda *a, **k: {'id': 's1', 'community': GREYSTONE, 'responses': [],
                                         'action_items': []})
    with c.session_transaction() as s:
        s.update(survey_type_id=ST, survey_type_name='Sales')
    monkeypatch.setattr(A.survey_type_service, 'validate_survey_type', lambda *a: True)
    r = c.post('/api/inspections', headers=HEADERS,
               data={'community': GREYSTONE,
                     'responses': json.dumps([{'question_id': 'q1', 'condition': 'Pass'}])})
    assert r.status_code in (200, 201), r.get_data(as_text=True)[:300]
    assert A.draft_service.get('greg.crutcher', GREYSTONE, ST) is None
    assert files(world) == []


def test_two_weeks_untouched_and_it_is_gone(world):
    c = as_user()
    put(c)
    photo(c)
    for d in A.draft_service.drafts:
        d['updated_at'] = (datetime.now() - timedelta(days=15)).isoformat()
    A.draft_service.save_to_file()
    assert get(c).get_json()['draft'] is None
    assert files(world) == [], 'the photos of an expired draft were left in the bucket'


def test_thirteen_days_and_it_is_still_there(world):
    c = as_user()
    put(c)
    for d in A.draft_service.drafts:
        d['updated_at'] = (datetime.now() - timedelta(days=13)).isoformat()
    A.draft_service.save_to_file()
    assert get(c).get_json()['draft'] is not None


def test_no_cap_on_how_many(world, monkeypatch):
    """One per community and survey type, as many as that adds up to. A cap
    would say "you're full" to somebody standing in a lobby."""
    names = [f'Place {i}' for i in range(6)]
    monkeypatch.setattr(A, 'regional_communities', lambda: names)
    c = as_user()
    for n in names:
        assert put(c, community=n).status_code == 200
    assert len(A.draft_service.drafts) == 6


# ------------------------------------------------------------------ the rename

def test_a_rename_carries_the_draft_and_its_signpost(world):
    c = as_user()
    put(c)
    A.draft_service.rename_community(GREYSTONE, 'Monarch Grove Greystone')
    A.draft_notice_service.rename_community(GREYSTONE, 'Monarch Grove Greystone')
    assert A.draft_service.get('greg.crutcher', 'Monarch Grove Greystone', ST) is not None
    assert A.draft_notice_service.for_user('greg.crutcher')[0]['community'] == 'Monarch Grove Greystone'


def test_the_rename_route_walks_them(world):
    src = open(os.path.join(_APP_DIR, 'app.py'), encoding='utf-8').read()
    i = src.index("def rename_region_community")
    body = src[i:src.index('\n@app.route', i)]
    assert 'draft_service.rename_community(old_name, new_name)' in body
    assert 'draft_notice_service.rename_community(old_name, new_name)' in body
