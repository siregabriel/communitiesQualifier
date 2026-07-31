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
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
