'use client';

import { useState, useEffect, useRef, useMemo } from 'react';
import { authFetch } from '../../../lib/auth';
import { useT } from '../../../lib/i18n';
import { useDiscogsEnabled } from '../../../../components/store/useDiscogsEnabled';
import { useTenantVertical } from '../../../../components/store/useTenantVertical';
import { Button } from '../../../../components/ui/button';
import { useSortFilter } from '../../../../components/admin/table/useSortFilter';
import { SortableTh } from '../../../../components/admin/table/SortableTh';
import { Plus, ChevronDown, ChevronRight, X, Trash2, RotateCcw } from 'lucide-react';
import { GRADINGS } from '../../../../components/admin/compras/shared';
import DevolucionCompraModal from '../../../../components/admin/compras/DevolucionCompraModal';

export default function ParticularsPage() {
  const t = useT();
  const [compras, setCompras] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [expanded, setExpanded] = useState(null);
  const [returnItem, setReturnItem] = useState(null); // { item, compra_id }
  const [filters, setFilters] = useState({ q: '', desde: '', hasta: '' });
  const filterDebounce = useRef(null);

  function buildQuery() {
    const params = new URLSearchParams();
    if (filters.q.trim()) params.set('q', filters.q.trim());
    if (filters.desde) params.set('desde', new Date(filters.desde).toISOString());
    if (filters.hasta) params.set('hasta', new Date(`${filters.hasta}T23:59:59`).toISOString());
    return params.toString();
  }

  async function loadAll() {
    setLoading(true);
    const qs = buildQuery();
    const r = await authFetch(`/admin/compras?tipo=particular${qs ? `&${qs}` : ''}`);
    setCompras(await r.json());
    setLoading(false);
  }

  useEffect(() => {
    clearTimeout(filterDebounce.current);
    const hasFilters = filters.q || filters.desde || filters.hasta;
    filterDebounce.current = setTimeout(loadAll, hasFilters ? 300 : 0);
    return () => clearTimeout(filterDebounce.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters]);

  const hasFilters = !!(filters.q || filters.desde || filters.hasta);

  const columns = useMemo(() => ({
    fecha: { sortValue: c => c.date ?? '' },
    entitat: { sortValue: c => (c.individual_name ?? c.user_nom ?? '').toLowerCase() },
    linies: { sortValue: c => c.items?.length ?? 0 },
  }), []);
  const { rows: comprasSorted, sort, toggleSort } = useSortFilter(compras, columns);

  return (
    <div className="space-y-5 max-w-5xl mx-auto">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-zinc-900">{t('purchases.tab.particulars', 'Compres particulars')}</h2>
        <Button onClick={() => setShowModal(true)}>
          <Plus size={16} /> {t('purchases.btn.individual_purchase', 'Compra particular')}
        </Button>
      </div>

      <div className="flex items-center gap-2 flex-wrap">
        <input value={filters.q} onChange={e => setFilters(f => ({ ...f, q: e.target.value }))}
          placeholder={t('purchases.filter.search_ph', 'Cerca per proveïdor, particular, núm. comanda o albarà...')}
          className="flex-1 min-w-[260px] border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
        <input type="date" value={filters.desde} onChange={e => setFilters(f => ({ ...f, desde: e.target.value }))}
          className="border border-zinc-300 rounded-lg px-3 py-2 text-sm text-zinc-600 focus:outline-none focus:ring-2 focus:ring-zinc-900" />
        <span className="text-zinc-400 text-sm">–</span>
        <input type="date" value={filters.hasta} onChange={e => setFilters(f => ({ ...f, hasta: e.target.value }))}
          className="border border-zinc-300 rounded-lg px-3 py-2 text-sm text-zinc-600 focus:outline-none focus:ring-2 focus:ring-zinc-900" />
        {hasFilters && (
          <button onClick={() => setFilters({ q: '', desde: '', hasta: '' })}
            className="text-xs text-zinc-400 hover:text-zinc-600 px-1">
            {t('common.clear', 'Netejar')}
          </button>
        )}
      </div>

      <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm overflow-hidden">
        {loading ? (
          <div className="p-12 text-center text-zinc-400 text-sm">{t('common.loading')}</div>
        ) : comprasSorted.length === 0 ? (
          <div className="p-12 text-center text-zinc-400 text-sm">
            {hasFilters ? t('purchases.order.no_results_filtered', 'Cap resultat amb aquests filtres.') : t('purchases.order.no_orders', 'Encara no hi ha comandes ni compres.')}
          </div>
        ) : (
          <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-zinc-50 text-xs text-zinc-500 border-b border-zinc-200">
              <tr>
                <th className="w-8 px-4 py-3" />
                <SortableTh label={t('common.date')} sortKey="fecha" sort={sort} onSort={toggleSort} />
                <SortableTh label={t('purchases.col.supplier_or_individual', 'Proveïdor / particular')} sortKey="entitat" sort={sort} onSort={toggleSort} />
                <SortableTh label={t('purchases.col.lines', 'Línies')} sortKey="linies" sort={sort} onSort={toggleSort} align="center" />
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-100">
              {comprasSorted.map(c => (
                <ParticularRow key={c.id} c={c} expanded={expanded} setExpanded={setExpanded}
                  onReturnItem={setReturnItem} />
              ))}
            </tbody>
          </table>
          </div>
        )}
      </div>

      {showModal && (
        <CompraParticularModal
          onClose={() => setShowModal(false)}
          onSaved={() => { setShowModal(false); loadAll(); }} />
      )}
      {returnItem && (
        <DevolucionCompraModal
          item={returnItem.item}
          compraId={returnItem.compra_id}
          onClose={() => setReturnItem(null)}
          onSaved={() => { setReturnItem(null); loadAll(); }}
        />
      )}
    </div>
  );
}

function ParticularRow({ c, expanded, setExpanded, onReturnItem }) {
  const t = useT();
  return (
    <>
      <tr onClick={() => setExpanded(expanded === c.id ? null : c.id)}
        className="hover:bg-zinc-50 cursor-pointer transition-colors">
        <td className="px-4 py-3 text-zinc-400">
          {expanded === c.id ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        </td>
        <td className="px-4 py-3 text-zinc-500">{new Date(c.date).toLocaleDateString()}</td>
        <td className="px-4 py-3 font-medium">{c.individual_name ?? c.user_nom ?? '—'}</td>
        <td className="px-4 py-3 text-center">
          <span className="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium bg-zinc-100 text-zinc-700">
            {c.items?.length ?? 0}
          </span>
        </td>
      </tr>
      {expanded === c.id && (
        <tr>
          <td colSpan={4} className="px-4 py-3 bg-amber-50/40 border-b border-amber-100">
            {(c.items?.length ?? 0) === 0
              ? <span className="text-sm text-zinc-400">{t('purchases.no_copies', 'Sense còpies.')}</span>
              : (
                <div className="space-y-1">
                  {c.items.map(it => (
                    <div key={it.item_id} className="flex items-center gap-4 text-sm flex-wrap">
                      <span className="font-semibold text-zinc-900">{it.artista} — {it.title}</span>
                      <span className="text-zinc-500">{t('purchases.pvp_short', 'PVP')}: {it.price} €</span>
                      {it.acquisition_cost && (
                        <span className="text-zinc-400">{t('purchases.cost_short', 'Cost')}: {it.acquisition_cost} €</span>
                      )}
                      {it.devuelto ? (
                        <span className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium bg-zinc-100 text-zinc-500">
                          {t('return.returned')}
                        </span>
                      ) : it.item_status === 'disponible' ? (
                        <button
                          onClick={e => { e.stopPropagation(); onReturnItem({ item: it, compra_id: c.id }); }}
                          className="flex items-center gap-1 text-xs font-semibold text-amber-600 hover:text-amber-700 border border-amber-200 rounded-lg px-2 py-0.5 hover:bg-amber-50 transition-colors"
                        >
                          <RotateCcw size={11} /> {t('purchases.return_action', 'Devolució')}
                        </button>
                      ) : (
                        <span className="text-xs text-zinc-400">{it.item_status}</span>
                      )}
                    </div>
                  ))}
                </div>
              )
            }
          </td>
        </tr>
      )}
    </>
  );
}

// Flux ràpid: compra a un particular que ve a la botiga. Neix entregada
// (stock disponible a l'instant) i, si hi ha caixa oberta, apunta la
// sortida automàticament.
function CompraParticularModal({ onClose, onSaved }) {
  const t = useT();
  const discogsEnabled = useDiscogsEnabled();
  const vertical = useTenantVertical();
  const [nombreParticular, setNombreParticular] = useState('');
  const [linkedUser, setLinkedUser] = useState(null);
  const [userQ, setUserQ] = useState('');
  const [userResults, setUserResults] = useState([]);
  const [fecha, setFecha] = useState(new Date().toISOString().slice(0, 10));
  const [notas, setNotas] = useState('');
  const [items, setItems] = useState([]);
  const [discogsQ, setDiscogsQ] = useState('');
  const [discogsRes, setDiscogsRes] = useState([]);
  const [searchingDiscogs, setSearchingDiscogs] = useState(false);
  const [resolving, setResolving] = useState(false);
  const [manualMode, setManualMode] = useState(false);
  const [manualForm, setManualForm] = useState({ artista: '', titulo: '', sello: '', formato: 'LP', anio: '' });
  const [saving, setSaving] = useState(false);
  const userDebounce = useRef(null);
  const discogsDebounce = useRef(null);

  function handleUserQ(val) {
    setUserQ(val);
    setLinkedUser(null);
    clearTimeout(userDebounce.current);
    if (val.length < 2) { setUserResults([]); return; }
    userDebounce.current = setTimeout(async () => {
      const r = await authFetch(`/admin/users/search?q=${encodeURIComponent(val)}`);
      setUserResults(await r.json());
    }, 300);
  }

  function selectUser(u) {
    setLinkedUser(u);
    setUserQ(u.name || u.email);
    setUserResults([]);
    if (!nombreParticular) setNombreParticular(u.name || '');
  }

  function handleDiscogsQ(val) {
    setDiscogsQ(val);
    clearTimeout(discogsDebounce.current);
    if (val.trim().length < 3) { setDiscogsRes([]); return; }
    discogsDebounce.current = setTimeout(async () => {
      setSearchingDiscogs(true);
      try {
        const r = await authFetch(`/admin/discogs/search?q=${encodeURIComponent(val)}`);
        const data = await r.json();
        setDiscogsRes(Array.isArray(data) ? data : (data.results ?? []));
      } finally {
        setSearchingDiscogs(false);
      }
    }, 400);
  }

  async function resolveRelease({ discogsId, artista, titulo, sello, formato, anio, genero, estilos, pais, imagen_url, tracklist, credits }) {
    const params = new URLSearchParams();
    if (discogsId) params.set('discogs_release_id', discogsId);
    else { params.set('artista', artista); params.set('titulo', titulo); }
    const dupRes = await authFetch(`/admin/releases/check-duplicate?${params.toString()}`);
    const matches = dupRes.ok ? await dupRes.json() : [];
    if (matches.length > 0) {
      const m = matches[0];
      return { id: m.id, artista: m.artista, titulo: m.titulo, existing: true };
    }
    const rRes = await authFetch('/admin/releases', {
      method: 'POST',
      body: JSON.stringify({
        artista, title: titulo, sello: sello || null, formato: formato || null,
        anio: anio ? parseInt(anio) : null, genero: genero || null,
        estilos: estilos || null, pais: pais || null, image_url: imagen_url || null,
        tracklist: tracklist || null, credits: credits || null,
        discogs_release_id: discogsId ? parseInt(discogsId) : null,
      }),
    });
    const { id } = await rRes.json();
    return { id, artista, titulo, existing: false };
  }

  async function pickDiscogs(result) {
    setResolving(true);
    try {
      let full = result;
      if (result.discogs_release_id) {
        try {
          const r = await authFetch(`/admin/discogs/release/${result.discogs_release_id}`);
          if (r.ok) full = { ...result, ...(await r.json()) };
        } catch { /* ens conformem amb les dades de la cerca */ }
      }
      const rel = await resolveRelease({
        discogsId: full.discogs_release_id, artista: full.artista, titulo: full.titulo,
        sello: full.sello, formato: full.formato?.split(',')[0]?.trim(), anio: full.anio,
        genero: full.genero, estilos: full.estilos, pais: full.pais, imagen_url: full.imagen_url,
        tracklist: full.tracklist, credits: full.credits,
      });
      addItem(rel);
    } finally {
      setResolving(false);
      setDiscogsQ(''); setDiscogsRes([]);
    }
  }

  async function addManual() {
    if (!manualForm.titulo.trim()) return;
    setResolving(true);
    try {
      const rel = await resolveRelease(manualForm);
      addItem(rel);
      setManualForm({ artista: '', titulo: '', sello: '', formato: 'LP', anio: '' });
      setManualMode(false);
    } finally {
      setResolving(false);
    }
  }

  function addItem(rel) {
    setItems(prev => [...prev, { release_id: rel.id, artista: rel.artista, titulo: rel.titulo, existing: rel.existing, precio: '', coste_adquisicion: '', condicion: 'segona_ma', estado_disco: '', estado_funda: '' }]);
  }

  function upd(idx, k, v) { setItems(prev => prev.map((it, i) => i === idx ? { ...it, [k]: v } : it)); }

  async function save(e) {
    e.preventDefault();
    setSaving(true);
    const payload = {
      individual_name: nombreParticular || null,
      user_id: linkedUser?.id || null,
      date: new Date(fecha).toISOString(),
      notes: notas || null,
      items: items.map(it => ({
        release_id: it.release_id,
        price: parseFloat(it.precio),
        acquisition_cost: parseFloat(it.coste_adquisicion),
        condition: it.condicion,
        estado_disco: it.condicion === 'nou' ? null : (it.estado_disco || null),
        estado_funda: it.condicion === 'nou' ? null : (it.estado_funda || null),
      })),
    };
    const r = await authFetch('/admin/compras/particular', { method: 'POST', body: JSON.stringify(payload) });
    setSaving(false);
    if (r.ok) onSaved();
  }

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-start justify-center p-4 overflow-y-auto">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-3xl my-8">
        <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-200">
          <h3 className="text-lg font-bold text-zinc-900">{t('purchases.btn.individual_purchase', 'Compra particular')}</h3>
          <button onClick={onClose} className="text-zinc-400 hover:text-zinc-600 p-1 rounded-lg hover:bg-zinc-100"><X size={20} /></button>
        </div>

        <form onSubmit={save} className="p-6 space-y-5">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-zinc-700 mb-1">
                {t('purchases.individual_modal.registered_user', 'Usuari registrat')} <span className="text-zinc-400 font-normal">{t('common.optional', '(opcional)')}</span>
              </label>
              {linkedUser ? (
                <div className="flex items-center gap-2 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
                  <div className="w-5 h-5 rounded-full bg-amber-200 text-amber-800 flex items-center justify-center text-xs font-bold shrink-0">
                    {(linkedUser.name || linkedUser.email)[0].toUpperCase()}
                  </div>
                  <span className="text-sm font-medium flex-1 truncate">{linkedUser.name || linkedUser.email}</span>
                  <button type="button" onClick={() => { setLinkedUser(null); setUserQ(''); }}
                    className="text-zinc-400 hover:text-zinc-600"><X size={13} /></button>
                </div>
              ) : (
                <div className="relative">
                  <input value={userQ} onChange={e => handleUserQ(e.target.value)}
                    placeholder={t('purchases.individual_modal.user_search_ph', 'Cerca per nom o email...')}
                    className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
                  {userResults.length > 0 && (
                    <div className="absolute z-10 w-full mt-1 bg-white border border-zinc-200 rounded-xl shadow-lg overflow-hidden">
                      {userResults.map(u => (
                        <button key={u.id} type="button" onClick={() => selectUser(u)}
                          className="w-full text-left px-3 py-2.5 hover:bg-zinc-50 text-sm border-b border-zinc-50 last:border-0">
                          <span className="font-medium">{u.name || u.email}</span>
                          {u.name && <span className="text-zinc-400 ml-1 text-xs">{u.email}</span>}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              )}
              <label className="block text-sm font-medium text-zinc-700 mb-1 mt-3">{t('purchases.individual_modal.individual_name', 'Nom particular')}</label>
              <input value={nombreParticular} onChange={e => setNombreParticular(e.target.value)}
                placeholder={t('purchases.individual_modal.individual_name_ph', 'Nom i cognoms (si no és usuari registrat)')}
                className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
            </div>
            <div>
              <label className="block text-sm font-medium text-zinc-700 mb-1">{t('common.date')}</label>
              <input type="date" value={fecha} onChange={e => setFecha(e.target.value)} required
                className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
              <label className="block text-sm font-medium text-zinc-700 mb-1 mt-3">{t('common.notes')}</label>
              <input value={notas} onChange={e => setNotas(e.target.value)}
                className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
            </div>
          </div>

          <div className="border border-zinc-200 rounded-xl p-4 space-y-3">
            <div className="text-sm font-semibold text-zinc-700">{t('purchases.modal.records', 'Discs comprats')}</div>
            {discogsEnabled && (
            <div className="relative">
              <input
                value={discogsQ}
                onChange={e => handleDiscogsQ(e.target.value)}
                placeholder={t('purchases.discogs_search_ph', 'Cerca a Discogs...')}
                disabled={resolving}
                className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900 disabled:opacity-50"
              />
              {searchingDiscogs && (
                <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-zinc-400">{t('common.searching')}</span>
              )}
              {discogsRes.length > 0 && (
                <div className="absolute top-full left-0 right-0 mt-1 bg-white border border-zinc-200 rounded-xl shadow-lg z-10 overflow-hidden max-h-72 overflow-y-auto">
                  {discogsRes.map((r, i) => (
                    <button key={i} type="button" onClick={() => pickDiscogs(r)} disabled={resolving}
                      className="w-full text-left px-4 py-2.5 text-sm hover:bg-amber-50 border-b border-zinc-100 last:border-0 transition-colors disabled:opacity-50">
                      <span className="font-medium">{r.artista}</span>
                      <span className="text-zinc-500"> — {r.titulo}</span>
                      <span className="text-zinc-400 ml-2 text-xs">{[r.sello, r.formato, r.anio].filter(Boolean).join(' · ')}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
            )}

            {discogsEnabled && (
            <button type="button" onClick={() => setManualMode(m => !m)}
              className="text-xs text-amber-600 hover:text-amber-700 font-medium">
              {manualMode ? t('common.cancel') : t('purchases.add_manual_toggle', '+ Afegir disc a mà')}
            </button>
            )}

            {(!discogsEnabled || manualMode) && (
              <div className="p-3 bg-white rounded-xl border border-zinc-200 space-y-2">
                <div className="grid grid-cols-2 gap-2">
                  <input value={manualForm.artista} onChange={e => setManualForm(f => ({ ...f, artista: e.target.value }))}
                    placeholder={t('purchases.manual.artist_ph', 'Artista')}
                    className="border border-zinc-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-zinc-900" />
                  <input value={manualForm.titulo} onChange={e => setManualForm(f => ({ ...f, titulo: e.target.value }))}
                    placeholder={t('purchases.manual.title_ph', 'Títol')}
                    className="border border-zinc-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-zinc-900" />
                  <input value={manualForm.sello} onChange={e => setManualForm(f => ({ ...f, sello: e.target.value }))}
                    placeholder={t('purchases.manual.label_ph', 'Segell')}
                    className="border border-zinc-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-zinc-900" />
                  <select value={manualForm.formato} onChange={e => setManualForm(f => ({ ...f, formato: e.target.value }))}
                    className="border border-zinc-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-zinc-900 bg-white">
                    {['LP', 'EP', '7"', '12"', 'CD', 'Cassette'].map(x => <option key={x}>{x}</option>)}
                    <option>{t('purchases.manual.format_other', 'Altre')}</option>
                  </select>
                  <input type="number" value={manualForm.anio} onChange={e => setManualForm(f => ({ ...f, anio: e.target.value }))}
                    placeholder={t('purchases.manual.year_ph', 'Any')} min="1900" max="2030"
                    className="border border-zinc-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-zinc-900" />
                </div>
                <Button type="button" size="sm" onClick={addManual}
                  disabled={resolving || !manualForm.titulo.trim()}>
                  {resolving ? t('common.creating') : t('common.add', 'Afegir')}
                </Button>
              </div>
            )}

            {items.length === 0 && (
              <div className="text-sm text-zinc-400 text-center py-4">{t('purchases.individual_modal.no_items', 'Encara no has afegit cap disc.')}</div>
            )}

            <div className="space-y-2">
              {items.map((it, idx) => (
                <div key={idx} className="p-3 bg-zinc-50 rounded-xl border border-zinc-200">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-semibold text-zinc-900">{it.artista} — {it.titulo}</span>
                      {it.existing && (
                        <span className="text-[10px] uppercase tracking-wide text-zinc-400 bg-zinc-100 rounded-full px-2 py-0.5">
                          {t('purchases.modal.already_in_catalog', 'Ja al catàleg')}
                        </span>
                      )}
                    </div>
                    <button type="button" onClick={() => setItems(p => p.filter((_, i) => i !== idx))}
                      className="text-zinc-400 hover:text-red-500 transition-colors">
                      <Trash2 size={15} />
                    </button>
                  </div>
                  <div className="flex flex-wrap gap-3">
                    <div>
                      <label className="block text-xs text-zinc-500 mb-1">{t('common.condition')}</label>
                      <select value={it.condicion} onChange={e => upd(idx, 'condicion', e.target.value)}
                        className="border border-zinc-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-zinc-900 bg-white">
                        <option value="segona_ma">{t('purchases.condition.used', 'Segona mà')}</option>
                        <option value="nou">{t('common.condition.new')}</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-xs text-zinc-500 mb-1">{t('purchases.individual_modal.purchase_price', 'Preu de compra')}</label>
                      <input type="number" step="0.01" min="0" value={it.coste_adquisicion} onChange={e => upd(idx, 'coste_adquisicion', e.target.value)} required
                        className="w-24 border border-zinc-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-zinc-900" />
                    </div>
                    <div>
                      <label className="block text-xs text-zinc-500 mb-1">{t('purchases.individual_modal.sale_price_catalog', 'Preu venda (catàleg)')}</label>
                      <input type="number" step="0.01" min="0" value={it.precio} onChange={e => upd(idx, 'precio', e.target.value)} required
                        className="w-24 border border-zinc-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-zinc-900" />
                    </div>
                    {it.condicion === 'segona_ma' && vertical === 'records' && <>
                      <div>
                        <label className="block text-xs text-zinc-500 mb-1">{t('purchases.grading.disc', 'Grading disc')}</label>
                        <select value={it.estado_disco} onChange={e => upd(idx, 'estado_disco', e.target.value)}
                          className="border border-zinc-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-zinc-900 bg-white">
                          <option value="">—</option>
                          {GRADINGS.map(g => <option key={g} value={g}>{g.split(' (')[0]}</option>)}
                        </select>
                      </div>
                      <div>
                        <label className="block text-xs text-zinc-500 mb-1">{t('purchases.grading.sleeve', 'Grading funda')}</label>
                        <select value={it.estado_funda} onChange={e => upd(idx, 'estado_funda', e.target.value)}
                          className="border border-zinc-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-zinc-900 bg-white">
                          <option value="">—</option>
                          {GRADINGS.map(g => <option key={g} value={g}>{g.split(' (')[0]}</option>)}
                        </select>
                      </div>
                    </>}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="flex justify-end gap-3">
            <Button type="button" variant="secondary" onClick={onClose}>{t('common.cancel')}</Button>
            <Button type="submit" disabled={saving || items.length === 0 || (!nombreParticular && !linkedUser)}>
              {saving ? t('common.saving') : `${t('purchases.individual_modal.register_btn', 'Registrar compra')} (${items.length})`}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
