/*
  "Also visits" in Edit person, run rather than read.

  The Goldton at Venice moved region and Lauren Hamilton still visits it, so a
  regional can now be given named communities outside their region. The
  server side is test_regional_extra_communities.py; this is the form: that it
  lists only the communities outside the region, follows the region dropdown,
  and sends the list only when it changed.
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

const VENICE = 'The Goldton at Venice, Venice';
const PEOPLE = {
  communities: ['Tampa Place', 'Sarasota Place', VENICE, "Angie's Place"],
  regions: [
    { id: 'gulf', name: 'Gulf', communities: ['Tampa Place', 'Sarasota Place'] },
    { id: 'south', name: 'South', communities: [VENICE, "Angie's Place"] },
  ],
};

function world({ role = 'regional', extras = [], regionId = 'gulf' } = {}) {
  const dom = new JSDOM(`<!doctype html><body>
    <input id="peName" value="Lauren Hamilton"><input id="peEmail" value="l@x.com">
    <select id="peRole"><option value="regional">r</option><option value="corporate">c</option>
      <option value="staff">s</option><option value="admin">a</option></select>
    <div id="peTitleWrap"><input id="peTitle" value="RDO"></div>
    <div id="peRegionWrap"><select id="peRegion">
      <option value="gulf">Gulf</option><option value="south">South</option></select></div>
    <div id="peCommunityWrap"><input id="peCommunity" value=""></div>
    <div id="peExtraWrap"><div id="peRegExtra"></div></div>
    <div id="peRoleNote"></div><span id="peMsg"></span></body>`, { runScripts: 'outside-only' });
  const w = dom.window;
  w.document.getElementById('peRole').value = role;
  w.document.getElementById('peRegion').value = regionId;
  w.eval(`
    var calls = [], closed = 0;
    var peopleData = ${JSON.stringify(PEOPLE)};
    peopleData.people = [{ username: 'lauren.hamilton', region_id: '${regionId}',
                           extra_communities: ${JSON.stringify(extras)} }];
    function escapeHtml(s) { return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;')
      .replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;'); }
    function fetch(url, opts) {
      calls.push({ url, method: opts.method, body: JSON.parse(opts.body) });
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ status: 'success' }) });
    }
    function closePersonModal() { closed++; }
    async function refreshPeopleViews() {}
    async function loadRegions() {}
    ${grab('checkedCoverage')}
    ${grab('regionalExtraChecklist')}
    ${grab('wirePersonExtras')}
    ${grab('peOnRoleChange')}
    ${grab('savePersonEdit')}
  `);
  w.wirePersonExtras(w.peopleData.people[0]);
  return w;
}

const offered = (w) => [...w.document.querySelectorAll('#peRegExtra .cov-check')].map(c => c.value);
const tick = (w) => w.document.querySelector(`#peRegExtra .cov-check[value="${CSS_escape(VENICE)}"]`);
const CSS_escape = (s) => s.replace(/"/g, '\\"');

console.log('\nOnly communities outside the region are offered');
{
  const w = world();
  ok(offered(w).join('|') === `${VENICE}|Angie's Place`, `outside Gulf (${offered(w).join(' | ')})`);
  ok(!offered(w).includes('Tampa Place'), 'her own region is not listed — she has it anyway');
}

console.log('\nWhat she has is ticked');
{
  const w = world({ extras: [VENICE] });
  ok(tick(w).checked === true, 'Venice is ticked');
}

console.log('\nThe list follows the region dropdown');
{
  const w = world({ extras: [] });
  tick(w).checked = true;
  const sel = w.document.getElementById('peRegion');
  sel.value = 'south';
  sel.dispatchEvent(new w.Event('change'));
  ok(offered(w).join('|') === 'Tampa Place|Sarasota Place',
     `moved to South, Gulf is what is outside now (${offered(w).join(' | ')})`);
  sel.value = 'gulf';
  sel.dispatchEvent(new w.Event('change'));
  ok(tick(w) && tick(w).checked === true, 'and a tick survives switching back');
}

console.log('\nOnly for a regional');
{
  for (const role of ['corporate', 'staff', 'admin']) {
    const w = world({ role });
    w.peOnRoleChange();
    ok(w.document.getElementById('peExtraWrap').style.display === 'none', `hidden for ${role}`);
  }
  const w = world();
  w.peOnRoleChange();
  ok(w.document.getElementById('peExtraWrap').style.display !== 'none', 'shown for a regional');
}

console.log('\nSaving');
{
  const w = world();
  tick(w).checked = true;
  await w.savePersonEdit('lauren.hamilton');
  const post = w.calls.find(c => /\/extra-communities$/.test(c.url));
  ok(w.calls[0].method === 'PUT', 'the person is saved first');
  ok(post && post.body.communities.join('|') === VENICE, 'then the ticked communities are sent');

  const same = world({ extras: [VENICE] });
  await same.savePersonEdit('lauren.hamilton');
  ok(!same.calls.some(c => /extra-communities/.test(c.url)), 'nothing is sent when nothing changed');

  const off = world({ extras: [VENICE] });
  tick(off).checked = false;
  await off.savePersonEdit('lauren.hamilton');
  const cleared = off.calls.find(c => /\/extra-communities$/.test(c.url));
  ok(cleared && cleared.body.communities.length === 0, 'unticking sends the empty list');

  const corp = world({ role: 'corporate' });
  tick(corp).checked = true;
  await corp.savePersonEdit('lauren.hamilton');
  ok(!corp.calls.some(c => /extra-communities/.test(c.url)), 'not sent for somebody no longer a regional');
}

console.log('\nAn apostrophe in a name survives the round trip');
{
  const w = world();
  const angie = [...w.document.querySelectorAll('#peRegExtra .cov-check')].find(c => c.value === "Angie's Place");
  ok(!!angie, 'the value reads back as the real name');
}

console.log(failures ? `\n${failures} failure(s)` : '\nA regional can be given one more community.');
process.exit(failures ? 1 : 0);
