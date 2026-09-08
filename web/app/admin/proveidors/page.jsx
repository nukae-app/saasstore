'use client';

import { useEffect, useMemo, useState } from 'react';
import { authFetch } from '../../lib/auth';
import { useSortFilter } from '../../../components/admin/table/useSortFilter';
import { SortableTh } from '../../../components/admin/table/SortableTh';
import MIcon from '../../../components/ui/m-icon';
import { useT } from '../../lib/i18n';

function fmtEur(v) {
  return v != null ? parseFloat(v).toFixed(2) + ' €' : '—';
}
function fmtDate(d) {
  if (!d) return '—';
  return new Date(d + 'T00:00:00').toLocaleDateString('ca-ES', { day: '2-digit', month: '2-digit', year: 'numeric' });
}

export default function ProveidorsPage() {
  const t = useT();
  const [proveidors, setProveidors] = useState([]);
  const [pendents, setPendents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState(null);
  const [historial, setHistorial] = useState({});

  useEffect(() => {
    Promise.all([
      authFetch('/admin/proveedores').then(r => r.json()),
      authFetch('/admin/despeses/pendents').then(r => r.json()),
    ]).then(([provs, pend]) => {
      setProveidors(provs);
      setPendents(pend);
      setLoading(false);
    });
  }, []);

  // Saldo pendent/vençut per proveïdor, calculat al client a partir de
  // /admin/despeses/pendents — sense endpoint nou, ja porta proveidor_id.
  const saldos = useMemo(() => {
    const acc = {};
    for (const d of pendents) {
      if (!d.proveidor_id) continue;
      const s = acc[d.proveidor_id] || { pendent: 0, vencut: 0 };
      s[d.payment_status === 'vencut' ? 'vencut' : 'pendent'] += parseFloat(d.total);
      acc[d.proveidor_id] = s;
    }
    return acc;
  }, [pendents]);

  const columns = useMemo(() => ({
    nom: { sortValue: p => p.name.toLowerCase() },
    saldo: { sortValue: p => (saldos[p.id]?.pendent || 0) + (saldos[p.id]?.vencut || 0) },
  }), [saldos]);

  const { rows: llista, sort, toggleSort } = useSortFilter(proveidors, columns);

  async function toggleExpand(prov) {
    if (expanded === prov.id) {
      setExpanded(null);
      return;
    }
    setExpanded(prov.id);
    if (!historial[prov.id]) {
      const r = await authFetch(`/admin/despeses?proveidor_id=${prov.id}`);
      const dades = await r.json();
      setHistorial(h => ({ ...h, [prov.id]: dades }));
    }
  }

  return (
    <div className="space-y-5 max-w-5xl mx-auto">
      <div>
        <h2 className="text-2xl font-bold text-on-surface">{t('nav.proveidors', 'Proveïdors')}</h2>
        <p className="text-sm text-secondary mt-1">{t('proveidors.subtitle', 'Compte corrent per proveïdor — saldo pendent i historial de factures.')}</p>
      </div>

      <div className="bg-card rounded-2xl border border-outline-variant shadow-sm overflow-hidden">
        {loading ? (
          <div className="p-12 text-center text-secondary text-sm">{t('common.loading', 'Carregant...')}</div>
        ) : llista.length === 0 ? (
          <div className="p-12 text-center text-secondary text-sm">{t('proveidors.empty', "Cap proveïdor donat d'alta")}</div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-surface-container-high text-xs text-secondary border-b border-outline-variant">
              <tr>
                <th className="w-8 px-4 py-3" />
                <SortableTh label={t('nav.proveidors', 'Proveïdor')} sortKey="nom" sort={sort} onSort={toggleSort} />
                <SortableTh label={t('proveidors.col.balance', 'Saldo pendent')} sortKey="saldo" sort={sort} onSort={toggleSort} align="right" />
              </tr>
            </thead>
            <tbody className="divide-y divide-outline-variant">
              {llista.map(p => {
                const s = saldos[p.id];
                const total = (s?.pendent || 0) + (s?.vencut || 0);
                return (
                  <>
                    <tr key={p.id} onClick={() => toggleExpand(p)} className="hover:bg-surface-container-high cursor-pointer transition-colors">
                      <td className="px-4 py-3 text-secondary">
                        {expanded === p.id ? <MIcon name="expand_more" size={14} /> : <MIcon name="chevron_right" size={14} />}
                      </td>
                      <td className="px-4 py-3 font-medium text-on-surface">{p.name}</td>
                      <td className="px-4 py-3 text-right">
                        {total === 0 ? (
                          <span className="text-secondary">{t('proveidors.up_to_date', 'Al dia')}</span>
                        ) : (
                          <span className={`font-semibold ${s?.vencut ? 'text-red-600' : 'text-amber-600'}`}>
                            {s?.vencut > 0 && <MIcon name="error" size={12} className="inline mr-1 -mt-0.5" />}
                            {fmtEur(total)}
                          </span>
                        )}
                      </td>
                    </tr>
                    {expanded === p.id && (
                      <tr key={`${p.id}-exp`}>
                        <td colSpan={3} className="px-6 py-3 bg-surface-container-high/80 border-b border-outline-variant">
                          {!historial[p.id] ? (
                            <div className="text-xs text-secondary py-2">{t('proveidors.loading_history', 'Carregant historial...')}</div>
                          ) : historial[p.id].length === 0 ? (
                            <div className="text-xs text-secondary py-2">{t('proveidors.no_invoices', 'Cap factura registrada')}</div>
                          ) : (
                            <table className="w-full text-xs">
                              <thead className="text-secondary">
                                <tr>
                                  <th className="text-left py-1 font-medium">{t('common.date', 'Data')}</th>
                                  <th className="text-left py-1 font-medium">{t('llibres.concept', 'Concepte')}</th>
                                  <th className="text-right py-1 font-medium">{t('despeses.col.total', 'Total')}</th>
                                  <th className="text-center py-1 font-medium">{t('despeses.col.status', 'Estat')}</th>
                                </tr>
                              </thead>
                              <tbody className="divide-y divide-outline-variant">
                                {historial[p.id].map(d => (
                                  <tr key={d.id}>
                                    <td className="py-1.5 text-on-surface-variant">{fmtDate(d.invoice_date)}</td>
                                    <td className="py-1.5 text-on-surface-variant">{d.concept}</td>
                                    <td className="py-1.5 text-right text-on-surface">{fmtEur(d.total)}</td>
                                    <td className="py-1.5 text-center">
                                      {d.payment_status === 'pagat' ? (
                                        <span className="text-green-600">{t('despeses.status.paid', 'Pagat')}</span>
                                      ) : d.payment_status === 'vencut' ? (
                                        <span className="text-red-600 flex items-center justify-center gap-1"><MIcon name="error" size={11} /> {t('despeses.status.overdue', 'Vençut')}</span>
                                      ) : (
                                        <span className="text-amber-600 flex items-center justify-center gap-1"><MIcon name="schedule" size={11} /> {t('despeses.status.pending', 'Pendent')}</span>
                                      )}
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          )}
                        </td>
                      </tr>
                    )}
                  </>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
