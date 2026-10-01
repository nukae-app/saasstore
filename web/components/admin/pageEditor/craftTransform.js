// Transformadores entre `Page.draft_tree` (nuestro formato portable,
// {id,type,props,style,children}, el que consume TreeRenderer.jsx en SSR)
// y el estado interno de Craft.js (`query.serialize()`/`actions.deserialize`).
//
// `treeToCraftState` es la mitad que el spike de Fase 0 no probó (cargar un
// árbol YA EXISTENTE al abrir el editor) — de-riesgada en una comprobación
// aparte con React/Craft.js reales en Node antes de escribir esto (ver
// checkpoint de bitácora en docs/ARQUITECTURA_DISENY_FIGMA.md, Fase 2).
// `craftStateToTree` reconstruye el criterio ya confirmado en el spike de
// Fase 0: usar `type.resolvedName`, nunca `displayName` (se minifica en
// build de producción).
import { isCanvasType } from './nodeTypes';

export const ROOT_ID = 'ROOT';

export function emptyRootTree() {
  return {
    id: ROOT_ID,
    type: 'Stack',
    props: { direction: { base: 'column' }, gap: { base: 16 } },
    style: {},
    children: [],
  };
}

let counter = 0;
export function newNodeId() {
  counter += 1;
  return `n${Date.now().toString(36)}${counter}`;
}

export function treeToCraftState(tree) {
  const nodes = {};
  function walk(node, parentId) {
    const canvas = isCanvasType(node.type);
    nodes[node.id] = {
      type: { resolvedName: node.type },
      isCanvas: canvas,
      props: { ...(node.props || {}), style: node.style || {} },
      displayName: node.type,
      custom: {},
      hidden: false,
      nodes: canvas ? (node.children || []).map((c) => c.id) : [],
      linkedNodes: {},
    };
    if (parentId) nodes[node.id].parent = parentId;
    (node.children || []).forEach((child) => walk(child, node.id));
  }
  walk(tree, null);
  return nodes;
}

export function craftStateToTree(serialized) {
  function build(id) {
    const n = serialized[id];
    const { style, ...props } = n.props || {};
    return {
      id,
      type: n.type.resolvedName,
      props,
      style: style || {},
      children: (n.nodes || []).map(build),
    };
  }
  return build(ROOT_ID);
}

// `draft_tree` de una `Page` recién creada es `{}` (default del backend,
// ver models/storefront.py::Page.draft_tree) — sin `id`/`type`, no se puede
// hidratar tal cual. Cualquier árbol real siempre tiene `id: "ROOT"` (ver
// test_pages.py), así que detectarlo es suficiente para distinguir los casos.
export function normalizeDraftTree(tree) {
  if (tree && tree.id === ROOT_ID) return tree;
  return emptyRootTree();
}
