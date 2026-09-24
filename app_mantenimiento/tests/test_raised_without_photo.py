"""
Raising an issue without attaching a photo.

Greg filled the form in on his phone — community picked, text written,
category chosen, no photo — and got "Pick a community you cover" in red
underneath a dropdown that was showing the community.

The form always posts multipart, whether or not a file is attached. The
route branched on `request.files` to decide where to read each field, and
`request.files` is empty when nobody attached anything, so every field was
read from the JSON body of a multipart request, which has none. All of them
arrived empty.

What people saw depended on who they were. Somebody covering several
communities got Greg's error. An Executive Director covering one had the
community filled in for them by a fallback further down, and then got "Say
what needs attention" under the text they had just typed. Commenting on an
item had the same shape: text lost unless a photo came with it.

It had been that way since the feature shipped. Two raised items existed in
production and both had photos — nobody had ever completed one without.

Run locally, never on the server.
"""

import io
import os
import sys

import pytest

_APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

import app as A  # noqa: E402


@pytest.fixture
def saved(monkeypatch):
    """Capture what would be stored instead of writing to the real file."""
    made = []

    def fake_create(community, text, username, display_name, priority='medium',
                    photo='', category='', visibility='community'):
        item = {'id': 'raised-test', 'community': community, 'text': text,
                'priority': priority, 'photo': photo, 'category': category,
                'visibility': visibility, 'raised_by': username, 'comments': []}
        made.append(item)
        return item

    monkeypatch.setattr(A.raised_item_service, 'create', fake_create)
    monkeypatch.setattr(A.email_service, 'enabled', False)
    monkeypatch.setattr(A.raised_category_service, 'is_choosable', lambda c: bool(c))
    return made


def _regional_session(client, communities):
    with client.session_transaction() as s:
        s.update(user='test.regional', role='regional', community=None,
                 communities=list(communities), region_id='innovia',
                 display_name='Test Regional')


@pytest.fixture
def client(monkeypatch):
    c = A.app.test_client()
    # A regional covering more than one community: the case that has to name
    # the community, and therefore the case the bug bit.
    monkeypatch.setattr(A, 'regional_communities',
                        lambda: ['Community One', 'Community Two'])
    monkeypatch.setattr(A, '_can_see_community',
                        lambda name: name in ('Community One', 'Community Two'))
    _regional_session(c, ['Community One', 'Community Two'])
    return c


HEADERS = {'Origin': 'http://localhost', 'Referer': 'http://localhost/'}


# ------------------------------------------------------ the one that failed

def test_multipart_with_no_photo_is_accepted(client, saved):
    """The exact shape the form sends when nobody attaches anything."""
    r = client.post('/api/raised-items', headers=HEADERS, data={
        'community': 'Community One',
        'text': 'We need a one bedroom model put together.',
        'category': 'exec',
        'priority': 'high',
    })
    assert r.status_code in (200, 201), r.get_data(as_text=True)[:200]
    assert len(saved) == 1
    assert saved[0]['community'] == 'Community One'
    assert 'one bedroom model' in saved[0]['text']
    assert saved[0]['priority'] == 'high'
    assert saved[0]['category'] == 'exec'


def test_and_the_text_is_not_silently_lost(client, saved):
    """The Executive Director's version of the same bug: community resolved,
    text gone, and an error about the field they had filled in."""
    r = client.post('/api/raised-items', headers=HEADERS, data={
        'community': 'Community One', 'text': 'Handrail is loose', 'category': 'maint'})
    assert r.status_code in (200, 201)
    assert saved[0]['text'] == 'Handrail is loose'


def test_multipart_with_a_photo_still_works(client, saved, monkeypatch):
    """The path that did work must keep working — this is the half the old
    branch got right."""
    monkeypatch.setattr(A.file_upload_handler, 'validate_file', lambda f: (True, ''))
    monkeypatch.setattr(A.file_upload_handler, 'save_file',
                        lambda f, u, c: 'Community_One/photo.jpg')
    r = client.post('/api/raised-items', headers=HEADERS, data={
        'community': 'Community One', 'text': 'Broken gate', 'category': 'maint',
        'photo': (io.BytesIO(b'\xff\xd8\xff not really a jpeg'), 'gate.jpg'),
    }, content_type='multipart/form-data')
    assert r.status_code in (200, 201), r.get_data(as_text=True)[:200]
    assert saved[0]['photo'] == 'Community_One/photo.jpg'
    assert saved[0]['text'] == 'Broken gate'


def test_a_json_body_still_works(client, saved):
    """Nothing in the app posts JSON here today, but the route accepted it and
    removing that quietly would be a second bug of the same kind."""
    r = client.post('/api/raised-items', headers=HEADERS, json={
        'community': 'Community Two', 'text': 'Lobby lighting', 'category': 'maint'})
    assert r.status_code in (200, 201), r.get_data(as_text=True)[:200]
    assert saved[0]['community'] == 'Community Two'
    assert saved[0]['text'] == 'Lobby lighting'


# ------------------------------------------- what must not have loosened

def test_an_empty_text_is_still_refused(client, saved):
    r = client.post('/api/raised-items', headers=HEADERS, data={
        'community': 'Community One', 'text': '   ', 'category': 'maint'})
    assert r.status_code == 400
    assert 'what needs attention' in r.get_json()['message'].lower()
    assert saved == []


def test_a_community_outside_your_reach_is_still_refused(client, saved):
    r = client.post('/api/raised-items', headers=HEADERS, data={
        'community': 'Somewhere Else', 'text': 'x', 'category': 'maint'})
    assert r.status_code == 400
    assert saved == []


def test_a_missing_category_is_still_refused(client, saved):
    r = client.post('/api/raised-items', headers=HEADERS, data={
        'community': 'Community One', 'text': 'x', 'category': ''})
    assert r.status_code == 400
    assert saved == []


def test_internal_still_takes_more_than_asking(client, saved, monkeypatch):
    """visibility is read the same new way, so the check that it is allowed
    has to be exercised through that path too."""
    monkeypatch.setattr(A, 'can_see_internal', lambda: False)
    r = client.post('/api/raised-items', headers=HEADERS, data={
        'community': 'Community One', 'text': 'x', 'category': 'maint',
        'visibility': 'internal'})
    assert r.status_code in (200, 201)
    assert saved[0]['visibility'] == 'community', \
        'anyone posting visibility=internal got it'


def test_internal_is_honoured_for_somebody_who_may(client, saved, monkeypatch):
    monkeypatch.setattr(A, 'can_see_internal', lambda: True)
    r = client.post('/api/raised-items', headers=HEADERS, data={
        'community': 'Community One', 'text': 'x', 'category': 'maint',
        'visibility': 'internal'})
    assert r.status_code in (200, 201)
    assert saved[0]['visibility'] == 'internal', \
        'a leadership-only item was filed as visible to the community'


# ------------------------------------------------- the same bug, commenting

def test_commenting_without_a_photo_keeps_the_words(monkeypatch):
    """`comment_on_raised_item` had the identical branch."""
    item = {'id': 'raised-1', 'community': 'Community One', 'text': 'x',
            'visibility': 'community', 'comments': []}
    said = []
    monkeypatch.setattr(A.raised_item_service, 'get', lambda i: item)
    monkeypatch.setattr(A, '_may_see_raised_item', lambda i: True)
    monkeypatch.setattr(A.raised_item_service, 'add_comment',
                        lambda item_id, username, display_name, text, photo='':
                        said.append(text) or {'id': 'cm-1', 'text': text})
    monkeypatch.setattr(A.email_service, 'enabled', False)

    c = A.app.test_client()
    with c.session_transaction() as s:
        s.update(user='test.regional', role='regional', region_id='innovia',
                 display_name='Test Regional')
    # Singular. Posting to /comments returns a Flask 404 that has nothing to
    # do with the route, which is a way to write a test that proves nothing.
    r = c.post('/api/raised-items/raised-1/comment', headers=HEADERS,
               data={'text': 'Vendor is booked for Tuesday'})
    assert r.status_code in (200, 201), r.get_data(as_text=True)[:200]
    assert said == ['Vendor is booked for Tuesday']


# ------------------------------------------------------ the branch is gone

def test_no_route_decides_where_to_read_by_whether_a_file_came():
    """Counted against the source, because the fix is the absence of
    something: a new route written in the old shape would be this bug again
    and would look perfectly reasonable in review."""
    with open(os.path.join(_APP_DIR, 'app.py'), encoding='utf-8') as f:
        src = f.read()
    assert 'if request.files' not in src, \
        'a route is choosing form-or-JSON by whether a file was attached again'
