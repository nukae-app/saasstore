'use client';

// Piezas comunes de las pestañas del centro de control de Discogs.

import { useState, useEffect } from 'react';
import { authFetch } from '../../../lib/auth';
import { Button } from '../../../../components/ui/button';
import MIcon from '../../../../components/ui/m-icon';

export const INV = '/admin/discogs/inventory';        // trabajos en segundo plano, informes e historial
export const CH = '/admin/channels/discogs';          // resumen, listings, alertas, ajustes...
export const DAY_MS = 24 * 3600 * 1000;
export const PAGE = 50;

export const ACTIONS = {
  crear: { label: 'Crear', cls: 'bg-green-100 text-green-800' },
  sumar_nou: { label: 'Sumar a línia nou', cls: 'bg-green-100 text-green-800' },
  actualitzar_preu: { label: 'Actualitzar preu', cls: 'bg-blue-100 text-blue-800' },
  actualitzar_data_entrada: { label: 'Data d\'entrada', cls: 'bg-blue-100 text-blue-800' },
  retirar: { label: 'Retirar', cls: 'bg-amber-100 text-amber-800' },
  descomptar_nou: { label: 'Descomptar 1 (nou)', cls: 'bg-amber-100 text-amber-800' },
  error: { label: 'Error', cls: 'bg-red-100 text-red-800' },
  publicar: { label: 'Publicar', cls: 'bg-green-100 text-green-800' },
  vincular_release: { label: 'Vincular release', cls: 'bg-surface-container-high text-secondary-foreground' },
  ok: { label: 'Correcte', cls: 'bg-surface-container-high text-secondary-foreground' },
  res: { label: 'Res a fer', cls: 'bg-surface-container-high text-secondary-foreground' },
  repreu_puja: { label: 'Puja', cls: 'bg-blue-100 text-blue-800' },
  repreu_baixa: { label: 'Baixa', cls: 'bg-amber-100 text-amber-800' },
  igual: { label: 'Igual', cls: 'bg-surface-container-high text-secondary-foreground' },
  sense_suggeriment: { label: 'Sense suggeriment', cls: 'bg-surface-container-high text-secondary-foreground' },
  orfe_discogs: { label: 'Orfe a Discogs', cls: 'bg-amber-100 text-amber-800' },
  no_a_discogs: { label: 'Ja no és a Discogs', cls: 'bg-amber-100 text-amber-800' },
  preu_diferent: { label: 'Preu diferent', cls: 'bg-blue-100 text-blue-800' },
};

export const PHASES = {
  connexio: 'Connectant amb Discogs…',
  inventari: 'Descarregant l\'inventari de Discogs',
  consolidacio: 'Consolidant línies duplicades',
  processar: 'Comparant amb la botiga',
  retirar: 'Calculant retirades',
  aplicar: 'Aplicant a Discogs',
  comparar: 'Comparant amb la botiga',
  preus: 'Consultant preus de Discogs',
  fet: 'Acabant…',
};

export function fmtPrice(v) {
  if (v === null || v === undefined || v === '') return '—';
  const n = Number(v);
  return Number.isNaN(n) ? v : `${n.toFixed(2)} €`;
}


export const RUN_KIND = {
  inventory_dry_run: 'Simulació de càrrega', inventory_apply: 'Càrrega inicial', reconcile_apply: 'Reconciliació',
  audit: 'Auditoria', pricing_preview: 'Simulació de preus',
};
export const RUN_STATUS = {
  queued: { label: 'A la cua', cls: 'bg-surface-container-high text-secondary-foreground' },
  running: { label: 'En marxa', cls: 'bg-blue-100 text-blue-800' },
  done: { label: 'Acabada', cls: 'bg-green-100 text-green-800' },
  error: { label: 'Error', cls: 'bg-red-100 text-red-800' },
  stalled: { label: 'Encallada', cls: 'bg-amber-100 text-amber-800' },
};

export function fmtDate(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString('ca-ES', { dateStyle: 'short', timeStyle: 'short' });
}


export function ProgressPanel({ t, job }) {
  const pct = job.total > 0 ? Math.min(100, Math.round((job.done / job.total) * 100)) : null;
  const phase = PHASES[job.phase] || t('discogs.canal.queued', 'A la cua…');
  return (
    <div className="bg-card rounded-2xl border border-outline-variant shadow-sm p-5 space-y-3">
      <div className="flex items-center justify-between text-sm">
        <span className="font-medium text-on-surface">
          {phase}{job.phase === 'inventari' && job.total > 0 ? ` (${job.done}/${job.total})` : ''}
          {job.phase === 'processar' && job.total > 0 ? ` (${job.done}/${job.total})` : ''}
        </span>
        {pct !== null && <span className="text-secondary-foreground">{pct}%</span>}
      </div>
      <div className="h-2 rounded-full bg-surface-container-high overflow-hidden">
        <div className={`h-full bg-primary transition-all ${pct === null ? 'w-1/3 animate-pulse' : ''}`} style={pct === null ? undefined : { width: `${pct}%` }} />
      </div>
      {job.log?.length > 0 && (
        <details className="text-xs text-secondary-foreground">
          <summary className="cursor-pointer">{t('discogs.canal.log', 'Registre')}</summary>
          <pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap">{job.log.join('\n')}</pre>
        </details>
      )}
    </div>
  );
}

export function JobError({ t, job }) {
  return (
    <div className="bg-red-50 text-red-700 border border-red-200 rounded-xl px-4 py-3 text-sm space-y-1">
      <p className="font-semibold">
        {job.error_kind === 'abort'
          ? t('discogs.canal.aborted', 'S\'ha aturat per seguretat (no s\'ha modificat res)')
          : t('discogs.canal.failed', 'La sincronització ha fallat')}
      </p>
      <p>{job.error}</p>
    </div>
  );
}

export function Results({ t, jobId }) {
  const [data, setData] = useState({ total: 0, counts: {}, rows: [] });
  const [accio, setAccio] = useState('');
  const [q, setQ] = useState('');
  const [page, setPage] = useState(0);
  const [downloading, setDownloading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const params = new URLSearchParams({ limit: String(PAGE), offset: String(page * PAGE) });
    if (accio) params.set('accio', accio);
    if (q.trim()) params.set('q', q.trim());
    authFetch(`${INV}/jobs/${jobId}/rows?${params}`).then(async (r) => {
      if (r.ok && !cancelled) setData(await r.json());
    });
    return () => { cancelled = true; };
  }, [jobId, accio, q, page]);

  async function download() {
    setDownloading(true);
    try {
      const r = await authFetch(`${INV}/jobs/${jobId}/report.csv`);
      if (!r.ok) return;
      const url = URL.createObjectURL(await r.blob());
      const a = document.createElement('a');
      a.href = url;
      a.download = 'discogs_inventari.csv';
      a.click();
      URL.revokeObjectURL(url);
    } finally {
      setDownloading(false);
    }
  }

  const totalAll = Object.values(data.counts).reduce((a, b) => a + b, 0);
  if (totalAll === 0) {
    return (
      <div className="bg-card rounded-2xl border border-outline-variant p-6 text-sm text-secondary-foreground text-center">
        {t('discogs.canal.no_changes', 'Cap canvi: la botiga i Discogs ja coincideixen.')}
      </div>
    );
  }
  const pages = Math.max(1, Math.ceil(data.total / PAGE));
  const hasProposed = data.rows.some((r) => r.preu_proposat !== null && r.preu_proposat !== undefined && r.preu_proposat !== '');

  return (
    <div className="bg-card rounded-2xl border border-outline-variant shadow-sm overflow-hidden">
      <div className="p-4 flex items-center gap-3 flex-wrap border-b border-outline-variant">
        <select value={accio} onChange={(e) => { setAccio(e.target.value); setPage(0); }}
          className="border border-outline-variant rounded-xl px-3 py-2 text-sm bg-card focus:outline-none focus:ring-2 focus:ring-primary">
          <option value="">{t('discogs.canal.all_actions', 'Totes les accions')} ({totalAll})</option>
          {Object.entries(data.counts).map(([k, n]) => (
            <option key={k} value={k}>{ACTIONS[k]?.label || k} ({n})</option>
          ))}
        </select>
        <input value={q} onChange={(e) => { setQ(e.target.value); setPage(0); }}
          placeholder={t('discogs.canal.search_ph', 'Cerca per artista, títol o codi Discogs…')}
          className="flex-1 min-w-[200px] border border-outline-variant rounded-xl px-3 py-2 text-sm bg-card focus:outline-none focus:ring-2 focus:ring-primary" />
        <Button variant="secondary" size="sm" onClick={download} disabled={downloading}>
          <MIcon name="download" size={14} /> {t('discogs.canal.csv', 'Descarregar CSV')}
        </Button>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-surface-container-high text-xs text-secondary-foreground border-b border-outline-variant">
            <tr>
              <th className="px-4 py-3 text-left font-medium">{t('discogs.canal.col_action', 'Acció')}</th>
              <th className="px-4 py-3 text-left font-medium">{t('discogs.canal.col_disc', 'Disc')}</th>
              <th className="px-4 py-3 text-left font-medium">{t('discogs.canal.col_cond', 'Condició')}</th>
              <th className="px-4 py-3 text-right font-medium">{t('discogs.canal.col_price_app', 'Preu botiga')}</th>
              <th className="px-4 py-3 text-right font-medium">{t('discogs.canal.col_price_discogs', 'Preu Discogs')}</th>
              {hasProposed && <th className="px-4 py-3 text-right font-medium">{t('discogs.canal.col_price_proposed', 'Preu proposat')}</th>}
              <th className="px-4 py-3 text-left font-medium">{t('discogs.canal.col_code', 'Codi Discogs')}</th>
              <th className="px-4 py-3 text-left font-medium">{t('discogs.canal.col_reason', 'Motiu')}</th>
            </tr>
          </thead>
          <tbody>
            {data.rows.map((r, i) => (
              <tr key={`${r.codi_discogs}-${r.accio}-${i}`} className="border-b border-outline-variant last:border-0">
                <td className="px-4 py-2.5">
                  <span className={`inline-block text-xs font-medium px-2 py-0.5 rounded-full ${ACTIONS[r.accio]?.cls || 'bg-surface-container-high'}`}>
                    {ACTIONS[r.accio]?.label || r.accio}
                  </span>
                </td>
                <td className="px-4 py-2.5">
                  <span className="font-medium text-on-surface">{r.artista || '—'}</span>
                  <span className="text-secondary-foreground"> — {r.titol || '—'}</span>
                </td>
                <td className="px-4 py-2.5 text-secondary-foreground">{r.condicio || '—'}{r.estat_disc ? ` · ${r.estat_disc}` : ''}</td>
                <td className="px-4 py-2.5 text-right tabular-nums">{fmtPrice(r.preu_app)}</td>
                <td className="px-4 py-2.5 text-right tabular-nums">{fmtPrice(r.preu_discogs)}</td>
                {hasProposed && <td className="px-4 py-2.5 text-right tabular-nums font-medium">{fmtPrice(r.preu_proposat)}</td>}
                <td className="px-4 py-2.5 text-secondary-foreground tabular-nums">{r.codi_discogs || '—'}</td>
                <td className="px-4 py-2.5 text-xs text-secondary-foreground">{r.motiu}</td>
              </tr>
            ))}
            {data.rows.length === 0 && (
              <tr><td colSpan={hasProposed ? 8 : 7} className="px-4 py-8 text-center text-secondary-foreground">{t('common.no_results', 'Sense resultats')}</td></tr>
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
  );
}



export function Badge({ children, cls = 'bg-surface-container-high text-secondary-foreground' }) {
  return <span className={`inline-block text-xs font-medium px-2 py-0.5 rounded-full ${cls}`}>{children}</span>;
}

export function Panel({ title, children, className = '' }) {
  return (
    <div className={`bg-card rounded-2xl border border-outline-variant shadow-sm p-5 space-y-3 ${className}`}>
      {title && <p className="text-sm font-semibold text-on-surface">{title}</p>}
      {children}
    </div>
  );
}

export function ErrorBox({ children }) {
  if (!children) return null;
  return <div className="bg-red-50 text-red-700 border border-red-200 rounded-xl px-4 py-3 text-sm">{children}</div>;
}

/** POST/PUT/PATCH con JSON; devuelve { ok, status, data } (data = cuerpo JSON o {}). */
export async function api(path, { method = 'GET', body } = {}) {
  const r = await authFetch(path, { method, body: body === undefined ? undefined : JSON.stringify(body) });
  const data = await r.json().catch(() => ({}));
  return { ok: r.ok, status: r.status, data };
}
