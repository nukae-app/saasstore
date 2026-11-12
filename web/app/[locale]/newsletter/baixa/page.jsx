'use client';

import { Suspense, useEffect, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { useTranslations } from 'next-intl';
import { Loader2, CheckCircle2 } from 'lucide-react';
import StorefrontNav from '../../../../components/store/StorefrontNav';
import StorefrontFooter from '../../../../components/store/StorefrontFooter';

// Baixa de la newsletter, en dos passos a propòsit: obrir l'enllaç del correu
// només valida el token (GET, sense efectes: els escàners d'enllaços dels
// correus també el visiten) i la baixa real és el POST del botó. Gmail/Yahoo
// fan la seva pròpia baixa en un clic contra /api/newsletter/baixa (POST).
function Unsubscribe() {
  const t = useTranslations('newsletterUnsubscribe');
  const token = useSearchParams().get('token');
  const [state, setState] = useState(token ? 'checking' : 'invalid'); // checking | ready | invalid | sending | done | error

  useEffect(() => {
    if (!token) return;
    fetch(`/api/newsletter/baixa?token=${encodeURIComponent(token)}`)
      .then((r) => setState(r.ok ? 'ready' : 'invalid'))
      .catch(() => setState('error'));
  }, [token]);

  async function confirm() {
    setState('sending');
    try {
      const r = await fetch(`/api/newsletter/baixa?token=${encodeURIComponent(token)}`, { method: 'POST' });
      setState(r.ok ? 'done' : 'invalid');
    } catch {
      setState('error');
    }
  }

  return (
    <main className="container max-w-xl py-12">
      <h1 className="text-2xl font-semibold mb-3">{t('title')}</h1>
      {state === 'checking' && <Loader2 size={20} className="animate-spin" aria-label={t('checking')} />}
      {(state === 'ready' || state === 'sending') && (
        <>
          <p className="text-sm text-zinc-600 mb-6">{t('intro')}</p>
          <button type="button" onClick={confirm} disabled={state === 'sending'}
            className="flex items-center gap-2 bg-zinc-900 hover:bg-zinc-800 text-white px-6 py-3 rounded-full font-medium text-sm disabled:opacity-60">
            {state === 'sending' && <Loader2 size={16} className="animate-spin" />}
            {t('confirm')}
          </button>
        </>
      )}
      {state === 'done' && (
        <div className="bg-green-50 border border-green-200 rounded-xl p-5 text-sm text-green-900" role="status">
          <div className="flex items-center gap-2 font-medium mb-1"><CheckCircle2 size={18} /> {t('doneTitle')}</div>
          <p>{t('done')}</p>
        </div>
      )}
      {state === 'invalid' && <p className="text-sm text-red-600" role="alert">{t('invalid')}</p>}
      {state === 'error' && <p className="text-sm text-red-600" role="alert">{t('error')}</p>}
    </main>
  );
}

export default function NewsletterUnsubscribePage() {
  return (
    <>
      <StorefrontNav />
      <Suspense fallback={null}>
        <Unsubscribe />
      </Suspense>
      <StorefrontFooter />
    </>
  );
}
