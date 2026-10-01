import { buildResponsiveCss } from '../responsiveStyle';

// Contenedor flex genérico — equivalente de producción del `Stack` probado
// en el spike de Fase 0 (web/app/admin/spike-editor-poc/). `direction`/`gap`
// son responsive ({base,tablet?,mobile?}), resueltos aquí vía CSS real
// (ver responsiveStyle.js), no vía rama JS como en el spike.
export default function Stack({ node, children }) {
  const { id, props = {}, style = {} } = node;
  const css = buildResponsiveCss(id, { direction: props.direction, gap: props.gap, align: props.align, justify: props.justify });
  return (
    <div data-node-id={id} style={{ display: 'flex', ...style }}>
      {css && <style dangerouslySetInnerHTML={{ __html: css }} />}
      {children}
    </div>
  );
}
