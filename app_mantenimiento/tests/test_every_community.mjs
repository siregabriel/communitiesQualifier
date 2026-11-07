/*
  "Every community" and bulk community changes on the Standards page, run in
  the page's own code.

  Greg Crutcher had to open every standard to add a new community (Nov 2026).
  The editor now has an "Every community" box that sets the list aside, the
  table says so, and selected standards can have one community added or
  removed in one click. The box is a <label> inside .form-group, whose caption
  rule (spaced capitals) is more specific than a bare class: the first draft
  lost to it, so the computed style is checked here too. Server side:
  test_every_community.py.
*/

import fs from 'fs';
import { JSDOM } from 'jsdom';

const html = fs.readFileSync(new URL('../templates/question_manager.html', import.meta.url), 'utf8');

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

// A slice of the real markup, from the first tag to the end of a balanced div.
const markup = (startText) => {
  const start = html.indexOf(startText);
  if (start < 0) throw new Error('markup not found: ' + startText);
  let depth = 0;
  const tag = /<(\/?)div\b[^>]*>/g;
  tag.lastIndex = start;
  let m;
  while ((m = tag.exec(html))) {
    depth += m[1] ? -1 : 1;
    if (depth === 0) return html.slice(start, m.index + m[0].length);
  }
  throw new Error('not balanced: ' + startText);
};

const COMMS = ['Kelley Place', 'Naples Place', 'Madison at Ocoee'];
const jinja = (s) => s
  .replace(/\{%\s*for community in communities\s*%\}([\s\S]*?)\{%\s*endfor\s*%\}/g, (_, body) =>
    COMMS.map((c, i) => body.replace(/\{\{\s*community\|plain\s*\}\}/g, c)
                            .replace(/\{\{\s*community\s*\}\}/g, c)
                            .replace(/\{\{\s*loop\.index\s*\}\}/g, String(i + 1))).join(''));

const formGroup = jinja(markup('<div class="form-group">\n                    <label><i class="fas fa-building"></i> Assigned Communities</label>'));
const toolbar = jinja(markup('<div class="filter-section">'));
const css = [...html.matchAll(/<style>([\s\S]*?)<\/style>/g)].map(m => m[1]).join('\n');

function boot({ dark = false, questions = [] } = {}) {
  const dom = new JSDOM(`<!doctype html><html ${dark ? 'data-theme="dark"' : ''}><head><style>${css}</style></head><body>
    ${toolbar}
    <table><tbody id="questionsBody"></tbody></table><input type="checkbox" id="selectAllRows">
    <div id="questionModal"><form id="questionForm">
      <h2 id="modalTitle"></h2><input id="questionId"><input id="questionText"><textarea id="interpretiveGuideline"></textarea>
      <textarea id="passCriteria"></textarea><input type="checkbox" id="photoRequired"><div id="textError"></div>
      <input type="checkbox" id="selectAllSurveyTypes"><div id="selectedSurveyTypesCount"></div>
      ${formGroup}
    </form></div></body></html>`, { runScripts: 'dangerously' });
  const w = dom.window;
  const posted = [];
  const confirms = [];
  const alerts = [];
  w.confirm = (m) => { confirms.push(m); return true; };
  w.alert = (m) => alerts.push(m);
  let server = questions.map(q => ({ ...q }));
  w.fetch = async (url, opts) => {
    if (opts && opts.method && opts.method !== 'GET') {
      const body = JSON.parse(opts.body);
      posted.push({ url, method: opts.method, body });
      return { ok: true, json: async () => ({ status: 'success', changed: body.ids || [], unchanged: [], refused: [] }) };
    }
    return { ok: true, json: async () => ({ status: 'success', questions: server }) };
  };
  w.eval(`
    var questions = [], allQuestions = [], surveyTypes = [], currentQuestionId = null;
    ${grab('escapeHtml')}
    ${grab('decodeEntities')}
    ${grab('getSurveyTypeBadges')}
    ${grab('renderQuestions')}
    ${grab('filterQuestions')}
    ${grab('loadQuestions')}
    ${grab('getSelectedQuestionIds')}
    ${grab('updateBulkActions')}
    ${grab('setEveryCommunity')}
    ${grab('updateSelectedCount')}
    ${grab('updateSelectedSurveyTypesCount')}
    ${grab('openCreateModal')}
    ${grab('openEditModal')}
    ${grab('changeSelectedCommunities')}
    ${grab('wireBulkCommunities')}
    function checkEmptySurveyTypes() {}
    function closeModal() {}
  `);
  // The page's real submit handler, lifted out of its addEventListener call.
  const start = html.indexOf("document.getElementById('questionForm').addEventListener('submit'");
  const fnStart = html.indexOf('async (e) =>', start);
  let depth = 0, end = -1;
  for (let k = html.indexOf('{', fnStart); k < html.length; k++) {
    if (html[k] === '{') depth++;
    else if (html[k] === '}' && --depth === 0) { end = k + 1; break; }
  }
  w.eval(`document.getElementById('questionForm').addEventListener('submit', ${html.slice(fnStart, end)});`);
  w.wireBulkCommunities();
  return { w, posted, confirms, alerts };
}

const settle = () => new Promise(r => setTimeout(r, 0));

console.log('\nThe table says when a standard reaches every community');
{
  const { w } = boot({ questions: [
    { id: 'q_a', text: 'Lobby clean', created_at: '2026-01-01', survey_types: [], communities: [], all_communities: true },
    { id: 'q_b', text: 'Pool fenced', created_at: '2026-01-02', survey_types: [], communities: ['Kelley Place'] },
  ] });
  await w.loadQuestions();
  const rows = [...w.document.querySelectorAll('#questionsBody tr')];
  ok(/Every community/.test(rows[0].textContent), 'the every-community one says "Every community"');
  ok(!/Every community/.test(rows[1].textContent), 'the other shows its list');
}

console.log('\nThe editor: "Every community" sets the list aside');
{
  const { w, posted } = boot({ questions: [
    { id: 'q_a', text: 'Lobby clean', created_at: '2026-01-01', survey_types: [], communities: ['Kelley Place'], all_communities: true },
  ] });
  await w.loadQuestions();
  w.openEditModal('q_a');
  const box = w.document.getElementById('everyCommunity');
  ok(box.checked, 'opening one that has it shows it ticked');
  ok(w.document.getElementById('communitySelector').classList.contains('is-every'), 'the list is greyed out');
  ok(/Every community, now and later/.test(w.document.getElementById('selectedCount').textContent), 'and the count says so');
  ok(w.document.querySelector('.community-checkbox[value="Kelley Place"]').checked,
     'the list underneath is kept, so unticking gives it back');
  box.checked = false;
  box.dispatchEvent(new w.Event('change'));
  ok(!w.document.getElementById('communitySelector').classList.contains('is-every'), 'unticked, the list comes back');
  ok(/1 community selected/.test(w.document.getElementById('selectedCount').textContent), 'with its own count');

  // Straight from editing one that has it, as happens: open it, then Create.
  w.openEditModal('q_a');
  ok(w.document.getElementById('everyCommunity').checked, '(back on an every-community standard)');
  w.openCreateModal();
  ok(!w.document.getElementById('everyCommunity').checked, 'a new standard starts without it');
  ok(!w.document.getElementById('communitySelector').classList.contains('is-every'), 'and with the list usable');
  w.document.getElementById('questionText').value = 'Exits lit';
  w.document.getElementById('everyCommunity').checked = true;
  w.document.getElementById('everyCommunity').dispatchEvent(new w.Event('change'));
  w.document.getElementById('questionForm').dispatchEvent(new w.Event('submit', { cancelable: true }));
  await settle();
  const sent = posted.find(p => p.url === '/api/questions');
  ok(sent && sent.body.all_communities === true, 'it is sent as every community');
  ok(sent && sent.body.communities.length === 0, 'with no boxes ticked, and that is allowed');
}

console.log('\nAdd or remove a community on the selected standards');
{
  const { w, posted, confirms, alerts } = boot({ questions: [
    { id: 'q_a', text: 'Month 4 - SMD', created_at: '2026-01-01', survey_types: [], communities: ['Kelley Place'] },
    { id: 'q_b', text: 'Month 4 - ED', created_at: '2026-01-02', survey_types: [], communities: ['Kelley Place'] },
  ] });
  await w.loadQuestions();
  const add = w.document.getElementById('bulkAddComm');
  const rem = w.document.getElementById('bulkRemoveComm');
  ok(add.disabled && rem.disabled, 'off until something is chosen');
  w.document.querySelectorAll('.row-select').forEach(cb => { cb.checked = true; });
  w.updateBulkActions();
  ok(add.disabled, 'still off with standards but no community');
  const sel = w.document.getElementById('bulkCommunity');
  sel.value = 'Madison at Ocoee';
  sel.dispatchEvent(new w.Event('change'));
  ok(!add.disabled && !rem.disabled, 'on with both');
  add.click();
  await settle(); await settle();
  const p = posted.find(x => x.url === '/api/questions/communities');
  ok(p && p.body.action === 'add' && p.body.community === 'Madison at Ocoee', 'adds that community');
  ok(p && JSON.stringify(p.body.ids.sort()) === JSON.stringify(['q_a', 'q_b']), 'to the selected standards');
  ok(/Add Madison at Ocoee to the 2 standards selected\?/.test(confirms[0] || ''), 'after asking');
  ok(/2 changed/.test(alerts[0] || ''), 'and says what happened');

  w.document.querySelectorAll('.row-select').forEach(cb => { cb.checked = true; });
  w.updateBulkActions();
  sel.value = 'Kelley Place';
  sel.dispatchEvent(new w.Event('change'));
  rem.click();
  await settle(); await settle();
  ok(/stop picking up new ones/.test(confirms[1] || ''), 'removing warns what it does to "Every community"');
}

console.log('\nHow it reads, light and dark (computed from the page\'s real CSS)');
{
  const rgb = (c) => (c.match(/[\d.]+/g) || []).map(Number);
  const over = (fg, bg) => { const [r, g, b, a = 1] = rgb(fg); const [R, G, B] = Array.isArray(bg) ? bg : rgb(bg); return [r * a + R * (1 - a), g * a + G * (1 - a), b * a + B * (1 - a)]; };
  const lum = ([r, g, b]) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; };
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
  const contrast = (a, b) => { const [x, y] = [lum(a), lum(b)].sort((m, n) => n - m); return (x + 0.05) / (y + 0.05); };
  for (const dark of [false, true]) {
    const mode = dark ? 'dark' : 'light';
    const { w } = boot({ dark });
    const cs = (el) => w.getComputedStyle(el);
    const label = w.document.querySelector('label.every-comm');
    ok(cs(label).textTransform === 'none', `${mode}: "Every community" is a sentence, not capitals (${cs(label).textTransform})`);
    const behind = rgb(cs(w.document.querySelector('.form-group')).backgroundColor);
    const bg = over(cs(label).backgroundColor, behind.length ? behind : [255, 255, 255]);
    for (const [name, el] of [['its heading', label.querySelector('b')], ['its explanation', label.querySelector('small')]]) {
      const c = contrast(rgb(cs(el).color).slice(0, 3), bg);
      ok(c >= 4.5, `${mode}: ${name} is readable (${c.toFixed(1)}:1)`);
    }
  }
}

console.log(failures ? `\n${failures} failure(s)` : '\nStandards can reach every community, and change many at once.');
process.exit(failures ? 1 : 0);
