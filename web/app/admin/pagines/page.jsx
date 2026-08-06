'use client';

import { useState, useEffect, useCallback } from 'react';
import { authFetch } from '../../lib/auth';
import { Plus, Pencil, Trash2, Eye, EyeOff, GripVertical, Globe, FileText, CalendarDays, List } from 'lucide-react';

const TIPUS_OPTIONS = [
  { value: 'llista-posts', label: 'Llista de posts', icon: List, desc: 'Mostra entrades de blog filtrades per aquesta pàgina' },
  { value: 'estatica',     label: 'Pàgina estàtica', icon: FileText, desc: 'Contingut HTML lliure, editable des de l\'admin' },
  { value: 'agenda',       label: 'Agenda',           icon: CalendarDays, desc: 'Mostra els events programats' },
];

const TIPUS_MAP = Object.fromEntries(TIPUS_OPTIONS.map(t => [t.value, t]));

function TipusIcon({ tipus, size = 14 }) {
  const opt = TIPUS_MAP[tipus];
  if (!opt) return null;
  const Icon = opt.icon;
  return <Icon size={size} />;
}

const EMPTY_FORM = { slug: '', nom: '', tipus: 'llista-posts', posicio: 0, visible_menu: true, contingut: '' };

export default function AdminPaginesPage() {
  const [pagines, setPagines]   = useState([]);
  const [loading, setLoading]   = useState(true);
  const [editing, setEditing]   = useState(null);   // null | {form data}
  const [editId, setEditId]     = useState(null);   // null = nova
  const [saving, setSaving]     = useState(false);
  const [deleting, setDeleting] = useState(null);
  const [err, setErr]           = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await authFetch('/api/admin/pagines');
      setPagines(await r.json());
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  function openNew() {
    setEditId(null);
    setEditing({ ...EMPTY_FORM, posicio: pagines.length });
    setErr('');
  }

  function openEdit(p) {
    setEditId(p.id);
    setEditing({ slug: p.slug, nom: p.nom, tipus: p.tipus, posicio: p.posicio,
                 visible_menu: p.visible_menu, contingut: p.contingut || '' });
    setErr('');
  }

  function cancelEdit() { setEditing(null); setEditId(null); setErr(''); }

  async function save() {
    if (!editing.slug || !editing.nom) { setErr('Slug i nom són obligatoris'); return; }
    setSaving(true); setErr('');
    try {
      const url = editId ? `/api/admin/pagines/${editId}` : '/api/admin/pagines';
      const method = editId ? 'PUT' : 'POST';
      const r = await authFetch(url, { method, headers: { 'Content-Type': 'application/json' },
                                       body: JSON.stringify(editing) });
      if (!r.ok) { const b = await r.json(); setErr(b.detail || 'Error en guardar'); return; }
      await load();
      cancelEdit();
    } finally { setSaving(false); }
  }

  async function deletePagina(id) {
    if (!confirm('Eliminar la pàgina? Els posts NO s\'eliminaran.')) return;
    setDeleting(id);
    try {
      await authFetch(`/api/admin/pagines/${id}`, { method: 'DELETE' });
      await load();
    } finally { setDeleting(null); }
  }

  async function toggleVisible(p) {
    await authFetch(`/api/admin/pagines/${p.id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...p, visible_menu: !p.visible_menu }),
    });
    await load();
  }

  function slugify(nom) {
    return nom.toLowerCase()
      .normalize('NFD').replace(/[̀-ͯ]/g, '')
      .replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
  }

  return (
    <div className="p-6 max-w-3xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold text-zinc-900">Pàgines</h1>
          <p className="text-sm text-zinc-500 mt-0.5">Gestiona les seccions del menú principal</p>
        </div>
        <button onClick={openNew}
          className="flex items-center gap-1.5 bg-zinc-900 text-white text-sm px-4 py-2 rounded-xl hover:bg-zinc-700 transition-colors">
          <Plus size={15} /> Nova pàgina
        </button>
      </div>

      {/* Formulari */}
      {editing && (
        <div className="bg-white rounded-2xl border border-zinc-200 p-6 mb-6 shadow-sm">
          <h2 className="font-semibold text-zinc-800 mb-4">{editId ? 'Editar pàgina' : 'Nova pàgina'}</h2>
          <div className="grid grid-cols-2 gap-4 mb-4">
            <div>
              <label className="block text-xs font-medium text-zinc-600 mb-1">Nom *</label>
              <input value={editing.nom}
                onChange={e => setEditing(v => ({ ...v, nom: e.target.value, slug: editId ? v.slug : slugify(e.target.value) }))}
                className="w-full border border-zinc-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-300"
                placeholder="Ex: Totes les Cançons" />
            </div>
            <div>
              <label className="block text-xs font-medium text-zinc-600 mb-1">Slug (URL) *</label>
              <div className="flex items-center border border-zinc-200 rounded-xl overflow-hidden focus-within:ring-2 focus-within:ring-zinc-300">
                <span className="px-2 text-zinc-400 text-xs border-r border-zinc-100 bg-zinc-50 py-2">/</span>
                <input value={editing.slug}
                  onChange={e => setEditing(v => ({ ...v, slug: e.target.value }))}
                  className="flex-1 px-3 py-2 text-sm focus:outline-none"
                  placeholder="podcast" />
              </div>
            </div>
          </div>

          {/* Tipus */}
          <div className="mb-4">
            <label className="block text-xs font-medium text-zinc-600 mb-2">Tipus de pàgina</label>
            <div className="grid grid-cols-3 gap-2">
              {TIPUS_OPTIONS.map(opt => {
                const Icon = opt.icon;
                const sel = editing.tipus === opt.value;
                return (
                  <button key={opt.value} onClick={() => setEditing(v => ({ ...v, tipus: opt.value }))}
                    className={`flex flex-col items-start gap-1.5 p-3 rounded-xl border text-left transition-colors ${
                      sel ? 'border-zinc-900 bg-zinc-900 text-white' : 'border-zinc-200 hover:border-zinc-300 text-zinc-700'
                    }`}>
                    <Icon size={16} />
                    <span className="text-xs font-semibold">{opt.label}</span>
                    <span className={`text-[10px] leading-tight ${sel ? 'text-zinc-300' : 'text-zinc-400'}`}>{opt.desc}</span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Contingut per estàtiques */}
          {editing.tipus === 'estatica' && (
            <div className="mb-4">
              <label className="block text-xs font-medium text-zinc-600 mb-1">Contingut (HTML)</label>
              <textarea value={editing.contingut}
                onChange={e => setEditing(v => ({ ...v, contingut: e.target.value }))}
                rows={8}
                className="w-full border border-zinc-200 rounded-xl px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-zinc-300"
                placeholder="<p>Contingut de la pàgina...</p>" />
            </div>
          )}

          <div className="flex items-center gap-4 mb-4">
            <div className="flex items-center gap-2">
              <input type="checkbox" id="visible_menu" checked={editing.visible_menu}
                onChange={e => setEditing(v => ({ ...v, visible_menu: e.target.checked }))}
                className="accent-zinc-900" />
              <label htmlFor="visible_menu" className="text-sm text-zinc-600">Visible al menú</label>
            </div>
            <div className="flex items-center gap-2">
              <label className="text-xs text-zinc-500">Posició:</label>
              <input type="number" value={editing.posicio} min={0}
                onChange={e => setEditing(v => ({ ...v, posicio: Number(e.target.value) }))}
                className="w-16 border border-zinc-200 rounded-lg px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-300" />
            </div>
          </div>

          {err && <p className="text-red-500 text-sm mb-3">{err}</p>}

          <div className="flex gap-2">
            <button onClick={save} disabled={saving}
              className="bg-zinc-900 text-white text-sm px-5 py-2 rounded-xl hover:bg-zinc-700 disabled:opacity-50 transition-colors">
              {saving ? 'Guardant…' : editId ? 'Guardar canvis' : 'Crear pàgina'}
            </button>
            <button onClick={cancelEdit}
              className="text-sm px-4 py-2 rounded-xl border border-zinc-200 hover:bg-zinc-50 transition-colors">
              Cancel·lar
            </button>
          </div>
        </div>
      )}

      {/* Llista */}
      {loading ? (
        <p className="text-zinc-400 text-sm">Carregant…</p>
      ) : (
        <div className="flex flex-col gap-2">
          {pagines.map(p => (
            <div key={p.id} className="flex items-center gap-3 bg-white rounded-xl shadow-[0_2px_20px_-6px_rgba(15,23,42,0.08)] px-4 py-3 hover:border-zinc-200 transition-colors">
              <GripVertical size={16} className="text-zinc-300 shrink-0" />

              <div className="flex items-center gap-2 shrink-0 text-zinc-400">
                <TipusIcon tipus={p.tipus} />
              </div>

              <div className="flex-1 min-w-0">
                <span className="font-medium text-zinc-900 text-sm">{p.nom}</span>
                <span className="ml-2 text-xs text-zinc-400">/{p.slug}</span>
                <span className="ml-2 text-[10px] bg-zinc-100 text-zinc-500 px-1.5 py-0.5 rounded-full">
                  {TIPUS_MAP[p.tipus]?.label || p.tipus}
                </span>
              </div>

              <div className="flex items-center gap-1 shrink-0">
                <a href={`/${p.slug}`} target="_blank" rel="noopener"
                  className="p-1.5 text-zinc-400 hover:text-zinc-700 rounded-lg hover:bg-zinc-50 transition-colors">
                  <Globe size={14} />
                </a>
                <button onClick={() => toggleVisible(p)}
                  className={`p-1.5 rounded-lg hover:bg-zinc-50 transition-colors ${p.visible_menu ? 'text-zinc-900' : 'text-zinc-300'}`}
                  title={p.visible_menu ? 'Visible al menú' : 'Ocult del menú'}>
                  {p.visible_menu ? <Eye size={14} /> : <EyeOff size={14} />}
                </button>
                <button onClick={() => openEdit(p)}
                  className="p-1.5 text-zinc-400 hover:text-zinc-700 rounded-lg hover:bg-zinc-50 transition-colors">
                  <Pencil size={14} />
                </button>
                <button onClick={() => deletePagina(p.id)} disabled={deleting === p.id}
                  className="p-1.5 text-zinc-300 hover:text-red-500 rounded-lg hover:bg-red-50 transition-colors">
                  <Trash2 size={14} />
                </button>
              </div>
            </div>
          ))}
          {pagines.length === 0 && (
            <p className="text-zinc-400 text-sm py-8 text-center">Cap pàgina creada. Afegeix-ne una!</p>
          )}
        </div>
      )}
    </div>
  );
}
