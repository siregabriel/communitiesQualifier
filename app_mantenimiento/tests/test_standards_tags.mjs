/*
  The Standards table's tags and columns, in the "Precisión" skin.

  Gabriel: the tags looked basic and flat and the table odd. Each survey
  type tinted its own tag background and text with its colour, so a light
  one (a lime "Sales Quick Visit") could not be read; the type's name went
  in unescaped and its colour went straight into a style attribute; "Every
  community" broke over two lines; the dates were #94a3b8. This runs the
  real getSurveyTypeBadges() with the page's styles and the theme, light
  and dark.
*/

import fs from 'fs';
import { JSDOM } from 'jsdom';

const theme = fs.readFileSync(new URL('../static/theme.css', import.meta.url), 'utf8');
const html = fs.readFileSync(new URL('../templates/question_manager.html', import.meta.url), 'utf8');
const css = [...html.matchAll(/<style>([\s\S]*?)<\/style>/g)].map(m => m[1]).join('\n');

let failures = 0;
const ok = (c, m) => { console.log((c ? '  ok   ' : '  FAIL ') + m); if (!c) failures++; };
const grab = (name) => {
  let i = html.indexOf(`function ${name}(`);
  if (i < 0) throw new Error(`no such function: ${name}`);
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

for (const dark of [false, true]) {
  const mode = dark ? 'dark' : 'light';
  const w = new JSDOM(`<!doctype html><html ${dark ? 'data-theme="dark"' : ''}><head>
    <style>${css}</style><style>${theme}</style></head><body>
    <div class="content-section"><table id="questionsTable"><tbody><tr>
      <td class="q-text">Lobby clean</td><td id="types"></td>
      <td><span class="community-count is-every">Every community</span></td>
      <td class="q-date">Jun 16, 2026</td></tr></tbody></table></div></body></html>`, { runScripts: 'outside-only' }).window;
  w.eval(`
    ${grab('decodeEntities')}
    ${grab('escapeHtml')}
    var surveyTypes = [
      { id: 'sqv', name: 'Sales Quick Visit', color: '#a3e635', icon: 'fa-tag' },
      { id: 'evil', name: '<img src=x onerror=alert(1)>', color: 'red;background:url(//x)', icon: 'fa-x' }];
    ${grab('getSurveyTypeBadges')}
    document.getElementById('types').innerHTML = getSurveyTypeBadges({ survey_types: ['sqv', 'evil'] });
  `);
  const d = w.document;
  const cs = (el) => w.getComputedStyle(typeof el === 'string' ? d.querySelector(el) : el);
  console.log(`\nThe table, ${mode}`);

  const [lime, evil] = d.querySelectorAll('.st-tag');
  const t = cs(lime);
  ok(contrast(t.color, t.backgroundColor) >= 7, `${mode}: a light-coloured type's name reads (${contrast(t.color, t.backgroundColor).toFixed(1)}:1)`);
  ok(lime.querySelector('.st-mark').style.background.replace(/\s/g, '') === 'rgb(163,230,53)', `${mode}: its colour is only the square`);
  ok(!d.querySelector('#types img'), `${mode}: a type's name is text, not markup`);
  ok(!/url|red/.test(evil.querySelector('.st-mark').getAttribute('style')), `${mode}: only a hex colour reaches the style`);
  ok(t.whiteSpace === 'nowrap' && cs('.community-count.is-every').whiteSpace === 'nowrap', `${mode}: tags stay on one line`);
  const date = cs('td.q-date');
  const rowBg = dark ? 'rgb(22, 31, 46)' : 'rgb(255, 255, 255)';
  ok(contrast(date.color, rowBg) >= 4.5 && /JetBrains Mono/.test(date.fontFamily), `${mode}: dates are mono and read (${contrast(date.color, rowBg).toFixed(1)}:1)`);
}

console.log(failures ? `\n${failures} failed` : '\nall passed');
process.exit(failures ? 1 : 0);
