/*
  The letters in an avatar when there is no photo.

  It took the first two characters of the whole string, so Angie Surls was AN
  and Kelse Henderson was KE. Plausible enough at a glance that it sat there
  for months and was reported by somebody looking at a screen full of them —
  every person without an uploaded photo, on every screen that draws one.

  The People view and the assign-leader list had the right version, written
  out inline in both. Three copies of one rule, two of which were not the one
  in use. That is the part this file is really about: they share a function
  now, and the test asserts there is nothing left to drift.
*/

import fs from 'fs';

const html = fs.readFileSync(new URL('../templates/dashboard.html', import.meta.url), 'utf8');

let failures = 0;
const ok = (c, m) => { console.log((c ? '  ok   ' : '  FAIL ') + m); if (!c) failures++; };

const grab = (name) => {
  const i = html.indexOf(`function ${name}(`);
  if (i < 0) throw new Error('not found: ' + name);
  let p = 0, after = -1;
  for (let k = html.indexOf('(', i); k < html.length; k++) {
    if (html[k] === '(') p++;
    else if (html[k] === ')' && --p === 0) { after = k + 1; break; }
  }
  let d = 0;
  for (let k = html.indexOf('{', after); k < html.length; k++) {
    if (html[k] === '{') d++;
    else if (html[k] === '}' && --d === 0) return html.slice(i, k + 1);
  }
};

const profileInitials = new Function(`${grab('profileInitials')} return profileInitials;`)();

console.log('\nThe six that were reported');
{
  // Taken straight off the screenshot, with what each was showing.
  const reported = [
    ['Angie Surls',          'AS', 'AN'],
    ['Kelse Henderson',      'KH', 'KE'],
    ['Carol Brinegar',       'CB', 'CA'],
    ['Ricky Kirk',           'RK', 'RI'],
    ['Keely Mcdonald',       'KM', 'KE'],
    ['Candice Butterfield',  'CB', 'CA'],
  ];
  for (const [name, want, was] of reported) {
    const got = profileInitials(name);
    ok(got === want, `${name} is ${want}, not ${was} (${got})`);
  }
}

console.log('\nAnd the shapes a name comes in');
{
  ok(profileInitials('gabriel.rosales') === 'GR',
     'a username splits on the dot, so it is GR and not GA');
  ok(profileInitials('jo-ellen.spivey') === 'JS',
     'a hyphen inside a first name is part of it');
  ok(profileInitials('Gabriel Rosales Montes') === 'GR',
     'three names take the first two, the same as the People view always has');
  ok(profileInitials('  Angie   Surls  ') === 'AS', 'extra spaces are nothing');
  ok(profileInitials('someone@atlas.com') === 'SA', 'an email address is two words to this');
}

console.log('\nWhen there is barely a name');
{
  ok(profileInitials('Cher') === 'CH',
     'one name still gets two letters — a lone C reads as an error, not a person');
  ok(profileInitials('') === '?', 'nothing is a question mark');
  ok(profileInitials(null) === '?', 'and so is nothing at all');
  ok(profileInitials(undefined) === '?', 'however it arrives');
  ok(profileInitials('   ') === '?', 'including whitespace pretending to be a name');
}

console.log('\nOne rule, in one place');
{
  // The bug existed because the rule was written three times and the copy in
  // use was the wrong one. A fourth copy is the same bug waiting.
  const inline = html.match(/split\(\/\[\\s@\.\]\+\/\)\.filter\(Boolean\)\.slice\(0, 2\)/g) || [];
  ok(inline.length === 0,
     `nothing spells the rule out inline any more (${inline.length} left)`);

  const defs = html.match(/function profileInitials\s*\(/g) || [];
  ok(defs.length === 1, `and it is defined once (${defs.length})`);

  const uses = (html.match(/profileInitials\(/g) || []).length - defs.length;
  ok(uses >= 8, `with everything drawing an avatar going through it (${uses} call sites)`);
}

console.log('\nIt is upper case, whatever was typed');
{
  ok(profileInitials('angie surls') === 'AS', 'lower case in');
  ok(profileInitials('ANGIE SURLS') === 'AS', 'and shouting');
}

console.log(failures ? `\n${failures} failure(s)` : '\nInitials are the initials.');
process.exit(failures ? 1 : 0);
