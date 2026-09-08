'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { authFetch } from '../../lib/auth';
import MIcon from '../../../components/ui/m-icon';
import { useT } from '../../lib/i18n';

function fmtEur(v) {
  return v != null ? parseFloat(v).toFixed(2) + ' €' : '—';
}
function fmtDate(d) {
  if (!d) return '—';
  return new Date(d + 'T00:00:00').toLocaleDateString('ca-ES', { day: '2-digit', month: '2-digit' });
}

export default function ComptabilitatResumPage() {
  const t = useT();
  const [pyg, setPyg] = useState(null);
  const [aeat, setAeat] = useState(null);
  const [pendents, setPendents] = useState([]);
  const [saldoBanc, setSaldoBanc] = useState(null);
  const [diari, setDiari] = useState(null);
  const [loading, setLoading] = useState(true);

  const ACCESSOS = [
    { href: '/admin/despeses', label: t('nav.despeses', 'Despeses'), icon: 'receipt_long' },
    { href: '/admin/banc', label: t('nav.banc', 'Banc'), icon: 'account_balance' },
    { href: '/admin/proveidors', label: t('nav.proveidors', 'Proveïdors'), icon: 'local_shipping' },
    { href: '/admin/pla-comptes', label: t('nav.pla_comptes', 'Pla de comptes'), icon: 'menu_book' },
    { href: '/admin/actius', label: t('nav.actius', 'Actius'), icon: 'inventory_2' },
    { href: '/admin/llibres', label: t('nav.llibres', 'Llibres'), icon: 'auto_stories' },
  ];

  useEffect(() => {
    const now = new Date();
    const year = now.getFullYear();
    const mes = now.getMonth() + 1;
    const trimestre = Math.ceil(mes / 3);

    // allSettled, no all: una targeta caient (p.ex. sessió caducada just en
    // aquesta crida concreta) no ha de deixar tota la pantalla penjada a
    // "Carregant..." per sempre — cada targeta es degrada per separat.
    Promise.allSettled([
      authFetch(`/admin/compte-resultats/${year}/${mes}`).then(r => (r.ok ? r.json() : null)),
      authFetch(`/admin/aeat/303/${year}/${trimestre}`).then(r => (r.ok ? r.json() : null)),
      authFetch('/admin/despeses/pendents').then(r => (r.ok ? r.json() : [])),
      authFetch(`/admin/llibre-major/${year}?compte=572`).then(r => (r.ok ? r.json() : null)),
      authFetch(`/admin/llibre-diari/${year}/${mes}`).then(r => (r.ok ? r.json() : null)),
    ]).then(([pygRes, aeatRes, pendentsRes, majorRes, diariRes]) => {
      setPyg(pygRes.status === 'fulfilled' ? pygRes.value : null);
      setAeat(aeatRes.status === 'fulfilled' ? aeatRes.value : null);
      setPendents(pendentsRes.status === 'fulfilled' ? pendentsRes.value ?? [] : []);
      setSaldoBanc(majorRes.status === 'fulfilled' ? majorRes.value?.saldo_final ?? null : null);
      setDiari(diariRes.status === 'fulfilled' ? diariRes.value : null);
      setLoading(false);
    });
  }, []);

  if (loading) return <div className="p-12 text-center text-secondary text-sm">{t('common.loading', 'Carregant...')}</div>;

  const resultatPositiu = pyg && parseFloat(pyg.resultat) >= 0;
  const vencudes = pendents.filter(d => d.payment_status === 'vencut');
  const properesAVencer = pendents
    .filter(d => d.payment_status !== 'vencut')
    .sort((a, b) => (a.due_date || '9999').localeCompare(b.due_date || '9999'))
    .slice(0, 5);
  const ultimsAssentaments = diari?.assentaments?.slice(-5).reverse() || [];

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      <div>
        <h2 className="text-2xl font-bold text-on-surface">{t('nav.comptabilitat', 'Comptabilitat')}</h2>
        <p className="text-sm text-secondary mt-1">{t('comptabilitat.subtitle', "Resum del mes en curs — un cop d'ull abans d'entrar al detall.")}</p>
      </div>

      {/* Targes resum */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <div className={`rounded-xl p-4 border ${resultatPositiu ? 'bg-green-50 border-green-200' : 'bg-red-50 border-red-200'}`}>
          <div className={`flex items-center gap-1.5 text-xs mb-1 ${resultatPositiu ? 'text-green-600' : 'text-red-600'}`}>
            {resultatPositiu ? <MIcon name="trending_up" size={13} /> : <MIcon name="trending_down" size={13} />} {t('comptabilitat.card.month_result', 'Resultat del mes')}
          </div>
          <div className={`text-xl font-bold ${resultatPositiu ? 'text-green-700' : 'text-red-700'}`}>
            {pyg ? fmtEur(pyg.resultat) : '—'}
          </div>
        </div>

        <Link href="/admin/models-fiscals" className="rounded-xl p-4 border bg-blue-50 border-blue-200 hover:border-blue-400 transition-colors">
          <div className="flex items-center gap-1.5 text-xs mb-1 text-blue-600"><MIcon name="calculate" size={13} /> {t('comptabilitat.card.vat_quarter', 'IVA trimestre actual')}</div>
          <div className="text-xl font-bold text-blue-700">{aeat ? fmtEur(aeat.casella_64_resultat_liquidacio) : '—'}</div>
        </Link>

        <div className="rounded-xl p-4 border bg-surface-container-high border-outline-variant">
          <div className="flex items-center gap-1.5 text-xs mb-1 text-secondary"><MIcon name="account_balance" size={13} /> {t('comptabilitat.card.bank_balance', 'Saldo banc (572)')}</div>
          <div className="text-xl font-bold text-on-surface">{saldoBanc != null ? fmtEur(saldoBanc) : '—'}</div>
        </div>

        <div className={`rounded-xl p-4 border ${vencudes.length ? 'bg-red-50 border-red-200' : 'bg-surface-container-high border-outline-variant'}`}>
          <div className={`flex items-center gap-1.5 text-xs mb-1 ${vencudes.length ? 'text-red-600' : 'text-secondary'}`}>
            <MIcon name="error" size={13} /> {t('comptabilitat.card.overdue', 'Factures vençudes')}
          </div>
          <div className={`text-xl font-bold ${vencudes.length ? 'text-red-700' : 'text-on-surface'}`}>{vencudes.length}</div>
        </div>
      </div>

      <div className="grid md:grid-cols-2 gap-4">
        {/* Pendents de pagament */}
        <div className="bg-card rounded-2xl border border-outline-variant shadow-sm overflow-hidden">
          <div className="px-4 py-2.5 bg-surface-container-high border-b border-outline-variant flex items-center justify-between">
            <span className="text-sm font-semibold text-on-surface-variant flex items-center gap-1.5"><MIcon name="schedule" size={14} /> {t('comptabilitat.upcoming_due', 'Properes a vèncer')}</span>
            <Link href="/admin/despeses" className="text-xs text-secondary hover:text-on-surface-variant flex items-center gap-0.5">
              {t('common.see_all', 'Veure totes')} <MIcon name="arrow_forward" size={11} />
            </Link>
          </div>
          {properesAVencer.length === 0 ? (
            <div className="p-6 text-center text-secondary text-xs">{t('comptabilitat.no_pending_invoices', 'Cap factura pendent')}</div>
          ) : (
            <div className="divide-y divide-outline-variant">
              {properesAVencer.map(d => (
                <div key={d.id} className="px-4 py-2.5 flex items-center justify-between text-sm">
                  <div>
                    <div className="text-on-surface">{d.supplier_name}</div>
                    <div className="text-xs text-secondary">{t('comptabilitat.due', 'Venç')} {fmtDate(d.due_date)}</div>
                  </div>
                  <div className="font-semibold text-on-surface">{fmtEur(d.total)}</div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Últims assentaments */}
        <div className="bg-card rounded-2xl border border-outline-variant shadow-sm overflow-hidden">
          <div className="px-4 py-2.5 bg-surface-container-high border-b border-outline-variant flex items-center justify-between">
            <span className="text-sm font-semibold text-on-surface-variant flex items-center gap-1.5"><MIcon name="auto_stories" size={14} /> {t('comptabilitat.latest_entries', 'Últims assentaments')}</span>
            <Link href="/admin/llibres" className="text-xs text-secondary hover:text-on-surface-variant flex items-center gap-0.5">
              {t('comptabilitat.see_books', 'Veure llibres')} <MIcon name="arrow_forward" size={11} />
            </Link>
          </div>
          {ultimsAssentaments.length === 0 ? (
            <div className="p-6 text-center text-secondary text-xs">{t('llibres.no_entries_month', 'Cap assentament aquest mes')}</div>
          ) : (
            <div className="divide-y divide-outline-variant">
              {ultimsAssentaments.map(a => (
                <div key={a.id} className="px-4 py-2.5 flex items-center justify-between text-sm">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs text-secondary">#{a.entry_number}</span>
                    <span className="text-on-surface">{a.description}</span>
                  </div>
                  <span className="text-xs text-secondary">{fmtDate(a.date)}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Accessos ràpids */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2">
        {ACCESSOS.map(({ href, label, icon }) => (
          <Link key={href} href={href}
            className="flex flex-col items-center gap-1.5 p-4 bg-card border border-outline-variant rounded-xl hover:border-outline hover:shadow-sm transition-all text-center">
            <MIcon name={icon} size={20} className="text-secondary" />
            <span className="text-xs font-medium text-on-surface-variant">{label}</span>
          </Link>
        ))}
      </div>
    </div>
  );
}
