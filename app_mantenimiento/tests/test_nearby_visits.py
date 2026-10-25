"""
Nearby visits: the positions Atlerts gets, and where /sso may send someone.

Atlerts (iOS) suggests starting a visit when a regional or Corporate arrives at
one of their communities. It asks /api/atlerts/visit-places for the positions,
server to server with the shared SSO secret; the phone compares its own
location and nothing about where anybody is reaches this server.

What has to hold:
- No secret, no data.
- No account here, nothing — and never a new account.
- Only people who run visits get positions: an Executive Director gets none.
- Only communities in that person's scope, and only those with a place.
- The kill switch answers enabled: false to everybody.
- /sso follows `next` only to a local path on the allow-list.
- The visit type screen carries a community the person can see, and ignores one they can't.

Everything here runs on fixtures. Run locally, never on the server.
"""

import os
import sys

import pytest

_APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

import app as A  # noqa: E402

SECRET = "test-shared-secret"

REGIONS = [
    {"id": "r1", "name": "Magnolia", "communities": ["Kelley Place", "Monark Grove", "Unplaced House"]},
    {"id": "r2", "name": "Coastal", "communities": ["Trussville Memory Care"]},
]

ACCOUNTS = {
    "ed@atlas.test": ("jazmyn", {"role": "staff", "community": "Kelley Place",
                                 "communities": ["Kelley Place"], "region_id": None,
                                 "display_name": "Jazmyn"}),
    "regional@atlas.test": ("wyman", {"role": "regional", "community": None,
                                      "region_id": "r1", "display_name": "Wyman"}),
}

PLACES = {
    "Kelley Place": {"lat": 33.52, "lng": -86.80},
    "Monark Grove": {"lat": 33.10, "lng": -86.70},
    "Trussville Memory Care": {"lat": 33.62, "lng": -86.60},
}

VISITS = {
    "Kelley Place": [{"id": "s1", "community": "Kelley Place", "submitted_at": "2026-10-01T10:00:00"}],
}


@pytest.fixture(autouse=True)
def world(monkeypatch):
    monkeypatch.setattr(A, "ATLERTS_SSO_SECRET", SECRET)
    monkeypatch.delenv("ATLERTS_NEARBY_VISITS", raising=False)
    monkeypatch.setattr(A, "_atlerts_account_by_email",
                        lambda email: ACCOUNTS.get((email or "").strip().lower()))
    monkeypatch.setattr(A.region_service, "get_all_regions", lambda: REGIONS)
    monkeypatch.setattr(A.profile_service, "get_admin_extra", lambda u: False)
    monkeypatch.setattr(A.profile_service, "get_all_communities", lambda u: False)
    monkeypatch.setattr(A.inspection_service, "get_submissions_by_community",
                        lambda c: list(VISITS.get(c, [])))
    monkeypatch.setattr(A.place_service, "placed",
                        lambda names: [dict(PLACES[n], community=n) for n in (names or []) if n in PLACES])


def places(email, secret=SECRET):
    headers = {"X-Atlerts-Sso-Secret": secret} if secret is not None else {}
    return A.app.test_client().post("/api/atlerts/visit-places", headers=headers, json={"email": email})


# ---------------------------------------------------------------- the door

def test_no_secret_no_data():
    assert places("regional@atlas.test", secret=None).status_code == 403


def test_wrong_secret_no_data():
    assert places("regional@atlas.test", secret="guess").status_code == 403


def test_no_account_here_means_nothing():
    r = places("stranger@atlas.test")
    assert r.status_code == 200
    assert r.get_json()["runs_visits"] is False and r.get_json()["communities"] == []


def test_the_isolated_session_never_becomes_a_cookie():
    assert "Set-Cookie" not in places("regional@atlas.test").headers


# ---------------------------------------------------------------- who and what

def test_an_executive_director_does_not_run_visits():
    body = places("ed@atlas.test").get_json()
    assert body["runs_visits"] is False and body["communities"] == []


def test_a_regional_gets_their_placed_communities_only():
    body = places("regional@atlas.test").get_json()
    assert body["enabled"] is True and body["runs_visits"] is True
    names = [c["community"] for c in body["communities"]]
    # Their region, without the one that has no place, and nothing from another region.
    assert names == ["Kelley Place", "Monark Grove"]


def test_positions_and_days_since_the_last_visit():
    rows = {c["community"]: c for c in places("regional@atlas.test").get_json()["communities"]}
    assert rows["Kelley Place"]["lat"] == 33.52 and rows["Kelley Place"]["lng"] == -86.80
    assert isinstance(rows["Kelley Place"]["days_since_visit"], int)
    assert rows["Monark Grove"]["days_since_visit"] is None   # never visited


def test_only_names_positions_and_days_leave_the_server():
    for row in places("regional@atlas.test").get_json()["communities"]:
        assert set(row) == {"community", "lat", "lng", "days_since_visit"}


def test_the_kill_switch(monkeypatch):
    monkeypatch.setenv("ATLERTS_NEARBY_VISITS", "0")
    body = places("regional@atlas.test").get_json()
    assert body["enabled"] is False and body["communities"] == []


# ---------------------------------------------------------------- /sso?next=

@pytest.mark.parametrize("value,expected", [
    ("/select-survey-type?community=Kelley%20Place", "/select-survey-type?community=Kelley%20Place"),
    ("/reporte?community=Monark%20Grove", "/reporte?community=Monark%20Grove"),
    ("/select-survey-type", "/select-survey-type"),
    ("https://evil.example/select-survey-type", None),
    ("//evil.example/select-survey-type", None),
    ("/\\evil.example", None),
    ("/dashboard", None),
    ("/select-survey-typeX", None),
    ("select-survey-type", None),
    ("", None),
    (None, None),
])
def test_sso_next_allow_list(value, expected):
    assert A._sso_next(value) == expected


# ---------------------------------------------------------------- the visit type screen

def _as(client, username, account):
    with client.session_transaction() as s:
        s["user"] = username
        s["community"] = account["community"]
        s["communities"] = account.get("communities") or []
        s["role"] = account["role"]
        s["region_id"] = account["region_id"]
        s["display_name"] = account["display_name"]
        s["admin_extra"] = False


def test_the_visit_type_screen_carries_a_community_in_scope():
    client = A.app.test_client()
    _as(client, *ACCOUNTS["regional@atlas.test"])
    html = client.get("/select-survey-type?community=Kelley%20Place").get_data(as_text=True)
    assert 'const NEXT_COMMUNITY = "Kelley Place";' in html


def test_the_visit_type_screen_ignores_a_community_out_of_scope():
    client = A.app.test_client()
    _as(client, *ACCOUNTS["regional@atlas.test"])
    html = client.get("/select-survey-type?community=Trussville%20Memory%20Care").get_data(as_text=True)
    assert 'const NEXT_COMMUNITY = "";' in html
