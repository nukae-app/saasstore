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
  let r;
  try {
    r = await authFetch(url);
  } catch (e) {
    alert(e?.message || 'Error de xarxa descarregant el PDF');
    return;
  }
  if (!r.ok) {
    const detail = await r.json().catch(() => null);
    alert(detail?.detail || `No s'ha pogut descarregar el PDF (${r.status})`);
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

export default function FacturesPage() {
  const t = useT();

  const ESTAT_CFG = useMemo(() => ({
    emesa: { label: t('factures.status.issued', 'Emesa'), cls: 'bg-green-100 text-green-700' },
    anullada: { label: t('factures.status.voided', 'Anul·lada'), cls: 'bg-red-100 text-red-700' },
  }), [t]);

  const ORIGEN_CFG = useMemo(() => ({
    ticket: { label: t('factures.origin.ticket', 'Tiquet'), icon: 'receipt_long' },
    manual: { label: t('factures.origin.manual', 'Servei'), icon: 'edit_note' },
  }), [t]);

  const [factures, setFactures] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [expanded, setExpanded] = useState(null);
  const [busy, setBusy] = useState(null);

  async function loadAll() {
    setLoading(true);
    const r = await authFetch('/admin/factures');
    setFactures(await r.json());
    setLoading(false);
  }
  useEffect(() => { loadAll(); }, []);

  const columns = useMemo(() => ({
    numero: { sortValue: f => `${f.fiscal_year}${String(f.number).padStart(6, '0')}` },
    client: { sortValue: f => f.client_name.toLowerCase(), filterValue: f => f.client_name },
    data: { sortValue: f => f.issue_date ?? '' },
    total: { sortValue: f => parseFloat(f.total) },
    origen: { sortValue: f => ORIGEN_CFG[f.origen]?.label || f.origen, filterValue: f => ORIGEN_CFG[f.origen]?.label || f.origen },
    estat: { sortValue: f => ESTAT_CFG[f.status]?.label || f.status, filterValue: f => ESTAT_CFG[f.status]?.label || f.status },
  }), [ESTAT_CFG, ORIGEN_CFG]);

  const { rows: llista, sort, toggleSort, filters, setFilter, distinctValues } = useSortFilter(factures, columns);

  async function anullar(factura) {
    if (!confirm(t('factures.confirm_void', `Anul·lar la factura ${factura.fiscal_year}/${String(factura.number).padStart(4, '0')}? El número no es reutilitzarà.`))) return;
    setBusy(factura.id);
    const r = await authFetch(`/admin/factures/${factura.id}/anullar`, { method: 'POST' });
    setBusy(null);
    if (r.ok) loadAll();
    else alert((await r.json()).detail || t('common.error', 'Error'));
  }

  return (
    <div className="space-y-5 max-w-6xl mx-auto">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-on-surface">{t('factures.title', 'Factures')}</h2>
          <p className="text-sm text-secondary-foreground mt-1">
            {t('factures.subtitle', 'Numeració correlativa i IVA — capa base del Reglament de Facturació, sense VeriFactu.')}
          </p>
        </div>
        <Button onClick={() => setShowModal(true)}>
          <MIcon name="add" size={16} /> {t('factures.new', 'Nova factura')}
        </Button>
      </div>

      <div className="bg-card rounded-2xl border border-outline-variant shadow-sm overflow-hidden">
        {loading ? (
          <div className="p-12 text-center text-secondary-foreground text-sm">{t('common.loading', 'Carregant...')}</div>
        ) : llista.length === 0 ? (
          <div className="p-12 text-center text-secondary-foreground text-sm">{t('factures.empty', 'Cap factura trobada')}</div>
        ) : (
          <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-surface-container-high text-xs text-secondary-foreground border-b border-outline-variant">
              <tr>
                <th className="w-8 px-4 py-3" />
                <SortableTh label={t('pressupostos.col.number', 'Número')} sortKey="numero" sort={sort} onSort={toggleSort} />
                <SortableTh label={t('pressupostos.client', 'Client')} sortKey="client" sort={sort} onSort={toggleSort}
                  filterOptions={distinctValues.client} selected={filters.client} onFilterChange={setFilter} />
                <SortableTh label={t('common.date', 'Data')} sortKey="data" sort={sort} onSort={toggleSort} />
                <SortableTh label={t('factures.col.origin', 'Origen')} sortKey="origen" sort={sort} onSort={toggleSort} align="center"
                  filterOptions={distinctValues.origen} selected={filters.origen} onFilterChange={setFilter} />
                <SortableTh label={t('despeses.col.total', 'Total')} sortKey="total" sort={sort} onSort={toggleSort} align="right" />
                <SortableTh label={t('despeses.col.status', 'Estat')} sortKey="estat" sort={sort} onSort={toggleSort} align="center"
                  filterOptions={distinctValues.estat} selected={filters.estat} onFilterChange={setFilter} />
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-outline-variant">
              {llista.map(f => {
                const isBusy = busy === f.id;
                const numero = `${f.fiscal_year}/${String(f.number).padStart(4, '0')}`;
                return (
                  <>
                    <tr key={f.id} onClick={() => setExpanded(expanded === f.id ? null : f.id)}
                      className={`hover:bg-surface-container-high cursor-pointer transition-colors ${f.status === 'anullada' ? 'opacity-60' : ''}`}>
                      <td className="px-4 py-3 text-secondary-foreground">
                        {expanded === f.id ? <MIcon name="expand_more" size={14} /> : <MIcon name="chevron_right" size={14} />}
                      </td>
                      <td className="px-4 py-3 font-mono text-xs text-secondary-foreground">{numero}</td>
                      <td className="px-4 py-3 font-medium text-on-surface">{f.client_name}</td>
                      <td className="px-4 py-3 text-on-surface-variant">{fmtDate(f.issue_date)}</td>
                      <td className="px-4 py-3 text-center">
                        <span className="inline-flex items-center gap-1 text-xs text-secondary-foreground">
                          <MIcon name={ORIGEN_CFG[f.origen]?.icon} size={13} /> {ORIGEN_CFG[f.origen]?.label}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right font-semibold text-on-surface">{fmtEur(f.total)}</td>
                      <td className="px-4 py-3 text-center">
                        <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${ESTAT_CFG[f.status]?.cls}`}>
                          {ESTAT_CFG[f.status]?.label}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center justify-end gap-1" onClick={e => e.stopPropagation()}>
                          <button title={t('pressupostos.download_pdf', 'Descarregar PDF')} disabled={isBusy}
                            onClick={() => downloadPdf(`/admin/factures/${f.id}/pdf`, `factura_${f.fiscal_year}_${f.number}.pdf`)}
                            className="text-secondary-foreground hover:text-on-surface-variant p-1.5 rounded hover:bg-surface-container-high transition-colors">
                            <MIcon name="download" size={14} />
                          </button>
                          {f.status === 'emesa' && (
                            <button title={t('factures.void', 'Anul·lar')} disabled={isBusy} onClick={() => anullar(f)}
                              className="text-secondary-foreground hover:text-red-600 p-1.5 rounded hover:bg-red-50 transition-colors">
                              <MIcon name="cancel" size={14} />
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                    {expanded === f.id && (
                      <tr key={`${f.id}-exp`}>
                        <td colSpan={8} className="px-6 py-3 bg-surface-container-high/80 border-b border-outline-variant">
                          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs mb-2">
                            {f.client_nif && <div><span className="text-secondary-foreground block">NIF</span>{f.client_nif}</div>}
                            <div><span className="text-secondary-foreground block">{t('despeses.taxable_base', 'Base imposable')}</span>{fmtEur(f.base_total)}</div>
                            <div><span className="text-secondary-foreground block">IVA</span>{fmtEur(f.vat_total)}</div>
                          </div>
                          <table className="w-full text-xs">
                            <thead className="text-secondary-foreground">
                              <tr>
                                <th className="text-left py-1 font-medium">{t('llibres.concept', 'Concepte')}</th>
                                <th className="text-right py-1 font-medium">{t('pressupostos.col.quantity', 'Quant.')}</th>
                                <th className="text-right py-1 font-medium">{t('pressupostos.col.unit_price', 'Preu unit.')}</th>
                                <th className="text-right py-1 font-medium">IVA</th>
                                <th className="text-right py-1 font-medium">{t('despeses.col.total', 'Total')}</th>
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-outline-variant">
                              {f.lines.map(l => (
                                <tr key={l.id}>
                                  <td className="py-1.5 text-on-surface-variant">{l.description}</td>
                                  <td className="py-1.5 text-right text-on-surface-variant">{parseFloat(l.quantity).toFixed(2)}</td>
                                  <td className="py-1.5 text-right text-on-surface-variant">{fmtEur(l.unit_price)}</td>
                                  <td className="py-1.5 text-right text-on-surface-variant">{parseFloat(l.vat_pct).toFixed(0)}%</td>
                                  <td className="py-1.5 text-right text-on-surface">{fmtEur(parseFloat(l.quantity) * parseFloat(l.unit_price))}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                          {f.notes && (
                            <div className="mt-2 text-xs text-secondary-foreground">
                              <span className="text-secondary-foreground">{t('common.notes', 'Notes')}: </span>{f.notes}
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
        <NovaFacturaModal onClose={() => setShowModal(false)} onSaved={() => { setShowModal(false); loadAll(); }} />
      )}
    </div>
  );
}

function NovaFacturaModal({ onClose, onSaved }) {
  const t = useT();
  const [mode, setMode] = useState('manual'); // manual | ticket

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-start justify-center p-4 overflow-y-auto">
      <div className="bg-card rounded-2xl shadow-2xl w-full max-w-2xl my-8">
        <div className="flex items-center justify-between px-6 py-4 border-b border-outline-variant">
          <h3 className="text-lg font-bold text-on-surface">{t('factures.new', 'Nova factura')}</h3>
          <button onClick={onClose} className="text-secondary-foreground hover:text-on-surface-variant p-1 rounded-lg hover:bg-surface-container-high"><MIcon name="close" size={20} /></button>
        </div>
        <div className="px-6 pt-4">
          <div className="flex gap-1 bg-surface-container-high p-1 rounded-xl w-fit">
            <button onClick={() => setMode('manual')}
              className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors ${mode === 'manual' ? 'bg-card shadow-sm text-on-surface' : 'text-on-surface-variant hover:text-on-surface'}`}>
              {t('factures.mode.manual', 'Des de zero')}
            </button>
            <button onClick={() => setMode('ticket')}
              className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors ${mode === 'ticket' ? 'bg-card shadow-sm text-on-surface' : 'text-on-surface-variant hover:text-on-surface'}`}>
              {t('factures.mode.ticket', 'Des de tiquet')}
            </button>
          </div>
        </div>
        {mode === 'manual' ? <FacturaManualForm onClose={onClose} onSaved={onSaved} /> : <FacturaDesDeTiquetForm onClose={onClose} onSaved={onSaved} />}
      </div>
    </div>
  );
}

function FacturaManualForm({ onClose, onSaved }) {
  const t = useT();
  const [clientName, setClientName] = useState('');
  const [clientNif, setClientNif] = useState('');
  const [notes, setNotes] = useState('');
  const [lines, setLines] = useState([{ description: '', quantity: '1', unit_price: '', vat_pct: '21' }]);
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
      client_nif: clientNif || null,
      notes: notes || null,
      lines: lines
        .filter(l => l.description && l.unit_price)
        .map(l => ({
          description: l.description, quantity: parseFloat(l.quantity) || 1,
          unit_price: parseFloat(l.unit_price), vat_pct: parseFloat(l.vat_pct) || 0,
        })),
    };
    const r = await authFetch('/admin/factures', { method: 'POST', body: JSON.stringify(payload) });
    setSaving(false);
    if (r.ok) onSaved();
    else setError((await r.json()).detail || t('common.error_saving', 'Error desant'));
  }

  return (
    <form onSubmit={save} className="p-6 space-y-4">
      <p className="text-xs text-secondary-foreground -mt-1">
        {t('factures.manual_hint', 'Per a un servei fora del catàleg — es comptabilitza automàticament (compte 705).')}
      </p>
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-on-surface-variant mb-1">{t('pressupostos.client_name', 'Nom del client')} *</label>
          <input value={clientName} onChange={e => setClientName(e.target.value)} required
            className="w-full border border-outline-variant rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary" />
        </div>
        <div>
          <label className="block text-sm font-medium text-on-surface-variant mb-1">NIF</label>
          <input value={clientNif} onChange={e => setClientNif(e.target.value)}
            className="w-full border border-outline-variant rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary" />
        </div>
      </div>

      <div className="border border-outline-variant rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-surface-container-high text-xs text-secondary-foreground">
            <tr>
              <th className="px-3 py-2 text-left font-medium">{t('llibres.concept', 'Concepte')}</th>
              <th className="px-3 py-2 text-right font-medium w-20">{t('pressupostos.col.quantity', 'Quant.')}</th>
              <th className="px-3 py-2 text-right font-medium w-24">{t('pressupostos.col.unit_price', 'Preu unit.')}</th>
              <th className="px-3 py-2 text-right font-medium w-20">IVA %</th>
              <th className="w-8" />
            </tr>
          </thead>
          <tbody className="divide-y divide-outline-variant">
            {lines.map((l, i) => (
              <tr key={i}>
                <td className="px-2 py-1.5">
                  <input value={l.description} onChange={e => updateLine(i, 'description', e.target.value)}
                    placeholder={t('factures.line_placeholder', 'Servei de masterització...')}
                    className="w-full border border-outline-variant rounded px-2 py-1 text-sm focus:outline-none focus:ring-1 focus:ring-primary" />
                </td>
                <td className="px-2 py-1.5">
                  <input type="number" step="0.01" value={l.quantity} onChange={e => updateLine(i, 'quantity', e.target.value)}
                    className="w-full border border-outline-variant rounded px-2 py-1 text-sm text-right focus:outline-none focus:ring-1 focus:ring-primary" />
                </td>
                <td className="px-2 py-1.5">
                  <input type="number" step="0.01" value={l.unit_price} onChange={e => updateLine(i, 'unit_price', e.target.value)}
                    className="w-full border border-outline-variant rounded px-2 py-1 text-sm text-right focus:outline-none focus:ring-1 focus:ring-primary" />
                </td>
                <td className="px-2 py-1.5">
                  <input type="number" step="0.01" value={l.vat_pct} onChange={e => updateLine(i, 'vat_pct', e.target.value)}
                    className="w-full border border-outline-variant rounded px-2 py-1 text-sm text-right focus:outline-none focus:ring-1 focus:ring-primary" />
                </td>
                <td className="px-1">
                  {lines.length > 1 && (
                    <button type="button" onClick={() => removeLine(i)} className="text-secondary-foreground hover:text-red-500"><MIcon name="close" size={14} /></button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
          <tfoot className="bg-surface-container-high border-t border-outline-variant">
            <tr>
              <td className="px-3 py-2" colSpan={2}>
                <button type="button" onClick={addLine} className="text-xs text-secondary-foreground hover:text-on-surface font-medium">+ {t('llibres.add_line', 'Afegir línia')}</button>
              </td>
              <td colSpan={3} className="px-3 py-2 text-right text-xs text-secondary-foreground">
                {t('despeses.taxable_base', 'Base imposable')}: <span className="font-semibold text-on-surface-variant">{fmtEur(totals.base)}</span>
                {' · '}IVA: <span className="font-semibold text-on-surface-variant">{fmtEur(totals.iva)}</span>
                {' · '}{t('despeses.col.total', 'Total')}: <span className="font-bold text-on-surface">{fmtEur(totals.total)}</span>
              </td>
            </tr>
          </tfoot>
        </table>
      </div>

      <div>
        <label className="block text-sm font-medium text-on-surface-variant mb-1">{t('common.notes', 'Notes')}</label>
        <textarea value={notes} onChange={e => setNotes(e.target.value)} rows={2}
          className="w-full border border-outline-variant rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary resize-none" />
      </div>

      {error && <p className="text-red-500 text-xs">{error}</p>}
      <div className="flex justify-end gap-3">
        <Button type="button" variant="secondary" onClick={onClose}>{t('common.cancel', "Cancel·lar")}</Button>
        <Button type="submit" disabled={saving}>{saving ? t('common.saving', 'Desant...') : t('factures.create', 'Crear factura')}</Button>
      </div>
    </form>
  );
}

function FacturaDesDeTiquetForm({ onClose, onSaved }) {
  const t = useT();
  const [tipus, setTipus] = useState('order'); // order | venda-externa
  const [id, setId] = useState('');
  const [clientNif, setClientNif] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  async function save(e) {
    e.preventDefault();
    setSaving(true);
    setError('');
    const path = tipus === 'order' ? 'des-de-order' : 'des-de-venda-externa';
    const qs = clientNif ? `?client_nif=${encodeURIComponent(clientNif)}` : '';
    const r = await authFetch(`/admin/factures/${path}/${id.trim()}${qs}`, { method: 'POST' });
    setSaving(false);
    if (r.ok) onSaved();
    else setError((await r.json()).detail || t('common.error_saving', 'Error desant'));
  }

  return (
    <form onSubmit={save} className="p-6 space-y-4">
      <p className="text-xs text-secondary-foreground -mt-1">
        {t('factures.ticket_hint', "Copia l'ID de la comanda (des de Vendes web) o del tiquet (des de TPV) — no genera cap assentament nou, ja es va comptabilitzar en vendre.")}
      </p>
      <div>
        <label className="block text-sm font-medium text-on-surface-variant mb-1">{t('factures.ticket_type', 'Tipus')}</label>
        <div className="flex gap-2">
          <button type="button" onClick={() => setTipus('order')}
            className={`px-4 py-1.5 rounded-lg text-sm border transition-colors ${tipus === 'order' ? 'bg-primary text-white border-primary' : 'bg-card text-on-surface-variant border-outline-variant hover:border-outline'}`}>
            {t('factures.ticket_type.order', 'Comanda web')}
          </button>
          <button type="button" onClick={() => setTipus('venda-externa')}
            className={`px-4 py-1.5 rounded-lg text-sm border transition-colors ${tipus === 'venda-externa' ? 'bg-primary text-white border-primary' : 'bg-card text-on-surface-variant border-outline-variant hover:border-outline'}`}>
            {t('factures.ticket_type.tpv', 'Tiquet TPV')}
          </button>
        </div>
      </div>
      <div>
        <label className="block text-sm font-medium text-on-surface-variant mb-1">
          {tipus === 'order' ? t('factures.order_id', 'ID de la comanda') : t('factures.ticket_id', 'ID del tiquet')} *
        </label>
        <input value={id} onChange={e => setId(e.target.value)} required placeholder="00000000-0000-0000-0000-000000000000"
          className="w-full border border-outline-variant rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-primary" />
      </div>
      <div>
        <label className="block text-sm font-medium text-on-surface-variant mb-1">NIF ({t('common.optional', 'opcional')})</label>
        <input value={clientNif} onChange={e => setClientNif(e.target.value)}
          className="w-full border border-outline-variant rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary" />
      </div>

      {error && <p className="text-red-500 text-xs">{error}</p>}
      <div className="flex justify-end gap-3">
        <Button type="button" variant="secondary" onClick={onClose}>{t('common.cancel', "Cancel·lar")}</Button>
        <Button type="submit" disabled={saving || !id.trim()}>{saving ? t('common.saving', 'Desant...') : t('factures.create', 'Crear factura')}</Button>
      </div>
    </form>
  );
}
