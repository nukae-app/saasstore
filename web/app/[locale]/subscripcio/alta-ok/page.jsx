'use client';

import { useEffect, useState } from 'react';
import { Link } from '../../../../i18n/navigation';
import { useTranslations } from 'next-intl';
import { Check, Loader2 } from 'lucide-react';
import { authFetch } from '../../../../components/store/AuthProvider';
import StorefrontNav from '../../../../components/store/StorefrontNav';
import StorefrontFooter from '../../../../components/store/StorefrontFooter';

// Redsys torna aquí després de la pantalla de pagament, però la notificació
// servidor-a-servidor que confirma l'alta de veritat (veure
// api/app/routers/subscripcions_public.py) pot arribar uns instants més
// tard: fem un petit polling abans de rendir-nos.
export default function SubscripcioAltaOkPage() {
  const t = useTranslations('subscripcio');
  const [estat, setEstat] = useState(null);
  const [tries, setTries] = useState(0);

  useEffect(() => {
    let cancelled = false;
    async function poll() {
      const res = await authFetch('/me/subscripcio');
      if (cancelled) return;
      if (res.status === 404) {
        if (tries < 8) setTimeout(() => setTries(t => t + 1), 1500);
        else setEstat('desconegut');
        return;
      }
      if (res.ok) {
        const data = await res.json();
        setEstat(data.estat);
        if (data.estat === 'pendent_pagament' && tries < 8) {
          setTimeout(() => setTries(t => t + 1), 1500);
        }
      }
    }
    poll();
    return () => { cancelled = true; };
  }, [tries]);

  return (
    <>
      <StorefrontNav />
      <main className="flex-1 container py-16 max-w-lg text-center">
        {estat === 'activa' ? (
          <>
            <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-6">
              <Check size={28} className="text-green-600" />
            </div>
            <h1 className="font-serif italic text-3xl mb-3">{t('welcomeToClub')}</h1>
            <p className="text-zinc-500 mb-8 text-sm">
              {t('confirmationEmailSent')}
            </p>
            <Link href="/compte/subscripcio" className="inline-flex items-center gap-2 bg-primary hover:bg-zinc-800 text-white px-6 py-3 rounded-full font-medium text-sm transition-colors">
              {t('viewMySubscription')}
            </Link>
          </>
        ) : estat === 'desconegut' ? (
          <>
            <h1 className="font-serif italic text-2xl mb-3">{t('cannotConfirmYet')}</h1>
            <p className="text-zinc-500 text-sm mb-8">{t('ifChargedWillActivate')}</p>
            <Link href="/compte/subscripcio" className="text-zinc-900 hover:underline text-sm">{t('goToMyAccount')}</Link>
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
