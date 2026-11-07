/*
  The community panel in the "Precisión" skin — rendered and measured.

  Gabriel asked whether the panel had the design yet. It had the colours, not
  the build: section titles as big iconed headings competing with the
  community's name, a solid white X brighter than the title, tall number
  tiles, and a band of empty space under every response (a bottom margin
  inside the grid plus the tag's own). Now a mono eyebrow names the region
  over the community, sections are mono eyebrows, and each response is as
  tall as its text with a rail in its result's colour — the same colours as
  the buttons on the visit form, which Gabriel asked to agree.
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

const header = html.slice(html.indexOf('<aside class="slide-panel"'), html.indexOf('</aside>') + 8);

for (const dark of [false, true]) {
  const mode = dark ? 'dark' : 'light';
  const w = new JSDOM(`<!doctype html><html ${dark ? 'data-theme="dark"' : ''}><head>
    <style>${head}</style><style>${theme}</style></head><body>${header}</body></html>`,
    { runScripts: 'outside-only' }).window;
  w.eval(`
    var regions = [{ name: 'Coastal', communities: ['Kelley Place, Enterprise'] }];
    function standardFor() { return { text: 'x' }; }
    function commentThreadHtml() { return ''; }
    function formatDate(s) { return s; }
    function photoUrl(p) { return p; }
    ${grab('decodeEntities')}
    ${grab('escapeHtml')}
    ${grab('escapeHtmlForAttr')}
    ${grab('getBadgeClass')}
    ${grab('getCommunityRegionName')}
    ${grab('setPanelEyebrow')}
    ${grab('helpRowHtml')}
    ${grab('renderResponses')}
    const r = (q, c) => ({ questionText: q, condition: c, conditionClass: getBadgeClass(c), conditionIcon: 'fas fa-check',
                           questionId: q, submissionId: 's1', comments: [] });
    document.getElementById('slidePanelBody').innerHTML = renderResponses([
      r('Phone Shop', 'Fail'), r('Tour Path is show time ready', 'Pass'), r('Kitchen', 'Not checked')]);
    setPanelEyebrow('Kelley Place, Enterprise');
  `);
  const d = w.document;
  const cs = (el) => w.getComputedStyle(typeof el === 'string' ? d.querySelector(el) : el);
  console.log(`\nThe panel, ${mode}`);

  const eb = d.getElementById('slidePanelEyebrow');
  ok(!eb.hidden && eb.textContent === 'Community · Coastal', `${mode}: a mono eyebrow names the region (${eb.textContent})`);
  ok(/JetBrains Mono/.test(cs(eb).fontFamily.replace(/var\(--font-mono\)/, 'JetBrains Mono')), `${mode}: in mono`);
  const x = cs('.slide-panel-close');
  ok(lum(rgb(x.color)) > 0.9 && !(x.backgroundColor === 'rgb(255, 255, 255)' || x.backgroundColor === 'rgb(241, 245, 249)'),
     `${mode}: the X is quiet, not a white block (${x.backgroundColor})`);

  const t = cs('.panel-section-title');
  ok(t.textTransform === 'uppercase' && /mono/i.test(t.fontFamily), `${mode}: section titles are mono eyebrows`);
  ok(cs('.panel-section-title i').display === 'none', `${mode}: without the big icon`);

  const cards = [...d.querySelectorAll('.response-card')];
  const rails = cards.map(c => cs(c).borderLeftColor);
  ok(rails[0] === 'rgb(234, 54, 110)', `${mode}: a Fail's rail is the form's Fail colour (${rails[0]})`);
  ok(rails[1] === 'rgb(117, 251, 135)', `${mode}: a Pass's is the form's Pass colour (${rails[1]})`);
  ok(rails[2] === 'rgb(91, 107, 133)', `${mode}: a Not checked's is grey (${rails[2]})`);
  ok(cards.every(c => cs(c).marginBottom === '0px'), `${mode}: no margin under a card inside the grid`);
  ok(cs('.response-condition').marginBottom === '0px', `${mode}: nor under its tag, so the card ends at its text`);
}

console.log(failures ? `\n${failures} failed` : '\nall passed');
process.exit(failures ? 1 : 0);
