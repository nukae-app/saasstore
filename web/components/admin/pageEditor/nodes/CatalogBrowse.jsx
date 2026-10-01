'use client';

// Versión craft-aware de components/store/pageTree/nodes/CatalogBrowse.jsx
// — el canvas del editor NUNCA carga catálogo/filtros en vivo (regla de oro
// §2), igual que ProductGrid: solo un placeholder. El catálogo real (con
// filtros funcionando) solo se ve tras publicar, en el storefront público.
import { useNode } from '@craftjs/core';
import StyleSettings from '../StyleFields';

export default function CatalogBrowse({ style }) {
  const { connectors: { connect, drag }, id, selected } = useNode((node) => ({ selected: node.events.selected }));
  return (
    <div
      ref={(ref) => connect(drag(ref))}
      data-node-id={id}
      style={{
        outline: selected ? '2px solid #6366f1' : '1px dashed #ccc',
        outlineOffset: -1,
        padding: 24,
        background: '#fafafa',
        fontSize: 12,
        color: '#666',
        textAlign: 'center',
        ...style,
      }}
    >
      Catàleg amb filtres — vista prèvia no disponible a l&apos;editor
      <br />(cerca, filtres i graella reals només al lloc públic)
    </div>
  );
}

CatalogBrowse.craft = {
  displayName: 'CatalogBrowse',
  props: { style: {} },
  related: { settings: CatalogBrowseSettings },
};

function CatalogBrowseSettings() {
  return (
    <div>
      <p style={{ fontSize: 11, color: '#666' }}>
        Aquest node no té propietats pròpies — la cerca i els filtres sempre són els reals del catàleg.
      </p>
      <StyleSettings />
    </div>
  );
}
