/*
  The unfinished-visits card in the "Precisión" skin — rendered and measured.

  Gabriel spotted it in My Visits after the phone pass: still the old build,
  cream with gold borders, 14px corners, a pill count, gold icon and chevron.
  It is now a white panel like the others, its header on a hairline, an amber
  rail for "still needs you" (amber only as a line: it is 2:1 on white), and
  each visit a row with a small navy bar for how far along it is. This runs
  the real draftNoticesHtml with the page's styles and the theme, light and
  dark.
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
const over = (fill, base) => {
  const a = (fill.match(/[\d.]+/g) || []).map(Number);
  if (a.length < 4) return fill;
  const b = rgb(base);
  return `rgb(${[0, 1, 2].map(i => Math.round(a[i] * a[3] + b[i] * (1 - a[3]))).join(', ')})`;
};
const contrast = (a, b) => { const [x, y] = [lum(rgb(a)), lum(rgb(b))].sort((m, n) => n - m); return (x + 0.05) / (y + 0.05); };

for (const dark of [false, true]) {
  const mode = dark ? 'dark' : 'light';
  const w = new JSDOM(`<!doctype html><html ${dark ? 'data-theme="dark"' : ''}><head>
    <style>${head}</style><style>${theme}</style></head><body><div id="host"></div></body></html>`,
    { runScripts: 'outside-only' }).window;
  w.eval(`
    ${grab('decodeEntities')}
    ${grab('escapeHtml')}
    ${grab('splitCommunityName')}
    function timeAgo() { return '6 hours ago'; }
    var draftNotices = [
      { community: 'Madison at Oviedo, Oviedo', survey_type_id: 's', answered: 1, total: 7, started_at: '', device: 'Mac · Safari', mine: true },
      { community: 'Greystone, Tampa', survey_type_id: 's', answered: 33, total: 51, started_at: '', username: 'greg', display_name: 'Greg Crutcher', mine: false }];
    ${grab('draftNoticesHtml')}
    document.getElementById('host').innerHTML = draftNoticesHtml();
  `);
  const d = w.document;
  const cs = (sel) => w.getComputedStyle(d.querySelector(sel));
  console.log(`\nUnfinished visits, ${mode}`);

  const card = cs('.dn').backgroundColor;
  ok(card === (dark ? 'rgb(22, 31, 46)' : 'rgb(255, 255, 255)'), `${mode}: a card-surface panel, not cream (${card})`);
  ok(cs('.dn').borderRadius === '8px', `${mode}: with the theme's 8px corner`);
  // In My Visits it sits in the gallery grid; it took one narrow column there.
  ok(cs('.dn').gridColumn === '1 / -1' || cs('.dn').gridColumnStart === '1', `${mode}: it spans the whole grid, not one column`);
  ok(/inset 3px 0px 0px/.test(cs('.dn').boxShadow) || /inset 3px 0 0/.test(cs('.dn').boxShadow), `${mode}: and an amber rail`);

  const t = cs('.dn-title');
  ok(t.borderBottomStyle === 'solid', `${mode}: the title is a header row on a hairline`);
  ok(contrast(t.color, card) >= 7, `${mode}: and reads (${contrast(t.color, card).toFixed(1)}:1)`);
  const n = cs('.dn-title span');
  ok(contrast(n.color, over(n.backgroundColor, card)) >= 4.5, `${mode}: the count reads on its tag (${contrast(n.color, over(n.backgroundColor, card)).toFixed(1)}:1)`);
  ok(n.borderRadius === '4px', `${mode}: a square tag, not a pill`);
  ok(contrast(cs('.dn-note').color, card) >= 4.5, `${mode}: the note reads`);
  ok(contrast(cs('.dn-meta').color, card) >= 4.5, `${mode}: so does each row's detail`);

  const row = cs('.dn-row');
  ok(row.borderLeftStyle === 'none' || row.borderLeftWidth === '0px', `${mode}: rows are lines in the panel, not boxes in a box`);
  const bars = [...d.querySelectorAll('.dn-bar i')].map(b => b.style.width);
  ok(JSON.stringify(bars) === '["14%","65%"]', `${mode}: each row shows how far along it is (${bars.join(', ')})`);
  ok(!!d.querySelector('.dn-row.is-theirs .dn-who'), `${mode}: someone else's still names them`);
  const who = cs('.dn-who');
  ok(contrast(who.color, over(who.backgroundColor, card)) >= 4.5, `${mode}: and the name reads`);
}

console.log(failures ? `\n${failures} failed` : '\nall passed');
process.exit(failures ? 1 : 0);
