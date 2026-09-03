'use client';

import { useState, useEffect, useRef, useMemo } from 'react';
import { authFetch } from '../../../lib/auth';
import { useT } from '../../../lib/i18n';
import { Button } from '../../../../components/ui/button';
import { useSortFilter } from '../../../../components/admin/table/useSortFilter';
import { SortableTh } from '../../../../components/admin/table/SortableTh';
import { ChevronDown, ChevronRight, Plus, PackageCheck, X } from 'lucide-react';

// Vista per defecte (sense necessitat de cercar) de l'històric de compres:
// llista de proveïdors desplegable (quants discos, quan la darrera) i un
// detall complet a sota. La cerca filtra totes dues parts alhora.
export default function HistorialPage() {
  const t = useT();
  const [q, setQ] = useState('');
  const [resum, setResum] = useState([]);
  const [detalle, setDetalle] = useState([]);
  const [loading, setLoading] = useState(true);
  const [expandedProv, setExpandedProv] = useState(null);
  const [expandedLineas, setExpandedLineas] = useState([]);
  const [loadingExpanded, setLoadingExpanded] = useState(false);
  const [cistella, setCistella] = useState([]); // { key, proveedor_id, proveedor_nombre, release_id, artista, titulo, sello, formato, cantidad }
  const [creantProveidor, setCreantProveidor] = useState(null);
  const debounce = useRef(null);

  function toggleCistella(l, proveedorId, proveedorNombre) {
    setCistella(prev => {
      if (prev.some(c => c.key === l.id)) return prev.filter(c => c.key !== l.id);
      return [...prev, {
        key: l.id, proveedor_id: proveedorId, proveedor_nombre: proveedorNombre,
        release_id: l.release_id ?? null, artista: l.artist, titulo: l.title,
        sello: l.label, formato: l.format, cantidad: 1,
      }];
    });
  }

  function updateQuantitat(key, cantidad) {
    setCistella(prev => prev.map(c => c.key === key ? { ...c, cantidad } : c));
  }

  function treureDeCistella(key) {
    setCistella(prev => prev.filter(c => c.key !== key));
  }

  async function crearSolicitud(proveedorId, proveedorNombre) {
    const items = cistella.filter(c => c.proveedor_id === proveedorId);
    if (items.length === 0) return;
    setCreantProveidor(proveedorId);
    try {
      const r = await authFetch('/admin/solicitudes-compra', {
        method: 'POST',
        body: JSON.stringify({
          origen: 'manual',
          notes: `${t('purchases.generated_from_search_supplier', 'Generada des de Cerca proveïdor')} (${proveedorNombre})`,
          lineas: items.map(c => ({
            release_id: c.release_id || undefined,
            artist: c.release_id ? undefined : c.artista,
            title: c.release_id ? undefined : c.titulo,
            label: c.release_id ? undefined : c.sello,
            format: c.release_id ? undefined : c.formato,
            quantity: c.cantidad,
            proveedor_sugerido_id: proveedorId,
          })),
        }),
      });
      if (!r.ok) {
        const body = await r.json().catch(() => ({}));
        alert(body.detail || t('purchases.request.create_error', 'No s\'ha pogut crear la sol·licitud.'));
        return;
      }
      setCistella(prev => prev.filter(c => c.proveedor_id !== proveedorId));
    } finally {
      setCreantProveidor(null);
    }
  }

  async function load(query) {
    setLoading(true);
    try {
      const qs = query.trim().length >= 2 ? `?q=${encodeURIComponent(query.trim())}` : '';
      const [rResum, rDetalle] = await Promise.all([
        authFetch(`/admin/historial-compres/resum${qs}`),
        authFetch(`/admin/historial-compres${qs}`),
      ]);
      setResum(rResum.ok ? await rResum.json() : []);
      setDetalle(rDetalle.ok ? await rDetalle.json() : []);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(''); }, []);

  const detalleColumns = useMemo(() => ({
    fecha: { sortValue: r => r.date ?? '' },
    proveedor_nombre: { sortValue: r => (r.proveedor_nombre ?? '').toLowerCase() },
    disc: { sortValue: r => (r.artist ? `${r.artist} ${r.title ?? ''}` : (r.notes ?? '')).toLowerCase() },
    sello: { sortValue: r => (r.label ?? '').toLowerCase() },
    precio_coste: { sortValue: r => r.cost_price != null ? parseFloat(r.cost_price) : null },
  }), []);
  const { rows: detalleSorted, sort: detalleSort, toggleSort: toggleDetalleSort } = useSortFilter(detalle, detalleColumns);

  function handleQ(val) {
    setQ(val);
    setExpandedProv(null);
    clearTimeout(debounce.current);
    debounce.current = setTimeout(() => load(val), 350);
  }

  async function toggleProveidor(proveedorId) {
    if (expandedProv === proveedorId) { setExpandedProv(null); return; }
    setExpandedProv(proveedorId);
    setLoadingExpanded(true);
    try {
      const qs = q.trim().length >= 2 ? `&q=${encodeURIComponent(q.trim())}` : '';
      const r = await authFetch(`/admin/historial-compres?proveedor_id=${proveedorId}${qs}`);
      setExpandedLineas(r.ok ? await r.json() : []);
    } finally {
      setLoadingExpanded(false);
    }
  }

  return (
    <div className="space-y-5 max-w-5xl mx-auto">
      <h2 className="text-2xl font-bold text-zinc-900">{t('purchases.tab.history', 'Historial')}</h2>

      <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm p-5 space-y-3">
        <input
          value={q}
          onChange={e => handleQ(e.target.value)}
          placeholder={t('purchases.search_history.search_ph', 'Cerca per artista, títol, segell... (opcional, per filtrar)')}
          className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900"
        />
        <p className="text-xs text-zinc-400">
          {t('purchases.search_history.hint', "Combina l'històric importat dels fulls de càlcul antics amb les comandes reals (enviada/rebuda) fetes des d'aquí — creix amb cada comanda nova. No indica estoc actual del proveïdor, només que se li ha comprat abans. Desplega un proveïdor per veure'n els discos.")}
        </p>
      </div>

      {cistella.length > 0 && (
        <div className="space-y-3">
          {Object.values(
            cistella.reduce((acc, c) => {
              (acc[c.proveedor_id] ??= { proveedor_id: c.proveedor_id, proveedor_nombre: c.proveedor_nombre, items: [] }).items.push(c);
              return acc;
            }, {})
          ).map(grup => (
            <div key={grup.proveedor_id} className="bg-blue-50/60 rounded-2xl border border-blue-100 shadow-sm overflow-hidden">
              <div className="px-5 py-3 flex items-center justify-between border-b border-blue-100">
                <span className="text-sm font-semibold text-zinc-700">
                  {grup.proveedor_nombre} · {grup.items.length} {grup.items.length === 1 ? t('purchases.record_singular', 'disc') : t('purchases.record_plural', 'discos')}
                </span>
                <Button onClick={() => crearSolicitud(grup.proveedor_id, grup.proveedor_nombre)} disabled={creantProveidor === grup.proveedor_id}>
                  {creantProveidor === grup.proveedor_id ? t('common.creating') : t('purchases.request_modal.create_btn', 'Crear sol·licitud')}
                </Button>
              </div>
              <div className="divide-y divide-blue-100/70">
                {grup.items.map(c => (
                  <div key={c.key} className="flex items-center gap-3 text-sm px-5 py-2 flex-wrap">
                    <span className="font-medium text-zinc-900 flex-1 min-w-[200px]">{c.artista} — {c.titulo}</span>
                    <input type="number" min="1" value={c.cantidad}
                      onChange={e => updateQuantitat(c.key, Math.max(1, parseInt(e.target.value) || 1))}
                      className="w-16 border border-zinc-300 rounded-lg px-2 py-1 text-sm text-center focus:outline-none focus:ring-2 focus:ring-zinc-900" />
                    <button onClick={() => treureDeCistella(c.key)} className="text-zinc-400 hover:text-red-500 p-1 rounded hover:bg-red-50">
                      <X size={14} />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {loading ? (
        <div className="text-sm text-zinc-400 text-center py-6">{t('common.loading')}</div>
      ) : (
        <>
          {resum.length === 0 ? (
            <div className="text-sm text-zinc-400 text-center py-6">{t('purchases.search_history.no_matches', "Cap coincidència a l'històric.")}</div>
          ) : (
            <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm overflow-hidden">
              <div className="px-5 py-3 text-sm font-semibold text-zinc-700 border-b border-zinc-100">
                {t('purchases.tab.suppliers')} ({resum.length})
              </div>
              <div className="divide-y divide-zinc-100">
                {resum.map(p => (
                  <div key={p.proveedor_id}>
                    <button
                      onClick={() => toggleProveidor(p.proveedor_id)}
                      className="w-full flex items-center justify-between px-5 py-3 text-sm hover:bg-zinc-50 transition-colors text-left"
                    >
                      <div className="flex items-center gap-2">
                        {expandedProv === p.proveedor_id ? <ChevronDown size={14} className="text-zinc-400" /> : <ChevronRight size={14} className="text-zinc-400" />}
                        <span className="font-medium text-zinc-900">{p.proveedor_nombre}</span>
                      </div>
                      <span className="text-zinc-500">
                        {p.count} {p.count === 1 ? t('purchases.search_history.purchase', 'compra') : t('purchases.search_history.purchases', 'compres')} · {t('purchases.search_history.last', 'última')} {new Date(p.ultima_compra).toLocaleDateString()}
                      </span>
                    </button>
                    {expandedProv === p.proveedor_id && (
                      <div className="bg-zinc-50/60 border-t border-zinc-100 px-5 py-3">
                        {loadingExpanded ? (
                          <div className="text-sm text-zinc-400 py-2">{t('common.loading')}</div>
                        ) : (
                          <div className="space-y-1.5">
                            {expandedLineas.map(l => {
                              const addable = !!(l.release_id || (l.artist && l.title));
                              const selected = cistella.some(c => c.key === l.id);
                              return (
                                <div key={l.id} className="flex items-center gap-3 text-sm flex-wrap">
                                  <span className="text-zinc-400 w-20 shrink-0">{new Date(l.date).toLocaleDateString()}</span>
                                  <span className="font-medium text-zinc-900">
                                    {l.artist ? `${l.artist}${l.title ? ` — ${l.title}` : ''}` : (l.notes ?? '—')}
                                  </span>
                                  {l.ean && <span className="text-[10px] uppercase tracking-wide text-emerald-600 bg-emerald-50 rounded-full px-2 py-0.5">EAN</span>}
                                  {l.cost_price != null && <span className="text-zinc-400 ml-auto">{l.cost_price} €</span>}
                                  {addable && (
                                    <button
                                      onClick={() => toggleCistella(l, p.proveedor_id, p.proveedor_nombre)}
                                      title={selected ? t('purchases.search_history.remove_from_request', 'Treure de la sol·licitud') : t('purchases.search_history.add_to_request', 'Afegir a sol·licitud')}
                                      className={`p-1 rounded-lg ${selected ? 'text-emerald-600 hover:bg-emerald-50' : 'text-zinc-400 hover:text-zinc-700 hover:bg-zinc-100'} ${l.cost_price == null ? 'ml-auto' : ''}`}
                                    >
                                      {selected ? <PackageCheck size={15} /> : <Plus size={15} />}
                                    </button>
                                  )}
                                </div>
                              );
                            })}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {detalle.length > 0 && (
            <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm overflow-hidden">
              <div className="px-5 py-3 text-sm font-semibold text-zinc-700 border-b border-zinc-100">
                {t('purchases.search_history.detail', 'Detall')} {q.trim().length >= 2 ? t('purchases.search_history.filtered', '(filtrat)') : t('purchases.search_history.most_recent', '(més recents)')}
              </div>
              <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-zinc-50 text-xs text-zinc-500 border-b border-zinc-200">
                  <tr>
                    <SortableTh label={t('common.date')} sortKey="fecha" sort={detalleSort} onSort={toggleDetalleSort} />
                    <SortableTh label={t('purchases.type.supplier')} sortKey="proveedor_nombre" sort={detalleSort} onSort={toggleDetalleSort} />
                    <SortableTh label={t('tpv.col.record')} sortKey="disc" sort={detalleSort} onSort={toggleDetalleSort} />
                    <SortableTh label={t('catalog.col.label')} sortKey="sello" sort={detalleSort} onSort={toggleDetalleSort} />
                    <SortableTh label={t('purchases.cost_short', 'Cost')} sortKey="precio_coste" sort={detalleSort} onSort={toggleDetalleSort} align="right" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-100">
                  {detalleSorted.map(r => (
                    <tr key={r.id}>
                      <td className="px-4 py-3 text-zinc-500">{new Date(r.date).toLocaleDateString()}</td>
                      <td className="px-4 py-3 font-medium">{r.proveedor_nombre}</td>
                      <td className="px-4 py-3">{r.artist ? `${r.artist}${r.title ? ` — ${r.title}` : ''}` : (r.notes ?? '—')}</td>
                      <td className="px-4 py-3 text-zinc-400">{r.label ?? '—'}</td>
                      <td className="px-4 py-3 text-right text-zinc-500">{r.cost_price != null ? `${r.cost_price} €` : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
