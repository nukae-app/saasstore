'use client';

import { useState, useEffect, useMemo } from 'react';
import { authFetch } from '../../lib/auth';
import { Button } from '../../../components/ui/button';
import { useSortFilter } from '../../../components/admin/table/useSortFilter';
import { SortableTh } from '../../../components/admin/table/SortableTh';
import { Plus, X, AlertCircle, Clock, CheckCircle2, ChevronDown, ChevronRight } from 'lucide-react';

const CATEGORIES = [
  { value: 'compres_material', label: 'Compres de material (discos)' },
  { value: 'subministraments', label: 'Subministraments (llum, aigua, gas)' },
  { value: 'lloguer', label: 'Lloguer' },
  { value: 'comunicacions', label: 'Comunicacions (telèfon, internet)' },
  { value: 'serveis_professionals', label: 'Serveis professionals (gestor, etc.)' },
  { value: 'transport', label: 'Transport' },
  { value: 'material_oficina', label: 'Material d\'oficina' },
  { value: 'publicitat', label: 'Publicitat' },
  { value: 'altres', label: 'Altres' },
];
const METODES = [
  { value: 'transferencia', label: 'Transferència bancària' },
  { value: 'rebut_domiciliat', label: 'Rebut domiciliat (SEPA)' },
  { value: 'targeta', label: 'Targeta' },
  { value: 'efectiu', label: 'Efectiu' },
  { value: 'paypal_altres', label: 'PayPal / Altres' },
];

const ESTAT_CONFIG = {
  pendent: { label: 'Pendent', icon: Clock, cls: 'bg-amber-100 text-amber-700' },
  pagat: { label: 'Pagat', icon: CheckCircle2, cls: 'bg-green-100 text-green-700' },
  vencut: { label: 'Vençut', icon: AlertCircle, cls: 'bg-red-100 text-red-700' },
};

function EstatBadge({ estat }) {
  const cfg = ESTAT_CONFIG[estat] || ESTAT_CONFIG.pendent;
  const Icon = cfg.icon;
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium ${cfg.cls}`}>
      <Icon size={11} /> {cfg.label}
    </span>
  );
}

function fmtDate(d) {
  if (!d) return '—';
  return new Date(d + 'T00:00:00').toLocaleDateString('ca-ES', { day: '2-digit', month: '2-digit', year: 'numeric' });
}

function fmtEur(v) {
  return v != null ? parseFloat(v).toFixed(2) + ' €' : '—';
}

export default function DespesesPage() {
  const [despeses, setDespeses] = useState([]);
  const [pendents, setPendents] = useState([]);
  const [proveidors, setProveidors] = useState([]);
  const [tipusIva, setTipusIva] = useState([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState('totes'); // totes | pendents
  const [showModal, setShowModal] = useState(false);
  const [editDespesa, setEditDespesa] = useState(null);
  const [expanded, setExpanded] = useState(null);

  async function loadAll() {
    setLoading(true);
    const [dRes, pRes, provRes, ivaRes] = await Promise.all([
      authFetch('/admin/despeses'),
      authFetch('/admin/despeses/pendents'),
      authFetch('/admin/proveedores'),
      authFetch('/admin/tipus-iva?nomes_actius=true'),
    ]);
    setDespeses(await dRes.json());
    setPendents(await pRes.json());
    setProveidors(await provRes.json());
    setTipusIva(await ivaRes.json());
    setLoading(false);
  }
  useEffect(() => { loadAll(); }, []);

  const baseList = tab === 'pendents' ? pendents : despeses;

  const columns = useMemo(() => ({
    data_factura: { sortValue: d => d.invoice_date ?? '' },
    data_venciment: { sortValue: d => d.due_date ?? '' },
    proveidor_nom: { sortValue: d => (d.supplier_name ?? '').toLowerCase(), filterValue: d => d.supplier_name },
    categoria: {
      sortValue: d => CATEGORIES.find(c => c.value === d.category)?.label || d.category || '',
      filterValue: d => CATEGORIES.find(c => c.value === d.category)?.label || d.category,
    },
    total: { sortValue: d => parseFloat(d.total) || 0 },
    estat_pagament: {
      sortValue: d => ESTAT_CONFIG[d.payment_status]?.label || d.payment_status || '',
      filterValue: d => ESTAT_CONFIG[d.payment_status]?.label || d.payment_status,
    },
  }), []);

  const { rows: llista, sort, toggleSort, filters, setFilter, distinctValues } = useSortFilter(baseList, columns);

  // Totals pendents per al dashboard
  const totalPendent = pendents.filter(d => d.payment_status === 'pendent').reduce((s, d) => s + parseFloat(d.total), 0);
  const totalVençut = pendents.filter(d => d.payment_status === 'vencut').reduce((s, d) => s + parseFloat(d.total), 0);

  return (
    <div className="space-y-5 max-w-6xl mx-auto">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-zinc-900">Despeses i factures</h2>
        <Button onClick={() => { setEditDespesa(null); setShowModal(true); }}>
          <Plus size={16} /> Nova despesa
        </Button>
      </div>

      {/* Resum pendent */}
      {(totalPendent > 0 || totalVençut > 0) && (
        <div className="grid grid-cols-2 gap-3">
          {totalVençut > 0 && (
            <div className="bg-red-50 border border-red-200 rounded-xl p-4 flex items-center gap-3">
              <AlertCircle className="text-red-500 shrink-0" size={22} />
              <div>
                <div className="text-xs text-red-600 font-medium uppercase tracking-wide">Vençudes</div>
                <div className="text-xl font-bold text-red-700">{totalVençut.toFixed(2)} €</div>
              </div>
            </div>
          )}
          {totalPendent > 0 && (
            <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 flex items-center gap-3">
              <Clock className="text-amber-500 shrink-0" size={22} />
              <div>
                <div className="text-xs text-amber-600 font-medium uppercase tracking-wide">Pendents de pagament</div>
                <div className="text-xl font-bold text-amber-700">{totalPendent.toFixed(2)} €</div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Tabs + filtres */}
      <div className="flex items-center gap-4 flex-wrap">
        <div className="flex gap-1 bg-zinc-100 p-1 rounded-xl">
          {[['totes', 'Totes'], ['pendents', `Per pagar (${pendents.length})`]].map(([k, l]) => (
            <button key={k} onClick={() => setTab(k)}
              className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors ${tab === k ? 'bg-white shadow-sm text-zinc-900' : 'text-zinc-600 hover:text-zinc-900'}`}>
              {l}
            </button>
          ))}
        </div>
      </div>

      {/* Taula */}
      <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm overflow-hidden">
        {loading ? (
          <div className="p-12 text-center text-zinc-400 text-sm">Carregant...</div>
        ) : llista.length === 0 ? (
          <div className="p-12 text-center text-zinc-400 text-sm">Cap despesa trobada</div>
        ) : (
          <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-zinc-50 text-xs text-zinc-500 border-b border-zinc-200">
              <tr>
                <th className="w-8 px-4 py-3" />
                <SortableTh label="Data factura" sortKey="data_factura" sort={sort} onSort={toggleSort} />
                <SortableTh label="Venciment" sortKey="data_venciment" sort={sort} onSort={toggleSort} />
                <SortableTh label="Proveïdor" sortKey="proveidor_nom" sort={sort} onSort={toggleSort}
                  filterOptions={distinctValues.proveidor_nom} selected={filters.proveidor_nom} onFilterChange={setFilter} />
                <SortableTh label="Categoria" sortKey="categoria" sort={sort} onSort={toggleSort}
                  filterOptions={distinctValues.categoria} selected={filters.categoria} onFilterChange={setFilter} />
                <SortableTh label="Total" sortKey="total" sort={sort} onSort={toggleSort} align="right" />
                <SortableTh label="Estat" sortKey="estat_pagament" sort={sort} onSort={toggleSort} align="center"
                  filterOptions={distinctValues.estat_pagament} selected={filters.estat_pagament} onFilterChange={setFilter} />
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-100">
              {llista.map(d => (
                <>
                  <tr key={d.id}
                    onClick={() => setExpanded(expanded === d.id ? null : d.id)}
                    className={`hover:bg-zinc-50 cursor-pointer transition-colors ${d.payment_status === 'vencut' ? 'bg-red-50/30' : ''}`}>
                    <td className="px-4 py-3 text-zinc-400">
                      {expanded === d.id ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                    </td>
                    <td className="px-4 py-3 text-zinc-600">{fmtDate(d.invoice_date)}</td>
                    <td className="px-4 py-3">
                      {d.due_date ? (
                        <span className={d.payment_status === 'vencut' ? 'text-red-600 font-medium' : 'text-zinc-600'}>
                          {fmtDate(d.due_date)}
                        </span>
                      ) : '—'}
                    </td>
                    <td className="px-4 py-3 font-medium text-zinc-900">{d.supplier_name}</td>
                    <td className="px-4 py-3 text-zinc-500 text-xs">{CATEGORIES.find(c => c.value === d.category)?.label || d.category}</td>
                    <td className="px-4 py-3 text-right font-semibold text-zinc-900">{fmtEur(d.total)}</td>
                    <td className="px-4 py-3 text-center"><EstatBadge estat={d.payment_status} /></td>
                    <td className="px-4 py-3">
                      <button onClick={e => { e.stopPropagation(); setEditDespesa(d); setShowModal(true); }}
                        className="text-xs text-zinc-400 hover:text-zinc-700 font-medium px-2 py-1 rounded hover:bg-zinc-100 transition-colors">
                        Editar
                      </button>
                    </td>
                  </tr>
                  {expanded === d.id && (
                    <tr key={`${d.id}-exp`}>
                      <td colSpan={8} className="px-6 py-3 bg-zinc-50/80 border-b border-zinc-100">
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                          <div><span className="text-zinc-400 text-xs block">Concepte</span>{d.concept}</div>
                          <div><span className="text-zinc-400 text-xs block">Nº factura</span>{d.invoice_number || '—'}</div>
                          <div><span className="text-zinc-400 text-xs block">Base imposable</span>{fmtEur(d.taxable_base)}</div>
                          <div><span className="text-zinc-400 text-xs block">IVA {d.vat_pct}%</span>{fmtEur(d.vat_amount)}</div>
                          {d.payment_method && <div><span className="text-zinc-400 text-xs block">Mètode pagament</span>{METODES.find(m => m.value === d.payment_method)?.label || d.payment_method}</div>}
                          {d.payment_date && <div><span className="text-zinc-400 text-xs block">Data pagament</span>{fmtDate(d.payment_date)}</div>}
                          {d.notes && <div className="col-span-2"><span className="text-zinc-400 text-xs block">Notes</span>{d.notes}</div>}
                        </div>
                      </td>
                    </tr>
                  )}
                </>
              ))}
            </tbody>
          </table>
          </div>
        )}
      </div>

      {showModal && (
        <DespesaModal
          despesa={editDespesa}
          proveidors={proveidors}
          tipusIva={tipusIva}
          onClose={() => setShowModal(false)}
          onSaved={() => { setShowModal(false); loadAll(); }}
        />
      )}
    </div>
  );
}

function DespesaModal({ despesa, proveidors, tipusIva, onClose, onSaved }) {
  const isEdit = !!despesa;
  const today = new Date().toISOString().slice(0, 10);

  const [proveidorId, setProveidorId] = useState(despesa?.proveidor_id || '');
  const [proveidorNom, setProveidorNom] = useState(despesa?.supplier_name || '');
  const [categoria, setCategoria] = useState(despesa?.category || 'subministraments');
  const [concepte, setConcepte] = useState(despesa?.concept || '');
  const [numFactura, setNumFactura] = useState(despesa?.invoice_number || '');
  const [dataFactura, setDataFactura] = useState(despesa?.invoice_date || today);
  const [dataVenciment, setDataVenciment] = useState(despesa?.due_date || '');
  const [base, setBase] = useState(despesa?.taxable_base || '');
  const [tipusIvaId, setTipusIvaId] = useState(despesa?.tipus_iva_id || '');
  const [ivaPct, setIvaPct] = useState(despesa?.vat_pct || '21.00');
  const [total, setTotal] = useState(despesa?.total || '');
  const [estat, setEstat] = useState(despesa?.payment_status || 'pendent');
  const [dataPagament, setDataPagament] = useState(despesa?.payment_date || '');
  const [metodePagament, setMetodePagament] = useState(despesa?.payment_method || '');
  const [notes, setNotes] = useState(despesa?.notes || '');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  // Auto-calcula total quan canvia base o IVA
  useEffect(() => {
    if (base && ivaPct !== undefined) {
      const b = parseFloat(base) || 0;
      const pct = parseFloat(ivaPct) || 0;
      setTotal((b + b * pct / 100).toFixed(2));
    }
  }, [base, ivaPct]);

  function handleTipusIvaSelect(id) {
    setTipusIvaId(id);
    if (id) {
      const t = tipusIva.find(t => String(t.id) === String(id));
      if (t) setIvaPct(t.percentage);
    }
  }

  // Auto-omplena nom proveïdor quan se selecciona
  function handleProveidorSelect(id) {
    setProveidorId(id);
    if (id) {
      const p = proveidors.find(p => p.id === id);
      if (p) {
        setProveidorNom(p.name);
        if (p.payment_days && dataFactura) {
          const d = new Date(dataFactura);
          d.setDate(d.getDate() + p.payment_days);
          if (p.payment_day_of_month) d.setDate(p.payment_day_of_month);
          setDataVenciment(d.toISOString().slice(0, 10));
        }
        if (p.payment_method) setMetodePagament(p.payment_method);
      }
    }
  }

  async function save(e) {
    e.preventDefault();
    setSaving(true);
    setError('');
    const payload = {
      invoice_number: numFactura || null,
      invoice_date: dataFactura,
      due_date: dataVenciment || null,
      proveidor_id: proveidorId || null,
      supplier_name: proveidorNom,
      category: categoria,
      concept: concepte,
      taxable_base: parseFloat(base),
      tipus_iva_id: tipusIvaId || null,
      vat_pct: parseFloat(ivaPct),
      total: parseFloat(total),
      payment_status: estat,
      payment_date: dataPagament || null,
      payment_method: metodePagament || null,
      notes: notes || null,
    };
    const url = isEdit ? `/admin/despeses/${despesa.id}` : '/admin/despeses';
    const method = isEdit ? 'PATCH' : 'POST';
    const r = await authFetch(url, { method, body: JSON.stringify(payload) });
    setSaving(false);
    if (r.ok) onSaved();
    else setError((await r.json()).detail || 'Error desant');
  }

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-start justify-center p-4 overflow-y-auto">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl my-8">
        <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-200">
          <h3 className="text-lg font-bold text-zinc-900">{isEdit ? 'Editar despesa' : 'Nova despesa'}</h3>
          <button onClick={onClose} className="text-zinc-400 hover:text-zinc-600 p-1 rounded-lg hover:bg-zinc-100"><X size={20} /></button>
        </div>
        <form onSubmit={save} className="p-6 space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-zinc-700 mb-1">Proveïdor (del sistema)</label>
              <select value={proveidorId} onChange={e => handleProveidorSelect(e.target.value)}
                className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900 bg-white">
                <option value="">— Cap (escriu el nom manualment) —</option>
                {proveidors.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-zinc-700 mb-1">Nom proveïdor *</label>
              <input value={proveidorNom} onChange={e => setProveidorNom(e.target.value)} required
                placeholder="Endesa, Gestor Roca..."
                className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
            </div>
            <div>
              <label className="block text-sm font-medium text-zinc-700 mb-1">Categoria *</label>
              <select value={categoria} onChange={e => setCategoria(e.target.value)} required
                className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900 bg-white">
                {CATEGORIES.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-zinc-700 mb-1">Concepte *</label>
              <input value={concepte} onChange={e => setConcepte(e.target.value)} required
                placeholder="Factura llum octubre 2026"
                className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
            </div>
            <div>
              <label className="block text-sm font-medium text-zinc-700 mb-1">Nº factura</label>
              <input value={numFactura} onChange={e => setNumFactura(e.target.value)}
                className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
            </div>
            <div>
              <label className="block text-sm font-medium text-zinc-700 mb-1">Data factura *</label>
              <input type="date" value={dataFactura} onChange={e => setDataFactura(e.target.value)} required
                className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
            </div>
            <div>
              <label className="block text-sm font-medium text-zinc-700 mb-1">Data venciment</label>
              <input type="date" value={dataVenciment} onChange={e => setDataVenciment(e.target.value)}
                className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
            </div>
          </div>

          {/* Imports */}
          <div className="border border-zinc-200 rounded-xl p-4 space-y-3">
            <div className="text-sm font-semibold text-zinc-700">Imports</div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <div>
                <label className="block text-xs text-zinc-500 mb-1">Base imposable *</label>
                <input type="number" step="0.01" value={base} onChange={e => setBase(e.target.value)} required
                  className="w-full border border-zinc-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-zinc-900" />
              </div>
              <div>
                <label className="block text-xs text-zinc-500 mb-1">Tipus d'IVA</label>
                <select value={tipusIvaId} onChange={e => handleTipusIvaSelect(e.target.value)}
                  className="w-full border border-zinc-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-zinc-900 bg-white">
                  <option value="">— Manual —</option>
                  {tipusIva.map(t => <option key={t.id} value={t.id}>{t.name} ({parseFloat(t.percentage).toFixed(0)}%)</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs text-zinc-500 mb-1">IVA %</label>
                <input type="number" step="0.01" value={ivaPct}
                  disabled={!!tipusIvaId}
                  onChange={e => setIvaPct(e.target.value)}
                  className="w-full border border-zinc-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-zinc-900 disabled:bg-zinc-100 disabled:text-zinc-500" />
              </div>
              <div>
                <label className="block text-xs text-zinc-500 mb-1">Total (€)</label>
                <input type="number" step="0.01" value={total} onChange={e => setTotal(e.target.value)} required
                  className="w-full border border-zinc-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-zinc-900 font-semibold" />
              </div>
            </div>
          </div>

          {/* Pagament */}
          <div className="border border-zinc-200 rounded-xl p-4 space-y-3">
            <div className="text-sm font-semibold text-zinc-700">Pagament</div>
            <div className="grid grid-cols-3 gap-3">
              <div>
                <label className="block text-xs text-zinc-500 mb-1">Estat</label>
                <select value={estat} onChange={e => setEstat(e.target.value)}
                  className="w-full border border-zinc-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-zinc-900 bg-white">
                  <option value="pendent">Pendent</option>
                  <option value="pagat">Pagat</option>
                  <option value="vencut">Vençut</option>
                </select>
              </div>
              {estat === 'pagat' && (
                <div>
                  <label className="block text-xs text-zinc-500 mb-1">Data pagament</label>
                  <input type="date" value={dataPagament} onChange={e => setDataPagament(e.target.value)}
                    className="w-full border border-zinc-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-zinc-900" />
                </div>
              )}
              <div>
                <label className="block text-xs text-zinc-500 mb-1">Mètode pagament</label>
                <select value={metodePagament} onChange={e => setMetodePagament(e.target.value)}
                  className="w-full border border-zinc-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-zinc-900 bg-white">
                  <option value="">—</option>
                  {METODES.map(m => <option key={m.value} value={m.value}>{m.label}</option>)}
                </select>
              </div>
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-zinc-700 mb-1">Notes</label>
            <textarea value={notes} onChange={e => setNotes(e.target.value)} rows={2}
              className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900 resize-none" />
          </div>

          {error && <p className="text-red-500 text-xs">{error}</p>}
          <div className="flex justify-end gap-3">
            <Button type="button" variant="secondary" onClick={onClose}>Cancel·lar</Button>
            <Button type="submit" disabled={saving}>{saving ? 'Desant...' : isEdit ? 'Desar canvis' : 'Crear despesa'}</Button>
          </div>
        </form>
      </div>
    </div>
  );
}
