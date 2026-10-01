'use client';

// Configuració › Còpies de seguretat: còpia de l'inventari de Discogs (només consulta i descàrrega) i punts de
// restauració del CATÀLEG de la botiga (releases, items, vincles amb Discogs i listings; mai la base de dades
// sencera). Restaurar mostra abans exactament què canviaria i no toca el que ja no és segur (vendes, reserves...).

import { useState, useEffect, useCallback } from 'react';
import { authFetch } from '../../../lib/auth';
import { Button } from '../../../../components/ui/button';
import MIcon from '../../../../components/ui/m-icon';
import { Badge, CH, ErrorBox, Panel, ProgressPanel, api, fmtDate } from './shared';

const TRIGGER = {
  manual: 'Manual', pre_load: 'Abans de la càrrega inicial', pre_prices: 'Abans d\'aplicar preus',
  pre_restore: 'Abans de restaurar',
};
const TABLE_LABEL = {
  releases: 'Fitxes de disc', release_records: 'Dades de disc (artista, format...)', items: 'Còpies a la venda (items)',
  record_stock_details: 'Vincles amb Discogs', channel_listings: 'Listings publicats',
};
const OP_LABEL = { insert: 'Tornar a crear', update: 'Corregir', delete: 'Eliminar (creat després)' };

function fmtSize(n) {
  if (n > 1024 * 1024) return `${(n / 1024 / 1024).toFixed(1)} MB`;
  return `${Math.max(1, Math.round(n / 1024))} KB`;
}

function content(b) {
  const s = b.summary || {};
  if (b.kind === 'catalog') return `${s.releases ?? 0} discos · ${s.items ?? 0} items · ${s.channel_listings ?? 0} listings`;
  const orders = s.comandes === null || s.comandes === undefined ? 'sense comandes' : `${s.comandes} comandes`;
  return `${s.compte} · ${s.listings_total} listings · ${orders}`;
}

export default function BackupsPanel({ t, estat, reload }) {
  const [backups, setBackups] = useState([]);
  const [label, setLabel] = useState('');
  const [withOrders, setWithOrders] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [msg, setMsg] = useState('');
  const [restore, setRestore] = useState(null);   // { backup, preview, ack, result, working }

  const job = estat?.job;
  const running = !!job && job.mode === 'discogs_backup' && ['queued', 'running'].includes(job.status);
  const lastFail = estat?.ultims?.discogs_backup?.status === 'error' ? estat.ultims.discogs_backup : null;

  const load = useCallback(async () => {
    const r = await api(`${CH}/backups`);
    if (r.ok) setBackups(r.data);
  }, []);
  useEffect(() => { load(); }, [load, job?.id, job?.status]);

  async function createCatalog() {
    setBusy(true); setError(''); setMsg('');
    const r = await api(`${CH}/backups/catalog`, { method: 'POST', body: { label } });
    setBusy(false);
    if (!r.ok) { setError(r.data.detail || 'No s\'ha pogut crear la còpia.'); return; }
    setLabel('');
    setMsg(t('discogs.backups.created', 'Punt de restauració creat.'));
    load();
  }

  async function startDiscogs() {
    setBusy(true); setError(''); setMsg('');
    const r = await api(`${CH}/backups/discogs`, { method: 'POST', body: { orders: withOrders } });
    setBusy(false);
    if (!r.ok) { setError(r.data.detail || 'No s\'ha pogut iniciar la còpia.'); return; }
    reload();
  }

  async function download(b, formato = 'json') {
    const r = await authFetch(`${CH}/backups/${b.id}/download?formato=${formato}`);
    if (!r.ok) { setError('No s\'ha pogut descarregar.'); return; }
    const cd = r.headers.get('content-disposition') || '';
    const name = (cd.match(/filename="([^"]+)"/) || [])[1] || `copia.${formato}`;
    const url = URL.createObjectURL(await r.blob());
    const a = document.createElement('a');
    a.href = url; a.download = name; a.click();
    URL.revokeObjectURL(url);
  }

  async function remove(b) {
    if (!window.confirm(t('discogs.backups.confirm_delete', 'Eliminar aquesta còpia? No es pot desfer.'))) return;
    const r = await api(`${CH}/backups/${b.id}`, { method: 'DELETE' });
    if (!r.ok) setError(r.data.detail || 'No s\'ha pogut eliminar.');
    load();
  }

  async function openRestore(b) {
    setError(''); setMsg('');
    setRestore({ backup: b, preview: null, ack: false, result: null, working: false });
    const r = await api(`${CH}/backups/${b.id}/restore/preview`, { method: 'POST' });
    if (!r.ok) { setRestore(null); setError(r.data.detail || 'No s\'ha pogut calcular la vista prèvia.'); return; }
    setRestore((s) => ({ ...s, preview: r.data }));
  }

  async function doRestore() {
    setRestore((s) => ({ ...s, working: true }));
    const r = await api(`${CH}/backups/${restore.backup.id}/restore`, { method: 'POST', body: { confirm: true } });
    if (!r.ok) {
      setRestore((s) => ({ ...s, working: false }));
      setError(r.data.detail || 'No s\'ha pogut restaurar.');
      return;
    }
    setRestore((s) => ({ ...s, working: false, result: r.data }));
    load();
  }

  const p = restore?.preview;
  const nothing = p && p.total_changes === 0;
  return (
    <Panel title={t('discogs.backups.title', 'Còpies de seguretat')}>
      <p className="text-xs text-secondary-foreground max-w-2xl">
        {t('discogs.backups.hint', 'Només el catàleg de discos de la teva botiga: mai la base de dades sencera. Es creen sols abans de la càrrega inicial i abans d\'aplicar preus, i es poden tornar a l\'estat d\'una còpia. La còpia de Discogs és la foto del que hi ha publicat (només consulta).')}
      </p>
      <ErrorBox>{error}</ErrorBox>
      {msg && <p className="text-xs text-green-700">{msg}</p>}
      {running && <ProgressPanel t={t} job={job} />}
      {!running && lastFail && <ErrorBox>{lastFail.error}</ErrorBox>}

      <div className="grid md:grid-cols-2 gap-3">
        <div className="rounded-xl bg-surface-container-high p-4 space-y-2">
          <p className="text-sm font-medium text-on-surface">{t('discogs.backups.catalog', 'Punt de restauració del catàleg')}</p>
          <input value={label} onChange={(e) => setLabel(e.target.value)} maxLength={200}
            placeholder={t('discogs.backups.label_ph', 'Nom (opcional), p. ex. «abans de provar»')}
            className="w-full border border-outline-variant rounded-xl px-3 py-2 text-sm bg-card" />
          <Button size="sm" onClick={createCatalog} disabled={busy}>
            <MIcon name="bookmark_add" size={14} /> {t('discogs.backups.create', 'Crear punt de restauració')}
          </Button>
        </div>
        <div className="rounded-xl bg-surface-container-high p-4 space-y-2">
          <p className="text-sm font-medium text-on-surface">{t('discogs.backups.discogs', 'Còpia de l\'inventari de Discogs')}</p>
          <label className="flex items-center gap-2 text-xs text-secondary-foreground">
            <input type="checkbox" checked={withOrders} onChange={(e) => setWithOrders(e.target.checked)} />
            {t('discogs.backups.with_orders', 'Incloure l\'històric de comandes (triga més)')}
          </label>
          <Button size="sm" variant="secondary" onClick={startDiscogs} disabled={busy || running}>
            <MIcon name={running ? 'progress_activity' : 'cloud_download'} size={14} className={running ? 'animate-spin' : ''} />
            {t('discogs.backups.download_discogs', 'Fer còpia de Discogs')}
          </Button>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="text-xs text-secondary-foreground border-b border-outline-variant">
            <tr>
              <th className="px-3 py-2 text-left font-medium">{t('discogs.canal.col_date', 'Data')}</th>
              <th className="px-3 py-2 text-left font-medium">{t('discogs.backups.col_what', 'Còpia')}</th>
              <th className="px-3 py-2 text-left font-medium">{t('discogs.backups.col_content', 'Contingut')}</th>
              <th className="px-3 py-2 text-left font-medium">{t('discogs.backups.col_by', 'Per')}</th>
              <th className="px-3 py-2" />
            </tr>
          </thead>
          <tbody>
            {backups.map((b) => (
              <tr key={b.id} className="border-b border-outline-variant last:border-0">
                <td className="px-3 py-2 text-secondary-foreground whitespace-nowrap">{fmtDate(b.created_at)}</td>
                <td className="px-3 py-2">
                  <Badge cls={b.kind === 'catalog' ? 'bg-blue-100 text-blue-800' : 'bg-violet-100 text-violet-800'}>
                    {b.kind === 'catalog' ? t('discogs.backups.k_catalog', 'Catàleg') : 'Discogs'}
                  </Badge>
                  <span className="ml-2 text-xs text-secondary-foreground">{TRIGGER[b.trigger] || b.trigger}</span>
                  {b.label && <p className="text-xs text-on-surface mt-0.5">{b.label}</p>}
                </td>
                <td className="px-3 py-2 text-xs text-secondary-foreground">{content(b)} · {fmtSize(b.size_bytes)}</td>
                <td className="px-3 py-2 text-xs text-secondary-foreground">{b.created_by}</td>
                <td className="px-3 py-2 text-right whitespace-nowrap text-xs space-x-3">
                  {b.kind === 'catalog' && (
                    <button type="button" className="text-primary hover:underline" onClick={() => openRestore(b)}>
                      {t('discogs.backups.restore', 'Restaurar')}
                    </button>
                  )}
                  <button type="button" className="text-primary hover:underline" onClick={() => download(b)}>JSON</button>
                  {b.kind === 'discogs_inventory' && (
                    <button type="button" className="text-primary hover:underline" onClick={() => download(b, 'csv')}>CSV</button>
                  )}
                  <button type="button" className="text-secondary-foreground hover:text-red-600" onClick={() => remove(b)}>
                    {t('discogs.backups.delete', 'Elimina')}
                  </button>
                </td>
              </tr>
            ))}
            {backups.length === 0 && (
              <tr><td colSpan={5} className="px-3 py-8 text-center text-secondary-foreground">{t('discogs.backups.none', 'Encara no hi ha cap còpia.')}</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {restore && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-card rounded-2xl border border-outline-variant shadow-xl max-w-3xl w-full max-h-[90vh] overflow-y-auto p-6 space-y-4">
            <p className="text-lg font-semibold text-on-surface">
              {t('discogs.backups.restore_title', 'Restaurar el catàleg')} · {restore.backup.label || fmtDate(restore.backup.created_at)}
            </p>

            {!p && <p className="text-sm text-secondary-foreground">{t('common.loading')}</p>}

            {restore.result ? (
              <div className="space-y-2 text-sm">
                <p className="text-green-700 font-medium">
                  {restore.result.restored
                    ? t('discogs.backups.restored', 'Catàleg restaurat.')
                    : restore.result.message}
                </p>
                {restore.result.copia_previa && (
                  <p className="text-xs text-secondary-foreground">{t('discogs.backups.pre_saved', 'S\'ha guardat una còpia de l\'estat anterior: pots tornar-hi igual que ara.')}</p>
                )}
                {restore.result.conflicts?.length > 0 && (
                  <p className="text-amber-700">{restore.result.conflicts.length} {t('discogs.backups.skipped', 'elements s\'han deixat com estaven per seguretat.')}</p>
                )}
                <div className="flex justify-end"><Button onClick={() => setRestore(null)}>{t('common.close', 'Tanca')}</Button></div>
              </div>
            ) : p && (
              <>
                {nothing ? (
                  <p className="text-sm text-secondary-foreground">{t('discogs.backups.same', 'El catàleg ja coincideix amb aquesta còpia: no hi ha res a restaurar.')}</p>
                ) : (
                  <>
                    <p className="text-sm text-secondary-foreground">
                      {t('discogs.backups.preview_intro', 'Això és exactament el que canviaria. No toca Discogs ni cap altra botiga.')}
                    </p>
                    <table className="w-full text-sm">
                      <thead className="text-xs text-secondary-foreground border-b border-outline-variant">
                        <tr><th className="py-1 text-left font-medium" />{Object.keys(OP_LABEL).map((k) => <th key={k} className="py-1 text-right font-medium">{OP_LABEL[k]}</th>)}</tr>
                      </thead>
                      <tbody>
                        {Object.entries(p.counts).map(([name, c]) => (
                          <tr key={name} className="border-b border-outline-variant last:border-0">
                            <td className="py-1.5">{TABLE_LABEL[name] || name}</td>
                            {Object.keys(OP_LABEL).map((k) => <td key={k} className={`py-1.5 text-right tabular-nums ${c[k] ? 'font-semibold text-on-surface' : 'text-secondary-foreground'}`}>{c[k]}</td>)}
                          </tr>
                        ))}
                      </tbody>
                    </table>

                    {p.sample.length > 0 && (
                      <div>
                        <p className="text-xs font-medium text-on-surface mb-1">{t('discogs.backups.examples', 'Exemples')}</p>
                        <ul className="text-xs text-secondary-foreground max-h-48 overflow-auto border border-outline-variant rounded-xl p-3 space-y-1">
                          {p.sample.map((s, i) => (
                            <li key={i}>
                              <b>{OP_LABEL[s.op]}</b> · {TABLE_LABEL[s.table] || s.table} · {s.label}
                              {s.changes && Object.entries(s.changes).map(([col, [now, was]]) => (
                                <span key={col} className="ml-2">{col}: <span className="text-red-700">{String(now)}</span> → <span className="text-green-700">{String(was)}</span></span>
                              ))}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </>
                )}

                {p.conflicts_total > 0 && (
                  <div className="bg-amber-50 border border-amber-200 text-amber-900 rounded-xl p-4 space-y-1 text-sm">
                    <p className="font-medium">{p.conflicts_total} {t('discogs.backups.conflicts', 'elements es deixaran com estan perquè ja no és segur tocar-los:')}</p>
                    <ul className="text-xs max-h-32 overflow-auto space-y-0.5">
                      {p.conflicts.map((c, i) => <li key={i}>{c.label} — {c.reason}</li>)}
                    </ul>
                  </div>
                )}

                {!nothing && (
                  <label className="flex items-start gap-2 text-sm">
                    <input type="checkbox" checked={restore.ack} onChange={(e) => setRestore({ ...restore, ack: e.target.checked })} className="mt-0.5" />
                    <span>{t('discogs.backups.ack', 'Entenc que es modificarà el catàleg de la botiga. Abans es guardarà una còpia de l\'estat actual.')}</span>
                  </label>
                )}
                <div className="flex justify-end gap-2">
                  <Button variant="secondary" onClick={() => setRestore(null)}>{t('common.cancel', 'Cancel·la')}</Button>
                  {!nothing && (
                    <Button disabled={!restore.ack || restore.working} onClick={doRestore}>
                      <MIcon name={restore.working ? 'progress_activity' : 'restore'} size={14} className={restore.working ? 'animate-spin' : ''} />
                      {t('discogs.backups.confirm_restore', 'Restaurar el catàleg')}
                    </Button>
                  )}
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </Panel>
  );
}
