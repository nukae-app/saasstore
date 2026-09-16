'use client';

import { useEffect, useState } from 'react';
import { useTranslations } from 'next-intl';
import { Minus, Plus } from 'lucide-react';
import AddToCartButton from './AddToCartButton';
import PriceTag from './PriceTag';

export default function NouStockLine({ itemId, precio, precioTarifa, disponibles }) {
  const t = useTranslations('disc');
  const [cantidad, setCantidad] = useState(1);
  // Mateix patró client-side que ReleaseCard/DiscInfoTabs.
  const [recordstore, setRecordstore] = useState(false);
  useEffect(() => {
    fetch('/api/config/public')
      .then(r => (r.ok ? r.json() : null))
      .then(data => { if (data?.theme?.preset === 'recordstore') setRecordstore(true); })
      .catch(() => {});
  }, []);

  if (recordstore) {
    // El preu i la insígnia "Nou" ja es mostren a dalt, a prop del títol
    // (ver disc/[id]/page.jsx) — aquí només queda l'acció: quantitat +
    // botó gran, com al mockup, sense repetir informació.
    return (
      <div className="flex items-stretch gap-3">
        {disponibles > 1 && (
          <div className="flex items-center border-2 border-black shrink-0">
            <button
              type="button"
              onClick={() => setCantidad(c => Math.max(1, c - 1))}
              disabled={cantidad <= 1}
              className="w-12 flex items-center justify-center text-black disabled:opacity-30"
              aria-label="-"
            >
              <Minus size={16} />
            </button>
            <span className="w-8 text-center text-base font-bold tabular-nums">{cantidad}</span>
            <button
              type="button"
              onClick={() => setCantidad(c => Math.min(disponibles, c + 1))}
              disabled={cantidad >= disponibles}
              className="w-12 flex items-center justify-center text-black disabled:opacity-30"
              aria-label="+"
            >
              <Plus size={16} />
            </button>
          </div>
        )}
        <AddToCartButton
          itemId={itemId}
          cantidad={cantidad}
          className="flex-1 h-14 text-base font-bold uppercase tracking-wide px-6"
        />
      </div>
    );
  }

  return (
    <div
      style={{ borderRadius: 'var(--radius-card, 12px)' }}
      className="flex items-center justify-between gap-4 p-4 border border-zinc-200 hover:border-zinc-300 transition-colors bg-white"
    >
      <div className="flex items-center gap-3 flex-wrap">
        <span className="inline-flex px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800">
          {t('newBadge')}
        </span>
        <span className="text-xs text-zinc-500">{t('copiesAvailable', { count: disponibles })}</span>
      </div>
      <div className="flex items-center gap-3 shrink-0">
        <PriceTag price={precio} listPrice={precioTarifa} />
        {disponibles > 1 && (
          <div style={{ borderRadius: 'var(--radius-button, 9999px)' }} className="flex items-center border border-zinc-200">
            <button
              type="button"
              onClick={() => setCantidad(c => Math.max(1, c - 1))}
              disabled={cantidad <= 1}
              className="w-8 h-8 flex items-center justify-center text-zinc-500 hover:text-zinc-900 disabled:opacity-40"
              aria-label="-"
            >
              <Minus size={13} />
            </button>
            <span className="w-6 text-center text-sm font-medium tabular-nums">{cantidad}</span>
            <button
              type="button"
              onClick={() => setCantidad(c => Math.min(disponibles, c + 1))}
              disabled={cantidad >= disponibles}
              className="w-8 h-8 flex items-center justify-center text-zinc-500 hover:text-zinc-900 disabled:opacity-40"
              aria-label="+"
            >
              <Plus size={13} />
            </button>
          </div>
        )}
        <AddToCartButton itemId={itemId} cantidad={cantidad} />
      </div>
    </div>
  );
}
