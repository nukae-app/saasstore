import { Suspense } from 'react';
import { getTranslations } from 'next-intl/server';
import { Link } from '../../../i18n/navigation';
import { api } from '../../lib/api';
import StorefrontNav from '../../../components/store/StorefrontNav';
import StorefrontFooter from '../../../components/store/StorefrontFooter';
import ReleaseCard from '../../../components/store/ReleaseCard';
import CatalogFilters from './CatalogFilters';
import MobileFilterSheet from '../../../components/store/MobileFilterSheet';
import CrateBrowser from '../../../components/store/CrateBrowser';

export async function generateMetadata({ params }) {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: 'cataleg' });
  return { title: t('title') };
}

async function CatalogResults({ searchParams }) {
  const t = await getTranslations('cataleg');
  const tc = await getTranslations('common');
  const p = await searchParams;
  const qs = new URLSearchParams();
  if (p.q) qs.set('q', p.q);
  if (p.format) qs.set('formato', p.format);
  if (p.genre) qs.set('genero', p.genre);
  if (p.etiqueta) qs.set('etiqueta', p.etiqueta);
  if (p.min) qs.set('precio_min', p.min);
  if (p.max) qs.set('precio_max', p.max);
  qs.set('page', p.page || '1');
  qs.set('page_size', '24');

  let catalog = { results: [], total: 0, page: 1, page_size: 24 };
  try {
    catalog = await api(`/catalog?${qs}`);
  } catch {}

  const totalPages = Math.ceil(catalog.total / catalog.page_size);
  const currentPage = catalog.page;

  function pageUrl(pg) {
    const next = new URLSearchParams(qs);
    next.set('page', pg);
    // convert back to UI params
    const ui = new URLSearchParams();
    if (p.q) ui.set('q', p.q);
    if (p.format) ui.set('format', p.format);
    if (p.genre) ui.set('genre', p.genre);
    if (p.etiqueta) ui.set('etiqueta', p.etiqueta);
    if (p.min) ui.set('min', p.min);
    if (p.max) ui.set('max', p.max);
    ui.set('page', pg);
    return `/cataleg?${ui}`;
  }

  return (
    <>
      <div className="flex items-baseline justify-between mb-6">
        <p className="text-sm text-zinc-500">
          {catalog.total === 0 ? t('noResults') : t('resultCount', { count: catalog.total })}
        </p>
      </div>

      {catalog.results.length === 0 ? (
        <div className="py-20 text-center">
          <p className="text-zinc-500 text-lg mb-4">{t('noResultsForSearch')}</p>
          <Link href="/cataleg" className="text-zinc-900 hover:underline text-sm">
            {t('viewFullCatalogArrow')}
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4 md:gap-6">
          {catalog.results.map(r => (
            <ReleaseCard key={r.id} release={r} />
          ))}
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <nav className="flex justify-center items-center gap-2 mt-12" aria-label={t('pagination')}>
          {currentPage > 1 && (
            <Link
              href={pageUrl(currentPage - 1)}
              className="px-4 py-2 rounded-lg border border-zinc-200 text-sm hover:bg-zinc-50 transition-colors"
            >
              ← {tc('previous')}
            </Link>
          )}
          <span className="text-sm text-zinc-500 px-4">
            {currentPage} / {totalPages}
          </span>
          {currentPage < totalPages && (
            <Link
              href={pageUrl(currentPage + 1)}
              className="px-4 py-2 rounded-lg border border-zinc-200 text-sm hover:bg-zinc-50 transition-colors"
            >
              {tc('next')} →
            </Link>
          )}
        </nav>
      )}
    </>
  );
}

async function ModeToggle({ searchParams }) {
  const t = await getTranslations('cataleg');
  const p = await searchParams;
  const mode = p.mode === 'remena' ? 'remena' : 'graella';

  function modeUrl(m) {
    const qs = new URLSearchParams(
      Object.entries(p).filter(([k]) => k !== 'mode')
    );
    if (m === 'remena') qs.set('mode', 'remena');
    const s = qs.toString();
    return `/cataleg${s ? `?${s}` : ''}`;
  }

  return (
    <div className="flex gap-1 bg-zinc-100 p-1 rounded-xl w-fit mb-8">
      <Link
        href={modeUrl('graella')}
        className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors ${mode === 'graella' ? 'bg-white shadow-sm text-zinc-900' : 'text-zinc-600 hover:text-zinc-900'}`}
      >
        {t('gridMode')}
      </Link>
      <Link
        href={modeUrl('remena')}
        className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors ${mode === 'remena' ? 'bg-white shadow-sm text-zinc-900' : 'text-zinc-600 hover:text-zinc-900'}`}
      >
        {t('browseMode')}
      </Link>
    </div>
  );
}

export default async function CatalogPage({ searchParams }) {
  const t = await getTranslations('cataleg');
  const p = await searchParams;
  let config = null;
  try {
    config = await api('/config/public');
  } catch {}
  const isVinils = !config || config.vertical === 'records';
  // El mode "remena" (regirar cubetes) és un concepte de botiga física de
  // discos — sense Seccio sembrades per a cap altre vertical (Fase 4), i
  // sense sentit per a res que no sigui vinil. El vertical és el sostre
  // (isVinils), però dins de "records" cada tenant pot apagar-lo individualment
  // (catalog_browse_mode, ver ConfiguracioBotiga) — igual fail-open que
  // isVinils si `config` no s'ha pogut resoldre.
  const browseModeEnabled = isVinils && (!config || config.catalog_browse_mode);
  const formatFilterEnabled = isVinils && (!config || config.catalog_format_filter);
  const genreFilterEnabled = isVinils && (!config || config.catalog_genre_filter);
  const mode = browseModeEnabled && p.mode === 'remena' ? 'remena' : 'graella';

  return (
    <>
      <StorefrontNav />

      <main className="flex-1 container py-8">
        <h1 className="font-serif italic text-3xl md:text-4xl mb-4">{t('title')}</h1>

        {browseModeEnabled && (
          <Suspense>
            <ModeToggle searchParams={searchParams} />
          </Suspense>
        )}

        {mode === 'remena' ? (
          <CrateBrowser />
        ) : (
          <>
            <Suspense>
              <MobileFilterSheet showFormatFilter={formatFilterEnabled} showGenreFilter={genreFilterEnabled} />
            </Suspense>

            <div className="flex gap-10">
              {/* Sidebar filters (desktop) */}
              <aside className="hidden md:block w-48 shrink-0 pt-0.5">
                <Suspense>
                  <CatalogFilters showFormatFilter={formatFilterEnabled} showGenreFilter={genreFilterEnabled} />
                </Suspense>
              </aside>

              {/* Results */}
              <div className="flex-1 min-w-0">
                <Suspense
                  fallback={
                    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4 md:gap-6">
                      {Array.from({ length: 8 }).map((_, i) => (
                        <div key={i} className="animate-pulse">
                          <div className="aspect-square bg-zinc-100 rounded-lg mb-3" />
                          <div className="h-3 bg-zinc-100 rounded w-3/4 mb-1.5" />
                          <div className="h-3 bg-zinc-100 rounded w-1/2" />
                        </div>
                      ))}
                    </div>
                  }
                >
                  <CatalogResults searchParams={searchParams} />
                </Suspense>
              </div>
            </div>
          </>
        )}
      </main>

      <StorefrontFooter />
    </>
  );
}
