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

const MAPS = { key: 'test-key', map_id: 'test-map-id' };

function makeWorld({ rows = ROWS, unplaced = [], unverified = [], renamed_from = {},
                     maps = MAPS, google = true } = {}) {
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

  /* A Google Maps that records instead of drawing. Only the calls the page
     makes are here, shaped the way the real API takes them: importLibrary
     per library, AdvancedMarkerElement with an element for content and a
     'gmp-click' listener, one InfoWindow opened against a pin. */
  const made = [];
  const fakeMap = { opts: null };
  const info = { content: null, opened: null, closed: 0 };
  const libs = {
    maps: {
      Map: function (host, opts) {
        fakeMap.host = host; fakeMap.opts = opts;
        fakeMap.fitBounds = (b, pad) => { fakeMap.fitted = b.points; fakeMap.pad = pad; };
        fakeMap.setCenter = (c) => { fakeMap.center = c; };
        fakeMap.setZoom = (z) => { fakeMap.zoom = z; };
        return fakeMap;
      },
      InfoWindow: function () {
        info.setContent = (el) => { info.content = el; };
        info.open = (o) => { info.opened = o; };
        info.close = () => { info.closed++; };
        return info;
      },
    },
    marker: {
      AdvancedMarkerElement: function (opts) {
        const m = { opts, map: opts.map, handlers: {},
                    addListener(evt, fn) { this.handlers[evt] = fn; } };
        made.push(m);
        return m;
      },
    },
    core: {
      LatLngBounds: function () {
        this.points = [];
        this.extend = (p) => { this.points.push(p); };
      },
    },
  };
  if (google) {
    w.google = { maps: { importLibrary: async (name) => libs[name] } };
  }
  w.made = made;
  w.fakeMap = fakeMap;
  w.info = info;
  w.isAdmin = false;
  w.currentUserCommunities = ['a', 'b'];
  w.eval(`
    var _payload = ${JSON.stringify({ status: 'success', communities: rows,
                                      unplaced, unverified, renamed_from, maps,
                                      stale_after_days: 60 })};
    var fetched = 0;
    function fetch() { fetched++; return Promise.resolve({ json: () => Promise.resolve(_payload) }); }
    function escapeHtml(s) { return String(s == null ? '' : s); }
    function escapeHtmlForAttr(s) { return String(s == null ? '' : s); }
    function formatDate(s) { return String(s).slice(0, 10); }
    ${grab('ensureGoogleMaps')}
    ${grab('updateCommunityLayoutSwitch')}
    ${grab('setCommunityLayout')}
    ${grab('cmapNote')}
    ${grab('cmapPin')}
    ${grab('cmapPopup')}
    ${grab('renderCommunityMap')}
    var _cmapLayout = 'list', _cmap = null, _cmapPins = [], _cmapInfo = null, _cmapLoading = null;
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

  const [good, poor, stale] = made.map(m => m.opts.content);
  ok(good.style.background === 'rgb(15, 138, 95)', `a 95 is green (${good.style.background})`);
  ok(poor.style.background === 'rgb(220, 38, 38)', `a 60 is red (${poor.style.background})`);

  ok(/transparent/.test(stale.style.background),
     `a four-month-old 100 is hollow, not filled (${stale.style.background})`);
  ok(stale.classList.contains('is-stale'), 'and drawn as the ring');
  ok(stale.style.borderColor === 'rgb(148, 163, 184)',
     `ringed in grey rather than green (${stale.style.borderColor})`);
  ok(!good.classList.contains('is-stale'), 'while a fresh one is solid');

  ok(made[0].opts.position.lat === 28.56 && made[0].opts.position.lng === -81.54,
     'each at its own position');
  ok(made[0].opts.map === w.fakeMap, 'on the map, not floating');
  ok(made[0].opts.title === 'Madison at Ocoee, Ocoee', 'named, for a screen reader and a hover');
}

console.log('\nThe map is the one Gabriel asked for');
{
  const w = makeWorld();
  await w.renderCommunityMap();
  const o = w.fakeMap.opts;
  ok(o.mapId === 'test-map-id', 'built with the Map ID, which Advanced Markers require');
  ok(o.mapTypeControl === true, 'with the Map / Satellite switch');
  ok(o.streetViewControl === true, 'and Street View');
  ok(o.gestureHandling === 'cooperative',
     'and one finger still scrolls the page on a phone');
  ok(w.fakeMap.fitted && w.fakeMap.fitted.length === 3,
     'framed around every pin');
}

console.log('\nWhat a pin says when you open it');
{
  const w = makeWorld();
  await w.renderCommunityMap();
  const [good, poor, stale] = w.made;
  const open = (m) => { m.handlers['gmp-click'](); return w.info.content; };

  const g = open(good);
  ok(w.info.opened && w.info.opened.anchor === good, 'the popup opens on the pin that was pressed');
  ok(/Madison at Ocoee/.test(g.innerHTML), 'it names the community');
  ok(/95%/.test(g.innerHTML), 'and the score');
  ok(/4 open items/.test(open(poor).innerHTML), 'and how much is open');
  const s = open(stale).innerHTML;
  ok(/1 open item\b/.test(s), 'with the singular when there is one');
  ok(/not visited recently/.test(s), 'and says outright that a stale one is stale');
  ok(!/not visited recently/.test(g.innerHTML), 'while a fresh one does not');

  // Pressed for real, because the handler is attached in JavaScript rather
  // than written into an attribute — there is no string to grep.
  w.eval('function openSlidePanel(c, id) { opened = [c, id]; }');
  w.opened = null;
  const btn = open(good).querySelector('.cmap-pop-go');
  ok(!!btn, 'the popup has a button');
  btn.onclick();
  ok(w.opened && w.opened[0] === 'Madison at Ocoee, Ocoee',
     `it opens that community (${w.opened && w.opened[0]})`);
  ok(w.opened && w.opened[1] === undefined,
     'with no visit id, because a pin stands for the place');
  ok(!/onclick=/.test(g.innerHTML),
     'and the name is never written into an attribute — an apostrophe in a '
     + 'community name would have been parsed as code');
}

console.log('\nOpening the map twice does not stack the pins');
{
  const w = makeWorld();
  await w.renderCommunityMap();
  const first = w.made.slice();
  await w.renderCommunityMap();
  ok(first.every(m => m.map === null), 'the old pins are taken off the map');
  ok(w.made.filter(m => m.map !== null).length === 3, 'and only the new three remain');
}

console.log('\nNo key, no Google');
{
  /* The code can reach the server before the key does. Then the page has to
     say the map is not set up — not load Google with an empty key, which
     shows a grey box and a watermark and explains nothing. */
  const w = makeWorld({ maps: { key: '', map_id: '' }, google: false });
  let scripts = 0;
  const realAppend = w.document.head.appendChild.bind(w.document.head);
  w.document.head.appendChild = (el) => { scripts++; return realAppend(el); };
  await w.renderCommunityMap();
  const note = w.document.getElementById('cmapNote');
  ok(note.hidden === false && /not set up/.test(note.innerHTML),
     'the note says the map is not set up');
  ok(scripts === 0, 'and no script is requested from Google');
  ok(w.made.length === 0, 'and nothing is drawn');

  const half = makeWorld({ maps: { key: 'k', map_id: '' }, google: false });
  await half.renderCommunityMap();
  ok(/not set up/.test(half.document.getElementById('cmapNote').innerHTML),
     'a key without a Map ID is not set up either — the pins would refuse to draw');
}

console.log('\nGoogle is asked for once, with the key it was given');
{
  const w = makeWorld({ google: false });
  const added = [];
  w.document.head.appendChild = (el) => { added.push(el); return el; };
  const a = w.ensureGoogleMaps('abc&v=1');
  const b = w.ensureGoogleMaps('abc&v=1');
  ok(added.length === 1, `one script tag, however often it is asked (${added.length})`);
  ok(a === b, 'and every caller waits on the same load');
  const src = added[0].src;
  ok(src.startsWith('https://maps.googleapis.com/maps/api/js?'), 'from Google');
  // An ampersand that reached the URL raw would end the key and start a
  // parameter of its own; a space would not have shown it, jsdom fixes those.
  ok(/key=abc%26v%3D1&/.test(src), 'with the key, escaped');
  ok(/callback=__cmapReady/.test(src) && typeof w.__cmapReady === 'function',
     'and a callback that resolves it');
  w.__cmapReady();
  ok(await a === true, 'which it does');
  ok(typeof w.gm_authFailure === 'function',
     'and a refused key is reported on the page instead of a silent grey box');
  w.gm_authFailure();
  ok(/refused the map key/.test(w.document.getElementById('cmapNote').innerHTML),
     'in words');

  const f = makeWorld({ google: false });
  const tags = [];
  f.document.head.appendChild = (el) => { tags.push(el); return el; };
  const p = f.ensureGoogleMaps('k');
  tags[0].onerror();
  ok(await p === false, 'a failed download says so');
  f.ensureGoogleMaps('k');
  ok(tags.length === 2, 'and the next attempt tries again rather than inheriting it');
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

console.log('\nWhy one went missing');
{
  /* A rename carries a community across every store that keys on its name.
     It does not carry the map's reference file, which ships with the code —
     so the position stays behind under the old name. Saying which name is the
     difference between a mystery and a one-line edit. */
  const w = makeWorld({
    unplaced: ['The Georgian at Lakeside'],
    renamed_from: { 'The Georgian at Lakeside': 'Georgian Lakeside' },
  });
  await w.renderCommunityMap();
  const note = w.document.getElementById('cmapNote').innerHTML;

  ok(/1 not on the map/.test(note), 'it still counts what is missing');
  ok(/was renamed from/.test(note), 'and says a rename is why');
  ok(/Georgian Lakeside/.test(note), 'naming the name to look under');
  // Tolerant of the line break the template literal leaves in the markup:
  // the browser collapses it, and a test that does not is a test about
  // indentation rather than about what the sentence says.
  ok(/filed\s+under the old name/.test(note), 'and where the position actually is');

  const plain = makeWorld({ unplaced: ['Somewhere New'] });
  await plain.renderCommunityMap();
  const bare = plain.document.getElementById('cmapNote').innerHTML;
  ok(/Somewhere New/.test(bare), 'a community that was never renamed is still named');
  ok(!/renamed/.test(bare),
     'and gets no invented explanation — a guess here sends somebody hunting');
}

console.log('\nAn empty map does not crash');
{
  const w = makeWorld({ rows: [] });
  await w.renderCommunityMap();
  ok(w.made.length === 0, 'no pins');
  ok(w.fakeMap.zoom === 5 && w.fakeMap.center, 'and it falls back to a fixed view');
}

console.log('\nOne pin is not zoomed to the rooftop');
{
  const w = makeWorld({ rows: [ROWS[0]] });
  await w.renderCommunityMap();
  ok(!w.fakeMap.fitted, 'no fitBounds around a single point');
  ok(w.fakeMap.zoom === 12, 'a town-level zoom instead');
}

console.log(failures ? `\n${failures} failure(s)` : '\nThe map goes where the list was.');
process.exit(failures ? 1 : 0);
