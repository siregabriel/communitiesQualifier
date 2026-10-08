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
- A regional's scope *is* their region. No region → `regional_communities()`
  returns `[]` and they see nothing. Corporate members are in the `corporate`
  group, whose `kind` grants every community.
- A regional can reach every community **and stay in their region**
  (People → Edit → "Can visit every community"). Stored as `all_communities`
  in profiles.json, not on the leader record (`update_leader` rebuilds it).
  Region still decides who gets that region's emails.

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
