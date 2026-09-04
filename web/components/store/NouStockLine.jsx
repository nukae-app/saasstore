'use client';

import { useState } from 'react';
import { useTranslations } from 'next-intl';
import { Minus, Plus } from 'lucide-react';
import AddToCartButton from './AddToCartButton';
import PriceTag from './PriceTag';

export default function NouStockLine({ itemId, precio, precioTarifa, disponibles }) {
  const t = useTranslations('disc');
  const [cantidad, setCantidad] = useState(1);

  return (
    <div className="flex items-center justify-between gap-4 p-4 border border-zinc-200 rounded-xl hover:border-zinc-300 transition-colors bg-white">
      <div className="flex items-center gap-3 flex-wrap">
        <span className="inline-flex px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800">
          {t('newBadge')}
        </span>
        <span className="text-xs text-zinc-500">{t('copiesAvailable', { count: disponibles })}</span>
      </div>
      <div className="flex items-center gap-3 shrink-0">
        <PriceTag price={precio} listPrice={precioTarifa} />
        {disponibles > 1 && (
          <div className="flex items-center border border-zinc-200 rounded-full">
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
