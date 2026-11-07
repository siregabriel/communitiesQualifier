/*
  Changing the visit type from the form.

  Gabriel: once a visit was started there was no way back to the type —
  somebody who picked the wrong one had to go Home, tap New Visit, choose the
  type and the community again. The type's tag now has "Change": back to
  choosing the type, carrying the community already chosen. Answers so far
  are kept as that type's draft; if there are any, it says so first and
  Cancel keeps them on the form. This boots the real form and clicks it.
*/

import fs from 'fs';
import { JSDOM, VirtualConsole } from 'jsdom';

const html = fs.readFileSync(new URL('../templates/reporte.html', import.meta.url), 'utf8');

let failures = 0;
const ok = (c, m) => { console.log((c ? '  ok   ' : '  FAIL ') + m); if (!c) failures++; };

const COMMUNITY = "Angie's Place, Ocoee";
const QUESTIONS = [{ id: 'q1', text: 'Lobby clean', photo_required: false }];
const badge = html.slice(html.indexOf('<div class="survey-type-badge" id="surveyTypeBadge"'), html.indexOf('<script>', html.indexOf('id="surveyTypeBadge"')))
  .replace(/\{\{\s*survey_type\.name\s*\}\}/g, 'Sales & Marketing').replace(/\{\{[\s\S]*?\}\}/g, '');

function boot(confirmAnswer = true) {
  const script = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)]
    .map((m) => m[1]).reduce((a, b) => (b.length > a.length ? b : a), '')
    .replace(/\{\{\s*survey_type_id\s*\}\}/g, 'sales')
    .replace(/\{\{\s*departments\s*\|\s*tojson\s*\}\}/g, '[]')
    .replace(/\{\{\s*community_places\s*\|\s*tojson\s*\}\}/g, '[]');
  const vc = new VirtualConsole();   // jsdom cannot follow the link; that is fine
  const dom = new JSDOM(`<!doctype html><html><body>
    ${badge}
    <div id="userInfo"></div>
    <div class="loading-message" id="loadingMessage"></div>
    <div class="loading-message" id="communityPrompt" style="display:none;"></div>
    <select id="communitySelect"><option value="">—</option><option value="${COMMUNITY}">${COMMUNITY}</option></select>
    <form id="reportForm" style="display:none;"><button type="submit">Submit Visit</button></form>
    <div id="questionsContainer"></div>
    <div id="progressContainer"><div id="progressFill"></div><div id="progressMessage"></div></div>
    <div id="draftChip"></div><div id="draftBanner"></div><div id="draftStatus"></div>
    <textarea id="visitNotes"></textarea><div id="notesCount"></div>
    <div id="successScreen"></div>
    </body></html>`, { runScripts: 'dangerously', virtualConsole: vc,
      url: 'http://localhost/reporte?community=' + encodeURIComponent(COMMUNITY) });
  const w = dom.window;
  const confirms = [];
  w.confirm = (m) => { confirms.push(String(m)); return confirmAnswer; };
  w.alert = () => {};
  w.Element.prototype.scrollIntoView = function () {};
  w.scrollTo = function () {};
  w.matchMedia = () => ({ matches: false, addEventListener() {}, removeEventListener() {} });
  w.fetch = async (url) => {
    const u = String(url);
    if (u.startsWith('/api/user-info')) return { ok: true, json: async () => ({ display_name: 'Marissa Scott',
      username: 'marissa', community: null, role: 'regional', is_admin: false }) };
    if (u.startsWith('/api/questions')) return { ok: true, json: async () => ({ status: 'success', questions: QUESTIONS }) };
    return { ok: true, json: async () => ({}) };
  };
  const el = w.document.createElement('script');
  el.textContent = script;
  w.document.body.appendChild(el);
  return { w, confirms };
}
const settle = () => new Promise((r) => setTimeout(r, 30));
async function ready(confirmAnswer) {
  const ctx = boot(confirmAnswer);
  await ctx.w.loadUserInfo();
  await settle();
  ctx.w.document.getElementById('communitySelect').value = COMMUNITY;
  return ctx;
}
function click(w) {
  const link = w.document.getElementById('changeTypeLink');
  const ev = new w.MouseEvent('click', { bubbles: true, cancelable: true });
  link.dispatchEvent(ev);
  return { link, prevented: ev.defaultPrevented };
}

console.log('\nNothing answered yet: straight back, community kept');
{
  const { w, confirms } = await ready();
  ok(!!w.document.getElementById('changeTypeLink'), 'the type tag offers Change');
  const { link, prevented } = click(w);
  ok(!prevented, 'it goes');
  ok(link.getAttribute('href') === '/select-survey-type?community=' + encodeURIComponent(COMMUNITY),
     `to choosing the type, with the community (${link.getAttribute('href')})`);
  ok(confirms.length === 0, 'without asking, since there is nothing to keep');
}

console.log('\nWith answers: it says they are kept, and Cancel stays');
{
  const stay = await ready(false);
  const input = stay.w.document.querySelector('input[name="condition_q1"][value="Pass"]');
  input.checked = true;
  input.dispatchEvent(new stay.w.Event('change', { bubbles: true }));
  const r1 = click(stay.w);
  ok(stay.confirms.length === 1 && /stay saved as a draft/.test(stay.confirms[0]) && /Sales & Marketing/.test(stay.confirms[0]),
     `it says the answers stay as a draft of this type (${(stay.confirms[0] || '').split('\n')[0]})`);
  ok(r1.prevented, 'Cancel keeps them on the form');

  const go = await ready(true);
  const i2 = go.w.document.querySelector('input[name="condition_q1"][value="Pass"]');
  i2.checked = true;
  i2.dispatchEvent(new go.w.Event('change', { bubbles: true }));
  const r2 = click(go.w);
  ok(!r2.prevented, 'OK goes to choosing the type');
}

console.log(failures ? `\n${failures} failed` : '\nall passed');
process.exit(failures ? 1 : 0);
