/*
  Text is escaped twice, so people read entities instead of words.

  The server runs html.escape on the way in, so a comment typed as
  "Angie's walk through" is stored as "Angie&#x27;s walk through". Every render
  path then escapes it again, turning the & into &amp; and putting the entity
  itself on screen. That is what was reported: "Angie&#x27;s walk through".

  Undoing the first escaping is easy to get dangerously wrong — the obvious way
  is to assign innerHTML and read textContent back, which lets an <img onerror>
  fire on the way through even on a detached node. So this checks two things at
  once: that what the person typed is what appears, and that a payload still
  comes out inert.

  The real functions are pulled from the templates and run; nothing here is a
  copy of them.
*/

import fs from 'fs';
import { JSDOM } from 'jsdom';

let failures = 0;
const ok = (c, m) => { console.log((c ? '  ok   ' : '  FAIL ') + m); if (!c) failures++; };

const TEMPLATES = ['dashboard.html', 'question_manager.html', 'reporte.html'];

/* What the server stores, given what the person typed. Mirrors html.escape:
   & first, then the rest. */
const stored = (typed) => typed
  .replace(/&/g, '&amp;')
  .replace(/</g, '&lt;')
  .replace(/>/g, '&gt;')
  .replace(/"/g, '&quot;')
  .replace(/'/g, '&#x27;');

const TYPED = [
  ["Angie's walk through", 'an apostrophe — the one that was reported'],
  ['Tom & Jerry Dining Room', 'an ampersand'],
  ['He said "looks good"', 'double quotes'],
  ['2nd floor < 3rd floor', 'a less-than sign'],
  ['Resident’s room is ready', 'a curly apostrophe, which was never escaped'],
  ['Painted; touched up. 100% done', 'ordinary text with no entities at all'],
];

for (const tpl of TEMPLATES) {
  console.log(`\n${tpl}`);
  const html = fs.readFileSync(new URL(`../templates/${tpl}`, import.meta.url), 'utf8');

  const grab = (name) => {
    const i = html.indexOf(`function ${name}(`);
    if (i < 0) return null;
    let depth = 0;
    for (let k = html.indexOf('{', i); k < html.length; k++) {
      if (html[k] === '{') depth++;
      else if (html[k] === '}' && --depth === 0) return html.slice(i, k + 1);
    }
    return null;
  };

  const src = [grab('decodeEntities'), grab('escapeHtml')];
  if (!src[0] || !src[1]) {
    ok(false, 'has both decodeEntities and escapeHtml');
    continue;
  }

  const dom = new JSDOM('<!doctype html><body><div id="out"></div></body>',
                        { runScripts: 'outside-only' });
  const w = dom.window;
  w.eval(src.join('\n'));

  // Render the way the app does: the escaped string goes into innerHTML.
  const render = (value) => {
    const el = w.document.getElementById('out');
    el.innerHTML = w.escapeHtml(value);
    return el.textContent;
  };

  for (const [typed, what] of TYPED) {
    const shown = render(stored(typed));
    ok(shown === typed, `${what} — reads back as typed (${JSON.stringify(shown)})`);
  }

  console.log('  and a payload still comes out inert');
  for (const payload of ['<img src=x onerror="window.__pwned=1">',
                         '<script>window.__pwned=1<\/script>',
                         '<svg onload="window.__pwned=1">']) {
    const el = w.document.getElementById('out');
    el.innerHTML = w.escapeHtml(stored(payload));
    ok(el.querySelector('img,script,svg') === null,
       `  ${payload.slice(0, 26)}… stays text, no element is built`);
    ok(el.textContent === payload, '  and shows exactly what was typed');
  }
  // Nothing anywhere in this template's run should have executed.
  ok(w.__pwned === undefined, '  nothing ran');

  // The order matters: &amp; has to be undone last, or a person who typed the
  // characters "&lt;" would have them turn into a real "<".
  ok(render(stored('&lt;')) === '&lt;',
     'someone typing "&lt;" literally still sees "&lt;"');
}

console.log(failures ? `\n${failures} failure(s)` : '\nWhat people type is what they read.');
process.exit(failures ? 1 : 0);
