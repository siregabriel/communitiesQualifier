/*
  The map switch, run rather than read.

  The Python tests cover the data: who gets which communities, what colour a
  band is, what happens to a community with no position. What they cannot
  cover is the part that actually happens in a browser — whether pressing Map
  puts the map on screen and takes the list off it.

  That gap is not theoretical. `gallery.hidden = true` looks like it hides the
  gallery, and it does not: the [hidden] attribute hides an element through a
  browser default rule, and `.gallery { display: grid }` is an author rule,
  which wins. The list would have stayed exactly where it was with the map
  underneath it, and every source-reading test would still have passed.

  So this loads the real stylesheet out of the template, runs the real
  functions, and looks at what a browser would compute.
*/

import fs from 'fs';
import { JSDOM } from 'jsdom';

const html = fs.readFileSync(new URL('../templates/dashboard.html', import.meta.url), 'utf8');

let failures = 0;
const ok = (c, m) => { console.log((c ? '  ok   ' : '  FAIL ') + m); if (!c) failures++; };

/* Everything between the first <style> and its close. The map rules and the
   .gallery rule both live there, and it is their argument with each other
   that this is about. */
const styles = (() => {
  const i = html.indexOf('<style>');
  return html.slice(i + 7, html.indexOf('</style>', i));
})();

const grab = (name) => {
  let i = html.indexOf(`function ${name}(`);
  if (i < 0) throw new Error(`no such function: ${name}`);
  if (html.slice(i - 6, i) === 'async ') i -= 6;
  let depth = 0;
  for (let k = html.indexOf('{', i); k < html.length; k++) {
    if (html[k] === '{') depth++;
    else if (html[k] === '}' && --depth === 0) return html.slice(i, k + 1);
  }
  throw new Error(`unbalanced braces in ${name}`);
};

const ROWS = [
  { community: 'Madison at Ocoee, Ocoee', lat: 28.56, lng: -81.54, city: 'Ocoee',
    state: 'FL', verified: false, score: 95, last_visit: '2026-09-20T10:00:00',
    days_since: 4, band: 'good', open_items: 0 },
  { community: 'Madison at Oviedo, Oviedo', lat: 28.67, lng: -81.20, city: 'Oviedo',
    state: 'FL', verified: false, score: 60, last_visit: '2026-09-18T10:00:00',
    days_since: 6, band: 'poor', open_items: 4 },
  { community: 'The Goldton at Stuart', lat: 27.19, lng: -80.25, city: 'Stuart',
    state: 'FL', verified: false, score: 100, last_visit: '2026-05-01T10:00:00',
    days_since: 146, band: 'stale', open_items: 1 },
];

function makeWorld({ rows = ROWS, unplaced = [], unverified = [] } = {}) {
  const dom = new JSDOM(`<!doctype html><html><head><style>${styles}</style></head>
    <body>
      <div id="cmapSwitch" class="cmap-switch" hidden>
        <button class="cmap-tab is-on" data-layout="list"></button>
        <button class="cmap-tab" data-layout="map"></button>
      </div>
      <div class="gallery" id="gallery"></div>
      <div id="cmapWrap" class="cmap-wrap" hidden>
        <div id="cmapNote" class="cmap-note" hidden></div>
        <div id="communityMap" class="cmap"></div>
      </div>
    </body></html>`, { runScripts: 'outside-only', pretendToBeVisual: true });
  const w = dom.window;

  // A Leaflet that records instead of drawing.
  const made = [];
  const fakeMap = {
    fitBounds() { this.fitted = true; return this; },
    setView() { this.viewed = true; return this; },
    invalidateSize() { this.sized = true; },
  };
  w.L = {
    map: () => fakeMap,
    tileLayer: () => ({ addTo: () => ({}) }),
    layerGroup: () => ({ addTo: () => ({}), remove() { this.removed = true; } }),
    latLngBounds: (pts) => ({ pad: () => pts }),
    circleMarker: (latlng, opts) => {
      const m = {
        latlng, opts, popup: '', handlers: {},
        bindPopup(h) { this.popup = h; return this; },
        on(evt, fn) { this.handlers[evt] = fn; return this; },
        addTo() { made.push(m); return this; },
        // Open the popup the way Leaflet would, and hand back the button so
        // a test can press it.
        openPopup(doc) {
          const host = doc.createElement('div');
          host.innerHTML = this.popup;
          this.handlers.popupopen({ popup: { getElement: () => host } });
          return host.querySelector('.cmap-pop-go');
        },
      };
      return m;
    },
  };
  w.made = made;
  w.fakeMap = fakeMap;
  w.isAdmin = false;
  w.currentUserCommunities = ['a', 'b'];
  w.eval(`
    var _payload = ${JSON.stringify({ status: 'success', communities: rows,
                                      unplaced, unverified, stale_after_days: 60 })};
    function fetch() { return Promise.resolve({ json: () => Promise.resolve(_payload) }); }
    function escapeHtml(s) { return String(s == null ? '' : s); }
    function escapeHtmlForAttr(s) { return String(s == null ? '' : s); }
    function formatDate(s) { return String(s).slice(0, 10); }
    ${grab('ensureLeaflet')}
    ${grab('updateCommunityLayoutSwitch')}
    ${grab('setCommunityLayout')}
    ${grab('cmapNote')}
    ${grab('renderCommunityMap')}
    var _cmapLayout = 'list', _cmap = null, _cmapLayer = null, _cmapLoaded = true;
    var CMAP_COLOURS = { good: '#0f8a5f', watch: '#d97706', poor: '#dc2626' };
  `);
  return w;
}

const shown = (w, id) => w.getComputedStyle(w.document.getElementById(id)).display;

console.log('\nPressing Map actually swaps them');
{
  const w = makeWorld();
  ok(shown(w, 'gallery') !== 'none', 'the list starts visible');

  w.setCommunityLayout('map');
  ok(shown(w, 'gallery') === 'none',
     `the list is hidden (computed display: ${shown(w, 'gallery')})`);
  ok(shown(w, 'cmapWrap') !== 'none', 'and the map is not');

  w.setCommunityLayout('list');
  ok(shown(w, 'gallery') !== 'none', 'and back again');
  ok(shown(w, 'cmapWrap') === 'none', 'with the map put away');
}

console.log('\nThe switch is only offered to somebody who covers several');
{
  const w = makeWorld();
  w.currentUserCommunities = ['only one'];
  w.updateCommunityLayoutSwitch();
  ok(w.document.getElementById('cmapSwitch').hidden === true,
     'one community: no map on offer');

  w.currentUserCommunities = ['a', 'b', 'c'];
  w.updateCommunityLayoutSwitch();
  ok(w.document.getElementById('cmapSwitch').hidden === false, 'three: offered');

  const w2 = makeWorld();
  w2.currentUserCommunities = [];
  w2.isAdmin = true;
  w2.updateCommunityLayoutSwitch();
  ok(w2.document.getElementById('cmapSwitch').hidden === false,
     'an admin is offered it regardless');
}

console.log('\nA pin per community, coloured by what we know');
{
  const w = makeWorld();
  await w.renderCommunityMap();
  const made = w.made;
  ok(made.length === 3, `three pins (${made.length})`);

  const good = made[0], poor = made[1], stale = made[2];
  ok(good.opts.fillColor === '#0f8a5f', 'a 95 is green');
  ok(poor.opts.fillColor === '#dc2626', 'a 60 is red');

  ok(stale.opts.fillOpacity === 0 && stale.opts.fillColor === 'transparent',
     'a four-month-old 100 is hollow, not filled');
  ok(stale.opts.color === '#94a3b8', 'and ringed in grey rather than green');
  ok(good.opts.fillOpacity > 0, 'while a fresh one is solid');
}

console.log('\nWhat a pin says when you open it');
{
  const w = makeWorld();
  await w.renderCommunityMap();
  const [good, poor, stale] = w.made;

  ok(/Madison at Ocoee/.test(good.popup), 'it names the community');
  ok(/95%/.test(good.popup), 'and the score');
  ok(/4 open items/.test(poor.popup), 'and how much is open');
  ok(/1 open item\b/.test(stale.popup), 'with the singular when there is one');
  ok(/not visited recently/.test(stale.popup),
     'and says outright that a stale one is stale');
  ok(!/not visited recently/.test(good.popup), 'while a fresh one does not');
  // Pressed for real, because the handler is attached in JavaScript now
  // rather than written into an attribute — there is no string to grep.
  let opened = null;
  w.eval('function openSlidePanel(c, id) { opened = [c, id]; }');
  w.opened = null;
  const btn = good.openPopup(w.document);
  ok(!!btn, 'the popup has a button');
  btn.onclick();
  ok(w.opened && w.opened[0] === 'Madison at Ocoee, Ocoee',
     `it opens that community (${w.opened && w.opened[0]})`);
  ok(w.opened && w.opened[1] === undefined,
     'with no visit id, because a pin stands for the place');

  ok(!/onclick=/.test(good.popup),
     'and the name is never written into an attribute — an apostrophe in a '
     + 'community name would have been parsed as code');
}

console.log('\nThe hidden attribute is made to actually work');
{
  /* Read rather than run, and deliberately so. In a browser the [hidden]
     default rule loses to `.gallery { display: grid }`, so setting .hidden
     does nothing — but jsdom resolves the cascade by document order instead
     of specificity and reports display:none either way. It cannot tell the
     broken version from the fixed one, which is exactly why the test above
     passed before this rule existed. So: check the rule is there. */
  ok(/\.gallery\[hidden\]/.test(styles),
     'the gallery has its own [hidden] rule');
  ok(/\.cmap-wrap\[hidden\]/.test(styles), 'and so does the map');
  const i = styles.indexOf('.gallery[hidden]');
  const j = styles.indexOf('.gallery {');
  ok(i > j, 'and it comes after the rule it has to beat');
}

console.log('\nWhat is missing is said above the map');
{
  const w = makeWorld({ unplaced: ['Tribute at The Glen'], unverified: ['a', 'b'] });
  await w.renderCommunityMap();
  const note = w.document.getElementById('cmapNote');
  ok(note.hidden === false, 'the note is shown');
  ok(/1 not on the map/.test(note.innerHTML), 'it counts them');
  ok(/Tribute at The Glen/.test(note.innerHTML), 'and names them');
  ok(!/proposed/.test(note.innerHTML),
     'and does not nag about unconfirmed positions, which never change');

  const clean = makeWorld();
  await clean.renderCommunityMap();
  ok(clean.document.getElementById('cmapNote').hidden === true,
     'and stays out of the way when there is nothing to report');
}

console.log('\nAn empty map does not crash');
{
  const w = makeWorld({ rows: [] });
  await w.renderCommunityMap();
  ok(w.made.length === 0, 'no pins');
  ok(w.fakeMap.viewed === true, 'and it falls back to a fixed view');
}

console.log(failures ? `\n${failures} failure(s)` : '\nThe map goes where the list was.');
process.exit(failures ? 1 : 0);
