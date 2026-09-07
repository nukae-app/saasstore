'use client';

import { useState, useEffect } from 'react';
import { authFetch } from '../../lib/auth';
import { useT } from '../../lib/i18n';
import { Plus, Star } from 'lucide-react';
import { Button } from '../../../components/ui/button';

export default function MargesPage() {
  const t = useT();

  return (
    <div className="space-y-5 max-w-4xl mx-auto">
      <div>
        <h2 className="text-2xl font-bold text-zinc-900">{t('config.tab.margins', 'Marges')}</h2>
      </div>
      <MargesPanel />
    </div>
  );
}

function MargesPanel() {
  const t = useT();
  const [marges, setMarges] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [edit, setEdit] = useState(null);

  async function load() {
    setLoading(true);
    const r = await authFetch('/admin/marges');
    setMarges(await r.json());
    setLoading(false);
  }
  useEffect(() => { load(); }, []);

  async function toggleActiu(m) {
    await authFetch(`/admin/marges/${m.id}`, { method: 'PATCH', body: JSON.stringify({ active: !m.active }) });
    load();
  }

  async function marcarDefecte(m, camp) {
    await authFetch(`/admin/marges/${m.id}`, { method: 'PATCH', body: JSON.stringify({ [camp]: true }) });
    load();
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-zinc-500 max-w-xl">
          {t('config.margins.hint', 'Configura els marges de benefici. El de per defecte segons condició (nou / 2a mà) es fa servir per suggerir el preu de venda a la recepció de compres — sempre editable a mà allà.')}
        </p>
        <Button onClick={() => { setEdit(null); setShowForm(true); }}>
          <Plus size={16} /> {t('config.margins.new', 'Nou marge')}
        </Button>
      </div>

      <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm overflow-hidden">
        {loading ? (
          <div className="p-12 text-center text-zinc-400 text-sm">{t('common.loading')}</div>
        ) : marges.length === 0 ? (
          <div className="p-12 text-center text-zinc-400 text-sm">{t('config.margins.no_margins', 'Cap marge configurat')}</div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-zinc-50 text-xs text-zinc-500 border-b border-zinc-200">
              <tr>
                <th className="px-4 py-3 text-left font-medium">{t('common.name')}</th>
                <th className="px-4 py-3 text-right font-medium">%</th>
                <th className="px-4 py-3 text-center font-medium">{t('config.default_new', 'Per defecte: nou')}</th>
                <th className="px-4 py-3 text-center font-medium">{t('config.default_used', 'Per defecte: 2a mà')}</th>
                <th className="px-4 py-3 text-center font-medium">{t('purchases.col.status', 'Actiu')}</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-100">
              {marges.map(m => (
                <tr key={m.id} className="hover:bg-zinc-50">
                  <td className="px-4 py-3 font-medium text-zinc-900">{m.name}</td>
                  <td className="px-4 py-3 text-right">{parseFloat(m.percentage).toFixed(2)}%</td>
                  <td className="px-4 py-3 text-center">
                    {m.default_new ? (
                      <Star size={16} className="inline text-amber-500 fill-amber-500" />
                    ) : (
                      <button onClick={() => marcarDefecte(m, 'default_new')}
                        className="text-xs text-zinc-400 hover:text-zinc-700 underline">{t('config.use', 'Fer servir')}</button>
                    )}
                  </td>
                  <td className="px-4 py-3 text-center">
                    {m.default_used ? (
                      <Star size={16} className="inline text-amber-500 fill-amber-500" />
                    ) : (
                      <button onClick={() => marcarDefecte(m, 'default_used')}
                        className="text-xs text-zinc-400 hover:text-zinc-700 underline">{t('config.use', 'Fer servir')}</button>
                    )}
                  </td>
                  <td className="px-4 py-3 text-center">
                    <button onClick={() => toggleActiu(m)}
                      className={`px-2 py-0.5 rounded-full text-xs font-medium ${m.active ? 'bg-green-100 text-green-700' : 'bg-zinc-100 text-zinc-500'}`}>
                      {m.active ? t('purchases.supplier.active', 'Actiu') : t('purchases.supplier.inactive', 'Inactiu')}
                    </button>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button onClick={() => { setEdit(m); setShowForm(true); }}
                      className="text-xs text-zinc-400 hover:text-zinc-700 font-medium px-2 py-1 rounded hover:bg-zinc-100">
                      {t('catalog.edit')}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {showForm && (
        <MargeForm marge={edit} onClose={() => setShowForm(false)} onSaved={() => { setShowForm(false); load(); }} />
      )}
    </div>
  );
}

function MargeForm({ marge, onClose, onSaved }) {
  const t = useT();
  const isEdit = !!marge;
  const [name, setName] = useState(marge?.name || '');
  const [percentage, setPercentage] = useState(marge?.percentage || '40.00');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  async function save(e) {
    e.preventDefault();
    setSaving(true);
    setError('');
    const payload = { name, percentage: parseFloat(percentage) };
    const url = isEdit ? `/admin/marges/${marge.id}` : '/admin/marges';
    const method = isEdit ? 'PATCH' : 'POST';
    const r = await authFetch(url, { method, body: JSON.stringify(payload) });
    setSaving(false);
    if (r.ok) onSaved();
    else setError((await r.json()).detail || t('config.save_error', 'Error desant'));
  }

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md">
        <div className="px-6 py-4 border-b border-zinc-200">
          <h3 className="text-lg font-bold text-zinc-900">{isEdit ? t('config.margins.edit_title', 'Editar marge') : t('config.margins.new_title', 'Nou marge')}</h3>
        </div>
        <form onSubmit={save} className="p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-zinc-700 mb-1">{t('config.name_required', 'Nom *')}</label>
            <input value={name} onChange={e => setName(e.target.value)} required
              placeholder={t('config.margins.name_ph', "Marge estàndard nou, marge col·leccionista...")}
              className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
          </div>
          <div>
            <label className="block text-sm font-medium text-zinc-700 mb-1">{t('config.percentage_required', 'Percentatge *')}</label>
            <input type="number" step="0.01" value={percentage} onChange={e => setPercentage(e.target.value)} required
              className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
          </div>
          {error && <p className="text-red-500 text-xs">{error}</p>}
          <div className="flex justify-end gap-3">
            <Button type="button" variant="secondary" onClick={onClose}>{t('common.cancel')}</Button>
            <Button type="submit" disabled={saving}>{saving ? t('common.saving') : isEdit ? t('config.save_changes', 'Desar canvis') : t('common.create')}</Button>
          </div>
        </form>
      </div>
    </div>
  );
}
