'use client';

import { useNode } from '@craftjs/core';
import { buildResponsiveCss } from '../../../store/pageTree/responsiveStyle';
import { ResponsiveNumberField } from './Stack';

export default function Spacer({ height }) {
  const { connectors: { connect, drag }, id, selected } = useNode((node) => ({ selected: node.events.selected }));
  const css = buildResponsiveCss(id, { height });
  return (
    <div
      ref={(ref) => connect(drag(ref))}
      data-node-id={id}
      style={{
        height: height?.base ?? 24,
        outline: selected ? '2px solid #6366f1' : '1px dashed #ddd',
        outlineOffset: -1,
      }}
    >
      {css && <style dangerouslySetInnerHTML={{ __html: css }} />}
    </div>
  );
}

Spacer.craft = {
  displayName: 'Spacer',
  props: { height: { base: 24 } },
  related: { settings: SpacerSettings },
};

function SpacerSettings() {
  const { height, actions: { setProp } } = useNode((node) => ({ height: node.data.props.height }));
  return (
    <ResponsiveNumberField
      label="Alçada (px)" value={height} min={0} max={400}
      onChange={(v) => setProp((props) => { props.height = v; })}
    />
  );
}
