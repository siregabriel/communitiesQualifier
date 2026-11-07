/*
  Settings in the "Precisión" skin — rendered, then measured.

  After the second pass Gabriel found Settings still built the old way: one
  long column of cards with colours written inline, and the Danger zone (wipe
  every visit) sitting between the visit target and the password form, while
  the tour told admins it was "at the bottom". It is now grouped under mono
  eyebrows — Your account, Administration, Email, Lists — with the Danger zone
  last and alone.

  Re-skinning it in theme.css exposed two quiet regressions, both caught
  here: theme.css loads after the page's own <style>, so a general card-title
  rule turned the Danger zone's red title ink-coloured, and a general region
  rule hid the red "No community assigned" warning. This runs the real
  renderSettings for an admin and for an ED, with the page's styles and the
  theme in their real order, in light and dark. jsdom has no layout: how the
  grid wraps on a phone still needs a human look.
*/

import fs from 'fs';
import { JSDOM } from 'jsdom';

const theme = fs.readFileSync(new URL('../static/theme.css', import.meta.url), 'utf8');
const html = fs.readFileSync(new URL('../templates/dashboard.html', import.meta.url), 'utf8');
const head = html.slice(html.indexOf('<style>') + 7, html.indexOf('</style>'));

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

const rgb = (s) => (s.match(/[\d.]+/g) || [0, 0, 0]).slice(0, 3).map(Number);
const lum = ([r, g, b]) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; };
  return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
const contrast = (a, b) => { const [x, y] = [lum(rgb(a)), lum(rgb(b))].sort((m, n) => n - m); return (x + 0.05) / (y + 0.05); };

async function settings({ admin, dark, coversNothing = false }) {
  const dom = new JSDOM(`<!doctype html><html ${dark ? 'data-theme="dark"' : ''}><head>
    <style>${head}</style><style>${theme}</style></head><body>
    <div class="main-content"><div id="gallery"></div></div></body></html>`, { runScripts: 'outside-only' });
  const w = dom.window;
  w.__profile = {
    status: 'success', username: 'preview.admin', display_name: 'Preview Admin',
    role: admin ? 'Administrator' : 'Executive Director', is_admin: admin,
    community: coversNothing ? '' : (admin ? 'All communities' : 'The Oscar at Georgetown'),
    covers_nothing: coversNothing, photo: null, last_active: null, recent_activity: [],
    stats: { inspections: 12, questions_created: 3, questions_edited: 5, total_actions: 40 },
  };
  w.eval(`
    var currentUsername = 'preview.admin', isAdmin = ${admin}, canRunVisits = true,
        currentUserCommunity = '', visitCadenceDays = 30, ACTIVITY_META = {};
    window.calls = [];
    function fetch() { return Promise.resolve({ ok: true, json: () => Promise.resolve(window.__profile) }); }
    function escapeHtml(s) { return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }
    function avatarColor() { return '#003366'; }
    function profileInitials(n) { return n.slice(0, 2).toUpperCase(); }
    function timeAgo() { return 'now'; }
    function loadEmailSettings() {} function loadNotificationSummary() {}
    function loadRaisedCategoryAdmin() {} function wireTeamPositionAdmin() {} function loadTeamPositionAdmin() {}
    ${grab('renderSettings')}
  `);
  await w.eval('renderSettings()');
  return w;
}

console.log('\nThe admin page is grouped, and the Danger zone is last');
{
  const w = await settings({ admin: true, dark: false });
  const d = w.document;
  const groups = [...d.querySelectorAll('.set-group')].map(g => g.textContent.trim());
  ok(JSON.stringify(groups) === JSON.stringify(['Your account', 'Administration', 'Email', 'Lists']),
     `four groups in order (${groups.join(' · ')})`);
  const wrap = d.querySelector('.profile-wrap');
  const last = wrap.lastElementChild;
  ok(last && last.classList.contains('danger-zone'), 'the Danger zone is the last thing on the page');
  ok(d.querySelectorAll('.danger-zone').length === 1, 'and appears once');
  const titles = [...d.querySelectorAll('.profile-section-title')].map(t => t.textContent.trim());
  for (const t of ['Change password', 'Visit target', 'User management', 'Email & notifications',
    'Email recipients', 'Raised item categories', 'Staff positions', 'Danger zone']) {
    ok(titles.includes(t), `"${t}" is still there`);
  }
  // Colours written inline beat the skin and ignore dark mode.
  const inline = [...wrap.querySelectorAll('[style]')].filter(el => el.id !== 'profilePhotoInput'
    && !el.matches('.profile-avatar-initials, .activity-avatar-initials, #profileNameEdit'));
  ok(inline.length === 0, `no inline styles in the cards (${inline.map(e => e.className || e.tagName).join(', ')})`);
}

console.log('\nAn Executive Director sees their account only');
{
  const w = await settings({ admin: false, dark: false });
  const d = w.document;
  const groups = [...d.querySelectorAll('.set-group')].map(g => g.textContent.trim());
  ok(JSON.stringify(groups) === JSON.stringify(['Your account']), `one group (${groups.join(' · ')})`);
  ok(!d.querySelector('.danger-zone, #tpList, #esSubscribers, #cadenceInput'), 'no admin cards');
  ok(!!d.getElementById('pwCurrent'), 'the password form is there');
}

for (const dark of [false, true]) {
  const mode = dark ? 'dark' : 'light';
  console.log(`\nThe cascade, ${mode}`);
  const w = await settings({ admin: true, dark });
  const d = w.document;
  const cs = (sel) => w.getComputedStyle(d.querySelector(sel));
  const root = w.getComputedStyle(d.documentElement);
  const font = (sel) => cs(sel).fontFamily.replace(/var\((--[\w-]+)\)/g, (_, n) => root.getPropertyValue(n));
  const page = dark ? 'rgb(11, 18, 32)' : 'rgb(244, 246, 248)';
  const card = dark ? 'rgb(22, 31, 46)' : 'rgb(255, 255, 255)';

  const eyebrow = cs('.set-group');
  ok(/JetBrains Mono/.test(font('.set-group')) && eyebrow.textTransform === 'uppercase', `${mode}: groups have the mono eyebrow`);
  ok(contrast(eyebrow.color, page) >= 4.5, `${mode}: and it reads on the page (${contrast(eyebrow.color, page).toFixed(1)}:1)`);

  const title = cs('.profile-section-title:not(.danger-title)');
  ok(title.borderBottomStyle === 'solid', `${mode}: each card has a header row on a hairline`);
  ok(contrast(title.color, card) >= 7, `${mode}: card titles read (${contrast(title.color, card).toFixed(1)}:1)`);

  const danger = cs('.danger-title');
  const [r, g, b] = rgb(danger.color);
  ok(r > g + 60 && r > b + 60, `${mode}: the Danger zone title stays red, not ink (${danger.color})`);
  ok(contrast(danger.color, card) >= 4.5, `${mode}: and reads (${contrast(danger.color, card).toFixed(1)}:1)`);
  const [br] = rgb(cs('.danger-zone').borderTopColor);
  ok(br > 150 && rgb(cs('.danger-zone').borderTopColor)[0] > rgb(cs('.danger-zone').borderTopColor)[2] + 40,
     `${mode}: its border is red too (${cs('.danger-zone').borderTopColor})`);

  const desc = cs('.set-desc');
  ok(contrast(desc.color, card) >= 4.5, `${mode}: descriptions read (${contrast(desc.color, card).toFixed(1)}:1)`);

  ok(/JetBrains Mono/.test(font('.profile-stat-value')), `${mode}: the numbers are mono`);
  ok(cs('.profile-stat').flexDirection === 'column-reverse', `${mode}: label above the number`);
  const stat = cs('.profile-stat-value');
  ok(contrast(stat.color, card) >= 4.5, `${mode}: and they read (${contrast(stat.color, card).toFixed(1)}:1)`);

  // #rcNew and #tpNew have no type attribute: the dark input rule misses them.
  const input = cs('#tpNew');
  ok(contrast(input.color, input.backgroundColor) >= 4.5 && (!dark || lum(rgb(input.backgroundColor)) < 0.1),
     `${mode}: an untyped input is ${dark ? 'dark' : 'light'} and readable (${input.backgroundColor})`);
  ok(cs('#tpNew').borderRadius === '8px', `${mode}: inputs share the 8px corner`);
}

console.log('\nAn account that covers nothing still says so in red');
for (const dark of [false, true]) {
  const w = await settings({ admin: false, dark, coversNothing: true });
  const el = w.document.querySelector('.profile-region.is-empty');
  const [r, g, b] = rgb(w.getComputedStyle(el).color);
  ok(r > g + 60 && r > b + 60, `${dark ? 'dark' : 'light'}: "No community assigned" is red (${w.getComputedStyle(el).color})`);
}

/*
  Nov 2026, Gabriel: the cards took too much room. An admin's "Change password"
  filled a whole row for three inputs, and "Email recipients" was one long row
  per person across the full width. Now an admin's account sits beside
  Administration, the four routing lists share a row, and recipients are cards
  in a grid. The text also said Executive Directors were not listed, which
  stopped being true when they were added. Widths still need a human look.
*/
console.log('\nSettings uses its width');
{
  const w = await settings({ admin: true, dark: false });
  const d = w.document;
  const top = d.querySelector('.set-top');
  const cols = top ? [...top.children].map(c => c.querySelector('.set-group')?.textContent.trim()) : [];
  ok(JSON.stringify(cols) === JSON.stringify(['Your account', 'Administration']),
     `an admin's account and Administration share one row (${cols.join(' | ')})`);
  ok(/minmax\(0px, 1fr\) minmax\(0px, 2fr\)|minmax\(0, 1fr\) minmax\(0, 2fr\)/.test(w.getComputedStyle(top).gridTemplateColumns),
     `a third for the account, two thirds for Administration (${w.getComputedStyle(top).gridTemplateColumns})`);
  ok(!d.getElementById('pwCurrent').closest('.set-wide'), 'the password card does not span the row');
  const lists = [...d.querySelectorAll('.set-lists > .set-list textarea')].map(t => t.id);
  ok(JSON.stringify(lists) === JSON.stringify(['esAdminNotify', 'esClinical', 'esOps', 'esSales']),
     `the four routing lists sit in one grid (${lists.join(', ')})`);
  // Gabriel's screenshot: Clinical, Ops and Sales boxes at three heights, because
  // two titles carried their hint inline and one wrapped. Same shape for all four.
  const shapes = [...d.querySelectorAll('.set-list')].map(l =>
    [...l.children].map(c => c.matches('label.set-label') ? 'title' : c.matches('.set-hint') ? 'hint' : c.tagName.toLowerCase()).join('+'));
  ok(shapes.length === 4 && shapes.every(x => x === 'title+hint+textarea'),
     `each list is title, hint, box (${shapes.join(' · ')})`);
  ok(!d.querySelector('.set-list label small'), 'no hint left inside a title');
  ok(w.getComputedStyle(d.getElementById('esSales')).marginTop === 'auto', 'the boxes sit at the bottom of their column');
  const desc = [...d.querySelectorAll('.set-desc')].map(p => p.textContent).join(' ');
  ok(!/Executive Directors don.t appear/.test(desc), 'nothing claims Executive Directors are not listed');

  // The recipients themselves: cards inside the grid, warnings below it.
  w.eval(`${grab('loadNotificationSummary')}
    fetch = () => Promise.resolve({ ok: true, json: () => Promise.resolve({
      status: 'success', email_enabled: false,
      missing_email: [{ name: 'No Address', region: 'Magnolia' }],
      people: [
        { email: 'a@x.com', name: 'Ann Auto', username: 'ann.auto', items: [{ kind: 'auto', label: 'Inspection reports', detail: 'Magnolia region (automatic)' }] },
        { email: 'b@x.com', name: "Bob O'Sub", items: [{ kind: 'all', label: 'Inspection reports', detail: '' }] },
        { email: 'c@x.com', name: 'Cy Both', username: 'cy.both', items: [{ kind: 'auto', label: 'Inspection reports', detail: 'Coastal region (automatic)' }, { kind: 'admin', label: 'Admin alerts', detail: '' }] },
      ] }) });
    var peopleOpenOnLoad = '', currentView = 'settings';
    window.sent = [];
    const realFetch = fetch;
    fetch = (url, opts) => { window.sent.push([url, (opts && opts.method) || 'GET']); return realFetch(url, opts); };
    function showView(v) { currentView = v; }`);
  await w.eval('loadNotificationSummary()');
  const host = d.getElementById('notifySummary');
  ok(host.querySelectorAll('.nsum-grid > .nsum-row').length === 3, 'each recipient is a card in the grid');
  ok(!host.querySelector('.nsum-grid .nsum-warn') && host.querySelectorAll(':scope > .nsum-warn').length === 2,
     'the warnings sit below the grid, full width');
  const gtc = w.getComputedStyle(host.querySelector('.nsum-grid')).gridTemplateColumns;
  ok(/^repeat\(3,/.test(gtc), `three columns when wide (${gtc})`);

  /* Gabriel saw a lock on most rows, hovered it, got a "?" cursor and nothing
     else: the explanation lived in a native tooltip. A row that comes from the
     person's role now says where to change it, and takes him there. */
  const row = (name) => [...host.querySelectorAll('.nsum-row')].find(r => r.querySelector('.nsum-name').textContent === name);
  ok(!host.querySelector('.nsum-lock, .fa-lock'), 'no lock is left');
  const edit = row('Ann Auto').querySelector('.nsum-edit');
  ok(edit && edit.textContent.trim() === 'Edit in People', 'a role row offers "Edit in People"');
  edit.click();
  ok(w.eval('currentView') === 'people' && w.eval('peopleOpenOnLoad') === 'ann.auto',
     'which opens People with that person queued to open');
  ok(!row("Bob O'Sub").querySelector('.nsum-edit'), 'a list-only row has no account to open');
  ok(row('Cy Both').querySelector('.nsum-edit'), 'a row that is both gets the button too');

  /* Then the bin. It sat on some cards and not others, and on Angie Surls it
     removed her "All inspections" subscription while Corporate reports kept
     coming: it looked like "stop emailing her" and was not. Gabriel chose a
     read-only summary: lists are edited above, roles in People. */
  ok(!host.querySelector('.fa-trash, .nsum-del, [data-remove]'), 'no card has a bin');
  ok(host.querySelectorAll('button').length === 2 && [...host.querySelectorAll('button')].every(b => b.matches('.nsum-edit')),
     'the only buttons are "Edit in People"');
  for (const b of host.querySelectorAll('button')) b.click();
  ok(w.sent.every(([, m]) => m === 'GET'), `nothing on the summary writes (${JSON.stringify(w.sent)})`);
  ok(/Nothing is changed here/.test(desc), 'and the card says so');
  ok(/Edit in People/.test(desc), 'the card text says what the button does');
}

console.log('\nPeople opens the person Settings asked for');
{
  const dom = new JSDOM('<div id="gallery"></div>', { runScripts: 'outside-only' });
  const w = dom.window;
  w.eval(`
    var peopleData = null, peopleOpenOnLoad = 'ann.auto'; window.opened = [];
    function fetch() { return Promise.resolve({ ok: true, json: () => Promise.resolve({ status: 'success', people: [{ username: 'ann.auto' }] }) }); }
    function drawPeople() {} function openPersonEdit(u) { window.opened.push(u); }
    ${grab('renderPeople')}`);
  await w.eval('renderPeople()');
  ok(JSON.stringify(w.opened) === '["ann.auto"]', `the person's edit form opens (${JSON.stringify(w.opened)})`);
  await w.eval('renderPeople()');
  ok(w.opened.length === 1, 'once: the next visit to People opens nothing');
}

console.log(failures ? `\n${failures} failed` : '\nall passed');
process.exit(failures ? 1 : 0);
