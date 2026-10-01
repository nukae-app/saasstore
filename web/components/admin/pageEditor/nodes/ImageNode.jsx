'use client';

import { useNode } from '@craftjs/core';
import { resolveLocale } from '../../../store/pageTree/locale';
import StyleSettings from '../StyleFields';

const LOCALES = ['ca', 'es', 'en'];

export default function ImageNode({ src, alt, style }) {
  const { connectors: { connect, drag }, id, selected } = useNode((node) => ({ selected: node.events.selected }));
  return (
    <div
      ref={(ref) => connect(drag(ref))}
      data-node-id={id}
      style={{ outline: selected ? '2px solid #6366f1' : '1px dashed transparent', outlineOffset: -1, minHeight: 40 }}
    >
      {src ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={src} alt={resolveLocale(alt, 'ca')} style={{ maxWidth: '100%', height: 'auto', display: 'block', ...style }} />
      ) : (
        <div style={{ padding: 16, fontSize: 11, color: '#999', background: '#f5f5f5', textAlign: 'center' }}>
          Imatge sense URL — configura-la al panell
        </div>
      )}
    </div>
  );
}

ImageNode.craft = {
  displayName: 'ImageNode',
  props: { src: '', alt: { ca: '', es: '', en: '' }, style: {} },
  related: { settings: ImageNodeSettings },
};

function ImageNodeSettings() {
  const { src, alt, actions: { setProp } } = useNode((node) => ({ src: node.data.props.src, alt: node.data.props.alt || {} }));
  return (
    <div>
      <div style={{ marginBottom: 8 }}>
        <label style={{ fontSize: 11, color: '#666', display: 'block', marginBottom: 2 }}>URL de la imatge</label>
        <input
          value={src || ''}
          onChange={(e) => setProp((props) => { props.src = e.target.value; })}
          placeholder="https://..."
          style={{ width: '100%', fontSize: 12, padding: '4px 6px', border: '1px solid #ccc', borderRadius: 6 }}
        />
      </div>
      {LOCALES.map((loc) => (
        <div key={loc} style={{ marginBottom: 8 }}>
          <label style={{ fontSize: 11, color: '#666', display: 'block', marginBottom: 2 }}>Alt ({loc})</label>
          <input
            value={alt[loc] || ''}
            onChange={(e) => setProp((props) => { props.alt = { ...props.alt, [loc]: e.target.value }; })}
            style={{ width: '100%', fontSize: 12, padding: '4px 6px', border: '1px solid #ccc', borderRadius: 6 }}
          />
        </div>
      ))}
      <StyleSettings />
    </div>
  );
}
