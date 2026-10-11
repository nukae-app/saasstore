'use client';

// Pestaña Listings: una fila por item con el estado en el canal, el precio de la app frente al publicado y la
// acción propuesta (publicar / actualizar precio / retirar / vincular release). Se puede aplicar por acción,
// por selección o por item, SIEMPRE con vista previa. Escribir en Discogs exige el modo lectura/escritura.

import { useState, useEffect, useCallback } from 'react';
import { Button } from '../../../../components/ui/button';
import MIcon from '../../../../components/ui/m-icon';
import {
  ACTIONS, Badge, CH, ErrorBox, PAGE, ProgressPanel, Results, RunHistory, api, fmtPrice, fmtDate,
} from './shared';

const ESTATS = {
  publicat: { label: 'Publicat', cls: 'bg-green-100 text-green-800' },
  pendent: { label: 'Pendent', cls: 'bg-blue-100 text-blue-800' },
  error: { label: 'Error', cls: 'bg-red-100 text-red-800' },
  sense_release: { label: 'Sense release', cls: 'bg-surface-container-high text-secondary-foreground' },
  retirat: { label: 'Retirat', cls: 'bg-surface-container-high text-secondary-foreground' },
  no_aplica: { label: '—', cls: 'bg-surface-container-high text-secondary-foreground' },
};
const ACTIONABLE = ['publicar', 'actualitzar_preu', 'retirar'];
const ACTION_BUTTON = { publicar: 'Publicar', actualitzar_preu: 'Actualitzar preus', retirar: 'Retirar' };

export default function ListingsTab({ t, account, estat, reload, initial, goTab }) {
  const [filters, setFilters] = useState({ estat: '', accio: '', condicio: '', q: '', ...initial });
  const [page, setPage] = useState(0);
  const [data, setData] = useState({ total: 0, counts_estat: {}, counts_accio: {}, rows: [] });
  const [selected, setSelected] = useState(new Set());
  const [preview, setPreview] = useState(null);   // { payload, data, force }
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [market, setMarket] = useState({});       // item_id -> datos de mercado (fila expandida)
  const [expanded, setExpanded] = useState(null);

  const job = estat?.job;
  // En curso (si es una reconciliación) y último resultado de ESTA funcionalidad, aunque después se lance otro tipo.
  const runningJob = job && job.mode === 'reconcile' && ['queued', 'running'].includes(job.status) ? job : null;
  const running = !!runningJob;
  const lastRec = estat?.ultims?.reconcile_apply || null;
  const [viewRun, setViewRun] = useState(null);
  const readOnly = !!account?.solo_lectura;

  const load = useCallback(async () => {
    const p = new URLSearchParams({ limit: String(PAGE), offset: String(page * PAGE) });
    Object.entries(filters).forEach(([k, v]) => { if (v) p.set(k, v); });
    const r = await api(`${CH}/listings?${p}`);
    if (r.ok) setData(r.data);
  }, [filters, page]);

  useEffect(() => { load(); }, [load, job?.id, job?.status]);

  function setFilter(k, v) { setFilters((f) => ({ ...f, [k]: v })); setPage(0); }

  async function openPreview(payload) {
    setError('');
    const r = await api(`${CH}/reconcile/preview`, { method: 'POST', body: payload });
    if (!r.ok) { setError(r.data.detail || 'No s\'ha pogut calcular la vista prèvia.'); return; }
    setPreview({ payload, data: r.data, force: false });
  }

  async function confirm() {
    setBusy(true);
    setError('');
    const r = await api(`${CH}/reconcile`, { method: 'POST', body: { ...preview.payload, force: preview.force } });
    setBusy(false);
    if (!r.ok) { setError(r.data.detail || 'No s\'ha pogut iniciar.'); return; }
    setPreview(null);
    setSelected(new Set());
    reload();
  }

  async function toggleMarket(row) {
    if (expanded === row.item_id) { setExpanded(null); return; }
    setExpanded(row.item_id);
    if (market[row.item_id] || !row.discogs_release_id) return;
    const r = await api(`${CH}/pricing/release/${row.discogs_release_id}`);
    setMarket((m) => ({ ...m, [row.item_id]: r.ok ? r.data : { error: r.data.detail || 'No s\'ha pogut consultar Discogs.' } }));
  }

  function toggleSel(id) {
    setSelected((s) => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n; });
  }

  const pages = Math.max(1, Math.ceil(data.total / PAGE));
  const writeBlock = readOnly ? t('discogs.listings.ro', 'Mode només lectura: no es pot escriure a Discogs (Configuració).') : '';
  const disabled = readOnly || running;

  return (
    <div className="space-y-4">
      <ErrorBox>{error}</ErrorBox>
      {readOnly && (
        <div className="bg-amber-50 text-amber-800 border border-amber-200 rounded-xl px-4 py-3 text-sm">{writeBlock}</div>
      )}

      <div className="flex items-center gap-2 flex-wrap">
        {ACTIONABLE.map((a) => (
          <Button key={a} variant="secondary" size="sm" disabled={disabled || !data.counts_accio[a]} title={writeBlock}
            onClick={() => openPreview({ actions: [a] })}>
            {ACTION_BUTTON[a]} ({data.counts_accio[a] || 0})
          </Button>
        ))}
        <Button size="sm" disabled={disabled || selected.size === 0} title={writeBlock}
          onClick={() => openPreview({ item_ids: [...selected] })}>
          <MIcon name="sync" size={14} /> {t('discogs.listings.apply_selected', 'Aplicar seleccionats')} ({selected.size})
        </Button>
      </div>

      {runningJob && <ProgressPanel t={t} job={runningJob} />}
      {!runningJob && lastRec && lastRec.status === 'error' && <ErrorBox>{lastRec.error}</ErrorBox>}
      {!runningJob && lastRec && lastRec.status === 'done' && lastRec.summary && (
        <div className="bg-card rounded-2xl border border-outline-variant p-4 space-y-3">
          <p className="text-sm font-semibold text-on-surface">
            {t('discogs.listings.done', 'Última reconciliació')} ({fmtDate(lastRec.finished_at)}): {lastRec.summary.publicats} {t('discogs.listings.published', 'publicats')} ·{' '}
            {lastRec.summary.actualitzats} {t('discogs.listings.prices', 'preus')} · {lastRec.summary.retirats} {t('discogs.listings.retired', 'retirats')} ·{' '}
            {lastRec.summary.errors} errors
          </p>
          <Results t={t} jobId={lastRec.id} />
        </div>
      )}

      <div className="bg-card rounded-2xl border border-outline-variant shadow-sm overflow-hidden">
        <div className="p-4 flex items-center gap-3 flex-wrap border-b border-outline-variant">
          <select value={filters.accio} onChange={(e) => setFilter('accio', e.target.value)} className="border border-outline-variant rounded-xl px-3 py-2 text-sm bg-card">
            <option value="">{t('discogs.listings.all_actions', 'Totes les accions')}</option>
            {Object.entries(data.counts_accio).map(([k, n]) => <option key={k} value={k}>{ACTIONS[k]?.label || k} ({n})</option>)}
          </select>
          <select value={filters.estat} onChange={(e) => setFilter('estat', e.target.value)} className="border border-outline-variant rounded-xl px-3 py-2 text-sm bg-card">
            <option value="">{t('discogs.listings.all_states', 'Tots els estats')}</option>
            {Object.entries(data.counts_estat).map(([k, n]) => <option key={k} value={k}>{ESTATS[k]?.label || k} ({n})</option>)}
          </select>
          <select value={filters.condicio} onChange={(e) => setFilter('condicio', e.target.value)} className="border border-outline-variant rounded-xl px-3 py-2 text-sm bg-card">
            <option value="">{t('discogs.listings.all_conditions', 'Nou i 2a mà')}</option>
            <option value="nou">Nou</option>
            <option value="segona_ma">2a mà</option>
          </select>
          <input value={filters.q} onChange={(e) => setFilter('q', e.target.value)}
            placeholder={t('discogs.listings.search_ph', 'Cerca per artista, títol o codi…')}
            className="flex-1 min-w-[200px] border border-outline-variant rounded-xl px-3 py-2 text-sm bg-card" />
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-surface-container-high text-xs text-secondary-foreground border-b border-outline-variant">
              <tr>
                <th className="px-3 py-3 w-8" />
                <th className="px-3 py-3 text-left font-medium">{t('discogs.canal.col_disc', 'Disc')}</th>
                <th className="px-3 py-3 text-left font-medium">{t('discogs.canal.col_cond', 'Condició')}</th>
                <th className="px-3 py-3 text-right font-medium">{t('discogs.listings.col_stock', 'Estoc')}</th>
                <th className="px-3 py-3 text-right font-medium">{t('discogs.canal.col_price_app', 'Preu botiga')}</th>
                <th className="px-3 py-3 text-right font-medium">{t('discogs.listings.col_published', 'Publicat')}</th>
                <th className="px-3 py-3 text-left font-medium">{t('discogs.listings.col_state', 'Estat')}</th>
                <th className="px-3 py-3 text-left font-medium">{t('discogs.canal.col_action', 'Acció')}</th>
                <th className="px-3 py-3" />
              </tr>
            </thead>
            <tbody>
              {data.rows.map((r) => {
                const actionable = ACTIONABLE.includes(r.accio);
                const m = market[r.item_id];
                return [
                  <tr key={r.item_id} className="border-b border-outline-variant">
                    <td className="px-3 py-2.5">
                      {actionable && <input type="checkbox" checked={selected.has(r.item_id)} onChange={() => toggleSel(r.item_id)} />}
                    </td>
                    <td className="px-3 py-2.5">
                      <span className="font-medium text-on-surface">{r.artista || '—'}</span>
                      <span className="text-secondary-foreground"> — {r.titol}</span>
                      {r.formato && <span className="text-xs text-secondary-foreground"> · {r.formato}</span>}
                    </td>
                    <td className="px-3 py-2.5 text-secondary-foreground">{r.condicio === 'nou' ? 'Nou' : '2a mà'}</td>
                    <td className="px-3 py-2.5 text-right tabular-nums">{r.condicio === 'nou' ? r.quantity : 1}</td>
                    <td className="px-3 py-2.5 text-right tabular-nums">{fmtPrice(r.price)}</td>
                    <td className="px-3 py-2.5 text-right tabular-nums">
                      {r.external_id ? (
                        <a href={`https://www.discogs.com/sell/item/${r.external_id}`} target="_blank" rel="noreferrer" className="text-primary hover:underline">{fmtPrice(r.published_price)}</a>
                      ) : '—'}
                    </td>
                    <td className="px-3 py-2.5">
                      <Badge cls={ESTATS[r.estat_canal]?.cls}>{ESTATS[r.estat_canal]?.label || r.estat_canal}</Badge>
                      {r.last_error && <p className="text-[11px] text-red-700 mt-1 max-w-[220px] truncate" title={r.last_error}>{r.last_error}</p>}
                    </td>
                    <td className="px-3 py-2.5" title={r.motiu}>
                      <Badge cls={ACTIONS[r.accio]?.cls}>{ACTIONS[r.accio]?.label || r.accio}</Badge>
                    </td>
                    <td className="px-3 py-2.5 text-right whitespace-nowrap">
                      {r.discogs_release_id && (
                        <button type="button" onClick={() => toggleMarket(r)} className="text-xs text-primary hover:underline">
                          {expanded === r.item_id ? t('discogs.listings.hide', 'Amaga') : t('discogs.listings.prices_link', 'Preus')}
                        </button>
                      )}
                      {r.accio === 'vincular_release' && (
                        <button type="button" className="ml-3 text-xs text-primary hover:underline" onClick={() => goTab('vincular')}>
                          {t('discogs.link.go', 'Vincula')}
                        </button>
                      )}
                      {actionable && !disabled && (
                        <button type="button" className="ml-3 text-xs text-primary hover:underline"
                          onClick={() => openPreview({ item_ids: [r.item_id] })}>
                          {ACTIONS[r.accio]?.label}
                        </button>
                      )}
                    </td>
                  </tr>,
                  expanded === r.item_id && (
                    <tr key={`${r.item_id}-m`} className="bg-surface-container-high/40 border-b border-outline-variant">
                      <td />
                      <td colSpan={8} className="px-3 py-3 text-xs"><MarketInfo t={t} data={m} item={r} /></td>
                    </tr>
                  ),
                ];
              })}
              {data.rows.length === 0 && (
                <tr><td colSpan={9} className="px-4 py-10 text-center text-secondary-foreground">{t('common.no_results', 'Sense resultats')}</td></tr>
              )}
            </tbody>
          </table>
        </div>
        <div className="p-3 flex items-center justify-between text-xs text-secondary-foreground">
          <span>{data.total} {t('discogs.canal.rows', 'files')}</span>
          <div className="flex items-center gap-2">
            <Button variant="secondary" size="sm" disabled={page === 0} onClick={() => setPage((p) => p - 1)}>‹</Button>
            <span>{page + 1} / {pages}</span>
            <Button variant="secondary" size="sm" disabled={page + 1 >= pages} onClick={() => setPage((p) => p + 1)}>›</Button>
          </div>
        </div>
      </div>

      <RunHistory t={t} kinds={['reconcile_apply']} refreshKey={`${job?.id}-${job?.status}`} viewId={viewRun?.id} onView={setViewRun} />
      {viewRun && viewRun.id !== lastRec?.id && <Results t={t} jobId={viewRun.id} />}

      {preview && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-card rounded-2xl border border-outline-variant shadow-xl max-w-xl w-full p-6 space-y-4">
            <p className="text-lg font-semibold text-on-surface">{t('discogs.listings.confirm_title', 'Aplicar a Discogs')}</p>
            <p className="text-sm text-secondary-foreground">
              {preview.data.total === 0
                ? t('discogs.listings.nothing', 'No hi ha res a fer amb aquesta selecció.')
                : t('discogs.listings.confirm_text', 'S\'escriurà al teu compte de Discogs:')}
            </p>
            <ul className="text-sm space-y-1">
              {Object.entries(preview.data.counts).map(([k, n]) => (
                <li key={k} className="flex items-center gap-2"><Badge cls={ACTIONS[k]?.cls}>{ACTIONS[k]?.label || k}</Badge> {n} items</li>
              ))}
            </ul>
            {preview.data.sample.length > 0 && (
              <ul className="text-xs text-secondary-foreground max-h-40 overflow-auto border border-outline-variant rounded-xl p-3 space-y-0.5">
                {preview.data.sample.map((s) => (
                  <li key={s.item_id}>{s.artista || '—'} — {s.titol}{s.accio === 'actualitzar_preu' ? ` · ${fmtPrice(s.published_price)} → ${fmtPrice(s.target_price)}` : s.accio === 'publicar' ? ` · ${fmtPrice(s.target_price)}` : ''}</li>
                ))}
                {preview.data.total > preview.data.sample.length && <li>… {t('discogs.listings.and_more', 'i')} {preview.data.total - preview.data.sample.length} {t('discogs.listings.more', 'més')}</li>}
              </ul>
            )}
            {preview.data.guard && (
              <div className="bg-amber-50 border border-amber-200 text-amber-800 rounded-xl px-4 py-3 text-sm space-y-2">
                <p>⚠ {preview.data.guard}</p>
                <label className="flex items-start gap-2">
                  <input type="checkbox" checked={preview.force} onChange={(e) => setPreview({ ...preview, force: e.target.checked })} className="mt-0.5" />
                  <span>{t('discogs.listings.force', 'Entenc l\'avís i vull continuar igualment.')}</span>
                </label>
              </div>
            )}
            <div className="flex justify-end gap-2">
              <Button variant="secondary" onClick={() => setPreview(null)}>{t('common.cancel', 'Cancel·la')}</Button>
              <Button disabled={busy || preview.data.total === 0 || (preview.data.guard && !preview.force)} onClick={confirm}>
                {t('discogs.listings.confirm', 'Sí, aplica-ho')}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function MarketInfo({ t, data, item }) {
  if (!data) return <span className="text-secondary-foreground">{t('common.loading')}</span>;
  if (data.error) return <span className="text-red-700">{data.error}</span>;
  const sug = data.suggestions || {};
  const keys = Object.keys(sug);
  return (
    <div className="flex flex-wrap gap-x-8 gap-y-2">
      <div>
        <p className="font-medium text-on-surface mb-1">{t('discogs.market.suggested', 'Preus suggerits per Discogs')}</p>
        {keys.length === 0 ? <p className="text-secondary-foreground">{t('discogs.market.none', 'Sense suggeriments per a aquest release.')}</p> : (
          <ul>{keys.map((k) => <li key={k}>{k}: <b>{fmtPrice(sug[k].value)}</b></li>)}</ul>
        )}
      </div>
      {data.stats && (
        <div>
          <p className="font-medium text-on-surface mb-1">{t('discogs.market.market', 'Mercat')}</p>
          <p>{t('discogs.market.lowest', 'Preu més baix')}: <b>{fmtPrice(data.stats.lowest_price?.value)}</b></p>
          <p>{t('discogs.market.for_sale', 'A la venda')}: <b>{data.stats.num_for_sale ?? '—'}</b></p>
        </div>
      )}
      <div>
        <p className="font-medium text-on-surface mb-1">{t('discogs.market.yours', 'El teu')}</p>
        <p>{t('discogs.canal.col_price_app', 'Preu botiga')}: <b>{fmtPrice(item.price)}</b></p>
        {item.last_synced_at && <p className="text-secondary-foreground">{fmtDate(item.last_synced_at)}</p>}
      </div>
    </div>
  );
}
