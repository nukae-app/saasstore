'use client';

// Sincronització d'inventari Discogs -> app. Dos passos: SIMULACIÓ (no guarda
// res; es revisa la llista) i EXECUCIÓ REAL (només amb una simulació recent).
// Només BAIXA dades de Discogs: el mode "només lectura" (Configuració) no
// l'afecta, perquè aquest bloqueja escriure a Discogs. Vegeu
// docs/PLAN_CANAL_DISCOGS.md §8 i api/app/routers/admin/discogs_inventory.py.

import { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import { authFetch } from '../../../lib/auth';
import { useT } from '../../../lib/i18n';
import { Button } from '../../../../components/ui/button';
import MIcon from '../../../../components/ui/m-icon';

const BASE = '/admin/discogs/inventory';
const DAY_MS = 24 * 3600 * 1000;
const PAGE = 50;

const ACTIONS = {
  crear: { label: 'Crear', cls: 'bg-green-100 text-green-800' },
  sumar_nou: { label: 'Sumar a línia nou', cls: 'bg-green-100 text-green-800' },
  actualitzar_preu: { label: 'Actualitzar preu', cls: 'bg-blue-100 text-blue-800' },
  actualitzar_data_entrada: { label: 'Data d\'entrada', cls: 'bg-blue-100 text-blue-800' },
  retirar: { label: 'Retirar', cls: 'bg-amber-100 text-amber-800' },
  descomptar_nou: { label: 'Descomptar 1 (nou)', cls: 'bg-amber-100 text-amber-800' },
  error: { label: 'Error', cls: 'bg-red-100 text-red-800' },
};

const PHASES = {
  connexio: 'Connectant amb Discogs…',
  inventari: 'Descarregant l\'inventari de Discogs',
  consolidacio: 'Consolidant línies duplicades',
  processar: 'Comparant amb la botiga',
  retirar: 'Calculant retirades',
  fet: 'Acabant…',
};

function fmtPrice(v) {
  if (v === null || v === undefined || v === '') return '—';
  const n = Number(v);
  return Number.isNaN(n) ? v : `${n.toFixed(2)} €`;
}

export default function DiscogsCanalPage() {
  const t = useT();
  const [account, setAccount] = useState(null);
  const [estat, setEstat] = useState(null);
  const [error, setError] = useState('');
  const [starting, setStarting] = useState(false);

  const loadAccount = useCallback(async () => {
    const r = await authFetch('/admin/secrets/discogs-account');
    if (r.ok) setAccount(await r.json());
  }, []);

  const loadEstat = useCallback(async () => {
    const r = await authFetch(`${BASE}/jobs/current`);
    if (r.ok) setEstat(await r.json());
    else if (r.status === 404) setEstat({ disabled: true });
  }, []);

  useEffect(() => { loadAccount(); loadEstat(); }, [loadAccount, loadEstat]);

  const job = estat?.job || null;
  const running = !!job && ['queued', 'running'].includes(job.status);

  useEffect(() => {
    if (!running) return undefined;
    const id = setInterval(loadEstat, 2000);
    return () => clearInterval(id);
  }, [running, loadEstat]);

  // Quan una execució real acaba, l'estat d'adopció de la cuenta canvia.
  useEffect(() => {
    if (job?.mode === 'apply' && job?.status === 'done') loadAccount();
  }, [job?.id, job?.status, job?.mode, loadAccount]);

  async function start(mode, extra = {}) {
    setError('');
    setStarting(true);
    try {
      const r = await authFetch(`${BASE}/jobs`, { method: 'POST', body: JSON.stringify({ mode, ...extra }) });
      const body = await r.json().catch(() => ({}));
      if (!r.ok) {
        setError(body.detail || t('discogs.canal.start_error', 'No s\'ha pogut iniciar la sincronització.'));
      } else {
        setEstat(body);
      }
    } finally {
      setStarting(false);
    }
  }

  if (estat === null) {
    return <div className="p-12 text-center text-secondary-foreground text-sm">{t('common.loading')}</div>;
  }
  if (estat.disabled) {
    return (
      <div className="max-w-3xl mx-auto bg-card rounded-2xl border border-outline-variant p-6 text-sm text-secondary-foreground">
        {t('discogs.canal.disabled', 'La sincronització amb Discogs està desactivada.')}{' '}
        <Link href="/admin/configuracio" className="text-primary underline">{t('nav.configuracio', 'Configuració')}</Link>
      </div>
    );
  }

  const simulacio = estat.ultima_simulacio;
  const simulacioRecent = !!simulacio && Date.now() - new Date(simulacio.finished_at).getTime() < DAY_MS;
  const adopcioFeta = !!account?.adopcio_feta;

  return (
    <div className="space-y-5 max-w-6xl mx-auto">
      <div>
        <h2 className="text-2xl font-bold text-on-surface">{t('discogs.canal.title', 'Sincronització amb Discogs')}</h2>
        <p className="text-sm text-secondary-foreground mt-1 max-w-3xl">
          {t('discogs.canal.intro', 'Primera càrrega: Discogs mana. Es compara l\'inventari de Discogs amb la botiga i es crea, s\'actualitza el preu o es retira el que calgui. Primer es fa una simulació que no guarda res; revisa-la i només llavors aplica-la. A partir d\'aquí, la font de veritat és l\'app.')}
        </p>
      </div>

      <AccountCard t={t} account={account} />

      {error && <div className="bg-red-50 text-red-700 border border-red-200 rounded-xl px-4 py-3 text-sm">{error}</div>}

      <StepSimulation
        t={t} running={running} starting={starting} job={job} adopcioFeta={adopcioFeta}
        onStart={() => start('dry_run')}
      />

      {job && job.status === 'error' && <JobError t={t} job={job} />}
      {job && job.status === 'stalled' && (
        <div className="bg-amber-50 text-amber-800 border border-amber-200 rounded-xl px-4 py-3 text-sm">
          {t('discogs.canal.stalled', 'La sincronització sembla encallada (fa minuts que no dona senyal). Pots tornar-la a llançar.')}
        </div>
      )}

      {running && <ProgressPanel t={t} job={job} />}

      {job && job.status === 'done' && job.mode === 'dry_run' && (
        <>
          <Summary t={t} summary={job.summary} title={t('discogs.canal.sim_result', 'Resultat de la simulació (res s\'ha guardat)')} />
          <Results t={t} jobId={job.id} />
        </>
      )}

      {job && job.status === 'done' && job.mode === 'apply' && (
        <>
          <Summary t={t} summary={job.summary} title={t('discogs.canal.apply_result', 'Sincronització aplicada')} applied />
          <Results t={t} jobId={job.id} />
        </>
      )}

      {!adopcioFeta && simulacioRecent && !running && (
        <ApplyPanel t={t} simulacio={simulacio} starting={starting} onApply={(force) => start('apply', { force })} />
      )}
    </div>
  );
}

function AccountCard({ t, account }) {
  if (!account) return null;
  return (
    <div className="bg-card rounded-2xl border border-outline-variant shadow-sm p-5 flex flex-wrap items-center gap-x-8 gap-y-3">
      <div>
        <p className="text-xs text-secondary-foreground">{t('discogs.canal.account', 'Compte de Discogs')}</p>
        {!account.configured ? (
          <p className="text-sm font-medium text-red-600">{t('discogs.canal.no_token', 'Sense token configurat')}</p>
        ) : account.username ? (
          <p className="text-sm font-medium text-on-surface">{account.username}</p>
        ) : (
          <p className="text-sm font-medium text-red-600">{account.error}</p>
        )}
      </div>
      <div>
        <p className="text-xs text-secondary-foreground">{t('discogs.canal.mode', 'Mode')}</p>
        <span className={`inline-block text-xs font-medium px-2 py-0.5 rounded-full ${account.solo_lectura ? 'bg-amber-100 text-amber-800' : 'bg-green-100 text-green-800'}`}>
          {account.solo_lectura ? t('discogs.canal.read_only', 'Només lectura') : t('discogs.canal.read_write', 'Lectura i escriptura')}
        </span>
      </div>
      <div>
        <p className="text-xs text-secondary-foreground">{t('discogs.canal.adoption', 'Càrrega inicial')}</p>
        <span className={`inline-block text-xs font-medium px-2 py-0.5 rounded-full ${account.adopcio_feta ? 'bg-green-100 text-green-800' : 'bg-surface-container-high text-secondary-foreground'}`}>
          {account.adopcio_feta ? t('discogs.canal.adoption_done', 'Feta') : t('discogs.canal.adoption_pending', 'Pendent')}
        </span>
      </div>
      <p className="text-xs text-secondary-foreground max-w-md">
        {t('discogs.canal.read_only_note', 'Aquesta pantalla només baixa dades de Discogs: el mode només lectura no l\'afecta.')}{' '}
        <Link href="/admin/configuracio" className="text-primary underline">{t('discogs.canal.go_config', 'Canviar a Configuració')}</Link>
      </p>
    </div>
  );
}

function StepSimulation({ t, running, starting, job, adopcioFeta, onStart }) {
  return (
    <div className="bg-card rounded-2xl border border-outline-variant shadow-sm p-5 flex items-center justify-between gap-4 flex-wrap">
      <div>
        <p className="text-sm font-semibold text-on-surface">{t('discogs.canal.step1', '1. Simulació')}</p>
        <p className="text-xs text-secondary-foreground mt-1 max-w-xl">
          {adopcioFeta
            ? t('discogs.canal.step1_done_hint', 'La càrrega inicial ja està feta. Pots tornar a simular per veure diferències, però no es pot tornar a aplicar.')
            : t('discogs.canal.step1_hint', 'Descarrega l\'inventari de Discogs i calcula què canviaria, sense modificar res. Pot trigar uns minuts.')}
        </p>
      </div>
      <Button onClick={onStart} disabled={running || starting}>
        <MIcon name={running ? 'progress_activity' : 'search'} size={16} className={running ? 'animate-spin' : ''} />
        {running ? t('discogs.canal.running', 'En marxa…') : job?.mode === 'dry_run' && job.status === 'done'
          ? t('discogs.canal.repeat', 'Tornar a simular')
          : t('discogs.canal.analyze', 'Analitzar Discogs')}
      </Button>
    </div>
  );
}

function ProgressPanel({ t, job }) {
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

function JobError({ t, job }) {
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

function Summary({ t, summary, title, applied = false }) {
  if (!summary) return null;
  const tiles = [
    { k: 'creats', label: t('discogs.canal.tile_create', 'A crear'), cls: 'text-green-700' },
    { k: 'sumats', label: t('discogs.canal.tile_sum', 'A sumar a línia nou'), cls: 'text-green-700' },
    { k: 'actualitzats', label: t('discogs.canal.tile_update', 'Preus/dates a actualitzar'), cls: 'text-blue-700' },
    { k: 'retirats', label: t('discogs.canal.tile_retire', 'A retirar'), cls: 'text-amber-700' },
    { k: 'errors', label: t('discogs.canal.tile_errors', 'Errors'), cls: 'text-red-700' },
  ];
  return (
    <div className="bg-card rounded-2xl border border-outline-variant shadow-sm p-5 space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <p className="text-sm font-semibold text-on-surface">{title}</p>
        <p className="text-xs text-secondary-foreground">
          {summary.listings} {t('discogs.canal.listings_found', 'listings a Discogs')} · {summary.compte_discogs}
        </p>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        {tiles.map(({ k, label, cls }) => (
          <div key={k} className="rounded-xl bg-surface-container-high px-4 py-3">
            <p className={`text-2xl font-bold ${cls}`}>{summary[k]}</p>
            <p className="text-xs text-secondary-foreground mt-1">{label}</p>
          </div>
        ))}
      </div>
      {summary.avisos?.length > 0 && (
        <div className="bg-amber-50 border border-amber-200 text-amber-800 rounded-xl px-4 py-3 text-sm space-y-1">
          {summary.avisos.map((a, i) => <p key={i}>⚠ {a}</p>)}
        </div>
      )}
      {applied && summary.adopcio_marcada && (
        <p className="text-sm text-green-700">{t('discogs.canal.adoption_marked', 'Càrrega inicial marcada com a feta: a partir d\'ara l\'app és la font de veritat.')}</p>
      )}
    </div>
  );
}

function Results({ t, jobId }) {
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
    authFetch(`${BASE}/jobs/${jobId}/rows?${params}`).then(async (r) => {
      if (r.ok && !cancelled) setData(await r.json());
    });
    return () => { cancelled = true; };
  }, [jobId, accio, q, page]);

  async function download() {
    setDownloading(true);
    try {
      const r = await authFetch(`${BASE}/jobs/${jobId}/report.csv`);
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
                <td className="px-4 py-2.5 text-secondary-foreground tabular-nums">{r.codi_discogs || '—'}</td>
                <td className="px-4 py-2.5 text-xs text-secondary-foreground">{r.motiu}</td>
              </tr>
            ))}
            {data.rows.length === 0 && (
              <tr><td colSpan={7} className="px-4 py-8 text-center text-secondary-foreground">{t('common.no_results', 'Sense resultats')}</td></tr>
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

function ApplyPanel({ t, simulacio, starting, onApply }) {
  const s = simulacio.summary || {};
  const needsForce = (s.avisos || []).length > 0;
  const [backup, setBackup] = useState(false);
  const [force, setForce] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const ready = backup && (!needsForce || force);

  return (
    <div className="bg-card rounded-2xl border border-red-200 shadow-sm p-5 space-y-4">
      <div>
        <p className="text-sm font-semibold text-on-surface">{t('discogs.canal.step2', '2. Aplicar a la botiga')}</p>
        <p className="text-xs text-secondary-foreground mt-1 max-w-2xl">
          {t('discogs.canal.step2_hint', 'Executa de veritat el que ha mostrat l\'última simulació: modifica la base de dades de la botiga. No escriu res a Discogs. Només es pot fer una vegada: després l\'app és la font de veritat.')}
        </p>
      </div>
      <label className="flex items-start gap-2 text-sm">
        <input type="checkbox" checked={backup} onChange={(e) => setBackup(e.target.checked)} className="mt-0.5" />
        <span>{t('discogs.canal.backup_check', 'He fet una còpia de seguretat de l\'inventari de Discogs i de la base de dades.')}</span>
      </label>
      {needsForce && (
        <label className="flex items-start gap-2 text-sm text-amber-800">
          <input type="checkbox" checked={force} onChange={(e) => setForce(e.target.checked)} className="mt-0.5" />
          <span>{t('discogs.canal.force_check', 'Entenc els avisos de la simulació i vull continuar igualment.')}</span>
        </label>
      )}
      {!confirming ? (
        <Button disabled={!ready || starting} onClick={() => setConfirming(true)}>
          <MIcon name="sync" size={16} /> {t('discogs.canal.apply', 'Aplicar sincronització')}
        </Button>
      ) : (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4 space-y-3">
          <p className="text-sm text-red-800">
            {t('discogs.canal.confirm_text', 'Es crearan {c}, se sumaran {s}, s\'actualitzaran {u} i es retiraran {r} ítems.')
              .replace('{c}', s.creats ?? 0).replace('{s}', s.sumats ?? 0)
              .replace('{u}', s.actualitzats ?? 0).replace('{r}', s.retirats ?? 0)}
          </p>
          <div className="flex gap-2">
            <Button disabled={starting} onClick={() => onApply(force)}>
              {t('discogs.canal.confirm_apply', 'Sí, aplica-ho')}
            </Button>
            <Button variant="secondary" onClick={() => setConfirming(false)}>{t('common.cancel', 'Cancel·la')}</Button>
          </div>
        </div>
      )}
    </div>
  );
}
