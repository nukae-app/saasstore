'use client';

// Versión craft-aware de components/store/pageTree/nodes/Stack.jsx — nunca
// se importan entre sí (el renderer SSR no puede cargar @craftjs/core, ver
// docs/ARQUITECTURA_DISENY_FIGMA.md §2), pero comparten el mismo cálculo de
// estilo (`buildResponsiveCss`) para que el canvas se vea igual que el
// storefront público.
import { useNode } from '@craftjs/core';
import { buildResponsiveCss } from '../../../store/pageTree/responsiveStyle';
import { useBreakpoint, readAtBreakpoint, writeAtBreakpoint, BREAKPOINTS } from '../BreakpointContext';
import StyleSettings from '../StyleFields';

export default function Stack({ children, direction, gap, align, justify, style }) {
  const { connectors: { connect, drag }, id, selected } = useNode((node) => ({ selected: node.events.selected }));
  const css = buildResponsiveCss(id, { direction, gap, align, justify });
  return (
    <div
      ref={(ref) => connect(drag(ref))}
      data-node-id={id}
      style={{
        display: 'flex',
        minHeight: 24,
        outline: selected ? '2px solid #6366f1' : '1px dashed transparent',
        outlineOffset: -1,
        ...style,
      }}
    >
      {css && <style dangerouslySetInnerHTML={{ __html: css }} />}
      {children}
      {!children || (Array.isArray(children) && children.length === 0) ? (
        <span style={{ fontSize: 11, color: '#999', padding: 4 }}>Secció buida — arrossega-hi un node</span>
      ) : null}
    </div>
  );
}

Stack.craft = {
  displayName: 'Stack',
  props: { direction: { base: 'row' }, gap: { base: 8 }, style: {} },
  related: { settings: StackSettings },
};

function ResponsiveNumberField({ label, value, onChange, min = 0, max = 200 }) {
  const { breakpoint } = useBreakpoint();
  const bpLabel = BREAKPOINTS.find((b) => b.key === breakpoint)?.label;
  const current = readAtBreakpoint(value, breakpoint);
  const hasOverride = breakpoint !== 'base' && value?.[breakpoint] !== undefined;
  return (
    <div style={{ marginBottom: 8 }}>
      <label style={{ fontSize: 11, color: '#666', display: 'block', marginBottom: 2 }}>
        {label} ({bpLabel})
      </label>
      <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
        <input
          type="number" min={min} max={max}
          value={current ?? ''}
          placeholder={String(readAtBreakpoint(value, 'base') ?? '')}
          onChange={(e) => onChange(writeAtBreakpoint(value, breakpoint, e.target.value === '' ? undefined : Number(e.target.value)))}
          style={{ width: 70, fontSize: 12, padding: '3px 6px', border: '1px solid #ccc', borderRadius: 6 }}
        />
        {hasOverride && (
          <button onClick={() => onChange(writeAtBreakpoint(value, breakpoint, undefined))} style={{ fontSize: 10, color: '#6366f1' }}>
            Treure override
          </button>
        )}
      </div>
    </div>
  );
}

function ResponsiveSelectField({ label, value, options, onChange }) {
  const { breakpoint } = useBreakpoint();
  const bpLabel = BREAKPOINTS.find((b) => b.key === breakpoint)?.label;
  const current = readAtBreakpoint(value, breakpoint);
  const hasOverride = breakpoint !== 'base' && value?.[breakpoint] !== undefined;
  return (
    <div style={{ marginBottom: 8 }}>
      <label style={{ fontSize: 11, color: '#666', display: 'block', marginBottom: 2 }}>
        {label} ({bpLabel})
      </label>
      <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
        <select
          value={current ?? ''}
          onChange={(e) => onChange(writeAtBreakpoint(value, breakpoint, e.target.value || undefined))}
          style={{ fontSize: 12, padding: '3px 6px', border: '1px solid #ccc', borderRadius: 6 }}
        >
          <option value="">(hereta de {readAtBreakpoint(value, 'base') ?? '—'})</option>
          {options.map((o) => {
            const [v, l] = Array.isArray(o) ? o : [o, o];
            return <option key={v} value={v}>{l}</option>;
          })}
        </select>
        {hasOverride && (
          <button onClick={() => onChange(writeAtBreakpoint(value, breakpoint, undefined))} style={{ fontSize: 10, color: '#6366f1' }}>
            Treure override
          </button>
        )}
      </div>
    </div>
  );
}

function StackSettings() {
  const { direction, gap, align, justify, actions: { setProp } } = useNode((node) => ({
    direction: node.data.props.direction,
    gap: node.data.props.gap,
    align: node.data.props.align,
    justify: node.data.props.justify,
  }));
  return (
    <div>
      <ResponsiveSelectField
        label="Direcció" value={direction} options={[['row', 'Fila'], ['column', 'Columna']]}
        onChange={(v) => setProp((props) => { props.direction = v; })}
      />
      <ResponsiveNumberField
        label="Espai (px)" value={gap}
        onChange={(v) => setProp((props) => { props.gap = v; })}
      />
      <ResponsiveSelectField
        label="Alineació"
        value={align}
        options={[['flex-start', 'Inici'], ['center', 'Centrat'], ['flex-end', 'Final'], ['stretch', 'Estirat']]}
        onChange={(v) => setProp((props) => { props.align = v; })}
      />
      <ResponsiveSelectField
        label="Distribució"
        value={justify}
        options={[['flex-start', 'Inici'], ['center', 'Centrat'], ['flex-end', 'Final'], ['space-between', 'Espai entre'], ['space-around', 'Espai al voltant']]}
        onChange={(v) => setProp((props) => { props.justify = v; })}
      />
      <StyleSettings />
    </div>
  );
}

export { ResponsiveNumberField, ResponsiveSelectField };
