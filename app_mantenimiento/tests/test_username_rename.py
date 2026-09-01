"""
Changing somebody's sign-in name without losing them.

The username is the key everything is filed under, so this is not a label
change. Two failures matter more than the rest, and neither one announces
itself:

  * the account moves but the saved password does not, and on Monday they
    cannot sign in;
  * the account moves but their visits do not, and their work is now filed
    under a name that no longer exists.

The fixtures below copy the real shapes, including the awkward ones — a comment
on a finding sits four levels down inside a submission, and a region member's
username lives pinned on their leadership entry rather than in users.json.

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

from services.username_rename import (  # noqa: E402
    RenameError, UsernameRenamer, validate,
)

OLD, NEW = 'jazmyn.frasier', 'jazmyn.frazier'


def write(folder, name, doc):
    with open(os.path.join(folder, name), 'w', encoding='utf-8') as f:
        json.dump(doc, f, indent=2)


def read(folder, name):
    with open(os.path.join(folder, name), encoding='utf-8') as f:
        return json.load(f)


@pytest.fixture
def data():
    """A small world with one Executive Director and one region member."""
    folder = tempfile.mkdtemp()

    write(folder, 'users.json', {'version': 1, 'last_modified': '', 'users': {
        OLD: {'role': 'staff', 'community': 'Kelley Place, Enterprise',
              'display_name': 'Jazmyn Frazier', 'email': 'j@x.com',
              'password_hash': 'pbkdf2:sha256:seed', 'created_by': 'admin'},
        'someone.else': {'role': 'staff', 'community': 'One Loudoun'},
    }})

    write(folder, 'profiles.json', {'version': 1, 'profiles': {
        OLD: {'photo': 'uploads/jazmyn.jpg', 'display_name': 'Jazmyn Frazier',
              'password_hash': 'pbkdf2:sha256:the-one-she-set',
              'must_change': False},
        'someone.else': {'photo': None},
    }, 'leaders': {'coastal::Lauren Hamilton': {'photo': 'uploads/l.jpg'}}})

    write(folder, 'regions.json', {'version': 1, 'regions': [
        {'id': 'coastal', 'name': 'Coastal', 'communities': ['One Loudoun'],
         'leadership': [{'name': 'Lauren Hamilton', 'username': 'lauren.hamilton',
                         'email': 'l@x.com'}]},
    ]})

    # A visit she sent, with a finding somebody addressed and a comment on it —
    # the deepest place a username hides.
    write(folder, 'inspections.json', {'version': 1, 'submissions': [
        {'id': 's1', 'username': OLD, 'community': 'Kelley Place, Enterprise',
         'submitted_at': '2026-08-20T10:00:00', 'survey_type_id': 'standards',
         'responses': [
             {'question_id': 'q1', 'answer': 'no',
              'addressed_by': OLD, 'addressed_note': 'painted',
              'comments': [{'id': 'c1', 'username': OLD, 'author': 'Jazmyn Frazier',
                            'text': 'done', 'at': '2026-08-21T09:00:00'},
                           {'id': 'c2', 'username': 'lauren.hamilton',
                            'author': 'Lauren Hamilton', 'text': 'thanks'}]},
         ],
         'action_items': [{'id': 'i1', 'resolved_by': OLD, 'resolved': True,
                           'comments': [{'id': 'c3', 'username': OLD,
                                         'author': 'Jazmyn Frazier'}]}]},
        {'id': 's2', 'username': 'lauren.hamilton', 'community': 'One Loudoun'},
    ]})

    write(folder, 'activity.json', {'version': 1, 'events': [
        {'id': 'e1', 'username': OLD, 'type': 'inspection_submitted'},
        {'id': 'e2', 'username': OLD, 'type': 'comment_added'},
        {'id': 'e3', 'username': 'lauren.hamilton', 'type': 'login'},
    ]})

    write(folder, 'raised_items.json', {'version': 1, 'items': [
        {'id': 'r1', 'raised_by': OLD, 'raised_by_name': 'Jazmyn Frazier',
         'text': 'Dryer vent', 'resolved_by': '',
         'comments': [{'id': 'rc1', 'username': OLD, 'author': 'Jazmyn Frazier'}]},
    ]})

    write(folder, 'draft_notices.json', {'version': 1, 'notices': [
        {'id': '%s::standards::Kelley Place, Enterprise' % OLD, 'username': OLD,
         'community': 'Kelley Place, Enterprise', 'survey_type_id': 'standards',
         'answered': 12, 'total': 39},
    ]})

    write(folder, 'presence.json', {'version': 1, 'users': {
        OLD: {'last_seen': '2026-08-31T12:00:00', 'logins': 14},
    }})

    return folder


# ------------------------------------------------------------------- shape

def test_it_refuses_a_name_that_is_not_a_username():
    for bad in ('', '   ', 'Jazmyn Frazier', 'jazmyn frazier', '.jazmyn',
                'jazmyn.', 'a', 'JAZMYN.FRAZIER!'):
        with pytest.raises(RenameError):
            validate(bad)


def test_it_accepts_the_ordinary_shapes():
    assert validate('  Jazmyn.Frazier  ') == 'jazmyn.frazier', 'trimmed and lowered'
    assert validate('lauren.goldsmith') == 'lauren.goldsmith'
    assert validate('jo-ellen.spivey') == 'jo-ellen.spivey'


# ------------------------------------------------------- the whole person

def test_the_account_moves(data):
    UsernameRenamer(data).rename(OLD, NEW)
    users = read(data, 'users.json')['users']
    assert NEW in users and OLD not in users
    assert users[NEW]['community'] == 'Kelley Place, Enterprise', 'same account'
    assert users['someone.else']['community'] == 'One Loudoun', 'nobody else moved'


def test_the_password_she_set_moves_with_her(data):
    """The failure that locks somebody out on Monday morning."""
    UsernameRenamer(data).rename(OLD, NEW)
    profiles = read(data, 'profiles.json')['profiles']
    assert OLD not in profiles
    assert profiles[NEW]['password_hash'] == 'pbkdf2:sha256:the-one-she-set'
    assert profiles[NEW]['photo'] == 'uploads/jazmyn.jpg'


def test_her_visits_are_still_hers(data):
    UsernameRenamer(data).rename(OLD, NEW)
    subs = read(data, 'inspections.json')['submissions']
    assert subs[0]['username'] == NEW
    assert subs[1]['username'] == 'lauren.hamilton', 'somebody else untouched'


def test_it_reaches_the_places_a_hand_written_list_would_miss(data):
    """A comment on a finding is four levels down inside a submission."""
    UsernameRenamer(data).rename(OLD, NEW)
    r = read(data, 'inspections.json')['submissions'][0]['responses'][0]
    assert r['addressed_by'] == NEW, 'who fixed it'
    assert r['comments'][0]['username'] == NEW, 'who commented on it'
    assert r['comments'][1]['username'] == 'lauren.hamilton'
    item = read(data, 'inspections.json')['submissions'][0]['action_items'][0]
    assert item['resolved_by'] == NEW
    assert item['comments'][0]['username'] == NEW


def test_the_rest_of_the_stores_come_too(data):
    UsernameRenamer(data).rename(OLD, NEW)
    assert [e['username'] for e in read(data, 'activity.json')['events']] \
        == [NEW, NEW, 'lauren.hamilton']
    item = read(data, 'raised_items.json')['items'][0]
    assert item['raised_by'] == NEW and item['comments'][0]['username'] == NEW
    assert NEW in read(data, 'presence.json')['users']


def test_a_draft_notice_keeps_pointing_at_the_same_draft(data):
    """Its id is built from the username, and the browser keys on the rest."""
    UsernameRenamer(data).rename(OLD, NEW)
    n = read(data, 'draft_notices.json')['notices'][0]
    assert n['username'] == NEW
    assert n['id'] == '%s::standards::Kelley Place, Enterprise' % NEW


def test_the_name_shown_at_the_time_is_left_alone(data):
    """'author' records what was displayed, not which account it points at."""
    UsernameRenamer(data).rename(OLD, NEW)
    r = read(data, 'inspections.json')['submissions'][0]['responses'][0]
    assert r['comments'][0]['author'] == 'Jazmyn Frazier'
    assert read(data, 'raised_items.json')['items'][0]['raised_by_name'] == 'Jazmyn Frazier'


def test_nothing_anywhere_still_says_the_old_name(data):
    UsernameRenamer(data).rename(OLD, NEW)
    assert UsernameRenamer(data).occurrences(OLD) == {}


def test_a_region_member_is_renamed_where_their_account_actually_lives(data):
    """Not in users.json — pinned on their leadership entry in regions.json."""
    out = UsernameRenamer(data).rename('lauren.hamilton', 'lauren.goldsmith')
    leader = read(data, 'regions.json')['regions'][0]['leadership'][0]
    assert leader['username'] == 'lauren.goldsmith'
    assert leader['name'] == 'Lauren Hamilton', 'the display name is a separate thing'
    assert read(data, 'inspections.json')['submissions'][1]['username'] == 'lauren.goldsmith'
    assert 'regions.json' in out['changed']


# ------------------------------------------------------------- it refuses

def test_it_will_not_take_a_name_somebody_already_has(data):
    with pytest.raises(RenameError, match='already in use'):
        UsernameRenamer(data).rename(OLD, 'someone.else')
    assert OLD in read(data, 'users.json')['users'], 'and changed nothing'


def test_it_will_not_rename_somebody_who_is_not_there(data):
    with pytest.raises(RenameError, match='No account found'):
        UsernameRenamer(data).rename('nobody.here', 'somebody.new')


def test_renaming_to_the_same_name_is_refused(data):
    with pytest.raises(RenameError):
        UsernameRenamer(data).rename(OLD, OLD)


# ------------------------------------------------------- it puts it back

def test_a_failure_partway_through_leaves_everything_as_it_was(data, monkeypatch):
    """The reason the copies are taken.

    Eight files cannot be written as one transaction. What can be guaranteed is
    that a run which does not finish cleanly leaves nothing behind.
    """
    before = {f: read(data, f) for f in os.listdir(data) if f.endswith('.json')}

    r = UsernameRenamer(data)
    monkeypatch.setattr(r, '_verify', lambda *a, **k: (_ for _ in ()).throw(
        RenameError('pretend the counts did not add up')))

    with pytest.raises(RenameError):
        r.rename(OLD, NEW)

    for name, doc in before.items():
        assert read(data, name) == doc, f'{name} was left changed'


def test_it_keeps_a_copy_of_what_it_replaced(data):
    out = UsernameRenamer(data).rename(OLD, NEW)
    assert os.path.isdir(out['backup'])
    saved = json.load(open(os.path.join(out['backup'], 'users.json'), encoding='utf-8'))
    assert OLD in saved['users'], 'the copy is from before the change'


def test_the_old_name_is_remembered_so_the_session_can_be_ended(data):
    """Their browser still holds the old name after the rename.

    Without this it keeps working in a half-real way: reads succeed, and
    anything written is filed under a person who is no longer there — putting
    back exactly the orphans the rename just cleared.
    """
    r = UsernameRenamer(data)
    assert r.retired(OLD) is None, 'nothing retired yet'
    r.rename(OLD, NEW)
    assert r.retired(OLD) == NEW
    assert r.retired(NEW) is None, 'the name they now use is not retired'
    assert r.retired('someone.else') is None, 'nobody else is signed out'


def test_a_refused_rename_does_not_sign_anybody_out(data):
    """A name is only retired once the move is known to have worked."""
    r = UsernameRenamer(data)
    with pytest.raises(RenameError):
        r.rename(OLD, 'someone.else')
    assert r.retired(OLD) is None


def test_it_reports_what_it_touched(data):
    out = UsernameRenamer(data).rename(OLD, NEW)
    assert out['from'] == OLD and out['to'] == NEW
    for expected in ('users.json', 'profiles.json', 'inspections.json',
                     'activity.json', 'raised_items.json', 'draft_notices.json',
                     'presence.json'):
        assert expected in out['changed'], f'{expected} reported as untouched'
    assert out['total'] > 10


# ---------------------------------------------------------------- the api
#
# These exercise the guards on the endpoint. None of them performs a rename:
# the mechanics are covered above against fixtures, and running a real one here
# would rewrite live records.

import app as A  # noqa: E402

HDR = {"Origin": "http://localhost", "Referer": "http://localhost/"}


def _client(**session_bits):
    c = A.app.test_client()
    with c.session_transaction() as s:
        s.update(**session_bits)
    return c


def _admin():
    return _client(user="admin", role="admin", community=None, region_id=None,
                   display_name="admin")


def test_only_an_administrator_can_change_a_username():
    c = _client(user="smoke.rename.ed", role="staff",
                community=(A.all_communities() or [""])[0], display_name="ED")
    r = c.post("/api/people/somebody/username",
               json={"new_username": "somebody.else"}, headers=HDR)
    assert r.status_code == 403


def test_the_built_in_administrator_cannot_be_renamed():
    """It lives in code, not in the data files.

    Moving it here would rewrite the records and leave the account behind —
    locking the door with everyone outside.
    """
    r = _admin().post("/api/people/admin/username",
                      json={"new_username": "administrator"}, headers=HDR)
    assert r.status_code == 400
    assert "built-in" in r.get_json()["message"].lower()


def test_renaming_somebody_who_is_not_there_is_a_404():
    r = _admin().post("/api/people/nobody.at.all/username",
                      json={"new_username": "still.nobody"}, headers=HDR)
    assert r.status_code == 404


def test_a_name_somebody_already_has_is_refused():
    # Has to start from a person who exists, or the 404 answers first.
    real = next(iter(A.get_regional_accounts()), None)
    if not real:
        pytest.skip("needs a region member in the roster")
    r = _admin().post(f"/api/people/{real}/username",
                      json={"new_username": "admin"}, headers=HDR)
    assert r.status_code == 400
    assert "already in use" in r.get_json()["message"]
    assert real in A.get_regional_accounts(), "and nothing was moved"


def test_signed_out_cannot_reach_it():
    r = A.app.test_client().post("/api/people/x/username",
                                 json={"new_username": "y"}, headers=HDR)
    assert r.status_code in (302, 401, 403)


def test_a_session_holding_a_renamed_name_is_ended(monkeypatch):
    """The browser keeps the old name until something tells it otherwise."""
    monkeypatch.setattr(A.username_renamer, "retired",
                        lambda name: "jazmyn.frazier" if name == OLD else None)

    c = _client(user=OLD, role="staff", community="Kelley Place, Enterprise",
                display_name="Jazmyn Frazier")
    r = c.get("/api/drafts")
    assert r.status_code == 401
    body = r.get_json()
    assert body["signed_out"] is True
    assert "jazmyn.frazier" in body["message"], "tell them what to sign in as"

    with c.session_transaction() as s:
        assert "user" not in s, "the session should have been cleared"


def test_the_login_page_says_what_happened():
    """Being bounced to a sign-in screen with no explanation reads as a fault."""
    page = A.app.test_client().get('/login?renamed=jazmyn.frazier').get_data(as_text=True)
    assert 'Your sign-in name changed' in page
    assert 'value="jazmyn.frazier"' in page, 'and fills in the new name for them'


def test_the_login_page_is_normal_otherwise():
    page = A.app.test_client().get('/login').get_data(as_text=True)
    assert 'Your sign-in name changed' not in page


def test_that_notice_cannot_be_used_to_inject():
    """It is built from a query string, so it is worth pinning."""
    page = A.app.test_client().get(
        '/login?renamed=%3Cscript%3Ealert(1)%3C/script%3E').get_data(as_text=True)
    assert '<script>alert(1)' not in page


def test_everyone_else_stays_signed_in(monkeypatch):
    """The check is per-name on purpose.

    An earlier version asked whether the account resolved at all, which signed
    out every session whose name could not be looked up right then.
    """
    monkeypatch.setattr(A.username_renamer, "retired",
                        lambda name: "jazmyn.frazier" if name == OLD else None)
    r = _admin().get("/api/drafts")
    assert r.status_code == 200
