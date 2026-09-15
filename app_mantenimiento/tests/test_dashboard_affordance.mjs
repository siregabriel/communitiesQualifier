/*
  Whether the things on the dashboard that go somewhere look like they do.

  Lauren passed on feedback from Executive Directors asking for the Open
  Action Items number to be a link. The number was not one. But the "Needs
  you" rows above it already were — cursor, hover, and a chevron — and the
  feedback said nobody had found those either.

  So the request and the real problem are not the same size. The chevron on
  those rows sat at 1.7:1 against the card, which is not a hint, it is a
  rumour. Both are fixed here, and both are measured rather than looked at:
  "dark enough to notice" is the judgement that shipped 1.7:1.
*/

import fs from 'fs';
import { JSDOM } from 'jsdom';

const html = fs.readFileSync(new URL('../templates/dashboard.html', import.meta.url), 'utf8');

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
const decl = (selector, prop) => {
  const i = html.indexOf(selector);
  if (i < 0) return null;
  const body = html.slice(html.indexOf('{', i) + 1, html.indexOf('}', i))
                   .replace(/\/\*[\s\S]*?\*\//g, '');
  const m = body.match(new RegExp(`(?:^|;)\\s*${prop}\\s*:\\s*([^;!]+)`));
  return m ? m[1].trim() : null;
};

console.log('\nThe rows that were already clickable');
{
  // WCAG asks 3:1 for something that is not text and carries meaning.
  const light = decl('.attn-chev {', 'color');
  ok(!!light, `the chevron has a colour (${light})`);
  const ratio = contrast(light, '#ffffff');
  ok(ratio >= 3, `visible against the card (${ratio.toFixed(1)}:1, was 1.7:1)`);

  const dark = decl('html[data-theme="dark"] .attn-chev {', 'color');
  ok(!!dark, 'and one for the dark card');
  const darkRatio = contrast(dark, '#16203a');
  ok(darkRatio >= 3, `visible there too (${darkRatio.toFixed(1)}:1)`);

  ok(/\.attn-item:hover \.attn-chev\s*\{[^}]*color/.test(html),
     'and it answers when the row is under the cursor');
  ok(decl('.attn-item {', 'cursor') === 'pointer', 'the row still says it is pressable');
}

/* Build the tiles for real rather than reading the template that builds
   them. The destination is written as ${k.go}, so searching the source for
   "action-items" finds nothing and searching for the placeholder proves only
   that a placeholder is there. Render it and look at what comes out. */
const tilesHtml = (() => {
  const from = html.indexOf('const kpis = [');
  const end = html.indexOf(".join('');", from) + ".join('');".length;
  const src = html.slice(from, end);
  return new Function(`
    const avgScore = 92, visitedThisMonth = 2, totalComms = 5,
          totalActions = 3, inspectionsThisMonth = 4;
    const scoreColor = () => '#0f8a5f';
    const escapeHtmlForAttr = (s) => String(s);
    ${src}
    return kpiHtml;
  `)();
})();

const tiles = new JSDOM(`<!doctype html><body>${tilesHtml}</body>`).window.document;

console.log('\nThe tile Lauren asked about');
{
  const go = tiles.querySelector('.kpi-go');
  ok(!!go, 'the open items tile is a link now');
  ok(/openKpi\(event, 'action-items'\)/.test(go.getAttribute('onclick') || ''),
     `and it goes to Action Items (${go.getAttribute('onclick')})`);
  ok(/Open action items/i.test(go.textContent), 'and it is the open items tile');
  ok(decl('.kpi-go {', 'cursor') === 'pointer', 'it says so with the cursor');
  ok(/\.kpi-go:hover\s*\{[^}]*border-color/.test(html), 'and on hover');
  ok(!!go.querySelector('.kpi-chev'), 'with a chevron, since the number alone said nothing');

  const chev = decl('.kpi-chev {', 'color');
  ok(contrast(chev, '#ffffff') >= 3,
     `the chevron is visible (${contrast(chev, '#ffffff').toFixed(1)}:1)`);
}

console.log('\nReachable without a mouse');
{
  const go = tiles.querySelector('.kpi-go');
  ok(go.getAttribute('role') === 'button', 'it announces itself as a button');
  ok(go.getAttribute('tabindex') === '0', 'and can be tabbed to');
  ok(/Enter/.test(go.getAttribute('onkeydown') || ''), 'and answers Enter');
  ok(!!go.getAttribute('aria-label'), 'with a label that says where it goes');
  ok(/\.kpi-go:focus-visible/.test(html), 'and it shows where the keyboard is');
}

console.log('\nThe other three tiles are untouched');
{
  const plain = [...tiles.querySelectorAll('.kpi')].filter(t => !t.classList.contains('kpi-go'));
  ok(plain.length === 3, `three tiles stay as they were (${plain.length})`);
  for (const t of plain) {
    ok(!t.getAttribute('onclick') && !t.getAttribute('role'),
       `"${t.textContent.trim().split('\n').pop().trim()}" does not pretend to lead anywhere`);
  }
  ok([...tiles.querySelectorAll('.kpi')].every(t => t.getAttribute('data-kpi')),
     'and every tile keeps the attribute the saved layout is keyed on');
}

console.log('\nOnly the one that has somewhere to go');
{
  // Three of the four tiles have a plausible destination and no request
  // behind them. A tile that takes somebody somewhere they did not mean to go
  // is worse than one that does nothing.
  const block = html.slice(html.indexOf('const kpis = ['), html.indexOf('const kpiHtml'));
  const gos = block.match(/go: '/g) || [];
  ok(gos.length === 1, `exactly one tile leads anywhere (${gos.length})`);
  ok(/Open action items[^}]*go: 'action-items'/.test(block.replace(/\n/g, ' ')),
     'and it is the open items one');
}

console.log('\nReordering the dashboard still reorders it');
{
  // The drag handle is inside the tile. A click that began on it is a drag
  // being finished, not a tile being pressed — without that guard, dragging
  // the tile navigates away from the thing you were arranging.
  const grab = (name) => {
    const i = html.indexOf(`function ${name}(`);
    let p = 0, after = -1;
    for (let k = html.indexOf('(', i); k < html.length; k++) {
      if (html[k] === '(') p++;
      else if (html[k] === ')' && --p === 0) { after = k + 1; break; }
    }
    let d = 0;
    for (let k = html.indexOf('{', after); k < html.length; k++) {
      if (html[k] === '{') d++;
      else if (html[k] === '}' && --d === 0) return html.slice(i, k + 1);
    }
  };

  const dom = new JSDOM(`<!doctype html><body>
    <div class="kpi kpi-go" id="tile"><span class="dash-drag" id="handle">⠿</span>
      <div class="kpi-val" id="val">2</div></div></body>`, { runScripts: 'outside-only' });
  const w = dom.window;
  w.eval(`${grab('openKpi')}\nvar went = []; function showView(v) { went.push(v); }`);

  const fire = (id) => {
    const e = new w.MouseEvent('click', { bubbles: true });
    w.document.getElementById(id).dispatchEvent(e);
    return e;
  };
  w.document.getElementById('tile').addEventListener('click', (e) => w.openKpi(e, 'action-items'));

  fire('val');
  ok(w.eval('went').join() === 'action-items', 'pressing the number opens Action Items');

  fire('handle');
  ok(w.eval('went').join() === 'action-items',
     'and pressing the reorder handle does not — that would navigate away mid-drag');
}

console.log(failures ? `\n${failures} failure(s)` : '\nWhat leads somewhere looks like it leads somewhere.');
process.exit(failures ? 1 : 0);
