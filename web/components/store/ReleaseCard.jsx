'use client';

import { useTranslations } from 'next-intl';
import { Link } from '../../i18n/navigation';
import Image from 'next/image';
import PriceTag from './PriceTag';

const VINYL_SVG = (
  <svg viewBox="0 0 100 100" className="w-16 h-16 text-zinc-300" fill="currentColor">
    <circle cx="50" cy="50" r="48" />
    <circle cx="50" cy="50" r="34" fill="#FAF9F6" />
    <circle cx="50" cy="50" r="14" />
    <circle cx="50" cy="50" r="4" fill="#FAF9F6" />
  </svg>
);

export default function ReleaseCard({ release }) {
  const t = useTranslations('crate');
  // Para nou (stock agregado), status se mantiene 'disponible' aunque no
  // quede ninguna unidad libre (cantidad - cantidad_reservada): hay que
  // comprobarlo aparte, si no un disco nuevo agotado seguiría pareciendo
  // comprable.
  const disponibles = release.items.filter(i => i.condition === 'nou'
    ? i.status === 'disponible' && (i.quantity - i.reserved_quantity) > 0
    : i.status === 'disponible');
  // El item más barato es el que se enseña en la tarjeta — si ese tiene
  // oferta activa (list_price), se muestra tachado junto al precio final.
  const minItem = disponibles.length
    ? disponibles.reduce((a, b) => (parseFloat(a.price) <= parseFloat(b.price) ? a : b))
    : null;

  return (
    <Link href={`/disc/${release.id}`} className="group block">
      <div
        style={{ borderRadius: 'var(--radius-card, 24px)' }}
        className="aspect-square overflow-hidden bg-zinc-100 mb-4 flex items-center justify-center relative shadow-[0_2px_20px_-6px_rgba(15,23,42,0.06)] group-hover:shadow-[0_8px_32px_-8px_rgba(15,23,42,0.12)] transition-shadow"
      >
        {release.image_url ? (
          <Image
            src={release.image_url}
            alt={`${release.artista} — ${release.title}`}
            fill
            sizes="(max-width: 640px) 50vw, (max-width: 1024px) 33vw, 25vw"
            className="object-cover group-hover:scale-105 transition-transform duration-500"
          />
        ) : (
          <div className="flex items-center justify-center w-full h-full">
            {VINYL_SVG}
          </div>
        )}
        {disponibles.length === 0 && (
          <div className="absolute inset-0 bg-white/60 flex items-center justify-center">
            <span className="text-xs font-medium text-zinc-500 bg-white px-2 py-1 rounded-full border">{t('soldOut')}</span>
          </div>
        )}
        {release.etiquetes?.length > 0 && (
          <div className="absolute top-2 left-2 flex flex-col gap-1 items-start">
            {release.etiquetes.slice(0, 2).map(e => (
              <span key={e.id}
                className="inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold text-white shadow-sm"
                style={{ backgroundColor: e.color || '#94a3b8' }}>
                {e.name_ca}
              </span>
            ))}
          </div>
        )}
      </div>
      <div>
        <p className="font-medium text-sm leading-snug truncate text-zinc-900 group-hover:text-zinc-500 transition-colors">
          {release.artista}
        </p>
        <p className="font-serif italic text-sm text-zinc-500 truncate leading-snug">
          {release.title}
        </p>
        <div className="flex items-center justify-between mt-1.5">
          <span className="text-xs text-zinc-500 truncate">
            {[release.formato, release.sello].filter(Boolean).join(' · ')}
          </span>
          {minItem !== null && (
            <span className="shrink-0 ml-1">
              <PriceTag price={minItem.price} listPrice={minItem.list_price} size="text-sm" />
            </span>
          )}
        </div>
      </div>
    </Link>
  );
}
