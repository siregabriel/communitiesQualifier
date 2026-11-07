# Atlas Excellence

Flask app for Atlas Senior Living: regionals and corporate staff walk
communities against a set of standards, failures become action items, and
Executive Directors close them. Code lives in `app_mantenimiento/`. Deployed on
AWS Lightsail; storage is JSON files on disk, photos in a private S3 bucket,
email through SES.

## Working with Gabriel

- Converse in **Spanish**. Code, comments, test names and commit messages in **English**.
- "No toques nada (aún)" means investigate and explain — change nothing.
- Give an opinion before building; he decides. Disagree with data, not adjectives.
- Keep replies short. He will ask for more.
- He runs `git push` and every server command himself. Claude has no SSH access:
  hand him exact, copy-pasteable, read-only-where-possible commands.
- He does all AWS console / IAM work himself.

## Commands

Run from `app_mantenimiento/`:

```bash
python3 -m pytest tests/ -q --ignore=tests/test_smoke.py
node tests/run-all.mjs        # discovers every tests/*.mjs; fails if it finds none
```

**Never run `tests/test_smoke.py` against production.** It makes ~40 writes on
real data and one test temporarily renames a real community.

## Deploy

Push to `main` → GitHub Actions runs both suites as a gate → SSH →
`deploy/deploy.sh` → `git reset --hard origin/main` → `pip install` →
`systemctl restart atlas`. A red suite stops the deploy.

- Server repo `/home/ubuntu/CommunitiesQualifier`, venv `../.venv` from the app dir.
- Env `/etc/atlas/atlas.env`. **Never** include it in S3 backups: its keys
  grant access to that same bucket.
- Units: `atlas` (gunicorn, 2 workers, timeout 60) and `atlas-reminders.timer`
  (12:00 UTC daily). The deploy does not install timers; that was manual.
- nginx `client_max_body_size 20M` vs Flask `MAX_CONTENT_LENGTH` 16MB — they
  disagree; known, left alone.

## Data

- `app_mantenimiento/data/*.json` is live data, **git-ignored**. Deploys never touch it.
- `data/seeds/` ships in git and only populates a live file that does not exist
  yet: regions, questions, survey_types, resources, movein_template,
  community_places. Editing a seed does not change an existing server.
- Accounts live in **two** stores: `users.json` (admins, EDs, admin-created) and
  the leadership lists in `regions.json` (regionals and the Corporate group).
  Anything that looks accounts up must check both.
- Role names: stored `staff` = **Executive Director**; stored `team` = shown as
  **Staff** (a community's team: chef, maintenance…). `team`: one community, no
  "Also covers", sees its items (never internal), comments and raises, never
  closes/visits, no move-ins, no ED email (`community_account_emails` is
  `staff` only). `TEAM_ROLE` / `is_team()` in app.py.
- Staff positions: any admin adds/removes them **only in Settings → Staff
  positions**; Add/Edit person just picks (Gabriel's call: nobody invents one
  while adding somebody). `team_position_service`, `data/team_positions.json`,
  the original six until first change. Stored on the person as **text**, so no
  rename; removing keeps it for whoever holds it. No reordering (not wanted).
- A regional's scope *is* their region. No region → `regional_communities()`
  returns `[]` and they see nothing. Corporate members are in the `corporate`
  group, whose `kind` grants every community.
- A regional can reach every community **and stay in their region**
  (People → Edit → "Can visit every community"). Stored as `all_communities`
  in profiles.json, not on the leader record (`update_leader` rebuilds it).
  Region still decides who gets that region's emails.
- Or named extras (People → Edit → "Also visits"): `extra_communities` in
  profiles.json, admin-only, own-region names dropped. Name-keyed, so it is
  in the community rename walk (`profile_service.rename_community`).
- Atlerts SSO matches the account's own email first, then a linked
  `atlerts_email` in profiles.json (personal Gmail etc.). Linked by the
  person: failed `/sso` leaves `session['atlerts_pending']`, the next
  password login offers "Link / Not me" (`/api/atlerts-link`, address read
  from the session only). Admin unlinks in People. Never emailed.

## AtlasAI (read-only API for Atlerts)

`POST /api/atlasai/query` (end of `app.py`) answers questions from AtlasAI, the
admin assistant inside Atlerts. Server to server, same `ATLERTS_SSO_SECRET` and
`X-Atlerts-Sso-Secret` header as `/sso`, plus the person's verified email.

- Scope is Excellence's own: the account is found like `/sso` does and every
  answer runs inside `_atlasai_as()`, an isolated request context with that
  account's session. No scoping rule is copied. **If `/sso` or `/api/login`
  change the session keys, `_atlasai_as()` must change too.**
- Read-only and small: never move-ins (resident names), comments, visit notes,
  photos or emails. `tests/test_atlasai_api.py` guards all of it.

## Nearby visits (positions for Atlerts, Oct 2026)

Atlerts (iOS) suggests "You're at X — start a visit in Excellence?" when a
regional or Corporate arrives at one of their communities. The phone compares
its own location; **where anybody is never reaches this server.**

- `POST /api/atlerts/visit-places`: same door as AtlasAI (secret + verified
  email, runs inside `_atlasai_as()`). Only for people who run visits
  (`can_run_visits()` and not a native admin); only `visible_communities()` that
  have a place in `place_service`; returns name, lat, lng, days since the last
  visit. Kill switch: `ATLERTS_NEARBY_VISITS=0` in the environment.
- `/sso?next=`: after signing in, `_sso_next()` follows only a local path on
  `_SSO_NEXT_PATHS` (`/select-survey-type`, `/reporte`), query kept; anything
  else is the home page. `/select-survey-type?community=` carries a community the
  person can see to `/reporte?community=` once the type is chosen.
- `tests/test_nearby_visits.py` guards all of it.

## Answers and order (Nov 2026, Greg's requests)

- A standard is `Pass`, `Fail` or `Not checked` (`services/conditions.py`).
  Not checked needs a reason (in `description`, enforced in form and server),
  is out of every score and pass rate, counts as answered (not partial), and
  is shown in the panel, history, emails, exports and AtlasAI. Anything new
  that counts responses must decide what it does with it.
- Visit notes are **private** to the ED and leadership unless the visitor
  ticks "Share this note with the community's staff" (`notes_shared` on the
  submission; absent = private, so older visits are private). Staff (`team`)
  still get the visit and its findings; `_without_private_note()` /
  `_visit_note_hidden()` strip note + photo server-side in `/api/inspections`
  and the history (Lauren Hamilton, Nov 2026). A new place that serves a
  visit must use them.
- A standard can be **Every community** (`all_communities: true`): it covers
  communities added later too; `QuestionManager.covers()` is the one test.
  Standards that listed every community were switched once at startup
  (`adopt_every_community`, marker `every_community_v1` in the questions
  file; Greg agreed). Standards → select rows → add/remove one community
  (`/api/questions/communities`); never leaves a standard with none.
- Question order: admins move standards up/down in Standards
  (`/api/questions/order`). One global `order`; each survey type shows its own
  questions in it; new ones go last. Never reordered → newest first, as before.

## Unfinished visits (drafts)

Phone first (IndexedDB, works offline), server second. Since Greg Crutcher lost
33 answers that existed only on his phone (Nov 2026):

- Every local save also PUTs `/api/drafts/content` (text only); each photo goes
  to `/api/drafts/photo` as it is taken → bucket `uploads/drafts/<user>/…`.
  `services/draft_service.py`, `data/drafts.json`. One per user + community +
  survey type, **no cap**, expires after 14 days with its photos.
- Owner only: not another regional, not an admin (admins keep the signpost in
  `draft_notice_service` for support, never the content). Paths never sent.
- The form restores the saved visit **before** autosave starts (the bug that
  cost Greg's answers), and picks the newer of phone/server copy by `saved_at`.
- Cleared on submit (server side too), discard, and expiry. Both stores are in
  the community rename walk.
- Submitting still uploads photos from the phone; reusing the draft photos
  already in the bucket was deliberately left for later.
- Owners are reminded at 3 and 11 quiet days (`REMIND_AT_DAYS`) by
  `send_reminders.py` (same dry-run/weekend/pause rules). Admins: read-only
  review, Remind, and "Send on their behalf" (`/api/drafts/send-on-behalf`):
  filed as the owner's visit, marked "Sent by Excellence Administrator on
  <date> on behalf of <name>" — the admin is **never named** on the visit or
  emails (Gabriel's choice), only in the activity log. Post-visit emails live
  in `_send_visit_emails()`, shared with the normal submit.

## Look ("Precisión" skin, Nov 2026)

- One section at the end of `static/theme.css` (PRECISION SKIN): navy
  `#003366`, Roboto + JetBrains Mono (numbers), static engineering grid
  instead of the animated blobs, white cards with hairline + soft shadow,
  navy sidebar with an electric `#00BFFF` rail on the current item (light
  mode; dark keeps its own). Revert = remove that section + the font links.
- `#00BFFF` / `#FFA500` are under 2.2:1 on white: lines, rails, fills only,
  never text. jsdom ignores `var()` inside the `background:` shorthand, so
  colours a test measures are written literally.
- Emails keep the old `#00285c`; templates and theme were moved to `#003366`.
- Gabriel's answer colours: chosen Pass `#75fb87` with dark ink, Fail
  `#ea366e` with white (4.0:1, his choice), Not checked `#5b6b85`. A visit
  card's left rail and a panel response's rail take the answer's colour
  (`:has()`); navy until answered. Submit is `#5ac486` with dark ink.
  Visit notes keep their blue rail on purpose: they are not a standard.
- A score's colour as text: `scoreColor()` only (returns `var(--score-*)`,
  defined light + dark in theme.css). Never write a band hex inline.
- Phones: the theme's `@media (max-width: 768px)` parts own the mobile
  header (one icon row; labels kept at font-size 0), the flat tab bar lives
  in `mobile_tabbar.html`. A rule that forces `display` must skip elements
  the page hides inline (Question Manager leaked to regionals once).
- `login.html` and `change_password.html` style themselves (login loads
  theme.css *before* its own block). The visit form's body is `.visit-page`.
- jsdom also drops `var()` in an `!important` `font-family`, has no media
  queries (tests unwrap them: `test_phone_skin.mjs`) and does not expand
  `border-radius` longhands. Write measured values literally.

## Pitfalls already paid for

- `templates/dashboard.html` is an ~11k-line monolith with inline JS. Tests pull
  functions out by brace-matching and run them in jsdom.
- **Scope on the server.** Use `visible_communities()` / `_can_see_community()`;
  never fetch everything and filter in the browser. Internal raised items:
  `can_see_internal()`, server-side only — don't copy the rule into JS.
- `openSlidePanel(community, submissionId)`: a row that represents one visit
  passes its id; community-level callers don't. `test_visit_link.mjs` counts call
  sites, so a new caller fails until you decide which kind it is.
- Read request fields with `_field(name)` (form, then JSON). Never branch on
  `if request.files` — a photoless multipart post has empty files. A test forbids it.
- `lastVisit` holds a date or `''`. "Never visited" is `lastVisitTs == 0`.
  Never put display text in a data field.
- `[hidden]` loses to any author `display:` rule. Add `.x[hidden]{display:none}`.
- Never build `onclick` strings around names. `escapeHtmlForAttr` turns `'` into
  `&#39;`, which the parser decodes back into code. Attach handlers in JS.
- A community rename walks: regions, questions, inspections, move-ins, raised
  items, cover photo, `place_service`. A new name-keyed store must join that chain.
- One home per style rule. Shared rows (e.g. Regions edit row) live in
  `static/theme.css`, not duplicated in the template.
- Map positions: `city` is the town only; districts go in `note`. Edited from
  Regions → pencil, saved via `/api/map/communities/<name>`; bounds-checked on
  write and on read.

## Testing discipline

- After every change, **break it on purpose** and confirm a test fails. If it
  doesn't, the test is the bug.
- Assert the thing, not the word. A grep for a flag name passes after the guard
  is deleted; a check for "some call exists" passes after the call is removed.
- Watch for vacuous tests: two empty lists compared, a route URL that 404s from
  Flask (`/comment` not `/comments`), a fixture that never contains the case.
- jsdom: no layout, cascade by document order (not specificity), no media
  queries. **Layout bugs need a human screenshot** — say so instead of claiming
  it's verified.
- Test docstrings tell the incident that motivated them, in plain English.

## Commits

Imperative subject. Body tells the story: what was wrong, how it was found, what
changed, what was deliberately not done, mutations run and caught.
Author `Gabriel Rosales <gabriel@gabrielrosales.org>`.

## Live features with state

- **Reminders** (`send_reminders.py`): 15 days quiet → ED; 30 → ED and regional
  (separate message, may carry internal items; the ED's never does). Clock
  armed 2026-09-24 12:33; first possible sends ~2026-10-09. Dry run by default;
  only the systemd unit passes `--send`. `--status`, `--pause`, `--resume`.
- **Map** (Communities → List/Map): pins by score band; grey ring past 60 days.
  Shown only to accounts covering more than one community. Google Maps JS
  (Advanced Markers): `GOOGLE_MAPS_API_KEY` + `GOOGLE_MAPS_MAP_ID` in
  `/etc/atlas/atlas.env`, served only inside `/api/map/communities` to
  accounts with >1 community. Key is referrer-restricted in Google Cloud;
  never commit it (a test scans for `AIza…`). Missing either → page says
  "not set up".

## Open questions

- Greg: should department recipients ("home base team") also get reminders?
  Currently EDs and regionals only.
- Visit panel two-column gaps (grid vs `column-count`) — never decided.
