/*
  Add / Edit person in the "Precisión" skin — rendered and measured.

  Gabriel: the Add person window still had the old build — a 16px card, a
  grey close tile, an 800-weight title and bold grey labels written inline,
  native selects, 9px lists, and the "beyond the role" permissions in a
  cream box with gold text. This renders the real openAddPerson() with the
  page's styles and the theme, light and dark, and measures it.
*/

import fs from 'fs';
import { JSDOM } from 'jsdom';

const theme = fs.readFileSync(new URL('../static/theme.css', import.meta.url), 'utf8');
const html = fs.readFileSync(new URL('../templates/dashboard.html', import.meta.url), 'utf8');
const head = html.slice(html.indexOf('<style>') + 7, html.indexOf('</style>'));
const modal = html.slice(html.indexOf('<div id="personModal"'), html.indexOf('</div>\n    </div>', html.indexOf('<div id="personModal"')) + 18);

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
    <style>${head}</style><style>${theme}</style></head><body>${modal}</body></html>`, { runScripts: 'outside-only' }).window;
  w.eval(`
    var peopleData = { regions: [{ id: 'coastal', name: 'Coastal' }], communities: ['Kelley Place, Enterprise'], team_positions: ['Chef'] };
    function escapeHtml(s) { return String(s); }
    function fillPositionSelect() {} function apOnRoleChange() {} function apRenderExtraComms() {}
    ${grab('openAddPerson')}
    openAddPerson();
    // A "beyond the role" box, as Edit person draws it.
    document.querySelector('.pf-grid').insertAdjacentHTML('beforeend',
      '<div class="pe-priv"><label class="pe-priv-row"><input type="checkbox"><span><b>Can visit every community</b><small>Stays in their region.</small></span></label></div>');
  `);
  const d = w.document;
  const cs = (sel) => w.getComputedStyle(d.querySelector(sel));
  // In dark the card is var(--surface) inside a background shorthand, which
  // jsdom drops (a browser shows #161f2e); use the real value.
  const card = dark ? 'rgb(22, 31, 46)' : cs('.pm-card').backgroundColor;
  console.log(`\nAdd person, ${mode}`);

  ok(!d.querySelector('.pf [style*="font-size"], .pf [style*="color:"]'), `${mode}: no colours or sizes written inline`);
  ok(cs('.pm-card').borderRadius === '8px', `${mode}: the theme's 8px card`);
  ok(/JetBrains Mono/.test(cs('.pf-eyebrow').fontFamily) && cs('.pf-eyebrow').textTransform === 'uppercase', `${mode}: a mono eyebrow over the title`);
  for (const sel of ['.pf-title', '.pf .mi-label']) {
    ok(contrast(cs(sel).color, card) >= 7, `${mode}: ${sel} reads (${contrast(cs(sel).color, card).toFixed(1)}:1)`);
  }
  ok(contrast(cs('.pf-sub').color, card) >= 4.5 && contrast(cs('.pf-note').color, card) >= 4.5, `${mode}: so do the help lines`);
  ok(cs('.pf .pw-input').borderRadius === '8px', `${mode}: fields have the 8px corner`);
  ok(/svg/.test(cs('.pf select.pw-input').backgroundImage), `${mode}: selects draw the theme's chevron`);
  ok(cs('.pf-actions').borderTopStyle === 'solid', `${mode}: the buttons sit on a hairline footer`);
  const priv = cs('.pf .pe-priv'), b = cs('.pf .pe-priv-row b');
  ok(contrast(b.color, priv.backgroundColor) >= 7, `${mode}: a permission's title is ink, not gold (${contrast(b.color, priv.backgroundColor).toFixed(1)}:1)`);
  ok(/inset/.test(priv.boxShadow), `${mode}: and the amber stays as a rail`);
}

console.log(failures ? `\n${failures} failed` : '\nall passed');
process.exit(failures ? 1 : 0);
