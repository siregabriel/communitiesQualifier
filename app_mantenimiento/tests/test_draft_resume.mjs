/*
  Picking up an unfinished visit, run end to end in the browser's own code.

  A draft is stored under community + survey type. Arriving at the form without
  both means it is not found, and the work reads as lost — that is the whole
  bug this feature exists to fix. So the chain has to hold all the way through:

      the list links to /reporte/resume
        -> which puts the survey type in the session
        -> and hands the form the community
        -> which the form selects
        -> which loads that community's questions
        -> which is what finally lets draftInit build the key and find it.

  Reading that chain and believing it is how the first version of this shipped
  pointing at a route that does not exist. This runs it.
*/

import fs from 'fs';
import { JSDOM } from 'jsdom';

const html = fs.readFileSync(new URL('../templates/reporte.html', import.meta.url), 'utf8');

let failures = 0;
const ok = (c, m) => { console.log((c ? '  ok   ' : '  FAIL ') + m); if (!c) failures++; };

const COMMUNITY = 'Kelley Place, Enterprise';
const SURVEY = 'standards';

/* The page as a regional would receive it, with the two Jinja values filled in
   the way the server fills them. */
function boot(search) {
  const script = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)]
    .map((m) => m[1]).reduce((a, b) => (b.length > a.length ? b : a), '')
    .replace(/\{\{\s*survey_type_id\s*\}\}/g, SURVEY)
    // The server also renders the department list into the page. Left as a
    // Jinja placeholder it is a syntax error, and the whole script fails to
    // load — which shows up as every function being undefined rather than as
    // anything pointing at the template.
    .replace(/\{\{\s*departments\s*\|\s*tojson\s*\}\}/g,
             JSON.stringify([{ id: 'maintenance', name: 'Maintenance' }]))
    // And the positions the nearby-community suggestion compares against.
    .replace(/\{\{\s*community_places\s*\|\s*tojson\s*\}\}/g, '[]');

  const dom = new JSDOM(`<!doctype html><html><body>
    <div id="userInfo"></div>
    <div class="loading-message" id="loadingMessage"></div>
    <div class="loading-message" id="communityPrompt" style="display:none;"></div>
    <select id="communitySelect">
      <option value="">— Select a community in your region —</option>
      <option value="${COMMUNITY}">${COMMUNITY}</option>
      <option value="Somewhere Else">Somewhere Else</option>
    </select>
    <form id="reportForm" style="display:none;"><button type="submit">Submit Visit</button></form>
    <div id="questionsContainer"></div>
    <div id="draftChip"></div><div id="draftBanner"></div><div id="draftStatus"></div>
    <textarea id="visitNotes"></textarea><div id="notesCount"></div>
    </body></html>`, { runScripts: 'dangerously', url: 'http://localhost/reporte' + search });

  const w = dom.window;
  const calls = { questionsFor: null, draftKeys: [] };

  w.fetch = async (url) => {
    if (String(url).startsWith('/api/user-info')) {
      return { ok: true, json: async () => ({ display_name: 'Marissa Scott',
        username: 'marissa', community: null, role: 'regional', is_admin: false }) };
    }
    if (String(url).startsWith('/api/questions')) {
      calls.questionsFor = String(url);
      // One real question: with none, the page hides the submit button and
      // stops early, which would be testing the empty-survey path instead.
      return { ok: true, json: async () => ({ status: 'success', questions: [
        { id: 'q1', text: 'Fire extinguisher tags are current', photo_required: false },
      ] }) };
    }
    if (String(url).startsWith('/api/drafts')) return { ok: true, json: async () => ({}) };
    return { ok: true, json: async () => ({}) };
  };

  // Run it as a real script, not through eval: `let` at the top of an eval
  // stays inside that eval, so the page's own state would be unreadable from
  // here and every assertion about it would quietly pass on undefined.
  const el = w.document.createElement('script');
  el.textContent = script;
  w.document.body.appendChild(el);
  return { w, calls };
}

const settle = () => new Promise((r) => setTimeout(r, 20));

console.log('\nArriving from the list of unfinished visits');
{
  const { w, calls } = boot(`?community=${encodeURIComponent(COMMUNITY)}`);
  await w.loadUserInfo();
  await settle();

  ok(w.document.getElementById('communitySelect').value === COMMUNITY,
     'the community named in the link is selected for them');
  // `let` at the top of a script is not a property of window — reading it
  // from outside gives undefined, which is how a passing assertion here can
  // mean nothing at all.
  ok(w.eval('selectedCommunity') === COMMUNITY, 'and the page knows which one it is');
  // Compare the parsed query, not the raw string: URLSearchParams writes a
  // space as "+", and expecting "%20" fails against perfectly correct code.
  const asked = new URL(calls.questionsFor || '', 'http://x').searchParams;
  ok(asked.get('community') === COMMUNITY,
     `that community's questions are the ones loaded (${asked.get('community')})`);
  ok(asked.get('survey_type') === SURVEY,
     'for the survey type the session was set to');

  const key = w.eval('draftKey()');
  ok(key === `${SURVEY}::${COMMUNITY}`,
     `the draft is looked for under the pair it was saved under (${key})`);
}

console.log('\nArriving the normal way, with no community named');
{
  const { w } = boot('');
  await w.loadUserInfo();
  await settle();
  ok(w.document.getElementById('communitySelect').value === '',
     'nothing is chosen for them');
  ok(w.eval('draftKey()') === null, 'and no draft is looked for until they pick one');
}

console.log('\nA link naming a community they cannot pick');
{
  // The roster changes. A stale link must not select something that is not
  // in their list, or the form would load questions for a community the
  // server will refuse.
  const { w, calls } = boot('?community=' + encodeURIComponent('A Community They Lost'));
  await w.loadUserInfo();
  await settle();
  ok(w.document.getElementById('communitySelect').value === '', 'nothing is selected');
  ok(calls.questionsFor === null, 'and no questions are fetched for it');
}

console.log('\nWhat goes to the server with each save');
{
  /* This used to assert the opposite: that only a signpost (community, type,
     count, device) ever left the phone. Greg Crutcher then lost 33 answers
     that existed nowhere else, and the text of a draft is now sent on
     purpose. Photos still never ride in that request — they go one at a time
     as files, so a single save is never a multi-megabyte upload. */
  const body = html.slice(html.indexOf('function draftServerBody'), html.indexOf('async function draftOk'));
  for (const field of ['community', 'survey_type_id', 'responses', 'action_items', 'notes', 'total', 'saved_at', 'device']) {
    ok(new RegExp(field + ':').test(body), `the text request carries ${field}`);
  }
  ok(!/photos|blob/.test(body), 'and never the photos');
  const photos = html.slice(html.indexOf('async function serverSyncPhotos'), html.indexOf("window.addEventListener('online'"));
  ok(/\/api\/drafts\/photo/.test(photos) && /new FormData\(\)/.test(photos),
     'photos go separately, as files');
  ok(/_photoSent\[slot\] === sig\) continue/.test(photos), 'and only the ones the server does not have yet');
  const sync = html.slice(html.indexOf('async function serverSyncNow'), html.indexOf('function draftPhotoSlots'));
  ok(/shape !== _syncShape/.test(sync), 'and the text only when it actually changed, not on every keystroke');
}

console.log('\nWhen the draft goes, so does the signpost');
{
  ok(/noticeClear\(\);/.test(html.slice(html.indexOf('async function discardDraft'),
                                        html.indexOf('function draftStatus'))),
     'discarding clears it');
  const submit = html.slice(html.indexOf('if (response.ok) {'), html.indexOf('} else if (response.status === 413)'));
  ok(/noticeClear\(\)/.test(submit), 'and so does submitting');
  ok(/draftIsEmpty\(data\)\) \{[\s\S]{0,200}noticeClear\(\)/.test(html),
     'and emptying the form leaves nothing pointing at nothing');
}

console.log(failures ? `\n${failures} failure(s)` : '\nAn unfinished visit can be picked up again.');
process.exit(failures ? 1 : 0);
