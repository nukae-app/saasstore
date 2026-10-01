import ReleaseCard from '../../ReleaseCard';
import { buildResponsiveCss } from '../responsiveStyle';

// Nodo "vivo" (docs/ARQUITECTURA_DISENY_FIGMA.md §2, regla de oro): sus
// props (`etiqueta_slug`, `columns`) solo configuran QUÉ mostrar, nunca
// llevan catálogo — `releases` llega ya resuelto por TreeRenderer.jsx
// (mismo patrón que `resolveBlockProps` en app/[locale]/page.jsx para el
// bloque "carousel" de HomeBlock), nunca se guarda en `props.draft_tree`.
export default function ProductGrid({ node, releases = [] }) {
  const { id, props = {}, style = {} } = node;
  const css = buildResponsiveCss(id, { columns: props.columns ?? { base: 4 } });
  if (releases.length === 0) return null;
  return (
    <div data-node-id={id} style={{ display: 'grid', gap: '1.5rem', ...style }}>
      {css && <style dangerouslySetInnerHTML={{ __html: css }} />}
      {releases.map((r) => (
        <ReleaseCard key={r.id} release={r} />
      ))}
    </div>
  );
}
