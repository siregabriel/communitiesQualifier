"""
One department list, and something actually arriving at the end of it.

Greg asked what happens when somebody picks "Maintenance" on an action item.
The answer was nothing: that dropdown was a list written into the visit form,
which he could not edit, storing a word that nobody read. Meanwhile three
other lists existed for the same idea — the categories he does edit, three
fixed routes on standards, and the address boxes in Settings — none of them
connected to another.

They are one list now. What has to hold:

  * nobody who was being emailed stops being emailed, which is the failure
    that announces itself weeks later and never as a bug report;
  * an option that existed in the old form still exists, because an option
    that quietly disappears is one nobody notices until the work is gone;
  * records already written keep working, whether they hold an id or the name
    that used to be stored as text.

Run locally, never on the server.
"""

import json
import os
import sys
import tempfile

import pytest

_APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

import app as A  # noqa: E402
from services.raised_category_service import (  # noqa: E402
    DEFAULT_CATEGORIES, LEGACY_DEPARTMENTS, RaisedCategoryService,
)

HDR = {"Origin": "http://localhost", "Referer": "http://localhost/"}

# What the visit form offered before any of this. Nothing here may vanish.
OLD_FORM_OPTIONS = [
    "Nursing / Wellness", "Dietary", "Maintenance", "Housekeeping",
    "Lifestyles", "Business Office", "Executive Director", "Sales",
    "Clinical", "Operations",
]


@pytest.fixture
def svc():
    return RaisedCategoryService(os.path.join(tempfile.mkdtemp(), "cats.json"))


# ------------------------------------------------------- nothing disappears

def test_every_option_the_old_form_had_still_exists(svc):
    """An option that goes missing is not reported, it is worked around."""
    names = {c["name"].lower() for c in svc.all()}
    for option in OLD_FORM_OPTIONS:
        assert option.lower() in names, f'"{option}" is no longer offered to anyone'


def test_the_departments_folded_in_are_choosable(svc):
    active = {c["name"] for c in svc.active()}
    for name in LEGACY_DEPARTMENTS:
        assert name in active


def test_greg_s_own_categories_are_untouched(svc):
    names = [c["name"] for c in svc.all()]
    assert names[:len(DEFAULT_CATEGORIES)] == DEFAULT_CATEGORIES, \
        "his list should still lead, in his order"


def test_adding_the_departments_twice_changes_nothing(svc):
    before = len(svc.all())
    svc.ensure_departments()
    svc.ensure_departments()
    assert len(svc.all()) == before, "it ran again and duplicated the list"


def test_an_installation_that_predates_them_gets_them(svc):
    """The upgrade path: seeded before these existed."""
    svc.categories = [c for c in svc.categories
                      if c["name"] not in LEGACY_DEPARTMENTS]
    svc.save_to_file()
    added = svc.ensure_departments()
    assert {c["name"] for c in added} == set(LEGACY_DEPARTMENTS)
    assert svc.id_for_name("Housekeeping")


# -------------------------------------------------------------- recipients

def test_a_department_with_nobody_on_it_is_not_an_error(svc):
    """Empty is a real answer: the notice still goes where it always went."""
    assert svc.recipients_for(svc.id_for_name("Dining")) == []
    assert svc.recipients_for("no-such-department") == []
    assert svc.recipients_for("") == []


def test_setting_them_from_a_pasted_line(svc):
    cid = svc.id_for_name("Maintenance")
    svc.set_recipients(cid, "michael@atlasseniorliving.com, ricky@atlasseniorliving.com")
    assert svc.recipients_for(cid) == ["michael@atlasseniorliving.com",
                                       "ricky@atlasseniorliving.com"]


def test_one_bad_address_does_not_cost_the_others(svc):
    """A person pasting a list should not lose nine because of one typo."""
    cid = svc.id_for_name("Dining")
    svc.set_recipients(cid, "ricky@atlas.com, not-an-address, carol@atlas.com")
    assert svc.recipients_for(cid) == ["ricky@atlas.com", "carol@atlas.com"]


def test_the_same_address_twice_is_kept_once(svc):
    cid = svc.id_for_name("Dining")
    svc.set_recipients(cid, "a@x.com, A@X.com, b@x.com")
    assert svc.recipients_for(cid) == ["a@x.com", "b@x.com"]


def test_renaming_a_department_keeps_its_recipients(svc):
    """The id does not move, so nothing filed under it is orphaned."""
    cid = svc.id_for_name("Lifestyles")
    svc.set_recipients(cid, "carol@atlas.com")
    svc.rename(cid, "Life Enrichment")
    assert svc.recipients_for(cid) == ["carol@atlas.com"]
    assert svc.id_for_name("Life Enrichment") == cid


# ------------------------------------------- an id or a name, both resolve

def test_a_department_resolves_by_id_and_by_name():
    """Action items written before this hold the name as free text."""
    assert A._department("maintenance")["name"] == "Maintenance"
    assert A._department("Maintenance")["name"] == "Maintenance"
    assert A._department("Nursing / Wellness")["name"] == "Nursing / Wellness"
    assert A._department("nothing-like-this") is None
    assert A._department("") is None


def test_a_label_falls_back_to_what_was_stored():
    """A department retired since should still read as itself, not as blank."""
    assert A._department_label("maintenance") == "Maintenance"
    assert A._department_label("Some Old Team") == "Some Old Team"
    assert A._department_label("") == ""


# --------------------------------------------------- it actually arrives

def test_raising_something_reaches_the_department(monkeypatch):
    """Greg's question, answered.

    Pick Maintenance and Michael hears about it, on top of the regional who
    was always told. Every other test here checks a field; this one checks
    that an email is addressed to the right people.
    """
    sent = {}
    monkeypatch.setattr(A.email_service, "enabled", True)
    monkeypatch.setattr(A.email_service, "send_raised_item",
                        lambda to, item: sent.update(to=list(to), item=item))
    monkeypatch.setattr(A, "region_leader_emails", lambda c: ["marissa@atlas.com"])
    monkeypatch.setattr(A.raised_category_service, "recipients_for",
                        lambda cid: ["michael@atlas.com"] if cid == "maintenance" else [])

    A.notify_raised_item({"community": "Kelley Place", "category": "maintenance",
                          "text": "Dryer vent is blocked"})
    assert sent.get("to") == ["marissa@atlas.com", "michael@atlas.com"], \
        "the department was chosen and nobody there was told"


def test_a_department_nobody_configured_still_reaches_the_regional(monkeypatch):
    """The old behaviour has to survive an empty list, not be replaced by it."""
    sent = {}
    monkeypatch.setattr(A.email_service, "enabled", True)
    monkeypatch.setattr(A.email_service, "send_raised_item",
                        lambda to, item: sent.update(to=list(to)))
    monkeypatch.setattr(A, "region_leader_emails", lambda c: ["marissa@atlas.com"])
    monkeypatch.setattr(A.raised_category_service, "recipients_for", lambda cid: [])

    A.notify_raised_item({"community": "Kelley Place", "category": "dining", "text": "x"})
    assert sent.get("to") == ["marissa@atlas.com"]


def test_somebody_on_both_lists_is_emailed_once(monkeypatch):
    sent = {}
    monkeypatch.setattr(A.email_service, "enabled", True)
    monkeypatch.setattr(A.email_service, "send_raised_item",
                        lambda to, item: sent.update(to=list(to)))
    monkeypatch.setattr(A, "region_leader_emails", lambda c: ["greg@atlas.com"])
    monkeypatch.setattr(A.raised_category_service, "recipients_for",
                        lambda cid: ["GREG@atlas.com"])

    A.notify_raised_item({"community": "Kelley Place", "category": "sales", "text": "x"})
    assert sent.get("to") == ["greg@atlas.com"], "the same person twice in one To:"


# --------------------------------------------------- carrying the old ones

def test_the_addresses_already_configured_are_carried_over(monkeypatch, svc):
    """Nobody stops being emailed because the lists were merged."""
    monkeypatch.setattr(A, "raised_category_service", svc)
    monkeypatch.setattr(A.settings_service, "get_email_settings",
                        lambda: {"clinical": ["nurse@atlas.com"],
                                 "sales": ["greg@atlas.com"],
                                 "ops": ["ops@atlas.com"],
                                 "admin_notify": [], "subscribers": []})
    A._fold_routes_into_departments()
    assert svc.recipients_for(svc.id_for_name("Clinical")) == ["nurse@atlas.com"]
    assert svc.recipients_for(svc.id_for_name("Sales")) == ["greg@atlas.com"]
    assert svc.recipients_for(svc.id_for_name("Operations")) == ["ops@atlas.com"]


def test_it_does_not_overwrite_what_greg_has_since_set(monkeypatch, svc):
    """Runs on every boot, so it must never undo an edit."""
    monkeypatch.setattr(A, "raised_category_service", svc)
    monkeypatch.setattr(A.settings_service, "get_email_settings",
                        lambda: {"clinical": ["old@atlas.com"], "sales": [], "ops": [],
                                 "admin_notify": [], "subscribers": []})
    cid = svc.id_for_name("Clinical")
    svc.set_recipients(cid, "whoever.greg.chose@atlas.com")
    A._fold_routes_into_departments()
    assert svc.recipients_for(cid) == ["whoever.greg.chose@atlas.com"]


# ---------------------------------------------------------------- the api

def _admin():
    c = A.app.test_client()
    with c.session_transaction() as s:
        s.update(user="admin", role="admin", community=None, region_id=None,
                 display_name="admin")
    return c


def _ed():
    comms = A.all_communities()
    if not comms:
        pytest.skip("needs a community")
    c = A.app.test_client()
    with c.session_transaction() as s:
        s.update(user="smoke.dept.ed", role="staff", community=comms[0],
                 communities=[comms[0]], display_name="ED")
    return c


def test_an_administrator_sees_the_address_lists():
    d = _admin().get("/api/raised-categories?all=1").get_json()
    assert d["categories"], "no departments came back"
    assert any("recipients" in c for c in d["categories"])


def test_everybody_else_gets_the_list_without_the_addresses():
    """An Executive Director picks a department; they are not handed the
    address book to do it."""
    d = _ed().get("/api/raised-categories").get_json()
    assert d["categories"], "no departments came back"
    for c in d["categories"]:
        assert "recipients" not in c, "the endpoint is handing out the address list"
        assert c.get("id") and c.get("name"), "but it still has what it needs to choose"


def test_only_an_administrator_can_change_them():
    cid = A.raised_category_service.active()[0]["id"]
    r = _ed().put(f"/api/raised-categories/{cid}",
                  json={"recipients": "sneak@example.com"}, headers=HDR)
    assert r.status_code == 403


def test_the_visit_form_carries_departments_but_not_addresses():
    """The list is serialised into the page, so it must be id and name only."""
    comms = A.all_communities()
    types = [t for t in A.survey_type_service.get_all_survey_types() if t.get("id")]
    if not comms or not types:
        pytest.skip("needs a community and a survey type")
    c = A.app.test_client()
    with c.session_transaction() as s:
        s.update(user="smoke.dept.reg", role="regional", community=None,
                 region_id=None, display_name="R",
                 survey_type_id=types[0]["id"], survey_type_name=types[0].get("name", ""))
    page = c.get("/reporte").get_data(as_text=True)
    if "AI_DEPARTMENTS" not in page:
        pytest.skip("the form did not render for this session")
    line = next(l for l in page.splitlines() if "const AI_DEPARTMENTS" in l)
    payload = json.loads(line.split("=", 1)[1].strip().rstrip(";"))
    assert payload, "the dropdown would be empty"
    for d in payload:
        assert set(d) == {"id", "name"}, f"the page is carrying {set(d) - {'id', 'name'}}"
