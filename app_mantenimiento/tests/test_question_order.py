"""
The order of the standards, set by an admin in Standards.

Greg Crutcher asked whether the questions could be put in a different order
(Nov 2026). They always came newest first, on the Standards page and on every
visit form. Now any admin moves them with up/down arrows; there is one order
for everything, each survey type shows its own questions in it, and a new
question goes to the end. A visit in progress is safe because answers are
kept by question id, never by position.

The page side is test_question_order.mjs.
"""

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
KELLEY = 'Kelley Place, Enterprise'


@pytest.fixture
def qm(monkeypatch, tmp_path):
    m = QuestionManager(str(tmp_path / 'questions.json'))
    monkeypatch.setattr(A, 'question_manager', m)
    monkeypatch.setattr(A.question_filter_service, 'question_manager', m)
    monkeypatch.setattr(A.survey_type_service, 'validate_survey_type', lambda *a: True)
    monkeypatch.setattr(A.activity_service, 'log', lambda *a, **k: None)
    monkeypatch.setattr(A, 'regional_communities', lambda *a, **k: [KELLEY])
    return m


def make(m, *texts, types=None):
    out = []
    for t in texts:
        out.append(m.create_question(t, False, [KELLEY], survey_types=types or []))
        time.sleep(0.002)   # distinct created_at, as in real life
    return out


def as_(role='admin', community=None):
    c = A.app.test_client()
    with c.session_transaction() as s:
        s.update(user='someone', role=role, display_name='someone', community=community,
                 communities=[community] if community else [])
    return c


def texts(qs):
    return [q['text'] for q in qs]


def order(ids, who=None):
    return (who or as_()).post('/api/questions/order', headers=HEADERS, json={'ids': ids})


def test_until_somebody_reorders_it_is_newest_first(qm):
    """What every install shows today, unchanged by the deploy."""
    make(qm, 'A', 'B', 'C')
    assert texts(qm.get_all_active_questions()) == ['C', 'B', 'A']


def test_an_admin_sets_the_order_and_every_list_follows(qm):
    a, b, c = make(qm, 'Exits lit', 'Kitchen clean', 'Lobby tidy')
    r = order([a['id'], b['id'], c['id']])
    assert r.status_code == 200, r.get_data(as_text=True)[:200]
    assert texts(qm.get_all_active_questions()) == ['Exits lit', 'Kitchen clean', 'Lobby tidy']
    assert texts(qm.get_questions_for_community(KELLEY)) == ['Exits lit', 'Kitchen clean', 'Lobby tidy']


def test_the_visit_form_gets_them_in_that_order(qm):
    """The form asks /api/questions for one survey type; the order holds."""
    a, b, c = make(qm, 'Exits lit', 'Kitchen clean', 'Lobby tidy')
    order([c['id'], a['id'], b['id']])
    got = as_('regional', KELLEY).get('/api/questions', headers=HEADERS,
                                      query_string={'community': KELLEY, 'survey_type': 'standards'})
    assert got.status_code == 200, got.get_data(as_text=True)[:200]
    assert texts(got.get_json()['questions']) == ['Lobby tidy', 'Exits lit', 'Kitchen clean']


def test_each_survey_type_shows_its_own_in_the_one_order(qm):
    a = make(qm, 'Sales only 1', types=['sales'])[0]
    b = make(qm, 'Everyone')[0]
    c = make(qm, 'Sales only 2', types=['sales'])[0]
    d = make(qm, 'Clinical only', types=['clinical'])[0]
    order([c['id'], d['id'], b['id'], a['id']])
    sales = A.question_filter_service.filter_by_survey_type(qm.get_questions_for_community(KELLEY), 'sales')
    assert texts(sales) == ['Sales only 2', 'Everyone', 'Sales only 1']


def test_a_new_question_goes_to_the_end(qm):
    a, b = make(qm, 'First', 'Second')
    order([a['id'], b['id']])
    make(qm, 'Newest')
    assert texts(qm.get_all_active_questions()) == ['First', 'Second', 'Newest']


def test_it_survives_a_restart(qm):
    a, b, c = make(qm, 'A', 'B', 'C')
    order([b['id'], c['id'], a['id']])
    assert texts(QuestionManager(qm.storage_path).get_all_active_questions()) == ['B', 'C', 'A']


def test_a_stale_page_cannot_lose_a_question(qm):
    """A page opened before somebody added one sends a list without it."""
    a, b = make(qm, 'A', 'B')
    c = make(qm, 'Added meanwhile')[0]
    order([b['id'], a['id'], 'q_deleted_123', b['id']])
    assert texts(qm.get_all_active_questions()) == ['B', 'A', 'Added meanwhile']
    assert all(isinstance(q['order'], int) for q in qm.get_all_active_questions())
    assert c['id'] in [q['id'] for q in qm.get_all_active_questions()]


def test_a_deleted_question_does_not_come_back(qm):
    a, b, c = make(qm, 'A', 'B', 'C')
    qm.delete_question(b['id'])
    order([c['id'], b['id'], a['id']])
    assert texts(qm.get_all_active_questions()) == ['C', 'A']


def test_an_empty_list_is_refused(qm):
    make(qm, 'A')
    assert order([]).status_code == 400
    assert as_().post('/api/questions/order', headers=HEADERS, json={'ids': 'q1'}).status_code == 400


@pytest.mark.parametrize('role', ['regional', 'corporate', 'staff', A.TEAM_ROLE])
def test_only_an_admin_changes_it(qm, role):
    a, b = make(qm, 'A', 'B')
    r = order([a['id'], b['id']], as_(role, KELLEY))
    assert r.status_code == 403
    assert texts(qm.get_all_active_questions()) == ['B', 'A']
