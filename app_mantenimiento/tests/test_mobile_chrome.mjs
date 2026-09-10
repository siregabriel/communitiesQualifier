/*
  What a phone actually shows: the menu button, the tab bar, the background.

  Three complaints from one screenshot, and the first is a shape this project
  has now hit three times. A dark-mode rule lifts the ink and leaves the
  surface behind: the sidebar labels, then the calendar chips, now the
  floating menu button — an <i> inside .main-content, caught by the catch-all
  that lifts every icon to #d7e0ec, sitting on a background still declared
  white. White on white, and only on a phone in dark mode, which is the corner
  nobody looks at.

  Contrast is measured here rather than eyeballed. "Looks dark enough" is what
  shipped #8a97a8 tab icons at 2.6:1.
*/

import fs from 'fs';
import { JSDOM } from 'jsdom';

const theme = fs.readFileSync(new URL('../static/theme.css', import.meta.url), 'utf8');
const dash = fs.readFileSync(new URL('../templates/dashboard.html', import.meta.url), 'utf8');
const tabbar = fs.readFileSync(new URL('../templates/mobile_tabbar.html', import.meta.url), 'utf8');
const head = dash.slice(dash.indexOf('<style>') + 7, dash.indexOf('</style>'));

let failures = 0;
const ok = (c, m) => { console.log((c ? '  ok   ' : '  FAIL ') + m); if (!c) failures++; };

const hex = (h) => {
  h = h.replace('#', '');
  if (h.length === 3) h = h.split('').map(c => c + c).join('');
  return [0, 2, 4].map(i => parseInt(h.slice(i, i + 2), 16));
};
const lum = ([r, g, b]) => {
  const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
  return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
};
const contrast = (fg, bg) => {
  const [a, b] = [lum(hex(fg)), lum(hex(bg))].sort((x, y) => y - x);
  return (a + 0.05) / (b + 0.05);
};

// Pull one declaration out of a rule, by selector.
//
// Comments come out of the body first: a rule whose first line is a comment
// ends that comment where this expected a semicolon, so it reported the
// declaration as missing — which reads as the stylesheet having lost it,
// rather than as the reader being wrong.
//
// Written with line comments on purpose. Explaining the problem inside a
// block comment meant writing the comment-closing token in the prose, which
// closed the comment early and broke the file.
function decl(css, selector, prop) {
  const i = css.indexOf(selector);
  if (i < 0) return null;
  const body = css.slice(css.indexOf('{', i) + 1, css.indexOf('}', i))
                  .replace(/\/\*[\s\S]*?\*\//g, '');
  const m = body.match(new RegExp(`(?:^|;)\\s*${prop}\\s*:\\s*([^;!]+)`));
  return m ? m[1].trim() : null;
}

console.log('\nThe menu button on a dark phone');
{
  // The catch-all that caused it, so the test says why the rule below exists.
  ok(/data-theme="dark"\][^{]*:where\(\.main-content[^{]*\)\s*:where\([^)]*\bi\b/.test(theme),
     'the catch-all still lifts every icon inside .main-content');

  const bg = decl(theme, 'html[data-theme="dark"] .mobile-menu-toggle {', 'background');
  ok(bg && /#[0-9a-f]{6}/i.test(bg), `and the button brings its own dark surface (${bg})`);

  const fg = decl(theme, 'html[data-theme="dark"] .mobile-menu-toggle,', 'color')
          || decl(theme, 'html[data-theme="dark"] .mobile-menu-toggle i', 'color');
  ok(!!fg, 'with an explicit colour for the icon');

  const ratio = contrast(fg.match(/#[0-9a-f]{6}/i)[0], bg.match(/#[0-9a-f]{6}/i)[0]);
  ok(ratio >= 4.5, `the three lines are readable on it (${ratio.toFixed(1)}:1, needs 4.5)`);

  // The rule has to name the <i> too. Setting colour on the button alone was
  // what failed for the sidebar: a direct match on the child beats anything
  // the parent passes down.
  ok(/\.mobile-menu-toggle i\b/.test(theme),
     'and it names the icon, not just the button — the catch-all matches the <i> directly');
}

console.log('\nThe tab bar in light mode');
{
  const ic = decl(tabbar, '.mtab-ic {', 'color');
  const lb = decl(tabbar, '.mtab-lb {', 'color');
  ok(ic === lb, `the icon and its label are the same colour (${ic} / ${lb})`);

  // The bar is translucent white over the page; take the lighter end of what
  // sits behind it, which is the least forgiving case.
  const ratio = contrast(ic, '#f4f8fd');
  ok(ratio >= 4.5, `and dark enough to read on the glass (${ratio.toFixed(1)}:1, needs 4.5)`);

  ok(contrast(ic, '#f4f8fd') > contrast('#8a97a8', '#f4f8fd'),
     'darker than the grey that was there');
}

console.log('\nThe background on a phone');
{
  // The layer starts 260px in so it never tints the sidebar. On a phone the
  // sidebar is off-canvas and that offset stayed, so the colour began two
  // thirds across and left a hard vertical seam.
  const off = decl(theme, '.main-content::before {', 'left');
  ok(off === '260px', `the offset that causes it is still there on desktop (${off})`);

  const mobile = theme.slice(theme.indexOf('@media (max-width: 768px)',
                             theme.indexOf('.main-content::before')));
  const block = mobile.slice(0, mobile.indexOf('}', mobile.indexOf('}') + 1) + 1);
  ok(/\.main-content::before\s*\{[^}]*display:\s*none/.test(block),
     'and the layer is off below 768px, so there is no seam to see');
}

console.log('\nIt still looks like something on a phone');
{
  // Turning the layer off must not leave a blank white page: the static wash
  // on .main-content is what carries it from there, in both themes.
  const light = decl(theme, '.main-content {', 'background');
  ok(/linear-gradient/.test(light || ''), 'the light wash is still on .main-content');

  const dark = decl(theme, 'html[data-theme="dark"] .main-content {', 'background');
  ok(/linear-gradient/.test(dark || ''), 'and the dark one too');
}

console.log('\nAnd the page still parses');
{
  const dom = new JSDOM(`<!doctype html><html><head><style>${head}</style>
    <style>${theme}</style></head><body><div class="main-content"></div></body></html>`);
  ok(!!dom.window.document.querySelector('.main-content'), 'the stylesheets load without error');
}

console.log(failures ? `\n${failures} failure(s)` : '\nA phone shows one background and a button you can see.');
process.exit(failures ? 1 : 0);
