'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { authFetch } from '../../../../lib/auth';
import { useT } from '../../../../lib/i18n';
import { resolveOrCreateRelease } from '../../../../lib/discogs';
import { useDiscogsEnabled } from '../../../../../components/store/useDiscogsEnabled';
import { Button } from '../../../../../components/ui/button';
import DiscogsSearchField from '../../../../../components/admin/discogs/DiscogsSearchField';
import MIcon from '../../../../../components/ui/m-icon';

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
  const [resolving, setResolving] = useState(false);
  const [manualMode, setManualMode] = useState(false);
  const [manualForm, setManualForm] = useState({ artista: '', titulo: '', sello: '', formato: 'LP', anio: '' });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    authFetch('/admin/proveedores').then(r => r.json()).then(setProveedores);
  }, []);

  async function pickDiscogs(full) {
    setResolving(true);
    try {
      const rel = await resolveOrCreateRelease(full);
      await addLinea(rel);
    } finally {
      setResolving(false);
    }
  }

  async function addManual() {
    if (!manualForm.titulo.trim()) return;
    setResolving(true);
    try {
      const rel = await resolveOrCreateRelease(manualForm);
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
        <h2 className="text-2xl font-bold text-on-surface">{t('purchases.add_to_pool_page.title', 'Afegir discos al pool')}</h2>
      </div>

      <form onSubmit={save} className="bg-card rounded-2xl border border-outline-variant shadow-sm p-6 space-y-5">
        <p className="text-xs text-secondary">
          {t('purchases.add_to_pool_page.hint', 'Afegeix els discos que vols comprar. Més endavant, des de la pestanya "Sol·licituds", els seleccionaràs per crear-ne una sol·licitud numerada i, quan calgui, la comanda a proveïdor.')}
        </p>
        <div>
          <label className="block text-sm font-medium text-on-surface-variant mb-1">{t('common.notes')}</label>
          <input value={notas} onChange={e => setNotas(e.target.value)}
            className="w-full border border-outline-variant rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary" />
        </div>

        <div className="border border-outline-variant rounded-xl p-4 space-y-3">
          <div className="text-sm font-semibold text-on-surface-variant">{t('purchases.request_modal.wanted_records', 'Discos volguts')}</div>
          {discogsEnabled && (
            <DiscogsSearchField onPick={pickDiscogs} disabled={resolving} />
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
              <Button type="button" size="sm" onClick={addManual}
                disabled={resolving || !manualForm.titulo.trim()}>
                {resolving ? t('common.creating') : t('common.add', 'Afegir')}
              </Button>
            </div>
          )}

          {lineas.length === 0 && (
            <div className="text-sm text-secondary text-center py-4">{t('purchases.individual_modal.no_items', 'Encara no has afegit cap disc.')}</div>
          )}

          <div className="space-y-2">
            {lineas.map((l, idx) => (
              <div key={idx} className="p-3 bg-surface-container-high rounded-xl border border-outline-variant">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-semibold text-on-surface">{l.artista} — {l.titulo}</span>
                    {l.existing && (
                      <span className="text-[10px] uppercase tracking-wide text-secondary bg-surface-container-high rounded-full px-2 py-0.5">
                        {t('purchases.modal.already_in_catalog', 'Ja al catàleg')}
                      </span>
                    )}
                  </div>
                  <button type="button" onClick={() => setLineas(p => p.filter((_, i) => i !== idx))}
                    className="text-secondary hover:text-red-500 transition-colors">
                    <MIcon name="delete" size={15} />
                  </button>
                </div>
                <div className="flex flex-wrap gap-3">
                  <div>
                    <label className="block text-xs text-secondary mb-1">{t('purchases.quantity', 'Quantitat')}</label>
                    <input type="number" min="1" value={l.cantidad} onChange={e => upd(idx, 'cantidad', e.target.value)}
                      className="w-20 border border-outline-variant rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-primary" />
                  </div>
                  <div>
                    <label className="block text-xs text-secondary mb-1">{t('purchases.suggested_supplier', 'Proveïdor suggerit')}</label>
                    <select value={l.proveedor_sugerido_id} onChange={e => upd(idx, 'proveedor_sugerido_id', e.target.value)}
                      className="border border-outline-variant rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-primary bg-card">
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
