/*
  "It looks like you're at …" on the visit form, run with a fake GPS.

  Gabriel's idea: open Excellence in a community's lobby and have it offer
  that community instead of a list of seven, or thirty-nine. The server puts
  the positions of the person's own communities in the page
  (test_nearby_community.py); this is everything after that — the distance,
  the question, and that answering it picks the right building and nothing
  else.
*/

import fs from 'fs';
import { JSDOM } from 'jsdom';

const html = fs.readFileSync(new URL('../templates/reporte.html', import.meta.url), 'utf8');

let failures = 0;
const ok = (c, m) => { console.log((c ? '  ok   ' : '  FAIL ') + m); if (!c) failures++; };

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
const constant = (name) => {
  const m = html.match(new RegExp(`const ${name} = ([^;]+);`));
  if (!m) throw new Error(`no constant ${name}`);
  return `const ${name} = ${m[1]};`;
};

// Real positions, a few hundred metres to tens of kilometres apart.
const PLACES = [
  { community: 'Legacy Ridge at Buckhead, Atlanta', lat: 33.8466, lng: -84.3672 },
  { community: "The Oscar at Georgetown", lat: 30.6327, lng: -97.6772 },
  { community: "Angie's Place", lat: 33.8480, lng: -84.3660 },   // ~190 m from Legacy Ridge
  { community: 'Far Away', lat: 28.5600, lng: -81.5400 },
];
const AT_LEGACY = { lat: 33.8466, lng: -84.3672 };
const AT_OSCAR = { lat: 30.6330, lng: -97.6775 };            // ~40 m off the pin
const NOWHERE = { lat: 35.0, lng: -90.0 };

function world({ here = AT_OSCAR, accuracy = 20, places = PLACES, deny = false,
                 options = PLACES.map(p => p.community), slow = false,
                 permission = 'granted', permissionsApi = true, dismissed = false } = {}) {
  const opts = options.map(o => `<option value="${o.replace(/"/g, '&quot;')}">${o}</option>`).join('');
  const dom = new JSDOM(`<!doctype html><body>
    <button id="nearbyFind" hidden></button>
    <div id="nearbySuggest" hidden></div>
    <select id="communitySelect"><option value="">— Select —</option>${opts}</select>
    </body>`, { runScripts: 'outside-only', url: 'https://standards.example/reporte' });
  const w = dom.window;
  let callback = null;
  let asks = 0;
  if (permissionsApi) {
    Object.defineProperty(w.navigator, 'permissions', {
      value: { query: async () => ({ state: permission }) },
    });
  }
  if (dismissed) w.localStorage.setItem('atlasNearbyAskDismissed', '1');
  Object.defineProperty(w.navigator, 'geolocation', {
    value: {
      getCurrentPosition(okFn, errFn) {
        asks++;
        const go = () => deny ? errFn({ code: 1 })
          : okFn({ coords: { latitude: here.lat, longitude: here.lng, accuracy } });
        if (slow) callback = go; else go();
      },
    },
  });
  w.eval(`
    var changed = 0;
    function onCommunityChange() { changed++; }
    ${constant('NEAR_METRES')}
    ${constant('NEAR_SLACK_MAX')}
    const COMMUNITY_PLACES = ${JSON.stringify(places)};
    ${grab('metresBetween')}
    ${grab('communitiesNear')}
    ${constant('NEARBY_DISMISSED_KEY')}
    ${grab('locationPermission')}
    ${grab('nearbyAskDismissed')}
    ${grab('offerNearbyCommunity')}
    ${grab('showNearbyAsk')}
    ${grab('nearbySay')}
    ${grab('suggestNearbyCommunity')}
    ${grab('showNearbySuggestion')}
  `);
  w.release = () => callback && callback();
  w.asks = () => asks;
  return w;
}

const box = (w) => w.document.getElementById('nearbySuggest');
const buttons = (w) => [...box(w).querySelectorAll('button')];
const sel = (w) => w.document.getElementById('communitySelect');

console.log('\nThe distance is right');
{
  const w = world();
  const d = w.metresBetween(PLACES[0], PLACES[2]);
  ok(d > 150 && d < 230, `two pins ~190 m apart measure ${Math.round(d)} m`);
  const far = w.metresBetween(PLACES[0], PLACES[1]);
  ok(far > 1_295_000 && far < 1_306_000, `Atlanta to Georgetown TX is ~1,301 km by great circle (${Math.round(far / 1000)} km)`);
}

console.log('\nStanding at one community');
{
  const w = world({ here: AT_OSCAR });
  w.suggestNearbyCommunity();
  ok(box(w).hidden === false, 'the suggestion appears');
  ok(/It looks like you're at The Oscar at Georgetown/.test(box(w).textContent),
     `it names the building (${box(w).textContent.trim().slice(0, 60)})`);
  ok(sel(w).value === '', 'and selects nothing on its own — picking takes a tap');
  ok(w.changed === 0, 'and loads no visit on its own');

  buttons(w).find(b => b.className === 'nearby-go').onclick();
  ok(sel(w).value === 'The Oscar at Georgetown', 'Start here picks it');
  ok(w.changed === 1, 'and loads its visit the way choosing it from the list does');
  ok(box(w).hidden === true, 'and the question goes away');
}

console.log('\nTwo communities close together');
{
  const w = world({ here: AT_LEGACY });
  w.suggestNearbyCommunity();
  const names = buttons(w).filter(b => b.className === 'nearby-go').map(b => b.textContent);
  ok(names.length === 2, `both are offered (${names.join(' | ')})`);
  ok(names[0] === 'Legacy Ridge at Buckhead, Atlanta', 'nearest first');
  ok(/more than one/.test(box(w).textContent), 'and it asks which, rather than guessing');
  buttons(w).find(b => b.textContent === "Angie's Place").onclick();
  ok(sel(w).value === "Angie's Place", 'an apostrophe in a name does not break the button');
}

console.log('\nNearest first, whatever order the list is in');
{
  // Standing at Angie's, which comes after Legacy Ridge in the data.
  const w = world({ here: { lat: 33.8480, lng: -84.3660 } });
  w.suggestNearbyCommunity();
  const names = buttons(w).filter(b => b.className === 'nearby-go').map(b => b.textContent);
  ok(names[0] === "Angie's Place", `the one you are standing in leads (${names.join(' | ')})`);
}

console.log('\nNowhere near one');
{
  const w = world({ here: NOWHERE });
  w.suggestNearbyCommunity();
  ok(box(w).hidden === true, 'nothing is shown');
  ok(sel(w).value === '', 'and the list is as it was');
}

console.log('\nJust outside the radius is outside');
{
  // ~550 m north of the Oscar pin, with a good fix.
  const w = world({ here: { lat: 30.6377, lng: -97.6772 }, accuracy: 10 });
  w.suggestNearbyCommunity();
  ok(box(w).hidden === true, 'half a kilometre away is not "at" a community');
}

console.log('\nA poor fix is allowed some slack, but not unlimited');
{
  // ~400 m away: outside 300 m, inside 300 + 150 of reported uncertainty.
  const here = { lat: 30.6363, lng: -97.6772 };
  const fuzzy = world({ here, accuracy: 150 });
  fuzzy.suggestNearbyCommunity();
  ok(fuzzy.document.getElementById('nearbySuggest').hidden === false,
     'a phone indoors that says ±150 m still finds the building');
  const wild = world({ here: { lat: 30.6417, lng: -97.6772 }, accuracy: 5000 });
  wild.suggestNearbyCommunity();
  ok(wild.document.getElementById('nearbySuggest').hidden === true,
     'but a ±5 km guess does not turn a kilometre into "here"');
}

console.log('\nLocation refused');
{
  const w = world({ deny: true });
  w.suggestNearbyCommunity();
  ok(box(w).hidden === true, 'nothing is shown, and nothing breaks');
}

console.log('\nThey picked one while the phone was still looking');
{
  const w = world({ here: AT_OSCAR, slow: true });
  w.suggestNearbyCommunity();
  sel(w).value = 'Far Away';
  w.release();
  ok(box(w).hidden === true, 'their choice is not second-guessed');
  ok(sel(w).value === 'Far Away', 'and stays theirs');
}

console.log('\nOnly what is in their list');
{
  // A position for a community that is not in this person's dropdown.
  const w = world({ here: AT_OSCAR, options: ['Far Away', 'Legacy Ridge at Buckhead, Atlanta'] });
  w.suggestNearbyCommunity();
  ok(box(w).hidden === true, 'a building they cannot visit is never suggested');
}

console.log('\nNot now');
{
  const w = world({ here: AT_OSCAR });
  w.suggestNearbyCommunity();
  buttons(w).find(b => b.className === 'nearby-no').onclick();
  ok(box(w).hidden === true && sel(w).value === '' && w.changed === 0,
     'closes the question and leaves the form untouched');
}

console.log('\nNames are text');
{
  const w = world({ here: AT_OSCAR, places: [{ community: '<img src=x onerror=1>', lat: AT_OSCAR.lat, lng: AT_OSCAR.lng }],
                    options: ['<img src=x onerror=1>'] });
  w.suggestNearbyCommunity();
  ok(box(w).querySelector('img') === null, 'a name cannot become markup');
}

console.log('\nIt is asked only when no community was named');
{
  const i = html.indexOf("const asked = new URLSearchParams(location.search).get('community');");
  const block = html.slice(i, i + 700);
  ok(/\} else \{\s*\/\/[^\n]*\n\s*offerNearbyCommunity\(\);/.test(block),
     'resuming an unfinished visit for a named community does not ask where they are');
}

// ---------------------------------------------------- explain, then ask

const tick = () => new Promise(r => setTimeout(r, 0));
const find = (w) => w.document.getElementById('nearbyFind');

console.log('\nNot asked yet: our card first, the phone\'s prompt only on a tap');
{
  const w = world({ permission: 'prompt' });
  await w.offerNearbyCommunity();
  ok(w.asks() === 0, 'opening the form does not trigger the location prompt');
  ok(box(w).hidden === false, 'the card is shown instead');
  ok(/At a community\?/.test(box(w).textContent), 'saying what it is for');
  ok(/stays on your phone and is never saved/.test(box(w).textContent),
     'and that the location goes nowhere — the reason people would refuse');
  buttons(w).find(b => b.textContent === 'Find my community').onclick();
  ok(w.asks() === 1, 'tapping Find is what asks the phone');
  ok(/It looks like you're at The Oscar at Georgetown/.test(box(w).textContent),
     'and the answer replaces the card');
}

console.log('\nAlready allowed: straight to the answer');
{
  const w = world({ permission: 'granted' });
  await w.offerNearbyCommunity();
  ok(w.asks() === 1, 'no card, the phone is asked at once');
  ok(/It looks like you're at/.test(box(w).textContent), 'and the suggestion appears');
}

console.log('\nRefused before: nothing, not even the link');
{
  const w = world({ permission: 'denied' });
  await w.offerNearbyCommunity();
  ok(w.asks() === 0 && box(w).hidden === true, 'no card and no prompt');
  ok(find(w).hidden === true, 'and no link that could only lead to a refusal');
}

console.log('\nA browser that cannot say counts as not yet asked');
{
  const w = world({ permissionsApi: false });
  await w.offerNearbyCommunity();
  ok(w.asks() === 0 && box(w).hidden === false, 'the card, not the prompt');
}

console.log('\nClosing the card is remembered, and the link stays');
{
  const w = world({ permission: 'prompt' });
  await w.offerNearbyCommunity();
  w.document.querySelector('.nearby-x').onclick();
  ok(box(w).hidden === true, 'the card closes');
  ok(w.localStorage.getItem('atlasNearbyAskDismissed') === '1', 'and the phone remembers');
  ok(find(w).hidden === false, 'the small link is still there');
  find(w).onclick();
  ok(w.asks() === 1, 'and still works');

  const again = world({ permission: 'prompt', dismissed: true });
  await again.offerNearbyCommunity();
  ok(again.document.getElementById('nearbySuggest').hidden === true,
     'next time the card is not shown');
  ok(again.document.getElementById('nearbyFind').hidden === false, 'only the link');
}

console.log('\nA tap always gets an answer');
{
  const nowhere = world({ permission: 'prompt', here: NOWHERE });
  await nowhere.offerNearbyCommunity();
  buttons(nowhere).find(b => b.textContent === 'Find my community').onclick();
  ok(/None of your communities/.test(nowhere.document.getElementById('nearbySuggest').textContent),
     'nowhere near one: it says so, rather than going quiet');

  const refused = world({ permission: 'prompt', deny: true });
  await refused.offerNearbyCommunity();
  buttons(refused).find(b => b.textContent === 'Find my community').onclick();
  ok(/Location is turned off/.test(refused.document.getElementById('nearbySuggest').textContent),
     'refused at the prompt: it says so');
  ok(refused.document.getElementById('nearbyFind').hidden === true,
     'and the link goes, since it can only fail now');

  const quiet = world({ permission: 'granted', here: NOWHERE });
  await quiet.offerNearbyCommunity();
  ok(quiet.document.getElementById('nearbySuggest').hidden === true,
     'but unasked, nowhere near one stays silent');
}

console.log(failures ? `\n${failures} failure(s)` : '\nThe form knows which building you are in.');
process.exit(failures ? 1 : 0);
