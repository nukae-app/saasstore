// Resuelve un campo de texto {ca,es,en} al idioma activo, con fallback a
// catalán — mismo patrón acordado en docs/PLAN_MULTIIDIOMA_CONTINGUT.md,
// aplicado desde el origen en el árbol de nodos nuevo (a diferencia de
// `HomeBlock.props`, que todavía guarda un string plano por campo).
export function resolveLocale(value, locale = 'ca') {
  if (value == null) return '';
  if (typeof value === 'string') return value; // compat: algún nodo simple sin variantes
  return value[locale] || value.ca || '';
}
