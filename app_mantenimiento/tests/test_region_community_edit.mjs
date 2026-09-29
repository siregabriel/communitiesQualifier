/*
  Editing a community where a community is edited.

  The map position spent a day at the bottom of the community panel, and
  Gabriel was right that it did not belong there. That panel is a visit —
  what was found, by whom, with what still open — and an administrative
  field underneath it mixes two audiences on one surface. Regions is where a
  community is renamed, reassigned and removed; the position is one more of
  those.

  So the pencil now opens both fields, and the row says when a community has
  no position at all — because a community with none is invisible on the map,
  and this is the row somebody would fix it from.
*/

import fs from 'fs';
import { JSDOM } from 'jsdom';

const html = fs.readFileSync(new URL('../templates/dashboard.html', import.meta.url), 'utf8');

let failures = 0;
const ok = (c, m) => { console.log((c ? '  ok   ' : '  FAIL ') + m); if (!c) failures++; };

const grab = (name) => {
  let i = html.indexOf(`function ${name}(`);
  if (i < 0) throw new Error(`no such function: ${name}`);
  if (html.slice(i - 6, i) === 'async ') i -= 6;
  let depth = 0;
  for (let k = html.indexOf('{', i); k < html.length; k++) {
    if (html[k] === '{') depth++;
    else if (html[k] === '}' && --depth === 0) return html.slice(i, k + 1);
  }
  throw new Error(`unbalanced braces in ${name}`);
};

function world({ placed = true, postOk = true, postMessage = '' } = {}) {
  const dom = new JSDOM(`<!doctype html><body>
    <input id="commName_r0" value="Tribute at One Loudoun">
    <input id="commPos_r0" value="${placed ? '39.0437, -77.4400' : ''}">
    <div id="commMsg_r0"></div></body>`, { runScripts: 'outside-only' });
  const w = dom.window;
  w.eval(`
    var posted = [], renamed = null, redrawn = 0, reloaded = 0, order = [];
    var communityPlaces = ${placed
      ? "{ 'Tribute at One Loudoun': { community: 'Tribute at One Loudoun', lat: 39.0437, lng: -77.44 } }"
      : '{}'};
    function fetch(url, opts) {
      posted.push({ url, body: JSON.parse(opts.body) }); order.push('place');
      return Promise.resolve({
        ok: ${postOk},
        json: () => Promise.resolve(${postOk
          ? "{ status: 'success', place: {} }"
          : `{ status: 'error', message: ${JSON.stringify(postMessage)} }`}),
      });
    }
    function regionAction(url, body) { renamed = { url, body }; order.push('rename'); }
    function renderRegions() { redrawn++; }
    function loadCommunityPlaces() { reloaded++; return Promise.resolve(); }
    ${grab('saveCommunityEdit')}
  `);
  return w;
}

console.log('\nOnly what changed is sent');
{
  const w = world();
  await w.saveCommunityEdit('r0', 'Tribute at One Loudoun');
  ok(w.posted.length === 0, 'nothing touched: no position saved');
  ok(w.renamed === null, 'and no rename');
  ok(w.redrawn === 1, 'the row just closes');
}

console.log('\nA new position');
{
  const w = world();
  w.document.getElementById('commPos_r0').value = '38.9640, -76.7280';
  await w.saveCommunityEdit('r0', 'Tribute at One Loudoun');
  ok(w.posted.length === 1, 'the position is saved');
  ok(/Tribute%20at%20One%20Loudoun/.test(w.posted[0].url),
     `to that community (${w.posted[0].url})`);
  ok(w.posted[0].body.pasted === '38.9640, -76.7280',
     'pasted as typed — the server does the parsing, in one place');
  ok(w.renamed === null, 'and the name is left alone');
  ok(w.reloaded === 1, 'the table of positions is refreshed before redrawing');
}

console.log('\nA new name');
{
  const w = world();
  w.document.getElementById('commName_r0').value = 'Tribute One Loudoun';
  await w.saveCommunityEdit('r0', 'Tribute at One Loudoun');
  ok(w.renamed && w.renamed.body.old_name === 'Tribute at One Loudoun',
     'the rename goes through the route that walks every store');
  ok(w.renamed.body.new_name === 'Tribute One Loudoun', 'with the new name');
  ok(w.posted.length === 0, 'and the position is not resaved for nothing');
}

console.log('\nBoth at once');
{
  const w = world();
  w.document.getElementById('commName_r0').value = 'Tribute One Loudoun';
  w.document.getElementById('commPos_r0').value = '38.9640, -76.7280';
  await w.saveCommunityEdit('r0', 'Tribute at One Loudoun');
  ok(w.posted.length === 1, 'the position is saved');
  ok(/Tribute%20at%20One%20Loudoun/.test(w.posted[0].url),
     'under the name it still has at that moment');
  ok(w.renamed !== null, 'and then it is renamed');
  /* Order matters, and is recorded rather than inferred. The position has to
     be saved under the name the community still has, because the rename is
     what carries it to the new one. Renaming first would file the position
     under a name the map has never heard of. */
  ok(w.order.join(' then ') === 'place then rename',
     `placed, then renamed (${w.order.join(' then ')})`);
}

console.log('\nA position the server refuses');
{
  const w = world({ postOk: false, postMessage: 'a positive longitude lands in the wrong hemisphere' });
  w.document.getElementById('commName_r0').value = 'A New Name';
  w.document.getElementById('commPos_r0').value = '39.0437, 77.4400';
  await w.saveCommunityEdit('r0', 'Tribute at One Loudoun');

  const msg = w.document.getElementById('commMsg_r0');
  ok(/wrong hemisphere/.test(msg.textContent), 'the reason is shown on the row');
  ok(/is-bad/.test(msg.className), 'and marked as a problem');
  ok(w.renamed === null,
     'and the rename does not happen — the position is saved first precisely '
     + 'so a refusal leaves everything where it was');
  ok(w.redrawn === 0, 'the row stays open on the value that was refused');
}

console.log('\nThe row says when there is nowhere to draw it');
{
  const i = html.indexOf('const place = communityPlaces[name];');
  ok(i > 0, 'the row reads the position table');
  // The row markup and its edit form together, which is further than it
  // looks — an earlier window stopped short and reported the field missing.
  const row = html.slice(i, i + 3000);
  ok(/region-comm-nopin/.test(row), 'and marks a community that has none');
  ok(/no position/.test(row), 'in words, not just a colour');
  ok(/id="commPos_/.test(row), 'and the pencil opens a field for it');
  ok(/saveCommunityEdit/.test(row), 'saved by the handler that sends only what changed');
}

console.log('\nAnd it is fetched once, not per row');
{
  /* Checked on the condition rather than on the word appearing somewhere in
     the function: the flag is also assigned inside, so a grep for the name
     passes even with the guard removed — and without the guard, loading calls
     renderRegions which loads again, for ever. */
  const fn = grab('renderRegions');
  ok(/if \(isAdmin && !renderRegions\._placesAsked\)/.test(fn),
     'the fetch is guarded, so redrawing does not fetch again for ever');
  ok(/renderRegions\._placesAsked = true;/.test(fn), 'and the guard is set');
}

console.log('\nThe row has room for what is on it');
{
  /* The first version of this put four children into a flex row that had no
     wrapping turned on. flex-basis: 100% does not wrap without it — it just
     takes its share of the one line — so both inputs were squeezed to nothing
     behind the buttons and the hint ran down the side in a narrow column.
     Gabriel sent a screenshot of it, which is the only reason it was caught:
     jsdom does no layout, so nothing here could have seen it happen.

     What can be checked is the pairing that makes it work, and that the rules
     live beside the row they belong to rather than in a second place that can
     drift. */
  const theme = fs.readFileSync(new URL('../static/theme.css', import.meta.url), 'utf8');

  const row = theme.slice(theme.indexOf('.region-comm-editrow {'));
  ok(/^[^}]*flex-wrap:\s*wrap/m.test(row.slice(0, row.indexOf('}'))),
     'the edit row wraps, which is what lets the lines below it be lines');

  ok(/\.region-comm-hint,\s*\n\.region-comm-msg \{[^}]*flex:\s*1 0 100%/.test(theme),
     'and the hint and the message each take a full line');

  ok(/\.region-comm-fields \{[^}]*flex-wrap:\s*wrap/s.test(theme),
     'the two fields wrap against each other too, on a narrow card');
  ok(/\.region-comm-fields input \{[^}]*flex:\s*1 1 150px/.test(theme),
     'with a basis, so neither collapses to nothing');

  ok(!/\.region-comm-(editrow|fields|hint|msg|nopin)\s*[,{]/.test(html),
     'and none of it is duplicated in the template, where it would drift');
}

console.log(failures ? `\n${failures} failure(s)` : '\nA community is edited where a community is edited.');
process.exit(failures ? 1 : 0);
