"""
Placing a community on the map, from inside the app.

The positions started as a file in the repository, on the argument that a pin
in the wrong state is the failure this cannot have and a diff is the cheapest
guard against it. That was an argument for review, and it cost more than it
bought: placing a new community meant a deploy, a rename left the position
behind under the old name, and `verified` could never become true because
there was no act of confirming.

So they moved to data/, seeded like the regions and the questions, and an
admin can place one from the community panel. Somebody looking at the pin and
agreeing with it is better review than somebody reading two numbers in a diff.

What has to stay true is the refusal. A pasted coordinate with a swapped sign
is the likeliest mistake there is here, and it puts a Florida building in
China. Catching it on the way in beats finding a community silently missing
from the map the next morning.

Run locally, never on the server.
"""

import json
import os
import sys

import pytest

_APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

import app as A  # noqa: E402
from services.place_service import PlaceService, in_range  # noqa: E402

HEADERS = {'Origin': 'http://localhost', 'Referer': 'http://localhost/'}
ATLANTA = (33.7490, -84.3880)


@pytest.fixture
def svc(tmp_path):
    p = tmp_path / 'places.json'
    p.write_text(json.dumps({'places': {
        'Already Placed': {'lat': 28.5, 'lng': -81.5, 'city': 'Ocoee',
                           'state': 'FL', 'verified': False,
                           'note': 'a guess of mine'},
    }}), encoding='utf-8')
    return PlaceService(str(p))


# --------------------------------------------------------------- the refusal

def test_a_plausible_position_is_accepted():
    assert in_range(*ATLANTA) is True


def test_a_swapped_sign_is_not():
    """The mistake that actually happens. It lands in China."""
    assert in_range(33.7490, 84.3880) is False


def test_neither_is_the_wrong_hemisphere_or_the_far_north():
    assert in_range(-33.7, -84.4) is False
    assert in_range(61.2, -84.4) is False


def test_nor_something_that_is_not_a_number():
    assert in_range('34', -84) is False
    assert in_range(None, None) is False
    # True == 1 in Python, and 1 is inside no range we use — but a boolean
    # arriving here at all means something upstream lost its way.
    assert in_range(True, -84) is False


def test_the_service_refuses_rather_than_storing(svc):
    assert svc.set('Somewhere', 33.7, 84.3) is None
    assert svc.unplaced(['Somewhere']) == ['Somewhere']


# ----------------------------------------------------------------- the write

def test_placing_one_records_who_confirmed_it(svc):
    rec = svc.set('Somewhere New', *ATLANTA, city='Atlanta', state='GA', by='gabriel')
    assert rec['lat'] == ATLANTA[0] and rec['lng'] == ATLANTA[1]
    assert rec['verified'] is True, 'somebody placed it; that is the confirming'
    assert rec['verified_by'] == 'gabriel'
    assert rec['verified_at']


def test_it_reaches_disk(svc, tmp_path):
    svc.set('Somewhere New', *ATLANTA, by='gabriel')
    again = PlaceService(str(tmp_path / 'places.json'))
    got = again.get('Somewhere New')
    assert got and got['lat'] == ATLANTA[0]
    assert got['verified'] is True


def test_moving_one_drops_the_note_that_explained_the_guess(svc):
    """The note said where a proposal came from. Once a person has placed the
    pin it is not a proposal, and leaving the note would argue with the flag."""
    assert svc.get('Already Placed')['note']
    rec = svc.set('Already Placed', *ATLANTA, by='gabriel')
    assert rec['lat'] == ATLANTA[0]
    assert not rec.get('note')


def test_it_keeps_the_city_it_already_had(svc):
    rec = svc.set('Already Placed', *ATLANTA, by='gabriel')
    assert rec['city'] == 'Ocoee', 'a position change is not a change of address'


# ---------------------------------------------------------------- the rename

def test_a_rename_carries_the_position(svc):
    assert svc.rename('Already Placed', 'Renamed Place') is True
    assert svc.get('Renamed Place')['lat'] == 28.5
    assert svc.get('Already Placed') is None


def test_renaming_something_with_no_position_does_nothing(svc):
    assert svc.rename('Never Placed', 'Still Nothing') is False


def test_renaming_to_the_same_name_is_not_a_rename(svc):
    assert svc.rename('Already Placed', 'Already Placed') is False
    assert svc.get('Already Placed') is not None


# ----------------------------------------------------------------- the route

@pytest.fixture
def as_admin(monkeypatch, tmp_path):
    p = tmp_path / 'places.json'
    p.write_text(json.dumps({'places': {}}), encoding='utf-8')
    monkeypatch.setattr(A, 'place_service', PlaceService(str(p)))
    monkeypatch.setattr(A, '_can_see_community', lambda c: c == 'A Community')
    c = A.app.test_client()
    with c.session_transaction() as s:
        s.update(user='admin', role='admin', display_name='Administrator')
    return c


def test_a_pasted_position_is_understood(as_admin):
    """What Google Maps puts on the clipboard when you right-click a spot."""
    r = as_admin.post('/api/map/communities/A Community', headers=HEADERS,
                      json={'pasted': '33.7490, -84.3880'})
    assert r.status_code == 200, r.get_data(as_text=True)[:200]
    assert r.get_json()['place']['lat'] == 33.7490


def test_plain_numbers_work_too(as_admin):
    r = as_admin.post('/api/map/communities/A Community', headers=HEADERS,
                      json={'lat': 33.7490, 'lng': -84.3880})
    assert r.status_code == 200


def test_a_swapped_sign_is_refused_with_a_reason(as_admin):
    r = as_admin.post('/api/map/communities/A Community', headers=HEADERS,
                      json={'pasted': '33.7490, 84.3880'})
    assert r.status_code == 400
    msg = r.get_json()['message']
    assert 'hemisphere' in msg, f'the refusal does not say what to look at: {msg}'


def test_something_that_is_not_a_position_is_refused(as_admin):
    r = as_admin.post('/api/map/communities/A Community', headers=HEADERS,
                      json={'pasted': 'round the back somewhere'})
    assert r.status_code == 400
    assert '34.0232' in r.get_json()['message'], 'it does not show the shape it wants'


def test_a_community_outside_your_reach_is_not_placeable(as_admin):
    r = as_admin.post('/api/map/communities/Not Yours', headers=HEADERS,
                      json={'pasted': '33.7490, -84.3880'})
    assert r.status_code == 404


def test_only_an_admin_may(monkeypatch, tmp_path):
    p = tmp_path / 'places.json'
    p.write_text(json.dumps({'places': {}}), encoding='utf-8')
    monkeypatch.setattr(A, 'place_service', PlaceService(str(p)))
    c = A.app.test_client()
    with c.session_transaction() as s:
        s.update(user='lauren', role='regional', region_id='innovia')
    r = c.post('/api/map/communities/A Community', headers=HEADERS,
               json={'pasted': '33.7490, -84.3880'})
    assert r.status_code in (403, 404, 302), r.status_code


def test_placing_one_is_recorded(as_admin, monkeypatch):
    logged = []
    monkeypatch.setattr(A.activity_service, 'log',
                        lambda u, t, d='', meta=None: logged.append((t, meta or {})))
    as_admin.post('/api/map/communities/A Community', headers=HEADERS,
                  json={'pasted': '33.7490, -84.3880'})
    assert any(t == 'community_placed' for t, _ in logged)


# ------------------------------------------------- the whole chain, for real

def test_renaming_through_the_route_takes_the_position_with_it(monkeypatch, tmp_path):
    """The gap this whole change closes: everything else the rename touches
    moved with the community, and the position stayed behind."""
    p = tmp_path / 'places.json'
    p.write_text(json.dumps({'places': {
        'Old Place': {'lat': 33.7, 'lng': -84.4, 'city': 'Atlanta', 'state': 'GA'}}}),
        encoding='utf-8')
    monkeypatch.setattr(A, 'place_service', PlaceService(str(p)))
    for svc_obj, name in ((A.region_service, 'rename_community'),
                          (A.question_manager, 'rename_community'),
                          (A.inspection_service, 'rename_community'),
                          (A.movein_service, 'rename_community'),
                          (A.raised_item_service, 'rename_community')):
        monkeypatch.setattr(svc_obj, name, lambda *a, **k: 0)
    monkeypatch.setattr(A.community_cover_service, 'rename', lambda *a, **k: None)
    monkeypatch.setattr(A.activity_service, 'log', lambda *a, **k: None)

    c = A.app.test_client()
    with c.session_transaction() as s:
        s.update(user='admin', role='admin')
    r = c.post('/api/regions/rename-community', headers=HEADERS,
               json={'old_name': 'Old Place', 'new_name': 'New Place'})
    assert r.status_code == 200

    assert A.place_service.get('New Place'), 'the position did not follow the rename'
    assert A.place_service.get('Old Place') is None


def test_the_live_file_is_seeded_like_the_others():
    """It is the sixth seeded file. Without that a fresh server starts with no
    positions at all and every community reports as unplaced."""
    with open(os.path.join(_APP_DIR, 'app.py'), encoding='utf-8') as f:
        src = f.read()
    i = src.index('for _seed_name in (')
    assert 'community_places.json' in src[i:i + 300]
    assert os.path.exists(os.path.join(_APP_DIR, 'data', 'seeds',
                                       'community_places.json'))


def test_a_city_is_a_city_and_nothing_else():
    """It is shown on the community card for a community whose own name does
    not carry a town — The Georgian Lakeside shows "Roswell". So a city of
    "Orlando (Lake Nona)" would make the card repeat itself next to a name
    that already says Lake Nona.

    The district or development belongs in the note, where it is useful to
    whoever is checking the pin.
    """
    import json as _json
    seed = os.path.join(_APP_DIR, 'data', 'seeds', 'community_places.json')
    with open(seed, encoding='utf-8') as f:
        places = _json.load(f)['places']

    parenthesised = {k: v['city'] for k, v in places.items() if '(' in (v.get('city') or '')}
    assert parenthesised == {}, \
        f'these carry a district in the city field: {parenthesised}'

    missing = [k for k, v in places.items() if not (v.get('city') or '').strip()]
    assert missing == [], f'no city on file for: {missing}'
