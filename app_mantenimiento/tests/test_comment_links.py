"""
A comment email opens the comment's own thread.

Gabriel asked whether the "standard commented" rows in Live activity could be
linked to straight from outside the app. Looking into it turned up that the
links the comment emails already carried never worked: "Review the item" went
to /?community=, and the home page redirected to the dashboard (admins) or to
starting a visit (everyone else) without the community. Somebody not signed in
was sent to /login, which then always went to the home page. So every reader
landed on a screen that had nothing to do with the comment.

Now the email links to the item itself (/dashboard?visit=&standard=, &item=, or
?raised=), signing in keeps that address, and old /?community= links reach the
dashboard. The page they come back to is checked: only a local path on an
allow-list, never another site.

Run locally, never on the server.
"""

import os
import sys
from urllib.parse import parse_qs, unquote, urlsplit

import pytest

_APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

import app as A  # noqa: E402
from services.email_service import EmailService  # noqa: E402

BASE = 'https://excellence.example'


def signed_in(user='greg', role='regional'):
    c = A.app.test_client()
    with c.session_transaction() as s:
        s.update(user=user, role=role, display_name=user, community=None, communities=[])
    return c


# ------------------------------------------------------------------ the links

def test_a_link_names_the_one_item():
    svc = EmailService(mail_from='x@y.z', app_base_url=BASE)
    assert svc.thread_link('s1', question_id='q1') == f'{BASE}/dashboard?visit=s1&standard=q1'
    assert svc.thread_link('s1', item_id='i1') == f'{BASE}/dashboard?visit=s1&item=i1'
    assert svc.thread_link(raised_id='r1') == f'{BASE}/dashboard?raised=r1'


def test_no_link_rather_than_a_half_one():
    """A visit without the standard would land on Action Items with nothing
    highlighted — the very thing this replaces."""
    svc = EmailService(mail_from='x@y.z', app_base_url=BASE)
    assert svc.thread_link('s1') is None
    assert EmailService(mail_from='x@y.z', app_base_url='').thread_link(raised_id='r1') is None


def test_the_email_button_is_the_item_link():
    svc = EmailService(mail_from='x@y.z', app_base_url=BASE)
    svc.enabled = True
    sent = []
    svc._send = lambda to, subject, html_body, text_body, **k: sent.append((html_body, text_body)) or (True, 'ok')
    link = svc.thread_link('s1', question_id='q1')
    svc.send_standard_comment(['a@x.com'], 'Kelley Place', 'Lobby', 'Ann', 'Done', link=link)
    html_body, text_body = sent[-1]
    assert f"href='{BASE}/dashboard?visit=s1&amp;standard=q1'" in html_body
    assert link in text_body
    # Without one it still links somewhere useful: the community.
    svc.send_standard_comment(['a@x.com'], 'Kelley Place', 'Lobby', 'Ann', 'Done')
    assert f'{BASE}/dashboard?community=Kelley%20Place' in sent[-1][1]


# ------------------------------------------------- each kind of comment uses it

@pytest.fixture
def mail(monkeypatch):
    got = []
    monkeypatch.setattr(A.email_service, 'enabled', True)
    monkeypatch.setattr(A.email_service, 'app_base_url', BASE)
    monkeypatch.setattr(A.email_service, 'send_standard_comment',
                        lambda to, *a, **k: got.append(k.get('link')))
    monkeypatch.setattr(A, 'region_leader_emails', lambda c: ['lead@atlas.com'])
    monkeypatch.setattr(A, 'community_account_emails', lambda c, **k: [])
    monkeypatch.setattr(A, 'resolve_account_context', lambda u: {'exists': False})
    return got


def as_user(fn):
    with A.app.test_request_context():
        A.session['user'] = 'someone'
        fn()


def test_a_comment_on_a_standard(mail):
    sub = {'id': 's1', 'community': 'C', 'responses': [{'question_id': 'q1', 'question_text': 'Lobby'}]}
    as_user(lambda: A.notify_comment(sub, 'q1', {'author': 'A', 'text': 't'}))
    assert mail[-1] == f'{BASE}/dashboard?visit=s1&standard=q1'


def test_a_comment_on_an_item_raised_on_a_visit(mail):
    sub = {'id': 's1', 'community': 'C', 'action_items': [{'id': 'i1', 'text': 'Sofa'}]}
    as_user(lambda: A.notify_item_comment(sub, 'Sofa', {'author': 'A', 'text': 't'}, 'i1'))
    assert mail[-1] == f'{BASE}/dashboard?visit=s1&item=i1'


def test_a_comment_on_something_a_community_raised(mail):
    item = {'id': 'r1', 'community': 'C', 'text': 'Carpet', 'visibility': 'community'}
    as_user(lambda: A.notify_raised_item_comment(item, {'author': 'A', 'text': 't'}))
    assert mail[-1] == f'{BASE}/dashboard?raised=r1'


def test_the_route_hands_the_item_id_on(mail, monkeypatch):
    """notify_item_comment had no item id to build a link from; the route
    has to pass it, or every such email links to nothing."""
    sub = {'id': 's1', 'community': 'C', 'action_items': [{'id': 'i1', 'text': 'Sofa'}]}
    monkeypatch.setattr(A.inspection_service, 'get_all_submissions', lambda: [sub])
    monkeypatch.setattr(A, '_can_see_community', lambda c: True)
    monkeypatch.setattr(A.inspection_service, 'add_item_comment',
                        lambda *a: {'id': 'c1', 'author': 'A', 'text': 'hi'})
    monkeypatch.setattr(A.activity_service, 'log', lambda *a, **k: None)
    r = signed_in().post('/api/action-items/s1/item/i1/comments', json={'text': 'hi'},
                         headers={'Origin': 'http://localhost', 'Referer': 'http://localhost/'})
    assert r.status_code == 201, r.get_data(as_text=True)
    assert mail[-1] == f'{BASE}/dashboard?visit=s1&item=i1'


# ----------------------------------------------------- signing in keeps the link

def next_of(location):
    return unquote(parse_qs(urlsplit(location).query).get('next', [''])[0])


def test_not_signed_in_the_link_survives_to_the_sign_in_page():
    r = A.app.test_client().get('/dashboard?visit=s1&standard=q1')
    assert r.status_code == 302
    assert urlsplit(r.headers['Location']).path == '/login'
    assert next_of(r.headers['Location']) == '/dashboard?visit=s1&standard=q1'


def test_the_sign_in_page_sends_them_on():
    page = A.app.test_client().get(
        '/login?next=' + '/dashboard%3Fvisit%3Ds1%26standard%3Dq1').get_data(as_text=True)
    assert 'const NEXT_PATH = "/dashboard?visit=s1\\u0026standard=q1"' in page
    assert "data.must_change_password ? '/change-password' : NEXT_PATH" in page


@pytest.mark.parametrize('bad', [
    'https://evil.example/dashboard', '//evil.example/dashboard', '/\\evil.example',
    '/api/inspections', '/admin', 'dashboard', 'javascript:alert(1)',
])
def test_but_only_to_a_page_of_ours(bad):
    from urllib.parse import quote
    page = A.app.test_client().get('/login?next=' + quote(bad, safe='')).get_data(as_text=True)
    assert 'const NEXT_PATH = ""' in page, bad
    r = signed_in().get('/login?next=' + quote(bad, safe=''))
    assert r.headers['Location'] != bad and 'evil' not in r.headers['Location']


def test_already_signed_in_goes_straight_there():
    r = signed_in().get('/login?next=' + '/dashboard%3Fraised%3Dr1')
    assert r.status_code == 302 and r.headers['Location'].endswith('/dashboard?raised=r1')


def test_an_api_call_is_never_a_place_to_come_back_to():
    r = A.app.test_client().get('/api/inspections')
    assert 'next=' not in (r.headers.get('Location') or '')


# ------------------------------------------------- links in emails already sent

def test_an_old_community_link_reaches_the_report_for_everyone():
    for role in ('regional', 'staff', 'admin'):
        r = signed_in(role=role).get('/?community=Kelley%20Place')
        assert r.status_code == 302, role
        loc = urlsplit(r.headers['Location'])
        assert loc.path == '/dashboard', (role, r.headers['Location'])
        assert parse_qs(loc.query) == {'community': ['Kelley Place']}, role


def test_and_survives_signing_in():
    r = A.app.test_client().get('/?community=Kelley%20Place')
    assert urlsplit(r.headers['Location']).path == '/login'
    assert next_of(r.headers['Location']) == '/dashboard?community=Kelley+Place'
