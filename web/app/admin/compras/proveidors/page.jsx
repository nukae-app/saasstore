'use client';

import { useState, useEffect, useMemo } from 'react';
import { authFetch } from '../../../lib/auth';
import { useT } from '../../../lib/i18n';
import { Button } from '../../../../components/ui/button';
import { useSortFilter } from '../../../../components/admin/table/useSortFilter';
import { SortableTh } from '../../../../components/admin/table/SortableTh';
import { Plus, X } from 'lucide-react';

function proveedorTipos(t) {
  return [
    ['distribuidor', t('purchases.supplier.type.dist', 'Distribuïdor')],
    ['proveidor_online', t('purchases.supplier.type.online_provider', 'Proveïdor online')],
    ['subministrador', t('purchases.supplier.type.provider', 'Subministrador')],
    ['professional', t('purchases.supplier.type.professional', 'Professional')],
    ['transport', t('purchases.supplier.type.transport', 'Transport')],
    ['particular', t('purchases.type.individual', 'Particular')],
    ['altres', t('purchases.supplier.type.other', 'Altres')],
  ];
}
function proveedorMetodesPagament(t) {
  return [
    ['transferencia', t('purchases.payment_method.transfer', 'Transferència')],
    ['rebut_domiciliat', t('purchases.payment_method.direct_debit', 'Rebut domiciliat')],
    ['targeta', t('tpv.pago.card')],
    ['efectiu', t('tpv.pago.cash')],
    ['paypal_altres', t('purchases.payment_method.paypal_other', 'PayPal / altres')],
  ];
}

function emptyProveedorForm() {
  return {
    name: '', type: '', nif: '', email: '', phone: '', address: '', contact: '',
    active: true, supplier_iban: '', payment_method: '', payment_days: '', payment_day_of_month: '', notes: '',
  };
}

export default function ProveidorsPage() {
  const t = useT();
  const [proveedores, setProveedores] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [editingProveedor, setEditingProveedor] = useState(null);
  const [provQ, setProvQ] = useState('');

  async function loadAll() {
    setLoading(true);
    const r = await authFetch('/admin/proveedores');
    setProveedores(await r.json());
    setLoading(false);
  }
  useEffect(() => { loadAll(); }, []);

  const proveedoresColumns = useMemo(() => ({
    name: { sortValue: p => (p.name ?? '').toLowerCase() },
    type: { sortValue: p => p.type ?? '', filterValue: p => p.type },
    nif: { sortValue: p => p.nif ?? '' },
    email: { sortValue: p => p.email ?? '' },
    phone: { sortValue: p => p.phone ?? '' },
    active: {
      sortValue: p => p.active ? t('purchases.supplier.active', 'Actiu') : t('purchases.supplier.inactive', 'Inactiu'),
      filterValue: p => p.active ? t('purchases.supplier.active', 'Actiu') : t('purchases.supplier.inactive', 'Inactiu'),
    },
  }), [t]);
  const provQl = provQ.trim().toLowerCase();
  const proveedoresBuscats = useMemo(() => !provQl ? proveedores : proveedores.filter(p =>
    [p.name, p.nif, p.email, p.phone, p.contact].some(v => v && v.toLowerCase().includes(provQl))
  ), [proveedores, provQl]);
  const {
    rows: proveedoresFiltrats, sort: provSort, toggleSort: toggleProvSort,
    filters: provFilters, setFilter: setProvFilter, distinctValues: provDistinct,
  } = useSortFilter(proveedoresBuscats, proveedoresColumns);

  return (
    <div className="space-y-5 max-w-5xl mx-auto">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-zinc-900">{t('purchases.tab.suppliers')}</h2>
        <Button onClick={() => setShowModal(true)}>
          <Plus size={16} /> {t('purchases.new_supplier')}
        </Button>
      </div>

      <input value={provQ} onChange={e => setProvQ(e.target.value)}
        placeholder={t('purchases.supplier_search_ph', 'Cerca per nom, NIF, email, telèfon o contacte...')}
        className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
      <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm overflow-hidden">
        {loading ? (
          <div className="p-12 text-center text-zinc-400 text-sm">{t('common.loading')}</div>
        ) : proveedores.length === 0 ? (
          <div className="p-12 text-center text-zinc-400 text-sm">{t('purchases.no_suppliers')}</div>
        ) : proveedoresFiltrats.length === 0 ? (
          <div className="p-12 text-center text-zinc-400 text-sm">{t('purchases.no_supplier_match', 'Cap proveïdor coincideix amb la cerca.')}</div>
        ) : (
          <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-zinc-50 text-xs text-zinc-500 border-b border-zinc-200">
              <tr>
                <SortableTh label={t('common.name')} sortKey="name" sort={provSort} onSort={toggleProvSort} />
                <SortableTh label={t('common.type')} sortKey="type" sort={provSort} onSort={toggleProvSort}
                  filterOptions={provDistinct.type} selected={provFilters.type} onFilterChange={setProvFilter} />
                <SortableTh label={t('purchases.col.nif', 'NIF')} sortKey="nif" sort={provSort} onSort={toggleProvSort} />
                <SortableTh label={t('purchases.col.email', 'Email')} sortKey="email" sort={provSort} onSort={toggleProvSort} />
                <SortableTh label={t('purchases.col.phone', 'Telèfon')} sortKey="phone" sort={provSort} onSort={toggleProvSort} />
                <SortableTh label={t('purchases.col.status', 'Estat')} sortKey="active" sort={provSort} onSort={toggleProvSort} align="center"
                  filterOptions={provDistinct.active} selected={provFilters.active} onFilterChange={setProvFilter} />
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-100">
              {proveedoresFiltrats.map(p => (
                <tr key={p.id} onClick={() => setEditingProveedor(p)} className="hover:bg-zinc-50 cursor-pointer transition-colors">
                  <td className="px-5 py-3 font-medium">{p.name}</td>
                  <td className="px-5 py-3 text-zinc-500">{p.type ?? '—'}</td>
                  <td className="px-5 py-3 text-zinc-500">{p.nif ?? '—'}</td>
                  <td className="px-5 py-3 text-zinc-500">{p.email ?? '—'}</td>
                  <td className="px-5 py-3 text-zinc-500">{p.phone ?? '—'}</td>
                  <td className="px-5 py-3 text-center">
                    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${p.active ? 'bg-emerald-100 text-emerald-700' : 'bg-zinc-100 text-zinc-500'}`}>
                      {p.active ? t('purchases.supplier.active', 'Actiu') : t('purchases.supplier.inactive', 'Inactiu')}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        )}
      </div>

      {showModal && (
        <ProveedorModal
          proveedor={null}
          onClose={() => setShowModal(false)}
          onSaved={() => { setShowModal(false); loadAll(); }} />
      )}
      {editingProveedor && (
        <ProveedorModal
          proveedor={editingProveedor}
          onClose={() => setEditingProveedor(null)}
          onSaved={() => { setEditingProveedor(null); loadAll(); }} />
      )}
    </div>
  );
}

function ProveedorModal({ proveedor, onClose, onSaved }) {
  const t = useT();
  const isEdit = !!proveedor;
  const [form, setForm] = useState(proveedor ? {
    name: proveedor.name ?? '', type: proveedor.type ?? '', nif: proveedor.nif ?? '',
    email: proveedor.email ?? '', phone: proveedor.phone ?? '', address: proveedor.address ?? '',
    contact: proveedor.contact ?? '', active: proveedor.active ?? true,
    supplier_iban: proveedor.supplier_iban ?? '', payment_method: proveedor.payment_method ?? '',
    payment_days: proveedor.payment_days ?? '', payment_day_of_month: proveedor.payment_day_of_month ?? '',
    notes: proveedor.notes ?? '',
  } : emptyProveedorForm());
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const f = (k, v) => setForm(prev => ({ ...prev, [k]: v }));

  async function save(e) {
    e.preventDefault();
    setSaving(true);
    setError('');
    const payload = {
      name: form.name, type: form.type || null, nif: form.nif || null,
      email: form.email || null, phone: form.phone || null, address: form.address || null,
      contact: form.contact || null, active: form.active,
      supplier_iban: form.supplier_iban || null, payment_method: form.payment_method || null,
      payment_days: form.payment_days ? parseInt(form.payment_days, 10) : null,
      payment_day_of_month: form.payment_day_of_month ? parseInt(form.payment_day_of_month, 10) : null,
      notes: form.notes || null,
    };
    const r = isEdit
      ? await authFetch(`/admin/proveedores/${proveedor.id}`, { method: 'PATCH', body: JSON.stringify(payload) })
      : await authFetch('/admin/proveedores', { method: 'POST', body: JSON.stringify(payload) });
    setSaving(false);
    if (!r.ok) {
      const body = await r.json().catch(() => ({}));
      setError(body.detail || t('purchases.supplier_modal.save_error', 'No s\'ha pogut desar.'));
      return;
    }
    onSaved();
  }

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-start justify-center p-4 overflow-y-auto">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl my-8">
        <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-200">
          <h3 className="font-bold text-zinc-900">{isEdit ? t('purchases.supplier_modal.edit_title', 'Editar proveïdor') : t('purchases.new_supplier')}</h3>
          <button onClick={onClose} className="text-zinc-400 hover:text-zinc-600 p-1 rounded-lg hover:bg-zinc-100"><X size={20} /></button>
        </div>
        <form onSubmit={save} className="p-6 space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div className="col-span-2">
              <label className="block text-sm font-medium text-zinc-700 mb-1">{t('purchases.supplier_modal.name', 'Nom *')}</label>
              <input value={form.name} onChange={e => f('name', e.target.value)} required
                className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
            </div>
            <div>
              <label className="block text-sm font-medium text-zinc-700 mb-1">{t('common.type')}</label>
              <select value={form.type} onChange={e => f('type', e.target.value)}
                className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900 bg-white">
                <option value="">—</option>
                {proveedorTipos(t).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-zinc-700 mb-1">{t('purchases.col.nif', 'NIF')}</label>
              <input value={form.nif} onChange={e => f('nif', e.target.value)}
                className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
            </div>
            <div>
              <label className="block text-sm font-medium text-zinc-700 mb-1">{t('purchases.col.email', 'Email')}</label>
              <input type="email" value={form.email} onChange={e => f('email', e.target.value)}
                className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
            </div>
            <div>
              <label className="block text-sm font-medium text-zinc-700 mb-1">{t('purchases.col.phone', 'Telèfon')}</label>
              <input value={form.phone} onChange={e => f('phone', e.target.value)}
                className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
            </div>
            <div className="col-span-2">
              <label className="block text-sm font-medium text-zinc-700 mb-1">{t('purchases.supplier_modal.address', 'Adreça')}</label>
              <input value={form.address} onChange={e => f('address', e.target.value)}
                className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
            </div>
            <div className="col-span-2">
              <label className="block text-sm font-medium text-zinc-700 mb-1">{t('purchases.supplier_modal.contact_person', 'Persona de contacte')}</label>
              <input value={form.contact} onChange={e => f('contact', e.target.value)}
                className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
            </div>
            <div className="col-span-2">
              <label className="block text-sm font-medium text-zinc-700 mb-1">{t('purchases.supplier_modal.iban', 'Número de compte (IBAN)')}</label>
              <input value={form.supplier_iban} onChange={e => f('supplier_iban', e.target.value)}
                placeholder={t('purchases.supplier_modal.iban_ph', 'ESXX XXXX XXXX XXXX XXXX XXXX')}
                className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
            </div>
            <div>
              <label className="block text-sm font-medium text-zinc-700 mb-1">{t('purchases.supplier_modal.payment_method', 'Mètode de pagament')}</label>
              <select value={form.payment_method} onChange={e => f('payment_method', e.target.value)}
                className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900 bg-white">
                <option value="">—</option>
                {proveedorMetodesPagament(t).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-sm font-medium text-zinc-700 mb-1">{t('purchases.supplier_modal.payment_days', 'Dies de pagament')}</label>
                <input type="number" min="0" value={form.payment_days} onChange={e => f('payment_days', e.target.value)}
                  placeholder={t('purchases.supplier_modal.payment_days_ph', '30, 60...')}
                  className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
              </div>
              <div>
                <label className="block text-sm font-medium text-zinc-700 mb-1">{t('purchases.supplier_modal.fixed_day', 'Dia fix del mes')}</label>
                <input type="number" min="1" max="31" value={form.payment_day_of_month} onChange={e => f('payment_day_of_month', e.target.value)}
                  className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
              </div>
            </div>
            <div className="col-span-2">
              <label className="block text-sm font-medium text-zinc-700 mb-1">{t('common.notes')}</label>
              <textarea value={form.notes} onChange={e => f('notes', e.target.value)} rows={2}
                className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900 resize-none" />
            </div>
            <div className="col-span-2 flex items-center gap-2">
              <input type="checkbox" id="proveedor-actiu" checked={form.active} onChange={e => f('active', e.target.checked)}
                className="rounded border-zinc-300 text-amber-600 focus:ring-zinc-900" />
              <label htmlFor="proveedor-actiu" className="text-sm text-zinc-700">{t('purchases.supplier_modal.active_checkbox', 'Proveïdor actiu')}</label>
            </div>
          </div>
          {error && <p className="text-red-500 text-sm">{error}</p>}
          <div className="flex justify-end gap-3 pt-2">
            <Button type="button" variant="secondary" onClick={onClose}>{t('common.cancel')}</Button>
            <Button type="submit" disabled={saving}>{saving ? t('common.saving') : isEdit ? t('common.save') : t('common.create')}</Button>
          </div>
        </form>
      </div>
    </div>
  );
}
