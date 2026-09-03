/*
  Which button each role is offered, and whether the menu works.

  The condition read `!isAdmin && canRunVisits`. That was written when admin
  meant only the built-in account, and can_run_visits() is already false for
  that one — so the clause did nothing it was meant to do and one thing it was
  not: it hid the button from anybody holding the admin accessory on top of a
  real role. Greg is Corporate and admin. So is Gabriel. The feature shipped
  invisible to the two people most likely to use it, and it was found by one of
  them looking for it on his phone.

  So the table below is the point of this file: role and accessory in, button
  out.
*/

import fs from 'fs';
import { JSDOM } from 'jsdom';

const html = fs.readFileSync(new URL('../templates/dashboard.html', import.meta.url), 'utf8');

let failures = 0;
const ok = (c, m) => { console.log((c ? '  ok   ' : '  FAIL ') + m); if (!c) failures++; };

/* The block that decides, lifted out of loadUserInfo so the decision is run
   rather than re-typed here. */
const decision = (() => {
  const marker = 'const raiseBtn = document.getElementById(\'raiseItemBtn\');';
  const i = html.indexOf(marker);
  if (i < 0) throw new Error('the button block moved');
  const end = html.indexOf('\n\n', i);
  return html.slice(i, end);
})();

function shown({ isAdmin, canRunVisits, communities }) {
  const dom = new JSDOM(`<!doctype html><body>
    <button id="startVisitBtn" style="display:none"></button>
    <button id="raiseItemBtn" style="display:none"></button>
    <div class="fab-menu" id="fabMenu" hidden></div>
    <button id="fabMenuBtn" style="display:none"></button>
    </body>`, { runScripts: 'outside-only' });
  const w = dom.window;
  w.eval(`
    var isAdmin = ${isAdmin};
    var canRunVisits = ${canRunVisits};
    var data = { communities: ${JSON.stringify(communities)} };
    var startVisitBtn = document.getElementById('startVisitBtn');
    ${decision}
  `);
  const on = ['startVisitBtn', 'raiseItemBtn', 'fabMenuBtn']
    .filter(id => w.document.getElementById(id).style.display === 'flex');
  return on.length === 1 ? on[0] : (on.length ? on.join('+') : 'nothing');
}

const COMMS = ['Kelley Place, Enterprise'];

console.log('\nWho is offered what');
const table = [
  ['a regional',                    { isAdmin: false, canRunVisits: true,  communities: COMMS }, 'fabMenuBtn'],
  ['a corporate member',            { isAdmin: false, canRunVisits: true,  communities: COMMS }, 'fabMenuBtn'],
  ['a corporate member who is also an administrator',
                                    { isAdmin: true,  canRunVisits: true,  communities: COMMS }, 'fabMenuBtn'],
  ['an Executive Director',         { isAdmin: false, canRunVisits: false, communities: COMMS }, 'raiseItemBtn'],
  ['the built-in administrator',    { isAdmin: true,  canRunVisits: false, communities: [] },    'nothing'],
];
for (const [who, session, expected] of table) {
  const got = shown(session);
  ok(got === expected, `${who} gets ${expected} (${got})`);
}

console.log('\nThe accessory does not take the button away');
{
  // The bug, stated as the thing it broke.
  ok(shown({ isAdmin: true, canRunVisits: true, communities: COMMS })
     === shown({ isAdmin: false, canRunVisits: true, communities: COMMS }),
     'Corporate with and without the admin accessory are offered the same button');
}

console.log('\nThe menu opens, closes, and does something');
{
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

  const dom = new JSDOM(`<!doctype html><body>
    <div class="fab-menu" id="fabMenu" hidden></div>
    <button id="fabMenuBtn" aria-expanded="false"></button>
    </body>`, { runScripts: 'outside-only' });
  const w = dom.window;
  const went = [];
  w.eval(`
    ${grab('toggleFabMenu')}
    ${grab('fabPick')}
    var picked = [];
    function navigateToStartNewVisit() { picked.push('visit'); }
    function openRaiseItem() { picked.push('raise'); }
  `);

  const menu = w.document.getElementById('fabMenu');
  const btn = w.document.getElementById('fabMenuBtn');

  w.toggleFabMenu();
  ok(!menu.hidden, 'it opens');
  ok(btn.getAttribute('aria-expanded') === 'true', 'and says so to a screen reader');

  w.toggleFabMenu();
  ok(menu.hidden, 'and closes again on a second press');

  w.toggleFabMenu(true);
  w.fabPick('visit');
  ok(menu.hidden, 'picking closes it');
  ok(w.eval('picked').join() === 'visit', 'and starts a visit');

  w.toggleFabMenu(true);
  w.fabPick('raise');
  ok(w.eval('picked').join() === 'visit,raise', 'the other one raises an issue');

  // A menu that can only be dismissed by choosing is a trap on a phone.
  w.toggleFabMenu(true);
  w.toggleFabMenu(false);
  ok(menu.hidden, 'and it can be dismissed without choosing anything');
}

console.log('\nOn a phone, where the floating button is hidden');
{
  // The floating button carries class start-visit-btn, and a media query hides
  // every one of those below 768px because the tab bar owns the bottom of the
  // screen. So on mobile the only way in is the tab bar's +, which is a link
  // straight to Start Visit. Wyman asked for this from an iPhone.
  const head = html.slice(html.indexOf('<style>') + 7, html.indexOf('</style>'));
  const hides = /\.start-visit-btn:not\(#raiseItemBtn\)\s*\{[^}]*display:\s*none/.test(head);
  ok(hides, 'the floating button is still hidden at phone width (so the tab bar must work)');

  const tabbar = fs.readFileSync(new URL('../templates/mobile_tabbar.html', import.meta.url), 'utf8');
  ok(/id="mtabNew"/.test(tabbar), 'the tab bar\'s + can be found by the page');
  ok(/href="\/select-survey-type"/.test(tabbar),
     'and keeps its href, so a page without the menu still navigates');

  // The handler, run: the click must open the menu rather than follow the link.
  const block = html.slice(html.indexOf("const mtabNew = document.getElementById('mtabNew');"));
  const src = block.slice(0, block.indexOf('\n\n'));

  const dom = new JSDOM(`<!doctype html><body>
    <div class="fab-menu" id="fabMenu" hidden></div>
    <button id="fabMenuBtn" aria-expanded="false"></button>
    <a id="mtabNew" href="/select-survey-type"><span id="inner">+</span></a>
    </body>`, { runScripts: 'outside-only' });
  const w = dom.window;
  const grabFn = (name) => {
    let i = html.indexOf(`function ${name}(`);
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
  // The dismiss-on-outside-click handler goes in too. Without it this tests
  // half the interaction: the opener alone passes while the real page opens
  // the menu and closes it again in the same tap, because the click bubbles
  // to a handler that does not know this button is an opener.
  const doc = html.slice(html.indexOf("document.addEventListener('click'"));
  const outsideClick = doc.slice(0, doc.indexOf('});') + 3);

  w.eval(`${grabFn('toggleFabMenu')}\nvar canRunVisits = true;\n${src}\n${outsideClick}`);

  let followed = false;
  w.document.getElementById('mtabNew').addEventListener('click', (e) => {
    if (!e.defaultPrevented) followed = true;
  });
  // Tap the icon inside the link, the way a thumb actually lands.
  w.document.getElementById('inner').dispatchEvent(
    new w.MouseEvent('click', { bubbles: true, cancelable: true }));

  ok(!w.document.getElementById('fabMenu').hidden,
     'tapping + on a phone opens the choice');
  ok(!followed, 'and does not navigate straight to Start Visit');
}

console.log(failures ? `\n${failures} failure(s)` : '\nEverybody who may raise an issue can reach it.');
process.exit(failures ? 1 : 0);
