'use client';

// Arrastrar un tipo desde aquí al canvas — mecanismo oficial de Craft.js
// (`connectors.create`), mismo patrón ya probado en el spike de Fase 0 para
// el botón "+ Secció" (ahí solo existía para `Stack`; aquí se generaliza a
// todos los tipos del registro).
import { Element, useEditor } from '@craftjs/core';
import Stack from './nodes/Stack';
import TextNode from './nodes/TextNode';
import ImageNode from './nodes/ImageNode';
import ProductGrid from './nodes/ProductGrid';
import CatalogBrowse from './nodes/CatalogBrowse';
import Button from './nodes/Button';
import Spacer from './nodes/Spacer';
import HomeBlockNode from './nodes/HomeBlockNode';

const PRIMITIVE_ITEMS = [
  { type: 'Stack', label: '+ Secció', make: () => <Element canvas is={Stack} direction={{ base: 'column' }} gap={{ base: 8 }} /> },
  { type: 'TextNode', label: '+ Text', make: () => <TextNode /> },
  { type: 'ImageNode', label: '+ Imatge', make: () => <ImageNode /> },
  { type: 'Button', label: '+ Botó', make: () => <Button /> },
  { type: 'Spacer', label: '+ Separador', make: () => <Spacer /> },
  { type: 'ProductGrid', label: '+ Graella de productes', make: () => <ProductGrid /> },
  { type: 'CatalogBrowse', label: '+ Catàleg amb filtres', make: () => <CatalogBrowse /> },
];

// Blocs llegat: reutilitzen els components reals de HomeBlock (ver
// pageTree/nodes/HomeBlockNode.jsx) — mateix disseny visual que ja
// coneixes de `disseny-web`, ara col·locables dins de qualsevol pàgina.
// Cada entrada porta uns `block_props` per defecte raonables (mateixos
// defaults que api/app/blocks/registry.py).
const HOME_BLOCK_ITEMS = [
  { type: 'hero', label: '+ Hero', block_props: { layout: 'image_right', title: '', cta_href: '/cataleg', text_align: 'center', illustration_size: 'medium' } },
  { type: 'carousel', label: '+ Carrusel', block_props: { layout: 'classic', heading: '', etiqueta_slug: 'novetat' } },
  { type: 'curator_selection', label: '+ Selecció del curador', block_props: { etiqueta_slug: 'recomanat' } },
  { type: 'genre_grid', label: '+ Graella de gèneres', block_props: {} },
  { type: 'spotify_recommendations', label: '+ Recomanacions Spotify', block_props: {} },
  { type: 'about_strip', label: '+ Franja "sobre nosaltres"', block_props: {} },
].map((item) => ({
  type: `home:${item.type}`,
  label: item.label,
  make: () => <HomeBlockNode block_type={item.type} block_props={item.block_props} />,
}));

// Clic, com a alternativa a arrossegar: afegeix al canvas seleccionat si
// n'hi ha un (i és un contenidor), o al node pare més proper que ho sigui,
// o a ROOT si no hi ha res seleccionat.
function addByClick(query, actions, item) {
  const selectedId = query.getEvent('selected').last();
  let targetId = 'ROOT';
  if (selectedId) {
    let node = query.node(selectedId).get();
    if (node.data.isCanvas) {
      targetId = selectedId;
    } else if (node.data.parent) {
      targetId = node.data.parent;
    }
  }
  const tree = query.parseReactElement(item.make()).toNodeTree();
  actions.addNodeTree(tree, targetId);
}

function ToolboxGroup({ title, items, connectors, query, actions }) {
  return (
    <div className="flex flex-col gap-2">
      <p className="text-[10px] font-semibold uppercase tracking-wide text-secondary-foreground mt-2">{title}</p>
      {items.map((item) => (
        <button
          key={item.type}
          ref={(ref) => ref && connectors.create(ref, item.make())}
          onClick={() => addByClick(query, actions, item)}
          className="text-left text-sm px-3 py-2 rounded-xl border border-outline-variant hover:border-primary hover:bg-surface-container-high transition-colors cursor-grab active:cursor-grabbing"
        >
          {item.label}
        </button>
      ))}
    </div>
  );
}

export default function Toolbox() {
  const { connectors, actions, query } = useEditor();
  return (
    <div className="flex flex-col gap-2">
      <ToolboxGroup title="Elements" items={PRIMITIVE_ITEMS} connectors={connectors} query={query} actions={actions} />
      <ToolboxGroup title="Blocs (llegat)" items={HOME_BLOCK_ITEMS} connectors={connectors} query={query} actions={actions} />
      <p className="text-[11px] text-secondary-foreground mt-1">Arrossega cap al canvas, o fes clic per afegir-lo al node seleccionat.</p>
    </div>
  );
}
