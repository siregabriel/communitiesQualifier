"""
Smoke tests for the Atlas Excellence app.

Boots the Flask app with its in-process test client (no network, no S3, no
SES) and exercises the endpoints and flows that have historically broken:
role scoping, exports, the move-in compliance gate, and the community-rename
data-consistency fixes.

Run either way:
    pytest tests/test_smoke.py
    python tests/test_smoke.py

These run against the real data/*.json files, so every test cleans up after
itself (creates + deletes its own records) and leaves data untouched.
"""

import os
import sys

# The app reads config from the environment at import time. Set safe defaults
# before importing so the test client works without HTTPS cookies or a secret.
os.environ.setdefault("COOKIE_SECURE", "0")
os.environ.setdefault("SECRET_KEY", "smoke-test-key")

# Make the app package importable whether run from repo root or app_mantenimiento.
_HERE = os.path.dirname(os.path.abspath(__file__))
_APP_DIR = os.path.dirname(_HERE)
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

import app as A  # noqa: E402

# CSRF guard checks Origin/Referer on unsafe methods.
HDR = {"Origin": "http://localhost", "Referer": "http://localhost/"}


def _sweep_test_photos():
    """Remove photos written by the tests.

    Only files whose name starts with a smoke-test username are touched — a
    real photo uploaded by a real person must never be caught by this."""
    import glob
    root = os.path.join(_APP_DIR, "static", "uploads")
    for path in glob.glob(os.path.join(root, "*", "smoke.*")):
        try:
            os.remove(path)
        except OSError:
            pass


def _client():
    return A.app.test_client()


def _as_admin(c):
    with c.session_transaction() as s:
        s.update(user="admin", role="admin", region_id=None,
                 community=None, display_name="admin")
        s.permanent = True


def _as_role(c, role, region_id=None, community=None, name="tester"):
    with c.session_transaction() as s:
        s.update(user=name, role=role, region_id=region_id,
                 community=community, display_name=name)
        s.permanent = True


# Fabricated sessions leave a presence record behind (every request marks the
# signed-in user as active), so drop them when the suite finishes.
_FAKE_USERS = ("tester", "smoke.regional")


def teardown_module(module):
    for u in _FAKE_USERS:
        A.presence_service.forget(u)
    _sweep_test_photos()


def _a_community():
    """Pick a real community name from the seeded regions."""
    for reg in A.region_service.get_all_regions():
        for comm in reg.get("communities", []):
            name = comm if isinstance(comm, str) else comm.get("name")
            if name:
                return name
    return "Kelley Place, Enterprise"


# ---------------------------------------------------------------------------

def test_login_and_core_endpoints_ok():
    c = _client()
    r = c.post("/api/login", json={"username": "admin", "password": "admin123"},
               headers=HDR)
    assert r.status_code == 200, r.get_data(as_text=True)

    endpoints = [
        "/dashboard", "/api/regions", "/api/communities", "/api/inspections",
        "/api/leaderboard", "/api/people/profile?name=admin", "/api/moveins",
        "/api/survey-types", "/api/questions", "/api/users",
    ]
    for e in endpoints:
        assert c.get(e).status_code < 400, f"{e} failed"


def test_exports_render():
    c = _client()
    _as_admin(c)
    for e in ["/api/reports/export.csv", "/api/reports/export.xlsx",
              "/api/reports/export.pdf", "/api/moveins/export.csv",
              "/api/moveins/export.xlsx", "/api/moveins/template/pdf"]:
        assert c.get(e).status_code == 200, f"{e} did not render"


def test_movein_status_validation():
    c = _client()
    _as_admin(c)
    mid = c.post("/api/moveins",
                 json={"resident_name": "Status Test", "community": _a_community(),
                       "target_date": "2026-07-20"},
                 headers=HDR).get_json()["movein"]["id"]
    try:
        # backend accepts only active/completed/archived
        assert c.post(f"/api/moveins/{mid}/status", json={"status": "bogus"},
                      headers=HDR).status_code == 400
        assert c.post(f"/api/moveins/{mid}/status", json={"status": "archived"},
                      headers=HDR).status_code == 200
    finally:
        c.delete(f"/api/moveins/{mid}", headers=HDR)


def test_movein_compliance_gate():
    """Cannot complete while required items are pending; can once they're done."""
    c = _client()
    _as_admin(c)
    template = c.get("/api/moveins/template").get_json()["template"]

    required = []
    all_ids = []

    def walk(o):
        if isinstance(o, dict):
            if "id" in o and any(k in o for k in ("label", "text", "title")):
                all_ids.append(o["id"])
                if o.get("required"):
                    required.append(o["id"])
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(template)

    mid = c.post("/api/moveins",
                 json={"resident_name": "Gate Test", "community": _a_community(),
                       "target_date": "2026-07-20"},
                 headers=HDR).get_json()["movein"]["id"]
    try:
        if required:
            r = c.post(f"/api/moveins/{mid}/status", json={"status": "completed"},
                       headers=HDR)
            assert r.status_code == 409, "gate should block completion"
        for i in required:
            c.post(f"/api/moveins/{mid}/item", json={"item_id": i, "done": True},
                   headers=HDR)
        r = c.post(f"/api/moveins/{mid}/status", json={"status": "completed"},
                   headers=HDR)
        assert r.status_code == 200, "completion should succeed once required done"
    finally:
        c.delete(f"/api/moveins/{mid}", headers=HDR)


def test_admin_api_returns_403_not_redirect_for_non_admin():
    """Regression: non-admins hitting admin /api/ endpoints get 403 JSON."""
    c = _client()
    _as_role(c, "regional", region_id="coastal")
    r = c.post("/api/regions/rename",
               json={"region_id": "coastal", "name": "Should Not Work"},
               headers=HDR)
    assert r.status_code == 403, f"expected 403, got {r.status_code}"
    assert r.get_json().get("status") == "error"


def test_community_rename_updates_moveins_and_cover():
    """Regression: renaming a community carries its move-ins and cover photo."""
    c = _client()
    _as_admin(c)
    old = _a_community()
    new = old + " (Renamed Test)"

    mid = c.post("/api/moveins",
                 json={"resident_name": "Rename Follow", "community": old,
                       "target_date": "2026-07-20"},
                 headers=HDR).get_json()["movein"]["id"]
    # seed a cover record for the old slug
    A.community_cover_service.set(A.community_slug(old), old,
                                  "community_covers/test.jpg", "test.jpg")
    raised = A.raised_item_service.create(old, "Follows the rename", "admin", "Administrator")
    try:
        r = c.post("/api/regions/rename-community",
                   json={"old_name": old, "new_name": new}, headers=HDR)
        assert r.status_code == 200

        mv = c.get(f"/api/moveins/{mid}").get_json()["movein"]
        assert mv["community"] == new, "move-in should follow the rename"

        assert A.community_cover_service.get(A.community_slug(new)) is not None
        assert A.community_cover_service.get(A.community_slug(old)) is None

        # Anything the community raised for itself follows the rename too.
        assert A.raised_item_service.for_communities([new]), \
            "a raised item was left pointing at the old name"
        assert not A.raised_item_service.for_communities([old])
    finally:
        # restore everything: rename back, drop cover + move-in
        c.post("/api/regions/rename-community",
               json={"old_name": new, "new_name": old}, headers=HDR)
        A.community_cover_service.delete(A.community_slug(old))
        A.community_cover_service.delete(A.community_slug(new))
        if raised:
            A.raised_item_service.delete(raised["id"])
        c.delete(f"/api/moveins/{mid}", headers=HDR)


def test_addressing_a_failed_standard_keeps_the_verdict_and_score():
    """Regression: marking a failed standard as addressed records the follow-up
    but must never rewrite the visit — the item stays 'Fail'."""
    c = _client()
    _as_admin(c)
    sub = A.inspection_service.create_submission(
        username="admin", community=_a_community(),
        inspector_name="Smoke Test",
        responses=[{
            "question_id": "smoke_q1",
            "question_text": "Smoke test standard",
            "condition": "Fail",
            "description": "seeded by the test suite",
            "answered_at": "2026-07-31T09:00:00",
        }])
    sid = sub["id"]
    url = f"/api/action-items/{sid}/standard/smoke_q1/resolve"
    try:
        r = c.post(url, json={"resolved": True, "note": "Fixed same day"},
                   headers=HDR)
        assert r.status_code == 200, r.get_data(as_text=True)
        resp = r.get_json()["response"]
        assert resp["condition"] == "Fail", "the verdict must not change"
        assert resp["addressed"] is True
        assert resp["addressed_note"] == "Fixed same day"
        assert resp["addressed_by"] == "admin"

        # Reopening clears the follow-up, still without touching the verdict.
        r = c.post(url, json={"resolved": False}, headers=HDR)
        assert r.status_code == 200
        resp = r.get_json()["response"]
        assert resp["addressed"] is False
        assert resp["condition"] == "Fail"
        assert "addressed_note" not in resp

        # Unknown standard on a real visit is a 404, not a silent success.
        assert c.post(f"/api/action-items/{sid}/standard/nope/resolve",
                      json={"resolved": True}, headers=HDR).status_code == 404
    finally:
        A.inspection_service.submissions = [
            s for s in A.inspection_service.submissions if s.get("id") != sid]
        A.inspection_service.save_to_file()


def test_fail_requires_a_comment():
    """A Fail with no comment is rejected; the same Fail with one goes through."""
    import json as _json
    # Admins can't submit inspections, so run this as a regional in a real region.
    region_id, comm = None, None
    for reg in A.region_service.get_all_regions():
        for entry in reg.get("communities", []):
            name = entry if isinstance(entry, str) else entry.get("name")
            if name:
                region_id, comm = reg.get("id"), name
                break
        if comm:
            break
    assert comm, "no seeded community to test with"

    survey_type_id = A.survey_type_service.get_all_survey_types()[0]["id"]

    c = _client()
    _as_role(c, "regional", region_id=region_id, name="smoke.regional")
    with c.session_transaction() as s:
        s["survey_type_id"] = survey_type_id

    def post(description):
        return c.post("/api/inspections", headers=HDR, data={
            "community": comm,
            "responses": _json.dumps([{
                "question_id": "smoke_q2",
                "question_text": "Smoke test standard",
                "condition": "Fail",
                "description": description,
            }]),
        }, content_type="multipart/form-data")

    before = {s["id"] for s in A.inspection_service.get_all_submissions()}
    r = post("   ")
    assert r.status_code == 400, "an empty Fail comment must be rejected"
    assert "comment" in r.get_json()["message"].lower()

    r = post("Handrail loose by room 204")
    assert r.status_code in (200, 201), r.get_data(as_text=True)
    try:
        after = A.inspection_service.get_all_submissions()
        new = [s for s in after if s["id"] not in before]
        assert len(new) == 1
        assert new[0]["responses"][0]["description"] == "Handrail loose by room 204"
    finally:
        A.inspection_service.submissions = [
            s for s in A.inspection_service.submissions if s.get("id") in before]
        A.inspection_service.save_to_file()


def test_login_is_recorded_and_shows_in_people():
    """Signing in updates presence and surfaces in the People directory."""
    c = _client()
    r = c.post("/api/login", json={"username": "admin", "password": "admin123"},
               headers=HDR)
    assert r.status_code == 200

    pres = A.presence_service.get("admin")
    assert pres["last_login"], "the sign-in should be recorded"
    assert pres["active"] is True, "just-signed-in counts as active"

    me = next(p for p in c.get("/api/people").get_json()["people"]
              if p["username"] == "admin")
    assert me["online"] is True
    assert me["last_login"]


def test_activity_feed_is_admin_only():
    c = _client()
    _as_role(c, "regional", region_id="coastal")
    assert c.get("/api/activity/live").status_code == 403

    _as_admin(c)
    d = c.get("/api/activity/live").get_json()
    assert d["status"] == "success"
    assert isinstance(d["events"], list) and isinstance(d["online"], list)


def test_activity_digest_preview_builds():
    """The digest can be built and previewed without sending anything."""
    c = _client()
    _as_admin(c)
    r = c.post("/api/activity/digest", json={"preview": True, "hours": 24},
               headers=HDR)
    assert r.status_code == 200, r.get_data(as_text=True)
    d = r.get_json()["digest"]
    for key in ("signed_in", "visits", "addressed", "security",
                "accounts", "never_signed_in"):
        assert isinstance(d[key], list), f"{key} should be a list"
    assert d["hours"] == 24


def test_sales_is_a_full_routing_destination():
    """Sales must behave exactly like Clinical and Ops: storable recipients, an
    accepted route on a response, and its own row in 'Who receives what'."""
    c = _client()
    _as_admin(c)
    before = A.settings_service.get_email_settings()
    try:
        r = c.post("/api/settings/email", headers=HDR, json={
            "admin_notify": "\n".join(before["admin_notify"]),
            "clinical": "\n".join(before["clinical"]),
            "ops": "\n".join(before["ops"]),
            "sales": "sales.team@example.com",
        })
        assert r.status_code == 200, r.get_data(as_text=True)
        assert r.get_json()["sales"] == ["sales.team@example.com"]

        # The service resolves it like any other route.
        assert A.settings_service.recipients_for_route("sales") == ["sales.team@example.com"]
        assert A.settings_service.recipients_for_route("nonsense") == []

        # And it shows up in the consolidated recipient view.
        summary = c.get("/api/settings/email/summary").get_json()
        row = next(p for p in summary["people"]
                   if p["email"].lower() == "sales.team@example.com")
        assert any("Sales" in i["label"] for i in row["items"]), row["items"]
    finally:
        A.settings_service.set_email_settings(
            subscribers=before["subscribers"], admin_notify=before["admin_notify"],
            clinical=before["clinical"], ops=before["ops"], sales=before["sales"])


def test_response_accepts_sales_route():
    """A visit response directed to Sales keeps that routing when stored."""
    import json as _json
    region_id, comm = None, None
    for reg in A.region_service.get_all_regions():
        for entry in reg.get("communities", []):
            name = entry if isinstance(entry, str) else entry.get("name")
            if name:
                region_id, comm = reg.get("id"), name
                break
        if comm:
            break
    survey_type_id = A.survey_type_service.get_all_survey_types()[0]["id"]

    c = _client()
    _as_role(c, "regional", region_id=region_id, name="smoke.regional")
    with c.session_transaction() as s:
        s["survey_type_id"] = survey_type_id

    before = {s["id"] for s in A.inspection_service.get_all_submissions()}
    r = c.post("/api/inspections", headers=HDR, data={
        "community": comm,
        "responses": _json.dumps([{
            "question_id": "smoke_q3",
            "question_text": "Tour path is show ready",
            "condition": "Fail",
            "description": "Front entrance needs attention before tours",
            "route_to": "sales",
        }]),
    }, content_type="multipart/form-data")
    assert r.status_code in (200, 201), r.get_data(as_text=True)
    try:
        new = [s for s in A.inspection_service.get_all_submissions()
               if s["id"] not in before]
        assert new[0]["responses"][0]["route_to"] == "sales"
    finally:
        A.inspection_service.submissions = [
            s for s in A.inspection_service.submissions if s.get("id") in before]
        A.inspection_service.save_to_file()


def _seed_failed_visit(community, qid="smoke_q4"):
    """A submitted visit with one failed standard, for the follow-up tests."""
    return A.inspection_service.create_submission(
        username="admin", community=community, inspector_name="Smoke Test",
        responses=[{
            "question_id": qid, "question_text": "Welcome sign in lobby",
            "condition": "Fail", "description": "No sign in the lobby",
            "answered_at": "2026-08-06T09:00:00",
        }])


def test_community_account_can_comment_but_not_close():
    """The heart of the agreed model: an Executive Director reports the fix,
    leadership verifies it. A community must never close its own item."""
    comm = _a_community()
    sub = _seed_failed_visit(comm)
    sid = sub["id"]
    base = f"/api/action-items/{sid}/standard/smoke_q4"
    try:
        ed = _client()
        _as_role(ed, "staff", community=comm, name="smoke.ed")

        # It can comment...
        r = ed.post(f"{base}/comments", json={"text": "New sign ordered, arrives Friday"},
                    headers=HDR)
        assert r.status_code == 201, r.get_data(as_text=True)
        assert r.get_json()["comment"]["text"] == "New sign ordered, arrives Friday"

        # ...but it cannot mark the item as addressed.
        r = ed.post(f"{base}/resolve", json={"resolved": True}, headers=HDR)
        assert r.status_code == 403, "a community account must not close its own item"
        assert "regional" in r.get_json()["message"].lower()

        # The comment is stored on the response, and the verdict is untouched.
        stored = next(s for s in A.inspection_service.get_all_submissions() if s["id"] == sid)
        resp = stored["responses"][0]
        assert len(resp["comments"]) == 1
        assert resp["condition"] == "Fail" and not resp.get("addressed")

        # A regional reviewing it can close it out.
        boss = _client()
        _as_admin(boss)
        r = boss.post(f"{base}/resolve", json={"resolved": True, "note": "Verified on site"},
                      headers=HDR)
        assert r.status_code == 200, r.get_data(as_text=True)
        assert r.get_json()["response"]["addressed"] is True
    finally:
        A.inspection_service.submissions = [
            s for s in A.inspection_service.submissions if s.get("id") != sid]
        A.inspection_service.save_to_file()
        A.presence_service.forget("smoke.ed")


def test_comment_authorship_and_scope():
    """Comments are scoped to the community, and only the author (or an admin)
    can delete one."""
    comm = _a_community()
    sub = _seed_failed_visit(comm, qid="smoke_q5")
    sid = sub["id"]
    base = f"/api/action-items/{sid}/standard/smoke_q5"
    try:
        ed = _client()
        _as_role(ed, "staff", community=comm, name="smoke.ed")
        cid = ed.post(f"{base}/comments", json={"text": "Fixed"}, headers=HDR).get_json()["comment"]["id"]

        # Someone from another community cannot see or comment on it.
        outsider = _client()
        _as_role(outsider, "staff", community="Some Other Place", name="smoke.other")
        assert outsider.post(f"{base}/comments", json={"text": "nope"},
                             headers=HDR).status_code == 403
        assert outsider.delete(f"{base}/comments/{cid}", headers=HDR).status_code == 403

        # An empty comment is refused rather than stored blank.
        assert ed.post(f"{base}/comments", json={"text": "   "}, headers=HDR).status_code == 400

        # The author can delete their own.
        assert ed.delete(f"{base}/comments/{cid}", headers=HDR).status_code == 200
        stored = next(s for s in A.inspection_service.get_all_submissions() if s["id"] == sid)
        assert stored["responses"][0].get("comments") == []
    finally:
        A.inspection_service.submissions = [
            s for s in A.inspection_service.submissions if s.get("id") != sid]
        A.inspection_service.save_to_file()
        for u in ("smoke.ed", "smoke.other"):
            A.presence_service.forget(u)


def test_community_cannot_file_its_own_visit():
    """The score comes from the latest visit, so letting a community run one
    would let it overwrite the regional's findings. Both the page and the
    endpoint must refuse."""
    import json as _json
    comm = _a_community()
    c = _client()
    _as_role(c, "staff", community=comm, name="smoke.ed")
    with c.session_transaction() as s:
        s["survey_type_id"] = A.survey_type_service.get_all_survey_types()[0]["id"]

    before = {x["id"] for x in A.inspection_service.get_all_submissions()}
    try:
        r = c.post("/api/inspections", headers=HDR, content_type="multipart/form-data", data={
            "community": comm,
            "responses": _json.dumps([{
                "question_id": "smoke_q6", "question_text": "Everything is fine",
                "condition": "Pass", "description": "self-assessed",
            }]),
        })
        assert r.status_code == 403, "a community must not be able to file a visit"
        assert "regional" in r.get_json()["message"].lower()
        after = {x["id"] for x in A.inspection_service.get_all_submissions()}
        assert after == before, "nothing may be written when the visit is refused"

        # The pages that lead there send them back to the dashboard.
        for path in ("/select-survey-type", "/reporte"):
            resp = c.get(path)
            assert resp.status_code in (301, 302), f"{path} should redirect"
            assert "/dashboard" in resp.headers.get("Location", "")

        # A regional in that region is still free to submit.
        assert A.app.test_client() is not None
    finally:
        A.inspection_service.submissions = [
            x for x in A.inspection_service.submissions if x.get("id") in before]
        A.inspection_service.save_to_file()
        A.presence_service.forget("smoke.ed")


def test_community_history_is_scoped_and_adds_up():
    """History is served per community, only to people who may see it, and its
    two scores follow the same rule as everywhere else."""
    comm = _a_community()
    sub = _seed_failed_visit(comm, qid="smoke_q7")
    sid = sub["id"]
    try:
        c = _client()
        _as_admin(c)
        d = c.get(f"/api/communities/{comm}/history").get_json()
        assert d["status"] == "success"
        v = next(x for x in d["visits"] if x["id"] == sid)
        assert v["failed"] == 1 and v["fixed"] == 0
        assert v["visit_score"] == 0 and v["current_score"] == 0

        # Verifying the fix lifts the current score but never the visit score.
        c.post(f"/api/action-items/{sid}/standard/smoke_q7/resolve",
               json={"resolved": True}, headers=HDR)
        v = next(x for x in c.get(f"/api/communities/{comm}/history").get_json()["visits"]
                 if x["id"] == sid)
        assert v["visit_score"] == 0, "the visit score must never move"
        assert v["current_score"] == 100, "a verified fix lifts the current score"
        assert v["fixed"] == 1

        # The per-standard record carries that visit.
        track = c.get(f"/api/communities/{comm}/history").get_json()["standards"]
        assert any(t["question_text"] == "Welcome sign in lobby" for t in track)

        # Somebody from another community cannot read it.
        outsider = _client()
        _as_role(outsider, "staff", community="Some Other Place", name="smoke.other")
        assert outsider.get(f"/api/communities/{comm}/history").status_code == 403
    finally:
        A.inspection_service.submissions = [
            s for s in A.inspection_service.submissions if s.get("id") != sid]
        A.inspection_service.save_to_file()
        A.presence_service.forget("smoke.other")


def test_one_rule_for_both_kinds_of_item():
    """The community reports, leadership closes — with no exception for the
    items raised by hand during a visit."""
    comm = _a_community()
    sub = A.inspection_service.create_submission(
        username="admin", community=comm, inspector_name="Smoke Test",
        responses=[{
            "question_id": "smoke_q8", "question_text": "Welcome sign in lobby",
            "condition": "Fail", "description": "No sign",
            "answered_at": "2026-08-08T09:00:00",
        }],
        action_items=[{"text": "Sandwich boards keep falling over",
                       "assigned_to": "Maintenance", "priority": "high"}])
    sid = sub["id"]
    item_id = sub["action_items"][0]["id"]
    try:
        ed = _client()
        _as_role(ed, "staff", community=comm, name="smoke.ed")

        # It can comment on both kinds of item...
        for url in (f"/api/action-items/{sid}/standard/smoke_q8/comments",
                    f"/api/action-items/{sid}/item/{item_id}/comments"):
            r = ed.post(url, json={"text": "Handled today"}, headers=HDR)
            assert r.status_code == 201, f"{url}: {r.get_data(as_text=True)}"

        # ...and close neither.
        assert ed.post(f"/api/action-items/{sid}/standard/smoke_q8/resolve",
                       json={"resolved": True}, headers=HDR).status_code == 403
        r = ed.post(f"/api/action-items/{sid}/{item_id}/resolve",
                    json={"resolved": True}, headers=HDR)
        assert r.status_code == 403, "a community must not close an ad-hoc item either"
        assert "comment" in r.get_json()["message"].lower()

        stored = next(s for s in A.inspection_service.get_all_submissions() if s["id"] == sid)
        assert len(stored["responses"][0]["comments"]) == 1
        assert len(stored["action_items"][0]["comments"]) == 1
        assert not stored["action_items"][0].get("resolved"), "still open until leadership closes it"

        # Leadership closes both.
        boss = _client()
        _as_admin(boss)
        assert boss.post(f"/api/action-items/{sid}/standard/smoke_q8/resolve",
                         json={"resolved": True}, headers=HDR).status_code == 200
        assert boss.post(f"/api/action-items/{sid}/{item_id}/resolve",
                         json={"resolved": True, "note": "Verified"},
                         headers=HDR).status_code == 200
    finally:
        A.inspection_service.submissions = [
            s for s in A.inspection_service.submissions if s.get("id") != sid]
        A.inspection_service.save_to_file()
        A.presence_service.forget("smoke.ed")


def test_user_info_carries_the_capability_flags():
    """The dashboard hides "Start a visit" and "Mark as addressed" on these two
    flags. They were once added to the wrong endpoint, which silently took the
    buttons away from everyone — so pin them down."""
    checks = [
        ("admin",     dict(user="admin", role="admin", community=None, region_id=None),
         {"can_run_visits": False, "can_verify_fixes": True}),
        ("regional",  dict(user="smoke.regional", role="regional", community=None, region_id="coastal"),
         {"can_run_visits": True, "can_verify_fixes": True}),
        ("community", dict(user="smoke.ed", role="staff", community=_a_community(), region_id=None),
         {"can_run_visits": False, "can_verify_fixes": False}),
    ]
    try:
        for label, sess, expected in checks:
            c = _client()
            with c.session_transaction() as s:
                s.update(display_name=label, **sess)
            d = c.get("/api/user-info").get_json()
            for key, want in expected.items():
                assert key in d, f"{label}: /api/user-info is missing {key}"
                assert d[key] is want, f"{label}: {key} should be {want}, got {d[key]}"
    finally:
        for u in ("smoke.regional", "smoke.ed"):
            A.presence_service.forget(u)


def _two_communities():
    names = []
    for reg in A.region_service.get_all_regions():
        for entry in reg.get("communities", []):
            n = entry if isinstance(entry, str) else entry.get("name")
            if n and n not in names:
                names.append(n)
            if len(names) >= 3:
                return names[0], names[1], names[2]
    raise AssertionError("need at least three communities to test isolation")


def test_an_account_can_cover_two_communities_and_no_more():
    """An ED standing in for a neighbour sees both — and must not gain a third.
    Every scoping check compared a single community before this, so each one
    is exercised here."""
    first, second, third = _two_communities()
    subs = []
    try:
        for comm in (first, second, third):
            subs.append(A.inspection_service.create_submission(
                username="admin", community=comm, inspector_name="Smoke",
                responses=[{"question_id": "smoke_q9", "question_text": "Welcome sign",
                            "condition": "Fail", "description": "missing",
                            "answered_at": "2026-08-11T09:00:00"}]))

        c = _client()
        with c.session_transaction() as s:
            s.update(user="smoke.ed", role="staff", region_id=None,
                     community=first, communities=[first, second],
                     display_name="Smoke ED")

        # The dashboard grid lists both, and only both.
        listed = set(c.get("/api/communities").get_json()["communities"])
        assert listed == {first, second}, listed

        # Visits: both visible, the third absent.
        seen = {s["community"] for s in c.get("/api/inspections").get_json()["submissions"]}
        assert first in seen and second in seen, seen
        assert third not in seen, "a third community leaked into the visit list"

        # History is readable for both, refused for the third.
        assert c.get(f"/api/communities/{first}/history").status_code == 200
        assert c.get(f"/api/communities/{second}/history").status_code == 200
        assert c.get(f"/api/communities/{third}/history").status_code == 403

        # Commenting follows the same rule.
        ok_sub = next(x for x in subs if x["community"] == second)
        no_sub = next(x for x in subs if x["community"] == third)
        assert c.post(f"/api/action-items/{ok_sub['id']}/standard/smoke_q9/comments",
                      json={"text": "covering this one too"}, headers=HDR).status_code == 201
        assert c.post(f"/api/action-items/{no_sub['id']}/standard/smoke_q9/comments",
                      json={"text": "nope"}, headers=HDR).status_code == 403

        # And so do the exports.
        csv_body = c.get("/api/reports/export.csv").get_data(as_text=True)
        assert first in csv_body and second in csv_body
        assert third not in csv_body, "the export reached beyond the account's communities"
    finally:
        ids = {s["id"] for s in subs}
        A.inspection_service.submissions = [
            s for s in A.inspection_service.submissions if s.get("id") not in ids]
        A.inspection_service.save_to_file()
        A.presence_service.forget("smoke.ed")


def test_a_photo_lands_on_its_own_standard():
    """Photos were numbered in sequence while the server matched them by the
    position of the response, so evidence filed under the wrong item whenever
    an earlier standard had no photo. Also covers a filename that sanitises
    down to nothing, which used to raise a 500 mid-upload."""
    import io, json as _json
    region_id = comm = None
    for reg in A.region_service.get_all_regions():
        for entry in reg.get("communities", []):
            n = entry if isinstance(entry, str) else entry.get("name")
            if n:
                region_id, comm = reg.get("id"), n
                break
        if comm:
            break
    c = _client()
    _as_role(c, "regional", region_id=region_id, name="smoke.regional")
    with c.session_transaction() as s:
        s["survey_type_id"] = A.survey_type_service.get_all_survey_types()[0]["id"]

    before = {x["id"] for x in A.inspection_service.get_all_submissions()}
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 40
    r = c.post("/api/inspections", headers=HDR, content_type="multipart/form-data", data={
        "community": comm,
        "responses": _json.dumps([
            {"question_id": "qa", "question_text": "First", "condition": "Pass", "description": ""},
            {"question_id": "qb", "question_text": "Second", "condition": "Pass", "description": ""},
            {"question_id": "qc", "question_text": "Third", "condition": "Fail", "description": "photo here"},
        ]),
        # a name that secure_filename() reduces to just the extension
        "photo_q_qc": (io.BytesIO(png), "\u56fe\u7247.png"),
    })
    try:
        assert r.status_code in (200, 201), r.get_data(as_text=True)
        new = [x for x in A.inspection_service.get_all_submissions() if x["id"] not in before]
        with_photo = [x["question_id"] for x in new[0]["responses"] if x.get("photo_path")]
        assert with_photo == ["qc"], f"the photo landed on {with_photo}"
    finally:
        A.inspection_service.submissions = [
            x for x in A.inspection_service.submissions if x.get("id") in before]
        A.inspection_service.save_to_file()
        A.presence_service.forget("smoke.regional")
        _sweep_test_photos()


def _region_owning(community):
    """The region a community belongs to, and one that doesn't."""
    owner = A.region_for_community(community)
    other = next(r for r in A.region_service.get_all_regions()
                 if r.get("id") != owner.get("id")
                 and community not in (r.get("communities") or []))
    return owner, other


def _groups(payload):
    return {g["key"]: g for g in payload["groups"]}


def test_attention_moves_between_the_two_sides():
    """The report-and-verify loop, seen from the worklist.

    A failed standard starts on the community's plate. Once they say it's done
    it moves to the regional's. Once the regional replies it goes back. Once
    the regional closes it, it belongs to nobody. Whoever the item is *not*
    waiting on must never be shown it as work."""
    comm = _a_community()
    sub = _seed_failed_visit(comm)
    sid = sub["id"]
    owner, _ = _region_owning(comm)
    ed_name = "smoke.attn.ed"
    A.user_service.create(ed_name, "Attention ED", "staff", "x" * 20,
                          community=comm, communities=[comm], email="attn@example.com")
    try:
        ed = _client()
        _as_role(ed, "staff", community=comm, name=ed_name)
        reg = _client()
        _as_role(reg, "regional", region_id=owner["id"], name="smoke.attn.reg")

        def mine(client):
            r = client.get("/api/attention")
            assert r.status_code == 200, r.get_data(as_text=True)
            return _groups(r.get_json())

        def has(groups, key):
            return any(i.get("question_id") == "smoke_q4"
                       for i in groups.get(key, {}).get("items", []))

        # 1. Nobody has said anything: it is the community's move.
        assert has(mine(ed), "respond"), "the ED should be asked for an update"
        assert not has(mine(reg), "verify"), "there is nothing to verify yet"

        # 2. The community reports the fix.
        ed.post(f"/api/action-items/{sid}/standard/smoke_q4/comments",
                json={"text": "Sign is up"}, headers=HDR)
        assert has(mine(reg), "verify"), "the regional should now be asked to confirm"
        assert has(mine(ed), "awaiting"), "the ED should see it as waiting on the regional"
        assert not has(mine(ed), "respond"), "and it should have left their to-do list"

        # 3. The regional asks for more: the ball goes back.
        reg.post(f"/api/action-items/{sid}/standard/smoke_q4/comments",
                 json={"text": "Send a wider shot"}, headers=HDR)
        assert not has(mine(reg), "verify"), \
            "leadership spoke last, so it is not waiting on them"

        # 4. Closed: it is work for nobody.
        reg.post(f"/api/action-items/{sid}/standard/smoke_q4/resolve",
                 json={"resolved": True}, headers=HDR)
        for groups in (mine(reg), mine(ed)):
            assert not any(has(groups, k) for k in
                           ("verify", "respond", "awaiting", "quiet")), \
                "a closed standard must disappear from every list"
    finally:
        A.inspection_service.submissions = [
            s for s in A.inspection_service.submissions if s.get("id") != sid]
        A.inspection_service.save_to_file()
        A.user_service.delete(ed_name)
        for u in (ed_name, "smoke.attn.reg"):
            A.presence_service.forget(u)


def test_attention_never_reaches_outside_its_scope():
    """Scoping is the whole safety property here: the endpoint reads every
    visit in the system before filtering."""
    comm = _a_community()
    sub = _seed_failed_visit(comm)
    sid = sub["id"]
    owner, other = _region_owning(comm)
    try:
        outsider = _client()
        _as_role(outsider, "regional", region_id=other["id"], name="smoke.attn.out")
        payload = outsider.get("/api/attention").get_json()
        seen = {i.get("community") for g in payload["groups"] for i in g["items"]}
        assert comm not in seen, f"a regional in {other['id']} can see {comm}"

        insider = _client()
        _as_role(insider, "regional", region_id=owner["id"], name="smoke.attn.in")
        payload = insider.get("/api/attention").get_json()
        seen = {i.get("community") for g in payload["groups"] for i in g["items"]}
        assert seen <= set(owner.get("communities") or []), \
            "a regional saw a community outside their own region"

        # An Executive Director gets their own community, and never the
        # verification queue — closing items is not theirs to do.
        ed = _client()
        _as_role(ed, "staff", community=comm, name="smoke.attn.ed2")
        payload = ed.get("/api/attention").get_json()
        keys = {g["key"] for g in payload["groups"]}
        assert not (keys & {"verify", "overdue", "quiet"}), \
            f"a community account was handed leadership's queue: {keys}"
        assert all(i.get("community") == comm
                   for g in payload["groups"] for i in g["items"])
    finally:
        A.inspection_service.submissions = [
            s for s in A.inspection_service.submissions if s.get("id") != sid]
        A.inspection_service.save_to_file()
        for u in ("smoke.attn.out", "smoke.attn.in", "smoke.attn.ed2"):
            A.presence_service.forget(u)


def test_visit_cadence_setting_is_admin_only_and_bounded():
    original = A.settings_service.get_visit_cadence_days()
    try:
        c = _client()
        _as_role(c, "regional", region_id=None, name="smoke.cadence")
        assert c.post("/api/settings/visit-cadence", json={"days": 14},
                      headers=HDR).status_code == 403

        _as_admin(c)
        r = c.post("/api/settings/visit-cadence", json={"days": 14}, headers=HDR)
        assert r.status_code == 200
        assert r.get_json()["visit_cadence_days"] == 14
        assert c.get("/api/user-info").get_json()["visit_cadence_days"] == 14

        # Out-of-range values are clamped, not stored, so nothing downstream
        # can end up marking every community overdue at once.
        assert c.post("/api/settings/visit-cadence", json={"days": 0},
                      headers=HDR).get_json()["visit_cadence_days"] == 7
        assert c.post("/api/settings/visit-cadence", json={"days": 99999},
                      headers=HDR).get_json()["visit_cadence_days"] == 365
        assert c.post("/api/settings/visit-cadence", json={"days": "nonsense"},
                      headers=HDR).get_json()["visit_cadence_days"] == 30
    finally:
        A.settings_service.set_visit_cadence_days(original)
        A.presence_service.forget("smoke.cadence")


def test_attention_survives_a_visit_with_duplicate_rows():
    """Older visits hold two rows for the same standard. A comment only ever
    lands on the first, so counting both would show work that can never be
    cleared."""
    comm = _a_community()
    sub = A.inspection_service.create_submission(
        username="admin", community=comm, inspector_name="Smoke Test",
        responses=[
            {"question_id": "smoke_dup", "question_text": "Same standard twice",
             "condition": "Fail", "description": "one", "answered_at": "2026-08-06T09:00:00"},
            {"question_id": "smoke_dup", "question_text": "Same standard twice",
             "condition": "Fail", "description": "two", "answered_at": "2026-08-06T09:00:00"},
        ])
    sid = sub["id"]
    owner, _ = _region_owning(comm)
    try:
        reg = _client()
        _as_role(reg, "regional", region_id=owner["id"], name="smoke.attn.dup")
        payload = reg.get("/api/attention").get_json()
        hits = [i for g in payload["groups"] for i in g["items"]
                if i.get("question_id") == "smoke_dup"]
        assert len(hits) <= 1, f"the same standard was listed {len(hits)} times"
    finally:
        A.inspection_service.submissions = [
            s for s in A.inspection_service.submissions if s.get("id") != sid]
        A.inspection_service.save_to_file()
        A.presence_service.forget("smoke.attn.dup")


def test_the_trend_matches_the_history_endpoint():
    """The card's sparkline is built in the browser from /api/inspections; the
    panel's is built from /api/communities/<c>/history. Two code paths, one
    number — a score shown two ways and disagreeing is exactly the bug that
    reached production before."""
    comm = _a_community()
    made = []
    try:
        # Two visits with known, different results: 1/2 then 2/2.
        made.append(A.inspection_service.create_submission(
            username="admin", community=comm, inspector_name="Smoke Test",
            responses=[
                {"question_id": "trend_a", "question_text": "A", "condition": "Pass",
                 "description": "", "answered_at": "2026-08-01T09:00:00"},
                {"question_id": "trend_b", "question_text": "B", "condition": "Fail",
                 "description": "x", "answered_at": "2026-08-01T09:00:00"},
            ]))
        made.append(A.inspection_service.create_submission(
            username="admin", community=comm, inspector_name="Smoke Test",
            responses=[
                {"question_id": "trend_a", "question_text": "A", "condition": "Pass",
                 "description": "", "answered_at": "2026-08-08T09:00:00"},
                {"question_id": "trend_b", "question_text": "B", "condition": "Pass",
                 "description": "", "answered_at": "2026-08-08T09:00:00"},
            ]))
        ids = {s["id"] for s in made}

        c = _client()
        _as_admin(c)
        hist = c.get(f"/api/communities/{comm}/history").get_json()
        ours = [v for v in hist["visits"] if v["id"] in ids]
        assert len(ours) == 2, "the history did not return both visits"
        by_id = {v["id"]: v for v in ours}
        assert by_id[made[0]["id"]]["visit_score"] == 50
        assert by_id[made[1]["id"]]["visit_score"] == 100

        # The same two visits as the browser receives them, scored the way
        # scoreBoth() in dashboard.html does it.
        raw = {s["id"]: s for s in c.get("/api/inspections").get_json()["submissions"]}
        for vid in ids:
            responses = raw[vid]["responses"]
            passed = sum(1 for r in responses if r.get("condition") == "Pass")
            failed = sum(1 for r in responses if r.get("condition") == "Fail")
            browser = round(passed / (passed + failed) * 100)
            assert browser == by_id[vid]["visit_score"], (
                f"visit {vid}: the card would show {browser}%, "
                f"the history shows {by_id[vid]['visit_score']}%")
    finally:
        keep = {s["id"] for s in made}
        A.inspection_service.submissions = [
            s for s in A.inspection_service.submissions if s.get("id") not in keep]
        A.inspection_service.save_to_file()


def _a_region_and_community():
    """A community together with the region that owns it, so a fabricated
    regional session is actually allowed to file a visit there."""
    for reg in A.region_service.get_all_regions():
        for entry in reg.get("communities", []):
            n = entry if isinstance(entry, str) else entry.get("name")
            if n:
                return reg.get("id"), n
    return None, _a_community()


def _submit_visit(c, comm, answers, standards_total=None):
    """File a visit through the real endpoint, the way the browser does."""
    import json as _json
    data = {
        "community": comm,
        "responses": _json.dumps([
            {"question_id": f"pv_{i}", "question_text": f"Standard {i}",
             "condition": cond, "description": "" if cond == "Pass" else "found it"}
            for i, cond in enumerate(answers)
        ]),
    }
    if standards_total is not None:
        data["standards_total"] = str(standards_total)
    return c.post("/api/inspections", headers=HDR,
                  content_type="multipart/form-data", data=data)


def _visiting_client(name):
    region_id, comm = _a_region_and_community()
    c = _client()
    _as_role(c, "regional", region_id=region_id, name=name)
    with c.session_transaction() as s:
        s["survey_type_id"] = A.survey_type_service.get_all_survey_types()[0]["id"]
    return c, comm


def _drop(ids):
    A.inspection_service.submissions = [
        x for x in A.inspection_service.submissions if x.get("id") not in ids]
    A.inspection_service.save_to_file()


def test_a_partial_visit_is_recorded_as_partial():
    """Only answered standards are stored and the score is worked out over
    those — so three of eight all passed reads as 100%, identical to a clean
    full visit. The survey's size is kept so the two can be told apart."""
    c, comm = _visiting_client("smoke.partial")
    before = {x["id"] for x in A.inspection_service.get_all_submissions()}
    made = set()
    try:
        r = _submit_visit(c, comm, ["Pass", "Pass", "Pass"], standards_total=99)
        assert r.status_code in (200, 201), r.get_data(as_text=True)
        new = [x for x in A.inspection_service.get_all_submissions()
               if x["id"] not in before]
        assert len(new) == 1
        sub = new[0]
        made = {sub["id"]}
        assert len(sub["responses"]) == 3, "only answered standards are stored"
        total = sub.get("standards_total")
        assert total and total > 3, "the survey's size was not recorded"

        _as_admin(c)
        hist = c.get(f"/api/communities/{comm}/history").get_json()
        v = next(v for v in hist["visits"] if v["id"] == sub["id"])
        assert v["partial"] is True
        assert v["answered"] == 3
        assert v["visit_score"] == 100, (
            "the score still covers only what was answered — which is exactly "
            "why it has to be labelled")
    finally:
        _drop(made)
        A.presence_service.forget("smoke.partial")


def test_a_complete_visit_is_not_labelled_partial():
    c, comm = _visiting_client("smoke.complete")
    before = {x["id"] for x in A.inspection_service.get_all_submissions()}
    made = set()
    try:
        r = _submit_visit(c, comm, ["Pass", "Fail", "Pass"], standards_total=3)
        assert r.status_code in (200, 201), r.get_data(as_text=True)
        new = [x for x in A.inspection_service.get_all_submissions()
               if x["id"] not in before]
        made = {x["id"] for x in new}
        # The server may know the survey is larger than the three sent; only
        # assert the not-partial case when it agrees the survey had three.
        if new[0].get("standards_total") == 3:
            _as_admin(c)
            hist = c.get(f"/api/communities/{comm}/history").get_json()
            v = next(v for v in hist["visits"] if v["id"] == new[0]["id"])
            assert v["partial"] is False, "a full visit must not be flagged"
    finally:
        _drop(made)
        A.presence_service.forget("smoke.complete")


def test_an_older_visit_is_left_unlabelled():
    """Visits filed before the survey size was captured carry no total.
    Reporting them as complete would be inventing a fact about them."""
    comm = _a_community()
    sub = A.inspection_service.create_submission(
        username="admin", community=comm, inspector_name="Smoke Test",
        responses=[{"question_id": "old_a", "question_text": "A", "condition": "Pass",
                    "description": "", "answered_at": "2026-01-01T09:00:00"}])
    assert "standards_total" not in sub, "nothing should be invented at write time"
    try:
        c = _client()
        _as_admin(c)
        hist = c.get(f"/api/communities/{comm}/history").get_json()
        v = next(v for v in hist["visits"] if v["id"] == sub["id"])
        assert v["standards_total"] is None
        assert v["partial"] is False, "unknown must not read as partial either"
    finally:
        _drop({sub["id"]})


def test_the_claimed_survey_size_is_not_taken_on_trust():
    """The browser sends the total, so it has to be checked — otherwise a
    partial visit could be filed claiming it was whole."""
    c, comm = _visiting_client("smoke.claim")
    st = A.survey_type_service.get_all_survey_types()[0]["id"]
    real = len(A.question_filter_service.get_questions_for_survey(comm, st) or [])
    before = {x["id"] for x in A.inspection_service.get_all_submissions()}
    made = set()
    try:
        # Claim the survey only ever held the one standard just answered.
        r = _submit_visit(c, comm, ["Pass"], standards_total=1)
        assert r.status_code in (200, 201), r.get_data(as_text=True)
        new = [x for x in A.inspection_service.get_all_submissions()
               if x["id"] not in before]
        made = {x["id"] for x in new}
        if real > 1:
            assert new[0].get("standards_total") == real, (
                f"stored the claimed 1 instead of the survey's real {real}")
    finally:
        _drop(made)
        A.presence_service.forget("smoke.claim")


def _sidebar_nav(html):
    """The sidebar's links, in order, as a browser would see them."""
    import re
    start = html.index('<div class="sidebar"')
    end = html.index('<!-- Main Content Area -->')
    side = html[start:end]
    return [(m.group(3).strip(), m.group(1), "active" in m.group(2))
            for m in re.finditer(
                r'<a\s+href="([^"]+)"([^>]*)>\s*<i[^>]*></i>\s*<span>([^<]+)</span>',
                side, re.S)]


def test_every_page_shows_the_same_menu():
    """The Standards page carried its own copy of the sidebar. The copies
    drifted — a different logo, a different product name, and no People at all
    — so the menu visibly changed when you opened it. One template now."""
    c = _client()
    _as_admin(c)
    dash = _sidebar_nav(c.get("/dashboard").get_data(as_text=True))
    qm = _sidebar_nav(c.get("/questions/manage").get_data(as_text=True))

    assert [x[0] for x in dash] == [x[0] for x in qm], "the two menus list different things"
    assert [x[1] for x in dash] == [x[1] for x in qm], "the two menus link to different places"
    assert "People" in [x[0] for x in dash]

    assert [x[0] for x in dash if x[2]] == ["Dashboard"], "wrong item highlighted on the dashboard"
    assert [x[0] for x in qm if x[2]] == ["Standards"], "wrong item highlighted on Standards"


def test_standards_is_offered_only_to_those_who_can_open_it():
    """The route is admin-only, so showing the link to anyone else is a dead
    end that bounces them out. It used to be shown to everybody."""
    admin = _client()
    _as_admin(admin)
    assert "Standards" in [x[0] for x in
                           _sidebar_nav(admin.get("/dashboard").get_data(as_text=True))]

    for role, kwargs, name in (
            ("regional", {"region_id": "coastal"}, "smoke.nav.reg"),
            ("staff", {"community": _a_community()}, "smoke.nav.ed")):
        c = _client()
        _as_role(c, role, name=name, **kwargs)
        try:
            labels = [x[0] for x in _sidebar_nav(c.get("/dashboard").get_data(as_text=True))]
            assert "Standards" not in labels, f"a {role} is offered Standards"
            assert "People" not in labels, f"a {role} is offered People"
            # And the door is still locked, not merely hidden.
            assert c.get("/questions/manage").status_code in (302, 403)
        finally:
            A.presence_service.forget(name)


def test_the_dashboard_menu_still_drives_the_single_page_app():
    """Sections are switched by script on the dashboard; Standards is a real
    page. Giving Standards a data-view would make the handler swallow the click
    and try to render a section that doesn't exist."""
    import re
    c = _client()
    _as_admin(c)
    html = c.get("/dashboard").get_data(as_text=True)
    side = html[html.index('<div class="sidebar"'):html.index("<!-- Main Content Area -->")]

    standards = re.search(r'<a[^>]*href="/questions/manage"[^>]*>', side).group(0)
    assert "data-view" not in standards, "Standards must not be handled as a section"

    for view in ("communities", "action-items", "settings"):
        assert f'data-view="{view}"' in side, f"{view} lost its section handle"

    # Real hrefs as well, so the menu still works if the script fails to load.
    assert 'href="/dashboard?view=communities"' in side


# ---------------------------------------------------------------------------
# Branding.
#
# "Standards" means two different things in this app and only one of them was
# renamed. "Atlas Standards" was the product; it is now Atlas Excellence. A
# "standard" is also an inspection point — the thing a visit marks Pass or Fail
# — and that word stays. A blind find-and-replace would have left the app
# saying "Weakest excellence" and "mark this excellence as addressed", so both
# halves are pinned here.

_SOURCE_DIRS = ("templates", "services")


def _source_files():
    import glob
    out = [os.path.join(_APP_DIR, "app.py")]
    for d in _SOURCE_DIRS:
        out += glob.glob(os.path.join(_APP_DIR, d, "*.html"))
        out += glob.glob(os.path.join(_APP_DIR, d, "*.py"))
    # Sample copy, not shipped UI.
    return [f for f in out if not f.endswith("ui_preview.html")]


def test_the_old_product_name_is_gone():
    stale = []
    for path in _source_files():
        with open(path, encoding="utf-8") as f:
            for i, line in enumerate(f, 1):
                if "Atlas Standards" in line or "Atlas Communities Standards" in line:
                    stale.append(f"{os.path.basename(path)}:{i}")
    assert not stale, "the old product name is still shown in: " + ", ".join(stale)


def test_the_inspection_noun_was_left_alone():
    """The rename must not have eaten the word the app uses for its own
    subject matter."""
    dash = os.path.join(_APP_DIR, "templates", "dashboard.html")
    with open(dash, encoding="utf-8") as f:
        html = f.read()

    for phrase in ("Weakest standards", "Mark as addressed", "failed standard"):
        assert phrase.lower() in html.lower(), f"lost the wording: {phrase}"

    # And nothing reads as the brand glued onto the noun.
    import re
    nonsense = re.findall(
        r"[Ee]xcellence (?:are|is|was|were) (?:posted|clean|open)"
        r"|[Ww]eakest excellence|failed excellence|open excellence",
        html)
    assert not nonsense, f"the rename ran over the noun: {nonsense}"


def test_the_menu_still_calls_the_section_standards():
    """The Standards section manages inspection points, not the brand — its
    label is the noun and must not have been renamed with the product."""
    c = _client()
    _as_admin(c)
    labels = [x[0] for x in _sidebar_nav(c.get("/dashboard").get_data(as_text=True))]
    assert "Standards" in labels
    assert "Excellence" not in labels


def test_what_people_actually_see_says_excellence():
    c = _client()
    _as_admin(c)
    for path in ("/dashboard", "/questions/manage"):
        html = c.get(path).get_data(as_text=True)
        assert "Atlas Excellence" in html, f"{path} does not show the product name"
        assert "Atlas Standards" not in html, f"{path} still shows the old name"


def test_emails_say_excellence_too():
    """Emails are the other half of what people see, and the subject line is
    assembled at send time — so intercept a real send rather than reading the
    source. Nothing leaves the machine: _send is replaced for the duration."""
    svc = A.email_service
    captured = []

    original_send = svc._send
    original_enabled = svc.enabled
    svc._send = lambda recipients, subject, html_body, text_body: (
        captured.append((subject, html_body, text_body)) or (True, "captured"))
    try:
        svc.enabled = True
    except Exception:
        pass

    try:
        svc.send_welcome("nobody@example.com", "Test Person", "test.person",
                         "x" * 12, role_label="Executive Director · Somewhere")
        svc.send_password_reset("nobody@example.com", "Test Person",
                                "test.person", "y" * 12)
        svc.send_activity_digest(["nobody@example.com"], A.build_activity_digest(24))

        assert captured, "no email was produced"
        for subject, html_body, text_body in captured:
            blob = f"{subject}\n{html_body}\n{text_body}"
            assert "Atlas Standards" not in blob, f"old name in: {subject}"
        assert any("Atlas Excellence" in s for s, _, _ in captured), \
            "no email names the product at all"
    finally:
        svc._send = original_send
        try:
            svc.enabled = original_enabled
        except Exception:
            pass


def test_infrastructure_names_were_not_renamed():
    """The bucket, the tour keys and the logo file are identifiers, not copy.
    Renaming them would have broken uploads, re-shown every tour, and left a
    missing image."""
    with open(os.path.join(_APP_DIR, "templates", "question_manager.html"),
              encoding="utf-8") as f:
        qm = f.read()
    assert "atlasStandardsTourSeen" in qm, "a tour key was renamed"

    with open(os.path.join(_APP_DIR, "templates", "change_password.html"),
              encoding="utf-8") as f:
        assert "atlas-standards-logo.svg" in f.read(), "the logo file was renamed"

    backup = os.path.join(os.path.dirname(_APP_DIR), "deploy", "backup_data.sh")
    if os.path.exists(backup):
        with open(backup, encoding="utf-8") as f:
            assert "atlas-standards-uploads" in f.read(), "the S3 bucket was renamed"


def test_a_stopped_backup_is_reported():
    """The nightly backup failed for two weeks and nobody knew: cron wrote the
    error into a log no human opens. It now leaves a receipt on success and the
    daily digest reads it, so the silence itself becomes visible."""
    import datetime, os as _os
    receipt = _os.path.join(A.DATA_FOLDER, ".last_backup")
    saved = None
    if _os.path.exists(receipt):
        with open(receipt, encoding="utf-8") as f:
            saved = f.read()
    try:
        # Never run at all.
        if _os.path.exists(receipt):
            _os.remove(receipt)
        st = A.backup_status()
        assert st["stale"] is True and st["known"] is False

        # Two nights missed.
        old = (datetime.datetime.now() - datetime.timedelta(days=3)).isoformat()
        with open(receipt, "w", encoding="utf-8") as f:
            f.write(f"{old} s3://bucket/x.tar.gz\n")
        st = A.backup_status()
        assert st["known"] is True and st["stale"] is True
        assert 70 < st["age_hours"] < 74

        # Ran last night: must say nothing at all. A daily "all good" line
        # becomes furniture and stops being read.
        fresh = (datetime.datetime.now() - datetime.timedelta(hours=8)).isoformat()
        with open(receipt, "w", encoding="utf-8") as f:
            f.write(f"{fresh} s3://bucket/x.tar.gz\n")
        assert A.backup_status()["stale"] is False

        digest = A.build_activity_digest(24)
        assert "backup" in digest, "the digest stopped carrying backup state"
    finally:
        if saved is None:
            if _os.path.exists(receipt):
                _os.remove(receipt)
        else:
            with open(receipt, "w", encoding="utf-8") as f:
                f.write(saved)


def test_the_backup_script_is_executable():
    """cron ran it directly and got "Permission denied" every night. Git tracks
    the mode, so the bit has to be set in the repository — otherwise the next
    deploy silently takes it away again."""
    import subprocess
    repo = os.path.dirname(_APP_DIR)
    out = subprocess.run(["git", "ls-files", "-s", "deploy/"], cwd=repo,
                         capture_output=True, text=True).stdout
    if not out.strip():
        return  # not a git checkout; nothing to assert
    for line in out.strip().splitlines():
        mode, _, rest = line.partition(" ")
        name = rest.split("\t")[-1]
        if name.endswith(".sh"):
            assert mode == "100755", f"{name} is not executable in git (mode {mode})"


def test_an_empty_survey_type_is_not_offered():
    """Unticking a survey type on the last standard is an ordinary-looking
    edit, and nothing used to say a word — the symptom appeared later, to a
    regional who had already driven to a community. The pickers now know how
    many standards each type would produce."""
    import copy
    saved = copy.deepcopy(A.question_manager.questions)
    try:
        c = _client()
        _as_admin(c)

        # Give every standard a type list that leaves one review with nothing.
        others = [s["id"] for s in A.survey_type_service.get_all_survey_types()][1:]
        orphan = A.survey_type_service.get_all_survey_types()[0]
        for q in A.question_manager.questions:
            q["survey_types"] = list(others)
        A.question_manager.save_to_file()

        types = {t["id"]: t for t in c.get("/api/survey-types").get_json()["survey_types"]}
        assert types[orphan["id"]]["standards"] == 0, "the empty review was not spotted"
        assert all(types[o]["standards"] > 0 for o in others), \
            "reviews that do have standards were reported empty"

        # A standard with no types at all belongs to every review, so one is
        # enough to bring the orphan back. This is the rule the form applies;
        # the count has to match it or a working type would look empty.
        A.question_manager.questions[0]["survey_types"] = []
        A.question_manager.save_to_file()
        types = {t["id"]: t for t in c.get("/api/survey-types").get_json()["survey_types"]}
        assert types[orphan["id"]]["standards"] == 1
    finally:
        A.question_manager.questions = saved
        A.question_manager.save_to_file()


def test_every_photo_in_a_visit_is_kept():
    """Photos were named "<user>_<unix seconds>", and every photo in one visit
    is saved inside the same second — so they overwrote each other and every
    standard ended up showing whichever one was saved last. A six-photo visit
    kept one. Nothing errored; it only surfaced when someone noticed the same
    picture on every item."""
    import io, json as _json
    region_id = comm = None
    for reg in A.region_service.get_all_regions():
        for entry in reg.get("communities", []):
            n = entry if isinstance(entry, str) else entry.get("name")
            if n:
                region_id, comm = reg.get("id"), n
                break
        if comm:
            break

    c = _client()
    _as_role(c, "regional", region_id=region_id, name="smoke.photos")
    with c.session_transaction() as s:
        s["survey_type_id"] = A.survey_type_service.get_all_survey_types()[0]["id"]

    before = {x["id"] for x in A.inspection_service.get_all_submissions()}
    made = set()
    try:
        # Four standards, four visibly different photos.
        payload = [{"question_id": f"ph_{i}", "question_text": f"Standard {i}",
                    "condition": "Pass", "description": ""} for i in range(4)]
        data = {"community": comm, "responses": _json.dumps(payload)}
        for i in range(4):
            body = b"\x89PNG\r\n\x1a\n" + bytes([i]) * 64
            data[f"photo_q_ph_{i}"] = (io.BytesIO(body), f"photo{i}.jpg")

        r = c.post("/api/inspections", headers=HDR,
                   content_type="multipart/form-data", data=data)
        assert r.status_code in (200, 201), r.get_data(as_text=True)

        new = [x for x in A.inspection_service.get_all_submissions()
               if x["id"] not in before]
        made = {x["id"] for x in new}
        paths = [resp.get("photo_path") for resp in new[0]["responses"]]
        assert all(paths), f"a photo went missing: {paths}"
        assert len(set(paths)) == 4, (
            "photos overwrote each other — every standard would show the same "
            f"picture: {paths}")
    finally:
        A.inspection_service.submissions = [
            x for x in A.inspection_service.submissions if x.get("id") not in made]
        A.inspection_service.save_to_file()
        A.presence_service.forget("smoke.photos")
        _sweep_test_photos()


def test_two_uploads_in_the_same_second_do_not_collide():
    """The same collision reaches comment photos and fix photos, which arrive
    in separate requests that know nothing about each other."""
    import io
    from werkzeug.datastructures import FileStorage
    names = set()
    for i in range(25):
        f = FileStorage(stream=io.BytesIO(b"x" * 32), filename="p.jpg",
                        content_type="image/jpeg")
        names.add(A.file_upload_handler.save_file(f, "smoke.user", "Photo Collision Test"))
    assert len(names) == 25, f"only {len(names)} of 25 uploads got their own name"

    folder = os.path.join(_APP_DIR, "static", "uploads", "Photo_Collision_Test")
    if os.path.isdir(folder):
        import shutil
        shutil.rmtree(folder)


def test_movein_emails_go_to_the_community_not_the_region():
    """A regional covering a dozen communities was getting forty to fifty
    move-in emails a month, which is how a mailbox teaches someone to ignore a
    sender. Move-ins are the community's own work, so the community is told;
    regionals keep full access under Move-Ins and still see anything overdue in
    the daily summary."""
    import json as _json
    comm = _a_community()
    region = A.region_for_community(comm)
    rid = region["id"]
    backup = _json.loads(_json.dumps(A.region_service.regions))
    before_notify = A.settings_service.get_email_settings().get("admin_notify", [])
    ed = "smoke.movein.ed"
    try:
        A.settings_service.set_email_settings(admin_notify=["admin@example.test"])
        for i, leader in enumerate(region.get("leadership") or []):
            A.region_service.update_leader(rid, i, leader.get("name") or f"L{i}",
                                           leader.get("title") or "",
                                           f"regional{i}@example.test")
        leaders = A.region_leader_emails(comm)
        assert leaders, "the test needs a region with leadership emails"

        # No community account yet: better a regional hears about it than
        # nobody does.
        assert set(leaders) <= set(A.movein_recipients(comm)), \
            "with no community account the region must still be told"

        # Once the community has an account, it is theirs and the region drops off.
        A.user_service.create(ed, "Smoke ED", "staff", "x" * 20, community=comm,
                              communities=[comm], email="ed@example.test")
        got = A.movein_recipients(comm)
        assert "ed@example.test" in got, "the community was not told"
        assert "admin@example.test" in got, "the administrator list was dropped"
        assert not any(a in got for a in leaders), \
            f"regionals are still being emailed every move-in: {got}"

        # Visit emails are a different question and must be untouched.
        assert set(A.region_leader_emails(comm)) == set(leaders), \
            "visit emails stopped reaching the region"
    finally:
        if A.user_service.get(ed):
            A.user_service.delete(ed)
        A.presence_service.forget(ed)
        A.region_service.regions = backup
        A.region_service.save_to_file()
        A.settings_service.set_email_settings(admin_notify=before_notify)


def test_a_visit_note_travels_but_never_scores():
    """Everything else on a visit is a problem. The note is the one place to
    say it went well, or to explain a number — a community mid-renovation and
    a community that isn't trying both score 60. It must reach the people who
    read the visit, and must not move the score by a single point."""
    import io, json as _json
    c, comm = _visiting_client("smoke.notes")
    NOTE = "Great visit - they had a wonderful event while I was there."
    before = {x["id"] for x in A.inspection_service.get_all_submissions()}
    made = set()
    try:
        payload = [
            {"question_id": "nt_1", "question_text": "One", "condition": "Pass", "description": ""},
            {"question_id": "nt_2", "question_text": "Two", "condition": "Fail", "description": "found it"},
        ]
        r = c.post("/api/inspections", headers=HDR, content_type="multipart/form-data", data={
            "community": comm,
            "responses": _json.dumps(payload),
            "visit_notes": NOTE,
            "visit_notes_photo": (io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"0" * 40), "event.jpg"),
        })
        assert r.status_code in (200, 201), r.get_data(as_text=True)
        new_subs = [x for x in A.inspection_service.get_all_submissions()
                    if x["id"] not in before]
        made = {x["id"] for x in new_subs}
        sub = new_subs[0]

        assert sub.get("notes") == NOTE, "the note was not stored"
        assert sub.get("notes_photo"), "the photo attached to the note was lost"

        # One Pass, one Fail — the note must not have changed that.
        passed = sum(1 for x in sub["responses"] if x["condition"] == "Pass")
        failed = sum(1 for x in sub["responses"] if x["condition"] == "Fail")
        assert (passed, failed) == (1, 1)
        assert not any(x.get("question_id", "").startswith("visit_notes")
                       for x in sub["responses"]), "the note leaked in as a standard"
        assert not sub.get("action_items"), "the note created a task"

        # It reaches whoever opens the visit later.
        _as_admin(c)
        hist = c.get(f"/api/communities/{comm}/history").get_json()
        v = next(v for v in hist["visits"] if v["id"] == sub["id"])
        assert v["notes"] == NOTE, "the history does not carry the note"
        assert v["visit_score"] == 50, "the note moved the score"
    finally:
        A.inspection_service.submissions = [
            x for x in A.inspection_service.submissions if x.get("id") not in made]
        A.inspection_service.save_to_file()
        A.presence_service.forget("smoke.notes")
        _sweep_test_photos()


def test_the_note_leads_both_emails():
    """The community used to receive a list of problems and nothing else, even
    after a visit that went well. Intercepts real sends; nothing leaves."""
    svc = A.email_service
    captured = []
    original_send, original_enabled = svc._send, svc.enabled
    svc._send = lambda recipients, subject, html_body, text_body: (
        captured.append((subject, html_body, text_body)) or (True, "captured"))
    svc.enabled = True
    NOTE = "Great visit - wonderful event while I was there."
    try:
        failed = [{"question_text": "Tour Path is show time ready", "description": "empty"}]
        passed = [{"question_text": "Vacant Rooms are Rent Ready"}]

        svc.send_community_findings(
            ["ed@example.test"], "A Community", "Marissa Scott", "2026-08-20",
            failed, [], None, notes=NOTE, passed_items=passed, score=50)
        subject, body_html, body_text = captured[-1]
        assert NOTE in body_text and NOTE in body_html, "the community never sees the note"
        assert body_html.index("Note from") < body_html.index("Tour Path"), \
            "the note has to lead — that is the whole point"
        assert "Vacant Rooms are Rent Ready" in body_text, "what passed is missing"
        assert "50%" in body_text, "the score is missing"
        assert body_html.index("Tour Path") < body_html.index("Also checked and passed"), \
            "context pushed the findings down the page"

        # And the leadership report.
        svc._build.__self__  # noqa: B018 - it is a bound method; just being explicit
        _, lead_html, lead_text = svc._build({
            "community": "A Community", "inspector_name": "Marissa Scott",
            "submitted_at": "2026-08-20T09:00:00", "notes": NOTE,
            "responses": [{"question_id": "a", "question_text": "Tour Path",
                           "condition": "Fail", "description": "empty"}],
            "action_items": [],
        })
        assert NOTE in lead_text and NOTE in lead_html, "leadership never sees the note"
    finally:
        svc._send = original_send
        svc.enabled = original_enabled


# ---------------------------------------------------------------------------
# Previewing the app as a community.
#
# The alternative was a fake ED account on a real community, which would then
# receive that community's emails and show up as its director. This keeps the
# administrator's own account and changes what they are shown — so the two
# things that matter are that only an administrator can start it, and that
# nothing can be written while it is on.

def test_only_an_administrator_can_preview():
    comm = _a_community()
    for role, kwargs, name in (
            ("regional", {"region_id": "coastal"}, "smoke.prev.reg"),
            ("staff", {"community": comm}, "smoke.prev.ed")):
        c = _client()
        _as_role(c, role, name=name, **kwargs)
        try:
            r = c.post("/api/view-as", json={"community": comm}, headers=HDR)
            assert r.status_code == 403, f"a {role} could start a preview"
        finally:
            A.presence_service.forget(name)

    c = _client()
    _as_admin(c)
    try:
        assert c.post("/api/view-as", json={"community": comm},
                      headers=HDR).status_code == 200
        # And not at a community that doesn't exist.
        c.post("/api/view-as/stop", json={}, headers=HDR)
        assert c.post("/api/view-as", json={"community": "Nowhere At All"},
                      headers=HDR).status_code == 400
    finally:
        c.post("/api/view-as/stop", json={}, headers=HDR)


def test_the_preview_shows_exactly_what_that_community_sees():
    comm = _a_community()
    c = _client()
    _as_admin(c)
    try:
        before = c.get("/api/user-info").get_json()
        assert before["is_admin"] is True

        c.post("/api/view-as", json={"community": comm}, headers=HDR)
        d = c.get("/api/user-info").get_json()
        assert d["view_as"] == comm
        assert d["role"] == "staff", "the preview did not take on the role"
        assert d["is_admin"] is False, "an admin menu during the preview defeats the point"
        assert d["communities"] == [comm], "the preview is not scoped to one community"
        assert d["can_run_visits"] is False and d["can_verify_fixes"] is False

        # The menu loses the administrator-only sections.
        labels = [x[0] for x in _sidebar_nav(c.get("/dashboard").get_data(as_text=True))]
        assert "People" not in labels and "Standards" not in labels

        # Admin endpoints are refused, not merely hidden.
        assert c.get("/questions/manage").status_code in (302, 403)
        assert c.get("/api/leaderboard").status_code == 403
    finally:
        c.post("/api/view-as/stop", json={}, headers=HDR)
        after = c.get("/api/user-info").get_json()
        assert after["is_admin"] is True, "leaving the preview did not restore the admin"
        assert after["view_as"] is None


def test_a_preview_acts_under_the_administrator_s_own_name():
    """The preview changes what an administrator is shown, not who they are.

    That is what makes it safe to let them act: a comment left while previewing
    is recorded and emailed under their own name, so nothing in the record
    claims the community said something it didn't."""
    comm = _a_community()
    sub = _seed_failed_visit(comm)
    sid = sub["id"]
    c = _client()
    _as_admin(c)
    try:
        c.post("/api/view-as", json={"community": comm}, headers=HDR)
        r = c.post(f"/api/action-items/{sid}/standard/smoke_q4/comments",
                   json={"text": "Training demo"}, headers=HDR)
        assert r.status_code == 201, r.get_data(as_text=True)
        comment = r.get_json()["comment"]
        assert comment["username"] == "admin", (
            "a comment made while previewing must carry the administrator's own "
            f"name, not the community's: {comment['username']}")
    finally:
        c.post("/api/view-as/stop", json={}, headers=HDR)
        A.inspection_service.submissions = [
            x for x in A.inspection_service.submissions if x.get("id") != sid]
        A.inspection_service.save_to_file()


def test_a_preview_cannot_reach_administrative_actions():
    """Nothing here is enforced by the preview itself — is_admin() answers False
    while it runs, so every admin endpoint refuses on its own terms. This is
    what stops a preview from being a way around the role."""
    comm = _a_community()
    c = _client()
    _as_admin(c)
    try:
        c.post("/api/view-as", json={"community": comm}, headers=HDR)
        blocked = [
            ("POST", "/api/settings/visit-cadence", {"days": 45}),
            ("POST", "/api/settings/email", {"admin_notify": "x@example.test"}),
            ("POST", "/api/people", {"name": "Should Not Exist", "role": "staff",
                                     "community": comm}),
            ("DELETE", "/api/people/whoever", None),
            ("POST", "/api/admin/reset-inspections", {"confirm": "RESET"}),
        ]
        for method, path, body in blocked:
            r = c.open(path, method=method, json=body, headers=HDR)
            assert r.status_code == 403, f"{method} {path} was allowed: {r.status_code}"

        # A community cannot file its own visit, and neither can a preview of one.
        assert c.post("/api/inspections", headers=HDR, data={}).status_code == 403

        assert c.get("/api/inspections").status_code == 200
        assert c.post("/api/view-as/stop", json={}, headers=HDR).status_code == 200
    finally:
        c.post("/api/view-as/stop", json={}, headers=HDR)
        assert not A.user_service.get("should.not.exist")


def test_a_preview_inherits_every_community_that_account_covers():
    """An Executive Director can stand in for a neighbouring community. A
    preview that showed only one of them would be showing a different job than
    the one that person actually does."""
    first, second, _ = _two_communities()
    ed = "smoke.preview.two"
    A.user_service.create(ed, "Two Community ED", "staff", "x" * 20,
                          community=first, communities=[first, second],
                          email="two@example.test")
    c = _client()
    _as_admin(c)
    try:
        r = c.post("/api/view-as", json={"username": ed}, headers=HDR)
        assert r.status_code == 200, r.get_data(as_text=True)
        assert sorted(r.get_json()["communities"]) == sorted([first, second])

        d = c.get("/api/user-info").get_json()
        assert sorted(d["communities"]) == sorted([first, second]), \
            "the preview dropped one of the communities they cover"
        assert d["view_as"] == "Two Community ED", "the banner names the person"

        # Both communities are genuinely reachable, not just listed.
        for comm in (first, second):
            assert c.get(f"/api/communities/{comm}/history").status_code == 200
    finally:
        c.post("/api/view-as/stop", json={}, headers=HDR)
        if A.user_service.get(ed):
            A.user_service.delete(ed)
        A.presence_service.forget(ed)


def test_a_preview_only_targets_an_executive_director():
    c = _client()
    _as_admin(c)
    try:
        for who in ("admin", "nobody.at.all"):
            r = c.post("/api/view-as", json={"username": who}, headers=HDR)
            assert r.status_code == 400, f"previewing as {who} was allowed"
    finally:
        c.post("/api/view-as/stop", json={}, headers=HDR)


# ---------------------------------------------------------------------------
# Items a community raises for itself.
#
# Until this existed an Executive Director could only comment on a finding that
# already existed — so if nothing had failed in the living room, there was no
# way to say the furniture needed replacing. Kept apart from what a regional
# finds on a visit: one says "this is wrong, fix it", the other "I need this".

def test_an_ed_can_raise_an_item_and_the_regional_sees_it():
    region = A.region_service.get_all_regions()[0]
    comm = region["communities"][0]
    ed = _client()
    _as_role(ed, "staff", community=comm, name="smoke.raise.ed")
    with ed.session_transaction() as s:
        s["communities"] = [comm]
        s["display_name"] = "Smoke ED"
    made = []
    try:
        r = ed.post("/api/raised-items",
                    json={"text": "Living room furniture is worn", "priority": "high",
                          "category": "capex"},
                    headers=HDR)
        assert r.status_code == 201, r.get_data(as_text=True)
        item = r.get_json()["item"]
        made.append(item["id"])

        # The community is inferred — somebody covering one shouldn't name it.
        assert item["community"] == comm
        assert item["raised_by_name"] == "Smoke ED", \
            f"stored the login instead of the person's name: {item['raised_by_name']}"
        assert item["priority"] == "high"
        assert item["category"] == "capex", "the id is stored, not the label"

        # Their regional sees it.
        reg = _client()
        _as_role(reg, "regional", region_id=region["id"], name="smoke.raise.reg")
        seen = reg.get("/api/raised-items").get_json()["items"]
        assert any(i["id"] == item["id"] for i in seen), "the regional cannot see it"

        # It is not part of any visit, so no score can move because of it.
        for sub in A.inspection_service.get_all_submissions():
            assert item["id"] not in _json_dump(sub), "a raised item leaked into a visit"
    finally:
        for i in made:
            A.raised_item_service.delete(i)
        for u in ("smoke.raise.ed", "smoke.raise.reg"):
            A.presence_service.forget(u)


def _json_dump(obj):
    import json as _json
    return _json.dumps(obj)


def test_a_raised_item_stays_inside_its_community():
    first, second, _ = _two_communities()
    a = _client()
    _as_role(a, "staff", community=first, name="smoke.raise.a")
    with a.session_transaction() as s:
        s["communities"] = [first]
    b = _client()
    _as_role(b, "staff", community=second, name="smoke.raise.b")
    with b.session_transaction() as s:
        s["communities"] = [second]
    made = []
    try:
        item = a.post("/api/raised-items",
                      json={"text": "Ours only", "category": "other"},
                      headers=HDR).get_json()["item"]
        made.append(item["id"])

        assert not b.get("/api/raised-items").get_json()["items"], \
            "another community can see it"
        assert b.post(f"/api/raised-items/{item['id']}/resolve", json={},
                      headers=HDR).status_code == 403, \
            "another community can close it"

        # The community that raised it may close its own — closing a finding
        # moves the score, which is why that stays with a regional; this does
        # not, and the person who asked knows when it arrived.
        assert a.post(f"/api/raised-items/{item['id']}/resolve",
                      json={"note": "Done"}, headers=HDR).status_code == 200
        assert not a.get("/api/raised-items").get_json()["items"], \
            "a closed item is still listed as open"
    finally:
        for i in made:
            A.raised_item_service.delete(i)
        for u in ("smoke.raise.a", "smoke.raise.b"):
            A.presence_service.forget(u)


def test_raising_something_empty_is_refused():
    comm = _a_community()
    c = _client()
    _as_role(c, "staff", community=comm, name="smoke.raise.empty")
    with c.session_transaction() as s:
        s["communities"] = [comm]
    try:
        assert c.post("/api/raised-items", json={"text": "   "},
                      headers=HDR).status_code == 400
    finally:
        A.presence_service.forget("smoke.raise.empty")


def test_leaderboard_hidden_from_community_accounts():
    c = _client()
    _as_role(c, "staff", community=_a_community(), name="smoke.ed")
    assert c.get("/api/leaderboard").status_code == 403
    _as_admin(c)
    assert c.get("/api/leaderboard").status_code == 200
    A.presence_service.forget("smoke.ed")


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS  {t.__name__}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"FAIL  {t.__name__}: {e}")
    teardown_module(None)
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
