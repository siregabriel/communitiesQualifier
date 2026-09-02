/*
  The panel that opens when you look at a community's last visit.

  Two things were wrong with it. It was 600px wide on any screen, so a visit —
  nine standards with photos and what was done about each — arrived as one long
  ribbon. And where the conversation about a failed standard should have been
  there was a button that sent you to another screen to read it; the gap on
  screen is what got reported.

  The panel also slides. It used to do that by animating `right` between two
  hand-written numbers that had to match the width, which is the kind of pair
  that silently stops matching. It moves by transform now, and that is worth
  holding down: get it wrong and the panel opens off-screen, which looks
  exactly like nothing happening.
*/

import fs from 'fs';
import { JSDOM } from 'jsdom';

const html = fs.readFileSync(new URL('../templates/dashboard.html', import.meta.url), 'utf8');
const theme = fs.readFileSync(new URL('../static/theme.css', import.meta.url), 'utf8');
const head = html.slice(html.indexOf('<style>') + 7, html.indexOf('</style>'));

let failures = 0;
const ok = (c, m) => { console.log((c ? '  ok   ' : '  FAIL ') + m); if (!c) failures++; };

/* Lift a function out of the template by matching its braces.

   The body has to be found after the parameter list closes, not from the first
   brace: commentThreadHtml destructures its argument, so `function f({ a, b })`
   made the naive version stop at the end of the parameters and hand back 81
   characters that happened to parse as nothing. */
const grab = (name) => {
  let i = html.indexOf(`function ${name}(`);
  if (i < 0) throw new Error('not found: ' + name);
  if (html.slice(i - 6, i) === 'async ') i -= 6;

  let parens = 0, afterParams = -1;
  for (let k = html.indexOf('(', i); k < html.length; k++) {
    if (html[k] === '(') parens++;
    else if (html[k] === ')' && --parens === 0) { afterParams = k + 1; break; }
  }
  if (afterParams < 0) throw new Error('unbalanced parameters: ' + name);

  let depth = 0;
  for (let k = html.indexOf('{', afterParams); k < html.length; k++) {
    if (html[k] === '{') depth++;
    else if (html[k] === '}' && --depth === 0) {
      const src = html.slice(i, k + 1);
      new Function(src);   // fail loudly here, not inside the page
      return src;
    }
  }
  throw new Error('unbalanced body: ' + name);
};

const RESPONSES = [
  { questionId: 'q1', submissionId: 's1', questionText: 'Speak2 Functioning Properly',
    condition: 'Fail', conditionClass: 'fail', conditionIcon: 'fa-times',
    description: 'Staff are not consistently using phones to document care.',
    comments: [
      { id: 'c1', author: 'Chloe Burke', text: 'Rolled out to caregivers today.', at: '2026-08-31T10:00:00' },
      { id: 'c2', author: 'Angie Surls', text: 'Thanks — check families next.', at: '2026-08-31T12:00:00' },
    ] },
  { questionId: 'q2', submissionId: 's1', questionText: 'Missing Meds and Exceptions',
    condition: 'Fail', conditionClass: 'fail', conditionIcon: 'fa-times',
    description: 'Several meds are listed as waiting on pharmacy.',
    comments: [] },
  { questionId: 'q3', submissionId: 's1', questionText: 'Tour Path is show time ready',
    condition: 'Pass', conditionClass: 'pass', conditionIcon: 'fa-check',
    description: '', comments: [],
    addressed: true, addressedAt: '2026-08-30', addressedBy: 'Chloe Burke',
    addressedNote: 'Repainted the entry.' },
];

function boot(width) {
  const dom = new JSDOM(`<!doctype html><html><head>
    <style>${head}</style><style>${theme}</style></head>
    <body><div class="slide-panel" id="panel"><div id="body"></div></div></body></html>`,
    { runScripts: 'outside-only' });
  const w = dom.window;
  // jsdom has no layout engine, so a media query is matched against what the
  // window says its width is. Set it before anything reads a computed style.
  Object.defineProperty(w, 'innerWidth', { value: width, configurable: true });
  w.eval(`
    ${grab('escapeHtml')}
    ${grab('decodeEntities')}
    ${grab('escapeHtmlForAttr')}
    ${grab('timeAgo')}
    ${grab('parseTs')}
    ${grab('formatDate')}
    ${grab('photoUrl')}
    ${grab('commentThreadHtml')}
    ${grab('renderResponses')}
    function standardFor() { return null; }
    var currentUsername = 'gabriel';
    var isAdmin = true;
  `);
  w.document.getElementById('body').innerHTML = w.renderResponses(RESPONSES);
  return w;
}

console.log('\nThe conversation is on the page, not one screen away');
{
  const w = boot(1400);
  const d = w.document;
  const cards = [...d.querySelectorAll('.response-card')];
  ok(cards.length === 3, 'every response is rendered');

  const speak2 = cards[0];
  ok(/Rolled out to caregivers today/.test(speak2.textContent),
     'the reply on the failed standard is readable without leaving');
  ok(/Angie Surls/.test(speak2.textContent), 'and who said it');
  ok(speak2.querySelectorAll('.cm').length === 2, 'both messages, not a count');

  ok(!speak2.querySelector('.cm-add'),
     'but there is no comment box here — replying stays in Action Items, '
     + 'so the thread keeps one home');
  ok(!speak2.querySelector('.cm-del'),
     'and nothing can be deleted from a read-only view');
  ok(/Reply in Action Items/.test(speak2.textContent), 'with the way through spelled out');

  const noTalk = cards[1];
  ok(!noTalk.querySelector('.resp-talk'),
     'a standard nobody has commented on shows no empty thread — that gap is what was reported');

  ok(/Addressed/.test(cards[2].textContent) && /Repainted the entry/.test(cards[2].textContent),
     'and what was done about a finding still shows');
}

console.log('\nHow it is laid out');
{
  // jsdom resolves no media queries in getComputedStyle — it answers `none`
  // at every width. Measuring here would have reported one column on a
  // monitor and one column on a phone and called both correct, which is a
  // passing test that checks nothing. So the base rule is measured and the
  // width-dependent part is read.
  const w = boot(1400);
  const grid = w.getComputedStyle(w.document.querySelector('.panel-responses'));
  ok(grid.display === 'grid', 'the responses are a grid');
  ok(grid.alignItems === 'start',
     'each card keeps its own height rather than stretching to its neighbour');
  ok(!grid.gridTemplateColumns || grid.gridTemplateColumns === 'none',
     'one column by default, so a phone gets the readable layout without a query');

  const rule = theme.match(
    /@media \(min-width:\s*(\d+)px\)\s*\{\s*\.panel-responses\s*\{([^}]*)\}/);
  ok(!!rule, 'and a second column is added at a width, not always');
  if (rule) {
    ok(/repeat\(2,/.test(rule[2]),
       `two columns above ${rule[1]}px (${rule[2].trim()})`);
    ok(Number(rule[1]) >= 700,
       `and not before there is room for them (${rule[1]}px)`);
  }
}

console.log('\nIt slides, and it comes back');
{
  // The failure this guards is invisible: a panel that opens off-screen looks
  // exactly like a click that did nothing.
  const w = boot(1400);
  const panel = w.document.getElementById('panel');
  const shut = w.getComputedStyle(panel);
  ok(shut.position === 'fixed', 'it is fixed to the viewport');
  ok(/translateX\(100%\)|matrix/.test(shut.transform),
     `closed, it is pushed off to the side (${shut.transform})`);

  panel.classList.add('show');
  const open = w.getComputedStyle(panel);
  ok(/translateX\(0(px)?\)|none|matrix\(1, 0, 0, 1, 0, 0\)/.test(open.transform),
     `open, it is back on screen (${open.transform})`);

  ok(shut.right === open.right,
     'and `right` is no longer the thing being animated, so no number has to be '
     + 'kept in step with the width');
}

console.log('\nNothing still parks it off-screen by hand');
{
  // The mobile rule used to say `right: -100%`, to pair with the old
  // animation. Left behind it survives `.show` — the transform comes back to
  // zero and the panel is still a whole screen to the right, invisible, and
  // only on a phone.
  //
  // The first version of this check read a fixed slice from the first
  // `.slide-panel` rule onwards and never reached the media query 150 lines
  // below, so it passed with that exact bug reinstated. Every block whose
  // selector mentions the panel is checked now.
  // Comments out first: the note explaining why the old offset was removed
  // quotes it, and a quoted declaration is not a declaration.
  const css = head.replace(/\/\*[\s\S]*?\*\//g, '');
  const blocks = [...css.matchAll(/([^{}]*\.slide-panel[^{}]*)\{([^}]*)\}/g)]
    .map(m => ({ selector: m[1].trim().replace(/\s+/g, ' '), body: m[2] }));
  ok(blocks.length >= 2, `every panel rule is examined (${blocks.length} found)`);

  const parked = blocks.filter(b => /right\s*:\s*-/.test(b.body));
  ok(parked.length === 0,
     parked.length
       ? `a rule still parks it off-screen: ${parked.map(b => b.selector).join(', ')}`
       : 'no rule pushes it off-screen with a negative offset');
}

console.log(failures ? `\n${failures} failure(s)` : '\nA visit reads as one thing.');
process.exit(failures ? 1 : 0);
