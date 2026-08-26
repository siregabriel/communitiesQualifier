"""
Categories on the items a community raises.

Greg asked for these so the items could be filtered, and for the list to be
his and Angie's to run. The two things worth holding down:

  * an item stores the category's id, so renaming one reaches every past item
    at once and nothing needs migrating — the mistake that was made with
    community names, which cost a regional a wasted trip;

  * retiring a category never deletes it, so the items already carrying it keep
    reading correctly instead of showing a blank chip.

Run locally, never on the server.
"""

import os
import sys
import tempfile

import pytest

_APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

import app as A  # noqa: E402
from services.raised_category_service import RaisedCategoryService  # noqa: E402

HDR = {"Origin": "http://localhost", "Referer": "http://localhost/"}
_FAKE_USERS = ("smoke.cat.ed", "smoke.cat.admin")


def teardown_module(module):
    for u in _FAKE_USERS:
        try:
            A.presence_service.forget(u)
        except Exception:
            pass


@pytest.fixture
def svc():
    """A throwaway store, so these never touch the real list."""
    return RaisedCategoryService(os.path.join(tempfile.mkdtemp(), "cats.json"))


# ------------------------------------------------------------- the service

def test_it_seeds_the_list_greg_asked_for(svc):
    names = [c["name"] for c in svc.active()]
    for expected in ["CapEx", "Sales", "Clinical", "Maintenance",
                     "Dining", "Lifestyles", "Admin/Personnel", "Other"]:
        assert expected in names, f"{expected} is missing from the starting list"
    assert "Dinning" not in names, "the typo from the email did not make it in"


def test_other_is_there_because_the_field_is_required(svc):
    """Without an escape hatch people pick a wrong category to get past the form."""
    assert any(c["id"] == "other" for c in svc.active())


def test_renaming_keeps_the_id_so_past_items_follow(svc):
    """The whole reason items store an id instead of a name."""
    before = svc.get("capex")["id"]
    svc.rename("capex", "Capital Projects")
    assert svc.get("capex")["id"] == before, "the id moved; every past item would be orphaned"
    assert svc.name_for("capex") == "Capital Projects", "and the new name is what shows"


def test_retiring_hides_it_without_losing_it(svc):
    svc.set_active("lifestyles", False)
    assert "lifestyles" not in [c["id"] for c in svc.active()], "gone from the dropdown"
    assert "lifestyles" in [c["id"] for c in svc.all()], "but still on record"
    assert svc.name_for("lifestyles") == "Lifestyles", \
        "an item that chose it still reads correctly"
    assert not svc.is_choosable("lifestyles"), "and nobody can choose it again"


def test_a_retired_category_can_come_back(svc):
    svc.set_active("dining", False)
    svc.set_active("dining", True)
    assert svc.is_choosable("dining")


def test_the_last_choosable_category_cannot_be_retired(svc):
    """Retiring everything would leave a required field with nothing to pick."""
    ids = [c["id"] for c in svc.active()]
    for cid in ids[:-1]:
        svc.set_active(cid, False)
    assert len(svc.active()) == 1
    assert svc.set_active(ids[-1], False) is None
    assert len(svc.active()) == 1


def test_names_are_not_duplicated(svc):
    assert svc.create("Sales") is None, "a second Sales helps nobody"
    assert svc.create("  sales  ") is None, "including one that only differs by case"
    assert svc.create("Transportation") is not None


def test_a_new_category_gets_a_usable_id(svc):
    cat = svc.create("Life Safety / Fire")
    assert cat["id"] == "life-safety-fire"
    assert svc.name_for(cat["id"]) == "Life Safety / Fire"


def test_an_item_from_before_categories_existed_says_so(svc):
    assert svc.name_for("") == "Uncategorised"
    assert svc.name_for("a-category-that-was-never-created") == "Uncategorised"


def test_reordering_changes_the_dropdown_order(svc):
    ids = [c["id"] for c in svc.active()]
    svc.reorder(list(reversed(ids)))
    assert [c["id"] for c in svc.active()] == list(reversed(ids))


# ---------------------------------------------------------------- the api

def _ed(community):
    c = A.app.test_client()
    with c.session_transaction() as s:
        s.update(user="smoke.cat.ed", role="staff", community=community,
                 communities=[community], display_name="Smoke ED", region_id=None)
    return c


def _admin():
    c = A.app.test_client()
    with c.session_transaction() as s:
        s.update(user="smoke.cat.admin", role="admin", community=None,
                 display_name="Smoke Admin", region_id=None)
    return c


def _a_community():
    comms = A.all_communities()
    if not comms:
        pytest.skip("needs a community in the roster")
    return comms[0]


def test_raising_without_a_category_is_refused():
    """Required, or the filter Greg asked for fills with uncategorised items."""
    c = _ed(_a_community())
    r = c.post("/api/raised-items", json={"text": "No category on this one"}, headers=HDR)
    assert r.status_code == 400
    assert "categor" in r.get_json()["message"].lower()


def test_an_invented_category_is_refused():
    c = _ed(_a_community())
    r = c.post("/api/raised-items",
               json={"text": "Made up", "category": "not-a-real-category"}, headers=HDR)
    assert r.status_code == 400


def test_raising_with_a_category_stores_the_id_and_returns_the_label():
    community = _a_community()
    c = _ed(community)
    r = c.post("/api/raised-items",
               json={"text": "Living room furniture is worn", "category": "capex"},
               headers=HDR)
    assert r.status_code == 201, r.get_data(as_text=True)
    item = r.get_json()["item"]
    try:
        assert item["category"] == "capex", "the id is what is stored"
        listed = c.get("/api/raised-items").get_json()
        mine = next(i for i in listed["items"] if i["id"] == item["id"])
        assert mine["category_name"] == A.raised_category_service.name_for("capex"), \
            "the label is resolved on read, so a rename reaches it"
        assert listed["categories"], "the list ships the choices alongside the items"
    finally:
        A.raised_item_service.delete(item["id"])


def test_only_an_admin_may_change_the_list():
    c = _ed(_a_community())
    assert c.post("/api/raised-categories", json={"name": "Sneaky"},
                  headers=HDR).status_code == 403
    assert c.put("/api/raised-categories/capex", json={"name": "Sneaky"},
                 headers=HDR).status_code == 403
    assert c.post("/api/raised-categories/order", json={"ids": []},
                  headers=HDR).status_code == 403


def test_an_admin_sees_retired_ones_too():
    c = _admin()
    everyone = c.get("/api/raised-categories").get_json()["categories"]
    admin_view = c.get("/api/raised-categories?all=1").get_json()["categories"]
    assert len(admin_view) >= len(everyone)


def test_an_ed_is_never_shown_the_retired_ones():
    c = _ed(_a_community())
    shown = c.get("/api/raised-categories?all=1").get_json()["categories"]
    assert all(cat.get("active", True) for cat in shown), \
        "asking for all does not get an ED the retired ones"


# ------------------------------------------------- what the regional reads

def test_the_email_carries_the_label_not_the_id():
    """A regional triaging their inbox should not have to read "capex"."""
    from services.email_service import EmailService
    svc = EmailService(mail_from="atlas@example.com", region="us-east-1")
    sent = {}

    def _capture(recipients, subject, html_body, text_body, **kw):
        sent.update(subject=subject, html=html_body, text=text_body)
        return (True, "captured")

    svc._send = _capture           # never actually reaches SES
    svc.enabled = True
    svc.send_raised_item(["regional@example.com"], {
        "community": "Kelley Place, Enterprise",
        "raised_by_name": "Jazmyn Frazier",
        "text": "Living room furniture is worn",
        "priority": "high",
        # Deliberately one whose id and label differ by more than case —
        # "capex" lowercases to the same string as "CapEx", so it could not
        # tell the two apart.
        "category": "admin-personnel",
        "category_name": "Admin/Personnel",
    })
    assert sent, "the email was never built"
    assert "Admin/Personnel" in sent["html"], "the label is missing from the email"
    assert "Admin/Personnel" in sent["text"], "and from the plain-text copy"
    assert "admin-personnel" not in sent["html"], "the raw id must not be shown"


def test_an_older_item_without_a_category_still_emails_cleanly():
    from services.email_service import EmailService
    svc = EmailService(mail_from="atlas@example.com", region="us-east-1")
    sent = {}
    svc._send = lambda r, s, h, t, **kw: (sent.update(html=h, text=t), (True, "ok"))[1]
    svc.enabled = True
    svc.send_raised_item(["regional@example.com"], {
        "community": "Kelley Place, Enterprise",
        "raised_by_name": "Jazmyn Frazier",
        "text": "From before categories existed",
        "priority": "low",
    })
    assert sent, "the email was never built"
    assert "None" not in sent["html"], "an absent category must not print as None"
    assert "&middot;" not in sent["html"], "nor leave a dangling separator"
