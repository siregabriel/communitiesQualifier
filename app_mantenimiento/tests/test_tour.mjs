/*
  The walkthrough: when it opens, and whether it can be told to stop.

  It was opening on every single visit. The four per-view tours mark themselves
  as seen the moment they start; the main one marked itself only in endTour(),
  so reloading, navigating away, or a phone discarding the page mid-tour left
  it unmarked — and it asked again. And again.

  Two things are held down here. That it opens once and then leaves you alone
  even if you never reach the last step, and that "Don't show again" silences
  every walkthrough rather than only the one on screen: an administrator who
  says no on the dashboard then meets four more, one per view, on their way
  around the app.

  Also that every step points at something that exists. A step whose target has
  been renamed still shows its card, with the ring pointing nowhere — it looks
  like the app, not like a broken tour, so nobody reports it.
*/

import fs from 'fs';
import { JSDOM } from 'jsdom';

const html = fs.readFileSync(new URL('../templates/dashboard.html', import.meta.url), 'utf8');

let failures = 0;
const ok = (c, m) => { console.log((c ? '  ok   ' : '  FAIL ') + m); if (!c) failures++; };

const grab = (name) => {
  let i = html.indexOf(`function ${name}(`);
  if (i < 0) throw new Error('not found: ' + name);
  if (html.slice(i - 6, i) === 'async ') i -= 6;
  let p = 0, after = -1;
  for (let k = html.indexOf('(', i); k < html.length; k++) {
    if (html[k] === '(') p++;
    else if (html[k] === ')' && --p === 0) { after = k + 1; break; }
  }
  let d = 0;
  for (let k = html.indexOf('{', after); k < html.length; k++) {
    if (html[k] === '{') d++;
    else if (html[k] === '}' && --d === 0) return html.slice(i, k + 1);
  }
};

function boot() {
  const dom = new JSDOM('<!doctype html><body></body>', { runScripts: 'outside-only' });
  const w = dom.window;
  // A plain stand-in rather than patching jsdom's Storage, whose methods are
  // not writable — assigning to them throws a bare DOMException that says
  // nothing about where it came from.
  const store = {};
  Object.defineProperty(w, 'localStorage', {
    configurable: true,
    value: {
      setItem: (k, v) => { store[k] = String(v); },
      getItem: (k) => (k in store ? store[k] : null),
      removeItem: (k) => { delete store[k]; },
    },
  });

  // Every tour opens on a timer. Reading the counter straight after calling
  // maybeStart… compared 0 with 0 and passed no matter what the code did —
  // which is how a mutation that made one tour ignore the off switch went
  // unnoticed. Run the callback now so the count means something.
  Object.defineProperty(w, 'setTimeout', {
    configurable: true,
    value: (fn) => { fn(); return 0; },
  });

  w.eval(`
    ${grab('_tourRemember')}
    ${grab('_tourRemembers')}
    ${grab('toursAreOff')}
    ${grab('turnToursOff')}
    ${grab('maybeStartTour')}
    ${grab('maybeStartCalendarTour')}
    ${grab('maybeStartPeopleTour')}
    ${grab('maybeStartRegionsTour')}
    ${grab('maybeStartMoveInsTour')}
    const TOURS_OFF = 'atlasToursOff_v1';
    var opened = [];
    function startTour() { opened.push('main'); }
    function startCalendarTour() { opened.push('calendar'); }
    function startPeopleTour() { opened.push('people'); }
    function startRegionsTour() { opened.push('regions'); }
    function startMoveInsTour() { opened.push('moveins'); }
    function endTour() {}
  `);
  return {
    w, store,
    openAll() {
      w.maybeStartTour(); w.maybeStartCalendarTour(); w.maybeStartPeopleTour();
      w.maybeStartRegionsTour(); w.maybeStartMoveInsTour();
      // They all open on a timer.
      const pending = w.eval('opened');
      return pending;
    },
  };
}

console.log('\nIt opens once');
{
  const { w, store } = boot();
  w.maybeStartTour();
  ok(store['atlasTourSeen_v2'] === '1',
     'starting is what marks it, not finishing — a reload mid-tour used to bring it back');

  const before = w.eval('opened.length');
  w.maybeStartTour();
  w.maybeStartTour();
  ok(w.eval('opened.length') === before, 'and it does not open again');
}

console.log('\nEven if you never reach the last step');
{
  // The exact sequence that was happening: it opens, the person closes the
  // tab, and the next visit starts over.
  const first = boot();
  first.w.maybeStartTour();
  const carried = { ...first.store };

  const second = boot();
  Object.assign(second.store, carried);   // same browser, new page load
  const before = second.w.eval('opened.length');
  second.w.maybeStartTour();
  ok(second.w.eval('opened.length') === before,
     'a second visit in the same browser is left alone');
}

console.log('\n"Don\'t show again" means all of them');
{
  const { w } = boot();
  w.turnToursOff();
  const opened = [];
  w.maybeStartTour(); w.maybeStartCalendarTour(); w.maybeStartPeopleTour();
  w.maybeStartRegionsTour(); w.maybeStartMoveInsTour();
  ok(w.eval('opened').length === 0,
     'no walkthrough opens on its own — not the four an administrator meets view by view');

  ok(/onclick="turnToursOff\(\)"/.test(html), 'and the button is on the card');
  ok(/Don't show again/.test(html), 'saying so in words');
}

console.log('\nHelp still works after saying no');
{
  // Turning them off must silence the ones that open themselves, not the one
  // you go looking for.
  const ctx = grab('contextHelp');
  ok(!/toursAreOff/.test(ctx),
     'the Help button does not check the flag, so it always opens');
  ok(/id="headerHelpBtn"[^>]*onclick="contextHelp\(\)"/.test(html),
     'and there is a Help button to press');
}

/* Where the "every step points at something" check went:

   the sidebar builds its items in a Jinja loop, so half the targets are not
   literal anywhere in a template and a static parse reported all of them as
   missing — a wall of noise nobody would read twice. It is in
   tests/test_tour.py now, against the page as Flask actually renders it,
   which is the only place the question can be answered honestly. */

console.log('\nThe steps describe what is actually there now');
{
  const admin = html.slice(html.indexOf('const TOUR_STEPS'), html.indexOf('function startTour'));
  ok(!/Clinical\/Ops\/Sales routing/.test(admin),
     'Settings no longer describes the three fixed routes that were merged away');
  ok(/Raise an issue/.test(admin), 'the + explains both of its actions');
  ok(/Keep this on our side/.test(admin), 'including the one the community cannot see');
  ok(/did not finish/.test(admin), 'and an unfinished visit is explained');
}

console.log(failures ? `\n${failures} failure(s)` : '\nIt asks once, and takes no for an answer.');
process.exit(failures ? 1 : 0);
