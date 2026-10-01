import { buildResponsiveCss } from '../responsiveStyle';

// Div vacío de altura configurable — separación vertical explícita cuando
// el `gap` de un Stack padre no basta (p. ej. dos Stacks hermanos sin
// contenedor común). `height` es responsive como `gap`/`columns`.
export default function Spacer({ node }) {
  const { id, props = {} } = node;
  const css = buildResponsiveCss(id, { height: props.height });
  return (
    <div data-node-id={id} style={{ height: props.height?.base ?? 24 }}>
      {css && <style dangerouslySetInnerHTML={{ __html: css }} />}
    </div>
  );
}
