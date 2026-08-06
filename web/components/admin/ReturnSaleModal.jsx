'use client';

import { useState } from 'react';
import { authFetch } from '../../app/lib/auth';
import { useT } from '../../app/lib/i18n';
import { Button } from '../ui/button';
import { X } from 'lucide-react';

/**
 * Devolució d'una venda (web o externa). Compartit entre /admin/vendes-web i /admin/tpv
 * perquè ambdós fluxos acaben al mateix endpoint `/admin/devolucions/venta`.
 *
 * `sale` espera: { item_id, artista, titulo, precio, order_item_id? | venta_externa_id?, nombre_cliente? }
 * Exactament un de `order_item_id` / `venta_externa_id` ha d'estar present.
 */
export default function ReturnSaleModal({ sale, onClose, onSaved }) {
  const t = useT();
  const [motivo, setMotivo] = useState('');
  const [destino, setDestino] = useState('disponible');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  async function save(e) {
    e.preventDefault();
    if (!motivo.trim()) { setError(t('return.motivo')); return; }
    setSaving(true);
    const payload = {
      item_id: sale.item_id,
      motivo,
      destino_item: destino,
      fecha: new Date().toISOString(),
      ...(sale.order_item_id
        ? { order_item_id: sale.order_item_id }
        : { venta_externa_id: sale.venta_externa_id }),
    };
    const r = await authFetch('/admin/devolucions/venta', { method: 'POST', body: JSON.stringify(payload) });
    setSaving(false);
    if (r.ok) onSaved();
    else setError((await r.json()).detail ?? 'Error');
  }

  return (
    <div className="fixed inset-0 bg-black/60 z-[60] flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-sm">
        <div className="flex items-center justify-between px-5 py-4 border-b border-zinc-200">
          <h3 className="font-bold text-zinc-900">{t('return.title.sale')}</h3>
          <button onClick={onClose} className="text-zinc-400 hover:text-zinc-600 p-1 rounded-lg hover:bg-zinc-100"><X size={18} /></button>
        </div>
        <form onSubmit={save} className="p-5 space-y-4">
          <div className="p-3 bg-zinc-50 rounded-xl text-sm">
            <span className="font-semibold text-zinc-900">{sale.artista} — {sale.titulo}</span>
            <span className="text-zinc-400 ml-2">{sale.precio} €</span>
            {sale.nombre_cliente && <span className="text-zinc-400 ml-2">· {sale.nombre_cliente}</span>}
          </div>
          <div>
            <label className="block text-sm font-medium text-zinc-700 mb-1">{t('return.motivo')}</label>
            <textarea value={motivo} onChange={e => setMotivo(e.target.value)} rows={2} required
              placeholder={t('return.motivo_ph')}
              className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900 resize-none" />
          </div>
          <div>
            <label className="block text-sm font-medium text-zinc-700 mb-1">{t('return.destino')}</label>
            <select value={destino} onChange={e => setDestino(e.target.value)}
              className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900 bg-white">
              <option value="disponible">{t('return.destino.available')}</option>
              <option value="retirat">{t('return.destino.retired')}</option>
            </select>
          </div>
          {error && <p className="text-red-500 text-xs">{error}</p>}
          <div className="flex gap-3 pt-1">
            <Button type="button" variant="secondary" className="flex-1" onClick={onClose}>{t('common.cancel')}</Button>
            <Button type="submit" className="flex-1" disabled={saving}>
              {saving ? t('return.confirming') : t('return.confirm')}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
