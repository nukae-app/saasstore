'use client';

import { useState, useEffect, useMemo } from 'react';
import { authFetch } from '../../lib/auth';
import { Button } from '../../../components/ui/button';
import { useSortFilter } from '../../../components/admin/table/useSortFilter';
import { SortableTh } from '../../../components/admin/table/SortableTh';
import { Plus, X, Send, CheckCircle2, XCircle, Download, ChevronDown, ChevronRight, Trash2 } from 'lucide-react';
import { useT } from '../../lib/i18n';

function fmtDate(d) {
  if (!d) return '—';
  return new Date(d + 'T00:00:00').toLocaleDateString('ca-ES', { day: '2-digit', month: '2-digit', year: 'numeric' });
}

function fmtEur(v) {
  return v != null ? parseFloat(v).toFixed(2) + ' €' : '—';
}

function calcTotals(lines) {
  let base = 0, iva = 0;
  for (const l of lines) {
    const subtotal = parseFloat(l.quantity) * parseFloat(l.unit_price);
    base += subtotal;
    iva += subtotal * parseFloat(l.vat_pct) / 100;
  }
  return { base, iva, total: base + iva };
}

async function downloadPdf(url, filename) {
  const r = await authFetch(url);
  if (!r.ok) return;
  const blob = await r.blob();
  const objUrl = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = objUrl;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(objUrl);
}

export default function PressupostosPage() {
  const t = useT();

  const ESTAT_CFG = useMemo(() => ({
    esborrany: { label: t('pressupostos.status.draft', 'Esborrany'), cls: 'bg-zinc-100 text-zinc-600' },
    enviat: { label: t('pressupostos.status.sent', 'Enviat'), cls: 'bg-blue-100 text-blue-700' },
    acceptat: { label: t('pressupostos.status.accepted', 'Acceptat'), cls: 'bg-green-100 text-green-700' },
    rebutjat: { label: t('pressupostos.status.rejected', 'Rebutjat'), cls: 'bg-red-100 text-red-700' },
  }), [t]);

  const [pressupostos, setPressupostos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState('totes');
  const [showModal, setShowModal] = useState(false);
  const [editPressupost, setEditPressupost] = useState(null);
  const [expanded, setExpanded] = useState(null);
  const [busy, setBusy] = useState(null);

  async function loadAll() {
    setLoading(true);
    const r = await authFetch('/admin/pressupostos');
    setPressupostos(await r.json());
    setLoading(false);
  }
  useEffect(() => { loadAll(); }, []);

  const baseList = tab === 'totes' ? pressupostos : pressupostos.filter(p => p.status === tab);

  const columns = useMemo(() => ({
    numero: { sortValue: p => `${p.fiscal_year}${String(p.number).padStart(6, '0')}` },
    client: { sortValue: p => p.client_name.toLowerCase(), filterValue: p => p.client_name },
    data: { sortValue: p => p.issue_date ?? '' },
    total: { sortValue: p => calcTotals(p.lines).total },
    estat: {
      sortValue: p => ESTAT_CFG[p.status]?.label || p.status,
      filterValue: p => ESTAT_CFG[p.status]?.label || p.status,
    },
  }), [ESTAT_CFG]);

  const { rows: llista, sort, toggleSort, filters, setFilter, distinctValues } = useSortFilter(baseList, columns);

  async function accio(pressupost, endpoint) {
    setBusy(pressupost.id);
    const r = await authFetch(`/admin/pressupostos/${pressupost.id}/${endpoint}`, { method: 'POST' });
    setBusy(null);
    if (r.ok) loadAll();
    else alert((await r.json()).detail || t('common.error', 'Error'));
  }

  async function eliminar(pressupost) {
    if (!confirm(t('pressupostos.confirm_delete', 'Eliminar aquest pressupost?'))) return;
    const r = await authFetch(`/admin/pressupostos/${pressupost.id}`, { method: 'DELETE' });
    if (r.ok) loadAll();
  }

  return (
    <div className="space-y-5 max-w-6xl mx-auto">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-zinc-900">{t('pressupostos.title', 'Pressupostos')}</h2>
        <Button onClick={() => { setEditPressupost(null); setShowModal(true); }}>
          <Plus size={16} /> {t('pressupostos.new', 'Nou pressupost')}
        </Button>
      </div>

      <div className="flex gap-1 bg-zinc-100 p-1 rounded-xl w-fit">
        {[
          ['totes', t('despeses.tab.all', 'Totes')],
          ['esborrany', t('pressupostos.status.draft', 'Esborrany')],
          ['enviat', t('pressupostos.status.sent', 'Enviat')],
          ['acceptat', t('pressupostos.status.accepted', 'Acceptat')],
          ['rebutjat', t('pressupostos.status.rejected', 'Rebutjat')],
        ].map(([k, l]) => (
          <button key={k} onClick={() => setTab(k)}
            className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors ${tab === k ? 'bg-white shadow-sm text-zinc-900' : 'text-zinc-600 hover:text-zinc-900'}`}>
            {l}
          </button>
        ))}
      </div>

      <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm overflow-hidden">
        {loading ? (
          <div className="p-12 text-center text-zinc-400 text-sm">{t('common.loading', 'Carregant...')}</div>
        ) : llista.length === 0 ? (
          <div className="p-12 text-center text-zinc-400 text-sm">{t('pressupostos.empty', 'Cap pressupost trobat')}</div>
        ) : (
          <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-zinc-50 text-xs text-zinc-500 border-b border-zinc-200">
              <tr>
                <th className="w-8 px-4 py-3" />
                <SortableTh label={t('pressupostos.col.number', 'Número')} sortKey="numero" sort={sort} onSort={toggleSort} />
                <SortableTh label={t('pressupostos.client', 'Client')} sortKey="client" sort={sort} onSort={toggleSort}
                  filterOptions={distinctValues.client} selected={filters.client} onFilterChange={setFilter} />
                <SortableTh label={t('common.date', 'Data')} sortKey="data" sort={sort} onSort={toggleSort} />
                <SortableTh label={t('despeses.col.total', 'Total')} sortKey="total" sort={sort} onSort={toggleSort} align="right" />
                <SortableTh label={t('despeses.col.status', 'Estat')} sortKey="estat" sort={sort} onSort={toggleSort} align="center"
                  filterOptions={distinctValues.estat} selected={filters.estat} onFilterChange={setFilter} />
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-100">
              {llista.map(p => {
                const totals = calcTotals(p.lines);
                const isBusy = busy === p.id;
                return (
                  <>
                    <tr key={p.id} onClick={() => setExpanded(expanded === p.id ? null : p.id)}
                      className="hover:bg-zinc-50 cursor-pointer transition-colors">
                      <td className="px-4 py-3 text-zinc-400">
                        {expanded === p.id ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                      </td>
                      <td className="px-4 py-3 font-mono text-xs text-zinc-500">{p.fiscal_year}/{String(p.number).padStart(4, '0')}</td>
                      <td className="px-4 py-3 font-medium text-zinc-900">{p.client_name}</td>
                      <td className="px-4 py-3 text-zinc-600">{fmtDate(p.issue_date)}</td>
                      <td className="px-4 py-3 text-right font-semibold text-zinc-900">{fmtEur(totals.total)}</td>
                      <td className="px-4 py-3 text-center">
                        <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${ESTAT_CFG[p.status]?.cls}`}>
                          {ESTAT_CFG[p.status]?.label}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center justify-end gap-1" onClick={e => e.stopPropagation()}>
                          <button title={t('pressupostos.download_pdf', 'Descarregar PDF')} disabled={isBusy}
                            onClick={() => downloadPdf(`/admin/pressupostos/${p.id}/pdf`, `pressupost_${p.fiscal_year}_${p.number}.pdf`)}
                            className="text-zinc-400 hover:text-zinc-700 p-1.5 rounded hover:bg-zinc-100 transition-colors">
                            <Download size={14} />
                          </button>
                          {(p.status === 'esborrany' || p.status === 'enviat') && (
                            <>
                              <button title={t('pressupostos.send', 'Enviar')} disabled={isBusy}
                                onClick={() => accio(p, 'enviar')}
                                className="text-blue-500 hover:text-blue-700 p-1.5 rounded hover:bg-blue-50 transition-colors">
                                <Send size={14} />
                              </button>
                              <button title={t('pressupostos.accept', 'Acceptar')} disabled={isBusy}
                                onClick={() => accio(p, 'acceptar')}
                                className="text-green-500 hover:text-green-700 p-1.5 rounded hover:bg-green-50 transition-colors">
                                <CheckCircle2 size={14} />
                              </button>
                              <button title={t('pressupostos.reject', 'Rebutjar')} disabled={isBusy}
                                onClick={() => accio(p, 'rebutjar')}
                                className="text-red-500 hover:text-red-700 p-1.5 rounded hover:bg-red-50 transition-colors">
                                <XCircle size={14} />
                              </button>
                            </>
                          )}
                          {p.status === 'esborrany' && (
                            <>
                              <button title={t('common.edit', 'Editar')}
                                onClick={() => { setEditPressupost(p); setShowModal(true); }}
                                className="text-xs text-zinc-400 hover:text-zinc-700 font-medium px-2 py-1 rounded hover:bg-zinc-100 transition-colors">
                                {t('common.edit', 'Editar')}
                              </button>
                              <button title={t('common.delete', 'Eliminar')} onClick={() => eliminar(p)}
                                className="text-zinc-400 hover:text-red-600 p-1.5 rounded hover:bg-red-50 transition-colors">
                                <Trash2 size={14} />
                              </button>
                            </>
                          )}
                        </div>
                      </td>
                    </tr>
                    {expanded === p.id && (
                      <tr key={`${p.id}-exp`}>
                        <td colSpan={7} className="px-6 py-3 bg-zinc-50/80 border-b border-zinc-100">
                          <table className="w-full text-xs">
                            <thead className="text-zinc-400">
                              <tr>
                                <th className="text-left py-1 font-medium">{t('llibres.concept', 'Concepte')}</th>
                                <th className="text-right py-1 font-medium">{t('pressupostos.col.quantity', 'Quant.')}</th>
                                <th className="text-right py-1 font-medium">{t('pressupostos.col.unit_price', 'Preu unit.')}</th>
                                <th className="text-right py-1 font-medium">IVA</th>
                                <th className="text-right py-1 font-medium">{t('despeses.col.total', 'Total')}</th>
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-zinc-100">
                              {p.lines.map(l => (
                                <tr key={l.id}>
                                  <td className="py-1.5 text-zinc-700">{l.description}</td>
                                  <td className="py-1.5 text-right text-zinc-600">{parseFloat(l.quantity).toFixed(2)}</td>
                                  <td className="py-1.5 text-right text-zinc-600">{fmtEur(l.unit_price)}</td>
                                  <td className="py-1.5 text-right text-zinc-600">{parseFloat(l.vat_pct).toFixed(0)}%</td>
                                  <td className="py-1.5 text-right text-zinc-900">{fmtEur(parseFloat(l.quantity) * parseFloat(l.unit_price))}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                          {p.notes && (
                            <div className="mt-2 text-xs text-zinc-500">
                              <span className="text-zinc-400">{t('common.notes', 'Notes')}: </span>{p.notes}
                            </div>
                          )}
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
        <PressupostModal
          pressupost={editPressupost}
          onClose={() => setShowModal(false)}
          onSaved={() => { setShowModal(false); loadAll(); }}
        />
      )}
    </div>
  );
}

function PressupostModal({ pressupost, onClose, onSaved }) {
  const t = useT();
  const isEdit = !!pressupost;

  const [clientName, setClientName] = useState(pressupost?.client_name || '');
  const [clientEmail, setClientEmail] = useState(pressupost?.client_email || '');
  const [validUntil, setValidUntil] = useState(pressupost?.valid_until || '');
  const [notes, setNotes] = useState(pressupost?.notes || '');
  const [lines, setLines] = useState(
    pressupost?.lines?.map(l => ({ description: l.description, quantity: l.quantity, unit_price: l.unit_price, vat_pct: l.vat_pct }))
    || [{ description: '', quantity: '1', unit_price: '', vat_pct: '21' }]
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  function updateLine(i, field, value) {
    setLines(ls => ls.map((l, idx) => (idx === i ? { ...l, [field]: value } : l)));
  }
  function addLine() {
    setLines(ls => [...ls, { description: '', quantity: '1', unit_price: '', vat_pct: '21' }]);
  }
  function removeLine(i) {
    setLines(ls => ls.filter((_, idx) => idx !== i));
  }

  const totals = calcTotals(lines.filter(l => l.description && l.unit_price));

  async function save(e) {
    e.preventDefault();
    setSaving(true);
    setError('');
    const payload = {
      client_name: clientName,
      client_email: clientEmail || null,
      valid_until: validUntil || null,
      notes: notes || null,
      lines: lines
        .filter(l => l.description && l.unit_price)
        .map(l => ({
          description: l.description, quantity: parseFloat(l.quantity) || 1,
          unit_price: parseFloat(l.unit_price), vat_pct: parseFloat(l.vat_pct) || 0,
        })),
    };
    const url = isEdit ? `/admin/pressupostos/${pressupost.id}` : '/admin/pressupostos';
    const method = isEdit ? 'PATCH' : 'POST';
    const r = await authFetch(url, { method, body: JSON.stringify(payload) });
    setSaving(false);
    if (r.ok) onSaved();
    else setError((await r.json()).detail || t('common.error_saving', 'Error desant'));
  }

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-start justify-center p-4 overflow-y-auto">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl my-8">
        <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-200">
          <h3 className="text-lg font-bold text-zinc-900">{isEdit ? t('pressupostos.edit', 'Editar pressupost') : t('pressupostos.new', 'Nou pressupost')}</h3>
          <button onClick={onClose} className="text-zinc-400 hover:text-zinc-600 p-1 rounded-lg hover:bg-zinc-100"><X size={20} /></button>
        </div>
        <form onSubmit={save} className="p-6 space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-zinc-700 mb-1">{t('pressupostos.client_name', 'Nom del client')} *</label>
              <input value={clientName} onChange={e => setClientName(e.target.value)} required
                className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
            </div>
            <div>
              <label className="block text-sm font-medium text-zinc-700 mb-1">{t('pressupostos.client_email', 'Email del client')}</label>
              <input type="email" value={clientEmail} onChange={e => setClientEmail(e.target.value)}
                className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
            </div>
            <div>
              <label className="block text-sm font-medium text-zinc-700 mb-1">{t('pressupostos.valid_until', 'Vàlid fins')}</label>
              <input type="date" value={validUntil} onChange={e => setValidUntil(e.target.value)}
                className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
            </div>
          </div>

          <div className="border border-zinc-200 rounded-xl overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-zinc-50 text-xs text-zinc-500">
                <tr>
                  <th className="px-3 py-2 text-left font-medium">{t('llibres.concept', 'Concepte')}</th>
                  <th className="px-3 py-2 text-right font-medium w-20">{t('pressupostos.col.quantity', 'Quant.')}</th>
                  <th className="px-3 py-2 text-right font-medium w-24">{t('pressupostos.col.unit_price', 'Preu unit.')}</th>
                  <th className="px-3 py-2 text-right font-medium w-20">IVA %</th>
                  <th className="w-8" />
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {lines.map((l, i) => (
                  <tr key={i}>
                    <td className="px-2 py-1.5">
                      <input value={l.description} onChange={e => updateLine(i, 'description', e.target.value)}
                        placeholder={t('pressupostos.line_placeholder', 'Descripció...')}
                        className="w-full border border-zinc-200 rounded px-2 py-1 text-sm focus:outline-none focus:ring-1 focus:ring-zinc-900" />
                    </td>
                    <td className="px-2 py-1.5">
                      <input type="number" step="0.01" value={l.quantity} onChange={e => updateLine(i, 'quantity', e.target.value)}
                        className="w-full border border-zinc-200 rounded px-2 py-1 text-sm text-right focus:outline-none focus:ring-1 focus:ring-zinc-900" />
                    </td>
                    <td className="px-2 py-1.5">
                      <input type="number" step="0.01" value={l.unit_price} onChange={e => updateLine(i, 'unit_price', e.target.value)}
                        className="w-full border border-zinc-200 rounded px-2 py-1 text-sm text-right focus:outline-none focus:ring-1 focus:ring-zinc-900" />
                    </td>
                    <td className="px-2 py-1.5">
                      <input type="number" step="0.01" value={l.vat_pct} onChange={e => updateLine(i, 'vat_pct', e.target.value)}
                        className="w-full border border-zinc-200 rounded px-2 py-1 text-sm text-right focus:outline-none focus:ring-1 focus:ring-zinc-900" />
                    </td>
                    <td className="px-1">
                      {lines.length > 1 && (
                        <button type="button" onClick={() => removeLine(i)} className="text-zinc-300 hover:text-red-500"><X size={14} /></button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot className="bg-zinc-50 border-t border-zinc-200">
                <tr>
                  <td className="px-3 py-2" colSpan={2}>
                    <button type="button" onClick={addLine} className="text-xs text-zinc-500 hover:text-zinc-800 font-medium">+ {t('llibres.add_line', 'Afegir línia')}</button>
                  </td>
                  <td colSpan={3} className="px-3 py-2 text-right text-xs text-zinc-500">
                    {t('despeses.taxable_base', 'Base imposable')}: <span className="font-semibold text-zinc-700">{fmtEur(totals.base)}</span>
                    {' · '}IVA: <span className="font-semibold text-zinc-700">{fmtEur(totals.iva)}</span>
                    {' · '}{t('despeses.col.total', 'Total')}: <span className="font-bold text-zinc-900">{fmtEur(totals.total)}</span>
                  </td>
                </tr>
              </tfoot>
            </table>
          </div>

          <div>
            <label className="block text-sm font-medium text-zinc-700 mb-1">{t('common.notes', 'Notes')}</label>
            <textarea value={notes} onChange={e => setNotes(e.target.value)} rows={2}
              className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900 resize-none" />
          </div>

          {error && <p className="text-red-500 text-xs">{error}</p>}
          <div className="flex justify-end gap-3">
            <Button type="button" variant="secondary" onClick={onClose}>{t('common.cancel', "Cancel·lar")}</Button>
            <Button type="submit" disabled={saving}>{saving ? t('common.saving', 'Desant...') : isEdit ? t('despeses.save_changes', 'Desar canvis') : t('pressupostos.create', 'Crear pressupost')}</Button>
          </div>
        </form>
      </div>
    </div>
  );
}
