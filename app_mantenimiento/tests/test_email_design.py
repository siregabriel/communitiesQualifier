"""
The emails in the Precision design (Nov 2026).

Gabriel approved the redesign from a side-by-side preview: one frame for
every email (the leadership report had its own copy), the navy band with the
engineering grid (Outlook shows it plain), "ATLAS EXCELLENCE" over the title
instead of the old "COMMUNITIES STANDARDS", each finding a card with a rail
in the app's answer colour, section titles as mono eyebrows, priorities as
tags. Nothing here sends: the transport is replaced.
"""

import os
import re
import sys

_APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

from services.email_service import EmailService  # noqa: E402

SUB = {'community': 'Kelley Place, Enterprise', 'inspector_name': 'Greg', 'submitted_at': '2026-11-07T10:00:00',
       'responses': [{'question_text': 'Lobby clean', 'condition': 'Pass'},
                     {'question_text': 'Cooler seals', 'condition': 'Fail', 'description': 'Gasket torn'},
                     {'question_text': 'Dining room', 'condition': 'Not checked', 'description': 'Closed'}],
       'action_items': [{'text': 'Replace sofa', 'priority': 'high'}]}


def _svc():
    svc = EmailService(mail_from='x@y.z', app_base_url='https://excellence.example')
    sent = []
    svc._send = lambda to, subject, html_body, text_body, **k: sent.append(html_body) or (True, 'ok')
    return svc, sent


def test_one_frame_for_every_email():
    svc, sent = _svc()
    _, report, _ = svc._build(SUB)
    svc.send_community_findings(['ed@x.com'], SUB['community'], 'Greg', '2026-11-07',
                                [SUB['responses'][1]], SUB['action_items'], {})
    svc.send_welcome('a@b.c', 'Lauren', 'lauren', 'Temp-1', 'Regional')
    for body in (report, *sent):
        assert '#003366' in body and 'linear-gradient' in body, 'the navy band with its grid'
        assert 'border-bottom:3px solid #00bfff' in body, 'and the electric rule'
        assert 'ATLAS EXCELLENCE' in body.upper() and 'COMMUNITIES STANDARDS' not in body.upper()
    assert 'Visit report' in report, 'the leadership report has its own eyebrow in the same frame'


def test_findings_are_cards_in_the_answer_colours():
    svc, _ = _svc()
    _, report, _ = svc._build(SUB)
    assert 'border-left:3px solid #ea366e' in report, 'a failed standard has the Fail rail'
    assert 'border-left:3px solid #5b6b85' in report, 'not checked, the grey one'
    assert 'border-left:3px solid #ffa500' in report, 'an action item, amber'
    assert '[HIGH]' not in report and '>high</span>' in report, 'the priority is a tag'


def test_no_old_navy_or_unreadable_amber_left():
    src = open(os.path.join(_APP_DIR, 'services', 'email_service.py'), encoding='utf-8').read()
    for old in ('#00285c', '#b58b00', '#d97706', '#9ca3af'):
        assert old not in src.lower(), f'{old} is still in the emails'
