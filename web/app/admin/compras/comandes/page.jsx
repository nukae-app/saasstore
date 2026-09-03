'use client';

import { useState, useEffect, useRef, useMemo } from 'react';
import { authFetch } from '../../../lib/auth';
import { useT } from '../../../lib/i18n';
import { useDiscogsEnabled } from '../../../../components/store/useDiscogsEnabled';
import { useTenantVertical } from '../../../../components/store/useTenantVertical';
import { Button } from '../../../../components/ui/button';
import { useSortFilter } from '../../../../components/admin/table/useSortFilter';
import { SortableTh } from '../../../../components/admin/table/SortableTh';
import {
  Plus, ChevronDown, ChevronRight, X, Trash2, FileSpreadsheet, Download,
  FileText, Send, Ban, PackageCheck, Loader2, Receipt,
} from 'lucide-react';
import {
  despesaEstatLabel, DESPESA_ESTAT_COLOR, comandaStatusLabel, COMANDA_STATUS_COLOR, GRADINGS, costCompra,
} from '../../../../components/admin/compras/shared';

export default function ComandesPage() {
  const t = useT();
  const [comandas, setComandas] = useState([]);
  const [comprasProveedor, setComprasProveedor] = useState([]);
  const [proveedores, setProveedores] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [showFacturarModal, setShowFacturarModal] = useState(false);
  const [expanded, setExpanded] = useState(null);
  const [recepcioComanda, setRecepcioComanda] = useState(null);
  const [busyId, setBusyId] = useState(null);
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
    const extra = qs ? `&${qs}` : '';
    const [ordRes, provRes, comprasRes] = await Promise.all([
      authFetch(`/admin/comandas${qs ? `?${qs}` : ''}`),
      authFetch('/admin/proveedores'),
      authFetch(`/admin/compras?tipo=proveedor${extra}`),
    ]);
    setComandas(await ordRes.json());
    setProveedores(await provRes.json());
    setComprasProveedor(await comprasRes.json());
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
    entitat: { sortValue: c => (c.proveedor_nombre ?? '').toLowerCase() },
    linies: { sortValue: c => c.lineas?.length ?? 0 },
    estat: {
      sortValue: c => comandaStatusLabel(t, c.status),
      filterValue: c => comandaStatusLabel(t, c.status),
    },
  }), [t]);
  const { rows: comandasSorted, sort, toggleSort, filters: colFilters, setFilter, distinctValues } = useSortFilter(comandas, columns);

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
    loadAll();
  }

  async function marcarEnviada(comanda) {
    setBusyId(comanda.id + '_marcar');
    await authFetch(`/admin/comandas/${comanda.id}/marcar-enviada`, { method: 'PATCH' });
    setBusyId(null);
    loadAll();
  }

  async function cancelar(comanda) {
    if (!confirm(t('purchases.order.confirm_cancel', 'Cancel·lar aquesta comanda?'))) return;
    setBusyId(comanda.id + '_cancelar');
    await authFetch(`/admin/comandas/${comanda.id}/cancelar`, { method: 'PATCH' });
    setBusyId(null);
    loadAll();
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
    loadAll();
  }

  return (
    <div className="space-y-5 max-w-5xl mx-auto">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-zinc-900">{t('purchases.tab.orders', 'Comandes')}</h2>
        <div className="flex items-center gap-2">
          <button onClick={() => setShowFacturarModal(true)}
            className="flex items-center gap-1.5 text-sm border border-zinc-200 text-zinc-600 hover:bg-zinc-50 px-3 py-2 rounded-lg transition-colors">
            <Receipt size={13} /> {t('purchases.btn.invoice_receptions', 'Facturar recepcions')}
          </button>
          <Button onClick={() => setShowModal(true)}>
            <Plus size={16} /> {t('purchases.btn.new_order', 'Nova comanda')}
          </Button>
        </div>
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
        ) : comandasSorted.length === 0 ? (
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
                <SortableTh label={t('purchases.type.supplier')} sortKey="entitat" sort={sort} onSort={toggleSort} />
                <SortableTh label={t('purchases.col.lines', 'Línies')} sortKey="linies" sort={sort} onSort={toggleSort} align="center" />
                <SortableTh label={t('purchases.col.status', 'Estat')} sortKey="estat" sort={sort} onSort={toggleSort}
                  filterOptions={distinctValues.estat} selected={colFilters.estat} onFilterChange={setFilter} />
                <th className="px-4 py-3 text-right font-medium">{t('catalog.col.actions')}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-100">
              {comandasSorted.map(c => (
                <ComandaRow key={c.id} c={c} expanded={expanded} setExpanded={setExpanded}
                  recepcions={comprasProveedor.filter(cp => cp.comanda_id === c.id)}
                  busyId={busyId} downloadPdf={downloadPdf} downloadRecepcioPdf={downloadRecepcioPdf}
                  enviarPerEmail={enviarPerEmail}
                  marcarEnviada={marcarEnviada} onRecepcio={setRecepcioComanda} cancelar={cancelar} eliminar={eliminar} />
              ))}
            </tbody>
          </table>
          </div>
        )}
      </div>

      {showModal && (
        <NovaComandaModal proveedores={proveedores}
          onClose={() => setShowModal(false)}
          onSaved={() => { setShowModal(false); loadAll(); }} />
      )}
      {recepcioComanda && (
        <RecepcioModal comanda={recepcioComanda}
          onClose={() => setRecepcioComanda(null)}
          onSaved={() => { setRecepcioComanda(null); loadAll(); }} />
      )}
      {showFacturarModal && (
        <FacturarRecepcionsModal
          proveedores={proveedores}
          onClose={() => setShowFacturarModal(false)}
          onSaved={() => { setShowFacturarModal(false); loadAll(); }}
        />
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
        <td className="px-4 py-3 font-medium">
          {c.proveedor_nombre}
          {c.order_number && <span className="text-zinc-400 font-normal ml-1.5 text-xs">{c.order_number}</span>}
        </td>
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
          <td colSpan={6} className="px-4 py-3 bg-blue-50/40 border-b border-blue-100">
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

function NovaComandaModal({ proveedores, onClose, onSaved }) {
  const t = useT();
  const discogsEnabled = useDiscogsEnabled();
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

function RecepcioModal({ comanda, onClose, onSaved }) {
  const t = useT();
  const vertical = useTenantVertical();
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
