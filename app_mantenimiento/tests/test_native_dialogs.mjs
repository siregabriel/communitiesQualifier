/*
  The app's questions and overlays are native <dialog>s (Nov 2026).

  A modern-web review found ~100 confirm()/alert()/prompt() calls and the
  modals built as <div>s shown with a class. On a phone, where most visits
  are filed, the browser's boxes freeze the page and show the site's address
  as their title; the <div> modals ignored Escape and the back gesture and let
  focus wander behind them. Now:

    * every question goes through uiConfirm / uiAlert / uiPrompt
      (static/dialogs.js), and nothing calls the browser's own again;
    * those answer correctly — OK, Cancel, Escape — and never read the
      message as HTML (it carries people's and communities' names);
    * the person, move-in, photo and Standards-editor overlays are <dialog>s;
    * the same review's head fixes stay: Font Awesome is pinned by hash, the
      phone's bar is navy, fonts are preconnected.
*/
import fs from 'fs';
import { JSDOM } from 'jsdom';
import { DIALOGS_JS } from './helpers/dialogs.mjs';

let failures = 0;
const ok = (c, m) => { console.log((c ? '  ok   ' : '  FAIL ') + m); if (!c) failures++; };
const read = (p) => fs.readFileSync(new URL(p, import.meta.url), 'utf8');

const PAGES = ['dashboard', 'question_manager', 'reporte', 'login', 'change_password',
               'select_survey_type', '_sidebar', 'mobile_tabbar', 'standards_print'];
const tpl = Object.fromEntries(PAGES.map(n => [n, read(`../templates/${n}.html`)]));

// ------------------------------------------------------------------------
console.log('\nNothing asks with the browser\'s own boxes any more');
{
  // Only // comments are taken out. Block comments are left in: a naive
  // /* … */ strip also eats from accept="image/*" to the next */, which hid
  // a reintroduced confirm() when this was first written.
  const stripComments = (js) => js.replace(/(^|\s)\/\/.*$/gm, '$1');
  const native = /(?:^|[^.\w])(?:window\.)?(confirm|alert|prompt)\s*\(/g;
  const found = [];
  for (const [name, src] of Object.entries(tpl)) {
    for (const m of src.matchAll(/<script[^>]*>([\s\S]*?)<\/script>/g)) {
      for (const hit of stripComments(m[1]).matchAll(native)) found.push(`${name}: ${hit[0].trim()}`);
    }
    // inline handlers too
    for (const m of src.matchAll(/\son\w+="([^"]*)"/g)) {
      for (const hit of m[1].matchAll(native)) found.push(`${name} (attribute): ${hit[0].trim()}`);
    }
  }
  for (const f of fs.readdirSync(new URL('../static/', import.meta.url)).filter(f => f.endsWith('.js'))) {
    for (const hit of stripComments(read(`../static/${f}`)).matchAll(native)) found.push(`static/${f}: ${hit[0].trim()}`);
  }
  ok(found.length === 0, `no confirm(), alert() or prompt() left (${found.slice(0, 5).join('; ')})`);

  for (const name of ['dashboard', 'question_manager', 'reporte', 'login']) {
    const at = tpl[name].indexOf("static_v('dialogs.js')");
    const firstUse = tpl[name].search(/ui(Confirm|Alert|Prompt|Open)\(/);
    ok(at > 0 && at < firstUse, `${name} loads dialogs.js before it asks anything`);
  }
}

// ------------------------------------------------------------------------
function world() {
  const w = new JSDOM('<!doctype html><body><button id="before">x</button></body>',
                      { runScripts: 'outside-only' }).window;
  w.eval(DIALOGS_JS);
  return w;
}
const open = (w) => w.document.querySelector('dialog.ui-dialog[open]');
const tick = () => new Promise(r => setTimeout(r, 0));
const btn = (w, cls) => open(w).querySelector('.' + cls);

console.log('\nuiConfirm answers what was chosen');
{
  const w = world();
  let p = w.uiConfirm('Delete this comment?');
  await tick();
  ok(!!open(w), 'it opens a dialog');
  btn(w, 'ui-dialog-ok').click();
  ok(await p === true, 'OK is yes');
  ok(!w.document.querySelector('dialog.ui-dialog'), 'and the dialog is gone afterwards');

  p = w.uiConfirm('Delete this comment?');
  await tick();
  btn(w, 'ui-dialog-cancel').click();
  ok(await p === false, 'Cancel is no');

  p = w.uiConfirm('Delete this comment?');
  await tick();
  w.uiClose(open(w));          // what Escape or the back gesture does
  ok(await p === false, 'Escape is no, never a silent yes');
}

console.log('\nThe message is text, never HTML');
{
  const w = world();
  const name = 'Angie\'s <img src=x onerror="window.__pwned=1"> Place';
  const p = w.uiConfirm(`Remove ${name}?\n\nThey will lose access.`, { ok: 'Remove', danger: true });
  await tick();
  const d = open(w);
  ok(!d.querySelector('img'), 'a name with markup in it stays words');
  ok(d.querySelector('.ui-dialog-msg').textContent.includes('\n\nThey will lose access.'),
     'line breaks survive (CSS shows them with pre-line)');
  ok(btn(w, 'ui-dialog-danger').textContent === 'Remove', 'the button says what it does');
  ok(w.document.activeElement === btn(w, 'ui-dialog-cancel'), 'a destructive question starts on Cancel');
  ok(d.getAttribute('aria-labelledby') === d.querySelector('.ui-dialog-msg').id, 'the dialog is named by its message');
  btn(w, 'ui-dialog-cancel').click();
  await p;
}

console.log('\nOne question at a time');
{
  const w = world();
  const a = w.uiAlert('First');
  const b = w.uiConfirm('Second');
  await tick();
  ok(w.document.querySelectorAll('dialog.ui-dialog').length === 1, 'the second waits');
  ok(open(w).textContent.includes('First'), 'the first is shown first');
  ok(!btn(w, 'ui-dialog-cancel'), 'an alert has only OK');
  btn(w, 'ui-dialog-ok').click();
  await a; await tick();
  ok(open(w) && open(w).textContent.includes('Second'), 'then the second');
  btn(w, 'ui-dialog-ok').click();
  ok(await b === true, 'and it answers on its own');
}

console.log('\nuiPrompt');
{
  const w = world();
  let p = w.uiPrompt('Rename region:', 'Coastal');
  await tick();
  const input = open(w).querySelector('input');
  ok(input.value === 'Coastal', 'starts with the current value');
  input.value = 'Gulf Coast';
  // Enter while an input method is still composing picks the word; it must not answer.
  input.dispatchEvent(new w.KeyboardEvent('keydown', { key: 'Enter', isComposing: true, bubbles: true }));
  ok(!!open(w), 'Enter mid-composition does not answer');
  input.dispatchEvent(new w.KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
  ok(await p === 'Gulf Coast', 'Enter answers with what was typed');

  p = w.uiPrompt('Optional: what was fixed?');
  await tick();
  btn(w, 'ui-dialog-cancel').click();
  ok(await p === null, 'Cancel is null, as prompt() was, so callers can tell it from an empty answer');
}

// ------------------------------------------------------------------------
console.log('\nThe overlays are <dialog>s');
{
  const expect = { dashboard: ['personModal', 'moveInModal', 'moveInTemplateModal', 'photoLightbox'],
                   question_manager: ['questionModal', 'deleteModal'] };
  for (const [page, ids] of Object.entries(expect)) {
    const doc = new JSDOM(tpl[page]).window.document;
    for (const id of ids) {
      const el = doc.getElementById(id);
      ok(el && el.tagName === 'DIALOG', `${page}: #${id} is a <dialog>`);
      ok(el && !el.hasAttribute('role') && !el.hasAttribute('aria-modal'),
         `${page}: #${id} carries no role/aria-modal of its own (the element provides them)`);
      ok(el && (el.hasAttribute('aria-label') || el.hasAttribute('aria-labelledby')), `${page}: #${id} has a name`);
      ok(new RegExp(`uiOpen\\(document\\.getElementById\\('${id}'\\)\\)|getElementById\\('${id}'\\)[\\s\\S]{0,2000}?uiOpen\\(`).test(tpl[page]),
         `${page}: #${id} is opened with uiOpen (showModal), not a class`);
    }
  }
  // Not one way in through a class: "some uiOpen exists" passes while a
  // second opener still adds .show.
  const byClass = [];
  for (const [page, ids] of Object.entries(expect)) {
    for (const id of ids) {
      if (new RegExp(`getElementById\\('${id}'\\)\\.classList`).test(tpl[page])) byClass.push(`${page} #${id}`);
    }
  }
  for (const v of ['modal', 'host', 'box']) {
    if (new RegExp(`\\b${v}\\.classList\\.(add|remove|contains)\\('show'\\)`).test(tpl.dashboard)) byClass.push(`dashboard ${v}.classList`);
  }
  ok(byClass.length === 0, `no dialog is shown or hidden with a class (${byClass.join(', ')})`);

  const theme = read('../static/theme.css');
  ok(/dialog:modal\s*\{[^}]*overscroll-behavior:\s*contain/.test(theme) &&
     /dialog::backdrop\s*\{[^}]*overflow:\s*hidden[^}]*overscroll-behavior:\s*contain/.test(theme),
     'scrolling over a dialog or its backdrop does not move the page behind');

  // Found in WebKit and Chromium before the first push: the questions opened
  // stuck to the top-left corner. Browsers centre a modal with margin: auto,
  // and the pages start with * { margin: 0 }, which wins over the browser's
  // own rule. jsdom gets this cascade backwards (its built-in dialog rule
  // beats the page's), so it cannot show the bug; the rule itself is checked.
  const rule = (sel) => ((new RegExp(sel.replace(/[.*]/g, '\\$&') + '\\s*\\{([^}]*)\\}').exec(theme) || [])[1] || '').replace(/\/\*[\s\S]*?\*\//g, '');
  ok(/(^|;|\s)margin:\s*auto/.test(rule('.ui-dialog')), 'a question keeps margin: auto, so it is centred, not pinned to the corner');
  ok(/box-sizing:\s*border-box/.test(rule('dialog.modal, dialog.pm-overlay, dialog.plb')),
     'a full-screen overlay keeps its padding inside the screen');
}

// ------------------------------------------------------------------------
console.log('\nThe <head>');
{
  // Published by cdnjs for font-awesome 6.4.0 css/all.min.css, and checked
  // against the downloaded file (Nov 2026).
  const FA = 'sha512-iecdLmaskl7CVkqkXNQ/ZH/XLlvWZOJyj7Yy7tcenmpD1ypASozpmT/E0iPtmFIB46ZmdtAc9eNBvH0H/ZpiBw==';
  for (const [name, src] of Object.entries(tpl)) {
    const doc = new JSDOM(src).window.document;
    for (const el of doc.querySelectorAll('script[src^="http"], link[rel="stylesheet"][href^="http"]')) {
      const url = el.getAttribute('src') || el.getAttribute('href');
      if (url.startsWith('https://fonts.googleapis.com/')) continue;   // changes in place by design; cannot be pinned
      ok(el.getAttribute('integrity') && el.getAttribute('crossorigin') === 'anonymous',
         `${name}: ${url.split('/').slice(-3).join('/')} is pinned by hash`);
      if (url.includes('font-awesome/6.4.0/css/all.min.css')) ok(el.getAttribute('integrity') === FA, `${name}: with the right hash`);
    }
    const tc = doc.querySelector('meta[name="theme-color"]');
    if (tc) ok(tc.getAttribute('content') === '#003366', `${name}: the phone's bar is navy (${tc.getAttribute('content')})`);
    if (doc.querySelector('link[href^="https://fonts.googleapis.com/css2"]')) {
      ok(!!doc.querySelector('link[rel="preconnect"][href="https://fonts.gstatic.com"][crossorigin]'),
         `${name}: the font files' host is preconnected (anonymous, as fonts are fetched)`);
    }
  }
  ok(JSON.parse(read('../static/manifest.json')).theme_color === '#003366', 'the installed app is navy too');
}

console.log(failures ? `\n${failures} failed` : '\nThe app asks its own questions.');
process.exit(failures ? 1 : 0);
