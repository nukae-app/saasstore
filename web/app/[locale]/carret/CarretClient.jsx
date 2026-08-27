'use client';

import { Link } from '../../../i18n/navigation';
import Image from 'next/image';
import { useTranslations } from 'next-intl';
import { Trash2, ShoppingBag, Loader2 } from 'lucide-react';
import { useState } from 'react';
import { useCart } from '../../../components/store/CartProvider';
import StorefrontNav from '../../../components/store/StorefrontNav';
import StorefrontFooter from '../../../components/store/StorefrontFooter';

function CartItem({ item, onRemove, removing }) {
  const t = useTranslations('carret');
  return (
    <div className="flex items-center gap-4 py-5 border-b border-zinc-100 last:border-0">
      {/* Cover */}
      <div className="relative w-16 h-16 rounded-lg overflow-hidden bg-zinc-100 shrink-0 flex items-center justify-center">
        {item.image_url ? (
          <Image src={item.image_url} alt="" fill sizes="64px" className="object-cover" />
        ) : (
          <svg viewBox="0 0 100 100" className="w-8 h-8 text-zinc-300" fill="currentColor">
            <circle cx="50" cy="50" r="48" />
            <circle cx="50" cy="50" r="34" fill="#FAF9F6" />
            <circle cx="50" cy="50" r="14" />
            <circle cx="50" cy="50" r="4" fill="#FAF9F6" />
          </svg>
        )}
      </div>

      {/* Info */}
      <div className="flex-1 min-w-0">
        <p className="font-medium text-sm truncate">{item.artista}</p>
        <p className="font-serif italic text-sm text-zinc-500 truncate">{item.title}</p>
        {item.condition === 'nou' && item.quantity > 1 && (
          <span className="text-xs text-zinc-500">{t('quantity', { count: item.quantity })}</span>
        )}
        {item.status === 'reservado' && (
          <span className="text-xs text-amber-600 font-medium">{t('reserved')}</span>
        )}
        {item.status !== 'disponible' && item.status !== 'reservado' && (
          <span className="text-xs text-red-500 font-medium">{t('noLongerAvailable')}</span>
        )}
      </div>

      {/* Price + remove */}
      <div className="flex items-center gap-3 shrink-0">
        <span className="font-semibold">{(parseFloat(item.price) * item.quantity).toFixed(2)} €</span>
        <button
          onClick={() => onRemove(item.item_id)}
          disabled={removing === item.item_id}
          className="w-11 h-11 -mr-1 flex items-center justify-center text-zinc-500 hover:text-red-500 transition-colors disabled:opacity-50"
          aria-label={t('remove')}
        >
          {removing === item.item_id ? (
            <Loader2 size={15} className="animate-spin" />
          ) : (
            <Trash2 size={15} />
          )}
        </button>
      </div>
    </div>
  );
}

export default function CarretClient() {
  const t = useTranslations('carret');
  const { items, total, refresh } = useCart();
  const [removing, setRemoving] = useState(null);
  const totalUnidades = items.reduce((sum, i) => sum + (i.quantity || 1), 0);

  async function handleRemove(itemId) {
    setRemoving(itemId);
    try {
      await fetch(`/api/cart/items/${itemId}`, { method: 'DELETE', credentials: 'include' });
      await refresh();
    } finally {
      setRemoving(null);
    }
  }

  return (
    <>
      <StorefrontNav />

      <main className="flex-1 container py-10 max-w-2xl">
        <h1 className="font-serif italic text-3xl mb-8">{t('myCart')}</h1>

        {items.length === 0 ? (
          <div className="text-center py-20">
            <ShoppingBag size={40} className="text-zinc-200 mx-auto mb-4" />
            <p className="text-zinc-500 mb-6">{t('cartEmpty')}</p>
            <Link
              href="/cataleg"
              className="inline-flex items-center gap-2 bg-primary hover:bg-zinc-800 text-white px-6 py-3 rounded-full font-medium text-sm transition-colors"
            >
              {t('exploreCatalog')}
            </Link>
          </div>
        ) : (
          <div className="grid md:grid-cols-[1fr_280px] gap-8 items-start">
            {/* Items */}
            <div className="bg-white rounded-xl shadow-[0_2px_20px_-6px_rgba(15,23,42,0.08)] px-5 py-2">
              {items.map(item => (
                <CartItem key={item.item_id} item={item} onRemove={handleRemove} removing={removing} />
              ))}
            </div>

            {/* Summary */}
            <div className="bg-white rounded-xl shadow-[0_2px_20px_-6px_rgba(15,23,42,0.08)] p-5 sticky top-24">
              <h2 className="font-medium text-zinc-900 mb-4">{t('summary')}</h2>

              <div className="flex justify-between text-sm text-zinc-500 mb-1.5">
                <span>{t('itemCount', { count: totalUnidades })}</span>
                <span>{parseFloat(total).toFixed(2)} €</span>
              </div>
              <div className="flex justify-between text-sm text-zinc-500 mb-4">
                <span>{t('shipping')}</span>
                <span className="text-zinc-500 italic">{t('atCheckout')}</span>
              </div>

              <div className="border-t border-zinc-100 pt-4 mb-4 flex justify-between font-semibold text-zinc-900">
                <span>{t('total')}</span>
                <span>{parseFloat(total).toFixed(2)} €</span>
              </div>

              <Link
                href="/checkout"
                className="block w-full text-center bg-primary hover:bg-zinc-800 text-white px-6 py-3 rounded-full font-medium text-sm transition-colors"
              >
                {t('proceedToPayment')}
              </Link>

              <Link
                href="/cataleg"
                className="block w-full text-center text-zinc-500 hover:text-zinc-700 mt-3 text-sm transition-colors py-1.5"
              >
                {t('continueShopping')}
              </Link>
            </div>
          </div>
        )}
      </main>

      <StorefrontFooter />
    </>
  );
}
