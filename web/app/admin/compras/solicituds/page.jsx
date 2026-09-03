'use client';

import { useState, useEffect, useRef, useMemo, Fragment } from 'react';
import { authFetch } from '../../../lib/auth';
import { useT } from '../../../lib/i18n';
import { useDiscogsEnabled } from '../../../../components/store/useDiscogsEnabled';
import { Button } from '../../../../components/ui/button';
import { useSortFilter } from '../../../../components/admin/table/useSortFilter';
import { SortableTh } from '../../../../components/admin/table/SortableTh';
import {
  Plus, ChevronDown, ChevronRight, X, Trash2, Ban, PackageCheck, ArrowRight, Sparkles, TrendingUp, TrendingDown, Minus,
} from 'lucide-react';
import { solicitudStatusLabel, SOLICITUD_STATUS_COLOR } from '../../../../components/admin/compras/shared';

// "Sol·licitud de compra": llista de discos a comprar sense proveïdor triat
// encara. Es pot deixar oberta, cancel·lar, o "resoldre" (repartint línies
// cap a una Comanda real d'un proveïdor concret).

export default function SolicitudsPage() {
  const t = useT();
  const [solicitudes, setSolicitudes] = useState([]);
  const [proveedores, setProveedores] = useState([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState(null);
  const [showSolicitudModal, setShowSolicitudModal] = useState(false);
  const [showRefillModal, setShowRefillModal] = useState(false);
  const [busyId, setBusyId] = useState(null);
  const [resolvingEstocLinea, setResolvingEstocLinea] = useState(null);
  const [seleccio, setSeleccio] = useState(() => new Set());
  const [resolvingLineas, setResolvingLineas] = useState(null);

  async function loadAll() {
    setLoading(true);
    const [sRes, pRes] = await Promise.all([
      authFetch('/admin/solicitudes-compra'),
      authFetch('/admin/proveedores'),
    ]);
    setSolicitudes(await sRes.json());
    setProveedores(await pRes.json());
    setLoading(false);
  }
  useEffect(() => { loadAll(); }, []);

  const noSuggestedSupplier = t('purchases.no_suggested_supplier', 'Sense proveïdor suggerit');
  const lineasPendents = solicitudes
    .filter(s => s.estado === 'oberta')
    .flatMap(s => s.lineas.filter(l => !l.resuelta).map(l => ({ ...l, solicitud_created_at: s.created_at })));

  const grups = new Map();
  for (const l of lineasPendents) {
    const key = l.proveedor_sugerido_nombre || noSuggestedSupplier;
    if (!grups.has(key)) grups.set(key, []);
    grups.get(key).push(l);
  }
  const gruposOrdenados = [...grups.entries()].sort(([a], [b]) => {
    if (a === noSuggestedSupplier) return 1;
    if (b === noSuggestedSupplier) return -1;
    return a.localeCompare(b);
  });

  function toggleLinia(id) {
    setSeleccio(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }

  const refillOriginLabel = t('purchases.origin.refill_stock', 'Reposició per vendes');
  const manualOriginLabel = t('purchases.origin.manual', 'Manual');
  const solicitudsColumns = useMemo(() => ({
    created_at: { sortValue: s => s.created_at ?? '' },
    origen: {
      sortValue: s => s.origen === 'refill_stock' ? refillOriginLabel : manualOriginLabel,
      filterValue: s => s.origen === 'refill_stock' ? refillOriginLabel : manualOriginLabel,
    },
    linies: { sortValue: s => s.lineas.length },
    estado: { sortValue: s => solicitudStatusLabel(t, s.estado), filterValue: s => solicitudStatusLabel(t, s.estado) },
  }), [t, refillOriginLabel, manualOriginLabel]);
  const {
    rows: solicitudesSorted, sort: solSort, toggleSort: toggleSolSort,
    filters: solFilters, setFilter: setSolFilter, distinctValues: solDistinct,
  } = useSortFilter(solicitudes, solicitudsColumns);

  function toggleGrup(lineasGrup) {
    const seleccionables = lineasGrup.filter(l => l.release_id);
    const totesSeleccionades = seleccionables.length > 0 && seleccionables.every(l => seleccio.has(l.id));
    setSeleccio(prev => {
      const next = new Set(prev);
      for (const l of seleccionables) {
        if (totesSeleccionades) next.delete(l.id); else next.add(l.id);
      }
      return next;
    });
  }

  async function cancelar(s) {
    if (!confirm(t('purchases.request.confirm_cancel', 'Cancel·lar aquesta sol·licitud?'))) return;
    setBusyId(s.id + '_cancelar');
    await authFetch(`/admin/solicitudes-compra/${s.id}/cancelar`, { method: 'PATCH' });
    setBusyId(null);
    loadAll();
  }

  async function eliminar(s) {
    if (!confirm(t('purchases.request.confirm_delete', 'Eliminar aquesta sol·licitud?'))) return;
    setBusyId(s.id + '_eliminar');
    const r = await authFetch(`/admin/solicitudes-compra/${s.id}`, { method: 'DELETE' });
    if (!r.ok) {
      const body = await r.json().catch(() => ({}));
      alert(body.detail || t('catalog.delete_error'));
    }
    setBusyId(null);
    loadAll();
  }

  async function eliminarLinia(s, l) {
    if (!confirm(t('purchases.request.confirm_remove_line', 'Treure "{disc}" d\'aquesta sol·licitud?').replace('{disc}', `${l.artist} — ${l.title}`))) return;
    setBusyId(l.id + '_eliminar_linia');
    const r = await authFetch(`/admin/solicitudes-compra/${s.id}/lineas/${l.id}`, { method: 'DELETE' });
    if (!r.ok) {
      const body = await r.json().catch(() => ({}));
      alert(body.detail || t('purchases.request.delete_line_error', 'No s\'ha pogut eliminar el disc.'));
    }
    setBusyId(null);
    loadAll();
  }

  return (
    <div className="space-y-5 max-w-5xl mx-auto">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-zinc-900">{t('purchases.tab.requests', 'Sol·licituds')}</h2>
        <div className="flex items-center gap-2">
          <button onClick={() => setShowRefillModal(true)}
            className="flex items-center gap-1.5 text-sm border border-zinc-200 text-zinc-600 hover:bg-zinc-50 px-3 py-2 rounded-lg transition-colors">
            <Sparkles size={13} /> {t('purchases.btn.generate_suggestions', 'Generar suggeriments')}
          </button>
          <Button onClick={() => setShowSolicitudModal(true)}>
            <Plus size={16} /> {t('purchases.btn.new_request', 'Nova sol·licitud')}
          </Button>
        </div>
      </div>

      {lineasPendents.length > 0 && (
        <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm overflow-hidden">
          <div className="px-5 py-3 border-b border-zinc-200">
            <div className="text-sm font-semibold text-zinc-900">{t('purchases.request.pending_records', 'Discos pendents de comanda')}</div>
            <div className="text-xs text-zinc-400">
              {t('purchases.request.pending_records_hint', 'Marca els discos que vols agrupar en una mateixa comanda, encara que vinguin de sol·licituds diferents.')}
            </div>
          </div>
          <div className="divide-y divide-zinc-100 max-h-96 overflow-y-auto">
            {gruposOrdenados.map(([nomProveedor, lineasGrup]) => {
              const seleccionables = lineasGrup.filter(l => l.release_id);
              const totesSeleccionades = seleccionables.length > 0 && seleccionables.every(l => seleccio.has(l.id));
              return (
                <div key={nomProveedor}>
                  <label className="flex items-center gap-2 px-5 py-2 bg-zinc-50 cursor-pointer">
                    <input type="checkbox" checked={totesSeleccionades} disabled={seleccionables.length === 0}
                      onChange={() => toggleGrup(lineasGrup)}
                      className="rounded border-zinc-300 text-amber-600 focus:ring-zinc-900" />
                    <span className="text-xs font-semibold text-zinc-600 uppercase tracking-wide">{nomProveedor}</span>
                    <span className="text-xs text-zinc-400">({lineasGrup.length})</span>
                  </label>
                  {lineasGrup.map(l => (
                    <label key={l.id}
                      className={`flex items-center gap-3 px-5 py-2.5 text-sm flex-wrap ${l.release_id ? 'cursor-pointer hover:bg-zinc-50' : 'opacity-50'}`}>
                      <input type="checkbox" checked={seleccio.has(l.id)} disabled={!l.release_id}
                        onChange={() => toggleLinia(l.id)}
                        className="rounded border-zinc-300 text-amber-600 focus:ring-zinc-900" />
                      <span className="font-medium text-zinc-900">{l.artist} — {l.title}</span>
                      <span className="text-zinc-500">{l.quantity}x</span>
                      {l.label && <span className="text-zinc-400">{l.label}</span>}
                      <span className="text-zinc-300 text-xs ml-auto">{new Date(l.solicitud_created_at).toLocaleDateString()}</span>
                      {!l.release_id && <span className="text-amber-600 text-xs">{t('purchases.request.needs_release', 'Cal donar d\'alta el disc abans')}</span>}
                    </label>
                  ))}
                </div>
              );
            })}
          </div>
          {seleccio.size > 0 && (
            <div className="px-5 py-3 bg-amber-50 border-t border-amber-100 flex items-center justify-between">
              <span className="text-sm font-medium text-amber-800">
                {seleccio.size} {seleccio.size !== 1 ? t('purchases.request.records_selected_plural', 'discs seleccionats') : t('purchases.request.records_selected', 'disc seleccionat')}
              </span>
              <div className="flex items-center gap-3">
                <button onClick={() => setSeleccio(new Set())} className="text-xs text-zinc-500 hover:text-zinc-700">
                  {t('purchases.request.clear_selection', 'Netejar selecció')}
                </button>
                <Button size="sm" onClick={() => setResolvingLineas(lineasPendents.filter(l => seleccio.has(l.id)))}>
                  <ArrowRight size={13} /> {t('purchases.request.create_order', 'Crear comanda')}
                </Button>
              </div>
            </div>
          )}
        </div>
      )}

      <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm overflow-hidden">
        {loading ? (
          <div className="p-12 text-center text-zinc-400 text-sm">{t('common.loading')}</div>
        ) : solicitudes.length === 0 ? (
          <div className="p-12 text-center text-zinc-400 text-sm">{t('purchases.request.no_requests', 'Encara no hi ha cap sol·licitud de compra.')}</div>
        ) : (
          <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-zinc-50 text-xs text-zinc-500 border-b border-zinc-200">
              <tr>
                <th className="w-8 px-4 py-3" />
                <SortableTh label={t('common.date')} sortKey="created_at" sort={solSort} onSort={toggleSolSort} />
                <SortableTh label={t('purchases.col.origin')} sortKey="origen" sort={solSort} onSort={toggleSolSort}
                  filterOptions={solDistinct.origen} selected={solFilters.origen} onFilterChange={setSolFilter} />
                <SortableTh label={t('purchases.col.lines', 'Línies')} sortKey="linies" sort={solSort} onSort={toggleSolSort} align="center" />
                <SortableTh label={t('purchases.col.status', 'Estat')} sortKey="estado" sort={solSort} onSort={toggleSolSort}
                  filterOptions={solDistinct.estado} selected={solFilters.estado} onFilterChange={setSolFilter} />
                <th className="px-4 py-3 text-right font-medium">{t('catalog.col.actions')}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-100">
              {solicitudesSorted.map(s => {
                const pendents = s.lineas.filter(l => !l.resuelta).length;
                return (
                  <Fragment key={s.id}>
                    <tr onClick={() => setExpanded(expanded === s.id ? null : s.id)}
                      className="hover:bg-zinc-50 cursor-pointer transition-colors">
                      <td className="px-4 py-3 text-zinc-400">
                        {expanded === s.id ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                      </td>
                      <td className="px-4 py-3 text-zinc-500">{new Date(s.created_at).toLocaleDateString()}</td>
                      <td className="px-4 py-3 text-zinc-500">
                        {s.origen === 'refill_stock' ? refillOriginLabel : manualOriginLabel}
                        {s.user_nom && <span className="text-zinc-400"> · {s.user_nom}</span>}
                      </td>
                      <td className="px-4 py-3 text-center">
                        <span className="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium bg-zinc-100 text-zinc-700">
                          {s.lineas.length}{pendents > 0 && pendents < s.lineas.length ? ` (${pendents} ${t('purchases.pending', 'pendents')})` : ''}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${SOLICITUD_STATUS_COLOR[s.estado]}`}>
                          {solicitudStatusLabel(t, s.estado)}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right" onClick={e => e.stopPropagation()}>
                        <div className="flex items-center justify-end gap-1.5">
                          {s.estado === 'oberta' && pendents > 0 && (
                            <button onClick={() => setResolvingLineas(s.lineas.filter(l => !l.resuelta))} title={t('purchases.action.resolve_to_order', 'Resoldre cap a una comanda')}
                              className="flex items-center gap-1 text-xs font-semibold text-amber-600 hover:text-amber-700 border border-amber-200 rounded-lg px-2 py-1 hover:bg-amber-50 transition-colors">
                              <ArrowRight size={12} /> {t('purchases.action.resolve', 'Resoldre')}
                            </button>
                          )}
                          {s.estado === 'oberta' && (
                            <button onClick={() => cancelar(s)} disabled={busyId === s.id + '_cancelar'} title={t('common.cancel')}
                              className="p-1.5 text-zinc-400 hover:text-red-500 rounded-lg hover:bg-red-50 disabled:opacity-50">
                              <Ban size={14} />
                            </button>
                          )}
                          {pendents === s.lineas.length && (
                            <button onClick={() => eliminar(s)} disabled={busyId === s.id + '_eliminar'} title={t('catalog.delete')}
                              className="p-1.5 text-zinc-300 hover:text-red-500 rounded-lg hover:bg-red-50 disabled:opacity-50">
                              <Trash2 size={14} />
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                    {expanded === s.id && (
                      <tr>
                        <td colSpan={6} className="px-4 py-3 bg-amber-50/40 border-b border-amber-100">
                          <div className="space-y-1">
                            {s.lineas.map(l => (
                              <div key={l.id} className="flex items-center gap-3 text-sm flex-wrap">
                                <span className="font-semibold text-zinc-900">{l.artist} — {l.title}</span>
                                <span className="text-zinc-500">{l.quantity}x</span>
                                {l.label && <span className="text-zinc-400">{l.label}</span>}
                                {l.proveedor_sugerido_nombre && (
                                  <span className="text-zinc-400">{t('purchases.suggested', 'Suggerit')}: {l.proveedor_sugerido_nombre}</span>
                                )}
                                {l.resuelta ? (
                                  <span className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium bg-emerald-100 text-emerald-700">
                                    {l.item_resuelto_id ? t('purchases.solicitud_status.resolved_stock', 'Resolta (estoc)') : solicitudStatusLabel(t, 'resolta')}
                                  </span>
                                ) : (
                                  <>
                                    <span className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium bg-zinc-100 text-zinc-500">
                                      {t('purchases.pending', 'Pendent')}
                                    </span>
                                    {l.release_id && (
                                      <button onClick={() => setResolvingEstocLinea(l)}
                                        className="flex items-center gap-1 text-xs font-medium text-emerald-600 hover:text-emerald-700 border border-emerald-200 rounded-lg px-2 py-0.5 hover:bg-emerald-50 transition-colors">
                                        <PackageCheck size={11} /> {t('purchases.action.resolve_from_stock', "Resoldre d'estoc")}
                                      </button>
                                    )}
                                    <button onClick={() => eliminarLinia(s, l)} disabled={busyId === l.id + '_eliminar_linia'}
                                      title={t('purchases.action.remove_from_request', 'Treure aquest disc de la sol·licitud')}
                                      className="p-1 text-zinc-300 hover:text-red-500 rounded-lg hover:bg-red-50 disabled:opacity-50 ml-auto">
                                      <Trash2 size={13} />
                                    </button>
                                  </>
                                )}
                              </div>
                            ))}
                          </div>
                          {s.notes && <div className="mt-2 text-xs text-zinc-400">{s.notes}</div>}
                        </td>
                      </tr>
                    )}
                  </Fragment>
                );
              })}
            </tbody>
          </table>
          </div>
        )}

        {resolvingEstocLinea && (
          <ResoldreEstocModal
            linea={resolvingEstocLinea}
            onClose={() => setResolvingEstocLinea(null)}
            onSaved={() => { setResolvingEstocLinea(null); loadAll(); }} />
        )}
      </div>

      {resolvingLineas && (
        <ResoldreSolicitudModal
          lineas={resolvingLineas} proveedores={proveedores}
          onClose={() => setResolvingLineas(null)}
          onSaved={() => { setResolvingLineas(null); setSeleccio(new Set()); loadAll(); }} />
      )}

      {showSolicitudModal && (
        <NovaSolicitudModal
          proveedores={proveedores}
          onClose={() => setShowSolicitudModal(false)}
          onSaved={() => { setShowSolicitudModal(false); loadAll(); }} />
      )}
      {showRefillModal && (
        <RefillSugerenciesModal
          onClose={() => setShowRefillModal(false)}
          onSaved={() => { setShowRefillModal(false); loadAll(); }} />
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

function NovaSolicitudModal({ proveedores, onClose, onSaved }) {
  const t = useT();
  const discogsEnabled = useDiscogsEnabled();
  const [notas, setNotas] = useState('');
  const [lineas, setLineas] = useState([]);
  const [discogsQ, setDiscogsQ] = useState('');
  const [discogsRes, setDiscogsRes] = useState([]);
  const [searchingDiscogs, setSearchingDiscogs] = useState(false);
  const [resolving, setResolving] = useState(false);
  const [manualMode, setManualMode] = useState(false);
  const [manualForm, setManualForm] = useState({ artista: '', titulo: '', sello: '', formato: 'LP', anio: '' });
  const [saving, setSaving] = useState(false);
  const discogsDebounce = useRef(null);

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
      return { id: m.id, artista: m.artista, titulo: m.titulo, sello: m.sello, existing: true };
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
    return { id, artista, titulo, sello, existing: false };
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
      await addLinea(rel);
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
      await addLinea(rel);
      setManualForm({ artista: '', titulo: '', sello: '', formato: 'LP', anio: '' });
      setManualMode(false);
    } finally {
      setResolving(false);
    }
  }

  async function suggestProveidor(releaseId, artista) {
    // Primer intent: el mateix disc del catàleg (senyal fort). Si no hi ha
    // historial per aquest release, provem per artista (senyal més feble).
    let rows = [];
    if (releaseId) {
      const r = await authFetch(`/admin/historial-compres?release_id=${releaseId}`);
      rows = r.ok ? await r.json() : [];
    }
    if (rows.length === 0 && artista) {
      const r = await authFetch(`/admin/historial-compres?q=${encodeURIComponent(artista)}`);
      rows = r.ok ? await r.json() : [];
    }
    if (rows.length === 0) return '';
    const counts = new Map();
    for (const row of rows) {
      counts.set(row.proveedor_id, (counts.get(row.proveedor_id) || 0) + 1);
    }
    return [...counts.entries()].sort((a, b) => b[1] - a[1])[0][0];
  }

  async function addLinea(rel) {
    // El match per release_id nomes te sentit si el disc ja existia al catàleg,
    // però el fallback per artista val independentment (encara que aquest disc
    // concret sigui nou i no s'hagi comprat mai).
    const proveedorSugerit = await suggestProveidor(rel.existing ? rel.id : null, rel.artista);
    setLineas(prev => [...prev, {
      release_id: rel.id, artista: rel.artista, titulo: rel.titulo, sello: rel.sello, existing: rel.existing,
      cantidad: 1, proveedor_sugerido_id: proveedorSugerit,
    }]);
  }

  function upd(idx, k, v) { setLineas(prev => prev.map((l, i) => i === idx ? { ...l, [k]: v } : l)); }

  async function save(e) {
    e.preventDefault();
    setSaving(true);
    const payload = {
      origen: 'manual',
      notes: notas || null,
      lineas: lineas.map(l => ({
        release_id: l.release_id,
        quantity: parseInt(l.cantidad, 10),
        proveedor_sugerido_id: l.proveedor_sugerido_id || null,
      })),
    };
    const r = await authFetch('/admin/solicitudes-compra', { method: 'POST', body: JSON.stringify(payload) });
    setSaving(false);
    if (r.ok) onSaved();
  }

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-start justify-center p-4 overflow-y-auto">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-3xl my-8">
        <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-200">
          <h3 className="text-lg font-bold text-zinc-900">{t('purchases.request_modal.title', 'Nova sol·licitud de compra')}</h3>
          <button onClick={onClose} className="text-zinc-400 hover:text-zinc-600 p-1 rounded-lg hover:bg-zinc-100"><X size={20} /></button>
        </div>

        <form onSubmit={save} className="p-6 space-y-5">
          <p className="text-xs text-zinc-400">
            {t('purchases.request_modal.hint', 'Afegeix els discos que vols comprar, encara sense triar proveïdor. Més endavant les resoldràs cap a una o diverses comandes des de la pestanya "Sol·licituds".')}
          </p>
          <div>
            <label className="block text-sm font-medium text-zinc-700 mb-1">{t('common.notes')}</label>
            <input value={notas} onChange={e => setNotas(e.target.value)}
              className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
          </div>

          <div className="border border-zinc-200 rounded-xl p-4 space-y-3">
            <div className="text-sm font-semibold text-zinc-700">{t('purchases.request_modal.wanted_records', 'Discos volguts')}</div>
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

            {lineas.length === 0 && (
              <div className="text-sm text-zinc-400 text-center py-4">{t('purchases.individual_modal.no_items', 'Encara no has afegit cap disc.')}</div>
            )}

            <div className="space-y-2">
              {lineas.map((l, idx) => (
                <div key={idx} className="p-3 bg-zinc-50 rounded-xl border border-zinc-200">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-semibold text-zinc-900">{l.artista} — {l.titulo}</span>
                      {l.existing && (
                        <span className="text-[10px] uppercase tracking-wide text-zinc-400 bg-zinc-100 rounded-full px-2 py-0.5">
                          {t('purchases.modal.already_in_catalog', 'Ja al catàleg')}
                        </span>
                      )}
                    </div>
                    <button type="button" onClick={() => setLineas(p => p.filter((_, i) => i !== idx))}
                      className="text-zinc-400 hover:text-red-500 transition-colors">
                      <Trash2 size={15} />
                    </button>
                  </div>
                  <div className="flex flex-wrap gap-3">
                    <div>
                      <label className="block text-xs text-zinc-500 mb-1">{t('purchases.quantity', 'Quantitat')}</label>
                      <input type="number" min="1" value={l.cantidad} onChange={e => upd(idx, 'cantidad', e.target.value)}
                        className="w-20 border border-zinc-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-zinc-900" />
                    </div>
                    <div>
                      <label className="block text-xs text-zinc-500 mb-1">{t('purchases.suggested_supplier', 'Proveïdor suggerit')}</label>
                      <select value={l.proveedor_sugerido_id} onChange={e => upd(idx, 'proveedor_sugerido_id', e.target.value)}
                        className="border border-zinc-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-zinc-900 bg-white">
                        <option value="">—</option>
                        {proveedores.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
                      </select>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="flex justify-end gap-3">
            <Button type="button" variant="secondary" onClick={onClose}>{t('common.cancel')}</Button>
            <Button type="submit" disabled={saving || lineas.length === 0}>
              {saving ? t('common.saving') : `${t('purchases.request_modal.create_btn', 'Crear sol·licitud')} (${lineas.length})`}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}

function ResoldreSolicitudModal({ lineas, proveedores, onClose, onSaved }) {
  const t = useT();
  const pendents = lineas.filter(l => !l.resuelta);
  const [proveedorId, setProveedorId] = useState(pendents[0]?.proveedor_sugerido_id || '');
  const [fecha, setFecha] = useState(new Date().toISOString().slice(0, 10));
  const [notas, setNotas] = useState('');
  const [seleccio, setSeleccio] = useState(() => new Set(pendents.map(l => l.id)));
  const [preus, setPreus] = useState(() => Object.fromEntries(pendents.map(l => [l.id, ''])));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  function toggle(id) {
    setSeleccio(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
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
            {pendents.map(l => (
              <label key={l.id} className="flex items-center gap-3 px-4 py-3 cursor-pointer hover:bg-zinc-50">
                <input type="checkbox" checked={seleccio.has(l.id)} onChange={() => toggle(l.id)}
                  className="rounded border-zinc-300 text-amber-600 focus:ring-zinc-900" />
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-zinc-900 truncate">{l.artist} — {l.title}</div>
                  <div className="text-xs text-zinc-400">{l.quantity}x{l.label ? ` · ${l.label}` : ''}</div>
                </div>
                <input type="number" step="0.01" min="0" placeholder={t('purchases.est_price', 'Preu est.')} value={preus[l.id] ?? ''}
                  onChange={e => setPreus(prev => ({ ...prev, [l.id]: e.target.value }))}
                  onClick={e => e.stopPropagation()}
                  className="w-24 border border-zinc-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-zinc-900" />
              </label>
            ))}
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

  const candidatsColumns = useMemo(() => ({
    disc: { sortValue: c => `${c.artista ?? ''} ${c.titulo ?? ''}`.toLowerCase() },
    stock_actual: { sortValue: c => c.stock_actual ?? 0 },
    vendes_periode: { sortValue: c => c.vendes_periode ?? 0 },
    dies_estoc: { sortValue: c => c.dies_estoc ?? 0 },
    marge_mitja: { sortValue: c => c.marge_mitja != null ? parseFloat(c.marge_mitja) : null },
    proveedor_sugerido_nombre: {
      sortValue: c => (c.proveedor_sugerido_nombre ?? '').toLowerCase(),
      filterValue: c => c.proveedor_sugerido_nombre,
    },
  }), []);
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
