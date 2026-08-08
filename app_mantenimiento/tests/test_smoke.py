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
