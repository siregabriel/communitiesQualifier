/* Comprobación de la experiencia en el teléfono: alturas de toque y una sola
   columna. jsdom no calcula diseño, así que se lee la hoja de estilos. */
import fs from 'fs';
const css = fs.readFileSync(new URL('../static/theme.css', import.meta.url), 'utf8');
let bad = 0; const ok=(c,m)=>{console.log((c?'  ok   ':'  FAIL ')+m); if(!c)bad++;};
// Anchored to the start of a line, or ".ail-thumb" also matches
// ".ail-row.is-done .ail-thumb" and reads the wrong rule.
const rule = (sel) => {
  const m = new RegExp('^' + sel.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '\\s*\\{([^}]*)\\}', 'm').exec(css);
  return m ? m[1] : '';
};
const px = (r, prop) => Number((r.match(new RegExp(prop + ':\\s*(\\d+)px')) || [])[1]);

ok(px(rule('.ail-head'), 'min-height') >= 44, 'a group header is at least 44px — a real tap target');
ok(px(rule('.ail-line'), 'min-height') >= 44, 'and so is a row');
ok(/flex-direction:\s*column/.test(rule('.ail')), 'one column by default — the phone case');
ok(!/grid-template-columns/.test(rule('.ail')),
   'and the base rule never introduces columns, whatever the screen');
ok(px(rule('.ail-thumb'), 'width') <= 56, 'the photo is a thumbnail, not a banner');
const from = css.indexOf('Action Items, as a queue');
const mid = css.slice(css.indexOf('@media (min-width: 900px)', from), css.indexOf('@media (min-width: 1250px)', from));
ok(/max-width:\s*900px/.test(mid), 'a laptop caps the line rather than stretching it');

const wide = css.slice(css.indexOf('@media (min-width: 1250px)', from));
ok(/grid-template-columns:\s*repeat\(2/.test(wide),
   'a wide monitor gets two communities side by side, not half a page of nothing');
ok(/align-items:\s*start/.test(wide),
   'a short community stays short instead of stretching to match its neighbour');
ok(!/columns:\s*2|column-count/.test(wide),
   'built as a grid, not CSS columns — those re-balance and would shuffle the page when a row opens');
ok(Number((wide.match(/max-width:\s*(\d+)px/) || [])[1]) > 900,
   'and the cap is lifted to make room for the second column');
/* Y en escritorio: la lista no puede quedar dentro de la rejilla de tarjetas.
   Metida ahí ocupaba una sola columna de 320px con media pantalla vacía al
   lado — el componente estaba bien y la página no. */
{
  const tpl = fs.readFileSync(new URL('../templates/dashboard.html', import.meta.url), 'utf8');
  ok(/gallery\.classList\.add\('gallery-queue'\)/.test(tpl),
     'the view turns the card grid off for itself');
  ok(/classList\.remove\('gallery-queue'\)/.test(tpl),
     'and turns it back on when you leave, or every other view loses its grid');
  ok(/\.gallery\.gallery-queue\s*\{[^}]*display:\s*block/.test(css),
     'the queue is a block, not one column of the card grid');
}

console.log(bad ? `\n${bad} fallo(s)` : '\nThe queue works on a phone and on a monitor.');
process.exit(bad ? 1 : 0);
