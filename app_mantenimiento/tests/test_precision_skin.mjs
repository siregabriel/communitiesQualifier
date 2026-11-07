/*
  The "Precisión" skin, computed rather than read.

  Gabriel chose the design.md proposal and, comparing the first pass with the
  mock-ups, found it had the colours and type but not the screens: headers,
  number tiles, chips still built the old way. The second pass re-shapes them,
  and the dashboard home brings its own <style> block that comes AFTER
  theme.css — so a rule there silently beats the skin unless the skin is more
  specific. This loads the three stylesheets in their real order and asks what
  the browser engine ends up with. jsdom resolves the cascade; it does not
  lay out, so sizes that only matter on screen still need a human look.
*/

import fs from 'fs';
import { JSDOM } from 'jsdom';

const theme = fs.readFileSync(new URL('../static/theme.css', import.meta.url), 'utf8');
const html = fs.readFileSync(new URL('../templates/dashboard.html', import.meta.url), 'utf8');
const head = html.slice(html.indexOf('<style>') + 7, html.indexOf('</style>'));
// The home's own block, rendered into the page after theme.css.
const homeStart = html.indexOf('            <style>\n                .dash-wrap');
const home = html.slice(homeStart + '            <style>'.length, html.indexOf('</style>', homeStart));

let failures = 0;
const ok = (c, m) => { console.log((c ? '  ok   ' : '  FAIL ') + m); if (!c) failures++; };

const rgb = (s) => (s.match(/[\d.]+/g) || [0, 0, 0]).slice(0, 3).map(Number);
const lum = ([r, g, b]) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; };
  return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
const contrast = (a, b) => { const [x, y] = [lum(rgb(a)), lum(rgb(b))].sort((m, n) => n - m); return (x + 0.05) / (y + 0.05); };

function page(dark) {
  const dom = new JSDOM(`<!doctype html><html ${dark ? 'data-theme="dark"' : ''}><head>
    <style>${head}</style><style>${theme}</style></head><body>
    <div class="main-content">
      <div class="header-section"><div class="header-left">
        <h1><i class="fas fa-gauge-high"></i> Dashboard</h1><p>Performance Overview</p></div></div>
      <div id="gallery"><style>${home}</style>
        <div class="dash-kpis">
          <div class="kpi"><div class="kpi-val" style="color:#0f8a5f">87%</div><div class="kpi-lbl">Average score</div></div>
          <div class="kpi"><div class="kpi-val" style="color:var(--kpi-navy)">12/40</div><div class="kpi-lbl">Visited this month</div></div>
        </div>
        <div class="attn attn-tone-act"><div class="attn-item"><div class="attn-main"><div class="attn-title">Naples</div></div></div></div>
        <div class="ai-chiprow"><button class="ai-chip on">All <span>118</span></button><button class="ai-chip">Findings <span>84</span></button></div>
      </div>
    </div></body></html>`);
  return dom.window;
}

for (const dark of [false, true]) {
  const mode = dark ? 'dark' : 'light';
  const w = page(dark);
  const d = w.document;
  const cs = (sel) => w.getComputedStyle(d.querySelector(sel));
  // jsdom hands back var(--x) as written; a browser substitutes it. Do the same.
  const root = w.getComputedStyle(d.documentElement);
  const font = (sel) => cs(sel).fontFamily.replace(/var\((--[\w-]+)\)/g, (_, n) => root.getPropertyValue(n));
  const bg = dark ? 'rgb(11, 18, 32)' : 'rgb(244, 246, 248)';
  console.log(`\nThe skin, ${mode}`);

  const eyebrow = cs('.header-left p');
  ok(eyebrow.textTransform === 'uppercase' && /JetBrains Mono/.test(font('.header-left p')),
     `${mode}: the subtitle is the mono eyebrow`);
  ok(eyebrow.order === '-1', `${mode}: and sits above the title`);
  ok(contrast(eyebrow.color, bg) >= 4.5, `${mode}: and reads on the page (${contrast(eyebrow.color, bg).toFixed(1)}:1)`);
  const h1 = cs('.header-left h1');
  ok(/Roboto/.test(font('.header-left h1')) && h1.fontWeight === '700', `${mode}: the title is Roboto bold`);
  ok(cs('.header-left h1 i').display === 'none', `${mode}: without the old icon`);
  ok(cs('.header-section').paddingLeft === '0px', `${mode}: the title starts where the cards do, not 36px in (${cs('.header-section').paddingLeft})`);

  const hero = cs('.dash-kpis > .kpi:first-child');
  const heroVal = cs('.dash-kpis > .kpi:first-child .kpi-val');
  ok(contrast(heroVal.color, hero.backgroundColor) >= 4.5,
     `${mode}: the hero tile's number reads on navy, over its inline status colour (${contrast(heroVal.color, hero.backgroundColor).toFixed(1)}:1)`);
  ok(/JetBrains Mono/.test(font('.dash-kpis > .kpi:first-child .kpi-val')), `${mode}: numbers are mono`);
  ok(cs('.dash-kpis > .kpi:first-child').flexDirection === 'column-reverse', `${mode}: label above the number`);
  ok(cs('.dash-kpis > .kpi:nth-child(2)').borderRadius === '8px',
     `${mode}: the home's own 10px corners lose to the skin's 8px`);


  const on = cs('.ai-chip.on');
  ok(contrast(on.color, on.backgroundColor) >= 4.5, `${mode}: the chosen chip reads (${contrast(on.color, on.backgroundColor).toFixed(1)}:1)`);
  ok(cs('.ai-chip:not(.on)').borderRadius === '6px', `${mode}: chips are square-cornered, not pills`);
}

console.log('\nStandards and buttons');
{
  // Gabriel's screenshot: capitals on every button, pill tags, a dotted
  // "Every community", 20px corners. The page's own <style> comes before
  // theme.css, so the skin wins there on order.
  const qm = fs.readFileSync(new URL('../templates/question_manager.html', import.meta.url), 'utf8');
  const qmCss = [...qm.matchAll(/<style>([\s\S]*?)<\/style>/g)].map(m => m[1]).join('\n');
  const w = new JSDOM(`<!doctype html><html><head><style>${qmCss}</style><style>${theme}</style></head><body>
    <div class="header-actions"><button class="btn btn-primary">Create New Question</button></div>
    <div class="content-section"><table id="questionsTable"><tbody><tr>
      <td><input type="checkbox"></td><td class="q-text">Lobby clean</td><td></td>
      <td><span class="survey-type-badge survey-type-all">All Types</span></td>
      <td><span class="community-count is-every">Every community</span><span class="community-badge">Community A</span></td>
      <td>Jun 16, 2026</td><td><button class="btn-icon edit"></button></td>
    </tr></tbody></table></div></body></html>`).window;
  const cs = (sel) => w.getComputedStyle(w.document.querySelector(sel));
  ok(cs('.btn').textTransform === 'none', `buttons are a sentence, not capitals (${cs('.btn').textTransform})`);
  ok(cs('.content-section').borderRadius === '8px', `the panel has the theme's corners (${cs('.content-section').borderRadius})`);
  for (const sel of ['.survey-type-badge', '.community-badge', '.community-count.is-every']) {
    ok(cs(sel).borderRadius === '4px', `${sel} is a square-cornered tag (${cs(sel).borderRadius})`);
  }
  const every = cs('.community-count.is-every');
  ok(every.borderBottomStyle !== 'dotted', `"Every community" is a tag, not a dotted link (${every.borderBottomStyle})`);
  ok(cs('.btn-icon').borderRadius === '6px', 'row actions share one corner');
}

console.log('\nCommunity cards, the visit panel, Rankings and the form');
{
  // The last round: vivid region gradients on cards with no photo (set as an
  // inline style), capitalised PASS blocks in the panel, colour-block totals
  // on Rankings, capitals on the form's buttons.
  const w = new JSDOM(`<!doctype html><html><head><style>${head}</style><style>${theme}</style></head><body>
    <div class="community-card"><div class="card-image" style="background: linear-gradient(135deg, #f472b6, #ef4444)"><i class="fas fa-building"></i>
      <span class="card-region-badge">Coastal</span></div></div>
    <span class="response-condition badge-pass">Pass</span>
    <div class="rk-kpi rk-fail"><div class="rk-kpi-lbl">Fail</div><div class="rk-kpi-val">4</div></div>
  </body></html>`).window;
  const cs = (sel) => w.getComputedStyle(w.document.querySelector(sel));
  const img = cs('.card-image');
  ok(!/f472b6|244, 114, 182/i.test(img.background + img.backgroundColor + img.backgroundImage),
     'a card with no photo loses the region gradient');
  ok(cs('.card-region-badge').textTransform === 'none' && cs('.card-region-badge').borderRadius === '4px',
     'the region is a square tag in sentence case');
  const pass = cs('.response-condition');
  ok(pass.textTransform === 'none' && pass.borderRadius === '4px', 'Pass is a soft tag, not a capitalised block');
  ok(contrast(pass.color, pass.backgroundColor) >= 4.5, `and reads (${contrast(pass.color, pass.backgroundColor).toFixed(1)}:1)`);
  const rk = cs('.rk-kpi');
  ok(rk.backgroundColor === 'rgb(255, 255, 255)', 'Rankings totals are white tiles');
  ok(contrast(cs('.rk-kpi-val').color, rk.backgroundColor) >= 4.5, 'with a readable coloured number');

  const rep = fs.readFileSync(new URL('../templates/reporte.html', import.meta.url), 'utf8');
  const repCss = [...rep.matchAll(/<style>([\s\S]*?)<\/style>/g)].map(m => m[1]).join('\n');
  const f = new JSDOM(`<!doctype html><html><head><style>${repCss}</style><style>${theme}</style></head><body>
    <button class="logout-btn">Logout</button><div class="question-section"></div></body></html>`).window;
  const fs2 = (sel) => f.getComputedStyle(f.document.querySelector(sel));
  ok(fs2('.logout-btn').textTransform === 'none', "the form's header buttons are not capitals");
  ok(fs2('.question-section').borderLeftWidth === '3px', 'each standard has the thin navy rail');
}

console.log('\nBy rule');
ok(/body \.attn-tone-act\s+\.attn-item::before \{ background: #c62828; \}/.test(theme), 'urgent lines carry a red square');
ok(/\.main-content::before \{ display: none !important;/.test(theme), 'the drifting colour layer is switched off');

console.log(failures ? `\n${failures} failure(s)` : '\nThe skin holds.');
process.exit(failures ? 1 : 0);
