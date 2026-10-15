"""
Linking the address Atlerts knows somebody by to their account here.

Every Excellence account carries a corporate address. Many people set Atlerts
up with a personal one — Gmail, Yahoo, Outlook — and the SSO matched on the
email alone. So the hand-off reached Excellence, Atlerts vouched for
laurablakeman11@gmail.com, no account had that address, and Laura was sent to
the password screen. Twenty-five times in two weeks; nine people in all.

The fix is that the person joins the two themselves, once. When Atlerts fails
to match, the address is remembered in that browser's session. When they then
sign in with their password, they are asked whether to link it. Both halves
are proven at that moment — Atlerts verified the address, and they just typed
this account's password — so nobody can link an address to an account that
is not theirs.

Run locally, never on the server.
"""

import json
import os
import sys

import pytest

_APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

import app as A  # noqa: E402
from services.profile_service import ProfileService  # noqa: E402
from services.region_service import RegionService  # noqa: E402

HEADERS = {'Origin': 'http://localhost', 'Referer': 'http://localhost/'}

LAURA = 'laura.blakeman'
GMAIL = 'laurablakeman11@gmail.com'
PASSWORDS = {LAURA: 'pw-laura', 'bob.corporate': 'pw-bob', 'admin': 'pw-admin'}


@pytest.fixture
def world(monkeypatch, tmp_path):
    regions = tmp_path / 'regions.json'
    regions.write_text(json.dumps({'regions': [
        {'id': 'north', 'name': 'North', 'communities': ['Alpha'],
         'leadership': [
             {'name': 'Laura Blakeman', 'role': 'RDO', 'username': LAURA,
              'email': 'lblakeman@atlasseniorliving.com'},
             {'name': 'Bob Corporate', 'role': 'RDO', 'username': 'bob.corporate',
              'email': 'bob@atlasseniorliving.com'},
         ]},
    ]}), encoding='utf-8')
    monkeypatch.setattr(A, 'region_service', RegionService(str(regions)))
    monkeypatch.setattr(A, 'REGIONS_FILE', str(regions))
    monkeypatch.setattr(A, 'profile_service', ProfileService(str(tmp_path / 'profiles.json')))
    A._regional_accounts_cache['accounts'] = None

    accounts = A.get_regional_accounts()

    def authenticate(username, password):
        if PASSWORDS.get(username) != password:
            return (False, None)
        if username == 'admin':
            return (True, {'role': 'admin', 'community': None, 'region_id': None,
                           'display_name': 'Administrator'})
        a = accounts[username]
        return (True, {'role': 'regional', 'community': None, 'region_id': a['region_id'],
                       'display_name': a['display_name'], 'communities': a['communities']})
    monkeypatch.setattr(A, 'authenticate_user', authenticate)
    monkeypatch.setattr(A, 'login_is_throttled', lambda: False)
    monkeypatch.setattr(A, 'ATLERTS_SSO_SECRET', 'x')
    monkeypatch.setattr(A.presence_service, 'record_login', lambda u: None)
    logged = []
    monkeypatch.setattr(A.activity_service, 'log',
                        lambda user, kind, detail='', meta=None: logged.append(
                            {'user': user, 'kind': kind, 'detail': detail, 'meta': meta or {}}))
    yield logged
    A._regional_accounts_cache['accounts'] = None


def atlerts_says(monkeypatch, email):
    class Resp:
        status_code = 200

        def json(self):
            return {'email': email}
    monkeypatch.setattr(A.requests, 'post', lambda *a, **k: Resp())


def sso(client):
    return client.get('/sso?code=a-code')


def login(client, username=LAURA):
    return client.post('/api/login', headers=HEADERS,
                       json={'username': username, 'password': PASSWORDS[username]})


def answer(client, link):
    return client.post('/api/atlerts-link', headers=HEADERS, json={'link': link})


def signed_in_as(client):
    with client.session_transaction() as s:
        return s.get('user')


# --------------------------------------------------------- the whole journey

def test_laura_links_once_and_atlerts_works_from_then_on(world, monkeypatch):
    atlerts_says(monkeypatch, GMAIL)
    c = A.app.test_client()

    r = sso(c)
    assert r.headers['Location'].endswith('/login'), 'the first try still lands on sign-in'

    r = login(c)
    assert r.status_code == 200
    assert r.get_json()['atlerts_link'] == GMAIL, 'she was not offered the link'

    r = answer(c, True)
    assert r.status_code == 200 and r.get_json()['linked'] is True, r.get_data(as_text=True)
    assert A.profile_service.get_atlerts_email(LAURA) == GMAIL

    # Next day, a fresh browser session.
    fresh = A.app.test_client()
    r = sso(fresh)
    assert r.headers['Location'].endswith('/'), \
        f'Atlerts still sent her to {r.headers["Location"]}'
    assert signed_in_as(fresh) == LAURA


def test_the_link_is_recorded_in_the_feed(world, monkeypatch):
    atlerts_says(monkeypatch, GMAIL)
    c = A.app.test_client()
    sso(c); login(c); answer(c, True)
    linked = [e for e in world if e['kind'] == 'atlerts_linked']
    assert linked and linked[0]['user'] == LAURA
    assert GMAIL in linked[0]['detail']


def test_not_me_links_nothing_and_does_not_ask_again(world, monkeypatch):
    atlerts_says(monkeypatch, GMAIL)
    c = A.app.test_client()
    sso(c); login(c)
    r = answer(c, False)
    assert r.status_code == 200 and r.get_json()['linked'] is False
    assert A.profile_service.get_atlerts_email(LAURA) == ''
    assert login(c).get_json()['atlerts_link'] == '', 'asked again after Not me'
    assert sso(A.app.test_client()).headers['Location'].endswith('/login')


# -------------------------------------------------------- who is asked

def test_nobody_is_asked_without_a_failed_hand_off(world):
    c = A.app.test_client()
    assert login(c).get_json()['atlerts_link'] == ''


def test_a_successful_hand_off_leaves_nothing_pending(world, monkeypatch):
    """Failed with one address, then got in with the corporate one: there is
    nothing left to link, and a later password sign-in must not ask."""
    c = A.app.test_client()
    atlerts_says(monkeypatch, GMAIL)
    sso(c)
    atlerts_says(monkeypatch, 'lblakeman@atlasseniorliving.com')
    assert sso(c).headers['Location'].endswith('/')
    assert login(c).get_json()['atlerts_link'] == ''


def test_signing_out_forgets_it(world, monkeypatch):
    atlerts_says(monkeypatch, GMAIL)
    c = A.app.test_client()
    sso(c)
    c.get('/logout')
    assert login(c).get_json()['atlerts_link'] == ''


def test_an_address_already_linked_here_is_not_offered_again(world, monkeypatch):
    A.profile_service.set_atlerts_email(LAURA, GMAIL)
    c = A.app.test_client()
    with c.session_transaction() as s:
        s['atlerts_pending'] = GMAIL
    assert login(c).get_json()['atlerts_link'] == ''


def test_the_built_in_administrator_is_not_asked(world, monkeypatch):
    """Seeded accounts carry no email and Atlerts never signs them in."""
    atlerts_says(monkeypatch, 'someone@gmail.com')
    c = A.app.test_client()
    sso(c)
    assert login(c, 'admin').get_json()['atlerts_link'] == ''


# --------------------------------------------------------- what it refuses

def test_the_address_comes_from_the_session_not_the_request(world):
    """Otherwise anybody signed in could link any address to themselves and
    then be signed in by whoever owns it in Atlerts."""
    c = A.app.test_client()
    login(c)
    r = c.post('/api/atlerts-link', headers=HEADERS,
               json={'link': True, 'email': 'attacker@gmail.com'})
    assert r.status_code == 400
    assert A.profile_service.get_atlerts_email(LAURA) == ''
    assert A.profile_service.username_for_atlerts_email('attacker@gmail.com') is None


def test_signed_out_cannot_link(world):
    c = A.app.test_client()
    with c.session_transaction() as s:
        s['atlerts_pending'] = GMAIL
    r = answer(c, True)
    assert r.status_code in (302, 401)
    assert A.profile_service.username_for_atlerts_email(GMAIL) is None


def test_one_address_opens_one_account(world, monkeypatch):
    A.profile_service.set_atlerts_email('bob.corporate', GMAIL)
    c = A.app.test_client()
    login(c)
    with c.session_transaction() as s:
        s['atlerts_pending'] = GMAIL
    r = answer(c, True)
    assert r.status_code == 409
    assert A.profile_service.get_atlerts_email(LAURA) == ''


def test_nor_somebody_elses_own_address(world):
    c = A.app.test_client()
    login(c)
    with c.session_transaction() as s:
        s['atlerts_pending'] = 'bob@atlasseniorliving.com'
    assert answer(c, True).status_code == 409


def test_an_accounts_own_address_wins_over_a_link(world, monkeypatch):
    """Checked first, so a link can never take over somebody's real address."""
    A.profile_service.set_atlerts_email(LAURA, 'bob@atlasseniorliving.com')
    atlerts_says(monkeypatch, 'bob@atlasseniorliving.com')
    c = A.app.test_client()
    sso(c)
    assert signed_in_as(c) == 'bob.corporate'


def test_it_is_matched_whatever_the_case(world, monkeypatch):
    A.profile_service.set_atlerts_email(LAURA, GMAIL)
    atlerts_says(monkeypatch, 'LauraBlakeman11@Gmail.com')
    c = A.app.test_client()
    sso(c)
    assert signed_in_as(c) == LAURA


# ------------------------------------------------------- the admin's side

def admin_client():
    c = A.app.test_client()
    with c.session_transaction() as s:
        s.update(user='admin', role='admin', display_name='Administrator')
    return c


def test_people_shows_it(world):
    A.profile_service.set_atlerts_email(LAURA, GMAIL)
    people = admin_client().get('/api/people', headers=HEADERS).get_json()['people']
    laura = next(p for p in people if p['username'] == LAURA)
    bob = next(p for p in people if p['username'] == 'bob.corporate')
    assert laura['atlerts_email'] == GMAIL
    assert bob['atlerts_email'] == ''


def test_an_admin_can_unlink_it(world, monkeypatch):
    A.profile_service.set_atlerts_email(LAURA, GMAIL)
    r = admin_client().delete(f'/api/people/{LAURA}/atlerts-link', headers=HEADERS)
    assert r.status_code == 200
    assert A.profile_service.get_atlerts_email(LAURA) == ''
    atlerts_says(monkeypatch, GMAIL)
    assert sso(A.app.test_client()).headers['Location'].endswith('/login')


def test_nobody_else_can(world):
    A.profile_service.set_atlerts_email(LAURA, GMAIL)
    c = A.app.test_client()
    login(c, 'bob.corporate')
    r = c.delete(f'/api/people/{LAURA}/atlerts-link', headers=HEADERS)
    assert r.status_code == 403
    assert A.profile_service.get_atlerts_email(LAURA) == GMAIL


def test_an_address_stored_with_capitals_still_matches(world, monkeypatch):
    """Written lowercase by the app, but profiles.json is a file somebody can
    open and fix by hand. A capital typed there must not quietly break it."""
    A.profile_service.profiles.setdefault(LAURA, {})['atlerts_email'] = 'LauraBlakeman11@Gmail.com'
    A.profile_service._save()
    atlerts_says(monkeypatch, GMAIL)
    c = A.app.test_client()
    sso(c)
    assert signed_in_as(c) == LAURA


# ------------------------------------------------ what the sign-in page says

def test_the_sign_in_page_says_why_they_are_there(world, monkeypatch):
    """People with no Excellence access see the shortcut in Atlerts too. They
    landed on a plain sign-in screen asking for a password they never had,
    and tried again. The page now names the address and says what to do —
    in both of the cases it cannot tell apart."""
    atlerts_says(monkeypatch, GMAIL)
    c = A.app.test_client()
    sso(c)
    page = c.get('/login').get_data(as_text=True)
    assert 'id="atlertsNoAccount"' in page, 'no explanation on the sign-in page'
    assert f"couldn't find an Excellence account for {GMAIL}" in page.replace('&#39;', "'")
    assert "sign in below and we'll link it" in page.replace('&#39;', "'"), \
        'nothing for the person who does have an account'
    assert 'given by your administrator' in page, 'nothing for the person who does not'


def test_and_says_nothing_otherwise(world):
    page = A.app.test_client().get('/login').get_data(as_text=True)
    assert 'id="atlertsNoAccount"' not in page


def test_nor_once_they_have_signed_out(world, monkeypatch):
    """The pending address lives in the session, so signing out takes the
    note with it. (After Not me they are signed in, and /login sends a
    signed-in person straight to the app, so there is no page to check.)"""
    atlerts_says(monkeypatch, GMAIL)
    c = A.app.test_client()
    sso(c); login(c); answer(c, False)
    c.get('/logout')
    assert 'id="atlertsNoAccount"' not in c.get('/login').get_data(as_text=True)


def test_the_address_is_printed_as_text(world, monkeypatch):
    """It comes from another app."""
    atlerts_says(monkeypatch, '<script>alert(1)</script>@x.com')
    c = A.app.test_client()
    sso(c)
    page = c.get('/login').get_data(as_text=True)
    assert '<script>alert(1)</script>' not in page
    assert '&lt;script&gt;' in page


def test_a_link_cannot_put_words_on_the_page(world):
    """Read from the session Atlerts filled, never from the URL."""
    page = A.app.test_client().get(
        '/login?atlerts_pending=you-have-been-hacked@x.com').get_data(as_text=True)
    assert 'you-have-been-hacked' not in page
