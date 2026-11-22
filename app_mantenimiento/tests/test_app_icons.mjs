/*
  The installed app's icons are real PNGs of the Atlas Excellence logo.

  Found in Nov 2026 while checking the dialogs in WebKit: icon-192.png and
  icon-512.png were SVG text with a .png name, a green "CQ" placeholder from
  the Communities Qualifier days. Browsers could not decode them, so Android
  had no install icon and the manifest still said "Communities Qualifier".
  The dashboard's iPhone icon was the white, transparent globe, which iOS
  shows white on black.

  This reads the files' bytes, not their names: every icon the manifest or a
  page names exists, is a PNG, is the size it claims, and the iPhone one is
  opaque.
*/
import fs from 'fs';

let failures = 0;
const ok = (c, m) => { console.log((c ? '  ok   ' : '  FAIL ') + m); if (!c) failures++; };
const STATIC = new URL('../static/', import.meta.url);

// width, height and colour type from the PNG header (IHDR); null if not a PNG
function png(rel) {
  const file = new URL(rel.replace(/^\/static\//, ''), STATIC);
  if (!fs.existsSync(file)) return null;
  const b = fs.readFileSync(file);
  const sig = [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a];
  if (b.length < 26 || !sig.every((v, i) => b[i] === v) || b.toString('ascii', 12, 16) !== 'IHDR') return null;
  return { w: b.readUInt32BE(16), h: b.readUInt32BE(20), colourType: b[25] };
}

console.log('\nThe manifest');
const manifest = JSON.parse(fs.readFileSync(new URL('manifest.json', STATIC), 'utf8'));
ok(manifest.name === 'Atlas Excellence', `it is called Atlas Excellence (${manifest.name})`);
for (const icon of manifest.icons) {
  const p = png(icon.src);
  const [w, h] = icon.sizes.split('x').map(Number);
  ok(!!p, `${icon.src} is a real PNG`);
  ok(p && p.w === w && p.h === h, `${icon.src} is ${icon.sizes} as it says (${p ? p.w + 'x' + p.h : 'unreadable'})`);
}
const purposes = manifest.icons.flatMap(i => (i.purpose || 'any').split(/\s+/));
ok(purposes.includes('any') && purposes.includes('maskable'), 'there is an ordinary icon and a maskable one');
ok(!manifest.icons.some(i => /\bany\b/.test(i.purpose || '') && /\bmaskable\b/.test(i.purpose || '')),
   'no icon is both: a logo sized for "any" gets its edges cut off when Android masks it');
ok(manifest.icons.some(i => (i.purpose || 'any').includes('any') && i.sizes === '512x512'), 'a 512px icon for the install screen');

console.log('\nThe iPhone icon on every page');
const pages = fs.readdirSync(new URL('../templates/', import.meta.url)).filter(f => f.endsWith('.html'));
const touch = new Set();
for (const f of pages) {
  const html = fs.readFileSync(new URL(`../templates/${f}`, import.meta.url), 'utf8');
  for (const m of html.matchAll(/<link rel="apple-touch-icon" href="([^"]+)"/g)) touch.add(`${m[1]}|${f}`);
}
ok(touch.size >= 5, `the pages name one (${touch.size})`);
for (const entry of touch) {
  const [href, page] = entry.split('|');
  const p = png(href);
  ok(p && p.w === 180 && p.h === 180, `${page}: ${href} is a 180x180 PNG`);
  // Colour types 4 and 6 carry alpha; iOS fills see-through pixels with black.
  ok(p && p.colourType !== 4 && p.colourType !== 6, `${page}: and opaque`);
}

console.log(failures ? `\n${failures} failed` : '\nThe app has its own icon.');
process.exit(failures ? 1 : 0);
