'use client';

import { useState, useEffect, useRef, useMemo, Fragment } from 'react';
import { authFetch } from '../../lib/auth';
import { useT } from '../../lib/i18n';
import { useDiscogsEnabled } from '../../../components/store/useDiscogsEnabled';
import { useTenantVertical } from '../../../components/store/useTenantVertical';
import { Button } from '../../../components/ui/button';
import { useSortFilter } from '../../../components/admin/table/useSortFilter';
import { SortableTh } from '../../../components/admin/table/SortableTh';
import {
  Plus, ChevronDown, ChevronRight, X, Trash2, RotateCcw, FileSpreadsheet, Download,
  FileText, Send, Ban, PackageCheck, Loader2, Receipt, ArrowRight, Sparkles, TrendingUp, TrendingDown, Minus,
} from 'lucide-react';

const DESPESA_ESTAT_FALLBACK = { pendent: 'Pendent', vencut: 'Vençuda', pagat: 'Pagada' };
const DESPESA_ESTAT_COLOR = {
  pendent: 'bg-amber-100 text-amber-700', vencut: 'bg-red-100 text-red-600', pagat: 'bg-emerald-100 text-emerald-700',
};
function despesaEstatLabel(t, estat) {
  return t(`purchases.despesa_status.${estat}`, DESPESA_ESTAT_FALLBACK[estat] ?? estat);
}

const GRADINGS = ['Mint (M)', 'Near Mint (NM or M-)', 'Very Good Plus (VG+)', 'Very Good (VG)', 'Good Plus (G+)', 'Good (G)', 'Fair (F)', 'Poor (P)'];

const COMANDA_STATUS_FALLBACK = {
  esborrany: 'Esborrany', enviada: 'Enviada', rebuda_parcial: 'Rebuda parcial',
  rebuda: 'Rebuda', cancelada: 'Cancel·lada',
};
const COMANDA_STATUS_COLOR = {
  esborrany: 'bg-zinc-100 text-zinc-600', enviada: 'bg-blue-100 text-blue-700',
  rebuda_parcial: 'bg-amber-100 text-amber-700', rebuda: 'bg-emerald-100 text-emerald-700',
  cancelada: 'bg-red-100 text-red-600',
};
function comandaStatusLabel(t, status) {
  return t(`purchases.comanda_status.${status}`, COMANDA_STATUS_FALLBACK[status] ?? status);
}

const SOLICITUD_STATUS_FALLBACK = { oberta: 'Oberta', resolta: 'Resolta', cancelada: 'Cancel·lada' };
const SOLICITUD_STATUS_COLOR = {
  oberta: 'bg-blue-100 text-blue-700', resolta: 'bg-emerald-100 text-emerald-700',
  cancelada: 'bg-red-100 text-red-600',
};
function solicitudStatusLabel(t, estado) {
  return t(`purchases.solicitud_status.${estado}`, SOLICITUD_STATUS_FALLBACK[estado] ?? estado);
}

export default function ComprasPage() {
  const t = useT();
  const [tab, setTab] = useState('solicituds');
  const [comprasParticulars, setComprasParticulars] = useState([]);
  const [comprasProveedor, setComprasProveedor] = useState([]);
  const [proveedores, setProveedores] = useState([]);
  const [comandas, setComandas] = useState([]);
  const [solicitudes, setSolicitudes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [showParticularModal, setShowParticularModal] = useState(false);
  const [showSolicitudModal, setShowSolicitudModal] = useState(false);
  const [showRefillModal, setShowRefillModal] = useState(false);
  const [expanded, setExpanded] = useState(null);
  const [returnItem, setReturnItem] = useState(null); // { item, compra_id }
  const [recepcioComanda, setRecepcioComanda] = useState(null);
  const [editingProveedor, setEditingProveedor] = useState(null);
  const [showFacturarModal, setShowFacturarModal] = useState(false);
  const [filters, setFilters] = useState({ q: '', desde: '', hasta: '' });
  const [provQ, setProvQ] = useState('');
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
    const extra = qs ? `&${qs}` : '';
    const [cRes, provRes, pRes, ordRes, solRes] = await Promise.all([
      authFetch(`/admin/compras?tipo=particular${extra}`), authFetch(`/admin/compras?tipo=proveedor${extra}`),
      authFetch('/admin/proveedores'), authFetch(`/admin/comandas${qs ? `?${qs}` : ''}`),
      authFetch('/admin/solicitudes-compra'),
    ]);
    setComprasParticulars(await cRes.json());
    setComprasProveedor(await provRes.json());
    setProveedores(await pRes.json());
    setComandas(await ordRes.json());
    setSolicitudes(await solRes.json());
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

  const proveedoresColumns = useMemo(() => ({
    name: { sortValue: p => (p.name ?? '').toLowerCase() },
    type: { sortValue: p => p.type ?? '', filterValue: p => p.type },
    nif: { sortValue: p => p.nif ?? '' },
    email: { sortValue: p => p.email ?? '' },
    phone: { sortValue: p => p.phone ?? '' },
    active: {
      sortValue: p => p.active ? t('purchases.supplier.active', 'Actiu') : t('purchases.supplier.inactive', 'Inactiu'),
      filterValue: p => p.active ? t('purchases.supplier.active', 'Actiu') : t('purchases.supplier.inactive', 'Inactiu'),
    },
  }), [t]);
  const provQl = provQ.trim().toLowerCase();
  const proveedoresBuscats = useMemo(() => !provQl ? proveedores : proveedores.filter(p =>
    [p.name, p.nif, p.email, p.phone, p.contact].some(v => v && v.toLowerCase().includes(provQl))
  ), [proveedores, provQl]);
  const {
    rows: proveedoresFiltrats, sort: provSort, toggleSort: toggleProvSort,
    filters: provFilters, setFilter: setProvFilter, distinctValues: provDistinct,
  } = useSortFilter(proveedoresBuscats, proveedoresColumns);

  return (
    <div className="space-y-5 max-w-5xl mx-auto">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-zinc-900">{t('purchases.title')}</h2>
        <div className="flex items-center gap-2">
          {tab === 'comandas' ? (
            <>
              <button onClick={() => setShowFacturarModal(true)}
                className="flex items-center gap-1.5 text-sm border border-zinc-200 text-zinc-600 hover:bg-zinc-50 px-3 py-2 rounded-lg transition-colors">
                <Receipt size={13} /> {t('purchases.btn.invoice_receptions', 'Facturar recepcions')}
              </button>
              <button onClick={() => setShowParticularModal(true)}
                className="flex items-center gap-1.5 text-sm border border-zinc-200 text-zinc-600 hover:bg-zinc-50 px-3 py-2 rounded-lg transition-colors">
                <Plus size={13} /> {t('purchases.btn.individual_purchase', 'Compra particular')}
              </button>
              <Button onClick={() => setShowModal(true)}>
                <Plus size={16} /> {t('purchases.btn.new_order', 'Nova comanda')}
              </Button>
            </>
          ) : tab === 'solicituds' ? (
            <>
              <button onClick={() => setShowRefillModal(true)}
                className="flex items-center gap-1.5 text-sm border border-zinc-200 text-zinc-600 hover:bg-zinc-50 px-3 py-2 rounded-lg transition-colors">
                <Sparkles size={13} /> {t('purchases.btn.generate_suggestions', 'Generar suggeriments')}
              </button>
              <Button onClick={() => setShowSolicitudModal(true)}>
                <Plus size={16} /> {t('purchases.btn.new_request', 'Nova sol·licitud')}
              </Button>
            </>
          ) : tab === 'proveedores' ? (
            <Button onClick={() => setShowModal(true)}>
              <Plus size={16} /> {t('purchases.new_supplier')}
            </Button>
          ) : null}
        </div>
      </div>

      <div className="flex gap-1 bg-zinc-100 p-1 rounded-xl w-fit">
        {[
          ['solicituds', t('purchases.tab.requests', 'Sol·licituds')],
          ['comandas', t('purchases.tab.orders', 'Comandes')],
          ['buscador', t('purchases.tab.search_supplier', 'Cerca proveïdor')],
          ['resum', t('purchases.tab.summary', 'Resum')],
          ['proveedores', t('purchases.tab.suppliers')],
        ].map(([key, label]) => (
          <button key={key} onClick={() => setTab(key)}
            className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors ${tab === key ? 'bg-white text-zinc-900 shadow-sm' : 'text-zinc-600 hover:text-zinc-900'}`}>
            {label}
          </button>
        ))}
      </div>

      {tab === 'comandas' && (
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
      )}

      {tab === 'comandas' && (
        <ComandesTab
          comandas={comandas} comprasParticulars={comprasParticulars} comprasProveedor={comprasProveedor}
          loading={loading}
          expanded={expanded} setExpanded={setExpanded}
          onRefresh={loadAll}
          onRecepcio={setRecepcioComanda}
          onReturnItem={setReturnItem}
          hasFilters={hasFilters}
        />
      )}

      {tab === 'solicituds' && (
        <SolicitudsTab
          solicitudes={solicitudes} loading={loading} proveedores={proveedores}
          expanded={expanded} setExpanded={setExpanded}
          onRefresh={loadAll}
        />
      )}

      {tab === 'buscador' && <BuscadorProveidorTab onRefresh={loadAll} />}

      {tab === 'resum' && <ResumTab proveedores={proveedores} />}

      {tab === 'proveedores' && (
        <>
          <input value={provQ} onChange={e => setProvQ(e.target.value)}
            placeholder={t('purchases.supplier_search_ph', 'Cerca per nom, NIF, email, telèfon o contacte...')}
            className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
          <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm overflow-hidden">
            {proveedores.length === 0 ? (
              <div className="p-12 text-center text-zinc-400 text-sm">{t('purchases.no_suppliers')}</div>
            ) : proveedoresFiltrats.length === 0 ? (
              <div className="p-12 text-center text-zinc-400 text-sm">{t('purchases.no_supplier_match', 'Cap proveïdor coincideix amb la cerca.')}</div>
            ) : (
              <table className="w-full text-sm">
                <thead className="bg-zinc-50 text-xs text-zinc-500 border-b border-zinc-200">
                  <tr>
                    <SortableTh label={t('common.name')} sortKey="name" sort={provSort} onSort={toggleProvSort} />
                    <SortableTh label={t('common.type')} sortKey="type" sort={provSort} onSort={toggleProvSort}
                      filterOptions={provDistinct.type} selected={provFilters.type} onFilterChange={setProvFilter} />
                    <SortableTh label={t('purchases.col.nif', 'NIF')} sortKey="nif" sort={provSort} onSort={toggleProvSort} />
                    <SortableTh label={t('purchases.col.email', 'Email')} sortKey="email" sort={provSort} onSort={toggleProvSort} />
                    <SortableTh label={t('purchases.col.phone', 'Telèfon')} sortKey="phone" sort={provSort} onSort={toggleProvSort} />
                    <SortableTh label={t('purchases.col.status', 'Estat')} sortKey="active" sort={provSort} onSort={toggleProvSort} align="center"
                      filterOptions={provDistinct.active} selected={provFilters.active} onFilterChange={setProvFilter} />
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-100">
                  {proveedoresFiltrats.map(p => (
                    <tr key={p.id} onClick={() => setEditingProveedor(p)} className="hover:bg-zinc-50 cursor-pointer transition-colors">
                      <td className="px-5 py-3 font-medium">{p.name}</td>
                      <td className="px-5 py-3 text-zinc-500">{p.type ?? '—'}</td>
                      <td className="px-5 py-3 text-zinc-500">{p.nif ?? '—'}</td>
                      <td className="px-5 py-3 text-zinc-500">{p.email ?? '—'}</td>
                      <td className="px-5 py-3 text-zinc-500">{p.phone ?? '—'}</td>
                      <td className="px-5 py-3 text-center">
                        <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${p.active ? 'bg-emerald-100 text-emerald-700' : 'bg-zinc-100 text-zinc-500'}`}>
                          {p.active ? t('purchases.supplier.active', 'Actiu') : t('purchases.supplier.inactive', 'Inactiu')}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </>
      )}

      {showModal && tab === 'proveedores' && (
        <ProveedorModal
          proveedor={null}
          onClose={() => setShowModal(false)}
          onSaved={() => { setShowModal(false); loadAll(); }} />
      )}
      {editingProveedor && (
        <ProveedorModal
          proveedor={editingProveedor}
          onClose={() => setEditingProveedor(null)}
          onSaved={() => { setEditingProveedor(null); loadAll(); }} />
      )}
      {showModal && tab === 'comandas' && (
        <NovaComandaModal proveedores={proveedores}
          onClose={() => setShowModal(false)}
          onSaved={() => { setShowModal(false); loadAll(); }} />
      )}
      {showParticularModal && (
        <CompraParticularModal
          onClose={() => setShowParticularModal(false)}
          onSaved={() => { setShowParticularModal(false); loadAll(); }} />
      )}
      {recepcioComanda && (
        <RecepcioModal comanda={recepcioComanda}
          onClose={() => setRecepcioComanda(null)}
          onSaved={() => { setRecepcioComanda(null); loadAll(); }} />
      )}
      {returnItem && (
        <DevolucionCompraModal
          item={returnItem.item}
          compraId={returnItem.compra_id}
          onClose={() => setReturnItem(null)}
          onSaved={() => { setReturnItem(null); loadAll(); }}
        />
      )}
      {showFacturarModal && (
        <FacturarRecepcionsModal
          proveedores={proveedores}
          onClose={() => setShowFacturarModal(false)}
          onSaved={() => { setShowFacturarModal(false); loadAll(); }}
        />
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

// ---- CompraParticularModal ---------------------------------------------------
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


function proveedorTipos(t) {
  return [
    ['distribuidor', t('purchases.supplier.type.dist', 'Distribuïdor')],
    ['proveidor_online', t('purchases.supplier.type.online_provider', 'Proveïdor online')],
    ['subministrador', t('purchases.supplier.type.provider', 'Subministrador')],
    ['professional', t('purchases.supplier.type.professional', 'Professional')],
    ['transport', t('purchases.supplier.type.transport', 'Transport')],
    ['particular', t('purchases.type.individual', 'Particular')],
    ['altres', t('purchases.supplier.type.other', 'Altres')],
  ];
}
function proveedorMetodesPagament(t) {
  return [
    ['transferencia', t('purchases.payment_method.transfer', 'Transferència')],
    ['rebut_domiciliat', t('purchases.payment_method.direct_debit', 'Rebut domiciliat')],
    ['targeta', t('tpv.pago.card')],
    ['efectiu', t('tpv.pago.cash')],
    ['paypal_altres', t('purchases.payment_method.paypal_other', 'PayPal / altres')],
  ];
}

function emptyProveedorForm() {
  return {
    name: '', type: '', nif: '', email: '', phone: '', address: '', contact: '',
    active: true, supplier_iban: '', payment_method: '', payment_days: '', payment_day_of_month: '', notes: '',
  };
}

function ProveedorModal({ proveedor, onClose, onSaved }) {
  const t = useT();
  const isEdit = !!proveedor;
  const [form, setForm] = useState(proveedor ? {
    name: proveedor.name ?? '', type: proveedor.type ?? '', nif: proveedor.nif ?? '',
    email: proveedor.email ?? '', phone: proveedor.phone ?? '', address: proveedor.address ?? '',
    contact: proveedor.contact ?? '', active: proveedor.active ?? true,
    supplier_iban: proveedor.supplier_iban ?? '', payment_method: proveedor.payment_method ?? '',
    payment_days: proveedor.payment_days ?? '', payment_day_of_month: proveedor.payment_day_of_month ?? '',
    notes: proveedor.notes ?? '',
  } : emptyProveedorForm());
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const f = (k, v) => setForm(prev => ({ ...prev, [k]: v }));

  async function save(e) {
    e.preventDefault();
    setSaving(true);
    setError('');
    const payload = {
      name: form.name, type: form.type || null, nif: form.nif || null,
      email: form.email || null, phone: form.phone || null, address: form.address || null,
      contact: form.contact || null, active: form.active,
      supplier_iban: form.supplier_iban || null, payment_method: form.payment_method || null,
      payment_days: form.payment_days ? parseInt(form.payment_days, 10) : null,
      payment_day_of_month: form.payment_day_of_month ? parseInt(form.payment_day_of_month, 10) : null,
      notes: form.notes || null,
    };
    const r = isEdit
      ? await authFetch(`/admin/proveedores/${proveedor.id}`, { method: 'PATCH', body: JSON.stringify(payload) })
      : await authFetch('/admin/proveedores', { method: 'POST', body: JSON.stringify(payload) });
    setSaving(false);
    if (!r.ok) {
      const body = await r.json().catch(() => ({}));
      setError(body.detail || t('purchases.supplier_modal.save_error', 'No s\'ha pogut desar.'));
      return;
    }
    onSaved();
  }

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-start justify-center p-4 overflow-y-auto">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl my-8">
        <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-200">
          <h3 className="font-bold text-zinc-900">{isEdit ? t('purchases.supplier_modal.edit_title', 'Editar proveïdor') : t('purchases.new_supplier')}</h3>
          <button onClick={onClose} className="text-zinc-400 hover:text-zinc-600 p-1 rounded-lg hover:bg-zinc-100"><X size={20} /></button>
        </div>
        <form onSubmit={save} className="p-6 space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div className="col-span-2">
              <label className="block text-sm font-medium text-zinc-700 mb-1">{t('purchases.supplier_modal.name', 'Nom *')}</label>
              <input value={form.name} onChange={e => f('name', e.target.value)} required
                className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
            </div>
            <div>
              <label className="block text-sm font-medium text-zinc-700 mb-1">{t('common.type')}</label>
              <select value={form.type} onChange={e => f('type', e.target.value)}
                className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900 bg-white">
                <option value="">—</option>
                {proveedorTipos(t).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-zinc-700 mb-1">{t('purchases.col.nif', 'NIF')}</label>
              <input value={form.nif} onChange={e => f('nif', e.target.value)}
                className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
            </div>
            <div>
              <label className="block text-sm font-medium text-zinc-700 mb-1">{t('purchases.col.email', 'Email')}</label>
              <input type="email" value={form.email} onChange={e => f('email', e.target.value)}
                className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
            </div>
            <div>
              <label className="block text-sm font-medium text-zinc-700 mb-1">{t('purchases.col.phone', 'Telèfon')}</label>
              <input value={form.phone} onChange={e => f('phone', e.target.value)}
                className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
            </div>
            <div className="col-span-2">
              <label className="block text-sm font-medium text-zinc-700 mb-1">{t('purchases.supplier_modal.address', 'Adreça')}</label>
              <input value={form.address} onChange={e => f('address', e.target.value)}
                className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
            </div>
            <div className="col-span-2">
              <label className="block text-sm font-medium text-zinc-700 mb-1">{t('purchases.supplier_modal.contact_person', 'Persona de contacte')}</label>
              <input value={form.contact} onChange={e => f('contact', e.target.value)}
                className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
            </div>
            <div className="col-span-2">
              <label className="block text-sm font-medium text-zinc-700 mb-1">{t('purchases.supplier_modal.iban', 'Número de compte (IBAN)')}</label>
              <input value={form.supplier_iban} onChange={e => f('supplier_iban', e.target.value)}
                placeholder={t('purchases.supplier_modal.iban_ph', 'ESXX XXXX XXXX XXXX XXXX XXXX')}
                className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
            </div>
            <div>
              <label className="block text-sm font-medium text-zinc-700 mb-1">{t('purchases.supplier_modal.payment_method', 'Mètode de pagament')}</label>
              <select value={form.payment_method} onChange={e => f('payment_method', e.target.value)}
                className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900 bg-white">
                <option value="">—</option>
                {proveedorMetodesPagament(t).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-sm font-medium text-zinc-700 mb-1">{t('purchases.supplier_modal.payment_days', 'Dies de pagament')}</label>
                <input type="number" min="0" value={form.payment_days} onChange={e => f('payment_days', e.target.value)}
                  placeholder={t('purchases.supplier_modal.payment_days_ph', '30, 60...')}
                  className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
              </div>
              <div>
                <label className="block text-sm font-medium text-zinc-700 mb-1">{t('purchases.supplier_modal.fixed_day', 'Dia fix del mes')}</label>
                <input type="number" min="1" max="31" value={form.payment_day_of_month} onChange={e => f('payment_day_of_month', e.target.value)}
                  className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
              </div>
            </div>
            <div className="col-span-2">
              <label className="block text-sm font-medium text-zinc-700 mb-1">{t('common.notes')}</label>
              <textarea value={form.notes} onChange={e => f('notes', e.target.value)} rows={2}
                className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900 resize-none" />
            </div>
            <div className="col-span-2 flex items-center gap-2">
              <input type="checkbox" id="proveedor-actiu" checked={form.active} onChange={e => f('active', e.target.checked)}
                className="rounded border-zinc-300 text-amber-600 focus:ring-zinc-900" />
              <label htmlFor="proveedor-actiu" className="text-sm text-zinc-700">{t('purchases.supplier_modal.active_checkbox', 'Proveïdor actiu')}</label>
            </div>
          </div>
          {error && <p className="text-red-500 text-sm">{error}</p>}
          <div className="flex justify-end gap-3 pt-2">
            <Button type="button" variant="secondary" onClick={onClose}>{t('common.cancel')}</Button>
            <Button type="submit" disabled={saving}>{saving ? t('common.saving') : isEdit ? t('common.save') : t('common.create')}</Button>
          </div>
        </form>
      </div>
    </div>
  );
}

function DevolucionCompraModal({ item, compraId, onClose, onSaved }) {
  const t = useT();
  const [motivo, setMotivo] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  async function save(e) {
    e.preventDefault();
    if (!motivo.trim()) { setError(t('return.motivo')); return; }
    setSaving(true);
    const r = await authFetch('/admin/devolucions/compra', {
      method: 'POST',
      body: JSON.stringify({
        item_id: item.item_id,
        compra_id: compraId,
        reason: motivo,
        date: new Date().toISOString(),
      }),
    });
    setSaving(false);
    if (r.ok) onSaved();
    else setError((await r.json()).detail ?? 'Error');
  }

  return (
    <div className="fixed inset-0 bg-black/60 z-[60] flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-sm">
        <div className="flex items-center justify-between px-5 py-4 border-b border-zinc-200">
          <h3 className="font-bold text-zinc-900">{t('return.title.purchase')}</h3>
          <button onClick={onClose} className="text-zinc-400 hover:text-zinc-600 p-1 rounded-lg hover:bg-zinc-100"><X size={18} /></button>
        </div>
        <form onSubmit={save} className="p-5 space-y-4">
          <div className="p-3 bg-zinc-50 rounded-xl text-sm">
            <span className="font-semibold text-zinc-900">{item.artista} — {item.title}</span>
            <span className="text-zinc-400 ml-2">{item.price} €</span>
          </div>
          <div>
            <label className="block text-sm font-medium text-zinc-700 mb-1">{t('return.motivo')}</label>
            <textarea value={motivo} onChange={e => setMotivo(e.target.value)} rows={2} required
              placeholder={t('return.motivo_ph')}
              className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900 resize-none" />
          </div>
          {error && <p className="text-red-500 text-xs">{error}</p>}
          <div className="flex gap-3 pt-1">
            <Button type="button" variant="secondary" className="flex-1" onClick={onClose}>{t('common.cancel')}</Button>
            <Button type="submit" className="flex-1" disabled={saving}>
              {saving ? t('return.confirming') : t('return.confirm')}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ---- ComandesTab -------------------------------------------------------------

function ComandesTab({ comandas, comprasParticulars, comprasProveedor, loading, expanded, setExpanded, onRefresh, onRecepcio, onReturnItem, hasFilters }) {
  const t = useT();
  const [busyId, setBusyId] = useState(null);

  const rows = [
    ...comandas.map(c => ({ kind: 'comanda', id: c.id, fecha: c.date, raw: c })),
    ...comprasParticulars.map(c => ({ kind: 'particular', id: c.id, fecha: c.date, raw: c })),
  ].sort((a, b) => new Date(b.fecha) - new Date(a.fecha));

  const columns = useMemo(() => ({
    fecha: { sortValue: r => r.fecha ?? '' },
    origen: {
      sortValue: r => r.kind === 'comanda' ? t('purchases.badge.order', 'Comanda') : t('purchases.type.individual'),
      filterValue: r => r.kind === 'comanda' ? t('purchases.badge.order', 'Comanda') : t('purchases.type.individual'),
    },
    entitat: { sortValue: r => (r.kind === 'comanda' ? r.raw.proveedor_nombre : (r.raw.individual_name ?? r.raw.user_nom ?? '')).toLowerCase() },
    linies: { sortValue: r => (r.kind === 'comanda' ? r.raw.lineas?.length : r.raw.items?.length) ?? 0 },
    estat: {
      sortValue: r => r.kind === 'comanda' ? comandaStatusLabel(t, r.raw.status) : comandaStatusLabel(t, 'rebuda'),
      filterValue: r => r.kind === 'comanda' ? comandaStatusLabel(t, r.raw.status) : comandaStatusLabel(t, 'rebuda'),
    },
  }), [t]);
  const { rows: rowsSorted, sort, toggleSort, filters, setFilter, distinctValues } = useSortFilter(rows, columns);

  async function downloadPdf(comanda) {
    const r = await authFetch(`/admin/comandas/${comanda.id}/pdf`);
    if (!r.ok) return;
    const blob = await r.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `comanda_${comanda.order_number || comanda.id}.pdf`;
    a.click();
    URL.revokeObjectURL(url);
  }

  async function downloadRecepcioPdf(compra) {
    const r = await authFetch(`/admin/compras/${compra.id}/pdf`);
    if (!r.ok) return;
    const blob = await r.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `recepcio_${compra.delivery_note_number || compra.id}.pdf`;
    a.click();
    URL.revokeObjectURL(url);
  }

  async function enviarPerEmail(comanda) {
    setBusyId(comanda.id + '_enviar');
    const r = await authFetch(`/admin/comandas/${comanda.id}/enviar`, { method: 'POST' });
    if (!r.ok) {
      const body = await r.json().catch(() => ({}));
      alert(body.detail || t('purchases.order.send_error', 'No s\'ha pogut enviar.'));
    }
    setBusyId(null);
    onRefresh();
  }

  async function marcarEnviada(comanda) {
    setBusyId(comanda.id + '_marcar');
    await authFetch(`/admin/comandas/${comanda.id}/marcar-enviada`, { method: 'PATCH' });
    setBusyId(null);
    onRefresh();
  }

  async function cancelar(comanda) {
    if (!confirm(t('purchases.order.confirm_cancel', 'Cancel·lar aquesta comanda?'))) return;
    setBusyId(comanda.id + '_cancelar');
    await authFetch(`/admin/comandas/${comanda.id}/cancelar`, { method: 'PATCH' });
    setBusyId(null);
    onRefresh();
  }

  async function eliminar(comanda) {
    if (!confirm(t('purchases.order.confirm_delete', 'Eliminar aquest esborrany de comanda?'))) return;
    setBusyId(comanda.id + '_eliminar');
    const r = await authFetch(`/admin/comandas/${comanda.id}`, { method: 'DELETE' });
    if (!r.ok) {
      const body = await r.json().catch(() => ({}));
      alert(body.detail || t('catalog.delete_error'));
    }
    setBusyId(null);
    onRefresh();
  }

  return (
    <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm overflow-hidden">
      {loading ? (
        <div className="p-12 text-center text-zinc-400 text-sm">{t('common.loading')}</div>
      ) : rows.length === 0 ? (
        <div className="p-12 text-center text-zinc-400 text-sm">
          {hasFilters ? t('purchases.order.no_results_filtered', 'Cap resultat amb aquests filtres.') : t('purchases.order.no_orders', 'Encara no hi ha comandes ni compres.')}
        </div>
      ) : (
        <table className="w-full text-sm">
          <thead className="bg-zinc-50 text-xs text-zinc-500 border-b border-zinc-200">
            <tr>
              <th className="w-8 px-4 py-3" />
              <SortableTh label={t('common.date')} sortKey="fecha" sort={sort} onSort={toggleSort} />
              <SortableTh label={t('purchases.col.origin')} sortKey="origen" sort={sort} onSort={toggleSort}
                filterOptions={distinctValues.origen} selected={filters.origen} onFilterChange={setFilter} />
              <SortableTh label={t('purchases.col.supplier_or_individual', 'Proveïdor / particular')} sortKey="entitat" sort={sort} onSort={toggleSort} />
              <SortableTh label={t('purchases.col.lines', 'Línies')} sortKey="linies" sort={sort} onSort={toggleSort} align="center" />
              <SortableTh label={t('purchases.col.status', 'Estat')} sortKey="estat" sort={sort} onSort={toggleSort}
                filterOptions={distinctValues.estat} selected={filters.estat} onFilterChange={setFilter} />
              <th className="px-4 py-3 text-right font-medium">{t('catalog.col.actions')}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-100">
            {rowsSorted.map(row => row.kind === 'comanda' ? (
              <ComandaRow key={row.id} c={row.raw} expanded={expanded} setExpanded={setExpanded}
                recepcions={comprasProveedor.filter(cp => cp.comanda_id === row.raw.id)}
                busyId={busyId} downloadPdf={downloadPdf} downloadRecepcioPdf={downloadRecepcioPdf}
                enviarPerEmail={enviarPerEmail}
                marcarEnviada={marcarEnviada} onRecepcio={onRecepcio} cancelar={cancelar} eliminar={eliminar} />
            ) : (
              <ParticularRow key={row.id} c={row.raw} expanded={expanded} setExpanded={setExpanded}
                onReturnItem={onReturnItem} />
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

function ComandaRow({ c, expanded, setExpanded, recepcions, busyId, downloadPdf, downloadRecepcioPdf, enviarPerEmail, marcarEnviada, onRecepcio, cancelar, eliminar }) {
  const t = useT();
  return (
    <>
      <tr onClick={() => setExpanded(expanded === c.id ? null : c.id)}
        className="hover:bg-zinc-50 cursor-pointer transition-colors">
        <td className="px-4 py-3 text-zinc-400">
          {expanded === c.id ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        </td>
        <td className="px-4 py-3 text-zinc-500">{new Date(c.date).toLocaleDateString()}</td>
        <td className="px-4 py-3">
          <span className="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium bg-blue-100 text-blue-700">
            {t('purchases.badge.order', 'Comanda')}{c.order_number ? ` ${c.order_number}` : ''}
          </span>
        </td>
        <td className="px-4 py-3 font-medium">{c.proveedor_nombre}</td>
        <td className="px-4 py-3 text-center">
          <span className="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium bg-zinc-100 text-zinc-700">
            {c.lineas?.length ?? 0}
          </span>
        </td>
        <td className="px-4 py-3">
          <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${COMANDA_STATUS_COLOR[c.status]}`}>
            {comandaStatusLabel(t, c.status)}
          </span>
        </td>
        <td className="px-4 py-3 text-right" onClick={e => e.stopPropagation()}>
          <div className="flex items-center justify-end gap-1.5">
            <button onClick={() => downloadPdf(c)} title={t('purchases.action.download_pdf', 'Descarregar PDF')}
              className="p-1.5 text-zinc-400 hover:text-zinc-700 rounded-lg hover:bg-zinc-100">
              <FileText size={14} />
            </button>
            {c.status === 'esborrany' && (
              <button onClick={() => enviarPerEmail(c)} disabled={busyId === c.id + '_enviar'} title={t('purchases.action.send_email', 'Enviar per email')}
                className="p-1.5 text-blue-500 hover:text-blue-700 rounded-lg hover:bg-blue-50 disabled:opacity-50">
                {busyId === c.id + '_enviar' ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
              </button>
            )}
            {c.status === 'esborrany' && (
              <button onClick={() => marcarEnviada(c)} disabled={busyId === c.id + '_marcar'} title={t('purchases.action.mark_sent', 'Marcar com a enviada (manual)')}
                className="p-1.5 text-zinc-400 hover:text-zinc-700 rounded-lg hover:bg-zinc-100 disabled:opacity-50">
                {busyId === c.id + '_marcar' ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} className="opacity-50" />}
              </button>
            )}
            {(c.status === 'enviada' || c.status === 'rebuda_parcial') && (
              <button onClick={() => onRecepcio(c)} title={t('purchases.action.register_reception', 'Registrar recepció')}
                className="p-1.5 text-emerald-600 hover:text-emerald-700 rounded-lg hover:bg-emerald-50">
                <PackageCheck size={14} />
              </button>
            )}
            {c.status !== 'rebuda' && c.status !== 'cancelada' && (
              <button onClick={() => cancelar(c)} disabled={busyId === c.id + '_cancelar'} title={t('common.cancel')}
                className="p-1.5 text-zinc-400 hover:text-red-500 rounded-lg hover:bg-red-50 disabled:opacity-50">
                <Ban size={14} />
              </button>
            )}
            {c.status === 'esborrany' && (
              <button onClick={() => eliminar(c)} disabled={busyId === c.id + '_eliminar'} title={t('catalog.delete')}
                className="p-1.5 text-zinc-300 hover:text-red-500 rounded-lg hover:bg-red-50 disabled:opacity-50">
                <Trash2 size={14} />
              </button>
            )}
          </div>
        </td>
      </tr>
      {expanded === c.id && (
        <tr>
          <td colSpan={7} className="px-4 py-3 bg-blue-50/40 border-b border-blue-100">
            <div className="space-y-1">
              {(c.lineas ?? []).map(l => (
                <div key={l.id} className="flex items-center gap-4 text-sm flex-wrap">
                  <span className="font-semibold text-zinc-900">{l.artista} — {l.titulo}</span>
                  <span className="text-zinc-500">{l.received_quantity}/{l.quantity} {t('purchases.received_suffix', 'rebudes')}</span>
                  {l.estimated_unit_price && (
                    <span className="text-zinc-400">{t('purchases.est_price', 'Preu est.')}: {l.estimated_unit_price} €</span>
                  )}
                </div>
              ))}
            </div>
            {recepcions.length > 0 && (
              <div className="mt-3 pt-3 border-t border-blue-100 space-y-1">
                <div className="text-xs font-semibold text-zinc-500 uppercase tracking-wide">
                  {t('purchases.receptions', 'Recepcions')} ({recepcions.length})
                </div>
                {recepcions.map(r => (
                  <div key={r.id} className="flex items-center gap-3 text-sm flex-wrap">
                    <span className="text-zinc-500">{new Date(r.date).toLocaleDateString()}</span>
                    <span className="text-zinc-400">{r.delivery_note_number ? `${t('purchases.albaran', 'Albarà')} ${r.delivery_note_number}` : t('purchases.no_albaran', 'Sense núm. albarà')}</span>
                    <span className="text-zinc-400">· {r.items?.length ?? 0} {t('purchases.copies', 'exemplars')}</span>
                    {r.despesa_estat ? (
                      <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${DESPESA_ESTAT_COLOR[r.despesa_estat] ?? ''}`}>
                        {t('purchases.col.invoice')} {despesaEstatLabel(t, r.despesa_estat)}
                      </span>
                    ) : (
                      <span className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium bg-zinc-100 text-zinc-500">
                        {t('purchases.not_invoiced', 'Sense facturar')}
                      </span>
                    )}
                    <button onClick={() => downloadRecepcioPdf(r)} title={t('purchases.action.download_reception_list', 'Descarregar llista de recepció (per etiquetes de preu)')}
                      className="p-1 text-zinc-400 hover:text-zinc-700 rounded hover:bg-zinc-100">
                      <FileText size={13} />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </td>
        </tr>
      )}
    </>
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
        <td className="px-4 py-3">
          <span className="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium bg-amber-100 text-amber-700">
            {t('purchases.type.individual')}
          </span>
        </td>
        <td className="px-4 py-3 font-medium">{c.individual_name ?? c.user_nom ?? '—'}</td>
        <td className="px-4 py-3 text-center">
          <span className="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium bg-zinc-100 text-zinc-700">
            {c.items?.length ?? 0}
          </span>
        </td>
        <td className="px-4 py-3">
          <span className="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium bg-emerald-100 text-emerald-700">
            {comandaStatusLabel(t, 'rebuda')}
          </span>
        </td>
        <td className="px-4 py-3" />
      </tr>
      {expanded === c.id && (
        <tr>
          <td colSpan={7} className="px-4 py-3 bg-amber-50/40 border-b border-amber-100">
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

// ---- SolicitudsTab -------------------------------------------------------------
// "Sol·licitud de compra": llista de discos a comprar sense proveïdor triat
// encara. Es pot deixar oberta, cancel·lar, o "resoldre" (repartint línies
// cap a una Comanda real d'un proveïdor concret).

function SolicitudsTab({ solicitudes, loading, proveedores, expanded, setExpanded, onRefresh }) {
  const t = useT();
  const [busyId, setBusyId] = useState(null);
  const [resolvingEstocLinea, setResolvingEstocLinea] = useState(null);
  const [seleccio, setSeleccio] = useState(() => new Set());
  const [resolvingLineas, setResolvingLineas] = useState(null);

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
    onRefresh();
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
    onRefresh();
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
    onRefresh();
  }

  return (
    <div className="space-y-4">
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
        )}

        {resolvingEstocLinea && (
          <ResoldreEstocModal
            linea={resolvingEstocLinea}
            onClose={() => setResolvingEstocLinea(null)}
            onSaved={() => { setResolvingEstocLinea(null); onRefresh(); }} />
        )}
      </div>

      {resolvingLineas && (
        <ResoldreSolicitudModal
          lineas={resolvingLineas} proveedores={proveedores}
          onClose={() => setResolvingLineas(null)}
          onSaved={() => { setResolvingLineas(null); setSeleccio(new Set()); onRefresh(); }} />
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

// ---- BuscadorProveidorTab -------------------------------------------------------
// Vista per defecte (sense necessitat de cercar) de l'històric de compres:
// llista de proveïdors desplegable (quants discos, quan la darrera) i un
// detall complet a sota. La cerca filtra totes dues parts alhora.

function BuscadorProveidorTab({ onRefresh }) {
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
      onRefresh?.();
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
    <div className="space-y-4">
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
          )}
        </>
      )}
    </div>
  );
}

// ---- RefillSugerenciesModal ------------------------------------------------------
// Previsualització dels candidats a reposició (estoc baix + es venen + sense
// comanda oberta). No crea res fins que es confirma: llavors genera una
// SolicitudCompra amb origen='refill_stock' amb les línies seleccionades.

const TENDENCIA_ICON = { accelerant: TrendingUp, frenant: TrendingDown, estable: Minus };
const TENDENCIA_COLOR = { accelerant: 'text-emerald-600', frenant: 'text-red-500', estable: 'text-zinc-400' };

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

// ---- ResumTab (dashboard de compres) -------------------------------------------

function fmtEur(n) {
  return `${parseFloat(n).toLocaleString('ca-ES', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} €`;
}

function costCompra(c) {
  return (c.items ?? []).reduce((acc, it) => acc + parseFloat(it.acquisition_cost || 0), 0);
}

function pendentQty(c) {
  return (c.lineas ?? []).reduce((acc, l) => acc + Math.max(0, l.quantity - l.received_quantity), 0);
}

function ResumTab({ proveedores }) {
  const t = useT();
  const [stats, setStats] = useState(null);
  const [comandesPendents, setComandesPendents] = useState([]);
  const [comprasPendents, setComprasPendents] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      setLoading(true);
      const [statsRes, esborranyRes, enviadaRes, parcialRes, comprasRes] = await Promise.all([
        authFetch('/admin/compras/stats'),
        authFetch('/admin/comandas?status=esborrany'),
        authFetch('/admin/comandas?status=enviada'),
        authFetch('/admin/comandas?status=rebuda_parcial'),
        authFetch('/admin/compras?tipo=proveedor&sense_facturar=true'),
      ]);
      if (statsRes.ok) setStats(await statsRes.json());
      const comandaLists = await Promise.all(
        [esborranyRes, enviadaRes, parcialRes].map(r => (r.ok ? r.json() : []))
      );
      setComandesPendents(comandaLists.flat().sort((a, b) => new Date(a.date) - new Date(b.date)));
      if (comprasRes.ok) {
        const data = await comprasRes.json();
        setComprasPendents(data.sort((a, b) => new Date(a.date) - new Date(b.date)));
      }
      setLoading(false);
    })();
  }, []);

  if (loading) {
    return <div className="p-12 text-center text-zinc-400 text-sm">{t('common.loading')}</div>;
  }
  if (!stats) {
    return <div className="p-12 text-center text-zinc-400 text-sm">{t('purchases.resum.load_error', "No s'han pogut carregar les dades.")}</div>;
  }

  const maxProveidor = stats.top_proveidors[0]?.total ?? 0;
  const proveedorNom = Object.fromEntries((proveedores || []).map(p => [p.id, p.name]));

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatTile label={t('purchases.resum.spend_month', 'Despesa aquest mes')} value={fmtEur(stats.total_mes)} />
        <StatTile label={t('purchases.resum.spend_quarter', 'Despesa aquest trimestre')} value={fmtEur(stats.total_trimestre)} />
        <StatTile label={t('purchases.resum.spend_year', 'Despesa aquest any')} value={fmtEur(stats.total_any)} />
        <StatTile label={t('purchases.resum.orders_pending', 'Comandes pendents de rebre')} value={stats.comandes_pendents}
          accent={stats.comandes_pendents > 0} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm overflow-hidden">
          <div className="px-5 py-3 border-b border-zinc-200">
            <div className="text-sm font-semibold text-zinc-700">{t('purchases.resum.orders_pending', 'Comandes pendents de rebre')}</div>
          </div>
          {comandesPendents.length === 0 ? (
            <div className="p-5 text-sm text-zinc-400">{t('purchases.resum.no_pending_orders', 'Cap comanda pendent de rebre.')}</div>
          ) : (
            <div className="divide-y divide-zinc-100 max-h-72 overflow-y-auto">
              {comandesPendents.map(c => (
                <div key={c.id} className="px-5 py-2.5 text-sm">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-medium text-zinc-900 truncate">{c.proveedor_nombre}</span>
                    <span className={`shrink-0 inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${COMANDA_STATUS_COLOR[c.status]}`}>
                      {comandaStatusLabel(t, c.status)}
                    </span>
                  </div>
                  <div className="text-xs text-zinc-400 mt-0.5">
                    {new Date(c.date).toLocaleDateString()}
                    {c.order_number ? ` · ${c.order_number}` : ''} · {pendentQty(c)} {t('purchases.resum.pending_records', 'discs pendents')}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm overflow-hidden">
          <div className="px-5 py-3 border-b border-zinc-200 flex items-center justify-between">
            <div className="text-sm font-semibold text-zinc-700">{t('purchases.resum.receptions_pending_invoice', 'Recepcions pendents de facturar')}</div>
            <span className="text-xs text-zinc-400">{fmtEur(stats.sense_facturar_import)}</span>
          </div>
          {comprasPendents.length === 0 ? (
            <div className="p-5 text-sm text-zinc-400">{t('purchases.resum.no_pending_receptions', 'Cap recepció pendent de facturar.')}</div>
          ) : (
            <div className="divide-y divide-zinc-100 max-h-72 overflow-y-auto">
              {comprasPendents.map(c => (
                <div key={c.id} className="px-5 py-2.5 text-sm">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-medium text-zinc-900 truncate">
                      {c.proveedor_id ? (proveedorNom[c.proveedor_id] ?? '—') : (c.individual_name ?? '—')}
                    </span>
                    <span className="shrink-0 font-medium text-zinc-900">{fmtEur(costCompra(c))}</span>
                  </div>
                  <div className="text-xs text-zinc-400 mt-0.5">
                    {new Date(c.date).toLocaleDateString()}
                    {' · '}{c.delivery_note_number ? `${t('purchases.albaran', 'Albarà')} ${c.delivery_note_number}` : t('purchases.no_albaran', 'Sense núm. albarà')}
                    {' · '}{c.items?.length ?? 0} {t('purchases.copies', 'exemplars')}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm p-5">
          <div className="text-sm font-semibold text-zinc-700 mb-3">{t('purchases.resum.top_suppliers', 'Top proveïdors (últims 12 mesos)')}</div>
          {stats.top_proveidors.length === 0 ? (
            <div className="text-sm text-zinc-400">{t('purchases.resum.no_data', 'Encara no hi ha dades.')}</div>
          ) : (
            <div className="space-y-2.5">
              {stats.top_proveidors.map(p => {
                const pct = maxProveidor > 0 ? (parseFloat(p.total) / parseFloat(maxProveidor)) * 100 : 0;
                return (
                  <div key={p.proveedor_id}>
                    <div className="flex items-center justify-between text-xs text-zinc-600 mb-1 gap-2">
                      <span className="font-medium truncate">{p.nombre}</span>
                      <span className="text-zinc-400 shrink-0">{fmtEur(p.total)}</span>
                    </div>
                    <div className="h-1.5 rounded-full bg-zinc-100 overflow-hidden">
                      <div className="h-full rounded-full bg-amber-500" style={{ width: `${pct}%` }} />
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      <DespesaMensualChart serie={stats.serie_mensual} />
    </div>
  );
}

function StatTile({ label, value, accent }) {
  return (
    <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm p-5">
      <div className="text-xs font-medium text-zinc-500 mb-1">{label}</div>
      <div className={`text-2xl font-bold ${accent ? 'text-amber-600' : 'text-zinc-900'}`}>{value}</div>
    </div>
  );
}

const MESOS_CURT_FALLBACK = ['Gen', 'Feb', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Oct', 'Nov', 'Des'];

function DespesaMensualChart({ serie }) {
  const t = useT();
  const [hover, setHover] = useState(null);

  const mesosCurt = MESOS_CURT_FALLBACK.map((fallback, i) => t(`purchases.chart.month.${i}`, fallback));
  const data = serie.map(s => ({
    mes: s.mes,
    label: mesosCurt[parseInt(s.mes.split('-')[1], 10) - 1],
    proveidor: parseFloat(s.proveidor),
    particular: parseFloat(s.particular),
  }));
  const max = Math.max(1, ...data.map(d => Math.max(d.proveidor, d.particular)));
  const W = 760, H = 220, padL = 46, padB = 26, padT = 10, padR = 10;
  const plotW = W - padL - padR, plotH = H - padT - padB;
  const groupW = data.length ? plotW / data.length : plotW;
  const barW = Math.min(22, groupW / 2 - 6);
  const y = v => padT + plotH - (v / max) * plotH;
  const ticks = [0, max / 2, max];

  const fmtTick = v => (v >= 1000 ? `${(v / 1000).toFixed(1)}k€` : `${Math.round(v)}€`);

  return (
    <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm p-5">
      <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
        <div className="text-sm font-semibold text-zinc-700">{t('purchases.resum.monthly_spend', 'Despesa mensual (últims 12 mesos)')}</div>
        <div className="flex items-center gap-4 text-xs text-zinc-500">
          <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-blue-600" /> {t('purchases.type.supplier')}</span>
          <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-amber-500" /> {t('purchases.type.individual')}</span>
        </div>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-56" onMouseLeave={() => setHover(null)}>
        {ticks.map((tickVal, i) => (
          <g key={i}>
            <line x1={padL} x2={W - padR} y1={y(tickVal)} y2={y(tickVal)} stroke="#e4e4e7" strokeWidth={1} />
            <text x={padL - 6} y={y(tickVal)} textAnchor="end" dominantBaseline="middle" fill="#a1a1aa" fontSize={10}>
              {fmtTick(tickVal)}
            </text>
          </g>
        ))}
        {data.map((d, i) => {
          const gx = padL + i * groupW;
          const bx1 = gx + groupW / 2 - barW - 1;
          const bx2 = gx + groupW / 2 + 1;
          const dimmed = hover !== null && hover !== i;
          return (
            <g key={d.mes} onMouseEnter={() => setHover(i)}>
              <rect x={gx} y={padT} width={groupW} height={plotH} fill="transparent" />
              <rect x={bx1} y={y(d.proveidor)} width={barW} height={Math.max(0, y(0) - y(d.proveidor))}
                rx={3} fill="#2563eb" opacity={dimmed ? 0.35 : 1} />
              <rect x={bx2} y={y(d.particular)} width={barW} height={Math.max(0, y(0) - y(d.particular))}
                rx={3} fill="#f59e0b" opacity={dimmed ? 0.35 : 1} />
              <text x={gx + groupW / 2} y={H - padB + 14} textAnchor="middle" fill="#a1a1aa" fontSize={10}>
                {d.label}
              </text>
            </g>
          );
        })}
      </svg>
      {hover !== null && (
        <div className="text-xs text-zinc-600 bg-zinc-50 rounded-lg px-3 py-2 inline-flex items-center gap-3">
          <span className="font-semibold text-zinc-900">{data[hover].mes}</span>
          <span>{t('purchases.type.supplier')}: {fmtEur(data[hover].proveidor)}</span>
          <span>{t('purchases.type.individual')}: {fmtEur(data[hover].particular)}</span>
        </div>
      )}
    </div>
  );
}

// ---- NovaComandaModal ---------------------------------------------------------

function NovaComandaModal({ proveedores, onClose, onSaved }) {
  const t = useT();
  const discogsEnabled = useDiscogsEnabled();
  const vertical = useTenantVertical();
  const [proveedorId, setProveedorId] = useState('');
  const [fecha, setFecha] = useState(new Date().toISOString().slice(0, 10));
  const [notas, setNotas] = useState('');
  const [lineas, setLineas] = useState([]);
  const [discogsQ, setDiscogsQ] = useState('');
  const [discogsRes, setDiscogsRes] = useState([]);
  const [searchingDiscogs, setSearchingDiscogs] = useState(false);
  const [resolving, setResolving] = useState(false);
  const [manualMode, setManualMode] = useState(false);
  const [manualForm, setManualForm] = useState({ artista: '', titulo: '', sello: '', formato: 'LP', anio: '' });
  const [saving, setSaving] = useState(false);
  const [importingCsv, setImportingCsv] = useState(false);
  const [csvErrors, setCsvErrors] = useState([]);
  const discogsDebounce = useRef(null);
  const csvInputRef = useRef(null);

  async function handleDownloadTemplate() {
    const r = await authFetch('/admin/comandas/plantilla.csv');
    if (!r.ok) return;
    const blob = await r.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'plantilla_comanda.csv';
    a.click();
    URL.revokeObjectURL(url);
  }

  async function handleCsvFile(file) {
    if (!file) return;
    setImportingCsv(true);
    setCsvErrors([]);
    try {
      const formData = new FormData();
      formData.append('file', file);
      const r = await authFetch('/admin/comandas/resolver-csv', { method: 'POST', body: formData });
      if (!r.ok) { setCsvErrors([{ motiu: t('purchases.order_modal.csv_read_error', 'No s\'ha pogut llegir el fitxer.') }]); return; }
      const data = await r.json();
      setLineas(prev => [
        ...prev,
        ...data.lineas.map(l => ({
          release_id: l.release_id, artista: l.artista, titulo: l.titulo, existing: true,
          cantidad: l.quantity, precio_unitario_estimado: l.estimated_unit_price ?? '',
        })),
      ]);
      setCsvErrors(data.errors ?? []);
    } finally {
      setImportingCsv(false);
      if (csvInputRef.current) csvInputRef.current.value = '';
    }
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
      addLinea(rel);
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
      addLinea(rel);
      setManualForm({ artista: '', titulo: '', sello: '', formato: 'LP', anio: '' });
      setManualMode(false);
    } finally {
      setResolving(false);
    }
  }

  function addLinea(rel) {
    setLineas(prev => [...prev, { release_id: rel.id, artista: rel.artista, titulo: rel.titulo, existing: rel.existing, cantidad: 1, precio_unitario_estimado: '' }]);
  }

  function upd(idx, k, v) { setLineas(prev => prev.map((l, i) => i === idx ? { ...l, [k]: v } : l)); }

  async function save(e) {
    e.preventDefault();
    setSaving(true);
    const payload = {
      proveedor_id: proveedorId,
      date: new Date(fecha).toISOString(),
      notes: notas || null,
      lineas: lineas.map(l => ({
        release_id: l.release_id,
        quantity: parseInt(l.cantidad, 10),
        estimated_unit_price: l.precio_unitario_estimado ? parseFloat(l.precio_unitario_estimado) : null,
      })),
    };
    const r = await authFetch('/admin/comandas', { method: 'POST', body: JSON.stringify(payload) });
    setSaving(false);
    if (r.ok) onSaved();
  }

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-start justify-center p-4 overflow-y-auto">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-3xl my-8">
        <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-200">
          <h3 className="text-lg font-bold text-zinc-900">{t('purchases.btn.new_order', 'Nova comanda')}</h3>
          <button onClick={onClose} className="text-zinc-400 hover:text-zinc-600 p-1 rounded-lg hover:bg-zinc-100"><X size={20} /></button>
        </div>

        <form onSubmit={save} className="p-6 space-y-5">
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
              <label className="block text-sm font-medium text-zinc-700 mb-1">{t('common.notes')}</label>
              <input value={notas} onChange={e => setNotas(e.target.value)}
                className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
            </div>
          </div>
          <p className="text-xs text-zinc-400">{t('purchases.order_modal.auto_number_hint', 'El número de comanda es genera automàticament en crear-la.')}</p>

          <div className="border border-zinc-200 rounded-xl p-4 space-y-3">
            <div className="text-sm font-semibold text-zinc-700">{t('purchases.order_modal.records_requested', 'Discos demanats')}</div>
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
            <div className="flex items-center gap-3 flex-wrap">
              <button type="button" onClick={() => setManualMode(m => !m)}
                className="text-xs text-amber-600 hover:text-amber-700 font-medium">
                {manualMode ? t('common.cancel') : t('purchases.add_manual_toggle', '+ Afegir disc a mà')}
              </button>
              <button type="button" onClick={() => csvInputRef.current?.click()} disabled={importingCsv}
                className="flex items-center gap-1 text-xs text-zinc-600 hover:text-zinc-800 font-medium disabled:opacity-50">
                {importingCsv ? <Loader2 size={12} className="animate-spin" /> : <FileSpreadsheet size={12} />}
                {t('purchases.order_modal.import_csv', 'Importar CSV')}
              </button>
              <button type="button" onClick={handleDownloadTemplate}
                className="flex items-center gap-1 text-xs text-zinc-400 hover:text-zinc-600">
                <Download size={12} /> {t('purchases.order_modal.template', 'Plantilla')}
              </button>
              <input ref={csvInputRef} type="file" accept=".csv" className="hidden"
                onChange={e => handleCsvFile(e.target.files?.[0])} />
            </div>
            )}

            {csvErrors.length > 0 && (
              <div className="border border-amber-200 bg-amber-50 rounded-lg p-2 text-xs text-amber-700 space-y-0.5">
                {csvErrors.map((e, i) => <div key={i}>{t('purchases.order_modal.csv_row', 'Fila')} {e.fila ?? '?'}: {e.motiu}</div>)}
              </div>
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
                      <input type="number" min="1" step="1" value={l.cantidad} onChange={e => upd(idx, 'cantidad', e.target.value)} required
                        className="w-20 border border-zinc-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-zinc-900" />
                    </div>
                    <div>
                      <label className="block text-xs text-zinc-500 mb-1">{t('purchases.order_modal.estimated_unit_price', 'Preu unitari estimat')}</label>
                      <input type="number" step="0.01" min="0" value={l.precio_unitario_estimado} onChange={e => upd(idx, 'precio_unitario_estimado', e.target.value)}
                        className="w-28 border border-zinc-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-zinc-900" />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="flex justify-end gap-3">
            <Button type="button" variant="secondary" onClick={onClose}>{t('common.cancel')}</Button>
            <Button type="submit" disabled={saving || lineas.length === 0 || !proveedorId}>
              {saving ? t('common.saving') : `${t('purchases.request.create_order', 'Crear comanda')} (${lineas.length})`}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ---- RecepcioModal -------------------------------------------------------------

function RecepcioModal({ comanda, onClose, onSaved }) {
  const t = useT();
  const pendents = (comanda.lineas ?? []).filter(l => l.received_quantity < l.quantity);
  const [fecha, setFecha] = useState(new Date().toISOString().slice(0, 10));
  const [numAlbaran, setNumAlbaran] = useState('');
  const [notas, setNotas] = useState('');
  // { [lineaId]: [{ precio, condicion, coste_adquisicion, estado_disco, estado_funda }, ...] }
  const [itemsPorLinea, setItemsPorLinea] = useState({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  // Marge/IVA per defecte de cada condició, per suggerir preu (sempre editable a mà després).
  const [defectesPreu, setDefectesPreu] = useState({ nou: null, segona_ma: null });
  useEffect(() => {
    (async () => {
      const [mRes, ivaRes] = await Promise.all([
        authFetch('/admin/marges?nomes_actius=true'),
        authFetch('/admin/tipus-iva?nomes_actius=true'),
      ]);
      const marges = mRes.ok ? await mRes.json() : [];
      const tipusIva = ivaRes.ok ? await ivaRes.json() : [];
      const margeNou = marges.find(m => m.default_new);
      const margeSegonaMa = marges.find(m => m.default_used);
      const ivaNou = tipusIva.find(iv => iv.default_new);
      const ivaSegonaMa = tipusIva.find(iv => iv.default_used);
      setDefectesPreu({
        nou: margeNou && ivaNou ? { marge: parseFloat(margeNou.percentage), iva: parseFloat(ivaNou.percentage) } : null,
        segona_ma: margeSegonaMa && ivaSegonaMa ? { marge: parseFloat(margeSegonaMa.percentage), iva: parseFloat(ivaSegonaMa.percentage) } : null,
      });
    })();
  }, []);

  function unitatsLinea(copias) {
    // segona_ma sempre val 1; nou pot representar-ne diverses en una sola entrada.
    return copias.reduce((sum, c) => sum + (c.condicion === 'nou' ? (parseInt(c.cantidad, 10) || 1) : 1), 0);
  }

  function addCopiaRebuda(linea) {
    setItemsPorLinea(prev => {
      const actuales = prev[linea.id] ?? [];
      const pendent = linea.quantity - linea.received_quantity;
      if (unitatsLinea(actuales) >= pendent) return prev;
      return { ...prev, [linea.id]: [...actuales, { precio: linea.estimated_unit_price ?? '', condicion: 'nou', coste_adquisicion: '', estado_disco: '', estado_funda: '', cantidad: 1 }] };
    });
  }

  function desglossPreu(copia) {
    const defecte = defectesPreu[copia.condicion];
    const coste = parseFloat(copia.coste_adquisicion);
    if (!defecte || !coste) return null;
    const importMarge = coste * (defecte.marge / 100);
    const baseAmbMarge = coste + importMarge;
    const importIva = baseAmbMarge * (defecte.iva / 100);
    return { importMarge, importIva, preuSuggerit: baseAmbMarge + importIva };
  }

  function calcularPreu(lineaId, idx, copia) {
    const desglos = desglossPreu(copia);
    if (!desglos) return;
    updCopia(lineaId, idx, 'precio', desglos.preuSuggerit.toFixed(2));
  }

  function updCopia(lineaId, idx, k, v) {
    setItemsPorLinea(prev => ({
      ...prev,
      [lineaId]: prev[lineaId].map((c, i) => i === idx ? { ...c, [k]: v } : c),
    }));
  }

  function removeCopia(lineaId, idx) {
    setItemsPorLinea(prev => ({ ...prev, [lineaId]: prev[lineaId].filter((_, i) => i !== idx) }));
  }

  const totalCopias = Object.values(itemsPorLinea).reduce((acc, arr) => acc + unitatsLinea(arr), 0);

  async function save(e) {
    e.preventDefault();
    setError('');
    const items = [];
    for (const [lineaId, copias] of Object.entries(itemsPorLinea)) {
      for (const c of copias) {
        if (!c.precio) { setError(t('purchases.reception_modal.missing_price', 'Falta el preu de venda en alguna còpia.')); return; }
        items.push({
          comanda_linea_id: lineaId,
          price: parseFloat(c.precio),
          condition: c.condicion,
          acquisition_cost: c.coste_adquisicion ? parseFloat(c.coste_adquisicion) : null,
          estado_disco: c.condicion === 'nou' ? null : (c.estado_disco || null),
          estado_funda: c.condicion === 'nou' ? null : (c.estado_funda || null),
          quantity: c.condicion === 'nou' ? (parseInt(c.cantidad, 10) || 1) : 1,
        });
      }
    }
    if (items.length === 0) { setError(t('purchases.reception_modal.no_copies', 'Afegeix com a mínim una còpia rebuda.')); return; }

    setSaving(true);
    const r = await authFetch(`/admin/comandas/${comanda.id}/recepcio`, {
      method: 'POST',
      body: JSON.stringify({ date: new Date(fecha).toISOString(), delivery_note_number: numAlbaran || null, notes: notas || null, items }),
    });
    setSaving(false);
    if (!r.ok) {
      const body = await r.json().catch(() => ({}));
      setError(body.detail || t('purchases.reception_modal.save_error', 'No s\'ha pogut registrar la recepció.'));
      return;
    }
    onSaved();
  }

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-start justify-center p-4 overflow-y-auto">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-3xl my-8">
        <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-200">
          <h3 className="text-lg font-bold text-zinc-900">{t('purchases.reception_modal.title', 'Registrar recepció')} — {comanda.proveedor_nombre}</h3>
          <button onClick={onClose} className="text-zinc-400 hover:text-zinc-600 p-1 rounded-lg hover:bg-zinc-100"><X size={20} /></button>
        </div>

        <form onSubmit={save} className="p-6 space-y-5">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-zinc-700 mb-1">{t('purchases.reception_modal.albaran_date', "Data de l'albarà")}</label>
              <input type="date" value={fecha} onChange={e => setFecha(e.target.value)} required
                className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
            </div>
            <div>
              <label className="block text-sm font-medium text-zinc-700 mb-1">
                {t('purchases.reception_modal.albaran_num', 'Núm. albarà')} <span className="text-zinc-400 font-normal">{t('common.optional', '(opcional)')}</span>
              </label>
              <input value={numAlbaran} onChange={e => setNumAlbaran(e.target.value)}
                placeholder={t('purchases.reception_modal.albaran_ph', 'Referència del proveïdor, no és la factura')}
                className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
            </div>
          </div>
          <p className="text-xs text-zinc-400 -mt-2">
            {t('purchases.reception_modal.invoice_hint', 'La factura es registra a part un cop arribi, des de "Facturar recepcions" — pot agrupar diverses recepcions.')}
          </p>

          <div className="space-y-3">
            {pendents.map(linea => {
              const copias = itemsPorLinea[linea.id] ?? [];
              const pendent = linea.quantity - linea.received_quantity;
              return (
                <div key={linea.id} className="border border-zinc-200 rounded-xl p-4 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-semibold text-zinc-900">{linea.artista} — {linea.titulo}</span>
                    <span className="text-xs text-zinc-500">{unitatsLinea(copias)}/{pendent} {t('purchases.pending', 'pendents')}</span>
                  </div>
                  {copias.map((c, idx) => (
                    <div key={idx} className="flex flex-wrap items-end gap-3 p-2 bg-zinc-50 rounded-lg">
                      <div>
                        <label className="block text-xs text-zinc-500 mb-1">{t('common.condition')}</label>
                        <select value={c.condicion} onChange={e => updCopia(linea.id, idx, 'condicion', e.target.value)}
                          className="border border-zinc-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-zinc-900 bg-white">
                          <option value="nou">{t('common.condition.new')}</option>
                          <option value="segona_ma">{t('purchases.condition.used', 'Segona mà')}</option>
                        </select>
                      </div>
                      {c.condicion === 'nou' && (
                        <div>
                          <label className="block text-xs text-zinc-500 mb-1">{t('purchases.reception_modal.units', 'Unitats')}</label>
                          <input type="number" step="1" min="1" max={pendent - unitatsLinea(copias.filter((_, i) => i !== idx))}
                            value={c.cantidad} onChange={e => updCopia(linea.id, idx, 'cantidad', e.target.value)}
                            title={t('purchases.reception_modal.units_hint', 'Aquesta entrada representa vàries unitats idèntiques (mateix cost i preu)')}
                            className="w-16 border border-zinc-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-zinc-900" />
                        </div>
                      )}
                      <div>
                        <label className="block text-xs text-zinc-500 mb-1">{t('purchases.cost_short', 'Cost')} {c.condicion === 'nou' ? t('purchases.reception_modal.per_unit', '(per unitat)') : ''}</label>
                        <input type="number" step="0.01" min="0" value={c.coste_adquisicion} onChange={e => updCopia(linea.id, idx, 'coste_adquisicion', e.target.value)}
                          className="w-24 border border-zinc-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-zinc-900" />
                      </div>
                      <div>
                        <label className="block text-xs text-zinc-500 mb-1">{t('purchases.reception_modal.sale_price', 'Preu venda')}</label>
                        <div className="flex gap-1">
                          <input type="number" step="0.01" min="0" value={c.precio} onChange={e => updCopia(linea.id, idx, 'precio', e.target.value)} required
                            className="w-24 border border-zinc-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-zinc-900" />
                          <button type="button" onClick={() => calcularPreu(linea.id, idx, c)}
                            disabled={!defectesPreu[c.condicion] || !c.coste_adquisicion}
                            title={t('purchases.reception_modal.calculate_hint', 'Calcula el preu a partir del cost + marge i IVA per defecte')}
                            className="text-xs text-zinc-400 hover:text-zinc-700 border border-zinc-300 rounded-lg px-2 disabled:opacity-30">
                            {t('purchases.reception_modal.calculate', 'Calcular')}
                          </button>
                        </div>
                        {(() => {
                          const desglos = desglossPreu(c);
                          if (!desglos) return null;
                          return (
                            <div className="text-[10px] text-zinc-400 mt-0.5 whitespace-nowrap">
                              {t('purchases.margin_capitalized', 'Marge')} {desglos.importMarge.toFixed(2)}€ · IVA {desglos.importIva.toFixed(2)}€
                            </div>
                          );
                        })()}
                      </div>
                      {c.condicion === 'segona_ma' && vertical === 'records' && <>
                        <div>
                          <label className="block text-xs text-zinc-500 mb-1">{t('purchases.grading.disc', 'Grading disc')}</label>
                          <select value={c.estado_disco} onChange={e => updCopia(linea.id, idx, 'estado_disco', e.target.value)}
                            className="border border-zinc-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-zinc-900 bg-white">
                            <option value="">—</option>
                            {GRADINGS.map(g => <option key={g} value={g}>{g.split(' (')[0]}</option>)}
                          </select>
                        </div>
                        <div>
                          <label className="block text-xs text-zinc-500 mb-1">{t('purchases.grading.sleeve', 'Grading funda')}</label>
                          <select value={c.estado_funda} onChange={e => updCopia(linea.id, idx, 'estado_funda', e.target.value)}
                            className="border border-zinc-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-zinc-900 bg-white">
                            <option value="">—</option>
                            {GRADINGS.map(g => <option key={g} value={g}>{g.split(' (')[0]}</option>)}
                          </select>
                        </div>
                      </>}
                      <button type="button" onClick={() => removeCopia(linea.id, idx)}
                        className="text-zinc-400 hover:text-red-500 transition-colors pb-1.5">
                        <Trash2 size={15} />
                      </button>
                    </div>
                  ))}
                  <button type="button" onClick={() => addCopiaRebuda(linea)} disabled={unitatsLinea(copias) >= pendent}
                    className="text-xs text-amber-600 hover:text-amber-700 font-medium disabled:opacity-40">
                    + {t('purchases.reception_modal.add_copy', 'Afegir còpia rebuda')}
                  </button>
                </div>
              );
            })}
          </div>

          {error && <p className="text-red-500 text-sm">{error}</p>}
          <div className="flex justify-end gap-3">
            <Button type="button" variant="secondary" onClick={onClose}>{t('common.cancel')}</Button>
            <Button type="submit" disabled={saving || totalCopias === 0}>
              {saving ? t('common.saving') : `${t('purchases.reception_modal.register', 'Registrar recepció')} (${totalCopias})`}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ---- FacturarRecepcionsModal ---------------------------------------------------
// Pas de "factura contra albarà": tria un proveïdor, mostra les recepcions
// (Compra) encara sense facturar i genera una única Despesa que les agrupa.

function FacturarRecepcionsModal({ proveedores, onClose, onSaved }) {
  const t = useT();
  const [proveedorId, setProveedorId] = useState('');
  const [compras, setCompras] = useState([]);
  const [loadingCompras, setLoadingCompras] = useState(false);
  const [selected, setSelected] = useState({}); // { compraId: bool }
  const [numFactura, setNumFactura] = useState('');
  const [dataFactura, setDataFactura] = useState(new Date().toISOString().slice(0, 10));
  const [notes, setNotes] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  async function handleProveedorChange(id) {
    setProveedorId(id);
    setSelected({});
    setCompras([]);
    if (!id) return;
    setLoadingCompras(true);
    try {
      const r = await authFetch(`/admin/compras?tipo=proveedor&proveedor_id=${id}&sense_facturar=true`);
      const data = r.ok ? await r.json() : [];
      setCompras(data);
      setSelected(Object.fromEntries(data.map(c => [c.id, true])));
    } finally {
      setLoadingCompras(false);
    }
  }

  const compraIds = Object.entries(selected).filter(([, v]) => v).map(([k]) => k);
  const total = compras.filter(c => selected[c.id]).reduce((acc, c) => acc + costCompra(c), 0);

  async function save(e) {
    e.preventDefault();
    setError('');
    if (compraIds.length === 0) { setError(t('purchases.invoice_modal.select_reception', 'Selecciona com a mínim una recepció.')); return; }
    setSaving(true);
    const r = await authFetch('/admin/despeses/des-de-compres', {
      method: 'POST',
      body: JSON.stringify({
        compra_ids: compraIds,
        num_factura: numFactura || null,
        data_factura: dataFactura || null,
        notes: notes || null,
      }),
    });
    setSaving(false);
    if (!r.ok) {
      const body = await r.json().catch(() => ({}));
      setError(body.detail || t('purchases.invoice_modal.save_error', 'No s\'ha pogut registrar la factura.'));
      return;
    }
    onSaved();
  }

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-start justify-center p-4 overflow-y-auto">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl my-8">
        <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-200">
          <h3 className="text-lg font-bold text-zinc-900">{t('purchases.btn.invoice_receptions', 'Facturar recepcions')}</h3>
          <button onClick={onClose} className="text-zinc-400 hover:text-zinc-600 p-1 rounded-lg hover:bg-zinc-100"><X size={20} /></button>
        </div>

        <form onSubmit={save} className="p-6 space-y-5">
          <div>
            <label className="block text-sm font-medium text-zinc-700 mb-1">{t('purchases.type.supplier')}</label>
            <select value={proveedorId} onChange={e => handleProveedorChange(e.target.value)} required
              className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900 bg-white">
              <option value="">{t('purchases.invoice_modal.select_supplier', 'Selecciona un proveïdor...')}</option>
              {proveedores.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
          </div>

          {loadingCompras ? (
            <div className="text-sm text-zinc-400 text-center py-4">{t('purchases.invoice_modal.loading_receptions', 'Carregant recepcions...')}</div>
          ) : proveedorId && compras.length === 0 ? (
            <div className="text-sm text-zinc-400 text-center py-4">{t('purchases.invoice_modal.no_pending_receptions', 'Aquest proveïdor no té recepcions pendents de facturar.')}</div>
          ) : compras.length > 0 && (
            <div className="border border-zinc-200 rounded-xl divide-y divide-zinc-100">
              {compras.map(c => (
                <label key={c.id} className="flex items-center gap-3 px-4 py-2.5 text-sm cursor-pointer hover:bg-zinc-50">
                  <input type="checkbox" checked={!!selected[c.id]}
                    onChange={e => setSelected(prev => ({ ...prev, [c.id]: e.target.checked }))}
                    className="rounded border-zinc-300 text-amber-600 focus:ring-zinc-900" />
                  <span className="text-zinc-500">{new Date(c.date).toLocaleDateString()}</span>
                  <span className="text-zinc-400">{c.delivery_note_number ? `${t('purchases.albaran', 'Albarà')} ${c.delivery_note_number}` : t('purchases.no_albaran', 'Sense núm. albarà')}</span>
                  <span className="text-zinc-400">· {c.items?.length ?? 0} {t('purchases.copies', 'exemplars')}</span>
                  <span className="ml-auto font-medium text-zinc-900">{costCompra(c).toFixed(2)} €</span>
                </label>
              ))}
            </div>
          )}

          {compras.length > 0 && (
            <>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-zinc-700 mb-1">{t('purchases.invoice_modal.invoice_num', 'Núm. factura')}</label>
                  <input value={numFactura} onChange={e => setNumFactura(e.target.value)}
                    className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-zinc-700 mb-1">{t('purchases.invoice_modal.invoice_date', 'Data factura')}</label>
                  <input type="date" value={dataFactura} onChange={e => setDataFactura(e.target.value)}
                    className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-zinc-700 mb-1">{t('common.notes')}</label>
                <input value={notes} onChange={e => setNotes(e.target.value)}
                  className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
              </div>
              <div className="flex items-center justify-between text-sm bg-zinc-50 rounded-lg px-4 py-2.5">
                <span className="text-zinc-500">{t('purchases.resum.total', 'Total')} ({compraIds.length} {t('purchases.receptions', 'Recepcions').toLowerCase()})</span>
                <span className="font-semibold text-zinc-900">{total.toFixed(2)} €</span>
              </div>
            </>
          )}

          {error && <p className="text-red-500 text-sm">{error}</p>}
          <div className="flex justify-end gap-3">
            <Button type="button" variant="secondary" onClick={onClose}>{t('common.cancel')}</Button>
            <Button type="submit" disabled={saving || compraIds.length === 0}>
              {saving ? t('common.saving') : t('purchases.invoice_modal.register', 'Registrar factura')}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
