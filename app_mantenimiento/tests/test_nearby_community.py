"""
The visit form offers the community you are standing in.

Gabriel's idea: a regional who opens Excellence in a community's lobby should
not have to scroll a list of seven — or Carol's thirty-nine — to find the
building they are standing in. The phone knows where it is; the map already
knows where each community is.

What the server does is small and is what these check: it writes into the
page the positions of the communities this person can already visit, and
nothing else. The comparison with the phone's location happens in the
browser, so where anybody is never reaches the server.

Run locally, never on the server.
"""

import json
import os
import re
import sys

import pytest

_APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

import app as A  # noqa: E402
from services.place_service import PlaceService  # noqa: E402

PLACES = {
    'Alpha Place': {'lat': 33.84, 'lng': -84.37},
    'Bravo Place': {'lat': 34.02, 'lng': -84.36},
    'Charlie Place': {'lat': 28.56, 'lng': -81.54},
}


@pytest.fixture
def form(monkeypatch, tmp_path):
    p = tmp_path / 'places.json'
    p.write_text(json.dumps({'places': PLACES}), encoding='utf-8')
    monkeypatch.setattr(A, 'place_service', PlaceService(str(p)))
    types = [t for t in A.survey_type_service.get_all_survey_types() if t.get('id')]
    if not types:
        pytest.skip('needs a survey type')

    def page(communities, role='regional'):
        monkeypatch.setattr(A, 'regional_communities', lambda: list(communities))
        c = A.app.test_client()
        with c.session_transaction() as s:
            s.update(user='test.reg', role=role, region_id='north',
                     display_name='Test', survey_type_id=types[0]['id'],
                     survey_type_name=types[0].get('name', ''))
        r = c.get('/reporte')
        assert r.status_code == 200, r.status_code
        html = r.get_data(as_text=True)
        m = re.search(r'const COMMUNITY_PLACES = (.*?);\n', html)
        assert m, 'the positions are not in the page at all'
        return json.loads(m.group(1))
    return page


def test_the_page_carries_the_positions_of_your_communities(form):
    places = form(['Alpha Place', 'Bravo Place'])
    assert {p['community'] for p in places} == {'Alpha Place', 'Bravo Place'}
    alpha = next(p for p in places if p['community'] == 'Alpha Place')
    assert (alpha['lat'], alpha['lng']) == (33.84, -84.37)


def test_and_only_yours(form):
    """A list of every building in the company in the page source would be
    the map's old scoping mistake by another route."""
    places = form(['Alpha Place', 'Bravo Place'])
    assert 'Charlie Place' not in {p['community'] for p in places}


def test_name_and_position_only(form):
    """Who confirmed a position and when is nobody's business on a visit form."""
    for p in form(['Alpha Place', 'Bravo Place']):
        assert set(p) == {'community', 'lat', 'lng'}, p


def test_nothing_for_somebody_with_one_community(form):
    """There is nothing to pick, so nothing to suggest — and no reason for the
    phone to ask for their location."""
    assert form(['Alpha Place']) == []


def test_a_community_with_no_position_is_simply_not_offered(form):
    places = form(['Alpha Place', 'Somewhere Unplaced'])
    assert [p['community'] for p in places] == ['Alpha Place']


def test_the_server_is_never_sent_a_location():
    """The comparison happens in the browser: nothing between asking the phone
    and showing the suggestion makes a request."""
    with open(os.path.join(_APP_DIR, 'templates', 'reporte.html'), encoding='utf-8') as f:
        html = f.read()
    i = html.index('const COMMUNITY_PLACES')
    body = html[i:html.index('function onCommunityChange(', i)]
    assert 'fetch(' not in body and 'XMLHttpRequest' not in body and 'sendBeacon' not in body, \
        'the position is being sent somewhere'
