'use client';

import { useState, useEffect, useMemo } from 'react';
import { authFetch } from '../../lib/auth';
import { Button } from '../../../components/ui/button';
import { useSortFilter } from '../../../components/admin/table/useSortFilter';
import { SortableTh } from '../../../components/admin/table/SortableTh';
import { Plus, X, Download } from 'lucide-react';
import { useT } from '../../lib/i18n';

function fmtDate(d) {
  if (!d) return '—';
  return new Date(d + 'T00:00:00').toLocaleDateString('ca-ES', { day: '2-digit', month: '2-digit', year: 'numeric' });
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

export default function AlbaransPage() {
  const t = useT();
  const [albarans, setAlbarans] = useState([]);
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);

  async function loadAll() {
    setLoading(true);
    const [aRes, oRes] = await Promise.all([
      authFetch('/admin/albarans'),
      authFetch('/admin/orders'),
    ]);
    setAlbarans(await aRes.json());
    setOrders(await oRes.json());
    setLoading(false);
  }
  useEffect(() => { loadAll(); }, []);

  const ordersById = useMemo(() => Object.fromEntries(orders.map(o => [o.id, o])), [orders]);
  const ordersSenseAlbara = useMemo(() => {
    const ambAlbara = new Set(albarans.map(a => a.order_id));
    return orders.filter(o => !ambAlbara.has(o.id));
  }, [orders, albarans]);

  const columns = useMemo(() => ({
    numero: { sortValue: a => `${a.fiscal_year}${String(a.number).padStart(6, '0')}` },
    client: { sortValue: a => (ordersById[a.order_id]?.email || '').toLowerCase() },
    data: { sortValue: a => a.delivery_date ?? '' },
  }), [ordersById]);

  const { rows: llista, sort, toggleSort } = useSortFilter(albarans, columns);

  return (
    <div className="space-y-5 max-w-5xl mx-auto">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-zinc-900">{t('nav.albarans', 'Albarans')}</h2>
        <Button onClick={() => setShowModal(true)}>
          <Plus size={16} /> {t('albarans.new', 'Nou albarà')}
        </Button>
      </div>

      <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm overflow-hidden">
        {loading ? (
          <div className="p-12 text-center text-zinc-400 text-sm">{t('common.loading', 'Carregant...')}</div>
        ) : llista.length === 0 ? (
          <div className="p-12 text-center text-zinc-400 text-sm">{t('albarans.empty', 'Cap albarà trobat')}</div>
        ) : (
          <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-zinc-50 text-xs text-zinc-500 border-b border-zinc-200">
              <tr>
                <SortableTh label={t('pressupostos.col.number', 'Número')} sortKey="numero" sort={sort} onSort={toggleSort} />
                <SortableTh label={t('pressupostos.client', 'Client')} sortKey="client" sort={sort} onSort={toggleSort} />
                <th className="px-4 py-3 text-left font-medium">{t('albarans.col.order', 'Comanda')}</th>
                <SortableTh label={t('albarans.col.delivery_date', 'Data entrega')} sortKey="data" sort={sort} onSort={toggleSort} />
                <th className="px-4 py-3 text-left font-medium">{t('common.notes', 'Notes')}</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-100">
              {llista.map(a => {
                const order = ordersById[a.order_id];
                return (
                  <tr key={a.id} className="hover:bg-zinc-50 transition-colors">
                    <td className="px-4 py-3 font-mono text-xs text-zinc-500">{a.fiscal_year}/{String(a.number).padStart(4, '0')}</td>
                    <td className="px-4 py-3 font-medium text-zinc-900">{order?.email || '—'}</td>
                    <td className="px-4 py-3 text-zinc-500 text-xs">#{a.order_id.slice(0, 8)}</td>
                    <td className="px-4 py-3 text-zinc-600">{fmtDate(a.delivery_date)}</td>
                    <td className="px-4 py-3 text-zinc-500 text-xs max-w-xs truncate">{a.notes || '—'}</td>
                    <td className="px-4 py-3 text-right">
                      <button title={t('pressupostos.download_pdf', 'Descarregar PDF')}
                        onClick={() => downloadPdf(`/admin/albarans/${a.id}/pdf`, `albara_${a.fiscal_year}_${a.number}.pdf`)}
                        className="text-zinc-400 hover:text-zinc-700 p-1.5 rounded hover:bg-zinc-100 transition-colors">
                        <Download size={14} />
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          </div>
        )}
      </div>

      {showModal && (
        <AlbaraModal
          orders={ordersSenseAlbara}
          onClose={() => setShowModal(false)}
          onSaved={() => { setShowModal(false); loadAll(); }}
        />
      )}
    </div>
  );
}

function AlbaraModal({ orders, onClose, onSaved }) {
  const t = useT();
  const today = new Date().toISOString().slice(0, 10);
  const [orderId, setOrderId] = useState('');
  const [deliveryDate, setDeliveryDate] = useState(today);
  const [notes, setNotes] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  async function save(e) {
    e.preventDefault();
    setSaving(true);
    setError('');
    const r = await authFetch('/admin/albarans', {
      method: 'POST',
      body: JSON.stringify({ order_id: orderId, delivery_date: deliveryDate, notes: notes || null }),
    });
    setSaving(false);
    if (r.ok) onSaved();
    else setError((await r.json()).detail || t('common.error_saving', 'Error desant'));
  }

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-sm">
        <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-200">
          <h3 className="font-bold text-zinc-900">{t('albarans.new', 'Nou albarà')}</h3>
          <button onClick={onClose} className="text-zinc-400 hover:text-zinc-600"><X size={18} /></button>
        </div>
        <form onSubmit={save} className="p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-zinc-700 mb-1">{t('albarans.col.order', 'Comanda')} *</label>
            <select value={orderId} onChange={e => setOrderId(e.target.value)} required
              className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900 bg-white">
              <option value="">{t('albarans.select_order', 'Selecciona una comanda...')}</option>
              {orders.map(o => (
                <option key={o.id} value={o.id}>#{o.id.slice(0, 8)} — {o.email} — {parseFloat(o.total).toFixed(2)} €</option>
              ))}
            </select>
            {orders.length === 0 && (
              <p className="text-xs text-zinc-400 mt-1">{t('albarans.no_pending_orders', 'Totes les comandes ja tenen albarà')}</p>
            )}
          </div>
          <div>
            <label className="block text-sm font-medium text-zinc-700 mb-1">{t('albarans.col.delivery_date', 'Data entrega')}</label>
            <input type="date" value={deliveryDate} onChange={e => setDeliveryDate(e.target.value)}
              className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
          </div>
          <div>
            <label className="block text-sm font-medium text-zinc-700 mb-1">{t('common.notes', 'Notes')}</label>
            <textarea value={notes} onChange={e => setNotes(e.target.value)} rows={2}
              className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900 resize-none" />
          </div>
          {error && <p className="text-red-500 text-xs">{error}</p>}
          <div className="flex justify-end gap-3 pt-2">
            <Button type="button" variant="secondary" onClick={onClose}>{t('common.cancel', "Cancel·lar")}</Button>
            <Button type="submit" disabled={saving || !orderId}>{saving ? t('common.saving', 'Desant...') : t('albarans.create', 'Crear albarà')}</Button>
          </div>
        </form>
      </div>
    </div>
  );
}
