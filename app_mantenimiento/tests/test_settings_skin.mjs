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

console.log(failures ? `\n${failures} failed` : '\nall passed');
process.exit(failures ? 1 : 0);
