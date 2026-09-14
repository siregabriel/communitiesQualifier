"""
Which device somebody signed in from, on the line that records the sign-in.

Device problems arrive as "on my phone it looks like this", and the first
question back is always which phone. That question is answerable from the
activity line, which already had the answer in the request and threw it away.

Two layers, on purpose. The line says the platform — iOS, Android, Desktop —
because that is how the app ships and how people here talk about it. The meta
keeps the exact device, because an iPad is a different screen from an iPhone
and the reason this field exists is that layout problems arrive as "on my
phone it looks like this".

Desktop is the catch-all rather than a fourth "unknown": somebody at a
computer is the ordinary case, and a field that says "unknown" for the
ordinary case is a field people learn to skip.

That catch-all is also the thing this file watches hardest. curl, a bot and a
monitoring probe all land in Desktop too, so a scripted sign-in reads like a
person at a desk; the raw User-Agent is kept for exactly those, which is what
makes the shortcut honest.

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
# a desktop if the desktop case is settled first.
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
    """The exact device, which is what the meta records."""
    with A.app.test_request_context('/', headers={'User-Agent': ua}):
        return A._client_device()


def platform(ua):
    """The platform, which is what the line says."""
    with A.app.test_request_context('/', headers={'User-Agent': ua}):
        return A._client_platform()


# ---------------------------------------------------------- what it reads

def test_the_two_platforms_that_prompted_this():
    """Atlerts ships on both, and the log said neither."""
    assert platform(IPHONE) == 'iOS'
    assert platform(ANDROID) == 'Android'
    assert read(IPHONE) == 'iPhone'
    assert read(ANDROID) == 'Android'


def test_an_ipad_is_ios_on_the_line_and_an_ipad_in_the_record():
    """One word apart in the sentence, two different screens in practice."""
    assert platform(IPAD) == 'iOS'
    assert read(IPAD) == 'iPad'
    assert platform(IPHONE) == platform(IPAD) == 'iOS'
    assert read(IPHONE) != read(IPAD), 'the distinction is lost where it matters'


def test_an_ipad_is_not_a_desktop():
    """iPadOS puts "Macintosh" in its User-Agent.

    Tested against the Mac in the same breath: the iPad case only works
    because it is settled first, and checking the iPad alone passes with that
    order reversed.
    """
    assert read(IPAD) == 'iPad'
    assert read(MAC) == 'Desktop'


def test_a_tablet_is_told_from_a_phone():
    assert read(ANDROID) == 'Android'
    assert read(ANDROID_TABLET) == 'Android tablet'


def test_the_browser_is_not_part_of_the_answer():
    """The app is native on both phones, so the browser is not a question.

    Two browsers on the same device have to give the same answer, or the
    field has quietly gone back to being about software.
    """
    assert read(IPHONE) == read(IPHONE_CHROME) == 'iPhone'
    assert platform(IPHONE) == platform(IPHONE_CHROME) == 'iOS'
    assert read(MAC) == read(WINDOWS_EDGE) == 'Desktop'
    for ua in (IPHONE, ANDROID, MAC, WINDOWS_EDGE):
        assert '·' not in read(ua) and 'Safari' not in read(ua)


# -------------------------------------------------------- the catch-all

def test_everything_else_is_a_desktop():
    for ua in (MAC, WINDOWS_EDGE,
               'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/126.0'):
        assert read(ua) == 'Desktop'


def test_there_is_no_fifth_answer():
    """Anything unrecognised is a desktop, including nothing at all."""
    for ua in ('curl/8.4.0', '', 'x', 'PostmanRuntime/7.37.0'):
        assert read(ua) == 'Desktop'


def test_something_that_is_not_a_browser_keeps_its_own_words():
    """The cost of the catch-all, paid for.

    curl reads as Desktop on the line, the same as a person at a computer. On
    a sign-in log that is the one confusion worth being able to undo later, so
    the header is kept verbatim for these and for nothing else.
    """
    for ua in ('curl/8.4.0', 'PostmanRuntime/7.37.0', ''):
        with A.app.test_request_context('/', headers={'User-Agent': ua}):
            meta = A._login_meta()
            assert meta['device'] == 'Desktop'
            assert meta.get('ua') == ua, 'the raw header was not kept'

    for ua in (IPHONE, MAC, ANDROID):
        with A.app.test_request_context('/', headers={'User-Agent': ua}):
            assert 'ua' not in A._login_meta(), \
                'a recognised browser does not need its header recording'


def test_a_very_long_header_is_cut():
    """It is a value the caller controls; it does not get to be unbounded."""
    with A.app.test_request_context('/', headers={'User-Agent': 'z' * 5000}):
        assert len(A._login_meta()['ua']) <= 200


# ------------------------------------------------------------ the sentence

def test_the_sentence_says_the_platform_not_the_hardware():
    """iOS, because that is how the app ships and how people here talk.

    The iPad proves it is the platform and not just a renamed iPhone: both
    read the same on the line.
    """
    with A.app.test_request_context('/', headers={'User-Agent': IPHONE}):
        assert A._signed_in_detail() == 'Signed in on iOS'
        assert A._signed_in_detail('Atlerts') == 'Signed in from Atlerts on iOS'
    with A.app.test_request_context('/', headers={'User-Agent': IPAD}):
        assert A._signed_in_detail('Atlerts') == 'Signed in from Atlerts on iOS'
    with A.app.test_request_context('/', headers={'User-Agent': ANDROID_TABLET}):
        assert A._signed_in_detail('Atlerts') == 'Signed in from Atlerts on Android'
    with A.app.test_request_context('/', headers={'User-Agent': 'curl/8.4.0'}):
        assert A._signed_in_detail() == 'Signed in on Desktop'
        assert A._signed_in_detail('Atlerts') == 'Signed in from Atlerts on Desktop'


def test_the_meta_carries_it_too():
    """The sentence is for reading; the meta is for filtering later."""
    with A.app.test_request_context('/', headers={'User-Agent': ANDROID}):
        meta = A._login_meta()
        assert meta['platform'] == 'Android'
        assert meta['device'] == 'Android'
        assert 'ip' in meta
    with A.app.test_request_context('/', headers={'User-Agent': ANDROID_TABLET}):
        meta = A._login_meta()
        assert meta['platform'] == 'Android', 'the line groups them'
        assert meta['device'] == 'Android tablet', 'the record does not' 


def test_extra_meta_is_kept():
    with A.app.test_request_context('/', headers={'User-Agent': IPHONE}):
        assert A._login_meta(via='atlerts')['via'] == 'atlerts'


# ------------------------------------------- both routes use the same words

def test_neither_sign_in_route_writes_its_own_sentence():
    """Two routes describing one event differently is how they drift.

    They also both record the device: the ordinary sign-in is the one most
    people use, and it was the one with nothing on it.
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
    assert seen['detail'] == 'Signed in on iOS'
    assert seen['meta']['platform'] == 'iOS'
    assert seen['meta']['device'] == 'iPhone'
