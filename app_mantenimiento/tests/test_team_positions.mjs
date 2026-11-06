/*
  Staff positions: managed in Settings, only picked in People. Run, not read.

  Gabriel needed a Move In Coordinator and the list was fixed in the code. The
  first fix let positions be added from inside Add/Edit person, which is
  exactly where somebody would invent one while adding a person. He wanted
  control: the list is run from Settings, and the person form only offers
  what is there. A position taken out of the list stays on the form of whoever
  still holds it, or saving their email would quietly clear it. The server
  side is test_team_positions.py.
*/

import fs from 'fs';
import { JSDOM } from 'jsdom';

const html = fs.readFileSync(new URL('../templates/dashboard.html', import.meta.url), 'utf8');

let failures = 0;
const ok = (c, m) => { console.log((c ? '  ok   ' : '  FAIL ') + m); if (!c) failures++; };

const grab = (name) => {
  let i = html.indexOf(`function ${name}(`);
  if (i < 0) throw new Error('not found: ' + name);
  if (html.slice(i - 6, i) === 'async ') i -= 6;
  let depth = 0;
  for (let k = html.indexOf('{', i); k < html.length; k++) {
    if (html[k] === '{') depth++;
    else if (html[k] === '}' && --depth === 0) return html.slice(i, k + 1);
  }
  throw new Error('unbalanced braces in ' + name);
};

const SIX = ['Sales and Marketing Director', 'Business Office Director', 'Wellness Director',
             'Lifestyles Director', 'Executive Chef', 'Director of Buildings Services'];

const CHRIS = {
  username: 'chris.oconnor', name: 'Chris OConnor', email: 'chris@venice.com',
  role: 'team', position: 'Executive Chef', community: 'Venice', communities: ['Venice'],
  source: 'user', title: 'Executive Chef', region_id: null, admin_extra: false,
};

const settle = () => new Promise(r => setTimeout(r, 0));
const optionValues = (sel) => Array.from(sel.options).map(o => o.value);

// ------------------------------------------------------------ the person form

function bootPeople(positions) {
  const dom = new JSDOM(`<!doctype html><body>
    <div id="personModal"><div id="personModalBody"></div></div></body>`, { runScripts: 'outside-only' });
  const w = dom.window;
  const posted = [];
  w.eval(`
    ${grab('escapeHtml')}
    ${grab('decodeEntities')}
    ${grab('escapeHtmlForAttr')}
    ${grab('coverageChecklist')}
    ${grab('wirePersonAtlerts')}
    ${grab('regionalExtraChecklist')}
    ${grab('wirePersonExtras')}
    ${grab('checkedCoverage')}
    ${grab('openPersonEdit')}
    ${grab('openAddPerson')}
    ${grab('fillPositionSelect')}
    var isAdmin = true;
    var currentUsername = 'gabriel';
    var peopleData = { people: [${JSON.stringify(CHRIS)}], regions: [], communities: ['Venice'],
                       team_positions: ${JSON.stringify(positions)}, can_grant_admin: true };
    function closePersonModal() {}
    function peOnRoleChange() {}
    function apOnRoleChange() {}
    function apRenderExtraComms() {}
  `);
  w.fetch = async (url, opts) => { posted.push(url); return { ok: true, json: async () => ({}) }; };
  return { w, posted };
}

console.log('\nAdd person offers the list, and only the list');
{
  const { w } = bootPeople([...SIX, 'Move In Coordinator']);
  w.openAddPerson();
  const d = w.document;
  const sel = d.getElementById('apPosition');
  ok(JSON.stringify(optionValues(sel)) === JSON.stringify(['', ...SIX, 'Move In Coordinator']),
     'all of them, in order, after "Select"');
  ok(sel.value === '', 'nothing picked for a new person');
  const wrap = d.getElementById('apPositionWrap');
  ok(!wrap.querySelector('input, button'), 'no way to type or add a position here');
  ok(/managed in Settings/.test(wrap.textContent), 'and it says where they are managed');
}

console.log('\nEdit person: the same, nothing to add');
{
  const { w } = bootPeople(SIX);
  w.openPersonEdit('chris.oconnor');
  const wrap = w.document.getElementById('pePositionWrap');
  ok(!wrap.querySelector('input, button'), 'no way to type or add a position here');
  const sel = w.document.getElementById('pePosition');
  ok(sel.value === 'Executive Chef', 'his position is selected');
  ok(!/no longer offered/.test(sel.textContent), 'and not marked, since it is offered');
}

console.log('\nWhoever holds a removed position keeps it on their form');
{
  const { w } = bootPeople(SIX.filter(n => n !== 'Executive Chef'));
  w.openPersonEdit('chris.oconnor');
  const sel = w.document.getElementById('pePosition');
  ok(sel.value === 'Executive Chef', `Chris's own position is still selected (${sel.value})`);
  const opt = Array.from(sel.options).find(o => o.value === 'Executive Chef');
  ok(opt && /no longer offered/.test(opt.textContent), 'marked as no longer offered');
  ok(optionValues(sel).filter(v => v === 'Executive Chef').length === 1, 'listed once');
}

console.log('\nNobody new is offered a removed position');
{
  const { w } = bootPeople(SIX.filter(n => n !== 'Executive Chef'));
  w.openAddPerson();
  ok(!optionValues(w.document.getElementById('apPosition')).includes('Executive Chef'), 'not in Add person');
}

// ------------------------------------------------------------------ Settings

// `server` holds the list the fake server keeps, so a reload shows the change.
function bootSettings(list, { fail } = {}) {
  const dom = new JSDOM(`<!doctype html><body>
    <div id="tpList"></div><input id="tpNew"><button id="tpAdd"></button><span id="tpMsg"></span>
    </body>`, { runScripts: 'outside-only' });
  const w = dom.window;
  const server = list.map(n => (typeof n === 'string' ? { name: n, active: true } : n));
  const posted = [];
  const active = () => server.filter(p => p.active).map(p => p.name);
  w.fetch = async (url, opts) => {
    if (!opts || !opts.method || opts.method === 'GET') {
      return { ok: true, json: async () => ({ status: 'success', positions: server.map(p => ({ ...p })) }) };
    }
    const body = JSON.parse(opts.body);
    posted.push({ url, body });
    if (fail) return { ok: false, json: async () => ({ status: 'error', message: fail }) };
    const hit = server.find(p => p.name.toLowerCase() === body.name.toLowerCase());
    if (url === '/api/team-positions') { if (hit) hit.active = true; else server.push({ name: body.name, active: true }); }
    else if (hit) hit.active = false;
    return { ok: true, json: async () => ({ status: 'success', name: hit ? hit.name : body.name, positions: active() }) };
  };
  w.eval(`
    var peopleData = { team_positions: [] };
    ${grab('_tpSay')}
    ${grab('loadTeamPositionAdmin')}
    ${grab('wireTeamPositionAdmin')}
    ${grab('changeTeamPosition')}
  `);
  return { w, posted, server };
}

const rows = (w) => Array.from(w.document.querySelectorAll('#tpList .rc-row'));
const rowFor = (w, name) => rows(w).find(r => r.querySelector('.rc-name').textContent === name);

console.log('\nSettings lists every position, removed ones marked');
{
  const { w } = bootSettings([...SIX, { name: 'Night Nurse', active: false }]);
  await w.loadTeamPositionAdmin();
  ok(rows(w).length === 7, 'one row each');
  const gone = rowFor(w, 'Night Nurse');
  ok(gone && gone.classList.contains('rc-off') && /Removed/.test(gone.textContent), 'the removed one says so');
  ok(gone && gone.querySelector('button').textContent === 'Bring back', 'and can be brought back');
  ok(rowFor(w, 'Executive Chef').querySelector('button').textContent === 'Remove', 'the others can be removed');
}

console.log('\nAdding the Move In Coordinator');
{
  const { w, posted } = bootSettings(SIX);
  w.wireTeamPositionAdmin();
  await w.loadTeamPositionAdmin();
  w.document.getElementById('tpNew').value = '  Move In Coordinator ';
  w.document.getElementById('tpAdd').click();
  await settle(); await settle();
  ok(posted.length === 1 && posted[0].url === '/api/team-positions', 'it posts to the server');
  ok(posted[0] && posted[0].body.name === 'Move In Coordinator', 'the name typed, trimmed');
  ok(!!rowFor(w, 'Move In Coordinator'), 'the list shows it');
  ok(w.peopleData.team_positions.includes('Move In Coordinator'), 'People will offer it without a reload');
  ok(w.document.getElementById('tpNew').value === '', 'the box is cleared');
  ok(/in the list/.test(w.document.getElementById('tpMsg').textContent), 'and it says so');
}

console.log('\nEnter adds too; a blank box sends nothing');
{
  const { w, posted } = bootSettings(SIX);
  w.wireTeamPositionAdmin();
  const box = w.document.getElementById('tpNew');
  box.value = '   ';
  w.document.getElementById('tpAdd').click();
  await settle();
  ok(posted.length === 0, 'nothing for blanks');
  ok(/Give it a name/.test(w.document.getElementById('tpMsg').textContent), 'and says why');
  box.value = 'Concierge';
  box.dispatchEvent(new w.KeyboardEvent('keydown', { key: 'Enter' }));
  await settle();
  ok(posted.length === 1 && posted[0].body.name === 'Concierge', 'Enter sends it');
}

console.log('\nRemoving and bringing back');
{
  const { w, posted } = bootSettings(SIX);
  await w.loadTeamPositionAdmin();
  rowFor(w, 'Wellness Director').querySelector('button').click();
  await settle(); await settle();
  ok(posted[0] && posted[0].url === '/api/team-positions/remove', 'Remove posts the removal');
  ok(posted[0] && posted[0].body.name === 'Wellness Director', 'for the row clicked');
  ok(!w.peopleData.team_positions.includes('Wellness Director'), 'People stops offering it');
  ok(/keeps it/.test(w.document.getElementById('tpMsg').textContent), 'and says holders keep it');
  rowFor(w, 'Wellness Director').querySelector('button').click();
  await settle(); await settle();
  ok(posted[1] && posted[1].url === '/api/team-positions', 'Bring back posts it again');
  ok(w.peopleData.team_positions.includes('Wellness Director'), 'and People offers it again');
}

console.log('\nThe last one cannot be removed');
{
  const { w } = bootSettings(['Executive Chef', { name: 'Gone', active: false }]);
  await w.loadTeamPositionAdmin();
  ok(rowFor(w, 'Executive Chef').querySelector('button').disabled, 'its button is off');
  ok(!rowFor(w, 'Gone').querySelector('button').disabled, 'bringing one back still works');
}

console.log('\nWhen the server says no');
{
  const { w } = bootSettings(SIX, { fail: 'Give it a name that is not already in the list' });
  w.wireTeamPositionAdmin();
  w.document.getElementById('tpNew').value = 'Executive Chef';
  w.document.getElementById('tpAdd').click();
  await settle(); await settle();
  ok(/not already in the list/.test(w.document.getElementById('tpMsg').textContent), 'the reason is shown');
  ok(w.document.getElementById('tpNew').value === 'Executive Chef', 'and what was typed is kept');
}

console.log('\nA name with quotes or markup cannot break out');
{
  const odd = `Chef's "Sous" <i>Lead</i>`;
  const { w, posted } = bootSettings([...SIX, odd]);
  await w.loadTeamPositionAdmin();
  ok(!w.document.querySelector('#tpList i'), 'no markup from the name is rendered');
  rowFor(w, odd).querySelector('button').click();
  await settle();
  ok(posted[0] && posted[0].body.name === odd, 'removing it sends the exact name');
}

console.log('\nSettings shows the section to admins and loads it');
{
  const at = html.indexOf('id="tpList"');
  const gate = html.lastIndexOf('${admin ?', at);
  const close = html.indexOf("` : ''}", gate);
  ok(at > 0 && gate > 0 && close > at, 'the section sits inside the admin-only part of Settings');
  ok(/if \(admin\) \{[^}]*loadTeamPositionAdmin\(\)/.test(html.slice(html.indexOf('async function renderSettings'))),
     'and renderSettings loads it for admins');
}

console.log(failures ? `\n${failures} failure(s)` : '\nStaff positions are managed in Settings.');
process.exit(failures ? 1 : 0);
