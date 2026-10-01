'use client';

import { useNode } from '@craftjs/core';
import { resolveLocale } from '../../../store/pageTree/locale';
import StyleSettings from '../StyleFields';

const LOCALES = ['ca', 'es', 'en'];

export default function TextNode({ text, style }) {
  const { connectors: { connect, drag }, id, selected } = useNode((node) => ({ selected: node.events.selected }));
  const value = resolveLocale(text, 'ca');
  return (
    <p
      ref={(ref) => connect(drag(ref))}
      data-node-id={id}
      style={{ outline: selected ? '2px solid #6366f1' : '1px dashed transparent', outlineOffset: -1, minHeight: '1em', ...style }}
    >
      {value || <span style={{ color: '#bbb' }}>(text buit)</span>}
    </p>
  );
}

TextNode.craft = {
  displayName: 'TextNode',
  props: { text: { ca: '', es: '', en: '' }, style: {} },
  related: { settings: TextNodeSettings },
};

function TextNodeSettings() {
  const { text, actions: { setProp } } = useNode((node) => ({ text: node.data.props.text || {} }));
  return (
    <div>
      {LOCALES.map((loc) => (
        <div key={loc} style={{ marginBottom: 8 }}>
          <label style={{ fontSize: 11, color: '#666', display: 'block', marginBottom: 2 }}>Text ({loc})</label>
          <textarea
            rows={2}
            value={text[loc] || ''}
            onChange={(e) => setProp((props) => { props.text = { ...props.text, [loc]: e.target.value }; })}
            style={{ width: '100%', fontSize: 12, padding: '4px 6px', border: '1px solid #ccc', borderRadius: 6 }}
          />
        </div>
      ))}
      <StyleSettings />
    </div>
  );
}
