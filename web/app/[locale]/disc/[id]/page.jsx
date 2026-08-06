import { getTranslations } from 'next-intl/server';
import { Link } from '../../../../i18n/navigation';
import Image from 'next/image';
import { notFound } from 'next/navigation';
import { api } from '../../../lib/api';
import StorefrontNav from '../../../../components/store/StorefrontNav';
import StorefrontFooter from '../../../../components/store/StorefrontFooter';
import AddToCartButton from '../../../../components/store/AddToCartButton';
import RequestReleaseButton from '../../../../components/store/RequestReleaseButton';
import DiscInfoTabs from '../../../../components/store/DiscInfoTabs';
import NouStockLine from '../../../../components/store/NouStockLine';

export async function generateMetadata({ params }) {
  const { id, locale } = await params;
  try {
    const r = await api(`/catalog/releases/${id}`);
    return { title: `${r.artista} — ${r.titulo}` };
  } catch {
    const t = await getTranslations({ locale, namespace: 'disc' });
    return { title: t('record') };
  }
}

const GRADING = {
  M:  'Mint',
  NM: 'Near Mint',
  VG_PLUS: 'VG+',
  VG: 'Very Good',
  G_PLUS: 'G+',
  G:  'Good',
  F:  'Fair',
  P:  'Poor',
};

function ConditionBadge({ value }) {
  const label = GRADING[value] || value;
  const color =
    ['M', 'NM'].includes(value) ? 'bg-green-100 text-green-800' :
    ['VG_PLUS', 'VG'].includes(value) ? 'bg-amber-100 text-amber-800' :
    'bg-zinc-100 text-zinc-700';
  return (
    <span className={`inline-flex px-2 py-0.5 rounded text-xs font-medium ${color}`}>
      {label}
    </span>
  );
}

export default async function DiscPage({ params }) {
  const { id } = await params;
  const t = await getTranslations('disc');
  const tNav = await getTranslations('nav');
  let release;
  try {
    release = await api(`/catalog/releases/${id}`);
  } catch {
    notFound();
  }

  // Para nou (stock agregado), `status` se mantiene 'disponible' mientras la
  // línea no se retire a mano: la disponibilidad real depende de si queda
  // alguna unidad libre (cantidad - cantidad_reservada), no solo del status.
  const esVenible = (i) => i.condicion === 'nou'
    ? i.status === 'disponible' && (i.cantidad - i.cantidad_reservada) > 0
    : i.status === 'disponible';

  const disponibles = release.items.filter(esVenible);
  const agotats = release.items.filter(i => !esVenible(i));
  const disponiblesNou = disponibles.filter(i => i.condicion === 'nou');
  const disponiblesSegonaMa = disponibles.filter(i => i.condicion !== 'nou');
  const totalUnidadesDisponibles = disponiblesSegonaMa.length
    + disponiblesNou.reduce((sum, i) => sum + (i.cantidad - i.cantidad_reservada), 0);

  return (
    <>
      <StorefrontNav />

      <main className="flex-1">
        {/* Breadcrumb */}
        <div className="container pt-6 pb-0">
          <nav className="text-xs text-zinc-500 flex items-center gap-1.5">
            <Link href="/" className="hover:text-zinc-700 transition-colors">{t('home')}</Link>
            <span>/</span>
            <Link href="/cataleg" className="hover:text-zinc-700 transition-colors">{tNav('catalog')}</Link>
            <span>/</span>
            <span className="text-zinc-600 truncate max-w-[200px]">{release.artista}</span>
          </nav>
        </div>

        <div className="container py-8">
          <div className="grid md:grid-cols-2 gap-10 lg:gap-16 items-start">
            {/* Cover */}
            <div className="relative aspect-square rounded-xl overflow-hidden bg-zinc-100 flex items-center justify-center sticky top-24">
              {release.imagen_url ? (
                <Image
                  src={release.imagen_url}
                  alt={`${release.artista} — ${release.titulo}`}
                  fill
                  sizes="(max-width: 768px) 100vw, 50vw"
                  priority
                  className="object-cover"
                />
              ) : (
                <svg viewBox="0 0 100 100" className="w-32 h-32 text-zinc-300" fill="currentColor">
                  <circle cx="50" cy="50" r="48" />
                  <circle cx="50" cy="50" r="34" fill="#FAF9F6" />
                  <circle cx="50" cy="50" r="14" />
                  <circle cx="50" cy="50" r="4" fill="#FAF9F6" />
                </svg>
              )}
            </div>

            {/* Info */}
            <div>
              <p className="text-zinc-500 text-sm mb-1 font-medium tracking-wide uppercase text-xs">
                {release.formato}
              </p>
              <h1 className="font-serif italic text-3xl md:text-4xl leading-tight mb-1">
                {release.titulo}
              </h1>
              <p className="text-xl font-medium text-zinc-700 mb-4">{release.artista}</p>

              <DiscInfoTabs
                spotifyAlbumId={release.spotify_album_id}
                infoContent={
                  <>
                    {/* Metadata grid */}
                    <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm mb-6 border-t border-b border-zinc-100 py-4">
                      {release.sello && (
                        <>
                          <dt className="text-zinc-500">{t('label')}</dt>
                          <dd className="text-zinc-700">{release.sello}</dd>
                        </>
                      )}
                      {release.anio && (
                        <>
                          <dt className="text-zinc-500">{t('year')}</dt>
                          <dd className="text-zinc-700">{release.anio}</dd>
                        </>
                      )}
                      {release.genero && (
                        <>
                          <dt className="text-zinc-500">{t('genre')}</dt>
                          <dd className="text-zinc-700">{release.genero}</dd>
                        </>
                      )}
                      {release.referencia && (
                        <>
                          <dt className="text-zinc-500">{t('catalogNumber')}</dt>
                          <dd className="text-zinc-700 font-mono text-xs">{release.referencia}</dd>
                        </>
                      )}
                      {release.pais && (
                        <>
                          <dt className="text-zinc-500">{t('country')}</dt>
                          <dd className="text-zinc-700">{release.pais}</dd>
                        </>
                      )}
                      {release.estilos && (
                        <>
                          <dt className="text-zinc-500">{t('style')}</dt>
                          <dd className="text-zinc-700">{release.estilos}</dd>
                        </>
                      )}
                      {release.ean && (
                        <>
                          <dt className="text-zinc-500">EAN</dt>
                          <dd className="text-zinc-700 font-mono text-xs">{release.ean}</dd>
                        </>
                      )}
                    </dl>

                    {release.descripcion && (
                      <p className="text-zinc-500 text-sm leading-relaxed">{release.descripcion}</p>
                    )}
                  </>
                }
              />

              <div className="mt-6">
              {disponibles.length > 0 ? (
                <div className="space-y-3">
                  <p className="text-sm font-medium text-zinc-700">
                    {t('copiesAvailable', { count: totalUnidadesDisponibles })}
                  </p>
                  {disponiblesNou.map(item => (
                    <NouStockLine
                      key={item.id}
                      itemId={item.id}
                      precio={item.precio}
                      disponibles={item.cantidad - item.cantidad_reservada}
                    />
                  ))}
                  {disponiblesSegonaMa.map(item => (
                    <div
                      key={item.id}
                      className="flex items-center justify-between gap-4 p-4 border border-zinc-200 rounded-xl hover:border-zinc-300 transition-colors bg-white"
                    >
                      <div className="flex items-center gap-3 flex-wrap">
                        <ConditionBadge value={item.condicion} />
                        {item.estado_disco && (
                          <span className="text-xs text-zinc-500">{t('vinylCondition')}: {item.estado_disco}</span>
                        )}
                        {item.estado_funda && (
                          <span className="text-xs text-zinc-500">{t('sleeveCondition')}: {item.estado_funda}</span>
                        )}
                      </div>
                      <div className="flex items-center gap-3 shrink-0">
                        <span className="text-lg font-semibold text-zinc-900">
                          {parseFloat(item.precio).toFixed(2)} €
                        </span>
                        <AddToCartButton itemId={item.id} />
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="p-4 bg-zinc-50 rounded-xl shadow-[0_2px_20px_-6px_rgba(15,23,42,0.08)] text-center space-y-3">
                  <p className="text-zinc-500 text-sm">{t('noStockRightNow')}</p>
                  <RequestReleaseButton releaseId={release.id} className="w-full" />
                  <div>
                    <Link href="/cataleg" className="text-zinc-900 hover:underline text-sm inline-block">
                      {t('exploreOtherRecords')}
                    </Link>
                  </div>
                </div>
              )}

              {/* Para nou no hay contador histórico de unidades vendidas
                  (solo el stock actual): esta estadística se limita a
                  segona_ma, donde cada fila agotada sí es una venta real. */}
              {agotats.filter(i => i.condicion !== 'nou').length > 0 && (
                <p className="text-xs text-zinc-500 mt-3">
                  {t('copiesSold', { count: agotats.filter(i => i.condicion !== 'nou').length })}
                </p>
              )}
              </div>
            </div>
          </div>

          {/* Tracklist + Crèdits */}
          {(release.tracklist?.length > 0 || release.credits?.length > 0) && (
            <div className="mt-12 grid md:grid-cols-2 gap-10 lg:gap-16">

              {release.tracklist?.length > 0 && (
                <div>
                  <h2 className="text-sm font-semibold text-zinc-500 uppercase tracking-widest mb-4">{t('tracklist')}</h2>
                  <ol className="divide-y divide-zinc-100">
                    {release.tracklist.map((t, i) => (
                      <li key={i} className="flex items-baseline gap-4 py-2.5 text-sm">
                        <span className="w-8 text-right text-zinc-500 font-mono text-xs shrink-0">{t.pos}</span>
                        <span className="flex-1 text-zinc-800">{t.title}</span>
                        {t.duration && (
                          <span className="text-zinc-500 font-mono text-xs shrink-0">{t.duration}</span>
                        )}
                      </li>
                    ))}
                  </ol>
                </div>
              )}

              {release.credits?.length > 0 && (
                <div>
                  <h2 className="text-sm font-semibold text-zinc-500 uppercase tracking-widest mb-4">{t('credits')}</h2>
                  <dl className="divide-y divide-zinc-100">
                    {release.credits.map((c, i) => (
                      <div key={i} className="flex gap-4 py-2.5 text-sm">
                        <dt className="text-zinc-500 w-36 shrink-0 leading-snug">{c.role}</dt>
                        <dd className="text-zinc-800 leading-snug">
                          {c.name}
                          {c.tracks && <span className="text-zinc-500 text-xs ml-1">({c.tracks})</span>}
                        </dd>
                      </div>
                    ))}
                  </dl>
                </div>
              )}

            </div>
          )}
        </div>
      </main>

      <StorefrontFooter />
    </>
  );
}
