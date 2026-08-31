/*
  The dashboard mini-calendar, measured rather than read.

  A day with something scheduled is a filled chip. In the light skin the fill
  is near-white and the number is navy. The dark skin lifted the number to
  #eef2f8 and left the fill alone, so the number sat on a near-white chip and
  vanished — every declaration present, every one of them correct on its own.
  Only asking what the two colours end up being together catches that.

  Unlike the sidebar, the dark rules for this live in theme.css, which is the
  second stylesheet — so jsdom resolving the cascade by document order lands on
  the same answer a real browser would, and measuring is meaningful here.
*/

import fs from 'fs';
import { JSDOM } from 'jsdom';

const theme = fs.readFileSync(new URL('../static/theme.css', import.meta.url), 'utf8');
const html = fs.readFileSync(new URL('../templates/dashboard.html', import.meta.url), 'utf8');
const head = html.slice(html.indexOf('<style>') + 7, html.indexOf('</style>'));

let failures = 0;
const ok = (c, m) => { console.log((c ? '  ok   ' : '  FAIL ') + m); if (!c) failures++; };

const rgb = (s) => (s.match(/\d+/g) || [0, 0, 0]).slice(0, 3).map(Number);
const lum = ([r, g, b]) => {
  const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
  return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
};
const contrast = (fg, bg) => {
  const [a, b] = [lum(rgb(fg)), lum(rgb(bg))].sort((x, y) => y - x);
  return (a + 0.05) / (b + 0.05);
};

/* The card the calendar sits on. A chip with no fill of its own has to be
   measured against what is actually behind it, not against transparent.

   .dash-card's own fill is declared inside a media query, which jsdom does not
   apply, so it cannot be read from the harness. Take the dark surface the
   theme defines for cards instead of writing a colour in here by hand — a
   hard-coded one would keep reporting a comfortable ratio long after the theme
   moved. It is also the lightest surface the calendar can sit on, so it is the
   least forgiving backdrop for light text: pass here and the real one passes. */
const darkCard = (theme.match(
  /html\[data-theme="dark"\] \.card,[\s\S]*?background:\s*(#[0-9a-fA-F]{6})/) || [])[1];
if (!darkCard) {
  console.log('  FAIL could not find the dark card surface in theme.css');
  process.exit(1);
}
const hexToRgb = (h) => `rgb(${parseInt(h.slice(1, 3), 16)}, ${parseInt(h.slice(3, 5), 16)}, ${parseInt(h.slice(5, 7), 16)})`;
const CARD = { dark: hexToRgb(darkCard), light: 'rgb(255, 255, 255)' };

function build(mode) {
  const dom = new JSDOM(`<!doctype html><html${mode === 'dark' ? ' data-theme="dark"' : ''}>
    <head><style>${head}</style><style>${theme}</style></head>
    <body><div class="main-content"><div class="dash-card">
      <div class="mini-cal-grid">
        <div class="mini-cal-cell" id="plain"><span class="mini-daynum">12</span></div>
        <div class="mini-cal-cell mini-has" id="has"><span class="mini-daynum">17</span>
          <span class="mini-dots"><span class="cal-dot"></span></span></div>
        <div class="mini-cal-cell mini-today" id="today"><span class="mini-daynum">31</span></div>
        <div class="mini-cal-cell mini-today mini-has" id="both"><span class="mini-daynum">31</span>
          <span class="mini-dots"><span class="cal-dot"></span></span></div>
      </div>
    </div></div></body></html>`);
  return dom.window;
}

for (const mode of ['dark', 'light']) {
  console.log(`\nMini-calendar — ${mode} mode, measured`);
  const w = build(mode);
  const d = w.document;
  const card = CARD[mode];
  // What is actually behind the number: the chip's own fill, or the card when
  // the chip has none.
  const behind = (id) => {
    const bg = w.getComputedStyle(d.getElementById(id)).backgroundColor;
    return (!bg || bg === 'transparent' || /rgba\(0, 0, 0, 0\)/.test(bg)) ? card : bg;
  };
  const ink = (id) => w.getComputedStyle(d.getElementById(id)).color;

  for (const [id, what] of [['plain', 'an ordinary day'],
                            ['has', 'a day with something on it'],
                            ['today', 'today'],
                            ['both', 'today, with something on it']]) {
    const ratio = contrast(ink(id), behind(id));
    ok(ratio >= 4.5,
       `${what} is legible (${ratio.toFixed(1)}:1, needs 4.5) — ${ink(id)} on ${behind(id)}`);
  }

  if (mode === 'dark') {
    // The ring is the only thing marking today, and it started out #00285c —
    // near-black against a dark card. jsdom does not resolve box-shadow into
    // computed style (it comes back empty), so this reads the declaration
    // rather than measuring it, and says so instead of quietly passing.
    const rule = (theme.match(
      /html\[data-theme="dark"\] \.mini-cal-cell\.mini-today\s*\{[^}]*\}/) || [''])[0];
    const colour = (rule.match(/box-shadow:[^;]*?(#[0-9a-fA-F]{6})/) || [])[1];
    ok(!!colour, `today's ring is restyled for dark (${colour || 'no rule found'})`);
    ok(colour && contrast(hexToRgb(colour), card) >= 3,
       colour ? `and stands out against the card (${contrast(hexToRgb(colour), card).toFixed(1)}:1)`
              : 'and stands out against the card');
  }
}

console.log(failures ? `\n${failures} failure(s)` : '\nEvery day in the calendar can be read.');
process.exit(failures ? 1 : 0);
