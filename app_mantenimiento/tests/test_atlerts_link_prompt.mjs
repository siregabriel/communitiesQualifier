/*
  The "Link your Atlerts account?" question on the sign-in page, and the
  Unlink button in People, run rather than read.

  Nine people reached Excellence from Atlerts with a personal address their
  account here does not carry, and were sent to the password screen every
  time. After that password sign-in they are now asked, once, to link the
  two. The server side is test_atlerts_link.py; this is the page.
*/

import fs from 'fs';
import { JSDOM } from 'jsdom';

const login = fs.readFileSync(new URL('../templates/login.html', import.meta.url), 'utf8');
const dash = fs.readFileSync(new URL('../templates/dashboard.html', import.meta.url), 'utf8');

let failures = 0;
const ok = (c, m) => { console.log((c ? '  ok   ' : '  FAIL ') + m); if (!c) failures++; };

const grab = (src, name) => {
  let i = src.indexOf(`function ${name}(`);
  if (i < 0) throw new Error(`no such function: ${name}`);
  if (src.slice(i - 6, i) === 'async ') i -= 6;
  let depth = 0;
  for (let k = src.indexOf('{', i); k < src.length; k++) {
    if (src[k] === '{') depth++;
    else if (src[k] === '}' && --depth === 0) return src.slice(i, k + 1);
  }
  throw new Error(`unbalanced braces in ${name}`);
};

const veilMarkup = login.slice(login.indexOf('<div id="atlertsLink"'),
                               login.indexOf('</div>\n    </div>', login.indexOf('<div id="atlertsLink"')) + 17);

function loginWorld({ ok: serverOk = true } = {}) {
  const dom = new JSDOM(`<!doctype html><body>${veilMarkup}</body>`, { runScripts: 'outside-only' });
  const w = dom.window;
  w.eval(`
    var calls = [], went = null, alerted = null;
    function fetch(url, opts) {
      calls.push({ url, body: JSON.parse(opts.body) });
      return Promise.resolve({ ok: ${serverOk}, json: () => Promise.resolve(
        ${serverOk} ? { status: 'success' } : { status: 'error', message: 'already linked to someone else' }) });
    }
    function alert(m) { alerted = m; }
    ${grab(login, 'offerAtlertsLink')}
  `);
  // window.location cannot be assigned in jsdom; watch the href setter instead.
  w.eval(`offerAtlertsLink = new Function('email', 'next',
    ${JSON.stringify(grab(login, 'offerAtlertsLink')
      .replace(/^async function offerAtlertsLink\(email, next\) \{|^function offerAtlertsLink\(email, next\) \{/, '')
      .replace(/\}$/, '')
      .replace('window.location.href = next;', 'went = next;'))});`);
  return w;
}

const tick = () => new Promise(r => setTimeout(r, 0));

console.log('\nAsked once, with the address that failed');
{
  const w = loginWorld();
  const veil = w.document.getElementById('atlertsLink');
  ok(veil.hidden === true, 'nothing is shown until there is something to ask');
  w.offerAtlertsLink('laurablakeman11@gmail.com', '/');
  ok(veil.hidden === false, 'the question appears');
  ok(w.document.getElementById('alEmail').textContent === 'laurablakeman11@gmail.com',
     'naming the address, so somebody it is not can say so');
}

console.log('\nThe address is text, never markup');
{
  const w = loginWorld();
  w.offerAtlertsLink('<img src=x onerror="pwned=1">@x.com', '/');
  ok(w.document.querySelector('#alEmail img') === null, 'an address cannot inject an element');
}

console.log('\nLink');
{
  const w = loginWorld();
  w.offerAtlertsLink('laurablakeman11@gmail.com', '/change-password');
  w.document.getElementById('alYes').onclick();
  await tick(); await tick();
  ok(w.calls.length === 1 && w.calls[0].url === '/api/atlerts-link', 'one request, to the link route');
  ok(w.calls[0].body.link === true, 'saying yes');
  ok(!('email' in w.calls[0].body),
     'without the address — the server takes it from the session, where Atlerts put it');
  ok(w.went === '/change-password', 'then on to wherever sign-in was going');
}

console.log('\nNot me');
{
  const w = loginWorld();
  w.offerAtlertsLink('laurablakeman11@gmail.com', '/');
  w.document.getElementById('alNo').onclick();
  await tick(); await tick();
  ok(w.calls[0].body.link === false, 'saying no, so the server forgets it');
  ok(w.went === '/', 'and they are in');
}

console.log('\nA refusal is said, and they are still let in');
{
  const w = loginWorld({ ok: false });
  w.offerAtlertsLink('laurablakeman11@gmail.com', '/');
  w.document.getElementById('alYes').onclick();
  await tick(); await tick();
  ok(/already linked/.test(w.alerted || ''), 'the reason is shown — otherwise Atlerts keeps failing and nobody knows why');
  ok(w.went === '/', 'and they are signed in anyway');
}

console.log('\nThe question waits for the answer');
{
  // The submit handler returns before redirecting when there is something to ask.
  const i = login.indexOf("if (data.atlerts_link) {");
  ok(i > 0, 'sign-in checks for an address to offer');
  const block = login.slice(i, login.indexOf('}', i));
  ok(/offerAtlertsLink\(data\.atlerts_link, next\);\s*return;/.test(block),
     'and stops there instead of navigating away from the question');
}

console.log('\nUnlink in People');
{
  const dom = new JSDOM(`<!doctype html><body>
    <div id="peAtlertsRow"><b class="pe-atlerts-email"></b>
      <button class="pe-atlerts-unlink"></button></div></body>`, { runScripts: 'outside-only' });
  const w = dom.window;
  w.eval(`
    var calls = [], refreshed = 0;
    function confirm() { return true; }
    function alert() {}
    function fetch(url, opts) { calls.push({ url, method: opts.method });
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ status: 'success' }) }); }
    async function refreshPeopleViews() { refreshed++; }
    ${grab(dash, 'wirePersonAtlerts')}
  `);
  const p = { username: "o'brien.k", name: 'K', atlerts_email: '<b>x</b>@gmail.com' };
  w.wirePersonAtlerts(p);
  ok(w.document.querySelector('.pe-atlerts-email').textContent === '<b>x</b>@gmail.com',
     'the linked address is shown as text');
  w.document.querySelector('.pe-atlerts-unlink').onclick();
  await tick(); await tick();
  ok(w.calls.length === 1 && w.calls[0].method === 'DELETE', 'unlinking sends a DELETE');
  ok(w.calls[0].url === "/api/people/o'brien.k/atlerts-link" ||
     w.calls[0].url === '/api/people/o\'brien.k/atlerts-link',
     `for that person, by a handler rather than a string of code (${w.calls[0].url})`);
  ok(!w.document.getElementById('peAtlertsRow'), 'and the row goes away');
  ok(w.refreshed === 1, 'and the list is refreshed');
}

console.log(failures ? `\n${failures} failure(s)` : '\nAtlerts can be linked, and unlinked.');
process.exit(failures ? 1 : 0);
