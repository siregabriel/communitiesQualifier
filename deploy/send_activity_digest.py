#!/usr/bin/env python3
"""
Daily activity digest.

Emails the admin-notify list a rundown of the last 24 hours: who signed in,
which visits were submitted, what was marked as addressed, and anything that
touched passwords or accounts. Also lists people who have an account but have
never signed in.

Run from cron on the server, e.g. 7:05 PM daily (after the workday):

  sudo crontab -e
  5 19 * * * set -a; . /etc/atlas/atlas.env; set +a; \
             cd /home/ubuntu/CommunitiesQualifier/app_mantenimiento && \
             /home/ubuntu/CommunitiesQualifier/.venv/bin/python \
             /home/ubuntu/CommunitiesQualifier/deploy/send_activity_digest.py \
             >> /var/log/atlas-activity-digest.log 2>&1

The env file must be sourced first (as above) because MAIL_FROM, SES_REGION and
the AWS credentials live there — cron does not inherit systemd's environment.

Override the window with DIGEST_HOURS (default 24).
"""

import os
import sys
from datetime import datetime

# Make sure we can import the app package.
HERE = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.join(os.path.dirname(HERE), 'app_mantenimiento')
sys.path.insert(0, APP_DIR)

HOURS = int(os.environ.get('DIGEST_HOURS', '24'))


def main():
    import app  # initializes services from the environment

    if not app.email_service.enabled:
        print(f"{datetime.now().isoformat()} email disabled (MAIL_FROM not set); nothing sent")
        return

    sent, detail, digest = app.run_activity_digest(hours=HOURS)
    stamp = datetime.now().isoformat()
    print(f"{stamp} activity digest ({HOURS}h): "
          f"{'SENT' if sent else 'NOT SENT'} — {detail}")
    print(f"  signed in: {len(digest['signed_in'])}"
          f" | visits: {len(digest['visits'])}"
          f" | addressed: {len(digest['addressed'])}"
          f" | password events: {len(digest['security'])}"
          f" | account changes: {len(digest['accounts'])}")
    if digest['never_signed_in']:
        print(f"  never signed in: {', '.join(digest['never_signed_in'])}")


if __name__ == '__main__':
    main()
