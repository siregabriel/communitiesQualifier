"""
The communities map.

A map is read differently from a list. Nobody audits a pin — if it is on
screen, in a state, with a colour, that is taken as fact. So the three ways
this feature can lie quietly are what most of these are about:

  - Showing somebody a community they could not already open. A map is an
    unusually easy place for that to happen, because the natural way to build
    one is to fetch everything and let the page draw what fits.
  - Putting a community in the wrong place. Fourteen of the thirty-nine names
    carry no city and nine of those name a development rather than a town, so
    a coordinate is never derived from a name — and a community with no entry
    is named above the map rather than dropped somewhere plausible.
  - Painting a stale score green. A community nobody has visited in two
    months still has its last score on file. "We have not looked" has to read
    differently from "it is fine".

Run locally, never on the server.
"""

import json
import os
import sys
from datetime import datetime, timedelta

import pytest

_APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

import app as A  # noqa: E402
from services.place_service import PlaceService  # noqa: E402

HEADERS = {'Origin': 'http://localhost', 'Referer': 'http://localhost/'}


def ago(days):
    return (datetime.now() - timedelta(days=days)).isoformat()


def visit(community, score_passes=9, fails=1, days=5, sid='s1'):
    responses = [{'question_id': f'p{i}', 'condition': 'Pass'}
                 for i in range(score_passes)]
    responses += [{'question_id': f'f{i}', 'condition': 'Fail'} for i in range(fails)]
    return {'id': sid, 'community': community, 'submitted_at': ago(days),
            'responses': responses, 'action_items': []}


# ------------------------------------------------------- the reference file

def test_every_community_this_machine_knows_about_has_a_position():
    """Worth having, and weaker than it looks.

    all_communities() reads the roster on *this* machine, and a development
    roster is not production's. The Georgian at Lakeside was live and missing
    from the reference file, and this test was green the whole time — the
    banner above the map is what found it, which is the argument for keeping
    that banner rather than trusting this.
    """
    svc = PlaceService()
    missing = svc.unplaced(A.all_communities())
    assert missing == [], f'no location on file for: {missing}'


def test_nothing_landed_in_the_ocean():
    """A swapped sign or a transposed digit is the likely typo here, and it
    puts a pin hundreds of miles out. Caught on load rather than on screen."""
    svc = PlaceService()
    assert svc.rejected() == [], f'impossible coordinates: {svc.rejected()}'


def test_a_bad_coordinate_is_dropped_not_drawn(tmp_path):
    p = tmp_path / 'places.json'
    p.write_text(json.dumps({'places': {
        'Good One': {'lat': 33.7, 'lng': -84.4, 'city': 'Atlanta', 'state': 'GA'},
        # Both halves of the box, because a check on one and not the other
        # reads identically until somebody deletes the wrong line.
        'Sign Flipped': {'lat': 33.7, 'lng': 84.4, 'city': 'Nowhere', 'state': 'GA'},
        'Wrong Hemisphere': {'lat': -33.7, 'lng': -84.4},
        'Off The Top': {'lat': 61.2, 'lng': -84.4},
        'Not A Number': {'lat': 'x', 'lng': -84.4},
    }}), encoding='utf-8')
    svc = PlaceService(str(p))
    every = ['Good One', 'Sign Flipped', 'Wrong Hemisphere', 'Off The Top', 'Not A Number']
    assert [r['community'] for r in svc.placed(every)] == ['Good One']
    assert svc.rejected() == ['Not A Number', 'Off The Top',
                              'Sign Flipped', 'Wrong Hemisphere']


def test_a_missing_community_is_named_not_guessed(tmp_path):
    p = tmp_path / 'places.json'
    p.write_text(json.dumps({'places': {
        'Placed': {'lat': 33.7, 'lng': -84.4}}}), encoding='utf-8')
    svc = PlaceService(str(p))
    assert svc.placed(['Placed', 'Unplaced']) == [
        {'lat': 33.7, 'lng': -84.4, 'city': '', 'state': '', 'verified': False,
         'note': '', 'community': 'Placed'}]
    assert svc.unplaced(['Placed', 'Unplaced']) == ['Unplaced']


def test_a_broken_file_does_not_take_the_app_down(tmp_path):
    p = tmp_path / 'places.json'
    p.write_text('{ this is not json', encoding='utf-8')
    svc = PlaceService(str(p))
    assert svc.placed(['Anything']) == []
    assert svc.unplaced(['Anything']) == ['Anything']


def test_the_confirmed_flag_still_means_something():
    """The map stopped showing a count of unconfirmed positions — it said the
    same thing every morning until somebody reviewed all forty, and a banner
    that never changes is a banner nobody reads. The flag stayed in the data
    so it can be surfaced per pin the day that is worth doing, and a flag
    nothing reads is a flag that quietly becomes wrong."""
    svc = PlaceService()
    everything = list(svc._places)
    assert svc.unverified(everything), \
        'every position is marked confirmed, which nobody has done'


# --------------------------------------------------------------- the colour

def test_the_bands():
    assert A._map_band(95, 3) == 'good'
    assert A._map_band(90, 3) == 'good'
    assert A._map_band(89, 3) == 'watch'
    assert A._map_band(75, 3) == 'watch'
    assert A._map_band(74, 3) == 'poor'
    assert A._map_band(0, 3) == 'poor'


def test_a_stale_score_is_not_a_good_score():
    """The one that matters. A 96 from four months ago is not evidence that
    the place is fine today, and green says it is."""
    assert A._map_band(96, A.MAP_STALE_DAYS + 1) == 'stale'
    assert A._map_band(96, A.MAP_STALE_DAYS) == 'good', 'the boundary moved'


def test_never_visited_is_stale_too():
    assert A._map_band(None, None) == 'stale'
    assert A._map_band(88, None) == 'stale'


def test_the_score_is_the_one_the_card_shows():
    """Passes plus anything since fixed, over everything answered — the same
    arithmetic as scoreBoth. A map that disagrees with the panel it links to
    is a map nobody trusts twice."""
    assert A._current_score([{'condition': 'Pass'}] * 9 + [{'condition': 'Fail'}]) == 90
    assert A._current_score(
        [{'condition': 'Pass'}] * 9 + [{'condition': 'Fail', 'addressed': True}]) == 100
    assert A._current_score([]) is None
    assert A._current_score([{'condition': 'N/A'}]) is None


# ------------------------------------------------------------- the scoping

@pytest.fixture
def as_regional(monkeypatch):
    """A regional covering two of the three communities in play."""
    monkeypatch.setattr(A, 'visible_communities',
                        lambda: ['Madison at Ocoee, Ocoee', 'Madison at Oviedo, Oviedo'])
    monkeypatch.setattr(A, 'can_see_internal', lambda: True)
    monkeypatch.setattr(A.inspection_service, 'get_all_submissions', lambda: [
        visit('Madison at Ocoee, Ocoee', 9, 1, days=5, sid='a'),
        visit('Madison at Oviedo, Oviedo', 6, 4, days=5, sid='b'),
        visit('The Goldton at Stuart', 10, 0, days=5, sid='c'),
    ])
    monkeypatch.setattr(A.raised_item_service, 'for_communities', lambda *a, **k: [])
    c = A.app.test_client()
    with c.session_transaction() as s:
        s.update(user='test.regional', role='regional', region_id='innovia',
                 display_name='Test Regional')
    return c


def test_a_regional_is_not_handed_the_whole_company(as_regional):
    r = as_regional.get('/api/map/communities', headers=HEADERS)
    assert r.status_code == 200
    names = [c['community'] for c in r.get_json()['communities']]
    assert names == ['Madison at Ocoee, Ocoee', 'Madison at Oviedo, Oviedo']
    assert 'The Goldton at Stuart' not in names, \
        'a community outside the region came down to the browser'


def test_nor_told_which_ones_it_is_missing(as_regional, monkeypatch, tmp_path):
    """unplaced is scoped too — otherwise the names of every community in the
    company arrive in a list nobody was looking at.

    This needs a community with no position to mean anything. All thirty-nine
    real ones have one, so an earlier version of this passed while asserting
    nothing: both lists were empty either way.
    """
    p = tmp_path / 'places.json'
    p.write_text(json.dumps({'places': {
        'Madison at Ocoee, Ocoee': {'lat': 28.5692, 'lng': -81.5434},
        'Madison at Oviedo, Oviedo': {'lat': 28.6700, 'lng': -81.2081},
    }}), encoding='utf-8')
    monkeypatch.setattr(A, 'place_service', PlaceService(str(p)))

    body = as_regional.get('/api/map/communities', headers=HEADERS).get_json()
    assert body['unplaced'] == [], 'the regional\'s own two are placed'
    assert all('Stuart' not in n for n in body['unplaced']), \
        'a community outside the region was named in the gaps list'
    assert all('Stuart' not in n for n in body['unverified'])


def test_a_gap_inside_your_own_region_is_named(as_regional, monkeypatch, tmp_path):
    """The other half: scoping must not become silence."""
    p = tmp_path / 'places.json'
    p.write_text(json.dumps({'places': {
        'Madison at Ocoee, Ocoee': {'lat': 28.5692, 'lng': -81.5434},
    }}), encoding='utf-8')
    monkeypatch.setattr(A, 'place_service', PlaceService(str(p)))

    body = as_regional.get('/api/map/communities', headers=HEADERS).get_json()
    assert body['unplaced'] == ['Madison at Oviedo, Oviedo']
    assert [c['community'] for c in body['communities']] == ['Madison at Ocoee, Ocoee']


def test_the_scores_come_from_the_right_visits(as_regional):
    r = as_regional.get('/api/map/communities', headers=HEADERS)
    by = {c['community']: c for c in r.get_json()['communities']}
    assert by['Madison at Ocoee, Ocoee']['score'] == 90
    assert by['Madison at Oviedo, Oviedo']['score'] == 60
    assert by['Madison at Ocoee, Ocoee']['band'] == 'good'
    assert by['Madison at Oviedo, Oviedo']['band'] == 'poor'


def test_a_stale_community_comes_down_hollow(monkeypatch):
    monkeypatch.setattr(A, 'visible_communities', lambda: ['Madison at Ocoee, Ocoee'])
    monkeypatch.setattr(A, 'can_see_internal', lambda: True)
    monkeypatch.setattr(A.inspection_service, 'get_all_submissions',
                        lambda: [visit('Madison at Ocoee, Ocoee', 10, 0,
                                       days=A.MAP_STALE_DAYS + 10)])
    monkeypatch.setattr(A.raised_item_service, 'for_communities', lambda *a, **k: [])
    c = A.app.test_client()
    with c.session_transaction() as s:
        s.update(user='test.regional', role='regional', region_id='innovia')
    row = c.get('/api/map/communities', headers=HEADERS).get_json()['communities'][0]
    assert row['score'] == 100
    assert row['band'] == 'stale', 'a four-month-old 100 was painted green'


def test_signed_out_gets_nothing():
    r = A.app.test_client().get('/api/map/communities')
    assert r.status_code in (302, 401), r.status_code


# ------------------------------------------------------- the page around it

def test_the_switch_is_hidden_from_somebody_with_one_community():
    """For an Executive Director the map is a single pin. Offering it is the
    first step towards a map of buildings that are not theirs."""
    with open(os.path.join(_APP_DIR, 'templates', 'dashboard.html'),
              encoding='utf-8') as f:
        html = f.read()
    i = html.index('function updateCommunityLayoutSwitch')
    body = html[i:i + 500]
    assert 'currentUserCommunities' in body and 'length > 1' in body
    assert 'sw.hidden = !many' in body


def test_leaving_communities_puts_the_list_back():
    """Otherwise the gallery stays hidden under a map that is no longer on
    screen, and the next section looks empty."""
    with open(os.path.join(_APP_DIR, 'templates', 'dashboard.html'),
              encoding='utf-8') as f:
        html = f.read()
    i = html.index('function showView(view)')
    body = html[i:i + 1200]
    assert "view !== 'communities'" in body
    assert 'g.hidden = false' in body


def test_the_map_is_only_fetched_when_it_is_opened():
    """Most people never open it; it is not worth a download to them.

    Looking for a markup tag rather than the word, because the word appears
    in the comments that explain all this — an earlier version of this test
    failed on its own prose, which proves a string search and a fact are not
    the same thing.
    """
    import re
    with open(os.path.join(_APP_DIR, 'templates', 'dashboard.html'),
              encoding='utf-8') as f:
        html = f.read()
    tags = re.findall(r'<(?:script|link)[^>]*leaflet[^>]*>', html, re.I)
    assert tags == [], f'Leaflet is loaded on every page view: {tags}'
    assert 'cdnjs.cloudflare.com/ajax/libs/leaflet' in html, \
        'and now it is not loaded at all'
