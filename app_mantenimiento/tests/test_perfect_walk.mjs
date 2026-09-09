/*
  The gold halo on a community that walked clean.

  Two cards at 100% used to look identical. One got there on the day with
  nothing to fix; the other got there afterwards by repairing three findings.
  Both are worth something and they are not the same thing, and the card had no
  way of saying which was which.

  What matters here is that the mark is hard to get. A mark handed out to
  anything that arithmetically reaches 100 — three standards answered out of
  thirty-nine, all passing — is a mark nobody looks at twice.
*/

import fs from 'fs';
import { JSDOM } from 'jsdom';

const html = fs.readFileSync(new URL('../templates/dashboard.html', import.meta.url), 'utf8');
const head = html.slice(html.indexOf('<style>') + 7, html.indexOf('</style>'));

let failures = 0;
const ok = (c, m) => { console.log((c ? '  ok   ' : '  FAIL ') + m); if (!c) failures++; };

/* The line that decides, lifted out of the card so the rule is run rather
   than restated here. */
const rule = (() => {
  const i = html.indexOf('const perfectWalk =');
  if (i < 0) throw new Error('the rule moved');
  return html.slice(i, html.indexOf(';', i) + 1);
})();

function earnsIt(community) {
  const w = new JSDOM('<!doctype html><body></body>', { runScripts: 'outside-only' }).window;
  // Read inside the same eval. `const` at the top of an eval belongs to that
  // eval, so a second one asking for the name gets a ReferenceError — and had
  // it been `var`, it would have got undefined and every assertion here would
  // have passed on nothing.
  return w.eval(`(function () {
    var community = ${JSON.stringify(community)};
    ${rule}
    return perfectWalk;
  })()`);
}

console.log('\nWho earns it');
{
  ok(earnsIt({ visitScore: 100, fixedSinceVisit: 0, partial: null }) === true,
     'every standard passed on the day, nothing to fix');

  ok(earnsIt({ visitScore: 92, fixedSinceVisit: 1, partial: null }) === false,
     'reaching 100 afterwards by fixing something does not — that has its own telling');

  ok(earnsIt({ visitScore: 89, fixedSinceVisit: 1, partial: null }) === false,
     'nor does recovering from further back');

  ok(earnsIt({ visitScore: 99, fixedSinceVisit: 0, partial: null }) === false,
     'and 99 is not 100');
}

console.log('\nAn incomplete visit does not count');
{
  // The way a mark like this becomes worthless: 3 of 39 standards answered,
  // all passing, is 100% by arithmetic and by nothing else.
  ok(earnsIt({ visitScore: 100, fixedSinceVisit: 0,
               partial: { answered: 3, total: 39, missing: 36 } }) === false,
     'three standards out of thirty-nine, all passing, is not a clean walk');

  ok(earnsIt({ visitScore: 100, fixedSinceVisit: 0, partial: null }) === true,
     'the same score on a visit that was finished does count');
}

console.log('\nA community with no visit is left alone');
{
  ok(earnsIt({ visitScore: null, fixedSinceVisit: 0, partial: null }) === false,
     'no visit, no mark');
  ok(earnsIt({ visitScore: undefined, fixedSinceVisit: 0, partial: null }) === false,
     'and nothing is not a hundred');
}

console.log('\nWhat it looks like');
{
  ok(/\.cc-medal\.cc-perfect\s*\{/.test(head), 'the medal takes a gold state');
  const block = head.slice(head.indexOf('.cc-medal.cc-perfect {'));
  const decl = block.slice(0, block.indexOf('}'));
  ok(/animation:\s*ccPerfectGlow/.test(decl), 'and it pulses');

  // The card clips. A halo that grows past the room it has loses its outer
  // edge to the corner and reads as broken rather than bright — the same
  // clipping that cost us the medal once already.
  const frames = head.slice(head.indexOf('@keyframes ccPerfectGlow'));
  const spreads = [...frames.slice(0, frames.indexOf('}\n')).matchAll(/0 0 (\d+)px (\d+)px/g)]
    .map(m => Number(m[1]) + Number(m[2]));
  ok(spreads.length > 0, 'the pulse is written as blur, not as a growing ring');
  ok(spreads.every(s => s <= 16),
     `and stays inside the room the medal has (largest ${Math.max(...spreads)}px, 15 available)`);

  ok(/prefers-reduced-motion[\s\S]{0,120}\.cc-medal\.cc-perfect\s*\{\s*animation:\s*none/.test(head),
     'somebody who asked their system to stop moving things keeps the gold and loses the pulse');
}

console.log('\nAnd it moves, visibly');
{
  // A pulse in opacity reads as "lit" rather than as moving. The sweep is the
  // part that is unmistakably an animation — which is what was asked for.
  ok(/\.cc-medal\.cc-perfect::before/.test(head), 'there is a sheen around the ring');
  const sheen = head.slice(head.indexOf('.cc-medal.cc-perfect::before'));
  const decl = sheen.slice(0, sheen.indexOf('}'));
  ok(/animation:\s*ccPerfectSweep/.test(decl), 'and it travels');
  ok(/conic-gradient/.test(decl), 'as a sheen going round, not another pulse');

  // Without the mask the cone covers the white disc and the score with it.
  ok(/mask:\s*radial-gradient/.test(decl),
     'masked down to the outer band, so it does not cover the number');
  const guard = head.slice(0, head.indexOf('.cc-medal.cc-perfect::before'));
  ok(/@supports[^{]*mask[^{]*$/m.test(guard.slice(-260)),
     'and guarded, so a browser without mask gets no sheen rather than a gold blob');

  const inset = (decl.match(/inset:\s*-(\d+)px/) || [])[1];
  ok(inset && Number(inset) <= 15,
     `it stays inside the room the card's clipping allows (${inset}px of 15)`);

  ok(/prefers-reduced-motion[\s\S]{0,260}::before\s*\{\s*animation:\s*none/.test(head),
     'and it stops for somebody who asked their system to stop moving things');
}

console.log('\nThe words on the card');
{
  ok(/class="cc-clean"/.test(html), 'a clean visit is named, not left to a colour');
  ok(/Clean visit/.test(html), 'in words');

  // The chip lives in the footer, beside the state summary. Next to the name
  // it wrapped onto a second line for a community called "The Goldton at
  // Spring Hill, Spring Hill".
  const foot = html.slice(html.indexOf('<div class="cc-foot">'));
  ok(foot.slice(0, 400).includes('cc-clean'), 'in the footer row, with the rest of the state');

  // The one that stops the two being merged into a single sentence.
  ok(/perfectWalk \? `<span class="cc-clean"/.test(html) && /open action/.test(foot),
     'and separate from the open-actions line: all standards can pass while an '
     + 'item that does not score is still open');
}

console.log('\nIt says what it means');
{
  // Search forward from the start of the block, not from the top of the file:
  // "circular-progress" first appears in a CSS rule hundreds of lines above,
  // so slicing to it ran backwards and handed back an empty string — which
  // fails here, but the same shape passes silently when the assertion is a
  // negative one.
  const from = html.indexOf('const perfectWalk =');
  const title = html.slice(from, html.indexOf('circular-progress', from));
  ok(title.length > 0, 'the block was found');
  ok(/nothing to fix/i.test(title),
     'the tooltip explains it, rather than leaving a glow nobody can account for');
}

console.log(failures ? `\n${failures} failure(s)` : '\nA clean walk looks different from a repair.');
process.exit(failures ? 1 : 0);
