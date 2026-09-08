'use client';

import { useState, useEffect, useMemo } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { clearToken as clearAdminToken } from '../lib/auth';
import { useAuth } from '../../components/store/AuthProvider';
import { useTenantConfig } from '../../components/store/useTenantConfig';
import { TranslationProvider, useT, useLang } from '../lib/i18n';
import MIcon from '../../components/ui/m-icon';

// Function del `config` complet (/config/public) en lloc d'array estàtic:
// l'etiqueta de fallback del catàleg varia per vertical (la traducció real
// de `nav.catalog` ja és genèrica — "Catàleg"/"Catálogo" — així que això
// només afecta el text abans que les traduccions carreguin). Un ítem pot
// declarar `requiresFeature: '<camp de ConfiguracioBotigaPublic>'` — es
// filtra si aquell camp és estrictament `false`; mentre `config` encara no
// s'ha resolt (`undefined`) es mostra, per no parpellejar. Un vertical nou
// que necessiti amagar/mostrar seccions senceres ho fa amb el mateix
// mecanisme, sense afegir un altre spread condicional a mà com abans.
function getNavGroups(config) {
  const vertical = config.vertical;
  const groups = [
    {
      label: null,
      items: [
        { href: '/admin', key: 'nav.dashboard', label: 'Dashboard', icon: 'space_dashboard', exact: true },
      ],
    },
    {
      label: 'Catàleg',
      items: [
        {
          href: '/admin/catalogo', key: 'nav.catalog',
          label: vertical === 'floristry' ? 'Productes' : 'Discos', icon: 'album',
        },
        { href: '/admin/etiquetes',    key: 'nav.etiquetes',    label: 'Etiquetes',       icon: 'sell' },
        { href: '/admin/ofertes',      key: 'nav.ofertes',      label: 'Ofertes',         icon: 'local_offer' },
        { href: '/admin/cupons',       key: 'nav.cupons',       label: 'Cupons',          icon: 'confirmation_number' },
        { href: '/admin/vendes-web',   key: 'nav.orders',       label: 'Vendes web',      icon: 'shopping_bag' },
      ],
    },
    {
      label: 'ERP',
      items: [
        { href: '/admin/tpv',       key: 'nav.tpv',       label: 'TPV',       icon: 'point_of_sale' },
        { href: '/admin/peticions', key: 'nav.peticions', label: 'Peticions', icon: 'inbox' },
        {
          href: '/admin/subscripcions', key: 'nav.subscripcions', label: 'Club del disc', icon: 'loyalty',
          requiresFeature: 'subscripcions_actives',
        },
      ],
    },
    {
      label: 'Compres',
      collapsible: true,
      items: [
        { href: '/admin/compras', key: 'nav.purchases', label: 'Compres', icon: 'shopping_cart', exact: true },
        { href: '/admin/compras/solicituds',  key: 'nav.compres_solicituds',  label: 'Sol·licituds',        icon: 'pending_actions' },
        { href: '/admin/compras/comandes',    key: 'nav.compres_comandes',    label: 'Comandes',             icon: 'local_shipping' },
        { href: '/admin/compras/particulars', key: 'nav.compres_particulars', label: 'Compres particulars',  icon: 'person_search' },
        { href: '/admin/compras/historial',   key: 'nav.compres_historial',   label: 'Historial',            icon: 'history' },
        { href: '/admin/compras/proveidors',  key: 'nav.compres_proveidors',  label: 'Proveïdors',           icon: 'factory' },
      ],
    },
    {
      label: 'Comptabilitat',
      collapsible: true,
      items: [
        { href: '/admin/comptabilitat', key: 'nav.comptabilitat_resum', label: 'Resum', icon: 'calculate', exact: true },
        { href: '/admin/pressupostos', key: 'nav.pressupostos', label: 'Pressupostos', icon: 'request_quote' },
        { href: '/admin/albarans',    key: 'nav.albarans',    label: 'Albarans',      icon: 'receipt_long' },
        { href: '/admin/factures',    key: 'nav.factures',    label: 'Factures',      icon: 'description' },
        { href: '/admin/despeses',    key: 'nav.despeses',    label: 'Despeses',      icon: 'payments' },
        { href: '/admin/banc',        key: 'nav.banc',        label: 'Banc',          icon: 'account_balance' },
        { href: '/admin/proveidors',  key: 'nav.proveidors',  label: 'Proveïdors',    icon: 'factory' },
        { href: '/admin/resultat',    key: 'nav.resultat',    label: 'Resultat',      icon: 'trending_up' },
        { href: '/admin/flux-caixa',  key: 'nav.flux_caixa',  label: 'Flux de caixa', icon: 'show_chart' },
        { href: '/admin/iva',         key: 'nav.iva',         label: 'IVA',           icon: 'calculate' },
        { href: '/admin/models-fiscals', key: 'nav.models_fiscals', label: 'Models AEAT', icon: 'gavel' },
        { href: '/admin/marges',      key: 'nav.marges',      label: 'Marges',        icon: 'percent' },
        { href: '/admin/pla-comptes', key: 'nav.pla_comptes', label: 'Pla de comptes', icon: 'menu_book' },
        { href: '/admin/actius',      key: 'nav.actius',      label: 'Actius',        icon: 'inventory_2' },
        { href: '/admin/llibres',     key: 'nav.llibres',     label: 'Llibres',       icon: 'auto_stories' },
        // Exportacions pendent — s'afegeix aquí quan es construeixi la seva pantalla.
      ],
    },
    {
      label: 'CMS',
      items: [
        { href: '/admin/disseny-web', key: 'nav.disseny_web', label: 'Disseny web', icon: 'palette' },
        { href: '/admin/pagines',    key: 'nav.pagines',    label: 'Pàgines',    icon: 'description' },
        { href: '/admin/blog',       key: 'nav.blog',       label: 'Blog',       icon: 'newspaper' },
        { href: '/admin/agenda',     key: 'nav.agenda',     label: 'Agenda',     icon: 'event' },
        { href: '/admin/newsletter', key: 'nav.newsletter', label: 'Newsletter', icon: 'mail' },
      ],
    },
    {
      label: 'Admin',
      items: [
        { href: '/admin/usuaris',       key: 'nav.users',         label: 'Usuaris',       icon: 'group' },
        { href: '/admin/configuracio',  key: 'nav.configuracio',  label: 'Configuració',  icon: 'settings' },
      ],
    },
  ];
  return groups.map((g) => ({
    ...g,
    items: g.items.filter((it) => !it.requiresFeature || config[it.requiresFeature] !== false),
  }));
}

const LANGS = [
  { code: 'ca', label: 'CAT' },
  { code: 'es', label: 'ESP' },
  { code: 'en', label: 'ENG' },
];

const VERTICAL_LABEL = { records: 'Discos', floristry: 'Floristeria' };

// Fonts pròpies de l'admin (Literata + Nunito Sans + Material Symbols): es
// carreguen només aquí (no a globals.css) perquè cap altra pantalla —
// storefront inclòs, que porta Bodoni Moda/Hanken Grotesk— les necessita.
// React 19 hi puja aquests <link> a <head> automàticament allà on es
// renderitzin.
function AdminHead() {
  return (
    <>
      <link href="https://fonts.googleapis.com/css2?family=Literata:ital,opsz,wght@0,7..72,400;0,7..72,600;0,7..72,700;1,7..72,400&family=Nunito+Sans:wght@400;500;600;700&display=swap" rel="stylesheet" />
      <link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,300..600,0..1,-25..0&display=swap" rel="stylesheet" />
    </>
  );
}

export default function AdminLayout({ children }) {
  return (
    <TranslationProvider>
      <AdminHead />
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
  const config = useTenantConfig();
  const NAV_GROUPS = useMemo(
    () => getNavGroups(config), [config]
  );
  const NAV = useMemo(() => NAV_GROUPS.flatMap(g => g.items), [NAV_GROUPS]);

  // Grups desplegables (avui només "Comptabilitat", que ha crescut prou per
  // no voler-lo sempre expandit): comença tancat, però s'obre sol quan la
  // pàgina activa hi és a dins — mai es tanca sol en navegar-hi fora, així
  // que un cop l'usuari el desplega a mà es queda obert per la resta de
  // sessió de navegació.
  const [openGroups, setOpenGroups] = useState({});
  useEffect(() => {
    setOpenGroups(prev => {
      const next = { ...prev };
      for (const g of NAV_GROUPS) {
        if (!g.collapsible) continue;
        const isActive = g.items.some(it => (it.exact ? pathname === it.href : pathname.startsWith(it.href)));
        if (isActive) next[g.label] = true;
      }
      return next;
    });
  }, [pathname, NAV_GROUPS]);

  // Tanca el drawer mòbil en canviar de pàgina.
  useEffect(() => { setMobileOpen(false); }, [pathname]);

  // Mateixa sessió que la botiga: si ja has entrat a la web com a admin, no
  // cal tornar a fer login aquí. dev_admin_bypass es manté per a proves
  // locals sense haver de crear cap usuari.
  const user = devBypass ? { email: 'dev@admin.local', nombre: 'Dev Admin', role: 'admin' } : sessionUser;

  function logout() {
    clearAdminToken();
    sessionLogout();
  }

  if (!devBypass && loading) {
    return (
      <div data-admin-theme="m3" className="min-h-screen bg-sidebar flex items-center justify-center">
        <AdminHead />
        <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!user) {
    return (
      <div data-admin-theme="m3" className="min-h-screen bg-sidebar flex items-center justify-center p-4">
        <AdminHead />
        <div className="bg-card rounded-2xl shadow-2xl w-full max-w-sm p-8 text-center">
          <h1 className="font-headline font-bold text-2xl text-on-surface mb-1">{config.nombre || 'Admin'}</h1>
          <p className="text-sm text-on-surface-variant mb-6">Cal iniciar sessió per accedir al panell.</p>
          <Link
            href="/login"
            className="inline-flex items-center justify-center w-full bg-primary hover:opacity-90 text-primary-foreground px-5 py-2.5 rounded-lg text-sm font-semibold transition-opacity"
          >
            Anar al login
          </Link>
        </div>
      </div>
    );
  }

  if (user.role !== 'admin') {
    return (
      <div data-admin-theme="m3" className="min-h-screen bg-sidebar flex items-center justify-center p-4">
        <AdminHead />
        <div className="bg-card rounded-2xl shadow-2xl w-full max-w-sm p-8 text-center">
          <h1 className="font-headline font-bold text-2xl text-on-surface mb-1">Sense accés</h1>
          <p className="text-sm text-on-surface-variant mb-6">Aquest compte no té permisos d&apos;administració.</p>
          <Link
            href="/"
            className="inline-flex items-center justify-center w-full border border-outline-variant text-on-surface-variant px-5 py-2.5 rounded-lg text-sm font-semibold hover:bg-surface-container-high transition-colors"
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
  const initials = (user.nombre || user.name || user.email || '?').trim().slice(0, 2).toUpperCase();

  return (
    <div data-admin-theme="m3" className="flex h-screen bg-surface overflow-hidden font-body text-on-surface">
      <AdminHead />
      {/* Mobile backdrop */}
      {mobileOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-30 md:hidden"
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`fixed md:static inset-y-0 left-0 z-40 w-72 ${collapsed ? 'md:w-16' : 'md:w-64'} flex flex-col bg-sidebar shrink-0 transform transition-transform md:transition-[width] duration-200 ${mobileOpen ? 'translate-x-0' : '-translate-x-full'} md:translate-x-0`}
      >
        {/* Brand */}
        <div className="flex items-center justify-between h-14 px-4 border-b border-white/10 shrink-0">
          {showLabels && (
            <div className="flex items-center gap-2.5 min-w-0">
              {config.logo_url ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={config.logo_url} alt={config.nombre} className="h-7 w-auto object-contain shrink-0" />
              ) : (
                <span className="w-7 h-7 rounded-lg bg-primary text-primary-foreground flex items-center justify-center shrink-0">
                  <MIcon name="storefront" size={16} />
                </span>
              )}
              <span className="font-headline font-bold text-sm text-white truncate">{config.nombre || 'Admin'}</span>
            </div>
          )}
          <button onClick={() => setCollapsed(!collapsed)} className="hidden md:block text-sidebar-foreground hover:text-white p-1 rounded-full ml-auto">
            <MIcon name={collapsed ? 'menu' : 'close'} size={18} />
          </button>
          <button onClick={() => setMobileOpen(false)} className="md:hidden text-sidebar-foreground hover:text-white p-1 rounded-full ml-auto">
            <MIcon name="close" size={18} />
          </button>
        </div>

        {/* Nav */}
        <nav className="flex-1 py-3 px-3 overflow-y-auto space-y-4">
          {NAV_GROUPS.map((group, gi) => {
            // Els grups desplegables només es pleguen amb el sidebar
            // expandit — en mode icona (showLabels=false) no té sentit
            // amagar-los, es mostren sempre plans com la resta.
            const isCollapsibleOpen = !group.collapsible || !showLabels || !!openGroups[group.label];
            return (
            <div key={gi}>
              {group.label && showLabels && group.collapsible && (
                <button
                  onClick={() => setOpenGroups(g => ({ ...g, [group.label]: !g[group.label] }))}
                  className="w-full flex items-center justify-between px-3 pb-1 pt-2 text-[11px] font-bold uppercase tracking-wider text-sidebar-muted hover:text-sidebar-foreground"
                >
                  {group.label}
                  <MIcon name="expand_more" size={14} className={`transition-transform ${isCollapsibleOpen ? '' : '-rotate-90'}`} />
                </button>
              )}
              {group.label && showLabels && !group.collapsible && (
                <p className="px-3 pb-1 pt-2 text-[11px] font-bold uppercase tracking-wider text-sidebar-muted">
                  {group.label}
                </p>
              )}
              {group.label && !showLabels && gi > 0 && (
                <div className="border-t border-white/10 mb-1 mx-2" />
              )}
              {isCollapsibleOpen && (
                <div className="space-y-0.5">
                  {group.items.map(({ href, key, label: fallbackLabel, icon, exact }) => {
                    const active = exact ? pathname === href : pathname.startsWith(href);
                    const label = t(key, fallbackLabel);
                    return (
                      <Link
                        key={href}
                        href={href}
                        title={collapsed && !mobileOpen ? label : undefined}
                        className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-all ${
                          active
                            ? 'bg-sidebar-active text-sidebar-active-foreground font-semibold shadow-[0_2px_8px_rgba(18,179,160,0.35)]'
                            : 'text-sidebar-foreground hover:bg-white/5 hover:text-white'
                        }`}
                      >
                        <MIcon name={icon} size={20} className="shrink-0" />
                        {showLabels && <span>{label}</span>}
                      </Link>
                    );
                  })}
                </div>
              )}
            </div>
            );
          })}
        </nav>

        {/* User + logout */}
        <div className="p-4 border-t border-white/10 shrink-0">
          <div className="flex items-center gap-2 mb-3 min-w-0">
            <div className="w-8 h-8 rounded-full bg-primary-container text-on-primary-container flex items-center justify-center font-bold text-xs shrink-0">
              {initials}
            </div>
            {showLabels && (
              <div className="min-w-0">
                <p className="text-xs font-semibold text-white truncate">{user.email}</p>
                <p className="text-[11px] text-sidebar-muted">Administrador</p>
              </div>
            )}
          </div>
          <button
            onClick={logout}
            title={collapsed && !mobileOpen ? t('nav.logout') : undefined}
            className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg bg-white/5 text-xs font-semibold text-sidebar-foreground hover:text-red-400 hover:bg-red-500/10 transition-all"
          >
            <MIcon name="logout" size={16} />
            {showLabels && <span>{t('nav.logout')}</span>}
          </button>
        </div>
      </aside>

      {/* Content */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Topbar */}
        <header className="h-14 bg-surface/85 backdrop-blur-md border-b border-outline-variant/40 flex items-center justify-between px-3 sm:px-6 gap-2 shrink-0">
          <div className="flex items-center gap-2 min-w-0">
            <button
              onClick={() => setMobileOpen(true)}
              className="md:hidden text-on-surface-variant hover:text-on-surface p-1 -ml-1 shrink-0"
            >
              <MIcon name="menu" size={22} />
            </button>
            <h1 className="font-headline font-semibold text-base text-on-surface truncate">{currentLabel}</h1>
            {config.vertical && (
              <span className="hidden sm:inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-secondary-container text-on-secondary-container">
                <span className="w-1.5 h-1.5 rounded-full bg-primary mr-1.5 shrink-0" />
                {VERTICAL_LABEL[config.vertical] || config.vertical}
              </span>
            )}
          </div>
          <div className="flex items-center gap-2 sm:gap-3 shrink-0">
            {/* Language switcher */}
            <nav className="flex items-center gap-1.5">
              {LANGS.map(({ code, label }, i) => (
                <span key={code} className="flex items-center gap-1.5">
                  {i > 0 && <span className="text-outline-variant text-xs">|</span>}
                  <button
                    onClick={() => setLang(code)}
                    className={`px-1 py-1 text-xs rounded transition-colors ${
                      lang === code ? 'text-primary font-bold' : 'text-on-surface-variant hover:text-on-surface'
                    }`}
                  >
                    {label}
                  </button>
                </span>
              ))}
            </nav>
            <Link
              href="/"
              className="flex items-center gap-1 text-xs font-semibold px-3 py-1.5 rounded-lg bg-surface-container hover:bg-surface-container-highest text-on-surface transition-all"
            >
              <MIcon name="open_in_new" size={16} /> <span className="hidden sm:inline">Web</span>
            </Link>
            <div className="w-8 h-8 rounded-full bg-primary flex items-center justify-center shrink-0">
              <MIcon name="person" size={18} className="text-primary-foreground" />
            </div>
          </div>
        </header>

        <main className="flex-1 overflow-y-auto overflow-x-hidden p-3 sm:p-6">
          {children}
        </main>
      </div>
    </div>
  );
}
