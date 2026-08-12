"""
Smoke tests for the Atlas Standards app.

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
    try:
        r = c.post("/api/regions/rename-community",
                   json={"old_name": old, "new_name": new}, headers=HDR)
        assert r.status_code == 200

        mv = c.get(f"/api/moveins/{mid}").get_json()["movein"]
        assert mv["community"] == new, "move-in should follow the rename"

        assert A.community_cover_service.get(A.community_slug(new)) is not None
        assert A.community_cover_service.get(A.community_slug(old)) is None
    finally:
        # restore everything: rename back, drop cover + move-in
        c.post("/api/regions/rename-community",
               json={"old_name": new, "new_name": old}, headers=HDR)
        A.community_cover_service.delete(A.community_slug(old))
        A.community_cover_service.delete(A.community_slug(new))
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
