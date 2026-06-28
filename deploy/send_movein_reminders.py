#!/usr/bin/env python3
"""
Daily move-in reminder sweep.

Emails the community's region leaders (plus the admin-notify list) for every
ACTIVE move-in whose target date is within the next few days and still has open
checklist items. Required ("gate") items are highlighted.

Run from cron on the server, e.g. 7:00 AM daily:

  crontab -e
  0 7 * * * cd /home/ubuntu/CommunitiesQualifier/app_mantenimiento && \
            /home/ubuntu/CommunitiesQualifier/.venv/bin/python \
            /home/ubuntu/CommunitiesQualifier/deploy/send_movein_reminders.py \
            >> /var/log/atlas-movein-reminders.log 2>&1

The script reads the same environment the app uses (MAIL_FROM, SES_REGION, etc.)
via systemd's EnvironmentFile is NOT loaded here, so make sure the cron entry
runs in an environment that has those vars, or source them first. Easiest: the
systemd service already has them; for cron, prepend the env file:

  0 7 * * * set -a; . /etc/atlas/atlas.env; set +a; cd /home/ubuntu/CommunitiesQualifier/app_mantenimiento && \
            /home/ubuntu/CommunitiesQualifier/.venv/bin/python /home/ubuntu/CommunitiesQualifier/deploy/send_movein_reminders.py \
            >> /var/log/atlas-movein-reminders.log 2>&1
"""

import os
import sys
from datetime import datetime

# Make sure we can import the app package (run from app_mantenimiento, or add it).
HERE = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.join(os.path.dirname(HERE), 'app_mantenimiento')
sys.path.insert(0, APP_DIR)

DAYS_AHEAD = int(os.environ.get('MOVEIN_REMINDER_DAYS', '3'))


def main():
    import app  # initializes services from the environment
    if not app.email_service.enabled:
        print(f"{datetime.now().isoformat()} email disabled (MAIL_FROM not set); nothing sent")
        return
    results = app.run_movein_reminders(days_ahead=DAYS_AHEAD)
    ok = sum(1 for r in results if r.get('sent'))
    print(f"{datetime.now().isoformat()} move-in reminders: {ok}/{len(results)} sent")
    for r in results:
        print(f"  - {r['resident']} @ {r['community']} (in {r['days_left']}d) -> "
              f"{'OK' if r['sent'] else 'FAIL: ' + str(r['detail'])} ({len(r['recipients'])} recipients)")


if __name__ == '__main__':
    main()
