/*
  The app asks its questions with uiConfirm / uiAlert / uiPrompt
  (static/dialogs.js) instead of the browser's confirm(), alert() and
  prompt(). Suites that run page code need those functions in their window.

  installDialogs(w) loads the real static/dialogs.js — so uiOpen / uiClose
  open and close the pages' <dialog>s the way the pages do (jsdom has no
  showModal(); the file falls back to the open attribute) — and then, if
  answers are given, replaces the three questions with ones that answer at
  once and remember what they were asked:

      const asked = installDialogs(w, { confirm: false });
      ... asked.confirms[0], asked.alerts, asked.prompts
*/
import fs from 'fs';

export const DIALOGS_JS = fs.readFileSync(new URL('../../static/dialogs.js', import.meta.url), 'utf8');

export function installDialogs(w, answers) {
  w.eval(DIALOGS_JS);
  const asked = { confirms: [], alerts: [], prompts: [] };
  if (!answers) return asked;
  const pick = (a, m) => (typeof a === 'function' ? a(m) : a);
  w.uiConfirm = async (m) => { asked.confirms.push(String(m)); return pick(answers.confirm ?? true, String(m)); };
  w.uiAlert = async (m) => { asked.alerts.push(String(m)); };
  w.uiPrompt = async (m, v) => { asked.prompts.push(String(m)); return answers.prompt === undefined ? (v ?? '') : pick(answers.prompt, String(m)); };
  return asked;
}
