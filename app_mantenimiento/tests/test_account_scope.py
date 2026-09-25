"""
An account that reaches nothing has to say so.

Michael Hamilton, VP of Building Services, was added as a regional with no
region. A regional's scope *is* their region — regional_communities() returns
an empty list without one — so he covered zero communities, and every screen
filters against that list. No communities, no visits, no raised items.

Two things let it happen and then hid it.

The form allowed it. Creating staff demands a community; creating a regional
demanded nothing, and that is the more expensive half: an Executive Director
with no community is obviously unfinished, while a regional with no region
looks complete.

And his profile told him he covered "All communities". The page printed the
community, or that phrase when there was none — and a regional never has a
single community, because that field belongs to Executive Directors. So every
regional read as covering everything, including the ones covering nothing.

He wrote in asking whether there was some other way in. There was not. There
was nothing to see.

Run locally, never on the server.
"""

import os
import sys

import pytest

_APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

import app as A  # noqa: E402

HEADERS = {'Origin': 'http://localhost', 'Referer': 'http://localhost/'}


def a_real_region():
    for r in A.region_service.get_all_regions():
        if r.get('id') not in ('unassigned', A.CORPORATE_ID):
            return r['id']
    pytest.skip('needs a geographic region')


# ------------------------------------------------- the empty scope, refused

def test_a_regional_with_no_region_is_refused():
    """The account Michael got. It reaches nothing, and nothing said so."""
    why = A._scope_complaint('regional', '', None)
    assert why and 'region' in why.lower()


def test_and_the_message_explains_why_rather_than_just_saying_no():
    why = A._scope_complaint('regional', '', None)
    assert 'see nothing' in why, f'the refusal does not say what is at stake: {why}'


def test_a_regional_with_a_region_is_fine():
    assert A._scope_complaint('regional', a_real_region(), None) is None


def test_a_region_that_no_longer_exists_is_refused():
    """Deleting a region would otherwise leave its people reaching nothing,
    and the next edit of one of those accounts is where that surfaces."""
    why = A._scope_complaint('regional', 'a-region-deleted-last-year', None)
    assert why and 'no longer exists' in why


def test_corporate_needs_its_group_too():
    assert A._scope_complaint('corporate', '', None) is not None
    assert A._scope_complaint('corporate', A.CORPORATE_ID, None) is None


def test_staff_still_needs_a_community():
    """The check that already existed, kept."""
    assert A._scope_complaint('staff', '', None) is not None
    assert A._scope_complaint('staff', '', 'Somewhere') is None


def test_an_admin_needs_neither():
    assert A._scope_complaint('admin', '', None) is None


# ------------------------------------------------ through the real routes

@pytest.fixture
def as_admin(monkeypatch):
    made = []
    monkeypatch.setattr(A.user_service, 'create',
                        lambda *a, **k: made.append((a, k)) or True)
    monkeypatch.setattr(A.email_service, 'enabled', False)
    c = A.app.test_client()
    with c.session_transaction() as s:
        s.update(user='admin', role='admin', display_name='Administrator')
    return c, made


def test_creating_one_is_refused_at_the_route(as_admin):
    """This one already held before today — the create route checks that the
    region exists. It is asserted anyway because the check lived inline and
    nothing pinned it, and because knowing it holds is what says Michael's
    account did not come from here."""
    c, made = as_admin
    r = c.post('/api/people', headers=HEADERS, json={
        'name': 'Michael Hamilton', 'email': 'mhamilton@atlasseniorliving.com',
        'role': 'regional', 'title': 'VP of Building Services'})
    assert r.status_code == 400, r.get_data(as_text=True)[:200]
    assert 'region' in r.get_json()['message'].lower()
    assert made == [], 'the account was created anyway'


def test_creating_one_with_a_region_goes_through(as_admin, monkeypatch):
    """A regional is stored as leadership of their region, not in users.json —
    which is the same reason the region is not optional for them."""
    c, _ = as_admin
    added = []
    monkeypatch.setattr(A.region_service, 'add_leader',
                        lambda *a, **k: added.append((a, k)) or True)
    monkeypatch.setattr(A.profile_service, 'set_password_hash', lambda *a, **k: True)
    r = c.post('/api/people', headers=HEADERS, json={
        'name': 'Someone Real', 'email': 'someone@atlasseniorliving.com',
        'role': 'regional', 'region_id': a_real_region()})
    assert r.status_code in (200, 201), r.get_data(as_text=True)[:200]
    assert added, 'a valid account was refused'


def test_editing_somebody_into_an_empty_scope_is_refused(as_admin, monkeypatch):
    """The likelier of the two mistakes, because the account already worked."""
    c, _ = as_admin
    moved = []
    monkeypatch.setattr(A.user_service, 'update',
                        lambda *a, **k: moved.append(k) or True)
    r = c.put('/api/people/someone', headers=HEADERS, json={
        'name': 'Someone', 'email': 'someone@atlasseniorliving.com',
        'role': 'regional', 'region_id': ''})
    assert r.status_code == 400
    assert moved == [], 'the account was moved into an empty scope anyway'


# ------------------------------------------- what the profile page is told

def _profile(**session_bits):
    c = A.app.test_client()
    with c.session_transaction() as s:
        s.update(user='michael.hamilton', display_name='Michael Hamilton',
                 **session_bits)
    return c.get('/api/profile').get_json()


def test_a_regional_with_no_region_is_not_told_they_have_everything():
    """The sentence that started all of this."""
    p = _profile(role='regional', region_id=None, community=None)
    assert p['community'] != 'All communities', \
        'an account covering nothing was told it covers everything'
    assert p['covers_nothing'] is True
    assert 'No region' in p['community']


def test_a_regional_with_a_region_is_told_which_one():
    rid = a_real_region()
    name = next(r['name'] for r in A.region_service.get_all_regions()
                if r['id'] == rid)
    p = _profile(role='regional', region_id=rid, community=None)
    assert p['community'] == f'{name} region'
    assert p['covers_nothing'] is False


def test_corporate_really_does_cover_everything():
    """The one case where the phrase is true, so it has to survive."""
    p = _profile(role='regional', region_id=A.CORPORATE_ID, community=None)
    assert p['community'] == 'All communities'
    assert p['covers_nothing'] is False


def test_an_executive_director_still_sees_their_own_community():
    p = _profile(role='staff', community='Madison at Ocoee, Ocoee',
                 communities=['Madison at Ocoee, Ocoee'])
    assert p['community'] == 'Madison at Ocoee, Ocoee'
    assert p['covers_nothing'] is False


def test_a_staff_account_with_no_community_says_so_too():
    p = _profile(role='staff', community=None, communities=[])
    assert p['covers_nothing'] is True
    assert 'No community' in p['community']


def test_the_page_stopped_guessing():
    """The phrase must not come back as a fallback on an empty field. The
    server decides it now, because the server is where the answer is."""
    with open(os.path.join(_APP_DIR, 'templates', 'dashboard.html'),
              encoding='utf-8') as f:
        html = f.read()
    # The function is long; the profile header sits well into it.
    i = html.index('async function renderSettings()')
    body = html[i:i + 12000]
    assert "`<span class=\"profile-region\"><i class=\"fas fa-globe\"></i> All communities</span>`" \
        not in body, 'the page is inventing "All communities" again'
    assert 'covers_nothing' in body, 'and it no longer reads what the server worked out'
    # The server always sends a sentence now, so the page's own fallback should
    # never fire — which is exactly why it must not be that phrase. A fallback
    # nothing exercises is where a lie waits patiently.
    assert "community || 'All communities'" not in body, \
        'the page would fall back to claiming everything'
