'use client';

import { Link } from '../../i18n/navigation';
import { useTranslations } from 'next-intl';
import { useEffect, useState } from 'react';

// Fallback mentre carrega /config/public o si la crida falla: mateixos
// valors que hi havia hardcoded abans, perquè el footer mai quedi buit.
const FALLBACK = {
  adreca: 'Carrer de les Pujades 113\n08005 Barcelona\nPoblenou',
  horari: 'Dl–Dv: 11h–20h\nDs: 11h–14h / 17h–20h\nDg: tancat',
  telefon: null,
  email_contacte: null,
  instagram_url: null,
};

export default function StorefrontFooter() {
  const t = useTranslations('footer');
  const tNav = useTranslations('nav');
  const [config, setConfig] = useState(FALLBACK);

  useEffect(() => {
    fetch('/api/config/public')
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => { if (data) setConfig(data); })
      .catch(() => {});
  }, []);

  return (
    <footer className="bg-zinc-50 text-zinc-500 mt-auto">
      <div className="container py-12 grid grid-cols-1 md:grid-cols-3 gap-8">
        <div>
          <img src="/logo.png" alt="Ultra-Local Records" className="h-9 w-auto mb-3 invert" />
          <address className="not-italic text-sm leading-relaxed">
            {(config.adreca || FALLBACK.adreca).split('\n').map((linia, i) => (
              <span key={i}>{linia}<br /></span>
            ))}
          </address>
          {(config.telefon || config.email_contacte || config.instagram_url) && (
            <p className="text-sm leading-relaxed mt-3">
              {config.telefon && <>{config.telefon}<br /></>}
              {config.email_contacte && <>{config.email_contacte}<br /></>}
              {config.instagram_url && (
                <a href={config.instagram_url} target="_blank" rel="noopener" className="hover:text-zinc-900 transition-colors">
                  Instagram
                </a>
              )}
            </p>
          )}
        </div>

        <div>
          <p className="text-zinc-900 text-sm font-medium mb-3">{t('schedule')}</p>
          <p className="text-sm leading-relaxed">
            {(config.horari || FALLBACK.horari).split('\n').map((linia, i) => (
              <span key={i}>{linia}<br /></span>
            ))}
          </p>
        </div>

        <div>
          <p className="text-zinc-900 text-sm font-medium mb-3">{t('links')}</p>
          <nav className="flex flex-col gap-1.5 text-sm">
            <Link href="/cataleg" className="hover:text-zinc-900 transition-colors">{tNav('catalog')}</Link>
            <Link href="/blog" className="hover:text-zinc-900 transition-colors">{tNav('blog')}</Link>
            <Link href="/agenda" className="hover:text-zinc-900 transition-colors">{tNav('agenda')}</Link>
            <a href="https://www.discogs.com" target="_blank" rel="noopener" className="hover:text-zinc-900 transition-colors">
              Discogs
            </a>
          </nav>
        </div>
      </div>

      <div className="border-t border-zinc-200 py-4">
        <div className="container flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 text-xs text-zinc-400">
          <span>© {new Date().getFullYear()} Ultra-Local Records · {t('allRightsReserved')}</span>
          <nav className="flex gap-4">
            <Link href="/privacitat" className="hover:text-zinc-600 transition-colors">{t('privacyPolicy')}</Link>
            <Link href="/termes" className="hover:text-zinc-600 transition-colors">{t('termsOfUse')}</Link>
          </nav>
        </div>
      </div>
    </footer>
  );
}
