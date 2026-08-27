'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { authFetch } from '../../lib/auth';
import { Button } from '../../../components/ui/button';
import { SortableTh } from '../../../components/admin/table/SortableTh';
import {
  Search, X, Plus, Download, ShoppingBag, Disc3, Package,
  UserCheck, UserX, Mail, MoreHorizontal, ChevronRight,
} from 'lucide-react';

// ─── Helpers ────────────────────────────────────────────────────────────────

function initials(u) {
  if (u.name) return u.name.split(' ').map(p => p[0]).join('').toUpperCase().slice(0, 2);
  return u.email[0].toUpperCase();
}
function displayName(u) { return u.name || u.email; }
const PROVIDER_LABELS = { google: 'Google', magic_link: 'Email', magic: 'Email' };
const fmt = d => new Date(d).toLocaleDateString('ca', { day: '2-digit', month: '2-digit', year: '2-digit' });

// ─── Page ───────────────────────────────────────────────────────────────────

export default function UsuarisPage() {
  const [users, setUsers] = useState([]);
  const [total, setTotal] = useState(0);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState('');
  const [filterActivo, setFilterActivo] = useState('');
  const [filterNewsletter, setFilterNewsletter] = useState('');
  const [filterRol, setFilterRol] = useState('');
  const [selected, setSelected] = useState(null);
  const [showCreate, setShowCreate] = useState(false);
  const [sort, setSort] = useState({ key: null, dir: 'desc' });
  const [pageSize, setPageSize] = useState(50);
  const [page, setPage] = useState(0);

  function toggleSort(key) {
    setSort(prev => {
      if (prev.key !== key) return { key, dir: 'asc' };
      if (prev.dir === 'asc') return { key, dir: 'desc' };
      return { key: null, dir: 'desc' };
    });
    setPage(0);
  }

  const load = useCallback(async () => {
    setLoading(true);
    const params = new URLSearchParams({ limit: String(pageSize), skip: String(page * pageSize) });
    if (q) params.set('q', q);
    if (filterActivo !== '') params.set('active', filterActivo);
    if (filterNewsletter !== '') params.set('newsletter', filterNewsletter);
    if (filterRol !== '') params.set('role', filterRol);
    if (sort.key) { params.set('order_by', sort.key); params.set('order_dir', sort.dir); }
    const [rU, rS] = await Promise.all([
      authFetch(`/admin/users?${params}`),
      authFetch('/admin/users/stats'),
    ]);
    const data = await rU.json();
    setUsers(data.items || []);
    setTotal(data.total || 0);
    setStats(await rS.json());
    setLoading(false);
  }, [q, filterActivo, filterNewsletter, filterRol, sort, pageSize, page]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { setPage(0); }, [q, filterActivo, filterNewsletter, filterRol, pageSize]);

  async function quickPatch(userId, patch) {
    await authFetch(`/admin/users/${userId}`, { method: 'PATCH', body: JSON.stringify(patch) });
    load();
    if (selected?.id === userId) setSelected(prev => ({ ...prev, ...patch }));
  }

  function exportCsv() {
    const token = typeof window !== 'undefined' && localStorage.getItem('access_token');
    const url = `/api/admin/users/export/newsletter`;
    const a = document.createElement('a');
    a.href = url;
    a.setAttribute('download', '');
    // Afegir header x-dev-admin via fetch + blob
    authFetch('/admin/users/export/newsletter').then(async r => {
      const blob = await r.blob();
      const burl = URL.createObjectURL(blob);
      const a2 = document.createElement('a');
      a2.href = burl;
      a2.download = `newsletter_${new Date().toISOString().slice(0,10)}.csv`;
      a2.click();
      URL.revokeObjectURL(burl);
    });
  }

  return (
    <div className="space-y-5 max-w-6xl mx-auto">
      {/* Capçalera */}
      <div className="flex items-start justify-between flex-wrap gap-3">
        <div>
          <h2 className="text-2xl font-bold text-zinc-900">Gestió d'usuaris</h2>
          {stats && (
            <div className="flex flex-wrap gap-4 mt-2">
              <StatPill label="Total" value={stats.total} color="zinc" />
              <StatPill label="Actius" value={stats.actius} color="green" />
              <StatPill label="Inactius" value={stats.inactius} color="red" />
              <StatPill label="Newsletter" value={stats.newsletter} color="zinc" />
              <StatPill label="Admins" value={stats.admins} color="purple" />
            </div>
          )}
        </div>
        <div className="flex gap-2 shrink-0">
          <button onClick={exportCsv}
            className="flex items-center gap-2 px-3 py-2 border border-zinc-300 rounded-xl text-sm text-zinc-600 hover:bg-zinc-50 transition-colors">
            <Download className="w-4 h-4" />
            Exportar newsletter
          </button>
          <Button onClick={() => setShowCreate(true)} className="flex items-center gap-2">
            <Plus className="w-4 h-4" />
            Nou usuari
          </Button>
        </div>
      </div>

      {/* Filtres */}
      <div className="flex flex-wrap gap-2">
        <div className="relative flex-1 min-w-[220px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-400" />
          <input value={q} onChange={e => setQ(e.target.value)}
            placeholder="Nom, email o telèfon..."
            className="w-full pl-9 pr-8 py-2 border border-zinc-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
          {q && (
            <button onClick={() => setQ('')} className="absolute right-3 top-1/2 -translate-y-1/2">
              <X className="w-3.5 h-3.5 text-zinc-400" />
            </button>
          )}
        </div>
        <FilterSelect value={filterActivo} onChange={setFilterActivo} options={[
          ['', 'Tots els estats'], ['true', 'Actius'], ['false', 'Inactius'],
        ]} />
        <FilterSelect value={filterNewsletter} onChange={setFilterNewsletter} options={[
          ['', 'Newsletter: tots'], ['true', 'Subscrits'], ['false', 'No subscrits'],
        ]} />
        <FilterSelect value={filterRol} onChange={setFilterRol} options={[
          ['', 'Tots els rols'], ['cliente', 'Clients'], ['admin', 'Admins'],
        ]} />
        {(q || filterActivo || filterNewsletter || filterRol) && (
          <button onClick={() => { setQ(''); setFilterActivo(''); setFilterNewsletter(''); setFilterRol(''); }}
            className="px-3 py-2 text-sm text-zinc-500 hover:text-zinc-700 flex items-center gap-1">
            <X className="w-3.5 h-3.5" /> Netejar
          </button>
        )}
      </div>

      {/* Taula */}
      <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm overflow-hidden">
        {loading ? (
          <div className="p-12 text-center text-zinc-400 text-sm">Carregant...</div>
        ) : users.length === 0 ? (
          <div className="p-12 text-center">
            <div className="text-zinc-300 text-4xl mb-3">👤</div>
            <div className="text-zinc-500 text-sm">Cap usuari trobat</div>
          </div>
        ) : (
          <>
            <div className="px-4 py-2.5 text-xs text-zinc-400 border-b border-zinc-100 flex items-center justify-between">
              <span>{total} usuaris</span>
              <label className="flex items-center gap-1.5">
                Per pàgina
                <select value={pageSize} onChange={e => setPageSize(Number(e.target.value))}
                  className="border border-zinc-200 rounded-lg px-2 py-1 text-xs bg-white focus:outline-none focus:ring-2 focus:ring-zinc-900">
                  <option value={50}>50</option>
                  <option value={100}>100</option>
                </select>
              </label>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm min-w-[750px]">
                <thead className="bg-zinc-50 text-xs text-zinc-500 border-b border-zinc-100">
                  <tr>
                    <SortableTh label="Usuari" sortKey="nombre" sort={sort} onSort={toggleSort} className="w-[280px]" />
                    <SortableTh label="Accés" sortKey="rol" sort={sort} onSort={toggleSort} />
                    <th className="px-4 py-3 text-right font-medium">Activitat</th>
                    <SortableTh label="NL" sortKey="consent_newsletter" sort={sort} onSort={toggleSort} align="center" />
                    <SortableTh label="Estat" sortKey="activo" sort={sort} onSort={toggleSort} align="center" />
                    <SortableTh label="Alta" sortKey="created_at" sort={sort} onSort={toggleSort} align="right" />
                    <th className="px-4 py-3 w-8" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-100">
                  {users.map(u => {
                    const isSelected = selected?.id === u.id;
                    return (
                      <tr key={u.id}
                        className={`hover:bg-zinc-50 cursor-pointer transition-colors ${isSelected ? 'bg-zinc-50' : ''} ${!u.active ? 'opacity-60' : ''}`}
                        onClick={() => setSelected(isSelected ? null : u)}>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-3">
                            <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold shrink-0 ${
                              u.role === 'admin' ? 'bg-purple-100 text-purple-700' : 'bg-zinc-100 text-zinc-700'
                            }`}>
                              {initials(u)}
                            </div>
                            <div className="min-w-0">
                              <div className="font-medium text-zinc-900 truncate">{displayName(u)}</div>
                              {u.name && <div className="text-xs text-zinc-400 truncate">{u.email}</div>}
                              {u.phone && <div className="text-xs text-zinc-400">{u.phone}</div>}
                            </div>
                          </div>
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex gap-1 flex-wrap">
                            {u.role === 'admin' && (
                              <span className="inline-flex items-center rounded-full px-2 py-0.5 text-xs bg-purple-100 text-purple-700 font-medium">Admin</span>
                            )}
                            {(u.providers || []).map(p => (
                              <span key={p} className="inline-flex items-center rounded-full px-2 py-0.5 text-xs bg-zinc-100 text-zinc-500">
                                {PROVIDER_LABELS[p] || p}
                              </span>
                            ))}
                            {!u.providers?.length && <span className="text-xs text-zinc-300">Manual</span>}
                          </div>
                        </td>
                        <td className="px-4 py-3 text-right">
                          <div className="flex items-center justify-end gap-3">
                            {u.stats?.orders > 0 && (
                              <span className="inline-flex items-center gap-1 text-xs text-zinc-500">
                                <ShoppingBag className="w-3 h-3" />{u.stats.orders}
                              </span>
                            )}
                            {u.stats?.vendes_tpv > 0 && (
                              <span className="inline-flex items-center gap-1 text-xs text-zinc-500">
                                <Disc3 className="w-3 h-3" />{u.stats.vendes_tpv}
                              </span>
                            )}
                            {u.stats?.compres_records > 0 && (
                              <span className="inline-flex items-center gap-1 text-xs text-zinc-500">
                                <Package className="w-3 h-3" />{u.stats.compres_records}
                              </span>
                            )}
                            {!u.stats?.orders && !u.stats?.vendes_tpv && !u.stats?.compres_records && (
                              <span className="text-zinc-300 text-xs">—</span>
                            )}
                          </div>
                        </td>
                        <td className="px-4 py-3 text-center" onClick={e => e.stopPropagation()}>
                          <button
                            onClick={() => quickPatch(u.id, { consent_newsletter: !u.consent_newsletter })}
                            title={u.consent_newsletter ? 'Eliminar de newsletter' : 'Subscriure a newsletter'}
                            className={`w-5 h-5 rounded-full border-2 transition-colors ${
                              u.consent_newsletter
                                ? 'bg-zinc-900 border-zinc-900'
                                : 'bg-white border-zinc-300 hover:border-zinc-400'
                            }`}
                          />
                        </td>
                        <td className="px-4 py-3 text-center" onClick={e => e.stopPropagation()}>
                          <button
                            onClick={() => quickPatch(u.id, { active: !u.active })}
                            title={u.active ? 'Desactivar compte' : 'Reactivar compte'}
                            className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium transition-colors ${
                              u.active
                                ? 'bg-green-100 text-green-700 hover:bg-red-50 hover:text-red-600'
                                : 'bg-zinc-100 text-zinc-500 hover:bg-green-50 hover:text-green-700'
                            }`}>
                            {u.active ? <UserCheck className="w-3 h-3" /> : <UserX className="w-3 h-3" />}
                            {u.active ? 'Actiu' : 'Inactiu'}
                          </button>
                        </td>
                        <td className="px-4 py-3 text-right text-zinc-400 text-xs whitespace-nowrap">
                          {fmt(u.created_at)}
                        </td>
                        <td className="px-4 py-3">
                          <ChevronRight className={`w-4 h-4 transition-transform ${isSelected ? 'rotate-90 text-zinc-900' : 'text-zinc-300'}`} />
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            {total > pageSize && (
              <div className="flex items-center justify-between px-4 py-3 border-t border-zinc-100 text-xs text-zinc-500">
                <span>{page * pageSize + 1}–{Math.min(page * pageSize + pageSize, total)} de {total}</span>
                <div className="flex gap-2">
                  <button onClick={() => setPage(p => Math.max(0, p - 1))} disabled={page === 0}
                    className="px-3 py-1.5 border border-zinc-200 rounded-lg hover:bg-zinc-50 disabled:opacity-40 transition-colors">
                    ← Anterior
                  </button>
                  <button onClick={() => setPage(p => p + 1)} disabled={(page + 1) * pageSize >= total}
                    className="px-3 py-1.5 border border-zinc-200 rounded-lg hover:bg-zinc-50 disabled:opacity-40 transition-colors">
                    Següent →
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </div>

      {/* Panell detall inline */}
      {selected && (
        <UserDetailPanel
          userId={selected.id}
          onClose={() => setSelected(null)}
          onUpdated={updated => {
            setUsers(prev => prev.map(u => u.id === updated.id ? { ...u, ...updated } : u));
          }}
          onDeleted={() => {
            setUsers(prev => prev.filter(u => u.id !== selected.id));
            setSelected(null);
            load();
          }}
        />
      )}

      {/* Modal creació */}
      {showCreate && (
        <CreateUserModal
          onClose={() => setShowCreate(false)}
          onCreated={newUser => {
            setShowCreate(false);
            load();
          }}
        />
      )}
    </div>
  );
}

// ─── Micro-components ────────────────────────────────────────────────────────

function StatPill({ label, value, color }) {
  const colors = {
    zinc: 'bg-zinc-100 text-zinc-700',
    green: 'bg-green-100 text-green-700',
    red: 'bg-red-100 text-red-600',
    purple: 'bg-purple-100 text-purple-700',
  };
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium ${colors[color]}`}>
      <span className="font-bold">{value}</span> {label}
    </span>
  );
}

function FilterSelect({ value, onChange, options }) {
  return (
    <select value={value} onChange={e => onChange(e.target.value)}
      className="border border-zinc-300 rounded-xl px-3 py-2 text-sm text-zinc-700 focus:outline-none focus:ring-2 focus:ring-zinc-900 bg-white">
      {options.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
    </select>
  );
}

// ─── Modal creació ───────────────────────────────────────────────────────────

function CreateUserModal({ onClose, onCreated }) {
  const [form, setForm] = useState({
    email: '', name: '', phone: '', role: 'cliente',
    active: true, consent_newsletter: false, language: 'ca', internal_notes: '',
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));

  async function save(e) {
    e.preventDefault();
    setSaving(true); setError('');
    const r = await authFetch('/admin/users', {
      method: 'POST',
      body: JSON.stringify({
        ...form,
        name: form.name || null,
        phone: form.phone || null,
        internal_notes: form.internal_notes || null,
      }),
    });
    setSaving(false);
    if (r.ok) { onCreated(await r.json()); }
    else {
      const d = await r.json().catch(() => ({}));
      setError(d.detail || 'Error al crear l\'usuari');
    }
  }

  return (
    <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md">
        <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-200">
          <h3 className="text-lg font-bold text-zinc-900">Nou usuari</h3>
          <button onClick={onClose} className="p-1.5 hover:bg-zinc-100 rounded-lg">
            <X className="w-5 h-5 text-zinc-400" />
          </button>
        </div>
        <form onSubmit={save} className="p-6 space-y-4">
          <FormField label="Email *" required>
            <input type="email" required value={form.email} onChange={e => set('email', e.target.value)}
              className={INPUT} placeholder="client@exemple.com" />
          </FormField>
          <div className="grid grid-cols-2 gap-3">
            <FormField label="Nom">
              <input value={form.name} onChange={e => set('name', e.target.value)} className={INPUT} placeholder="Nom i cognoms" />
            </FormField>
            <FormField label="Telèfon">
              <input value={form.phone} onChange={e => set('phone', e.target.value)} className={INPUT} placeholder="+34 600..." />
            </FormField>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <FormField label="Rol">
              <select value={form.role} onChange={e => set('role', e.target.value)} className={INPUT}>
                <option value="cliente">Client</option>
                <option value="admin">Admin</option>
              </select>
            </FormField>
            <FormField label="Idioma">
              <select value={form.language} onChange={e => set('language', e.target.value)} className={INPUT}>
                <option value="ca">Català</option>
                <option value="es">Castellà</option>
                <option value="en">Anglès</option>
              </select>
            </FormField>
          </div>
          <FormField label="Notes internes">
            <textarea value={form.internal_notes} onChange={e => set('internal_notes', e.target.value)}
              rows={2} className={INPUT} placeholder="Nota visible només per admin..." />
          </FormField>
          <div className="flex gap-5">
            <label className="flex items-center gap-2 text-sm text-zinc-700 cursor-pointer">
              <input type="checkbox" checked={form.active} onChange={e => set('active', e.target.checked)}
                className="rounded border-zinc-300 text-zinc-900 focus:ring-zinc-900" />
              Compte actiu
            </label>
            <label className="flex items-center gap-2 text-sm text-zinc-700 cursor-pointer">
              <input type="checkbox" checked={form.consent_newsletter} onChange={e => set('consent_newsletter', e.target.checked)}
                className="rounded border-zinc-300 text-zinc-900 focus:ring-zinc-900" />
              Newsletter
            </label>
          </div>
          {error && <div className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">{error}</div>}
          <div className="flex gap-3 pt-2">
            <button type="button" onClick={onClose}
              className="flex-1 px-4 py-2.5 border border-zinc-300 rounded-xl text-sm text-zinc-600 hover:bg-zinc-50">
              Cancel·lar
            </button>
            <Button type="submit" className="flex-1" disabled={saving}>
              {saving ? 'Creant...' : 'Crear usuari'}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}

const INPUT = "w-full border border-zinc-300 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900";

function FormField({ label, children, required }) {
  return (
    <div>
      <label className="block text-xs font-medium text-zinc-600 mb-1.5">
        {label}{required && <span className="text-red-400 ml-0.5">*</span>}
      </label>
      {children}
    </div>
  );
}

// ─── Panell de detall ────────────────────────────────────────────────────────

function UserDetailPanel({ userId, onClose, onUpdated, onDeleted }) {
  const [user, setUser] = useState(null);
  const [tab, setTab] = useState('perfil');
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState({});
  const [saving, setSaving] = useState(false);
  const [confirmAnon, setConfirmAnon] = useState(false);
  const [anonizing, setAnonizing] = useState(false);
  const [showSetPassword, setShowSetPassword] = useState(false);
  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));

  useEffect(() => {
    setUser(null); setTab('perfil'); setEditing(false); setConfirmAnon(false);
    authFetch(`/admin/users/${userId}`).then(r => r.json()).then(d => {
      setUser(d);
      setForm({
        name: d.name || '', phone: d.phone || '',
        internal_notes: d.internal_notes || '',
        consent_newsletter: d.consent_newsletter,
        active: d.active, role: d.role, language: d.language,
      });
    });
  }, [userId]);

  async function save() {
    setSaving(true);
    const r = await authFetch(`/admin/users/${userId}`, {
      method: 'PATCH',
      body: JSON.stringify({
        name: form.name || null, phone: form.phone || null,
        internal_notes: form.internal_notes || null,
        consent_newsletter: form.consent_newsletter,
        active: form.active, role: form.role, language: form.language,
      }),
    });
    const updated = await r.json();
    setSaving(false); setEditing(false);
    setUser(prev => ({ ...prev, ...updated }));
    onUpdated(updated);
  }

  async function toggleActivo() {
    const r = await authFetch(`/admin/users/${userId}`, {
      method: 'PATCH',
      body: JSON.stringify({ active: !user.active }),
    });
    const updated = await r.json();
    setUser(prev => ({ ...prev, ...updated }));
    onUpdated(updated);
  }

  async function toggleNewsletter() {
    const r = await authFetch(`/admin/users/${userId}`, {
      method: 'PATCH',
      body: JSON.stringify({ consent_newsletter: !user.consent_newsletter }),
    });
    const updated = await r.json();
    setUser(prev => ({ ...prev, ...updated }));
    onUpdated(updated);
  }

  async function anonymize() {
    setAnonizing(true);
    await authFetch(`/admin/users/${userId}/anonymize`, { method: 'POST' });
    setAnonizing(false);
    onDeleted();
  }

  if (!user) return (
    <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm p-8 text-center text-zinc-400 text-sm animate-pulse">
      Carregant...
    </div>
  );

  const totalOrders = (user.orders || []).reduce((s, o) => s + o.total, 0);
  const totalTpv = (user.vendes_tpv || []).reduce((s, v) => s + v.sale_price, 0);
  const totalRecords = (user.compres_records || []).reduce((s, c) => s + c.total_pagat, 0);

  const TABS = [
    { key: 'perfil', label: 'Perfil' },
    { key: 'orders', label: `Comandes (${user.orders?.length || 0})` },
    { key: 'tpv', label: `TPV (${user.vendes_tpv?.length || 0})` },
    { key: 'records', label: `Records venuts (${user.compres_records?.length || 0})` },
  ];

  return (
    <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm overflow-hidden">
      {/* Capçalera */}
      <div className="px-6 py-5 border-b border-zinc-100 flex items-start gap-4">
        <div className={`w-14 h-14 rounded-full flex items-center justify-center text-xl font-bold shrink-0 ${
          user.role === 'admin' ? 'bg-purple-100 text-purple-700' : 'bg-zinc-100 text-zinc-700'
        }`}>
          {initials(user)}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-semibold text-zinc-900 text-lg">{displayName(user)}</span>
            {user.role === 'admin' && (
              <span className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium bg-purple-100 text-purple-700">Admin</span>
            )}
            <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
              user.active ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-600'
            }`}>
              {user.active ? 'Actiu' : 'Inactiu'}
            </span>
            {user.consent_newsletter && (
              <span className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium bg-zinc-100 text-zinc-700">
                <Mail className="w-3 h-3 mr-1" /> Newsletter
              </span>
            )}
          </div>
          {user.name && <div className="text-sm text-zinc-500 mt-0.5">{user.email}</div>}
          {user.phone && <div className="text-sm text-zinc-400">{user.phone}</div>}
          {/* Accions ràpides */}
          <div className="flex gap-2 mt-3 flex-wrap">
            <button onClick={toggleActivo}
              className={`flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg border transition-colors font-medium ${
                user.active
                  ? 'border-red-200 text-red-600 hover:bg-red-50'
                  : 'border-green-200 text-green-600 hover:bg-green-50'
              }`}>
              {user.active ? <><UserX className="w-3.5 h-3.5" /> Desactivar</> : <><UserCheck className="w-3.5 h-3.5" /> Reactivar</>}
            </button>
            <button onClick={toggleNewsletter}
              className={`flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg border transition-colors font-medium ${
                user.consent_newsletter
                  ? 'border-zinc-300 text-zinc-700 hover:bg-zinc-50'
                  : 'border-zinc-200 text-zinc-500 hover:bg-zinc-50'
              }`}>
              <Mail className="w-3.5 h-3.5" />
              {user.consent_newsletter ? 'Donar de baixa NL' : 'Subscriure a NL'}
            </button>
            <button onClick={() => setShowSetPassword(true)}
              className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg border border-zinc-200 text-zinc-500 hover:bg-zinc-50 transition-colors font-medium">
              Assignar contrasenya
            </button>
          </div>
        </div>
        <button onClick={onClose} className="p-2 hover:bg-zinc-100 rounded-lg shrink-0">
          <X className="w-5 h-5 text-zinc-400" />
        </button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 divide-x divide-zinc-100 border-b border-zinc-100 bg-zinc-50">
        <MiniStat icon={<ShoppingBag className="w-4 h-4" />} label="Comandes web" count={user.orders?.length || 0} total={totalOrders} />
        <MiniStat icon={<Disc3 className="w-4 h-4" />} label="Compres TPV" count={user.vendes_tpv?.length || 0} total={totalTpv} />
        <MiniStat icon={<Package className="w-4 h-4" />} label="Records venuts" count={user.compres_records?.length || 0} total={totalRecords} totalLabel="pagat" />
      </div>

      {/* Tabs */}
      <div className="flex border-b border-zinc-100 overflow-x-auto">
        {TABS.map(({ key, label }) => (
          <button key={key} onClick={() => setTab(key)}
            className={`px-5 py-3 text-sm font-medium shrink-0 border-b-2 transition-colors ${
              tab === key ? 'border-zinc-900 text-zinc-900' : 'border-transparent text-zinc-500 hover:text-zinc-700'
            }`}>
            {label}
          </button>
        ))}
      </div>

      {/* Contingut */}
      <div className="p-6">
        {tab === 'perfil' && (
          <div className="space-y-6">
            {editing ? (
              <div className="space-y-4 max-w-md">
                <div className="grid grid-cols-2 gap-3">
                  <FormField label="Nom">
                    <input value={form.name} onChange={e => set('name', e.target.value)} className={INPUT} />
                  </FormField>
                  <FormField label="Telèfon">
                    <input value={form.phone} onChange={e => set('phone', e.target.value)} className={INPUT} />
                  </FormField>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <FormField label="Rol">
                    <select value={form.role} onChange={e => set('role', e.target.value)} className={INPUT}>
                      <option value="cliente">Client</option>
                      <option value="admin">Admin</option>
                    </select>
                  </FormField>
                  <FormField label="Idioma">
                    <select value={form.language} onChange={e => set('language', e.target.value)} className={INPUT}>
                      <option value="ca">Català</option>
                      <option value="es">Castellà</option>
                      <option value="en">Anglès</option>
                    </select>
                  </FormField>
                </div>
                <FormField label="Notes internes">
                  <textarea value={form.internal_notes} onChange={e => set('internal_notes', e.target.value)}
                    rows={3} className={INPUT} placeholder="Visible només per admin..." />
                </FormField>
                <div className="flex gap-5">
                  <label className="flex items-center gap-2 text-sm cursor-pointer">
                    <input type="checkbox" checked={form.consent_newsletter} onChange={e => set('consent_newsletter', e.target.checked)}
                      className="rounded border-zinc-300 text-zinc-900" />
                    Newsletter
                  </label>
                  <label className="flex items-center gap-2 text-sm cursor-pointer">
                    <input type="checkbox" checked={form.active} onChange={e => set('active', e.target.checked)}
                      className="rounded border-zinc-300 text-zinc-900" />
                    Compte actiu
                  </label>
                </div>
                <div className="flex gap-2 pt-2">
                  <Button onClick={save} disabled={saving}>{saving ? 'Guardant...' : 'Guardar canvis'}</Button>
                  <button onClick={() => setEditing(false)} className="px-3 py-1.5 text-sm text-zinc-500 hover:text-zinc-700">
                    Cancel·lar
                  </button>
                </div>
              </div>
            ) : (
              <div className="space-y-3 max-w-md">
                <ProfileRow label="Email" value={user.email} mono />
                <ProfileRow label="Nom" value={user.name || <span className="text-zinc-300">—</span>} />
                <ProfileRow label="Telèfon" value={user.phone || <span className="text-zinc-300">—</span>} />
                <ProfileRow label="Idioma" value={{ ca: 'Català', es: 'Castellà', en: 'Anglès' }[user.language] || user.language} />
                <ProfileRow label="Rol" value={user.role} />
                <ProfileRow label="Alta" value={new Date(user.created_at).toLocaleDateString('ca', { day: '2-digit', month: '2-digit', year: 'numeric' })} />
                {user.providers?.length > 0 && (
                  <ProfileRow label="Accés" value={user.providers.map(p => PROVIDER_LABELS[p] || p).join(', ')} />
                )}
                {user.internal_notes && (
                  <div>
                    <div className="text-xs text-zinc-400 mb-1">Notes internes</div>
                    <div className="text-sm text-zinc-700 bg-zinc-50 rounded-xl p-3 whitespace-pre-wrap">{user.internal_notes}</div>
                  </div>
                )}
                <div className="pt-2">
                  <button onClick={() => setEditing(true)}
                    className="text-sm text-zinc-900 hover:text-zinc-600 font-medium">
                    Editar perfil →
                  </button>
                </div>
              </div>
            )}

            {/* Zona destructiva */}
            <div className="border-t border-zinc-100 pt-6 mt-6">
              <div className="text-xs font-semibold text-zinc-400 uppercase tracking-wide mb-4">Zona perillosa</div>
              {!confirmAnon ? (
                <button onClick={() => setConfirmAnon(true)}
                  className="flex items-center gap-2 text-sm text-red-500 hover:text-red-700 border border-red-200 hover:border-red-300 rounded-xl px-4 py-2.5 transition-colors">
                  <X className="w-4 h-4" />
                  Anonimitzar compte (RGPD)
                </button>
              ) : (
                <div className="bg-red-50 border border-red-200 rounded-xl p-4 space-y-3">
                  <div className="text-sm text-red-800 font-medium">Confirmar anonimització</div>
                  <div className="text-xs text-red-600">
                    S'eliminaran el nom, email, telèfon i notes. Les comandes i l'historial de vendes es conserven (obligació fiscal). Aquesta acció no es pot desfer.
                  </div>
                  <div className="flex gap-2">
                    <button onClick={anonymize} disabled={anonizing}
                      className="px-4 py-2 text-sm bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50 font-medium">
                      {anonizing ? 'Anonimitzant...' : 'Sí, anonimitzar'}
                    </button>
                    <button onClick={() => setConfirmAnon(false)}
                      className="px-4 py-2 text-sm text-zinc-500 hover:text-zinc-700">
                      Cancel·lar
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {tab === 'orders' && (
          <ActivitySection
            items={user.orders || []}
            empty="Sense comandes web"
            renderItem={o => (
              <div key={o.id} className="flex items-start gap-3 py-3 border-b border-zinc-50 last:border-0">
                <div className="w-8 h-8 rounded-lg bg-blue-50 text-blue-500 flex items-center justify-center shrink-0">
                  <ShoppingBag className="w-4 h-4" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between gap-2 mb-0.5">
                    <span className="text-xs text-zinc-400">{fmt(o.created_at)}</span>
                    <div className="flex items-center gap-2">
                      <OrderStatusBadge status={o.status} />
                      <span className="font-semibold text-zinc-900 text-sm">{o.total.toFixed(2)} €</span>
                    </div>
                  </div>
                  <div className="text-xs text-zinc-500">
                    {o.items.map(i => `${i.artista} — ${i.titulo}`).join(' · ')}
                  </div>
                </div>
              </div>
            )}
          />
        )}

        {tab === 'tpv' && (
          <ActivitySection
            items={user.vendes_tpv || []}
            empty="Sense compres en TPV"
            renderItem={v => (
              <div key={v.id} className="flex items-center gap-3 py-3 border-b border-zinc-50 last:border-0">
                <div className="w-8 h-8 rounded-lg bg-zinc-100 text-zinc-700 flex items-center justify-center shrink-0">
                  <Disc3 className="w-4 h-4" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="font-medium text-zinc-900 text-sm truncate">{v.artista} — {v.titulo}</div>
                  <div className="text-xs text-zinc-400">
                    {fmt(v.date)} · {v.channel} ·
                    <span className={`ml-1 ${v.payment_method === 'efectivo' ? 'text-green-600' : 'text-indigo-600'}`}>
                      {v.payment_method}
                    </span>
                  </div>
                </div>
                <span className="font-semibold text-zinc-900 text-sm shrink-0">{v.sale_price.toFixed(2)} €</span>
              </div>
            )}
          />
        )}

        {tab === 'records' && (
          <ActivitySection
            items={user.compres_records || []}
            empty="Sense records venuts a la botiga"
            renderItem={c => (
              <div key={c.id} className="py-3 border-b border-zinc-50 last:border-0">
                <div className="flex items-center justify-between gap-2 mb-1">
                  <span className="text-xs text-zinc-400">{fmt(c.fecha)} · {c.num_items} disc{c.num_items !== 1 ? 'os' : ''}</span>
                  <span className="text-sm font-semibold text-green-700">{c.total_pagat.toFixed(2)} € pagat</span>
                </div>
                <div className="text-xs text-zinc-500">
                  {c.items.map(i => `${i.artista} — ${i.titulo}`).join(' · ')}
                </div>
              </div>
            )}
          />
        )}
      </div>

      {showSetPassword && (
        <SetPasswordModal userId={userId} onClose={() => setShowSetPassword(false)} />
      )}
    </div>
  );
}

function SetPasswordModal({ userId, onClose }) {
  const [password, setPassword] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [done, setDone] = useState(false);

  async function save(e) {
    e.preventDefault();
    setSaving(true); setError('');
    const r = await authFetch(`/admin/users/${userId}/set-password`, {
      method: 'POST',
      body: JSON.stringify({ password }),
    });
    setSaving(false);
    if (r.ok) { setDone(true); }
    else {
      const d = await r.json().catch(() => ({}));
      setError(d.detail || 'Error en assignar la contrasenya');
    }
  }

  return (
    <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-sm">
        <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-200">
          <h3 className="text-lg font-bold text-zinc-900">Assignar contrasenya</h3>
          <button onClick={onClose} className="p-1.5 hover:bg-zinc-100 rounded-lg">
            <X className="w-5 h-5 text-zinc-400" />
          </button>
        </div>
        {done ? (
          <div className="p-6 space-y-4">
            <div className="text-sm text-green-700 bg-green-50 border border-green-200 rounded-xl p-3">
              Contrasenya assignada. Ja pot entrar amb aquest email i contrasenya.
            </div>
            <Button onClick={onClose}>Tancar</Button>
          </div>
        ) : (
          <form onSubmit={save} className="p-6 space-y-4">
            <FormField label="Nova contrasenya *" required>
              <input type="password" required minLength={8} value={password} onChange={e => setPassword(e.target.value)}
                className={INPUT} placeholder="Mínim 8 caràcters" />
            </FormField>
            {error && <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-xl p-3">{error}</div>}
            <div className="flex gap-2">
              <Button type="submit" disabled={saving}>{saving ? 'Guardant...' : 'Assignar'}</Button>
              <button type="button" onClick={onClose} className="px-3 py-1.5 text-sm text-zinc-500 hover:text-zinc-700">
                Cancel·lar
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}

function MiniStat({ icon, label, count, total, totalLabel = 'total' }) {
  return (
    <div className="px-4 py-3 text-center">
      <div className="flex items-center justify-center gap-1.5 text-zinc-400 mb-1">{icon}<span className="text-xs">{label}</span></div>
      <div className="text-xl font-bold text-zinc-900">{count}</div>
      {total > 0 && <div className="text-xs text-zinc-500 font-medium">{totalLabel} {total.toFixed(2)} €</div>}
    </div>
  );
}

function ProfileRow({ label, value, mono }) {
  return (
    <div className="flex items-start gap-3 py-1.5 border-b border-zinc-50">
      <span className="text-xs text-zinc-400 w-20 shrink-0 pt-0.5">{label}</span>
      <span className={`text-sm text-zinc-800 ${mono ? 'font-mono text-xs' : ''}`}>{value}</span>
    </div>
  );
}

function ActivitySection({ items, empty, renderItem }) {
  if (!items.length) return (
    <div className="py-12 text-center text-zinc-400 text-sm">{empty}</div>
  );
  return <div>{items.map(renderItem)}</div>;
}

const STATUS_COLORS = {
  pendiente_pago: 'bg-yellow-100 text-yellow-700',
  pagado: 'bg-blue-100 text-blue-700',
  enviado: 'bg-indigo-100 text-indigo-700',
  entregado: 'bg-green-100 text-green-700',
  cancelado: 'bg-red-100 text-red-600',
};
function OrderStatusBadge({ status }) {
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_COLORS[status] || 'bg-zinc-100 text-zinc-600'}`}>
      {status}
    </span>
  );
}
