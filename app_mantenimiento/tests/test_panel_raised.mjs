/*
  What was raised for a community, shown on that community.

  Michael Hamilton opened Madison at The Range looking for a photo of an HVAC
  unit that Greg had raised there. He found the visit Shannon had submitted,
  did not find the photo, and wrote in asking whether there was some other
  access. There was not: the panel showed the cover, the stats, the visit's
  answers, its photos and the history — and never the raised items, which
  lived only in Action Items. Nobody had told him to look there, and nobody
  should have to.

  The section that fixes that is also a new place for an internal item to
  leak, and one of the two items in production right now is internal. So the
  bulk of this is about where that list comes from: the server, already
  scoped, rather than a second copy of the rule on this side.
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

// What the server hands back for somebody who may see both. An Executive
// Director asking the same endpoint would not receive the internal one at
// all — that filtering happens there, which is the point.
const GREG_HVAC = {
  id: 'raised_1758664020000_4821', community: 'Madison at The Range, Madison',
  text: 'Would like to see what we can do to get this HVAC line hidden.',
  priority: 'medium', category_name: 'Maintenance', raised_by: 'greg.crutcher',
  raised_by_name: 'Greg Crutcher', raised_at: '2026-09-23T22:07:00',
  visibility: 'community', photo: 'Range/hvac.jpg', comments: [],
};
const ELSEWHERE = {
  id: 'raised_1758663780000_1111', community: 'The Goldton at Spring Hill, Spring Hill',
  text: 'Landscaping needs attention.', priority: 'high',
  raised_by: 'greg.crutcher', raised_by_name: 'Greg Crutcher',
  raised_at: '2026-09-23T22:03:00', visibility: 'internal', comments: [],
};

function makeWorld(items) {
  const dom = new JSDOM('<!doctype html><body><div id="panelRaised"></div></body>',
                        { runScripts: 'outside-only' });
  const w = dom.window;
  w.eval(`
    var _items = ${JSON.stringify(items)};
    var _asked = 0;
    var raisedItems = [], raisedCategories = [];
    var went = null;
    function fetch(url) {
      _asked++;
      return Promise.resolve({ ok: true, json: () =>
        Promise.resolve({ status: 'success', items: _items, categories: [] }) });
    }
    function escapeHtml(s) { return String(s == null ? '' : s); }
    function escapeHtmlForAttr(s) { return String(s == null ? '' : s); }
    function formatDate(s) { return String(s).slice(0, 10); }
    function closeSlidePanel() { went = 'closed'; }
    function openRaisedTarget(id) { went = id; }
    ${grab('loadCommunityRaised')}
  `);
  return w;
}

const host = (w) => w.document.getElementById('panelRaised');

console.log('\nThe item Michael was looking for');
{
  const w = makeWorld([GREG_HVAC, ELSEWHERE]);
  await w.loadCommunityRaised('Madison at The Range, Madison');
  const h = host(w).innerHTML;

  ok(/Raised here/.test(h), 'the section has a heading');
  ok(/HVAC line hidden/.test(h), 'and the item raised at this community');
  ok(/Greg Crutcher/.test(h), 'with who raised it');
  ok(/2026-09-23/.test(h), 'and when');
  ok(/Maintenance/.test(h), 'and what it was filed under');
  ok(/fa-image/.test(h), 'and a mark that it carries a photo');
}

console.log('\nOnly this community');
{
  const w = makeWorld([GREG_HVAC, ELSEWHERE]);
  await w.loadCommunityRaised('Madison at The Range, Madison');
  const h = host(w).innerHTML;
  ok(!/Landscaping/.test(h),
     'an item raised somewhere else is not shown on this one');
  ok((h.match(/rz-row/g) || []).length === 1, 'one row, not two');
}

console.log('\nWhere the list comes from');
{
  /* The internal rule is enforced on the server — /api/raised-items passes
     include_internal=can_see_internal(). Copying that filter here would make
     two places for one rule, and the second is where it goes stale. So this
     checks the source asks the server and does not re-decide. */
  const src = grab('loadCommunityRaised');
  ok(/fetch\('\/api\/raised-items'\)/.test(src),
     'it asks the endpoint that already scopes by viewer');
  ok(!/visibility\s*[=!]==?\s*'internal'\s*\)\s*(\?|&&|\|\|)?[^]{0,40}(filter|continue|return)/.test(src),
     'and does not keep its own copy of the internal rule');
  ok(/i\.community === community/.test(src),
     'it narrows to this community and nothing more');
}

console.log('\nAn internal item, for somebody the server let see it');
{
  // A regional opening the panel of a community that has one. It is shown,
  // and it is labelled — an item the community cannot see should be obvious
  // to the person who can, or it gets discussed in front of them.
  const internalHere = { ...ELSEWHERE, community: 'Madison at The Range, Madison' };
  const w = makeWorld([internalHere]);
  await w.loadCommunityRaised('Madison at The Range, Madison');
  const h = host(w).innerHTML;
  ok(/Landscaping/.test(h), 'it is shown to somebody the server sent it to');
  ok(/<b>internal<\/b>/.test(h), 'and marked as internal, not passed off as ordinary');
}

console.log('\nAn Executive Director, whose list simply lacks it');
{
  // The server sends them only the community-visible ones. Nothing here has
  // to know that; drawing what arrives is the whole behaviour.
  const w = makeWorld([GREG_HVAC]);
  await w.loadCommunityRaised('Madison at The Range, Madison');
  const h = host(w).innerHTML;
  ok(/HVAC/.test(h) && !/internal/.test(h), 'they see the ordinary one and no more');
}

console.log('\nNothing raised, and things going wrong');
{
  const empty = makeWorld([]);
  await empty.loadCommunityRaised('Madison at The Range, Madison');
  ok(/Nothing raised for this community/.test(host(empty).innerHTML),
     'an empty community says so rather than showing a blank heading');

  const dom = new JSDOM('<!doctype html><body><div id="panelRaised"></div></body>',
                        { runScripts: 'outside-only' });
  const w = dom.window;
  w.eval(`
    var raisedItems = [], raisedCategories = [];
    function fetch() { return Promise.reject(new Error('offline')); }
    function escapeHtml(s) { return String(s); }
    function escapeHtmlForAttr(s) { return String(s); }
    function formatDate(s) { return String(s); }
    function closeSlidePanel() {}
    function openRaisedTarget() {}
    ${grab('loadCommunityRaised')}
  `);
  await w.loadCommunityRaised('Anywhere');
  ok(/Could not load/.test(w.document.getElementById('panelRaised').innerHTML),
     'and a failed fetch says so instead of spinning forever');
}

console.log('\nPressing a row');
{
  const w = makeWorld([GREG_HVAC]);
  await w.loadCommunityRaised('Madison at The Range, Madison');
  const row = host(w).querySelector('.rz-row');
  ok(!!row, 'the row is there');
  const call = row.getAttribute('onclick') || '';
  ok(/closeSlidePanel\(\)/.test(call), 'it closes the panel first');
  ok(call.includes(GREG_HVAC.id), `and opens that item (${call.slice(0, 70)})`);
}

console.log('\nThe panel actually asks for it');
{
  const render = grab('renderPanelContent');
  ok(/id="panelRaised"/.test(render), 'the panel makes room for the section');
  ok(/loadCommunityRaised\(data\.communityName\)/.test(render),
     'and fills it, or the heading would sit there loading forever');
  ok(render.indexOf('panelRaised') < render.indexOf('panelHistory'),
     'above the history, because it is the newer thing');
}

console.log(failures ? `\n${failures} failure(s)` : '\nWhat was raised here shows up here.');
process.exit(failures ? 1 : 0);
