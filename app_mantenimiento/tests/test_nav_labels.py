"""
What the Communities section is called, per account.

A regional moves between many, so a list is what they want. An Executive
Director only ever reaches their own, and "Communities" reads like a directory
they are being kept out of.

The count decides the plural rather than the role, because an ED can stand in
for a neighbouring community.

Run locally, never on the server.
"""

import os
import re
import sys

import pytest

_APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

import app as A  # noqa: E402

_FAKE_USERS = ("smoke.nav",)


def teardown_module(module):
    for u in _FAKE_USERS:
        try:
            A.presence_service.forget(u)
        except Exception:
            pass


def _sidebar_label(html):
    """The text of the Communities entry as it actually renders."""
    m = re.search(r'data-view="communities"[^>]*>.*?<span>(.*?)</span>', html, re.S)
    return m.group(1).strip() if m else None


def _dashboard_as(**session_values):
    c = A.app.test_client()
    with c.session_transaction() as s:
        s.update(user="smoke.nav", display_name="smoke.nav", **session_values)
    r = c.get("/dashboard")
    assert r.status_code == 200, r.status_code
    return r.get_data(as_text=True)


def _communities(n):
    comms = A.all_communities()
    if len(comms) < n:
        pytest.skip("needs at least %d communities in the roster" % n)
    return comms[:n]


def test_an_ed_with_one_community_sees_my_community():
    (mine,) = _communities(1)
    html = _dashboard_as(role="staff", community=mine, communities=[mine],
                         region_id=None)
    assert _sidebar_label(html) == "My Community"


def test_an_ed_standing_in_for_a_neighbour_sees_the_plural():
    """Telling someone who covers two that they have "My Community" is a lie."""
    both = _communities(2)
    html = _dashboard_as(role="staff", community=both[0], communities=both,
                         region_id=None)
    assert _sidebar_label(html) == "My Communities"


def test_a_regional_still_sees_communities():
    html = _dashboard_as(role="regional", community=None, region_id=None)
    assert _sidebar_label(html) == "Communities"


def test_an_admin_still_sees_communities():
    html = _dashboard_as(role="admin", community=None, region_id=None)
    assert _sidebar_label(html) == "Communities"


def test_the_heading_is_told_the_same_thing_as_the_menu():
    """Menu and page heading read from one value, so they cannot disagree."""
    (mine,) = _communities(1)
    html = _dashboard_as(role="staff", community=mine, communities=[mine],
                         region_id=None)
    block = re.search(r'id="navCommunityData"[^>]*>(.*?)</script>', html, re.S)
    assert block, "the heading has nothing to read"
    assert "My Community" in block.group(1)
    assert _sidebar_label(html) in block.group(1)


def test_the_label_falls_back_when_a_session_has_no_community_yet():
    """A half-built session must not render an empty menu entry."""
    html = _dashboard_as(role="staff", community=None, region_id=None)
    assert _sidebar_label(html) == "Communities"
