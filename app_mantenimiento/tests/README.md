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

## JavaScript — draft storage

```bash
npm install --no-save fake-indexeddb
node tests/test_drafts.mjs
```

Covers the unfinished-visit store: answers, ad-hoc items and photo blobs
surviving a round trip, one draft per community, expiry after seven days, and
removal on submit.

It mirrors the store in `templates/reporte.html` rather than importing it — the
code lives inline in the template. If you change the database name, version,
keyPath or the put/get calls there, change them here too.
