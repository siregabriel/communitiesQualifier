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
ok(/flex-direction:\s*column/.test(rule('.ail')), 'the list is one column, always');
ok(!/grid-template-columns/.test(rule('.ail')), 'never a grid, at any width');
ok(px(rule('.ail-thumb'), 'width') <= 56, 'the photo is a thumbnail, not a banner');
const wide = css.slice(css.indexOf('@media (min-width: 900px)', css.indexOf('Action Items, as a queue')));
ok(/max-width:\s*900px/.test(wide), 'on a monitor the line is capped rather than stretched');
ok(!/grid/.test(wide.slice(0, 400)), 'and a wide screen still gets a list, not columns');
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
