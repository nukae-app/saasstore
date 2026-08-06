import { getTranslations } from 'next-intl/server';
import { Link } from '../../i18n/navigation';
import { api } from '../lib/api';
import StorefrontNav from '../../components/store/StorefrontNav';
import StorefrontFooter from '../../components/store/StorefrontFooter';
import ReleaseCarousel from '../../components/store/ReleaseCarousel';
import SpotifyRecommendations from '../../components/store/SpotifyRecommendations';
import HomeHero from '../../components/store/HomeHero';
import CuratorSelection from '../../components/store/CuratorSelection';
import GenreGrid from '../../components/store/GenreGrid';

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

export default async function HomePage() {
  const t = await getTranslations('home');
  let catalog = [];
  let recomanats = [];
  let sonant = [];
  try {
    catalog = await fetchAllByEtiqueta('novetat');
  } catch {}
  try {
    recomanats = await fetchAllByEtiqueta('recomanat');
  } catch {}
  try {
    sonant = (await api('/catalog?esta_sonant=true&page_size=1')).results;
  } catch {}

  const featured = sonant[0] || recomanats[0] || catalog[0] || null;
  // Evitem mostrar el mateix disc a "Ara sona" i a "Selecció del curador"
  // si per casualitat el disc marcat com a sonant també és "recomanat".
  const curatorReleases = featured ? recomanats.filter(r => r.id !== featured.id) : recomanats;

  return (
    <>
      <StorefrontNav />

      <main className="flex-1">
        <HomeHero featured={featured} />

        {/* New arrivals */}
        {catalog.length > 0 && (
          <section className="py-24 md:py-32 px-5 md:px-16 bg-white">
            <div className="max-w-[1280px] mx-auto">
              <div className="flex justify-between items-baseline mb-12 md:mb-16">
                <div>
                  <h2 className="font-serif italic text-3xl md:text-4xl">{t('newArrivals')}</h2>
                  <p className="text-zinc-500 mt-2">{t('newArrivalsSubtitle')}</p>
                </div>
                <Link
                  href="/cataleg"
                  className="hidden sm:block text-xs font-medium text-zinc-900 uppercase tracking-widest hover:tracking-[0.15em] transition-all"
                >
                  {t('viewFullCatalog')}
                </Link>
              </div>
              <ReleaseCarousel releases={catalog} />
            </div>
          </section>
        )}

        {/* Spotify recommendations — client-side, only for logged-in users */}
        <SpotifyRecommendations />

        <CuratorSelection releases={curatorReleases} />

        <GenreGrid />

        {/* About strip */}
        <section className="py-24 px-5 md:px-16 bg-zinc-50">
          <div className="max-w-2xl mx-auto text-center">
            <h2 className="font-serif italic text-2xl md:text-3xl mb-4 text-zinc-900">
              Carrer de les Pujades&nbsp;113
            </h2>
            <p className="text-zinc-500 leading-relaxed mb-6">
              {t('aboutText')}
            </p>
            <p className="text-sm text-zinc-500">
              {t('alsoOn')}{' '}
              <a
                href="https://www.discogs.com"
                target="_blank"
                rel="noopener"
                className="text-zinc-900 hover:underline"
              >
                Discogs
              </a>
            </p>
          </div>
        </section>
      </main>

      <StorefrontFooter />
    </>
  );
}
