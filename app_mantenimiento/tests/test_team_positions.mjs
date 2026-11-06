/*
  Adding and removing Staff positions from the People form, run rather than read.

  Gabriel needed a Move In Coordinator and the list was fixed in the code. Now
  "Add or remove positions" under the Position field changes it on the server,
  and the dropdown follows at once, with the new one picked. A position taken
  out of the list stays on the form of whoever still holds it, or saving their
  email would quietly clear it. The server side is test_team_positions.py.
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

// `reply(url, body)` decides what the server answers.
function boot(positions, reply) {
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
    ${grab('wirePositionManager')}
    ${grab('drawPositionManager')}
    ${grab('changeTeamPositions')}
    var isAdmin = true;
    var currentUsername = 'gabriel';
    var peopleData = { people: [${JSON.stringify(CHRIS)}], regions: [], communities: ['Venice'],
                       team_positions: ${JSON.stringify(positions)}, can_grant_admin: true };
    function closePersonModal() {}
    function peOnRoleChange() {}
    function apOnRoleChange() {}
    function apRenderExtraComms() {}
  `);
  w.fetch = async (url, opts) => {
    const body = JSON.parse(opts.body);
    posted.push({ url, body });
    const [status, data] = reply(url, body);
    return { ok: status < 400, status, json: async () => data };
  };
  return { w, posted };
}

const settle = () => new Promise(r => setTimeout(r, 0));
const optionValues = (sel) => Array.from(sel.options).map(o => o.value);

console.log('\nThe dropdown is the list the server sent');
{
  const { w } = boot([...SIX, 'Move In Coordinator'], () => [200, {}]);
  w.openAddPerson();
  const sel = w.document.getElementById('apPosition');
  ok(JSON.stringify(optionValues(sel)) === JSON.stringify(['', ...SIX, 'Move In Coordinator']),
     'all of them, in order, after "Select"');
  ok(sel.value === '', 'and nothing is picked for a new person');
}

console.log('\nAdding a position from the Add person form');
{
  const { w, posted } = boot(SIX, (url, body) =>
    [201, { status: 'success', name: body.name, positions: [...SIX, body.name] }]);
  w.openAddPerson();
  const d = w.document;
  const box = d.getElementById('apPositionManager');
  ok(box.hidden, 'the manager starts closed');
  d.getElementById('apPositionManage').click();
  ok(!box.hidden, 'the link opens it');
  ok(box.querySelectorAll('.pos-row').length === SIX.length, 'listing every position');
  box.querySelector('.pos-new').value = '  Move In Coordinator ';
  box.querySelector('.pos-add-btn').click();
  await settle();
  ok(posted.length === 1 && posted[0].url === '/api/team-positions', 'it posts to the server');
  ok(posted[0] && posted[0].body.name === 'Move In Coordinator', 'the name that was typed, trimmed');
  const sel = d.getElementById('apPosition');
  ok(optionValues(sel).includes('Move In Coordinator'), 'the dropdown gains it');
  ok(sel.value === 'Move In Coordinator', 'and picks it, since that is why it was added');
  ok(w.peopleData.team_positions.includes('Move In Coordinator'), 'the edit form will offer it too');
  ok(/Added Move In Coordinator/.test(box.textContent), 'and says so');
}

console.log('\nEnter adds too; an empty box sends nothing');
{
  const { w, posted } = boot(SIX, (url, body) =>
    [201, { status: 'success', name: body.name, positions: [...SIX, body.name] }]);
  w.openAddPerson();
  const d = w.document;
  d.getElementById('apPositionManage').click();
  const input = d.querySelector('#apPositionManager .pos-new');
  input.value = '   ';
  d.querySelector('#apPositionManager .pos-add-btn').click();
  await settle();
  ok(posted.length === 0, 'nothing for blanks');
  input.value = 'Concierge';
  input.dispatchEvent(new w.KeyboardEvent('keydown', { key: 'Enter' }));
  await settle();
  ok(posted.length === 1 && posted[0].body.name === 'Concierge', 'Enter sends it');
}

console.log('\nWhen the server says no');
{
  const { w } = boot(SIX, () =>
    [400, { status: 'error', message: 'Give it a name that is not already in the list' }]);
  w.openAddPerson();
  const d = w.document;
  d.getElementById('apPositionManage').click();
  d.querySelector('#apPositionManager .pos-new').value = 'Executive Chef';
  d.querySelector('#apPositionManager .pos-add-btn').click();
  await settle();
  ok(/not already in the list/.test(d.querySelector('#apPositionManager .pos-msg').textContent),
     'the reason is shown');
  ok(w.peopleData.team_positions.length === SIX.length, 'and the list is unchanged');
}

console.log('\nRemoving one');
{
  const { w, posted } = boot(SIX, (url, body) =>
    [200, { status: 'success', name: body.name, positions: SIX.filter(n => n !== body.name) }]);
  w.openAddPerson();
  const d = w.document;
  const sel = d.getElementById('apPosition');
  sel.value = 'Wellness Director';
  d.getElementById('apPositionManage').click();
  const row = Array.from(d.querySelectorAll('#apPositionManager .pos-row'))
    .find(r => r.textContent.includes('Wellness Director'));
  row.querySelector('.pos-remove').click();
  await settle();
  ok(posted[0] && posted[0].url === '/api/team-positions/remove', 'it posts the removal');
  ok(posted[0] && posted[0].body.name === 'Wellness Director', 'for the row that was clicked');
  ok(!optionValues(sel).includes('Wellness Director'), 'the dropdown loses it');
  ok(sel.value === '', 'and a new person is no longer set to it');
}

console.log('\nThe last one cannot be removed');
{
  const { w } = boot(['Executive Chef'], () => [200, {}]);
  w.openAddPerson();
  w.document.getElementById('apPositionManage').click();
  ok(w.document.querySelector('#apPositionManager .pos-remove').disabled, 'its button is off');
}

console.log('\nA name with quotes cannot break out (handlers attached in JS)');
{
  const odd = `Chef's "Sous" <i>Lead</i>`;
  const { w, posted } = boot([...SIX, odd], (url, body) =>
    [200, { status: 'success', name: body.name, positions: SIX }]);
  w.openAddPerson();
  const d = w.document;
  ok(optionValues(d.getElementById('apPosition')).includes(odd), 'the option value is the exact name');
  d.getElementById('apPositionManage').click();
  ok(!d.querySelector('#apPositionManager i'), 'no markup from the name is rendered');
  const rows = d.querySelectorAll('#apPositionManager .pos-row');
  rows[rows.length - 1].querySelector('.pos-remove').click();
  await settle();
  ok(posted[0] && posted[0].body.name === odd, 'and removing it sends the exact name');
}

console.log('\nWhoever holds a removed position keeps it on their form');
{
  const without = SIX.filter(n => n !== 'Executive Chef');
  const { w } = boot(without, () => [200, {}]);
  w.openPersonEdit('chris.oconnor');
  const sel = w.document.getElementById('pePosition');
  ok(sel.value === 'Executive Chef', `Chris's own position is still selected (${sel.value})`);
  const opt = Array.from(sel.options).find(o => o.value === 'Executive Chef');
  ok(opt && /no longer offered/.test(opt.textContent), 'marked as no longer offered');
  ok(optionValues(sel).filter(v => v === 'Executive Chef').length === 1, 'listed once');
}

console.log('\nAnd when it is still offered, it is not marked');
{
  const { w } = boot(SIX, () => [200, {}]);
  w.openPersonEdit('chris.oconnor');
  const sel = w.document.getElementById('pePosition');
  ok(sel.value === 'Executive Chef', 'selected');
  ok(!/no longer offered/.test(sel.textContent), 'no mark');
}

console.log(failures ? `\n${failures} failure(s)` : '\nStaff positions are run from People.');
process.exit(failures ? 1 : 0);
