'use client';

import { useNode } from '@craftjs/core';
import { resolveLocale } from '../../../store/pageTree/locale';
import StyleSettings from '../StyleFields';

const LOCALES = ['ca', 'es', 'en'];
const DEFAULT_STYLE = {
  display: 'inline-block',
  padding: '10px 20px',
  borderRadius: '8px',
  background: '#18181b',
  color: '#ffffff',
  fontSize: '14px',
  fontWeight: 600,
};

export default function Button({ text, href, style }) {
  const { connectors: { connect, drag }, id, selected } = useNode((node) => ({ selected: node.events.selected }));
  const label = resolveLocale(text, 'ca') || '(botó sense text)';
  return (
    <a
      ref={(ref) => connect(drag(ref))}
      data-node-id={id}
      href="#"
      onClick={(e) => e.preventDefault()}
      style={{ ...DEFAULT_STYLE, outline: selected ? '2px solid #6366f1' : '1px dashed transparent', outlineOffset: -1, ...style }}
    >
      {label}
    </a>
  );
}

Button.craft = {
  displayName: 'Button',
  props: { text: { ca: '', es: '', en: '' }, href: '', style: {} },
  related: { settings: ButtonSettings },
};

function ButtonSettings() {
  const { text, href, actions: { setProp } } = useNode((node) => ({ text: node.data.props.text || {}, href: node.data.props.href }));
  return (
    <div>
      {LOCALES.map((loc) => (
        <div key={loc} style={{ marginBottom: 8 }}>
          <label style={{ fontSize: 11, color: '#666', display: 'block', marginBottom: 2 }}>Text ({loc})</label>
          <input
            value={text[loc] || ''}
            onChange={(e) => setProp((props) => { props.text = { ...props.text, [loc]: e.target.value }; })}
            style={{ width: '100%', fontSize: 12, padding: '4px 6px', border: '1px solid #ccc', borderRadius: 6 }}
          />
        </div>
      ))}
      <div style={{ marginBottom: 8 }}>
        <label style={{ fontSize: 11, color: '#666', display: 'block', marginBottom: 2 }}>Enllaç (URL o ruta)</label>
        <input
          value={href || ''}
          onChange={(e) => setProp((props) => { props.href = e.target.value; })}
          placeholder="/cataleg o https://..."
          style={{ width: '100%', fontSize: 12, padding: '4px 6px', border: '1px solid #ccc', borderRadius: 6 }}
        />
      </div>
      <StyleSettings />
    </div>
  );
}
