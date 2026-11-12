'use client';

import { useEffect, useState } from 'react';
import { useTranslations } from 'next-intl';
import { Link } from '../../i18n/navigation';
import {
  CONSENT_EVENT, OPEN_BANNER_EVENT, readAnalyticsConsent, writeAnalyticsConsent,
} from '../lib/analyticsConsent';

// Banner de cookies/analítica. "Acceptar" y "Rebutjar" tienen exactamente el
// mismo peso visual (criterio AEPD: rechazar no puede ser más difícil que
// aceptar). Solo hay una categoría opcional (analítica); las técnicas
// (sesión, carrito) están exentas y se explican en /cookies.
export default function CookieConsent() {
  const t = useTranslations('cookieConsent');
  const [open, setOpen] = useState(false);

  useEffect(() => {
    setOpen(readAnalyticsConsent() === null);
    const reopen = () => setOpen(true);
    const sync = () => setOpen(readAnalyticsConsent() === null);
    window.addEventListener(OPEN_BANNER_EVENT, reopen);
    window.addEventListener('storage', sync);
    return () => {
      window.removeEventListener(OPEN_BANNER_EVENT, reopen);
      window.removeEventListener('storage', sync);
    };
  }, []);

  if (!open) return null;

  function decide(value) {
    writeAnalyticsConsent(value);
    setOpen(false);
  }

  const btn = 'flex-1 sm:flex-none rounded border border-zinc-900 bg-white px-5 py-2 text-sm font-medium text-zinc-900 hover:bg-zinc-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-zinc-900';

  return (
    <div
      role="dialog"
      aria-modal="false"
      aria-labelledby="cookie-consent-title"
      className="fixed inset-x-0 bottom-0 z-50 border-t border-zinc-300 bg-white p-4 shadow-lg"
    >
      <div className="container flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="text-sm text-zinc-800 max-w-3xl">
          <p id="cookie-consent-title" className="font-semibold">{t('title')}</p>
          <p>
            {t('body')}{' '}
            <Link href="/cookies" className="underline">{t('moreInfo')}</Link>
          </p>
        </div>
        <div className="flex gap-3 shrink-0">
          <button type="button" className={btn} onClick={() => decide(false)}>{t('reject')}</button>
          <button type="button" className={btn} onClick={() => decide(true)}>{t('accept')}</button>
        </div>
      </div>
    </div>
  );
}
