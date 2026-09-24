"""
The reminder for action items that have gone quiet.

Greg asked for an automatic email at 15 and 30 days of silence. Three things
about it can go wrong quietly, and those are what most of this is about:

  - An internal item reaching an Executive Director. Leadership can raise
    something the community is not meant to see; a new email is a new place
    for that to leak, and nobody would notice it had.
  - The same nudge going out every morning, because nothing recorded that
    yesterday's already went.
  - The day it is switched on emptying months of backlog into everybody's
    inbox at once.

There is also a plain safety catch: the job must not send unless told to.
That one is asserted by running the real entry point.

Run locally, never on the server.
"""

import os
import sys
from datetime import datetime, timedelta

import pytest

_APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

from services import reminder_service as R  # noqa: E402

NOW = datetime(2026, 9, 23, 9, 0)


def iso(days_ago):
    return (NOW - timedelta(days=days_ago)).isoformat()


def submission(**kw):
    base = {'id': 'sub-1', 'community': 'The Oscar at Georgetown',
            'submitted_at': iso(40), 'responses': [], 'action_items': []}
    base.update(kw)
    return base


def failed(qid='q1', text='Handrail loose', days=40, comments=None, addressed=None):
    r = {'question_id': qid, 'question_text': text, 'condition': 'Fail',
         'answered_at': iso(days)}
    if comments:
        r['comments'] = comments
    if addressed:
        r['addressed'] = True
    return r


# ------------------------------------------------------- what counts as open

def test_it_finds_all_three_kinds():
    """The Action Items view shows three different things; so does this."""
    subs = [submission(
        responses=[failed()],
        action_items=[{'id': 'act_1750000000000_1111', 'text': 'Repaint the lobby',
                       'resolved': False}])]
    raised = [{'id': 'raised_1750000000000_2222', 'community': 'The Oscar at Georgetown',
               'text': 'Dumpster gate is broken', 'raised_at': iso(20),
               'resolved': False}]
    kinds = sorted(i['kind'] for i in R.open_items(subs, raised))
    assert kinds == ['manual', 'raised', 'standard'], kinds


def test_closed_work_is_not_open_work():
    subs = [submission(
        responses=[failed(addressed=True)],
        action_items=[{'id': 'act_1750000000000_1111', 'text': 'done', 'resolved': True}])]
    raised = [{'id': 'raised_1', 'community': 'C', 'text': 'x',
               'raised_at': iso(20), 'resolved': True}]
    assert R.open_items(subs, raised) == []


def test_a_passed_standard_is_not_an_action_item():
    subs = [submission(responses=[{'question_id': 'q1', 'condition': 'Pass',
                                   'answered_at': iso(40)}])]
    assert R.open_items(subs) == []


def test_a_manual_item_dates_itself_from_its_id():
    """Manual items carry no created_at — the milliseconds in the id are the
    only record of when one was written, so they are read rather than the
    visit's date being used for everything."""
    made = datetime(2026, 8, 1, 12, 0)
    aid = 'act_%d_4821' % int(made.timestamp() * 1000)
    subs = [submission(submitted_at=iso(2),
                       action_items=[{'id': aid, 'text': 'x', 'resolved': False}])]
    got = R.open_items(subs)[0]
    assert abs((got['opened'] - made).total_seconds()) < 2, got['opened']


def test_an_unreadable_date_does_not_become_ancient():
    """A timestamp that will not parse must not read as the epoch and fire on
    the first run."""
    subs = [submission(submitted_at='not a date',
                       responses=[{'question_id': 'q1', 'condition': 'Fail',
                                   'answered_at': 'also not a date'}])]
    assert R.open_items(subs) == []


# ------------------------------------------------------------------ the clock

def test_a_comment_is_an_update():
    """Greg's criterion: no update, not 'not closed'. An item being discussed
    is an item somebody is holding."""
    subs = [submission(responses=[failed(days=40, comments=[{'at': iso(2)}])])]
    it = R.open_items(subs)[0]
    assert (NOW - it['last_activity']).days == 2


def test_the_newest_comment_is_the_one_that_counts():
    subs = [submission(responses=[failed(days=40, comments=[
        {'at': iso(30)}, {'at': iso(3)}, {'at': iso(19)}])])]
    assert (NOW - R.open_items(subs)[0]['last_activity']).days == 3


def test_quiet_long_enough_is_reported_at_the_stage_it_passed():
    subs = [submission(responses=[failed(days=16)])]
    rows = R.due(R.open_items(subs), NOW, None, lambda k, s: False)
    assert [r['stage'] for r in rows] == [15]


def test_something_quiet_for_forty_days_reports_once_at_thirty():
    """Not twice, and not at the lower mark. Whoever reads it should see the
    worse number."""
    subs = [submission(responses=[failed(days=40)])]
    rows = R.due(R.open_items(subs), NOW, None, lambda k, s: False)
    assert len(rows) == 1
    assert rows[0]['stage'] == 30 and rows[0]['quiet_days'] == 40


def test_after_the_thirty_day_one_has_gone_nothing_repeats():
    subs = [submission(responses=[failed(days=40)])]
    items = R.open_items(subs)
    assert R.due(items, NOW, None, lambda k, s: s == 30) == [], \
        'the 30-day nudge would go out again every morning'


def test_having_had_the_fifteen_day_one_it_still_escalates_at_thirty():
    subs = [submission(responses=[failed(days=31)])]
    rows = R.due(R.open_items(subs), NOW, None, lambda k, s: s == 15)
    assert [r['stage'] for r in rows] == [30]


def test_fourteen_days_is_not_fifteen():
    subs = [submission(responses=[failed(days=14)])]
    assert R.due(R.open_items(subs), NOW, None, lambda k, s: False) == []


# ------------------------------------------------- not emptying the backlog

def test_arming_today_means_the_backlog_waits():
    """The whole reason arming exists. An item silent for ninety days is not
    somebody ignoring a reminder — there was no reminder."""
    subs = [submission(responses=[failed(days=90)])]
    armed = NOW - timedelta(days=1)
    assert R.due(R.open_items(subs), NOW, armed, lambda k, s: False) == []


def test_and_starts_counting_from_there():
    subs = [submission(responses=[failed(days=90)])]
    armed = NOW - timedelta(days=16)
    rows = R.due(R.open_items(subs), NOW, armed, lambda k, s: False)
    assert [r['stage'] for r in rows] == [15]


def test_an_item_quiet_since_after_arming_counts_from_itself():
    """Arming is a floor, not a replacement: something that went quiet after
    the switch is measured from when it went quiet."""
    subs = [submission(responses=[failed(days=20)])]
    armed = NOW - timedelta(days=60)
    rows = R.due(R.open_items(subs), NOW, armed, lambda k, s: False)
    assert rows[0]['quiet_days'] == 20


# -------------------------------------------------- the rule that must hold

INTERNAL = {'id': 'raised_1750000000000_9999', 'community': 'The Oscar at Georgetown',
            'text': 'ED may be leaving, plan cover', 'raised_at': None,
            'resolved': False, 'visibility': 'internal'}


def _mixed():
    internal = dict(INTERNAL, raised_at=iso(40))
    ordinary = {'id': 'raised_1750000000000_1111',
                'community': 'The Oscar at Georgetown',
                'text': 'Dumpster gate is broken', 'raised_at': iso(40),
                'resolved': False, 'visibility': 'community'}
    return R.due(R.open_items([], [internal, ordinary]), NOW, None, lambda k, s: False)


def test_an_internal_item_never_reaches_an_executive_director():
    groups = R.for_executive_director(_mixed())
    texts = [i['text'] for g in groups.values() for i in g]
    assert 'Dumpster gate is broken' in texts
    assert INTERNAL['text'] not in texts, 'an internal item leaked to the community'


def test_the_regional_does_see_it():
    """Regionals are the leadership the flag exists for, and their digest is
    their own message — which is why it can carry these."""
    groups = R.for_regional(_mixed())
    texts = [i['text'] for g in groups.values() for i in g]
    assert INTERNAL['text'] in texts


def test_an_item_with_no_community_goes_to_nobody():
    """Rather than to everybody, which is the other way a grouping bug ends."""
    rows = R.due(R.open_items([], [{'id': 'raised_1', 'community': '',
                                    'text': 'orphan', 'raised_at': iso(40),
                                    'resolved': False}]),
                 NOW, None, lambda k, s: False)
    assert R.for_executive_director(rows) == {}
    assert R.for_regional(rows) == {}


def test_the_regional_digest_is_only_the_second_stage():
    subs = [submission(responses=[failed(qid='q1', days=16),
                                  failed(qid='q2', days=31)])]
    rows = R.due(R.open_items(subs), NOW, None, lambda k, s: False)
    assert len(rows) == 2
    got = [i['quiet_days'] for g in R.for_regional(rows).values() for i in g]
    assert got == [31], f'a 15-day item was escalated to the regional ({got})'


def test_the_leak_would_survive_a_careless_caller():
    """for_executive_director is the whole of the guarantee, so it filters
    rather than trusting whoever assembled the rows."""
    rows = [{'key': 'k', 'community': 'C', 'text': INTERNAL['text'],
             'internal': True, 'stage': 15, 'quiet_days': 20, 'kind': 'raised'}]
    assert R.for_executive_director(rows) == {}


# -------------------------------------------------------------- the ledger

@pytest.fixture
def ledger(tmp_path):
    return R.ReminderLedger(str(tmp_path / 'reminders.json'))


def test_nothing_is_sent_twice(ledger):
    ledger.mark('standard::sub-1::q1', 15, NOW)
    assert ledger.already('standard::sub-1::q1', 15)
    assert not ledger.already('standard::sub-1::q1', 30)
    assert not ledger.already('standard::sub-1::q2', 15)


def test_it_survives_being_reopened(ledger, tmp_path):
    ledger.mark('k', 30, NOW)
    again = R.ReminderLedger(str(tmp_path / 'reminders.json'))
    assert again.already('k', 30), 'the record did not reach disk'


def test_arming_twice_keeps_the_first_date(ledger):
    """A redeploy or a second run must not quietly reset everybody's clock."""
    first = ledger.arm(NOW - timedelta(days=30))
    second = ledger.arm(NOW)
    assert first == second == NOW - timedelta(days=30)


def test_closed_items_are_forgotten(ledger):
    ledger.mark('standard::sub-1::q1', 15, NOW)
    ledger.mark('standard::sub-1::q2', 15, NOW)
    dropped = ledger.forget_closed(['standard::sub-1::q1'])
    assert dropped == 1
    assert ledger.already('standard::sub-1::q1', 15)
    assert not ledger.already('standard::sub-1::q2', 15)


def test_the_stop_button(ledger):
    assert ledger.is_paused() is False
    ledger.set_paused(True)
    assert ledger.is_paused() is True
    ledger.set_paused(False)
    assert ledger.is_paused() is False


# ------------------------------------------------ all the way to the wording

def _email_service():
    import app as A
    return A.email_service


def test_the_email_a_director_gets_carries_no_internal_item(monkeypatch):
    """End to end from raw data to the bytes of the message, because every
    step in between is somewhere the filter could be dropped."""
    svc = _email_service()
    captured = {}
    monkeypatch.setattr(svc, 'enabled', True)
    monkeypatch.setattr(svc, '_send',
                        lambda to, subject, html_body, text_body:
                        captured.update(to=to, subject=subject,
                                        html=html_body, text=text_body) or (True, 'ok'))

    groups = R.for_executive_director(_mixed())
    community, items = next(iter(groups.items()))
    svc.send_open_items_reminder(['ed@atlas.com'], community, items, 30)

    blob = captured['html'] + captured['text'] + captured['subject']
    assert 'Dumpster gate' in blob, 'the ordinary item should be there'
    assert 'ED may be leaving' not in blob, 'an internal item reached the community'


def test_the_email_says_how_to_stop_it(monkeypatch):
    """An item waiting on a vendor will never close. If the only way to stop
    the reminder is to close it, the reminder becomes noise."""
    svc = _email_service()
    captured = {}
    monkeypatch.setattr(svc, 'enabled', True)
    monkeypatch.setattr(svc, '_send',
                        lambda to, s, h, t: captured.update(html=h, text=t) or (True, 'ok'))
    rows = R.due(R.open_items([submission(responses=[failed(days=20)])]),
                 NOW, None, lambda k, s: False)
    svc.send_open_items_reminder(['ed@atlas.com'], 'C', rows, 15)
    # Both versions: almost everyone reads the HTML, and a check that only
    # looked at the plain text let a mutation through that emptied the other.
    for part in ('text', 'html'):
        assert 'comment counts as an update' in captured[part], \
            f'the {part} version does not say how to stop the reminder'


def test_the_wording_reports_rather_than_accuses(monkeypatch):
    svc = _email_service()
    captured = {}
    monkeypatch.setattr(svc, 'enabled', True)
    monkeypatch.setattr(svc, '_send',
                        lambda to, s, h, t: captured.update(text=t, subject=s) or (True, 'ok'))
    rows = R.due(R.open_items([submission(responses=[failed(days=20)])]),
                 NOW, None, lambda k, s: False)
    svc.send_open_items_reminder(['ed@atlas.com'], 'C', rows, 15)
    blob = (captured['text'] + captured['subject']).lower()
    for word in ('overdue', 'failed to', 'you have not', 'neglect'):
        assert word not in blob, f'the reminder reads as an accusation ("{word}")'


# ------------------------------------------------------------ the safety catch

def test_it_does_not_send_unless_told_to(tmp_path, monkeypatch, capsys):
    """The one that matters most. A mistake here is in the inbox of every
    Executive Director at once, so the default has to be silence."""
    import app as A
    import send_reminders as S

    monkeypatch.setattr(S, 'LEDGER', R.ReminderLedger(str(tmp_path / 'r.json')))
    S.LEDGER.arm(NOW - timedelta(days=365))

    # Give the run somebody to write to. The development data has no community
    # accounts, so without this the job correctly sends nothing and the test
    # would pass while asserting nothing at all.
    monkeypatch.setattr(A, 'community_account_emails', lambda *a, **k: ['ed@atlas.com'])
    monkeypatch.setattr(A, 'region_leader_emails', lambda *a, **k: ['regional@atlas.com'])

    sent = []
    monkeypatch.setattr(A.email_service, 'send_open_items_reminder',
                        lambda *a, **k: sent.append(a) or (True, 'ok'))
    monkeypatch.setattr(A.email_service, 'send_regional_open_items',
                        lambda *a, **k: sent.append(a) or (True, 'ok'))

    S.main([])
    assert sent == [], 'a bare run sent email'
    assert 'ENSAYO' in capsys.readouterr().out

    S.main(['--send', '--force'])
    assert sent, 'nothing went out even when asked'


def test_a_paused_run_sends_nothing(tmp_path, monkeypatch):
    import app as A
    import send_reminders as S
    monkeypatch.setattr(S, 'LEDGER', R.ReminderLedger(str(tmp_path / 'r.json')))
    monkeypatch.setattr(A, 'community_account_emails', lambda *a, **k: ['ed@atlas.com'])
    monkeypatch.setattr(A, 'region_leader_emails', lambda *a, **k: ['reg@atlas.com'])
    S.LEDGER.arm(NOW - timedelta(days=365))
    S.LEDGER.set_paused(True)
    sent = []
    monkeypatch.setattr(A.email_service, 'send_open_items_reminder',
                        lambda *a, **k: sent.append(a) or (True, 'ok'))
    S.main(['--send', '--force'])
    assert sent == []


def test_an_unarmed_run_sends_nothing(tmp_path, monkeypatch):
    import app as A
    import send_reminders as S
    monkeypatch.setattr(S, 'LEDGER', R.ReminderLedger(str(tmp_path / 'r.json')))
    monkeypatch.setattr(A, 'community_account_emails', lambda *a, **k: ['ed@atlas.com'])
    monkeypatch.setattr(A, 'region_leader_emails', lambda *a, **k: ['reg@atlas.com'])
    sent = []
    monkeypatch.setattr(A.email_service, 'send_open_items_reminder',
                        lambda *a, **k: sent.append(a) or (True, 'ok'))
    S.main(['--send', '--force'])
    assert sent == [], 'it sent before the clock was ever started'


def test_a_failed_send_is_not_recorded_as_done(tmp_path, monkeypatch):
    """Otherwise one SES hiccup silently drops that nudge for good."""
    import app as A
    import send_reminders as S
    monkeypatch.setattr(S, 'LEDGER', R.ReminderLedger(str(tmp_path / 'r.json')))
    monkeypatch.setattr(A, 'community_account_emails', lambda *a, **k: ['ed@atlas.com'])
    monkeypatch.setattr(A, 'region_leader_emails', lambda *a, **k: ['reg@atlas.com'])
    S.LEDGER.arm(NOW - timedelta(days=365))
    monkeypatch.setattr(A.email_service, 'send_open_items_reminder',
                        lambda *a, **k: (False, 'SES said no'))
    monkeypatch.setattr(A.email_service, 'send_regional_open_items',
                        lambda *a, **k: (False, 'SES said no'))
    S.main(['--send', '--force'])
    assert S.LEDGER.sent == {}, 'a send that failed was written down as sent'


# ------------------------------------- one message per place, per morning

def _plan_for(monkeypatch, tmp_path, subs, raised=(), armed_days=365):
    """Run the real planner over made-up data.

    The double-send this guards against was invisible in the unit tests and
    obvious the first time it met a real community, so this drives the
    planner itself rather than the pieces under it.
    """
    import app as A
    import send_reminders as S
    monkeypatch.setattr(S, 'LEDGER', R.ReminderLedger(str(tmp_path / 'r.json')))
    S.LEDGER.arm(NOW - timedelta(days=armed_days))
    monkeypatch.setattr(A.inspection_service, 'get_all_submissions', lambda: subs)
    monkeypatch.setattr(A.raised_item_service, 'for_communities',
                        lambda *a, **k: list(raised))
    monkeypatch.setattr(A, 'all_communities', lambda: ['Tribute at One Loudoun'])
    monkeypatch.setattr(A, 'community_account_emails', lambda *a, **k: ['ed@atlas.com'])
    monkeypatch.setattr(A, 'region_leader_emails', lambda *a, **k: ['reg@atlas.com'])
    monkeypatch.setattr(A, 'region_for_community',
                        lambda c: {'id': 'dmv', 'name': 'DMV'})
    return S._plan(NOW)


def test_a_community_with_both_marks_gets_one_email(monkeypatch, tmp_path):
    """Tribute at One Loudoun had ten items at fifteen days and three past
    thirty. It was going to send its Executive Director two emails minutes
    apart, which is how a sender ends up in a filter."""
    subs = [submission(community='Tribute at One Loudoun',
                       responses=[failed(qid='q1', days=16),
                                  failed(qid='q2', days=17),
                                  failed(qid='q3', days=36)])]
    ed_mail, _, _, _ = _plan_for(monkeypatch, tmp_path, subs)
    assert len(ed_mail) == 1, f'{len(ed_mail)} emails to the same person'
    assert len(ed_mail[0]['items']) == 3
    assert ed_mail[0]['past_second'] == 1, 'the escalated one is not counted'


def test_the_worst_one_is_named_and_the_rest_ordered_behind_it(monkeypatch, tmp_path):
    subs = [submission(community='Tribute at One Loudoun',
                       responses=[failed(qid='q1', days=16),
                                  failed(qid='q2', days=40)])]
    ed_mail, _, _, _ = _plan_for(monkeypatch, tmp_path, subs)
    assert [i['quiet_days'] for i in ed_mail[0]['items']] == [40, 16]


def test_merging_did_not_cost_the_escalation(monkeypatch, tmp_path):
    """The regional still gets their own message about the 30-day ones."""
    subs = [submission(community='Tribute at One Loudoun',
                       responses=[failed(qid='q1', days=16),
                                  failed(qid='q2', days=36)])]
    _, regional_mail, _, _ = _plan_for(monkeypatch, tmp_path, subs)
    assert len(regional_mail) == 1
    days = [i['quiet_days'] for v in regional_mail[0]['by_community'].values() for i in v]
    assert days == [36], f'the regional list is wrong ({days})'


def test_each_item_is_still_recorded_at_its_own_stage(monkeypatch, tmp_path):
    """Merging the message must not merge the bookkeeping: the 15-day item
    has to stay eligible for its own 30-day escalation later."""
    subs = [submission(community='Tribute at One Loudoun',
                       responses=[failed(qid='q1', days=16),
                                  failed(qid='q2', days=36)])]
    ed_mail, _, _, _ = _plan_for(monkeypatch, tmp_path, subs)
    stages = sorted(i['stage'] for i in ed_mail[0]['items'])
    assert stages == [15, 30], f'both items were filed under one stage ({stages})'
