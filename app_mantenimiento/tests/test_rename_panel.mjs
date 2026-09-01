/*
  The control that changes somebody's sign-in name, run rather than read.

  It is one link and one input, but it is the only field in that form that
  moves a person's whole history, so the things worth holding down are who can
  see it, that it cannot be aimed at the built-in administrator, and that it
  posts the name that was typed to the account that was open.
*/

import fs from 'fs';
import { JSDOM } from 'jsdom';

const html = fs.readFileSync(new URL('../templates/dashboard.html', import.meta.url), 'utf8');

let failures = 0;
const ok = (c, m) => { console.log((c ? '  ok   ' : '  FAIL ') + m); if (!c) failures++; };

const grab = (name) => {
  let i = html.indexOf(`function ${name}(`);
  if (i < 0) throw new Error('not found: ' + name);
  // Take the `async` with it: slicing from `function` alone drops the keyword
  // and the extracted source stops parsing at its first await.
  if (html.slice(i - 6, i) === 'async ') i -= 6;
  let depth = 0;
  for (let k = html.indexOf('{', i); k < html.length; k++) {
    if (html[k] === '{') depth++;
    else if (html[k] === '}' && --depth === 0) return html.slice(i, k + 1);
  }
};

function boot(person, { admin = true } = {}) {
  const dom = new JSDOM(`<!doctype html><body>
    <div id="personModal"><div id="personModalBody"></div></div>
    </body>`, { runScripts: 'outside-only' });
  const w = dom.window;
  const posted = [];

  w.eval(`
    ${grab('escapeHtml')}
    ${grab('decodeEntities')}
    ${grab('escapeHtmlForAttr')}
    ${grab('coverageChecklist')}
    ${grab('openPersonEdit')}
    ${grab('startUsernameChange')}
    ${grab('saveUsername')}
    var isAdmin = ${admin};
    var currentUsername = 'gabriel';
    var peopleData = { people: [${JSON.stringify(person)}], regions: [],
                       can_grant_admin: true };
    function closePersonModal() {}
    async function renderPeople() {}
    // Bits of the panel this test is not about.
    function peOnRoleChange() {}
    function apRenderExtraComms() {}
  `);
  w.fetch = async (url, opts) => {
    posted.push({ url, body: JSON.parse(opts.body) });
    return { ok: true, json: async () => ({ status: 'success', message: 'done' }) };
  };
  return { w, posted };
}

const JAZMYN = {
  username: 'jazmyn.frasier', name: 'Jazmyn Frazier', email: 'j@x.com',
  role: 'staff', community: 'Kelley Place, Enterprise', communities: [],
  source: 'user', title: '', region_id: null, admin_extra: false,
};

console.log('\nWho gets offered it');
{
  const { w } = boot(JAZMYN);
  w.openPersonEdit('jazmyn.frasier');
  const d = w.document;
  ok(!!d.querySelector('.pe-rename-link'), 'an administrator is offered the change');
  ok(d.getElementById('peUserWrap').style.display === 'none',
     'but it starts folded away — it is rare, and it is not a label');
  ok(d.getElementById('peUsername').value === 'jazmyn.frasier',
     'and opens on the name they have now');
}

{
  const { w } = boot(JAZMYN, { admin: false });
  w.openPersonEdit('jazmyn.frasier');
  ok(!w.document.querySelector('.pe-rename-link'),
     'somebody who is not an administrator is not offered it');
}

{
  const { w } = boot({ ...JAZMYN, username: 'admin', name: 'Administrator' });
  w.openPersonEdit('admin');
  ok(!w.document.querySelector('.pe-rename-link'),
     'and the built-in administrator is not offered it at all — it lives in code');
}

console.log('\nChanging it');
{
  const { w, posted } = boot(JAZMYN);
  w.openPersonEdit('jazmyn.frasier');
  w.startUsernameChange();
  ok(w.document.getElementById('peUserWrap').style.display === 'block', 'the panel opens');

  w.document.getElementById('peUsername').value = '  Jazmyn.FRAZIER  ';
  await w.saveUsername('jazmyn.frasier');

  ok(posted.length === 1, 'one request went out');
  ok(posted[0].url === '/api/people/jazmyn.frasier/username',
     `aimed at the account that was open (${posted[0].url})`);
  ok(posted[0].body.new_username === 'jazmyn.frazier',
     `trimmed and lowered before sending (${posted[0].body.new_username})`);
}

{
  const { w, posted } = boot(JAZMYN);
  w.openPersonEdit('jazmyn.frasier');
  w.startUsernameChange();
  w.document.getElementById('peUsername').value = 'jazmyn.frasier';
  await w.saveUsername('jazmyn.frasier');
  ok(posted.length === 0, 'the same name again is not sent anywhere');
  ok(/type the new username/i.test(w.document.getElementById('peUserMsg').textContent),
     'and says so');
}

{
  const { w, posted } = boot(JAZMYN);
  w.openPersonEdit('jazmyn.frasier');
  w.startUsernameChange();
  w.document.getElementById('peUsername').value = '   ';
  await w.saveUsername('jazmyn.frasier');
  ok(posted.length === 0, 'an empty box is not sent either');
}

console.log('\nWhen the server says no');
{
  const { w } = boot(JAZMYN);
  w.openPersonEdit('jazmyn.frasier');
  w.startUsernameChange();
  w.fetch = async () => ({ ok: false, json: async () =>
    ({ status: 'error', message: '"jazmyn.frazier" is already in use.' }) });
  w.document.getElementById('peUsername').value = 'jazmyn.frazier';
  await w.saveUsername('jazmyn.frasier');
  const msg = w.document.getElementById('peUserMsg');
  ok(/already in use/.test(msg.textContent), 'the reason is shown, not swallowed');
  ok(msg.classList.contains('error'), 'as an error');
}

{
  const { w } = boot(JAZMYN);
  w.openPersonEdit('jazmyn.frasier');
  w.startUsernameChange();
  w.fetch = async () => { throw new Error('offline'); };
  w.document.getElementById('peUsername').value = 'jazmyn.frazier';
  await w.saveUsername('jazmyn.frasier');
  ok(/nothing was changed/i.test(w.document.getElementById('peUserMsg').textContent),
     'and a dropped connection says nothing was changed, rather than leaving it open');
}

console.log(failures ? `\n${failures} failure(s)` : '\nThe rename control does what it says.');
process.exit(failures ? 1 : 0);
