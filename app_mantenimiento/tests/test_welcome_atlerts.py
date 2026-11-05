"""
The welcome email tells people about the Atlerts shortcut.

Almost everybody at Atlas has Atlerts, and its Excellence shortcut signs them
in with no password. The welcome email only explained the password, so new
people typed a temporary one, made their own, and forgot it — while the
one-tap way in sat on their phone. Staff accounts (a community's chef, its
maintenance lead) made this worth fixing: many of them will only ever come in
through Atlerts.

The section also explains linking, for the many who use a personal email in
Atlerts: sign in once, tap Link, and from then on the shortcut works.

Run locally, never on the server.
"""

import os
import sys

_APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

import app as A  # noqa: E402
from services.email_service import EmailService  # noqa: E402

IMAGE = os.path.join(_APP_DIR, 'static', 'email-atlerts-shortcut.jpg')


def capture(base_url='https://standards.atlasseniorliving.net'):
    svc = EmailService(mail_from='excellence@example.com', region='us-east-1', app_base_url=base_url)
    sent = []
    svc._send = lambda to, subject, html_body, text: sent.append(
        {'to': to, 'subject': subject, 'html': html_body, 'text': text}) or (True, 'ok')
    return svc, sent


def test_the_welcome_explains_the_atlerts_shortcut():
    svc, sent = capture()
    svc.send_welcome('cait@thegoldtonatvenice.com', 'Cait', 'cait.chef', 'k7-Ravel-42',
                     'Staff · The Goldton at Venice')
    h = sent[0]['html']
    assert 'The easiest way in: Atlerts' in h
    assert 'Apps &amp; Shortcuts' in h and 'Excellence' in h


def test_and_how_to_link_a_different_email():
    svc, sent = capture()
    svc.send_welcome('cait@thegoldtonatvenice.com', 'Cait', 'cait.chef', 'pw', None)
    h = sent[0]['html']
    assert 'Use a different email in Atlerts?' in h
    assert '<b>Link</b>' in h


def test_the_login_details_still_come_first():
    """The section is extra; the username and password are what the email is for."""
    svc, sent = capture()
    svc.send_welcome('a@b.com', 'Cait', 'cait.chef', 'k7-Ravel-42', None)
    h = sent[0]['html']
    assert h.index('k7-Ravel-42') < h.index('The easiest way in')


def test_the_picture_is_the_hosted_still():
    svc, sent = capture()
    svc.send_welcome('a@b.com', 'Cait', 'cait.chef', 'pw', None)
    h = sent[0]['html']
    assert "src='https://standards.atlasseniorliving.net/static/email-atlerts-shortcut.jpg'" in h
    assert 'alt=' in h, 'no alt text for the many clients that block pictures'


def test_no_server_address_no_broken_picture():
    svc, sent = capture(base_url=None)
    svc.send_welcome('a@b.com', 'Cait', 'cait.chef', 'pw', None)
    h = sent[0]['html']
    assert '<img' not in h.split('The easiest way in')[1]
    assert 'The easiest way in: Atlerts' in h, 'the words still go out without the picture'


def test_the_plain_text_part_says_it_too():
    svc, sent = capture()
    svc.send_welcome('a@b.com', 'Cait', 'cait.chef', 'pw', None)
    t = sent[0]['text']
    assert 'Atlerts' in t and 'tap Excellence' in t and 'tap Link' in t


def test_the_picture_exists_is_small_and_is_served():
    """A missing file is a broken image in every welcome email from then on."""
    assert os.path.exists(IMAGE)
    size = os.path.getsize(IMAGE)
    assert 0 < size < 200_000, f'{size} bytes is too heavy for an email picture'
    with open(IMAGE, 'rb') as f:
        assert f.read(3) == b'\xff\xd8\xff', 'not a JPEG'
    r = A.app.test_client().get('/static/email-atlerts-shortcut.jpg')
    assert r.status_code == 200


def test_a_password_reset_mentions_it_in_one_line():
    svc, sent = capture()
    svc.send_password_reset('a@b.com', 'Cait', 'cait.chef', 'pw')
    assert 'skip passwords entirely' in sent[0]['html']
    assert 'skip passwords entirely' in sent[0]['text']
    assert 'The easiest way in' not in sent[0]['html'], 'the reset email is not the place for the full section'
