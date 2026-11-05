/*
  Adding a Staff member from People, run rather than read.

  Staff belong to one community: the form must ask for it, must not offer
  "Also covers" (an Executive Director's), and must send role "team" — the
  "Area Manager" option it replaces sent "staff", which made an Executive
  Director. The server side is test_staff_role.py.
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

function world(role) {
  const dom = new JSDOM(`<!doctype html><body>
    <input id="apName" value="Cait Chef"><input id="apEmail" value="cait@thegoldtonatvenice.com">
    <select id="apRole">
      <option value="regional">r</option><option value="corporate">c</option>
      <option value="staff">ED</option><option value="team">Staff</option><option value="admin">a</option>
    </select>
    <div id="apTitleWrap"><input id="apTitle" value=""></div>
    <div id="apRegionWrap"><select id="apRegion"><option value="north">North</option></select></div>
    <div id="apCommunityWrap"><select id="apCommunity"><option value="">—</option>
      <option value="${VENICE}">${VENICE}</option><option value="Naples Place">Naples Place</option></select>
      <div class="cov-extra" id="apExtraWrap" style="display:none;"><div id="apExtraComms"></div></div>
    </div>
    <div id="apRoleNote"></div><span id="apMsg"></span></body>`, { runScripts: 'outside-only' });
  const w = dom.window;
  w.document.getElementById('apRole').value = role;
  w.document.getElementById('apCommunity').value = VENICE;
  w.eval(`
    var calls = [];
    var peopleData = { communities: ['${VENICE}', 'Naples Place'] };
    function escapeHtml(s) { return String(s); }
    function fetch(url, opts) { calls.push({ url, body: JSON.parse(opts.body) });
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ status: 'success', password: 'x', display_name: 'Cait' }) }); }
    function refreshPeopleViews() {} function closeAddPerson() {} function alert() {}
    function showNewCredentials() {} function renderPeople() {}
    ${grab('coverageChecklist')}
    ${grab('checkedCoverage')}
    ${grab('apRenderExtraComms')}
    ${grab('apOnRoleChange')}
    ${grab('submitAddPerson')}
  `);
  return w;
}

console.log('\nThe form offers Staff, not Area Manager');
ok(/<option value="team">Staff — one community<\/option>/.test(html), 'Staff is in the role list');
ok(!/Area Manager/.test(html), 'and the option that made Executive Directors is gone');

console.log('\nStaff: one community, no "Also covers"');
{
  const w = world('team');
  w.apOnRoleChange();
  ok(w.document.getElementById('apCommunityWrap').style.display !== 'none', 'the community is asked for');
  w.apRenderExtraComms();
  ok(w.document.getElementById('apExtraWrap').style.display === 'none', '"Also covers" is not offered');
  ok(/community's team/.test(w.document.getElementById('apRoleNote').textContent), 'and the note says what Staff can do');
}

console.log('\nAn Executive Director still gets "Also covers"');
{
  const w = world('staff');
  w.apOnRoleChange();
  w.apRenderExtraComms();
  ok(w.document.getElementById('apExtraWrap').style.display !== 'none', 'offered');
}

console.log('\nWhat is sent');
{
  const w = world('team');
  w.apOnRoleChange();
  await w.submitAddPerson();
  const body = w.calls[0] && w.calls[0].body;
  ok(body && body.role === 'team', `role "team", not "staff" (${body && body.role})`);
  ok(body && body.community === VENICE, 'with the community');
  ok(body && !('communities' in body), 'and no list of extra communities');

  const empty = world('team');
  empty.document.getElementById('apCommunity').value = '';
  await empty.submitAddPerson();
  ok(empty.calls.length === 0, 'without a community it does not send');
  ok(/Pick a community/.test(empty.document.getElementById('apMsg').textContent), 'and says why');
}

console.log(failures ? `\n${failures} failure(s)` : '\nStaff are added to one community.');
process.exit(failures ? 1 : 0);
