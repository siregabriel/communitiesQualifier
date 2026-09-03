"""
An issue raised for the leadership side, that the community does not see.

Wyman asked whether he could record something at a community without walking a
whole survey, and without it landing on the Executive Director. The first half
already worked — the server has always accepted a raised item from a regional;
the button was simply never shown to anyone who could run visits. The second
half is this: a visibility on the item.

The reason it is defensible here and would not be on a visit finding is that a
raised item never touches a score. Nothing is hidden that moves a number the
community is measured by.

What has to hold is one sentence: an Executive Director must not be able to
reach one, by any route. Listing, opening by id, commenting, closing, or an
administrator previewing as them. A leak here is not a cosmetic bug — somebody
wrote it believing the community would not read it.

Run locally, never on the server.
"""

import os
import sys
import tempfile

import pytest

_APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

import app as A  # noqa: E402
from services.raised_item_service import RaisedItemService  # noqa: E402

HDR = {"Origin": "http://localhost", "Referer": "http://localhost/"}


@pytest.fixture
def svc():
    return RaisedItemService(os.path.join(tempfile.mkdtemp(), "items.json"))


# ------------------------------------------------------------- the service

def test_an_item_is_visible_to_the_community_by_default(svc):
    item = svc.create("Kelley Place", "Furniture is worn", "jazmyn", "Jazmyn")
    assert item["visibility"] == "community"
    assert not svc.is_internal(item)


def test_one_raised_internally_says_so(svc):
    item = svc.create("Kelley Place", "Watch this ED", "wyman", "Wyman",
                      visibility="internal")
    assert item["visibility"] == "internal"
    assert svc.is_internal(item)


def test_an_item_written_before_any_of_this_stays_as_visible_as_it_was(svc):
    """No visibility recorded is not the same as hidden."""
    svc.create("Kelley Place", "Old one", "jazmyn", "Jazmyn")
    svc.items[0].pop("visibility")
    svc.save_to_file()
    assert not svc.is_internal(svc.items[0])
    assert len(svc.for_communities(["Kelley Place"])) == 1


def test_the_listing_leaves_internal_out_unless_asked(svc):
    svc.create("Kelley Place", "Theirs", "jazmyn", "Jazmyn")
    svc.create("Kelley Place", "Ours", "wyman", "Wyman", visibility="internal")

    seen = svc.for_communities(["Kelley Place"])
    assert [i["text"] for i in seen] == ["Theirs"], "the community read the internal one"

    both = svc.for_communities(["Kelley Place"], include_internal=True)
    assert len(both) == 2


def test_a_caller_that_forgets_to_think_about_it_leaks_nothing(svc):
    """include_internal defaults to False on purpose.

    The mistake this prevents is the quiet one: somebody adds a route, calls
    for_communities, and never considers visibility at all.
    """
    svc.create("Kelley Place", "Ours", "wyman", "Wyman", visibility="internal")
    assert svc.for_communities(["Kelley Place"]) == []


# ------------------------------------------------------ who may see one

def _client(user, role, community=None, region_id=None):
    c = A.app.test_client()
    with c.session_transaction() as s:
        s.update(user=user, role=role, community=community,
                 communities=[community] if community else [],
                 region_id=region_id, display_name=user)
    return c


def _community_and_region():
    comms = A.all_communities()
    if not comms:
        pytest.skip("needs a community")
    community = comms[0]
    region = next((r for r in A.region_service.get_all_regions()
                   if community in (r.get("communities") or [])), None)
    if not region:
        pytest.skip("that community is not in a region")
    return community, region["id"]


@pytest.fixture
def internal_item():
    """A real internal item, cleaned up afterwards."""
    community, region_id = _community_and_region()
    cat = A.raised_category_service.active()[0]["id"]
    item = A.raised_item_service.create(
        community, "smoke: internal only", "smoke.internal.reg", "Reg",
        category=cat, visibility="internal")
    yield item, community, region_id
    A.raised_item_service.items = [i for i in A.raised_item_service.items
                                   if i.get("id") != item["id"]]
    A.raised_item_service.save_to_file()


def test_an_executive_director_does_not_see_it_in_their_list(internal_item):
    item, community, _ = internal_item
    d = _client("smoke.internal.ed", "staff", community=community) \
        .get("/api/raised-items").get_json()
    assert all(i["id"] != item["id"] for i in d["items"]), \
        "the community was shown an item raised about them"


def test_a_regional_does_see_it(internal_item):
    item, community, region_id = internal_item
    d = _client("smoke.internal.reg2", "regional", region_id=region_id) \
        .get("/api/raised-items").get_json()
    assert any(i["id"] == item["id"] for i in d["items"]), \
        "the side it was raised for cannot read it either"


def test_an_executive_director_cannot_open_it_by_id(internal_item):
    """Guessing an id must answer the same as an id that does not exist.

    Telling the two apart tells them an internal item exists, which is the one
    thing raising it internally was meant to avoid.
    """
    item, community, _ = internal_item
    c = _client("smoke.internal.ed", "staff", community=community)
    r = c.post(f"/api/raised-items/{item['id']}/comment",
               json={"text": "what is this?"}, headers=HDR)
    assert r.status_code == 404
    body = r.get_json() or {}
    assert "not found" in (body.get("message") or "").lower(), \
        f"that 404 has to come from the rule, not from a mistyped URL ({body})"


def test_an_executive_director_cannot_close_it(internal_item):
    item, community, _ = internal_item
    r = _client("smoke.internal.ed", "staff", community=community) \
        .post(f"/api/raised-items/{item['id']}/resolve",
              json={"resolved": True}, headers=HDR)
    assert r.status_code == 404


def test_a_preview_shows_what_that_person_really_sees(internal_item):
    """An administrator looking as an Executive Director.

    current_role() answers 'staff' during a preview, so this follows from that
    — but it is the case where a leak would be found last, because the person
    looking has every right to the data and would not notice it was wrong.
    """
    item, community, _ = internal_item
    c = A.app.test_client()
    with c.session_transaction() as s:
        s.update(user="admin", role="admin", community=None, region_id=None,
                 display_name="admin",
                 view_as={"communities": [community], "label": "An ED"})
    d = c.get("/api/raised-items").get_json()
    assert all(i["id"] != item["id"] for i in d["items"]), \
        "the preview handed an administrator's view to a community's screen"


# ------------------------------------------------------ and by email

def test_an_internal_item_is_not_emailed_to_the_community(monkeypatch):
    """The screens hide it; the address lists are somebody else's to fill in.

    Nothing stops an Executive Director's address being put against a
    department — Greg fills those boxes, and the person who ticks "keep this
    on our side" is not the person who filled them. If it still arrived in
    their inbox the feature would be lying.
    """
    sent = {}
    monkeypatch.setattr(A.email_service, "enabled", True)
    monkeypatch.setattr(A.email_service, "send_raised_item",
                        lambda to, item: sent.update(to=list(to)))
    monkeypatch.setattr(A, "region_leader_emails", lambda c: ["marissa@atlas.com"])
    monkeypatch.setattr(A, "community_account_emails", lambda c: ["jazmyn@atlas.com"])
    # The department list has the ED's address on it, which is allowed.
    monkeypatch.setattr(A.raised_category_service, "recipients_for",
                        lambda cid: ["michael@atlas.com", "JAZMYN@atlas.com"])

    A.notify_raised_item({"community": "Kelley Place", "category": "maintenance",
                          "text": "not theirs to answer for",
                          "visibility": "internal"})
    assert sent.get("to") == ["marissa@atlas.com", "michael@atlas.com"], \
        "the community was emailed an item raised behind them"


def test_an_ordinary_item_still_reaches_them(monkeypatch):
    """The filter is for internal items only — it must not quietly narrow
    everything else."""
    sent = {}
    monkeypatch.setattr(A.email_service, "enabled", True)
    monkeypatch.setattr(A.email_service, "send_raised_item",
                        lambda to, item: sent.update(to=list(to)))
    monkeypatch.setattr(A, "region_leader_emails", lambda c: ["marissa@atlas.com"])
    monkeypatch.setattr(A, "community_account_emails", lambda c: ["jazmyn@atlas.com"])
    monkeypatch.setattr(A.raised_category_service, "recipients_for",
                        lambda cid: ["jazmyn@atlas.com"])

    A.notify_raised_item({"community": "Kelley Place", "category": "maintenance",
                          "text": "furniture", "visibility": "community"})
    assert sent.get("to") == ["marissa@atlas.com", "jazmyn@atlas.com"]


# --------------------------------------------------- who may raise one

def test_a_community_account_cannot_raise_one_internally():
    """It would be hiding something from itself, and from its own regional."""
    community, _ = _community_and_region()
    cat = A.raised_category_service.active()[0]["id"]
    c = _client("smoke.internal.ed", "staff", community=community)
    r = c.post("/api/raised-items",
               json={"community": community, "text": "smoke: tried to hide",
                     "category": cat, "visibility": "internal"}, headers=HDR)
    try:
        assert r.status_code == 201
        assert r.get_json()["item"]["visibility"] == "community", \
            "a community account hid an item from itself"
    finally:
        got = (r.get_json() or {}).get("item") or {}
        A.raised_item_service.items = [i for i in A.raised_item_service.items
                                       if i.get("id") != got.get("id")]
        A.raised_item_service.save_to_file()


def test_a_regional_can():
    community, region_id = _community_and_region()
    cat = A.raised_category_service.active()[0]["id"]
    c = _client("smoke.internal.reg3", "regional", region_id=region_id)
    r = c.post("/api/raised-items",
               json={"community": community, "text": "smoke: ours",
                     "category": cat, "visibility": "internal"}, headers=HDR)
    try:
        assert r.status_code == 201
        assert r.get_json()["item"]["visibility"] == "internal"
    finally:
        got = (r.get_json() or {}).get("item") or {}
        A.raised_item_service.items = [i for i in A.raised_item_service.items
                                       if i.get("id") != got.get("id")]
        A.raised_item_service.save_to_file()


def test_who_can_see_internal_at_all():
    with A.app.test_request_context("/"):
        from flask import session
        session.update(user="x", role="staff", community="c")
        assert A.can_see_internal() is False
        session["role"] = "regional"
        assert A.can_see_internal() is True
        session["role"] = "corporate"
        assert A.can_see_internal() is True
        session["role"] = "admin"
        assert A.can_see_internal() is True
        session["view_as"] = {"communities": ["c"], "label": "An ED"}
        assert A.can_see_internal() is False, "a preview must not widen it"
