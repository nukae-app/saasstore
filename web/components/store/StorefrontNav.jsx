'use client';

import { Link } from '../../i18n/navigation';
import { usePathname } from '../../i18n/navigation';
import NextLink from 'next/link';
import { useTranslations } from 'next-intl';
import { ShoppingBag, Menu, X, User, LogOut, LayoutDashboard } from 'lucide-react';
import { useState, useEffect } from 'react';
import { useCart } from './CartProvider';
import { useAuth } from './AuthProvider';
import { useSubscripcionsActives } from './useSubscripcionsActives';
import { useManteniment } from './useManteniment';
import { useTenantConfig } from './useTenantConfig';
import LanguageSwitcher from './LanguageSwitcher';

export default function StorefrontNav() {
  const t = useTranslations('nav');
  const FALLBACK_LINKS = [
    { href: '/cataleg', label: t('catalog') },
    { href: '/blog', label: t('blog') },
    { href: '/agenda', label: t('agenda') },
  ];
  const [open, setOpen] = useState(false);
  const [userMenu, setUserMenu] = useState(false);
  const [navLinks, setNavLinks] = useState(FALLBACK_LINKS);
  const { itemCount } = useCart();
  const { user, logout } = useAuth();
  const subscripcionsActives = useSubscripcionsActives();
  const manteniment = useManteniment();
  const config = useTenantConfig();
  const pathname = usePathname();
  const links = subscripcionsActives ? [...navLinks, { href: '/subscripcio', label: t('club') }] : navLinks;
  // Tema "Recordstore" (ver globals.css :: [data-theme-preset]) — aquest
  // component és dels pocs del storefront que no és token-driven (bg-white/
  // border-zinc en dur), així que la barra negra/majúscules necessita un
  // canvi de component real, no només CSS. Es dedueix de config.theme
  // (mateix /config/public que ja es consultava) en lloc d'una prop nova.
  const recordstore = config.theme?.preset === 'recordstore';
  // Als mockups la barra només és negra al home (on continua visualment amb
  // la franja negra de la il·lustració de sota) — a la resta de pàgines es
  // fon amb el fons clar de la pàgina, amb text fosc. `recordstore` decideix
  // l'estructura (mida, font, separadors); `dark` només decideix quin joc
  // de colors s'hi aplica per sobre.
  const dark = recordstore && pathname === '/';

  useEffect(() => {
    fetch('/api/pagines')
      .then(r => r.ok ? r.json() : null)
      .then(pagines => {
        if (!pagines?.length) return;
        const links = [
          { href: '/cataleg', label: t('catalog') },
          ...pagines.map(p => ({ href: `/${p.slug}`, label: p.name })),
        ];
        setNavLinks(links);
      })
      .catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <header
      className={
        recordstore
          ? dark
            ? 'sticky top-0 z-40 bg-black text-white border-b border-black'
            : 'sticky top-0 z-40 bg-background text-foreground border-b border-black/10'
          : 'sticky top-0 z-40 bg-white/90 backdrop-blur-md border-b border-zinc-200 text-zinc-900'
      }
    >
      {manteniment && (
        <div className="bg-amber-500 text-white text-xs md:text-sm text-center py-2 px-4">
          {t('maintenanceBanner')}
        </div>
      )}
      <div className={`container flex items-center gap-8 ${recordstore ? 'h-20 md:h-28' : 'h-16'}`}>
        <Link href="/" className="shrink-0 opacity-90 hover:opacity-100 transition-opacity">
          {recordstore ? (
            // Mockup: sempre wordmark de text pla, mai el logo en caixa —
            // encara que el tenant tingui un logo_url pujat (ver
            // StorefrontFooter.jsx pel mateix criteri). Mida gran, a prop
            // de la dels enllaços del nav (al mockup pesen pràcticament
            // igual), no la mida petita "de marca discreta" del tema per
            // defecte.
            <span className={`font-serif text-2xl md:text-4xl uppercase tracking-tight leading-none ${dark ? 'text-white' : 'text-black'}`}>{config.nombre}</span>
          ) : config.logo_url ? (
            <img src={config.logo_url} alt={config.nombre} className="h-8 md:h-10 w-auto invert" />
          ) : (
            <span className="font-serif italic text-xl md:text-2xl text-zinc-900">{config.nombre}</span>
          )}
        </Link>

        <nav className={`hidden md:flex items-center flex-1 ${recordstore ? 'gap-1 font-serif text-xl md:text-3xl uppercase tracking-tight' : 'gap-6 text-sm text-zinc-500'}`}>
          {links.map(({ href, label }, i) => (
            <span key={href} className="flex items-center">
              {recordstore && i > 0 && (
                <span className={`mx-3 md:mx-4 ${dark ? 'text-white/50' : 'text-black/30'}`} aria-hidden="true">•</span>
              )}
              <Link
                href={href}
                className={
                  recordstore
                    ? `transition-opacity hover:opacity-70 ${dark ? 'text-white' : 'text-black'} ${pathname.startsWith(href) ? '' : 'opacity-90'}`
                    : `hover:text-zinc-900 transition-colors ${pathname.startsWith(href) ? 'text-zinc-900 font-medium' : ''}`
                }
              >
                {label}
              </Link>
            </span>
          ))}
        </nav>

        <div className="flex items-center gap-3 ml-auto md:ml-0">
          <LanguageSwitcher className="hidden md:flex" dark={dark} />

          {/* Cart */}
          <Link
            href="/carret"
            className={`relative w-11 h-11 flex items-center justify-center transition-colors ${recordstore ? (dark ? 'text-white/70 hover:text-white' : 'text-black/70 hover:text-black') : 'text-zinc-500 hover:text-zinc-900'}`}
          >
            <ShoppingBag size={20} />
            {itemCount > 0 && (
              <span className={`absolute top-1.5 right-1.5 text-[9px] font-bold rounded-full min-w-[16px] h-4 flex items-center justify-center px-0.5 ${recordstore ? (dark ? 'bg-white text-black' : 'bg-black text-white') : 'bg-zinc-900 text-white'}`}>
                {itemCount > 9 ? '9+' : itemCount}
              </span>
            )}
          </Link>

          {/* User */}
          {user ? (
            <div className="relative">
              <button
                onClick={() => setUserMenu(v => !v)}
                className={`flex items-center gap-1.5 h-11 px-2 -mr-2 transition-colors ${recordstore ? (dark ? 'text-white/70 hover:text-white' : 'text-black/70 hover:text-black') : 'text-zinc-500 hover:text-zinc-900'}`}
              >
                <User size={20} />
                <span className="hidden md:block text-xs max-w-[100px] truncate">
                  {user.name || user.email.split('@')[0]}
                </span>
              </button>
              {userMenu && (
                <div className="absolute right-0 top-full mt-2 w-48 bg-white rounded-xl shadow-[0_8px_32px_-8px_rgba(15,23,42,0.16)] py-1 text-zinc-700 text-sm z-50">
                  <div className="px-3 py-2 border-b border-zinc-100 text-xs text-zinc-400 truncate">
                    {user.email}
                  </div>
                  <Link
                    href="/compte"
                    onClick={() => setUserMenu(false)}
                    className="flex items-center gap-2 px-3 py-2 hover:bg-zinc-50 transition-colors"
                  >
                    <User size={14} /> {t('myAccount')}
                  </Link>
                  <Link
                    href="/compte/comandes"
                    onClick={() => setUserMenu(false)}
                    className="flex items-center gap-2 px-3 py-2 hover:bg-zinc-50 transition-colors"
                  >
                    {t('myOrders')}
                  </Link>
                  {user.role === 'admin' && (
                    <NextLink
                      href="/admin"
                      onClick={() => setUserMenu(false)}
                      className="flex items-center gap-2 px-3 py-2 hover:bg-zinc-50 transition-colors border-t border-zinc-100"
                    >
                      <LayoutDashboard size={14} /> {t('adminPanel')}
                    </NextLink>
                  )}
                  <button
                    onClick={() => { logout(); setUserMenu(false); }}
                    className="flex items-center gap-2 w-full px-3 py-2 hover:bg-zinc-50 transition-colors text-red-500"
                  >
                    <LogOut size={14} /> {t('logout')}
                  </button>
                </div>
              )}
            </div>
          ) : (
            <Link
              href="/login"
              className={`hidden md:flex items-center gap-1.5 text-xs transition-colors p-1 ${recordstore ? (dark ? 'text-white/70 hover:text-white' : 'text-black/70 hover:text-black') : 'text-zinc-500 hover:text-zinc-900'}`}
            >
              <User size={18} /> {t('login')}
            </Link>
          )}

          {/* Mobile menu */}
          <button
            className={`md:hidden w-11 h-11 -mr-2 flex items-center justify-center ${recordstore ? (dark ? 'text-white/70 hover:text-white' : 'text-black/70 hover:text-black') : 'text-zinc-500 hover:text-zinc-900'}`}
            onClick={() => setOpen(v => !v)}
          >
            {open ? <X size={20} /> : <Menu size={20} />}
          </button>
        </div>
      </div>

      {open && (
        <div className={`md:hidden border-t py-4 px-4 flex flex-col gap-0.5 animate-fade-in ${recordstore ? `uppercase tracking-wide ${dark ? 'border-white/20' : 'border-black/10'}` : 'border-zinc-200'}`}>
          {links.map(({ href, label }) => (
            <Link
              key={href}
              href={href}
              onClick={() => setOpen(false)}
              className={recordstore
                ? `py-2.5 px-2 text-sm transition-colors ${dark ? 'text-white/80 hover:text-white' : 'text-black/70 hover:text-black'}`
                : 'py-2.5 px-2 text-sm text-zinc-600 hover:text-zinc-900 rounded-lg hover:bg-zinc-50 transition-colors'}
            >
              {label}
            </Link>
          ))}
          <div className={`border-t mt-2 pt-2 pb-2 ${recordstore ? (dark ? 'border-white/20' : 'border-black/10') : 'border-zinc-200'}`}>
            <LanguageSwitcher dark={dark} />
          </div>
          <div className={`border-t mt-2 pt-2 ${recordstore ? (dark ? 'border-white/20' : 'border-black/10') : 'border-zinc-200'}`}>
            {user ? (
              <>
                <Link href="/compte" onClick={() => setOpen(false)} className={recordstore ? `py-2.5 px-2 text-sm transition-colors block ${dark ? 'text-white/80 hover:text-white' : 'text-black/70 hover:text-black'}` : 'py-2.5 px-2 text-sm text-zinc-600 hover:text-zinc-900 rounded-lg hover:bg-zinc-50 transition-colors block'}>
                  {t('myAccount')}
                </Link>
                {user.role === 'admin' && (
                  <NextLink href="/admin" onClick={() => setOpen(false)} className={recordstore ? `py-2.5 px-2 text-sm transition-colors flex items-center gap-2 ${dark ? 'text-white/80 hover:text-white' : 'text-black/70 hover:text-black'}` : 'py-2.5 px-2 text-sm text-zinc-600 hover:text-zinc-900 rounded-lg hover:bg-zinc-50 transition-colors flex items-center gap-2'}>
                    <LayoutDashboard size={14} /> {t('adminPanel')}
                  </NextLink>
                )}
                <button onClick={() => { logout(); setOpen(false); }} className="py-2.5 px-2 text-sm text-red-500 rounded-lg hover:bg-zinc-50 transition-colors w-full text-left">
                  {t('logout')}
                </button>
              </>
            ) : (
              <Link href="/login" onClick={() => setOpen(false)} className={recordstore ? `py-2.5 px-2 text-sm transition-colors block ${dark ? 'text-white/80 hover:text-white' : 'text-black/70 hover:text-black'}` : 'py-2.5 px-2 text-sm text-zinc-600 hover:text-zinc-900 rounded-lg hover:bg-zinc-50 transition-colors block'}>
                {t('loginRegister')}
              </Link>
            )}
          </div>
        </div>
      )}
    </header>
  );
}
