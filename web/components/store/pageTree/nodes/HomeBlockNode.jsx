import { BLOCK_COMPONENTS } from '../../blocks/registry';

// Puente hacia el sistema de bloques viejo (`HomeBlock`, ver
// api/app/blocks/registry.py) — reutiliza sus componentes React TAL CUAL
// (cero reimplementación, cero riesgo de divergencia visual) para poder
// colocarlos dentro del árbol nuevo. `props.block_type` decide qué
// componente de BLOCK_COMPONENTS usar; `props.block_props` es lo que el
// admin configura (mismo shape que `HomeBlock.props` de siempre).
//
// La resolución de datos en vivo (`resolveLiveProps`) es una copia
// deliberada de `resolveBlockProps` en app/[locale]/page.jsx — mismo
// criterio que el resto de pageTree/: ese fichero es del home viejo, que
// se retira en la Fase 5, esta copia es la que queda cuando eso pase.
function resolveLiveProps(blockType, staticProps, live) {
  const { featured, config, recomanats, releasesByEtiqueta, recordstore } = live || {};
  switch (blockType) {
    case 'hero': {
      const featured2 = (recomanats || []).find((r) => r.id !== featured?.id) || null;
      const mosaicReleases = (recomanats || []).filter((r) => r.image_url).slice(0, 6);
      return { ...staticProps, featured, featured2, mosaicReleases, config };
    }
    case 'carousel':
      return { ...staticProps, releases: (releasesByEtiqueta || {})[staticProps.etiqueta_slug] || [], recordstore };
    case 'curator_selection': {
      const releases = (releasesByEtiqueta || {})[staticProps.etiqueta_slug] || [];
      return { releases: featured ? releases.filter((r) => r.id !== featured.id) : releases };
    }
    case 'about_strip':
      return { config };
    default:
      return staticProps;
  }
}

export default function HomeBlockNode({ node, liveHomeData }) {
  const { id, props = {} } = node;
  const Block = BLOCK_COMPONENTS[props.block_type];
  if (!Block) return null; // block_type desconocido: no tira la página, solo omite el nodo
  const blockProps = resolveLiveProps(props.block_type, props.block_props || {}, liveHomeData);
  return <Block key={id} id={id} {...blockProps} />;
}
