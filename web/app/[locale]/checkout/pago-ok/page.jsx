'use client';

import { Suspense, useEffect, useState } from 'react';
import { useTranslations } from 'next-intl';
import { Link } from '../../../../i18n/navigation';
import { useSearchParams } from 'next/navigation';
import { Check, Loader2, XCircle } from 'lucide-react';
import StorefrontNav from '../../../../components/store/StorefrontNav';
import StorefrontFooter from '../../../../components/store/StorefrontFooter';

// Redsys nos trae aquí tras la pasarela, pero su notificación server-to-server
// (la que realmente confirma el pago, ver api/app/routers/checkout.py) puede
// llegar unos instantes después: hacemos un pequeño polling antes de rendirnos.
function PagoOk() {
  const t = useTranslations('checkout');
  const params = useSearchParams();
  const orderId = params.get('order');
  const [order, setOrder] = useState(null);
  const [tries, setTries] = useState(0);

  useEffect(() => {
    if (!orderId) return;
    let cancelled = false;
    async function poll() {
      const res = await fetch(`/api/checkout/${orderId}`, { credentials: 'include' });
      if (cancelled) return;
      if (res.ok) {
        const data = await res.json();
        setOrder(data);
        if (data.status === 'pendiente_pago' && tries < 8) {
          setTimeout(() => setTries(t => t + 1), 1500);
        }
      }
    }
    poll();
    return () => { cancelled = true; };
  }, [orderId, tries]);

  const status = order?.status;

  return (
    <>
      <StorefrontNav />
      <main className="flex-1 container py-16 max-w-lg text-center">
        {!orderId ? (
          <p className="text-zinc-500">{t('missingOrderReference')}</p>
        ) : status === 'pagado' ? (
          <>
            <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-6">
              <Check size={28} className="text-green-600" />
            </div>
            <h1 className="font-serif italic text-3xl mb-3">{t('paymentConfirmed')}</h1>
            <p className="text-zinc-500 mb-2">
              {t('reference')}: <span className="font-mono text-zinc-700">{orderId.slice(0, 8).toUpperCase()}</span>
            </p>
            <p className="text-zinc-500 mb-8 text-sm">
              {t('emailSentPreparingOrder')}
            </p>
            <Link
              href="/cataleg"
              className="inline-flex items-center gap-2 bg-primary hover:bg-zinc-800 text-white px-6 py-3 rounded-full font-medium text-sm transition-colors"
            >
              {t('continueExploring')}
            </Link>
          </>
        ) : status === 'cancelado' ? (
          <>
            <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-6">
              <XCircle size={28} className="text-red-600" />
            </div>
            <h1 className="font-serif italic text-3xl mb-3">{t('couldNotConfirm')}</h1>
            <p className="text-zinc-500 mb-8 text-sm">
              {t('bankAuthorizedButUnavailable')}
            </p>
            <Link href="/cataleg" className="text-zinc-900 hover:underline text-sm">
              {t('backToCatalog')}
            </Link>
          </>
        ) : (
          <>
            <Loader2 size={32} className="text-zinc-900 animate-spin mx-auto mb-6" />
            <h1 className="font-serif italic text-2xl mb-3">{t('confirmingPayment')}</h1>
            <p className="text-zinc-500 text-sm">{t('validatingBankResponse')}</p>
          </>
        )}
      </main>
      <StorefrontFooter />
    </>
  );
}

export default function PagoOkPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 size={32} className="text-zinc-900 animate-spin" />
      </div>
    }>
      <PagoOk />
    </Suspense>
  );
}
