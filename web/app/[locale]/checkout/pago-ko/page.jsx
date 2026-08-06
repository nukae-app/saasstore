'use client';

import { Suspense } from 'react';
import { useTranslations } from 'next-intl';
import { Link } from '../../../../i18n/navigation';
import { useSearchParams } from 'next/navigation';
import { Loader2, XCircle } from 'lucide-react';
import StorefrontNav from '../../../../components/store/StorefrontNav';
import StorefrontFooter from '../../../../components/store/StorefrontFooter';

function PagoKo() {
  const t = useTranslations('checkout');
  const params = useSearchParams();
  const orderId = params.get('order');

  return (
    <>
      <StorefrontNav />
      <main className="flex-1 container py-16 max-w-lg text-center">
        <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-6">
          <XCircle size={28} className="text-red-600" />
        </div>
        <h1 className="font-serif italic text-3xl mb-3">{t('paymentNotCompleted')}</h1>
        {orderId && (
          <p className="text-zinc-500 mb-2">
            {t('reference')}: <span className="font-mono text-zinc-700">{orderId.slice(0, 8).toUpperCase()}</span>
          </p>
        )}
        <p className="text-zinc-500 mb-8 text-sm">
          {t('bankRejectedPayment')}
        </p>
        <Link
          href="/cataleg"
          className="inline-flex items-center gap-2 bg-primary hover:bg-zinc-800 text-white px-6 py-3 rounded-full font-medium text-sm transition-colors"
        >
          {t('backToCatalogPlain')}
        </Link>
      </main>
      <StorefrontFooter />
    </>
  );
}

export default function PagoKoPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 size={32} className="text-zinc-900 animate-spin" />
      </div>
    }>
      <PagoKo />
    </Suspense>
  );
}
