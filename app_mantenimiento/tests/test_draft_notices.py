"""
The signpost that says somebody has a visit in progress.

A draft lives in the browser on the device it is being filled in on, keyed on
community + survey type. Enter the form by any other route and it is not found
— which reads as the work having been lost. A regional hit exactly that and
asked for her draft to be deleted by someone who had no way to see or touch it.

So the server keeps a note that the draft exists. Not the visit: no answers, no
photos. The two things these hold down are that the note carries nothing it
shouldn't, and that it is only ever your own.

Run locally, never on the server.
"""

import os
import sys
import tempfile
from datetime import datetime, timedelta

import pytest

_APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

import app as A  # noqa: E402
from services.draft_notice_service import DraftNoticeService, TTL_DAYS  # noqa: E402

HDR = {"Origin": "http://localhost", "Referer": "http://localhost/"}
_FAKE_USERS = ("smoke.draft.a", "smoke.draft.b")


def teardown_module(module):
    for u in _FAKE_USERS:
        try:
            A.presence_service.forget(u)
        except Exception:
            pass
        for c in A.all_communities()[:2]:
            try:
                A.draft_notice_service.clear(u, c, "standards")
            except Exception:
                pass


@pytest.fixture
def svc():
    return DraftNoticeService(os.path.join(tempfile.mkdtemp(), "notices.json"))


def _communities(n=2):
    comms = A.all_communities()
    if len(comms) < n:
        pytest.skip("needs %d communities in the roster" % n)
    return comms[:n]


# ------------------------------------------------------------- the service

def test_it_notes_that_a_draft_exists(svc):
    n = svc.record("marissa", "Kelley Place", "standards",
                   answered=12, total=39, device="iPhone · Safari")
    assert n["community"] == "Kelley Place"
    assert (n["answered"], n["total"]) == (12, 39)
    assert n["device"] == "iPhone · Safari", "which device holds the actual work"


def test_it_carries_nothing_of_the_visit_itself(svc):
    """The answers and photos are the reason this is a signpost and not a copy."""
    n = svc.record("marissa", "Kelley Place", "standards", answered=12, total=39)
    for forbidden in ("responses", "photos", "answers", "notes", "text"):
        assert forbidden not in n, f"the note is carrying {forbidden}"
    assert set(n) == {"id", "username", "community", "survey_type_id",
                      "answered", "total", "device", "started_at", "updated_at"}


def test_progress_updates_in_place(svc):
    first = svc.record("marissa", "Kelley Place", "standards", answered=3, total=39)
    later = svc.record("marissa", "Kelley Place", "standards", answered=20, total=39)
    assert later["id"] == first["id"], "the same draft, not a second one"
    assert later["answered"] == 20
    assert later["started_at"] == first["started_at"], "when they began does not move"
    assert len(svc.for_user("marissa")) == 1


def test_two_people_on_the_same_community_do_not_collide(svc):
    svc.record("marissa", "Kelley Place", "standards", answered=3)
    svc.record("shannon", "Kelley Place", "standards", answered=8)
    assert len(svc.for_user("marissa")) == 1
    assert svc.for_user("marissa")[0]["answered"] == 3
    assert svc.for_user("shannon")[0]["answered"] == 8


def test_different_survey_types_are_different_drafts(svc):
    """The browser keys on both, so the note has to as well."""
    svc.record("marissa", "Kelley Place", "standards", answered=3)
    svc.record("marissa", "Kelley Place", "sales-new-hire", answered=1)
    assert len(svc.for_user("marissa")) == 2


def test_clearing_removes_it(svc):
    svc.record("marissa", "Kelley Place", "standards", answered=3)
    assert svc.clear("marissa", "Kelley Place", "standards") is True
    assert svc.for_user("marissa") == []


def test_a_note_never_outlives_the_draft_it_points_at(svc):
    """The browser prunes its own drafts at seven days.

    A note that outlived one would send somebody looking for work that is no
    longer there — worse than saying nothing at all.
    """
    svc.record("marissa", "Kelley Place", "standards", answered=3)
    stale = (datetime.now() - timedelta(days=TTL_DAYS + 1)).isoformat()
    svc.notices[0]["updated_at"] = stale
    assert svc.for_user("marissa") == []


def test_the_newest_is_first(svc):
    a, b = _communities()
    svc.record("marissa", a, "standards", answered=1)
    svc.record("marissa", b, "standards", answered=1)
    svc.notices[0]["updated_at"] = "2020-01-01T00:00:00"
    assert svc.for_user("marissa")[0]["community"] == b


# ---------------------------------------------------------------- the api

def _client(name, community):
    """A regional who covers that community.

    Their reach comes from the region they lead, not from anything on the
    session — setting session["communities"] and expecting it to count is how
    the first version of this test managed to fail against working code.
    """
    region = next((r for r in A.region_service.get_all_regions()
                   if community in (r.get("communities") or [])), None)
    if not region:
        pytest.skip("that community is not in a region")
    c = A.app.test_client()
    with c.session_transaction() as s:
        s.update(user=name, role="regional", region_id=region["id"],
                 community=None, display_name=name)
    return c


def test_you_only_ever_see_your_own():
    community = _communities(1)[0]
    a = _client("smoke.draft.a", community)
    b = _client("smoke.draft.b", community)
    try:
        assert a.post("/api/drafts", json={"community": community,
                                           "survey_type_id": "standards",
                                           "answered": 4, "total": 39},
                      headers=HDR).status_code == 200
        assert b.get("/api/drafts").get_json()["drafts"] == [], \
            "someone else's unfinished visit is not theirs to see"
        mine = a.get("/api/drafts").get_json()["drafts"]
        assert len(mine) == 1 and mine[0]["answered"] == 4
    finally:
        A.draft_notice_service.clear("smoke.draft.a", community, "standards")


def test_a_community_you_do_not_cover_is_refused():
    comms = A.all_communities()
    mine = comms[0]
    c = _client("smoke.draft.a", mine)
    # Something outside their region: the roster is grouped by region, so take
    # a community from a different one.
    region = next(r for r in A.region_service.get_all_regions()
                  if mine in (r.get("communities") or []))
    theirs = next((x for x in comms if x not in (region.get("communities") or [])), None)
    if not theirs:
        pytest.skip("only one region in the roster")
    r = c.post("/api/drafts", json={"community": theirs, "survey_type_id": "standards"},
               headers=HDR)
    assert r.status_code == 400


def test_nonsense_counts_do_not_get_through():
    community = _communities(1)[0]
    c = _client("smoke.draft.a", community)
    try:
        d = c.post("/api/drafts",
                   json={"community": community, "survey_type_id": "standards",
                         "answered": "many", "total": -5},
                   headers=HDR).get_json()["draft"]
        assert d["answered"] == 0 and d["total"] == 0
    finally:
        A.draft_notice_service.clear("smoke.draft.a", community, "standards")


def test_signed_out_gets_nothing():
    assert A.app.test_client().get("/api/drafts").status_code in (302, 401, 403)


# ------------------------------------------------- getting back to the draft

def test_resuming_sets_the_survey_type_the_draft_is_stored_under():
    """The draft is keyed on survey type + community.

    The survey type lives in the session, not the URL, so a link straight to
    the form would land with whatever type was there last — and the draft would
    not be found. This route sets it first.
    """
    comms = A.all_communities()
    if not comms:
        pytest.skip("needs a community")
    community = comms[0]
    types = [t for t in A.survey_type_service.get_all_survey_types() if t.get("id")]
    if not types:
        pytest.skip("needs a survey type")
    st = types[0]["id"]

    c = _client("smoke.draft.a", community)
    r = c.get(f"/reporte/resume?community={community}&survey_type={st}")
    assert r.status_code == 302, r.status_code
    assert "/reporte" in r.headers["Location"]
    assert "community=" in r.headers["Location"], \
        "the community rides along, or the form cannot preselect it"
    with c.session_transaction() as s:
        assert s.get("survey_type_id") == st, "the session now matches the draft's key"


def test_resuming_someone_elses_community_goes_nowhere():
    comms = A.all_communities()
    mine = comms[0]
    region = next(r for r in A.region_service.get_all_regions()
                  if mine in (r.get("communities") or []))
    theirs = next((x for x in comms if x not in (region.get("communities") or [])), None)
    if not theirs:
        pytest.skip("only one region in the roster")
    types = [t for t in A.survey_type_service.get_all_survey_types() if t.get("id")]
    if not types:
        pytest.skip("needs a survey type")
    c = _client("smoke.draft.a", mine)
    r = c.get(f"/reporte/resume?community={theirs}&survey_type={types[0]['id']}")
    assert r.status_code == 302
    assert "select" in r.headers["Location"], "sent to pick again, not into the form"


def test_resuming_with_a_bad_survey_type_goes_nowhere():
    comms = A.all_communities()
    if not comms:
        pytest.skip("needs a community")
    c = _client("smoke.draft.a", comms[0])
    r = c.get(f"/reporte/resume?community={comms[0]}&survey_type=not-a-type")
    assert r.status_code == 302
    assert "select" in r.headers["Location"]
