"""
An Atlerts hand-off that does not complete leaves a trace.

The route is built to give up quietly: any doubt and the person lands on the
ordinary sign-in page, types their password and gets in. That is the right
behaviour — an error nobody can act on helps nobody.

The cost was invisible until Gabriel asked why some rows said "from Atlerts
on iOS" and others only "on iOS". They record different routes in, which is
correct — and it means a broken hand-off and somebody who simply prefers the
website read exactly the same. If the redemption broke for everyone, the feed
would show a slow drift away from Atlerts and be read as a change of habit.

So each way of giving up now records one line. Nothing changes for the person:
the assertions here are as much about that as about the logging.

Run locally, never on the server.
"""

import os
import sys

import pytest

_APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

import app as A  # noqa: E402


@pytest.fixture
def logged(monkeypatch):
    """Capture activity entries instead of writing them."""
    entries = []
    monkeypatch.setattr(A.activity_service, 'log',
                        lambda user, kind, detail='', meta=None: entries.append(
                            {'user': user, 'kind': kind, 'detail': detail, 'meta': meta or {}}))
    return entries


def _get(url):
    return A.app.test_client().get(url)


# ------------------------------------------------- every way of giving up

def test_no_secret_configured(logged, monkeypatch):
    monkeypatch.setattr(A, 'ATLERTS_SSO_SECRET', '')
    r = _get('/sso?code=abc123')
    assert r.status_code == 302 and '/login' in r.headers['Location']
    assert len(logged) == 1
    assert 'secret' in logged[0]['meta']['reason']


def test_atlerts_unreachable(logged, monkeypatch):
    monkeypatch.setattr(A, 'ATLERTS_SSO_SECRET', 'x')

    def boom(*a, **k):
        raise OSError('connection refused')
    monkeypatch.setattr(A.requests, 'post', boom)

    r = _get('/sso?code=abc123')
    assert r.status_code == 302 and '/login' in r.headers['Location']
    assert logged[0]['meta']['reason'] == 'could not reach Atlerts'


def test_a_code_that_is_expired_used_or_unknown(logged, monkeypatch):
    monkeypatch.setattr(A, 'ATLERTS_SSO_SECRET', 'x')

    class Resp:
        status_code = 404

        def json(self):
            return {}
    monkeypatch.setattr(A.requests, 'post', lambda *a, **k: Resp())

    r = _get('/sso?code=abc123')
    assert r.status_code == 302
    assert 'expired' in logged[0]['meta']['reason']


def test_an_email_with_no_account_here(logged, monkeypatch):
    """The one where the entry says what to do about it."""
    monkeypatch.setattr(A, 'ATLERTS_SSO_SECRET', 'x')

    class Resp:
        status_code = 200

        def json(self):
            return {'email': 'someone.new@atlasseniorliving.com'}
    monkeypatch.setattr(A.requests, 'post', lambda *a, **k: Resp())
    monkeypatch.setattr(A, '_atlerts_account_by_email', lambda e: None)

    r = _get('/sso?code=abc123')
    assert r.status_code == 302
    assert logged[0]['meta']['email'] == 'someone.new@atlasseniorliving.com', \
        'without the address there is nothing to act on'
    assert 'no Excellence account' in logged[0]['meta']['reason']


def test_arriving_with_no_code_is_not_a_failure(logged):
    """Somebody who reached this URL without coming from Atlerts.

    Nothing was attempted, so nothing is recorded — a feed that fills with
    entries for people simply visiting a URL is a feed nobody reads.
    """
    r = _get('/sso')
    assert r.status_code == 302 and '/login' in r.headers['Location']
    assert logged == []


# ------------------------------------------------ what it does not change

def test_somebody_coming_from_atlerts_still_gets_in(monkeypatch):
    """The thing all of this was built around, asserted end to end.

    Every edit above lives in a branch that gives up, so the way in should be
    untouched — but "should be untouched" is what everybody says before
    breaking something. This signs a regional in through the hand-off and
    checks they end up with a working session on the dashboard, not merely
    that a redirect was returned.

    It also exists because the first version of this change put the new helper
    between @app.route("/sso") and the function it decorates. Flask registered
    the helper as the view, and every hand-off would have been a 500.
    """
    monkeypatch.setattr(A, 'ATLERTS_SSO_SECRET', 'x')
    monkeypatch.setattr(A.presence_service, 'record_login', lambda u: None)
    monkeypatch.setattr(A.profile_service, 'get_admin_extra', lambda u: False)
    monkeypatch.setattr(A.profile_service, 'get_must_change', lambda u: False)

    class Resp:
        status_code = 200

        def json(self):
            return {'email': 'lauren@atlasseniorliving.com'}
    monkeypatch.setattr(A.requests, 'post', lambda *a, **k: Resp())
    monkeypatch.setattr(A, '_atlerts_account_by_email',
                        lambda e: ('lauren.hamilton',
                                   {'role': 'regional', 'community': None,
                                    'communities': [], 'region_id': 'innovia',
                                    'display_name': 'Lauren Hamilton'}))

    c = A.app.test_client()
    r = c.get('/sso?code=a-real-code')
    assert r.status_code == 302, r.get_data(as_text=True)[:200]
    assert r.headers['Location'].endswith('/'), \
        f'landed on {r.headers["Location"]} instead of the app'

    with c.session_transaction() as s:
        assert s.get('user') == 'lauren.hamilton', 'no session was established'
        assert s.get('role') == 'regional'
        assert s.get('region_id') == 'innovia'

    assert c.get('/dashboard').status_code == 200, \
        'the session exists but does not open anything'


def test_somebody_who_must_change_their_password_still_goes_there(monkeypatch):
    """The other destination this route has, so the branch is not forgotten."""
    monkeypatch.setattr(A, 'ATLERTS_SSO_SECRET', 'x')
    monkeypatch.setattr(A.presence_service, 'record_login', lambda u: None)
    monkeypatch.setattr(A.profile_service, 'get_admin_extra', lambda u: False)
    monkeypatch.setattr(A.profile_service, 'get_must_change', lambda u: True)

    class Resp:
        status_code = 200

        def json(self):
            return {'email': 'new@atlasseniorliving.com'}
    monkeypatch.setattr(A.requests, 'post', lambda *a, **k: Resp())
    monkeypatch.setattr(A, '_atlerts_account_by_email',
                        lambda e: ('new.person', {'role': 'staff', 'community': 'C',
                                                  'communities': ['C'], 'region_id': None,
                                                  'display_name': 'New Person'}))

    r = A.app.test_client().get('/sso?code=a-real-code')
    assert r.status_code == 302
    assert '/change-password' in r.headers['Location']


def test_the_route_is_wired_to_the_right_function():
    """A decorator sitting above the wrong function is not a syntax error.

    It reads as one function added above another, the app starts, and every
    request to the route calls something that was never meant to answer one.
    """
    rules = [r for r in A.app.url_map.iter_rules() if r.rule == '/sso']
    assert len(rules) == 1, f'/sso is registered {len(rules)} times'
    assert rules[0].endpoint == 'atlerts_sso', \
        f'/sso is answered by {rules[0].endpoint}'



def test_the_person_still_lands_on_the_sign_in_page(logged, monkeypatch):
    """The whole design of this route. Recording the failure must not start
    showing anybody an error they cannot resolve."""
    monkeypatch.setattr(A, 'ATLERTS_SSO_SECRET', '')
    r = _get('/sso?code=abc123')
    assert r.status_code == 302
    assert r.headers['Location'].endswith('/login')
    assert 'error' not in r.headers['Location']


def test_a_successful_hand_off_records_nothing_of_this(monkeypatch):
    """It records a sign-in, which it always did — and no failure."""
    entries = []
    monkeypatch.setattr(A.activity_service, 'log',
                        lambda user, kind, detail='', meta=None: entries.append(
                            {'user': user, 'kind': kind, 'detail': detail}))
    monkeypatch.setattr(A, 'ATLERTS_SSO_SECRET', 'x')
    monkeypatch.setattr(A.presence_service, 'record_login', lambda u: None)
    monkeypatch.setattr(A.profile_service, 'get_admin_extra', lambda u: False)
    monkeypatch.setattr(A.profile_service, 'get_must_change', lambda u: False)

    class Resp:
        status_code = 200

        def json(self):
            return {'email': 'someone@atlasseniorliving.com'}
    monkeypatch.setattr(A.requests, 'post', lambda *a, **k: Resp())
    monkeypatch.setattr(A, '_atlerts_account_by_email',
                        lambda e: ('someone', {'role': 'staff', 'community': 'C',
                                               'communities': ['C'], 'region_id': None,
                                               'display_name': 'Someone'}))

    r = _get('/sso?code=abc123')
    assert r.status_code == 302
    kinds = [e['kind'] for e in entries]
    assert 'sso_failed' not in kinds
    assert 'login' in kinds
    assert 'from Atlerts' in next(e['detail'] for e in entries if e['kind'] == 'login')


# ----------------------------------------------- how it reads in the feed

def test_the_entry_is_about_the_hand_off_not_a_person():
    """In four of the five cases we do not know who it was.

    So the subject is the hand-off itself. It has to read as a name and not as
    a username, or the row says "atlerts hand-off did not complete".
    """
    assert A.resolve_display_name('atlerts') == 'Atlerts'


def test_a_real_account_would_still_win(monkeypatch):
    """The system name is the last fallback, not an override.

    If a person ever ends up with that username they are still called by their
    own name.
    """
    monkeypatch.setattr(A.profile_service, 'get_display_name',
                        lambda u: 'A Real Person' if u == 'atlerts' else None)
    assert A.resolve_display_name('atlerts') == 'A Real Person'


def test_the_feed_knows_how_to_draw_it():
    """An unknown type renders without an icon or a verb — the entry would be
    there and say nothing."""
    with open(os.path.join(_APP_DIR, 'templates', 'dashboard.html'), encoding='utf-8') as f:
        html = f.read()
    assert 'sso_failed:' in html, 'the feed has no icon or wording for this type'


def test_every_giving_up_path_leaves_one(logged, monkeypatch):
    """Counted against the route itself, so a sixth way added later without a
    trace shows up here rather than as silence in production."""
    with open(os.path.join(_APP_DIR, 'app.py'), encoding='utf-8') as f:
        src = f.read()
    route = src[src.index('def atlerts_sso('):src.index('return redirect("/change-password"')]
    bare = route.count('return redirect("/login")')
    traced = route.count('_atlerts_gave_up(')
    assert traced == 4, f'expected four traced exits, found {traced}'
    assert bare == 1, \
        f'{bare} exits still leave no trace (only the no-code one should)'
