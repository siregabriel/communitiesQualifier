#!/usr/bin/env python
"""
The daily nudge for open action items that have gone quiet.

Run by a systemd timer. Two things about it are deliberate and worth not
undoing:

  1. It does not send unless told to. Without --send it prints what it would
     have done and exits. This is the first thing in the app that writes to
     a lot of people without anybody asking it to, and a mistake here lands
     in the inbox of every Executive Director at once.

  2. It does nothing at all until it has been armed. Arming records the
     moment the clock starts, so switching this on does not empty however
     much backlog exists into everybody's inbox on the first morning. Items
     are measured from their last update or from the arming date, whichever
     is later.

Usage
    python send_reminders.py                 # dry run: print, send nothing
    python send_reminders.py --send          # actually send
    python send_reminders.py --arm           # start the clock (once)
    python send_reminders.py --pause         # stop sending, keep the timer
    python send_reminders.py --resume
    python send_reminders.py --status
    python send_reminders.py --send --force  # ignore the weekend rule
"""

import argparse
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import app as A  # noqa: E402
from services import reminder_service as R  # noqa: E402

LEDGER = R.ReminderLedger(os.path.join(A.DATA_FOLDER, 'reminders.json'))


# ------------------------------------------------------------------ helpers

def _plan(now):
    """What today would send, as (ed_mail, regional_mail, rows, all_keys).

    Pure enough to print: it reads the data and decides, but sends nothing
    and writes nothing. --send and the dry run share it, so what you see in
    a dry run is what goes out.
    """
    submissions = A.inspection_service.get_all_submissions()
    # include_internal is asked for explicitly, and only because the
    # regional's own digest carries them. Everything bound for an Executive
    # Director goes through for_executive_director(), which strips them — so
    # that one function is the whole of the guarantee, and is tested as such.
    raised = A.raised_item_service.for_communities(
        A.all_communities(), include_internal=True)
    items = R.open_items(submissions, raised)
    rows = R.due(items, now, LEDGER.armed(), LEDGER.already)

    # --- the Executive Director's own community, internal items removed ---
    ed_mail = []
    for community, group in sorted(R.for_executive_director(rows).items()):
        by_stage = {}
        for r in group:
            by_stage.setdefault(r['stage'], []).append(r)
        for stage, group_items in sorted(by_stage.items()):
            to = A.community_account_emails(community)
            ed_mail.append({
                'community': community, 'stage': stage, 'to': to,
                'items': sorted(group_items, key=lambda i: -i['quiet_days']),
            })

    # --- the regional, once for the whole region, second stage only ---
    regional_mail = []
    by_region = {}
    for community, group in R.for_regional(rows).items():
        region = A.region_for_community(community)
        rid = (region or {}).get('id') or ''
        slot = by_region.setdefault(rid, {'name': (region or {}).get('name', ''),
                                          'to': A.region_leader_emails(community),
                                          'by_community': {}})
        slot['by_community'][community] = sorted(group, key=lambda i: -i['quiet_days'])
    for rid, slot in sorted(by_region.items()):
        regional_mail.append({'region_id': rid, **slot})

    return ed_mail, regional_mail, rows, [i['key'] for i in items]


def _print_plan(now, ed_mail, regional_mail, rows):
    armed = LEDGER.armed()
    print(f'\n  ahora        : {now:%Y-%m-%d %H:%M}')
    print(f'  reloj desde  : {armed:%Y-%m-%d %H:%M}' if armed else
          '  reloj desde  : SIN ARMAR — no se enviaría nada')
    print(f'  en pausa     : {"sí" if LEDGER.is_paused() else "no"}')
    print(f'  items a avisar: {len(rows)}\n')

    if not ed_mail and not regional_mail:
        print('  nada que enviar hoy.\n')
        return

    if armed is None:
        # Without a start date `due` measures from each item's own last
        # update, so this listing is the backlog as it stands — useful to see
        # before arming, and misleading if read as today's outbox.
        print('  (atraso existente. Con el reloj sin armar NO se enviaría nada\n'
              '   de esto: al armar, todos estos empiezan a contar de cero.)\n')

    for m in ed_mail:
        who = ', '.join(m['to']) if m['to'] else '*** NADIE — sin correo ***'
        print(f"  ED · {m['community']} · {m['stage']} días → {who}")
        for it in m['items']:
            print(f"        [{it['quiet_days']:>3}d] {it['kind']:<9} {it['text'][:64]}")
    for m in regional_mail:
        who = ', '.join(m['to']) if m['to'] else '*** NADIE — sin correo ***'
        total = sum(len(v) for v in m['by_community'].values())
        print(f"\n  REGIONAL · {m['name'] or m['region_id']} · {total} items → {who}")
        for community, items in sorted(m['by_community'].items()):
            for it in items:
                flag = ' (interno)' if it['internal'] else ''
                print(f"        [{it['quiet_days']:>3}d] {community}: {it['text'][:48]}{flag}")
    print()


def _note_nobody_to_tell(community, stage):
    """A reminder with nowhere to go is worth the same line as a report with
    nowhere to go — otherwise a community nobody has onboarded looks exactly
    like one that reads its email."""
    try:
        A.activity_service.log(
            'system', 'reminder_undelivered',
            f'{community} has nobody to remind',
            meta={'community': community, 'stage': stage,
                  'reason': f'{community} has no account here yet'})
    except Exception:  # noqa: BLE001 - a log must never stop the run
        pass


# --------------------------------------------------------------------- main

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--send', action='store_true',
                    help='actually send; without this it only prints')
    ap.add_argument('--arm', action='store_true', help='start the clock (once)')
    ap.add_argument('--pause', action='store_true')
    ap.add_argument('--resume', action='store_true')
    ap.add_argument('--status', action='store_true')
    ap.add_argument('--force', action='store_true',
                    help='run on a weekend too')
    args = ap.parse_args(argv)

    if args.pause or args.resume:
        state = LEDGER.set_paused(bool(args.pause))
        print(f'  recordatorios {"EN PAUSA" if state else "activos"}')
        return 0

    if args.arm:
        when = LEDGER.arm()
        print(f'  reloj armado desde {when:%Y-%m-%d %H:%M}')
        print('  (si ya estaba armado, esta fecha es la original y no cambió)')
        return 0

    now = datetime.now()

    if args.status:
        ed_mail, regional_mail, rows, _ = _plan(now)
        _print_plan(now, ed_mail, regional_mail, rows)
        return 0

    if LEDGER.is_paused():
        print('  en pausa — no se envía nada. Reanudar con --resume')
        return 0

    if LEDGER.armed() is None:
        print('  sin armar — no se envía nada. Arrancar el reloj con --arm')
        return 0

    # A Saturday reminder is read on Monday, by which time it is one more
    # unread thing rather than a nudge.
    if now.weekday() >= 5 and not args.force:
        print('  fin de semana — nada que hacer (--force para forzarlo)')
        return 0

    ed_mail, regional_mail, rows, live_keys = _plan(now)

    if not args.send:
        _print_plan(now, ed_mail, regional_mail, rows)
        print('  ENSAYO. Nada fue enviado. Añade --send para enviar de verdad.\n')
        return 0

    sent_rows, failures = [], []
    ed_sent = regional_sent = 0

    for m in ed_mail:
        if not m['to']:
            _note_nobody_to_tell(m['community'], m['stage'])
            continue
        ok, detail = A.email_service.send_open_items_reminder(
            m['to'], m['community'], m['items'], m['stage'])
        if ok:
            ed_sent += 1
            sent_rows.extend(m['items'])
        else:
            failures.append(f"ED {m['community']} ({m['stage']}d): {detail}")

    for m in regional_mail:
        if not m['to']:
            continue
        ok, detail = A.email_service.send_regional_open_items(
            m['to'], m['name'], m['by_community'])
        if ok:
            regional_sent += 1
        else:
            failures.append(f"regional {m['name'] or m['region_id']}: {detail}")

    # Marked only for what actually left. A send that failed should be tried
    # again tomorrow, not recorded as done.
    marked = LEDGER.mark_many(sent_rows, now)
    forgotten = LEDGER.forget_closed(live_keys)

    # Counted from what actually left, not from what was planned. The first
    # version printed the plan, which reads as success on a run where every
    # single send was skipped for having no address.
    print(f'  enviados: {ed_sent}/{len(ed_mail)} a EDs, '
          f'{regional_sent}/{len(regional_mail)} a regionales')
    print(f'  items anotados: {marked}   cerrados y olvidados: {forgotten}')
    for f in failures:
        print(f'  FALLO  {f}')
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
