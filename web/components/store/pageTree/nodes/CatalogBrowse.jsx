// Nodo "vivo" (mismo espíritu que ProductGrid, regla de oro §2 del
// documento) que envuelve el catálogo real (búsqueda/filtros/paginación,
// `GET /catalog`) para poder incrustarlo en cualquier página del editor
// nuevo, sin tocar su lógica — decisión explícita del usuario (2026-09-28):
// "solo necesitamos poder diseñar el catálogo, no la manera de funcionar".
//
// Alcance de esta primera versión, a propósito: solo la experiencia
// estándar (filtros + graella + paginació) que ya usa `/cataleg` fuera del
// tema "Recordstore" y del mode "remena" (regirar cubetes) — esas dos
// variantes son bonus específicos de tema/vertical sobre la base, no la
// funcionalidad central. Añadirlas aquí es trabajo futuro si hace falta,
// no algo que se ha intentado replicar a medias.
import { Suspense } from 'react';
import { getTranslations } from 'next-intl/server';
import { Link } from '../../../../i18n/navigation';
import { api } from '../../../../app/lib/api';
import ReleaseCard from '../../ReleaseCard';
import CatalogFilters from '../../CatalogFilters';
import MobileFilterSheet from '../../MobileFilterSheet';

async function CatalogResults({ searchParams, basePath }) {
  const t = await getTranslations('cataleg');
  const tc = await getTranslations('common');
  const p = searchParams || {};
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
    const ui = new URLSearchParams();
    if (p.q) ui.set('q', p.q);
    if (p.format) ui.set('format', p.format);
    if (p.genre) ui.set('genre', p.genre);
    if (p.etiqueta) ui.set('etiqueta', p.etiqueta);
    if (p.min) ui.set('min', p.min);
    if (p.max) ui.set('max', p.max);
    ui.set('page', pg);
    return `${basePath}?${ui}`;
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
          <Link href={basePath} className="text-zinc-900 hover:underline text-sm">
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

      {totalPages > 1 && (
        <nav className="flex justify-center items-center gap-2 mt-12" aria-label={t('pagination')}>
          {currentPage > 1 && (
            <Link href={pageUrl(currentPage - 1)} className="px-4 py-2 rounded-lg border border-zinc-200 text-sm hover:bg-zinc-50 transition-colors">
              ← {tc('previous')}
            </Link>
          )}
          <span className="text-sm text-zinc-500 px-4">{currentPage} / {totalPages}</span>
          {currentPage < totalPages && (
            <Link href={pageUrl(currentPage + 1)} className="px-4 py-2 rounded-lg border border-zinc-200 text-sm hover:bg-zinc-50 transition-colors">
              {tc('next')} →
            </Link>
          )}
        </nav>
      )}
    </>
  );
}

export default async function CatalogBrowse({ node, locale, searchParams, basePath }) {
  const { id, style = {} } = node;
  let config = null;
  try {
    config = await api('/config/public');
  } catch {}
  const isVinils = !config || config.vertical === 'records';
  const formatFilterEnabled = isVinils && (!config || config.catalog_format_filter);
  const genreFilterEnabled = isVinils && (!config || config.catalog_genre_filter);
  const path = basePath || '/cataleg';

  return (
    <div data-node-id={id} style={style}>
      <Suspense>
        <MobileFilterSheet showFormatFilter={formatFilterEnabled} showGenreFilter={genreFilterEnabled} basePath={path} />
      </Suspense>
      <div className="flex gap-10">
        <aside className="hidden md:block w-48 shrink-0 pt-0.5">
          <Suspense>
            <CatalogFilters showFormatFilter={formatFilterEnabled} showGenreFilter={genreFilterEnabled} basePath={path} />
          </Suspense>
        </aside>
        <div className="flex-1 min-w-0">
          <Suspense
            fallback={
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4 md:gap-6">
                {Array.from({ length: 8 }).map((_, i) => (
                  <div key={i} className="animate-pulse">
                    <div style={{ borderRadius: 'var(--radius-card, 16px)' }} className="aspect-square bg-zinc-100 mb-3" />
                    <div className="h-3 bg-zinc-100 rounded w-3/4 mb-1.5" />
                    <div className="h-3 bg-zinc-100 rounded w-1/2" />
                  </div>
                ))}
              </div>
            }
          >
            <CatalogResults searchParams={searchParams} basePath={path} />
          </Suspense>
        </div>
      </div>
    </div>
  );
}
