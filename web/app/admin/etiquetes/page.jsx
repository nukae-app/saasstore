'use client';

import { useState, useEffect } from 'react';
import { authFetch } from '../../lib/auth';
import { Button } from '../../../components/ui/button';
import { Plus, Pencil, Trash2, Check, X, GripVertical } from 'lucide-react';

const DEFAULT_COLORS = [
  '#10b981', '#f59e0b', '#ef4444', '#8b5cf6',
  '#3b82f6', '#ec4899', '#06b6d4', '#84cc16',
];

const EMPTY = { slug: '', nom_ca: '', nom_es: '', color: '#f59e0b', activa: true, posicio: 0 };

export default function EtiquetesPage() {
  const [etiquetes, setEtiquetes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(null); // null | 'new' | etiqueta object
  const [form, setForm] = useState(EMPTY);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  async function load() {
    setLoading(true);
    const r = await authFetch('/admin/etiquetes');
    setEtiquetes(await r.json());
    setLoading(false);
  }

  useEffect(() => { load(); }, []);

  function openNew() {
    setForm({ ...EMPTY, posicio: (etiquetes.length + 1) });
    setEditing('new');
    setError('');
  }

  function openEdit(et) {
    setForm({ slug: et.slug, nom_ca: et.nom_ca, nom_es: et.nom_es || '', color: et.color || '#f59e0b', activa: et.activa, posicio: et.posicio });
    setEditing(et);
    setError('');
  }

  function cancel() {
    setEditing(null);
    setError('');
  }

  async function save() {
    if (!form.slug || !form.nom_ca) { setError('Slug i nom en català són obligatoris'); return; }
    setSaving(true); setError('');
    try {
      const isNew = editing === 'new';
      const url = isNew ? '/admin/etiquetes' : `/admin/etiquetes/${editing.id}`;
      const method = isNew ? 'POST' : 'PUT';
      const r = await authFetch(url, { method, body: JSON.stringify(form) });
      if (!r.ok) {
        const d = await r.json().catch(() => ({}));
        setError(d.detail || 'Error desant');
        return;
      }
      setEditing(null);
      load();
    } finally {
      setSaving(false);
    }
  }

  async function del(et) {
    if (!confirm(`Eliminar etiqueta "${et.nom_ca}"? Es traurà de tots els discos.`)) return;
    await authFetch(`/admin/etiquetes/${et.id}`, { method: 'DELETE' });
    load();
  }

  async function toggleActiva(et) {
    await authFetch(`/admin/etiquetes/${et.id}`, {
      method: 'PUT',
      body: JSON.stringify({ ...et, nom_es: et.nom_es || '', activa: !et.activa }),
    });
    load();
  }

  return (
    <div className="space-y-5 max-w-2xl mx-auto">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-zinc-900">Etiquetes</h2>
        <Button size="sm" onClick={openNew}>
          <Plus size={15} /> Nova etiqueta
        </Button>
      </div>

      {editing && (
        <EtiquetaForm
          form={form}
          setForm={setForm}
          onSave={save}
          onCancel={cancel}
          saving={saving}
          error={error}
          isNew={editing === 'new'}
        />
      )}

      <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm overflow-hidden">
        {loading ? (
          <div className="p-12 text-center text-zinc-400 text-sm">Carregant...</div>
        ) : etiquetes.length === 0 ? (
          <div className="p-12 text-center text-zinc-400 text-sm">Encara no hi ha etiquetes. Crea'n una!</div>
        ) : (
          <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-zinc-50 text-xs text-zinc-500 border-b border-zinc-200">
              <tr>
                <th className="px-4 py-3 text-left font-medium w-6" />
                <th className="px-4 py-3 text-left font-medium">Etiqueta</th>
                <th className="px-4 py-3 text-left font-medium">Slug</th>
                <th className="px-4 py-3 text-left font-medium">Castellà</th>
                <th className="px-4 py-3 text-left font-medium">Activa</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-100">
              {etiquetes.map(et => (
                <tr key={et.id} className="hover:bg-zinc-50 transition-colors">
                  <td className="px-4 py-3 text-zinc-300">
                    <GripVertical size={14} />
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold text-white"
                      style={{ backgroundColor: et.color || '#94a3b8' }}
                    >
                      {et.nom_ca}
                    </span>
                  </td>
                  <td className="px-4 py-3 font-mono text-zinc-500 text-xs">{et.slug}</td>
                  <td className="px-4 py-3 text-zinc-500">{et.nom_es || '—'}</td>
                  <td className="px-4 py-3">
                    <button
                      onClick={() => toggleActiva(et)}
                      className={`w-8 h-4 rounded-full transition-colors relative ${et.activa ? 'bg-green-500' : 'bg-zinc-300'}`}
                    >
                      <span className={`absolute top-0.5 w-3 h-3 rounded-full bg-white shadow transition-all ${et.activa ? 'left-4' : 'left-0.5'}`} />
                    </button>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex justify-end gap-1">
                      <button
                        onClick={() => openEdit(et)}
                        className="p-1.5 rounded-lg text-zinc-400 hover:text-zinc-700 hover:bg-zinc-100 transition-colors"
                      >
                        <Pencil size={14} />
                      </button>
                      <button
                        onClick={() => del(et)}
                        className="p-1.5 rounded-lg text-zinc-400 hover:text-red-600 hover:bg-red-50 transition-colors"
                      >
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
    </div>
  );
}

function EtiquetaForm({ form, setForm, onSave, onCancel, saving, error, isNew }) {
  const f = (k, v) => setForm(p => ({ ...p, [k]: v }));

  return (
    <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm p-5 space-y-4">
      <h3 className="font-semibold text-zinc-900">{isNew ? 'Nova etiqueta' : 'Editar etiqueta'}</h3>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-xs font-medium text-zinc-500 mb-1">Slug <span className="text-red-500">*</span></label>
          <input
            value={form.slug}
            onChange={e => f('slug', e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, '_'))}
            placeholder="novetat"
            className="w-full border border-zinc-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900 font-mono"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-zinc-500 mb-1">Posició</label>
          <input
            type="number" value={form.posicio}
            onChange={e => f('posicio', parseInt(e.target.value) || 0)}
            className="w-full border border-zinc-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-zinc-500 mb-1">Nom català <span className="text-red-500">*</span></label>
          <input
            value={form.nom_ca} onChange={e => f('nom_ca', e.target.value)}
            placeholder="Novetat"
            className="w-full border border-zinc-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-zinc-500 mb-1">Nom castellà</label>
          <input
            value={form.nom_es} onChange={e => f('nom_es', e.target.value)}
            placeholder="Novedad"
            className="w-full border border-zinc-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900"
          />
        </div>
      </div>

      <div>
        <label className="block text-xs font-medium text-zinc-500 mb-2">Color</label>
        <div className="flex items-center gap-2 flex-wrap">
          {DEFAULT_COLORS.map(c => (
            <button
              key={c}
              onClick={() => f('color', c)}
              className={`w-7 h-7 rounded-full transition-transform ${form.color === c ? 'ring-2 ring-offset-2 ring-zinc-400 scale-110' : ''}`}
              style={{ backgroundColor: c }}
            />
          ))}
          <input
            type="color" value={form.color || '#94a3b8'}
            onChange={e => f('color', e.target.value)}
            className="w-7 h-7 rounded-full border border-zinc-200 cursor-pointer"
            title="Color personalitzat"
          />
          <span
            className="ml-2 inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold text-white"
            style={{ backgroundColor: form.color || '#94a3b8' }}
          >
            {form.nom_ca || 'Previsualització'}
          </span>
        </div>
      </div>

      {error && <p className="text-red-500 text-sm">{error}</p>}

      <div className="flex gap-2 pt-1">
        <Button size="sm" onClick={onSave} disabled={saving}>
          <Check size={14} /> {saving ? 'Desant...' : 'Desar'}
        </Button>
        <button onClick={onCancel} className="px-3 py-1.5 text-sm text-zinc-500 hover:text-zinc-700">
          <X size={14} className="inline mr-1" />Cancel·lar
        </button>
      </div>
    </div>
  );
}
