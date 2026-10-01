// Resolución de valores responsive {base, tablet?, mobile?} — cascada
// "desktop-first": base es el valor por defecto, tablet/mobile son
// overrides opcionales para pantallas más estrechas, con fallback hacia
// arriba si un nivel intermedio no está definido (mismo espíritu que el
// fallback a `ca` del patrón de idiomas {ca,es,en}).
//
// Los breakpoints en px se definen aquí una sola vez — los usa tanto este
// helper (fallback en JS, para casos sin CSS, ninguno por ahora) como
// responsiveStyle.js (media queries reales para el HTML servidor). Alineados
// con los breakpoints por defecto de Tailwind (sm/lg) que ya usa el resto
// del proyecto, no un valor inventado aparte.
export const BREAKPOINT_MAX_WIDTH = {
  tablet: 1024,
  mobile: 640,
};

const FALLBACK_CHAIN = {
  base: ['base'],
  tablet: ['tablet', 'base'],
  mobile: ['mobile', 'tablet', 'base'],
};

export function resolveResponsive(value, breakpoint = 'base') {
  if (value == null || typeof value !== 'object') return value;
  for (const key of FALLBACK_CHAIN[breakpoint] ?? ['base']) {
    if (value[key] !== undefined) return value[key];
  }
  return undefined;
}
