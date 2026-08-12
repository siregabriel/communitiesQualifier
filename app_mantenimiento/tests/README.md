# Tests

Two suites, run them both before deploying.

## Python — the API and its scoping rules

```bash
python3 -m pytest tests/test_smoke.py -q
```

Covers the things that have actually broken: role scoping, who may close an
item, community isolation, exports, the move-in compliance gate, and the
capability flags the dashboard uses to show or hide controls.

These run against the real `data/*.json` files. Every test creates and removes
its own records, so the data is left as it was found.

## JavaScript

Install both packages in one command — `npm install --no-save` prunes anything
it isn't asked for, so installing them separately leaves you with only the last.

```bash
npm install --no-save fake-indexeddb jsdom
node tests/test_drafts.mjs
node tests/test_dashboard_render.mjs
```

**`test_drafts.mjs`** covers the unfinished-visit store: answers, ad-hoc items
and photo blobs surviving a round trip, one draft per community, expiry after
seven days, and removal on submit.

It mirrors the store in `templates/reporte.html` rather than importing it — the
code lives inline in the template. If you change the database name, version,
keyPath or the put/get calls there, change them here too.

**`test_dashboard_render.mjs`** pulls the script out of
`templates/dashboard.html` and runs it in a real DOM, then calls the render
functions and inspects the HTML they produce. Covers the "Needs you" strip and
the visit-cadence rules on the community cards.

This one exists because syntax checks don't catch what has actually broken this
app: a variable that no longer exists, or a function that only fails when
something calls it. Both have reached production. Running the code is the only
check that finds them.
