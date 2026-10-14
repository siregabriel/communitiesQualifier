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


def test_long_item_text_is_shortened_at_a_word_and_says_so():
    long = "Memory care branding. Let us make sure we work on signage for that and also add that " \
           "to collateral and the website so families see the same name everywhere they look today"
    short = A._atlasai_short(long)
    assert short.endswith("…") and len(short) <= 161
    assert not short[:-1].endswith("colla")
    assert long.startswith(short[:-1])
    assert A._atlasai_short("Replace hallway carpet") == "Replace hallway carpet"


# ---------------------------------------------------------------- activity

@pytest.fixture
def log(monkeypatch, items):
    """A small activity log: today, last week, and things that must never leave."""
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    today = (now - timedelta(minutes=5)).isoformat()
    week_ago = (now - timedelta(days=6)).isoformat()
    public = items.for_communities(["Kelley Place"])[0]["id"]
    internal = items.for_communities(["Kelley Place"], include_internal=True)
    internal = next(i["id"] for i in internal if i["text"] == "Watch this ED")
    events = [
        {"username": "wyman", "type": "inspection_submitted", "timestamp": today,
         "detail": "Submitted a visit for Kelley Place", "meta": {"community": "Kelley Place"}},
        {"username": "jazmyn", "type": "standard_addressed", "timestamp": today,
         "detail": "Marked addressed: Kitchen is sanitary at Kelley Place", "meta": {"community": "Kelley Place"}},
        {"username": "jazmyn", "type": "item_raised", "timestamp": today,
         "detail": "Raised an item at Kelley Place: Front door sticks",
         "meta": {"community": "Kelley Place", "raised_item_id": public}},
        {"username": "wyman", "type": "item_raised", "timestamp": today,
         "detail": "Raised an item at Kelley Place: Watch this ED",
         "meta": {"community": "Kelley Place", "raised_item_id": internal}},
        {"username": "jazmyn", "type": "movein_created", "timestamp": today,
         "detail": "Started move-in for Mrs. Smith (Kelley Place)", "meta": {"community": "Kelley Place"}},
        {"username": "jazmyn", "type": "login", "timestamp": today, "detail": "Signed in", "meta": {}},
        {"username": "x", "type": "inspection_submitted", "timestamp": today,
         "detail": "Submitted a visit for Trussville Memory Care",
         "meta": {"community": "Trussville Memory Care"}},
        {"username": "wyman", "type": "inspection_submitted", "timestamp": week_ago,
         "detail": "Submitted a visit for Monark Grove", "meta": {"community": "Monark Grove"}},
    ]

    def recent(limit=30, types=None, since=None):
        rows = [e for e in events if not types or e["type"] in set(types)]
        return sorted(rows, key=lambda e: e["timestamp"], reverse=True)[:limit]
    monkeypatch.setattr(A.activity_service, "get_recent", recent)
    monkeypatch.setattr(A, "resolve_display_name", lambda u: u.title())


def _whats(body):
    return [(e["what"], e["community"], e["detail"]) for e in body["events"]]


def test_activity_today_is_scoped_to_the_region(log):
    body = ask("activity", "regional@atlas.test").get_json()
    assert {e["community"] for e in body["events"]} == {"Kelley Place"}
    assert ("Visit submitted", "Kelley Place", "Submitted a visit for Kelley Place") in _whats(body)
    assert body["totals"]["Visit submitted"] == 1


def test_activity_never_carries_move_ins_or_sign_ins(log):
    raw = ask("activity", "regional@atlas.test", {"days": 30}).get_data(as_text=True)
    assert "Mrs. Smith" not in raw and "move-in" not in raw.lower() and "Signed in" not in raw


def test_activity_keeps_internal_items_with_leadership(log):
    ed = ask("activity", "ed@atlas.test").get_data(as_text=True)
    assert "Front door sticks" in ed and "Watch this ED" not in ed
    assert "Watch this ED" in ask("activity", "regional@atlas.test").get_data(as_text=True)


def test_activity_window_and_community_outside_scope(log):
    assert "Monark Grove" not in ask("activity", "regional@atlas.test").get_data(as_text=True)
    week = ask("activity", "regional@atlas.test", {"days": 7}).get_json()
    assert "Monark Grove" in {e["community"] for e in week["events"]}
    assert ask("activity", "regional@atlas.test", {"community": "Trussville"}).get_json()["error"] == "not_found"


# ---------------------------------------------------------------- org chart

@pytest.fixture
def org(monkeypatch):
    regions = [
        {"id": "r1", "name": "Magnolia", "communities": ["Kelley Place", "Monark Grove"],
         "leadership": [{"name": "Wyman", "role": "RDO", "email": "wyman@atlas.test"},
                        {"name": "Open", "role": "RDW"}]},
        {"id": "r2", "name": "Coastal", "communities": ["Trussville Memory Care"],
         "leadership": [{"name": "Keith", "role": "SRDO", "email": "keith@atlas.test"}]},
        {"id": A.CORPORATE_ID, "name": "Corporate", "kind": A.CORPORATE_KIND, "communities": [],
         "leadership": [{"name": "Scott", "role": "President and CEO", "email": "scott@atlas.test"}]},
    ]
    monkeypatch.setattr(A.region_service, "get_all_regions", lambda: regions)
    monkeypatch.setattr(A.user_service, "get_all", lambda: [
        {"username": "jazmyn", "role": "staff", "community": "Kelley Place", "display_name": "Jazmyn",
         "email": "jazmyn@atlas.test"}])
    monkeypatch.setattr(A, "account_communities", lambda u: [u["community"]])
    monkeypatch.setattr(A.profile_service, "get_display_name", lambda u: None)


def test_org_chart_is_scoped_and_lists_eds_and_corporate(org):
    body = ask("org_chart", "regional@atlas.test").get_json()
    assert [r["region"] for r in body["regions"]] == ["Magnolia"]
    magnolia = body["regions"][0]
    assert magnolia["leaders"] == [{"name": "Wyman", "title": "RDO"}]   # "Open" seats are left out
    assert {"community": "Kelley Place", "executive_directors": ["Jazmyn"]} in magnolia["communities"]
    assert body["corporate"]["members"] == [{"name": "Scott", "title": "President and CEO"}]


def test_org_chart_never_carries_emails(org):
    raw = ask("org_chart", "regional@atlas.test").get_data(as_text=True)
    assert "@atlas.test" not in raw


def test_org_chart_community_outside_scope(org):
    assert ask("org_chart", "ed@atlas.test", {"community": "Trussville"}).get_json()["error"] == "not_found"
