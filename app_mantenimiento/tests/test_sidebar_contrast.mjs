/*
  The sidebar labels, measured rather than read.

  The current section is a filled pill. Getting the fill right and the text
  wrong is easy here, because theme.css carries `.sidebar * { color: #1f2937
  !important }` — a rule that hits the label <span> directly, and a direct
  match beats anything the anchor passes down. The first attempt set the colour
  on the link only, so the pill went dark and the word stayed dark with it.

  String checks missed that entirely: every declaration was present and
  correct. So this loads both stylesheets, builds the real markup, and asks the
  browser engine what colour the text actually ends up.
*/

import fs from 'fs';
import { JSDOM } from 'jsdom';

const theme = fs.readFileSync(new URL('../static/theme.css', import.meta.url), 'utf8');
const html = fs.readFileSync(new URL('../templates/dashboard.html', import.meta.url), 'utf8');
const head = html.slice(html.indexOf('<style>') + 7, html.indexOf('</style>'));

let failures = 0;
const ok = (c, m) => { console.log((c ? '  ok   ' : '  FAIL ') + m); if (!c) failures++; };

function build(mode) {
  const dom = new JSDOM(`<!doctype html><html${mode ? ` data-theme="${mode}"` : ''}>
    <head><style>${head}</style><style>${theme}</style></head><body>
    <div class="sidebar"><nav class="navigation-menu">
      <a class="nav-item active" data-view="my-visits"><i class="fas fa-file-alt"></i><span>My Visits</span></a>
      <a class="nav-item" data-view="communities"><i class="fas fa-building"></i><span>Communities</span></a>
      <a class="nav-item" href="/logout"><i class="fas fa-right-from-bracket"></i><span>Log Out</span></a>
    </nav></div></body></html>`);
  return dom.window;
}

const rgb = (s) => (s.match(/\d+/g) || [0, 0, 0]).slice(0, 3).map(Number);
const lum = ([r, g, b]) => {
  const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
  return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
};
/* WCAG contrast ratio. 4.5 is the threshold for body text. */
const contrast = (fg, bg) => {
  const [a, b] = [lum(rgb(fg)), lum(rgb(bg))].sort((x, y) => y - x);
  return (a + 0.05) / (b + 0.05);
};

/* Light mode is measured for real. jsdom resolves the cascade by document
   order rather than by specificity, and theme.css is loaded second — which
   happens to give the same answer a browser would here, since the winning
   rule is both later and more specific. Dark mode is the opposite case: its
   rules sit in the first stylesheet and win on specificity alone, which jsdom
   would get wrong, so it is checked by rule below instead of measured. */
console.log('\nSidebar — light mode, measured');
{
  const w = build(null);
  const d = w.document;
  const g = (sel) => w.getComputedStyle(d.querySelector(sel));

  const pill = g('.nav-item.active');
  const text = g('.nav-item.active span');
  const icon = g('.nav-item.active i');

  const ratio = contrast(text.color, pill.backgroundColor);
  ok(ratio >= 4.5,
     `the current section's label is readable on its fill (${ratio.toFixed(1)}:1, needs 4.5)`);
  ok(contrast(icon.color, pill.backgroundColor) >= 4.5, 'and so is its icon');
  ok(text.color === pill.color,
     `the label matches the link it sits in (${text.color} vs ${pill.color})`);

  const rest = g('.nav-item:not(.active) span');
  const panel = w.getComputedStyle(d.querySelector('.sidebar')).backgroundColor;
  ok(contrast(rest.color, panel) >= 4.5,
     `an unselected section is readable on the panel (${contrast(rest.color, panel).toFixed(1)}:1)`);
}

console.log('\nSidebar — dark mode, by rule');
{
  // The trap is the same one, mirrored: `html[data-theme="dark"] .sidebar *`
  // paints the label near-white, and the dark pill is a LIGHT fill. Without
  // naming the children, that is white text on a near-white pill.
  ok(/html\[data-theme="dark"\] \.nav-item\.active \*/.test(html),
     'the dark rules name the label, not just the link');
  const darkBlock = html.slice(html.indexOf('html[data-theme="dark"] .nav-item.active,'));
  ok(/color:\s*#0f1e36\s*!important/.test(darkBlock.slice(0, 400)),
     'and give it dark text, because the dark pill is a light fill');
  ok(/background:\s*#e8eefc/.test(darkBlock.slice(0, 700)),
     'a near-black pill would vanish on a dark sidebar, so it inverts');
}

/* Hover is a pseudo-class jsdom cannot enter, so that one state is held down
   by checking the rule names the children as well as the link. */
console.log('\nSidebar — hover');
{
  ok(/\.nav-item:hover,\s*\.nav-item:hover \*/.test(theme),
     'hover colours the label too, not just the link around it');
  ok(/\.nav-item\.active \*/.test(theme),
     'and so does the current section — the label is a span, and .sidebar * outranks inheritance');
}

console.log(failures ? `\n${failures} failure(s)` : '\nEvery sidebar label is readable where it sits.');
process.exit(failures ? 1 : 0);
