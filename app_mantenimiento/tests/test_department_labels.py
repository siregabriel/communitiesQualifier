"""
A department reads as its name, everywhere it is shown.

The "Who should handle it?" dropdown stores the department's id so renaming
one cannot orphan the items filed under it. That decision is right and it had
a consequence nobody checked: every place that printed the field raw started
showing people the id. "For: admin-personnel" went out in a visit email to
Greg, Angie, Wyman and Scott.

Five places display it — the community email, the leadership report, that
report's plain-text part, the activity line, and the card in Action Items.
Patching five display sites is how the sixth one, written next month, gets it
wrong again; they all read one resolved field now.

Run locally, never on the server.
"""

import os
import sys

import pytest

_APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

import app as A  # noqa: E402


def _a_department():
    d = next((c for c in A.raised_category_service.active()
              if c["id"] != c["name"]), None)
    if not d:
        pytest.skip("needs a department whose id differs from its name")
    return d


# ----------------------------------------------------------- the resolver

def test_it_puts_the_name_beside_the_id():
    d = _a_department()
    out = A._with_department_names([{"text": "The cell phones are down",
                                     "assigned_to": d["id"]}])
    assert out[0]["assigned_to_name"] == d["name"]
    assert out[0]["assigned_to"] == d["id"], "the reference itself does not move"


def test_the_id_is_never_what_a_person_reads():
    """The bug, stated as the thing it looked like."""
    d = _a_department()
    out = A._with_department_names([{"assigned_to": d["id"]}])
    assert out[0]["assigned_to_name"] != d["id"] or d["id"] == d["name"]
    assert "-" not in out[0]["assigned_to_name"] or " " in out[0]["assigned_to_name"] \
        or "/" in out[0]["assigned_to_name"], \
        f'"{out[0]["assigned_to_name"]}" still reads like a slug'


def test_an_item_with_no_department_is_left_alone():
    out = A._with_department_names([{"text": "x"}, {"text": "y", "assigned_to": ""}])
    assert "assigned_to_name" not in out[0]
    assert "assigned_to_name" not in out[1]


def test_a_department_recorded_as_text_still_reads():
    """Items saved before the dropdown stored ids hold the name itself."""
    out = A._with_department_names([{"assigned_to": "Nursing / Wellness"}])
    assert out[0]["assigned_to_name"] == "Nursing / Wellness"


def test_a_department_that_no_longer_exists_reads_as_itself():
    """Better than blank: whatever was stored is at least what was chosen."""
    out = A._with_department_names([{"assigned_to": "Some Team We Retired"}])
    assert out[0]["assigned_to_name"] == "Some Team We Retired"


def test_nothing_in_gives_nothing_out():
    assert A._with_department_names(None) == []
    assert A._with_department_names([]) == []


# ------------------------------------------------- where it has to arrive

def test_the_emails_read_the_name_and_fall_back_to_the_id():
    """All three outputs, in the service that formats them."""
    path = os.path.join(_APP_DIR, "services", "email_service.py")
    with open(path, encoding="utf-8") as f:
        src = f.read()
    shown = src.count("assigned_to_name")
    assert shown >= 3, \
        f"only {shown} of the three email outputs read the resolved name"
    assert "esc(i.get('assigned_to'))" not in src, \
        "an email still prints the id straight out"


def test_the_activity_line_resolves_it():
    path = os.path.join(_APP_DIR, "app.py")
    with open(path, encoding="utf-8") as f:
        src = f.read()
    assert 'f"For: {_department_label(' in src, \
        "the activity line still records the id as the department"


def test_the_card_prefers_the_name():
    path = os.path.join(_APP_DIR, "templates", "dashboard.html")
    with open(path, encoding="utf-8") as f:
        src = f.read()
    assert "item.assigned_to_name || item.assigned_to" in src


def test_the_api_sends_the_name_to_the_browser(monkeypatch):
    """Whatever the card prefers is only there if the server put it there.

    The submission is fabricated and handed to the real route, rather than
    skipped when no visit on file happens to carry a department — a skip here
    is the end-to-end step going unchecked, and it is the step that failed.
    Nothing is written: the service is asked for this one instead.
    """
    d = _a_department()
    fake = {
        "id": "smoke-dept-label",
        "username": "smoke.dept",
        "community": (A.all_communities() or ["Somewhere"])[0],
        "submitted_at": "2026-09-10T10:00:00",
        "survey_type_id": "standards",
        "responses": [{"question_id": "q1", "condition": "Pass"}],
        "action_items": [
            {"id": "a1", "text": "The cell phones are still not working",
             "assigned_to": d["id"], "priority": "high", "resolved": False},
            {"id": "a2", "text": "No department on this one", "resolved": False},
        ],
    }
    monkeypatch.setattr(A.inspection_service, "get_all_submissions", lambda: [fake])

    c = A.app.test_client()
    with c.session_transaction() as s:
        s.update(user="admin", role="admin", community=None, region_id=None,
                 display_name="admin")
    got = c.get("/api/inspections").get_json()["submissions"]

    items = {i["id"]: i for i in got[0]["action_items"]}
    assert items["a1"]["assigned_to_name"] == d["name"], \
        "the browser is being handed the id with no name beside it"
    assert items["a1"]["assigned_to"] == d["id"], "and the reference is still there"
    assert "assigned_to_name" not in items["a2"], \
        "an item with no department did not gain an empty one"


def test_the_leadership_report_gets_them_resolved_too():
    """It reads the action items off the submission itself, so resolving the
    list handed to the other email does not reach it — which is exactly where
    "admin-personnel" was seen."""
    path = os.path.join(_APP_DIR, "app.py")
    with open(path, encoding="utf-8") as f:
        src = f.read()
    call = src[src.index("email_service.send_inspection_report("):]
    call = call[:call.index(")") + 1]
    assert "_with_department_names" in call, \
        "the leadership report is still handed the submission unresolved"
