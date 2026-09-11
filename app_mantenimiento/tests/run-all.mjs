/*
  Run every .mjs suite and report what happened.

  There was no such thing: each suite was run by hand, one command per file,
  which works while somebody is watching and not at all otherwise. Adding a
  suite meant remembering to add it to whatever loop was being typed that day,
  so a new file could sit there passing nobody's attention.

  This finds them by looking, so a suite that exists is a suite that runs.

  Two things it is careful about. It reports the count it found, because "0
  suites, all passed" is the failure mode of anything that globs — green and
  empty look identical from the outside. And it exits non-zero if any suite
  fails or if it finds none at all.
*/

import { spawnSync } from 'child_process';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const here = path.dirname(fileURLToPath(import.meta.url));

const suites = fs.readdirSync(here)
  .filter(f => f.endsWith('.mjs') && f !== path.basename(fileURLToPath(import.meta.url)))
  .sort();

if (!suites.length) {
  console.error('No .mjs suites found in ' + here + ' — that is the bug, not a pass.');
  process.exit(1);
}

console.log(`Running ${suites.length} suites\n`);

const failed = [];
for (const file of suites) {
  const r = spawnSync(process.execPath, [path.join(here, file)], { encoding: 'utf8' });
  const out = (r.stdout || '') + (r.stderr || '');
  const ok = r.status === 0;
  if (!ok) failed.push(file);

  // The last line of a passing suite is its own one-line summary. Print that
  // when it passed, and everything when it did not — reading seventeen full
  // transcripts to find one failure is how a failure gets missed.
  const lines = out.trim().split('\n').filter(Boolean);
  const summary = lines[lines.length - 1] || '(no output)';
  console.log(`${ok ? '  ok  ' : '  FAIL'}  ${file.padEnd(30)} ${ok ? summary : ''}`);
  if (!ok) {
    console.log(out.split('\n').map(l => '        ' + l).join('\n'));
  }
}

console.log();
if (failed.length) {
  console.error(`${failed.length} of ${suites.length} suites failed: ${failed.join(', ')}`);
  process.exit(1);
}
console.log(`All ${suites.length} suites passed.`);
