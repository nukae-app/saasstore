'use client';

import { Link } from '../../i18n/navigation';
import { useTranslations } from 'next-intl';
import { useEffect, useState } from 'react';
import { Instagram } from 'lucide-react';

// Fallback mentre carrega /config/public o si la crida falla: mateixos
// valors que hi havia hardcoded abans, perquè el footer mai quedi buit.
const FALLBACK = {
  address: 'Carrer de les Pujades 113\n08005 Barcelona\nPoblenou',
  hours: 'Dl–Dv: 11h–20h\nDs: 11h–14h / 17h–20h\nDg: tancat',
  phone: null,
  contact_email: null,
  instagram_url: null,
  nombre: '',
  logo_url: null,
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

  // Mateix criteri que StorefrontNav.jsx: aquest component tampoc és
  // token-driven (bg-zinc-50 en dur), el footer negre del tema "Recordstore"
  // necessita el mateix canvi de component.
  const recordstore = config.theme?.preset === 'recordstore';
  const linkClass = recordstore ? 'text-white/70 hover:text-white transition-colors' : 'hover:text-zinc-900 transition-colors';

  return (
    <footer className={recordstore ? 'bg-black text-white/70 mt-auto' : 'bg-zinc-50 text-zinc-500 mt-auto'}>
      {recordstore ? (
        // Mockup: logo en columna pròpia (no apilat amb l'adreça), sense
        // capçaleres "Horari"/"Enllaços" en negreta, i Instagram com a icona
        // a dalt a la dreta en comptes d'un enllaç de text dins l'adreça.
        <div className="container py-12 md:py-16 relative">
          {config.instagram_url && (
            <a
              href={config.instagram_url}
              target="_blank"
              rel="noopener"
              aria-label="Instagram"
              className="absolute top-12 md:top-16 right-5 md:right-16 w-9 h-9 flex items-center justify-center border border-white/40 hover:border-white transition-colors"
            >
              <Instagram size={16} className="text-white" />
            </a>
          )}
          <div className="grid grid-cols-1 md:grid-cols-[1.3fr_1fr_1fr_1fr] gap-8 md:gap-6">
            <p className="font-serif text-4xl md:text-5xl uppercase tracking-tight text-white leading-[0.9]">
              {config.nombre}
            </p>

            <address className="not-italic text-sm md:text-base leading-relaxed text-white/80">
              {(config.address || FALLBACK.address).split('\n').map((linia, i) => (
                <span key={i}>{linia}<br /></span>
              ))}
              {config.phone && <>{config.phone}<br /></>}
              {config.contact_email && <>{config.contact_email}<br /></>}
            </address>

            <p className="text-sm md:text-base leading-relaxed text-white/80">
              {t('schedule')}<br />
              {(config.hours || FALLBACK.hours).split('\n').map((linia, i) => (
                <span key={i}>{linia}<br /></span>
              ))}
            </p>

            <nav className="flex flex-col gap-1.5 text-sm md:text-base text-white/80">
              <Link href="/cataleg" className={linkClass}>{tNav('catalog')}</Link>
              <Link href="/blog" className={linkClass}>{tNav('blog')}</Link>
              <Link href="/agenda" className={linkClass}>{tNav('agenda')}</Link>
              {config.vertical === 'records' && (
                <a href="https://www.discogs.com" target="_blank" rel="noopener" className={linkClass}>
                  Discogs
                </a>
              )}
            </nav>
          </div>
        </div>
      ) : (
        <div className="container py-12 grid grid-cols-1 md:grid-cols-3 gap-8">
          <div>
            {config.logo_url ? (
              <img src={config.logo_url} alt={config.nombre} className="h-9 w-auto mb-3 invert" />
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
                  <a href={config.instagram_url} target="_blank" rel="noopener" className={linkClass}>
                    Instagram
                  </a>
                )}
              </p>
            )}
          </div>

          <div>
            <p className="text-sm font-medium mb-3 text-zinc-900">{t('schedule')}</p>
            <p className="text-sm leading-relaxed">
              {(config.hours || FALLBACK.hours).split('\n').map((linia, i) => (
                <span key={i}>{linia}<br /></span>
              ))}
            </p>
          </div>

          <div>
            <p className="text-sm font-medium mb-3 text-zinc-900">{t('links')}</p>
            <nav className="flex flex-col gap-1.5 text-sm">
              <Link href="/cataleg" className={linkClass}>{tNav('catalog')}</Link>
              <Link href="/blog" className={linkClass}>{tNav('blog')}</Link>
              <Link href="/agenda" className={linkClass}>{tNav('agenda')}</Link>
              {config.vertical === 'records' && (
                <a href="https://www.discogs.com" target="_blank" rel="noopener" className={linkClass}>
                  Discogs
                </a>
              )}
            </nav>
          </div>
        </div>
      )}

      <div className={`border-t py-4 ${recordstore ? 'border-white/20' : 'border-zinc-200'}`}>
        <div className={`container flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 text-xs ${recordstore ? 'text-white/50' : 'text-zinc-400'}`}>
          <span>© {new Date().getFullYear()} {config.nombre} · {t('allRightsReserved')}</span>
          <nav className="flex gap-4">
            <Link href="/privacitat" className={recordstore ? 'hover:text-white transition-colors' : 'hover:text-zinc-600 transition-colors'}>{t('privacyPolicy')}</Link>
            <Link href="/termes" className={recordstore ? 'hover:text-white transition-colors' : 'hover:text-zinc-600 transition-colors'}>{t('termsOfUse')}</Link>
          </nav>
        </div>
      </div>
    </footer>
  );
}
