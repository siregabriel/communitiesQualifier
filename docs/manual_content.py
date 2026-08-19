"""
Content for the Atlas Excellence manual.

Kept apart from the layout code so the wording can be edited without touching
anything to do with fonts and page breaks. Every statement here was checked
against the running app rather than written from memory — where a number
appears (seven days, thirty days, three days) it is the value the code uses.

Markup understood by build_manual.py:
    ('h1', text)      new page, section title
    ('h2', text)      sub-heading
    ('p', text)       paragraph; <b> and <i> allowed
    ('bullets', [..]) bulleted list
    ('steps', [..])   numbered list
    ('table', [[..]]) first row is the header
    ('note', text)    boxed aside
    ('spacer', n)     vertical space in points
"""

VERSION = "2.0"
PRODUCT = "Atlas Excellence"

# --------------------------------------------------------------------------

COVER = {
    'title': 'Atlas Excellence',
    'subtitle': 'Community standards, visits and follow-up',
    'blurb': 'A guide for Executive Directors, Regionals and Administrators',
}

SECTIONS = [

# ===========================================================================
('h1', 'What this app is for'),

('p', 'Atlas Excellence keeps one record of how each community is doing, and '
      'one place to work through what a visit finds.'),

('p', 'A regional walks a community and marks each standard Pass or Fail. What '
      'they find becomes that community\'s score. The Executive Director then '
      'reports what has been put right, with a photo, and a regional confirms '
      'it. Only then does the score move.'),

('p', 'That last part is the whole design. A community can always say what it '
      'has done, and can never mark its own work as finished. It is what makes '
      'the number on the dashboard worth something.'),

('h2', 'The two scores'),

('p', 'Every community shows two numbers, and they mean different things.'),

('table', [
    ['', 'What it is', 'When it changes'],
    ['Current score',
     'Where the community stands today, counting fixes a regional has verified.',
     'Goes up as fixes are confirmed. You do not wait for the next visit.'],
    ['Visit score',
     'What the visit found on the day. A permanent record.',
     'Never. It stays as it was so past visits stay comparable.'],
]),

('p', 'Only the most recent visit counts toward the score. An older visit does '
      'not drag the number down forever, and a community cannot improve its '
      'standing by being visited more often.'),

('note', 'A community never inspects itself. The score comes from the latest '
         'visit, so a self-run walkthrough would quietly replace what the '
         'regional found — open items and all.'),

# ===========================================================================
('h1', 'Signing in'),

('p', 'The app runs in a web browser. There is nothing to install. It works on '
      'a phone, a tablet and a computer, and the layout adapts to each.'),

('steps', [
    'Open the address you were sent and enter your username and password.',
    'The first time, you will be asked to set a password of your own.',
    'If you forget it, use "Forgot password" on the sign-in screen. A reset '
    'arrives by email.',
]),

('h2', 'Put it on your home screen'),

('p', 'On a phone it is worth adding to the home screen, so it opens like an '
      'app instead of a bookmark:'),

('bullets', [
    '<b>iPhone:</b> open it in Safari, tap Share, then "Add to Home Screen".',
    '<b>Android:</b> open it in Chrome, tap the menu, then "Install app".',
]),

('note', 'If a message from the app does not arrive, look in Junk or Spam '
         'first and mark it as safe. That is where they land until your mail '
         'system has seen a few of them.'),

# ===========================================================================
('h1', 'Who can do what'),

('p', 'What you see depends on your role. Nobody is shown a button that would '
      'be refused.'),

('table', [
    ['', 'Executive Director', 'Regional / Corporate', 'Administrator'],
    ['Run a visit', 'No', 'Yes', 'No'],
    ['Comment on a finding', 'Yes', 'Yes', 'Yes'],
    ['Mark a finding as addressed', 'No', 'Yes', 'Yes'],
    ['See other communities', 'No', 'Their region', 'All'],
    ['Manage people and standards', 'No', 'No', 'Yes'],
]),

('p', 'A regional covers the communities of their region. A Corporate member '
      'covers the whole company. An Executive Director sees their own '
      'community, and can cover a second one when standing in for a '
      'neighbour — without a second login.'),

('p', 'Administrators do not run visits. The role exists to manage the system, '
      'not to inspect. If you need to do both, an administrator can set you up '
      'as a Corporate member with administrator privileges.'),

# ===========================================================================
('h1', 'Your dashboard'),

('p', 'The dashboard opens with <b>Needs you</b> — the short list of things '
      'waiting on you specifically. Everything below it is context.'),

('h2', 'If you are a regional'),

('bullets', [
    '<b>Fixes waiting on your confirmation.</b> A community has reported these '
    'as done. Their score does not move until you agree.',
    '<b>Due for a visit.</b> Communities past the visit target, and any that '
    'have never been visited.',
    '<b>Open with no follow-up.</b> Findings nobody has said anything about '
    'since the visit.',
]),

('h2', 'If you are an Executive Director'),

('bullets', [
    '<b>Needs an update from you.</b> Failed standards you have not yet '
    'responded to.',
    '<b>With your regional.</b> What you have reported and are waiting on '
    'someone to confirm.',
]),

('p', 'Click any line to go straight to it. When there is nothing pending, the '
      'panel is not there at all.'),

('h2', 'The rest of the dashboard'),

('bullets', [
    'Average score, communities visited this month, open action items.',
    'Performance by region — click a region to drill into its communities.',
    'The standards that fail most often across the company.',
    'Recent activity, and a calendar of what is coming up.',
]),

('p', 'Press <b>/</b> from anywhere to search communities, people and past '
      'visits. On a phone, use the search button in the header.'),

# ===========================================================================
('h1', 'Running a visit'),

('p', 'For regionals and Corporate members.'),

('steps', [
    'Tap <b>+</b> in the bottom bar on a phone, or "Start New Visit".',
    'Choose the type of review. A review with no standards behind it is greyed '
    'out — it would only give you an empty form.',
    'Choose the community.',
    'Work through each standard, marking Pass or Fail.',
    'Add a photo where it helps. A photo is worth more than a sentence.',
    'Submit.',
]),

('h2', 'A Fail needs a comment'),

('p', 'The app will not accept a Fail without a note saying what you found. '
      'Whoever fixes it needs to know where to start, and "Fail" on its own '
      'tells them nothing. If you try to submit without one, the app jumps to '
      'the item.'),

('h2', 'Sending a finding to a team'),

('p', 'A finding can be directed to <b>Clinical</b>, <b>Operations</b> or '
      '<b>Sales</b>. That team is emailed directly, without waiting for anyone '
      'to pass it along.'),

('h2', 'Action items'),

('p', 'Anything that needs attention but is not one of the standards goes '
      'under <b>Additional action items</b>. These are tasks, and they never '
      'affect the score.'),

('h2', 'You can stop and come back'),

('p', 'The form saves itself on your device as you go, photos included. Lose '
      'signal, take a call, walk out to the car — when you come back to that '
      'community you will be offered the unfinished visit. Nothing is sent '
      'until you press Submit.'),

('note', 'A saved visit is kept on that device for seven days. It never leaves '
         'the phone until you submit, so finish it on the same phone you '
         'started it on.'),

('h2', 'Sending an incomplete visit'),

('p', 'You can submit having answered only some of the standards — a walk gets '
      'interrupted. The app will tell you how many are unanswered and ask you '
      'to confirm, and the visit is then marked <b>Partial</b> wherever the '
      'score appears.'),

('p', 'That marking matters. The score only covers the standards that were '
      'answered, so three of eight all passed reads as 100%. The label is what '
      'stops that being mistaken for a clean full visit.'),

# ===========================================================================
('h1', 'After the visit'),

('p', 'A visit is not the end of anything. The work is what happens next.'),

('h2', 'What the community receives'),

('p', 'When a visit is submitted, the community and the region\'s leadership '
      'are emailed what it found: the score, the standards that failed, the '
      'photos and any action items raised.'),

('h2', 'Reporting a fix — Executive Directors'),

('steps', [
    'Open <b>Action Items</b>, or click the line in "Needs you".',
    'Find the standard and press <b>Comment on this</b>.',
    'Say what was done, and attach a photo of it.',
]),

('p', 'Your regional is emailed straight away. You cannot close the item '
      'yourself, and that is deliberate — your comment is the report, their '
      'confirmation is the sign-off.'),

('h2', 'Confirming a fix — regionals'),

('steps', [
    'The item appears under "Fixes waiting on your confirmation".',
    'Read what was done and look at the photo.',
    'If you are satisfied, press <b>Mark as addressed</b>.',
    'If not, comment back. The community is emailed and it returns to them.',
]),

('p', 'Marking it addressed is what lifts the community\'s current score. The '
      'visit\'s own score does not change — the record of that day stays '
      'exactly as it was.'),

('h2', 'History'),

('p', 'Open any community for its full history: every past visit, and a track '
      'record for each standard. Anything marked <b>recurring</b> has failed '
      'three times or more, which is usually worth more attention than a '
      'one-off.'),

('p', 'A small chart shows whether the community is improving across recent '
      'visits. It uses the visit score each time, not the current one, so '
      'fixes made afterwards cannot flatter the line.'),

# ===========================================================================
('h1', 'Move-Ins'),

('p', 'Every new resident gets a checklist, in four phases:'),

('bullets', [
    '<b>Pre Move-In</b> — red carpet and preparation.',
    '<b>Move-In Day</b> — the tour-in.',
    '<b>Welcome Home</b>.',
    '<b>Follow-Up</b> — day 5, and one to two weeks in.',
]),

('p', 'Some items are required for compliance and can carry an attachment. A '
      'move-in cannot be marked complete while a required item is still open — '
      'the app will say which ones.'),

('p', 'A reminder is emailed to the community three days before each move-in '
      'date, and again when the move-in is completed. Regionals are not emailed '
      'each one — a region covering a dozen communities would receive forty or '
      'fifty a month, and a mailbox like that teaches you to ignore the sender. '
      'They see every move-in in their region here instead.'),

('p', 'Anything past its date with required items still open is reported in the '
      'daily summary until it is dealt with, so nothing drifts quietly.'),

('p', 'Each move-in can be printed as a binder page, and the whole list exports '
      'to Excel or CSV.'),

# ===========================================================================
('h1', 'For administrators'),

('h2', 'People'),

('p', 'Everyone with access lives in one list. Adding someone creates their '
      'login and emails it to them automatically. From here you can change '
      'roles, reset passwords, remove access, and grant administrator '
      'privileges to a Corporate member.'),

('p', 'Each row shows sign-in activity: a green marker while someone is using '
      'the app, when they last signed in, or <b>Never signed in</b> — which is '
      'the one to act on. An account nobody has opened is not adoption.'),

('h2', 'Standards'),

('p', 'This is where the questions come from. Each standard carries its pass '
      'criteria, the communities it applies to, and which reviews it belongs '
      'to.'),

('note', 'A standard with no review ticked belongs to <i>every</i> review. '
         'That is the rule the visit form applies, so it is worth knowing '
         'before you start ticking boxes.'),

('p', 'If a review is left with no standards, a warning appears at the top of '
      'this page, and that review cannot be picked when starting a visit. '
      'Emptying one is an ordinary-looking edit and the effect would otherwise '
      'only surface to a regional already standing in a community.'),

('p', 'When you add a community in Regions, it becomes available here '
      'immediately — but it is not attached to any standard until you tick it.'),

('h2', 'Settings'),

('bullets', [
    '<b>Who receives which visit emails</b>, by region or by inspector.',
    '<b>Clinical, Operations and Sales</b> routing addresses.',
    '<b>Visit target</b> — how many days a community may go between visits '
    'before it is flagged. Thirty by default. Nothing is blocked by it; it '
    'decides what counts as falling behind.',
    '<b>Who receives what</b> — every address the app sends to, flagging '
    'anyone missing an email address.',
]),

('h2', 'The daily summary'),

('p', 'Administrators receive one email a day covering who signed in, visits '
      'submitted, what communities reported, what is waiting on a regional, '
      'password activity, and errors people hit.'),

('p', 'It also reports the backup, but only when something is wrong — if no '
      'backup has succeeded for more than a day and a half. A green tick every '
      'morning becomes furniture within a week and stops being read.'),

# ===========================================================================
('h1', 'When something goes wrong'),

('table', [
    ['What you see', 'What it means'],
    ['"No questions available for this survey type"',
     'No standards are set up for that review and community. An administrator '
     'fixes it under Standards; it is not a fault with your device.'],
    ['A review is greyed out when starting a visit',
     'It has no standards behind it. Pick another, and tell an administrator.'],
    ['Emails are not arriving',
     'Check Junk or Spam and mark them safe. If a person has no email address '
     'on file, Settings will show it under "Who receives what".'],
    ['Your unfinished visit is missing',
     'Drafts stay on the device that made them, for seven days. Use the same '
     'phone, and check you picked the same community.'],
    ['A score looks wrong',
     'Check whether the visit is marked Partial. The score only covers the '
     'standards that were answered.'],
]),

('p', 'If none of that fits, send a screenshot of what you are seeing before '
      'you leave the community. It is far easier to sort out while you are '
      'still on site.'),
]
