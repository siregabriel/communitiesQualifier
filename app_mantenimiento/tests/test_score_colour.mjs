/*
  One colour per score band, readable as text — measured in both themes.

  Found while reskinning the community panel: its History printed a 67% in
  #b58b00, about 3:1 on white, and N/A in #94a3b8 (2.6:1). The same hexes
  were written in four places in the dashboard — the home, the panel's
  history, a person's profile, a region, the calendar — so fixing one would
  have left three. There is now one scoreColor(); the others call it. It
  returns CSS variables, because the colours go inline and an inline hex
  cannot follow the theme when somebody switches it; --score-* are defined
  in theme.css for light and dark, and checked here on each card surface.
*/

import fs from 'fs';
import { JSDOM } from 'jsdom';

const theme = fs.readFileSync(new URL('../static/theme.css', import.meta.url), 'utf8');
const html = fs.readFileSync(new URL('../templates/dashboard.html', import.meta.url), 'utf8');

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
const hex = (h) => { h = h.trim().replace('#', ''); return [0, 2, 4].map(i => parseInt(h.slice(i, i + 2), 16)); };
const lum = ([r, g, b]) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; };
  return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
const contrast = (a, b) => { const [x, y] = [lum(a), lum(b)].sort((m, n) => n - m); return (x + 0.05) / (y + 0.05); };

console.log('\nOne helper');
const code = html.slice(html.indexOf('<script>'));
ok(!/return[^;]*#b58b00|=>\s*\(v == null \? '#94a3b8'/.test(code), 'no copy still returns the old hexes');
const w = new JSDOM('<!doctype html><body></body>', { runScripts: 'outside-only' }).window;
w.eval(`${grab('scoreColor')}\n${grab('_calScoreColor')}`);
for (const v of [null, 40, 60, 90]) {
  ok(w.eval(`_calScoreColor(${v})`) === w.eval(`scoreColor(${v})`), `the calendar agrees with the rest at ${v}`);
}
ok((code.match(/const sc = scoreColor;/g) || []).length === 2, 'the profile and region screens use it too');

for (const dark of [false, true]) {
  const mode = dark ? 'dark' : 'light';
  const d = new JSDOM(`<!doctype html><html ${dark ? 'data-theme="dark"' : ''}><head><style>${theme}</style></head><body></body></html>`).window;
  const root = d.getComputedStyle(d.document.documentElement);
  const card = dark ? '#161f2e' : '#ffffff';
  console.log(`\nAs text on a card, ${mode}`);
  for (const [v, band] of [[90, 'pass'], [60, 'warn'], [40, 'fail'], [null, 'na']]) {
    const ref = w.eval(`scoreColor(${v})`);
    const name = (ref.match(/var\((--[\w-]+)\)/) || [])[1];
    const col = name && root.getPropertyValue(name);
    ok(!!col, `${mode}: ${band} resolves (${ref} = ${col})`);
    if (col) {
      const c = contrast(hex(col), hex(card));
      ok(c >= 4.5, `${mode}: ${v === null ? 'N/A' : v + '%'} reads (${c.toFixed(1)}:1)`);
    }
  }
}

console.log(failures ? `\n${failures} failed` : '\nall passed');
process.exit(failures ? 1 : 0);
