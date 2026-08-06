'use client';

import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { authFetch } from '../../lib/auth';
import { useT } from '../../lib/i18n';
import { Button } from '../../../components/ui/button';
import { useSortFilter } from '../../../components/admin/table/useSortFilter';
import { SortableTh } from '../../../components/admin/table/SortableTh';
import {
  Plus, Search, Disc3, ChevronDown, ChevronRight, X, Pencil, Trash2, Copy,
  AlertTriangle, RefreshCw, Upload, Image, Loader2, Download, FileSpreadsheet,
  CheckCircle2, Clock, CircleOff, ImageIcon, Music2, Eye,
} from 'lucide-react';

function fmtEur(n) {
  return `${parseFloat(n).toLocaleString('ca-ES', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} €`;
}

const GRADINGS = ['Mint (M)', 'Near Mint (NM or M-)', 'Very Good Plus (VG+)', 'Very Good (VG)', 'Good Plus (G+)', 'Good (G)', 'Fair (F)', 'Poor (P)'];
const LIMIT = 50;
const CATALOG_FETCH_LIMIT = 5000;

// ---- Helpers ---------------------------------------------------------------

function syncStatus(item, release) {
  if (item.codi_discogs) return 'listed';
  if (release.discogs_release_id) return 'pending';
  return 'no_release_id';
}

function SyncBadge({ status, codiDiscogs }) {
  if (status === 'listed') return (
    <span className="inline-flex items-center gap-1 text-xs font-medium text-emerald-700 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded-full whitespace-nowrap">
      <CheckCircle2 size={9} /> #{codiDiscogs}
    </span>
  );
  if (status === 'pending') return (
    <span className="inline-flex items-center gap-1 text-xs font-medium text-amber-700 bg-amber-50 border border-amber-200 px-2 py-0.5 rounded-full">
      <Clock size={9} /> Pendent
    </span>
  );
  return (
    <span className="inline-flex items-center gap-1 text-xs font-medium text-zinc-400 bg-zinc-50 border border-zinc-200 px-2 py-0.5 rounded-full">
      <CircleOff size={9} /> Sense ID
    </span>
  );
}

function ReleaseSyncSummary({ items, discogs_release_id }) {
  if (!items?.length) return <span className="text-zinc-300 text-xs">—</span>;
  const active = items.filter(i => i.status === 'disponible' || i.status === 'reservado');
  if (!active.length) return <span className="text-zinc-300 text-xs">—</span>;
  const listed = active.filter(i => i.codi_discogs).length;
  const pending = active.filter(i => !i.codi_discogs && discogs_release_id).length;
  if (listed === 0 && pending === 0) return <span className="text-xs text-zinc-400">—</span>;
  return (
    <div className="flex items-center gap-1.5 flex-wrap">
      {listed > 0 && (
        <span className="inline-flex items-center gap-0.5 text-xs text-emerald-700 bg-emerald-50 border border-emerald-200 px-1.5 py-0.5 rounded-full">
          <CheckCircle2 size={9} /> {listed}
        </span>
      )}
      {pending > 0 && (
        <span className="inline-flex items-center gap-0.5 text-xs text-amber-700 bg-amber-50 border border-amber-200 px-1.5 py-0.5 rounded-full">
          <Clock size={9} /> {pending}
        </span>
      )}
    </div>
  );
}

function CoverImg({ url, size = 36 }) {
  const [failed, setFailed] = useState(false);
  if (!url || failed) return (
    <div className="rounded-lg bg-zinc-100 border border-zinc-200 shrink-0 flex items-center justify-center" style={{ width: size, height: size }}>
      <Disc3 size={Math.round(size * 0.4)} className="text-zinc-300" />
    </div>
  );
  return (
    <img src={url} alt="" width={size} height={size} onError={() => setFailed(true)}
      className="rounded-lg object-cover bg-zinc-100 shrink-0" style={{ width: size, height: size }} />
  );
}

function StockBadge({ items }) {
  // Para nou (stock agregado) cuenta unidades, no líneas: una sola fila
  // puede representar varias copias físicas.
  const disp = items.reduce((sum, i) => {
    if (i.condicion === 'nou') return sum + (i.status === 'disponible' ? Math.max(0, i.cantidad - i.cantidad_reservada) : 0);
    return sum + (i.status === 'disponible' ? 1 : 0);
  }, 0);
  const total = items.reduce((sum, i) => sum + (i.condicion === 'nou' ? i.cantidad : 1), 0);
  const cls = disp === 0 ? 'bg-red-100 text-red-700' : disp <= 2 ? 'bg-yellow-100 text-yellow-700' : 'bg-green-100 text-green-700';
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${cls}`}>
      {disp}/{total}
    </span>
  );
}

function StatCard({ label, value, color }) {
  const colors = {
    emerald: 'bg-emerald-50 border-emerald-200 text-emerald-700',
    amber:   'bg-amber-50 border-amber-200 text-amber-700',
    zinc:    'bg-zinc-50 border-zinc-200 text-zinc-600',
    blue:    'bg-blue-50 border-blue-200 text-blue-700',
    violet:  'bg-violet-50 border-violet-200 text-violet-700',
    rose:    'bg-rose-50 border-rose-200 text-rose-600',
  };
  return (
    <div className={`rounded-xl border p-3 ${colors[color] || colors.zinc}`}>
      <p className="text-xl font-bold">{value ?? '—'}</p>
      <p className="text-xs mt-0.5 opacity-70">{label}</p>
    </div>
  );
}

// ---- Main component --------------------------------------------------------

export default function CatalogoPage() {
  const t = useT();
  const [tab, setTab] = useState('llistat');
  const [releases, setReleases] = useState([]);
  const [page, setPage] = useState(0);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState('');
  const [modal, setModal] = useState(null);
  const [expanded, setExpanded] = useState(null);
  const [stats, setStats] = useState(null);
  const [bulkSyncing, setBulkSyncing] = useState(false);
  const [bulkMsg, setBulkMsg] = useState('');
  const [exporting, setExporting] = useState(false);
  const [showImport, setShowImport] = useState(false);

  const loadReleases = useCallback(async () => {
    setLoading(true);
    try {
      const r = await authFetch(`/admin/releases?limit=${CATALOG_FETCH_LIMIT}`);
      if (r.ok) {
        const data = await r.json();
        setReleases(Array.isArray(data.releases) ? data.releases : []);
      }
    } catch { /* auth error handled by AdminShell */ }
    setLoading(false);
  }, []);

  const searched = useMemo(() => {
    if (!q.trim()) return releases;
    const ql = q.trim().toLowerCase();
    return releases.filter(r =>
      r.artista?.toLowerCase().includes(ql) ||
      r.titulo?.toLowerCase().includes(ql) ||
      r.sello?.toLowerCase().includes(ql) ||
      r.ean?.toLowerCase().includes(ql)
    );
  }, [releases, q]);

  const columns = useMemo(() => ({
    artista: { sortValue: r => `${r.artista ?? ''} ${r.titulo ?? ''}`.toLowerCase() },
    sello: { sortValue: r => (r.sello ?? '').toLowerCase(), filterValue: r => r.sello },
    formato: { sortValue: r => (r.formato ?? '').toLowerCase(), filterValue: r => r.formato },
    anio: { sortValue: r => r.anio ?? null, filterValue: r => r.anio != null ? String(r.anio) : null },
    ean: { sortValue: r => r.ean ?? '' },
  }), []);

  const { rows: sortedFiltered, sort, toggleSort, filters, setFilter, distinctValues } = useSortFilter(searched, columns);

  function handleSort(key) {
    toggleSort(key);
    setPage(0);
  }

  function handleFilterChange(key, selected) {
    setFilter(key, selected);
    setPage(0);
  }

  const total = sortedFiltered.length;
  const offset = page * LIMIT;
  const pageRows = sortedFiltered.slice(offset, offset + LIMIT);

  const loadStats = useCallback(async () => {
    try {
      const r = await authFetch('/admin/discogs/sync/stats');
      if (r.ok) setStats(await r.json());
    } catch { /* non-critical */ }
  }, []);

  useEffect(() => { loadStats(); }, [loadStats]);

  function handleSearch(val) {
    setQ(val);
    setPage(0);
  }

  useEffect(() => { loadReleases(); }, [loadReleases]);

  function handlePage(dir) {
    setPage(p => Math.max(0, p + dir));
  }

  async function deleteRelease(r) {
    if (!confirm(`Eliminar "${r.artista} - ${r.titulo}"? Aquesta acció no es pot desfer.`)) return;
    const resp = await authFetch(`/admin/releases/${r.id}`, { method: 'DELETE' });
    if (!resp.ok) {
      const body = await resp.json().catch(() => ({}));
      alert(body.detail || 'No s\'ha pogut eliminar.');
      return;
    }
    loadReleases();
    loadStats();
  }

  async function handleBulkImages() {
    setBulkSyncing(true);
    setBulkMsg('');
    const res = await authFetch('/admin/discogs/sync/images/start', { method: 'POST' });
    if (res.ok) {
      const data = await res.json();
      setBulkMsg(data.message);
      setTimeout(() => { loadStats(); setBulkMsg(''); }, 5000);
    }
    setBulkSyncing(false);
  }

  function refresh() {
    loadReleases();
    loadStats();
  }

  function veureAlLlistat(releaseId, artista, titulo) {
    const search = `${artista} ${titulo}`;
    setTab('llistat');
    setQ(search);
    setPage(0);
    setExpanded(releaseId);
  }

  async function handleExport() {
    setExporting(true);
    try {
      const r = await authFetch('/admin/catalog/export.csv');
      if (!r.ok) { alert('No s\'ha pogut exportar.'); return; }
      const blob = await r.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'catalog.csv';
      a.click();
      URL.revokeObjectURL(url);
    } finally {
      setExporting(false);
    }
  }

  return (
    <div className="space-y-5 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h2 className="text-2xl font-bold text-zinc-900">{t('catalog.title')}</h2>
        {tab === 'llistat' && (
        <div className="flex items-center gap-2">
          <button onClick={handleExport} disabled={exporting}
            className="flex items-center gap-1.5 text-sm border border-zinc-200 text-zinc-600 hover:bg-zinc-50 px-3 py-2 rounded-lg transition-colors disabled:opacity-60">
            {exporting ? <Loader2 size={13} className="animate-spin" /> : <Download size={13} />}
            Exportar CSV
          </button>
          <button onClick={() => setShowImport(true)}
            className="flex items-center gap-1.5 text-sm border border-zinc-200 text-zinc-600 hover:bg-zinc-50 px-3 py-2 rounded-lg transition-colors">
            <FileSpreadsheet size={13} /> Importar canvis
          </button>
          <button onClick={handleBulkImages} disabled={bulkSyncing}
            className="flex items-center gap-1.5 text-sm border border-violet-200 text-violet-700 bg-violet-50 hover:bg-violet-100 px-3 py-2 rounded-lg transition-colors disabled:opacity-60">
            {bulkSyncing ? <Loader2 size={13} className="animate-spin" /> : <Image size={13} />}
            Sync Discogs
          </button>
          <button onClick={refresh}
            className="flex items-center gap-1.5 text-sm text-zinc-600 border border-zinc-200 px-3 py-2 rounded-lg hover:bg-zinc-50 transition-colors">
            <RefreshCw size={13} /> Actualitzar
          </button>
          <Button onClick={() => setModal({ mode: 'create', release: null })}>
            <Plus size={16} /> {t('catalog.new_disc')}
          </Button>
        </div>
        )}
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-zinc-100 p-1 rounded-xl w-fit">
        {[['llistat', 'Llistat'], ['dashboards', 'Dashboards']].map(([key, label]) => (
          <button key={key} onClick={() => setTab(key)}
            className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors ${tab === key ? 'bg-white text-zinc-900 shadow-sm' : 'text-zinc-600 hover:text-zinc-900'}`}>
            {label}
          </button>
        ))}
      </div>

      {tab === 'dashboards' && <AgingDashboard onVeureRelease={veureAlLlistat} />}

      {tab === 'llistat' && (
      <>
      {bulkMsg && (
        <div className="bg-violet-50 border border-violet-200 text-violet-800 text-sm rounded-xl px-4 py-3">
          {bulkMsg} — les estadístiques s&apos;actualitzen en uns minuts.
        </div>
      )}

      {/* Stats */}
      <div className="grid grid-cols-3 md:grid-cols-4 lg:grid-cols-8 gap-2">
        <StatCard label="Items actius"      value={stats?.total_actius}     color="blue" />
        <StatCard label="A Discogs"         value={stats?.listed_discogs}   color="emerald" />
        <StatCard label="Pendents"          value={stats?.pot_listar}       color="amber" />
        <StatCard label="Sense Release ID"  value={stats?.sense_release_id} color="zinc" />
        <StatCard label="Amb caràtula"      value={stats?.amb_caratula}     color="violet" />
        <StatCard label="Sense caràtula"    value={stats?.sense_caratula}   color="rose" />
        <StatCard label="Sense gènere"      value={stats?.sense_genere}     color="rose" />
        <StatCard label="Sense EAN"         value={stats?.sense_ean}        color="rose" />
        <StatCard label="Sense format"      value={stats?.sense_format}     color="rose" />
      </div>

      {/* Search */}
      <div className="relative">
        <Search size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-zinc-400" />
        <input
          value={q}
          onChange={e => handleSearch(e.target.value)}
          placeholder={t('catalog.search_ph')}
          className="w-full pl-10 pr-4 py-2.5 border border-zinc-300 rounded-xl text-sm bg-white focus:outline-none focus:ring-2 focus:ring-zinc-900 shadow-sm"
        />
      </div>

      {/* Table */}
      <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm overflow-hidden">
        {loading ? (
          <div className="p-12 text-center text-zinc-400 text-sm flex items-center justify-center gap-2">
            <Loader2 size={16} className="animate-spin" /> Carregant...
          </div>
        ) : sortedFiltered.length === 0 ? (
          <div className="p-12 text-center text-zinc-400 text-sm">{t('catalog.no_results')}</div>
        ) : (
          <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-zinc-50 text-xs text-zinc-500 border-b border-zinc-200">
              <tr>
                <th className="w-8 px-4 py-3" />
                <SortableTh label={t('catalog.col.artist')} sortKey="artista" sort={sort} onSort={handleSort} />
                <SortableTh label={t('catalog.col.label')} sortKey="sello" sort={sort} onSort={handleSort}
                  filterOptions={distinctValues.sello} selected={filters.sello} onFilterChange={handleFilterChange}
                  className="hidden md:table-cell" />
                <SortableTh label={t('catalog.col.format')} sortKey="formato" sort={sort} onSort={handleSort}
                  filterOptions={distinctValues.formato} selected={filters.formato} onFilterChange={handleFilterChange}
                  className="hidden md:table-cell" />
                <SortableTh label={t('catalog.col.year')} sortKey="anio" sort={sort} onSort={handleSort}
                  filterOptions={distinctValues.anio} selected={filters.anio} onFilterChange={handleFilterChange}
                  className="hidden lg:table-cell" />
                <SortableTh label={t('catalog.col.ean', 'EAN')} sortKey="ean" sort={sort} onSort={handleSort}
                  className="hidden lg:table-cell" />
                <th className="px-4 py-3 text-center font-medium">{t('catalog.col.stock')}</th>
                <th className="px-4 py-3 text-left font-medium hidden lg:table-cell">Discogs</th>
                <th className="px-4 py-3 text-right font-medium">{t('catalog.col.actions', 'Accions')}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-100">
              {pageRows.map(r => (
                <>
                  <tr key={r.id}
                    onClick={() => setExpanded(expanded === r.id ? null : r.id)}
                    className="hover:bg-zinc-50 cursor-pointer transition-colors">
                    <td className="px-4 py-3 text-zinc-400">
                      {expanded === r.id ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-3">
                        <CoverImg url={r.imagen_url} size={36} />
                        <div>
                          <div className="font-semibold text-zinc-900 flex items-center gap-1.5">
                            {r.artista}
                            {r.properament && (
                              <span className="inline-flex items-center gap-0.5 text-[10px] font-semibold text-violet-700 bg-violet-50 border border-violet-200 px-1.5 py-0.5 rounded-full">
                                <Clock size={8} /> Properament
                              </span>
                            )}
                            {r.esta_sonant && (
                              <span className="inline-flex items-center gap-0.5 text-[10px] font-semibold text-zinc-900 bg-zinc-100 border border-zinc-300 px-1.5 py-0.5 rounded-full">
                                <Music2 size={8} /> Sonant
                              </span>
                            )}
                          </div>
                          <div className="text-zinc-500 text-xs">{r.titulo}</div>
                          {r.etiquetes?.length > 0 && (
                            <div className="flex gap-1 mt-1 flex-wrap">
                              {r.etiquetes.map(e => (
                                <span key={e.id}
                                  className="inline-flex items-center rounded-full px-1.5 py-0.5 text-[10px] font-semibold text-white"
                                  style={{ backgroundColor: e.color || '#94a3b8' }}>
                                  {e.nom_ca}
                                </span>
                              ))}
                            </div>
                          )}
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-zinc-500 hidden md:table-cell">{r.sello ?? '—'}</td>
                    <td className="px-4 py-3 text-zinc-500 hidden md:table-cell">{r.formato ?? '—'}</td>
                    <td className="px-4 py-3 text-zinc-500 hidden lg:table-cell">{r.anio ?? '—'}</td>
                    <td className="px-4 py-3 text-zinc-500 hidden lg:table-cell font-mono text-xs">{r.ean ?? '—'}</td>
                    <td className="px-4 py-3 text-center">
                      <StockBadge items={r.items ?? []} />
                    </td>
                    <td className="px-4 py-3 hidden lg:table-cell">
                      <ReleaseSyncSummary items={r.items ?? []} discogs_release_id={r.discogs_release_id} />
                    </td>
                    <td className="px-4 py-3 text-right" onClick={e => e.stopPropagation()}>
                      <div className="flex items-center justify-end gap-1">
                        <button onClick={() => setModal({ mode: 'edit', release: r })} title="Editar"
                          className="p-1.5 text-zinc-400 hover:text-zinc-700 rounded-lg hover:bg-zinc-100 transition-colors">
                          <Pencil size={14} />
                        </button>
                        <button onClick={() => setModal({ mode: 'duplicate', release: r })} title="Duplicar"
                          className="p-1.5 text-zinc-400 hover:text-zinc-700 rounded-lg hover:bg-zinc-100 transition-colors">
                          <Copy size={14} />
                        </button>
                        <button onClick={() => deleteRelease(r)} title="Eliminar"
                          className="p-1.5 text-zinc-300 hover:text-red-500 rounded-lg hover:bg-red-50 transition-colors">
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </td>
                  </tr>
                  {expanded === r.id && (
                    <tr key={`${r.id}-exp`}>
                      <td colSpan={9} className="px-4 py-3 bg-amber-50/60 border-b border-amber-100">
                        <ExpandedPanel
                          release={r}
                          onRefresh={() => { loadReleases(); loadStats(); }}
                        />
                      </td>
                    </tr>
                  )}
                </>
              ))}
            </tbody>
          </table>
          </div>
        )}

        {/* Pagination */}
        {total > LIMIT && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-zinc-100 text-xs text-zinc-500">
            <span>{offset + 1}–{Math.min(offset + LIMIT, total)} de {total}</span>
            <div className="flex gap-2">
              <button onClick={() => handlePage(-1)} disabled={offset === 0}
                className="px-3 py-1.5 border border-zinc-200 rounded-lg hover:bg-zinc-50 disabled:opacity-40 transition-colors">
                ← Anterior
              </button>
              <button onClick={() => handlePage(1)} disabled={offset + LIMIT >= total}
                className="px-3 py-1.5 border border-zinc-200 rounded-lg hover:bg-zinc-50 disabled:opacity-40 transition-colors">
                Següent →
              </button>
            </div>
          </div>
        )}
      </div>
      </>
      )}

      {modal && (
        <DiscModal
          mode={modal.mode}
          release={modal.release}
          onClose={() => setModal(null)}
          onSaved={() => { setModal(null); loadReleases(); loadStats(); }}
        />
      )}

      {showImport && (
        <ImportCsvModal
          onClose={() => setShowImport(false)}
          onDone={() => { setShowImport(false); refresh(); }}
        />
      )}
    </div>
  );
}

// ---- AgingDashboard: antiguitat de l'estoc (rotació) -----------------------

const AGING_BUCKET_COLOR = {
  '0_30': 'bg-emerald-500', '31_90': 'bg-lime-500', '91_180': 'bg-amber-500',
  '181_365': 'bg-orange-500', '366_730': 'bg-red-500', '730_plus': 'bg-red-700',
  sin_fecha: 'bg-zinc-400',
};

const ORIGEN_LABEL = { compra: 'Compra', discogs: 'Discogs (llegat)', desconegut: 'Desconegut' };
const ORIGEN_COLOR = {
  compra: 'bg-blue-50 text-blue-700 border-blue-200',
  discogs: 'bg-violet-50 text-violet-700 border-violet-200',
  desconegut: 'bg-zinc-50 text-zinc-500 border-zinc-200',
};

const AGING_ITEMS_LIMIT = 20;

function AgingDashboard({ onVeureRelease }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [bucket, setBucket] = useState(null);
  const [items, setItems] = useState([]);
  const [itemsTotal, setItemsTotal] = useState(0);
  const [itemsOffset, setItemsOffset] = useState(0);
  const [itemsLoading, setItemsLoading] = useState(true);

  const loadSummary = useCallback(async () => {
    setLoading(true);
    try {
      const r = await authFetch('/admin/catalog/aging');
      if (r.ok) setData(await r.json());
    } catch { /* non-critical */ }
    setLoading(false);
  }, []);

  const loadItems = useCallback(async (bucketKey, offset) => {
    setItemsLoading(true);
    try {
      const params = new URLSearchParams({ limit: AGING_ITEMS_LIMIT, offset });
      if (bucketKey) params.set('bucket', bucketKey);
      const r = await authFetch(`/admin/catalog/aging/items?${params}`);
      if (r.ok) {
        const body = await r.json();
        setItems(body.items);
        setItemsTotal(body.total);
      }
    } catch { /* non-critical */ }
    setItemsLoading(false);
  }, []);

  useEffect(() => { loadSummary(); }, [loadSummary]);
  useEffect(() => { loadItems(bucket, itemsOffset); }, [loadItems, bucket, itemsOffset]);

  function selectBucket(key) {
    setBucket(prev => (prev === key ? null : key));
    setItemsOffset(0);
  }

  function refresh() {
    loadSummary();
    loadItems(bucket, itemsOffset);
  }

  if (loading) {
    return (
      <div className="p-12 text-center text-zinc-400 text-sm flex items-center justify-center gap-2">
        <Loader2 size={16} className="animate-spin" /> Carregant...
      </div>
    );
  }
  if (!data) {
    return <div className="p-12 text-center text-zinc-400 text-sm">No s&apos;han pogut carregar les dades.</div>;
  }

  const maxCount = Math.max(1, ...data.buckets.map(b => b.count));
  const bucketLabel = bucket ? data.buckets.find(b => b.key === bucket)?.label : null;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-zinc-500 max-w-2xl">
          Antiguitat de l&apos;estoc disponible des de la data d&apos;entrada al magatzem
          (recepció de compra, o &quot;posted&quot; de Discogs per a l&apos;estoc anterior a l&apos;app).
        </p>
        <button onClick={refresh}
          className="flex items-center gap-1.5 text-sm text-zinc-600 border border-zinc-200 px-3 py-2 rounded-lg hover:bg-zinc-50 transition-colors shrink-0">
          <RefreshCw size={13} /> Actualitzar
        </button>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <StatCard label="Còpies disponibles" value={data.total_disponible} color="blue" />
        <StatCard label="Valor en estoc (venda)" value={fmtEur(data.valor_total)} color="emerald" />
        <StatCard label="Cost adquisició" value={fmtEur(data.coste_total)} color="amber" />
        <StatCard label="Antiguitat mitjana" value={data.edad_media_dias != null ? `${data.edad_media_dias} dies` : '—'} color="violet" />
        <StatCard label="Sense data d'entrada" value={data.sin_fecha} color={data.sin_fecha > 0 ? 'rose' : 'zinc'} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-1 bg-white rounded-2xl border border-zinc-200 shadow-sm p-5">
          <div className="flex items-center justify-between mb-3">
            <div className="text-sm font-semibold text-zinc-700">Distribució per antiguitat</div>
            {bucket && (
              <button onClick={() => selectBucket(bucket)} className="text-xs text-zinc-400 hover:text-zinc-700">
                Veure tots
              </button>
            )}
          </div>
          <div className="space-y-2.5">
            {data.buckets.map(b => {
              const pct = maxCount > 0 ? (b.count / maxCount) * 100 : 0;
              const selected = bucket === b.key;
              return (
                <button key={b.key} onClick={() => selectBucket(b.key)}
                  className={`w-full text-left rounded-lg p-1.5 -m-1.5 transition-colors ${selected ? 'bg-zinc-100' : 'hover:bg-zinc-50'}`}>
                  <div className="flex items-center justify-between text-xs text-zinc-600 mb-1 gap-2">
                    <span className={`font-medium ${selected ? 'text-zinc-900' : ''}`}>{b.label}</span>
                    <span className="text-zinc-400 shrink-0">{b.count} · {fmtEur(b.valor)} venda · {fmtEur(b.coste)} cost</span>
                  </div>
                  <div className="h-1.5 rounded-full bg-zinc-100 overflow-hidden">
                    <div className={`h-full rounded-full ${AGING_BUCKET_COLOR[b.key] ?? 'bg-zinc-400'}`} style={{ width: `${pct}%` }} />
                  </div>
                </button>
              );
            })}
          </div>
          {data.sin_fecha > 0 && (
            <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 mt-3">
              {data.sin_fecha} còpia{data.sin_fecha === 1 ? '' : 's'} sense data d&apos;entrada fiable — normalment
              per manca del &quot;posted&quot; de Discogs; no compten en la mitjana ni la mediana.
            </p>
          )}
        </div>

        <div className="lg:col-span-2 bg-white rounded-2xl border border-zinc-200 shadow-sm overflow-hidden">
          <div className="px-5 py-3 border-b border-zinc-200">
            <div className="text-sm font-semibold text-zinc-700">
              {bucketLabel ? `Discs a "${bucketLabel}"` : 'Discs amb més antiguitat (tots els grups)'}
            </div>
          </div>
          {itemsLoading ? (
            <div className="p-8 text-center text-zinc-400 text-sm flex items-center justify-center gap-2">
              <Loader2 size={14} className="animate-spin" /> Carregant...
            </div>
          ) : items.length === 0 ? (
            <div className="p-5 text-sm text-zinc-400">Cap còpia en aquest grup.</div>
          ) : (
            <>
              <div className="divide-y divide-zinc-100 max-h-[22rem] overflow-y-auto">
                {items.map(it => (
                  <div key={it.item_id} className="flex items-center gap-3 px-5 py-2.5">
                    <CoverImg url={it.imagen_url} size={32} />
                    <div className="min-w-0 flex-1">
                      <div className="text-sm font-medium text-zinc-900 truncate">{it.artista} — {it.titulo}</div>
                      <div className="flex items-center gap-2 flex-wrap mt-0.5">
                        <span className="text-xs text-zinc-400">
                          {it.fecha_entrada ? `des de ${new Date(it.fecha_entrada).toLocaleDateString('ca-ES')}` : 'sense data'}
                        </span>
                        <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-medium border ${ORIGEN_COLOR[it.origen]}`}>
                          {ORIGEN_LABEL[it.origen]}
                        </span>
                      </div>
                    </div>
                    <div className="text-right shrink-0">
                      <div className="text-sm font-semibold text-zinc-900">{it.dias != null ? `${it.dias} dies` : '—'}</div>
                      <div className="text-xs text-zinc-400">
                        {fmtEur(it.precio)} venda{it.coste != null ? ` · ${fmtEur(it.coste)} cost` : ''}
                      </div>
                    </div>
                    <button onClick={() => onVeureRelease(it.release_id, it.artista, it.titulo)} title="Veure al llistat"
                      className="p-1.5 text-zinc-400 hover:text-zinc-700 rounded-lg hover:bg-zinc-100 transition-colors shrink-0">
                      <Eye size={14} />
                    </button>
                  </div>
                ))}
              </div>
              {itemsTotal > AGING_ITEMS_LIMIT && (
                <div className="flex items-center justify-between px-4 py-3 border-t border-zinc-100 text-xs text-zinc-500">
                  <span>{itemsOffset + 1}–{Math.min(itemsOffset + AGING_ITEMS_LIMIT, itemsTotal)} de {itemsTotal}</span>
                  <div className="flex gap-2">
                    <button onClick={() => setItemsOffset(o => Math.max(0, o - AGING_ITEMS_LIMIT))} disabled={itemsOffset === 0}
                      className="px-3 py-1.5 border border-zinc-200 rounded-lg hover:bg-zinc-50 disabled:opacity-40 transition-colors">
                      ← Anterior
                    </button>
                    <button onClick={() => setItemsOffset(o => o + AGING_ITEMS_LIMIT)} disabled={itemsOffset + AGING_ITEMS_LIMIT >= itemsTotal}
                      className="px-3 py-1.5 border border-zinc-200 rounded-lg hover:bg-zinc-50 disabled:opacity-40 transition-colors">
                      Següent →
                    </button>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

// ---- ImportCsvModal ---------------------------------------------------------

function ImportCsvModal({ onClose, onDone }) {
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');

  async function handleUpload(e) {
    e.preventDefault();
    if (!file) return;
    setUploading(true);
    setError('');
    try {
      const formData = new FormData();
      formData.append('file', file);
      const r = await authFetch('/admin/catalog/import', { method: 'POST', body: formData });
      if (!r.ok) {
        const body = await r.json().catch(() => ({}));
        setError(body.detail || 'No s\'ha pogut importar el fitxer.');
        return;
      }
      setResult(await r.json());
    } finally {
      setUploading(false);
    }
  }

  return (
    <Modal title="Importar canvis del catàleg" onClose={onClose}>
      <p className="text-sm text-zinc-500">
        Puja el CSV exportat (amb canvis de preu, condició, grading, segell, format,
        any o gènere, o amb la columna <strong>eliminar</strong> marcada amb una X
        per donar de baixa una còpia).
      </p>

      {!result ? (
        <form onSubmit={handleUpload} className="space-y-4">
          <input type="file" accept=".csv" required
            onChange={e => setFile(e.target.files?.[0] ?? null)}
            className="block w-full text-sm border border-zinc-300 rounded-lg px-3 py-2 file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:bg-zinc-100 file:text-zinc-700 file:text-sm" />
          {error && <p className="text-red-500 text-sm">{error}</p>}
          <div className="flex justify-end gap-3">
            <Button type="button" variant="secondary" onClick={onClose}>Cancel·lar</Button>
            <Button type="submit" disabled={!file || uploading}>{uploading ? 'Important...' : 'Importar'}</Button>
          </div>
        </form>
      ) : (
        <div className="space-y-4">
          <div className="grid grid-cols-3 gap-2">
            <StatCard label="Actualitzats" value={result.actualitzats} color="emerald" />
            <StatCard label="Eliminats" value={result.eliminats} color="rose" />
            <StatCard label="Sense canvis" value={result.sense_canvis} color="zinc" />
          </div>
          {result.errors?.length > 0 && (
            <div className="border border-amber-200 bg-amber-50 rounded-xl p-3 max-h-48 overflow-y-auto">
              <div className="text-xs font-semibold text-amber-800 mb-1">{result.errors.length} fila(es) amb problemes:</div>
              <ul className="space-y-0.5 text-xs text-amber-700">
                {result.errors.map((e, i) => (
                  <li key={i}>Fila {e.fila}{e.item_id ? ` (${e.item_id})` : ''}: {e.motiu}</li>
                ))}
              </ul>
            </div>
          )}
          <div className="flex justify-end">
            <Button onClick={onDone}>Tancar</Button>
          </div>
        </div>
      )}
    </Modal>
  );
}

// ---- ExpandedPanel (tabs: Còpies | Galeria & Etiquetes) --------------------

function ExpandedPanel({ release, onRefresh }) {
  const [tab, setTab] = useState('copies');
  return (
    <div className="space-y-3">
      <div className="flex gap-1 border-b border-amber-200/60 pb-0">
        {[{ id: 'copies', label: 'Còpies' }, { id: 'gallery', label: 'Galeria & Etiquetes' }].map(({ id, label }) => (
          <button key={id} onClick={() => setTab(id)}
            className={`px-3 py-1.5 text-xs font-semibold rounded-t-lg transition-colors ${tab === id ? 'bg-white border border-b-white border-amber-200/60 text-amber-700' : 'text-zinc-500 hover:text-zinc-700'}`}>
            {label}
          </button>
        ))}
      </div>
      {tab === 'copies' ? (
        <CopiesPanel release={release} items={release.items ?? []} onRefresh={onRefresh} />
      ) : (
        <GalleryEtiquetesPanel release={release} onRefresh={onRefresh} />
      )}
    </div>
  );
}

// ---- GalleryEtiquetesPanel -------------------------------------------------

function GalleryEtiquetesPanel({ release, onRefresh }) {
  const [images, setImages] = useState(release.images ?? []);
  const [etiquetes, setEtiquetes] = useState(release.etiquetes ?? []);
  const [allEtiquetes, setAllEtiquetes] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [savingEt, setSavingEt] = useState(false);
  const [estaSonant, setEstaSonant] = useState(release.esta_sonant ?? false);
  const [savingFlag, setSavingFlag] = useState(false);
  const fileRef = useRef(null);

  useEffect(() => {
    authFetch('/admin/etiquetes').then(r => r.ok ? r.json() : []).then(setAllEtiquetes).catch(() => {});
  }, []);

  async function handleToggleEstaSonant(e) {
    const val = e.target.checked;
    setEstaSonant(val);
    setSavingFlag(true);
    try {
      const res = await authFetch(`/admin/releases/${release.id}/esta-sonant?esta_sonant=${val}`, { method: 'PATCH' });
      if (!res.ok) {
        setEstaSonant(!val);
        const body = await res.json().catch(() => ({}));
        alert(body.detail || 'No s\'ha pogut actualitzar "Està sonant".');
        return;
      }
    } catch {
      setEstaSonant(!val);
      alert('Error de connexió en actualitzar "Està sonant".');
      return;
    } finally {
      setSavingFlag(false);
    }
    onRefresh();
  }

  async function handleToggleRecomanat(e) {
    const checked = e.target.checked;
    const recomanatTag = allEtiquetes.find(et => et.slug === 'recomanat');
    if (!recomanatTag) return;
    const prev = etiquetes;
    const next = checked
      ? [...etiquetes.filter(x => x.id !== recomanatTag.id), recomanatTag]
      : etiquetes.filter(x => x.id !== recomanatTag.id);
    setEtiquetes(next);
    setSavingFlag(true);
    try {
      const res = await authFetch(`/admin/releases/${release.id}/etiquetes`, {
        method: 'PUT',
        body: JSON.stringify({ etiqueta_ids: next.map(x => x.id) }),
      });
      if (!res.ok) {
        setEtiquetes(prev);
        const body = await res.json().catch(() => ({}));
        alert(body.detail || 'No s\'ha pogut actualitzar "Recomanats".');
        return;
      }
    } catch {
      setEtiquetes(prev);
      alert('Error de connexió en actualitzar "Recomanats".');
      return;
    } finally {
      setSavingFlag(false);
    }
    onRefresh();
  }

  async function handleUpload(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    const fd = new FormData();
    fd.append('file', file);
    const res = await authFetch(`/admin/releases/${release.id}/images`, { method: 'POST', body: fd });
    if (res.ok) {
      const img = await res.json();
      setImages(prev => [...prev, img]);
      onRefresh();
    } else {
      const err = await res.json().catch(() => ({}));
      alert(err.detail || 'No s\'ha pogut pujar la imatge.');
    }
    setUploading(false);
    e.target.value = '';
  }

  async function deleteImage(imgId) {
    if (!confirm('Eliminar aquesta imatge?')) return;
    const res = await authFetch(`/admin/releases/${release.id}/images/${imgId}`, { method: 'DELETE' });
    if (res.ok) {
      setImages(prev => prev.filter(i => i.id !== imgId));
      onRefresh();
    }
  }

  function toggleEtiqueta(id) {
    setEtiquetes(prev => prev.some(e => e.id === id)
      ? prev.filter(e => e.id !== id)
      : [...prev, allEtiquetes.find(e => e.id === id)]);
  }

  async function saveEtiquetes() {
    setSavingEt(true);
    await authFetch(`/admin/releases/${release.id}/etiquetes`, {
      method: 'PUT',
      body: JSON.stringify({ etiqueta_ids: etiquetes.map(e => e.id) }),
    });
    setSavingEt(false);
    onRefresh();
  }

  const isRecomanat = etiquetes.some(e => e.slug === 'recomanat');

  return (
    <div className="space-y-6">
      {/* Aparició a la portada */}
      <div className="border-b border-zinc-100 pb-4">
        <div className="text-xs font-semibold text-zinc-500 uppercase tracking-wide mb-3">
          Aparició a la portada {savingFlag && <span className="normal-case font-normal text-zinc-400">· desant...</span>}
        </div>
        <div className="flex flex-wrap gap-6">
          <label className="flex items-center gap-2 cursor-pointer select-none">
            <input type="checkbox" checked={estaSonant} onChange={handleToggleEstaSonant}
              className="w-4 h-4 rounded border-zinc-300 text-zinc-900 focus:ring-zinc-900" />
            <span className="text-sm text-zinc-700">Està sonant <span className="text-zinc-400">(targeta del hero, només un disc alhora)</span></span>
          </label>
          <label className="flex items-center gap-2 cursor-pointer select-none">
            <input type="checkbox" checked={isRecomanat} onChange={handleToggleRecomanat}
              className="w-4 h-4 rounded border-zinc-300 text-zinc-900 focus:ring-zinc-900" />
            <span className="text-sm text-zinc-700">Recomanats <span className="text-zinc-400">(Selecció del curador)</span></span>
          </label>
        </div>
      </div>

    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
      {/* Galeria */}
      <div>
        <div className="text-xs font-semibold text-zinc-500 uppercase tracking-wide mb-2">
          Galeria d&apos;imatges ({images.length})
        </div>
        <div className="flex flex-wrap gap-2 mb-3">
          {images.map(img => (
            <div key={img.id} className="relative group">
              <img src={img.url} alt="" className="w-16 h-16 object-cover rounded-lg border border-zinc-200 bg-zinc-100" />
              <button onClick={() => deleteImage(img.id)}
                className="absolute -top-1.5 -right-1.5 w-5 h-5 bg-red-500 text-white rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
                <X size={10} />
              </button>
              {img.font && (
                <span className="absolute bottom-0.5 left-0.5 text-[8px] bg-black/50 text-white rounded px-1">{img.font}</span>
              )}
            </div>
          ))}
          {images.length === 0 && <p className="text-sm text-zinc-400">Cap imatge.</p>}
        </div>
        <input ref={fileRef} type="file" accept="image/*" onChange={handleUpload} className="hidden" />
        <button onClick={() => fileRef.current?.click()} disabled={uploading}
          className="flex items-center gap-1.5 text-xs text-violet-700 border border-violet-200 bg-violet-50 hover:bg-violet-100 px-3 py-1.5 rounded-lg transition-colors disabled:opacity-60">
          {uploading ? <Loader2 size={11} className="animate-spin" /> : <Upload size={11} />}
          Pujar imatge
        </button>
      </div>

      {/* Etiquetes */}
      <div>
        <div className="text-xs font-semibold text-zinc-500 uppercase tracking-wide mb-2">Etiquetes</div>
        <div className="flex flex-wrap gap-2 mb-3">
          {allEtiquetes.filter(et => et.slug !== 'recomanat').map(et => {
            const active = etiquetes.some(e => e.id === et.id);
            return (
              <button key={et.id} type="button" onClick={() => toggleEtiqueta(et.id)}
                className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold border transition-all ${active ? 'text-white border-transparent' : 'text-zinc-600 bg-white border-zinc-300 hover:border-zinc-400'}`}
                style={active ? { backgroundColor: et.color || '#94a3b8', borderColor: et.color || '#94a3b8' } : {}}>
                {et.nom_ca}
              </button>
            );
          })}
        </div>
        <button onClick={saveEtiquetes} disabled={savingEt}
          className="text-xs font-medium bg-primary hover:bg-zinc-800 text-white px-3 py-1.5 rounded-lg transition-colors disabled:opacity-60">
          {savingEt ? 'Desant...' : 'Desar etiquetes'}
        </button>
      </div>
    </div>
    </div>
  );
}

// ---- CopiesPanel -----------------------------------------------------------

const condicionColor = { nou: 'bg-blue-100 text-blue-700', segona_ma: 'bg-zinc-100 text-zinc-600' };
const statusColor = {
  disponible: 'bg-green-100 text-green-700',
  reservado:  'bg-yellow-100 text-yellow-700',
  vendido:    'bg-blue-100 text-blue-700',
  retirado:   'bg-zinc-100 text-zinc-500',
};
const statusKey = {
  disponible: 'status.available',
  reservado:  'status.reserved',
  vendido:    'status.sold',
  retirado:   'status.retired',
};

function CopiesPanel({ release, items, onRefresh }) {
  const t = useT();
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ precio: '', condicion: 'segona_ma', estado_disco: '', estado_funda: '', cantidad: '1' });
  const [saving, setSaving] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [editForm, setEditForm] = useState(null);
  const [savingEdit, setSavingEdit] = useState(false);
  const [actionId, setActionId] = useState(null);

  async function save(e) {
    e.preventDefault();
    setSaving(true);
    await authFetch('/admin/items', {
      method: 'POST',
      body: JSON.stringify({
        release_id: release.id,
        precio: parseFloat(form.precio),
        coste_adquisicion: form.coste_adquisicion ? parseFloat(form.coste_adquisicion) : null,
        condicion: form.condicion,
        estado_disco: form.condicion === 'nou' ? null : (form.estado_disco || null),
        estado_funda: form.condicion === 'nou' ? null : (form.estado_funda || null),
        cantidad: form.condicion === 'nou' ? (parseInt(form.cantidad, 10) || 1) : 1,
      }),
    });
    setSaving(false);
    setForm({ precio: '', coste_adquisicion: '', condicion: 'segona_ma', estado_disco: '', estado_funda: '', cantidad: '1' });
    setShowForm(false);
    onRefresh();
  }

  function startEdit(item) {
    setEditingId(item.id);
    setEditForm({
      precio: String(item.precio),
      coste_adquisicion: item.coste_adquisicion != null ? String(item.coste_adquisicion) : '',
      condicion: item.condicion,
      estado_disco: item.estado_disco || '',
      estado_funda: item.estado_funda || '',
    });
  }

  async function saveEdit(e) {
    e.preventDefault();
    setSavingEdit(true);
    const resp = await authFetch(`/admin/items/${editingId}`, {
      method: 'PUT',
      body: JSON.stringify({
        precio: parseFloat(editForm.precio),
        coste_adquisicion: editForm.coste_adquisicion ? parseFloat(editForm.coste_adquisicion) : null,
        condicion: editForm.condicion,
        estado_disco: editForm.condicion === 'nou' ? null : (editForm.estado_disco || null),
        estado_funda: editForm.condicion === 'nou' ? null : (editForm.estado_funda || null),
      }),
    });
    setSavingEdit(false);
    if (!resp.ok) {
      const body = await resp.json().catch(() => ({}));
      alert(body.detail || 'No s\'ha pogut actualitzar.');
      return;
    }
    setEditingId(null);
    onRefresh();
  }

  async function deleteItem(item) {
    if (!confirm('Eliminar aquesta còpia? Aquesta acció no es pot desfer.')) return;
    const resp = await authFetch(`/admin/items/${item.id}`, { method: 'DELETE' });
    if (!resp.ok) {
      const body = await resp.json().catch(() => ({}));
      alert(body.detail || 'No s\'ha pogut eliminar.');
      return;
    }
    onRefresh();
  }

  async function handlePush(item) {
    setActionId(item.id + '_push');
    const res = await authFetch(`/admin/discogs/sync/items/${item.id}/push`, { method: 'POST' });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      alert(`Error: ${err.detail || res.status}`);
    }
    setActionId(null);
    onRefresh();
  }

  async function handleRemove(item) {
    if (!confirm('Eliminar aquest listing de Discogs?')) return;
    setActionId(item.id + '_remove');
    const res = await authFetch(`/admin/discogs/sync/items/${item.id}/listing`, { method: 'DELETE' });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      alert(`Error: ${err.detail || res.status}`);
    }
    setActionId(null);
    onRefresh();
  }

  async function handleEnrichImage(item) {
    setActionId(item.id + '_img');
    const res = await authFetch(`/admin/discogs/sync/items/${item.id}/enrich-image`, { method: 'POST' });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      alert(`Error: ${err.detail || res.status}`);
    }
    setActionId(null);
    onRefresh();
  }

  return (
    <div className="space-y-2">
      <div className="text-xs font-semibold text-zinc-500 uppercase tracking-wide">
        Còpies ({items.length})
      </div>
      {items.length === 0 && <div className="text-sm text-zinc-400">Cap còpia.</div>}
      <div className="space-y-1.5">
        {items.map(item => editingId === item.id ? (
          <form key={item.id} onSubmit={saveEdit} className="flex flex-wrap items-end gap-3 p-3 bg-white rounded-xl border border-amber-200 shadow-sm">
            <Field label={t('common.condition')}>
              <select value={editForm.condicion} onChange={e => setEditForm(f => ({ ...f, condicion: e.target.value }))}
                className="border border-zinc-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900 bg-white">
                <option value="segona_ma">{t('common.condition.used')}</option>
                <option value="nou">{t('common.condition.new')}</option>
              </select>
            </Field>
            <Field label="PVP (€)">
              <input type="number" step="0.01" min="0" required value={editForm.precio}
                onChange={e => setEditForm(f => ({ ...f, precio: e.target.value }))}
                className="w-24 border border-zinc-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
            </Field>
            <Field label="Cost (€)">
              <input type="number" step="0.01" min="0" value={editForm.coste_adquisicion}
                onChange={e => setEditForm(f => ({ ...f, coste_adquisicion: e.target.value }))}
                placeholder="—"
                className="w-24 border border-zinc-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
            </Field>
            {editForm.condicion === 'segona_ma' && <>
              <Field label={t('catalog.disc_grade')}>
                <GradingSelect value={editForm.estado_disco} onChange={v => setEditForm(f => ({ ...f, estado_disco: v }))} />
              </Field>
              <Field label={t('catalog.sleeve_grade')}>
                <GradingSelect value={editForm.estado_funda} onChange={v => setEditForm(f => ({ ...f, estado_funda: v }))} />
              </Field>
            </>}
            <div className="flex gap-2 pb-0.5">
              <Button type="submit" size="sm" disabled={savingEdit}>{savingEdit ? t('common.saving') : t('common.save')}</Button>
              <Button type="button" variant="ghost" size="sm" onClick={() => setEditingId(null)}>{t('common.cancel')}</Button>
            </div>
          </form>
        ) : (
          <div key={item.id} className="flex items-center gap-2 text-sm group flex-wrap">
            <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${statusColor[item.status]}`}>
              {t(statusKey[item.status] ?? item.status)}
            </span>
            <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${condicionColor[item.condicion] ?? condicionColor.segona_ma}`}>
              {item.condicion === 'nou' ? t('common.condition.new') : t('common.condition.used')}
            </span>
            <span className="font-semibold text-zinc-900">{item.precio} €</span>
            {item.condicion === 'nou' && (
              <span className="text-xs text-zinc-500">
                {item.cantidad} unitats
                {item.cantidad_reservada > 0 && ` (${item.cantidad_reservada} reservades)`}
              </span>
            )}
            {item.coste_adquisicion != null && (() => {
              const pvp = parseFloat(item.precio);
              const cost = parseFloat(item.coste_adquisicion);
              const marge = pvp - cost;
              const pct = pvp > 0 ? Math.round((marge / pvp) * 100) : 0;
              return (
                <span className="text-xs text-zinc-400" title={`Cost: ${cost.toFixed(2)} € · Marge: ${marge.toFixed(2)} € (${pct}%)`}>
                  cost {cost.toFixed(2)} € · <span className={marge >= 0 ? 'text-emerald-600' : 'text-red-500'}>{marge >= 0 ? '+' : ''}{marge.toFixed(2)} €</span>
                </span>
              );
            })()}
            {item.estado_disco && <span className="text-zinc-500 text-xs">{item.estado_disco}</span>}
            {item.estado_funda && <span className="text-zinc-400 text-xs">/ {item.estado_funda}</span>}

            {/* Discogs sync */}
            <div className="flex items-center gap-1 ml-1">
              <SyncBadge status={syncStatus(item, release)} codiDiscogs={item.codi_discogs} />
              {syncStatus(item, release) === 'pending' && (
                <button onClick={() => handlePush(item)} disabled={!!actionId} title="Pujar a Discogs"
                  className="flex items-center gap-1 text-xs text-amber-700 bg-amber-50 hover:bg-amber-100 border border-amber-200 px-2 py-0.5 rounded-lg transition-colors disabled:opacity-50">
                  {actionId === item.id + '_push' ? <Loader2 size={9} className="animate-spin" /> : <Upload size={9} />}
                  Pujar
                </button>
              )}
              {syncStatus(item, release) === 'listed' && (
                <button onClick={() => handleRemove(item)} disabled={!!actionId} title="Eliminar listing"
                  className="flex items-center gap-1 text-xs text-zinc-500 hover:text-red-500 border border-zinc-200 hover:border-red-200 px-2 py-0.5 rounded-lg transition-colors disabled:opacity-50">
                  {actionId === item.id + '_remove' ? <Loader2 size={9} className="animate-spin" /> : <Trash2 size={9} />}
                  Treure
                </button>
              )}
              {(item.codi_discogs || release.discogs_release_id) && (
                <button onClick={() => handleEnrichImage(item)} disabled={!!actionId}
                  title={release.imagen_url ? 'Actualitzar caràtula' : 'Obtenir caràtula de Discogs'}
                  className="flex items-center gap-1 text-xs text-zinc-500 hover:text-violet-700 border border-zinc-200 hover:border-violet-200 px-2 py-0.5 rounded-lg transition-colors disabled:opacity-50">
                  {actionId === item.id + '_img' ? <Loader2 size={9} className="animate-spin" /> : <Image size={9} />}
                  {release.imagen_url ? '↑ Art' : 'Art'}
                </button>
              )}
            </div>

            {item.status !== 'vendido' && (
              <div className="flex items-center gap-0.5 ml-auto opacity-0 group-hover:opacity-100 transition-opacity">
                <button onClick={() => startEdit(item)} title="Editar"
                  className="p-1 text-zinc-400 hover:text-zinc-700 rounded-md hover:bg-zinc-100">
                  <Pencil size={12} />
                </button>
                <button onClick={() => deleteItem(item)} title="Eliminar"
                  className="p-1 text-zinc-300 hover:text-red-500 rounded-md hover:bg-red-50">
                  <Trash2 size={12} />
                </button>
              </div>
            )}
          </div>
        ))}
      </div>

      {!showForm ? (
        <button onClick={() => setShowForm(true)} className="text-xs text-amber-600 hover:text-amber-700 font-medium mt-1">
          + Afegir còpia
        </button>
      ) : (
        <form onSubmit={save} className="flex flex-wrap items-end gap-3 mt-2 p-4 bg-white rounded-xl border border-amber-200 shadow-sm">
          <Field label={t('common.condition')}>
            <select value={form.condicion} onChange={e => setForm(f => ({ ...f, condicion: e.target.value }))}
              className="border border-zinc-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900 bg-white">
              <option value="segona_ma">{t('common.condition.used')}</option>
              <option value="nou">{t('common.condition.new')}</option>
            </select>
          </Field>
          <Field label="Cost (€)">
            <input type="number" step="0.01" min="0" value={form.coste_adquisicion}
              onChange={e => setForm(f => ({ ...f, coste_adquisicion: e.target.value }))}
              placeholder="0.00"
              className="w-24 border border-zinc-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
          </Field>
          <Field label="PVP (€)">
            <input type="number" step="0.01" min="0" required value={form.precio}
              onChange={e => setForm(f => ({ ...f, precio: e.target.value }))}
              className="w-24 border border-zinc-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
          </Field>
          {form.condicion === 'nou' ? (
            <Field label="Unitats">
              <input type="number" step="1" min="1" required value={form.cantidad}
                onChange={e => setForm(f => ({ ...f, cantidad: e.target.value }))}
                title="Si ja hi ha estoc nou d'aquest disc, se sumarà a la línia existent"
                className="w-20 border border-zinc-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
            </Field>
          ) : (
            <>
              <Field label={t('catalog.disc_grade')}>
                <GradingSelect value={form.estado_disco} onChange={v => setForm(f => ({ ...f, estado_disco: v }))} />
              </Field>
              <Field label={t('catalog.sleeve_grade')}>
                <GradingSelect value={form.estado_funda} onChange={v => setForm(f => ({ ...f, estado_funda: v }))} />
              </Field>
            </>
          )}
          <div className="flex gap-2 pb-0.5">
            <Button type="submit" size="sm" disabled={saving}>{saving ? t('common.saving') : t('common.save')}</Button>
            <Button type="button" variant="ghost" size="sm" onClick={() => setShowForm(false)}>{t('common.cancel')}</Button>
          </div>
        </form>
      )}
    </div>
  );
}

// ---- Shared form helpers ---------------------------------------------------

function Field({ label, children }) {
  return (
    <div>
      <label className="block text-xs text-zinc-500 mb-1">{label}</label>
      {children}
    </div>
  );
}

function GradingSelect({ value, onChange }) {
  return (
    <select value={value} onChange={e => onChange(e.target.value)}
      className="border border-zinc-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900 bg-white">
      <option value="">—</option>
      {GRADINGS.map(g => <option key={g} value={g}>{g.split(' (')[0]}</option>)}
    </select>
  );
}

// ---- DiscModal (crear / editar / duplicar) ---------------------------------

function emptyForm() {
  return {
    artista: '', titulo: '', sello: '', ean: '', formato: 'LP', anio: '',
    genero: '', estilos: '', pais: '', imagen_url: '', discogs_release_id: '',
    tracklist: null, credits: null, pes_g: '', seccio_id: '',
    precio: '', condicion: 'segona_ma', estado_disco: '', estado_funda: '',
    etiqueta_ids: [], properament: false, data_disponibilitat: '',
  };
}

function formFromRelease(release) {
  return {
    artista: release.artista ?? '', titulo: release.titulo ?? '', sello: release.sello ?? '',
    ean: release.ean ?? '',
    formato: release.formato ?? 'LP', anio: release.anio ? String(release.anio) : '',
    genero: release.genero ?? '', estilos: release.estilos ?? '', pais: release.pais ?? '',
    imagen_url: release.imagen_url ?? '',
    discogs_release_id: release.discogs_release_id ? String(release.discogs_release_id) : '',
    tracklist: release.tracklist ?? null, credits: release.credits ?? null,
    pes_g: release.pes_g ? String(release.pes_g) : '',
    seccio_id: release.seccio_id ? String(release.seccio_id) : '',
    precio: '', condicion: 'segona_ma', estado_disco: '', estado_funda: '',
    etiqueta_ids: (release.etiquetes ?? []).map(e => e.id),
    properament: release.properament ?? false,
    data_disponibilitat: release.data_disponibilitat ?? '',
  };
}

function DiscModal({ mode, release, onClose, onSaved }) {
  const t = useT();
  const isEdit = mode === 'edit';
  const [discogsQ, setDiscogsQ] = useState('');
  const [discogsRes, setDiscogsRes] = useState([]);
  const [searching, setSearching] = useState(false);
  const [form, setForm] = useState(release ? formFromRelease(release) : emptyForm());
  const [saving, setSaving] = useState(false);
  const [dupMatches, setDupMatches] = useState([]);
  const [allEtiquetes, setAllEtiquetes] = useState([]);
  const [pesPerFormat, setPesPerFormat] = useState({});
  const [allSeccions, setAllSeccions] = useState([]);
  const f = (k, v) => setForm(prev => ({ ...prev, [k]: v }));

  useEffect(() => {
    authFetch('/admin/etiquetes').then(r => r.ok ? r.json() : []).then(setAllEtiquetes).catch(() => {});
    authFetch('/admin/pes-format').then(r => r.ok ? r.json() : [])
      .then(list => setPesPerFormat(Object.fromEntries(list.map(p => [p.formato, p.pes_g]))))
      .catch(() => {});
    authFetch('/admin/seccions').then(r => r.ok ? r.json() : []).then(setAllSeccions).catch(() => {});
  }, []);

  function toggleEtiqueta(id) {
    setForm(prev => ({
      ...prev,
      etiqueta_ids: prev.etiqueta_ids.includes(id)
        ? prev.etiqueta_ids.filter(x => x !== id)
        : [...prev.etiqueta_ids, id],
    }));
  }

  const dupCheckTimer = useRef(null);
  function scheduleDupCheck() {
    if (isEdit) return;
    clearTimeout(dupCheckTimer.current);
    dupCheckTimer.current = setTimeout(checkDuplicate, 400);
  }

  async function checkDuplicate() {
    const params = new URLSearchParams();
    if (form.discogs_release_id) params.set('discogs_release_id', form.discogs_release_id);
    if (form.ean.trim()) params.set('ean', form.ean.trim());
    if (form.artista.trim() && form.titulo.trim()) {
      params.set('artista', form.artista.trim());
      params.set('titulo', form.titulo.trim());
    }
    if (mode === 'duplicate' && release?.id) params.set('exclude_id', release.id);
    if (!params.has('discogs_release_id') && !params.has('ean') && !params.has('artista')) { setDupMatches([]); return; }
    try {
      const r = await authFetch(`/admin/releases/check-duplicate?${params.toString()}`);
      if (r.ok) setDupMatches(await r.json());
    } catch { /* informatiu */ }
  }

  useEffect(() => { if (mode === 'duplicate') checkDuplicate(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  async function searchDiscogs() {
    if (!discogsQ.trim()) return;
    setSearching(true);
    try {
      const r = await authFetch(`/admin/discogs/search?q=${encodeURIComponent(discogsQ)}`);
      const data = await r.json();
      setDiscogsRes(Array.isArray(data) ? data : (data.results ?? []));
    } finally { setSearching(false); }
  }

  async function pick(result) {
    let full = result;
    if (result.discogs_release_id) {
      try {
        const r = await authFetch(`/admin/discogs/release/${result.discogs_release_id}`);
        if (r.ok) full = { ...result, ...(await r.json()) };
      } catch {}
    }
    setForm(prev => ({
      ...prev,
      artista: full.artista ?? prev.artista,
      titulo: full.titulo ?? prev.titulo,
      sello: full.sello ?? prev.sello,
      ean: full.ean ?? prev.ean ?? '',
      formato: full.formato?.split(',')[0].trim() ?? prev.formato,
      anio: full.anio ? String(full.anio) : prev.anio,
      genero: full.genero ?? prev.genero,
      estilos: full.estilos ?? prev.estilos ?? '',
      pais: full.pais ?? prev.pais ?? '',
      imagen_url: full.imagen_url ?? prev.imagen_url,
      discogs_release_id: full.discogs_release_id ? String(full.discogs_release_id) : prev.discogs_release_id,
      tracklist: full.tracklist ?? prev.tracklist ?? null,
      credits: full.credits ?? prev.credits ?? null,
    }));
    setDiscogsRes([]);
    setTimeout(checkDuplicate, 0);
  }

  function buildReleasePayload() {
    return {
      artista: form.artista, titulo: form.titulo,
      sello: form.sello || null, ean: form.ean || null, formato: form.formato || null,
      anio: form.anio ? parseInt(form.anio) : null,
      genero: form.genero || null, estilos: form.estilos || null,
      pais: form.pais || null, imagen_url: form.imagen_url || null,
      tracklist: form.tracklist || null, credits: form.credits || null,
      pes_g: form.pes_g ? parseInt(form.pes_g) : null,
      seccio_id: form.seccio_id ? parseInt(form.seccio_id) : null,
      discogs_release_id: form.discogs_release_id ? parseInt(form.discogs_release_id) : null,
    };
  }

  async function refreshFromDiscogs() {
    if (!form.discogs_release_id) return;
    setSaving(true);
    // Guardem primer per si l'ID s'ha editat i encara no s'ha desat.
    const saveResp = await authFetch(`/admin/releases/${release.id}`, {
      method: 'PUT', body: JSON.stringify(buildReleasePayload()),
    });
    if (!saveResp.ok) {
      const body = await saveResp.json().catch(() => ({}));
      alert(body.detail || 'No s\'ha pogut desar l\'ID de Discogs.');
      setSaving(false);
      return;
    }
    const resp = await authFetch(`/admin/discogs/sync/releases/${release.id}/enrich`, { method: 'POST' });
    if (resp.ok) {
      const data = await resp.json();
      setForm(prev => ({
        ...prev,
        tracklist: data.tracklist ?? prev.tracklist,
        credits: data.credits ?? prev.credits,
        genero: data.genero ?? prev.genero,
        pais: data.pais ?? prev.pais,
        estilos: data.estilos ?? prev.estilos,
        formato: data.formato ?? prev.formato,
        ean: data.ean ?? prev.ean,
        imagen_url: data.imagen_url ?? prev.imagen_url,
        sello: data.sello ?? prev.sello,
      }));
    } else {
      const body = await resp.json().catch(() => ({}));
      alert(body.detail || 'No s\'ha pogut actualitzar des de Discogs.');
    }
    setSaving(false);
  }

  async function save(e) {
    e.preventDefault();
    setSaving(true);
    const releasePayload = buildReleasePayload();

    let savedId;

    if (isEdit) {
      const resp = await authFetch(`/admin/releases/${release.id}`, { method: 'PUT', body: JSON.stringify(releasePayload) });
      if (!resp.ok) {
        const body = await resp.json().catch(() => ({}));
        alert(body.detail || 'No s\'ha pogut actualitzar.');
        setSaving(false);
        return;
      }
      savedId = release.id;
    } else {
      const rRes = await authFetch('/admin/releases', { method: 'POST', body: JSON.stringify(releasePayload) });
      const created = await rRes.json();
      savedId = created.id;
      if (form.precio) {
        await authFetch('/admin/items', {
          method: 'POST',
          body: JSON.stringify({
            release_id: savedId,
            precio: parseFloat(form.precio),
            condicion: form.condicion,
            estado_disco: form.condicion === 'nou' ? null : (form.estado_disco || null),
            estado_funda: form.condicion === 'nou' ? null : (form.estado_funda || null),
          }),
        });
      }
    }

    // Save etiquetes (always, even if empty — replaces all)
    await authFetch(`/admin/releases/${savedId}/etiquetes`, {
      method: 'PUT',
      body: JSON.stringify({ etiqueta_ids: form.etiqueta_ids }),
    });

    // Save properament
    const propParams = new URLSearchParams({ properament: form.properament });
    if (form.data_disponibilitat) propParams.set('data_disponibilitat', form.data_disponibilitat);
    await authFetch(`/admin/releases/${savedId}/properament?${propParams}`, { method: 'PATCH' });

    setSaving(false);
    onSaved();
  }

  const title = isEdit ? 'Editar disc' : mode === 'duplicate' ? 'Duplicar disc' : t('catalog.modal.title');

  return (
    <Modal title={title} onClose={onClose}>
      {dupMatches.length > 0 && (
        <div className="p-3 bg-amber-50 border border-amber-300 rounded-xl flex gap-3 text-sm">
          <AlertTriangle size={16} className="text-amber-600 shrink-0 mt-0.5" />
          <div>
            <div className="font-medium text-amber-800">{t('catalog.modal.dup_warning', 'Ja existeix un disc semblant al catàleg:')}</div>
            <ul className="mt-1 space-y-0.5">
              {dupMatches.map(m => (
                <li key={m.id} className="text-amber-700">
                  {m.artista} — {m.titulo} {m.sello ? `(${m.sello})` : ''} · {m.num_items} còpies
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}

      {!isEdit && (
        <div className="p-4 bg-zinc-50 rounded-xl border border-zinc-200 space-y-3">
          <div className="text-sm font-medium text-zinc-700">{t('catalog.modal.discogs')}</div>
          <div className="flex gap-2">
            <input
              value={discogsQ}
              onChange={e => setDiscogsQ(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && (e.preventDefault(), searchDiscogs())}
              placeholder={t('catalog.modal.discogs_ph')}
              className="flex-1 border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900"
            />
            <Button type="button" variant="secondary" onClick={searchDiscogs} disabled={searching}>
              <Search size={14} /> {searching ? t('common.searching') : t('common.search')}
            </Button>
          </div>
          {discogsRes.length > 0 && (
            <div className="max-h-52 overflow-y-auto space-y-1 border border-zinc-200 rounded-lg bg-white p-1">
              {discogsRes.map((r, i) => (
                <button key={i} type="button" onClick={() => pick(r)}
                  className="w-full flex items-center gap-3 p-2.5 rounded-lg hover:bg-amber-50 text-left transition-colors">
                  <CoverImg url={r.imagen_url} size={40} />
                  <div className="min-w-0">
                    <div className="text-sm font-semibold text-zinc-900 truncate">{r.artista} — {r.titulo}</div>
                    <div className="text-xs text-zinc-500">{[r.sello, r.formato, r.anio].filter(Boolean).join(' · ')}</div>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {isEdit && (
        <div className="p-4 bg-zinc-50 rounded-xl border border-zinc-200 space-y-2">
          <div className="text-sm font-medium text-zinc-700">
            {t('catalog.modal.discogs_id', 'ID de Discogs')}
          </div>
          <div className="flex gap-2">
            <input
              value={form.discogs_release_id}
              onChange={e => f('discogs_release_id', e.target.value.replace(/\D/g, ''))}
              placeholder={t('catalog.modal.discogs_id_ph', 'p.ex. 1234567 (discogs.com/release/1234567-...)')}
              className="flex-1 border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900"
            />
            <Button type="button" variant="secondary" onClick={refreshFromDiscogs} disabled={saving || !form.discogs_release_id}>
              {t('catalog.modal.discogs_refresh', 'Actualitzar des de Discogs')}
            </Button>
          </div>
          <p className="text-xs text-zinc-500">
            {t('catalog.modal.discogs_id_help', 'Vincula aquest disc a un release de Discogs (per a discos donats d\'alta a mà que ara ja hi estan catalogats). En actualitzar es desa l\'ID i es porten tracklist, crèdits i altres dades.')}
          </p>
        </div>
      )}

      <form onSubmit={save} className="space-y-4">
        <div className="grid grid-cols-2 gap-3">
          {[
            ['artista', t('catalog.modal.artist'), true],
            ['titulo', t('catalog.modal.title_field'), true],
          ].map(([k, lbl, req]) => (
            <div key={k}>
              <label className="block text-sm font-medium text-zinc-700 mb-1">{lbl}</label>
              <input value={form[k]} onChange={e => f(k, e.target.value)} onBlur={scheduleDupCheck} required={req}
                className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
            </div>
          ))}
          <div>
            <label className="block text-sm font-medium text-zinc-700 mb-1">{t('catalog.modal.label')}</label>
            <input value={form.sello} onChange={e => f('sello', e.target.value)}
              className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
          </div>
          <div>
            <label className="block text-sm font-medium text-zinc-700 mb-1">{t('catalog.modal.ean', 'EAN / codi de barres')}</label>
            <input value={form.ean} onChange={e => f('ean', e.target.value)} onBlur={scheduleDupCheck}
              placeholder="p.ex. 0888072345678"
              className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
          </div>
          <div>
            <label className="block text-sm font-medium text-zinc-700 mb-1">{t('catalog.modal.format')}</label>
            <select value={form.formato} onChange={e => f('formato', e.target.value)}
              className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900 bg-white">
              {['LP', 'EP', '7"', '12"', 'CD', 'Cassette', 'Altre'].map(x => <option key={x}>{x}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-zinc-700 mb-1">{t('catalog.modal.year')}</label>
            <input type="number" value={form.anio} onChange={e => f('anio', e.target.value)} min="1900" max="2030"
              className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
          </div>
          <div>
            <label className="block text-sm font-medium text-zinc-700 mb-1">{t('catalog.modal.genre')}</label>
            <input value={form.genero} onChange={e => f('genero', e.target.value)}
              className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
          </div>
          <div>
            <label className="block text-sm font-medium text-zinc-700 mb-1">Secció (cubeta)</label>
            <select value={form.seccio_id} onChange={e => f('seccio_id', e.target.value)}
              className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900 bg-white">
              <option value="">Sense classificar</option>
              {allSeccions.map(s => <option key={s.id} value={s.id}>{s.nom_ca}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-zinc-700 mb-1">Pes (grams)</label>
            <input type="number" min="1" value={form.pes_g} onChange={e => f('pes_g', e.target.value)}
              placeholder={pesPerFormat[form.formato] != null ? String(pesPerFormat[form.formato]) : ''}
              className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
            <p className="text-xs text-zinc-400 mt-1">
              Nomes per a casos especials. Buit = pes per defecte del format{' '}
              {pesPerFormat[form.formato] != null ? `(${pesPerFormat[form.formato]} g, ` : '('}
              configurable a Configuració → Enviaments).
            </p>
          </div>
        </div>
        <div>
          <label className="block text-sm font-medium text-zinc-700 mb-1">{t('catalog.modal.image_url')}</label>
          <input value={form.imagen_url} onChange={e => f('imagen_url', e.target.value)}
            className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
        </div>

        {/* Etiquetes */}
        {allEtiquetes.length > 0 && (
          <div>
            <label className="block text-sm font-medium text-zinc-700 mb-2">Etiquetes</label>
            <div className="flex flex-wrap gap-2">
              {allEtiquetes.map(et => {
                const active = form.etiqueta_ids.includes(et.id);
                return (
                  <button key={et.id} type="button" onClick={() => toggleEtiqueta(et.id)}
                    className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold border transition-all ${active ? 'text-white border-transparent' : 'text-zinc-600 bg-white border-zinc-300 hover:border-zinc-400'}`}
                    style={active ? { backgroundColor: et.color || '#94a3b8', borderColor: et.color || '#94a3b8' } : {}}>
                    {et.nom_ca}
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {/* Properament */}
        <div className="flex items-start gap-4">
          <label className="flex items-center gap-2 cursor-pointer select-none">
            <input type="checkbox" checked={form.properament} onChange={e => f('properament', e.target.checked)}
              className="w-4 h-4 rounded border-zinc-300 text-violet-600 focus:ring-violet-500" />
            <span className="text-sm font-medium text-zinc-700">Properament (pre-venda)</span>
          </label>
          {form.properament && (
            <div>
              <label className="block text-xs text-zinc-500 mb-1">Data disponibilitat (opcional)</label>
              <input type="date" value={form.data_disponibilitat} onChange={e => f('data_disponibilitat', e.target.value)}
                className="border border-zinc-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-violet-500" />
            </div>
          )}
        </div>

        {!isEdit && (
          <div className="border-t border-zinc-200 pt-4">
            <div className="text-sm font-semibold text-zinc-700 mb-3">{t('catalog.modal.first_copy')}</div>
            <div className="grid grid-cols-2 gap-3 mb-3">
              <div>
                <label className="block text-xs text-zinc-500 mb-1">{t('common.condition')}</label>
                <select value={form.condicion} onChange={e => f('condicion', e.target.value)}
                  className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900 bg-white">
                  <option value="segona_ma">{t('common.condition.used')}</option>
                  <option value="nou">{t('common.condition.new')}</option>
                </select>
              </div>
              <div>
                <label className="block text-xs text-zinc-500 mb-1">{t('common.price')}</label>
                <input type="number" step="0.01" min="0" value={form.precio} onChange={e => f('precio', e.target.value)}
                  className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
              </div>
            </div>
            {form.condicion === 'segona_ma' && (
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs text-zinc-500 mb-1">{t('catalog.disc_grade')}</label>
                  <GradingSelect value={form.estado_disco} onChange={v => f('estado_disco', v)} />
                </div>
                <div>
                  <label className="block text-xs text-zinc-500 mb-1">{t('catalog.sleeve_grade')}</label>
                  <GradingSelect value={form.estado_funda} onChange={v => f('estado_funda', v)} />
                </div>
              </div>
            )}
          </div>
        )}

        <div className="flex justify-end gap-3 pt-2">
          <Button type="button" variant="secondary" onClick={onClose}>{t('common.cancel')}</Button>
          <Button type="submit" disabled={saving}>
            {saving ? t('common.saving') : isEdit ? t('common.save') : t('catalog.modal.create')}
          </Button>
        </div>
      </form>
    </Modal>
  );
}

function Modal({ title, onClose, children }) {
  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-start justify-center p-4 overflow-y-auto">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl my-8">
        <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-200">
          <h3 className="text-lg font-bold text-zinc-900">{title}</h3>
          <button onClick={onClose} className="text-zinc-400 hover:text-zinc-600 p-1 rounded-lg hover:bg-zinc-100">
            <X size={20} />
          </button>
        </div>
        <div className="p-6 space-y-5">{children}</div>
      </div>
    </div>
  );
}
