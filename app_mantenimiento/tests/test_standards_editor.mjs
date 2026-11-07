/*
  The Standards editor (Create / Edit question) in the "Precisión" skin.

  Gabriel found it still in the old build: a 22px card with a gradient
  header, every label in capitals — including each survey type's name,
  because the page's `.form-group label` rule reached the option rows —
  12px rounded inputs, a blue gradient "1 type selected" pill and a green
  Save. This renders the real window (page styles, then theme.css) with a
  survey type row like the ones the page builds, light and dark, and
  measures it.
*/

import fs from 'fs';
import { JSDOM } from 'jsdom';

const theme = fs.readFileSync(new URL('../static/theme.css', import.meta.url), 'utf8');
const html = fs.readFileSync(new URL('../templates/question_manager.html', import.meta.url), 'utf8');
const css = [...html.matchAll(/<style>([\s\S]*?)<\/style>/g)].map(m => m[1]).join('\n');
const modal = html.slice(html.indexOf('<div id="questionModal"'), html.indexOf('<!-- Delete Confirmation Modal -->'))
  .replace(/\{%[\s\S]*?%\}/g, '').replace(/\{\{[\s\S]*?\}\}/g, 'x')
  .replace('<div id="surveyTypesList">', `<div id="surveyTypesList"><div class="survey-type-option">
      <input type="checkbox" id="surveyType_0" class="survey-type-checkbox">
      <label for="surveyType_0"><span class="survey-type-icon"><i class="fas fa-chart-line"></i></span> Sales Quick Visit</label></div>`);

let failures = 0;
const ok = (c, m) => { console.log((c ? '  ok   ' : '  FAIL ') + m); if (!c) failures++; };
const rgb = (s) => (s.match(/[\d.]+/g) || [0, 0, 0]).slice(0, 3).map(Number);
const lum = ([r, g, b]) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; };
  return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
const contrast = (a, b) => { const [x, y] = [lum(rgb(a)), lum(rgb(b))].sort((m, n) => n - m); return (x + 0.05) / (y + 0.05); };

for (const dark of [false, true]) {
  const mode = dark ? 'dark' : 'light';
  const w = new JSDOM(`<!doctype html><html ${dark ? 'data-theme="dark"' : ''}><head>
    <style>${css}</style><style>${theme}</style></head><body>${modal}</body></html>`).window;
  const d = w.document;
  const cs = (sel) => w.getComputedStyle(d.querySelector(sel));
  const card = cs('.modal-content').backgroundColor;
  console.log(`\nThe editor, ${mode}`);

  ok(cs('.modal-content').borderRadius === '8px', `${mode}: the theme's 8px card, not 22px`);
  ok(cs('.modal-header').backgroundImage === 'none' || !/gradient/.test(cs('.modal-header').backgroundImage),
     `${mode}: a flat navy header, no gradient`);
  const sec = cs('label[for="questionText"]');
  ok(sec.textTransform === 'uppercase' && /JetBrains Mono/.test(sec.fontFamily), `${mode}: section labels are mono eyebrows`);
  ok(contrast(sec.color, card) >= 4.5, `${mode}: and read (${contrast(sec.color, card).toFixed(1)}:1)`);
  for (const sel of ['.survey-type-option label', 'label[for="photoRequired"]', '.survey-type-selector-header label', '.community-selector-header label']) {
    ok(cs(sel).textTransform === 'none', `${mode}: ${sel} is in sentence case (${cs(sel).textTransform})`);
  }
  const opt = cs('.survey-type-option label'), box = cs('.survey-type-selector').backgroundColor;
  ok(contrast(opt.color, box) >= 7, `${mode}: a survey type's name reads (${contrast(opt.color, box).toFixed(1)}:1)`);
  ok(cs('#questionText').borderRadius === '8px', `${mode}: inputs have 8px corners`);
  const count = cs('.selected-count');
  ok(!/gradient/.test(count.backgroundImage) && contrast(count.color, count.backgroundColor) >= 4.5,
     `${mode}: the count is a quiet tag that reads (${count.backgroundColor})`);
  const save = cs('.modal-actions .btn-success');
  const [r, g, b] = rgb(save.backgroundColor);
  ok(b > r && b > g, `${mode}: Save is the brand blue, not green (${save.backgroundColor})`);
  ok(contrast(save.color, save.backgroundColor) >= 4.5, `${mode}: and its label reads`);
}

console.log(failures ? `\n${failures} failed` : '\nall passed');
process.exit(failures ? 1 : 0);
