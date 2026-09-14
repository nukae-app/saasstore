'use client';

import { useState, useEffect, useMemo } from 'react';
import { authFetch } from '../../lib/auth';
import { Button } from '../../../components/ui/button';
import { useSortFilter } from '../../../components/admin/table/useSortFilter';
import { SortableTh } from '../../../components/admin/table/SortableTh';
import MIcon from '../../../components/ui/m-icon';
import { useT } from '../../lib/i18n';

function fmtDate(d) {
  if (!d) return '—';
  return new Date(d + 'T00:00:00').toLocaleDateString('ca-ES', { day: '2-digit', month: '2-digit', year: 'numeric' });
}

function fmtEur(v) {
  return v != null ? parseFloat(v).toFixed(2) + ' €' : '—';
}

async function downloadFile(url, filename) {
  let r;
  try {
    r = await authFetch(url);
  } catch (e) {
    alert(e?.message || 'Error de xarxa descarregant el fitxer');
    return;
  }
  if (!r.ok) {
    const detail = await r.json().catch(() => null);
    alert(detail?.detail || `No s'ha pogut descarregar el fitxer (${r.status})`);
    return;
  }
  const blob = await r.blob();
  const objUrl = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = objUrl;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(objUrl);
}

export default function RemesesPagamentPage() {
  const t = useT();

  const ESTAT_CFG = useMemo(() => ({
    generada: { label: t('remeses.status.generada', 'Generada'), cls: 'bg-green-100 text-green-700' },
    anullada: { label: t('remeses.status.anullada', 'Anul·lada'), cls: 'bg-red-100 text-red-700' },
  }), [t]);

  const [remeses, setRemeses] = useState([]);
  const [comptes, setComptes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [expanded, setExpanded] = useState(null);
  const [busy, setBusy] = useState(null);

  async function loadAll() {
    setLoading(true);
    const [rRes, cRes] = await Promise.all([
      authFetch('/admin/remeses-pagament'),
      authFetch('/admin/comptes'),
    ]);
    setRemeses(await rRes.json());
    setComptes(await cRes.json());
    setLoading(false);
  }
  useEffect(() => { loadAll(); }, []);

  function nomCompte(id) {
    return comptes.find(c => c.id === id)?.name || '—';
  }

  const columns = useMemo(() => ({
    numero: { sortValue: r => `${r.fiscal_year}${String(r.number).padStart(6, '0')}` },
    data_execucio: { sortValue: r => r.execution_date ?? '' },
    total: { sortValue: r => parseFloat(r.total) },
    estat: { sortValue: r => ESTAT_CFG[r.status]?.label || r.status, filterValue: r => ESTAT_CFG[r.status]?.label || r.status },
  }), [ESTAT_CFG]);

  const { rows: llista, sort, toggleSort, filters, setFilter, distinctValues } = useSortFilter(remeses, columns);

  async function anullar(remesa) {
    const numero = `${remesa.fiscal_year}/${String(remesa.number).padStart(4, '0')}`;
    if (!confirm(t('remeses.confirm_void', `Anul·lar la remesa ${numero}? Les despeses que encara estiguin "en remesa" tornaran a quedar pendents.`).replace('{numero}', numero))) return;
    setBusy(remesa.id);
    const r = await authFetch(`/admin/remeses-pagament/${remesa.id}/anullar`, { method: 'POST' });
    setBusy(null);
    if (r.ok) loadAll();
    else alert((await r.json()).detail || t('common.error', 'Error'));
  }

  return (
    <div className="space-y-5 max-w-6xl mx-auto">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-on-surface">{t('remeses.title', 'Remeses de pagament')}</h2>
          <p className="text-sm text-secondary-foreground mt-1">
            {t('remeses.subtitle', 'Fitxer SEPA (pain.001) per pagar proveïdors — només el genera, mai el presenta: descarrega\'l i puja\'l al portal del teu banc.')}
          </p>
        </div>
        <Button onClick={() => setShowModal(true)}>
          <MIcon name="add" size={16} /> {t('remeses.new', 'Nova remesa')}
        </Button>
      </div>

      <div className="bg-card rounded-2xl border border-outline-variant shadow-sm overflow-hidden">
        {loading ? (
          <div className="p-12 text-center text-secondary-foreground text-sm">{t('common.loading', 'Carregant...')}</div>
        ) : llista.length === 0 ? (
          <div className="p-12 text-center text-secondary-foreground text-sm">{t('remeses.empty', 'Cap remesa generada')}</div>
        ) : (
          <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-surface-container-high text-xs text-secondary-foreground border-b border-outline-variant">
              <tr>
                <th className="w-8 px-4 py-3" />
                <SortableTh label={t('pressupostos.col.number', 'Número')} sortKey="numero" sort={sort} onSort={toggleSort} />
                <SortableTh label={t('remeses.execution_date', 'Data execució')} sortKey="data_execucio" sort={sort} onSort={toggleSort} />
                <th className="px-4 py-3 text-left font-medium">{t('banc.title_short', 'Compte')}</th>
                <SortableTh label={t('despeses.col.total', 'Total')} sortKey="total" sort={sort} onSort={toggleSort} align="right" />
                <SortableTh label={t('despeses.col.status', 'Estat')} sortKey="estat" sort={sort} onSort={toggleSort} align="center"
                  filterOptions={distinctValues.estat} selected={filters.estat} onFilterChange={setFilter} />
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-outline-variant">
              {llista.map(r => {
                const isBusy = busy === r.id;
                const numero = `${r.fiscal_year}/${String(r.number).padStart(4, '0')}`;
                return (
                  <>
                    <tr key={r.id} onClick={() => setExpanded(expanded === r.id ? null : r.id)}
                      className={`hover:bg-surface-container-high cursor-pointer transition-colors ${r.status === 'anullada' ? 'opacity-60' : ''}`}>
                      <td className="px-4 py-3 text-secondary-foreground">
                        {expanded === r.id ? <MIcon name="expand_more" size={14} /> : <MIcon name="chevron_right" size={14} />}
                      </td>
                      <td className="px-4 py-3 font-mono text-xs text-secondary-foreground">{numero}</td>
                      <td className="px-4 py-3 text-on-surface-variant">{fmtDate(r.execution_date)}</td>
                      <td className="px-4 py-3 text-on-surface-variant">{nomCompte(r.compte_bancari_id)}</td>
                      <td className="px-4 py-3 text-right font-semibold text-on-surface">{fmtEur(r.total)}</td>
                      <td className="px-4 py-3 text-center">
                        <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${ESTAT_CFG[r.status]?.cls}`}>
                          {ESTAT_CFG[r.status]?.label}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center justify-end gap-1" onClick={e => e.stopPropagation()}>
                          <button title={t('remeses.download_xml', 'Descarregar XML')} disabled={isBusy}
                            onClick={() => downloadFile(`/admin/remeses-pagament/${r.id}/xml`, `remesa_${r.fiscal_year}_${r.number}.xml`)}
                            className="text-secondary-foreground hover:text-on-surface-variant p-1.5 rounded hover:bg-surface-container-high transition-colors">
                            <MIcon name="download" size={14} />
                          </button>
                          {r.status === 'generada' && (
                            <button title={t('remeses.void', 'Anul·lar')} disabled={isBusy} onClick={() => anullar(r)}
                              className="text-secondary-foreground hover:text-red-600 p-1.5 rounded hover:bg-red-50 transition-colors">
                              <MIcon name="cancel" size={14} />
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                    {expanded === r.id && (
                      <tr key={`${r.id}-exp`}>
                        <td colSpan={7} className="px-6 py-3 bg-surface-container-high/80 border-b border-outline-variant">
                          <table className="w-full text-xs">
                            <thead className="text-secondary-foreground">
                              <tr>
                                <th className="text-left py-1 font-medium">{t('nav.proveidors', 'Proveïdor')}</th>
                                <th className="text-right py-1 font-medium">{t('despeses.col.total', 'Import')}</th>
                                <th className="text-left py-1 font-medium">End-to-End ID</th>
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-outline-variant">
                              {r.lines.map(l => (
                                <tr key={l.despesa_id}>
                                  <td className="py-1.5 text-on-surface-variant">{l.supplier_name}</td>
                                  <td className="py-1.5 text-right text-on-surface">{fmtEur(l.import)}</td>
                                  <td className="py-1.5 text-secondary-foreground font-mono">{l.end_to_end_id}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </td>
                      </tr>
                    )}
                  </>
                );
              })}
            </tbody>
          </table>
          </div>
        )}
      </div>

      {showModal && (
        <NovaRemesaModal comptes={comptes} onClose={() => setShowModal(false)} onSaved={() => { setShowModal(false); loadAll(); }} />
      )}
    </div>
  );
}

function NovaRemesaModal({ comptes, onClose, onSaved }) {
  const t = useT();
  const today = new Date().toISOString().slice(0, 10);
  const [compteId, setCompteId] = useState(comptes[0]?.id || '');
  const [dataExecucio, setDataExecucio] = useState(today);
  const [despeses, setDespeses] = useState([]);
  const [loadingDespeses, setLoadingDespeses] = useState(true);
  const [seleccionades, setSeleccionades] = useState(new Set());
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    authFetch('/admin/remeses-pagament/despeses-elegibles').then(r => r.json()).then(list => {
      setDespeses(list);
      setLoadingDespeses(false);
    });
  }, []);

  function toggle(id) {
    setSeleccionades(s => {
      const next = new Set(s);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }

  const total = despeses.filter(d => seleccionades.has(d.despesa_id)).reduce((s, d) => s + parseFloat(d.net_a_pagar), 0);

  async function save(e) {
    e.preventDefault();
    if (seleccionades.size === 0) { setError(t('remeses.select_at_least_one', 'Selecciona com a mínim una despesa')); return; }
    setSaving(true);
    setError('');
    const r = await authFetch('/admin/remeses-pagament', {
      method: 'POST',
      body: JSON.stringify({
        compte_bancari_id: Number(compteId), execution_date: dataExecucio,
        despesa_ids: Array.from(seleccionades),
      }),
    });
    setSaving(false);
    if (r.ok) onSaved();
    else setError((await r.json()).detail || t('common.error_saving', 'Error desant'));
  }

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-start justify-center p-4 overflow-y-auto">
      <div className="bg-card rounded-2xl shadow-2xl w-full max-w-2xl my-8">
        <div className="flex items-center justify-between px-6 py-4 border-b border-outline-variant">
          <h3 className="text-lg font-bold text-on-surface">{t('remeses.new', 'Nova remesa')}</h3>
          <button onClick={onClose} className="text-secondary-foreground hover:text-on-surface-variant p-1 rounded-lg hover:bg-surface-container-high"><MIcon name="close" size={20} /></button>
        </div>
        <form onSubmit={save} className="p-6 space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-on-surface-variant mb-1">{t('remeses.issuing_account', 'Compte emissor')} *</label>
              <select value={compteId} onChange={e => setCompteId(e.target.value)} required
                className="w-full border border-outline-variant rounded-lg px-3 py-2 text-sm bg-card focus:outline-none focus:ring-2 focus:ring-primary">
                <option value="">{t('common.select', 'Selecciona...')}</option>
                {comptes.map(c => <option key={c.id} value={c.id}>{c.name}{c.iban ? ` — ${c.iban.slice(-6)}` : ''}</option>)}
              </select>
              {comptes.length > 0 && comptes.find(c => String(c.id) === String(compteId)) && !comptes.find(c => String(c.id) === String(compteId)).iban && (
                <p className="text-xs text-red-500 mt-1">{t('remeses.account_needs_iban', 'Aquest compte no té IBAN informat.')}</p>
              )}
            </div>
            <div>
              <label className="block text-sm font-medium text-on-surface-variant mb-1">{t('remeses.execution_date', 'Data execució')} *</label>
              <input type="date" value={dataExecucio} onChange={e => setDataExecucio(e.target.value)} required min={today}
                className="w-full border border-outline-variant rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary" />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-on-surface-variant mb-2">
              {t('remeses.eligible_expenses', 'Despeses elegibles')}
              <span className="text-xs text-secondary-foreground font-normal ml-1">
                ({t('remeses.eligible_hint', 'pendents/vençudes, pagament per transferència, proveïdor amb IBAN')})
              </span>
            </label>
            {loadingDespeses ? (
              <div className="p-6 text-center text-secondary-foreground text-sm">{t('common.loading', 'Carregant...')}</div>
            ) : despeses.length === 0 ? (
              <div className="p-6 text-center text-secondary-foreground text-sm border border-outline-variant rounded-xl">
                {t('remeses.no_eligible_expenses', 'Cap despesa elegible per a una remesa ara mateix.')}
              </div>
            ) : (
              <div className="border border-outline-variant rounded-xl divide-y divide-outline-variant max-h-64 overflow-y-auto">
                {despeses.map(d => (
                  <label key={d.despesa_id} className="flex items-center gap-3 px-3 py-2 text-sm cursor-pointer hover:bg-surface-container-high">
                    <input type="checkbox" checked={seleccionades.has(d.despesa_id)} onChange={() => toggle(d.despesa_id)} />
                    <span className="flex-1 text-on-surface-variant">{d.supplier_name}</span>
                    <span className="text-xs text-secondary-foreground">{d.due_date ? fmtDate(d.due_date) : '—'}</span>
                    <span className="font-semibold text-on-surface w-20 text-right">{fmtEur(d.net_a_pagar)}</span>
                  </label>
                ))}
              </div>
            )}
          </div>

          {seleccionades.size > 0 && (
            <div className="flex items-center justify-between bg-surface-container-high rounded-xl px-4 py-3">
              <span className="text-sm text-secondary-foreground">{seleccionades.size} {t('remeses.selected', 'seleccionades')}</span>
              <span className="text-lg font-bold text-on-surface">{fmtEur(total)}</span>
            </div>
          )}

          {error && <p className="text-red-500 text-xs">{error}</p>}
          <div className="flex justify-end gap-3">
            <Button type="button" variant="secondary" onClick={onClose}>{t('common.cancel', "Cancel·lar")}</Button>
            <Button type="submit" disabled={saving || seleccionades.size === 0}>
              {saving ? t('common.saving', 'Desant...') : t('remeses.generate', 'Generar remesa')}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
