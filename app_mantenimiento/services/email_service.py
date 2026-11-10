"""
Email Service (Amazon SES)
Sends a post-visit summary email when an inspection is submitted.

Env-driven, like the S3 backend:
  - MAIL_FROM         verified SES sender, e.g. "Atlas Excellence <noreply@atlasseniorliving.net>"
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
from datetime import datetime
from urllib.parse import quote

from services.conditions import NOT_CHECKED

logger = logging.getLogger(__name__)

_EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


def _valid(addr):
    return bool(addr) and bool(_EMAIL_RE.match(addr.strip()))


def _strip_tags(s):
    """Turn a small HTML fragment into readable plain text for the text part."""
    return html.unescape(re.sub(r'<[^>]+>', '', s or '')).strip()


def sent_on_behalf_line(submission):
    """'Sent by Excellence Administrator on Nov 7 on behalf of Greg Crutcher',
    or '' for a visit its inspector sent. The administrator is never named
    here — Gabriel's choice; who did it is in the activity log."""
    info = (submission or {}).get('sent_on_behalf') or {}
    if not info:
        return ''
    try:
        when = datetime.fromisoformat(info.get('at') or '').strftime('%b %-d')
    except (ValueError, TypeError):
        when = ''
    who = submission.get('inspector_name') or submission.get('username') or 'the inspector'
    return (f"Sent by Excellence Administrator{' on ' + when if when else ''} "
            f"on behalf of {who}")


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

    @staticmethod
    def _not_checked(submission):
        return [r for r in (submission.get('responses') or []) if r.get('condition') == NOT_CHECKED]

    def report_link(self, community):
        if not self.app_base_url:
            return None
        return f"{self.app_base_url}/?community={quote(community or '')}"

    # Pieces of the email design, shared by every message (Nov 2026): a mono
    # eyebrow for section titles, a card with a rail in the answer's colour
    # (the same as the app's), and a small square tag.
    MONO = "'SFMono-Regular',Menlo,Consolas,'Courier New',monospace"
    RAIL = {'fail': '#ea366e', 'not_checked': '#5b6b85', 'action': '#ffa500', 'pass': '#75fb87'}
    PRIORITY_TAG = {'high': ('#b42318', '#fdecea'), 'medium': ('#8a5300', '#fff3dc'), 'low': ('#36454f', '#f1f3f5')}

    @classmethod
    def _eyebrow(cls, text, count=None):
        n = f" &middot; {count}" if count is not None else ""
        return (f"<div style=\"font-family:{cls.MONO};font-size:11px;letter-spacing:.14em;"
                f"text-transform:uppercase;color:#00709a;margin:24px 0 8px\">{html.escape(text)}{n}</div>")

    @staticmethod
    def _card(inner, rail):
        return (f"<div style='border:1px solid #e1e5ea;border-left:3px solid {rail};border-radius:6px;"
                f"padding:12px 14px;margin:8px 0;background:#ffffff'>{inner}</div>")

    @classmethod
    def _priority_tag(cls, priority):
        p = (priority or 'medium').lower()
        fg, bg = cls.PRIORITY_TAG.get(p, cls.PRIORITY_TAG['medium'])
        return (f"<span style=\"font-family:{cls.MONO};font-size:10.5px;letter-spacing:.08em;"
                f"text-transform:uppercase;color:{fg};background:{bg};padding:2px 7px;border-radius:4px\">"
                f"{html.escape(p)}</span>")

    @staticmethod
    def _help_for(response, help_map):
        """A failed standard's help material, matched like its criteria."""
        if not help_map:
            return None
        qid = response.get('question_id')
        if qid and help_map.get(qid):
            return help_map[qid]
        return help_map.get('t:' + (response.get('question_text') or '').strip().lower())

    def _help_url(self, info):
        """Where an email reader gets it: the app's own download, which asks
        them to sign in. Nothing without a base address to build it on."""
        if not self.app_base_url or not info.get('download'):
            return None
        return f"{self.app_base_url}{info['download']}"

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

        subject = f"Visit — {community}: {score_txt} ({passed}/{total} pass)"

        # Plain text
        lines = [
            f"Visit submitted for {community}",
            f"Inspector: {inspector}",
            f"Date: {when}",
        ]
        if survey_type_name:
            lines.append(f"Survey type: {survey_type_name}")
        not_checked = self._not_checked(submission)
        lines += [
            f"Overall score: {score_txt}",
            f"Passed: {passed} / {total}    Failed: {failed}"
            + (f"    Not checked: {len(not_checked)} (not scored)" if not_checked else ""),
        ]
        behalf = sent_on_behalf_line(submission)
        if behalf:
            lines += ["", behalf]
        note_for_text = (submission.get('notes') or '').strip()
        if note_for_text:
            lines += ["", f"Note from {inspector}:", f"  {note_for_text}"]
        if fails:
            lines.append("")
            lines.append("Failed items:")
            for r in fails:
                q = r.get('question_text', 'Item')
                note = r.get('description', '')
                lines.append(f"  - {q}" + (f": {note}" if note else ""))
                for c in self._criteria_for(r, criteria_map):
                    lines.append(f"      • {c}")
        if not_checked:
            lines.append("")
            lines.append("Not checked (left out of the score):")
            for r in not_checked:
                reason = r.get('description', '')
                lines.append(f"  - {r.get('question_text', 'Item')}" + (f": {reason}" if reason else ""))
        if link:
            lines += ["", f"View the full report: {link}"]
        text = "\n".join(lines)

        # HTML
        def esc(s):
            return html.escape(str(s or ''))

        score_color = '#0b6b49' if (score is not None and score >= 75) else (
            '#9a5b00' if (score is not None and score >= 50) else '#b42318')
        def fail_li(r):
            crit = self._criteria_for(r, criteria_map)
            crit_html = ''
            if crit:
                items = ''.join(f"<li style='margin:2px 0'>{esc(c)}</li>" for c in crit)
                crit_html = (f"<div style='font-size:12px;color:#5a6872;margin:4px 0 2px'>Standard — to pass, must include:</div>"
                             f"<ul style='margin:0 0 6px;padding-left:16px;color:#475569;font-size:12px'>{items}</ul>")
            return self._card(
                f"<div style='font-weight:600;font-size:14.5px;color:#1b2730'>{esc(r.get('question_text','Item'))}</div>"
                + (f"<div style='font-size:13.5px;color:#36454f;margin-top:3px'>{esc(r.get('description',''))}</div>"
                   if r.get('description') else "")
                + crit_html, self.RAIL['fail'])
        fail_rows = ''.join(fail_li(r) for r in fails)
        fail_block = (
            self._eyebrow('Failed', failed) + fail_rows
        ) if fails else ("<p style='color:#0b6b49;font-size:14px;margin:14px 0'>"
                         + ("Everything checked passed." if not_checked else "All items passed.") + "</p>")
        # What could not be checked, and why. Out of the score, so it is listed
        # where leadership will see it: an empty Fail list next to five of
        # these is not the same visit as an empty Fail list on its own.
        not_checked_block = (
            self._eyebrow('Not checked', len(not_checked))
            + ''.join(self._card(
                f"<div style='font-weight:600;font-size:14px;color:#1b2730'>{esc(r.get('question_text', 'Item'))}</div>"
                + (f"<div style='font-size:13px;color:#36454f;margin-top:3px'>{esc(r.get('description', ''))}</div>"
                   if r.get('description') else ""), self.RAIL['not_checked'])
                for r in not_checked)
            + "<p style='color:#5a6872;font-size:12px;margin:6px 0 0'>"
              "Left out of the score. Worth a look next time.</p>"
        ) if not_checked else ""

        # Ad-hoc action items raised during the visit (not standards, no score
        # impact) — surfaced so the right team sees them without digging.
        manual = [i for i in (submission.get('action_items') or []) if not i.get('resolved')]
        if manual:
            rows = ''.join(
                self._card(
                    f"{self._priority_tag(i.get('priority'))} "
                    f"<span style='font-size:14px;color:#1b2730'>{esc(i.get('text'))}</span>"
                    # assigned_to holds the department's id; the resolver puts
                    # its name here. Falling back to the id keeps an older record
                    # readable rather than blank.
                    + (f"<div style='color:#5a6872;font-size:13px;margin-top:4px'>For: "
                       f"{esc(i.get('assigned_to_name') or i.get('assigned_to'))}</div>"
                       if i.get('assigned_to') else ""), self.RAIL['action'])
                for i in manual)
            action_block = (
                self._eyebrow('Action items raised on this visit', len(manual)) + rows
                + f"<p style='color:#5a6872;font-size:12px;margin:6px 0 0'>"
                f"These are follow-up tasks noted by the inspector — they don't affect the score.</p>"
            )
        else:
            action_block = ""

        button = (
            f"<a href='{esc(link)}' style='display:inline-block;background:#003366;color:#fff;"
            f"text-decoration:none;font-weight:700;padding:12px 22px;border-radius:8px;"
            f"font-size:14px'>View full report</a>"
        ) if link else ""

        # The regional's own note about the visit. Leadership reads this report
        # to judge a community; the sentence explaining why it scored what it
        # scored belongs above the numbers, not buried under them.
        note = (submission.get('notes') or '').strip()
        note_block = (f"<div style='margin:14px 0 4px;padding:13px 15px;background:#f1f5fa;"
                      f"border-left:3px solid #003366;border-radius:0 8px 8px 0;"
                      f"font-size:14px;color:#1b2730;line-height:1.55'>"
                      f"<div style=\"font-family:{self.MONO};font-size:11px;color:#00709a;"
                      f"text-transform:uppercase;letter-spacing:.14em;margin-bottom:5px\">"
                      f"Note from {esc(inspector)}</div>{esc(note)}</div>") if note else ""
        # Sent from an unfinished draft by an administrator: said up front, so
        # nobody reads it as the inspector's finished, reviewed visit.
        if behalf:
            note_block = (f"<div style='margin:14px 0 4px;padding:11px 14px;background:#fffbeb;"
                          f"border:1px solid #fde68a;border-radius:8px;font-size:13.5px;color:#7c5e10'>"
                          f"{esc(behalf)}</div>") + note_block

        survey_row = (
            f"<tr><td style='color:#5a6872;padding:3px 12px 3px 0'>Survey type</td>"
            f"<td style='font-weight:600'>{esc(survey_type_name)}</td></tr>"
        ) if survey_type_name else ""

        body = f"""\
    <div style="font-family:'SFMono-Regular',Menlo,Consolas,'Courier New',monospace;font-size:36px;font-weight:600;letter-spacing:-.02em;color:{score_color}">{esc(score_txt)}</div>
    <div style="color:#5a6872;font-size:13px;margin-bottom:16px">Overall score &middot; {passed}/{total} passed{f" &middot; {len(not_checked)} not checked" if not_checked else ""}</div>
    <table style="font-size:14px;border-collapse:collapse;margin-bottom:6px">
      <tr><td style="color:#5a6872;padding:3px 14px 3px 0">Inspector</td><td style="font-weight:600">{esc(inspector)}</td></tr>
      <tr><td style="color:#5a6872;padding:3px 14px 3px 0">Date</td><td style="font-weight:600">{esc(when)}</td></tr>
      {survey_row}
    </table>
    {note_block}
    {fail_block}
    {not_checked_block}
    {action_block}
    <div style="margin-top:20px">{button}</div>"""
        # The same frame as every other email; the community is the heading.
        html_body = self._shell(community, body, eyebrow='Visit report')

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
                f"style='display:inline-block;background:#003366;color:#fff;text-decoration:none;"
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
                f"style='display:inline-block;background:#003366;color:#fff;text-decoration:none;"
                f"font-weight:700;padding:11px 20px;border-radius:8px;font-size:14px'>Open Move-Ins</a></p>"
                if self.app_base_url else "")
        body = f"""\
<p style="font-size:14px;margin:0 0 12px">The move-in checklist for <b>{esc(resident)}</b> at
<b>{esc(community)}</b> has been <b style="color:#0b6b49">completed</b>
({esc(done)}/{esc(total)} items, target date {esc(target_date) or 'n/a'}).</p>
<p style="font-size:14px;margin:0 0 4px">Nice work to the whole team. &#127881;</p>
{link}"""
        text = (f"Move-in completed: {resident} at {community} "
                f"({done}/{total} items, target {target_date}).")
        return self._send(recipients, f"Move-in completed: {resident} ({community})",
                          self._shell("Move-In Completed", body), text)

    def _shell(self, heading, body_html, eyebrow='Atlas Excellence'):
        """Wrap a body in the one frame every email uses.

        Precision design (Nov 2026), within what email clients render: a grey
        page, a white card with a hairline and 8px corners, the wordmark, a
        navy band with the engineering grid (Gabriel's ask; Outlook, which
        draws no background patterns, shows it plain navy) and a mono eyebrow,
        and an electric rule under it. Web fonts
        and the app's grid do not survive Outlook, so Roboto is asked for by
        name (Gmail and Android have it) with Helvetica and Arial behind it."""
        def esc(s):
            return html.escape(str(s or ''))
        # The product's own wordmark, not the parent company's. Served from
        # /static, which is public — an email client fetches it without a
        # session, so it has to be a URL nobody needs to sign in for.
        logo_url = f"{self.app_base_url}/static/arlas-excellence-logo.png" if self.app_base_url else None
        logo_band = (
            f"<div style='background:#ffffff;padding:18px 28px 14px'>"
            f"<img src='{esc(logo_url)}' alt='Atlas Excellence' style='height:36px;display:block'></div>"
        ) if logo_url else ""
        sans = "Roboto,'Helvetica Neue',Helvetica,Arial,sans-serif"
        mono = "'SFMono-Regular',Menlo,Consolas,'Courier New',monospace"
        return f"""\
<div style="background:#f4f6f8;padding:24px 12px">
<div style="font-family:{sans};max-width:600px;margin:0 auto;color:#1b2730;background:#ffffff;border:1px solid #e1e5ea;border-radius:8px;overflow:hidden">
  {logo_band}
  <div style="background-color:#003366;background-image:linear-gradient(rgba(255,255,255,.08) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.08) 1px,transparent 1px);background-size:20px 20px;color:#ffffff;padding:18px 28px 16px;border-bottom:3px solid #00bfff">
    <div style="font-family:{mono};font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:#8fd8ff">{esc(eyebrow)}</div>
    <div style="font-size:21px;font-weight:700;letter-spacing:-.01em;margin-top:5px;color:#ffffff">{esc(heading)}</div>
  </div>
  <div style="padding:24px 28px 26px;font-size:14px;line-height:1.55">
    {body_html}
  </div>
</div>
<div style="font-family:{sans};color:#5a6872;font-size:11.5px;text-align:center;padding:14px">Atlas Senior Living — Atlas Excellence</div>
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
            resp = self._send_email(
                Source=self.mail_from,
                Destination={'ToAddresses': to},
                Message={
                    'Subject': {'Data': subject, 'Charset': 'UTF-8'},
                    'Body': {'Html': {'Data': html_body, 'Charset': 'UTF-8'},
                             'Text': {'Data': text_body, 'Charset': 'UTF-8'}},
                },
            )
            # SES accepting a message only means it left our side. When it never
            # reaches the inbox the recipient's mail server is the next place to
            # look, and the MessageId is what lets an admin trace it there — so
            # always record it.
            message_id = (resp or {}).get('MessageId', '')
            logger.info('Email accepted by SES | id=%s | from=%s | to=%s | subject=%s',
                        message_id, self.mail_from, ', '.join(to), subject)
            return (True, f'sent to {len(to)} (SES id {message_id})' if message_id
                          else f'sent to {len(to)}')
        except Exception as e:
            logger.error('Email send failed | to=%s | subject=%s | %s',
                         ', '.join(to), subject, e)
            return (False, str(e))

    def _atlerts_tip(self):
        """How to get in through Atlerts, for the welcome email. (html, text)

        Most people already have Atlerts, and its Excellence shortcut signs
        them in with no password. Nobody was told: the welcome email only
        explained the password, so people typed one they then forgot. The
        picture is a still, not a GIF — Outlook on Windows shows only the
        first frame of one — and it is cropped to the shortcuts row, with no
        name on it."""
        esc = html.escape
        img_url = f"{self.app_base_url}/static/email-atlerts-shortcut.jpg" if self.app_base_url else None
        picture = (
            f"<img src='{esc(img_url)}' width='516' alt='Atlerts home screen: the Excellence "
            f"shortcut under Apps &amp; Shortcuts' style='display:block;width:100%;max-width:516px;"
            f"height:auto;border-radius:10px;margin:0 0 14px'>"
        ) if img_url else ""
        body = f"""\
<div style="margin-top:24px;padding-top:20px;border-top:1px solid #e1e5ea">
  <p style="font-size:16px;font-weight:700;color:#1b2730;margin:0 0 6px">The easiest way in: Atlerts</p>
  <p style="font-size:14px;color:#36454f;margin:0 0 14px">If you have Atlerts on your phone, you don't need a password. Open Atlerts and tap <b style="color:#1b2730">Excellence</b> under Apps &amp; Shortcuts — you're signed in straight away.</p>
  {picture}
  <table style="font-size:14px;border-collapse:collapse;margin:0 0 14px;color:#1b2730">
    <tr><td style="vertical-align:top;padding:2px 10px 2px 0;color:#5a6872">1</td><td>Open <b>Atlerts</b>.</td></tr>
    <tr><td style="vertical-align:top;padding:2px 10px 2px 0;color:#5a6872">2</td><td>Under <b>Apps &amp; Shortcuts</b>, tap <b>Excellence</b> (swipe if you don't see it).</td></tr>
    <tr><td style="vertical-align:top;padding:2px 10px 2px 0;color:#5a6872">3</td><td>You're in — no password to remember.</td></tr>
  </table>
  <div style="background:#f1f5fa;border:1px solid #d3dde8;border-radius:10px;padding:12px 14px;font-size:13px;line-height:1.55;color:#1b2730">
    <b>Use a different email in Atlerts?</b><br>
    If your Atlerts account uses another email (a personal Gmail, for example), the first time you'll land on the sign-in page. Sign in once with the username and password above, then tap <b>Link</b> when asked. After that, Atlerts takes you straight in.
  </div>
</div>"""
        text = (
            "\nThe easiest way in: Atlerts\n"
            "If you have Atlerts on your phone, you don't need a password: open Atlerts and "
            "tap Excellence under Apps & Shortcuts.\n"
            "If your Atlerts account uses another email (a personal Gmail, for example), the "
            "first time you'll land on the sign-in page. Sign in once with the username and "
            "password above, then tap Link when asked. After that, Atlerts takes you straight in.\n"
        )
        return body, text

    def send_welcome(self, to_email, display_name, username, password, role_label=None):
        """Welcome a newly-created user with their login details."""
        if not self.enabled or not _valid(to_email or ''):
            return (False, 'no recipient / disabled')
        login = self.app_base_url or ''
        subject = "Your Atlas Excellence account"
        role_line = f"<tr><td style='color:#5a6872;padding:3px 12px 3px 0'>Role</td><td style='font-weight:600'>{html.escape(role_label)}</td></tr>" if role_label else ""
        body = f"""\
<p style="font-size:14px;margin:0 0 14px">Hi {html.escape(display_name)}, an account was created for you on Atlas Excellence.</p>
<table style="font-size:14px;border-collapse:collapse;margin-bottom:8px">
  <tr><td style="color:#5a6872;padding:3px 12px 3px 0">Username</td><td style="font-weight:700">{html.escape(username)}</td></tr>
  <tr><td style="color:#5a6872;padding:3px 12px 3px 0">Temporary password</td><td style="font-weight:700;font-family:monospace">{html.escape(password)}</td></tr>
  {role_line}
</table>
<p style="font-size:13px;color:#5a6872;margin:6px 0 18px">Sign in with the temporary password above — you'll be asked to create your own password right away.</p>
{f'<a href="{html.escape(login)}" style="display:inline-block;background:#003366;color:#fff;text-decoration:none;font-weight:600;padding:12px 22px;border-radius:8px;font-size:14px">Sign in</a>' if login else ''}"""
        tip_html, tip_text = self._atlerts_tip()
        body += tip_html
        text = (f"Hi {display_name}, an account was created for you on Atlas Excellence.\n"
                f"Username: {username}\nTemporary password: {password}\n"
                + (f"Role: {role_label}\n" if role_label else "")
                + "Sign in with the temporary password above — you'll be asked to create your own password right away.\n"
                + (f"{login}\n" if login else "")
                + tip_text)
        return self._send([to_email], subject, self._shell("Welcome", body), text)

    def send_password_reset(self, to_email, display_name, username, password):
        """Send a user the temporary password an administrator just set."""
        if not self.enabled or not _valid(to_email or ''):
            return (False, 'no recipient / disabled')
        login = self.app_base_url or ''
        subject = "Your Atlas Excellence password was reset"
        body = f"""\
<p style="font-size:14px;margin:0 0 14px">Hi {html.escape(display_name)}, an administrator reset your Atlas Excellence password.</p>
<table style="font-size:14px;border-collapse:collapse;margin-bottom:8px">
  <tr><td style="color:#5a6872;padding:3px 12px 3px 0">Username</td><td style="font-weight:700">{html.escape(username)}</td></tr>
  <tr><td style="color:#5a6872;padding:3px 12px 3px 0">Temporary password</td><td style="font-weight:700;font-family:monospace">{html.escape(password)}</td></tr>
</table>
<p style="font-size:13px;color:#5a6872;margin:6px 0 18px">Sign in with the temporary password above — you'll be asked to create your own password right away.</p>
{f'<a href="{html.escape(login)}" style="display:inline-block;background:#003366;color:#fff;text-decoration:none;font-weight:600;padding:12px 22px;border-radius:8px;font-size:14px">Sign in</a>' if login else ''}
<p style="font-size:13px;color:#36454f;margin:18px 0 0"><b>Tip:</b> with Atlerts on your phone you can skip passwords entirely — tap <b>Excellence</b> under Apps &amp; Shortcuts.</p>
<p style="font-size:12px;color:#5a6872;margin:12px 0 0">If you didn't expect this, contact your administrator.</p>"""
        text = (f"Hi {display_name}, an administrator reset your Atlas Excellence password.\n"
                f"Username: {username}\nTemporary password: {password}\n"
                "Sign in with the temporary password above — you'll be asked to create your own password right away.\n"
                + (f"{login}\n" if login else "")
                + "Tip: with Atlerts on your phone you can skip passwords entirely — tap Excellence under Apps & Shortcuts.\n")
        return self._send([to_email], subject, self._shell("Password reset", body), text)

    def send_draft_reminder(self, to_email, display_name, community, survey_name,
                            answered, total, quiet_days, days_left, link=None):
        """Tell somebody they have an unfinished visit, before it expires.

        Unfinished visits are deleted, photos and all, after two weeks without a
        save — until now without a word to anybody. Greg Crutcher's Greystone
        visit sat for four days before anyone looked for it."""
        if not self.enabled or not _valid(to_email or ''):
            return (False, 'no recipient / disabled')
        esc = html.escape
        progress = f"{answered} of {total} answered" if total else f"{answered} answered"
        when = 'today' if quiet_days == 0 else f"{quiet_days} day{'s' if quiet_days != 1 else ''} ago"
        left = (f"It will be deleted in {days_left} day{'s' if days_left != 1 else ''} "
                "if it isn't finished or saved again.") if days_left else "It will be deleted soon."
        subject = f"Unfinished visit: {community}"
        body = f"""\
<p style="font-size:14px;margin:0 0 12px">Hi {esc(display_name)}, you have an unfinished visit in Atlas Excellence.</p>
<table style="font-size:14px;border-collapse:collapse;margin-bottom:10px">
  <tr><td style="color:#5a6872;padding:3px 12px 3px 0">Community</td><td style="font-weight:700">{esc(community)}</td></tr>
  {f'<tr><td style="color:#5a6872;padding:3px 12px 3px 0">Visit</td><td>{esc(survey_name)}</td></tr>' if survey_name else ''}
  <tr><td style="color:#5a6872;padding:3px 12px 3px 0">Progress</td><td>{esc(progress)}</td></tr>
  <tr><td style="color:#5a6872;padding:3px 12px 3px 0">Last saved</td><td>{esc(when)}</td></tr>
</table>
<p style="font-size:14px;color:#9a5b00;margin:0 0 16px">{esc(left)}</p>
{f'<a href="{esc(link)}" style="display:inline-block;background:#003366;color:#fff;text-decoration:none;font-weight:600;padding:12px 22px;border-radius:8px;font-size:14px">Finish this visit</a>' if link else ''}
<p style="font-size:13px;color:#5a6872;margin:16px 0 0">It is saved to your account, so you can finish it on any device.</p>"""
        text = (f"Hi {display_name}, you have an unfinished visit at {community}"
                + (f" ({survey_name})" if survey_name else "")
                + f": {progress}, last saved {when}.\n{left}\n"
                + (f"{link}\n" if link else "")
                + "It is saved to your account, so you can finish it on any device.\n")
        return self._send([to_email], subject, self._shell("Unfinished visit", body), text)

    def send_sent_on_behalf(self, to_email, display_name, community, survey_name, sent_on):
        """Tell somebody their unfinished visit was sent for them."""
        if not self.enabled or not _valid(to_email or ''):
            return (False, 'no recipient / disabled')
        esc = html.escape
        subject = f"Your visit to {community} was sent"
        body = f"""\
<p style="font-size:14px;margin:0 0 12px">Hi {esc(display_name)}, your unfinished visit to <b>{esc(community)}</b>{f' ({esc(survey_name)})' if survey_name else ''} was sent on your behalf by the Excellence Administrator on {esc(sent_on)}.</p>
<p style="font-size:14px;color:#36454f;margin:0">It was sent as it was saved, marked as partial where standards were left unanswered. If something needs correcting, reply to this email.</p>"""
        text = (f"Hi {display_name}, your unfinished visit to {community}"
                + (f" ({survey_name})" if survey_name else "")
                + f" was sent on your behalf by the Excellence Administrator on {sent_on}.\n"
                "It was sent as it was saved, marked as partial where standards were left unanswered.\n")
        return self._send([to_email], subject, self._shell("Visit sent", body), text)

    def send_new_user_alert(self, admin_emails, display_name, username, role_label, created_by):
        """Notify admins that a new account was created."""
        if not self.enabled:
            return (False, 'disabled')
        subject = f"New user created: {display_name}"
        body = f"""\
<p style="font-size:14px;margin:0 0 12px">A new account was created.</p>
<table style="font-size:14px;border-collapse:collapse">
  <tr><td style="color:#5a6872;padding:3px 12px 3px 0">Name</td><td style="font-weight:700">{html.escape(display_name)}</td></tr>
  <tr><td style="color:#5a6872;padding:3px 12px 3px 0">Username</td><td style="font-weight:600">{html.escape(username)}</td></tr>
  <tr><td style="color:#5a6872;padding:3px 12px 3px 0">Role</td><td style="font-weight:600">{html.escape(role_label or '')}</td></tr>
  <tr><td style="color:#5a6872;padding:3px 12px 3px 0">Created by</td><td style="font-weight:600">{html.escape(created_by or '')}</td></tr>
</table>"""
        text = (f"New account created.\nName: {display_name}\nUsername: {username}\n"
                f"Role: {role_label}\nCreated by: {created_by}\n")
        return self._send(admin_emails, subject, self._shell("New user", body), text)

    def send_password_reset_request(self, admin_emails, display_name, username, context, requested_at):
        """Notify admins that a user requested a password reset (admin-assisted flow)."""
        if not self.enabled:
            return (False, 'disabled')
        subject = f"Password reset requested: {display_name or username}"
        ctx_line = (f"<tr><td style='color:#5a6872;padding:3px 12px 3px 0'>Account</td>"
                    f"<td style='font-weight:600'>{html.escape(context)}</td></tr>") if context else ""
        body = f"""\
<p style="font-size:14px;margin:0 0 12px">A user asked to reset their password. Reset it from
<b>Settings &rarr; Reset a user's password</b>, then share the temporary password with them.</p>
<table style="font-size:14px;border-collapse:collapse">
  <tr><td style="color:#5a6872;padding:3px 12px 3px 0">Name</td><td style="font-weight:700">{html.escape(display_name or '')}</td></tr>
  <tr><td style="color:#5a6872;padding:3px 12px 3px 0">Username</td><td style="font-weight:700;font-family:monospace">{html.escape(username)}</td></tr>
  {ctx_line}
  <tr><td style="color:#5a6872;padding:3px 12px 3px 0">Requested</td><td style="font-weight:600">{html.escape(requested_at)}</td></tr>
</table>
<p style="font-size:12px;color:#5a6872;margin:14px 0 0">If you don't recognize this request, you can ignore it — no change was made.</p>"""
        text = (f"Password reset requested.\nName: {display_name}\nUsername: {username}\n"
                + (f"Account: {context}\n" if context else "")
                + f"Requested: {requested_at}\n"
                "Reset it from Settings > Reset a user's password, then share the temporary password.\n")
        return self._send(admin_emails, subject, self._shell("Password reset requested", body), text)

    def send_password_changed_alert(self, admin_emails, display_name, username,
                                    changed_by='', when='', ip=''):
        """Security notice: an account's password changed.

        Sent whether the user changed it themselves or an admin reset it, so
        the administrator always has a trail of who touched which account."""
        if not self.enabled:
            return (False, 'disabled')
        who = display_name or username
        self_service = (not changed_by) or (changed_by == username)
        how = ("The user changed it themselves."
               if self_service else f"Reset by {changed_by}.")
        subject = f"Password changed: {who}"
        rows = [("Name", display_name or ''), ("Username", username), ("Changed", when or '')]
        if not self_service:
            rows.append(("Reset by", changed_by))
        if ip:
            rows.append(("From IP", ip))
        table = "".join(
            f"<tr><td style=\"color:#5a6872;padding:3px 12px 3px 0\">{html.escape(k)}</td>"
            f"<td style=\"font-weight:600\">{html.escape(str(v))}</td></tr>"
            for k, v in rows if v)
        body = f"""\
<p style="font-size:14px;margin:0 0 12px">The password for an account was changed. {html.escape(how)}</p>
<table style="font-size:14px;border-collapse:collapse">{table}</table>
<p style="font-size:12px;color:#5a6872;margin:14px 0 0">If this wasn't expected, reset the
account from <b>People</b> and ask the user to sign in again.</p>"""
        text = (f"Password changed.\n{how}\n"
                + "".join(f"{k}: {v}\n" for k, v in rows if v))
        return self._send(admin_emails, subject,
                          self._shell("Password changed", body), text)

    def send_activity_digest(self, admin_emails, digest):
        """Daily rundown for the administrator: who signed in, what was done,
        and anything touching passwords or accounts."""
        if not self.enabled:
            return (False, 'disabled')

        def section(title, rows, empty=None):
            """One block of the digest. Skipped entirely when empty unless a
            fallback line is given (used for the quiet-day message)."""
            if not rows:
                if not empty:
                    return "", ""
                return (f"<p style='font-size:13px;color:#5a6872;margin:0 0 14px'>{html.escape(empty)}</p>",
                        f"{empty}\n")
            lis = "".join(
                f"<li style='margin:3px 0'>{r}</li>" for r in rows)
            h = (f"<p style='font-size:12px;font-weight:700;text-transform:uppercase;"
                 f"letter-spacing:.5px;color:#5a6872;margin:16px 0 6px'>{html.escape(title)}</p>"
                 f"<ul style='font-size:14px;margin:0;padding-left:18px'>{lis}</ul>")
            t = f"\n{title.upper()}\n" + "".join(f"  - {_strip_tags(r)}\n" for r in rows)
            return h, t

        signins = [f"<b>{html.escape(p['name'])}</b>"
                   + (f" <span style='color:#5a6872'>({p['count']}x)</span>" if p['count'] > 1 else "")
                   for p in digest['signed_in']]
        visits = [f"<b>{html.escape(v['name'])}</b> — {html.escape(v['detail'] or v['community'])}"
                  for v in digest['visits']]
        addressed = [f"<b>{html.escape(a['name'])}</b> — {html.escape(a['detail'])}"
                     for a in digest['addressed']]
        comments = [f"<b>{html.escape(c['name'])}</b> — {html.escape(c['detail'])}"
                    for c in digest.get('comments', [])]
        # Named separately because it's the one line worth acting on: somebody
        # said they fixed something and nobody has confirmed it.
        awaiting = [html.escape(c) for c in digest.get('awaiting_review', [])]
        security = [f"<b>{html.escape(s['name'])}</b> — {html.escape(s['detail'])}"
                    for s in digest['security']]
        accounts = [f"<b>{html.escape(a['name'])}</b> — {html.escape(a['detail'])}"
                    for a in digest['accounts']]
        never = [html.escape(n) for n in digest['never_signed_in']]
        # Leads the email when present: a failure nobody hears about is the
        # one that quietly costs someone their work.
        errs = [f"<b>{e['count']}×</b> {html.escape(e['what'])}"
                for e in digest.get('errors', [])]
        # A standing condition rather than today's news, so it says how long.
        overdue = [f"<b>{html.escape(o['resident'])}</b> at {html.escape(o['community'])} — "
                   f"{o['days']} day{'s' if o['days'] != 1 else ''} past the move-in date, "
                   f"{o['pending']} required item{'s' if o['pending'] != 1 else ''} still open"
                   for o in digest.get('overdue_moveins', [])]

        # Only reported when something is wrong. A green tick every morning
        # becomes furniture within a week and stops being read — which is how
        # a backup can fail for a fortnight in plain sight.
        backup = digest.get('backup') or {}
        backup_warning = []
        if backup.get('stale'):
            if backup.get('known'):
                days = int((backup.get('age_hours') or 0) // 24)
                backup_warning = [
                    f"<b>No backup for {days} day{'s' if days != 1 else ''}.</b> "
                    f"The last one succeeded on {html.escape(str(backup.get('when', ''))[:16].replace('T', ' '))}."]
            else:
                backup_warning = [
                    "<b>No successful backup on record.</b> "
                    "The nightly job has not reported success — check that it can run."]

        quiet = not any([signins, visits, addressed, comments, security, accounts,
                         overdue, errs, backup_warning])
        blocks = [
            section("Signed in", signins,
                    empty="No activity in the last 24 hours." if quiet else None),
            section("Visits submitted", visits),
            section("Backups", backup_warning),
            section("Errors users hit", errs),
            section("Move-ins past due with required items open", overdue),
            section("Reported by communities", comments),
            section("Waiting on a regional to confirm", awaiting),
            section("Marked as addressed", addressed),
            section("Passwords", security),
            section("Account changes", accounts),
            section("Never signed in", never) if never else ("", ""),
        ]
        body_html = "".join(b[0] for b in blocks)
        body_text = "".join(b[1] for b in blocks)

        subject = (f"Atlas Excellence — daily activity"
                   + ("" if quiet else f" ({digest['total_events']} events)"))
        header = (f"<p style='font-size:13px;color:#5a6872;margin:0 0 4px'>"
                  f"Since {html.escape(digest['since'])}</p>")
        return self._send(admin_emails, subject,
                          self._shell("Daily activity", header + body_html),
                          f"Atlas Excellence — daily activity since {digest['since']}\n" + body_text)

    def send_raised_item(self, recipients, item):
        """A community has raised something for its regional to look at.

        Not a finding — nobody marked this Fail and no score moved. The wording
        keeps that clear, because a regional scanning their inbox should be
        able to tell a request from a problem without opening it."""
        if not self.enabled:
            return (False, 'disabled')

        def esc(s):
            return html.escape(str(s or ''))

        community = item.get('community', '')
        who = item.get('raised_by_name') or item.get('raised_by') or 'The community'
        text = item.get('text', '')
        priority = (item.get('priority') or 'medium').lower()
        colour = {'high': '#b42318', 'medium': '#9a5b00', 'low': '#475569'}.get(priority, '#9a5b00')

        link = self.report_link(community)
        button = (f"<div style='margin-top:20px'><a href='{esc(link)}' "
                  f"style='display:inline-block;background:#003366;color:#fff;text-decoration:none;"
                  f"font-weight:600;padding:12px 22px;border-radius:8px;font-size:14px'>"
                  f"Open in Atlas Excellence</a></div>") if link else ""

        subject = f"Raised by {community}: {text[:60]}" + ('…' if len(text) > 60 else '')
        body = (f"<p style='font-size:14px;margin:0 0 14px'><b>{esc(who)}</b> raised this at "
                f"<b>{esc(community)}</b>.</p>"
                f"<div style='padding:14px 16px;background:#f7f9fc;border-left:3px solid {colour};"
                f"border-radius:0 8px 8px 0'>"
                f"<div style='font-size:11.5px;font-weight:800;color:{colour};"
                f"text-transform:uppercase;letter-spacing:.5px;margin-bottom:5px'>"
                f"{esc(priority)} priority"
                # The category travels with the item. A regional triaging their
                # inbox can tell a CapEx request from a Clinical one without
                # opening anything.
                + (f" &middot; {esc(item.get('category_name'))}"
                   if item.get('category_name') else "")
                + "</div>"
                f"<div style='font-size:15px;color:#1b2730;line-height:1.55'>{esc(text)}</div></div>"
                f"<p style='font-size:13px;color:#5a6872;margin:16px 0 0;line-height:1.55'>"
                f"This came from the community rather than from a visit, so nothing was marked "
                f"Fail and no score has changed. It is here for you to look at.</p>"
                f"{button}")
        text_body = (f"{who} raised this at {community}.\n\n"
                     f"[{priority.upper()}"
                     + (f" | {item.get('category_name')}" if item.get('category_name') else "")
                     + f"] {text}\n\n"
                     f"This came from the community rather than from a visit, so nothing was "
                     f"marked Fail and no score has changed.\n"
                     + (f"\nOpen in Atlas Excellence: {link}\n" if link else ""))
        return self._send(recipients, subject, self._shell("Raised by a community", body), text_body)

    # ---------------------------------------------------- quiet action items

    KIND_WORDS = {'standard': 'Failed standard',
                  'manual': 'Raised during a visit',
                  'raised': 'Raised by the community'}

    def _quiet_rows_html(self, items, show_community=False):
        """The list that both reminder emails share.

        Days of silence rather than a date, because "28 days with no update"
        is the fact being reported and a date makes the reader do the
        subtraction.
        """
        def esc(s):
            return html.escape(str(s or ''))
        out = []
        for it in items:
            days = it.get('quiet_days', 0)
            colour = '#b42318' if days >= 30 else '#9a5b00'
            where = (f"<div style='font-size:12px;color:#5a6872;margin-top:3px'>"
                     f"{esc(it.get('community'))}</div>") if show_community else ''
            out.append(
                f"<tr><td style='padding:11px 0;border-bottom:1px solid #e6ebf3'>"
                f"<div style='font-size:14.5px;color:#1b2730;line-height:1.5'>"
                f"{esc(it.get('text'))}</div>"
                f"<div style='font-size:11.5px;color:#5a6872;margin-top:4px'>"
                f"{esc(self.KIND_WORDS.get(it.get('kind'), 'Open item'))}</div>{where}</td>"
                f"<td style='padding:11px 0 11px 14px;text-align:right;vertical-align:top;"
                f"white-space:nowrap;font-size:13px;font-weight:700;color:{colour}'>"
                f"{days} days</td></tr>")
        return ("<table style='width:100%;border-collapse:collapse;margin:6px 0 0'>"
                + ''.join(out) + "</table>")

    @staticmethod
    def _quiet_rows_text(items, show_community=False):
        lines = []
        for it in items:
            where = f" ({it.get('community')})" if show_community else ''
            lines.append(f"  - [{it.get('quiet_days', 0)} days]{where} {it.get('text')}")
        return '\n'.join(lines)

    def send_open_items_reminder(self, recipients, community, items, stage, past_second=0):
        """To the Executive Director: what is open here and has gone quiet.

        The wording avoids blame on purpose. Plenty of these are waiting on a
        contractor or a budget, and an email that reads as an accusation gets
        filtered — at which point the one channel we had is gone. It states
        what is quiet and offers the place to answer.
        """
        if not self.enabled:
            return (False, 'disabled')

        def esc(s):
            return html.escape(str(s or ''))

        n = len(items)
        link = self.report_link(community)
        button = (f"<div style='margin-top:22px'><a href='{esc(link)}' "
                  f"style='display:inline-block;background:#003366;color:#fff;text-decoration:none;"
                  f"font-weight:600;padding:12px 22px;border-radius:8px;font-size:14px'>"
                  f"Open in Atlas Excellence</a></div>") if link else ''

        # The subject leads with the worse number when there is one, because
        # that is what decides whether this gets opened now or later.
        lead = (f"{past_second} past 30 days" if past_second
                else f"no update in {stage} days")
        subject = (f"{n} open item{'' if n == 1 else 's'} at {community} — {lead}")
        escalated = (f"<p style='font-size:13.5px;margin:0 0 16px;line-height:1.6;"
                     f"color:#b42318'><b>{past_second} of these"
                     f"</b> {'has' if past_second == 1 else 'have'} now passed 30 days, "
                     f"so your regional has the same list.</p>") if past_second else ''
        body = (f"<p style='font-size:14px;margin:0 0 16px;line-height:1.6'>"
                f"{'This item has' if n == 1 else f'These {n} items have'} been open at "
                f"<b>{esc(community)}</b> with nothing recorded against "
                f"{'it' if n == 1 else 'them'} for {stage} days or more.</p>"
                f"{escalated}"
                f"{self._quiet_rows_html(items)}"
                f"<p style='font-size:13px;color:#5a6872;margin:18px 0 0;line-height:1.6'>"
                f"A comment counts as an update. If something is waiting on a vendor or a "
                f"budget, saying so on the item is enough to stop this reminder and tells "
                f"whoever looks next where it stands.</p>"
                f"{button}")
        text_body = (f"{n} open item{'' if n == 1 else 's'} at {community} with no update "
                     f"in {stage} days or more.\n"
                     + (f"{past_second} of them have passed 30 days, so your regional "
                        f"has the same list.\n" if past_second else '')
                     + "\n"
                     + self._quiet_rows_text(items)
                     + "\n\nA comment counts as an update. If something is waiting on a "
                       "vendor or a budget, saying so on the item is enough to stop this "
                       "reminder.\n"
                     + (f"\nOpen in Atlas Excellence: {link}\n" if link else ''))
        return self._send(recipients, subject,
                          self._shell(f"No update in {stage} days", body), text_body)

    def send_regional_open_items(self, recipients, region_name, by_community, stage=30):
        """To the regional: everything in their region past the second mark.

        One email covering the whole region, not one per community — somebody
        who covers six sites should be able to see all of it at once and
        decide where to spend a phone call.

        This is a separate message from the Executive Director's rather than
        the same one with them copied, which is what lets it carry internal
        items without those reaching the community.
        """
        if not self.enabled:
            return (False, 'disabled')

        def esc(s):
            return html.escape(str(s or ''))

        total = sum(len(v) for v in by_community.values())
        blocks = []
        text_blocks = []
        for community in sorted(by_community):
            items = sorted(by_community[community],
                           key=lambda i: -i.get('quiet_days', 0))
            blocks.append(
                f"<div style='margin:0 0 20px'>"
                f"<div style='font-size:13px;font-weight:800;color:#003366;"
                f"text-transform:uppercase;letter-spacing:.4px'>{esc(community)}</div>"
                f"{self._quiet_rows_html(items)}</div>")
            text_blocks.append(f"{community}\n" + self._quiet_rows_text(items))

        where = f" in {region_name}" if region_name else ''
        subject = (f"{total} open item{'' if total == 1 else 's'}{where} "
                   f"past {stage} days with no update")
        body = (f"<p style='font-size:14px;margin:0 0 18px;line-height:1.6'>"
                f"{'One item' if total == 1 else f'{total} items'} across your communities "
                f"{'has' if total == 1 else 'have'} had no update for {stage} days or more. "
                f"The Executive Directors have been told about their own.</p>"
                + ''.join(blocks)
                + f"<p style='font-size:13px;color:#5a6872;margin:6px 0 0;line-height:1.6'>"
                  f"Sent once per item when it passes {stage} days. A comment on an item "
                  f"counts as an update and stops it repeating.</p>")
        text_body = (f"{total} open item(s){where} with no update in {stage} days or more.\n"
                     f"The Executive Directors have been told about their own.\n\n"
                     + '\n\n'.join(text_blocks) + "\n")
        return self._send(recipients, subject,
                          self._shell(f"Past {stage} days{where}", body), text_body)

    # Company-level teams a comment can be directed to during a visit.
    ROUTE_LABELS = {'clinical': 'Clinical', 'ops': 'Operations', 'sales': 'Sales'}

    def send_community_findings(self, recipients, community, inspector, when,
                                failed_items, action_items, criteria_map=None,
                                handover=False, notes='', passed_items=None,
                                score=None, not_checked_items=None, help_map=None):
        """What the community itself needs after a visit.

        Still not the leadership report — what needs doing comes first and
        nothing is allowed to push it down the page. But an Executive Director
        used to open this and see only a list of problems, even after a visit
        that went well. So the regional's note leads, and what passed sits
        underneath as context rather than competing with the work."""
        if not self.enabled:
            return (False, 'disabled')

        def esc(s):
            return html.escape(str(s or ''))

        # The note the regional left. First thing read, deliberately: it is
        # the only part of this email that isn't a problem.
        notes = (notes or '').strip()
        notes_html = (f"<div style='margin:0 0 18px;padding:14px 16px;background:#f1f5fa;"
                      f"border-left:3px solid #003366;border-radius:0 8px 8px 0'>"
                      f"<div style=\"font-family:{self.MONO};font-size:11px;color:#00709a;"
                      f"text-transform:uppercase;letter-spacing:.14em;margin-bottom:5px\">"
                      f"Note from {esc(inspector) or 'your regional'}</div>"
                      f"<div style='font-size:14.5px;color:#1b2730;line-height:1.55'>"
                      f"{esc(notes)}</div></div>") if notes else ""
        notes_text = (f"NOTE FROM {(inspector or 'YOUR REGIONAL').upper()}\n  {notes}\n\n"
                      if notes else "")

        # What passed, and the score, underneath everything else.
        #
        # This email is a to-do list first — the findings keep the top of the
        # page. But a list of problems with no counterweight was all a community
        # ever received, however well the visit went. The score is here because
        # they can already see it in the app; leaving it out of the email stopped
        # protecting anyone a long time ago and only made the two disagree.
        passed_items = passed_items or []
        context_bits = []
        if score is not None:
            done = len(passed_items) + len(failed_items)
            context_bits.append(f"<b>{score}%</b> — {len(passed_items)} of {done} standards passed")
        if passed_items:
            names = ''.join(
                f"<li style='margin:3px 0'>{esc(i.get('question_text', 'Standard'))}</li>"
                for i in passed_items)
            context_bits.append(
                f"<div style='margin-top:8px'>Also checked and passed:</div>"
                f"<ul style='margin:4px 0 0;padding-left:18px'>{names}</ul>")
        # Not checked this time: not the community's to fix, but worth knowing
        # it will be looked at next visit. Context, like what passed.
        not_checked_items = not_checked_items or []
        if not_checked_items:
            rows = ''.join(
                f"<li style='margin:3px 0'>{esc(i.get('question_text', 'Standard'))}"
                + (f" — {esc(i.get('description', ''))}" if i.get('description') else "") + "</li>"
                for i in not_checked_items)
            context_bits.append(
                f"<div style='margin-top:8px'>Not checked this time (not scored):</div>"
                f"<ul style='margin:4px 0 0;padding-left:18px'>{rows}</ul>")
        context_html = (
            f"<div style='margin-top:24px;padding-top:16px;border-top:1px solid #e1e5ea;"
            f"font-size:13px;color:#5a6872;line-height:1.55'>"
            + ''.join(context_bits) + "</div>") if context_bits else ""

        context_text = ""
        if context_bits:
            lines = [""]
            if score is not None:
                lines.append(f"{score}% — {len(passed_items)} of "
                             f"{len(passed_items) + len(failed_items)} standards passed")
            if passed_items:
                lines.append("Also checked and passed:")
                lines += [f"  - {i.get('question_text', 'Standard')}" for i in passed_items]
            if not_checked_items:
                lines.append("Not checked this time (not scored):")
                lines += [f"  - {i.get('question_text', 'Standard')}"
                          + (f": {i.get('description')}" if i.get('description') else "")
                          for i in not_checked_items]
            context_text = "\n".join(lines) + "\n"

        link = self.report_link(community)
        button = (f"<div style='margin-top:20px'><a href='{esc(link)}' "
                  f"style='display:inline-block;background:#003366;color:#fff;text-decoration:none;"
                  f"font-weight:600;padding:12px 22px;border-radius:8px;font-size:14px'>"
                  f"Open in Atlas Excellence</a></div>") if link else ""

        # Two ways in: straight after a visit, or when somebody takes over the
        # community and needs to know where things stand. Same content, and the
        # opening line says which it is — arriving to a list of findings with no
        # explanation is disorienting on your first day.
        needs_line = " Here's what needs attention." if (failed_items or action_items) else ""
        opener_html = (f"<p style='font-size:14px;margin:0 0 4px'>You've been set up for "
                       f"<b>{esc(community)}</b> in Atlas Excellence. Here's where things stand today"
                       f"{(' — from the last visit on ' + esc(when)) if when else ''}"
                       f"{(' by ' + esc(inspector)) if inspector else ''}.</p>"
                       ) if handover else (
                       f"<p style='font-size:14px;margin:0 0 4px'>{esc(inspector)} visited "
                       f"<b>{esc(community)}</b>{(' on ' + esc(when)) if when else ''}."
                       f"{needs_line}</p>")
        opener_text = (f"You've been set up for {community} in Atlas Excellence. "
                       f"Here's where things stand today"
                       f"{(' — from the last visit on ' + when) if when else ''}"
                       f"{(' by ' + inspector) if inspector else ''}."
                       ) if handover else (
                       f"{inspector} visited {community}{(' on ' + when) if when else ''}."
                       + needs_line)

        total = len(failed_items) + len(action_items)
        if not total:
            if handover:
                subject = f"Welcome to Atlas Excellence — {community}"
                good = "Nothing is open right now. You'll get an email here after each visit."
                header = "Welcome"
            else:
                subject = f"Visit complete — {community}: nothing outstanding"
                good = ("Everything checked passed — nothing needs your attention." if not_checked_items
                        else "Everything passed — nothing needs your attention.")
                header = "Visit complete"
            body = (opener_html + notes_html
                    + f"<p style='font-size:15px;color:#0b6b49;font-weight:700;margin:12px 0 0'>"
                      f"{esc(good)}</p>{context_html}{button}")
            text = opener_text + "\n\n" + notes_text + good + "\n" + context_text
            return self._send(recipients, subject, self._shell(header, body), text)

        def crit_html(item):
            crit = self._criteria_for(item, criteria_map)
            if not crit:
                return ''
            lis = ''.join(f"<li style='margin:2px 0'>{esc(c)}</li>" for c in crit)
            return (f"<div style='font-size:12px;color:#5a6872;margin:6px 0 2px'>To pass, must include:</div>"
                    f"<ul style='margin:0;padding-left:16px;color:#475569;font-size:12.5px'>{lis}</ul>")

        # The standard's help material (a flyer, a guide), so the community
        # has what it needs to put the finding right without asking for it.
        def help_html(item):
            info = self._help_for(item, help_map)
            if not info:
                return ''
            url = self._help_url(info)
            name = esc(info.get('title'))
            what = (f"<a href='{esc(url)}' style='color:#003366;font-weight:700'>{name}</a>"
                    if url else f"<b>{name}</b> (in Atlas Excellence)")
            return (f"<div style='font-size:13px;color:#36454f;margin-top:6px'>"
                    f"Help material: {what}</div>")

        std_rows = ''.join(self._card(
            f"<div style='font-weight:600;font-size:14.5px;color:#1b2730'>{esc(i.get('question_text', 'Item'))}</div>"
            + (f"<div style='font-size:13.5px;color:#36454f;margin-top:3px'>{esc(i.get('description'))}</div>"
               if i.get('description') else "")
            + crit_html(i) + help_html(i), self.RAIL['fail'])
            for i in failed_items)

        act_rows = ''.join(self._card(
            f"{self._priority_tag(i.get('priority'))} "
            f"<span style='font-size:14px;color:#1b2730'>{esc(i.get('text'))}</span>"
            + (f"<div style='font-size:13px;color:#5a6872;margin-top:4px'>For: "
               f"{esc(i.get('assigned_to_name') or i.get('assigned_to'))}</div>"
               if i.get('assigned_to') else ""), self.RAIL['action'])
            for i in action_items)

        blocks = ''
        if failed_items:
            blocks += self._eyebrow('Standards that need attention', len(failed_items)) + std_rows
        if action_items:
            blocks += self._eyebrow('Other items flagged', len(action_items)) + act_rows

        subject = (f"Welcome to Atlas Excellence — {total} open item{'s' if total != 1 else ''} at {community}"
                   if handover else
                   f"Action needed — {community}: {total} item{'s' if total != 1 else ''}")
        body = (opener_html + notes_html
                + f"{blocks}"
                + context_html
                + f"<div style='margin-top:22px;padding:12px 14px;background:#f1f5fa;"
                f"border-left:3px solid #d3dde8;font-size:13px;color:#1b2730'>"
                f"<b>What to do next.</b> As each one is handled, open it in Atlas Excellence "
                f"and add a comment saying what was done — a photo helps. Your regional will "
                f"review it and close it out.</div>{button}")

        text_lines = [opener_text, ""]
        if notes_text:
            text_lines.append(notes_text.rstrip("\n"))
            text_lines.append("")
        if failed_items:
            text_lines.append(f"STANDARDS THAT NEED ATTENTION ({len(failed_items)})")
            for i in failed_items:
                text_lines.append(f"  - {i.get('question_text', 'Item')}"
                                  + (f": {i.get('description')}" if i.get('description') else ""))
                for c in self._criteria_for(i, criteria_map):
                    text_lines.append(f"      to pass: {c}")
                info = self._help_for(i, help_map)
                if info:
                    url = self._help_url(info)
                    text_lines.append(f"      help material: {info.get('title')}"
                                      + (f" — {url}" if url else " (in Atlas Excellence)"))
            text_lines.append("")
        if action_items:
            text_lines.append(f"OTHER ITEMS FLAGGED ({len(action_items)})")
            for i in action_items:
                text_lines.append(f"  - [{(i.get('priority') or 'medium').upper()}] {i.get('text')}"
                                  + (f" (for: {i.get('assigned_to_name') or i.get('assigned_to')})"
                                     if i.get('assigned_to') else ""))
            text_lines.append("")
        if context_text:
            text_lines.append(context_text.rstrip("\n"))
            text_lines.append("")
        text_lines.append("As each one is handled, comment on it in Atlas Excellence — a photo "
                          "helps. Your regional will review and close it out.")
        if link:
            text_lines += ["", f"Open: {link}"]

        return self._send(recipients, subject,
                          self._shell("Welcome" if handover else "What needs attention", body),
                          "\n".join(text_lines))

    def send_standard_comment(self, recipients, community, standard,
                              author, text, has_photo=False):
        """Tell the inspector that someone commented on one of their findings —
        usually the community reporting that it has been fixed."""
        if not self.enabled:
            return (False, 'disabled')
        subject = f"New comment — {community}: {standard[:60]}"
        photo_line = ("<p style='font-size:13px;color:#5a6872;margin:8px 0 0'>"
                      "A photo was attached — open the item to see it.</p>") if has_photo else ""
        link = self.report_link(community)
        button = (f"<div style='margin-top:18px'><a href='{html.escape(link)}' "
                  f"style='display:inline-block;background:#003366;color:#fff;text-decoration:none;"
                  f"font-weight:700;padding:11px 20px;border-radius:8px;font-size:14px'>"
                  f"Review the item</a></div>") if link else ""
        body = (f"<p style='font-size:14px;margin:0 0 4px'><b>{html.escape(author)}</b> commented on"
                f" <b>{html.escape(standard)}</b> at {html.escape(community)}.</p>"
                f"<blockquote style='margin:12px 0;padding:10px 14px;border-left:3px solid #d3dde8;"
                f"background:#f1f5fa;font-size:14px;color:#1b2730'>{html.escape(text)}</blockquote>"
                f"{photo_line}"
                f"<p style='font-size:12.5px;color:#5a6872;margin:14px 0 0'>The item is still open. "
                f"Once you're satisfied it's resolved, mark it as addressed.</p>{button}")
        text_body = (f"{author} commented on {standard} at {community}:\n\n  {text}\n"
                     + ("\n(a photo was attached)\n" if has_photo else "")
                     + "\nThe item is still open until a regional marks it as addressed.\n"
                     + (f"\nReview it: {link}\n" if link else ""))
        return self._send(recipients, subject, self._shell("New comment", body), text_body)

    def send_directed_comments(self, recipients, route, submission, items):
        """Email a company-level team the comments an inspector directed to them."""
        if not self.enabled:
            return (False, 'disabled')
        label = self.ROUTE_LABELS.get(route, route.title())
        community = submission.get('community', 'a community')
        inspector = submission.get('inspector_name') or submission.get('username') or 'Unknown'
        when = (submission.get('submitted_at') or '')[:10]

        def esc(s):
            return html.escape(str(s or ''))
        # A Not checked's text is the reason it was skipped, not a finding;
        # sent to a department bare, it would read as one.
        def nc(it):
            return 'Not checked: ' if it.get('condition') == NOT_CHECKED else ''
        rows = ''.join(
            f"<li style='margin:8px 0'><strong>{esc(it.get('question_text','Item'))}</strong>"
            f"<div style='color:#475569;font-size:13px;margin-top:2px'>{esc(nc(it))}{esc(it.get('description',''))}</div></li>"
            for it in items
        )
        link = self.report_link(community)
        button = (f"<div style='margin-top:18px'><a href='{esc(link)}' style='display:inline-block;"
                  f"background:#003366;color:#fff;text-decoration:none;font-weight:700;padding:11px 20px;"
                  f"border-radius:8px;font-size:14px'>View full report</a></div>") if link else ""
        body = (f"<p style='font-size:14px;margin:0 0 12px'>{esc(inspector)} directed the following "
                f"{label.lower()} item(s) to your team during a visit to <strong>{esc(community)}</strong>"
                f"{(' on ' + esc(when)) if when else ''}.</p>"
                f"<ul style='margin:0;padding-left:18px;font-size:14px;color:#1b2730'>{rows}</ul>{button}")
        subject = f"{label} follow-up — {community} ({len(items)})"
        text_lines = [f"{inspector} directed {len(items)} {label.lower()} item(s) to your team for {community}:"]
        for it in items:
            text_lines.append(f"  - {it.get('question_text','Item')}: {nc(it)}{it.get('description','')}")
        if link:
            text_lines += ["", f"View the full report: {link}"]
        return self._send(recipients, subject, self._shell(f"{label} follow-up", body), "\n".join(text_lines))

    def send_selected_standards(self, recipients, submission, responses,
                                survey_type_name=None, criteria_map=None):
        """A subscriber who asked for only some standards: those answers from
        this visit, and nothing else — no score, no note, no action items.
        No link to the report either: these are teams outside Excellence
        (PPC, Social Media) with no account, so it would only ask them to
        sign in."""
        if not self.enabled:
            return (False, 'disabled')
        community = submission.get('community', 'a community')
        inspector = submission.get('inspector_name') or submission.get('username') or 'Unknown'
        when = (submission.get('submitted_at') or '')[:10]

        def esc(s):
            return html.escape(str(s or ''))
        rail = {'Pass': self.RAIL['pass'], 'Fail': self.RAIL['fail'], NOT_CHECKED: self.RAIL['not_checked']}

        def card(r):
            cond = r.get('condition') or ''
            crit = self._criteria_for(r, criteria_map) if cond == 'Fail' else []
            crit_html = ''
            if crit:
                items = ''.join(f"<li style='margin:2px 0'>{esc(c)}</li>" for c in crit)
                crit_html = (f"<div style='font-size:12px;color:#5a6872;margin:4px 0 2px'>Standard — to pass, must include:</div>"
                             f"<ul style='margin:0 0 6px;padding-left:16px;color:#475569;font-size:12px'>{items}</ul>")
            return self._card(
                f"<div style=\"font-family:{self.MONO};font-size:10.5px;letter-spacing:.08em;"
                f"text-transform:uppercase;color:#5a6872;margin-bottom:3px\">{esc(cond)}</div>"
                f"<div style='font-weight:600;font-size:14.5px;color:#1b2730'>{esc(r.get('question_text', 'Item'))}</div>"
                + (f"<div style='font-size:13.5px;color:#36454f;margin-top:3px'>{esc(r.get('description', ''))}</div>"
                   if r.get('description') else "")
                + crit_html, rail.get(cond, '#003366'))

        survey_row = (f"<tr><td style='color:#5a6872;padding:3px 14px 3px 0'>Survey type</td>"
                      f"<td style='font-weight:600'>{esc(survey_type_name)}</td></tr>") if survey_type_name else ""
        body = (f"<table style='font-size:14px;border-collapse:collapse;margin-bottom:6px'>"
                f"<tr><td style='color:#5a6872;padding:3px 14px 3px 0'>Inspector</td><td style='font-weight:600'>{esc(inspector)}</td></tr>"
                f"<tr><td style='color:#5a6872;padding:3px 14px 3px 0'>Date</td><td style='font-weight:600'>{esc(when)}</td></tr>"
                f"{survey_row}</table>"
                + self._eyebrow('Your standards', len(responses))
                + ''.join(card(r) for r in responses)
                + "<p style='color:#5a6872;font-size:12px;margin:6px 0 0'>"
                  "You receive only the standards chosen for you.</p>")
        fails = sum(1 for r in responses if r.get('condition') == 'Fail')
        subject = (f"Visit — {community}: {len(responses)} standard(s) you follow"
                   + (f", {fails} failed" if fails else ""))
        text_lines = [f"Visit to {community}", f"Inspector: {inspector}", f"Date: {when}"]
        if survey_type_name:
            text_lines.append(f"Survey type: {survey_type_name}")
        text_lines.append("")
        for r in responses:
            note = r.get('description', '')
            text_lines.append(f"  - [{r.get('condition', '')}] {r.get('question_text', 'Item')}"
                              + (f": {note}" if note else ""))
        return self._send(recipients, subject,
                          self._shell(community, body, eyebrow='Visit report'), "\n".join(text_lines))

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
