/*
  The "Can visit every community" switch in Edit person, run rather than read.

  Carol Brinegar asked for every community while staying the regional for her
  own region. Corporate would have given her the reach and silently taken the
  region's emails, so the reach became a switch of its own. The server side is
  covered in test_regional_all_communities.py; this is the form: that the
  switch is only offered where it means something, and that saving sends it
  only when it changed.
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

function world({ role = 'regional', has = false, grantFails = false } = {}) {
  const dom = new JSDOM(`<!doctype html><body>
    <input id="peName" value="Carol Brinegar">
    <input id="peEmail" value="carol@example.com">
    <select id="peRole">
      <option value="staff">s</option><option value="regional">r</option>
      <option value="corporate">c</option><option value="admin">a</option>
    </select>
    <div id="peTitleWrap"><input id="peTitle" value="RDO"></div>
    <div id="peRegionWrap"><select id="peRegion">
      <option value="north">North</option><option value="corporate">Corporate (company-wide)</option>
    </select></div>
    <div id="peCommunityWrap"><input id="peCommunity" value=""></div>
    <div id="peAllWrap"><input type="checkbox" id="peAllComms" ${has ? 'checked' : ''}></div>
    <div id="peRoleNote"></div>
    <span id="peMsg"></span></body>`, { runScripts: 'outside-only' });
  const w = dom.window;
  w.document.getElementById('peRole').value = role;
  w.eval(`
    var calls = [], closed = 0;
    var peopleData = { people: [{ username: 'carol.brinegar', all_communities: ${has} }] };
    function fetch(url, opts) {
      calls.push({ url, method: opts.method, body: JSON.parse(opts.body) });
      const failing = ${grantFails} && /all-communities/.test(url);
      return Promise.resolve({ ok: !failing, json: () => Promise.resolve(
        failing ? { status: 'error', message: 'nope' } : { status: 'success' }) });
    }
    function checkedCoverage() { return []; }
    function closePersonModal() { closed++; }
    async function refreshPeopleViews() {}
    async function loadRegions() {}
    ${grab('peOnRoleChange')}
    ${grab('savePersonEdit')}
  `);
  return w;
}

const shownFor = (role) => {
  const w = world({ role });
  w.peOnRoleChange();
  return w.document.getElementById('peAllWrap').style.display !== 'none';
};

console.log('\nOffered only where there is a region to stay in');
ok(shownFor('regional'), 'a regional is offered it');
ok(!shownFor('corporate'), 'Corporate is not — it already reaches everything');
ok(!shownFor('staff'), 'an Executive Director is not — their sites are picked one by one');
ok(!shownFor('admin'), 'an administrator is not');

console.log('\nTurning it on');
{
  const w = world();
  w.document.getElementById('peAllComms').checked = true;
  await w.savePersonEdit('carol.brinegar');
  const grant = w.calls.find(c => /\/all-communities$/.test(c.url));
  ok(w.calls[0].method === 'PUT', 'the person is saved first');
  ok(!!grant, 'then the switch is sent');
  ok(grant && /carol\.brinegar/.test(grant.url), 'for her');
  ok(grant && grant.body.grant === true, 'as on');
  ok(w.closed === 1, 'and the form closes');
}

console.log('\nTurning it off');
{
  const w = world({ has: true });
  w.document.getElementById('peAllComms').checked = false;
  await w.savePersonEdit('carol.brinegar');
  const grant = w.calls.find(c => /\/all-communities$/.test(c.url));
  ok(grant && grant.body.grant === false, 'sent as off');
}

console.log('\nLeft alone');
{
  const w = world({ has: true });
  await w.savePersonEdit('carol.brinegar');
  ok(!w.calls.some(c => /all-communities/.test(c.url)),
     'nothing is sent when it did not change — every grant is logged, and a log '
     + 'of grants nobody made is worse than none');
}

console.log('\nNot for somebody who is no longer a regional');
{
  /* The box can still be ticked from before the role was changed in the same
     form. Sending it would ask the server to grant reach to an account that
     is about to stop being a regional. */
  const w = world({ role: 'corporate' });
  w.document.getElementById('peAllComms').checked = true;
  await w.savePersonEdit('carol.brinegar');
  ok(!w.calls.some(c => /all-communities/.test(c.url)), 'nothing is sent');
}

console.log('\nA refusal is shown, not swallowed');
{
  const w = world({ grantFails: true });
  w.document.getElementById('peAllComms').checked = true;
  await w.savePersonEdit('carol.brinegar');
  const msg = w.document.getElementById('peMsg');
  ok(/nope/.test(msg.textContent), 'the reason is on the form');
  ok(w.closed === 0, 'and the form stays open');
}

console.log(failures ? `\n${failures} failure(s)` : '\nReach is a switch, and the region stays.');
process.exit(failures ? 1 : 0);
