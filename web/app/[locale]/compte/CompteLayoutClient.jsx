'use client';

import { useEffect } from 'react';
import { useRouter, usePathname } from '../../../i18n/navigation';
import { Link } from '../../../i18n/navigation';
import { useTranslations } from 'next-intl';
import { User, ShoppingBag, Settings, MapPin, LogOut, Bell, Music2, Repeat } from 'lucide-react';
import { useAuth } from '../../../components/store/AuthProvider';
import { useSpotifyEnabled } from '../../../components/store/useSpotifyEnabled';
import { useSubscripcionsActives } from '../../../components/store/useSubscripcionsActives';
import StorefrontNav from '../../../components/store/StorefrontNav';
import StorefrontFooter from '../../../components/store/StorefrontFooter';

export default function CompteLayoutClient({ children }) {
  const t = useTranslations('compte');
  const NAV = [
    { href: '/compte', label: t('overview'), icon: User, exact: true },
    { href: '/compte/comandes', label: t('orders'), icon: ShoppingBag },
    { href: '/compte/subscripcio', label: t('subscription'), icon: Repeat, subscripcions: true },
    { href: '/compte/peticions', label: t('requests'), icon: Bell },
    { href: '/compte/artistes', label: t('artists'), icon: Music2, spotify: true },
    { href: '/compte/adreces', label: t('addresses'), icon: MapPin },
    { href: '/compte/perfil', label: t('profile'), icon: Settings },
  ];
  const { user, loading, logout } = useAuth();
  const spotifyEnabled = useSpotifyEnabled();
  const subscripcionsActives = useSubscripcionsActives();
  const nav = NAV.filter(item => !item.spotify || spotifyEnabled)
    .filter(item => !item.subscripcions || subscripcionsActives);
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (!loading && !user) router.replace('/login');
  }, [user, loading]);

  if (loading || !user) {
    return (
      <>
        <StorefrontNav />
        <main className="flex-1 flex items-center justify-center py-20">
          <div className="w-6 h-6 border-2 border-zinc-900 border-t-transparent rounded-full animate-spin" />
        </main>
      </>
    );
  }

  return (
    <>
      <StorefrontNav />
      <main className="flex-1 container py-8 md:py-12">
        <div className="flex gap-8 items-start">
          {/* Sidebar */}
          <aside className="hidden md:block w-52 shrink-0">
            <div className="bg-white rounded-xl shadow-[0_2px_20px_-6px_rgba(15,23,42,0.08)] overflow-hidden">
              <div className="px-4 py-4 border-b border-zinc-50">
                <p className="font-medium text-sm truncate">{user.nombre || t('user')}</p>
                <p className="text-xs text-zinc-400 truncate">{user.email}</p>
              </div>
              <nav className="p-2">
                {nav.map(({ href, label, icon: Icon, exact }) => {
                  const active = exact ? pathname === href : pathname.startsWith(href);
                  return (
                    <Link
                      key={href}
                      href={href}
                      className={`flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-colors ${
                        active ? 'bg-zinc-100 text-zinc-900 font-medium' : 'text-zinc-600 hover:bg-zinc-50'
                      }`}
                    >
                      <Icon size={15} />
                      {label}
                    </Link>
                  );
                })}
                <button
                  onClick={logout}
                  className="flex items-center gap-2.5 w-full px-3 py-2 rounded-lg text-sm text-zinc-400 hover:bg-zinc-50 hover:text-red-500 transition-colors mt-1"
                >
                  <LogOut size={15} /> {t('logout')}
                </button>
              </nav>
            </div>
          </aside>

          {/* Mobile nav */}
          <div className="md:hidden w-full mb-4 overflow-x-auto">
            <div className="flex gap-2 pb-1">
              {nav.map(({ href, label, icon: Icon, exact }) => {
                const active = exact ? pathname === href : pathname.startsWith(href);
                return (
                  <Link
                    key={href}
                    href={href}
                    className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm whitespace-nowrap transition-colors ${
                      active ? 'bg-zinc-900 text-white font-medium' : 'border border-zinc-200 text-zinc-600'
                    }`}
                  >
                    <Icon size={13} /> {label}
                  </Link>
                );
              })}
            </div>
          </div>

          {/* Content */}
          <div className="flex-1 min-w-0">
            {children}
          </div>
        </div>
      </main>
      <StorefrontFooter />
    </>
  );
}
