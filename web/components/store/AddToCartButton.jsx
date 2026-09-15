'use client';

import { useState } from 'react';
import { useTranslations } from 'next-intl';
import { ShoppingBag, Check, Loader2 } from 'lucide-react';
import { cn } from '../lib/utils';
import { useCart } from './CartProvider';

export default function AddToCartButton({ itemId, cantidad = 1, className }) {
  const t = useTranslations('cart');
  const [state, setState] = useState('idle'); // idle | loading | done | error
  const { refresh } = useCart();

  async function handleAdd() {
    setState('loading');
    try {
      const res = await fetch('/api/cart/items', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ item_id: itemId, quantity: cantidad }),
      });
      if (res.ok) {
        setState('done');
        await refresh();
        setTimeout(() => setState('idle'), 2000);
      } else if (res.status === 409) {
        setState('error');
        setTimeout(() => setState('idle'), 3000);
      } else {
        setState('idle');
      }
    } catch {
      setState('idle');
    }
  }

  return (
    <button
      onClick={handleAdd}
      disabled={state === 'loading' || state === 'done'}
      style={{ borderRadius: 'var(--radius-button, 9999px)' }}
      className={cn(
        'inline-flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-medium transition-all',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
        state === 'done'
          ? 'bg-green-500 text-white cursor-default'
          : state === 'error'
          ? 'bg-red-100 text-red-700 border border-red-200'
          : 'bg-primary text-primary-foreground hover:opacity-90 shadow-sm disabled:opacity-60',
        className,
      )}
    >
      {state === 'loading' && <Loader2 size={15} className="animate-spin" />}
      {state === 'done' && <Check size={15} />}
      {state === 'idle' && <ShoppingBag size={15} />}
      {state === 'loading' ? t('adding') : state === 'done' ? t('added') : state === 'error' ? t('notAvailable') : t('addToCart')}
    </button>
  );
}
