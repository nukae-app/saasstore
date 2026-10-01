'use client';

// Sección de estilo genérica (fondo, padding, borde, color de texto) —
// compartida por los 4 tipos de nodo, porque todos aceptan `style` tal
// cual (mismo objeto CSS-in-JS que consume el renderer SSR, ver
// pageTree/nodes/*.jsx). No es responsive: `style` siempre va por el
// nivel "base" del canvas, igual que hoy en el árbol — los overrides por
// breakpoint solo existen para las props estructurales (direction/gap/
// columns), no para `style`.
import { useNode } from '@craftjs/core';

function StyleField({ label, value, onChange, type = 'text', placeholder }) {
  return (
    <div style={{ marginBottom: 8, display: 'flex', alignItems: 'center', gap: 8 }}>
      <label style={{ fontSize: 11, color: '#666', width: 80, flexShrink: 0 }}>{label}</label>
      <input
        type={type}
        value={value ?? (type === 'color' ? '#ffffff' : '')}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
        style={{ flex: 1, fontSize: 12, padding: type === 'color' ? '0' : '3px 6px', border: '1px solid #ccc', borderRadius: 6, height: type === 'color' ? 26 : 'auto' }}
      />
    </div>
  );
}

function StyleSelectField({ label, value, options, onChange }) {
  return (
    <div style={{ marginBottom: 8, display: 'flex', alignItems: 'center', gap: 8 }}>
      <label style={{ fontSize: 11, color: '#666', width: 80, flexShrink: 0 }}>{label}</label>
      <select
        value={value ?? ''}
        onChange={(e) => onChange(e.target.value)}
        style={{ flex: 1, fontSize: 12, padding: '3px 6px', border: '1px solid #ccc', borderRadius: 6 }}
      >
        <option value="">(per defecte)</option>
        {options.map(([v, label2]) => <option key={v} value={v}>{label2}</option>)}
      </select>
    </div>
  );
}

export default function StyleSettings() {
  const { style, actions: { setProp } } = useNode((node) => ({ style: node.data.props.style || {} }));

  function set(key, value) {
    setProp((props) => {
      props.style = { ...(props.style || {}) };
      if (value === '' || value == null) delete props.style[key];
      else props.style[key] = value;
    });
  }

  // La imatge de fons sempre va acompanyada de cover/center/no-repeat — mai
  // té sentit una imatge de fons repetida en mosaic en aquest editor, així
  // que no s'exposen com a camps separats (menys controls, mateix criteri
  // que "no exposar el que mai fa falta triar").
  function setBackgroundImage(url) {
    setProp((props) => {
      props.style = { ...(props.style || {}) };
      if (!url) {
        delete props.style.backgroundImage;
        delete props.style.backgroundSize;
        delete props.style.backgroundPosition;
        delete props.style.backgroundRepeat;
      } else {
        props.style.backgroundImage = `url('${url}')`;
        props.style.backgroundSize = 'cover';
        props.style.backgroundPosition = 'center';
        props.style.backgroundRepeat = 'no-repeat';
      }
    });
  }

  const padding = style.padding ? String(style.padding).replace('px', '') : '';
  const borderRadius = style.borderRadius ? String(style.borderRadius).replace('px', '') : '';
  const fontSize = style.fontSize ? String(style.fontSize).replace('px', '') : '';
  const lineHeight = style.lineHeight ?? '';

  return (
    <div style={{ marginTop: 8, paddingTop: 8, borderTop: '1px solid #eee' }}>
      <p style={{ fontSize: 11, fontWeight: 600, color: '#666', marginBottom: 6 }}>Estil</p>
      <StyleField label="Fons" type="color" value={/^#/.test(style.background) ? style.background : undefined}
        onChange={(v) => set('background', v)} />
      <StyleField label="Imatge de fons" type="text" value={style.backgroundImage ? style.backgroundImage.replace(/^url\(['"]?/, '').replace(/['"]?\)$/, '') : ''}
        placeholder="https://..."
        onChange={setBackgroundImage} />
      {style.backgroundImage && (
        <p style={{ marginLeft: 88, marginTop: -4, marginBottom: 8, fontSize: 10, color: '#999' }}>cobreix la secció, centrada</p>
      )}
      <StyleField label="Padding (px)" type="number" value={padding}
        onChange={(v) => set('padding', v === '' ? '' : `${v}px`)} />
      <StyleField label="Vora (radi px)" type="number" value={borderRadius}
        onChange={(v) => set('borderRadius', v === '' ? '' : `${v}px`)} />

      <p style={{ fontSize: 11, fontWeight: 600, color: '#666', margin: '10px 0 6px' }}>Tipografia</p>
      <StyleField label="Color text" type="color" value={/^#/.test(style.color) ? style.color : undefined}
        onChange={(v) => set('color', v)} />
      <StyleField label="Mida (px)" type="number" value={fontSize}
        onChange={(v) => set('fontSize', v === '' ? '' : `${v}px`)} />
      <StyleSelectField label="Pes" value={style.fontWeight}
        options={[['400', 'Normal'], ['500', 'Mitjà'], ['600', 'Semi-negreta'], ['700', 'Negreta'], ['800', 'Extra-negreta']]}
        onChange={(v) => set('fontWeight', v)} />
      <StyleSelectField label="Alineació" value={style.textAlign}
        options={[['left', 'Esquerra'], ['center', 'Centre'], ['right', 'Dreta'], ['justify', 'Justificat']]}
        onChange={(v) => set('textAlign', v)} />
      <StyleField label="Interlineat" type="number" value={lineHeight}
        placeholder="1.4" onChange={(v) => set('lineHeight', v)} />
    </div>
  );
}
