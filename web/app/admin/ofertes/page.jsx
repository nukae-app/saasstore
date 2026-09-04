'use client';

import { useEffect, useMemo, useState } from 'react';
import { authFetch } from '../../lib/auth';
import { useTenantConfig } from '../../../components/store/useTenantConfig';
import { Button } from '../../../components/ui/button';
import { Plus, Pencil, Trash2, Check, X, AlertTriangle, RefreshCw, Search, Loader2 } from 'lucide-react';

const DISCOUNT_LABELS = { percentage: '%', fixed_amount: '€ fixos', fixed_price: 'Preu fixe' };

const EMPTY_CRITERIA = {
  seccio_id: '', etiqueta_id: '', condicion: '', precio_min: '', precio_max: '',
  antiguedad_dias_min: '', sin_venta_dias_min: '', genero: '', artista: '', sello: '', formato: '',
};

const EMPTY_OFFER = {
  name: '', description: '', discount_type: 'percentage', discount_value: '',
  starts_at: '', ends_at: '', active: true, priority: 0, criteria: { ...EMPTY_CRITERIA },
};

function toDatetimeLocal(iso) {
  return iso ? new Date(iso).toISOString().slice(0, 16) : '';
}

function toIsoOrNull(local) {
  return local ? new Date(local).toISOString() : null;
}

function buildCriteriaPayload(c) {
  const out = {};
  if (c.seccio_id) out.seccio_id = Number(c.seccio_id);
  if (c.etiqueta_id) out.etiqueta_id = Number(c.etiqueta_id);
  if (c.condicion) out.condicion = c.condicion;
  if (c.precio_min !== '') out.precio_min = c.precio_min;
  if (c.precio_max !== '') out.precio_max = c.precio_max;
  if (c.antiguedad_dias_min !== '') out.antiguedad_dias_min = Number(c.antiguedad_dias_min);
  if (c.sin_venta_dias_min !== '') out.sin_venta_dias_min = Number(c.sin_venta_dias_min);
  if (c.genero) out.genero = c.genero;
  if (c.artista) out.artista = c.artista;
  if (c.sello) out.sello = c.sello;
  if (c.formato) out.formato = c.formato;
  return out;
}

function formatDiscount(o) {
  if (o.discount_type === 'percentage') return `-${parseFloat(o.discount_value)}%`;
  if (o.discount_type === 'fixed_amount') return `-${parseFloat(o.discount_value).toFixed(2)} €`;
  return `${parseFloat(o.discount_value).toFixed(2)} € fixe`;
}

export default function OfertesPage() {
  const config = useTenantConfig();
  const isVinils = !config || config.vertical === 'records';

  const [offers, setOffers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [seccions, setSeccions] = useState([]);
  const [etiquetes, setEtiquetes] = useState([]);
  const [editing, setEditing] = useState(null); // null | 'new' | offer object
  const [form, setForm] = useState(EMPTY_OFFER);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [recomputing, setRecomputing] = useState(false);
  const [recomputeMsg, setRecomputeMsg] = useState('');

  async function load() {
    setLoading(true);
    const r = await authFetch('/admin/offers');
    setOffers(await r.json());
    setLoading(false);
  }

  useEffect(() => {
    load();
    authFetch('/catalog/seccions').then(r => r.json()).then(setSeccions).catch(() => {});
    authFetch('/catalog/etiquetes').then(r => r.json()).then(setEtiquetes).catch(() => {});
  }, []);

  function openNew() {
    setForm({ ...EMPTY_OFFER, criteria: { ...EMPTY_CRITERIA } });
    setEditing('new');
    setError('');
  }

  function openEdit(offer) {
    setForm({
      name: offer.name, description: offer.description || '',
      discount_type: offer.discount_type, discount_value: String(offer.discount_value),
      starts_at: toDatetimeLocal(offer.starts_at), ends_at: toDatetimeLocal(offer.ends_at),
      active: offer.active, priority: offer.priority,
      criteria: { ...EMPTY_CRITERIA, ...(offer.criteria || {}) },
    });
    setEditing(offer);
    setError('');
  }

  function cancel() {
    setEditing(null);
    setError('');
  }

  async function save() {
    if (!form.name || form.discount_value === '') { setError('Nom i valor del descompte són obligatoris'); return; }
    setSaving(true); setError('');
    try {
      const payload = {
        name: form.name, description: form.description || null,
        discount_type: form.discount_type, discount_value: form.discount_value,
        starts_at: toIsoOrNull(form.starts_at), ends_at: toIsoOrNull(form.ends_at),
        active: form.active, priority: Number(form.priority) || 0,
        criteria: buildCriteriaPayload(form.criteria),
      };
      const isNew = editing === 'new';
      const url = isNew ? '/admin/offers' : `/admin/offers/${editing.id}`;
      const method = isNew ? 'POST' : 'PUT';
      const r = await authFetch(url, { method, body: JSON.stringify(payload) });
      if (!r.ok) {
        const d = await r.json().catch(() => ({}));
        setError(typeof d.detail === 'string' ? d.detail : 'Error desant l’oferta');
        return;
      }
      const saved = await r.json();
      setEditing(saved); // se queda en edición para poder añadir items manuales
      load();
    } finally {
      setSaving(false);
    }
  }

  async function del(offer) {
    if (!confirm(`Eliminar l'oferta "${offer.name}"? Els preus afectats es revertiran.`)) return;
    await authFetch(`/admin/offers/${offer.id}`, { method: 'DELETE' });
    if (editing && editing !== 'new' && editing.id === offer.id) setEditing(null);
    load();
  }

  async function toggleActive(offer) {
    await authFetch(`/admin/offers/${offer.id}`, {
      method: 'PUT',
      body: JSON.stringify({
        name: offer.name, description: offer.description, discount_type: offer.discount_type,
        discount_value: offer.discount_value, starts_at: offer.starts_at, ends_at: offer.ends_at,
        active: !offer.active, priority: offer.priority, criteria: offer.criteria,
      }),
    });
    load();
  }

  async function recompute() {
    setRecomputing(true); setRecomputeMsg('');
    try {
      const r = await authFetch('/admin/offers/recompute', { method: 'POST' });
      const d = await r.json();
      setRecomputeMsg(`${d.applied} aplicats, ${d.reverted} revertits`);
      load();
    } finally {
      setRecomputing(false);
    }
  }

  return (
    <div className="space-y-5 max-w-4xl mx-auto">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h2 className="text-2xl font-bold text-zinc-900">Ofertes</h2>
        <div className="flex items-center gap-2">
          {recomputeMsg && <span className="text-xs text-zinc-500">{recomputeMsg}</span>}
          <Button size="sm" variant="outline" onClick={recompute} disabled={recomputing}>
            <RefreshCw size={14} className={recomputing ? 'animate-spin' : ''} /> Recalcular ara
          </Button>
          <Button size="sm" onClick={openNew}>
            <Plus size={15} /> Nova oferta
          </Button>
        </div>
      </div>

      {editing && (
        <OfferForm
          form={form} setForm={setForm} onSave={save} onCancel={cancel}
          saving={saving} error={error} isNew={editing === 'new'}
          seccions={seccions} etiquetes={etiquetes} isVinils={isVinils}
          offerId={editing === 'new' ? null : editing.id}
          savedOffer={editing === 'new' ? null : editing}
          onOfferItemsChanged={load}
        />
      )}

      <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm overflow-hidden">
        {loading ? (
          <div className="p-12 text-center text-zinc-400 text-sm">Carregant...</div>
        ) : offers.length === 0 ? (
          <div className="p-12 text-center text-zinc-400 text-sm">Encara no hi ha ofertes. Crea'n una!</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-zinc-50 text-xs text-zinc-500 border-b border-zinc-200">
                <tr>
                  <th className="px-4 py-3 text-left font-medium">Oferta</th>
                  <th className="px-4 py-3 text-left font-medium">Descompte</th>
                  <th className="px-4 py-3 text-left font-medium">Prioritat</th>
                  <th className="px-4 py-3 text-left font-medium">Vigència</th>
                  <th className="px-4 py-3 text-left font-medium">Activa</th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {offers.map(o => (
                  <tr key={o.id} className="hover:bg-zinc-50 transition-colors">
                    <td className="px-4 py-3 font-medium text-zinc-900">{o.name}</td>
                    <td className="px-4 py-3 text-zinc-600">{formatDiscount(o)}</td>
                    <td className="px-4 py-3 text-zinc-500 tabular-nums">{o.priority}</td>
                    <td className="px-4 py-3 text-zinc-500 text-xs">
                      {o.starts_at ? new Date(o.starts_at).toLocaleDateString('ca-ES') : 'sempre'}
                      {' → '}
                      {o.ends_at ? new Date(o.ends_at).toLocaleDateString('ca-ES') : 'sense fi'}
                    </td>
                    <td className="px-4 py-3">
                      <button
                        onClick={() => toggleActive(o)}
                        className={`w-8 h-4 rounded-full transition-colors relative ${o.active ? 'bg-green-500' : 'bg-zinc-300'}`}
                      >
                        <span className={`absolute top-0.5 w-3 h-3 rounded-full bg-white shadow transition-all ${o.active ? 'left-4' : 'left-0.5'}`} />
                      </button>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex justify-end gap-1">
                        <button onClick={() => openEdit(o)} className="p-1.5 rounded-lg text-zinc-400 hover:text-zinc-700 hover:bg-zinc-100 transition-colors">
                          <Pencil size={14} />
                        </button>
                        <button onClick={() => del(o)} className="p-1.5 rounded-lg text-zinc-400 hover:text-red-600 hover:bg-red-50 transition-colors">
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

function OfferForm({
  form, setForm, onSave, onCancel, saving, error, isNew,
  seccions, etiquetes, isVinils, offerId, savedOffer, onOfferItemsChanged,
}) {
  const f = (k, v) => setForm(p => ({ ...p, [k]: v }));
  const fc = (k, v) => setForm(p => ({ ...p, criteria: { ...p.criteria, [k]: v } }));

  const [preview, setPreview] = useState(null);
  const [previewing, setPreviewing] = useState(false);
  const [overlaps, setOverlaps] = useState([]);

  const criteriaKey = useMemo(() => JSON.stringify(form.criteria), [form.criteria]);

  useEffect(() => {
    const payload = buildCriteriaPayload(form.criteria);
    setPreviewing(true);
    const timer = setTimeout(async () => {
      try {
        const [pr, ov] = await Promise.all([
          authFetch('/admin/offers/preview', { method: 'POST', body: JSON.stringify(payload) }).then(r => r.json()),
          authFetch('/admin/offers/overlaps', {
            method: 'POST',
            body: JSON.stringify({ ...payload, exclude_offer_id: offerId }),
          }).then(r => r.json()),
        ]);
        setPreview(pr);
        setOverlaps(Array.isArray(ov) ? ov : []);
      } catch {
        setPreview(null);
      } finally {
        setPreviewing(false);
      }
    }, 400);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [criteriaKey, offerId]);

  return (
    <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm p-5 space-y-5">
      <h3 className="font-semibold text-zinc-900">{isNew ? 'Nova oferta' : 'Editar oferta'}</h3>

      <div className="grid md:grid-cols-2 gap-4">
        <div className="md:col-span-2">
          <label className="block text-xs font-medium text-zinc-500 mb-1">Nom <span className="text-red-500">*</span></label>
          <input
            value={form.name} onChange={e => f('name', e.target.value)}
            placeholder="Rebaixes d'hivern"
            className="w-full border border-zinc-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900"
          />
        </div>
        <div className="md:col-span-2">
          <label className="block text-xs font-medium text-zinc-500 mb-1">Descripció</label>
          <input
            value={form.description} onChange={e => f('description', e.target.value)}
            className="w-full border border-zinc-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900"
          />
        </div>

        <div>
          <label className="block text-xs font-medium text-zinc-500 mb-1">Tipus de descompte</label>
          <select
            value={form.discount_type} onChange={e => f('discount_type', e.target.value)}
            className="w-full border border-zinc-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900"
          >
            <option value="percentage">Percentatge</option>
            <option value="fixed_amount">Import fix de descompte</option>
            <option value="fixed_price">Preu fixe final</option>
          </select>
        </div>
        <div>
          <label className="block text-xs font-medium text-zinc-500 mb-1">
            Valor {form.discount_type === 'percentage' ? '(%)' : '(€)'} <span className="text-red-500">*</span>
          </label>
          <input
            type="number" step="0.01" value={form.discount_value}
            onChange={e => f('discount_value', e.target.value)}
            className="w-full border border-zinc-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900"
          />
        </div>

        <div>
          <label className="block text-xs font-medium text-zinc-500 mb-1">Comença (opcional)</label>
          <input
            type="datetime-local" value={form.starts_at} onChange={e => f('starts_at', e.target.value)}
            className="w-full border border-zinc-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-zinc-500 mb-1">Acaba (opcional)</label>
          <input
            type="datetime-local" value={form.ends_at} onChange={e => f('ends_at', e.target.value)}
            className="w-full border border-zinc-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900"
          />
        </div>

        <div>
          <label className="block text-xs font-medium text-zinc-500 mb-1">
            Prioritat
            <span className="text-zinc-400 font-normal"> (guanya la més alta en cas de solapament)</span>
          </label>
          <input
            type="number" value={form.priority} onChange={e => f('priority', e.target.value)}
            className="w-full border border-zinc-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900"
          />
        </div>
        <div className="flex items-end">
          <label className="flex items-center gap-2 text-sm text-zinc-700 pb-2">
            <input type="checkbox" checked={form.active} onChange={e => f('active', e.target.checked)} />
            Activa
          </label>
        </div>
      </div>

      <div className="border-t border-zinc-100 pt-4">
        <p className="text-xs font-semibold text-zinc-500 uppercase tracking-wide mb-3">Criteris (qui queda cobert per aquesta oferta)</p>
        <div className="grid md:grid-cols-3 gap-3">
          <div>
            <label className="block text-xs text-zinc-500 mb-1">Secció</label>
            <select
              value={form.criteria.seccio_id} onChange={e => fc('seccio_id', e.target.value)}
              className="w-full border border-zinc-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900"
            >
              <option value="">Qualsevol</option>
              {seccions.map(s => <option key={s.id} value={s.id}>{s.name_ca}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs text-zinc-500 mb-1">Etiqueta</label>
            <select
              value={form.criteria.etiqueta_id} onChange={e => fc('etiqueta_id', e.target.value)}
              className="w-full border border-zinc-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900"
            >
              <option value="">Qualsevol</option>
              {etiquetes.map(e => <option key={e.id} value={e.id}>{e.name_ca}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs text-zinc-500 mb-1">Condició</label>
            <select
              value={form.criteria.condicion} onChange={e => fc('condicion', e.target.value)}
              className="w-full border border-zinc-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900"
            >
              <option value="">Qualsevol</option>
              <option value="nou">Nou</option>
              <option value="segona_ma">Segona mà</option>
            </select>
          </div>
          <div>
            <label className="block text-xs text-zinc-500 mb-1">Preu mínim actual (€)</label>
            <input
              type="number" step="0.01" value={form.criteria.precio_min} onChange={e => fc('precio_min', e.target.value)}
              className="w-full border border-zinc-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900"
            />
          </div>
          <div>
            <label className="block text-xs text-zinc-500 mb-1">Preu màxim actual (€)</label>
            <input
              type="number" step="0.01" value={form.criteria.precio_max} onChange={e => fc('precio_max', e.target.value)}
              className="w-full border border-zinc-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900"
            />
          </div>
          <div>
            <label className="block text-xs text-zinc-500 mb-1">Antiguitat mínima (dies a catàleg)</label>
            <input
              type="number" value={form.criteria.antiguedad_dias_min} onChange={e => fc('antiguedad_dias_min', e.target.value)}
              className="w-full border border-zinc-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900"
            />
          </div>
          <div>
            <label className="block text-xs text-zinc-500 mb-1">Sense vendre des de fa (dies)</label>
            <input
              type="number" value={form.criteria.sin_venta_dias_min} onChange={e => fc('sin_venta_dias_min', e.target.value)}
              className="w-full border border-zinc-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900"
            />
          </div>
          {isVinils && (
            <>
              <div>
                <label className="block text-xs text-zinc-500 mb-1">Gènere</label>
                <input
                  value={form.criteria.genero} onChange={e => fc('genero', e.target.value)}
                  className="w-full border border-zinc-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900"
                />
              </div>
              <div>
                <label className="block text-xs text-zinc-500 mb-1">Artista</label>
                <input
                  value={form.criteria.artista} onChange={e => fc('artista', e.target.value)}
                  className="w-full border border-zinc-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900"
                />
              </div>
              <div>
                <label className="block text-xs text-zinc-500 mb-1">Segell</label>
                <input
                  value={form.criteria.sello} onChange={e => fc('sello', e.target.value)}
                  className="w-full border border-zinc-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900"
                />
              </div>
              <div>
                <label className="block text-xs text-zinc-500 mb-1">Format</label>
                <input
                  value={form.criteria.formato} onChange={e => fc('formato', e.target.value)}
                  className="w-full border border-zinc-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900"
                />
              </div>
            </>
          )}
        </div>
      </div>

      {/* Previsualització */}
      <div className="bg-zinc-50 rounded-xl p-4 space-y-2">
        <p className="text-sm font-medium text-zinc-700 flex items-center gap-2">
          {previewing ? <Loader2 size={13} className="animate-spin text-zinc-400" /> : null}
          {preview ? `${preview.total_items} article${preview.total_items === 1 ? '' : 's'} coincideixen amb aquests criteris` : 'Calculant...'}
        </p>
        {preview?.sample?.length > 0 && (
          <ul className="text-xs text-zinc-500 space-y-0.5">
            {preview.sample.slice(0, 8).map(it => (
              <li key={it.item_id}>
                {[it.artista, it.title].filter(Boolean).join(' — ')} · {parseFloat(it.price).toFixed(2)} €
              </li>
            ))}
          </ul>
        )}
        {overlaps.length > 0 && (
          <div className="mt-2 flex items-start gap-2 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
            <AlertTriangle size={15} className="text-amber-600 shrink-0 mt-0.5" />
            <div className="text-xs text-amber-800">
              <p className="font-medium">Es solapa amb {overlaps.length} oferta{overlaps.length === 1 ? '' : 's'} activa{overlaps.length === 1 ? '' : 's'}:</p>
              <ul className="mt-1 space-y-0.5">
                {overlaps.map(o => (
                  <li key={o.offer_id}>
                    {o.offer_name} (prioritat {o.priority}) — {o.overlapping_items} article{o.overlapping_items === 1 ? '' : 's'} en comú
                  </li>
                ))}
              </ul>
              <p className="mt-1">Ajusta la prioritat d'aquesta oferta si vols que guanyi ella en cas de conflicte.</p>
            </div>
          </div>
        )}
      </div>

      {!isNew && savedOffer && (
        <ManualItemsSection offer={savedOffer} onChanged={onOfferItemsChanged} />
      )}

      {error && <p className="text-red-500 text-sm">{error}</p>}

      <div className="flex gap-2 pt-1">
        <Button size="sm" onClick={onSave} disabled={saving}>
          <Check size={14} /> {saving ? 'Desant...' : 'Desar'}
        </Button>
        <button onClick={onCancel} className="px-3 py-1.5 text-sm text-zinc-500 hover:text-zinc-700">
          <X size={14} className="inline mr-1" />Tancar
        </button>
      </div>
    </div>
  );
}

function ManualItemsSection({ offer, onChanged }) {
  const [q, setQ] = useState('');
  const [results, setResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [busy, setBusy] = useState(false);

  async function search(query) {
    if (!query.trim()) { setResults([]); return; }
    setSearching(true);
    try {
      const r = await authFetch(`/catalog?q=${encodeURIComponent(query)}&page_size=15`);
      const data = await r.json();
      const items = (data.results ?? []).flatMap(rel =>
        (rel.items ?? []).map(it => ({ ...it, artista: rel.artista, titulo: rel.title }))
      );
      setResults(items);
    } finally {
      setSearching(false);
    }
  }

  let debounce;
  function handleQ(val) {
    setQ(val);
    clearTimeout(debounce);
    debounce = setTimeout(() => search(val), 300);
  }

  async function addOverride(itemId, mode) {
    setBusy(true);
    try {
      await authFetch(`/admin/offers/${offer.id}/items`, {
        method: 'POST', body: JSON.stringify({ item_id: itemId, mode }),
      });
      setQ(''); setResults([]);
      onChanged();
    } finally {
      setBusy(false);
    }
  }

  async function removeOverride(itemId) {
    setBusy(true);
    try {
      await authFetch(`/admin/offers/${offer.id}/items/${itemId}`, { method: 'DELETE' });
      onChanged();
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="border-t border-zinc-100 pt-4">
      <p className="text-xs font-semibold text-zinc-500 uppercase tracking-wide mb-2">
        Ajustos manuals (incloure/excloure articles concrets)
      </p>

      {(offer.items || []).length > 0 && (
        <ul className="mb-3 space-y-1">
          {offer.items.map(oi => (
            <li key={oi.id} className="flex items-center justify-between text-xs bg-zinc-50 rounded-lg px-3 py-1.5">
              <span>
                <span className={`inline-block px-1.5 py-0.5 rounded text-[10px] font-semibold mr-2 ${oi.mode === 'include' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
                  {oi.mode === 'include' ? 'INCLÒS' : 'EXCLÒS'}
                </span>
                <span className="font-mono text-zinc-500">{oi.item_id.slice(0, 8)}…</span>
              </span>
              <button onClick={() => removeOverride(oi.item_id)} disabled={busy} className="text-zinc-400 hover:text-red-600">
                <Trash2 size={13} />
              </button>
            </li>
          ))}
        </ul>
      )}

      <div className="relative">
        <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400" />
        <input
          value={q} onChange={e => handleQ(e.target.value)}
          placeholder="Cerca un disc per afegir-lo o excloure'l a mà..."
          className="w-full border border-zinc-200 rounded-xl pl-9 pr-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900"
        />
      </div>
      {searching && <p className="text-xs text-zinc-400 mt-1">Cercant...</p>}
      {results.length > 0 && (
        <ul className="mt-2 border border-zinc-200 rounded-xl divide-y divide-zinc-100 max-h-56 overflow-y-auto">
          {results.map(it => (
            <li key={it.id} className="flex items-center justify-between gap-2 px-3 py-2 text-xs">
              <span className="truncate">
                {[it.artista, it.titulo].filter(Boolean).join(' — ')}
                <span className="text-zinc-400"> · {parseFloat(it.price).toFixed(2)} € · {it.condition}</span>
              </span>
              <div className="flex gap-1 shrink-0">
                <button
                  onClick={() => addOverride(it.id, 'include')} disabled={busy}
                  className="px-2 py-1 rounded-lg bg-green-50 text-green-700 hover:bg-green-100 text-[11px] font-medium"
                >
                  Incloure
                </button>
                <button
                  onClick={() => addOverride(it.id, 'exclude')} disabled={busy}
                  className="px-2 py-1 rounded-lg bg-red-50 text-red-700 hover:bg-red-100 text-[11px] font-medium"
                >
                  Excloure
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
