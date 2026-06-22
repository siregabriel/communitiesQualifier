"""
Email Service (Amazon SES)
Sends a post-visit summary email when an inspection is submitted.

Env-driven, like the S3 backend:
  - MAIL_FROM         verified SES sender, e.g. "Atlas Standards <noreply@atlasseniorliving.net>"
  - SES_REGION        SES region (defaults to AWS_REGION)
  - MAIL_EXTRA_RECIPIENTS  comma-separated fixed recipients added to every email
  - APP_BASE_URL      base URL for the "view report" link, e.g. https://standards.atlasseniorliving.net

If MAIL_FROM is unset the service is disabled and send() is a no-op, so the app
runs fine before email is configured. Send failures never raise to the caller —
a failed email must not break an inspection submission.
"""

import re
import html
import logging
from urllib.parse import quote

logger = logging.getLogger(__name__)

_EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


def _valid(addr):
    return bool(addr) and bool(_EMAIL_RE.match(addr.strip()))


class EmailService:
    def __init__(self, mail_from=None, region=None,
                 extra_recipients=None, app_base_url=None):
        self.mail_from = (mail_from or '').strip() or None
        self.region = region
        self.extra_recipients = [a.strip() for a in (extra_recipients or []) if _valid(a)]
        self.app_base_url = (app_base_url or '').rstrip('/')
        self.enabled = bool(self.mail_from)
        self._ses = None

    @property
    def ses(self):
        if self._ses is None:
            import boto3
            self._ses = boto3.client('ses', region_name=self.region)
        return self._ses

    @staticmethod
    def _summarize(submission):
        responses = submission.get('responses', []) or []
        passed = sum(1 for r in responses if r.get('condition') == 'Pass')
        failed = sum(1 for r in responses if r.get('condition') == 'Fail')
        total = passed + failed
        score = round(passed / total * 100) if total else None
        fails = [r for r in responses if r.get('condition') == 'Fail']
        return passed, failed, total, score, fails

    def report_link(self, community):
        if not self.app_base_url:
            return None
        return f"{self.app_base_url}/?community={quote(community or '')}"

    def _build(self, submission, survey_type_name=None):
        community = submission.get('community', 'Unknown community')
        inspector = submission.get('inspector_name') or submission.get('username') or 'Unknown'
        when = (submission.get('submitted_at') or '')[:10]
        passed, failed, total, score, fails = self._summarize(submission)
        score_txt = f"{score}%" if score is not None else "N/A"
        link = self.report_link(community)

        subject = f"Inspection — {community}: {score_txt} ({passed}/{total} pass)"

        # Plain text
        lines = [
            f"Inspection submitted for {community}",
            f"Inspector: {inspector}",
            f"Date: {when}",
        ]
        if survey_type_name:
            lines.append(f"Survey type: {survey_type_name}")
        lines += [
            f"Overall score: {score_txt}",
            f"Passed: {passed} / {total}    Failed: {failed}",
        ]
        if fails:
            lines.append("")
            lines.append("Failed items:")
            for r in fails:
                q = r.get('question_text', 'Item')
                note = r.get('description', '')
                lines.append(f"  - {q}" + (f": {note}" if note else ""))
        if link:
            lines += ["", f"View the full report: {link}"]
        text = "\n".join(lines)

        # HTML
        def esc(s):
            return html.escape(str(s or ''))

        score_color = '#0f8a5f' if (score is not None and score >= 75) else (
            '#b58b00' if (score is not None and score >= 50) else '#d13212')
        fail_rows = ''.join(
            f"<li style='margin:4px 0'><strong>{esc(r.get('question_text','Item'))}</strong>"
            + (f" — {esc(r.get('description',''))}" if r.get('description') else "")
            + "</li>"
            for r in fails
        )
        fail_block = (
            f"<h3 style='font-size:15px;color:#d13212;margin:18px 0 6px'>Failed items ({failed})</h3>"
            f"<ul style='margin:0;padding-left:18px;color:#1f2937;font-size:14px'>{fail_rows}</ul>"
        ) if fails else "<p style='color:#0f8a5f;font-size:14px;margin:14px 0'>All items passed.</p>"

        button = (
            f"<a href='{esc(link)}' style='display:inline-block;background:#00285c;color:#fff;"
            f"text-decoration:none;font-weight:700;padding:12px 22px;border-radius:8px;"
            f"font-size:14px'>View full report</a>"
        ) if link else ""

        survey_row = (
            f"<tr><td style='color:#6b7280;padding:3px 12px 3px 0'>Survey type</td>"
            f"<td style='font-weight:600'>{esc(survey_type_name)}</td></tr>"
        ) if survey_type_name else ""

        html_body = f"""\
<div style="font-family:Helvetica,Arial,sans-serif;max-width:600px;margin:0 auto;color:#0f1e36">
  <div style="background:#00285c;color:#fff;padding:20px 24px;border-radius:10px 10px 0 0">
    <div style="font-size:13px;letter-spacing:.5px;opacity:.85">ATLAS STANDARDS</div>
    <div style="font-size:20px;font-weight:800;margin-top:4px">{esc(community)}</div>
  </div>
  <div style="border:1px solid #d9dfe8;border-top:none;border-radius:0 0 10px 10px;padding:22px 24px">
    <div style="font-size:34px;font-weight:800;color:{score_color}">{esc(score_txt)}</div>
    <div style="color:#6b7280;font-size:13px;margin-bottom:14px">Overall score &middot; {passed}/{total} passed</div>
    <table style="font-size:14px;border-collapse:collapse;margin-bottom:6px">
      <tr><td style="color:#6b7280;padding:3px 12px 3px 0">Inspector</td><td style="font-weight:600">{esc(inspector)}</td></tr>
      <tr><td style="color:#6b7280;padding:3px 12px 3px 0">Date</td><td style="font-weight:600">{esc(when)}</td></tr>
      {survey_row}
    </table>
    {fail_block}
    <div style="margin-top:20px">{button}</div>
  </div>
  <div style="color:#9ca3af;font-size:11px;text-align:center;padding:14px">
    Atlas Senior Living — Communities Standards
  </div>
</div>"""

        return subject, html_body, text

    def send_inspection_report(self, submission, recipients=None, survey_type_name=None):
        """
        Send the summary email. recipients = region-leader addresses; the fixed
        MAIL_EXTRA_RECIPIENTS are always added. Returns (sent: bool, detail: str).
        Never raises.
        """
        if not self.enabled:
            return (False, 'email not configured')

        to = []
        for addr in list(recipients or []) + self.extra_recipients:
            a = (addr or '').strip()
            if _valid(a) and a.lower() not in [x.lower() for x in to]:
                to.append(a)
        if not to:
            return (False, 'no valid recipients')

        try:
            subject, html_body, text = self._build(submission, survey_type_name)
            self.ses.send_email(
                Source=self.mail_from,
                Destination={'ToAddresses': to},
                Message={
                    'Subject': {'Data': subject, 'Charset': 'UTF-8'},
                    'Body': {
                        'Html': {'Data': html_body, 'Charset': 'UTF-8'},
                        'Text': {'Data': text, 'Charset': 'UTF-8'},
                    },
                },
            )
            logger.info(f'Inspection email sent to {len(to)} recipient(s) for '
                        f"{submission.get('community')}")
            return (True, f'sent to {len(to)}')
        except Exception as e:
            logger.error(f'Failed to send inspection email: {e}')
            return (False, str(e))
