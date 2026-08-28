import { api } from '../lib/api';
import StorefrontNav from '../../components/store/StorefrontNav';
import StorefrontFooter from '../../components/store/StorefrontFooter';
import PreviewBridge from '../../components/store/PreviewBridge';
import { BLOCK_COMPONENTS } from '../../components/store/blocks/registry';

async function fetchAllByEtiqueta(slug) {
  const results = [];
  let page = 1;
  for (;;) {
    const data = await api(`/catalog?etiqueta=${slug}&page=${page}&page_size=100`);
    results.push(...data.results);
    if (results.length >= data.total || data.results.length === 0) break;
    page += 1;
  }
  return results;
}

// Combina els props que ha configurat l'admin (block.props) amb dades de
// catàleg en viu — regla d'or del constructor de blocs (ver
// api/app/blocks/registry.py): els props d'un bloc mai porten dades de
// catàleg, sempre les resol aquesta pàgina a cada request, igual que abans.
function resolveBlockProps(block, { featured, config, releasesByEtiqueta }) {
  switch (block.block_type) {
    case 'hero':
      return { ...block.props, featured };
    case 'carousel':
      return { ...block.props, releases: releasesByEtiqueta[block.props.etiqueta_slug] || [] };
    case 'curator_selection': {
      // Evitem mostrar el mateix disc a "Ara sona" i a la selecció del
      // curador si per casualitat el disc destacat també té l'etiqueta
      // que alimenta aquest bloc.
      const releases = releasesByEtiqueta[block.props.etiqueta_slug] || [];
      return { releases: featured ? releases.filter((r) => r.id !== featured.id) : releases };
    }
    case 'about_strip':
      return { config };
    default:
      return block.props;
  }
}

export default async function HomePage() {
  let blocks = [];
  let recomanats = [];
  let sonant = [];
  let config = null;
  try {
    blocks = await api('/config/public/home-blocks');
  } catch {}
  try {
    recomanats = await fetchAllByEtiqueta('recomanat');
  } catch {}
  try {
    sonant = (await api('/catalog?esta_sonant=true&page_size=1')).results;
  } catch {}
  try {
    config = await api('/config/public');
  } catch {}

  const featured = sonant[0] || recomanats[0] || null;

  // Un fetch per cada etiqueta diferent que faci servir algun bloc
  // "carousel" o "curator_selection" del tenant (normalment "novetat"/
  // "recomanat", però res impedeix tenir-ne més amb etiquetes diferents).
  const etiquetaSlugs = [...new Set(
    blocks
      .filter((b) => b.block_type === 'carousel' || b.block_type === 'curator_selection')
      .map((b) => b.props.etiqueta_slug)
      .filter(Boolean)
  )];
  const releasesByEtiqueta = {};
  for (const slug of etiquetaSlugs) {
    try {
      releasesByEtiqueta[slug] = await fetchAllByEtiqueta(slug);
    } catch {
      releasesByEtiqueta[slug] = [];
    }
  }

  return (
    <>
      <PreviewBridge />
      <StorefrontNav />

      <main className="flex-1">
        {blocks.length === 0 ? (
          // Xarxa de seguretat: si per algun motiu el tenant no té cap bloc
          // configurat (migració pendent, esborrat per error...), un home
          // completament buit és el pitjor fallback possible.
          <div className="py-24 text-center text-zinc-400">
            <p className="font-serif italic text-2xl">{config?.nombre || ''}</p>
          </div>
        ) : (
          blocks.map((block) => {
            const Block = BLOCK_COMPONENTS[block.block_type];
            if (!Block) return null;
            return <Block key={block.id} id={block.id} {...resolveBlockProps(block, { featured, config, releasesByEtiqueta })} />;
          })
        )}
      </main>

      <StorefrontFooter />
    </>
  );
}
