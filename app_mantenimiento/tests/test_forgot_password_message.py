"""
"Forgot your password?" says who gets the request, and the same thing every time.

Excellence has no self-service reset: the request emails the administrators,
who reset it by hand. The old reply, "your administrator has been notified",
left directors asking who that was. The new one names the Atlas Excellence
administrators and points to the Atlerts shortcut, which needs no password.

What must not change: the reply is identical whether or not the username
exists, so the form can never be used to find out which accounts are real.

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
def quiet(monkeypatch):
    """No emails, no activity log, no rate limit carried between tests."""
    sent = []
    monkeypatch.setattr(A.email_service, 'send_password_reset_request',
                        lambda *args, **kwargs: sent.append(args))
    monkeypatch.setattr(A.activity_service, 'log', lambda *args, **kwargs: None)
    monkeypatch.setattr(A.settings_service, 'get_email_settings',
                        lambda: {'admin_notify': ['admin@example.com']})
    A._forgot_attempts.clear()
    return sent


def _ask(username):
    return A.app.test_client().post('/api/forgot-password', json={'username': username})


def test_existing_and_unknown_accounts_get_the_same_reply(quiet, monkeypatch):
    monkeypatch.setattr(A, 'resolve_account_context',
                        lambda u: {'exists': u == 'real.user', 'display_name': 'Real User', 'context': ''})
    real = _ask('real.user')
    fake = _ask('nobody.here')
    assert real.status_code == fake.status_code == 200
    assert real.get_json() == fake.get_json()
    # Only the real account reaches the administrators.
    assert len(quiet) == 1


def test_the_reply_says_who_and_mentions_atlerts(quiet, monkeypatch):
    monkeypatch.setattr(A, 'resolve_account_context', lambda u: {'exists': False})
    message = _ask('anyone').get_json()['message']
    assert message == A.FORGOT_PASSWORD_MESSAGE
    assert 'Atlas Excellence administrators' in message
    assert 'Atlerts' in message
    assert 'your administrator has been notified' not in message
