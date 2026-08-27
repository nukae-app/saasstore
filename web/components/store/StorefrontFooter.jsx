'use client';

import { Link } from '../../i18n/navigation';
import { useTranslations } from 'next-intl';
import { useEffect, useState } from 'react';

// Fallback mentre carrega /config/public o si la crida falla: mateixos
// valors que hi havia hardcoded abans, perquè el footer mai quedi buit.
const FALLBACK = {
  address: 'Carrer de les Pujades 113\n08005 Barcelona\nPoblenou',
  hours: 'Dl–Dv: 11h–20h\nDs: 11h–14h / 17h–20h\nDg: tancat',
  phone: null,
  contact_email: null,
  instagram_url: null,
  nombre: '',
  slug: null,
};

// No hi ha sistema de pujada de logo per tenant (fora d'abast, ver plan) —
// mentrestant, la imatge compartida (/logo.png) només es mostra per al
// tenant real d'Ultra-Local Records; la resta veu el seu nom en text.
const TENANT_AMB_LOGO = 'recordstore';

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
          {config.slug === TENANT_AMB_LOGO ? (
            <img src="/logo.png" alt={config.nombre} className="h-9 w-auto mb-3 invert" />
          ) : (
            <p className="font-serif italic text-lg text-zinc-900 mb-3">{config.nombre}</p>
          )}
          <address className="not-italic text-sm leading-relaxed">
            {(config.address || FALLBACK.address).split('\n').map((linia, i) => (
              <span key={i}>{linia}<br /></span>
            ))}
          </address>
          {(config.phone || config.contact_email || config.instagram_url) && (
            <p className="text-sm leading-relaxed mt-3">
              {config.phone && <>{config.phone}<br /></>}
              {config.contact_email && <>{config.contact_email}<br /></>}
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
            {(config.hours || FALLBACK.hours).split('\n').map((linia, i) => (
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
          <span>© {new Date().getFullYear()} {config.nombre} · {t('allRightsReserved')}</span>
          <nav className="flex gap-4">
            <Link href="/privacitat" className="hover:text-zinc-600 transition-colors">{t('privacyPolicy')}</Link>
            <Link href="/termes" className="hover:text-zinc-600 transition-colors">{t('termsOfUse')}</Link>
          </nav>
        </div>
      </div>
    </footer>
  );
}
