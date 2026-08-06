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
  const pathname = usePathname();
  const links = subscripcionsActives ? [...navLinks, { href: '/subscripcio', label: t('club') }] : navLinks;

  useEffect(() => {
    fetch('/api/pagines')
      .then(r => r.ok ? r.json() : null)
      .then(pagines => {
        if (!pagines?.length) return;
        const links = [
          { href: '/cataleg', label: t('catalog') },
          ...pagines.map(p => ({ href: `/${p.slug}`, label: p.nom })),
        ];
        setNavLinks(links);
      })
      .catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <header className="sticky top-0 z-40 bg-white/90 backdrop-blur-md border-b border-zinc-200 text-zinc-900">
      {manteniment && (
        <div className="bg-amber-500 text-white text-xs md:text-sm text-center py-2 px-4">
          {t('maintenanceBanner')}
        </div>
      )}
      <div className="container flex items-center h-16 gap-8">
        <Link href="/" className="shrink-0 opacity-90 hover:opacity-100 transition-opacity">
          <img src="/logo.png" alt="Ultra-Local Records" className="h-8 md:h-10 w-auto invert" />
        </Link>

        <nav className="hidden md:flex items-center gap-6 text-sm text-zinc-500 flex-1">
          {links.map(({ href, label }) => (
            <Link
              key={href}
              href={href}
              className={`hover:text-zinc-900 transition-colors ${pathname.startsWith(href) ? 'text-zinc-900 font-medium' : ''}`}
            >
              {label}
            </Link>
          ))}
        </nav>

        <div className="flex items-center gap-3 ml-auto md:ml-0">
          <LanguageSwitcher className="hidden md:flex" />

          {/* Cart */}
          <Link href="/carret" className="relative w-11 h-11 flex items-center justify-center text-zinc-500 hover:text-zinc-900 transition-colors">
            <ShoppingBag size={20} />
            {itemCount > 0 && (
              <span className="absolute top-1.5 right-1.5 bg-zinc-900 text-white text-[9px] font-bold rounded-full min-w-[16px] h-4 flex items-center justify-center px-0.5">
                {itemCount > 9 ? '9+' : itemCount}
              </span>
            )}
          </Link>

          {/* User */}
          {user ? (
            <div className="relative">
              <button
                onClick={() => setUserMenu(v => !v)}
                className="flex items-center gap-1.5 h-11 px-2 -mr-2 text-zinc-500 hover:text-zinc-900 transition-colors"
              >
                <User size={20} />
                <span className="hidden md:block text-xs max-w-[100px] truncate">
                  {user.nombre || user.email.split('@')[0]}
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
                  {user.rol === 'admin' && (
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
              className="hidden md:flex items-center gap-1.5 text-xs text-zinc-500 hover:text-zinc-900 transition-colors p-1"
            >
              <User size={18} /> {t('login')}
            </Link>
          )}

          {/* Mobile menu */}
          <button
            className="md:hidden w-11 h-11 -mr-2 flex items-center justify-center text-zinc-500 hover:text-zinc-900"
            onClick={() => setOpen(v => !v)}
          >
            {open ? <X size={20} /> : <Menu size={20} />}
          </button>
        </div>
      </div>

      {open && (
        <div className="md:hidden border-t border-zinc-200 py-4 px-4 flex flex-col gap-0.5 animate-fade-in">
          {links.map(({ href, label }) => (
            <Link
              key={href}
              href={href}
              onClick={() => setOpen(false)}
              className="py-2.5 px-2 text-sm text-zinc-600 hover:text-zinc-900 rounded-lg hover:bg-zinc-50 transition-colors"
            >
              {label}
            </Link>
          ))}
          <div className="border-t border-zinc-200 mt-2 pt-2 pb-2">
            <LanguageSwitcher />
          </div>
          <div className="border-t border-zinc-200 mt-2 pt-2">
            {user ? (
              <>
                <Link href="/compte" onClick={() => setOpen(false)} className="py-2.5 px-2 text-sm text-zinc-600 hover:text-zinc-900 rounded-lg hover:bg-zinc-50 transition-colors block">
                  {t('myAccount')}
                </Link>
                {user.rol === 'admin' && (
                  <NextLink href="/admin" onClick={() => setOpen(false)} className="py-2.5 px-2 text-sm text-zinc-600 hover:text-zinc-900 rounded-lg hover:bg-zinc-50 transition-colors flex items-center gap-2">
                    <LayoutDashboard size={14} /> {t('adminPanel')}
                  </NextLink>
                )}
                <button onClick={() => { logout(); setOpen(false); }} className="py-2.5 px-2 text-sm text-red-500 rounded-lg hover:bg-zinc-50 transition-colors w-full text-left">
                  {t('logout')}
                </button>
              </>
            ) : (
              <Link href="/login" onClick={() => setOpen(false)} className="py-2.5 px-2 text-sm text-zinc-600 hover:text-zinc-900 rounded-lg hover:bg-zinc-50 transition-colors block">
                {t('loginRegister')}
              </Link>
            )}
          </div>
        </div>
      )}
    </header>
  );
}
