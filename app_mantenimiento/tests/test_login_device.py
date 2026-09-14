"""
Which phone somebody signed in from, on the line that records the sign-in.

Device problems arrive as "on my phone it looks like this", and the first
question back is always which phone. That question is answerable from the
activity line, which already knew the answer and threw it away.

Read off the User-Agent, which is whatever the client says it is. So the point
of most of this file is the quiet part: when the header says nothing we
recognise, the sign-in is recorded exactly as it always was, with no device
at all. A log that is confidently wrong is worse than one that says less.

Run locally, never on the server.
"""

import os
import sys

_APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

import app as A  # noqa: E402

IPHONE = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) "
          "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1")
IPHONE_CHROME = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) "
                 "AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/126.0 Mobile/15E148 Safari/604.1")
# iPadOS says "Macintosh". This is the one that quietly turns every iPad into
# a laptop if the tests are written from the desktop end first.
IPAD = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
        "(KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1")
ANDROID = ("Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 "
           "(KHTML, like Gecko) Chrome/126.0 Mobile Safari/537.36")
ANDROID_TABLET = ("Mozilla/5.0 (Linux; Android 14; SM-X200) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
MAC = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
       "(KHTML, like Gecko) Version/17.5 Safari/605.1.15")
WINDOWS_EDGE = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/126.0 Safari/537.36 Edg/126.0")


def read(ua):
    with A.app.test_request_context('/', headers={'User-Agent': ua}):
        return A._client_device()


# ---------------------------------------------------------- what it reads

def test_the_two_platforms_that_prompted_this():
    """Atlerts ships on both, and the log said neither."""
    assert read(IPHONE).startswith('iPhone')
    assert read(ANDROID).startswith('Android')


def test_an_ipad_is_not_a_mac():
    """iPadOS puts "Macintosh" in its User-Agent.

    Test the two together: the iPad case only works because it is checked
    before the Mac one, and a test that checks the Mac alone passes with that
    order reversed.
    """
    assert read(IPAD).startswith('iPad')
    assert read(MAC).startswith('Mac')


def test_a_tablet_is_told_from_a_phone():
    assert read(ANDROID) == 'Android · Chrome'
    assert read(ANDROID_TABLET) == 'Android tablet · Chrome'


def test_the_browser_is_the_specific_one():
    """Chrome on iOS contains "Safari"; Edge contains both Chrome and Safari.

    Whichever is checked last wins, so these read as Safari if the order is
    wrong — which looks entirely plausible and is wrong every time.
    """
    assert read(IPHONE_CHROME) == 'iPhone · Chrome'
    assert read(WINDOWS_EDGE) == 'Windows · Edge'
    assert read(IPHONE) == 'iPhone · Safari'


# ------------------------------------------------------ what it will not say

def test_nothing_recognisable_means_nothing_recorded():
    for ua in ('curl/8.4.0', '', 'x', 'PostmanRuntime/7.37.0'):
        assert read(ua) == '', f'{ua!r} was given a device it does not have'


def test_the_sentence_drops_the_device_rather_than_guessing():
    with A.app.test_request_context('/', headers={'User-Agent': 'curl/8.4.0'}):
        assert A._signed_in_detail() == 'Signed in'
        assert A._signed_in_detail('Atlerts') == 'Signed in from Atlerts', \
            'this is what the line has always said, and it is still true'


def test_the_sentence_carries_both_when_it_can():
    with A.app.test_request_context('/', headers={'User-Agent': IPHONE}):
        assert A._signed_in_detail() == 'Signed in on iPhone · Safari'
        assert A._signed_in_detail('Atlerts') == 'Signed in from Atlerts on iPhone · Safari'


def test_the_meta_carries_it_too():
    """The sentence is for reading; the meta is for filtering later."""
    with A.app.test_request_context('/', headers={'User-Agent': ANDROID}):
        assert A._login_meta()['device'] == 'Android · Chrome'
        assert 'ip' in A._login_meta()
    with A.app.test_request_context('/', headers={'User-Agent': 'curl/8.4.0'}):
        assert 'device' not in A._login_meta(), 'an empty device is not a device'


def test_extra_meta_is_kept():
    with A.app.test_request_context('/', headers={'User-Agent': IPHONE}):
        assert A._login_meta(via='atlerts')['via'] == 'atlerts'


# ------------------------------------------------- both routes use the same

def test_neither_sign_in_route_writes_its_own_sentence():
    """Two routes describing one event differently is how they drift.

    They also both have to record the device: the ordinary sign-in is the one
    most people use, and it was the one with nothing on it.
    """
    with open(os.path.join(_APP_DIR, 'app.py'), encoding='utf-8') as f:
        src = f.read()
    assert src.count("_signed_in_detail(") >= 3, \
        "a sign-in route is still writing its own wording"
    assert "'Signed in'," not in src and '"Signed in",' not in src, \
        'a literal sign-in sentence is still being logged somewhere'
    assert src.count('meta=_login_meta(') == 2, \
        'both sign-in routes should record where from and on what'


def test_a_real_sign_in_records_the_device(monkeypatch):
    """End to end through the route people actually use."""
    seen = {}
    monkeypatch.setattr(A.activity_service, 'log',
                        lambda user, kind, detail, meta=None: seen.update(
                            user=user, kind=kind, detail=detail, meta=meta or {}))
    monkeypatch.setattr(A, 'authenticate_user',
                        lambda u, p: (True, {'role': 'staff', 'community': 'C',
                                             'region_id': None, 'communities': ['C'],
                                             'display_name': 'Somebody'}))
    monkeypatch.setattr(A.presence_service, 'record_login', lambda u: None)

    c = A.app.test_client()
    r = c.post('/api/login', json={'username': 'smoke.device', 'password': 'x'},
               headers={'Origin': 'http://localhost', 'Referer': 'http://localhost/',
                        'User-Agent': IPHONE})
    assert r.status_code == 200, r.get_data(as_text=True)[:200]
    assert seen.get('kind') == 'login'
    assert seen['detail'] == 'Signed in on iPhone · Safari'
    assert seen['meta']['device'] == 'iPhone · Safari'
