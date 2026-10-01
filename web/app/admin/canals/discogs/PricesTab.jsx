'use client';

// Pestaña Preus: precios sugeridos y de mercado de Discogs (solo lectura), comisión y reprecio masivo con
// simulación. Aplicar cambia el precio en LA APP; luego "Listings" propone propagarlo a Discogs.

import { useState, useEffect, useCallback } from 'react';
import { Button } from '../../../../components/ui/button';
import MIcon from '../../../../components/ui/m-icon';
import { ACTIONS, Badge, CH, ErrorBox, INV, Panel, ProgressPanel, api, fmtPrice } from './shared';

const inputCls = 'border border-outline-variant rounded-xl px-3 py-2 text-sm bg-card w-full';

function Field({ label, children }) {
  return <label className="text-xs text-secondary-foreground space-y-1 block">{label}{children}</label>;
}

export default function PricesTab({ t, estat, reload, goTab }) {
  const [release, setRelease] = useState('');
  const [market, setMarket] = useState(null);
  const [price, setPrice] = useState('');
  const [fee, setFee] = useState(null);
  const [form, setForm] = useState({ limit: 200, factor: 1, step: 0.5, min_diff_pct: 5 });
  const [rows, setRows] = useState(null);
  const [selected, setSelected] = useState(new Set());
  const [error, setError] = useState('');
  const [msg, setMsg] = useState('');
  const [busy, setBusy] = useState(false);

  const job = estat?.job;
  const priceJob = job && job.mode === 'pricing_preview' ? job : null;
  const running = !!priceJob && ['queued', 'running'].includes(priceJob.status);

  async function lookup() {
    setError('');
    setMarket(null);
    const r = await api(`${CH}/pricing/release/${encodeURIComponent(release.trim())}`);
    if (!r.ok) { setError(r.data.detail || 'No s\'ha pogut consultar Discogs.'); return; }
    setMarket(r.data);
  }

  async function lookupFee() {
    setError('');
    const r = await api(`${CH}/pricing/fee?price=${encodeURIComponent(price)}`);
    if (!r.ok) { setError(r.data.detail || 'No s\'ha pogut consultar la comissió.'); return; }
    setFee(r.data);
  }

  async function startPreview() {
    setError('');
    setMsg('');
    setRows(null);
    const r = await api(`${CH}/pricing/preview`, { method: 'POST', body: {
      limit: Number(form.limit), factor: Number(form.factor), step: Number(form.step), min_diff_pct: Number(form.min_diff_pct),
    } });
    if (!r.ok) { setError(r.data.detail || (Array.isArray(r.data.detail) ? 'Paràmetres no vàlids' : 'No s\'ha pogut iniciar.')); return; }
    reload();
  }

  // Cuando acaba la simulación de precios, se cargan todas las filas (hasta 500, en páginas de 200).
  const loadRows = useCallback(async (jobId) => {
    const all = [];
    for (let offset = 0; offset < 600; offset += 200) {
      const r = await api(`${INV}/jobs/${jobId}/rows?limit=200&offset=${offset}`);
      if (!r.ok) break;
      all.push(...r.data.rows);
      if (all.length >= r.data.total) break;
    }
    setRows(all);
    setSelected(new Set(all.filter((x) => ['repreu_puja', 'repreu_baixa'].includes(x.accio)).map((x) => x.item_id)));
  }, []);
  useEffect(() => {
    if (priceJob && priceJob.status === 'done') loadRows(priceJob.id);
  }, [priceJob?.id, priceJob?.status, loadRows]);

  async function apply() {
    setBusy(true);
    setError('');
    const r = await api(`${CH}/pricing/apply`, { method: 'POST', body: { job_id: priceJob.id, item_ids: [...selected] } });
    setBusy(false);
    if (!r.ok) { setError(r.data.detail || 'No s\'han pogut aplicar els preus.'); return; }
    setMsg(`${r.data.aplicats} preus canviats a l'app${r.data.saltats.length ? ` · ${r.data.saltats.length} saltats (${[...new Set(r.data.saltats.map((s) => s.motiu))].join('; ')})` : ''}.`);
    setRows((rs) => rs.filter((x) => !selected.has(x.item_id)));
    setSelected(new Set());
  }

  const changeable = (rows || []).filter((r) => ['repreu_puja', 'repreu_baixa'].includes(r.accio));
  function toggle(id) { setSelected((s) => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n; }); }

  return (
    <div className="space-y-5">
      <ErrorBox>{error}</ErrorBox>

      <Panel title={t('discogs.prices.lookup', 'Consulta d\'un release')}>
        <div className="flex gap-2 items-end flex-wrap">
          <div className="w-48"><Field label={t('discogs.prices.release_id', 'ID de release de Discogs')}>
            <input value={release} onChange={(e) => setRelease(e.target.value)} className={inputCls} inputMode="numeric" />
          </Field></div>
          <Button size="sm" onClick={lookup} disabled={!/^\d+$/.test(release.trim())}>{t('discogs.prices.consult', 'Consultar')}</Button>
          <div className="w-32 ml-6"><Field label={t('discogs.prices.price', 'Comissió d\'un preu (€)')}>
            <input value={price} onChange={(e) => setPrice(e.target.value)} className={inputCls} inputMode="decimal" />
          </Field></div>
          <Button size="sm" variant="secondary" onClick={lookupFee} disabled={!(Number(price) > 0)}>{t('discogs.prices.fee', 'Comissió')}</Button>
          {fee && <span className="text-sm text-secondary-foreground">{fmtPrice(fee.value)} {fee.currency !== 'EUR' ? fee.currency : ''}</span>}
        </div>
        {market && (
          <div className="grid md:grid-cols-2 gap-4 text-sm pt-2">
            <div>
              <p className="font-medium text-on-surface mb-1">{t('discogs.market.suggested', 'Preus suggerits per Discogs')}</p>
              {Object.keys(market.suggestions || {}).length === 0
                ? <p className="text-secondary-foreground">{t('discogs.market.none', 'Sense suggeriments per a aquest release.')}</p>
                : <ul>{Object.entries(market.suggestions).map(([k, v]) => <li key={k}>{k}: <b>{fmtPrice(v.value)}</b></li>)}</ul>}
            </div>
            <div>
              <p className="font-medium text-on-surface mb-1">{t('discogs.market.market', 'Mercat')}</p>
              <p>{t('discogs.market.lowest', 'Preu més baix')}: <b>{fmtPrice(market.stats?.lowest_price?.value)}</b></p>
              <p>{t('discogs.market.for_sale', 'A la venda')}: <b>{market.stats?.num_for_sale ?? '—'}</b></p>
            </div>
          </div>
        )}
      </Panel>

      <Panel title={t('discogs.prices.bulk', 'Simulació de reprecio massiu')}>
        <p className="text-xs text-secondary-foreground max-w-2xl">
          {t('discogs.prices.bulk_hint', 'Consulta el preu suggerit per Discogs per a l\'estat de cada disc a la venda i proposa un preu nou. No canvia res fins que l\'apliques. Cada release és una consulta (~1 s), així que va per tandes.')}
        </p>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3 items-end">
          <Field label={t('discogs.prices.limit', 'Items (màx. 500)')}><input type="number" min="1" max="500" value={form.limit} onChange={(e) => setForm({ ...form, limit: e.target.value })} className={inputCls} /></Field>
          <Field label={t('discogs.prices.factor', 'Factor sobre el suggerit')}><input type="number" step="0.05" min="0.1" max="3" value={form.factor} onChange={(e) => setForm({ ...form, factor: e.target.value })} className={inputCls} /></Field>
          <Field label={t('discogs.prices.step', 'Arrodoniment (€)')}><input type="number" step="0.25" min="0" value={form.step} onChange={(e) => setForm({ ...form, step: e.target.value })} className={inputCls} /></Field>
          <Field label={t('discogs.prices.min_diff', 'Només si difereix ≥ (%)')}><input type="number" step="1" min="0" max="100" value={form.min_diff_pct} onChange={(e) => setForm({ ...form, min_diff_pct: e.target.value })} className={inputCls} /></Field>
          <Button onClick={startPreview} disabled={running}>
            <MIcon name={running ? 'progress_activity' : 'price_change'} size={16} className={running ? 'animate-spin' : ''} />
            {running ? t('discogs.canal.running', 'En marxa…') : t('discogs.prices.simulate', 'Simular')}
          </Button>
        </div>
      </Panel>

      {running && <ProgressPanel t={t} job={priceJob} />}
      {priceJob && priceJob.status === 'error' && <ErrorBox>{priceJob.error}</ErrorBox>}
      {msg && <div className="bg-green-50 text-green-800 border border-green-200 rounded-xl px-4 py-3 text-sm">{msg} <button type="button" className="underline ml-2" onClick={() => goTab('listings', { accio: 'actualitzar_preu' })}>{t('discogs.prices.go_listings', 'Propagar a Discogs (Listings)')}</button></div>}

      {priceJob && priceJob.status === 'done' && rows && (
        <div className="bg-card rounded-2xl border border-outline-variant shadow-sm overflow-hidden">
          <div className="p-4 flex items-center justify-between gap-3 flex-wrap border-b border-outline-variant">
            <p className="text-sm text-on-surface">
              {priceJob.summary.puja} {t('discogs.prices.up', 'pugen')} · {priceJob.summary.baixa} {t('discogs.prices.down', 'baixen')} · {priceJob.summary.igual} {t('discogs.prices.same', 'igual')} · {priceJob.summary.sense_suggeriment} {t('discogs.prices.no_sug', 'sense suggeriment')}
              {priceJob.summary.errors ? ` · ${priceJob.summary.errors} errors` : ''}
            </p>
            <Button disabled={busy || selected.size === 0} onClick={apply}>
              {t('discogs.prices.apply', 'Aplicar preus seleccionats')} ({selected.size})
            </Button>
          </div>
          <div className="overflow-x-auto max-h-[520px]">
            <table className="w-full text-sm">
              <thead className="bg-surface-container-high text-xs text-secondary-foreground border-b border-outline-variant sticky top-0">
                <tr>
                  <th className="px-3 py-3 w-8"><input type="checkbox" checked={changeable.length > 0 && selected.size === changeable.length}
                    onChange={(e) => setSelected(e.target.checked ? new Set(changeable.map((x) => x.item_id)) : new Set())} /></th>
                  <th className="px-3 py-3 text-left font-medium">{t('discogs.canal.col_disc', 'Disc')}</th>
                  <th className="px-3 py-3 text-left font-medium">{t('discogs.canal.col_cond', 'Condició')}</th>
                  <th className="px-3 py-3 text-right font-medium">{t('discogs.canal.col_price_app', 'Preu botiga')}</th>
                  <th className="px-3 py-3 text-right font-medium">{t('discogs.prices.col_suggested', 'Suggerit')}</th>
                  <th className="px-3 py-3 text-right font-medium">{t('discogs.canal.col_price_proposed', 'Preu proposat')}</th>
                  <th className="px-3 py-3 text-left font-medium">{t('discogs.canal.col_action', 'Acció')}</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => {
                  const can = ['repreu_puja', 'repreu_baixa'].includes(r.accio);
                  return (
                    <tr key={r.item_id} className="border-b border-outline-variant last:border-0">
                      <td className="px-3 py-2">{can && <input type="checkbox" checked={selected.has(r.item_id)} onChange={() => toggle(r.item_id)} />}</td>
                      <td className="px-3 py-2"><span className="font-medium text-on-surface">{r.artista || '—'}</span><span className="text-secondary-foreground"> — {r.titol}</span></td>
                      <td className="px-3 py-2 text-secondary-foreground">{r.estat_disc || (r.condicio === 'nou' ? 'Nou' : '—')}</td>
                      <td className="px-3 py-2 text-right tabular-nums">{fmtPrice(r.preu_app)}</td>
                      <td className="px-3 py-2 text-right tabular-nums">{fmtPrice(r.preu_discogs)}</td>
                      <td className="px-3 py-2 text-right tabular-nums font-medium">{fmtPrice(r.preu_proposat)}</td>
                      <td className="px-3 py-2" title={r.motiu}><Badge cls={ACTIONS[r.accio]?.cls}>{ACTIONS[r.accio]?.label || r.accio}</Badge> <span className="text-xs text-secondary-foreground">{r.motiu}</span></td>
                    </tr>
                  );
                })}
                {rows.length === 0 && <tr><td colSpan={7} className="px-4 py-8 text-center text-secondary-foreground">{t('common.no_results', 'Sense resultats')}</td></tr>}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
