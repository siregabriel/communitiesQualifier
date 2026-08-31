"""
Text that a template prints itself, rather than handing to JavaScript.

Everything is escaped on the way in, so "Angie's" is stored as "Angie&#x27;s".
Most of the app renders through escapeHtml in the browser, but a handful of
places print straight from Jinja — the community list on the visit form, the
labels in Standards Manager, the printable standards sheet. Those escape a
second time and put the entity on the page.

The `plain` filter undoes the storage escaping. What has to stay true is that
Jinja's own autoescaping still runs after it, so undoing the first pass cannot
turn stored text into live markup.

Run locally, never on the server.
"""

import html
import os
import sys

_APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

from flask import render_template_string  # noqa: E402

import app as A  # noqa: E402


def render(template, **ctx):
    """Render through the real app, so the real filter and the real
    autoescaping setting are the ones under test."""
    with A.app.app_context():
        return render_template_string(template, **ctx)


def shown(stored):
    """What the browser puts on screen for a stored value.

    Jinja escapes again on output, so the rendered HTML for "Angie's" is
    "Angie&#39;s" — correct, and the browser draws an apostrophe. Comparing the
    raw HTML would fail against working code, so decode one pass to get the
    visible text, which is what the complaint was actually about.
    """
    return html.unescape(render("{{ v|plain }}", v=stored))


def test_an_apostrophe_reads_as_an_apostrophe():
    """The reported bug, in the server-rendered half."""
    assert shown("Angie&#x27;s walk through") == "Angie's walk through"


def test_the_other_escaped_characters_come_back_too():
    for stored, typed in [("Tom &amp; Jerry", "Tom & Jerry"),
                          ("He said &quot;ok&quot;", 'He said "ok"'),
                          ("2nd &lt; 3rd", "2nd < 3rd")]:
        assert shown(stored) == typed, stored


def test_without_the_filter_the_entity_is_what_people_see():
    """Pins the bug itself, so this cannot pass again by accident."""
    assert html.unescape(render("{{ v }}", v="Angie&#x27;s")) == "Angie&#x27;s"


def test_it_cannot_turn_stored_text_into_markup():
    """The whole risk of undoing an escape.

    Jinja escapes again on output, so the tags have to come back out as text.
    If this ever renders a real <script>, the filter has become an XSS hole.
    """
    out = render("{{ v|plain }}", v="&lt;script&gt;alert(1)&lt;/script&gt;")
    assert "<script>" not in out, "stored text became live markup"
    assert "&lt;script&gt;" in out, "it should be shown, as text"


def test_an_onerror_payload_stays_text():
    out = render("{{ v|plain }}", v="&lt;img src=x onerror=alert(1)&gt;")
    assert "<img" not in out
    assert "&lt;img src=x onerror=alert(1)&gt;" in out


def test_it_leaves_everything_else_alone():
    assert render("{{ v|plain }}", v="Painted; 100% done") == "Painted; 100% done"
    assert render("{{ v|plain }}", v=None) == "None", "non-strings pass through"
    assert render("{{ v|plain }}", v=12) == "12"


def test_the_visit_form_keeps_the_stored_name_as_the_option_value():
    """Display and value are deliberately different.

    The option's text is for the person; its value is what gets posted back and
    compared against the roster, which holds the escaped form. Prettifying the
    value too would break resuming a draft for a community whose name has an
    apostrophe in it.
    """
    tpl = os.path.join(_APP_DIR, "templates", "reporte.html")
    with open(tpl, encoding="utf-8") as f:
        html = f.read()
    assert '<option value="{{ c }}">{{ c|plain }}</option>' in html
