"""
Standards that apply to every community, and changing many at once.

Greg Crutcher asked (Nov 2026) whether there was an easier way to add a
community to the surveys than editing every standard. There was not: each
standard keeps a fixed list of names, and adding a community in Regions
touched none of them, so a new community arrived with no standards at all and
the list showed "40" on some and "39" on others.

Now a standard can be "Every community", which reaches communities added
later too; the ones that already listed every community were switched once,
automatically, as Greg agreed. And Standards can add or remove one community
on many standards in one go. The page side is test_every_community.mjs.
"""

import ast
import os
import sys
import time

import pytest

_APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

import app as A  # noqa: E402
from services.question_manager import QuestionManager  # noqa: E402

HEADERS = {'Origin': 'http://localhost', 'Referer': 'http://localhost/'}
OLD = ['Kelley Place', 'Naples Place', 'Greystone']
NEW = 'Madison at Ocoee'


@pytest.fixture
def qm(monkeypatch, tmp_path):
    m = QuestionManager(str(tmp_path / 'questions.json'))
    monkeypatch.setattr(A, 'question_manager', m)
    monkeypatch.setattr(A.question_filter_service, 'question_manager', m)
    monkeypatch.setattr(A.survey_type_service, 'validate_survey_type', lambda *a: True)
    monkeypatch.setattr(A.activity_service, 'log', lambda *a, **k: None)
    monkeypatch.setattr(A, 'all_communities', lambda: OLD + [NEW])
    monkeypatch.setattr(A, 'regional_communities', lambda *a, **k: OLD + [NEW])
    return m


def make(m, text, communities, **kw):
    q = m.create_question(text, False, communities, survey_types=[], **kw)
    time.sleep(0.002)
    return q


def texts(qs):
    return sorted(q['text'] for q in qs)


def as_(role='admin', community=None):
    c = A.app.test_client()
    with c.session_transaction() as s:
        s.update(user='someone', role=role, display_name='someone', community=community,
                 communities=[community] if community else [])
    return c


# ------------------------------------------------------- the one-time switch

def test_standards_listing_every_community_are_switched(qm):
    """What Greg agreed to: the ones covering all of them follow new ones too."""
    everywhere = make(qm, 'Lobby clean', list(OLD))
    some = make(qm, 'Pool fenced', ['Kelley Place'])
    assert qm.adopt_every_community(OLD) == 1
    assert qm.get_question(everywhere['id']).get('all_communities') is True
    assert not qm.get_question(some['id']).get('all_communities')
    assert texts(qm.get_questions_for_community(NEW)) == ['Lobby clean'], 'a new community gets it'


def test_it_runs_once(qm):
    """Later, somebody ticking every box by hand is choosing a list."""
    qm.adopt_every_community(OLD)
    later = make(qm, 'Chosen by hand', list(OLD))
    assert qm.adopt_every_community(OLD) == 0
    assert not qm.get_question(later['id']).get('all_communities')
    assert not QuestionManager(qm.storage_path).adopt_every_community(OLD), 'remembered across restarts'


def test_a_server_with_no_communities_yet_does_not_use_up_the_switch(qm):
    make(qm, 'Lobby clean', list(OLD))
    assert qm.adopt_every_community([]) == 0
    assert qm.adopt_every_community(OLD) == 1


def test_the_app_runs_it_at_start(qm):
    """At module level, so a deploy does it, and failure never stops the app."""
    make(qm, 'Lobby clean', OLD + [NEW])
    assert A._adopt_every_community_at_start() == 1
    tree = ast.parse(open(A.__file__, encoding='utf-8').read())
    calls = [n for n in tree.body if isinstance(n, ast.Expr) and isinstance(n.value, ast.Call)
             and getattr(n.value.func, 'id', '') == '_adopt_every_community_at_start']
    assert calls, 'defined but never run'


def test_and_survives_a_broken_store(qm, monkeypatch):
    def boom(*a):
        raise IOError('disk full')
    monkeypatch.setattr(qm, 'adopt_every_community', boom)
    assert A._adopt_every_community_at_start() == 0


# ------------------------------------------------------- every community

def test_a_new_community_gets_every_community_standards_on_the_visit_form(qm):
    make(qm, 'Lobby clean', [], all_communities=True)
    make(qm, 'Only Kelley', ['Kelley Place'])
    got = as_('regional').get('/api/questions', headers=HEADERS,
                              query_string={'community': NEW, 'survey_type': 'standards'})
    assert got.status_code == 200, got.get_data(as_text=True)[:200]
    assert texts(got.get_json()['questions']) == ['Lobby clean']


def test_an_admin_can_create_one_with_no_list(qm):
    r = as_().post('/api/questions', headers=HEADERS, json={
        'text': 'Exits lit', 'photo_required': False, 'communities': [], 'all_communities': True})
    assert r.status_code in (200, 201), r.get_data(as_text=True)[:200]
    assert texts(qm.get_questions_for_community(NEW)) == ['Exits lit']


def test_without_it_a_list_is_still_required(qm):
    r = as_().post('/api/questions', headers=HEADERS, json={
        'text': 'Exits lit', 'photo_required': False, 'communities': []})
    assert r.status_code == 400
    r = as_().post('/api/questions', headers=HEADERS, json={
        'text': 'Exits lit', 'photo_required': False, 'communities': [], 'all_communities': 'yes'})
    assert r.status_code == 400, 'only a real true counts'


def test_editing_turns_it_on_and_off(qm):
    q = make(qm, 'Lobby clean', ['Kelley Place'])
    url = f"/api/questions/{q['id']}"
    body = {'text': 'Lobby clean', 'photo_required': False, 'communities': ['Kelley Place']}
    assert as_().put(url, headers=HEADERS, json={**body, 'all_communities': True}).status_code == 200
    assert qm.get_question(q['id'])['all_communities'] is True
    assert as_().put(url, headers=HEADERS, json=body).status_code == 200
    assert 'all_communities' not in qm.get_question(q['id'])
    assert texts(qm.get_questions_for_community(NEW)) == []


# ------------------------------------------------------------ in bulk

def change(ids, community, action, who=None):
    return (who or as_()).post('/api/questions/communities', headers=HEADERS,
                               json={'ids': ids, 'community': community, 'action': action})


def test_add_a_community_to_many_at_once(qm):
    """The 39s: add the new community to all of them in one go."""
    a = make(qm, 'Month 4 - SMD', list(OLD))
    b = make(qm, 'Month 4 - ED', list(OLD))
    c = make(qm, 'Untouched', list(OLD))
    r = change([a['id'], b['id']], NEW, 'add')
    assert r.status_code == 200, r.get_data(as_text=True)[:200]
    assert sorted(r.get_json()['changed']) == sorted([a['id'], b['id']])
    assert texts(qm.get_questions_for_community(NEW)) == ['Month 4 - ED', 'Month 4 - SMD']
    assert NEW not in qm.get_question(c['id'])['communities']


def test_adding_where_it_already_is_changes_nothing(qm):
    every = make(qm, 'Everywhere', [], all_communities=True)
    has = make(qm, 'Has it', [NEW])
    d = change([every['id'], has['id']], NEW, 'add').get_json()
    assert sorted(d['unchanged']) == sorted([every['id'], has['id']]) and d['changed'] == []
    assert qm.get_question(has['id'])['communities'] == [NEW], 'not added twice'


def test_removing_from_every_community_keeps_everyone_else(qm):
    every = make(qm, 'Everywhere', [], all_communities=True)
    d = change([every['id']], 'Greystone', 'remove').get_json()
    assert d['changed'] == [every['id']]
    q = qm.get_question(every['id'])
    assert 'all_communities' not in q, 'it no longer reaches every community'
    assert sorted(q['communities']) == sorted(['Kelley Place', 'Naples Place', NEW])


def test_a_standard_is_never_left_with_no_community(qm):
    only = make(qm, 'Only Kelley', ['Kelley Place'])
    d = change([only['id']], 'Kelley Place', 'remove').get_json()
    assert d['refused'] == [only['id']]
    assert qm.get_question(only['id'])['communities'] == ['Kelley Place']


def test_only_a_real_community(qm):
    q = make(qm, 'Lobby', ['Kelley Place'])
    assert change([q['id']], 'Atlantis', 'add').status_code == 400
    assert change([q['id']], NEW, 'smash').status_code == 400
    assert change([], NEW, 'add').status_code == 400
    assert qm.get_question(q['id'])['communities'] == ['Kelley Place']


@pytest.mark.parametrize('role', ['regional', 'corporate', 'staff', A.TEAM_ROLE])
def test_only_an_admin_changes_them(qm, role):
    q = make(qm, 'Lobby', ['Kelley Place'])
    assert change([q['id']], NEW, 'add', as_(role, 'Kelley Place')).status_code == 403
    assert qm.get_question(q['id'])['communities'] == ['Kelley Place']


def test_a_rename_still_follows(qm):
    q = make(qm, 'Lobby', ['Kelley Place'])
    qm.rename_community('Kelley Place', 'Kelley Place Enterprise')
    assert qm.get_question(q['id'])['communities'] == ['Kelley Place Enterprise']
