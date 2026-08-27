/*
  Photos are shrunk in the browser before a visit is submitted.

  A visit carries one photo per standard, and a Standards visit has thirty-nine
  of them. A phone camera writes 3-5MB each, and the server accepts 16MB for the
  whole request — so four or five full-size photos are already too many. When
  the server closes the connection while the phone is still uploading, Safari
  says "Load failed", which is what a regional saw standing in a building on
  LTE with a visit she could not send.

  These run the real shrinkPhoto() out of the template against a stubbed canvas,
  so the decisions it makes are checked rather than the wording around them.
*/

import fs from 'fs';

const html = fs.readFileSync(new URL('../templates/reporte.html', import.meta.url), 'utf8');

let failures = 0;
const ok = (c, m) => { console.log((c ? '  ok   ' : '  FAIL ') + m); if (!c) failures++; };

/* Lift the function out and give it a world to run in: a fake decoder that
   reports the dimensions we ask for, and a canvas that "encodes" to a size
   proportional to the pixels drawn — enough to tell a real shrink from a
   no-op. */
function loadShrink({ encodedBytesPerPixel = 0.12, toBlobFails = false, decodeFails = false } = {}) {
  // Ends at the "async" that begins the next function, not at the word
  // "function" inside it — otherwise the slice trails a dangling keyword.
  const src = html.slice(html.indexOf('const PHOTO_MAX_EDGE'),
                         html.indexOf('async function onNotesPhotoChosen'));
  const drawn = [];
  const ctx = { drawImage: (_b, _x, _y, w, h) => drawn.push([w, h]) };
  const sandbox = {
    console: { warn() {}, error() {} },
    createImageBitmap: async (file) => {
      if (decodeFails) throw new Error('cannot decode');
      return { width: file.width, height: file.height, close() {} };
    },
    document: {
      createElement: () => ({
        width: 0, height: 0,
        getContext: () => ctx,
        toBlob(cb, type, q) {
          if (toBlobFails) return cb(null);
          const size = Math.round(this.width * this.height * encodedBytesPerPixel);
          cb({ size, type, quality: q });
        },
      }),
    },
    File: class {
      constructor(parts, name, opts) {
        this.size = parts[0].size;
        this.name = name;
        this.type = (opts || {}).type;
        this.shrunk = true;
      }
    },
  };
  const fn = new Function(...Object.keys(sandbox), src + '; return shrinkPhoto;');
  return { shrink: fn(...Object.values(sandbox)), drawn };
}

const photo = (mb, w, h, name = 'IMG_0421.HEIC', type = 'image/jpeg') =>
  ({ size: Math.round(mb * 1024 * 1024), width: w, height: h, name, type });

console.log('\nA phone photo is made sendable');
{
  const { shrink, drawn } = loadShrink();
  const out = await shrink(photo(4.2, 4032, 3024));
  ok(out.shrunk === true, 'a 4MB camera photo is re-encoded');
  ok(out.size < 700 * 1024, `and comes out far smaller (${Math.round(out.size / 1024)}KB)`);
  ok(drawn[0][0] === 1600, `redrawn to 1600px on the long edge (${drawn[0].join('x')})`);
  ok(drawn[0][1] === 1200, 'keeping its proportions');
  ok(/\.jpg$/.test(out.name), 'and saved as jpg, whatever the camera called it');
}

console.log('\nA whole visit now fits in one request');
{
  const { shrink } = loadShrink();
  let before = 0, after = 0;
  for (let i = 0; i < 10; i++) {
    const f = photo(4.2, 4032, 3024);
    before += f.size;
    after += (await shrink(f)).size;
  }
  ok(before > 16 * 1024 * 1024,
     `ten photos used to exceed the 16MB the server accepts (${Math.round(before / 1024 / 1024)}MB)`);
  ok(after < 16 * 1024 * 1024,
     `and now fit with room to spare (${Math.round(after / 1024 / 1024)}MB)`);
}

console.log('\nIt leaves alone what it should');
{
  const { shrink, drawn } = loadShrink();
  const small = photo(0.2, 800, 600);
  ok(await shrink(small) === small, 'a photo already small enough is untouched');
  ok(drawn.length === 0, 'nothing is redrawn, so no detail is lost re-encoding it');

  const notAnImage = { size: 5 * 1024 * 1024, name: 'notes.pdf', type: 'application/pdf' };
  ok(await shrink(notAnImage) === notAnImage, 'and a non-image is passed straight through');

  ok(await shrink(null) === null, 'nothing in, nothing out');
}

console.log('\nFailing to shrink never means failing to submit');
{
  const broken = loadShrink({ decodeFails: true });
  const f = photo(4.2, 4032, 3024);
  ok(await broken.shrink(f) === f, 'an image the browser cannot decode is sent as it is');

  const noBlob = loadShrink({ toBlobFails: true });
  ok(await noBlob.shrink(f) === f, 'and so is one the canvas cannot encode');

  // Some cameras already write better JPEGs than a canvas can.
  const worse = loadShrink({ encodedBytesPerPixel: 5 });
  const out = await worse.shrink(photo(1.6, 1600, 1200));
  ok(out.shrunk === undefined,
     'if the re-encode would come out bigger, the original is kept');
}

console.log('\nThe person is told what happened, and that their work is safe');
{
  ok(/Couldn't reach the server/.test(html),
     'a dropped connection is explained in plain words, not as "Load failed"');
  ok(/draft is saved on this phone, so nothing is lost/.test(html),
     'and the draft is confirmed safe, which is the thing they actually fear');
  ok(/response\.status === 413/.test(html),
     'too-large is caught on its own');
  ok(/too many photos at once/.test(html), 'and named as what it usually is');
}

console.log('\nA draft can be thrown away by the person who owns it');
{
  ok(/function discardDraft\(/.test(html), 'there is a way to discard one');
  ok(/onclick="discardDraft\(\)"/.test(html), 'reachable from the page');
  ok(/confirm\(/.test(html.slice(html.indexOf('async function discardDraft'))),
     'it asks first, because it cannot be undone');
  ok(/draftDelete\(dk\)/.test(html.slice(html.indexOf('async function discardDraft'))),
     'and actually clears the stored draft');
}

console.log(failures ? `\n${failures} failure(s)` : '\nA visit can be sent from a phone on mobile data.');
process.exit(failures ? 1 : 0);
