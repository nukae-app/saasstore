// Registro de tipos de nodo del árbol constructible (ver
// docs/ARQUITECTURA_DISENY_FIGMA.md §3) — mismo espíritu que
// components/store/blocks/registry.js para HomeBlock, pero para nodos
// anidables. Los nombres coinciden a propósito con los que usará el editor
// real de Fase 2 (Craft.js, `resolvedName` del resolver — ver el spike en
// web/app/admin/spike-editor-poc/): así el árbol que produzca el editor se
// renderiza aquí sin capa de traducción de nombres.
import Stack from './nodes/Stack';
import TextNode from './nodes/TextNode';
import ImageNode from './nodes/ImageNode';
import ProductGrid from './nodes/ProductGrid';
import CatalogBrowse from './nodes/CatalogBrowse';
import Button from './nodes/Button';
import Spacer from './nodes/Spacer';
import HomeBlockNode from './nodes/HomeBlockNode';

export const NODE_REGISTRY = {
  Stack,
  TextNode,
  ImageNode,
  ProductGrid,
  CatalogBrowse,
  Button,
  Spacer,
  HomeBlockNode,
};
