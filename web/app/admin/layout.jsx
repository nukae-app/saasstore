'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  LayoutDashboard, Disc3, ShoppingCart, PackagePlus, Store, Users,
  LogOut, Menu, X, Globe, FileText, CalendarDays, Layers,
  Receipt, Landmark, TrendingUp, Calculator, Tag, Mail, Bell, Home,
  Settings, Repeat,
} from 'lucide-react';
import { clearToken as clearAdminToken } from '../lib/auth';
import { useAuth } from '../../components/store/AuthProvider';
import { TranslationProvider, useT, useLang } from '../lib/i18n';

const NAV_GROUPS = [
  {
    label: null,
    items: [
      { href: '/admin', key: 'nav.dashboard', label: 'Dashboard', icon: LayoutDashboard, exact: true },
    ],
  },
  {
    label: 'Catàleg',
    items: [
      { href: '/admin/catalogo',     key: 'nav.catalog',      label: 'Discos',          icon: Disc3 },
      { href: '/admin/etiquetes',    key: 'nav.etiquetes',    label: 'Etiquetes',       icon: Tag },
      { href: '/admin/vendes-web',   key: 'nav.orders',       label: 'Vendes web',      icon: ShoppingCart },
    ],
  },
  {
    label: 'ERP',
    items: [
      { href: '/admin/compras',   key: 'nav.purchases', label: 'Compres',   icon: PackagePlus },
      { href: '/admin/tpv',       key: 'nav.tpv',       label: 'TPV',       icon: Store },
      { href: '/admin/peticions', key: 'nav.peticions', label: 'Peticions', icon: Bell },
      { href: '/admin/subscripcions', key: 'nav.subscripcions', label: 'Club del disc', icon: Repeat },
    ],
  },
  {
    label: 'Comptabilitat',
    items: [
      { href: '/admin/despeses', key: 'nav.despeses', label: 'Despeses',  icon: Receipt },
      { href: '/admin/banc',     key: 'nav.banc',     label: 'Banc',      icon: Landmark },
      { href: '/admin/resultat', key: 'nav.resultat', label: 'Resultat',  icon: TrendingUp },
      { href: '/admin/iva',      key: 'nav.iva',      label: 'IVA',       icon: Calculator },
    ],
  },
  {
    label: 'CMS',
    items: [
      { href: '/admin/pagines',    key: 'nav.pagines',    label: 'Pàgines',    icon: Layers },
      { href: '/admin/blog',       key: 'nav.blog',       label: 'Blog',       icon: FileText },
      { href: '/admin/agenda',     key: 'nav.agenda',     label: 'Agenda',     icon: CalendarDays },
      { href: '/admin/newsletter', key: 'nav.newsletter', label: 'Newsletter', icon: Mail },
    ],
  },
  {
    label: 'Admin',
    items: [
      { href: '/admin/usuaris',       key: 'nav.users',         label: 'Usuaris',       icon: Users },
      { href: '/admin/configuracio',  key: 'nav.configuracio',  label: 'Configuració',  icon: Settings },
    ],
  },
];

// Llista plana per a cerques (breadcrumb topbar, etc.)
const NAV = NAV_GROUPS.flatMap(g => g.items);

const LANGS = [
  { code: 'ca', label: 'CAT' },
  { code: 'es', label: 'ESP' },
  { code: 'en', label: 'ENG' },
];

export default function AdminLayout({ children }) {
  return (
    <TranslationProvider>
      <AdminShell>{children}</AdminShell>
    </TranslationProvider>
  );
}

function AdminShell({ children }) {
  const pathname = usePathname();
  const t = useT();
  const { lang, setLang } = useLang();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const devBypass = process.env.NEXT_PUBLIC_DEV_ADMIN_BYPASS === 'true';
  const { user: sessionUser, loading, logout: sessionLogout } = useAuth();

  // Tanca el drawer mòbil en canviar de pàgina.
  useEffect(() => { setMobileOpen(false); }, [pathname]);

  // Mateixa sessió que la botiga: si ja has entrat a la web com a admin, no
  // cal tornar a fer login aquí. dev_admin_bypass es manté per a proves
  // locals sense haver de crear cap usuari.
  const user = devBypass ? { email: 'dev@admin.local', nombre: 'Dev Admin', rol: 'admin' } : sessionUser;

  function logout() {
    clearAdminToken();
    sessionLogout();
  }

  if (!devBypass && loading) {
    return (
      <div className="min-h-screen bg-zinc-900 flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-white border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!user) {
    return (
      <div className="min-h-screen bg-zinc-900 flex items-center justify-center p-4">
        <div className="bg-white rounded-2xl shadow-2xl w-full max-w-sm p-8 text-center">
          <div className="text-4xl mb-3">💿</div>
          <h1 className="text-xl font-bold text-zinc-900 mb-1">Ultra-Local Admin</h1>
          <p className="text-sm text-zinc-500 mb-6">Cal iniciar sessió per accedir al panell.</p>
          <Link
            href="/login"
            className="inline-flex items-center justify-center w-full bg-primary hover:bg-zinc-800 text-white px-5 py-2.5 rounded-lg text-sm font-medium transition-colors"
          >
            Anar al login
          </Link>
        </div>
      </div>
    );
  }

  if (user.rol !== 'admin') {
    return (
      <div className="min-h-screen bg-zinc-900 flex items-center justify-center p-4">
        <div className="bg-white rounded-2xl shadow-2xl w-full max-w-sm p-8 text-center">
          <h1 className="text-xl font-bold text-zinc-900 mb-1">Sense accés</h1>
          <p className="text-sm text-zinc-500 mb-6">Aquest compte no té permisos d&apos;administració.</p>
          <Link
            href="/"
            className="inline-flex items-center justify-center w-full border border-zinc-200 text-zinc-600 px-5 py-2.5 rounded-lg text-sm font-medium hover:bg-zinc-50 transition-colors"
          >
            Tornar a la web
          </Link>
        </div>
      </div>
    );
  }

  const currentSection = NAV.find(n => n.exact ? pathname === n.href : pathname.startsWith(n.href));
  const currentLabel = currentSection ? t(currentSection.key, currentSection.label) : 'Admin';

  const showLabels = !collapsed || mobileOpen;

  return (
    <div className="flex h-screen bg-gray-50 overflow-hidden">
      {/* Mobile backdrop */}
      {mobileOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-30 md:hidden"
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`fixed md:static inset-y-0 left-0 z-40 w-64 ${collapsed ? 'md:w-16' : 'md:w-56'} flex flex-col bg-zinc-900 shrink-0 transform transition-transform md:transition-[width] duration-200 ${mobileOpen ? 'translate-x-0' : '-translate-x-full'} md:translate-x-0`}
      >
        {/* Brand */}
        <div className="flex items-center justify-between h-14 px-4 border-b border-zinc-800 shrink-0">
          {showLabels && (
            <span className="font-bold text-white text-sm tracking-wide">UL Records</span>
          )}
          <button onClick={() => setCollapsed(!collapsed)} className="hidden md:block text-zinc-500 hover:text-white p-1 rounded ml-auto">
            {collapsed ? <Menu size={18} /> : <X size={18} />}
          </button>
          <button onClick={() => setMobileOpen(false)} className="md:hidden text-zinc-500 hover:text-white p-1 rounded ml-auto">
            <X size={18} />
          </button>
        </div>

        {/* Nav */}
        <nav className="flex-1 py-3 px-2 overflow-y-auto space-y-4">
          {NAV_GROUPS.map((group, gi) => (
            <div key={gi}>
              {group.label && showLabels && (
                <p className="text-[10px] font-bold text-zinc-600 uppercase tracking-widest px-3 mb-1">
                  {group.label}
                </p>
              )}
              {group.label && !showLabels && gi > 0 && (
                <div className="border-t border-zinc-800 mb-1 mx-2" />
              )}
              <div className="space-y-0.5">
                {group.items.map(({ href, key, label: fallbackLabel, icon: Icon, exact }) => {
                  const active = exact ? pathname === href : pathname.startsWith(href);
                  const label = t(key, fallbackLabel);
                  return (
                    <Link
                      key={href}
                      href={href}
                      title={collapsed && !mobileOpen ? label : undefined}
                      className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
                        active
                          ? 'bg-zinc-800 text-white font-medium'
                          : 'text-zinc-400 hover:text-white hover:bg-zinc-800'
                      }`}
                    >
                      <Icon size={16} className="shrink-0" />
                      {showLabels && <span>{label}</span>}
                    </Link>
                  );
                })}
              </div>
            </div>
          ))}
        </nav>

        {/* User + logout */}
        <div className="p-2 border-t border-zinc-800 shrink-0">
          {showLabels && (
            <div className="px-3 py-1 text-xs text-zinc-500 truncate mb-1">{user.email}</div>
          )}
          <button
            onClick={logout}
            title={collapsed && !mobileOpen ? t('nav.logout') : undefined}
            className="flex items-center gap-3 w-full px-3 py-2 rounded-lg text-sm text-zinc-500 hover:text-white hover:bg-zinc-800 transition-colors"
          >
            <LogOut size={18} className="shrink-0" />
            {showLabels && <span>{t('nav.logout')}</span>}
          </button>
        </div>
      </aside>

      {/* Content */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Topbar */}
        <header className="h-14 bg-white border-b border-zinc-200 flex items-center justify-between px-3 sm:px-6 gap-2 shrink-0">
          <div className="flex items-center gap-2 min-w-0">
            <button
              onClick={() => setMobileOpen(true)}
              className="md:hidden text-zinc-500 hover:text-zinc-800 p-1 -ml-1 shrink-0"
            >
              <Menu size={20} />
            </button>
            <h1 className="text-sm font-semibold text-zinc-700 truncate">{currentLabel}</h1>
          </div>
          <div className="flex items-center gap-2 sm:gap-3 shrink-0">
            {/* Language switcher */}
            <div className="flex items-center gap-1 bg-zinc-100 rounded-lg p-0.5">
              <Globe size={13} className="hidden sm:block text-zinc-400 ml-1.5" />
              {LANGS.map(({ code, label }) => (
                <button
                  key={code}
                  onClick={() => setLang(code)}
                  className={`px-1.5 sm:px-2 py-1 rounded text-xs font-semibold transition-colors ${
                    lang === code
                      ? 'bg-white text-zinc-900 shadow-sm'
                      : 'text-zinc-500 hover:text-zinc-800'
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
            <Link
              href="/"
              className="flex items-center gap-1.5 text-xs font-medium text-zinc-500 hover:text-zinc-800 border border-zinc-200 rounded-lg px-2 sm:px-2.5 py-1.5 transition-colors"
            >
              <Home size={13} /> <span className="hidden sm:inline">Web</span>
            </Link>
            <span className="hidden lg:inline text-xs text-zinc-400">{user.nombre ?? user.email}</span>
          </div>
        </header>

        <main className="flex-1 overflow-y-auto overflow-x-hidden p-3 sm:p-6">
          {children}
        </main>
      </div>
    </div>
  );
}
