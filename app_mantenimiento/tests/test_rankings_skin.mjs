/*
  Rankings in the "Precisión" skin — rendered, clicked, measured.

  Gabriel asked for Rankings after Settings: under the four totals it was
  still the old build — 20px heavy titles, colours written inline, emoji
  medals (the design says no emoji, icons only), three solid navy buttons.
  Rewriting it also retired two old habits on that page: names went into the
  HTML unescaped, and each person row opened its profile through an onclick
  string built around the name (CLAUDE.md: an apostrophe there turns back
  into code). Rows now carry data-person and are wired in JS. Gabriel then
  had "Top Performers" removed: visits per person, beside a leaderboard
  whose "Most visits" already says it.

  This runs the real renderReports and loadLeaderboard with a name holding
  an apostrophe and one holding markup, clicks them, and measures the
  cascade (page styles, then theme.css) in light and dark. jsdom has no
  layout: how the tables wrap on a phone still needs a human look.
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
// A translucent fill is seen over the card under it, so measure that.
const over = (fill, base) => {
  const a = (fill.match(/[\d.]+/g) || []).map(Number);
  if (a.length < 4) return fill;
  const b = rgb(base);
  return `rgb(${[0, 1, 2].map(i => Math.round(a[i] * a[3] + b[i] * (1 - a[3]))).join(', ')})`;
};
const contrast = (a, b) => { const [x, y] = [lum(rgb(a)), lum(rgb(b))].sort((m, n) => n - m); return (x + 0.05) / (y + 0.05); };

const OBRIEN = "Kelly O'Brien";
const MARKUP = '<b id="injected">Bold</b> Pat';
const submissions = [OBRIEN, OBRIEN, OBRIEN, MARKUP, MARKUP, 'Greg Crutcher'].map((n, i) => ({
  inspector_name: n, submitted_at: `2026-11-0${i + 1}T12:00:00Z`, survey_type_id: 'standards', responses: [] }));
const LEADERS = {
  status: 'success',
  by_visits: [{ name: OBRIEN, region: 'Gulf', visits: 3 }, { name: MARKUP, region: '', visits: 2 },
              { name: 'Greg Crutcher', region: 'Texas', visits: 1 }, { name: 'Ana Ruiz', region: 'Texas', visits: 1 }],
  by_pass_rate: [{ name: 'Greg Crutcher', pass_rate: 91 }, { name: OBRIEN, pass_rate: 62 }, { name: MARKUP, pass_rate: 40 }],
};

async function rankings(dark) {
  const dom = new JSDOM(`<!doctype html><html ${dark ? 'data-theme="dark"' : ''}><head>
    <style>${head}</style><style>${theme}</style></head><body>
    <div class="main-content"><div id="gallery"></div></div></body></html>`, { runScripts: 'outside-only' });
  const w = dom.window;
  w.__leaders = LEADERS;
  w.eval(`
    window.opened = [];
    function openPersonPanel(n) { window.opened.push(n); }
    function exportReport() {}
    function fetch() { return Promise.resolve({ ok: true, json: () => Promise.resolve(window.__leaders) }); }
    ${grab('decodeEntities')}
    ${grab('escapeHtml')}
    ${grab('escapeHtmlForAttr')}
    ${grab('wirePersonRows')}
    ${grab('loadLeaderboard')}
    ${grab('renderReports')}
    var allSubmissions = ${JSON.stringify(submissions)};
    var surveyTypes = [{ id: 'standards', name: 'Standards', color: '#00285c', icon: 'fa-list' }];
    var allInspections = [{ type: 'inspection', condition: 'Pass' }, { type: 'inspection', condition: 'Fail' }];
    var communityData = [
      { name: "Tribute at The Glen", score: 92, actionItems: 0 },
      { name: "Naples' Landing", score: 64, actionItems: 3 },
      { name: 'The Oscar at Georgetown', score: 31, actionItems: 7 },
      { name: 'Never Visited', score: null, actionItems: 0 }];
  `);
  w.renderReports();
  await new Promise(r => setTimeout(r, 0));
  await new Promise(r => setTimeout(r, 0));
  return w;
}

console.log('\nThe page is built from classes, not emoji and inline colour');
{
  const w = await rankings(false);
  const g = w.document.getElementById('gallery');
  ok(g.querySelectorAll('.lb-row').length === 7, 'the leaderboard filled in (7 rows)');
  ok(!/\p{Extended_Pictographic}/u.test(g.textContent), 'no emoji anywhere, medals included');
  const ranks = [...g.querySelectorAll('.rk-table .rk-rank')].slice(0, 4).map(r => r.textContent);
  ok(JSON.stringify(ranks) === '["01","02","03","04"]', `ranks are two-digit numbers (${ranks.join(' ')})`);
  const first = g.querySelector('.rk-table');
  ok([...first.querySelectorAll('tbody .rk-rank')].map(r => r.classList.contains('top')).join() === 'true,true,true,false',
     'and the top three are marked');
  const inline = [...g.querySelectorAll('[style]')].filter(el => !el.classList.contains('rk-bar-fill'));
  ok(inline.length === 0, `no inline styles but the bar widths (${inline.map(e => e.className || e.tagName).join(', ')})`);
  const bands = [...g.querySelectorAll('.rk-score')].map(s => s.className.replace('rk-score ', ''));
  ok(JSON.stringify(bands) === '["rk-pass","rk-warn","rk-fail","rk-na"]', `scores carry their band (${bands.join(' ')})`);
  ok(g.querySelector('.rk-num.rk-open') && g.querySelector('.rk-num.rk-open').textContent === '3',
     'a community with open items has its count marked');
  ok(g.querySelectorAll('.rk-exports .btn.btn-secondary').length === 3, 'the exports are outline buttons');
}

console.log('\nNames are text, and a click opens the right person');
{
  const w = await rankings(false);
  const g = w.document.getElementById('gallery');
  ok(!w.document.getElementById('injected'), 'a name with markup is shown, not rendered');
  ok(g.textContent.includes(MARKUP), 'and reads as written');
  ok(g.textContent.includes("Naples' Landing"), 'a community with an apostrophe reads as written');
  ok(!g.querySelector('[onclick*="openPersonPanel"]'), 'no onclick string is built around a name');

  ok(!/Top Performers/.test(g.textContent) && !g.querySelector('.tp-row'),
     '"Top Performers" is gone; "Most visits" says it');
  ok(g.querySelectorAll('.rk-table').length === 1, 'one table left: the communities');

  const row = [...g.querySelectorAll('.lb-row')].find(r => r.dataset.person === OBRIEN);
  ok(!!row, 'a leaderboard row carries the name');
  row.click();
  ok(w.opened.at(-1) === OBRIEN, `clicking it opens ${OBRIEN} (${w.opened.at(-1)})`);
  row.dispatchEvent(new w.KeyboardEvent('keydown', { key: 'Enter' }));
  ok(w.opened.at(-1) === OBRIEN && w.opened.length === 2, 'Enter opens it too');

  const lb = [...g.querySelectorAll('.lb-row')].find(r => r.dataset.person === MARKUP);
  lb.click();
  ok(w.opened.at(-1) === MARKUP, 'a leaderboard row opens its person, markup and all');
  const rate = [...g.querySelectorAll('.lb-val')].map(v => v.className).filter(c => /rk-/.test(c));
  ok(rate.length === 3 && rate[0].includes('rk-pass') && rate[2].includes('rk-fail'),
     'pass rates carry their band, not an inline colour');
}

for (const dark of [false, true]) {
  const mode = dark ? 'dark' : 'light';
  console.log(`\nThe cascade, ${mode}`);
  const w = await rankings(dark);
  const d = w.document;
  const cs = (sel) => w.getComputedStyle(d.querySelector(sel));
  const root = w.getComputedStyle(d.documentElement);
  const font = (sel) => cs(sel).fontFamily.replace(/var\((--[\w-]+)\)/g, (_, n) => root.getPropertyValue(n));
  const card = cs('.rk-card').backgroundColor;
  ok(card === (dark ? 'rgb(22, 31, 46)' : 'rgb(255, 255, 255)'), `${mode}: panels are the card surface (${card})`);
  ok(cs('.lb-card').borderRadius === '8px' && cs('.rk-card').borderRadius === '8px', `${mode}: with 8px corners`);

  for (const sel of ['.rk-card-h', '.lb-card h3']) {
    const t = cs(sel);
    ok(t.borderBottomStyle === 'solid' && t.fontWeight === '600', `${mode}: ${sel} is a header row on a hairline`);
    ok(contrast(t.color, card) >= 7, `${mode}: and reads (${contrast(t.color, card).toFixed(1)}:1)`);
  }
  const top = cs('.rk-rank.top');
  ok(contrast(top.color, top.backgroundColor) >= 4.5, `${mode}: a top rank reads on its tile (${contrast(top.color, top.backgroundColor).toFixed(1)}:1)`);
  const plain = cs('.rk-table tbody tr:nth-child(4) .rk-rank');
  ok(contrast(plain.color, plain.backgroundColor) >= 4.5, `${mode}: so does a plain one (${contrast(plain.color, plain.backgroundColor).toFixed(1)}:1)`);
  for (const b of ['pass', 'warn', 'fail', 'na']) {
    const t = cs(`.rk-score.rk-${b}`);
    const bgc = over(t.backgroundColor, card);
    ok(contrast(t.color, bgc) >= 4.5, `${mode}: a ${b} score reads (${contrast(t.color, bgc).toFixed(1)}:1)`);
  }
  const lv = cs('.lb-val.rk-warn');
  const lvb = over(lv.backgroundColor, card);
  ok(contrast(lv.color, lvb) >= 4.5, `${mode}: a middling pass rate reads (${contrast(lv.color, lvb).toFixed(1)}:1)`);
  const th = cs('.rk-table th');
  ok(contrast(th.color, th.backgroundColor) >= 4.5, `${mode}: table headings read (${contrast(th.color, th.backgroundColor).toFixed(1)}:1)`);
  const td = cs('.rk-table td');
  ok(contrast(td.color, card) >= 7, `${mode}: table text reads (${contrast(td.color, card).toFixed(1)}:1)`);
  for (const sel of ['.rk-rank', '.rk-num', '.rk-score', '.lb-val', '.rk-type-val']) {
    ok(/JetBrains Mono/.test(font(sel)), `${mode}: ${sel} is mono`);
  }
  const fill = cs('.rk-bar-fill');
  ok(contrast(fill.backgroundColor, cs('.rk-bar').backgroundColor) >= 3, `${mode}: the bar shows on its track`);
}

console.log(failures ? `\n${failures} failed` : '\nall passed');
process.exit(failures ? 1 : 0);
