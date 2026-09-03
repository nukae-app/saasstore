'use client';

import { useState, useEffect, useRef, Fragment } from 'react';
import Link from 'next/link';
import { authFetch } from '../../../lib/auth';
import { useT } from '../../../lib/i18n';
import { useDiscogsEnabled } from '../../../../components/store/useDiscogsEnabled';
import { Button } from '../../../../components/ui/button';
import { useSortFilter } from '../../../../components/admin/table/useSortFilter';
import { SortableTh } from '../../../../components/admin/table/SortableTh';
import {
  Plus, X, Trash2, PackageCheck, ArrowRight, Sparkles, TrendingUp, TrendingDown, Minus,
} from 'lucide-react';
import {
  poolLineaEstat, poolLineaEstatLabel, POOL_LINEA_ESTAT_COLOR, origenSolicitudLabel, ORIGEN_SOLICITUD_COLOR,
} from '../../../../components/admin/compras/shared';

// Pool de línies de sol·licitud: totes les línies de tots els orígens
// (manual / reposició / petició de client) i de tots els lots, aplanades en
// una sola llista paginada. Aquest és el "com" real amb què l'admin gestiona
// les sol·licituds — el lot (`SolicitudCompra`) que les agrupa és només
// metadata de cada línia (veure GET /admin/solicitudes-compra/pool), no una
// unitat de treball pròpia.
const PAGE_SIZE = 30;
const ESTAT_TABS = ['pendent', 'resolta', 'cancelada', 'totes'];

export default function SolicitudsPage() {
  const t = useT();
  const [estado, setEstado] = useState('pendent');
  const [origen, setOrigen] = useState('');
  const [proveedorId, setProveedorId] = useState('');
  const [qInput, setQInput] = useState('');
  const [q, setQ] = useState('');
  const [page, setPage] = useState(1);
  const [rows, setRows] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [proveedores, setProveedores] = useState([]);
  const [seleccio, setSeleccio] = useState(() => new Map());
  const [busyId, setBusyId] = useState(null);
  const [resolvingEstocLinea, setResolvingEstocLinea] = useState(null);
  const [resolvingLineas, setResolvingLineas] = useState(null);
  const [showRefillModal, setShowRefillModal] = useState(false);
  const qDebounce = useRef(null);

  useEffect(() => { authFetch('/admin/proveedores').then(r => r.json()).then(setProveedores); }, []);

  async function loadPool() {
    setLoading(true);
    const params = new URLSearchParams({ estado, page: String(page), page_size: String(PAGE_SIZE) });
    if (origen) params.set('origen', origen);
    if (proveedorId) params.set('proveedor_id', proveedorId);
    if (q) params.set('q', q);
    const r = await authFetch(`/admin/solicitudes-compra/pool?${params.toString()}`);
    const data = await r.json();
    setRows(data.results ?? []);
    setTotal(data.total ?? 0);
    setLoading(false);
  }
  useEffect(() => { loadPool(); }, [estado, origen, proveedorId, q, page]);
  useEffect(() => { setPage(1); }, [estado, origen, proveedorId, q]);

  function handleQInput(val) {
    setQInput(val);
    clearTimeout(qDebounce.current);
    qDebounce.current = setTimeout(() => setQ(val.trim()), 400);
  }

  function toggleLinea(row) {
    setSeleccio(prev => {
      const next = new Map(prev);
      if (next.has(row.id)) next.delete(row.id); else next.set(row.id, row);
      return next;
    });
  }

  function toggleAllVisible() {
    const seleccionables = rows.filter(r => poolLineaEstat(r) === 'pendent');
    const totesSeleccionades = seleccionables.length > 0 && seleccionables.every(r => seleccio.has(r.id));
    setSeleccio(prev => {
      const next = new Map(prev);
      for (const r of seleccionables) {
        if (totesSeleccionades) next.delete(r.id); else next.set(r.id, r);
      }
      return next;
    });
  }

  async function eliminarLinia(row) {
    if (!confirm(t('purchases.request.confirm_remove_line', 'Treure "{disc}" d\'aquesta sol·licitud?').replace('{disc}', `${row.artist} — ${row.title}`))) return;
    setBusyId(row.id);
    const r = await authFetch(`/admin/solicitudes-compra/${row.solicitud_id}/lineas/${row.id}`, { method: 'DELETE' });
    if (!r.ok) {
      const body = await r.json().catch(() => ({}));
      alert(body.detail || t('purchases.request.delete_line_error', 'No s\'ha pogut eliminar el disc.'));
    }
    setBusyId(null);
    setSeleccio(prev => { const next = new Map(prev); next.delete(row.id); return next; });
    loadPool();
  }

  const from = total === 0 ? 0 : (page - 1) * PAGE_SIZE + 1;
  const to = Math.min(page * PAGE_SIZE, total);

  return (
    <div className="space-y-5 max-w-6xl mx-auto">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h2 className="text-2xl font-bold text-zinc-900">{t('purchases.tab.requests', 'Sol·licituds')}</h2>
        <div className="flex items-center gap-2">
          <button onClick={() => setShowRefillModal(true)}
            className="flex items-center gap-1.5 text-sm border border-zinc-200 text-zinc-600 hover:bg-zinc-50 px-3 py-2 rounded-lg transition-colors">
            <Sparkles size={13} /> {t('purchases.btn.generate_suggestions', 'Generar suggeriments')}
          </button>
          <Link href="/admin/compras/solicituds/nueva"
            className="flex items-center gap-1.5 bg-primary hover:bg-zinc-800 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors">
            <Plus size={15} /> {t('purchases.btn.new_request', 'Nova sol·licitud')}
          </Link>
        </div>
      </div>

      <div className="flex items-center gap-2 flex-wrap">
        <div className="flex items-center gap-1 bg-zinc-100 rounded-lg p-1">
          {ESTAT_TABS.map(tab => (
            <button key={tab} onClick={() => setEstado(tab)}
              className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${estado === tab ? 'bg-white text-zinc-900 shadow-sm' : 'text-zinc-500 hover:text-zinc-700'}`}>
              {t(`purchases.pool.tab.${tab}`, tab)}
            </button>
          ))}
        </div>
        <select value={origen} onChange={e => setOrigen(e.target.value)}
          className="border border-zinc-200 rounded-lg px-2.5 py-1.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-zinc-900">
          <option value="">{t('purchases.pool.filter.origin_all', 'Tots els orígens')}</option>
          <option value="manual">{origenSolicitudLabel(t, 'manual')}</option>
          <option value="refill_stock">{origenSolicitudLabel(t, 'refill_stock')}</option>
          <option value="peticion_cliente">{origenSolicitudLabel(t, 'peticion_cliente')}</option>
        </select>
        <select value={proveedorId} onChange={e => setProveedorId(e.target.value)}
          className="border border-zinc-200 rounded-lg px-2.5 py-1.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-zinc-900">
          <option value="">{t('purchases.pool.filter.supplier_all', 'Tots els proveïdors')}</option>
          {proveedores.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
        </select>
        <input value={qInput} onChange={e => handleQInput(e.target.value)}
          placeholder={t('purchases.pool.search_ph', 'Cerca per artista o títol...')}
          className="border border-zinc-200 rounded-lg px-3 py-1.5 text-sm flex-1 min-w-[180px] focus:outline-none focus:ring-2 focus:ring-zinc-900" />
      </div>

      {seleccio.size > 0 && (
        <div className="px-4 py-3 bg-amber-50 border border-amber-100 rounded-xl flex items-center justify-between">
          <span className="text-sm font-medium text-amber-800">
            {seleccio.size} {seleccio.size !== 1 ? t('purchases.request.records_selected_plural', 'discs seleccionats') : t('purchases.request.records_selected', 'disc seleccionat')}
          </span>
          <div className="flex items-center gap-3">
            <button onClick={() => setSeleccio(new Map())} className="text-xs text-zinc-500 hover:text-zinc-700">
              {t('purchases.request.clear_selection', 'Netejar selecció')}
            </button>
            <Button size="sm" onClick={() => setResolvingLineas([...seleccio.values()])}>
              <ArrowRight size={13} /> {t('purchases.request.create_order', 'Crear comanda')}
            </Button>
          </div>
        </div>
      )}

      <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm overflow-hidden">
        {loading ? (
          <div className="p-12 text-center text-zinc-400 text-sm">{t('common.loading')}</div>
        ) : rows.length === 0 ? (
          <div className="p-12 text-center text-zinc-400 text-sm">{t('purchases.pool.empty', 'No hi ha cap disc en aquest filtre.')}</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-zinc-50 text-xs text-zinc-500 border-b border-zinc-200">
                <tr>
                  <th className="w-8 px-4 py-3">
                    <input type="checkbox"
                      checked={rows.some(r => poolLineaEstat(r) === 'pendent') && rows.filter(r => poolLineaEstat(r) === 'pendent').every(r => seleccio.has(r.id))}
                      onChange={toggleAllVisible}
                      className="rounded border-zinc-300 text-amber-600 focus:ring-zinc-900" />
                  </th>
                  <th className="px-4 py-3 text-left font-medium">{t('tpv.col.record')}</th>
                  <th className="px-4 py-3 text-center font-medium">{t('purchases.quantity', 'Quantitat')}</th>
                  <th className="px-4 py-3 text-left font-medium">{t('purchases.col.origin')}</th>
                  <th className="px-4 py-3 text-left font-medium">{t('purchases.type.supplier')}</th>
                  <th className="px-4 py-3 text-left font-medium">{t('purchases.col.status')}</th>
                  <th className="px-4 py-3 text-left font-medium">{t('common.date')}</th>
                  <th className="px-4 py-3 text-right font-medium">{t('catalog.col.actions')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {rows.map(row => {
                  const estat = poolLineaEstat(row);
                  return (
                    <tr key={row.id} className="hover:bg-zinc-50">
                      <td className="px-4 py-3">
                        <input type="checkbox" checked={seleccio.has(row.id)} disabled={estat !== 'pendent'}
                          onChange={() => toggleLinea(row)}
                          className="rounded border-zinc-300 text-amber-600 focus:ring-zinc-900 disabled:opacity-30" />
                      </td>
                      <td className="px-4 py-3">
                        <div className="font-medium text-zinc-900">{row.artist} — {row.title}</div>
                        {row.label && <div className="text-xs text-zinc-400">{row.label}</div>}
                        {row.solicitud_notes && <div className="text-xs text-zinc-400">{row.solicitud_notes}</div>}
                      </td>
                      <td className="px-4 py-3 text-center text-zinc-600">{row.quantity}x</td>
                      <td className="px-4 py-3">
                        <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${ORIGEN_SOLICITUD_COLOR[row.origen] ?? 'bg-zinc-100 text-zinc-600'}`}>
                          {origenSolicitudLabel(t, row.origen)}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-zinc-600">{row.proveedor_sugerido_nombre ?? <span className="text-zinc-300">—</span>}</td>
                      <td className="px-4 py-3">
                        <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${POOL_LINEA_ESTAT_COLOR[estat]}`}>
                          {poolLineaEstatLabel(t, row)}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-zinc-500">{new Date(row.solicitud_created_at).toLocaleDateString()}</td>
                      <td className="px-4 py-3 text-right">
                        {estat === 'pendent' && (
                          <div className="flex items-center justify-end gap-1.5">
                            {row.release_id && (
                              <button onClick={() => setResolvingEstocLinea(row)}
                                title={t('purchases.action.resolve_from_stock', "Resoldre d'estoc")}
                                className="flex items-center gap-1 text-xs font-medium text-emerald-600 hover:text-emerald-700 border border-emerald-200 rounded-lg px-2 py-1 hover:bg-emerald-50 transition-colors">
                                <PackageCheck size={12} />
                              </button>
                            )}
                            <button onClick={() => eliminarLinia(row)} disabled={busyId === row.id}
                              title={t('purchases.action.remove_from_request', 'Treure aquest disc de la sol·licitud')}
                              className="p-1.5 text-zinc-300 hover:text-red-500 rounded-lg hover:bg-red-50 disabled:opacity-50">
                              <Trash2 size={14} />
                            </button>
                          </div>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
        {total > PAGE_SIZE && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-zinc-100 text-xs text-zinc-500">
            <span>{from}–{to} {t('common.of', 'de')} {total}</span>
            <div className="flex gap-2">
              <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}
                className="px-3 py-1.5 border border-zinc-200 rounded-lg hover:bg-zinc-50 disabled:opacity-40 transition-colors">
                ← {t('common.previous', 'Anterior')}
              </button>
              <button onClick={() => setPage(p => p + 1)} disabled={page * PAGE_SIZE >= total}
                className="px-3 py-1.5 border border-zinc-200 rounded-lg hover:bg-zinc-50 disabled:opacity-40 transition-colors">
                {t('common.next', 'Següent')} →
              </button>
            </div>
          </div>
        )}
      </div>

      {resolvingEstocLinea && (
        <ResoldreEstocModal
          linea={resolvingEstocLinea}
          onClose={() => setResolvingEstocLinea(null)}
          onSaved={() => { setResolvingEstocLinea(null); loadPool(); }} />
      )}

      {resolvingLineas && (
        <ResoldreSolicitudModal
          lineas={resolvingLineas} proveedores={proveedores}
          onClose={() => setResolvingLineas(null)}
          onSaved={() => { setResolvingLineas(null); setSeleccio(new Map()); loadPool(); }} />
      )}
      {showRefillModal && (
        <RefillSugerenciesModal
          onClose={() => setShowRefillModal(false)}
          onSaved={() => { setShowRefillModal(false); loadPool(); }} />
      )}
    </div>
  );
}

function ResoldreEstocModal({ linea, onClose, onSaved }) {
  const t = useT();
  const [items, setItems] = useState(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    authFetch(`/catalog/releases/${linea.release_id}`)
      .then(r => r.json())
      .then(d => setItems((d.items || []).filter(i => i.condition === 'nou'
        ? i.status === 'disponible' && (i.quantity - i.reserved_quantity) > 0
        : i.status === 'disponible')));
  }, [linea.release_id]);

  async function resoldre(item) {
    setSaving(true);
    setError('');
    try {
      const r = await authFetch(`/admin/solicitudes-compra/lineas/${linea.id}/resoldre-estoc`, {
        method: 'POST', body: JSON.stringify({ item_id: item.id }),
      });
      if (r.ok) onSaved();
      else { const d = await r.json().catch(() => ({})); setError(d.detail || t('purchases.action.resolve_error', 'No s\'ha pogut resoldre.')); }
    } finally { setSaving(false); }
  }

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-xl max-w-sm w-full p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-bold text-zinc-900">{t('purchases.action.resolve_from_stock', "Resoldre d'estoc")}</h2>
          <button onClick={onClose} className="text-zinc-400 hover:text-zinc-600"><X size={18} /></button>
        </div>
        <p className="text-sm text-zinc-500 mb-4">{linea.artist} — {linea.title}</p>
        <p className="text-xs text-zinc-400 mb-4">
          {t('purchases.resolve_stock_modal.hint', "Tria l'exemplar que ja hi ha a estoc per tancar aquesta línia sense fer-ne una comanda a proveïdor.")}
        </p>
        {error && <p className="text-sm text-red-600 mb-3">{error}</p>}
        {items === null ? (
          <div className="animate-pulse bg-zinc-100 rounded-lg h-16" />
        ) : items.length === 0 ? (
          <p className="text-sm text-zinc-400 text-center py-6">{t('purchases.resolve_stock_modal.no_items', 'Aquest disc no té cap exemplar disponible a estoc ara mateix.')}</p>
        ) : (
          <div className="space-y-1.5">
            {items.map(i => (
              <button key={i.id} disabled={saving} onClick={() => resoldre(i)}
                className="w-full flex items-center justify-between p-2.5 rounded-lg shadow-[0_2px_20px_-6px_rgba(15,23,42,0.08)] hover:border-emerald-300 hover:bg-emerald-50/30 transition-colors text-sm disabled:opacity-50">
                <span className="text-zinc-700">
                  {i.condition} {i.estado_disco ? `· ${i.estado_disco}` : ''}
                  {i.condition === 'nou' && ` · ${i.quantity - i.reserved_quantity} ${t('purchases.units_free', 'lliures')}`}
                </span>
                <span className="font-medium text-zinc-900">{Number(i.price).toFixed(2)} €</span>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function ResoldreSolicitudModal({ lineas, proveedores, onClose, onSaved }) {
  const t = useT();
  const discogsEnabled = useDiscogsEnabled();
  const pendents = lineas.filter(l => !l.resuelta);
  const [proveedorId, setProveedorId] = useState(pendents[0]?.proveedor_sugerido_id || '');
  const [fecha, setFecha] = useState(new Date().toISOString().slice(0, 10));
  const [notas, setNotas] = useState('');
  // Les línies sense release_id (creades a mà, disc encara no al catàleg) no
  // es marquen soles: cal resoldre-les primer (cercar/donar d'alta) abans
  // de poder-les incloure a la comanda.
  const [seleccio, setSeleccio] = useState(() => new Set(pendents.filter(l => l.release_id).map(l => l.id)));
  const [preus, setPreus] = useState(() => Object.fromEntries(pendents.map(l => [l.id, ''])));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  // Resolució de línies sense catalogar: només una oberta a la vegada.
  const [resolvingLineaId, setResolvingLineaId] = useState(null);
  const [resolvedReleases, setResolvedReleases] = useState({}); // { [linea_id]: { id, artista, titulo, existing } }
  const [discogsQ, setDiscogsQ] = useState('');
  const [discogsRes, setDiscogsRes] = useState([]);
  const [searchingDiscogs, setSearchingDiscogs] = useState(false);
  const [resolvingRelease, setResolvingRelease] = useState(false);
  const [manualMode, setManualMode] = useState(false);
  const [manualForm, setManualForm] = useState({ artista: '', titulo: '', sello: '', formato: 'LP', anio: '' });
  const discogsDebounce = useRef(null);

  function toggle(id) {
    setSeleccio(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }

  function openResolver(linea) {
    setResolvingLineaId(linea.id);
    setManualMode(false);
    setManualForm({ artista: linea.artist || '', titulo: linea.title || '', sello: linea.label || '', formato: linea.format || 'LP', anio: '' });
    setDiscogsQ(''); setDiscogsRes([]);
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

  function applyResolved(rel) {
    setResolvedReleases(prev => ({ ...prev, [resolvingLineaId]: rel }));
    setSeleccio(prev => new Set(prev).add(resolvingLineaId));
    setResolvingLineaId(null);
  }

  async function pickDiscogs(result) {
    setResolvingRelease(true);
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
      applyResolved(rel);
    } finally {
      setResolvingRelease(false);
      setDiscogsQ(''); setDiscogsRes([]);
    }
  }

  async function addManual() {
    if (!manualForm.titulo.trim()) return;
    setResolvingRelease(true);
    try {
      const rel = await resolveRelease(manualForm);
      applyResolved(rel);
    } finally {
      setResolvingRelease(false);
    }
  }

  async function save(e) {
    e.preventDefault();
    if (seleccio.size === 0) return;
    setSaving(true);
    setError('');
    const payload = {
      proveedor_id: proveedorId,
      date: new Date(fecha).toISOString(),
      notes: notas || null,
      lineas: pendents.filter(l => seleccio.has(l.id)).map(l => ({
        solicitud_linea_id: l.id,
        estimated_unit_price: preus[l.id] ? parseFloat(preus[l.id]) : null,
        release_id: l.release_id ? undefined : resolvedReleases[l.id]?.id,
      })),
    };
    const r = await authFetch('/admin/solicitudes-compra/resolver', { method: 'POST', body: JSON.stringify(payload) });
    setSaving(false);
    if (r.ok) onSaved();
    else setError((await r.json().catch(() => ({}))).detail || t('purchases.action.resolve_error', 'No s\'ha pogut resoldre.'));
  }

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-start justify-center p-4 overflow-y-auto">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl my-8">
        <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-200">
          <h3 className="text-lg font-bold text-zinc-900">{t('purchases.resolve_request_modal.title', 'Crear comanda des de sol·licituds')}</h3>
          <button onClick={onClose} className="text-zinc-400 hover:text-zinc-600 p-1 rounded-lg hover:bg-zinc-100"><X size={20} /></button>
        </div>

        <form onSubmit={save} className="p-6 space-y-5">
          <p className="text-xs text-zinc-400">
            {t('purchases.resolve_request_modal.hint', 'Tria quines línies (poden venir de sol·licituds diferents) van a la mateixa comanda. Les que no seleccionis queden pendents per resoldre-les després (cap a un altre proveïdor, per exemple).')}
          </p>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-zinc-700 mb-1">{t('purchases.type.supplier')}</label>
              <select value={proveedorId} onChange={e => setProveedorId(e.target.value)} required
                className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900 bg-white">
                <option value="">{t('common.select')}</option>
                {proveedores.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-zinc-700 mb-1">{t('common.date')}</label>
              <input type="date" value={fecha} onChange={e => setFecha(e.target.value)} required
                className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
            </div>
            <div className="col-span-2">
              <label className="block text-sm font-medium text-zinc-700 mb-1">{t('purchases.order_notes', 'Notes de la comanda')}</label>
              <input value={notas} onChange={e => setNotas(e.target.value)}
                className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
            </div>
          </div>

          <div className="border border-zinc-200 rounded-xl divide-y divide-zinc-100">
            {pendents.map(l => {
              const resolved = resolvedReleases[l.id];
              const catalogat = !!l.release_id || !!resolved;
              return (
                <Fragment key={l.id}>
                  <div className="flex items-center gap-3 px-4 py-3 hover:bg-zinc-50">
                    <input type="checkbox" checked={seleccio.has(l.id)} disabled={!catalogat} onChange={() => toggle(l.id)}
                      className="rounded border-zinc-300 text-amber-600 focus:ring-zinc-900 disabled:opacity-40" />
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium text-zinc-900 truncate">
                        {resolved ? `${resolved.artista} — ${resolved.titulo}` : `${l.artist} — ${l.title}`}
                      </div>
                      <div className="text-xs text-zinc-400 flex items-center gap-1.5">
                        {l.quantity}x{l.label ? ` · ${l.label}` : ''}
                        {!catalogat && (
                          <span className="text-sky-600 font-medium">
                            · {t('purchases.resolve_request_modal.not_catalogued', 'Article nou al catàleg')}
                          </span>
                        )}
                        {resolved && (
                          <span className="text-emerald-600 font-medium">
                            · {resolved.existing ? t('purchases.modal.already_in_catalog', 'Ja al catàleg') : t('purchases.resolve_request_modal.newly_catalogued', 'Acabat de catalogar')}
                          </span>
                        )}
                      </div>
                    </div>
                    {catalogat ? (
                      <input type="number" step="0.01" min="0" placeholder={t('purchases.est_price', 'Preu est.')} value={preus[l.id] ?? ''}
                        onChange={e => setPreus(prev => ({ ...prev, [l.id]: e.target.value }))}
                        className="w-24 border border-zinc-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-zinc-900" />
                    ) : (
                      <Button type="button" variant="secondary" size="sm" onClick={() => openResolver(l)}
                        disabled={resolvingLineaId === l.id}>
                        {t('purchases.resolve_request_modal.resolve_btn', 'Cercar / donar d\'alta')}
                      </Button>
                    )}
                  </div>

                  {resolvingLineaId === l.id && (
                    <div className="px-4 py-3 bg-amber-50/50 space-y-2">
                      {discogsEnabled && (
                        <div className="relative">
                          <input
                            value={discogsQ}
                            onChange={e => handleDiscogsQ(e.target.value)}
                            placeholder={t('purchases.discogs_search_ph', 'Cerca a Discogs...')}
                            disabled={resolvingRelease}
                            autoFocus
                            className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900 disabled:opacity-50"
                          />
                          {searchingDiscogs && (
                            <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-zinc-400">{t('common.searching')}</span>
                          )}
                          {discogsRes.length > 0 && (
                            <div className="absolute top-full left-0 right-0 mt-1 bg-white border border-zinc-200 rounded-xl shadow-lg z-10 overflow-hidden max-h-72 overflow-y-auto">
                              {discogsRes.map((r, i) => (
                                <button key={i} type="button" onClick={() => pickDiscogs(r)} disabled={resolvingRelease}
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
                          <div className="flex gap-2">
                            <Button type="button" size="sm" onClick={addManual} disabled={resolvingRelease || !manualForm.titulo.trim()}>
                              {resolvingRelease ? t('common.creating') : t('common.add', 'Afegir')}
                            </Button>
                            <Button type="button" variant="secondary" size="sm" onClick={() => setResolvingLineaId(null)}>
                              {t('common.cancel')}
                            </Button>
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </Fragment>
              );
            })}
          </div>

          {error && <p className="text-red-500 text-sm">{error}</p>}
          <div className="flex justify-end gap-3">
            <Button type="button" variant="secondary" onClick={onClose}>{t('common.cancel')}</Button>
            <Button type="submit" disabled={saving || seleccio.size === 0 || !proveedorId}>
              {saving ? t('purchases.request_modal.creating_order', 'Creant comanda...') : `${t('purchases.request_modal.create_order', 'Crear comanda')} (${seleccio.size})`}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}

const TENDENCIA_ICON = { accelerant: TrendingUp, frenant: TrendingDown, estable: Minus };
const TENDENCIA_COLOR = { accelerant: 'text-emerald-600', frenant: 'text-red-500', estable: 'text-zinc-400' };

// Previsualització dels candidats a reposició (estoc baix + es venen + sense
// comanda oberta). No crea res fins que es confirma: llavors genera una
// SolicitudCompra amb origen='refill_stock' amb les línies seleccionades.
function RefillSugerenciesModal({ onClose, onSaved }) {
  const t = useT();
  const [candidats, setCandidats] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState(new Set());
  const [cantidades, setCantidades] = useState({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    (async () => {
      setLoading(true);
      const r = await authFetch('/admin/solicitudes-compra/refill-sugerencias');
      const data = r.ok ? await r.json() : [];
      setCandidats(data);
      setSelected(new Set(data.map(c => c.release_id)));
      setCantidades(Object.fromEntries(data.map(c => [c.release_id, c.cantidad_sugerida])));
      setLoading(false);
    })();
  }, []);

  function toggle(releaseId) {
    setSelected(prev => {
      const next = new Set(prev);
      if (next.has(releaseId)) next.delete(releaseId); else next.add(releaseId);
      return next;
    });
  }

  function toggleAllVisible(visibleRows) {
    setSelected(prev => {
      const allSelected = visibleRows.length > 0 && visibleRows.every(c => prev.has(c.release_id));
      const next = new Set(prev);
      visibleRows.forEach(c => allSelected ? next.delete(c.release_id) : next.add(c.release_id));
      return next;
    });
  }

  const candidatsColumns = {
    disc: { sortValue: c => `${c.artista ?? ''} ${c.titulo ?? ''}`.toLowerCase() },
    stock_actual: { sortValue: c => c.stock_actual ?? 0 },
    vendes_periode: { sortValue: c => c.vendes_periode ?? 0 },
    dies_estoc: { sortValue: c => c.dies_estoc ?? 0 },
    marge_mitja: { sortValue: c => c.marge_mitja != null ? parseFloat(c.marge_mitja) : null },
    proveedor_sugerido_nombre: {
      sortValue: c => (c.proveedor_sugerido_nombre ?? '').toLowerCase(),
      filterValue: c => c.proveedor_sugerido_nombre,
    },
  };
  const {
    rows: candidatsSorted, sort: candSort, toggleSort: toggleCandSort,
    filters: candFilters, setFilter: setCandFilter, distinctValues: candDistinct,
  } = useSortFilter(candidats, candidatsColumns);

  async function save(e) {
    e.preventDefault();
    if (selected.size === 0) return;
    setSaving(true);
    setError('');
    const payload = {
      origen: 'refill_stock',
      notes: `${t('purchases.refill_modal.auto_generated', 'Generat automàticament')} (${new Date().toLocaleDateString()})`,
      lineas: candidats.filter(c => selected.has(c.release_id)).map(c => ({
        release_id: c.release_id,
        quantity: parseInt(cantidades[c.release_id], 10) || 1,
        proveedor_sugerido_id: c.proveedor_sugerido_id || null,
      })),
    };
    const r = await authFetch('/admin/solicitudes-compra', { method: 'POST', body: JSON.stringify(payload) });
    setSaving(false);
    if (r.ok) onSaved();
    else setError((await r.json().catch(() => ({}))).detail || t('purchases.request.create_error', 'No s\'ha pogut crear la sol·licitud.'));
  }

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-start justify-center p-4 overflow-y-auto">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-4xl my-8">
        <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-200">
          <h3 className="text-lg font-bold text-zinc-900">{t('purchases.btn.generate_suggestions_title', 'Suggeriments de reposició')}</h3>
          <button onClick={onClose} className="text-zinc-400 hover:text-zinc-600 p-1 rounded-lg hover:bg-zinc-100"><X size={20} /></button>
        </div>

        <div className="p-6 space-y-4">
          <p className="text-xs text-zinc-400">
            {t('purchases.refill_modal.hint', "Discos amb estoc nou baix que es continuen venent (vendes dels últims 60 dies), amb menys de 21 dies d'estoc restant al ritme actual. No inclou discos amb una comanda ja oberta. La quantitat i el proveïdor són editables abans de crear la sol·licitud.")}
          </p>

          {loading ? (
            <div className="text-sm text-zinc-400 text-center py-8">{t('purchases.refill_modal.calculating', 'Calculant...')}</div>
          ) : candidats.length === 0 ? (
            <div className="text-sm text-zinc-400 text-center py-8">
              {t('purchases.refill_modal.no_candidates', 'Ara mateix no hi ha cap disc que compleixi els criteris de reposició.')}
            </div>
          ) : (
            <div className="border border-zinc-200 rounded-xl overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-zinc-50 text-xs text-zinc-500 border-b border-zinc-200">
                  <tr>
                    <th className="w-8 px-3 py-2">
                      <input type="checkbox"
                        checked={candidatsSorted.length > 0 && candidatsSorted.every(c => selected.has(c.release_id))}
                        onChange={() => toggleAllVisible(candidatsSorted)}
                        title={candidatsSorted.every(c => selected.has(c.release_id)) ? t('purchases.refill_modal.unselect_all', 'Desmarcar-ho tot') : t('purchases.refill_modal.select_all', 'Seleccionar-ho tot')}
                        className="rounded border-zinc-300 text-amber-600 focus:ring-zinc-900" />
                    </th>
                    <SortableTh label={t('tpv.col.record')} sortKey="disc" sort={candSort} onSort={toggleCandSort} className="px-3 py-2" />
                    <SortableTh label={t('catalog.col.stock')} sortKey="stock_actual" sort={candSort} onSort={toggleCandSort} align="center" className="px-3 py-2" />
                    <SortableTh label={t('purchases.refill_modal.col.sales_60d', 'Vendes 60d')} sortKey="vendes_periode" sort={candSort} onSort={toggleCandSort} align="center" className="px-3 py-2" />
                    <SortableTh label={t('purchases.refill_modal.col.stock_days', 'Dies estoc')} sortKey="dies_estoc" sort={candSort} onSort={toggleCandSort} align="center" className="px-3 py-2" />
                    <SortableTh label={t('purchases.margin')} sortKey="marge_mitja" sort={candSort} onSort={toggleCandSort} align="right" className="px-3 py-2" />
                    <SortableTh label={t('purchases.type.supplier')} sortKey="proveedor_sugerido_nombre" sort={candSort} onSort={toggleCandSort} className="px-3 py-2"
                      filterOptions={candDistinct.proveedor_sugerido_nombre} selected={candFilters.proveedor_sugerido_nombre} onFilterChange={setCandFilter} />
                    <th className="px-3 py-2 text-center font-medium">{t('purchases.quantity', 'Quantitat')}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-100">
                  {candidatsSorted.map(c => {
                    const TendIcon = TENDENCIA_ICON[c.tendencia];
                    return (
                      <tr key={c.release_id} className={selected.has(c.release_id) ? '' : 'opacity-40'}>
                        <td className="px-3 py-2.5">
                          <input type="checkbox" checked={selected.has(c.release_id)} onChange={() => toggle(c.release_id)}
                            className="rounded border-zinc-300 text-amber-600 focus:ring-zinc-900" />
                        </td>
                        <td className="px-3 py-2.5">
                          <div className="font-medium text-zinc-900">{c.artista} — {c.titulo}</div>
                          {c.devolucions_recents > 0 && (
                            <div className="text-[11px] text-red-500">⚠ {c.devolucions_recents} {c.devolucions_recents > 1 ? t('purchases.refill_modal.recent_returns_plural', 'devolucions recents') : t('purchases.refill_modal.recent_returns', 'devolució recent')}</div>
                          )}
                        </td>
                        <td className="px-3 py-2.5 text-center text-zinc-600">{c.stock_actual}</td>
                        <td className="px-3 py-2.5 text-center">
                          <span className={`inline-flex items-center gap-1 ${TENDENCIA_COLOR[c.tendencia]}`}>
                            {c.vendes_periode} <TendIcon size={12} />
                          </span>
                        </td>
                        <td className="px-3 py-2.5 text-center text-zinc-600">{c.dies_estoc}</td>
                        <td className="px-3 py-2.5 text-right text-zinc-600">{c.marge_mitja != null ? `${parseFloat(c.marge_mitja).toFixed(2)} €` : '—'}</td>
                        <td className="px-3 py-2.5 text-zinc-600">{c.proveedor_sugerido_nombre ?? <span className="text-zinc-300">—</span>}</td>
                        <td className="px-3 py-2.5">
                          <input type="number" min="1" value={cantidades[c.release_id] ?? 1}
                            onChange={e => setCantidades(prev => ({ ...prev, [c.release_id]: e.target.value }))}
                            className="w-16 border border-zinc-300 rounded-lg px-2 py-1 text-sm text-center focus:outline-none focus:ring-1 focus:ring-zinc-900" />
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          {error && <p className="text-red-500 text-sm">{error}</p>}
          <div className="flex justify-end gap-3">
            <Button type="button" variant="secondary" onClick={onClose}>{t('common.cancel')}</Button>
            <Button type="button" onClick={save} disabled={saving || selected.size === 0}>
              {saving ? t('common.creating') : `${t('purchases.request_modal.create_btn', 'Crear sol·licitud')} (${selected.size})`}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
