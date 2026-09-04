'use client';

import { useEffect, useState } from 'react';
import { authFetch } from '../../lib/auth';
import { Button } from '../../../components/ui/button';
import { Plus, Pencil, Trash2, Check, X, History } from 'lucide-react';

const EMPTY = {
  code: '', discount_type: 'percentage', discount_value: '', starts_at: '', ends_at: '',
  active: true, max_uses: '', max_uses_per_user: '', min_order_amount: '', combinable_with_offers: false,
};

function toDatetimeLocal(iso) {
  return iso ? new Date(iso).toISOString().slice(0, 16) : '';
}

function toIsoOrNull(local) {
  return local ? new Date(local).toISOString() : null;
}

function formatDiscount(c) {
  return c.discount_type === 'percentage'
    ? `-${parseFloat(c.discount_value)}%`
    : `-${parseFloat(c.discount_value).toFixed(2)} €`;
}

export default function CuponsPage() {
  const [coupons, setCoupons] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(EMPTY);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [redemptions, setRedemptions] = useState(null); // { coupon, rows } | null

  async function load() {
    setLoading(true);
    const r = await authFetch('/admin/coupons');
    setCoupons(await r.json());
    setLoading(false);
  }

  useEffect(() => { load(); }, []);

  function openNew() {
    setForm({ ...EMPTY });
    setEditing('new');
    setError('');
  }

  function openEdit(c) {
    setForm({
      code: c.code, discount_type: c.discount_type, discount_value: String(c.discount_value),
      starts_at: toDatetimeLocal(c.starts_at), ends_at: toDatetimeLocal(c.ends_at), active: c.active,
      max_uses: c.max_uses ?? '', max_uses_per_user: c.max_uses_per_user ?? '',
      min_order_amount: c.min_order_amount ?? '', combinable_with_offers: c.combinable_with_offers,
    });
    setEditing(c);
    setError('');
  }

  function cancel() { setEditing(null); setError(''); }

  async function save() {
    if (!form.code || form.discount_value === '') { setError('Codi i valor del descompte són obligatoris'); return; }
    setSaving(true); setError('');
    try {
      const payload = {
        code: form.code, discount_type: form.discount_type, discount_value: form.discount_value,
        starts_at: toIsoOrNull(form.starts_at), ends_at: toIsoOrNull(form.ends_at), active: form.active,
        max_uses: form.max_uses === '' ? null : Number(form.max_uses),
        max_uses_per_user: form.max_uses_per_user === '' ? null : Number(form.max_uses_per_user),
        min_order_amount: form.min_order_amount === '' ? null : form.min_order_amount,
        combinable_with_offers: form.combinable_with_offers,
      };
      const isNew = editing === 'new';
      const url = isNew ? '/admin/coupons' : `/admin/coupons/${editing.id}`;
      const method = isNew ? 'POST' : 'PUT';
      const r = await authFetch(url, { method, body: JSON.stringify(payload) });
      if (!r.ok) {
        const d = await r.json().catch(() => ({}));
        setError(typeof d.detail === 'string' ? d.detail : 'Error desant el cupó');
        return;
      }
      setEditing(null);
      load();
    } finally {
      setSaving(false);
    }
  }

  async function del(c) {
    if (!confirm(`Eliminar el cupó "${c.code}"?`)) return;
    await authFetch(`/admin/coupons/${c.id}`, { method: 'DELETE' });
    load();
  }

  async function toggleActive(c) {
    await authFetch(`/admin/coupons/${c.id}`, {
      method: 'PUT',
      body: JSON.stringify({
        code: c.code, discount_type: c.discount_type, discount_value: c.discount_value,
        starts_at: c.starts_at, ends_at: c.ends_at, active: !c.active,
        max_uses: c.max_uses, max_uses_per_user: c.max_uses_per_user,
        min_order_amount: c.min_order_amount, combinable_with_offers: c.combinable_with_offers,
      }),
    });
    load();
  }

  async function showRedemptions(c) {
    const r = await authFetch(`/admin/coupons/${c.id}/redemptions`);
    setRedemptions({ coupon: c, rows: await r.json() });
  }

  return (
    <div className="space-y-5 max-w-3xl mx-auto">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-zinc-900">Cupons</h2>
        <Button size="sm" onClick={openNew}>
          <Plus size={15} /> Nou cupó
        </Button>
      </div>

      {editing && (
        <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm p-5 space-y-4">
          <h3 className="font-semibold text-zinc-900">{editing === 'new' ? 'Nou cupó' : 'Editar cupó'}</h3>
          <div className="grid md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-zinc-500 mb-1">Codi <span className="text-red-500">*</span></label>
              <input
                value={form.code} onChange={e => setForm(p => ({ ...p, code: e.target.value.toUpperCase() }))}
                placeholder="BENVINGUDA10"
                className="w-full border border-zinc-200 rounded-xl px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-zinc-900"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-zinc-500 mb-1">Tipus</label>
              <select
                value={form.discount_type} onChange={e => setForm(p => ({ ...p, discount_type: e.target.value }))}
                className="w-full border border-zinc-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900"
              >
                <option value="percentage">Percentatge</option>
                <option value="fixed_amount">Import fix</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-zinc-500 mb-1">
                Valor {form.discount_type === 'percentage' ? '(%)' : '(€)'} <span className="text-red-500">*</span>
              </label>
              <input
                type="number" step="0.01" value={form.discount_value}
                onChange={e => setForm(p => ({ ...p, discount_value: e.target.value }))}
                className="w-full border border-zinc-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-zinc-500 mb-1">Import mínim de comanda (€)</label>
              <input
                type="number" step="0.01" value={form.min_order_amount}
                onChange={e => setForm(p => ({ ...p, min_order_amount: e.target.value }))}
                className="w-full border border-zinc-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-zinc-500 mb-1">Comença (opcional)</label>
              <input
                type="datetime-local" value={form.starts_at} onChange={e => setForm(p => ({ ...p, starts_at: e.target.value }))}
                className="w-full border border-zinc-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-zinc-500 mb-1">Acaba (opcional)</label>
              <input
                type="datetime-local" value={form.ends_at} onChange={e => setForm(p => ({ ...p, ends_at: e.target.value }))}
                className="w-full border border-zinc-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-zinc-500 mb-1">Usos màxims (total)</label>
              <input
                type="number" value={form.max_uses} onChange={e => setForm(p => ({ ...p, max_uses: e.target.value }))}
                placeholder="Il·limitats"
                className="w-full border border-zinc-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-zinc-500 mb-1">Usos màxims per client</label>
              <input
                type="number" value={form.max_uses_per_user} onChange={e => setForm(p => ({ ...p, max_uses_per_user: e.target.value }))}
                placeholder="Il·limitats"
                className="w-full border border-zinc-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900"
              />
            </div>
          </div>

          <div className="flex items-center gap-4">
            <label className="flex items-center gap-2 text-sm text-zinc-700">
              <input type="checkbox" checked={form.active} onChange={e => setForm(p => ({ ...p, active: e.target.checked }))} />
              Actiu
            </label>
            <label className="flex items-center gap-2 text-sm text-zinc-700">
              <input
                type="checkbox" checked={form.combinable_with_offers}
                onChange={e => setForm(p => ({ ...p, combinable_with_offers: e.target.checked }))}
              />
              Combinable amb ofertes de catàleg ja actives
            </label>
          </div>

          {error && <p className="text-red-500 text-sm">{error}</p>}

          <div className="flex gap-2 pt-1">
            <Button size="sm" onClick={save} disabled={saving}>
              <Check size={14} /> {saving ? 'Desant...' : 'Desar'}
            </Button>
            <button onClick={cancel} className="px-3 py-1.5 text-sm text-zinc-500 hover:text-zinc-700">
              <X size={14} className="inline mr-1" />Cancel·lar
            </button>
          </div>
        </div>
      )}

      <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm overflow-hidden">
        {loading ? (
          <div className="p-12 text-center text-zinc-400 text-sm">Carregant...</div>
        ) : coupons.length === 0 ? (
          <div className="p-12 text-center text-zinc-400 text-sm">Encara no hi ha cupons. Crea'n un!</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-zinc-50 text-xs text-zinc-500 border-b border-zinc-200">
                <tr>
                  <th className="px-4 py-3 text-left font-medium">Codi</th>
                  <th className="px-4 py-3 text-left font-medium">Descompte</th>
                  <th className="px-4 py-3 text-left font-medium">Usos</th>
                  <th className="px-4 py-3 text-left font-medium">Vigència</th>
                  <th className="px-4 py-3 text-left font-medium">Actiu</th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {coupons.map(c => (
                  <tr key={c.id} className="hover:bg-zinc-50 transition-colors">
                    <td className="px-4 py-3 font-mono font-medium text-zinc-900">{c.code}</td>
                    <td className="px-4 py-3 text-zinc-600">{formatDiscount(c)}</td>
                    <td className="px-4 py-3 text-zinc-500 text-xs">
                      {c.max_uses != null ? `màx. ${c.max_uses}` : 'il·limitats'}
                      {c.max_uses_per_user != null && ` (${c.max_uses_per_user}/client)`}
                    </td>
                    <td className="px-4 py-3 text-zinc-500 text-xs">
                      {c.starts_at ? new Date(c.starts_at).toLocaleDateString('ca-ES') : 'sempre'}
                      {' → '}
                      {c.ends_at ? new Date(c.ends_at).toLocaleDateString('ca-ES') : 'sense fi'}
                    </td>
                    <td className="px-4 py-3">
                      <button
                        onClick={() => toggleActive(c)}
                        className={`w-8 h-4 rounded-full transition-colors relative ${c.active ? 'bg-green-500' : 'bg-zinc-300'}`}
                      >
                        <span className={`absolute top-0.5 w-3 h-3 rounded-full bg-white shadow transition-all ${c.active ? 'left-4' : 'left-0.5'}`} />
                      </button>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex justify-end gap-1">
                        <button onClick={() => showRedemptions(c)} className="p-1.5 rounded-lg text-zinc-400 hover:text-zinc-700 hover:bg-zinc-100 transition-colors" title="Veure usos">
                          <History size={14} />
                        </button>
                        <button onClick={() => openEdit(c)} className="p-1.5 rounded-lg text-zinc-400 hover:text-zinc-700 hover:bg-zinc-100 transition-colors">
                          <Pencil size={14} />
                        </button>
                        <button onClick={() => del(c)} className="p-1.5 rounded-lg text-zinc-400 hover:text-red-600 hover:bg-red-50 transition-colors">
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {redemptions && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4" onClick={() => setRedemptions(null)}>
          <div className="bg-white rounded-2xl shadow-xl max-w-md w-full p-5 space-y-3" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between">
              <h3 className="font-semibold text-zinc-900">Usos de {redemptions.coupon.code}</h3>
              <button onClick={() => setRedemptions(null)} className="text-zinc-400 hover:text-zinc-700"><X size={16} /></button>
            </div>
            {redemptions.rows.length === 0 ? (
              <p className="text-sm text-zinc-400">Encara no s'ha fet servir.</p>
            ) : (
              <ul className="divide-y divide-zinc-100 max-h-80 overflow-y-auto">
                {redemptions.rows.map(row => (
                  <li key={row.id} className="py-2 text-xs flex items-center justify-between">
                    <span className="text-zinc-500">{new Date(row.created_at).toLocaleString('ca-ES')}</span>
                    <span className="font-medium text-zinc-800">-{parseFloat(row.discount_amount).toFixed(2)} €</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
