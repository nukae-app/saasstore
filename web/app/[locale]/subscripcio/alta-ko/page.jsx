'use client';

import { Link } from '../../../../i18n/navigation';
import { useTranslations } from 'next-intl';
import { XCircle } from 'lucide-react';
import StorefrontNav from '../../../../components/store/StorefrontNav';
import StorefrontFooter from '../../../../components/store/StorefrontFooter';

export default function SubscripcioAltaKoPage() {
  const t = useTranslations('subscripcio');
  return (
    <>
      <StorefrontNav />
      <main className="flex-1 container py-16 max-w-lg text-center">
        <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-6">
          <XCircle size={28} className="text-red-600" />
        </div>
        <h1 className="font-serif italic text-3xl mb-3">{t('paymentNotCompleted')}</h1>
        <p className="text-zinc-500 mb-8 text-sm">
          {t('bankDeniedCharge')}
        </p>
        <Link href="/subscripcio" className="inline-flex items-center gap-2 bg-primary hover:bg-zinc-800 text-white px-6 py-3 rounded-full font-medium text-sm transition-colors">
          {t('tryAgain')}
        </Link>
      </main>
      <StorefrontFooter />
    </>
  );
}
