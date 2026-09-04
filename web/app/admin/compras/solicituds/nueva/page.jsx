'use client';

import { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { authFetch } from '../../../../lib/auth';
import { useT } from '../../../../lib/i18n';
import { useDiscogsEnabled } from '../../../../../components/store/useDiscogsEnabled';
import { Button } from '../../../../../components/ui/button';
import { Trash2 } from 'lucide-react';

// Pantalla dedicada per crear una sol·licitud manual, separada del llistat
// (veure /admin/compras/solicituds): un formulari necessita més espai que un
// modal per a la cerca a Discogs + la llista de discos afegits.
export default function NovaSolicitudPage() {
  const t = useT();
  const router = useRouter();
  const discogsEnabled = useDiscogsEnabled();
  const [proveedores, setProveedores] = useState([]);
  const [notas, setNotas] = useState('');
  const [lineas, setLineas] = useState([]);
  const [discogsQ, setDiscogsQ] = useState('');
  const [discogsRes, setDiscogsRes] = useState([]);
  const [searchingDiscogs, setSearchingDiscogs] = useState(false);
  const [resolving, setResolving] = useState(false);
  const [manualMode, setManualMode] = useState(false);
  const [manualForm, setManualForm] = useState({ artista: '', titulo: '', sello: '', formato: 'LP', anio: '' });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const discogsDebounce = useRef(null);

  useEffect(() => {
    authFetch('/admin/proveedores').then(r => r.json()).then(setProveedores);
  }, []);

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
    setError('');
    const payload = {
      origen: 'manual',
      lineas: lineas.map(l => ({
        release_id: l.release_id,
        quantity: parseInt(l.cantidad, 10),
        proveedor_sugerido_id: l.proveedor_sugerido_id || null,
        notes: notas || null,
      })),
    };
    const r = await authFetch('/admin/solicitudes-compra/pool', { method: 'POST', body: JSON.stringify(payload) });
    setSaving(false);
    if (r.ok) router.push('/admin/compras/solicituds');
    else setError((await r.json().catch(() => ({}))).detail || t('purchases.request.create_error', 'No s\'ha pogut crear la sol·licitud.'));
  }

  return (
    <div className="space-y-5 max-w-3xl mx-auto">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-zinc-900">{t('purchases.add_to_pool_page.title', 'Afegir discos al pool')}</h2>
      </div>

      <form onSubmit={save} className="bg-white rounded-2xl border border-zinc-200 shadow-sm p-6 space-y-5">
        <p className="text-xs text-zinc-400">
          {t('purchases.add_to_pool_page.hint', 'Afegeix els discos que vols comprar. Més endavant, des de la pestanya "Sol·licituds", els seleccionaràs per crear-ne una sol·licitud numerada i, quan calgui, la comanda a proveïdor.')}
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

        {error && <p className="text-red-500 text-sm">{error}</p>}
        <div className="flex justify-end gap-3">
          <Button type="button" variant="secondary" onClick={() => router.push('/admin/compras/solicituds')}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" disabled={saving || lineas.length === 0}>
            {saving ? t('common.saving') : `${t('purchases.btn.add_to_pool', 'Afegir al pool')} (${lineas.length})`}
          </Button>
        </div>
      </form>
    </div>
  );
}
