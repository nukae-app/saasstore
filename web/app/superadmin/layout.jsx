'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { Building2, LogOut, ScrollText, Layers, UserCog, LayoutDashboard, CreditCard, Landmark } from 'lucide-react';
import { getToken, clearToken, superadminAuthFetch } from '../lib/superadmin-auth';

const ROLE_LABEL = { owner: 'Owner', support: 'Support (només lectura)' };

export default function SuperadminLayout({ children }) {
  const pathname = usePathname();
  const router = useRouter();
  const [ready, setReady] = useState(false);
  const [authed, setAuthed] = useState(false);
  const [me, setMe] = useState(null);

  const loadMe = useCallback(async () => {
    const res = await superadminAuthFetch('/superadmin/me');
    if (res.ok) setMe(await res.json());
  }, []);

  useEffect(() => {
    // Recomprova en cada canvi de ruta, no només al muntar: el login fa
    // un router.replace() dins del mateix layout ja muntat (navegació
    // client-side, sense recàrrega), així que sense `pathname` a les deps
    // l'estat `authed` es quedaria congelat amb el valor d'abans d'entrar.
    const isAuthed = !!getToken();
    setAuthed(isAuthed);
    setReady(true);
    if (isAuthed) loadMe();
  }, [pathname, loadMe]);

  // La página de login no lleva shell ni gate — se muestra siempre.
  if (pathname === '/superadmin/login') return children;

  if (!ready) return null;

  if (!authed) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center p-4">
        <div className="bg-white rounded-2xl shadow-2xl w-full max-w-sm p-8 text-center">
          <Building2 className="mx-auto mb-3 text-slate-700" size={32} />
          <h1 className="text-xl font-bold text-slate-900 mb-1">Panell de plataforma</h1>
          <p className="text-sm text-slate-500 mb-6">Cal iniciar sessió per accedir-hi.</p>
          <Link
            href="/superadmin/login"
            className="inline-flex items-center justify-center w-full bg-slate-900 hover:bg-slate-800 text-white px-5 py-2.5 rounded-lg text-sm font-medium transition-colors"
          >
            Anar al login
          </Link>
        </div>
      </div>
    );
  }

  function logout() {
    clearToken();
    router.replace('/superadmin/login');
  }

  return (
    <div className="flex h-screen bg-slate-50 overflow-hidden">
      <aside className="w-56 flex flex-col bg-slate-950 shrink-0">
        <div className="flex items-center gap-2 h-14 px-4 border-b border-slate-800 shrink-0">
          <Building2 size={18} className="text-indigo-400" />
          <span className="font-bold text-white text-sm tracking-wide">Panell de plataforma</span>
        </div>
        <nav className="flex-1 py-3 px-2 space-y-1">
          <Link
            href="/superadmin"
            className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
              pathname === '/superadmin' || pathname.startsWith('/superadmin/tenants')
                ? 'bg-slate-800 text-white font-medium'
                : 'text-slate-400 hover:text-white hover:bg-slate-800'
            }`}
          >
            Tenants
          </Link>
          <Link
            href="/superadmin/dashboard"
            className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
              pathname === '/superadmin/dashboard'
                ? 'bg-slate-800 text-white font-medium'
                : 'text-slate-400 hover:text-white hover:bg-slate-800'
            }`}
          >
            <LayoutDashboard size={16} className="shrink-0" /> Dashboard
          </Link>
          <Link
            href="/superadmin/plans"
            className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
              pathname === '/superadmin/plans'
                ? 'bg-slate-800 text-white font-medium'
                : 'text-slate-400 hover:text-white hover:bg-slate-800'
            }`}
          >
            <CreditCard size={16} className="shrink-0" /> Plans
          </Link>
          <Link
            href="/superadmin/banc"
            className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
              pathname === '/superadmin/banc'
                ? 'bg-slate-800 text-white font-medium'
                : 'text-slate-400 hover:text-white hover:bg-slate-800'
            }`}
          >
            <Landmark size={16} className="shrink-0" /> Banc
          </Link>
          <Link
            href="/superadmin/verticals"
            className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
              pathname === '/superadmin/verticals'
                ? 'bg-slate-800 text-white font-medium'
                : 'text-slate-400 hover:text-white hover:bg-slate-800'
            }`}
          >
            <Layers size={16} className="shrink-0" /> Verticals
          </Link>
          <Link
            href="/superadmin/admins"
            className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
              pathname === '/superadmin/admins'
                ? 'bg-slate-800 text-white font-medium'
                : 'text-slate-400 hover:text-white hover:bg-slate-800'
            }`}
          >
            <UserCog size={16} className="shrink-0" /> Operadors
          </Link>
          <Link
            href="/superadmin/audit"
            className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
              pathname === '/superadmin/audit'
                ? 'bg-slate-800 text-white font-medium'
                : 'text-slate-400 hover:text-white hover:bg-slate-800'
            }`}
          >
            <ScrollText size={16} className="shrink-0" /> Audit log
          </Link>
        </nav>
        {me && (
          <div className="px-4 py-2 border-t border-slate-800 shrink-0">
            <p className="text-xs text-slate-500 truncate">{me.email}</p>
            <p className="text-xs text-indigo-400 font-medium">{ROLE_LABEL[me.role] ?? me.role}</p>
          </div>
        )}
        <div className="p-2 border-t border-slate-800 shrink-0">
          <button
            onClick={logout}
            className="flex items-center gap-3 w-full px-3 py-2 rounded-lg text-sm text-slate-500 hover:text-white hover:bg-slate-800 transition-colors"
          >
            <LogOut size={16} className="shrink-0" /> Sortir
          </button>
        </div>
      </aside>
      <div className="flex-1 flex flex-col min-w-0">
        <header className="h-14 bg-white border-b border-slate-200 flex items-center px-6 shrink-0">
          <h1 className="text-sm font-semibold text-slate-700">Operador de plataforma</h1>
        </header>
        <main className="flex-1 overflow-y-auto p-6">{children}</main>
      </div>
    </div>
  );
}
