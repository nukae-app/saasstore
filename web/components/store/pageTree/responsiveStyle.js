// Genera CSS real con media queries para props responsive — la pieza que
// faltaba del spike de Fase 0 (docs/ARQUITECTURA_DISENY_FIGMA.md, checkpoint
// de breakpoints): allí "cambiar de breakpoint" era una rama JS sobre un
// ancho simulado; aquí es un único HTML servido que se adapta solo, vía
// `<style>` + `@media`, sin JS ni Craft.js en el storefront público.
//
// No se puede repartir esto entre un `style` inline (para "base") y un
// `<style>` con media queries (para los overrides): un atributo `style`
// inline gana SIEMPRE a una regla de hoja de estilos, sin importar la media
// query — así que un prop responsive va TODO por aquí, `base` incluido,
// nunca por `style` inline.
import { BREAKPOINT_MAX_WIDTH } from './breakpoints';

// Cada prop responsive que un tipo de nodo declare debe tener un handler
// aquí: recibe el valor "en crudo" del nivel de la cascada (base/tablet/
// mobile) y devuelve las declaraciones CSS correspondientes.
const PROPERTY_HANDLERS = {
  direction: (v) => ({ 'flex-direction': v }),
  gap: (v) => ({ gap: `${v}px` }),
  columns: (v) => ({ 'grid-template-columns': `repeat(${v}, minmax(0, 1fr))` }),
  align: (v) => ({ 'align-items': v }),
  justify: (v) => ({ 'justify-content': v }),
  height: (v) => ({ height: `${v}px` }),
};

// Los ids vienen del propio editor (Craft.js), pero esto sirve para
// render público — nunca confiar en que solo contengan caracteres seguros
// para un selector de atributo CSS.
function safeSelectorId(nodeId) {
  return String(nodeId).replace(/[^a-zA-Z0-9_-]/g, '');
}

function declsToCss(decls) {
  return Object.entries(decls)
    .map(([prop, value]) => `${prop}:${value}`)
    .join(';');
}

/**
 * @param nodeId id del nodo (para el selector de atributo `[data-node-id]`)
 * @param responsiveProps ej. { direction: {base:'column',mobile:'row'}, gap: {base:12} }
 * @returns string CSS (vacío si ningún prop tiene forma responsive) para
 *          meter en un <style> junto al nodo.
 */
export function buildResponsiveCss(nodeId, responsiveProps) {
  const selector = `[data-node-id="${safeSelectorId(nodeId)}"]`;
  const base = {};
  const tablet = {};
  const mobile = {};

  for (const [propKey, value] of Object.entries(responsiveProps)) {
    const handler = PROPERTY_HANDLERS[propKey];
    if (!handler || value == null || typeof value !== 'object') continue;
    if (value.base !== undefined) Object.assign(base, handler(value.base));
    if (value.tablet !== undefined) Object.assign(tablet, handler(value.tablet));
    if (value.mobile !== undefined) Object.assign(mobile, handler(value.mobile));
  }

  const rules = [];
  if (Object.keys(base).length) rules.push(`${selector}{${declsToCss(base)}}`);
  if (Object.keys(tablet).length) {
    rules.push(`@media (max-width:${BREAKPOINT_MAX_WIDTH.tablet}px){${selector}{${declsToCss(tablet)}}}`);
  }
  // mobile SIEMPRE después de tablet en el CSS final: a un ancho de móvil
  // también matchea la media query de tablet, así que el orden de aparición
  // decide qué regla gana (misma especificidad) — debe ganar mobile.
  if (Object.keys(mobile).length) {
    rules.push(`@media (max-width:${BREAKPOINT_MAX_WIDTH.mobile}px){${selector}{${declsToCss(mobile)}}}`);
  }
  return rules.join('');
}
