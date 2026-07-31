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
                 extra_recipients=None, app_base_url=None, configuration_set=None):
        self.mail_from = (mail_from or '').strip() or None
        self.region = region
        self.extra_recipients = [a.strip() for a in (extra_recipients or []) if _valid(a)]
        self.app_base_url = (app_base_url or '').rstrip('/')
        self.configuration_set = (configuration_set or '').strip() or None
        self.enabled = bool(self.mail_from)
        self._ses = None

    def _send_email(self, **kwargs):
        """ses.send_email with the configuration set attached (for bounce/
        complaint tracking) when one is configured."""
        if self.configuration_set:
            kwargs['ConfigurationSetName'] = self.configuration_set
        return self.ses.send_email(**kwargs)

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

    @staticmethod
    def _criteria_for(response, criteria_map):
        if not criteria_map:
            return []
        qid = response.get('question_id')
        if qid and criteria_map.get(qid):
            return criteria_map[qid]
        key = 't:' + (response.get('question_text') or '').strip().lower()
        return criteria_map.get(key, [])

    def _build(self, submission, survey_type_name=None, criteria_map=None):
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
                for c in self._criteria_for(r, criteria_map):
                    lines.append(f"      • {c}")
        if link:
            lines += ["", f"View the full report: {link}"]
        text = "\n".join(lines)

        # HTML
        def esc(s):
            return html.escape(str(s or ''))

        score_color = '#0f8a5f' if (score is not None and score >= 75) else (
            '#b58b00' if (score is not None and score >= 50) else '#d13212')
        def fail_li(r):
            crit = self._criteria_for(r, criteria_map)
            crit_html = ''
            if crit:
                items = ''.join(f"<li style='margin:2px 0'>{esc(c)}</li>" for c in crit)
                crit_html = (f"<div style='font-size:12px;color:#6b7280;margin:4px 0 2px'>Standard — to pass, must include:</div>"
                             f"<ul style='margin:0 0 6px;padding-left:16px;color:#475569;font-size:12px'>{items}</ul>")
            return (f"<li style='margin:8px 0'><strong>{esc(r.get('question_text','Item'))}</strong>"
                    + (f" — {esc(r.get('description',''))}" if r.get('description') else "")
                    + crit_html + "</li>")
        fail_rows = ''.join(fail_li(r) for r in fails)
        fail_block = (
            f"<h3 style='font-size:15px;color:#d13212;margin:18px 0 6px'>Failed items ({failed})</h3>"
            f"<ul style='margin:0;padding-left:18px;color:#1f2937;font-size:14px'>{fail_rows}</ul>"
        ) if fails else "<p style='color:#0f8a5f;font-size:14px;margin:14px 0'>All items passed.</p>"

        # Ad-hoc action items raised during the visit (not standards, no score
        # impact) — surfaced so the right team sees them without digging.
        manual = [i for i in (submission.get('action_items') or []) if not i.get('resolved')]
        if manual:
            pr_color = {'high': '#b42318', 'medium': '#92620a', 'low': '#475569'}
            rows = ''.join(
                f"<li style='margin:6px 0'>"
                f"<b style='color:{pr_color.get(i.get('priority'), '#92620a')}'>"
                f"[{esc((i.get('priority') or 'medium').upper())}]</b> {esc(i.get('text'))}"
                + (f"<br><span style='color:#6b7280;font-size:13px'>For: {esc(i.get('assigned_to'))}</span>"
                   if i.get('assigned_to') else "")
                + "</li>"
                for i in manual)
            action_block = (
                f"<h3 style='font-size:15px;color:#d97706;margin:18px 0 6px'>"
                f"Action items raised on this visit ({len(manual)})</h3>"
                f"<ul style='margin:0;padding-left:18px;color:#1f2937;font-size:14px'>{rows}</ul>"
                f"<p style='color:#9ca3af;font-size:12px;margin:6px 0 0'>"
                f"These are follow-up tasks noted by the inspector — they don't affect the score.</p>"
            )
        else:
            action_block = ""

        button = (
            f"<a href='{esc(link)}' style='display:inline-block;background:#00285c;color:#fff;"
            f"text-decoration:none;font-weight:700;padding:12px 22px;border-radius:8px;"
            f"font-size:14px'>View full report</a>"
        ) if link else ""

        survey_row = (
            f"<tr><td style='color:#6b7280;padding:3px 12px 3px 0'>Survey type</td>"
            f"<td style='font-weight:600'>{esc(survey_type_name)}</td></tr>"
        ) if survey_type_name else ""

        # Logo sits on its own white band (the logo is designed for light
        # backgrounds); the navy band with the community name goes below it.
        logo_url = f"{self.app_base_url}/static/atlas-logo.png" if self.app_base_url else None
        logo_band = (
            f"<div style='background:#fff;border:1px solid #d9dfe8;border-bottom:none;"
            f"border-radius:10px 10px 0 0;padding:16px 24px;text-align:center'>"
            f"<img src='{esc(logo_url)}' alt='Atlas Senior Living' "
            f"style='height:34px;display:inline-block'></div>"
        ) if logo_url else ""
        navy_radius = "0" if logo_band else "10px 10px 0 0"

        html_body = f"""\
<div style="font-family:Helvetica,Arial,sans-serif;max-width:600px;margin:0 auto;color:#0f1e36">
  {logo_band}
  <div style="background:#00285c;color:#fff;padding:18px 24px;border-radius:{navy_radius}">
    <div style="font-size:12px;letter-spacing:.5px;opacity:.85">COMMUNITIES STANDARDS</div>
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
    {action_block}
    <div style="margin-top:20px">{button}</div>
  </div>
  <div style="color:#9ca3af;font-size:11px;text-align:center;padding:14px">
    Atlas Senior Living — Communities Standards
  </div>
</div>"""

        return subject, html_body, text

    def send_movein_reminder(self, recipients, resident, community, target_date,
                             days_left, missing_required, missing_other):
        """Remind the team that a move-in is approaching and items are still open.
        missing_required / missing_other are lists of item-text strings."""
        if not self.enabled:
            return (False, 'disabled')

        def esc(s):
            return html.escape(str(s or ''))

        when = (f"in {days_left} day{'s' if days_left != 1 else ''}" if days_left and days_left > 0
                else ("today" if days_left == 0 else "soon"))

        def li_list(items, color):
            rows = ''.join(
                f"<li style='margin:3px 0;color:{color}'>{esc(t)}</li>" for t in items)
            return f"<ul style='margin:6px 0 14px;padding-left:20px;font-size:14px'>{rows}</ul>"

        req_block = ''
        if missing_required:
            req_block = (
                "<div style='font-weight:700;color:#b42318;margin-bottom:4px'>"
                "&#128274; Required before move-in</div>" + li_list(missing_required, '#7f1d1d'))
        other_block = ''
        if missing_other:
            other_block = (
                "<div style='font-weight:700;color:#475569;margin-bottom:4px'>"
                "Still open</div>" + li_list(missing_other, '#475569'))

        link = (f"<p style='margin-top:8px'><a href='{esc(self.app_base_url)}/dashboard?view=move-ins' "
                f"style='display:inline-block;background:#00285c;color:#fff;text-decoration:none;"
                f"font-weight:700;padding:11px 20px;border-radius:8px;font-size:14px'>Open Move-Ins</a></p>"
                if self.app_base_url else "")

        body = f"""\
<p style="font-size:14px;margin:0 0 12px">The move-in for <b>{esc(resident)}</b> at
<b>{esc(community)}</b> is <b>{when}</b> (target date {esc(target_date) or 'TBD'}),
and some checklist items are still open.</p>
{req_block}
{other_block}
{link}"""
        text_lines = [f"Move-in reminder: {resident} at {community} is {when} (target {target_date})."]
        if missing_required:
            text_lines.append("Required before move-in: " + "; ".join(missing_required))
        if missing_other:
            text_lines.append("Still open: " + "; ".join(missing_other))
        subject = f"Move-in {when}: {resident} ({community})"
        return self._send(recipients, subject, self._shell("Move-In Reminder", body), "\n".join(text_lines))

    def send_movein_completed(self, recipients, resident, community, target_date, done, total):
        """Notify the team that a resident's move-in checklist is complete."""
        if not self.enabled:
            return (False, 'disabled')

        def esc(s):
            return html.escape(str(s or ''))

        link = (f"<p style='margin-top:8px'><a href='{esc(self.app_base_url)}/dashboard?view=move-ins' "
                f"style='display:inline-block;background:#00285c;color:#fff;text-decoration:none;"
                f"font-weight:700;padding:11px 20px;border-radius:8px;font-size:14px'>Open Move-Ins</a></p>"
                if self.app_base_url else "")
        body = f"""\
<p style="font-size:14px;margin:0 0 12px">The move-in checklist for <b>{esc(resident)}</b> at
<b>{esc(community)}</b> has been <b style="color:#0f8a5f">completed</b>
({esc(done)}/{esc(total)} items, target date {esc(target_date) or 'n/a'}).</p>
<p style="font-size:14px;margin:0 0 4px">Nice work to the whole team. &#127881;</p>
{link}"""
        text = (f"Move-in completed: {resident} at {community} "
                f"({done}/{total} items, target {target_date}).")
        return self._send(recipients, f"Move-in completed: {resident} ({community})",
                          self._shell("Move-In Completed", body), text)

    def _shell(self, heading, body_html):
        """Wrap body in the branded card (logo band + navy header)."""
        def esc(s):
            return html.escape(str(s or ''))
        logo_url = f"{self.app_base_url}/static/atlas-logo.png" if self.app_base_url else None
        logo_band = (
            f"<div style='background:#fff;border:1px solid #d9dfe8;border-bottom:none;"
            f"border-radius:10px 10px 0 0;padding:16px 24px;text-align:center'>"
            f"<img src='{esc(logo_url)}' alt='Atlas Senior Living' style='height:34px'></div>"
        ) if logo_url else ""
        navy_radius = "0" if logo_band else "10px 10px 0 0"
        return f"""\
<div style="font-family:Helvetica,Arial,sans-serif;max-width:600px;margin:0 auto;color:#0f1e36">
  {logo_band}
  <div style="background:#00285c;color:#fff;padding:18px 24px;border-radius:{navy_radius}">
    <div style="font-size:12px;letter-spacing:.5px;opacity:.85">COMMUNITIES STANDARDS</div>
    <div style="font-size:20px;font-weight:800;margin-top:4px">{esc(heading)}</div>
  </div>
  <div style="background:#fff;border:1px solid #d9dfe8;border-top:none;border-radius:0 0 10px 10px;padding:22px 24px">
    {body_html}
  </div>
  <div style="color:#9ca3af;font-size:11px;text-align:center;padding:14px">Atlas Senior Living — Communities Standards</div>
</div>"""

    def _send(self, recipients, subject, html_body, text_body):
        """Low-level send to a list of recipients. Returns (sent, detail)."""
        if not self.enabled:
            return (False, 'email not configured')
        to = []
        for addr in (recipients or []):
            a = (addr or '').strip()
            if _valid(a) and a.lower() not in [x.lower() for x in to]:
                to.append(a)
        if not to:
            return (False, 'no valid recipients')
        try:
            self._send_email(
                Source=self.mail_from,
                Destination={'ToAddresses': to},
                Message={
                    'Subject': {'Data': subject, 'Charset': 'UTF-8'},
                    'Body': {'Html': {'Data': html_body, 'Charset': 'UTF-8'},
                             'Text': {'Data': text_body, 'Charset': 'UTF-8'}},
                },
            )
            return (True, f'sent to {len(to)}')
        except Exception as e:
            logger.error(f'Email send failed: {e}')
            return (False, str(e))

    def send_welcome(self, to_email, display_name, username, password, role_label=None):
        """Welcome a newly-created user with their login details."""
        if not self.enabled or not _valid(to_email or ''):
            return (False, 'no recipient / disabled')
        login = self.app_base_url or ''
        subject = "Your Atlas Standards account"
        role_line = f"<tr><td style='color:#6b7280;padding:3px 12px 3px 0'>Role</td><td style='font-weight:600'>{html.escape(role_label)}</td></tr>" if role_label else ""
        body = f"""\
<p style="font-size:14px;margin:0 0 14px">Hi {html.escape(display_name)}, an account was created for you on Atlas Standards.</p>
<table style="font-size:14px;border-collapse:collapse;margin-bottom:8px">
  <tr><td style="color:#6b7280;padding:3px 12px 3px 0">Username</td><td style="font-weight:700">{html.escape(username)}</td></tr>
  <tr><td style="color:#6b7280;padding:3px 12px 3px 0">Temporary password</td><td style="font-weight:700;font-family:monospace">{html.escape(password)}</td></tr>
  {role_line}
</table>
<p style="font-size:13px;color:#6b7280;margin:6px 0 18px">Sign in with the temporary password above — you'll be asked to create your own password right away.</p>
{f'<a href="{html.escape(login)}" style="display:inline-block;background:#00285c;color:#fff;text-decoration:none;font-weight:700;padding:12px 22px;border-radius:8px;font-size:14px">Sign in</a>' if login else ''}"""
        text = (f"Hi {display_name}, an account was created for you on Atlas Standards.\n"
                f"Username: {username}\nTemporary password: {password}\n"
                + (f"Role: {role_label}\n" if role_label else "")
                + "Sign in with the temporary password above — you'll be asked to create your own password right away.\n"
                + (f"{login}\n" if login else ""))
        return self._send([to_email], subject, self._shell("Welcome", body), text)

    def send_password_reset(self, to_email, display_name, username, password):
        """Send a user the temporary password an administrator just set."""
        if not self.enabled or not _valid(to_email or ''):
            return (False, 'no recipient / disabled')
        login = self.app_base_url or ''
        subject = "Your Atlas Standards password was reset"
        body = f"""\
<p style="font-size:14px;margin:0 0 14px">Hi {html.escape(display_name)}, an administrator reset your Atlas Standards password.</p>
<table style="font-size:14px;border-collapse:collapse;margin-bottom:8px">
  <tr><td style="color:#6b7280;padding:3px 12px 3px 0">Username</td><td style="font-weight:700">{html.escape(username)}</td></tr>
  <tr><td style="color:#6b7280;padding:3px 12px 3px 0">Temporary password</td><td style="font-weight:700;font-family:monospace">{html.escape(password)}</td></tr>
</table>
<p style="font-size:13px;color:#6b7280;margin:6px 0 18px">Sign in with the temporary password above — you'll be asked to create your own password right away.</p>
{f'<a href="{html.escape(login)}" style="display:inline-block;background:#00285c;color:#fff;text-decoration:none;font-weight:700;padding:12px 22px;border-radius:8px;font-size:14px">Sign in</a>' if login else ''}
<p style="font-size:12px;color:#9ca3af;margin:18px 0 0">If you didn't expect this, contact your administrator.</p>"""
        text = (f"Hi {display_name}, an administrator reset your Atlas Standards password.\n"
                f"Username: {username}\nTemporary password: {password}\n"
                "Sign in with the temporary password above — you'll be asked to create your own password right away.\n"
                + (f"{login}\n" if login else ""))
        return self._send([to_email], subject, self._shell("Password reset", body), text)

    def send_new_user_alert(self, admin_emails, display_name, username, role_label, created_by):
        """Notify admins that a new account was created."""
        if not self.enabled:
            return (False, 'disabled')
        subject = f"New user created: {display_name}"
        body = f"""\
<p style="font-size:14px;margin:0 0 12px">A new account was created.</p>
<table style="font-size:14px;border-collapse:collapse">
  <tr><td style="color:#6b7280;padding:3px 12px 3px 0">Name</td><td style="font-weight:700">{html.escape(display_name)}</td></tr>
  <tr><td style="color:#6b7280;padding:3px 12px 3px 0">Username</td><td style="font-weight:600">{html.escape(username)}</td></tr>
  <tr><td style="color:#6b7280;padding:3px 12px 3px 0">Role</td><td style="font-weight:600">{html.escape(role_label or '')}</td></tr>
  <tr><td style="color:#6b7280;padding:3px 12px 3px 0">Created by</td><td style="font-weight:600">{html.escape(created_by or '')}</td></tr>
</table>"""
        text = (f"New account created.\nName: {display_name}\nUsername: {username}\n"
                f"Role: {role_label}\nCreated by: {created_by}\n")
        return self._send(admin_emails, subject, self._shell("New user", body), text)

    def send_password_reset_request(self, admin_emails, display_name, username, context, requested_at):
        """Notify admins that a user requested a password reset (admin-assisted flow)."""
        if not self.enabled:
            return (False, 'disabled')
        subject = f"Password reset requested: {display_name or username}"
        ctx_line = (f"<tr><td style='color:#6b7280;padding:3px 12px 3px 0'>Account</td>"
                    f"<td style='font-weight:600'>{html.escape(context)}</td></tr>") if context else ""
        body = f"""\
<p style="font-size:14px;margin:0 0 12px">A user asked to reset their password. Reset it from
<b>Settings &rarr; Reset a user's password</b>, then share the temporary password with them.</p>
<table style="font-size:14px;border-collapse:collapse">
  <tr><td style="color:#6b7280;padding:3px 12px 3px 0">Name</td><td style="font-weight:700">{html.escape(display_name or '')}</td></tr>
  <tr><td style="color:#6b7280;padding:3px 12px 3px 0">Username</td><td style="font-weight:700;font-family:monospace">{html.escape(username)}</td></tr>
  {ctx_line}
  <tr><td style="color:#6b7280;padding:3px 12px 3px 0">Requested</td><td style="font-weight:600">{html.escape(requested_at)}</td></tr>
</table>
<p style="font-size:12px;color:#9ca3af;margin:14px 0 0">If you don't recognize this request, you can ignore it — no change was made.</p>"""
        text = (f"Password reset requested.\nName: {display_name}\nUsername: {username}\n"
                + (f"Account: {context}\n" if context else "")
                + f"Requested: {requested_at}\n"
                "Reset it from Settings > Reset a user's password, then share the temporary password.\n")
        return self._send(admin_emails, subject, self._shell("Password reset requested", body), text)

    def send_directed_comments(self, recipients, route, submission, items):
        """Email the Clinical/Ops team the comments an inspector directed to them."""
        if not self.enabled:
            return (False, 'disabled')
        label = 'Clinical' if route == 'clinical' else 'Operations'
        community = submission.get('community', 'a community')
        inspector = submission.get('inspector_name') or submission.get('username') or 'Unknown'
        when = (submission.get('submitted_at') or '')[:10]

        def esc(s):
            return html.escape(str(s or ''))
        rows = ''.join(
            f"<li style='margin:8px 0'><strong>{esc(it.get('question_text','Item'))}</strong>"
            f"<div style='color:#475569;font-size:13px;margin-top:2px'>{esc(it.get('description',''))}</div></li>"
            for it in items
        )
        link = self.report_link(community)
        button = (f"<div style='margin-top:18px'><a href='{esc(link)}' style='display:inline-block;"
                  f"background:#00285c;color:#fff;text-decoration:none;font-weight:700;padding:11px 20px;"
                  f"border-radius:8px;font-size:14px'>View full report</a></div>") if link else ""
        body = (f"<p style='font-size:14px;margin:0 0 12px'>{esc(inspector)} directed the following "
                f"{label.lower()} item(s) to your team during an inspection of <strong>{esc(community)}</strong>"
                f"{(' on ' + esc(when)) if when else ''}.</p>"
                f"<ul style='margin:0;padding-left:18px;font-size:14px;color:#1f2937'>{rows}</ul>{button}")
        subject = f"{label} follow-up — {community} ({len(items)})"
        text_lines = [f"{inspector} directed {len(items)} {label.lower()} item(s) to your team for {community}:"]
        for it in items:
            text_lines.append(f"  - {it.get('question_text','Item')}: {it.get('description','')}")
        if link:
            text_lines += ["", f"View the full report: {link}"]
        return self._send(recipients, subject, self._shell(f"{label} follow-up", body), "\n".join(text_lines))

    def send_inspection_report(self, submission, recipients=None, survey_type_name=None, criteria_map=None):
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
            subject, html_body, text = self._build(submission, survey_type_name, criteria_map)
            self._send_email(
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
