// Vocabulario de tipos de nodo del árbol constructible (ver
// docs/ARQUITECTURA_DISENY_FIGMA.md §3) — comparte nombre con
// `components/store/pageTree/registry.js` (SSR, sin Craft.js) a propósito:
// mismo `type` string en el árbol, dos implementaciones (una para editar,
// otra para servir), nunca una capa de traducción de nombres entre ambas.
//
// `canvas: true` es lo único que decide si un tipo puede tener `children`
// en Craft.js (`isCanvas`, ver craftTransform.js) — hoy solo `Stack`. Los
// nodos protegidos de checkout (§3d) no viven aquí todavía: siguen sin
// construirse, ver docs/CONTINUAR_DISENY_FIGMA.md.
export const NODE_TYPES = {
  Stack: { canvas: true },
  TextNode: { canvas: false },
  ImageNode: { canvas: false },
  ProductGrid: { canvas: false },
  CatalogBrowse: { canvas: false },
  Button: { canvas: false },
  Spacer: { canvas: false },
  HomeBlockNode: { canvas: false },
};

export function isCanvasType(type) {
  return Boolean(NODE_TYPES[type]?.canvas);
}
