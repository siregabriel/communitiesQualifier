/*
  The sign-in page in the "Precisión" skin — measured.

  Gabriel asked whether the sign-in screen could take the design too. It had
  the old build: a near-black veil on the photo, Helvetica headings, bright
  #1f6fe5 links and focus ring, and a particle network drifting behind the
  form from an external script. Now: navy over the photo with the engineering
  grid, mono eyebrows, the app's grid behind the form, navy accents, no
  motion. In dark mode the username hint was left at its light grey on the
  dark panel; it is measured here. The page loads theme.css first and its
  own styles after, so this cascades them in that order.
*/

import fs from 'fs';
import { JSDOM } from 'jsdom';

const theme = fs.readFileSync(new URL('../static/theme.css', import.meta.url), 'utf8');
const html = fs.readFileSync(new URL('../templates/login.html', import.meta.url), 'utf8');
const css = [...html.matchAll(/<style>([\s\S]*?)<\/style>/g)].map(m => m[1]).join('\n');
const body = html.slice(html.indexOf('<body>') + 6, html.indexOf('<div id="atlertsLink"'))
  .replace(/\{%[\s\S]*?%\}/g, '').replace(/\{\{[\s\S]*?\}\}/g, '');

let failures = 0;
const ok = (c, m) => { console.log((c ? '  ok   ' : '  FAIL ') + m); if (!c) failures++; };
const rgb = (s) => (s.match(/[\d.]+/g) || [0, 0, 0]).slice(0, 3).map(Number);
const lum = ([r, g, b]) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; };
  return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
const contrast = (a, b) => { const [x, y] = [lum(rgb(a)), lum(rgb(b))].sort((m, n) => n - m); return (x + 0.05) / (y + 0.05); };

console.log('\nWhat the page is made of');
ok(!/particles/i.test(html), 'no particle network, and no external script for one');
ok(/<h1>Sign in<\/h1>/.test(html) && /<span>Sign in<\/span>/.test(html), '"Sign in" in sentence case, title and button');
ok((html.match(/class="login-eyebrow"/g) || []).length === 2, 'a mono eyebrow on each side');
ok(!/Helvetica|#1f6fe5|'Inter'/.test(css), 'no Helvetica, bright blue or Inter left in its styles');

for (const dark of [false, true]) {
  const mode = dark ? 'dark' : 'light';
  const w = new JSDOM(`<!doctype html><html ${dark ? 'data-theme="dark"' : ''}><head>
    <style>${theme}</style><style>${css}</style></head><body>${body}</body></html>`).window;
  const d = w.document;
  const cs = (sel) => w.getComputedStyle(d.querySelector(sel));
  const panel = cs('.login-right').backgroundColor;
  console.log(`\nThe form, ${mode}`);
  ok(/linear-gradient/.test(cs('.login-right').backgroundImage), `${mode}: the app's grid behind the form`);
  ok(/JetBrains Mono/.test(cs('.login-right .login-eyebrow').fontFamily), `${mode}: the eyebrow is mono`);
  for (const sel of ['.login-card h1', '.form-group label', '.form-group .help', '.login-right .login-eyebrow', '.forgot-row a']) {
    const c = contrast(cs(sel).color, panel);
    ok(c >= 4.5, `${mode}: ${sel} reads on the panel (${c.toFixed(1)}:1)`);
  }
  const btn = cs('.submit-btn');
  ok(btn.backgroundColor === 'rgb(0, 51, 102)', `${mode}: the button is the brand navy (${btn.backgroundColor})`);
  ok(cs('.theme-toggle-float').borderRadius === '8px', `${mode}: the theme button has the theme's corner`);
}

console.log('\nSetting a new password (the screen after a reset)');
{
  // Found in the final check: it still showed the old "Atlas Standards"
  // wordmark, Inter, a 16px card and bright-blue links.
  const cp = fs.readFileSync(new URL('../templates/change_password.html', import.meta.url), 'utf8');
  const cpCss = [...cp.matchAll(/<style>([\s\S]*?)<\/style>/g)].map(m => m[1]).join('\n');
  const logo = (cp.match(/class="cp-logo" src="\/static\/([^"]+)"/) || [])[1];
  ok(logo === 'arlas-excellence-logo.png', `it shows the Atlas Excellence wordmark (${logo})`);
  ok(logo && fs.existsSync(new URL('../static/' + logo, import.meta.url)), 'and the file is there');
  ok(!/'Inter'|#1f6fe5|border-radius: 1[0-9]px/.test(cpCss), 'no Inter, bright blue or round 10-16px corners left');
  for (const dark of [false, true]) {
    const mode = dark ? 'dark' : 'light';
    const body = cp.slice(cp.indexOf('<body>') + 6, cp.indexOf('<script>', cp.indexOf('<body>'))).replace(/\{%[\s\S]*?%\}/g, '').replace(/\{\{[\s\S]*?\}\}/g, '');
    const w = new JSDOM(`<!doctype html><html ${dark ? 'data-theme="dark"' : ''}><head><style>${cpCss}</style></head><body>${body}</body></html>`).window;
    const cs = (sel) => w.getComputedStyle(w.document.querySelector(sel));
    const card = cs('.cp-card').backgroundColor;
    for (const sel of ['h1', '.cp-sub', '.cp-eyebrow', 'label', '.cp-alt a']) {
      const c = contrast(cs(sel).color, card);
      ok(c >= 4.5, `${mode}: ${sel} reads on the card (${c.toFixed(1)}:1)`);
    }
  }
}

console.log(failures ? `\n${failures} failed` : '\nall passed');
process.exit(failures ? 1 : 0);
