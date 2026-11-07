/*
  The "Precisión" skin on a phone — computed, with the phone rules switched on.

  Gabriel sent a phone screenshot of the visit form (capitals, its own
  colours, a header whose Logout fell off the screen) and asked for a
  complete pass on mobile. Walking every screen at 390px found more: each
  section opened with ~330px of stacked buttons, Settings and Standards ran
  off the right edge, amber score text at 2-3:1, and in dark mode the form's
  titles went dark on a dark card, and a caption rule for <label> turned
  the navy "Add Photo" button's text dark too (a <label> as well). Reworking the header row then hid a trap,
  caught by eye before it shipped: forcing the square buttons to
  `display: inline-flex !important` showed Question Manager to a regional,
  because the page hides it with an inline display:none.

  jsdom has no media queries, so this unwraps the theme's phone blocks
  (max-width 768px and narrower) and applies them as a phone would. It has no
  layout either: whether things fit is still a human look; what is measured
  here is what the cascade decides.
*/

import fs from 'fs';
import { JSDOM } from 'jsdom';

const theme = fs.readFileSync(new URL('../static/theme.css', import.meta.url), 'utf8');
const dash = fs.readFileSync(new URL('../templates/dashboard.html', import.meta.url), 'utf8');
const rep = fs.readFileSync(new URL('../templates/reporte.html', import.meta.url), 'utf8');
const dashHead = dash.slice(dash.indexOf('<style>') + 7, dash.indexOf('</style>'));
const repCss = [...rep.matchAll(/<style>([\s\S]*?)<\/style>/g)].map(m => m[1]).join('\n');

let failures = 0;
const ok = (c, m) => { console.log((c ? '  ok   ' : '  FAIL ') + m); if (!c) failures++; };

/* Replace each `@media (max-width: N px) { … }` with its body when N ≤ 768,
   so jsdom applies it; wider ones are left as they are (ignored). */
function asPhone(css) {
  let out = '', i = 0;
  const re = /@media\s*\(max-width:\s*(\d+)px\)\s*\{/g;
  let m;
  while ((m = re.exec(css))) {
    if (Number(m[1]) > 768) continue;
    let depth = 1, k = re.lastIndex;
    for (; k < css.length && depth; k++) {
      if (css[k] === '{') depth++;
      else if (css[k] === '}') depth--;
    }
    out += css.slice(i, m.index) + css.slice(re.lastIndex, k - 1);
    i = k; re.lastIndex = k;
  }
  return out + css.slice(i);
}

const rgb = (s) => (s.match(/[\d.]+/g) || [0, 0, 0]).slice(0, 3).map(Number);
const lum = ([r, g, b]) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; };
  return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
const contrast = (a, b) => { const [x, y] = [lum(rgb(a)), lum(rgb(b))].sort((m, n) => n - m); return (x + 0.05) / (y + 0.05); };

// The real header, as the template writes it.
const header = dash.slice(dash.indexOf('<div class="header-section">'), dash.indexOf('<div class="filter-section">'));

for (const dark of [false, true]) {
  const mode = dark ? 'dark' : 'light';
  const w = new JSDOM(`<!doctype html><html ${dark ? 'data-theme="dark"' : ''}><head>
    <style>${asPhone(dashHead)}</style><style>${asPhone(theme)}</style></head><body>
    <div class="main-content"><div class="dashboard-container">${header}</div>
      <div class="profile-wrap"><div class="set-grid"><div class="profile-section"></div></div></div>
      <div class="slide-panel"><div class="slide-panel-header"><button class="slide-panel-close"><i class="fas fa-xmark"></i></button></div>
        <div class="panel-stats"><div class="panel-stat-card"><div class="panel-stat-label">Score</div>
          <div class="panel-stat-value warning">67%</div></div></div></div>
      <div class="region-card"><div class="region-stats"><div class="region-stat">
        <div class="region-stat-value rs-warn">64%</div><div class="region-stat-label">Avg score</div></div></div></div>
    </div></body></html>`).window;
  const d = w.document;
  const cs = (sel) => w.getComputedStyle(d.querySelector(sel));
  console.log(`\nThe section header on a phone, ${mode}`);

  ok(cs('.header-actions').order === '-1', `${mode}: the buttons are one row above the title`);
  ok(cs('.header-actions').flexWrap === 'nowrap', `${mode}: and stay on one line`);
  const help = cs('#headerHelpBtn');
  ok(help.width === '40px' && help.fontSize === '0px', `${mode}: each is a 40px square, its label kept for screen readers`);
  ok(/Help/.test(d.getElementById('headerHelpBtn').textContent), `${mode}: the label is still in the markup`);
  ok(cs('#questionManagerBtn').display === 'none',
     `${mode}: Question Manager stays hidden until the page shows it (${cs('#questionManagerBtn').display})`);
  d.getElementById('questionManagerBtn').style.display = 'inline-block';     // what the page does for an admin
  ok(cs('#questionManagerBtn').display === 'inline-flex', `${mode}: and is a square once shown`);
  d.getElementById('headerHelpBtn').style.display = 'none';                  // a view with no tour
  ok(cs('#headerHelpBtn').display === 'none', `${mode}: Help hides where there is no tour`);
  ok(cs('.header-left').alignItems === 'flex-start', `${mode}: the title is left-aligned, as in the mock-up`);

  console.log(`\nNothing pushes the page sideways, ${mode}`);
  ok(cs('.set-grid > .profile-section').minWidth === '0px' && cs('.profile-wrap').minWidth === '0px',
     `${mode}: Settings' cards may shrink to the screen`);

  console.log(`\nNumbers that read, ${mode}`);
  const card = cs('.panel-stat-card').backgroundColor;
  const v = cs('.panel-stat-value.warning');
  ok(contrast(v.color, card) >= 4.5, `${mode}: a middling score in the visit panel reads (${contrast(v.color, card).toFixed(1)}:1)`);
  const rs = cs('.region-stat');
  ok(contrast(cs('.rs-warn').color, rs.backgroundColor) >= 4.5,
     `${mode}: and in Regions (${contrast(cs('.rs-warn').color, rs.backgroundColor).toFixed(1)}:1)`);
  ok(rs.flexDirection === 'column-reverse', `${mode}: label above the number`);
  // jsdom hands repeat() back as written.
  ok(/^repeat\(2,/.test(cs('.panel-stats').gridTemplateColumns), `${mode}: the panel's two numbers sit side by side`);
}

console.log('\nThe visit form');
for (const dark of [false, true]) {
  const mode = dark ? 'dark' : 'light';
  const w = new JSDOM(`<!doctype html><html ${dark ? 'data-theme="dark"' : ''}><head>
    <style>${asPhone(repCss)}</style><style>${asPhone(theme)}</style></head>
    <body class="visit-page"><div class="container">
      ${rep.slice(rep.indexOf('<div class="header">'), rep.indexOf('<div class="success-message"'))}
      <div class="form-group"><label for="c">Community to inspect</label><select id="c"><option>A</option></select></div>
      <div class="progress-bar-container show"><div class="progress-title">Visit Progress</div>
        <div class="progress-bar"><div class="progress-fill" style="width: 40%">40%</div></div>
        <div class="progress-message warning">40% positive.</div></div>
      <div class="question-section" id="q1"><div class="question-title">Lobby is clean</div>
        <span class="response-label">Response</span>
        <div class="condition-rating">
          <label class="radio-button"><input type="radio" name="a" value="Pass"><span class="radio-label pass">Pass</span></label>
          <label class="radio-button"><input type="radio" name="a" value="Fail" checked><span class="radio-label fail">Fail</span></label>
          <label class="radio-button rb-notchecked"><input type="radio" name="a" value="Not checked"><span class="radio-label notchecked">Not checked</span></label>
        </div></div>
      <div class="question-section" id="q3">
        <label class="dc-label">Direct comment to <span class="dc-opt">(optional)</span></label>
        <div class="file-upload-wrapper" id="ev1"><label for="p" class="file-upload-label"><i class="fas fa-camera"></i> Add Photo</label>
          <div class="file-name"></div><div class="image-preview"></div></div>
        <div class="file-upload-wrapper" id="ev2"><label for="p2" class="file-upload-label"><i class="fas fa-camera"></i> Add Photo</label>
          <div class="file-name">photo.jpg</div><div class="image-preview"><img alt=""></div></div></div>
      <div class="notes-foot"><label class="notes-photo"><i class="fas fa-camera"></i> <span>Add a photo</span></label></div>
      <div class="submit-row"><button type="submit">Submit Visit</button></div>
      <div class="interpretive-guideline"><div class="guideline-title">Standard expectations</div>
        <div class="guideline-content"><div class="g-narr">Lobby clean and free of odors.</div></div></div>
      <div class="question-section" id="q4"><div class="condition-rating"><label class="radio-button rb-notchecked"><input type="radio" name="c" value="Not checked" checked><span class="radio-label notchecked">Not checked</span></label></div></div>
      <div class="question-section" id="q5"><div class="condition-rating"><label class="radio-button"><input type="radio" name="d" value="Pass"><span class="radio-label pass">Pass</span></label></div></div>
      <div class="question-section" id="q2"><div class="question-title">Kitchen</div>
        <div class="condition-rating"><label class="radio-button"><input type="radio" name="b" value="Pass" checked><span class="radio-label pass">Pass</span></label></div></div>
    </div></body></html>`).window;
  const d = w.document;
  const cs = (sel) => w.getComputedStyle(d.querySelector(sel));

  ok(!d.querySelector('.hdr-actions [style]') && !d.querySelector('.hdr-actions[style]'),
     `${mode}: the header buttons carry no inline colours`);
  ok(cs('.hdr-actions').order === '-1', `${mode}: the buttons are one row above the title`);
  for (const sel of ['.hdr-out', 'label', '.radio-label.notchecked']) {
    ok(cs(sel).textTransform === 'none', `${mode}: ${sel} is not in capitals`);
  }
  // jsdom will not compute a <select>'s corners; its chevron it will.
  ok(/svg/.test(cs('select').backgroundImage), `${mode}: the select draws the theme's chevron, not the phone's own control`);

  const panel = cs('.progress-bar-container').backgroundColor;
  ok(lum(rgb(panel)) < 0.05, `${mode}: the progress is a navy panel (${panel})`);
  const fill = cs('.progress-fill');
  ok(contrast(fill.color, fill.backgroundColor) >= 4.5, `${mode}: its percentage reads on the electric bar (${contrast(fill.color, fill.backgroundColor).toFixed(1)}:1)`);
  ok(contrast(cs('.progress-title').color, panel) >= 4.5, `${mode}: and so does its eyebrow`);

  // Gabriel's colours for the chosen answer. Pass carries dark ink (white on
  // that green is 1.3:1). Fail's white is 4.0:1: his choice, held here at
  // what it is so it cannot slide lower unnoticed.
  const chosenPass = cs('#q2 .radio-label.pass'), chosenFail = cs('#q1 .radio-label.fail');
  ok(chosenPass.backgroundColor === 'rgb(117, 251, 135)', `${mode}: a chosen Pass is his green (${chosenPass.backgroundColor})`);
  ok(contrast(chosenPass.color, chosenPass.backgroundColor) >= 4.5, `${mode}: with ink that reads on it (${contrast(chosenPass.color, chosenPass.backgroundColor).toFixed(1)}:1)`);
  ok(chosenFail.backgroundColor === 'rgb(234, 54, 110)', `${mode}: a chosen Fail is his pink-red (${chosenFail.backgroundColor})`);
  ok(contrast(chosenFail.color, chosenFail.backgroundColor) >= 3.95, `${mode}: with white on it (${contrast(chosenFail.color, chosenFail.backgroundColor).toFixed(1)}:1)`);
  // The rail matches the chosen button: Gabriel asked for the two to agree.
  ok(cs('#q1').borderLeftColor === chosenFail.backgroundColor, `${mode}: a Fail's rail is its button's colour (${cs('#q1').borderLeftColor})`);
  ok(cs('#q2').borderLeftColor === chosenPass.backgroundColor, `${mode}: so is a Pass's (${cs('#q2').borderLeftColor})`);
  ok(cs('#q4').borderLeftColor === 'rgb(91, 107, 133)', `${mode}: and a Not checked's is grey (${cs('#q4').borderLeftColor})`);
  const idle = rgb(cs('#q5').borderLeftColor);
  ok(idle[2] > idle[0] + 60, `${mode}: one not yet answered keeps the navy rail (${cs('#q5').borderLeftColor})`);

  // Gabriel's screenshot: the page-wide caption rule reached this <label>
  // too, and the navy button's text and camera went dark on navy.
  const photo = cs('.file-upload-label');
  ok(contrast(photo.color, photo.backgroundColor) >= 4.5,
     `${mode}: "Add Photo" reads on its button (${contrast(photo.color, photo.backgroundColor).toFixed(1)}:1)`);
  ok(cs('.dc-label').textTransform === 'none', `${mode}: "Direct comment to" is not in capitals`);
  // The empty preview drew a grey line under every standard.
  ok(cs('#ev1 .image-preview').display === 'none', `${mode}: no photo, no empty preview box`);
  ok(cs('#ev2 .image-preview').display !== 'none' && cs('#ev2 .image-preview').order === '-1',
     `${mode}: a photo shows as a thumbnail before the button`);
  ok((dark ? photo.backgroundColor === 'rgb(27, 37, 55)' : lum(rgb(photo.backgroundColor)) > 0.9) && photo.borderTopStyle === 'dashed',
     `${mode}: Add Photo is a quiet outlined button, not a navy bar (${photo.backgroundColor})`);
  ok(cs('.condition-rating').flexWrap === 'nowrap' && cs('.rb-notchecked').flexGrow === '1',
     `${mode}: Pass, Fail and Not checked share one line`);
  // Gabriel: the notes' "Add a photo" did not match the standards' one.
  const np = cs('.notes-photo');
  for (const k of ['backgroundColor', 'color', 'borderTopStyle', 'borderTopColor', 'height', 'fontWeight', 'fontSize']) {
    ok(np[k] === photo[k], `${mode}: the notes' photo button matches the standards' on ${k} (${np[k]} / ${photo[k]})`);
  }
  const sub = cs('.submit-row button');
  ok(sub.backgroundColor === 'rgb(90, 196, 134)', `${mode}: Submit is Gabriel's green (${sub.backgroundColor})`);
  ok(sub.textTransform === 'none' && contrast(sub.color, sub.backgroundColor) >= 4.5,
     `${mode}: a sentence, in ink that reads on it (${contrast(sub.color, sub.backgroundColor).toFixed(1)}:1)`);
  // In dark mode the expectations box stayed white (found in the final check).
  const gb = cs('.interpretive-guideline').backgroundColor;
  ok(dark ? lum(rgb(gb)) < 0.05 : lum(rgb(gb)) > 0.85, `${mode}: the expectations box follows the theme (${gb})`);
  ok(contrast(cs('.g-narr').color, gb) >= 4.5 && contrast(cs('.guideline-title').color, gb) >= 4.5,
     `${mode}: and its text reads on it (${contrast(cs('.g-narr').color, gb).toFixed(1)}:1)`);
  const qbg = cs('.question-section').backgroundColor;
  for (const sel of ['.question-title', '.response-label', 'label']) {
    ok(contrast(cs(sel).color, qbg) >= 7, `${mode}: ${sel} reads on its card (${contrast(cs(sel).color, qbg).toFixed(1)}:1)`);
  }
}

console.log(failures ? `\n${failures} failed` : '\nall passed');
process.exit(failures ? 1 : 0);
