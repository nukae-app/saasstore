'use client';

// A diferencia de components/store/pageTree/nodes/ProductGrid.jsx (que
// resuelve el catálogo real en SSR), el canvas del editor NUNCA carga
// catálogo en vivo (regla de oro, §2 del documento) — se muestra un
// placeholder con el `etiqueta_slug` configurado, el catálogo real solo se
// ve en el storefront público tras publicar.
import { useNode } from '@craftjs/core';
import { ResponsiveNumberField } from './Stack';
import StyleSettings from '../StyleFields';

export default function ProductGrid({ etiqueta_slug, columns, style }) {
  const { connectors: { connect, drag }, id, selected } = useNode((node) => ({ selected: node.events.selected }));
  return (
    <div
      ref={(ref) => connect(drag(ref))}
      data-node-id={id}
      style={{
        outline: selected ? '2px solid #6366f1' : '1px dashed #ccc',
        outlineOffset: -1,
        padding: 16,
        background: '#fafafa',
        fontSize: 12,
        color: '#666',
        textAlign: 'center',
        ...style,
      }}
    >
      Graella de productes — etiqueta: <strong>{etiqueta_slug || '(sense configurar)'}</strong>
      <br />({(columns && columns.base) || 4} columnes a desktop — catàleg real només al lloc públic)
    </div>
  );
}

ProductGrid.craft = {
  displayName: 'ProductGrid',
  props: { etiqueta_slug: '', columns: { base: 4 } },
  related: { settings: ProductGridSettings },
};

function ProductGridSettings() {
  const { etiqueta_slug, columns, actions: { setProp } } = useNode((node) => ({
    etiqueta_slug: node.data.props.etiqueta_slug,
    columns: node.data.props.columns,
  }));
  return (
    <div>
      <div style={{ marginBottom: 8 }}>
        <label style={{ fontSize: 11, color: '#666', display: 'block', marginBottom: 2 }}>Etiqueta del catàleg</label>
        <input
          value={etiqueta_slug || ''}
          onChange={(e) => setProp((props) => { props.etiqueta_slug = e.target.value; })}
          placeholder="novetats"
          style={{ width: '100%', fontSize: 12, padding: '4px 6px', border: '1px solid #ccc', borderRadius: 6 }}
        />
      </div>
      <ResponsiveNumberField
        label="Columnes" value={columns} min={1} max={6}
        onChange={(v) => setProp((props) => { props.columns = v; })}
      />
      <StyleSettings />
    </div>
  );
}
