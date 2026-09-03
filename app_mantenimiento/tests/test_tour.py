"""
Every step of the walkthrough points at something that is really there.

A step whose target has been renamed does not fail: the card still opens and
the ring points at nothing. It looks like the app rather than like a broken
tour, so nobody reports it — it just quietly stops teaching that thing. That
happened to "Start a visit", which pointed at #startVisitBtn after the button
a regional actually sees became the + that offers two actions.

This has to run against the page as Flask renders it. The sidebar builds its
items in a Jinja loop, so half the targets are not literal in any template and
reading the files reports every nav item as missing — a wall of noise that
gets switched off, taking the one real failure with it.

Run locally, never on the server.
"""

import os
import re
import sys

import pytest

_APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

import app as A  # noqa: E402

_TEMPLATE = os.path.join(_APP_DIR, "templates", "dashboard.html")

# Targets built by JavaScript after the page loads — a row in a list, a card
# for a region. Listed rather than skipped by pattern, so a typo in one of the
# static selectors is still caught.
BUILT_AT_RUNTIME = {
    "#gallery .card", "#gallery .cal-cell.cal-has",
    ".ppl-row", ".ppl-actions", ".ppl-toolbar .btn-primary", ".ppl-chips",
    ".mi-row", ".mi-card", ".mi-phase", ".mi-attach-btn",
    ".region-card", ".region-leader", ".region-addleader-btn",
    ".region-card-corporate", ".region-leader-actions",
    ".rg-card", ".rg-head", ".rg-leaders", ".rg-comm",
    ".cal-month", ".cal-legend", "#calFilterBar",
    "[data-card=\"live\"]", "#dashMainGrid",
    "#moveInNewBtn", "#moveInTemplateBtn", "#moveInPrintBlankBtn", "#moveInSearch",
}


def _rendered_dashboard():
    c = A.app.test_client()
    with c.session_transaction() as s:
        s.update(user="admin", role="admin", community=None, region_id=None,
                 display_name="admin")
    r = c.get("/dashboard")
    assert r.status_code == 200
    return r.get_data(as_text=True)


def _targets():
    with open(_TEMPLATE, encoding="utf-8") as f:
        return sorted(set(re.findall(r"target:\s*'([^']+)'", f.read())))


def _present(page, selector):
    """Whether the rendered page contains an element the selector would find.

    Only the three shapes the tours actually use, matched against the markup:
    an id, a plain class, and a class with one attribute. Deliberately not a
    general CSS engine — a half-written one that quietly matches nothing would
    make every assertion here pass.
    """
    m = re.fullmatch(r"#([\w-]+)", selector)
    if m:
        return f'id="{m.group(1)}"' in page

    m = re.fullmatch(r"\.([\w-]+)\[([\w-]+)=\"([^\"]+)\"\]", selector)
    if m:
        cls, attr, val = m.groups()
        for tag in re.findall(r"<[^>]*%s=\"%s\"[^>]*>" % (re.escape(attr), re.escape(val)), page):
            if re.search(r'class="[^"]*\b%s\b' % re.escape(cls), tag):
                return True
        return False

    m = re.fullmatch(r"\.([\w-]+)", selector)
    if m:
        return re.search(r'class="[^"]*\b%s\b' % re.escape(m.group(1)), page) is not None

    return None   # a shape this cannot judge


def test_the_matcher_can_actually_fail():
    """Guards the guard.

    Every other assertion here is only worth anything if this one holds: a
    matcher that answers True to everything, or that silently gives up on the
    shapes in use, would make the whole file green and meaningless.
    """
    page = _rendered_dashboard()
    assert _present(page, "#tourCard") is True
    assert _present(page, "#definitely-not-in-this-page") is False
    assert _present(page, '.nav-item[data-view="dashboard"]') is True
    assert _present(page, '.nav-item[data-view="not-a-view"]') is False
    assert _present(page, ".tour-card") is True
    assert _present(page, ".not-a-class-anywhere") is False


def test_every_step_points_at_something_that_exists():
    page = _rendered_dashboard()
    unjudgeable, missing = [], []
    for selector in _targets():
        if selector in BUILT_AT_RUNTIME:
            continue
        answer = _present(page, selector)
        if answer is None:
            unjudgeable.append(selector)
        elif not answer:
            missing.append(selector)

    assert not unjudgeable, \
        f"the matcher cannot judge these, so they are untested: {unjudgeable}"
    assert not missing, \
        ("these steps point at nothing on the page, so the tour teaches them "
         f"to an empty corner of the screen: {missing}")


def test_the_start_visit_step_follows_the_button_that_exists():
    """The one that had already gone stale.

    A regional is shown the + that offers both actions, not #startVisitBtn.
    """
    with open(_TEMPLATE, encoding="utf-8") as f:
        html = f.read()
    regional = html[html.index("regional: ["):html.index("staff: [")]
    assert "#startVisitBtn" not in regional, \
        "the regional tour still points at the button they are not shown"
    assert "#fabMenuBtn" in regional


def test_there_are_steps_for_each_audience():
    with open(_TEMPLATE, encoding="utf-8") as f:
        html = f.read()
    block = html[html.index("const TOUR_STEPS"):html.index("function startTour")]
    for audience in ("admin:", "regional:", "staff:"):
        assert audience in block, f"no walkthrough for {audience}"
    assert block.count("target:") >= 20
