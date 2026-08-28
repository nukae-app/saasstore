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
function resolveBlockProps(block, { featured, curatorReleases, config, releasesByEtiqueta }) {
  switch (block.block_type) {
    case 'hero':
      return { ...block.props, featured };
    case 'carousel':
      return { ...block.props, releases: releasesByEtiqueta[block.props.etiqueta_slug] || [] };
    case 'curator_selection':
      return { releases: curatorReleases };
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
  // Evitem mostrar el mateix disc a "Ara sona" i a "Selecció del curador"
  // si per casualitat el disc marcat com a sonant també és "recomanat".
  const curatorReleases = featured ? recomanats.filter((r) => r.id !== featured.id) : recomanats;

  // Un fetch per cada etiqueta diferent que faci servir algun bloc
  // "carousel" del tenant (normalment només "novetat", però res impedeix
  // tenir-ne dos amb etiquetes diferents).
  const carouselSlugs = [...new Set(blocks.filter((b) => b.block_type === 'carousel').map((b) => b.props.etiqueta_slug).filter(Boolean))];
  const releasesByEtiqueta = {};
  for (const slug of carouselSlugs) {
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

      <main id="__blocks_root" className="flex-1">
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
            return <Block key={block.id} id={block.id} {...resolveBlockProps(block, { featured, curatorReleases, config, releasesByEtiqueta })} />;
          })
        )}
      </main>

      <StorefrontFooter />
    </>
  );
}
