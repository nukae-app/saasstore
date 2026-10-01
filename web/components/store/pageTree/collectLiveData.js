// Recorre el árbol para saber, ANTES de renderizar, qué datos en vivo hacen
// falta — mismo patrón que app/[locale]/page.jsx ya usa para HomeBlock
// (`etiquetaSlugs` + `releasesByEtiqueta`), extendido para funcionar sobre
// un árbol anidado en vez de una lista plana.
const HOME_BLOCK_TYPES_WITH_ETIQUETA = new Set(['carousel', 'curator_selection']);

export function collectEtiquetaSlugs(node, acc = new Set()) {
  if (!node) return acc;
  if (node.type === 'ProductGrid' && node.props?.etiqueta_slug) {
    acc.add(node.props.etiqueta_slug);
  }
  if (node.type === 'HomeBlockNode' && HOME_BLOCK_TYPES_WITH_ETIQUETA.has(node.props?.block_type)) {
    const slug = node.props?.block_props?.etiqueta_slug;
    if (slug) acc.add(slug);
  }
  for (const child of node.children ?? []) collectEtiquetaSlugs(child, acc);
  return acc;
}

// `HomeBlockNode` necesita datos en vivo extra (config/recomanats/sonant,
// ver TreeRenderer.jsx) que el resto de nodos no piden — comprobar si hace
// falta pedirlos evita ese coste en páginas que no usan bloques legado.
export function treeHasHomeBlockNode(node) {
  if (!node) return false;
  if (node.type === 'HomeBlockNode') return true;
  return (node.children ?? []).some(treeHasHomeBlockNode);
}
