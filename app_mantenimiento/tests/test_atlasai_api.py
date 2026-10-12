"""
AtlasAI reads Excellence as the person asking — never more.

AtlasAI is the assistant inside Atlerts. When an admin asks it about visits,
findings or raised items, Atlerts calls /api/atlasai/query server to server
with the shared SSO secret and the admin's verified email. Excellence answers
with its own rules, as if that person had opened the dashboard.

What has to hold, in one sentence each:
- No secret, no data.
- No Excellence account, no data — and never a new account.
- An Executive Director sees their community; a regional sees their region;
  nobody sees a community outside their scope by naming it.
- Internal raised items stay internal.
- Nothing that names residents or carries free text (move-ins, comments,
  visit notes) leaves the server.
- The isolated session never becomes a cookie.

Everything here runs on fixtures. Run locally, never on the server.
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

SECRET = "test-shared-secret"

REGIONS = [
    {"id": "r1", "name": "Magnolia", "communities": ["Kelley Place", "Monark Grove"]},
    {"id": "r2", "name": "Coastal", "communities": ["Trussville Memory Care"]},
]

ACCOUNTS = {
    "ed@atlas.test": ("jazmyn", {"role": "staff", "community": "Kelley Place",
                                 "communities": ["Kelley Place"], "region_id": None,
                                 "display_name": "Jazmyn"}),
    "regional@atlas.test": ("wyman", {"role": "regional", "community": None,
                                      "region_id": "r1", "display_name": "Wyman"}),
}

VISITS = {
    "Kelley Place": [{
        "id": "s1", "community": "Kelley Place", "submitted_at": "2026-10-01T10:00:00",
        "username": "wyman", "inspector_name": "Wyman",
        "notes": "Resident in room 12 mentioned the smell",   # free text: must not leave
        "responses": [
            {"question_id": "q1", "question_text": "Lobby is clean", "condition": "Pass"},
            {"question_id": "q2", "question_text": "Kitchen is sanitary", "condition": "Fail",
             "comments": [{"text": "Mrs. Smith complained", "author": "Jazmyn"}]},
            {"question_id": "q3", "question_text": "Fire exits clear", "condition": "Fail",
             "addressed": True},
        ],
        "action_items": [{"text": "Replace hallway carpet", "resolved": False}],
    }],
    "Monark Grove": [],
    "Trussville Memory Care": [{
        "id": "s2", "community": "Trussville Memory Care", "submitted_at": "2026-09-01T10:00:00",
        "responses": [{"question_id": "q1", "question_text": "Lobby is clean", "condition": "Fail"}],
    }],
}


@pytest.fixture
def items():
    return RaisedItemService(os.path.join(tempfile.mkdtemp(), "items.json"))


@pytest.fixture(autouse=True)
def world(monkeypatch, items):
    monkeypatch.setattr(A, "ATLERTS_SSO_SECRET", SECRET)
    monkeypatch.setattr(A, "_atlerts_account_by_email",
                        lambda email: ACCOUNTS.get((email or "").strip().lower()))
    monkeypatch.setattr(A.region_service, "get_all_regions", lambda: REGIONS)
    monkeypatch.setattr(A.profile_service, "get_admin_extra", lambda u: False)
    monkeypatch.setattr(A.profile_service, "get_all_communities", lambda u: False)
    monkeypatch.setattr(A.inspection_service, "get_submissions_by_community",
                        lambda c: list(VISITS.get(c, [])))
    monkeypatch.setattr(A.settings_service, "get_visit_cadence_days", lambda: 90)
    monkeypatch.setattr(A.raised_category_service, "name_for", lambda c: "Building")
    monkeypatch.setattr(A, "raised_item_service", items)
    items.create("Kelley Place", "Front door sticks", "jazmyn", "Jazmyn")
    items.create("Kelley Place", "Watch this ED", "wyman", "Wyman", visibility="internal")
    items.create("Trussville Memory Care", "Roof leak", "x", "X")


def ask(tool, email, args=None, secret=SECRET):
    headers = {"X-Atlerts-Sso-Secret": secret} if secret is not None else {}
    return A.app.test_client().post("/api/atlasai/query", headers=headers,
                                    json={"tool": tool, "email": email, "args": args or {}})


# ---------------------------------------------------------------- the door

def test_no_secret_no_data():
    assert ask("overview", "ed@atlas.test", secret=None).status_code == 403


def test_wrong_secret_no_data():
    assert ask("overview", "ed@atlas.test", secret="guess").status_code == 403


def test_a_server_without_the_secret_answers_nobody(monkeypatch):
    monkeypatch.setattr(A, "ATLERTS_SSO_SECRET", "")
    assert ask("overview", "ed@atlas.test", secret="").status_code == 403


def test_no_account_here_means_nothing_and_no_new_account():
    r = ask("overview", "stranger@atlas.test")
    assert r.status_code == 200 and r.get_json() == {"status": "no_account"}


def test_unknown_tool():
    assert ask("delete_everything", "ed@atlas.test").status_code == 400


def test_the_isolated_session_never_becomes_a_cookie():
    r = ask("overview", "regional@atlas.test")
    assert r.status_code == 200
    assert "Set-Cookie" not in r.headers


# ---------------------------------------------------------------- the scope

def _names(r):
    return [c["community"] for c in r.get_json()["communities"]]


def test_an_executive_director_sees_their_community():
    assert _names(ask("overview", "ed@atlas.test")) == ["Kelley Place"]


def test_a_regional_sees_their_region_and_nothing_else():
    assert sorted(_names(ask("overview", "regional@atlas.test"))) == ["Kelley Place", "Monark Grove"]


def test_naming_a_community_outside_scope_finds_nothing():
    body = ask("visit", "regional@atlas.test", {"community": "Trussville"}).get_json()
    assert body.get("error") == "not_found" and body["candidates"] == []
    body = ask("visit", "ed@atlas.test", {"community": "Monark Grove"}).get_json()
    assert body.get("error") == "not_found"


def test_a_short_name_resolves_inside_scope():
    body = ask("visit", "regional@atlas.test", {"community": "kelley"}).get_json()
    assert body["community"] == "Kelley Place"


def test_raised_items_outside_scope_never_appear():
    body = ask("raised_items", "regional@atlas.test").get_json()
    assert {i["community"] for i in body["items"]} == {"Kelley Place"}


# ---------------------------------------------------------------- internal items

def test_an_executive_director_never_sees_an_internal_item():
    texts = [i["text"] for i in ask("raised_items", "ed@atlas.test").get_json()["items"]]
    assert "Front door sticks" in texts and "Watch this ED" not in texts


def test_a_regional_does():
    texts = [i["text"] for i in ask("raised_items", "regional@atlas.test").get_json()["items"]]
    assert "Watch this ED" in texts


# ---------------------------------------------------------------- what leaves

def test_the_visit_summary_matches_the_scores_the_dashboard_shows():
    body = ask("visit", "ed@atlas.test", {"community": "Kelley Place"}).get_json()
    assert body["passed"] == 1 and body["failed"] == 2 and body["fixed"] == 1
    assert body["visit_score"] == 33 and body["current_score"] == 67
    assert {"standard": "Kitchen is sanitary", "still_open": True} in body["failed_standards"]
    assert body["open_action_items"] == ["Replace hallway carpet"]


def test_no_free_text_or_resident_words_leave_the_server():
    for tool, args in [("overview", {}), ("visit", {"community": "Kelley Place"}),
                       ("open_items", {}), ("raised_items", {})]:
        raw = ask(tool, "regional@atlas.test", args).get_data(as_text=True)
        assert "room 12" not in raw and "Mrs. Smith" not in raw, tool
        assert '"notes"' not in raw and '"comments"' not in raw, tool


def test_open_items_list_the_unclosed_work_oldest_first():
    body = ask("open_items", "regional@atlas.test").get_json()
    texts = [i["text"] for i in body["items"]]
    assert "Kitchen is sanitary" in texts and "Replace hallway carpet" in texts
    assert "Fire exits clear" not in texts  # already addressed


def test_there_is_no_move_in_tool():
    assert ask("moveins", "regional@atlas.test").status_code == 400
