'use client';

import { useState, useEffect, useRef, Fragment } from 'react';
import Link from 'next/link';
import { authFetch } from '../../../lib/auth';
import { useT } from '../../../lib/i18n';
import { resolveOrCreateRelease } from '../../../lib/discogs';
import { useDiscogsEnabled } from '../../../../components/store/useDiscogsEnabled';
import { Button } from '../../../../components/ui/button';
import { useSortFilter } from '../../../../components/admin/table/useSortFilter';
import { SortableTh } from '../../../../components/admin/table/SortableTh';
import DiscogsSearchField from '../../../../components/admin/discogs/DiscogsSearchField';
import MIcon from '../../../../components/ui/m-icon';
import {
  poolLineaEstat, poolLineaEstatLabel, POOL_LINEA_ESTAT_COLOR, origenSolicitudLabel, origenesSolicitudLabel,
  ORIGEN_SOLICITUD_COLOR, solicitudStatusLabel, SOLICITUD_STATUS_COLOR,
} from '../../../../components/admin/compras/shared';

// Pool de línies de sol·licitud: totes les línies de tots els orígens
// (manual / reposició / petició de client) i de tots els lots, aplanades en
// una sola llista paginada. Aquest és el "com" real amb què l'admin gestiona
// les sol·licituds — el lot (`SolicitudCompra`) que les agrupa és només
// metadata de cada línia (veure GET /admin/solicitudes-compra/pool), no una
// unitat de treball pròpia.
const PAGE_SIZE = 30;
const ESTAT_TABS = ['pendent', 'resolta', 'totes'];

export default function SolicitudsPage() {
  const t = useT();
  const [vista, setVista] = useState('pool');
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
  const [generatingLineas, setGeneratingLineas] = useState(null);
  const [showRefillModal, setShowRefillModal] = useState(false);
  const [showVentasModal, setShowVentasModal] = useState(false);
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
    const r = await authFetch(`/admin/solicitudes-compra/pool/lineas/${row.id}`, { method: 'DELETE' });
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
        <h2 className="text-2xl font-bold text-on-surface">{t('purchases.tab.requests', 'Sol·licituds')}</h2>
        <div className="flex items-center gap-2">
          <button onClick={() => setShowVentasModal(true)}
            className="flex items-center gap-1.5 text-sm border border-outline-variant text-on-surface-variant hover:bg-surface-container-high px-3 py-2 rounded-lg transition-colors">
            <MIcon name="receipt_long" size={13} /> {t('purchases.btn.recent_sales', 'Vendes recents')}
          </button>
          <button onClick={() => setShowRefillModal(true)}
            className="flex items-center gap-1.5 text-sm border border-outline-variant text-on-surface-variant hover:bg-surface-container-high px-3 py-2 rounded-lg transition-colors">
            <MIcon name="auto_awesome" size={13} /> {t('purchases.btn.generate_suggestions', 'Generar suggeriments')}
          </button>
          <Link href="/admin/compras/solicituds/nueva"
            className="flex items-center gap-1.5 bg-primary hover:opacity-90 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors">
            <MIcon name="add" size={15} /> {t('purchases.btn.add_to_pool', 'Afegir al pool')}
          </Link>
        </div>
      </div>

      <div className="flex items-center gap-1 border-b border-outline-variant">
        <button onClick={() => setVista('pool')}
          className={`px-3 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${vista === 'pool' ? 'border-primary text-on-surface' : 'border-transparent text-secondary-foreground hover:text-on-surface-variant'}`}>
          {t('purchases.view.pool', 'Pool de compra')}
        </button>
        <button onClick={() => setVista('llistat')}
          className={`px-3 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${vista === 'llistat' ? 'border-primary text-on-surface' : 'border-transparent text-secondary-foreground hover:text-on-surface-variant'}`}>
          {t('purchases.view.list', 'Registre de sol·licituds')}
        </button>
      </div>

      {vista === 'llistat' && <SolicitudsLlistatView proveedores={proveedores} />}

      {vista === 'pool' && (
      <>
      <div className="flex items-center gap-2 flex-wrap">
        <div className="flex items-center gap-1 bg-surface-container-high rounded-lg p-1">
          {ESTAT_TABS.map(tab => (
            <button key={tab} onClick={() => setEstado(tab)}
              className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${estado === tab ? 'bg-card text-on-surface shadow-sm' : 'text-secondary-foreground hover:text-on-surface-variant'}`}>
              {t(`purchases.pool.tab.${tab}`, tab)}
            </button>
          ))}
        </div>
        <select value={origen} onChange={e => setOrigen(e.target.value)}
          className="border border-outline-variant rounded-lg px-2.5 py-1.5 text-sm bg-card focus:outline-none focus:ring-2 focus:ring-primary">
          <option value="">{t('purchases.pool.filter.origin_all', 'Tots els orígens')}</option>
          <option value="manual">{origenSolicitudLabel(t, 'manual')}</option>
          <option value="refill_stock">{origenSolicitudLabel(t, 'refill_stock')}</option>
          <option value="peticion_cliente">{origenSolicitudLabel(t, 'peticion_cliente')}</option>
        </select>
        <select value={proveedorId} onChange={e => setProveedorId(e.target.value)}
          className="border border-outline-variant rounded-lg px-2.5 py-1.5 text-sm bg-card focus:outline-none focus:ring-2 focus:ring-primary">
          <option value="">{t('purchases.pool.filter.supplier_all', 'Tots els proveïdors')}</option>
          {proveedores.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
        </select>
        <input value={qInput} onChange={e => handleQInput(e.target.value)}
          placeholder={t('purchases.pool.search_ph', 'Cerca per artista o títol...')}
          className="border border-outline-variant rounded-lg px-3 py-1.5 text-sm flex-1 min-w-[180px] focus:outline-none focus:ring-2 focus:ring-primary" />
      </div>

      {seleccio.size > 0 && (
        <div className="px-4 py-3 bg-amber-50 border border-amber-100 rounded-xl flex items-center justify-between">
          <span className="text-sm font-medium text-amber-800">
            {seleccio.size} {seleccio.size !== 1 ? t('purchases.request.records_selected_plural', 'discs seleccionats') : t('purchases.request.records_selected', 'disc seleccionat')}
          </span>
          <div className="flex items-center gap-3">
            <button onClick={() => setSeleccio(new Map())} className="text-xs text-secondary-foreground hover:text-on-surface-variant">
              {t('purchases.request.clear_selection', 'Netejar selecció')}
            </button>
            <Button size="sm" onClick={() => setGeneratingLineas([...seleccio.values()])}>
              <MIcon name="arrow_forward" size={13} /> {t('purchases.request.generate_request', 'Crear sol·licitud')}
            </Button>
          </div>
        </div>
      )}

      <div className="bg-card rounded-2xl border border-outline-variant shadow-sm overflow-hidden">
        {loading ? (
          <div className="p-12 text-center text-secondary-foreground text-sm">{t('common.loading')}</div>
        ) : rows.length === 0 ? (
          <div className="p-12 text-center text-secondary-foreground text-sm">{t('purchases.pool.empty', 'No hi ha cap disc en aquest filtre.')}</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-surface-container-high text-xs text-secondary-foreground border-b border-outline-variant">
                <tr>
                  <th className="w-8 px-4 py-3">
                    <input type="checkbox"
                      checked={rows.some(r => poolLineaEstat(r) === 'pendent') && rows.filter(r => poolLineaEstat(r) === 'pendent').every(r => seleccio.has(r.id))}
                      onChange={toggleAllVisible}
                      className="rounded border-outline-variant text-amber-600 focus:ring-primary" />
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
              <tbody className="divide-y divide-outline-variant">
                {rows.map(row => {
                  const estat = poolLineaEstat(row);
                  return (
                    <tr key={row.id} className="hover:bg-surface-container-high">
                      <td className="px-4 py-3">
                        <input type="checkbox" checked={seleccio.has(row.id)} disabled={estat !== 'pendent'}
                          onChange={() => toggleLinea(row)}
                          className="rounded border-outline-variant text-amber-600 focus:ring-primary disabled:opacity-30" />
                      </td>
                      <td className="px-4 py-3">
                        <div className="font-medium text-on-surface">{row.artist} — {row.title}</div>
                        {row.label && <div className="text-xs text-secondary-foreground">{row.label}</div>}
                        {row.notes && <div className="text-xs text-secondary-foreground">{row.notes}</div>}
                      </td>
                      <td className="px-4 py-3 text-center text-on-surface-variant">{row.quantity}x</td>
                      <td className="px-4 py-3">
                        <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${ORIGEN_SOLICITUD_COLOR[row.origen] ?? 'bg-surface-container-high text-on-surface-variant'}`}>
                          {origenSolicitudLabel(t, row.origen)}
                        </span>
                        {row.origen === 'peticion_cliente' && (
                          <div className="text-xs text-secondary-foreground mt-0.5">{row.cliente_nombre || row.cliente_email}</div>
                        )}
                      </td>
                      <td className="px-4 py-3 text-on-surface-variant">{row.proveedor_sugerido_nombre ?? <span className="text-secondary-foreground">—</span>}</td>
                      <td className="px-4 py-3">
                        <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${POOL_LINEA_ESTAT_COLOR[estat]}`}>
                          {poolLineaEstatLabel(t, row)}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-secondary-foreground">{new Date(row.created_at).toLocaleDateString()}</td>
                      <td className="px-4 py-3 text-right">
                        {estat === 'pendent' && (
                          <div className="flex items-center justify-end gap-1.5">
                            {row.release_id && (
                              <button onClick={() => setResolvingEstocLinea(row)}
                                title={t('purchases.action.resolve_from_stock', "Resoldre d'estoc")}
                                className="flex items-center gap-1 text-xs font-medium text-emerald-600 hover:text-emerald-700 border border-emerald-200 rounded-lg px-2 py-1 hover:bg-emerald-50 transition-colors">
                                <MIcon name="local_shipping" size={12} />
                              </button>
                            )}
                            <button onClick={() => eliminarLinia(row)} disabled={busyId === row.id}
                              title={t('purchases.action.remove_from_request', 'Treure aquest disc de la sol·licitud')}
                              className="p-1.5 text-secondary-foreground hover:text-red-500 rounded-lg hover:bg-red-50 disabled:opacity-50">
                              <MIcon name="delete" size={14} />
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
          <div className="flex items-center justify-between px-4 py-3 border-t border-outline-variant text-xs text-secondary-foreground">
            <span>{from}–{to} {t('common.of', 'de')} {total}</span>
            <div className="flex gap-2">
              <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}
                className="px-3 py-1.5 border border-outline-variant rounded-lg hover:bg-surface-container-high disabled:opacity-40 transition-colors">
                ← {t('common.previous', 'Anterior')}
              </button>
              <button onClick={() => setPage(p => p + 1)} disabled={page * PAGE_SIZE >= total}
                className="px-3 py-1.5 border border-outline-variant rounded-lg hover:bg-surface-container-high disabled:opacity-40 transition-colors">
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

      {generatingLineas && (
        <GenerarSolicitudModal
          lineas={generatingLineas}
          onClose={() => setGeneratingLineas(null)}
          onSaved={() => { setGeneratingLineas(null); setSeleccio(new Map()); loadPool(); }} />
      )}
      </>
      )}

      {showRefillModal && (
        <RefillSugerenciesModal
          onClose={() => setShowRefillModal(false)}
          onSaved={() => { setShowRefillModal(false); loadPool(); }} />
      )}

      {showVentasModal && (
        <VentasRecientesModal
          onClose={() => setShowVentasModal(false)}
          onSaved={() => { setShowVentasModal(false); loadPool(); }} />
      )}
    </div>
  );
}

// Consolida línies seleccionades del pool (poden ser de diversos orígens)
// en una nova sol·licitud numerada — el pas "Crear sol·licitud". Encara no
// tria proveïdor: això és un pas posterior, des del registre (veure
// ResoldreSolicitudModal, que sí que el demana per crear la comanda).
function GenerarSolicitudModal({ lineas, onClose, onSaved }) {
  const t = useT();
  const [notas, setNotas] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  async function save(e) {
    e.preventDefault();
    setSaving(true);
    setError('');
    const r = await authFetch('/admin/solicitudes-compra/generar', {
      method: 'POST',
      body: JSON.stringify({ linea_ids: lineas.map(l => l.id), notes: notas || null }),
    });
    setSaving(false);
    if (r.ok) onSaved();
    else setError((await r.json().catch(() => ({}))).detail || t('purchases.action.resolve_error', 'No s\'ha pogut resoldre.'));
  }

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-start justify-center p-4 overflow-y-auto">
      <div className="bg-card rounded-2xl shadow-2xl w-full max-w-lg my-8">
        <div className="flex items-center justify-between px-6 py-4 border-b border-outline-variant">
          <h3 className="text-lg font-bold text-on-surface">{t('purchases.generate_request_modal.title', 'Crear sol·licitud')}</h3>
          <button onClick={onClose} className="text-secondary-foreground hover:text-on-surface-variant p-1 rounded-lg hover:bg-surface-container-high"><MIcon name="close" size={20} /></button>
        </div>
        <form onSubmit={save} className="p-6 space-y-4">
          <p className="text-xs text-secondary-foreground">
            {t('purchases.generate_request_modal.hint', 'Aquestes línies (poden venir de diversos orígens) es consolidaran en una sol·licitud numerada. Podràs triar proveïdor i crear-ne la comanda més endavant, des del registre.')}
          </p>
          <div className="border border-outline-variant rounded-xl divide-y divide-outline-variant max-h-64 overflow-y-auto">
            {lineas.map(l => (
              <div key={l.id} className="px-4 py-2.5 text-sm flex items-center gap-2 flex-wrap">
                <span className="font-medium text-on-surface">{l.artist} — {l.title}</span>
                <span className="text-secondary-foreground">{l.quantity}x</span>
                <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium ${ORIGEN_SOLICITUD_COLOR[l.origen] ?? 'bg-surface-container-high text-on-surface-variant'}`}>
                  {origenSolicitudLabel(t, l.origen)}
                </span>
                {l.origen === 'peticion_cliente' && (
                  <span className="text-secondary-foreground text-xs">{l.cliente_nombre || l.cliente_email}</span>
                )}
              </div>
            ))}
          </div>
          <div>
            <label className="block text-sm font-medium text-on-surface-variant mb-1">{t('common.notes')}</label>
            <input value={notas} onChange={e => setNotas(e.target.value)}
              className="w-full border border-outline-variant rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary" />
          </div>
          {error && <p className="text-red-500 text-sm">{error}</p>}
          <div className="flex justify-end gap-3">
            <Button type="button" variant="secondary" onClick={onClose}>{t('common.cancel')}</Button>
            <Button type="submit" disabled={saving}>
              {saving ? t('common.creating') : `${t('purchases.generate_request_modal.submit', 'Crear sol·licitud')} (${lineas.length})`}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}

const LLISTAT_PAGE_SIZE = 20;
const LLISTAT_ESTAT_TABS = ['oberta', 'resolta', 'cancelada', 'totes'];

// Registre de sol·licituds com a entitat (una fila = un lot, amb el seu
// número — veure GET /admin/solicitudes-compra): a diferència del pool
// (aplanat per línia), aquí es classifica per sol·licitud, per poder
// referenciar-ne una en concret ("SOL-2026-000004").
function SolicitudsLlistatView({ proveedores }) {
  const t = useT();
  const [estado, setEstado] = useState('oberta');
  const [origen, setOrigen] = useState('');
  const [page, setPage] = useState(1);
  const [solicitudes, setSolicitudes] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState(null);
  const [busyId, setBusyId] = useState(null);
  const [resolvingEstocLinea, setResolvingEstocLinea] = useState(null);
  const [resolvingLineas, setResolvingLineas] = useState(null);

  async function loadSolicituds() {
    setLoading(true);
    const params = new URLSearchParams({ page: String(page), page_size: String(LLISTAT_PAGE_SIZE) });
    if (estado !== 'totes') params.set('estado', estado);
    if (origen) params.set('origen', origen);
    const r = await authFetch(`/admin/solicitudes-compra?${params.toString()}`);
    const data = await r.json();
    setSolicitudes(data.results ?? []);
    setTotal(data.total ?? 0);
    setLoading(false);
  }
  useEffect(() => { loadSolicituds(); }, [estado, origen, page]);
  useEffect(() => { setPage(1); }, [estado, origen]);

  async function cancelar(s) {
    if (!confirm(t('purchases.request.confirm_cancel', 'Cancel·lar aquesta sol·licitud?'))) return;
    setBusyId(s.id + '_cancelar');
    await authFetch(`/admin/solicitudes-compra/${s.id}/cancelar`, { method: 'PATCH' });
    setBusyId(null);
    loadSolicituds();
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
    loadSolicituds();
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
    loadSolicituds();
  }

  const from = total === 0 ? 0 : (page - 1) * LLISTAT_PAGE_SIZE + 1;
  const to = Math.min(page * LLISTAT_PAGE_SIZE, total);

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 flex-wrap">
        <div className="flex items-center gap-1 bg-surface-container-high rounded-lg p-1">
          {LLISTAT_ESTAT_TABS.map(tab => (
            <button key={tab} onClick={() => setEstado(tab)}
              className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${estado === tab ? 'bg-card text-on-surface shadow-sm' : 'text-secondary-foreground hover:text-on-surface-variant'}`}>
              {tab === 'totes' ? t('purchases.pool.tab.totes', 'Totes') : solicitudStatusLabel(t, tab)}
            </button>
          ))}
        </div>
        <select value={origen} onChange={e => setOrigen(e.target.value)}
          className="border border-outline-variant rounded-lg px-2.5 py-1.5 text-sm bg-card focus:outline-none focus:ring-2 focus:ring-primary">
          <option value="">{t('purchases.pool.filter.origin_all', 'Tots els orígens')}</option>
          <option value="manual">{origenSolicitudLabel(t, 'manual')}</option>
          <option value="refill_stock">{origenSolicitudLabel(t, 'refill_stock')}</option>
          <option value="peticion_cliente">{origenSolicitudLabel(t, 'peticion_cliente')}</option>
        </select>
      </div>

      <div className="bg-card rounded-2xl border border-outline-variant shadow-sm overflow-hidden">
        {loading ? (
          <div className="p-12 text-center text-secondary-foreground text-sm">{t('common.loading')}</div>
        ) : solicitudes.length === 0 ? (
          <div className="p-12 text-center text-secondary-foreground text-sm">{t('purchases.request.no_requests', 'Encara no hi ha cap sol·licitud de compra.')}</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-surface-container-high text-xs text-secondary-foreground border-b border-outline-variant">
                <tr>
                  <th className="w-8 px-4 py-3" />
                  <th className="px-4 py-3 text-left font-medium">{t('purchases.col.number', 'Número')}</th>
                  <th className="px-4 py-3 text-left font-medium">{t('common.date')}</th>
                  <th className="px-4 py-3 text-left font-medium">{t('purchases.col.origin')}</th>
                  <th className="px-4 py-3 text-center font-medium">{t('purchases.col.lines', 'Línies')}</th>
                  <th className="px-4 py-3 text-left font-medium">{t('purchases.col.status')}</th>
                  <th className="px-4 py-3 text-right font-medium">{t('catalog.col.actions')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-outline-variant">
                {solicitudes.map(s => {
                  const pendents = s.lineas.filter(l => !l.resuelta).length;
                  return (
                    <Fragment key={s.id}>
                      <tr onClick={() => setExpanded(expanded === s.id ? null : s.id)}
                        className="hover:bg-surface-container-high cursor-pointer transition-colors">
                        <td className="px-4 py-3 text-secondary-foreground">
                          {expanded === s.id ? <MIcon name="expand_more" size={14} /> : <MIcon name="chevron_right" size={14} />}
                        </td>
                        <td className="px-4 py-3 font-mono text-xs text-on-surface-variant">{s.numero}</td>
                        <td className="px-4 py-3 text-secondary-foreground">{new Date(s.created_at).toLocaleDateString()}</td>
                        <td className="px-4 py-3">
                          <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${s.origenes.length === 1 ? (ORIGEN_SOLICITUD_COLOR[s.origenes[0]] ?? 'bg-surface-container-high text-on-surface-variant') : 'bg-fuchsia-100 text-fuchsia-700'}`}>
                            {origenesSolicitudLabel(t, s.origenes)}
                          </span>
                          {s.user_nom && <span className="text-secondary-foreground text-xs"> · {s.user_nom}</span>}
                        </td>
                        <td className="px-4 py-3 text-center">
                          <span className="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium bg-surface-container-high text-on-surface-variant">
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
                                <MIcon name="arrow_forward" size={12} /> {t('purchases.action.resolve', 'Resoldre')}
                              </button>
                            )}
                            {s.estado === 'oberta' && (
                              <button onClick={() => cancelar(s)} disabled={busyId === s.id + '_cancelar'} title={t('common.cancel')}
                                className="p-1.5 text-secondary-foreground hover:text-red-500 rounded-lg hover:bg-red-50 disabled:opacity-50">
                                <MIcon name="block" size={14} />
                              </button>
                            )}
                            {pendents === s.lineas.length && (
                              <button onClick={() => eliminar(s)} disabled={busyId === s.id + '_eliminar'} title={t('catalog.delete')}
                                className="p-1.5 text-secondary-foreground hover:text-red-500 rounded-lg hover:bg-red-50 disabled:opacity-50">
                                <MIcon name="delete" size={14} />
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>
                      {expanded === s.id && (
                        <tr>
                          <td colSpan={7} className="px-4 py-3 bg-amber-50/40 border-b border-amber-100">
                            <div className="space-y-1">
                              {s.lineas.map(l => (
                                <div key={l.id} className="flex items-center gap-3 text-sm flex-wrap">
                                  <span className="font-semibold text-on-surface">{l.artist} — {l.title}</span>
                                  <span className="text-secondary-foreground">{l.quantity}x</span>
                                  {l.label && <span className="text-secondary-foreground">{l.label}</span>}
                                  <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium ${ORIGEN_SOLICITUD_COLOR[l.origen] ?? 'bg-surface-container-high text-on-surface-variant'}`}>
                                    {origenSolicitudLabel(t, l.origen)}
                                  </span>
                                  {l.origen === 'peticion_cliente' && (
                                    <span className="text-secondary-foreground">{l.cliente_nombre || l.cliente_email}</span>
                                  )}
                                  {l.proveedor_sugerido_nombre && (
                                    <span className="text-secondary-foreground">{t('purchases.suggested', 'Suggerit')}: {l.proveedor_sugerido_nombre}</span>
                                  )}
                                  {l.resuelta ? (
                                    <span className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium bg-emerald-100 text-emerald-700">
                                      {l.item_resuelto_id ? t('purchases.solicitud_status.resolved_stock', 'Resolta (estoc)') : solicitudStatusLabel(t, 'resolta')}
                                    </span>
                                  ) : (
                                    <>
                                      <span className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium bg-surface-container-high text-secondary-foreground">
                                        {t('purchases.pending', 'Pendent')}
                                      </span>
                                      {l.release_id && (
                                        <button onClick={() => setResolvingEstocLinea(l)}
                                          className="flex items-center gap-1 text-xs font-medium text-emerald-600 hover:text-emerald-700 border border-emerald-200 rounded-lg px-2 py-0.5 hover:bg-emerald-50 transition-colors">
                                          <MIcon name="local_shipping" size={11} /> {t('purchases.action.resolve_from_stock', "Resoldre d'estoc")}
                                        </button>
                                      )}
                                      <button onClick={() => eliminarLinia(s, l)} disabled={busyId === l.id + '_eliminar_linia'}
                                        title={t('purchases.action.remove_from_request', 'Treure aquest disc de la sol·licitud')}
                                        className="p-1 text-secondary-foreground hover:text-red-500 rounded-lg hover:bg-red-50 disabled:opacity-50 ml-auto">
                                        <MIcon name="delete" size={13} />
                                      </button>
                                    </>
                                  )}
                                </div>
                              ))}
                            </div>
                            {s.notes && <div className="mt-2 text-xs text-secondary-foreground">{s.notes}</div>}
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
        {total > LLISTAT_PAGE_SIZE && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-outline-variant text-xs text-secondary-foreground">
            <span>{from}–{to} {t('common.of', 'de')} {total}</span>
            <div className="flex gap-2">
              <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}
                className="px-3 py-1.5 border border-outline-variant rounded-lg hover:bg-surface-container-high disabled:opacity-40 transition-colors">
                ← {t('common.previous', 'Anterior')}
              </button>
              <button onClick={() => setPage(p => p + 1)} disabled={page * LLISTAT_PAGE_SIZE >= total}
                className="px-3 py-1.5 border border-outline-variant rounded-lg hover:bg-surface-container-high disabled:opacity-40 transition-colors">
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
          onSaved={() => { setResolvingEstocLinea(null); loadSolicituds(); }} />
      )}

      {resolvingLineas && (
        <ResoldreSolicitudModal
          lineas={resolvingLineas} proveedores={proveedores}
          onClose={() => setResolvingLineas(null)}
          onSaved={() => { setResolvingLineas(null); loadSolicituds(); }} />
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
      <div className="bg-card rounded-xl max-w-sm w-full p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-bold text-on-surface">{t('purchases.action.resolve_from_stock', "Resoldre d'estoc")}</h2>
          <button onClick={onClose} className="text-secondary-foreground hover:text-on-surface-variant"><MIcon name="close" size={18} /></button>
        </div>
        <p className="text-sm text-secondary-foreground mb-4">{linea.artist} — {linea.title}</p>
        <p className="text-xs text-secondary-foreground mb-4">
          {t('purchases.resolve_stock_modal.hint', "Tria l'exemplar que ja hi ha a estoc per tancar aquesta línia sense fer-ne una comanda a proveïdor.")}
        </p>
        {error && <p className="text-sm text-red-600 mb-3">{error}</p>}
        {items === null ? (
          <div className="animate-pulse bg-surface-container-high rounded-lg h-16" />
        ) : items.length === 0 ? (
          <p className="text-sm text-secondary-foreground text-center py-6">{t('purchases.resolve_stock_modal.no_items', 'Aquest disc no té cap exemplar disponible a estoc ara mateix.')}</p>
        ) : (
          <div className="space-y-1.5">
            {items.map(i => (
              <button key={i.id} disabled={saving} onClick={() => resoldre(i)}
                className="w-full flex items-center justify-between p-2.5 rounded-lg shadow-[0_2px_20px_-6px_rgba(15,23,42,0.08)] hover:border-emerald-300 hover:bg-emerald-50/30 transition-colors text-sm disabled:opacity-50">
                <span className="text-on-surface-variant">
                  {i.condition} {i.estado_disco ? `· ${i.estado_disco}` : ''}
                  {i.condition === 'nou' && ` · ${i.quantity - i.reserved_quantity} ${t('purchases.units_free', 'lliures')}`}
                </span>
                <span className="font-medium text-on-surface">{Number(i.price).toFixed(2)} €</span>
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
  const [resolvingRelease, setResolvingRelease] = useState(false);
  const [manualMode, setManualMode] = useState(false);
  const [manualForm, setManualForm] = useState({ artista: '', titulo: '', sello: '', formato: 'LP', anio: '' });

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
  }

  function applyResolved(rel) {
    setResolvedReleases(prev => ({ ...prev, [resolvingLineaId]: rel }));
    setSeleccio(prev => new Set(prev).add(resolvingLineaId));
    setResolvingLineaId(null);
  }

  async function pickDiscogs(full) {
    setResolvingRelease(true);
    try {
      const rel = await resolveOrCreateRelease(full);
      applyResolved(rel);
    } finally {
      setResolvingRelease(false);
    }
  }

  async function addManual() {
    if (!manualForm.titulo.trim()) return;
    setResolvingRelease(true);
    try {
      const rel = await resolveOrCreateRelease(manualForm);
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
      <div className="bg-card rounded-2xl shadow-2xl w-full max-w-2xl my-8">
        <div className="flex items-center justify-between px-6 py-4 border-b border-outline-variant">
          <h3 className="text-lg font-bold text-on-surface">{t('purchases.resolve_request_modal.title', 'Crear comanda des de sol·licituds')}</h3>
          <button onClick={onClose} className="text-secondary-foreground hover:text-on-surface-variant p-1 rounded-lg hover:bg-surface-container-high"><MIcon name="close" size={20} /></button>
        </div>

        <form onSubmit={save} className="p-6 space-y-5">
          <p className="text-xs text-secondary-foreground">
            {t('purchases.resolve_request_modal.hint', 'Tria quines línies (poden venir de sol·licituds diferents) van a la mateixa comanda. Les que no seleccionis queden pendents per resoldre-les després (cap a un altre proveïdor, per exemple).')}
          </p>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-on-surface-variant mb-1">{t('purchases.type.supplier')}</label>
              <select value={proveedorId} onChange={e => setProveedorId(e.target.value)} required
                className="w-full border border-outline-variant rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary bg-card">
                <option value="">{t('common.select')}</option>
                {proveedores.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-on-surface-variant mb-1">{t('common.date')}</label>
              <input type="date" value={fecha} onChange={e => setFecha(e.target.value)} required
                className="w-full border border-outline-variant rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary" />
            </div>
            <div className="col-span-2">
              <label className="block text-sm font-medium text-on-surface-variant mb-1">{t('purchases.order_notes', 'Notes de la comanda')}</label>
              <input value={notas} onChange={e => setNotas(e.target.value)}
                className="w-full border border-outline-variant rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary" />
            </div>
          </div>

          <div className="border border-outline-variant rounded-xl divide-y divide-outline-variant">
            {pendents.map(l => {
              const resolved = resolvedReleases[l.id];
              const catalogat = !!l.release_id || !!resolved;
              return (
                <Fragment key={l.id}>
                  <div className="flex items-center gap-3 px-4 py-3 hover:bg-surface-container-high">
                    <input type="checkbox" checked={seleccio.has(l.id)} disabled={!catalogat} onChange={() => toggle(l.id)}
                      className="rounded border-outline-variant text-amber-600 focus:ring-primary disabled:opacity-40" />
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium text-on-surface truncate">
                        {resolved ? `${resolved.artista} — ${resolved.titulo}` : `${l.artist} — ${l.title}`}
                      </div>
                      <div className="text-xs text-secondary-foreground flex items-center gap-1.5">
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
                        className="w-24 border border-outline-variant rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-primary" />
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
                        <DiscogsSearchField key={l.id} onPick={pickDiscogs} disabled={resolvingRelease} autoFocus />
                      )}
                      {discogsEnabled && (
                        <button type="button" onClick={() => setManualMode(m => !m)}
                          className="text-xs text-amber-600 hover:text-amber-700 font-medium">
                          {manualMode ? t('common.cancel') : t('purchases.add_manual_toggle', '+ Afegir disc a mà')}
                        </button>
                      )}
                      {(!discogsEnabled || manualMode) && (
                        <div className="p-3 bg-card rounded-xl border border-outline-variant space-y-2">
                          <div className="grid grid-cols-2 gap-2">
                            <input value={manualForm.artista} onChange={e => setManualForm(f => ({ ...f, artista: e.target.value }))}
                              placeholder={t('purchases.manual.artist_ph', 'Artista')}
                              className="border border-outline-variant rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-primary" />
                            <input value={manualForm.titulo} onChange={e => setManualForm(f => ({ ...f, titulo: e.target.value }))}
                              placeholder={t('purchases.manual.title_ph', 'Títol')}
                              className="border border-outline-variant rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-primary" />
                            <input value={manualForm.sello} onChange={e => setManualForm(f => ({ ...f, sello: e.target.value }))}
                              placeholder={t('purchases.manual.label_ph', 'Segell')}
                              className="border border-outline-variant rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-primary" />
                            <select value={manualForm.formato} onChange={e => setManualForm(f => ({ ...f, formato: e.target.value }))}
                              className="border border-outline-variant rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-primary bg-card">
                              {['LP', 'EP', '7"', '12"', 'CD', 'Cassette'].map(x => <option key={x}>{x}</option>)}
                              <option>{t('purchases.manual.format_other', 'Altre')}</option>
                            </select>
                            <input type="number" value={manualForm.anio} onChange={e => setManualForm(f => ({ ...f, anio: e.target.value }))}
                              placeholder={t('purchases.manual.year_ph', 'Any')} min="1900" max="2030"
                              className="border border-outline-variant rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-primary" />
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

const TENDENCIA_ICON = { accelerant: 'trending_up', frenant: 'trending_down', estable: 'remove' };
const TENDENCIA_COLOR = { accelerant: 'text-emerald-600', frenant: 'text-red-500', estable: 'text-secondary-foreground' };

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
    const nota = `${t('purchases.refill_modal.auto_generated', 'Generat automàticament')} (${new Date().toLocaleDateString()})`;
    const payload = {
      origen: 'refill_stock',
      lineas: candidats.filter(c => selected.has(c.release_id)).map(c => ({
        release_id: c.release_id,
        quantity: parseInt(cantidades[c.release_id], 10) || 1,
        proveedor_sugerido_id: c.proveedor_sugerido_id || null,
        notes: nota,
      })),
    };
    const r = await authFetch('/admin/solicitudes-compra/pool', { method: 'POST', body: JSON.stringify(payload) });
    setSaving(false);
    if (r.ok) onSaved();
    else setError((await r.json().catch(() => ({}))).detail || t('purchases.request.create_error', 'No s\'ha pogut crear la sol·licitud.'));
  }

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-start justify-center p-4 overflow-y-auto">
      <div className="bg-card rounded-2xl shadow-2xl w-full max-w-4xl my-8">
        <div className="flex items-center justify-between px-6 py-4 border-b border-outline-variant">
          <h3 className="text-lg font-bold text-on-surface">{t('purchases.btn.generate_suggestions_title', 'Suggeriments de reposició')}</h3>
          <button onClick={onClose} className="text-secondary-foreground hover:text-on-surface-variant p-1 rounded-lg hover:bg-surface-container-high"><MIcon name="close" size={20} /></button>
        </div>

        <div className="p-6 space-y-4">
          <p className="text-xs text-secondary-foreground">
            {t('purchases.refill_modal.hint', "Discos amb estoc nou baix que es continuen venent (vendes dels últims 60 dies), amb menys de 21 dies d'estoc restant al ritme actual. No inclou discos amb una comanda ja oberta. La quantitat i el proveïdor són editables abans de crear la sol·licitud.")}
          </p>

          {loading ? (
            <div className="text-sm text-secondary-foreground text-center py-8">{t('purchases.refill_modal.calculating', 'Calculant...')}</div>
          ) : candidats.length === 0 ? (
            <div className="text-sm text-secondary-foreground text-center py-8">
              {t('purchases.refill_modal.no_candidates', 'Ara mateix no hi ha cap disc que compleixi els criteris de reposició.')}
            </div>
          ) : (
            <div className="border border-outline-variant rounded-xl overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-surface-container-high text-xs text-secondary-foreground border-b border-outline-variant">
                  <tr>
                    <th className="w-8 px-3 py-2">
                      <input type="checkbox"
                        checked={candidatsSorted.length > 0 && candidatsSorted.every(c => selected.has(c.release_id))}
                        onChange={() => toggleAllVisible(candidatsSorted)}
                        title={candidatsSorted.every(c => selected.has(c.release_id)) ? t('purchases.refill_modal.unselect_all', 'Desmarcar-ho tot') : t('purchases.refill_modal.select_all', 'Seleccionar-ho tot')}
                        className="rounded border-outline-variant text-amber-600 focus:ring-primary" />
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
                <tbody className="divide-y divide-outline-variant">
                  {candidatsSorted.map(c => {
                    const tendIcon = TENDENCIA_ICON[c.tendencia];
                    return (
                      <tr key={c.release_id} className={selected.has(c.release_id) ? '' : 'opacity-40'}>
                        <td className="px-3 py-2.5">
                          <input type="checkbox" checked={selected.has(c.release_id)} onChange={() => toggle(c.release_id)}
                            className="rounded border-outline-variant text-amber-600 focus:ring-primary" />
                        </td>
                        <td className="px-3 py-2.5">
                          <div className="font-medium text-on-surface">{c.artista} — {c.titulo}</div>
                          {c.devolucions_recents > 0 && (
                            <div className="text-[11px] text-red-500">⚠ {c.devolucions_recents} {c.devolucions_recents > 1 ? t('purchases.refill_modal.recent_returns_plural', 'devolucions recents') : t('purchases.refill_modal.recent_returns', 'devolució recent')}</div>
                          )}
                        </td>
                        <td className="px-3 py-2.5 text-center text-on-surface-variant">{c.stock_actual}</td>
                        <td className="px-3 py-2.5 text-center">
                          <span className={`inline-flex items-center gap-1 ${TENDENCIA_COLOR[c.tendencia]}`}>
                            {c.vendes_periode} <MIcon name={tendIcon} size={12} />
                          </span>
                        </td>
                        <td className="px-3 py-2.5 text-center text-on-surface-variant">{c.dies_estoc}</td>
                        <td className="px-3 py-2.5 text-right text-on-surface-variant">{c.marge_mitja != null ? `${parseFloat(c.marge_mitja).toFixed(2)} €` : '—'}</td>
                        <td className="px-3 py-2.5 text-on-surface-variant">{c.proveedor_sugerido_nombre ?? <span className="text-secondary-foreground">—</span>}</td>
                        <td className="px-3 py-2.5">
                          <input type="number" min="1" value={cantidades[c.release_id] ?? 1}
                            onChange={e => setCantidades(prev => ({ ...prev, [c.release_id]: e.target.value }))}
                            className="w-16 border border-outline-variant rounded-lg px-2 py-1 text-sm text-center focus:outline-none focus:ring-1 focus:ring-primary" />
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
              {saving ? t('common.creating') : `${t('purchases.btn.add_to_pool', 'Afegir al pool')} (${selected.size})`}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

// Browser complementari a RefillSugerenciesModal: llista TOTES les vendes
// (només còpies noves) en un rang de dates lliure, sense cap llindar
// d'urgència ni exclusió per comanda oberta — per a vendes puntuals que
// "Generar suggeriments" descarta perquè encara queda prou estoc pel ritme
// de venda actual. L'admin decideix què val la pena reposar.
function VentasRecientesModal({ onClose, onSaved }) {
  const t = useT();
  const avui = new Date().toISOString().slice(0, 10);
  const fa90dies = new Date(Date.now() - 90 * 86400000).toISOString().slice(0, 10);
  const [desde, setDesde] = useState(fa90dies);
  const [hasta, setHasta] = useState(avui);
  const [ventas, setVentas] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState(new Set());
  const [cantidades, setCantidades] = useState({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    (async () => {
      setLoading(true);
      const params = new URLSearchParams({ desde, hasta });
      const r = await authFetch(`/admin/solicitudes-compra/ventas-recientes?${params.toString()}`);
      const data = r.ok ? await r.json() : [];
      setVentas(data);
      setCantidades(Object.fromEntries(data.map(v => [v.release_id, 1])));
      setLoading(false);
    })();
  }, [desde, hasta]);

  function toggle(releaseId) {
    setSelected(prev => {
      const next = new Set(prev);
      if (next.has(releaseId)) next.delete(releaseId); else next.add(releaseId);
      return next;
    });
  }

  function toggleAllVisible(visibleRows) {
    setSelected(prev => {
      const allSelected = visibleRows.length > 0 && visibleRows.every(v => prev.has(v.release_id));
      const next = new Set(prev);
      visibleRows.forEach(v => allSelected ? next.delete(v.release_id) : next.add(v.release_id));
      return next;
    });
  }

  const ventasColumns = {
    disc: { sortValue: v => `${v.artista ?? ''} ${v.titulo ?? ''}`.toLowerCase() },
    unidades_vendidas: { sortValue: v => v.unidades_vendidas ?? 0 },
    ultima_venta: { sortValue: v => v.ultima_venta ?? '' },
    stock_actual: { sortValue: v => v.stock_actual ?? 0 },
    proveedor_sugerido_nombre: {
      sortValue: v => (v.proveedor_sugerido_nombre ?? '').toLowerCase(),
      filterValue: v => v.proveedor_sugerido_nombre,
    },
  };
  const {
    rows: ventasSorted, sort: ventSort, toggleSort: toggleVentSort,
    filters: ventFilters, setFilter: setVentFilter, distinctValues: ventDistinct,
  } = useSortFilter(ventas, ventasColumns);

  async function save(e) {
    e.preventDefault();
    if (selected.size === 0) return;
    setSaving(true);
    setError('');
    const nota = `${t('purchases.ventas_modal.manual_from_sales', 'Afegit des de Vendes recents')} (${new Date().toLocaleDateString()})`;
    const payload = {
      origen: 'manual',
      lineas: ventas.filter(v => selected.has(v.release_id)).map(v => ({
        release_id: v.release_id,
        quantity: parseInt(cantidades[v.release_id], 10) || 1,
        proveedor_sugerido_id: v.proveedor_sugerido_id || null,
        notes: nota,
      })),
    };
    const r = await authFetch('/admin/solicitudes-compra/pool', { method: 'POST', body: JSON.stringify(payload) });
    setSaving(false);
    if (r.ok) onSaved();
    else setError((await r.json().catch(() => ({}))).detail || t('purchases.request.create_error', 'No s\'ha pogut crear la sol·licitud.'));
  }

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-start justify-center p-4 overflow-y-auto">
      <div className="bg-card rounded-2xl shadow-2xl w-full max-w-4xl my-8">
        <div className="flex items-center justify-between px-6 py-4 border-b border-outline-variant">
          <h3 className="text-lg font-bold text-on-surface">{t('purchases.ventas_modal.title', 'Vendes recents')}</h3>
          <button onClick={onClose} className="text-secondary-foreground hover:text-on-surface-variant p-1 rounded-lg hover:bg-surface-container-high"><MIcon name="close" size={20} /></button>
        </div>

        <div className="p-6 space-y-4">
          <p className="text-xs text-secondary-foreground">
            {t('purchases.ventas_modal.hint', "Tot el que s'ha venut (només còpies noves) en aquest rang de dates, sense cap filtre d'urgència: útil per a vendes puntuals que \"Generar suggeriments\" no proposa perquè encara queda prou estoc pel ritme de venda actual.")}
          </p>

          <div className="flex items-center gap-3 flex-wrap">
            <label className="flex items-center gap-1.5 text-sm text-on-surface-variant">
              {t('common.from', 'Des de')}
              <input type="date" value={desde} onChange={e => setDesde(e.target.value)} max={hasta}
                className="border border-outline-variant rounded-lg px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary" />
            </label>
            <label className="flex items-center gap-1.5 text-sm text-on-surface-variant">
              {t('common.to', 'Fins a')}
              <input type="date" value={hasta} onChange={e => setHasta(e.target.value)} min={desde} max={avui}
                className="border border-outline-variant rounded-lg px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary" />
            </label>
          </div>

          {loading ? (
            <div className="text-sm text-secondary-foreground text-center py-8">{t('common.loading')}</div>
          ) : ventas.length === 0 ? (
            <div className="text-sm text-secondary-foreground text-center py-8">
              {t('purchases.ventas_modal.no_sales', 'No hi ha vendes de còpies noves en aquest rang de dates.')}
            </div>
          ) : (
            <div className="border border-outline-variant rounded-xl overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-surface-container-high text-xs text-secondary-foreground border-b border-outline-variant">
                  <tr>
                    <th className="w-8 px-3 py-2">
                      <input type="checkbox"
                        checked={ventasSorted.length > 0 && ventasSorted.every(v => selected.has(v.release_id))}
                        onChange={() => toggleAllVisible(ventasSorted)}
                        className="rounded border-outline-variant text-amber-600 focus:ring-primary" />
                    </th>
                    <SortableTh label={t('tpv.col.record')} sortKey="disc" sort={ventSort} onSort={toggleVentSort} className="px-3 py-2" />
                    <SortableTh label={t('purchases.ventas_modal.col.units_sold', 'Unitats venudes')} sortKey="unidades_vendidas" sort={ventSort} onSort={toggleVentSort} align="center" className="px-3 py-2" />
                    <SortableTh label={t('purchases.ventas_modal.col.last_sale', 'Última venda')} sortKey="ultima_venta" sort={ventSort} onSort={toggleVentSort} className="px-3 py-2" />
                    <SortableTh label={t('catalog.col.stock')} sortKey="stock_actual" sort={ventSort} onSort={toggleVentSort} align="center" className="px-3 py-2" />
                    <SortableTh label={t('purchases.type.supplier')} sortKey="proveedor_sugerido_nombre" sort={ventSort} onSort={toggleVentSort} className="px-3 py-2"
                      filterOptions={ventDistinct.proveedor_sugerido_nombre} selected={ventFilters.proveedor_sugerido_nombre} onFilterChange={setVentFilter} />
                    <th className="px-3 py-2 text-center font-medium">{t('purchases.quantity', 'Quantitat')}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-outline-variant">
                  {ventasSorted.map(v => (
                    <tr key={v.release_id} className={selected.has(v.release_id) ? '' : 'opacity-60'}>
                      <td className="px-3 py-2.5">
                        <input type="checkbox" checked={selected.has(v.release_id)} onChange={() => toggle(v.release_id)}
                          className="rounded border-outline-variant text-amber-600 focus:ring-primary" />
                      </td>
                      <td className="px-3 py-2.5">
                        <div className="font-medium text-on-surface">{v.artista} — {v.titulo}</div>
                        {v.tiene_comanda_abierta && (
                          <div className="text-[11px] text-amber-600">{t('purchases.ventas_modal.open_order', 'Ja té una comanda oberta')}</div>
                        )}
                      </td>
                      <td className="px-3 py-2.5 text-center text-on-surface-variant">{v.unidades_vendidas}</td>
                      <td className="px-3 py-2.5 text-on-surface-variant">{new Date(v.ultima_venta).toLocaleDateString()}</td>
                      <td className="px-3 py-2.5 text-center text-on-surface-variant">{v.stock_actual}</td>
                      <td className="px-3 py-2.5 text-on-surface-variant">{v.proveedor_sugerido_nombre ?? <span className="text-secondary-foreground">—</span>}</td>
                      <td className="px-3 py-2.5">
                        <input type="number" min="1" value={cantidades[v.release_id] ?? 1}
                          onChange={e => setCantidades(prev => ({ ...prev, [v.release_id]: e.target.value }))}
                          className="w-16 border border-outline-variant rounded-lg px-2 py-1 text-sm text-center focus:outline-none focus:ring-1 focus:ring-primary" />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {error && <p className="text-red-500 text-sm">{error}</p>}
          <div className="flex justify-end gap-3">
            <Button type="button" variant="secondary" onClick={onClose}>{t('common.cancel')}</Button>
            <Button type="button" onClick={save} disabled={saving || selected.size === 0}>
              {saving ? t('common.creating') : `${t('purchases.btn.add_to_pool', 'Afegir al pool')} (${selected.size})`}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
