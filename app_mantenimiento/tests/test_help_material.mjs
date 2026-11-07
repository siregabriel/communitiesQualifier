/*
  Help material on a standard, as people see it: on the visit form, in the
  Standards editor, and in the community panel / Action Items.

  Gabriel (Nov 2026): on the "Atlerts App" standard a regional should be able
  to download the Atlerts flyer during the visit and pass it to the Executive
  Director; the ED should find it again later. Titles and file names are typed
  by people, so each place is checked with one carrying markup and quotes.
  The server side is test_help_material.py.
*/

import fs from 'fs';
import { JSDOM } from 'jsdom';

const rep = fs.readFileSync(new URL('../templates/reporte.html', import.meta.url), 'utf8');
const qm = fs.readFileSync(new URL('../templates/question_manager.html', import.meta.url), 'utf8');
const dash = fs.readFileSync(new URL('../templates/dashboard.html', import.meta.url), 'utf8');

let failures = 0;
const ok = (c, m) => { console.log((c ? '  ok   ' : '  FAIL ') + m); if (!c) failures++; };
const grabFrom = (src) => (name) => {
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

const HELP = { id: 'res_1', title: 'Atlerts "flyer" <img src=x onerror=alert(1)>', kind: 'file',
  filename: 'atlerts-flyer.pdf', content_type: 'application/pdf',
  download: '/api/resources/res_1/download', file: '/api/resources/res_1/file' };

console.log('\nOn the visit form');
for (const canShare of [true, false]) {
  const w = new JSDOM('<!doctype html><body></body>', { runScripts: 'outside-only' }).window;
  if (canShare) w.navigator.share = async () => {};
  w.eval(`${grabFrom(rep)('helpMaterialRow')}\n${grabFrom(rep)('shareHelpMaterial')}`);
  w.document.body.append(w.helpMaterialRow(HELP));
  const d = w.document;
  ok(!d.querySelector('img'), `${canShare ? 'phone' : 'desktop'}: a title is text, not markup`);
  ok(d.querySelector('.help-row-text b').textContent === HELP.title, 'and reads as written');
  ok(d.querySelector('.help-row-text small').textContent === 'PDF', 'with its kind');
  ok(d.querySelector('.help-download').getAttribute('href') === HELP.download, 'Download goes to the signed-in download');
  ok(!!d.querySelector('.help-share') === canShare, canShare ? 'Share where the phone can share' : 'no Share where it cannot');
  ok(w.helpMaterialRow(null) === null, 'and nothing at all for a standard without one');
}

console.log('\nShare hands the file itself to the share sheet');
{
  const w = new JSDOM('<!doctype html><body><button id="b"></button></body>', { runScripts: 'outside-only', url: 'http://localhost/reporte' }).window;
  const shared = [], opened = [];
  w.navigator.share = async (data) => { shared.push(data); };
  w.navigator.canShare = () => true;
  w.fetch = async (u) => ({ ok: u === HELP.file, blob: async () => new w.Blob(['%PDF'], { type: 'application/pdf' }) });
  w.open = (u) => opened.push(u);
  w.eval(grabFrom(rep)('shareHelpMaterial'));
  await w.shareHelpMaterial(HELP, w.document.getElementById('b'));
  ok(shared.length === 1 && shared[0].files && shared[0].files[0].name === 'atlerts-flyer.pdf', 'the PDF goes to the share sheet, named as uploaded');
  ok(opened.length === 0, 'without opening anything else');
  w.navigator.canShare = () => false;
  await w.shareHelpMaterial(HELP, w.document.getElementById('b'));
  ok(opened[0] === HELP.download, 'a phone that cannot share files downloads it instead');
  w.navigator.canShare = () => true;
  w.navigator.share = async () => { const e = new Error('x'); e.name = 'AbortError'; throw e; };
  const before = opened.length;
  await w.shareHelpMaterial(HELP, w.document.getElementById('b'));
  ok(opened.length === before, 'closing the share sheet is a choice: nothing else happens');
  ok(!w.document.getElementById('b').disabled, 'and the button comes back');
}

console.log('\nIn the Standards editor');
{
  const w = new JSDOM('<!doctype html><body><select id="helpResource"></select></body>', { runScripts: 'outside-only' }).window;
  w.eval(`var helpResources = [{ id: 'res_1', title: '<b>Atlerts</b> flyer', kind: 'file', filename: 'a.pdf' },
                               { id: 'res_2', title: 'Guide', kind: 'link' }];
          ${grabFrom(qm)('fillHelpSelect')}`);
  w.fillHelpSelect('res_1');
  const sel = w.document.getElementById('helpResource');
  ok(sel.value === 'res_1', 'the standard\'s material is the one picked');
  ok(!sel.querySelector('b') && sel.options[1].textContent === '<b>Atlerts</b> flyer · PDF', 'titles are text, with their kind');
  ok(sel.options[0].value === '' && sel.options[0].textContent === 'None', 'None is first');
  w.fillHelpSelect('res_gone');
  ok(sel.value === '', 'something no longer in Resources shows None');
}

console.log('\nIn the community panel and Action Items');
{
  const w = new JSDOM('<!doctype html><body><div id="h"></div></body>', { runScripts: 'outside-only' }).window;
  w.navigator.share = async () => {};
  w.eval(`${grabFrom(dash)('decodeEntities')}\n${grabFrom(dash)('escapeHtml')}\n${grabFrom(dash)('escapeHtmlForAttr')}\n${grabFrom(dash)('helpRowHtml')}`);
  w.document.getElementById('h').innerHTML = w.helpRowHtml({ help: HELP });
  const d = w.document;
  ok(!d.querySelector('#h img') && d.querySelector('.help-row-text b').textContent === HELP.title, 'a title is text, not markup');
  const share = d.querySelector('[data-help-share]');
  ok(share && share.dataset.helpShare === 'res_1' && !share.hasAttribute('onclick'), 'Share is wired by the id, not an onclick string');
  ok(w.helpRowHtml(null) === '' && w.helpRowHtml({}) === '', 'nothing for a standard without one');
  ok(/helpRowHtml\(std\)/.test(dash) && /helpRowHtml\(standardFor\(item\)\)/.test(dash), 'shown with each response and each finding');
}

console.log(failures ? `\n${failures} failed` : '\nall passed');
process.exit(failures ? 1 : 0);
